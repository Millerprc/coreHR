from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.governance_models import OutboxEvent
from hris.modules.workforce.models import (
    AuditLog,
    Organization,
    OrganizationType,
    OrganizationVersion,
    RevenueTarget,
)
from hris.modules.workforce.organization_models import RevenueTargetMonth


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _command(expected_version: int) -> dict[str, object]:
    return {
        "expected_version": expected_version,
        "idempotency_key": str(uuid4()),
        "change_reason": "合成财务维度测试",
    }


def _months(amount: str, *, count: int = 12) -> list[dict[str, object]]:
    return [
        {"month": month, "amount": amount}
        for month in range(1, count + 1)
    ]


async def _seed_organization_tree(
    db_session: AsyncSession,
) -> tuple[Organization, Organization]:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    group_type = OrganizationType(
        code="FIN_TEST_GROUP",
        name="合成财务集团",
        sort_order=1,
        is_active=True,
    )
    bu_type = OrganizationType(
        code="FIN_TEST_BU",
        name="合成财务事业部",
        sort_order=2,
        is_active=True,
    )
    group = Organization(code="720001")
    child = Organization(code="720002")
    db_session.add_all([group_type, bu_type, group, child])
    await db_session.flush()
    db_session.add_all(
        [
            OrganizationVersion(
                organization_id=group.id,
                version=1,
                name="合成财务集团",
                organization_type_id=group_type.id,
                status="active",
                effective_from=today,
                is_current=True,
                change_reason="合成初始化",
            ),
            OrganizationVersion(
                organization_id=child.id,
                version=1,
                name="合成财务事业部",
                organization_type_id=bu_type.id,
                parent_organization_id=group.id,
                status="active",
                effective_from=today,
                is_current=True,
                change_reason="合成初始化",
            ),
        ]
    )
    await db_session.flush()
    return group, child


async def test_cost_allocation_is_versioned_and_must_equal_one_hundred(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    tomorrow = today + timedelta(days=1)
    _, child = await _seed_organization_tree(db_session)

    cost_centers: list[dict[str, object]] = []
    for code, name in (("CC_TEST_A", "合成成本中心A"), ("CC_TEST_B", "合成成本中心B")):
        response = await business_client.post(
            "/api/v1/cost-centers",
            headers=_auth(admin_token),
            json={
                "code": code,
                "name": name,
                "country_code": "CN",
                "effective_from": today.isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        cost_centers.append(response.json())

    first_command = _command(1)
    first_payload = {
        "effective_from": today.isoformat(),
        "lines": [
            {
                "cost_center_id": cost_centers[0]["id"],
                "allocation_percent": "60.0000",
            },
            {
                "cost_center_id": cost_centers[1]["id"],
                "allocation_percent": "40.0000",
            },
        ],
        "command": first_command,
    }
    first = await business_client.put(
        f"/api/v1/organizations/{child.id}/cost-allocation",
        headers=_auth(admin_token),
        json=first_payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 2

    repeated = await business_client.put(
        f"/api/v1/organizations/{child.id}/cost-allocation",
        headers=_auth(admin_token),
        json=first_payload,
    )
    assert repeated.status_code == 200
    assert repeated.json() == first.json()

    invalid = await business_client.put(
        f"/api/v1/organizations/{child.id}/cost-allocation",
        headers=_auth(admin_token),
        json={
            "effective_from": tomorrow.isoformat(),
            "lines": [
                {
                    "cost_center_id": cost_centers[0]["id"],
                    "allocation_percent": "60.0000",
                },
                {
                    "cost_center_id": cost_centers[1]["id"],
                    "allocation_percent": "39.9999",
                },
            ],
            "command": _command(2),
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "ALLOCATION_TOTAL_INVALID"

    future = await business_client.put(
        f"/api/v1/organizations/{child.id}/cost-allocation",
        headers=_auth(admin_token),
        json={
            "effective_from": tomorrow.isoformat(),
            "lines": [
                {
                    "cost_center_id": cost_centers[0]["id"],
                    "allocation_percent": "70.0000",
                },
                {
                    "cost_center_id": cost_centers[1]["id"],
                    "allocation_percent": "30.0000",
                },
            ],
            "command": _command(2),
        },
    )
    assert future.status_code == 200
    assert future.json()["version"] == 3

    current_view = await business_client.get(
        f"/api/v1/organizations/{child.id}/cost-allocation?effective_at={today.isoformat()}",
        headers=_auth(restricted_token),
    )
    future_view = await business_client.get(
        f"/api/v1/organizations/{child.id}/cost-allocation?effective_at={tomorrow.isoformat()}",
        headers=_auth(restricted_token),
    )
    assert {
        line["cost_center_id"]: line["allocation_percent"]
        for line in current_view.json()["lines"]
    } == {
        cost_centers[0]["id"]: "60.0000",
        cost_centers[1]["id"]: "40.0000",
    }
    assert {
        line["cost_center_id"]: line["allocation_percent"]
        for line in future_view.json()["lines"]
    } == {
        cost_centers[0]["id"]: "70.0000",
        cost_centers[1]["id"]: "30.0000",
    }

    denied = await business_client.post(
        "/api/v1/cost-centers",
        headers=_auth(restricted_token),
        json={
            "code": "CC_DENIED",
            "name": "无权限成本中心",
            "effective_from": today.isoformat(),
        },
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"

    allocation_audit = await db_session.scalar(
        select(AuditLog)
        .where(
            AuditLog.action == "organization.cost_allocation.set",
            AuditLog.object_id == child.id,
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(1)
    )
    assert allocation_audit is not None
    assert allocation_audit.before_payload["version"] == 2
    assert len(allocation_audit.before_payload["lines"]) == 2


async def test_revenue_targets_keep_months_versions_and_currency_separate(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    group, child = await _seed_organization_tree(db_session)
    year = 2027

    async def set_target(
        organization: Organization,
        currency: str,
        annual: str,
        monthly: str,
        expected_version: int = 1,
    ) -> dict[str, object]:
        response = await business_client.put(
            f"/api/v1/organizations/{organization.id}/revenue-targets/{year}/{currency}",
            headers=_auth(admin_token),
            json={
                "year": year,
                "currency_code": currency,
                "annual_amount": annual,
                "months": _months(monthly),
                "command": _command(expected_version),
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    group_cny = await set_target(group, "CNY", "120.0000", "10.0000")
    child_cny = await set_target(child, "CNY", "240.0000", "20.0000")
    child_usd = await set_target(child, "USD", "12.0000", "1.0000")
    assert len(group_cny["months"]) == len(child_cny["months"]) == 12
    assert child_usd["currency_code"] == "USD"

    missing_month = await business_client.put(
        f"/api/v1/organizations/{child.id}/revenue-targets/{year}/EUR",
        headers=_auth(admin_token),
        json={
            "year": year,
            "currency_code": "EUR",
            "annual_amount": "110.0000",
            "months": _months("10.0000", count=11),
            "command": _command(1),
        },
    )
    assert missing_month.status_code == 422
    assert missing_month.json()["code"] == "REVENUE_MONTH_SET_INVALID"

    wrong_total = await business_client.put(
        f"/api/v1/organizations/{child.id}/revenue-targets/{year}/EUR",
        headers=_auth(admin_token),
        json={
            "year": year,
            "currency_code": "EUR",
            "annual_amount": "120.0000",
            "months": _months("9.0000"),
            "command": _command(1),
        },
    )
    assert wrong_total.status_code == 422
    assert wrong_total.json()["code"] == "REVENUE_MONTH_TOTAL_INVALID"

    aggregate = await business_client.get(
        f"/api/v1/organizations/{group.id}/revenue-targets?year={year}&include_descendants=true",
        headers=_auth(restricted_token),
    )
    assert aggregate.status_code == 200
    totals = aggregate.json()["totals_by_currency"]
    assert totals["CNY"]["annual_amount"] == "360.0000"
    assert totals["CNY"]["months"]["1"] == "30.0000"
    assert totals["USD"]["annual_amount"] == "12.0000"
    assert set(totals) == {"CNY", "USD"}

    own_only = await business_client.get(
        f"/api/v1/organizations/{group.id}/revenue-targets?year={year}",
        headers=_auth(restricted_token),
    )
    assert set(own_only.json()["totals_by_currency"]) == {"CNY"}
    assert own_only.json()["totals_by_currency"]["CNY"]["annual_amount"] == "120.0000"
    assert own_only.json()["targets"] == [group_cny]

    updated_child = await set_target(
        child,
        "CNY",
        "360.0000",
        "30.0000",
        expected_version=2,
    )
    assert updated_child["version"] == 3
    target_count = await db_session.scalar(
        select(func.count())
        .select_from(RevenueTarget)
        .where(
            RevenueTarget.organization_id == child.id,
            RevenueTarget.year == year,
            RevenueTarget.currency_code == "CNY",
        )
    )
    month_count = await db_session.scalar(
        select(func.count())
        .select_from(RevenueTargetMonth)
        .join(RevenueTarget, RevenueTarget.id == RevenueTargetMonth.revenue_target_id)
        .where(
            RevenueTarget.organization_id == child.id,
            RevenueTarget.year == year,
            RevenueTarget.currency_code == "CNY",
        )
    )
    outbox = await db_session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.event_type == "organization.revenue_target.set",
            OutboxEvent.aggregate_id == child.id,
        )
    )
    revenue_audit = await db_session.scalar(
        select(AuditLog)
        .where(
            AuditLog.action == "organization.revenue_target.set",
            AuditLog.object_id == child.id,
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(1)
    )
    assert target_count == 2
    assert month_count == 24
    assert outbox is not None
    assert revenue_audit is not None
    assert revenue_audit.before_payload["annual_amount"] == "240.0000"
    assert len(revenue_audit.before_payload["months"]) == 12

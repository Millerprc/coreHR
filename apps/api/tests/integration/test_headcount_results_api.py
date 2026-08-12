from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import (
    Employment,
    EmploymentAssignment,
    JobCatalog,
    LegalEntity,
    Organization,
    Person,
)


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _month_end(period_month: date) -> date:
    next_month = (
        date(period_month.year + 1, 1, 1)
        if period_month.month == 12
        else date(period_month.year, period_month.month + 1, 1)
    )
    return next_month - timedelta(days=1)


async def test_headcount_results_freeze_override_and_immutable_snapshots(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    period_month = date.today().replace(day=1)
    planned_start = period_month + timedelta(days=9)
    month_end = _month_end(period_month)
    organization = Organization(code="732001")
    job = JobCatalog(
        code="JOB-HC-SYNTHETIC",
        name="合成编制职务",
        level_code="L6",
        grade_code="G2",
        class_code="C2",
        sequence_code="TECH",
        status="active",
        effective_from=period_month,
        attributes={},
    )
    legal = LegalEntity(
        code="LE-HC-SYNTHETIC",
        name="合成编制法人",
        country_code="CN",
        status="active",
        effective_from=period_month,
    )
    person = Person(
        employee_number="990001",
        legal_name="合成占编人员",
        display_name="合成占编人员",
        status="active",
    )
    db_session.add_all([organization, job, legal, person])
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="pending_start",
        planned_start_date=planned_start,
        contract_legal_entity_id=legal.id,
        payroll_legal_entity_id=legal.id,
        social_insurance_legal_entity_id=legal.id,
        tax_legal_entity_id=legal.id,
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    db_session.add(
        EmploymentAssignment(
            employment_id=employment.id,
            organization_id=organization.id,
            job_id=job.id,
            relation_type="primary",
            effective_from=planned_start,
            version=1,
        )
    )
    await db_session.flush()

    rule = await business_client.post(
        "/api/v1/workforce/occupancy-rules",
        headers=_auth(admin_token),
        json={
            "employee_type_code": "REGULAR",
            "counts_for_headcount": True,
            "effective_from": period_month.isoformat(),
            "change_reason": "正式员工计入编制",
        },
    )
    assert rule.status_code == 201, rule.text

    plan_payload = {
        "organization_id": str(organization.id),
        "job_id": str(job.id),
        "period_month": period_month.isoformat(),
        "planned_count": "10.00",
        "change_reason": "建立月度编制",
    }
    plan = await business_client.post(
        "/api/v1/workforce/headcount-plans",
        headers=_auth(admin_token),
        json=plan_payload,
    )
    assert plan.status_code == 201, plan.text
    assert plan.json()["version"] == 1

    timezone = ZoneInfo("Asia/Shanghai")
    start_snapshot_payload = {
        "snapshot_type": "month_start",
        "period_month": period_month.isoformat(),
        "timezone": "Asia/Shanghai",
        "boundary_at": datetime(
            period_month.year,
            period_month.month,
            1,
            tzinfo=timezone,
        ).isoformat(),
        "rule_version": "synthetic-v1",
        "reason": "月初快照",
    }
    start_snapshot = await business_client.post(
        "/api/v1/workforce/headcount-snapshots",
        headers=_auth(admin_token),
        json=start_snapshot_payload,
    )
    assert start_snapshot.status_code == 201, start_snapshot.text
    assert start_snapshot.json()["status"] == "completed"
    repeated_start = await business_client.post(
        "/api/v1/workforce/headcount-snapshots",
        headers=_auth(admin_token),
        json=start_snapshot_payload,
    )
    assert repeated_start.status_code == 201
    assert repeated_start.json()["id"] == start_snapshot.json()["id"]
    unlinked_revision = await business_client.post(
        "/api/v1/workforce/headcount-snapshots",
        headers=_auth(admin_token),
        json={**start_snapshot_payload, "reason": "未关联原批次的修订"},
    )
    assert unlinked_revision.status_code == 409
    assert unlinked_revision.json()["code"] == "SNAPSHOT_REVISION_PARENT_REQUIRED"

    end_snapshot = await business_client.post(
        "/api/v1/workforce/headcount-snapshots",
        headers=_auth(admin_token),
        json={
            "snapshot_type": "month_end",
            "period_month": period_month.isoformat(),
            "timezone": "Asia/Shanghai",
            "boundary_at": datetime(
                month_end.year,
                month_end.month,
                month_end.day,
                23,
                59,
                59,
                tzinfo=timezone,
            ).isoformat(),
            "rule_version": "synthetic-v1",
            "reason": "月末快照",
        },
    )
    assert end_snapshot.status_code == 201, end_snapshot.text

    now = datetime.now(UTC)
    freeze = await business_client.post(
        "/api/v1/workforce/headcount-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": "month_close",
            "period_month": period_month.isoformat(),
            "organization_id": str(organization.id),
            "job_id": str(job.id),
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "reason": "合成月结冻结",
        },
    )
    assert freeze.status_code == 201, freeze.text

    blocked = await business_client.post(
        "/api/v1/workforce/headcount-plans",
        headers=_auth(admin_token),
        json={**plan_payload, "planned_count": "12.00", "change_reason": "冻结后普通修改"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "HEADCOUNT_PLAN_FROZEN"

    overridden = await business_client.post(
        "/api/v1/workforce/headcount-plans",
        headers=_auth(admin_token),
        json={
            **plan_payload,
            "planned_count": "12.00",
            "change_reason": "授权绕过冻结修订",
            "override_freeze": True,
        },
    )
    assert overridden.status_code == 201, overridden.text
    assert overridden.json()["version"] == 2

    result = await business_client.get(
        "/api/v1/workforce/headcount-results",
        headers=_auth(admin_token),
        params={
            "period_month": period_month.isoformat(),
            "as_of": planned_start.isoformat(),
            "organization_id": str(organization.id),
            "job_id": str(job.id),
        },
    )
    assert result.status_code == 200, result.text
    [line] = result.json()["items"]
    assert Decimal(line["planned_count"]) == Decimal("12.00")
    assert line["current_count"] == 1
    assert Decimal(line["variance"]) == Decimal("11.00")
    assert line["month_start_count"] == 0
    assert line["month_end_count"] == 1
    assert Decimal(line["average_count"]) == Decimal("0.5")
    assert line["frozen"] is True

    closed = await business_client.post(
        f"/api/v1/workforce/headcount-freezes/{freeze.json()['id']}/close",
        headers=_auth(admin_token),
        json={"reason": "完成授权修订后解冻"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    third_version = await business_client.post(
        "/api/v1/workforce/headcount-plans",
        headers=_auth(admin_token),
        json={**plan_payload, "planned_count": "13.00", "change_reason": "解冻后调整"},
    )
    assert third_version.status_code == 201, third_version.text
    assert third_version.json()["version"] == 3

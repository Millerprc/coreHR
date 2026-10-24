# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""发假明细（额度规则 / 发放批次 / 发放明细行）与时点余额查询的集成测试。

Requirement: D-107 —— 规则取值缺失时计提跳过并记录可读原因，不得用默认值硬算。
Requirement: D-097 —— 单个发放批次最多 1000 条明细。
"""

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.attendance.accrual_scheduler import (
    LeaveAccrualSchedulerSettings,
    main as accrual_scheduler_main,
)
from hris.modules.attendance.grant_service import LeaveGrantService
from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _employment(db_session: AsyncSession, employee_number: str) -> Employment:
    person = Person(
        employee_number=employee_number,
        legal_name=f"Grant {employee_number}",
        display_name=f"Grant {employee_number}",
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=date(2026, 1, 1),
        actual_start_date=date(2026, 1, 1),
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()
    return employment


async def _leave_type(
    business_client: AsyncClient,
    admin_token: str,
    *,
    code: str,
    balance_mode: str = "enforced",
) -> dict[str, object]:
    response = await business_client.post(
        "/api/v1/attendance/leave-types",
        headers=_auth(admin_token),
        json={
            "code": code,
            "name": f"Synthetic {code}",
            "unit": "day",
            "rules": {"balance_mode": balance_mode},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _grant_batch(
    business_client: AsyncClient,
    admin_token: str,
    *,
    period_code: str,
    grant_date: str,
    employment_id: object,
    leave_type_id: object,
    days: str,
) -> dict[str, object]:
    response = await business_client.post(
        "/api/v1/attendance/leave-grant-batches",
        headers=_auth(admin_token),
        json={
            "period_code": period_code,
            "period_type": "month",
            "grant_date": grant_date,
            "source": "manual",
            "items": [
                {
                    "employment_id": str(employment_id),
                    "leave_type_id": str(leave_type_id),
                    "grant_days": days,
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_grant_batch_issues_ledger_and_keeps_balance_identity(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992101")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_GRANT_ANNUAL",
    )

    batch = await _grant_batch(
        business_client,
        admin_token,
        period_code="2026-01",
        grant_date="2026-01-01",
        employment_id=employment.id,
        leave_type_id=leave_type["id"],
        days="5.00",
    )
    assert batch["status"] == "draft"

    detail = await business_client.get(
        f"/api/v1/attendance/leave-grant-batches/{batch['id']}",
        headers=_auth(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["items"]) == 1
    assert detail.json()["items"][0]["status"] == "pending"

    issued = await business_client.post(
        f"/api/v1/attendance/leave-grant-batches/{batch['id']}/issue",
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "issued"
    assert issued.json()["issued_at"] is not None

    detail_after = await business_client.get(
        f"/api/v1/attendance/leave-grant-batches/{batch['id']}",
        headers=_auth(admin_token),
    )
    item = detail_after.json()["items"][0]
    assert item["status"] == "issued"
    assert item["account_id"] is not None
    assert item["transaction_id"] is not None

    accounts = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}&period_year=2026",
        headers=_auth(admin_token),
    )
    assert accounts.status_code == 200, accounts.text
    account = accounts.json()["items"][0]
    assert account["current_balance"] == "5.00"
    assert account["as_of"] is None
    assert account["balance_as_of"] is None

    ledger = await business_client.get(
        f"/api/v1/attendance/leave-balances/{account['id']}/transactions",
        headers=_auth(admin_token),
    )
    assert ledger.status_code == 200, ledger.text
    transaction = ledger.json()["items"][0]
    assert transaction["transaction_type"] == "grant"
    assert transaction["amount"] == "5.00"
    assert transaction["balance_before"] == "0.00"
    assert transaction["balance_after"] == "5.00"
    assert transaction["source_type"] == "leave_grant_item"

    replay = await business_client.post(
        f"/api/v1/attendance/leave-grant-batches/{batch['id']}/issue",
        headers=_auth(admin_token),
    )
    assert replay.status_code == 409, replay.text


async def test_point_in_time_balance_uses_transaction_effective_date(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992102")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_GRANT_POINT",
    )

    first = await _grant_batch(
        business_client,
        admin_token,
        period_code="2026-01",
        grant_date="2026-01-01",
        employment_id=employment.id,
        leave_type_id=leave_type["id"],
        days="5.00",
    )
    assert (
        await business_client.post(
            f"/api/v1/attendance/leave-grant-batches/{first['id']}/issue",
            headers=_auth(admin_token),
        )
    ).status_code == 200

    second = await _grant_batch(
        business_client,
        admin_token,
        period_code="2026-06",
        grant_date="2026-06-01",
        employment_id=employment.id,
        leave_type_id=leave_type["id"],
        days="3.00",
    )
    assert (
        await business_client.post(
            f"/api/v1/attendance/leave-grant-batches/{second['id']}/issue",
            headers=_auth(admin_token),
        )
    ).status_code == 200

    current = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}&period_year=2026",
        headers=_auth(admin_token),
    )
    assert current.status_code == 200, current.text
    assert current.json()["items"][0]["current_balance"] == "8.00"

    as_of = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}"
        "&period_year=2026&as_of=2026-03-01",
        headers=_auth(admin_token),
    )
    assert as_of.status_code == 200, as_of.text
    account = as_of.json()["items"][0]
    assert account["as_of"] == "2026-03-01"
    assert account["balance_as_of"] == "5.00"
    assert account["current_balance"] == "8.00"

    as_of_after = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}"
        "&period_year=2026&as_of=2026-12-31",
        headers=_auth(admin_token),
    )
    assert as_of_after.json()["items"][0]["balance_as_of"] == "8.00"


async def test_accrual_skips_rules_without_enterprise_values(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992103")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_GRANT_ACCRUAL",
    )
    rule = await business_client.post(
        "/api/v1/attendance/leave-grant-rules",
        headers=_auth(admin_token),
        json={
            "code": "SYN_ACCRUAL_UNSET",
            "name": "Synthetic unset accrual rule",
            "leave_type_id": str(leave_type["id"]),
            "effective_from": "2026-01-01",
            # 额度天数、工龄折算等字段留空：规则待配置。
            "accrual_frequency": "2026-03",
        },
    )
    assert rule.status_code == 201, rule.text
    assert rule.json()["entitlement_days"] is None
    assert rule.json()["proration_method"] is None
    activated = await business_client.post(
        f"/api/v1/attendance/leave-grant-rules/{rule.json()['id']}/activate",
        headers=_auth(admin_token),
    )
    assert activated.status_code == 200, activated.text

    service = LeaveGrantService(db_session, actor_id=uuid4(), trace_id="synthetic-accrual")
    result = await service.run_accrual(
        period_code="2026-03",
        period_type="month",
        grant_date=date(2026, 3, 1),
    )
    assert result.created_items == 0
    assert result.batch_id is None
    assert [item.code for item in result.skipped] == ["LEAVE_GRANT_ENTITLEMENT_UNSET"]
    assert "待企业输入" in result.skipped[0].reason


async def test_accrual_creates_batch_once_and_issues_balance(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992104")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_GRANT_ACCRUAL_OK",
    )
    rule = await business_client.post(
        "/api/v1/attendance/leave-grant-rules",
        headers=_auth(admin_token),
        json={
            "code": "SYN_ACCRUAL_FLAT",
            "name": "Synthetic flat accrual rule",
            "leave_type_id": str(leave_type["id"]),
            "effective_from": "2026-01-01",
            "entitlement_days": "5.00",
            "accrual_frequency": "2026-03",
        },
    )
    assert rule.status_code == 201, rule.text
    await business_client.post(
        f"/api/v1/attendance/leave-grant-rules/{rule.json()['id']}/activate",
        headers=_auth(admin_token),
    )

    service = LeaveGrantService(db_session, actor_id=uuid4(), trace_id="synthetic-accrual")
    result = await service.run_accrual(
        period_code="2026-03",
        period_type="month",
        grant_date=date(2026, 3, 1),
    )
    assert result.created_items == 1
    assert result.batch_id is not None
    assert result.skipped == []

    replay = await service.run_accrual(
        period_code="2026-03",
        period_type="month",
        grant_date=date(2026, 3, 1),
    )
    assert replay.created_items == 0
    assert [item.code for item in replay.skipped] == ["LEAVE_GRANT_ALREADY_ACCRUED"]

    issued = await business_client.post(
        f"/api/v1/attendance/leave-grant-batches/{result.batch_id}/issue",
        headers=_auth(admin_token),
    )
    assert issued.status_code == 200, issued.text
    accounts = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}&period_year=2026",
        headers=_auth(admin_token),
    )
    assert accounts.json()["items"][0]["current_balance"] == "5.00"


async def test_grant_batch_rejects_oversized_payload(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992105")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_GRANT_LIMIT",
    )
    lines = [
        {
            "employment_id": str(employment.id),
            "leave_type_id": str(leave_type["id"]),
            "grant_days": "1.00",
        }
        for _ in range(1001)
    ]
    response = await business_client.post(
        "/api/v1/attendance/leave-grant-batches",
        headers=_auth(admin_token),
        json={
            "period_code": "2026-01",
            "period_type": "month",
            "grant_date": "2026-01-01",
            "source": "manual",
            "items": lines,
        },
    )
    assert response.status_code == 422, response.text


async def test_accrual_scheduler_is_disabled_by_default() -> None:
    """调度器默认关闭，关闭时不产生任何写入。"""
    settings = LeaveAccrualSchedulerSettings()
    assert settings.enabled is False
    assert accrual_scheduler_main([]) == 0


async def test_grant_rule_requires_existing_leave_type(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.post(
        "/api/v1/attendance/leave-grant-rules",
        headers=_auth(admin_token),
        json={
            "code": "SYN_NO_LEAVE_TYPE",
            "name": "Synthetic rule without leave type",
            "leave_type_id": str(uuid4()),
            "effective_from": "2026-01-01",
            "entitlement_days": "1.00",
        },
    )
    assert response.status_code == 404, response.text

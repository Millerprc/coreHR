from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _employment(db_session: AsyncSession, employee_number: str) -> Employment:
    person = Person(
        employee_number=employee_number,
        display_name=f"Leave balance {employee_number}",
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
    balance_mode: str,
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


async def _leave_request(
    business_client: AsyncClient,
    admin_token: str,
    *,
    employment_id: object,
    leave_type_id: object,
    start_date: str,
    end_date: str,
    amount: str,
) -> dict[str, object]:
    response = await business_client.post(
        "/api/v1/attendance/leave-requests",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment_id),
            "leave_type_id": str(leave_type_id),
            "start_date": start_date,
            "end_date": end_date,
            "amount": amount,
            "reason": "Synthetic balance test",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_enforced_balance_is_idempotent_and_reverses_after_cancellation(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "991001")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_ENFORCED",
        balance_mode="enforced",
    )
    idempotency_key = str(uuid4())
    grant_payload = {
        "employment_id": str(employment.id),
        "leave_type_id": leave_type["id"],
        "period_year": 2026,
        "transaction_type": "grant",
        "amount": "5.00",
        "effective_date": "2026-01-01",
        "reason": "Synthetic annual grant",
        "idempotency_key": idempotency_key,
    }
    first_grant = await business_client.post(
        "/api/v1/attendance/leave-balances/transactions",
        headers=_auth(admin_token),
        json=grant_payload,
    )
    assert first_grant.status_code == 201, first_grant.text
    assert first_grant.json()["balance_after"] == "5.00"
    duplicate_grant = await business_client.post(
        "/api/v1/attendance/leave-balances/transactions",
        headers=_auth(admin_token),
        json=grant_payload,
    )
    assert duplicate_grant.status_code == 201, duplicate_grant.text
    assert duplicate_grant.json()["id"] == first_grant.json()["id"]
    idempotency_conflict = await business_client.post(
        "/api/v1/attendance/leave-balances/transactions",
        headers=_auth(admin_token),
        json={**grant_payload, "amount": "6.00"},
    )
    assert idempotency_conflict.status_code == 409, idempotency_conflict.text

    leave = await _leave_request(
        business_client,
        admin_token,
        employment_id=employment.id,
        leave_type_id=leave_type["id"],
        start_date="2026-08-10",
        end_date="2026-08-11",
        amount="2.00",
    )
    approved = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{leave['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Synthetic approval"},
    )
    assert approved.status_code == 200, approved.text
    approved_again = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{leave['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Idempotency replay"},
    )
    assert approved_again.status_code == 200, approved_again.text

    accounts = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}&period_year=2026",
        headers=_auth(admin_token),
    )
    assert accounts.status_code == 200, accounts.text
    assert accounts.json()["total"] == 1
    assert accounts.json()["items"][0]["current_balance"] == "3.00"
    assert accounts.json()["items"][0]["version"] == 2

    excessive = await _leave_request(
        business_client,
        admin_token,
        employment_id=employment.id,
        leave_type_id=leave_type["id"],
        start_date="2026-09-01",
        end_date="2026-09-04",
        amount="4.00",
    )
    denied = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{excessive['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Should be denied"},
    )
    assert denied.status_code == 409, denied.text
    requests = await business_client.get(
        f"/api/v1/attendance/leave-requests?employment_id={employment.id}",
        headers=_auth(admin_token),
    )
    excessive_after = next(item for item in requests.json()["items"] if item["id"] == excessive["id"])
    assert excessive_after["status"] == "draft"

    cancellation = await business_client.post(
        f"/api/v1/attendance/leave-requests/{leave['id']}/cancel",
        headers=_auth(admin_token),
        json={"reason": "Synthetic cancellation"},
    )
    assert cancellation.status_code == 201, cancellation.text
    cancelled = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{cancellation.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Synthetic cancellation approval"},
    )
    assert cancelled.status_code == 200, cancelled.text
    accounts_after = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}&period_year=2026",
        headers=_auth(admin_token),
    )
    account = accounts_after.json()["items"][0]
    assert account["current_balance"] == "5.00"
    assert account["version"] == 3
    ledger = await business_client.get(
        f"/api/v1/attendance/leave-balances/{account['id']}/transactions",
        headers=_auth(admin_token),
    )
    assert ledger.status_code == 200, ledger.text
    assert [item["transaction_type"] for item in ledger.json()["items"]] == [
        "reversal",
        "usage",
        "grant",
    ]


async def test_tracked_mode_allows_negative_and_none_mode_creates_no_account(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "991002")
    tracked = await _leave_type(
        business_client,
        admin_token,
        code="SYN_TRACKED",
        balance_mode="tracked",
    )
    untracked = await _leave_type(
        business_client,
        admin_token,
        code="SYN_UNTRACKED",
        balance_mode="none",
    )
    tracked_leave = await _leave_request(
        business_client,
        admin_token,
        employment_id=employment.id,
        leave_type_id=tracked["id"],
        start_date="2026-08-12",
        end_date="2026-08-13",
        amount="2.00",
    )
    tracked_approved = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{tracked_leave['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Allow negative"},
    )
    assert tracked_approved.status_code == 200, tracked_approved.text

    tracked_cancelled = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{tracked_leave['id']}",
        headers=_auth(admin_token),
        json={"status": "cancelled", "change_reason": "Direct cancellation"},
    )
    assert tracked_cancelled.status_code == 200, tracked_cancelled.text

    untracked_leave = await _leave_request(
        business_client,
        admin_token,
        employment_id=employment.id,
        leave_type_id=untracked["id"],
        start_date="2026-08-14",
        end_date="2026-08-14",
        amount="1.00",
    )
    untracked_approved = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{untracked_leave['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "No balance tracking"},
    )
    assert untracked_approved.status_code == 200, untracked_approved.text
    untracked_grant = await business_client.post(
        "/api/v1/attendance/leave-balances/transactions",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "leave_type_id": untracked["id"],
            "period_year": 2026,
            "transaction_type": "grant",
            "amount": "1.00",
            "effective_date": "2026-01-01",
            "reason": "Must remain untracked",
            "idempotency_key": str(uuid4()),
        },
    )
    assert untracked_grant.status_code == 409, untracked_grant.text

    accounts = await business_client.get(
        f"/api/v1/attendance/leave-balances?employment_id={employment.id}&period_year=2026",
        headers=_auth(admin_token),
    )
    assert accounts.status_code == 200, accounts.text
    assert accounts.json()["total"] == 1
    assert accounts.json()["items"][0]["leave_type_id"] == tracked["id"]
    assert accounts.json()["items"][0]["current_balance"] == "0.00"


async def test_managed_cross_year_leave_is_rejected_and_permission_is_required(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "991003")
    leave_type = await _leave_type(
        business_client,
        admin_token,
        code="SYN_CROSS_YEAR",
        balance_mode="tracked",
    )
    leave = await _leave_request(
        business_client,
        admin_token,
        employment_id=employment.id,
        leave_type_id=leave_type["id"],
        start_date="2026-12-31",
        end_date="2027-01-01",
        amount="2.00",
    )
    rejected = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{leave['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Cross-year request"},
    )
    assert rejected.status_code == 422, rejected.text

    denied = await business_client.get(
        "/api/v1/attendance/leave-balances",
        headers=_auth(restricted_token),
    )
    assert denied.status_code == 403, denied.text

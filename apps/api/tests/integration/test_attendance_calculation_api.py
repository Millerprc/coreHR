from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_attendance_daily_monthly_and_leave_cancellation_are_versioned(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    work_date = date(2026, 8, 10)
    leave_date = work_date + timedelta(days=1)
    person = Person(
        employee_number="990005",
        legal_name="Synthetic attendance person",
        display_name="Synthetic attendance person",
        status="active",
    )
    db_session.add(person)
    await db_session.flush()
    employment = Employment(
        person_id=person.id,
        employee_type_code="REGULAR",
        status="active",
        planned_start_date=work_date - timedelta(days=30),
        actual_start_date=work_date - timedelta(days=30),
        version=1,
    )
    db_session.add(employment)
    await db_session.flush()

    rule = await business_client.post(
        "/api/v1/attendance/rule-sets",
        headers=_auth(admin_token),
        json={
            "code": "SYNTHETIC_STANDARD",
            "name": "Synthetic standard attendance",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
            "rules": {"late_grace_minutes": 5, "early_leave_grace_minutes": 5},
        },
    )
    assert rule.status_code == 201, rule.text
    published = await business_client.post(
        f"/api/v1/attendance/rule-sets/{rule.json()['id']}/publish",
        headers=_auth(admin_token),
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "active"

    shift = await business_client.post(
        "/api/v1/attendance/shifts",
        headers=_auth(admin_token),
        json={
            "code": "SYN-DAY",
            "name": "Synthetic day shift",
            "start_time": time(9, 0).isoformat(),
            "end_time": time(18, 0).isoformat(),
            "crosses_midnight": False,
            "rule_set_id": rule.json()["id"],
        },
    )
    assert shift.status_code == 201, shift.text
    for scheduled_date in (work_date, leave_date):
        schedule = await business_client.post(
            "/api/v1/attendance/schedules",
            headers=_auth(admin_token),
            json={
                "employment_id": str(employment.id),
                "work_date": scheduled_date.isoformat(),
                "shift_id": shift.json()["id"],
                "source": "synthetic",
            },
        )
        assert schedule.status_code == 201, schedule.text

    timezone = ZoneInfo("Asia/Shanghai")
    for punch_type, punched_at in (
        ("in", datetime.combine(work_date, time(9, 10), tzinfo=timezone)),
        ("out", datetime.combine(work_date, time(17, 50), tzinfo=timezone)),
    ):
        punch = await business_client.post(
            "/api/v1/attendance/punches",
            headers=_auth(admin_token),
            json={
                "employment_id": str(employment.id),
                "punched_at": punched_at.isoformat(),
                "punch_type": punch_type,
                "source": "synthetic",
                "source_record_id": f"{work_date}-{punch_type}",
            },
        )
        assert punch.status_code == 201, punch.text

    daily_payload = {
        "employment_id": str(employment.id),
        "work_date": work_date.isoformat(),
        "reason": "Synthetic daily calculation",
    }
    first_daily = await business_client.post(
        "/api/v1/attendance/daily-results/calculate",
        headers=_auth(admin_token),
        json=daily_payload,
    )
    assert first_daily.status_code == 201, first_daily.text
    assert first_daily.json()["scheduled_minutes"] == 540
    assert first_daily.json()["worked_minutes"] == 520
    assert first_daily.json()["late_minutes"] == 5
    assert first_daily.json()["early_leave_minutes"] == 5
    assert set(first_daily.json()["exception_codes"]) == {"LATE", "EARLY_LEAVE"}
    second_daily = await business_client.post(
        "/api/v1/attendance/daily-results/calculate",
        headers=_auth(admin_token),
        json={**daily_payload, "reason": "Synthetic correction"},
    )
    assert second_daily.status_code == 201
    assert second_daily.json()["version"] == 2
    all_versions = await business_client.get(
        f"/api/v1/attendance/daily-results?employment_id={employment.id}&current_only=false",
        headers=_auth(admin_token),
    )
    assert all_versions.status_code == 200
    assert all_versions.json()["total"] == 2
    assert sum(1 for item in all_versions.json()["items"] if item["is_current"]) == 1

    leave_type = await business_client.post(
        "/api/v1/attendance/leave-types",
        headers=_auth(admin_token),
        json={"code": "SYN_ANNUAL", "name": "Synthetic annual leave", "unit": "day"},
    )
    assert leave_type.status_code == 201, leave_type.text
    leave = await business_client.post(
        "/api/v1/attendance/leave-requests",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "leave_type_id": leave_type.json()["id"],
            "start_date": leave_date.isoformat(),
            "end_date": leave_date.isoformat(),
            "amount": "1.00",
            "reason": "Synthetic leave",
        },
    )
    assert leave.status_code == 201, leave.text
    approved = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{leave.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Synthetic admin approval"},
    )
    assert approved.status_code == 200, approved.text
    leave_daily = await business_client.post(
        "/api/v1/attendance/daily-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "work_date": leave_date.isoformat(),
            "reason": "Synthetic leave calculation",
        },
    )
    assert leave_daily.status_code == 201, leave_daily.text
    assert leave_daily.json()["status"] == "leave"

    monthly = await business_client.post(
        "/api/v1/attendance/monthly-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "period_month": "2026-08-01",
            "reason": "Synthetic monthly calculation",
        },
    )
    assert monthly.status_code == 201, monthly.text
    assert Decimal(monthly.json()["scheduled_days"]) == Decimal("2")
    assert Decimal(monthly.json()["worked_days"]) == Decimal("1")
    assert Decimal(monthly.json()["leave_days"]) == Decimal("1")
    assert monthly.json()["late_minutes"] == 5

    cancellation = await business_client.post(
        f"/api/v1/attendance/leave-requests/{leave.json()['id']}/cancel",
        headers=_auth(admin_token),
        json={"reason": "Synthetic leave cancellation"},
    )
    assert cancellation.status_code == 201, cancellation.text
    cancellation_approved = await business_client.patch(
        f"/api/v1/attendance/leave-requests/{cancellation.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "change_reason": "Synthetic cancellation approval"},
    )
    assert cancellation_approved.status_code == 200, cancellation_approved.text
    leave_after = await business_client.get(
        f"/api/v1/attendance/leave-requests?employment_id={employment.id}",
        headers=_auth(admin_token),
    )
    assert {item["status"] for item in leave_after.json()["items"]} == {"approved", "cancelled"}

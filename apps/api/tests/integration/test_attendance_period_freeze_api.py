from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.attendance.models import AttendancePunch
from hris.modules.workforce.models import AuditLog, Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _employment(db_session: AsyncSession) -> Employment:
    person = Person(
        employee_number="990006",
        legal_name="Synthetic frozen-period person",
        display_name="Synthetic frozen-period person",
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


async def test_period_freeze_blocks_result_recalculation_but_keeps_raw_evidence(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session)
    created = await business_client.post(
        "/api/v1/attendance/period-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": "monthly",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "reason": "Synthetic August month close",
        },
    )
    assert created.status_code == 201, created.text
    freeze = created.json()
    assert freeze["status"] == "active"
    assert freeze["freeze_type"] == "monthly"
    assert freeze["released_at"] is None

    listed = await business_client.get(
        "/api/v1/attendance/period-freezes?status=active",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == freeze["id"]

    punch = await business_client.post(
        "/api/v1/attendance/punches",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "punched_at": datetime(2026, 8, 10, 9, 0, tzinfo=UTC).isoformat(),
            "punch_type": "in",
            "source": "synthetic",
            "source_record_id": "frozen-period-punch",
        },
    )
    assert punch.status_code == 201, punch.text
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 1

    daily = await business_client.post(
        "/api/v1/attendance/daily-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "work_date": "2026-08-10",
            "reason": "Synthetic recalculation while frozen",
        },
    )
    assert daily.status_code == 409, daily.text
    assert daily.json()["code"] == "ATTENDANCE_PERIOD_FROZEN"
    assert daily.json()["details"] == [
        {
            "freeze_id": freeze["id"],
            "freeze_type": "monthly",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }
    ]

    monthly = await business_client.post(
        "/api/v1/attendance/monthly-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "period_month": "2026-08-01",
            "reason": "Synthetic monthly recalculation while frozen",
        },
    )
    assert monthly.status_code == 409, monthly.text
    assert monthly.json()["code"] == "ATTENDANCE_PERIOD_FROZEN"

    released = await business_client.post(
        f"/api/v1/attendance/period-freezes/{freeze['id']}/release",
        headers=_auth(admin_token),
        json={"reason": "Synthetic approved correction window"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "released"
    assert released.json()["release_reason"] == "Synthetic approved correction window"

    after_release = await business_client.post(
        "/api/v1/attendance/daily-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "work_date": "2026-08-10",
            "reason": "Synthetic approved correction",
        },
    )
    assert after_release.status_code == 201, after_release.text

    audit_actions = set(
        (
            await db_session.scalars(
                select(AuditLog.action).where(
                    AuditLog.object_id == UUID(freeze["id"]),
                )
            )
        ).all()
    )
    assert audit_actions == {
        "attendance.period_freeze.create",
        "attendance.period_freeze.release",
    }


async def test_special_freeze_blocks_overlapping_month_and_monthly_shape_is_validated(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session)
    invalid_month = await business_client.post(
        "/api/v1/attendance/period-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": "monthly",
            "date_from": "2026-08-02",
            "date_to": "2026-08-31",
            "reason": "Synthetic invalid month",
        },
    )
    assert invalid_month.status_code == 422, invalid_month.text

    special = await business_client.post(
        "/api/v1/attendance/period-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": "special",
            "date_from": "2026-08-15",
            "date_to": "2026-08-20",
            "reason": "Synthetic special business freeze",
        },
    )
    assert special.status_code == 201, special.text

    monthly = await business_client.post(
        "/api/v1/attendance/monthly-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "period_month": "2026-08-01",
            "reason": "Synthetic overlapping month",
        },
    )
    assert monthly.status_code == 409, monthly.text
    assert monthly.json()["details"][0]["freeze_type"] == "special"


async def test_period_freezes_require_attendance_admin_permission(
    business_client: AsyncClient,
    restricted_token: str,
) -> None:
    response = await business_client.get(
        "/api/v1/attendance/period-freezes",
        headers=_auth(restricted_token),
    )
    assert response.status_code == 403, response.text

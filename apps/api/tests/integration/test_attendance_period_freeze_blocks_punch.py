# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.config import get_settings
from hris.modules.attendance.models import AttendancePunch
from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _business_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().business_timezone)


async def _employment(db_session: AsyncSession, employee_number: str) -> Employment:
    person = Person(
        employee_number=employee_number,
        legal_name="Synthetic freeze blocked punch person",
        display_name="Synthetic freeze blocked punch person",
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


async def _create_freeze(
    business_client: AsyncClient,
    admin_token: str,
    *,
    date_from: str,
    date_to: str,
    reason: str,
    freeze_type: str = "monthly",
) -> dict:
    response = await business_client.post(
        "/api/v1/attendance/period-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": freeze_type,
            "date_from": date_from,
            "date_to": date_to,
            "reason": reason,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _post_punch(
    business_client: AsyncClient,
    admin_token: str,
    *,
    employment_id: object,
    punched_at: datetime,
    source_record_id: str,
    source: str = "synthetic-freeze",
):
    return await business_client.post(
        "/api/v1/attendance/punches",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment_id),
            "punched_at": punched_at.isoformat(),
            "punch_type": "in",
            "source": source,
            "source_record_id": source_record_id,
        },
    )


async def test_punch_inside_frozen_period_is_rejected_and_writes_nothing(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "990011")
    freeze = await _create_freeze(
        business_client,
        admin_token,
        date_from="2026-08-01",
        date_to="2026-08-31",
        reason="Synthetic August month close",
    )

    punch = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        source_record_id="frozen-period-punch",
    )
    assert punch.status_code == 409, punch.text
    body = punch.json()
    assert body["code"] == "ATTENDANCE_PERIOD_FROZEN"
    assert body["details"] == [
        {
            "freeze_id": freeze["id"],
            "freeze_type": "monthly",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        }
    ]
    # 消息要说明被冻结的区间与"不允许补卡"，且不得包含任何个人信息。
    assert "2026-08-01" in body["message"]
    assert "2026-08-31" in body["message"]
    assert "不允许补录打卡" in body["message"]
    assert "990011" not in body["message"]
    assert "Synthetic freeze blocked punch person" not in body["message"]
    # 失败不留半写状态：库里没有新增打卡记录。
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 0


async def test_punch_outside_frozen_period_is_accepted(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "990012")
    await _create_freeze(
        business_client,
        admin_token,
        date_from="2026-08-01",
        date_to="2026-08-31",
        reason="Synthetic August month close",
    )

    punch = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
        source_record_id="outside-frozen-period-punch",
    )
    assert punch.status_code == 201, punch.text
    assert punch.json()["duplicate"] is False
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 1


async def test_punch_is_accepted_after_freeze_release(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "990013")
    freeze = await _create_freeze(
        business_client,
        admin_token,
        date_from="2026-08-01",
        date_to="2026-08-31",
        reason="Synthetic August month close",
    )
    released = await business_client.post(
        f"/api/v1/attendance/period-freezes/{freeze['id']}/release",
        headers=_auth(admin_token),
        json={"reason": "Synthetic approved correction window"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "released"

    punch = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        source_record_id="released-period-punch",
    )
    assert punch.status_code == 201, punch.text
    assert punch.json()["duplicate"] is False
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 1


async def test_duplicate_punch_returns_existing_record_even_inside_frozen_period(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "990014")
    punched_at = datetime(2026, 7, 15, 1, 0, tzinfo=UTC)
    first = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=punched_at,
        source_record_id="idempotent-punch",
    )
    assert first.status_code == 201, first.text
    assert first.json()["duplicate"] is False
    record_id = first.json()["record"]["id"]

    await _create_freeze(
        business_client,
        admin_token,
        date_from="2026-07-01",
        date_to="2026-07-31",
        reason="Synthetic July month close",
    )

    # 幂等命中优先：重复提交同一条打卡不产生新的考勤事实，返回既有记录而不是被冻结拦下。
    repeated = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=punched_at,
        source_record_id="idempotent-punch",
    )
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["duplicate"] is True
    assert repeated.json()["record"]["id"] == record_id
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 1


async def test_special_freeze_blocks_punch_by_business_day(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "990015")
    freeze = await _create_freeze(
        business_client,
        admin_token,
        date_from="2026-08-15",
        date_to="2026-08-20",
        reason="Synthetic special business freeze",
        freeze_type="special",
    )

    blocked = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=datetime(2026, 8, 18, 1, 0, tzinfo=UTC),
        source_record_id="special-freeze-punch",
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "ATTENDANCE_PERIOD_FROZEN"
    assert blocked.json()["details"] == [
        {
            "freeze_id": freeze["id"],
            "freeze_type": "special",
            "date_from": "2026-08-15",
            "date_to": "2026-08-20",
        }
    ]
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 0


async def test_punch_business_day_uses_configured_business_timezone(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """冻结判定按业务时区自然日：UTC 跨日的前后两天分别落在冻结区间内外。"""
    employment = await _employment(db_session, "990016")
    await _create_freeze(
        business_client,
        admin_token,
        date_from="2026-08-01",
        date_to="2026-08-31",
        reason="Synthetic August month close",
    )
    timezone = _business_tz()

    # 2026-08-01 00:30 +08:00 == 2026-07-31T16:30Z：业务日属于 8 月，落在冻结区间内。
    inside = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=datetime(2026, 8, 1, 0, 30, tzinfo=timezone),
        source_record_id="business-day-inside",
    )
    assert inside.status_code == 409, inside.text
    assert inside.json()["code"] == "ATTENDANCE_PERIOD_FROZEN"

    # 2026-07-31 23:30 +08:00：业务日属于 7 月，落在冻结区间外。
    outside = await _post_punch(
        business_client,
        admin_token,
        employment_id=employment.id,
        punched_at=datetime(2026, 7, 31, 23, 30, tzinfo=timezone),
        source_record_id="business-day-outside",
    )
    assert outside.status_code == 201, outside.text
    assert await db_session.scalar(select(func.count()).select_from(AttendancePunch)) == 1

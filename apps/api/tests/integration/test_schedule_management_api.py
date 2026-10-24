# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""排班管理（类型 / 轮班周期 / 弹性窗口 / 草稿发布 / 换班 / 批量）与规则集版本绑定的集成测试。

Requirement: D-097 —— 批量排班单次最多 1000 条明细，超限整批拒绝。
Requirement: D-052 —— 批量维护允许部分成功并返回失败明细。
Requirement: D-107 —— 班次绑定不可变的规则集版本行，旧班次不跟随新规则。
"""

from datetime import date, datetime, time
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _employment(
    db_session: AsyncSession,
    employee_number: str,
) -> Employment:
    person = Person(
        employee_number=employee_number,
        legal_name=f"Schedule {employee_number}",
        display_name=f"Schedule {employee_number}",
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


async def _published_rule_set(
    business_client: AsyncClient,
    admin_token: str,
    *,
    code: str,
    late_grace_minutes: int,
) -> dict[str, object]:
    rule = await business_client.post(
        "/api/v1/attendance/rule-sets",
        headers=_auth(admin_token),
        json={
            "code": code,
            "name": f"Synthetic {code}",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
            "rules": {
                "late_grace_minutes": late_grace_minutes,
                "early_leave_grace_minutes": 0,
            },
        },
    )
    assert rule.status_code == 201, rule.text
    published = await business_client.post(
        f"/api/v1/attendance/rule-sets/{rule.json()['id']}/publish",
        headers=_auth(admin_token),
    )
    assert published.status_code == 200, published.text
    return published.json()


async def _shift(
    business_client: AsyncClient,
    admin_token: str,
    *,
    code: str,
    rule_set_id: str,
    start_hour: int = 9,
) -> dict[str, object]:
    response = await business_client.post(
        "/api/v1/attendance/shifts",
        headers=_auth(admin_token),
        json={
            "code": code,
            "name": f"Synthetic {code}",
            "start_time": time(start_hour, 0).isoformat(),
            "end_time": time(18, 0).isoformat(),
            "crosses_midnight": False,
            "rule_set_id": rule_set_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_schedule_types_cycles_and_windows_are_stored(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    schedule_type = await business_client.post(
        "/api/v1/attendance/schedule-types",
        headers=_auth(admin_token),
        json={
            "code": "ROTATING",
            "name": "Synthetic rotating schedule",
            "requires_shift_cycle": True,
            "requires_flexible_window": False,
            "allows_multiple_shifts_per_day": False,
            "requires_publish": True,
        },
    )
    assert schedule_type.status_code == 201, schedule_type.text
    type_id = schedule_type.json()["id"]

    cycle = await business_client.post(
        "/api/v1/attendance/shift-cycles",
        headers=_auth(admin_token),
        json={
            "code": "CYCLE-14",
            "name": "Synthetic 14 day cycle",
            "schedule_type_id": type_id,
            "cycle_start_date": "2026-01-05",
            "cycle_days": 14,
            "shift_sequence": [],
        },
    )
    assert cycle.status_code == 201, cycle.text
    assert cycle.json()["cycle_days"] == 14

    window = await business_client.post(
        "/api/v1/attendance/flexible-windows",
        headers=_auth(admin_token),
        json={
            "code": "FLEX-STD",
            "name": "Synthetic flexible window",
            "schedule_type_id": type_id,
            "arrival_window_start": "08:00:00",
            "arrival_window_end": "10:00:00",
            "departure_window_start": "17:00:00",
            "departure_window_end": "19:00:00",
            "standard_daily_minutes": 480,
        },
    )
    assert window.status_code == 201, window.text

    listed = await business_client.get(
        "/api/v1/attendance/schedule-types",
        headers=_auth(admin_token),
    )
    assert listed.status_code == 200, listed.text
    assert any(item["code"] == "ROTATING" for item in listed.json()["items"])


async def test_batch_schedule_rejects_more_than_1000_lines(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992201")
    rule_set = await _published_rule_set(
        business_client,
        admin_token,
        code="SYN_SCHED_LIMIT",
        late_grace_minutes=0,
    )
    shift = await _shift(
        business_client,
        admin_token,
        code="SYN-LIMIT-SHIFT",
        rule_set_id=str(rule_set["id"]),
    )
    lines = [
        {
            "employment_id": str(employment.id),
            "work_date": f"2026-09-{day:02d}",
            "shift_id": str(shift["id"]),
        }
        for day in range(1, 29)
    ]
    lines = lines * 36  # 1008 条明细
    response = await business_client.post(
        "/api/v1/attendance/schedules/draft",
        headers=_auth(admin_token),
        json={
            "period_code": "2026-09",
            "source": "batch",
            "lines": lines,
        },
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "SCHEDULE_BATCH_LIMIT_EXCEEDED"


async def test_draft_schedules_publish_by_period_and_report_failures(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    employment = await _employment(db_session, "992202")
    rule_set = await _published_rule_set(
        business_client,
        admin_token,
        code="SYN_SCHED_DRAFT",
        late_grace_minutes=0,
    )
    shift = await _shift(
        business_client,
        admin_token,
        code="SYN-DRAFT-SHIFT",
        rule_set_id=str(rule_set["id"]),
    )
    schedule_type = await business_client.post(
        "/api/v1/attendance/schedule-types",
        headers=_auth(admin_token),
        json={"code": "FIXED", "name": "Synthetic fixed schedule"},
    )
    assert schedule_type.status_code == 201, schedule_type.text

    # 先建一条已发布排班，同日再生成草稿应失败并返回失败明细。
    existing = await business_client.post(
        "/api/v1/attendance/schedules",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "work_date": "2026-09-01",
            "shift_id": str(shift["id"]),
            "source": "manual",
        },
    )
    assert existing.status_code == 201, existing.text
    assert existing.json()["publish_status"] == "published"

    draft = await business_client.post(
        "/api/v1/attendance/schedules/draft",
        headers=_auth(admin_token),
        json={
            "period_code": "2026-09",
            "schedule_type_id": schedule_type.json()["id"],
            "source": "batch",
            "lines": [
                {
                    "employment_id": str(employment.id),
                    "work_date": "2026-09-01",
                    "shift_id": str(shift["id"]),
                },
                {
                    "employment_id": str(employment.id),
                    "work_date": "2026-09-02",
                    "shift_id": str(shift["id"]),
                },
            ],
        },
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["created"] == 1
    failures = draft.json()["failed"]
    assert len(failures) == 1
    assert failures[0]["code"] == "SCHEDULE_EXISTS"
    assert failures[0]["work_date"] == "2026-09-01"

    drafts = await business_client.get(
        "/api/v1/attendance/schedules?publish_status=draft",
        headers=_auth(admin_token),
    )
    assert drafts.status_code == 200, drafts.text
    assert drafts.json()["total"] == 1
    assert drafts.json()["items"][0]["work_date"] == "2026-09-02"
    assert drafts.json()["items"][0]["publish_status"] == "draft"

    batch = await business_client.post(
        "/api/v1/attendance/schedule-publish-batches",
        headers=_auth(admin_token),
        json={"period_code": "2026-09"},
    )
    assert batch.status_code == 201, batch.text
    published = await business_client.post(
        f"/api/v1/attendance/schedule-publish-batches/{batch.json()['id']}/publish",
        headers=_auth(admin_token),
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["published_count"] == 1

    after_publish = await business_client.get(
        "/api/v1/attendance/schedules?publish_status=published",
        headers=_auth(admin_token),
    )
    assert after_publish.json()["total"] == 2
    published_row = next(
        item
        for item in after_publish.json()["items"]
        if item["work_date"] == "2026-09-02"
    )
    assert published_row["batch_id"] == batch.json()["id"]


async def test_swap_record_swaps_shifts_when_approved(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    first = await _employment(db_session, "992203")
    second = await _employment(db_session, "992204")
    rule_set = await _published_rule_set(
        business_client,
        admin_token,
        code="SYN_SCHED_SWAP",
        late_grace_minutes=0,
    )
    day_shift = await _shift(
        business_client,
        admin_token,
        code="SYN-SWAP-DAY",
        rule_set_id=str(rule_set["id"]),
    )
    night_shift = await _shift(
        business_client,
        admin_token,
        code="SYN-SWAP-NIGHT",
        rule_set_id=str(rule_set["id"]),
        start_hour=14,
    )
    for employment, shift in ((first, day_shift), (second, night_shift)):
        response = await business_client.post(
            "/api/v1/attendance/schedules",
            headers=_auth(admin_token),
            json={
                "employment_id": str(employment.id),
                "work_date": "2026-09-10",
                "shift_id": str(shift["id"]),
                "source": "manual",
            },
        )
        assert response.status_code == 201, response.text

    swap = await business_client.post(
        "/api/v1/attendance/schedule-swaps",
        headers=_auth(admin_token),
        json={
            "employment_id_a": str(first.id),
            "employment_id_b": str(second.id),
            "work_date": "2026-09-10",
            "original_shift_id": str(day_shift["id"]),
            "new_shift_id": str(night_shift["id"]),
            "remark": "Synthetic swap",
        },
    )
    assert swap.status_code == 201, swap.text
    assert swap.json()["status"] == "draft"
    assert swap.json()["request_number"].startswith("SW")

    approved = await business_client.patch(
        f"/api/v1/attendance/schedule-swaps/{swap.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "approved", "remark": "Synthetic approval"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["effective_at"] is not None

    schedules = await business_client.get(
        f"/api/v1/attendance/schedules?date_from=2026-09-10&date_to=2026-09-10",
        headers=_auth(admin_token),
    )
    rows = {item["employment_id"]: item["shift_id"] for item in schedules.json()["items"]}
    assert rows[str(first.id)] == str(night_shift["id"])
    assert rows[str(second.id)] == str(day_shift["id"])

    decided_again = await business_client.patch(
        f"/api/v1/attendance/schedule-swaps/{swap.json()['id']}",
        headers=_auth(admin_token),
        json={"status": "rejected"},
    )
    assert decided_again.status_code == 409, decided_again.text


async def test_shift_binds_immutable_rule_set_version(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """规则集发布新版本后，旧班次仍按旧版本计算（不静默跟随新规则）。"""
    employment = await _employment(db_session, "992205")
    work_date = date(2026, 9, 20)
    rule_set = await _published_rule_set(
        business_client,
        admin_token,
        code="SYN_SCHED_VERSION",
        late_grace_minutes=0,
    )
    shift = await _shift(
        business_client,
        admin_token,
        code="SYN-VERSION-SHIFT",
        rule_set_id=str(rule_set["id"]),
    )
    assert shift["rule_set_version"] == 1
    assert shift["rule_snapshot"]["version"] == 1

    # 发布新版本：宽限 60 分钟。
    new_version = await business_client.post(
        f"/api/v1/attendance/rule-sets/{rule_set['id']}/versions",
        headers=_auth(admin_token),
        json={
            "name": "Synthetic standard attendance v2",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-09-01",
            "rules": {"late_grace_minutes": 60, "early_leave_grace_minutes": 0},
        },
    )
    assert new_version.status_code == 201, new_version.text
    assert new_version.json()["version"] == 2
    published = await business_client.post(
        f"/api/v1/attendance/rule-sets/{new_version.json()['id']}/publish",
        headers=_auth(admin_token),
    )
    assert published.status_code == 200, published.text

    schedule = await business_client.post(
        "/api/v1/attendance/schedules",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "work_date": work_date.isoformat(),
            "shift_id": str(shift["id"]),
            "source": "manual",
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
                "source_record_id": f"{work_date}-{punch_type}-version",
            },
        )
        assert punch.status_code == 201, punch.text

    daily = await business_client.post(
        "/api/v1/attendance/daily-results/calculate",
        headers=_auth(admin_token),
        json={
            "employment_id": str(employment.id),
            "work_date": work_date.isoformat(),
            "reason": "Synthetic version binding check",
        },
    )
    assert daily.status_code == 201, daily.text
    # 旧班次绑定 v1（宽限 0 分钟）：迟到 10 分钟。
    assert daily.json()["late_minutes"] == 10
    assert daily.json()["evidence"]["rule_set_version"] == 1

    # 未发布的规则集版本不能被新班次引用。
    draft_rule = await business_client.post(
        "/api/v1/attendance/rule-sets",
        headers=_auth(admin_token),
        json={
            "code": "SYN_SCHED_DRAFT_ONLY",
            "name": "Synthetic draft only rule",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
            "rules": {"late_grace_minutes": 0},
        },
    )
    assert draft_rule.status_code == 201, draft_rule.text
    rejected_shift = await business_client.post(
        "/api/v1/attendance/shifts",
        headers=_auth(admin_token),
        json={
            "code": "SYN-DRAFT-RULE-SHIFT",
            "name": "Synthetic draft rule shift",
            "start_time": time(9, 0).isoformat(),
            "end_time": time(18, 0).isoformat(),
            "crosses_midnight": False,
            "rule_set_id": draft_rule.json()["id"],
        },
    )
    assert rejected_shift.status_code == 409, rejected_shift.text
    assert rejected_shift.json()["code"] == "SHIFT_RULE_SET_NOT_PUBLISHED"


async def test_shift_requires_existing_rule_set(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.post(
        "/api/v1/attendance/shifts",
        headers=_auth(admin_token),
        json={
            "code": "SYN-MISSING-RULE-SHIFT",
            "name": "Synthetic missing rule shift",
            "start_time": time(9, 0).isoformat(),
            "end_time": time(18, 0).isoformat(),
            "crosses_midnight": False,
            "rule_set_id": str(uuid4()),
        },
    )
    assert response.status_code == 404, response.text

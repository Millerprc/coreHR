# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""批量考勤计算（日报 / 月报）集成测试。

Requirement: D-116 — 逐人提交在 200 人规模下不可用（要点 200 次），
批量计算因此走后台任务，覆盖范围三态（全员 / 指定人员 / 排除人员）。

本文件覆盖：
- 提交端点：入队语义、请求体校验、账期冻结预检、权限区分、人员存在性校验；
- 执行端点：范围解析、单人失败不牵连他人、结果统计；
- 任务租约：长任务必须续租，否则会被回收并重复执行。
"""

from contextlib import asynccontextmanager
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.attendance.extended_service import ExtendedAttendanceService
from hris.modules.attendance.models import AttendanceDailyResult, AttendanceMonthlyResult
from hris.modules.platform import task_worker
from hris.modules.platform.task_handlers import execute_task
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.platform.task_queue import TaskQueue
from hris.modules.workforce.models import Employment, Person


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_employment(
    db_session: AsyncSession,
    employee_number: str,
    display_name: str,
) -> Employment:
    person = Person(
        employee_number=employee_number,
        legal_name=display_name,
        display_name=display_name,
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


async def _run_worker_once(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def _fake_session_factory():
        yield db_session

    monkeypatch.setattr(task_worker, "session_factory", _fake_session_factory)
    await task_worker.run_worker(once=True, worker_id="worker-attendance-calc")


async def _submit(
    client: AsyncClient,
    token: str,
    *,
    kind: str = "daily",
    scope: str = "all",
    employment_ids: list[str] | None = None,
    work_date: str = "2026-08-10",
    period_month: str = "2026-08-01",
    reason: str = "合成批量计算",
) -> Response:
    body: dict[str, object] = {
        "kind": kind,
        "scope": scope,
        "employment_ids": employment_ids or [],
        "reason": reason,
    }
    if kind == "daily":
        body["work_date"] = work_date
    else:
        body["period_month"] = period_month
    return await client.post(
        "/api/v1/attendance/calculation-tasks",
        headers=_auth(token),
        json=body,
    )


# ---------------------------------------------------------------------------
# 提交端点
# ---------------------------------------------------------------------------


async def test_submit_creates_a_pending_background_task(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """默认范围是全员：提交后落一条 pending 的后台任务，载荷里没有人 id。"""

    response = await _submit(business_client, admin_token)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["task_type"] == "attendance.calculate"
    assert body["status"] == "pending"

    task = await db_session.get(BackgroundTask, UUID(body["id"]))
    assert task is not None
    assert task.payload["kind"] == "daily"
    assert task.payload["scope"] == "all"
    assert task.payload["employment_ids"] == []
    assert task.payload["reason"] == "合成批量计算"


async def test_submit_rejects_unknown_employment_in_selected_scope(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """指定人员里混进不存在的 id 时，提交阶段就拒绝，不让管理员白等一次任务。"""

    response = await _submit(
        business_client,
        admin_token,
        scope="selected",
        employment_ids=[str(uuid4())],
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "ATTENDANCE_CALCULATION_TARGET_INVALID"


async def test_submit_rejects_a_frozen_period_before_queuing(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
) -> None:
    """冻结的账期在提交时就该被拒（409），而不是让任务跑起来再失败。"""

    created = await business_client.post(
        "/api/v1/attendance/period-freezes",
        headers=_auth(admin_token),
        json={
            "freeze_type": "monthly",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
            "reason": "合成月结冻结",
        },
    )
    assert created.status_code == 201, created.text

    response = await _submit(business_client, admin_token, work_date="2026-08-10")
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "ATTENDANCE_PERIOD_FROZEN"

    # 没有任务被入队。
    count = await db_session.scalar(
        select(func.count())
        .select_from(BackgroundTask)
        .where(BackgroundTask.task_type == "attendance.calculate")
    )
    assert count == 0


async def test_submit_requires_the_matching_recalc_permission(
    business_client: AsyncClient,
    restricted_token: str,
) -> None:
    """没有重算权限的人不能发起批量计算。"""

    response = await _submit(business_client, restricted_token)
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_submit_rejects_a_malformed_request(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    """范围与人员列表不自洽时直接拒绝，不静默忽略。"""

    response = await business_client.post(
        "/api/v1/attendance/calculation-tasks",
        headers=_auth(admin_token),
        json={
            "kind": "daily",
            "scope": "all",
            "employment_ids": [str(uuid4())],
            "work_date": "2026-08-10",
            "reason": "口径冲突",
        },
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# 执行端点
# ---------------------------------------------------------------------------


async def test_batch_daily_calculation_covers_everyone_by_default(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """默认全员：一次提交给所有人各生成一条日报。"""

    first = await _make_employment(db_session, "993301", "合成批量甲")
    second = await _make_employment(db_session, "993302", "合成批量乙")

    response = await _submit(business_client, admin_token, work_date="2026-08-10")
    assert response.status_code == 202, response.text

    await _run_worker_once(db_session, monkeypatch)

    task = await db_session.get(
        BackgroundTask, UUID(response.json()["id"]), populate_existing=True
    )
    assert task.status == "succeeded", task.error_code
    assert task.result is not None
    assert task.result["scope"] == "all"
    assert task.result["target_count"] == 2
    assert task.result["succeeded_count"] == 2
    assert task.result["failed_count"] == 0

    generated = list(
        (
            await db_session.scalars(
                select(AttendanceDailyResult).where(
                    AttendanceDailyResult.work_date == date(2026, 8, 10)
                )
            )
        ).all()
    )
    assert {item.employment_id for item in generated} == {first.id, second.id}


async def test_selected_scope_calculates_only_the_chosen_people(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """指定人员：只算选中的人，没选的不算。"""

    chosen = await _make_employment(db_session, "993311", "合成指定甲")
    skipped = await _make_employment(db_session, "993312", "合成指定乙")

    response = await _submit(
        business_client,
        admin_token,
        scope="selected",
        employment_ids=[str(chosen.id)],
        work_date="2026-08-11",
    )
    assert response.status_code == 202, response.text

    await _run_worker_once(db_session, monkeypatch)

    task = await db_session.get(
        BackgroundTask, UUID(response.json()["id"]), populate_existing=True
    )
    assert task.status == "succeeded", task.error_code
    assert task.result is not None
    assert task.result["target_count"] == 1
    assert task.result["succeeded_count"] == 1

    generated = list(
        (
            await db_session.scalars(
                select(AttendanceDailyResult).where(
                    AttendanceDailyResult.work_date == date(2026, 8, 11)
                )
            )
        ).all()
    )
    assert {item.employment_id for item in generated} == {chosen.id}
    assert skipped.id not in {item.employment_id for item in generated}


async def test_excluded_scope_calculates_everyone_but_the_excluded(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """排除人员：全员都算，但排除掉选中的人（200 人规模下的常用操作）。"""

    kept = await _make_employment(db_session, "993321", "合成保留甲")
    excluded = await _make_employment(db_session, "993322", "合成排除乙")

    response = await _submit(
        business_client,
        admin_token,
        scope="excluded",
        employment_ids=[str(excluded.id)],
        work_date="2026-08-12",
    )
    assert response.status_code == 202, response.text

    await _run_worker_once(db_session, monkeypatch)

    task = await db_session.get(
        BackgroundTask, UUID(response.json()["id"]), populate_existing=True
    )
    assert task.status == "succeeded", task.error_code
    assert task.result is not None
    assert task.result["scope"] == "excluded"
    assert task.result["target_count"] == 1
    assert task.result["succeeded_count"] == 1

    generated = list(
        (
            await db_session.scalars(
                select(AttendanceDailyResult).where(
                    AttendanceDailyResult.work_date == date(2026, 8, 12)
                )
            )
        ).all()
    )
    assert {item.employment_id for item in generated} == {kept.id}
    assert excluded.id not in {item.employment_id for item in generated}


async def test_batch_monthly_calculation_produces_monthly_results(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """月报批量：一次提交给每个人各生成一条月报。"""

    first = await _make_employment(db_session, "993331", "合成月报甲")
    second = await _make_employment(db_session, "993332", "合成月报乙")

    response = await _submit(
        business_client,
        admin_token,
        kind="monthly",
        period_month="2026-07-01",
    )
    assert response.status_code == 202, response.text

    await _run_worker_once(db_session, monkeypatch)

    task = await db_session.get(
        BackgroundTask, UUID(response.json()["id"]), populate_existing=True
    )
    assert task.status == "succeeded", task.error_code
    assert task.result is not None
    assert task.result["kind"] == "monthly"
    assert task.result["target_count"] == 2
    assert task.result["succeeded_count"] == 2

    generated = list(
        (
            await db_session.scalars(
                select(AttendanceMonthlyResult).where(
                    AttendanceMonthlyResult.period_month == date(2026, 7, 1)
                )
            )
        ).all()
    )
    assert {item.employment_id for item in generated} == {first.id, second.id}


async def test_one_failing_person_does_not_stop_the_others(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单个人的失败不牵连其他人：失败的人被计数，其余人的结果照常落库。"""

    good = await _make_employment(db_session, "993341", "合成成功甲")
    bad = await _make_employment(db_session, "993342", "合成失败乙")

    original = ExtendedAttendanceService.calculate_daily

    async def failing(self, payload):  # type: ignore[no-untyped-def]
        if payload.employment_id == bad.id:
            raise ApiError(
                status_code=422,
                code="RULE_SET_NOT_FOUND",
                message="合成失败",
            )
        return await original(self, payload)

    monkeypatch.setattr(ExtendedAttendanceService, "calculate_daily", failing)

    response = await _submit(business_client, admin_token, work_date="2026-08-13")
    assert response.status_code == 202, response.text

    await _run_worker_once(db_session, monkeypatch)

    task = await db_session.get(
        BackgroundTask, UUID(response.json()["id"]), populate_existing=True
    )
    assert task.status == "succeeded", task.error_code
    assert task.result is not None
    assert task.result["target_count"] == 2
    assert task.result["succeeded_count"] == 1
    assert task.result["failed_count"] == 1
    assert task.result["failure_codes"] == {"RULE_SET_NOT_FOUND": 1}

    generated = list(
        (
            await db_session.scalars(
                select(AttendanceDailyResult).where(
                    AttendanceDailyResult.work_date == date(2026, 8, 13)
                )
            )
        ).all()
    )
    assert {item.employment_id for item in generated} == {good.id}


async def test_task_detail_is_visible_to_the_submitter(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """发起人能看到任务状态与结果统计。"""

    await _make_employment(db_session, "993351", "合成可见甲")
    response = await _submit(business_client, admin_token, work_date="2026-08-14")
    assert response.status_code == 202, response.text
    task_id = response.json()["id"]

    pending = await business_client.get(
        f"/api/v1/attendance/calculation-tasks/{task_id}",
        headers=_auth(admin_token),
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["status"] == "pending"
    assert pending.json()["result"] is None

    await _run_worker_once(db_session, monkeypatch)

    done = await business_client.get(
        f"/api/v1/attendance/calculation-tasks/{task_id}",
        headers=_auth(admin_token),
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "succeeded"
    assert done.json()["result"]["succeeded_count"] == 1


async def test_unknown_task_is_not_found(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.get(
        f"/api/v1/attendance/calculation-tasks/{uuid4()}",
        headers=_auth(admin_token),
    )
    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# 租约续租
# ---------------------------------------------------------------------------


async def test_renew_lease_extends_the_running_task(
    db_session: AsyncSession,
) -> None:
    """长任务必须能续租：领取租约默认 60 秒，批量计算要跑好几分钟。"""

    queue = TaskQueue(db_session, worker_id="worker-lease-1")
    task = await queue.enqueue("test.lease.renew", {"case": "renew"})
    claimed = await queue.claim(limit=10, lease_seconds=60)
    assert len(claimed) == 1
    first_expiry = task.lease_expires_at
    assert first_expiry is not None

    renewed = await queue.renew_lease(
        task.id,
        expected_owner="worker-lease-1",
        lease_seconds=600,
    )
    assert renewed.lease_expires_at is not None
    assert renewed.lease_expires_at > first_expiry


async def test_renew_lease_rejects_a_mismatched_owner(
    db_session: AsyncSession,
) -> None:
    """租约已经被别人抢走时不能续租 —— 否则两个 Worker 会同时在写同一批结果。"""

    queue = TaskQueue(db_session, worker_id="worker-lease-2")
    task = await queue.enqueue("test.lease.owner", {"case": "owner"})
    await queue.claim(limit=10, lease_seconds=60)

    with pytest.raises(ValueError):
        await queue.renew_lease(task.id, expected_owner="worker-lease-other")


async def test_renew_lease_rejects_a_task_that_is_not_running(
    db_session: AsyncSession,
) -> None:
    queue = TaskQueue(db_session, worker_id="worker-lease-3")
    task = await queue.enqueue("test.lease.pending", {"case": "pending"})

    with pytest.raises(ValueError):
        await queue.renew_lease(task.id, expected_owner="worker-lease-3")

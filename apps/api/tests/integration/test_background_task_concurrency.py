# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""后台任务并发与事务边界回归测试。

Requirement: D-121 — 覆盖审计提出的三个问题：

1. Worker 整批共用一次提交 → 改成**每条任务一个独立事务**；
2. 人工重试「先读后写」→ 改成**原子条件更新**；
3. 重复提交标识跨批次复用 → 改成**冲突（409）**。

这些用例刻意用**真实连接**（``test_engine``）而不是共享会话：
共享会话的写入没有真正提交，别的连接看不见，
「领取状态是否立即可见」「尝试次数是否被回滚」这类断言就测不出来。
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform import task_worker
from hris.modules.platform.models import UserAccount
from hris.modules.platform.task_api import retry_background_task
from hris.modules.platform.task_handlers import TASK_HANDLERS
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.platform.task_queue import TaskQueue


pytestmark = pytest.mark.asyncio


TASK_TYPE_VISIBLE = "test.d121.visible"
TASK_TYPE_OK = "test.d121.ok"
TASK_TYPE_CRASH = "test.d121.crash"
TASK_TYPE_RETRY = "test.d121.retry"
TASK_TYPE_EXHAUSTED = "test.d121.exhausted"

_ALL_TEST_TYPES = (
    TASK_TYPE_VISIBLE,
    TASK_TYPE_OK,
    TASK_TYPE_CRASH,
    TASK_TYPE_RETRY,
    TASK_TYPE_EXHAUSTED,
)


class _SimulatedCrash(BaseException):
    """模拟进程被杀。

    刻意不继承 ``Exception``：``execute_task`` 只捕获 ``Exception``，
    真正的进程崩溃（SIGKILL / OOM / 断电）也走不到那里，
    只能靠事务回滚 + 租约回收来兜。
    """


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _session(test_engine: AsyncEngine) -> AsyncSession:
    """与会话工厂配置一致的会话。

    生产用的 ``session_factory`` 是 ``expire_on_commit=False``；
    测试里如果用默认的 ``True``，提交后 ORM 属性会被过期，
    再访问就会变成异步上下文里的非法懒加载（MissingGreenlet）——
    那测的就不是生产行为了。
    """

    return AsyncSession(test_engine, expire_on_commit=False)


def _probe_user() -> UserAccount:
    """重试端点的权限由依赖注入把关，函数体本身不读 user —— 这里只需要一个占位对象。"""

    return UserAccount(
        username="probe-retry",
        display_name="Probe Retry",
        password_hash="not-used",
        status="active",
        failed_attempts=0,
    )


async def _cleanup(test_engine: AsyncEngine) -> None:
    async with _session(test_engine) as session:
        await session.execute(
            delete(BackgroundTask).where(BackgroundTask.task_type.in_(_ALL_TEST_TYPES))
        )
        await session.commit()


def _use_real_sessions(test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    """让 Worker 用真实会话跑：提交是真的提交，别的连接看得见。"""

    monkeypatch.setattr(
        task_worker,
        "session_factory",
        lambda: _session(test_engine),
    )


# ---------------------------------------------------------------------------
# 问题 1：Worker 整批共用一次提交
# ---------------------------------------------------------------------------


async def test_claim_state_is_committed_before_the_task_starts_running(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """领取状态必须**先提交**再执行：执行期间别的连接就能看到 running 与尝试次数。

    早先的实现里领取与执行在同一个事务，页面在整个批次跑完前看到的都是「等待中」。
    """

    started = asyncio.Event()
    release = asyncio.Event()
    observed: dict[str, object] = {}

    async def probe_handler(db: AsyncSession, task: BackgroundTask) -> dict[str, int]:
        async with _session(test_engine) as probe:
            row = await probe.get(BackgroundTask, task.id)
            observed["status"] = row.status
            observed["attempts"] = row.attempts
        started.set()
        await release.wait()
        return {"ok": 1}

    monkeypatch.setitem(TASK_HANDLERS, TASK_TYPE_VISIBLE, probe_handler)
    _use_real_sessions(test_engine, monkeypatch)

    try:
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(TASK_TYPE_VISIBLE, {"case": "visible"})
            task_id = task.id
            await seed.commit()

        worker = asyncio.create_task(
            task_worker.run_worker(once=True, worker_id="worker-visible")
        )
        await asyncio.wait_for(started.wait(), timeout=60)

        # 执行期间：另一条连接已经能看到 running，且尝试次数已落库。
        assert observed["status"] == "running"
        assert observed["attempts"] == 1

        release.set()
        await asyncio.wait_for(worker, timeout=60)

        async with _session(test_engine) as check:
            row = await check.get(BackgroundTask, task_id)
            assert row.status == "succeeded"
            assert row.result == {"ok": 1}
    finally:
        release.set()
        await _cleanup(test_engine)


async def test_a_crash_in_a_later_task_does_not_roll_back_an_earlier_one(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """后面任务崩溃**不能回滚**前面已经执行完的任务，也不能回滚尝试次数。

    早先的实现整批共用一次提交：一条任务崩溃，整批回滚，
    前面算好的考勤结果连同任务状态一起消失，尝试次数也被抹掉
    （反复崩溃的任务永远攒不够次数，「最多重试 N 次」形同虚设）。
    """

    async def ok_handler(db: AsyncSession, task: BackgroundTask) -> dict[str, int]:
        return {"ok": 1}

    async def crash_handler(db: AsyncSession, task: BackgroundTask) -> dict[str, int]:
        raise _SimulatedCrash("模拟进程被杀")

    monkeypatch.setitem(TASK_HANDLERS, TASK_TYPE_OK, ok_handler)
    monkeypatch.setitem(TASK_HANDLERS, TASK_TYPE_CRASH, crash_handler)
    _use_real_sessions(test_engine, monkeypatch)

    try:
        ok_id: UUID | None = None
        crash_id: UUID | None = None
        # 分两次事务入队，保证 created_at 有先后，领取顺序确定。
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(TASK_TYPE_OK, {"case": "ok"})
            ok_id = task.id
            await seed.commit()

        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(TASK_TYPE_CRASH, {"case": "crash"})
            crash_id = task.id
            await seed.commit()

        with pytest.raises(_SimulatedCrash):
            await task_worker.run_worker(once=True, worker_id="worker-crash")

        async with _session(test_engine) as check:
            finished = await check.get(BackgroundTask, ok_id)
            crashed = await check.get(BackgroundTask, crash_id)

        # 前面那条已经提交成功，没有被后面那条的崩溃带走。
        assert finished.status == "succeeded"
        assert finished.result == {"ok": 1}

        # 崩溃那条：领取状态与尝试次数都留住了（没有回滚成 pending / attempts=0）。
        assert crashed.status == "running"
        assert crashed.attempts == 1
    finally:
        await _cleanup(test_engine)


async def test_attempt_count_survives_a_crash_and_keeps_accumulating(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """崩溃后尝试次数继续累加：回收 → 再领取 → attempts=2。"""

    async def crash_handler(db: AsyncSession, task: BackgroundTask) -> dict[str, int]:
        raise _SimulatedCrash("模拟进程被杀")

    monkeypatch.setitem(TASK_HANDLERS, TASK_TYPE_CRASH, crash_handler)
    _use_real_sessions(test_engine, monkeypatch)

    try:
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(TASK_TYPE_CRASH, {"case": "crash"})
            task_id = task.id
            await seed.commit()

        with pytest.raises(_SimulatedCrash):
            await task_worker.run_worker(once=True, worker_id="worker-crash-1")

        # 租约到期 → 回收 → 重新领取。
        async with _session(test_engine) as session:
            queue = TaskQueue(session, worker_id="worker-reclaim")
            reclaimed = await queue.reclaim_expired(
                now=datetime.now(UTC) + timedelta(seconds=300)
            )
            await session.commit()
            assert reclaimed == 1

        async with _session(test_engine) as session:
            queue = TaskQueue(session, worker_id="worker-reclaim")
            rows = await queue.claim(limit=1)
            await session.commit()
            assert len(rows) == 1
            assert rows[0].attempts == 2
    finally:
        await _cleanup(test_engine)


async def test_a_task_that_keeps_crashing_is_not_requeued_forever(
    test_engine: AsyncEngine,
) -> None:
    """尝试次数用尽的任务不再被领取，直接置为失败 —— 崩溃循环必须收敛。"""

    try:
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(
                TASK_TYPE_EXHAUSTED,
                {"case": "exhausted"},
                max_attempts=1,
            )
            task_id = task.id
            await queue.claim(limit=1)
            await seed.commit()

        # 模拟「进程被杀」：任务停在 running，尝试次数已经是 1。
        async with _session(test_engine) as session:
            queue = TaskQueue(session, worker_id="worker-reclaim")
            reclaimed = await queue.reclaim_expired(
                now=datetime.now(UTC) + timedelta(seconds=300)
            )
            await session.commit()
            assert reclaimed == 1

        async with _session(test_engine) as check:
            row = await check.get(BackgroundTask, task_id)
            assert row.status == "failed"
            assert row.error_code == "retry_exhausted"
            assert row.finished_at is not None

        # 失败的任务不会再被领取。
        async with _session(test_engine) as session:
            queue = TaskQueue(session, worker_id="worker-reclaim")
            assert await queue.claim(limit=10) == []
    finally:
        await _cleanup(test_engine)


async def test_a_late_worker_cannot_write_the_result_of_a_task_it_no_longer_owns(
    test_engine: AsyncEngine,
) -> None:
    """租约被抢走后，迟到的 Worker 不得写结果（否则两个 Worker 同时写同一批数据）。"""

    try:
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-first")
            task = await queue.enqueue(TASK_TYPE_RETRY, {"case": "lease"})
            task_id = task.id
            await queue.claim(limit=1, lease_seconds=60)
            await seed.commit()

        # 另一个 Worker 抢走了租约。
        async with _session(test_engine) as session:
            queue = TaskQueue(session, worker_id="worker-second")
            await queue.reclaim_expired(now=datetime.now(UTC) + timedelta(seconds=300))
            await queue.claim(limit=1, lease_seconds=60)
            await session.commit()

        # 迟到的 Worker 想写结果 —— 必须被拒。
        async with _session(test_engine) as session:
            queue = TaskQueue(session, worker_id="worker-first")
            with pytest.raises(Exception) as exc:
                await queue.complete(task_id, result={"ok": 1}, expected_owner="worker-first")
            assert "租约" in str(exc.value)

        async with _session(test_engine) as check:
            row = await check.get(BackgroundTask, task_id)
            assert row.status == "running"
            assert row.result is None
    finally:
        await _cleanup(test_engine)


# ---------------------------------------------------------------------------
# 问题 2：人工重试的并发覆盖
# ---------------------------------------------------------------------------


async def test_retry_does_not_resurrect_a_task_that_finished_concurrently(
    test_engine: AsyncEngine,
) -> None:
    """重试必须用**原子条件更新**：任务已被执行完时，重试不能把它改回队列。

    早先的写法是「先读状态、再改成等待中」：重试请求读到 failed 之后、
    Worker 把任务跑完之前，重试请求再写一次，就把已经完成的任务改回 pending ——
    于是同一条任务被执行两遍（批量考勤计算每次执行都产生新版本）。
    """

    try:
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(
                TASK_TYPE_RETRY,
                {"case": "retry"},
                max_attempts=1,
            )
            task_id = task.id
            await queue.claim(limit=1)
            await queue.fail(task.id, "handler_exception:runtimeerror")
            await seed.commit()

        # 重试请求开始：它看到的是 failed。
        async with _session(test_engine) as retry_session:
            observed = await retry_session.get(BackgroundTask, task_id)
            assert observed.status == "failed"

            # 期间 Worker 把任务跑完了。
            async with _session(test_engine) as racer:
                racer_queue = TaskQueue(racer, worker_id="worker-racer")
                await racer_queue.complete(task_id, result={"ok": True})
                await racer.commit()

            # 迟到的重试请求必须被拒，不能把任务改回 pending。
            with pytest.raises(ApiError) as exc:
                await retry_background_task(
                    task_id=task_id,
                    db=retry_session,
                    user=_probe_user(),
                )
            assert exc.value.status_code == 409
            assert exc.value.code == "BACKGROUND_TASK_NOT_RETRYABLE"

        async with _session(test_engine) as check:
            row = await check.get(BackgroundTask, task_id)
            assert row.status == "succeeded"
            assert row.attempts == 1
    finally:
        await _cleanup(test_engine)


async def test_concurrent_retries_of_the_same_task_let_only_one_through(
    test_engine: AsyncEngine,
) -> None:
    """两个并发重试只有一个能成功 —— 另一个必须拿到 409。"""

    try:
        async with _session(test_engine) as seed:
            queue = TaskQueue(seed, worker_id="worker-seed")
            task = await queue.enqueue(
                TASK_TYPE_RETRY,
                {"case": "concurrent"},
                max_attempts=1,
            )
            task_id = task.id
            await queue.claim(limit=1)
            await queue.fail(task.id, "handler_exception:runtimeerror")
            await seed.commit()

        async def do_retry() -> tuple[int, str]:
            async with _session(test_engine) as session:
                try:
                    await retry_background_task(
                        task_id=task_id,
                        db=session,
                        user=_probe_user(),
                    )
                except ApiError as exc:
                    return exc.status_code, exc.code
                await session.commit()
                return 200, "ok"

        results = await asyncio.gather(do_retry(), do_retry())
        statuses = sorted(status for status, _ in results)
        assert statuses == [200, 409]
        assert any(code == "BACKGROUND_TASK_NOT_RETRYABLE" for _, code in results)
    finally:
        await _cleanup(test_engine)


# ---------------------------------------------------------------------------
# 问题 3：重复提交标识串到别的导入批次
# ---------------------------------------------------------------------------


async def _validate_import_batch(
    client: AsyncClient,
    token: str,
    *,
    file_name: str,
    employee_number: str,
) -> str:
    response = await client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_auth(token),
        json={
            "entity_type": "person_basic",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_person_basic",
            "file_name": file_name,
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": f"{file_name}-1",
                    "data": {
                        "employee_number": employee_number,
                        "legal_name": "Synthetic Conflict Person",
                    },
                }
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_reusing_an_idempotency_key_for_another_batch_is_rejected(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    """同一个重复提交标识用到**另一个批次**上必须报冲突，而不是返回旧任务。

    早先的写法只要标识相同就返回旧任务：批次 B 会拿到 202「已受理」，
    但 B 根本没进队列 —— 调用方以为提交成功，实际什么都没发生。
    """

    first_batch = await _validate_import_batch(
        business_client,
        admin_token,
        file_name="synthetic-d121-a.csv",
        employee_number="993401",
    )
    second_batch = await _validate_import_batch(
        business_client,
        admin_token,
        file_name="synthetic-d121-b.csv",
        employee_number="993402",
    )
    submit_key = str(uuid4())

    first = await business_client.post(
        f"/api/v1/governance/import-batches/{first_batch}/submit",
        headers=_auth(admin_token),
        json={"reason": "幂等冲突用例：首个批次", "idempotency_key": submit_key},
    )
    assert first.status_code == 202, first.text

    second = await business_client.post(
        f"/api/v1/governance/import-batches/{second_batch}/submit",
        headers=_auth(admin_token),
        json={"reason": "幂等冲突用例：另一个批次", "idempotency_key": submit_key},
    )
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "BACKGROUND_TASK_IDEMPOTENCY_CONFLICT"

    # 第二个批次**没有**产生任务。
    count = await db_session.scalar(
        select(func.count())
        .select_from(BackgroundTask)
        .where(BackgroundTask.payload["batch_id"].as_string() == second_batch)
    )
    assert count == 0

    # 第一个批次的任务还在，状态不变。
    first_task = await db_session.get(BackgroundTask, UUID(first.json()["id"]))
    assert first_task is not None
    assert first_task.status == "pending"


async def test_enqueue_with_a_conflicting_scope_raises_a_conflict(
    db_session: AsyncSession,
) -> None:
    """队列层的同一道防线：标识相同但身份字段不同 → 冲突。"""

    key = f"d121-scope-{uuid4()}"
    queue = TaskQueue(db_session)
    first = await queue.enqueue(
        "test.d121.scope",
        {"batch_id": "batch-a", "actor_id": "actor-1"},
        idempotency_key=key,
        idempotency_scope={"batch_id": "batch-a", "actor_id": "actor-1"},
    )

    with pytest.raises(ApiError) as exc:
        await queue.enqueue(
            "test.d121.scope",
            {"batch_id": "batch-b", "actor_id": "actor-1"},
            idempotency_key=key,
            idempotency_scope={"batch_id": "batch-b", "actor_id": "actor-1"},
        )
    assert exc.value.status_code == 409
    assert exc.value.code == "BACKGROUND_TASK_IDEMPOTENCY_CONFLICT"

    # 同一个身份再提交仍然幂等。
    same = await queue.enqueue(
        "test.d121.scope",
        {"batch_id": "batch-a", "actor_id": "actor-1"},
        idempotency_key=key,
        idempotency_scope={"batch_id": "batch-a", "actor_id": "actor-1"},
    )
    assert same.id == first.id

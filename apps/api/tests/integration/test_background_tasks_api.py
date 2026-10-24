# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""后台任务框架集成测试。

Requirement: D-110 — 覆盖任务状态机、指数退避、领取租约回收、并发领取不重复、
幂等入队、异步导入端到端、接口权限与「错误码不含个人信息」。
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from hris.modules.platform import task_worker
from hris.modules.platform.import_models import ImportBatch
from hris.modules.platform.task_handlers import TASK_HANDLERS, execute_task
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.platform.task_queue import TaskQueue
from hris.modules.workforce.models import Person


pytestmark = pytest.mark.asyncio


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _run_worker_once(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """用测试会话替换 Worker 的会话工厂，跑一轮 Worker。"""

    @asynccontextmanager
    async def _fake_session_factory():
        yield db_session

    monkeypatch.setattr(task_worker, "session_factory", _fake_session_factory)
    await task_worker.run_worker(once=True, worker_id="worker-test-e2e")


async def test_enqueue_claim_complete_moves_task_to_succeeded(
    db_session: AsyncSession,
) -> None:
    queue = TaskQueue(db_session, worker_id="worker-test-1")
    task = await queue.enqueue("test.happy", {"case": "happy"})
    assert task.status == "pending"
    assert task.attempts == 0
    assert task.error_code is None
    assert task.next_attempt_at is not None

    claimed = await queue.claim(limit=10)
    assert [item.id for item in claimed] == [task.id]
    assert task.status == "running"
    assert task.attempts == 1
    assert task.lease_owner == "worker-test-1"
    assert task.lease_expires_at is not None
    assert task.started_at is not None

    finished = await queue.complete(task.id, result={"rows": 3})
    assert finished.status == "succeeded"
    assert finished.result == {"rows": 3}
    assert finished.finished_at is not None
    assert finished.lease_owner is None
    assert finished.lease_expires_at is None


async def test_failed_handler_is_requeued_with_backoff(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(db: AsyncSession, task: BackgroundTask) -> None:
        raise RuntimeError("合成失败")

    monkeypatch.setitem(TASK_HANDLERS, "test.boom.backoff", boom)

    queue = TaskQueue(db_session, worker_id="worker-test-2")
    task = await queue.enqueue("test.boom.backoff", {"case": "backoff"}, max_attempts=3)
    claimed = await queue.claim(limit=10)
    assert len(claimed) == 1

    before = datetime.now(UTC)
    requeued = await execute_task(queue, claimed[0])
    assert requeued.status == "pending"
    assert requeued.attempts == 1
    assert requeued.error_code == "handler_exception:runtimeerror"
    assert requeued.finished_at is None
    # 指数退避首档 30 秒。
    delay = requeued.next_attempt_at - before
    assert timedelta(seconds=29) <= delay <= timedelta(seconds=31)

    # 退避未到，任务不会被再次领取。
    assert await queue.claim(limit=10) == []


async def test_task_is_marked_failed_when_attempts_reach_max_attempts(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(db: AsyncSession, task: BackgroundTask) -> None:
        raise RuntimeError("合成失败")

    monkeypatch.setitem(TASK_HANDLERS, "test.boom.max", boom)

    queue = TaskQueue(db_session, worker_id="worker-test-3")
    task = await queue.enqueue("test.boom.max", {"case": "max"}, max_attempts=2)
    task_id = task.id

    first = await queue.claim(limit=10)
    assert len(first) == 1
    first_result = await execute_task(queue, first[0])
    assert first_result.status == "pending"
    assert first_result.attempts == 1

    record = await db_session.get(BackgroundTask, task_id)
    record.next_attempt_at = datetime.now(UTC)
    await db_session.flush()

    second = await queue.claim(limit=10)
    assert len(second) == 1
    second_result = await execute_task(queue, second[0])
    assert second_result.attempts == 2
    assert second_result.status == "failed"
    assert second_result.finished_at is not None
    assert second_result.error_code == "handler_exception:runtimeerror"


async def test_reclaim_expired_lease_returns_task_to_pending(
    db_session: AsyncSession,
) -> None:
    queue = TaskQueue(db_session, worker_id="worker-test-4")
    task = await queue.enqueue("test.lease", {"case": "lease"})
    claimed = await queue.claim(limit=10, lease_seconds=60)
    assert len(claimed) == 1
    assert claimed[0].status == "running"

    reclaimed = await queue.reclaim_expired(
        now=datetime.now(UTC) + timedelta(seconds=120)
    )
    assert reclaimed == 1
    assert task.status == "pending"
    assert task.lease_owner is None
    assert task.lease_expires_at is None

    again = await queue.claim(limit=10)
    assert len(again) == 1
    assert again[0].id == task.id
    assert again[0].attempts == 2


async def test_concurrent_claim_does_not_hand_out_the_same_task_twice(
    test_engine: AsyncEngine,
) -> None:
    async with AsyncSession(test_engine) as seed_session:
        queue = TaskQueue(seed_session, worker_id="worker-seeder")
        task = await queue.enqueue("test.concurrent", {"case": "concurrent"})
        task_id = task.id
        await seed_session.commit()

    try:

        async def claimer(worker_id: str) -> list[UUID]:
            async with AsyncSession(test_engine) as claim_session:
                claim_queue = TaskQueue(claim_session, worker_id=worker_id)
                rows = await claim_queue.claim(limit=10)
                claimed_ids = [row.id for row in rows]
                await claim_session.commit()
                return claimed_ids

        first, second = await asyncio.gather(
            claimer("worker-a"),
            claimer("worker-b"),
        )
        claimed_ids = first + second
        assert task_id in claimed_ids
        assert claimed_ids.count(task_id) == 1
    finally:
        async with AsyncSession(test_engine) as cleanup_session:
            await cleanup_session.execute(
                delete(BackgroundTask).where(
                    BackgroundTask.task_type == "test.concurrent"
                )
            )
            await cleanup_session.commit()


async def test_enqueue_with_same_idempotency_key_returns_the_same_task(
    db_session: AsyncSession,
) -> None:
    queue = TaskQueue(db_session)
    key = f"import-batch-{uuid4()}"

    first = await queue.enqueue("test.idempotent", {"case": "idem"}, idempotency_key=key)
    second = await queue.enqueue(
        "test.idempotent", {"case": "idem"}, idempotency_key=key
    )

    assert first.id == second.id
    count = await db_session.scalar(
        select(func.count())
        .select_from(BackgroundTask)
        .where(BackgroundTask.idempotency_key == key)
    )
    assert count == 1


async def test_handler_error_code_does_not_leak_personal_information(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(db: AsyncSession, task: BackgroundTask) -> None:
        raise RuntimeError("导入失败，联系人手机号 13800000000")

    monkeypatch.setitem(TASK_HANDLERS, "test.pii", boom)

    queue = TaskQueue(db_session, worker_id="worker-test-pii")
    await queue.enqueue("test.pii", {"case": "pii"})
    claimed = await queue.claim(limit=10)
    assert len(claimed) == 1

    result = await execute_task(queue, claimed[0])
    assert result.error_code is not None
    assert "13800000000" not in result.error_code
    assert result.error_code == "handler_exception:runtimeerror"


async def test_submit_import_batch_runs_in_background_worker(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "person_basic",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_person_basic",
            "file_name": "synthetic-async.csv",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "synthetic-async-1",
                    "data": {
                        "employee_number": "991101",
                        "legal_name": "Synthetic Async Person",
                    },
                }
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    batch_id = validated.json()["id"]

    submitted = await business_client.post(
        f"/api/v1/governance/import-batches/{batch_id}/submit",
        headers=_headers(admin_token),
        json={"reason": "异步执行合成人员导入"},
    )
    assert submitted.status_code == 202, submitted.text
    body = submitted.json()
    assert body["task_type"] == "import_batch.execute"
    assert body["status"] == "pending"
    task_id = body["id"]

    detail = await business_client.get(
        f"/api/v1/governance/tasks/{task_id}",
        headers=_headers(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "pending"
    assert detail.json()["payload"]["batch_id"] == batch_id

    # 提交只落任务，批次此刻还没有被执行。
    batch = await db_session.get(ImportBatch, UUID(batch_id), populate_existing=True)
    assert batch.status == "validated"

    await _run_worker_once(db_session, monkeypatch)

    task_row = await db_session.get(
        BackgroundTask, UUID(task_id), populate_existing=True
    )
    assert task_row.status == "succeeded"
    assert task_row.result is not None
    assert task_row.result["batch_status"] == "completed"
    assert task_row.result["imported_rows"] == 1
    assert task_row.finished_at is not None

    batch = await db_session.get(ImportBatch, UUID(batch_id), populate_existing=True)
    assert batch.status == "completed"

    person = await db_session.scalar(
        select(Person).where(Person.employee_number == "991101")
    )
    assert person is not None
    assert person.legal_name == "Synthetic Async Person"


async def test_submit_import_batch_is_idempotent_with_the_same_key(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    validated = await business_client.post(
        "/api/v1/governance/import-batches/validate",
        headers=_headers(admin_token),
        json={
            "entity_type": "person_basic",
            "source_system": "synthetic_ehr",
            "source_table": "synthetic_person_basic",
            "file_name": "synthetic-idempotent.csv",
            "idempotency_key": str(uuid4()),
            "rows": [
                {
                    "source_record_id": "synthetic-idempotent-1",
                    "data": {
                        "employee_number": "991102",
                        "legal_name": "Synthetic Idempotent Person",
                    },
                }
            ],
        },
    )
    assert validated.status_code == 201, validated.text
    batch_id = validated.json()["id"]
    submit_key = str(uuid4())

    first = await business_client.post(
        f"/api/v1/governance/import-batches/{batch_id}/submit",
        headers=_headers(admin_token),
        json={"reason": "幂等提交合成人员导入", "idempotency_key": submit_key},
    )
    assert first.status_code == 202, first.text

    second = await business_client.post(
        f"/api/v1/governance/import-batches/{batch_id}/submit",
        headers=_headers(admin_token),
        json={"reason": "幂等提交合成人员导入", "idempotency_key": submit_key},
    )
    assert second.status_code == 202, second.text
    assert second.json()["id"] == first.json()["id"]


async def test_submit_import_batch_rejects_unknown_batch(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.post(
        f"/api/v1/governance/import-batches/{uuid4()}/submit",
        headers=_headers(admin_token),
        json={"reason": "提交不存在的批次"},
    )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "IMPORT_BATCH_NOT_FOUND"


async def test_task_list_requires_governance_permission(
    business_client: AsyncClient,
    restricted_token: str,
) -> None:
    response = await business_client.get(
        "/api/v1/governance/tasks",
        headers=_headers(restricted_token),
    )
    assert response.status_code == 403, response.text


async def test_task_list_and_detail_are_visible_to_governance_viewer(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    queue = TaskQueue(db_session)
    task = await queue.enqueue("test.list.visible", {"case": "list"})

    listed = await business_client.get(
        "/api/v1/governance/tasks",
        headers=_headers(admin_token),
        params={"task_type": "test.list.visible"},
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["items"][0]["id"] == str(task.id)
    assert body["items"][0]["status"] == "pending"

    detail = await business_client.get(
        f"/api/v1/governance/tasks/{task.id}",
        headers=_headers(admin_token),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["task_type"] == "test.list.visible"
    assert detail.json()["max_attempts"] == 5


async def test_retry_of_succeeded_task_returns_conflict(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    queue = TaskQueue(db_session)
    task = await queue.enqueue("test.retry.succeeded", {"case": "retry"})
    await queue.complete(task.id, result={"ok": True})

    response = await business_client.post(
        f"/api/v1/governance/tasks/{task.id}/retry",
        headers=_headers(admin_token),
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "BACKGROUND_TASK_NOT_RETRYABLE"


async def test_retry_of_failed_task_resets_it_to_pending(
    business_client: AsyncClient,
    db_session: AsyncSession,
    admin_token: str,
) -> None:
    queue = TaskQueue(db_session)
    task = await queue.enqueue("test.retry.failed", {"case": "retry"}, max_attempts=1)
    await queue.claim(limit=10)
    await queue.fail(task.id, "handler_exception:runtimeerror")

    response = await business_client.post(
        f"/api/v1/governance/tasks/{task.id}/retry",
        headers=_headers(admin_token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["attempts"] == 0
    assert body["error_code"] is None
    assert body["finished_at"] is None


async def test_retry_requires_governance_admin_permission(
    business_client: AsyncClient,
    db_session: AsyncSession,
    restricted_token: str,
) -> None:
    queue = TaskQueue(db_session)
    task = await queue.enqueue("test.retry.denied", {"case": "retry"}, max_attempts=1)
    await queue.claim(limit=10)
    await queue.fail(task.id, "handler_exception:runtimeerror")

    response = await business_client.post(
        f"/api/v1/governance/tasks/{task.id}/retry",
        headers=_headers(restricted_token),
    )
    assert response.status_code == 403, response.text

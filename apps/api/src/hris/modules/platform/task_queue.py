# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Background task queue.

Requirement: D-110 — 长任务从请求链路搬进可重试后台任务框架：
任务表是唯一事实来源，领取用 PostgreSQL ``FOR UPDATE SKIP LOCKED``，
多 Worker 实例并行运行不会重复消费同一条任务。
失败按指数退避重排，超过重试上限置为 ``failed``；
失败原因只保留受控错误码，异常原文不落库。
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.core.redaction import sanitize_error_code
from hris.modules.platform.task_models import (
    TASK_STATUS_CANCELED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_SUCCEEDED,
    BackgroundTask,
)


MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 1800
DEFAULT_LEASE_SECONDS = 60


class TaskQueue:
    """后台任务队列。

    取舍说明：
    - 退避参数与消息投递队列保持一致（30s 起、按次翻倍、上限 1800s），
      避免同一套运维心智模型下出现两套节奏。
    - 领取租约默认 60 秒：长任务单次执行超过租约时会被回收流程重排，
      代价是任务可能被重复执行，因此处理器必须自身幂等（导入批次执行即是）。
    """

    def __init__(self, db: AsyncSession, *, worker_id: str | None = None) -> None:
        self._db = db
        self._worker_id = worker_id or f"worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    @property
    def db(self) -> AsyncSession:
        """暴露底层会话，供处理器在保存点内执行。"""

        return self._db

    @property
    def worker_id(self) -> str:
        """当前领取者标识，写进 ``lease_owner`` 便于排障。"""

        return self._worker_id

    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        *,
        max_attempts: int = MAX_ATTEMPTS,
        created_by: UUID | None = None,
        idempotency_key: str | None = None,
        available_at: datetime | None = None,
    ) -> BackgroundTask:
        """把任务放进队列。

        ``idempotency_key`` 命中已存在的任务时**直接返回那条既有任务**（幂等，不新建）。
        """

        if idempotency_key is not None:
            existing = await self.find_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        now = datetime.now(UTC)
        task = BackgroundTask(
            task_type=task_type,
            status=TASK_STATUS_PENDING,
            payload=dict(payload),
            result=None,
            error_code=None,
            attempts=0,
            max_attempts=max_attempts,
            next_attempt_at=available_at if available_at is not None else now,
            lease_owner=None,
            lease_expires_at=None,
            started_at=None,
            finished_at=None,
            created_by=created_by,
            idempotency_key=idempotency_key,
            progress=None,
        )
        try:
            # 保存点：并发入队时唯一键冲突只回滚这一条插入，不牵连调用方的事务。
            async with self._db.begin_nested():
                self._db.add(task)
                await self._db.flush()
        except IntegrityError:
            if idempotency_key is None:
                raise
            existing = await self.find_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            return existing
        return task

    async def claim(
        self,
        limit: int = 50,
        *,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> list[BackgroundTask]:
        """领取一批待执行任务。

        领取使用 ``FOR UPDATE SKIP LOCKED``：多个 Worker 实例并行执行时，
        同一批行只会被一个实例拿到，其余实例直接跳过。
        """

        now = datetime.now(UTC)
        rows = (
            await self._db.scalars(
                select(BackgroundTask)
                .where(
                    BackgroundTask.status == TASK_STATUS_PENDING,
                    BackgroundTask.next_attempt_at <= now,
                )
                .order_by(BackgroundTask.next_attempt_at, BackgroundTask.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for task in rows:
            task.status = TASK_STATUS_RUNNING
            task.attempts += 1
            task.lease_owner = self._worker_id
            task.lease_expires_at = now + timedelta(seconds=lease_seconds)
            task.started_at = now
        if rows:
            await self._db.flush()
        return list(rows)

    async def complete(
        self,
        task_id: UUID,
        result: dict[str, Any] | None = None,
        progress: str | None = None,
    ) -> BackgroundTask:
        """把任务标记为成功。"""

        task = await self._require(task_id)
        task.status = TASK_STATUS_SUCCEEDED
        task.result = result
        task.progress = progress
        task.error_code = None
        task.finished_at = datetime.now(UTC)
        task.lease_owner = None
        task.lease_expires_at = None
        await self._db.flush()
        await self._refresh(task)
        return task

    async def renew_lease(
        self,
        task_id: UUID,
        *,
        expected_owner: str | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> BackgroundTask:
        """延长一条**正在执行**的任务的租约。

        Requirement: D-116 — 领取租约默认 60 秒，而批量考勤计算（200 人 × 一个月
        ≈ 6000 次单位计算）会跑好几分钟。租约一到期，回收流程就会把任务重排成
        `pending`，另一个 Worker 会**重复执行**它 —— 而批量计算不是幂等的
        （每次执行都产生新版本），重复执行等于重复写结果与审计。

        所以长任务必须在执行过程中**主动续租**。

        `expected_owner` 传当前租约持有者时做校验：租约已经被别人抢走时
        （例如原 Worker 只是卡住没退出）**不续租**，避免把别人的租约延长。
        """
        task = await self._require(task_id)
        if task.status != TASK_STATUS_RUNNING:
            raise ValueError("only running tasks can renew their lease")
        if expected_owner is not None and task.lease_owner != expected_owner:
            raise ValueError("lease owner mismatch")
        task.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        await self._db.flush()
        return task

    async def fail(
        self,
        task_id: UUID,
        error_code: str,
        *,
        retryable: bool = True,
    ) -> BackgroundTask:
        """把任务标记为失败。

        ``retryable=True`` 且还有重试次数时回到 ``pending`` 并按指数退避重排；
        否则置为 ``failed`` 并落结束时间。
        """

        task = await self._require(task_id)
        task.error_code = sanitize_error_code(error_code) or "unknown_error"
        task.lease_owner = None
        task.lease_expires_at = None
        now = datetime.now(UTC)
        if retryable and task.attempts < task.max_attempts:
            task.status = TASK_STATUS_PENDING
            task.next_attempt_at = now + timedelta(
                seconds=self._backoff_seconds(task.attempts)
            )
            task.finished_at = None
        else:
            task.status = TASK_STATUS_FAILED
            task.finished_at = now
        await self._db.flush()
        await self._refresh(task)
        return task

    async def cancel(self, task_id: UUID) -> BackgroundTask:
        """把任务标记为已取消。"""

        task = await self._require(task_id)
        task.status = TASK_STATUS_CANCELED
        task.finished_at = datetime.now(UTC)
        task.lease_owner = None
        task.lease_expires_at = None
        await self._db.flush()
        await self._refresh(task)
        return task

    async def reclaim_expired(self, now: datetime | None = None) -> int:
        """回收租约超时的任务，返回回收条数。

        Worker 崩溃时任务会停在 ``running``；没有这一步，任务将永久卡死。
        ``now`` 只作为「租约是否已过期」的判定基准；
        回收后的任务**立即**可被再次领取，因此 ``next_attempt_at`` 取真实当前时间
        而不是判定基准（判定基准可能来自测试用的未来时刻）。
        """

        cutoff = now if now is not None else datetime.now(UTC)
        available_at = datetime.now(UTC)
        rows = (
            await self._db.scalars(
                select(BackgroundTask)
                .where(
                    BackgroundTask.status == TASK_STATUS_RUNNING,
                    BackgroundTask.lease_expires_at.is_not(None),
                    BackgroundTask.lease_expires_at < cutoff,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        for task in rows:
            task.status = TASK_STATUS_PENDING
            task.lease_owner = None
            task.lease_expires_at = None
            task.next_attempt_at = available_at
        if rows:
            await self._db.flush()
        return len(rows)

    async def find_by_idempotency_key(self, idempotency_key: str) -> BackgroundTask | None:
        """按幂等键查任务；没有则返回 ``None``。"""

        return await self._db.scalar(
            select(BackgroundTask).where(
                BackgroundTask.idempotency_key == idempotency_key
            )
        )

    async def _require(self, task_id: UUID) -> BackgroundTask:
        task = await self._db.get(BackgroundTask, task_id)
        if task is None:
            raise ApiError(
                status_code=404,
                code="BACKGROUND_TASK_NOT_FOUND",
                message="后台任务不存在",
            )
        return task

    async def _refresh(self, task: BackgroundTask) -> None:
        """重新读取任务行。

        Requirement: D-110 — ``updated_at`` 带服务端 ``onupdate``，更新后会被标记为过期；
        不刷新就交给调用方序列化会触发异步会话里不可用的懒加载。
        """

        await self._db.refresh(task)

    def _backoff_seconds(self, attempts: int) -> int:
        return min(
            BASE_BACKOFF_SECONDS * (2 ** max(attempts - 1, 0)),
            MAX_BACKOFF_SECONDS,
        )

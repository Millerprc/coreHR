# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Standalone background task worker process.

Requirement: D-110 — 长任务由**独立 Worker 进程**执行，不挂在 API 应用启动路径上。
Worker 用 PostgreSQL ``FOR UPDATE SKIP LOCKED`` 领取待执行任务，多实例可并行运行；
领取租约超时的任务会被回收成 ``pending``，因此 Worker 崩溃不会让任务永久卡死。

Requirement: D-121 — **每条任务一个独立事务**（领取、执行、落结果三段各自提交）。

早先的实现是「一批任务共用一次提交」，三个后果都是真的：

1. 领取状态（``pending → running``）在整批跑完前不提交，页面看到的还是「等待中」；
2. 批次中途崩溃会回滚**整批**，前面已经执行完的任务连同业务写入一起没了；
3. 尝试次数与领取状态在同一个事务里，崩溃时一起回滚 ——
   反复崩溃的任务永远攒不够次数，「最多重试 N 次」形同虚设。

现在拆成三段：

- **领取**：单独提交，状态与尝试次数立刻可见、立刻落库；
- **执行**：每条任务独占一个事务，并对任务行加 ``FOR UPDATE`` ——
  执行期间别的 Worker 既回收不了它，也不会重复执行它；
- **落结果**：在同一个执行事务里提交，失败只回滚这一条。

另有一处连带问题：批量领取时，排在后面的任务的租约在轮到它之前就可能过期
（领取时统一起算，60 秒租约遇上一条要跑几分钟的任务就必然过期），
回收流程会把它们放回队列，导致**另一个 Worker 重复执行**。
改成「一次领一条、立刻执行」后，租约总是执行前才起算。

运行方式（容器内，``/work`` 为 ``apps/api`` 挂载点）::

    python -m hris.modules.platform.task_worker
    python -m hris.modules.platform.task_worker --once
    python -m hris.modules.platform.task_worker --batch-size 100 --poll-interval 1
"""

import argparse
import asyncio
import logging
import os
import random
import signal
from types import FrameType
from uuid import UUID

from sqlalchemy import select

from hris.core.database import session_factory
from hris.modules.platform.task_handlers import execute_task
from hris.modules.platform.task_models import (
    TASK_STATUS_RUNNING,
    BackgroundTask,
)
from hris.modules.platform.task_queue import (
    DEFAULT_LEASE_SECONDS,
    TaskLeaseLostError,
    TaskQueue,
)


logger = logging.getLogger("hris.platform.task_worker")

DEFAULT_BATCH_SIZE = 50
DEFAULT_POLL_INTERVAL_SECONDS = 2.0

#: 单条任务的执行结果。
OUTCOME_EXECUTED = "executed"
OUTCOME_MISSING = "missing"
OUTCOME_NOT_OWNER = "not_owner"
OUTCOME_LEASE_LOST = "lease_lost"


async def _reclaim_expired(owner: str) -> int:
    """回收租约超时的任务（独立事务，回收结果立即可见）。"""

    async with session_factory() as session:
        queue = TaskQueue(session, worker_id=owner)
        reclaimed = await queue.reclaim_expired()
        await session.commit()
        return reclaimed


async def _claim_one(*, owner: str, lease_seconds: int) -> UUID | None:
    """领取一条任务并**立即提交**。

    单独提交的意义：任务状态与尝试次数在执行的**之前**就落库 ——
    页面马上能看到「运行中」，而进程崩溃也不会把尝试次数一起回滚。
    """

    async with session_factory() as session:
        queue = TaskQueue(session, worker_id=owner)
        rows = await queue.claim(limit=1, lease_seconds=lease_seconds)
        # id 必须在提交前取出来：提交之后 ORM 属性可能已过期，
        # 再访问就会变成异步上下文里的非法懒加载。
        claimed_id = rows[0].id if rows else None
        await session.commit()
        return claimed_id


async def _execute_claimed_task(*, task_id: UUID, owner: str) -> str:
    """执行一条已领取的任务（独立事务，行锁保护）。"""

    async with session_factory() as session:
        queue = TaskQueue(session, worker_id=owner)
        # 行锁：执行期间别的 Worker 回收不了这条任务（``SKIP LOCKED`` 会跳过它），
        # 因此不会重复执行 —— 批量考勤计算每次执行都产生新版本，重复执行是数据事故。
        task = await session.scalar(
            select(BackgroundTask)
            .where(BackgroundTask.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if task is None:
            return OUTCOME_MISSING
        if task.status != TASK_STATUS_RUNNING or task.lease_owner != owner:
            # 领取之后、执行之前被别的 Worker 回收并接管 —— 不重复执行。
            return OUTCOME_NOT_OWNER
        try:
            await execute_task(queue, task)
        except TaskLeaseLostError:
            # 租约在执行途中被抢走：回滚本次执行，不写结果，交给新持有者。
            await session.rollback()
            return OUTCOME_LEASE_LOST
        await session.commit()
        return OUTCOME_EXECUTED


async def run_worker(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    once: bool = False,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    worker_id: str | None = None,
) -> None:
    """领取并执行后台任务，直到收到停止信号。"""

    stop = asyncio.Event()
    _install_signal_handlers(stop)
    owner = worker_id or f"worker-{os.getpid()}"
    logger.info(
        "background task worker started (worker_id=%s, batch_size=%s, poll_interval=%s, once=%s)",
        owner,
        batch_size,
        poll_interval,
        once,
    )
    try:
        while not stop.is_set():
            reclaimed = await _reclaim_expired(owner)
            processed = 0
            for _ in range(batch_size):
                if stop.is_set():
                    break
                task_id = await _claim_one(owner=owner, lease_seconds=lease_seconds)
                if task_id is None:
                    break
                outcome = await _execute_claimed_task(task_id=task_id, owner=owner)
                processed += 1
                if outcome != OUTCOME_EXECUTED:
                    logger.warning(
                        "background task not executed task_id=%s outcome=%s worker_id=%s",
                        task_id,
                        outcome,
                        owner,
                    )
            if reclaimed or processed:
                logger.info(
                    "task cycle reclaimed=%s processed=%s worker_id=%s",
                    reclaimed,
                    processed,
                    owner,
                )
            if once:
                break
            delay = poll_interval if processed else poll_interval * 2
            delay += random.uniform(0, poll_interval * 0.2)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue
    finally:
        logger.info("background task worker stopped")


def _install_signal_handlers(stop: asyncio.Event) -> None:
    """把停止信号接到 ``stop`` 事件上。

    Requirement: D-110 — Worker 必须可独立部署与重启，收到停止信号后优雅退出。
    Windows 上没有 ``loop.add_signal_handler``，这里用 ``signal.signal`` 兜底。
    """

    loop = asyncio.get_running_loop()

    def handler(signum: int, frame: FrameType | None) -> None:
        loop.call_soon_threadsafe(stop.set)

    for name in ("SIGINT", "SIGTERM"):
        signal_number = getattr(signal, name, None)
        if signal_number is None:
            continue
        try:
            signal.signal(signal_number, handler)
        except (OSError, ValueError):
            continue


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(
        prog="python -m hris.modules.platform.task_worker",
        description="coreHR 后台任务 Worker（PostgreSQL SKIP LOCKED 队列）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="单轮最多处理的任务条数（每条任务独立提交）",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="没有待执行任务时的轮询间隔（秒）",
    )
    parser.add_argument(
        "--lease-seconds",
        type=int,
        default=DEFAULT_LEASE_SECONDS,
        help="领取租约时长（秒），超时未完成的任务会被回收重排",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只跑一轮后退出，用于排障与冒烟",
    )
    parser.add_argument("--log-level", default="INFO", help="日志级别")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(
        run_worker(
            batch_size=args.batch_size,
            poll_interval=args.poll_interval,
            once=args.once,
            lease_seconds=args.lease_seconds,
            worker_id=f"worker-{os.getpid()}",
        )
    )


if __name__ == "__main__":
    main()

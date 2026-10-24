# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Standalone background task worker process.

Requirement: D-110 — 长任务由**独立 Worker 进程**执行，不挂在 API 应用启动路径上。
Worker 用 PostgreSQL ``FOR UPDATE SKIP LOCKED`` 领取待执行任务，多实例可并行运行；
领取租约超时的任务会被回收成 ``pending``，因此 Worker 崩溃不会让任务永久卡死。

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

from hris.core.database import session_factory
from hris.modules.platform.task_handlers import execute_task
from hris.modules.platform.task_queue import DEFAULT_LEASE_SECONDS, TaskQueue


logger = logging.getLogger("hris.platform.task_worker")

DEFAULT_BATCH_SIZE = 50
DEFAULT_POLL_INTERVAL_SECONDS = 2.0


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
            async with session_factory() as session:
                queue = TaskQueue(session, worker_id=owner)
                reclaimed = await queue.reclaim_expired()
                tasks = await queue.claim(
                    limit=batch_size,
                    lease_seconds=lease_seconds,
                )
                for task in tasks:
                    await execute_task(queue, task)
                await session.commit()
            if reclaimed or tasks:
                logger.info(
                    "task batch reclaimed=%s claimed=%s worker_id=%s",
                    reclaimed,
                    len(tasks),
                    owner,
                )
            if once:
                break
            delay = poll_interval if tasks else poll_interval * 2
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
        help="单轮领取的任务上限",
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

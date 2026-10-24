# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""假期自动计提调度器（独立 Worker 进程运行）。

与流程调度器同一模式：基于 asyncio 的调度循环，不引入新依赖
（`apps/api` 容器镜像里没有 APScheduler 等调度包，加依赖要重建镜像）。

本模块**不挂在应用启动路径上**：`create_business_app()` 不会 import 它。
由独立 Worker 进程调用：`python -m hris.modules.attendance.accrual_scheduler`。

开关与阈值全部来自环境变量（前缀 `LEAVE_ACCRUAL_SCHEDULER_`），**默认关闭**；
关闭时不产生任何写入。

多实例安全：
- 事务级 advisory lock（`pg_try_advisory_xact_lock`）：同一时刻只有一个实例在跑这一轮。
- 规则扫描用 `FOR UPDATE ... SKIP LOCKED`：行级冲突时直接跳过，不互相等待。

Requirement: D-107 —— 规则取值未配置时必须跳过并记录可读原因，不得用默认值硬算。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hris.modules.attendance.grant_service import AccrualRunResult, LeaveGrantService


logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid5(NAMESPACE_URL, "corehr:system:leave-accrual")


class LeaveAccrualSchedulerSettings(BaseSettings):
    """调度器配置（环境变量前缀 `LEAVE_ACCRUAL_SCHEDULER_`）。"""

    model_config = SettingsConfigDict(
        env_prefix="LEAVE_ACCRUAL_SCHEDULER_",
        extra="ignore",
    )

    # 默认关闭：调度器是独立进程，由运维显式开启。
    enabled: bool = False
    # 轮询间隔（秒）。
    poll_interval_seconds: int = 3600
    # 计提期间粒度：month=按自然月，year=按自然年。
    period_type: Literal["month", "year"] = "month"
    # 是否在计提后自动发放（写余额流水）。默认只生成草稿批次，由人工复核后发放。
    auto_issue: bool = False
    # 事务级 advisory lock 键，多实例之间靠它互斥。
    advisory_lock_key: int = 20261025


class LeaveAccrualScheduler:
    """假期自动计提调度器。"""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: LeaveAccrualSchedulerSettings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or LeaveAccrualSchedulerSettings()

    @property
    def settings(self) -> LeaveAccrualSchedulerSettings:
        return self._settings

    def period_code(self, today: date) -> str:
        if self._settings.period_type == "year":
            return f"{today.year:04d}"
        return f"{today.year:04d}-{today.month:02d}"

    async def run_once(self, today: date | None = None) -> AccrualRunResult:
        """跑一轮计提，返回计提结果；拿不到锁时直接返回空结果。"""
        business_date = today or datetime.now(UTC).date()
        async with self._session_factory() as session:
            locked = await session.scalar(
                select(func.pg_try_advisory_xact_lock(self._settings.advisory_lock_key))
            )
            if not locked:
                logger.debug(
                    "leave accrual scheduler skipped: another instance holds the lock"
                )
                return AccrualRunResult()
            service = LeaveGrantService(
                session,
                actor_id=self._settings.system_actor_id,
                trace_id=f"leave-accrual-{business_date.isoformat()}",
            )
            result = await service.run_accrual(
                period_code=self.period_code(business_date),
                period_type=self._settings.period_type,
                grant_date=business_date,
                auto_issue=self._settings.auto_issue,
            )
            for skip in result.skipped:
                logger.warning(
                    "leave accrual skipped rule=%s code=%s reason=%s",
                    skip.rule_id,
                    skip.code,
                    skip.reason,
                )
            if result.created_items:
                logger.info(
                    "leave accrual created batch=%s items=%s",
                    result.batch_number,
                    result.created_items,
                )
            await session.commit()
            return result

    async def run_forever(self) -> None:
        """调度循环。由独立 Worker 进程调用。"""
        while True:
            try:
                await self.run_once()
            except Exception:  # noqa: BLE001 — 调度循环不能因为单轮失败而退出
                logger.exception("leave accrual scheduler cycle failed")
            await asyncio.sleep(self._settings.poll_interval_seconds)


async def _run_worker(settings: LeaveAccrualSchedulerSettings) -> None:
    # 局部导入：让 `import hris.modules.attendance.accrual_scheduler` 不产生数据库引擎副作用。
    from hris.core.database import session_factory

    scheduler = LeaveAccrualScheduler(session_factory=session_factory, settings=settings)
    logger.info(
        "leave accrual scheduler started period_type=%s poll_seconds=%s auto_issue=%s",
        settings.period_type,
        settings.poll_interval_seconds,
        settings.auto_issue,
    )
    await scheduler.run_forever()


def main(argv: list[str] | None = None) -> int:
    """Worker 入口：`python -m hris.modules.attendance.accrual_scheduler`。"""
    del argv
    settings = LeaveAccrualSchedulerSettings()
    if not settings.enabled:
        logger.warning(
            "leave accrual scheduler is disabled "
            "(set LEAVE_ACCRUAL_SCHEDULER_ENABLED=true to start the worker)"
        )
        return 0
    asyncio.run(_run_worker(settings))
    return 0


if __name__ == "__main__":  # pragma: no cover - 进程入口
    raise SystemExit(main())

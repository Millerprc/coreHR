# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Background task handler registry.

Requirement: D-110 — 任务类型与处理器的对应关系集中在一处注册表里，
Worker 只认注册表，不认识任何业务细节。
处理器签名固定为 ``async def (db, task) -> dict | None``，
返回的字典会落进任务表的 ``result`` 列，因此只允许放**非个人信息**的统计值。
"""

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.attendance.extended_schemas import AttendanceCalculationScope
from hris.modules.attendance.extended_service import ExtendedAttendanceService
from hris.modules.platform.import_service import ImportService
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.platform.task_queue import TaskQueue


logger = logging.getLogger("hris.platform.task_handlers")

Handler = Callable[[AsyncSession, BackgroundTask], Awaitable[dict[str, Any] | None]]

IMPORT_BATCH_EXECUTE = "import_batch.execute"
ATTENDANCE_CALCULATE = "attendance.calculate"

#: 续租间隔（秒）。领取租约默认 60 秒，批量计算要跑好几分钟，
#: 不续租会被回收流程重排成 pending 并被另一个 Worker **重复执行**。
_LEASE_RENEW_INTERVAL_SECONDS = 15.0


async def _execute_import_batch(
    db: AsyncSession,
    task: BackgroundTask,
) -> dict[str, Any] | None:
    """执行一次导入批次。

    载荷只放坐标：批次 id、发起人 id、链路 id、执行原因——
    不放姓名、手机号等个人信息，避免后台任务表变成敏感数据落点。
    """

    payload = task.payload or {}
    raw_batch_id = payload.get("batch_id")
    raw_actor_id = payload.get("actor_id")
    if not raw_batch_id or not raw_actor_id:
        raise ValueError("import_batch.execute payload requires batch_id and actor_id")
    batch_id = UUID(str(raw_batch_id))
    actor_id = UUID(str(raw_actor_id))
    trace_id = str(payload.get("trace_id") or "background-task")
    reason = str(payload.get("reason") or "后台任务执行导入批次")

    service = ImportService(db, actor_id=actor_id, trace_id=trace_id)
    batch, _rows = await service.execute_batch(batch_id, reason=reason)
    return {
        "batch_id": str(batch.id),
        "batch_status": batch.status,
        "total_rows": batch.total_rows,
        "imported_rows": batch.imported_rows,
        "skipped_rows": batch.skipped_rows,
        "rejected_rows": batch.rejected_rows,
    }


async def _execute_attendance_calculation(
    db: AsyncSession,
    task: BackgroundTask,
) -> dict[str, Any] | None:
    """执行一次批量考勤计算（日报或月报）。

    Requirement: D-116 — 200 人规模下逐人提交不可用，批量计算因此走后台任务。

    载荷只放坐标与范围（类型、范围、人员 id 列表、日期、发起人、链路 id、原因），
    **不放姓名、手机号等个人信息**；结果只回统计值（成功数、失败数、失败错误码计数），
    同样不含个人信息。
    """

    payload = task.payload or {}
    kind = str(payload.get("kind") or "")
    if kind not in ("daily", "monthly"):
        raise ValueError("attendance.calculate payload requires kind")
    scope = AttendanceCalculationScope(str(payload.get("scope") or "all"))
    raw_ids = payload.get("employment_ids") or []
    employment_ids = [UUID(str(item)) for item in raw_ids]
    reason = str(payload.get("reason") or "后台任务计算考勤")
    raw_actor_id = payload.get("actor_id")
    if not raw_actor_id:
        raise ValueError("attendance.calculate payload requires actor_id")
    actor_id = UUID(str(raw_actor_id))
    trace_id = str(payload.get("trace_id") or "background-task")

    service = ExtendedAttendanceService(db, actor_id=actor_id, trace_id=trace_id)
    queue = TaskQueue(db)
    renewed_at = time.monotonic()

    async def keepalive() -> None:
        """在长循环里续租，避免任务被回收后重复执行。"""

        nonlocal renewed_at
        now = time.monotonic()
        if now - renewed_at < _LEASE_RENEW_INTERVAL_SECONDS:
            return
        renewed_at = now
        # 租约已被别人抢走时 renew_lease 会抛错 —— 此时必须**中止整个任务**，
        # 而不是继续写结果（否则两个 Worker 同时在写同一批考勤结果）。
        # 异常会一路冒到 execute_task，Worker 放弃这条任务并回滚本次执行。
        await queue.renew_lease(task.id, expected_owner=task.lease_owner)

    if kind == "daily":
        raw_work_date = payload.get("work_date")
        if not raw_work_date:
            raise ValueError("attendance.calculate payload requires work_date")
        return await service.calculate_daily_batch(
            scope=scope,
            employment_ids=employment_ids,
            work_date=date.fromisoformat(str(raw_work_date)),
            reason=reason,
            keepalive=keepalive,
        )

    raw_period_month = payload.get("period_month")
    if not raw_period_month:
        raise ValueError("attendance.calculate payload requires period_month")
    return await service.calculate_monthly_batch(
        scope=scope,
        employment_ids=employment_ids,
        period_month=date.fromisoformat(str(raw_period_month)),
        reason=reason,
        keepalive=keepalive,
    )


TASK_HANDLERS: dict[str, Handler] = {
    IMPORT_BATCH_EXECUTE: _execute_import_batch,
    ATTENDANCE_CALCULATE: _execute_attendance_calculation,
}


def get_handler(task_type: str) -> Handler | None:
    """按任务类型取处理器；未知类型返回 ``None``。"""

    return TASK_HANDLERS.get(task_type)


async def execute_task(queue: TaskQueue, task: BackgroundTask) -> BackgroundTask:
    """执行单条任务并落状态。

    Requirement: D-110 — 处理器抛出的异常原文可能含姓名、手机号等个人信息，
    因此只把「异常类型名」写进错误码，异常原文既不落库也不进日志。
    处理器在保存点内执行，单条任务失败不会污染同一轮里的其他任务。

    Requirement: D-121 — 落结果时校验**租约归属**：租约已被别的 Worker 抢走就
    抛 :class:`TaskLeaseLostError`，由 Worker 放弃这条任务。
    迟到的 Worker 绝不能把别人正在跑的任务改写掉。
    """

    handler = get_handler(task.task_type)
    if handler is None:
        logger.warning(
            "background task handler not found task_id=%s task_type=%s",
            task.id,
            task.task_type,
        )
        return await queue.fail(
            task.id,
            f"handler_unknown:{task.task_type}",
            retryable=False,
            expected_owner=queue.worker_id,
        )

    try:
        async with queue.db.begin_nested():
            result = await handler(queue.db, task)
    except Exception as exc:  # noqa: BLE001 — 处理器异常统一收敛成受控错误码
        logger.warning(
            "background task handler failed task_id=%s task_type=%s exception=%s",
            task.id,
            task.task_type,
            type(exc).__name__,
        )
        return await queue.fail(
            task.id,
            f"handler_exception:{type(exc).__name__}",
            expected_owner=queue.worker_id,
        )
    return await queue.complete(
        task.id,
        result=result,
        expected_owner=queue.worker_id,
    )

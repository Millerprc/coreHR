# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Async import submission API.

Requirement: D-110 — 长任务走可重试后台任务：提交导入只落一条任务记录即返回 202，
真正的批次执行由独立 Worker 进程完成。
既有的同步执行端点 ``POST /import-batches/{batch_id}/execute`` 保持原样，
异步是**新增**路径而不是替换，两条路径并存。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.platform.dependencies import ensure_permissions, require_permission
from hris.modules.platform.import_models import ImportBatch
from hris.modules.platform.models import UserAccount
from hris.modules.platform.task_handlers import IMPORT_BATCH_EXECUTE
from hris.modules.platform.task_models import BackgroundTask
from hris.modules.platform.task_queue import TaskQueue
from hris.modules.platform.task_schemas import BackgroundTaskSummaryResponse


router = APIRouter(prefix="/api/v1/governance", tags=["phase-1-data-governance"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
GovernanceAdmin = Annotated[
    UserAccount,
    Depends(require_permission("DATA_GOVERNANCE_ADMIN")),
]

# 与 ImportService.execute_batch 的可执行状态集合保持一致。
EXECUTABLE_BATCH_STATUSES = frozenset({"validated", "validated_with_errors"})


class ImportBatchSubmit(BaseModel):
    """异步执行导入批次的请求体。

    ``idempotency_key`` 命中**同一次提交**时返回**同一条任务**（幂等），
    不带该字段则每次提交都产生一条新任务。

    Requirement: D-121 — 同一个标识被复用到**另一条导入请求**（另一个批次或另一个
    发起人）时必须报冲突，而不是返回旧任务。
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: UUID | None = None


def _assert_same_submission(
    task: BackgroundTask,
    *,
    batch_id: UUID,
    actor_id: UUID,
) -> None:
    """校验幂等标识命中的任务确实是**这一次提交**。

    Requirement: D-121 — 早先的写法只要标识相同就返回旧任务。
    批次 B 复用批次 A 的标识时，接口会返回 202「已受理」，
    但 B 根本没进队列 —— 调用方以为提交成功，实际什么都没发生。
    标识相同但请求不同，必须是 409 冲突。
    """

    payload = task.payload or {}
    same_request = (
        task.task_type == IMPORT_BATCH_EXECUTE
        and str(payload.get("batch_id")) == str(batch_id)
        and str(payload.get("actor_id")) == str(actor_id)
    )
    if not same_request:
        raise ApiError(
            status_code=409,
            code="BACKGROUND_TASK_IDEMPOTENCY_CONFLICT",
            message="重复提交标识已被另一条后台任务占用",
        )


@router.post(
    "/import-batches/{batch_id}/submit",
    response_model=BackgroundTaskSummaryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_import_batch(
    batch_id: UUID,
    payload: ImportBatchSubmit,
    db: DbSession,
    user: GovernanceAdmin,
    request: Request,
) -> BackgroundTaskSummaryResponse:
    """把一次导入批次执行排进后台任务队列。"""

    batch = await db.get(ImportBatch, batch_id)
    if batch is None:
        raise ApiError(
            status_code=404,
            code="IMPORT_BATCH_NOT_FOUND",
            message="导入批次不存在",
        )
    if batch.entity_type == "person_basic":
        await ensure_permissions(user, db, "PERSON_IMPORT")

    queue = TaskQueue(db)
    idempotency_key = (
        str(payload.idempotency_key) if payload.idempotency_key is not None else None
    )
    if idempotency_key is not None:
        existing = await queue.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            # 幂等命中必须先校验是不是同一次提交，再决定是返回旧任务还是报冲突。
            _assert_same_submission(existing, batch_id=batch_id, actor_id=user.id)
            return BackgroundTaskSummaryResponse.model_validate(existing)

    if batch.status not in EXECUTABLE_BATCH_STATUSES:
        raise ApiError(
            status_code=409,
            code="IMPORT_BATCH_NOT_EXECUTABLE",
            message="导入批次尚未完成校验或当前状态不可执行",
        )

    task = await queue.enqueue(
        IMPORT_BATCH_EXECUTE,
        {
            "batch_id": str(batch_id),
            "actor_id": str(user.id),
            "trace_id": str(request.state.trace_id),
            "reason": payload.reason,
        },
        created_by=user.id,
        idempotency_key=idempotency_key,
        idempotency_scope={"batch_id": str(batch_id), "actor_id": str(user.id)},
    )
    return BackgroundTaskSummaryResponse.model_validate(task)

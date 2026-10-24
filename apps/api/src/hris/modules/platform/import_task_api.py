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

    ``idempotency_key`` 命中既有任务时返回**同一条任务**（幂等），
    不带该字段则每次提交都产生一条新任务。
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: UUID | None = None


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
    )
    return BackgroundTaskSummaryResponse.model_validate(task)

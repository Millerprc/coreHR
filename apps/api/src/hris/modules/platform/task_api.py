# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""Background task management API.

Requirement: D-110 — 治理端要能看见长任务的真实状态并做人工补偿：
列表与详情提供可见性，``retry`` 提供失败任务的人工重试入口。
读用 ``DATA_GOVERNANCE_VIEW``，写（重试）用 ``DATA_GOVERNANCE_ADMIN``。
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.platform.task_models import (
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    BackgroundTask,
)
from hris.modules.platform.task_schemas import (
    BackgroundTaskListResponse,
    BackgroundTaskResponse,
)


router = APIRouter(prefix="/api/v1/governance/tasks", tags=["phase-1-data-governance"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
TaskViewer = Annotated[
    UserAccount,
    Depends(require_permission("DATA_GOVERNANCE_VIEW")),
]
TaskAdmin = Annotated[
    UserAccount,
    Depends(require_permission("DATA_GOVERNANCE_ADMIN")),
]


@router.get("", response_model=BackgroundTaskListResponse)
@router.get("/", response_model=BackgroundTaskListResponse, include_in_schema=False)
async def list_background_tasks(
    db: DbSession,
    user: TaskViewer,
    task_type: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> BackgroundTaskListResponse:
    """按任务类型与状态分页查询后台任务。"""

    filters = []
    if task_type is not None:
        filters.append(BackgroundTask.task_type == task_type)
    if status is not None:
        filters.append(BackgroundTask.status == status)

    total = await db.scalar(
        select(func.count()).select_from(BackgroundTask).where(*filters)
    )
    rows = (
        await db.scalars(
            select(BackgroundTask)
            .where(*filters)
            .order_by(BackgroundTask.created_at.desc(), BackgroundTask.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return BackgroundTaskListResponse(
        items=[BackgroundTaskResponse.model_validate(row) for row in rows],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=BackgroundTaskResponse)
async def get_background_task(
    task_id: UUID,
    db: DbSession,
    user: TaskViewer,
) -> BackgroundTaskResponse:
    """返回一条后台任务的全部字段。"""

    task = await db.get(BackgroundTask, task_id)
    if task is None:
        raise ApiError(
            status_code=404,
            code="BACKGROUND_TASK_NOT_FOUND",
            message="后台任务不存在",
        )
    return BackgroundTaskResponse.model_validate(task)


@router.post("/{task_id}/retry", response_model=BackgroundTaskResponse)
async def retry_background_task(
    task_id: UUID,
    db: DbSession,
    user: TaskAdmin,
) -> BackgroundTaskResponse:
    """人工重试一条失败的任务。

    只有 ``failed`` 状态的任务可以重试：成功或仍在执行的任务重复重试没有意义，
    直接返回 409，避免把已完成的动作重复触发。
    """

    task = await db.get(BackgroundTask, task_id)
    if task is None:
        raise ApiError(
            status_code=404,
            code="BACKGROUND_TASK_NOT_FOUND",
            message="后台任务不存在",
        )
    if task.status != TASK_STATUS_FAILED:
        raise ApiError(
            status_code=409,
            code="BACKGROUND_TASK_NOT_RETRYABLE",
            message="只有失败状态的后台任务可以重试",
        )

    task.status = TASK_STATUS_PENDING
    task.attempts = 0
    task.next_attempt_at = datetime.now(UTC)
    task.error_code = None
    task.finished_at = None
    task.lease_owner = None
    task.lease_expires_at = None
    task.started_at = None
    await db.flush()
    # Requirement: D-110 — ``updated_at`` 带服务端 onupdate，更新后会被标记为过期；
    # 直接序列化会触发同步上下文里的懒加载，因此先刷新再组装响应。
    await db.refresh(task)
    return BackgroundTaskResponse.model_validate(task)

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""批量异动（方案制）的 HTTP 接口。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.batch_change_models import BATCH_CHANGE_STATUSES
from hris.modules.workforce.batch_change_schemas import (
    BatchChangeCreate,
    BatchChangeDetailResponse,
    BatchChangeLineResponse,
    BatchChangeLinesCreate,
    BatchChangeLinesResponse,
    BatchChangeListResponse,
    BatchChangeSubmit,
    BatchChangeSummaryResponse,
)
from hris.modules.workforce.batch_change_service import BatchChangeService


router = APIRouter(
    prefix="/api/v1/workforce",
    tags=["phase-1-workforce-batch-changes"],
)
DbSession = Annotated[AsyncSession, Depends(get_db)]
# Requirement: HR-BATCH-006 — 批量异动统一按生命周期管理员权限开放。
AdminUser = Annotated[UserAccount, Depends(require_permission("LIFECYCLE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> BatchChangeService:
    return BatchChangeService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/batch-changes",
    response_model=BatchChangeSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch_change(
    payload: BatchChangeCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> BatchChangeSummaryResponse:
    # Requirement: HR-BATCH-002 — 新建方案一律是草稿态。
    batch = await service(db, user, request).create_batch(payload)
    return BatchChangeSummaryResponse.model_validate(batch)


@router.get("/batch-changes", response_model=BatchChangeListResponse)
async def list_batch_changes(
    request: Request,
    db: DbSession,
    user: AdminUser,
    batch_status: str | None = Query(default=None, alias="status", max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> BatchChangeListResponse:
    if batch_status is not None and batch_status not in BATCH_CHANGE_STATUSES:
        raise ApiError(
            status_code=422,
            code="BATCH_CHANGE_STATUS_INVALID",
            message="方案状态筛选值不合法",
        )
    items, total = await service(db, user, request).list_batches(
        status=batch_status,
        page=page,
        page_size=page_size,
    )
    return BatchChangeListResponse(
        items=[BatchChangeSummaryResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/batch-changes/{batch_id}", response_model=BatchChangeDetailResponse)
async def get_batch_change(
    batch_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> BatchChangeDetailResponse:
    batch_service = service(db, user, request)
    batch = await batch_service.get_batch(batch_id)
    lines = await batch_service.list_lines(batch.id)
    return BatchChangeDetailResponse(
        **BatchChangeSummaryResponse.model_validate(batch).model_dump(),
        lines=[BatchChangeLineResponse.model_validate(line) for line in lines],
    )


@router.post(
    "/batch-changes/{batch_id}/lines",
    response_model=BatchChangeLinesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_batch_change_lines(
    batch_id: UUID,
    payload: BatchChangeLinesCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> BatchChangeLinesResponse:
    # Requirement: HR-BATCH-001 — 单次可追加多条明细，整批受 1000 条上限约束。
    batch, created, skipped = await service(db, user, request).append_lines(
        batch_id,
        payload,
    )
    return BatchChangeLinesResponse(
        batch=BatchChangeSummaryResponse.model_validate(batch),
        created=[BatchChangeLineResponse.model_validate(line) for line in created],
        skipped=[BatchChangeLineResponse.model_validate(line) for line in skipped],
    )


@router.delete("/batch-changes/{batch_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_batch_change_line(
    batch_id: UUID,
    line_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> Response:
    # Requirement: HR-BATCH-002 — 明细只在草稿态可删。
    await service(db, user, request).remove_line(batch_id, line_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/batch-changes/{batch_id}/submit", response_model=BatchChangeSummaryResponse)
async def submit_batch_change(
    batch_id: UUID,
    payload: BatchChangeSubmit,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> BatchChangeSummaryResponse:
    # Requirement: HR-BATCH-003 — 整批提交只产生一个流程实例，全部明细共享它。
    batch = await service(db, user, request).submit_batch(batch_id, payload)
    return BatchChangeSummaryResponse.model_validate(batch)

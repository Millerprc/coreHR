# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""人员级兼岗（concurrent position）接口。

Requirement: D-104 — 兼岗以人员级组织关系为唯一权威载体，
本组端点是兼岗的读写入口；读取端点不再以 employment 级任职为兼岗来源。
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_any_permission, require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.concurrent_positions_service import (
    CHANGE_REASON_MAX_LENGTH,
    ConcurrentPositionService,
)


router = APIRouter(prefix="/api/v1/workforce", tags=["phase-1-workforce-concurrent-positions"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
# Requirement: P-14 — 写端点（新建兼岗、结束兼岗）权限一个字都不放宽，仍要求 WORKFORCE_ADMIN。
AdminUser = Annotated[UserAccount, Depends(require_permission("WORKFORCE_ADMIN"))]
# Requirement: P-14 — 读端点放宽，符合「读宽写窄」。
# 兼岗既是人员档案的一部分，也是组织关系的一部分，因此放行
# ORGANIZATION_VIEW（组织查看者）与 PERSON_VIEW（人员档案查看者），
# 并集语义保证持有 WORKFORCE_ADMIN 的角色不会因为放宽而失去读取能力。
ViewerUser = Annotated[
    UserAccount,
    Depends(require_any_permission("ORGANIZATION_VIEW", "PERSON_VIEW", "WORKFORCE_ADMIN")),
]


class ConcurrentPositionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    person_id: UUID
    organization_id: UUID
    job_id: UUID | None = None
    effective_from: date
    effective_to: date | None = None
    change_reason: str = Field(min_length=1, max_length=CHANGE_REASON_MAX_LENGTH)


class ConcurrentPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    person_name: str | None
    organization_id: UUID
    organization_name: str | None
    job_id: UUID | None
    job_name: str | None
    relation_type: str
    effective_from: date
    effective_to: date | None
    change_reason: str | None


class ConcurrentPositionPage(BaseModel):
    items: list[ConcurrentPositionResponse]
    total: int
    page: int
    page_size: int


def service(db: AsyncSession, user: UserAccount, request: Request) -> ConcurrentPositionService:
    return ConcurrentPositionService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/concurrent-positions",
    response_model=ConcurrentPositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_concurrent_position(
    payload: ConcurrentPositionCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ConcurrentPositionResponse:
    # Requirement: D-104 — 新建兼岗写人员级组织关系，不再写 employment 级任职。
    record = await service(db, user, request).create_concurrent_position(
        person_id=payload.person_id,
        organization_id=payload.organization_id,
        job_id=payload.job_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        change_reason=payload.change_reason,
    )
    return ConcurrentPositionResponse.model_validate(record)


@router.get("/concurrent-positions", response_model=ConcurrentPositionPage)
async def list_concurrent_positions(
    request: Request,
    db: DbSession,
    user: ViewerUser,
    effective_at: date | None = Query(default=None),
    person_id: UUID | None = Query(default=None),
    organization_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> ConcurrentPositionPage:
    items, total = await service(db, user, request).list_concurrent_positions(
        effective_at=effective_at,
        person_id=person_id,
        organization_id=organization_id,
        page=page,
        page_size=page_size,
    )
    return ConcurrentPositionPage(
        items=[ConcurrentPositionResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/persons/{person_id}/concurrent-positions",
    response_model=list[ConcurrentPositionResponse],
)
async def list_person_concurrent_positions(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: ViewerUser,
    effective_at: date | None = Query(default=None),
) -> list[ConcurrentPositionResponse]:
    # Requirement: D-104 — 员工档案的兼岗只读视图，来源是人员级组织关系。
    items = await service(db, user, request).list_person_concurrent_positions(
        person_id=person_id,
        effective_at=effective_at,
    )
    return [ConcurrentPositionResponse.model_validate(item) for item in items]


@router.delete(
    "/concurrent-positions/{relation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def end_concurrent_position(
    relation_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> Response:
    # Requirement: D-104 — 结束兼岗关闭人员级关系的生效区间，历史记录保留。
    await service(db, user, request).end_concurrent_position(relation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_any_permission, require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.reporting_service import (
    ReportingRelationService,
)


router = APIRouter(prefix="/api/v1/workforce", tags=["phase-1-workforce-reporting"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
# Requirement: P-14 — 写端点（新增汇报关系、结束汇报关系）权限一个字都不放宽，仍要求 WORKFORCE_ADMIN。
AdminUser = Annotated[UserAccount, Depends(require_permission("WORKFORCE_ADMIN"))]
# Requirement: P-14 — 读端点放宽到 ORGANIZATION_VIEW，符合「读宽写窄」。
# 并集语义：持有 WORKFORCE_ADMIN 的角色（编制管理员、SSC 管理员）不会因为放宽而失去读取能力。
ViewerUser = Annotated[
    UserAccount,
    Depends(require_any_permission("ORGANIZATION_VIEW", "WORKFORCE_ADMIN")),
]


class ReportingRelationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    manager_person_id: UUID
    subordinate_person_id: UUID
    relation_type: str = Field(min_length=1, max_length=20)
    effective_from: date
    effective_to: date | None = None


class ReportingRelationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    manager_person_id: UUID
    manager_name: str | None
    subordinate_person_id: UUID
    subordinate_name: str | None
    relation_type: str
    effective_from: date
    effective_to: date | None


class ReportingRelationPage(BaseModel):
    items: list[ReportingRelationResponse]
    total: int
    page: int
    page_size: int


def service(db: AsyncSession, user: UserAccount, request: Request) -> ReportingRelationService:
    return ReportingRelationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/reporting-relations",
    response_model=ReportingRelationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reporting_relation(
    payload: ReportingRelationCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> ReportingRelationResponse:
    record = await service(db, user, request).create_relation(
        manager_person_id=payload.manager_person_id,
        subordinate_person_id=payload.subordinate_person_id,
        relation_type=payload.relation_type,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    return ReportingRelationResponse.model_validate(record)


@router.get("/reporting-relations", response_model=ReportingRelationPage)
async def list_reporting_relations(
    request: Request,
    db: DbSession,
    user: ViewerUser,
    effective_at: date | None = Query(default=None),
    manager_person_id: UUID | None = Query(default=None),
    subordinate_person_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> ReportingRelationPage:
    items, total = await service(db, user, request).list_relations(
        effective_at=effective_at,
        manager_person_id=manager_person_id,
        subordinate_person_id=subordinate_person_id,
        page=page,
        page_size=page_size,
    )
    return ReportingRelationPage(
        items=[ReportingRelationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/reporting-relations/{relation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def end_reporting_relation(
    relation_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> Response:
    await service(db, user, request).end_relation(relation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

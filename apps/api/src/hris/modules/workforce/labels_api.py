# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.label_library import (
    LabelLibraryListResponse,
    LabelLibraryService,
)
from hris.modules.workforce.labels_service import (
    LabelTypeListResponse,
    PageResponse,
    PersonLabelBatchCreate,
    PersonLabelBatchResponse,
    PersonLabelCreate,
    PersonLabelListResponse,
    PersonLabelResponse,
    PersonLabelService,
)


router = APIRouter(prefix="/api/v1/workforce", tags=["phase-1-workforce-labels"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("WORKFORCE_ADMIN"))]


def service(db: AsyncSession, user: UserAccount, request: Request) -> PersonLabelService:
    return PersonLabelService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.get(
    "/persons/{person_id}/labels",
    response_model=PersonLabelListResponse,
)
async def list_person_labels(
    person_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
    effective_at: date | None = Query(default=None),
) -> PersonLabelListResponse:
    # Requirement: HR-LABEL-006 — 未指定查询日期时按业务当天判断标签是否有效。
    label_service = service(db, user, request)
    items = await label_service.list_person_labels(
        person_id,
        effective_at or label_service.business_date(),
    )
    return PersonLabelListResponse(
        items=[PersonLabelResponse.model_validate(item).model_dump() for item in items],
        total=len(items),
    )


@router.get("/labels", response_model=PageResponse)
async def list_labels(
    request: Request,
    db: DbSession,
    user: AdminUser,
    label_type: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=80),
    person_id: UUID | None = Query(default=None),
    include_expired: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> PageResponse:
    # Requirement: HR-LABEL-007 — 全局标签查询默认只返回当前有效标签。
    items, total = await service(db, user, request).list_labels(
        label_type=label_type,
        source=source,
        person_id=person_id,
        include_expired=include_expired,
        page=page,
        page_size=page_size,
    )
    return PageResponse(
        items=[PersonLabelResponse.model_validate(item).model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/persons/{person_id}/labels",
    response_model=PersonLabelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_person_label(
    person_id: UUID,
    payload: PersonLabelCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> PersonLabelResponse:
    # Requirement: HR-LABEL-001 — 标签必须绑定已存在的人员档案。
    label = await service(db, user, request).create_label(person_id, payload)
    return PersonLabelResponse.model_validate(label)


@router.post(
    "/persons/{person_id}/labels/batch",
    response_model=PersonLabelBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_person_labels_batch(
    person_id: UUID,
    payload: PersonLabelBatchCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> PersonLabelBatchResponse:
    # Requirement: HR-LABEL-015 — 从标签库多选的标签整批原子写入。
    labels = await service(db, user, request).create_labels_batch(person_id, payload)
    return PersonLabelBatchResponse(
        created=[PersonLabelResponse.model_validate(label) for label in labels]
    )


@router.delete("/person-labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_person_label(
    label_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> Response:
    # Requirement: HR-LABEL-008 — 删除标签采用软结束，结束日期记为业务当天。
    await service(db, user, request).end_label(label_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/label-types", response_model=LabelTypeListResponse)
async def list_label_types(
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LabelTypeListResponse:
    # Requirement: HR-LABEL-009 — 标签类型按现有数据聚合并按有效数量倒序。
    items = await service(db, user, request).list_label_types()
    return LabelTypeListResponse(items=items)


@router.get("/label-library", response_model=LabelLibraryListResponse)
async def list_label_library(
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> LabelLibraryListResponse:
    # Requirement: HR-LABEL-011 — 标签库读取沿用 workforce 域的权限口径，不复用配置模块权限。
    items = await LabelLibraryService(db).list_types()
    return LabelLibraryListResponse(items=items)

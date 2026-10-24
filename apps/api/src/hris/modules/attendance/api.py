# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.attendance.schemas import (
    AttendanceRuleSetCreate,
    AttendanceRuleSetListResponse,
    AttendanceRuleSetResponse,
    AttendanceRuleSetUpdate,
    AttendanceRuleSetVersionCreate,
)
from hris.modules.attendance.service import AttendanceService
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/attendance", tags=["phase-3-attendance"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[UserAccount, Depends(require_permission("ATTENDANCE_ADMIN"))]
# Requirement: C5 — 考勤高风险动作拆独立权限码。
# 依据：docs/review/D-考勤-待确认-决策-文档规范.md §8「权限与审计」（14.md:185 行，P0）。
# 「规则发布」是 7 类高风险动作之一：规则集发布后立即生效并归档旧版，会改变后续日报/月报口径，
# 因此改用独立权限码 ATTENDANCE_RULE_PUBLISH，不再与普通考勤操作共用 ATTENDANCE_ADMIN。
# 其余规则集动作（建草稿 / 改草稿 / 建版本 / 查询）仍属普通考勤操作，保持 ATTENDANCE_ADMIN。
RulePublishUser = Annotated[
    UserAccount, Depends(require_permission("ATTENDANCE_RULE_PUBLISH"))
]


def service(db: AsyncSession, user: UserAccount, request: Request) -> AttendanceService:
    return AttendanceService(db, actor_id=user.id, trace_id=str(request.state.trace_id))


@router.post(
    "/rule-sets",
    response_model=AttendanceRuleSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attendance_rule_set(
    payload: AttendanceRuleSetCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendanceRuleSetResponse:
    result = await service(db, user, request).create_rule_set(payload)
    return AttendanceRuleSetResponse.model_validate(result)


@router.get("/rule-sets", response_model=AttendanceRuleSetListResponse)
async def list_attendance_rule_sets(
    request: Request,
    db: DbSession,
    user: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AttendanceRuleSetListResponse:
    items, total = await service(db, user, request).list_rule_sets(
        limit=limit,
        offset=offset,
    )
    return AttendanceRuleSetListResponse(
        items=[AttendanceRuleSetResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/rule-sets/{rule_set_id}", response_model=AttendanceRuleSetResponse)
async def get_attendance_rule_set(
    rule_set_id: UUID,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendanceRuleSetResponse:
    return AttendanceRuleSetResponse.model_validate(
        await service(db, user, request).get_rule_set(rule_set_id)
    )


@router.patch("/rule-sets/{rule_set_id}", response_model=AttendanceRuleSetResponse)
async def update_attendance_rule_set(
    rule_set_id: UUID,
    payload: AttendanceRuleSetUpdate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendanceRuleSetResponse:
    return AttendanceRuleSetResponse.model_validate(
        await service(db, user, request).update_rule_set(rule_set_id, payload)
    )


@router.post("/rule-sets/{rule_set_id}/versions", response_model=AttendanceRuleSetResponse, status_code=201)
async def create_attendance_rule_set_version(
    rule_set_id: UUID,
    payload: AttendanceRuleSetVersionCreate,
    request: Request,
    db: DbSession,
    user: AdminUser,
) -> AttendanceRuleSetResponse:
    return AttendanceRuleSetResponse.model_validate(
        await service(db, user, request).create_rule_set_version(rule_set_id, payload)
    )


@router.post("/rule-sets/{rule_set_id}/publish", response_model=AttendanceRuleSetResponse)
async def publish_attendance_rule_set(
    rule_set_id: UUID,
    request: Request,
    db: DbSession,
    user: RulePublishUser,
) -> AttendanceRuleSetResponse:
    return AttendanceRuleSetResponse.model_validate(
        await service(db, user, request).publish_rule_set(rule_set_id)
    )

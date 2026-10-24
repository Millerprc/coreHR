# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""HTTP endpoints for maintaining performance OKR definitions."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.performance.schemas import (
    PerformanceCycleCreate,
    PerformanceCycleDetailResponse,
    PerformanceCyclePage,
    PerformanceCycleResponse,
    PerformanceCycleUpdate,
    PerformanceKeyResultCreate,
    PerformanceKeyResultResponse,
    PerformanceKeyResultUpdate,
    PerformanceObjectiveCreate,
    PerformanceObjectiveListResponse,
    PerformanceObjectiveResponse,
    PerformanceObjectiveUpdate,
    PerformanceScorecardResponse,
)
from hris.modules.performance.service import PerformanceService
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/performance", tags=["phase-1-performance-okr"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
# Requirement: HR-PERF-010 — 绩效 OKR 的读写统一使用既有权限码 LIFECYCLE_ADMIN。
PerformanceUser = Annotated[
    UserAccount,
    Depends(require_permission("LIFECYCLE_ADMIN")),
]


def service(db: AsyncSession, user: UserAccount, request: Request) -> PerformanceService:
    return PerformanceService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/cycles",
    response_model=PerformanceCycleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cycle(
    payload: PerformanceCycleCreate,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceCycleResponse:
    # Requirement: HR-PERF-001 — 新建绩效周期默认处于草稿状态。
    cycle = await service(db, user, request).create_cycle(payload)
    return PerformanceCycleResponse.model_validate(cycle)


@router.get("/cycles", response_model=PerformanceCyclePage)
async def list_cycles(
    request: Request,
    db: DbSession,
    user: PerformanceUser,
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    cycle_type: str | None = Query(default=None, max_length=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> PerformanceCyclePage:
    # Requirement: HR-PERF-001 — 周期列表支持状态与类型筛选并分页返回。
    items, total = await service(db, user, request).list_cycles(
        status=status_filter,
        cycle_type=cycle_type,
        page=page,
        page_size=page_size,
    )
    return PerformanceCyclePage(
        items=[PerformanceCycleResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cycles/{cycle_id}", response_model=PerformanceCycleDetailResponse)
async def get_cycle(
    cycle_id: UUID,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceCycleDetailResponse:
    # Requirement: HR-PERF-001 — 周期详情附带目标与关键结果统计。
    return await service(db, user, request).get_cycle_detail(cycle_id)


@router.patch("/cycles/{cycle_id}", response_model=PerformanceCycleResponse)
async def update_cycle(
    cycle_id: UUID,
    payload: PerformanceCycleUpdate,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceCycleResponse:
    # Requirement: HR-PERF-002 — 周期状态只允许沿草稿→进行中→已关闭方向流转。
    cycle = await service(db, user, request).update_cycle(cycle_id, payload)
    return PerformanceCycleResponse.model_validate(cycle)


@router.post(
    "/cycles/{cycle_id}/objectives",
    response_model=PerformanceObjectiveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_objective(
    cycle_id: UUID,
    payload: PerformanceObjectiveCreate,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceObjectiveResponse:
    # Requirement: HR-PERF-005 — 建目标时校验同一周期同一人的权重之和不超过 100。
    objective = await service(db, user, request).create_objective(cycle_id, payload)
    return await service(db, user, request).build_objective_response(objective)


@router.get(
    "/cycles/{cycle_id}/objectives",
    response_model=PerformanceObjectiveListResponse,
)
async def list_objectives(
    cycle_id: UUID,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
    person_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    include_archived: bool = Query(default=False),
    group_by_person: bool = Query(default=False),
) -> PerformanceObjectiveListResponse:
    # Requirement: HR-PERF-008 — 目标列表可按人筛选，并可按人聚合返回权重合计。
    return await service(db, user, request).list_objectives(
        cycle_id,
        person_id=person_id,
        status=status_filter,
        include_archived=include_archived,
        group_by_person=group_by_person,
    )


@router.patch(
    "/objectives/{objective_id}",
    response_model=PerformanceObjectiveResponse,
)
async def update_objective(
    objective_id: UUID,
    payload: PerformanceObjectiveUpdate,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceObjectiveResponse:
    # Requirement: HR-PERF-013 — 权重变更后重新校验周期内同一人权重之和。
    objective = await service(db, user, request).update_objective(objective_id, payload)
    return await service(db, user, request).build_objective_response(objective)


@router.post(
    "/objectives/{objective_id}/key-results",
    response_model=PerformanceKeyResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_key_result(
    objective_id: UUID,
    payload: PerformanceKeyResultCreate,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceKeyResultResponse:
    # Requirement: HR-PERF-006 — 建关键结果时校验同一目标下权重之和不超过 100。
    key_result = await service(db, user, request).create_key_result(
        objective_id, payload
    )
    return PerformanceKeyResultResponse.model_validate(key_result)


@router.patch(
    "/key-results/{key_result_id}",
    response_model=PerformanceKeyResultResponse,
)
async def update_key_result(
    key_result_id: UUID,
    payload: PerformanceKeyResultUpdate,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceKeyResultResponse:
    # Requirement: HR-PERF-007 — 写入得分时校验 0-100 区间，未评分保持为空。
    key_result = await service(db, user, request).update_key_result(
        key_result_id, payload
    )
    return PerformanceKeyResultResponse.model_validate(key_result)


@router.delete(
    "/key-results/{key_result_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_key_result(
    key_result_id: UUID,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> Response:
    # Requirement: HR-PERF-014 — 删除关键结果为物理删除，并写入审计日志。
    await service(db, user, request).delete_key_result(key_result_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/cycles/{cycle_id}/scorecard",
    response_model=PerformanceScorecardResponse,
)
async def get_scorecard(
    cycle_id: UUID,
    request: Request,
    db: DbSession,
    user: PerformanceUser,
) -> PerformanceScorecardResponse:
    # Requirement: HR-PERF-012 — 计分卡按人汇总，未评分项得分为 null。
    return await service(db, user, request).build_scorecard(cycle_id)

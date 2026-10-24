# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.audit_service import (
    ActionListResponse,
    AuditActorListResponse,
    AuditLogDetailResponse,
    AuditLogFilters,
    AuditLogResponse,
    AuditLogService,
    PageResponse,
)
from hris.modules.platform.dependencies import require_any_permission, require_permission
from hris.modules.platform.models import UserAccount


router = APIRouter(prefix="/api/v1/platform", tags=["platform-audit-logs"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
# Requirement: AUDIT-006 — 审计数据敏感，读取也必须持有 DATA_GOVERNANCE_ADMIN，不降级为 VIEW。
AuditLogAdmin = Annotated[
    UserAccount,
    Depends(require_permission("DATA_GOVERNANCE_ADMIN")),
]
# Requirement: P-13 — 操作人下拉是只读辅助数据源，按「读宽写窄」用治理查看权限开放；
# DATA_GOVERNANCE_ADMIN 与 DATA_GOVERNANCE_VIEW 任一命中即放行，
# 因此治理管理员与只读治理角色都能取到下拉选项，且不依赖主管理员专用的 /platform/users。
AuditActorReader = Annotated[
    UserAccount,
    Depends(require_any_permission("DATA_GOVERNANCE_VIEW", "DATA_GOVERNANCE_ADMIN")),
]


def _service(db: AsyncSession, user: UserAccount, request: Request) -> AuditLogService:
    return AuditLogService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


def _filters(
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    actor_id: UUID | None,
    action: str | None,
    object_type: str | None,
    object_id: UUID | None,
    trace_id: str | None,
) -> AuditLogFilters:
    return AuditLogFilters(
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        trace_id=trace_id,
    )


@router.get("/audit-logs", response_model=PageResponse)
async def list_audit_logs(
    db: DbSession,
    user: AuditLogAdmin,
    request: Request,
    occurred_from: datetime | None = Query(default=None),
    occurred_to: datetime | None = Query(default=None),
    actor_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None, max_length=100),
    object_type: str | None = Query(default=None, max_length=50),
    object_id: UUID | None = Query(default=None),
    trace_id: str | None = Query(default=None, max_length=100),
    # Requirement: AUDIT-011 — 分页默认第 1 页、每页 20 条，每页最多 200 条。
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> PageResponse:
    # Requirement: AUDIT-009 — 列表响应不返回 before_payload / after_payload。
    items, total = await _service(db, user, request).list_logs(
        _filters(
            occurred_from,
            occurred_to,
            actor_id,
            action,
            object_type,
            object_id,
            trace_id,
        ),
        page=page,
        page_size=page_size,
    )
    return PageResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit-logs/actions", response_model=ActionListResponse)
async def list_audit_log_actions(
    db: DbSession,
    user: AuditLogAdmin,
    request: Request,
) -> ActionListResponse:
    # Requirement: AUDIT-004 — action 聚合用于筛选下拉，条目多的排在前面。
    items = await _service(db, user, request).action_counts()
    return ActionListResponse(items=items)


@router.get("/audit/actors", response_model=AuditActorListResponse)
async def list_audit_actors(
    db: DbSession,
    user: AuditActorReader,
    request: Request,
) -> AuditActorListResponse:
    # Requirement: P-13 — 审计页「操作人」下拉专用只读端点：
    # 只返回 id、display_name、username，按 display_name 升序；
    # 不返回邮箱、手机号等个人联系方式，也不返回账号状态与角色。
    items = await _service(db, user, request).list_actors()
    return AuditActorListResponse(items=items, total=len(items))


@router.get(
    "/audit-logs/export",
    response_class=Response,
    responses={
        200: {
            "content": {"text/csv": {"schema": {"type": "string"}}},
            "description": "审计日志 CSV 附件",
        }
    },
)
async def export_audit_logs(
    db: DbSession,
    user: AuditLogAdmin,
    request: Request,
    occurred_from: datetime | None = Query(default=None),
    occurred_to: datetime | None = Query(default=None),
    actor_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None, max_length=100),
    object_type: str | None = Query(default=None, max_length=50),
    object_id: UUID | None = Query(default=None),
    trace_id: str | None = Query(default=None, max_length=100),
) -> Response:
    # Requirement: AUDIT-007 — 导出沿用列表的全部筛选条件，但不分页。
    content, filename, row_count = await _service(db, user, request).export_csv(
        _filters(
            occurred_from,
            occurred_to,
            actor_id,
            action,
            object_type,
            object_id,
            trace_id,
        )
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Row-Count": str(row_count),
        },
    )


@router.get("/audit-logs/{audit_log_id}", response_model=AuditLogDetailResponse)
async def get_audit_log(
    audit_log_id: UUID,
    db: DbSession,
    user: AuditLogAdmin,
    request: Request,
) -> AuditLogDetailResponse:
    # Requirement: AUDIT-009 — payload 只在单条详情端点返回，该端点独立鉴权。
    detail = await _service(db, user, request).get_log(audit_log_id)
    return AuditLogDetailResponse(
        id=detail.id,
        occurred_at=detail.occurred_at,
        actor_id=detail.actor_id,
        actor_name=detail.actor_name,
        trace_id=detail.trace_id,
        action=detail.action,
        object_type=detail.object_type,
        object_id=detail.object_id,
        reason=detail.reason,
        source=detail.source,
        before_payload=detail.before_payload,
        after_payload=detail.after_payload,
    )

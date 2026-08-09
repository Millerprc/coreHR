from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.concurrency import VersionCommand
from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.workforce.organization_schemas import (
    BpMembershipCreate,
    BpMembershipView,
    BpServiceScopeSet,
    OrganizationCreate,
    OrganizationEventView,
    OrganizationLeaderSet,
    OrganizationLegalEntitySet,
    OrganizationRelationsView,
    OrganizationTreeNode,
    OrganizationTypeCreate,
    OrganizationTypeUpdate,
    OrganizationTypeView,
    OrganizationVersionCreate,
    OrganizationView,
    RelationSetView,
)
from hris.modules.workforce.organization_service import OrganizationService


router = APIRouter(tags=["phase-1-organization"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
OrganizationViewer = Annotated[
    UserAccount,
    Depends(require_permission("ORGANIZATION_VIEW")),
]
OrganizationAdmin = Annotated[
    UserAccount,
    Depends(require_permission("ORGANIZATION_ADMIN")),
]
OrganizationEventOperator = Annotated[
    UserAccount,
    Depends(require_permission("ORGANIZATION_EVENT_APPLY")),
]


def service(
    db: AsyncSession,
    user: UserAccount,
    request: Request,
) -> OrganizationService:
    return OrganizationService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.post(
    "/api/v1/organization-types",
    response_model=OrganizationTypeView,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_type(
    payload: OrganizationTypeCreate,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> OrganizationTypeView:
    return await service(db, user, request).create_type(payload)


@router.get(
    "/api/v1/organization-types",
    response_model=list[OrganizationTypeView],
)
async def list_organization_types(
    request: Request,
    db: DbSession,
    user: OrganizationViewer,
    active_only: bool = Query(default=False),
) -> list[OrganizationTypeView]:
    return await service(db, user, request).list_types(active_only)


@router.patch(
    "/api/v1/organization-types/{type_id}",
    response_model=OrganizationTypeView,
)
async def update_organization_type(
    type_id: UUID,
    payload: OrganizationTypeUpdate,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> OrganizationTypeView:
    return await service(db, user, request).update_type(type_id, payload)


@router.post(
    "/api/v1/organizations",
    response_model=OrganizationView,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    payload: OrganizationCreate,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> OrganizationView:
    return await service(db, user, request).create(payload)


@router.get(
    "/api/v1/organizations/tree",
    response_model=list[OrganizationTreeNode],
)
async def current_organization_tree(
    request: Request,
    db: DbSession,
    user: OrganizationViewer,
) -> list[OrganizationTreeNode]:
    if "effective_at" in request.query_params:
        raise ApiError(
            status_code=422,
            code="CURRENT_TREE_ONLY",
            message="组织树仅展示当前有效结构，请在组织详情查看历史和未来版本",
        )
    return await service(db, user, request).get_current_tree()


@router.get(
    "/api/v1/organizations/{organization_id}",
    response_model=OrganizationView,
)
async def get_organization(
    organization_id: UUID,
    request: Request,
    db: DbSession,
    user: OrganizationViewer,
    effective_at: date | None = Query(default=None),
) -> OrganizationView:
    organization_service = service(db, user, request)
    return await organization_service.get_as_of(
        organization_id,
        effective_at or organization_service.business_date(),
    )


@router.post(
    "/api/v1/organizations/{organization_id}/versions",
    response_model=OrganizationEventView,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_organization_version(
    organization_id: UUID,
    payload: OrganizationVersionCreate,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> OrganizationEventView:
    return await service(db, user, request).schedule_version(
        organization_id,
        payload,
    )


@router.post(
    "/api/v1/organization-events/{event_id}/cancel",
    response_model=OrganizationEventView,
)
async def cancel_organization_event(
    event_id: UUID,
    command: VersionCommand,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> OrganizationEventView:
    return await service(db, user, request).cancel_event(event_id, command)


@router.post("/api/v1/organization-events/apply-due")
async def apply_due_organization_events(
    request: Request,
    db: DbSession,
    user: OrganizationEventOperator,
    business_date: date | None = Query(default=None),
) -> dict[str, object]:
    organization_service = service(db, user, request)
    effective_date = business_date or organization_service.business_date()
    applied_count = await organization_service.apply_due_events(effective_date)
    return {
        "business_date": effective_date.isoformat(),
        "applied_count": applied_count,
    }


@router.put(
    "/api/v1/organizations/{organization_id}/legal-entities",
    response_model=RelationSetView,
)
async def set_organization_legal_entities(
    organization_id: UUID,
    payload: OrganizationLegalEntitySet,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> RelationSetView:
    return await service(db, user, request).set_legal_entities(
        organization_id,
        payload,
    )


@router.put(
    "/api/v1/organizations/{organization_id}/leaders",
    response_model=RelationSetView,
)
async def set_organization_leaders(
    organization_id: UUID,
    payload: OrganizationLeaderSet,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> RelationSetView:
    return await service(db, user, request).set_leaders(
        organization_id,
        payload,
    )


@router.post(
    "/api/v1/bp-memberships",
    response_model=BpMembershipView,
    status_code=status.HTTP_201_CREATED,
)
async def create_bp_membership(
    payload: BpMembershipCreate,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> BpMembershipView:
    return await service(db, user, request).create_bp_membership(payload)


@router.put(
    "/api/v1/bp-memberships/{membership_id}/service-scopes",
    response_model=BpMembershipView,
)
async def set_bp_service_scopes(
    membership_id: UUID,
    payload: BpServiceScopeSet,
    request: Request,
    db: DbSession,
    user: OrganizationAdmin,
) -> BpMembershipView:
    return await service(db, user, request).set_bp_service_scopes(
        membership_id,
        payload,
    )


@router.get(
    "/api/v1/organizations/{organization_id}/relations",
    response_model=OrganizationRelationsView,
)
async def get_organization_relations(
    organization_id: UUID,
    request: Request,
    db: DbSession,
    user: OrganizationViewer,
    effective_at: date | None = Query(default=None),
) -> OrganizationRelationsView:
    organization_service = service(db, user, request)
    return await organization_service.get_relations(
        organization_id,
        effective_at or organization_service.business_date(),
    )

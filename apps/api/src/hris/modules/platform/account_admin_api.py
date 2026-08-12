from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.modules.platform.account_admin_service import AccountAdminService
from hris.modules.platform.dependencies import require_permission
from hris.modules.platform.models import UserAccount
from hris.modules.platform.schemas import (
    RoleListResponse,
    RoleResponse,
    UserAdminCreate,
    UserAdminListResponse,
    UserAdminResponse,
    UserAdminUpdate,
)


router = APIRouter(prefix="/api/v1/platform", tags=["platform-account-admin"])
DbSession = Annotated[AsyncSession, Depends(get_db)]
SystemAdmin = Annotated[UserAccount, Depends(require_permission("*"))]


def service(
    db: AsyncSession,
    user: UserAccount,
    request: Request,
) -> AccountAdminService:
    return AccountAdminService(
        db,
        actor_id=user.id,
        trace_id=str(request.state.trace_id),
    )


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    request: Request,
    db: DbSession,
    user: SystemAdmin,
) -> RoleListResponse:
    items = await service(db, user, request).list_roles()
    return RoleListResponse(items=[RoleResponse.model_validate(item) for item in items])


@router.get("/users", response_model=UserAdminListResponse)
async def list_users(
    request: Request,
    db: DbSession,
    user: SystemAdmin,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserAdminListResponse:
    items, total = await service(db, user, request).list_users(
        limit=limit,
        offset=offset,
    )
    return UserAdminListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/users", response_model=UserAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserAdminCreate,
    request: Request,
    db: DbSession,
    user: SystemAdmin,
) -> UserAdminResponse:
    return await service(db, user, request).create_user(payload)


@router.patch("/users/{user_id}", response_model=UserAdminResponse)
async def update_user(
    user_id: UUID,
    payload: UserAdminUpdate,
    request: Request,
    db: DbSession,
    user: SystemAdmin,
) -> UserAdminResponse:
    return await service(db, user, request).update_user(user_id, payload)

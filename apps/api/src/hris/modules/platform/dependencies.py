from datetime import UTC, datetime
from typing import Annotated, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.database import get_db
from hris.core.errors import ApiError
from hris.modules.platform.models import (
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.security import token_digest


bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


async def get_current_session(
    credentials: BearerCredentials,
    db: DbSession,
) -> tuple[UserAccount, UserSession]:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise ApiError(status_code=401, code="AUTHENTICATION_REQUIRED", message="需要登录")
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(UserAccount, UserSession)
            .join(UserSession, UserSession.user_id == UserAccount.id)
            .where(
                UserSession.token_hash == token_digest(credentials.credentials),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserAccount.status == "active",
            )
        )
    ).one_or_none()
    if row is None:
        raise ApiError(status_code=401, code="SESSION_INVALID", message="登录状态无效或已过期")
    user, session = row
    session.last_seen_at = now
    return user, session


CurrentSession = Annotated[tuple[UserAccount, UserSession], Depends(get_current_session)]


def require_permission(permission_code: str) -> Callable[..., UserAccount]:
    async def dependency(current: CurrentSession, db: DbSession) -> UserAccount:
        user, _ = current
        permission_codes = set(
            (
                await db.scalars(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .join(Role, Role.id == RolePermission.role_id)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user.id, Role.is_active.is_(True))
                )
            ).all()
        )
        if "*" not in permission_codes and permission_code not in permission_codes:
            raise ApiError(status_code=403, code="PERMISSION_DENIED", message="没有执行此操作的权限")
        return user

    return dependency

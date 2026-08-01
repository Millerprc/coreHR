import hmac
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import (
    Permission,
    Role,
    RolePermission,
    UserAccount,
    UserRole,
    UserSession,
)
from hris.modules.platform.schemas import (
    BootstrapAdminRequest,
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from hris.modules.platform.security import (
    hash_password,
    new_access_token,
    token_digest,
    verify_password,
)


ADMIN_ROLE_CODE = "SYSTEM_ADMIN"
ADMIN_PERMISSION_CODE = "*"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bootstrap_admin(self, payload: BootstrapAdminRequest) -> UserResponse:
        expected = os.getenv("COREHR_BOOTSTRAP_TOKEN", "")
        if not expected or not hmac.compare_digest(payload.bootstrap_token, expected):
            raise ApiError(status_code=403, code="BOOTSTRAP_DENIED", message="初始化凭证无效")

        user_count = await self._session.scalar(select(func.count()).select_from(UserAccount))
        if user_count:
            raise ApiError(status_code=409, code="BOOTSTRAP_ALREADY_COMPLETED", message="主管理员已初始化")

        permission = Permission(code=ADMIN_PERMISSION_CODE, name="全部权限", module_code="SYSTEM")
        role = Role(
            code=ADMIN_ROLE_CODE,
            name="主管理员",
            description="系统首个主管理员角色，可管理全部模块",
            is_system=True,
            is_active=True,
        )
        user = UserAccount(
            username=payload.username.casefold(),
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
            status="active",
            failed_attempts=0,
        )
        self._session.add_all([permission, role, user])
        await self._session.flush()
        self._session.add_all(
            [
                RolePermission(role_id=role.id, permission_id=permission.id),
                UserRole(user_id=user.id, role_id=role.id),
            ]
        )
        await self._session.flush()
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            person_id=user.person_id,
            roles=[role.code],
            permissions=[permission.code],
        )

    async def login(self, payload: LoginRequest) -> LoginResponse:
        now = datetime.now(UTC)
        user = await self._session.scalar(
            select(UserAccount).where(UserAccount.username == payload.username.casefold())
        )
        invalid = user is None or user.status != "active"
        if user is not None and user.locked_until is not None and user.locked_until > now:
            raise ApiError(status_code=423, code="ACCOUNT_LOCKED", message="账号暂时锁定")
        if invalid or user is None or not verify_password(payload.password, user.password_hash):
            if user is not None:
                user.failed_attempts += 1
                if user.failed_attempts >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                await self._session.commit()
            raise ApiError(status_code=401, code="INVALID_CREDENTIALS", message="用户名或密码错误")

        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        raw_token = new_access_token()
        expires_at = now + timedelta(hours=8)
        self._session.add(
            UserSession(
                user_id=user.id,
                token_hash=token_digest(raw_token),
                expires_at=expires_at,
                last_seen_at=now,
            )
        )
        await self._session.flush()
        profile = await self.user_profile(user)
        return LoginResponse(
            access_token=raw_token,
            expires_at=expires_at,
            user=profile,
        )

    async def user_profile(self, user: UserAccount) -> UserResponse:
        role_codes = list(
            (
                await self._session.scalars(
                    select(Role.code)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user.id, Role.is_active.is_(True))
                    .order_by(Role.code)
                )
            ).all()
        )
        permission_codes = list(
            (
                await self._session.scalars(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .join(Role, Role.id == RolePermission.role_id)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user.id, Role.is_active.is_(True))
                    .distinct()
                    .order_by(Permission.code)
                )
            ).all()
        )
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            person_id=user.person_id,
            roles=role_codes,
            permissions=permission_codes,
        )

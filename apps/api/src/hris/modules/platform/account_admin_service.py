from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.errors import ApiError
from hris.modules.platform.models import Role, UserAccount, UserRole, UserSession
from hris.modules.platform.schemas import (
    UserAdminCreate,
    UserAdminResponse,
    UserAdminUpdate,
)
from hris.modules.platform.security import hash_password
from hris.modules.workforce.models import AuditLog


SYSTEM_ADMIN_ROLE = "SYSTEM_ADMIN"


class AccountAdminService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        trace_id: str,
    ) -> None:
        self._session = session
        self._actor_id = actor_id
        self._trace_id = trace_id

    async def list_roles(self) -> list[Role]:
        return list(
            (
                await self._session.scalars(
                    select(Role).where(Role.is_active.is_(True)).order_by(Role.code)
                )
            ).all()
        )

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[UserAdminResponse], int]:
        total = int(await self._session.scalar(select(func.count()).select_from(UserAccount)) or 0)
        users = list(
            (
                await self._session.scalars(
                    select(UserAccount)
                    .order_by(UserAccount.username)
                    .limit(limit)
                    .offset(offset)
                )
            ).all()
        )
        role_rows = (
            await self._session.execute(
                select(UserRole.user_id, Role.code)
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id.in_([user.id for user in users]))
                .order_by(Role.code)
            )
        ).all() if users else []
        role_codes: dict[UUID, list[str]] = {}
        for user_id, role_code in role_rows:
            role_codes.setdefault(user_id, []).append(role_code)
        return [
            self._response(user, role_codes.get(user.id, []))
            for user in users
        ], total

    async def create_user(self, payload: UserAdminCreate) -> UserAdminResponse:
        roles = await self._roles(payload.role_codes)
        if await self._session.scalar(
            select(UserAccount.id).where(UserAccount.username == payload.username)
        ) is not None:
            raise ApiError(
                status_code=409,
                code="USER_USERNAME_EXISTS",
                message="账号已存在",
            )
        user = UserAccount(
            username=payload.username,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
            status="active",
            failed_attempts=0,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(user)
                await self._session.flush()
                self._session.add_all(
                    UserRole(user_id=user.id, role_id=role.id) for role in roles
                )
                await self._session.flush()
        except IntegrityError as error:
            raise ApiError(
                status_code=409,
                code="USER_USERNAME_EXISTS",
                message="账号已存在",
            ) from error
        self._audit(
            action="account.create",
            object_id=user.id,
            reason=payload.reason,
            before={},
            after=self._audit_payload(user, payload.role_codes),
        )
        return self._response(user, payload.role_codes)

    async def update_user(
        self,
        user_id: UUID,
        payload: UserAdminUpdate,
    ) -> UserAdminResponse:
        user = await self._session.get(UserAccount, user_id, with_for_update=True)
        if user is None:
            raise ApiError(status_code=404, code="USER_NOT_FOUND", message="账号不存在")
        before_roles = await self._user_role_codes(user.id)
        before = self._audit_payload(user, before_roles)
        target_roles = before_roles
        if payload.role_codes is not None:
            roles = await self._roles(payload.role_codes)
            target_roles = payload.role_codes
        else:
            roles = []
        target_status = payload.status or user.status
        if user.id == self._actor_id and target_status != "active":
            raise ApiError(
                status_code=409,
                code="CANNOT_DEACTIVATE_CURRENT_USER",
                message="不能停用当前登录账号",
            )
        if await self._removes_active_system_admin(
            user,
            before_roles=before_roles,
            target_roles=target_roles,
            target_status=target_status,
        ):
            raise ApiError(
                status_code=409,
                code="LAST_SYSTEM_ADMIN_REQUIRED",
                message="必须保留至少一个有效主管理员账号",
            )
        if payload.display_name is not None:
            user.display_name = payload.display_name
        user.status = target_status
        if target_status == "inactive" and before["status"] == "active":
            await self._session.execute(
                update(UserSession)
                .where(
                    UserSession.user_id == user.id,
                    UserSession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
        if payload.role_codes is not None:
            await self._session.execute(delete(UserRole).where(UserRole.user_id == user.id))
            self._session.add_all(UserRole(user_id=user.id, role_id=role.id) for role in roles)
        await self._session.flush()
        self._audit(
            action="account.update",
            object_id=user.id,
            reason=payload.reason,
            before=before,
            after=self._audit_payload(user, target_roles),
        )
        return self._response(user, target_roles)

    async def _roles(self, role_codes: list[str]) -> list[Role]:
        roles = list(
            (
                await self._session.scalars(
                    select(Role).where(
                        Role.code.in_(role_codes),
                        Role.is_active.is_(True),
                    )
                )
            ).all()
        )
        found = {role.code for role in roles}
        missing = sorted(set(role_codes) - found)
        if missing:
            raise ApiError(
                status_code=422,
                code="ROLE_NOT_AVAILABLE",
                message="角色不存在或已停用",
                details=[{"role_code": code} for code in missing],
            )
        return roles

    async def _user_role_codes(self, user_id: UUID) -> list[str]:
        return list(
            (
                await self._session.scalars(
                    select(Role.code)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user_id)
                    .order_by(Role.code)
                )
            ).all()
        )

    async def _removes_active_system_admin(
        self,
        user: UserAccount,
        *,
        before_roles: list[str],
        target_roles: list[str],
        target_status: str,
    ) -> bool:
        was_admin = user.status == "active" and SYSTEM_ADMIN_ROLE in before_roles
        remains_admin = target_status == "active" and SYSTEM_ADMIN_ROLE in target_roles
        if not was_admin or remains_admin:
            return False
        await self._session.scalar(
            select(Role.id)
            .where(Role.code == SYSTEM_ADMIN_ROLE)
            .with_for_update()
        )
        other_count = await self._session.scalar(
            select(func.count())
            .select_from(UserAccount)
            .join(UserRole, UserRole.user_id == UserAccount.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserAccount.id != user.id,
                UserAccount.status == "active",
                Role.code == SYSTEM_ADMIN_ROLE,
                Role.is_active.is_(True),
            )
        )
        return int(other_count or 0) == 0

    def _audit(
        self,
        *,
        action: str,
        object_id: UUID,
        reason: str,
        before: dict[str, object],
        after: dict[str, object],
    ) -> None:
        self._session.add(
            AuditLog(
                occurred_at=datetime.now(UTC),
                actor_id=self._actor_id,
                trace_id=self._trace_id,
                action=action,
                object_type="user_account",
                object_id=object_id,
                reason=reason,
                before_payload=before,
                after_payload=after,
                source="api",
            )
        )

    @staticmethod
    def _response(user: UserAccount, roles: list[str]) -> UserAdminResponse:
        return UserAdminResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            status=user.status,
            person_id=user.person_id,
            roles=roles,
        )

    @staticmethod
    def _audit_payload(user: UserAccount, roles: list[str]) -> dict[str, object]:
        return {
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status,
            "person_id": str(user.person_id) if user.person_id else None,
            "roles": roles,
        }

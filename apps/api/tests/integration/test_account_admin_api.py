from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.modules.platform.models import UserAccount
from hris.modules.workforce.models import AuditLog


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_system_admin_creates_ssc_account_and_manages_access(
    business_client: AsyncClient,
    admin_token: str,
    restricted_token: str,
    db_session: AsyncSession,
) -> None:
    denied = await business_client.get(
        "/api/v1/platform/users",
        headers=_auth(restricted_token),
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["code"] == "PERMISSION_DENIED"

    roles = await business_client.get(
        "/api/v1/platform/roles",
        headers=_auth(admin_token),
    )
    assert roles.status_code == 200, roles.text
    assert "SSC_ADMIN" in {item["code"] for item in roles.json()["items"]}

    created = await business_client.post(
        "/api/v1/platform/users",
        headers=_auth(admin_token),
        json={
            "username": "SSC.SYNTHETIC",
            "display_name": "  合成SSC管理员  ",
            "password": "synthetic-password-123",
            "role_codes": ["ssc_admin", "SSC_ADMIN"],
            "reason": "  创建合成SSC测试账号  ",
        },
    )
    assert created.status_code == 201, created.text
    user = created.json()
    assert user["username"] == "ssc.synthetic"
    assert user["display_name"] == "合成SSC管理员"
    assert user["roles"] == ["SSC_ADMIN"]
    assert user["status"] == "active"
    assert "password" not in user

    duplicate = await business_client.post(
        "/api/v1/platform/users",
        headers=_auth(admin_token),
        json={
            "username": "ssc.synthetic",
            "display_name": "重复账号",
            "password": "synthetic-password-456",
            "role_codes": ["SSC_ADMIN"],
            "reason": "重复账号验证",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "USER_USERNAME_EXISTS"

    initial_login = await business_client.post(
        "/api/v1/auth/login",
        json={"username": "ssc.synthetic", "password": "synthetic-password-123"},
    )
    assert initial_login.status_code == 200, initial_login.text
    initial_token = initial_login.json()["access_token"]

    updated = await business_client.patch(
        f"/api/v1/platform/users/{user['id']}",
        headers=_auth(admin_token),
        json={
            "status": "inactive",
            "role_codes": ["SSC_ADMIN"],
            "reason": "暂停合成SSC账号",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "inactive"

    login = await business_client.post(
        "/api/v1/auth/login",
        json={"username": "ssc.synthetic", "password": "synthetic-password-123"},
    )
    assert login.status_code == 401, login.text

    reactivated = await business_client.patch(
        f"/api/v1/platform/users/{user['id']}",
        headers=_auth(admin_token),
        json={"status": "active", "reason": "恢复合成SSC账号"},
    )
    assert reactivated.status_code == 200, reactivated.text
    old_session = await business_client.get(
        "/api/v1/auth/me",
        headers=_auth(initial_token),
    )
    assert old_session.status_code == 401, old_session.text

    account = await db_session.get(UserAccount, UUID(user["id"]))
    audit_rows = list(
        (
            await db_session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.object_type == "user_account",
                    AuditLog.object_id == UUID(user["id"]),
                )
                .order_by(AuditLog.occurred_at)
            )
        ).all()
    )
    assert account is not None
    assert account.status == "active"
    assert [item.action for item in audit_rows] == [
        "account.create",
        "account.update",
        "account.update",
    ]
    assert audit_rows[0].reason == "创建合成SSC测试账号"
    assert audit_rows[1].before_payload["status"] == "active"
    assert audit_rows[1].after_payload["status"] == "inactive"
    assert audit_rows[2].before_payload["status"] == "inactive"
    assert audit_rows[2].after_payload["status"] == "active"
    assert "password" not in audit_rows[0].after_payload


async def test_account_admin_preserves_current_and_last_system_admin(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    users = await business_client.get(
        "/api/v1/platform/users?limit=200&offset=0",
        headers=_auth(admin_token),
    )
    assert users.status_code == 200, users.text
    admin = next(item for item in users.json()["items"] if item["username"] == "synthetic-admin")

    self_deactivation = await business_client.patch(
        f"/api/v1/platform/users/{admin['id']}",
        headers=_auth(admin_token),
        json={"status": "inactive", "reason": "不允许停用自己"},
    )
    assert self_deactivation.status_code == 409, self_deactivation.text
    assert self_deactivation.json()["code"] == "CANNOT_DEACTIVATE_CURRENT_USER"

    remove_last_admin_role = await business_client.patch(
        f"/api/v1/platform/users/{admin['id']}",
        headers=_auth(admin_token),
        json={"role_codes": ["SSC_ADMIN"], "reason": "不允许移除最后主管理员"},
    )
    assert remove_last_admin_role.status_code == 409, remove_last_admin_role.text
    assert remove_last_admin_role.json()["code"] == "LAST_SYSTEM_ADMIN_REQUIRED"

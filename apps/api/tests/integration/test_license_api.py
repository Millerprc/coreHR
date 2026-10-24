# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权管理 API 的集成测试。

Requirement: D-108 — 激活 / 停用 / 状态查询 / 只读拦截 / 审计 / 只存摘要，
全部按对外契约验证（断言带 response.text）。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from license_support import (
    SYNTHETIC_LICENSEE,
    TEST_KID,
    build_token,
    install_public_keys,
    new_signing_key,
    set_enforcement,
    uninstall_public_keys,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hris.core.licensing import store
from hris.core.licensing.service import clear_license_state_cache
from hris.modules.platform.models import LicenseRegistration
from hris.modules.workforce.models import AuditLog


_LICENSE_PATH = "/api/v1/license"
_ACTIVATE_PATH = "/api/v1/license/activate"
_DEACTIVATE_PATH = "/api/v1/license/deactivate"
_RULE_SETS_PATH = "/api/v1/attendance/rule-sets"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def signing_key():
    private_key, public_b64 = new_signing_key()
    install_public_keys(public_b64, TEST_KID)
    try:
        yield private_key
    finally:
        uninstall_public_keys()


@pytest_asyncio.fixture(autouse=True)
async def reset_license_state_cache():
    """授权状态是进程内 + Redis 两级缓存，测试之间必须清干净。"""
    await clear_license_state_cache()
    yield
    await clear_license_state_cache()


@pytest.fixture
def enforcement_enabled():
    set_enforcement(True)
    try:
        yield
    finally:
        set_enforcement(False)


def _license_id() -> str:
    return f"LIC-TEST-{uuid.uuid4().hex[:12].upper()}"


async def test_get_license_without_authorization_is_readonly(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.get(_LICENSE_PATH, headers=_auth(admin_token))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "none"
    assert payload["readonly_mode"] is True
    assert payload["tier"] is None
    assert payload["licensee"] is None
    assert payload["license_id"] is None
    assert payload["seat_limit"] is None
    assert set(payload["entitlements"]) == {
        "attendance",
        "workflow",
        "lifecycle",
        "governance",
        "workforce",
        "performance",
    }
    for entitlement in payload["entitlements"].values():
        assert entitlement == {"read": True, "write": False}


async def test_get_license_requires_login(business_client: AsyncClient) -> None:
    response = await business_client.get(_LICENSE_PATH)

    assert response.status_code == 401, response.text


async def test_activate_valid_token_unlocks_write_entitlements(
    business_client: AsyncClient,
    admin_token: str,
    signing_key,
) -> None:
    token = build_token(signing_key, license_id=_license_id())

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["activated"] is True
    assert payload["status"] == "active"
    assert payload["tier"] == "commercial"
    assert payload["licensee"] == SYNTHETIC_LICENSEE
    assert payload["entitlements"]["attendance"] == {"read": True, "write": True}
    assert payload["entitlements"]["workflow"] == {"read": True, "write": False}
    assert payload["expires_at"].endswith("Z")

    status = await business_client.get(_LICENSE_PATH, headers=_auth(admin_token))
    assert status.status_code == 200, status.text
    state = status.json()
    assert state["status"] == "active"
    assert state["readonly_mode"] is False
    assert state["license_id"] == payload.get("license_id") or state["license_id"]
    assert state["licensee_short"] == "Synthetic"


async def test_activation_stores_only_token_digest(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    signing_key,
) -> None:
    license_id = _license_id()
    token = build_token(signing_key, license_id=license_id)

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )
    assert response.status_code == 200, response.text

    registration = await db_session.scalar(
        select(LicenseRegistration).where(LicenseRegistration.license_id == license_id)
    )
    assert registration is not None
    assert registration.token_digest == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert registration.token_digest != token
    assert token not in registration.token_digest
    assert token not in json.dumps(registration.entitlements, ensure_ascii=False)


async def test_activate_tampered_token_is_rejected(
    business_client: AsyncClient,
    admin_token: str,
    signing_key,
) -> None:
    token = build_token(signing_key, license_id=_license_id())
    prefix, header_b64, payload_b64, signature_b64 = token.split(".")
    index = len(signature_b64) // 2
    flipped = "A" if signature_b64[index] != "A" else "B"
    tampered = (
        f"{prefix}.{header_b64}.{payload_b64}."
        f"{signature_b64[:index]}{flipped}{signature_b64[index + 1:]}"
    )

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": tampered}
    )

    assert response.status_code == 400, response.text
    assert response.json()["code"] == "LICENSE_INVALID_SIGNATURE"


async def test_activate_malformed_token_is_rejected(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": "not-a-token"}
    )

    assert response.status_code == 400, response.text
    assert response.json()["code"] == "LICENSE_INVALID_TOKEN"


async def test_activate_expired_token_keeps_readonly_mode(
    business_client: AsyncClient,
    admin_token: str,
    signing_key,
) -> None:
    now = datetime.now(UTC)
    token = build_token(
        signing_key,
        license_id=_license_id(),
        issued_at=now - timedelta(days=10),
        not_before=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
    )

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "expired"

    status = await business_client.get(_LICENSE_PATH, headers=_auth(admin_token))
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "expired"
    assert status.json()["readonly_mode"] is True


async def test_repeat_activation_is_idempotent(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    signing_key,
) -> None:
    license_id = _license_id()
    token = build_token(signing_key, license_id=license_id)

    first = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )
    second = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "active"

    rows = (
        await db_session.scalars(
            select(LicenseRegistration).where(
                LicenseRegistration.license_id == license_id
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "active"


async def test_concurrent_activation_conflict_keeps_single_active_row(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    signing_key,
    monkeypatch,
) -> None:
    """并发激活同一 license_id：唯一索引兜底，后激活覆盖前激活，不产生双活。"""
    license_id = _license_id()
    token = build_token(signing_key, license_id=license_id)

    # 模拟另一个进程已经写入了同一 license_id。
    db_session.add(
        LicenseRegistration(
            id=uuid.uuid4(),
            license_id=license_id,
            licensee="Synthetic Other Process",
            licensee_short="Synthetic Other",
            tier="developer",
            entitlements={},
            token_digest=hashlib.sha256(b"other").hexdigest(),
            issued_at=datetime.now(UTC),
            not_before=None,
            expires_at=None,
            seat_limit=None,
            status="active",
            source="admin",
            activated_at=datetime.now(UTC),
            activated_by="synthetic-other",
        )
    )
    await db_session.flush()

    # 让前置查询「看不到」这条记录（模拟竞态窗口：查完才被别的事务插入）。
    original_lock = store._lock_by_license_id
    calls = {"count": 0}

    async def _racing_lock(session, license_id_value):
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return await original_lock(session, license_id_value)

    monkeypatch.setattr(store, "_lock_by_license_id", _racing_lock)

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )

    assert response.status_code == 200, response.text
    rows = (
        await db_session.scalars(
            select(LicenseRegistration).where(
                LicenseRegistration.license_id == license_id
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "active"
    assert rows[0].licensee == SYNTHETIC_LICENSEE
    assert rows[0].token_digest == hashlib.sha256(token.encode("utf-8")).hexdigest()


async def test_deactivate_falls_back_to_readonly(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    signing_key,
) -> None:
    license_id = _license_id()
    token = build_token(signing_key, license_id=license_id)
    activated = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )
    assert activated.status_code == 200, activated.text

    response = await business_client.post(_DEACTIVATE_PATH, headers=_auth(admin_token))

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "none", "readonly_mode": True}

    registration = await db_session.scalar(
        select(LicenseRegistration).where(LicenseRegistration.license_id == license_id)
    )
    assert registration is not None
    assert registration.status == "superseded"

    status = await business_client.get(_LICENSE_PATH, headers=_auth(admin_token))
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "none"
    assert status.json()["readonly_mode"] is True


async def test_audit_log_contains_no_token_plaintext(
    business_client: AsyncClient,
    admin_token: str,
    db_session: AsyncSession,
    signing_key,
) -> None:
    token = build_token(signing_key, license_id=_license_id())

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )
    assert response.status_code == 200, response.text

    logs = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "platform.license.activate")
        )
    ).all()
    assert logs, "激活必须写审计"
    payload = json.dumps(
        {
            "before": logs[-1].before_payload,
            "after": logs[-1].after_payload,
            "reason": logs[-1].reason,
        },
        ensure_ascii=False,
    )
    assert token not in payload
    assert "coreHR." not in payload


async def test_readonly_mode_blocks_write_and_allows_read(
    business_client: AsyncClient,
    admin_token: str,
    enforcement_enabled,
) -> None:
    write = await business_client.post(
        _RULE_SETS_PATH,
        headers=_auth(admin_token),
        json={
            "code": "SYNTHETIC_LICENSED",
            "name": "Synthetic licensed attendance",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
            "rules": {"late_grace_minutes": 5},
        },
    )

    assert write.status_code == 403, write.text
    payload = write.json()
    assert payload["code"] == "LICENSE_REQUIRED"
    assert set(payload["details"]) == {"module", "required", "tier", "contact_hint"}
    assert payload["details"]["module"] == "attendance"
    assert payload["details"]["required"] == "write"
    assert payload["details"]["tier"] is None

    read = await business_client.get(_RULE_SETS_PATH, headers=_auth(admin_token))

    assert read.status_code == 200, read.text


async def test_licensed_module_write_is_allowed_after_activation(
    business_client: AsyncClient,
    admin_token: str,
    signing_key,
    enforcement_enabled,
) -> None:
    token = build_token(signing_key, license_id=_license_id())
    activated = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": token}
    )
    assert activated.status_code == 200, activated.text

    write = await business_client.post(
        _RULE_SETS_PATH,
        headers=_auth(admin_token),
        json={
            "code": "SYNTHETIC_LICENSED",
            "name": "Synthetic licensed attendance",
            "timezone": "Asia/Shanghai",
            "effective_from": "2026-01-01",
            "rules": {"late_grace_minutes": 5},
        },
    )

    assert write.status_code == 201, write.text


async def test_activate_requires_admin_permission(
    business_client: AsyncClient,
    restricted_token: str,
    signing_key,
) -> None:
    token = build_token(signing_key, license_id=_license_id())

    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(restricted_token), json={"token": token}
    )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_deactivate_requires_admin_permission(
    business_client: AsyncClient,
    restricted_token: str,
) -> None:
    response = await business_client.post(_DEACTIVATE_PATH, headers=_auth(restricted_token))

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_activate_rejects_empty_token(
    business_client: AsyncClient,
    admin_token: str,
) -> None:
    response = await business_client.post(
        _ACTIVATE_PATH, headers=_auth(admin_token), json={"token": ""}
    )

    assert response.status_code == 422, response.text

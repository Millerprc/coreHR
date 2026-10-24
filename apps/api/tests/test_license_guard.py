# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""只读演示模式的路由级 / 服务级拦截。

Requirement: D-108 — 写方法需要对应模块的写授权；只读方法放行；
403 的 `details` 只有 {module, required, tier, contact_hint}，不泄露业务策略细节。
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from hris.core.licensing import guard
from hris.core.licensing.errors import LICENSE_DETAIL_KEYS, LicenseRequiredError
from hris.core.licensing.types import (
    LICENSED_MODULES,
    LicenseEntitlements,
    LicenseState,
    LicenseStatus,
    LicenseTier,
)


_WRITE_PATH = "/api/v1/attendance/rule-sets"
_QUERY_POST_PATH = "/api/v1/attendance/daily-results/query"


def _request(method: str, path: str = _WRITE_PATH) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "root_path": "",
            "query_string": b"",
            "headers": [],
            "client": ("test", 12345),
            "server": ("test", 80),
        }
    )


def _state(
    *,
    write: bool = True,
    read: bool = True,
    tier: LicenseTier | None = LicenseTier.COMMERCIAL,
    status: LicenseStatus = LicenseStatus.ACTIVE,
) -> LicenseState:
    entitlements = LicenseEntitlements.from_payload(
        {
            name: {"read": read, "write": write}
            for name in LICENSED_MODULES
        }
    )
    return LicenseState(
        status=status,
        readonly_mode=status is not LicenseStatus.ACTIVE or tier is LicenseTier.COMMUNITY,
        tier=tier,
        entitlements=entitlements,
    )


@pytest.fixture
def enforced(monkeypatch):
    """打开拦截开关并固定授权状态。"""
    monkeypatch.setattr(guard, "is_enforcement_enabled", lambda: True)
    return monkeypatch


def _stub_state(monkeypatch, state: LicenseState) -> None:
    async def _current_state(self, *, use_cache: bool = True) -> LicenseState:
        return state

    monkeypatch.setattr(guard.LicenseService, "current_state", _current_state)


async def _call(dependency, method: str, path: str = _WRITE_PATH):
    current = (SimpleNamespace(id=uuid.uuid4()), SimpleNamespace())
    return await dependency(request=_request(method, path), current=current, db=object())


async def test_get_is_allowed_without_write_entitlement(enforced) -> None:
    _stub_state(enforced, _state(write=False))

    user = await _call(guard.require_licensed_write("attendance"), "GET")

    assert user is not None


async def test_post_without_write_entitlement_is_blocked(enforced) -> None:
    _stub_state(enforced, _state(write=False))

    with pytest.raises(LicenseRequiredError) as excinfo:
        await _call(guard.require_licensed_write("attendance"), "POST")

    error = excinfo.value
    assert error.status_code == 403
    assert error.code == "LICENSE_REQUIRED"
    assert error.details["module"] == "attendance"
    assert error.details["required"] == "write"
    assert error.details["tier"] == "commercial"


async def test_post_with_write_entitlement_is_allowed(enforced) -> None:
    _stub_state(enforced, _state(write=True))

    user = await _call(guard.require_licensed_write("attendance"), "POST")

    assert user is not None


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
async def test_other_write_methods_are_blocked(enforced, method: str) -> None:
    _stub_state(enforced, _state(write=False))

    with pytest.raises(LicenseRequiredError):
        await _call(guard.require_licensed_write("attendance"), method)


async def test_expired_license_blocks_write_even_with_write_flag(enforced) -> None:
    """过期授权一律只读：entitlements 里还留着 write 也必须拦。"""
    _stub_state(enforced, _state(write=True, status=LicenseStatus.EXPIRED))

    with pytest.raises(LicenseRequiredError):
        await _call(guard.require_licensed_write("attendance"), "POST")


async def test_community_tier_blocks_write(enforced) -> None:
    _stub_state(enforced, _state(write=True, tier=LicenseTier.COMMUNITY))

    with pytest.raises(LicenseRequiredError):
        await _call(guard.require_licensed_write("attendance"), "POST")


async def test_whitelisted_query_post_is_allowed(enforced) -> None:
    """查询型 POST 必须在白名单里显式登记后才放行。"""
    _stub_state(enforced, _state(write=False))
    guard.register_read_only_post_exception(
        _QUERY_POST_PATH,
        module="attendance",
        reason="只读报表查询，不产生任何写副作用",
    )
    try:
        user = await _call(
            guard.require_licensed_write("attendance"), "POST", _QUERY_POST_PATH
        )
    finally:
        guard.READ_ONLY_POST_EXCEPTIONS.pop(_QUERY_POST_PATH, None)

    assert user is not None


async def test_query_post_without_registration_is_blocked(enforced) -> None:
    """禁止「默认放行」：没登记的 POST 一律按写操作拦截。"""
    _stub_state(enforced, _state(write=False))

    with pytest.raises(LicenseRequiredError):
        await _call(
            guard.require_licensed_write("attendance"), "POST", _QUERY_POST_PATH
        )


async def test_require_licensed_read_blocks_when_read_missing(enforced) -> None:
    _stub_state(enforced, _state(write=True, read=False))

    with pytest.raises(LicenseRequiredError) as excinfo:
        current = (SimpleNamespace(id=uuid.uuid4()), SimpleNamespace())
        await guard.require_licensed_read("attendance")(
            current=current, db=object()
        )

    assert excinfo.value.details["required"] == "read"
    assert excinfo.value.details["module"] == "attendance"


async def test_ensure_write_allowed_raises_for_denied_module(enforced) -> None:
    _stub_state(enforced, _state(write=False))

    with pytest.raises(LicenseRequiredError) as excinfo:
        await guard.ensure_write_allowed("attendance", session=object())

    assert excinfo.value.code == "LICENSE_REQUIRED"
    assert excinfo.value.details["module"] == "attendance"


async def test_ensure_write_allowed_passes_for_granted_module(enforced) -> None:
    _stub_state(enforced, _state(write=True))

    await guard.ensure_write_allowed("attendance", session=object())


async def test_ensure_write_allowed_is_noop_when_enforcement_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(guard, "is_enforcement_enabled", lambda: False)
    _stub_state(monkeypatch, _state(write=False))

    await guard.ensure_write_allowed("attendance", session=object())


async def test_details_expose_only_the_four_allowed_keys(enforced) -> None:
    _stub_state(enforced, _state(write=False))

    with pytest.raises(LicenseRequiredError) as excinfo:
        await _call(guard.require_licensed_write("attendance"), "POST")

    details = excinfo.value.details
    assert set(details) == set(LICENSE_DETAIL_KEYS)
    assert set(details) == {"module", "required", "tier", "contact_hint"}


async def test_error_payload_does_not_leak_business_policy(enforced) -> None:
    """details / message 不得出现业务策略细节（否则可被反复试错反推引擎行为）。"""
    _stub_state(enforced, _state(write=False))

    with pytest.raises(LicenseRequiredError) as excinfo:
        await _call(guard.require_licensed_write("attendance"), "POST")

    payload = f"{excinfo.value.message} {excinfo.value.details}"
    for leaked in ("规则", "排班", "班次", "假勤", "校验", "workflow", "state_machine"):
        assert leaked not in payload

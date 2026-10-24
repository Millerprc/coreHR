# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权模型的核心类型。

Requirement: D-108 — 授权判定只有一个收口点（`hris/core/licensing/`），
任何模块不得自己实现一套授权逻辑；本模块的枚举与数据结构是对外契约的唯一来源。

术语：
- tier（版本）：community / developer / commercial，决定写能力的授予范围。
- status（状态）：当前授权事实的状态，与 tier 正交。
- entitlements（授权范围）：模块 → {read, write} 的逐模块读写能力。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


#: 受授权管理的模块清单。顺序与 API 响应契约一致（前端按此渲染）。
LICENSED_MODULES: tuple[str, ...] = (
    "attendance",
    "workflow",
    "lifecycle",
    "governance",
    "workforce",
    "performance",
)


class LicenseTier(StrEnum):
    """授权版本。

    Requirement: D-108 — 三级版本中只有 community 固定为「全部写禁用」，
    developer / commercial 按合同模块授予写能力。
    """

    COMMUNITY = "community"
    DEVELOPER = "developer"
    COMMERCIAL = "commercial"


class LicenseStatus(StrEnum):
    """当前授权状态。

    Requirement: D-108 — 除 ACTIVE 外，其余状态一律等价于只读演示模式。
    """

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    NOT_YET_VALID = "not_yet_valid"
    NONE = "none"


@dataclass(frozen=True)
class ModuleEntitlement:
    """单模块的读 / 写能力。"""

    read: bool = True
    write: bool = False

    def to_payload(self) -> dict[str, bool]:
        return {"read": self.read, "write": self.write}


@dataclass(frozen=True)
class LicenseEntitlements:
    """模块 → 读写能力的集合。

    Requirement: D-108 — 未授权时所有模块 read=True、write=False：
    只读演示模式必须让全部功能可浏览，只禁写。
    """

    modules: Mapping[str, ModuleEntitlement]

    @classmethod
    def readonly(cls) -> LicenseEntitlements:
        return cls(
            {name: ModuleEntitlement(read=True, write=False) for name in LICENSED_MODULES}
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None) -> LicenseEntitlements:
        raw = payload or {}
        modules: dict[str, ModuleEntitlement] = {}
        for name in LICENSED_MODULES:
            entry = raw.get(name)
            modules[name] = _to_module_entitlement(entry)
        # 清单外的模块（例如后续新增）保留在内部判定里，但不进入对外响应契约。
        for name, entry in raw.items():
            if name in modules:
                continue
            modules[name] = _to_module_entitlement(entry)
        return cls(modules)

    def can_read(self, module: str) -> bool:
        entitlement = self.modules.get(module)
        return bool(entitlement and entitlement.read)

    def can_write(self, module: str) -> bool:
        entitlement = self.modules.get(module)
        return bool(entitlement and entitlement.write)

    def to_payload(self) -> dict[str, dict[str, bool]]:
        """对外响应契约：固定六个模块，字段恒为 {read, write}。"""
        return {name: self.modules[name].to_payload() for name in LICENSED_MODULES}


def _to_module_entitlement(entry: Any) -> ModuleEntitlement:
    if not isinstance(entry, Mapping):
        return ModuleEntitlement(read=True, write=False)
    return ModuleEntitlement(
        read=bool(entry.get("read", True)),
        write=bool(entry.get("write", False)),
    )


@dataclass(frozen=True)
class LicenseState:
    """当前授权状态快照。

    Requirement: D-108 — 这是唯一对外暴露的授权事实；`readonly_mode` 表示
    「当前处于只读演示模式」，即没有可用的写授权（未激活 / 已过期 / 已吊销 /
    尚未生效 / community 版本）。
    """

    status: LicenseStatus
    readonly_mode: bool
    tier: LicenseTier | None = None
    licensee: str | None = None
    licensee_short: str | None = None
    license_id: str | None = None
    entitlements: LicenseEntitlements = field(default_factory=LicenseEntitlements.readonly)
    issued_at: datetime | None = None
    not_before: datetime | None = None
    expires_at: datetime | None = None
    seat_limit: int | None = None
    activated_at: datetime | None = None

    def can_read(self, module: str) -> bool:
        return self.entitlements.can_read(module)

    def can_write(self, module: str) -> bool:
        """写能力判定：状态必须是 active，且该模块显式授予 write。

        Requirement: D-108 — community 版本固定为全部写禁用（只读演示模式）。
        """
        if self.status is not LicenseStatus.ACTIVE:
            return False
        if self.tier is LicenseTier.COMMUNITY:
            return False
        return self.entitlements.can_write(module)

    def to_payload(self) -> dict[str, Any]:
        """序列化给 Redis 共享缓存用。"""
        return {
            "status": self.status.value,
            "readonly_mode": self.readonly_mode,
            "tier": self.tier.value if self.tier else None,
            "licensee": self.licensee,
            "licensee_short": self.licensee_short,
            "license_id": self.license_id,
            "entitlements": self.entitlements.to_payload(),
            "issued_at": _iso(self.issued_at),
            "not_before": _iso(self.not_before),
            "expires_at": _iso(self.expires_at),
            "seat_limit": self.seat_limit,
            "activated_at": _iso(self.activated_at),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> LicenseState:
        status_value = str(payload.get("status") or LicenseStatus.NONE.value)
        tier_value = payload.get("tier")
        entitlements = payload.get("entitlements")
        return cls(
            status=LicenseStatus(status_value)
            if status_value in {item.value for item in LicenseStatus}
            else LicenseStatus.NONE,
            readonly_mode=bool(payload.get("readonly_mode", True)),
            tier=LicenseTier(str(tier_value)) if tier_value else None,
            licensee=payload.get("licensee"),
            licensee_short=payload.get("licensee_short"),
            license_id=payload.get("license_id"),
            entitlements=LicenseEntitlements.from_payload(
                entitlements if isinstance(entitlements, Mapping) else None
            ),
            issued_at=_parse_iso(payload.get("issued_at")),
            not_before=_parse_iso(payload.get("not_before")),
            expires_at=_parse_iso(payload.get("expires_at")),
            seat_limit=(
                int(payload["seat_limit"]) if payload.get("seat_limit") is not None else None
            ),
            activated_at=_parse_iso(payload.get("activated_at")),
        )


@dataclass(frozen=True)
class VerificationResult:
    """Token 验签结果。

    Requirement: D-108 — 验签失败一律 `LICENSE_INVALID_SIGNATURE`，
    只有「结构 / 载荷非法」才是 `LICENSE_INVALID_TOKEN`。
    """

    ok: bool
    error_code: str | None = None
    message: str | None = None
    kid: str | None = None
    license_id: str | None = None
    licensee: str | None = None
    licensee_short: str | None = None
    tier: LicenseTier | None = None
    entitlements: LicenseEntitlements | None = None
    issued_at: datetime | None = None
    not_before: datetime | None = None
    expires_at: datetime | None = None
    seat_limit: int | None = None


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

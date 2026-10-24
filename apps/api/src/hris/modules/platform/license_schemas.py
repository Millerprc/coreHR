# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权管理的 API 契约。

Requirement: D-108 — 响应契约是前端（授权徽标 / 授权管理页）的唯一依据，
字段名、类型、可空性不得随意改动。

约定：
- `status`：active | expired | revoked | not_yet_valid | none
- `readonly_mode`：true 表示当前处于只读演示模式（没有可用的写授权）
- `entitlements`：对象恒存在，固定六个模块，字段恒为 {read, write}
- 时间一律 `YYYY-MM-DDTHH:MM:SSZ`（UTC）
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_serializer

from hris.core.licensing.types import LicenseStatus, LicenseTier


def to_iso_z(value: datetime | None) -> str | None:
    """datetime → `2026-10-24T06:00:00Z`（UTC，秒精度）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


class ModuleEntitlementResponse(BaseModel):
    """单模块的读 / 写能力。"""

    read: bool
    write: bool


class LicenseActivateRequest(BaseModel):
    """激活请求：提交签发方给的 License Token。"""

    token: str = Field(min_length=1, max_length=16384)


class LicenseStateResponse(BaseModel):
    """当前授权状态。"""

    status: LicenseStatus
    readonly_mode: bool
    tier: LicenseTier | None = None
    licensee: str | None = None
    licensee_short: str | None = None
    license_id: str | None = None
    entitlements: dict[str, ModuleEntitlementResponse]
    issued_at: datetime | None = None
    not_before: datetime | None = None
    expires_at: datetime | None = None
    seat_limit: int | None = None
    activated_at: datetime | None = None

    @field_serializer("issued_at", "not_before", "expires_at", "activated_at")
    def _serialize_datetimes(self, value: datetime | None) -> str | None:
        return to_iso_z(value)


class LicenseActivateResponse(BaseModel):
    """激活结果。

    Requirement: D-108 — 过期 Token 也允许激活，此时 status=expired，
    系统仍保持只读演示模式。
    """

    activated: bool
    status: LicenseStatus
    tier: LicenseTier | None = None
    licensee: str | None = None
    entitlements: dict[str, ModuleEntitlementResponse]
    expires_at: datetime | None = None

    @field_serializer("expires_at")
    def _serialize_expires_at(self, value: datetime | None) -> str | None:
        return to_iso_z(value)


class LicenseDeactivateResponse(BaseModel):
    """停用结果。"""

    status: LicenseStatus
    readonly_mode: bool

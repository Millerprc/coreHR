# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""授权测试的共用支撑。

Requirement: D-108 — 测试用的 Ed25519 私钥**只存在于测试进程内存里**：
不落盘、不进仓库、不写进任何 fixture 文件。
合成数据一律可识别（`Synthetic Licensee`），不写真实企业名。
"""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from hris.core.config import get_settings
from hris.core.licensing import keys
from hris.core.licensing.token import encode_token


TEST_KID = "test-k1"
ROTATED_KID = "test-k2"
SYNTHETIC_LICENSEE = "Synthetic Licensee"
SYNTHETIC_LICENSEE_SHORT = "Synthetic"


def new_signing_key() -> tuple[Ed25519PrivateKey, str]:
    """生成测试用 Ed25519 密钥对。

    取舍说明：私钥由 `cryptography` 在进程内生成（Windows 下没有
    `RandomNumberGenerator.Fill` 那种静默弱密钥的坑），用完即弃。
    """
    private_key = Ed25519PrivateKey.generate()
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    public_b64 = base64.urlsafe_b64encode(public_raw).decode("ascii").rstrip("=")
    return private_key, public_b64


def install_public_keys(public_b64: str, kid: str = TEST_KID) -> None:
    """把测试公钥装进环境变量（`COREHR_LICENSE_PUBLIC_KEYS` 覆盖入口）。"""
    install_public_key_table(f"{kid}={public_b64}")


def install_public_key_table(raw: str) -> None:
    """直接写入公钥表原始值（用于轮换期多 kid 并存的用例）。"""
    os.environ["COREHR_LICENSE_PUBLIC_KEYS"] = raw
    get_settings.cache_clear()
    keys._load_public_keys_cached.cache_clear()


def uninstall_public_keys() -> None:
    """移除测试公钥，回到内置公钥表。"""
    os.environ.pop("COREHR_LICENSE_PUBLIC_KEYS", None)
    get_settings.cache_clear()
    keys._load_public_keys_cached.cache_clear()


def set_enforcement(enabled: bool) -> None:
    """切换只读演示模式的拦截总开关。"""
    os.environ["COREHR_LICENSE_ENFORCE"] = "true" if enabled else "false"
    get_settings.cache_clear()


def build_token(
    private_key: Ed25519PrivateKey,
    *,
    kid: str = TEST_KID,
    license_id: str = "LIC-TEST-000001",
    tier: str = "commercial",
    entitlements: dict[str, dict[str, bool]] | None = None,
    not_before: datetime | None = None,
    expires_at: datetime | None = None,
    issued_at: datetime | None = None,
    seat_limit: int | None = 100,
    licensee: str = SYNTHETIC_LICENSEE,
    licensee_short: str = SYNTHETIC_LICENSEE_SHORT,
    extra: dict[str, Any] | None = None,
) -> str:
    """签发一个合成授权 Token。"""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "v": 1,
        "license_id": license_id,
        "licensee": licensee,
        "licensee_short": licensee_short,
        "tier": tier,
        "entitlements": entitlements
        if entitlements is not None
        else {
            "attendance": {"read": True, "write": True},
            "workflow": {"read": True, "write": False},
            "lifecycle": {"read": True, "write": False},
            "governance": {"read": True, "write": False},
            "workforce": {"read": True, "write": False},
            "performance": {"read": True, "write": False},
        },
        "issued_at": _iso(issued_at or (now - timedelta(minutes=1))),
        "not_before": _iso(not_before or (now - timedelta(minutes=1))),
        "expires_at": _iso(expires_at or (now + timedelta(days=365))),
        "seat_limit": seat_limit,
        "deployment_binding": None,
        "issuer": "coreHR",
        "nonce": "synthetic-nonce",
    }
    if extra:
        payload.update(extra)
    return encode_token(payload, private_key=private_key, kid=kid)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

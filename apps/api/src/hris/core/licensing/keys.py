# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""内置授权公钥表与轮换期覆盖。

Requirement: D-108 — 公钥内置在公开仓里（公开不是问题，私钥才是秘密）；
`COREHR_LICENSE_PUBLIC_KEYS` 环境变量用于轮换期临时补充 / 替换公钥。

安全约束：
- 内置公钥缺失或配置损坏时，**激活一律拒绝**（fail-closed on activation），
  但系统仍可只读运行。
- 私钥永远不进仓库；本模块只处理公钥。
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from hris.core.config import get_settings


#: 内置公钥表：{kid: base64(raw 32 字节公钥)}。
#:
#: 取舍说明：`k1` 是**正式签发公钥**（Requirement: D-114）——维护者用 Ed25519
#: 私钥离线签发 License Token，私钥保存在离线签发环境，**永不进入任何仓库**。
#: 轮换时新增 `k2` 与本表并存（旧 kid 仍在），等旧 Token 自然过期后再摘除 `k1`。
#: 公钥不可用或配置损坏时，激活请求会以 `LICENSE_INVALID_SIGNATURE` 被拒（fail-closed），
#: 系统仍以只读演示模式运行 —— 这是预期行为，不是故障。
BUILTIN_PUBLIC_KEYS: dict[str, str] = {
    "k1": "S9vJgSqS8CJneMaXazXl0pvO-uqVA40g6Kn1ISs2BZ0",
}

#: 轮换期环境变量名（值同时支持 JSON 对象与 `kid=base64` 逗号分隔两种写法）。
PUBLIC_KEYS_ENV_VAR = "COREHR_LICENSE_PUBLIC_KEYS"

#: Ed25519 公钥原始长度（字节）。
_ED25519_PUBLIC_KEY_BYTES = 32


class LicenseKeyConfigurationError(RuntimeError):
    """内置公钥缺失或配置损坏 —— 激活必须 fail-closed。"""


def parse_public_key_table(raw: str) -> dict[str, str]:
    """解析 `COREHR_LICENSE_PUBLIC_KEYS` 的值。

    支持两种写法：
    1. JSON 对象：``{"k1": "<base64>", "k2": "<base64>"}``
    2. 逗号分隔：``k1=<base64>,k2=<base64>``

    取舍说明：轮换期需要「旧 kid 仍在、新 kid 已加」的并存状态，
    因此环境变量里的 kid 与内置表**合并**（同名 kid 以环境变量为准），
    而不是整体替换 —— 否则轮换当天所有旧 Token 会立刻失效。
    """
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LicenseKeyConfigurationError(
                f"{PUBLIC_KEYS_ENV_VAR} 不是合法的 JSON"
            ) from exc
        if not isinstance(data, Mapping):
            raise LicenseKeyConfigurationError(
                f"{PUBLIC_KEYS_ENV_VAR} 必须是 kid 到公钥的映射"
            )
        table: dict[str, str] = {}
        for kid, value in data.items():
            if not isinstance(kid, str) or not isinstance(value, str):
                raise LicenseKeyConfigurationError(
                    f"{PUBLIC_KEYS_ENV_VAR} 的条目格式非法"
                )
            table[kid] = value
        return table

    table = {}
    for item in text.split(","):
        entry = item.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise LicenseKeyConfigurationError(
                f"{PUBLIC_KEYS_ENV_VAR} 的条目格式非法"
            )
        kid, _, value = entry.partition("=")
        table[kid.strip()] = value.strip()
    return table


def _decode_base64(value: str) -> bytes:
    text = (value or "").strip()
    padding = "=" * (-len(text) % 4)
    try:
        # altchars 同时兼容 base64url 与标准 base64；validate=True 拒绝非法字符。
        return base64.b64decode(text + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise LicenseKeyConfigurationError("授权公钥不是合法的 base64") from exc


@lru_cache(maxsize=16)
def _load_public_keys_cached(raw: str | None) -> Mapping[str, bytes]:
    table = dict(BUILTIN_PUBLIC_KEYS)
    if raw:
        table.update(parse_public_key_table(raw))
    decoded: dict[str, bytes] = {}
    for kid, value in table.items():
        material = _decode_base64(value)
        if len(material) != _ED25519_PUBLIC_KEY_BYTES:
            raise LicenseKeyConfigurationError(f"授权公钥 {kid} 长度非法")
        decoded[kid] = material
    return MappingProxyType(decoded)


def load_public_keys() -> Mapping[str, bytes]:
    """返回 {kid: raw 公钥字节}。

    Requirement: D-108 — 公钥表损坏时抛 `LicenseKeyConfigurationError`，
    由调用方 fail-closed 拒绝激活，绝不放行。
    """
    raw = get_settings().license_public_keys
    return _load_public_keys_cached(raw or None)


def load_public_key(kid: str) -> bytes | None:
    """按 kid 取公钥；未知 kid 返回 None（不得回退到任意一把公钥）。"""
    return load_public_keys().get(kid)


def known_key_ids() -> tuple[str, ...]:
    return tuple(sorted(load_public_keys().keys()))

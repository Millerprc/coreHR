# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""License Token 的编解码与 Ed25519 离线验签。

Token 格式（计划 §5.1）::

    coreHR.<b64url(header)>.<b64url(payload)>.<b64url(signature)>

header::

    {"alg": "EdDSA", "typ": "corehr-license-v1", "kid": "k1"}

签名覆盖 `header段 + "." + payload段` 的 ASCII 字节，因此 **header 与 payload
任一字节被改都会验签失败**。

Requirement: D-108 — 验签失败一律 `LICENSE_INVALID_SIGNATURE`；
只有「结构 / 载荷非法」才是 `LICENSE_INVALID_TOKEN`。

错误码划分（避免被伪造利用）：
- `LICENSE_INVALID_TOKEN`：外层信封非法（分段数 / 前缀 / base64）或载荷字段非法；
- `LICENSE_INVALID_SIGNATURE`：从头部开始的一切（头部解析 / alg / typ / kid / 签名），
  即**无法建立信任**的情形一律按签名无效处理（fail-closed）。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from hris.core.licensing.keys import (
    LicenseKeyConfigurationError,
    load_public_key,
)
from hris.core.licensing.types import (
    LicenseEntitlements,
    LicenseTier,
    VerificationResult,
)


TOKEN_PREFIX = "coreHR"
TOKEN_HEADER_TYPE = "corehr-license-v1"
SIGNATURE_ALGORITHM = "EdDSA"
TOKEN_VERSION = 1

ERROR_INVALID_TOKEN = "LICENSE_INVALID_TOKEN"
ERROR_INVALID_SIGNATURE = "LICENSE_INVALID_SIGNATURE"


class LicenseTokenFormatError(ValueError):
    """Token 结构非法（分段、base64 或 JSON 解析失败）。"""


def b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise LicenseTokenFormatError("授权 Token 片段不是合法的 base64") from exc


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def encode_token(
    payload: Mapping[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    kid: str,
) -> str:
    """签发 Token。

    取舍说明：签发能力放在 SDK 里是为了让签发工具（私有仓 `corehr-license`）
    与验签共用同一份格式定义，避免两边实现漂移。私钥由调用方持有，
    本函数不接触任何密钥文件，也不落盘。
    """
    header = {"alg": SIGNATURE_ALGORITHM, "typ": TOKEN_HEADER_TYPE, "kid": kid}
    header_b64 = b64url_encode(_canonical_json(header))
    payload_b64 = b64url_encode(_canonical_json(payload))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = private_key.sign(signing_input)
    return f"{TOKEN_PREFIX}.{header_b64}.{payload_b64}.{b64url_encode(signature)}"


def split_token(token: str) -> tuple[str, str, str]:
    """拆出 (header_b64, payload_b64, signature_b64)。"""
    if not isinstance(token, str) or not token.strip():
        raise LicenseTokenFormatError("授权 Token 为空")
    parts = token.strip().split(".")
    if len(parts) != 4 or parts[0] != TOKEN_PREFIX:
        raise LicenseTokenFormatError("授权 Token 格式非法")
    return parts[1], parts[2], parts[3]


def token_digest(token: str) -> str:
    """Token 摘要（sha256 hex）——入库只存它，不存明文。

    Requirement: D-108 — 明文 Token 只在激活请求里出现一次。
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str) -> VerificationResult:
    """离线验签 + 载荷校验。

    Requirement: D-108 — 任何一步失败都不会让系统不可用，
    只影响这一次激活；公钥不可用时 fail-closed（拒绝激活）。
    """
    try:
        header_b64, payload_b64, signature_b64 = split_token(token)
        header_raw = b64url_decode(header_b64)
        payload_raw = b64url_decode(payload_b64)
        signature = b64url_decode(signature_b64)
    except LicenseTokenFormatError as exc:
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_TOKEN, message=str(exc)
        )

    try:
        header = json.loads(header_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # 头部解析不了就没法确定 alg / kid，无法验签 —— 按签名无效处理（fail-closed）。
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_SIGNATURE, message="授权 Token 头部无法解析"
        )
    if not isinstance(header, dict):
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_SIGNATURE, message="授权 Token 头部无法解析"
        )

    # 算法 / 类型不接受降级（例如 alg=none）——一律按签名无效处理。
    if header.get("alg") != SIGNATURE_ALGORITHM or header.get("typ") != TOKEN_HEADER_TYPE:
        return VerificationResult(
            ok=False,
            error_code=ERROR_INVALID_SIGNATURE,
            message="授权 Token 的签名算法或类型不受支持",
        )

    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_SIGNATURE, message="授权 Token 缺少签名密钥标识"
        )

    try:
        public_key_raw = load_public_key(kid)
    except LicenseKeyConfigurationError:
        # 内置公钥缺失 / 配置损坏 → fail-closed：拒绝激活，系统继续只读运行。
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_SIGNATURE, message="授权公钥不可用，无法验证授权"
        )
    if public_key_raw is None:
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_SIGNATURE, message="授权 Token 的签名密钥不受信任"
        )

    try:
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(
            signature, f"{header_b64}.{payload_b64}".encode("ascii")
        )
    except InvalidSignature:
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_SIGNATURE, message="授权 Token 签名校验失败"
        )

    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 载荷无法解析"
        )
    if not isinstance(payload, dict):
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 载荷无法解析"
        )

    return _build_result(payload, kid)


def _build_result(payload: Mapping[str, Any], kid: str) -> VerificationResult:
    license_id = payload.get("license_id")
    if not isinstance(license_id, str) or not license_id.strip():
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 缺少 license_id"
        )

    tier_value = payload.get("tier")
    try:
        tier = LicenseTier(str(tier_value))
    except ValueError:
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 的 tier 非法"
        )

    entitlements_raw = payload.get("entitlements")
    if not isinstance(entitlements_raw, Mapping):
        return VerificationResult(
            ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 缺少 entitlements"
        )

    seat_limit_raw = payload.get("seat_limit")
    seat_limit: int | None = None
    if seat_limit_raw is not None:
        if not isinstance(seat_limit_raw, int) or isinstance(seat_limit_raw, bool):
            return VerificationResult(
                ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 的 seat_limit 非法"
            )
        if seat_limit_raw < 0:
            return VerificationResult(
                ok=False, error_code=ERROR_INVALID_TOKEN, message="授权 Token 的 seat_limit 非法"
            )
        seat_limit = seat_limit_raw

    return VerificationResult(
        ok=True,
        kid=kid,
        license_id=license_id.strip(),
        licensee=_optional_text(payload.get("licensee")),
        licensee_short=_optional_text(payload.get("licensee_short")),
        tier=tier,
        entitlements=LicenseEntitlements.from_payload(entitlements_raw),
        issued_at=_parse_iso(payload.get("issued_at")),
        not_before=_parse_iso(payload.get("not_before")),
        expires_at=_parse_iso(payload.get("expires_at")),
        seat_limit=seat_limit,
    )


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


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

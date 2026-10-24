# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""License Token 编解码与 Ed25519 离线验签。

Requirement: D-108 — 验签失败一律 `LICENSE_INVALID_SIGNATURE`；
只有结构 / 载荷非法才是 `LICENSE_INVALID_TOKEN`。
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from license_support import (
    ROTATED_KID,
    SYNTHETIC_LICENSEE,
    TEST_KID,
    build_token,
    install_public_key_table,
    install_public_keys,
    new_signing_key,
    uninstall_public_keys,
)

from hris.core.licensing.keys import load_public_keys, parse_public_key_table
from hris.core.licensing.service import compute_activation_status
from hris.core.licensing.token import (
    ERROR_INVALID_SIGNATURE,
    ERROR_INVALID_TOKEN,
    b64url_decode,
    b64url_encode,
    split_token,
    token_digest,
    verify_token,
)
from hris.core.licensing.types import LicenseTier


@pytest.fixture
def signing_key():
    private_key, public_b64 = new_signing_key()
    install_public_keys(public_b64, TEST_KID)
    try:
        yield private_key
    finally:
        uninstall_public_keys()


def test_encode_decode_roundtrip(signing_key) -> None:
    token = build_token(signing_key)

    header_b64, payload_b64, signature_b64 = split_token(token)
    assert token.startswith("coreHR.")
    assert len(signature_b64) > 0
    assert b64url_decode(header_b64)
    assert b64url_decode(payload_b64)

    result = verify_token(token)

    assert result.ok is True, result.message
    assert result.error_code is None
    assert result.kid == TEST_KID
    assert result.license_id == "LIC-TEST-000001"
    assert result.licensee == SYNTHETIC_LICENSEE
    assert result.tier is LicenseTier.COMMERCIAL
    assert result.entitlements is not None
    assert result.entitlements.can_write("attendance") is True
    assert result.entitlements.can_write("workflow") is False
    assert result.seat_limit == 100


def test_b64url_roundtrip_without_padding() -> None:
    raw = b"\x00\x01\x02coreHR"

    encoded = b64url_encode(raw)

    assert "=" not in encoded
    assert b64url_decode(encoded) == raw
    assert base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)) == raw


def test_tampered_payload_byte_fails_signature(signing_key) -> None:
    token = build_token(signing_key)
    prefix, header_b64, payload_b64, signature_b64 = token.split(".")

    # 篡改载荷中间的一个字符：base64 仍合法，但签名不再匹配。
    index = len(payload_b64) // 2
    flipped = "A" if payload_b64[index] != "A" else "B"
    tampered = f"{prefix}.{header_b64}.{payload_b64[:index]}{flipped}{payload_b64[index + 1:]}.{signature_b64}"

    result = verify_token(tampered)

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_tampered_signature_byte_fails_signature(signing_key) -> None:
    token = build_token(signing_key)
    prefix, header_b64, payload_b64, signature_b64 = token.split(".")

    index = len(signature_b64) // 2
    flipped = "A" if signature_b64[index] != "A" else "B"
    tampered = f"{prefix}.{header_b64}.{payload_b64}.{signature_b64[:index]}{flipped}{signature_b64[index + 1:]}"

    result = verify_token(tampered)

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_tampered_header_byte_fails_signature(signing_key) -> None:
    token = build_token(signing_key)
    prefix, header_b64, payload_b64, signature_b64 = token.split(".")
    index = len(header_b64) // 2
    flipped = "A" if header_b64[index] != "A" else "B"
    tampered = f"{prefix}.{header_b64[:index]}{flipped}{header_b64[index + 1:]}.{payload_b64}.{signature_b64}"

    result = verify_token(tampered)

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_unknown_kid_is_rejected(signing_key) -> None:
    token = build_token(signing_key, kid="unknown-kid")

    result = verify_token(token)

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_wrong_algorithm_is_rejected(signing_key) -> None:
    """alg 降级（HS256 / none）必须按签名无效处理，不能放行。"""
    import json

    token = build_token(signing_key)
    prefix, header_b64, payload_b64, signature_b64 = token.split(".")
    header = json.loads(b64url_decode(header_b64).decode("utf-8"))
    header["alg"] = "HS256"
    forged_header_b64 = b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )

    result = verify_token(f"{prefix}.{forged_header_b64}.{payload_b64}.{signature_b64}")

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_malformed_token_is_invalid_token(signing_key) -> None:
    for candidate in ("", "not-a-token", "coreHR.only.two", "other.aaa.bbb.ccc"):
        result = verify_token(candidate)

        assert result.ok is False, candidate
        assert result.error_code == ERROR_INVALID_TOKEN, candidate


def test_payload_without_license_id_is_invalid_token(signing_key) -> None:
    token = build_token(signing_key, extra={"license_id": ""})

    result = verify_token(token)

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_TOKEN


def test_expired_token_verifies_but_computes_expired_status(signing_key) -> None:
    now = datetime.now(UTC)
    token = build_token(
        signing_key,
        issued_at=now - timedelta(days=10),
        not_before=now - timedelta(days=10),
        expires_at=now - timedelta(days=1),
    )

    result = verify_token(token)

    assert result.ok is True, result.message
    assert compute_activation_status(result, datetime.now(UTC)) == "expired"


def test_not_yet_valid_token_computes_not_yet_valid_status(signing_key) -> None:
    now = datetime.now(UTC)
    token = build_token(
        signing_key,
        issued_at=now,
        not_before=now + timedelta(days=2),
        expires_at=now + timedelta(days=365),
    )

    result = verify_token(token)

    assert result.ok is True, result.message
    assert compute_activation_status(result, datetime.now(UTC)) == "not_yet_valid"


def test_valid_token_computes_active_status(signing_key) -> None:
    token = build_token(signing_key)

    result = verify_token(token)

    assert result.ok is True, result.message
    assert compute_activation_status(result, datetime.now(UTC)) == "active"


def test_public_key_rotation_keeps_both_kids_trusted(signing_key) -> None:
    """轮换期：新旧 kid 并存，旧 Token 仍然可用。"""
    rotated_private_key, rotated_public_b64 = new_signing_key()
    install_public_key_table(
        f"{TEST_KID}={_public_b64(signing_key)},{ROTATED_KID}={rotated_public_b64}"
    )

    old_token = build_token(signing_key, kid=TEST_KID)
    new_token = build_token(rotated_private_key, kid=ROTATED_KID)

    assert verify_token(old_token).ok is True
    assert verify_token(new_token).ok is True
    # 轮换期语义：环境变量里的 kid 与内置表**合并**（内置 k1 仍然可信）。
    assert {TEST_KID, ROTATED_KID} <= set(load_public_keys().keys())


def test_removed_kid_invalidates_old_token(signing_key) -> None:
    """旧 kid 移除后，旧 Token 全部失效。"""
    rotated_private_key, rotated_public_b64 = new_signing_key()
    install_public_key_table(f"{ROTATED_KID}={rotated_public_b64}")
    old_token = build_token(signing_key, kid=TEST_KID)

    result = verify_token(old_token)

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_unparsable_header_is_treated_as_signature_failure(signing_key) -> None:
    """头部被改成非 JSON：无法确定 kid → fail-closed，按签名无效处理。"""
    token = build_token(signing_key)
    prefix, _header_b64, payload_b64, signature_b64 = token.split(".")

    result = verify_token(
        f"{prefix}.{b64url_encode(b'not-json')}.{payload_b64}.{signature_b64}"
    )

    assert result.ok is False
    assert result.error_code == ERROR_INVALID_SIGNATURE


def test_public_key_table_parsing_supports_json_and_pairs() -> None:
    pairs = parse_public_key_table("k1=abc,k2=def")
    as_json = parse_public_key_table('{"k1": "abc", "k2": "def"}')

    assert pairs == as_json == {"k1": "abc", "k2": "def"}
    assert parse_public_key_table("") == {}


def test_token_digest_is_sha256_and_never_plaintext(signing_key) -> None:
    token = build_token(signing_key)

    digest = token_digest(token)

    assert len(digest) == 64
    assert digest != token
    assert token not in digest


def _public_b64(private_key) -> str:
    from cryptography.hazmat.primitives import serialization

    return base64.urlsafe_b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode("ascii").rstrip("=")

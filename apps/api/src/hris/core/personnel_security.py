from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

if TYPE_CHECKING:
    from hris.core.config import Settings


Normalizer = Callable[[str], str]
Masker = Callable[[str], str]


class SensitiveDataError(RuntimeError):
    """A fail-closed error that never includes protected plaintext."""


@dataclass(frozen=True, slots=True)
class ProtectedValue:
    key_version: str
    nonce: bytes
    ciphertext: bytes
    masked_value: str
    search_digest: str


class SensitiveValueProtector:
    _KEY_BYTES = 32
    _NONCE_BYTES = 12

    def __init__(
        self,
        *,
        encryption_keys: Mapping[str, bytes],
        active_key_version: str,
        search_key: bytes,
    ) -> None:
        keys = dict(encryption_keys)
        if not keys:
            raise ValueError("至少配置一个人员敏感字段加密密钥")
        for version, key in keys.items():
            if not version or len(key) != self._KEY_BYTES:
                raise ValueError("人员敏感字段密钥版本不能为空且密钥必须为32字节")
        if active_key_version not in keys:
            raise ValueError("当前人员敏感字段密钥版本不存在")
        if len(search_key) != self._KEY_BYTES:
            raise ValueError("人员敏感字段检索密钥必须为32字节")
        self._encryption_keys = keys
        self._active_key_version = active_key_version
        self._search_key = search_key

    @property
    def active_key_version(self) -> str:
        return self._active_key_version

    @classmethod
    def from_base64_keys(
        cls,
        *,
        encryption_keys: Mapping[str, str],
        active_key_version: str,
        search_key: str,
    ) -> SensitiveValueProtector:
        return cls(
            encryption_keys={
                version: _decode_key(encoded)
                for version, encoded in encryption_keys.items()
            },
            active_key_version=active_key_version,
            search_key=_decode_key(search_key),
        )

    def protect(
        self,
        raw_value: str,
        *,
        field_code: str,
        record_id: UUID,
        normalizer: Normalizer,
        masker: Masker,
    ) -> ProtectedValue:
        normalized = normalizer(raw_value)
        if not normalized:
            raise ValueError("受保护字段规范化后不能为空")
        nonce = os.urandom(self._NONCE_BYTES)
        aad = self._aad(field_code=field_code, record_id=record_id)
        ciphertext = AESGCM(self._encryption_keys[self._active_key_version]).encrypt(
            nonce,
            normalized.encode("utf-8"),
            aad,
        )
        return ProtectedValue(
            key_version=self._active_key_version,
            nonce=nonce,
            ciphertext=ciphertext,
            masked_value=masker(normalized),
            search_digest=self.digest(
                normalized,
                field_code=field_code,
                normalizer=lambda value: value,
            ),
        )

    def reveal(
        self,
        protected: ProtectedValue,
        *,
        field_code: str,
        record_id: UUID,
    ) -> str:
        key = self._encryption_keys.get(protected.key_version)
        if key is None:
            raise SensitiveDataError("未知密钥版本，拒绝读取敏感字段")
        if len(protected.nonce) != self._NONCE_BYTES:
            raise SensitiveDataError("敏感字段认证失败，拒绝读取")
        try:
            plaintext = AESGCM(key).decrypt(
                protected.nonce,
                protected.ciphertext,
                self._aad(field_code=field_code, record_id=record_id),
            )
        except (InvalidTag, ValueError):
            raise SensitiveDataError("敏感字段认证失败，拒绝读取") from None
        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError:
            raise SensitiveDataError("敏感字段内容无效，拒绝读取") from None

    def digest(
        self,
        raw_value: str,
        *,
        field_code: str,
        normalizer: Normalizer,
    ) -> str:
        normalized = normalizer(raw_value)
        if not normalized:
            raise ValueError("受保护字段规范化后不能为空")
        domain_value = f"corehr:personnel:v1:{field_code}\0{normalized}".encode()
        return hmac.new(self._search_key, domain_value, hashlib.sha256).hexdigest()

    @staticmethod
    def _aad(*, field_code: str, record_id: UUID) -> bytes:
        if not field_code:
            raise ValueError("受保护字段代码不能为空")
        return f"corehr:personnel:v1:{field_code}:{record_id}".encode()


def protector_from_settings(settings: Settings) -> SensitiveValueProtector:
    if (
        not settings.personnel_encryption_keys
        or not settings.personnel_active_key_version
        or not settings.personnel_search_key
    ):
        raise SensitiveDataError("人员敏感字段密钥未完整配置")
    try:
        return SensitiveValueProtector.from_base64_keys(
            encryption_keys=settings.personnel_encryption_keys,
            active_key_version=settings.personnel_active_key_version,
            search_key=settings.personnel_search_key,
        )
    except ValueError:
        raise SensitiveDataError("人员敏感字段密钥配置无效") from None


def _decode_key(encoded: str) -> bytes:
    try:
        return base64.b64decode(encoded, altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("人员敏感字段密钥必须是有效Base64") from exc


def normalize_document_number(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def normalize_phone(value: str) -> str:
    stripped = value.strip()
    prefix = "+" if stripped.startswith("+") else ""
    return prefix + "".join(character for character in stripped if character.isdigit())


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def normalize_text(value: str) -> str:
    return value.strip()


def mask_document_number(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return value[:1] + "*" * (len(value) - 2) + value[-1:]
    suffix_length = 4 if len(value) >= 15 else 3
    visible_prefix = value[:3]
    visible_suffix = value[-suffix_length:]
    return visible_prefix + "*" * (len(value) - 3 - suffix_length) + visible_suffix


def mask_phone(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 7:
        return "*" * (len(value) - 2) + value[-2:]
    prefix_length = 3 if value.startswith("+") and len(value) > 7 else 0
    return (
        value[:prefix_length]
        + "*" * (len(value) - prefix_length - 4)
        + value[-4:]
    )


def mask_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator or not local or not domain:
        return "*" * len(value)
    return local[:1] + "*" * max(len(local) - 1, 1) + "@" + domain


def mask_text(value: str) -> str:
    if len(value) <= 2:
        return "*" * len(value)
    return value[:1] + "*" * (len(value) - 2) + value[-1:]

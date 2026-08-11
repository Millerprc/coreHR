from base64 import urlsafe_b64encode
from uuid import uuid4

import pytest

from hris.core.config import Settings
from hris.core.personnel_security import (
    ProtectedValue,
    SensitiveDataError,
    SensitiveValueProtector,
    mask_document_number,
    mask_email,
    mask_phone,
    normalize_document_number,
    normalize_email,
    normalize_phone,
    protector_from_settings,
)


def _protector() -> SensitiveValueProtector:
    return SensitiveValueProtector(
        encryption_keys={"v1": bytes(range(32)), "v2": bytes(range(32, 64))},
        active_key_version="v2",
        search_key=bytes(reversed(range(32))),
    )


def test_protected_value_uses_random_nonce_and_stable_domain_separated_digest() -> None:
    protector = _protector()
    record_id = uuid4()

    first = protector.protect(
        " 110-101 1990 0101 123X ",
        field_code="document_number",
        record_id=record_id,
        normalizer=normalize_document_number,
        masker=mask_document_number,
    )
    second = protector.protect(
        "11010119900101123x",
        field_code="document_number",
        record_id=record_id,
        normalizer=normalize_document_number,
        masker=mask_document_number,
    )

    assert first.key_version == "v2"
    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext
    assert first.search_digest == second.search_digest
    assert first.masked_value == "110***********123X"
    assert protector.reveal(
        first,
        field_code="document_number",
        record_id=record_id,
    ) == "11010119900101123X"


def test_ciphertext_tampering_or_wrong_context_fails_closed() -> None:
    protector = _protector()
    record_id = uuid4()
    protected = protector.protect(
        "13800138000",
        field_code="personal_phone",
        record_id=record_id,
        normalizer=normalize_phone,
        masker=mask_phone,
    )
    tampered = ProtectedValue(
        key_version=protected.key_version,
        nonce=protected.nonce,
        ciphertext=protected.ciphertext[:-1] + bytes([protected.ciphertext[-1] ^ 1]),
        masked_value=protected.masked_value,
        search_digest=protected.search_digest,
    )

    with pytest.raises(SensitiveDataError, match="认证失败"):
        protector.reveal(tampered, field_code="personal_phone", record_id=record_id)
    with pytest.raises(SensitiveDataError, match="认证失败"):
        protector.reveal(protected, field_code="personal_phone", record_id=uuid4())


def test_unknown_key_version_and_invalid_key_material_are_rejected() -> None:
    protector = _protector()
    protected = ProtectedValue(
        key_version="retired",
        nonce=bytes(12),
        ciphertext=bytes(32),
        masked_value="***",
        search_digest="0" * 64,
    )
    with pytest.raises(SensitiveDataError, match="未知密钥版本"):
        protector.reveal(protected, field_code="document_number", record_id=uuid4())

    with pytest.raises(ValueError, match="32字节"):
        SensitiveValueProtector(
            encryption_keys={"v1": b"short"},
            active_key_version="v1",
            search_key=bytes(32),
        )


@pytest.mark.parametrize(
    ("normalizer", "raw", "expected"),
    [
        (normalize_document_number, " ab-12 3 ", "AB123"),
        (normalize_phone, "+86 (138) 0013-8000", "+8613800138000"),
        (normalize_email, " User.Name@Example.COM ", "user.name@example.com"),
    ],
)
def test_field_normalizers_are_explicit_and_stable(normalizer, raw: str, expected: str) -> None:
    assert normalizer(raw) == expected


def test_maskers_do_not_return_original_value() -> None:
    assert mask_document_number("AB123456789") == "AB1*****789"
    assert mask_phone("+8613800138000") == "+86*******8000"
    assert mask_email("person@example.com") == "p*****@example.com"
    assert mask_document_number("AB1234") == "A****4"
    assert mask_phone("12345") == "***45"


def test_base64_key_configuration_does_not_accept_wrong_length() -> None:
    valid = urlsafe_b64encode(bytes(32)).decode()
    invalid = urlsafe_b64encode(bytes(31)).decode()

    configured = SensitiveValueProtector.from_base64_keys(
        encryption_keys={"v1": valid},
        active_key_version="v1",
        search_key=valid,
    )
    assert configured.active_key_version == "v1"

    with pytest.raises(ValueError, match="32字节"):
        SensitiveValueProtector.from_base64_keys(
            encryption_keys={"v1": invalid},
            active_key_version="v1",
            search_key=valid,
        )


def test_settings_build_protector_without_exposing_key_material() -> None:
    encoded_key = urlsafe_b64encode(bytes(32)).decode()
    settings = Settings(
        personnel_encryption_keys={"v1": encoded_key},
        personnel_active_key_version="v1",
        personnel_search_key=encoded_key,
    )
    assert protector_from_settings(settings).active_key_version == "v1"

    with pytest.raises(SensitiveDataError, match="未完整配置") as error:
        protector_from_settings(Settings())
    assert encoded_key not in str(error.value)

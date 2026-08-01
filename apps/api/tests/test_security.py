from hris.modules.platform.security import hash_password, token_digest, verify_password


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_token_digest_is_stable_without_storing_plaintext() -> None:
    digest = token_digest("opaque-token")

    assert digest == token_digest("opaque-token")
    assert digest != "opaque-token"
    assert len(digest) == 64

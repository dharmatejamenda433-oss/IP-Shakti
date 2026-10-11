from __future__ import annotations

import pytest
from ipsakti.auth.password import (
    BCRYPT_MAX_BYTES,
    PasswordTooLongError,
    hash_password,
    needs_rehash,
    verify_password,
    verify_password_dummy,
)


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True


def test_wrong_password_fails() -> None:
    hashed = hash_password("right-password")
    assert verify_password("wrong-password", hashed) is False


def test_hashes_are_salted() -> None:
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b  # distinct salts
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_over_length_password_rejected_on_hash() -> None:
    too_long = "a" * (BCRYPT_MAX_BYTES + 1)
    with pytest.raises(PasswordTooLongError):
        hash_password(too_long)


def test_verify_never_raises_on_garbage() -> None:
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("x" * 200, hash_password("y" * 10)) is False


def test_needs_rehash_false_for_fresh_hash() -> None:
    assert needs_rehash(hash_password("some-password")) is False
    assert needs_rehash("garbage") is True


def test_dummy_verify_does_not_raise() -> None:
    verify_password_dummy("whatever")
    verify_password_dummy("x" * 500)

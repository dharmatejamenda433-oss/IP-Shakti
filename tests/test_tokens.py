from __future__ import annotations

import time
import uuid

import jwt
import pytest
from ipsakti.auth.tokens import (
    ISSUER,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from ipsakti.core.config import get_settings
from ipsakti.core.errors import AuthenticationError


def _ids() -> tuple[uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), uuid.uuid4()


def test_access_token_roundtrip() -> None:
    subject, tenant = _ids()
    encoded = create_access_token(subject=subject, tenant_id=tenant)
    claims = decode_token(encoded.token, expected_type=TokenType.ACCESS)
    assert claims.subject == subject
    assert claims.tenant_id == tenant
    assert claims.token_type is TokenType.ACCESS
    assert claims.jti == encoded.jti


def test_refresh_token_roundtrip() -> None:
    subject, tenant = _ids()
    encoded = create_refresh_token(subject=subject, tenant_id=tenant)
    claims = decode_token(encoded.token, expected_type=TokenType.REFRESH)
    assert claims.token_type is TokenType.REFRESH


def test_access_token_rejected_as_refresh() -> None:
    subject, tenant = _ids()
    access = create_access_token(subject=subject, tenant_id=tenant)
    with pytest.raises(AuthenticationError):
        decode_token(access.token, expected_type=TokenType.REFRESH)


def test_expired_token_rejected() -> None:
    settings = get_settings()
    subject, tenant = _ids()
    now = int(time.time())
    claims = {
        "sub": str(subject),
        "tid": str(tenant),
        "typ": TokenType.ACCESS.value,
        "jti": uuid.uuid4().hex,
        "iat": now - 100,
        "exp": now - 1,
        "iss": ISSUER,
    }
    token = jwt.encode(claims, settings.secret_key.get_secret_value(), settings.jwt_algorithm)
    with pytest.raises(AuthenticationError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_tampered_token_rejected() -> None:
    subject, tenant = _ids()
    encoded = create_access_token(subject=subject, tenant_id=tenant)
    with pytest.raises(AuthenticationError):
        decode_token(encoded.token + "tamper", expected_type=TokenType.ACCESS)


def test_wrong_issuer_rejected() -> None:
    settings = get_settings()
    subject, tenant = _ids()
    now = int(time.time())
    claims = {
        "sub": str(subject),
        "tid": str(tenant),
        "typ": TokenType.ACCESS.value,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + 60,
        "iss": "someone-else",
    }
    token = jwt.encode(claims, settings.secret_key.get_secret_value(), settings.jwt_algorithm)
    with pytest.raises(AuthenticationError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_ttl_seconds_positive() -> None:
    subject, tenant = _ids()
    encoded = create_access_token(subject=subject, tenant_id=tenant)
    assert encoded.ttl_seconds > 0

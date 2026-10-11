"""JWT access and refresh token creation and decoding.

Tokens are signed HS256 with the application secret (never hard-coded here; it is
read from settings). Both token types carry the subject (user id) and the tenant
id, plus a unique ``jti`` used for refresh-token revocation and a ``typ`` claim so
an access token can never be replayed as a refresh token (or vice versa).

The tenant id embedded here is derived server-side from the authenticated user at
issue time. Clients never supply it, and it is re-validated against the database on
every request, so a stale or forged ``tid`` cannot grant cross-tenant access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt

from ipsakti.core.config import get_settings
from ipsakti.core.errors import AuthenticationError

ISSUER = "ipsakti"

# OAuth 2.0 token-type label returned to clients; a protocol constant, not a secret.
BEARER_TOKEN_TYPE = "bearer"  # noqa: S105


class TokenType(StrEnum):
    """Distinguishes access tokens from refresh tokens."""

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class EncodedToken:
    """A signed JWT together with the metadata needed to revoke/track it."""

    token: str
    jti: str
    expires_at: datetime

    @property
    def ttl_seconds(self) -> int:
        """Whole seconds until expiry (never negative)."""
        delta = self.expires_at - datetime.now(UTC)
        return max(0, int(delta.total_seconds()))


def _sign(
    *,
    subject: uuid.UUID,
    tenant_id: uuid.UUID,
    token_type: TokenType,
    lifetime: timedelta,
) -> EncodedToken:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + lifetime
    jti = uuid.uuid4().hex
    claims: dict[str, Any] = {
        "sub": str(subject),
        "tid": str(tenant_id),
        "typ": token_type.value,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
        "iss": ISSUER,
    }
    token = jwt.encode(claims, settings.secret_key.get_secret_value(), settings.jwt_algorithm)
    return EncodedToken(token=token, jti=jti, expires_at=expires_at)


def create_access_token(*, subject: uuid.UUID, tenant_id: uuid.UUID) -> EncodedToken:
    """Create a short-lived access token for ``subject`` within ``tenant_id``."""
    settings = get_settings()
    return _sign(
        subject=subject,
        tenant_id=tenant_id,
        token_type=TokenType.ACCESS,
        lifetime=timedelta(minutes=settings.access_token_ttl_minutes),
    )


def create_refresh_token(*, subject: uuid.UUID, tenant_id: uuid.UUID) -> EncodedToken:
    """Create a longer-lived refresh token used to mint new access tokens."""
    settings = get_settings()
    return _sign(
        subject=subject,
        tenant_id=tenant_id,
        token_type=TokenType.REFRESH,
        lifetime=timedelta(days=settings.refresh_token_ttl_days),
    )


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Validated claims extracted from a decoded token."""

    subject: uuid.UUID
    tenant_id: uuid.UUID
    token_type: TokenType
    jti: str
    expires_at: datetime


def decode_token(token: str, *, expected_type: TokenType) -> TokenClaims:
    """Decode and validate a JWT, enforcing issuer, expiry, and token type.

    Raises:
        AuthenticationError: If the token is malformed, expired, tampered with, of
            the wrong type, or missing required claims.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "jti", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("invalid token") from exc

    raw_type = payload.get("typ")
    if raw_type != expected_type.value:
        raise AuthenticationError("invalid token type")

    try:
        subject = uuid.UUID(str(payload["sub"]))
        tenant_id = uuid.UUID(str(payload["tid"]))
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("invalid token claims") from exc

    return TokenClaims(
        subject=subject,
        tenant_id=tenant_id,
        token_type=TokenType(raw_type),
        jti=str(payload["jti"]),
        expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=UTC),
    )

"""Authentication service: credential check, token issuance, refresh, revocation.

All identity and tenancy is resolved from the database here; the API layer simply
calls these functions and never constructs a principal from request bodies.

Failure modes are deliberately uniform: unknown email, wrong password, disabled
account, and suspended tenant all surface the same generic
:class:`~ipsakti.core.errors.AuthenticationError` so login cannot be used to
enumerate accounts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ipsakti.auth.password import verify_password, verify_password_dummy
from ipsakti.auth.principal import Principal
from ipsakti.auth.revocation import denylist
from ipsakti.auth.schemas import TokenResponse
from ipsakti.auth.tokens import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from ipsakti.core.errors import AuthenticationError
from ipsakti.core.logging import get_logger
from ipsakti.db.enums import TenantStatus, UserStatus
from ipsakti.db.models.identity import User

logger = get_logger(__name__)


def _token_pair(user: User) -> TokenResponse:
    access = create_access_token(subject=user.id, tenant_id=user.tenant_id)
    refresh = create_refresh_token(subject=user.id, tenant_id=user.tenant_id)
    return TokenResponse(
        access_token=access.token,
        refresh_token=refresh.token,
        expires_in=access.ttl_seconds,
    )


def authenticate(session: Session, email: str, password: str) -> User:
    """Verify credentials and return the matching active user.

    Side effect: updates ``last_login_at`` on success (committed by the caller).

    Raises:
        AuthenticationError: For any credential/eligibility failure (generic).
    """
    normalized = email.strip().lower()
    matches = list(
        session.scalars(
            select(User).where(func.lower(User.email) == normalized)
        ).all()
    )
    active = [u for u in matches if u.status == UserStatus.ACTIVE]

    if not active:
        # Equalize timing whether or not the account exists.
        verify_password_dummy(password)
        raise AuthenticationError("invalid credentials")

    if len(active) > 1:
        # Email is unique per tenant, not globally; multiple active matches mean an
        # operational ambiguity. Refuse rather than guess a tenant.
        logger.warning("ambiguous login: multiple active users share email")
        verify_password_dummy(password)
        raise AuthenticationError("invalid credentials")

    user = active[0]
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("invalid credentials")

    if user.tenant is not None and user.tenant.status != TenantStatus.ACTIVE:
        raise AuthenticationError("invalid credentials")

    user.last_login_at = datetime.now(UTC)
    session.flush()
    return user


def issue_token_pair(user: User) -> TokenResponse:
    """Mint a fresh access/refresh pair for an already-authenticated user."""
    return _token_pair(user)


def get_principal(session: Session, user_id: uuid.UUID) -> Principal:
    """Load and validate the principal for ``user_id`` (used per request).

    Raises:
        AuthenticationError: If the user is missing, disabled, or its tenant is
            suspended — i.e. the bearer token no longer maps to a valid identity.
    """
    user = session.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AuthenticationError("invalid credentials")
    if user.tenant is not None and user.tenant.status != TenantStatus.ACTIVE:
        raise AuthenticationError("invalid credentials")
    return Principal.from_user(user)


def refresh_token_pair(session: Session, refresh_token: str) -> TokenResponse:
    """Rotate a refresh token: revoke the old one and issue a new pair.

    Raises:
        AuthenticationError: If the refresh token is invalid, expired, revoked, or
            its user is no longer eligible.
    """
    claims = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    user = session.get(User, claims.subject)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AuthenticationError("invalid credentials")
    if user.tenant is not None and user.tenant.status != TenantStatus.ACTIVE:
        raise AuthenticationError("invalid credentials")

    # Atomically consume the old token after eligibility checks. A concurrent
    # refresh request in this process can no longer exchange the same token.
    if not denylist.consume_once(
        claims.jti,
        expires_at_epoch=claims.expires_at.timestamp(),
    ):
        raise AuthenticationError("token has been revoked")
    return _token_pair(user)


def revoke_refresh_token(refresh_token: str) -> None:
    """Revoke a refresh token on logout. Idempotent and tolerant of bad tokens."""
    try:
        claims = decode_token(refresh_token, expected_type=TokenType.REFRESH)
    except AuthenticationError:
        # Nothing actionable; logout still succeeds so clients can always clear state.
        return
    denylist.revoke(claims.jti, expires_at_epoch=claims.expires_at.timestamp())

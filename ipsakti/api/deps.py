"""FastAPI dependencies: database session, authenticated principal, permissions.

The principal dependency is the single place where identity is established. It
derives ``user_id`` and ``tenant_id`` from a validated access token and re-checks
them against the database — client-supplied tenant identifiers are never trusted.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ipsakti.auth.principal import Principal
from ipsakti.auth.revocation import denylist
from ipsakti.auth.service import get_principal
from ipsakti.auth.tokens import TokenType, decode_token
from ipsakti.core.errors import AuthenticationError
from ipsakti.core.request_context import set_request_context
from ipsakti.db.enums import PermissionCode

_BEARER_PREFIX = "bearer "


def get_db(request: Request) -> Iterator[Session]:
    """Yield a request-scoped Session; commit on success, roll back on error."""
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith(_BEARER_PREFIX):
        raise AuthenticationError("missing bearer token")
    token = header[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise AuthenticationError("missing bearer token")
    return token


def get_current_principal(db: DbSession, request: Request) -> Principal:
    """Resolve the authenticated principal from the request's bearer access token.

    Raises:
        AuthenticationError: If the token is absent, invalid, expired, revoked, or
            no longer maps to an eligible user/tenant.
    """
    token = _extract_bearer_token(request)
    claims = decode_token(token, expected_type=TokenType.ACCESS)
    if denylist.is_revoked(claims.jti):
        raise AuthenticationError("token has been revoked")

    principal = get_principal(db, claims.subject)
    set_request_context(user_id=str(principal.user_id), tenant_id=str(principal.tenant_id))
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_permission(permission: PermissionCode) -> Any:
    """Build a dependency that enforces ``permission`` on the current principal."""

    def _dependency(principal: CurrentPrincipal) -> Principal:
        principal.require(permission)
        return principal

    return Depends(_dependency)

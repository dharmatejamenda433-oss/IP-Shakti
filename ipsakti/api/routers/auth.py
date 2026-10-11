"""Authentication routes: login, refresh, logout."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ipsakti.api.deps import DbSession
from ipsakti.auth.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from ipsakti.auth.service import (
    authenticate,
    issue_token_pair,
    refresh_token_pair,
    revoke_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    """Exchange valid credentials for an access/refresh token pair."""
    user = authenticate(db, body.email, body.password.get_secret_value())
    return issue_token_pair(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: DbSession) -> TokenResponse:
    """Rotate a refresh token into a fresh token pair."""
    return refresh_token_pair(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest) -> Response:
    """Revoke a refresh token. Idempotent; always succeeds for the client."""
    revoke_refresh_token(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

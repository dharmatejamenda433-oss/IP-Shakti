"""Pydantic schemas for the authentication and identity API.

These are the wire contracts for ``/auth/*`` and ``/users/me``. Note that no schema
accepts a ``tenant_id`` from the client: tenancy is always derived server-side from
the authenticated principal.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ipsakti.auth.tokens import BEARER_TOKEN_TYPE
from ipsakti.db.enums import UserStatus


class LoginRequest(BaseModel):
    """Credentials submitted to obtain a token pair."""

    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """A refresh token to exchange for a fresh token pair."""

    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    """The refresh token to revoke on logout."""

    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """An issued access/refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = BEARER_TOKEN_TYPE
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class UserResponse(BaseModel):
    """The authenticated user's own profile (returned by ``/users/me``)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str | None
    status: UserStatus
    roles: list[str]

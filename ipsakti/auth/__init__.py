"""Authentication, RBAC, and tenant isolation.

Public surface used by the API layer and tests:
    * password hashing/verification (:mod:`ipsakti.auth.password`)
    * JWT access/refresh tokens (:mod:`ipsakti.auth.tokens`)
    * refresh-token revocation (:mod:`ipsakti.auth.revocation`)
    * the server-derived :class:`~ipsakti.auth.principal.Principal`
    * idempotent RBAC bootstrap (:mod:`ipsakti.auth.rbac`)
    * the auth service (:mod:`ipsakti.auth.service`)
"""

from __future__ import annotations

from ipsakti.auth.password import (
    BCRYPT_MAX_BYTES,
    hash_password,
    needs_rehash,
    verify_password,
)
from ipsakti.auth.principal import ROLE_PERMISSIONS, Principal
from ipsakti.auth.rbac import assign_role, bootstrap, ensure_permissions, ensure_roles
from ipsakti.auth.revocation import TokenDenylist, denylist
from ipsakti.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from ipsakti.auth.service import (
    authenticate,
    get_principal,
    issue_token_pair,
    refresh_token_pair,
    revoke_refresh_token,
)
from ipsakti.auth.tokens import (
    EncodedToken,
    TokenClaims,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
)

__all__ = [
    "BCRYPT_MAX_BYTES",
    "EncodedToken",
    "LoginRequest",
    "LogoutRequest",
    "Principal",
    "RefreshRequest",
    "ROLE_PERMISSIONS",
    "TokenClaims",
    "TokenDenylist",
    "TokenResponse",
    "TokenType",
    "UserResponse",
    "assign_role",
    "authenticate",
    "bootstrap",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "denylist",
    "ensure_permissions",
    "ensure_roles",
    "get_principal",
    "hash_password",
    "issue_token_pair",
    "needs_rehash",
    "refresh_token_pair",
    "revoke_refresh_token",
    "verify_password",
]

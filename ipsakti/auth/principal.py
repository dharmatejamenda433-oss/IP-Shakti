"""The authenticated principal and the default role → permission mapping.

A :class:`Principal` is the server-derived identity used for every authorization
decision. It is built from the persisted :class:`~ipsakti.db.models.identity.User`
(never from client-supplied data), so ``tenant_id`` always reflects the
authenticated user's real tenant membership.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ipsakti.core.errors import AuthorizationError
from ipsakti.db.enums import PermissionCode, RoleName, TenantStatus, UserStatus

if TYPE_CHECKING:
    from ipsakti.db.models.identity import User

# Default RBAC matrix. Roles are cumulative groupings of permission codes.
#   ADMIN   — full control, including user management.
#   MANAGER — document lifecycle + search + audit, but cannot manage users.
#   USER    — read documents and run searches.
ROLE_PERMISSIONS: dict[RoleName, frozenset[PermissionCode]] = {
    RoleName.ADMIN: frozenset(PermissionCode),
    RoleName.MANAGER: frozenset(
        {
            PermissionCode.DOCUMENT_UPLOAD,
            PermissionCode.DOCUMENT_READ,
            PermissionCode.DOCUMENT_DELETE,
            PermissionCode.SEARCH_EXECUTE,
            PermissionCode.AUDIT_READ,
        }
    ),
    RoleName.USER: frozenset(
        {
            PermissionCode.DOCUMENT_READ,
            PermissionCode.SEARCH_EXECUTE,
        }
    ),
}


@dataclass(frozen=True, slots=True)
class Principal:
    """An authenticated identity plus its effective roles and permissions."""

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    roles: frozenset[RoleName] = field(default_factory=frozenset)
    permissions: frozenset[PermissionCode] = field(default_factory=frozenset)

    def has_role(self, role: RoleName) -> bool:
        """Return True when the principal holds ``role``."""
        return role in self.roles

    def has_permission(self, permission: PermissionCode) -> bool:
        """Return True when the principal holds ``permission``."""
        return permission in self.permissions

    def require(self, permission: PermissionCode) -> None:
        """Raise :class:`AuthorizationError` unless the principal holds ``permission``."""
        if not self.has_permission(permission):
            raise AuthorizationError("insufficient permissions")

    @classmethod
    def from_user(cls, user: User) -> Principal:
        """Build a principal from a persisted user, deriving permissions from roles.

        The user must be ACTIVE and belong to an ACTIVE tenant; a disabled account
        or suspended tenant is treated as unauthorized rather than silently allowed.
        """
        if user.status != UserStatus.ACTIVE:
            raise AuthorizationError("account is disabled")
        if user.tenant is not None and user.tenant.status != TenantStatus.ACTIVE:
            raise AuthorizationError("tenant is suspended")

        roles = frozenset(role.name for role in user.roles)
        permissions: set[PermissionCode] = set()
        for role in user.roles:
            permissions.update(ROLE_PERMISSIONS.get(role.name, frozenset()))
            # Explicitly granted permissions (role_permissions) take precedence so an
            # operator can extend a role without editing ROLE_PERMISSIONS.
            permissions.update(perm.code for perm in role.permissions)

        return cls(
            user_id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            roles=roles,
            permissions=frozenset(permissions),
        )

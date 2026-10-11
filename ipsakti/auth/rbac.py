"""Idempotent RBAC bootstrap.

Seeds the global permission registry and the three built-in role templates
(``tenant_id`` NULL, so a single set of roles serves every tenant), linking each
role to its default permissions from :data:`~ipsakti.auth.principal.ROLE_PERMISSIONS`.

Running :func:`bootstrap` repeatedly is safe: existing rows are reused, never
duplicated. It does not commit — the caller controls the transaction boundary.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ipsakti.auth.principal import ROLE_PERMISSIONS
from ipsakti.db.enums import PermissionCode, RoleName
from ipsakti.db.models.identity import Permission, Role, User


def ensure_permissions(session: Session) -> dict[PermissionCode, Permission]:
    """Return every permission code, creating any that are missing."""
    existing = {row.code: row for row in session.scalars(select(Permission)).all()}
    for code in PermissionCode:
        if code not in existing:
            perm = Permission(code=code, description=f"Permission: {code.value}")
            session.add(perm)
            existing[code] = perm
    session.flush()
    return existing


def ensure_roles(session: Session) -> dict[RoleName, Role]:
    """Return the global role templates, creating any that are missing."""
    existing: dict[RoleName, Role] = {}
    for role in session.scalars(select(Role).where(Role.tenant_id.is_(None))).all():
        existing[role.name] = role
    for name in RoleName:
        if name not in existing:
            role = Role(tenant_id=None, name=name, description=f"Built-in {name.value} role")
            session.add(role)
            existing[name] = role
    session.flush()
    return existing


def bootstrap(session: Session) -> None:
    """Seed permissions, role templates, and their links (idempotent)."""
    permissions = ensure_permissions(session)
    roles = ensure_roles(session)
    for name, role in roles.items():
        desired = ROLE_PERMISSIONS.get(name, frozenset())
        current = {perm.code for perm in role.permissions}
        for code in desired - current:
            role.permissions.append(permissions[code])
    session.flush()


def assign_role(session: Session, user: User, role_name: RoleName) -> None:
    """Attach a global role template to ``user`` if not already present."""
    role = session.scalar(select(Role).where(Role.tenant_id.is_(None), Role.name == role_name))
    if role is None:
        msg = f"role template {role_name.value} has not been bootstrapped"
        raise LookupError(msg)
    if role not in user.roles:
        user.roles.append(role)
    session.flush()

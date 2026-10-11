from __future__ import annotations

import pytest
from ipsakti.auth.password import hash_password
from ipsakti.auth.principal import ROLE_PERMISSIONS, Principal
from ipsakti.auth.rbac import assign_role, bootstrap
from ipsakti.core.errors import AuthorizationError
from ipsakti.db.enums import PermissionCode, RoleName, TenantStatus, UserStatus
from ipsakti.db.models.identity import Permission, Role, Tenant, User
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _counts(session: Session) -> tuple[int, int]:
    perms = session.scalar(select(func.count()).select_from(Permission)) or 0
    roles = session.scalar(select(func.count()).select_from(Role)) or 0
    return int(perms), int(roles)


def _make_user(session: Session, *, role: RoleName, status: UserStatus = UserStatus.ACTIVE) -> User:
    bootstrap(session)
    tenant = Tenant(name="t", slug=f"s-{role.value}-{status.value}")
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id,
        email=f"{role.value.lower()}@example.com",
        password_hash=hash_password("pw-not-used-here"),
        status=status,
    )
    session.add(user)
    session.flush()
    assign_role(session, user, role)
    session.commit()
    session.refresh(user)
    return user


def test_bootstrap_seeds_permissions_and_roles(session: Session) -> None:
    bootstrap(session)
    session.commit()
    perms, roles = _counts(session)
    assert perms == len(PermissionCode)
    assert roles == len(RoleName)


def test_bootstrap_is_idempotent(session: Session) -> None:
    bootstrap(session)
    session.commit()
    first = _counts(session)
    bootstrap(session)
    session.commit()
    second = _counts(session)
    assert first == second


def test_role_permission_links_match_matrix(session: Session) -> None:
    bootstrap(session)
    session.commit()
    admin = session.scalar(select(Role).where(Role.name == RoleName.ADMIN))
    assert admin is not None
    linked = {p.code for p in admin.permissions}
    assert linked == set(ROLE_PERMISSIONS[RoleName.ADMIN])
    assert PermissionCode.USER_MANAGE in linked


def test_assign_role_is_idempotent(session: Session) -> None:
    user = _make_user(session, role=RoleName.USER)
    assign_role(session, user, RoleName.USER)
    session.commit()
    assert len(user.roles) == 1


def test_principal_derives_permissions_from_role(session: Session) -> None:
    user = _make_user(session, role=RoleName.USER)
    principal = Principal.from_user(user)
    assert principal.user_id == user.id
    assert principal.tenant_id == user.tenant_id
    assert principal.has_permission(PermissionCode.SEARCH_EXECUTE)
    assert not principal.has_permission(PermissionCode.USER_MANAGE)


def test_admin_principal_has_user_manage(session: Session) -> None:
    user = _make_user(session, role=RoleName.ADMIN)
    principal = Principal.from_user(user)
    assert principal.has_permission(PermissionCode.USER_MANAGE)
    assert principal.has_role(RoleName.ADMIN)


def test_principal_require_raises_without_permission(session: Session) -> None:
    user = _make_user(session, role=RoleName.USER)
    principal = Principal.from_user(user)
    with pytest.raises(AuthorizationError):
        principal.require(PermissionCode.USER_MANAGE)


def test_disabled_user_cannot_form_principal(session: Session) -> None:
    user = _make_user(session, role=RoleName.USER, status=UserStatus.DISABLED)
    with pytest.raises(AuthorizationError):
        Principal.from_user(user)


def test_suspended_tenant_blocks_principal(session: Session) -> None:
    user = _make_user(session, role=RoleName.USER)
    tenant = session.get(Tenant, user.tenant_id)
    assert tenant is not None
    tenant.status = TenantStatus.SUSPENDED
    session.commit()
    session.refresh(user)
    with pytest.raises(AuthorizationError):
        Principal.from_user(user)

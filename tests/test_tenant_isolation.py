"""Security tests: RBAC enforcement, tenant isolation, and identity revocation.

These assert the Phase 4 invariants from the master specification:
  * authorization checks identity + tenant + role + permission (spec 23),
  * tenancy is server-derived, never client-supplied (spec 22/24),
  * disabling a user or suspending a tenant invalidates already-issued tokens.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ipsakti.api.deps import require_permission
from ipsakti.auth.revocation import denylist
from ipsakti.core.config import get_settings
from ipsakti.db.enums import PermissionCode, RoleName, TenantStatus, UserStatus
from ipsakti.db.models.identity import Tenant, User
from sqlalchemy.orm import Session, sessionmaker

PREFIX = get_settings().api_v1_prefix


@pytest.fixture(autouse=True)
def _clean_denylist() -> Iterator[None]:
    denylist.clear()
    yield
    denylist.clear()


def _auth_header(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _login(client: TestClient, email: str, password: str) -> dict[str, Any]:
    resp = client.post(f"{PREFIX}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _add_probe(app: FastAPI) -> None:
    admin_only = require_permission(PermissionCode.USER_MANAGE)

    @app.get(f"{PREFIX}/_probe_admin", dependencies=[admin_only])
    def _probe() -> dict[str, bool]:  # pragma: no cover - trivial
        return {"ok": True}


def test_rbac_denies_user_missing_permission(
    app: FastAPI, client: TestClient, seed: Callable[..., User]
) -> None:
    _add_probe(app)
    seed("user@corp.test", "pw-user", role=RoleName.USER, slug="corp-user")
    tokens = _login(client, "user@corp.test", "pw-user")
    resp = client.get(f"{PREFIX}/_probe_admin", headers=_auth_header(tokens))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "authorization_error"


def test_rbac_allows_admin(
    app: FastAPI, client: TestClient, seed: Callable[..., User]
) -> None:
    _add_probe(app)
    seed("admin@corp.test", "pw-admin", role=RoleName.ADMIN, slug="corp-admin")
    tokens = _login(client, "admin@corp.test", "pw-admin")
    resp = client.get(f"{PREFIX}/_probe_admin", headers=_auth_header(tokens))
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_tenants_are_isolated_in_identity(
    client: TestClient, seed: Callable[..., User]
) -> None:
    a = seed("a@corp-a.test", "pw-a", slug="corp-a")
    b = seed("b@corp-b.test", "pw-b", slug="corp-b")
    assert a.tenant_id != b.tenant_id

    hdr_a = _auth_header(_login(client, "a@corp-a.test", "pw-a"))
    hdr_b = _auth_header(_login(client, "b@corp-b.test", "pw-b"))
    me_a = client.get(f"{PREFIX}/users/me", headers=hdr_a)
    me_b = client.get(f"{PREFIX}/users/me", headers=hdr_b)

    assert me_a.json()["tenant_id"] == str(a.tenant_id)
    assert me_b.json()["tenant_id"] == str(b.tenant_id)
    assert me_a.json()["tenant_id"] != me_b.json()["tenant_id"]


def test_no_client_supplied_tenant_is_honoured(
    client: TestClient, seed: Callable[..., User]
) -> None:
    # A client injecting tenant_id into the login body cannot influence identity:
    # tenancy is always taken from the authenticated user record.
    user = seed("solo@corp.test", "pw-solo", slug="corp-solo")
    resp = client.post(
        f"{PREFIX}/auth/login",
        json={"email": "solo@corp.test", "password": "pw-solo", "tenant_id": "attacker-chosen"},
    )
    assert resp.status_code == 200
    me = client.get(f"{PREFIX}/users/me", headers=_auth_header(resp.json()))
    assert me.json()["tenant_id"] == str(user.tenant_id)


def test_disabled_user_token_is_rejected(
    client: TestClient,
    seed: Callable[..., User],
    api_session_factory: sessionmaker[Session],
) -> None:
    user = seed("temp@corp.test", "pw-temp", slug="corp-temp")
    tokens = _login(client, "temp@corp.test", "pw-temp")

    with api_session_factory() as session:
        db_user = session.get(User, user.id)
        assert db_user is not None
        db_user.status = UserStatus.DISABLED
        session.commit()

    resp = client.get(f"{PREFIX}/users/me", headers=_auth_header(tokens))
    assert resp.status_code == 401


def test_suspended_tenant_token_is_rejected(
    client: TestClient,
    seed: Callable[..., User],
    api_session_factory: sessionmaker[Session],
) -> None:
    user = seed("emp@corp.test", "pw-emp", slug="corp-emp")
    tokens = _login(client, "emp@corp.test", "pw-emp")

    with api_session_factory() as session:
        tenant = session.get(Tenant, user.tenant_id)
        assert tenant is not None
        tenant.status = TenantStatus.SUSPENDED
        session.commit()

    resp = client.get(f"{PREFIX}/users/me", headers=_auth_header(tokens))
    assert resp.status_code == 401


def test_login_after_logout_still_works(client: TestClient, seed: Callable[..., User]) -> None:
    seed("re@corp.test", "pw-re", slug="corp-re")
    tokens = _login(client, "re@corp.test", "pw-re")
    client.post(f"{PREFIX}/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    # Access token remains valid until expiry; a fresh login issues new tokens.
    again = _login(client, "re@corp.test", "pw-re")
    me = client.get(f"{PREFIX}/users/me", headers=_auth_header(again))
    assert me.status_code == 200

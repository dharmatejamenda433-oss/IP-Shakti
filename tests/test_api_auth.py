from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from ipsakti.auth.revocation import denylist
from ipsakti.core.config import get_settings
from ipsakti.db.enums import RoleName
from ipsakti.db.models.identity import User

PREFIX = get_settings().api_v1_prefix


@pytest.fixture(autouse=True)
def _clean_denylist() -> Iterator[None]:
    denylist.clear()
    yield
    denylist.clear()


def _login(client: TestClient, email: str, password: str) -> Response:
    resp: Response = client.post(
        f"{PREFIX}/auth/login", json={"email": email, "password": password}
    )
    return resp


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_returns_token_pair(client: TestClient, seed: Callable[..., User]) -> None:
    seed("alice@example.com", "pw-alice", role=RoleName.USER, slug="t-alice")
    resp = _login(client, "alice@example.com", "pw-alice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0


def test_login_wrong_password_401(client: TestClient, seed: Callable[..., User]) -> None:
    seed("bob@example.com", "pw-bob", slug="t-bob")
    resp = _login(client, "bob@example.com", "nope")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_error"
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_login_unknown_user_401(client: TestClient) -> None:
    resp = _login(client, "ghost@example.com", "whatever")
    assert resp.status_code == 401


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get(f"{PREFIX}/users/me")
    assert resp.status_code == 401


def test_me_rejects_garbage_token(client: TestClient) -> None:
    resp = client.get(f"{PREFIX}/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_me_returns_own_profile(client: TestClient, seed: Callable[..., User]) -> None:
    user = seed("carol@example.com", "pw-carol", role=RoleName.MANAGER, slug="t-carol")
    tokens = _login(client, "carol@example.com", "pw-carol").json()
    resp = client.get(
        f"{PREFIX}/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "carol@example.com"
    assert body["tenant_id"] == str(user.tenant_id)
    assert body["roles"] == [RoleName.MANAGER.value]


def test_refresh_issues_new_pair_and_rotates(
    client: TestClient, seed: Callable[..., User]
) -> None:
    seed("dave@example.com", "pw-dave", slug="t-dave")
    first = _login(client, "dave@example.com", "pw-dave").json()
    resp = client.post(f"{PREFIX}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert resp.status_code == 200
    second = resp.json()
    assert second["refresh_token"] != first["refresh_token"]

    # Old refresh token is now revoked (single-use rotation).
    reuse = client.post(f"{PREFIX}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert reuse.status_code == 401


def test_logout_revokes_refresh(client: TestClient, seed: Callable[..., User]) -> None:
    seed("erin@example.com", "pw-erin", slug="t-erin")
    tokens = _login(client, "erin@example.com", "pw-erin").json()
    out = client.post(f"{PREFIX}/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204

    reuse = client.post(f"{PREFIX}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401


def test_request_id_header_echoed(client: TestClient) -> None:
    resp = client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert resp.headers.get("X-Request-ID") == "trace-123"


def test_error_body_shape(client: TestClient) -> None:
    resp = client.get(f"{PREFIX}/users/me")
    assert resp.status_code == 401
    body = resp.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message"}

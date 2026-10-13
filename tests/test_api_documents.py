"""API and security tests for document upload / read (Phase 5).

Covers the HTTP contract plus the ingestion-side security invariants: RBAC
(``document:upload``), MIME/magic/size/extension rejection at the boundary,
per-tenant duplicate detection, and IDOR/BOLA protection on reads.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ipsakti.auth.revocation import denylist
from ipsakti.core.config import get_settings
from ipsakti.db.enums import RoleName

PREFIX = get_settings().api_v1_prefix
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "storage_root", str(tmp_path))
    yield


@pytest.fixture(autouse=True)
def _clean_denylist() -> Iterator[None]:
    denylist.clear()
    yield
    denylist.clear()


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post(f"{PREFIX}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    data: dict[str, Any] | None = None,
    file: tuple[str, bytes, str] = ("doc.pdf", PDF, "application/pdf"),
) -> Any:
    filename, content, content_type = file
    form: dict[str, Any] = {"title": "Test Doc"}
    if data:
        form.update(data)
    return client.post(
        f"{PREFIX}/documents",
        headers=headers,
        data=form,
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


def test_upload_requires_authentication(client: TestClient) -> None:
    resp = client.post(
        f"{PREFIX}/documents",
        data={"title": "x"},
        files={"file": ("doc.pdf", io.BytesIO(PDF), "application/pdf")},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_error"


def test_upload_forbidden_without_permission(client: TestClient, seed: Any) -> None:
    seed("user@corp.test", "pw-user", role=RoleName.USER, slug="c-user")
    headers = _login(client, "user@corp.test", "pw-user")
    resp = _upload(client, headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "authorization_error"


def test_upload_success_returns_document_version_and_job(client: TestClient, seed: Any) -> None:
    seed("mgr@corp.test", "pw-mgr", role=RoleName.MANAGER, slug="c-mgr")
    headers = _login(client, "mgr@corp.test", "pw-mgr")
    resp = _upload(
        client,
        headers,
        data={"title": "Ayurveda Act", "document_type": "ACT", "domain": "AYURVEDA"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == "Ayurveda Act"
    assert body["document_type"] == "ACT"
    assert body["domain"] == "AYURVEDA"
    assert body["version"]["version_number"] == 1
    assert body["version"]["file_size_bytes"] == len(PDF)
    assert body["job"]["status"] == "UPLOADED"


def test_upload_rejects_non_pdf_content_type(client: TestClient, seed: Any) -> None:
    seed("a1@corp.test", "pw", role=RoleName.ADMIN, slug="c-ct")
    headers = _login(client, "a1@corp.test", "pw")
    resp = _upload(client, headers, file=("doc.pdf", PDF, "text/plain"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_upload_rejects_bad_magic_bytes(client: TestClient, seed: Any) -> None:
    seed("a2@corp.test", "pw", role=RoleName.ADMIN, slug="c-magic")
    headers = _login(client, "a2@corp.test", "pw")
    resp = _upload(client, headers, file=("doc.pdf", b"not a pdf at all", "application/pdf"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_upload_rejects_bad_extension(client: TestClient, seed: Any) -> None:
    seed("a3@corp.test", "pw", role=RoleName.ADMIN, slug="c-ext")
    headers = _login(client, "a3@corp.test", "pw")
    resp = _upload(client, headers, file=("payload.txt", PDF, "application/pdf"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_upload_rejects_oversize(
    client: TestClient, seed: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed("a4@corp.test", "pw", role=RoleName.ADMIN, slug="c-size")
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 16)
    headers = _login(client, "a4@corp.test", "pw")
    resp = _upload(client, headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_duplicate_upload_conflicts(client: TestClient, seed: Any) -> None:
    seed("a5@corp.test", "pw", role=RoleName.ADMIN, slug="c-dup")
    headers = _login(client, "a5@corp.test", "pw")
    first = _upload(client, headers)
    assert first.status_code == 201
    second = _upload(client, headers, data={"title": "Same bytes"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_same_content_allowed_in_different_tenants(client: TestClient, seed: Any) -> None:
    seed("t1@corp.test", "pw", role=RoleName.ADMIN, slug="ten-1")
    seed("t2@corp.test", "pw", role=RoleName.ADMIN, slug="ten-2")
    first = _upload(client, _login(client, "t1@corp.test", "pw"))
    second = _upload(client, _login(client, "t2@corp.test", "pw"))
    assert first.status_code == 201
    assert second.status_code == 201


def test_read_returns_own_document(client: TestClient, seed: Any) -> None:
    seed("r1@corp.test", "pw", role=RoleName.MANAGER, slug="c-read")
    headers = _login(client, "r1@corp.test", "pw")
    created = _upload(client, headers).json()
    resp = client.get(f"{PREFIX}/documents/{created['document_id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["document_id"] == created["document_id"]


def test_read_cross_tenant_is_not_found(client: TestClient, seed: Any) -> None:
    seed("owner@corp.test", "pw", role=RoleName.MANAGER, slug="ten-owner")
    seed("intruder@corp.test", "pw", role=RoleName.MANAGER, slug="ten-intruder")
    created = _upload(client, _login(client, "owner@corp.test", "pw")).json()

    intruder = _login(client, "intruder@corp.test", "pw")
    resp = client.get(f"{PREFIX}/documents/{created['document_id']}", headers=intruder)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_read_missing_document_is_not_found(client: TestClient, seed: Any) -> None:
    seed("r2@corp.test", "pw", role=RoleName.MANAGER, slug="c-miss")
    headers = _login(client, "r2@corp.test", "pw")
    resp = client.get(f"{PREFIX}/documents/{uuid4()}", headers=headers)
    assert resp.status_code == 404

"""Service-level tests for document creation and tenant-scoped reads (Phase 5)."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from ipsakti.auth.password import hash_password
from ipsakti.auth.principal import Principal
from ipsakti.core.config import get_settings
from ipsakti.core.errors import ConflictError, NotFoundError, ValidationError
from ipsakti.db.enums import DocumentStatus, DocumentType, IngestionStatus, PermissionCode, RoleName
from ipsakti.db.models.documents import Document, DocumentVersion
from ipsakti.db.models.identity import Tenant, User
from ipsakti.documents.schemas import DocumentCreate, DocumentResponse
from ipsakti.documents.service import create_document, get_document
from ipsakti.documents.storage import storage_root
from sqlalchemy import select
from sqlalchemy.orm import Session

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "storage_root", str(tmp_path))
    yield


def _principal(session: Session, *, slug: str, email: str) -> Principal:
    tenant = Tenant(name=slug, slug=slug)
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id,
        email=email,
        full_name="uploader",
        password_hash=hash_password("pw-unused"),
    )
    session.add(user)
    session.flush()
    return Principal(
        user_id=user.id,
        tenant_id=tenant.id,
        email=email,
        roles=frozenset({RoleName.ADMIN}),
        permissions=frozenset(PermissionCode),
    )


def _upload(session: Session, principal: Principal, *, title: str = "Doc") -> DocumentResponse:
    return create_document(
        session=session,
        principal=principal,
        metadata=DocumentCreate(title=title, document_type=DocumentType.ACT),
        file_stream=io.BytesIO(PDF),
        declared_content_type="application/pdf",
        original_filename="doc.pdf",
    )


def test_create_document_persists_document_version_and_job(session: Session) -> None:
    principal = _principal(session, slug="t-create", email="c@corp.test")
    resp = _upload(session, principal, title="Ayurveda Act")

    assert resp.title == "Ayurveda Act"
    assert resp.document_type == DocumentType.ACT
    assert resp.status == DocumentStatus.ACTIVE
    assert resp.version.version_number == 1
    assert resp.version.file_sha256 == hashlib.sha256(PDF).hexdigest()
    assert resp.version.mime_type == "application/pdf"
    assert resp.job is not None
    assert resp.job.status == IngestionStatus.UPLOADED

    document = session.get(Document, resp.document_id)
    assert document is not None
    assert document.tenant_id == principal.tenant_id
    assert document.created_by == principal.user_id

    version = session.get(DocumentVersion, resp.version.version_id)
    assert version is not None
    assert version.is_current is True
    assert (storage_root() / version.file_path).exists()


def test_duplicate_content_within_tenant_conflicts(session: Session, tmp_path: Path) -> None:
    principal = _principal(session, slug="t-dup", email="d@corp.test")
    _upload(session, principal)
    committed_before = set(tmp_path.rglob("*.pdf"))

    with pytest.raises(ConflictError):
        _upload(session, principal, title="Same bytes again")

    assert set(tmp_path.rglob("*.pdf")) == committed_before
    assert list(tmp_path.rglob("*.part")) == []


def test_same_content_allowed_across_different_tenants(session: Session) -> None:
    a = _principal(session, slug="t-a", email="a@a.test")
    b = _principal(session, slug="t-b", email="b@b.test")
    first = _upload(session, a)
    second = _upload(session, b)
    assert first.version.file_sha256 == second.version.file_sha256
    assert first.document_id != second.document_id


def test_rejects_non_pdf_before_touching_storage(session: Session) -> None:
    principal = _principal(session, slug="t-bad", email="bad@corp.test")
    with pytest.raises(ValidationError):
        create_document(
            session=session,
            principal=principal,
            metadata=DocumentCreate(title="Nope"),
            file_stream=io.BytesIO(b"plain text, not a pdf"),
            declared_content_type="application/pdf",
            original_filename="nope.pdf",
        )
    assert session.execute(select(Document)).scalars().all() == []


def test_get_document_is_tenant_scoped(session: Session) -> None:
    owner = _principal(session, slug="t-owner", email="o@corp.test")
    other = _principal(session, slug="t-other", email="x@corp.test")
    created = _upload(session, owner)

    fetched = get_document(session=session, principal=owner, document_id=created.document_id)
    assert fetched.document_id == created.document_id

    with pytest.raises(NotFoundError):
        get_document(session=session, principal=other, document_id=created.document_id)


def test_get_document_missing_is_not_found(session: Session) -> None:
    principal = _principal(session, slug="t-missing", email="m@corp.test")
    with pytest.raises(NotFoundError):
        get_document(session=session, principal=principal, document_id=uuid4())

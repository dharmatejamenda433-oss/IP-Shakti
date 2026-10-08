"""Tests for the SQLAlchemy ORM models (Phase 3)."""

from __future__ import annotations

import uuid

import pytest
from ipsakti.db.base import Base
from ipsakti.db.enums import (
    AuditAction,
    AuditResult,
    DocumentStatus,
    DocumentType,
    Domain,
    IngestionStatus,
    PermissionCode,
    RoleName,
    TenantStatus,
    UserStatus,
)
from ipsakti.db.models import (
    AuditLog,
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
    Permission,
    Role,
    Tenant,
    User,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

EXPECTED_TABLES = {
    "tenants",
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "documents",
    "document_versions",
    "document_chunks",
    "ingestion_jobs",
    "audit_logs",
}


def test_all_expected_tables_registered() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))


def test_uuid_primary_keys_generated(session: Session) -> None:
    tenant = Tenant(name="Acme", slug="acme")
    session.add(tenant)
    session.flush()
    assert isinstance(tenant.id, uuid.UUID)


def test_tenant_slug_unique(session: Session) -> None:
    session.add_all([Tenant(name="A", slug="dup"), Tenant(name="B", slug="dup")])
    with pytest.raises(IntegrityError):
        session.flush()


def test_user_email_unique_per_tenant(session: Session) -> None:
    t1 = Tenant(name="T1", slug="t1")
    t2 = Tenant(name="T2", slug="t2")
    session.add_all([t1, t2])
    session.flush()
    session.add_all(
        [
            User(tenant_id=t1.id, email="a@x.com", password_hash="h"),
            User(tenant_id=t2.id, email="a@x.com", password_hash="h"),
        ]
    )
    session.flush()  # same email, different tenants → allowed
    session.add(User(tenant_id=t1.id, email="a@x.com", password_hash="h"))
    with pytest.raises(IntegrityError):
        session.flush()  # duplicate within tenant → rejected


def test_enum_values_persist_as_member_values(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-enum", status=TenantStatus.ACTIVE)
    perm = Permission(code=PermissionCode.DOCUMENT_UPLOAD)
    session.add_all([tenant, perm])
    session.flush()
    row = session.connection().exec_driver_sql(
        "SELECT status FROM tenants WHERE slug = 't-enum'"
    ).scalar_one()
    assert row == "ACTIVE"
    prow = session.connection().exec_driver_sql(
        "SELECT code FROM permissions"
    ).scalar_one()
    assert prow == "document:upload"


def test_user_role_permission_relationships(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-rbac")
    session.add(tenant)
    session.flush()

    role = Role(tenant_id=tenant.id, name=RoleName.ADMIN)
    perm = Permission(code=PermissionCode.SEARCH_EXECUTE)
    role.permissions.append(perm)
    user = User(tenant_id=tenant.id, email="admin@x.com", password_hash="h")
    user.roles.append(role)
    session.add_all([role, perm, user])
    session.flush()
    session.refresh(user)

    assert user.roles[0].name is RoleName.ADMIN
    assert user.roles[0].permissions[0].code is PermissionCode.SEARCH_EXECUTE
    assert tenant.users[0].email == "admin@x.com"


def test_document_version_chunk_cascade(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-doc")
    session.add(tenant)
    session.flush()
    doc = Document(
        tenant_id=tenant.id,
        title="The Patents Act, 1970",
        document_type=DocumentType.ACT,
        domain=Domain.PATENTS,
        jurisdiction="IN",
        status=DocumentStatus.ACTIVE,
    )
    session.add(doc)
    session.flush()
    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path="/data/x.pdf",
        file_sha256="abc123",
        file_size_bytes=1024,
        mime_type="application/pdf",
        is_current=True,
    )
    session.add(version)
    session.flush()
    chunk = DocumentChunk(
        version_id=version.id,
        chunk_id="patents-1970:v1:0001",
        ordinal=1,
        text="Section 3(d) ...",
        page_start=10,
        page_end=10,
        section="3",
        subsection="3(d)",
    )
    session.add(chunk)
    session.flush()

    session.refresh(doc)
    assert doc.versions[0].chunks[0].chunk_id == "patents-1970:v1:0001"

    # Deleting the document cascades to versions and chunks.
    session.delete(doc)
    session.flush()
    assert session.query(DocumentVersion).count() == 0
    assert session.query(DocumentChunk).count() == 0


def test_chunk_id_globally_unique(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-chunk-uq")
    session.add(tenant)
    session.flush()
    doc = Document(
        tenant_id=tenant.id,
        title="D",
        document_type=DocumentType.OTHER,
        domain=Domain.OTHER,
    )
    session.add(doc)
    session.flush()
    v = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path="/d.pdf",
        file_sha256="s",
        file_size_bytes=1,
        mime_type="application/pdf",
    )
    session.add(v)
    session.flush()
    session.add(DocumentChunk(version_id=v.id, chunk_id="same", ordinal=1, text="a"))
    session.flush()
    session.add(DocumentChunk(version_id=v.id, chunk_id="same", ordinal=2, text="b"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_document_version_number_unique_per_document(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-vernum")
    session.add(tenant)
    session.flush()
    doc = Document(
        tenant_id=tenant.id,
        title="D",
        document_type=DocumentType.OTHER,
        domain=Domain.OTHER,
    )
    session.add(doc)
    session.flush()
    for _ in range(2):
        session.add(
            DocumentVersion(
                document_id=doc.id,
                version_number=1,
                file_path="/d.pdf",
                file_sha256="s",
                file_size_bytes=1,
                mime_type="application/pdf",
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()


def test_ingestion_job_state_machine_defaults(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-job")
    session.add(tenant)
    session.flush()
    doc = Document(
        tenant_id=tenant.id,
        title="D",
        document_type=DocumentType.OTHER,
        domain=Domain.OTHER,
    )
    session.add(doc)
    session.flush()
    v = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path="/d.pdf",
        file_sha256="s",
        file_size_bytes=1,
        mime_type="application/pdf",
    )
    session.add(v)
    session.flush()
    job = IngestionJob(document_version_id=v.id)
    session.add(job)
    session.flush()
    assert job.status is IngestionStatus.UPLOADED
    assert job.attempt_count == 0
    assert job.max_attempts == 3

    job.status = IngestionStatus.COMPLETED
    session.flush()
    session.refresh(job)
    assert job.status is IngestionStatus.COMPLETED


def test_audit_log_roundtrip(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-audit")
    session.add(tenant)
    session.flush()
    log = AuditLog(
        tenant_id=tenant.id,
        action=AuditAction.LOGIN,
        result=AuditResult.SUCCESS,
        request_id="req-1",
        detail={"endpoint": "/auth/login"},
    )
    session.add(log)
    session.flush()
    session.refresh(log)
    assert log.action is AuditAction.LOGIN
    assert log.detail == {"endpoint": "/auth/login"}


def test_timestamps_are_populated(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-ts")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    assert tenant.created_at is not None
    assert tenant.updated_at is not None


def test_foreign_keys_present() -> None:
    fk_cols = {
        col.name
        for col in Base.metadata.tables["documents"].columns
        if col.foreign_keys
    }
    assert {"tenant_id", "created_by"}.issubset(fk_cols)


def test_default_statuses(session: Session) -> None:
    tenant = Tenant(name="T", slug="t-defaults")
    session.add(tenant)
    session.flush()
    user = User(tenant_id=tenant.id, email="u@x.com", password_hash="h")
    session.add(user)
    session.flush()
    assert tenant.status is TenantStatus.ACTIVE
    assert user.status is UserStatus.ACTIVE

"""Document upload orchestration (Phase 5).

Single entry point that turns an authenticated multipart upload into durable
state: validate → stage the bytes (hash/size/magic) → reject per-tenant duplicates
→ commit the file atomically → create ``Document`` + current ``DocumentVersion`` +
``IngestionJob(UPLOADED)``. It also provides the tenant-scoped read used to fetch
an uploaded document's status.

The tenant is always taken from the principal, never from the request payload, and
any cross-tenant read is reported as ``not found`` so direct-id manipulation cannot
probe another tenant's catalogue (IDOR/BOLA protection).
"""

from __future__ import annotations

from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ipsakti.auth.principal import Principal
from ipsakti.core.config import get_settings
from ipsakti.core.errors import ConflictError, NotFoundError
from ipsakti.db.enums import DocumentStatus, IngestionStatus
from ipsakti.db.models.documents import Document, DocumentVersion, IngestionJob
from ipsakti.documents.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentVersionInfo,
    IngestionJobInfo,
)
from ipsakti.documents.storage import (
    build_relative_path,
    commit_staged,
    discard_staged,
    remove_stored,
    stage_pdf_stream,
)
from ipsakti.documents.validation import (
    validate_content_type,
    validate_filename_extension,
)

_INITIAL_VERSION_NUMBER = 1
_DEFAULT_MAX_ATTEMPTS = 3


def build_document_response(
    document: Document,
    version: DocumentVersion,
    job: IngestionJob | None,
) -> DocumentResponse:
    """Assemble the client-facing response from the three persisted rows."""
    return DocumentResponse(
        document_id=document.id,
        tenant_id=document.tenant_id,
        title=document.title,
        document_type=document.document_type,
        domain=document.domain,
        status=document.status,
        version=DocumentVersionInfo(
            version_id=version.id,
            version_number=version.version_number,
            file_sha256=version.file_sha256,
            file_size_bytes=version.file_size_bytes,
            mime_type=version.mime_type,
            page_count=version.page_count,
        ),
        job=(
            IngestionJobInfo(
                job_id=job.id,
                status=job.status,
                attempt_count=job.attempt_count,
                error_message=job.error_message,
            )
            if job is not None
            else None
        ),
    )


def _reject_duplicate(session: Session, *, tenant_id: UUID, sha256: str) -> None:
    """Raise if identical content already exists within this tenant."""
    existing = session.execute(
        select(DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.tenant_id == tenant_id, DocumentVersion.file_sha256 == sha256)
        .limit(1),
    ).first()
    if existing is not None:
        raise ConflictError("a document with identical content already exists in this tenant")


def create_document(
    *,
    session: Session,
    principal: Principal,
    metadata: DocumentCreate,
    file_stream: BinaryIO,
    declared_content_type: str | None,
    original_filename: str | None,
) -> DocumentResponse:
    """Validate, store, and persist a new document version and its ingestion job.

    Raises:
        ValidationError: On a bad MIME type, filename, signature, empty file, or
            oversized upload.
        ConflictError: If the same content already exists in the tenant.
    """
    normalized_mime = validate_content_type(declared_content_type)
    validate_filename_extension(original_filename)

    document_id = uuid4()
    version_id = uuid4()
    relative_path = build_relative_path(
        tenant_id=principal.tenant_id,
        document_id=document_id,
        version_number=_INITIAL_VERSION_NUMBER,
    )

    staged = stage_pdf_stream(
        file_stream,
        relative_path=relative_path,
        max_bytes=get_settings().max_upload_bytes,
    )
    try:
        _reject_duplicate(session, tenant_id=principal.tenant_id, sha256=staged.sha256)
    except BaseException:
        discard_staged(staged)
        raise

    stored = commit_staged(staged)
    try:
        document = Document(
            id=document_id,
            tenant_id=principal.tenant_id,
            title=metadata.title,
            source=metadata.source,
            authority=metadata.authority,
            document_type=metadata.document_type,
            domain=metadata.domain,
            jurisdiction=metadata.jurisdiction,
            country=metadata.country,
            language=metadata.language,
            publication_date=metadata.publication_date,
            effective_date=metadata.effective_date,
            status=DocumentStatus.ACTIVE,
            created_by=principal.user_id,
        )
        version = DocumentVersion(
            id=version_id,
            document_id=document_id,
            version_number=_INITIAL_VERSION_NUMBER,
            version_label=f"v{_INITIAL_VERSION_NUMBER}",
            file_path=stored.relative_path,
            file_sha256=stored.sha256,
            file_size_bytes=stored.size_bytes,
            mime_type=normalized_mime,
            is_current=True,
        )
        job = IngestionJob(
            document_version_id=version_id,
            status=IngestionStatus.UPLOADED,
            attempt_count=0,
            max_attempts=_DEFAULT_MAX_ATTEMPTS,
        )
        session.add(document)
        session.add(version)
        session.add(job)
        session.flush()
    except BaseException:
        remove_stored(stored.path)
        raise

    return build_document_response(document, version, job)


def get_document(*, session: Session, principal: Principal, document_id: UUID) -> DocumentResponse:
    """Return a document with its current version and latest job, tenant-scoped.

    Raises:
        NotFoundError: If the document does not exist, has no current version, or
            belongs to a different tenant (reported identically to a true miss).
    """
    document = session.get(Document, document_id)
    if document is None or document.tenant_id != principal.tenant_id:
        raise NotFoundError("document not found")

    version = session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.is_current.is_(True),
        ),
    ).scalar_one_or_none()
    if version is None:
        raise NotFoundError("document not found")

    job = session.execute(
        select(IngestionJob)
        .join(DocumentVersion, IngestionJob.document_version_id == DocumentVersion.id)
        .where(DocumentVersion.document_id == document_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(1),
    ).scalar_one_or_none()

    return build_document_response(document, version, job)

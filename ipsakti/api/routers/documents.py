"""Document upload and status routes (Phase 5).

``POST /documents`` accepts a multipart PDF plus descriptive form fields, enforces
the ``document:upload`` permission, and returns the created document, its current
version, and the initial ingestion job. ``GET /documents/{id}`` returns the same
view for the caller's tenant only.

All authorization is via :func:`require_permission`; identity and tenant come from
the authenticated principal, never from the request body.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Form, UploadFile, status

from ipsakti.api.deps import CurrentPrincipal, DbSession, require_permission
from ipsakti.auth.principal import Principal
from ipsakti.db.enums import DocumentType, Domain, PermissionCode
from ipsakti.documents.schemas import DocumentCreate, DocumentResponse
from ipsakti.documents.service import create_document, get_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    db: DbSession,
    principal: CurrentPrincipal,
    _authorized: Annotated[Principal, require_permission(PermissionCode.DOCUMENT_UPLOAD)],
    file: UploadFile,
    title: Annotated[str, Form(min_length=1, max_length=500)],
    source: Annotated[str | None, Form(max_length=255)] = None,
    authority: Annotated[str | None, Form(max_length=255)] = None,
    document_type: Annotated[DocumentType, Form()] = DocumentType.OTHER,
    domain: Annotated[Domain, Form()] = Domain.OTHER,
    jurisdiction: Annotated[str | None, Form(max_length=100)] = None,
    country: Annotated[str | None, Form(max_length=100)] = None,
    language: Annotated[str, Form(min_length=2, max_length=16)] = "en",
    publication_date: Annotated[date | None, Form()] = None,
    effective_date: Annotated[date | None, Form()] = None,
) -> DocumentResponse:
    """Validate, store, and register an uploaded PDF for asynchronous ingestion."""
    metadata = DocumentCreate(
        title=title,
        source=source,
        authority=authority,
        document_type=document_type,
        domain=domain,
        jurisdiction=jurisdiction,
        country=country,
        language=language,
        publication_date=publication_date,
        effective_date=effective_date,
    )
    return create_document(
        session=db,
        principal=principal,
        metadata=metadata,
        file_stream=file.file,
        declared_content_type=file.content_type,
        original_filename=file.filename,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def read_document(
    document_id: UUID,
    db: DbSession,
    principal: CurrentPrincipal,
    _authorized: Annotated[Principal, require_permission(PermissionCode.DOCUMENT_READ)],
) -> DocumentResponse:
    """Return a document's current version and latest ingestion status."""
    return get_document(session=db, principal=principal, document_id=document_id)

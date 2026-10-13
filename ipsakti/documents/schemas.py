"""Request/response schemas for the document upload boundary (Phase 5).

The upload endpoint is multipart: the PDF binary arrives as a file part and the
descriptive metadata arrives as form fields. ``DocumentCreate`` is the validated
metadata container handed to the service; ``DocumentResponse`` is the stable
contract returned to clients (document + current version + ingestion job).

Tenancy is never part of any request schema — it is derived server-side from the
authenticated principal (ADR 0005), so no field here accepts a client tenant id.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ipsakti.db.enums import DocumentStatus, DocumentType, Domain, IngestionStatus


class DocumentCreate(BaseModel):
    """Validated document metadata supplied by the uploader."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    source: str | None = Field(default=None, max_length=255)
    authority: str | None = Field(default=None, max_length=255)
    document_type: DocumentType = DocumentType.OTHER
    domain: Domain = Domain.OTHER
    jurisdiction: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    language: str = Field(default="en", min_length=2, max_length=16)
    publication_date: date | None = None
    effective_date: date | None = None


class DocumentVersionInfo(BaseModel):
    """The stored-file facts for a document version."""

    model_config = ConfigDict(from_attributes=True)

    version_id: UUID
    version_number: int
    file_sha256: str
    file_size_bytes: int
    mime_type: str
    page_count: int | None


class IngestionJobInfo(BaseModel):
    """The ingestion state machine position for a document version."""

    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: IngestionStatus
    attempt_count: int
    error_message: str | None


class DocumentResponse(BaseModel):
    """Combined view returned by upload and read endpoints."""

    document_id: UUID
    tenant_id: UUID
    title: str
    document_type: DocumentType
    domain: Domain
    status: DocumentStatus
    version: DocumentVersionInfo
    job: IngestionJobInfo | None

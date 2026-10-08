"""Document, version, chunk, and ingestion-job models.

PostgreSQL is the system of record (ADR 0001). Every chunk belongs to a document
version, so versions are never mixed and citations resolve to a specific version.
Ingestion jobs carry the state machine used by the worker (ADR 0002).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ipsakti.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from ipsakti.db.enums import (
    DocumentStatus,
    DocumentType,
    Domain,
    IngestionStatus,
    sa_enum,
)

if TYPE_CHECKING:
    from ipsakti.db.models.identity import Tenant, User


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A logical document with full source provenance metadata."""

    __tablename__ = "documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255))
    authority: Mapped[str | None] = mapped_column(String(255))
    document_type: Mapped[DocumentType] = mapped_column(
        sa_enum(DocumentType, "document_type"),
        nullable=False,
        default=DocumentType.OTHER,
    )
    domain: Mapped[Domain] = mapped_column(
        sa_enum(Domain, "domain"),
        nullable=False,
        default=Domain.OTHER,
    )
    jurisdiction: Mapped[str | None] = mapped_column(String(100), index=True)
    country: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    publication_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[DocumentStatus] = mapped_column(
        sa_enum(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.ACTIVE,
    )
    source_url: Mapped[str | None] = mapped_column(String(2048))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="documents")
    creator: Mapped[User | None] = relationship()
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentVersion.version_number",
    )


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An immutable, versioned snapshot of a document's stored file."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="document_version_number"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    document: Mapped[Document] = relationship(back_populates="versions")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.ordinal",
    )
    ingestion_jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    """A structure-aware chunk belonging to a specific document version."""

    __tablename__ = "document_chunks"

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Deterministic, globally unique chunk identifier (see spec §10).
    chunk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(500))
    subsection: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    version: Mapped[DocumentVersion] = relationship(back_populates="chunks")


class IngestionJob(UUIDPrimaryKeyMixin, Base):
    """A unit of ingestion work tracked by an explicit state machine."""

    __tablename__ = "ingestion_jobs"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[IngestionStatus] = mapped_column(
        sa_enum(IngestionStatus, "ingestion_status"),
        nullable=False,
        default=IngestionStatus.UPLOADED,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(255))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    version: Mapped[DocumentVersion] = relationship(back_populates="ingestion_jobs")

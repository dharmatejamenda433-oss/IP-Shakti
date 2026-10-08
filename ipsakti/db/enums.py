"""Status/type enumerations and a portable SQLAlchemy enum helper.

Enums are persisted as VARCHAR with a CHECK constraint (``native_enum=False``) so
that the same DDL runs unchanged on PostgreSQL (production) and SQLite (unit
tests), and so Alembic migrations stay portable. The stored value is the enum
member's ``value`` (via ``values_callable``), which keeps permission codes such as
``document:upload`` intact in the database.
"""

from __future__ import annotations

from enum import Enum, StrEnum

from sqlalchemy import Enum as SAEnum


class TenantStatus(StrEnum):
    """Lifecycle status of a tenant."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class UserStatus(StrEnum):
    """Lifecycle status of a user account."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class RoleName(StrEnum):
    """Built-in RBAC roles."""

    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    USER = "USER"


class PermissionCode(StrEnum):
    """RBAC permission codes."""

    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE = "document:delete"
    SEARCH_EXECUTE = "search:execute"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"


class DocumentType(StrEnum):
    """Kind of source document."""

    ACT = "ACT"
    RULES = "RULES"
    GUIDELINES = "GUIDELINES"
    TREATY = "TREATY"
    CASE_LAW = "CASE_LAW"
    REGULATION = "REGULATION"
    OTHER = "OTHER"


class Domain(StrEnum):
    """Knowledge domain of a document."""

    PATENTS = "PATENTS"
    AYUSH = "AYUSH"
    DRUGS = "DRUGS"
    BIODIVERSITY = "BIODIVERSITY"
    AYURVEDA = "AYURVEDA"
    CASE_LAW = "CASE_LAW"
    INTERNATIONAL = "INTERNATIONAL"
    TRADITIONAL_KNOWLEDGE = "TRADITIONAL_KNOWLEDGE"
    OTHER = "OTHER"


class DocumentStatus(StrEnum):
    """Lifecycle status of a logical document."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class IngestionStatus(StrEnum):
    """Ingestion job state machine."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    CHUNKED = "CHUNKED"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditAction(StrEnum):
    """Auditable actions."""

    LOGIN = "LOGIN"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_DELETE = "DOCUMENT_DELETE"
    SEARCH = "SEARCH"
    CHAT = "CHAT"
    USER_CHANGE = "USER_CHANGE"


class AuditResult(StrEnum):
    """Outcome of an audited action."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


def sa_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Build a portable, value-storing SQLAlchemy Enum type.

    Args:
        enum_cls: The Python enum class.
        name: The database type/constraint name.

    Returns:
        A SQLAlchemy ``Enum`` configured for VARCHAR+CHECK storage of member values.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda e: [member.value for member in e],
        validate_strings=True,
        length=max(len(str(member.value)) for member in enum_cls),
    )

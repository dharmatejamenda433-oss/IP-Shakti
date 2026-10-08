"""Audit log model.

Records important actions (spec §32). Audit rows are append-only; the ``detail``
JSON column must never contain secrets or raw credentials.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from ipsakti.db.base import Base, UUIDPrimaryKeyMixin
from ipsakti.db.enums import AuditAction, AuditResult, sa_enum


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """An immutable record of an auditable action."""

    __tablename__ = "audit_logs"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    action: Mapped[AuditAction] = mapped_column(
        sa_enum(AuditAction, "audit_action"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(128))
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    result: Mapped[AuditResult] = mapped_column(
        sa_enum(AuditResult, "audit_result"),
        nullable=False,
        default=AuditResult.SUCCESS,
    )
    detail: Mapped[dict[str, object] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

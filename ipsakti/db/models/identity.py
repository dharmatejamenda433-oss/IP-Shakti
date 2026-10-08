"""Identity, tenancy, and RBAC models.

Tables: tenants, users, roles, permissions, and the user_roles / role_permissions
associations. Roles are tenant-scoped (a null tenant_id denotes a system role
template). Permissions are a global registry referenced by role_permissions.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Table,
    Column,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from ipsakti.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from ipsakti.db.enums import PermissionCode, RoleName, TenantStatus, UserStatus, sa_enum

if TYPE_CHECKING:
    from ipsakti.db.models.documents import Document

# --- Association tables -----------------------------------------------------

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Uuid,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# --- Models -----------------------------------------------------------------


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tenant — the hard isolation boundary for all resources."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[TenantStatus] = mapped_column(
        sa_enum(TenantStatus, "tenant_status"),
        nullable=False,
        default=TenantStatus.ACTIVE,
    )

    users: Mapped[list[User]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    roles: Mapped[list[Role]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An authenticated identity belonging to exactly one tenant."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="tenant_email"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        sa_enum(UserStatus, "user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tenant-scoped role grouping permissions."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="tenant_name"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[RoleName] = mapped_column(sa_enum(RoleName, "role_name"), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    tenant: Mapped[Tenant | None] = relationship(back_populates="roles")
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin",
    )


class Permission(UUIDPrimaryKeyMixin, Base):
    """A global permission code that can be granted to roles."""

    __tablename__ = "permissions"

    code: Mapped[PermissionCode] = mapped_column(
        sa_enum(PermissionCode, "permission_code"),
        unique=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions,
        back_populates="permissions",
    )

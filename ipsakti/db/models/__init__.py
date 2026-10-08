"""ORM models.

Importing this package registers every model on ``Base.metadata`` so Alembic
autogenerate and ``create_all`` see the full schema.
"""

from __future__ import annotations

from ipsakti.db.models.audit import AuditLog
from ipsakti.db.models.documents import (
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
)
from ipsakti.db.models.identity import (
    Permission,
    Role,
    Tenant,
    User,
    role_permissions,
    user_roles,
)

__all__ = [
    "AuditLog",
    "Document",
    "DocumentChunk",
    "DocumentVersion",
    "IngestionJob",
    "Permission",
    "Role",
    "Tenant",
    "User",
    "role_permissions",
    "user_roles",
]

"""HTTP API layer: FastAPI app factory, /api/v1 routers, dependencies, SSE.

Phase 4 introduces the application factory and the auth/users routes. Later phases
add documents, search, chat (SSE), and audit routers here.
"""

from __future__ import annotations

from ipsakti.api.app import create_app

__all__ = ["create_app"]

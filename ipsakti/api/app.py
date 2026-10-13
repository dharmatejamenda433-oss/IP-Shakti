"""FastAPI application factory.

Keeps infrastructure concerns (DB session factory, error translation, request-id
propagation) in one place so the same app can be built against PostgreSQL in
production or an in-memory SQLite engine in tests.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from ipsakti.api.errors import register_error_handlers
from ipsakti.api.middleware import RequestContextMiddleware
from ipsakti.api.routers import auth as auth_router
from ipsakti.api.routers import documents as documents_router
from ipsakti.api.routers import users as users_router
from ipsakti.core.config import get_settings
from ipsakti.core.logging import configure_logging
from ipsakti.db.session import create_db_engine, create_session_factory


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    """Build and return a configured FastAPI application.

    Args:
        session_factory: Optional override for the DB session factory. When omitted,
            one is created from settings (PostgreSQL). Tests inject an in-memory
            SQLite factory.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="IP-SAKTI", version="0.1.0", docs_url="/docs")

    if session_factory is None:
        engine = create_db_engine()
        session_factory = create_session_factory(engine)
        app.state.engine = engine
    app.state.session_factory = session_factory

    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    app.include_router(auth_router.router, prefix=settings.api_v1_prefix)
    app.include_router(users_router.router, prefix=settings.api_v1_prefix)
    app.include_router(documents_router.router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, Any]:
        """Liveness probe."""
        return {"status": "ok"}

    return app

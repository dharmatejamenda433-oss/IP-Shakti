"""Database engine and session management.

Provides an engine and a session factory built from application settings, plus a
``session_scope`` context manager that commits on success and rolls back on error.
The FastAPI dependency and the worker both use ``session_scope`` so transaction
boundaries are explicit and consistent.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from ipsakti.core.config import get_settings


def create_db_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy Engine.

    Args:
        url: Database URL. Defaults to ``settings.database_url``.
        echo: When True, echo SQL (development/debug only).

    Returns:
        A configured :class:`sqlalchemy.Engine`.
    """
    settings = get_settings()
    db_url = url or settings.database_url
    return create_engine(db_url, echo=echo, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a Session factory bound to an engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Commits on clean exit, rolls back on exception, and always closes the session.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

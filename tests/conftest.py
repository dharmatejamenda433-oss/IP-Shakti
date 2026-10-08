"""Shared pytest fixtures for the IP-SAKTI test suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from ipsakti.db import models  # noqa: F401  (register all models on Base.metadata)
from ipsakti.db.base import Base
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Provide an in-memory SQLite engine with the full schema created.

    The ORM models use portable types (Uuid, JSON, CHECK-constrained enums) so the
    same schema definitions run on SQLite here and PostgreSQL in production.
    """
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Provide a Session bound to the in-memory engine."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()

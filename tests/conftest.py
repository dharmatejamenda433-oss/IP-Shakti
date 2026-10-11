"""Shared pytest fixtures for the IP-SAKTI test suite."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ipsakti.auth.password import hash_password
from ipsakti.auth.rbac import assign_role, bootstrap
from ipsakti.db import models  # noqa: F401  (register all models on Base.metadata)
from ipsakti.db.base import Base
from ipsakti.db.enums import RoleName
from ipsakti.db.models.identity import Tenant, User
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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


# --- API fixtures -----------------------------------------------------------
#
# The ASGI app runs endpoints in a worker thread, so the in-memory database must
# be pinned to a single shared connection (StaticPool) that ignores thread affinity.


@pytest.fixture
def api_engine() -> Iterator[Engine]:
    """Provide a thread-shared in-memory SQLite engine with RBAC bootstrapped."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False, future=True)
    with factory() as sess:
        bootstrap(sess)
        sess.commit()
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def api_session_factory(api_engine: Engine) -> sessionmaker[Session]:
    """Provide a Session factory bound to the shared API engine."""
    return sessionmaker(bind=api_engine, autoflush=False, expire_on_commit=False, future=True)


@pytest.fixture
def app(api_session_factory: sessionmaker[Session]) -> FastAPI:
    """Build a FastAPI app wired to the in-memory session factory."""
    from ipsakti.api.app import create_app

    return create_app(session_factory=api_session_factory)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Provide a TestClient with exception propagation enabled."""
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


@pytest.fixture
def seed(api_session_factory: sessionmaker[Session]) -> Callable[..., User]:
    """Return a factory that creates a tenant (once per slug) and a user in it.

    Signature: ``seed(email, password, *, role=RoleName.USER, slug=None, name=None)``.
    The returned User is detached; use ``session.merge`` to reattach if needed.
    """

    def _seed(
        email: str,
        password: str,
        *,
        role: RoleName = RoleName.USER,
        slug: str | None = None,
        name: str | None = None,
    ) -> User:
        tenant_slug = slug or f"t-{uuid.uuid4().hex[:8]}"
        with api_session_factory() as sess:
            tenant = Tenant(name=name or tenant_slug, slug=tenant_slug)
            sess.add(tenant)
            sess.flush()
            user = User(
                tenant_id=tenant.id,
                email=email,
                full_name=name or email.split("@")[0],
                password_hash=hash_password(password),
            )
            sess.add(user)
            sess.flush()
            assign_role(sess, user, role)
            sess.commit()
            sess.refresh(user)
            return user

    return _seed

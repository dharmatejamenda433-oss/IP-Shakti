"""Tests that the Alembic migration chain applies cleanly (Phase 3).

These run the real migration scripts against a throwaway SQLite database to prove
the version chain is coherent (upgrade creates the schema, downgrade removes it).
The types used are portable, so success here implies the scripts are valid; the
production target remains PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from ipsakti.core.config import get_settings
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_cfg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Config]:
    """Build an Alembic Config pointed at a temporary SQLite database.

    ``get_settings`` is process-cached, so the cache is cleared after overriding
    ``IPSAKTI_DATABASE_URL``; otherwise ``alembic/env.py`` would reuse a URL cached
    by an earlier test and ignore this override.
    """
    db_path = tmp_path / "migration_test.db"
    monkeypatch.setenv("IPSAKTI_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    try:
        yield cfg
    finally:
        get_settings.cache_clear()


def test_single_head_revision(alembic_cfg: Config) -> None:
    """The migration chain must have exactly one head (no divergent branches)."""
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1


def test_upgrade_head_creates_all_tables(alembic_cfg: Config) -> None:
    command.upgrade(alembic_cfg, "head")
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    assert url is not None
    engine = create_engine(url, future=True)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    expected = {
        "tenants",
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "documents",
        "document_versions",
        "document_chunks",
        "ingestion_jobs",
        "audit_logs",
        "alembic_version",
    }
    assert expected.issubset(tables)


def test_downgrade_removes_tables(alembic_cfg: Config) -> None:
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    assert url is not None
    engine = create_engine(url, future=True)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "documents" not in tables
    assert "tenants" not in tables
    # alembic_version table remains to track revision state.
    assert "alembic_version" in tables

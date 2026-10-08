"""Phase 1 foundation smoke tests.

These verify that the toolchain and core runtime dependencies are installed and
importable. They intentionally do not test application logic (introduced in later
phases) — only that the environment is correctly provisioned.
"""

from __future__ import annotations

import sys
from importlib import import_module

import pytest


def test_python_version_supported() -> None:
    """The interpreter must satisfy the project's requires-python (>=3.12)."""
    assert sys.version_info >= (3, 12)


@pytest.mark.parametrize(
    "module_name",
    [
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "sqlalchemy",
        "alembic",
        "jwt",
        "passlib",
    ],
)
def test_core_dependency_importable(module_name: str) -> None:
    """Each core runtime dependency declared in pyproject.toml must import."""
    assert import_module(module_name) is not None


def test_sqlalchemy_is_2x() -> None:
    """The spec mandates SQLAlchemy 2.x."""
    import sqlalchemy

    assert sqlalchemy.__version__.startswith("2.")

"""Unit tests for path-traversal-safe, atomic storage (NFP-SEC, ADR 0008)."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from ipsakti.core.config import get_settings
from ipsakti.core.errors import ValidationError
from ipsakti.documents.storage import (
    build_relative_path,
    commit_staged,
    discard_staged,
    remove_stored,
    resolve_within_root,
    stage_pdf_stream,
    storage_root,
)

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
_MIB = 1024 * 1024


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "storage_root", str(tmp_path))
    yield


def _rel() -> str:
    return build_relative_path(tenant_id=uuid4(), document_id=uuid4(), version_number=1)


def test_relative_path_uses_only_uuid_components() -> None:
    tenant, doc = uuid4(), uuid4()
    rel = build_relative_path(tenant_id=tenant, document_id=doc, version_number=3)
    assert rel == f"{tenant.hex}/{doc.hex}/v3.pdf"


def test_stage_hashes_and_sizes_then_commit_writes_file() -> None:
    rel = _rel()
    staged = stage_pdf_stream(io.BytesIO(PDF), relative_path=rel, max_bytes=_MIB)
    assert staged.size_bytes == len(PDF)
    assert staged.sha256 == hashlib.sha256(PDF).hexdigest()
    assert staged.tmp_path.exists()
    assert not staged.dest_path.exists()

    stored = commit_staged(staged)
    assert Path(stored.path).read_bytes() == PDF
    assert not staged.tmp_path.exists()
    assert stored.relative_path == rel


def test_stage_rejects_non_pdf_and_leaves_no_temp() -> None:
    rel = _rel()
    with pytest.raises(ValidationError):
        stage_pdf_stream(io.BytesIO(b"definitely not a pdf"), relative_path=rel, max_bytes=_MIB)
    assert not resolve_within_root(rel).exists()


def test_stage_rejects_empty_file() -> None:
    with pytest.raises(ValidationError):
        stage_pdf_stream(io.BytesIO(b""), relative_path=_rel(), max_bytes=_MIB)


def test_stage_rejects_oversize_file() -> None:
    oversized = b"%PDF-" + b"x" * 5000
    with pytest.raises(ValidationError):
        stage_pdf_stream(io.BytesIO(oversized), relative_path=_rel(), max_bytes=1024)


def test_no_partial_files_leak_after_failures(tmp_path: Path) -> None:
    for payload in (b"", b"nope", b"%PDF-" + b"x" * 5000):
        with pytest.raises(ValidationError):
            stage_pdf_stream(io.BytesIO(payload), relative_path=_rel(), max_bytes=1024)
    assert list(tmp_path.rglob("*.part")) == []


def test_discard_staged_removes_temp_without_committing() -> None:
    staged = stage_pdf_stream(io.BytesIO(PDF), relative_path=_rel(), max_bytes=_MIB)
    discard_staged(staged)
    assert not staged.tmp_path.exists()
    assert not staged.dest_path.exists()


def test_remove_stored_deletes_committed_file() -> None:
    staged = stage_pdf_stream(io.BytesIO(PDF), relative_path=_rel(), max_bytes=_MIB)
    stored = commit_staged(staged)
    assert Path(stored.path).exists()
    remove_stored(stored.path)
    assert not Path(stored.path).exists()


def test_resolve_within_root_rejects_traversal() -> None:
    with pytest.raises(ValidationError):
        resolve_within_root("../../etc/passwd")


def test_resolve_within_root_accepts_nested_key() -> None:
    resolved = resolve_within_root(_rel())
    assert storage_root() in resolved.parents

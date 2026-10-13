"""Path-traversal-safe, atomic, immutable PDF storage (NFP-SEC, ADR 0008).

Design invariants:

* **UUID paths.** Storage keys are built exclusively from server-generated UUIDs
  and an integer version number — never from the client filename — so no user
  input reaches the filesystem path.
* **Containment.** Every relative key is resolved and re-checked to live inside
  the configured storage root before any write happens.
* **Atomic + immutable.** Bytes stream to a sibling ``*.part`` temp file and are
  moved into place with :func:`os.replace` (atomic on POSIX and Windows). A
  committed file is never rewritten; new content means a new version path.
* **Single pass.** The stream is hashed (SHA-256), size-capped, and magic-checked
  in one read loop so an oversized or non-PDF upload is rejected early.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from ipsakti.core.config import get_settings
from ipsakti.core.errors import ValidationError
from ipsakti.documents.validation import validate_pdf_magic

_CHUNK_SIZE = 1024 * 1024  # 1 MiB
_PART_SUFFIX = ".part"


@dataclass(frozen=True, slots=True)
class StagedFile:
    """A fully written, validated temp file awaiting an atomic commit."""

    tmp_path: Path
    dest_path: Path
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class StoredFile:
    """A committed, immutable stored file."""

    path: str
    relative_path: str
    sha256: str
    size_bytes: int


def storage_root() -> Path:
    """Return the configured storage root as an absolute, resolved path."""
    return Path(get_settings().storage_root).resolve()


def build_relative_path(*, tenant_id: UUID, document_id: UUID, version_number: int) -> str:
    """Build a deterministic, input-free relative storage key for a version."""
    return f"{tenant_id.hex}/{document_id.hex}/v{version_number}.pdf"


def resolve_within_root(relative_path: str) -> Path:
    """Resolve ``relative_path`` under the storage root, enforcing containment.

    Raises:
        ValidationError: If the resolved path escapes the storage root.
    """
    root = storage_root()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValidationError("resolved storage path escapes the storage root")
    return candidate


def stage_pdf_stream(stream: BinaryIO, *, relative_path: str, max_bytes: int) -> StagedFile:
    """Stream an upload to a temp file, hashing, size-capping, and magic-checking.

    Args:
        stream: A binary file-like object positioned at the start of the upload.
        relative_path: The eventual storage key (relative to the storage root).
        max_bytes: Hard upper bound on accepted size.

    Returns:
        A :class:`StagedFile` holding the temp path, destination, digest, and size.

    Raises:
        ValidationError: On a bad signature, an empty file, an oversized file, or a
            path that escapes the storage root. The temp file is always removed.
    """
    dest = resolve_within_root(relative_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f"{dest.name}.{uuid4().hex}{_PART_SUFFIX}")

    hasher = hashlib.sha256()
    size = 0
    header_checked = False
    try:
        with tmp.open("wb") as handle:
            while True:
                chunk = stream.read(_CHUNK_SIZE)
                if not chunk:
                    break
                if not header_checked:
                    validate_pdf_magic(chunk)
                    header_checked = True
                size += len(chunk)
                if size > max_bytes:
                    raise ValidationError("file exceeds the maximum allowed size")
                hasher.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if size == 0:
            raise ValidationError("uploaded file is empty")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return StagedFile(
        tmp_path=tmp,
        dest_path=dest,
        relative_path=relative_path,
        sha256=hasher.hexdigest(),
        size_bytes=size,
    )


def commit_staged(staged: StagedFile) -> StoredFile:
    """Atomically move a staged temp file into its final immutable location."""
    os.replace(staged.tmp_path, staged.dest_path)
    return StoredFile(
        path=str(staged.dest_path),
        relative_path=staged.relative_path,
        sha256=staged.sha256,
        size_bytes=staged.size_bytes,
    )


def discard_staged(staged: StagedFile) -> None:
    """Remove a staged temp file without committing it."""
    staged.tmp_path.unlink(missing_ok=True)


def remove_stored(path: str) -> None:
    """Best-effort removal of a committed file (used to roll back on DB failure)."""
    Path(path).unlink(missing_ok=True)

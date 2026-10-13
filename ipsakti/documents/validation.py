"""Upload validation predicates (FR-ING-2).

These are pure, framework-agnostic checks run before a file is trusted or stored:
declared MIME type, filename extension, and PDF magic-byte signature. Size is
enforced during streaming (see :mod:`ipsakti.documents.storage`) so an oversized
upload is rejected without ever being fully buffered or written.

The magic-byte check is authoritative: a client-declared content type or filename
can be trivially forged, but the leading ``%PDF-`` signature cannot be faked by
renaming an arbitrary file.
"""

from __future__ import annotations

from pathlib import Path

from ipsakti.core.errors import ValidationError

PDF_MAGIC_BYTES = b"%PDF-"
PDF_MIME_TYPE = "application/pdf"
PDF_EXTENSION = ".pdf"
ALLOWED_CONTENT_TYPES = frozenset({PDF_MIME_TYPE})


def validate_content_type(content_type: str | None) -> str:
    """Validate and normalize the client-declared MIME type.

    Args:
        content_type: The multipart part's declared content type (may include
            parameters such as ``; charset=...``).

    Returns:
        The normalized media type (lower-cased, parameters stripped).

    Raises:
        ValidationError: If the type is missing or not an accepted PDF type.
    """
    if not content_type:
        raise ValidationError("missing file content type")
    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("unsupported file type; only PDF is accepted")
    return normalized


def validate_filename_extension(filename: str | None) -> None:
    """Reject a supplied filename that does not carry the ``.pdf`` extension.

    The filename is advisory only — it is never used to build a storage path, so a
    traversal-laden name is harmless here. A missing filename is permitted because
    the magic-byte check remains authoritative.

    Raises:
        ValidationError: If a filename is present but is not ``.pdf``.
    """
    if not filename:
        return
    if Path(filename).suffix.lower() != PDF_EXTENSION:
        raise ValidationError("file name must end with .pdf")


def validate_pdf_magic(header: bytes) -> None:
    """Verify the leading bytes are a PDF signature.

    Args:
        header: The first bytes read from the upload stream.

    Raises:
        ValidationError: If the signature is absent (not a real PDF).
    """
    if not header.startswith(PDF_MAGIC_BYTES):
        raise ValidationError("file content is not a valid PDF")

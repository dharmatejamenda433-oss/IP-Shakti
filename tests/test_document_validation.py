"""Unit tests for upload validation predicates (FR-ING-2)."""

from __future__ import annotations

import pytest
from ipsakti.core.errors import ValidationError
from ipsakti.documents.validation import (
    validate_content_type,
    validate_filename_extension,
    validate_pdf_magic,
)


def test_content_type_accepts_pdf() -> None:
    assert validate_content_type("application/pdf") == "application/pdf"


def test_content_type_normalizes_case_and_params() -> None:
    assert validate_content_type("Application/PDF; charset=binary") == "application/pdf"


def test_content_type_rejects_non_pdf() -> None:
    with pytest.raises(ValidationError):
        validate_content_type("text/plain")


def test_content_type_rejects_missing() -> None:
    with pytest.raises(ValidationError):
        validate_content_type(None)


def test_extension_accepts_pdf_case_insensitive() -> None:
    validate_filename_extension("reports/Final.PDF")


def test_extension_accepts_missing_filename() -> None:
    validate_filename_extension(None)


def test_extension_rejects_non_pdf() -> None:
    with pytest.raises(ValidationError):
        validate_filename_extension("payload.exe")


def test_magic_accepts_pdf_signature() -> None:
    validate_pdf_magic(b"%PDF-1.7\n...")


def test_magic_rejects_non_pdf() -> None:
    with pytest.raises(ValidationError):
        validate_pdf_magic(b"MZ\x90\x00 not a pdf")


def test_magic_rejects_short_header() -> None:
    with pytest.raises(ValidationError):
        validate_pdf_magic(b"%PD")

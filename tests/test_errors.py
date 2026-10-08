"""Tests for the ipsakti.core.errors domain exception hierarchy."""

from __future__ import annotations

import pytest
from ipsakti.core.errors import (
    AuthenticationError,
    AuthorizationError,
    CitationValidationError,
    ConflictError,
    ExtractionError,
    GenerationError,
    IngestionError,
    InsufficientEvidenceError,
    IPSaktiError,
    NotFoundError,
    RetrievalError,
    ValidationError,
)


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (ValidationError, 422, "validation_error"),
        (AuthenticationError, 401, "authentication_error"),
        (AuthorizationError, 403, "authorization_error"),
        (NotFoundError, 404, "not_found"),
        (ConflictError, 409, "conflict"),
        (IngestionError, 500, "ingestion_error"),
        (RetrievalError, 500, "retrieval_error"),
        (InsufficientEvidenceError, 200, "insufficient_evidence"),
        (GenerationError, 502, "generation_error"),
        (CitationValidationError, 500, "citation_validation_error"),
    ],
)
def test_status_and_code(
    exc: type[IPSaktiError], status: int, code: str
) -> None:
    err = exc("boom")
    assert err.status_code == status
    assert err.code == code
    assert err.message == "boom"


def test_extraction_error_is_ingestion_error() -> None:
    err = ExtractionError("needs OCR")
    assert isinstance(err, IngestionError)
    assert err.code == "extraction_error"


def test_code_override() -> None:
    err = NotFoundError("gone", code="document_not_found")
    assert err.code == "document_not_found"


def test_default_message_uses_class_name() -> None:
    err = NotFoundError()
    assert err.message == "NotFoundError"


def test_all_errors_share_base() -> None:
    for exc in (ValidationError, NotFoundError, GenerationError):
        assert issubclass(exc, IPSaktiError)
        assert isinstance(exc("x"), Exception)

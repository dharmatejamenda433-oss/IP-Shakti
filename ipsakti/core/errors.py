"""Domain exception hierarchy.

These exceptions carry an HTTP status and a stable machine-readable `code` so the
API layer can translate them into consistent JSON error responses without leaking
internal details. They are deliberately framework-agnostic (no FastAPI imports) so
services can raise them anywhere.
"""

from __future__ import annotations


class IPSaktiError(Exception):
    """Base class for all IP-SAKTI domain errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        """Initialize with an optional message and code override."""
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        if code is not None:
            self.code = code


class ValidationError(IPSaktiError):
    """Raised when input fails validation at a system boundary."""

    status_code = 422
    code = "validation_error"


class AuthenticationError(IPSaktiError):
    """Raised when identity cannot be established (missing/invalid/expired)."""

    status_code = 401
    code = "authentication_error"


class AuthorizationError(IPSaktiError):
    """Raised when an authenticated principal lacks permission for an action."""

    status_code = 403
    code = "authorization_error"


class NotFoundError(IPSaktiError):
    """Raised when a resource does not exist or is not visible to the tenant.

    Tenant-isolation failures surface as NotFound (not Forbidden) so that direct ID
    manipulation does not reveal whether a resource exists in another tenant.
    """

    status_code = 404
    code = "not_found"


class ConflictError(IPSaktiError):
    """Raised when a request conflicts with current resource state."""

    status_code = 409
    code = "conflict"


class IngestionError(IPSaktiError):
    """Raised when a document ingestion job fails."""

    status_code = 500
    code = "ingestion_error"


class ExtractionError(IngestionError):
    """Raised when PDF extraction fails or a document requires OCR."""

    code = "extraction_error"


class RetrievalError(IPSaktiError):
    """Raised when the retrieval pipeline fails."""

    status_code = 500
    code = "retrieval_error"


class InsufficientEvidenceError(IPSaktiError):
    """Raised when retrieval returns evidence below the relevance gate.

    This is a controlled, expected outcome — not a system fault — so it maps to a
    200-level application result rather than an HTTP error in the API layer.
    """

    status_code = 200
    code = "insufficient_evidence"


class GenerationError(IPSaktiError):
    """Raised when the generation provider fails."""

    status_code = 502
    code = "generation_error"


class CitationValidationError(IPSaktiError):
    """Raised when a model-produced citation fails backend validation."""

    status_code = 500
    code = "citation_validation_error"

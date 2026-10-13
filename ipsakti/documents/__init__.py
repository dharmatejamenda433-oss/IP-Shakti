"""Document upload, validation, storage, and versioning (Phase 5)."""

from __future__ import annotations

from ipsakti.documents.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentVersionInfo,
    IngestionJobInfo,
)
from ipsakti.documents.service import create_document, get_document
from ipsakti.documents.storage import StoredFile, build_relative_path, stage_pdf_stream
from ipsakti.documents.validation import (
    validate_content_type,
    validate_filename_extension,
    validate_pdf_magic,
)

__all__ = [
    "DocumentCreate",
    "DocumentResponse",
    "DocumentVersionInfo",
    "IngestionJobInfo",
    "StoredFile",
    "build_relative_path",
    "create_document",
    "get_document",
    "stage_pdf_stream",
    "validate_content_type",
    "validate_filename_extension",
    "validate_pdf_magic",
]

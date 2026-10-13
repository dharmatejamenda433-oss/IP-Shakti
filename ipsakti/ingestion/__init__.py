"""Ingestion pipeline: PDF extraction, chunking, embedding, indexing.

Phase 6 adds page-aware PDF extraction. Chunking (Phase 7), embeddings (Phase 8),
and Qdrant indexing (Phase 9) are added in later phases.
"""

from __future__ import annotations

from ipsakti.ingestion.extraction import (
    BlockKind,
    ExtractedBlock,
    ExtractionResult,
    PageExtraction,
    extract_pdf,
)

__all__ = [
    "BlockKind",
    "ExtractedBlock",
    "ExtractionResult",
    "PageExtraction",
    "extract_pdf",
]

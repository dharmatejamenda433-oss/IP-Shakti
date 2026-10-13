"""Page-aware PDF extraction with explicit failure handling (Phase 6, FR-ING-3/4/5).

PyMuPDF is used to pull text off each page while preserving 1-based page numbers,
and to detect document structure (headings → section/subsection, paragraphs, and
best-effort tables) that the Phase 7 chunker consumes.

Design rules driven by the spec:

* **Never silently discard pages** (FR-ING-4): every page yields a
  :class:`PageExtraction`, even blank or image-only ones, so page accounting is
  exact and downstream can see what was and was not extractable.
* **Report, never fake, OCR needs** (FR-ING-5): a document with no extractable
  text but with page images raises ``ExtractionError(code="ocr_required")`` rather
  than returning an empty "success".
* **Explicit hard failures**: corrupt/malformed, password-protected, empty, and
  oversized documents each raise ``ExtractionError`` with a distinct machine code.

PyMuPDF is imported lazily so the base package and the pure helpers below remain
importable (and unit-testable) without the heavy dependency installed.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ipsakti.core.errors import ExtractionError

# Machine-readable failure codes (used as ``ExtractionError.code``).
CODE_CORRUPT = "corrupt_document"
CODE_ENCRYPTED = "password_required"
CODE_OCR = "ocr_required"
CODE_EMPTY = "empty_document"
CODE_TOO_LARGE = "too_large"

# PyMuPDF span flag bit for bold (see PyMuPDF docs: bit 4 == 16).
_BOLD_FLAG = 16
_HEADING_MAX_CHARS = 160
_HEADING_MAX_LINES = 2

Bbox = tuple[float, float, float, float]


class BlockKind(StrEnum):
    """Coarse structural classification of an extracted block."""

    HEADING = "HEADING"
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"


@dataclass(frozen=True, slots=True)
class ExtractedBlock:
    """A structural block with its resolved outline context."""

    text: str
    page_number: int
    kind: BlockKind
    level: int | None
    section: str | None
    subsection: str | None


@dataclass(frozen=True, slots=True)
class PageExtraction:
    """Per-page extraction facts; recorded for every page, blank or not."""

    page_number: int
    text: str
    char_count: int
    has_text: bool
    image_only: bool


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """The full extraction outcome for a document version."""

    page_count: int
    pages: tuple[PageExtraction, ...]
    blocks: tuple[ExtractedBlock, ...]
    total_chars: int
    title: str | None


@dataclass(frozen=True, slots=True)
class _RawBlock:
    """Intermediate block before outline context is assigned."""

    text: str
    page_number: int
    kind: BlockKind
    level: int | None
    y0: float


@dataclass(frozen=True, slots=True)
class _PagePiece:
    """A page block before heading classification (body size not yet known)."""

    text: str
    page_number: int
    y0: float
    max_size: float
    is_bold: bool
    is_table: bool


# --- Pure helpers (unit-testable without PyMuPDF) ---------------------------


def flatten_table_rows(rows: Sequence[Sequence[object]]) -> str:
    """Flatten a table's rows into pipe-delimited text, dropping empty rows."""
    lines: list[str] = []
    for row in rows:
        cells = ["" if cell is None else str(cell).strip() for cell in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def bbox_within(inner: Bbox, outer: Bbox, *, tolerance: float = 1.0) -> bool:
    """Return True when ``inner`` sits inside ``outer`` within ``tolerance``."""
    ix0, iy0, ix1, iy1 = inner
    ox0, oy0, ox1, oy1 = outer
    return (
        ix0 >= ox0 - tolerance
        and iy0 >= oy0 - tolerance
        and ix1 <= ox1 + tolerance
        and iy1 <= oy1 + tolerance
    )


def dominant_font_size(sizes: Iterable[float]) -> float:
    """Return the most common font size (the presumed body size), or 0.0 if none.

    Sizes are bucketed to one decimal place. Ties are broken toward the larger
    size so a document with two equally common sizes treats the bigger as body.
    """
    counts: dict[float, int] = {}
    for size in sizes:
        key = round(float(size), 1)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return 0.0
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def classify_heading(
    text: str,
    *,
    max_size: float,
    is_bold: bool,
    body_size: float,
) -> tuple[bool, int | None]:
    """Decide whether a text block is a heading and, if so, its outline level.

    Returns:
        ``(is_heading, level)`` where level is 1/2/3 for headings and ``None``
        otherwise. The heuristic is deliberately conservative: a heading is short,
        spans few lines, and is either noticeably larger than body text or bold
        without terminal sentence punctuation.
    """
    stripped = text.strip()
    if not stripped or body_size <= 0:
        return False, None
    if len(stripped) > _HEADING_MAX_CHARS:
        return False, None
    if stripped.count("\n") > _HEADING_MAX_LINES - 1:
        return False, None

    ratio = max_size / body_size if body_size else 0.0
    short = len(stripped) <= 120
    if ratio >= 1.12 and short:
        level = 1 if ratio >= 1.55 else 2 if ratio >= 1.28 else 3
        return True, level

    no_terminal = not stripped.endswith((".", ",", ";", ":", "!", "?"))
    if is_bold and short and no_terminal and max_size >= body_size > 0:
        return True, 3
    return False, None


def assign_structure(raw_blocks: Sequence[_RawBlock]) -> tuple[ExtractedBlock, ...]:
    """Walk blocks in reading order, resolving section/subsection context.

    A level-1 heading opens a new section (clearing the subsection); any deeper
    heading opens a subsection. Each block records the outline context that
    encloses it (headings record their parent context, before they update it).
    """
    section: str | None = None
    subsection: str | None = None
    out: list[ExtractedBlock] = []
    for raw in raw_blocks:
        out.append(
            ExtractedBlock(
                text=raw.text,
                page_number=raw.page_number,
                kind=raw.kind,
                level=raw.level,
                section=section,
                subsection=subsection,
            )
        )
        if raw.kind == BlockKind.HEADING:
            if raw.level == 1:
                section = raw.text.strip()
                subsection = None
            else:
                subsection = raw.text.strip()
    return tuple(out)


# --- PyMuPDF interaction ----------------------------------------------------


def _load_pymupdf() -> Any:
    """Import PyMuPDF lazily, raising a clear error when it is unavailable."""
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ExtractionError(
            "PyMuPDF is not installed; install the 'retrieval' extra",
        ) from exc
    return pymupdf


def _as_bbox(value: Any) -> Bbox:
    x0, y0, x1, y1 = value
    return (float(x0), float(y0), float(x1), float(y1))


def _block_text(block: dict[str, Any]) -> tuple[str, float, bool]:
    """Join a dict-mode text block into ``(text, max_span_size, is_bold)``."""
    lines: list[str] = []
    max_size = 0.0
    is_bold = False
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        line_text = "".join(span.get("text", "") for span in spans)
        lines.append(line_text)
        for span in spans:
            max_size = max(max_size, float(span.get("size", 0.0)))
            if int(span.get("flags", 0)) & _BOLD_FLAG:
                is_bold = True
    return "\n".join(lines).strip(), max_size, is_bold


def _span_sizes(block: dict[str, Any]) -> list[float]:
    return [
        float(span.get("size", 0.0))
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    ]


def _extract_one_table(table: Any) -> tuple[Bbox, str] | None:
    """Flatten a single detected table, returning ``None`` if it is unusable."""
    try:
        text = flatten_table_rows(table.extract())
        bbox = _as_bbox(table.bbox)
    except Exception:  # noqa: BLE001 - skip undecodable tables (best-effort)
        return None
    return (bbox, text) if text else None


def _safe_find_tables(page: Any) -> list[tuple[Bbox, str]]:
    """Best-effort table detection; returns ``(bbox, flattened_text)`` pairs.

    Table extraction is opportunistic (FR-ING-3 "where reasonably possible"): any
    failure is swallowed so it can never break plain-text extraction.
    """
    try:
        finder = page.find_tables()
        tables = list(finder.tables)
    except Exception:  # noqa: BLE001 - table support varies across PyMuPDF versions
        return []
    results: list[tuple[Bbox, str]] = []
    for table in tables:
        entry = _extract_one_table(table)
        if entry is not None:
            results.append(entry)
    return results


def _process_page(
    page: Any,
    page_number: int,
) -> tuple[PageExtraction, list[float], list[_PagePiece]]:
    """Extract one page's text, font sizes, and un-classified block pieces.

    Heading classification needs the document-wide body font size, so blocks are
    returned as neutral pieces here and classified later by :func:`extract_pdf`.
    """
    text: str = page.get_text("text")
    has_text = bool(text.strip())
    has_images = bool(page.get_images(full=True))
    page_info = PageExtraction(
        page_number=page_number,
        text=text,
        char_count=len(text),
        has_text=has_text,
        image_only=(not has_text) and has_images,
    )

    data: dict[str, Any] = page.get_text("dict")
    tables = _safe_find_tables(page)
    table_bboxes = [bbox for bbox, _ in tables]

    sizes: list[float] = []
    pieces: list[_PagePiece] = []

    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = _as_bbox(block.get("bbox", (0.0, 0.0, 0.0, 0.0)))
        if any(bbox_within(bbox, tb) for tb in table_bboxes):
            continue
        block_text, max_size, is_bold = _block_text(block)
        sizes.extend(_span_sizes(block))
        if not block_text:
            continue
        pieces.append(
            _PagePiece(
                text=block_text,
                page_number=page_number,
                y0=bbox[1],
                max_size=max_size,
                is_bold=is_bold,
                is_table=False,
            )
        )

    for bbox, table_text in tables:
        pieces.append(
            _PagePiece(
                text=table_text,
                page_number=page_number,
                y0=bbox[1],
                max_size=0.0,
                is_bold=False,
                is_table=True,
            )
        )

    pieces.sort(key=lambda piece: piece.y0)
    return page_info, sizes, pieces


def _classify_pieces(
    pieces: Sequence[_PagePiece],
    *,
    body_size: float,
) -> list[_RawBlock]:
    """Turn neutral pieces into heading/paragraph/table raw blocks in order."""
    raw: list[_RawBlock] = []
    for piece in pieces:
        if piece.is_table:
            raw.append(
                _RawBlock(
                    text=piece.text,
                    page_number=piece.page_number,
                    kind=BlockKind.TABLE,
                    level=None,
                    y0=piece.y0,
                )
            )
            continue
        is_heading, level = classify_heading(
            piece.text,
            max_size=piece.max_size,
            is_bold=piece.is_bold,
            body_size=body_size,
        )
        raw.append(
            _RawBlock(
                text=piece.text,
                page_number=piece.page_number,
                kind=BlockKind.HEADING if is_heading else BlockKind.PARAGRAPH,
                level=level,
                y0=piece.y0,
            )
        )
    return raw


def _open_document(pymupdf: Any, path: str | Path) -> Any:
    try:
        return pymupdf.open(str(path))
    except Exception as exc:  # noqa: BLE001 - PyMuPDF raises assorted errors
        raise ExtractionError(
            "could not open PDF (corrupt or malformed)",
            code=CODE_CORRUPT,
        ) from exc


def _unlock(document: Any, password: str | None) -> None:
    if not document.needs_pass:
        return
    if password is None:
        raise ExtractionError("PDF is password-protected", code=CODE_ENCRYPTED)
    if not document.authenticate(password):
        raise ExtractionError("PDF password was rejected", code=CODE_ENCRYPTED)


def extract_pdf(
    path: str | Path,
    *,
    password: str | None = None,
    max_pages: int | None = None,
) -> ExtractionResult:
    """Extract page-aware text and structure from a PDF.

    Args:
        path: Filesystem path to the stored PDF (server-generated, never client input).
        password: Optional password for an encrypted document.
        max_pages: Optional hard cap; exceeding it raises rather than extracting.

    Returns:
        An :class:`ExtractionResult` with every page accounted for.

    Raises:
        ExtractionError: With a distinct ``code`` for corrupt, password-protected
            (``password_required``), image-only (``ocr_required``), empty
            (``empty_document``), or oversized (``too_large``) inputs.
    """
    pymupdf = _load_pymupdf()
    document = _open_document(pymupdf, path)
    try:
        _unlock(document, password)

        page_count = int(document.page_count)
        if page_count == 0:
            raise ExtractionError("PDF contains no pages", code=CODE_EMPTY)
        if max_pages is not None and page_count > max_pages:
            raise ExtractionError(
                f"PDF has {page_count} pages, exceeding the maximum of {max_pages}",
                code=CODE_TOO_LARGE,
            )

        pages: list[PageExtraction] = []
        all_sizes: list[float] = []
        all_pieces: list[_PagePiece] = []
        for index in range(page_count):
            page = document.load_page(index)
            page_info, sizes, pieces = _process_page(page, index + 1)
            pages.append(page_info)
            all_sizes.extend(sizes)
            all_pieces.extend(pieces)

        body_size = dominant_font_size(all_sizes)
        blocks = assign_structure(_classify_pieces(all_pieces, body_size=body_size))

        total_chars = sum(len(page.text.strip()) for page in pages)
        if total_chars == 0:
            if any(page.image_only for page in pages):
                raise ExtractionError(
                    "PDF has no extractable text and appears to be scanned; OCR is required",
                    code=CODE_OCR,
                )
            raise ExtractionError("PDF contains no extractable text", code=CODE_EMPTY)

        metadata = document.metadata or {}
        raw_title = metadata.get("title")
        title = str(raw_title).strip() if raw_title else None

        return ExtractionResult(
            page_count=page_count,
            pages=tuple(pages),
            blocks=blocks,
            total_chars=total_chars,
            title=title or None,
        )
    finally:
        document.close()


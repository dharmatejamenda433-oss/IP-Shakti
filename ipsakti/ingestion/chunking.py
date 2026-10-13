"""Structure-aware, deterministic chunking for extracted PDF blocks (Phase 7).

Chunk boundaries prefer extracted headings, paragraphs, and table blocks. Oversized
blocks are split on sentence boundaries where possible, with hard token-span fallback.
Token counts are estimates based on lexical tokens, not model-tokenizer guarantees.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ipsakti.ingestion.extraction import ExtractedBlock

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A chunk plus deterministic identity and source provenance."""

    chunk_id: str
    text: str
    token_count: int
    page_start: int
    page_end: int
    page_numbers: tuple[int, ...]
    sections: tuple[str, ...]
    subsections: tuple[str, ...]
    block_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Unit:
    """A sentence-sized unit with source metadata."""

    text: str
    token_count: int
    page_number: int
    section: str | None
    subsection: str | None
    block_kind: str


def estimate_token_count(text: str) -> int:
    """Estimate token count consistently without requiring an ML tokenizer."""
    return len(_TOKEN_RE.findall(text))


def _split_block(block: ExtractedBlock, *, target_tokens: int) -> list[_Unit]:
    """Split a block into sentence units, hard-splitting exceptionally long spans."""
    text = block.text.strip()
    if not text:
        return []

    units: list[_Unit] = []
    for sentence in _SENTENCE_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        tokens = list(_TOKEN_RE.finditer(sentence))
        if len(tokens) <= target_tokens:
            units.append(
                _Unit(
                    sentence,
                    len(tokens),
                    block.page_number,
                    block.section,
                    block.subsection,
                    str(block.kind),
                )
            )
            continue

        # Split long sentences by token spans while preserving original punctuation
        # and whitespace inside each slice.
        for start in range(0, len(tokens), target_tokens):
            token_slice = tokens[start : start + target_tokens]
            piece = sentence[token_slice[0].start() : token_slice[-1].end()].strip()
            if piece:
                units.append(
                    _Unit(
                        piece,
                        len(token_slice),
                        block.page_number,
                        block.section,
                        block.subsection,
                        str(block.kind),
                    )
                )
    return units


def chunk_extracted_blocks(
    blocks: tuple[ExtractedBlock, ...] | list[ExtractedBlock],
    *,
    document_version_id: uuid.UUID | str,
    target_tokens: int = 600,
    overlap_tokens: int = 75,
) -> tuple[TextChunk, ...]:
    """Create deterministic chunks while retaining page and outline provenance.

    Empty or whitespace-only input yields an empty tuple. Invalid sizing raises
    ValueError. Overlap is carried by whole trailing sentence units where possible.
    """
    if target_tokens < 1:
        raise ValueError("target_tokens must be at least 1")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens cannot be negative")
    if overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be smaller than target_tokens")

    units = [
        unit
        for block in blocks
        for unit in _split_block(block, target_tokens=target_tokens)
    ]
    if not units:
        return ()

    grouped: list[list[_Unit]] = []
    current: list[_Unit] = []
    current_count = 0
    for unit in units:
        if current and current_count + unit.token_count > target_tokens:
            grouped.append(current)
            current = []
            current_count = 0
        current.append(unit)
        current_count += unit.token_count
    if current:
        grouped.append(current)

    # Add overlap after the initial greedy split. This avoids emitting overlap-only
    # chunks or getting stuck when a carried unit plus the next unit exceeds target.
    for index in range(1, len(grouped)):
        previous = grouped[index - 1]
        carry: list[_Unit] = []
        carry_count = 0
        for unit in reversed(previous):
            if carry_count + unit.token_count > overlap_tokens:
                break
            if sum(item.token_count for item in grouped[index]) + carry_count + unit.token_count > target_tokens:
                break
            carry.insert(0, unit)
            carry_count += unit.token_count
        grouped[index] = carry + grouped[index]

    namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"ipsakti:{document_version_id}")
    chunks: list[TextChunk] = []
    for index, group in enumerate(grouped):
        chunk_text = "\n\n".join(unit.text for unit in group).strip()
        if not chunk_text:
            continue
        pages = tuple(dict.fromkeys(unit.page_number for unit in group))
        sections = tuple(dict.fromkeys(unit.section for unit in group if unit.section))
        subsections = tuple(
            dict.fromkeys(unit.subsection for unit in group if unit.subsection)
        )
        kinds = tuple(dict.fromkeys(unit.block_kind for unit in group))
        digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        chunk_id = str(uuid.uuid5(namespace, f"{index}:{digest}"))
        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                text=chunk_text,
                token_count=estimate_token_count(chunk_text),
                page_start=min(pages),
                page_end=max(pages),
                page_numbers=pages,
                sections=sections,
                subsections=subsections,
                block_kinds=kinds,
            )
        )
    return tuple(chunks)

from __future__ import annotations

import uuid

import pytest
from ipsakti.ingestion.chunking import chunk_extracted_blocks, estimate_token_count
from ipsakti.ingestion.extraction import BlockKind, ExtractedBlock


def _block(
    text: str,
    *,
    page: int = 1,
    kind: BlockKind = BlockKind.PARAGRAPH,
    section: str | None = "Section A",
    subsection: str | None = None,
) -> ExtractedBlock:
    return ExtractedBlock(
        text=text,
        page_number=page,
        kind=kind,
        level=None,
        section=section,
        subsection=subsection,
    )


def test_empty_blocks_return_no_chunks() -> None:
    assert chunk_extracted_blocks([], document_version_id="version-1") == ()
    assert chunk_extracted_blocks(
        [_block("   ")], document_version_id="version-1"
    ) == ()


def test_chunking_is_deterministic_for_same_version_and_content() -> None:
    blocks = [_block("First sentence. Second sentence."), _block("Third sentence.", page=2)]
    first = chunk_extracted_blocks(
        blocks, document_version_id="version-1", target_tokens=5, overlap_tokens=1
    )
    second = chunk_extracted_blocks(
        blocks, document_version_id="version-1", target_tokens=5, overlap_tokens=1
    )
    assert first == second
    assert all(chunk.chunk_id for chunk in first)


def test_chunk_ids_differ_between_document_versions() -> None:
    blocks = [_block("A short source passage.")]
    first = chunk_extracted_blocks(blocks, document_version_id="version-1")
    second = chunk_extracted_blocks(blocks, document_version_id="version-2")
    assert first[0].chunk_id != second[0].chunk_id


def test_chunks_preserve_page_and_section_provenance() -> None:
    blocks = [
        _block("First source sentence.", page=2, section="Act", subsection="Part I"),
        _block("Second source sentence.", page=3, section="Act", subsection="Part II"),
    ]
    chunks = chunk_extracted_blocks(
        blocks, document_version_id=uuid.uuid4(), target_tokens=100, overlap_tokens=10
    )
    assert len(chunks) == 1
    assert chunks[0].page_start == 2
    assert chunks[0].page_end == 3
    assert chunks[0].page_numbers == (2, 3)
    assert chunks[0].sections == ("Act",)
    assert chunks[0].subsections == ("Part I", "Part II")


def test_large_input_splits_without_losing_words() -> None:
    words = [f"word{i}" for i in range(40)]
    source = " ".join(words)
    chunks = chunk_extracted_blocks(
        [_block(source)], document_version_id="version-1", target_tokens=10, overlap_tokens=2
    )
    assert len(chunks) > 1
    combined = " ".join(chunk.text for chunk in chunks)
    for word in words:
        assert word in combined
    assert all(chunk.token_count <= 10 for chunk in chunks)
    assert "word8" in chunks[0].text
    assert "word8" in chunks[1].text


@pytest.mark.parametrize(
    ("target", "overlap"),
    [(0, 0), (10, -1), (10, 10)],
)
def test_invalid_chunk_sizes_rejected(target: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_extracted_blocks(
            [_block("Text.")],
            document_version_id="version-1",
            target_tokens=target,
            overlap_tokens=overlap,
        )


def test_token_estimate_counts_words_and_punctuation() -> None:
    assert estimate_token_count("Section 1: Rules.") == 5

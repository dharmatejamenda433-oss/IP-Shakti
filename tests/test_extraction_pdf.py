"""Integration tests for PDF extraction using PyMuPDF (skipped if unavailable)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ipsakti.core.errors import ExtractionError
from ipsakti.ingestion.extraction import (
    CODE_EMPTY,
    CODE_ENCRYPTED,
    CODE_OCR,
    CODE_TOO_LARGE,
    BlockKind,
    extract_pdf,
)

pymupdf = pytest.importorskip("pymupdf")


def _make_pdf(path: Path, pages: list[list[tuple[str, int, str]]], *, step: int = 40) -> None:
    """Build a PDF; each page is a list of ``(text, fontsize, fontname)`` lines."""
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for text, size, font in lines:
            page.insert_text((72, y), text, fontsize=size, fontname=font)
            y += step
    doc.save(str(path))
    doc.close()


def test_extracts_pages_preserving_numbers(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    _make_pdf(
        pdf,
        [
            [("First page body text.", 11, "helv"), ("More body on page one.", 11, "helv")],
            [("Second page body text.", 11, "helv")],
        ],
    )
    result = extract_pdf(pdf)
    assert result.page_count == 2
    assert [p.page_number for p in result.pages] == [1, 2]
    assert "First page" in result.pages[0].text
    assert "Second page" in result.pages[1].text
    assert result.total_chars > 0
    assert all(p.has_text for p in result.pages)


def test_detects_headings_sections_and_subsections(tmp_path: Path) -> None:
    pdf = tmp_path / "structured.pdf"
    _make_pdf(
        pdf,
        [
            [
                ("Chapter One", 22, "helv"),
                ("Body paragraph under chapter one.", 11, "helv"),
                ("Another body line to dominate the size.", 11, "helv"),
                ("Section 1.1", 15, "helv"),
                ("Body under subsection.", 11, "helv"),
                ("Even more body text here.", 11, "helv"),
            ]
        ],
    )
    result = extract_pdf(pdf)
    headings = [b for b in result.blocks if b.kind == BlockKind.HEADING]
    assert any(b.text.strip() == "Chapter One" and b.level == 1 for b in headings)
    assert any(b.text.strip() == "Section 1.1" and b.level == 2 for b in headings)

    sub_body = next(b for b in result.blocks if b.text.strip() == "Body under subsection.")
    assert sub_body.kind == BlockKind.PARAGRAPH
    assert sub_body.section == "Chapter One"
    assert sub_body.subsection == "Section 1.1"


def test_blank_page_is_recorded_not_discarded(tmp_path: Path) -> None:
    pdf = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Content on page one.", fontsize=11)
    doc.new_page()  # page 2: blank, no text, no image
    doc.new_page().insert_text((72, 72), "Content on page three.", fontsize=11)
    doc.save(str(pdf))
    doc.close()

    result = extract_pdf(pdf)
    assert result.page_count == 3
    assert len(result.pages) == 3
    assert result.pages[1].has_text is False
    assert result.pages[1].image_only is False
    assert result.pages[1].char_count == 0
    assert "page three" in result.pages[2].text


def test_image_only_document_requires_ocr(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 32, 32))
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 200, 200), pixmap=pix)
    doc.save(str(pdf))
    doc.close()

    with pytest.raises(ExtractionError) as excinfo:
        extract_pdf(pdf)
    assert excinfo.value.code == CODE_OCR


def test_document_with_no_content_is_empty(tmp_path: Path) -> None:
    pdf = tmp_path / "empty.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()

    with pytest.raises(ExtractionError) as excinfo:
        extract_pdf(pdf)
    assert excinfo.value.code == CODE_EMPTY


def test_password_protected_document(tmp_path: Path) -> None:
    pdf = tmp_path / "secret.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Secret body text.", fontsize=11)
    doc.save(
        str(pdf),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-pw",
        user_pw="user-pw",
    )
    doc.close()

    with pytest.raises(ExtractionError) as no_pw:
        extract_pdf(pdf)
    assert no_pw.value.code == CODE_ENCRYPTED

    with pytest.raises(ExtractionError) as wrong_pw:
        extract_pdf(pdf, password="not-the-password")
    assert wrong_pw.value.code == CODE_ENCRYPTED

    result = extract_pdf(pdf, password="user-pw")
    assert "Secret body text" in result.pages[0].text


def test_corrupt_document_raises_extraction_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\nthis is not a valid pdf body\n")
    with pytest.raises(ExtractionError):
        extract_pdf(bad)


def test_max_pages_is_enforced(tmp_path: Path) -> None:
    pdf = tmp_path / "multi.pdf"
    _make_pdf(pdf, [[(f"Page {i} body text.", 11, "helv")] for i in range(1, 4)])

    with pytest.raises(ExtractionError) as excinfo:
        extract_pdf(pdf, max_pages=2)
    assert excinfo.value.code == CODE_TOO_LARGE

    assert extract_pdf(pdf, max_pages=10).page_count == 3


def test_metadata_title_is_surfaced(tmp_path: Path) -> None:
    pdf = tmp_path / "titled.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Some body text.", fontsize=11)
    doc.set_metadata({"title": "  My Report  "})
    doc.save(str(pdf))
    doc.close()

    assert extract_pdf(pdf).title == "My Report"

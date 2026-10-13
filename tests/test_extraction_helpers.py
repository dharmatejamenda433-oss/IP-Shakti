"""Unit tests for the pure extraction helpers (no PyMuPDF required)."""

from __future__ import annotations

from collections.abc import Sequence

from ipsakti.ingestion.extraction import (
    BlockKind,
    _RawBlock,
    assign_structure,
    bbox_within,
    classify_heading,
    dominant_font_size,
    flatten_table_rows,
)


def test_flatten_table_rows_joins_and_drops_empty() -> None:
    rows: list[Sequence[object]] = [["a", "b"], [None, ""], ["c", "d"]]
    assert flatten_table_rows(rows) == "a | b\nc | d"


def test_flatten_table_rows_handles_none_cells() -> None:
    assert flatten_table_rows([[None, "x"]]) == " | x"


def test_bbox_within_true_and_false() -> None:
    outer = (0.0, 0.0, 10.0, 10.0)
    assert bbox_within((1.0, 1.0, 2.0, 2.0), outer) is True
    assert bbox_within((0.0, 0.0, 20.0, 20.0), outer) is False


def test_bbox_within_honours_tolerance() -> None:
    outer = (0.0, 0.0, 10.0, 10.0)
    assert bbox_within((-0.5, -0.5, 10.5, 10.5), outer, tolerance=1.0) is True
    assert bbox_within((-2.0, 0.0, 10.0, 10.0), outer, tolerance=1.0) is False


def test_dominant_font_size_picks_mode() -> None:
    assert dominant_font_size([11.0, 11.0, 11.0, 20.0, 15.0]) == 11.0


def test_dominant_font_size_tie_breaks_larger() -> None:
    assert dominant_font_size([11.0, 14.0]) == 14.0


def test_dominant_font_size_empty_is_zero() -> None:
    assert dominant_font_size([]) == 0.0


def test_classify_heading_levels_by_size_ratio() -> None:
    assert classify_heading("Chapter", max_size=22.0, is_bold=False, body_size=11.0) == (True, 1)
    assert classify_heading("Section", max_size=15.0, is_bold=False, body_size=11.0) == (True, 2)
    assert classify_heading("Subhead", max_size=13.0, is_bold=False, body_size=11.0) == (True, 3)


def test_classify_heading_rejects_body_text() -> None:
    is_heading, level = classify_heading(
        "This is ordinary body text.", max_size=11.0, is_bold=False, body_size=11.0
    )
    assert is_heading is False
    assert level is None


def test_classify_heading_bold_short_no_terminal() -> None:
    assert classify_heading("Important Note", max_size=11.0, is_bold=True, body_size=11.0) == (
        True,
        3,
    )


def test_classify_heading_bold_with_terminal_period_is_not_heading() -> None:
    is_heading, _ = classify_heading(
        "This ends with a period.", max_size=11.0, is_bold=True, body_size=11.0
    )
    assert is_heading is False


def test_classify_heading_rejects_long_and_multiline() -> None:
    long_text = "x" * 200
    assert classify_heading(long_text, max_size=22.0, is_bold=False, body_size=11.0) == (
        False,
        None,
    )
    multiline = "Line one\nLine two\nLine three"
    assert classify_heading(multiline, max_size=22.0, is_bold=False, body_size=11.0) == (
        False,
        None,
    )


def test_classify_heading_zero_body_size_is_not_heading() -> None:
    assert classify_heading("Title", max_size=22.0, is_bold=True, body_size=0.0) == (False, None)


def _raw(text: str, kind: BlockKind, level: int | None, page: int = 1) -> _RawBlock:
    return _RawBlock(text=text, page_number=page, kind=kind, level=level, y0=0.0)


def test_assign_structure_tracks_section_and_subsection() -> None:
    raws = [
        _raw("Chapter One", BlockKind.HEADING, 1),
        _raw("body one", BlockKind.PARAGRAPH, None),
        _raw("Section 1.1", BlockKind.HEADING, 2),
        _raw("body two", BlockKind.PARAGRAPH, None),
    ]
    blocks = assign_structure(raws)

    assert blocks[0].kind == BlockKind.HEADING
    assert blocks[0].section is None  # heading records its parent context
    assert blocks[1].section == "Chapter One"
    assert blocks[1].subsection is None
    assert blocks[2].section == "Chapter One"
    assert blocks[2].subsection is None
    assert blocks[3].section == "Chapter One"
    assert blocks[3].subsection == "Section 1.1"


def test_assign_structure_new_section_clears_subsection() -> None:
    raws = [
        _raw("A", BlockKind.HEADING, 1),
        _raw("A.1", BlockKind.HEADING, 2),
        _raw("B", BlockKind.HEADING, 1),
        _raw("body", BlockKind.PARAGRAPH, None),
    ]
    blocks = assign_structure(raws)
    assert blocks[3].section == "B"
    assert blocks[3].subsection is None


def test_assign_structure_table_keeps_context() -> None:
    raws = [
        _raw("Chapter", BlockKind.HEADING, 1),
        _raw("col1 | col2", BlockKind.TABLE, None),
    ]
    blocks = assign_structure(raws)
    assert blocks[1].kind == BlockKind.TABLE
    assert blocks[1].section == "Chapter"
    assert blocks[1].level is None

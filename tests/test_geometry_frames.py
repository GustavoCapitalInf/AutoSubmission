"""Phase 2.1 cell G (`docs/agent-handoffs/P21-GEOMETRY.md`): one `DocumentGeometry`
from canonical evidence — native PyMuPDF words and (synthetic) Paddle-shaped
word boxes through the SAME path, explicit and tested coordinate frames.

Proves:
* item 3 — `geometry_from_pdf` is BYTE-IDENTICAL to its Phase 2.0 implementation
  (the legacy copy below) on the structurer fixtures, two structurer-safety-
  style synthetic PDFs, and 12 pinned corpus PDFs (`corpus_gate.py`'s manifest,
  read-only; sha16s in the test and in this cell's W3 section).
* item 4 — `_group_lines` is a thin wrapper over `evidence.group_lines` (the
  ONE grouping rule); an AST guard against a second tolerance/median
  computation (mutant M4).
* item 5 — coordinate conventions: a pixel evidence round-trips through
  `to_pixels`/`to_pdf_points` to 1e-6; a native evidence of "the same rows"
  agrees with an independently-authored pixel evidence within 1.5 pt; mixed
  spaces on one document are legal; malformed geometry cannot reach
  `geometry_from_evidence` because `evidence/` already refused to build it;
  rotation is recorded, never corrected, and measured over the corpus.
* item 6 — `PageGeometry.page` (1-based) == `PageFrame.page_index + 1`
  (0-based), including an empty middle page.
* item 7 — no statement-specific hardcodes (covered by the layer-wide
  `tests/test_no_statement_hardcodes.py`; nothing here needs its own case).

Every document in this file is synthetic — invented institutions, invented
amounts — except the 12 pinned corpus PDFs, read read-only and named only by
sha16.
"""
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from types import SimpleNamespace

import pytest

from analysis.structurer import geometry_from_pdf, structure_document
from analysis.structurer.geometry import (
    NATIVE_EXTRACTOR_ID,
    UNREADABLE_PAGE_NOTE,
    UNROTATED_WORDS_NOTE,
    WORD_REFUSED_NOTE,
    DocumentGeometry,
    GeoLine,
    PageGeometry,
    Word,
    _group_lines,
    geometry_from_evidence,
    native_evidence_from_pdf,
)
from analysis.structurer import STRUCTURER_ENV, structurer_enabled
from evidence import (
    ExtractionEvidence,
    LineBox,
    MalformedGeometry,
    PageEvidence,
    PageFrame,
    WordBox,
    page_text,
    to_pdf_points,
    to_pixels,
    word_id,
)

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "Bank Statements"
LETTER_PT = (612.0, 792.0)


# ===========================================================================
# The Phase 2.0 implementation, copied VERBATIM (item 3). Never called by
# production code — it exists only so this file can assert equality against
# it. Do not "clean up" a divergence here; a divergence here IS the finding.
# ===========================================================================

@dataclass(frozen=True)
class _LegacyWord:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


@dataclass(frozen=True)
class _LegacyGeoLine:
    page: int
    words: tuple
    text: str
    spans: tuple


@dataclass(frozen=True)
class _LegacyPageGeometry:
    page: int
    width: float
    height: float
    lines: tuple = ()


@dataclass(frozen=True)
class _LegacyDocumentGeometry:
    pages: tuple

    @property
    def word_count(self) -> int:
        return sum(len(line.words) for page in self.pages for line in page.lines)


def _legacy_group_lines(page_number: int, words: list) -> tuple:
    if not words:
        return ()
    tolerance = max(1.0, median(word.height for word in words) * 0.6)
    ordered = sorted(words, key=lambda word: (round(word.mid_y, 1), word.x0))

    lines: list[list] = []
    current: list = [ordered[0]]
    for word in ordered[1:]:
        if abs(word.mid_y - current[-1].mid_y) <= tolerance:
            current.append(word)
        else:
            lines.append(current)
            current = [word]
    lines.append(current)

    built: list = []
    for row in lines:
        row.sort(key=lambda word: word.x0)
        parts: list[str] = []
        spans: list[tuple[int, int]] = []
        offset = 0
        for index, word in enumerate(row):
            if index:
                parts.append(" ")
                offset += 1
            spans.append((offset, offset + len(word.text)))
            parts.append(word.text)
            offset += len(word.text)
        built.append(_LegacyGeoLine(page_number, tuple(row), "".join(parts), tuple(spans)))
    return tuple(built)


def _legacy_geometry_from_pdf(pdf_bytes: bytes):
    try:
        import fitz
    except Exception:
        return None
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return None

    pages: list = []
    try:
        for index, page in enumerate(document, start=1):
            try:
                raw = page.get_text("words")
                rect = page.rect
            except Exception:
                pages.append(_LegacyPageGeometry(index, 0.0, 0.0, ()))
                continue
            words = [
                _LegacyWord(str(item[4]), float(item[0]), float(item[1]), float(item[2]), float(item[3]))
                for item in raw
                if str(item[4]).strip()
            ]
            pages.append(_LegacyPageGeometry(
                index, float(rect.width), float(rect.height), _legacy_group_lines(index, words)
            ))
    except Exception:
        return None
    finally:
        try:
            document.close()
        except Exception:
            pass

    geometry = _LegacyDocumentGeometry(tuple(pages))
    return geometry if geometry.word_count else None


def _assert_geometry_equal(legacy, new) -> None:
    """Structural equality: every page's page/width/height, every line's
    text/spans, every word's box — the properties the card's item 3 pins."""
    if legacy is None or new is None:
        assert legacy is None and new is None
        return
    assert len(legacy.pages) == len(new.pages)
    for lp, np in zip(legacy.pages, new.pages):
        assert (lp.page, lp.width, lp.height) == (np.page, np.width, np.height)
        assert len(lp.lines) == len(np.lines)
        for ll, nl in zip(lp.lines, np.lines):
            assert ll.page == nl.page  # F-2: the GeoLine site, not just PageGeometry's
            assert ll.text == nl.text
            assert ll.spans == nl.spans
            assert len(ll.words) == len(nl.words)
            for lw, nw in zip(ll.words, nl.words):
                assert (lw.text, lw.x0, lw.y0, lw.x1, lw.y1) == (nw.text, nw.x0, nw.y0, nw.x1, nw.y1)


# ===========================================================================
# Synthetic PDF builders
# ===========================================================================

def _render_pdf(rows: list, *, width: float = 612.0, height: float = 792.0,
                fontsize: float = 10.0, extra_pages: int = 0, rotate: int = 0) -> bytes:
    """A one-column ledger PDF, real glyphs at known baselines, via PyMuPDF —
    synthetic text only. `rows` is `[[(text, x), ...], ...]`, one output row
    per list entry at consecutive 20pt baselines starting at y=100."""
    import fitz

    document = fitz.open()
    page = document.new_page(width=width, height=height)
    baseline = 100.0
    for row in rows:
        for text, x in row:
            page.insert_text(fitz.Point(x, baseline), text, fontsize=fontsize, fontname="helv")
        baseline += 20.0
    if rotate:
        page.set_rotation(rotate)
    for _ in range(extra_pages):
        document.new_page(width=width, height=height)
    data = document.tobytes()
    document.close()
    return data


# The structurer fixture from `tests/test_structurer.py::
# test_geometry_finds_rows_whose_date_is_not_at_the_start_of_the_line`,
# rendered as a real PDF (that test builds `GeoLine`s directly and never
# exercises `geometry_from_pdf`; this is the PDF the same content would
# print to).
_STRUCTURER_FIXTURE_ROWS = [
    [("Statement", 40.0), ("period", 90.0), ("03/01/2054", 140.0), ("to", 200.0), ("03/31/2054", 220.0)],
    [("Beginning", 40.0), ("balance", 90.0), ("1,000.00", 300.0)],
    [("Ending", 40.0), ("balance", 90.0), ("1,010.00", 300.0)],
] + [
    [(f"40{index}", 40.0), (f"03/{index + 2:02d}", 120.0), (f"VENDOR{index}", 180.0),
     (f"{amount:,.2f}", 320.0), (f"{balance:,.2f}", 400.0)]
    for index, (amount, balance) in enumerate(
        zip([25.00, 100.00, 5.00, 30.00, 20.00, 10.00, 20.00],
            [975.00, 1075.00, 1070.00, 1040.00, 1020.00, 1030.00, 1010.00]),
        start=3,
    )
]

# Two "structurer-safety"-style fixtures: a small-font / large-font pair (the
# same tolerance-scaling property `test_group_lines_tolerance_scales_with_the
# _page_type_size` proves at the evidence layer) and a two-column layout,
# rendered as real PDFs — no fixture PDF pre-existed in the repo for this
# pin, so these are authored here for it.
_SAFETY_FIXTURE_SMALL_FONT_ROWS = [
    [("Reference", 40.0), ("Document", 100.0)],
    [("01/02/2054", 40.0), ("Vendor Alpha", 100.0), ("12.00", 300.0), ("988.00", 380.0)],
    [("01/03/2054", 40.0), ("Vendor Beta", 100.0), ("34.00", 300.0), ("954.00", 380.0)],
]
_SAFETY_FIXTURE_TWO_COLUMN_ROWS = [
    [("Left", 40.0), ("Right", 320.0)],
    [("01/04/2054", 40.0), ("Note A", 100.0), ("55.00", 260.0), ("01/04/2054", 320.0), ("Note B", 380.0), ("77.00", 520.0)],
]


def _fixture_bytes() -> dict[str, bytes]:
    return {
        "structurer_fixture": _render_pdf(_STRUCTURER_FIXTURE_ROWS),
        "safety_fixture_6pt": _render_pdf(_SAFETY_FIXTURE_SMALL_FONT_ROWS, fontsize=6.0),
        "safety_fixture_two_column": _render_pdf(_SAFETY_FIXTURE_TWO_COLUMN_ROWS),
    }


# ===========================================================================
# The equivalence pin (item 3)
# ===========================================================================

@pytest.mark.parametrize("name", sorted(_fixture_bytes().keys()))
def test_geometry_from_pdf_is_byte_identical_to_phase_2_0_on_synthetic_fixtures(name):
    data = _fixture_bytes()[name]
    _assert_geometry_equal(_legacy_geometry_from_pdf(data), geometry_from_pdf(data))


def test_geometry_from_pdf_is_byte_identical_on_a_multi_page_document_with_an_empty_middle_page():
    data = _render_pdf(_STRUCTURER_FIXTURE_ROWS, extra_pages=1)
    # A third, empty page appended after the two extras below.
    import fitz
    document = fitz.open(stream=data, filetype="pdf")
    document.new_page(width=612.0, height=792.0)
    data = document.tobytes()
    document.close()
    _assert_geometry_equal(_legacy_geometry_from_pdf(data), geometry_from_pdf(data))


#: 12 corpus PDFs pinned by content sha16, spread across 12 different
#: manifest folders (`corpus_gate.py`'s pinned manifest — read-only; picked
#: by even index spacing, not by name). Corpus-relative paths are used only
#: to open the files; nothing about a name, a bank or an amount is asserted.
_PINNED_CORPUS_RELATIVE_PATHS = (
    "ATB/ATB August 2023.pdf",
    "BofA/BofA.pdf",
    "CapitalOne/capital one may 2026.pdf",
    "Chase/Chase Salomon March 2026.pdf",
    "Misc/Checking Account Statements - 1_30_2026 - 4001245.pdf",
    "Misc/WMB May 25.pdf",
    "Others/B1/b1 march 2026.pdf",
    "Others/Santander/Santander_April26.pdf",
    "RBC/Chequing Statement-DEC+.pdf",
    "TD Can/Dec_31-Jan_30_2026 (6).pdf",
    "Truist/Truist AUTO February, 2026.pdf",
    "WellsFargo/113025 WellsFargo.pdf",
)
#: sha256 (first 16 hex chars, uppercase) of each path above, in the same
#: order — the pin. A mismatch means the corpus file changed since this was
#: written, and this test is checking that as much as it is checking geometry.
_PINNED_CORPUS_SHA16 = (
    "DF4905B76381B48D", "3D8D7F8F43ED2A06", "393547C0407F1A87", "040261AC8183C1EF",
    "CD7E104D7474DD68", "6EFD091D2A38B437", "1C1DA63082C5D724", "A198CD1DEE8C154B",
    "A26ECE4F32488CEC", "58FE8A5C3D8760D6", "90BA1E7A5D5822A6", "AF60A6EB9CEBB451",
)


@pytest.mark.parametrize("relative_path,expected_sha16", list(zip(_PINNED_CORPUS_RELATIVE_PATHS, _PINNED_CORPUS_SHA16)))
def test_geometry_from_pdf_is_byte_identical_on_the_pinned_corpus(relative_path, expected_sha16):
    data = (CORPUS / relative_path).read_bytes()
    assert hashlib.sha256(data).hexdigest().upper()[:16] == expected_sha16, (
        "the pinned corpus file's content changed since this pin was written"
    )
    _assert_geometry_equal(_legacy_geometry_from_pdf(data), geometry_from_pdf(data))


def test_geometry_from_a_pdf_without_native_text_is_still_none():
    """The two pre-existing garbage-bytes pins from `tests/test_structurer.py`,
    re-proven equal to the legacy copy (not just `is None`)."""
    for data in (b"not a pdf at all", b"%PDF-1.4\n garbage \n%%EOF"):
        assert _legacy_geometry_from_pdf(data) is None
        assert geometry_from_pdf(data) is None


# ===========================================================================
# item 4 — one grouping rule
# ===========================================================================

def test_group_lines_is_a_thin_wrapper_with_no_second_tolerance_computation():
    """M4: a mutant that reintroduces `median(...) * 0.5` (or any tolerance
    arithmetic) directly in `geometry.py` must be caught even if every other
    test still passes by coincidence. AST, not a string search, so a
    reformatted call cannot dodge it."""
    source = (ROOT / "analysis" / "structurer" / "geometry.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = [
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "median"
    ]
    assert not offenders, "geometry.py must not compute a tolerance itself; delegate to evidence.group_lines"
    assert "import median" not in source and "from statistics" not in source


def test_group_lines_wrapper_matches_the_canonical_rule_on_a_larger_document():
    """A second, independent check beside the already-committed
    `test_the_grouping_rule_matches_the_structurer_native_grouping_exactly`
    (`tests/test_evidence_canonical.py`): five rows, three columns, built the
    way `geometry_from_pdf` builds `Word`s (list order, not pre-sorted)."""
    words = [
        Word(f"R{row}C{col}", 40.0 + col * 90.0, 100.0 + row * 20.0, 40.0 + col * 90.0 + 30.0, 100.0 + row * 20.0 + 8.0)
        for row in range(5) for col in range(3)
    ]
    lines = _group_lines(1, words)
    assert [line.text for line in lines] == [
        f"R{row}C0 R{row}C1 R{row}C2" for row in range(5)
    ]
    assert all(line.page == 1 for line in lines)


# ===========================================================================
# item 5 — coordinate conventions
# ===========================================================================

def _pixel_frame(*, dpi: float = 300.0, page_index: int = 0) -> PageFrame:
    width_pt, height_pt = LETTER_PT
    return PageFrame.pixel(
        page_index=page_index,
        raster_width_px=round(width_pt / 72 * dpi),
        raster_height_px=round(height_pt / 72 * dpi),
        dpi=dpi, pdf_width_pt=width_pt, pdf_height_pt=height_pt,
    )


def _pixel_word(frame: PageFrame, text: str, x0_pt: float, y0_pt: float, x1_pt: float, y1_pt: float,
                *, index: int, line_ref: int, confidence: float = 0.9) -> WordBox:
    """A word authored in PDF points, expressed as this frame's pixels — the
    shape a Paddle adapter would build (word boxes in raster pixels)."""
    scale_x, scale_y = frame.scale_x, frame.scale_y
    return WordBox(
        word_id=word_id(frame.page_index, line_ref, index), page_index=frame.page_index, text=text,
        x0=round(x0_pt * scale_x, 3), y0=round(y0_pt * scale_y, 3),
        x1=round(x1_pt * scale_x, 3), y1=round(y1_pt * scale_y, 3),
        confidence=confidence, line_ref=line_ref,
    )


def test_a_pixel_evidence_round_trips_through_geometry_within_1e6_points():
    """CASE 5 (geometry half): a synthetic PIXEL evidence (a letter page at
    300 dpi; a header row and three ledger rows) -> `geometry_from_evidence`
    -> every `Word` box in points; `to_pixels` on each corner reproduces the
    original pixel box within 1e-6; the frame/source are recorded; line texts
    equal the evidence's own `page_text`; `GeoLine.x_at` answers in points."""
    frame = _pixel_frame()
    rows_pt = [
        [("DATE", 40.0, 100.0, 70.0, 110.0), ("DESCRIPTION", 100.0, 100.0, 200.0, 110.0), ("AMOUNT", 400.0, 100.0, 450.0, 110.0)],
        [("01/02/2054", 40.0, 120.0, 100.0, 130.0), ("ACH TRANSFER", 100.0, 120.0, 220.0, 130.0), ("12.34", 400.0, 120.0, 440.0, 130.0)],
        [("01/05/2054", 40.0, 140.0, 100.0, 150.0), ("CARD DEBIT", 100.0, 140.0, 200.0, 150.0), ("56.78", 400.0, 140.0, 440.0, 150.0)],
        [("01/09/2054", 40.0, 160.0, 100.0, 170.0), ("DEPOSIT", 100.0, 160.0, 170.0, 170.0), ("9,940.27", 400.0, 160.0, 430.0, 170.0)],
    ]
    words = []
    for line_ref, row in enumerate(rows_pt):
        for index, (text, x0, y0, x1, y1) in enumerate(row):
            words.append(_pixel_word(frame, text, x0, y0, x1, y1, index=index, line_ref=line_ref))
    page = PageEvidence(frame=frame, words=tuple(words))
    evidence = ExtractionEvidence(
        document_sha256="B" * 64, extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=(page,),
    )

    geometry = geometry_from_evidence(evidence)
    assert geometry is not None
    assert len(geometry.pages) == 1
    page_geometry = geometry.pages[0]
    assert page_geometry.page == 1
    assert page_geometry.frame is frame
    assert page_geometry.frame.space == "pixel"
    assert page_geometry.source == "paddle-ocr"
    assert (page_geometry.width, page_geometry.height) == (frame.pdf_width_pt, frame.pdf_height_pt)

    # Every corner survives points -> pixels within 1e-6 of the original.
    original_by_id = {w.word_id: w for w in words}
    for line, source_line in zip(page_geometry.lines, page.lines):
        for word, wid in zip(line.words, source_line.word_ids):
            original = original_by_id[wid]
            back_x0, back_y0 = to_pixels(frame, word.x0, word.y0)
            back_x1, back_y1 = to_pixels(frame, word.x1, word.y1)
            assert back_x0 == pytest.approx(original.x0, abs=1e-6)
            assert back_y0 == pytest.approx(original.y0, abs=1e-6)
            assert back_x1 == pytest.approx(original.x1, abs=1e-6)
            assert back_y1 == pytest.approx(original.y1, abs=1e-6)

    assert [line.text for line in page_geometry.lines] == list(page_text(page).split("\n"))
    first_line = page_geometry.lines[0]
    # F-4: compared against an INDEPENDENTLY derived point value (the pixel
    # box divided by the frame's own scale), not the same converted word's
    # own x0 -- a self-referential comparison holds in any unit and cannot
    # catch a unit error.
    first_word_px = original_by_id[page.lines[0].word_ids[0]]
    expected_x0_pt = first_word_px.x0 / frame.scale_x
    assert first_line.x_at(0) == pytest.approx(expected_x0_pt, abs=1e-6)


def test_a_pixel_evidence_with_distinct_per_axis_scale_converts_each_axis_correctly():
    """BLOCK-1: a rasteriser that rounds one page dimension to a different
    pixel count than the other produces DISTINCT `scale_x`/`scale_y` (legal
    under `evidence/canonical.py`'s own validation -- both scales need only
    agree with dpi/72 within 1%, independently). Every pixel frame the rest
    of this file builds (`_pixel_frame`) derives both scales from a single
    `dpi`, so on those frames alone a bug that uses one axis' scale for the
    other is numerically invisible. This frame makes the two axes
    distinguishable, and the assertions compare the converted point values
    against the AUTHORED point coordinates directly -- not only a round-trip
    through `to_pixels`, which is included too but composes the SAME wrong
    scale with itself in the reverse direction and only fails when the two
    scales genuinely differ (which is exactly why this frame, not
    `_pixel_frame()`, is required)."""
    frame = PageFrame.pixel(
        page_index=0, raster_width_px=2550, raster_height_px=3320,
        dpi=300.0, pdf_width_pt=612.0, pdf_height_pt=792.0,
    )
    assert frame.scale_x != frame.scale_y  # the property this frame exists to provide

    authored = [
        ("DATE", 40.0, 100.0, 70.0, 110.0),
        ("AMOUNT", 400.0, 160.0, 450.0, 172.0),
    ]
    # Built with the EXACT pixel value (no 3-decimal rounding, unlike
    # `_pixel_word`) so the 1e-6 bound below measures conversion arithmetic
    # only, not a deliberately coarsened fixture.
    words = tuple(
        WordBox(
            word_id=word_id(0, 0, index), page_index=0, text=text,
            x0=x0 * frame.scale_x, y0=y0 * frame.scale_y,
            x1=x1 * frame.scale_x, y1=y1 * frame.scale_y,
        )
        for index, (text, x0, y0, x1, y1) in enumerate(authored)
    )
    page = PageEvidence(frame=frame, words=words)
    evidence = ExtractionEvidence(
        document_sha256="F" * 64, extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=(page,),
    )
    geometry = geometry_from_evidence(evidence)
    assert geometry is not None
    converted_words = geometry.pages[0].lines[0].words
    for (_, x0, y0, x1, y1), word in zip(authored, converted_words):
        assert word.x0 == pytest.approx(x0, abs=1e-6)
        assert word.y0 == pytest.approx(y0, abs=1e-6)
        assert word.x1 == pytest.approx(x1, abs=1e-6)
        assert word.y1 == pytest.approx(y1, abs=1e-6)
        # the round-trip too, now meaningful since scale_x != scale_y
        back_x0, back_y0 = to_pixels(frame, word.x0, word.y0)
        assert back_x0 == pytest.approx(x0 * frame.scale_x, abs=1e-6)
        assert back_y0 == pytest.approx(y0 * frame.scale_y, abs=1e-6)


# The 1.5 pt bound the card names for comparing a native read and an
# independently-authored pixel-style estimate of the SAME printed rows. The
# pixel evidence's box SHAPE (width from `fitz.Font("helv").text_length`,
# ascent/descent from the same font's published metrics) is computed from
# font metrics directly rather than read off `page.get_text("words")`'s own
# per-word bbox output — a distinct code path from the one under test, not a
# copy of its answer — and then perturbed by a small deterministic jitter
# (<= 0.6 pt per coordinate, alternating sign) to stand in for two
# extractors never agreeing to the sub-point level, and finally expressed as
# a pixel box at 150 dpi (Paddle's boxes are integer-shaped; the frame's
# scale is exact here, so the only extra error is the jitter itself). The
# measured maximum per-corner delta against the real PyMuPDF glyph boxes is
# asserted below; measured once while writing this test: 0.6002 pt (the
# 0.6 pt jitter plus float noise) — comfortably inside the 1.5 pt bound; the
# two sources still agree closely because the layout is the same layout,
# not because the pipeline forced them to.
_MIXED_SOURCE_ROWS = [
    [("DATE", 72.0), ("DESCRIPTION", 172.0), ("AMOUNT", 432.0)],
    [("01/02/2054", 72.0), ("ACH", 172.0), ("12.34", 432.0)],
    [("01/05/2054", 72.0), ("DEBIT", 172.0), ("56.78", 432.0)],
]
_MIXED_SOURCE_BASELINES = (100.0, 120.0, 140.0)
_MIXED_SOURCE_FONTSIZE = 10.0
_WORD_BOX_AGREEMENT_BOUND_PT = 1.5


def _nominal_box(text: str, x: float, baseline: float, fontsize: float, jitter: float) -> tuple[float, float, float, float]:
    """An independent box estimate: real Helvetica metrics for the box
    SHAPE (so this test measures the jitter, not a guessed font), perturbed
    by `jitter` to emulate two extractors reading the same glyphs slightly
    differently."""
    import fitz

    font = fitz.Font("helv")
    width = font.text_length(text, fontsize=fontsize)
    x0 = x + jitter
    x1 = x + width + jitter
    y0 = baseline - font.ascender * fontsize - jitter
    y1 = baseline - font.descender * fontsize - jitter
    return x0, y0, x1, y1


def test_a_native_read_and_an_independently_authored_pixel_read_of_the_same_rows_agree_within_1_5pt():
    """CASE 5/6: the same printed rows, read two ways."""
    pdf_bytes = _render_pdf(_MIXED_SOURCE_ROWS, fontsize=_MIXED_SOURCE_FONTSIZE)
    native_evidence = native_evidence_from_pdf(pdf_bytes)
    assert native_evidence is not None
    native_geometry = geometry_from_evidence(native_evidence)
    assert native_geometry.pages[0].frame.space == "pdf_point"
    assert native_geometry.pages[0].source == NATIVE_EXTRACTOR_ID

    dpi = 150.0
    frame = _pixel_frame(dpi=dpi)
    words = []
    flat_index = 0
    for line_ref, (row, baseline) in enumerate(zip(_MIXED_SOURCE_ROWS, _MIXED_SOURCE_BASELINES)):
        for index, (text, x) in enumerate(row):
            jitter = 0.6 if flat_index % 2 == 0 else -0.6
            x0, y0, x1, y1 = _nominal_box(text, x, baseline, _MIXED_SOURCE_FONTSIZE, jitter)
            words.append(_pixel_word(frame, text, x0, y0, x1, y1, index=index, line_ref=line_ref))
            flat_index += 1
    pixel_page = PageEvidence(frame=frame, words=tuple(words))
    pixel_evidence = ExtractionEvidence(
        document_sha256="C" * 64, extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=(pixel_page,),
    )
    pixel_geometry = geometry_from_evidence(pixel_evidence)

    native_lines = native_geometry.pages[0].lines
    pixel_lines = pixel_geometry.pages[0].lines
    assert [line.text for line in native_lines] == [line.text for line in pixel_lines]

    max_delta = 0.0
    for native_line, pixel_line in zip(native_lines, pixel_lines):
        for native_word, pixel_word in zip(native_line.words, pixel_line.words):
            for a, b in zip((native_word.x0, native_word.y0, native_word.x1, native_word.y1),
                            (pixel_word.x0, pixel_word.y0, pixel_word.x1, pixel_word.y1)):
                max_delta = max(max_delta, abs(a - b))
    assert max_delta < _WORD_BOX_AGREEMENT_BOUND_PT, f"measured max delta {max_delta:.4f} pt"


def test_mixed_coordinate_spaces_on_one_document_are_legal():
    """A page-0-pixel / page-1-pdf_point document (the Phase 2.4 shape) —
    each page converts by its own frame; neither infects the other."""
    pixel_frame = _pixel_frame(page_index=0)
    pixel_word = _pixel_word(pixel_frame, "PIXELWORD", 40.0, 100.0, 140.0, 112.0, index=0, line_ref=0)
    pixel_page = PageEvidence(frame=pixel_frame, words=(pixel_word,))

    point_frame = PageFrame.pdf_points(page_index=1, width_pt=612.0, height_pt=792.0)
    point_word = WordBox(word_id=word_id(1, 0, 0), page_index=1, text="POINTWORD",
                         x0=40.0, y0=100.0, x1=140.0, y1=112.0, line_ref=0)
    point_page = PageEvidence(frame=point_frame, words=(point_word,))

    evidence = ExtractionEvidence(
        document_sha256="D" * 64, extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=(pixel_page, point_page),
    )
    geometry = geometry_from_evidence(evidence)
    assert geometry is not None
    assert geometry.pages[0].frame.space == "pixel"
    assert geometry.pages[1].frame.space == "pdf_point"
    assert geometry.pages[0].lines[0].text == "PIXELWORD"
    assert geometry.pages[1].lines[0].text == "POINTWORD"
    # The pdf_point page's word box is untouched by conversion (identity).
    assert (geometry.pages[1].lines[0].words[0].x0, geometry.pages[1].lines[0].words[0].y0) == (40.0, 100.0)


def test_malformed_geometry_cannot_reach_geometry_from_evidence_because_it_cannot_be_built():
    """CASE 8: an inverted box, a box outside its raster, a scale that
    disagrees with dpi, and a line referencing a word its page lacks all
    refuse at construction in `evidence/` — `geometry_from_evidence` never
    sees them because they cannot exist as `ExtractionEvidence` objects."""
    frame = _pixel_frame()
    with pytest.raises(MalformedGeometry):
        WordBox(word_id="p0.l0.w0", page_index=0, text="x", x0=10.0, y0=10.0, x1=5.0, y1=20.0)
    with pytest.raises(MalformedGeometry):
        PageEvidence(frame=frame, words=(
            WordBox(word_id="p0.l0.w0", page_index=0, text="spill", x0=2540.0, y0=10.0, x1=2560.0, y1=40.0),
        ))
    with pytest.raises(MalformedGeometry):
        PageFrame.pixel(page_index=0, raster_width_px=2550, raster_height_px=3300,
                        dpi=200.0, pdf_width_pt=612.0, pdf_height_pt=792.0)
    known_word = WordBox(word_id="p0.l0.w0", page_index=0, text="ok", x0=10.0, y0=10.0, x1=30.0, y1=20.0)
    bad_line = LineBox(line_id="p0.L0", page_index=0, y_top=10.0, y_bottom=20.0,
                       word_ids=("p0.l0.w9",), text="ok")
    with pytest.raises(Exception):
        PageEvidence(frame=frame, words=(known_word,), lines=(bad_line,))


def test_geometry_from_evidence_never_raises_on_a_hostile_duck_typed_object():
    """`geometry_from_evidence` is typed to take `ExtractionEvidence`, but the
    boundary is a real refusal, not a type hint: a duck-typed stand-in whose
    `words`/`lines` are not actually `WordBox`/`LineBox` instances (something
    no REAL `PageEvidence` can ever hold — its own constructor refuses that)
    yields `None`, never an exception."""
    frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    hostile_page = SimpleNamespace(
        frame=frame, page_index=0,
        words=(SimpleNamespace(word_id="p0.l0.w0", x0=0.0, y0=0.0, x1=1.0, y1=1.0, text="x"),),
        lines=(SimpleNamespace(line_id="p0.L0", page_index=0, word_ids=("p0.l0.w0",), text="x"),),
        notes=(),
    )
    hostile_evidence = SimpleNamespace(pages=(hostile_page,), extractor_id="hostile")
    assert geometry_from_evidence(hostile_evidence) is None
    assert geometry_from_evidence(None) is None

    hostile_frame_object = SimpleNamespace(pages=(SimpleNamespace(frame=object(), page_index=0, words=(), lines=(), notes=()),), extractor_id="hostile")
    assert geometry_from_evidence(hostile_frame_object) is None

    # F-1: the two isinstance guards above (`:318`, `:322`) return `None` on
    # their own path and never touch the broad `except Exception: return
    # None` — the *untested* guard load-bearing in production. These two
    # shapes reach it. (1) A REAL `WordBox` + a REAL `LineBox` whose
    # `word_ids` names a word this page does not have -- the shape the card
    # itself describes ("whose `lines` reference a word id its page
    # lacks"); a genuine `PageEvidence` already refuses to hold this
    # (`tests/test_evidence_canonical.py::
    # test_lines_supplied_explicitly_must_reference_this_page_words`), so it
    # is only reachable here via the same SimpleNamespace bypass every other
    # case in this test uses, and it raises `KeyError` inside
    # `geometry_from_evidence`'s own line-rebuilding loop, not at any
    # isinstance check.
    real_frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    real_word = WordBox(word_id=word_id(0, 0, 0), page_index=0, text="ok", x0=10.0, y0=10.0, x1=30.0, y1=20.0)
    dangling_line = LineBox(line_id="p0.L0", page_index=0, y_top=10.0, y_bottom=20.0,
                            word_ids=("p0.l0.w9",), text="ok")
    dangling_page = SimpleNamespace(frame=real_frame, page_index=0, words=(real_word,),
                                    lines=(dangling_line,), notes=())
    assert geometry_from_evidence(SimpleNamespace(pages=(dangling_page,), extractor_id="hostile")) is None

    # (2) The reviewer's other shape ("a page missing `notes`") stopped
    # reaching the `except` once F-8 removed `geometry_from_evidence`'s only
    # read of `page.notes` -- a page lacking that attribute now builds
    # successfully, which is the intended effect of F-8, not a gap. This
    # substitutes an equally genuine except-reaching shape: a `words`
    # collection that raises partway through iteration (a hostile object can
    # make ANY attribute access misbehave, not only a missing one).
    class _ExplodingWords:
        def __iter__(self):
            yield real_word
            raise RuntimeError("simulated hostile iteration failure")

    exploding_page = SimpleNamespace(frame=real_frame, page_index=0, words=_ExplodingWords(),
                                     lines=(), notes=())
    assert geometry_from_evidence(SimpleNamespace(pages=(exploding_page,), extractor_id="hostile")) is None


def test_the_unreadable_native_page_placeholder_reports_its_own_frame_dimensions():
    """A page whose own `get_text`/`rect` read throws (a PyMuPDF failure this
    project's corpus has never produced) is kept — for page-number fidelity —
    with `UNREADABLE_PAGE_NOTE` and a minimal placeholder frame. Phase 2.0's
    reader hardcoded `width == height == 0.0` for this exact case; this cell
    no longer reproduces that number (P21-GEOMETRY-CLOSURE F-8: the neutral
    `geometry_from_evidence` must not branch on a note string, so it reports
    the placeholder frame's OWN declared dimensions like any other page,
    here `1.0 x 1.0`). A documented, RULED, untriggered (0/109 corpus PDFs)
    divergence from Phase 2.0 for this specific dead code path. Simulated by
    monkeypatching `fitz.Page.get_text` to raise for one page of a two-page
    document."""
    import fitz

    pdf_bytes = _render_pdf(_STRUCTURER_FIXTURE_ROWS, extra_pages=1)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    pdf_bytes = document.tobytes()
    document.close()

    real_get_text = fitz.Page.get_text

    def _exploding_get_text(self, *args, **kwargs):
        if self.number == 0:
            raise RuntimeError("simulated PyMuPDF failure")
        return real_get_text(self, *args, **kwargs)

    original = fitz.Page.get_text
    fitz.Page.get_text = _exploding_get_text
    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
        geometry = geometry_from_pdf(pdf_bytes)
    finally:
        fitz.Page.get_text = original

    assert evidence is not None
    assert UNREADABLE_PAGE_NOTE in evidence.pages[0].notes
    assert evidence.pages[0].words == ()
    assert geometry is not None
    assert (geometry.pages[0].width, geometry.pages[0].height) == (1.0, 1.0)
    assert geometry.pages[1].width > 0.0 and geometry.pages[1].lines


def test_a_page_with_one_refused_word_reports_its_real_dimensions_not_unreadable():
    """P21-GEOMETRY-CLOSURE F-5: a page whose `get_text`/`rect` read
    SUCCEEDS (a real frame exists) but whose PyMuPDF word list contains one
    box `evidence/`'s strict `x0 < x1 and y0 < y1` refuses gets
    `WORD_REFUSED_NOTE` — never `UNREADABLE_PAGE_NOTE`, which would mislabel
    a page that read fine — and reports the REAL page dimensions, not a
    placeholder's. The whole page is still refused down to zero words (the
    fail-closed direction is unchanged: no guessed structure, no silently
    dropping just the bad word); a sibling page is unaffected. This is a
    deliberate, documented, latent (0/261,526 words on the pinned corpus)
    divergence from Phase 2.0, which kept every word regardless."""
    import fitz

    pdf_bytes = _render_pdf(_STRUCTURER_FIXTURE_ROWS, extra_pages=1)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    pdf_bytes = document.tobytes()
    document.close()

    real_get_text = fitz.Page.get_text

    def _corrupting_get_text(self, *args, **kwargs):
        words = real_get_text(self, *args, **kwargs)
        if self.number == 0 and words:
            corrupted = list(words[0])
            corrupted[3] = corrupted[1]  # y1 = y0: a zero-height, refused box
            return [tuple(corrupted)] + list(words[1:])
        return words

    original = fitz.Page.get_text
    fitz.Page.get_text = _corrupting_get_text
    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
        geometry = geometry_from_pdf(pdf_bytes)
    finally:
        fitz.Page.get_text = original

    assert evidence is not None
    assert WORD_REFUSED_NOTE in evidence.pages[0].notes
    assert UNREADABLE_PAGE_NOTE not in evidence.pages[0].notes
    assert evidence.pages[0].words == ()
    assert geometry is not None
    # the REAL page dimensions (letter, 612x792), not a 1x1 placeholder
    assert (geometry.pages[0].width, geometry.pages[0].height) == pytest.approx((612.0, 792.0))
    assert geometry.pages[0].lines == ()
    assert geometry.pages[1].width > 0.0 and geometry.pages[1].lines


def test_rotation_is_recorded_never_corrected():
    """Item 5, rotation bullet: `rotation_deg` is recorded from `page.rotation`
    and a rotated native page carries `UNROTATED_WORDS_NOTE` — the byte-
    identical, un-fixed Phase 2.0 behaviour, documented as a Phase 2.2
    prerequisite. Measured over the pinned corpus below: 0/830 rotated pages
    (this cell's read-only measurement, `docs/agent-handoffs/P21-GEOMETRY.md`
    item 5) — this synthetic case exercises the code path the corpus never
    triggers."""
    pdf_bytes = _render_pdf(_MIXED_SOURCE_ROWS, rotate=90)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    frame = evidence.pages[0].frame
    assert frame.rotation_deg == 90
    assert UNROTATED_WORDS_NOTE in evidence.pages[0].notes

    unrotated = native_evidence_from_pdf(_render_pdf(_MIXED_SOURCE_ROWS, rotate=0))
    assert unrotated.pages[0].frame.rotation_deg == 0
    assert UNROTATED_WORDS_NOTE not in unrotated.pages[0].notes


def test_no_page_in_the_pinned_corpus_sample_is_rotated():
    """The read-only measurement (item 5): of the 12 pinned corpus PDFs
    (spanning 12 institution folders), 0 pages carry a non-zero rotation —
    consistent with the full 109-PDF / 830-page measurement recorded in this
    cell's W3 section. A future rotated corpus document would start failing
    this count-only assertion, which is exactly the point: it is the signal
    that the Phase 2.2 rotation prerequisite has become live."""
    rotated = 0
    total_pages = 0
    for relative_path in _PINNED_CORPUS_RELATIVE_PATHS:
        data = (CORPUS / relative_path).read_bytes()
        evidence = native_evidence_from_pdf(data)
        if evidence is None:
            continue
        for page in evidence.pages:
            total_pages += 1
            if page.frame.rotation_deg != 0:
                rotated += 1
    assert total_pages > 0
    assert rotated == 0


# ===========================================================================
# item 6 — page numbering convention
# ===========================================================================

def test_page_geometry_page_is_frame_page_index_plus_one_including_an_empty_middle_page():
    frame0 = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    word0 = WordBox(word_id=word_id(0, 0, 0), page_index=0, text="First", x0=40.0, y0=100.0, x1=80.0, y1=112.0)
    page0 = PageEvidence(frame=frame0, words=(word0,))

    frame1 = PageFrame.pdf_points(page_index=1, width_pt=612.0, height_pt=792.0)
    page1 = PageEvidence(frame=frame1, words=())  # the empty middle page

    frame2 = PageFrame.pdf_points(page_index=2, width_pt=612.0, height_pt=792.0)
    word2 = WordBox(word_id=word_id(2, 0, 0), page_index=2, text="Third", x0=40.0, y0=100.0, x1=80.0, y1=112.0)
    page2 = PageEvidence(frame=frame2, words=(word2,))

    evidence = ExtractionEvidence(
        document_sha256="E" * 64, extractor_id=NATIVE_EXTRACTOR_ID, model_token=NATIVE_EXTRACTOR_ID,
        pages=(page0, page1, page2),
    )
    geometry = geometry_from_evidence(evidence)
    assert geometry is not None
    assert len(geometry.pages) == 3
    for page_geometry, page_evidence in zip(geometry.pages, evidence.pages):
        assert page_geometry.page == page_evidence.frame.page_index + 1
    assert geometry.pages[1].lines == ()  # kept, empty, page number still true


# ===========================================================================
# `PageGeometry` default-backward-compatibility (item 4)
# ===========================================================================

def test_page_geometry_defaults_keep_every_existing_positional_constructor_call_valid():
    page = PageGeometry(1, 612.0, 792.0, ())
    assert page.frame is None
    assert page.source == "native"


def test_generic_structurer_stays_disabled_by_default():
    """`GENERIC_STRUCTURER_ENABLED` stays unset in this cell (Phase 2.1
    exclusion: no structurer enablement)."""
    import os

    assert STRUCTURER_ENV not in os.environ
    assert structurer_enabled() is False

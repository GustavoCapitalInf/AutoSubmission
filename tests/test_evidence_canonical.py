"""Phase 2.1 cell 0: the canonical-evidence contract (`evidence/canonical.py`).

Proves, without any extractor: the coordinate conventions (origin, axes, box
order, the two spaces never interchangeable, scale/dpi agreement), the
refusals (CASE 8: inverted/degenerate boxes, out-of-raster words, mixed pages,
missing dpi — refused, never swapped or clamped), immutability and hashing of
raw evidence, deterministic JSON round-trip that reproduces every sha, the ONE
line-grouping rule (identical partition to `analysis/structurer/geometry.py`'s
native grouping on the same words), and `page_text`'s construction.
"""
from __future__ import annotations

import json
import random
from types import MappingProxyType

import pytest

from evidence import (
    EVIDENCE_SCHEMA_VERSION,
    PDF_POINT,
    PIXEL,
    EvidenceError,
    ExtractionEvidence,
    LineBox,
    MalformedGeometry,
    PageEvidence,
    PageFrame,
    WordBox,
    from_json,
    group_lines,
    page_text,
    sha256_of_json,
    to_json,
    to_pdf_points,
    to_pixels,
    word_id,
)

DOC_SHA = "A" * 64
LETTER_PT = (612.0, 792.0)


def _pixel_frame(page_index: int = 0, raster_dpi: float = 300.0, **overrides) -> PageFrame:
    """A letter page rasterised at `raster_dpi`; `overrides` replace fields
    AFTER the raster dimensions are derived, so `dpi=200.0` in `overrides`
    declares a dpi that disagrees with a 300-dpi raster (the mismatch shape)."""
    width_pt, height_pt = LETTER_PT
    fields = dict(
        page_index=page_index,
        raster_width_px=round(width_pt / 72 * raster_dpi),
        raster_height_px=round(height_pt / 72 * raster_dpi),
        dpi=raster_dpi, pdf_width_pt=width_pt, pdf_height_pt=height_pt,
    )
    fields.update(overrides)
    return PageFrame.pixel(**fields)


def _word(page: int, text: str, x0: float, y0: float, x1: float, y1: float, *, index: int,
          line_ref: int | None = None, confidence: float | None = None) -> WordBox:
    return WordBox(word_id=word_id(page, line_ref, index), page_index=page, text=text,
                   x0=x0, y0=y0, x1=x1, y1=y1, confidence=confidence, line_ref=line_ref)


# ---------------------------------------------------------------------------
# Frames and conversions
# ---------------------------------------------------------------------------

def test_pixel_frame_derives_scales_that_agree_with_dpi():
    frame = _pixel_frame()
    assert frame.space == PIXEL
    assert (frame.raster_width_px, frame.raster_height_px) == (2550, 3300)
    assert frame.scale_x == pytest.approx(300 / 72)
    assert frame.scale_y == pytest.approx(300 / 72)


def test_pdf_point_frame_has_unit_scale_and_no_raster_fields():
    frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    assert frame.space == PDF_POINT
    assert (frame.scale_x, frame.scale_y) == (1.0, 1.0)
    assert frame.dpi is None and frame.raster_width_px is None and frame.raster_sha256 is None
    assert (frame.pdf_width_pt, frame.pdf_height_pt) == (612.0, 792.0)


@pytest.mark.parametrize("bad", [
    dict(dpi=200.0),                        # dpi says 2.78 px/pt, raster says 4.17 px/pt
    dict(raster_width_px=2000),             # raster/pdf ratio disagrees with dpi on one axis
    dict(pdf_width_pt=500.0),               # the PDF page is not the page this raster came from
])
def test_pixel_frame_refuses_a_scale_that_disagrees_with_its_dpi(bad):
    with pytest.raises(MalformedGeometry):
        _pixel_frame(**bad)


def test_pixel_frame_requires_dpi_and_raster_dimensions():
    with pytest.raises(MalformedGeometry):
        PageFrame(page_index=0, space=PIXEL, width=100.0, height=100.0, pdf_width_pt=24.0,
                  pdf_height_pt=24.0, raster_width_px=100, raster_height_px=100, dpi=None,
                  scale_x=100 / 24, scale_y=100 / 24)
    with pytest.raises(MalformedGeometry):
        PageFrame(page_index=0, space=PIXEL, width=100.0, height=100.0, pdf_width_pt=24.0,
                  pdf_height_pt=24.0, dpi=300.0, scale_x=100 / 24, scale_y=100 / 24)


def test_pdf_point_frame_refuses_raster_fields_and_a_non_unit_scale():
    with pytest.raises(MalformedGeometry):
        PageFrame(page_index=0, space=PDF_POINT, width=612.0, height=792.0, dpi=300.0)
    with pytest.raises(MalformedGeometry):
        PageFrame(page_index=0, space=PDF_POINT, width=612.0, height=792.0, scale_x=2.0)


def test_unknown_space_rotation_and_negative_page_index_are_refused():
    with pytest.raises(EvidenceError):
        PageFrame(page_index=0, space="inches", width=1.0, height=1.0)
    with pytest.raises(MalformedGeometry):
        PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0, rotation_deg=45)
    with pytest.raises(EvidenceError):
        PageFrame.pdf_points(page_index=-1, width_pt=612.0, height_pt=792.0)


def test_pixel_to_point_to_pixel_round_trip_is_exact_to_1e6():
    frame = _pixel_frame()
    for x, y in ((0.0, 0.0), (152.0, 22.0), (2549.0, 3299.0), (1234.5, 987.25)):
        px, py = to_pdf_points(frame, x, y)
        back = to_pixels(frame, px, py)
        assert back == pytest.approx((x, y), abs=1e-6)
    # And the points are what dpi/72 says they are.
    assert to_pdf_points(frame, 2550.0, 3300.0) == pytest.approx((612.0, 792.0))


def test_a_pdf_point_frame_cannot_be_asked_for_pixels():
    frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    assert to_pdf_points(frame, 10.0, 20.0) == (10.0, 20.0)
    with pytest.raises(MalformedGeometry):
        to_pixels(frame, 10.0, 20.0)


# ---------------------------------------------------------------------------
# Words: box order enforced, never repaired (CASE 8)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("box", [
    (10, 10, 5, 20),     # x inverted
    (10, 20, 30, 10),    # y inverted
    (10, 10, 10, 20),    # zero width
    (10, 10, 30, 10),    # zero height
])
def test_inverted_or_degenerate_boxes_are_refused_not_swapped(box):
    with pytest.raises(MalformedGeometry):
        _word(0, "x", *box, index=0)


def test_word_coordinates_are_floats_and_nan_is_refused():
    word = _word(0, "x", 1, 2, 3, 4, index=0)
    assert (word.x0, word.y0, word.x1, word.y1) == (1.0, 2.0, 3.0, 4.0)
    assert isinstance(word.x0, float)
    with pytest.raises(MalformedGeometry):
        _word(0, "x", float("nan"), 2, 3, 4, index=0)


def test_empty_text_and_out_of_range_confidence_are_refused():
    with pytest.raises(EvidenceError):
        _word(0, "   ", 1, 2, 3, 4, index=0)
    with pytest.raises(EvidenceError):
        _word(0, "x", 1, 2, 3, 4, index=0, confidence=1.5)
    assert _word(0, "x", 1, 2, 3, 4, index=0, confidence=0.25).confidence == 0.25


def test_word_ids_follow_the_page_line_index_scheme():
    assert word_id(0, 3, 2) == "p0.l3.w2"
    assert word_id(4, None, 0) == "p4.l-.w0"


# ---------------------------------------------------------------------------
# Pages: frame/page agreement, raster bounds, raw immutability
# ---------------------------------------------------------------------------

def test_a_word_outside_its_raster_refuses_the_page():
    frame = _pixel_frame()
    inside = _word(0, "ok", 10, 10, 50, 40, index=0)
    outside = _word(0, "spill", 2540, 10, 2560, 40, index=1)
    PageEvidence(frame=frame, words=(inside,))
    with pytest.raises(MalformedGeometry):
        PageEvidence(frame=frame, words=(inside, outside))


def test_a_pdf_point_frame_is_a_viewport_a_word_outside_it_constructs_unmodified():
    """CASE 15 as RULED at the Phase 2.2 closure (option c). Between this
    cell's first commit and its closure a `pdf_point` box outside
    `[0, width] x [0, height]` refused the page; measured over the archive
    that refused every page of 102 documents (89 validated) for margin
    headers and footers — defeating the lineage the evidence exists for. A
    `pdf_point` frame is a VIEWPORT: a box outside it is a faithful record of
    where the PDF put the word and CONSTRUCTS, untouched — never clamped,
    never swapped, never dropped; `inside_frame` (the ONE bounds rule) says
    it is outside, and the native reader records that as a note. The
    representation is unchanged: `EVIDENCE_SCHEMA_VERSION` stays 1."""
    from evidence import inside_frame

    frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    inside = _word(0, "inside", 10.0, 10.0, 50.0, 20.0, index=0)
    assert inside_frame(frame, inside.x0, inside.y0, inside.x1, inside.y1)
    for box in (
        (-2.0, 10.0, 20.0, 20.0),        # past the left edge (the Phase 2.1 "bleed" shape)
        (600.0, 10.0, 620.0, 20.0),      # past the right edge
        (10.0, -0.5, 50.0, 20.0),        # past the top edge, sub-point
        (10.0, 780.0, 50.0, 800.0),      # past the bottom edge
        (10.0, 792.0 + 30.0, 50.0, 792.0 + 40.0),  # wholly off the page
    ):
        outside = _word(0, "outside", *box, index=1)
        page = PageEvidence(frame=frame, words=(inside, outside))
        assert page.words == (inside, outside)
        assert (outside.x0, outside.y0, outside.x1, outside.y1) == tuple(float(v) for v in box)
        assert not inside_frame(frame, outside.x0, outside.y0, outside.x1, outside.y1)
    # a box exactly ON the edges is inside (closed interval)
    edge = _word(0, "edge", 0.0, 0.0, 612.0, 792.0, index=2)
    assert inside_frame(frame, edge.x0, edge.y0, edge.x1, edge.y1)
    assert EVIDENCE_SCHEMA_VERSION == 1


def test_a_pixel_frame_is_a_container_a_word_outside_it_refuses():
    """The other half of the rule: a raster physically cannot hold a box
    outside itself, so the SAME overshoot that a `pdf_point` frame admits
    refuses a `pixel` frame (M4: the viewport rule re-applied to pixels, or
    the container rule re-applied to points, fails one of these two)."""
    from evidence import inside_frame

    pixel = _pixel_frame()
    point = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    for frame in (pixel, point):
        spill = _word(0, "spill", frame.width - 5.0, 10.0, frame.width + 5.0, 40.0, index=0)
        assert not inside_frame(frame, spill.x0, spill.y0, spill.x1, spill.y1)
        ok = _word(0, "ok", frame.width - 15.0, 10.0, frame.width, 40.0, index=1)
        assert PageEvidence(frame=frame, words=(ok,)).words == (ok,)
        if frame.space == PIXEL:
            with pytest.raises(MalformedGeometry):
                PageEvidence(frame=frame, words=(spill,))
        else:
            assert PageEvidence(frame=frame, words=(spill,)).words == (spill,)


def test_every_existing_evidence_fixture_in_this_file_still_constructs():
    """Item 3's proof obligation: the validation tightened, the shape did not
    — every evidence this file builds (pixel and pdf_point, with and without
    raw) still constructs and still round-trips with its sha reproduced."""
    for with_raw in (True, False):
        evidence = _document(with_raw=with_raw)
        rebuilt = from_json(to_json(evidence))
        assert rebuilt.evidence_sha256 == evidence.evidence_sha256
    frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    words = (
        _word(0, "AMOUNT", 500.0, 100.0, 560.0, 110.0, index=0),
        _word(0, "DATE", 50.0, 100.5, 90.0, 110.5, index=1),
    )
    assert len(PageEvidence(frame=frame, words=words).lines) == 1


def test_words_from_another_page_or_duplicate_ids_are_refused():
    frame = _pixel_frame(page_index=0)
    with pytest.raises(MalformedGeometry):
        PageEvidence(frame=frame, words=(_word(1, "x", 1, 1, 5, 5, index=0),))
    a = _word(0, "x", 1, 1, 5, 5, index=0)
    b = _word(0, "y", 10, 1, 15, 5, index=0)  # same word_id
    with pytest.raises(EvidenceError):
        PageEvidence(frame=frame, words=(a, b))


def test_raw_evidence_is_deep_frozen_and_hashed():
    frame = _pixel_frame()
    raw = {"rec_texts": ["a", "b"], "rec_boxes": [[1, 2, 3, 4]], "nested": {"k": [1, {"z": 2}]}}
    page = PageEvidence(frame=frame, words=(_word(0, "a", 1, 2, 3, 4, index=0),), raw=raw)
    assert isinstance(page.raw, MappingProxyType)
    assert isinstance(page.raw["rec_texts"], tuple)
    assert isinstance(page.raw["nested"]["k"][1], MappingProxyType)
    with pytest.raises(TypeError):
        page.raw["rec_texts"] = ["mutated"]  # type: ignore[index]
    with pytest.raises(TypeError):
        page.raw["nested"]["k"][1]["z"] = 3  # type: ignore[index]
    assert page.raw_sha256 == sha256_of_json(raw)
    # Mutating the ORIGINAL dict after construction changes nothing inside.
    raw["rec_texts"].append("c")
    assert page.raw["rec_texts"] == ("a", "b")
    assert page.raw_sha256 == sha256_of_json({"rec_texts": ["a", "b"], "rec_boxes": [[1, 2, 3, 4]],
                                              "nested": {"k": [1, {"z": 2}]}})


def test_a_claimed_raw_sha_that_does_not_reproduce_is_refused():
    frame = _pixel_frame()
    with pytest.raises(EvidenceError):
        PageEvidence(frame=frame, words=(), raw={"a": 1}, raw_sha256="0" * 64)
    with pytest.raises(EvidenceError):
        PageEvidence(frame=frame, words=(), raw=None, raw_sha256="0" * 64)


def test_raw_evidence_refuses_non_json_values():
    frame = _pixel_frame()
    with pytest.raises(EvidenceError):
        PageEvidence(frame=frame, words=(), raw={"bytes": b"\x00"})
    with pytest.raises(EvidenceError):
        PageEvidence(frame=frame, words=(), raw={"set": {1, 2}})


# ---------------------------------------------------------------------------
# Lines: THE grouping rule, and page_text
# ---------------------------------------------------------------------------

def test_lines_are_derived_by_vertical_overlap_and_ordered_left_to_right():
    frame = PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0)
    # Two rows; the second row's words arrive in scrambled order and at
    # slightly different baselines (as a real read produces them).
    words = (
        _word(0, "AMOUNT", 500.0, 100.0, 560.0, 110.0, index=0),
        _word(0, "DATE", 50.0, 100.5, 90.0, 110.5, index=1),
        _word(0, "DESCRIPTION", 150.0, 99.5, 260.0, 109.5, index=2),
        _word(0, "12.34", 500.0, 120.0, 560.0, 130.0, index=3),
        _word(0, "01/02", 50.0, 120.0, 90.0, 130.0, index=4),
        _word(0, "ACH", 150.0, 120.0, 180.0, 130.0, index=5),
        _word(0, "DEBIT", 185.0, 120.0, 230.0, 130.0, index=6),
    )
    page = PageEvidence(frame=frame, words=words)
    assert [line.text for line in page.lines] == ["DATE DESCRIPTION AMOUNT", "01/02 ACH DEBIT 12.34"]
    assert page.lines[0].word_ids == ("p0.l-.w1", "p0.l-.w2", "p0.l-.w0")
    assert page.lines[0].line_id == "p0.L0"
    assert page_text(page) == "DATE DESCRIPTION AMOUNT\n01/02 ACH DEBIT 12.34"


def test_group_lines_takes_one_page_only_and_is_deterministic():
    a = _word(0, "a", 1, 1, 5, 5, index=0)
    b = _word(1, "b", 1, 1, 5, 5, index=0)
    with pytest.raises(MalformedGeometry):
        group_lines((a, b))
    assert group_lines(()) == ()
    words = [_word(0, f"w{i}", 10.0 * i, 100.0 + (i % 3) * 30.0, 10.0 * i + 8.0,
                   108.0 + (i % 3) * 30.0, index=i) for i in range(30)]
    once = group_lines(words)
    shuffled = list(words)
    random.Random(7).shuffle(shuffled)
    assert group_lines(shuffled) == once


def test_the_grouping_rule_matches_the_structurer_native_grouping_exactly():
    """D1/D9: one rule. On the same words, the partition `geometry.py`'s
    `_group_lines` produces and this package's `group_lines` produce are
    identical — texts, order, and membership."""
    from analysis.structurer.geometry import Word, _group_lines

    rng = random.Random(11)
    words: list[WordBox] = []
    native: list[Word] = []
    for index in range(120):
        row = rng.randrange(0, 25)
        col = rng.randrange(0, 6)
        x0 = 40.0 + col * 90.0 + rng.random() * 5
        y0 = 60.0 + row * 14.0 + rng.random() * 2.5
        height = 7.0 + rng.random() * 2.0
        text = f"t{row}c{col}"
        words.append(_word(0, text, x0, y0, x0 + 30.0, y0 + height, index=index))
        native.append(Word(text, x0, y0, x0 + 30.0, y0 + height))
    ours = [line.text for line in group_lines(words)]
    theirs = [line.text for line in _group_lines(1, native)]
    assert ours == theirs


def test_group_lines_tolerance_scales_with_the_page_type_size():
    """6pt and 11pt renderings of the same two rows both regroup into two
    rows: the tolerance is relative to the median word height, not fixed."""
    for height in (6.0, 11.0):
        gap = height * 1.4
        words = (
            _word(0, "a", 10, 100, 20, 100 + height, index=0),
            _word(0, "b", 30, 100 + height * 0.3, 40, 100 + height * 1.3, index=1),
            _word(0, "c", 10, 100 + gap, 20, 100 + gap + height, index=2),
        )
        assert [line.text for line in group_lines(words)] == ["a b", "c"]


# ---------------------------------------------------------------------------
# Documents: hashing, round-trip, refusals
# ---------------------------------------------------------------------------

def _document(*, with_raw: bool = True) -> ExtractionEvidence:
    pages = []
    for page_index in range(2):
        frame = _pixel_frame(page_index=page_index)
        words = (
            _word(page_index, "Balance", 100, 100, 200, 130, index=0, line_ref=0, confidence=0.99),
            _word(page_index, "1,234.56", 400, 101, 520, 131, index=1, line_ref=0, confidence=0.99),
            _word(page_index, "Total", 100, 200, 160, 230, index=2, line_ref=1, confidence=0.5),
        )
        raw = {"rec_texts": ["Balance 1,234.56", "Total"], "rec_scores": [0.99, 0.5],
               "page_index": page_index} if with_raw else None
        pages.append(PageEvidence(frame=frame, words=words, raw=raw, notes=("synthetic",)))
    return ExtractionEvidence(
        document_sha256=DOC_SHA, extractor_id="paddle-ocr", model_token="paddle-ocr+ppocrv5",
        pages=tuple(pages),
        runtime={"provider": "vast.ai", "execution_class": "remote_paid", "paddleocr_version": "3.7.0"},
    )


def test_document_sha_reproduces_across_a_json_round_trip():
    evidence = _document()
    payload = to_json(evidence)
    text = json.dumps(payload, sort_keys=True)
    rebuilt = from_json(json.loads(text))
    assert rebuilt.evidence_sha256 == evidence.evidence_sha256
    assert rebuilt == evidence
    assert [p.raw_sha256 for p in rebuilt.pages] == [p.raw_sha256 for p in evidence.pages]
    assert rebuilt.page_texts() == evidence.page_texts() == ["Balance 1,234.56\nTotal"] * 2
    assert rebuilt.runtime["provider"] == "vast.ai"
    assert rebuilt.word_count == 6


def test_the_document_sha_covers_every_field_but_itself():
    base = _document()
    changed_runtime = ExtractionEvidence(
        document_sha256=base.document_sha256, extractor_id=base.extractor_id,
        model_token=base.model_token, pages=base.pages, runtime={"provider": "local"},
    )
    assert changed_runtime.evidence_sha256 != base.evidence_sha256
    changed_raw = _document(with_raw=False)
    assert changed_raw.evidence_sha256 != base.evidence_sha256


def test_a_drifted_cached_copy_is_refused():
    payload = to_json(_document())
    payload["pages"][0]["words"][1]["text"] = "1,234.57"  # one digit, in the cache
    with pytest.raises(EvidenceError):
        from_json(payload)
    payload = to_json(_document())
    payload["pages"][0]["raw"]["rec_scores"][0] = 1.0  # a score, in the cache
    with pytest.raises(EvidenceError):
        from_json(payload)


def test_schema_version_and_page_contiguity_are_enforced():
    payload = to_json(_document())
    payload["schema_version"] = EVIDENCE_SCHEMA_VERSION + 1
    with pytest.raises(EvidenceError):
        from_json(payload)
    frame1 = _pixel_frame(page_index=1)
    with pytest.raises(MalformedGeometry):
        ExtractionEvidence(document_sha256=DOC_SHA, extractor_id="x", model_token="x",
                           pages=(PageEvidence(frame=frame1, words=()),))
    with pytest.raises(EvidenceError):
        ExtractionEvidence(document_sha256="nope", extractor_id="x", model_token="x", pages=())


def test_documents_and_pages_are_frozen():
    evidence = _document()
    with pytest.raises((AttributeError, TypeError)):
        evidence.pages = ()  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        evidence.pages[0].words = ()  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        evidence.pages[0].words[0].text = "x"  # type: ignore[misc]
    with pytest.raises(TypeError):
        evidence.runtime["provider"] = "local"  # type: ignore[index]


def test_lines_supplied_explicitly_must_reference_this_page_words():
    frame = _pixel_frame()
    words = (_word(0, "a", 1, 1, 5, 5, index=0),)
    bad = LineBox(line_id="p0.L0", page_index=0, y_top=1.0, y_bottom=5.0, word_ids=("p0.l-.w9",), text="a")
    with pytest.raises(EvidenceError):
        PageEvidence(frame=frame, words=words, lines=(bad,))

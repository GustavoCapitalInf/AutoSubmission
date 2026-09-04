"""Phase 2.2 cell K (`docs/agent-handoffs/P22-IDENTITY.md` item 1; D3/D4;
cases 14, 16): the ONE native reader, `evidence/native.py::native_evidence_from_pdf`,
places every word box in the DISPLAY frame.

Proves, on synthetic PDFs only (invented rows, dates >= 2031, letter pages):

* the four-angle pin — ONE displayed page, produced four times with `/Rotate`
  0/90/180/270 (the same picture; for 90/270 the unrotated page is landscape
  and the content is pre-rotated into it as a form XObject, exactly the shape
  of a real rotated statement), yields the same line texts, the same word
  count, word boxes equal to the `/Rotate 0` boxes (measured tolerance in the
  test's docstring), AND boxes equal to what an INDEPENDENT rotation formula
  predicts from PyMuPDF's raw unrotated boxes — all inside the display frame;
* the transform agrees with Poppler's display orientation: the 72-dpi
  `pdf2image` raster of every rotated page is pixel-identical to the
  `/Rotate 0` raster, carries ink under every transformed box, and carries
  ink under FEWER untransformed (Phase 2.1) boxes than transformed ones;
* an unrotated page's boxes are PyMuPDF's raw boxes verbatim (the identity
  applied as the identity) — the Phase 2.1 byte-identity property;
* identity facts (`extractor_id`, `model_token`, `runtime`, `document_sha256`,
  `raw`/`confidence`/`line_ref` = None), the JSON round-trip reproducing the
  sha, and the `None` cases the Phase 2.1 reader had (garbage bytes, no
  words, PyMuPDF unimportable);
* the three page-level refusals, named separately: unreadable page,
  inverted word, and — new — a word outside the display frame after the
  transform refuses the page with `native_word_outside_frame` and its REAL
  frame; the retired Phase 2.1 note is never emitted.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

from evidence import (
    FRAME_DISPLAY,
    NATIVE_EXTRACTOR_ID,
    ROTATION_APPLIED_NOTE,
    UNREADABLE_PAGE_NOTE,
    WORD_OUTSIDE_FRAME_NOTE,
    WORD_REFUSED_NOTE,
    ExtractionEvidence,
    from_json,
    native_evidence_from_pdf,
    page_text,
    to_json,
)

ROOT = Path(__file__).resolve().parents[1]
LETTER = (612.0, 792.0)
RETIRED_NOTE = "native_words_unrotated_space"

_ROWS = [
    [("DATE", 72.0), ("DESCRIPTION", 172.0), ("AMOUNT", 432.0)],
    [("01/02/2054", 72.0), ("ACH", 172.0), ("12.34", 432.0)],
    [("01/05/2054", 72.0), ("DEBIT", 172.0), ("56.78", 432.0)],
    [("01/09/2054", 72.0), ("DEPOSIT", 172.0), ("9,940.27", 432.0)],
]
_BASELINE0 = 100.0
_PITCH = 20.0


def _render_upright(rows=_ROWS, *, fontsize: float = 10.0) -> bytes:
    """A one-column ledger on an unrotated letter page, real Helvetica glyphs
    at known baselines."""
    document = fitz.open()
    page = document.new_page(width=LETTER[0], height=LETTER[1])
    baseline = _BASELINE0
    for row in rows:
        for text, x in row:
            page.insert_text(fitz.Point(x, baseline), text, fontsize=fontsize, fontname="helv")
        baseline += _PITCH
    data = document.tobytes()
    document.close()
    return data


def _rotated_copy(upright: bytes, rotate: int, *, extra_pages: int = 0) -> bytes:
    """The SAME displayed page carrying `/Rotate` = `rotate`: for 90/270 the
    unrotated page is landscape, the upright page is drawn into it pre-rotated
    (`show_pdf_page(..., rotate=rotate)`), and `set_rotation` makes the display
    upright again — the shape of a real rotated statement, where PyMuPDF's
    unrotated-space word boxes differ from where the words are displayed."""
    if rotate == 0:
        if not extra_pages:
            return upright
        document = fitz.open(stream=upright, filetype="pdf")
        for _ in range(extra_pages):
            document.new_page(width=LETTER[0], height=LETTER[1])
        data = document.tobytes()
        document.close()
        return data
    source = fitz.open(stream=upright, filetype="pdf")
    document = fitz.open()
    if rotate in (90, 270):
        page = document.new_page(width=LETTER[1], height=LETTER[0])
    else:
        page = document.new_page(width=LETTER[0], height=LETTER[1])
    page.show_pdf_page(page.rect, source, 0, rotate=rotate)
    page.set_rotation(rotate)
    for _ in range(extra_pages):
        document.new_page(width=LETTER[0], height=LETTER[1])
    data = document.tobytes()
    document.close()
    source.close()
    return data


def _render(rows=_ROWS, *, rotate: int = 0, extra_pages: int = 0) -> bytes:
    return _rotated_copy(_render_upright(rows), rotate, extra_pages=extra_pages)


def _raw_words(pdf_bytes: bytes, page_index: int = 0) -> list[tuple]:
    """PyMuPDF's own `get_text("words")` items — boxes in UNROTATED space."""
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return [item for item in document[page_index].get_text("words") if str(item[4]).strip()]
    finally:
        document.close()


def _unrotated_size(pdf_bytes: bytes, page_index: int = 0) -> tuple[float, float]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[page_index]
        rect = page.rect * page.derotation_matrix
        return abs(rect.width), abs(rect.height)
    finally:
        document.close()


def _expected_display(rotation: int, box, unrotated_w: float, unrotated_h: float):
    """The INDEPENDENT formula (not PyMuPDF's matrix): a PDF `/Rotate` of R
    displays the page rotated R degrees CLOCKWISE. In top-left-origin, y-down
    coordinates, with the unrotated page W x H:
      90:  (x, y) -> (H - y, x)        display page H x W
      180: (x, y) -> (W - x, H - y)    display page W x H
      270: (x, y) -> (y, W - x)        display page H x W
    applied to the four corners, then the enclosing box."""
    x0, y0, x1, y1 = box
    if rotation == 0:
        return (x0, y0, x1, y1)
    if rotation == 90:
        return (unrotated_h - y1, x0, unrotated_h - y0, x1)
    if rotation == 180:
        return (unrotated_w - x1, unrotated_h - y1, unrotated_w - x0, unrotated_h - y0)
    if rotation == 270:
        return (y0, unrotated_w - x1, y1, unrotated_w - x0)
    raise AssertionError(rotation)


# ---------------------------------------------------------------------------
# unrotated pages: verbatim boxes (the byte-identity property)
# ---------------------------------------------------------------------------

def test_an_unrotated_page_keeps_pymupdf_boxes_verbatim():
    """The identity is applied as the identity: every `WordBox` coordinate on
    a `/Rotate 0` page is EXACTLY the float PyMuPDF returned, in the same
    order, with the same text — which is what makes the Phase 2.1 pin in
    `tests/test_geometry_frames.py` hold by construction."""
    pdf_bytes = _render()
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    raw = _raw_words(pdf_bytes)
    assert len(page.words) == len(raw) == 12
    for word, item in zip(page.words, raw):
        assert (word.x0, word.y0, word.x1, word.y1) == (float(item[0]), float(item[1]), float(item[2]), float(item[3]))
        assert word.text == str(item[4])
    assert page.frame.rotation_deg == 0
    assert page.notes == ()
    assert (page.frame.width, page.frame.height) == LETTER


# ---------------------------------------------------------------------------
# the four-angle pin (case 14)
# ---------------------------------------------------------------------------

#: Tolerance MEASURED while writing this pin (PyMuPDF 1.27.2.3, Poppler
#: 24.08.0): the maximum absolute per-coordinate delta between a rotated
#: page's display boxes and the `/Rotate 0` boxes was 0.0000305 pt at 90 and
#: 180 and 0.0000153 pt at 270 (the form XObject's matrix is written to the
#: content stream at single precision); the delta against the independent
#: formula applied to PyMuPDF's raw boxes was 0.0 at every angle. The
#: assertion bounds below are 1e-3 pt and 1e-6 pt respectively.
_CROSS_ANGLE_TOLERANCE_PT = 1e-3
_FORMULA_TOLERANCE_PT = 1e-6


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_four_angle_pin_boxes_land_at_the_expected_display_positions(rotation):
    """The same displayed page at `/Rotate` 0/90/180/270: the frame is the
    display rect (letter at every angle; the UNROTATED page is landscape at
    90/270, witnessed below), every word's display box equals the `/Rotate 0`
    box within the measured cross-angle tolerance AND equals the independent
    formula's prediction from PyMuPDF's raw unrotated box within 1e-6,
    every box lies inside the frame, the line texts and word count are the
    same at every angle, and a rotated page carries `rotation_applied`
    (never the retired Phase 2.1 note)."""
    upright = _render_upright()
    reference = native_evidence_from_pdf(upright)
    pdf_bytes = _rotated_copy(upright, rotation)
    rotated = native_evidence_from_pdf(pdf_bytes)
    assert reference is not None and rotated is not None
    page = rotated.pages[0]
    assert (page.frame.width, page.frame.height) == LETTER
    assert page.frame.rotation_deg == rotation
    assert page.frame.space == "pdf_point"
    assert page_text(page) == page_text(reference.pages[0])
    assert len(page.words) == len(reference.pages[0].words) == 12
    assert RETIRED_NOTE not in page.notes
    assert (ROTATION_APPLIED_NOTE in page.notes) is bool(rotation)
    assert WORD_OUTSIDE_FRAME_NOTE not in page.notes

    unrotated_w, unrotated_h = _unrotated_size(pdf_bytes)
    if rotation in (90, 270):
        assert (unrotated_w, unrotated_h) == (LETTER[1], LETTER[0])  # landscape underneath
    else:
        assert (unrotated_w, unrotated_h) == LETTER
    raw = _raw_words(pdf_bytes)
    assert [w.text for w in page.words] == [str(item[4]) for item in raw]
    max_cross = 0.0
    max_formula = 0.0
    for word, reference_word, item in zip(page.words, reference.pages[0].words, raw):
        actual = (word.x0, word.y0, word.x1, word.y1)
        expected_formula = _expected_display(rotation, tuple(float(v) for v in item[:4]), unrotated_w, unrotated_h)
        expected_cross = (reference_word.x0, reference_word.y0, reference_word.x1, reference_word.y1)
        max_formula = max(max_formula, max(abs(a - e) for a, e in zip(actual, expected_formula)))
        max_cross = max(max_cross, max(abs(a - e) for a, e in zip(actual, expected_cross)))
        assert 0.0 <= word.x0 < word.x1 <= page.frame.width
        assert 0.0 <= word.y0 < word.y1 <= page.frame.height
    assert max_formula <= _FORMULA_TOLERANCE_PT, max_formula
    assert max_cross <= _CROSS_ANGLE_TOLERANCE_PT, max_cross
    if rotation:
        # the witness that the transform DID something: PyMuPDF's raw boxes
        # are not where the words are displayed
        raw_first = tuple(float(v) for v in raw[0][:4])
        assert raw_first != (page.words[0].x0, page.words[0].y0, page.words[0].x1, page.words[0].y1)


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_four_angle_pin_agrees_with_popplers_display_orientation(rotation):
    """Independent of PyMuPDF: `pdf2image` (Poppler) renders the DISPLAY
    orientation. At 72 dpi one pixel is one point, so the rotated page's
    raster must have the frame's dimensions and be pixel-identical (as an
    ink mask) to the `/Rotate 0` raster, carry ink under EVERY transformed
    box (grown by one pixel for anti-aliasing), and carry ink under strictly
    FEWER of the untransformed Phase 2.1 boxes — the two frames disagree on
    where the words are, and Poppler sides with the transform."""
    from ocr.rasterize import rasterize_pdf

    upright = _render_upright()
    pdf_bytes = _rotated_copy(upright, rotation)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    image = rasterize_pdf(pdf_bytes, dpi=72)[0].convert("L")
    reference = rasterize_pdf(upright, dpi=72)[0].convert("L")
    assert (image.width, image.height) == (round(page.frame.width), round(page.frame.height))
    assert image.size == reference.size
    ink_mask_disagreements = sum(
        1 for a, b in zip(image.getdata(), reference.getdata()) if (a < 128) != (b < 128)
    )
    assert ink_mask_disagreements == 0

    def has_ink(box) -> bool:
        x0, y0, x1, y1 = box
        left, top = max(0, int(x0) - 1), max(0, int(y0) - 1)
        right, bottom = min(image.width, int(x1) + 2), min(image.height, int(y1) + 2)
        if right <= left or bottom <= top:
            return False
        return min(image.crop((left, top, right, bottom)).getdata()) < 128

    transformed_with_ink = sum(1 for w in page.words if has_ink((w.x0, w.y0, w.x1, w.y1)))
    assert transformed_with_ink == len(page.words) == 12
    untransformed_with_ink = sum(1 for item in _raw_words(pdf_bytes) if has_ink(tuple(float(v) for v in item[:4])))
    assert untransformed_with_ink < transformed_with_ink


# ---------------------------------------------------------------------------
# identity facts, round-trip, None cases (Phase 2.1 parity)
# ---------------------------------------------------------------------------

def test_identity_facts_runtime_and_sha():
    pdf_bytes = _render(rotate=270, extra_pages=1)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert isinstance(evidence, ExtractionEvidence)
    assert evidence.extractor_id == NATIVE_EXTRACTOR_ID == "native-pdf-words"
    assert evidence.model_token == NATIVE_EXTRACTOR_ID
    assert evidence.document_sha256 == hashlib.sha256(pdf_bytes).hexdigest().upper()
    assert dict(evidence.runtime) == {
        "pymupdf_version": str(getattr(fitz, "pymupdf_version", getattr(fitz, "__version__", "unknown"))),
        "frame": FRAME_DISPLAY,
    }
    assert FRAME_DISPLAY == "display"
    assert len(evidence.pages) == 2 and evidence.pages[1].words == ()
    for word in evidence.pages[0].words:
        assert word.confidence is None and word.line_ref is None
    assert [w.word_id for w in evidence.pages[0].words][:2] == ["p0.l-.w0", "p0.l-.w1"]
    assert evidence.pages[0].raw is None and evidence.pages[0].raw_sha256 is None
    assert len(evidence.evidence_sha256) == 64


def test_the_json_round_trip_reproduces_the_evidence_sha():
    evidence = native_evidence_from_pdf(_render(rotate=90))
    payload = json.loads(json.dumps(to_json(evidence), sort_keys=True))
    rebuilt = from_json(payload)
    assert rebuilt == evidence
    assert rebuilt.evidence_sha256 == evidence.evidence_sha256
    assert ROTATION_APPLIED_NOTE in rebuilt.pages[0].notes


def test_none_exactly_where_the_phase_2_1_reader_returned_none():
    for data in (b"not a pdf at all", b"%PDF-1.4\n garbage \n%%EOF", b""):
        assert native_evidence_from_pdf(data) is None
    blank = fitz.open()
    blank.new_page()
    assert native_evidence_from_pdf(blank.tobytes()) is None  # a page with no words at all


def test_the_reader_answers_none_when_pymupdf_is_unimportable():
    program = (
        "import sys\nsys.modules['fitz'] = None\n"
        "from evidence import native_evidence_from_pdf\n"
        "print(native_evidence_from_pdf(b'%PDF-1.4') is None)\n"
    )
    done = subprocess.run([sys.executable, "-c", program], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "True"


# ---------------------------------------------------------------------------
# the three page-level refusals, named separately
# ---------------------------------------------------------------------------

def _two_page_fixture(rotate: int = 0) -> bytes:
    pdf_bytes = _render(rotate=rotate, extra_pages=1)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    data = document.tobytes()
    document.close()
    return data


def _with_patched_get_text(patch):
    original = fitz.Page.get_text

    def wrapper(self, *args, **kwargs):
        return patch(self, original(self, *args, **kwargs))

    fitz.Page.get_text = wrapper
    return original


@pytest.mark.parametrize("rotate", [0, 90])
def test_a_word_outside_the_display_frame_refuses_the_page_with_its_real_frame(rotate):
    """Item 1: one PyMuPDF word whose box, once in the display frame, lies
    outside `[0, width] x [0, height]` refuses the WHOLE page (zero words,
    `native_word_outside_frame`, the page's REAL frame — never the
    unreadable placeholder, never a clamp, never just that word dropped);
    the sibling page is untouched. Exercised on an unrotated and a rotated
    page: the extra word is injected in PyMuPDF's unrotated space 30 pt past
    that space's bottom edge, which after a 90-degree transform is 30 pt
    past the RIGHT edge of the display frame."""
    pdf_bytes = _two_page_fixture(rotate)
    unrotated_w, unrotated_h = _unrotated_size(pdf_bytes)

    def add_far_word(page, words):
        if page.number == 0:
            return list(words) + [(72.0, unrotated_h + 30.0, 120.0, unrotated_h + 40.0, "OFFPAGE", 0, 0, 0)]
        return words

    original = _with_patched_get_text(add_far_word)
    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
    finally:
        fitz.Page.get_text = original
    assert evidence is not None
    first = evidence.pages[0]
    assert WORD_OUTSIDE_FRAME_NOTE in first.notes
    assert UNREADABLE_PAGE_NOTE not in first.notes and WORD_REFUSED_NOTE not in first.notes
    assert (ROTATION_APPLIED_NOTE in first.notes) is bool(rotate)
    assert first.words == ()
    assert (first.frame.width, first.frame.height) == LETTER  # the REAL display frame, not 1x1
    assert first.frame.rotation_deg == rotate
    assert evidence.pages[1].words and evidence.pages[1].notes == ()


def test_an_inverted_word_refuses_the_page_as_word_refused_not_outside_frame():
    pdf_bytes = _two_page_fixture()

    def corrupt(page, words):
        if page.number == 0 and words:
            first = list(words[0])
            first[3] = first[1]  # zero height
            return [tuple(first)] + list(words[1:])
        return words

    original = _with_patched_get_text(corrupt)
    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
    finally:
        fitz.Page.get_text = original
    assert WORD_REFUSED_NOTE in evidence.pages[0].notes
    assert WORD_OUTSIDE_FRAME_NOTE not in evidence.pages[0].notes
    assert evidence.pages[0].words == ()
    assert (evidence.pages[0].frame.width, evidence.pages[0].frame.height) == LETTER
    assert evidence.pages[1].words


def test_an_unreadable_page_keeps_the_placeholder_frame():
    pdf_bytes = _two_page_fixture()
    original = fitz.Page.get_text

    def exploding(self, *args, **kwargs):
        if self.number == 0:
            raise RuntimeError("simulated PyMuPDF failure")
        return original(self, *args, **kwargs)

    fitz.Page.get_text = exploding
    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
    finally:
        fitz.Page.get_text = original
    assert UNREADABLE_PAGE_NOTE in evidence.pages[0].notes
    assert (evidence.pages[0].frame.width, evidence.pages[0].frame.height) == (1.0, 1.0)
    assert evidence.pages[1].words


def test_the_retired_phase_2_1_note_is_never_emitted():
    for rotate in (0, 90, 180, 270):
        evidence = native_evidence_from_pdf(_render(rotate=rotate, extra_pages=1))
        for page in evidence.pages:
            assert RETIRED_NOTE not in page.notes


def test_a_mixed_document_rotated_and_unrotated_pages_each_get_their_own_frame():
    """Generalization: a two-page document whose first page is `/Rotate 270`
    (landscape underneath, pre-rotated content) and whose second is the
    plain upright page — each page converts by its own matrix; the rotated
    page is noted, the unrotated page is not, both display as letter, and
    both read the same words in the same lines at the same places."""
    upright = _render_upright()
    rotated = _rotated_copy(upright, 270)
    document = fitz.open(stream=rotated, filetype="pdf")
    document.insert_pdf(fitz.open(stream=upright, filetype="pdf"))
    pdf_bytes = document.tobytes()
    document.close()
    evidence = native_evidence_from_pdf(pdf_bytes)
    first, second = evidence.pages
    assert first.frame.rotation_deg == 270 and ROTATION_APPLIED_NOTE in first.notes
    assert second.frame.rotation_deg == 0 and second.notes == ()
    assert (first.frame.width, first.frame.height) == (second.frame.width, second.frame.height) == LETTER
    assert page_text(first) == page_text(second)
    assert len(first.words) == len(second.words) == 12
    for a, b in zip(first.words, second.words):
        assert (a.x0, a.y0, a.x1, a.y1) == pytest.approx((b.x0, b.y0, b.x1, b.y1), abs=_CROSS_ANGLE_TOLERANCE_PT)

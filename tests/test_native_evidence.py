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

from evidence.native import CLAMPED_TRANSFORM_NOTE, _display_matrix
from evidence import (
    FRAME_DISPLAY,
    INVALID_ROTATION_NOTE,
    NATIVE_EXTRACTOR_ID,
    OUTSIDE_FRAME_NOTE_PREFIX,
    ROTATION_APPLIED_NOTE,
    UNREADABLE_PAGE_NOTE,
    WORDS_OUTSIDE_FRAME_NOTE_PREFIX,
    WORD_OUTSIDE_FRAME_NOTE,
    WORD_REFUSED_NOTE,
    ExtractionEvidence,
    from_json,
    inside_frame,
    native_evidence_from_pdf,
    outside_frame_word_ids,
    page_text,
    to_json,
    words_outside_frame,
)

ROOT = Path(__file__).resolve().parents[1]
LETTER = (612.0, 792.0)
RETIRED_NOTE = "native_words_unrotated_space"
#: Both retired notes: Phase 2.1's unrotated-space note and the closure-retired
#: whole-page refusal for an out-of-frame word. Neither is ever emitted.
RETIRED_NOTES = (RETIRED_NOTE, WORD_OUTSIDE_FRAME_NOTE)

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
#: page's display boxes and the `/Rotate 0` boxes was 305e-7 pt at 90 and
#: 180 and 153e-7 pt at 270 (the form XObject's matrix is written to the
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
    assert not any(note in RETIRED_NOTES for note in page.notes)
    assert (ROTATION_APPLIED_NOTE in page.notes) is bool(rotation)
    assert words_outside_frame(page.notes) == 0 and outside_frame_word_ids(page.notes) == ()

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
        1 for a, b in zip(image.tobytes(), reference.tobytes()) if (a < 128) != (b < 128)
    )
    assert ink_mask_disagreements == 0

    def has_ink(box) -> bool:
        x0, y0, x1, y1 = box
        left, top = max(0, int(x0) - 1), max(0, int(y0) - 1)
        right, bottom = min(image.width, int(x1) + 2), min(image.height, int(y1) + 2)
        if right <= left or bottom <= top:
            return False
        return image.crop((left, top, right, bottom)).getextrema()[0] < 128

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
def test_a_word_outside_the_display_frame_is_kept_verbatim_and_noted(rotate):
    """The closure ruling (option c): a `pdf_point` frame is a viewport. One
    PyMuPDF word whose box, once in the display frame, lies outside
    `[0, width] x [0, height]` is KEPT — its transformed box verbatim, never
    clamped, never dropped — and the page records `outside_frame:<word_id>`
    for it plus `words_outside_frame=1`; every other word and the page's
    REAL frame are untouched; the sibling page carries no such note; the
    retired whole-page refusal never appears. Exercised on an unrotated and
    a rotated page: the extra word is injected in PyMuPDF's unrotated space
    30 pt past that space's bottom edge, which after a 90-degree transform
    is 30 pt past the LEFT edge of the display frame."""
    pdf_bytes = _two_page_fixture(rotate)
    unrotated_w, unrotated_h = _unrotated_size(pdf_bytes)
    clean = native_evidence_from_pdf(pdf_bytes)
    assert clean is not None and clean.pages[0].notes == ((ROTATION_APPLIED_NOTE,) if rotate else ())

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
    far = first.words[-1]
    assert far.text == "OFFPAGE"
    assert not inside_frame(first.frame, far.x0, far.y0, far.x1, far.y1)
    if rotate == 90:
        # in unrotated space the word sits 30 pt BELOW the landscape page's
        # bottom edge; the 90-degree display rotation maps that edge to the
        # display's LEFT edge, so the box lands 30 pt past x = 0 — kept as-is
        assert far.x1 <= -30.0
    else:
        assert far.y0 >= LETTER[1] + 30.0  # past the BOTTOM edge
    assert first.words[:-1] == clean.pages[0].words  # every other word verbatim
    assert first.notes == ((ROTATION_APPLIED_NOTE,) if rotate else ()) + (
        OUTSIDE_FRAME_NOTE_PREFIX + far.word_id, WORDS_OUTSIDE_FRAME_NOTE_PREFIX + "1",
    )
    assert outside_frame_word_ids(first.notes) == (far.word_id,)
    assert words_outside_frame(first.notes) == 1
    assert not any(note in RETIRED_NOTES for note in first.notes)
    assert UNREADABLE_PAGE_NOTE not in first.notes and WORD_REFUSED_NOTE not in first.notes
    assert (first.frame.width, first.frame.height) == LETTER  # the REAL display frame, not 1x1
    assert first.frame.rotation_deg == rotate
    assert evidence.pages[1].words and evidence.pages[1].notes == ()
    assert outside_frame_word_ids(evidence.pages[1].notes) == () and words_outside_frame(evidence.pages[1].notes) == 0
    # the notes survive the JSON round-trip with the sha
    rebuilt = from_json(to_json(evidence))
    assert rebuilt.pages[0].notes == first.notes and rebuilt.evidence_sha256 == evidence.evidence_sha256


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
    assert not any(note in RETIRED_NOTES for note in evidence.pages[0].notes)
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


def test_the_retired_notes_are_never_emitted():
    """Both retired notes — Phase 2.1's `native_words_unrotated_space` and
    the closure-retired `native_word_outside_frame` — are never emitted, on
    clean pages and on a page carrying an out-of-frame word alike."""
    for rotate in (0, 90, 180, 270):
        evidence = native_evidence_from_pdf(_render(rotate=rotate, extra_pages=1))
        for page in evidence.pages:
            assert not any(note in RETIRED_NOTES for note in page.notes)
    pdf_bytes = _two_page_fixture()
    _, height = _unrotated_size(pdf_bytes)
    original = _with_patched_get_text(
        lambda page, words: list(words) + [(72.0, height + 30.0, 120.0, height + 40.0, "OFFPAGE", 0, 0, 0)]
        if page.number == 0 else words
    )
    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
    finally:
        fitz.Page.get_text = original
    assert words_outside_frame(evidence.pages[0].notes) == 1
    assert not any(note in RETIRED_NOTES for note in evidence.pages[0].notes)


# ---------------------------------------------------------------------------
# closure-2 (review F-1): the raster renders the CropBox — one rectangle for
# the native display frame and the Paddle-style pixel frame
# ---------------------------------------------------------------------------

_CROPBOX = (15.0, 25.0, 560.0, 700.0)  # shifted AND smaller than the letter MediaBox


def _cropped(rotate: int = 0) -> bytes:
    """The upright ledger on a letter MediaBox with a CropBox shifted from it
    (the reviewer's S3 shape); optionally with a `/Rotate`."""
    document = fitz.open(stream=_render_upright(), filetype="pdf")
    page = document[0]
    page.set_cropbox(fitz.Rect(*_CROPBOX))
    if rotate:
        page.set_rotation(rotate)
    data = document.tobytes()
    document.close()
    return data


def _ink_fraction(image, words, scale_x: float, scale_y: float) -> float:
    """The reviewer's overlay measure: the fraction of word boxes (grown one
    pixel) that contain ink in the raster, at the raster's own scale."""
    gray = image.convert("L")
    hits = 0
    for word in words:
        left = max(0, int(word.x0 * scale_x) - 1)
        top = max(0, int(word.y0 * scale_y) - 1)
        right = min(gray.width, int(word.x1 * scale_x) + 2)
        bottom = min(gray.height, int(word.y1 * scale_y) + 2)
        if right > left and bottom > top and gray.crop((left, top, right, bottom)).getextrema()[0] < 128:
            hits += 1
    return hits / max(1, len(words))


@pytest.mark.parametrize("rotate", [0, 90])
@pytest.mark.parametrize("dpi", [72, 144])
def test_the_raster_renders_the_cropbox_so_frame_and_raster_share_one_rectangle(rotate, dpi):
    """Review F-1: on a page whose CropBox is shifted from (and smaller than)
    its MediaBox, the native display frame is `page.rect` (the CropBox) while
    Poppler's default raster was the MediaBox — boxes offset from the ink by
    the CropBox origin, frame size disagreeing with the raster. With
    `use_cropbox=True` (RASTER_VERSION 2): the raster's pixel size equals the
    frame × dpi/72 (rounded), a `PageFrame.pixel` built from the raster and
    the native frame passes the scale check, and the overlay measure — the
    fraction of word boxes containing ink — is 1.0, which is ≥ the unrotated
    plain-page baseline (also 1.0). A MediaBox raster (mutant M18) fails the
    size equality and the scale check."""
    from ocr.rasterize import rasterize_pdf
    from evidence import PageFrame

    baseline_pdf = _render_upright()
    baseline = native_evidence_from_pdf(baseline_pdf)
    baseline_image = rasterize_pdf(baseline_pdf, dpi=dpi)[0]
    baseline_fraction = _ink_fraction(baseline_image, baseline.pages[0].words, dpi / 72.0, dpi / 72.0)
    assert baseline_fraction == 1.0

    pdf_bytes = _cropped(rotate)
    evidence = native_evidence_from_pdf(pdf_bytes)
    page = evidence.pages[0]
    width_pt, height_pt = _CROPBOX[2] - _CROPBOX[0], _CROPBOX[3] - _CROPBOX[1]
    if rotate == 90:
        width_pt, height_pt = height_pt, width_pt
    assert (page.frame.width, page.frame.height) == (width_pt, height_pt)
    assert page.frame.rotation_deg == rotate

    image = rasterize_pdf(pdf_bytes, dpi=dpi)[0]
    assert (image.width, image.height) == (round(width_pt * dpi / 72.0), round(height_pt * dpi / 72.0))
    pixel_frame = PageFrame.pixel(  # the Paddle rung's own frame construction: refuses on a scale mismatch
        page_index=0, raster_width_px=image.width, raster_height_px=image.height, dpi=float(dpi),
        pdf_width_pt=page.frame.width, pdf_height_pt=page.frame.height, rotation_deg=rotate,
    )
    fraction = _ink_fraction(image, page.words, pixel_frame.scale_x, pixel_frame.scale_y)
    assert fraction == 1.0 and fraction >= baseline_fraction
    assert len(page.words) == 12 and words_outside_frame(page.notes) == 0


# ---------------------------------------------------------------------------
# closure-2 (review F-2): an invalid page-level /Rotate is refused by name
# ---------------------------------------------------------------------------

def _with_raw_rotate(rotate: int, *, inherited: bool = False, extra_pages: int = 1) -> bytes:
    """The upright ledger with a RAW `/Rotate` value written into the page
    object (or, `inherited=True`, into the parent `Pages` node with the page's
    own key removed) — values PyMuPDF normalises before `page.rotation`."""
    document = fitz.open(stream=_render(extra_pages=extra_pages), filetype="pdf")
    page = document[0]
    if extra_pages:
        # the sibling page carries a word, so a refused first page never
        # empties the whole document into the reader's honest `None`
        document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    if inherited:
        kind, value = document.xref_get_key(page.xref, "Parent")
        parent_xref = int(value.split()[0])
        document.xref_set_key(page.xref, "Rotate", "null")
        document.xref_set_key(parent_xref, "Rotate", str(rotate))
    else:
        document.xref_set_key(page.xref, "Rotate", str(rotate))
    data = document.tobytes()
    document.close()
    return data


@pytest.mark.parametrize("inherited", [False, True])
def test_an_invalid_page_rotate_refuses_the_page_by_name(inherited):
    """Review F-2: a raw `/Rotate 45` (not a multiple of 90) makes PyMuPDF
    report rotation 0 with an identity matrix but a swapped rect and rotated
    word coordinates — boxes that would miss the ink of the page a viewer
    shows. The reader refuses the page whole (`invalid_rotation`, zero words,
    the declared rect), whether the value sits on the page or is inherited
    from the parent `Pages` node; the sibling page is untouched; the document
    is not aborted. The archive carries 0 such pages (the closure-2 census)."""
    pdf_bytes = _with_raw_rotate(45, inherited=inherited)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    first = evidence.pages[0]
    assert first.notes == (INVALID_ROTATION_NOTE,)
    assert first.words == ()
    assert first.frame.width > 1.0 and first.frame.height > 1.0  # the declared rect, not the placeholder
    assert UNREADABLE_PAGE_NOTE not in first.notes and WORD_REFUSED_NOTE not in first.notes
    assert evidence.pages[1].notes == ()


@pytest.mark.parametrize("raw,normalised", [(450, 90), (-90, 270), (360, 0), (0, 0)])
def test_a_raw_rotate_that_is_a_multiple_of_90_is_normalised_not_refused(raw, normalised):
    """The reviewer's S5 shapes: odd but VALID `/Rotate` values normalise to
    the display rotation and read every word; nothing is refused."""
    pdf_bytes = _with_raw_rotate(raw, extra_pages=0)
    evidence = native_evidence_from_pdf(pdf_bytes)
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == normalised
    assert len(page.words) == 12


# ---------------------------------------------------------------------------
# Phase 2.3 cell X (P23-AGREE item 4): the two latent defects the closure-2
# re-review named. Both had population 0 in the archive and both are reachable
# by a real PDF, so both are closed here and pinned by a synthetic page.
# ---------------------------------------------------------------------------

#: A CropBox that OVERHANGS the letter MediaBox on every side — the N-1
#: shape. PyMuPDF clamps `page.rect` and the word coordinates to the
#: MediaBox (so does Poppler) but builds `rotation_matrix`'s translation from
#: THIS rectangle, so a rotated page's boxes were offset by the overhang.
_OVERHANG = (-40.0, -38.0, 652.0, 830.0)


def _overhanging_cropbox(rotate: int = 0) -> bytes:
    """The upright ledger whose CropBox is written directly into the page
    object so it can exceed the MediaBox (`set_cropbox` will not do it), with
    an optional `/Rotate`."""
    document = fitz.open(stream=_render_upright(), filetype="pdf")
    page = document[0]
    document.xref_set_key(page.xref, "CropBox",
                          "[ %g %g %g %g ]" % _OVERHANG)
    if rotate:
        document.xref_set_key(page.xref, "Rotate", str(rotate))
    data = document.tobytes()
    document.close()
    return data


def _matrix_translation(pdf_bytes: bytes) -> tuple[float, float]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        matrix = document[0].rotation_matrix
        return float(matrix.e), float(matrix.f)
    finally:
        document.close()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_an_overhanging_cropbox_on_a_rotated_page_lands_on_the_rasters_ink(rotation):
    """Re-review N-1. The page's CropBox extends past its MediaBox on every
    side. PyMuPDF clamps `page.rect` to the MediaBox — and Poppler renders
    exactly that rectangle — but its `rotation_matrix` translates by the
    UNCLAMPED CropBox, so at 90/180/270 every word box the Phase 2.2 reader
    emitted was offset by the overhang and contained no ink at all. The
    transform is now derived from `page.rect`: the frame is the clamped
    rectangle, every box carries ink in the 72-dpi raster, the boxes equal
    the `/Rotate 0` boxes within the measured cross-angle tolerance, and the
    page says so with `clamped_display_transform`. The 0-degree page is
    untouched (its matrix and the rect already agreed) and carries no note.

    Mutant M8 — the transform built from PyMuPDF's matrix regardless — is
    killed by the ink assertion at all three rotated angles.
    """
    from ocr.rasterize import rasterize_pdf

    pdf_bytes = _overhanging_cropbox(rotation)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    expected = LETTER if rotation in (0, 180) else (LETTER[1], LETTER[0])
    assert (page.frame.width, page.frame.height) == expected
    assert page.frame.rotation_deg == rotation
    assert len(page.words) == 12
    assert words_outside_frame(page.notes) == 0

    # the defect is really present in PyMuPDF at this shape (the pin is not
    # measuring a page that never had the problem): its matrix translates by
    # the UNCLAMPED CropBox's sides, the derived one by the display rect's
    overhang_w = _OVERHANG[2] - _OVERHANG[0]
    overhang_h = _OVERHANG[3] - _OVERHANG[1]
    translation = _matrix_translation(pdf_bytes)
    if rotation:
        assert translation == {
            90: (overhang_h, 0.0), 180: (overhang_w, overhang_h), 270: (0.0, overhang_w),
        }[rotation]
        assert translation != _display_matrix(rotation, *expected)[4:]
        assert CLAMPED_TRANSFORM_NOTE in page.notes
    else:
        assert translation == (0.0, 0.0)
        assert CLAMPED_TRANSFORM_NOTE not in page.notes

    image = rasterize_pdf(pdf_bytes, dpi=72)[0]
    assert image.size == (round(page.frame.width), round(page.frame.height))
    assert _ink_fraction(image, page.words, 1.0, 1.0) == 1.0

    reference = native_evidence_from_pdf(_overhanging_cropbox(0))
    for word, other in zip(page.words, reference.pages[0].words):
        expected_box = _expected_display(rotation, (other.x0, other.y0, other.x1, other.y1), *LETTER)
        assert (word.x0, word.y0, word.x1, word.y1) == pytest.approx(
            expected_box, abs=_CROSS_ANGLE_TOLERANCE_PT)


def test_a_cropbox_inside_the_mediabox_still_uses_pymupdfs_own_matrix():
    """The other side of N-1's fix: on every ordinary page — and on the
    closure-2 CropBox shape, which sits INSIDE the MediaBox — PyMuPDF's
    matrix and the rectangle-derived one agree, the reader keeps PyMuPDF's,
    and no page carries the note. That is what makes the fix free of
    evidence-byte movement on the archive."""
    for rotation in (0, 90, 180, 270):
        for pdf_bytes in (_render(rotate=rotation), _cropped(rotation) if rotation in (0, 90) else None):
            if pdf_bytes is None:
                continue
            evidence = native_evidence_from_pdf(pdf_bytes)
            assert evidence is not None
            for page in evidence.pages:
                assert CLAMPED_TRANSFORM_NOTE not in page.notes


def _with_indirect_rotate(value, *, extra_pages: int = 1) -> bytes:
    """The upright ledger whose `/Rotate` is an INDIRECT reference to an
    object holding `value` (written as its literal source) — the N-2 shape."""
    document = fitz.open(stream=_render(extra_pages=extra_pages), filetype="pdf")
    page = document[0]
    if extra_pages:
        document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    xref = document.get_new_xref()
    document.update_object(xref, str(value))
    document.xref_set_key(page.xref, "Rotate", f"{xref} 0 R")
    data = document.tobytes()
    document.close()
    return data


@pytest.mark.parametrize("value", [45, 225, 46, 89, 91])
def test_an_indirect_invalid_rotate_is_resolved_and_refused_by_name(value):
    """Re-review N-2. A `/Rotate` written as `12 0 R` reads back with kind
    `xref`, which the Phase 2.2 reader treated as "no value": an indirect 45
    escaped the invalid-rotation refusal and was mis-framed exactly as a
    direct 45 had been — PyMuPDF reports rotation 0 with an identity matrix
    but a SWAPPED rect, so every box missed the page a viewer shows. The
    reference is now resolved before the mod-90 test and the page is refused
    by name. Mutant M9 — the `xref` kind treated as absent — is killed here.

    The values are the ones whose harm is OBSERVABLE (closure, MAJOR-1):
    PyMuPDF rounds an invalid rotation to the nearest multiple of 90, and for
    this family it rounds to 90 or 270, which shows as a TRANSPOSED
    `page.rect` while `page.rotation` reads 0 — measured, with Poppler
    rasterising the UNSWAPPED page and no display transform at any of the four
    angles putting ink under a single box. That is the mis-framing, and it is
    what the refusal is for.
    """
    pdf_bytes = _with_indirect_rotate(value)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[0]
        assert document.xref_get_key(page.xref, "Rotate")[0] == "xref"
        assert page.rotation == 0          # PyMuPDF normalised it away
        assert (page.rect.width, page.rect.height) == (LETTER[1], LETTER[0])   # ... but swapped the rect
    finally:
        document.close()
    from ocr.rasterize import rasterize_pdf
    assert rasterize_pdf(pdf_bytes, dpi=72)[0].size == (round(LETTER[0]), round(LETTER[1]))

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    first = evidence.pages[0]
    assert first.notes == (INVALID_ROTATION_NOTE,)
    assert first.words == ()
    assert evidence.pages[1].words and evidence.pages[1].notes == ()


@pytest.mark.parametrize("value", [-45, 315])
def test_an_indirect_rotate_pymupdf_rounds_to_zero_reads_every_word(value):
    """The other half of the same measurement, and the reason the indirect
    refusal is tied to the observable harm rather than to the mod-90
    arithmetic alone: PyMuPDF rounds these to 0, the rect is NOT swapped,
    Poppler renders the same rectangle and every word box carries ink. The
    page is fine; refusing it would lose a document for a number that changed
    nothing."""
    pdf_bytes = _with_indirect_rotate(value, extra_pages=0)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == 0
    assert len(page.words) == 12
    assert _poppler_ink(pdf_bytes, page) == 1.0


@pytest.mark.parametrize("value", [135])
def test_an_indirect_rotate_pymupdf_rounds_to_180_is_a_RECORDED_RESIDUAL(value):
    """A measured, named latent — pinned so it cannot drift silently.

    PyMuPDF rounds this family to 180: `page.rotation` reads 0 and the rect is
    NOT swapped, so the mis-framing leaves no geometric signature, yet the
    word coordinates are in the 180-rotated space and miss the raster's ink.
    The indirect path therefore does NOT refuse it, and this test records
    exactly that, with the harm measured.

    It is not a regression: the Phase 2.2 reader did the same (it resolved no
    indirect reference at all), the archive population is 0 (the corpus census
    finds four indirect `/Rotate` objects, every one resolving to 0), and the
    alternative — refusing on any resolved non-multiple of 90 — refuses a
    page whenever the reference is a CHAIN whose intermediate object number
    happens to land in this family, which is the regression MAJOR-1 was.
    Object numbers are small integers; rotations are not. Carried for the
    milestone that owns the reader.
    """
    pdf_bytes = _with_indirect_rotate(value, extra_pages=0)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[0]
        assert page.rotation == 0
        assert (page.rect.width, page.rect.height) == LETTER      # NOT swapped: no signature
    finally:
        document.close()
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes                # recorded: not refused
    assert len(page.words) == 12
    assert _poppler_ink(pdf_bytes, page) == 0.0                   # recorded: the boxes miss the ink


@pytest.mark.parametrize("value,normalised", [(90, 90), (270, 270), (0, 0), (-90, 270), (360, 0)])
def test_an_indirect_valid_rotate_is_resolved_and_read(value, normalised):
    """The archive's own shape: its four non-integer `/Rotate` objects are
    indirect references resolving to 0 (the re-reviewer's census). A resolved
    multiple of 90 normalises and every word is read — resolving the
    reference must not turn a good page into a refusal."""
    pdf_bytes = _with_indirect_rotate(value, extra_pages=0)
    evidence = native_evidence_from_pdf(pdf_bytes)
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == normalised
    assert len(page.words) == 12


def test_an_indirect_rotate_written_as_a_real_is_coerced_by_the_writer_and_refused():
    """The re-reviewer's own observation, now on the indirect path: a PDF
    writer coerces `45.0` to the integer 45, so the resolved value is an
    integer and the page is refused like any other invalid rotation. The
    reader does no coercion of its own."""
    document = fitz.open(stream=_render(extra_pages=1), filetype="pdf")
    document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    xref = document.get_new_xref()
    document.update_object(xref, "45.0")
    document.xref_set_key(document[0].xref, "Rotate", f"{xref} 0 R")
    pdf_bytes = document.tobytes()
    document.close()
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    assert evidence.pages[0].notes == (INVALID_ROTATION_NOTE,)
    assert evidence.pages[1].words


@pytest.mark.parametrize("source", ["/Ninety", "(45)", "<</A 1>>"])
def test_an_indirect_rotate_that_is_not_an_integer_is_no_value_not_a_guess(source):
    """A resolved object this reader cannot read as an integer is the same
    fact as an absent key: no raw value, so the page follows PyMuPDF's own
    normalised rotation — exactly what it did before N-2 was closed. The
    reader never guesses an angle out of a non-integer."""
    document = fitz.open(stream=_render(extra_pages=0), filetype="pdf")
    xref = document.get_new_xref()
    document.update_object(xref, source)
    document.xref_set_key(document[0].xref, "Rotate", f"{xref} 0 R")
    pdf_bytes = document.tobytes()
    document.close()
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    assert INVALID_ROTATION_NOTE not in evidence.pages[0].notes
    assert len(evidence.pages[0].words) == 12


def _with_objects(bodies, *, inherited: bool = False, extra_pages: int = 1) -> bytes:
    """The upright ledger plus real PDF objects: `bodies[i]` is written into
    the i-th newly allocated xref (`{0}`, `{1}` ... interpolate the allocated
    numbers, so a body can be a reference to a sibling), and the page's — or
    the parent `Pages` node's — `/Rotate` is set to a reference to the FIRST
    of them. Real objects in a real document; no stub anywhere."""
    document = fitz.open(stream=_render(extra_pages=extra_pages), filetype="pdf")
    if extra_pages:
        document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    xrefs = [document.get_new_xref() for _ in bodies]
    for xref, body in zip(xrefs, bodies):
        document.update_object(xref, body.format(*xrefs))
    page = document[0]
    if inherited:
        _, value = document.xref_get_key(page.xref, "Parent")
        parent = int(str(value).split()[0])
        document.xref_set_key(page.xref, "Rotate", "null")
        document.xref_set_key(parent, "Rotate", f"{xrefs[0]} 0 R")
    else:
        document.xref_set_key(page.xref, "Rotate", f"{xrefs[0]} 0 R")
    data = document.tobytes()
    document.close()
    return data


def _poppler_ink(pdf_bytes: bytes, page: "object") -> float:
    """The fraction of the page's word boxes that contain ink in Poppler's own
    72-dpi raster — the independent renderer, the same oracle the four-angle
    pin uses."""
    from ocr.rasterize import rasterize_pdf

    image = rasterize_pdf(pdf_bytes, dpi=72)[0]
    assert image.size == (round(page.frame.width), round(page.frame.height)), (
        "the reader's frame and Poppler's raster describe different rectangles"
    )
    return _ink_fraction(image, page.words, 1.0, 1.0)


@pytest.mark.parametrize("terminal", ["270", "90", "0", "45", "13"])
def test_an_indirect_rotate_resolving_to_an_xref_number_is_the_page_every_renderer_shows(terminal):
    """Re-review closure, MAJOR-1 — on REAL PDFs, with Poppler as the oracle,
    and named for what the BYTES contain rather than for what was built.

    `_with_objects(["{1} 0 R", terminal])` asks for `/Rotate` -> A -> B ->
    `terminal`, but PyMuPDF's writer FLATTENS a reference-bodied object:
    dumped out of the finished file, object A reads `A 0 obj\\n B \\nendobj`.
    So what every reader of this file sees is a SINGLE indirect `/Rotate`
    resolving to the integer B — an xref NUMBER, not an angle, and not the
    terminal. The terminal is parametrised to show it makes no difference,
    which is itself the evidence for the flattening. (The genuine
    reference-to-reference, built by byte surgery, is pinned below.)

    B is 18 here — not a multiple of 90 — so PyMuPDF normalises it away:
    rotation 0, an UNSWAPPED rect, Poppler rasterising the same rectangle,
    every word on the ink at 0 degrees. This is exactly the shape the first
    implementation lost the whole document's native reading on: it returned
    18 as an angle and refused the page.
    """
    pdf_bytes = _with_objects(["{1} 0 R", terminal])
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        kind, value = document.xref_get_key(document[0].xref, "Rotate")
        assert kind == "xref"
        a = int(str(value).split()[0])
        # THE FLATTENING, pinned in the bytes: object A was written as the
        # reference `B 0 R` and the file holds the bare integer B
        assert f"{a} 0 obj\n{a + 1}\nendobj".encode() in pdf_bytes
        assert str(document.xref_object(a)).strip() == str(a + 1) != terminal
        assert int(document[0].rotation) == 0
        assert (document[0].rect.width, document[0].rect.height) == LETTER
    finally:
        document.close()

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None, "the document's native reading was lost"
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == 0
    assert (page.frame.width, page.frame.height) == LETTER
    assert len(page.words) == 12
    assert _poppler_ink(pdf_bytes, page) == 1.0
    assert evidence.pages[1].words


@pytest.mark.parametrize("terminal", ["45", "13"])
def test_an_indirect_rotate_resolving_to_an_xref_number_is_read_through_the_parent_walk_too(terminal):
    """The same flattened shape, reached through the `/Parent` walk."""
    pdf_bytes = _with_objects(["{1} 0 R", terminal], inherited=True)
    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert len(page.words) == 12
    assert _poppler_ink(pdf_bytes, page) == 1.0


@pytest.mark.parametrize("value,normalised", [(90, 90), (270, 270), (180, 180), (0, 0)])
def test_an_inherited_indirect_rotate_through_the_pages_node_is_resolved_and_read(value, normalised):
    """The fifth shape of the closure ruling: a SINGLE-hop indirect `/Rotate`
    that the page does not carry itself but inherits from its parent `/Pages`
    node — the legal PDF spelling, and the one this reader's `/Parent` walk
    exists for.

    MEASURED on a real PDF: PyMuPDF resolves the inherited reference itself
    (`page.rotation` reads the angle, the rect swaps at 90 and 270), the
    reader's walk resolves the same object, the two corroborate, and every
    word lands on Poppler's ink in the display frame."""
    pdf_bytes = _with_objects([str(value)], inherited=True, extra_pages=0)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[0]
        # the key is not on the page: it is reached through `/Parent`
        assert document.xref_get_key(page.xref, "Rotate")[0] in ("null", "")
        _, parent = document.xref_get_key(page.xref, "Parent")
        assert document.xref_get_key(int(str(parent).split()[0]), "Rotate")[0] == "xref"
        assert int(page.rotation) == normalised
    finally:
        document.close()

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == normalised
    assert len(page.words) == 12
    assert _poppler_ink(pdf_bytes, page) == 1.0


@pytest.mark.parametrize("value", [45, 225])
def test_an_inherited_indirect_invalid_rotate_through_the_pages_node_is_refused_by_name(value):
    """The refusal on the same inherited path, and the harm it is for.

    MEASURED: PyMuPDF normalises the inherited 45 away (`page.rotation` 0) and
    still swaps the declared rect to 792 x 612, while Poppler rasterises the
    UNSWAPPED 612 x 792 page — the mis-framing signature exactly, so the page
    is refused by name, whole, with the sibling page untouched. An inherited
    reference must not be a hole in the refusal the direct value gets."""
    from ocr.rasterize import rasterize_pdf

    pdf_bytes = _with_objects([str(value)], inherited=True)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[0]
        assert int(page.rotation) == 0
        assert (page.rect.width, page.rect.height) == (LETTER[1], LETTER[0])
    finally:
        document.close()
    assert rasterize_pdf(pdf_bytes, dpi=72)[0].size == (round(LETTER[0]), round(LETTER[1]))

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    first = evidence.pages[0]
    assert first.notes == (INVALID_ROTATION_NOTE,)
    assert first.words == ()
    assert evidence.pages[1].words and evidence.pages[1].notes == ()


def test_the_resolver_makes_one_call_so_no_reference_shape_can_spin():
    """A three-object request, a self-referencing object and a two-object
    cycle: each is written out flattened (see the pin above), each resolves to
    an xref number the page does not corroborate, each is read as the
    unrotated page every renderer shows — and none of them can loop, because
    the resolver makes exactly ONE `xref_object` call and there is no walk to
    bound."""
    for bodies in (["{1} 0 R", "{2} 0 R", "270"], ["{0} 0 R"], ["{1} 0 R", "{0} 0 R"]):
        pdf_bytes = _with_objects(bodies)
        evidence = native_evidence_from_pdf(pdf_bytes)
        assert evidence is not None, bodies
        assert len(evidence.pages[0].words) == 12, bodies
        assert _poppler_ink(pdf_bytes, evidence.pages[0]) == 1.0, bodies


def _with_genuine_chained_rotate(terminal: str, *, extra_pages: int = 0) -> tuple[bytes, int, int]:
    """The upright ledger whose `/Rotate` really is a reference to a reference
    — the shape `Document.tobytes()` flattens away, so it is put back by
    LENGTH-PRESERVING byte surgery: object A is written as an integer of
    exactly the same width as `B 0 R` and that run of bytes is replaced in the
    finished file, leaving every xref offset intact. Returns `(bytes, A, B)`.
    Every step is asserted, so a PyMuPDF that stopped flattening — or wrote
    the placeholder differently — fails here loudly instead of silently
    turning these pins into the other shape."""
    document = fitz.open(stream=_render(extra_pages=extra_pages), filetype="pdf")
    if extra_pages:
        document[1].insert_text(fitz.Point(40.0, 100.0), "SecondPageWord", fontsize=10.0, fontname="helv")
    b, a = document.get_new_xref(), document.get_new_xref()
    reference = f"{b} 0 R"
    placeholder = "9" * len(reference)
    document.update_object(b, terminal)
    document.update_object(a, placeholder)
    document.xref_set_key(document[0].xref, "Rotate", f"{a} 0 R")
    data = document.tobytes()
    document.close()
    assert data.count(placeholder.encode()) == 1
    assert f"{a} 0 obj\n{placeholder}\nendobj".encode() in data     # the writer wrote it verbatim
    patched = data.replace(placeholder.encode(), reference.encode())
    assert len(patched) == len(data)                                # every offset still stands
    assert f"{a} 0 obj\n{reference}\nendobj".encode() in patched    # a genuine reference body
    return patched, a, b


@pytest.mark.parametrize("terminal,rotation,words", [("0", 0, 12), ("13", 0, 12)])
def test_a_genuine_reference_chain_is_resolved_by_the_library_in_the_readers_one_call(
        terminal, rotation, words):
    """Closure of the closure, MAJOR-1: what a REAL reference-to-reference
    does, measured in the bytes rather than inferred from a writer that
    cannot produce one.

    `xref_object(A)` returns the TERMINAL's value — `'0'`, `'13'` — not `B`
    and not the text `B 0 R`: PyMuPDF resolves the chain itself, so the
    reader's single call is the whole walk and a bounded loop over
    `xref_object` would only ever re-read values the library had already
    followed. `page.rotation` agrees, Poppler rasterises the same rectangle,
    and every word lands on its ink."""
    pdf_bytes, a, _ = _with_genuine_chained_rotate(terminal)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        assert document.xref_get_key(document[0].xref, "Rotate")[0] == "xref"
        assert str(document.xref_object(a)).strip() == terminal     # resolved, in one call
        assert int(document[0].rotation) == rotation
    finally:
        document.close()

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == rotation
    assert len(page.words) == words
    assert _poppler_ink(pdf_bytes, page) == 1.0


def test_a_genuine_reference_chain_to_an_invalid_rotation_is_refused_by_name():
    """The same genuine shape carrying 45. PyMuPDF resolves the chain,
    normalises the angle away (`page.rotation` 0) and STILL swaps the declared
    rect to 792 x 612, while Poppler renders the unswapped 612 x 792 page —
    the mis-framing signature exactly, so the page is refused by name with the
    sibling page untouched. The Phase 2.2 reader read this page and put every
    box in a space no renderer shows."""
    from ocr.rasterize import rasterize_pdf

    pdf_bytes, a, _ = _with_genuine_chained_rotate("45", extra_pages=1)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        assert str(document.xref_object(a)).strip() == "45"
        assert int(document[0].rotation) == 0
        assert (document[0].rect.width, document[0].rect.height) == (LETTER[1], LETTER[0])
    finally:
        document.close()
    assert rasterize_pdf(pdf_bytes, dpi=72)[0].size == (round(LETTER[0]), round(LETTER[1]))

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    assert evidence.pages[0].notes == (INVALID_ROTATION_NOTE,)
    assert evidence.pages[0].words == ()
    assert evidence.pages[1].words and evidence.pages[1].notes == ()


@pytest.mark.parametrize("terminal", ["270", "90"])
def test_a_genuine_reference_chain_the_two_renderers_disagree_about_is_a_RECORDED_RESIDUAL(terminal):
    """A measured, named latent, pinned so it cannot drift silently.

    On a GENUINE reference-to-reference the two renderers part company:
    PyMuPDF resolves the chain and honours it (`page.rotation` 270, the rect
    swapped), while Poppler resolves one level, finds a reference where an
    integer belongs, and renders the page UNROTATED. There is no signature to
    branch on — the library's rotation and the resolved value agree — and
    nothing this reader can see says which renderer the document's author
    meant. It follows PyMuPDF, exactly as the Phase 2.2 reader did, so this
    is not a regression; the archive population is 0 (the census finds four
    indirect `/Rotate` objects, trail length 1, every one resolving to 0).
    Carried, with its harm measured, for the milestone that owns the reader."""
    from ocr.rasterize import rasterize_pdf

    pdf_bytes, a, _ = _with_genuine_chained_rotate(terminal)
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        assert str(document.xref_object(a)).strip() == terminal
        assert int(document[0].rotation) == int(terminal)                   # PyMuPDF honours it
        assert (document[0].rect.width, document[0].rect.height) == (LETTER[1], LETTER[0])
    finally:
        document.close()
    # ... and Poppler does not
    assert rasterize_pdf(pdf_bytes, dpi=72)[0].size == (round(LETTER[0]), round(LETTER[1]))

    evidence = native_evidence_from_pdf(pdf_bytes)
    assert evidence is not None
    page = evidence.pages[0]
    assert INVALID_ROTATION_NOTE not in page.notes
    assert page.frame.rotation_deg == int(terminal)                         # the reader follows PyMuPDF
    assert len(page.words) == 12


def test_an_indirect_rotate_the_page_does_not_corroborate_is_no_value():
    """The corroboration rule, both ways, on real PDFs.

    A resolved multiple of 90 is acted on ONLY when PyMuPDF resolved the
    reference the same way (`page.rotation` agrees); a resolved non-multiple
    ONLY when the mis-framing signature is actually present. Here the page's
    `/Rotate` is a DIRECT 0 while a stray object holds 90: nothing refers to
    it, nothing is corroborated, and the page reads unrotated."""
    from evidence.native import _indirect_rotate

    pdf_bytes = _with_objects(["{1} 0 R", "90"])
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[0]
        assert int(page.rotation) == 0
        # the chain resolves to the intermediate object's NUMBER; the page
        # does not corroborate it, so the reader takes no value from it
        _, value = document.xref_get_key(page.xref, "Rotate")
        assert _indirect_rotate(document, page, value) is None
    finally:
        document.close()


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


def test_the_native_census_loads_a_committed_reader_without_patching_the_current_one(monkeypatch):
    from tools.agree_native_census import _baseline_reader, _evidence_sha
    import evidence.native as current

    ref, reader = _baseline_reader("HEAD")
    assert len(ref) == 40
    pdf_bytes = _render_upright()
    expected = _evidence_sha(pdf_bytes)
    assert _evidence_sha(pdf_bytes, reader) == expected
    monkeypatch.setattr(current, "_raw_rotate", lambda *_: 45)
    assert _evidence_sha(pdf_bytes) != expected
    assert _evidence_sha(pdf_bytes, reader) == expected


def test_the_native_census_counts_an_inherited_indirect_rotation():
    from tools.agree_native_census import _Counts, _structural

    counts = _Counts()
    pdf_bytes = _with_objects(["45"], inherited=True, extra_pages=0)
    assert _structural(pdf_bytes, counts) is True
    assert counts.rotate_indirect == 1
    assert counts.rotate_indirect_invalid == 1


def test_the_native_census_exits_nonzero_on_movement_or_an_absent_population(tmp_path, monkeypatch, capsys):
    import csv
    import hashlib
    from tools import agree_native_census as census

    pdf_bytes = _render_upright()
    (tmp_path / "synthetic.pdf").write_bytes(pdf_bytes)
    with (tmp_path / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["content_sha256", "relative_path"])
        writer.writeheader()
        writer.writerow({"content_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                         "relative_path": "synthetic.pdf"})
    monkeypatch.setattr(census, "_baseline_reader", lambda _: ("synthetic-control", lambda _: None))
    args = ["--run", str(tmp_path), "--archive-root", str(tmp_path), "--verify-all"]
    assert census.main(args) == 2
    assert "STOP" in capsys.readouterr().out
    (tmp_path / "synthetic.pdf").unlink()
    assert census.main(args) == 3
    assert "INCOMPLETE" in capsys.readouterr().out

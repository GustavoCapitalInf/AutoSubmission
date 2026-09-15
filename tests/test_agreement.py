"""Phase 2.3 cell X (`docs/agent-handoffs/P23-AGREE.md` items 1, 5, 6; umbrella
case 7): native <-> extractor agreement and the geometry census,
`layout/agreement.py`.

Everything here is SYNTHETIC. The word geometry comes from
`tests/paddle_synthetic.py` (invented literals, a synthetic year >= 2031,
arithmetically generated figures), from PDFs this module renders with
PyMuPDF, or from evidence objects built literally in a test. No archive
document, no cache, no network.

What is proven
--------------
* the pair table (card item 5): identical -> 1.0; a known shift -> the matched
  ratio the box arithmetic predicts, word by word; perturbed amounts -> the
  exact-agreement drop equal to the perturbed count; a rotated pair at each of
  the four angles -> the rotation census and matching are correct; a skewed
  page -> the skew census within the card's 0.5 degrees (and, measured, far
  inside it);
* the frame normalisation: a 300-dpi `pixel` frame and a `pdf_point` frame
  describe one rectangle in points (M3 dies here);
* alignment is greedy by IoU and each box is used ONCE (M2);
* the character normaliser is applied (M4) and the amount/date agreement is
  computed over MATCHED pairs only (M5);
* nothing outside `layout/` may read an agreement statistic (M6: the AST
  guard over `ocr/` and `analysis/`), the module imports only the standard
  library, `evidence` and `layout.signals`, and the row projection is EMPTY
  for a document carrying only one evidence source (M7).
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import fitz
import pytest

from evidence import (
    ExtractionEvidence,
    PageEvidence,
    PageFrame,
    WordBox,
    native_evidence_from_pdf,
    word_id,
)
from layout.agreement import (
    AGREEMENT_VERSION,
    FRAME_TOLERANCE,
    IOU_THRESHOLD,
    TABLE_REGION_MIN_MONEY,
    TABLE_REGION_VERSION,
    TEXT_NORMALISER_VERSION,
    align,
    box_iou,
    display_frame_size,
    display_words,
    document_agreement,
    frames_agree,
    geometry_census,
    normalise_text,
    page_agreement,
    row_columns,
)
from tests.paddle_synthetic import (
    CHAR_WIDTH,
    build_ledger_page,
    raster_dimensions,
    render_native_pdf,
    synthetic_paddle_result,
)

ROOT = Path(__file__).resolve().parents[1]
DPI = 300
PADDLE_EXTRACTOR = "paddle-ocr+ppocrv5"
NATIVE_EXTRACTOR = "native-pdf-words"
SHA = "A" * 64


# ---------------------------------------------------------------------------
# fixtures built from the ONE synthetic ledger page's KNOWN word positions
# ---------------------------------------------------------------------------

def _known_words(page) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Every synthetic word as `(text, (x0, y0, x1, y1))` in points, in
    reading order — the ground truth both sides of a pair are built from."""
    return [(word.text, (word.x0, word.y0, word.x1, word.y1))
            for line in page.lines for word in line.words]


def _native_page(words, *, width_pt: float, height_pt: float, page_index: int = 0,
                 rotation_deg: int = 0) -> PageEvidence:
    """A `pdf_point` page carrying `words` verbatim — the native side of a
    synthetic pair, built from the SAME ground truth the extractor side is
    built from so an expected statistic is exact rather than approximate."""
    frame = PageFrame.pdf_points(page_index=page_index, width_pt=width_pt, height_pt=height_pt,
                                 rotation_deg=rotation_deg)
    boxes = tuple(
        WordBox(word_id=word_id(page_index, None, index), page_index=page_index, text=text,
                x0=box[0], y0=box[1], x1=box[2], y1=box[3])
        for index, (text, box) in enumerate(words)
    )
    return PageEvidence(frame=frame, words=boxes)


def _pixel_page(words, *, width_pt: float, height_pt: float, dpi: int = DPI, page_index: int = 0,
                rotation_deg: int = 0) -> PageEvidence:
    """The extractor side: the same ground truth in the raster's PIXEL space
    at `dpi` (what `ocr/paddle_adapter.py` produces from a worker result)."""
    scale = dpi / 72.0
    frame = PageFrame.pixel(
        page_index=page_index, raster_width_px=round(width_pt * scale),
        raster_height_px=round(height_pt * scale), dpi=float(dpi),
        pdf_width_pt=width_pt, pdf_height_pt=height_pt, rotation_deg=rotation_deg,
    )
    boxes = tuple(
        WordBox(word_id=word_id(page_index, 0, index), page_index=page_index, text=text,
                x0=box[0] * scale, y0=box[1] * scale, x1=box[2] * scale, y1=box[3] * scale,
                confidence=1.0, line_ref=0)
        for index, (text, box) in enumerate(words)
    )
    return PageEvidence(frame=frame, words=boxes)


def _document(page: PageEvidence, *, extractor_id: str, document_sha: str = SHA) -> ExtractionEvidence:
    return ExtractionEvidence(document_sha256=document_sha, extractor_id=extractor_id,
                              model_token=extractor_id, pages=(page,))


@pytest.fixture(scope="module")
def ledger():
    return build_ledger_page(8)


@pytest.fixture(scope="module")
def truth(ledger):
    return _known_words(ledger)


def _pair(ledger, truth, *, extractor_words=None, dpi: int = DPI):
    native = _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    extractor = _pixel_page(extractor_words if extractor_words is not None else truth,
                            width_pt=ledger.width_pt, height_pt=ledger.height_pt, dpi=dpi)
    return native, extractor


# ---------------------------------------------------------------------------
# the versions and thresholds are PINNED (M1's first killer)
# ---------------------------------------------------------------------------

def test_the_versions_and_thresholds_are_pinned():
    """A threshold change without a version bump is the mutation M1 attacks:
    these constants are the contract every recorded statistic is comparable
    under, so each is pinned at its published value."""
    assert AGREEMENT_VERSION == 1
    assert IOU_THRESHOLD == 0.5
    assert TEXT_NORMALISER_VERSION == 1
    assert TABLE_REGION_VERSION == 1
    assert TABLE_REGION_MIN_MONEY == 2
    assert FRAME_TOLERANCE == 0.01


# ---------------------------------------------------------------------------
# the pair table
# ---------------------------------------------------------------------------

def test_identical_words_at_300_dpi_agree_completely(ledger, truth):
    """Card item 5, row 1, and M3's killer. The two pages carry the SAME
    words: one in points, one in the 300-dpi raster's pixels. Normalised into
    the display frame both describe one rectangle, so every box aligns with
    IoU 1.0 and every statistic is 1.0. A pixel frame left unscaled puts
    every box 4.1666x too far right and down: no pair reaches IoU 0.5 and the
    matched ratio is 0.0."""
    native, extractor = _pair(ledger, truth)
    result = page_agreement(native, extractor)
    assert result.native_words == result.extractor_words == len(truth) == 54
    assert result.matched_pairs == len(truth)
    assert result.matched_native == 1.0 and result.matched_extractor == 1.0
    assert result.char_agreement == 1.0
    assert result.amount_agreement == 1.0 and result.amount_pairs == 16
    assert result.date_agreement == 1.0 and result.date_pairs == 8
    assert result.frame_mismatch is False
    assert result.unmatched_table_density == 0.0


def test_a_known_shift_drops_the_matched_ratio_exactly_as_the_box_arithmetic_says(ledger, truth):
    """Card item 5, row 2. Every extractor box is shifted right by `dx`
    points. Two identical `w x h` boxes offset by `dx` have
    `IoU = (w - dx) / (w + dx)`, so a box matches iff `w >= 3 * dx` — the
    expected matched count is computed from the widths here, never copied
    from the implementation. `dx` is deliberately two and a half characters
    wide: `3 * dx` then falls between two whole token widths, so no word sits
    exactly ON the 0.5 boundary where a float comparison decides the answer."""
    dx = 2.5 * CHAR_WIDTH  # the short tokens fall out, the long ones survive
    shifted = [(text, (x0 + dx, y0, x1 + dx, y1)) for text, (x0, y0, x1, y1) in truth]
    expected = [text for text, (x0, _, x1, _) in truth if (x1 - x0) >= 3 * dx]
    native, extractor = _pair(ledger, truth, extractor_words=shifted)
    result = page_agreement(native, extractor)
    assert 0 < len(expected) < len(truth)
    assert result.matched_pairs == len(expected)
    assert result.matched_native == pytest.approx(len(expected) / len(truth))
    assert result.matched_extractor == pytest.approx(len(expected) / len(truth))
    # every surviving pair is still the SAME token, so the text statistics
    # stay perfect on what matched — a shift is a geometry finding, not a
    # recognition one, and the two must not be confused
    assert result.char_agreement == 1.0
    # M5's killer: the parsed-shape denominators are the MATCHED pairs, not
    # the words. Every amount token here is too short to survive the shift,
    # so no matched pair carries money at all and the statistic is
    # unmeasured — `None`, never a manufactured 1.0; the ten-character dates
    # do survive and are measured.
    assert [text for text in expected if text.endswith(".00")] == []
    assert result.amount_pairs == 0 and result.amount_agreement is None
    assert result.date_pairs == 8 and result.date_agreement == 1.0


def test_perturbed_amounts_drop_the_exact_agreement_by_the_perturbed_count(ledger, truth):
    """Card item 5, row 3, and M5's killer. Two amount tokens have one digit
    changed on the extractor side; the boxes are untouched, so the pairs
    still MATCH and the exact-amount agreement falls by exactly two of the
    sixteen amount-bearing pairs. A mutant that computes amount agreement
    over every word rather than over matched pairs cannot reproduce these
    denominators."""
    perturbed = []
    hits = 0
    for text, box in truth:
        if hits < 2 and text.endswith(".00"):
            perturbed.append((text[:-1] + "9", box))
            hits += 1
        else:
            perturbed.append((text, box))
    assert hits == 2
    native, extractor = _pair(ledger, truth, extractor_words=perturbed)
    result = page_agreement(native, extractor)
    assert result.matched_pairs == len(truth)          # geometry untouched
    assert result.amount_pairs == 16
    assert result.amount_agreement == pytest.approx(14 / 16)
    assert result.date_agreement == 1.0                 # dates untouched
    assert result.char_agreement < 1.0


def test_a_perturbed_date_drops_only_the_date_agreement(ledger, truth):
    perturbed = []
    done = False
    for text, box in truth:
        if not done and text.startswith("2031-01-"):
            perturbed.append(("2031-02-" + text[-2:], box))
            done = True
        else:
            perturbed.append((text, box))
    assert done
    native, extractor = _pair(ledger, truth, extractor_words=perturbed)
    result = page_agreement(native, extractor)
    assert result.date_pairs == 8
    assert result.date_agreement == pytest.approx(7 / 8)
    assert result.amount_agreement == 1.0


def test_the_case_and_whitespace_normaliser_is_applied(ledger, truth):
    """M4's killer. The extractor reads the same tokens in a different case
    and with stray internal whitespace; the normaliser (case-folded,
    whitespace-collapsed) makes the character agreement 1.0. Without it the
    agreement falls, which is exactly the mutant."""
    noisy = [(text.lower() if text.isupper() else text, box) for text, box in truth]
    assert any(a[0] != b[0] for a, b in zip(truth, noisy))
    native, extractor = _pair(ledger, truth, extractor_words=noisy)
    result = page_agreement(native, extractor)
    assert result.char_agreement == 1.0
    assert normalise_text("  Ending   BALANCE ") == "ending balance"
    assert normalise_text("A\tB\nC") == "a b c"


def test_alignment_is_greedy_and_uses_every_box_once(ledger):
    """M2's killer, in BOTH directions. One word on one side overlaps TWO on
    the other, each above the threshold: the higher IoU wins and the loser
    stays unmatched. A box spent twice would let one reader's single word
    "cover" two of the other's and inflate the matched ratio, so the property
    is pinned with the duplicate on the extractor side AND on the native
    side."""
    one = [("TOTAL", (100.0, 100.0, 160.0, 112.0))]
    two = [("TOTAL", (101.0, 100.0, 161.0, 112.0)), ("TOTAL", (104.0, 100.0, 164.0, 112.0))]

    native = _native_page(one, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    extractor = _pixel_page(two, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    pairs = align(display_words(native), display_words(extractor))
    assert len(pairs) == 1 and pairs[0][0] == 0 and pairs[0][1] == 0
    result = page_agreement(native, extractor)
    assert result.matched_pairs == 1
    assert result.matched_native == 1.0
    assert result.matched_extractor == pytest.approx(0.5)

    native = _native_page(two, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    extractor = _pixel_page(one, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    pairs = align(display_words(native), display_words(extractor))
    assert len(pairs) == 1 and pairs[0][0] == 0 and pairs[0][1] == 0
    result = page_agreement(native, extractor)
    assert result.matched_pairs == 1
    assert result.matched_native == pytest.approx(0.5)
    assert result.matched_extractor == 1.0


def test_a_negative_amount_never_agrees_with_its_positive_twin(ledger, truth):
    """Review closure, MINOR-1 / mutant FR3 — the material one. The synthetic
    ledger carries no negative figure, so nothing pinned that a debit must
    DISAGREE with a credit. Here the extractor reads every amount with a
    leading minus: the boxes are untouched, so all 54 pairs still match, and
    the exact money agreement must fall to ZERO over the sixteen
    money-bearing pairs. A comparison that dropped the sign — the one thing
    the statistic 2.5 will read must not be blind to — would report 1.0.
    """
    negated = [(("-" + text) if text.endswith(".00") else text, box) for text, box in truth]
    assert sum(1 for text, _ in negated if text.startswith("-")) == 16
    native, extractor = _pair(ledger, truth, extractor_words=negated)
    result = page_agreement(native, extractor)
    assert result.matched_pairs == len(truth)
    assert result.amount_pairs == 16
    assert result.amount_agreement == 0.0
    # and the parenthesised and trailing-minus spellings of the same debit
    # agree with each other, because the grammar resolves them to one value
    for spelling in ("(12.00)", "12.00-", "-12.00"):
        both = _pair(ledger, [("-12.00", (100.0, 100.0, 160.0, 112.0))],
                     extractor_words=[(spelling, (100.0, 100.0, 160.0, 112.0))])
        assert page_agreement(*both).amount_agreement == 1.0, spelling
    # ... and none of them agrees with the credit
    both = _pair(ledger, [("-12.00", (100.0, 100.0, 160.0, 112.0))],
                 extractor_words=[("12.00", (100.0, 100.0, 160.0, 112.0))])
    assert page_agreement(*both).amount_agreement == 0.0


def test_the_skew_statistic_is_the_MEDIAN_over_lines_not_the_mean(ledger):
    """Review closure, MINOR-1 / mutant FR4. Every skew fixture until now was
    UNIFORMLY skewed, where the mean and the median coincide, so the
    published statistic's definition was unpinned. A page of two blocks —
    six flat lines and two steeply skewed ones — separates them: the median
    is 0.0 (what most of the page does), the mean is not.
    """
    drop_per_column = 5.0                      # gentle enough that no line splits
    angle = math.degrees(math.atan(drop_per_column / 120.0))

    def two_block_page(flat_rows: int, skewed_rows: int):
        words: list[tuple[str, tuple[float, float, float, float]]] = []
        for row in range(flat_rows):
            y = 100.0 + row * 30.0
            for column in range(3):
                x = 72.0 + column * 120.0
                words.append((f"FLAT{row}{column}", (x, y, x + 60.0, y + 11.0)))
        for row in range(skewed_rows):
            y = 400.0 + row * 30.0
            for column in range(3):
                x = 72.0 + column * 120.0
                drop = column * drop_per_column
                words.append((f"SKEW{row}{column}", (x, y + drop, x + 60.0, y + drop + 11.0)))
        page = _native_page(words, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
        return geometry_census(_document(page, extractor_id=NATIVE_EXTRACTOR))[0]

    facts = two_block_page(6, 2)
    assert facts.measured_lines == 8                            # nothing fragmented
    assert facts.skew_deg == pytest.approx(0.0, abs=1e-9)       # the MEDIAN: what most of the page does
    mean = (6 * 0.0 + 2 * angle) / 8
    assert abs(facts.skew_deg - mean) > 0.4                     # ... and not the mean

    #: The limit MINOR-4 records: one angle per page is the contract, so a
    #: page of two equal blocks reports an angle NEITHER block has.
    even = two_block_page(4, 4)
    assert even.measured_lines == 8
    assert even.skew_deg == pytest.approx(angle / 2, abs=1e-9)
    assert 0.0 < even.skew_deg < angle


def test_the_iou_threshold_is_inclusive_at_exactly_one_half(ledger):
    """Review closure, MINOR-1 / mutant FR1. `box_iou`'s arithmetic was pinned
    at exactly 0.5, but `align`'s COMPARISON was not: a pair sitting exactly
    on the threshold must MATCH (`>=`), and one a hair below must not."""
    native = _native_page([("TOTAL", (0.0, 0.0, 30.0, 10.0))],
                          width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    on = _native_page([("TOTAL", (10.0, 0.0, 40.0, 10.0))],
                      width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    assert box_iou((0.0, 0.0, 30.0, 10.0), (10.0, 0.0, 40.0, 10.0)) == pytest.approx(0.5)
    assert len(align(display_words(native), display_words(on))) == 1
    below_box = (10.0 + 1 / 50, 0.0, 40.0 + 1 / 50, 10.0)
    below = _native_page([("TOTAL", below_box)],
                         width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    assert box_iou((0.0, 0.0, 30.0, 10.0), below_box) < 0.5
    assert align(display_words(native), display_words(below)) == ()


def test_a_legal_non_uniform_pixel_frame_normalises_to_the_true_points(ledger):
    """Review closure, MINOR-2 / mutant FR2's neighbour. `PageFrame` validates
    each axis' scale against `dpi / 72` only to within `SCALE_TOLERANCE`, so a
    raster rounded to whole pixels can be legally non-uniform. Scaling both
    axes by one nominal `72 / dpi` then moves a word at the page FOOT by
    several points and drops the pair — a measurement artefact that reads as
    the two engines disagreeing about everything, with `frame_mismatch`
    False. Each axis is scaled by its own factor, so the pair survives."""
    # Place short words at the page foot, where a legal scale discrepancy
    # exceeds their IoU matching margin. The earlier ledger-only control
    # lived too high on the page and could not kill the nominal-scale mutant.
    truth = [("FOOT", (72.0, 740.0, 112.0, 750.0)),
             ("EDGE", (200.0, 760.0, 240.0, 770.0))]
    scale = DPI / 72.0
    height_px = round(ledger.height_pt * scale) - 25          # a legal, non-uniform raster
    frame = PageFrame.pixel(page_index=0, raster_width_px=round(ledger.width_pt * scale),
                            raster_height_px=height_px, dpi=float(DPI),
                            pdf_width_pt=ledger.width_pt, pdf_height_pt=ledger.height_pt)
    assert frame.scale_y != frame.scale_x                      # non-uniform ...
    assert abs(frame.scale_y - DPI / 72.0) <= 0.01 * (DPI / 72.0)   # ... and legal
    words = tuple(
        WordBox(word_id=word_id(0, 0, index), page_index=0, text=text,
                x0=box[0] * frame.scale_x, y0=box[1] * frame.scale_y,
                x1=box[2] * frame.scale_x, y1=box[3] * frame.scale_y)
        for index, (text, box) in enumerate(truth)
    )
    extractor = PageEvidence(frame=frame, words=words)
    native = _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    for expected, observed in zip(display_words(native), display_words(extractor)):
        assert observed.box == pytest.approx(expected.box)
    result = page_agreement(native, extractor)
    assert result.frame_mismatch is False
    assert result.matched_pairs == len(truth)
    assert result.matched_native == 1.0 and result.char_agreement == 1.0


def test_two_frames_that_disagree_about_the_rotation_are_a_frame_mismatch(ledger, truth):
    """Review closure, MINOR-3. On a SQUARE page the two rectangles match at
    every rotation, so a rotation mix-up between the readers was invisible as
    a frame mismatch and surfaced only as a low matched ratio — which the
    calibration would read as the engines disagreeing about the TEXT."""
    square = 600.0
    upright = _native_page([("TOTAL", (100.0, 100.0, 160.0, 112.0))],
                           width_pt=square, height_pt=square, rotation_deg=0)
    turned = _native_page([("TOTAL", (100.0, 100.0, 160.0, 112.0))],
                          width_pt=square, height_pt=square, rotation_deg=90)
    assert display_frame_size(upright.frame) == display_frame_size(turned.frame)
    assert frames_agree(upright.frame, turned.frame) is False
    assert page_agreement(upright, turned).frame_mismatch is True
    assert frames_agree(upright.frame, upright.frame) is True
    # 0 versus 180 on a letter page: the same rectangle, the other way up
    letter_up = _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    letter_down = _pixel_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt,
                              rotation_deg=180)
    assert page_agreement(letter_up, letter_down).frame_mismatch is True


def test_box_iou_and_the_threshold_behave_as_the_arithmetic_says():
    assert box_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert box_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert box_iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)
    # the boundary: two `w`-wide boxes offset by `w/3` sit exactly at 0.5
    assert box_iou((0.0, 0.0, 30.0, 10.0), (10.0, 0.0, 40.0, 10.0)) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# the table-region density (a named, versioned heuristic — never a layout model)
# ---------------------------------------------------------------------------

def test_unmatched_words_inside_a_candidate_table_region_are_counted(ledger, truth):
    """A candidate table region is the union of the y-bands of lines whose
    words carry at least `TABLE_REGION_MIN_MONEY` money shapes — on this page
    the eight ledger rows, never the two header lines. Dropping one extractor
    word inside a ledger row leaves exactly one unmatched word in the region;
    the denominator is every word of BOTH sides inside it."""
    dropped_index = next(i for i, (text, _) in enumerate(truth) if text.endswith(".00"))
    without = [pair for i, pair in enumerate(truth) if i != dropped_index]
    native, extractor = _pair(ledger, truth, extractor_words=without)
    result = page_agreement(native, extractor)
    # 8 ledger rows x 6 words = 48 native words in the region; 47 extractor
    assert result.words_in_table_region == 48 + 47
    assert result.unmatched_in_table_region == 1
    assert result.unmatched_table_density == pytest.approx(1 / 95)
    # a word in the HEADER lines is outside every region
    header = _native_page([("STATEMENT", (100.0, 60.0, 160.0, 72.0))],
                          width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    empty = page_agreement(header, _pixel_page([], width_pt=ledger.width_pt, height_pt=ledger.height_pt))
    assert empty.words_in_table_region == 0
    assert empty.unmatched_table_density is None


# ---------------------------------------------------------------------------
# frames
# ---------------------------------------------------------------------------

def test_two_frames_describing_one_rectangle_agree_and_a_mismatch_is_recorded(ledger, truth):
    native, extractor = _pair(ledger, truth)
    assert frames_agree(native.frame, extractor.frame) is True
    wrong = _pixel_page(truth, width_pt=ledger.width_pt * 1.2, height_pt=ledger.height_pt)
    assert frames_agree(native.frame, wrong.frame) is False
    result = page_agreement(native, wrong)
    assert result.frame_mismatch is True
    # a 0.5 % difference is inside the 1 % tolerance; 2 % is not
    near = PageFrame.pdf_points(page_index=0, width_pt=ledger.width_pt * 1.005, height_pt=ledger.height_pt)
    far = PageFrame.pdf_points(page_index=0, width_pt=ledger.width_pt * 1.02, height_pt=ledger.height_pt)
    assert frames_agree(native.frame, near) is True
    assert frames_agree(native.frame, far) is False


def test_a_frame_mismatch_never_stops_the_measurement(ledger, truth):
    """A recorded fact, never a refusal: the statistics are still computed and
    the mismatch is one more column (the row carries both)."""
    native, _ = _pair(ledger, truth)
    wrong = _pixel_page(truth, width_pt=ledger.width_pt * 1.2, height_pt=ledger.height_pt)
    result = page_agreement(native, wrong)
    assert result.frame_mismatch is True
    assert result.matched_pairs == len(truth)  # the words themselves still land


# ---------------------------------------------------------------------------
# rotation and skew (the geometry census)
# ---------------------------------------------------------------------------

def _display(rotation: int, box, width: float, height: float):
    """The INDEPENDENT display formula of the four-angle pin
    (`tests/test_native_evidence.py`), repeated here so a rotated pair's
    extractor side is built without asking the reader under test."""
    x0, y0, x1, y1 = box
    if rotation == 0:
        return (x0, y0, x1, y1)
    if rotation == 90:
        return (height - y1, x0, height - y0, x1)
    if rotation == 180:
        return (width - x1, height - y1, width - x0, height - y0)
    if rotation == 270:
        return (y0, width - x1, y1, width - x0)
    raise AssertionError(rotation)


def _rotated_pdf(ledger, rotation: int) -> bytes:
    document = fitz.open(stream=render_native_pdf(ledger), filetype="pdf")
    try:
        if rotation:
            document[0].set_rotation(rotation)
        return document.tobytes()
    finally:
        document.close()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_rotated_pair_matches_and_the_rotation_census_is_correct(ledger, truth, rotation):
    """Card item 5, row 4. The native side is the REAL reader on a page
    carrying `/Rotate`; the extractor side is the ground truth mapped by the
    independent display formula into the raster's pixels. Both describe the
    same displayed page, so every word matches at every angle and the census
    reports the rotation the page declares."""
    evidence = native_evidence_from_pdf(_rotated_pdf(ledger, rotation))
    assert evidence is not None
    native = evidence.pages[0]
    width, height = ledger.width_pt, ledger.height_pt
    display_w, display_h = (height, width) if rotation in (90, 270) else (width, height)
    assert (native.frame.width, native.frame.height) == (display_w, display_h)
    assert native.frame.rotation_deg == rotation
    mapped = [(text, _display(rotation, box, width, height)) for text, box in truth]
    extractor = _pixel_page(mapped, width_pt=display_w, height_pt=display_h, rotation_deg=rotation)
    result = page_agreement(native, extractor)
    assert result.frame_mismatch is False
    assert result.matched_pairs == len(truth)
    assert result.matched_native == 1.0 and result.matched_extractor == 1.0
    assert result.char_agreement == 1.0 and result.amount_agreement == 1.0
    facts = geometry_census(_document(native, extractor_id=NATIVE_EXTRACTOR))
    assert len(facts) == 1
    assert facts[0].rotation_deg == rotation
    assert facts[0].page_size == (round(display_w, 1), round(display_h, 1))


def test_the_skew_census_recovers_a_known_angle(ledger, truth):
    """Card item 5, row 5. Every word centre is rotated about the page centre
    by a known angle (a page scanned slightly crooked); the box sizes are
    unchanged, which is what the axis-aligned hull of a rotated box does to
    first order. The census recovers the angle well inside the card's 0.5
    degrees. Positive means the text descends to the right (y grows
    downward)."""
    angle = 0.6
    radians = math.radians(angle)
    cx, cy = ledger.width_pt / 2, ledger.height_pt / 2
    skewed = []
    for text, (x0, y0, x1, y1) in truth:
        mx, my = (x0 + x1) / 2 - cx, (y0 + y1) / 2 - cy
        rx = mx * math.cos(radians) - my * math.sin(radians) + cx
        ry = mx * math.sin(radians) + my * math.cos(radians) + cy
        half_w, half_h = (x1 - x0) / 2, (y1 - y0) / 2
        skewed.append((text, (rx - half_w, ry - half_h, rx + half_w, ry + half_h)))
    page = _native_page(skewed, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    facts = geometry_census(_document(page, extractor_id=NATIVE_EXTRACTOR))
    assert facts[0].skew_deg is not None
    assert abs(facts[0].skew_deg - angle) <= 0.5          # the card's contract
    assert abs(facts[0].skew_deg - angle) <= 0.05         # what it actually measures
    flat = _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    assert abs(geometry_census(_document(flat, extractor_id=NATIVE_EXTRACTOR))[0].skew_deg) <= 0.01


def test_the_geometry_census_reports_a_page_with_no_measurable_skew_as_none(ledger):
    page = _native_page([("ALONE", (100.0, 100.0, 160.0, 112.0))],
                        width_pt=ledger.width_pt, height_pt=ledger.height_pt)
    facts = geometry_census(_document(page, extractor_id=NATIVE_EXTRACTOR))
    assert facts[0].skew_deg is None
    assert facts[0].word_count == 1


# ---------------------------------------------------------------------------
# the REAL pair: the ONE native reader beside the fake worker's evidence
# ---------------------------------------------------------------------------

def test_the_real_native_reader_agrees_with_the_fake_workers_evidence(ledger):
    """The card's "a native page and its 300-dpi raster read by the fake
    worker's evidence". The native side is `evidence/native.py` on the
    rendered PDF; the extractor side is `ocr/paddle_adapter.py` on the
    synthetic PaddleOCR-shaped result for the SAME page at 300 dpi. The two
    geometries are independent (PyMuPDF's font metrics versus the fixture's
    fixed-width arithmetic), so this is the pair the calibration is actually
    made of: every word matches, and the MEASURED IoU floor is pinned."""
    from ocr.paddle_adapter import page_evidence_from_result

    evidence = native_evidence_from_pdf(render_native_pdf(ledger))
    assert evidence is not None
    native = evidence.pages[0]
    width_px, height_px = raster_dimensions(ledger, dpi=DPI)
    frame = PageFrame.pixel(page_index=0, raster_width_px=width_px, raster_height_px=height_px,
                            dpi=float(DPI), pdf_width_pt=ledger.width_pt, pdf_height_pt=ledger.height_pt)
    extractor = page_evidence_from_result(synthetic_paddle_result(ledger, dpi=DPI), frame=frame)
    result = page_agreement(native, extractor)
    assert result.native_words == result.extractor_words == 54
    assert result.matched_pairs == 54
    assert result.matched_native == 1.0 and result.matched_extractor == 1.0
    assert result.char_agreement == 1.0
    assert result.amount_agreement == 1.0 and result.date_agreement == 1.0
    assert result.frame_mismatch is False
    #: MEASURED while writing this pin (PyMuPDF 1.27.2.3): the lowest IoU over
    #: the 54 pairs was 0.7017 — the two readers box the same glyphs to about
    #: seven tenths, comfortably above the 0.5 threshold.
    assert min(iou for _, _, iou in result.pairs) >= 0.65


def test_the_document_fold_states_what_it_folds(ledger, truth):
    """Two pages, the second half as many words: the document-level ratios are
    word-weighted sums over the pages compared (never the mean of per-page
    ratios), which is what the row columns declare."""
    half = truth[: len(truth) // 2]
    native = _document_pages([
        _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=0),
        _native_page(half, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=1),
    ], extractor_id=NATIVE_EXTRACTOR)
    dropped = [pair for pair in half if not pair[0].endswith(".00")]
    extractor = _document_pages([
        _pixel_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=0),
        _pixel_page(dropped, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=1),
    ], extractor_id=PADDLE_EXTRACTOR)
    result = document_agreement(native, extractor)
    assert result.pages_compared == 2
    matched = len(truth) + len(dropped)
    assert result.matched_native == pytest.approx(matched / (len(truth) + len(half)))
    assert result.matched_extractor == 1.0
    assert result.frame_mismatch_pages == 0


def _document_pages(pages, *, extractor_id: str) -> ExtractionEvidence:
    return ExtractionEvidence(document_sha256=SHA, extractor_id=extractor_id,
                              model_token=extractor_id, pages=tuple(pages))


def test_documents_with_different_page_counts_compare_the_common_pages(ledger, truth):
    native = _document_pages([
        _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=0),
        _native_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=1),
    ], extractor_id=NATIVE_EXTRACTOR)
    extractor = _document_pages([
        _pixel_page(truth, width_pt=ledger.width_pt, height_pt=ledger.height_pt, page_index=0),
    ], extractor_id=PADDLE_EXTRACTOR)
    result = document_agreement(native, extractor)
    assert result.pages_compared == 1
    assert result.native_pages == 2 and result.extractor_pages == 1


# ---------------------------------------------------------------------------
# the row columns (card item 2) — the projection is EMPTY without both sources
# ---------------------------------------------------------------------------

AGREE_COLUMNS = (
    "agree_version", "agree_pages", "agree_matched_native", "agree_matched_paddle",
    "agree_char", "agree_amounts", "agree_dates", "agree_unmatched_table_density",
    "agree_frame_mismatch", "geom_rotation", "geom_skew_deg", "geom_page_size",
)


def test_the_row_columns_are_strings_in_the_card_order(ledger, truth):
    native, extractor = _pair(ledger, truth)
    columns = row_columns(document_agreement(_document(native, extractor_id=NATIVE_EXTRACTOR),
                                             _document(extractor, extractor_id=PADDLE_EXTRACTOR)))
    assert tuple(columns) == AGREE_COLUMNS
    assert all(isinstance(value, str) for value in columns.values())
    assert columns["agree_version"] == "1"
    assert columns["agree_pages"] == "1"
    assert columns["agree_matched_native"] == "1.0"
    assert columns["agree_matched_paddle"] == "1.0"
    assert columns["agree_char"] == "1.0"
    assert columns["agree_amounts"] == "1.0"
    assert columns["agree_dates"] == "1.0"
    assert columns["agree_frame_mismatch"] == "0"
    assert columns["geom_rotation"] == "0"
    assert columns["geom_page_size"] == "612.0x792.0"
    assert columns["geom_skew_deg"] == "0.0"


def test_row_columns_are_empty_for_a_missing_agreement():
    empty = row_columns(None)
    assert tuple(empty) == AGREE_COLUMNS
    assert set(empty.values()) == {""}


def test_the_runner_projects_the_columns_only_when_both_evidences_exist(ledger, truth):
    """M7's killer. A document carrying ONE evidence source projects EMPTY
    columns — a half-measured agreement must never read as a measured one."""
    from discovery.runner import DiscoveryRunner, DocumentRow

    native, extractor = _pair(ledger, truth)

    class _Doc:
        def __init__(self, native_evidence, evidence):
            self.native_evidence = native_evidence
            self.evidence = evidence

    native_doc = _document(native, extractor_id=NATIVE_EXTRACTOR)
    paddle_doc = _document(extractor, extractor_id=PADDLE_EXTRACTOR)
    for facts in ({"document": _Doc(native_doc, None)}, {"document": _Doc(None, paddle_doc)},
                  {"document": _Doc(None, None)}, {}):
        row = DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256=SHA, byte_size=1)
        DiscoveryRunner._project_agreement(row, facts)
        for column in AGREE_COLUMNS:
            assert getattr(row, column) == "", (column, facts)

    row = DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256=SHA, byte_size=1)
    DiscoveryRunner._project_agreement(row, {"document": _Doc(native_doc, paddle_doc)})
    assert row.agree_version == "1"
    assert row.agree_matched_native == "1.0"
    assert row.geom_page_size == "612.0x792.0"
    assert set(row.as_dict()) >= set(AGREE_COLUMNS)


def test_a_broken_agreement_is_a_finding_on_the_row_never_a_lost_document(monkeypatch, ledger, truth):
    """The same discipline the classifier projection follows: a reporting
    consumer must not be able to fail a run."""
    from discovery import runner as runner_module

    native, extractor = _pair(ledger, truth)

    class _Doc:
        native_evidence = _document(native, extractor_id=NATIVE_EXTRACTOR)
        evidence = _document(extractor, extractor_id=PADDLE_EXTRACTOR)

    def explode(*args, **kwargs):
        raise RuntimeError("simulated agreement defect")

    monkeypatch.setattr(runner_module, "document_agreement", explode)
    row = runner_module.DocumentRow(relative_path="F/a.pdf", folder_label="F",
                                    content_sha256=SHA, byte_size=1)
    runner_module.DiscoveryRunner._project_agreement(row, {"document": _Doc()})
    for column in AGREE_COLUMNS:
        assert getattr(row, column) == ""


def test_a_document_whose_evidence_attribute_raises_is_a_finding_not_an_exception():
    """Review closure, MINOR-6. `getattr` swallows only `AttributeError`, so a
    document object whose `evidence` (or `native_evidence`) property raises
    anything else propagated out of the projection and out of the row's single
    exit — a reporting consumer failing the run it only describes. Both reads
    are inside the guard now."""
    from discovery.runner import DiscoveryRunner, DocumentRow

    class _Exploding:
        @property
        def native_evidence(self):
            raise RuntimeError("reader exploded")

        @property
        def evidence(self):
            raise RuntimeError("reader exploded")

    class _HalfExploding:
        native_evidence = None

        @property
        def evidence(self):
            raise RuntimeError("reader exploded")

    for document in (_Exploding(), _HalfExploding()):
        row = DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256=SHA, byte_size=1)
        DiscoveryRunner._project_agreement(row, {"document": document})   # must not raise
        for column in AGREE_COLUMNS:
            assert getattr(row, column) == ""


# ---------------------------------------------------------------------------
# the boundaries (M6) — an agreement statistic never reaches a decision
# ---------------------------------------------------------------------------

def test_the_module_imports_only_the_standard_library_evidence_and_layout_signals():
    """Card item 1. `layout/agreement.py` is a pure measurement over evidence:
    no `ocr`, no `analysis`, no third party, and inside `layout` only the
    signal grammars it is told to import."""
    import sys

    tree = ast.parse((ROOT / "layout" / "agreement.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            imported.add(node.module)
    allowed = {"evidence", "layout.signals"}
    offenders = sorted(
        name for name in imported
        if name.split(".")[0] not in sys.stdlib_module_names and name not in allowed
    )
    assert offenders == [], offenders


DECISION_PACKAGES = ("ocr", "analysis")
_AGREEMENT_IMPORTS = ("agreement", "document_agreement", "page_agreement", "row_columns")


def agreement_readers(source: str, name: str) -> list[str]:
    """Every way a module could read an agreement statistic: importing the
    module (by any spelling), naming one of its entry points, or naming an
    `agree_*` column as an attribute, a bare name or a string. A pure
    function of SOURCE TEXT so the guard can be run over a scratch copy with
    a mutant planted in it — which is what proves the guard bites."""
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source, filename=name)):
        if isinstance(node, ast.Import):
            offenders += [f"{name}: import {a.name}" for a in node.names
                          if a.name.startswith("layout.agreement")]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("layout.agreement"):
                offenders.append(f"{name}: from {node.module}")
            if node.module == "layout":
                offenders += [f"{name}: from layout import {a.name}" for a in node.names
                              if a.name in _AGREEMENT_IMPORTS]
        elif isinstance(node, ast.Attribute) and node.attr.startswith("agree_"):
            offenders.append(f"{name}: .{node.attr}")
        elif isinstance(node, ast.Name) and node.id.startswith("agree_"):
            offenders.append(f"{name}: {node.id}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value.startswith("agree_"):
            offenders.append(f"{name}: {node.value!r}")
    return offenders


def test_no_decision_package_reads_an_agreement_statistic():
    """`ocr/` (the router and the intake ladder) and `analysis/` (the
    structurer and the validator) may not import `layout.agreement` and may
    not name an `agree_*` column: a calibration statistic that reached a
    trigger or a verdict would be the third engine the anti-optimizer rule
    forbids (E4 is review evidence, recorded on the row, and nothing more)."""
    offenders: list[str] = []
    for package in DECISION_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            offenders += agreement_readers(path.read_text(encoding="utf-8"), path.name)
    assert offenders == [], offenders


def test_m6_the_guard_fires_on_a_scratch_copy_of_the_router_and_the_structurer():
    """M6's killer, planted rather than committed: the router's and the
    structurer's real sources are copied IN MEMORY, each mutant is added to
    the copy, and the guard must name it. The working tree is never touched,
    which is a stronger proof of the same property than editing it — and it
    means this mutant can be run on a shared host without a restore."""
    for relative in ("ocr/escalation.py", "analysis/structurer/geometry.py"):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert agreement_readers(source, relative) == []
        for mutant in (
            "\nfrom layout.agreement import document_agreement\n",
            "\nfrom layout import agreement\n",
            "\nimport layout.agreement\n",
            "\ndef _peek(row):\n    return row.agree_char\n",
            "\ndef _peek(row):\n    return row['agree_matched_native']\n",
        ):
            assert agreement_readers(source + mutant, relative) != [], (relative, mutant)


# ---------------------------------------------------------------------------
# the census instrument (card item 3) — counts and percentiles, never a word
# ---------------------------------------------------------------------------

def _research_cache(tmp_path, ledger, truth):
    """A synthetic research partition: one PAIRED document (both readings)
    and one with the native reading only."""
    from types import SimpleNamespace

    from webapp.artifact_cache import open_cache

    native, extractor = _pair(ledger, truth)
    key = "B" * 64
    cache = open_cache(tmp_path)
    cache.put_ocr("C" * 64, key, SimpleNamespace(
        model="fake", pages=["page"],
        evidence=_document(extractor, extractor_id=PADDLE_EXTRACTOR, document_sha="C" * 64),
        native_evidence=_document(native, extractor_id=NATIVE_EXTRACTOR, document_sha="C" * 64)))
    cache.put_ocr("D" * 64, key, SimpleNamespace(
        model="fake", pages=["page"], evidence=None,
        native_evidence=_document(native, extractor_id=NATIVE_EXTRACTOR, document_sha="D" * 64)))
    return key


def test_the_census_prints_counts_and_percentiles_and_never_a_word(tmp_path, capsys, ledger, truth):
    """M10's killer. Every token of the fixture page — its headers, its
    invented description, its generated figures and its synthetic date — is
    absent from the census output, which carries only counts, percentiles and
    the labels it was given."""
    from tools.agreement_census import main

    key = _research_cache(tmp_path, ledger, truth)
    assert main(["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod",
                 "--settings-key", key, "--label", "CTRL"]) == 0
    output = capsys.readouterr().out
    for token in ("SYNTHETIC", "STATEMENT", "DESCRIPTION", "AMOUNT", "BALANCE", "DATE", "ROW",
                  "2031-01-01", "510.00", "10.00"):
        assert token not in output, token
    assert "documents with BOTH readings (paired)" in output
    assert "pages compared" in output
    assert "geometry census" in output
    assert "geometry census (CTRL; native reading)" in output
    assert "geometry census (CTRL; extractor reading)" in output
    native_geometry = output.split("geometry census (CTRL; native reading)", 1)[1]
    extractor_geometry = output.split("geometry census (CTRL; extractor reading)", 1)[1]
    assert int(native_geometry.split("pages", 1)[1].split()[0]) == 2
    assert int(extractor_geometry.split("pages", 1)[1].split()[0]) == 1
    # the two documents: one paired, one not
    numbers = {line.split()[-1] for line in output.splitlines() if line.startswith("  documents")}
    assert "1" in numbers
    assert "rotation   0 deg" in output


def test_the_census_refuses_a_partition_it_cannot_identify(tmp_path, capsys, ledger, truth):
    """It never guesses which partition it is reading: a malformed id is
    refused by the OCR key's own shape rule, and a cache holding TWO
    evidence-carrying keys is refused with the count rather than resolved by
    a preference order. A cache with exactly one such key resolves, and the
    report names the door it came through."""
    from types import SimpleNamespace

    from webapp.artifact_cache import open_cache

    from tools.agreement_census import CensusRefused, main

    _research_cache(tmp_path, ledger, truth)
    with pytest.raises(CensusRefused, match="research-partition"):
        main(["--data-dir", str(tmp_path), "--research-partition", "has a space"])

    # one evidence-carrying key: resolved, and said out loud
    assert main(["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod"]) == 0
    assert "the cache scan" in capsys.readouterr().out

    # a second one: refused with the count, never a preference order
    native, extractor = _pair(ledger, truth)
    open_cache(tmp_path).put_ocr("C" * 64, "F" * 64, SimpleNamespace(
        model="fake", pages=["page"], native_evidence=None,
        evidence=_document(extractor, extractor_id=PADDLE_EXTRACTOR)))
    with pytest.raises(CensusRefused, match="--run or --settings-key"):
        main(["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod"])


def test_the_census_separates_populations_in_one_shared_partition(tmp_path, capsys, ledger, truth):
    from tools.agreement_census import CensusRefused, main

    key = _research_cache(tmp_path, ledger, truth)
    population = tmp_path / "population.shas"
    population.write_text("# named population\n" + "D" * 64 + "\n" + "E" * 64 + "\n", encoding="utf-8")
    arguments = ["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod",
                 "--settings-key", key, "--shas", str(population)]
    assert main(arguments) == 0
    output = capsys.readouterr().out
    counts = {line.rsplit(maxsplit=1)[0].strip(): int(line.rsplit(maxsplit=1)[1])
              for line in output.splitlines() if line.startswith("  documents")}
    assert counts["documents in the selected population"] == 2
    assert counts["documents with BOTH readings (paired)"] == 0
    assert counts["documents with one reading (unpaired)"] == 1
    assert counts["documents whose record could not be read"] == 1
    population.write_text("", encoding="utf-8")
    with pytest.raises(CensusRefused, match="nonempty"):
        main(arguments)


def test_the_census_refuses_a_run_recorded_under_another_partition(tmp_path):
    """A census of one partition never reads another's artifacts — and a
    PRODUCTION run (its recorded partition empty) is refused by the same
    check, which is the run-of-record boundary restated at this door."""
    import json

    from tools.agreement_census import CensusRefused, _key_from_run

    run = tmp_path / "run"
    run.mkdir()
    (run / "provenance.json").write_text(json.dumps(
        {"run_of_record": {"partitions": {"research_partition": "", "paddle_ocr_key": "E" * 64}}}),
        encoding="utf-8")
    with pytest.raises(CensusRefused, match="research_partition"):
        _key_from_run(run, "paddle-v5-prod")


def test_the_census_never_substitutes_an_offline_key_for_an_unrecorded_paddle_key(tmp_path):
    import json
    from tools.agreement_census import CensusRefused, _key_from_run

    (tmp_path / "provenance.json").write_text(json.dumps({"run_of_record": {"partitions": {
        "research_partition": "paddle-v5-prod", "offline_ocr_key": "B" * 64,
        "paddle_ocr_key_note": "not recorded here",
    }}}), encoding="utf-8")
    with pytest.raises(CensusRefused, match="without paddle_ocr_key"):
        _key_from_run(tmp_path, "paddle-v5-prod")


def test_the_census_refuses_an_empty_measurement_under_the_selected_key(tmp_path, ledger, truth):
    from tools.agreement_census import CensusRefused, main

    _research_cache(tmp_path, ledger, truth)
    population = tmp_path / "selected.shas"
    population.write_text("C" * 64 + "\n", encoding="utf-8")
    with pytest.raises(CensusRefused, match="empty measurement"):
        main(["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod",
              "--settings-key", "E" * 64, "--shas", str(population)])


def test_the_census_refuses_conflicting_extractor_identities_under_one_key(tmp_path, ledger, truth):
    from dataclasses import replace
    from types import SimpleNamespace
    from tools.agreement_census import CensusRefused, main
    from webapp.artifact_cache import open_cache

    key = _research_cache(tmp_path, ledger, truth)
    native, extractor = _pair(ledger, truth)
    alternative = replace(_document(extractor, extractor_id=PADDLE_EXTRACTOR, document_sha="D" * 64),
                          runtime={"pipeline_switches": {"orientation": True}})
    open_cache(tmp_path).put_ocr("D" * 64, key, SimpleNamespace(
        model="fake", pages=["page"], evidence=alternative,
        native_evidence=_document(native, extractor_id=NATIVE_EXTRACTOR, document_sha="D" * 64)))
    with pytest.raises(CensusRefused, match="conflicting extractor identities"):
        main(["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod",
              "--settings-key", key])


@pytest.mark.parametrize("corruption", [
    "missing_evidence", "malformed_evidence", "no_pages", "native_in_extractor",
    "extractor_in_native", "evidence_sha", "envelope_sha", "envelope_key", "envelope_stage",
])
def test_the_census_refuses_empty_or_misidentified_evidence(tmp_path, ledger, truth, corruption):
    import json
    import sqlite3
    from dataclasses import replace
    from evidence.canonical import from_json, to_json
    from tools.agreement_census import CensusRefused, main

    key = _research_cache(tmp_path, ledger, truth)
    selected = "C" * 64
    population = tmp_path / "selected.shas"
    population.write_text(selected + "\n", encoding="utf-8")
    with sqlite3.connect(tmp_path / "webapp.db") as conn:
        artifact = conn.execute("SELECT artifact_path FROM artifact_cache WHERE input_sha256=?",
                                (selected,)).fetchone()[0]
    path = tmp_path / "artifacts" / artifact
    payload = json.loads(path.read_text(encoding="utf-8"))
    record = payload["artifact"]["document"]
    if corruption in {"missing_evidence", "malformed_evidence"}:
        record["evidence"] = record["native_evidence"] = (
            None if corruption == "missing_evidence" else {"invalid": True})
    elif corruption == "no_pages":
        for slot in ("evidence", "native_evidence"):
            record[slot] = to_json(replace(from_json(record[slot]), pages=()))
    elif corruption == "native_in_extractor":
        record["evidence"] = record["native_evidence"]
    elif corruption == "extractor_in_native":
        record["native_evidence"] = record["evidence"]
    elif corruption == "evidence_sha":
        record["evidence"] = to_json(replace(from_json(record["evidence"]), document_sha256="E" * 64))
    else:
        field = {"envelope_sha": "input_sha256", "envelope_key": "settings_key",
                 "envelope_stage": "stage"}[corruption]
        payload[field] = "E" * 64 if corruption != "envelope_stage" else "other"
        # A readable companion has native geometry. Envelope conflict must
        # refuse in its own right, not merely reach the empty-measurement guard.
        population.write_text(selected + "\n" + "D" * 64 + "\n", encoding="utf-8")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CensusRefused):
        main(["--data-dir", str(tmp_path), "--research-partition", "paddle-v5-prod",
              "--settings-key", key, "--shas", str(population)])


@pytest.mark.parametrize("reverse", [False, True])
def test_the_census_refuses_duplicate_index_rows_in_either_order(tmp_path, reverse):
    """The cache index's primary key does not make its selection tuple unique.
    A malformed index must refuse even when either candidate is readable."""
    import hashlib
    import json
    import sqlite3

    from tools.agreement_census import CensusRefused, _Partition

    sha, key = "A" * 64, "B" * 64
    root = tmp_path / "artifacts"
    root.mkdir()
    candidates = [("left", {"side": "left"}), ("right", {"side": "right"})]
    if reverse:
        candidates.reverse()
    for name, document in candidates:
        (root / (name + ".json")).write_text(json.dumps({
            "stage": "ocr", "input_sha256": sha, "settings_key": key,
            "artifact": {"document": document},
        }), encoding="utf-8")
    database = tmp_path / "webapp.db"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE artifact_cache (stage TEXT, cache_key TEXT, "
                     "input_sha256 TEXT, settings_key TEXT, artifact_path TEXT, "
                     "PRIMARY KEY(stage, cache_key))")
        conn.execute("INSERT INTO artifact_cache VALUES (?, ?, ?, ?, ?)",
                     ("ocr", candidates[0][0], sha, key, candidates[0][0] + ".json"))
    conn.close()
    partition = _Partition(tmp_path, key)
    try:
        assert partition.document(sha) == candidates[0][1]
        assert partition.document("C" * 64) is None
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            partition.conn.execute("DELETE FROM artifact_cache")
    finally:
        partition.close()
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO artifact_cache VALUES (?, ?, ?, ?, ?)",
                     ("ocr", candidates[1][0], sha, key, candidates[1][0] + ".json"))
    conn.close()
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    partition = _Partition(tmp_path, key)
    try:
        with pytest.raises(CensusRefused, match="ambiguous indexed artifacts") as refusal:
            partition.document(sha)
        assert sha not in str(refusal.value) and key not in str(refusal.value)
    finally:
        partition.close()
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_the_census_checks_for_another_evidence_key_beyond_the_first_twenty_five_records(tmp_path, ledger, truth):
    from types import SimpleNamespace
    from tools.agreement_census import CensusRefused, _key_by_scan
    from webapp.artifact_cache import open_cache

    _research_cache(tmp_path, ledger, truth)
    cache = open_cache(tmp_path)
    other_key = "F" * 64
    for ordinal in range(1, 26):
        cache.put_ocr(f"{ordinal:064X}", other_key,
                      SimpleNamespace(model="fake", pages=["page"], evidence=None, native_evidence=None))
    native, extractor = _pair(ledger, truth)
    cache.put_ocr("E" * 64, other_key, SimpleNamespace(
        model="fake", pages=["page"], native_evidence=None,
        evidence=_document(extractor, extractor_id=PADDLE_EXTRACTOR, document_sha="E" * 64)))
    with pytest.raises(CensusRefused, match="2 of the cache's 2"):
        _key_by_scan(tmp_path)


def test_the_agreement_module_names_no_verdict_vocabulary():
    """Nothing here decides. The module may not carry a threshold vocabulary
    that reads as a decision — no `trigger`, no `escalate`, no `refuse`, no
    outcome name — only measurements and their versions."""
    source = (ROOT / "layout" / "agreement.py").read_text(encoding="utf-8").lower()
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names |= {node.name for node in ast.walk(tree)
              if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    forbidden = ("trigger", "escalat", "verdict", "validated", "refuse")
    offenders = sorted(name for name in names if any(token in name.lower() for token in forbidden))
    assert offenders == [], offenders

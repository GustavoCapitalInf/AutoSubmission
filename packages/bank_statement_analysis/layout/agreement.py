"""layout/agreement.py — native <-> extractor word agreement and the geometry
census (Phase 2.3 cell X, `docs/agent-handoffs/P23-AGREE.md` item 1; plan
§G.2.3 cell X, §H.4).

What this module is for
-----------------------
Phase 2.4's LayoutModel will build structure from geometry that comes from
two sources — native PDF words and PaddleOCR words — and Phase 2.5 will admit
Paddle only where it is MEASURED to add evidence. Neither can be judged
without knowing what agreement between the two sources looks like on
known-good documents (the control sample's calibration) and where they
disagree on the unresolved ones. This module produces those numbers. It
decides nothing.

What it is NOT
--------------
* Not a layout model. The one spatial heuristic here — the "candidate table
  region", the union of the y-bands of lines carrying at least
  `TABLE_REGION_MIN_MONEY` money shapes — is a named, versioned counting
  device for the unmatched-word density, not a structure hypothesis, and it
  is never consumed by anything but this module's own statistics.
* Not a third engine. E4 (cross-engine disagreement below calibration) is
  REVIEW EVIDENCE recorded on the row and nothing more: nothing here returns
  a verdict, a threshold breach, a routing hint or a quality class, and no
  package that makes a decision may read these numbers
  (`tests/test_agreement.py` pins both directions by AST).
* Not a reader. It consumes `ExtractionEvidence` that some reader already
  produced; it never opens a PDF, a raster or a cache.

Frames (the one normalisation)
------------------------------
Both readers place a word in the DISPLAY frame of the page — `evidence/
native.py` transforms PyMuPDF's unrotated boxes by the page's rotation
(Phase 2.2 D4), and a Paddle raster is rendered display-oriented at
`RASTER_VERSION` 2's CropBox — so the two geometries are comparable once
they are in the same UNITS. Everything here is normalised into POINTS:

* a ``pdf_point`` frame is taken as it stands (it is already points);
* a ``pixel`` frame is scaled by its OWN per-axis scales (``scale_x`` /
  ``scale_y``, pixels per point), which `evidence.canonical.PageFrame`
  computes from each axis' raster/page ratio and checks against ``dpi / 72``
  only to within `SCALE_TOLERANCE`. Using one nominal ``72 / dpi`` for both
  axes is wrong by up to that tolerance on a legal frame, which is enough to
  drop a matched pair at the page foot (review closure, MINOR-2).

The two frames are asserted to describe the same rectangle — the same size
within `FRAME_TOLERANCE` (1 %) AND the same page rotation; a disagreement is
RECORDED (`frame_mismatch`) and never stops the measurement — a mismatch is
itself the finding, and the numbers beside it are what makes it readable.

Determinism
-----------
Pure functions of their arguments: no clock, no randomness, no filesystem,
no network (`tests/test_layout_boundary.py` forbids the imports that would
allow any of them). Alignment is greedy by descending IoU with ties broken
by index, so one pair of pages always produces one answer.
"""
from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass

from evidence import (
    POINTS_PER_INCH,
    ExtractionEvidence,
    PageEvidence,
    PageFrame,
    PIXEL,
)
from layout.signals import find_dates, find_money

__all__ = [
    "AGREEMENT_VERSION",
    "FRAME_TOLERANCE",
    "IOU_THRESHOLD",
    "TABLE_REGION_MIN_MONEY",
    "TABLE_REGION_VERSION",
    "TEXT_NORMALISER_VERSION",
    "AGREE_COLUMNS",
    "DisplayWord",
    "DocumentAgreement",
    "PageAgreement",
    "PageGeometryFacts",
    "align",
    "box_iou",
    "display_frame_size",
    "display_words",
    "document_agreement",
    "frames_agree",
    "geometry_census",
    "normalise_text",
    "page_agreement",
    "row_columns",
    "skew_degrees",
]

#: The version every statistic this module publishes is comparable under.
#: Bump it whenever a threshold, a denominator, a normaliser or the alignment
#: rule changes — a number recorded under version N and one recorded under
#: version N+1 are different measurements, and the row carries the version so
#: the two can never be pooled by accident.
AGREEMENT_VERSION = 1

#: Two boxes are the SAME word when their intersection-over-union reaches
#: this. 0.5 is the standard detection-matching threshold and is deliberately
#: loose for text: the two readers box the same glyphs differently (PyMuPDF
#: uses font metrics, an OCR engine uses ink), measured at ~0.70 on the
#: synthetic pair where both sides describe identical text.
IOU_THRESHOLD = 0.5

#: The text normaliser `normalise_text` implements: case-folded,
#: whitespace-collapsed, nothing else. Versioned separately because a change
#: to it (accent folding, punctuation stripping) would move the character
#: agreement without moving the alignment.
TEXT_NORMALISER_VERSION = 1

#: The candidate-table-region heuristic's own version and its one parameter:
#: a derived line whose text carries at least this many money shapes votes
#: its y-band into the region.
TABLE_REGION_VERSION = 1
TABLE_REGION_MIN_MONEY = 2

#: How far the two readers' page rectangles may differ, relatively, before
#: the page is recorded as a frame mismatch. Rasterisers round page
#: dimensions to whole pixels, so a fraction of a pixel over a page is
#: expected; 1 % is generous for that and far too tight for a page/raster
#: mix-up (the same reasoning, and the same figure, as
#: `evidence.canonical.SCALE_TOLERANCE`).
FRAME_TOLERANCE = 0.01

#: The row columns this module projects, in the order the card names them.
AGREE_COLUMNS: tuple[str, ...] = (
    "agree_version", "agree_pages", "agree_matched_native", "agree_matched_paddle",
    "agree_char", "agree_amounts", "agree_dates", "agree_unmatched_table_density",
    "agree_frame_mismatch", "geom_rotation", "geom_skew_deg", "geom_page_size",
)

_WHITESPACE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------

def normalise_text(text: str) -> str:
    """Case-folded and whitespace-collapsed, nothing else
    (`TEXT_NORMALISER_VERSION` 1).

    Deliberately conservative: accents, punctuation and digits are left
    exactly as the reader read them, because the character agreement exists
    to measure what the two readers DISAGREE about and a normaliser that
    erases a difference erases the finding."""
    return _WHITESPACE.sub(" ", str(text)).strip().casefold()


def _matching_characters(left: str, right: str) -> int:
    """The number of characters two strings share, in order — the sum of the
    matching block sizes of a deterministic diff (`autojunk=False`, so the
    heuristic that ignores frequent characters in long strings can never
    make this depend on the input's length)."""
    if left == right:
        return len(left)
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks())


# ---------------------------------------------------------------------------
# frames and the display normalisation
# ---------------------------------------------------------------------------

def display_frame_size(frame: PageFrame) -> tuple[float, float]:
    """The page rectangle this frame describes, in POINTS."""
    if frame.space == PIXEL:
        return float(frame.pdf_width_pt), float(frame.pdf_height_pt)
    return float(frame.width), float(frame.height)


def _points_scale(frame: PageFrame) -> tuple[float, float]:
    """Points per frame unit, PER AXIS: a raster's own ``scale_x`` / ``scale_y``
    (pixels per point) inverted, and 1.0 on a `pdf_point` frame.

    The frame's declared scales are the truth, not ``72 / dpi``. The evidence
    contract computes each axis from that axis' own raster/page ratio and only
    checks it against ``dpi / 72`` to within `SCALE_TOLERANCE`, so a legal
    frame can be non-uniform by up to a per cent — a rasteriser rounding a
    page to whole pixels, for instance. Dividing both axes by one nominal
    ``72 / dpi`` then moves a word at the page foot by several points, which
    is enough to drop a matched pair, and `display_frame_size` (which compares
    the page's declared point dimensions) cannot catch it. Each axis is scaled
    by its own factor (review closure, MINOR-2).
    """
    if frame.space != PIXEL:
        return 1.0, 1.0
    # a pixel frame's per-axis scales are positive by construction (the
    # evidence contract refuses the frame otherwise); `72 / dpi` is the
    # fallback only if that ever stopped being true
    nominal = POINTS_PER_INCH / float(frame.dpi)
    scale_x = 1.0 / float(frame.scale_x) if frame.scale_x else nominal
    scale_y = 1.0 / float(frame.scale_y) if frame.scale_y else nominal
    return scale_x, scale_y


def frames_agree(left: PageFrame, right: PageFrame) -> bool:
    """Do the two frames describe the same rectangle — the same size within
    `FRAME_TOLERANCE` relatively on both axes, AND the same page rotation?

    The rotation is part of the answer (review closure, MINOR-3): on a square
    page, and on any 0-versus-180 disagreement, two readers can differ about
    which way up the page is while their rectangles match exactly. Left
    unchecked that surfaces only as a low matched ratio, which the calibration
    would read as the two engines disagreeing about the TEXT rather than
    about the frame — the one confusion `frame_mismatch` exists to prevent.
    """
    if int(left.rotation_deg) != int(right.rotation_deg):
        return False
    left_size = display_frame_size(left)
    right_size = display_frame_size(right)
    for a, b in zip(left_size, right_size):
        reference = max(abs(a), abs(b))
        if reference <= 0.0 or abs(a - b) > FRAME_TOLERANCE * reference:
            return False
    return True


@dataclass(frozen=True)
class DisplayWord:
    """One word normalised into the display frame, in points."""

    word_id: str
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


def display_words(page: PageEvidence) -> tuple[DisplayWord, ...]:
    """Every word of `page` in the display frame, in points, in the page's
    own word order."""
    scale_x, scale_y = _points_scale(page.frame)
    return tuple(
        DisplayWord(word_id=word.word_id, text=word.text,
                    x0=word.x0 * scale_x, y0=word.y0 * scale_y,
                    x1=word.x1 * scale_x, y1=word.y1 * scale_y)
        for word in page.words
    )


def _display_bands(page: PageEvidence) -> tuple[tuple[float, float], ...]:
    """The y-bands, in points, of the page's derived lines whose text carries
    at least `TABLE_REGION_MIN_MONEY` money shapes."""
    _, scale_y = _points_scale(page.frame)
    bands: list[tuple[float, float]] = []
    for line in page.lines:
        if len(find_money(line.text)) >= TABLE_REGION_MIN_MONEY:
            bands.append((line.y_top * scale_y, line.y_bottom * scale_y))
    return tuple(bands)


# ---------------------------------------------------------------------------
# alignment
# ---------------------------------------------------------------------------

def box_iou(left: tuple[float, float, float, float],
            right: tuple[float, float, float, float]) -> float:
    """Intersection over union of two boxes; 0.0 when they do not overlap."""
    ax0, ay0, ax1, ay1 = left
    bx0, by0, bx1, by1 = right
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    intersection = (ix1 - ix0) * (iy1 - iy0)
    union = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - intersection
    return intersection / union if union > 0.0 else 0.0


def align(left: tuple[DisplayWord, ...], right: tuple[DisplayWord, ...], *,
          threshold: float = IOU_THRESHOLD) -> tuple[tuple[int, int, float], ...]:
    """Greedy one-to-one alignment by descending IoU.

    Every candidate pair whose IoU reaches `threshold` is ranked highest
    first (ties broken by the two indices, so the result is a function of the
    inputs alone); a pair is taken when NEITHER of its boxes has been taken
    already. Each box is therefore used at most ONCE — the property a
    matched-ratio depends on, because a box spent twice would let one reader's
    single word "cover" two of the other's.

    Returns `(left_index, right_index, iou)` triples in the order taken.
    """
    candidates: list[tuple[float, int, int]] = []
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            score = box_iou(a.box, b.box)
            if score >= threshold:
                candidates.append((score, i, j))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    taken_left: set[int] = set()
    taken_right: set[int] = set()
    pairs: list[tuple[int, int, float]] = []
    for score, i, j in candidates:
        if i in taken_left or j in taken_right:
            continue
        taken_left.add(i)
        taken_right.add(j)
        pairs.append((i, j, score))
    return tuple(pairs)


# ---------------------------------------------------------------------------
# parsed shapes (imported from the closed grammars; never re-implemented)
# ---------------------------------------------------------------------------

def _amounts(text: str) -> tuple[int, ...]:
    """The money shapes a word carries, in cents, in text order."""
    return tuple(token.cents for token in find_money(text))


def _dates(text: str) -> tuple[tuple[int | None, int, int], ...]:
    """The date shapes a word carries as `(year, month, day)`, in text
    order. The two readers may spell a date the same way or not; what is
    compared is what the grammar resolves it to."""
    return tuple(token.ymd() for token in find_dates(text))


# ---------------------------------------------------------------------------
# one page
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageAgreement:
    """Every statistic one page's two readings produce. Numbers only: no
    class, no threshold breach, no name of a decision."""

    page_index: int
    native_words: int
    extractor_words: int
    matched_pairs: int
    #: `(native index, extractor index, iou)` in the order the greedy
    #: alignment took them.
    pairs: tuple[tuple[int, int, float], ...]
    matched_native: float | None
    matched_extractor: float | None
    char_agreement: float | None
    matched_characters: int
    compared_characters: int
    amount_pairs: int
    amount_agreements: int
    amount_agreement: float | None
    date_pairs: int
    date_agreements: int
    date_agreement: float | None
    words_in_table_region: int
    unmatched_in_table_region: int
    unmatched_table_density: float | None
    frame_mismatch: bool
    native_size: tuple[float, float]
    extractor_size: tuple[float, float]


def _ratio(numerator: float, denominator: float) -> float | None:
    """A ratio, or `None` when nothing was measured — an unmeasured statistic
    must never read as a measured zero."""
    return (numerator / denominator) if denominator else None


def page_agreement(native: PageEvidence, extractor: PageEvidence) -> PageAgreement:
    """Compare ONE page read two ways.

    Both sides are normalised into the display frame in points, aligned
    greedily by IoU, and then measured: how much of each side matched, how
    many characters the matched pairs share, how many of the matched pairs
    that carry a money (or date) shape resolve to the SAME value, and how
    dense the unmatched words are inside the candidate table region.
    """
    native_display = display_words(native)
    extractor_display = display_words(extractor)
    pairs = align(native_display, extractor_display)

    matched_characters = 0
    compared_characters = 0
    amount_pairs = amount_agreements = 0
    date_pairs = date_agreements = 0
    for i, j, _ in pairs:
        left = normalise_text(native_display[i].text)
        right = normalise_text(extractor_display[j].text)
        matched_characters += _matching_characters(left, right)
        compared_characters += max(len(left), len(right))
        left_amounts, right_amounts = _amounts(left), _amounts(right)
        if left_amounts or right_amounts:
            amount_pairs += 1
            amount_agreements += int(left_amounts == right_amounts)
        left_dates, right_dates = _dates(left), _dates(right)
        if left_dates or right_dates:
            date_pairs += 1
            date_agreements += int(left_dates == right_dates)

    bands = _display_bands(native) + _display_bands(extractor)
    in_region = 0
    unmatched_in_region = 0
    matched_left = {i for i, _, _ in pairs}
    matched_right = {j for _, j, _ in pairs}
    for words, matched in ((native_display, matched_left), (extractor_display, matched_right)):
        for index, word in enumerate(words):
            middle = (word.y0 + word.y1) / 2
            if any(top <= middle <= bottom for top, bottom in bands):
                in_region += 1
                if index not in matched:
                    unmatched_in_region += 1

    return PageAgreement(
        page_index=native.frame.page_index,
        native_words=len(native_display),
        extractor_words=len(extractor_display),
        matched_pairs=len(pairs),
        pairs=pairs,
        matched_native=_ratio(len(pairs), len(native_display)),
        matched_extractor=_ratio(len(pairs), len(extractor_display)),
        char_agreement=_ratio(matched_characters, compared_characters),
        matched_characters=matched_characters,
        compared_characters=compared_characters,
        amount_pairs=amount_pairs,
        amount_agreements=amount_agreements,
        amount_agreement=_ratio(amount_agreements, amount_pairs),
        date_pairs=date_pairs,
        date_agreements=date_agreements,
        date_agreement=_ratio(date_agreements, date_pairs),
        words_in_table_region=in_region,
        unmatched_in_table_region=unmatched_in_region,
        unmatched_table_density=_ratio(unmatched_in_region, in_region),
        frame_mismatch=not frames_agree(native.frame, extractor.frame),
        native_size=display_frame_size(native.frame),
        extractor_size=display_frame_size(extractor.frame),
    )


# ---------------------------------------------------------------------------
# the geometry census
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageGeometryFacts:
    """One page's size, rotation and skew — the census 2.4 will read to know
    what shapes the corpus actually holds."""

    page_index: int
    page_size: tuple[float, float]
    rotation_deg: int
    skew_deg: float | None
    word_count: int
    line_count: int
    measured_lines: int


def skew_degrees(page: PageEvidence) -> float | None:
    """The median angle of the page's derived line baselines, in degrees,
    positive when text DESCENDS to the right (y grows downward).

    Each line with at least two words contributes the least-squares slope of
    its word CENTRES against x — the centre of the axis-aligned hull of a
    rotated box is the rotated centre, so a uniformly rotated page reproduces
    its angle exactly. The median over lines is what a page reports; `None`
    when no line has two words to fit. Deliberately measured from the
    already-derived lines (`evidence.group_lines`, the ONE grouping rule)
    rather than from a grouping of this module's own.

    Two limits, MEASURED (review closure, MINOR-4), because a statistic is
    only as useful as its stated range:

    * between 0.80 and 0.85 degrees on a 500 pt line (20 rows, 12 pt pitch,
      8 pt words) the ONE grouping rule stops separating the rows and
      OVER-MERGES the page into a single line — and the statistic stays EXACT
      through it (0.75 deg -> 20 lines, 0.7500 measured; 0.80 -> 20 lines,
      0.8000; 0.85 -> 1 line, 0.8500; 0.90 -> 1 line, 0.9000; 2.00 -> 1 line,
      2.0000). It is not a fragmentation failure and the angle does not
      drift; the merge point moves with the pitch and the span, so the
      bracket is this fixture's, not a constant of the rule;
    * the page statistic is a plain MEDIAN over line slopes, so a page whose
      blocks are skewed DIFFERENTLY reports an angle no block has (a 0-degree
      and a 5-degree block of equal size report 2.5; two flat rows against
      four skewed report 5.0). One angle per page is the contract; a page
      that needs two is a finding for the milestone that reconstructs it.
    """
    scale_x, scale_y = _points_scale(page.frame)
    by_id = {word.word_id: word for word in page.words}
    slopes: list[float] = []
    for line in page.lines:
        points = [
            (((word.x0 + word.x1) / 2) * scale_x, ((word.y0 + word.y1) / 2) * scale_y)
            for word in (by_id.get(wid) for wid in line.word_ids) if word is not None
        ]
        if len(points) < 2:
            continue
        mean_x = sum(x for x, _ in points) / len(points)
        mean_y = sum(y for _, y in points) / len(points)
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in points)
        denominator = sum((x - mean_x) ** 2 for x, _ in points)
        if denominator <= 0.0:
            continue
        slopes.append(math.degrees(math.atan(numerator / denominator)))
    if not slopes:
        return None
    slopes.sort()
    middle = len(slopes) // 2
    if len(slopes) % 2:
        return slopes[middle]
    return (slopes[middle - 1] + slopes[middle]) / 2


def geometry_census(evidence: ExtractionEvidence) -> tuple[PageGeometryFacts, ...]:
    """Page size (points), rotation (from the frame) and skew, per page."""
    facts: list[PageGeometryFacts] = []
    for page in evidence.pages:
        width, height = display_frame_size(page.frame)
        measured = sum(1 for line in page.lines if len(line.word_ids) >= 2)
        facts.append(PageGeometryFacts(
            page_index=page.frame.page_index,
            page_size=(round(width, 1), round(height, 1)),
            rotation_deg=int(page.frame.rotation_deg),
            skew_deg=skew_degrees(page),
            word_count=len(page.words),
            line_count=len(page.lines),
            measured_lines=measured,
        ))
    return tuple(facts)


# ---------------------------------------------------------------------------
# one document
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentAgreement:
    """The document-level fold. Every ratio is a SUM-OVER-SUM across the
    pages compared — never the mean of per-page ratios, which would weight a
    three-word page like a six-hundred-word one — and every count is a count
    of pages. The geometry census covers EVERY native page, not only the
    compared ones, because a page the extractor never read still has a size
    and a rotation worth knowing."""

    version: int
    native_pages: int
    extractor_pages: int
    pages_compared: int
    pages: tuple[PageAgreement, ...]
    matched_native: float | None
    matched_extractor: float | None
    char_agreement: float | None
    amount_agreement: float | None
    amount_pairs: int
    date_agreement: float | None
    date_pairs: int
    unmatched_table_density: float | None
    frame_mismatch_pages: int
    geometry: tuple[PageGeometryFacts, ...]
    rotations: tuple[int, ...]
    skew_deg: float | None
    page_sizes: tuple[tuple[float, float], ...]


def document_agreement(native: ExtractionEvidence, extractor: ExtractionEvidence) -> DocumentAgreement:
    """Compare two readings of ONE document, page index by page index.

    Only page indices BOTH readings carry are compared (a reading that
    covered fewer pages is a fact the page counts record, never a reason to
    pair a page with a different one). The geometry census is taken from the
    native reading, which is the one that knows the PDF's own rotation.
    """
    extractor_pages = {page.frame.page_index: page for page in extractor.pages}
    compared: list[PageAgreement] = []
    for page in native.pages:
        other = extractor_pages.get(page.frame.page_index)
        if other is not None:
            compared.append(page_agreement(page, other))

    def total(attribute: str) -> int:
        return sum(getattr(page, attribute) for page in compared)

    geometry = geometry_census(native)
    skews = sorted(fact.skew_deg for fact in geometry if fact.skew_deg is not None)
    if skews:
        middle = len(skews) // 2
        skew = skews[middle] if len(skews) % 2 else (skews[middle - 1] + skews[middle]) / 2
    else:
        skew = None

    return DocumentAgreement(
        version=AGREEMENT_VERSION,
        native_pages=len(native.pages),
        extractor_pages=len(extractor.pages),
        pages_compared=len(compared),
        pages=tuple(compared),
        matched_native=_ratio(total("matched_pairs"), total("native_words")),
        matched_extractor=_ratio(total("matched_pairs"), total("extractor_words")),
        char_agreement=_ratio(total("matched_characters"), total("compared_characters")),
        amount_agreement=_ratio(total("amount_agreements"), total("amount_pairs")),
        amount_pairs=total("amount_pairs"),
        date_agreement=_ratio(total("date_agreements"), total("date_pairs")),
        date_pairs=total("date_pairs"),
        unmatched_table_density=_ratio(total("unmatched_in_table_region"), total("words_in_table_region")),
        frame_mismatch_pages=sum(1 for page in compared if page.frame_mismatch),
        geometry=geometry,
        rotations=tuple(sorted({fact.rotation_deg for fact in geometry})),
        skew_deg=skew,
        page_sizes=tuple(sorted({fact.page_size for fact in geometry})),
    )


# ---------------------------------------------------------------------------
# the row projection
# ---------------------------------------------------------------------------

def _number(value: float | None, places: int) -> str:
    """A fixed-precision decimal with its trailing zeros trimmed (never a
    bare integer: `1` and `1.0` read differently in a CSV column of ratios),
    and `""` for an unmeasured statistic. `+ 0.0` so a negative zero — which a
    median of tiny negative slopes produces — never prints as `-0.0`."""
    if value is None:
        return ""
    text = f"{round(float(value), places) + 0.0:.{places}f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def row_columns(agreement: DocumentAgreement | None) -> dict[str, str]:
    """The card's twelve columns as strings, in order.

    `None` — the document does not carry BOTH readings — projects EMPTY
    columns: a half-measured agreement must never read as a measured one.
    """
    if agreement is None:
        return {name: "" for name in AGREE_COLUMNS}
    return {
        "agree_version": str(agreement.version),
        "agree_pages": str(agreement.pages_compared),
        "agree_matched_native": _number(agreement.matched_native, 4),
        "agree_matched_paddle": _number(agreement.matched_extractor, 4),
        "agree_char": _number(agreement.char_agreement, 4),
        "agree_amounts": _number(agreement.amount_agreement, 4),
        "agree_dates": _number(agreement.date_agreement, 4),
        "agree_unmatched_table_density": _number(agreement.unmatched_table_density, 4),
        "agree_frame_mismatch": str(agreement.frame_mismatch_pages),
        "geom_rotation": "|".join(str(value) for value in agreement.rotations),
        "geom_skew_deg": _number(agreement.skew_deg, 2),
        "geom_page_size": "|".join(
            f"{width:.1f}x{height:.1f}" for width, height in agreement.page_sizes
        ),
    }

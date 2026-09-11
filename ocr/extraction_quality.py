"""Extraction quality v2 — MEASURED, VERSIONED, admitted as NOTHING
(Phase 2.3 cell E, `docs/agent-handoffs/P23-EGATE.md`; plan §H.4; Ruling B).

What this module is
-------------------
Pure functions over ONE page of canonical `ExtractionEvidence` (and, where a
metric needs pixels, that page's raster) producing named, closed figures:
how many words there are and how densely they sit; what the extractor's own
recognition scores look like; what share of the numeric tokens parses as a
money figure and what share of the alphabetic tokens is statement furniture
in one of the three languages; how much of the page is garbage tokens; how
regular the boxes are; how much of the page's ink lies outside every word
box; and which way the words read. From those figures, an E-CLASS —
`""` / `E0` / `E1` / `E2` / `E3` / `E5`, exactly the plan's §H.4 vocabulary.

What this module is NOT, by construction
----------------------------------------
**Nothing here is a trigger, a verdict, or a router input.** `ocr/escalation.py`
does not import this module and its `ADMITTED_TRIGGERS` are unchanged
(`tests/test_extraction_quality_admission.py` pins both, by AST and by blob).
The only consumer of these figures in this phase is the REPORT: thirteen
`eq_*` columns on `rows.csv` and the census instrument
(`tools/extraction_quality_census.py`). Ruling B's discipline is labelled
evidence FIRST, review SECOND, admission THIRD — and 2.3 is the first step
only. An extraction-quality criterion becomes a production trigger in 2.5,
from the measured distributions, or never.

The import boundary (pinned by AST in `tests/test_extraction_quality.py`)
------------------------------------------------------------------------
The standard library, `evidence` and `layout.signals`. Nothing else — no
`analysis`, no `ocr.paddle_client`, no `webapp`, no `telemetry`, no image
library. That is why the ink metric takes an already-decoded `RasterGray`
(8-bit grey, row-major) rather than PNG bytes: decoding is the CALLER's job
(the census tool and the tests own an image library; a metrics module that
could import one could import anything). A module that cannot import the
analysis layer cannot be handed a verdict even by accident.

Thresholds, honestly
--------------------
Every threshold is a named constant in ONE table (`THRESHOLDS`), pinned
beside `EXTRACTION_QUALITY_VERSION` by test: a threshold cannot move without
a reviewed version edit (M1). The v1 values are **a-priori labels, not
corpus-fitted numbers** — the mistake `ocr/escalation.py::ALNUM_DENSITY_FLOOR`
documents at length (a round number chosen just below the observed minimum of
the very population it was then used to split) is not repeated here. Each
floor is set where the SHAPE of a page stops being a statement page at all
(a page with numeric tokens and no parseable money figure; a page with
alphabetic tokens and not one word of statement furniture in three
languages), not where a corpus happens to sit. The census measures the real
distributions per configuration; 2.5 recalibrates from them, and a
recalibration is a version bump by construction.

Two figures are deliberately NOT thresholded:

* **the rec-score distribution** (`rec_mean`, `rec_p10`) — a PER-CONFIGURATION
  proxy that must be recalibrated for every engine setup, so it never gates a
  page on its own (§H.4's own warning; `test_the_rec_score_is_a_proxy_and_
  never_sets_a_class_on_its_own`). It is carried, never compared across
  configurations;
* **density** — words per square unit OF THE FRAME'S OWN SPACE, so a pixel
  frame at 300 dpi and a pdf-point frame of the same page produce numbers
  that differ by (300/72)^2. It is a description, and comparing two spaces'
  densities is a mistake this module refuses to make by never classifying on
  it. `frame_space` travels beside it so a consumer cannot make that mistake
  either.

What these metrics cannot say
-----------------------------
The money rate and the lexicon rate are LAYOUT-sensitive as well as
recognition-sensitive: a terms-and-conditions page or an address page of a
genuine statement carries numeric tokens and no money, and a table of figures
carries few words of furniture. The minimum-denominator guards
(`money_rate_min_numeric_tokens`, `lexicon_rate_min_alphabetic_tokens`) keep
a sparse page from being classified on a rate computed from four tokens, but
they do not make either rate a measure of recognition alone. E3 covers
orientation and box regularity; SKEW — §H.4's third E3 criterion — needs a
baseline-angle estimate and belongs with cell X's geometry census, and its
absence here is named rather than implied. These limits are why 2.3 admits
none of this and why the census reports distributions rather than verdicts.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from statistics import fmean, median, pstdev
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from evidence.canonical import ExtractionEvidence, PageEvidence, WordBox
from layout.signals import LEXICONS, fold, money_cents

__all__ = [
    "EQ_ROW_COLUMNS",
    "EXTRACTION_QUALITY_VERSION",
    "E_CLASSES",
    "E_CLASS_PRIORITY",
    "THRESHOLDS",
    "DocumentQuality",
    "OrientationVotes",
    "PageQuality",
    "QualityInputError",
    "RasterGray",
    "document_quality",
    "e_class",
    "eq_row_values",
    "lexicon_vocabulary",
    "page_quality",
]

#: The version of THIS module's metric definitions AND of its threshold
#: table. Bump it in the same commit as any change to either — a figure
#: recorded under v1 must mean exactly what v1 measured, because the census
#: of one configuration and the census of the next are compared only through
#: this number.
EXTRACTION_QUALITY_VERSION = 1

# ---------------------------------------------------------------------------
# the E-class vocabulary (plan §H.4, exactly)
# ---------------------------------------------------------------------------

#: No evidence: the extractor returned no word at all for this page. (A
#: worker error, a raster failure, a timeout or a refusal is the same class,
#: recorded by the wave runner, which is where those facts exist.)
E0_NO_EVIDENCE = "E0"
#: Coverage gap: the share of ink outside every word box clears the ceiling
#: ON A PAGE WHOSE INK SAYS IT IS NOT BLANK — the extractor missed regions.
E1_COVERAGE_GAP = "E1"
#: Recognition quality: the money-shape parse rate over numeric tokens, the
#: lexicon rate over alphabetic tokens, or the garbage-token rate fails its
#: threshold. The rec-score p10 is a proxy here and never a gate.
E2_RECOGNITION = "E2"
#: Frame / orientation: the orientation votes are unanimously against the
#: frame, or box regularity (line-height CV, numeric right-edge residual) is
#: outside its threshold.
E3_FRAME_ORIENTATION = "E3"
#: Truncation / bleed: the EXISTING page-integrity flag, supplied by the
#: caller (`ocr.truncation.PageIntegrity.truncated`). This module does not
#: re-derive it — one truncation rule, in the module that owns it.
E5_TRUNCATION = "E5"

#: The closed vocabulary `e_class` may return. `""` is "no extraction failure
#: on this page", not "not assessed".
E_CLASSES: tuple[str, ...] = ("", E0_NO_EVIDENCE, E1_COVERAGE_GAP, E2_RECOGNITION,
                              E3_FRAME_ORIENTATION, E5_TRUNCATION)

#: When more than one class is true, which one `e_class` REPORTS — the same
#: separation `ocr/escalation.py::TRIGGER_REPORT_PRIORITY` draws between a
#: vocabulary's order and a reporting preference. Most upstream first: a page
#: with no evidence at all is not also a recognition-quality finding. Every
#: class that fired is kept in `PageQuality.classes`, so the precedence
#: reports, it never discards.
E_CLASS_PRIORITY: tuple[str, ...] = (E0_NO_EVIDENCE, E1_COVERAGE_GAP, E2_RECOGNITION,
                                     E3_FRAME_ORIENTATION, E5_TRUNCATION)


class QualityInputError(ValueError):
    """An input this module refuses: a raster that cannot describe its page, a
    grey buffer whose length disagrees with its dimensions. Refused whole —
    never guessed around, in the direction `evidence/canonical.py` set."""


# ---------------------------------------------------------------------------
# THE threshold table (M1: pinned beside the version by test)
# ---------------------------------------------------------------------------

THRESHOLDS: Mapping[str, float] = MappingProxyType({
    # A page with fewer words than this is not classified on its RATES at
    # all: a rate over eight tokens is noise wearing a number's clothes.
    "min_words_for_page_metrics": 12,
    # E2 / money. A FLOOR for an anomaly, not a quality score: a page that
    # carries numeric tokens and effectively no parseable money figure is
    # anomalous on a financial document; a page at 0.4 versus one at 0.5 says
    # nothing, and this threshold deliberately cannot tell them apart.
    "money_rate_floor": 0.02,
    "money_rate_min_numeric_tokens": 20,
    # E2 / lexicon. Likewise a floor: a page with this many alphabetic tokens
    # and NOT ONE word of EN/FR/ES statement furniture is anomalous.
    "lexicon_rate_floor": 0.01,
    "lexicon_rate_min_alphabetic_tokens": 30,
    # The vocabulary keeps lexicon words of at least this many letters, so
    # "of" / "du" / "de" do not make every page look like language.
    "lexicon_min_word_letters": 3,
    # A token counts as ALPHABETIC once it carries this many letters.
    "alphabetic_token_min_letters": 2,
    # E2 / garbage: over-long tokens and repeated-letter runs.
    "garbage_rate_ceiling": 0.05,
    "garbage_token_max_chars": 20,
    "garbage_repeat_run": 4,
    # E3 / box regularity.
    "line_height_cv_ceiling": 0.5,
    "line_height_cv_min_lines": 5,
    "right_edge_residual_ceiling": 1.5,
    "right_edge_residual_min_lines": 3,
    # E1 / ink. A pixel at or below this luminance is ink; a box is padded by
    # this many pixels before the ink inside it is counted (a tight box plus
    # antialiasing puts a rim of ink just outside the glyphs); a page with a
    # smaller ink share than this is BLANK, not a coverage gap.
    "ink_dark_luminance_max": 128,
    "ink_box_pad_px": 1,
    "ink_blank_page_share": 0.0005,
    "ink_outside_boxes_ceiling": 0.35,
    # E3 / orientation. A token of at least this many characters votes; it
    # votes vertical or horizontal only when one side exceeds the other by
    # this factor (a near-square box is indeterminate and does not vote); the
    # votes decide only with at least this many of them, and only when they
    # are UNANIMOUS — §H.4's own word, kept literal in v1.
    "orientation_min_chars": 2,
    "orientation_min_aspect": 1.2,
    "orientation_min_votes": 8,
    "orientation_unanimous_share": 1.0,
    # A raster whose per-axis scales disagree by more than this cannot be a
    # raster OF this page.
    "raster_aspect_tolerance": 0.02,
    # The rec-score percentile carried beside the mean. NOT a threshold on
    # the score — a description of which percentile is reported.
    "rec_p10_percentile": 10,
})


def _t(name: str) -> Any:
    """The ONE way this module reads a threshold. A value spelled anywhere
    but the table above is a fork waiting to happen
    (`test_no_threshold_is_dead_and_none_is_spelled_twice`)."""
    return THRESHOLDS[name]


#: A run of the SAME LETTER, `garbage_repeat_run` long or longer — built from
#: the table so the threshold governs the regex rather than being echoed by
#: it. Letters only: a padded numeric field (`00000`) and a rule of dots are
#: not garbage tokens.
_REPEATED_LETTER_RE = re.compile(r"([^\W\d_])\1{" + str(int(_t("garbage_repeat_run")) - 1) + r",}")
#: Non-letters, for reducing a token to its alphabetic core before a
#: vocabulary lookup (`Balance:` -> `balance`).
_NON_LETTER_RE = re.compile(r"[\W\d_]+")


# ---------------------------------------------------------------------------
# the lexicon vocabulary, DERIVED from layout.signals (never spelled here)
# ---------------------------------------------------------------------------

_VOCABULARY: frozenset[str] | None = None


def lexicon_vocabulary() -> frozenset[str]:
    """Every word of `layout.signals.LEXICONS` with at least
    `lexicon_min_word_letters` letters, folded.

    DERIVED, not copied: no word of statement furniture is spelled in `ocr/`,
    a lexicon edit reaches this metric with nothing to keep in step, and the
    OQ2 no-hardcodes scans over `ocr/` stay clean by construction. The
    vocabulary is small and closed — it is statement FURNITURE, never a
    dictionary — so the lexicon rate it produces is low even on a perfect
    page, which is exactly why its threshold is a floor near zero.
    """
    global _VOCABULARY
    if _VOCABULARY is None:
        minimum = int(_t("lexicon_min_word_letters"))
        words: set[str] = set()
        for by_language in LEXICONS.values():
            for phrases in by_language.values():
                for phrase in phrases:
                    for word in fold(phrase).replace("'", " ").replace(",", " ").split():
                        core = _NON_LETTER_RE.sub("", word)
                        if len(core) >= minimum:
                            words.add(core)
        _VOCABULARY = frozenset(words)
    return _VOCABULARY


# ---------------------------------------------------------------------------
# value types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RasterGray:
    """One page's raster as 8-bit grey, row-major, `width * height` bytes.

    The caller decodes (the census tool and the tests own an image library;
    this module owns none — see the module docstring's import boundary). The
    buffer is validated on construction: a grey buffer whose length disagrees
    with its dimensions describes nothing."""

    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        for name in ("width", "height"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise QualityInputError(f"{name} must be a positive int, got {value!r}")
        if not isinstance(self.pixels, (bytes, bytearray, memoryview)):
            raise QualityInputError("pixels must be a bytes-like grey buffer")
        object.__setattr__(self, "pixels", bytes(self.pixels))
        if len(self.pixels) != self.width * self.height:
            raise QualityInputError(
                f"pixels holds {len(self.pixels)} bytes but {self.width} x {self.height} "
                f"needs {self.width * self.height}"
            )


@dataclass(frozen=True)
class OrientationVotes:
    """How the page's own words read, from their boxes alone.

    A token of at least `orientation_min_chars` characters is wider than it
    is tall when it reads across the page and taller than it is wide when it
    reads down it. `indeterminate` is the honest third answer for a box too
    close to square to say — it votes for neither side and is not in the
    share."""

    horizontal: int
    vertical: int
    indeterminate: int

    @property
    def decided(self) -> int:
        return self.horizontal + self.vertical

    @property
    def vertical_share(self) -> float | None:
        return None if not self.decided else self.vertical / self.decided


@dataclass(frozen=True)
class PageQuality:
    """Every metric of ONE page, plus the classes they fire.

    `None` means NOT MEASURED (no raster was supplied, the extractor gave no
    recognition score, the page has too few lines for a dispersion figure) —
    never zero. A figure a page never measured must not read as a measured
    zero; that distinction is the whole reason the census can be believed."""

    page_index: int
    frame_space: str
    word_count: int
    density: float
    rec_mean: float | None
    rec_p10: float | None
    numeric_tokens: int
    money_rate: float | None
    alphabetic_tokens: int
    lexicon_rate: float | None
    garbage_rate: float
    line_count: int
    line_height_cv: float | None
    right_edge_lines: int
    right_edge_residual: float | None
    ink_share: float | None
    ink_outside_boxes: float | None
    orientation_votes: OrientationVotes | None
    truncated: bool
    classes: tuple[str, ...]

    @property
    def e_class(self) -> str:
        """The first class by `E_CLASS_PRIORITY`, or `""`."""
        return next((name for name in E_CLASS_PRIORITY if name in self.classes), "")


@dataclass(frozen=True)
class DocumentQuality:
    """One document's pages folded to ONE figure per metric.

    The fold NAMES THE WORST PAGE for every rate (the minimum where a low
    value is the defect, the maximum where a high one is), so a document's
    column answers "how bad was its worst page" rather than averaging a
    defect away. The two exceptions are stated where they live:
    `rec_mean` is the mean of the page means (a distribution figure, per
    configuration), and `e_class` is the worst page's class by
    `E_CLASS_PRIORITY`. `None` stays `None`: a metric no page measured is
    unmeasured at the document level too."""

    version: int
    pages: tuple[PageQuality, ...]
    word_count_min: int | None
    density_min: float | None
    rec_mean: float | None
    rec_p10_min: float | None
    money_rate_min: float | None
    lexicon_rate_min: float | None
    garbage_rate_max: float | None
    line_height_cv_max: float | None
    right_edge_residual_max: float | None
    ink_outside_boxes_max: float | None
    orientation_vertical_share_max: float | None
    e_class: str


#: The row columns this module produces, in `ROW_FIELDS` order, each paired
#: with the `DocumentQuality` attribute it carries and the fold that made it.
#: ONE table, so `discovery/runner.py`'s projection has nothing to decide and
#: a column cannot silently change which figure it holds.
EQ_ROW_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("eq_version", "version", "the metric version"),
    ("eq_word_count", "word_count_min", "min over pages"),
    ("eq_density", "density_min", "min over pages"),
    ("eq_rec_mean", "rec_mean", "mean of the page means"),
    ("eq_rec_p10", "rec_p10_min", "min over pages"),
    ("eq_money_rate", "money_rate_min", "min over pages"),
    ("eq_lexicon_rate", "lexicon_rate_min", "min over pages"),
    ("eq_garbage_rate", "garbage_rate_max", "max over pages"),
    ("eq_line_height_cv", "line_height_cv_max", "max over pages"),
    ("eq_right_edge_residual", "right_edge_residual_max", "max over pages"),
    ("eq_ink_outside_boxes", "ink_outside_boxes_max", "max over pages"),
    ("eq_orientation_votes", "orientation_vertical_share_max", "max vertical share over pages"),
    ("eq_class", "e_class", "the worst page's class by E_CLASS_PRIORITY"),
)


# ---------------------------------------------------------------------------
# token shapes
# ---------------------------------------------------------------------------

def _letters(text: str) -> int:
    return sum(1 for ch in text if ch.isalpha())


def _is_numeric_token(text: str) -> bool:
    """A token that carries at least one digit. Deliberately the widest
    honest definition: a garbled figure whose digits were half-substituted is
    still a numeric token, which is precisely the page the money rate is
    meant to notice."""
    return any(ch.isdigit() for ch in text)


def _is_alphabetic_token(text: str) -> bool:
    return _letters(text) >= int(_t("alphabetic_token_min_letters"))


def _is_garbage_token(text: str) -> bool:
    """Over-long, or carrying a repeated-letter run. BOTH halves, always: a
    rule that only measured length reads 0.0 on a page of `lllll` runs
    (P23-EGATE M3)."""
    return len(text) > int(_t("garbage_token_max_chars")) or bool(_REPEATED_LETTER_RE.search(text))


def _percentile(values: Sequence[float], percent: float) -> float:
    """Nearest-rank percentile over a sorted copy — no interpolation, no
    dependency on a statistics implementation's quantile convention."""
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * percent / 100.0))
    return ordered[min(rank, len(ordered)) - 1]


# ---------------------------------------------------------------------------
# geometry metrics
# ---------------------------------------------------------------------------

def _char_width(words: Sequence[WordBox]) -> float | None:
    """The page's own median character width, from its own boxes: the unit
    the right-edge residual is expressed in, so the figure means the same
    thing on a 6pt page and an 11pt one."""
    widths = [(word.x1 - word.x0) / len(word.text) for word in words if word.text]
    return median(widths) if widths else None


def _line_height_cv(page: PageEvidence) -> float | None:
    heights = [line.y_bottom - line.y_top for line in page.lines]
    if len(heights) < 2:
        return None
    mean = fmean(heights)
    return None if mean <= 0 else pstdev(heights) / mean


def _right_edge_residual(page: PageEvidence) -> tuple[int, float | None]:
    """`(lines measured, residual in character widths)`.

    A statement's figures sit in a right-aligned column: the LAST money token
    of each line that has one should share a right edge with its neighbours.
    The residual is the median absolute deviation of those edges from their
    median, divided by the page's own character width — a column of figures
    whose last edge wanders by more than a character or so is not a column."""
    by_id = {word.word_id: word for word in page.words}
    edges: list[float] = []
    for line in page.lines:
        money = [by_id[wid] for wid in line.word_ids
                 if wid in by_id and money_cents(by_id[wid].text) is not None]
        if money:
            edges.append(max(word.x1 for word in money))
    if len(edges) < 2:
        return len(edges), None
    unit = _char_width(page.words)
    if not unit:
        return len(edges), None
    centre = median(edges)
    return len(edges), median([abs(edge - centre) for edge in edges]) / unit


def _orientation_votes(words: Sequence[WordBox]) -> OrientationVotes | None:
    minimum = int(_t("orientation_min_chars"))
    aspect = float(_t("orientation_min_aspect"))
    horizontal = vertical = indeterminate = 0
    for word in words:
        if len(word.text.strip()) < minimum:
            continue
        width, height = word.x1 - word.x0, word.y1 - word.y0
        if width > height * aspect:
            horizontal += 1
        elif height > width * aspect:
            vertical += 1
        else:
            indeterminate += 1
    if not (horizontal or vertical or indeterminate):
        return None
    return OrientationVotes(horizontal=horizontal, vertical=vertical, indeterminate=indeterminate)


# ---------------------------------------------------------------------------
# the ink metric (needs pixels)
# ---------------------------------------------------------------------------

def _merged(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _ink_shares(page: PageEvidence, raster: RasterGray) -> tuple[float, float | None]:
    """`(share of the raster that is ink, share of that ink outside every word
    box)`. The second is `None` when the page carries no ink at all.

    The boxes are SCALED into the raster (a pdf-point frame and a 300-dpi
    raster are the same page in two spaces); a raster whose per-axis scales
    disagree is refused rather than stretched."""
    frame = page.frame
    scale_x = raster.width / float(frame.width)
    scale_y = raster.height / float(frame.height)
    tolerance = float(_t("raster_aspect_tolerance"))
    if abs(scale_x - scale_y) > tolerance * max(scale_x, scale_y):
        raise QualityInputError(
            f"the raster's aspect ({raster.width} x {raster.height}) disagrees with page "
            f"{frame.page_index}'s frame ({frame.width:g} x {frame.height:g}) beyond "
            f"{tolerance:.0%}; it cannot be a raster of this page"
        )
    pad = int(_t("ink_box_pad_px"))
    dark = int(_t("ink_dark_luminance_max"))
    table = bytes(1 if value <= dark else 0 for value in range(256))

    spans_by_row: list[list[tuple[int, int]]] = [[] for _ in range(raster.height)]
    for word in page.words:
        x0 = max(0, int(math.floor(word.x0 * scale_x)) - pad)
        x1 = min(raster.width, int(math.ceil(word.x1 * scale_x)) + pad)
        y0 = max(0, int(math.floor(word.y0 * scale_y)) - pad)
        y1 = min(raster.height, int(math.ceil(word.y1 * scale_y)) + pad)
        if x1 <= x0 or y1 <= y0:
            continue
        for y in range(y0, y1):
            spans_by_row[y].append((x0, x1))

    pixels = raster.pixels
    total = inside = 0
    for y in range(raster.height):
        row = pixels[y * raster.width:(y + 1) * raster.width].translate(table)
        count = row.count(1)
        if not count:
            continue
        total += count
        for start, end in _merged(spans_by_row[y]):
            inside += row.count(1, start, end)
    share = total / float(raster.width * raster.height)
    return share, (None if not total else (total - inside) / total)


# ---------------------------------------------------------------------------
# the page metric set and its classes
# ---------------------------------------------------------------------------

def page_quality(page: PageEvidence, *, raster: RasterGray | None = None,
                 truncated: bool = False) -> PageQuality:
    """Every metric of one page, and the E-classes they fire.

    `raster` is that page's own pixels (`None` -> the ink metrics are
    unmeasured, which is the production case: a production partition keeps
    only `raster_sha256`). `truncated` is the EXISTING page-integrity flag —
    supplied, never re-derived here."""
    words = page.words
    frame = page.frame
    word_count = len(words)
    area = float(frame.width) * float(frame.height)

    scores = [float(word.confidence) for word in words if word.confidence is not None]
    rec_mean = fmean(scores) if scores else None
    rec_p10 = _percentile(scores, float(_t("rec_p10_percentile"))) if scores else None

    numeric = [word.text for word in words if _is_numeric_token(word.text)]
    alphabetic = [word.text for word in words if _is_alphabetic_token(word.text)]
    vocabulary = lexicon_vocabulary()
    money_rate = (
        None if not numeric
        else sum(1 for text in numeric if money_cents(text) is not None) / len(numeric)
    )
    lexicon_rate = (
        None if not alphabetic
        else sum(1 for text in alphabetic if _NON_LETTER_RE.sub("", fold(text)) in vocabulary) / len(alphabetic)
    )
    garbage_rate = (
        0.0 if not word_count
        else sum(1 for word in words if _is_garbage_token(word.text)) / word_count
    )

    line_height_cv = _line_height_cv(page)
    right_edge_lines, right_edge_residual = _right_edge_residual(page)
    votes = _orientation_votes(words)
    ink_share, ink_outside = (None, None) if raster is None else _ink_shares(page, raster)

    quality = PageQuality(
        page_index=frame.page_index,
        frame_space=frame.space,
        word_count=word_count,
        density=word_count / area if area else 0.0,
        rec_mean=rec_mean,
        rec_p10=rec_p10,
        numeric_tokens=len(numeric),
        money_rate=money_rate,
        alphabetic_tokens=len(alphabetic),
        lexicon_rate=lexicon_rate,
        garbage_rate=garbage_rate,
        line_count=len(page.lines),
        line_height_cv=line_height_cv,
        right_edge_lines=right_edge_lines,
        right_edge_residual=right_edge_residual,
        ink_share=ink_share,
        ink_outside_boxes=ink_outside,
        orientation_votes=votes,
        truncated=bool(truncated),
        classes=(),
    )
    return _with_classes(quality)


def _with_classes(quality: PageQuality) -> PageQuality:
    """The §H.4 rules, each reading only figures the page measured.

    A metric that is `None` (unmeasured) never fires a class, and a rate
    whose denominator is below its minimum is MEASURED but not CLASSIFIED —
    measurement and classification are separate questions, and conflating
    them is how a four-token page acquires a verdict."""
    fired: list[str] = []
    enough_words = quality.word_count >= int(_t("min_words_for_page_metrics"))

    if quality.word_count == 0:
        fired.append(E0_NO_EVIDENCE)

    if (
        quality.ink_outside_boxes is not None
        and quality.ink_share is not None
        and quality.ink_share >= float(_t("ink_blank_page_share"))
        and quality.ink_outside_boxes > float(_t("ink_outside_boxes_ceiling"))
    ):
        fired.append(E1_COVERAGE_GAP)

    recognition = enough_words and (
        (
            quality.money_rate is not None
            and quality.numeric_tokens >= int(_t("money_rate_min_numeric_tokens"))
            and quality.money_rate < float(_t("money_rate_floor"))
        )
        or (
            quality.lexicon_rate is not None
            and quality.alphabetic_tokens >= int(_t("lexicon_rate_min_alphabetic_tokens"))
            and quality.lexicon_rate < float(_t("lexicon_rate_floor"))
        )
        or quality.garbage_rate > float(_t("garbage_rate_ceiling"))
    )
    if recognition:
        fired.append(E2_RECOGNITION)

    votes = quality.orientation_votes
    frame_or_boxes = (
        (
            votes is not None
            and votes.decided >= int(_t("orientation_min_votes"))
            and votes.vertical_share is not None
            and votes.vertical_share >= float(_t("orientation_unanimous_share"))
        )
        or (
            quality.line_height_cv is not None
            and quality.line_count >= int(_t("line_height_cv_min_lines"))
            and quality.line_height_cv > float(_t("line_height_cv_ceiling"))
        )
        or (
            quality.right_edge_residual is not None
            and quality.right_edge_lines >= int(_t("right_edge_residual_min_lines"))
            and quality.right_edge_residual > float(_t("right_edge_residual_ceiling"))
        )
    )
    if frame_or_boxes:
        fired.append(E3_FRAME_ORIENTATION)

    if quality.truncated:
        fired.append(E5_TRUNCATION)

    ordered = tuple(name for name in E_CLASS_PRIORITY if name in fired)
    return replace(quality, classes=ordered)


def e_class(subject: PageEvidence | PageQuality, *, raster: RasterGray | None = None,
            truncated: bool = False) -> str:
    """The page's E-class — `""` when nothing fired. Accepts a page or its
    already-computed `PageQuality` (the census computes the metrics once)."""
    if isinstance(subject, PageQuality):
        return subject.e_class
    return page_quality(subject, raster=raster, truncated=truncated).e_class


# ---------------------------------------------------------------------------
# the document fold
# ---------------------------------------------------------------------------

def _fold(values: Iterable[Any], how) -> Any:
    present = [value for value in values if value is not None]
    return how(present) if present else None


def document_quality(evidence: ExtractionEvidence, *,
                     rasters: Mapping[int, RasterGray] | None = None,
                     truncated_pages: Iterable[int] = ()) -> DocumentQuality:
    """Every page measured, then folded once per column (see `DocumentQuality`
    and `EQ_ROW_COLUMNS` for the fold each column carries)."""
    flagged = {int(index) for index in truncated_pages}
    pages = tuple(
        page_quality(
            page,
            raster=None if rasters is None else rasters.get(page.frame.page_index),
            truncated=page.frame.page_index in flagged,
        )
        for page in evidence.pages
    )
    worst = ""
    for name in E_CLASS_PRIORITY:
        if any(name in page.classes for page in pages):
            worst = name
            break
    return DocumentQuality(
        version=EXTRACTION_QUALITY_VERSION,
        pages=pages,
        word_count_min=_fold((page.word_count for page in pages), min),
        density_min=_fold((page.density for page in pages), min),
        rec_mean=_fold((page.rec_mean for page in pages), fmean),
        rec_p10_min=_fold((page.rec_p10 for page in pages), min),
        money_rate_min=_fold((page.money_rate for page in pages), min),
        lexicon_rate_min=_fold((page.lexicon_rate for page in pages), min),
        garbage_rate_max=_fold((page.garbage_rate for page in pages), max),
        line_height_cv_max=_fold((page.line_height_cv for page in pages), max),
        right_edge_residual_max=_fold((page.right_edge_residual for page in pages), max),
        ink_outside_boxes_max=_fold((page.ink_outside_boxes for page in pages), max),
        orientation_vertical_share_max=_fold(
            (None if page.orientation_votes is None else page.orientation_votes.vertical_share
             for page in pages), max,
        ),
        e_class=worst,
    )


def _rendered(value: Any) -> str:
    """A row cell. `None` -> `""` (unmeasured is not zero); a float is rounded
    to six places so a column is stable across platforms and re-runs."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(round(value, 6))
    return str(value)


def eq_row_values(evidence: ExtractionEvidence, *,
                  rasters: Mapping[int, RasterGray] | None = None,
                  truncated_pages: Iterable[int] = ()) -> dict[str, str]:
    """The thirteen `eq_*` row cells for one document's evidence, as strings.

    The ONE place a row cell is produced, so the runner's projection has
    nothing to decide and the census and the row cannot disagree about what a
    column holds."""
    quality = document_quality(evidence, rasters=rasters, truncated_pages=truncated_pages)
    return {column: _rendered(getattr(quality, attribute)) for column, attribute, _ in EQ_ROW_COLUMNS}

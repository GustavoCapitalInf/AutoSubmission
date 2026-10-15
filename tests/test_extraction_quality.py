"""Phase 2.3 cell E (`docs/agent-handoffs/P23-EGATE.md`): extraction-quality
metrics v2 — MEASURED, VERSIONED, and admitted as NOTHING.

What this file proves, in the order the card words it:

1. the threshold table and `EXTRACTION_QUALITY_VERSION` are pinned TOGETHER,
   so a threshold cannot move without a reviewed version edit (M1);
2. every metric moves on the synthetic defect page built for it, and no
   other E-class fires there (the page -> metric -> value -> class table the
   W3 section carries);
3. the rec-score distribution is a per-configuration PROXY and never sets a
   class on its own (M5);
4. the money rate's denominator is the NUMERIC tokens and the lexicon rate's
   is the ALPHABETIC tokens (M2), the garbage rule counts repeated letters as
   well as over-long tokens (M3), and the ink metric measures the ink OUTSIDE
   the boxes (M4);
5. the module's import set is the standard library, `evidence` and
   `layout.signals` — by AST, not by discipline (M10).

Every page here is synthetic: rendered from literal strings by
`tests/paddle_synthetic.py`, dated in 2031, never derived from a document.
"""
from __future__ import annotations

import ast
from pathlib import Path
from statistics import fmean

import pytest

from evidence.canonical import ExtractionEvidence, PageEvidence, PageFrame, WordBox, word_id
from evidence.native import NATIVE_EXTRACTOR_ID
from ocr.extraction_quality import (
    CALIBRATION_DIGESTS,
    EQ_ROW_COLUMNS,
    NON_GARBAGE_SHAPES,
    E_CLASSES,
    E_CLASS_PRIORITY,
    EXTRACTION_QUALITY_VERSION,
    THRESHOLDS,
    QualityInputError,
    RasterGray,
    document_quality,
    e_class,
    eq_row_values,
    _is_garbage_token,
    calibration_digest,
    lexicon_vocabulary,
    non_garbage_shape,
    page_quality,
)
from tests.paddle_synthetic import (
    FURNITURE_TOKENS,
    build_blank_page,
    build_column_page,
    build_garbage_token_page,
    build_ledger_page,
    build_noise_page,
    build_repeated_letter_page,
    build_sparse_furniture_page,
    keep_first_lines,
    rotate_page_90,
    substitute_digit_glyphs,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "ocr" / "extraction_quality.py"

#: Every defect page is grown from a ledger this many rows long, so the
#: denominators the classification guards require (numeric tokens, alphabetic
#: tokens) are met on the CLEAN page too — a fixture that cannot reach a
#: metric's minimum denominator proves nothing about that metric.
ROWS = 20


# ---------------------------------------------------------------------------
# helpers: a SyntheticPage -> one PageEvidence page, in the page's own points
# ---------------------------------------------------------------------------

def evidence_page(page, *, page_index: int = 0, confidence: float | None = None) -> PageEvidence:
    words = []
    for line_index, line in enumerate(page.lines):
        for word in line.words:
            words.append(WordBox(
                word_id=word_id(page_index, line_index, len(words)), page_index=page_index,
                text=word.text, x0=word.x0, y0=word.y0, x1=word.x1, y1=word.y1,
                confidence=confidence, line_ref=line_index,
            ))
    frame = PageFrame.pdf_points(page_index=page_index, width_pt=page.width_pt, height_pt=page.height_pt)
    return PageEvidence(frame=frame, words=tuple(words))


def rendered_raster(page, *, dpi: int = 100) -> RasterGray:
    """The page's own pixels, through the SAME rasteriser the Paddle rung uses
    (`ocr.rasterize`, CropBox, RASTER_VERSION 2), reduced to 8-bit grey."""
    from ocr.rasterize import rasterize_pdf
    from tests.paddle_synthetic import render_native_pdf

    image = rasterize_pdf(render_native_pdf(page), dpi=dpi)[0].convert("L")
    return RasterGray(width=image.width, height=image.height, pixels=image.tobytes())


def grey(width: int, height: int, dark: list[tuple[int, int]]) -> RasterGray:
    """A hand-made raster: white everywhere except the named pixels. Exact,
    fast, and independent of any font or rasteriser."""
    pixels = bytearray(b"\xff" * (width * height))
    for x, y in dark:
        pixels[y * width + x] = 0
    return RasterGray(width=width, height=height, pixels=bytes(pixels))


def block(width: int, height: int, x0: int, y0: int, x1: int, y1: int) -> RasterGray:
    return grey(width, height, [(x, y) for y in range(y0, y1) for x in range(x0, x1)])


def one_word_page(*, width: float, height: float, box: tuple[float, float, float, float],
                  text: str = "SYNTHETIC") -> PageEvidence:
    x0, y0, x1, y1 = box
    return PageEvidence(
        frame=PageFrame.pdf_points(page_index=0, width_pt=width, height_pt=height),
        words=(WordBox(word_id=word_id(0, 0, 0), page_index=0, text=text,
                       x0=x0, y0=y0, x1=x1, y1=y1, line_ref=0),),
    )


# ---------------------------------------------------------------------------
# 1. the version and the threshold table are ONE pinned edit (M1)
# ---------------------------------------------------------------------------

def test_the_threshold_table_and_the_version_are_pinned_together():
    """M1's killer. Every threshold this module classifies on lives in ONE
    table, and the table is pinned HERE beside the version number: a
    threshold cannot move without this literal moving, and this literal
    cannot move without a reviewer reading the version line next to it.

    The values are v1 A-PRIORI labels, not corpus-fitted numbers — see the
    module docstring. 2.5 recalibrates them PER CONFIGURATION from the
    census; that recalibration is a version bump by construction.
    """
    assert EXTRACTION_QUALITY_VERSION == 2
    assert dict(THRESHOLDS) == {
        "min_words_for_page_metrics": 12,
        "money_rate_floor": 0.02,
        "money_rate_min_numeric_tokens": 20,
        "lexicon_rate_floor": 0.01,
        "lexicon_rate_min_alphabetic_tokens": 30,
        "lexicon_min_word_letters": 3,
        "alphabetic_token_min_letters": 2,
        "garbage_rate_ceiling": 0.05,
        "garbage_rate_min_tokens": 30,
        "garbage_token_max_chars": 20,
        "garbage_repeat_run": 4,
        "line_height_cv_ceiling": 0.5,
        "line_height_cv_min_lines": 5,
        "right_edge_residual_ceiling": 1.5,
        "right_edge_residual_min_lines": 3,
        "right_edge_cluster_tolerance": 3.0,
        "ink_dark_luminance_max": 128,
        "ink_box_pad_px": 1,
        "ink_blank_page_share": 0.0005,
        "ink_outside_boxes_ceiling": 0.35,
        "orientation_min_chars": 2,
        "orientation_min_aspect": 1.2,
        "orientation_min_votes": 8,
        "orientation_majority_share": 0.8,
        "frame_square_aspect_tolerance": 0.02,
        "raster_aspect_tolerance": 0.02,
        "rec_p10_percentile": 10,
    }


def test_no_threshold_is_dead_and_none_is_spelled_twice():
    """A table nothing reads is documentation. Every key is looked up in the
    module's own source, and no numeric literal from the table is spelled
    again outside it (which is how a threshold silently forks)."""
    source = MODULE.read_text(encoding="utf-8")
    body = source.split("THRESHOLDS: Mapping[str, float] = MappingProxyType({", 1)[1]
    table, rest = body.split("})", 1)
    for name in THRESHOLDS:
        assert f'_t("{name}")' in rest, f"threshold {name} is never read"
    for name, value in THRESHOLDS.items():
        assert f'"{name}": {value!r}' in table, f"threshold {name} is not in the one table"


def test_e_class_reads_a_page_or_its_already_measured_quality():
    page = evidence_page(build_ledger_page(ROWS))
    assert e_class(page) == ""
    assert e_class(page, truncated=True) == "E5"
    assert e_class(page_quality(page, truncated=True)) == "E5"
    assert e_class(page) in E_CLASSES


def test_the_e_class_vocabulary_is_closed_and_ordered():
    assert E_CLASSES == ("", "E0", "E1", "E2", "E3", "E5")
    assert E_CLASS_PRIORITY == ("E0", "E1", "E2", "E3", "E5")
    assert set(E_CLASS_PRIORITY) == set(E_CLASSES) - {""}


# ---------------------------------------------------------------------------
# 2. the clean page: every metric measured, no class
# ---------------------------------------------------------------------------

def test_a_clean_ledger_page_fires_no_class_and_measures_every_metric():
    quality = page_quality(evidence_page(build_ledger_page(ROWS)))
    assert quality.e_class == "" and quality.classes == ()
    assert quality.word_count == 6 + ROWS * 6
    assert quality.density == pytest.approx(quality.word_count / (612.0 * 792.0))
    # the denominators the classification guards need are met on the clean page
    assert quality.numeric_tokens >= THRESHOLDS["money_rate_min_numeric_tokens"]
    assert quality.alphabetic_tokens >= THRESHOLDS["lexicon_rate_min_alphabetic_tokens"]
    assert quality.money_rate > THRESHOLDS["money_rate_floor"]
    assert quality.lexicon_rate > THRESHOLDS["lexicon_rate_floor"]
    assert quality.garbage_rate == 0.0
    assert quality.line_height_cv == pytest.approx(0.0)
    assert quality.right_edge_residual == pytest.approx(0.0)
    # no raster was supplied, so the ink metrics are UNMEASURED, not zero
    assert quality.ink_share is None and quality.ink_outside_boxes is None
    # no confidence was supplied, so the rec-score figures are unmeasured too
    assert quality.rec_mean is None and quality.rec_p10 is None
    assert quality.orientation_votes is not None
    assert quality.orientation_votes.vertical == 0
    assert quality.frame_space == "pdf_point"


def test_a_clean_page_with_a_raster_puts_almost_all_of_its_ink_inside_its_boxes():
    page = build_ledger_page(ROWS)
    quality = page_quality(evidence_page(page), raster=rendered_raster(page))
    assert quality.ink_share > THRESHOLDS["ink_blank_page_share"]
    assert quality.ink_outside_boxes < THRESHOLDS["ink_outside_boxes_ceiling"]
    assert quality.e_class == ""


# ---------------------------------------------------------------------------
# 2b. one defect page per metric — the card's table (item 4)
# ---------------------------------------------------------------------------

def test_a_blank_page_is_E0_and_nothing_else():
    page = build_blank_page()
    quality = page_quality(evidence_page(page), raster=rendered_raster(page))
    assert quality.word_count == 0
    assert quality.classes == ("E0",) and quality.e_class == "E0"
    # a blank sheet is not a coverage gap: there is no ink to be outside a box
    assert quality.ink_outside_boxes is None


def test_a_partly_covered_page_is_E1_and_the_ink_it_measures_is_the_ink_OUTSIDE(
):
    """M4's killer. The evidence covers the top six lines of a 22-line page,
    so the share OUTSIDE the boxes clears the ceiling while the share INSIDE
    them does not: a gate that measured the inside would not fire here."""
    page = build_ledger_page(ROWS)
    quality = page_quality(evidence_page(keep_first_lines(page, 6)), raster=rendered_raster(page))
    assert quality.ink_outside_boxes > THRESHOLDS["ink_outside_boxes_ceiling"]
    inside = 1.0 - quality.ink_outside_boxes
    assert inside < THRESHOLDS["ink_outside_boxes_ceiling"]
    assert quality.classes == ("E1",) and quality.e_class == "E1"


def test_a_90_degree_page_is_E3_on_unanimous_orientation_votes():
    page = rotate_page_90(build_ledger_page(ROWS))
    quality = page_quality(evidence_page(page))
    votes = quality.orientation_votes
    assert votes is not None and votes.horizontal == 0 and votes.vertical >= THRESHOLDS["orientation_min_votes"]
    assert votes.vertical_share == 1.0
    # the text is untouched: every recognition metric reads what the clean page reads
    assert quality.money_rate == page_quality(evidence_page(build_ledger_page(ROWS))).money_rate
    assert quality.e_class == "E3" and quality.classes[0] == "E3"


def test_a_noise_page_is_E2_on_the_lexicon_rate():
    quality = page_quality(evidence_page(build_noise_page()))
    assert quality.alphabetic_tokens >= THRESHOLDS["lexicon_rate_min_alphabetic_tokens"]
    assert quality.lexicon_rate == 0.0
    assert quality.garbage_rate == 0.0
    assert quality.line_height_cv == pytest.approx(0.0)
    assert quality.classes == ("E2",) and quality.e_class == "E2"


def test_a_digit_glyph_substituted_page_is_E2_on_the_money_rate():
    page = substitute_digit_glyphs(build_ledger_page(ROWS))
    quality = page_quality(evidence_page(page))
    assert quality.numeric_tokens >= THRESHOLDS["money_rate_min_numeric_tokens"]
    assert quality.money_rate == 0.0
    # the page still reads as language and its boxes are still a ledger's
    assert quality.lexicon_rate > THRESHOLDS["lexicon_rate_floor"]
    assert quality.garbage_rate == 0.0
    assert quality.classes == ("E2",) and quality.e_class == "E2"


def test_a_garbage_token_page_is_E2_on_over_long_tokens():
    quality = page_quality(evidence_page(build_garbage_token_page()))
    assert quality.garbage_rate > THRESHOLDS["garbage_rate_ceiling"]
    assert quality.money_rate > THRESHOLDS["money_rate_floor"]
    assert quality.lexicon_rate > THRESHOLDS["lexicon_rate_floor"]
    assert quality.classes == ("E2",) and quality.e_class == "E2"


def test_a_repeated_letter_page_is_E2_although_every_token_is_short():
    """M3's killer: a garbage rule that only measured token LENGTH reads 0.0
    on this page, because no token on it reaches the 20-character bound."""
    page = build_repeated_letter_page()
    longest = max(len(word.text) for line in page.lines for word in line.words)
    assert longest <= THRESHOLDS["garbage_token_max_chars"]
    quality = page_quality(evidence_page(page))
    assert quality.garbage_rate > THRESHOLDS["garbage_rate_ceiling"]
    assert quality.classes == ("E2",) and quality.e_class == "E2"


def test_a_truncated_page_is_E5_from_the_existing_page_integrity_flag():
    quality = page_quality(evidence_page(build_ledger_page(ROWS)), truncated=True)
    assert quality.truncated is True
    assert quality.classes == ("E5",) and quality.e_class == "E5"


# ---------------------------------------------------------------------------
# 3. the denominators, the rec-score proxy, the precedence (M2, M3, M5)
# ---------------------------------------------------------------------------

def test_the_money_rate_denominator_is_the_numeric_tokens_not_every_token():
    """M2's killer. On the clean ledger every row prints a date, a row
    number, an amount and a balance: 4 * ROWS tokens carry a digit and
    exactly half of them parse as money. A rate taken over EVERY token would
    read 40/166, not 40/80 — the exact numbers are asserted, because a
    denominator defect does not move a threshold, it moves a number."""
    quality = page_quality(evidence_page(build_ledger_page(ROWS)))
    assert quality.numeric_tokens == 4 * ROWS
    assert quality.numeric_tokens < quality.word_count
    assert quality.money_rate == pytest.approx((2 * ROWS) / (4 * ROWS))


def test_the_lexicon_rate_denominator_is_the_alphabetic_tokens():
    """The same argument for the lexicon rate: the denominator is the tokens
    that carry letters, never every token on the page."""
    quality = page_quality(evidence_page(build_ledger_page(ROWS)))
    assert quality.alphabetic_tokens == 6 + 2 * ROWS
    assert quality.alphabetic_tokens < quality.word_count
    # Of the page's seven distinct alphabetic tokens, four are statement
    # furniture in `layout.signals` (STATEMENT, DATE, AMOUNT, BALANCE) and
    # three are not (SYNTHETIC, DESCRIPTION, ROW) — and the four sit in the
    # header, so they are four occurrences, not four per row.
    vocabulary = lexicon_vocabulary()
    assert {"statement", "date", "amount", "balance"} <= vocabulary
    assert not ({"synthetic", "description", "row"} & vocabulary)
    assert quality.lexicon_rate == pytest.approx(4 / (6 + 2 * ROWS))


def test_the_lexicon_vocabulary_is_derived_from_layout_signals_and_is_not_spelled_here():
    """The vocabulary is a projection of `layout.signals.LEXICONS`, so a
    lexicon edit reaches this metric with no second list to maintain — and no
    word of statement furniture is hardcoded in `ocr/`."""
    from layout.signals import LEXICONS

    vocabulary = lexicon_vocabulary()
    assert "balance" in vocabulary and "statement" in vocabulary
    assert "solde" in vocabulary and "saldo" in vocabulary       # fr / es carried too
    every = {
        word
        for by_language in LEXICONS.values()
        for phrases in by_language.values()
        for phrase in phrases
        for word in phrase.replace("'", " ").split()
    }
    assert vocabulary <= {word.lower() for word in every} | {w.lower() for w in vocabulary}
    assert all(len(word) >= THRESHOLDS["lexicon_min_word_letters"] for word in vocabulary)


def test_the_rec_score_is_a_proxy_and_never_sets_a_class_on_its_own():
    """M5's killer. Every word on a clean page carries the WORST possible
    recognition score; the page still fires no class, and no threshold in the
    table names the rec-score distribution at all."""
    quality = page_quality(evidence_page(build_ledger_page(ROWS), confidence=0.01))
    assert quality.rec_mean == pytest.approx(0.01) and quality.rec_p10 == pytest.approx(0.01)
    assert quality.classes == () and quality.e_class == ""
    # and it cannot reach a class by any path: the ONE function that decides
    # which classes fire never names a recognition score. `rec_p10_percentile`
    # is in the table because it says WHICH percentile is reported, not
    # because anything is gated on the score.
    decider = next(
        node for node in ast.walk(ast.parse(MODULE.read_text(encoding="utf-8")))
        if isinstance(node, ast.FunctionDef) and node.name == "_with_classes"
    )
    named = {node.attr for node in ast.walk(decider) if isinstance(node, ast.Attribute)}
    named |= {node.value for node in ast.walk(decider) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert not {name for name in named if isinstance(name, str) and "rec" in name.split("_")}


def test_the_rec_score_figures_are_the_mean_and_the_nearest_rank_p10():
    page = build_ledger_page(2)
    evidence = evidence_page(page)
    scores = [round(0.1 * (index % 10), 3) for index in range(len(evidence.words))]
    words = tuple(
        WordBox(word_id=word.word_id, page_index=word.page_index, text=word.text,
                x0=word.x0, y0=word.y0, x1=word.x1, y1=word.y1,
                confidence=score, line_ref=word.line_ref)
        for word, score in zip(evidence.words, scores)
    )
    quality = page_quality(PageEvidence(frame=evidence.frame, words=words))
    ordered = sorted(scores)
    rank = max(1, -(-len(ordered) * 10 // 100))
    assert quality.rec_p10 == pytest.approx(ordered[rank - 1])
    assert quality.rec_mean == pytest.approx(sum(scores) / len(scores))


def test_when_several_classes_fire_the_e_class_is_the_first_by_priority():
    """A blank page over an inked sheet: E0 (no evidence) and E1 (all of the
    ink is outside a box, since there are no boxes) are BOTH true, and
    `e_class` reports the most upstream one while `classes` keeps both."""
    evidence = PageEvidence(
        frame=PageFrame.pdf_points(page_index=0, width_pt=100.0, height_pt=100.0), words=(),
    )
    quality = page_quality(evidence, raster=block(100, 100, 10, 10, 30, 30))
    assert quality.classes == ("E0", "E1")
    assert quality.e_class == "E0"


# ---------------------------------------------------------------------------
# the ink metric, exactly (hand-made rasters: no font, no rasteriser)
# ---------------------------------------------------------------------------

def test_ink_inside_a_word_box_is_not_outside_it():
    page = one_word_page(width=100.0, height=100.0, box=(10.0, 10.0, 30.0, 30.0))
    quality = page_quality(page, raster=block(100, 100, 12, 12, 28, 28))
    assert quality.ink_outside_boxes == 0.0
    assert quality.ink_share == pytest.approx(16 * 16 / 10_000)
    assert quality.classes == ()


def test_ink_far_from_every_word_box_is_a_coverage_gap():
    page = one_word_page(width=100.0, height=100.0, box=(10.0, 10.0, 30.0, 30.0))
    quality = page_quality(page, raster=block(100, 100, 60, 60, 80, 80))
    assert quality.ink_outside_boxes == 1.0
    assert quality.classes == ("E1",)


def test_a_page_with_a_speck_of_ink_is_blank_not_a_coverage_gap():
    """The E1 guard §H.4 words: the share of ink outside the boxes counts
    only ON A PAGE WHOSE INK COVERAGE SAYS IT IS NOT BLANK. Two dark pixels
    in ten thousand is a blank sheet with a speck, not a missed region."""
    page = one_word_page(width=100.0, height=100.0, box=(10.0, 10.0, 30.0, 30.0))
    quality = page_quality(page, raster=grey(100, 100, [(90, 90), (91, 91)]))
    assert quality.ink_outside_boxes == 1.0
    assert quality.ink_share < THRESHOLDS["ink_blank_page_share"]
    assert quality.classes == ()


def test_the_ink_metric_scales_the_boxes_into_the_raster():
    """The frame is in points and the raster is in pixels: the boxes are
    scaled, never compared raw."""
    page = one_word_page(width=100.0, height=100.0, box=(10.0, 10.0, 30.0, 30.0))
    quality = page_quality(page, raster=block(200, 200, 24, 24, 56, 56))
    assert quality.ink_outside_boxes == 0.0


def test_a_raster_whose_aspect_disagrees_with_the_frame_is_refused():
    page = one_word_page(width=100.0, height=100.0, box=(10.0, 10.0, 30.0, 30.0))
    with pytest.raises(QualityInputError, match="aspect"):
        page_quality(page, raster=block(200, 100, 10, 10, 20, 20))


def test_a_raster_whose_pixel_count_disagrees_with_its_dimensions_is_refused():
    with pytest.raises(QualityInputError, match="pixels"):
        RasterGray(width=10, height=10, pixels=b"\xff" * 99)


# ---------------------------------------------------------------------------
# 4b. the row projection: extractor evidence only (M8), at the row's one exit
# ---------------------------------------------------------------------------

class _Read:
    """A `StatementMarkdown`-shaped stand-in carrying whichever evidence the
    case is about. The projection reads exactly three attributes."""

    def __init__(self, *, evidence=None, native_evidence=None, truncated_pages=()):
        self.evidence = evidence
        self.native_evidence = native_evidence
        self.truncated_pages = list(truncated_pages)


def _bare_row():
    from discovery.runner import DocumentRow

    return DocumentRow(relative_path="F/a.pdf", folder_label="F", content_sha256="A" * 64, byte_size=1)


def _project(document):
    from discovery.runner import DiscoveryRunner

    row = _bare_row()
    DiscoveryRunner._project_extraction_quality(row, {"document": document})
    return row


def _eq_cells(row) -> dict[str, str]:
    return {column: getattr(row, column) for column, _, _ in EQ_ROW_COLUMNS}


def test_the_projection_fills_the_columns_from_extractor_evidence():
    row = _project(_Read(evidence=document_of(build_ledger_page(ROWS))))
    cells = _eq_cells(row)
    assert cells["eq_version"] == str(EXTRACTION_QUALITY_VERSION)
    assert cells["eq_word_count"] == str(6 + ROWS * 6)
    assert cells["eq_money_rate"] == repr(round(0.5, 6))
    assert cells["eq_class"] == ""
    # the ink columns stay EMPTY without a raster, which is the production
    # case: outside a research partition only `raster_sha256` is kept
    assert cells["eq_ink_outside_boxes"] == ""
    assert row.as_dict()["eq_word_count"] == cells["eq_word_count"]


def test_the_projection_is_empty_on_a_native_only_read():
    """M8's killer. A native read carries `native_evidence`, never
    `evidence`: the extraction-quality question is not asked of text the
    document already carried (an unclaimed native document is a layout
    problem, never a Class-A extraction failure), and a projection that read
    it would put figures on 2,500 production rows."""
    native = ExtractionEvidence(
        document_sha256="B" * 64, extractor_id=NATIVE_EXTRACTOR_ID, model_token=NATIVE_EXTRACTOR_ID,
        pages=(evidence_page(build_ledger_page(ROWS)),),
    )
    assert _eq_cells(_project(_Read(native_evidence=native))) == {
        column: "" for column, _, _ in EQ_ROW_COLUMNS
    }
    # and the second condition holds alone: native evidence attached to the
    # EXTRACTOR field is still refused by its extractor id
    assert _eq_cells(_project(_Read(evidence=native))) == {
        column: "" for column, _, _ in EQ_ROW_COLUMNS
    }


def test_the_projection_is_empty_when_no_read_exists_at_all():
    assert _eq_cells(_project(None)) == {column: "" for column, _, _ in EQ_ROW_COLUMNS}
    assert _eq_cells(_project(_Read())) == {column: "" for column, _, _ in EQ_ROW_COLUMNS}


def test_the_projection_takes_truncation_from_the_existing_page_integrity_flag():
    document = _Read(evidence=document_of(build_ledger_page(ROWS), build_ledger_page(ROWS)),
                     truncated_pages=[1])
    assert _project(document).eq_class == "E5"


def test_a_defect_in_the_metrics_leaves_the_columns_empty_and_never_fails_a_run():
    class _Exploding:
        @property
        def evidence(self):
            return self

        extractor_id = "paddle-synthetic"
        truncated_pages = ()

        @property
        def pages(self):
            raise RuntimeError("a reporting consumer must not be able to fail a run")

    assert _eq_cells(_project(_Exploding())) == {column: "" for column, _, _ in EQ_ROW_COLUMNS}


def test_the_row_refuses_an_e_class_outside_the_closed_vocabulary():
    row = _bare_row()
    row.eq_class = "E9"
    with pytest.raises(ValueError, match="eq_class"):
        row.as_dict()
    row.eq_class = "E2"
    assert row.as_dict()["eq_class"] == "E2"


# ---------------------------------------------------------------------------
# 5. the import boundary, by AST (M10)
# ---------------------------------------------------------------------------

def test_the_module_imports_only_the_standard_library_evidence_and_layout_signals():
    """M10's killer. `analysis`, `ocr.paddle_client`, `webapp`, `telemetry`,
    `discovery` and every third-party package are refused BY SHAPE: a metrics
    module that could import the analysis layer could be handed a verdict."""
    allowed_roots = {"evidence", "layout"}
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative import: this module stands alone in ocr/"
            imported.add((node.module or "").split(".")[0])
    repository = {"analysis", "ocr", "webapp", "telemetry", "discovery", "tools", "tests"}
    assert not (imported & repository), f"repository imports outside the allowance: {sorted(imported & repository)}"
    import sys

    for name in sorted(imported - allowed_roots):
        assert name in sys.stdlib_module_names, f"{name} is neither the standard library nor an allowed package"


# ---------------------------------------------------------------------------
# 4. the document fold and the row cells
# ---------------------------------------------------------------------------

def document_of(*pages) -> ExtractionEvidence:
    """A whole document's evidence from the given SyntheticPages, under a
    synthetic extractor id — the shape the Paddle rung produces."""
    return ExtractionEvidence(
        document_sha256="A" * 64, extractor_id="paddle-synthetic", model_token="synthetic-model",
        pages=tuple(evidence_page(page, page_index=index) for index, page in enumerate(pages)),
    )


def test_the_document_fold_names_the_worst_page_per_column():
    clean, noisy, blank = build_ledger_page(ROWS), build_noise_page(), build_blank_page()
    quality = document_quality(document_of(clean, noisy, blank))
    pages = quality.pages
    assert [page.page_index for page in pages] == [0, 1, 2]
    assert quality.version == EXTRACTION_QUALITY_VERSION
    # the minimum where a LOW value is the defect ...
    assert quality.word_count_min == 0                       # the blank page
    assert quality.density_min == min(page.density for page in pages)
    assert quality.lexicon_rate_min == 0.0                   # the noise page
    assert quality.money_rate_min == min(
        page.money_rate for page in pages if page.money_rate is not None)
    # ... the maximum where a HIGH one is ...
    assert quality.garbage_rate_max == max(page.garbage_rate for page in pages)
    # ... and the worst page's class, by priority: E0 (the blank page)
    # outranks E2 (the noise page).
    assert [page.e_class for page in pages] == ["", "E2", "E0"]
    assert quality.e_class == "E0"


def test_a_metric_no_page_measured_stays_unmeasured_at_the_document_level():
    quality = document_quality(document_of(build_ledger_page(ROWS)))
    assert quality.ink_outside_boxes_max is None             # no raster was supplied
    assert quality.rec_mean is None and quality.rec_p10_min is None
    # and an unmeasured figure is an EMPTY cell, never a zero
    values = eq_row_values(document_of(build_ledger_page(ROWS)))
    assert values["eq_ink_outside_boxes"] == "" and values["eq_rec_mean"] == ""


def test_the_truncation_flag_is_taken_per_page_from_the_caller():
    quality = document_quality(document_of(build_ledger_page(ROWS), build_ledger_page(ROWS)),
                               truncated_pages=(1,))
    assert [page.truncated for page in quality.pages] == [False, True]
    assert [page.e_class for page in quality.pages] == ["", "E5"]
    assert quality.e_class == "E5"


def test_the_row_cells_are_exactly_the_thirteen_columns_in_one_table():
    values = eq_row_values(document_of(build_ledger_page(ROWS)))
    assert list(values) == [column for column, _, _ in EQ_ROW_COLUMNS]
    assert list(values)[0] == "eq_version" and list(values)[-1] == "eq_class"
    assert values["eq_version"] == str(EXTRACTION_QUALITY_VERSION)
    assert values["eq_class"] == ""
    assert all(isinstance(value, str) for value in values.values())
    # every column names a real DocumentQuality attribute and states its fold
    quality = document_quality(document_of(build_ledger_page(ROWS)))
    for column, attribute, fold_note in EQ_ROW_COLUMNS:
        assert hasattr(quality, attribute), column
        assert fold_note, column


def test_the_metrics_are_deterministic():
    first = eq_row_values(document_of(build_ledger_page(ROWS), build_noise_page()))
    second = eq_row_values(document_of(build_ledger_page(ROWS), build_noise_page()))
    assert first == second


def test_the_module_names_no_document_and_no_issuer():
    """The metrics are computed from shapes, never from a string a statement
    prints: no bank, no customer, no sha, no path appears in this module."""
    source = MODULE.read_text(encoding="utf-8")
    for token in ("Bank Statements", "corpus_cache", "webapp_data", ".pdf"):
        assert token not in source, token


# ---------------------------------------------------------------------------
# 9. the money COLUMNS (P23-EGATE review MAJOR-1)
#
# The residual asks "is this a column of figures?" — a question that only
# means something asked of ONE column. Measuring the last money token of each
# line measured the distance BETWEEN columns on every layout that has two, and
# fired E3 on a page with no defect at all.
# ---------------------------------------------------------------------------

def money_column_page(edges, *, text: str = "10.00", token_width: float = 33.0) -> PageEvidence:
    """The smallest page that can say what the residual does: one money token
    per line, each ENDING at the given edge. `token_width / len(text)` is the
    page's own character width, so an edge expressed in points converts to
    character widths by a number the test can state."""
    words = tuple(
        WordBox(word_id=word_id(0, index, index), page_index=0, text=text,
                x0=edge - token_width, y0=72.0 + index * 18.0,
                x1=edge, y1=72.0 + index * 18.0 + 11.0, line_ref=index)
        for index, edge in enumerate(edges)
    )
    return PageEvidence(
        frame=PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0),
        words=words,
    )


def test_a_flawless_two_column_page_is_not_a_wandering_column():
    """The review's MAJOR-1, as a pin. Withdrawals and deposits, no running
    balance, every token clean — the residual is each column's OWN wobble
    (zero), not the 120 points between them, and nothing fires."""
    quality = page_quality(evidence_page(build_column_page(columns=2)))
    assert quality.right_edge_residual == pytest.approx(0.0)
    assert quality.classes == (), quality.classes
    assert quality.e_class == ""


def test_a_three_column_page_is_measured_by_its_worst_column():
    quality = page_quality(evidence_page(build_column_page(columns=3)))
    assert quality.right_edge_residual == pytest.approx(0.0)
    assert quality.classes == ()
    # and the count reported is the worst COLUMN's, never every edge on the page
    assert 0 < quality.right_edge_lines < 12


def test_a_single_column_that_really_wanders_still_fires_E3():
    """The other half of MAJOR-1: the metric must still do its job. Six edges
    ten points apart — every gap well inside the clustering tolerance, so this
    is ONE column — scatter by 2.27 character widths against a 1.5 ceiling."""
    page = money_column_page([400.0, 410.0, 420.0, 430.0, 440.0, 450.0])
    quality = page_quality(page)
    assert quality.right_edge_lines == 6
    assert quality.right_edge_residual == pytest.approx(15.0 / 6.6)
    assert quality.right_edge_residual > THRESHOLDS["right_edge_residual_ceiling"]
    assert "E3" in quality.classes


def test_two_tidy_columns_of_the_same_page_are_two_columns_not_one_wide_one():
    """The clustering itself, at the smallest scale: two groups 100 points
    apart, each perfectly aligned. Measured as one distribution the residual
    would be 50 points — 7.6 character widths, five times the ceiling."""
    page = money_column_page([400.0, 400.0, 400.0, 500.0, 500.0, 500.0])
    quality = page_quality(page)
    assert quality.right_edge_residual == pytest.approx(0.0)
    assert quality.right_edge_lines == 3
    assert "E3" not in quality.classes


def test_a_column_with_too_few_edges_is_unmeasured_never_a_measured_zero():
    """`right_edge_residual_min_lines` applies PER COLUMN. Two edges in one
    column and two in another is not two columns of figures; it is a page
    this metric has nothing to say about."""
    page = money_column_page([400.0, 400.0, 500.0, 500.0])
    quality = page_quality(page)
    assert quality.right_edge_residual is None
    assert "E3" not in quality.classes


def test_the_cluster_tolerance_sits_above_the_residual_ceiling():
    """A structural invariant, not a value judgement: if the tolerance were at
    or below the ceiling, a column wobbling up to its ceiling would split into
    two tidy halves and the defect would measure zero — the metric would hide
    exactly what it exists to report."""
    assert THRESHOLDS["right_edge_cluster_tolerance"] > THRESHOLDS["right_edge_residual_ceiling"]


# ---------------------------------------------------------------------------
# 10. E3's orientation criterion reads the FRAME (P23-EGATE review MINOR-2)
# ---------------------------------------------------------------------------

def rotated_page_with_wide_boxes(count: int) -> PageEvidence:
    """The quarter-turned ledger plus `count` WIDE two-character boxes — the
    page number, rule fragment or stamp that every real rotated scan carries,
    and that at v1's literal unanimity disarmed E3 completely."""
    rotated = evidence_page(rotate_page_90(build_ledger_page(ROWS)))
    words = list(rotated.words)
    for index in range(count):
        y = 40.0 + index * 20.0
        words.append(WordBox(
            word_id=word_id(0, 900 + index, len(words)), page_index=0, text="PG",
            x0=20.0, y0=y, x1=80.0, y1=y + 12.0, line_ref=900 + index,
        ))
    return PageEvidence(frame=rotated.frame, words=tuple(words))


def test_a_rotated_page_carrying_one_wide_box_still_fires_E3():
    """MINOR-2, as a pin. One horizontal vote among a hundred vertical ones is
    an artefact box, not evidence that the page is upright."""
    quality = page_quality(rotated_page_with_wide_boxes(1))
    assert quality.orientation_votes.horizontal == 1
    assert quality.orientation_votes.vertical_share < 1.0
    assert quality.orientation_votes.vertical_share >= THRESHOLDS["orientation_majority_share"]
    assert "E3" in quality.classes


def test_a_page_whose_boxes_are_a_bare_majority_vertical_does_not_fire_E3():
    """The threshold is a majority, not "more than half": a page whose boxes
    are only three-quarters vertical is not a rotated page, it is a page with
    a tall panel on it."""
    rotated = rotated_page_with_wide_boxes(0)
    words = list(rotated.words)
    vertical = sum(1 for word in words
                   if (word.y1 - word.y0) > (word.x1 - word.x0) * THRESHOLDS["orientation_min_aspect"]
                   and len(word.text.strip()) >= THRESHOLDS["orientation_min_chars"])
    for index in range(vertical // 3):
        y = 40.0 + index * 12.0
        words.append(WordBox(
            word_id=word_id(0, 800 + index, len(words)), page_index=0, text="PG",
            x0=20.0, y0=y, x1=80.0, y1=y + 10.0, line_ref=800 + index,
        ))
    quality = page_quality(PageEvidence(frame=rotated.frame, words=tuple(words)))
    assert quality.orientation_votes.vertical_share < THRESHOLDS["orientation_majority_share"]
    assert "E3" not in quality.classes


def vertical_box_page(*, width: float, height: float, boxes: int = 12) -> PageEvidence:
    """A page whose ONLY possible class is the orientation one: `boxes` tall
    two-character boxes, one per line, all the same height (so the line-height
    CV is zero) and not one money token (so the residual is unmeasured)."""
    words = tuple(
        WordBox(word_id=word_id(0, index, index), page_index=0, text="PG",
                x0=100.0, y0=index * 30.0, x1=120.0, y1=index * 30.0 + 60.0,
                line_ref=index)
        for index in range(boxes)
    )
    return PageEvidence(
        frame=PageFrame.pdf_points(page_index=0, width_pt=width, height_pt=height),
        words=words,
    )


def test_a_square_frame_has_no_reading_direction_to_disagree_with():
    """The FRAME half of §H.4's E3, and the reason `frame_reading` exists: a
    square page says nothing about which way it is read, so no arrangement of
    its boxes disagrees with it. The same boxes in a frame that HAS a long
    side are a rotated page."""
    upright = page_quality(vertical_box_page(width=612.0, height=792.0))
    assert upright.frame_reading == "horizontal"
    assert upright.orientation_votes.vertical_share == pytest.approx(1.0)
    assert upright.classes == ("E3",)

    square = page_quality(vertical_box_page(width=612.0, height=612.0))
    assert square.frame_reading is None
    assert square.orientation_votes.vertical_share == pytest.approx(1.0)
    assert square.classes == (), square.classes


def test_the_square_tolerance_is_a_tolerance_not_an_equality():
    """A scanned page is never exactly square, and a frame a hair off square
    still has no reading direction worth the name."""
    nearly = page_quality(vertical_box_page(width=612.0, height=618.0))
    assert nearly.frame_reading is None
    assert nearly.classes == ()
    clearly = page_quality(vertical_box_page(width=612.0, height=700.0))
    assert clearly.frame_reading == "horizontal"
    assert clearly.classes == ("E3",)


# ---------------------------------------------------------------------------
# 11. the garbage rule: furniture, and a denominator (review MINOR-1)
# ---------------------------------------------------------------------------

def test_statement_furniture_is_not_garbage_and_says_which_shape_it_is():
    """A masked account number, a fully masked field, an IBAN and a footer URL
    are what a page READ PERFECTLY looks like. Each is excused by a NAMED
    shape, so a reviewer can ask which one and an unused shape is visible."""
    shapes = [non_garbage_shape(token) for token in FURNITURE_TOKENS]
    assert shapes == ["masked_account", "masked_field", "iban", "url"]
    assert not any(_is_garbage_token(token) for token in FURNITURE_TOKENS)


def test_the_named_shapes_do_not_excuse_the_runs_they_resemble():
    """The bound lives inside each shape, so a shape cannot quietly widen into
    an excuse for the defect it sits next to."""
    assert non_garbage_shape("X" * 30) is None and _is_garbage_token("X" * 30)
    assert non_garbage_shape("XX") is None
    assert non_garbage_shape("GB29" + "N" * 40) is None
    # and the tokens v1 correctly did NOT call garbage are still not garbage
    assert not _is_garbage_token("00000000") and not _is_garbage_token("-" * 11)


def test_every_named_shape_is_read_and_none_is_dead():
    """A shape table nothing matches is documentation, and a shape spelled
    twice is a fork — the same two claims the threshold table carries."""
    matched = {non_garbage_shape(token) for token in FURNITURE_TOKENS}
    assert matched == set(NON_GARBAGE_SHAPES), sorted(set(NON_GARBAGE_SHAPES) - matched)
    source = MODULE.read_text(encoding="utf-8")
    for pattern in NON_GARBAGE_SHAPES.values():
        assert source.count(pattern) == 1, f"the shape {pattern!r} is spelled more than once"


def test_a_sparse_furniture_page_is_measured_and_not_classified():
    """Both halves of MINOR-1 on one page: the furniture is not garbage, and
    even if it were, fourteen tokens is not a denominator for a rate."""
    quality = page_quality(evidence_page(build_sparse_furniture_page()))
    assert quality.word_count < THRESHOLDS["garbage_rate_min_tokens"]
    assert quality.garbage_rate == pytest.approx(0.0)
    assert quality.classes == (), quality.classes


def garbage_rate_page(*, money: int, garbage: int) -> PageEvidence:
    """A page built to isolate the GARBAGE criterion and nothing else: one
    tidy money column (so the residual is zero and the money rate is 1.0),
    too few alphabetic tokens for the lexicon criterion to have a denominator,
    uniform line heights, and `garbage` repeated-letter tokens."""
    tokens = ["10.00"] * money + ["SYNTHETICCCCCCC"] * garbage
    words = tuple(
        WordBox(word_id=word_id(0, index, index), page_index=0, text=token,
                x0=400.0 - len(token) * 6.6, y0=72.0 + index * 18.0,
                x1=400.0, y1=72.0 + index * 18.0 + 11.0, line_ref=index)
        for index, token in enumerate(tokens)
    )
    return PageEvidence(
        frame=PageFrame.pdf_points(page_index=0, width_pt=612.0, height_pt=792.0),
        words=words,
    )


def test_the_garbage_denominator_guard_measures_and_refuses_to_classify():
    """The guard is on CLASSIFICATION, never on measurement: a short page's
    rate is still reported, it just does not acquire a class from it. Both
    pages carry the same defect at the same rate; only the denominator
    differs."""
    short = page_quality(garbage_rate_page(money=18, garbage=2))
    assert short.word_count >= THRESHOLDS["min_words_for_page_metrics"]
    assert short.word_count < THRESHOLDS["garbage_rate_min_tokens"]
    assert short.garbage_rate > THRESHOLDS["garbage_rate_ceiling"]
    assert short.classes == (), short.classes

    long = page_quality(garbage_rate_page(money=27, garbage=3))
    assert long.word_count >= THRESHOLDS["garbage_rate_min_tokens"]
    assert long.garbage_rate == pytest.approx(short.garbage_rate)
    assert long.classes == ("E2",), long.classes


# ---------------------------------------------------------------------------
# 12. the fold, proven per column (P23-EGATE review MAJOR-2)
#
# The first fold fixture was three pages that AGREED on seven of the eleven
# folded figures, so "min over pages" and "max over pages" were the same
# number and the assertion held whichever fold the module used. The review
# killed nothing with six mutants that swap one fold for its opposite. This
# fixture makes every column's three page values DISTINCT, so each fold is
# the only answer that passes.
# ---------------------------------------------------------------------------

def fold_page(index: int, *, money_ok: int, wobble: float, money_bad: int,
              lexicon_words: int, other_words: int, garbage_words: int,
              narrow_boxes: int, heights: tuple[float, ...],
              confidence_high: float, confidence_low: float) -> PageEvidence:
    """One page of the discriminating fold fixture, every metric dialled.

    A NARROW box is how a vertical vote is cast without disturbing anything
    else: it keeps its line's own height, so the line-height CV is untouched,
    and it is five points wide, so it votes vertical."""
    vocabulary = sorted(lexicon_vocabulary())
    tokens: list[tuple[str, str]] = []
    tokens += [("10.00", "money")] * money_ok
    tokens += [("12X45", "plain")] * money_bad
    tokens += [(vocabulary[position % len(vocabulary)].upper(), "plain")
               for position in range(lexicon_words)]
    tokens += [("SYNTHETIC", "plain")] * other_words
    tokens += [("SYNTHETICCCCCCC", "plain")] * garbage_words
    tokens += [("PG", "narrow")] * narrow_boxes

    words: list[WordBox] = []
    for position, (text, kind) in enumerate(tokens):
        line = position % len(heights)
        height = heights[line]
        y0 = 72.0 + line * 90.0
        if kind == "money":
            x1 = 400.0 + (wobble if position % 2 else 0.0)
            x0 = x1 - len(text) * 6.6
        elif kind == "narrow":
            x0 = 60.0 + position
            x1 = x0 + 5.0
        else:
            x0 = 60.0 + (position % 4) * 70.0
            x1 = x0 + len(text) * 6.6
        words.append(WordBox(
            word_id=word_id(index, line, position), page_index=index, text=text,
            x0=x0, y0=y0, x1=x1, y1=y0 + height,
            confidence=confidence_low if position % 10 == 0 else confidence_high,
            line_ref=line,
        ))
    return PageEvidence(
        frame=PageFrame.pdf_points(page_index=index, width_pt=612.0, height_pt=792.0),
        words=tuple(words),
    )


#: Three pages that disagree about EVERYTHING. Page 1 clears the line-height
#: ceiling (so it is the E3 page), page 2 is flagged truncated by the caller
#: (E5), page 0 is clean — so the worst page by priority is the MIDDLE one,
#: which neither "the first page's class" nor "the last page's" can produce.
FOLD_PAGES = (
    dict(money_ok=10, wobble=0.0, money_bad=0, lexicon_words=12, other_words=8,
         garbage_words=0, narrow_boxes=0, heights=(10.0, 10.0, 10.0, 10.0, 10.0, 10.0),
         confidence_high=0.95, confidence_low=0.90),
    dict(money_ok=12, wobble=6.6, money_bad=4, lexicon_words=10, other_words=14,
         garbage_words=1, narrow_boxes=6, heights=(10.0, 40.0, 10.0, 40.0, 10.0, 40.0),
         confidence_high=0.85, confidence_low=0.70),
    dict(money_ok=14, wobble=13.2, money_bad=14, lexicon_words=6, other_words=20,
         garbage_words=2, narrow_boxes=16, heights=(10.0, 15.0, 10.0, 15.0, 10.0, 15.0),
         confidence_high=0.60, confidence_low=0.40),
)


def fold_document() -> ExtractionEvidence:
    return ExtractionEvidence(
        document_sha256="B" * 64, extractor_id="paddle-synthetic",
        model_token="synthetic-model",
        pages=tuple(fold_page(index, **spec) for index, spec in enumerate(FOLD_PAGES)),
    )


#: A raster for one fold page: `inside` dark pixels inside the money column's
#: first box, `outside` dark pixels in a corner no box reaches. The share of
#: ink outside every box is then exactly `outside / (inside + outside)`, which
#: is how this fixture states an ink figure instead of discovering one.
FOLD_RASTER_WIDTH, FOLD_RASTER_HEIGHT = 61, 79
FOLD_INSIDE_PIXELS = [(x, y) for y in (7, 8) for x in range(36, 41)]
FOLD_OUTSIDE_PIXELS = [(x, 75) for x in range(50, 60)]


def fold_raster(*, inside: int, outside: int) -> RasterGray:
    return grey(FOLD_RASTER_WIDTH, FOLD_RASTER_HEIGHT,
                FOLD_INSIDE_PIXELS[:inside] + FOLD_OUTSIDE_PIXELS[:outside])


#: One per fold page, chosen so the three ink shares differ and none of them
#: reaches `ink_outside_boxes_ceiling` — the ink column must discriminate the
#: FOLD without firing a class, or the fixture would be proving two things.
FOLD_RASTERS = {0: fold_raster(inside=9, outside=1),
                1: fold_raster(inside=8, outside=2),
                2: fold_raster(inside=7, outside=3)}


def test_every_folded_column_is_pinned_by_pages_that_disagree():
    """MAJOR-2's killer, and the card's "state AND pin the fold per column".

    For each folded column the three pages carry three DIFFERENT values, so
    the fold the table names is the only one that produces the document's
    figure — the opposite fold is asserted to be a different number, which is
    what makes each of the review's six swap mutants die."""
    quality = document_quality(fold_document(), rasters=FOLD_RASTERS, truncated_pages=(2,))
    pages = quality.pages
    folded = {
        "word_count_min": ([page.word_count for page in pages], min),
        "density_min": ([page.density for page in pages], min),
        "rec_p10_min": ([page.rec_p10 for page in pages], min),
        "money_rate_min": ([page.money_rate for page in pages], min),
        "lexicon_rate_min": ([page.lexicon_rate for page in pages], min),
        "garbage_rate_max": ([page.garbage_rate for page in pages], max),
        "line_height_cv_max": ([page.line_height_cv for page in pages], max),
        "right_edge_residual_max": ([page.right_edge_residual for page in pages], max),
        "ink_outside_boxes_max": ([page.ink_outside_boxes for page in pages], max),
        "orientation_vertical_share_max": (
            [page.orientation_votes.vertical_share for page in pages], max),
    }
    for name, (values, fold) in folded.items():
        assert None not in values, (name, values)
        assert len(set(values)) == len(pages), (name, values, "the fixture must discriminate")
        assert getattr(quality, name) == fold(values), (name, values)
        opposite = max if fold is min else min
        assert getattr(quality, name) != opposite(values), (name, values, "the swap survives")

    # `rec_mean` is the one distribution figure: the mean of the page means,
    # which on a discriminating fixture is neither the smallest nor the largest.
    means = [page.rec_mean for page in pages]
    assert quality.rec_mean == pytest.approx(fmean(means))
    assert quality.rec_mean not in (min(means), max(means))

    # and the class fold names the WORST page by priority — here the MIDDLE
    # page, which neither "the first page's class" nor "the last page's" gives.
    assert [page.e_class for page in pages] == ["", "E3", "E5"]
    assert quality.e_class == "E3"


def test_the_fold_fixture_covers_every_column_the_row_carries():
    """The pin above is only worth what it COVERS. Every column of
    `EQ_ROW_COLUMNS` is either folded and pinned there, the version, or the
    class — so a fourteenth column cannot arrive with no fold pinned."""
    pinned = {
        "word_count_min", "density_min", "rec_p10_min", "money_rate_min",
        "lexicon_rate_min", "garbage_rate_max", "line_height_cv_max",
        "right_edge_residual_max", "ink_outside_boxes_max",
        "orientation_vertical_share_max", "rec_mean",
    }
    carried = {attribute for _, attribute, _ in EQ_ROW_COLUMNS}
    assert carried - pinned == {"version", "e_class"}, sorted(carried - pinned - {"version", "e_class"})
    assert pinned <= carried, sorted(pinned - carried)


def test_the_calibration_surface_is_pinned_by_a_digest_against_the_version():
    """F9's killer. v1 pinned the thresholds by a literal in THIS file, and
    the review defeated it in two lines: move a threshold, move the literal
    with it, leave the version at 1. The digest is keyed by the version, so a
    threshold edit now fails until it arrives with a new version and its own
    recorded digest — and editing a recorded version's row is rewriting what
    an already-censused number meant."""
    assert calibration_digest() == CALIBRATION_DIGESTS[EXTRACTION_QUALITY_VERSION]
    assert EXTRACTION_QUALITY_VERSION in CALIBRATION_DIGESTS
    assert all(isinstance(key, int) for key in CALIBRATION_DIGESTS)


def test_the_digest_is_derived_from_both_tables_and_not_decorative():
    """A digest that does not move when a value moves is a constant with a
    long name. Every threshold and every shape is shown to change it — in a
    COPY of each table, so the module under test is never mutated."""
    import hashlib
    import json

    def digest_of(thresholds, shapes):
        payload = json.dumps(
            {"thresholds": {name: thresholds[name] for name in sorted(thresholds)},
             "shapes": {name: shapes[name] for name in sorted(shapes)}},
            sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    base = dict(THRESHOLDS), dict(NON_GARBAGE_SHAPES)
    assert digest_of(*base) == calibration_digest()
    for name in THRESHOLDS:
        moved = dict(THRESHOLDS)
        moved[name] = float(moved[name]) + 1.0
        assert digest_of(moved, base[1]) != calibration_digest(), name
    for name in NON_GARBAGE_SHAPES:
        widened = dict(NON_GARBAGE_SHAPES)
        widened[name] = widened[name] + "?"
        assert digest_of(base[0], widened) != calibration_digest(), name


# ---------------------------------------------------------------------------
# 13. E1's known false positive, recorded rather than tuned (review MINOR-3)
# ---------------------------------------------------------------------------

def test_a_logo_block_fires_E1_and_that_is_a_recorded_calibration_limit():
    """MINOR-3. E1 is a share of INK — the plan's own definition — so ordinary
    non-text ink dominates it on a sparse page: a logo, a shaded header band, a
    signature panel, ink every real statement carries and no word box covers.

    This is pinned as a KNOWN false positive rather than fixed. The threshold
    is not moved, because moving a threshold without real evidence is exactly
    the mistake Ruling B exists to prevent and exactly what `ALNUM_DENSITY_
    FLOOR` documents; the owed census over real evidence is what says where
    this ceiling belongs. If this test ever fails, the calibration changed and
    the record must change with it.

    `with_logo` lived in `tools/p23egate_synthetic_table.py`, which left with the
    PaddleOCR rung (model-code removal, slice S5); it is copied here verbatim
    from that file's last commit (a290301)."""
    from ocr.extraction_quality import RasterGray

    def with_logo(raster: RasterGray, *, size: int = 90, x: int = 20, y: int = 20) -> RasterGray:
        """A raster plus one solid block of ink that carries no word box — a logo,
        a shaded header band, a signature panel: ink every real statement has."""
        pixels = bytearray(raster.pixels)
        for row in range(y, min(y + size, raster.height)):
            start = row * raster.width
            for column in range(x, min(x + size, raster.width)):
                pixels[start + column] = 0
        return RasterGray(width=raster.width, height=raster.height, pixels=bytes(pixels))

    page = build_ledger_page(ROWS)
    clean = page_quality(evidence_page(page), raster=rendered_raster(page))
    assert clean.ink_outside_boxes < THRESHOLDS["ink_outside_boxes_ceiling"]
    assert clean.classes == ()

    # The fixture's Courier is not embedded, so each host draws it in its own substitute font (a thin Courier New on
    # Windows, a heavier mono face on Linux CI): a fixed-size logo's share of the ink then depended on the host. The
    # block now carries as much ink as every word on the page together and sits in the empty foot of the page, away
    # from every word box, so its share is about one half on any host. The threshold itself is untouched.
    raster = rendered_raster(page)
    text_ink = sum(1 for value in raster.pixels if value <= THRESHOLDS["ink_dark_luminance_max"])
    side = int(text_ink ** 0.5) + 1
    logo = page_quality(evidence_page(page), raster=with_logo(raster, size=side, y=raster.height - side - 20))
    assert logo.ink_outside_boxes > THRESHOLDS["ink_outside_boxes_ceiling"]
    assert logo.classes == ("E1",)
    # the page's WORDS are identical: nothing about the extraction changed
    assert logo.word_count == clean.word_count
    assert logo.money_rate == clean.money_rate and logo.lexicon_rate == clean.lexicon_rate

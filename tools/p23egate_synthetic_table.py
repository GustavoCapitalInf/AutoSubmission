"""tools/p23egate_synthetic_table.py — the defect-page table (P23-EGATE item 4).

    python tools/p23egate_synthetic_table.py

Prints, for every synthetic defect page, the metric it targets, that metric's
measured value, the threshold it crosses, and the E-class the page fires —
the table the W3 section carries. The numbers in the record are produced by
this instrument rather than typed from a test's assertions, which is the rule
for any figure that reaches a report.

Every page comes from `tests/paddle_synthetic.py` (literal strings, dated
2031, never derived from a document) and the raster, where a page needs one,
is rendered through `ocr.rasterize` — the same rasteriser the Paddle rung
uses. Nothing here reads the archive, a cache or the network; it is the
default suite's own fixtures, printed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.canonical import PageEvidence, PageFrame, WordBox, word_id  # noqa: E402
from ocr.extraction_quality import (  # noqa: E402
    EXTRACTION_QUALITY_VERSION,
    THRESHOLDS,
    RasterGray,
    page_quality,
)
from tests.paddle_synthetic import (  # noqa: E402
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

ROWS = 20


def evidence_page(page) -> PageEvidence:
    words = []
    for line_index, line in enumerate(page.lines):
        for word in line.words:
            words.append(WordBox(
                word_id=word_id(0, line_index, len(words)), page_index=0, text=word.text,
                x0=word.x0, y0=word.y0, x1=word.x1, y1=word.y1, line_ref=line_index,
            ))
    return PageEvidence(
        frame=PageFrame.pdf_points(page_index=0, width_pt=page.width_pt, height_pt=page.height_pt),
        words=tuple(words),
    )


def raster_of(page, *, dpi: int = 100) -> RasterGray:
    from ocr.rasterize import rasterize_pdf
    from tests.paddle_synthetic import render_native_pdf

    image = rasterize_pdf(render_native_pdf(page), dpi=dpi)[0].convert("L")
    return RasterGray(width=image.width, height=image.height, pixels=image.tobytes())


def with_logo(raster: RasterGray, *, size: int = 90, x: int = 20, y: int = 20) -> RasterGray:
    """A raster plus one solid block of ink that carries no word box — a logo,
    a shaded header band, a signature panel: ink every real statement has."""
    pixels = bytearray(raster.pixels)
    for row in range(y, min(y + size, raster.height)):
        start = row * raster.width
        for column in range(x, min(x + size, raster.width)):
            pixels[start + column] = 0
    return RasterGray(width=raster.width, height=raster.height, pixels=bytes(pixels))


def case_raster(rendered):
    """`None`, a page to rasterise, or a callable that builds the raster."""
    if rendered is None:
        return None
    return rendered() if callable(rendered) else raster_of(rendered)


def main() -> int:
    clean = build_ledger_page(ROWS)
    cases = [
        # (page name, evidence page, page rendered for the raster, metric, threshold key, direction)
        ("clean ledger (the control)", clean, None, None, None, None),
        ("blank", build_blank_page(), build_blank_page(), "word_count", None, "== 0"),
        ("partly covered", keep_first_lines(clean, 6), clean, "ink_outside_boxes",
         "ink_outside_boxes_ceiling", "above"),
        ("90 degrees", rotate_page_90(clean), None, "orientation_votes", "orientation_majority_share", "above"),
        ("noise", build_noise_page(), None, "lexicon_rate", "lexicon_rate_floor", "below"),
        ("digit-glyph substitution", substitute_digit_glyphs(clean), None, "money_rate",
         "money_rate_floor", "below"),
        ("over-long tokens", build_garbage_token_page(), None, "garbage_rate", "garbage_rate_ceiling", "above"),
        ("repeated-letter runs", build_repeated_letter_page(), None, "garbage_rate",
         "garbage_rate_ceiling", "above"),
        ("clean ledger, page-integrity flag set", clean, None, "truncated", None, "True"),
        # --- pages that are NOT defects, carried in the same table ----------
        # Two layouts the review found firing E3 with nothing wrong with them,
        # now measured per money column (MAJOR-1), and a sparse page whose
        # furniture v1 counted as garbage (MINOR-1). They belong here because
        # a defect table that only shows defects cannot show a FALSE POSITIVE
        # being closed.
        ("two money columns (no defect)", build_column_page(columns=2), None,
         "right_edge_residual", "right_edge_residual_ceiling", "above"),
        ("three money columns (no defect)", build_column_page(columns=3), None,
         "right_edge_residual", "right_edge_residual_ceiling", "above"),
        ("sparse page of furniture (no defect)", build_sparse_furniture_page(), None,
         "garbage_rate", "garbage_rate_ceiling", "above"),
        # And one this cell does NOT close: E1 is a share of INK, so ordinary
        # non-text ink dominates it on a sparse page. Named, measured, and
        # left alone — a threshold moved without real evidence is the mistake
        # Ruling B exists to prevent (review MINOR-3).
        ("clean ledger + a logo block (KNOWN FALSE POSITIVE)", clean,
         lambda: with_logo(raster_of(build_ledger_page(ROWS))),
         "ink_outside_boxes", "ink_outside_boxes_ceiling", "above"),
    ]

    print(f"# P23-EGATE synthetic defect table (EXTRACTION_QUALITY_VERSION {EXTRACTION_QUALITY_VERSION})")
    print()
    print("| page | metric it targets | measured | threshold | E-class | every class that fired |")
    print("|---|---|---|---|---|---|")
    for name, page, rendered, metric, key, direction in cases:
        raster = case_raster(rendered)
        quality = page_quality(evidence_page(page), raster=raster,
                               truncated=name.endswith("page-integrity flag set"))
        if metric is None:
            measured = threshold = "-"
        elif metric == "orientation_votes":
            votes = quality.orientation_votes
            measured = f"vertical share {votes.vertical_share!r} of {votes.decided} votes"
            threshold = f"{key} = {THRESHOLDS[key]!r}"
        else:
            value = getattr(quality, metric)
            measured = "-" if value is None else (f"{value:.6g}" if isinstance(value, float) else str(value))
            threshold = "-" if key is None else f"{key} = {THRESHOLDS[key]!r}"
        print(f"| {name} | {metric or '(none)'} | {measured} | {threshold} | "
              f"{quality.e_class or '(none)'} | {', '.join(quality.classes) or '(none)'} |")

    print()
    print("Every other metric on every DEFECT page stays inside its threshold: the pages are")
    print("transforms of the same clean ledger, so the defect is the only difference. The rows")
    print("marked (no defect) fire nothing at all, which is what closes the review's MAJOR-1 and")
    print("MINOR-1; the row marked KNOWN FALSE POSITIVE fires E1 and is recorded, not fixed.")
    print()
    print("| page | word_count | money_rate | lexicon_rate | garbage_rate | line_height_cv "
          "| right_edge_residual | ink_outside_boxes |")
    print("|---|---|---|---|---|---|---|---|")
    for name, page, rendered, *_ in cases:
        raster = case_raster(rendered)
        quality = page_quality(evidence_page(page), raster=raster)
        cells = []
        for metric in ("word_count", "money_rate", "lexicon_rate", "garbage_rate",
                       "line_height_cv", "right_edge_residual", "ink_outside_boxes"):
            value = getattr(quality, metric)
            cells.append("unmeasured" if value is None
                         else (f"{value:.6g}" if isinstance(value, float) else str(value)))
        print(f"| {name} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

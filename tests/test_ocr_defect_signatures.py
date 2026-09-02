"""P20-SEAM / OQ7: `triage_scan.py`'s `CHECKS` dict, salvaged before retirement.

`triage_scan.py` was a dev-only script that grepped `output/*.md` for seven
known visual-OCR defect signatures so a human could triage which banks needed
postprocessor work. OCR_LEGACY_AUDIT.md #32 calls it "a useful inventory of
the visual rung's known defect signatures [that] should be salvaged into a
test before deletion." This module is that salvage: each signature is
reproduced as a synthetic fixture and asserted against the detector that
replaces it — `ocr.ocr_client`'s postprocess functions — or, where none
exists, recorded honestly as a known, undetected visual-output defect rather
than silently dropped when the script was removed (`git rm`, this commit).

Nothing here performs OCR or touches a network; every fixture is a literal
string standing in for the model's raw output.
"""
from __future__ import annotations

import re

from ocr.ocr_client import (
    collapse_repeated_amounts,
    fix_amount_column_bleed,
    postprocess,
    split_fused_header_row,
    strip_det_tags,
    strip_placeholder_markers,
)

# ---------------------------------------------------------------------------
# triage_scan.py::CHECKS, verbatim (the salvaged inventory)
# ---------------------------------------------------------------------------

CHECKS = {
    "leftover_det_tags": re.compile(r"<\|/?det\|>"),
    "non_text_marker": re.compile(r"\[Non-?Text\]", re.IGNORECASE),
    "image_placeholder": re.compile(r"\[(image|figure|logo|picture|photo)\]", re.IGNORECASE),
    # header glued to a value in one cell, e.g. "DATE01/02", "AMOUNT$1,000.00"
    "fused_header_cell": re.compile(r"<td>(DATE|AMOUNT|BALANCE|DESCRIPTION)(?=[^\s<])"),
    # 3+ whitespace-separated money tokens (repetition degeneration)
    "money_run": re.compile(r"(-?\$?[\d,]+\.\d{2})(?:\s+-?\$?[\d,]+\.\d{2}){2,}"),
    "empty_table": re.compile(r"<table>\s*</table>"),
    # a cell holding description text AND a trailing amount (column bleed)
    "amount_bleed": re.compile(r"<td>[^<]* [A-Za-z]{3}[^<]* -?\$?[\d,]+\.\d{2}</td>"),
}


# ---------------------------------------------------------------------------
# Signatures with a detector: the fixture is cleaned and the signature is gone
# ---------------------------------------------------------------------------


def test_leftover_det_tags_removed_by_strip_det_tags():
    fixture = "<|det|>label [1,2,3,4]<|/det|>text here"
    cleaned = strip_det_tags(fixture)
    assert CHECKS["leftover_det_tags"].search(cleaned) is None
    assert "text here" in cleaned


def test_leftover_det_tags_orphan_variant_also_removed():
    """The orphan/unclosed variant the model emits around footers."""
    fixture = "<|det|>footer [819, 811, 942, 825] Page 1 of 3"
    cleaned = strip_det_tags(fixture)
    assert CHECKS["leftover_det_tags"].search(cleaned) is None


def test_non_text_marker_removed_by_strip_placeholder_markers():
    fixture = "Deposits\n[Non-Text]\n$5.00"
    cleaned = strip_placeholder_markers(fixture)
    assert CHECKS["non_text_marker"].search(cleaned) is None
    assert "Deposits" in cleaned and "$5.00" in cleaned


def test_fused_header_cell_removed_by_split_fused_header_row():
    fixture = (
        "<table><tr><td>DATE04/06</td><td>DESCRIPTIONFoo Bar</td>"
        "<td>AMOUNT100.00</td></tr></table>"
    )
    cleaned = split_fused_header_row(fixture)
    assert CHECKS["fused_header_cell"].search(cleaned) is None
    # The hidden first data row is recovered, not dropped.
    assert "04/06" in cleaned and "Foo Bar" in cleaned and "100.00" in cleaned


def test_money_run_collapsed_by_collapse_repeated_amounts():
    fixture = "Balance 100.00 100.00 100.00 done"
    cleaned = collapse_repeated_amounts(fixture)
    assert CHECKS["money_run"].search(cleaned) is None
    assert cleaned.count("100.00") == 1


def test_amount_bleed_repaired_by_fix_amount_column_bleed():
    fixture = (
        "<table><tr><td>Description</td><td>Amount</td></tr>"
        "<tr><td>x</td><td>ID:9531796 INDN:HEARTLAND SE CO -74.88</td></tr></table>"
    )
    cleaned = fix_amount_column_bleed(fixture)
    assert CHECKS["amount_bleed"].search(cleaned) is None
    assert "-74.88" in cleaned and "ID:9531796" in cleaned


# ---------------------------------------------------------------------------
# Signatures with NO detector: recorded honestly, not silently dropped
# ---------------------------------------------------------------------------


def test_image_placeholder_has_no_detector_recorded_as_known_defect():
    """`[image]`/`[figure]`/`[logo]`/`[picture]`/`[photo]` bracket placeholders
    are a DIFFERENT shape from the det-tag region markers `embed_image_regions`
    handles (`<|det|>image [x0,y0,x1,y1]<|/det|>`, normalized 0-1000
    coordinates). No function in `ocr.ocr_client.postprocess` strips a bare
    bracket placeholder. This is not an oversight this test papers over: it
    documents the gap OCR_LEGACY_AUDIT.md #32 named, so a future postprocess
    change that silently starts eating this shape is a visible test change,
    not a quiet regression either way.
    """
    fixture = "a photo appears here: [image] and continues"
    cleaned = postprocess(fixture)
    assert CHECKS["image_placeholder"].search(cleaned) is not None


def test_empty_table_has_no_detector_recorded_as_known_defect():
    """A fully empty `<table></table>` (or one holding only whitespace) is not
    repaired or removed by any function in the postprocess chain. Recorded
    the same way as `image_placeholder`, for the same reason."""
    fixture = "before <table>\n</table> after"
    cleaned = postprocess(fixture)
    assert CHECKS["empty_table"].search(cleaned) is not None


# ---------------------------------------------------------------------------
# The salvaged inventory is exactly seven signatures, not a subset
# ---------------------------------------------------------------------------


def test_all_seven_triage_scan_signatures_are_accounted_for():
    """Every key `triage_scan.CHECKS` held has an assertion above — either a
    detector-closes-it test or a no-detector-recorded test. If this module's
    CHECKS dict ever grows or shrinks relative to the original script, this
    count is the tripwire."""
    tested = {
        "leftover_det_tags", "non_text_marker", "image_placeholder",
        "fused_header_cell", "money_run", "empty_table", "amount_bleed",
    }
    assert set(CHECKS) == tested

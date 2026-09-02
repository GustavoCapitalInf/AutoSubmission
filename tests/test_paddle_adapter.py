"""Phase 2.1 cell P: `ocr/paddle_adapter.py` (CASE 5, CASE 7, CASE 8; M5, M6, M7).

Uses the REAL PaddleOCR 3.7 demo result fixture
(`tests/fixtures/paddle/paddle_demo_wordboxes_res.json`) and
`tests/paddle_synthetic.py`'s deterministic generator — no OCR engine runs,
no network, no real statement.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evidence.canonical import PageFrame, from_json, to_json
from ocr.paddle_adapter import PaddleAdapterError, evidence_from_pages, page_evidence_from_result
from tests.paddle_synthetic import build_ledger_page, raster_dimensions, synthetic_paddle_result

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "paddle" / "paddle_demo_wordboxes_res.json"
DOCUMENT_SHA = "A" * 64


def _demo_result() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _demo_frame() -> PageFrame:
    # The demo image's content fits within 900x520px at every measured box;
    # the exact raster size is not asserted by anything here.
    return PageFrame.pixel(
        page_index=0, raster_width_px=900, raster_height_px=520, dpi=96,
        pdf_width_pt=900 * 72 / 96, pdf_height_pt=520 * 72 / 96, raster_sha256=None,
    )


# ---------------------------------------------------------------------------
# CASE 5 — the demo fixture: 33 raw lines / 62 raw word slots -> canonical
# words/lines; every box reproduces from `raw`; JSON round-trip sha stable.
# ---------------------------------------------------------------------------

def test_case5_demo_fixture_shape():
    raw = _demo_result()
    assert len(raw["text_word"]) == 33
    assert sum(len(line) for line in raw["text_word"]) == 62

    page = page_evidence_from_result(raw, frame=_demo_frame())
    assert page.notes == ("dropped_empty_words:11",)
    assert len(page.words) == 51  # 62 raw slots minus 11 blank/whitespace entries
    assert len(page.lines) > 0

    # Every stored word's box reproduces the exact raw pixel box it came from.
    seen = 0
    for line_index, (words, boxes) in enumerate(zip(raw["text_word"], raw["text_word_boxes"])):
        for word_index, (text, box) in enumerate(zip(words, boxes)):
            if not text.strip():
                continue
            wid = f"p0.l{line_index}.w{word_index}"
            word = page.word(wid)
            assert word.text == text
            assert [word.x0, word.y0, word.x1, word.y1] == [float(v) for v in box]
            seen += 1
    assert seen == 51


def test_case5_json_roundtrip_sha_stable():
    raw = _demo_result()
    page = page_evidence_from_result(raw, frame=_demo_frame())
    evidence = evidence_from_pages([page], document_sha256=DOCUMENT_SHA, runtime={"provider": "local"})
    payload = to_json(evidence)
    restored = from_json(payload)
    assert restored.evidence_sha256 == evidence.evidence_sha256
    assert restored.pages[0].raw_sha256 == evidence.pages[0].raw_sha256
    # A second round-trip through JSON text (not just the dict) is stable too.
    text = json.dumps(payload, sort_keys=True)
    restored_again = from_json(json.loads(text))
    assert restored_again.evidence_sha256 == evidence.evidence_sha256


def test_case5_synthetic_ledger_reading_order():
    page = build_ledger_page(n_rows=4)
    width_px, height_px = raster_dimensions(page, dpi=300)
    frame = PageFrame.pixel(
        page_index=0, raster_width_px=width_px, raster_height_px=height_px, dpi=300,
        pdf_width_pt=page.width_pt, pdf_height_pt=page.height_pt, raster_sha256=None,
    )
    raw = synthetic_paddle_result(page, dpi=300)
    evidence_page = page_evidence_from_result(raw, frame=frame)
    lines = [line.text for line in evidence_page.lines]
    assert lines == [line.text for line in page.lines]
    assert lines[2] == "2031-01-01 SYNTHETIC ROW 01 10.00 510.00"


def test_case5_m6_two_column_page_regroups_by_geometry_not_by_paddle_line_order():
    """M6: PaddleOCR's own detector frequently splits ONE visual row into
    SEPARATE `text_word` lines (the demo fixture does this 33 raw lines ->
    11 canonical visual lines). A two-"line" result whose boxes actually
    share one visual row must merge into ONE `LineBox`, words ordered by x —
    even when PaddleOCR's own line order lists the RIGHT-hand word first.
    An adapter that joined `rec_texts` (or grouped by PaddleOCR's own line
    index) instead of `evidence.group_lines`'s geometry would keep them as
    two separate, mis-ordered lines."""
    frame = PageFrame.pixel(page_index=0, raster_width_px=400, raster_height_px=100, dpi=96,
                            pdf_width_pt=400 * 72 / 96, pdf_height_pt=100 * 72 / 96, raster_sha256=None)
    raw = {
        # PaddleOCR detected the RIGHT-hand word as "line 0" and the
        # LEFT-hand word as "line 1" — same y-range, so geometrically one row.
        "text_word": [["RIGHT"], ["LEFT"]],
        "text_word_boxes": [[[200, 10, 260, 30]], [[10, 10, 60, 30]]],
        "rec_texts": ["RIGHT", "LEFT"],
        "rec_scores": [0.9, 0.9],
    }
    page = page_evidence_from_result(raw, frame=frame)
    assert len(page.lines) == 1, "two same-row detections must regroup into one visual line"
    assert page.lines[0].text == "LEFT RIGHT", "words within a regrouped line are ordered by x, not by Paddle's line order"


# ---------------------------------------------------------------------------
# CASE 8 / M5 — malformed shapes refuse the WHOLE page; nothing is clamped.
# ---------------------------------------------------------------------------

def test_case8_length_mismatch_between_arrays_refuses():
    raw = _demo_result()
    raw["rec_scores"] = raw["rec_scores"][:-1]  # one fewer score than lines
    with pytest.raises(PaddleAdapterError, match="line-count mismatch"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_case8_word_box_count_mismatch_within_a_line_refuses():
    raw = _demo_result()
    raw["text_word_boxes"][0] = raw["text_word_boxes"][0][:-1] if len(raw["text_word_boxes"][0]) > 1 else [[0, 0, 1, 1]]
    raw["text_word"][0] = ["ONE", "TWO"]  # force a 2-vs-1 mismatch regardless of the line chosen
    raw["text_word_boxes"][0] = [[0, 0, 1, 1]]
    with pytest.raises(PaddleAdapterError, match="word/box count mismatch"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_case8_missing_key_refuses():
    raw = _demo_result()
    del raw["text_word_boxes"]
    with pytest.raises(PaddleAdapterError, match="text_word_boxes"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_case8_non_list_text_word_refuses():
    raw = _demo_result()
    raw["text_word"] = "not a list"
    with pytest.raises(PaddleAdapterError, match="text_word"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_case8_inverted_box_refuses_never_swapped():
    """M5: the adapter must not clamp or swap an out-of-order box; `evidence`
    itself refuses it, and the adapter surfaces that as a whole-page failure."""
    raw = {
        "text_word": [["BAD"]],
        "text_word_boxes": [[[50, 50, 10, 10]]],  # x1 < x0 and y1 < y0
        "rec_texts": ["BAD"],
        "rec_scores": [0.9],
    }
    with pytest.raises(PaddleAdapterError, match="BAD|inverted|degenerate"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_case8_out_of_raster_box_refuses():
    frame = PageFrame.pixel(page_index=0, raster_width_px=100, raster_height_px=100, dpi=96,
                            pdf_width_pt=100 * 72 / 96, pdf_height_pt=100 * 72 / 96, raster_sha256=None)
    raw = {
        "text_word": [["OUT"]],
        "text_word_boxes": [[[10, 10, 500, 40]]],  # x1 far exceeds the 100px raster width
        "rec_texts": ["OUT"],
        "rec_scores": [0.9],
    }
    with pytest.raises(PaddleAdapterError):
        page_evidence_from_result(raw, frame=frame)


def test_case8_malformed_word_box_shape_refuses():
    raw = {
        "text_word": [["X"]],
        "text_word_boxes": [[[1, 2, 3]]],  # only 3 elements, not [x0,y0,x1,y1]
        "rec_texts": ["X"],
        "rec_scores": [0.9],
    }
    with pytest.raises(PaddleAdapterError, match="4-element"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_minor10_non_string_text_word_entry_refuses_never_coerced():
    """MINOR-10 (PHASE2_P21PADDLE_REVIEW.md): a malformed result (a bare
    number where OCR text should be) must refuse the page — `str()` would
    otherwise manufacture a number-shaped token that looks like it came
    from OCR, exactly the class of hazard CASE 8's other shapes exist for."""
    raw = {
        "text_word": [[1234.56]],
        "text_word_boxes": [[[1, 2, 50, 20]]],
        "rec_texts": ["x"],
        "rec_scores": [0.9],
    }
    with pytest.raises(PaddleAdapterError, match="not a string"):
        page_evidence_from_result(raw, frame=_demo_frame())


@pytest.mark.parametrize("bad_value", [None, True, False, ["a", "list"], {"a": "dict"}])
def test_minor10_every_non_string_shape_refuses(bad_value):
    raw = {
        "text_word": [[bad_value]],
        "text_word_boxes": [[[1, 2, 50, 20]]],
        "rec_texts": ["x"],
        "rec_scores": [0.9],
    }
    with pytest.raises(PaddleAdapterError, match="not a string"):
        page_evidence_from_result(raw, frame=_demo_frame())


def test_case8_bad_rec_score_refuses():
    raw = {
        "text_word": [["X"]],
        "text_word_boxes": [[[1, 2, 3, 4]]],
        "rec_texts": ["X"],
        "rec_scores": ["not-a-number"],
    }
    with pytest.raises(PaddleAdapterError, match="not a number"):
        page_evidence_from_result(raw, frame=_demo_frame())


# ---------------------------------------------------------------------------
# CASE 7 / M7 — confidence is an ANNOTATION only: `page_texts()` is
# unaffected by every score, high or low.
# ---------------------------------------------------------------------------

def test_case7_confidence_lives_only_on_wordbox_and_raw():
    raw = _demo_result()
    page = page_evidence_from_result(raw, frame=_demo_frame())
    text = "\n".join(line.text for line in page.lines)
    for word in page.words:
        assert word.confidence is not None
    # No numeric confidence value leaks into the derived text.
    scores_as_strings = {f"{s:.4f}" for s in raw["rec_scores"]}
    for token in text.split():
        assert token not in scores_as_strings


@pytest.mark.parametrize("forced_score", [1.0, 0.0])
def test_case7_m7_mutant_score_leaves_pages_byte_identical(forced_score):
    """M7: a mutant that filters words below a confidence threshold would
    drop every word once `forced_score=0.0`, changing `pages` — this proves
    the adapter carries NO such filter, at either extreme."""
    raw = _demo_result()
    baseline_page = page_evidence_from_result(copy.deepcopy(raw), frame=_demo_frame())
    baseline_text = "\n".join(line.text for line in baseline_page.lines)

    mutated = copy.deepcopy(raw)
    mutated["rec_scores"] = [forced_score] * len(mutated["rec_scores"])
    mutated_page = page_evidence_from_result(mutated, frame=_demo_frame())
    mutated_text = "\n".join(line.text for line in mutated_page.lines)

    assert mutated_text == baseline_text
    assert len(mutated_page.words) == len(baseline_page.words)
    assert all(word.confidence == forced_score for word in mutated_page.words)


def test_confidence_out_of_range_refuses():
    raw = {
        "text_word": [["X"]],
        "text_word_boxes": [[[1, 2, 3, 4]]],
        "rec_texts": ["X"],
        "rec_scores": [1.5],
    }
    with pytest.raises(PaddleAdapterError, match=r"\[0, 1\]"):
        page_evidence_from_result(raw, frame=_demo_frame())


# ---------------------------------------------------------------------------
# evidence_from_pages / CASE 11's runtime-secrecy half (adapter side)
# ---------------------------------------------------------------------------

def test_evidence_from_pages_carries_the_declared_extractor_identity():
    raw = _demo_result()
    page = page_evidence_from_result(raw, frame=_demo_frame())
    evidence = evidence_from_pages([page], document_sha256=DOCUMENT_SHA,
                                    runtime={"provider": "vast.ai", "execution_class": "remote_paid"})
    assert evidence.extractor_id == "paddle-ocr"
    assert evidence.model_token == "paddle-ocr+ppocrv5"
    assert evidence.document_sha256 == DOCUMENT_SHA
    text = json.dumps(dict(evidence.runtime))
    for forbidden in ("http://", "127.0.0.1", "ssh", "token"):
        assert forbidden not in text

"""ocr/paddle_adapter.py — PaddleOCR 3.7 result -> canonical evidence
(Phase 2.1 cell P, `docs/agent-handoffs/P21-PADDLE.md` §3, D9, CASE 5, CASE 8).

This module has no idea what a statement is. It reads exactly four arrays
out of a PaddleOCR 3.7 `return_word_box=True` result
(`text_word`, `text_word_boxes`, `rec_texts`, `rec_scores`) and produces
`evidence.PageEvidence` / `evidence.ExtractionEvidence` — nothing about an
amount, a date, a sign or a header is interpreted here, and nothing is
guessed when the shape disagrees with itself: a length mismatch or a box
`evidence.WordBox`/`PageEvidence` itself refuses becomes `PaddleAdapterError`
for the WHOLE page, which the rung turns into a whole-document failure
(`paddle_evidence_malformed`) — never a partial page.

Word confidence (D9's documented wrinkle): PaddleOCR 3.7 scores LINES
(`rec_scores[i]`), not words. Every word on line `i` is stamped with
`rec_scores[i]` as its `WordBox.confidence` — an honestly-labeled per-line
value, never invented per-word precision.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from evidence.canonical import (
    EvidenceError,
    ExtractionEvidence,
    PageEvidence,
    PageFrame,
    WordBox,
    word_id,
)

from .paddle_config import PADDLE_EXTRACTOR_ID, PADDLE_MODEL_TOKEN

__all__ = ["PaddleAdapterError", "evidence_from_pages", "page_evidence_from_result"]


class PaddleAdapterError(RuntimeError):
    """The page's PaddleOCR result cannot be trusted as evidence: a length
    mismatch between `text_word` / `text_word_boxes` / `rec_texts` /
    `rec_scores`, a malformed box shape, or a box that `evidence.WordBox` /
    `evidence.PageEvidence` itself refuses (inverted, degenerate, outside
    the raster — never pre-clamped, never pre-swapped). The rung fails the
    WHOLE document on this; there is no such thing as a partial page."""


def _line_confidence(score: Any, *, line_index: int) -> float:
    try:
        value = float(score)
    except (TypeError, ValueError) as exc:
        raise PaddleAdapterError(f"line {line_index}: rec_scores entry is not a number: {score!r}") from exc
    if not (0.0 <= value <= 1.0):
        raise PaddleAdapterError(f"line {line_index}: rec_scores entry out of [0, 1]: {value!r}")
    return value


def _require_list(raw: Mapping[str, Any], name: str) -> list:
    value = raw.get(name)
    if not isinstance(value, list):
        raise PaddleAdapterError(f"{name!r} must be a list in the PaddleOCR result; got {type(value).__name__}")
    return value


def page_evidence_from_result(raw: Mapping[str, Any], *, frame: PageFrame) -> PageEvidence:
    """One page's PaddleOCR 3.7 result -> `PageEvidence`.

    Words come from `text_word[i][j]` with box `text_word_boxes[i][j] =
    [x0, y0, x1, y1]` (pixels of the raster `frame` describes), `line_ref =
    i`, `confidence = rec_scores[i]`. A word whose text is blank/whitespace
    is DROPPED and counted in `notes` (`"dropped_empty_words:N"`) — never
    invented, never merged into a neighbour. `raw` is stored verbatim
    (`dt_polys`, `rec_polys`, `rec_boxes`, `textline_orientation_angles`
    included) so nothing here is lossy; lines are derived by
    `evidence.group_lines` through `PageEvidence`'s own default.
    """
    text_word = _require_list(raw, "text_word")
    text_word_boxes = _require_list(raw, "text_word_boxes")
    rec_texts = _require_list(raw, "rec_texts")
    rec_scores = _require_list(raw, "rec_scores")
    lengths = {len(text_word), len(text_word_boxes), len(rec_texts), len(rec_scores)}
    if len(lengths) > 1:
        raise PaddleAdapterError(
            "line-count mismatch across the PaddleOCR arrays: "
            f"text_word={len(text_word)} text_word_boxes={len(text_word_boxes)} "
            f"rec_texts={len(rec_texts)} rec_scores={len(rec_scores)}"
        )

    words: list[WordBox] = []
    dropped = 0
    for line_index, (line_words, line_boxes, score) in enumerate(zip(text_word, text_word_boxes, rec_scores)):
        if not isinstance(line_words, list) or not isinstance(line_boxes, list):
            raise PaddleAdapterError(f"line {line_index}: text_word/text_word_boxes entries must be lists")
        if len(line_words) != len(line_boxes):
            raise PaddleAdapterError(
                f"line {line_index}: word/box count mismatch ({len(line_words)} vs {len(line_boxes)})"
            )
        confidence = _line_confidence(score, line_index=line_index)
        for word_index, (text_value, box) in enumerate(zip(line_words, line_boxes)):
            text_str = str(text_value)
            if not text_str.strip():
                dropped += 1
                continue
            if not (isinstance(box, (list, tuple)) and len(box) == 4):
                raise PaddleAdapterError(
                    f"line {line_index} word {word_index}: box must be a 4-element [x0, y0, x1, y1]; got {box!r}"
                )
            try:
                x0, y0, x1, y1 = (float(v) for v in box)
            except (TypeError, ValueError) as exc:
                raise PaddleAdapterError(
                    f"line {line_index} word {word_index}: box entries must be numbers: {box!r}"
                ) from exc
            try:
                words.append(WordBox(
                    word_id=word_id(frame.page_index, line_index, word_index),
                    page_index=frame.page_index,
                    text=text_str,
                    x0=x0, y0=y0, x1=x1, y1=y1,
                    confidence=confidence,
                    line_ref=line_index,
                ))
            except EvidenceError as exc:
                # Inverted / degenerate / out-of-raster boxes are refused by
                # `evidence` itself (never clamped, never swapped here).
                raise PaddleAdapterError(f"line {line_index} word {word_index}: {exc}") from exc

    notes = (f"dropped_empty_words:{dropped}",) if dropped else ()
    try:
        return PageEvidence(frame=frame, words=tuple(words), raw=dict(raw), notes=notes)
    except EvidenceError as exc:
        raise PaddleAdapterError(str(exc)) from exc


def evidence_from_pages(pages: Sequence[PageEvidence], *, document_sha256: str,
                         runtime: Mapping[str, Any]) -> ExtractionEvidence:
    """Assemble the document-level `ExtractionEvidence`. `runtime` is
    provenance ONLY (the worker's echoed identity block + provider /
    execution_class / gpu / worker_contract / dpi, per the rung) — NEVER a
    URL, host, port, request id or token; CASE 11 asserts the JSON directly."""
    return ExtractionEvidence(
        document_sha256=document_sha256,
        extractor_id=PADDLE_EXTRACTOR_ID,
        model_token=PADDLE_MODEL_TOKEN,
        pages=tuple(pages),
        runtime=dict(runtime),
    )

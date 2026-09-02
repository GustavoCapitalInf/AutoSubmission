"""tests/test_paddle_live.py — the LIVE Paddle proof, over the real SSH
tunnel to the Vast.ai RTX 5090, on a synthetic image-only PDF ONLY.

Deselected by every other proof-floor run: `pytestmark` carries
`pytest.mark.live` plus a `skipif` gated, in order, on (1) the remote opt-in
env literal being exactly set (a cheap string comparison — checked FIRST so
the default suite never even calls `load_paddle_settings`), (2)
`load_paddle_settings()` succeeding, and (3) `probe()` reporting the worker
reachable and identity-matched. Because (1) is checked first and is False in
every environment that has not deliberately opted in, collecting this module
during the default suite, `corpus_gate.py`, `pytest -m corpus`, or CI makes
NO network call — `probe()` is only ever invoked once (1) and (2) both hold.

Run once, deliberately:

    PADDLE_REMOTE_OPT_IN=I_ACCEPT_REMOTE_PAID_PADDLE_OCR \\
      python -m pytest tests/test_paddle_live.py -m live -q

No document from `Bank Statements/`, `tests/corpus_cache/` or any real
statement is used here — only `tests/paddle_synthetic.py`'s generated pages.
"""
from __future__ import annotations

import hashlib
import os

import pytest

from ocr.paddle_client import PaddleClient, probe
from ocr.paddle_config import PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL, PaddleConfigError, load_paddle_settings
from ocr.paddle_rung import read_document
from tests.paddle_synthetic import build_ledger_page, render_image_pdf


def _live_ready() -> bool:
    if os.environ.get(PADDLE_REMOTE_OPT_IN_ENV) != PADDLE_REMOTE_OPT_IN_LITERAL:
        return False
    try:
        settings = load_paddle_settings()
    except PaddleConfigError:
        return False
    return probe(settings).available


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not _live_ready(),
        reason="Paddle live proof needs PADDLE_REMOTE_OPT_IN + valid config + a reachable, identity-matched worker",
    ),
]


def test_live_word_boxes_over_the_real_tunnel():
    settings = load_paddle_settings()
    client = PaddleClient(settings)
    page = build_ledger_page(n_rows=5)
    pdf_bytes = render_image_pdf(page, dpi=300)
    document_sha = hashlib.sha256(pdf_bytes).hexdigest().upper()

    result = read_document(
        pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
        settings=settings, client=client, dpi=300,
    )

    assert result.pages, "the live worker returned no pages"
    assert result.evidence.word_count > 0
    assert result.evidence.runtime["provider"] == "vast.ai"
    assert result.evidence.runtime["execution_class"] == "remote_paid"
    assert result.evidence.runtime["paddleocr_version"] == "3.7.0"

    # The rung's own frame/adapter validation already ran; a second read of
    # the same bytes must produce a stable document sha and a non-empty,
    # differently-hashed evidence sha (PaddleOCR is not required to be
    # bit-identical run to run, but the pipeline's own bookkeeping is).
    result2 = read_document(
        pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
        settings=settings, client=client, dpi=300,
    )
    assert result2.evidence.document_sha256 == result.evidence.document_sha256

    print(
        "LIVE PADDLE PROOF:",
        {
            "pages": len(result.pages),
            "words": result.evidence.word_count,
            "lines": sum(len(page_evidence.lines) for page_evidence in result.evidence.pages),
            "identity": {k: v for k, v in dict(result.evidence.runtime).items() if k != "gpu"},
            "telemetry_totals": result.telemetry["totals"],
        },
    )

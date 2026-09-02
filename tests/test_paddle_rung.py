"""Phase 2.1 cell P: `ocr/paddle_rung.py` (§4) — the full offline pipeline
against `tests/paddle_fake_worker.FakeWorker` and `tests/paddle_synthetic.py`.
No `paddleocr`, no real network beyond `127.0.0.1`, no real statement.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from ocr.paddle_client import PaddleClient, PaddleTransportError
from ocr.paddle_config import (
    PADDLE_MODEL_TOKEN,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
    PaddleRefused,
    PaddleSettings,
    load_paddle_settings,
)
from ocr.paddle_rung import read_document
from tests.paddle_fake_worker import FakeWorker
from tests.paddle_synthetic import build_ledger_page, render_image_pdf, synthetic_paddle_result

VAST_ENV = {
    "PADDLE_PROVIDER": "vast.ai", "PADDLE_EXECUTION_CLASS": "remote_paid",
    "PADDLE_VAST_HOST": "example-host.invalid", "PADDLE_VAST_SSH_PORT": "22022",
    "PADDLE_VAST_SSH_USER": "someone", PADDLE_REMOTE_OPT_IN_ENV: PADDLE_REMOTE_OPT_IN_LITERAL,
}


def _settings(url: str) -> PaddleSettings:
    return load_paddle_settings(dict(VAST_ENV, PADDLE_WORKER_URL=url))


@pytest.fixture(scope="module")
def ledger_fixture():
    page = build_ledger_page(n_rows=3)
    dpi = 150  # keep the module fast; not the D5 default, exercised separately below
    pdf_bytes = render_image_pdf(page, dpi=dpi)
    document_sha = hashlib.sha256(pdf_bytes).hexdigest().upper()
    return page, pdf_bytes, document_sha, dpi


def test_end_to_end_synthetic_document(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                                settings=settings, client=client, dpi=dpi)

    assert len(result.pages) == 1
    assert result.pages[0] == page.text
    assert result.page_extractor == [PADDLE_MODEL_TOKEN]
    assert result.evidence.document_sha256 == document_sha
    assert result.evidence.word_count > 0
    assert result.telemetry["totals"]["pages"] == 1
    assert len(fake.requests) == 1

    # CASE 11 / D6: no secret anywhere in the evidence or telemetry.
    from evidence.canonical import canonical_json

    combined = canonical_json({"runtime": dict(result.evidence.runtime), "telemetry": result.telemetry})
    for forbidden in ("example-host.invalid", "22022", "someone", fake.url, "127.0.0.1", "Bearer"):
        assert forbidden not in combined


def test_zero_page_document_yields_empty_evidence_no_invention(monkeypatch, ledger_fixture):
    """A document that rasterises to zero images (a defensive path a real
    PDF should never trigger, but the rung must not invent a page for) ->
    an evidence of zero pages, no `/ocr` request."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    import ocr.paddle_rung as rung_module

    monkeypatch.setattr(rung_module, "rasterize_pdf", lambda pdf, dpi: [])
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                                settings=settings, client=client, dpi=dpi)
    assert result.pages == []
    assert result.page_extractor == []
    assert result.evidence.pages == ()
    assert fake.requests == []  # /version is still called (verify_identity), but no /ocr


def test_case13_opt_in_checked_before_any_network_call(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker() as fake:
        env = {k: v for k, v in VAST_ENV.items() if k != PADDLE_REMOTE_OPT_IN_ENV}
        settings = load_paddle_settings(dict(env, PADDLE_WORKER_URL=fake.url))
        client = PaddleClient(settings)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi)
        assert excinfo.value.reason == "paddle_remote_opt_in_required"
        assert fake.requests == []


def test_case20_customer_scope_refused_before_any_network_call(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="customer",
                           settings=settings, client=client, dpi=dpi)
        assert excinfo.value.reason == "remote_customer_data_refused"
        assert fake.requests == []


def test_case16_identity_mismatch_refuses_before_any_ocr_request(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi)
        assert excinfo.value.reason == "paddle_runtime_mismatch"
        assert fake.requests == []


def test_case18_transport_failure_propagates_and_tries_nothing_else(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(fail_mode="connection_refused") as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleTransportError) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi)
        assert excinfo.value.reason == "paddle_worker_unreachable"


def test_case18_ocr_failure_mid_document_propagates(ledger_fixture):
    """The identity check succeeds (so `/version` is reachable) but every
    `/ocr` request fails — the failure must surface as
    `PaddleTransportError`, not silently produce a partial `PaddleRead`."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(fail_mode="http_500") as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleTransportError):
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi)


def test_paddle_evidence_malformed_fails_the_whole_document(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture

    def broken_result(idx, img):
        result = synthetic_paddle_result(page, dpi=dpi)
        result["rec_scores"] = result["rec_scores"][:-1]  # length mismatch -> PaddleAdapterError
        return result

    with FakeWorker(result_for=broken_result) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi)
        assert excinfo.value.reason == "paddle_evidence_malformed"


def test_m11_no_tempfile_or_path_open_anywhere_in_the_rung():
    import ast
    from pathlib import Path

    source = Path("ocr/paddle_rung.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tempfile":
                    forbidden_calls.append("import tempfile")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            forbidden_calls.append("open(")
    assert forbidden_calls == []


def test_default_dpi_matches_the_pinned_raster_dpi():
    import inspect

    from ocr.paddle_config import PADDLE_RASTER_DPI
    from ocr.paddle_rung import read_document as fn

    default_dpi = inspect.signature(fn).parameters["dpi"].default
    assert default_dpi == PADDLE_RASTER_DPI == 300

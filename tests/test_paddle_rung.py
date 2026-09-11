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
import ocr.paddle_rung as rung_module
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
        client = PaddleClient(settings, environ=VAST_ENV)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                                settings=settings, client=client, dpi=dpi, environ=VAST_ENV)

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
    """A document BOTH the rasteriser and PyMuPDF agree has zero pages (a
    defensive path a real PDF should never trigger, but the rung must not
    invent a page for) -> an evidence of zero pages, no `/ocr` request.

    MINOR-4 (`PHASE2_P21PADDLE_REVIEW.md`): this used to monkeypatch only
    `rasterize_pdf` to return `[]` against a PDF PyMuPDF still sees as ONE
    page — exactly the page-count DISAGREEMENT MINOR-4 requires the rung to
    refuse (`paddle_frame_mismatch`), not silently publish short. The
    genuine 0-vs-0 case the card specifies needs BOTH sides to agree on
    zero, so this fakes PyMuPDF's own page count too."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    import ocr.paddle_rung as rung_module

    class _ZeroPageDocument:
        page_count = 0

        def close(self) -> None:
            pass

        def __getitem__(self, index):  # pragma: no cover - never reached at 0 pages
            raise IndexError(index)

    monkeypatch.setattr(rung_module, "rasterize_pdf", lambda pdf, dpi: [])
    monkeypatch.setattr(rung_module.fitz, "open", lambda **kwargs: _ZeroPageDocument())
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                                settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
    assert result.pages == []
    assert result.page_extractor == []
    assert result.evidence.pages == ()
    assert fake.requests == []  # /version is still called (verify_identity), but no /ocr


def test_minor4_page_count_disagreement_refuses_never_publishes_short(ledger_fixture):
    """The disagreement case itself: the rasteriser under-reports (or
    PyMuPDF over-reports) relative to the other. Reproduced exactly as the
    review measured it — a rasteriser returning ONE fewer image than
    PyMuPDF's real page count on the actual fixture PDF."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    import ocr.paddle_rung as rung_module

    real_rasterize = rung_module.rasterize_pdf
    real_images = real_rasterize(pdf_bytes, dpi=dpi)
    assert len(real_images) >= 1

    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(rung_module, "rasterize_pdf", lambda pdf, dpi: [])
            with pytest.raises(PaddleRefused) as excinfo:
                read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                               settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
        assert excinfo.value.reason == "paddle_frame_mismatch"
        assert fake.requests == []  # no /ocr request for a document refused before rung step 5


def test_case13_opt_in_checked_before_any_network_call(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker() as fake:
        env = {k: v for k, v in VAST_ENV.items() if k != PADDLE_REMOTE_OPT_IN_ENV}
        settings = load_paddle_settings(dict(env, PADDLE_WORKER_URL=fake.url))
        # No pre-built client: settings.remote_opt_in is already False here, so
        # read_document's own check_remote_authorization must refuse before
        # ever constructing one (a pre-built PaddleClient would now refuse at
        # ITS OWN construction, which is a different, MAJOR-2 assertion made
        # elsewhere — this test stays about read_document's ordering).
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, dpi=dpi)
        assert excinfo.value.reason == "paddle_remote_opt_in_required"
        assert fake.requests == []


def test_case20_customer_scope_refused_before_any_network_call(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker() as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="customer",
                           settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
        assert excinfo.value.reason == "remote_customer_data_refused"
        assert fake.requests == []


def test_r2_read_document_refuses_a_hand_built_customer_opt_in_with_only_the_remote_literal_present(ledger_fixture):
    """R-2 (`PHASE2_P21PADDLE_REVIEW.md` re-review): the customer-side twin
    of MAJOR-2's remote-half test, at the `read_document` level — a
    hand-built `PaddleSettings` claiming `customer_data_opt_in=True`, with
    ONLY the remote literal present in the environment, must be refused
    before any `/ocr` request. This is the exact case the reversal mutant
    (`customer_data_opt_in = settings.customer_data_opt_in`, dropping the
    re-derivation) passed undetected without this test."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = PaddleSettings(
            provider="vast.ai", execution_class="remote_paid", vast_host="h", vast_ssh_port=1,
            vast_ssh_user="u", remote_opt_in=True, customer_data_opt_in=True, worker_url=fake.url,
            worker_port=8765, tunnel_local_port=18765, worker_token=None, runtime_dir=".paddle_runtime",
        )
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="customer",
                          settings=settings, dpi=dpi, environ=VAST_ENV)  # VAST_ENV carries only the remote literal
        assert excinfo.value.reason == "remote_customer_data_refused"
        assert fake.requests == []


def test_case16_identity_mismatch_refuses_before_any_ocr_request(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(identity_overrides={"provider": "local", "execution_class": "local_free"}) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
        assert excinfo.value.reason == "paddle_runtime_mismatch"
        assert fake.requests == []


def test_case18_transport_failure_propagates_and_tries_nothing_else(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(fail_mode="connection_refused") as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        with pytest.raises(PaddleTransportError) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
        assert excinfo.value.reason == "paddle_worker_unreachable"


def test_case18_ocr_failure_mid_document_propagates(ledger_fixture):
    """The identity check succeeds (so `/version` is reachable) but every
    `/ocr` request fails — the failure must surface as
    `PaddleTransportError`, not silently produce a partial `PaddleRead`."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(fail_mode="http_500") as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        with pytest.raises(PaddleTransportError):
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi, environ=VAST_ENV)


def test_paddle_evidence_malformed_fails_the_whole_document(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture

    def broken_result(idx, img):
        result = synthetic_paddle_result(page, dpi=dpi)
        result["rec_scores"] = result["rec_scores"][:-1]  # length mismatch -> PaddleAdapterError
        return result

    with FakeWorker(result_for=broken_result) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        with pytest.raises(PaddleRefused) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                           settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
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


# ---------------------------------------------------------------------------
# MAJOR-1 / MINOR-6: the runtime block is a closed whitelist, and
# evidence_sha256 is stable across a cold and a warm read of the SAME bytes
# ---------------------------------------------------------------------------

def test_major1_runtime_block_is_the_closed_whitelist_never_the_raw_reply(ledger_fixture):
    """A worker echoing UNKNOWN /version keys (a URL, a host, an operator
    note) must never see any of them survive into `evidence.runtime` —
    proven directly (reproducing the review's finding), not merely by
    asserting the module constant's shape."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    injected = {
        "worker_url": "http://198.51.100.7:8765",
        "ssh_host": "attacker.example",
        "operator_note": "PP-OCRv6 actually",
    }
    with FakeWorker(identity_overrides=injected,
                    result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                               settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
    assert set(result.evidence.runtime) <= rung_module.RUNTIME_FIELDS
    assert "worker_url" not in result.evidence.runtime
    assert "ssh_host" not in result.evidence.runtime
    assert "operator_note" not in result.evidence.runtime
    from evidence.canonical import canonical_json

    text = canonical_json(dict(result.evidence.runtime))
    assert "198.51.100.7" not in text
    assert "attacker.example" not in text
    assert "PP-OCRv6 actually" not in text


def test_r3_runtime_fields_is_the_exact_whitelist_including_data_scope():
    """R-3 (`PHASE2_P21PADDLE_REVIEW.md` re-review): `data_scope` joined the
    closed whitelist — this pins the whole set exactly, not merely a subset
    check, so a future accidental removal (or an accidental widening) of any
    member is caught here."""
    assert rung_module.RUNTIME_FIELDS == frozenset({
        "paddleocr_version", "paddlepaddle_version", "ocr_version",
        "text_detection_model_name", "text_recognition_model_name", "pipeline_switches",
        "gpu", "cuda_compiled", "python_version",
        "provider", "execution_class", "worker_contract", "dpi", "data_scope",
    })


def test_r3_evidence_runtime_records_the_declared_data_scope(ledger_fixture):
    """`data_scope` in `evidence.runtime` comes from `read_document`'s OWN
    argument — never from the worker — so an artifact this rung produces is
    self-describing about what its producer claimed it was sending."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        client = PaddleClient(settings, environ=VAST_ENV)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                               settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
    assert result.evidence.runtime["data_scope"] == "synthetic"


def test_minor6_evidence_sha256_stable_across_cold_and_warm_worker_identity(ledger_fixture):
    """The SAME document read through two workers that differ ONLY in
    `model_loaded` / `worker_started_at` (a cold vs. a warm read of the real
    worker, in practice) must produce the SAME `evidence_sha256` — those two
    fields are deliberately excluded from `RUNTIME_FIELDS` (MINOR-6)."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    shas = []
    for model_loaded, started_at in ((False, 100.0), (True, 200.0)):
        overrides = {"model_loaded": model_loaded, "worker_started_at": started_at}
        with FakeWorker(identity_overrides=overrides,
                        result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
            settings = _settings(fake.url)
            client = PaddleClient(settings, environ=VAST_ENV)
            result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                                   settings=settings, client=client, dpi=dpi, environ=VAST_ENV)
            shas.append(result.evidence.evidence_sha256)
    assert shas[0] == shas[1]


# ---------------------------------------------------------------------------
# MINOR-5: a contract-shaped-but-malformed envelope refuses typed, never a
# bare KeyError; a mismatched echoed page_index refuses too
# ---------------------------------------------------------------------------

class _BadEnvelopeClient:
    """Wraps a real client; `version()` passes through untouched (so
    identity verification succeeds), `ocr_page` returns whatever the test
    wants regardless of what was asked."""

    def __init__(self, real, bad_response):
        self._real = real
        self._bad_response = bad_response

    def version(self):
        return self._real.version()

    def ocr_page(self, *args, **kwargs):
        return self._bad_response


def test_minor5_missing_raw_refuses_typed_not_a_bare_keyerror(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        real_client = PaddleClient(settings, environ=VAST_ENV)
        bad_client = _BadEnvelopeClient(real_client, {"image": {}, "timing": {}, "page_index": 0})
        with pytest.raises(PaddleTransportError) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                          settings=settings, client=bad_client, dpi=dpi, environ=VAST_ENV)
        assert excinfo.value.reason == "paddle_worker_unreachable"
        assert excinfo.value.error_type == "MalformedEnvelope"


def test_minor5_mismatched_page_index_refuses(ledger_fixture):
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        real_client = PaddleClient(settings, environ=VAST_ENV)
        bad_client = _BadEnvelopeClient(
            real_client, {"raw": synthetic_paddle_result(page, dpi=dpi), "image": {}, "timing": {}, "page_index": 7}
        )
        with pytest.raises(PaddleTransportError) as excinfo:
            read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                          settings=settings, client=bad_client, dpi=dpi, environ=VAST_ENV)
        assert excinfo.value.error_type == "MalformedEnvelope"


# ---------------------------------------------------------------------------
# P23-WAVE (Phase 2.3, case 14): the technical-telemetry field — an APPEND to
# this file, because the figures it carries are the ones THIS rung measures.
# Cell T named the missing field as its STOP: the rung had the numbers and
# nothing carried them to the row. The field is one optional attribute on
# `StatementMarkdown`, set by `ocr/pipeline.py` from `PaddleRead.telemetry`,
# TRANSIENT by ruling (never persisted; a cache hit carries none).
# ---------------------------------------------------------------------------


def test_the_rung_measures_exactly_the_figures_the_row_columns_need(ledger_fixture):
    """The four row columns are projections of these keys and of nothing else.
    Pinning the SHAPE here means a rung that stopped measuring one of them
    fails at its own source rather than silently emptying a report column."""
    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        settings = _settings(fake.url)
        result = read_document(pdf_bytes, document_sha256=document_sha, data_scope="synthetic",
                                settings=settings, client=PaddleClient(settings, environ=VAST_ENV),
                                dpi=dpi, environ=VAST_ENV)
    totals = result.telemetry["totals"]
    assert set(totals) == {"pages", "inference_ms_total", "bytes_sent_total", "bytes_received_total"}
    assert totals["pages"] == 1 and totals["bytes_sent_total"] > 0 and totals["bytes_received_total"] > 0
    page_row = result.telemetry["pages"][0]
    for name in ("page_index", "inference_ms", "bytes_sent", "bytes_received", "gpu_memory_used_mib"):
        assert name in page_row, name
    # figures only: nothing derived from the document's content is in here
    serialized = json.dumps(result.telemetry)
    assert page.text.split("\n")[0] not in serialized


def test_the_pipeline_attaches_the_rung_telemetry_verbatim_and_markdown_is_byte_identical(
    ledger_fixture, monkeypatch,
):
    """The one line in `ocr/pipeline.py`. `to_markdown()` is the extraction
    input for every parser and the corpus artifacts are pinned to it, so the
    field must not add a byte to it — the same rule O-3's flags follow.

    Hermetic in this file's house style: every `PADDLE_*` name in the real
    environment (the gitignored `.env` of a developer machine carries real
    ones) is blanked first, then exactly this test's values are set."""
    import os

    from ocr.document import StatementMarkdown
    from ocr.pipeline import parse_statement

    page, pdf_bytes, document_sha, dpi = ledger_fixture
    with FakeWorker(result_for=lambda idx, img: synthetic_paddle_result(page, dpi=dpi)) as fake:
        for name in list(os.environ):
            if name.startswith("PADDLE_"):
                monkeypatch.setenv(name, "")
        for name, value in dict(VAST_ENV, PADDLE_WORKER_URL=fake.url).items():
            monkeypatch.setenv(name, value)
        document = parse_statement(
            pdf_bytes, source_file="synthetic.pdf", dpi=dpi, force_ocr=True,
            allow_local_ocr=False, allow_visual_ocr=False, allow_paddle_ocr=True,
            paddle_data_scope="synthetic",
        )
    assert document is not None
    assert document.extraction_telemetry is not None
    assert document.extraction_telemetry["totals"]["pages"] == len(document.pages)
    bare = StatementMarkdown(
        source_file=document.source_file, model=document.model, pages=list(document.pages),
        page_integrity=list(document.page_integrity), page_extractor=list(document.page_extractor),
        evidence=document.evidence,
    )
    assert bare.to_markdown() == document.to_markdown()
    assert bare.extraction_telemetry is None


def test_every_other_rung_leaves_the_telemetry_field_unset():
    """`None` means "this read measured no request", and it must stay the
    honest default of every rung that makes none."""
    from ocr.document import StatementMarkdown

    assert StatementMarkdown(source_file="x.pdf", model="native-pdf-text").extraction_telemetry is None


def test_the_telemetry_field_refuses_a_wrong_shape():
    from ocr.config import ProvenanceTokenError
    from ocr.document import StatementMarkdown

    with pytest.raises(ProvenanceTokenError, match="extraction_telemetry"):
        StatementMarkdown(source_file="x.pdf", model="native-pdf-text",
                          extraction_telemetry="not a dict")


# ---------------------------------------------------------------------------
# P23-WAVE (case 12): the worker's retention DECLARATION, read by the client.
# ---------------------------------------------------------------------------


def test_the_worker_declares_retention_none_on_version():
    from ocr.paddle_client import RETENTION_NONE, retention_declaration
    from ocr.paddle_worker import RETENTION_POLICY, version_payload

    payload = version_payload({"provider": "vast.ai", "execution_class": "remote_paid"})
    assert payload["retention"] == RETENTION_POLICY == RETENTION_NONE
    assert retention_declaration(payload) == RETENTION_NONE


@pytest.mark.parametrize("value", [None, "", "none-ish", "we keep nothing", True, 0, {"policy": "none"}])
def test_a_worker_that_does_not_declare_retention_none_reads_as_undeclared(value):
    """The shape bound is total: only the exact string passes, so a worker
    cannot satisfy the attestation with a value that merely looks reassuring."""
    from ocr.paddle_client import retention_declaration

    payload = {} if value is None else {"retention": value}
    assert retention_declaration(payload) is None

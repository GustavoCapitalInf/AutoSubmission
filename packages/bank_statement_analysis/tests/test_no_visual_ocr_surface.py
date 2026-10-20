"""No route, page control or worker branch offers visual OCR any more (owner ruling, 2026-10-13: the product uses no
model; model-code removal, slice S1). Auto reads and analyses exactly as Deterministic only, a scanned page with no
usable text ends in the fixed no-text refusal without one outbound connection, and an upload that still asks for
Force visual OCR is refused before anything is stored. Fabricated PDFs only."""
from __future__ import annotations

import ast
import io
import json
import re
import shutil
import socket
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "webapp/templates/index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "webapp/static/app.js").read_text(encoding="utf-8")

#: The advice the page used to give, which pointed at readers that no longer exist.
RETIRED_ADVICE = (
    "Enable the configured visual fallback",
    "select Force visual OCR",
    "Turn on visual OCR",
    "retry with the OCR service",
    "turn on Force visual OCR",
)


# --- the page ---------------------------------------------------------------------------------------------------------


def test_the_upload_page_offers_no_visual_ocr():
    assert "forceOcrToggle" not in INDEX_HTML
    assert 'name="force_ocr"' not in INDEX_HTML and "force_ocr" not in INDEX_HTML
    assert not re.search(r"visual\s+OCR", INDEX_HTML, re.IGNORECASE)
    # The hint names the readers that remain, and the Parsing-mode control stays.
    assert "scanned pages are read with local OCR on this machine" in INDEX_HTML
    assert 'name="parseMode" value="auto"' in INDEX_HTML and 'name="parseMode" value="deterministic"' in INDEX_HTML


def test_the_dashboard_sends_no_force_ocr_field_and_gives_none_of_the_retired_advice():
    assert "force_ocr" not in APP_JS and "forceOcrToggle" not in APP_JS
    for advice in RETIRED_ADVICE:
        assert advice.lower() not in APP_JS.lower(), advice
    # The two refusals a user sees still match their fixed texts (the prefix regexes are unchanged).
    assert "/no deterministic parser matched/i" in APP_JS
    assert "/native PDF text unavailable|too sparse|no native text/i" in APP_JS


# --- the upload route -------------------------------------------------------------------------------------------------


@pytest.fixture
def scratch_store(monkeypatch, tmp_path):
    """A job store of its own, installed where the routes read it."""
    from webapp import app as webapp_app
    from webapp.jobs import JobStore
    from webapp.storage import Storage

    store = JobStore(Storage(tmp_path / "data"))
    monkeypatch.setattr(webapp_app, "store", store)
    return store


def _fabricated_pdf() -> bytes:
    import fitz

    with fitz.open() as document:
        document.new_page().insert_text((72, 72), "FABRICATED NATIVE TEXT")
        return document.tobytes()


def _stored(store) -> tuple[int, int, int]:
    """(job rows, document rows, PDFs on disk) of the store."""
    data_dir = Path(store.storage.data_dir)
    with sqlite3.connect(str(data_dir / "webapp.db")) as conn:
        jobs = conn.execute("SELECT count(*) FROM jobs").fetchone()[0]
        documents = conn.execute("SELECT count(*) FROM documents").fetchone()[0]
    return jobs, documents, sum(1 for _ in data_dir.rglob("*.pdf"))


@pytest.mark.parametrize("payload", ["valid", "not_a_pdf"])
def test_an_upload_asking_for_force_visual_ocr_is_refused_before_anything_is_stored(
        monkeypatch, scratch_store, payload):
    from webapp import app as webapp_app

    monkeypatch.setattr(webapp_app, "_enqueue_job", lambda *a: pytest.fail("a job was queued"))
    monkeypatch.setattr(webapp_app, "inspect_pdf", lambda *a, **k: pytest.fail("the upload was read"))
    before = _stored(scratch_store)
    raw = _fabricated_pdf() if payload == "valid" else b"not a pdf"
    response = webapp_app.app.test_client().post(
        "/upload", data={"force_ocr": "1", "files": (io.BytesIO(raw), "fabricated.pdf")},
        content_type="multipart/form-data")
    assert response.status_code == 400
    assert response.get_json() == {"error": webapp_app.FORCE_OCR_REMOVED}
    assert _stored(scratch_store) == before


def test_an_upload_without_the_flag_is_accepted_and_records_force_ocr_false(monkeypatch, scratch_store):
    from webapp import app as webapp_app

    queued = []
    monkeypatch.setattr(webapp_app, "_enqueue_job", lambda *args: queued.append(args))
    response = webapp_app.app.test_client().post(
        "/upload", data={"force_ocr": "0", "files": (io.BytesIO(_fabricated_pdf()), "fabricated.pdf")},
        content_type="multipart/form-data")
    assert response.status_code == 200
    job = response.get_json()["jobs"][0]
    assert job["force_ocr"] is False and queued[0][3] is False
    assert scratch_store.get(job["id"]).force_ocr is False


def test_the_settings_offer_no_visual_key(scratch_store):
    from webapp import app as webapp_app

    response = webapp_app.app.test_client().get("/api/settings")
    assert response.status_code == 200
    keys = json.dumps(sorted(response.get_json()["settings"]))
    assert not re.search(r"visual|force_ocr|ocr_model|gemini|paddle", keys, re.IGNORECASE)


# --- the worker -------------------------------------------------------------------------------------------------------


def test_the_worker_imports_no_model_reader_and_names_no_router():
    """webapp/worker.py imports nothing of the visual pair, the OCR service's settings or the escalation router."""
    tree = ast.parse((ROOT / "webapp/worker.py").read_text(encoding="utf-8"))
    modules = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    forbidden = ("vlm", "openai", "google", "ocr.config", "ocr.visual_pair_config", "ocr.escalation",
                 "ocr.ocr_client", "ocr.paddle_client", "ocr.private_artifacts", "analysis.extract")
    assert not {m for m in modules if any(m == f or m.startswith(f + ".") for f in forbidden)}
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"decide", "EscalationRouter", "router_inputs", "check_remote_authorization",
                        "extract_visual_pair", "analyze_visual_pair", "load_visual_pair_settings"}


@pytest.fixture
def no_outbound(monkeypatch):
    """Every outbound connection is refused and counted."""
    attempts = []

    def refuse(self, address):  # noqa: ANN001
        attempts.append(type(address).__name__)
        raise ConnectionRefusedError("an outbound connection was attempted")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    return attempts


@pytest.fixture
def worker_store(tmp_path):
    from webapp.jobs import JobStore
    from webapp.storage import Storage

    return JobStore(Storage(tmp_path / "data"))


def _image_only_pdf() -> bytes:
    import fitz

    with fitz.open() as document:
        page = document.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 64, 64), 0)
        pixmap.clear_with(255)
        page.insert_image(page.rect, pixmap=pixmap)
        return document.tobytes()


def _run(store, pdf: bytes, mode: str):
    from webapp.worker import run_job

    job = store.create("fabricated.pdf", pdf_bytes=pdf, parse_mode=mode)
    run_job(job.id, pdf, "fabricated.pdf", store, False, mode)
    return store.get(job.id)


NO_TEXT = "native PDF text unavailable or too sparse, and local Tesseract OCR did not produce usable statement text"


@pytest.mark.parametrize("mode", ["auto", "deterministic"])
def test_an_image_only_page_ends_in_the_no_text_refusal_with_no_outbound_connection(
        monkeypatch, worker_store, no_outbound, mode):
    """N5 with the Tesseract rung stubbed to read nothing (the real rung is the next test): the native rung finds no
    text, nothing else is tried, and the job ends in the fixed refusal in either mode."""
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
    job = _run(worker_store, _image_only_pdf(), mode)
    assert (job.status, job.analysis, job.analysis_error, job.parse_model) == (
        "done", None, NO_TEXT, "deterministic-native-preflight")
    assert no_outbound == []


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="local Tesseract not installed")
@pytest.mark.parametrize("mode", ["auto", "deterministic"])
def test_local_tesseract_reads_an_image_only_page_on_the_machine_with_no_outbound_connection(
        worker_store, no_outbound, mode):
    job = _run(worker_store, _image_only_pdf(), mode)
    assert (job.status, job.analysis_error) == ("done", NO_TEXT)
    assert no_outbound == []


# The printed shape of the Woodforest layout (tests/test_woodforest.py's SIMPLE fixture), one line per text block.
_CLAIMED_LINES = [
    "00131374040126102556",
    "Statement Period: March 01  - March 31, 2054 Page 1 of 6",
    "Account Information & Customer Service 1-(877) 968-7962",
    "P.O. Box 7889 The Woodlands, TX 77387",
    "Visit Us Online at www.woodforest.com",
    "Summary of Accounts",
    "ACCOUNT TYPE AND NUMBER BALANCE FORWARD TOTAL DEBITS TOTAL CREDITS CLOSING BALANCE",
    "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00",
    "Business Simple Checking 1205009515",
    "Transactions",
    "Date Credits Debits Balance Description",
    "03-02 200.00 800.00 POS DB ONE",
    "03-03 500.00 1,300.00 POS CR TWO",
    "03-04 100.00 1,200.00 POS DB THREE",
]


def _text_pdf(lines, gap) -> bytes:
    import fitz

    with fitz.open() as document:
        page = document.new_page()
        y = 40.0
        for line in lines:
            page.insert_text((36, y), line, fontsize=8)
            y += gap
        return document.tobytes()


def test_auto_equals_deterministic_on_a_claimed_native_statement(worker_store, no_outbound):
    """The two modes publish the same reading and the same analysis, apart from the parse_mode stamp."""
    pdf = _text_pdf(_CLAIMED_LINES, 28.0)
    auto, deterministic = _run(worker_store, pdf, "auto"), _run(worker_store, pdf, "deterministic")
    assert auto.analysis is not None and auto.analysis_error is None
    assert (auto.analysis["parse_mode"], deterministic.analysis["parse_mode"]) == ("auto", "deterministic")
    strip = lambda analysis: {k: v for k, v in analysis.items() if k != "parse_mode"}  # noqa: E731
    assert strip(auto.analysis) == strip(deterministic.analysis)
    assert (auto.markdown, auto.html, auto.parse_model, auto.status) == (
        deterministic.markdown, deterministic.html, deterministic.parse_model, deterministic.status)
    assert no_outbound == []


def test_auto_equals_deterministic_on_an_unclaimed_native_document(worker_store, no_outbound):
    lines = ["FABRICATED HOLDINGS LIMITED", "A fabricated memorandum, not a bank statement."] + [
        f"Fabricated filler sentence number {n} for the text volume gate." for n in range(40)]
    pdf = _text_pdf(lines, 12.0)
    auto, deterministic = _run(worker_store, pdf, "auto"), _run(worker_store, pdf, "deterministic")
    assert (auto.analysis, deterministic.analysis) == (None, None)
    assert auto.analysis_error == deterministic.analysis_error == "no deterministic parser matched this statement"
    assert (auto.markdown, auto.parse_model) == (deterministic.markdown, deterministic.parse_model)
    assert no_outbound == []

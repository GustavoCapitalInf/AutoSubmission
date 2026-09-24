# D-1 delta: JobStore persists through webapp.storage now, so tests inject a
# tmp-dir Storage instead of the bare JobStore() constructor (which would
# write to the real data dir).
#
# O-1 delta: the worker's private preflight ladder (_native_statement /
# _local_ocr_statement) is gone — routing lives solely in
# ocr.pipeline.parse_statement. Tests that previously patched the worker's
# helpers now either patch the ladder's rungs at their one home
# (ocr.pipeline._native_statement / ocr.pipeline.parse_local_tesseract) and
# run the REAL unified ladder, or patch webapp.worker.parse_statement with a
# fake honoring the ladder's capability-flag contract. Worker fakes accept
# **kwargs because the worker now passes profile/on_stage/capability flags.
import pytest

from webapp.jobs import JobStore
from webapp.storage import Storage
from webapp.worker import document_to_json, run_job


@pytest.fixture
def store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))
from analysis.detect import DetectionResult
from analysis.metrics import Metrics
from analysis.pipeline import DocumentIntegrity, DocumentReport, Quality, Report
from analysis.reconcile import ReconResult
from analysis.schema import Statement


class _FakeDoc:
    model = "test-model"
    pages = ["# Hello"]

    def to_markdown(self):
        return "# Hello"


def test_run_job_success(monkeypatch, store):
    job = store.create("s.pdf")

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, **kwargs):
        if on_page_delta:
            on_page_delta(0, "streamed chunk")  # simulate live streaming of page 1
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "auto"}
    assert fetched.analysis_error is None
    assert fetched.parse_model == "test-model"
    assert "streamed chunk" in fetched.live_text  # worker forwarded the stream


def test_run_job_failure(monkeypatch, store):
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file="", **kwargs):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    # #WORKERPRIV: the durable job error is the exception's CLASS NAME and the
    # named stage that raised, never `str(e)`. The full contract (and the proof
    # that no statement text can cross) lives in tests/test_worker_privacy.py.
    assert fetched.error == (
        "reading stage failed: RuntimeError "
        "(message withheld; an exception message can quote statement text)"
    )
    assert "connection error" not in fetched.error


@pytest.mark.parametrize("mode", ["auto", "deterministic"])
def test_forced_pair_skips_all_legacy_readers(monkeypatch, store, mode):
    job = store.create("forced.pdf")
    calls = []
    monkeypatch.setattr("webapp.worker.inspect_pdf", lambda *a, **k: pytest.fail("native text probe ran"))
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *a, **k: pytest.fail("legacy reader ran"))
    monkeypatch.setattr("webapp.worker._read_visual_pair", lambda *a, **k: calls.append("pair") or _FakeDoc())
    monkeypatch.setattr("webapp.worker.analyze_document", lambda *a, **k: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda report: {"quality": {"level": "transaction_level"}})
    run_job(job.id, b"%PDF-fake", "forced.pdf", store, force_ocr=True, parse_mode=mode)
    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert calls == ["pair"]
    assert fetched.analysis["parse_mode"] == mode


def test_explicit_legacy_flag_uses_old_visual_rung(monkeypatch, store):
    monkeypatch.setenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", "1")
    job = store.create("legacy.pdf")
    calls = []
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *a, **k: calls.append(k) or _FakeDoc())
    monkeypatch.setattr("webapp.worker._read_visual_pair", lambda *a, **k: pytest.fail("pair ran"))
    monkeypatch.setattr("webapp.worker.analyze_document", lambda *a, **k: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda report: {"quality": {"level": "transaction_level"}})
    run_job(job.id, b"%PDF-fake", "legacy.pdf", store, force_ocr=True, parse_mode="deterministic")
    assert store.get(job.id).status == "done"
    assert len(calls) == 1
    assert calls[0]["force_ocr"] is True
    assert calls[0]["allow_visual_ocr"] is True


def test_deterministic_run_reports_native_text_required_without_force_ocr(monkeypatch, store):
    job = store.create("scan.pdf")

    # Ladder rungs at their one home: nothing offline matches, and the
    # deterministic preflight (allow_visual_ocr=False) must return None
    # rather than reach for visual OCR.
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("visual OCR rung must not run"))

    run_job(job.id, b"%PDF-fake", "scan.pdf", store, force_ocr=False, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis is None
    assert "native PDF text unavailable" in (fetched.analysis_error or "")
    assert fetched.parse_model == "deterministic-native-preflight"


def test_auto_run_uses_local_ocr_before_remote_visual_ocr(monkeypatch, store):
    # The REAL unified ladder: native misses, the webapp's tesseract
    # capability (allow_local_ocr=True) serves the scan, and the remote
    # visual rung is never reached.
    job = store.create("scan.pdf")

    class LocalDoc(_FakeDoc):
        model = "local-tesseract-ocr"

    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda pdf_bytes, source_file="", **k: LocalDoc())
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("remote visual OCR must not run"))
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "scan.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.parse_model == "local-tesseract-ocr"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "auto"}


def test_deterministic_run_uses_local_ocr_before_reporting_no_text(monkeypatch, store):
    job = store.create("scan.pdf")

    class LocalDoc(_FakeDoc):
        model = "local-tesseract-ocr"

    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda pdf_bytes, source_file="", **k: LocalDoc())
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("remote OCR should not run"))
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "scan.pdf", store, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.parse_model == "local-tesseract-ocr"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "deterministic"}
    assert fetched.analysis_error is None


def test_document_to_json_includes_document_integrity():
    report = Report(
        statement=Statement(bank="Test Bank"),
        reconciliation=ReconResult(ok=False, summary_ok=False, issues=[]),
        metrics=Metrics(),
        detection=DetectionResult(known_funders=[], recurring_debits=[]),
        quality=Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=False,
            corporate_use="manual_review_required",
        ),
        integrity=DocumentIntegrity(
            risk_level="high",
            flags=["summary_math_inconsistent"],
            notes=["bank-stated summary totals do not reconcile"],
            possible_document_issue=True,
        ),
        model_used="test-model",
        escalated=False,
    )

    body = document_to_json(DocumentReport(accounts=[report]))

    assert body["integrity"]["risk_level"] == "high"
    assert body["integrity"]["possible_document_issue"] is True

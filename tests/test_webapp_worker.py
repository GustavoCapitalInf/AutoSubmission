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
from webapp.worker import report_to_json, run_job


@pytest.fixture
def store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))
from analysis.detect import DetectionResult
from analysis.metrics import Metrics
from analysis.pipeline import DocumentIntegrity, Quality, Report
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
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

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
    assert fetched.error == "connection error"


def test_deterministic_run_prefers_native_before_forced_visual_ocr(monkeypatch, store):
    # The REAL unified ladder routes: the native rung (patched at its one home
    # in ocr.pipeline) matches, so neither tesseract nor visual OCR ever runs
    # even though the operator forced OCR in deterministic mode.
    job = store.create("td.pdf")

    monkeypatch.setattr("ocr.pipeline._native_statement",
                        lambda pdf_bytes, source_file="": _FakeDoc())
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract",
                        lambda *a, **k: pytest.fail("tesseract rung must not run"))
    monkeypatch.setattr("ocr.pipeline.load_settings",
                        lambda **k: pytest.fail("visual OCR rung must not run"))
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "td.pdf", store, force_ocr=True, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "deterministic"}


def test_deterministic_run_retries_visual_ocr_when_native_parser_does_not_match(monkeypatch, store):
    # Mode policy: deterministic + Force OCR escalates to the visual rung when
    # the native read exists but fails analysis. The ladder contract is
    # asserted through the capability flags the worker passes.
    job = store.create("unsupported.pdf")
    calls = []

    class NativeDoc(_FakeDoc):
        model = "native-pdf-text"

    class OcrDoc(_FakeDoc):
        model = "ocr-model"

    def fake_parse(pdf_bytes, source_file="", force_ocr=False, allow_visual_ocr=True, **kwargs):
        calls.append({"force_ocr": force_ocr, "allow_visual_ocr": allow_visual_ocr})
        return OcrDoc() if force_ocr else NativeDoc()

    def fake_analyze(markdown, parse_mode="auto", **kwargs):
        if len(calls) < 2:
            raise RuntimeError("no deterministic parser matched this statement")
        return object()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", fake_analyze)
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "unsupported.pdf", store, force_ocr=True, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "deterministic"}
    assert fetched.analysis_error is None
    # First the offline preflight (visual rung withheld), then the escalation.
    assert calls == [
        {"force_ocr": False, "allow_visual_ocr": False},
        {"force_ocr": True, "allow_visual_ocr": True},
    ]


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
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

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
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto", **kwargs: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "scan.pdf", store, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.parse_model == "local-tesseract-ocr"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "deterministic"}
    assert fetched.analysis_error is None


def test_report_to_json_includes_document_integrity():
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

    body = report_to_json(report)

    assert body["integrity"]["risk_level"] == "high"
    assert body["integrity"]["possible_document_issue"] is True

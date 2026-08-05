from types import SimpleNamespace

from webapp.jobs import JobStore
from webapp.worker import report_to_json, run_job
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


def test_run_job_success(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        if on_page_delta:
            on_page_delta(0, "streamed chunk")  # simulate live streaming of page 1
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto": object())
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


def test_run_job_failure(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)
    monkeypatch.setattr(
        "webapp.worker.load_analysis_settings",
        lambda: SimpleNamespace(max_external_extraction_attempts=0),
    )

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"


def test_deterministic_run_prefers_native_before_forced_visual_ocr(monkeypatch):
    store = JobStore()
    job = store.create("td.pdf")
    calls = []

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        calls.append(force_ocr)
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf_bytes, filename: _FakeDoc())
    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto": object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "td.pdf", store, force_ocr=True, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "deterministic"}
    assert calls == []


def test_deterministic_run_retries_visual_ocr_when_native_parser_does_not_match(monkeypatch):
    store = JobStore()
    job = store.create("unsupported.pdf")
    calls = []

    class NativeDoc(_FakeDoc):
        model = "native-pdf-text"

    class OcrDoc(_FakeDoc):
        model = "ocr-model"

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        calls.append(force_ocr)
        return OcrDoc()

    def fake_analyze(markdown, parse_mode="auto"):
        if not calls:
            raise RuntimeError("no deterministic parser matched this statement")
        return object()

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf_bytes, filename: NativeDoc())
    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", fake_analyze)
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "unsupported.pdf", store, force_ocr=True, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "deterministic"}
    assert fetched.analysis_error is None
    assert calls == [True]


def test_deterministic_run_reports_native_text_required_without_force_ocr(monkeypatch):
    store = JobStore()
    job = store.create("scan.pdf")

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf_bytes, filename: None)

    run_job(job.id, b"%PDF-fake", "scan.pdf", store, force_ocr=False, parse_mode="deterministic")

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis is None
    assert "native PDF text unavailable" in (fetched.analysis_error or "")
    assert fetched.parse_model == "deterministic-native-preflight"


def test_auto_run_uses_local_ocr_before_remote_visual_ocr(monkeypatch):
    store = JobStore()
    job = store.create("scan.pdf")
    remote_calls = []

    class LocalDoc(_FakeDoc):
        model = "local-tesseract-ocr"

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        remote_calls.append(force_ocr)
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf_bytes, filename: None)
    monkeypatch.setattr("webapp.worker._local_ocr_statement", lambda pdf_bytes, filename: LocalDoc())
    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto": object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "scan.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.parse_model == "local-tesseract-ocr"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "auto"}
    assert remote_calls == []


def test_deterministic_run_uses_local_ocr_before_reporting_no_text(monkeypatch):
    store = JobStore()
    job = store.create("scan.pdf")

    class LocalDoc(_FakeDoc):
        model = "local-tesseract-ocr"

    monkeypatch.setattr("webapp.worker._native_statement", lambda pdf_bytes, filename: None)
    monkeypatch.setattr("webapp.worker._local_ocr_statement", lambda pdf_bytes, filename: LocalDoc())
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("remote OCR should not run")))
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown, parse_mode="auto": object())
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

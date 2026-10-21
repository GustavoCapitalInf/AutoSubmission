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


def _assert_no_visual_rung():
    """The visual OCR rung these tests used to forbid (by patching
    `ocr.pipeline.load_settings`) no longer exists (slice S2): its client
    module cannot be found and the ladder holds no visual-settings loader."""
    import importlib.util

    import ocr.pipeline

    assert importlib.util.find_spec("ocr.ocr_client") is None
    assert not hasattr(ocr.pipeline, "load_settings")


def test_run_job_success(monkeypatch, store):
    job = store.create("s.pdf")

    def fake_parse(pdf_bytes, source_file="", on_page_replace=None, **kwargs):
        # The visual rung's `on_page_delta` stream left with it (slice S2); the
        # live buffer is filled through the ladder's `on_page_replace`.
        assert "on_page_delta" not in kwargs
        if on_page_replace:
            on_page_replace(0, "replayed page")
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "auto"}
    assert fetched.analysis_error is None
    assert fetched.parse_model == "test-model"
    assert "replayed page" in fetched.live_text  # worker forwarded the ladder's pages


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


class _StageRecorder:
    """The job store, with every stage it is told recorded (the forced refusal must name none)."""

    def __init__(self, store):
        self._store, self.stages = store, []

    def __getattr__(self, name):
        return getattr(self._store, name)

    def set_stage(self, job_id, stage, parse_model=None):
        self.stages.append(stage)
        return self._store.set_stage(job_id, stage, parse_model)


def test_a_forced_job_is_refused_before_preflight_with_the_fixed_text(monkeypatch, store):
    """Force visual OCR is retired (owner ruling, 2026-10-13). `/upload` refuses the flag; a job stored with it reaches
    `run_job` only through its re-analysis, and ends before preflight: nothing is read, no stage is named, the job
    error is the fixed literal and the telemetry record names the class `ForcedOcrRemoved`."""
    from webapp.worker import FORCED_OCR_ERROR_TYPE, FORCED_OCR_RETIRED

    job = store.create("forced.pdf", force_ocr=True)
    for name in ("inspect_pdf", "parse_statement", "analyze_document", "cached_ocr", "cached_analysis"):
        monkeypatch.setattr(f"webapp.worker.{name}", lambda *a, _n=name, **k: pytest.fail(f"{_n} ran"))
    recorder = _StageRecorder(store)
    run_job(job.id, b"%PDF-fake", "forced.pdf", recorder, force_ocr=True)
    fetched = store.get(job.id)
    assert (fetched.status, fetched.error, fetched.analysis, fetched.markdown) == (
        "error", FORCED_OCR_RETIRED, None, None)
    assert recorder.stages == []
    records = [r for r in store.storage.telemetry_records() if r["job_id"] == job.id]
    assert [r["outcome"]["error_type"] for r in records] == [FORCED_OCR_ERROR_TYPE]
    assert records[0]["source"]["model"] is None and records[0]["stages"] == {}
    assert FORCED_OCR_ERROR_TYPE == "ForcedOcrRemoved" and FORCED_OCR_RETIRED.endswith("read it deterministically.")


@pytest.mark.parametrize("env", [{}, {"OCR_ALLOW_VISUAL_PAIR": "1", "OCR_VISUAL_PAIR_LEGACY_VISUAL": "1",
                                      "OCR_VISUAL_PAIR_FALLBACK_TRIGGER": "broad"}])
def test_every_read_uses_the_deterministic_flags_whatever_the_retired_switches(monkeypatch, store, env):
    """One read, native text then local Tesseract, the visual rung a literal False, and the analysis is asked for no
    mode. The retired visual switches no longer reach the worker (moved from tests/test_visual_pair_worker.py and
    tests/test_webapp_worker.py's legacy-flag test, slice S1)."""
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    job = store.create("statement.pdf")
    reads, analysed = [], []
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *a, **k: reads.append(k) or _FakeDoc())

    def analyze(markdown, **kwargs):
        analysed.append(kwargs)
        raise RuntimeError("no deterministic parser matched this statement")

    monkeypatch.setattr("webapp.worker.analyze_document", analyze)
    run_job(job.id, b"%PDF-fake-" + str(len(env)).encode(), "statement.pdf", store)
    fetched = store.get(job.id)
    assert [(k["force_ocr"], k["allow_local_ocr"], k["allow_visual_ocr"]) for k in reads] == [(False, True, False)]
    assert [("parse_mode" in kwargs) for kwargs in analysed] == [False]
    assert (fetched.status, fetched.analysis, fetched.analysis_error) == (
        "done", None, "no deterministic parser matched this statement")


def test_a_forged_contradiction_message_is_withheld_like_any_other_crash():
    """A statement-contradiction refusal is no longer produced by any reader of the worker, so a message of its shape
    is an ordinary exception's text and is withheld (moved from tests/test_source_contradiction.py, slice S1)."""
    from webapp.worker import _analysis_failure

    forged = RuntimeError("Fail: Statement debit total ($1.00 listed, $2.00 printed) contradiction")
    assert _analysis_failure(forged) == (
        "analysis stage failed: RuntimeError (message withheld; an exception message can quote statement text)")


def test_deterministic_run_reports_native_text_required_without_force_ocr(monkeypatch, store):
    job = store.create("scan.pdf")

    # Ladder rungs at their one home: nothing offline matches, and the
    # deterministic preflight (allow_visual_ocr=False) must return None
    # rather than reach for visual OCR.
    monkeypatch.setattr("ocr.pipeline._native_statement", lambda pdf_bytes, source_file="": None)
    monkeypatch.setattr("ocr.pipeline.parse_local_tesseract", lambda *a, **k: None)
    _assert_no_visual_rung()

    run_job(job.id, b"%PDF-fake", "scan.pdf", store, force_ocr=False)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.analysis is None
    # The fixed no-text refusal, without the retired "turn on Force visual OCR ... or use Auto mode" advice.
    assert fetched.analysis_error == (
        "native PDF text unavailable or too sparse, and local Tesseract OCR did not produce usable statement text")
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
    _assert_no_visual_rung()
    monkeypatch.setattr("webapp.worker.analyze_document", lambda markdown, **kwargs: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "scan.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.parse_model == "local-tesseract-ocr"
    assert fetched.analysis == {"quality": {"level": "transaction_level"}, "parse_mode": "auto"}


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

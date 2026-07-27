from webapp.jobs import JobStore
from webapp.worker import run_job


class _FakeDoc:
    model = "test-model"

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
    monkeypatch.setattr("webapp.worker.analyze_markdown", lambda markdown: object())
    monkeypatch.setattr("webapp.worker.report_to_json", lambda report: {"quality": {"level": "transaction_level"}})

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html
    assert fetched.analysis == {"quality": {"level": "transaction_level"}}
    assert fetched.analysis_error is None
    assert fetched.parse_model == "test-model"
    assert "streamed chunk" in fetched.live_text  # worker forwarded the stream


def test_run_job_failure(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None, force_ocr=False):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"

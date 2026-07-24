from webapp.jobs import JobStore
from webapp.worker import run_job


class _FakeDoc:
    def to_markdown(self):
        return "# Hello"


def test_run_job_success(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def fake_parse(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None):
        if on_page_delta:
            on_page_delta(0, "streamed chunk")  # simulate live streaming of page 1
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html
    assert "streamed chunk" in fetched.live_text  # worker forwarded the stream


def test_run_job_failure(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file="", on_page_delta=None, on_page_replace=None):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"

from webapp.jobs import JobStore
from webapp.worker import run_job


class _FakeDoc:
    def to_markdown(self):
        return "# Hello"


def test_run_job_success(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def fake_parse(pdf_bytes, source_file="", on_delta=None):
        if on_delta:
            on_delta("streamed chunk")  # simulate live streaming
        return _FakeDoc()

    monkeypatch.setattr("webapp.worker.parse_statement", fake_parse)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html
    assert fetched.live_text == "streamed chunk"  # worker forwarded the stream


def test_run_job_failure(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file="", on_delta=None):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"

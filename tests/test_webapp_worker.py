from webapp.jobs import JobStore
from webapp.worker import run_job


class _FakeDoc:
    def to_markdown(self):
        return "# Hello"


def test_run_job_success(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")
    monkeypatch.setattr("webapp.worker.parse_statement",
                        lambda pdf_bytes, source_file="": _FakeDoc())

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# Hello"
    assert "<h1>Hello</h1>" in fetched.html


def test_run_job_failure(monkeypatch):
    store = JobStore()
    job = store.create("s.pdf")

    def boom(pdf_bytes, source_file=""):
        raise RuntimeError("connection error")

    monkeypatch.setattr("webapp.worker.parse_statement", boom)

    run_job(job.id, b"%PDF-fake", "s.pdf", store)

    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"

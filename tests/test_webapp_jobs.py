# tests/test_webapp_jobs.py
from webapp.jobs import JobStore, Job


def test_create_and_get():
    store = JobStore()
    job = store.create("statement.pdf")
    assert isinstance(job, Job)
    assert job.filename == "statement.pdf"
    assert job.status == "queued"
    assert store.get(job.id) is job


def test_get_unknown_returns_none():
    store = JobStore()
    assert store.get("nope") is None


def test_set_status():
    store = JobStore()
    job = store.create("x.pdf")
    store.set_status(job.id, "processing")
    assert store.get(job.id).status == "processing"


def test_set_result_marks_done():
    store = JobStore()
    job = store.create("x.pdf")
    store.set_result(job.id, "# md", "<h1>md</h1>")
    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# md"
    assert fetched.html == "<h1>md</h1>"


def test_set_error_marks_error():
    store = JobStore()
    job = store.create("x.pdf")
    store.set_error(job.id, "boom")
    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "boom"


def test_append_page_live_renders_in_page_order():
    store = JobStore()
    job = store.create("x.pdf")
    # Pages OCR concurrently, so buffers may arrive out of order...
    store.append_page_live(job.id, 1, "second")
    store.append_page_live(job.id, 0, "first")
    store.append_page_live(job.id, 1, " page")
    text = store.get(job.id).live_text
    # ...but live_text renders them in page order with markers.
    assert text == "\n\n--- Page 1 ---\n\nfirst\n\n--- Page 2 ---\n\nsecond page"
    assert text.index("Page 1") < text.index("Page 2")

# tests/test_webapp_jobs.py
#
# D-1 delta: JobStore is now a facade over a durable SQLite/disk store, so
# each test injects a Storage rooted in a pytest tmp dir instead of calling
# the bare JobStore() constructor (which would write to the real data dir).
# Every assertion below is unchanged from the in-memory era — the facade
# keeps the exact same public behaviour. Durability itself is covered by
# tests/test_webapp_storage.py.
import pytest

from webapp.jobs import JobStore, Job
from webapp.storage import Storage


@pytest.fixture
def store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))


def test_create_and_get(store):
    job = store.create("statement.pdf")
    assert isinstance(job, Job)
    assert job.filename == "statement.pdf"
    assert job.status == "queued"
    assert store.get(job.id) is job


def test_get_unknown_returns_none(store):
    assert store.get("nope") is None


def test_set_status(store):
    job = store.create("x.pdf")
    store.set_status(job.id, "processing")
    assert store.get(job.id).status == "processing"


def test_set_result_marks_done(store):
    job = store.create("x.pdf")
    store.set_result(job.id, "# md", "<h1>md</h1>")
    fetched = store.get(job.id)
    assert fetched.status == "done"
    assert fetched.markdown == "# md"
    assert fetched.html == "<h1>md</h1>"


def test_set_error_marks_error(store):
    job = store.create("x.pdf")
    store.set_error(job.id, "boom")
    fetched = store.get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "boom"


def test_set_page_live_replaces_buffer(store):
    job = store.create("x.pdf")
    store.append_page_live(job.id, 0, "truncated first attempt")
    store.set_page_live(job.id, 0, "recovered full read")  # fallback overwrites
    assert store.get(job.id).pages_live[0] == "recovered full read"


def test_append_page_live_renders_in_page_order(store):
    job = store.create("x.pdf")
    # Pages OCR concurrently, so buffers may arrive out of order...
    store.append_page_live(job.id, 1, "second")
    store.append_page_live(job.id, 0, "first")
    store.append_page_live(job.id, 1, " page")
    text = store.get(job.id).live_text
    # ...but live_text renders them in page order with markers.
    assert text == "\n\n--- Page 1 ---\n\nfirst\n\n--- Page 2 ---\n\nsecond page"
    assert text.index("Page 1") < text.index("Page 2")

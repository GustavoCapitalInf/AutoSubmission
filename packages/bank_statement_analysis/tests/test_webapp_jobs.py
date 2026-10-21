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

"""/status asks storage for `duplicate_of` at most once per job, and the answer it keeps is final (audit 2026-10-13,
BE-2).

Every /status poll used to open a connection and run two queries for a value the dashboard never reads from /status;
while the in-process worker held the interpreter that made each poll tens to hundreds of milliseconds. The fix keeps
the answer on the job. It is only safe because the document row, the job row and the upload audit row are now written
in ONE transaction (`Storage.record_upload`): before, a document row could be visible without its job row, and a
second upload of the same bytes committed in that gap read None and would have kept it.

All bytes here are fabricated (SAMPLE / CONTOSO); nothing reads a statement.
"""
from __future__ import annotations

import io
import sqlite3
import threading
import uuid
from contextlib import closing

import pytest

from webapp.jobs import JobStore
from webapp.storage import Storage, content_sha256


def _sample_bytes() -> bytes:
    return b"%PDF-SAMPLE-" + uuid.uuid4().hex.encode()


def _count(storage: Storage, table: str, where: str = "", params: tuple = ()) -> int:
    with closing(sqlite3.connect(storage.db_path)) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table} {where}", params).fetchone()[0]


@pytest.fixture
def store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))


# ---------------------------------------------------------------------------------------------------------------------
# The memo
# ---------------------------------------------------------------------------------------------------------------------


def test_a_job_created_here_knows_its_answer_without_asking_storage(store, monkeypatch):
    first = store.create("contoso.pdf", pdf_bytes=(content := _sample_bytes()))
    again = store.create("contoso-again.pdf", pdf_bytes=content)
    other = store.create("fabrikam.pdf", pdf_bytes=_sample_bytes())
    calls = []
    real = store.storage.duplicate_of
    monkeypatch.setattr(store.storage, "duplicate_of", lambda job_id: calls.append(job_id) or real(job_id))
    for _ in range(5):
        assert [store.duplicate_of(job.id) for job in (first, again, other)] == [None, first.id, None]
    assert calls == []
    assert (first.duplicate_of, again.duplicate_of, other.duplicate_of) == (None, first.id, None)
    assert [real(job.id) for job in (first, again, other)] == [None, first.id, None]


def test_a_job_loaded_from_storage_asks_once(tmp_path, monkeypatch):
    data = tmp_path / "data"
    created = JobStore(Storage(data))
    first = created.create("contoso.pdf", pdf_bytes=(content := _sample_bytes()))
    again = created.create("contoso-again.pdf", pdf_bytes=content)

    reopened = JobStore(Storage(data))
    calls = []
    real = reopened.storage.duplicate_of
    monkeypatch.setattr(reopened.storage, "duplicate_of", lambda job_id: calls.append(job_id) or real(job_id))
    for _ in range(5):
        assert reopened.duplicate_of(again.id) == first.id
        assert reopened.duplicate_of(first.id) is None
    assert sorted(calls) == sorted([again.id, first.id])


def test_a_job_without_bytes_has_no_duplicate_and_asks_nothing(store, monkeypatch):
    job = store.create("sample.pdf")
    monkeypatch.setattr(store.storage, "duplicate_of", lambda job_id: pytest.fail("asked storage"))
    assert store.duplicate_of(job.id) is None
    assert store.duplicate_of("no-such-job") is None


# ---------------------------------------------------------------------------------------------------------------------
# The transaction that makes the memo safe
# ---------------------------------------------------------------------------------------------------------------------


def test_document_job_and_audit_rows_are_written_together_or_not_at_all(store):
    storage = store.storage
    storage.create_job("sample-taken-id", filename="sample.pdf")  # the job insert below will collide with this id
    sha = content_sha256(_sample_bytes())
    before = (_count(storage, "documents"), _count(storage, "jobs"), _count(storage, "audit_log"))
    with pytest.raises(sqlite3.IntegrityError):
        storage.record_upload("sample-taken-id", filename="contoso.pdf", content_sha256=sha, byte_size=10)
    assert (_count(storage, "documents"), _count(storage, "jobs"), _count(storage, "audit_log")) == before
    assert _count(storage, "documents", "WHERE content_sha256 = ?", (sha,)) == 0


def test_the_upload_audit_row_is_unchanged(store):
    content = _sample_bytes()
    job = store.create("contoso.pdf", pdf_bytes=content)
    with closing(sqlite3.connect(store.storage.db_path)) as conn:
        rows = conn.execute("SELECT event_type, detail FROM audit_log WHERE job_id = ?", (job.id,)).fetchall()
    assert rows == [("upload", '{"filename": "contoso.pdf", "content_sha256": "%s"}' % content_sha256(content))]


def test_concurrent_uploads_of_the_same_new_bytes_always_agree_with_storage(store):
    """Two request threads recording the same new bytes at the same moment, 40 times: exactly one of each pair is
    first, the other names it, and every kept answer equals what storage says afterwards."""
    storage = store.storage
    for trial in range(40):
        sha = content_sha256(_sample_bytes())
        barrier = threading.Barrier(2)
        answers: dict[str, str | None] = {}
        failures: list[BaseException] = []

        def upload(name: str) -> None:
            try:
                barrier.wait()
                job_id = f"sample-{trial}-{name}"
                answers[job_id] = storage.record_upload(job_id, filename=f"{name}.pdf", content_sha256=sha,
                                                        byte_size=10)
            except BaseException as exc:  # noqa: BLE001 - reported below
                failures.append(exc)

        threads = [threading.Thread(target=upload, args=(name,)) for name in ("contoso", "fabrikam")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert failures == []
        firsts =[job_id for job_id, answer in answers.items() if answer is None]
        assert len(firsts) == 1
        assert {answer for answer in answers.values() if answer is not None} == set(firsts)
        assert all(storage.duplicate_of(job_id) == answer for job_id, answer in answers.items())


# ---------------------------------------------------------------------------------------------------------------------
# Through the routes
# ---------------------------------------------------------------------------------------------------------------------


class _FakeThread:
    def __init__(self, target=None, args=(), daemon=None):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


class _FakeDoc:
    model = "test-model"
    pages = ["# SAMPLE"]

    def to_markdown(self):
        return "# SAMPLE"


def test_an_upload_and_its_polls_ask_storage_at_most_once(monkeypatch):
    from webapp import app as app_module

    monkeypatch.setattr("webapp.app.threading.Thread", _FakeThread)
    monkeypatch.setattr("webapp.app.pdf_page_count", lambda pdf_bytes: 1)
    monkeypatch.setattr("webapp.worker.parse_statement", lambda *a, **k: _FakeDoc())
    monkeypatch.setattr("webapp.worker.analyze_document", lambda *a, **k: object())
    monkeypatch.setattr("webapp.worker.document_to_json", lambda document: {"quality": {"level": "transaction_level"}})
    storage = app_module.store.storage
    calls = []
    real = storage.duplicate_of
    monkeypatch.setattr(storage, "duplicate_of", lambda job_id: calls.append(job_id) or real(job_id))
    client = app_module.app.test_client()
    content = _sample_bytes()

    def upload():
        response = client.post("/upload", data={"files": (io.BytesIO(content), "contoso.pdf")},
                               content_type="multipart/form-data")
        assert response.status_code == 200
        return response.get_json()["jobs"][0]

    first, again = upload(), upload()
    assert (first["duplicate_of"], again["duplicate_of"]) == (None, first["id"])
    for _ in range(5):
        assert client.get(f"/status/{first['id']}").get_json()["duplicate_of"] is None
        assert client.get(f"/status/{again['id']}").get_json()["duplicate_of"] == first["id"]
    assert calls == []  # jobs created in this process need no call at all (a loaded job: one, see above)
    assert (real(first["id"]), real(again["id"])) == (None, first["id"])

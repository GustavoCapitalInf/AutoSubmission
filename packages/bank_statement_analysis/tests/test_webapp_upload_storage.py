"""An upload is stored whole or not queued at all, and concurrent writers of the same bytes never fail each other
(audit 2026-10-13, BE-4).

* /upload stored and queued one file at a time: a storage failure on file k left files 1..k-1 queued and processed
  under ids the dashboard never received (it got an HTML 500). Now the whole batch is stored first; a failure marks
  every job the request created failed with fixed text, queues none, and answers 503 JSON.
* `Storage.save_pdf` and the artifact cache's payload writer wrote through ONE fixed temporary name per target, so two
  writers of the same new bytes at once could fail (measured on Windows: about one aligned pair in four). Each write
  now has a temporary file of its own.

All bytes are fabricated (SAMPLE); nothing reads a statement.
"""
from __future__ import annotations

import io
import os
import threading
import uuid

import pytest

from webapp import app as app_module
from webapp import intake as intake_module
from webapp.artifact_cache import ArtifactCache
from webapp.storage import Storage, content_sha256


def _sample_bytes(size: int = 0) -> bytes:
    return b"%PDF-SAMPLE-" + uuid.uuid4().hex.encode() + os.urandom(size)


def _run_pairs(trials: int, work) -> list[BaseException]:
    failures: list[BaseException] = []
    for trial in range(trials):
        barrier = threading.Barrier(2)

        def one(index: int, trial: int = trial) -> None:
            try:
                barrier.wait()
                work(trial, index)
            except BaseException as exc:  # noqa: BLE001 - reported to the test
                failures.append(exc)

        threads = [threading.Thread(target=one, args=(index,)) for index in (0, 1)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    return failures


# ---------------------------------------------------------------------------------------------------------------------
# One temporary file per write
# ---------------------------------------------------------------------------------------------------------------------


def test_two_requests_storing_the_same_new_bytes_never_fail(tmp_path):
    storage = Storage(tmp_path / "data")
    contents = [_sample_bytes(2 * 1024 * 1024) for _ in range(60)]
    shas = [content_sha256(content) for content in contents]  # outside the threads, so both reach save_pdf together
    failures = _run_pairs(60, lambda trial, index: storage.save_pdf(shas[trial], contents[trial]))
    assert failures == []
    for content in contents:
        assert storage.load_pdf(content_sha256(content)) == content
    assert [name for name in os.listdir(storage.data_dir) if name.endswith(".tmp")] == []


def test_a_failed_pdf_write_leaves_no_temporary_file(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "data")
    content = _sample_bytes()

    def broken_replace(source, target):
        raise OSError("no space left on device")

    monkeypatch.setattr("webapp.storage._replace_retrying", broken_replace)
    with pytest.raises(OSError):
        storage.save_pdf(content_sha256(content), content)
    assert [name for name in os.listdir(storage.data_dir) if name.endswith(".tmp")] == []
    assert storage.load_pdf(content_sha256(content)) is None


def test_a_rename_refused_after_another_request_stored_the_bytes_counts_as_stored(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "data")
    content = _sample_bytes()
    sha = content_sha256(content)

    def other_request_won(source, target):
        with open(target, "wb") as stream:
            stream.write(content)
        raise PermissionError("the target is open")

    monkeypatch.setattr("webapp.storage._replace_retrying", other_request_won)
    assert storage.save_pdf(sha, content) == storage.pdf_path(sha)
    assert storage.load_pdf(sha) == content
    assert [name for name in os.listdir(storage.data_dir) if name.endswith(".tmp")] == []


def test_a_rename_refused_with_no_target_still_fails(tmp_path, monkeypatch):
    storage = Storage(tmp_path / "data")
    content = _sample_bytes()

    def refused(source, target):
        raise PermissionError("refused")

    monkeypatch.setattr("webapp.storage._replace_retrying", refused)
    with pytest.raises(PermissionError):
        storage.save_pdf(content_sha256(content), content)


def test_two_writers_of_one_cache_entry_never_fail(tmp_path):
    cache = ArtifactCache(Storage(tmp_path / "data"))
    target = cache.root / "ocr" / "ab" / "sample.json"
    payloads = [{"sample": uuid.uuid4().hex, "pages": ["SAMPLE"] * 2000} for _ in range(50)]
    failures = _run_pairs(50, lambda trial, index: cache._write_payload(target, payloads[trial]))
    assert failures == []
    assert [name for name in os.listdir(target.parent) if name.endswith(".tmp")] == []
    assert target.read_text(encoding="utf-8").startswith("{")


# ---------------------------------------------------------------------------------------------------------------------
# /upload: stored whole, or nothing queued
# ---------------------------------------------------------------------------------------------------------------------


@pytest.fixture
def upload_seams(monkeypatch):
    monkeypatch.setattr("webapp.intake.pdf_page_count", lambda pdf_bytes: 1)
    queued: list[str] = []
    monkeypatch.setattr("webapp.app._enqueue_job", lambda job_id, *args: queued.append(job_id))
    return queued


def _post(files):
    client = app_module.app.test_client()
    data = {"files": [(io.BytesIO(content), name) for name, content in files]}
    return client.post("/upload", data=data, content_type="multipart/form-data")


def test_a_storage_failure_mid_batch_queues_nothing_and_answers_fixed_json(upload_seams, monkeypatch):
    storage = app_module.store.storage
    real_save = storage.save_pdf
    calls = {"n": 0}
    created = []
    real_create = app_module.store.create

    def recording_create(*args, **kwargs):
        job = real_create(*args, **kwargs)
        created.append(job.id)
        return job

    def failing_third(sha, content):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("SAMPLE-SECRET no space left on device")
        return real_save(sha, content)

    monkeypatch.setattr(storage, "save_pdf", failing_third)
    monkeypatch.setattr(app_module.store, "create", recording_create)
    response = _post([(f"sample-{n}.pdf", _sample_bytes()) for n in range(3)])
    assert response.status_code == 503
    assert response.is_json
    assert response.get_json() == {"error": intake_module.UPLOAD_NOT_STORED}
    assert "SAMPLE-SECRET" not in response.get_data(as_text=True)
    assert upload_seams == []
    assert len(created) == 2
    for job_id in created:
        job = app_module.store.get(job_id)
        assert (job.status, job.error) == ("error", intake_module.UPLOAD_NOT_STORED)
        assert job.pdf_bytes is None
        assert storage.load_job(job_id)["status"] == "error"


def test_a_profile_write_failure_also_queues_nothing(upload_seams, monkeypatch):
    storage = app_module.store.storage
    real = storage.set_document_profile
    calls = {"n": 0}

    def failing_second(job_id, profile_json):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk I/O error")
        return real(job_id, profile_json)

    monkeypatch.setattr(storage, "set_document_profile", failing_second)
    response = _post([(f"sample-{n}.pdf", _sample_bytes()) for n in range(3)])
    assert response.status_code == 503
    assert upload_seams == []


def test_a_healthy_batch_is_stored_then_queued_in_upload_order(upload_seams):
    response = _post([(f"sample-{n}.pdf", _sample_bytes()) for n in range(3)])
    assert response.status_code == 200
    jobs = response.get_json()["jobs"]
    assert [job["filename"] for job in jobs] == ["sample-0.pdf", "sample-1.pdf", "sample-2.pdf"]
    assert upload_seams == [job["id"] for job in jobs]
    assert all(app_module.store.get(job["id"]).status == "queued" for job in jobs)

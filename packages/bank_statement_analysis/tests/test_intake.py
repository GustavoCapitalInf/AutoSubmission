"""`webapp.intake.accepted_statements`: a batch is stored whole and queued only when the caller's block completes.
Fabricated PDF bytes only."""
import uuid

import pytest

from webapp.intake import UPLOAD_NOT_STORED, Upload, accepted_statements
from webapp.jobs import JobStore
from webapp.storage import Storage


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr("webapp.intake.pdf_page_count", lambda pdf_bytes: 1)
    return JobStore(Storage(tmp_path / "data"))


def _uploads(count):
    return [Upload(f"sample-{n}.pdf", b"%PDF-SAMPLE-" + uuid.uuid4().hex.encode()) for n in range(count)]


def test_a_completed_block_queues_every_job_in_order(store):
    queued = []
    uploads = _uploads(3)
    with accepted_statements(store, uploads, enqueue=lambda *job: queued.append(job),
                             volume_nearly_full=lambda incoming: False) as jobs:
        assert queued == []
        assert [store.get(job.id).status for job in jobs] == ["queued"] * 3
    assert queued == [(job.id, upload.pdf_bytes, upload.filename, False) for job, upload in zip(jobs, uploads)]


def test_a_block_that_raises_fails_every_job_and_queues_none(store):
    queued = []
    with pytest.raises(LookupError):
        with accepted_statements(store, _uploads(2), enqueue=lambda *job: queued.append(job),
                                 volume_nearly_full=lambda incoming: False) as jobs:
            raise LookupError("the caller's own write failed")
    assert queued == []
    assert [(store.get(job.id).status, store.get(job.id).error) for job in jobs] == [
        ("error", UPLOAD_NOT_STORED)] * 2

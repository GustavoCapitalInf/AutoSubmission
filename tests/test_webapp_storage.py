"""Wave 1 / D-1 — durable persistence for the webapp.

Restart survival is simulated the way the brief prescribes: the store is torn
down and reopened over the same data directory (a fresh Storage + JobStore is
exactly what a process restart constructs), so no real process kill is needed.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy

import pytest

from webapp.jobs import JobStore
from webapp.storage import SCHEMA_VERSION, Storage, content_sha256

PDF = b"%PDF-1.7\nfake statement body for hashing"


def _analysis() -> dict:
    return {
        "statement": {
            "bank": "Test Bank",
            "account_number": "987654321",
            "transactions": [
                {
                    "date": "2026-01-04",
                    "description": "ACH DEPOSIT",
                    "amount": 1000.0,
                    "classification": {
                        "account": "987654321",
                        "source_location": "page-1-row-1",
                        "revenue_classification": "unverified_deposit",
                    },
                }
            ],
        },
        "metrics": {"effective_total_deposits": 1000.0},
    }


def _reviewed(analysis: dict, status: str, state: str) -> dict:
    updated = deepcopy(analysis)
    classification = updated["statement"]["transactions"][0]["classification"]
    classification["revenue_review_status"] = status
    classification["revenue_classification"] = state
    return updated


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def store(data_dir):
    return JobStore(Storage(data_dir))


def _reopen(data_dir) -> JobStore:
    """Simulated restart: a brand-new Storage + JobStore over the same dir."""
    return JobStore(Storage(data_dir))


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------


def test_schema_creation_writes_a_single_version_row(data_dir):
    storage = Storage(data_dir)
    assert storage.schema_version() == SCHEMA_VERSION
    # Reopening must be idempotent — still exactly one row.
    Storage(data_dir)
    with sqlite3.connect(storage.db_path) as conn:
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
    assert rows == [(SCHEMA_VERSION,)]


def test_future_schema_version_is_refused(data_dir):
    storage = Storage(data_dir)
    with sqlite3.connect(storage.db_path) as conn:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION + 1,))
    with pytest.raises(RuntimeError, match="downgrades are refused"):
        Storage(data_dir)


def test_content_sha256_matches_the_corpus_gate_convention():
    # The O-1 handshake definition: UPPERCASE hex SHA-256 of the raw bytes,
    # identical to corpus_gate.sha256_upper.
    assert content_sha256(PDF) == hashlib.sha256(PDF).hexdigest().upper()
    assert content_sha256(PDF) == content_sha256(PDF)
    assert len(content_sha256(PDF)) == 64
    assert content_sha256(PDF) == content_sha256(PDF).upper()


# ---------------------------------------------------------------------------
# job round-trip / restart survival
# ---------------------------------------------------------------------------


def test_job_round_trip_survives_reopen(data_dir, store):
    job = store.create(
        "statement.pdf",
        page_count=3,
        force_ocr=True,
        parse_mode="deterministic",
        pdf_bytes=PDF,
    )
    store.set_status(job.id, "processing")
    store.set_stage(job.id, "analyzing", "test-model")
    store.set_result(
        job.id, "# md", "<h1>md</h1>",
        analysis=_analysis(), analysis_error=None, parse_model="test-model",
    )

    reopened = _reopen(data_dir)
    fetched = reopened.get(job.id)
    assert fetched is not None
    assert fetched.status == "done"
    assert fetched.markdown == "# md"
    assert fetched.html == "<h1>md</h1>"
    assert fetched.analysis == _analysis()  # verbatim, unmasked
    assert fetched.analysis_error is None
    assert fetched.parse_model == "test-model"
    assert fetched.force_ocr is True
    assert fetched.parse_mode == "deterministic"
    assert fetched.page_count == 3
    assert fetched.filename == "statement.pdf"
    assert fetched.content_sha256 == content_sha256(PDF)

    row = reopened.storage.load_job(job.id)
    assert row["created_at"] and row["started_at"] and row["finished_at"]


def test_error_job_survives_reopen(data_dir, store):
    job = store.create("bad.pdf", pdf_bytes=PDF)
    store.set_status(job.id, "processing")
    store.set_error(job.id, "connection error")

    fetched = _reopen(data_dir).get(job.id)
    assert fetched.status == "error"
    assert fetched.error == "connection error"


def test_unknown_job_is_none_after_reopen(data_dir, store):
    assert _reopen(data_dir).get("nope") is None


# ---------------------------------------------------------------------------
# startup interruption marking — nothing silently lost
# ---------------------------------------------------------------------------


def test_in_flight_jobs_are_marked_interrupted_never_lost(data_dir, store):
    queued = store.create("queued.pdf", pdf_bytes=PDF)
    processing = store.create("processing.pdf", pdf_bytes=PDF)
    store.set_status(processing.id, "processing")
    done = store.create("done.pdf", pdf_bytes=PDF)
    store.set_result(done.id, "# md", "<h1>md</h1>", analysis=_analysis())

    reopened = _reopen(data_dir)
    interrupted = reopened.mark_interrupted()
    assert set(interrupted) == {queued.id, processing.id}

    for job_id in (queued.id, processing.id):
        job = reopened.get(job_id)
        assert job.status == "interrupted"
        assert job.stage == "interrupted"
        assert job.error  # explanatory, not silent
    # The completed job is untouched and still fully served.
    survivor = reopened.get(done.id)
    assert survivor.status == "done"
    assert survivor.analysis == _analysis()

    events = reopened.storage.audit_events("status_change", job_id=queued.id)
    assert any(json.loads(e["detail"])["status"] == "interrupted" for e in events)


def test_mark_interrupted_is_a_no_op_when_nothing_was_in_flight(data_dir, store):
    job = store.create("done.pdf", pdf_bytes=PDF)
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis())
    assert _reopen(data_dir).mark_interrupted() == []


# ---------------------------------------------------------------------------
# review decisions — append-only, full history, restart survival
# ---------------------------------------------------------------------------


def _completed_job(store):
    job = store.create("review.pdf", pdf_bytes=PDF)
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis())
    return job


def test_review_history_records_actor_timestamp_and_prior_state(data_dir, store):
    job = _completed_job(store)
    first = _reviewed(_analysis(), "confirmed", "verified_revenue")
    store.apply_review(
        job.id, first,
        source_location="page-1-row-1", decision="confirm", actor="analyst-a",
    )
    second = _reviewed(first, "rejected", "non_revenue")
    store.apply_review(
        job.id, second,
        source_location="page-1-row-1", decision="reject",
    )

    history = _reopen(data_dir).review_history(job.id)
    assert [row["decision"] for row in history] == ["confirm", "reject"]
    assert [row["actor"] for row in history] == ["analyst-a", "local-analyst"]
    assert all(row["decided_at"] for row in history)

    prior_first = json.loads(history[0]["prior_state"])
    assert prior_first["revenue_classification"] == "unverified_deposit"
    assert "revenue_review_status" not in prior_first
    prior_second = json.loads(history[1]["prior_state"])
    assert prior_second["revenue_review_status"] == "confirmed"
    assert prior_second["revenue_classification"] == "verified_revenue"

    # The mutated analysis is durable too.
    fetched = _reopen(data_dir).get(job.id)
    classification = fetched.analysis["statement"]["transactions"][0]["classification"]
    assert classification["revenue_review_status"] == "rejected"


def test_review_decisions_table_is_append_only(data_dir, store):
    job = _completed_job(store)
    store.apply_review(
        job.id, _reviewed(_analysis(), "confirmed", "verified_revenue"),
        source_location="page-1-row-1", decision="confirm",
    )
    with sqlite3.connect(store.storage.db_path) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE review_decisions SET decision = 'tampered'")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM review_decisions")


def test_audit_log_table_is_append_only(store):
    job = store.create("audit.pdf", pdf_bytes=PDF)  # writes an upload event
    assert store.storage.audit_events("upload", job_id=job.id)
    with sqlite3.connect(store.storage.db_path) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("UPDATE audit_log SET event_type = 'tampered'")
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            conn.execute("DELETE FROM audit_log")


# ---------------------------------------------------------------------------
# packages
# ---------------------------------------------------------------------------


def test_package_round_trip_survives_reopen(data_dir, store):
    job_a = _completed_job(store)
    job_b = _completed_job(store)
    package_id = store.create_package([job_a.id, job_b.id], reference="deal-42")

    reopened = _reopen(data_dir)
    assert reopened.package_member_ids(package_id) == [job_a.id, job_b.id]
    assert reopened.package_member_ids("not-a-package") is None

    events = reopened.storage.audit_events("package_created", package_id=package_id)
    assert len(events) == 1
    assert json.loads(events[0]["detail"])["reference"] == "deal-42"


# ---------------------------------------------------------------------------
# PDF disk store + RAM release
# ---------------------------------------------------------------------------


def test_pdf_disk_round_trip_and_ram_release(data_dir, store):
    job = store.create("statement.pdf", page_count=1, pdf_bytes=PDF)
    sha = content_sha256(PDF)
    assert (data_dir / f"{sha}.pdf").read_bytes() == PDF

    # In flight: bytes stay in RAM for /page and /render streaming.
    assert store.get(job.id).pdf_bytes == PDF

    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis())
    # Completed: no pdf_bytes in RAM, disk serves on demand.
    assert store.get(job.id).pdf_bytes is None
    assert store.pdf_bytes(job.id) == PDF

    reopened = _reopen(data_dir)
    assert reopened.get(job.id).pdf_bytes is None
    assert reopened.pdf_bytes(job.id) == PDF


def test_error_jobs_also_release_pdf_bytes(store):
    job = store.create("bad.pdf", pdf_bytes=PDF)
    store.set_error(job.id, "boom")
    assert store.get(job.id).pdf_bytes is None
    assert store.pdf_bytes(job.id) == PDF  # still recoverable from disk


def test_pdf_store_rejects_a_non_hash_name(store):
    with pytest.raises(ValueError):
        store.storage.pdf_path("../../evil")


# ---------------------------------------------------------------------------
# audit log rows for upload / review / export
# ---------------------------------------------------------------------------


def test_audit_rows_for_upload_review_and_export(store):
    job = store.create("audited.pdf", pdf_bytes=PDF)
    store.set_result(job.id, "# md", "<h1>md</h1>", analysis=_analysis())
    store.apply_review(
        job.id, _reviewed(_analysis(), "confirmed", "verified_revenue"),
        source_location="page-1-row-1", decision="confirm", actor="analyst-a",
    )
    store.record_export(job_id=job.id, detail={"format": "csv"})

    storage = store.storage
    uploads = storage.audit_events("upload", job_id=job.id)
    assert len(uploads) == 1
    assert json.loads(uploads[0]["detail"])["content_sha256"] == content_sha256(PDF)

    reviews = storage.audit_events("review", job_id=job.id)
    assert len(reviews) == 1
    review_detail = json.loads(reviews[0]["detail"])
    assert review_detail["decision"] == "confirm"
    assert review_detail["actor"] == "analyst-a"

    exports = storage.audit_events("export", job_id=job.id)
    assert len(exports) == 1
    assert json.loads(exports[0]["detail"])["format"] == "csv"

    assert all(event["at"] for event in storage.audit_events())

import copy
import json
import sys
import threading
import time

import pytest

from analysis import package as package_view
from tests.test_webapp_studio_views import _single
from webapp.jobs import JobStore, UnknownJobs
from webapp.storage import Storage


@pytest.fixture
def store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))


def _done(store, filename, analysis):
    job = store.create(filename)
    store.set_result(job.id, "# Fabricated", "<p>Fabricated</p>", analysis=analysis)
    return job.id


def test_a_snapshot_outlives_a_review_a_reanalysis_and_a_result(store):
    job_id = _done(store, "march.pdf", _single())
    held = store.snapshot([job_id])[0]
    analysis = held.analysis
    before = copy.deepcopy(analysis)

    store.apply_review(job_id, {**_single(), "fabricated": "reviewed"}, source_location="transaction:2",
                       decision="confirm")
    store.apply_reanalysis(job_id, {**_single(), "fabricated": "reanalysed"})
    store.set_result(job_id, "# Again", "<p>Again</p>", analysis=None, analysis_error="fabricated refusal")

    assert held.analysis is analysis and held.analysis == before
    assert (held.status, held.analysis_error) == ("done", None)
    now = store.snapshot([job_id])[0]
    assert (now.analysis, now.analysis_error) == (None, "fabricated refusal")


def test_a_job_that_finishes_after_the_snapshot_is_pending_in_a_package_built_from_it(store):
    march = _done(store, "march.pdf", _single(month=3))
    april = store.create("april.pdf").id
    held = store.snapshot([march, april])
    store.set_result(april, "# April", "<p>April</p>", analysis=_single(month=4))

    totals = package_view.package_analysis(held)["totals"]
    assert (totals["completed"], totals.get("pending"), totals["failed"]) == (1, 1, 0)
    assert [document["status"] for document in package_view.package_analysis(held)["documents"]] == [
        "done", "queued"]
    assert package_view.package_analysis(store.snapshot([march, april]))["totals"]["completed"] == 2


def _read_while_writing(write, read):
    """`read()` repeated from before a thread starts `write()` until it returns. Raises what `write` raised."""
    failures = []

    def run():
        try:
            write()
        except BaseException as failure:
            failures.append(failure)

    # A short switch interval interleaves the two threads often, and keeps the writer from waiting on the reader.
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        writer = threading.Thread(target=run, daemon=True)
        deadline = time.monotonic() + 30
        reads = [read()]
        writer.start()
        while writer.is_alive():
            assert time.monotonic() < deadline, "the writer did not finish"
            reads.append(read())
    finally:
        sys.setswitchinterval(previous)
    if failures:
        raise failures[0]
    return reads


def test_a_writer_alternating_results_never_yields_a_torn_snapshot(store):
    job_id = _done(store, "march.pdf", {"fabricated": -1})

    def write():
        for turn in range(200):
            if turn % 2:
                store.set_result(job_id, "#", "<p></p>", analysis=None, analysis_error="fabricated refusal")
            else:
                store.set_result(job_id, "#", "<p></p>", analysis={"fabricated": turn})

    jobs = _read_while_writing(write, lambda: store.snapshot([job_id])[0])
    torn = [job for job in jobs if (job.analysis is None) == (job.analysis_error is None)]
    assert (len(jobs) > 2, torn) == (True, [])


def test_two_jobs_written_under_one_hold_of_the_lock_are_never_read_apart(store):
    ids = [_done(store, "march.pdf", {"generation": 0}), _done(store, "april.pdf", {"generation": 0})]
    jobs = [store.get(job_id) for job_id in ids]

    def write():
        for generation in range(1, 20001):
            with store._lock:
                for job in jobs:
                    job.analysis = {"generation": generation}

    pairs = _read_while_writing(write, lambda: tuple(job.analysis["generation"] for job in store.snapshot(ids)))
    assert len(set(pairs)) > 2
    assert [pair for pair in pairs if pair[0] != pair[1]] == []


def test_a_snapshot_names_every_job_the_store_does_not_hold(store):
    known = store.create("march.pdf").id
    with pytest.raises(UnknownJobs) as refused:
        store.snapshot(["missing-one", known, "missing-two"])
    assert refused.value.ids == ["missing-one", "missing-two"]


def test_a_package_of_settled_jobs_reads_the_same_from_a_snapshot(store):
    ids = [_done(store, "march.pdf", _single(month=3)), _done(store, "april.pdf", _single(month=4))]
    failed = store.create("may.pdf").id
    store.set_error(failed, "fabricated failure")
    ids.append(failed)

    live = package_view.package_analysis([store.get(job_id) for job_id in ids])
    assert json.dumps(package_view.package_analysis(store.snapshot(ids))) == json.dumps(live)


@pytest.mark.parametrize("path", ["/package_analysis", "/package_download/json"])
def test_the_browser_answers_a_member_the_store_does_not_hold_as_before(monkeypatch, path):
    from webapp.app import app, store as app_store

    monkeypatch.setattr(app_store, "package_member_ids", lambda package_id: ["missing-member"])
    response = app.test_client().get(f"{path}?package_id=fabricated-package")
    assert response.status_code == 404
    assert response.get_json() == {"error": "unknown job ids", "missing": ["missing-member"]}

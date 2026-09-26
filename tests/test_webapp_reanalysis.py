"""Re-analysis of a saved statement (spec docs/superpowers/specs/2026-09-24-lender-detection-design.md §8.6 and D12;
the interface contract's C9): POST /analysis/<job>/reanalyze runs the stored PDF through the worker's own read path
again, its reading served from the artifact cache, replaces the job's analysis in place after writing the analysis it
replaces to the audit log, and replays the analyst's revenue decisions where their posting is unchanged. Fabricated
statements only, whole-dollar amounts; the storage and job-store tests use opaque stand-in payloads."""
import copy
import json
import threading

import pytest

from tests.test_webapp_revenue_batch import ROWS, _records, _two_accounts
from tests.test_webapp_studio_views import _report
from webapp.jobs import JobStore
from webapp.storage import Storage


# --- the store: one transaction, the replaced analysis audited first -------------------------------------------------


def test_a_reanalysis_audits_the_analysis_it_replaces_in_the_same_transaction(tmp_path):
    storage = Storage(tmp_path / "data")
    storage.create_job("job-a", filename="fabricated.pdf")
    storage.set_job_result("job-a", markdown="# F", html="<p>F</p>", analysis_json='{"rules": "old"}',
                           analysis_error=None, parse_model="fabricated-reader")
    assert storage.record_reanalysis("job-a", analysis_json='{"rules": "new"}',
                                     detail={"reviews_replayed": [3], "reviews_not_replayed": [4]}) is True
    row = storage.load_job("job-a")
    assert row["analysis_json"] == '{"rules": "new"}' and row["status"] == "done"
    events = storage.audit_events("reanalysis", job_id="job-a")
    assert len(events) == 1
    assert json.loads(events[0]["detail"]) == {
        "reviews_replayed": [3], "reviews_not_replayed": [4],
        "previous_analysis_json": '{"rules": "old"}', "previous_analysis_error": None}


def test_a_reanalysis_that_produced_an_analysis_clears_the_old_analysis_error(tmp_path):
    storage = Storage(tmp_path / "data")
    storage.create_job("job-a", filename="fabricated.pdf")
    storage.set_job_result("job-a", markdown="# F", html="<p>F</p>", analysis_json=None,
                           analysis_error="fabricated refusal", parse_model=None)
    assert storage.record_reanalysis("job-a", analysis_json='{"rules": "new"}', detail={}) is True
    row = storage.load_job("job-a")
    assert (row["analysis_json"], row["analysis_error"]) == ('{"rules": "new"}', None)
    detail = json.loads(storage.audit_events("reanalysis", job_id="job-a")[0]["detail"])
    assert (detail["previous_analysis_json"], detail["previous_analysis_error"]) == (None, "fabricated refusal")


def test_a_reanalysis_of_an_unknown_job_writes_nothing(tmp_path):
    storage = Storage(tmp_path / "data")
    assert storage.record_reanalysis("no-such-job", analysis_json="{}", detail={}) is False
    assert storage.audit_events("reanalysis") == []

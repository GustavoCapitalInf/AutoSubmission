"""Several revenue-review decisions on one statement at once (the dashboard's multi-select): POST
/analysis/<job>/revenue-reviews saves a batch whole or not at all, one decision row and one audit row per decision.
Fabricated statements only, analysed by the real analysis path."""
import copy

import pytest

from tests.test_webapp_studio_views import _report

ROWS = [(2, "ACH CREDIT FABRICATED CUSTOMER PAYMENT", 4200.0), (4, "DEPOSIT FABRICATED ONE", 300.0),
        (6, "DEPOSIT FABRICATED TWO", 200.0), (8, "DEPOSIT FABRICATED THREE", 100.0),
        (12, "WIRE TRANSFER OUT FABRICATED VENDOR", -1600.0)]


@pytest.fixture
def job():
    from analysis.serialization import document_report_to_dict
    from webapp.app import store

    analysis = document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, ROWS))
    created = store.create("fabricated-batch.pdf")
    store.set_result(created.id, "# Fabricated", "<p>Fabricated</p>", analysis=analysis)
    return created.id


def _records(analysis):
    return {tx["classification"]["source_location"]: tx["classification"]
            for tx in analysis["statement"]["transactions"]}


def _post(job_id, decisions, **extra):
    from webapp.app import app
    return app.test_client().post(f"/analysis/{job_id}/revenue-reviews", json={"decisions": decisions, **extra})


def test_a_batch_confirms_every_selected_deposit_and_records_each_decision(job):
    from webapp.app import app, store

    before = copy.deepcopy(store.get(job).analysis)
    response = _post(job, [{"source_location": "transaction:2", "decision": "confirm"},
                           {"source_location": "transaction:3", "decision": "confirm"}])
    assert response.status_code == 200 and response.get_json()["applied"] == 2
    records = _records(response.get_json()["analysis"])
    assert records["transaction:2"]["revenue_review_status"] == "confirmed"
    assert records["transaction:3"]["revenue_review_status"] == "confirmed"
    assert records["transaction:4"]["revenue_review_status"] == "pending"
    metrics = response.get_json()["analysis"]["metrics"]
    assert metrics["verified_revenue_total"] == before["metrics"]["verified_revenue_total"] + 500.0
    assert metrics["unverified_deposit_total"] == 100.0 and metrics["unverified_deposit_count"] == 1
    # One decision row per decision, each with the state it changed, as single clicks would have left.
    history = store.review_history(job)
    assert [(row["source_location"], row["decision"]) for row in history] == [
        ("transaction:2", "confirm"), ("transaction:3", "confirm")]
    assert all('"pending"' in row["prior_state"] for row in history)
    # The package's True deposits (verified revenue) follow at once.
    package = app.test_client().get(f"/package_analysis?ids={job}").get_json()
    assert package["documents"][0]["verified_revenue_total"] == metrics["verified_revenue_total"]
    assert package["documents"][0]["verified_revenue_count"] == metrics["verified_revenue_count"] == 3


def test_a_batch_marks_deposits_non_revenue(job):
    response = _post(job, [{"source_location": "transaction:4", "decision": "reject"}])
    assert response.status_code == 200
    records = _records(response.get_json()["analysis"])
    assert records["transaction:4"]["revenue_review_status"] == "rejected"
    assert records["transaction:4"]["revenue_classification"] == "non_revenue"


@pytest.mark.parametrize("bad, status", [
    ({"source_location": "transaction:99", "decision": "confirm"}, 404),  # no such transaction
    ({"source_location": "transaction:3", "decision": "maybe"}, 400),     # no such decision
    ({"source_location": "transaction:1", "decision": "confirm"}, 400),   # verified revenue is not reviewable
])
def test_one_refused_decision_refuses_the_batch_and_saves_nothing(job, bad, status):
    from webapp.app import store

    before = copy.deepcopy(store.get(job).analysis)
    response = _post(job, [{"source_location": "transaction:2", "decision": "confirm"}, bad])
    assert response.status_code == status and "error" in response.get_json()
    assert store.get(job).analysis == before and store.review_history(job) == []


@pytest.mark.parametrize("body", [
    {"decisions": []},
    {"decisions": "transaction:2"},
    {"decisions": [{"decision": "confirm"}]},
    {"decisions": ["transaction:2"]},
    {"decisions": [{"source_location": "transaction:2", "decision": "confirm"},
                   {"source_location": "transaction:2", "decision": "reject"}]},
])
def test_a_malformed_batch_is_refused(job, body):
    from webapp.app import app, store

    response = app.test_client().post(f"/analysis/{job}/revenue-reviews", json=body)
    assert response.status_code == 400 and store.review_history(job) == []


def test_a_batch_has_a_size_limit_and_needs_json(job):
    from webapp.app import MAX_REVIEW_BATCH, app

    oversized = [{"source_location": f"transaction:{index}", "decision": "confirm"}
                 for index in range(MAX_REVIEW_BATCH + 1)]
    assert _post(job, oversized).status_code == 400
    form = app.test_client().post(f"/analysis/{job}/revenue-reviews",
                                  data={"decisions": "transaction:2"})  # a cross-site form cannot send JSON
    assert form.status_code == 400


def test_an_unknown_or_unfinished_job_is_not_found():
    assert _post("no-such-job", [{"source_location": "transaction:2", "decision": "confirm"}]).status_code == 404

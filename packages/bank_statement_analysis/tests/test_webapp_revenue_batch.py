"""Several revenue-review decisions on one statement at once (the dashboard's multi-select): POST
/analysis/<job>/revenue-reviews saves a batch whole or not at all, one decision row and one audit row per decision.
Also what both review routes share: the account a decision names, the per-statement lock, the actor and the body.
Fabricated statements only, analysed by the real analysis path."""
import copy
import json
import threading

import pytest

from tests.test_webapp_studio_views import _report

ROWS = [(2, "ACH CREDIT NORTHWIND CUSTOMER PAYMENT", 4200.0), (4, "DEPOSIT FABRICATED ONE", 300.0),
        (6, "DEPOSIT FABRICATED TWO", 200.0), (8, "DEPOSIT FABRICATED THREE", 100.0),
        (12, "WIRE TRANSFER OUT FABRICATED VENDOR", -1600.0)]
# A savings account whose second row is also a deposit awaiting review: each account numbers its own rows, so
# `transaction:2` names a posting in both accounts of the statement.
SAVINGS_ROWS = [(3, "INTEREST PAID", 2.0), (6, "DEPOSIT FABRICATED SAVINGS", 700.0),
                (20, "WITHDRAWAL FABRICATED", -100.0)]


@pytest.fixture
def job():
    from analysis.serialization import document_report_to_dict
    from webapp.app import store

    analysis = document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, ROWS))
    created = store.create("fabricated-batch.pdf")
    store.set_result(created.id, "# Fabricated", "<p>Fabricated</p>", analysis=analysis)
    return created.id


def _two_accounts():
    from analysis.pipeline import AccountRosterEntry, DocumentReport, identify_internal_transfers
    from analysis.serialization import document_report_to_dict

    checking = _report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, ROWS).accounts[0]
    savings = _report("FABRICATED SAVINGS", "000000002020", 9000.0, SAVINGS_ROWS).accounts[0]
    roster = [AccountRosterEntry("FABRICATED BUSINESS CHECKING", "checking", "1010", "published", published_index=0),
              AccountRosterEntry("FABRICATED SAVINGS", "savings", "2020", "published", published_index=1)]
    transfers, notes = identify_internal_transfers([checking, savings])
    return document_report_to_dict(DocumentReport(accounts=[checking, savings],
                                                  document_period=("2031-03-01", "2031-03-28"),
                                                  internal_transfers=transfers, integrity_notes=notes,
                                                  account_roster=roster))


@pytest.fixture
def two_account_job():
    from webapp.app import store

    created = store.create("fabricated-two-accounts.pdf")
    store.set_result(created.id, "# Fabricated", "<p>Fabricated</p>", analysis=_two_accounts())
    return created.id


def _records(analysis, account=1):
    """The classification records of one account (1-based), by location."""
    holder = analysis["accounts"][account - 1] if "accounts" in analysis else analysis
    return {tx["classification"]["source_location"]: tx["classification"]
            for tx in holder["statement"]["transactions"]}


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
    from webapp import app as webapp_app

    assert _post("no-such-job", [{"source_location": "transaction:2", "decision": "confirm"}]).status_code == 404
    assert _single("no-such-job", source_location="transaction:2", decision="confirm").status_code == 404
    # A request naming no statement leaves no lock behind: the table of locks holds statements, not guesses.
    assert "no-such-job" not in webapp_app._review_locks


# --- the account a decision names ------------------------------------------------------------------------------


def _single(job_id, **body):
    from webapp.app import app
    return app.test_client().post(f"/analysis/{job_id}/revenue-review", json=body)


def test_a_decision_reaches_the_posting_of_the_account_it_names(two_account_job):
    from webapp.app import store

    before = store.get(two_account_job).analysis
    assert _records(before, 1)["transaction:2"]["revenue_review_status"] == "pending"
    assert _records(before, 2)["transaction:2"]["revenue_review_status"] == "pending"

    response = _post(two_account_job, [{"source_location": "transaction:2", "decision": "confirm", "account": 2}])
    assert response.status_code == 200
    analysis = response.get_json()["analysis"]
    assert _records(analysis, 2)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert _records(analysis, 1)["transaction:2"]["revenue_review_status"] == "pending"
    # The decision row's prior state is the savings posting's own record, and the audit row names the account.
    history = store.review_history(two_account_job)
    assert len(history) == 1 and json.loads(history[0]["prior_state"])["account_name"] == "FABRICATED SAVINGS"
    audit = [json.loads(row["detail"]) for row in store.storage.audit_events("review", job_id=two_account_job)]
    assert audit == [{"source_location": "transaction:2", "decision": "confirm", "actor": "local-analyst",
                      "account": 2}]

    response = _single(two_account_job, source_location="transaction:2", decision="reject", account=1)
    assert response.status_code == 200
    analysis = response.get_json()["analysis"]
    assert _records(analysis, 1)["transaction:2"]["revenue_review_status"] == "rejected"
    assert _records(analysis, 2)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert json.loads(store.review_history(two_account_job)[1]["prior_state"])["account_name"] == (
        "FABRICATED BUSINESS CHECKING")


def test_a_location_two_accounts_hold_is_refused_unless_the_account_is_named(two_account_job):
    from webapp.app import store

    before = copy.deepcopy(store.get(two_account_job).analysis)
    refusal = "transaction source location is in more than one account; name the account"
    batch = _post(two_account_job, [{"source_location": "transaction:2", "decision": "confirm"}])
    single = _single(two_account_job, source_location="transaction:2", decision="confirm")
    for response in (batch, single):
        assert response.status_code == 400 and response.get_json()["error"] == refusal
    assert store.get(two_account_job).analysis == before and store.review_history(two_account_job) == []
    # A location only one account holds needs no account: checking prints five rows, savings three.
    response = _post(two_account_job, [{"source_location": "transaction:4", "decision": "confirm"}])
    assert response.status_code == 200
    assert _records(response.get_json()["analysis"], 1)["transaction:4"]["revenue_review_status"] == "confirmed"


@pytest.mark.parametrize("account, status", [(3, 404), (0, 400), ("2", 400), (True, 400), (float(2), 400)])
def test_the_account_is_one_the_statement_prints(two_account_job, account, status):
    from webapp.app import store

    for response in (_post(two_account_job, [{"source_location": "transaction:2", "decision": "confirm",
                                              "account": account}]),
                     _single(two_account_job, source_location="transaction:2", decision="confirm", account=account)):
        assert response.status_code == status
    assert store.review_history(two_account_job) == []


def test_a_batch_names_every_account_or_none(two_account_job):
    from webapp.app import store

    # Only checking prints a fourth row, so "transaction:4" and account 1's "transaction:4" are one posting: named
    # both ways it would be decided twice in one batch, each decision recorded against the state before the batch.
    mixed = _post(two_account_job, [{"source_location": "transaction:4", "decision": "confirm", "account": 1},
                                    {"source_location": "transaction:4", "decision": "reject"}])
    assert mixed.status_code == 400 and store.review_history(two_account_job) == []
    both = _post(two_account_job, [{"source_location": "transaction:2", "decision": "confirm", "account": 1},
                                   {"source_location": "transaction:2", "decision": "reject", "account": 2}])
    assert both.status_code == 200 and both.get_json()["applied"] == 2
    analysis = both.get_json()["analysis"]
    assert _records(analysis, 1)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert _records(analysis, 2)["transaction:2"]["revenue_review_status"] == "rejected"


# --- what both routes share --------------------------------------------------------------------------------------


def test_two_reviews_of_one_statement_at_once_keep_both_decisions(job, monkeypatch):
    """A batch and a row's own button on one statement at once. The second waits for the first; without the
    per-statement lock it would read the analysis the batch had not saved yet, and the batch's save would then drop
    the row's decision while its decision row stayed recorded."""
    from webapp.app import store

    entered, release = threading.Event(), threading.Event()
    save = store.apply_reviews

    def held_save(*args, **kwargs):
        entered.set()
        release.wait(5)
        return save(*args, **kwargs)

    monkeypatch.setattr(store, "apply_reviews", held_save)
    results = {}
    batch = threading.Thread(target=lambda: results.update(
        batch=_post(job, [{"source_location": "transaction:2", "decision": "confirm"}])))
    single = threading.Thread(target=lambda: results.update(
        single=_single(job, source_location="transaction:3", decision="reject")))
    batch.start()
    assert entered.wait(5)
    single.start()
    single.join(timeout=1)
    waited = single.is_alive()
    release.set()
    batch.join(5)
    single.join(5)
    assert waited
    assert results["batch"].status_code == results["single"].status_code == 200
    records = _records(store.get(job).analysis)
    assert records["transaction:2"]["revenue_review_status"] == "confirmed"
    assert records["transaction:3"]["revenue_review_status"] == "rejected"
    assert [row["source_location"] for row in store.review_history(job)] == ["transaction:2", "transaction:3"]


@pytest.mark.parametrize("actor", [{"name": "analyst"}, 42, ["analyst"], "a" * 121])
def test_an_actor_that_is_not_a_name_is_refused(job, actor):
    from webapp.app import store

    assert _post(job, [{"source_location": "transaction:2", "decision": "confirm"}], actor=actor).status_code == 400
    assert _single(job, source_location="transaction:2", decision="confirm", actor=actor).status_code == 400
    assert store.review_history(job) == []


def test_an_actor_is_recorded_trimmed_and_a_blank_one_is_the_local_analyst(job):
    from webapp.app import store

    assert _post(job, [{"source_location": "transaction:2", "decision": "confirm"}],
                 actor=" " + "a" * 120 + " ").status_code == 200
    assert _single(job, source_location="transaction:3", decision="confirm", actor="   ").status_code == 200
    assert [row["actor"] for row in store.review_history(job)] == ["a" * 120, "local-analyst"]


@pytest.mark.parametrize("body", [["transaction:2"], "transaction:2", 7, None])
def test_a_single_review_that_is_not_an_object_is_refused_not_an_error(job, body):
    from webapp.app import app, store

    response = app.test_client().post(f"/analysis/{job}/revenue-review", data=json.dumps(body),
                                      content_type="application/json")
    assert response.status_code == 400 and store.review_history(job) == []


# --- the package: each row's account, and when True deposits stand ----------------------------------------------


def test_a_package_row_of_a_multi_account_statement_names_its_account(two_account_job):
    from analysis.serialization import document_report_to_dict
    from webapp.app import app, store

    # Audit B11 (I06): the single-account statement is another account's (its own number). The `job` fixture prints
    # the document's checking statement itself, which the package now leaves out of the document as a repeat.
    other = store.create("fabricated-other-account.pdf")
    store.set_result(other.id, "# Fabricated", "<p>Fabricated</p>", analysis=document_report_to_dict(
        _report("FABRICATED BUSINESS CHECKING", "000000005050", 1500.0, ROWS)))
    job = other.id
    package = app.test_client().get(f"/package_analysis?ids={job},{two_account_job}").get_json()
    savings = [tx for tx in package["transactions"] if tx.get("description") == "DEPOSIT FABRICATED SAVINGS"]
    assert [tx["source_account"] for tx in savings] == [2]
    assert {tx["source_account"] for tx in package["transactions"] if tx["source_job"] == two_account_job} == {1, 2}
    # A statement of one account publishes today's shape: its rows carry no account.
    assert all("source_account" not in tx for tx in package["transactions"] if tx["source_job"] == job)


def _established(analysis, status="done"):
    from tests.test_l1s3_surfaces import _Job
    from webapp.app import _package_analysis

    member = _Job("job-1", analysis)
    member.status = status
    return [row["verified_revenue_established"] for row in _package_analysis([member])["documents"]]


def _account_payload(rows=ROWS):
    from analysis.serialization import document_report_to_dict
    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows))


def test_true_deposits_stand_when_every_credit_is_classified_and_the_credits_are_the_total():
    assert _established(_account_payload()) == [True]
    reconciled = _account_payload()
    reconciled["metrics"]["deposits_source"] = "bank_stated_reconciled"  # the bank's total, and the rows add up to it
    assert _established(reconciled) == [True]
    assert _established(_account_payload([])) == [True]  # nothing came in: True deposits are zero


def test_true_deposits_are_not_established_over_part_of_the_money():
    short = _account_payload()  # the bank's total is more than the rows captured
    short["metrics"].update(deposits_source="bank_stated_unverified",
                            effective_total_deposits=short["metrics"]["total_deposits"] + 1000.0)
    assert _established(short) == [False]
    partial = _account_payload()  # a credit without its revenue state
    partial["statement"]["transactions"][1]["classification"] = None
    assert _established(partial) == [False]
    summary_only = _account_payload([])  # no rows, but the bank printed deposits
    summary_only["metrics"].update(deposits_source="bank_stated_unverified", effective_total_deposits=1000.0)
    assert _established(summary_only) == [False]
    assert _established(_account_payload(), status="failed") == [False]

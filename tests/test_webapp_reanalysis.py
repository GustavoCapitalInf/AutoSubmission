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


# --- the job store: the same job, in memory and on disk -------------------------------------------------------------


def test_the_job_store_replaces_the_analysis_in_memory_and_on_disk(tmp_path):
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("fabricated.pdf")
    store.set_result(job.id, "# F", "<p>F</p>", analysis={"rules": "old"})
    saved = store.apply_reanalysis(job.id, {"rules": "new"}, replayed=(5,), not_replayed=(6,), decided_by_rules=(7,))
    assert saved == {"rules": "new"} and store.get(job.id).analysis == {"rules": "new"}
    saved["rules"] = "edited by a caller"  # the store keeps its own copy
    assert store.get(job.id).analysis == {"rules": "new"}
    assert JobStore(Storage(tmp_path / "data")).get(job.id).analysis == {"rules": "new"}  # a restart reads it back
    detail = json.loads(store.storage.audit_events("reanalysis", job_id=job.id)[0]["detail"])
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [5], [6], [7])
    assert json.loads(detail["previous_analysis_json"]) == {"rules": "old"}


def test_the_job_store_clears_the_analysis_error_and_refuses_an_unknown_job(tmp_path):
    store = JobStore(Storage(tmp_path / "data"))
    job = store.create("fabricated.pdf")
    store.set_result(job.id, "# F", "<p>F</p>", analysis=None, analysis_error="fabricated refusal")
    assert store.apply_reanalysis(job.id, {"rules": "new"}) == {"rules": "new"}
    assert (store.get(job.id).analysis, store.get(job.id).analysis_error) == ({"rules": "new"}, None)
    assert store.apply_reanalysis("no-such-job", {"rules": "new"}) is None


# --- the review writer the replay uses ------------------------------------------------------------------------------

DECIDED_AT = "2031-04-02T09:00:00+00:00"


def _payload(rows=ROWS):
    """A fabricated business checking statement, analysed by the real analysis path."""
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(_report("FABRICATED BUSINESS CHECKING", "000000001010", 1500.0, rows))


def test_the_review_writer_keeps_the_decision_s_own_time_and_leaves_the_rebuild_to_its_caller():
    from analysis.revenue import rebuild_serialized_revenue_views, record_serialized_revenue_review

    analysis = _payload()
    metrics = copy.deepcopy(analysis["metrics"])
    record = record_serialized_revenue_review(analysis, source_location="transaction:2", decision="confirm",
                                              reviewed_at=DECIDED_AT)
    assert record is _records(analysis)["transaction:2"]
    assert (record["revenue_review_status"], record["revenue_classification"], record["revenue_reviewed_at"]) == (
        "confirmed", "verified_revenue", DECIDED_AT)
    assert analysis["metrics"] == metrics  # the views wait for the caller's one rebuild
    rebuild_serialized_revenue_views(analysis)
    assert analysis["metrics"]["verified_revenue_total"] == metrics["verified_revenue_total"] + 300.0
    reset = record_serialized_revenue_review(analysis, source_location="transaction:2", decision="reset",
                                             reviewed_at=DECIDED_AT)
    assert (reset["revenue_review_status"], reset["revenue_reviewed_at"]) == ("pending", None)


@pytest.mark.parametrize("location, decision, refusal", [
    ("transaction:1", "confirm", ValueError),   # revenue a rule verified: not the analyst's to decide
    ("transaction:99", "confirm", LookupError),  # no such row
    ("transaction:2", "approve", ValueError),    # no such decision
])
def test_the_review_writer_writes_nothing_when_it_refuses(location, decision, refusal):
    from analysis.revenue import record_serialized_revenue_review

    analysis = _payload()
    before = copy.deepcopy(analysis)
    with pytest.raises(refusal):
        record_serialized_revenue_review(analysis, source_location=location, decision=decision)
    assert analysis == before


# --- replaying the analyst's decisions ------------------------------------------------------------------------------

# The same statement read under new rules, where one deposit now prints another amount: the row at that location is
# no longer the posting the analyst decided.
CHANGED_ROWS = [(day, text, 250.0) if text == "DEPOSIT FABRICATED TWO" else (day, text, amount)
                for day, text, amount in ROWS]
# The same statement with one more row read near the top: every later posting moved one location down.
SHIFTED_ROWS = [ROWS[0], (3, "DEPOSIT FABRICATED EARLY", 50.0), *ROWS[1:]]
# Two deposits alike but for their day; then the same statement where the first of them prints another amount.
TWIN_ROWS = [ROWS[0], (4, "DEPOSIT FABRICATED TWIN", 300.0), (6, "DEPOSIT FABRICATED TWIN", 300.0), *ROWS[3:]]
TWIN_CHANGED_ROWS = [ROWS[0], (4, "DEPOSIT FABRICATED TWIN", 350.0), *TWIN_ROWS[2:]]


def _decision(row_id, analysis, location, decision, account=1):
    """A `review_decisions` row as `JobStore.review_history` returns it, its prior state the record in `analysis`."""
    return {"id": row_id, "job_id": "fabricated-job", "source_location": location, "decision": decision,
            "actor": "local-analyst", "decided_at": DECIDED_AT,
            "prior_state": json.dumps(_records(analysis, account)[location])}


def _alike_in_both_accounts():
    """`_two_accounts()` where the savings account's second row is the checking account's second deposit, printed
    under the savings account's own number: one location, description and amount in two accounts."""
    from analysis.revenue import rebuild_serialized_revenue_views

    payload = _two_accounts()
    checking, savings = (account["statement"]["transactions"] for account in payload["accounts"])
    row = copy.deepcopy(checking[1])
    row["classification"]["account"] = savings[1]["classification"]["account"]
    savings[1] = row
    return rebuild_serialized_revenue_views(payload)


def test_a_decision_is_replayed_where_its_posting_is_unchanged():
    from webapp.reanalysis import replay_reviews

    old, new = _payload(), _payload()
    before = new["metrics"]["verified_revenue_total"]
    replay = replay_reviews(new, [_decision(7, old, "transaction:2", "confirm")])
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((7,), (), ())
    record = _records(replay.analysis)["transaction:2"]
    assert (record["revenue_review_status"], record["revenue_classification"]) == ("confirmed", "verified_revenue")
    assert replay.analysis["metrics"]["verified_revenue_total"] == before + 300.0
    assert new["metrics"]["verified_revenue_total"] == before  # the analysis handed in is left as it was
    # The decision keeps the time the analyst made it, on the row and on every copy of its record.
    assert record["revenue_reviewed_at"] == DECIDED_AT
    copies = [item for item in replay.analysis["classifications"] if item["source_location"] == "transaction:2"]
    assert [item["revenue_reviewed_at"] for item in copies] == [DECIDED_AT]


def test_a_decision_is_not_replayed_where_the_row_at_its_location_changed():
    from webapp.reanalysis import replay_reviews

    old = _payload()
    changed = replay_reviews(_payload(CHANGED_ROWS), [_decision(8, old, "transaction:3", "reject")])
    assert (changed.replayed, changed.not_replayed) == ((), (8,))
    assert _records(changed.analysis)["transaction:3"]["revenue_review_status"] == "pending"
    # The posting still exists one row further down. A location names a row, so the decision does not follow it.
    shifted = replay_reviews(_payload(SHIFTED_ROWS), [_decision(9, old, "transaction:2", "confirm")])
    assert (shifted.replayed, shifted.not_replayed) == ((), (9,))
    records = _records(shifted.analysis)
    assert records["transaction:2"]["revenue_review_status"] == "pending"
    assert records["transaction:3"]["revenue_review_status"] == "pending"


def test_a_posting_s_latest_decision_is_replayed_and_a_reset_needs_nothing():
    from webapp.reanalysis import replay_reviews

    old = _payload()
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, old, "transaction:4", "confirm"),
               _decision(3, old, "transaction:2", "reject"), _decision(4, old, "transaction:4", "reset")]
    replay = replay_reviews(_payload(), history)
    assert (replay.replayed, replay.not_replayed) == ((3,), ())
    records = _records(replay.analysis)
    assert records["transaction:2"]["revenue_review_status"] == "rejected"
    assert records["transaction:4"]["revenue_review_status"] == "pending"


def test_each_account_gets_its_own_decisions_back():
    from webapp.reanalysis import replay_reviews

    old = _two_accounts()
    history = [_decision(1, old, "transaction:2", "confirm", account=2),
               _decision(2, old, "transaction:2", "reject", account=1)]
    replay = replay_reviews(_two_accounts(), history)
    assert (replay.replayed, replay.not_replayed) == ((1, 2), ())
    assert _records(replay.analysis, 2)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert _records(replay.analysis, 1)["transaction:2"]["revenue_review_status"] == "rejected"


def test_a_posting_two_accounts_hold_alike_is_not_guessed():
    from webapp.reanalysis import replay_reviews

    old, new = _two_accounts(), _two_accounts()
    new["accounts"][1] = copy.deepcopy(new["accounts"][0])  # both accounts now print the same row at the same place
    replay = replay_reviews(new, [_decision(3, old, "transaction:2", "confirm", account=1)])
    assert (replay.replayed, replay.not_replayed) == ((), (3,))


def test_a_decision_never_follows_its_posting_into_another_account():
    """The account number is part of what a decision was made on: a deposit alike in two accounts is two postings."""
    from webapp.reanalysis import replay_reviews

    old, new = _alike_in_both_accounts(), _alike_in_both_accounts()
    # The savings account's deposit now prints another amount; the checking account's, alike before, is unchanged.
    changed = new["accounts"][1]["statement"]["transactions"][1]
    changed["amount"] = changed["classification"]["amount"] = 350.0
    replay = replay_reviews(new, [_decision(4, old, "transaction:2", "confirm", account=2)])
    assert (replay.replayed, replay.not_replayed) == ((), (4,))
    assert _records(replay.analysis, 1)["transaction:2"]["revenue_review_status"] == "pending"


@pytest.mark.parametrize("prior_state", [None, "not a record", "[1, 2]"])
def test_a_decision_whose_prior_state_cannot_be_read_is_not_replayed(prior_state):
    from webapp.reanalysis import replay_reviews

    history = [{"id": 1, "source_location": "transaction:2", "decision": "confirm", "decided_at": DECIDED_AT,
                "prior_state": prior_state},
               {"id": 2, "source_location": "transaction:3", "decision": "reset", "decided_at": DECIDED_AT,
                "prior_state": prior_state}]
    replay = replay_reviews(_payload(), history)
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((), (1,), ())


def test_a_decision_that_cannot_be_applied_leaves_the_analysis_as_it_was():
    from webapp.reanalysis import replay_reviews

    old, new = _payload(), _payload()
    # Another credit of the account has lost its classification record: rebuilding the revenue views refuses, after
    # the decision was already written onto its row.
    new["statement"]["transactions"][0]["classification"] = None
    before = copy.deepcopy(new)
    replay = replay_reviews(new, [_decision(7, old, "transaction:2", "confirm")])
    assert (replay.replayed, replay.not_replayed) == ((), (7,))
    assert replay.analysis == before and new == before


def test_every_decision_is_replayed_onto_one_copy_rebuilt_once(monkeypatch):
    """The replay runs under the statement's review lock, so its cost must not grow with the decisions times the
    statement: one copy of the analysis takes every decision, and its revenue views are rebuilt once, after the
    last."""
    import webapp.reanalysis as reanalysis

    old = _payload()
    rebuilds, copies = [], []
    rebuild, deepcopy = reanalysis.rebuild_serialized_revenue_views, reanalysis.deepcopy
    monkeypatch.setattr(reanalysis, "rebuild_serialized_revenue_views",
                        lambda analysis: rebuilds.append(1) or rebuild(analysis))
    monkeypatch.setattr(reanalysis, "deepcopy", lambda value: copies.append(1) or deepcopy(value))
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, old, "transaction:3", "reject"),
               _decision(3, old, "transaction:4", "confirm")]
    replay = reanalysis.replay_reviews(_payload(), history)
    assert (replay.replayed, len(rebuilds), len(copies)) == ((1, 2, 3), 1, 1)
    records = _records(replay.analysis)
    assert [records[f"transaction:{number}"]["revenue_review_status"] for number in (2, 3, 4)] == [
        "confirmed", "rejected", "confirmed"]


def _ruled(analysis, location, account=1):
    """`analysis` after a new rule decided the deposit at `location` (S2's D1, say: a credit from a financing payee is
    financing proceeds): the rule classifies the credit itself, so the row no longer awaits the analyst, who could not
    review it again (analysis/revenue.py refuses any row a rule decided)."""
    from analysis.revenue import rebuild_serialized_revenue_views

    _records(analysis, account)[location].update(
        revenue_classification="non_revenue", revenue_initial_classification="non_revenue",
        revenue_review_required=False, revenue_review_status="not_required",
        revenue_match_method="financing_proceeds_credit")
    return rebuild_serialized_revenue_views(analysis)


def test_a_decision_on_a_row_a_rule_now_decides_is_reported_apart():
    from webapp.reanalysis import replay_reviews

    old = _payload()
    replay = replay_reviews(_ruled(_payload(), "transaction:2"), [_decision(5, old, "transaction:2", "confirm")])
    assert (replay.replayed, replay.not_replayed, replay.decided_by_rules) == ((), (), (5,))
    assert _records(replay.analysis)["transaction:2"]["revenue_classification"] == "non_revenue"


def test_a_review_redone_on_a_changed_row_is_not_reported_again():
    from webapp.reanalysis import replay_reviews

    old, changed = _payload(), _payload(CHANGED_ROWS)
    # The analyst's decision; a re-analysis on which its row prints another amount; the analyst's redo on that row.
    history = [_decision(1, old, "transaction:3", "confirm"), _decision(2, changed, "transaction:3", "confirm")]
    replay = replay_reviews(_payload(CHANGED_ROWS), history)
    assert (replay.replayed, replay.not_replayed) == ((2,), ())
    assert _records(replay.analysis)["transaction:3"]["revenue_review_status"] == "confirmed"


def test_a_review_redone_where_its_posting_moved_is_not_reported_again():
    from webapp.reanalysis import replay_reviews

    old, shifted = _payload(), _payload(SHIFTED_ROWS)
    # The posting decided at transaction:2 moved to transaction:3, and the analyst decided it again there.
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, shifted, "transaction:3", "confirm")]
    replay = replay_reviews(_payload(SHIFTED_ROWS), history)
    assert (replay.replayed, replay.not_replayed) == ((2,), ())
    records = _records(replay.analysis)
    assert (records["transaction:2"]["revenue_review_status"], records["transaction:3"]["revenue_review_status"]) == (
        "pending", "confirmed")


def test_a_decision_on_a_posting_alike_on_another_day_is_not_a_redo():
    from webapp.reanalysis import replay_reviews

    old = _payload(TWIN_ROWS)
    history = [_decision(1, old, "transaction:2", "confirm"), _decision(2, old, "transaction:3", "confirm")]
    # While both twins are unchanged, each keeps its own decision.
    both = replay_reviews(_payload(TWIN_ROWS), history)
    assert (both.replayed, both.not_replayed) == ((1, 2), ())
    # When the first prints another amount, its decision needs redoing: the decision on the second twin was made on
    # another day's posting, so it did not redo the first.
    changed = replay_reviews(_payload(TWIN_CHANGED_ROWS), history)
    assert (changed.replayed, changed.not_replayed) == ((2,), (1,))


def test_a_decision_on_another_account_is_not_a_redo():
    """A redo is made on the same account number: the other account's row at the same location is another posting."""
    from webapp.reanalysis import replay_reviews

    old, new = _two_accounts(), _two_accounts()
    changed = new["accounts"][0]["statement"]["transactions"][1]  # the checking account's transaction:2
    changed["amount"] = changed["classification"]["amount"] = 350.0
    history = [_decision(1, old, "transaction:2", "confirm", account=1),
               _decision(2, old, "transaction:2", "confirm", account=2)]
    replay = replay_reviews(new, history)
    assert (replay.replayed, replay.not_replayed) == ((2,), (1,))

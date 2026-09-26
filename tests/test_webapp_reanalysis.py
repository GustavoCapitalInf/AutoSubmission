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


# --- re-running the statement through the worker's own path ---------------------------------------------------------

PDF = b"%PDF-1.7\nfabricated statement for the re-analysis tests"
WITHHELD = "(message withheld; an exception message can quote statement text)"


@pytest.fixture
def private_store(monkeypatch, tmp_path):
    """A job store of its own (so an artifact cache of its own), installed where the routes read it. The visual pair
    stays off, as it is by default: these statements are read by the fabricated reader below."""
    from webapp import app as webapp_app

    store = JobStore(Storage(tmp_path / "data"))
    monkeypatch.setattr(webapp_app, "store", store)
    monkeypatch.delenv("OCR_ALLOW_VISUAL_PAIR", raising=False)
    monkeypatch.delenv("OCR_VISUAL_PAIR_LEGACY_VISUAL", raising=False)
    return store


class _Pipeline:
    """The worker's two expensive stages, fabricated: a reader that counts its reads and, like the real ladder
    (ocr/pipeline.py), names its rung before it reads; and an analysis stage that answers with the payload of the rules
    in force. Everything between them (the worker, the artifact cache, the job store) is real, so an upload leaves the
    reading cached exactly as production does.

    `announce = False` makes a reader that names no stage before it reads, and `stream = True` one that streams text
    through the live view before it reads: each takes one of the re-analysis's guards out of the way of the other."""

    def __init__(self, monkeypatch, store):
        self.monkeypatch, self.store = monkeypatch, store
        self.reads = 0
        self.announce = True
        self.stream = False
        self.payload = None
        self.analysis_failure = None
        monkeypatch.setattr("webapp.worker.parse_statement", self._read)
        monkeypatch.setattr("webapp.worker.analyze_document", self._analyze)
        monkeypatch.setattr("webapp.worker.document_to_json", lambda document: copy.deepcopy(self.payload))

    def _read(self, pdf_bytes, source_file="", on_stage=None, on_page_delta=None, **kwargs):
        from ocr.document import StatementMarkdown

        if self.stream and on_page_delta is not None:
            on_page_delta(0, "FABRICATED")
        if self.announce and on_stage is not None:
            on_stage("native")
        self.reads += 1
        return StatementMarkdown(source_file=source_file, model="fabricated-reader",
                                 pages=["FABRICATED STATEMENT PAGE"])

    def _analyze(self, markdown, **kwargs):
        if self.analysis_failure is not None:
            raise self.analysis_failure
        return object()

    def upload(self, payload, filename="fabricated.pdf", *, force_ocr=False, parse_mode="auto"):
        """One upload through the real worker, with the job's own read flag and parse mode; returns the job id."""
        from webapp.worker import run_job

        self.payload = payload
        job = self.store.create(filename, pdf_bytes=PDF, force_ocr=force_ocr, parse_mode=parse_mode)
        run_job(job.id, PDF, filename, self.store, force_ocr=force_ocr, parse_mode=parse_mode)
        assert self.store.get(job.id).status == "done"
        return job.id

    def new_rules(self, payload):
        """What a release of new rules does: the analysis stage version moves on, so the cached analysis is not
        served, and the analysis stage answers under the new rules. The reading stays cached."""
        from webapp import artifact_cache

        self.monkeypatch.setattr(artifact_cache, "ANALYSIS_STAGE_VERSION", artifact_cache.ANALYSIS_STAGE_VERSION + 1)
        self.payload = payload

    def forget_ocr(self):
        """The reading is no longer cached (a pruned cache, a new OCR toolchain)."""
        for entry in self.store.storage.cache_entries("ocr"):
            self.store.storage.cache_forget("ocr", entry["cache_key"])

    def drift_ocr(self):
        """The cached reading fails its own round-trip check (`cached_ocr` in webapp/artifact_cache.py): the cache
        takes it for a miss after answering a hit, and would read the statement again."""
        for entry in self.store.storage.cache_entries("ocr"):
            path = self.store.cache.root / entry["artifact_path"]
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["artifact"]["document"]["visual_pair"] = {"fabricated": True}
            payload["artifact"]["document"]["visual_pair_sha256"] = "0" * 64
            path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def pipeline(monkeypatch, private_store):
    return _Pipeline(monkeypatch, private_store)


@pytest.fixture
def visual_pair(monkeypatch, tmp_path):
    """The visual pair, fabricated at its one entry point (`vlm.pair.extract_visual_pair`, imported by the worker when
    it reads), as tests/test_private_artifacts.py does. It records each call and answers as the pair does from its own
    local evidence index: it names no step and streams nothing. Its customer-data fence is opened for these fabricated
    statements, and its private evidence root is a temporary directory. The answer is not a pair document (no pair
    evidence, another model name), so the fabricated analysis stage reads it."""
    from ocr import private_artifacts
    from ocr.document import StatementMarkdown

    calls = []

    def extract(pdf, **kwargs):
        calls.append(pdf)
        return StatementMarkdown(source_file="statement.pdf", model="fabricated-pair-reader",
                                 pages=["FABRICATED STATEMENT PAGE"])

    monkeypatch.setenv(private_artifacts.PRIVATE_ROOT_ENV, str(tmp_path / "private"))
    monkeypatch.setattr("webapp.worker.check_remote_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr("vlm.pair.extract_visual_pair", extract)
    return calls


def _stamped(payload, parse_mode="auto"):
    """A payload as the worker saves it: stamped with the parse mode it ran under (webapp/worker.py:392-393)."""
    return {**payload, "parse_mode": parse_mode}


def _json(value):
    return json.loads(json.dumps(value))


def test_a_rerun_reads_the_statement_from_the_ocr_cache_and_leaves_the_saved_job_alone(pipeline, private_store):
    from webapp.reanalysis import rerun_analysis

    old, new = _payload(), _payload(SHIFTED_ROWS)
    job_id = pipeline.upload(old)
    assert pipeline.reads == 1
    pipeline.new_rules(new)
    statuses = len(private_store.storage.audit_events("status_change", job_id=job_id))
    telemetry = len(private_store.storage.telemetry_records())

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert rerun.reason is None and rerun.analysis == _stamped(new)
    assert pipeline.reads == 1  # the statement was not read again
    hits = [json.loads(row["detail"])["stage"] for row in private_store.storage.audit_events("cache_hit", job_id=job_id)]
    assert "ocr" in hits
    # Nothing of the saved job moved: no status change, no telemetry record, the same analysis in memory and on disk.
    saved = private_store.get(job_id)
    assert saved.status == "done" and saved.analysis == _stamped(old)
    assert json.loads(private_store.storage.load_job(job_id)["analysis_json"]) == _json(_stamped(old))
    assert len(private_store.storage.audit_events("status_change", job_id=job_id)) == statuses
    assert len(private_store.storage.telemetry_records()) == telemetry


def test_a_rerun_keeps_the_job_s_own_parse_mode(pipeline, private_store):
    """A job uploaded in deterministic mode is re-run in deterministic mode: in auto mode the analysis stage may make
    the hosted call the operator did not choose for this job."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload(), parse_mode="deterministic")
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.reason, rerun.analysis) == (None, _stamped(new, "deterministic"))


def test_a_statement_the_visual_pair_read_is_reanalyzed_from_the_pair_s_cached_reading(
        pipeline, private_store, visual_pair):
    """A job uploaded with Force visual OCR was read by the visual pair. Its re-analysis takes the same path (the
    job's own read flag), and the pair's reading comes from the cache: the pair is not called again."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload(), force_ocr=True)
    assert (len(visual_pair), pipeline.reads) == (1, 0)
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.reason, rerun.analysis) == (None, _stamped(new))
    assert (len(visual_pair), pipeline.reads) == (1, 0)


@pytest.mark.parametrize("failure, reason", [
    (RuntimeError("no deterministic parser matched this statement"), "no deterministic parser matched this statement"),
    (RuntimeError("FABRICATED STATEMENT TEXT"), f"analysis stage failed: RuntimeError {WITHHELD}"),
])
def test_a_rerun_that_produces_no_analysis_gives_the_worker_s_own_reason(pipeline, private_store, failure, reason):
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.analysis_failure = failure
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, reason)


def test_a_rerun_whose_analysis_comes_from_another_reading_is_not_accepted(pipeline, private_store):
    from webapp.reanalysis import READS_DIFFERENTLY, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    # The saved analysis was made from another reading than the one the current rules analyse: a statement the visual
    # pair read, say, which the deterministic path now claims from its own cached reading.
    saved = copy.copy(private_store.get(job_id))
    saved.markdown = "<!-- fabricated: the reading the saved analysis was made from -->"
    rerun = rerun_analysis(private_store, saved, private_store.pdf_bytes(job_id))
    assert pipeline.reads == 1
    assert (rerun.analysis, rerun.reason) == (None, READS_DIFFERENTLY)


# --- the reading comes from the cache, or the re-analysis is refused ------------------------------------------------


def test_a_rerun_runs_no_reader_for_a_statement_whose_reading_is_not_cached(pipeline, private_store):
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    old = _payload()
    job_id = pipeline.upload(old)
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()
    statuses = len(private_store.storage.audit_events("status_change", job_id=job_id))

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1  # the reader was never called
    assert private_store.storage.cache_entries("ocr") == []  # and nothing was read into the cache
    saved = private_store.get(job_id)
    assert (saved.status, saved.analysis) == ("done", _stamped(old))
    assert len(private_store.storage.audit_events("status_change", job_id=job_id)) == statuses


def test_a_miss_stops_the_run_before_a_reader_that_names_no_stage(pipeline, private_store):
    """The cache lookup is the guard, not the stage a reader names: here nothing but the lookup stands between the run
    and the reader."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()
    pipeline.announce = False
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1


def test_a_cached_reading_that_fails_its_own_checks_is_not_read_again(pipeline, private_store):
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.drift_ocr()
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1  # stopped where the ladder named its rung, before the rung read


def test_a_reading_that_streams_before_it_names_a_stage_is_stopped(pipeline, private_store):
    """A cached reading that fails its own checks is read again after the lookup answered a hit; a reader that streams
    its text before it names a stage is stopped at its first streamed chunk."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.drift_ocr()
    pipeline.announce, pipeline.stream = False, True
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert pipeline.reads == 1


def test_the_visual_pair_is_never_called_for_a_reading_that_is_not_cached(pipeline, private_store, visual_pair):
    """The pair answers from its own evidence, or asks its model servers for their models, before it names a step, so
    on its path the cache lookup is the only guard."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    job_id = pipeline.upload(_payload(), force_ocr=True)
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert (len(visual_pair), pipeline.reads) == (1, 0)  # the upload's call, and no other


def test_a_statement_that_now_needs_the_visual_pair_is_refused_without_calling_it(
        pipeline, private_store, visual_pair, monkeypatch):
    """With the pair on, a statement the deterministic path no longer analyses falls back to the visual pair
    (webapp/worker.py), a reading this statement never had."""
    from webapp.reanalysis import READING_NOT_CACHED, rerun_analysis

    monkeypatch.setenv("OCR_ALLOW_VISUAL_PAIR", "1")
    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.analysis_failure = RuntimeError("no deterministic parser matched this statement")
    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))
    assert (rerun.analysis, rerun.reason) == (None, READING_NOT_CACHED)
    assert (visual_pair, pipeline.reads) == ([], 1)


# --- the upload queue's worker stays the artifact cache's one writer ------------------------------------------------


def _cache_files(store):
    """Every artifact-cache entry by stage: its key and the bytes of its file. Hit counts are left out, since serving
    a hit updates them."""
    return {stage: [(entry["cache_key"], (store.cache.root / entry["artifact_path"]).read_bytes())
                    for entry in store.storage.cache_entries(stage)]
            for stage in ("ocr", "analysis", "report")}


def test_a_rerun_writes_no_analysis_and_no_report_into_the_cache(pipeline, private_store):
    """The new analysis and the report rendered again are not cached: an upload of the same statement writing the
    same entry at that moment could fail on the cache's one temporary file per entry."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload())
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    for entry in private_store.storage.cache_entries("report"):
        private_store.storage.cache_forget("report", entry["cache_key"])  # so the report is rendered again
    before = _cache_files(private_store)

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert (rerun.reason, rerun.analysis) == (None, _stamped(new))
    assert _cache_files(private_store) == before


def test_a_pair_reading_answered_again_from_the_pair_s_own_evidence_is_not_written_back(
        pipeline, private_store, visual_pair):
    """A cached pair reading that fails its own checks is read again, and the pair answers from its own local
    evidence, naming no step (the fabricated pair answers that way). That answer is a reading already made, so the
    re-analysis goes on with it, and it leaves the drifted entry for the next upload to repair."""
    from webapp.reanalysis import rerun_analysis

    job_id = pipeline.upload(_payload(), force_ocr=True)
    new = _payload(SHIFTED_ROWS)
    pipeline.new_rules(new)
    pipeline.drift_ocr()
    before = _cache_files(private_store)

    rerun = rerun_analysis(private_store, private_store.get(job_id), private_store.pdf_bytes(job_id))

    assert (rerun.reason, rerun.analysis) == (None, _stamped(new))
    assert (len(visual_pair), pipeline.reads) == (2, 0)
    assert _cache_files(private_store) == before


# --- the route ------------------------------------------------------------------------------------------------------


def _reanalyze(job_id, body=None):
    from webapp.app import app

    return app.test_client().post(f"/analysis/{job_id}/reanalyze", json={} if body is None else body)


def _review(job_id, location, decision):
    from webapp.app import app

    response = app.test_client().post(f"/analysis/{job_id}/revenue-review",
                                      json={"source_location": location, "decision": decision})
    assert response.status_code == 200


def test_a_reanalysis_replaces_the_analysis_in_place(pipeline, private_store):
    from webapp.app import app

    old, new = _payload(), _payload(SHIFTED_ROWS)
    job_id = pipeline.upload(old)
    before = private_store.storage.load_job(job_id)
    pipeline.new_rules(new)

    response = _reanalyze(job_id)

    assert response.status_code == 200
    body = response.get_json()
    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (0, 0, 0)
    # The same job: its id, its creation time and its source view do not change; its analysis does.
    after = private_store.storage.load_job(job_id)
    assert after["id"] == job_id and after["status"] == "done"
    assert (after["created_at"], after["markdown"], after["html"]) == (
        before["created_at"], before["markdown"], before["html"])
    assert private_store.get(job_id).analysis == _stamped(new)
    assert json.loads(after["analysis_json"]) == _json(_stamped(new))
    # The page is drawn from the answer, which is the analysis as /analysis/<job> now serves it, masked.
    assert body["analysis"] == app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]
    assert body["analysis"]["statement"]["account_number"] == "****1010"
    # The analysis replaced is in the audit log, verbatim.
    events = private_store.storage.audit_events("reanalysis", job_id=job_id)
    assert len(events) == 1
    detail = json.loads(events[0]["detail"])
    assert detail["previous_analysis_json"] == before["analysis_json"]
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [], [], [])
    # A restart reads the new analysis back.
    assert JobStore(Storage(private_store.storage.data_dir)).get(job_id).analysis == _json(_stamped(new))


def test_a_reanalysis_replays_the_revenue_decisions_whose_posting_is_unchanged(pipeline, private_store):
    job_id = pipeline.upload(_payload())
    _review(job_id, "transaction:2", "confirm")  # unchanged under the new rules: replayed
    _review(job_id, "transaction:3", "reject")   # its row now prints another amount: needs redoing
    _review(job_id, "transaction:4", "confirm")
    _review(job_id, "transaction:4", "reset")    # left pending: nothing to redo
    history = private_store.review_history(job_id)
    pipeline.new_rules(_payload(CHANGED_ROWS))

    body = _reanalyze(job_id).get_json()

    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (1, 1, 0)
    records = _records(private_store.get(job_id).analysis)
    assert records["transaction:2"]["revenue_review_status"] == "confirmed"
    assert records["transaction:2"]["revenue_reviewed_at"] == history[0]["decided_at"]
    assert records["transaction:3"]["revenue_review_status"] == "pending"
    assert records["transaction:4"]["revenue_review_status"] == "pending"
    assert _records(body["analysis"])["transaction:2"]["revenue_review_status"] == "confirmed"
    # The audit row names the decisions by id; replaying records no decision of its own.
    detail = json.loads(private_store.storage.audit_events("reanalysis", job_id=job_id)[0]["detail"])
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [history[0]["id"]], [history[1]["id"]], [])
    assert private_store.review_history(job_id) == history


def test_a_reanalysis_reports_the_reviews_a_rule_now_decides(pipeline, private_store):
    """Nothing re-labels silently (D12): a deposit the analyst confirmed that a rule of the current analysis now
    decides is not replayed, and the answer says so."""
    job_id = pipeline.upload(_payload())
    _review(job_id, "transaction:2", "confirm")
    history = private_store.review_history(job_id)
    pipeline.new_rules(_ruled(_payload(), "transaction:2"))

    body = _reanalyze(job_id).get_json()

    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (0, 0, 1)
    record = _records(private_store.get(job_id).analysis)["transaction:2"]
    assert (record["revenue_classification"], record["revenue_review_status"]) == ("non_revenue", "not_required")
    detail = json.loads(private_store.storage.audit_events("reanalysis", job_id=job_id)[0]["detail"])
    assert (detail["reviews_replayed"], detail["reviews_not_replayed"], detail["reviews_decided_by_rules"]) == (
        [], [], [history[0]["id"]])


def test_a_reanalysis_puts_each_account_s_decisions_back_on_that_account(pipeline, private_store):
    from webapp.app import app

    job_id = pipeline.upload(_two_accounts())
    response = app.test_client().post(f"/analysis/{job_id}/revenue-reviews", json={"decisions": [
        {"source_location": "transaction:2", "decision": "confirm", "account": 1},
        {"source_location": "transaction:2", "decision": "reject", "account": 2}]})
    assert response.status_code == 200
    pipeline.new_rules(_two_accounts())

    body = _reanalyze(job_id).get_json()

    assert (body["reviews_replayed"], body["reviews_not_replayed"]) == (2, 0)
    analysis = private_store.get(job_id).analysis
    assert _records(analysis, 1)["transaction:2"]["revenue_review_status"] == "confirmed"
    assert _records(analysis, 2)["transaction:2"]["revenue_review_status"] == "rejected"


def test_an_unknown_job_is_not_found(private_store):
    response = _reanalyze("no-such-job")
    assert response.status_code == 404 and response.get_json() == {"error": "job not found"}


def test_a_job_that_is_not_finished_is_refused(private_store):
    queued = private_store.create("fabricated.pdf", pdf_bytes=PDF)  # still waiting for the worker
    failed = private_store.create("fabricated.pdf", pdf_bytes=PDF)
    private_store.set_error(failed.id, "fabricated failure")
    for job_id in (queued.id, failed.id):
        response = _reanalyze(job_id)
        assert response.status_code == 409 and response.get_json() == {"error": "job is not finished"}
    assert private_store.storage.audit_events("reanalysis") == []


def test_a_job_whose_pdf_is_not_stored_is_refused(pipeline, private_store):
    job_id = pipeline.upload(_payload())
    before = copy.deepcopy(private_store.get(job_id).analysis)
    private_store.storage.pdf_path(private_store.get(job_id).content_sha256).unlink()  # the stored PDF is gone
    never = private_store.create("fabricated.pdf")  # a job saved without its PDF
    private_store.set_result(never.id, "# F", "<p>F</p>", analysis=_payload())
    for refused in (job_id, never.id):
        response = _reanalyze(refused)
        assert response.status_code == 409 and response.get_json() == {"error": "the original PDF is not stored"}
    assert private_store.get(job_id).analysis == before
    assert private_store.storage.audit_events("reanalysis") == []


def test_a_request_that_is_not_a_json_object_is_refused(pipeline, private_store):
    from webapp.app import app

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    before = copy.deepcopy(private_store.get(job_id).analysis)
    form = app.test_client().post(f"/analysis/{job_id}/reanalyze",
                                  data={"reanalyze": "1"})  # a cross-site form cannot send JSON
    listed = _reanalyze(job_id, ["reanalyze"])
    assert form.status_code == listed.status_code == 400
    assert form.get_json() == {"error": "the request must be a JSON object"}
    assert private_store.get(job_id).analysis == before
    assert private_store.storage.audit_events("reanalysis") == []


def test_a_reanalysis_that_produces_no_analysis_keeps_the_saved_one(pipeline, private_store):
    from webapp.app import REANALYSIS_NOT_SAVED

    job_id = pipeline.upload(_payload())
    before = copy.deepcopy(private_store.get(job_id).analysis)
    stored_text = private_store.storage.load_job(job_id)["analysis_json"]
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.analysis_failure = RuntimeError("FABRICATED STATEMENT TEXT")

    response = _reanalyze(job_id)

    assert response.status_code == 422
    assert response.get_json() == {"error": REANALYSIS_NOT_SAVED,
                                   "reason": f"analysis stage failed: RuntimeError {WITHHELD}"}
    assert REANALYSIS_NOT_SAVED == "no new analysis was saved; the saved analysis is unchanged"
    assert "FABRICATED STATEMENT TEXT" not in response.get_data(as_text=True)
    assert private_store.get(job_id).analysis == before
    assert private_store.storage.load_job(job_id)["analysis_json"] == stored_text
    assert private_store.storage.audit_events("reanalysis", job_id=job_id) == []


def test_a_statement_whose_reading_is_not_cached_is_refused_and_runs_no_reader(pipeline, private_store):
    from webapp.app import REANALYSIS_NOT_SAVED
    from webapp.reanalysis import READING_NOT_CACHED

    job_id = pipeline.upload(_payload())
    stored_text = private_store.storage.load_job(job_id)["analysis_json"]
    pipeline.new_rules(_payload(SHIFTED_ROWS))
    pipeline.forget_ocr()

    response = _reanalyze(job_id)

    assert response.status_code == 422
    assert response.get_json() == {"error": REANALYSIS_NOT_SAVED, "reason": READING_NOT_CACHED}
    assert READING_NOT_CACHED == ("the reading this re-analysis needs is not cached, and a re-analysis only "
                                  "analyzes a reading already made; upload the statement again instead")
    assert pipeline.reads == 1  # the upload's read, and no other
    assert private_store.storage.load_job(job_id)["analysis_json"] == stored_text
    assert private_store.storage.audit_events("reanalysis", job_id=job_id) == []


def test_a_review_waits_for_a_reanalysis_of_the_same_statement(pipeline, private_store, monkeypatch):
    """A row's decision while its statement is being re-analyzed. Without the statement's lock it would be saved on
    the old analysis and then overwritten when the re-analysis saved its own, while its decision row stayed
    recorded."""
    from webapp import app as webapp_app

    job_id = pipeline.upload(_payload())
    pipeline.new_rules(_payload())
    entered, release = threading.Event(), threading.Event()
    save = private_store.apply_reanalysis

    def held_save(*args, **kwargs):
        entered.set()
        release.wait(5)
        return save(*args, **kwargs)

    monkeypatch.setattr(private_store, "apply_reanalysis", held_save)
    results = {}
    rerun = threading.Thread(target=lambda: results.update(rerun=_reanalyze(job_id)))
    review = threading.Thread(target=lambda: results.update(review=webapp_app.app.test_client().post(
        f"/analysis/{job_id}/revenue-review", json={"source_location": "transaction:3", "decision": "reject"})))
    rerun.start()
    assert entered.wait(5)
    review.start()
    review.join(timeout=1)
    waited = review.is_alive()
    release.set()
    rerun.join(5)
    review.join(5)
    assert waited
    assert results["rerun"].status_code == results["review"].status_code == 200
    assert _records(private_store.get(job_id).analysis)["transaction:3"]["revenue_review_status"] == "rejected"
    # A request naming no statement leaves no lock behind: the table of locks holds statements, not guesses.
    assert _reanalyze("no-such-job").status_code == 404 and "no-such-job" not in webapp_app._review_locks


# --- after S2 and S3: the current rules are the 5.0 rules, served through the flag groups --------------------------

#: The fabricated premium financier the 5.0 insurance rule is shown. S2 reads `PREMIUM_FINANCE_ALIASES` only inside
#: the insurance rule, so it is not one of S2's `FAKE_PAYEES`.
PREMIUM_FINANCE_PAYEE = "FABRICATED PFC"


def _saved_under_old_rules(payload):
    """A payload as a statement analysed before the 5.0 rules left it: every record stamped with the old version."""
    for account in payload["accounts"] if "accounts" in payload else [payload]:
        for transaction in account["statement"]["transactions"]:
            transaction["classification"]["classification_version"] = "4.1"
    return payload


def _every_group_rows():
    """A fabricated statement's rows: a deposit from the floor-plan, factoring and premium-finance payees each and an
    ordinary deposit, then one debit to a payee of each of the eleven flag groups, in FLAG_GROUPS order. The payees
    are S2's fabricated FAKE_PAYEES; the bank loan is the statement bank's own loan transfer (D5), which no payee
    registry names; premium financing is the fabricated premium financier above. Every row has an amount of its own,
    so no recurrence rule (D6) groups them. Returns the rows and the deposits' locations, in that order: floor plan,
    factoring, premium finance, ordinary."""
    from analysis.flag_groups import FLAG_GROUPS
    from tests.flag_group_fixtures import FAKE_PAYEES

    payee_of = {}
    for alias, (_entity, state) in FAKE_PAYEES.items():
        payee_of.setdefault(state, alias)
    debits = []
    for group in FLAG_GROUPS:
        if group.state is None:  # premium financing: an insurance row that also carries the flag
            debits.append(f"ACH DEBIT {PREMIUM_FINANCE_PAYEE} 0001")
        elif group.state == "bank_loan":
            debits.append("TRANSFER TO LOAN 0001")
        else:
            debits.append(f"ACH DEBIT {payee_of[group.state]} 0001")
    deposits = [f"{payee_of['floor_plan_financing']} DEPOSIT 0001", f"{payee_of['factoring']} DEPOSIT 0001",
                f"{PREMIUM_FINANCE_PAYEE} DEPOSIT 0001", "DEPOSIT FABRICATED ORDINARY"]
    rows = [(2 + index, text, 400.0 + 50.0 * index) for index, text in enumerate(deposits)]
    rows += [(2 + len(deposits) + index, text, -100.0 - 10.0 * index) for index, text in enumerate(debits)]
    return rows, [f"transaction:{index + 1}" for index in range(len(deposits))]


def test_a_reanalysis_under_the_5_0_rules_saves_and_serves_every_flag_group(pipeline, private_store, monkeypatch):
    """An integration pin (Task 11 of the S5 plan): the analysis stage is fabricated, and the payloads it answers with
    are built here by S2's real classifier: first with registries that know none of these payees (the rules the
    statement was analysed under), then with S2's fabricated payees and premium financier (the current rules)."""
    from analysis import transaction_classifier
    from analysis.flag_groups import FLAG_GROUPS
    from tests.flag_group_fixtures import fake_match
    from webapp.app import app

    keys = {group.key for group in FLAG_GROUPS}
    rows, deposits = _every_group_rows()
    monkeypatch.setattr(transaction_classifier, "match_known_payee", lambda normalized_text: None)
    monkeypatch.setattr(transaction_classifier, "PREMIUM_FINANCE_ALIASES", {})
    job_id = pipeline.upload(_saved_under_old_rules(_payload(rows)))
    for location in deposits:
        _review(job_id, location, "confirm")
    assert app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]["analysis_rules_outdated"] is True
    monkeypatch.setattr(transaction_classifier, "match_known_payee", fake_match)
    monkeypatch.setattr(transaction_classifier, "PREMIUM_FINANCE_ALIASES",
                        {"Fabricated Premium Finance": (PREMIUM_FINANCE_PAYEE,)})
    pipeline.new_rules(_payload(rows))

    body = _reanalyze(job_id).get_json()

    # The ordinary deposit keeps its review, and so does the factoring deposit: a factor's payout is the business's own
    # sales, a deposit the analyst decides, which now also carries the Factoring flag (owner ruling 2026-09-26). The
    # floor-plan deposit is financing proceeds now (D1), and the premium financier's keeps the insurance credit
    # treatment: a rule decides both, and the answer says so.
    assert (body["reviews_replayed"], body["reviews_not_replayed"], body["reviews_decided_by_rules"]) == (2, 0, 2)
    saved = private_store.get(job_id).analysis
    records = _records(saved)
    floor_plan, factoring, premium_financed, ordinary = deposits
    assert [records[location]["revenue_classification"] for location in deposits] == [
        "non_revenue", "verified_revenue", "non_revenue", "verified_revenue"]
    assert [records[location]["revenue_review_status"] for location in deposits] == [
        "not_required", "confirmed", "not_required", "confirmed"]
    assert records[floor_plan]["contributes_to_lender_credit_exclusion"] is True
    assert (records[factoring]["classification"], records[factoring]["flagged_group"],
            records[factoring]["contributes_to_lender_credit_exclusion"]) == ("factoring", "factoring", False)
    assert records[premium_financed]["classification"] == "insurance"
    # Every one of the eleven groups is saved: on its row, in the metrics and in the detection. The factoring deposit
    # is the one flagged credit, so twelve rows are flagged: the eleven debits and it.
    flagged = [record for record in records.values() if record.get("contributes_to_flagged_totals")]
    assert {record["flagged_group"] for record in flagged} == keys
    assert [record["source_location"] for record in flagged if record["direction"] == "credit"] == [factoring]
    assert len(flagged) == len(keys) + 1
    assert set(saved["metrics"]["flagged_groups"]) == keys
    assert saved["metrics"]["flagged_groups"]["factoring"]["count_credited"] == 1
    assert {position["group"] for position in saved["detection"]["flagged_positions"]} == keys
    assert {record["classification_version"] for record in records.values()} == {"5.0"}
    # Premium financing is no state of its own: the row stays insurance, in the insurance totals, and carries its flag.
    (premium,) = [record for record in flagged if record["flagged_group"] == "premium_financing"]
    assert (premium["classification"], premium["contributes_to_insurance_totals"]) == ("insurance", True)
    # The answer is the analysis as it is now served: every group is ticked by default, so every flagged row shows,
    # the factoring credit's among them, and the rules are current.
    served = _records(body["analysis"])
    assert [served[record["source_location"]]["flag_shown"] for record in flagged] == [True] * len(flagged)
    assert body["analysis"]["analysis_rules_outdated"] is False


def test_the_outdated_rules_flag_clears_after_a_reanalysis(pipeline, private_store):
    from webapp.app import app

    job_id = pipeline.upload(_saved_under_old_rules(_payload()))
    assert app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]["analysis_rules_outdated"] is True
    pipeline.new_rules(_payload())
    body = _reanalyze(job_id).get_json()
    assert body["analysis"]["analysis_rules_outdated"] is False
    assert app.test_client().get(f"/analysis/{job_id}").get_json()["analysis"]["analysis_rules_outdated"] is False

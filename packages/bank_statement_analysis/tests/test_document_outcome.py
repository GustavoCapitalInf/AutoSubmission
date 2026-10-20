"""The DOCUMENT outcome, and the telemetry readers taught the document shape.

L1-S3. Every payload here is CONSTRUCTED (`tests/l1s3_payloads.py`): the
document shape has never been published, so there is no real document to build
one from, and every branch under test is unreachable in production at this
tree.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from analysis.payload_shape import PayloadShapeError
from telemetry.diagnostics import diagnose, diagnose_document, empty_diagnostics
from telemetry.record import (
    DOCUMENT_LADDER,
    RATIFIED_OMISSION_REASONS,
    build_record,
    classify_document,
    classify_outcome,
)
from telemetry.stated_counts import evaluate, evaluate_accounts
from tests.l1s3_payloads import account_payload, document_payload, omission


# --- the ladder the fold ranks on ------------------------------------------


def test_the_document_ladder_is_the_ladder_the_regime_is_measured_on():
    """A private rank order would fold documents onto a ladder the
    non-regression regime does not read. The duplicate is deliberate (a cycle
    is worse) and this is what keeps the two equal."""
    from discovery.compare import LADDER

    assert DOCUMENT_LADDER == LADDER


def test_deferred_is_not_a_rung():
    """It is a statement about the RUN, so a document fold may not produce it."""
    assert "deferred" not in DOCUMENT_LADDER


# --- classify_outcome: the loud refusal ------------------------------------


def test_classify_outcome_refuses_the_document_shape():
    """Measured before the teaching: it answered `withheld/withheld_adb` — a
    refusal naming a check nobody ran."""
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
        classify_outcome(document_payload())


def test_classify_outcome_is_unchanged_on_every_shape_the_tree_publishes():
    assert classify_outcome(account_payload()) == ("validated", "approved")
    assert classify_outcome(account_payload(outcome="withheld")) == (
        "withheld", "withheld_adb")
    assert classify_outcome(account_payload(outcome="review")) == (
        "review", "integrity_flags")
    assert classify_outcome(None) == ("failed", "no_analysis")
    assert classify_outcome({}) == ("withheld", "withheld_adb")


# --- classify_document: the contract at its door (L1-S3 review BLOCK-1) ----


@pytest.mark.parametrize("not_a_payload", [[], "text", 3, object()])
def test_the_fold_refuses_a_non_mapping_with_a_type_error(not_a_payload):
    """It reads a published PAYLOAD, and says so at its own door.

    `TypeError`, not `PayloadShapeError`: "this is not a published payload at
    all" is a different statement from "this is the wrong one of the two
    published shapes", and a caller probing which call shape a function wants
    reads the first as *try the other argument*.
    """
    with pytest.raises(TypeError, match="reads a published payload"):
        classify_document(not_a_payload)


def test_the_fold_refuses_the_document_OBJECT_and_names_its_payload_function():
    """The exact call the L1-S2 resolver makes first.

    It used to be delegated to `classify_outcome` and die two frames down with
    `AttributeError: 'DocumentReport' object has no attribute 'get'`; the
    resolver narrows on `TypeError` to mean "try the other call shape", so it
    never reached the payload leg and eleven Q10 pins went red at the merged
    tree. The message names the function that turns the object into a payload.
    """
    from analysis.pipeline import DocumentReport

    with pytest.raises(TypeError, match="document_report_to_dict"):
        classify_document(DocumentReport(accounts=[]))


def test_the_fold_still_answers_none_and_a_mapping():
    """The door refuses a non-payload and nothing else."""
    assert classify_document(None) == ("failed", "no_analysis")
    assert classify_document({}) == ("withheld", "withheld_adb")


# --- classify_document: the fold -------------------------------------------


def test_the_document_outcome_is_todays_outcome_on_one_account():
    """By construction, not by measurement: an account payload never reaches
    the fold."""
    for outcome in ("validated", "review", "withheld"):
        payload = account_payload(outcome=outcome)
        assert classify_document(payload) == classify_outcome(payload)
    assert classify_document(None) == classify_outcome(None)
    assert classify_document(None, error_type="ValueError") == ("failed", "exception")
    assert classify_document(None, deferred="deferred_scanned") == (
        "deferred", "deferred_scanned")


def test_the_document_outcome_is_the_weakest_accounts():
    assert classify_document(document_payload(
        outcomes=("validated", "validated"))) == ("validated", "approved")
    assert classify_document(document_payload(
        outcomes=("validated", "review"))) == ("review", "account_integrity_flags")
    assert classify_document(document_payload(
        outcomes=("review", "withheld"))) == ("withheld", "account_withheld_adb")
    assert classify_document(document_payload(
        outcomes=("withheld", "validated"))) == ("withheld", "account_withheld_adb")


def test_the_weakest_account_wins_wherever_it_is_printed():
    """Printed order breaks TIES; it does not decide the outcome."""
    first = classify_document(document_payload(outcomes=("withheld", "validated")))
    last = classify_document(document_payload(outcomes=("validated", "withheld")))
    assert first == last == ("withheld", "account_withheld_adb")


def test_a_document_publishing_no_account_fails():
    payload = document_payload()
    payload["accounts"] = []
    assert classify_document(payload) == ("failed", "document_publishes_no_account")


def test_an_omission_on_ratified_evidence_does_not_lower_the_document():
    """The design's third override is deliberately NOT wired — Q10.

    §1.5 proposed that a ratified omission should stop a document being
    `validated` and file it `review/sibling_section_omitted`. L1-S2 records
    exactly such omissions on 15 documents batch 8 validated, each admitted on
    printed evidence, so wiring it would fold 15 protected documents from
    `validated` to `review` — a regression under the batch-9 doctrine and not a
    decision a stage that moves zero documents may take. The ruling is with
    Gustavo as Q10; until it lands, a ratified omission leaves the fold alone.
    """
    for reason in RATIFIED_OMISSION_REASONS:
        payload = document_payload(omitted_sections=(omission(reason),))
        assert classify_document(payload) == ("validated", "approved")


def test_one_validated_account_with_a_ratified_omission_stays_validated():
    """The protected shape L1-S2 produces, stated on its own (Q10)."""
    payload = document_payload(outcomes=("validated",),
                               omitted_sections=(omission(),))
    assert classify_document(payload) == ("validated", "approved")


def test_an_omission_on_unratified_evidence_fails_the_document():
    """L1-C17: the section should never have been published as omitted, so the
    document fails rather than being graded around it."""
    payload = document_payload(omitted_sections=(omission("absence_of_parsed_rows"),))
    assert classify_document(payload) == ("failed", "document_omission_unratified")


def test_the_omission_vocabulary_is_closed_against_absence():
    assert "absence_of_parsed_rows" not in RATIFIED_OMISSION_REASONS


def test_an_omission_never_raises_a_weak_account():
    """Every override that IS wired can only LOWER the result."""
    payload = document_payload(outcomes=("withheld", "validated"),
                               omitted_sections=(omission(),))
    assert classify_document(payload) == ("withheld", "account_withheld_adb")


def test_an_account_outcome_off_the_ladder_is_refused():
    """Ranking an unranked class would make it the document's class, and
    `compare.direction` scores it as neither improvement nor regression —
    invisible to the whole non-regression regime."""
    payload = document_payload()
    payload["accounts"][0]["__deferred__"] = True

    import telemetry.record as record

    original = record.classify_outcome

    def _off_ladder(account, **kwargs):
        if isinstance(account, dict) and account.get("__deferred__"):
            return "deferred", "deferred_scanned"
        return original(account, **kwargs)

    record.classify_outcome = _off_ladder
    try:
        with pytest.raises(ValueError, match="not on the ladder"):
            record.classify_document(payload)
    finally:
        record.classify_outcome = original


# --- the record --------------------------------------------------------------


def _record(payload):
    return build_record(
        run_id="l1s3", emitter="test", document={}, source={}, dispatch={},
        stages={}, model_calls=[], payload=payload,
    )


def test_the_record_carries_the_document_outcome():
    record = _record(document_payload(outcomes=("validated", "withheld")))
    assert record["outcome"]["class"] == "withheld"
    assert record["outcome"]["reason"] == "account_withheld_adb"


def test_the_record_is_unchanged_for_a_single_account_payload():
    payload = account_payload()
    record = _record(payload)
    assert (record["outcome"]["class"], record["outcome"]["reason"]) == (
        "validated", "approved")
    # MAJOR-3 (PHASE2_P20SEAM_REVIEW.md): build_record adds
    # source_path_unrecognized_model ALONGSIDE diagnose_document's own
    # closed taxonomy (never a member of it) — see
    # telemetry/record.py::build_record's "diagnostics" comment.
    assert record["diagnostics"] == {
        **empty_diagnostics(),
        "source_path_unrecognized_model": False,
    }


# --- diagnostics -------------------------------------------------------------


def test_diagnose_refuses_the_document_shape():
    """Measured before the teaching: an EMPTY diagnosis marked
    `evaluated=True`, riding in every discovery telemetry record."""
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
        diagnose(document_payload(), "withheld")


def test_diagnose_document_is_diagnose_on_an_account_payload():
    payload = account_payload(outcome="review")
    assert diagnose_document(payload, "review") == diagnose(payload, "review")
    assert diagnose_document(None, "review") == diagnose(None, "review")


def test_diagnose_document_unions_its_accounts():
    payload = document_payload(outcomes=("review", "review"))
    payload["accounts"][0]["integrity"]["flags"] = ["running_balance_breaks"]
    payload["accounts"][1]["integrity"]["flags"] = ["parser_ambiguous"]
    merged = diagnose_document(payload, "review")
    assert merged["evaluated"] is True
    assert merged["integrity_flags"] == ["parser_ambiguous", "running_balance_breaks"]
    assert "integrity:parser_ambiguous" in merged["codes"]
    assert "integrity:running_balance_breaks" in merged["codes"]
    # Two accounts, one transaction each.
    assert merged["counts"]["transactions"] == 2


def test_diagnose_document_never_publishes_one_accounts_diagnosis():
    """The union is the point: a selection would put one account's answer under
    the document's name."""
    payload = document_payload(outcomes=("review", "review"))
    payload["accounts"][1]["integrity"]["flags"] = ["parser_exception"]
    merged = diagnose_document(payload, "review")
    first = diagnose(payload["accounts"][0], "review")
    assert merged["codes"] != first["codes"]
    assert set(first["codes"]) <= set(merged["codes"])


def test_diagnose_document_is_empty_for_an_undiagnosable_class():
    assert diagnose_document(document_payload(), "validated") == empty_diagnostics()


def test_diagnose_document_does_not_mutate_the_payload():
    payload = document_payload(outcomes=("review", "review"))
    before = json.dumps(payload, sort_keys=True, default=str)
    diagnose_document(payload, "review")
    assert json.dumps(payload, sort_keys=True, default=str) == before


def test_the_counts_key_order_is_diagnoses_own():
    payload = document_payload(outcomes=("review", "review"))
    merged = diagnose_document(payload, "review")
    single = diagnose(payload["accounts"][0], "review")
    assert list(merged["counts"]) == list(single["counts"])
    assert list(merged) == list(single)


# --- stated counts -----------------------------------------------------------


def test_evaluate_refuses_the_document_shape():
    """Measured before the teaching: `check_unavailable/statement_absent` —
    "printed no counts" about a document whose accounts printed them."""
    with pytest.raises(PayloadShapeError, match="reader_is_account_scope"):
        evaluate(document_payload())


def test_evaluate_accounts_yields_one_observation_per_account():
    single = evaluate_accounts(account_payload())
    assert len(single) == 1
    assert single[0] == evaluate(account_payload())
    several = evaluate_accounts(document_payload(outcomes=("validated",) * 3))
    assert len(several) == 3
    assert [observation.transactions for observation in several] == [1, 1, 1]


def test_evaluate_accounts_never_sums_a_total_the_bank_never_printed():
    """A count check has no document-level meaning, so the answer is a list."""
    several = evaluate_accounts(document_payload())
    assert isinstance(several, list)
    assert len(several) == 2

def test_the_count_observer_reaches_the_per_account_reader():
    """MINOR-2. `evaluate_accounts` was written and had no caller anywhere in
    the tree outside its own test, while the observer's only entry point called
    the REFUSING `evaluate` — so on a multi-account document the count observer
    would have raised instead of observing each account.

    Checked with the census's own live-call helper, which skips constant-dead
    branches, so wiring it back into `if False:` does not satisfy this either.
    """
    import ast

    from tools.l1s3_surface_census import _called_names

    tree = ast.parse(pathlib.Path("telemetry/stated_counts.py").read_text(encoding="utf-8"))
    loader = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "observe_run"
    )
    called = _called_names(loader)
    assert "evaluate_accounts" in called
    assert "evaluate" not in called

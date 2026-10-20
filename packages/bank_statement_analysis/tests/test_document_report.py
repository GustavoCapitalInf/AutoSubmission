"""The document object and RULE S (L-1 stage 1).

`Statement` and `Report` are ONE ACCOUNT's and stay so. `DocumentReport` is the
object that knows one PDF can carry several accounts, and RULE S is the promise
that introducing it costs the archive nothing:

    a document carrying exactly ONE account publishes exactly today's payload —
    with no added key of any kind. The `document` + `accounts` shape requires
    more than one.

RULE S was a four-way conjunction (one account AND no omission AND no roll-up
AND no boundary mechanism) until the L1-S3 / L1-S2 composition; the composed
tree measured what that cost, and `analysis/serialization.py
::_publishes_todays_payload` carries the whole reasoning. These tests pin the
WRAPPER's own shape: what RULE S publishes, that a single-account document
publishes it WHATEVER document-level fact it carries, that the integrity block
keeps every flag it publishes today IN PUBLISHED ORDER, and the three things a
document object refuses to do even though nothing in production can ask it to
yet. The archive-scale proof of
RULE S is a byte comparison over the run of record (`tools/l1s1_seam_probe.py`);
what cannot be measured there is the behaviour of shapes production never
builds, and that is what is constructed here.

No value, name, number or date here comes from any document: the statement
below is synthetic and its calendar is the fixture calendar.
"""
from __future__ import annotations

import json
import re
from dataclasses import fields, replace
from pathlib import Path

import pytest

from analysis.parser_registry import Dispatch, Marker, Registration
from analysis.pipeline import (
    DOCUMENT_SCOPE_FLAGS,
    DocumentIntegrity,
    DocumentReport,
    Report,
    RollupOracle,
    SiblingOmission,
    analyze_document,
    analyze_markdown,
    split_integrity_flags,
)
from analysis.schema import Statement, Transaction
from analysis.serialization import document_report_to_dict, report_to_dict

MARKDOWN = """<!-- source: wrapper.pdf | pages: 1 | model: native -->

--- Page 1 ---
Beginning Balance 1,000.00
02/03 CARD PURCHASE 100.00 900.00
Ending Balance 900.00
"""


def _statement(*, name: str, opening: float, closing: float, amount: float) -> Statement:
    return Statement(
        bank="Wrapper Bank",
        account_name=name,
        period_start="2054-02-01",
        period_end="2054-02-28",
        beginning_balance=opening,
        ending_balance=closing,
        transactions=[
            Transaction(
                date="2054-02-03",
                description="CARD PURCHASE",
                amount=amount,
                direction="debit",
                running_balance=closing,
            )
        ],
    )


def _claimed(statement: Statement) -> Dispatch:
    """A claiming `Dispatch`, built directly so the live registry is untouched."""
    registration = Registration(
        id="wrapper_parser",
        bank=statement.bank or "Wrapper Bank",
        markers=(Marker("m", lambda text: True),),
        parse=lambda markdown: None,
    )
    return Dispatch("claimed", registration=registration, statement=statement)


def _report(monkeypatch, statement: Statement) -> Report:
    monkeypatch.setattr("analysis.pipeline.resolve", lambda markdown: _claimed(statement))
    return analyze_markdown(MARKDOWN, parse_mode="deterministic")


def _first_account(monkeypatch) -> Report:
    return _report(monkeypatch, _statement(
        name="OPERATING", opening=1000.0, closing=900.0, amount=-100.0))


def _second_account(monkeypatch) -> Report:
    return _report(monkeypatch, _statement(
        name="RESERVE", opening=4000.0, closing=3750.0, amount=-250.0))


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)


# ---------------------------------------------------------------------------
# RULE S
# ---------------------------------------------------------------------------


def test_rule_s_publishes_todays_payload_byte_for_byte(monkeypatch):
    """The whole stage, in one assertion."""
    account = _first_account(monkeypatch)
    document = DocumentReport(accounts=[account])
    assert canonical(document_report_to_dict(document)) == canonical(report_to_dict(account))


def test_rule_s_adds_no_key_of_any_kind(monkeypatch):
    """"No added key" is stronger than "the same values", and it is the promise
    that lets the analysis cache serve a single-account document without a
    version bump: an added key whose value is `[]` moves the payload BYTES
    while contributing no leaf to the projection the coverage cells report
    under, so the key set is asserted directly."""
    account = _first_account(monkeypatch)
    published = document_report_to_dict(DocumentReport(accounts=[account]))
    assert set(published) == set(report_to_dict(account))
    assert "document" not in published
    assert "accounts" not in published


@pytest.mark.parametrize("carries", [
    "omission",
    "rollup",
    "boundary_mechanism",
])
def test_a_single_account_document_keeps_todays_payload_and_adds_only_the_block(
    monkeypatch, carries
):
    """RULE S is the ACCOUNT COUNT, and this is the case that decided it.

    L1-S2 records `omissions` on the 15 protected carriers — every one a
    single-account document batch 8 validated. Under S1's four-way conjunction
    those 15 took the `document` + `accounts` shape at the production seams,
    and at the composed tree `python corpus_gate.py` died with
    `balance_forensic_audit.py::audit_source answers about one ACCOUNT and was
    handed a document carrying 1 of them`. The readers were right; the SHAPE
    was wrong, and L1-S3's closure-2 made the shape the account count alone.

    **L1-S4 closes the gap that left**, and this test is where the two halves
    are held apart. The shape is still the account count: no `accounts` list,
    `statement` still at the top level, so `is_document_payload` still answers
    False and every account-scope reader still answers this payload. What is
    added is the `document` BLOCK, and only for a document that established a
    document-level fact — because Q10 rules that a surfaced omission is
    surfaced, and a fact that reaches no payload reaches no package and no
    person.

    So: every key today's payload has, byte-identical, plus exactly one.
    """
    account = _first_account(monkeypatch)
    document = DocumentReport(accounts=[account])
    if carries == "omission":
        document.omissions = [SiblingOmission(
            label=None, reason="printed_dormancy_declaration", posting_count=0)]
    elif carries == "rollup":
        document.rollup = RollupOracle(
            caption_class="begin_end", column_roles_printed=True, rows=2,
            cross_account_total_printed=False)
    else:
        document.boundary_mechanism = "rollup-oracle"
    today = report_to_dict(account)
    published = document_report_to_dict(document)
    assert set(published) == set(today) | {"document"}
    assert "accounts" not in published
    assert "statement" in published
    # Every existing key is the one today's payload publishes, unchanged.
    for key, value in today.items():
        assert canonical(published[key]) == canonical(value), key
    assert published["document"]["account_count"] == 1


def test_a_single_account_document_that_established_nothing_publishes_todays_payload(
    monkeypatch,
):
    """The other side of the same clause, and the one that keeps the archive
    still: a document with no document-level fact to publish adds NO key. That
    is every document in the run of record but twenty-one."""
    account = _first_account(monkeypatch)
    published = document_report_to_dict(DocumentReport(accounts=[account]))
    assert published == report_to_dict(account)
    assert "document" not in published and "accounts" not in published


def test_the_document_shape_needs_more_than_one_account(monkeypatch):
    """The other direction of the same clause, so neither can move alone."""
    one = DocumentReport(accounts=[_first_account(monkeypatch)])
    two = DocumentReport(accounts=[_first_account(monkeypatch),
                                   _second_account(monkeypatch)])
    assert "accounts" not in document_report_to_dict(one)
    assert "accounts" in document_report_to_dict(two)


#: Where a SINGLE-account document carries each document-level fact. RULE S
#: publishes today's payload for it, so none of these is in that payload; each
#: entry says where the fact does live and who owns lighting it.
DOCUMENT_LEVEL_FIELDS = {
    "accounts": "not a document FACT — the accounts themselves; RULE S is its length",
    "document_period": "on the object; unset at this tree (analyze_document fills no document field)",
    "rollup": "on the object; the boundary layer that reads a roll-up is S4's",
    "omissions": "on the object, where L1-S2's protected-carrier pins read it; the "
                 "package surface publishes it for a MULTI-account payload only (Q10, dark)",
    "boundary_mechanism": "on the object; set by the boundary layer (L1-S4), and "
                          "left unset by every reader that establishes no printed partition",
    "internal_transfers": "on the object, and EMPTY on a single-account document by "
                          "construction — one ledger has no sibling for a counterpart "
                          "to be in, so there is nothing for RULE S to hide (L1-S4, R-d)",
    "integrity_notes": "on the object; today's only member is "
                       "`ambiguous_internal_transfer`, which needs two ledgers to be "
                       "reachable at all, so a single-account document carries none (L1-S4)",
    "account_roster": "in the `document` block beside a single published account (the other accounts the "
                      "document prints, idle or held), and in the multi-account block; empty from every "
                      "reader that does not judge accounts one by one, so their payloads are unchanged",
}


def test_every_document_level_field_is_declared_against_rule_s():
    """RULE S is the account count, so every OTHER document fact is invisible in
    a single-account payload — and that has to be a decision, not an accident.

    The failure this prevents is silent and total: a later stage adds a
    document-level field, populates it on a single-account document, and the
    payload says nothing about it. Pinning the field set with a declaration of
    where each fact lives turns "remember to decide" into a red test.
    """
    assert {f.name for f in fields(DocumentReport)} == set(DOCUMENT_LEVEL_FIELDS), (
        "DocumentReport gained or lost a field: declare in DOCUMENT_LEVEL_FIELDS "
        "where a SINGLE-account document carries it, given that RULE S publishes "
        "today's payload for it and this payload therefore cannot")


def test_a_document_carrying_two_accounts_takes_the_document_shape(monkeypatch):
    document = DocumentReport(accounts=[_first_account(monkeypatch),
                                        _second_account(monkeypatch)])
    published = document_report_to_dict(document)
    assert published["document"]["account_count"] == 2
    assert len(published["accounts"]) == 2


def test_the_document_shape_has_no_top_level_statement(monkeypatch):
    """A consumer that reads `payload["statement"]` on a two-account document
    reads ONE account and calls it the document — the defect this model exists
    to remove, moved out of the parser and into the payload. Its ABSENCE is
    what makes such a consumer stop instead of answering."""
    published = document_report_to_dict(DocumentReport(
        accounts=[_first_account(monkeypatch), _second_account(monkeypatch)]))
    assert "statement" not in published


def test_each_account_of_the_document_shape_is_todays_payload(monkeypatch):
    first, second = _first_account(monkeypatch), _second_account(monkeypatch)
    published = document_report_to_dict(DocumentReport(accounts=[first, second]))
    assert canonical(published["accounts"][0]) == canonical(report_to_dict(first))
    assert canonical(published["accounts"][1]) == canonical(report_to_dict(second))


def test_accounts_are_published_in_printed_order_and_never_sorted(monkeypatch):
    """Printed order is printed evidence about a SEQUENCE. It is not evidence
    that the first element stands for the document, and it is not a key."""
    first, second = _first_account(monkeypatch), _second_account(monkeypatch)
    forwards = document_report_to_dict(DocumentReport(accounts=[first, second]))
    backwards = document_report_to_dict(DocumentReport(accounts=[second, first]))
    assert forwards["accounts"][0] == backwards["accounts"][1]
    assert forwards["accounts"][1] == backwards["accounts"][0]


# ---------------------------------------------------------------------------
# the integrity scope split
# ---------------------------------------------------------------------------

#: An integrity block carrying flags of BOTH scopes, account-scope FIRST. The
#: run of record's 232-document cohort contains no document ordered this way,
#: which is exactly why this is a constructed fixture: the order is pinned by
#: `corpus_gate.py` ("Published ORDER, not sorted"), so the assembly must be
#: right because the rule says so, not because a cohort happened to catch it.
INTERLEAVED_FLAGS = [
    "ledger_sum_mismatch",
    "parser_ambiguous",
    "running_balance_breaks",
    "missing_declared_statement_page",
    "credit_detail_coverage_mismatch",
]


def _with_flags(account: Report, flags: list[str]) -> Report:
    return replace(account, integrity=DocumentIntegrity(
        risk_level="review", flags=list(flags), notes=[],
        possible_document_issue=False))


def test_split_integrity_flags_partitions_without_reordering():
    document, account = split_integrity_flags(INTERLEAVED_FLAGS)
    assert document == ["parser_ambiguous", "missing_declared_statement_page"]
    assert account == ["ledger_sum_mismatch", "running_balance_breaks",
                       "credit_detail_coverage_mismatch"]
    # Each half is a SUBSEQUENCE of the input, and the two halves partition it.
    assert sorted(document + account) == sorted(INTERLEAVED_FLAGS)
    carried = set(document) | set(account)
    assert [f for f in INTERLEAVED_FLAGS if f in carried] == INTERLEAVED_FLAGS
    # And the concatenation is NOT the published list, which is the whole
    # reason this function returns a partition rather than an assembly.
    assert document + account != INTERLEAVED_FLAGS


def test_the_published_account_block_keeps_every_flag_in_published_order(monkeypatch):
    """The row S1 has to PROVE rather than assume. Two mutants die here: the
    document-scope flags LEAVING the account block (the design's prose read
    literally, which moves 3 of the run of record's 232-document cohort and
    their ladder outcome with them), and the two scopes CONCATENATED (identical
    as a set, different as the list the corpus gate pins)."""
    account = _with_flags(_first_account(monkeypatch), INTERLEAVED_FLAGS)
    published = document_report_to_dict(DocumentReport(accounts=[account]))
    assert published["integrity"]["flags"] == INTERLEAVED_FLAGS


def test_the_document_scope_view_is_additive_never_subtractive(monkeypatch):
    account = _with_flags(_first_account(monkeypatch), INTERLEAVED_FLAGS)
    document = DocumentReport(accounts=[account])
    assert document.document_scope_flags() == [
        "parser_ambiguous", "missing_declared_statement_page"]
    # Reading the document's view removed nothing from the account's own block.
    assert account.integrity.flags == INTERLEAVED_FLAGS
    assert document_report_to_dict(document)["integrity"]["flags"] == INTERLEAVED_FLAGS


def test_the_document_scope_view_de_duplicates_across_accounts(monkeypatch):
    """A document fact is carried ONCE however many accounts publish it."""
    first = _with_flags(_first_account(monkeypatch), ["parser_ambiguous"])
    second = _with_flags(_second_account(monkeypatch),
                         ["parser_ambiguous", "repair_exception"])
    document = DocumentReport(accounts=[first, second])
    assert document.document_scope_flags() == ["parser_ambiguous", "repair_exception"]


def test_the_document_scope_flag_set_is_pinned_exactly():
    """The membership PREDICATE is not the SET, and only the set is the rule.

    Everything else about this table is checked by a property that an ADDED
    flag still satisfies: the partition still partitions, the account block
    still keeps every flag in published order, and the source guard below still
    reads `subset of what the pipeline raises`. And no comparison at any scale
    can see the addition, because the split publishes no byte at this stage —
    which is exactly the window in which it is cheap to get wrong.

    What it would cost is paid later and elsewhere: from the stage that teaches
    readers to consume `document_scope_flags()`, an account-scope flag in this
    set promotes ONE account's ledger failure to a fact about the whole PDF, on
    a document where "which account failed" is the question. Seven of the
    fifteen flags the pipeline raises are account-scope and could be added
    undetected, so the set is pinned by equality — the same treatment the
    document object's field list gets, for the same reason.
    """
    assert DOCUMENT_SCOPE_FLAGS == {
        "parser_ambiguous",
        "parser_exception",
        "repair_exception",
        "integrity_check_exception",
        "missing_declared_statement_page",
    }, ("the document-scope set changed. A flag belongs here only if it is a "
        "fact about the PDF rather than about one account's ledger; if a new "
        "pipeline flag really is one, add it here AND to this assertion, and "
        "say in the message why the document rather than the account owns it")


def test_every_document_scope_flag_is_one_the_pipeline_actually_raises():
    """A scope table naming a flag no code path produces is a table about
    nothing — and it fails SILENTLY, by classifying every real flag as
    account-scope. The membership is checked against the source that raises
    them rather than against a second copy of the list."""
    source = (Path(__file__).resolve().parents[1] / "analysis" / "pipeline.py").read_text(
        encoding="utf-8")
    raised = set(re.findall(r'flags\.append\("([a-z_]+)"\)', source))
    assert DOCUMENT_SCOPE_FLAGS <= raised
    assert DOCUMENT_SCOPE_FLAGS != raised, (
        "every flag being document-scope would empty the account block")


# ---------------------------------------------------------------------------
# what the wrapper refuses — the three fail-closed fixtures this stage owes
# ---------------------------------------------------------------------------


def test_a_document_publishing_no_account_is_refused(monkeypatch):
    """An empty `accounts` is a publisher defect, not a document with nothing
    to say. Publishing it would put an empty container in front of readers that
    ANSWER about it rather than refuse — the measured failure of the untaught
    shape is quiet, not loud, so the refusal is made here where it is loud."""
    with pytest.raises(ValueError) as excinfo:
        document_report_to_dict(DocumentReport(accounts=[]))
    assert "document_publishes_no_account" in str(excinfo.value)


def test_two_accounts_publishing_identical_content_are_refused(monkeypatch):
    """The arithmetic property, not tidiness: a section published twice is
    counted twice by every cross-account total, average and count a package
    computes, and no reader downstream can tell it from a member with two
    accounts. Refused by CONTENT — a duplicate is a duplicate whatever identity
    token the paper printed over it."""
    account = _first_account(monkeypatch)
    with pytest.raises(ValueError) as excinfo:
        document_report_to_dict(DocumentReport(accounts=[account, account]))
    assert "document_publishes_duplicate_account" in str(excinfo.value)


def test_two_accounts_that_differ_are_not_refused(monkeypatch):
    """The other half of the same gate: the refusal is about duplication, and a
    gate that refused every two-account document would satisfy the test above
    while making the model useless."""
    published = document_report_to_dict(DocumentReport(
        accounts=[_first_account(monkeypatch), _second_account(monkeypatch)]))
    assert published["document"]["account_count"] == 2


def test_a_per_document_field_is_left_empty_and_account_count_carries_the_fact(monkeypatch):
    """No per-document field is ever filled from a chosen account — not by a
    derived quantity and not by printed position. A surface that needs one
    value per document gets `account_count` and an empty field."""
    first, second = _first_account(monkeypatch), _second_account(monkeypatch)
    published = document_report_to_dict(DocumentReport(accounts=[first, second]))
    block = published["document"]
    assert block["period_start"] is None
    assert block["period_end"] is None
    assert block["boundary_mechanism"] is None
    assert block["rollup"] is None
    assert block["omitted_sections"] == []
    assert block["account_count"] == 2
    # And nothing an account holds leaked into the document block: the accounts
    # DO carry a period, and the document block carries none of it.
    assert first.statement.period_start is not None
    assert canonical(block).find(first.statement.period_start) == -1
    assert canonical(block).find(first.statement.account_name or "") == -1


def test_the_document_block_carries_exactly_the_documents_own_facts(monkeypatch):
    """The block's key set is pinned: a per-document field added later is a
    decision, not a side effect of a reader needing somewhere to put a value."""
    published = document_report_to_dict(DocumentReport(
        accounts=[_first_account(monkeypatch), _second_account(monkeypatch)]))
    assert set(published["document"]) == {
        "period_start", "period_end", "boundary_mechanism", "account_count",
        "rollup", "omitted_sections", "internal_transfers", "integrity_notes",
    }


def test_an_omission_and_a_rollup_are_published_as_evidence(monkeypatch):
    document = DocumentReport(
        accounts=[_first_account(monkeypatch), _second_account(monkeypatch)],
        rollup=RollupOracle(caption_class="type_begin_end", column_roles_printed=True,
                            rows=3, cross_account_total_printed=True),
        omissions=[SiblingOmission(label=None, reason="printed_zero_activity_summary",
                                   posting_count=0)],
        boundary_mechanism="rollup-oracle",
    )
    block = document_report_to_dict(document)["document"]
    assert block["rollup"] == {
        "caption_class": "type_begin_end", "column_roles_printed": True,
        "rows": 3, "cross_account_total_printed": True,
    }
    assert block["omitted_sections"] == [
        {"label": None, "reason": "printed_zero_activity_summary", "posting_count": 0}]


# ---------------------------------------------------------------------------
# the pipeline seam
# ---------------------------------------------------------------------------


def test_analyze_document_publishes_one_account_and_nothing_else(monkeypatch):
    monkeypatch.setattr("analysis.pipeline.resolve", lambda markdown: _claimed(
        _statement(name="OPERATING", opening=1000.0, closing=900.0, amount=-100.0)))
    document = analyze_document(MARKDOWN, parse_mode="deterministic")
    assert isinstance(document, DocumentReport)
    assert len(document.accounts) == 1


def test_analyze_document_fills_no_document_level_field(monkeypatch):
    """The account carries a period; the DOCUMENT does not. A per-document fact
    taken from the single account is a fact this stage did not read, and it is
    the first thing a reader reaches for when the account list has length one.
    This is the killer of the "leak an account value into a document field"
    mutant at the seam that builds the object."""
    monkeypatch.setattr("analysis.pipeline.resolve", lambda markdown: _claimed(
        _statement(name="OPERATING", opening=1000.0, closing=900.0, amount=-100.0)))
    document = analyze_document(MARKDOWN, parse_mode="deterministic")
    assert document.accounts[0].statement.period_start is not None
    assert document.document_period is None
    assert document.rollup is None
    assert document.omissions == []
    assert document.boundary_mechanism is None


def test_the_seam_publishes_exactly_what_the_account_seam_publishes(monkeypatch):
    """The pipeline-seam form of RULE S: the same text, analysed through the
    document entry point and through today's, publishes the same bytes."""
    statement = _statement(name="OPERATING", opening=1000.0, closing=900.0, amount=-100.0)
    monkeypatch.setattr("analysis.pipeline.resolve", lambda markdown: _claimed(statement))
    through_document = document_report_to_dict(
        analyze_document(MARKDOWN, parse_mode="deterministic"))
    through_account = report_to_dict(
        analyze_markdown(MARKDOWN, parse_mode="deterministic"))
    assert canonical(through_document) == canonical(through_account)


def test_analyze_markdown_still_returns_one_report(monkeypatch):
    """The account entry point is unchanged and every existing caller keeps
    reaching it: nothing in this stage moves a seam."""
    report = _first_account(monkeypatch)
    assert isinstance(report, Report)
    assert not isinstance(report, DocumentReport)

"""The sibling omission (L-1 stage 2): evidence, not absence.

Gustavo's checkpoint condition is that an idle sibling is admitted ONLY when
explicit statement structure establishes the sibling AND its empty/silent
state, and that absence of parsed activity alone is insufficient. These tests
pin that as a property of the three readers that used to decide it on absence,
and of the vocabulary they decide it with:

* the classifier answers each of L1-C17's classes and REFUSES the shapes that
  only look like one — a summary that printed activity, a pair that does not
  coincide, a grid missing a row;
* the vocabulary is closed at the point the record is BUILT, so a reason an
  implementer invented cannot reach a payload;
* each of the three sites admits its section on printed evidence and RECORDS
  it, and refuses the DOCUMENT when the same section prints none;
* the record lands on the document object and never on `Statement`, and the
  account block a document with an omission publishes is byte-identical to the
  one it published before (RULE S's second clause, made visible).

Every fixture is synthetic. The three parser fixtures are the committed
layout suites' own — invented names, invented figures, the fixture calendar —
reused so that what these tests exercise is the reader on the shape the layout
tests already pin, with the declaration present and then removed.
"""
from __future__ import annotations

import json

import pytest

from analysis.community_section import (
    _parse_sectioned_statement,
    parse_community_section_statement,
    parse_dakota_west_statement,
)
from analysis.pipeline import analyze_document, analyze_markdown
from analysis.serialization import document_report_to_dict, report_to_dict
from analysis.sibling_omission import (
    EVIDENCE_CLASSES,
    PRINTED_DORMANCY_DECLARATION,
    PRINTED_ZERO_ACTIVITY_SUMMARY,
    YIELD_ONLY_ARITHMETIC,
    SectionLedger,
    SiblingOmission,
    collecting,
    evidence_class,
    publish_omissions,
)
from analysis.symitar import parse_symitar_statement
from analysis.zions import parse_zions_statement
from tests.test_community_section_layouts import PLATFORM_HEAD, SIMPLE_BODY
from tests.test_symitar import ACTIVE as SYM_ACTIVE
from tests.test_symitar import DORMANT as SYM_DORMANT
from tests.test_symitar import GRID as SYM_GRID
from tests.test_symitar import HEAD as SYM_HEAD
from tests.test_symitar import DIVIDEND_ONLY as SYM_DIVIDEND_ONLY
from tests.test_zions_layouts import _INERT_SAVINGS, _document as zions_document


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)


# ===========================================================================
# L1-C17 — the classifier, and the shapes it must refuse
# ===========================================================================
#
# The nine cases below are the re-review's constructed fixture set, carried
# over as the seed the card asked for: invented figures, the committed
# patterns' own wordings, nothing from the archive. Five of the nine are
# REFUSALS, which is what makes the measured `no_printed_evidence = 0` a
# finding rather than a vacuous zero — the class the condition refuses is
# reachable, and a section that printed activity does not reach an admitting
# one.

A_ZERO_SUMMARY = dict(
    opening=1234.56, closing=1234.56,
    credit_total=0.0, debit_total=0.0,
    credit_count="0", debit_count="0",
)


def test_a_heading_and_nothing_else_is_no_printed_evidence():
    assert evidence_class(text="Money Market Savings") is None


def test_an_empty_grid_header_with_no_summary_is_no_printed_evidence():
    assert evidence_class(text="Date Description Amount Balance") is None


def test_the_first_ratified_declaration_wording_is_the_declaration_class():
    assert evidence_class(text="No Transactions This Period") == PRINTED_DORMANCY_DECLARATION


def test_the_second_ratified_declaration_wording_is_the_same_class():
    """Two issuers, two sentences, ONE fact. A class keyed on one issuer's
    phrasing would be a per-issuer vocabulary (R-1), so the wordings are a
    tuple and the class is what they both mean."""
    assert evidence_class(
        text="There were no transactions this period."
    ) == PRINTED_DORMANCY_DECLARATION


def test_all_six_clauses_of_the_zero_activity_summary_admit_the_section():
    assert evidence_class(**A_ZERO_SUMMARY) == PRINTED_ZERO_ACTIVITY_SUMMARY


def test_a_summary_that_printed_activity_is_refused():
    """One credit. The section is not silent, and nothing here may say it was."""
    assert evidence_class(**{**A_ZERO_SUMMARY,
                            "credit_total": 25.00, "credit_count": "1"}) is None


def test_a_summary_whose_pair_does_not_coincide_is_refused():
    """The balances moved, so something posted that this reader did not read."""
    assert evidence_class(**{**A_ZERO_SUMMARY, "closing": 1230.00}) is None


def test_a_zero_pair_with_a_non_zero_debit_total_is_refused():
    """Coinciding balances are not enough on their own: a section can print a
    debit and a credit that cancel."""
    assert evidence_class(**{**A_ZERO_SUMMARY, "debit_total": 40.00}) is None


def test_a_summary_missing_its_second_balance_row_is_refused():
    """Read fail-closed: a grid missing either balance yields nothing rather
    than a partial answer."""
    assert evidence_class(**{**A_ZERO_SUMMARY, "closing": None}) is None


def test_a_zero_amount_beside_a_non_zero_printed_count_is_refused():
    """The clause `zions._inert` does not read. A grid stating instances beside
    a zero amount is a block the reader has NOT accounted for."""
    assert evidence_class(**{**A_ZERO_SUMMARY, "credit_count": "2"}) is None


def test_an_unreadable_count_is_absence_and_not_a_zero():
    assert evidence_class(**{**A_ZERO_SUMMARY, "debit_count": "--"}) is None


def test_a_declaration_outranks_a_summary_it_disagrees_with():
    """Order is not cosmetic: the declaration is the paper's own statement
    about the section, and it is read before the grid arithmetic."""
    assert evidence_class(
        text="No Transactions This Period",
        **{**A_ZERO_SUMMARY, "credit_total": 25.00},
    ) == PRINTED_DORMANCY_DECLARATION


# ===========================================================================
# L1-C17 — the vocabulary is closed against ABSENCE
# ===========================================================================


def test_the_vocabulary_is_exactly_the_designs_three_reachable_members():
    assert EVIDENCE_CLASSES == {
        PRINTED_DORMANCY_DECLARATION,
        PRINTED_ZERO_ACTIVITY_SUMMARY,
        YIELD_ONLY_ARITHMETIC,
    }


def test_absence_of_parsed_rows_is_not_a_reason_and_cannot_be_recorded():
    """The class this whole module exists to refuse. It is checked where the
    record is BUILT, so no call site can invent its way past the vocabulary."""
    with pytest.raises(ValueError):
        SiblingOmission(label=None, reason="absence_of_parsed_rows", posting_count=0)


def test_a_ratified_reason_is_accepted():
    record = SiblingOmission(label="SAVINGS", reason=PRINTED_ZERO_ACTIVITY_SUMMARY,
                             posting_count=0)
    assert record.reason in EVIDENCE_CLASSES


def test_a_ledger_records_a_refusal_when_no_class_admits_the_section():
    ledger = SectionLedger()
    assert ledger.record("SAVINGS", None) is False
    assert ledger.refused == 1
    assert ledger.omissions == []


# ===========================================================================
# the seam — the record reaches a DOCUMENT, and only when one is collecting
# ===========================================================================


def test_nothing_is_collected_outside_a_collecting_block():
    """The account entry point opens no collector, and a reader that publishes
    into no document may not raise or leak."""
    publish_omissions([SiblingOmission(None, PRINTED_ZERO_ACTIVITY_SUMMARY, 0)])


def test_a_collecting_block_receives_what_a_reader_publishes():
    with collecting() as sink:
        publish_omissions([SiblingOmission("SAVINGS", PRINTED_ZERO_ACTIVITY_SUMMARY, 0)])
    assert [record.reason for record in sink] == [PRINTED_ZERO_ACTIVITY_SUMMARY]


def test_the_collector_is_reset_when_the_block_ends():
    with collecting():
        pass
    publish_omissions([SiblingOmission(None, PRINTED_ZERO_ACTIVITY_SUMMARY, 0)])
    with collecting() as sink:
        pass
    assert sink == []


# ===========================================================================
# symitar — the dormant sibling, and the same sibling with nothing printed
# ===========================================================================

#: The same share account, with the platform's declaration removed and nothing
#: put in its place: a heading, a grid, an opening and a closing, no row and no
#: statement about the section's state. This is the ABSENCE-ONLY shape, and the
#: killer of any mutant that restores the absence skip.
SYM_DORMANT_SILENT = SYM_DORMANT.replace("No Transactions This Period ", "")


def test_the_absence_only_fixture_really_is_the_dormant_one_minus_its_declaration():
    """A fixture that differs in more than the declaration would not isolate
    the thing under test."""
    assert SYM_DORMANT_SILENT != SYM_DORMANT
    assert SYM_DORMANT_SILENT + "No Transactions This Period " != SYM_DORMANT
    assert "No Transactions This Period" not in SYM_DORMANT_SILENT
    assert len(SYM_DORMANT) - len(SYM_DORMANT_SILENT) == len("No Transactions This Period ")


def test_a_declared_dormant_sibling_is_published_and_recorded():
    with collecting() as sink:
        stmt = parse_symitar_statement(SYM_HEAD + SYM_ACTIVE + SYM_DORMANT)
    assert stmt is not None
    assert [(record.reason, record.posting_count) for record in sink] == [
        (PRINTED_DORMANCY_DECLARATION, 0)]


def test_a_sibling_that_prints_no_row_and_declares_nothing_refuses_the_document():
    """Fail closed. The document is not published from the one account this
    reader could read: a statement one of whose accounts it cannot account for
    is not a statement it has read."""
    with collecting() as sink:
        assert parse_symitar_statement(SYM_HEAD + SYM_ACTIVE + SYM_DORMANT_SILENT) is None
    assert sink == []


def test_the_yield_only_sibling_is_recorded_under_its_own_ratified_class():
    """The second skip in the same file was never absence-based — it rests on
    the platform's own arithmetic — but it was silent. It is not any more."""
    with collecting() as sink:
        stmt = parse_symitar_statement(SYM_HEAD + SYM_ACTIVE + SYM_DIVIDEND_ONLY)
    assert stmt is not None
    assert [(record.reason, record.posting_count) for record in sink] == [
        (YIELD_ONLY_ARITHMETIC, 1)]


def test_the_symitar_layout_cannot_reach_the_zero_summary_class():
    """This issue prints no instance counts, so the six-clause class refuses
    rather than falling through on a partial reading — which is what keeps the
    silent sibling above refused instead of admitted by arithmetic."""
    with collecting() as sink:
        assert parse_symitar_statement(SYM_HEAD + SYM_ACTIVE + SYM_DORMANT_SILENT) is None
    assert sink == []


# ===========================================================================
# community_section — the block whose summary states its own empty state
# ===========================================================================

#: A second printed account block whose summary grid states its own opening,
#: a closing coinciding with it, zero totals and zero counts, and prints no
#: transaction section at all.
IDLE_BODY = (
    "Business Savings - XXXXXX5678\n"
    "Account Summary Date Description Amount 01/01/2054 Beginning Balance $50.00"
    " 0 Credit(s) This Period $0.00 0 Debit(s) This Period $0.00"
    " 01/30/2054 Ending Balance $50.00\n"
)

#: The same block with its summary stating ACTIVITY it printed no row for.
#: Absence-only in the sense that matters: nothing printed says this account
#: was idle, and the grid says the opposite.
BUSY_BUT_EMPTY_BODY = (
    "Business Savings - XXXXXX5678\n"
    "Account Summary Date Description Amount 01/01/2054 Beginning Balance $50.00"
    " 1 Credit(s) This Period $20.00 0 Debit(s) This Period $0.00"
    " 01/30/2054 Ending Balance $70.00\n"
)

PLATFORM_MULTI_HEAD = (
    "Statement Ending 01/30/2054\n"
    "Online Access www.examplecommunitybank.com\n"
    "Summary of Accounts\n"
    "Account Type Account Number Ending Balance Business Checking XXXXXX1234 $105.00\n"
)


def test_a_block_whose_summary_states_its_own_empty_state_is_recorded():
    with collecting() as sink:
        stmt = parse_community_section_statement(
            PLATFORM_MULTI_HEAD + SIMPLE_BODY + IDLE_BODY)
    assert stmt is not None
    assert stmt.account_name == "Business Checking"
    assert [(record.reason, record.posting_count) for record in sink] == [
        (PRINTED_ZERO_ACTIVITY_SUMMARY, 0)]


def test_a_block_whose_summary_states_activity_it_printed_no_row_for_refuses():
    with collecting() as sink:
        assert parse_community_section_statement(
            PLATFORM_MULTI_HEAD + SIMPLE_BODY + BUSY_BUT_EMPTY_BODY) is None
    assert sink == []


#: This issue prints its account headings with the account number in digits, so
#: its own two blocks are written out rather than reusing the platform's.
DW_HEAD = (
    "Thank you for being a member of Dakota West Credit Union.\n"
    "Website dakotawestcu.com\n"
)
DW_ACTIVE_BODY = (
    "Small Business Checking - 35127380\n"
    "Account Summary Date Description Amount 11/01/2053 Beginning Balance $100.00"
    " 1 Credit(s) This Period $500.00 1 Debit(s) This Period $25.00"
    " 11/30/2053 Ending Balance $575.00\n"
    "Electronic Credits Date Description Amount 11/04/2053 EXTERNAL DEPOSIT ACH $500.00\n"
    "Other Debits Date Description Amount 11/05/2053 POS PURCHASE $25.00\n"
)
DW_IDLE_BODY = (
    "Badlands Savings - 35127372\n"
    "Account Summary Date Description Amount 11/01/2053 Beginning Balance $10.00"
    " 0 Credit(s) This Period $0.00 0 Debit(s) This Period $0.00"
    " 11/30/2053 Ending Balance $10.00\n"
)
DW_BUSY_BUT_EMPTY_BODY = DW_IDLE_BODY.replace(
    "0 Credit(s) This Period $0.00", "1 Credit(s) This Period $5.00").replace(
    "11/30/2053 Ending Balance $10.00", "11/30/2053 Ending Balance $15.00")


def test_dakota_west_records_the_same_class_through_its_own_entry_point():
    """Three entry points share one callee, so the ledger travels with the
    call rather than living in the callee."""
    with collecting() as sink:
        stmt = parse_dakota_west_statement(DW_HEAD + DW_ACTIVE_BODY + DW_IDLE_BODY)
    assert stmt is not None
    assert stmt.account_name == "Small Business Checking"
    assert [record.reason for record in sink] == [PRINTED_ZERO_ACTIVITY_SUMMARY]


def test_dakota_west_refuses_when_a_printed_heading_declares_nothing():
    with collecting() as sink:
        assert parse_dakota_west_statement(
            DW_HEAD + DW_ACTIVE_BODY + DW_BUSY_BUT_EMPTY_BODY) is None
    assert sink == []


def test_the_shared_callee_will_not_run_without_a_ledger():
    """The argument is required and has no default on purpose: this callee is
    where the distinction between an admitted omission and an absence-drop
    lives, and a caller allowed to omit the argument would be allowed to lose
    it silently."""
    with pytest.raises(TypeError):
        _parse_sectioned_statement(  # type: ignore[call-arg]
            PLATFORM_HEAD + SIMPLE_BODY, bank=None, account_name="Business Checking")


# ===========================================================================
# zions — the inert block, named rather than newly gated
# ===========================================================================


def _zions(extra_block: str) -> str:
    return zions_document(
        summary_title="SUMMARY OF ACCOUNT BALANCES",
        summary_table=(
            "Account Type Account Number Account Ending Balance "
            "BUSINESS GROWTH CHECKING 1234567890 $1,200.00 "
            "BUSINESS SAVINGS 5795685527 $0.00 Total $1,200.00"
        ),
        extra_block=extra_block,
    )


#: The inert block with its declaration removed from both posting sections and
#: a non-zero instance count printed beside its zero amounts — the two ways
#: this layout can print a block that `_inert` accepts and L1-C17 does not.
ZIONS_SILENT = _INERT_SAVINGS.replace("There were no transactions this period.", "")
ZIONS_COUNTED = ZIONS_SILENT.replace(
    "Count:                     0                       0",
    "Count:                     2                       0")


def test_a_declared_inert_block_is_published_and_recorded():
    with collecting() as sink:
        stmt = parse_zions_statement(_zions(_INERT_SAVINGS))
    assert stmt is not None
    assert stmt.account_number == "1234567890"
    assert [record.reason for record in sink] == [PRINTED_DORMANCY_DECLARATION]


def test_an_inert_block_printing_zero_columns_and_zero_counts_is_the_summary_class():
    """`_inert` was never absence-based: it needs every printed summary amount
    to be zero. What it lacked was a NAME, and the name is the class the
    evidence belongs to rather than a token of this reader's own."""
    with collecting() as sink:
        stmt = parse_zions_statement(_zions(ZIONS_SILENT))
    assert stmt is not None
    assert [record.reason for record in sink] == [PRINTED_ZERO_ACTIVITY_SUMMARY]


def test_an_inert_block_stating_instances_it_printed_no_row_for_refuses():
    """The clause `_inert` does not read, and the only place this card
    tightened a reader rather than naming what it already required."""
    with collecting() as sink:
        assert parse_zions_statement(_zions(ZIONS_COUNTED)) is None
    assert sink == []


# ===========================================================================
# RULE S — where the record goes, and what it costs the account block
# ===========================================================================


def test_the_document_carrying_an_omission_publishes_the_same_account_block():
    """The second clause of RULE S, made visible. A document that omitted a
    sibling no longer publishes today's payload — it publishes the document
    shape — and what it adds is EXACTLY the gap: the account block inside it is
    byte-identical to the one the account seam publishes for the same text."""
    text = SYM_HEAD + SYM_ACTIVE + SYM_DORMANT
    document = analyze_document(text, parse_mode="deterministic")
    published = document_report_to_dict(document)
    assert canonical(published["accounts"][0]) == canonical(
        report_to_dict(analyze_markdown(text, parse_mode="deterministic")))


def test_the_omission_is_the_only_document_level_fact_the_stage_fills():
    text = SYM_HEAD + SYM_ACTIVE + SYM_DORMANT
    block = document_report_to_dict(
        analyze_document(text, parse_mode="deterministic"))["document"]
    assert block["omitted_sections"] == [
        {"label": "Money Market", "reason": PRINTED_DORMANCY_DECLARATION,
         "posting_count": 0}]
    assert block["account_count"] == 1
    assert block["period_start"] is None
    assert block["period_end"] is None
    assert block["boundary_mechanism"] is None
    assert block["rollup"] is None


def test_the_record_never_reaches_the_statement():
    """`Statement` is ONE ACCOUNT's, and RULE S rests on it staying so. A
    document-level fact written onto it would move every single-account payload
    in the archive, which is the mutant this pins."""
    text = SYM_HEAD + SYM_ACTIVE + SYM_DORMANT
    document = analyze_document(text, parse_mode="deterministic")
    statement = document.accounts[0].statement
    assert not [name for name in statement.model_dump() if "omi" in name.lower()]
    assert PRINTED_DORMANCY_DECLARATION not in canonical(
        report_to_dict(document.accounts[0]))


def test_the_account_seam_publishes_todays_payload_for_a_document_with_an_omission():
    """The seam production still uses. Nothing this card records changes what a
    caller of the account entry point is handed."""
    text = SYM_HEAD + SYM_ACTIVE + SYM_DORMANT
    payload = report_to_dict(analyze_markdown(text, parse_mode="deterministic"))
    assert "document" not in payload
    assert "omitted_sections" not in canonical(payload)


def test_a_document_that_omitted_nothing_still_publishes_todays_payload():
    """RULE S itself, unweakened: the clause added here fires only on a
    document that actually carries a gap."""
    text = SYM_HEAD + SYM_ACTIVE
    document = analyze_document(text, parse_mode="deterministic")
    assert document.omissions == []
    assert canonical(document_report_to_dict(document)) == canonical(
        report_to_dict(analyze_markdown(text, parse_mode="deterministic")))

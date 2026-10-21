"""W3 §GLANCE — the signed category partition, and the grid it refuses to read.

**Every document in this module is INVENTED.** No name, account number, date,
balance or amount here is copied from any archive statement, and that is a
measurement rather than an intention: every money figure, date token, digit run
and masked account form the family's eight documents print was extracted and
grepped against this branch's whole diff, and the count is zero. The eight are
named by `content_sha256` in the branch log and in the commit message and are
reproduced nowhere.

The category LABELS here are invented too, and deliberately so. The reader
memorises no category name — it reads each category's direction off the
trailing plus the platform prints on the amount — so a fixture whose categories
are called `Alpha Credits` and `Beta Debits` tests the rule, while one reusing
the platform's own names would let a memorised list pass unnoticed.

The module carries the card's MUTATION TABLE (`MUTANTS` below). Each row names
a gate, transforms the document as the row's description says, and asserts the
outcome. Two properties are asserted about the table itself rather than
assumed: every mutant must actually CHANGE the document it is applied to (a
mutant that edits nothing pins nothing — the batch-7 lesson), and every mutated
tree must be distinct from every other (a duplicated row is a gate reported as
covered twice and tested once).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest

from analysis import category_partition as cp
from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401 — populates the registry
from analysis.adb import compute_average_daily_balance
from analysis.count_semantics import counts_comparable

# ---------------------------------------------------------------------------
# One document of each printed issue, in the pieces a test can vary
# ---------------------------------------------------------------------------

U_MASTHEAD = (
    "INVENTED ISSUER ONE PO BOX 7 EXAMPLETOWN, EXAMPLE  91742 "
    "Tel: (432) 555-0173\n"
    "HOLDER ALPHA 7 EXAMPLE ROAD EXAMPLETOWN EX 91742-0173\n"
    "Statement Date: 09/30/2031 Account No.: XX9174 Page: 1\n"
)
U_GLANCE = (
    "ACCOUNTS AT A GLANCE Account No. Sub Acct. Account Title Acct Type "
    "Balance XX9174 Invented Alpha Account Deposit 58,997.63\n"
    "Your Total Deposits = 58,997.63 And Your Total Loans = 6.02\n"
)
U_SUMMARY = (
    "Invented Alpha Account SUMMARY Type :     REG    Status :    Active\n"
    "Category Number Amount Balance Forward From 08/29/31 41,003.77 "
    "Alpha Credits 1 62,005.11+ Beta Debits 1 33,001.13 "
    "Gamma Debits 1 11,002.29 Zeta Charge 7.83 "
    "Ending Balance On 09/30/31 58,997.63\n"
)
U_LEDGER = (
    "STATEMENT PERIOD ACTIVITY\n"
    "Date Check/Description Amount Balance "
    "09/01/31 EXAMPLE ROW ALPHA 62,005.11+ 103,008.88 "
    "09/02/31 EXAMPLE ROW BETA 33,001.13 70,007.75\n"
    "Continued 21/1997/1\n"
    "Statement Date: 09/30/2031 Account No.: XX9174 Page: 2 "
    "STATEMENT PERIOD ACTIVITY (cont.)\n"
    "Date Check/Description Amount Balance "
    "09/03/31 EXAMPLE ROW GAMMA 11,002.29 59,005.46 "
    "09/30/31 EXAMPLE ROW DELTA 7.83 58,997.63\n"
)
U_CHECK_RECAP = (
    "CHECKS AND OTHER DEBITS * indicates a gap in the check numbers\n"
    "Date Check # Amount 09/02/31 4417 33,001.13\n"
)
U_ITEMIZED = (
    "ITEMIZED SERVICE CHARGE\n"
    "Date Description Status Amount\n"
    "09/30/31 EXAMPLE CHARGE ALPHA 7.83 TOTAL SERVICE CHARGE : 7.83\n"
)
U_GRID = (
    "DAILY BALANCE SUMMARY Beginning Ledger Balance on 08/29/31 was 41,003.77 "
    "Date Balance Date Balance Date Balance "
    "09/01/31 103,008.88 09/02/31 70,007.75 09/03/31 59,005.46 "
    "09/30/31 58,997.63\n"
    "This Statement Cycle Reflects 32 Days\n"
)
U_IMAGES = (
    "HOLDER ALPHA Account No. : XX9174 Stmt. Date : 09/30/2031\n"
    "IMAGE STATEMENT\n"
    "AM: 33,001.13 CK: 4417 DT: 09/02 SQ: 61743072 Paid\n"
    "End Statement 21/1997/3E\n"
)


def unified(*, masthead=U_MASTHEAD, glance=U_GLANCE, summary=U_SUMMARY,
            ledger=U_LEDGER, recap=U_CHECK_RECAP, itemized=U_ITEMIZED,
            grid=U_GRID, images=U_IMAGES) -> str:
    """The UNIFIED issue: one running-balance table, a cheque recap that
    restates rows the table already carries, and a ledger daily grid."""
    return masthead + glance + summary + ledger + recap + itemized + grid + images


S_MASTHEAD = (
    "Contact Us\n"
    "Branch Name Example Branch\n"
    "Online Access WWW.EXAMPLE.INVALID\n"
    "Statement Date: 09/30/2031 Account No.: 9174063 Page: 1\n"
)
S_GLANCE = (
    "ACCOUNTS AT A GLANCE\n"
    "Account No. Sub Acct. Account Title Acct Type Balance "
    "9174063 INVENTED BETA ACCOUNT Deposit 58,997.63\n"
    "Your Total Deposits = 58,997.63 And Your Total Loans = 6.02\n"
)
S_SUMMARY = (
    "INVENTED BETA ACCOUNT SUMMARY Type :     **REG    Status :    Active\n"
    "Category Number Amount Balance Forward From 08/29/31 41,003.77 "
    "Alpha Credits 1 62,005.11+ Zero Category 0.00 "
    "Delta Debits 2 44,003.42 Epsilon Charge 7.83 "
    "Ending Balance On 09/30/31 58,997.63 "
    "Average Balance (Ledger) 44,444.44+\n"
)
S_CREDITS = (
    "ALL CREDIT ACTIVITY\n"
    "Date Description Amount 09/01/31 EXAMPLE ROW ALPHA 62,005.11\n"
)
S_DEBITS = (
    "ELECTRONIC DEBITS\n"
    "Date Description Amount "
    "09/02/31 EXAMPLE ROW BETA (09/02/31 01:02:03) 33,001.13\n"
    "Continued 8/4173/1\n"
    "Statement Date: 09/30/2031 Account No.: 9174063 Page: 2 "
    "ELECTRONIC DEBITS (cont.)\n"
    "Date Description Amount 09/03/31 EXAMPLE ROW GAMMA 11,002.29\n"
)
S_OTHER = (
    "CHECKS AND OTHER DEBITS * indicates a gap in the check numbers\n"
    "Date Description Amount 09/30/31 EXAMPLE ROW DELTA 7.83\n"
)
S_GRID = (
    "DAILY BALANCE SUMMARY Beginning Ledger Balance on 08/29/31 was 41,003.77\n"
    "Date Balance Date Balance Date Balance "
    "09/01/31 103,008.88 09/02/31 70,007.75 09/03/31 59,005.46 "
    "09/30/31 58,997.63\n"
)
S_ITEMIZED = (
    "ITEMIZED SERVICE CHARGE\n"
    "Date Description Status Amount\n"
    "09/30/31 EXAMPLE CHARGE ALPHA 7.83\n"
    "TOTAL SERVICE CHARGE : 7.83\n"
    "This Statement Cycle Reflects 32 Days\n"
)
S_IMAGES = (
    "HOLDER BETA Account No. : 9174063 Stmt. Date : 09/30/2031\n"
    "IMAGE STATEMENT\n"
    "AMT: 7.83 SEQ: 61743072 CK:   DT: 09/30/31  ST: Paid\n"
    "End Statement 8/4173/3E\n"
)


def sectioned(*, masthead=S_MASTHEAD, glance=S_GLANCE, summary=S_SUMMARY,
              credits=S_CREDITS, debits=S_DEBITS, other=S_OTHER, grid=S_GRID,
              itemized=S_ITEMIZED, images=S_IMAGES) -> str:
    """The SECTIONED issue: named direction sections, no running balance, an
    authorization stamp welded into one description, and a zero-amount
    category the platform prints with no item count."""
    return (masthead + glance + summary + credits + debits + other + grid
            + itemized + images)


def parse(markdown: str):
    return cp.parse_category_partition_statement(markdown)


def published(markdown: str):
    statement = parse(markdown)
    assert statement is not None
    return statement


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("document", [unified(), sectioned()],
                         ids=["unified", "sectioned"])
def test_both_printed_issues_are_recognised_by_the_partition(document):
    assert cp.detect(document).claims


@pytest.mark.parametrize("document", [unified(), sectioned()],
                         ids=["unified", "sectioned"])
def test_upper_casing_the_document_is_not_this_platform(document):
    """The registration has no normalization, and the case is what holds it
    apart from the scanned template that prints `BALANCE FORWARD FROM`."""
    assert not cp.detect(document.upper()).claims


def test_the_relationship_block_is_furniture_rather_than_the_marker():
    """One of the eight archive documents prints no `ACCOUNTS AT A GLANCE` and
    no masthead at all; the census named the family after that block and the
    adversarial verification refuted it. Detection must not depend on it."""
    without = sectioned(
        masthead="Statement Date: 09/30/2031 Account No.: 9174063 Page: 1\n",
        glance="")
    assert cp.detect(without).claims
    assert parse(without) is not None


def test_a_header_with_no_ledger_is_not_a_statement():
    assert parse(U_MASTHEAD + U_GLANCE + U_SUMMARY) is None


#: The one issuer in the archive that already had its own reader for this
#: template. Its two markers, as `analysis/wilson_muir.py` declares them.
_ISSUER_SPECIFIC = "WILSON & MUIR BK & TRUST\nSMALL BUSINESS PACKAGE SUMMARY Type"


def _issuer_printing() -> str:
    """The same invented statement under the one masthead that has a reader."""
    return unified().replace("Invented Alpha Account SUMMARY Type", _ISSUER_SPECIFIC)


def test_the_issuer_specific_reader_of_this_template_supersedes_the_general_one():
    """The archive taught this edge, not the census: 14 documents of one issuer
    print this same partition and are read today by `wilson_muir`. The general
    reader claims them too, so without the edge all 14 resolve `ambiguous` and
    every one of them is validated today."""
    document = _issuer_printing()
    assert cp.detect(document).claims, "the general reader does claim this printing"
    dispatch = pr.resolve(document)
    assert dispatch.outcome != "ambiguous"
    assert [identifier for identifier, _score in dispatch.candidates] == ["wilson_muir"]


#: The pinned corpus surface, read rather than remembered.
_EXPECTATIONS = Path(__file__).resolve().parent / "data" / "parser_expectations.json"


def test_the_edge_is_what_keeps_the_one_PINNED_document_of_this_template_on_its_reader():
    """The corpus gate's green depends on this edge (review finding 2).

    Exactly one document in `tests/data/parser_expectations.json` is registered
    to the issuer-specific reader, and it prints this template: the general
    registration claims that printing, and the `supersedes` edge is the only
    thing that keeps it on `wilson_muir`. With the edge dropped, two claimants
    survive and the document resolves `ambiguous` — which is a corpus-gate
    regression, not a routing detail. The record said the opposite in three
    places until this closure.
    """
    pinned = [entry for entry in
              json.loads(_EXPECTATIONS.read_text(encoding="utf-8"))["documents"]
              if entry["parser_id"] == "wilson_muir"]
    assert len(pinned) == 1, "the pinned surface no longer holds exactly one"

    document = _issuer_printing()
    claimants = sorted(r.id for r in pr.registrations() if r.detect(document).claims)
    assert claimants == ["category_partition", "wilson_muir"]

    # The ROUTING is what this pins. The document body is invented, so the
    # issuer reader declines it and the dispatch is `unclaimed` — what matters
    # is that the edge left exactly one candidate standing and that it is the
    # issuer's. On the real pinned document, measured over its cached text,
    # the same routing ends in
    # `claimed/wilson_muir` with `attempted == []`.
    dispatch = pr.resolve(document)
    assert dispatch.outcome != "ambiguous"
    assert [identifier for identifier, _score in dispatch.candidates] == ["wilson_muir"]

    # The counterfactual, computed with the registry's own rule and this one
    # edge dropped: both claimants survive, which is what `ambiguous` means.
    superseded = {
        identifier
        for claimant in pr.registrations() if claimant.id in claimants
        for identifier in getattr(claimant, "supersedes", frozenset())
        if not (claimant.id == "wilson_muir" and identifier == "category_partition")
    }
    assert [identifier for identifier in claimants if identifier not in superseded] == [
        "category_partition", "wilson_muir"
    ]


def test_the_issuer_specific_reader_does_not_claim_the_general_printings():
    """The other direction. `wilson_muir` requires the issuer's own NAME, which
    this reader never looks for, so neither can shadow the other by accident."""
    from analysis import wilson_muir

    for document in (unified(), sectioned()):
        assert not wilson_muir.detect(document).claims


def test_the_registration_is_the_sole_claimant_of_both_issues():
    for document in (unified(), sectioned()):
        dispatch = pr.resolve(document)
        assert dispatch.outcome == "claimed"
        assert dispatch.parser_id == "category_partition"
        assert [identifier for identifier, _score in dispatch.candidates] == [
            "category_partition"
        ]


# ---------------------------------------------------------------------------
# What the two issues publish
# ---------------------------------------------------------------------------

def test_the_unified_issue_publishes_its_whole_ledger_with_running_balances():
    statement = published(unified())
    assert [(row.date, row.direction, row.amount, row.running_balance)
            for row in statement.transactions] == [
        ("2031-09-01", "credit", 62005.11, 103008.88),
        ("2031-09-02", "debit", -33001.13, 70007.75),
        ("2031-09-03", "debit", -11002.29, 59005.46),
        ("2031-09-30", "debit", -7.83, 58997.63),
    ]
    assert statement.stated_credit_count == 1
    assert statement.stated_debit_count == 3
    assert statement.stated_total_credits == 62005.11
    assert statement.stated_total_debits == 44011.25
    assert statement.stated_service_charge == 7.83


def test_the_sectioned_issue_takes_each_row_direction_from_its_section():
    statement = published(sectioned())
    assert [(row.date, row.direction, row.amount)
            for row in statement.transactions] == [
        ("2031-09-01", "credit", 62005.11),
        ("2031-09-02", "debit", -33001.13),
        ("2031-09-03", "debit", -11002.29),
        ("2031-09-30", "debit", -7.83),
    ]
    assert all(row.running_balance is None for row in statement.transactions)


def test_the_L1_partition_refusal_is_of_a_SECOND_DISTINCT_printing():
    """`unique_match`'s contract, pinned because the record misstated it as
    "exactly one" (review finding 7). A page header repeats, so an IDENTICAL
    second printing of the partition line — or of the summary control line —
    publishes the identical statement; a second DIFFERENT printing is the
    document contradicting itself about its own summary and is refused (M37)."""
    once = published(sectioned()).model_dump()
    twice = sectioned().replace(S_SUMMARY, S_SUMMARY + S_SUMMARY, 1)
    assert published(twice).model_dump() == once

    control = "INVENTED BETA ACCOUNT SUMMARY Type :     **REG    Status :    Active"
    repeated = sectioned().replace(control, control + "\n" + control, 1)
    assert published(repeated).model_dump() == once

    differing = sectioned().replace(
        S_SUMMARY, S_SUMMARY + S_SUMMARY.replace("Alpha Credits 1", "Alpha Credits 2"), 1)
    assert parse(differing) is None


def test_a_zero_amount_category_accounts_for_no_rows():
    """The platform prints no item count beside a category that moved nothing,
    and the count gate must read that as zero rather than as unknown."""
    assert published(sectioned()).stated_debit_count == 3


def test_an_authorization_stamp_inside_a_description_is_not_a_row_date():
    """The stamp is printed in the SAME notation as the row date. A reader that
    admits it splits the row and loses the amount."""
    stamped = next(row for row in published(sectioned()).transactions
                   if row.date == "2031-09-02")
    assert stamped.amount == -33001.13
    assert "01:02:03" in stamped.description


def test_the_period_opens_the_day_after_the_balance_forward_is_dated():
    statement = published(unified())
    assert (statement.period_start, statement.period_end) == ("2031-08-30", "2031-09-30")
    assert statement.days_in_period == 32


def test_the_printed_cycle_length_is_the_calendar_count_the_doctrine_reports_on():
    statement = published(unified())
    printed = cp._CYCLE_DAYS_RE.search(unified())
    assert printed is not None
    assert printed.group(1) == str(statement.days_in_period)


def test_the_ledger_grid_is_published_as_in_period_daily_evidence():
    statement = published(unified())
    assert [(entry.date, entry.balance)
            for entry in statement.stated_daily_balances] == [
        ("2031-09-01", 103008.88),
        ("2031-09-02", 70007.75),
        ("2031-09-03", 59005.46),
        ("2031-09-30", 58997.63),
    ]


def test_the_product_is_published_and_the_issuer_is_not():
    """`Statement.bank` is None by construction: a masthead welded to a PO box,
    a `Branch Name` that is a branch office and a bare contact domain are not
    an institution field (the honest-unknown-issuer ruling)."""
    assert published(unified()).bank is None
    assert published(sectioned()).bank is None
    assert published(unified()).account_name == "Invented Alpha Account"
    assert published(sectioned()).account_name == "INVENTED BETA ACCOUNT"


def test_the_currency_is_the_schema_default_and_says_so():
    """Nothing in this printing states a denomination, and this reader proves
    no institution, so a jurisdiction default would be an absence inference."""
    statement = published(unified())
    assert (statement.currency, statement.currency_source) == ("USD", "schema_default")


def test_the_bank_printed_average_is_evidence_and_never_the_platforms_own():
    statement = published(sectioned())
    assert statement.bank_reported_average_balance == 44444.44
    assert statement.bank_reported_average_label == "Average Balance (Ledger)"
    adb = compute_average_daily_balance(statement)
    assert adb.underwriting_adb != statement.bank_reported_average_balance
    assert adb.validations["agrees_with_bank_stated_average"] is False
    assert adb.ok is True


def test_the_printed_counts_are_published_but_never_compared():
    """The reader gates each direction's count against the rows it read, so a
    reconciler comparison would be a tautology. The table's default is
    INCOMPARABLE and this registration is deliberately not promoted into it."""
    assert counts_comparable("category_partition", "credit") is False
    assert counts_comparable("category_partition", "debit") is False


def test_the_reconstructed_ledger_supports_a_calendar_day_average():
    for document in (unified(), sectioned()):
        adb = compute_average_daily_balance(published(document),
                                            source_markdown=document)
        assert adb.ok is True
        assert adb.underwriting_adb is not None
        assert adb.calendar_day_count == 32


# ---------------------------------------------------------------------------
# THE COLLECTED GRID — the card's refusal
# ---------------------------------------------------------------------------

def _collected(document: str) -> str:
    """The same statement, under the platform's OTHER grid heading."""
    return document.replace("DAILY BALANCE SUMMARY", "COLLECTED BALANCE SUMMARY")


def test_a_collected_grids_cells_are_never_published_on_the_sectioned_issue():
    """The heading is the platform's own statement of what the series IS. A
    collected balance is the ledger balance minus uncollected float, so it is
    not the quantity the ADB doctrine averages, and NONE of its cells reaches
    the payload — the statement published under the collected heading is the
    one published under the ledger heading with the daily series removed and
    nothing else changed.

    This is the property §GLANCE GL3 was protecting and it is unchanged. What
    changed (W3 §CPDECL) is what happens next: the document is no longer
    declined for the absence, it publishes an EMPTY series and
    `analysis/adb.py` rules on it.
    """
    document = _collected(sectioned())
    assert cp.detect(document).claims
    statement = published(document)
    assert statement.stated_daily_balances == []
    with_ledger_grid = published(sectioned()).model_dump()
    assert with_ledger_grid["stated_daily_balances"] != []
    with_ledger_grid["stated_daily_balances"] = []
    assert statement.model_dump() == with_ledger_grid


def test_a_sectioned_document_printing_no_grid_at_all_publishes_an_empty_series():
    """The same rule with no grid of either kind on the page. The reader has no
    per-day evidence to gate and does not invent a verdict about it: the
    arithmetic gates still all apply, the series is empty, and the ADB doctrine
    decides whether an average can be published from the ledger alone."""
    document = sectioned().replace(S_GRID, "")
    assert document != sectioned()
    statement = published(document)
    assert statement.stated_daily_balances == []
    assert statement.bank_reported_average_balance is not None


def test_a_collected_grid_cell_is_never_published_as_a_daily_balance():
    """The unified issue keeps its per-row oracle when the grid is collected,
    so it still publishes — and it publishes NO daily snapshots, because the
    only grid it was offered is not one."""
    statement = published(_collected(unified()))
    assert statement.stated_daily_balances == []
    assert [row.running_balance for row in statement.transactions] == [
        103008.88, 70007.75, 59005.46, 58997.63
    ]


def test_the_collected_grids_own_seed_is_still_read_as_the_opening_balance():
    """Both headings print `Beginning Ledger Balance on <date> was <amount>`,
    and both call it a LEDGER balance. Only the CELLS are refused."""
    broken = _collected(unified()).replace(
        "Beginning Ledger Balance on 08/29/31 was 41,003.77",
        "Beginning Ledger Balance on 08/29/31 was 41,003.78",
    )
    assert parse(broken) is None


# ---------------------------------------------------------------------------
# The fourth sign case: the one BALANCE this platform marks
# ---------------------------------------------------------------------------

def test_a_trailing_plus_on_the_banks_average_balance_is_accepted():
    """The fourth sign case (review finding 4). The average IS a balance, and
    every document of the family that prints the entry prints it marked — four
    of the eight, measured. The mark is accepted and the figure read as
    positive, so the marked and unmarked printings publish the same statement."""
    marked = sectioned()
    unmarked = marked.replace("Average Balance (Ledger) 44,444.44+",
                              "Average Balance (Ledger) 44,444.44", 1)
    assert unmarked != marked
    assert published(marked).bank_reported_average_balance == 44444.44
    assert published(marked).model_dump() == published(unmarked).model_dump()


@pytest.mark.parametrize("printed,marked", [
    ("Ending Balance On 09/30/31 58,997.63", "Ending Balance On 09/30/31 58,997.63+"),
    ("Balance Forward From 08/29/31 41,003.77",
     "Balance Forward From 08/29/31 41,003.77+"),
])
def test_a_trailing_plus_on_a_DATED_balance_still_refuses_the_document(printed, marked):
    """The other side of the same case, and the reason it is a carried risk
    rather than a closed one: a plus on either dated balance costs the
    document. Fail-closed — nothing wrong is published — but the platform
    demonstrably marks a balance, so this is a printing it could produce."""
    document = sectioned().replace(printed, marked, 1)
    assert document != sectioned()
    assert cp.detect(document).claims
    assert parse(document) is None


# ---------------------------------------------------------------------------
# The sectioned issue: a mark that contradicts its heading
# ---------------------------------------------------------------------------

def test_a_plus_marked_row_inside_a_debit_section_is_refused():
    """The section heading is the platform's own statement of the direction, so
    a row marked money-IN inside a money-OUT section is two printings that
    disagree. The reader refuses rather than discarding the mark — which is
    what it did before this closure, publishing the row as a debit with no
    flag (review finding 5)."""
    document = sectioned().replace("EXAMPLE ROW GAMMA 11,002.29",
                                   "EXAMPLE ROW GAMMA 11,002.29+", 1)
    assert document != sectioned()
    assert cp.detect(document).claims
    assert parse(document) is None


def test_a_minus_marked_row_in_any_section_is_refused():
    """A trailing minus on an AMOUNT is a combination this platform prints
    nowhere: a minus is a balance's sign here. Refused on the sectioned issue
    exactly as `_unified_rows` refuses it on the unified one (M10)."""
    document = sectioned().replace("EXAMPLE ROW ALPHA 62,005.11",
                                   "EXAMPLE ROW ALPHA 62,005.11-", 1)
    assert document != sectioned()
    assert parse(document) is None


def test_a_plus_that_agrees_with_its_credit_section_still_publishes():
    """The refusal is of CONTRADICTION and not of the mark: a plus inside the
    credit section says what the heading says, and the statement published is
    the one the unmarked printing publishes."""
    document = sectioned().replace("EXAMPLE ROW ALPHA 62,005.11",
                                   "EXAMPLE ROW ALPHA 62,005.11+", 1)
    assert document != sectioned()
    assert published(document).model_dump() == published(sectioned()).model_dump()


# ---------------------------------------------------------------------------
# The mutation table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Mutant:
    """One row of the table: the gate, the edit, and what must happen."""

    id: str
    gate: str
    base: Callable[[], str]
    mutate: Callable[[str], str]
    #: `None` = the document must be DECLINED; `"detect"` = it must not even be
    #: claimed; `"same"` = a control arm that must publish an IDENTICAL
    #: statement; `"no_snapshots"` = it must publish the base statement with an
    #: EMPTY daily series and nothing else changed.
    expect: str | None


def _sub(old: str, new: str) -> Callable[[str], str]:
    return lambda text: text.replace(old, new, 1)


MUTANTS: tuple[Mutant, ...] = (
    # --- detection ---------------------------------------------------------
    Mutant("M01", "detection: the summary control line",
           unified, _sub("SUMMARY Type :     REG    Status :    Active",
                         "Account Summary"), "detect"),
    Mutant("M02", "detection: the partition column header",
           unified, _sub("Category Number Amount ", ""), "detect"),
    Mutant("M03", "detection: the dated closing balance",
           unified, _sub("Ending Balance On 09/30/31", "Ending Balance"), "detect"),
    Mutant("M04", "detection: the dated balance forward",
           sectioned, _sub("Balance Forward From 08/29/31", "Balance Forward"),
           "detect"),
    # --- the sign map ------------------------------------------------------
    Mutant("M05", "sign map: the trailing plus on a credit category",
           unified, _sub("Alpha Credits 1 62,005.11+", "Alpha Credits 1 62,005.11"),
           None),
    Mutant("M06", "sign map: a trailing plus added to a debit category",
           unified, _sub("Gamma Debits 1 11,002.29", "Gamma Debits 1 11,002.29+"),
           None),
    Mutant("M07", "sign map: a trailing MINUS on a category amount is refused",
           unified, _sub("Beta Debits 1 33,001.13", "Beta Debits 1 33,001.13-"), None),
    Mutant("M08", "sign map: a trailing PLUS on a grid balance is refused",
           unified, _sub("09/02/31 70,007.75", "09/02/31 70,007.75+"), None),
    Mutant("M09", "sign map: the trailing plus on a unified credit row",
           unified, _sub("EXAMPLE ROW ALPHA 62,005.11+", "EXAMPLE ROW ALPHA 62,005.11"),
           None),
    Mutant("M10", "sign map: a trailing minus on a unified row amount is refused",
           unified, _sub("EXAMPLE ROW GAMMA 11,002.29 59,005.46",
                         "EXAMPLE ROW GAMMA 11,002.29- 59,005.46"), None),
    # --- the partition's own arithmetic ------------------------------------
    Mutant("M11", "identity: the printed ending balance",
           unified, _sub("Ending Balance On 09/30/31 58,997.63",
                         "Ending Balance On 09/30/31 58,997.64"), None),
    Mutant("M12", "identity: the printed balance forward",
           sectioned, _sub("Balance Forward From 08/29/31 41,003.77",
                           "Balance Forward From 08/29/31 41,003.78"), None),
    Mutant("M13", "count gate: a credit category's printed count",
           unified, _sub("Alpha Credits 1 62,005.11+", "Alpha Credits 2 62,005.11+"),
           None),
    Mutant("M14", "count gate: a debit category's printed count",
           sectioned, _sub("Delta Debits 2 44,003.42", "Delta Debits 3 44,003.42"),
           None),
    Mutant("M15", "count gate: the uncounted category is exactly one posting",
           sectioned, _sub("Date Description Amount 09/30/31 EXAMPLE ROW DELTA 7.83",
                           "Date Description Amount 09/30/31 EXAMPLE ROW DELTA 5.41 "
                           "09/30/31 EXAMPLE ROW DELTA 2.42"), None),
    Mutant("M16", "amount gate: a debit row's amount",
           sectioned, _sub("EXAMPLE ROW GAMMA 11,002.29",
                           "EXAMPLE ROW GAMMA 11,002.30"), None),
    Mutant("M17", "recap gate: the printed service-charge total",
           unified, _sub("TOTAL SERVICE CHARGE : 7.83", "TOTAL SERVICE CHARGE : 8.71"),
           None),
    Mutant("M18", "partition is read END TO END: text no entry accounts for",
           unified, _sub("Ending Balance On 09/30/31 58,997.63",
                         "Ending Balance On 09/30/31 58,997.63 Unaccounted Trailer"),
           None),
    # --- the period --------------------------------------------------------
    Mutant("M19", "period: the printed cycle length",
           unified, _sub("This Statement Cycle Reflects 32 Days",
                         "This Statement Cycle Reflects 31 Days"), None),
    Mutant("M20", "period: a row dated outside the printed period",
           unified, _sub("09/03/31 EXAMPLE ROW GAMMA", "10/03/31 EXAMPLE ROW GAMMA"),
           None),
    # --- the per-day oracle ------------------------------------------------
    Mutant("M21", "grid: a cell that disagrees with the walked ledger",
           unified, _sub("09/03/31 59,005.46 09/30/31 58,997.63",
                         "09/03/31 59,005.47 09/30/31 58,997.63"), None),
    Mutant("M22", "grid: a day the ledger posts on missing from the grid",
           unified, _sub(" 09/03/31 59,005.46 09/30/31", " 09/30/31"), None),
    Mutant("M23", "grid: a day printed twice",
           unified, _sub("09/30/31 58,997.63\nThis Statement",
                         "09/30/31 58,997.63 09/30/31 58,997.63\nThis Statement"), None),
    Mutant("M24", "grid seed: the amount",
           sectioned, _sub("Beginning Ledger Balance on 08/29/31 was 41,003.77",
                           "Beginning Ledger Balance on 08/29/31 was 41,003.78"), None),
    Mutant("M25", "grid seed: the date",
           sectioned, _sub("Beginning Ledger Balance on 08/29/31",
                           "Beginning Ledger Balance on 08/28/31"), None),
    # M26 and M27 changed EXPECTATION in batch 9 (W3 §CPDECL) and are kept
    # rather than deleted: the gate they pin is still here, and it is now
    # "the collected grid's cells never reach the payload" instead of "the
    # document is declined". `no_snapshots` is the strictest form of that —
    # the mutant must publish the base statement with the daily series empty
    # and every other field unchanged — so a reader that read a collected cell,
    # or that changed anything else when the grid went away, still fails.
    Mutant("M26", "the collected heading: its cells never reach the payload",
           sectioned, _sub("DAILY BALANCE SUMMARY", "COLLECTED BALANCE SUMMARY"),
           "no_snapshots"),
    Mutant("M27", "no grid at all on the sectioned issue: an empty series, "
                  "not a decline",
           sectioned, lambda text: text.replace(S_GRID, ""), "no_snapshots"),
    Mutant("M28", "walk: a printed running balance",
           unified, _sub("EXAMPLE ROW BETA 33,001.13 70,007.75",
                         "EXAMPLE ROW BETA 33,001.13 70,007.76"), None),
    Mutant("M29", "walk: two rows swapped out of printed order",
           unified, _sub("09/01/31 EXAMPLE ROW ALPHA 62,005.11+ 103,008.88 "
                         "09/02/31 EXAMPLE ROW BETA 33,001.13 70,007.75",
                         "09/02/31 EXAMPLE ROW BETA 33,001.13 70,007.75 "
                         "09/01/31 EXAMPLE ROW ALPHA 62,005.11+ 103,008.88"), None),
    # --- the row grammar ---------------------------------------------------
    Mutant("M30", "unified rows carry EXACTLY two figures",
           unified, _sub("EXAMPLE ROW BETA 33,001.13 70,007.75",
                         "EXAMPLE ROW BETA REF 8.71 33,001.13 70,007.75"), None),
    Mutant("M31", "the authorization stamp's own parentheses",
           sectioned, _sub("(09/02/31 01:02:03)", "09/02/31 01:02:03"), None),
    # The row's text is untouched: only the SECTION it is printed in changes,
    # and that alone moves both direction counts. It is the mutant form of the
    # census's sign trap — one description printed as a credit in one section
    # and as a debit in another on the same statement.
    Mutant("M32", "direction follows the SECTION: a debit row moved into the "
                  "credit section moves both counts",
           sectioned, lambda text: text.replace(
               "Date Description Amount 09/01/31 EXAMPLE ROW ALPHA 62,005.11\n",
               "Date Description Amount 09/01/31 EXAMPLE ROW ALPHA 62,005.11 "
               "09/03/31 EXAMPLE ROW GAMMA 11,002.29\n"
           ).replace(
               "Date Description Amount 09/03/31 EXAMPLE ROW GAMMA 11,002.29\n"
               "CHECKS AND OTHER DEBITS", "CHECKS AND OTHER DEBITS"), None),
    Mutant("M33", "cheque recap: a row the unified table does not carry",
           unified, _sub("Date Check # Amount 09/02/31 4417 33,001.13",
                         "Date Check # Amount 09/02/31 4417 33,001.14"), None),
    # --- L-1 ---------------------------------------------------------------
    Mutant("M34", "L-1: a second account listed in the relationship block",
           unified, _sub("Invented Alpha Account Deposit 58,997.63\n",
                         "Invented Alpha Account Deposit 58,997.63 "
                         "XX9175 Invented Gamma Account Deposit 8.71\n"), None),
    Mutant("M35", "L-1: the relationship roll-up disagrees with the closing balance",
           unified, _sub("Your Total Deposits = 58,997.63",
                         "Your Total Deposits = 58,997.64"), None),
    Mutant("M36", "L-1: a second account number in a page header",
           unified, _sub("Account No.: XX9174 Page: 2", "Account No.: XX9175 Page: 2"),
           None),
    Mutant("M37", "L-1: a second partition on the page",
           sectioned, lambda text: text.replace(
               S_SUMMARY,
               S_SUMMARY + S_SUMMARY.replace("Alpha Credits 1", "Alpha Credits 2")),
           None),
    # The closure of review finding 5. The row's text is the platform's own
    # except for one character, and that character contradicts the heading the
    # row is printed under. Before the closure it was silently discarded and
    # the row published as a debit.
    Mutant("M38", "direction: a row mark that contradicts its SECTION",
           sectioned, _sub("EXAMPLE ROW GAMMA 11,002.29",
                           "EXAMPLE ROW GAMMA 11,002.29+"), None),
    # --- control arms: these must change NOTHING ---------------------------
    Mutant("C01", "control: the grid's three-up cells arrive out of document order",
           unified, _sub("09/01/31 103,008.88 09/02/31 70,007.75 "
                         "09/03/31 59,005.46 09/30/31 58,997.63",
                         "09/03/31 59,005.46 09/30/31 58,997.63 "
                         "09/01/31 103,008.88 09/02/31 70,007.75"), "same"),
    Mutant("C02", "control: an extra page break inside the ledger",
           unified, _sub("09/03/31 EXAMPLE ROW GAMMA",
                         "Continued 21/1997/2\nStatement Date: 09/30/2031 "
                         "Account No.: XX9174 Page: 3 "
                         "STATEMENT PERIOD ACTIVITY (cont.)\n"
                         "Date Check/Description Amount Balance "
                         "09/03/31 EXAMPLE ROW GAMMA"), "same"),
    Mutant("C03", "control: the relationship block is absent entirely",
           sectioned, lambda text: text.replace(S_GLANCE, ""), "same"),
)


def test_the_table_has_no_duplicate_rows_and_no_mutant_that_edits_nothing():
    """The batch-7 lesson, asserted rather than trusted: a mutant that does not
    change the document, or that produces a tree another row already produced,
    pins nothing while reporting a gate as covered."""
    seen: dict[str, str] = {}
    inert, duplicated = [], []
    for mutant in MUTANTS:
        base = mutant.base()
        mutated = mutant.mutate(base)
        if mutated == base:
            inert.append(mutant.id)
        if mutated in seen:
            duplicated.append(f"{mutant.id} duplicates {seen[mutated]}")
        seen[mutated] = mutant.id
    assert not inert, f"mutants that edit nothing: {inert}"
    assert not duplicated, f"duplicated mutants: {duplicated}"


def test_the_reorder_control_really_only_reorders():
    """C01 says `reorder`. A mutant whose description says reorder and whose
    edit deletes is the batch-7 defect that pinned nothing, so the claim is
    checked against the token multiset rather than taken on trust."""
    control = next(m for m in MUTANTS if m.id == "C01")
    base = control.base()
    mutated = control.mutate(base)
    assert sorted(re.findall(r"\S+", base)) == sorted(re.findall(r"\S+", mutated))
    assert base != mutated


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: m.id)
def test_every_gate_is_killed_by_its_own_mutant(mutant: Mutant):
    base = mutant.base()
    baseline = parse(base)
    assert baseline is not None, "the unmutated document must publish"
    mutated = mutant.mutate(base)
    if mutant.expect == "detect":
        assert not cp.detect(mutated).claims, f"{mutant.id} ({mutant.gate}) still claims"
        return
    if mutant.expect == "same":
        assert cp.detect(mutated).claims
        after = parse(mutated)
        assert after is not None, f"{mutant.id} ({mutant.gate}) stopped publishing"
        assert after.model_dump() == baseline.model_dump(), (
            f"{mutant.id} ({mutant.gate}) changed the published statement"
        )
        return
    if mutant.expect == "no_snapshots":
        assert cp.detect(mutated).claims
        after = parse(mutated)
        assert after is not None, f"{mutant.id} ({mutant.gate}) stopped publishing"
        expected = baseline.model_dump()
        assert expected["stated_daily_balances"] != [], (
            f"{mutant.id} ({mutant.gate}) has no daily series to remove"
        )
        expected["stated_daily_balances"] = []
        assert after.model_dump() == expected, (
            f"{mutant.id} ({mutant.gate}) changed more than the daily series"
        )
        return
    assert parse(mutated) is None, f"{mutant.id} ({mutant.gate}) still publishes"


# ---------------------------------------------------------------------------
# Fail-closed: a mangled token is an answer, never an exception
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("printed,damaged", [
    # a month and a day that are not one
    ("Balance Forward From 08/29/31", "Balance Forward From 13/45/31"),
    # a shape that IS a date, and a day that is not
    ("Balance Forward From 08/29/31", "Balance Forward From 02/30/31"),
    # an integer part past the money grammar's digit bound
    ("Ending Balance On 09/30/31 58,997.63",
     "Ending Balance On 09/30/31 9999999999999999.00"),
    # an item count longer than any count this platform prints
    ("Alpha Credits 1 62,005.11+", "Alpha Credits 99999 62,005.11+"),
    # a column header with nothing to the right of it
    ("Category Number Amount Balance Forward From 08/29/31 41,003.77 ",
     "Category Number Amount "),
    # a cycle length that is not the period's
    ("This Statement Cycle Reflects 32 Days", "This Statement Cycle Reflects 999 Days"),
    # a figure whose cents the layer lost
    ("Alpha Credits 1 62,005.11+", "Alpha Credits 1 62,005.1+"),
    # an account number one page disagrees about
    ("Account No.: XX9174 Page: 1", "Account No.: XX917 Page: 1"),
])
def test_a_mangled_summary_token_declines_rather_than_raising(printed, damaged):
    """Fail closed, and closed means an ANSWER: `None`, never an exception."""
    document = unified().replace(printed, damaged, 1)
    assert document != unified(), "the damage must actually change the document"
    assert parse(document) is None


@pytest.mark.parametrize("token", ["09/31/31", "13/01/31", "00/01/31", "09/00/31"])
def test_an_impossible_row_date_declines_rather_than_raising(token: str):
    document = unified().replace("09/03/31 EXAMPLE ROW GAMMA",
                                 f"{token} EXAMPLE ROW GAMMA", 1)
    assert document != unified()
    assert parse(document) is None


def test_an_empty_document_and_a_truncated_one_decline():
    assert parse("") is None
    assert parse(unified()[:200]) is None

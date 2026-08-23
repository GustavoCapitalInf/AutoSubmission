"""W3 §GLANCE — the signed category partition, and the grid it refuses to read.

**Every document in this module is INVENTED.** No name, account number, date,
balance or amount here is copied from any archive statement; the eight archive
documents that motivated the registration are named by `content_sha256` in the
branch log and in the commit message and are reproduced nowhere. That is the
standing batch-8 privacy rule, and it is also the better test: a test that
needs a real statement to make its point is a test of that statement rather
than of the rule.

The module carries the card's MUTATION TABLE (`MUTANTS` below). Each row names
a gate, transforms the document as the row's description says, and asserts the
outcome. Two properties are asserted about the table itself rather than
assumed: every mutant must actually CHANGE the document it is applied to (a
mutant that edits nothing pins nothing — the batch-7 lesson), and every
distinct mutated tree must be distinct from every other (a duplicated row is a
gate reported as covered twice and tested once).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
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
    "INVENTED BANK EXAMPLETOWN PO BOX 0 EXAMPLETOWN, EXAMPLE  00000 "
    "Tel: (000) 000-0000\n"
    "HOLDER NAME 1 EXAMPLE STREET EXAMPLETOWN EX 00000-0000\n"
    "Statement Date: 04/30/2026 Account No.: XX0000 Page: 1\n"
)
U_GLANCE = (
    "ACCOUNTS AT A GLANCE Account No. Sub Acct. Account Title Acct Type "
    "Balance XX0000 Invented Business Checking Deposit 125.00\n"
    "Your Total Deposits = 125.00 And Your Total Loans = .00\n"
)
U_SUMMARY = (
    "Invented Business Checking SUMMARY Type :     REG    Status :    Active\n"
    "Category Number Amount Balance Forward From 03/31/26 100.00 "
    "Deposits 1 200.00+ Debits 1 120.00 Automatic Withdrawals 1 50.00 "
    "TOTAL SERVICE CHARGE 5.00 Ending Balance On 04/30/26 125.00\n"
)
U_LEDGER = (
    "STATEMENT PERIOD ACTIVITY\n"
    "Date Check/Description Amount Balance "
    "04/01/26 EXAMPLE DEPOSIT 200.00+ 300.00 "
    "04/02/26 CHK#1001 120.00 180.00\n"
    "Continued 0/000/1\n"
    "Statement Date: 04/30/2026 Account No.: XX0000 Page: 2 "
    "STATEMENT PERIOD ACTIVITY (cont.)\n"
    "Date Check/Description Amount Balance "
    "04/03/26 EXAMPLE AUTOMATIC WITHDRAWAL 50.00 130.00 "
    "04/30/26 TOTAL SERVICE CHARGE 5.00 125.00\n"
)
U_CHECK_RECAP = (
    "CHECKS AND OTHER DEBITS * indicates a gap in the check numbers\n"
    "Date Check # Amount 04/02/26 1001 120.00\n"
)
U_ITEMIZED = (
    "ITEMIZED SERVICE CHARGE\n"
    "Date Description Status Amount\n"
    "04/30/26 EXAMPLE MINIMUM BALANCE FEE 5.00 TOTAL SERVICE CHARGE : 5.00\n"
)
U_GRID = (
    "DAILY BALANCE SUMMARY Beginning Ledger Balance on 03/31/26 was 100.00 "
    "Date Balance Date Balance Date Balance "
    "04/01/26 300.00 04/02/26 180.00 04/03/26 130.00 04/30/26 125.00\n"
    "This Statement Cycle Reflects 30 Days\n"
)
U_IMAGES = (
    "HOLDER NAME Account No. : XX0000 Stmt. Date : 04/30/2026\n"
    "IMAGE STATEMENT\n"
    "AM: 120.00 CK: 1001 DT: 04/02 SQ: 00000000 Paid\n"
    "End Statement 0/000/3E\n"
)


def unified(*, masthead=U_MASTHEAD, glance=U_GLANCE, summary=U_SUMMARY,
            ledger=U_LEDGER, recap=U_CHECK_RECAP, itemized=U_ITEMIZED,
            grid=U_GRID, images=U_IMAGES) -> str:
    """The UNIFIED issue: one running-balance table, a cheque recap, a ledger
    daily grid."""
    return masthead + glance + summary + ledger + recap + itemized + grid + images


S_MASTHEAD = (
    "Contact Us\n"
    "Branch Name Example Office\n"
    "Phone Number (000) 000-0000\n"
    "Address 1 Example Street Exampletown EX 00000\n"
    "Online Access WWW.EXAMPLE.INVALID\n"
    "Statement Date: 04/30/2026 Account No.: 0000000 Page: 1\n"
)
S_GLANCE = (
    "ACCOUNTS AT A GLANCE\n"
    "Account No. Sub Acct. Account Title Acct Type Balance "
    "0000000 INVENTED SMALL BUSINESS Deposit 125.00\n"
    "Your Total Deposits = 125.00 And Your Total Loans = .00\n"
)
S_SUMMARY = (
    "INVENTED SMALL BUSINESS SUMMARY Type :     **REG    Status :    Active\n"
    "Category Number Amount Balance Forward From 03/31/26 100.00 "
    "Deposits 1 200.00+ Debits 0.00 Card Activity 2 170.00 "
    "SERVICE CHARGE 5.00 Ending Balance On 04/30/26 125.00 "
    "Average Balance (Ledger) 140.00+\n"
)
S_CREDITS = (
    "ALL CREDIT ACTIVITY\n"
    "Date Description Amount 04/01/26 EXAMPLE MOBILE DEPOSIT 200.00\n"
)
S_DEBITS = (
    "ELECTRONIC DEBITS\n"
    "Date Description Amount "
    "04/02/26 0000 EXA PUR EXAMPLE MERCHANT EXAMPLETOWN EX "
    "(04/02/26 01:02:03) 120.00\n"
    "Continued 0/000/1\n"
    "Statement Date: 04/30/2026 Account No.: 0000000 Page: 2 "
    "ELECTRONIC DEBITS (cont.)\n"
    "Date Description Amount "
    "04/03/26 0000 EXA PUR EXAMPLE MERCHANT EXAMPLETOWN EX 50.00\n"
)
S_OTHER = (
    "CHECKS AND OTHER DEBITS * indicates a gap in the check numbers\n"
    "Date Description Amount 04/30/26 SERVICE CHARGE 5.00\n"
)
S_GRID = (
    "DAILY BALANCE SUMMARY Beginning Ledger Balance on 03/31/26 was 100.00\n"
    "Date Balance Date Balance Date Balance "
    "04/01/26 300.00 04/02/26 180.00 04/03/26 130.00 04/30/26 125.00\n"
)
S_ITEMIZED = (
    "ITEMIZED SERVICE CHARGE\n"
    "Date Description Status Amount\n"
    "04/30/26 EXAMPLE EXCESSIVE ITEM FEE 5.00\n"
    "TOTAL SERVICE CHARGE : 5.00\n"
    "This Statement Cycle Reflects 30 Days\n"
)
S_IMAGES = (
    "HOLDER NAME Account No. : 0000000 Stmt. Date : 04/30/2026\n"
    "IMAGE STATEMENT\n"
    "AMT: 5.00 SEQ: 00000000 CK:   DT: 04/30/26  ST: Paid\n"
    "End Statement 0/000/3E\n"
)


def sectioned(*, masthead=S_MASTHEAD, glance=S_GLANCE, summary=S_SUMMARY,
              credits=S_CREDITS, debits=S_DEBITS, other=S_OTHER, grid=S_GRID,
              itemized=S_ITEMIZED, images=S_IMAGES) -> str:
    """The SECTIONED issue: named direction sections, no running balance, an
    authorization stamp welded inside one description."""
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

@pytest.mark.parametrize("document", [unified(), sectioned()], ids=["unified", "sectioned"])
def test_both_printed_issues_are_recognised_by_the_partition(document):
    assert cp.detect(document).claims


@pytest.mark.parametrize("document", [unified(), sectioned()], ids=["unified", "sectioned"])
def test_upper_casing_the_document_is_not_this_platform(document):
    """The registration has no normalization and the case is what holds it
    apart from a scanned template printing `BALANCE FORWARD FROM`."""
    assert not cp.detect(document.upper()).claims


def test_the_relationship_block_is_furniture_rather_than_the_marker():
    """One of the eight archive documents prints no `ACCOUNTS AT A GLANCE` and
    no masthead at all; the census named the family after that block and the
    adversarial verification refuted it. Detection must not depend on it."""
    without = sectioned(masthead="Statement Date: 04/30/2026 Account No.: 0000000 Page: 1\n",
                        glance="")
    assert cp.detect(without).claims
    assert parse(without) is not None


def test_a_header_with_no_ledger_is_not_a_statement():
    assert parse(U_MASTHEAD + U_GLANCE + U_SUMMARY) is None


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
    assert [(row.date, row.direction, row.amount, row.running_balance) for row in
            statement.transactions] == [
        ("2026-04-01", "credit", 200.0, 300.0),
        ("2026-04-02", "debit", -120.0, 180.0),
        ("2026-04-03", "debit", -50.0, 130.0),
        ("2026-04-30", "debit", -5.0, 125.0),
    ]
    assert statement.stated_credit_count == 1
    assert statement.stated_debit_count == 3
    assert statement.stated_total_credits == 200.0
    assert statement.stated_total_debits == 175.0
    assert statement.stated_service_charge == 5.0


def test_the_sectioned_issue_takes_each_row_direction_from_its_section():
    statement = published(sectioned())
    assert [(row.date, row.direction, row.amount) for row in statement.transactions] == [
        ("2026-04-01", "credit", 200.0),
        ("2026-04-02", "debit", -120.0),
        ("2026-04-03", "debit", -50.0),
        ("2026-04-30", "debit", -5.0),
    ]
    assert all(row.running_balance is None for row in statement.transactions)


def test_an_authorization_stamp_inside_a_description_is_not_a_row_date():
    """The stamp is printed in the SAME notation as the row date. A reader that
    admits it splits the row and loses the amount."""
    statement = published(sectioned())
    stamped = next(row for row in statement.transactions if row.date == "2026-04-02")
    assert stamped.amount == -120.0
    assert "01:02:03" in stamped.description


def test_the_period_opens_the_day_after_the_balance_forward_is_dated():
    statement = published(unified())
    assert (statement.period_start, statement.period_end) == ("2026-04-01", "2026-04-30")
    assert statement.days_in_period == 30


def test_the_printed_cycle_length_is_the_calendar_count_the_doctrine_reports_on():
    statement = published(unified())
    assert cp._CYCLE_DAYS_RE.search(unified()).group(1) == str(statement.days_in_period)


def test_the_ledger_grid_is_published_as_in_period_daily_evidence():
    statement = published(unified())
    assert [(entry.date, entry.balance) for entry in statement.stated_daily_balances] == [
        ("2026-04-01", 300.0),
        ("2026-04-02", 180.0),
        ("2026-04-03", 130.0),
        ("2026-04-30", 125.0),
    ]


def test_the_product_is_published_and_the_issuer_is_not():
    """`Statement.bank` is None by construction: a masthead welded to a PO box,
    a `Branch Name` that is a branch office and a bare contact domain are not
    an institution field (the honest-unknown-issuer ruling)."""
    assert published(unified()).bank is None
    assert published(sectioned()).bank is None
    assert published(unified()).account_name == "Invented Business Checking"
    assert published(sectioned()).account_name == "INVENTED SMALL BUSINESS"


def test_the_currency_is_the_schema_default_and_says_so():
    """Nothing in this printing states a denomination, and this reader proves
    no institution, so a jurisdiction default would be an absence inference."""
    statement = published(unified())
    assert (statement.currency, statement.currency_source) == ("USD", "schema_default")


def test_the_bank_printed_average_is_evidence_and_never_the_platforms_own():
    statement = published(sectioned())
    assert statement.bank_reported_average_balance == 140.0
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
        adb = compute_average_daily_balance(published(document), source_markdown=document)
        assert adb.ok is True
        assert adb.underwriting_adb is not None
        assert adb.calendar_day_count == 30


# ---------------------------------------------------------------------------
# THE COLLECTED GRID — the card's refusal
# ---------------------------------------------------------------------------

def _collected(document: str) -> str:
    """The same statement, with the platform's OTHER grid heading."""
    return document.replace("DAILY BALANCE SUMMARY", "COLLECTED BALANCE SUMMARY")


def test_a_collected_grid_is_not_daily_ledger_evidence_and_the_document_is_declined():
    """The heading is the platform's own statement of what the series IS. A
    collected balance is the ledger balance minus uncollected float, so it is
    not the quantity the ADB doctrine averages, and the sectioned issue prints
    no running balance — leaving no per-day oracle at all."""
    document = _collected(sectioned())
    assert cp.detect(document).claims
    assert parse(document) is None


def test_the_decline_is_the_missing_oracle_and_not_the_arithmetic():
    """Everything else about the document still reads: the same statement with
    the ledger heading publishes, so the refusal is about the evidence class
    and nothing else."""
    assert parse(sectioned()) is not None
    assert parse(_collected(sectioned())) is None


def test_a_collected_grid_cell_is_never_published_as_a_daily_balance():
    """The unified issue keeps its per-row oracle when the grid is collected,
    so it still publishes — and it publishes NO daily snapshots, because the
    only grid it was offered is not one."""
    statement = published(_collected(unified()))
    assert statement.stated_daily_balances == []
    assert [row.running_balance for row in statement.transactions] == [
        300.0, 180.0, 130.0, 125.0
    ]


def test_the_collected_grids_own_seed_is_still_read_as_the_opening_balance():
    """Both headings print `Beginning Ledger Balance on <date> was <amount>`,
    and both call it a LEDGER balance. Only the CELLS are refused."""
    broken = _collected(unified()).replace(
        "Beginning Ledger Balance on 03/31/26 was 100.00",
        "Beginning Ledger Balance on 03/31/26 was 101.00",
    )
    assert parse(broken) is None


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
    #: statement.
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
           unified, _sub("Ending Balance On 04/30/26", "Ending Balance"), "detect"),
    Mutant("M04", "detection: the dated balance forward",
           sectioned, _sub("Balance Forward From 03/31/26", "Balance Forward"), "detect"),
    # --- the sign map ------------------------------------------------------
    Mutant("M05", "sign map: the trailing plus on a credit category",
           unified, _sub("Deposits 1 200.00+", "Deposits 1 200.00"), None),
    Mutant("M06", "sign map: a trailing plus added to a debit category",
           unified, _sub("Automatic Withdrawals 1 50.00", "Automatic Withdrawals 1 50.00+"),
           None),
    Mutant("M07", "sign map: a trailing MINUS on a category amount is refused",
           unified, _sub("Debits 1 120.00", "Debits 1 120.00-"), None),
    Mutant("M08", "sign map: a trailing PLUS on a grid balance is refused",
           unified, _sub("04/02/26 180.00", "04/02/26 180.00+"), None),
    Mutant("M09", "sign map: the trailing plus on a unified credit row",
           unified, _sub("EXAMPLE DEPOSIT 200.00+", "EXAMPLE DEPOSIT 200.00"), None),
    Mutant("M10", "sign map: a trailing minus on a unified row amount is refused",
           unified, _sub("EXAMPLE AUTOMATIC WITHDRAWAL 50.00",
                         "EXAMPLE AUTOMATIC WITHDRAWAL 50.00-"), None),
    # --- the partition's own arithmetic -----------------------------------
    Mutant("M11", "identity: the printed ending balance",
           unified, _sub("Ending Balance On 04/30/26 125.00",
                         "Ending Balance On 04/30/26 125.01"), None),
    Mutant("M12", "identity: the printed balance forward",
           sectioned, _sub("Balance Forward From 03/31/26 100.00",
                           "Balance Forward From 03/31/26 100.01"), None),
    Mutant("M13", "count gate: a credit category's printed count",
           unified, _sub("Deposits 1 200.00+", "Deposits 2 200.00+"), None),
    Mutant("M14", "count gate: a debit category's printed count",
           sectioned, _sub("Card Activity 2 170.00", "Card Activity 3 170.00"), None),
    Mutant("M15", "count gate: the uncounted category is exactly one posting",
           sectioned, _sub("Date Description Amount 04/30/26 SERVICE CHARGE 5.00",
                           "Date Description Amount 04/30/26 SERVICE CHARGE 2.00 "
                           "04/30/26 SERVICE CHARGE 3.00"), None),
    Mutant("M16", "amount gate: a debit row's amount",
           sectioned, _sub("EXAMPLE MERCHANT EXAMPLETOWN EX 50.00",
                           "EXAMPLE MERCHANT EXAMPLETOWN EX 51.00"), None),
    Mutant("M17", "recap gate: the printed service-charge total",
           unified, _sub("TOTAL SERVICE CHARGE : 5.00", "TOTAL SERVICE CHARGE : 6.00"),
           None),
    Mutant("M18", "partition is read END TO END: text no entry accounts for",
           unified, _sub("Ending Balance On 04/30/26 125.00",
                         "Ending Balance On 04/30/26 125.00 Unaccounted Trailer"), None),
    # --- the period --------------------------------------------------------
    Mutant("M19", "period: the printed cycle length",
           unified, _sub("This Statement Cycle Reflects 30 Days",
                         "This Statement Cycle Reflects 29 Days"), None),
    Mutant("M20", "period: a row dated outside the printed period",
           unified, _sub("04/03/26 EXAMPLE AUTOMATIC WITHDRAWAL",
                         "05/03/26 EXAMPLE AUTOMATIC WITHDRAWAL"), None),
    # --- the per-day oracle ------------------------------------------------
    Mutant("M21", "grid: a cell that disagrees with the walked ledger",
           unified, _sub("04/03/26 130.00", "04/03/26 131.00"), None),
    Mutant("M22", "grid: a day the ledger posts on missing from the grid",
           unified, _sub(" 04/03/26 130.00", ""), None),
    Mutant("M23", "grid: a day printed twice",
           unified, _sub("04/30/26 125.00\nThis Statement",
                         "04/30/26 125.00 04/30/26 125.00\nThis Statement"), None),
    Mutant("M24", "grid seed: the amount",
           sectioned, _sub("Beginning Ledger Balance on 03/31/26 was 100.00",
                           "Beginning Ledger Balance on 03/31/26 was 110.00"), None),
    Mutant("M25", "grid seed: the date",
           sectioned, _sub("Beginning Ledger Balance on 03/31/26",
                           "Beginning Ledger Balance on 03/30/26"), None),
    Mutant("M26", "the oracle itself: a collected grid leaves the sectioned "
                  "issue with none",
           sectioned, _sub("DAILY BALANCE SUMMARY", "COLLECTED BALANCE SUMMARY"), None),
    Mutant("M27", "the oracle itself: no grid at all on the sectioned issue",
           sectioned, lambda text: text.replace(S_GRID, ""), None),
    Mutant("M28", "walk: a printed running balance",
           unified, _sub("CHK#1001 120.00 180.00", "CHK#1001 120.00 181.00"), None),
    Mutant("M29", "walk: two rows of one day swapped out of printed order",
           unified, _sub("04/01/26 EXAMPLE DEPOSIT 200.00+ 300.00 "
                         "04/02/26 CHK#1001 120.00 180.00",
                         "04/02/26 CHK#1001 120.00 180.00 "
                         "04/01/26 EXAMPLE DEPOSIT 200.00+ 300.00"), None),
    # --- the row grammar ---------------------------------------------------
    Mutant("M30", "unified rows carry EXACTLY two figures",
           unified, _sub("CHK#1001 120.00 180.00", "CHK#1001 REF 9.99 120.00 180.00"),
           None),
    Mutant("M31", "the authorization stamp's own parentheses",
           sectioned, _sub("(04/02/26 01:02:03)", "04/02/26 01:02:03"), None),
    # The row's text is untouched: only the SECTION it is printed in changes,
    # and that alone moves both direction counts. It is the mutant form of the
    # census's sign trap — one description printed as a credit in one section
    # and as a debit in another on the same statement.
    Mutant("M32", "direction follows the SECTION: a debit row moved into the "
                  "credit section moves both counts",
           sectioned, lambda text: text.replace(
               "Date Description Amount 04/01/26 EXAMPLE MOBILE DEPOSIT 200.00\n",
               "Date Description Amount 04/01/26 EXAMPLE MOBILE DEPOSIT 200.00 "
               "04/03/26 0000 EXA PUR EXAMPLE MERCHANT EXAMPLETOWN EX 50.00\n"
           ).replace(
               "Date Description Amount "
               "04/03/26 0000 EXA PUR EXAMPLE MERCHANT EXAMPLETOWN EX 50.00\n"
               "CHECKS AND OTHER DEBITS", "CHECKS AND OTHER DEBITS"), None),
    Mutant("M33", "cheque recap: a row the unified table does not carry",
           unified, _sub("Date Check # Amount 04/02/26 1001 120.00",
                         "Date Check # Amount 04/02/26 1001 121.00"), None),
    # --- L-1 ---------------------------------------------------------------
    Mutant("M34", "L-1: a second account listed in the relationship block",
           unified, _sub("Deposit 125.00\n", "Deposit 125.00 XX0001 Invented Savings "
                                             "Deposit 9.00\n"), None),
    Mutant("M35", "L-1: the relationship roll-up disagrees with the closing balance",
           unified, _sub("Your Total Deposits = 125.00", "Your Total Deposits = 126.00"),
           None),
    Mutant("M36", "L-1: a second account number in a page header",
           unified, _sub("Account No.: XX0000 Page: 2", "Account No.: XX0001 Page: 2"),
           None),
    Mutant("M37", "L-1: a second partition on the page",
           sectioned, lambda text: text.replace(S_SUMMARY, S_SUMMARY + S_SUMMARY.replace(
               "Deposits 1 200.00+", "Deposits 2 200.00+")), None),
    # --- control arms: these must change NOTHING ---------------------------
    Mutant("C01", "control: the grid's three-up cells arrive out of document order",
           unified, _sub("04/01/26 300.00 04/02/26 180.00 04/03/26 130.00 04/30/26 125.00",
                         "04/03/26 130.00 04/30/26 125.00 04/01/26 300.00 04/02/26 180.00"),
           "same"),
    Mutant("C02", "control: an extra page break inside the ledger",
           unified, _sub("04/03/26 EXAMPLE AUTOMATIC WITHDRAWAL",
                         "Continued 0/000/2\nStatement Date: 04/30/2026 "
                         "Account No.: XX0000 Page: 3 "
                         "STATEMENT PERIOD ACTIVITY (cont.)\n"
                         "Date Check/Description Amount Balance "
                         "04/03/26 EXAMPLE AUTOMATIC WITHDRAWAL"), "same"),
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
    assert parse(mutated) is None, f"{mutant.id} ({mutant.gate}) still publishes"


# ---------------------------------------------------------------------------
# Fail-closed: a mangled token is an answer, never an exception
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("printed,damaged", [
    # a month and a day that are not one
    ("Balance Forward From 03/31/26", "Balance Forward From 13/45/26"),
    # a shape that IS a date and a day that is not
    ("Balance Forward From 03/31/26", "Balance Forward From 02/30/26"),
    # an integer part past the money grammar's digit bound
    ("Ending Balance On 04/30/26 125.00",
     "Ending Balance On 04/30/26 9999999999999999.00"),
    # an item count longer than any count this platform prints
    ("Deposits 1 200.00+", "Deposits 99999 200.00+"),
    # a column header with nothing to the right of it
    ("Category Number Amount Balance Forward From 03/31/26 100.00 ",
     "Category Number Amount "),
    # a cycle length that is not the period's
    ("This Statement Cycle Reflects 30 Days", "This Statement Cycle Reflects 999 Days"),
    # a figure whose cents the layer lost
    ("Deposits 1 200.00+", "Deposits 1 200.0+"),
    # an account number the second page disagrees about
    ("Account No.: XX0000 Page: 1", "Account No.: XX000 Page: 1"),
])
def test_a_mangled_summary_token_declines_rather_than_raising(printed, damaged):
    """Fail closed, and closed means an ANSWER: `None`, never an exception."""
    document = unified().replace(printed, damaged, 1)
    assert document != unified(), "the damage must actually change the document"
    assert parse(document) is None


@pytest.mark.parametrize("token", ["04/31/26", "13/01/26", "00/01/26", "04/00/26"])
def test_an_impossible_row_date_declines_rather_than_raising(token: str):
    document = unified().replace("04/03/26 EXAMPLE AUTOMATIC WITHDRAWAL",
                                 f"{token} EXAMPLE AUTOMATIC WITHDRAWAL", 1)
    assert parse(document) is None


def test_an_empty_document_and_a_truncated_one_decline():
    assert parse("") is None
    assert parse(unified()[:200]) is None

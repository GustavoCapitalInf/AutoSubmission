"""W3 §GRAM4 — the fourth summary grammar of the third core processor.

Every document here is synthetic. The eight archive documents that motivated
the registration are named by content sha in the branch log and in the commit
message; none of them is reproduced, because a test that needs a real
statement to make its point is a test of that statement rather than of the
rule.

The three EXCLUSION proofs this cell owes Ocean are pinned in this module
rather than only measured in the log: `core_processor_daily`'s 20, the
2-document `Statement Period Start:` platform, and the Columbia cohort's 3.
Each is a printing this registration must not claim, and each is asserted in
BOTH directions where a sibling registration exists.
"""
from __future__ import annotations

import json

import pytest

from analysis import core_processor_counted as cpc, core_processor_daily as cpd
from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401 — populates the registry
from analysis.count_semantics import counts_comparable, semantics_for

# ---------------------------------------------------------------------------
# One document of the template, in the pieces a test can vary
# ---------------------------------------------------------------------------

MASTHEAD = (
    "Page 1 (1)\n"
    "Account #:\n"
    "XXXXXX0000\n"
    "This statement: February 27, 2054 Last statement: January 30, 2054\n"
    "Contact us:\n"
    "000-000-0000\n"
    "Example Branch Office 1 Example St Exampletown XX 00000\n"
    "HOLDER NAME 1 EXAMPLE ST EXAMPLETOWN XX 00000-0000\n"
    "example.com\n"
)
PRODUCT = "Analyzed Example Checking\n"
SUMMARY = (
    "Account Summary Account Activity\n"
    "Account number XXXXXX0000 Minimum balance $50.00 Average balance $120.00 "
    "Avg. collected balance $120.00\n"
    "Beginning balance (1/30/2054)\n"
    "$100.00\n"
    "Credits\n"
    "Deposits (0) + 0.00 Electronic cr (1) + 300.00 Other credits (0) + 0.00\n"
    "Total credits\n"
    "+$300.00\n"
    "Debits\n"
    "Checks paid (1) - 200.00 Electronic db (1) - 50.00 Other debits (0) - 0.00\n"
    "Total debits\n"
    "- $250.00\n"
    "Ending balance (2/27/2054)\n"
    "$150.00\n"
)
CREDITS = (
    "ELECTRONIC CREDITS\n"
    "Date Description Credits\n"
    "2-3 Preauthorized Credit 300.00\n"
    "EXAMPLE ORIGINATOR PAYABLES CCD EXAMPLE HOLDER\n"
)
CHECKS = (
    "CHECKS PAID\n"
    "Number Date Amount\n"
    "1001 2-2 200.00\n"
)
DEBITS = (
    "ELECTRONIC DEBITS\n"
    "Date Description Debits\n"
    "2-5 Preauthorized Debit 50.00\n"
)
GRID = (
    "DAILY BALANCES\n"
    "Date Amount\n"
    "1-30 100.00 2-2 -100.00 2-3 200.00\n"
    "2-5 150.00\n"
)
FOOTER = (
    "Thank you for banking with Example Branch Office\n"
    "PLEASE EXAMINE THIS STATEMENT AND ENCLOSED ITEMS AT ONCE.\n"
)


def document(*, masthead=MASTHEAD, product=PRODUCT, summary=SUMMARY,
             credits=CREDITS, checks=CHECKS, debits=DEBITS, grid=GRID,
             footer=FOOTER) -> str:
    return masthead + product + summary + credits + checks + debits + grid + footer


def parse(markdown: str):
    return cpc.parse_core_processor_counted_statement(markdown)


def published(**pieces):
    """The statement a variation publishes, asserted to exist."""
    statement = parse(document(**pieces))
    assert statement is not None
    return statement


# ---------------------------------------------------------------------------
# Detection — the two markers, and the case that separates four grammars
# ---------------------------------------------------------------------------

def test_the_template_is_recognised_by_its_period_sentence_and_dated_balances():
    assert cpc.detect(document()).claims


def test_upper_casing_the_document_is_not_this_template():
    """Sentence case is what separates this processor's grammars from the
    SECOND core processor's upper-case period line, so this registration
    declares no normalization — pinned rather than left to be noticed."""
    assert not cpc.detect(document().upper()).claims


def test_the_registration_declares_no_normalization():
    assert pr.by_id("core_processor_counted").normalize is None


@pytest.mark.parametrize("field", [
    "Last statement:", "This statement:",
    "Beginning balance (", "Ending balance (",
])
def test_no_single_required_field_claims_on_its_own(field):
    """Two required markers, each needing both of its halves: removing any one
    of the four fields must withdraw the claim."""
    assert not cpc.detect(document().replace(field, "Removed field ")).claims


def test_an_undated_balance_pair_is_not_this_grammar():
    """The dated balances are the marker. A summary printing `Beginning
    balance $100.00` with no parenthesised date is a DIFFERENT grammar of the
    same processor, and this is the whole reason the two registrations are
    disjoint rather than ordered."""
    undated = document().replace(
        "Beginning balance (1/30/2054)\n$100.00", "Beginning balance $100.00"
    ).replace("Ending balance (2/27/2054)\n$150.00", "Ending balance $150.00")
    assert not cpc.detect(undated).claims


def test_the_period_sentences_may_be_printed_in_either_order():
    """This grammar prints `This statement:` FIRST, which is the opposite of
    the sibling's order — the two sentences are therefore read separately
    rather than as one phrase."""
    swapped = document().replace(
        "This statement: February 27, 2054 Last statement: January 30, 2054",
        "Last statement: January 30, 2054 Page 1 of 3\nThis statement: February 27, 2054",
    )
    statement = parse(swapped)
    assert statement is not None
    assert (statement.period_start, statement.period_end) == ("2054-01-31", "2054-02-27")


def test_a_document_that_merely_quotes_the_period_sentence_is_not_claimed():
    quoted = (
        "SOME OTHER BANK\nStatement of Account\n"
        "01/15 ACH DEBIT This statement: February 27, 2054 250.00\n"
    )
    assert not cpc.detect(quoted).claims


# ---------------------------------------------------------------------------
# Exclusion proof 1 — `core_processor_daily`'s 20, in both directions
# ---------------------------------------------------------------------------

SIBLING_DAILY = (
    "Last statement: March 31, 2054 This statement: April 30, 2054 "
    "Total days in statement period: 30\n"
    "Direct inquiries to: 000-000-0000\n"
    "Example Business Checking\n"
    "Account number XXXXXX0000 Enclosures 2 Low balance $50.00\n"
    "Beginning balance $100.00 Total additions 300.00 "
    "Total subtractions 250.00 Ending balance $150.00\n"
    "DEBITS\nDate Description Subtractions\n04-02 ' ACH Debit 250.00\n"
    "CREDITS\nDate Description Additions\n04-03 ' Deposit 300.00\n"
    "DAILY BALANCES\nDate Amount\n03-31 100.00 04-02 -150.00 04-03 150.00\n"
)


def test_the_third_grammar_of_this_processor_is_not_claimed_by_this_reader():
    """The 20 documents `core_processor_daily` reads print this registration's
    period sentence and NOT its dated balances."""
    assert not cpc.detect(SIBLING_DAILY).claims


def test_this_grammar_is_not_claimed_by_the_third_one():
    """The other half of the same fact, and the one that would have cost
    documents: `core_processor_daily` requires a `Total days in statement
    period:` line, which this grammar prints nowhere."""
    assert not cpd.detect(document()).claims


def test_the_two_registrations_are_disjoint_by_marker_not_by_precedence():
    """No supersedes edge and no band: neither can claim the other's printing,
    so there is nothing for a precedence rule to resolve."""
    registration = pr.by_id("core_processor_counted")
    assert registration.supersedes == frozenset()
    assert registration.band == pr.by_id("core_processor_daily").band


def test_neither_document_resolves_ambiguous():
    """The failure mode a precedence rule exists to prevent, asserted absent
    end to end rather than argued from the markers."""
    assert pr.resolve(document()).parser_id == "core_processor_counted"
    assert pr.resolve(SIBLING_DAILY).outcome in {"claimed", "unclaimed"}
    assert pr.resolve(SIBLING_DAILY).parser_id != "core_processor_counted"


# ---------------------------------------------------------------------------
# Exclusion proof 2 — the 2-document `Statement Period Start:` platform
# ---------------------------------------------------------------------------

OTHER_PLATFORM = (
    "Statement Period Start: May 1, 2054 Statement Period End: May 31, 2054\n"
    "Account Summary\n"
    "Beginning Balance as of 05/01/2054 $3,297.98\n"
    "+ Deposits and Credits  (31) $80,351.88\n"
    "- Checks and Debits  (24) $79,145.20\n"
    "Ending Balance as of 05/31/2054 $4,504.66\n"
    "Total Days in Statement Period 31\n"
)


def test_the_statement_period_start_platform_is_not_claimed():
    """§LCPERIOD L2.1/L7.2's two documents: parenthesised counts and an
    `Account Summary` block, which makes them LOOK like this grammar. They
    print neither of its required markers — the period sentence pair or the
    dated balances — and they belong to no cell yet."""
    assert not cpc.detect(OTHER_PLATFORM).claims


def test_a_parenthesised_count_alone_is_not_this_summary_partition():
    """The near miss stated precisely: that platform prints counts in
    parentheses too. What this reader requires is the category NAMES this
    processor prints, in a partition closed by `Total credits`/`Total
    debits`."""
    assert cpc._counted_partition(OTHER_PLATFORM) is None


# ---------------------------------------------------------------------------
# Exclusion proof 3 — the Columbia cohort's 3 (COLUMBIA-5's population)
# ---------------------------------------------------------------------------

COLUMBIA_GRAMMAR = (
    "Last statement: February 27, 2054 This statement: March 31, 2054\n"
    "Account number XXXXXX4166 Beginning balance $59,347.32\n"
    "Low balance $21,464.92 Deposits/Additions $129,016.40\n"
    "Average balance $42,172.07 Withdrawals/Subtractions $156,005.07\n"
    "Interest earned $0.00 Ending balance $32,358.65\n"
    "Deposits/Additions\n03-16 39,692.35\nTotal Additions $129,016.40\n"
)


def test_the_columbia_fifth_grammar_is_not_claimed():
    """Three documents print this registration's period sentence PAIR with an
    UNDATED `Beginning balance $` / `Ending balance $`. They are another
    cell's population and this registration must not reach them — the dated
    balances are what hold the two apart."""
    assert not cpc.detect(COLUMBIA_GRAMMAR).claims


def test_the_columbia_cohort_is_not_reachable_by_relaxing_to_the_period_pair():
    """Stated as the counterfactual, because it is the mistake the card was
    written to avoid: the period pair alone is printed by four grammars of
    this processor, so a registration resting on it would claim all of them
    and then decline three at parse."""
    assert cpc._OPENING_DATE_RE.search(COLUMBIA_GRAMMAR)
    assert cpc._CLOSING_DATE_RE.search(COLUMBIA_GRAMMAR)
    assert not cpc._BEGINNING_LABEL_RE.search(COLUMBIA_GRAMMAR)


# ---------------------------------------------------------------------------
# What one document publishes
# ---------------------------------------------------------------------------

def test_the_whole_statement_is_published_from_the_printed_figures():
    statement = published()
    assert statement.period_start == "2054-01-31"
    assert statement.period_end == "2054-02-27"
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 150.00
    assert statement.stated_total_credits == 300.00
    assert statement.stated_total_debits == 250.00
    assert statement.account_number == "XXXXXX0000"
    assert statement.account_name == "Analyzed Example Checking"
    assert [(row.date, row.direction, row.amount) for row in statement.transactions] == [
        ("2054-02-02", "debit", -200.00),
        ("2054-02-03", "credit", 300.00),
        ("2054-02-05", "debit", -50.00),
    ]


def test_the_period_opens_the_day_after_the_last_statement_closed():
    """The two printed dates are the dates of STATEMENTS, not of the period.
    The grid's first cell and the parenthesised date on `Beginning balance`
    both confirm it independently."""
    statement = published()
    assert statement.period_start == "2054-01-31"
    assert cpc._summary(document()).seed == "2054-01-30"


def test_the_printed_counts_are_published_as_the_sum_of_their_categories():
    statement = published()
    assert statement.stated_credit_count == 1
    assert statement.stated_debit_count == 2


def test_the_bank_reported_average_is_published_with_the_label_it_was_read_from():
    statement = published()
    assert statement.bank_reported_average_balance == 120.00
    assert statement.bank_reported_average_label == "Average balance"


def test_the_collected_balance_statistic_is_not_read_as_the_average():
    """`Avg. collected balance` is a different basis printed on the same line;
    the `$` and the label are what keep the two apart."""
    statement = published(summary=SUMMARY.replace("Average balance $120.00 ", ""))
    assert statement.bank_reported_average_balance is None
    assert statement.bank_reported_average_label is None


def test_no_day_count_is_published_because_the_template_prints_none():
    """This grammar drops the sibling's `Total days in statement period:`
    line. The canonical ADB denominator is the printed period's calendar days,
    which `analysis/adb.py` derives for itself, so an invented figure here
    would be a number no statement carries."""
    assert published().days_in_period is None


def test_the_issuer_is_never_published_even_though_the_document_names_a_branch():
    """§LCPERIOD L4's evidence came from THIS cohort: what these documents
    print under `Contact us:` and in the courtesy sentence is a BRANCH office.
    A wrong name is worse than no name."""
    assert published().bank is None
    assert pr.by_id("core_processor_counted").bank == "Core Processor Counted Summary Platform"


def test_a_product_name_the_text_layer_printed_four_times_is_declined():
    """This processor's layer emits a line up to four times over — fill,
    stroke and two shadows of one printed string. Publishing the repeat
    publishes a name no statement carries; collapsing it is a REPAIR."""
    statement = published(product="Analyzed Example Analyzed Example\n")
    assert statement.account_name is None


def test_a_product_name_printed_once_is_published_as_printed():
    assert published(product="Business Business Checking\n").account_name == (
        "Business Business Checking")


def test_a_paragraph_in_the_product_slot_is_declined():
    """The slot is one printed line; a disclosure sentence in it is not a
    product name."""
    long_line = ("EFFECTIVE THIS MONTH YOU WILL SEE UPDATED STANDARD PRICING "
                 "CHANGES FOR CERTAIN TREASURY SERVICES IF APPLICABLE.\n")
    assert published(product=long_line).account_name is None


# ---------------------------------------------------------------------------
# The daily grid, and the ADB doctrine's opening state
# ---------------------------------------------------------------------------

def test_the_pre_period_cell_is_a_gate_and_is_not_published():
    """ADB doctrine (2054-08-15): a balance dated before the period opens is
    initialization, never a denominator day. `stated_daily_balances`'
    contract is IN-PERIOD snapshots and `analysis/adb.py` treats an
    out-of-period one as a defect of the statement, so publishing it would
    withhold every document of the family (§LCPERIOD L7.8)."""
    statement = published()
    assert [entry.date for entry in statement.stated_daily_balances] == [
        "2054-02-02", "2054-02-03", "2054-02-05"]
    assert all(entry.date >= statement.period_start
               for entry in statement.stated_daily_balances)


def test_the_pre_period_cell_must_equal_the_printed_beginning_balance():
    """It is the platform's own second printing of the opening balance, and it
    is checked as one."""
    assert parse(document(grid=GRID.replace("1-30 100.00", "1-30 999.00"))) is None


def test_a_grid_day_that_disagrees_with_the_walk_refuses_the_document():
    assert parse(document(grid=GRID.replace("2-3 200.00", "2-3 201.00"))) is None


def test_a_posting_day_missing_from_the_grid_refuses_the_document():
    assert parse(document(grid=GRID.replace(" 2-3 200.00", ""))) is None


def test_a_grid_day_the_ledger_never_posts_on_refuses_the_document():
    assert parse(document(grid=GRID.rstrip("\n") + " 2-9 150.00\n")) is None


def test_the_grid_is_required():
    """On a template printing no running balance, the grid is the only
    per-day evidence there is."""
    assert parse(document(grid="")) is None


def test_a_day_the_grid_prints_twice_refuses_the_document():
    """Not the sibling's rule. This grammar prints its grid in four columns
    whose cells arrive out of document order, so a repeated day is evidence
    the column recovery went wrong rather than a harmless reprint."""
    assert parse(document(grid=GRID.rstrip("\n") + " 2-5 150.00\n")) is None


def test_the_grid_may_print_its_cells_out_of_document_order():
    """Measured on the archive: a `2-23` cell after the `2-26` one. The grid
    is read as a map, so order carries nothing."""
    shuffled = (
        "DAILY BALANCES\nDate Amount\n"
        "2-5 150.00 1-30 100.00\n2-3 200.00 2-2 -100.00\n"
    )
    assert published(grid=shuffled).ending_balance == 150.00


# ---------------------------------------------------------------------------
# The counted partition — twelve gates no other grammar in the complex has
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("printed,corrupted", [
    ("Electronic cr (1)", "Electronic cr (2)"),
    ("Checks paid (1)", "Checks paid (0)"),
    ("Electronic db (1)", "Electronic db (3)"),
    ("Deposits (0)", "Deposits (1)"),
    ("Other credits (0)", "Other credits (2)"),
    ("Other debits (0)", "Other debits (1)"),
])
def test_every_category_count_is_gated_against_the_section_it_heads(printed, corrupted):
    assert parse(document(summary=SUMMARY.replace(printed, corrupted))) is None


@pytest.mark.parametrize("printed,corrupted", [
    ("Electronic cr (1) + 300.00", "Electronic cr (1) + 301.00"),
    ("Checks paid (1) - 200.00", "Checks paid (1) - 199.00"),
    ("Electronic db (1) - 50.00", "Electronic db (1) - 51.00"),
])
def test_every_category_total_is_gated_against_its_own_rows(printed, corrupted):
    assert parse(document(summary=SUMMARY.replace(printed, corrupted))) is None


def test_a_category_total_that_its_own_rows_do_not_reach_refuses():
    """ISOLATED to the per-category check, which is the point: the direction
    total and the identity are moved WITH the category so that both still
    close, and the only printing left disagreeing is the category's own.

    A mutation run is what asked for this test. The parametrized corruption
    above kills through the DIRECTION sum — it moves a category without
    moving the total that category feeds — so with the per-category check
    deleted the suite still passed. A gate test that fires through a
    different gate is a gate that is not tested."""
    broken = (SUMMARY.replace("Electronic cr (1) + 300.00", "Electronic cr (1) + 301.00")
              .replace("+$300.00", "+$301.00")
              .replace("Ending balance (2/27/2054)\n$150.00",
                       "Ending balance (2/27/2054)\n$151.00"))
    assert parse(document(summary=broken)) is None


def test_a_direction_total_that_its_categories_do_not_sum_to_refuses():
    """The bank prints the parts AND the sum, so this is a printing
    independent of the per-category checks above — and this corruption is
    isolated to it: every category still matches its own rows, and the
    identity still closes, because the ending balance moves with the total."""
    broken = SUMMARY.replace("+$300.00", "+$400.00").replace(
        "Ending balance (2/27/2054)\n$150.00",
        "Ending balance (2/27/2054)\n$250.00")
    assert parse(document(summary=broken)) is None


def test_a_summary_whose_identity_does_not_close_refuses():
    assert parse(document(summary=SUMMARY.replace(
        "Ending balance (2/27/2054)\n$150.00",
        "Ending balance (2/27/2054)\n$151.00"))) is None


def test_a_partition_missing_one_of_its_six_categories_refuses():
    """All six or nothing: the direction totals are checked against the SUM of
    the categories, so a missing one would move the check rather than fail
    it."""
    assert parse(document(summary=SUMMARY.replace(
        "Other debits (0) - 0.00", ""))) is None


def test_a_category_figure_printed_with_the_wrong_sign_refuses():
    """The sign is the direction the template declares. A credit category
    printed with a minus is a summary this reader has misread, and the
    pattern refuses to match rather than reading the magnitude."""
    assert parse(document(summary=SUMMARY.replace(
        "Electronic cr (1) + 300.00", "Electronic cr (1) - 300.00"))) is None


def test_a_direction_total_printed_with_the_wrong_sign_refuses():
    assert parse(document(summary=SUMMARY.replace(
        "Total credits\n+$300.00", "Total credits\n-$300.00"))) is None


def test_a_direction_total_printed_with_no_sign_at_all_refuses():
    """Requiring what is printed and nothing else. The template always prints
    the sign, so an unsigned total is a layout this reader has not seen, and
    refusing it is the fail-closed answer rather than a stricter reading of
    the same document."""
    assert parse(document(summary=SUMMARY.replace(
        "Total credits\n+$300.00", "Total credits\n$300.00"))) is None


@pytest.mark.parametrize("contradiction", [
    "Total credits\n+$900.00\n",
    "Electronic cr (9) + 999.00\n",
])
def test_a_summary_contradicting_itself_about_one_row_refuses(contradiction):
    """`unique_match`: a row a strip prints twice, differently, is the
    document contradicting itself, and there is no rule saying which printing
    to believe. Both halves of the partition are pinned — the CATEGORY rows
    are read by the same discipline as the direction totals, which a mutation
    run had to ask for."""
    assert parse(document(summary=SUMMARY + contradiction)) is None


def test_a_summary_row_reprinted_identically_is_not_a_contradiction():
    """A page header repeats. The test is on the captured groups, not on the
    number of matches."""
    assert parse(document(summary=SUMMARY + "Electronic cr (1) + 300.00\n")) is not None


def test_the_gates_are_blind_to_a_same_day_same_direction_same_category_redistribution():
    """Named rather than left to be found. Moving value between two rows that
    share a date, a direction AND a category holds every gate — the counted
    partition SHRINKS §LCPERIOD L3's blind spot rather than closing it: there,
    splitting one row into two survived; here that moves the category's count,
    so the surviving construction needs two rows that already exist. Both are
    forgery signatures rather than OCR ones."""
    two_rows = (
        "ELECTRONIC CREDITS\nDate Description Credits\n"
        "2-3 Preauthorized Credit 100.00 2-3 Preauthorized Credit 200.00\n"
    )
    moved = (
        "ELECTRONIC CREDITS\nDate Description Credits\n"
        "2-3 Preauthorized Credit 150.00 2-3 Preauthorized Credit 150.00\n"
    )
    summary = SUMMARY.replace("Electronic cr (1)", "Electronic cr (2)")
    honest = published(summary=summary, credits=two_rows)
    forged = published(summary=summary, credits=moved)
    assert honest.stated_total_credits == forged.stated_total_credits
    assert sorted(row.amount for row in forged.transactions) != sorted(
        row.amount for row in honest.transactions)


# ---------------------------------------------------------------------------
# The two printed account numbers
# ---------------------------------------------------------------------------

def test_the_two_printed_account_numbers_must_agree():
    """A document printing two different numbers is carrying more than one
    account, which this reader has no schema for (L-1). Refused rather than
    read from whichever field came first."""
    assert parse(document(masthead=MASTHEAD.replace(
        "XXXXXX0000\n", "XXXXXX9999\n", 1))) is None


def test_a_document_printing_no_masthead_account_field_refuses():
    assert parse(document(masthead=MASTHEAD.replace("Account #:\n", ""))) is None


# ---------------------------------------------------------------------------
# The period, printed twice in two notations
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("printed,corrupted", [
    ("Beginning balance (1/30/2054)", "Beginning balance (1/29/2054)"),
    ("Ending balance (2/27/2054)", "Ending balance (2/28/2054)"),
])
def test_a_dated_balance_that_disagrees_with_the_statement_dates_refuses(printed, corrupted):
    assert parse(document(summary=SUMMARY.replace(printed, corrupted))) is None


def test_a_month_word_that_is_not_a_month_refuses():
    """The pattern proves the SHAPE and nothing more."""
    assert parse(document(masthead=MASTHEAD.replace(
        "February 27, 2054", "Fiscal 27, 2026"))) is None


def test_a_calendar_impossible_statement_date_refuses():
    assert parse(document(masthead=MASTHEAD.replace(
        "February 27, 2054", "February 31, 2054"))) is None


def test_a_row_dated_outside_the_printed_period_refuses():
    assert parse(document(debits=DEBITS.replace("2-5 ", "3-5 "))) is None


def test_a_row_dated_on_the_day_before_the_period_opens_refuses():
    """The seed day is opening STATE. A posting dated there is not a posting
    of this period."""
    assert parse(document(debits=DEBITS.replace("2-5 ", "1-30 "))) is None


# ---------------------------------------------------------------------------
# The row grammar: an unpadded `m-d` needs a real calendar class
# ---------------------------------------------------------------------------

def test_an_invoice_suffix_in_a_description_is_not_a_row_date():
    """The hazard this template's SHORTER row date creates, and the reason the
    month and day are calendar ranges rather than digit runs: these ledgers
    print `BILL.COM P26031002 - 4974025 INV 26-2` on ordinary rows. Read as a
    date, `26-2` is a phantom row — which the printed count would then catch,
    refusing eight honest documents."""
    with_reference = CREDITS.replace(
        "EXAMPLE ORIGINATOR PAYABLES CCD EXAMPLE HOLDER",
        "EXAMPLE ORIGINATOR PAYABLES CCD BILL.COM P26031002 - 4974025 INV 26-2",
    )
    statement = published(credits=with_reference)
    assert len(statement.transactions) == 3


@pytest.mark.parametrize("token", ["26-2", "0-5", "13-1", "2-32", "773-7100"])
def test_a_token_that_is_not_a_calendar_month_and_day_is_not_a_row_date(token):
    assert not cpc._DATE_RE.search(f"prefix {token} suffix")


@pytest.mark.parametrize("token", ["2-3", "12-31", "02-03", "1-1"])
def test_the_dates_this_template_really_prints_are_read(token):
    assert cpc._DATE_RE.search(f"prefix {token} suffix").group(1) == token


def test_a_sub_dollar_amount_printed_bare_is_read():
    """`.14` and `.55` are printings this family really carries, which is what
    makes the bare alternative load-bearing rather than defensive."""
    statement = published(
        summary=SUMMARY.replace("Electronic db (1) - 50.00", "Electronic db (1) - .50")
        .replace("- $250.00", "- $200.50")
        .replace("Ending balance (2/27/2054)\n$150.00",
                 "Ending balance (2/27/2054)\n$199.50"),
        debits=DEBITS.replace("50.00", ".50"),
        grid=GRID.replace("2-5 150.00", "2-5 199.50"),
    )
    assert statement.transactions[-1].amount == -0.50


def test_an_amount_whose_integer_part_is_not_ascii_is_invisible_not_zero():
    """§LCPERIOD L6.2. With an ASCII boundary class the sub-dollar alternative
    matches at the dot and publishes 0.00 where the bank printed 250.00. The
    `\\w` boundary is what closes it — asserted against the hole directly so
    the test cannot rot into a tautology."""
    import re
    ascii_boundary = re.compile(r"(?<![0-9A-Za-z.,/-])((?:[0-9][0-9,]*\.[0-9]{2}|\.[0-9]{2}))(?![0-9A-Za-z.,])")
    foreign = "٢٥٠.00"
    assert ascii_boundary.search(foreign).group(1) == ".00"
    assert cpc._FIGURE_RE.search(foreign) is None


@pytest.mark.parametrize("run_on", ["300.00USD", "300.00٥"])
def test_an_amount_run_onto_a_word_is_refused(run_on):
    """Both boundary classes refuse the ASCII case; only the `\\w` one refuses
    a figure run onto a non-ASCII glyph, and that is the difference the
    class is carried for. Asserted because a mutation run showed the ASCII
    form of the RIGHT boundary passing every other test in this module."""
    assert cpc._FIGURE_RE.search(run_on) is None


def test_a_signed_section_figure_is_refused():
    """Every amount printed in a section is a MAGNITUDE whose direction is its
    category. One arriving with a sign contradicts its own column."""
    assert parse(document(debits=DEBITS.replace("50.00", "-50.00"))) is None


def test_a_row_printing_no_amount_before_the_next_row_refuses():
    assert parse(document(credits=CREDITS.replace("300.00", ""))) is None


def test_two_rows_printed_on_one_line_are_both_read():
    """A line-anchored pattern would silently halve this printing."""
    two = (
        "ELECTRONIC DEBITS\nDate Description Debits\n"
        "2-5 Preauthorized Debit 20.00 2-5 Preauthorized Debit 30.00\n"
    )
    statement = published(
        summary=SUMMARY.replace("Electronic db (1)", "Electronic db (2)"),
        debits=two,
    )
    assert [row.amount for row in statement.transactions if row.date == "2054-02-05"] == [
        -20.00, -30.00]


def test_a_description_printed_below_its_amount_is_not_swallowed_into_the_next_row():
    """Audit B10 (I05): the block printed below a credit's amount is that credit's own (it alone is outstanding
    and the line holds one ACH block), so the credit publishes it; the next row never takes it."""
    statement = published()
    assert statement.transactions[1].description == (
        "Preauthorized Credit EXAMPLE ORIGINATOR PAYABLES CCD EXAMPLE HOLDER"
    )
    assert statement.transactions[2].description == "Preauthorized Debit"


#: The interleaving printing, in the pieces the archive prints it in: two
#: rows' merchant blocks welded onto ONE line inside the second row's span,
#: and then a third row whose span holds a flush the layer proves is its own
#: (W3 §DESCATTRIB). Three rows on one day, so the grid moves by one figure.
INTERLEAVED_DEBITS = (
    "ELECTRONIC DEBITS\n"
    "Date Description Debits\n"
    "2-5 Preauthorized Debit 10.00 2-5 Preauthorized Debit\n"
    "EXAMPLE FIRST PAYABLES CCD EXAMPLE SECOND PAYABLES CCD\n"
    "20.00 2-5 Preauthorized Debit\n"
    "EXAMPLE THIRD PAYABLES CCD\n"
    "30.00\n"
)


def interleaved():
    """The document above, with the summary and the grid it implies."""
    return published(
        summary=SUMMARY.replace("Electronic db (1) - 50.00", "Electronic db (3) - 60.00")
        .replace("- $250.00", "- $260.00")
        .replace("Ending balance (2/27/2054)\n$150.00",
                 "Ending balance (2/27/2054)\n$140.00"),
        debits=INTERLEAVED_DEBITS,
        grid=GRID.replace("2-5 150.00", "2-5 140.00"),
    )


def debits_of(statement):
    return [row.description for row in statement.transactions
            if row.direction == "debit" and row.date == "2054-02-05"]


def test_an_interleaved_block_pair_is_published_on_neither_of_its_rows():
    """The reader-level form of §DESCATTRIB's oracle. The layer welded two
    rows' merchant blocks with a single space and no boundary to cut at; a
    reader that publishes them attributes one row's merchant to the other."""
    assert debits_of(interleaved())[:2] == ["Preauthorized Debit", "Preauthorized Debit"]


def test_a_block_the_layer_proves_is_one_rows_own_is_published_on_that_row():
    """Fail-closed, not fail-silent: where the layer leaves exactly one row's
    block outstanding the block IS published, on the row it belongs to."""
    assert debits_of(interleaved())[2] == "Preauthorized Debit EXAMPLE THIRD PAYABLES CCD"


def test_no_row_publishes_a_merchant_printed_for_another_row():
    """The property, rather than a string: this is the defect the card is for,
    and on the archive it is what the KAPITUS and ONDECK rows were suffering."""
    published_text = " ".join(debits_of(interleaved()))
    assert "EXAMPLE FIRST" not in published_text
    assert "EXAMPLE SECOND" not in published_text


def test_the_reader_attributes_through_the_shared_call_and_not_beside_it():
    """Patching the shared function must change what this reader publishes.
    Importing the name proves nothing about the call site; this does."""
    marker = "REPLACED BY THE HARNESS"
    original = cpc.attributed_descriptions
    try:
        cpc.attributed_descriptions = (
            lambda runs, **kwargs: [[marker] * len(cells) for cells in runs])
        assert debits_of(interleaved()) == [marker] * 3
    finally:
        cpc.attributed_descriptions = original


def test_a_section_broken_across_a_page_keeps_both_of_its_runs():
    continued = CREDITS + (
        "ELECTRONIC CREDITS (Continued)\nDate Description Credits\n"
        "2-4 Preauthorized Credit 100.00\n"
    )
    statement = published(
        summary=SUMMARY.replace("Electronic cr (1) + 300.00", "Electronic cr (2) + 400.00")
        .replace("+$300.00", "+$400.00")
        .replace("Ending balance (2/27/2054)\n$150.00",
                 "Ending balance (2/27/2054)\n$250.00"),
        credits=continued,
        grid=GRID.replace("2-3 200.00", "2-3 200.00 2-4 300.00").replace(
            "2-5 150.00", "2-5 250.00"),
    )
    assert len([row for row in statement.transactions if row.direction == "credit"]) == 2


# ---------------------------------------------------------------------------
# The cheque grid — §LCPERIOD L5.3's three constructions, one template on
# ---------------------------------------------------------------------------

def test_a_cheque_serial_is_read_from_the_rows_own_leading_cell():
    assert published().transactions[0].description == "Check 1001"


def test_two_cheque_rows_on_one_line_each_keep_their_own_serial():
    two = (
        "CHECKS PAID\nNumber Date Amount\n"
        "1001 2-2 120.00 1002 * 2-2 80.00\n"
    )
    statement = published(
        summary=SUMMARY.replace("Checks paid (1)", "Checks paid (2)"),
        checks=two,
    )
    assert [row.description for row in statement.transactions
            if row.date == "2054-02-02"] == ["Check 1001", "Check 1002"]


@pytest.mark.parametrize("furniture", [
    "Continued on page 27\n",
    "XXXXXXXXXXXX0000\n",
    "Page 2 February 27, 2054 7654321\n",
])
def test_furniture_printed_above_a_cheque_row_cannot_fabricate_a_serial(furniture):
    """An end-anchored read over the gap takes any trailing digits as a
    serial and publishes a number the statement does not carry — the worst of
    the three being a WRONG serial rather than a missing one. The serial is
    the leading cell of the row's own line, so furniture on a different line
    cannot reach it."""
    checks = (
        "CHECKS PAID\nNumber Date Amount\n" + furniture + "2-2 200.00\n"
    )
    assert published(checks=checks).transactions[0].description == "Check"


def test_a_serial_break_marker_is_not_read_into_the_serial():
    checks = "CHECKS PAID\nNumber Date Amount\n1001 * 2-2 200.00\n"
    assert published(checks=checks).transactions[0].description == "Check 1001"


# ---------------------------------------------------------------------------
# Registry wiring and the count-semantics entry
# ---------------------------------------------------------------------------

def test_the_registration_is_wired_to_this_modules_reader():
    assert pr.by_id("core_processor_counted").parse is (
        cpc.parse_core_processor_counted_statement)


def test_a_header_with_no_ledger_is_not_a_statement():
    assert parse(MASTHEAD + PRODUCT + SUMMARY) is None


@pytest.mark.parametrize("direction", ["credit", "debit"])
def test_the_printed_counts_are_surveyed_as_a_comparable_category_sum(direction):
    """This is the first registration in the complex to print a count at all.
    The entry is comparable, and its reason says out loud that the agreement
    is a tautology of the parser's own gate."""
    assert counts_comparable("core_processor_counted", direction)
    semantics = semantics_for("core_processor_counted", direction)
    assert semantics.scope == "multi_category_sum_proven_complete"
    assert semantics.mapping is None
    assert "TAUTOLOG" in semantics.reason.upper()


# ---------------------------------------------------------------------------
# Audit round 2, R2-B07 (R07): a welded run of credit blocks keeps its text beside the rows it marks
# ---------------------------------------------------------------------------

#: Seven credits printed the way the archive's welded runs print them: row 1 alone on its line with its block under
#: it; rows 2 to 5 opened on one line, the fifth row's amount pushed below a line that welds four blocks; rows 6 and 7
#: on the next line with their two blocks welded under them. The receiver of every block is the holder.
WELDED_SUMMARY = SUMMARY.replace("Electronic cr (1) + 300.00", "Electronic cr (7) + 610.00").replace(
    "+$300.00", "+$610.00").replace("Ending balance (2/27/2054)\n$150.00", "Ending balance (2/27/2054)\n$460.00")
WELDED_GRID = (
    "DAILY BALANCES\n"
    "Date Amount\n"
    "1-30 100.00 2-2 -100.00 2-3 50.00\n"
    "2-4 100.00 2-5 110.00 2-6 180.00\n"
    "2-7 260.00 2-8 350.00 2-9 460.00\n"
)
RECEIVER = "NORTHWIND BAKERY"
ALONE_BLOCK = f"CONTOSO INC. PAYABLES 1100000001 {RECEIVER} CCD"
CUSTOMER_BLOCKS = tuple(f"CONTOSO INC. PAYABLES 110000000{n} {RECEIVER} CCD" for n in (2, 3, 4))
KAPITUS_BLOCK = f"KAPITUS LLC FUNDING 5500000005 {RECEIVER} CCD"
SECOND_BLOCKS = (f"FABRIKAM INC. PAYABLES 2200000001 {RECEIVER} CCD", f"SAMPLE INC. PAYABLES 2200000002 {RECEIVER} CCD")


def welded_credits(first_line=(*CUSTOMER_BLOCKS, KAPITUS_BLOCK), second_line=SECOND_BLOCKS, *,
                   alone=ALONE_BLOCK) -> str:
    return (
        "ELECTRONIC CREDITS\n"
        "Date Description Credits\n"
        "2-3 Preauthorized Credit 150.00\n"
        f"{alone}\n"
        "2-4 Preauthorized Credit 50.00 2-5 Preauthorized Credit 60.00 2-6 Preauthorized Credit 70.00 "
        "2-7 Preauthorized Credit\n"
        f"{' '.join(first_line)}\n"
        "80.00 2-8 Preauthorized Credit 90.00 2-9 Preauthorized Credit 110.00\n"
        f"{' '.join(second_line)}\n"
    )


def welded(**lines):
    """The welded statement, published."""
    return published(summary=WELDED_SUMMARY, credits=welded_credits(**lines), grid=WELDED_GRID)


def test_a_welded_runs_marked_credits_keep_the_flushs_text_beside_their_label():
    statement = welded()
    credits = [t for t in statement.transactions if t.amount > 0]
    first, second = " ".join((*CUSTOMER_BLOCKS, KAPITUS_BLOCK)), " ".join(SECOND_BLOCKS)
    assert [t.description for t in credits] == [f"Preauthorized Credit {ALONE_BLOCK}"] + ["Preauthorized Credit"] * 6
    assert [t.payer_text_unread for t in credits] == [False] + [True] * 6
    assert [t.unread_payer_text for t in credits] == ["", first, first, first, first, second, second]


#: Audit round 3, R3-B09 (R3-87): a registry lender whose ACH company name holds a class-code word (CashArc's
#: 'CASH-ARC LLC', the spelling its own ACH entries print; the registry's alias 'CASH ARC LLC').
CASHARC_BLOCKS = (f"CASH ARC LLC EDI PYMNTS 0000001 {RECEIVER} CCD", f"CASH-ARC LLC EDI PYMNTS 0000001 {RECEIVER} CCD",
                  f"CASH ARC L.L.C. EDI PYMNTS 0000001 {RECEIVER} CCD")


@pytest.mark.parametrize("block", CASHARC_BLOCKS)
def test_r3_87_a_class_code_word_before_a_legal_form_is_a_name_word_not_a_second_code(block):
    assert cpc._block_below_is_one([block])
    credits = f"ELECTRONIC CREDITS\nDate Description Credits\n2-3 Preauthorized Credit 300.00\n{block}\n"
    statement = published(credits=credits)
    [credit] = [t for t in statement.transactions if t.amount > 0]
    assert (credit.description, credit.payer_text_unread, credit.unread_payer_text) == (
        f"Preauthorized Credit {block}", False, "")


@pytest.mark.parametrize("line", [
    # A real ARC entry (no legal form after the code) closes its block: two codes, never one row's.
    f"CONTOSO SUPPLY ARC 0001 {RECEIVER} CCD",
    f"CONTOSO SUPPLY CCD {RECEIVER} FABRIKAM TOOLS PPD {RECEIVER}",
    # A legal form after the LAST code does not join two blocks into one.
    f"CASH ARC LLC EDI PYMNTS 0000001 {RECEIVER} CCD CONTOSO INC. PAYABLES 0000002 {RECEIVER} CCD",
])
def test_r3_87_the_controls_still_count_two_codes(line):
    assert not cpc._block_below_is_one([line])


#: Audit round 3, R3-B09 review round 1: two blocks welded under ONE outstanding row whose SECOND block's originator
#: opens with a legal-form word other than the LLC family (a cooperative, a state's revenue department, a village, a
#: company store, an LP gas dealer). The code closing the first block is still a code, so the line holds two codes and
#: the row is marked unread with the whole flush, as before R3-87: the weld never becomes one row's description.
LOOKALIKE_WELDS = tuple(
    f"{first} 2200000001 {RECEIVER} CCD {second} 2200000002 {RECEIVER} {code}" for first, second, code in (
    ("FABRIKAM INC. PAYABLES", "CO-OP POWER PAYMENT", "CCD"),
    ("FABRIKAM INC. PAYABLES", "Co-op Power Payment", "CCD"),
    ("FABRIKAM INC. PAYABLES", "CO DEPT REVENUE TAX REFUND", "PPD"),
    ("FABRIKAM INC. PAYABLES", "INC VILLAGE OF SAMPLE AP", "CCD"),
    ("FABRIKAM INC. PAYABLES", "INCORPORATED VILLAGE OF SAMPLE", "CCD"),
    ("FABRIKAM INC. PAYABLES", "CORPORATION SAMPLE SERVICES", "CCD"),
    ("FABRIKAM INC. PAYABLES", "CORP SAMPLE PAYABLES", "CCD"),
    ("FABRIKAM INC. PAYABLES", "COMPANY STORE SALES", "CCD"),
    ("FABRIKAM INC. PAYABLES", "LP GAS SAMPLE", "CCD"),
    ("FABRIKAM INC. PAYABLES", "LIMITED SAMPLE BRANDS", "CCD"),
    ("FABRIKAM INC. PAYABLES", "LTD SAMPLE COMMODITIES", "CCD"),
    ("KAPITUS LLC FUNDING", "CO-OP POWER PAYMENT", "CCD"),
    ("KAPITUS LLC FUNDING", "COMPANY STORE SALES", "CCD"),
    ("KAPITUS LLC FUNDING", "INC VILLAGE OF SAMPLE AP", "CCD"),
    )
)


@pytest.mark.parametrize("line", LOOKALIKE_WELDS)
def test_r3_87_review_a_weld_whose_next_block_opens_on_a_legal_form_word_still_counts_two_codes(line):
    assert not cpc._block_below_is_one([line])
    credits = f"ELECTRONIC CREDITS\nDate Description Credits\n2-3 Preauthorized Credit 300.00\n{line}\n"
    statement = published(credits=credits)
    [credit] = [t for t in statement.transactions if t.amount > 0]
    assert (credit.description, credit.payer_text_unread, credit.unread_payer_text) == (
        "Preauthorized Credit", True, line)


def test_r3_87_review_only_the_llc_family_joins_a_class_code_word_to_a_name():
    """The narrowed rule: a class-code word is a name word only before LLC, L.L.C., L L C, LLP or PLLC (no ACH
    originator name opens on one of them). Before INC, CORP, CO, LTD or LP it is still a code (a name like that
    stays unread: the safe direction); no registry alias prints a class-code word before one of them."""
    for form in ("LLC", "llc", "L.L.C.", "L L C", "LLP", "PLLC"):
        assert cpc._block_below_is_one([f"CASH ARC {form} EDI PYMNTS 0000001 {RECEIVER} CCD"]), form
    for form in ("INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP"):
        assert not cpc._block_below_is_one([f"CASH ARC {form} EDI PYMNTS 0000001 {RECEIVER} CCD"]), form


def test_r3_87_a_welded_run_holding_casharc_still_marks_its_rows_and_keeps_the_flush():
    second = (f"CONTOSO INC. PAYABLES 2200000001 {RECEIVER} CCD", CASHARC_BLOCKS[1])
    statement = welded(second_line=second)
    credits = [t for t in statement.transactions if t.amount > 0]
    assert [t.payer_text_unread for t in credits] == [False] + [True] * 6
    assert [t.unread_payer_text for t in credits][5:] == [" ".join(second)] * 2
    assert [t.description for t in credits][5:] == ["Preauthorized Credit"] * 2


def test_the_unread_text_is_kept_out_of_the_schema_and_written_only_where_set():
    from analysis.schema import Statement, Transaction

    assert "unread_payer_text" not in json.dumps(Statement.model_json_schema())
    statement = welded()
    rows = statement.model_dump()["transactions"]
    assert ["unread_payer_text" in row for row in rows if row["amount"] > 0] == [False] + [True] * 6
    assert not any("unread_payer_text" in row for row in rows if row["amount"] < 0)
    plain = Transaction(date="2054-02-03", description="Preauthorized Credit", amount=10.0, direction="credit")
    assert "unread_payer_text" not in plain.model_dump()
    restored = Statement.model_validate(statement.model_dump())
    assert [t.unread_payer_text for t in restored.transactions] == [t.unread_payer_text for t in statement.transactions]


def test_a_debit_section_with_a_welded_block_keeps_its_labels_and_no_unread_text():
    """Debit sections keep their labels until the owner admits the debit readings (G7): a welded flush naming a funder
    under two debits gives them neither the text nor the mark."""
    debits = (
        "ELECTRONIC DEBITS\n"
        "Date Description Debits\n"
        "2-5 Preauthorized Debit 20.00 2-5 Preauthorized Debit\n"
        f"KAPITUS LLC PAYMENT 5500000005 {RECEIVER} CCD CONTOSO INC. BILLING 3300000001 {RECEIVER} CCD\n"
        "30.00\n"
    )
    statement = published(summary=SUMMARY.replace("Electronic db (1) - 50.00", "Electronic db (2) - 50.00"),
                          debits=debits)
    rows = [(t.description, t.payer_text_unread, t.unread_payer_text) for t in statement.transactions
            if t.description.startswith("Preauthorized Debit")]
    assert rows == [("Preauthorized Debit", False, "")] * 2

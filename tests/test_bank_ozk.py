"""W3 §FROSTOZK — Bank OZK, where the direction of a row has to be solved.

EVERY FIGURE, NAME, ACCOUNT NUMBER AND DATE IN THIS FILE IS INVENTED. No
archive content appears here. The numbers are chosen so that each gate's
failure is visible and so that the day the printed count has to disambiguate
is reproducible in four rows instead of eighty.
"""
from __future__ import annotations

import pytest

from analysis.bank_ozk import DETECTION_MARKERS, detect, parse_bank_ozk_statement
from analysis.parser_registry import score_markers

SERVICE = (
    "CUSTOMER SERVICE CENTER\n"
    "P.O. BOX 196 OZARK, AR 72949\n"
    "800-274-4482\n"
)

HEADER = (
    "Statement Date: 02/28/2026\n"
    "Account Number: 000000\n"
    "SAMPLE CHECKING* ACCOUNT - 000000\n"
)


def summary(*, credits_count: int = 2, credits: str = "13.00",
            debits_count: int = 2, debits: str = "3.00",
            previous: str = "100.00", current: str = "110.00",
            previous_as_of: str = "01/31/26", current_as_of: str = "02/28/26",
            days: int = 28) -> str:
    return (
        f"PREVIOUS STATEMENT BALANCE AS OF {previous_as_of}: {previous} "
        f"PLUS     {credits_count}   DEPOSITS AND OTHER CREDITS: {credits} "
        f"LESS     {debits_count}      CHECKS AND OTHER DEBITS: {debits} "
        f"CURRENT STATEMENT BALANCE AS OF {current_as_of}: {current} "
        f"NUMBER OF DAYS IN THIS STATEMENT PERIOD:            {days}\n"
    )


#: One day carrying three rows whose signs the day's own step does NOT
#: determine — 3.00 against 1.00 + 2.00 — followed by a day that does.
ROWS = (
    "OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS "
    "02/02 SAMPLE ALPHA 3.00 02/02 SAMPLE BETA 1.00 02/02 SAMPLE GAMMA 2.00 "
    "02/03 SAMPLE DELTA 10.00\n"
)

GRID = (
    "BALANCE BY DATE\n"
    "DATE AMOUNT            DATE AMOUNT 02/02 100.00 02/03 110.00\n"
)


def document(*, service: str = SERVICE, header: str = HEADER,
             block: str | None = None, rows: str = ROWS, grid: str = GRID,
             checks: str = "", tail: str = "") -> str:
    return service + header + (summary() if block is None else block) + checks + rows + grid + tail


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_it_claims_its_own_printing():
    assert detect(document()).claims


@pytest.mark.parametrize(
    "removed",
    ["P.O. BOX 196 OZARK, AR 72949", "800-274-4482",
     "PREVIOUS STATEMENT BALANCE AS OF", "BALANCE BY DATE"],
)
def test_every_required_marker_is_load_bearing(removed):
    assert not detect(document().replace(removed, "XXXX")).claims


def test_the_marker_set_is_three_required_and_one_corroborating():
    kinds = sorted(marker.kind for marker in DETECTION_MARKERS)
    assert kinds == ["corroborating", "required", "required", "required"]
    assert score_markers(DETECTION_MARKERS, document()).score == 1.0


def test_it_does_not_claim_a_mixed_case_balance_by_date_platform():
    """The core-processor template that prints `Balance By Date` is a DIFFERENT
    registration (`analysis/balance_by_date.py`), and neither may shadow the
    other. This one requires the all-caps heading and the OZK service block."""
    other = document().replace("BALANCE BY DATE", "Balance By Date")
    assert not detect(other).claims


# ---------------------------------------------------------------------------
# The period, which this layout prints and checks against itself
# ---------------------------------------------------------------------------

def test_the_period_opens_the_day_after_the_previous_statement_closed():
    stmt = parse_bank_ozk_statement(document())
    assert (stmt.period_start, stmt.period_end) == ("2026-02-01", "2026-02-28")
    assert stmt.days_in_period == 28


def test_a_printed_day_count_that_contradicts_the_two_as_of_dates_refuses():
    """The document states both endpoints and then states the length; where the
    two disagree the period is not printed evidence and nothing is published."""
    assert parse_bank_ozk_statement(document(block=summary(days=27))) is None


def test_an_inverted_pair_of_as_of_dates_refuses():
    assert parse_bank_ozk_statement(
        document(block=summary(previous_as_of="03/31/26", current_as_of="02/28/26", days=28))
    ) is None


# ---------------------------------------------------------------------------
# The solve — the card
# ---------------------------------------------------------------------------

def test_the_printed_credit_count_decides_a_day_the_balances_do_not():
    """Two credits: the 3.00 row is the credit and 1.00 + 2.00 are debits."""
    stmt = parse_bank_ozk_statement(document())
    assert stmt is not None
    assert [(t.amount, t.direction) for t in stmt.transactions] == [
        (3.00, "credit"), (-1.00, "debit"), (-2.00, "debit"), (10.00, "credit"),
    ]


def test_the_same_balances_and_a_different_printed_count_give_the_other_answer():
    """THE proof that the count is load-bearing rather than decorative.

    Identical balances, identical rows, identical totals — only the printed
    COUNTS differ, and the ledger comes out inverted on three rows. A reader
    that ignored the counts would have to pick one of these at random.
    """
    stmt = parse_bank_ozk_statement(document(block=summary(credits_count=3, debits_count=1)))
    assert stmt is not None
    assert [(t.amount, t.direction) for t in stmt.transactions] == [
        (-3.00, "debit"), (1.00, "credit"), (2.00, "credit"), (10.00, "credit"),
    ]


def test_a_day_the_printed_count_cannot_separate_is_refused():
    """Two equal amounts on a zero-step day: both assignments credit exactly
    one row, so the cross-day constraint cannot choose and neither may this
    reader. A refusal is an answer."""
    rows = (
        "OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS "
        "02/02 SAMPLE ALPHA 1.00 02/02 SAMPLE BETA 1.00 02/03 SAMPLE DELTA 10.00\n"
    )
    block = summary(credits_count=2, credits="11.00", debits_count=1, debits="1.00")
    assert parse_bank_ozk_statement(document(block=block, rows=rows)) is None


def test_a_day_whose_step_no_assignment_reproduces_is_refused():
    assert parse_bank_ozk_statement(
        document(grid=GRID.replace("02/02 100.00", "02/02 100.50"))
    ) is None


def test_cheques_are_known_debits_and_seed_their_day():
    checks = (
        "CHECK TRANSACTIONS SERIAL DATE AMOUNT SERIAL DATE AMOUNT "
        "1000 02/02 1.00 1001* 02/02 2.00\n"
    )
    rows = (
        "OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS "
        "02/02 SAMPLE ALPHA 3.00 02/03 SAMPLE DELTA 10.00\n"
    )
    stmt = parse_bank_ozk_statement(document(checks=checks, rows=rows))
    assert stmt is not None
    assert sorted((t.amount, t.direction) for t in stmt.transactions) == [
        (-2.00, "debit"), (-1.00, "debit"), (3.00, "credit"), (10.00, "credit"),
    ]


def test_the_summary_arithmetic_is_the_fail_fast():
    assert parse_bank_ozk_statement(document(block=summary(current="110.01"))) is None


def test_the_captured_row_count_must_be_the_two_printed_counts():
    """A ZERO-amount extra row, deliberately: every other gate still passes on
    it — the day's step is unchanged and both printed totals still reproduce —
    so this check is the only thing standing between a phantom row and
    publication."""
    extra = ROWS.rstrip("\n") + " 02/03 SAMPLE EPSILON 0.00\n"
    assert parse_bank_ozk_statement(document(rows=extra)) is None


def test_the_grid_must_close_on_the_printed_current_balance():
    assert parse_bank_ozk_statement(document(grid=GRID.replace("02/03 110.00", "02/03 110.01"))) is None


def test_a_row_dated_on_a_day_the_grid_does_not_carry_is_refused():
    rows = ROWS.replace("02/03 SAMPLE DELTA", "02/04 SAMPLE DELTA")
    assert parse_bank_ozk_statement(document(rows=rows)) is None


def test_an_off_grid_row_is_refused_and_never_silently_dropped():
    """The test above is also caught by the row-count check once the row goes
    missing, so it does not prove this gate. This one does: the off-grid row
    carries a ZERO amount, so DROPPING it leaves the row count, both totals and
    every day's step intact and the document would publish. Only refusing
    catches it. (W3 §FROSTOZK's mutation table, mutant O4.)"""
    rows = ROWS.rstrip("\n") + " 02/04 SAMPLE EPSILON 0.00\n"
    block = summary(credits_count=2, debits_count=3)
    assert parse_bank_ozk_statement(document(block=block, rows=rows)) is None


def test_a_date_shaped_token_the_period_cannot_place_is_never_silently_dropped():
    """The same shape one level down. A token the period cannot place, printed
    with an amount after it, would become a row the reader silently loses if it
    were skipped rather than refused. (Mutant O15.)"""
    rows = ROWS.rstrip("\n") + " 12/25 SAMPLE OUT OF PERIOD 99.00\n"
    assert parse_bank_ozk_statement(document(rows=rows)) is None


def test_a_grid_day_with_no_rows_is_refused():
    grid = GRID.replace("02/03 110.00", "02/03 110.00 02/05 110.00")
    assert parse_bank_ozk_statement(document(grid=grid)) is None


def test_a_grid_date_printed_twice_with_two_values_is_refused():
    grid = GRID.replace("02/03 110.00", "02/03 110.00 02/03 111.00")
    assert parse_bank_ozk_statement(document(grid=grid)) is None


def test_a_negative_grid_balance_prints_its_minus_in_front():
    rows = (
        "OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS "
        "02/02 SAMPLE ALPHA 110.00 02/03 SAMPLE DELTA 120.00\n"
    )
    block = summary(credits_count=1, credits="120.00", debits_count=1,
                    debits="110.00", current="110.00")
    grid = GRID.replace("02/02 100.00", "02/02 -10.00")
    stmt = parse_bank_ozk_statement(document(block=block, rows=rows, grid=grid))
    assert stmt is not None
    assert [e.balance for e in stmt.stated_daily_balances] == [-10.00, 110.00]
    assert [t.direction for t in stmt.transactions] == ["debit", "credit"]


# ---------------------------------------------------------------------------
# Splitting a flattened table into rows — the confirmed traps
# ---------------------------------------------------------------------------

def _one_row(description: str) -> str:
    return (
        "OTHER TRANSACTIONS DATE DESCRIPTION DEBITS CREDITS "
        f"02/02 SAMPLE ALPHA 3.00 02/02 SAMPLE BETA 1.00 02/02 SAMPLE GAMMA 2.00 "
        f"02/03 {description}\n"
    )


@pytest.mark.parametrize(
    "description",
    [
        # A date-shaped token whose day field is three digits long.
        "SAMPLE INVOICE 03/2026 10.00",
        # A six-figure reference whose first pair is not a month.
        "SAMPLE WIRE REF OF 26/04/01 10.00",
        # A trace number printed AFTER the amount, with no decimal.
        "SAMPLE POS PURCHASE 10.00 000000",
        # A wrapped description continuation printed after the amount.
        "SAMPLE TRANSFER 10.00 via Online",
        # An amount QUOTED inside the description, marked by the symbol the
        # money column never carries. A first-amount rule would take it.
        "SAMPLE CHK# 0000 AMT $1,800.00, SAMPLE FEE 10.00",
        # The same quoting, AFTER the row's own amount: a last-amount rule
        # without the mask would take the quoted figure instead.
        "SAMPLE FEE 10.00 REVERSAL OF $1,800.00",
    ],
)
def test_a_row_survives_the_split_and_amount_traps(description):
    stmt = parse_bank_ozk_statement(document(rows=_one_row(description)))
    assert stmt is not None
    assert len(stmt.transactions) == 4
    assert stmt.transactions[-1].amount == 10.00


def test_the_rows_amount_is_the_last_money_token_and_the_archive_never_says():
    """A DOCUMENTED choice, pinned as one rather than reported as measured.

    After the quoted-amount mask, not one row of the eight archive documents
    carries two money tokens, so the archive cannot distinguish `first` from
    `last` at all. `last` is chosen because every confirmed trailing trap
    carries no decimals (a trace number) or no amount (a wrapped description),
    while the one confirmed LEADING extra is an amount quoted in the
    description — so a leading extra is the shape that occurs and a trailing
    one is not. If a printing ever puts the row's own amount first, this test
    is what will have to change, and deliberately.
    """
    stmt = parse_bank_ozk_statement(document(rows=_one_row("SAMPLE MEMO 1.00 SAMPLE TAIL 10.00")))
    assert stmt is not None
    assert stmt.transactions[-1].amount == 10.00


def test_a_date_token_the_period_cannot_place_refuses_the_document():
    """Not treated as description text: it may be a row whose date was mangled,
    and this reader would rather decline than lose one."""
    assert parse_bank_ozk_statement(document(rows=_one_row("SAMPLE MEMO 12/25 10.00"))) is None


def test_a_row_with_no_readable_amount_refuses_the_document():
    assert parse_bank_ozk_statement(document(rows=_one_row("SAMPLE MEMO WITH NO AMOUNT"))) is None


# ---------------------------------------------------------------------------
# What it publishes
# ---------------------------------------------------------------------------

def test_it_publishes_the_account_from_two_printings_that_agree():
    stmt = parse_bank_ozk_statement(document())
    assert (stmt.bank, stmt.account_number) == ("Bank OZK", "000000")
    assert stmt.account_name == "SAMPLE CHECKING"


def test_a_second_account_number_refuses_the_document():
    """L-1: this schema publishes one account, so two is a refusal."""
    assert parse_bank_ozk_statement(document(tail="Account Number: 000001\n")) is None


def test_the_daily_grid_is_published_as_the_bank_printed_it():
    stmt = parse_bank_ozk_statement(document())
    assert [(e.date, e.balance) for e in stmt.stated_daily_balances] == [
        ("2026-02-02", 100.00), ("2026-02-03", 110.00),
    ]


def test_the_bank_printed_average_is_evidence_and_carries_its_own_label():
    tail = "AVERAGE LEDGER BALANCE:            105.00\nINTEREST PAID THIS PERIOD:   0.50\n"
    stmt = parse_bank_ozk_statement(document(tail=tail))
    assert stmt.bank_reported_average_balance == 105.00
    assert stmt.bank_reported_average_label == "AVERAGE LEDGER BALANCE"
    assert stmt.stated_interest_paid == 0.50


def test_the_currency_is_the_institution_default():
    stmt = parse_bank_ozk_statement(document())
    assert (stmt.currency, stmt.currency_source) == ("USD", "institution_default")


def test_a_document_with_no_ledger_is_not_a_statement():
    assert parse_bank_ozk_statement(SERVICE + HEADER + summary() + "BALANCE BY DATE\n") is None

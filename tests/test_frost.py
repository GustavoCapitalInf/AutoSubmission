"""W3 §FROSTOZK — the Frost mainframe printing.

EVERY FIGURE, NAME, ACCOUNT NUMBER AND DATE IN THIS FILE IS INVENTED. No
archive content appears here; the fixtures are assembled from the printing's
STRUCTURE — its rules, its column heads and its box — with numbers chosen to
make each gate's failure visible.
"""
from __future__ import annotations

import pytest

from analysis.frost import DETECTION_MARKERS, detect, parse_frost_statement
from analysis.parser_registry import score_markers

# ---------------------------------------------------------------------------
# The fixture, assembled from parts so a gate can be mutated in isolation
# ---------------------------------------------------------------------------

MASTHEAD = (
    "FOR INFORMATION CALL\n"
    "000-000-0000 OR 1-800-513-7678\n"
    "P.O. Box 0000 Example City, Texas 00000 Member FDIC\n"
    "STATEMENT ISSUED\n"
    "02-27-2026\n"
    "Page 1 of 1\n"
)

BANNER = (
    "FROST BUSINESS CHECKING :  ACCOUNT NO.  00 0000000 "
    "___________________________________________________\n"
)

BOX_LINE = (
    "|          DEPOSITS           |       WITHDRAWALS           | "
    "|_____________________________|_____________________________|\n"
)

LABEL_LINE = (
    "BALANCE LAST STATEMENT    |  NO.  |         AMOUNT      |  NO.  |"
    "         AMOUNT      |   BALANCE THIS STATEMENT "
    "___________________________________________________\n"
)

#: opening 1,000.00 · 3 deposits totalling 1,500.10 · withdrawals printed as
#: ONE row but summing 700.20 across TWO — the scope difference this family's
#: count-semantics entry is about — · closing 1,799.90.
VALUE_LINE = (
    "|       |                     |       |                     | "
    "1,000.00              3            1,500.10         1            700.20"
    "                 1,799.90 ______________________________\n"
)

DEPOSITS = (
    "--------------------------------------- DEPOSITS/CREDITS "
    "-------------------------------------------\n"
    "DATE      TRANSACTION                         AMOUNT     |  "
    "DATE      TRANSACTION                         AMOUNT\n"
    "|\n"
    "02-02     SAMPLE CREDIT ROW                 500.00     |  "
    "02-03     SAMPLE CREDIT ROW               1,000.00\n"
    "DATE             AMOUNT     TRANSACTION              DESCRIPTION\n"
    "02-04               .10     SAMPLE ELECTRONIC        SAMPLE MEMO\n"
)

WITHDRAWALS = (
    "-------------------------------------  OTHER WITHDRAWALS/DEBITS  "
    "-----------------------------------\n"
    "DATE             AMOUNT     TRANSACTION              DESCRIPTION\n"
    "02-05            700.00     SAMPLE DEBIT             SAMPLE MEMO\n"
    "02-06               .20     SERVICE CHARGE/FEE       SAMPLE CHARGE\n"
)

DAILY = (
    "---------------------------------------- DAILY BALANCE "
    "---------------------------------------------\n"
    "DATE         BALANCE                 |  DATE         BALANCE"
    "                 |  DATE         BALANCE\n"
    "|                                       |\n"
    "01-30        1,000.00                 | 02-04        2,500.10"
    "                 | 02-06        1,799.90\n"
    "02-02        1,500.00                 | 02-05        1,800.10\n"
    "02-03        2,500.00\n"
)

FOOTER = "Please examine your bank statement upon receipt and report any differences.\n"


def document(
    *,
    masthead: str = MASTHEAD,
    banner: str = BANNER,
    box: str = BOX_LINE,
    label: str = LABEL_LINE,
    values: str = VALUE_LINE,
    deposits: str = DEPOSITS,
    withdrawals: str = WITHDRAWALS,
    daily: str = DAILY,
) -> str:
    return (
        masthead + banner + box + label + values + deposits + withdrawals + daily + FOOTER
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_it_claims_its_own_printing():
    assert detect(document()).claims


@pytest.mark.parametrize(
    "removed",
    [
        "1-800-513-7678",
        "FROST BUSINESS CHECKING",
        "BALANCE LAST STATEMENT",
        "DEPOSITS           |       WITHDRAWALS",
    ],
)
def test_every_required_marker_is_load_bearing(removed):
    """Each one removed, the registration must not claim."""
    assert not detect(document().replace(removed, "XXXX")).claims


def test_the_marker_set_is_three_required_and_one_corroborating():
    kinds = sorted(marker.kind for marker in DETECTION_MARKERS)
    assert kinds == ["corroborating", "required", "required", "required"]
    assert score_markers(DETECTION_MARKERS, document()).score == 1.0


# ---------------------------------------------------------------------------
# What it publishes
# ---------------------------------------------------------------------------

def test_it_reads_the_strip_the_sections_and_the_grid():
    stmt = parse_frost_statement(document())
    assert stmt is not None
    assert stmt.bank == "Frost Bank"
    assert stmt.account_number == "00 0000000"
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.00, 1799.90)
    assert (stmt.stated_total_credits, stmt.stated_total_debits) == (1500.10, 700.20)
    assert (stmt.stated_credit_count, stmt.stated_debit_count) == (3, 1)
    assert [t.amount for t in stmt.transactions] == [500.00, 1000.00, 0.10, -700.00, -0.20]
    assert [t.direction for t in stmt.transactions] == [
        "credit", "credit", "credit", "debit", "debit",
    ]


def test_the_two_up_deposit_block_is_two_transactions_not_one():
    """The pipe packs two logical rows onto one physical line."""
    stmt = parse_frost_statement(document())
    assert [t.date for t in stmt.transactions][:2] == ["2026-02-02", "2026-02-03"]


def test_a_sub_dollar_amount_prints_with_no_integer_part():
    """`.10` is ten cents, not an unreadable token and not a dropped row."""
    stmt = parse_frost_statement(document())
    assert 0.10 in [t.amount for t in stmt.transactions]
    assert stmt.stated_credit_count == 3


def test_the_daily_grid_is_sorted_and_carries_the_prior_cycle_cell():
    stmt = parse_frost_statement(document())
    dates = [entry.date for entry in stmt.stated_daily_balances]
    assert dates == sorted(dates)
    assert dates[0] == "2026-01-30"
    assert stmt.stated_daily_balances[0].balance == 1000.00
    assert stmt.stated_daily_balances[-1].balance == 1799.90


def test_the_period_is_not_published_because_none_is_printed():
    """The ADB doctrine averages over the PRINTED period, and there is none.

    `analysis/adb.py` then withholds the average through its required
    `statement_period_dates_valid` check, which is the doctrine enforced rather
    than a defect. Pinned so a later cell cannot quietly derive one.
    """
    stmt = parse_frost_statement(document())
    assert stmt.period_start is None and stmt.period_end is None
    assert stmt.days_in_period is None


def test_no_average_and_no_interest_are_invented():
    stmt = parse_frost_statement(document())
    assert stmt.bank_reported_average_balance is None
    assert stmt.stated_interest_paid is None


def test_the_currency_is_the_institution_default():
    stmt = parse_frost_statement(document())
    assert (stmt.currency, stmt.currency_source) == ("USD", "institution_default")


# ---------------------------------------------------------------------------
# The summary strip is bound by its header — the card's central gate
# ---------------------------------------------------------------------------

def test_the_box_line_decides_which_side_comes_first():
    """Swapping the two side names swaps the roles, so the strip stops closing.

    This is the gate that makes the binding POSITIONAL-BY-EVIDENCE rather than
    positional-by-assumption: the same six figures, read under a box that
    declares the other order, are refused instead of published.
    """
    swapped = BOX_LINE.replace("DEPOSITS", "TEMP").replace("WITHDRAWALS", "DEPOSITS")
    swapped = swapped.replace("TEMP", "WITHDRAWALS")
    assert parse_frost_statement(document(box=swapped)) is None


def test_an_unrecognised_label_line_is_refused():
    assert parse_frost_statement(document(label=LABEL_LINE.replace("NO.", "CNT"))) is None


def test_a_count_slot_carrying_cents_is_refused():
    """The type check, independent of the arithmetic."""
    mangled = VALUE_LINE.replace("              3            ", "         3.00            ")
    assert parse_frost_statement(document(values=mangled)) is None


def test_a_strip_whose_arithmetic_does_not_close_is_refused():
    assert parse_frost_statement(document(values=VALUE_LINE.replace("1,799.90", "1,799.91"))) is None


def test_the_strip_arithmetic_catches_what_the_totals_and_the_grid_cannot():
    """The test above is caught by the grid-ends check too, so it does not
    prove this gate is load-bearing. This one does: the printed deposit TOTAL
    moves and a matching deposit row moves with it, so the captured totals
    still reproduce the printed ones and both grid ends are untouched — and the
    strip stops closing on itself. Only this check sees it. (W3 §FROSTOZK's
    mutation table, mutant F4.)"""
    louder = VALUE_LINE.replace("1,500.10", "1,600.10")
    extra = DEPOSITS + "02-04            100.00     SAMPLE ELECTRONIC        SAMPLE MEMO\n"
    assert parse_frost_statement(document(values=louder, deposits=extra)) is None


def test_a_value_row_with_the_wrong_number_of_figures_is_refused():
    assert parse_frost_statement(document(values=VALUE_LINE.replace(" 700.20", " 700.20  7.00"))) is None


# ---------------------------------------------------------------------------
# Section structure
# ---------------------------------------------------------------------------

def test_an_unknown_column_head_is_refused():
    assert parse_frost_statement(
        document(withdrawals=WITHDRAWALS.replace("DATE             AMOUNT     TRANSACTION",
                                                 "DATE             SUBTOTAL   TRANSACTION"))
    ) is None


def test_a_line_inside_a_section_that_is_not_a_row_is_refused():
    """Completeness: an unmodelled printing fails the document closed."""
    junked = WITHDRAWALS + "SAMPLE UNMODELLED LINE\n"
    assert parse_frost_statement(document(withdrawals=junked)) is None


def test_a_captured_credit_total_that_misses_the_printed_one_is_refused():
    dropped = DEPOSITS.replace("02-04               .10     SAMPLE ELECTRONIC        SAMPLE MEMO\n", "")
    assert parse_frost_statement(document(deposits=dropped)) is None


def test_a_captured_debit_total_that_misses_the_printed_one_is_refused():
    dropped = WITHDRAWALS.replace("02-06               .20     SERVICE CHARGE/FEE       SAMPLE CHARGE\n", "")
    assert parse_frost_statement(document(withdrawals=dropped)) is None


def test_the_grid_must_open_on_the_printed_opening_balance():
    assert parse_frost_statement(document(daily=DAILY.replace("01-30        1,000.00", "01-30        1,000.01"))) is None


def test_the_grid_must_close_on_the_printed_closing_balance():
    assert parse_frost_statement(document(daily=DAILY.replace("02-06        1,799.90", "02-06        1,799.91"))) is None


def test_a_document_with_no_grid_is_refused():
    assert parse_frost_statement(document(daily="")) is None


def test_a_document_with_no_ledger_is_not_a_statement():
    assert parse_frost_statement(MASTHEAD + BANNER + BOX_LINE + LABEL_LINE + VALUE_LINE) is None


# ---------------------------------------------------------------------------
# Dates, and the two printings that make them hard
# ---------------------------------------------------------------------------

def test_a_month_after_the_cycle_month_belongs_to_the_year_before():
    """A January cycle whose grid opens on the previous December."""
    january = document(
        masthead=MASTHEAD.replace("02-27-2026", "01-30-2026"),
        deposits=DEPOSITS.replace("02-0", "01-0"),
        withdrawals=WITHDRAWALS.replace("02-0", "01-0"),
        daily=DAILY.replace("01-30        1,000.00", "12-31        1,000.00").replace("02-0", "01-0"),
    )
    stmt = parse_frost_statement(january)
    assert stmt is not None
    assert stmt.stated_daily_balances[0].date == "2025-12-31"
    assert stmt.stated_daily_balances[-1].date == "2026-01-06"


def test_an_overdrawn_grid_cell_prints_its_minus_after_the_digits():
    """`1,234.56- OD`. One cell in one archive document has this form, and a
    reader that dropped the trailing minus would invert a day's balance."""
    overdrawn = document(
        values=VALUE_LINE.replace("1,799.90 ___", "1,799.90 ___"),
        daily=DAILY.replace("02-05        1,800.10", "02-05        1,800.10- OD"),
    )
    stmt = parse_frost_statement(overdrawn)
    assert stmt is not None
    assert [e.balance for e in stmt.stated_daily_balances if e.date == "2026-02-05"] == [-1800.10]


def test_two_different_statement_issued_dates_refuse_the_document():
    assert parse_frost_statement(document() + "STATEMENT ISSUED   03-31-2026\n") is None


def test_two_different_account_banners_refuse_the_document():
    second = BANNER.replace("00 0000000", "00 0000001")
    assert parse_frost_statement(document() + second) is None


def test_a_repeated_banner_that_agrees_is_free_corroboration():
    continued = BANNER.replace(
        "___________________________________________________", "(CONTINUED) ______"
    )
    stmt = parse_frost_statement(document() + continued)
    assert stmt is not None and stmt.account_number == "00 0000000"


# ---------------------------------------------------------------------------
# Count semantics, end to end through the pipeline
# ---------------------------------------------------------------------------

def test_the_credit_count_check_is_live_and_can_fail():
    """The reader gates on the printed TOTALS and never on a printed COUNT, so
    the platform's credit-count check is a real defect detector on this family
    rather than a tautology. Proved by constructing the defect: one deposit row
    split into two halves of the same total. The money still reconciles to the
    cent, so nothing else notices — and the count check raises its flag.
    """
    from analysis.pipeline import analyze_markdown

    split = DEPOSITS.replace(
        "02-04               .10     SAMPLE ELECTRONIC        SAMPLE MEMO\n",
        "02-04               .04     SAMPLE ELECTRONIC        SAMPLE MEMO\n"
        "02-04               .06     SAMPLE ELECTRONIC        SAMPLE MEMO\n",
    )
    report = analyze_markdown(document(deposits=split), parse_mode="deterministic")
    assert report.statement.bank == "Frost Bank"
    assert report.reconciliation.captured_credit_count == 4
    assert report.reconciliation.expected_credit_count == 3
    assert report.reconciliation.credit_coverage == 1.0
    assert "credit_count_mismatch" in report.integrity.flags


def test_the_debit_count_scope_difference_raises_no_flag():
    """The printed withdrawal figure excludes the `SERVICE CHARGE/FEE` row this
    reader posts, so the two sides count different sets. `count_semantics`
    declares the direction incomparable and the platform stays silent instead
    of manufacturing a mismatch on a ledger that reconciles to the cent."""
    from analysis.pipeline import analyze_markdown

    report = analyze_markdown(document(), parse_mode="deterministic")
    assert report.reconciliation.captured_debit_count == 2
    assert report.reconciliation.expected_debit_count == 1
    assert report.reconciliation.debit_coverage == 1.0
    assert report.integrity.flags == []


def test_the_average_is_withheld_because_no_period_is_printed():
    """The ADB doctrine's own gate, exercised end to end: this family publishes
    a complete dated ledger and the platform still refuses the one metric it
    cannot ground in a printed period."""
    from analysis.pipeline import analyze_markdown

    report = analyze_markdown(document(), parse_mode="deterministic")
    assert report.metrics.average_daily_balance is None
    assert report.metrics.adb.validations["statement_period_dates_valid"] is False


# ---------------------------------------------------------------------------
# It does not claim other printings
# ---------------------------------------------------------------------------

def test_a_bare_mention_of_the_bank_is_not_a_statement():
    assert not detect("Transfer to FROST BUSINESS CHECKING account\n").claims


def test_a_grid_day_printed_twice_with_two_values_is_refused():
    """The grid's two ENDS are checked against the strip; nothing else checks a
    cell in the middle, so a day printed twice two different ways would
    otherwise publish two balances for one date and let `analysis/adb.py`
    choose. No archive document of this family prints a duplicate, so this
    closes a hole rather than describing one."""
    doubled = DAILY.replace("02-04        2,500.10", "02-04        2,500.10 | 02-04        2,500.11")
    assert parse_frost_statement(document(daily=doubled)) is None


def test_a_grid_day_printed_twice_with_the_same_value_is_corroboration():
    doubled = DAILY.replace("02-04        2,500.10", "02-04        2,500.10 | 02-04        2,500.10")
    stmt = parse_frost_statement(document(daily=doubled))
    assert stmt is not None
    dates = [entry.date for entry in stmt.stated_daily_balances]
    assert dates == sorted(set(dates))

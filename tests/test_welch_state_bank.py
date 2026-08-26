"""Welch State Bank — W3 §WELCH.

EVERY FIGURE, NAME, ACCOUNT NUMBER, CHECK NUMBER AND DATE IN THIS FILE IS
INVENTED. Nothing here is copied from a document: the archive is gitignored by
design and the wave's privacy rule forbids archive content in tracked source,
so the fixtures below are a synthetic statement built to the template's SHAPE.
They are the same invented figures the module docstring quotes.

The invented statement closes on all four printed oracles at once, which is
what makes the mutation tests below meaningful — each one breaks exactly one
of them and asserts the reader refuses:

    beginning              1,000.00
    2 credits                300.00 + 200.00 = 500.00
    3 debits         100.00 + 50.00 + 100.00 = 250.00   (the last is a check)
    ending                 1,000.00 + 500.00 - 250.00 = 1,250.00
    grid       06/01 1,000.00 · 06/02 1,300.00 · 06/03 1,200.00
               06/04 1,100.00 · 06/05 1,300.00 · 06/09 1,250.00
"""
from __future__ import annotations

import pytest

# Importing the entries module is what POPULATES the registry; this file
# asserts the registration and the module are one detector, so it needs a
# loaded registry even when run alone.
from analysis import parser_registry_entries  # noqa: F401
from analysis.parser_registry import by_id
from analysis.welch_state_bank import (
    WELCH_DETECTION_MARKERS,
    detect,
    parse_welch_state_bank_statement,
)

MASTHEAD = (
    "Direct Inquires To:\n"
    "000-000-0000 fax: 000-000-0001\n"
    "000-000-0002 fax: 000-000-0003\n"
    "000-000-0004 fax: 000-000-0005\n"
    "PO Box 1 Welch, OK 00000\n"
    "PO Box 2 Sampleville, OK 00001\n"
    "ACCOUNT NUMBER 1234567\n"
    "STATEMENT DATES 06/01/26-06/30/26\n"
    "PAGE 1 of 2\n"
    "Sample Business Checking\n"
)
SUMMARY = (
    "Account Number 1234567 Beginning Balance 1,000.00 "
    "Days in Statement Period 30 "
    "2 Deposits/Other Credits 500.00 "
    "3 Checks/Other Debits 250.00 Ending Balance 1,250.00\n"
)
CREDITS = (
    "Deposits/Other Credits\n"
    "Date Description Amount Sample Credit One 06/02 300.00 "
    "Sample Credit Two 06/05 200.00\n"
)
DEBITS = (
    "Other Debits\n"
    "Date Description Amount Sample Debit One 06/03 100.00 "
    "Sample Debit Two 06/09 50.00\n"
)
CHECKS = (
    "Checks Cleared\n"
    "Listed in numerical order\n"
    "Date Check Amount Date Check Amount 6/04 1001 100.00\n"
    "(*) indicates gap in sequence\n"
)
GRID = (
    "Daily Ending Balance\n"
    "DATE BALANCE DATE BALANCE DATE BALANCE "
    "06/01 1,000.00 06/02 1,300.00 06/03 1,200.00 "
    "06/04 1,100.00 06/05 1,300.00 06/09 1,250.00\n"
)


def document(
    *,
    masthead: str = MASTHEAD,
    summary: str = SUMMARY,
    credits: str = CREDITS,
    debits: str = DEBITS,
    checks: str = CHECKS,
    grid: str = GRID,
) -> str:
    return masthead + summary + credits + debits + checks + grid


def parsed(**kwargs: str):
    return parse_welch_state_bank_statement(document(**kwargs))


# ---------------------------------------------------------------------------
# The whole document, read
# ---------------------------------------------------------------------------

def test_the_invented_statement_reads_end_to_end():
    stmt = parsed()
    assert stmt is not None
    assert stmt.bank == "Welch State Bank"
    assert stmt.account_number == "1234567"
    assert (stmt.period_start, stmt.period_end) == ("2026-06-01", "2026-06-30")
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.00, 1250.00)
    assert (stmt.stated_total_credits, stmt.stated_total_debits) == (500.00, 250.00)
    assert (stmt.stated_credit_count, stmt.stated_debit_count) == (2, 3)
    assert stmt.days_in_period == 30
    assert len(stmt.transactions) == 5


def test_the_direction_of_a_row_comes_from_its_banner_and_not_from_a_glyph():
    stmt = parsed()
    assert stmt is not None
    by_direction = {"credit": [], "debit": []}
    for transaction in stmt.transactions:
        by_direction[transaction.direction].append(transaction.amount)
    assert sorted(by_direction["credit"]) == [200.00, 300.00]
    assert sorted(by_direction["debit"]) == [-100.00, -100.00, -50.00]


def test_a_description_is_the_text_printed_before_its_own_anchor():
    """DESC-ATTRIB, on the shape that would break it: two rows on one line."""
    stmt = parsed()
    assert stmt is not None
    described = {t.date: t.description for t in stmt.transactions}
    assert described["2026-06-02"] == "Sample Credit One"
    assert described["2026-06-05"] == "Sample Credit Two"
    assert described["2026-06-03"] == "Sample Debit One"
    assert described["2026-06-09"] == "Sample Debit Two"


def test_the_cleared_check_is_a_debit_the_printed_debit_count_includes():
    stmt = parsed()
    assert stmt is not None
    checks = [t for t in stmt.transactions if t.date == "2026-06-04"]
    assert [(t.direction, t.amount, t.description) for t in checks] == [
        ("debit", -100.00, "Check 1001")
    ]


def test_the_daily_grid_is_published_as_the_banks_own_dated_evidence():
    stmt = parsed()
    assert stmt is not None
    assert [(d.date, d.balance) for d in stmt.stated_daily_balances] == [
        ("2026-06-01", 1000.00),
        ("2026-06-02", 1300.00),
        ("2026-06-03", 1200.00),
        ("2026-06-04", 1100.00),
        ("2026-06-05", 1300.00),
        ("2026-06-09", 1250.00),
    ]


def test_the_product_line_is_read_positionally_and_not_from_a_memorized_name():
    stmt = parsed()
    assert stmt is not None
    assert stmt.account_name == "Sample Business Checking"
    # A DIFFERENT product on the same template still publishes its own product,
    # which is the property a memorized product string would not have.
    other = parsed(masthead=MASTHEAD.replace("Sample Business Checking", "Another Product"))
    assert other is not None
    assert other.account_name == "Another Product"


def test_a_line_carrying_a_digit_is_not_published_as_a_product_line():
    stmt = parsed(masthead=MASTHEAD.replace("Sample Business Checking\n", ""))
    assert stmt is not None
    assert stmt.account_name is None


def test_the_currency_is_asserted_from_the_institution_and_says_so():
    stmt = parsed()
    assert stmt is not None
    assert (stmt.currency, stmt.currency_source) == ("USD", "institution_default")


def test_no_average_service_charge_or_nsf_count_is_invented():
    stmt = parsed()
    assert stmt is not None
    assert stmt.bank_reported_average_balance is None
    assert stmt.bank_reported_average_label is None
    assert stmt.stated_service_charge is None
    assert stmt.stated_nsf_count is None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_every_marker_is_required_and_all_of_them_together_claim():
    assert {marker.kind for marker in WELCH_DETECTION_MARKERS} == {"required"}
    assert detect(document()).claims


def test_the_home_office_po_box_is_required_to_claim():
    without = document(masthead=MASTHEAD.replace("PO Box 1 Welch, OK 00000\n", ""))
    assert not detect(without).claims
    assert parse_welch_state_bank_statement(without) is None


def test_a_two_rung_contact_ladder_is_not_a_branch_ladder():
    """The rung count is the marker: two numbers is a letterhead, not this
    bank's six-branch masthead."""
    two_rungs = MASTHEAD.replace("000-000-0004 fax: 000-000-0005\n", "")
    assert not detect(document(masthead=two_rungs)).claims
    assert detect(document()).claims


def test_the_ladder_keyword_probe_cannot_change_the_answer():
    """The ladder marker runs a cheap literal probe before its pattern, purely
    to keep this registration's share of the full-registry detect sweep down.
    The probe carries the same case-insensitivity as the pattern, so a printing
    that capitalises the keyword is claimed exactly as one that does not."""
    shouted = MASTHEAD.replace("fax:", "FAX:")
    assert "FAX:" in shouted
    assert detect(document(masthead=shouted)).claims
    # And a masthead with the keyword but no rungs still does not claim.
    rungless = [line for line in MASTHEAD.splitlines() if "fax:" not in line]
    keyword_only = "\n".join([*rungless, "fax:", ""])
    assert not detect(document(masthead=keyword_only)).claims


def test_the_summary_grammar_is_required_at_detection_and_not_only_at_parse():
    """A printing with no counted summary box is one this reader cannot prove
    complete, so it must not claim it and strand it."""
    without = document(summary="")
    assert not detect(without).claims


def test_the_registration_and_the_module_are_one_detector():
    registration = by_id("welch_state_bank")
    assert registration is not None
    assert registration.bank == "Welch State Bank"
    assert registration.detect(document()).score == detect(document()).score


def test_detection_does_not_depend_on_the_source_filename():
    named = "<!-- source: welch state bank.pdf -->\n" + document()
    anonymous = "<!-- source: 0000.pdf -->\n" + document()
    assert detect(named).claims and detect(anonymous).claims
    assert parse_welch_state_bank_statement(named) == parse_welch_state_bank_statement(
        anonymous
    )


# ---------------------------------------------------------------------------
# The summary box
# ---------------------------------------------------------------------------

def test_a_summary_that_does_not_close_refuses_the_document():
    assert parsed(summary=SUMMARY.replace("Ending Balance 1,250.00", "Ending Balance 1,250.01")) is None


def test_a_summary_printed_twice_with_two_readings_refuses_the_document():
    contradicting = SUMMARY + SUMMARY.replace(
        "Beginning Balance 1,000.00", "Beginning Balance 2,000.00"
    ).replace("Ending Balance 1,250.00", "Ending Balance 2,250.00")
    assert parsed(summary=contradicting) is None


def test_a_summary_printed_twice_identically_is_corroboration_and_is_accepted():
    assert parsed(summary=SUMMARY + SUMMARY) is not None


def test_a_masthead_account_the_summary_contradicts_refuses_the_document():
    assert parsed(masthead=MASTHEAD.replace("ACCOUNT NUMBER 1234567", "ACCOUNT NUMBER 7654321")) is None


def test_two_different_mastheads_refuse_the_document():
    doubled = MASTHEAD + "ACCOUNT NUMBER 7654321\n"
    assert parsed(masthead=doubled) is None


def test_a_period_that_ends_before_it_starts_refuses_the_document():
    assert parsed(masthead=MASTHEAD.replace("06/01/26-06/30/26", "06/30/26-06/01/26")) is None


def test_a_period_no_calendar_holds_refuses_instead_of_raising():
    assert parsed(masthead=MASTHEAD.replace("06/01/26-06/30/26", "06/31/26-06/30/26")) is None


def test_two_different_periods_refuse_the_document():
    doubled = MASTHEAD + "STATEMENT DATES 07/01/26-07/31/26\n"
    assert parsed(masthead=doubled) is None


# ---------------------------------------------------------------------------
# The complete-coverage oracle: the printed counts and totals
# ---------------------------------------------------------------------------

def test_a_dropped_credit_row_is_caught_by_the_printed_credit_count():
    short = CREDITS.replace(" Sample Credit Two 06/05 200.00", "")
    assert parsed(credits=short) is None


def test_a_dropped_debit_row_is_caught_by_the_printed_debit_count():
    short = DEBITS.replace(" Sample Debit Two 06/09 50.00", "")
    assert parsed(debits=short) is None


def test_ignoring_the_cleared_check_table_is_caught_by_the_printed_debit_count():
    """The failure mode the census measured on 14 of its 16 documents: a
    reader that never reads `Checks Cleared` is short one to five debits."""
    assert parsed(checks="") is None


def test_a_credit_count_the_rows_do_not_match_refuses_the_document():
    assert parsed(summary=SUMMARY.replace("2 Deposits", "3 Deposits")) is None


def test_a_debit_count_the_rows_do_not_match_refuses_the_document():
    assert parsed(summary=SUMMARY.replace("3 Checks", "4 Checks")) is None


def test_a_credit_total_the_rows_do_not_sum_to_refuses_the_document():
    """A swap that keeps the COUNT and the closing identity intact: the two
    credits change value and the ending balance is restated to match, so only
    the printed credit TOTAL can catch it."""
    swapped = CREDITS.replace("06/02 300.00", "06/02 310.00")
    assert parsed(credits=swapped) is None


def test_a_debit_total_the_rows_do_not_sum_to_refuses_the_document():
    swapped = DEBITS.replace("06/03 100.00", "06/03 110.00")
    assert parsed(debits=swapped) is None


def test_a_signed_ledger_amount_refuses_because_the_banner_states_direction():
    assert parsed(debits=DEBITS.replace("06/03 100.00", "06/03 100.00-")) is None


# ---------------------------------------------------------------------------
# The four printed oracles have ONE degree of redundancy, and these are the
# documents that separate them. See `tools/welch_mutation_table.py`: with the
# per-direction COUNTS and the daily grid held fixed, the closing identity, the
# two printed TOTALS and the replay's arrival at the printed ending balance are
# four constraints of which any three imply the fourth. So no single one of
# them can be isolated by any document — and a PAIR can, which is what these
# two fixtures do.
# ---------------------------------------------------------------------------

#: One credit and one debit ON THE SAME DAY, so that overstating both by the
#: same amount leaves the day's NET — and therefore the whole daily grid, and
#: therefore the closing identity — untouched.
SUMMARY_ONE_EACH = (
    "Account Number 1234567 Beginning Balance 1,000.00 "
    "Days in Statement Period 30 "
    "1 Deposits/Other Credits 300.00 "
    "1 Checks/Other Debits 100.00 Ending Balance 1,200.00\n"
)
CREDITS_ONE_EACH = (
    "Deposits/Other Credits\n"
    "Date Description Amount Sample Credit One 06/03 300.00\n"
)
DEBITS_ONE_EACH = (
    "Other Debits\n"
    "Date Description Amount Sample Debit One 06/03 100.00\n"
)
GRID_ONE_EACH = (
    "Daily Ending Balance\n"
    "DATE BALANCE DATE BALANCE DATE BALANCE 06/01 1,000.00 06/03 1,200.00\n"
)


def one_each(*, credits: str = CREDITS_ONE_EACH, debits: str = DEBITS_ONE_EACH,
             grid: str = GRID_ONE_EACH, summary: str = SUMMARY_ONE_EACH):
    return parsed(summary=summary, credits=credits, debits=debits, checks="", grid=grid)


def test_the_one_each_control_document_reads():
    stmt = one_each()
    assert stmt is not None
    assert len(stmt.transactions) == 2


def test_two_compensating_overstatements_are_caught_only_by_the_printed_totals():
    """A credit and a debit on one day, each overstated by the same amount.

    Both printed COUNTS still match, the day's net is unchanged so every
    printed daily balance still replays, the walk still lands on the printed
    ending balance, and the printed summary still closes. The only evidence
    left is the two printed per-direction TOTALS, and they are what refuses it.
    """
    assert one_each(
        credits=CREDITS_ONE_EACH.replace("06/03 300.00", "06/03 350.00"),
        debits=DEBITS_ONE_EACH.replace("06/03 100.00", "06/03 150.00"),
    ) is None


def test_a_summary_that_does_not_close_is_refused_by_the_identity_either_way():
    """The other half of the pair: with the totals fixed, the closing identity
    and the replay's arrival at the printed ending balance are the SAME
    constraint read from two ends, and this document fails both."""
    assert one_each(
        summary=SUMMARY_ONE_EACH.replace("Ending Balance 1,200.00", "Ending Balance 1,200.01")
    ) is None


#: A day whose postings NET TO ZERO — the only shape on which a grid day
#: printed twice survives the per-day balance walk, because adding zero twice
#: lands on the same printed figure both times.
SUMMARY_ZERO_NET = (
    "Account Number 1234567 Beginning Balance 1,000.00 "
    "Days in Statement Period 30 "
    "1 Deposits/Other Credits 50.00 "
    "1 Checks/Other Debits 50.00 Ending Balance 1,000.00\n"
)
CREDITS_ZERO_NET = (
    "Deposits/Other Credits\n"
    "Date Description Amount Sample Credit One 06/03 50.00\n"
)
DEBITS_ZERO_NET = (
    "Other Debits\n"
    "Date Description Amount Sample Debit One 06/03 50.00\n"
)
GRID_ZERO_NET = (
    "Daily Ending Balance\n"
    "DATE BALANCE DATE BALANCE DATE BALANCE 06/01 1,000.00 06/03 1,000.00\n"
)


def test_the_zero_net_control_document_reads():
    stmt = parsed(summary=SUMMARY_ZERO_NET, credits=CREDITS_ZERO_NET,
                  debits=DEBITS_ZERO_NET, checks="", grid=GRID_ZERO_NET)
    assert stmt is not None
    assert len(stmt.stated_daily_balances) == 2


def test_a_grid_that_prints_one_day_twice_refuses_even_when_the_walk_survives():
    """The isolating document for the distinct-days rule: on a zero-net day the
    balance walk cannot notice the repeat, so only the rule itself refuses —
    and it must, because a repeated date would publish two `stated_daily_balances`
    entries for one calendar day."""
    assert parsed(
        summary=SUMMARY_ZERO_NET, credits=CREDITS_ZERO_NET, debits=DEBITS_ZERO_NET,
        checks="",
        grid=GRID_ZERO_NET.replace("06/03 1,000.00", "06/03 1,000.00 06/03 1,000.00"),
    ) is None


def test_a_posting_outside_the_period_refuses_even_when_the_grid_agrees():
    """The isolating document for the period bound: a posting dated after the
    printed period end, WITH a grid that prints that day too, so every other
    oracle closes on it. Only `iso_unique_in_period` refuses — and it must,
    because `analysis/adb.py` cannot compute a period average over a day the
    period does not contain."""
    assert parsed(
        summary=SUMMARY_ONE_EACH,
        credits=CREDITS_ONE_EACH.replace("06/03 300.00", "07/02 300.00"),
        debits=DEBITS_ONE_EACH,
        checks="",
        grid=(
            "Daily Ending Balance\n"
            "DATE BALANCE DATE BALANCE DATE BALANCE "
            "06/01 1,000.00 06/03 900.00 07/02 1,200.00\n"
        ),
    ) is None


# ---------------------------------------------------------------------------
# The whole-line rule
# ---------------------------------------------------------------------------

def test_page_furniture_between_two_ledger_lines_is_not_a_description():
    """The reprinted page header and the mail-sort control token this template
    prints mid-section are ignored, and — the point — the row AFTER them keeps
    its own description instead of inheriting theirs."""
    interrupted = (
        "Other Debits\n"
        "Date Description Amount Sample Debit One 06/03 100.00\n"
        "ACCOUNT NUMBER 1234567\n"
        "STATEMENT DATES 06/01/26-06/30/26\n"
        "PAGE 2 of 2\n"
        "SAMPLE 00XYZ 0000000 0000A00X.000\n"
        "Sample Debit Two 06/09 50.00\n"
    )
    stmt = parsed(debits=interrupted)
    assert stmt is not None
    described = {t.date: t.description for t in stmt.transactions}
    assert described["2026-06-09"] == "Sample Debit Two"


def test_text_left_over_after_the_last_ledger_anchor_refuses_the_document():
    trailing = DEBITS.rstrip("\n") + " Sample Debit Three\n"
    assert parsed(debits=trailing) is None


def test_a_ledger_anchor_with_no_description_refuses_the_document():
    undescribed = (
        "Other Debits\n"
        "Date Description Amount 06/03 100.00 Sample Debit Two 06/09 50.00\n"
    )
    assert parsed(debits=undescribed) is None


def test_text_between_two_printed_grid_pairs_refuses_the_document():
    intruding = GRID.replace("06/03 1,200.00 06/04", "06/03 1,200.00 Number: 9 06/04")
    assert parsed(grid=intruding) is None


def test_text_between_two_printed_check_pairs_refuses_the_document():
    intruding = CHECKS.replace(
        "Date Check Amount Date Check Amount 6/04 1001 100.00",
        "Date Check Amount Date Check Amount 6/04 1001 100.00 stray",
    )
    assert parsed(checks=intruding) is None


def test_a_gap_marked_check_number_is_read_and_its_marker_is_not_the_amount():
    starred = CHECKS.replace("6/04 1001 100.00", "6/04 1001* 100.00")
    stmt = parsed(checks=starred)
    assert stmt is not None
    assert [t.description for t in stmt.transactions if t.date == "2026-06-04"] == [
        "Check 1001"
    ]


def test_the_check_head_printed_on_the_same_line_as_its_sub_heading_is_read():
    """Three of the seventeen print `Listed in numerical order` welded to the
    column head rather than on its own line."""
    welded = CHECKS.replace(
        "Listed in numerical order\nDate Check Amount Date Check Amount",
        "Listed in numerical order Date Check Amount Date Check Amount",
    )
    assert parsed(checks=welded) is not None


# ---------------------------------------------------------------------------
# The daily grid
# ---------------------------------------------------------------------------

def test_a_grid_spilling_under_a_continued_banner_is_one_grid():
    split = (
        "Daily Ending Balance\n"
        "DATE BALANCE DATE BALANCE DATE BALANCE "
        "06/01 1,000.00 06/02 1,300.00 06/03 1,200.00\n"
        "Daily Ending Balance (continued)\n"
        "DATE BALANCE DATE BALANCE DATE BALANCE "
        "06/04 1,100.00 06/05 1,300.00 06/09 1,250.00\n"
    )
    stmt = parsed(grid=split)
    assert stmt is not None
    assert len(stmt.stated_daily_balances) == 6


def test_a_grid_balance_the_ledger_does_not_reach_refuses_the_document():
    assert parsed(grid=GRID.replace("06/03 1,200.00", "06/03 1,200.01")) is None


def test_a_day_that_moved_and_is_missing_from_the_grid_refuses_the_document():
    assert parsed(grid=GRID.replace(" 06/04 1,100.00", "")) is None


def test_a_grid_day_the_ledger_never_posted_to_refuses_the_document():
    assert parsed(grid=GRID.replace("06/09 1,250.00", "06/09 1,250.00 06/10 1,250.00")) is None


def test_a_grid_that_repeats_a_day_refuses_the_document():
    assert parsed(grid=GRID.replace("06/05 1,300.00", "06/03 1,200.00")) is None


def test_a_document_with_no_grid_at_all_refuses():
    assert parsed(grid="") is None


def test_a_grid_date_outside_the_printed_period_refuses_the_document():
    assert parsed(grid=GRID.replace("06/09 1,250.00", "07/09 1,250.00")) is None


def test_a_misdated_row_no_other_oracle_can_see_is_caught_by_the_grid():
    """The count gates, the total gates and the closing identity are all
    indifferent to WHICH day a posting sat on. Only the grid replay is not, and
    the ADB depends on it."""
    misdated = DEBITS.replace("Sample Debit Two 06/09 50.00", "Sample Debit Two 06/08 50.00")
    assert parsed(debits=misdated) is None


# ---------------------------------------------------------------------------
# Mangled tokens are refusals, never exceptions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "token",
    [
        "06/32 300.00",   # a day no calendar holds
        "13/02 300.00",   # a month no calendar holds
        "07/02 300.00",   # a day outside the printed period
        "0\u00b9/02 300.00",  # a superscript in the date position
        "\u0660\u0666/02 300.00",  # Arabic-Indic digits, which `\\d` matches
    ],
)
def test_a_posting_date_the_period_cannot_place_refuses_rather_than_raises(token):
    """Each of these is a REFUSAL and none is an exception. The last two are
    the crash class `tests/test_parser_crash_shapes.py` exists for: `\\d` matches
    every Unicode decimal digit, so a date group written with it would convert
    a glyph nobody printed as a day. The anchors use `[0-9]`, so these rows do
    not anchor, the printed credit count no longer matches, and the document
    refuses rather than publishing a chronology it invented."""
    mangled = CREDITS.replace("06/02 300.00", token)
    assert parse_welch_state_bank_statement(document(credits=mangled)) is None


#: Arabic-Indic digits `\u0660`-`\u0669`. Unicode category Nd, so the shorthand
#: digit class matches them and `int()` and `float()` accept them — which is
#: exactly why every pattern in the reader that reaches a numeric conversion
#: spells `[0-9]` instead. `\u0660\u0666` reads as 06 to `int()`.
ND = {str(digit): chr(0x0660 + digit) for digit in range(10)}


def nd(text: str) -> str:
    """`text` with every ASCII digit replaced by its Arabic-Indic counterpart."""
    return "".join(ND.get(character, character) for character in text)


def test_the_non_ascii_digit_class_is_the_one_that_would_have_converted():
    """The premise of the tests below, asserted rather than assumed: these
    glyphs really are the class `int()` and `float()` silently accept, and the
    superscripts this archive actually carries are NOT."""
    assert int(nd("31")) == 31 and float(nd("1000") + ".00") == 1000.00
    for superscript in ("\u00b9", "\u00b2", "\u00b3"):
        with pytest.raises(ValueError):
            int(superscript)


@pytest.mark.parametrize(
    ("reading", "field", "value"),
    [
        ("ledger amount", "credits", CREDITS.replace("300.00", nd("300.00"))),
        ("cleared cheque amount", "checks", CHECKS.replace("100.00", nd("100.00"))),
        ("cleared cheque number", "checks", CHECKS.replace("1001", nd("1001"))),
        ("daily grid balance", "grid", GRID.replace("1,200.00", nd("1,200.00"))),
        ("summary money term", "summary",
         SUMMARY.replace("Beginning Balance 1,000.00", "Beginning Balance " + nd("1,000.00"))),
        ("summary day count", "summary",
         SUMMARY.replace("Statement Period 30", "Statement Period " + nd("30"))),
        ("summary credit count", "summary",
         SUMMARY.replace("30 2 Deposits", "30 " + nd("2") + " Deposits")),
        ("summary debit count", "summary",
         SUMMARY.replace("500.00 3 Checks", "500.00 " + nd("3") + " Checks")),
        ("summary account number", "summary",
         SUMMARY.replace("Account Number 1234567", "Account Number " + nd("1234567"))),
        ("masthead account number", "masthead",
         MASTHEAD.replace("ACCOUNT NUMBER 1234567", "ACCOUNT NUMBER " + nd("1234567"))),
        ("period start", "masthead",
         MASTHEAD.replace("06/01/26-06/30/26", nd("06/01/26") + "-06/30/26")),
        ("period end", "masthead",
         MASTHEAD.replace("06/01/26-06/30/26", "06/01/26-" + nd("06/30/26"))),
    ],
)
def test_a_reading_written_in_non_ascii_digits_refuses_rather_than_converts(
    reading, field, value
):
    """MINOR-1, one case per class of reading that reaches a numeric conversion.

    Each of these would have been CONVERTED — not dropped, converted — by a
    pattern written with the shorthand digit class: an amount, a cheque number,
    a daily balance, a day count, a transaction count, an account number and
    both endpoints of the period. Every one of them is refused, and refused by
    the pattern failing to match rather than by a guard downstream of it, which
    is what makes the refusal total instead of a silent drop.
    """
    assert parse_welch_state_bank_statement(document(**{field: value})) is None


def test_an_account_number_written_in_non_ascii_digits_in_BOTH_readings_refuses():
    """The isolating case for the account number, and the one the parametrized
    list above cannot make.

    Mutating one reading is caught by the other: the summary's account number
    and the masthead's must agree, so a non-ASCII digit on either side alone
    refuses through the DISAGREEMENT and says nothing about the digit class.
    The exposure is a printing that is non-ASCII in both places — the two
    readings then agree, every other gate closes, and only the digit class
    stands between the reader and an account number it publishes in glyphs the
    template does not print.
    """
    shifted = nd("1234567")
    assert parse_welch_state_bank_statement(document(
        masthead=MASTHEAD.replace("ACCOUNT NUMBER 1234567", "ACCOUNT NUMBER " + shifted),
        summary=SUMMARY.replace("Account Number 1234567", "Account Number " + shifted),
    )) is None


def test_an_empty_document_is_declined_rather_than_crashed():
    assert parse_welch_state_bank_statement("") is None


def test_a_masthead_with_no_ledger_at_all_is_not_a_statement():
    assert parse_welch_state_bank_statement(MASTHEAD + SUMMARY) is None

"""W3 coverage wave / DECLINES-C: the shapes bluevine, relay and navy_federal
could not survive.

Every fixture here is a SYNTHETIC reproduction of a *structural shape* found in
the three declined populations (33 documents: bluevine 14, navy_federal 10,
relay 9). The institution and column markers are each platform's own layout
sentinels — the same ones the parsers key on — and every counterparty, holder,
date, amount and account number is invented.

B1 the abbreviated month
    Bluevine prints its statement period both ways, "February 1, 2054" and
    "Feb. 1, 2054". The period pattern matched a month name with `\\w+`, which
    cannot span the abbreviating period, so twelve of the fourteen declines
    were refused on the FIRST field they were asked for. Both spellings are the
    same field of the same sentence and must read identically.

R1 the private-use glyph
    Some Relay statements embed a subset font whose ToUnicode table leaves the
    printed `+`, `-`, `(` and `)` in the Unicode private-use area. Six of the
    nine declines print every amount that way, so no transaction row matched at
    all. The signs are certified by the document's own arithmetic, never
    assumed: read one backwards and the balance walk stops.

R2 the wrapped row
    A row whose label wrapped onto the line above it was invisible to a pattern
    that required label and columns on one line. Three declines each lost
    exactly one row that way, and a statement missing one row fails its own
    balance walk, so all three were refused whole. A wrapped row whose label
    cannot be attributed is refused rather than guessed at.

N1 the product read from the document
    `navy_federal` carried "Business Checking" as a structural anchor, which
    restricted it to the business issue of a statement the credit union also
    prints for retail members ("EveryDay Checking", "e-Checking"). The product
    is read from the statement's own summary table and confirmed against its
    transaction-section heading.

N2 two checking products
    A statement covering two DIFFERENT checking accounts has no single product
    to anchor on, and the single-account extraction schema (L-1) cannot say
    "both". It is refused, not answered with half of itself.

N3 the attached overdrawn minus
    An overdrawn balance prints with a trailing minus, detached ("136.51 -") or
    attached ("136.51-"). Only the detached form was read, so the ledger walk
    stopped at the first overdrawn day.

N4 the amount-first text (audit round 2, R2-B06: R03)
    A retail statement (EveryDay Checking) reaches the compatibility path
    through generic block text in which every row's amount and balance sort
    ABOVE its own date and description. The path gave each pair the text read
    before it, the previous row's, from the first debit on. The section is
    now read as tokens (a pair, a date group, a description line with no date
    before it) with one token of lookahead: a pair followed by a date group is
    one row, and a date group followed by a pair, then any lone description
    lines, is one row with its wrap lines. A reading that does not fit falls
    back to the old loop unchanged. The native layout rung reads the one
    checking product the summary declares, as the parser does, instead of
    "Business Checking" alone.
"""
from __future__ import annotations

import pytest

from analysis.bluevine import parse_bluevine_statement
from analysis.navy_federal import parse_navy_federal_statement
from analysis.relay import _restore_glyphs, parse_relay_statement
from analysis.transaction_classifier import classify_statement_transactions
from ocr import native_text

# --------------------------------------------------------------- bluevine

#: 1,000.00 + 500.00 - 200.00 = 1,300.00.
BLUEVINE_FULL_MONTH = (
    "Bluevine Inc.\n"
    "Account Number: 900000001\n"
    "Statement Period: January 2054 (January 1, 2054 - January 31, 2054)\n"
    "Activity summary\n"
    "Beginning Balance on 01/01/2054 $1,000.00\n"
    "Deposits/credits $500.00\n"
    "Withdrawals/debits $-200.00\n"
    "Ending balance on 01/31/2054 $1,300.00\n"
    "Transactions\n"
    "Date Description Amount\n"
    "01/05/54 EXAMPLE PAYER TRANSFER $500.00\n"
    "01/09/54 EXAMPLE VENDOR PURCHASE $-200.00\n"
)

#: The identical statement with the month abbreviated, as this platform also
#: prints it. Only the two period tokens differ.
BLUEVINE_ABBREVIATED_MONTH = BLUEVINE_FULL_MONTH.replace(
    "(January 1, 2054 - January 31, 2054)", "(Jan. 1, 2054 - Jan. 31, 2054)"
)


def test_bluevine_reads_the_abbreviated_month_it_also_prints():
    """B1: "Jan. 1, 2054" is the same field as "January 1, 2054"."""
    statement = parse_bluevine_statement(BLUEVINE_ABBREVIATED_MONTH)

    assert statement is not None
    assert statement.period_start == "2054-01-01"
    assert statement.period_end == "2054-01-31"


def test_bluevine_month_spelling_changes_nothing_else():
    """B1 ablation: the two spellings produce the same statement."""
    full = parse_bluevine_statement(BLUEVINE_FULL_MONTH)
    abbreviated = parse_bluevine_statement(BLUEVINE_ABBREVIATED_MONTH)

    assert full is not None and abbreviated is not None
    assert full.period_start == abbreviated.period_start
    assert full.period_end == abbreviated.period_end
    assert full.days_in_period == abbreviated.days_in_period
    assert full.beginning_balance == abbreviated.beginning_balance
    assert full.ending_balance == abbreviated.ending_balance
    assert [t.amount for t in full.transactions] == [
        t.amount for t in abbreviated.transactions
    ]


def test_bluevine_declines_a_day_the_month_does_not_have():
    """B1 fail-closed: "Feb. 30" is date-SHAPED and is not a date.

    `_LONG_DATE` admits `\\d{1,2}` as the day, so this reaches `date()`, which
    raises ValueError. An escaping ValueError is a `parser_exception` — a
    crash — where this document deserves a named decline. Both are terminally
    non-publishing; only one puts the document in the right queue.
    """
    assert parse_bluevine_statement(
        BLUEVINE_FULL_MONTH.replace(
            "(January 1, 2054 - January 31, 2054)",
            "(Feb. 1, 2054 - Feb. 30, 2054)",
        )
    ) is None


def test_bluevine_declines_a_month_it_does_not_recognise():
    """A period-shaped phrase headed by a word that is not a month is a
    DECLINE, not an exception: the parser must fail closed, never crash."""
    assert parse_bluevine_statement(
        BLUEVINE_FULL_MONTH.replace(
            "(January 1, 2054 - January 31, 2054)",
            "(Janubry 1, 2054 - Janubry 31, 2054)",
        )
    ) is None


# ------------------------------------------------------------------ relay

#: 100.00 + 500.00 - 200.00 = 400.00. Relay prints newest row first.
RELAY_PRINTED_SIGNS = (
    "Relay Financials Technology Inc\n"
    "Account Statement\n"
    "Example Company LLC | Jan 1 - Jan 31, 2054\n"
    "Account Number: XXXXXX1234\n"
    "Opening Balance $100.00\n"
    "Closing Balance $400.00\n"
    "Deposits +$500.00\n"
    "Withdrawals -$200.00\n"
    "Name Date Status Amount Balance\n"
    "Example Vendor VISA Jan 20, 2054 Settled -$200.00 $400.00\n"
    "Example Payer ACH Jan 10, 2054 Settled +$500.00 $600.00\n"
)

#: The identical statement as the broken subset font delivers it: the two
#: amount signs, and the parentheses around an account's last four digits.
RELAY_PRIVATE_USE_GLYPHS = (
    RELAY_PRINTED_SIGNS
    .replace("+$", "\ue09d$")
    .replace("-$", "\ue088$")
    .replace("Example Vendor VISA", "Example Vendor \ue0819999\ue082 VISA")
)


def test_relay_reads_a_statement_whose_signs_are_private_use_glyphs():
    """R1: the printed characters are restored before anything is read."""
    statement = parse_relay_statement(RELAY_PRIVATE_USE_GLYPHS)

    assert statement is not None
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 400.00
    assert [t.amount for t in statement.transactions] == [500.00, -200.00]


def test_relay_glyph_statement_matches_the_printed_one():
    """R1: restoring the glyphs is the ONLY difference between the two."""
    printed = parse_relay_statement(RELAY_PRINTED_SIGNS)
    glyphs = parse_relay_statement(RELAY_PRIVATE_USE_GLYPHS)

    assert printed is not None and glyphs is not None
    assert printed.beginning_balance == glyphs.beginning_balance
    assert printed.ending_balance == glyphs.ending_balance
    assert printed.stated_total_credits == glyphs.stated_total_credits
    assert printed.stated_total_debits == glyphs.stated_total_debits
    assert [t.amount for t in printed.transactions] == [
        t.amount for t in glyphs.transactions
    ]


def test_relay_refuses_a_statement_whose_signs_are_the_wrong_way_round():
    """R1 ablation, the load-bearing one: the sign mapping is not trusted, it
    is CERTIFIED by the balance walk.

    The inversion is applied to the TRANSACTION ROWS ONLY and the printed
    summary is left exactly as it is. That distinction is the whole test. An
    earlier version rewrote every `+$`/`-$` in the document, summary included,
    so the summary pattern (which requires a literal `+` before Deposits and
    `-` before Withdrawals) failed first and the parser returned None before
    reading a single row \u2014 it passed against a tree with the entire balance
    walk deleted, and therefore certified nothing.

    With the summary intact the parser reaches the walk with a ledger whose
    signs are backwards: opening 100.00 + (-500.00) cannot be the printed
    600.00, so it stops at the first row it touches.
    """
    rows_inverted = (
        RELAY_PRINTED_SIGNS
        .replace("Settled +$", "Settled \ue088$")   # deliberately mapped to "-"
        .replace("Settled -$", "Settled \ue09d$")   # deliberately mapped to "+"
    )
    # The summary must still be readable, or this test proves nothing again.
    assert "Deposits +$500.00" in rows_inverted
    assert "Withdrawals -$200.00" in rows_inverted

    assert parse_relay_statement(rows_inverted) is None


def test_relay_glyph_restoration_leaves_ordinary_text_alone():
    assert _restore_glyphs("Example Payer ACH -$1.00") == "Example Payer ACH -$1.00"


#: The same statement after the newest row's label wrapped onto its own line —
#: the shape that made exactly one row per document invisible.
RELAY_WRAPPED_ROW = RELAY_PRINTED_SIGNS.replace(
    "Example Vendor VISA Jan 20, 2054 Settled -$200.00 $400.00\n",
    "Example Vendor VISA\nJan 20, 2054 Settled -$200.00 $400.00\n",
)


def test_relay_reads_a_row_whose_label_wrapped_onto_the_line_above():
    """R2: the row is read, and it keeps its own label."""
    statement = parse_relay_statement(RELAY_WRAPPED_ROW)

    assert statement is not None
    assert [t.amount for t in statement.transactions] == [500.00, -200.00]
    assert statement.transactions[1].description == (
        "Debit Card Purchase: Example Vendor"
    )


def test_relay_wrapped_row_matches_the_unwrapped_one():
    """R2 ablation: wrapping is a typesetting accident, not a difference."""
    flat = parse_relay_statement(RELAY_PRINTED_SIGNS)
    wrapped = parse_relay_statement(RELAY_WRAPPED_ROW)

    assert flat is not None and wrapped is not None
    assert [(t.date, t.description, t.amount, t.running_balance)
            for t in flat.transactions] == [
        (t.date, t.description, t.amount, t.running_balance)
        for t in wrapped.transactions
    ]


def test_relay_refuses_a_wrapped_row_whose_label_is_page_furniture():
    """R2 fail-closed: a wrapped row sitting under a page break has its label
    on the far side of it. The row is refused, not given the footer's text as
    a description — the balance walk would accept a mislabelled row happily."""
    across_a_page_break = RELAY_PRINTED_SIGNS.replace(
        "Example Vendor VISA Jan 20, 2054 Settled -$200.00 $400.00\n",
        "--- Page 2 ---\nJan 20, 2054 Settled -$200.00 $400.00\n",
    )

    assert parse_relay_statement(across_a_page_break) is None


# ----------------------------------------------------------- navy_federal


def _navy_federal(product: str, extra_table_rows: str = "") -> str:
    """A Navy Federal statement covering one checking product.

    1,000.00 - 200.00 + 300.00 = 1,100.00. The debit prints its date and
    description BEFORE its money columns and the credit prints them after,
    which is this platform's own row order.
    """
    return (
        "Navy Federal\n"
        "Statement Period 01/01/54 - 01/31/54\n"
        "Summary of your deposit accounts\n"
        "Previous Deposits/ Withdrawals/ Ending YTD "
        "Balance Credits Debits Balance Dividends\n"
        f"{product}\n"
        "7000000001 $1,000.00 $300.00 $200.00 $1,100.00 $0.00\n"
        f"{extra_table_rows}"
        "Membership Savings\n"
        "3000000002 $5.00 $0.00 $0.00 $5.00 $0.00\n"
        "Totals $1,005.00 $300.00 $200.00 $1,105.00 $0.00\n"
        "Checking\n"
        "Date Transaction Detail Amount($) Balance($)\n"
        f"{product} - 7000000001\n"
        "1,000.00\n"
        "01-01\n"
        "Beginning Balance\n"
        "01-05\n"
        "Example Vendor Purchase\n"
        "200.00 800.00\n"
        "300.00 1,100.00\n"
        "01-09\n"
        "Example Payer Deposit\n"
        "Ending Balance\n"
        "Average Daily Balance - Current Cycle: $1,050.00\n"
        "Membership Savings - 3000000002\n"
        "5.00\n"
        "01-01\n"
        "Beginning Balance\n"
        "Ending Balance\n"
    )


def test_navy_federal_reads_the_business_product():
    """N1 baseline: the product the parser used to have written into it."""
    statement = parse_navy_federal_statement(_navy_federal("Business Checking"))

    assert statement is not None
    assert statement.account_name == "Business Checking"
    assert statement.account_number == "7000000001"
    assert statement.beginning_balance == 1000.00
    assert statement.ending_balance == 1100.00
    assert [t.amount for t in statement.transactions] == [-200.00, 300.00]


def test_navy_federal_reads_a_retail_product_it_has_never_seen():
    """N1: the capability. Same grid, same layout, a different product word —
    read from the statement's own summary table."""
    statement = parse_navy_federal_statement(_navy_federal("EveryDay Checking"))

    assert statement is not None
    assert statement.account_name == "EveryDay Checking"
    assert statement.account_number == "7000000001"
    assert [t.amount for t in statement.transactions] == [-200.00, 300.00]


def test_navy_federal_product_name_changes_nothing_but_the_name():
    """N1 ablation: the product is a label, not a layout."""
    business = parse_navy_federal_statement(_navy_federal("Business Checking"))
    retail = parse_navy_federal_statement(_navy_federal("e-Checking"))

    assert business is not None and retail is not None
    assert business.beginning_balance == retail.beginning_balance
    assert business.ending_balance == retail.ending_balance
    assert business.stated_total_credits == retail.stated_total_credits
    assert business.stated_total_debits == retail.stated_total_debits
    assert business.stated_average_balance == retail.stated_average_balance
    assert [t.amount for t in business.transactions] == [
        t.amount for t in retail.transactions
    ]


def test_navy_federal_stops_a_section_at_the_next_account_heading():
    """N1: the section boundary is read from the document's own headings, so a
    savings product this parser has never been told about still ends the
    checking section it follows."""
    statement = parse_navy_federal_statement(_navy_federal("EveryDay Checking"))

    assert statement is not None
    # The savings section's own beginning balance is not in the checking walk.
    assert len(statement.transactions) == 2
    assert statement.stated_average_balance == 1050.00


def test_navy_federal_ignores_a_prose_mention_of_the_heading():
    """N1: the second printing must be a HEADING, not any prose that happens
    to name the pair.

    The statement's transaction detail is replaced by a sentence mentioning
    "EveryDay Checking - 7000000001" mid-line. A substring test is satisfied
    by that and would confirm a reading the document never printed as a
    heading; the line-anchored test is not, and the document is refused.
    """
    prose_only = _navy_federal("EveryDay Checking").replace(
        "EveryDay Checking - 7000000001\n",
        "Questions about EveryDay Checking - 7000000001 may be directed to us.\n",
    )

    assert "EveryDay Checking - 7000000001" in prose_only      # substring: yes
    assert parse_navy_federal_statement(prose_only) is None    # heading: no


def test_navy_federal_accepts_a_caption_merged_into_the_column_header():
    """N1: the second printing may sit at the END of the grid's column-header
    line, which is where the text extractor puts it on three cohort documents
    that validate. Requiring the caption to BE the whole line refuses them.
    """
    merged = _navy_federal("Business Checking").replace(
        "Date Transaction Detail Amount($) Balance($)\n"
        "Business Checking - 7000000001\n",
        "Date Transaction Detail Amount($) Balance($) "
        "Business Checking - 7000000001 (Continued from previous page)\n",
    )

    statement = parse_navy_federal_statement(merged)

    assert statement is not None
    assert statement.account_number == "7000000001"
    assert [t.amount for t in statement.transactions] == [-200.00, 300.00]


def test_navy_federal_refuses_two_different_checking_products():
    """N2: L-1. Two checking accounts, one single-account schema, no way to
    say "both" — so it says nothing."""
    two_products = _navy_federal(
        "EveryDay Checking",
        extra_table_rows="e-Checking\n7000000003 $10.00 $0.00 $0.00 $10.00 $0.00\n",
    )

    assert parse_navy_federal_statement(two_products) is None


def test_navy_federal_reads_an_overdrawn_balance_with_an_attached_minus():
    """N3: "800.00-" and "800.00 -" are the same printed balance.

    1,000.00 - 1,800.00 = -800.00 overdrawn, then + 1,900.00 = 1,100.00.
    """
    overdrawn = _navy_federal("EveryDay Checking").replace(
        "7000000001 $1,000.00 $300.00 $200.00 $1,100.00 $0.00",
        "7000000001 $1,000.00 $1,900.00 $1,800.00 $1,100.00 $0.00",
    ).replace(
        "Totals $1,005.00 $300.00 $200.00 $1,105.00 $0.00",
        "Totals $1,005.00 $1,900.00 $1,800.00 $1,105.00 $0.00",
    ).replace(
        "200.00 800.00\n", "1,800.00 800.00-\n"
    ).replace(
        "300.00 1,100.00\n", "1,900.00 1,100.00\n"
    )

    statement = parse_navy_federal_statement(overdrawn)

    assert statement is not None
    assert [t.amount for t in statement.transactions] == [-1800.00, 1900.00]
    assert statement.transactions[0].running_balance == -800.00


def test_navy_federal_attached_and_detached_minus_read_alike():
    """N3 ablation: the separator is typesetting, the minus is the balance."""
    attached = _navy_federal("EveryDay Checking").replace(
        "7000000001 $1,000.00 $300.00 $200.00 $1,100.00 $0.00",
        "7000000001 $1,000.00 $1,900.00 $1,800.00 $1,100.00 $0.00",
    ).replace(
        "Totals $1,005.00 $300.00 $200.00 $1,105.00 $0.00",
        "Totals $1,005.00 $1,900.00 $1,800.00 $1,105.00 $0.00",
    ).replace("200.00 800.00\n", "1,800.00 800.00-\n"
              ).replace("300.00 1,100.00\n", "1,900.00 1,100.00\n")
    detached = attached.replace("1,800.00 800.00-\n", "1,800.00 800.00 -\n")

    first = parse_navy_federal_statement(attached)
    second = parse_navy_federal_statement(detached)

    assert first is not None and second is not None
    assert [(t.amount, t.running_balance) for t in first.transactions] == [
        (t.amount, t.running_balance) for t in second.transactions
    ]


# --------------------------------------------- navy_federal (W3 §WITHHELDGRIDS)


def _navy_federal_dated_credit() -> str:
    """The same platform printing every row's date and description ABOVE its
    money columns: `<date>` / `<description>` / `<amount> <balance>`.

    This is the date-first arrangement the af117fd narrowing was written for
    (its withheld documents are not in the corpus). It is NOT what the
    archive's text-layer documents print: the corpus's four EveryDay Checking
    statements print every row amount-first (`<amount>` `<balance>` /
    `<date>` / `<description>`, the pair sorting above its own date), which
    `_navy_federal_amount_first` reproduces (audit round 2, R2-B06: R03). Both
    arrangements read through the lookahead reading; this one is kept as its
    control.

    1,000.00 + 300.00 - 200.00 = 1,100.00.
    """
    return (
        "Navy Federal\n"
        "Statement Period 01/01/54 - 01/31/54\n"
        "Summary of your deposit accounts\n"
        "Previous Deposits/ Withdrawals/ Ending YTD "
        "Balance Credits Debits Balance Dividends\n"
        "Business Checking\n"
        "7000000001 $1,000.00 $300.00 $200.00 $1,100.00 $0.00\n"
        "Totals $1,000.00 $300.00 $200.00 $1,100.00 $0.00\n"
        "Checking\n"
        "Date Transaction Detail Amount($) Balance($)\n"
        "Business Checking - 7000000001\n"
        "1,000.00\n"
        "01-01\n"
        "Beginning Balance\n"
        "01-05\n"
        "Example Payer Deposit\n"
        "300.00 1,300.00\n"
        "01-09\n"
        "Example Vendor Purchase\n"
        "200.00 1,100.00\n"
        "01-31\n"
        "Ending Balance\n"
    )


def test_a_credit_that_carries_its_own_date_keeps_it():
    """The compatibility branch takes a credit's date and description from the
    row BELOW it. That is right only where the row has neither of its own.

    Where the row has both, taking the next row's does not relabel one row —
    it shifts the ledger by one: this row is published on the next row's day
    under the next row's description, the next row inherits that same day with
    an empty description, and the day this row was printed on is never posted.
    """
    statement = parse_navy_federal_statement(_navy_federal_dated_credit())

    assert statement is not None
    assert [(t.date, t.amount) for t in statement.transactions] == [
        ("2054-01-05", 300.00),
        ("2054-01-09", -200.00),
    ]
    assert [t.description for t in statement.transactions] == [
        "Example Payer Deposit",
        "Example Vendor Purchase",
    ]


def test_the_platforms_other_row_order_still_reads_its_credit():
    """NEGATIVE pin (passes at base by construction).

    The ablation: the branch is narrowed, not removed. In the arrangement
    it exists for, the credit reaches its amount pair with no date and no
    description of its own and still takes both from the row below."""
    statement = parse_navy_federal_statement(_navy_federal("Business Checking"))

    assert statement is not None
    assert [(t.date, t.amount) for t in statement.transactions] == [
        ("2054-01-05", -200.00),
        ("2054-01-09", 300.00),
    ]


# ------------------------- navy_federal amount-first (audit round 2, R2-B06: R03)

#: The archive's amount-first arrangement of the generic block text: each row's
#: amount and balance sort ABOVE its own date and description (a separate pair
#: or a one-line pair, a debit's detached '-' after it). The Zelle row prints
#: its date and description first and wraps a line AFTER its pair (G P D).
#: 1,000.00 + 300.00 - 200.00 + 450.00 + 2,500.00 - 50.00 + 75.00 = 4,075.00.
NAVY_AMOUNT_FIRST_LEDGER = (
    "300.00\n"
    "1,300.00\n"
    "01-02\n"
    "Transfer From Shares\n"
    "200.00 1,100.00\n"
    "-\n"
    "01-05\n"
    "POS Debit- Debit Card 0000 FABRIKAM STORE\n"
    "01-07\n"
    "Zelle CR CONTOSO LLC\n"
    "450.00 1,550.00\n"
    "SAMPLE CITY ST\n"
    "2,500.00 4,050.00\n"
    "01-09\n"
    "Bank Wire Deposit\n"
    "50.00 4,000.00\n"
    "-\n"
    "01-12\n"
    "Paid To - NORTHWIND UTILITIES\n"
    "75.00 4,075.00\n"
    "01-15\n"
    "Deposit\n"
)

#: What the PDF prints, row by row.
NAVY_AMOUNT_FIRST_ROWS = [
    ("2054-01-02", 300.00, "Transfer From Shares"),
    ("2054-01-05", -200.00, "POS Debit- Debit Card 0000 FABRIKAM STORE"),
    ("2054-01-07", 450.00, "Zelle CR CONTOSO LLC SAMPLE CITY ST"),
    ("2054-01-09", 2500.00, "Bank Wire Deposit"),
    ("2054-01-12", -50.00, "Paid To - NORTHWIND UTILITIES"),
    ("2054-01-15", 75.00, "Deposit"),
]


def _navy_federal_amount_first(
    product: str = "EveryDay Checking",
    ledger: str = NAVY_AMOUNT_FIRST_LEDGER,
    ending: str = "01-31\nEnding Balance\n4,075.00\n",
) -> str:
    """A Navy Federal statement whose generic block text prints the ledger
    amount-first, as the archive's four EveryDay Checking statements do."""
    return (
        "Navy Federal\n"
        "Statement Period 01/01/54 - 01/31/54\n"
        "Summary of your deposit accounts\n"
        "Previous Deposits/ Withdrawals/ Ending YTD "
        "Balance Credits Debits Balance Dividends\n"
        f"{product}\n"
        "7000000001 $1,000.00 $3,325.00 $250.00 $4,075.00 $0.00\n"
        "Membership Savings\n"
        "3000000002 $5.00 $0.00 $0.00 $5.00 $0.00\n"
        "Totals $1,005.00 $3,325.00 $250.00 $4,080.00 $0.00\n"
        "Checking\n"
        "Date Transaction Detail Amount($) Balance($)\n"
        f"{product} - 7000000001\n"
        "1,000.00\n"
        "01-01\n"
        "Beginning Balance\n"
        f"{ledger}"
        f"{ending}"
        "Average Daily Balance - Current Cycle: $2,000.00\n"
        "Membership Savings - 3000000002\n"
        "5.00\n"
        "01-01\n"
        "Beginning Balance\n"
        "01-31\n"
        "Ending Balance\n"
        "5.00\n"
    )


def _credit_tiers(statement):
    return [
        (record.amount, record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
        for record in classify_statement_transactions(statement)
        if record.amount > 0
    ]


#: The credits' tiers once each row carries its own text: the member's own
#: share transfer is non-revenue, the Zelle is counted as P2P (Q4), the wire
#: that prints no sender is held (Q5), the bare deposit is counted (Q2).
NAVY_AMOUNT_FIRST_CREDIT_TIERS = [
    (300.00, "non_revenue"),
    (450.00, ("counted_flagged", "p2p")),
    (2500.00, ("excluded_pending_review", "wire_no_sender")),
    (75.00, ("counted_flagged", "no_payer_printed")),
]


def _matches_tiers(observed, expected):
    for (amount, tier, reason), (want_amount, want) in zip(observed, expected, strict=True):
        assert amount == want_amount
        if isinstance(want, tuple):
            assert (tier, reason) == want, (amount, tier, reason)
        else:
            assert tier == want, (amount, tier, reason)


def test_an_amount_first_retail_statement_reads_each_row_s_own_date_and_text():
    """N4 (T1): each pair owns the date group that FOLLOWS it; the Zelle row
    printed date-first keeps its wrap line. Before, the +2,500.00 wire read
    the Zelle's wrap line 'SAMPLE CITY ST', the -200.00 debit read the share
    transfer's date, and the +75.00 deposit read the 'Paid To' debit's text."""
    statement = parse_navy_federal_statement(_navy_federal_amount_first())

    assert statement is not None
    assert [(t.date, t.amount, t.description) for t in statement.transactions] == NAVY_AMOUNT_FIRST_ROWS


def test_an_amount_first_retail_statement_tiers_each_credit_on_its_own_text():
    """N4 (T1): before, the +2,500.00 and +75.00 credits read another row's
    text and were both counted as a named payer with no channel; the wire with
    no sender was out of the review it is owed."""
    statement = parse_navy_federal_statement(_navy_federal_amount_first())

    assert statement is not None
    _matches_tiers(_credit_tiers(statement), NAVY_AMOUNT_FIRST_CREDIT_TIERS)


def test_the_business_product_printed_amount_first_reads_the_same():
    """N4 (T2): the product is a label, not a layout."""
    retail = parse_navy_federal_statement(_navy_federal_amount_first())
    business = parse_navy_federal_statement(_navy_federal_amount_first("Business Checking"))

    assert retail is not None and business is not None
    assert [(t.date, t.amount, t.description) for t in business.transactions] == NAVY_AMOUNT_FIRST_ROWS
    _matches_tiers(_credit_tiers(business), NAVY_AMOUNT_FIRST_CREDIT_TIERS)


def test_an_ending_balance_printed_above_its_own_date_is_no_description():
    """N4: amount-first, the Ending Balance's own figure can sort above its
    date too, right after the last row's description. It is that balance,
    not a wrap line of the last row."""
    statement = parse_navy_federal_statement(
        _navy_federal_amount_first(ending="4,075.00\n01-31\nEnding Balance\n")
    )

    assert statement is not None
    assert [(t.date, t.amount, t.description) for t in statement.transactions] == NAVY_AMOUNT_FIRST_ROWS


def test_the_date_first_and_mixed_arrangements_read_as_before():
    """N4 controls: the af117fd date-first fixture and the base mixed fixture
    read their rows exactly as they did before the lookahead reading."""
    dated = parse_navy_federal_statement(_navy_federal_dated_credit())
    mixed = parse_navy_federal_statement(_navy_federal("Business Checking"))

    assert dated is not None and mixed is not None
    assert [(t.date, t.amount, t.description) for t in dated.transactions] == [
        ("2054-01-05", 300.00, "Example Payer Deposit"),
        ("2054-01-09", -200.00, "Example Vendor Purchase"),
    ]
    assert [(t.date, t.amount, t.description) for t in mixed.transactions] == [
        ("2054-01-05", -200.00, "Example Vendor Purchase"),
        ("2054-01-09", 300.00, "Example Payer Deposit"),
    ]


def test_a_row_with_no_date_still_falls_back_to_the_line_reader():
    """N4 control: a description line with no date before it opens the ledger,
    so the lookahead reading does not fit; the old line reader decides, and it
    refuses a debit with no date as it always did."""
    no_date = _navy_federal_dated_credit().replace(
        "01-05\nExample Payer Deposit\n300.00 1,300.00\n01-09\nExample Vendor Purchase\n200.00 1,100.00\n",
        "Example Vendor Purchase\n200.00 800.00\n300.00 1,100.00\n01-09\nExample Payer Deposit\n",
    )

    assert "Example Vendor Purchase\n200.00 800.00" in no_date
    assert parse_navy_federal_statement(no_date) is None


# ---------------------- navy_federal native layout rung (audit round 2, R2-B06: R03)

#: The layout-sorted text (MuPDF `sort=True`) of one page: one visual row per
#: line, each row's date, description, amount and balance together.
def _navy_layout_text(product: str = "EveryDay Checking", extra_summary: str = "",
                      ending: str = "01-31 Ending Balance 4,075.00\n") -> str:
    return (
        "Navy Federal Credit Union\n"
        "Statement of Account\n"
        "Statement Period 01/01/54 - 01/31/54\n"
        "Summary of your deposit accounts\n"
        "Previous Deposits/ Withdrawals/ Ending YTD\n"
        "Balance Credits Debits Balance Dividends\n"
        f"{product}\n"
        "7000000001 $1,000.00 $3,325.00 $250.00 $4,075.00 $0.00\n"
        f"{extra_summary}"
        "Membership Savings\n"
        "3000000002 $5.00 $0.01 $0.00 $5.01 $0.01\n"
        "Totals $1,005.00 $3,325.01 $250.00 $4,080.01 $0.01\n"
        "Statement of Account\n"
        f"{product} - 7000000001\n"
        "Date Transaction Detail Amount($) Balance($)\n"
        "01-01 Beginning Balance 1,000.00\n"
        "01-02 Transfer From Shares 300.00 1,300.00\n"
        "01-05 POS Debit- Debit Card 0000 FABRIKAM STORE 200.00 - 1,100.00\n"
        "01-07 Zelle CR CONTOSO LLC 450.00 1,550.00\n"
        "SAMPLE CITY ST\n"
        "01-09 Bank Wire Deposit 2,500.00 4,050.00\n"
        "01-12 Paid To - NORTHWIND UTILITIES 50.00 - 4,000.00\n"
        "01-15 Deposit 75.00 4,075.00\n"
        f"{ending}"
        "Average Daily Balance - Current Cycle: $2,000.00\n"
        "Membership Savings - 3000000002\n"
        "01-01 Beginning Balance 5.00\n"
        "01-31 Dividend 0.01 5.01\n"
        "01-31 Ending Balance 5.01\n"
    )


class _LayoutPage:
    """A page whose layout-sorted text and blocks are the given text."""

    def __init__(self, text: str) -> None:
        self._text = text

    def get_text(self, mode: str = "text", **_options):
        if mode == "blocks":
            return [
                (0.0, float(10 * number), 100.0, float(10 * number + 8), line, number, 0)
                for number, line in enumerate(self._text.splitlines())
            ]
        return self._text


class _LayoutDoc:
    def __init__(self, text: str) -> None:
        self._pages = [_LayoutPage(text)]
        self.page_count = 1

    def __iter__(self):
        return iter(self._pages)

    def __getitem__(self, index):
        return self._pages[index]

    def close(self) -> None:
        return None


@pytest.fixture
def navy_layout(monkeypatch):
    """Stub MuPDF so the rung reads the given layout text as the document."""
    import fitz

    def install(text: str) -> bytes:
        native_text._native_pages_cached.cache_clear()
        monkeypatch.setattr(fitz, "open", lambda *a, **k: _LayoutDoc(text))
        return b"%PDF-1.4 navy " + text.encode("utf-8")

    yield install
    native_text._native_pages_cached.cache_clear()


def _nfcu_rows(document):
    markdown = document.to_markdown()
    return [line.split("|", 2)[2] for line in markdown.splitlines() if line.startswith("NFCU_TX|")]


def test_the_layout_rung_reads_the_retail_product_the_summary_declares(navy_layout):
    """N4 (T3): the rung read only 'Business Checking', so a retail statement
    fell through to the generic rung and the amount-first block text."""
    raw = navy_layout(_navy_layout_text())

    document = native_text.parse_native_navy_federal(raw, source_file="x.pdf")

    assert document is not None
    assert document.model == "native-pdf-text+navy-federal-layout"
    assert _nfcu_rows(document) == [
        "01-02|300.00|1,300.00|Transfer From Shares",
        "01-05|200.00|1,100.00|POS Debit- Debit Card 0000 FABRIKAM STORE",
        "01-07|450.00|1,550.00|Zelle CR CONTOSO LLC SAMPLE CITY ST",
        "01-09|2,500.00|4,050.00|Bank Wire Deposit",
        "01-12|50.00|4,000.00|Paid To - NORTHWIND UTILITIES",
        "01-15|75.00|4,075.00|Deposit",
    ]
    assert native_text.native_statement(raw, source_file="x.pdf").model == document.model


def test_the_layout_rung_s_retail_rows_publish_the_statement(navy_layout):
    """N4 (T3): the rung's rows are what the parser publishes for the product."""
    raw = navy_layout(_navy_layout_text())

    statement = parse_navy_federal_statement(
        native_text.parse_native_navy_federal(raw, source_file="x.pdf").to_markdown()
    )

    assert statement is not None
    assert statement.account_name == "EveryDay Checking"
    assert [(t.date, t.amount, t.description) for t in statement.transactions] == NAVY_AMOUNT_FIRST_ROWS


def test_the_layout_rung_refuses_two_checking_products(navy_layout):
    """N4 (T3), N2's rule: two checking products have no single account."""
    raw = navy_layout(_navy_layout_text(extra_summary="e-Checking\n7000000003 $10.00 $0.00 $0.00 $10.00 $0.00\n"))

    assert native_text.parse_native_navy_federal(raw, source_file="x.pdf") is None


def test_the_layout_rung_refuses_a_product_its_section_never_heads(navy_layout):
    """N4 (T3): the summary's product is confirmed by its own section heading."""
    raw = navy_layout(_navy_layout_text().replace("EveryDay Checking - 7000000001\n", "Checking\n"))

    assert native_text.parse_native_navy_federal(raw, source_file="x.pdf") is None


@pytest.mark.parametrize("product", ["EveryDay Checking", "Business Checking"])
def test_the_layout_rung_stops_at_any_other_account_s_heading(navy_layout, product):
    """N4 (T3): a section with no Ending Balance line ends where the next
    account's '<name> - <digits>' heading begins, whatever that product is."""
    raw = navy_layout(_navy_layout_text(product, ending=""))

    document = native_text.parse_native_navy_federal(raw, source_file="x.pdf")

    assert document is not None
    rows = _nfcu_rows(document)
    assert len(rows) == 6
    assert not any("Dividend" in row for row in rows)

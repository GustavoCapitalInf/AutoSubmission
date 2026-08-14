"""W3 §FINTECH — Mercury, Found/Lead Bank and Brex.

Synthetic documents throughout: the names, numbers and amounts here are
invented, and each fixture carries exactly the printed shape the assertion is
about. Where a rule was chosen over a plausible alternative, BOTH readings are
pinned — a test that only shows the rule working cannot fail when someone
"simplifies" it back to the alternative.
"""
from __future__ import annotations

import pytest

from analysis import brex, found_lead, mercury
from analysis.reconcile import reconcile

#: The icon glyph Mercury sets at the head of the Type column. A Private Use
#: Area codepoint: no meaning, only ink, and the column boundary.
MARK = ""


# ===========================================================================
# Mercury
# ===========================================================================

def mercury_document(grid: str, *, beginning="$0.00", withdrawals="$0.00",
                     deposits="$0.00", ending="$0.00", total=None,
                     header=None) -> str:
    return (
        (header or "April 2026 statement April 1, 2026-April 30, 2026 (30 days) All dates in UTC")
        + "\nNorthwind Trading LLC\n"
        "Account details\n"
        "Account Type Checking\n"
        "Account Number 40011122233\n"
        "Routing Number 12345678\n"
        "Account activity\n"
        f"Beginning Balance {beginning}\n"
        f"Total withdrawals {withdrawals}\n"
        f"Total deposits {deposits}\n"
        f"Statement balance {ending}\n"
        "Banking services provided by Column N.A., Member FDIC\n"
        "Mercury | help@mercury.com | 100 Example Street\n"
        "All Transactions /\n"
        "Date (UTC) Description Type Amount End of Day Balance\n"
        + grid +
        f"Total {total if total is not None else ending}\n"
        "Banking services provided by Column N.A., Member FDIC\n"
        "Mercury | help@mercury.com | 100 Example Street\n"
    )


def test_mercury_prints_the_balance_only_on_the_last_row_of_a_day():
    """Three postings on one day, one printed balance. The two rows above it
    carry `running_balance=None` rather than the day's closing figure, and the
    balance walk still closes because `reconcile` accumulates across them."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull -$10.00\n"
        f"Beta Freight {MARK}ACH Pull -$15.00\n"
        f"Gamma Retail {MARK}ACH In $40.00 $115.00\n",
        beginning="$100.00", withdrawals="-$25.00", deposits="$40.00", ending="$115.00",
    ))
    assert statement is not None
    assert [t.running_balance for t in statement.transactions] == [None, None, 115.00]
    assert {t.date for t in statement.transactions} == {"2026-04-02"}
    assert reconcile(statement).continuity_breaks == 0


def test_mercury_carries_the_date_forward_across_a_page_break():
    """A day whose postings span two pages: the second page reprints the
    column header and NOT the date."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull -$10.00\n"
        "Banking services provided by Column N.A., Member FDIC\n"
        "All Transactions /\n"
        "Date (UTC) Description Type Amount End of Day Balance\n"
        f"Beta Freight {MARK}ACH Pull -$15.00 $75.00\n",
        beginning="$100.00", withdrawals="-$25.00", deposits="$0.00", ending="$75.00",
    ))
    assert statement is not None
    assert [t.date for t in statement.transactions] == ["2026-04-02", "2026-04-02"]


@pytest.mark.parametrize("minus", ["-", "−", "–"])
def test_mercury_reads_all_three_printed_minus_glyphs(minus):
    """The same generator prints ASCII hyphen, U+2212 and U+2013 as the sign,
    and a reader that knows only one of them sign-flips the others."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull {minus}$10.00 $90.00\n",
        beginning="$100.00", withdrawals=f"{minus}$10.00", deposits="$0.00", ending="$90.00",
    ))
    assert statement is not None
    assert statement.transactions[0].amount == -10.00
    assert statement.transactions[0].direction == "debit"
    assert reconcile(statement).ok


def test_mercury_takes_direction_from_the_sign_and_never_from_the_type_column():
    """The trap this parser exists to avoid. Three rows whose Type cell points
    the OTHER way from the printed sign, all read from the sign:

    * "Credit Account Payment" — the word Credit, a debit;
    * "Credit Cashback Deposit" — the same word, a credit;
    * a masked card number — no direction word at all, and a refund.
    """
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Card Issuer {MARK}Credit Account Payment -$30.00\n"
        f"Rewards {MARK}Credit Cashback Deposit $5.00\n"
        f"Corner Shop {MARK}••1234 $25.00 $100.00\n",
        beginning="$100.00", withdrawals="-$30.00", deposits="$30.00", ending="$100.00",
    ))
    assert statement is not None
    assert [t.direction for t in statement.transactions] == ["debit", "credit", "credit"]
    assert [t.amount for t in statement.transactions] == [-30.00, 5.00, 25.00]


def test_mercury_refuses_a_posting_row_that_carries_no_type_mark():
    """The mark is the Description | Type column boundary and every surveyed
    posting carries one. A row-shaped line without it is not a posting this
    reader knows how to place, so the grid closes — and the row then falls
    outside it, which is a refusal rather than a silent drop."""
    assert mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull -$10.00 $90.00\n"
        "Apr 03 Beta Freight ACH Pull -$10.00 $80.00\n",
        beginning="$100.00", withdrawals="-$20.00", deposits="$0.00", ending="$80.00",
    )) is None


def test_mercury_does_not_read_a_month_word_in_a_description_as_the_date():
    """A merchant whose name opens with a month word and a number. The token
    resolves outside the statement period, so it stays description and the row
    continues the day above it — the alternative silently re-dates the row and
    with it an end-of-day balance."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull -$10.00\n"
        f"May 15 Holdings {MARK}ACH Pull -$10.00 $80.00\n",
        beginning="$100.00", withdrawals="-$20.00", deposits="$0.00", ending="$80.00",
    ))
    assert statement is not None
    assert [t.date for t in statement.transactions] == ["2026-04-02", "2026-04-02"]
    assert statement.transactions[1].description.startswith("May 15 Holdings")


def test_mercury_admits_a_printed_zero_activity_period():
    """The four negatives Ocean ruled for Chase and applied in scotia: an
    EMPTY grid, both stated totals zero, and the two balances equal."""
    statement = mercury.parse_mercury_statement(mercury_document(
        "", beginning="$0.00", withdrawals="$0.00", deposits="$0.00", ending="$0.00",
    ))
    assert statement is not None
    assert statement.transactions == []
    assert reconcile(statement).ok


@pytest.mark.parametrize("grid,kwargs", [
    # rows WERE printed and none was read — an empty ledger for the other
    # reason, which must never be published as "nothing happened".
    ("Apr 02 Alpha Supply -$10.00 $90.00\n",
     {"beginning": "$100.00", "withdrawals": "-$10.00", "deposits": "$0.00", "ending": "$90.00"}),
    # the bank states activity but printed no rows.
    ("", {"beginning": "$100.00", "withdrawals": "-$10.00", "deposits": "$0.00", "ending": "$90.00"}),
    # the balances moved with nothing to move them.
    ("", {"beginning": "$100.00", "withdrawals": "$0.00", "deposits": "$0.00", "ending": "$90.00"}),
])
def test_mercury_refuses_an_empty_ledger_that_is_not_a_zero_activity_period(grid, kwargs):
    assert mercury.parse_mercury_statement(mercury_document(grid, **kwargs)) is None


def test_mercury_reports_a_grid_total_that_disagrees_with_the_statement_balance():
    document = mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull -$10.00 $90.00\n",
        beginning="$100.00", withdrawals="-$10.00", deposits="$0.00", ending="$90.00",
        total="$91.00",
    )
    statement = mercury.parse_mercury_statement(document)
    assert statement is not None
    notes = mercury.printed_total_contradictions(document, statement)
    assert any("printed Total" in note for note in notes)


def test_mercury_reports_a_day_count_that_disagrees_with_the_printed_period():
    document = mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull -$10.00 $90.00\n",
        beginning="$100.00", withdrawals="-$10.00", deposits="$0.00", ending="$90.00",
        header="April 2026 statement April 1, 2026-April 30, 2026 (28 days) All dates in UTC",
    )
    statement = mercury.parse_mercury_statement(document)
    assert statement is not None
    assert any("28-day period" in note
               for note in mercury.printed_total_contradictions(document, statement))


# ===========================================================================
# Found / Lead Bank
# ===========================================================================

_FOUND_FOOTER = (
    "Found is a financial technology company, not a bank.\n"
    "Page 1 of 1\n"
    "Banking services are provided by Lead Bank, Member FDIC.\n"
)
_FOUND_DISCLAIMER = (
    "The information in this document is not a bank statement and therefore "
    "should not be relied upon as a bank statement.\n"
)


def found_document(grid: str, *, title="Account Statement", beginning="$0.00",
                   credits="+ $0.00", debits="$0.00", fees="$0.00",
                   ending="$0.00", period="February 1 to February 28, 2026",
                   sections=("Transactions",), disclaimer="") -> str:
    heading = "".join(f"{section}\nDate Description Amount Balance\n" for section in sections)
    return (
        f"February 2026 {title}\n"
        "Statement period\nRouting number\nAccount number\n"
        f"{period}\n101 019 644\n2135 0078 7137\n"
        "Business name: Northwind Trading\n"
        "Account summary\n"
        f"Beginning balance on February 1, 2026 {beginning}\n"
        f"Deposits & other credits {credits}\n"
        f"Purchases & other debits {debits}\n"
        f"Fees {fees}\n"
        f"Ending balance on February 28, 2026 {ending}\n"
        + heading + grid + disclaimer + _FOUND_FOOTER
    )


def test_found_reads_the_spaced_sign_and_an_overdrawn_closing_balance():
    statement = found_lead.parse_found_lead_statement(found_document(
        "02/04/26 Alpha Supply - $30.00 -$10.00\n"
        "02/05/26 Beta Freight + $5.00 -$5.00\n",
        beginning="$20.00", credits="+ $5.00", debits="$30.00", ending="-$5.00",
    ))
    assert statement is not None
    assert [t.amount for t in statement.transactions] == [-30.00, 5.00]
    assert statement.transactions[0].running_balance == -10.00
    assert statement.ending_balance == -5.00
    assert reconcile(statement).ok


def test_found_excludes_pending_rows_and_still_closes_the_walk():
    """A pending row prints `--` in both the Date and the Balance column and
    the issuer states it is excluded from the balance. Booking it would break
    the ledger against the bank's own total."""
    statement = found_lead.parse_found_lead_statement(found_document(
        "-- Gamma Retail - $99.00 --\n"
        "Transactions\nDate Description Amount Balance\n"
        "02/04/26 Alpha Supply - $30.00 $70.00\n",
        beginning="$100.00", credits="+ $0.00", debits="$30.00", ending="$70.00",
        sections=("Pending transactions",), disclaimer=_FOUND_DISCLAIMER,
    ))
    assert statement is not None
    assert len(statement.transactions) == 1
    assert reconcile(statement).ok


def test_found_refuses_a_row_that_is_pending_in_one_column_only():
    assert found_lead.parse_found_lead_statement(found_document(
        "-- Gamma Retail - $99.00 $1.00\n",
        sections=("Pending transactions",),
    )) is None


def test_found_refuses_a_pending_row_printed_in_the_settled_grid():
    assert found_lead.parse_found_lead_statement(found_document(
        "-- Gamma Retail - $99.00 --\n",
        sections=("Transactions",),
    )) is None


def test_found_does_not_deduct_the_fee_a_second_time():
    """The printed Fees figure is a memo inside `Purchases & other debits`;
    the summary identity closes without subtracting it again."""
    statement = found_lead.parse_found_lead_statement(found_document(
        "02/04/26 Alpha Supply - $30.00 $70.00\n",
        beginning="$100.00", credits="+ $0.00", debits="$30.00", fees="$5.00", ending="$70.00",
    ))
    assert statement is not None
    assert statement.stated_service_charge == 5.00
    assert reconcile(statement).summary_ok is True


def test_the_month_to_date_disclaimer_separates_the_two_found_registrations():
    settled = found_document("02/04/26 Alpha Supply - $30.00 $70.00\n",
                             beginning="$100.00", debits="$30.00", ending="$70.00")
    activity = found_document("02/04/26 Alpha Supply - $30.00 $70.00\n",
                              title="Activity (Month to Date)",
                              beginning="$100.00", debits="$30.00", ending="$70.00",
                              disclaimer=_FOUND_DISCLAIMER)
    assert found_lead.detect(settled).claims
    assert not found_lead.activity_detect(settled).claims
    assert found_lead.activity_detect(activity).claims
    # EXCLUDING, so the closed-statement registration scores a hard zero rather
    # than merely falling short — the two can never resolve `ambiguous`.
    assert found_lead.detect(activity).score == 0.0


def test_found_reports_a_header_period_that_disagrees_with_the_balance_labels():
    document = found_document(
        "02/04/26 Alpha Supply - $30.00 $70.00\n",
        beginning="$100.00", debits="$30.00", ending="$70.00",
        period="February 1 to February 27, 2026",
    )
    statement = found_lead.parse_found_lead_statement(document)
    assert statement is not None
    assert found_lead.printed_period_contradictions(document, statement)


# ===========================================================================
# Brex
# ===========================================================================

def brex_document(credit_rows: str, debit_rows: str, *, beginning="$0.00",
                  additions="$0.00", subtractions="-$0.00", fees="-",
                  ending="$0.00", credit_total=None, debit_total=None) -> str:
    return (
        "Apr 1 - Apr 30, 2026\n"
        "Account Number: 63325646\n"
        "Northwind Trading checking account\n"
        "Checking provided by Column N.A., Member FDIC\n"
        "support@brex.com Account Statement\n"
        "Account Summary\n"
        "This Period Year-to-Date\n"
        f"Beginning Account Balance {beginning} $9,999.99\n"
        f"Additions {additions} $9,999.99\n"
        f"Deposits & Credits {additions} $9,999.99\n"
        f"Subtractions {subtractions} -$9,999.99\n"
        f"Withdrawals & Debits {subtractions} -$9,999.99\n"
        f"Fees & Charges {fees} -\n"
        f"Ending Account Balance {ending} {ending}\n"
        "Activity - Deposits & Credits\n"
        "Date From Method Amount\n"
        + credit_rows +
        f"Total Deposits & Credits {credit_total if credit_total is not None else additions}\n"
        "Activity - Withdrawals & Debits\n"
        "Date To Method Amount\n"
        + debit_rows +
        f"Total Withdrawals & Debits {debit_total if debit_total is not None else subtractions}\n"
        "Page 1 of 1\n"
    )


def test_brex_takes_this_period_and_not_the_year_to_date_column():
    statement = brex.parse_brex_statement(brex_document(
        "4/3 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    ))
    assert statement is not None
    assert statement.beginning_balance == 100.00
    assert statement.stated_total_credits == 500.00
    assert statement.stated_total_debits == 200.00
    assert reconcile(statement).summary_ok is True


def test_brex_reads_a_nil_dash_as_zero():
    """Brex's own zero glyph. Read as "absent", the statement loses its opening
    balance and `analysis.adb` derives one from the closing figure — which
    makes the ledger identity reconcile against itself."""
    statement = brex.parse_brex_statement(brex_document(
        "4/3 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="-", additions="$500.00", subtractions="-$200.00", ending="$300.00",
    ))
    assert statement is not None
    assert statement.beginning_balance == 0.0
    assert statement.stated_service_charge == 0.0
    assert reconcile(statement).summary_ok is True


def test_brex_reads_a_row_whose_counterparty_pushed_the_amount_onto_the_next_line():
    statement = brex.parse_brex_statement(brex_document(
        "4/3 A VERY LONG COUNTERPARTY NAME THAT FILLS THE COLUMN\nWire $500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    ))
    assert statement is not None
    assert len(statement.transactions) == 2
    assert statement.transactions[0].amount == 500.00
    assert statement.transactions[0].description.endswith("Wire")


def test_brex_reopens_a_grid_on_the_column_header_after_a_page_break():
    statement = brex.parse_brex_statement(brex_document(
        "4/3 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$150.00\n"
        "Page 2 of 3\n"
        "Date To Method Amount\n"
        "4/7 Gamma Retail ACH -$50.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    ))
    assert statement is not None
    assert len(statement.transactions) == 3


def test_brex_refuses_a_row_whose_amount_never_arrived():
    assert brex.parse_brex_statement(brex_document(
        "4/3 Alpha Supply\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    )) is None


def test_brex_publishes_no_running_balances_because_none_are_printed():
    statement = brex.parse_brex_statement(brex_document(
        "4/3 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    ))
    assert statement is not None
    assert all(t.running_balance is None for t in statement.transactions)


def test_brex_reports_a_row_printed_in_the_grid_that_contradicts_its_sign():
    """The grid heading and the sign are two independent declarations of one
    row's direction. Where they disagree the document contradicts itself, and
    that is a finding for a human rather than something to resolve by
    preferring one of them."""
    document = brex_document(
        "4/3 Alpha Supply ACH -$500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="-$500.00", subtractions="-$200.00", ending="-$600.00",
    )
    statement = brex.parse_brex_statement(document)
    assert statement is not None
    assert any("grid but carries" in note
               for note in brex.printed_total_contradictions(document, statement))


def test_brex_reports_a_section_total_that_disagrees_with_the_summary():
    document = brex_document(
        "4/3 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
        credit_total="$501.00",
    )
    statement = brex.parse_brex_statement(document)
    assert statement is not None
    assert any("grid totals" in note
               for note in brex.printed_total_contradictions(document, statement))


# ===========================================================================
# Cross-family negatives
# ===========================================================================

@pytest.mark.parametrize("parser", [
    mercury.parse_mercury_statement,
    found_lead.parse_found_lead_statement,
    brex.parse_brex_statement,
])
def test_no_fintech_parser_claims_another_fintech_layout(parser):
    """Three platforms, two of them sponsored by the same bank. The sponsor
    line is corroborating evidence at most; the issuer's own furniture is what
    each parser claims on."""
    documents = [
        mercury_document(f"Apr 02 Alpha {MARK}ACH In $10.00 $10.00\n", deposits="$10.00", ending="$10.00"),
        found_document("02/04/26 Alpha Supply - $30.00 $70.00\n",
                       beginning="$100.00", debits="$30.00", ending="$70.00"),
        brex_document("4/3 Alpha Supply ACH $500.00\n", "4/6 Beta ACH -$200.00\n",
                      beginning="$100.00", additions="$500.00",
                      subtractions="-$200.00", ending="$400.00"),
    ]
    parsed = [parser(document) is not None for document in documents]
    assert sum(parsed) == 1, "a fintech parser claimed more than one platform's layout"

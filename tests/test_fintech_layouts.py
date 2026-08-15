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
MARK = "\ue001"


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


def test_mercury_reads_a_description_that_ends_in_a_money_token():
    """Pins the CURRENT mechanism — the row splits at the printed Type mark —
    on a description ending in money with the balance column empty.

    **This test does not discriminate against the pattern it replaced, and the
    docstring said otherwise until Ocean's review caught it.** Measured over
    nine ambiguous shapes, the earlier pattern (non-greedy body, `\\s+`
    separator, mandatory mark check) produced the IDENTICAL split on every one:
    its `\\s+` and the mark requirement already forced this reading. The
    mark-split is a structural clarification, not a defect fix, and §FT6 of the
    log has been corrected to say so.

    It is kept because the property is worth holding: it is what stops the
    pattern being "simplified" to "the last two money tokens", which §RBCCIBC
    lost nine documents to. The two tests below DO discriminate — they pin
    shapes where the mark-split, as first written, was wrong."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Refund of $5.00 fee {MARK}ACH Pull -$10.00\n"
        f"Beta Freight {MARK}ACH Pull -$10.00 $80.00\n",
        beginning="$100.00", withdrawals="-$20.00", deposits="$0.00", ending="$80.00",
    ))
    assert statement is not None
    assert statement.transactions[0].amount == -10.00
    assert statement.transactions[0].running_balance is None
    assert statement.transactions[0].description == "Refund of $5.00 fee ACH Pull"
    assert reconcile(statement).ok


def test_mercury_keeps_the_date_when_the_description_cell_is_empty():
    """A row whose Description cell is blank prints the Type mark straight
    after the date. The mark-split, as first written, required a non-space
    character before the mark — so the engine backtracked and swallowed
    `Apr 02` INTO the description, costing the row its posting day and moving
    an end-of-day balance onto the wrong date.

    Found by asking (at Ocean's prompting) whether the new pattern really
    differed from the old one: it did, and here it was worse."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 {MARK}ACH Pull -$10.00 $90.00\n",
        beginning="$100.00", withdrawals="-$10.00", deposits="$0.00", ending="$90.00",
    ))
    assert statement is not None
    assert statement.transactions[0].date == "2026-04-02"
    assert statement.transactions[0].description == "ACH Pull"


def test_no_private_use_glyph_survives_into_a_published_description():
    """A row printing TWO icons. The mark-split keeps the last one as the
    column boundary, which left the FIRST sitting raw inside the description —
    a font-private codepoint in a published financial field, rendering as
    whatever the reader's font happens to map it to.

    The glyph is column furniture in every position, so it is scrubbed in every
    position."""
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Two {MARK}marks {MARK}Type -$10.00 $90.00\n",
        beginning="$100.00", withdrawals="-$10.00", deposits="$0.00", ending="$90.00",
    ))
    assert statement is not None
    description = statement.transactions[0].description
    assert description == "Two marks Type"
    assert not any("\ue000" <= c <= "\uf8ff" for c in description)


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


@pytest.mark.parametrize("minus", ["-", "\u2212", "\u2013"])
def test_mercury_reads_all_three_printed_minus_glyphs(minus):
    """The same generator prints ASCII hyphen, U+2212 and U+2013 as the sign,
    and a reader that knows only one of them sign-flips the others.

    Exactly three, measured: over the 31 archive statements the character
    immediately before a `$` is U+2212 1,202 times, U+2013 687 and U+002D 13,
    and U+2014 EM DASH zero times. The em dash was admitted here by a shadowed
    second definition of the shared class and is now ruled out (W3 §MGD); the
    test below is what it does instead.
    """
    statement = mercury.parse_mercury_statement(mercury_document(
        f"Apr 02 Alpha Supply {MARK}ACH Pull {minus}$10.00 $90.00\n",
        beginning="$100.00", withdrawals=f"{minus}$10.00", deposits="$0.00", ending="$90.00",
    ))
    assert statement is not None
    assert statement.transactions[0].amount == -10.00
    assert statement.transactions[0].direction == "debit"
    assert reconcile(statement).ok


def test_an_em_dash_is_not_a_sign_and_the_document_declines():
    """THE RULING (W3 §MGD), at the parser, with its real mechanism named.

    An em dash before the currency symbol used to make the amount NEGATIVE,
    because ``SIGNED_MONEY_TOKEN`` was built from a shadowed four-glyph class
    while every other consumer of that name held a narrower one. The em dash
    is now outside the sign class on the archive's own evidence: it stands in
    a sign position on exactly two documents, both failing, and on one of them
    it is an empty-column placeholder in front of a POSITIVE balance.

    What that costs this layout is stated exactly rather than optimistically.
    The row does NOT refuse at the pattern: ``type`` is a lazy any-character
    group, so it absorbs ``ACH Pull —$10.00`` and the BALANCE cell is read as
    the amount — a worse reading than either sign, not a cleaner one. What
    refuses is the arithmetic: the balance walk no longer reaches the printed
    end-of-day balance, no average daily balance is produced, and
    ``telemetry.record.classify_outcome`` turns that into ``withheld_adb``.
    Nothing publishes, which is the same guarantee
    `test_a_tampered_sign_glyph_publishes_nothing` pins for a dropped sign.

    Zero archive documents print the shape (0 of 3,453 amounts over the 31
    statements), so this moves nothing today. It is pinned because the
    fail-closed depends on the ARITHMETIC rather than on the grammar, and a
    future row shape without a balance column would not have that backstop.
    Carried for Ocean as §MGD MGD-C2.
    """
    from analysis.metrics import compute_metrics

    statement = mercury.parse_mercury_statement(_two_row_document(debit_sign="\u2014"))
    assert statement is not None
    # the mis-read, named rather than glossed
    assert statement.transactions[1].amount == 130.00
    assert "\u2014$10.00" in statement.transactions[1].description
    # ... and the arithmetic that refuses it
    recon = reconcile(statement)
    assert not recon.ok
    assert compute_metrics(statement, trust_stated_summary=recon.summary_ok,
                           trust_running_balances=recon.ok).average_daily_balance is None


def test_the_spaced_em_dash_is_a_third_shape_with_its_own_mechanism():
    """`— $10.00` is not the same defect as `—$10.00`, and reading one
    test as covering both would be wrong.

    ``SIGNED_MONEY_TOKEN`` carries an optional space between sign and symbol,
    so the two shapes fail differently once the em dash leaves the class:

      welded  `—$10.00`   the whole cell is swallowed by ``type``; the
                            BALANCE column becomes the amount   -> +130.00
      spaced  `— $10.00`  only the dash is swallowed; the amount cell is
                            still read, unsigned                -> +10.00

    Both are a debit booked as a credit and both are caught by the balance
    walk, but by different arithmetic, and the magnitudes differ. Pinned so
    the second is not assumed from the first.
    """
    from analysis.metrics import compute_metrics

    statement = mercury.parse_mercury_statement(_two_row_document(
        debit_sign="\u2014 "))
    assert statement is not None
    assert statement.transactions[1].amount == 10.00        # not 130.00
    assert statement.transactions[1].direction == "credit"  # the mis-read
    recon = reconcile(statement)
    assert not recon.ok
    assert compute_metrics(statement, trust_stated_summary=recon.summary_ok,
                           trust_running_balances=recon.ok).average_daily_balance is None


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
                  ending="$0.00", credit_total=None, debit_total=None,
                  appendix="") -> str:
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
        + appendix +
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


# ===========================================================================
# A date-shaped token that is not a date
# ===========================================================================

def test_found_refuses_a_date_cell_that_no_calendar_can_hold():
    """`13/45/26` matches the row pattern's date shape perfectly. Converting it
    without a guard raises out of `parse` — a `ParserCrashError` in
    deterministic mode, which is the defect class discovery hit on 17
    documents. A Date cell holding no date means the columns were not read as
    printed, so the document is refused."""
    assert found_lead.parse_found_lead_statement(found_document(
        "13/45/26 Alpha Supply - $30.00 $70.00\n",
        beginning="$100.00", debits="$30.00", ending="$70.00",
    )) is None


def test_brex_refuses_a_date_cell_that_no_calendar_can_hold():
    assert brex.parse_brex_statement(brex_document(
        "13/45 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    )) is None


@pytest.mark.parametrize("parser,document", [
    (found_lead.parse_found_lead_statement,
     lambda: found_document("13/45/26 Alpha Supply - $30.00 $70.00\n",
                            beginning="$100.00", debits="$30.00", ending="$70.00")),
    (brex.parse_brex_statement,
     lambda: brex_document("13/45 Alpha Supply ACH $500.00\n",
                           "4/6 Beta ACH -$200.00\n", beginning="$100.00",
                           additions="$500.00", subtractions="-$200.00", ending="$400.00")),
])
def test_a_bad_date_declines_rather_than_raising(parser, document):
    """The refusal must be a `None`, not an exception: W3-1's seam would record
    it as `parser_exception` and file our own crash as a document defect."""
    assert parser(document()) is None


# ===========================================================================
# Mercury glyph ablations (asked for by Ocean out of the DECLINES-C cell)
# ===========================================================================
#
# The DECLINES-C finding is that a platform can encode its SIGNS as private-use
# codepoints, that no shared translation table across platforms is possible,
# and that a reader which maps them must certify the mapping against the
# document's own arithmetic.
#
# Mercury does not do that, and it is worth pinning that it does not. Measured
# over all 31 statements and their 3,453 printed amounts: the character
# immediately before a `$` is MINUS SIGN 1,202 times, EN DASH 687, HYPHEN-MINUS
# 13, and nothing at all on the 1,551 credits. It is a PUA codepoint ZERO
# times, and there are zero parenthesised negatives. All 2,696 PUA occurrences
# are followed by TEXT — they are the icon at the head of the Type column, and
# this parser reads them as a column boundary and never as a symbol.
#
# The three ablations below are what make those two claims falsifiable.

_MARK_IN = "\ue001"       # the icon Mercury sets on a credit's Type cell
_MARK_OUT = "\ue002"      # ... and on a debit's
_MARK_FOREIGN = "\uf8f0"  # a PUA codepoint from nowhere in this archive


def _two_row_document(mark_credit=_MARK_IN, mark_debit=_MARK_OUT, debit_sign="-"):
    return mercury_document(
        f"Apr 02 Payer Co {mark_credit}ACH In $40.00\n"
        f"Vendor Co {mark_debit}ACH Pull {debit_sign}$10.00 $130.00\n",
        beginning="$100.00", withdrawals="-$10.00", deposits="$40.00", ending="$130.00",
    )


def test_the_type_icon_carries_no_direction_permuting_it_changes_nothing():
    """THE ablation for this cell's central claim. Swap the "in" icon for the
    "out" icon on both rows — a permutation that would invert every direction
    if the glyph were being read as a sign — and the published payload must be
    byte-identical, because direction comes from the printed sign alone.

    If someone ever wires the icon into the direction rule, this test fails.
    """
    baseline = mercury.parse_mercury_statement(_two_row_document())
    swapped = mercury.parse_mercury_statement(
        _two_row_document(mark_credit=_MARK_OUT, mark_debit=_MARK_IN)
    )
    assert baseline is not None and swapped is not None
    assert baseline.model_dump() == swapped.model_dump()
    assert [t.direction for t in baseline.transactions] == ["credit", "debit"]


def test_an_unknown_private_use_glyph_still_marks_the_column():
    """No mapping is assumed and no table is consulted: the mark is read as
    INK. A codepoint this archive has never printed divides the columns exactly
    as Mercury's own does, which is what makes the rule issuer-neutral rather
    than a memorized list of four codepoints."""
    baseline = mercury.parse_mercury_statement(_two_row_document())
    foreign = mercury.parse_mercury_statement(
        _two_row_document(mark_credit=_MARK_FOREIGN, mark_debit=_MARK_FOREIGN)
    )
    assert baseline is not None and foreign is not None
    assert baseline.model_dump() == foreign.model_dump()


def test_a_tampered_sign_glyph_publishes_nothing():
    """The signs are CERTIFIED by the document's own arithmetic, not trusted.
    Drop the minus from one debit — the only change — and the row becomes a
    credit, the balance walk no longer reaches the printed end-of-day balance,
    and the printed totals no longer match the ledger. Nothing publishes.

    This is what makes the three-glyph minus reading safe: a wrong sign cannot
    survive to the output, whichever glyph it was printed with."""
    from analysis.metrics import compute_metrics

    statement = mercury.parse_mercury_statement(_two_row_document(debit_sign=""))
    # The grid still READS — the row shape is intact and only the sign moved —
    # which is exactly what makes this the dangerous case rather than an
    # obvious one.
    assert statement is not None
    recon = reconcile(statement)
    assert not recon.ok
    assert recon.continuity_breaks > 0 or recon.summary_ok is False
    # And nothing publishes: no average daily balance is produced, which is
    # what `telemetry.record.classify_outcome` turns into `withheld_adb`. The
    # intact document validates through the same path.
    metrics = compute_metrics(statement, trust_stated_summary=recon.summary_ok,
                              trust_running_balances=recon.ok)
    assert metrics.average_daily_balance is None

    intact = mercury.parse_mercury_statement(_two_row_document())
    intact_recon = reconcile(intact)
    assert intact_recon.ok
    assert compute_metrics(intact, trust_stated_summary=intact_recon.summary_ok,
                           trust_running_balances=True).average_daily_balance is not None


@pytest.mark.parametrize("minus", ["-", "\u2212", "\u2013"])
def test_every_printed_minus_glyph_certifies_against_the_same_arithmetic(minus):
    """The three glyphs are one column. Each must produce the SAME statement,
    and each must reconcile — the arithmetic is what certifies the reading."""
    statement = mercury.parse_mercury_statement(_two_row_document(debit_sign=minus))
    assert statement is not None
    assert statement.transactions[1].amount == -10.00
    assert reconcile(statement).ok


# ===========================================================================
# The MTD boundary — both leak directions (Ocean's adversarial review)
# ===========================================================================
#
# The split between `found_lead` and `found_lead_activity` first rested on a
# flat substring of the disclaimer clause. The clause is FLOWED body text, so
# the PDF breaks it wherever it reaches the margin, and the reviewer proved the
# test leaked both ways. The boundary is now the printed TITLE, which is a
# generated line of its own and does not wrap. These two tests are the leaks.

#: The disclaimer as the PDF actually breaks it on a real month-to-date
#: document: the clause spans a line wrap, so no single line — and no flat
#: uppercased substring of the whole text — contains it intact.
_WRAPPED_DISCLAIMER = (
    "The information in this document is not a bank statement and therefore\n"
    "should not be relied upon as a bank statement.\n"
)


def test_a_month_to_date_document_whose_clause_wraps_never_validates():
    """THE UNSAFE LEAK, pinned. Under the substring boundary this document was
    claimed by `found_lead` as `formal_statement=True` and published
    `validated/approved` with no flag at all — the platform asserting a
    month-to-date view is a closed bank statement, on a document that says
    otherwise in words it happened to break across two lines.

    The title is what settles it, so the wrap cannot reach the decision.
    """
    document = found_document(
        "02/04/26 Alpha Supply - $30.00 $70.00\n",
        title="Activity (Month to Date)",
        beginning="$100.00", debits="$30.00", ending="$70.00",
        disclaimer=_WRAPPED_DISCLAIMER,
    )
    # the clause really is unreachable as a flat substring
    assert "is not a bank statement and therefore should not be relied upon" not in document
    # `found_lead` must not merely fail to claim — it must be EXCLUDED
    assert found_lead.detect(document).score == 0.0
    assert found_lead.detect(document).excluded_by == "month_to_date_title"
    assert found_lead.activity_detect(document).claims


def test_a_closed_statement_that_quotes_the_clause_is_not_demoted():
    """THE OTHER LEAK. A closed statement carrying the sentence in a footnote —
    a disclosure change, a quoted policy — was demoted to review by the
    substring boundary. Its title says what it is."""
    document = found_document(
        "02/04/26 Alpha Supply - $30.00 $70.00\n",
        beginning="$100.00", debits="$30.00", ending="$70.00",
        disclaimer=(
            "Note: unlike our month-to-date view, which is not a bank statement "
            "and therefore should not be relied upon as a bank statement, this "
            "document is your statement of record.\n"
        ),
    )
    assert found_lead.detect(document).claims
    assert not found_lead.activity_detect(document).claims
    statement = found_lead.parse_found_lead_statement(document)
    assert statement is not None
    assert reconcile(statement).ok


def test_neither_registration_claims_a_found_document_with_no_printed_title():
    """The title is REQUIRED on both, so a Found document whose title line this
    reader cannot see is claimed by neither and fails closed — rather than one
    of them taking it by default."""
    document = found_document(
        "02/04/26 Alpha Supply - $30.00 $70.00\n",
        title="Statement Of Account",  # not a title this issuer prints
        beginning="$100.00", debits="$30.00", ending="$70.00",
    )
    assert not found_lead.detect(document).claims
    assert not found_lead.activity_detect(document).claims


# ===========================================================================
# Brex: a dated posting this reader cannot place is a REFUSAL, not a skip
# (alignment with the sibling parsers, from Ocean's review)
# ===========================================================================

def test_brex_refuses_a_posting_that_follows_mid_page_furniture():
    """Furniture closes a grid, and Brex reopens it by REPRINTING the column
    header. A dated posting arriving after the furniture with no header before
    it is a row this reader has lost its place on.

    Before the alignment this was silently skipped — and a skipped row is
    invisible downstream, because the rows that remain still sum to their own
    printed total. mercury.py and found_lead.py already refused here."""
    assert brex.parse_brex_statement(brex_document(
        "4/3 Alpha Supply ACH $500.00\n",
        "4/6 Beta Freight ACH -$150.00\n"
        "Page 2 of 3\n"
        "4/7 Gamma Retail ACH -$50.00\n",   # no column header reopened the grid
        beginning="$100.00", additions="$500.00", subtractions="-$200.00", ending="$400.00",
    )) is None


def test_brex_does_not_book_the_deposited_checks_appendix_twice():
    """Brex re-prints its check deposits in a `Deposited checks` section with
    no column header. They are the SAME two deposits the grid already booked,
    so booking them again would double-count them against the bank's own
    total — and stepping over them silently is the defect this cell refuses
    everywhere else. The heading is recognised, and the rows are checked."""
    statement = brex.parse_brex_statement(brex_document(
        "4/3 Rakuten Check $81.92\n"
        "4/3 Novi Commons Check $675.00\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$756.92", subtractions="-$200.00", ending="$656.92",
        appendix="Deposited checks\n04/03 Check from Rakuten $81.92\n"
                 "04/03 Check from Novi Commons $675.00\n",
    ))
    assert statement is not None
    assert len(statement.transactions) == 3
    assert sum(x.amount for x in statement.transactions if x.amount > 0) == 756.92
    assert reconcile(statement).ok


def test_brex_refuses_an_appendix_row_the_grid_never_booked():
    """The appendix is only safe because it is CHECKED. A check listed there
    that no grid row accounts for is a posting that was dropped, and the
    document is refused rather than published short."""
    assert brex.parse_brex_statement(brex_document(
        "4/3 Rakuten Check $81.92\n",
        "4/6 Beta Freight ACH -$200.00\n",
        beginning="$100.00", additions="$81.92", subtractions="-$200.00", ending="-$18.08",
        appendix="Deposited checks\n04/03 Check from Rakuten $81.92\n"
                 "04/04 Check from Nobody $999.00\n",
    )) is None

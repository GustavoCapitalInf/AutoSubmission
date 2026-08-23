"""W3 §LILI — the Lili / Sunrise Banks business-checking printing.

EVERY FIXTURE IN THIS FILE IS INVENTED. No amount, name, account number,
authorization code or date from any archive document appears here, and none
of the out-of-period blocks the archive's tampered members carry is
reproduced: the out-of-period rows below are made up, in a year and with
figures that occur nowhere in the family.

The document below is the shape `analysis/lili.py` publishes, and it is
arithmetically closed three ways so that a mutant can only break it:

    beginning 100.00 + deposits 500.00 - withdrawals 300.00 - fees 10.00
        == ending 290.00                       (the printed summary closes)
    100.00 -> -200.00 -> 300.00 -> 290.00      (the printed chain walks)
    rows: credits 500.00, debits 310.00        (rows == withdrawals + fees)
"""
from __future__ import annotations

import pytest

from analysis.lili import DETECTION_MARKERS, detect, parse_lili_statement

# ---------------------------------------------------------------------------
# The invented documents
# ---------------------------------------------------------------------------

HEADER = (
    "Account Number Statement Period 999900000000 "
    "1 March, 2026 - 31 March, 2026\n"
)
SUMMARY = (
    "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 March, 2026 $100.00\n"
    "Deposits and other credits $500.00\n"
    "Withdrawals and other debits $-300.00\n"
    "Fees $-10.00\n"
    "Ending balance on 31 March, 2026 $290.00\n"
)
LEDGER = (
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "03/02/2026 111111111 A MERCHANT SOMEWHERE STUS $-300.00 $-200.00\n"
    "03/20/2026 222222222 Wire Transfer $500.00 $300.00\n"
    "03/31/2026 333333333 Plan Fee (Effective Date 03/09/2026) $-10.00 $290.00\n"
)
DISCLOSURE = (
    "Lili is a financial technology company, not a bank. Banking services "
    "provided by Sunrise Banks N.A., Member FDIC. support@lili.co\n"
)

SKIN_A = HEADER + SUMMARY + LEDGER + DISCLOSURE

#: The credit-builder printing: three money columns (checking, collateral and
#: their total) and a SECOND ledger with its own running balance. Both halves
#: close on their own; the schema carries one account, so it is refused.
SKIN_A_TWO_ACCOUNTS = (
    "Account Number Statement Period 999900000000 "
    "1 March, 2026 - 31 March, 2026\n"
    "Checking Account Summary Checking Account\n"
    "BusinessBuild\n"
    "Collateral\n"
    "Beginning balance on 1 March, 2026 $100.00 $40.00 $140.00\n"
    "Deposits and other credits $500.00 $20.00 $520.00\n"
    "Withdrawals and other debits $-300.00 $-30.00 $-330.00\n"
    "Fees $-10.00 $0.00 $-10.00\n"
    "Ending balance on 31 March, 2026 $290.00 $30.00 $320.00\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "03/02/2026 111111111 A MERCHANT SOMEWHERE STUS $-300.00 $-200.00\n"
    "03/20/2026 222222222 Wire Transfer $500.00 $300.00\n"
    "03/31/2026 333333333 Plan Fee (Effective Date 03/09/2026) $-10.00 $290.00\n"
    "Business Build Collateral Activity\n"
    "Date Authorization Code Description Amount Balance\n"
    "03/10/2026 444444444 Card collateral deposit $20.00 $60.00\n"
    "03/11/2026 555555555 Card collateral withdrawal $-30.00 $30.00\n"
) + DISCLOSURE

#: The second printing: header order reversed, summary labels and figures on
#: SEPARATE lines, postings shredded across lines with a floating network tag,
#: and a block of rows dated outside the period the document declares. The
#: figures, codes and dates are invented.
SKIN_B_OUT_OF_PERIOD = (
    "Statement Period Account Number\n"
    "999900000000              01 March, 2026 - 31 March, 2026\n"
    "Summary\n"
    "Amount\n"
    "Beginning balance on 01 March, 2026\n"
    "$100.00\n"
    "Deposits and other credits\n"
    "$500.00\n"
    "Withdrawals and other debits\n"
    "$300.00\n"
    "Fees\n"
    "$0.00 $0.00\n"
    "Activity\n"
    "Amount Balance\n"
    "Date\n"
    "Description Authorization Code\n"
    "A MERCHANT SOMEWHERE\n"
    "03/02/2026\n"
    "777777777\n"
    "$-300.00  $-200.00\n"
    "VS\n"
    "AN OLDER MERCHANT\n"
    "07/14/2019\n"
    "888888888\n"
    "$-11.00 $-211.00\n"
    "PM\n"
    "Ending balance on      31 March, 2026\n"
    "$290.00\n"
    "For questions regarding account history: support@lili.co\n"
)


#: Three money columns and ONE ledger. Nothing but the §L-1 COLUMN reading can
#: refuse it: the checking column closes on itself, the single chain walks, and
#: the gross debits total to the two checking debit terms.
SKIN_A_THREE_COLUMNS_ONE_LEDGER = (
    HEADER
    + "Checking Account Summary Checking Account\n"
    "BusinessBuild\n"
    "Collateral\n"
    "Beginning balance on 1 March, 2026 $100.00 $40.00 $140.00\n"
    "Deposits and other credits $500.00 $20.00 $520.00\n"
    "Withdrawals and other debits $-300.00 $-30.00 $-330.00\n"
    "Fees $-10.00 $0.00 $-10.00\n"
    "Ending balance on 31 March, 2026 $290.00 $30.00 $320.00\n"
    + LEDGER + DISCLOSURE
)

#: One money column and TWO ledger column heads, the second carrying no rows.
#: Nothing but the §L-1 LEDGER reading can refuse it: the summary, the chain
#: and the gross debits are the clean document's.
SKIN_A_SECOND_LEDGER_HEAD = (
    HEADER + SUMMARY + LEDGER
    + "Business Build Collateral Activity\n"
    "Date Authorization Code Description Amount Balance\n"
    + DISCLOSURE
)

#: A summary whose Withdrawals term is printed as an INFLOW while its Fees term
#: absorbs the difference. Every arithmetic gate closes on it.
SKIN_A_WITHDRAWALS_PRINTED_POSITIVE = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 March, 2026 $100.00\n"
    "Deposits and other credits $500.00\n"
    "Withdrawals and other debits $50.00\n"
    "Fees $-350.00\n"
    "Ending balance on 31 March, 2026 $300.00\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "03/02/2026 111111111 A MERCHANT SOMEWHERE STUS $-300.00 $-200.00\n"
    "03/20/2026 222222222 Wire Transfer $500.00 $300.00\n"
    + DISCLOSURE
)

#: The same for the Fees term: printed as a credit, every arithmetic gate still
#: closing.
SKIN_A_FEES_PRINTED_POSITIVE = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 March, 2026 $100.00\n"
    "Deposits and other credits $500.00\n"
    "Withdrawals and other debits $-300.00\n"
    "Fees $10.00\n"
    "Ending balance on 31 March, 2026 $310.00\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "03/02/2026 111111111 A MERCHANT SOMEWHERE STUS $-290.00 $-190.00\n"
    "03/20/2026 222222222 Wire Transfer $500.00 $310.00\n"
    + DISCLOSURE
)


def _swap(document: str, before: str, after: str) -> str:
    assert before in document, before
    return document.replace(before, after, 1)


# ---------------------------------------------------------------------------
# Detection — both printings are claimed, on purpose
# ---------------------------------------------------------------------------

def test_the_registration_rests_on_three_required_markers():
    assert [marker.id for marker in DETECTION_MARKERS] == [
        "issuer_support_address",
        "summary_credit_term",
        "summary_debit_term",
    ]
    assert all(marker.kind == "required" for marker in DETECTION_MARKERS)


@pytest.mark.parametrize(
    "document", [SKIN_A, SKIN_A_TWO_ACCOUNTS, SKIN_B_OUT_OF_PERIOD],
    ids=["skin_a", "skin_a_two_accounts", "skin_b"],
)
def test_every_printing_of_this_platform_is_claimed(document):
    """Including the one that is then refused: a tampered document must be
    named by the parser that recognised it, not left unclaimed."""
    assert detect(document).claims


def test_a_document_without_the_platforms_support_address_is_not_claimed():
    assert not detect(_swap(SKIN_A, "support@lili.co", "support@example.test")).claims


def test_the_summary_terms_alone_are_not_a_claim():
    """`Deposits and other credits` is a core-processor section name too."""
    assert not detect(SUMMARY + LEDGER).claims


# ---------------------------------------------------------------------------
# The published statement
# ---------------------------------------------------------------------------

def test_the_clean_printing_publishes_its_summary_and_its_ledger():
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert statement.bank == "Lili"
    assert statement.account_number == "999900000000"
    assert statement.period_start == "2026-03-01"
    assert statement.period_end == "2026-03-31"
    assert statement.days_in_period == 31
    assert statement.beginning_balance == 100.00
    assert statement.ending_balance == 290.00
    assert statement.stated_total_credits == 500.00


def test_the_debit_total_excludes_the_fee_term_the_document_prints_separately():
    """This platform's `Withdrawals and other debits` term does NOT include
    its `Fees` term — the rows prove it — so the two are published apart."""
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert statement.stated_total_debits == 300.00
    assert statement.stated_service_charge == 10.00
    debited = sum(-t.amount for t in statement.transactions if t.amount < 0)
    assert debited == statement.stated_total_debits + statement.stated_service_charge


def test_every_posting_carries_the_balance_the_document_printed_after_it():
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert [t.running_balance for t in statement.transactions] == [-200.00, 300.00, 290.00]
    assert [t.direction for t in statement.transactions] == ["debit", "credit", "debit"]
    assert [t.date for t in statement.transactions] == [
        "2026-03-02", "2026-03-20", "2026-03-31",
    ]


def test_the_reader_claims_no_currency_and_no_product_name_of_its_own():
    """The family prints neither, so neither is invented: `currency` stays on
    the schema default and `account_name` stays None."""
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert statement.currency == "USD"
    assert statement.currency_source == "schema_default"
    assert statement.account_name is None
    assert statement.stated_daily_balances == []
    assert statement.stated_credit_count is None
    assert statement.stated_debit_count is None


def test_a_description_that_contains_a_figure_does_not_steal_the_amount_column():
    """Merchant, city and country run together with no delimiter on this
    template, so the amount is the SECOND-TO-LAST money token of the line and
    the balance is the last — never the first pair that appears."""
    statement = parse_lili_statement(
        _swap(SKIN_A, "Wire Transfer $500.00", "Wire Transfer REF $9.99 $500.00")
    )
    assert statement is not None
    assert statement.transactions[1].amount == 500.00
    assert statement.transactions[1].running_balance == 300.00
    assert "$9.99" in statement.transactions[1].description


# ---------------------------------------------------------------------------
# §INTEGRITY — a date the document prints outside the period it declares
# ---------------------------------------------------------------------------

def test_a_posting_dated_outside_the_printed_period_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "03/02/2026 111111111", "03/02/2019 111111111")
    ) is None


def test_the_shredded_printing_is_refused_for_printing_rows_from_another_period():
    """The archive's five tampered members reach this gate; the fixture is an
    invented document of the same SHAPE, never a copy of one of them."""
    assert detect(SKIN_B_OUT_OF_PERIOD).claims
    assert parse_lili_statement(SKIN_B_OUT_OF_PERIOD) is None


def test_the_shredded_printing_is_still_refused_without_the_out_of_period_rows():
    """Belt and braces: even with every date inside the period, the second
    printing's summary is not line-anchored and it is refused anyway."""
    inside = _swap(SKIN_B_OUT_OF_PERIOD, "07/14/2019", "03/14/2026")
    assert detect(inside).claims
    assert parse_lili_statement(inside) is None


def test_a_posting_dated_inside_the_year_but_outside_the_period_is_refused():
    """One archive member carries a row a whole month after the period it
    declares. A gate that compared only the YEAR would read it as in-period."""
    assert parse_lili_statement(
        _swap(SKIN_A, "03/20/2026 222222222", "04/20/2026 222222222")
    ) is None


def test_a_posting_date_that_is_not_a_calendar_date_refuses_the_document():
    """`str.isdigit()` grammar admits `13/45/2026`; a calendar does not."""
    assert parse_lili_statement(
        _swap(SKIN_A, "03/20/2026 222222222", "13/45/2026 222222222")
    ) is None


def test_a_non_calendar_date_inside_a_description_refuses_the_document():
    """Away from the date column, only the §INTEGRITY gate ever looks at this
    token — and it must answer, not raise."""
    assert parse_lili_statement(
        _swap(SKIN_A, "(Effective Date 03/09/2026)", "(Effective Date 13/45/2026)")
    ) is None


def test_an_effective_date_inside_a_description_is_read_by_the_same_gate():
    """The fee rows of this template carry an effective date in their text.
    Inside the period it is fine; outside it, it refuses — measured over the
    family's 15 clean members, zero of 2,738 printed date tokens fall
    outside."""
    assert parse_lili_statement(SKIN_A) is not None
    assert parse_lili_statement(
        _swap(SKIN_A, "(Effective Date 03/09/2026)", "(Effective Date 12/09/2019)")
    ) is None


# ---------------------------------------------------------------------------
# §L-1 — the second account, read twice
# ---------------------------------------------------------------------------

def test_a_summary_that_prints_a_second_money_column_is_refused():
    """Three columns, one ledger: only the §L-1 COLUMN reading can see it —
    the checking column closes on itself and the single chain walks."""
    assert detect(SKIN_A_THREE_COLUMNS_ONE_LEDGER).claims
    assert parse_lili_statement(SKIN_A_THREE_COLUMNS_ONE_LEDGER) is None


def test_the_credit_builder_printing_as_the_archive_prints_it_is_refused():
    """Three columns AND a second ledger, the shape three archive members
    carry. Either §L-1 reading refuses it, which is why the two isolating
    documents exist beside it."""
    assert detect(SKIN_A_TWO_ACCOUNTS).claims
    assert parse_lili_statement(SKIN_A_TWO_ACCOUNTS) is None


def test_a_second_ledger_is_refused_even_when_the_summary_has_one_column():
    """The two §L-1 readings are independent: a printing that grew a ledger
    without growing a column is a shape nobody has measured. The second column
    head carries no rows on purpose — postings under it would break the chain,
    and then the chain gate rather than this one would be refusing."""
    assert parse_lili_statement(SKIN_A_SECOND_LEDGER_HEAD) is None


def test_a_ragged_summary_grid_is_refused():
    """Four terms in one column and one in three is not a grid."""
    assert parse_lili_statement(
        _swap(SKIN_A, "Fees $-10.00", "Fees $-10.00 $0.00 $-10.00")
    ) is None


# ---------------------------------------------------------------------------
# The header
# ---------------------------------------------------------------------------

def test_the_header_is_read_in_either_printed_order():
    reversed_order = _swap(
        SKIN_A,
        "Account Number Statement Period 999900000000",
        "Statement Period Account Number 999900000000",
    )
    statement = parse_lili_statement(reversed_order)
    assert statement is not None
    assert statement.account_number == "999900000000"
    assert statement.period_start == "2026-03-01"


def test_two_headers_that_disagree_refuse_the_document():
    assert parse_lili_statement(SKIN_A + HEADER.replace("999900000000", "888800000000")) is None


def test_a_header_reprinted_identically_is_corroboration_not_a_contradiction():
    statement = parse_lili_statement(SKIN_A + HEADER)
    assert statement is not None
    assert statement.account_number == "999900000000"


def test_a_period_that_ends_before_it_starts_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "1 March, 2026 - 31 March, 2026", "31 March, 2026 - 1 March, 2026")
    ) is None


def test_a_period_bound_the_calendar_does_not_have_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "1 March, 2026 - 31 March, 2026", "1 March, 2026 - 31 February, 2026")
    ) is None


def test_a_document_with_no_header_at_all_is_claimed_and_declined():
    document = SUMMARY + LEDGER + DISCLOSURE
    assert detect(document).claims
    assert parse_lili_statement(document) is None


# ---------------------------------------------------------------------------
# The summary shape and its signs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "term",
    [
        "Beginning balance on 1 March, 2026 $100.00\n",
        "Deposits and other credits $500.00\n",
        "Withdrawals and other debits $-300.00\n",
        "Fees $-10.00\n",
        "Ending balance on 31 March, 2026 $290.00\n",
    ],
)
def test_a_summary_missing_any_one_of_its_five_terms_is_refused(term):
    assert parse_lili_statement(_swap(SKIN_A, term, "")) is None


def test_a_summary_term_printed_twice_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "Fees $-10.00\n", "Fees $-10.00\nFees $-10.00\n")
    ) is None


def test_the_five_terms_must_appear_in_the_order_the_template_prints_them():
    scrambled = (
        HEADER
        + "Checking Account Summary Total Checking Amount\n"
        "Deposits and other credits $500.00\n"
        "Beginning balance on 1 March, 2026 $100.00\n"
        "Withdrawals and other debits $-300.00\n"
        "Fees $-10.00\n"
        "Ending balance on 31 March, 2026 $290.00\n"
        + LEDGER + DISCLOSURE
    )
    assert parse_lili_statement(scrambled) is None


def test_a_term_whose_figure_is_on_the_next_line_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "Deposits and other credits $500.00", "Deposits and other credits\n$500.00")
    ) is None


def test_a_withdrawals_term_printed_as_an_inflow_is_refused():
    """The archive's second printing prints its withdrawals positive. In this
    document every arithmetic gate still closes, so the printed-sign reading
    is the only one that can refuse it — and without it `stated_total_debits`
    would carry a magnitude for money the document printed coming in."""
    assert parse_lili_statement(SKIN_A_WITHDRAWALS_PRINTED_POSITIVE) is None


def test_a_fees_term_printed_as_an_inflow_is_refused():
    """The same for the fee term and `stated_service_charge`."""
    assert parse_lili_statement(SKIN_A_FEES_PRINTED_POSITIVE) is None


# ---------------------------------------------------------------------------
# The three arithmetic gates
# ---------------------------------------------------------------------------

def test_a_summary_that_does_not_close_on_itself_is_refused():
    """One archive member prints a Deposits figure its own ledger contradicts;
    this is the gate that refuses it."""
    assert parse_lili_statement(
        _swap(SKIN_A, "Deposits and other credits $500.00",
              "Deposits and other credits $180.00")
    ) is None


def test_a_broken_chain_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "$500.00 $300.00", "$500.00 $301.00")
    ) is None


def test_a_dropped_posting_refuses_the_document():
    """A row lost between two printed balances breaks the walk at the next
    row: this reader needs no stated count, and the template prints none."""
    assert parse_lili_statement(
        _swap(SKIN_A, "03/20/2026 222222222 Wire Transfer $500.00 $300.00\n", "")
    ) is None


def test_a_chain_that_does_not_arrive_at_the_printed_ending_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "03/31/2026 333333333 Plan Fee (Effective Date 03/09/2026) $-10.00 $290.00\n", "")
    ) is None


def test_a_posting_pair_the_summary_nets_out_is_refused():
    """A credit and its reversal, inserted so that the chain still walks and
    the printed summary still closes. Only the rows-versus-summary reading
    can see it: the rows' GROSS debits no longer equal the two debit terms
    added, even though every balance printed on the page is consistent."""
    document = _swap(
        SKIN_A,
        "03/02/2026 111111111 A MERCHANT SOMEWHERE STUS $-300.00 $-200.00\n",
        "03/02/2026 111111111 A MERCHANT SOMEWHERE STUS $-300.00 $-200.00\n"
        "03/05/2026 666666666 A CREDIT STUS $50.00 $-150.00\n"
        "03/06/2026 777777777 ITS REVERSAL STUS $-50.00 $-200.00\n",
    )
    assert parse_lili_statement(document) is None


def test_a_first_posting_that_does_not_step_from_the_printed_beginning_is_refused():
    """The chain is anchored at the printed beginning, not at the first row's
    own printed balance: both summary figures move here so the summary still
    closes on itself, and only the anchored walk can see it."""
    document = SKIN_A
    document = _swap(document, "Beginning balance on 1 March, 2026 $100.00",
                     "Beginning balance on 1 March, 2026 $150.00")
    document = _swap(document, "Ending balance on 31 March, 2026 $290.00",
                     "Ending balance on 31 March, 2026 $340.00")
    assert parse_lili_statement(document) is None


def test_a_description_that_cleans_away_to_nothing_refuses_the_document():
    """A row whose description survives the cell cleaner as an empty string is
    a row this reader cannot describe, and a blank description is not one."""
    assert parse_lili_statement(
        _swap(SKIN_A, "Wire Transfer $500.00", "<b> $500.00")
    ) is None


def test_an_unreadable_ledger_refuses_rather_than_publishing_a_partial_one():
    """No postings at all is not an empty statement — it is a ledger this
    reader could not read."""
    assert parse_lili_statement(HEADER + SUMMARY + DISCLOSURE) is None

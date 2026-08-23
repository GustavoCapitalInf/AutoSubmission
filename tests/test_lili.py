"""W3 §LILI — the Lili / Sunrise Banks business-checking printing.

EVERY FIXTURE IN THIS FILE IS INVENTED, and deliberately invented AWAY from
the family: the period is a month of a calendar year no member of the family
contains, every figure carries cents no member prints, the authorization codes
are digit repeats, and the descriptions are made up. None of the tampered
members' out-of-period blocks is reproduced — the out-of-period rows below are
invented too. `tools/lili_privacy_scan.py` is the measurement behind that
paragraph rather than the paragraph being the assurance.

The base document is arithmetically closed three ways, so that a mutant can
only break it:

    beginning 137.41 + deposits 512.63 - withdrawals 308.19 - fees 13.27
        == ending 328.58                        (the printed summary closes)
    137.41 -> -170.78 -> 341.85 -> 328.58       (the printed chain walks)
    rows: gross debits 321.46 == 308.19 + 13.27 (rows == the two debit terms)
"""
from __future__ import annotations

import pytest

from analysis.lili import DETECTION_MARKERS, detect, parse_lili_statement

# ---------------------------------------------------------------------------
# The invented documents
# ---------------------------------------------------------------------------

HEADER = (
    "Account Number Statement Period 999900000000 "
    "1 September, 2027 - 30 September, 2027\n"
)
SUMMARY = (
    "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $137.41\n"
    "Deposits and other credits $512.63\n"
    "Withdrawals and other debits $-308.19\n"
    "Fees $-13.27\n"
    "Ending balance on 30 September, 2027 $328.58\n"
)
LEDGER = (
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-308.19 $-170.78\n"
    "09/17/2027 222222222 A MOVEMENT IN $512.63 $341.85\n"
    "09/30/2027 333333333 A PERIODIC LEVY (Applies From 09/08/2027) $-13.27 $328.58\n"
)
#: The only furniture detection needs, and the only furniture reproduced: the
#: platform's own support address.
CONTACT = "Contact us at support@lili.co\n"

SKIN_A = HEADER + SUMMARY + LEDGER + CONTACT

#: The credit-builder printing as the archive prints it: three money columns
#: (checking, its sibling, and their total) and a SECOND ledger with its own
#: running balance. Both halves close on their own; the schema carries one
#: account, so it is refused.
SKIN_A_TWO_ACCOUNTS = (
    HEADER
    + "Checking Account Summary Checking Account\n"
    "Sibling\n"
    "Total\n"
    "Beginning balance on 1 September, 2027 $137.41 $41.09 $178.50\n"
    "Deposits and other credits $512.63 $24.83 $537.46\n"
    "Withdrawals and other debits $-308.19 $-33.75 $-341.94\n"
    "Fees $-13.27 $0.00 $-13.27\n"
    "Ending balance on 30 September, 2027 $328.58 $32.17 $360.75\n"
    + LEDGER
    + "Sibling Account Activity\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/10/2027 444444444 A SIBLING TOPUP $24.83 $65.92\n"
    "09/11/2027 555555555 A SIBLING DRAWDOWN $-33.75 $32.17\n"
    + CONTACT
)

#: Three money columns and ONE ledger. The checking column closes on itself
#: and the single chain walks, so the §L-1 COLUMN reading is what refuses it.
SKIN_A_THREE_COLUMNS_ONE_LEDGER = (
    HEADER
    + "Checking Account Summary Checking Account\n"
    "Sibling\n"
    "Total\n"
    "Beginning balance on 1 September, 2027 $137.41 $41.09 $178.50\n"
    "Deposits and other credits $512.63 $24.83 $537.46\n"
    "Withdrawals and other debits $-308.19 $-33.75 $-341.94\n"
    "Fees $-13.27 $0.00 $-13.27\n"
    "Ending balance on 30 September, 2027 $328.58 $32.17 $360.75\n"
    + LEDGER + CONTACT
)

#: Three money columns whose SECOND column is idle, so the total column and
#: the checking column carry identical figures. Reading the wrong column is
#: arithmetically invisible here, which is exactly what isolates the §L-1
#: COLUMN reading from the chain gate behind it.
SKIN_A_THREE_COLUMNS_IDLE_SIBLING = (
    HEADER
    + "Checking Account Summary Checking Account\n"
    "Sibling\n"
    "Total\n"
    "Beginning balance on 1 September, 2027 $137.41 $0.00 $137.41\n"
    "Deposits and other credits $512.63 $0.00 $512.63\n"
    "Withdrawals and other debits $-308.19 $0.00 $-308.19\n"
    "Fees $-13.27 $0.00 $-13.27\n"
    "Ending balance on 30 September, 2027 $328.58 $0.00 $328.58\n"
    + LEDGER + CONTACT
)

#: One money column and TWO ledger column heads, the second carrying no rows.
#: The summary, the chain and the gross debits are the clean document's, so
#: the §L-1 LEDGER reading is what refuses it.
SKIN_A_SECOND_LEDGER_HEAD = (
    HEADER + SUMMARY + LEDGER
    + "Sibling Account Activity\n"
    "Date Authorization Code Description Amount Balance\n"
    + CONTACT
)

#: A summary whose Withdrawals term is printed as an INFLOW while its Fees
#: term absorbs the difference. Every arithmetic gate closes on it.
SKIN_A_WITHDRAWALS_PRINTED_POSITIVE = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $137.41\n"
    "Deposits and other credits $512.63\n"
    "Withdrawals and other debits $58.22\n"
    "Fees $-361.93\n"
    "Ending balance on 30 September, 2027 $346.33\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-303.71 $-166.30\n"
    "09/17/2027 222222222 A MOVEMENT IN $512.63 $346.33\n"
    + CONTACT
)

#: The same for the Fees term, printed as a credit.
SKIN_A_FEES_PRINTED_POSITIVE = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $137.41\n"
    "Deposits and other credits $512.63\n"
    "Withdrawals and other debits $-294.92\n"
    "Fees $13.27\n"
    "Ending balance on 30 September, 2027 $355.12\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-294.92 $-157.51\n"
    "09/17/2027 222222222 A MOVEMENT IN $512.63 $355.12\n"
    + CONTACT
)

#: Beginning and Deposits both wrong, in step, so the summary still closes on
#: itself, the last printed balance is still the printed ending, and the rows
#: still total to the two debit terms. Only a chain ANCHORED AT THE PRINTED
#: BEGINNING can see it.
SKIN_A_OPENING_ANCHOR_BROKEN = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $162.29\n"
    "Deposits and other credits $487.75\n"
    "Withdrawals and other debits $-308.19\n"
    "Fees $-13.27\n"
    "Ending balance on 30 September, 2027 $328.58\n"
    + LEDGER + CONTACT
)

#: A posting whose BALANCE the money grammar refuses (its integer part runs
#: past the grammar's digit bound), moving no money and standing between two
#: rows that chain to each other. Skipping it would leave the chain, the
#: summary and the gross debits all intact, so only "a posting I cannot read
#: refuses the document" can see it.
SKIN_A_UNREADABLE_POSTING_THAT_NETS_TO_NOTHING = (
    HEADER + SUMMARY
    + "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-308.19 $-170.78\n"
    "09/17/2027 222222222 A MOVEMENT IN $512.63 $341.85\n"
    "09/22/2027 666666666 A HELD AUTHORISATION $0.00 $12345678901234.00\n"
    "09/30/2027 333333333 A PERIODIC LEVY (Applies From 09/08/2027) $-13.27 $328.58\n"
    + CONTACT
)

#: A month whose summary closes with no movement and whose ledger head is
#: printed with nothing under it. Every arithmetic gate is content with an
#: empty ledger, so only "no postings is not an empty statement" can see it.
SKIN_A_LEDGER_HEAD_WITH_NO_ROWS = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $137.41\n"
    "Deposits and other credits $0.00\n"
    "Withdrawals and other debits $0.00\n"
    "Fees $0.00\n"
    "Ending balance on 30 September, 2027 $137.41\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    + CONTACT
)

#: A description carrying its own figures, so that the row pattern's trailing
#: anchor is what has to bind the amount and balance columns.
SKIN_A_FIGURES_INSIDE_A_DESCRIPTION = (
    HEADER + SUMMARY
    + "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-308.19 $-170.78\n"
    "09/17/2027 222222222 A MOVEMENT IN REF $7.13 $2.41 $512.63 $341.85\n"
    "09/30/2027 333333333 A PERIODIC LEVY (Applies From 09/08/2027) $-13.27 $328.58\n"
    + CONTACT
)

#: A credit and its reversal, inserted so the chain still walks and the
#: summary still closes. Only the GROSS-debit reading can see them.
SKIN_A_POSTING_PAIR_THE_SUMMARY_NETS_OUT = (
    HEADER + SUMMARY
    + "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 111111111 A MERCHANT NOWHERE ZZUS $-308.19 $-170.78\n"
    "09/05/2027 666666666 AN INFLOW $57.36 $-113.42\n"
    "09/06/2027 777777777 ITS REVERSAL $-57.36 $-170.78\n"
    "09/17/2027 222222222 A MOVEMENT IN $512.63 $341.85\n"
    "09/30/2027 333333333 A PERIODIC LEVY (Applies From 09/08/2027) $-13.27 $328.58\n"
    + CONTACT
)

#: The second printing: header order reversed, summary labels and figures on
#: SEPARATE lines, postings shredded across lines with a floating network tag,
#: and a block of rows dated outside the period the document declares.
SKIN_B_OUT_OF_PERIOD = (
    "Statement Period Account Number\n"
    "999900000000              01 September, 2027 - 30 September, 2027\n"
    "Summary\n"
    "Amount\n"
    "Beginning balance on 01 September, 2027\n"
    "$137.41\n"
    "Deposits and other credits\n"
    "$512.63\n"
    "Withdrawals and other debits\n"
    "$308.19\n"
    "Fees\n"
    "$0.00 $0.00\n"
    "Activity\n"
    "Amount Balance\n"
    "Date\n"
    "Description Authorization Code\n"
    "A MERCHANT NOWHERE\n"
    "09/03/2027\n"
    "777777777\n"
    "$-308.19  $-170.78\n"
    "QQ\n"
    "AN OLDER MERCHANT\n"
    "07/14/2019\n"
    "888888888\n"
    "$-11.06 $-181.84\n"
    "RR\n"
    "Ending balance on      30 September, 2027\n"
    "$328.58\n"
    + CONTACT
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
    assert statement.period_start == "2027-09-01"
    assert statement.period_end == "2027-09-30"
    assert statement.days_in_period == 30
    assert statement.beginning_balance == 137.41
    assert statement.ending_balance == 328.58
    assert statement.stated_total_credits == 512.63


def test_the_debit_total_excludes_the_fee_term_the_document_prints_separately():
    """This platform's `Withdrawals and other debits` term does NOT include
    its `Fees` term — the rows prove it — so the two are published apart."""
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert statement.stated_total_debits == 308.19
    assert statement.stated_service_charge == 13.27
    debited = round(sum(-t.amount for t in statement.transactions if t.amount < 0), 2)
    assert debited == round(
        statement.stated_total_debits + statement.stated_service_charge, 2
    )


def test_every_posting_carries_the_balance_the_document_printed_after_it():
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert [t.running_balance for t in statement.transactions] == [-170.78, 341.85, 328.58]
    assert [t.direction for t in statement.transactions] == ["debit", "credit", "debit"]
    assert [t.date for t in statement.transactions] == [
        "2027-09-03", "2027-09-17", "2027-09-30",
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


def test_a_description_that_contains_figures_does_not_steal_the_amount_column():
    """Merchant, city and country run together with no delimiter on this
    template, so the amount is the SECOND-TO-LAST money token of the line and
    the balance is the last — never the first pair that appears. The row
    pattern's END ANCHOR is what binds those two columns, with the greedy
    description behind it."""
    statement = parse_lili_statement(SKIN_A_FIGURES_INSIDE_A_DESCRIPTION)
    assert statement is not None
    assert statement.transactions[1].amount == 512.63
    assert statement.transactions[1].running_balance == 341.85
    assert "$7.13" in statement.transactions[1].description
    assert "$2.41" in statement.transactions[1].description


# ---------------------------------------------------------------------------
# §INTEGRITY — a date the document prints outside the period it declares
# ---------------------------------------------------------------------------

def test_a_posting_dated_outside_the_printed_period_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "09/03/2027 111111111", "09/03/2019 111111111")
    ) is None


def test_a_posting_dated_inside_the_year_but_outside_the_period_is_refused():
    """One archive member carries a row a whole month after the period it
    declares. A gate that compared only the YEAR would read it as in-period."""
    assert parse_lili_statement(
        _swap(SKIN_A, "09/17/2027 222222222", "10/17/2027 222222222")
    ) is None


def test_the_shredded_printing_is_refused_for_printing_rows_from_another_period():
    """The archive's five tampered members reach this gate; this fixture is an
    invented document of the same SHAPE, never a copy of one of them."""
    assert detect(SKIN_B_OUT_OF_PERIOD).claims
    assert parse_lili_statement(SKIN_B_OUT_OF_PERIOD) is None


def test_the_shredded_printing_is_still_refused_without_the_out_of_period_rows():
    """Belt and braces: even with every date inside the period, the second
    printing's summary is not line-anchored and it is refused anyway."""
    inside = _swap(SKIN_B_OUT_OF_PERIOD, "07/14/2019", "09/14/2027")
    assert detect(inside).claims
    assert parse_lili_statement(inside) is None


def test_a_posting_date_that_is_not_a_calendar_date_refuses_the_document():
    """`str.isdigit()` grammar admits `13/45/2027`; a calendar does not."""
    assert parse_lili_statement(
        _swap(SKIN_A, "09/17/2027 222222222", "13/45/2027 222222222")
    ) is None


def test_a_non_calendar_date_inside_a_description_refuses_the_document():
    """Away from the date column, only the §INTEGRITY gate ever looks at this
    token — and it must answer, not raise."""
    assert parse_lili_statement(
        _swap(SKIN_A, "(Applies From 09/08/2027)", "(Applies From 13/45/2027)")
    ) is None


def test_an_unreadable_posting_refuses_even_when_skipping_it_would_reconcile():
    """A posting this reader cannot read is not a posting it may leave out."""
    assert parse_lili_statement(SKIN_A_UNREADABLE_POSTING_THAT_NETS_TO_NOTHING) is None


def test_a_date_inside_a_description_is_read_by_the_same_gate():
    """The fee rows of this template carry a date in their text. Inside the
    period it is fine; outside it, it refuses — measured over the family's 15
    clean members, zero of 2,738 printed date tokens fall outside."""
    assert parse_lili_statement(SKIN_A) is not None
    assert parse_lili_statement(
        _swap(SKIN_A, "(Applies From 09/08/2027)", "(Applies From 12/09/2019)")
    ) is None


# ---------------------------------------------------------------------------
# §L-1 — the second account, read twice
# ---------------------------------------------------------------------------

def test_a_summary_that_prints_a_second_money_column_is_refused():
    """Three columns, one ledger: the checking column closes on itself and the
    single chain walks, so the §L-1 COLUMN reading is what sees it."""
    assert detect(SKIN_A_THREE_COLUMNS_ONE_LEDGER).claims
    assert parse_lili_statement(SKIN_A_THREE_COLUMNS_ONE_LEDGER) is None


def test_a_second_money_column_is_refused_even_when_it_is_idle():
    """With the sibling column all zeros the total column and the checking
    column agree, so no arithmetic gate can tell them apart — and the reader
    still refuses, because a printed second column is a second account and
    this template prints no idle-sibling banner that would exempt it."""
    assert parse_lili_statement(SKIN_A_THREE_COLUMNS_IDLE_SIBLING) is None


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
        _swap(SKIN_A, "Fees $-13.27", "Fees $-13.27 $0.00 $-13.27")
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
    assert statement.period_start == "2027-09-01"


def test_two_headers_that_disagree_refuse_the_document():
    assert parse_lili_statement(SKIN_A + HEADER.replace("999900000000", "888800000000")) is None


def test_a_header_reprinted_identically_is_corroboration_not_a_contradiction():
    statement = parse_lili_statement(SKIN_A + HEADER)
    assert statement is not None
    assert statement.account_number == "999900000000"


def test_a_period_that_ends_before_it_starts_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "1 September, 2027 - 30 September, 2027",
              "30 September, 2027 - 1 September, 2027")
    ) is None


def test_a_period_bound_the_calendar_does_not_have_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "1 September, 2027 - 30 September, 2027",
              "1 September, 2027 - 31 September, 2027")
    ) is None


def test_a_document_with_no_header_at_all_is_claimed_and_declined():
    document = SUMMARY + LEDGER + CONTACT
    assert detect(document).claims
    assert parse_lili_statement(document) is None


# ---------------------------------------------------------------------------
# The summary shape and its signs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "term",
    [
        "Beginning balance on 1 September, 2027 $137.41\n",
        "Deposits and other credits $512.63\n",
        "Withdrawals and other debits $-308.19\n",
        "Fees $-13.27\n",
        "Ending balance on 30 September, 2027 $328.58\n",
    ],
)
def test_a_summary_missing_any_one_of_its_five_terms_is_refused(term):
    assert parse_lili_statement(_swap(SKIN_A, term, "")) is None


def test_a_summary_term_printed_twice_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "Fees $-13.27\n", "Fees $-13.27\nFees $-13.27\n")
    ) is None


def test_the_five_terms_must_appear_in_the_order_the_template_prints_them():
    scrambled = (
        HEADER
        + "Checking Account Summary Total Checking Amount\n"
        "Deposits and other credits $512.63\n"
        "Beginning balance on 1 September, 2027 $137.41\n"
        "Withdrawals and other debits $-308.19\n"
        "Fees $-13.27\n"
        "Ending balance on 30 September, 2027 $328.58\n"
        + LEDGER + CONTACT
    )
    assert parse_lili_statement(scrambled) is None


def test_a_term_whose_figure_is_on_the_next_line_is_refused():
    """The second printing's layout. A term pattern joined by `\\s` rather than
    by a same-line class would match across the break and read it."""
    assert parse_lili_statement(
        _swap(SKIN_A, "Deposits and other credits $512.63",
              "Deposits and other credits\n$512.63")
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
        _swap(SKIN_A, "Deposits and other credits $512.63",
              "Deposits and other credits $471.02")
    ) is None


def test_a_broken_chain_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "$512.63 $341.85", "$512.63 $342.85")
    ) is None


def test_a_first_posting_that_does_not_step_from_the_printed_beginning_is_refused():
    """The chain is anchored at the printed BEGINNING, not at the first row's
    own implied opening: Beginning and Deposits move together here, so the
    summary still closes, the last printed balance is still the printed
    ending, and the gross debits still total to the two debit terms."""
    assert parse_lili_statement(SKIN_A_OPENING_ANCHOR_BROKEN) is None


def test_a_dropped_posting_refuses_the_document():
    """A row lost between two printed balances breaks the walk at the next
    row: this reader needs no stated count, and the template prints none."""
    assert parse_lili_statement(
        _swap(SKIN_A, "09/17/2027 222222222 A MOVEMENT IN $512.63 $341.85\n", "")
    ) is None


def test_a_chain_that_does_not_arrive_at_the_printed_ending_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A,
              "09/30/2027 333333333 A PERIODIC LEVY (Applies From 09/08/2027) $-13.27 $328.58\n",
              "")
    ) is None


def test_a_posting_pair_the_summary_nets_out_is_refused():
    """A credit and its reversal: the chain still walks and the printed
    summary still closes, but the rows' GROSS debits no longer equal the two
    debit terms added. Only that reading can see it."""
    assert parse_lili_statement(SKIN_A_POSTING_PAIR_THE_SUMMARY_NETS_OUT) is None


def test_a_description_that_cleans_away_to_nothing_refuses_the_document():
    """A row whose description survives the cell cleaner as an empty string is
    a row this reader cannot describe, and a blank description is not one."""
    assert parse_lili_statement(
        _swap(SKIN_A, "A MOVEMENT IN $512.63", "<b> $512.63")
    ) is None


def test_an_unreadable_ledger_refuses_rather_than_publishing_a_partial_one():
    """No postings at all is not an empty statement — it is a ledger this
    reader could not read."""
    assert parse_lili_statement(HEADER + SUMMARY + CONTACT) is None


def test_a_ledger_head_with_no_rows_under_it_refuses_rather_than_publishing_zero():
    """The summary closes with no movement, so every arithmetic gate is happy
    with an empty ledger. This template prints no idle-period banner, so a
    month that had no postings and a ledger this reader failed to read are the
    same text, and both fail closed."""
    assert parse_lili_statement(SKIN_A_LEDGER_HEAD_WITH_NO_ROWS) is None

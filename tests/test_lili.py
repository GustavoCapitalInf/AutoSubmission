"""W3 §LILI — the Lili / Sunrise Banks business-checking printing.

EVERY FIXTURE IN THIS FILE IS INVENTED, and deliberately invented AWAY from
the family: the period is a month of a calendar year no member of the family
contains, every figure carries cents no member prints, the authorization codes
are a `7000000n` series, and the descriptions are made up. None of the tampered
members' out-of-period blocks is reproduced — the out-of-period rows below are
invented too. `tools/lili_privacy_scan.py` is the measurement behind that
paragraph rather than the paragraph being the assurance.

INVENTED IS NOT THE SAME AS DISTINCT, and this file is where batch 9 measured
the difference. The original figures were invented against this family's 20
documents; against the WHOLE 3,351-document archive, which prints 354,835
distinct money figures with cents and 208,695 distinct digit runs, twelve of
them collided with something some document prints, and so did one of the
repeated-digit authorization codes. Nothing about the fixture said so and
nobody could see it.

Every figure here is now the original invented figure with its CENT VALUE
multiplied by 428. A whole-number scale on integer cents is exact, so all
three closures below hold to the cent exactly as they did, and no figure had
to be re-derived. 428 is not a taste: `tools/fixpriv_invent.py --scale-search`
reports it as the smallest whole-number scale under which neither any scaled
figure NOR ANY DIGIT RUN IT GENERATES appears anywhere in the archive — the
digit run matters, because writing a six-figure amount into a file writes a
six-digit run with it, and the first attempt at this repair (scale 1013)
cleared every figure and introduced sixteen colliding runs.

The scale is applied only to figures that were invented in the first place. An
archive figure is never scaled or shifted anywhere: a scale is reversible, and
a reversible redaction is not one.

The base document is arithmetically closed three ways, so that a mutant can
only break it:

    beginning 58811.48 + deposits 219405.64 - withdrawals 131905.32 - fees 5679.56
        == ending 140632.24                        (the printed summary closes)
    58811.48 -> -73093.84 -> 146311.80 -> 140632.24       (the printed chain walks)
    rows: gross debits 137584.88 == 131905.32 + 5679.56 (rows == the two debit terms)
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
    "Beginning balance on 1 September, 2027 $58811.48\n"
    "Deposits and other credits $219405.64\n"
    "Withdrawals and other debits $-131905.32\n"
    "Fees $-5679.56\n"
    "Ending balance on 30 September, 2027 $140632.24\n"
)
LEDGER = (
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $146311.80\n"
    "09/30/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n"
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
    "Beginning balance on 1 September, 2027 $58811.48 $17586.52 $76398.00\n"
    "Deposits and other credits $219405.64 $10627.24 $230032.88\n"
    "Withdrawals and other debits $-131905.32 $-14445.00 $-146350.32\n"
    "Fees $-5679.56 $0.00 $-5679.56\n"
    "Ending balance on 30 September, 2027 $140632.24 $13768.76 $154401.00\n"
    + LEDGER
    + "Sibling Account Activity\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/10/2027 700000004 A SIBLING TOPUP $10627.24 $28213.76\n"
    "09/11/2027 700000005 A SIBLING DRAWDOWN $-14445.00 $13768.76\n"
    + CONTACT
)

#: Three money columns and ONE ledger. The checking column closes on itself
#: and the single chain walks, so the §L-1 COLUMN reading is what refuses it.
SKIN_A_THREE_COLUMNS_ONE_LEDGER = (
    HEADER
    + "Checking Account Summary Checking Account\n"
    "Sibling\n"
    "Total\n"
    "Beginning balance on 1 September, 2027 $58811.48 $17586.52 $76398.00\n"
    "Deposits and other credits $219405.64 $10627.24 $230032.88\n"
    "Withdrawals and other debits $-131905.32 $-14445.00 $-146350.32\n"
    "Fees $-5679.56 $0.00 $-5679.56\n"
    "Ending balance on 30 September, 2027 $140632.24 $13768.76 $154401.00\n"
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
    "Beginning balance on 1 September, 2027 $58811.48 $0.00 $58811.48\n"
    "Deposits and other credits $219405.64 $0.00 $219405.64\n"
    "Withdrawals and other debits $-131905.32 $0.00 $-131905.32\n"
    "Fees $-5679.56 $0.00 $-5679.56\n"
    "Ending balance on 30 September, 2027 $140632.24 $0.00 $140632.24\n"
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
    "Beginning balance on 1 September, 2027 $58811.48\n"
    "Deposits and other credits $219405.64\n"
    "Withdrawals and other debits $24918.16\n"
    "Fees $-154906.04\n"
    "Ending balance on 30 September, 2027 $148229.24\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-129987.88 $-71176.40\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $148229.24\n"
    + CONTACT
)

#: The same for the Fees term, printed as a credit.
SKIN_A_FEES_PRINTED_POSITIVE = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $58811.48\n"
    "Deposits and other credits $219405.64\n"
    "Withdrawals and other debits $-131905.32\n"
    "Fees $5679.56\n"
    "Ending balance on 30 September, 2027 $151991.36\n"
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-126225.76 $-67414.28\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $151991.36\n"
    + CONTACT
)

#: Beginning and Deposits both wrong, in step, so the summary still closes on
#: itself, the last printed balance is still the printed ending, and the rows
#: still total to the two debit terms. Only a chain ANCHORED AT THE PRINTED
#: BEGINNING can see it.
SKIN_A_OPENING_ANCHOR_BROKEN = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $69460.12\n"
    "Deposits and other credits $208757.00\n"
    "Withdrawals and other debits $-131905.32\n"
    "Fees $-5679.56\n"
    "Ending balance on 30 September, 2027 $140632.24\n"
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
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $146311.80\n"
    "09/22/2027 700000006 A HELD AUTHORISATION $0.00 $12345678901234.00\n"
    "09/30/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n"
    + CONTACT
)

#: A month whose summary closes with no movement and whose ledger head is
#: printed with nothing under it. Every arithmetic gate is content with an
#: empty ledger, so only "no postings is not an empty statement" can see it.
SKIN_A_LEDGER_HEAD_WITH_NO_ROWS = (
    HEADER
    + "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 1 September, 2027 $58811.48\n"
    "Deposits and other credits $0.00\n"
    "Withdrawals and other debits $0.00\n"
    "Fees $0.00\n"
    "Ending balance on 30 September, 2027 $58811.48\n"
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
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN REF $3051.64 $1031.48 $219405.64 $146311.80\n"
    "09/30/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n"
    + CONTACT
)

#: A credit and its reversal, inserted so the chain still walks and the
#: summary still closes. Only the GROSS-debit reading can see them.
SKIN_A_POSTING_PAIR_THE_SUMMARY_NETS_OUT = (
    HEADER + SUMMARY
    + "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/05/2027 700000006 AN INFLOW $24550.08 $-48543.76\n"
    "09/06/2027 700000007 ITS REVERSAL $-24550.08 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $146311.80\n"
    "09/30/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n"
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
    "$58811.48\n"
    "Deposits and other credits\n"
    "$219405.64\n"
    "Withdrawals and other debits\n"
    "$131905.32\n"
    "Fees\n"
    "$0.00 $0.00\n"
    "Activity\n"
    "Amount Balance\n"
    "Date\n"
    "Description Authorization Code\n"
    "A MERCHANT NOWHERE\n"
    "09/03/2027\n"
    "700000007\n"
    "$-131905.32  $-73093.84\n"
    "QQ\n"
    "AN OLDER MERCHANT\n"
    "07/14/2019\n"
    "700000008\n"
    "$-4733.68 $-77827.52\n"
    "RR\n"
    "Ending balance on      30 September, 2027\n"
    "$140632.24\n"
    + CONTACT
)


#: A period that does NOT start on the first of its month. The archive has one
#: (a period running from late one month to the end of the next), and it is
#: what makes the lower bound of the period reading pinnable: a rule that
#: slackened to "the first of the period-start month" would be invisible on a
#: calendar-month period and is caught here.
MID_MONTH_HEADER = (
    "Account Number Statement Period 999900000000 "
    "15 September, 2027 - 14 October, 2027\n"
)
MID_MONTH_SUMMARY = (
    "Checking Account Summary Total Checking Amount\n"
    "Beginning balance on 15 September, 2027 $58811.48\n"
    "Deposits and other credits $219405.64\n"
    "Withdrawals and other debits $-131905.32\n"
    "Fees $-5679.56\n"
    "Ending balance on 14 October, 2027 $140632.24\n"
)
MID_MONTH_LEDGER = (
    "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/16/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $146311.80\n"
    "10/14/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n"
)
SKIN_A_MID_MONTH = MID_MONTH_HEADER + MID_MONTH_SUMMARY + MID_MONTH_LEDGER + CONTACT

#: A line that BEGINS with a date and that the row pattern cannot parse — here
#: because the posting carries no authorization code. It moves no money and
#: repeats the balance above it, so every arithmetic gate is content with it
#: dropped: only the coverage reading can see that a printed line was silently
#: not read.
SKIN_A_UNPARSED_LEDGER_LINE = (
    HEADER + SUMMARY
    + "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN $219405.64 $146311.80\n"
    "09/22/2027 A HOLD WITH NO CODE $0.00 $146311.80\n"
    "09/30/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n"
    + CONTACT
)

#: Six clean printings that carry a date OUTSIDE the declared period without
#: any of them being a claim about when money moved. Every one of these was
#: refused by this reader's first revision, and every one must publish.
SKIN_A_LEGITIMATE_OUT_OF_PERIOD_DATES = (
    HEADER + SUMMARY
    + "Checking Account Activity - Main Account\n"
    "Date Authorization Code Description Amount Balance\n"
    "09/03/2027 700000001 A MERCHANT NOWHERE ZZUS $-131905.32 $-73093.84\n"
    "09/17/2027 700000002 A MOVEMENT IN REF 04/02/2026 $219405.64 $146311.80\n"
    "09/30/2027 700000003 A PERIODIC LEVY (Applies From 08/25/2027) $-5679.56 $140632.24\n"
    "Statement printed 10/02/2027\n"
    "These terms were last revised 01/14/2019.\n"
    "Report an error no later than 11/29/2027.\n"
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
    assert statement.beginning_balance == 58811.48
    assert statement.ending_balance == 140632.24
    assert statement.stated_total_credits == 219405.64


def test_the_debit_total_excludes_the_fee_term_the_document_prints_separately():
    """This platform's `Withdrawals and other debits` term does NOT include
    its `Fees` term — the rows prove it — so the two are published apart."""
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert statement.stated_total_debits == 131905.32
    assert statement.stated_service_charge == 5679.56
    debited = round(sum(-t.amount for t in statement.transactions if t.amount < 0), 2)
    assert debited == round(
        statement.stated_total_debits + statement.stated_service_charge, 2
    )


def test_every_posting_carries_the_balance_the_document_printed_after_it():
    statement = parse_lili_statement(SKIN_A)
    assert statement is not None
    assert [t.running_balance for t in statement.transactions] == [-73093.84, 146311.80, 140632.24]
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
    assert statement.transactions[1].amount == 219405.64
    assert statement.transactions[1].running_balance == 146311.80
    assert "$3051.64" in statement.transactions[1].description
    assert "$1031.48" in statement.transactions[1].description


# ---------------------------------------------------------------------------
# §INTEGRITY — a date the document prints outside the period it declares
# ---------------------------------------------------------------------------

def test_a_posting_dated_outside_the_printed_period_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "09/03/2027 700000001", "09/03/2019 700000001")
    ) is None


def test_a_posting_dated_inside_the_year_but_outside_the_period_is_refused():
    """One archive member carries a row a whole month after the period it
    declares. A gate that compared only the YEAR would read it as in-period."""
    assert parse_lili_statement(
        _swap(SKIN_A, "09/17/2027 700000002", "10/17/2027 700000002")
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
        _swap(SKIN_A, "09/17/2027 700000002", "13/45/2027 700000002")
    ) is None


def test_a_non_calendar_date_inside_a_description_does_not_refuse():
    """Description text is not a claim about when money moved. The row's own
    leading date, amount and balance have already been verified, so a
    malformed date inside its description changes nothing — and it must not
    raise either."""
    statement = parse_lili_statement(
        _swap(SKIN_A, "(Applies From 09/08/2027)", "(Applies From 13/45/2027)")
    )
    assert statement is not None
    assert "13/45/2027" in statement.transactions[2].description


def test_a_line_that_begins_with_a_date_must_be_a_posting():
    """MINOR-3, and the reading that refuses the second printing. A printed
    ledger line the row pattern cannot parse is silently dropped by every
    other gate when it moves no money — so coverage is checked on ROWS, not
    only on money. Measured over the 15 clean members: 2,718 line-leading
    dates, 2,718 parsed postings, exact on every document."""
    assert parse_lili_statement(SKIN_A_UNPARSED_LEDGER_LINE) is None


def test_a_posting_on_the_first_day_of_the_period_publishes():
    assert parse_lili_statement(
        _swap(SKIN_A, "09/03/2027 700000001", "09/01/2027 700000001")
    ) is not None


def test_a_posting_one_day_before_the_period_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "09/03/2027 700000001", "08/31/2027 700000001")
    ) is None


def test_a_posting_on_the_last_day_of_the_period_publishes():
    assert parse_lili_statement(
        _swap(SKIN_A, "09/03/2027 700000001", "09/30/2027 700000001")
    ) is not None


def test_a_posting_one_day_after_the_period_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "09/03/2027 700000001", "10/01/2027 700000001")
    ) is None


def test_a_period_that_does_not_start_on_the_first_publishes():
    statement = parse_lili_statement(SKIN_A_MID_MONTH)
    assert statement is not None
    assert statement.period_start == "2027-09-15"
    assert statement.period_end == "2027-10-14"
    assert statement.days_in_period == 30


def test_a_posting_earlier_in_the_period_start_month_is_refused():
    """The lower bound is the period's own first day, not the first of the
    month it falls in. On a calendar-month period those are the same day and
    a slackened bound would be invisible; on this period they are two weeks
    apart."""
    assert parse_lili_statement(
        _swap(SKIN_A_MID_MONTH, "09/16/2027 700000001", "09/03/2027 700000001")
    ) is None


def test_a_posting_later_in_the_period_end_month_is_refused():
    """The upper bound, pinned the same way."""
    assert parse_lili_statement(
        _swap(SKIN_A_MID_MONTH, "10/14/2027 700000003", "10/29/2027 700000003")
    ) is None


def test_an_unreadable_posting_refuses_even_when_skipping_it_would_reconcile():
    """A posting this reader cannot read is not a posting it may leave out."""
    assert parse_lili_statement(SKIN_A_UNREADABLE_POSTING_THAT_NETS_TO_NOTHING) is None


def test_a_fee_effective_date_before_the_period_publishes():
    """The fee rows of this template print the start of the plan CYCLE they
    bill for, and a cycle can begin before the statement period does — so an
    effective date outside the period is an ordinary printing, not a finding.
    Measured over the 15 clean members: 11 description dates, all of them a
    fee row's effective date."""
    assert parse_lili_statement(SKIN_A) is not None
    assert parse_lili_statement(
        _swap(SKIN_A, "(Applies From 09/08/2027)", "(Applies From 08/25/2027)")
    ) is not None


def test_six_clean_printings_that_carry_an_out_of_period_date_publish():
    """A merchant string with a date in it, a fee cycle that began before the
    period, a footer print date, a terms-revision date and an error-resolution
    deadline. Every one of these was refused by this reader's first revision,
    which checked every date the document printed wherever it printed it."""
    statement = parse_lili_statement(SKIN_A_LEGITIMATE_OUT_OF_PERIOD_DATES)
    assert statement is not None
    assert len(statement.transactions) == 3


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
        _swap(SKIN_A, "Fees $-5679.56", "Fees $-5679.56 $0.00 $-5679.56")
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
        "Beginning balance on 1 September, 2027 $58811.48\n",
        "Deposits and other credits $219405.64\n",
        "Withdrawals and other debits $-131905.32\n",
        "Fees $-5679.56\n",
        "Ending balance on 30 September, 2027 $140632.24\n",
    ],
)
def test_a_summary_missing_any_one_of_its_five_terms_is_refused(term):
    assert parse_lili_statement(_swap(SKIN_A, term, "")) is None


def test_a_summary_term_printed_twice_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A, "Fees $-5679.56\n", "Fees $-5679.56\nFees $-5679.56\n")
    ) is None


def test_the_five_terms_must_appear_in_the_order_the_template_prints_them():
    scrambled = (
        HEADER
        + "Checking Account Summary Total Checking Amount\n"
        "Deposits and other credits $219405.64\n"
        "Beginning balance on 1 September, 2027 $58811.48\n"
        "Withdrawals and other debits $-131905.32\n"
        "Fees $-5679.56\n"
        "Ending balance on 30 September, 2027 $140632.24\n"
        + LEDGER + CONTACT
    )
    assert parse_lili_statement(scrambled) is None


def test_a_term_whose_figure_is_on_the_next_line_is_refused():
    """The second printing's layout. A term pattern joined by `\\s` rather than
    by a same-line class would match across the break and read it."""
    assert parse_lili_statement(
        _swap(SKIN_A, "Deposits and other credits $219405.64",
              "Deposits and other credits\n$219405.64")
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
        _swap(SKIN_A, "Deposits and other credits $219405.64",
              "Deposits and other credits $201596.56")
    ) is None


def test_a_broken_chain_refuses_the_document():
    assert parse_lili_statement(
        _swap(SKIN_A, "$219405.64 $146311.80", "$219405.64 $146739.80")
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
        _swap(SKIN_A, "09/17/2027 700000002 A MOVEMENT IN $219405.64 $146311.80\n", "")
    ) is None


def test_a_chain_that_does_not_arrive_at_the_printed_ending_is_refused():
    assert parse_lili_statement(
        _swap(SKIN_A,
              "09/30/2027 700000003 A PERIODIC LEVY (Applies From 09/08/2027) $-5679.56 $140632.24\n",
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
        _swap(SKIN_A, "A MOVEMENT IN $219405.64", "<b> $219405.64")
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

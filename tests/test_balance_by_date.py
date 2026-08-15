"""The four-way partitioned-summary core-processor template (W3 SCANC).

Every fixture is synthetic: no customer, account, date or amount from the
archive appears here, and the institution named in the back-page fine print is
a deliberately impossible one.

Two groups of tests carry the weight, and they are the two failure modes this
template invites.

**The partition.**  The summary's `SERVICE CHARGES` and `INTEREST PAID` terms
are money the printed COUNTS exclude and the printed TOTALS exclude, which the
balance identity then puts back.  A reader that folds a fee row into the debit
total produces a statement whose balance chain still closes to the cent - so
the identity cannot detect the mistake, and the printed COUNT is the only
thing that can.  `test_the_folded_summary_still_closes_but_the_count_refuses_
it` is that statement, written out: the identity is asserted to hold and the
document is asserted to be refused anyway.

**The two-column grids.**  Each grid prints a legend that is its column unit
repeated once per column, and OCR flattens the columns into lines that carry
several rows each.  A reader that scans a section as one blob cannot tell a
row it has already read from one it has not, and a duplicated row is exactly
the defect a total can hide.  The guard is the printed legend: a line may
yield at most as many rows as the grid declared columns.  The paired tests
below run the SAME three rows on one line under a two-column legend (refused)
and under a three-column legend (published), so what is being tested is the
document's own declaration rather than a constant in the reader.
"""
from __future__ import annotations

import re

import pytest

from analysis import balance_by_date as bbd
from analysis.balance_by_date import (
    _partition_holds,
    _summary,
    detect,
    parse_balance_by_date_statement as parse,
)
from analysis.count_semantics import counts_comparable

PAGE_HEAD = (
    "PO Box 0 Springfield, ZZ 00000\n"
    "Electronic Service Requested 03/01/2026 - 03/31/2026\n"
    "Account Number: 900000\n"
)

SUMMARY = (
    "Checking Account Summary\n"
    "PREVIOUS BALANCE 100.00 AVERAGE BALANCE\n"
    "+ 2 CREDITS 300.00 150.00\n"
    "- 3 DEBITS 210.00 YTD INTEREST PAID\n"
    "- SERVICE CHARGES 5.00 .00\n"
    "+ INTEREST PAID .50\n"
    "ENDING BALANCE 185.50\n"
)

CREDITS = (
    "e Deposits and Other Credits\n"
    "Date Amount Description Date Amount Description\n"
    "03/02 100.00 SYNTHETIC CREDIT ONE 03/05 200.00 SYNTHETIC CREDIT TWO\n"
    "03/31 .50 SYNTHETIC INTEREST\n"
)

CHECKS = (
    "e Checks\n"
    "Date Serial Amount Date Serial Amount\n"
    "03/03 900 10.00\n"
)

DEBITS = (
    "e Other Debits\n"
    "Date Amount Description Date Amount Description\n"
    "03/04 100.00 SYNTHETIC DEBIT ONE 03/06 100.00 SYNTHETIC DEBIT TWO\n"
    "03/31 5.00 SYNTHETIC LEDGER CHARGE\n"
)

DAILY = (
    "e Balance By Date\n"
    "Date Balance Date Balance Date Balance\n"
    "02/28 100.00 03/04 90.00 03/31 185.50\n"
    "03/02 200.00 03/05 290.00\n"
    "03/03 190.00 03/06 190.00\n"
)

#: The back of the form.  It is here in the HAPPY-PATH document on purpose:
#: its fine print contains the words `other debits`, and a reader that let a
#: section run to the end of the document would take this page into the
#: ledger.  It also names an institution, which no test may see published.
BACK_PAGE = (
    "In case of errors or questions about your electronic transfers, write to "
    "us at Impossible Example Bank, PO Box 0, Springfield, ZZ 00000.\n"
    "Interest Charges have been computed by applying the daily periodic rate "
    "to payments, credits, loan advances and other debits posted to your "
    "Account over the billing cycle.\n"
)


def document(*, summary: str = SUMMARY, credits: str = CREDITS,
             checks: str = CHECKS, debits: str = DEBITS, daily: str = DAILY,
             back: str = BACK_PAGE, page_head: str = PAGE_HEAD) -> str:
    return (
        "--- Page 1 ---\n\n"
        f"{page_head}{summary}{credits}{checks}{debits}{daily}"
        "--- Page 2 ---\n\n"
        f"{back}"
    )


# ===========================================================================
# The happy path
# ===========================================================================

def test_the_printed_statement_is_published_whole():
    stmt = parse(document())
    assert stmt is not None
    assert stmt.period_start == "2026-03-01"
    assert stmt.period_end == "2026-03-31"
    assert stmt.days_in_period == 31
    assert stmt.beginning_balance == 100.00
    assert stmt.ending_balance == 185.50
    assert stmt.account_name == "Checking"
    assert stmt.account_number == "900000"
    # The printed figures, published as printed: the counts and totals EXCLUDE
    # the uncounted terms, and the uncounted terms travel in their own fields.
    assert stmt.stated_credit_count == 2
    assert stmt.stated_total_credits == 300.00
    assert stmt.stated_debit_count == 3
    assert stmt.stated_total_debits == 210.00
    assert stmt.stated_service_charge == 5.00
    assert stmt.stated_interest_paid == 0.50
    # Every row, including the two the counts exclude.
    assert len(stmt.transactions) == 7
    assert sum(1 for t in stmt.transactions if t.direction == "credit") == 3
    assert sum(1 for t in stmt.transactions if t.direction == "debit") == 4
    assert round(sum(t.amount for t in stmt.transactions), 2) == 85.50


def test_a_cheque_is_published_by_its_printed_serial():
    stmt = parse(document())
    cheques = [t for t in stmt.transactions if t.description.startswith("Check ")]
    assert [(t.date, t.description, t.amount) for t in cheques] == [
        ("2026-03-03", "Check 900", -10.00)
    ]


def test_the_daily_grid_is_published_without_its_pre_period_bookend():
    """The grid opens on the day BEFORE the period with the previous balance
    printed a second time.  It has done its work as evidence; published as a
    snapshot the ADB engine would have to reject it as out of period."""
    stmt = parse(document())
    days = [snapshot.date for snapshot in stmt.stated_daily_balances]
    assert "2026-02-28" not in days
    assert days == ["2026-03-02", "2026-03-03", "2026-03-04",
                    "2026-03-05", "2026-03-06", "2026-03-31"]
    assert all(stmt.period_start <= day <= stmt.period_end for day in days)


def test_the_issuer_is_not_published_even_though_the_fine_print_names_one():
    """Honest-unknown-issuer.  This template prints its wordmark as a graphic;
    the only institution named in text is in the back-page disclosures, which
    is where a statement names institutions it merely cites."""
    stmt = parse(document())
    assert stmt.bank is None
    assert "Impossible Example Bank" in document()


def test_the_back_page_fine_print_is_not_read_as_a_ledger_section():
    """`other debits` appears in the disclosure paragraph.  If the boundary
    were missing the reader would look for a grid there, find no legend, and
    refuse the document - so a published statement IS the assertion."""
    assert parse(document()) is not None
    assert "other debits posted to your" in BACK_PAGE


# ===========================================================================
# The partition — the trap
# ===========================================================================

FOLDED_SUMMARY = (
    "Checking Account Summary\n"
    "PREVIOUS BALANCE 100.00 AVERAGE BALANCE\n"
    "+ 2 CREDITS 300.00 150.00\n"
    "- 3 DEBITS 215.00 YTD INTEREST PAID\n"
    "- SERVICE CHARGES .00 .00\n"
    "+ INTEREST PAID .50\n"
    "ENDING BALANCE 185.50\n"
)


def test_the_folded_summary_still_closes_but_the_count_refuses_it():
    """The mis-model, written as the document it would produce.

    The fee is inside the debit total and the service-charge term prints zero.
    `b0 + C - D - S + I == b1` still holds EXACTLY - which is why a reader
    checking only the identity publishes this and reports a debit count one
    short of the ledger it just built.  The count is what refuses it.
    """
    folded = document(summary=FOLDED_SUMMARY)
    summary = _summary(folded)
    assert summary is not None
    assert summary.identity_holds, "the fixture must be plausible, or it proves nothing"
    assert parse(folded) is None


COUNTED_INTEREST_SUMMARY = (
    "Checking Account Summary\n"
    "PREVIOUS BALANCE 100.00 AVERAGE BALANCE\n"
    "+ 3 CREDITS 300.50 150.00\n"
    "- 3 DEBITS 210.00 YTD INTEREST PAID\n"
    "- SERVICE CHARGES 5.00 .00\n"
    "+ INTEREST PAID .00\n"
    "ENDING BALANCE 185.50\n"
)


def test_a_bank_that_counts_its_own_interest_row_is_read_that_way_too():
    """The partition is the DOCUMENT'S, not this reader's.

    Here the same ledger is summarised with the interest row inside the credit
    count and total, and the interest term printing zero.  That is a different
    convention, not a defect, and the reader must publish it - which is only
    possible because it takes the partition from the printed counts rather
    than from a rule about what interest is.
    """
    stmt = parse(document(summary=COUNTED_INTEREST_SUMMARY))
    assert stmt is not None
    assert stmt.stated_credit_count == 3
    assert stmt.stated_interest_paid == 0.0
    assert len(stmt.transactions) == 7


MISDISTRIBUTED_SUMMARY = (
    "Checking Account Summary\n"
    "PREVIOUS BALANCE 100.00 AVERAGE BALANCE\n"
    "+ 2 CREDITS 300.00 150.00\n"
    "- 2 DEBITS 100.00 YTD INTEREST PAID\n"
    "- SERVICE CHARGES 115.00 .00\n"
    "+ INTEREST PAID .50\n"
    "ENDING BALANCE 185.50\n"
)


def test_the_partition_checks_the_distribution_and_not_only_the_total():
    """A summary whose every AGGREGATE matches and whose split cannot.

    The debit rows still come to `D + S`, the identity still closes, and the
    row count still equals `M` plus the two rows the count excludes.  What
    cannot be true is the split itself: no two of the captured debit rows come
    to the 115.00 the bank says it did not count.  Refusing here is the
    difference between checking a sum and checking the document.
    """
    misdistributed = document(summary=MISDISTRIBUTED_SUMMARY)
    summary = _summary(misdistributed)
    assert summary is not None
    assert summary.identity_holds
    assert round(summary.debits + summary.uncounted_debit, 2) == 215.00
    assert parse(misdistributed) is None


def test_an_uncounted_term_with_no_row_behind_it_is_refused():
    """The fee is printed in the summary and posts nowhere in the ledger.

    Two independent checks refuse this one - the partition and the daily walk
    - so the partition is asserted directly as well as end to end, rather than
    the end-to-end refusal being read as evidence about a check it does not
    isolate.
    """
    without_the_fee_row = (
        "e Other Debits\n"
        "Date Amount Description Date Amount Description\n"
        "03/04 100.00 SYNTHETIC DEBIT ONE 03/06 100.00 SYNTHETIC DEBIT TWO\n"
    )
    assert not _partition_holds([10.00, 100.00, 100.00], counted=3,
                                total=210.00, uncounted=5.00)
    assert parse(document(debits=without_the_fee_row)) is None


def test_the_partition_search_is_bounded_rather_than_unbounded():
    """A pathological document is refused, not searched.

    With one row excluded and a hundred rows to pick it from the search is
    trivial; the bound exists so that a document engineered to make it large
    fails closed instead of hanging the pipeline.
    """
    assert _partition_holds([1.00] * 100 + [7.00], counted=100,
                            total=100.00, uncounted=7.00)
    # 200 rows, half of them excluded, and a four-figure target: the aggregate
    # checks all pass and the split is refused because confirming it would
    # cost more search than this reader will spend.
    spread = [cents / 100 for cents in range(1, 201)]
    assert not _partition_holds(spread, counted=100, total=111.00,
                                uncounted=90.00)


def test_two_counted_terms_on_one_side_are_refused_rather_than_added_up():
    """A grid this reader has not been shown.  Adding the two together would
    be a guess about which rows each enumerates, and the count check - the one
    thing that catches a folded fee - is exactly what the guess disables."""
    two_credit_terms = (
        "Checking Account Summary\n"
        "PREVIOUS BALANCE 100.00 AVERAGE BALANCE\n"
        "+ 1 CREDITS 100.00 150.00\n"
        "+ 1 DEPOSITS 200.00\n"
        "- 3 DEBITS 210.00 YTD INTEREST PAID\n"
        "- SERVICE CHARGES 5.00 .00\n"
        "+ INTEREST PAID .50\n"
        "ENDING BALANCE 185.50\n"
    )
    assert _summary(document(summary=two_credit_terms)) is None
    assert parse(document(summary=two_credit_terms)) is None


#: The two mutants below both survived every other test in this file, which is
#: why they are here: the module's claim to have NO stop list for the summary's
#: right-hand statistics rests entirely on one invariant - a summary term OPENS
#: ITS PRINTED LINE WITH AN OPERATOR - and an invariant nothing pins is a
#: comment, not a contract.
#:
#: Both fixtures are payload-inert today: the statistic is ignored and the
#: published statement is identical to the base one, which is asserted field by
#: field rather than by "it parsed". Under either mutant the statistic becomes
#: an uncounted term, the identity stops closing, and the document is refused -
#: so each fixture fails loudly the moment its half of the invariant is relaxed.
_STATISTIC_ON_ITS_OWN_LINE = (
    "Checking Account Summary\n"
    "PREVIOUS BALANCE 100.00\n"
    "AVERAGE BALANCE 150.00\n"
    "+ 2 CREDITS 300.00\n"
    "- 3 DEBITS 210.00\n"
    "YTD INTEREST PAID 12.00\n"
    "- SERVICE CHARGES 5.00\n"
    "+ INTEREST PAID .50\n"
    "ENDING BALANCE 185.50\n"
)

#: The same, with the statistics bulleted by an EM DASH. `analysis/money.py`
#: keeps U+2014 out of `MINUS_CLASS` deliberately - "it is punctuation, not a
#: sign" - and this is the document that makes that exclusion load-bearing here
#: rather than incidental.
_STATISTIC_BULLETED = _STATISTIC_ON_ITS_OWN_LINE.replace(
    "AVERAGE BALANCE 150.00", "— AVERAGE BALANCE 150.00"
).replace("YTD INTEREST PAID 12.00", "— YTD INTEREST PAID 12.00")


@pytest.mark.parametrize(
    "summary", [_STATISTIC_ON_ITS_OWN_LINE, _STATISTIC_BULLETED],
    ids=["bare-statistic-line", "em-dash-bulleted-statistic"],
)
def test_an_undated_statistic_is_excluded_by_the_operator_and_not_by_a_name(summary):
    """A statistic printed on its own line is not a term, and no list says so.

    `AVERAGE BALANCE` and `YTD INTEREST PAID` are balances by name and would
    wreck the identity if summed into it: this document's would be out by
    150.00 and 12.00. They are excluded because they print no `+` or `-` at
    the head of their line - the platform's own notation for "this is a term
    of the arithmetic" - and for no other reason.
    """
    baseline = parse(document())
    with_statistics = parse(document(summary=summary))
    assert with_statistics is not None
    assert with_statistics.model_dump() == baseline.model_dump()


def test_the_operator_is_read_as_the_sign_and_not_assumed_from_the_label():
    """The direction of a term is the operator the bank printed on it.

    Flipping the two uncounted terms' operators - charges credited, interest
    levied - and re-deriving the closing balance produces a document that is
    just as internally consistent as the original and means something
    different. A reader that assumed "SERVICE CHARGES subtract" from the words
    would publish the first statement's arithmetic for the second one.
    """
    flipped = (
        "Checking Account Summary\n"
        "PREVIOUS BALANCE 100.00\n"
        "+ 2 CREDITS 300.00\n"
        "- 3 DEBITS 210.00\n"
        "+ SERVICE CHARGES 5.00\n"
        "- INTEREST PAID .50\n"
        "ENDING BALANCE 194.50\n"
    )
    summary = _summary(document(summary=flipped))
    assert summary is not None
    assert summary.identity_holds
    assert summary.uncounted_credit == 5.00 and summary.uncounted_debit == 0.50


def test_a_sub_dollar_figure_cannot_be_read_out_of_a_longer_number():
    """`-25.00` is twenty-five dollars, or it is nothing - never 25 cents.

    The sub-dollar branch exists for the `.00` this platform prints with no
    integer part, and unbounded it also matched the HEAD of a longer number.
    Every position the reader takes a figure from is checked against the
    printed oracle, so the misread failed documents closed rather than
    publishing them - but a misread one check away from a published figure is
    a defect waiting for the check to move.
    """
    from analysis.balance_by_date import _FIGURE, _figure

    found = re.compile(_FIGURE)
    assert found.search("-25.00").group() == "25.00"
    assert _figure("25.00") == 25.00
    # The forms the platform really prints still read as themselves.
    for token, value in ((".00", 0.0), ("-00", 0.0), (".50", 0.5), ("1,234.56", 1234.56)):
        assert found.search(token).group() == token
        assert _figure(token) == value


def test_the_printed_counts_are_not_comparable_to_the_rows_this_reader_builds():
    """A pin, not a formality.

    This parser's printed counts enumerate a strict SUBSET of the rows it
    publishes - the class `capital_one:debit` is already in the semantics
    table for - so the platform's count check must stay silent about it.  It
    does, because an unsurveyed parser is incomparable by default.  Promoting
    it would need measurement and a table entry, and this test is what makes
    that promotion deliberate instead of incidental.
    """
    assert counts_comparable("balance_by_date", "credit") is False
    assert counts_comparable("balance_by_date", "debit") is False


# ===========================================================================
# The two-column grids — duplication
# ===========================================================================

THREE_ROWS_ON_ONE_LINE = (
    "03/02 100.00 SYNTHETIC CREDIT ONE 03/05 200.00 SYNTHETIC CREDIT TWO "
    "03/31 .50 SYNTHETIC INTEREST\n"
)


def test_a_line_carrying_more_rows_than_the_grid_declared_columns_is_refused():
    crowded = (
        "e Deposits and Other Credits\n"
        "Date Amount Description Date Amount Description\n"
        f"{THREE_ROWS_ON_ONE_LINE}"
    )
    assert parse(document(credits=crowded)) is None


def test_the_same_line_is_read_when_the_grid_declares_three_columns():
    """The bound is the DOCUMENT'S declaration, not a constant.

    Identical rows, identical everything else; the only change is the printed
    legend.  A reader with `2` written into it would refuse this, and a reader
    with no bound at all would accept the one above.
    """
    declared = (
        "e Deposits and Other Credits\n"
        "Date Amount Description Date Amount Description Date Amount Description\n"
        f"{THREE_ROWS_ON_ONE_LINE}"
    )
    stmt = parse(document(credits=declared))
    assert stmt is not None
    assert sum(1 for t in stmt.transactions if t.direction == "credit") == 3


def test_a_row_read_twice_is_refused():
    duplicated = CREDITS + "03/02 100.00 SYNTHETIC CREDIT ONE\n"
    assert parse(document(credits=duplicated)) is None


def test_two_identical_rows_the_bank_really_printed_are_published():
    """The counterpart, and the reason this reader has no "no two rows may be
    alike" rule.

    Six of the eleven documents in the measured population post a pair of rows
    identical in date, amount AND description - two $377.27 insurance premiums
    on one day, two $5,000.00 transfers on another. A rule refusing repeated
    rows would refuse every one of them. What certifies the pair is the
    printed TOTAL, which accounts for both: an echo of one of them would push
    the captured total past the printed one, which is `test_a_row_read_twice_
    is_refused` above.
    """
    summary = (
        "Checking Account Summary\n"
        "PREVIOUS BALANCE 100.00\n"
        "+ 2 CREDITS 200.00\n"
        "- 0 DEBITS .00\n"
        "- SERVICE CHARGES .00\n"
        "+ INTEREST PAID .00\n"
        "ENDING BALANCE 300.00\n"
    )
    twice = (
        "e Deposits and Other Credits\n"
        "Date Amount Description Date Amount Description\n"
        "03/02 100.00 SYNTHETIC CREDIT 03/02 100.00 SYNTHETIC CREDIT\n"
    )
    daily = (
        "e Balance By Date\n"
        "Date Balance Date Balance Date Balance\n"
        "02/28 100.00 03/02 300.00\n"
    )
    stmt = parse(document(summary=summary, credits=twice, checks="", debits="", daily=daily))
    assert stmt is not None
    same_day = [t for t in stmt.transactions if t.date == "2026-03-02"]
    assert len(same_day) == 2
    assert same_day[0].amount == same_day[1].amount == 100.00
    assert same_day[0].description == same_day[1].description


#: A zero-amount row is the one row no printed figure on this template is a
#: witness to: it moves no total, no daily balance, and the count it moves can
#: be matched by the excluded side growing to meet it. These two documents are
#: the constructions that proved it, and they are refused by the rule that a
#: zero-amount row may not be one of the EXCLUDED.
_ZERO_ROW_ADDED = (
    "e Deposits and Other Credits\n"
    "Date Amount Description Date Amount Description\n"
    "03/02 100.00 SYNTHETIC CREDIT ONE 03/05 200.00 SYNTHETIC CREDIT TWO\n"
    "03/07 .00 SYNTHETIC ZERO CREDIT\n"
    "03/31 .50 SYNTHETIC INTEREST\n"
)

#: The daily grid the document above prints: a zero-amount row still posts on
#: a day, and the day it posts on carries the balance it did not change. The
#: grid is included so the WALK agrees and the partition is the only thing
#: left that can refuse - a fixture refused by two checks proves neither.
_DAILY_WITH_ZERO_DAY = (
    "e Balance By Date\n"
    "Date Balance Date Balance Date Balance\n"
    "02/28 100.00 03/04 90.00 03/07 190.00\n"
    "03/02 200.00 03/05 290.00 03/31 185.50\n"
    "03/03 190.00 03/06 190.00\n"
)

#: The same summary with the zero row COUNTED by the bank: three credits, and
#: the same 300.00 total, because the row is worth nothing.
_COUNTS_THE_ZERO_ROW = (
    "Checking Account Summary\n"
    "PREVIOUS BALANCE 100.00 AVERAGE BALANCE\n"
    "+ 3 CREDITS 300.00 150.00\n"
    "- 3 DEBITS 210.00 YTD INTEREST PAID\n"
    "- SERVICE CHARGES 5.00 .00\n"
    "+ INTEREST PAID .50\n"
    "ENDING BALANCE 185.50\n"
)


def test_a_zero_amount_row_the_bank_did_not_count_is_refused():
    """Eight rows published against the seven the document accounts for.

    The summary is untouched, so it still counts two credits and one uncounted
    interest row; the reader captured four. Every aggregate agrees - the
    captured credit total is 300.50 either way, the identity closes, and the
    daily grid agrees day for day, because the extra row is worth nothing.
    Only the rule that the excluded side is made of rows the printed lump can
    account for refuses it.
    """
    invented = document(credits=_ZERO_ROW_ADDED, daily=_DAILY_WITH_ZERO_DAY)
    summary = _summary(invented)
    assert summary is not None and summary.identity_holds
    # Isolated: the walk and the totals are satisfied, the partition is not.
    assert not _partition_holds([100.00, 200.00, 0.00, 0.50], counted=2,
                                total=300.00, uncounted=0.50)
    assert parse(invented) is None
    # And it is the ZERO that does it. Give the same invented row an amount
    # and the TOTAL catches it instead, so neither check stands in for the
    # other and neither is redundant.
    assert not _partition_holds([100.00, 200.00, 7.00, 0.50], counted=2,
                                total=300.00, uncounted=0.50)


def test_a_zero_amount_row_the_bank_counted_is_published():
    """The other side of the same rule, and the reason it is not "refuse every
    zero-amount row".

    This platform posts genuine zero-amount rows - a returned ACH of $0.00
    that the bank counts as one credit - and `analysis/community_section.py`
    and `analysis/reconcile.py` both state the same rule for the same reason.
    Counted, the row lands on the side the printed count vouches for, and it
    publishes.
    """
    stmt = parse(document(summary=_COUNTS_THE_ZERO_ROW, credits=_ZERO_ROW_ADDED,
                          daily=_DAILY_WITH_ZERO_DAY))
    assert stmt is not None
    assert stmt.stated_credit_count == 3
    zero_rows = [t for t in stmt.transactions if t.amount == 0.0]
    assert len(zero_rows) == 1 and zero_rows[0].direction == "credit"


def test_a_zero_amount_row_read_twice_is_refused():
    """The echo the review constructed: the bank counted one zero row and the
    reader captured two. The pair moves no total and no daily balance, and the
    count it moves would be absorbed by the excluded side growing to meet it.
    """
    echoed = _ZERO_ROW_ADDED.replace(
        "03/07 .00 SYNTHETIC ZERO CREDIT\n",
        "03/07 .00 SYNTHETIC ZERO CREDIT\n03/07 .00 SYNTHETIC ZERO CREDIT\n",
    )
    assert not _partition_holds([100.00, 200.00, 0.00, 0.00, 0.50], counted=3,
                                total=300.00, uncounted=0.50)
    assert parse(document(summary=_COUNTS_THE_ZERO_ROW, credits=echoed,
                          daily=_DAILY_WITH_ZERO_DAY)) is None


def test_a_grid_whose_legend_this_reader_cannot_resolve_is_refused():
    unknown = (
        "e Deposits and Other Credits\n"
        "Date Amount Reference Date Amount Reference\n"
        "03/02 100.00 SYNTHETIC CREDIT ONE 03/05 200.00 SYNTHETIC CREDIT TWO\n"
        "03/31 .50 SYNTHETIC INTEREST\n"
    )
    assert parse(document(credits=unknown)) is None


def test_the_cheque_grid_is_read_by_its_own_legend_and_not_the_amount_one():
    """`Date Serial Amount` puts the serial between the date and the money.
    Read with the `Date Amount Description` grammar the serial IS the money,
    and the debit total is then wrong by every cheque on the statement."""
    stmt = parse(document())
    assert stmt is not None
    assert round(sum(-t.amount for t in stmt.transactions if t.amount < 0), 2) == 215.00


# ===========================================================================
# The daily grid — the independent walk
# ===========================================================================

def test_a_daily_grid_that_disagrees_on_one_day_refuses_the_document():
    wrong_day = DAILY.replace("03/04 90.00", "03/04 95.00")
    assert wrong_day != DAILY
    assert parse(document(daily=wrong_day)) is None


def test_a_daily_grid_naming_a_day_the_ledger_never_posted_is_refused():
    extra_day = DAILY.replace("03/03 190.00 03/06 190.00",
                              "03/03 190.00 03/06 190.00 03/09 190.00")
    assert parse(document(daily=extra_day)) is None


def test_a_daily_grid_that_does_not_open_on_the_previous_balance_is_refused():
    wrong_open = DAILY.replace("02/28 100.00", "02/28 101.00")
    assert parse(document(daily=wrong_open)) is None


def test_a_repeated_day_in_the_daily_grid_is_refused():
    repeated = DAILY + "03/06 190.00\n"
    assert parse(document(daily=repeated)) is None


def test_a_document_without_a_daily_grid_is_not_even_claimed():
    """The walk is one of the constraints, so a document that cannot supply it
    is refused at detection rather than parsed and then declined."""
    assert not detect(document(daily="")).claims
    assert parse(document(daily="")) is None


# ===========================================================================
# Overdrawn days
# ===========================================================================

OVERDRAWN = (
    "--- Page 1 ---\n\n"
    "PO Box 0 Springfield, ZZ 00000\n"
    "Electronic Service Requested 03/01/2026 - 03/31/2026\n"
    "Checking Account Summary\n"
    "PREVIOUS BALANCE .00 AVERAGE BALANCE\n"
    "+ 1 CREDITS 60.00 5.00\n"
    "- 1 DEBITS 50.00 YTD INTEREST PAID\n"
    "- SERVICE CHARGES -00 -00\n"
    "+ INTEREST PAID .00\n"
    "ENDING BALANCE 10.00\n"
    "e Deposits and Other Credits\n"
    "Date Amount Description Date Amount Description\n"
    "03/03 60.00 SYNTHETIC CREDIT\n"
    "e Other Debits\n"
    "Date Amount Description Date Amount Description\n"
    "03/02 50.00 SYNTHETIC DEBIT\n"
    "e Balance By Date\n"
    "Date Balance Date Balance Date Balance\n"
    "02/28 .00 03/02 50.00 OD 03/03 10.00\n"
)


def test_an_overdrawn_day_is_read_from_the_marker_the_grid_prints():
    """The grid prints magnitudes; `OD` is how it prints the sign.  Ignoring
    the marker turns a -50.00 day into a +50.00 one and the walk disagrees, so
    the marker is read - and the magnitude still has to match, which is what
    keeps reading it from being a way to manufacture agreement."""
    stmt = parse(OVERDRAWN)
    assert stmt is not None
    assert [(s.date, s.balance) for s in stmt.stated_daily_balances] == [
        ("2026-03-02", -50.00), ("2026-03-03", 10.00)
    ]


def test_an_overdrawn_day_printed_without_its_marker_refuses_the_document():
    assert parse(OVERDRAWN.replace("03/02 50.00 OD", "03/02 50.00")) is None


def test_the_printed_sub_dollar_zero_is_read_in_both_of_its_spellings():
    """`.00` and `-00` are the same printed figure; a scanned print stream
    resolves the leading dot as a hyphen on some lines and not others, and
    this document carries both."""
    assert "SERVICE CHARGES -00" in OVERDRAWN and "INTEREST PAID .00" in OVERDRAWN
    stmt = parse(OVERDRAWN)
    assert stmt.beginning_balance == 0.0
    assert stmt.stated_service_charge == 0.0
    assert stmt.stated_interest_paid == 0.0


# ===========================================================================
# Period and dates
# ===========================================================================

def test_a_row_dated_outside_the_printed_period_refuses_the_document():
    outside = CREDITS.replace("03/05 200.00", "04/05 200.00")
    assert parse(document(credits=outside)) is None


def test_pages_that_disagree_about_the_period_refuse_the_document():
    disagreeing = document() + "Electronic Service Requested 04/01/2026 - 04/30/2026\n"
    assert parse(disagreeing) is None


def test_two_different_account_numbers_publish_neither():
    stmt = parse(document() + "Account Number: 900001\n")
    assert stmt is not None
    assert stmt.account_number is None


# ===========================================================================
# Detection
# ===========================================================================

def test_the_partition_itself_is_the_marker():
    """A summary of an opening balance, two counted totals and a closing
    balance is the ordinary shape of every bank's summary.  What identifies
    this template is a term that carries NO count printed beside terms that
    do - so a document without one must not be claimed, even though every
    other piece of furniture is present."""
    unpartitioned = (
        "Checking Account Summary\n"
        "PREVIOUS BALANCE 100.00\n"
        "+ 2 CREDITS 300.00\n"
        "- 4 DEBITS 214.50\n"
        "ENDING BALANCE 185.50\n"
    )
    assert not detect(document(summary=unpartitioned)).claims


def test_detection_needs_both_markers_and_the_fixture_document_has_both():
    detection = detect(document())
    assert detection.claims
    assert set(detection.matched) == {"partitioned_summary", "balance_by_date_grid"}


@pytest.mark.parametrize("text", [
    "",
    "PREVIOUS BALANCE 100.00\nENDING BALANCE 100.00\n",
    "e Balance By Date\nDate Balance Date Balance\n03/01 1.00\n",
    "This is a lease agreement between the parties named below.",
])
def test_documents_that_are_not_this_template_are_not_claimed(text):
    assert not detect(text).claims


def test_parse_rechecks_detection_and_never_trusts_the_caller():
    assert parse("a lease agreement, not a bank statement") is None


def test_the_detection_prefilters_change_no_outcome():
    """Both markers are guarded by a cheap literal prefilter so the sweep does
    not pay a line-anchored scan on documents it will reject. Each prefilter
    is a strictly necessary condition of the pattern behind it, so it may only
    make the marker faster - never quieter. Run against every registration's
    conformance fixture, this cell's own documents, and the mutants above.
    """
    from tests.data.parser_conformance_fixtures import ALTERNATE_FIXTURES, FIXTURES

    corpus = [
        *FIXTURES.values(),
        *(doc for docs in ALTERNATE_FIXTURES.values() for doc in docs),
        document(),
        document(summary=FOLDED_SUMMARY),
        document(daily=""),
        OVERDRAWN,
        "PREVIOUS BALANCE 1.00\nENDING BALANCE 1.00\nBalance By Date\n",
        "balance by date\nprevious balance 1.00\n",
        "",
    ]
    for text in corpus:
        assert bbd._has_daily_grid(text) == bool(bbd._DAILY_HEAD_RE.search(text))
        gated = bbd._has_partitioned_summary(text)
        previous = bbd._PREVIOUS_RE.search(text)
        ending = previous and bbd._ENDING_RE.search(text, previous.end())
        ungated = bool(
            ending
            and bbd._COUNTED_TERM_RE.search(text[previous.end():ending.start()])
            and bbd._UNCOUNTED_TERM_RE.search(text[previous.end():ending.start()])
        )
        assert gated == ungated, text[:60]

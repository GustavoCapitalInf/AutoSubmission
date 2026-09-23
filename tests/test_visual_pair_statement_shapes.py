"""Fabricated statements only. Statement shapes the visual pair reads through the page's own print:

* a statement that prints only its closing date opens the day after the previous statement's ("Your previous
  balance as of ...");
* a cut-off read of a page listing no transaction (terms, a balancing form printing only the ending balance)
  holds nothing, unless the proposer read more there than the text layer prints (a scanned body);
* rows no reader gave a direction are no transactions when the directed rows already make the printed totals
  (a summary of cheques repeating the transaction history, items returned unpaid);
* a zero amount stands where the row's own line prints it, and a line printed without any amount is none.
"""
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.native_text import PrintedEvidence
from vlm.pair import exclude_undirected_by_totals, pages_without_transactions, previous_balance_period_start


def _period(texts, end="2031-04-17"):
    account = {"period_start": None, "period_end": end}
    reasons = ["period_mismatch"]
    occurrences = [{"code": "period_mismatch", "page": None, "field": "period_start", "source": "metadata"}]
    evidence = []
    audit = previous_balance_period_start(account, reasons, occurrences, evidence, texts)
    return account, reasons, occurrences, evidence, audit


def test_the_period_opens_the_day_after_the_previous_statements_closing_date():
    account, reasons, occurrences, evidence, audit = _period(
        ["FABRICATED CHECKING\nYour previous balance as of 03/18/2031 $1,234.57\nYour new balance as of 04/17/2031"])
    assert account["period_start"] == "2031-03-19"
    assert reasons == [] and occurrences == []
    assert audit == {"period_start": "2031-03-19", "page": 1, "settled_holds": 1}
    assert evidence == [{"field": "period_start", "page": 1, "source": "text_layer_previous_balance_date",
                         "value": "2031-03-19"}]


def test_no_period_start_without_one_unambiguous_printed_date_in_reach():
    # Two different printed dates, a date too far from the end, and a date both month-first and day-first
    # readings put in reach (03/04 and 04/03 against an end of 04/17) settle nothing.
    for texts in (["Previous balance as of 03/18/2031 1.00", "Previous balance as of 03/19/2031 1.00"],
                  ["Previous balance as of 01/10/2031 1.00"],
                  ["Previous balance as of 03/04/2031 1.00"]):
        account, reasons, _, evidence, audit = _period(texts)
        assert account["period_start"] is None and reasons == ["period_mismatch"] and audit is None, texts
    # A printed start stays as it is.
    account = {"period_start": "2031-03-01", "period_end": "2031-03-31"}
    assert previous_balance_period_start(account, [], [], [], ["Previous balance as of 02/27/2031 1.00"]) is None
    assert account["period_start"] == "2031-03-01"


BALANCING_FORM = """How to Balance your Account
Begin by adjusting your account register as follows: subtract any services charges shown on this statement,
subtract any automatic payments, transfers or other electronic withdrawals not previously recorded.
Your ending balance shown on this statement is:
2,468.13
List below the amount of deposits or credit transfers which do not appear on this statement.
"""
PROPOSER_READING = ("How to Balance your Account Begin by adjusting your account register as follows subtract "
                    "any services charges shown on this statement subtract any automatic payments transfers")


def test_a_page_printing_no_amount_but_the_statements_balances_lists_no_transaction():
    account = {"beginning_balance": 1000.0, "ending_balance": 2468.13}
    pages = [PrintedEvidence(native=BALANCING_FORM, proposer=PROPOSER_READING),
             PrintedEvidence(native="Terms and conditions of your account apply.", proposer=""),
             PrintedEvidence(native=BALANCING_FORM.replace("2,468.13", "2,468.14"), proposer=PROPOSER_READING),
             PrintedEvidence(native=None, proposer=PROPOSER_READING)]
    assert pages_without_transactions(pages, account) == frozenset({1, 2})


def test_a_printed_header_over_a_scanned_body_is_not_a_page_without_transactions():
    # The text layer prints the header and the ending balance; the proposer read rows the text layer lacks.
    header = "FABRICATED BANK\nPage 2 of 3\nEnding balance 2,468.13\n"
    rows = " ".join(f"04/{day:02d} FABRICATED MERCHANT NUMBER {day} PURCHASE" for day in range(1, 12))
    account = {"beginning_balance": 1000.0, "ending_balance": 2468.13}
    assert pages_without_transactions([PrintedEvidence(native=header, proposer=rows)], account) == frozenset()


def _row(amount, direction, locator, page=1):
    return CandidateRow("2031-03-03", "3/3", f"FABRICATED ROW {locator}", Decimal(amount), direction, None, page,
                        "stage_b", locator)


ACCOUNT = {"beginning_balance": 500.0, "ending_balance": 650.0, "stated_total_credits": 400.0,
           "stated_total_debits": 250.0}


def test_undirected_rows_the_printed_totals_leave_no_room_for_are_no_transactions():
    rows = [_row("400.00", "credit", "t0r1"), _row("250.00", "debit", "t0r2"),
            _row("75.25", "unknown", "t1r1", page=4), _row("250.00", "unknown", "t1r2", page=4)]
    kept, audit = exclude_undirected_by_totals(rows, ACCOUNT)
    assert [row.locator for row in kept] == ["t0r1", "t0r2"]
    assert audit == {"rows": 2, "locators": [[4, "t1r1"], [4, "t1r2"]]}


def test_undirected_rows_stay_when_the_directed_rows_do_not_make_the_printed_figures():
    rows = [_row("400.00", "credit", "t0r1"), _row("175.00", "debit", "t0r2"), _row("75.00", "unknown", "t1r1")]
    kept, audit = exclude_undirected_by_totals(rows, ACCOUNT)   # the undirected row is a missing debit
    assert len(kept) == 3 and audit is None
    counted = dict(ACCOUNT, stated_debit_count=2)
    rows = [_row("400.00", "credit", "t0r1"), _row("250.00", "debit", "t0r2"), _row("75.00", "unknown", "t1r1")]
    assert exclude_undirected_by_totals(rows, counted)[1] is None                  # the printed count says two
    assert exclude_undirected_by_totals(rows, dict(ACCOUNT, stated_total_debits=None))[1] is None
    # An undirected row with a printed balance takes its direction from the balance chain instead.
    balanced = rows[:2] + [CandidateRow("2031-03-03", "3/3", "FABRICATED", Decimal("75.00"), "unknown",
                                        Decimal("575.00"), 1, "stage_b", "t1r1")]
    assert exclude_undirected_by_totals(balanced, ACCOUNT)[1] is None


def test_a_daily_balance_table_opening_with_the_carried_in_balance_is_not_a_day_of_the_statement():
    from vlm.pair import opening_balance_days
    account = {"period_start": "2031-04-01", "beginning_balance": 1234.57}
    daily = [{"date": "2031-03-31", "balance": 1234.57}, {"date": "2031-04-01", "balance": 1100.0}]
    assert opening_balance_days(daily, account) == ([{"date": "2031-04-01", "balance": 1100.0}], ["2031-03-31"])
    # Any other day before the period stays, for the analysis to refuse.
    other = [{"date": "2031-03-30", "balance": 99.0}, *daily[1:]]
    assert opening_balance_days(other, account) == (other, [])


ZERO_PAGE = """Other withdrawals, debits and service charges
DATE DESCRIPTION AMOUNT($)
03/19 AutoPay Fabricated Lender 4417 Fabricated Payer 0.00
03/20 FABRICATED HARDWARE PURCHASE 57.25
Checks
DATE CHECK # AMOUNT($) DATE CHECK # AMOUNT($)
03/23 301~ 03/24 302 81.40
"""


def test_a_zero_amount_stands_where_its_own_line_prints_it():
    from vlm.review import merge_review
    from vlm.schema import empty_review
    payload = empty_review("statement_page")
    payload["added"] = [
        {"after_candidate_id": None,
         "row": {"date": "2031-03-19", "date_text": "03/19", "description": "AutoPay Fabricated Lender 4417 Fabricated Payer",
                 "amount": 0.0, "direction": "debit", "balance": None, "bbox": None, "printed_amount": None}},
        {"after_candidate_id": None,
         "row": {"date": "2031-03-23", "date_text": "03/23", "description": "301~", "amount": 0.0,
                 "direction": "debit", "balance": None, "bbox": None, "printed_amount": None}}]
    merged = merge_review([], payload, page=1, printed=PrintedEvidence(native=ZERO_PAGE))
    assert [row.description for row in merged.rows] == ["AutoPay Fabricated Lender 4417 Fabricated Payer"]
    states = {item["locator"]: (item["state"], item["reason"]) for item in merged.evidence}
    assert states == {"added0": ("added", "reviewer_only"), "added1": ("rejected", "addition_amount_not_printed")}
    # Without a text layer a zero amount cannot be told from a line printed without one: it stays unresolved.
    unread = merge_review([], payload, page=1, printed=None)
    assert unread.rows == () and unread.counts["unresolved"] == 2

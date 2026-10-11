"""The owner's request of 2026-10-10 (active positions by month; true revenue spec §2.2, §9.1, §9.2, §10, §20): "One
thing i want to add right now and it should also be included in the demo website is the active Position count by
month." His answers (all the recommended options): confirmed lenders count, potential lenders are shown beside them
apart ("2 active positions (+1 possible)"), alternative positions, lines of credit, credit cards and every other flag
group stay out; one funder paying on two schedules is 2 positions, a small fee stream never one; a position is active
in a month when a payment cleared that month (bounced attempts alone never count).

The pure reading (analysis/active_positions.py over analysis/lender_payment_changes.py's positions) on fabricated
classification records, and the package's per-statement and per-month counts through webapp.app._package_analysis on
fabricated statements analysed by the real pipeline. Computed when served: nothing stored moves, and the payment
changes stay byte-identical.

Fabricated data only: CONTOSO PLUMBING LLC; FABRIKAM and NORTHWIND payees; KAPITUS and ONDECK (public funders of the
registry) and DAILY FUNDING (a generic potential lender alias of the registry) as descriptors; SHOPIFY CAPITAL and
SQUARE CAPITAL (public alternative positions) as descriptors; the tests' 2054 dates; whole amounts."""
from __future__ import annotations

import copy
from datetime import date

import pytest

from analysis import active_positions as ap
from analysis import lender_payment_changes as lpc
from tests.test_lender_payment_changes import _located, _potential, _row, _rows, bdays, every


def J(day):  # noqa: N802
    return date(2054, 1, day)


def F(day):  # noqa: N802
    return date(2054, 2, day)


def M(day):  # noqa: N802
    return date(2054, 3, day)


def A(day):  # noqa: N802
    return date(2054, 4, day)


JAN = ("2054-01-01", "2054-01-31")
FEB = ("2054-02-01", "2054-02-28")
MAR = ("2054-03-01", "2054-03-31")
APR = ("2054-04-01", "2054-04-30")


def chain(*months):
    """A chain of one account's statements: each (rows, (period start, period end)), USD."""
    return [lpc.StatementRows(_located(rows), start, end, "USD") for rows, (start, end) in months]


def counts(statements):
    return [(entry["active_positions"], entry["possible_positions"])
            for entry in ap.chain_active_positions(statements)]


def alone(rows, period):
    found = ap.statement_active_positions(_located(rows), period_start=period[0], period_end=period[1],
                                          currency="USD")
    return found["active_positions"], found["possible_positions"]


# ------------------------------------------------------------------------------- the definition, on fabricated rows
def test_one_weekly_stream_paid_every_week_is_one_position_each_month():
    months = [(_rows(every(J(5), J(26)), 1000), JAN), (_rows(every(F(2), F(23)), 1000), FEB),
              (_rows(every(M(2), M(30)), 1000), MAR)]
    assert counts(chain(*months)) == [(1, 0), (1, 0), (1, 0)]
    assert [alone(rows, period) for rows, period in months] == [(1, 0), (1, 0), (1, 0)]


def test_a_daily_and_a_weekly_stream_of_one_funder_at_the_same_time_are_two_positions():
    daily, weekly = _rows(bdays(M(2), M(31)), 300), _rows(every(M(2), M(30)), 2000)
    # The module reads two positions (two streams with one funder).
    [series] = lpc.series_positions([lpc.StatementRows(_located(daily + weekly), *MAR, "USD")])
    assert [position.number for position in series.positions] == [1, 2]
    assert alone(daily + weekly, MAR) == (2, 0)
    jan = _rows(bdays(J(5), J(30)), 300) + _rows(every(J(5), J(26)), 2000)
    assert counts(chain((jan, JAN), (daily + weekly, MAR))) == [(2, 0), (2, 0)]


def test_a_small_fee_stream_beside_a_main_stream_is_one_position():
    rows = _rows(every(M(2), M(30)), 1000) + _rows(every(M(2), M(30)), 25)
    assert alone(rows, MAR) == (1, 0)
    # A token one-off beside the main stream is no position either, and neither is one in a month the stream skipped.
    months = [(_rows(every(J(5), J(26)), 1000), JAN), (_rows([F(9)], 15), FEB), (_rows(every(M(2), M(30)), 1000), MAR)]
    assert counts(chain(*months)) == [(1, 0), (0, 0), (1, 0)]


def test_a_stream_paused_for_a_whole_month_is_zero_that_month_and_one_before_and_after():
    months = [(_rows(every(J(5), J(26)), 1000), JAN), ([], FEB), (_rows(every(M(2), M(30)), 1000), MAR)]
    assert counts(chain(*months)) == [(1, 0), (0, 0), (1, 0)]
    assert alone([], FEB) == (0, 0)


def test_a_month_where_every_attempt_bounced_is_zero():
    bounced = _rows(every(F(2), F(23)), 1000, returned_funder_payment_by="transaction:99")
    months = [(_rows(every(J(5), J(26)), 1000), JAN), (bounced, FEB), (_rows(every(M(2), M(30)), 1000), MAR)]
    assert counts(chain(*months)) == [(1, 0), (0, 0), (1, 0)]
    assert alone(bounced, FEB) == (0, 0)


def test_a_bounced_payment_re_debited_makes_its_month_active():
    # R3-73: the funder re-debited the returned payment of 02-02 on 02-04; the re-debit is the payment it is.
    february = (_rows([F(2)], 1000, returned_funder_payment_by="transaction:99", represented_by="transaction:3")
                + _rows([F(4)], 1000)
                + _rows(every(F(9), F(23)), 1000, returned_funder_payment_by="transaction:98"))
    months = [(_rows(every(J(5), J(26)), 1000), JAN), (february, FEB), (_rows(every(M(2), M(30)), 1000), MAR)]
    assert counts(chain(*months)) == [(1, 0), (1, 0), (1, 0)]
    assert alone(february, FEB) == (1, 0)


def test_a_potential_lender_stream_is_a_possible_position_never_a_confirmed_one():
    rows = _rows(every(M(2), M(30)), 1000) + _potential(every(M(4), M(25)), 1500)
    assert alone(rows, MAR) == (1, 1)
    assert alone(_potential(every(M(4), M(25)), 1500), MAR) == (0, 1)


@pytest.mark.parametrize("state, entity", [("alternative_position", "SHOPIFY CAPITAL"),
                                           ("alternative_position", "SQUARE CAPITAL"),
                                           ("line_of_credit", None), ("credit_card_payment", "Sample Card")])
def test_an_alternative_position_a_line_of_credit_and_a_card_payment_never_count(state, entity):
    rows = _rows(every(M(2), M(30)), 900, entity=entity, state=state, contributes_to_lender_totals=True)
    assert alone(rows, MAR) == (0, 0)
    assert alone(rows + _rows(every(M(4), M(25)), 1000), MAR) == (1, 0)


def test_a_catch_up_level_beside_its_stream_is_no_second_position():
    # The precision sample's one catch-up shape: a weekly 500 stream whose debits bounced, then two debits of exactly
    # twice the payment on its beat. The module reads the 1,000 level as a second, concurrent position; it is the
    # first one catching up (A8's catch-up: 2x or 3x, never longer than 2 payments), so the statement holds 1.
    rows = (_rows([F(12), F(19), F(26)], 500) + _rows([F(19), F(24)], 1000)
            + _rows([F(3), F(10)], 1000, returned_funder_payment_by="transaction:99")
            + _rows([F(5)], 500, returned_funder_payment_by="transaction:98"))
    [series] = lpc.series_positions([lpc.StatementRows(_located(rows), *FEB, "USD")])
    assert [position.number for position in series.positions] == [1, 2]
    assert alone(rows, FEB) == (1, 0)
    # A stream at twice another's amount that pays more than twice is a position of its own.
    rows = _rows(every(M(2), M(30)), 500) + _rows(every(M(2), M(30)), 1000)
    assert alone(rows, MAR) == (2, 0)
    # Its payments are the first stream's presence: a month the catch-up alone paid in is active.
    months = [(_rows(every(J(5), J(26)), 500), JAN), (_rows([F(19), F(24)], 1000), FEB)]
    assert counts(chain(*months)) == [(1, 0), (1, 0)]


def test_one_payment_split_into_two_debits_on_the_same_days_is_one_position():
    # The precision sample's split shape: a weekly 1,250 payment bounced, cleared once, then came as two debits on the
    # same days, 1,000 and 250, that add up to it. The module reads two concurrent positions; it is one, split.
    split = _rows([M(17), M(24), M(31)], 1000) + _rows([M(17), M(24), M(31)], 250)
    rows = split + _rows([M(3), M(5)], 1250, returned_funder_payment_by="transaction:99") + _rows([M(10)], 1250)
    [series] = lpc.series_positions([lpc.StatementRows(_located(rows), *MAR, "USD")])
    assert [position.number for position in series.positions] == [1, 2]
    assert alone(rows, MAR) == (1, 0)
    # Only bounced: the attempts at the whole amount are the evidence too.
    assert alone(split + _rows([M(3), M(5)], 1250, returned_funder_payment_by="transaction:99"), MAR) == (1, 0)
    # Across a chain: February paid 1,250 weekly, March the two parts.
    assert counts(chain((_rows(every(F(3), F(24)), 1250), FEB), (split, MAR))) == [(1, 0), (1, 0)]
    # Without a payment or an attempt at their sum before them, two debits on the same days are two positions.
    assert alone(split, MAR) == (2, 0)
    assert alone(split + _rows([M(10)], 1300), MAR) == (2, 0)


def test_a_cleared_fee_beside_bounced_payments_is_no_position():
    # Every weekly payment bounced and the funder's token fee cleared: no payment of the position cleared.
    rows = _rows(every(F(2), F(23)), 1000, returned_funder_payment_by="transaction:99") + _rows([F(24)], 35)
    assert alone(rows, FEB) == (0, 0)
    # A one-off of 5% of the bounced payment or more is a payment.
    assert alone(_rows(every(F(2), F(23)), 1000, returned_funder_payment_by="transaction:99")
                 + _rows([F(24)], 300), FEB) == (1, 0)


def test_a_potential_payee_under_the_payment_changes_floor_is_no_possible_position():
    # A10: a potential series under $100 a week is noise to the payment changes (a coffee or fuel card purchase on a
    # schedule reads as a payee); it is no possible position either. A confirmed lender has no floor.
    assert alone(_potential(every(M(2), M(30)), 25), MAR) == (0, 0)
    assert alone(_potential([M(9)], 60), MAR) == (0, 0)
    assert alone(_potential([M(9)], 150), MAR) == (0, 1)
    assert alone(_potential(bdays(M(2), M(31)), 25), MAR) == (0, 1)
    assert alone(_rows(every(M(2), M(30)), 25), MAR) == (1, 0)


def test_a_monthly_payment_seen_once_in_a_statement_is_one_position():
    # One payment a statement joins no level of the statement alone; across the chain it is one monthly stream.
    months = [(_rows([J(15)], 2500, entity="ONDECK"), JAN), (_rows([F(16)], 2500, entity="ONDECK"), FEB),
              (_rows([M(16)], 2500, entity="ONDECK"), MAR)]
    assert [alone(rows, period) for rows, period in months] == [(1, 0), (1, 0), (1, 0)]
    assert counts(chain(*months)) == [(1, 0), (1, 0), (1, 0)]


def test_a_payment_dated_outside_the_printed_period_counts_in_no_period():
    rows = _rows([date(2054, 2, 27)], 1000) + _rows(every(M(9), M(30)), 1000)
    assert alone(_rows([date(2054, 2, 27)], 1000), MAR) == (0, 0)
    assert alone(rows, MAR) == (1, 0)


def test_a_missing_period_bound_is_open():
    rows = _rows(every(M(2), M(30)), 1000)
    assert alone(rows, (None, None)) == (1, 0)
    assert alone(rows, ("2054-03-01", None)) == (1, 0)


def test_series_positions_never_moves_the_payment_changes():
    rows = (_rows(every(M(2), M(30)), 1000) + _rows(every(M(18), date(2054, 4, 29)), 1200)
            + _potential(bdays(M(2), M(13)), 300) + _potential(bdays(M(16), M(25)), 200))
    statements = [lpc.StatementRows(_located(rows), "2054-03-01", "2054-04-30", "USD")]
    before = copy.deepcopy(lpc.payment_changes(statements))
    lpc.series_positions(statements)
    ap.chain_active_positions(statements)
    assert lpc.payment_changes(statements) == before


# ------------------------------------------------------------------------------------- the package, through the app
def _pkg():
    from tests import test_lender_payment_changes_package as pkg

    return pkg


NORTHWIND = "NORTHWIND FUNDING DES:DEBIT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000003 PPD"
SHOPIFY = "SHOPIFY CAPITAL DES:LOAN PMT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000005 CCD"
SQUARE = "SQUARE CAPITAL DES:LOAN ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000006 CCD"
LINE = "SAMPLE BANK LOC PAYMENT"
CARD = "AMEX EPAYMENT ACH PMT"


def _rows_of(built):
    return {doc["id"]: (doc.get("active_positions"), doc.get("possible_positions")) for doc in built["documents"]}


def _months(built):
    return [(entry["month"], entry["active_positions"], entry["possible_positions"])
            for entry in built["active_positions_by_month"]]


def three_months():
    """Account A: KAPITUS weekly from March to May; ONDECK daily from April (a second funder); a NORTHWIND FUNDING
    potential lender weekly in May; alternative positions, a line of credit and a card payment every week."""
    pkg = _pkg()
    others = lambda first, last: [*pkg.debits(every(first, last), 700, SHOPIFY), *pkg.debits(every(first, last), 650, SQUARE),
                                  *pkg.debits(every(first, last), 600, LINE), *pkg.debits(every(first, last), 550, CARD)]
    march = pkg.statement_payload(pkg.debits(every(M(4), M(25)), 1000) + others(M(4), M(25)), month=3)
    april = pkg.statement_payload(pkg.debits(every(pkg.A(1), pkg.A(29)), 1000)
                                  + pkg.debits(bdays(pkg.A(1), pkg.A(30)), 300, pkg.ONDECK)
                                  + others(pkg.A(1), pkg.A(29)), month=4, opening=pkg.closing(march))
    may = pkg.statement_payload(pkg.debits(every(pkg.Y(6), pkg.Y(27)), 1000)
                                + pkg.debits(bdays(pkg.Y(1), pkg.Y(29)), 300, pkg.ONDECK)
                                + pkg.debits(every(pkg.Y(6), pkg.Y(27)), 1500, NORTHWIND)
                                + others(pkg.Y(6), pkg.Y(27)), month=5, opening=pkg.closing(april))
    return march, april, may


def test_a_package_of_three_months_of_one_account_counts_each_month():
    pkg = _pkg()
    march, april, may = three_months()
    built = pkg.package(pkg.job("march", march), pkg.job("april", april), pkg.job("may", may))
    assert _rows_of(built) == {"march": (1, 0), "april": (2, 0), "may": (2, 1)}
    assert _months(built) == [("2054-03", 1, 0), ("2054-04", 2, 0), ("2054-05", 2, 1)]
    # The Monthly Statements rows carry the same figures (`monthly` lists the same member rows).
    assert {doc["id"]: doc["active_positions"] for doc in built["monthly"]} == {"march": 1, "april": 2, "may": 2}
    # Each statement viewed alone reads its own rows.
    from webapp.app import _displayed

    served = [_displayed(payload, settings={})["metrics"] for payload in (march, april, may)]
    assert [(metrics["active_positions"], metrics["possible_positions"]) for metrics in served] == [
        (1, 0), (2, 0), (2, 1)]


def test_a_package_of_two_accounts_adds_each_account_s_positions_up():
    # P6's shape: account A pays KAPITUS 1,000 weekly, account B 700 weekly, in March and April: two positions a month.
    pkg = _pkg()
    a_march = pkg.statement_payload(pkg.debits(every(M(4), M(25)), 1000), month=3)
    a_april = pkg.statement_payload(pkg.debits(every(pkg.A(1), pkg.A(29)), 1000), month=4, opening=pkg.closing(a_march))
    b_march = pkg.statement_payload(pkg.debits(every(M(4), M(25)), 700), month=3, account=pkg.ACCOUNT_B)
    b_april = pkg.statement_payload(pkg.debits(every(pkg.A(1), pkg.A(29)), 700), month=4, account=pkg.ACCOUNT_B,
                                    opening=pkg.closing(b_march))
    built = pkg.package(pkg.job("a-march", a_march), pkg.job("a-april", a_april), pkg.job("b-march", b_march),
                        pkg.job("b-april", b_april))
    assert _rows_of(built) == {"a-march": (1, 0), "a-april": (1, 0), "b-march": (1, 0), "b-april": (1, 0)}
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0)]


def test_a_stream_the_payment_changes_link_across_accounts_counts_once_in_a_month():
    # P6b: KAPITUS stops in account A after 04-08 and continues from account B from 04-15 (R3-83's "continues from
    # another account"): April's rows read 1 each, the month 1.
    pkg = _pkg()
    built = pkg.p6b()
    [stop] = built["lender_payment_changes"]
    assert stop["continues_in_other_account"]["first_date"] == "2054-04-15"
    assert _rows_of(built) == {"a-march": (1, 0), "a-april": (1, 0), "a-may": (0, 0), "b-april": (1, 0),
                               "b-may": (1, 0)}
    assert _months(built) == [("2054-03", 1, 0), ("2054-04", 1, 0), ("2054-05", 1, 0)]
    # Another funder in account B is no continuation: April holds two positions.
    built = pkg.p6b(pkg.ONDECK)
    assert _rows_of(built)["b-april"] == (1, 0)
    assert _months(built) == [("2054-03", 1, 0), ("2054-04", 2, 0), ("2054-05", 1, 0)]


def test_a_member_never_analysed_reads_n_a_never_zero():
    pkg = _pkg()
    march, april, _may = three_months()
    from webapp.jobs import Job

    failed = Job(id="june", filename="june.pdf", status="failed", analysis=None, content_sha256="june")
    built = pkg.package(pkg.job("march", march), pkg.job("april", april), failed)
    assert _rows_of(built) == {"march": (1, 0), "april": (2, 0), "june": (None, None)}
    assert _months(built) == [("2054-03", 1, 0), ("2054-04", 2, 0)]


def test_a_member_analysed_before_the_check_reads_n_a_and_so_does_its_month():
    pkg = _pkg()
    march, april, _may = three_months()
    older = copy.deepcopy(april)
    del pkg._account(older)["detection"]["lender_payment_changes"]
    built = pkg.package(pkg.job("march", march), pkg.job("april", older))
    assert _rows_of(built) == {"march": (1, 0), "april": (None, None)}
    assert _months(built) == [("2054-03", 1, 0), ("2054-04", None, None)]
    from webapp.app import _displayed

    metrics = _displayed(older, settings={})["metrics"]
    assert (metrics["active_positions"], metrics["possible_positions"]) == (None, None)


def test_nothing_stored_moves():
    pkg = _pkg()
    march, april, may = three_months()
    stored = copy.deepcopy([march, april, may])
    built = pkg.package(pkg.job("march", march), pkg.job("april", april), pkg.job("may", may))
    assert [march, april, may] == stored
    assert not any("active_positions" in (pkg._account(payload).get("metrics") or {}) for payload in stored)
    assert built["active_positions_by_month"]


# ------------------------------------------------------- review round 1 (2026-10-11; fabricated rows and statements)
def test_a_monthly_potential_lender_reads_the_same_alone_and_across_the_chain():
    # Review round 1: one basis for A10's floor. A payment of $100 or more counts, as a one-off and as a level alike,
    # so a potential lender paid once a month reads "+1 possible" in each statement alone and across the chain.
    months = [(_potential([J(15)], 300), JAN), (_potential([F(16)], 300), FEB), (_potential([M(16)], 300), MAR)]
    assert [alone(rows, period) for rows, period in months] == [(0, 1), (0, 1), (0, 1)]
    assert counts(chain(*months)) == [(0, 1), (0, 1), (0, 1)]
    weekly = [_rows(every(J(5), J(26)), 1000), _rows(every(F(2), F(23)), 1000), _rows(every(M(2), M(30)), 1000)]
    beside = [(rows + stream, period) for (rows, period), stream in zip(months, weekly)]
    assert [alone(rows, period) for rows, period in beside] == [(1, 1), (1, 1), (1, 1)]
    assert counts(chain(*beside)) == [(1, 1), (1, 1), (1, 1)]
    # Under the floor both ways: a $60 monthly payment is no possible position, alone or across the chain.
    small = [(_potential([J(15)], 60), JAN), (_potential([F(16)], 60), FEB), (_potential([M(16)], 60), MAR)]
    assert [alone(rows, period) for rows, period in small] == [(0, 0), (0, 0), (0, 0)]
    assert counts(chain(*small)) == [(0, 0), (0, 0), (0, 0)]


def test_the_fee_reference_is_the_regular_attempt_never_a_bounced_catch_up_or_payoff():
    # Review round 1: a cleared regular payment is a payment even where a far larger catch-up or payoff attempt bounced.
    weekly = (_rows(every(F(2), F(16)), 1000, returned_funder_payment_by="transaction:99")
              + _rows([F(20)], 25000, returned_funder_payment_by="transaction:98") + _rows([F(23)], 1000))
    assert alone(weekly, FEB) == (1, 0)
    daily = (_rows(bdays(F(2), F(20)), 300, returned_funder_payment_by="transaction:99")
             + _rows([F(23)], 7000, returned_funder_payment_by="transaction:98") + _rows([F(24)], 300))
    assert alone(daily, FEB) == (1, 0)
    # A token charge beside the bounced regular payments is still no payment.
    token = (_rows(every(F(2), F(23)), 1000, returned_funder_payment_by="transaction:99")
             + _rows([F(20)], 25000, returned_funder_payment_by="transaction:98") + _rows([F(24)], 35))
    assert alone(token, FEB) == (0, 0)


def test_a_new_stream_at_twice_another_s_amount_with_no_missed_or_bounced_payment_is_its_own_position():
    # Review round 1: A8's catch-up follows a missed or bounced payment. A new weekly stream at exactly twice a daily
    # stream's amount, beside a daily stream that paid every day, is a second position.
    rows = _rows(bdays(M(2), M(31)), 500) + _rows([M(23), M(30)], 1000)
    [series] = lpc.series_positions([lpc.StatementRows(_located(rows), *MAR, "USD")])
    assert [position.number for position in series.positions] == [1, 2]
    assert alone(rows, MAR) == (2, 0)
    # After two missed days of the daily stream, the two debits at twice its amount are it catching up.
    paid = [day for day in bdays(M(2), M(31)) if day not in (M(18), M(19))]
    rows = _rows(paid, 500) + _rows([M(20), M(23)], 1000)
    [series] = lpc.series_positions([lpc.StatementRows(_located(rows), *MAR, "USD")])
    assert [position.number for position in series.positions] == [1, 2]
    assert alone(rows, MAR) == (1, 0)


def _two_accounts(b_march_amount, b_april_days, b_april_amount, b_may_amount):
    """Account A pays KAPITUS 1,000 weekly from 03-04 to 04-08 and stops; account B pays KAPITUS `b_march_amount`
    weekly in March, `b_april_amount` on `b_april_days` and `b_may_amount` weekly in May."""
    pkg = _pkg()
    a_march = pkg.statement_payload(pkg.debits(every(M(4), M(25)), 1000), month=3)
    a_april = pkg.statement_payload(pkg.debits(every(pkg.A(1), pkg.A(8)), 1000), month=4, opening=pkg.closing(a_march))
    a_may = pkg.statement_payload([], month=5, opening=pkg.closing(a_april))
    b_march = pkg.statement_payload(pkg.debits(every(M(4), M(25)), b_march_amount), month=3, account=pkg.ACCOUNT_B)
    b_april = pkg.statement_payload(pkg.debits(b_april_days, b_april_amount), month=4, account=pkg.ACCOUNT_B,
                                    opening=pkg.closing(b_march))
    b_may = pkg.statement_payload(pkg.debits(every(pkg.Y(6), pkg.Y(27)), b_may_amount), month=5,
                                  account=pkg.ACCOUNT_B, opening=pkg.closing(b_april))
    return pkg.package(pkg.job("a-march", a_march), pkg.job("a-april", a_april), pkg.job("a-may", a_may),
                       pkg.job("b-march", b_march), pkg.job("b-april", b_april), pkg.job("b-may", b_may))


def test_a_link_across_accounts_counts_once_only_where_the_stream_is_handed_over():
    # Review round 1: account B's KAPITUS 700 position paid beside account A's 1,000 from March, so March and April
    # each held two positions that cleared, although the payment changes read A's stop as continuing in account B.
    pkg = _pkg()
    built = _two_accounts(700, every(pkg.A(1), pkg.A(29)), 700, 700)
    [stop] = [item for item in built["lender_payment_changes"] if item["kind"] == "stop"]
    assert stop["source_document"] == "a-april.pdf" and "continues_in_other_account" in stop
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 1, 0)]
    # B paid a 700 position of its own in March, then took A's 1,000 over from 04-15 (the module reads one position
    # in B, an increase): March holds two positions, April the handed-over one once.
    built = _two_accounts(700, every(pkg.A(15), pkg.A(29)), 1000, 1000)
    [stop] = [item for item in built["lender_payment_changes"] if item["kind"] == "stop"]
    assert stop["continues_in_other_account"]["first_date"] == "2054-04-15"
    assert _rows_of(built) == {"a-march": (1, 0), "a-april": (1, 0), "a-may": (0, 0), "b-march": (1, 0),
                               "b-april": (1, 0), "b-may": (1, 0)}
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 1, 0), ("2054-05", 1, 0)]


#: A potential lender of the registry (POTENTIAL_LENDER_ALIASES' generic "DAILY FUNDING", no legal entity named).
DAILY_FUNDING = "DAILY FUNDING DES:PAYMENT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000007 PPD"


def test_a_monthly_potential_lender_in_a_package_reads_as_each_statement_alone():
    # Review round 1: a registry potential lender paid $300 once a month beside a confirmed weekly stream reads
    # "+1 possible" in each statement alone, and so in the package's rows and months.
    pkg = _pkg()
    march = pkg.statement_payload(pkg.debits([M(16)], 300, DAILY_FUNDING) + pkg.debits(every(M(4), M(25)), 1000),
                                  month=3)
    april = pkg.statement_payload(pkg.debits([pkg.A(16)], 300, DAILY_FUNDING)
                                  + pkg.debits(every(pkg.A(1), pkg.A(29)), 1000), month=4, opening=pkg.closing(march))
    may = pkg.statement_payload(pkg.debits([pkg.Y(15)], 300, DAILY_FUNDING)
                                + pkg.debits(every(pkg.Y(6), pkg.Y(27)), 1000), month=5, opening=pkg.closing(april))
    from webapp.app import _displayed

    served = [_displayed(payload, settings={})["metrics"] for payload in (march, april, may)]
    assert [(metrics["active_positions"], metrics["possible_positions"]) for metrics in served] == [
        (1, 1), (1, 1), (1, 1)]
    built = pkg.package(pkg.job("march", march), pkg.job("april", april), pkg.job("may", may))
    assert _rows_of(built) == {"march": (1, 1), "april": (1, 1), "may": (1, 1)}
    assert _months(built) == [("2054-03", 1, 1), ("2054-04", 1, 1), ("2054-05", 1, 1)]


def test_a_package_member_whose_statement_holds_no_rows_list_reads_n_a_and_so_does_its_month():
    pkg = _pkg()
    march, april, _may = three_months()
    rowless = copy.deepcopy(april)
    del pkg._account(rowless)["statement"]["transactions"]
    built = pkg.package(pkg.job("march", march), pkg.job("april", rowless))
    assert _rows_of(built) == {"march": (1, 0), "april": (None, None)}
    assert _months(built) == [("2054-03", 1, 0), ("2054-04", None, None)]
    from webapp.app import _displayed

    metrics = _displayed(rowless, settings={})["metrics"]
    assert (metrics["active_positions"], metrics["possible_positions"]) == (None, None)


# ------------------------------------------------------- review round 2 (2026-10-11; fabricated rows and statements)
def _two_stop_in_a(b_april, b_may):
    """Account A pays KAPITUS on two concurrent positions, 1,000 on Wednesdays and 500 on Fridays, from 03-04 and 03-06
    to 04-08 and 04-10, and stops; account B pays KAPITUS nothing in March, then `b_april` and `b_may` (each a list of
    (days, amount))."""
    pkg = _pkg()
    a_march = pkg.statement_payload(pkg.debits(every(M(4), M(25)), 1000) + pkg.debits(every(M(6), M(27)), 500),
                                    month=3)
    a_april = pkg.statement_payload(pkg.debits(every(A(1), A(8)), 1000) + pkg.debits(every(A(3), A(10)), 500),
                                    month=4, opening=pkg.closing(a_march))
    a_may = pkg.statement_payload([], month=5, opening=pkg.closing(a_april))
    b_march = pkg.statement_payload([], month=3, account=pkg.ACCOUNT_B)
    b_april_payload = pkg.statement_payload([row for days, amount in b_april for row in pkg.debits(days, amount)],
                                            month=4, account=pkg.ACCOUNT_B, opening=pkg.closing(b_march))
    b_may_payload = pkg.statement_payload([row for days, amount in b_may for row in pkg.debits(days, amount)],
                                          month=5, account=pkg.ACCOUNT_B, opening=pkg.closing(b_april_payload))
    return pkg.package(pkg.job("a-march", a_march), pkg.job("a-april", a_april), pkg.job("a-may", a_may),
                       pkg.job("b-march", b_march), pkg.job("b-april", b_april_payload),
                       pkg.job("b-may", b_may_payload))


def _never_below_a_row(built):
    """Each month reads at least as many positions as any of its rows (one account's own count for that month)."""
    months = {entry["month"]: entry["active_positions"] for entry in built["active_positions_by_month"]}
    for doc in built["documents"]:
        if doc.get("active_positions") is not None:
            assert months[doc["period_start"][:7]] >= doc["active_positions"], doc["id"]


def test_two_positions_that_stop_together_in_one_account_count_twice_where_one_continuation_takes_over():
    # Review round 2: both of account A's stops continue in account B (the payment changes read the funder's first
    # debit there for each), but B's one position continues one of them at most. Consolidated: one 1,600 weekly in B
    # from 04-15. April held A's two positions, both cleared: 2.
    pkg = _pkg()
    built = _two_stop_in_a([(every(A(15), A(29)), 1600)], [(every(pkg.Y(6), pkg.Y(27)), 1600)])
    stops = [item for item in built["lender_payment_changes"] if item["kind"] == "stop"]
    assert [item["continues_in_other_account"]["first_date"] for item in stops] == ["2054-04-15", "2054-04-15"]
    assert _rows_of(built)["a-april"] == (2, 0) and _rows_of(built)["b-april"] == (1, 0)
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 1, 0)]
    _never_below_a_row(built)
    # The 500 paid off, the 1,000 moved to account B from 04-15: April 2 (the 1,000 handed over once, the 500 apart).
    built = _two_stop_in_a([(every(A(15), A(29)), 1000)], [(every(pkg.Y(6), pkg.Y(27)), 1000)])
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 1, 0)]
    _never_below_a_row(built)
    # Both moved (a bank switch: 1,000 on Wednesdays from 04-15, 500 on Fridays from 04-17): each counted once, 2.
    built = _two_stop_in_a([(every(A(15), A(29)), 1000), (every(A(17), A(24)), 500)],
                           [(every(pkg.Y(6), pkg.Y(27)), 1000), (every(pkg.Y(1), pkg.Y(29)), 500)])
    assert _rows_of(built)["b-april"] == (2, 0)
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 2, 0)]
    _never_below_a_row(built)


def test_one_continuation_takes_over_one_stop_at_most():
    # Review round 2, the pure reading: both stops of chain 0 linked to chain 1's one position (the link's first
    # payment 1,600 there) never fold chain 0's two positions into one; the stop nearest the continuation's amount is
    # the one handed over.
    first = chain((_rows(every(M(4), M(25)), 1000) + _rows(every(M(6), M(27)), 500), MAR),
                  (_rows(every(A(1), A(8)), 1000) + _rows(every(A(3), A(10)), 500), APR))
    [series] = lpc.series_positions(first)
    assert [(position.number, position.levels[0][0]) for position in series.positions] == [(1, 100000), (2, 50000)]
    second = chain((_rows(every(A(15), A(29)), 1600), APR))
    links = [ap.PositionLink(0, ("confirmed", "KAPITUS"), number, 1, A(15), 1600.0) for number in (1, 2)]
    march, april = 2054 * 12 + 2, 2054 * 12 + 3
    _per, by_month = ap.package_active_positions([first, second], months=[[march, april], [april]], links=links)
    assert [(entry["month"], entry["active_positions"]) for entry in by_month] == [("2054-03", 2), ("2054-04", 2)]
    # One stop linked: handed over once, the other apart.
    _per, by_month = ap.package_active_positions([first, second], months=[[march, april], [april]], links=links[:1])
    assert [(entry["month"], entry["active_positions"]) for entry in by_month] == [("2054-03", 2), ("2054-04", 2)]


def test_a_bounce_the_stream_paid_past_is_no_catch_up_premise():
    # Review round 2: A8's premise reads a bounce the fuller stream has not paid past (dated after its last payment
    # before the 2x level), as the catch-up line counts missed payments from the last paid presence. A daily stream
    # that bounced once on 03-05 and paid every business day since, beside a new weekly stream at twice its amount, is
    # two positions.
    daily = [day for day in bdays(M(2), M(31)) if day != M(5)]
    bounce = _rows([M(5)], 500, returned_funder_payment_by="transaction:99")
    rows = _rows(daily, 500) + bounce + _rows([M(23), M(30)], 1000)
    assert alone(rows, MAR) == (2, 0)
    # A bounce after the stream's last payment before the 2x level: the 2x level is the stream catching up.
    paid = [day for day in bdays(M(2), M(31)) if day != M(20)]
    rows = (_rows(paid, 500) + _rows([M(20)], 500, returned_funder_payment_by="transaction:99")
            + _rows([M(23), M(30)], 1000))
    assert alone(rows, MAR) == (1, 0)
    # The 2x amount presented and bounced before it cleared, after the stream's own bounce: the funder collecting the
    # bounced payment as a multiple (the precision sample's catch-up shape, test_a_catch_up_level_beside_its_stream_is_
    # no_second_position), one position.
    rows = (_rows(daily, 500) + bounce + _rows([M(16)], 1000, returned_funder_payment_by="transaction:98")
            + _rows([M(23), M(30)], 1000))
    assert alone(rows, MAR) == (1, 0)


def test_two_same_day_debits_are_one_split_payment_only_when_they_add_up_to_the_payment_just_before_them():
    # Review round 2: the parts add up to the series' last payment or attempt just before they began (the payment that
    # was split), never to an older level or attempt. After a decrease from 1,500 to 1,000 in February, a new 500 on
    # the 1,000's days in March is a second position, as the payment changes read it (a new concurrent stream).
    february = _rows(every(F(2), F(9)), 1500) + _rows(every(F(16), F(23)), 1000)
    march = _rows(every(M(2), M(30)), 1000) + _rows(every(M(2), M(30)), 500)
    statements = chain((february, FEB), (march, MAR))
    assert [(item["kind"], item.get("position")) for item in lpc.payment_changes(statements)] == [
        ("decrease", 1), ("new_stream", 2)]
    assert counts(statements) == [(1, 0), (2, 0)]
    # A bounced 1,500 attempt a month earlier, before a 700 weekly, is no payment the March debits split either.
    february = _rows([F(2)], 1500, returned_funder_payment_by="transaction:99") + _rows(every(F(9), F(23)), 700)
    assert counts(chain((february, FEB), (march, MAR))) == [(1, 0), (2, 0)]
    # The 1,500 paid weekly through February, then the two parts on its days: one payment split, one position.
    february = _rows(every(F(2), F(23)), 1500)
    assert counts(chain((february, FEB), (march, MAR))) == [(1, 0), (1, 0)]


# ------------------------------------------------------- review round 3 (2026-10-11; fabricated rows and statements)
def test_a_bank_switch_that_re_prices_both_positions_hands_each_over_once():
    # Review round 3: both of account A's positions move to account B (a bank switch) and are re-priced on the move.
    # The payment changes read both stops as continuing from the funder's first debit in B (04-15); each stop is handed
    # over to one continuation that began there on or after that day, whatever its amount, as A7 reads a level that
    # follows another in one account (a level joins the position it is not concurrent with). April held two positions.
    pkg = _pkg()
    # Both re-priced by 3% (1,000 -> 1,030 on Wednesdays from 04-15, 500 -> 515 on Fridays from 04-17).
    built = _two_stop_in_a([(every(A(15), A(29)), 1030), (every(A(17), A(24)), 515)],
                           [(every(pkg.Y(6), pkg.Y(27)), 1030), (every(pkg.Y(1), pkg.Y(29)), 515)])
    stops = [item for item in built["lender_payment_changes"] if item["kind"] == "stop"]
    assert [item["continues_in_other_account"]["first_date"] for item in stops] == ["2054-04-15", "2054-04-15"]
    assert _rows_of(built)["a-april"] == (2, 0) and _rows_of(built)["b-april"] == (2, 0)
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 2, 0)]
    _never_below_a_row(built)
    # Only the Friday one re-priced (500 -> 520): 2.
    built = _two_stop_in_a([(every(A(15), A(29)), 1000), (every(A(17), A(24)), 520)],
                           [(every(pkg.Y(6), pkg.Y(27)), 1000), (every(pkg.Y(1), pkg.Y(29)), 520)])
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 2, 0)]
    # Re-priced far more (500 -> 800): still the stopped position's continuation, 2.
    built = _two_stop_in_a([(every(A(15), A(29)), 1000), (every(A(17), A(24)), 800)],
                           [(every(pkg.Y(6), pkg.Y(27)), 1000), (every(pkg.Y(1), pkg.Y(29)), 800)])
    assert _months(built) == [("2054-03", 2, 0), ("2054-04", 2, 0), ("2054-05", 2, 0)]
    _never_below_a_row(built)


def test_a_second_stop_is_handed_over_to_a_continuation_that_began_after_the_link_whatever_its_amount():
    # Review round 3, the pure reading: both stops of chain 0 linked to chain 1 at its first debit (1,030 on 04-15);
    # chain 1 also began a 515 position on 04-17. One to one, the nearest amounts first: 1,000 -> 1,030 and 500 -> 515.
    first = chain((_rows(every(M(4), M(25)), 1000) + _rows(every(M(6), M(27)), 500), MAR),
                  (_rows(every(A(1), A(8)), 1000) + _rows(every(A(3), A(10)), 500), APR))
    second = chain((_rows(every(A(15), A(29)), 1030) + _rows(every(A(17), A(24)), 515), APR))
    links = [ap.PositionLink(0, ("confirmed", "KAPITUS"), number, 1, A(15), 1030.0) for number in (1, 2)]
    march, april = 2054 * 12 + 2, 2054 * 12 + 3
    _per, by_month = ap.package_active_positions([first, second], months=[[march, april], [april]], links=links)
    assert [(entry["month"], entry["active_positions"]) for entry in by_month] == [("2054-03", 2), ("2054-04", 2)]
    # A position of chain 1 that paid before the link's day paid beside the stopped ones: never a continuation.
    second = chain((_rows(every(A(1), A(29)), 515) + _rows(every(A(15), A(29)), 1030), APR))
    _per, by_month = ap.package_active_positions([first, second], months=[[march, april], [april]], links=links)
    assert [(entry["month"], entry["active_positions"]) for entry in by_month] == [("2054-03", 2), ("2054-04", 3)]


def test_a_split_payment_beside_a_stream_that_carries_on_unchanged_is_one_position():
    # Review round 3: the precision sample's split shape (a weekly 1,250 bounced, cleared once, then came as 1,000 and
    # 250 on the same days) beside a daily 200 stream of the same funder that paid every business day at the level it
    # paid before the parts began. The daily stream carries on unchanged, so it was not split: the 1,250 just before the
    # parts is the payment that was. Two positions: the daily stream and the split one.
    split = _rows([M(17), M(24), M(31)], 1000) + _rows([M(17), M(24), M(31)], 250)
    whole = _rows([M(3), M(5)], 1250, returned_funder_payment_by="transaction:99") + _rows([M(10)], 1250)
    daily = _rows(bdays(M(2), M(31)), 200)
    [series] = lpc.series_positions([lpc.StatementRows(_located(split + whole + daily), *MAR, "USD")])
    assert [[level[0] for level in position.levels] for position in series.positions] == [[20000], [25000], [100000]]
    assert alone(split + whole + daily, MAR) == (2, 0)
    # Across a chain: February paid 1,250 weekly beside the daily 200, March the two parts beside it: 2 each month.
    february = _rows(every(F(3), F(24)), 1250) + _rows(bdays(F(2), F(27)), 200)
    march = _rows(every(M(3), M(31)), 1000) + _rows(every(M(3), M(31)), 250) + _rows(bdays(M(2), M(31)), 200)
    assert counts(chain((february, FEB), (march, MAR))) == [(2, 0), (2, 0)]
    # A stream whose level changes where the parts begin is the one split: February 1,250, March 1,000 + 250.
    assert counts(chain((_rows(every(F(3), F(24)), 1250), FEB),
                        (_rows(every(M(3), M(31)), 1000) + _rows(every(M(3), M(31)), 250), MAR))) == [(1, 0), (1, 0)]

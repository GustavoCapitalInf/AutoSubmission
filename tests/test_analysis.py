"""Unit tests for the deterministic analysis stages (no network / no LLM).
These lock in the math and detection logic — the parts that must be exactly right."""
from __future__ import annotations
from datetime import date
from analysis.schema import Statement, Transaction
from analysis.reconcile import reconcile
from analysis.metrics import compute_metrics, daily_closing_balances
from analysis.detect import detect, find_known_funders, find_recurring_debits


def _txn(date, amount, desc="x", bal=None):
    return Transaction(
        date=date, description=desc, amount=amount,
        direction="credit" if amount >= 0 else "debit", running_balance=bal,
    )


# ---- reconciliation ----------------------------------------------------------

def test_reconcile_ok():
    s = Statement(beginning_balance=1000.0, ending_balance=1300.0, transactions=[
        _txn("2026-01-01", 500.0, bal=1500.0),
        _txn("2026-01-02", -200.0, bal=1300.0),
    ])
    r = reconcile(s)
    assert r.ok
    assert r.sum_delta == 0.0
    assert r.continuity_breaks == 0


def test_reconcile_sum_mismatch():
    s = Statement(beginning_balance=1000.0, ending_balance=9999.0, transactions=[
        _txn("2026-01-01", 500.0),
    ])
    r = reconcile(s)
    assert not r.ok
    assert any("sum check" in i for i in r.issues)


def test_reconcile_continuity_break():
    s = Statement(beginning_balance=1000.0, ending_balance=1300.0, transactions=[
        _txn("2026-01-01", 500.0, bal=1500.0),
        _txn("2026-01-02", -200.0, bal=9999.0),  # wrong running balance
    ])
    r = reconcile(s)
    assert not r.ok
    assert r.continuity_breaks == 1


def test_reconcile_flags_scrambled_summary():
    # credits/debits swapped and a count (26) read as the debit total -> the
    # bank-stated summary itself no longer reconciles.
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=3945.12, stated_total_debits=26.0,  # scrambled
        transactions=[],
    )
    r = reconcile(s)
    assert not r.ok
    assert any("summary does not reconcile" in i for i in r.issues)


def test_reconcile_good_summary_passes_with_service_charge_residual():
    # Real F&M values: residual is the $8 service charge listed outside the total.
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=7329.22, stated_total_debits=3945.12,
        transactions=[],
    )
    r = reconcile(s)
    assert not any("summary does not reconcile" in i for i in r.issues)


def test_reconcile_debit_coverage_flags_incomplete_ocr():
    # Bank says $4000 of debits; we only captured $756 of line items.
    s = Statement(
        beginning_balance=0.0, ending_balance=0.0,
        stated_total_credits=7329.22, stated_total_debits=3945.12,
        stated_credit_count=3, stated_debit_count=26,
        transactions=[_txn("2026-01-01", 7329.22), _txn("2026-01-02", -756.30)],
    )
    r = reconcile(s)
    assert r.credit_coverage == 1.0
    assert r.debit_coverage is not None and r.debit_coverage < 0.5
    assert any("stated" in i and "debits" in i for i in r.issues)


# ---- metrics -----------------------------------------------------------------

def test_daily_average_balance_carries_forward():
    # 3-day period; no activity on day 3 carries day 2's balance forward.
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-03",
        beginning_balance=1000.0, ending_balance=1300.0, transactions=[
            _txn("2026-01-01", 500.0, bal=1500.0),
            _txn("2026-01-02", -200.0, bal=1300.0),
        ],
    )
    balances = daily_closing_balances(s)
    assert balances[date(2026, 1, 3)] == 1300.0  # carried from day 2
    m = compute_metrics(s)
    assert m.days_in_period == 3
    assert m.average_daily_balance == round((1500 + 1300 + 1300) / 3, 2)  # 1366.67


def test_metrics_uses_bank_stated_average_when_no_running_balances():
    s = Statement(stated_average_balance=1569.0, transactions=[_txn("2026-01-01", 100.0)])
    m = compute_metrics(s)
    assert m.stated_average_balance == 1569.0
    assert m.average_daily_balance is None  # nothing to compute


def test_metrics_counts_and_nsf():
    s = Statement(transactions=[
        _txn("2026-01-01", 500.0, "DEPOSIT"),
        _txn("2026-01-02", -30.0, "NSF FEE"),
        _txn("2026-01-03", -20.0, "Returned item fee"),
    ])
    m = compute_metrics(s)
    assert m.num_deposits == 1 and m.num_withdrawals == 2
    assert m.total_deposits == 500.0 and m.total_withdrawals == 50.0
    assert m.nsf_count == 2


# ---- detection ---------------------------------------------------------------

def test_detect_known_funder():
    s = Statement(transactions=[
        _txn("2026-01-02", -450.0, "Orig CO Name:Kapitus Descr:Payment ACH Debit"),
        _txn("2026-01-03", -450.0, "Orig CO Name:Kapitus Descr:Payment ACH Debit"),
    ])
    matches = find_known_funders(s)
    assert len(matches) == 1
    assert matches[0].funder == "Kapitus"
    assert matches[0].total_debited == 900.0


def test_detect_recurring_daily_pattern():
    # 5 fixed $450 debits on business days -> daily cadence.
    s = Statement(transactions=[
        _txn("2026-01-02", -450.0, "ACH Debit Funder 0102"),
        _txn("2026-01-05", -450.0, "ACH Debit Funder 0105"),
        _txn("2026-01-06", -450.0, "ACH Debit Funder 0106"),
        _txn("2026-01-07", -450.0, "ACH Debit Funder 0107"),
        _txn("2026-01-08", -450.0, "ACH Debit Funder 0108"),
    ])
    rec = find_recurring_debits(s)
    assert len(rec) == 1
    assert rec[0].count == 5
    assert rec[0].amount == 450.0
    assert rec[0].cadence == "daily"


def test_detect_ignores_one_off_debits():
    s = Statement(transactions=[
        _txn("2026-01-02", -12.34, "Coffee"),
        _txn("2026-01-03", -56.78, "Gas"),
    ])
    d = detect(s)
    assert d.recurring_debits == []
    assert d.known_funders == []

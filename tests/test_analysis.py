"""Unit tests for the deterministic analysis stages (no network / no LLM).
These lock in the math and detection logic — the parts that must be exactly right."""
from __future__ import annotations
from datetime import date
from analysis.schema import Statement, Transaction
from analysis.reconcile import reconcile
from analysis.metrics import compute_metrics, daily_closing_balances
from analysis.detect import detect, find_known_funders, find_recurring_debits
from analysis.extract import strip_embedded_images
from analysis.pipeline import analyze_markdown, normalize_statement
from analysis.td_can import parse_td_canada_statement
from analysis.bofa import repair_bofa_summary
from analysis.first_community import repair_first_community_posted_activity
from analysis.regions import repair_regions_summary


def test_strip_embedded_images_removes_base64_bloat():
    md = ('Deposits\n<img class="doc-image" src="data:image/png;base64,QUJDRA==" alt="image" />\n'
          '<table><tr><td>04/01</td><td>ACH</td><td>100.00</td></tr></table>')
    out = strip_embedded_images(md)
    assert "base64" not in out and "<img" not in out
    assert "Deposits" in out and "100.00" in out  # text ledger preserved


def test_normalize_statement_drops_daily_balance_summary_rows():
    stmt = Statement(transactions=[
        _txn("2026-04-30", -10.0, "MAINTENANCE FEE"),
        _txn("2026-04-30", 0.0, "DAILY BALANCE", bal=35121.16),
        _txn("2026-04-29", 0.0, "DAILY BALANCE SUMMARY", bal=36361.22),
    ])
    cleaned = normalize_statement(stmt)
    assert [t.description for t in cleaned.transactions] == ["MAINTENANCE FEE"]


def test_parse_td_canada_table_handles_fused_and_shifted_rows():
    md = """
Accounts issued by: THE TORONTO-DOMINION BANK
<table>
<tr><td>Branch No.</td><td>Account No.</td><td>BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY A</td><td>SEP 29/25 - OCT 31/25</td></tr>
<tr><td>2023</td><td>2023-5224784</td><td>EVERY DAY A</td><td>Page 1 of 2</td></tr>
<tr><td>DESCRIPTION</td><td>CHEQUE/DEBIT</td><td>DEPOSIT/CREDIT</td><td>DATE</td><td>BALANCE</td></tr>
<tr><td>BALANCE FORWARD PRODIGY SYSTEMS PAY</td><td></td><td>100.00</td><td>SEP29 OCT10</td><td>19.070D</td></tr>
<tr><td>SEND E-TFR FEE</td><td>1.50</td><td></td><td>200.00</td><td>OCT15</td></tr>
<tr><td>PRODIGY SYSTEMS PAY</td><td></td><td></td><td>OCT24</td><td></td></tr>
<tr><td>0 CHQS ENCLOSED NEXT STATEMENT DATE IS</td><td>NOV 28/25</td><td></td><td>No.</td><td>Amount</td></tr>
<tr><td>MONTHLY AVER. CR. BAL.</td><td>$294.88</td><td>Credits</td><td>2 300.00</td></tr>
<tr><td>DEP CONTENT- CASH 0</td><td>ITEMS 0</td><td>UNC BATCH 0</td><td>Debits</td><td>1 1.50</td></tr>
</table>
<table>
<tr><td>Branch No.</td><td>Account No.</td><td>BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY A</td><td>SEP 29/25 - OCT 31/25</td></tr>
<tr><td>2023</td><td>2023-5224784</td><td>EVERY DAY A</td><td>Page 2 of 2</td></tr>
<tr><td>DESCRIPTION</td><td>CHEQUE/DEBIT</td><td>DEPOSIT/CREDIT</td><td>DATE</td><td>BALANCE</td></tr>
<tr><td>BALANCE FORWARD</td><td></td><td></td><td>OCT24</td><td>279.43</td></tr>
<tr><td>MONTHLY PLAN FEE</td><td>30.00</td><td></td><td>OCT31</td><td>249.43</td></tr>
<tr><td>0 CHQS ENCLOSED NEXT STATEMENT DATE IS NOV 28/25</td><td></td><td></td><td>No.</td><td>Amount</td></tr>
<tr><td>MONTHLY AVER. CR. BAL.</td><td>$294.88</td><td></td><td>Credits</td><td>0 0.00</td></tr>
<tr><td>DEP CONTENT- CASH 0 ITEMS 0 UNC BATCH 0</td><td></td><td></td><td>Debits</td><td>1 30.00</td></tr>
</table>
"""
    stmt = parse_td_canada_statement(md)
    assert stmt is not None
    assert stmt.account_number == "2023-5224784"
    assert stmt.period_start == "2025-09-29"
    assert stmt.period_end == "2025-10-31"
    assert stmt.beginning_balance == -19.07
    assert stmt.ending_balance == 249.43
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 31.5
    assert [(t.description, t.amount) for t in stmt.transactions] == [
        ("PRODIGY SYSTEMS PAY", 100.0),
        ("SEND E-TFR FEE", -1.5),
        ("PRODIGY SYSTEMS PAY", 200.0),
        ("MONTHLY PLAN FEE", -30.0),
    ]
    assert all(t.running_balance is None for t in stmt.transactions)
    assert reconcile(stmt).ok


def test_analyze_td_canada_native_text_bypasses_gemini(monkeypatch):
    def fail_extract(*args, **kwargs):
        raise AssertionError("Gemini extraction should not run for deterministic TD Canada")

    monkeypatch.setattr("analysis.pipeline.extract_statement", fail_extract)
    md = """
--- Page 1 ---
Accounts issued by: THE TORONTO-DOMINION BANK
Statement of Account Account Type Statement From - To
Branch No. Account No. MAR 31/26 - APR 30/26
BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY B
4444 0052-5220318 Page 1 of 1
DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE
BALANCE FORWARD MAR31 29.42
Lightspeed MSP 100.00 APR01
CMCA Finance BUS 50.00 APR01
SERVICE CHARGE 23.39 APR30 56.03
MONTHLY AVER. CR. BAL. $483.78
Credits 1 100.00
Debits 2 73.39
0 CHQS ENCLOSED NEXT STATEMENT DATE IS MAY 29/26
"""
    report = analyze_markdown(md)
    assert report.model_used == "td-canada-trust-deterministic"
    assert report.reconciliation.ok
    assert report.metrics.effective_total_deposits == 100.0
    assert report.metrics.effective_total_withdrawals == 73.39


def test_repair_bofa_summary_folds_checks_and_service_fees():
    md = """
Bank of America
Account summary
Beginning balance on February 1, 2026 $6,767.39
# of deposits/credits: 52
Deposits and other credits 35,968.84
# of withdrawals/debits: 154
Withdrawals and other debits -35,626.82
Checks -5,490.40
Service fees -120.43
Ending balance on February 28, 2026 $1,498.58
Total # of checks 10
"""
    stmt = repair_bofa_summary(md, Statement(bank="Bank of America"))
    assert stmt.stated_total_debits == 41237.65
    assert stmt.stated_debit_count == 164
    assert reconcile(stmt).summary_ok is True


def test_repair_regions_summary_handles_returned_checks_and_trailing_minus():
    md = """
Regions Bank
SUMMARY
Beginning Balance $7,317.34 Deposits & Credits $53,689.64 + Withdrawals $65,850.69 - Fees $108.00 - Automatic Transfers $0.00 + Returned Checks $17,142.47 + Checks $12,786.27 - Ending Balance $595.51 -
Total Deposits & Credits $53,689.64
Total Withdrawals $65,850.69
Total Fees $108.00
Total Returned Checks $17,142.47
Total Checks $12,786.27
"""
    stmt = repair_regions_summary(md, Statement(bank="Regions Bank"))
    assert stmt.ending_balance == -595.51
    assert stmt.stated_total_credits == 70832.11
    assert stmt.stated_total_debits == 78744.96
    assert reconcile(stmt).summary_ok is True


def test_repair_first_community_removes_balance_neutral_failed_efts():
    stmt = Statement(
        bank="First Community",
        beginning_balance=100.0,
        ending_balance=150.0,
        stated_total_credits=100.0,
        stated_total_debits=250.0,
        transactions=[
            _txn("2025-10-01", 100.0, "DIRECT DEPOSIT", bal=200.0),
            _txn("2025-10-02", -200.0, "EFT - FAILED ATTEMPT", bal=200.0),
            _txn("2025-10-03", -50.0, "POS - PURCHASE", bal=150.0),
        ],
    )
    repaired = repair_first_community_posted_activity(stmt)
    assert [t.description for t in repaired.transactions] == ["DIRECT DEPOSIT", "POS - PURCHASE"]
    assert repaired.stated_total_debits == 50.0
    assert reconcile(repaired).ok


def test_analysis_marks_incomplete_bmo_detail_as_summary_trusted(monkeypatch):
    def fake_extract(*args, **kwargs):
        return Statement(
            bank="BMO",
            account_name="Example",
            beginning_balance=100.0,
            ending_balance=250.0,
            stated_total_credits=200.0,
            stated_total_debits=50.0,
            transactions=[_txn("2026-01-01", 100.0)],
        )

    monkeypatch.setattr("analysis.pipeline.extract_statement", fake_extract)
    report = analyze_markdown("BMO Account Summary")
    assert not report.reconciliation.ok
    assert report.reconciliation.summary_ok is True
    assert report.quality.level == "summary_trusted"
    assert report.quality.corporate_use == "summary_only"
    assert report.quality.transaction_detail_reliable is False
    assert not any("UNCAPTURED" in t.description for t in report.statement.transactions)


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


def test_reconcile_sparse_running_balances_accumulates_intervening_rows():
    s = Statement(beginning_balance=100.0, ending_balance=85.0, transactions=[
        _txn("2026-01-01", -10.0),
        _txn("2026-01-01", -5.0, bal=85.0),
    ])
    r = reconcile(s)
    assert r.ok
    assert r.continuity_breaks == 0


def test_reconcile_implies_missing_beginning_from_stated_summary():
    s = Statement(
        ending_balance=167.73,
        stated_total_credits=12023.20,
        stated_total_debits=11836.40,
        transactions=[
            _txn("2025-10-10", 12023.20),
            _txn("2025-10-31", -11836.40, bal=167.73),
        ],
    )
    r = reconcile(s)
    assert r.summary_ok is True
    assert r.computed_ending == 167.73
    assert r.sum_delta == 0.0


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
    assert r.summary_ok is False
    assert any("summary does not reconcile" in i for i in r.issues)


def test_reconcile_good_summary_with_separate_service_charge():
    # Real F&M values: -78.68 + 7329.22 - 3945.12 - 8.00 SC + 0 interest == 3297.42
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=7329.22, stated_total_debits=3945.12,
        stated_service_charge=8.00, stated_interest_paid=0.0,
        transactions=[],
    )
    r = reconcile(s)
    assert r.summary_ok is True
    assert not any("summary does not reconcile" in i for i in r.issues)


def test_reconcile_good_summary_service_charge_folded_into_debits():
    # Bank folds the $8 charge into the debit total; no separate SC field.
    s = Statement(
        beginning_balance=-78.68, ending_balance=3297.42,
        stated_total_credits=7329.22, stated_total_debits=3953.12,  # 3945.12 + 8
        transactions=[],
    )
    r = reconcile(s)
    assert r.summary_ok is True


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


def test_daily_average_balance_tolerates_rows_without_running_balance():
    # Real statements sometimes omit the balance on fee/detail rows. Those rows
    # should not prevent ADB as long as dated EOD balances still exist.
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-04",
        beginning_balance=1000.0, ending_balance=1150.0, transactions=[
            _txn("2026-01-01", 200.0, bal=1200.0),
            _txn("2026-01-02", -25.0, "SERVICE FEE", bal=None),
            _txn("2026-01-03", -50.0, bal=1150.0),
        ],
    )
    balances = daily_closing_balances(s)
    assert balances[date(2026, 1, 2)] == 1200.0
    assert balances[date(2026, 1, 4)] == 1150.0
    m = compute_metrics(s)
    assert m.average_daily_balance == round((1200 + 1200 + 1150 + 1150) / 4, 2)


def test_metrics_uses_bank_stated_average_when_no_running_balances():
    s = Statement(stated_average_balance=1569.0, transactions=[_txn("2026-01-01", 100.0)])
    m = compute_metrics(s)
    assert m.stated_average_balance == 1569.0
    assert m.average_balance == 1569.0
    assert m.average_balance_source == "bank_stated"
    assert m.average_daily_balance is None  # nothing to compute


def test_metrics_effective_totals_use_reconciled_bank_summary():
    s = Statement(
        stated_total_credits=5000.0,
        stated_total_debits=3200.0,
        stated_credit_count=8,
        stated_debit_count=20,
        transactions=[_txn("2026-01-01", 1000.0), _txn("2026-01-02", -250.0)],
    )
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.total_deposits == 1000.0
    assert m.total_withdrawals == 250.0
    assert m.effective_total_deposits == 5000.0
    assert m.effective_total_withdrawals == 3200.0
    assert m.effective_num_deposits == 8
    assert m.effective_num_withdrawals == 20
    assert m.deposits_source == "bank_stated_reconciled"
    assert m.withdrawals_source == "bank_stated_reconciled"


def test_metrics_effective_withdrawals_include_separate_service_charge():
    s = Statement(
        beginning_balance=11982.22,
        ending_balance=35121.16,
        stated_total_credits=141759.20,
        stated_total_debits=118610.26,
        stated_service_charge=10.00,
        transactions=[],
    )
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.effective_total_withdrawals == 118620.26


def test_metrics_does_not_compute_adb_when_running_balances_untrusted():
    s = Statement(
        period_start="2026-01-01", period_end="2026-01-02",
        stated_average_balance=100.0,
        transactions=[_txn("2026-01-01", 50.0, bal=150.0)],
    )
    m = compute_metrics(s, trust_running_balances=False)
    assert m.average_balance == 100.0
    assert m.average_balance_source == "bank_stated"
    assert m.average_daily_balance is None
    assert m.min_balance is None
    assert any("line-item balances did not reconcile" in n for n in m.notes)


def test_metrics_ignores_bank_totals_when_summary_fails():
    s = Statement(
        stated_total_credits=5000.0,
        stated_total_debits=3200.0,
        transactions=[_txn("2026-01-01", 1000.0), _txn("2026-01-02", -250.0)],
    )
    m = compute_metrics(s, trust_stated_summary=False)
    assert m.effective_total_deposits == 1000.0
    assert m.effective_total_withdrawals == 250.0
    assert m.deposits_source == "line_items"
    assert m.withdrawals_source == "line_items"
    assert any("ignored bank-stated" in n for n in m.notes)


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


def test_metrics_effective_nsf_prefers_bank_stated_count():
    s = Statement(stated_nsf_count=4, transactions=[
        _txn("2026-01-02", -30.0, "NSF FEE"),
    ])
    m = compute_metrics(s)
    assert m.nsf_count == 1
    assert m.effective_nsf_count == 4
    assert m.nsf_source == "bank_stated"


def test_metrics_computes_true_revenue_cash_flow_lender_pos_and_loan_counts():
    s = Statement(stated_total_credits=12000.0, stated_total_debits=5000.0, transactions=[
        _txn("2026-01-02", 10000.0, "CUSTOMER DEPOSIT"),
        _txn("2026-01-03", 2000.0, "ACH CREDIT RAPID FINANCE FUNDING"),
        _txn("2026-01-04", -500.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2026-01-05", -25.0, "DEBIT CARD PURCHASE GAS"),
        _txn("2026-01-06", -750.0, "SBA LOAN PAYMENT"),
    ])
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.lender_credits == 2000.0
    assert m.lender_debits == 500.0
    assert m.monthly_lender_debits == 500.0
    assert m.true_revenue == 10000.0
    assert m.cash_flow == 7000.0
    assert m.withholding_rate == 5.0
    assert m.pos_count == 1
    assert m.loan_count == 1


def test_metrics_normalizes_weekly_lender_debits_for_withholding_rate():
    s = Statement(stated_total_credits=4330.0, stated_total_debits=400.0, transactions=[
        _txn("2026-01-01", 4330.0, "CUSTOMER DEPOSIT"),
        _txn("2026-01-02", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2026-01-09", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2026-01-16", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
        _txn("2026-01-23", -100.0, "ACH DEBIT RAPID FINANCE PAYMENT"),
    ])
    m = compute_metrics(s, trust_stated_summary=True)
    assert m.lender_debits == 400.0
    assert m.monthly_lender_debits == 433.0
    assert m.withholding_rate == 10.0


# ---- detection ---------------------------------------------------------------

def test_detect_known_funder():
    s = Statement(transactions=[
        _txn("2026-01-02", -450.0, "Orig CO Name:Kapitus Descr:Payment ACH Debit"),
        _txn("2026-01-03", -450.0, "Orig CO Name:Kapitus Descr:Payment ACH Debit"),
    ])
    matches = find_known_funders(s)
    assert len(matches) == 1
    assert matches[0].funder == "KAPITUS"
    assert matches[0].total_debited == 900.0


def test_detect_expanded_lender_keyword_aliases():
    s = Statement(transactions=[
        _txn("2026-01-02", -300.0, "ACH DEBIT THE FUNDWORKS LLC PMT"),
        _txn("2026-01-03", -225.0, "DIRECT DEB DELAGELANDEN LEASE"),
    ])
    matches = find_known_funders(s)
    assert [m.funder for m in matches] == ["FUNDWORKS", "DE LAGE LANDEN"]


def test_recurring_debits_filters_generic_processors():
    s = Statement(transactions=[
        _txn("2026-01-02", -45.0, "DEBIT CARD PURCHASE COFFEE 0102"),
        _txn("2026-01-03", -45.0, "DEBIT CARD PURCHASE COFFEE 0103"),
        _txn("2026-01-04", -45.0, "DEBIT CARD PURCHASE COFFEE 0104"),
    ])
    assert find_recurring_debits(s) == []


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

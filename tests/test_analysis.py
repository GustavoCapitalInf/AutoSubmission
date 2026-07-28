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
from analysis.capital_one import parse_capital_one_statement
from analysis.chase import parse_chase_statement
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


def test_parse_capital_one_uses_running_balances_to_fix_miscolumned_credits():
    md = """
CapitalOne Bank
ACCOUNT SUMMARY FOR PERIOD MARCH 01, 2026 - MARCH 31, 2026
Business Basic Checking 00005733890536
<table><tr><td>Previous Balance 02/28/26</td><td>$619.39</td></tr><tr><td>19 Deposits/Credits</td><td>$9,230.78</td></tr><tr><td>30 Checks/Debits</td><td>($8,968.79)</td></tr><tr><td>Service Charges</td><td>($15.00)</td></tr><tr><td>Ending Balance 03/31/26</td><td>$866.38</td></tr></table>
<table><tr><td>Number of Days in Cycle</td><td>31</td></tr><tr><td>Minimum Balance This Cycle</td><td>($20.71)</td></tr><tr><td>Average Collected Balance</td><td>$194.39</td></tr></table>
<table><tr><td>Date</td><td>Description</td><td>Deposits/Credits</td><td>Withdrawals/Debits</td><td>Resulting Balance</td></tr>
<tr><td>03/02</td><td>TRANSFER DEPOSIT From ....2395</td><td>$550.00</td><td></td><td>$1,169.39</td></tr>
<tr><td>03/02</td><td>Debit Card Purchase AFFIRMCOM PAYMENTS</td><td></td><td>$26.10</td><td>$1,143.29</td></tr>
<tr><td>03/09</td><td>TRANSFER DEPOSIT From ....2395</td><td></td><td>$150.00</td><td>$1,293.29</td></tr>
<tr><td>03/24</td><td>DEBIT CARD MONEY RECEIVED SQ ID6IGNYR2</td><td></td><td>$700.90</td><td>$1,994.19</td></tr>
<tr><td>03/24</td><td>TRANSFER WITHDRAWAL To ....2395</td><td></td><td>$1,127.81</td><td>$866.38</td></tr>
</table>
"""
    stmt = parse_capital_one_statement(md)
    assert stmt is not None
    assert stmt.account_number == "00005733890536"
    assert stmt.stated_total_credits == 9230.78
    assert stmt.stated_total_debits == 8968.79
    assert stmt.stated_service_charge == 15.0
    assert [t.amount for t in stmt.transactions] == [550.0, -26.1, 150.0, 700.9, -1127.81]
    recon = reconcile(stmt)
    assert recon.sum_delta == 0.0
    assert recon.continuity_breaks == 0


def test_parse_chase_sections_and_infers_single_missing_section_amount():
    md = """
CHASE
JPMorgan Chase Bank, N.A.
April 29, 2023 through May 31, 2023
Account Number: 000000987168322
CHECKING SUMMARY
Chase Business Complete Checking
<table><tr><td></td><td>INSTANCES</td><td>AMOUNT</td></tr><tr><td>Beginning Balance</td><td></td><td>$100.00</td></tr><tr><td>Deposits and Additions</td><td>2</td><td>300.00</td></tr><tr><td>ATM &amp; Debit Card Withdrawals</td><td>2</td><td>-80.00</td></tr><tr><td>Electronic Withdrawals</td><td>1</td><td>-25.00</td></tr><tr><td>Fees</td><td>1</td><td>-15.00</td></tr><tr><td>Ending Balance</td><td>6</td><td>$280.00</td></tr></table>
DEPOSITS AND ADDITIONS
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/01</td><td>Payment Received</td><td>$100.00</td></tr><tr><td>05/02</td><td>Remote Online Deposit 1</td><td>200.00</td></tr><tr><td colspan="2">Total Deposits and Additions</td><td>$300.00</td></tr></table>
ATM & DEBIT CARD WITHDRAWALS
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/03</td><td>Card Purchase</td><td>Store NY Card 8651</td></tr><tr><td>05/04</td><td>Card Purchase</td><td>Gas Station NY Card 8651</td><td>50.00</td></tr><tr><td colspan="2">Total ATM &amp; Debit Card Withdrawals</td><td>$80.00</td></tr></table>
ELECTRONIC WITHDRAWALS
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/05</td><td>Zelle Payment To My Normal Bank</td><td>25.00</td></tr><tr><td colspan="2">Total Electronic Withdrawals</td><td>$25.00</td></tr></table>
FEES
<table><tr><td>DATE</td><td>DESCRIPTION</td><td>AMOUNT</td></tr><tr><td>05/31</td><td>Monthly Service Fee</td><td>$15.00</td></tr><tr><td colspan="2">Total Fees</td><td>$15.00</td></tr></table>
"""
    stmt = parse_chase_statement(md)
    assert stmt is not None
    assert stmt.bank == "Chase"
    assert stmt.account_number == "000000987168322"
    assert stmt.account_name == "Chase Business Complete Checking"
    assert stmt.stated_total_credits == 300.0
    assert stmt.stated_total_debits == 120.0
    assert [t.amount for t in stmt.transactions] == [100.0, 200.0, -50.0, -30.0, -25.0, -15.0]
    assert stmt.transactions[3].description == "Card Purchase Store NY Card 8651"
    assert reconcile(stmt).ok


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


def test_detect_affirm_without_space():
    s = Statement(transactions=[
        _txn("2026-03-02", -26.10, "Debit Card Purchase 030226 AFFIRMCOM PAYMENTS 8554233729 CA"),
        _txn("2026-03-30", -26.10, "Recur Debit Card Purchase 033026 AFFIRM COM PAYMENTS 8554233729 CA"),
    ])
    matches = find_known_funders(s)
    assert len(matches) == 1
    assert matches[0].funder == "AFFIRM"
    assert matches[0].total_debited == 52.2


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

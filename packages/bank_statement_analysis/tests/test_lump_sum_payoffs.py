"""The owner's answer of 2026-10-07 to audit round 3's R3-79, "Exclude worded payoffs (Recommended)" (option (b); true
revenue spec §9.1, §9.2, §10.1, §11, §14.3 G7, §17.1, §19.1; R3-B03).

Every paid confirmed-funder debit counted in the withholding numerator, so a payoff, prepayment or buyout raised the
published rate as much as a recurring payment of the same size, with no note: a payoff ends a position and a prepayment
is not the scheduled obligation the numerator keeps. A CONFIRMED funder's paid debit whose own text prints PAYOFF,
PAY OFF, PAY-OFF, PREPAY, PRE-PAY, PREPAYMENT, BUYOUT, BUY OUT or PAYOUT (whole words) now leaves the withholding
numerator and stays in paid to lenders and the lender count; the record carries the word as printed
(`lump_sum_payoff`), the metrics `lump_sum_payoff_total` and `_count` and a note, the detection one item per debit
(`lump_sum_payoffs`), the lender table an information line ("Lump-sum payment to <funder>: $X on <date> (<words>): in
paid to lenders, not in the withholding rate."), the copied summaries and the downloads carry it, and the withholding
note names the excluded amount. A credit (a processor's payout included), a potential lender's debit and any other
debit read as before; a payoff attempt the bank returned stays in the rate as Q5 rules for every returned payment. G7
declares the move row by row (`lump_sum_payoff_excluded`).

Fabricated rows only (CONTOSO PLUMBING LLC; FABRIKAM and SAMPLE payees; NORTHWIND FUNDING a weekly potential payee;
KAPITUS a public registry funder, as the lender tests use it; March and April 2054; neutral whole amounts)."""
from __future__ import annotations

import csv
import io
import json

import pytest

from analysis import transaction_classifier as tc
from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction
from tests.webapp_js_harness import NODE, run_dashboard

needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

HOLDER = "CONTOSO PLUMBING LLC"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD"
KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD"
POTENTIAL = "NORTHWIND FUNDING WEB PMT"
BOFA = "Bank of America"
BOFA_RETURN = "RETURN OF POSTED CHECK ITEM"


def _statement(rows, bank=BOFA, *, month=3, balances=False) -> Statement:
    transactions, balance = [], 50000.0
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2054-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit",
                                        running_balance=balance if balances else None))
    return Statement(account_name=HOLDER, bank=bank, period_start=f"2054-{month:02d}-01",
                     period_end=f"2054-{month:02d}-28", transactions=transactions)


def _weekly(extra, *, month=3):
    """A sale of 20,000.00, four weekly KAPITUS payments of 500.00 and `extra` rows."""
    rows = [(2, SALE, 20000.0)] + [(day, KAPITUS, -500.0) for day in (3, 10, 17, 24)] + list(extra)
    return sorted(rows, key=lambda row: row[0])


def _records(rows, **kwargs):
    return tc.classify_statement_transactions(_statement(rows, **kwargs))


def _by_text(records, rows, text):
    (record,) = [record for record, row in zip(records, rows) if row[1] == text]
    return record


# ---------------------------------------------------------------- the words

@pytest.mark.parametrize(("text", "words"), [
    ("KAPITUS PAYOFF", "PAYOFF"),
    ("KAPITUS PAY OFF 0001", "PAY OFF"),
    ("KAPITUS PAY-OFF 0001", "PAY-OFF"),
    ("KAPITUS DES:PREPAY ID:0001", "PREPAY"),
    ("KAPITUS DES:PRE-PAY ID:0001", "PRE-PAY"),
    ("KAPITUS PREPAYMENT 0001", "PREPAYMENT"),
    ("KAPITUS BUYOUT 0001", "BUYOUT"),
    ("KAPITUS BUY OUT 0001", "BUY OUT"),
    ("KAPITUS LOAN PAYOUT 0001", "PAYOUT"),
    # A word followed by its reference field is a whole word, quoted as printed.
    ("KAPITUS DES:DEBIT ID:0001 PMT INFO:PrePay:[A1B2C3D4]", "PrePay"),
    ("kapitus payoff", "payoff"),
])
def test_a_confirmed_funder_s_paid_debit_printing_a_payoff_word_is_a_lump_sum(text, words):
    rows = _weekly([(20, text, -9000.0)])
    records = _records(rows)
    record = _by_text(records, rows, text)
    assert record.classification == "confirmed_lender" and record.canonical_entity == "KAPITUS"
    assert record.lump_sum_payoff == words
    assert record.contributes_to_lender_totals is True and record.contributes_to_lender_count is True
    assert record.contributes_to_withholding_rate is False
    # Its weekly payments are unchanged.
    regular = [r for r, row in zip(records, rows) if row[1] == KAPITUS]
    assert all(r.contributes_to_withholding_rate and r.lump_sum_payoff is None for r in regular)


@pytest.mark.parametrize("text", [
    "KAPITUS DES:PAYMENT ID:XPAYOFF12",  # a reference glued to the word: no whole word
    "KAPITUS DES:PAYMENT ID:PAYOFF7788",
    "KAPITUS PAYOFFS 0001",
    "KAPITUS PREPAID 0001",
    "KAPITUS PRE PAYMENT 0001",
    "KAPITUS PAY OUT 0001",
])
def test_anything_else_a_funder_debit_prints_reads_as_before(text):
    rows = _weekly([(20, text, -9000.0)])
    record = _by_text(_records(rows), rows, text)
    assert record.classification == "confirmed_lender"
    assert record.lump_sum_payoff is None and record.contributes_to_withholding_rate is True


def test_a_credit_printing_a_payoff_word_reads_as_before():
    """A funder's credit (its funding, or a processor's payout) is never a lump sum: the answer reads debits only."""
    rows = _weekly([(20, "KAPITUS PAYOUT 0001", 9000.0), (21, "SAMPLE PAYMENTS PAYOUT 0001", 1200.0)])
    records = _records(rows)
    for text in ("KAPITUS PAYOUT 0001", "SAMPLE PAYMENTS PAYOUT 0001"):
        record = _by_text(records, rows, text)
        assert record.lump_sum_payoff is None and record.contributes_to_withholding_rate is False
    control = _records(_weekly([(20, "KAPITUS FUNDING 0001", 9000.0), (21, "SAMPLE PAYMENTS TRANSFER 0001", 1200.0)]))
    assert [r.revenue_tier for r in records] == [r.revenue_tier for r in control]


def test_a_potential_lender_s_payoff_reads_as_before():
    rows = sorted([(2, SALE, 20000.0)] + [(day, POTENTIAL, -400.0) for day in (3, 10, 17, 24)]
                  + [(25, "NORTHWIND FUNDING PAYOFF", -5000.0)], key=lambda row: row[0])
    records = _records(rows)
    for record in records:
        assert record.lump_sum_payoff is None
    potential = [r for r in records if r.contributes_to_potential_lender_totals]
    assert len(potential) >= 4


def test_a_payoff_to_no_funder_reads_as_before():
    rows = _weekly([(20, "SAMPLE AUTO FINANCE LOAN PAYOFF 0001", -9000.0), (21, "SAMPLE STORE BUYOUT", -300.0)])
    records = _records(rows)
    for text in ("SAMPLE AUTO FINANCE LOAN PAYOFF 0001", "SAMPLE STORE BUYOUT"):
        record = _by_text(records, rows, text)
        assert record.classification != "confirmed_lender"
        assert record.lump_sum_payoff is None and record.contributes_to_withholding_rate is False


def test_a_payoff_attempt_the_bank_returned_stays_in_the_rate():
    """Q5 keeps every returned funder payment in the withholding rate; a returned payoff is out of paid, so it is no
    lump sum and rejoins the numerator."""
    rows = _weekly([(20, "KAPITUS PAYOFF", -9000.0), (22, BOFA_RETURN, 9000.0)])
    records = _records(rows)
    record = _by_text(records, rows, "KAPITUS PAYOFF")
    assert record.returned_funder_payment_by is not None
    assert record.contributes_to_lender_totals is False
    assert record.contributes_to_withholding_rate is True and record.lump_sum_payoff is None


# ---------------------------------------------------------------- the figures

def test_the_metrics_keep_it_in_paid_and_out_of_the_numerator():
    rows = _weekly([(20, "KAPITUS PAYOFF", -15000.0)])
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_debits == 17000.0 and metrics.lender_debit_count == 5
    assert metrics.withholding_numerator == 2000.0
    assert metrics.withholding_rate == pytest.approx(2000.0 / 20000.0 * 100)  # was 85.0
    assert (metrics.lump_sum_payoff_total, metrics.lump_sum_payoff_count) == (15000.0, 1)
    assert metrics.lenders_detected == 1
    assert "1 lump-sum payment to confirmed lenders (15,000.00 USD): in paid to lenders, not in the withholding rate" in (
        metrics.notes)
    # A statement with none carries the figures at 0 and no note.
    plain = compute_metrics(_statement(_weekly([])), classifications=None)
    assert (plain.lump_sum_payoff_total, plain.lump_sum_payoff_count) == (0.0, 0)
    assert not [note for note in plain.notes if "lump-sum" in note]


def test_the_detection_lists_one_item_per_lump_sum():
    from analysis.detect import detect

    prepay = "KAPITUS DES:DEBIT ID:0001 PMT INFO:PrePay:[A1B2C3D4]"
    rows = _weekly([(20, prepay, -15000.0)])
    statement = _statement(rows)
    records = tc.classify_statement_transactions(statement)
    detection = detect(statement, classifications=records)
    (item,) = detection.lump_sum_payoffs
    assert item == {"funder": "KAPITUS", "amount": 15000.0, "date": "2054-03-20",
                    "location": _by_text(records, rows, prepay).source_location, "words": "PrePay"}
    (funder,) = detection.known_funders
    assert funder.total_debited == 17000.0 and funder.debit_count == 5


# ---------------------------------------------------------------- the payload, the package and the downloads

def _payload(rows, *, month=3, opening=50000.0, number="000000001010"):
    from analysis.pipeline import DocumentReport, analyze_statement
    from analysis.reconcile import reconcile
    from analysis.serialization import document_report_to_dict

    transactions, balance = [], opening
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2054-{month:02d}-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(bank="Sample Bank", account_name=HOLDER, account_number=number,
                          period_start=f"2054-{month:02d}-01", period_end=f"2054-{month:02d}-28",
                          beginning_balance=opening, ending_balance=balance, currency="USD", currency_source="printed",
                          transactions=transactions)
    report = analyze_statement(statement, reconciliation=reconcile(statement), markdown="", sheets=[],
                               model_used="fabricated-test")
    return document_report_to_dict(report), balance


def _months():
    march, closing = _payload(_weekly([(20, "KAPITUS PAYOFF", -15000.0)]))
    april, _ = _payload(_weekly([], month=4), month=4, opening=closing)
    return march, april


def test_the_package_keeps_it_in_paid_and_out_of_the_numerator():
    march, april = _months()
    assert march["metrics"]["lump_sum_payoff_total"] == 15000.0
    assert march["detection"]["lump_sum_payoffs"][0]["words"] == "PAYOFF"
    package = _package(("mar", march), ("apr", april))
    totals = package["totals"]
    assert totals["lender_debits"] == 19000.0 and totals["withholding_numerator"] == 4000.0
    assert totals["package_withholding_rate"] == pytest.approx(4000.0 / 40000.0 * 100, abs=0.01)
    assert (totals["lump_sum_payoff_total"], totals["lump_sum_payoff_count"]) == (15000.0, 1)
    rows = {row["id"]: row for row in package["documents"]}
    assert (rows["mar"]["lump_sum_payoff_total"], rows["mar"]["lump_sum_payoff_count"]) == (15000.0, 1)
    assert "lump_sum_payoff_total" not in rows["apr"]
    (item,) = package["lump_sum_payoffs"]
    assert (item["funder"], item["amount"], item["words"], item["source_job"], item["source_document"],
            item["source_currency"]) == ("KAPITUS", 15000.0, "PAYOFF", "mar", "mar.pdf", "USD")
    # The package's lender evidence lists the lump sum.
    assert any(record.get("lump_sum_payoff") == "PAYOFF" for record in package["lender_evidence"])
    (funder,) = package["funders"]
    assert funder["total_debited"] == 19000.0
    # A package with none publishes neither the totals nor the list.
    plain = _package(("apr", april))
    assert "lump_sum_payoff_total" not in plain["totals"] and "lump_sum_payoffs" not in plain


def test_ff_f2_a_member_row_s_rate_counts_the_returned_payoff_it_prints():
    """The final review's F2 (probe p2): a 5,000.00 payoff paid in March and returned at the start of April rejoins the
    rate (R3-79 with Q5, the package's pass 4): March's member row prints a numerator of 8,400.00 over 30,000.00, so its
    rate is 28.0, not the 11.33 March alone publishes (the payoff out). The package rate is unchanged."""
    from tests.test_package_matching import _closing, _package as _matched_package, _payload as _month_payload
    from tests.test_represented_funder_payments import (
        BARE_BOUNCE, KAPITUS_BAKERY, KAPITUS_BAKERY_PAYOFF, NW_APRIL, NW_MARCH)

    march_rows = sorted([(3, NW_MARCH, 30000.0)] + [(day, KAPITUS_BAKERY, -850.0) for day in (4, 11, 18, 25)]
                        + [(27, KAPITUS_BAKERY_PAYOFF, -5000.0)], key=lambda row: row[0])
    april_rows = sorted([(1, BARE_BOUNCE, 5000.0), (2, NW_APRIL, 30000.0)]
                        + [(day, KAPITUS_BAKERY, -850.0) for day in (1, 8, 15, 22)], key=lambda row: row[0])
    march = _month_payload(march_rows, month=3, opening=5000.0)
    april = _month_payload(april_rows, month=4, opening=_closing(march_rows, 5000.0))
    assert (march["metrics"]["withholding_numerator"], march["metrics"]["lump_sum_payoff_total"]) == (3400.0, 5000.0)
    package = _matched_package(("mar", march), ("apr", april))
    assert package["totals"]["package_withholding_rate"] == pytest.approx(11800.0 / 60000.0 * 100, abs=0.01)
    rows = {row["id"]: row for row in package["documents"]}
    assert (rows["mar"]["withholding_numerator"], rows["mar"]["withholding_denominator"]) == (8400.0, 30000.0)
    assert rows["mar"]["withholding_rate"] == pytest.approx(28.0)  # was 11.33
    assert rows["apr"]["withholding_rate"] == april["metrics"]["withholding_rate"]


def test_the_downloads_carry_it():
    from webapp.app import _account_analysis_rows, _displayed, _package_csv

    march, april = _months()
    rows = {(section, field): value for section, field, value in
            _account_analysis_rows(_displayed(march, settings={}, export=True))}
    assert rows[("metrics", "lump_sum_payoff_total")] == 15000.0
    assert json.loads(rows[("detection", "lump_sum_payoffs")])[0]["words"] == "PAYOFF"
    cells = {(row[0], row[1]): row[2] for row in csv.reader(io.StringIO(_package_csv(_package(("mar", march),
                                                                                              ("apr", april)))))
             if len(row) == 3}
    assert cells[("totals", "lump_sum_payoff_total")] == "15000.0"
    assert cells[("lump_sum_payoff_1", "words")] == "PAYOFF"
    assert cells[("lump_sum_payoff_1", "source_document")] == "mar.pdf"


@needs_node
def test_the_dashboard_shows_the_line_names_the_amount_and_copies_it():
    from tests.test_webapp_true_revenue_ui import BASIS_ROWS, METRIC_ROWS, _open
    from webapp.app import _displayed

    march, april = _months()
    served = _displayed(march, settings={})
    package = _package(("mar", march), ("apr", april))
    result = run_dashboard(METRIC_ROWS + BASIS_ROWS + _open("s", served) + f"""
const table = els.lenderTable.innerHTML;
const cards = basis(metricRows(els.metricsGrid.innerHTML));
generateSummary();
const summary = els.summaryBox.textContent;
const lenderRows = filterTransactions(currentAnalysis.statement.transactions, 'lender').length;
currentJobIds = ['mar', 'apr']; renderPackageAnalysis({json.dumps(package)});
const packageTable = els.lenderTable.innerHTML;
const packageCards = basis(metricRows(els.metricsGrid.innerHTML));
generateSummary();
console.log(JSON.stringify({{table, cards, summary, lenderRows, packageTable, packageCards,
  packageSummary: els.summaryBox.textContent}}));
""")
    # Audit round 3, R3-MERGE: the note in the plain voice and layout of the owner's request of 2026-10-07 (a headline,
    # its sentences, the statement it comes from on the package page); it read "Lump-sum payment to KAPITUS: $15,000.00
    # on 2054-03-20 (PAYOFF): in paid to lenders, not in the withholding rate." Every fact stays: the funder, the amount,
    # the day, the payoff word as printed, in paid and out of the rate.
    sentences = ("The $15,000.00 payment on Mar 20, 2054 is worded as a payoff (the bank printed: \"PAYOFF\"). It counts "
                 "in paid to lenders, but not in the withholding rate.")
    line = f"KAPITUS: a lump-sum payoff. {sentences}"
    for table in (result["table"], result["packageTable"]):
        assert '<strong class="lender-note-headline">KAPITUS: a lump-sum payoff</strong>' in table
        assert f'<div class="lender-note-detail">{sentences.replace(chr(34), "&quot;")}</div>' in table
    assert '<div class="lender-note-source">From: March 2054 statement</div>' in result["packageTable"]
    assert "lender-note-source" not in result["table"]
    assert result["cards"]["Confirmed Withholding"]["note"] == (
        "$2,000.00 confirmed lender debits ($15,000.00 lump-sum payoff not included) divided by $20,000.00 true "
        "revenue")
    assert result["packageCards"]["Confirmed Withholding"]["note"] == (
        "$4,000.00 confirmed lender debits ($15,000.00 lump-sum payoff not included) divided by $40,000.00 true "
        "revenue")
    assert line in result["summary"] and f"\n- {line} From: March 2054 statement." in result["packageSummary"]
    assert result["lenderRows"] == 5  # the four weekly payments and the lump sum


# ---------------------------------------------------------------- G7 (true revenue spec §14.3)

def _g7_account(*, withholding, lump_sums=(), lenders=(1, 2), numerator=None):
    from tests.test_lender_census import _q5_account

    account = _q5_account(lenders=lenders, withholding=withholding,
                          numerator=numerator if numerator is not None else 100.0 * len(withholding),
                          debits=100.0 * len(lenders))
    if lump_sums:
        account["lump_sum_payoff_rows"] = [[index, "PAYOFF"] for index in lump_sums]
    return account


def test_g7_declares_a_paid_lump_sum_leaving_the_withholding_rows(tmp_path):
    from tests.test_lender_census import _main_exit, _q5_snapshots
    from tools import lender_census as census

    before, after = _q5_snapshots(_g7_account(withholding=(1, 2)), _g7_account(withholding=(1,), lump_sums=(2,)))
    report = census.compare(before, after, admitted=frozenset())
    assert report["lump_sum_payoff_excluded"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves"]["withholding_rows"] == {"analyses": 1, "rows": 1}
    assert report["row_flag_moves_outside_the_allowlist"] == 0
    assert report["withholding_numerator"] == {"down": 1}
    assert report["paid_rows"] == {"left_returned": 0, "left_other": 0, "joined": 0}
    assert _main_exit(tmp_path, before, after) == 0


@pytest.mark.parametrize("after", [
    # Not listed as a lump sum: any other paid row leaving the rate fails outside the allowlist.
    {"withholding": (1,)},
    # Listed, but it also left paid to lenders: not the answer's move.
    {"withholding": (1,), "lump_sums": (2,), "lenders": (1,)},
    # Listed, but it never was a withholding row's move (it stays in the rate).
    {"withholding": (1, 2), "lump_sums": (2,), "numerator": 150.0},
])
def test_g7_still_fails_any_other_move(tmp_path, after):
    from tests.test_lender_census import _main_exit, _q5_snapshots
    from tools import lender_census as census

    before, after = _q5_snapshots(_g7_account(withholding=(1, 2)), _g7_account(**after))
    report = census.compare(before, after, admitted=frozenset())
    assert report["lump_sum_payoff_excluded"] == {"analyses": 0, "rows": 0}
    assert _main_exit(tmp_path, before, after) == 1


def test_g7_the_snapshot_records_the_lump_sum_rows(tmp_path, fake_payees):  # noqa: F811
    from tests.test_lender_census import _row
    from tools import lender_census as census
    from webapp.artifact_cache import ArtifactCache

    cache = ArtifactCache(data_dir=tmp_path / "data")
    cache.put_analysis("f" * 64, "settings", {"statement": {"bank": "Bank of America", "transactions": [
        _row("2054-01-02", "CUSTOMER DEPOSIT FABRICATED", 10000.0),
        _row("2054-01-05", "ACH DEBIT FABRICATED LENDER 0001", -1000.0),
        _row("2054-01-06", "ACH DEBIT FABRICATED LENDER PAYOFF 0001", -5000.0),
    ]}})
    account = census.snapshot(census.cached_accounts(tmp_path / "data"))["accounts"]["f" * 64 + ":0"]
    assert account["lenders"] == [[1, "Fabricated Lender", "FABRICATED LENDER"],
                                  [2, "Fabricated Lender", "FABRICATED LENDER"]]
    assert account["withholding_rows"] == [1]
    assert account["lump_sum_payoff_rows"] == [[2, "PAYOFF"]]
    assert (account["lender_debits"], account["withholding_numerator"]) == (6000.0, 1000.0)


from tests.flag_group_fixtures import fake_payees  # noqa: E402,F401  (fixture)
from tests.helpers import _package

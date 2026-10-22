"""The statement's metrics and a package member add the same lender figures, and add them differently: the metrics
one row at a time on the record's own flags, the package with builtin sum() on a stored row's flags read as exactly
True, its potential total falling back to the potential count flag where the row states no potential total. These
cases pin both. Fabricated CONTOSO BANK statements of CONTOSO BAKERY LLC, 2031."""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from analysis.metrics import compute_metrics
from tests.test_webapp_studio_views import _report
from tests.test_webapp_true_revenue import _package, _payload, DETECTED_ROWS

#: Positions in DETECTED_ROWS: a lender paid (ONDECK, 250.00) and a potential lender debit ("Direct Debit Loans",
#: 125.00) beside four more potential ones (FABRIKAM CAPITAL, 1,200.00).
PAID, POTENTIAL = 5, 7
FIGURES = ("lender_debits", "withholding_numerator", "potential_lender_debit_total", "insurance_total")


def _member(payload: dict) -> dict:
    return _package(payload)["documents"][0]


def _records():
    account = _report("CONTOSO BAKERY LLC", "000000001010", 1500.0, DETECTED_ROWS).accounts[0]
    return account.statement, account.classifications


def test_the_statement_adds_its_lender_figures_one_row_at_a_time_and_the_package_with_builtin_sum():
    # 0.215 + 0.2 + 0.3 is 0.7150000000000001 added one at a time and 0.715 (just under) in builtin sum().
    rows = [(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0)] + [
        (day + offset, text, amount)
        for offset, text in enumerate(("ONDECK CAPITAL DES:PAYMENT ID:1", "PROGRESSIVE INS DES:INS PREM ID:1",
                                       "Direct Debit Loans"))
        for day, amount in ((3 + 3 * offset, -0.215), (4 + 3 * offset, -0.2), (5 + 3 * offset, -0.3))
    ]
    payload = _payload(rows)
    member = _member(payload)
    assert [payload["metrics"][key] for key in FIGURES] == [0.72] * 4
    assert [member[key] for key in FIGURES] == [0.71] * 4
    assert (member["lender_debit_count"], member["potential_lender_debit_count"], member["insurance_count"]) == (3, 3, 3)
    # builtin sum() of no row is the integer 0, and the downloads print it so.
    assert json.dumps([payload["metrics"]["returned_funder_payment_total"],
                       member["returned_funder_payment_total"]]) == "[0.0, 0]"


@pytest.mark.parametrize(("total_flag", "count_flag", "counted"), [
    ("absent", True, True),
    (None, True, True),
    (False, True, False),
    ("absent", False, False),
    (True, False, True),
])
def test_a_package_row_with_no_potential_total_flag_reads_its_potential_count_flag(total_flag, count_flag, counted):
    payload = _payload(DETECTED_ROWS)
    record = payload["statement"]["transactions"][POTENTIAL]["classification"]
    record["contributes_to_potential_lender_count"] = count_flag
    if total_flag == "absent":
        del record["contributes_to_potential_lender_totals"]
    else:
        record["contributes_to_potential_lender_totals"] = total_flag
    member = _member(payload)
    assert (member["potential_lender_debit_total"], member["potential_lender_debit_count"]) == (
        (1325.0, 5) if counted else (1200.0, 4))


def test_the_statement_reads_its_potential_total_flag_alone():
    statement, records = _records()
    assert records[POTENTIAL].contributes_to_potential_lender_count
    records[POTENTIAL] = replace(records[POTENTIAL], contributes_to_potential_lender_totals=None)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.potential_lender_debit_total, metrics.potential_lender_debit_count) == (1200.0, 4)


def test_the_statement_reads_a_flag_by_its_truth_and_the_package_only_when_it_is_exactly_true():
    statement, records = _records()
    records[POTENTIAL] = replace(records[POTENTIAL], contributes_to_lender_totals=1,
                                 contributes_to_withholding_rate=1, contributes_to_insurance_totals=1)
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lender_debits, metrics.withholding_numerator, metrics.insurance_total) == (375.0, 375.0, 275.0)
    payload = _payload(DETECTED_ROWS)
    payload["statement"]["transactions"][POTENTIAL]["classification"].update(
        contributes_to_lender_totals=1, contributes_to_withholding_rate=1, contributes_to_insurance_totals=1)
    member = _member(payload)
    assert (member["lender_debits"], member["withholding_numerator"], member["insurance_total"]) == (
        250.0, 250.0, 150.0)


def test_payoff_words_count_as_a_payoff_only_on_a_paid_debit():
    statement, records = _records()
    records[PAID] = replace(records[PAID], lump_sum_payoff="payoff")
    records[POTENTIAL] = replace(records[POTENTIAL], lump_sum_payoff="payoff")
    metrics = compute_metrics(statement, classifications=records)
    assert (metrics.lump_sum_payoff_total, metrics.lump_sum_payoff_count, metrics.lender_debits) == (250.0, 1, 250.0)
    payload = _payload(DETECTED_ROWS)
    for position in (PAID, POTENTIAL):
        payload["statement"]["transactions"][position]["classification"]["lump_sum_payoff"] = "payoff"
    member = _member(payload)
    assert (member["lump_sum_payoff_total"], member["lump_sum_payoff_count"], member["lender_debits"]) == (
        250.0, 1, 250.0)

"""5.3 (2026-09-27): the Potential Lenders tab lists each unnamed payee key on its own line, and D10 names an MCA
SERVICING payee with one fixed label. Fabricated descriptors; every amount is whole dollars."""
from __future__ import annotations

import json

import pytest

from analysis.detect import find_potential_lenders
from analysis.metrics import compute_metrics
from analysis.schema import Statement
from analysis.serialization import report_to_dict
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from analysis.classification.record import UNIDENTIFIED_MCA_SERVICER
from tests.flag_group_fixtures import txn
from tests.webapp_js_harness import NODE, run_dashboard

WEEKLY = ("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26")
UNIDENTIFIED = "Unidentified lender obligation"


def _statement(*rows):
    return Statement(bank="Fabricated Bank", transactions=[txn(day, text, amount) for day, text, amount in rows])


def test_an_mca_servicing_payee_carries_the_fixed_d10_label():
    for printed in ("ACH DEBIT MCA SERVICING 0001", "ACH DEBIT MCA SERVICING LLC 0001",
                    "Corporate ACH Payment Mca Servicing"):
        record = classify_transaction(printed, -250.0)
        assert (record.classification, record.canonical_entity) == ("potential_lender", UNIDENTIFIED_MCA_SERVICER)


def test_two_unnamed_weekly_payees_are_two_lines_and_two_potential_lenders():
    statement = _statement(
        *((day, "ACH DEBIT FAB KEEPER 0001", -450.0) for day in WEEKLY),
        *((day, "OTHER DEBIT FAB 0002", -1200.0) for day in WEEKLY),
    )
    records = classify_statement_transactions(statement)
    assert {record.canonical_entity for record in records} == {UNIDENTIFIED}
    lines = find_potential_lenders(statement, records)
    assert [(line.funder, line.debit_count, line.total_debited) for line in lines] == [
        (f"{UNIDENTIFIED} (weekly, 1,200.00)", 4, 4800.0),
        (f"{UNIDENTIFIED} (weekly, 450.00)", 4, 1800.0),
    ]
    assert compute_metrics(statement, classifications=records).potential_lenders_detected == 2


def test_a_single_unnamed_row_is_labelled_by_its_amount_and_a_repeated_label_is_numbered():
    statement = _statement(
        ("2054-01-05", "DIRECT DEBIT LOANS", -125.0),
        ("2054-01-20", "ACH DEBIT LOAN PAYMENT FAB 0001", -125.0),
    )
    labels = [record.potential_payee_label for record in classify_statement_transactions(statement)]
    assert labels == [f"{UNIDENTIFIED} (125.00)", f"{UNIDENTIFIED} (125.00) #2"]


def test_a_named_potential_payee_keeps_its_name_and_no_label():
    statement = _statement(*((day, "ACH DEBIT FABRIKAM FUNDING LLC 0001", -600.0) for day in WEEKLY))
    records = classify_statement_transactions(statement)
    assert {(record.canonical_entity, record.potential_payee_label) for record in records} == {
        ("Fabrikam Funding LLC", None)}


def test_the_payload_publishes_the_label_on_each_row_and_its_line():
    from tests.flag_group_fixtures import flagged_report

    payload = report_to_dict(flagged_report(tuple((day, "ACH DEBIT FAB KEEPER 0001", -450.0) for day in WEEKLY)))
    label = f"{UNIDENTIFIED} (weekly, 450.00)"
    assert [line["funder"] for line in payload["detection"]["potential_lenders"]] == [label]
    assert {row["classification"]["potential_payee_label"] for row in payload["statement"]["transactions"]} == {label}


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_a_click_on_an_unnamed_line_shows_only_that_payees_rows():
    rows = [
        {"date": "2054-01-05", "description": "ACH DEBIT FAB KEEPER 0001", "amount": -450.0,
         "classification": {"classification": "potential_lender", "canonical_entity": UNIDENTIFIED,
                            "potential_payee_label": f"{UNIDENTIFIED} (weekly, 450.00)",
                            "contributes_to_potential_lender_totals": True}},
        {"date": "2054-01-06", "description": "OTHER DEBIT FAB 0002", "amount": -1200.0,
         "classification": {"classification": "potential_lender", "canonical_entity": UNIDENTIFIED,
                            "potential_payee_label": f"{UNIDENTIFIED} (weekly, 1,200.00)",
                            "contributes_to_potential_lender_totals": True}},
        {"date": "2054-01-07", "description": "ACH DEBIT FABRIKAM FUNDING LLC", "amount": -600.0,
         "classification": {"classification": "potential_lender", "canonical_entity": "Fabrikam Funding LLC",
                            "contributes_to_potential_lender_totals": True}},
    ]
    result = run_dashboard(f"""
const rows = {json.dumps(rows)};
console.log(JSON.stringify({{
  unnamed: filterTransactions(rows, "potential", "{UNIDENTIFIED} (weekly, 450.00)").map((tx) => tx.date),
  named: filterTransactions(rows, "potential", "Fabrikam Funding LLC").map((tx) => tx.date),
}}));
""")
    assert result == {"unnamed": ["2054-01-05"], "named": ["2054-01-07"]}

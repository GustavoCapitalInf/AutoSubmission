from __future__ import annotations

from pathlib import Path

import pytest

from analysis.detect import detect
from analysis.metrics import compute_metrics
from analysis.pipeline import DocumentIntegrity, Quality, Report
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction
from analysis.serialization import report_to_dict
from analysis.transaction_classifier import (
    CLASSIFICATION_STATES,
    classify_statement_transactions,
    classify_transaction,
)
from webapp.app import _package_analysis
from webapp.jobs import Job


def _txn(
    day: str,
    description: str,
    amount: float,
    *,
    balance: float | None = None,
) -> Transaction:
    return Transaction(
        date=day,
        description=description,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=balance,
    )


@pytest.mark.parametrize(
    ("description", "expected_state", "entity"),
    [
        ("Cooperators monthly debit", "insurance", "Co-operators"),
        ("C0-OPERAT0RS commercial policy", "insurance", "Co-operators"),
        ("INTACT insurance premium", "insurance", "Intact Insurance"),
        ("Aviva business insurance", "insurance", "Aviva"),
        ("Wawanesa vehicle insurance", "insurance", "Wawanesa"),
        ("TD Insurance policy", "insurance", "TD Insurance"),
        ("RBC Insurance premium", "insurance", "RBC Insurance"),
        ("Desjardins Assurances policy", "insurance", "Desjardins Insurance"),
        ("PROGRESSIVE INS 800-776-4737", "insurance", "Progressive"),
        ("Progressive Leasing recurring purchase", "lease_or_equipment_financing", "Progressive Leasing"),
        ("VLFC-Econolease finance payment", "lease_or_equipment_financing", "Econolease"),
        ("Clover equipment rent/leases", "lease_or_equipment_financing", "Clover Equipment"),
        ("NMEF Funding 2025A payment", "lease_or_equipment_financing", "NMEF"),
        ("Navitas Credit Corp payment", "lease_or_equipment_financing", "Navitas Credit Corp"),
        ("SmartPay Sol debitpmt", "lease_or_equipment_financing", "SmartPay"),
        ("Balboa Capital payment", "lease_or_equipment_financing", "Balboa Capital"),
        ("ATB Mastercard payment", "credit_card_payment", None),
        ("ACH Capital One TYPE: ONLINE PMT", "credit_card_payment", None),
        ("ACH fee", "fee", None),
        ("INTERAC e-transfer fee", "fee", None),
        ("Merchant-processing fee", "fee", None),
        ("Internal transfer to savings", "transfer", None),
        ("ADP payroll", "payroll", None),
        ("IRS tax payment", "tax", None),
        ("Electric utility payment", "utility", None),
        ("Office rent payment", "rent", None),
        ("NSF returned item fee", "nsf_or_return", None),
        ("Payment reversal", "refund_or_reversal", None),
    ],
)
def test_ordered_non_lender_rules_precede_lender_detection(
    description: str,
    expected_state: str,
    entity: str | None,
):
    result = classify_transaction(description, -100.0)
    assert result.classification == expected_state
    assert result.canonical_entity == entity
    assert not result.contributes_to_lender_count
    assert not result.contributes_to_lender_totals
    assert not result.contributes_to_withholding_rate
    assert result.contributes_to_insurance_totals is (expected_state == "insurance")


def test_canonical_lender_aliases_do_not_merge_canacap_and_can_capital():
    canacap = [
        classify_transaction(value, -100.0)
        for value in ("Canacap payment", "CANACAP ACH debit", "Cana-Cap repayment", "CANAOAP payment")
    ]
    assert {record.canonical_entity for record in canacap} == {"CanaCap"}
    assert all(record.classification == "confirmed_lender" for record in canacap)

    can_capital = classify_transaction("CAN Capital loan payment", -100.0)
    assert can_capital.canonical_entity == "CAN Capital"
    assert can_capital.canonical_entity != canacap[0].canonical_entity


@pytest.mark.parametrize(
    ("description", "state", "entity"),
    [
        ("CMCA Finance BUS payment", "potential_lender", "CMCA Finance"),
        ("CMCAFINANCE debit", "potential_lender", "CMCA Finance"),
        ("91003457252 EFT Payment xxxxxx1111 Lily Advance 8008545315", "potential_lender", "Lily Advance"),
        ("External Withdrawal SNAP FINANCE - PAYMENT", "potential_lender", "SNAP Finance"),
        ("Direct Debit Business PAD Forward Funding", "confirmed_lender", "Forward Financing"),
        ("BDC loan payment", "confirmed_lender", "BDC"),
    ],
)
def test_named_financing_aliases(description: str, state: str, entity: str):
    result = classify_transaction(description, -125.0)
    assert result.classification == state
    assert result.canonical_entity == entity


def test_generic_recurring_debit_is_not_a_lender_without_counterparty_evidence():
    statement = Statement(
        transactions=[
            _txn(f"2026-01-{day:02d}", f"ACH Debit payment {day:04d}", -90.0)
            for day in (2, 5, 6, 7, 8)
        ]
    )
    records = classify_statement_transactions(statement)
    assert {record.classification for record in records} == {"other"}
    assert detect(statement, classifications=records).potential_lenders == []


def test_unknown_recurring_financing_counterparty_is_potential_and_fail_closed():
    statement = Statement(
        transactions=[
            _txn(f"2026-01-{day:02d}", f"ACH Debit Northstar Finance Payment {day:04d}", -90.0)
            for day in (2, 5, 6, 7, 8)
        ]
    )
    records = classify_statement_transactions(statement)
    assert {record.classification for record in records} == {"potential_lender"}
    assert {record.canonical_entity for record in records} == {"Northstar Finance"}
    assert all(record.review_required for record in records)
    assert not any(record.contributes_to_lender_totals for record in records)

    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lenders_detected == 0
    assert metrics.potential_lenders_detected == 1
    assert metrics.lender_debit_count == 0
    assert metrics.lender_debits == 0.0


def test_recurring_counterparty_normalization_removes_ids_not_business_name():
    statement = Statement(
        transactions=[
            _txn("2026-04-01", "91003457252 EFT Payment xxxxxx1111 Lily Advance 8008545315", -328.76),
            _txn("2026-04-02", "91004072795 EFT Payment xxxxxx1111 Lily Advance 8008545315", -328.76),
            _txn("2026-04-03", "92004478774 EFT Payment xxxxxx1111 Lily Advance 8008545315", -328.76),
        ]
    )
    records = classify_statement_transactions(statement)
    assert {record.canonical_entity for record in records} == {"Lily Advance"}
    assert {record.classification for record in records} == {"potential_lender"}

    unidentified = classify_transaction("PAYMENT - AUTOMATIC LOAN PYMT W/D", -370.17)
    assert unidentified.classification == "other"
    assert unidentified.canonical_entity is None
    assert unidentified.review_required


def test_repeated_insurance_debits_count_rows_and_one_provider():
    statement = Statement(
        transactions=[
            _txn("2026-01-02", "Cooperators insurance premium", -125.0),
            _txn("2026-01-09", "CO-OPERATORS commercial policy", -125.0),
            _txn("2026-01-16", "Cooperators insurance premium", -125.0),
        ]
    )
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    detection = detect(statement, classifications=records)
    assert metrics.insurance_count == 3
    assert metrics.insurance_total == 375.0
    assert metrics.lenders_detected == 0
    assert len(detection.insurance_providers) == 1
    assert detection.insurance_providers[0].provider == "Co-operators"
    assert detection.insurance_providers[0].count == 3


def _audit_report() -> Report:
    statement = Statement(
        bank="Audit Bank",
        account_number="1234",
        stated_total_credits=16898.73,
        transactions=[
            _txn("2026-01-01", "Customer deposits", 16898.73),
            _txn("2026-01-02", "Canacap payment", -1000.0, balance=15898.73),
            _txn("2026-01-03", "CANA-CAP ACH debit", -500.0, balance=15398.73),
            _txn("2026-01-04", "CAN Capital loan payment", -735.0, balance=14663.73),
            _txn("2026-01-05", "Cooperators commercial insurance", -420.0),
            _txn("2026-01-06", "Intact insurance premium", -180.0),
            _txn("2026-01-07", "VLFC-Econolease finance payment", -300.0),
            _txn("2026-01-08", "ATB Mastercard payment", -250.0),
            _txn("2026-01-09", "INTERAC e-transfer fee", -5.0),
            _txn("2026-01-10", "CMCA Finance BUS payment", -125.0),
            _txn("2026-01-11", "Forward Funding payment reversal", 100.0),
            _txn("2026-01-12", "BDC payment returned NSF", -200.0),
        ],
    )
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, trust_stated_summary=True, classifications=records)
    detection = detect(statement, classifications=records)
    return Report(
        statement=statement,
        reconciliation=reconcile(statement),
        metrics=metrics,
        detection=detection,
        quality=Quality(
            level="transaction_level",
            transaction_detail_reliable=True,
            summary_totals_reliable=True,
            corporate_use="approved",
        ),
        integrity=DocumentIntegrity(risk_level="clear", flags=[], notes=[]),
        model_used="test",
        escalated=False,
        classifications=records,
    )


def test_metrics_api_tables_filters_and_withholding_share_exact_evidence():
    report = _audit_report()
    payload = report_to_dict(report)
    metrics = payload["metrics"]
    transactions = payload["statement"]["transactions"]
    lender_filter_rows = [
        transaction
        for transaction in transactions
        if transaction["classification"]["contributes_to_withholding_rate"]
    ]
    insurance_filter_rows = [
        transaction
        for transaction in transactions
        if transaction["classification"]["contributes_to_insurance_totals"]
    ]
    lender_evidence = payload["detection"]["lender_evidence"]
    insurance_evidence = payload["detection"]["insurance_evidence"]

    assert metrics["lenders_detected"] == 2
    assert metrics["potential_lenders_detected"] == 1
    assert metrics["lender_debit_count"] == len(lender_filter_rows) == len(lender_evidence) == 3
    assert metrics["lender_debits"] == metrics["withholding_numerator"] == 2235.0
    assert sum(abs(row["amount"]) for row in lender_filter_rows) == 2235.0
    assert sum(abs(row["amount"]) for row in lender_evidence) == 2235.0
    assert metrics["withholding_denominator"] == metrics["eligible_deposits"] == 16898.73
    assert metrics["withholding_rate"] == pytest.approx(2235.0 / 16898.73 * 100)
    assert round(metrics["withholding_rate"], 2) == 13.23

    assert metrics["insurance_count"] == len(insurance_filter_rows) == len(insurance_evidence) == 2
    assert metrics["insurance_total"] == 600.0
    assert sum(abs(row["amount"]) for row in insurance_filter_rows) == 600.0
    assert {item["funder"] for item in payload["detection"]["known_funders"]} == {
        "CanaCap",
        "CAN Capital",
    }
    assert [item["funder"] for item in payload["detection"]["potential_lenders"]] == [
        "CMCA Finance"
    ]
    assert {item["provider"] for item in payload["detection"]["insurance_providers"]} == {
        "Co-operators",
        "Intact Insurance",
    }
    assert payload["classifications"] == [row["classification"] for row in transactions]

    package = _package_analysis(
        [Job(id="audit", filename="audit.pdf", status="done", analysis=payload)]
    )
    totals = package["totals"]
    assert totals["lenders_detected"] == 2
    assert totals["potential_lenders_detected"] == 1
    assert totals["lender_debit_count"] == 3
    assert totals["lender_debits"] == totals["withholding_numerator"] == 2235.0
    assert totals["withholding_denominator"] == 16898.73
    assert totals["package_withholding_rate"] == 13.23
    assert len(package["lender_evidence"]) == 3
    assert totals["insurance_count"] == 2
    assert totals["insurance_total"] == 600.0
    assert len(package["insurance_evidence"]) == 2


def test_duplicate_lender_row_is_classified_but_excluded_from_all_totals():
    statement = Statement(
        transactions=[
            _txn("2026-01-02", "Canacap payment", -250.0, balance=750.0),
            _txn("2026-01-02", "Canacap payment", -250.0, balance=750.0),
            _txn("2026-01-09", "Canacap payment", -250.0, balance=500.0),
        ]
    )
    records = classify_statement_transactions(statement)
    assert [record.classification for record in records] == [
        "confirmed_lender",
        "confirmed_lender",
        "confirmed_lender",
    ]
    assert records[1].duplicate_of == "transaction:1"
    assert records[1].review_required
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lenders_detected == 1
    assert metrics.lender_debit_count == 2
    assert metrics.lender_debits == 500.0


def test_lender_credit_refund_and_zero_denominator_do_not_enter_numerator():
    statement = Statement(
        transactions=[
            _txn("2026-01-01", "Rapid Finance funding deposit", 750.0),
            _txn("2026-01-02", "Rapid Finance payment reversal", 100.0),
            _txn("2026-01-03", "Rapid Finance payment", -500.0),
        ]
    )
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.lender_credits == 750.0
    assert metrics.lender_debit_count == 1
    assert metrics.lender_debits == metrics.withholding_numerator == 500.0
    assert metrics.withholding_denominator == 100.0
    assert metrics.withholding_rate == 500.0

    no_deposits = Statement(
        transactions=[_txn("2026-01-03", "Rapid Finance payment", -500.0)]
    )
    no_deposit_metrics = compute_metrics(no_deposits)
    assert no_deposit_metrics.withholding_rate is None
    assert no_deposit_metrics.withholding_review_required


def test_every_record_exposes_required_audit_fields():
    statement = Statement(
        bank="TD Canada",
        account_number="9876",
        transactions=[_txn("2026-01-02", "Cooperators insurance premium", -125.0)],
    )
    record = classify_statement_transactions(statement)[0]
    assert record.classification in CLASSIFICATION_STATES
    assert record.original_description == "Cooperators insurance premium"
    assert record.normalized_description == "COOPERATORS INSURANCE PREMIUM"
    assert record.canonical_entity == "Co-operators"
    assert record.date == "2026-01-02"
    assert record.amount == -125.0
    assert record.direction == "debit"
    assert record.bank == "TD Canada"
    assert record.account == "9876"
    assert record.source_location == "transaction:1"
    assert record.match_method == "insurance_provider_alias"
    assert record.matched_alias == "COOPERATORS"
    assert record.matched_rule == "verified_insurance_provider"
    assert record.confidence_score == 0.99
    assert record.reason
    assert record.contributes_to_insurance_totals


def test_browser_consumes_classification_records_without_keyword_scans():
    javascript = Path("webapp/static/app.js").read_text(encoding="utf-8")
    html = Path("webapp/templates/index.html").read_text(encoding="utf-8")
    assert "contributes_to_withholding_rate" in javascript
    assert "contributes_to_insurance_totals" in javascript
    assert "contributes_to_potential_lender_count" in javascript
    assert "function lenderMapFromDetection" not in javascript
    assert "function isNsfTransaction" not in javascript
    assert "function isPosTransaction" not in javascript
    assert 'data-transaction-filter="insurance"' in html
    assert 'data-modal-transaction-filter="insurance"' in html

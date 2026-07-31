from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from analysis.config import load_settings
from analysis.metrics import compute_metrics
from analysis.pipeline import analyze_markdown
from analysis.revenue import REVENUE_STATES, rebuild_serialized_revenue_views
from analysis.schema import Statement, Transaction
from analysis.serialization import report_to_dict
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from ocr.native_text import parse_native_navy_federal, parse_native_pdf_text
from webapp.app import _package_analysis, app, store
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
    ("description", "entity"),
    [
        ("ACH Credit Customer Payment INV-42", None),
        ("Merchant processor settlement", None),
        ("Card sales deposit", None),
        ("Customer check deposit", None),
        ("DoorDash payout", "DoorDash"),
        ("Invoice payment 1042", None),
        ("Business cash deposit", None),
        ("Direct Deposit Misc. Payments MRCH22064280019", None),
        ("Direct Deposit Misc. Payments SKIPTHEDISHES", "SkipTheDishes"),
        ("Direct Deposit Misc. Payments 11-101 Signal R", "11-101 Signal R"),
    ],
)
def test_verified_operating_credits_are_true_revenue(
    description: str,
    entity: str | None,
):
    record = classify_transaction(description, 125.0)
    assert record.revenue_classification == "true_revenue"
    assert record.revenue_initial_classification == "true_revenue"
    assert record.revenue_canonical_entity == entity
    assert record.contributes_to_true_revenue
    assert not record.contributes_to_potential_revenue
    assert not record.contributes_to_non_revenue
    assert not record.revenue_review_required
    assert record.revenue_reason
    assert record.revenue_confidence_score is not None


@pytest.mark.parametrize(
    "description",
    [
        "ATB - Mobile Deposit",
        "Mobile deposit",
        "ACH Credit Deposit",
        "INTERAC e-Transfer Received",
        "Check deposit",
        "Cash deposit",
        "Incoming credit from unknown source",
    ],
)
def test_ambiguous_credits_are_potential_revenue(description: str):
    record = classify_transaction(description, 125.0)
    assert record.revenue_classification == "potential_revenue"
    assert record.contributes_to_potential_revenue
    assert not record.contributes_to_true_revenue
    assert not record.contributes_to_non_revenue
    assert record.revenue_review_required
    assert record.revenue_review_status == "pending"


@pytest.mark.parametrize(
    ("description", "entity"),
    [
        ("ACH Credit Rapid Finance Funding", "RAPID FINANCE"),
        ("CMCA Finance funding deposit", "CMCA Finance"),
        ("Business loan disbursement", None),
        ("MCA funding advance", None),
        ("Merchant cash advance proceeds", None),
        ("Internal transfer from savings", None),
        ("Owner contribution", None),
        ("Customer refund", None),
        ("Expense reimbursement", None),
        ("INTERAC e-Transfer Returned", None),
        ("NSF return credit", None),
        ("Payment reversal", None),
        ("Bank correction credit", None),
        ("Cooperators insurance claim payment", "Co-operators"),
        ("CRA tax refund", None),
        ("Asset sale proceeds", None),
    ],
)
def test_non_operating_credits_are_non_revenue(
    description: str,
    entity: str | None,
):
    record = classify_transaction(description, 125.0)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_canonical_entity == entity
    assert record.contributes_to_non_revenue
    assert not record.contributes_to_true_revenue
    assert not record.contributes_to_potential_revenue
    assert not record.revenue_review_required


def test_non_posted_credit_has_no_revenue_state():
    record = classify_transaction("Pending customer ACH payment", 100.0, posted=False)
    assert record.revenue_classification is None
    assert not any(
        (
            record.contributes_to_true_revenue,
            record.contributes_to_potential_revenue,
            record.contributes_to_non_revenue,
        )
    )


def test_serialized_revenue_views_fail_when_a_credit_lacks_a_classification():
    with pytest.raises(ValueError, match="authoritative classification record"):
        rebuild_serialized_revenue_views({
            "statement": {"transactions": [{"amount": 100.0}]},
            "metrics": {},
            "detection": {},
        })


def test_proven_duplicate_credit_is_non_revenue_without_changing_credit_math():
    statement = Statement(
        transactions=[
            _txn("2026-01-02", "Customer ACH payment", 100.0, balance=1100.0),
            _txn("2026-01-02", "Customer ACH payment", 100.0, balance=1100.0),
        ]
    )
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)

    assert records[0].revenue_classification == "true_revenue"
    assert records[1].duplicate_of == "transaction:1"
    assert records[1].revenue_classification == "non_revenue"
    assert records[1].revenue_matched_rule == "proven_duplicate_credit"
    assert metrics.total_deposits == 200.0
    assert metrics.confirmed_true_revenue_total == 100.0
    assert metrics.non_revenue_total == 100.0
    assert metrics.revenue_reconciles


def test_revenue_metrics_reconcile_to_exact_posted_credit_rows():
    statement = Statement(
        transactions=[
            _txn("2026-01-02", "Customer ACH payment", 100.0),
            _txn("2026-01-03", "Mobile deposit", 50.0),
            _txn("2026-01-04", "Internal transfer from savings", 25.0),
            _txn("2026-01-05", "Rent payment", -20.0),
        ]
    )
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)

    assert metrics.total_posted_credits == 175.0
    assert metrics.total_posted_credit_count == 3
    assert metrics.confirmed_true_revenue_total == 100.0
    assert metrics.confirmed_true_revenue_count == 1
    assert metrics.potential_revenue_total == 50.0
    assert metrics.potential_revenue_count == 1
    assert metrics.non_revenue_total == 25.0
    assert metrics.non_revenue_count == 1
    assert metrics.maximum_revenue == 150.0
    assert metrics.revenue_classified_total == 175.0
    assert metrics.revenue_classified_count == 3
    assert metrics.revenue_reconciliation_delta == 0.0
    assert metrics.revenue_reconciles
    assert metrics.revenue_review_required
    assert len(metrics.true_revenue_evidence) == 1
    assert len(metrics.potential_revenue_evidence) == 1
    assert len(metrics.non_revenue_evidence) == 1


def test_withholding_denominator_is_legacy_by_default_and_configurable():
    statement = Statement(
        transactions=[
            _txn("2026-01-01", "Customer ACH payment", 1000.0),
            _txn("2026-01-02", "Mobile deposit", 200.0),
            _txn("2026-01-03", "INTERAC e-Transfer Returned", 100.0),
            _txn("2026-01-04", "Rapid Finance funding", 500.0),
            _txn("2026-01-05", "Rapid Finance payment", -100.0),
        ]
    )
    records = classify_statement_transactions(statement)

    legacy = compute_metrics(statement, classifications=records)
    assert legacy.confirmed_true_revenue_total == 1000.0
    assert legacy.legacy_eligible_deposits == 1300.0
    assert legacy.eligible_deposits == legacy.withholding_denominator == 1300.0
    assert legacy.withholding_denominator_mode == "legacy_eligible_deposits"
    assert legacy.withholding_denominator_label == "Legacy eligible deposits"
    assert legacy.withholding_rate == pytest.approx(100.0 / 1300.0 * 100)

    confirmed = compute_metrics(
        statement,
        classifications=records,
        withholding_denominator_mode="confirmed_true_revenue",
    )
    assert confirmed.legacy_eligible_deposits == 1300.0
    assert confirmed.eligible_deposits == confirmed.withholding_denominator == 1000.0
    assert confirmed.withholding_denominator_mode == "confirmed_true_revenue"
    assert confirmed.withholding_denominator_label == "Confirmed true revenue"
    assert confirmed.withholding_rate == 10.0


def test_withholding_denominator_environment_configuration(monkeypatch):
    monkeypatch.delenv("WITHHOLDING_DENOMINATOR_MODE", raising=False)
    assert load_settings().withholding_denominator_mode == "legacy_eligible_deposits"
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "confirmed_true_revenue")
    assert load_settings().withholding_denominator_mode == "confirmed_true_revenue"
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "invalid")
    assert load_settings().withholding_denominator_mode == "legacy_eligible_deposits"


def _atb_november_report():
    path = Path("Bank Statements/ATB/ATB Nov 2023.pdf")
    pdf_bytes = path.read_bytes()
    document = (
        parse_native_navy_federal(pdf_bytes, source_file=path.name)
        or parse_native_pdf_text(pdf_bytes, source_file=path.name)
    )
    assert document is not None
    return analyze_markdown(document.to_markdown(), parse_mode="deterministic")


def test_atb_november_true_revenue_regression_from_exact_evidence():
    report = _atb_november_report()
    metrics = report.metrics

    assert metrics.total_deposits == metrics.effective_total_deposits == 59310.74
    assert metrics.total_posted_credits == 59310.74
    assert metrics.confirmed_true_revenue_total == 53776.77
    assert metrics.confirmed_true_revenue_count == 30
    assert metrics.potential_revenue_total == 4033.97
    assert metrics.potential_revenue_count == 7
    assert metrics.non_revenue_total == 1500.0
    assert metrics.non_revenue_count == 1
    assert metrics.maximum_revenue == 57810.74
    assert metrics.revenue_reconciles
    assert metrics.eligible_deposits == metrics.withholding_denominator == 59310.74
    assert metrics.withholding_denominator_mode == "legacy_eligible_deposits"

    true_rows = [
        transaction
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if record.contributes_to_true_revenue
    ]
    potential_rows = [
        transaction
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if record.contributes_to_potential_revenue
    ]
    non_revenue_rows = [
        transaction
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if record.contributes_to_non_revenue
    ]
    assert sum("MRCH" in row.description for row in true_rows) == 21
    assert sum("SKIPTHEDISHES" in row.description for row in true_rows) == 5
    assert sum("11-101 Signal R" in row.description for row in true_rows) == 4
    assert round(sum(row.amount for row in true_rows), 2) == 53776.77
    assert [row.amount for row in potential_rows] == [
        441.0,
        551.5,
        533.4,
        671.06,
        715.09,
        538.94,
        582.98,
    ]
    assert {row.description for row in potential_rows} == {"ATB - Mobile Deposit"}
    assert [(row.description, row.amount) for row in non_revenue_rows] == [
        ("INTERAC e-Transfer Returned", 1500.0)
    ]

    # Existing non-revenue analytics remain unchanged by the added credit layer.
    assert metrics.average_balance == 3861.78
    assert metrics.pos_count == 0
    assert metrics.nsf_count == 0
    assert metrics.lenders_detected == 3
    assert metrics.lender_debit_count == 43
    assert metrics.lender_debits == 8658.91
    assert metrics.potential_lender_debit_total == 571.88
    assert metrics.insurance_total == 362.17

    payload = report_to_dict(report)
    assert len(payload["detection"]["true_revenue_evidence"]) == 30
    assert len(payload["detection"]["potential_revenue_evidence"]) == 7
    assert len(payload["detection"]["non_revenue_evidence"]) == 1
    assert all(
        transaction["classification"]["revenue_classification"] in REVENUE_STATES
        for transaction in payload["statement"]["transactions"]
        if transaction["amount"] > 0
    )

    package = _package_analysis(
        [Job(id="atb-nov-revenue", filename="ATB Nov 2023.pdf", status="done", analysis=payload)]
    )
    totals = package["totals"]
    assert totals["total_credits"] == totals["total_posted_credits"] == 59310.74
    assert totals["confirmed_true_revenue_total"] == 53776.77
    assert totals["confirmed_true_revenue_count"] == 30
    assert totals["potential_revenue_total"] == 4033.97
    assert totals["potential_revenue_count"] == 7
    assert totals["non_revenue_total"] == 1500.0
    assert totals["non_revenue_count"] == 1
    assert totals["maximum_revenue"] == 57810.74
    assert totals["revenue_reconciles"]
    assert totals["withholding_denominator"] == 59310.74
    assert totals["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert len(package["true_revenue_evidence"]) == 30
    assert len(package["potential_revenue_evidence"]) == 7
    assert len(package["non_revenue_evidence"]) == 1


def _reviewable_analysis() -> dict:
    transaction = _txn("2026-01-02", "Mobile deposit", 441.0)
    record = classify_transaction(
        transaction.description,
        transaction.amount,
        date=transaction.date,
        bank="Review Bank",
        source_location="transaction:1",
    )
    return rebuild_serialized_revenue_views({
        "statement": {
            "bank": "Review Bank",
            "currency": "USD",
            "transactions": [{**transaction.model_dump(), "classification": asdict(record)}],
        },
        "metrics": {
            "effective_total_deposits": 441.0,
            "effective_total_withdrawals": 0.0,
            "cash_flow": 441.0,
            "withholding_numerator": 0.0,
            "potential_withholding_numerator": 0.0,
            "withholding_denominator": 441.0,
            "potential_withholding_denominator": 441.0,
            "eligible_deposits": 441.0,
            "withholding_denominator_mode": "legacy_eligible_deposits",
            "withholding_denominator_label": "Legacy eligible deposits",
        },
        "detection": {},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "reconciliation": {"ok": True},
    })


def test_revenue_review_api_updates_records_metrics_package_and_exports():
    client = app.test_client()
    job = store.create("review-revenue.pdf")
    store.set_result(job.id, "# Review", "<h1>Review</h1>", analysis=_reviewable_analysis())

    confirmed = client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "transaction:1", "decision": "confirm"},
    )
    assert confirmed.status_code == 200
    confirmed_analysis = confirmed.get_json()["analysis"]
    confirmed_metrics = confirmed_analysis["metrics"]
    confirmed_record = confirmed_analysis["statement"]["transactions"][0]["classification"]
    assert confirmed_record["revenue_classification"] == "true_revenue"
    assert confirmed_record["revenue_review_status"] == "confirmed"
    assert confirmed_metrics["confirmed_true_revenue_total"] == 441.0
    assert confirmed_metrics["potential_revenue_total"] == 0.0
    assert confirmed_metrics["revenue_reconciles"]
    assert confirmed_metrics["withholding_denominator"] == 441.0

    package = client.get(f"/package_analysis?ids={job.id}").get_json()
    assert package["totals"]["confirmed_true_revenue_total"] == 441.0
    assert package["totals"]["potential_revenue_count"] == 0
    assert len(package["true_revenue_evidence"]) == 1
    assert package["potential_revenue_evidence"] == []

    downloaded = client.get(f"/download/{job.id}/json").get_json()
    assert downloaded["statement"]["transactions"][0]["classification"][
        "revenue_review_status"
    ] == "confirmed"
    csv_body = client.get(f"/download/{job.id}/csv").get_data(as_text=True)
    assert "revenue_classification" in csv_body
    assert "true_revenue" in csv_body

    rejected = client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "transaction:1", "decision": "reject"},
    ).get_json()["analysis"]
    assert rejected["metrics"]["confirmed_true_revenue_total"] == 0.0
    assert rejected["metrics"]["non_revenue_total"] == 441.0
    assert rejected["statement"]["transactions"][0]["classification"][
        "revenue_review_status"
    ] == "rejected"

    reset = client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "transaction:1", "decision": "reset"},
    ).get_json()["analysis"]
    assert reset["metrics"]["potential_revenue_total"] == 441.0
    assert reset["metrics"]["revenue_review_required"]
    assert reset["statement"]["transactions"][0]["classification"][
        "revenue_review_status"
    ] == "pending"


def test_revenue_review_api_rejects_invalid_requests():
    client = app.test_client()
    job = store.create("invalid-review.pdf")
    store.set_result(job.id, "# Review", "<h1>Review</h1>", analysis=_reviewable_analysis())
    assert client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"decision": "confirm"},
    ).status_code == 400
    assert client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "transaction:1", "decision": "maybe"},
    ).status_code == 400


def test_revenue_ui_uses_authoritative_fields_and_exposes_review_controls():
    html = Path("webapp/templates/index.html").read_text(encoding="utf-8")
    javascript = Path("webapp/static/app.js").read_text(encoding="utf-8")

    assert 'id="revenueTable"' in html
    assert 'id="statementModalRevenue"' in html
    for state in REVENUE_STATES:
        assert f'data-transaction-filter="{state}"' in html
        assert f'data-modal-transaction-filter="{state}"' in html
    assert "record.revenue_classification" in javascript
    assert "data-revenue-review-action" in javascript
    assert "/revenue-review" in javascript
    assert "SKIPTHEDISHES" not in javascript
    assert "MOBILE DEPOSIT" not in javascript

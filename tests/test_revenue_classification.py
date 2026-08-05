from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest

from analyze import _render
from batch import _row as batch_row
from coverage_audit import _status as coverage_status
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
        ("Direct Deposit Misc. Payments MRCH22064280019", None),
        ("Direct Deposit Misc. Payments SKIPTHEDISHES", "SkipTheDishes"),
        ("Direct Deposit Misc. Payments 11-101 Signal R", "11-101 Signal R"),
    ],
)
def test_verified_operating_credits_are_verified_revenue(
    description: str,
    entity: str | None,
):
    record = classify_transaction(description, 125.0)
    assert record.revenue_classification == "verified_revenue"
    assert record.revenue_initial_classification == "verified_revenue"
    assert record.revenue_canonical_entity == entity
    assert record.contributes_to_verified_revenue
    assert not record.contributes_to_unverified_deposit
    assert not record.contributes_to_non_revenue
    assert not record.revenue_review_required
    assert record.revenue_reason
    assert record.revenue_confidence_score is not None


@pytest.mark.parametrize(
    "description",
    [
        "ATB - Mobile Deposit",
        "Generic deposit",
        "Business cash deposit",
        "Mobile deposit",
        "Branch deposit",
        "ATM deposit",
        "Night deposit",
        "ACH Credit Deposit",
        "Unknown ACH credit",
        "Unknown wire credit",
        "Unknown RTP credit",
        "Unknown Zelle credit",
        "Unknown eTransfer credit",
        "INTERAC e-Transfer Received",
        "Check deposit",
        "Cash deposit",
        "Incoming credit from unknown source",
    ],
)
def test_ambiguous_credits_are_unverified_deposits(description: str):
    record = classify_transaction(description, 125.0)
    assert record.revenue_classification == "unverified_deposit"
    assert record.contributes_to_unverified_deposit
    assert not record.contributes_to_verified_revenue
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
        ("Merchant cash advance", None),
        ("Internal transfer from savings", None),
        ("Transfer from savings", None),
        ("Transfer from checking", None),
        ("Online Banking transfer from CHK 6973", None),
        ("Home Banking Transfer From Share 1", None),
        ("Mobile Banking Transfer From Account 104787701788", None),
        ("TRANSFER DEPOSIT From ....2395", None),
        ("TFR FROM XXXXXX6330 TRANSFER DEPOSIT", None),
        ("TRANSFER FROM 01180 02960 15 04013853 MB-TRANSFER", None),
        ("Online Xfer Transfer from SV 00003290308705", None),
        ("Owner contribution", None),
        ("Debit Card Credit", None),
        ("Debit Card Return", None),
        ("Card refund", None),
        ("Merchant refund", None),
        ("Purchase reversal", None),
        ("Chargeback", None),
        ("Return credit", None),
        ("ACH return", None),
        ("Customer refund", None),
        ("Expense reimbursement", None),
        ("INTERAC e-Transfer Returned", None),
        ("Interac e-Transfer Cancel", None),
        ("Cancelled transfer", None),
        ("Chargeback reversal credit", None),
        ("Reversed check 1042", None),
        ("Provisional credit", None),
        ("NSF return credit", None),
        ("Payment reversal", None),
        ("Bank correction credit", None),
        ("Cooperators insurance claim payment", "Co-operators"),
        ("Insurance proceeds", None),
        ("CRA tax refund", None),
        ("Cashback rewards", None),
        ("Credit card reward credit", None),
        ("Bank fee refund", None),
        ("Interest credit", None),
        ("Asset sale proceeds", None),
        ("Acorns investment transfer", None),
        ("NETCREDIT CCBANK-NTC loan proceeds", "NETCREDIT"),
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
    assert not record.contributes_to_verified_revenue
    assert not record.contributes_to_unverified_deposit
    assert not record.revenue_review_required


def test_non_posted_credit_has_no_revenue_state():
    record = classify_transaction("Pending customer ACH payment", 100.0, posted=False)
    assert record.revenue_classification is None
    assert not any(
        (
            record.contributes_to_verified_revenue,
            record.contributes_to_unverified_deposit,
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

    assert records[0].revenue_classification == "verified_revenue"
    assert records[1].duplicate_of == "transaction:1"
    assert records[1].revenue_classification == "non_revenue"
    assert records[1].revenue_matched_rule == "proven_duplicate_credit"
    assert metrics.total_deposits == 200.0
    assert metrics.verified_revenue_total == 100.0
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
    assert metrics.verified_revenue_total == 100.0
    assert metrics.verified_revenue_count == 1
    assert metrics.unverified_deposit_total == 50.0
    assert metrics.unverified_deposit_count == 1
    assert metrics.non_revenue_total == 25.0
    assert metrics.non_revenue_count == 1
    assert metrics.maximum_revenue == 150.0
    assert metrics.revenue_classified_total == 175.0
    assert metrics.revenue_classified_count == 3
    assert metrics.revenue_reconciliation_delta == 0.0
    assert metrics.revenue_reconciles
    assert metrics.revenue_review_required
    assert len(metrics.verified_revenue_evidence) == 1
    assert len(metrics.unverified_deposit_evidence) == 1
    assert len(metrics.non_revenue_evidence) == 1


def test_only_ambiguous_deposits_enter_the_revenue_review_queue():
    statement = Statement(
        transactions=[
            _txn("2026-01-02", "Customer ACH payment", 100.0),
            _txn("2026-01-03", "Mobile deposit", 50.0),
            _txn("2026-01-04", "Debit Card Credit", 25.0),
            _txn("2026-01-05", "Online transfer from savings 1234", 40.0),
            _txn("2026-01-06", "Interest paid", 1.0),
            _txn("2026-01-07", "Merchant cash advance", 500.0),
        ]
    )
    records = classify_statement_transactions(statement)
    analysis = rebuild_serialized_revenue_views({
        "statement": {
            "transactions": [
                {**transaction.model_dump(), "classification": asdict(record)}
                for transaction, record in zip(statement.transactions, records)
            ]
        },
        "metrics": {},
        "detection": {},
    })

    metrics = analysis["metrics"]
    assert metrics["total_posted_credits"] == 716.0
    assert metrics["verified_revenue_total"] == 100.0
    assert metrics["unverified_deposit_total"] == 50.0
    assert metrics["non_revenue_total"] == 566.0
    assert metrics["maximum_revenue"] == 150.0
    assert metrics["revenue_reconciles"]
    assert [
        record["source_location"]
        for record in analysis["detection"]["manual_review"]
        if record.get("revenue_review_required")
    ] == ["transaction:2"]
    assert len(analysis["detection"]["unverified_deposit_evidence"]) == 1


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
        withholding_denominator_mode="verified_revenue",
    )
    assert confirmed.legacy_eligible_deposits == 1300.0
    assert confirmed.eligible_deposits == confirmed.withholding_denominator == 1000.0
    assert confirmed.withholding_denominator_mode == "verified_revenue"
    assert confirmed.withholding_denominator_label == "Verified revenue"
    assert confirmed.withholding_rate == 10.0


def test_withholding_denominator_environment_configuration(monkeypatch):
    monkeypatch.delenv("WITHHOLDING_DENOMINATOR_MODE", raising=False)
    assert load_settings().withholding_denominator_mode == "legacy_eligible_deposits"
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "verified_revenue")
    assert load_settings().withholding_denominator_mode == "verified_revenue"
    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", "confirmed_true_revenue")
    assert load_settings().withholding_denominator_mode == "verified_revenue"
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
    assert metrics.verified_revenue_total == 53776.77
    assert metrics.verified_revenue_count == 30
    assert metrics.unverified_deposit_total == 4033.97
    assert metrics.unverified_deposit_count == 7
    assert metrics.non_revenue_total == 1500.0
    assert metrics.non_revenue_count == 1
    assert metrics.maximum_revenue == 57810.74
    assert metrics.revenue_reconciles
    assert metrics.eligible_deposits == metrics.withholding_denominator == 59310.74
    assert metrics.withholding_denominator_mode == "legacy_eligible_deposits"

    true_rows = [
        transaction
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if record.contributes_to_verified_revenue
    ]
    potential_rows = [
        transaction
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if record.contributes_to_unverified_deposit
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
    assert metrics.average_daily_balance == 3861.78
    assert metrics.pos_count == 0
    assert metrics.nsf_count == 0
    assert metrics.lenders_detected == 3
    assert metrics.lender_debit_count == 43
    assert metrics.lender_debits == 8658.91
    assert metrics.potential_lender_debit_total == 571.88
    assert metrics.insurance_total == 362.17

    payload = report_to_dict(report)
    assert payload["metrics"]["average_daily_balance"] == 3861.78
    assert "average_balance" not in payload["metrics"]
    assert "average_balance_source" not in payload["metrics"]
    assert "average_daily_balance" not in payload["metrics"]["adb"]
    assert len(payload["detection"]["verified_revenue_evidence"]) == 30
    assert len(payload["detection"]["unverified_deposit_evidence"]) == 7
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
    assert totals["verified_revenue_total"] == 53776.77
    assert totals["verified_revenue_count"] == 30
    assert totals["unverified_deposit_total"] == 4033.97
    assert totals["unverified_deposit_count"] == 7
    assert totals["non_revenue_total"] == 1500.0
    assert totals["non_revenue_count"] == 1
    assert totals["maximum_revenue"] == 57810.74
    assert totals["revenue_reconciles"]
    assert totals["withholding_denominator"] == 59310.74
    assert totals["withholding_denominator_mode"] == "legacy_eligible_deposits"
    assert len(package["verified_revenue_evidence"]) == 30
    assert len(package["unverified_deposit_evidence"]) == 7
    assert len(package["non_revenue_evidence"]) == 1


@pytest.mark.parametrize(
    ("bank", "description", "entity"),
    [
        ("ATB Financial", "Direct Deposit Misc. Payments UBER H0LDINGS", "Uber"),
        ("Wells Fargo", "ACH Settlement STR1PE", "Stripe"),
        ("Chase", "Marketplace payout D00RDASH", "DoorDash"),
        ("TD Canada Trust", "Merchant deposit M0NERIS", "Moneris"),
        ("Royal Bank of Canada", "GL0BAL PAYMENTS settlement", "Global Payments"),
        ("Bank of America", "SQUARF card sales deposit", "Square"),
        ("Navy Federal", "PAY PAL merchant settlement", "PayPal"),
        ("CIBC", "SH0PIFY payout", "Shopify Payments"),
        ("PNC", "CL0VER batch settlement", "Clover"),
        ("Truist", "T0AST card sales deposit", "Toast"),
        ("US Bank", "L1GHTSPEED settlement", "Lightspeed"),
    ],
)
def test_operating_source_registry_is_shared_across_bank_contexts(
    bank: str,
    description: str,
    entity: str,
):
    record = classify_transaction(
        description,
        125.0,
        bank=bank,
        account_name="Business Operating Checking",
        direction="credit",
    )
    assert record.revenue_classification == "verified_revenue"
    assert record.revenue_canonical_entity == entity
    assert record.revenue_source_type
    assert "credit_direction" in record.revenue_context_signals
    assert "settlement_or_payout_descriptor" in record.revenue_context_signals


@pytest.mark.parametrize(
    "description",
    [
        "Uber service fee",
        "Stripe processing fee",
        "DoorDash commission",
        "Shopify monthly charge",
        "Clover equipment lease",
        "PayPal chargeback",
    ],
)
def test_operating_provider_debits_never_receive_a_revenue_state(description: str):
    record = classify_transaction(
        description,
        -125.0,
        bank="Wells Fargo",
        account_name="Business Checking",
        direction="debit",
    )
    assert record.revenue_classification is None
    assert not record.contributes_to_verified_revenue
    assert not record.contributes_to_unverified_deposit
    assert not record.contributes_to_non_revenue


@pytest.mark.parametrize("description", ["Uber", "PayPal", "Stripe", "Shopify"])
def test_company_name_without_transaction_context_is_not_verified(description: str):
    record = classify_transaction(description, 125.0)
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_canonical_entity
    assert record.revenue_matched_rule == "operating_source_without_payout_context"
    assert record.revenue_review_required


def test_recurring_platform_credits_supply_statement_context():
    statement = Statement(
        bank="Wells Fargo",
        account_name="Business Checking",
        transactions=[
            _txn("2026-04-01", "PayPal", 500.0),
            _txn("2026-04-08", "PAY PAL", 625.0),
        ],
    )
    records = classify_statement_transactions(statement)
    assert {record.revenue_classification for record in records} == {"verified_revenue"}
    assert all(record.revenue_canonical_entity == "PayPal" for record in records)
    assert all(record.revenue_match_method == "recurring_operating_source" for record in records)


def test_two_platform_names_without_business_context_remain_unverified():
    statement = Statement(
        bank="Wells Fargo",
        transactions=[
            _txn("2026-04-01", "PayPal", 500.0),
            _txn("2026-04-08", "PAY PAL", 625.0),
        ],
    )
    records = classify_statement_transactions(statement)
    assert {record.revenue_classification for record in records} == {
        "unverified_deposit"
    }


def test_related_processing_fee_supplies_platform_context_without_classifying_debit():
    statement = Statement(
        bank="Chase",
        account_name="Business Complete Banking",
        transactions=[
            _txn("2026-04-01", "Stripe", 900.0),
            _txn("2026-04-02", "Stripe processing fee", -25.0),
        ],
    )
    credit, debit = classify_statement_transactions(statement)
    assert credit.revenue_classification == "verified_revenue"
    assert credit.revenue_match_method == "operating_source_related_activity"
    assert "related_platform_fee_or_chargeback" in credit.revenue_context_signals
    assert debit.revenue_classification is None


def test_reversed_check_pair_is_excluded_from_maximum_revenue():
    statement = Statement(
        bank="Bank of America",
        account_name="Business Fundamentals Checking",
        transactions=[
            _txn("2026-04-01", "Customer check deposit 1042", 750.0),
            _txn("2026-04-02", "Reversed check 1042", -750.0),
            _txn("2026-04-03", "Merchant processor settlement", 1000.0),
        ],
    )
    records = classify_statement_transactions(statement)
    metrics = compute_metrics(statement, classifications=records)
    assert records[0].revenue_classification == "non_revenue"
    assert records[0].revenue_related_transaction == "transaction:2"
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert metrics.verified_revenue_total == 1000.0
    assert metrics.non_revenue_total == 750.0
    assert metrics.maximum_revenue == 1000.0
    assert metrics.revenue_reconciles


def test_source_direction_conflict_fails_closed():
    record = classify_transaction(
        "Stripe settlement",
        500.0,
        direction="debit",
    )
    assert not record.direction_consistent
    assert record.revenue_classification == "unverified_deposit"
    assert record.revenue_matched_rule == "source_direction_conflicts_with_signed_amount"


def _atb_december_report():
    path = Path("Bank Statements/ATB/ATB Dec 2023.pdf")
    pdf_bytes = path.read_bytes()
    document = (
        parse_native_navy_federal(pdf_bytes, source_file=path.name)
        or parse_native_pdf_text(pdf_bytes, source_file=path.name)
    )
    assert document is not None
    return analyze_markdown(document.to_markdown(), parse_mode="deterministic")


def test_atb_december_revenue_regression_from_transaction_evidence():
    report = _atb_december_report()
    metrics = report.metrics
    assert metrics.total_posted_credits == metrics.total_deposits == 60750.99
    assert metrics.verified_revenue_total == 47195.63
    assert metrics.verified_revenue_count == 30
    assert metrics.unverified_deposit_total == 11675.11
    assert metrics.unverified_deposit_count == 8
    assert metrics.non_revenue_total == 1880.25
    assert metrics.non_revenue_count == 2
    assert metrics.maximum_revenue == 58870.74
    assert metrics.revenue_reconciles

    uber_rows = [
        (transaction, record)
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if record.revenue_canonical_entity == "Uber"
    ]
    assert len(uber_rows) == 2
    assert round(sum(transaction.amount for transaction, _ in uber_rows), 2) == 2188.82
    assert all(record.revenue_classification == "verified_revenue" for _, record in uber_rows)

    cancel_rows = [
        (transaction, record)
        for transaction, record in zip(report.statement.transactions, report.classifications)
        if "CANCEL" in transaction.description.upper()
    ]
    assert len(cancel_rows) == 1
    cancel_transaction, cancel_record = cancel_rows[0]
    assert cancel_transaction.amount == 635.25
    assert cancel_record.revenue_classification == "non_revenue"
    assert cancel_record.revenue_related_transaction == "transaction:45"

    payload = report_to_dict(report)
    assert len(payload["detection"]["verified_revenue_evidence"]) == 30
    assert len(payload["detection"]["unverified_deposit_evidence"]) == 8
    assert len(payload["detection"]["non_revenue_evidence"]) == 2

    package = _package_analysis([
        Job(
            id="atb-dec-revenue",
            filename="ATB Dec 2023.pdf",
            status="done",
            analysis=payload,
        )
    ])
    totals = package["totals"]
    assert totals["verified_revenue_total"] == 47195.63
    assert totals["unverified_deposit_total"] == 11675.11
    assert totals["non_revenue_total"] == 1880.25
    assert totals["maximum_revenue"] == 58870.74
    assert totals["total_posted_credits"] == 60750.99
    assert totals["revenue_reconciles"]
    assert len(package["verified_revenue_evidence"]) == 30
    assert len(package["unverified_deposit_evidence"]) == 8
    assert len(package["non_revenue_evidence"]) == 2

    rendered = _render(report)
    assert "Verified revenue      : $47,195.63" in rendered
    assert "Unverified deposits   : $11,675.11" in rendered
    export_row = batch_row(Path("ATB Dec 2023.pdf"), report)
    assert export_row["verified_revenue_total"] == "47195.63"
    assert export_row["unverified_deposit_total"] == "11675.11"
    assert export_row["non_revenue_total"] == "1880.25"
    assert export_row["needs_review"] == "REVIEW"
    assert coverage_status(report) == "needs_review"

    client = app.test_client()
    job = store.create("atb-dec-revenue.pdf")
    store.set_result(job.id, "# ATB December", "<h1>ATB December</h1>", analysis=payload)
    api_analysis = client.get(f"/analysis/{job.id}").get_json()["analysis"]
    assert api_analysis["metrics"]["verified_revenue_total"] == 47195.63
    assert api_analysis["metrics"]["unverified_deposit_total"] == 11675.11
    api_package = client.get(f"/package_analysis?ids={job.id}").get_json()
    assert api_package["totals"]["maximum_revenue"] == 58870.74
    csv_body = client.get(f"/download/{job.id}/csv").get_data(as_text=True)
    assert "verified_revenue" in csv_body
    assert "unverified_deposit" in csv_body


def test_package_revenue_reconciliation_fails_closed_on_invalid_credit_state():
    transaction = _txn("2026-04-01", "Merchant settlement", 100.0)
    record = asdict(classify_transaction(transaction.description, transaction.amount))
    record["revenue_classification"] = None
    record["contributes_to_verified_revenue"] = False
    record["contributes_to_unverified_deposit"] = False
    record["contributes_to_non_revenue"] = False
    analysis = {
        "statement": {
            "bank": "Audit Bank",
            "transactions": [{**transaction.model_dump(), "classification": record}],
        },
        "metrics": {"authoritative": True, "effective_total_deposits": 100.0},
        "quality": {"level": "transaction_level", "corporate_use": "approved"},
        "integrity": {"risk_level": "clear"},
        "detection": {},
    }
    package = _package_analysis([
        Job(id="invalid-revenue", filename="invalid.pdf", status="done", analysis=analysis)
    ])
    assert package["totals"]["total_posted_credits"] == 100.0
    assert package["totals"]["revenue_classified_total"] == 0.0
    assert package["totals"]["revenue_reconciliation_delta"] == -100.0
    assert not package["totals"]["revenue_reconciles"]
    assert package["totals"]["decision"] == "review_required"


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
            "authoritative": True,
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
    assert confirmed_record["revenue_classification"] == "verified_revenue"
    assert confirmed_record["revenue_review_status"] == "confirmed"
    assert confirmed_metrics["verified_revenue_total"] == 441.0
    assert confirmed_metrics["unverified_deposit_total"] == 0.0
    assert confirmed_metrics["revenue_reconciles"]
    assert confirmed_metrics["withholding_denominator"] == 441.0

    package = client.get(f"/package_analysis?ids={job.id}").get_json()
    assert package["totals"]["verified_revenue_total"] == 441.0
    assert package["totals"]["unverified_deposit_count"] == 0
    assert len(package["verified_revenue_evidence"]) == 1
    assert package["unverified_deposit_evidence"] == []

    downloaded = client.get(f"/download/{job.id}/json").get_json()
    assert downloaded["statement"]["transactions"][0]["classification"][
        "revenue_review_status"
    ] == "confirmed"
    csv_body = client.get(f"/download/{job.id}/csv").get_data(as_text=True)
    assert "revenue_classification" in csv_body
    assert "verified_revenue" in csv_body

    rejected = client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "transaction:1", "decision": "reject"},
    ).get_json()["analysis"]
    assert rejected["metrics"]["verified_revenue_total"] == 0.0
    assert rejected["metrics"]["non_revenue_total"] == 441.0
    assert rejected["statement"]["transactions"][0]["classification"][
        "revenue_review_status"
    ] == "rejected"

    reset = client.post(
        f"/analysis/{job.id}/revenue-review",
        json={"source_location": "transaction:1", "decision": "reset"},
    ).get_json()["analysis"]
    assert reset["metrics"]["unverified_deposit_total"] == 441.0
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
    assert "Verified Revenue" in html
    assert "Unverified Deposits" in html
    assert "Revenue Upper Bound" in javascript
    assert "Upper-bound estimate: verified revenue plus unverified deposits" in javascript
    assert "Confirmed operating revenue" in javascript
    assert "Deposits requiring analyst review" in javascript
    assert "Excluded from revenue analysis" in javascript
    assert "Confirm Revenue" in javascript
    assert "Mark Non-Revenue" in javascript
    assert "Generic deposit with insufficient source information." in javascript
    assert 'REV: ["◐", "Revenue"]' in javascript
    assert 'REVIEW: ["◐", "Review"]' in javascript
    assert "data-running-balance-column" in html
    assert "showRunningBalance" in javascript
    assert "Transaction Count" in html
    assert "Credit Count" not in html
    assert "Maximum Revenue" not in javascript
    assert "Potential Revenue" not in html
    assert "Potential Revenue" not in javascript
    assert "SKIPTHEDISHES" not in javascript
    assert "MOBILE DEPOSIT" not in javascript

"""One JSON contract for CLI, web, downloads, and package aggregation."""
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
)
from .revenue import rebuild_serialized_revenue_views

if TYPE_CHECKING:
    from .pipeline import Report
    from .schema import Transaction


def _transaction_dict(
    transaction: Transaction,
    classification: TransactionClassification,
) -> dict:
    return {
        **transaction.model_dump(),
        "classification": asdict(classification),
    }


def _funder_dict(match) -> dict:
    is_potential = match.classification == "potential_lender"
    potential_evidence = [
        evidence
        for evidence in match.evidence
        if evidence.contributes_to_potential_lender_totals
    ]
    debit_count = len(potential_evidence) if is_potential and potential_evidence else match.debit_count
    total_debited = (
        round(sum(abs(evidence.amount) for evidence in potential_evidence), 2)
        if is_potential and potential_evidence
        else match.total_debited
    )
    potential_exposure = match.potential_withholding_exposure
    if is_potential and match.eligible_deposit_denominator is not None:
        potential_exposure = (
            abs(total_debited) / match.eligible_deposit_denominator * 100
            if match.eligible_deposit_denominator > 0
            else None
        )
    return {
        "funder": match.funder,
        "matched_alias": match.matched_alias,
        "classification": match.classification,
        "debit_count": debit_count,
        "total_debited": total_debited,
        "potential_lender_debit_count": (
            debit_count if is_potential else 0
        ),
        "potential_lender_debit_total": (
            total_debited if is_potential else 0.0
        ),
        "eligible_deposit_denominator": match.eligible_deposit_denominator,
        "potential_withholding_exposure": potential_exposure,
        "potential_withholding_formula": match.potential_withholding_formula,
        "review_required": match.review_required,
        "status": match.status,
        "transactions": [
            _transaction_dict(transaction, evidence)
            for transaction, evidence in zip(match.transactions, match.evidence)
        ],
        "evidence": [asdict(evidence) for evidence in match.evidence],
    }


def _insurance_dict(match) -> dict:
    return {
        "provider": match.provider,
        "matched_alias": match.matched_alias,
        "count": match.count,
        "total_debited": match.total_debited,
        "transactions": [
            _transaction_dict(transaction, evidence)
            for transaction, evidence in zip(match.transactions, match.evidence)
        ],
        "evidence": [asdict(evidence) for evidence in match.evidence],
    }


def _recurring_dict(item) -> dict:
    return {
        "description_key": item.description_key,
        "amount": item.amount,
        "count": item.count,
        "cadence": item.cadence,
        "avg_gap_days": item.avg_gap_days,
        "transactions": [
            _transaction_dict(transaction, evidence)
            for transaction, evidence in zip(item.transactions, item.evidence)
        ],
        "evidence": [asdict(evidence) for evidence in item.evidence],
    }


def _metrics_dict(metrics) -> dict:
    """Serialize one public ADB value and fail closed on rejected ledgers."""
    data = asdict(metrics)
    adb = data.get("adb")
    validated = (
        data.get("adb_ok") is True
        and data.get("average_daily_balance") is not None
    )
    if not validated:
        data["average_daily_balance"] = None
        data["daily_balance_sum"] = None
    if isinstance(adb, dict):
        # `metrics.average_daily_balance` is the sole public ADB field. The
        # nested object carries validation evidence, not a second value.
        adb.pop("average_daily_balance", None)
        adb["ok"] = validated
        if not validated:
            # Candidate working remains available on the in-process result for
            # forensic review, but rejected numbers are never API/export data.
            adb["daily_balance_sum"] = None
            adb["daily_balances"] = []
    return data


def _withhold_untrusted_generic_values(payload: dict, *, reason: str) -> dict:
    """Keep validation evidence while removing every untrusted public value."""
    statement = payload.get("statement") or {}
    for key in (
        "beginning_balance",
        "ending_balance",
        "days_in_period",
        "stated_total_credits",
        "stated_total_debits",
        "stated_credit_count",
        "stated_debit_count",
        "stated_average_balance",
        "stated_service_charge",
        "stated_interest_paid",
        "stated_nsf_count",
    ):
        statement[key] = None
    statement["stated_daily_balances"] = []
    statement["transactions"] = []

    metrics = payload.get("metrics") or {}
    for key, value in list(metrics.items()):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[key] = None
        elif isinstance(value, list) and key.endswith("_evidence"):
            metrics[key] = []
    metrics["adb_ok"] = False
    metrics["revenue_reconciles"] = False
    metrics["revenue_review_required"] = True
    metrics["withholding_review_required"] = True
    metrics["potential_withholding_review_required"] = True
    metrics["authoritative"] = False
    metrics["unavailable_reason"] = reason
    if isinstance(metrics.get("adb"), dict):
        adb = metrics["adb"]
        for key, value in list(adb.items()):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                adb[key] = None
        adb["ok"] = False
        adb["reconciled"] = False
        adb["daily_balance_sum"] = None
        adb["daily_balances"] = []
        if isinstance(adb.get("validations"), dict):
            adb["validations"] = {
                key: False for key in adb["validations"]
            }

    detection = payload.get("detection") or {}
    for key, value in list(detection.items()):
        if isinstance(value, list):
            detection[key] = []
    payload["classifications"] = []
    return payload


def report_unavailable_reason(report: Report) -> str | None:
    """Return why report financial values must not cross the public boundary."""
    if report.statement.account_selection_status == "ambiguous":
        return "ambiguous_account_selection"
    if report.source_validation.method != "generic_ocr_text_grounding":
        return None
    if not report.source_validation.ok:
        return "generic_source_grounding_failed"
    if not report.reconciliation.ok:
        return "generic_financial_reconciliation_failed"
    if report.quality.corporate_use != "approved":
        return "generic_validation_failed"
    return None


def report_to_dict(report: Report) -> dict:
    records = report.classifications or classify_statement_transactions(report.statement)
    if len(records) != len(report.statement.transactions):
        raise ValueError("classification count must equal transaction count")

    statement = report.statement.model_dump()
    # A printed ending balance remains reconciliation evidence, but it is not a
    # reportable metric when neither the detailed ledger nor the bank's own
    # summary identity supports it. The reconciliation object retains the source
    # value and computed value for forensic review.
    closing_balance_valid = (
        report.reconciliation.ok
        or report.reconciliation.summary_ok is True
    )
    if not closing_balance_valid:
        statement["ending_balance"] = None
    statement["transactions"] = [
        _transaction_dict(transaction, classification)
        for transaction, classification in zip(report.statement.transactions, records)
    ]
    detection = report.detection
    extraction_attempts = [asdict(attempt) for attempt in report.extraction_attempts]
    estimated_costs = [
        attempt["estimated_cost_usd"]
        for attempt in extraction_attempts
        if attempt.get("estimated_cost_usd") is not None
    ]
    payload = {
        "statement": statement,
        "classifications": [asdict(record) for record in records],
        "reconciliation": asdict(report.reconciliation),
        "metrics": _metrics_dict(report.metrics),
        "detection": {
            "known_funders": [_funder_dict(match) for match in detection.known_funders],
            "potential_lenders": [_funder_dict(match) for match in detection.potential_lenders],
            "insurance_providers": [_insurance_dict(match) for match in detection.insurance_providers],
            "recurring_debits": [_recurring_dict(item) for item in detection.recurring_debits],
            "lender_evidence": [asdict(item) for item in detection.lender_evidence],
            "potential_lender_evidence": [
                asdict(item) for item in detection.potential_lender_evidence
            ],
            "insurance_evidence": [asdict(item) for item in detection.insurance_evidence],
            "verified_revenue_evidence": [
                asdict(item) for item in detection.verified_revenue_evidence
            ],
            "unverified_deposit_evidence": [
                asdict(item) for item in detection.unverified_deposit_evidence
            ],
            "non_revenue_evidence": [
                asdict(item) for item in detection.non_revenue_evidence
            ],
            "true_revenue_evidence": [
                asdict(item) for item in detection.verified_revenue_evidence
            ],
            "potential_revenue_evidence": [
                asdict(item) for item in detection.unverified_deposit_evidence
            ],
            "manual_review": [asdict(item) for item in detection.manual_review],
        },
        "quality": asdict(report.quality),
        "integrity": asdict(report.integrity),
        "source_validation": asdict(report.source_validation),
        "model_used": report.model_used,
        "escalated": report.escalated,
        "extraction": {
            "attempt_count": len(extraction_attempts),
            "attempts": extraction_attempts,
            "estimated_cost_usd": round(sum(estimated_costs), 8),
            "cost_complete": len(estimated_costs) == len(extraction_attempts),
        },
    }
    payload = rebuild_serialized_revenue_views(payload)
    unavailable_reason = report_unavailable_reason(report)
    if unavailable_reason is not None:
        payload = _withhold_untrusted_generic_values(
            payload,
            reason=unavailable_reason,
        )
    else:
        payload["metrics"]["authoritative"] = True
        payload["metrics"]["unavailable_reason"] = None
    return payload

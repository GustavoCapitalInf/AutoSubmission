"""One JSON contract for CLI, web, downloads, and package aggregation."""
from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
)

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
    return {
        "funder": match.funder,
        "matched_alias": match.matched_alias,
        "classification": match.classification,
        "total_debited": match.total_debited,
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


def report_to_dict(report: Report) -> dict:
    records = report.classifications or classify_statement_transactions(report.statement)
    if len(records) != len(report.statement.transactions):
        raise ValueError("classification count must equal transaction count")

    statement = report.statement.model_dump()
    statement["transactions"] = [
        _transaction_dict(transaction, classification)
        for transaction, classification in zip(report.statement.transactions, records)
    ]
    detection = report.detection
    return {
        "statement": statement,
        "classifications": [asdict(record) for record in records],
        "reconciliation": asdict(report.reconciliation),
        "metrics": asdict(report.metrics),
        "detection": {
            "known_funders": [_funder_dict(match) for match in detection.known_funders],
            "potential_lenders": [_funder_dict(match) for match in detection.potential_lenders],
            "insurance_providers": [_insurance_dict(match) for match in detection.insurance_providers],
            "recurring_debits": [_recurring_dict(item) for item in detection.recurring_debits],
            "lender_evidence": [asdict(item) for item in detection.lender_evidence],
            "insurance_evidence": [asdict(item) for item in detection.insurance_evidence],
            "manual_review": [asdict(item) for item in detection.manual_review],
        },
        "quality": asdict(report.quality),
        "integrity": asdict(report.integrity),
        "model_used": report.model_used,
        "escalated": report.escalated,
    }

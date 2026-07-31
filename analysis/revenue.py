"""Shared revenue states and serialized reviewer operations."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal


RevenueState = Literal["true_revenue", "potential_revenue", "non_revenue"]
REVENUE_STATES: tuple[RevenueState, ...] = (
    "true_revenue",
    "potential_revenue",
    "non_revenue",
)
WITHHOLDING_DENOMINATOR_MODES = (
    "legacy_eligible_deposits",
    "confirmed_true_revenue",
)


def revenue_contribution_flags(state: RevenueState | None) -> dict[str, bool]:
    return {
        "contributes_to_true_revenue": state == "true_revenue",
        "contributes_to_potential_revenue": state == "potential_revenue",
        "contributes_to_non_revenue": state == "non_revenue",
    }


def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def rebuild_serialized_revenue_views(analysis: dict) -> dict:
    """Rebuild every serialized revenue view from transaction records in place."""
    statement = analysis.setdefault("statement", {})
    transactions = statement.get("transactions") or []
    evidence: dict[str, list[dict]] = {state: [] for state in REVENUE_STATES}
    totals: dict[str, float] = {state: 0.0 for state in REVENUE_STATES}
    counts: dict[str, int] = {state: 0 for state in REVENUE_STATES}
    posted_total = 0.0
    posted_count = 0
    serialized_records: list[dict] = []

    for transaction in transactions:
        amount = _number(transaction.get("amount"))
        record = transaction.get("classification")
        if not isinstance(record, dict):
            if amount > 0:
                raise ValueError(
                    "every posted credit must have an authoritative classification record"
                )
            continue
        if amount <= 0 or record.get("is_posted") is False:
            serialized_records.append(deepcopy(record))
            continue
        posted_total += amount
        posted_count += 1
        state = record.get("revenue_classification")
        if state not in REVENUE_STATES:
            raise ValueError("every posted credit must have a valid revenue classification")
        flags = revenue_contribution_flags(state)
        record.update(flags)
        serialized_records.append(deepcopy(record))
        totals[state] += amount
        counts[state] += 1
        evidence[state].append(deepcopy(record))

    posted_total = round(posted_total, 2)
    for state in REVENUE_STATES:
        totals[state] = round(totals[state], 2)
    classified_total = round(sum(totals.values()), 2)
    classified_count = sum(counts.values())
    delta = round(classified_total - posted_total, 2)

    metrics = analysis.setdefault("metrics", {})
    metrics.update({
        "total_posted_credits": posted_total,
        "total_posted_credit_count": posted_count,
        "true_revenue": totals["true_revenue"],
        "confirmed_true_revenue": totals["true_revenue"],
        "confirmed_true_revenue_total": totals["true_revenue"],
        "confirmed_true_revenue_count": counts["true_revenue"],
        "potential_revenue_total": totals["potential_revenue"],
        "potential_revenue_count": counts["potential_revenue"],
        "non_revenue_total": totals["non_revenue"],
        "non_revenue_count": counts["non_revenue"],
        "maximum_revenue": round(
            totals["true_revenue"] + totals["potential_revenue"], 2
        ),
        "revenue_classified_total": classified_total,
        "revenue_classified_count": classified_count,
        "revenue_reconciliation_delta": delta,
        "revenue_reconciles": delta == 0.0 and classified_count == posted_count,
        "revenue_review_required": counts["potential_revenue"] > 0,
        "true_revenue_evidence": evidence["true_revenue"],
        "potential_revenue_evidence": evidence["potential_revenue"],
        "non_revenue_evidence": evidence["non_revenue"],
    })

    if metrics.get("withholding_denominator_mode") == "confirmed_true_revenue":
        denominator = totals["true_revenue"]
        metrics["eligible_deposits"] = denominator
        metrics["withholding_denominator"] = denominator
        metrics["potential_withholding_denominator"] = denominator
        metrics["eligible_deposit_definition"] = "confirmed classified true revenue"
        numerator = _number(metrics.get("withholding_numerator"))
        potential_numerator = _number(metrics.get("potential_withholding_numerator"))
        metrics["withholding_rate"] = (
            abs(numerator) / denominator * 100 if denominator > 0 else None
        )
        metrics["potential_withholding_exposure"] = (
            abs(potential_numerator) / denominator * 100 if denominator > 0 else None
        )
        metrics["withholding_review_required"] = denominator <= 0

    detection = analysis.setdefault("detection", {})
    detection["true_revenue_evidence"] = evidence["true_revenue"]
    detection["potential_revenue_evidence"] = evidence["potential_revenue"]
    detection["non_revenue_evidence"] = evidence["non_revenue"]
    detection["manual_review"] = [
        deepcopy(record)
        for record in serialized_records
        if record.get("review_required") or record.get("revenue_review_required")
    ]
    analysis["classifications"] = [
        deepcopy(transaction["classification"])
        for transaction in transactions
        if isinstance(transaction.get("classification"), dict)
    ]
    return analysis


def apply_serialized_revenue_review(
    analysis: dict,
    *,
    source_location: str,
    decision: Literal["confirm", "reject", "reset"],
) -> dict:
    """Apply a human decision to one potential credit and rebuild all views."""
    if decision not in {"confirm", "reject", "reset"}:
        raise ValueError("decision must be confirm, reject, or reset")
    transactions = (analysis.get("statement") or {}).get("transactions") or []
    target = next(
        (
            transaction
            for transaction in transactions
            if (transaction.get("classification") or {}).get("source_location")
            == source_location
        ),
        None,
    )
    if target is None:
        raise LookupError("transaction source location was not found")
    record = target.get("classification") or {}
    initial_state = record.get("revenue_initial_classification")
    if initial_state != "potential_revenue":
        raise ValueError("only automatically potential revenue can be reviewed")

    if decision == "confirm":
        state: RevenueState = "true_revenue"
        status = "confirmed"
        note = "Reviewer confirmed this credit as operating revenue."
    elif decision == "reject":
        state = "non_revenue"
        status = "rejected"
        note = "Reviewer rejected this credit as operating revenue."
    else:
        state = "potential_revenue"
        status = "pending"
        note = None

    record["revenue_classification"] = state
    record["revenue_review_required"] = state == "potential_revenue"
    record["revenue_review_status"] = status
    record["revenue_review_note"] = note
    record["revenue_reviewed_at"] = (
        None if decision == "reset" else datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state))
    return rebuild_serialized_revenue_views(analysis)

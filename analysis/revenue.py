"""Shared revenue states and serialized reviewer operations."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal

from .payload_shape import DOCUMENT_SHAPE, assert_payload_shape, payload_accounts

#: Named once: it reaches a refusal message, and a surface that names itself
#: two ways is two surfaces to a reader of the message.
_REVENUE_SURFACE = "analysis/revenue.py::rebuild_serialized_revenue_views"


RevenueState = Literal["verified_revenue", "unverified_deposit", "non_revenue"]
REVENUE_STATES: tuple[RevenueState, ...] = (
    "verified_revenue",
    "unverified_deposit",
    "non_revenue",
)
WITHHOLDING_DENOMINATOR_MODES = (
    "legacy_eligible_deposits",
    "verified_revenue",
)
LEGACY_REVENUE_STATE_MAP = {
    "true_revenue": "verified_revenue",
    "potential_revenue": "unverified_deposit",
}
LEGACY_WITHHOLDING_DENOMINATOR_MODES = {
    "confirmed_true_revenue": "verified_revenue",
}


def normalize_withholding_denominator_mode(value: object) -> str:
    mode = str(value or "legacy_eligible_deposits")
    mode = LEGACY_WITHHOLDING_DENOMINATOR_MODES.get(mode, mode)
    return mode if mode in WITHHOLDING_DENOMINATOR_MODES else "legacy_eligible_deposits"


def revenue_contribution_flags(state: RevenueState | None) -> dict[str, bool]:
    return {
        "contributes_to_verified_revenue": state == "verified_revenue",
        "contributes_to_unverified_deposit": state == "unverified_deposit",
        "contributes_to_non_revenue": state == "non_revenue",
        # Deprecated aliases remain serialized for existing API consumers. They
        # are derived from the canonical state and are never scanned separately.
        "contributes_to_true_revenue": state == "verified_revenue",
        "contributes_to_potential_revenue": state == "unverified_deposit",
    }


def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def rebuild_serialized_revenue_views(analysis: dict) -> dict:
    """Rebuild every serialized revenue view from transaction records in place.

    Per ACCOUNT, always: revenue is a property of a ledger, and a document's
    accounts each have one. A document payload has its accounts rebuilt in
    printed order and is returned; an account payload is rebuilt exactly as it
    always was, in the same call, with no branch between.

    The head used to be `analysis.setdefault("statement", {})`, and that one
    word was the quiet failure this teaching exists to remove: handed a shape
    it had never seen, this function INSERTED an empty ledger and rebuilt every
    revenue view over it — totals of 0.00, evidence lists emptied,
    `revenue_reconciles` true because nothing failed to reconcile (measured,
    design §1.4). The shape assertion (L1-C16) is what turns that into a
    refusal. It is reached only by a payload that carries neither shape, which
    no publisher in this tree can produce: `report_to_dict` always writes a
    statement.
    """
    shape = assert_payload_shape(analysis, surface=_REVENUE_SURFACE)
    if shape == DOCUMENT_SHAPE:
        for account in payload_accounts(analysis, surface=_REVENUE_SURFACE):
            _rebuild_account_revenue_views(account)
        return analysis
    return _rebuild_account_revenue_views(analysis)


def _rebuild_account_revenue_views(analysis: dict) -> dict:
    """One ACCOUNT's serialized revenue views, rebuilt in place."""
    statement = analysis["statement"]
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
        state = LEGACY_REVENUE_STATE_MAP.get(
            record.get("revenue_classification"),
            record.get("revenue_classification"),
        )
        if state not in REVENUE_STATES:
            raise ValueError("every posted credit must have a valid revenue classification")
        record["revenue_classification"] = state
        initial_state = record.get("revenue_initial_classification")
        record["revenue_initial_classification"] = LEGACY_REVENUE_STATE_MAP.get(
            initial_state,
            initial_state,
        )
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
        "verified_revenue_total": totals["verified_revenue"],
        "verified_revenue_count": counts["verified_revenue"],
        "unverified_deposit_total": totals["unverified_deposit"],
        "unverified_deposit_count": counts["unverified_deposit"],
        "non_revenue_total": totals["non_revenue"],
        "non_revenue_count": counts["non_revenue"],
        "maximum_revenue": round(
            totals["verified_revenue"] + totals["unverified_deposit"], 2
        ),
        "revenue_classified_total": classified_total,
        "revenue_classified_count": classified_count,
        "revenue_reconciliation_delta": delta,
        "revenue_reconciles": delta == 0.0 and classified_count == posted_count,
        "revenue_review_required": counts["unverified_deposit"] > 0,
        "verified_revenue_evidence": evidence["verified_revenue"],
        "unverified_deposit_evidence": evidence["unverified_deposit"],
        "non_revenue_evidence": evidence["non_revenue"],
        # Deprecated aggregate aliases, all derived from canonical records.
        "true_revenue": totals["verified_revenue"],
        "confirmed_true_revenue": totals["verified_revenue"],
        "confirmed_true_revenue_total": totals["verified_revenue"],
        "confirmed_true_revenue_count": counts["verified_revenue"],
        "potential_revenue_total": totals["unverified_deposit"],
        "potential_revenue_count": counts["unverified_deposit"],
        "true_revenue_evidence": evidence["verified_revenue"],
        "potential_revenue_evidence": evidence["unverified_deposit"],
    })

    denominator_mode = normalize_withholding_denominator_mode(
        metrics.get("withholding_denominator_mode")
    )
    metrics["withholding_denominator_mode"] = denominator_mode
    if denominator_mode == "verified_revenue":
        denominator = totals["verified_revenue"]
        metrics["eligible_deposits"] = denominator
        metrics["withholding_denominator"] = denominator
        metrics["potential_withholding_denominator"] = denominator
        metrics["withholding_denominator_label"] = "Verified revenue"
        metrics["eligible_deposit_definition"] = "verified classified revenue"
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
    detection["verified_revenue_evidence"] = evidence["verified_revenue"]
    detection["unverified_deposit_evidence"] = evidence["unverified_deposit"]
    detection["non_revenue_evidence"] = evidence["non_revenue"]
    detection["true_revenue_evidence"] = evidence["verified_revenue"]
    detection["potential_revenue_evidence"] = evidence["unverified_deposit"]
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
    initial_state = LEGACY_REVENUE_STATE_MAP.get(initial_state, initial_state)
    if initial_state != "unverified_deposit":
        raise ValueError("only automatically unverified deposits can be reviewed")

    if decision == "confirm":
        state: RevenueState = "verified_revenue"
        status = "confirmed"
        note = "Reviewer confirmed this credit as operating revenue."
    elif decision == "reject":
        state = "non_revenue"
        status = "rejected"
        note = "Reviewer rejected this credit as operating revenue."
    else:
        state = "unverified_deposit"
        status = "pending"
        note = None

    record["revenue_classification"] = state
    record["revenue_review_required"] = state == "unverified_deposit"
    record["revenue_review_status"] = status
    record["revenue_review_note"] = note
    record["revenue_reviewed_at"] = (
        None if decision == "reset" else datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state))
    return rebuild_serialized_revenue_views(analysis)

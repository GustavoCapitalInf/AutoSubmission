"""Revenue figures as the dashboard presents them (true revenue spec §10.4, §12).

A presentation step, like `analysis/flagged_view.py`: it works on a COPY of a published payload and never refuses. On
every account it sets the two flags the dashboard reads before it prints a revenue figure:

* `verified_revenue_established`: every captured credit carries a revenue state, and the captured credits are the
  money the statement's Total counts (the line items are the Total's source, or they add up to the bank's own total);
  a statement that captured no credit and whose Total is zero took in nothing, and is established at zero;
* `revenue_established`: that, and every posted credit carries a 5.6 tier.

A payload analysed before 5.6 carries no tier. Its served copy nulls True revenue and every tier figure
(`true_revenue`, `true_revenue_total` and the counted and held totals, counts and reasons), nulls every
`true_revenue_evidence`, and drops `contributes_to_true_revenue` from every row, so no reader takes the old
verified meaning of those names for the new one (T9, T10). Its verified figures stay as stored.
"""
from __future__ import annotations

import copy
from collections.abc import Mapping

from analysis.payload_shape import (
    ACCOUNTS_KEY,
    DOCUMENT_SHAPE,
    PayloadShapeError,
    assert_payload_shape,
    payload_accounts,
)
from analysis.revenue import REVENUE_STATES, TIER_DETECTION_KEYS, TIER_METRIC_KEYS

_SURFACE = "analysis/revenue_view.py::apply_revenue_view"


def _number(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def revenue_flags(account: Mapping) -> tuple[bool, bool]:
    """`(verified_revenue_established, revenue_established)` of one account payload (§10.4)."""
    statement = account.get("statement") if isinstance(account.get("statement"), Mapping) else {}
    metrics = account.get("metrics") if isinstance(account.get("metrics"), Mapping) else {}
    rows = [row for row in statement.get("transactions") or [] if isinstance(row, Mapping)]
    positive = [row for row in rows if _number(row.get("amount")) > 0]
    classified = [row for row in positive if isinstance(row.get("classification"), Mapping)]
    posted = [row for row in classified if row["classification"].get("is_posted") is not False]
    states_complete = (
        any(isinstance(row.get("classification"), Mapping) for row in rows)
        and len(classified) == len(positive)
        and all(row["classification"].get("revenue_classification") in REVENUE_STATES for row in posted)
    )
    deposit_total = _number(metrics.get("effective_total_deposits"))
    line_item_total = _number(metrics.get("total_deposits"))
    totals_agree = (
        str(metrics.get("deposits_source") or "line_items") == "line_items"
        or abs(line_item_total - deposit_total) < 0.005
    )
    verified = (states_complete and totals_agree) or (bool(statement) and not positive and deposit_total == 0)
    tiered = all(isinstance(row["classification"].get("revenue_tier"), str) for row in posted)
    return verified, verified and tiered


def _served_account(account: Mapping) -> dict:
    result = dict(account)
    verified, established = revenue_flags(account)
    statement = result.get("statement")
    rows = statement.get("transactions") if isinstance(statement, Mapping) else None
    posted = [
        row["classification"] for row in rows or []
        if isinstance(row, Mapping) and isinstance(row.get("classification"), Mapping)
        and _number(row.get("amount")) > 0 and row["classification"].get("is_posted") is not False
    ]
    tiered = bool(posted) and all(isinstance(record.get("revenue_tier"), str) for record in posted)
    metrics = copy.deepcopy(dict(result.get("metrics") or {}))
    metrics["verified_revenue_established"] = verified
    metrics["revenue_established"] = established and (tiered or not posted)
    if posted and not tiered:
        for key in TIER_METRIC_KEYS:
            metrics[key] = None
        transactions = copy.deepcopy(rows)
        for row in transactions:
            if isinstance(row, dict) and isinstance(row.get("classification"), dict):
                row["classification"].pop("contributes_to_true_revenue", None)
        result["statement"] = {**statement, "transactions": transactions}
        detection = copy.deepcopy(dict(result.get("detection") or {}))
        for key in TIER_DETECTION_KEYS:
            detection[key] = None
        result["detection"] = detection
    result["metrics"] = metrics
    return result


def apply_revenue_view(payload: object) -> object:
    """A copy of a published analysis payload with each account's revenue flags set and, before 5.6, its True
    revenue nulled (§10.4, §12). The input is never mutated; a payload of neither published shape is returned as
    it is."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    if shape == DOCUMENT_SHAPE:
        return {**payload, ACCOUNTS_KEY: [_served_account(account) for account in accounts]}
    return _served_account(payload)

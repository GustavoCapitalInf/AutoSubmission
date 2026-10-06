"""Revenue figures as the dashboard presents them (true revenue spec §10.4, §12).

A presentation step, like `analysis/flagged_view.py`: it works on a COPY of a published payload and never refuses. On
every account it sets the two flags the dashboard reads before it prints a revenue figure:

* `verified_revenue_established`: every captured credit carries a revenue state, and the captured credits are the
  money the statement's Total counts (the line items are the Total's source, or they add up to the bank's own total);
  a statement that captured no credit and whose Total is zero took in nothing, and is established at zero;
* `revenue_established`: that, and every posted credit carries a 5.6 tier.

A payload analysed before 5.6 carries no tier. Its served copy nulls True revenue and every tier figure
(`true_revenue`, `true_revenue_total` and the counted and held totals, counts and reasons), nulls every
`true_revenue_evidence`, and drops `contributes_to_true_revenue` from every copy of a record in the account: the
statement rows and `classifications`, every evidence list in `metrics` and `detection`, `manual_review`, and the known
funder, potential lender, insurer and recurring debit matches. Each of those copies stored the old verified meaning,
so no reader takes it for the new one (T9, T10). Its verified figures stay as stored.
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
from analysis.transaction_classifier import _deposit_return_debit, processor_chargeback_debit

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


#: The record flag 5.6 repointed from verified to True revenue (T9).
_REPOINTED_RECORD_FLAG = "contributes_to_true_revenue"


def _drop_repointed_flag(node: object) -> None:
    """Remove `contributes_to_true_revenue` from every dict under `node`, in place. Only ever called on a copy."""
    if isinstance(node, dict):
        node.pop(_REPOINTED_RECORD_FLAG, None)
        for value in node.values():
            _drop_repointed_flag(value)
    elif isinstance(node, list):
        for value in node:
            _drop_repointed_flag(value)


#: Owner ruling 2026-10-02 (the underwriter's Q6; true revenue spec §6.2's package passes, §9.1; R2-OW15): the two debit
#: flags, in the order a statement's served metrics and a package's totals publish them.
DEBIT_FLAG_KINDS = ("unmatched_deposit_return", "processor_chargeback")
#: The classes whose debit is never a processor's chargeback or adjustment: financing (lender detection's financing
#: groups and the retired lease or equipment financing), a card payment, insurance, tax and payroll.
_NOT_A_PROCESSOR_DEBIT = frozenset({
    "confirmed_lender", "potential_lender", "alternative_position", "line_of_credit", "vehicle_financing", "bank_loan",
    "mortgage", "lease_or_rental", "personal_loan", "floor_plan_financing", "factoring", "debt_relief",
    "lease_or_equipment_financing", "credit_card_payment", "insurance", "tax", "payroll",
})
#: The lender, potential-lender and withholding contributions a processor's chargeback never carries.
_LENDER_CONTRIBUTIONS = (
    "contributes_to_lender_count", "contributes_to_lender_totals", "contributes_to_withholding_rate",
    "contributes_to_potential_lender_count", "contributes_to_potential_lender_totals",
    "contributes_to_potential_withholding_exposure",
)


def _row_location(record: Mapping, position: int) -> str:
    location = record.get("source_location")
    return location if isinstance(location, str) and location else f"transaction:{position + 1}"


def debit_side_flags(transactions: object, *, matched_locations: frozenset[str] | set[str] = frozenset()) -> list[dict]:
    """Owner ruling 2026-10-02 (the underwriter's Q6, "2": "Flag, but do not deduct, returns that cannot be matched and
    processor chargebacks"; audit I42; true revenue spec §6.2's package passes, §9.1, §9.2; R2-OW15): the debits one
    statement's serialized rows flag, in row order, each `{kind, wording (a chargeback only), source_location, date,
    amount, description}`. Never deducted: no figure, tier, gate or lender reading reads a flag.

    * `unmatched_deposit_return`: a posted debit, no duplicate, that undoes a deposit (`_deposit_return_debit`, R2-B08's
      wordings included), that no credit of the statement pairs (no posted credit's `revenue_match_method` is
      `matched_reversal_pair` with its `revenue_related_transaction` on the debit's location) and that is not among
      `matched_locations` (the package's cross-statement matches, `webapp/app.py` `_package_matches`). A correction
      that names an equal credit of its own statement, which the package never nets across, is flagged here.
    * `processor_chargeback`: a posted debit, no duplicate, whose text reads as a processor's chargeback or adjustment
      (`processor_chargeback_debit`: never a fee, never a deposit return), with no lender, potential-lender or
      withholding contribution and a class outside financing, card payments, insurance, tax and payroll. Its
      `wording` is 'chargeback' or 'adjustment'.

    Reads the serialized rows only (a row without a classification record is skipped); the payload is never
    mutated."""
    rows = [(position, row) for position, row in enumerate(transactions if isinstance(transactions, list) else [])
            if isinstance(row, Mapping) and isinstance(row.get("classification"), Mapping)]
    paired = {
        row["classification"].get("revenue_related_transaction")
        for _position, row in rows
        if _number(row.get("amount")) > 0 and row["classification"].get("is_posted") is not False
        and row["classification"].get("revenue_match_method") == "matched_reversal_pair"
    }
    flags: list[dict] = []
    for position, row in rows:
        record = row["classification"]
        if _number(row.get("amount")) >= 0 or record.get("is_posted") is False or record.get("duplicate_of"):
            continue
        location = _row_location(record, position)
        text = str(record.get("normalized_description") or "")
        entry = {"source_location": location, "date": row.get("date"), "amount": row.get("amount"),
                 "description": row.get("description")}
        if _deposit_return_debit(text):
            if location not in paired and location not in matched_locations:
                flags.append({"kind": "unmatched_deposit_return", **entry})
            continue
        if record.get("classification") in _NOT_A_PROCESSOR_DEBIT or any(
                record.get(flag) is True for flag in _LENDER_CONTRIBUTIONS):
            continue
        wording = processor_chargeback_debit(text)
        if wording is not None:
            flags.append({"kind": "processor_chargeback", "wording": wording, **entry})
    return flags


def debit_flag_metrics(flags: list[dict]) -> dict:
    """R2-OW15 (§9.1): a statement's served flag keys, `<kind>_count`, `<kind>_total` (the debits' magnitude) and
    `<kind>_locations`, for each kind `flags` holds; {} when it holds none, so a statement without a flag is served as
    before."""
    metrics: dict = {}
    for kind in DEBIT_FLAG_KINDS:
        entries = [flag for flag in flags if flag["kind"] == kind]
        if entries:
            metrics[f"{kind}_count"] = len(entries)
            metrics[f"{kind}_total"] = round(sum(abs(_number(flag["amount"])) for flag in entries), 2)
            metrics[f"{kind}_locations"] = [flag["source_location"] for flag in entries]
    return metrics


def _served_account(account: Mapping) -> dict:
    verified, established = revenue_flags(account)
    statement = account.get("statement")
    rows = statement.get("transactions") if isinstance(statement, Mapping) else None
    posted = [
        row["classification"] for row in rows or []
        if isinstance(row, Mapping) and isinstance(row.get("classification"), Mapping)
        and _number(row.get("amount")) > 0 and row["classification"].get("is_posted") is not False
    ]
    tiered = bool(posted) and all(isinstance(record.get("revenue_tier"), str) for record in posted)
    if posted and not tiered:
        # Before 5.6 (T10, §12). The old flag sits on every copy of a record the account stored, not only on the
        # statement rows (`classifications`, each evidence list, `manual_review`, the funder, potential lender,
        # insurer and recurring debit matches), so the whole account is copied and the flag dropped from every dict
        # in it. The stored job is never touched.
        result = copy.deepcopy(dict(account))
        _drop_repointed_flag(result)
        metrics = dict(result.get("metrics") or {})
        for key in TIER_METRIC_KEYS:
            metrics[key] = None
        detection = dict(result.get("detection") or {})
        for key in TIER_DETECTION_KEYS:
            detection[key] = None
        result["detection"] = detection
    else:
        result = dict(account)
        metrics = copy.deepcopy(dict(result.get("metrics") or {}))
    metrics["verified_revenue_established"] = verified
    metrics["revenue_established"] = established and (tiered or not posted)
    # Owner ruling 2026-10-02 (the underwriter's Q6; §9.1, R2-OW15): the statement's returns no credit of it pairs and
    # its processor chargebacks and adjustments, flagged, never deducted; the keys only where a debit is flagged.
    metrics.update(debit_flag_metrics(debit_side_flags(rows)))
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

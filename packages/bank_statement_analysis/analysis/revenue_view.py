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

The final review of round 2, F1 (§10.4, §11): an account whose withholding mode divides by a basis that is not
established (True revenue where `revenue_established` is false, Verified revenue where `verified_revenue_established`
is) publishes no rate over it: its served copy nulls `withholding_rate`, `potential_withholding_exposure` and each
potential lender's exposure and basis, sets `withholding_review_required` and publishes `withholding_basis_unestablished`
(only there). The legacy basis is the bank's own deposits and is never touched.

Audit round 3, R3-B24 (R3-16; §9.1, §17.1's default D1): an account whose revenue is established also publishes, only
where one is flagged, the counted credits whose source the statement does not prove that are $10,000 or more and more
than 25% of its True (`large_unsourced_deposits`, with their count and total), for information only: nothing reads them.
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
from analysis.revenue import (
    REVENUE_STATES,
    TIER_DETECTION_KEYS,
    TIER_METRIC_KEYS,
    normalize_withholding_denominator_mode,
)
from analysis.transaction_classifier import _deposit_return_debit, processor_chargeback_debit

_SURFACE = "analysis/revenue_view.py::apply_revenue_view"

#: Audit B11 (I51, §10.4 for the exports): the figures a download leaves empty when an account's revenue is not
#: established (its captured credits are not the money its Total counts, or it was analysed before 5.6): True,
#: Counted, Held and every name that carries them or a part of them. The dashboard already reads them as N/A; a
#: download printed them as numbers beside `revenue_established = False`. Non-revenue stays: its rows are known
#: non-revenue, captured rows only. Audit round 2, R2-B16 (R52): public here, so the CLI (analyze.py, batch.py) and
#: the webapp's downloads (webapp/app.py) read one list.
UNESTABLISHED_REVENUE_KEYS = (
    "true_revenue", "true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
    "excluded_pending_review_total", "excluded_pending_review_count", "counted_flagged_by_reason",
    "excluded_pending_review_by_reason", "revenue_review_items", "unverified_deposit_total",
    "potential_revenue_total", "maximum_revenue",
)
#: ... and when its Verified figure is not established: Verified and its aliases (T9).
UNESTABLISHED_VERIFIED_KEYS = ("verified_revenue_total", "confirmed_true_revenue", "confirmed_true_revenue_total")
#: Audit round 3, R3-B20 (R3-48; §10.4's I51 and R52): the Zelle figures' parts (`zelle_deposits.by_tier`,
#: analysis/zelle_view.py) that are parts of Counted and Held, read as None where the revenue is not established ...
UNESTABLISHED_ZELLE_TIERS = ("counted_flagged", "excluded_pending_review")
#: ... and the part of Verified, where the Verified figure is not.
UNESTABLISHED_VERIFIED_ZELLE_TIERS = ("verified",)
#: The order the Zelle figures list their parts in (zelle_view's, the dashboard's).
_ZELLE_TIER_ORDER = ("verified", "counted_flagged", "excluded_pending_review", "non_revenue")


def unestablished_zelle_figures(figures: object, *, established: bool, verified_established: bool) -> object:
    """Audit round 3, R3-48 (§10.4, I51): Zelle figures (`{counted_as_true_revenue, setting_applied, count, total,
    by_tier}`, and a package's `setting`) as a surface prints them where an account's or a package's revenue is not
    established: `figures` itself when both flags hold or it is no dict; otherwise a copy whose
    UNESTABLISHED_ZELLE_TIERS slots (where `established` is false) and UNESTABLISHED_VERIFIED_ZELLE_TIERS slot (where
    `verified_established` is false) read `{"count": None, "total": None}`, present or not, so no reader takes a
    missing slot for a firm zero.
    It keeps what the captured rows say: `count` and `total` (the captured Zelle rows, as `total_posted_credits` is
    kept), the `non_revenue` slot (as Non-revenue is kept), `counted_as_true_revenue`, `setting_applied` and `setting`.
    The input is never mutated."""
    if not isinstance(figures, Mapping) or (established and verified_established):
        return figures
    nulled = (UNESTABLISHED_ZELLE_TIERS if not established else ()) + (
        UNESTABLISHED_VERIFIED_ZELLE_TIERS if not verified_established else ())
    by_tier = figures.get("by_tier") if isinstance(figures.get("by_tier"), Mapping) else {}
    slots = {tier: copy.deepcopy(slot) for tier, slot in by_tier.items()}
    slots.update({tier: {"count": None, "total": None} for tier in nulled})
    order = {tier: position for position, tier in enumerate(_ZELLE_TIER_ORDER)}
    return {**figures, "by_tier": dict(sorted(slots.items(), key=lambda item: (order.get(item[0], len(order)),
                                                                              item[0])))}


#: The final review of round 2, F1 (§10.4, §11; the owner's ruling of 2026-10-02 on the underwriter's Q7, R2-OW14, beside
#: B11's I51 and the final review's M10): where the basis an account's withholding mode divides by is not established
#: (`withholding_basis_unestablished`), the served copy publishes no rate over it: these are None, its
#: `withholding_review_required` is set and the flag `withholding_basis_unestablished` is published (only there).
UNESTABLISHED_WITHHOLDING_KEYS = ("withholding_rate", "potential_withholding_exposure")
#: ... and a download (and the CLI) leaves the basis itself empty. The served copy keeps these figures: the package
#: sums its members' and refuses its own rate on them (M10); the dashboard reads the flag and prints N/A.
UNESTABLISHED_WITHHOLDING_BASIS_KEYS = ("eligible_deposits", "withholding_denominator", "potential_withholding_denominator")
#: The served flag, published only where it is set.
WITHHOLDING_BASIS_UNESTABLISHED = "withholding_basis_unestablished"


def withholding_basis_unestablished(mode: object, *, verified_established: bool, established: bool) -> bool:
    """F1 (final review of round 2): whether the basis withholding `mode` divides by is not established: True revenue
    where the revenue is not (`revenue_established` false), Verified revenue where the Verified figure is not
    (`verified_revenue_established` false). The legacy basis is the bank's own deposits less lender funding and is
    always established; a stored payload with no mode was analysed on it (normalize_withholding_denominator_mode)."""
    basis = normalize_withholding_denominator_mode(mode)
    return (basis == "true_revenue" and not established) or (basis == "verified_revenue" and not verified_established)


def _unestablished_potential_lender(match: object) -> object:
    """A potential lender's detection entry with no exposure and no basis (F1): its row divides by the basis, which the
    dashboard would otherwise recompute the exposure from."""
    if not isinstance(match, Mapping):
        return match
    return {**match, "potential_withholding_exposure": None, "eligible_deposit_denominator": None}


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
      `matched_locations` (the package's cross-statement matches, `analysis/package/passes.py` `package_matches`). A
      correction that names an equal credit of its own statement, which the package never nets across, is flagged here.
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


#: Audit round 3, R3-B24 (R3-16; true revenue spec §9.1, §17.1's default D1; standard G7, "Large one-off or unexplained
#: deposits: COUNT+FLAG, and source them when large", and P22, "count + flag + source"): a counted credit whose source
#: the statement does not prove is flagged, for information only, when it is this many dollars or more ...
LARGE_UNSOURCED_DEPOSIT_FLOOR = 10_000
#: ... and strictly more than this percent of its statement's True revenue ...
LARGE_UNSOURCED_DEPOSIT_SHARE = 25
#: ... on these counted reasons, the ones that name no proven source (the owner's Q2 to Q6 and OQ3 of 2026-09-28
#: count them, never Verified): a bare, cash or branch deposit, a check deposit, a named sender's wire, a one-off or
#: unlabelled payer, a numbered company, a person-to-person rail, payer text not read. A classified counted reason (a
#: builder's draw, an insurer paying for work, a lessor's rent and the like) is outside (§17.1's alternative (b)).
LARGE_UNSOURCED_DEPOSIT_REASONS = frozenset({
    "no_payer_printed", "check_deposit", "wire_named_sender", "named_payer_one_off", "numbered_company_payer", "p2p",
    "named_payer_unlabelled", "payer_text_not_read",
})
#: The fields of one flagged credit, in order (the served list's, the downloads' sections').
LARGE_UNSOURCED_DEPOSIT_FIELDS = (
    "source_location", "date", "description", "amount", "revenue_tier_reason", "share_of_true_percent",
)


def large_unsourced_deposits(transactions: object, true_total: object) -> list[dict]:
    """Audit round 3, R3-B24 (R3-16; §9.1, §9.2, §17.1's default D1): the credits of serialized rows `transactions` that
    are large and unsourced, in row order, each `{source_location, date, description, amount, revenue_tier_reason,
    share_of_true_percent}`: a row with a classification record, an amount above 0, `is_posted` not False and no
    `duplicate_of`, in the counted tier (`counted_flagged`) for one of LARGE_UNSOURCED_DEPOSIT_REASONS, whose amount is
    LARGE_UNSOURCED_DEPOSIT_FLOOR dollars or more and strictly more than LARGE_UNSOURCED_DEPOSIT_SHARE percent of
    `true_total` (the statement's True revenue; read in integer cents, nothing where it is not above 0). Its share is
    `round(amount / true_total * 100, 1)`.

    Information only: no tier, reason, True or Verified figure, review gate, badge or decision reads it. A Verified,
    held or non-revenue credit is never flagged, so a deposit the reviewer confirmed (Verified) drops out. The rows are
    read, never mutated."""
    try:
        true_cents = round(float(true_total) * 100) if true_total is not None else 0
    except (TypeError, ValueError):
        true_cents = 0
    if true_cents <= 0 or not isinstance(transactions, list):
        return []
    flags: list[dict] = []
    for position, row in enumerate(transactions):
        if not isinstance(row, Mapping) or not isinstance(row.get("classification"), Mapping):
            continue
        record = row["classification"]
        amount = _number(row.get("amount"))
        if amount <= 0 or record.get("is_posted") is False or record.get("duplicate_of"):
            continue
        if (record.get("revenue_tier") != "counted_flagged"
                or record.get("revenue_tier_reason") not in LARGE_UNSOURCED_DEPOSIT_REASONS):
            continue
        amount_cents = round(amount * 100)
        if (amount_cents < LARGE_UNSOURCED_DEPOSIT_FLOOR * 100
                or amount_cents * 100 <= LARGE_UNSOURCED_DEPOSIT_SHARE * true_cents):
            continue
        flags.append({
            "source_location": _row_location(record, position), "date": row.get("date"),
            "description": row.get("description"), "amount": row.get("amount"),
            "revenue_tier_reason": record.get("revenue_tier_reason"),
            "share_of_true_percent": round(amount / float(true_total) * 100, 1),
        })
    return flags


def large_unsourced_deposit_metrics(flags: list[dict]) -> dict:
    """R3-B24 (R3-16; §9.1): a statement's served keys for its flagged credits, `large_unsourced_deposit_count`,
    `large_unsourced_deposit_total` and the list `large_unsourced_deposits`; {} when none is flagged, so a statement
    without one is served as before."""
    if not flags:
        return {}
    return {
        "large_unsourced_deposit_count": len(flags),
        "large_unsourced_deposit_total": round(sum(_number(flag["amount"]) for flag in flags), 2),
        "large_unsourced_deposits": flags,
    }


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
    # Audit round 3, R3-B24 (R3-16; §9.1, §17.1's default D1; standard G7, P22): the counted credits whose source the
    # statement does not prove that are large beside its True, flagged for information only, never stored; the keys
    # only where one is flagged on a statement whose revenue is established, read in the reading served (the Zelle
    # view runs first, so a Zelle deposit counted under Yes can be flagged and the one excluded under No cannot).
    if metrics["revenue_established"] is True and tiered:
        metrics.update(large_unsourced_deposit_metrics(
            large_unsourced_deposits(rows, metrics.get("true_revenue_total"))))
    # The final review of round 2, F1 (§10.4, §11; M10 on the statement): no rate over a basis that is not
    # established. The statement asks for review, and each potential lender's row loses its exposure and its basis.
    if withholding_basis_unestablished(metrics.get("withholding_denominator_mode"), verified_established=verified,
                                       established=metrics["revenue_established"]):
        metrics.update({key: None for key in UNESTABLISHED_WITHHOLDING_KEYS})
        metrics["withholding_review_required"] = True
        metrics[WITHHOLDING_BASIS_UNESTABLISHED] = True
        detection = result.get("detection")
        if isinstance(detection, Mapping) and isinstance(detection.get("potential_lenders"), list):
            result["detection"] = {
                **detection,
                "potential_lenders": [_unestablished_potential_lender(match) for match in detection["potential_lenders"]],
            }
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

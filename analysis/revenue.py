"""Shared revenue states and serialized reviewer operations."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal

from .payload_shape import DOCUMENT_SHAPE, assert_payload_shape, payload_accounts

#: Named once: it reaches a refusal message, and a surface that names itself
#: two ways is two surfaces to a reader of the message.
_REVENUE_SURFACE = "analysis/revenue.py::rebuild_serialized_revenue_views"
_REVIEW_SURFACE = "analysis/revenue.py::apply_serialized_revenue_review"


RevenueState = Literal["verified_revenue", "unverified_deposit", "non_revenue"]
REVENUE_STATES: tuple[RevenueState, ...] = (
    "verified_revenue",
    "unverified_deposit",
    "non_revenue",
)
#: 5.6 (true revenue spec §5.3): every posted credit carries exactly one tier. `verified` goes with the state
#: verified_revenue, `non_revenue` with non_revenue, and the two middle tiers with unverified_deposit.
RevenueTier = Literal["verified", "counted_flagged", "excluded_pending_review", "non_revenue"]
REVENUE_TIERS: tuple[RevenueTier, ...] = ("verified", "counted_flagged", "excluded_pending_review", "non_revenue")
STATE_OF_TIER: dict[str, RevenueState] = {
    "verified": "verified_revenue",
    "counted_flagged": "unverified_deposit",
    "excluded_pending_review": "unverified_deposit",
    "non_revenue": "non_revenue",
}
#: 5.6 (§5.3): the reason codes of the counted and held tiers: code -> (tier, the label on screen). Nothing else lists
#: them; the dashboard mirrors them (webapp/static/app.js REVENUE_TIER_REASONS). Since the owner's rulings of
#: 2026-10-02 the non_revenue codes end the table (NON_REVENUE_REASONS): the underwriter's Q3's zelle_excluded, then
#: Q12's display reason, government_no_purpose (R2-OW03), then Q11's asset_sale_proceeds (R2-OW06).
REVENUE_TIER_REASONS: dict[str, tuple[RevenueTier, str]] = {
    "direction_conflict": ("excluded_pending_review", "Direction conflicts with the amount"),
    "insurer_payer": ("excluded_pending_review", "Insurance carrier"),
    "insurer_named_payer": ("excluded_pending_review", "Payer name reads as an insurer"),
    "possible_return": ("excluded_pending_review", "Possible return or adjustment"),
    "financing_named_payer": ("excluded_pending_review", "Payer or entry suggests financing"),
    # Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's payout that is a large one-off lump sum, held
    # until sourced (true_revenue.CUSTOMER_FINANCING_LUMP_SUM).
    "customer_financing_lump_sum": (
        "excluded_pending_review", "One-off lump sum from a lease-to-own or patient financier",
    ),
    # Audit round 2, R2-B07 (R07): a credit the parser marked unread whose run of payer blocks prints a lender's or a
    # lending bank's block (true_revenue.UNREAD_RUN_NAMES_FINANCING).
    "unread_run_names_financing": (
        "excluded_pending_review", "A lender is printed among this credit's unread payer blocks",
    ),
    "payer_debited_as_lender": ("excluded_pending_review", "Payer is also debited as a lender"),
    "holder_name": ("excluded_pending_review", "From the holder's own name or brand"),
    "payroll_or_salary": ("excluded_pending_review", "Payroll, salary or employee reimbursement"),
    "personal_income": ("excluded_pending_review", "Benefit or pension"),
    "non_sale_purpose": (
        "excluded_pending_review", "Not a sale: owner money, investment, grant, refund, claim or interest",
    ),
    "payer_also_debited": ("excluded_pending_review", "Payer also debited this account"),
    "wire_no_sender": ("excluded_pending_review", "Wire, no sender printed"),
    "transfer_no_counterparty": ("excluded_pending_review", "Transfer, no counterparty"),
    "transfer_account_designation": ("excluded_pending_review", "Transfer naming an account"),
    "p2p_round_repeat": ("excluded_pending_review", "Repeated round sums from one sender"),
    "wire_named_sender": ("counted_flagged", "Wire from a named sender"),
    "check_deposit": ("counted_flagged", "Check deposit"),
    "no_payer_printed": ("counted_flagged", "No payer printed"),
    # Audit B10 (I05, I60): the statement printed a payer the parser did not read (true_revenue.PAYER_TEXT_NOT_READ).
    "payer_text_not_read": ("counted_flagged", "Payer text not read"),
    "p2p": ("counted_flagged", "Person-to-person"),
    "factoring_payout": ("counted_flagged", "Factoring payout"),
    # Owner ruling 2026-10-02 (the underwriter's Q9, part (c)), R2-OW05: a lender paying the business for its services
    # (a listed auto lender's payables on a statement with no dealer evidence: a repossession agency's recoveries),
    # counted, never verified (true_revenue.LENDER_PAID_FOR_SERVICES).
    "lender_paid_for_services": ("counted_flagged", "Lender paid for services"),
    # Owner ruling 2026-10-02 (the underwriter's Q11 (a)), R2-OW06: a builder's progress draw, counted and flagged, never
    # verified (true_revenue.CONSTRUCTION_PROGRESS_DRAW_REASON).
    "construction_progress_draw": ("counted_flagged", "Builder's progress draw"),
    # Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: an insurer paying the business for its work (a holder's
    # trade, a service form, or three or more credits from one insurer within 31 days), counted, never verified
    # (true_revenue.INSURER_FOR_WORK_METHOD).
    "insurer_paid_for_services": ("counted_flagged", "Insurer paid for the business's work"),
    # Audit B11 (I53): the payer's own settlement of the merchant's sales (OQ2's BNPL providers, marketplaces), counted;
    # the label keeps the caution that the payer also lends, and never reads as financing counted in True.
    "payout_credit_entity": ("counted_flagged", "BNPL or marketplace settlement (payer also lends)"),
    # Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's payout to the merchant for a customer's
    # financed purchase, counted, never verified (true_revenue.CUSTOMER_FINANCING_PAYOUT).
    "customer_financing_payout": ("counted_flagged", "Lease-to-own or patient-financing payout"),
    "platform_unconfirmed": ("counted_flagged", "Platform payout, not confirmed"),
    "numbered_company_payer": ("counted_flagged", "Numbered company payer"),
    "named_payer_purpose_refused": ("counted_flagged", "Named payer, purpose not accepted as proof"),
    "named_payer_one_off": ("counted_flagged", "One-off payer"),
    "named_payer_unlabelled": ("counted_flagged", "Payer named, channel not printed"),
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit the Zelle policy excluded
    # (true_revenue.ZELLE_EXCLUDED), the one non_revenue row that carries a reason; a Zelle row another non-revenue
    # rule decided keeps that rule and no reason.
    "zelle_excluded": ("non_revenue", "Zelle deposit (excluded by policy)"),
    # The owner's ruling of 2026-10-02 (the underwriter's Q12), R2-OW03: the display reason of a government payment
    # that prints no purpose (§6.1 step 3a, method government_no_purpose_exclusion), which the non-revenue breakdown
    # names (true_revenue.GOVERNMENT_NO_PURPOSE). Display only: no tier, state, method or flag moves.
    "government_no_purpose": ("non_revenue", "Government payment, no purpose printed"),
    # The owner's ruling of 2026-10-02 (the underwriter's Q11 (b)), R2-OW06: a non-dealer's sale of equipment or
    # vehicles (an equipment auction's or a car buyer's seller payout, a printed truck, trailer, vehicle or equipment
    # sale), non_revenue with this reason (true_revenue.ASSET_SALE_METHOD); no review path.
    "asset_sale_proceeds": ("non_revenue", "Sale of equipment or vehicles (not a dealer)"),
}
#: R2-OW03 (owner ruling 2026-10-02; §5.3, §9.1): the reason codes REVENUE_TIER_REASONS files under non_revenue. A
#: non_revenue row carries one only when an owner ruling decided it (the Zelle policy, Q12's no-purpose government
#: payments, Q11's non-dealer asset sales); every other non_revenue row carries none, and a reviewer's rejection keeps
#: the counted or held reason it had, which is no such code. `non_revenue_by_reason` counts the rows of these codes
#: alone.
NON_REVENUE_REASONS: frozenset[str] = frozenset(
    code for code, (tier, _label) in REVENUE_TIER_REASONS.items() if tier == "non_revenue"
)
#: R2-OW03 (the underwriter's Q3: "I can review"; §10.7): the non_revenue codes the underwriter may confirm back into
#: revenue (confirm and reset only; a reject is refused, the row being non-revenue already). Every other non_revenue
#: row keeps the review refusal: a non-revenue rule's, Q12's no-purpose government payment's, Q11's asset sale's (the
#: Q11 card's open point 4: no confirm-dealer path).
REVIEWABLE_NON_REVENUE_REASONS: frozenset[str] = frozenset({"zelle_excluded"})


def non_revenue_reason(code: object) -> bool:
    """R2-OW03: whether `code` is a reason code REVENUE_TIER_REASONS files under non_revenue (NON_REVENUE_REASONS)."""
    return isinstance(code, str) and code in NON_REVENUE_REASONS


#: 5.6 (§12): the tier figures a payload analysed before 5.6 cannot have. Its rebuild and its served copy
#: (analysis/revenue_view.py) set every one to None. R2-OW03: and the non-revenue breakdown, which reads the tiers.
TIER_METRIC_KEYS = (
    "true_revenue", "true_revenue_total", "true_revenue_count", "counted_flagged_total", "counted_flagged_count",
    "excluded_pending_review_total", "excluded_pending_review_count", "counted_flagged_by_reason",
    "excluded_pending_review_by_reason", "revenue_review_items", "true_revenue_evidence",
    "counted_flagged_evidence", "excluded_pending_review_evidence", "non_revenue_by_reason",
)
TIER_DETECTION_KEYS = ("true_revenue_evidence", "counted_flagged_evidence", "excluded_pending_review_evidence")
#: 5.6 (T7): a statement needs revenue review when its held credits are this share, in percent, or more of its
#: posted credits (non-revenue included), compared in integer cents.
REVENUE_REVIEW_HELD_SHARE = 10
#: Audit B11 (I50, T7 amended): it also needs review when its held credits are REVENUE_REVIEW_HELD_SHARE percent or
#: more of True plus held (the base an MCA advance is sized on, so heavy non-revenue no longer dilutes the share), and
#: at least this many dollars, so a statement whose True is $0 is never gated on held cents.
REVENUE_REVIEW_HELD_FLOOR = 500
WITHHOLDING_DENOMINATOR_MODES = (
    "legacy_eligible_deposits",
    "verified_revenue",
    # 5.6 (T8): True revenue is selectable, never the default.
    "true_revenue",
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


def revenue_contribution_flags(state: RevenueState | None, tier: str | None = None) -> dict[str, bool]:
    """The contribution flags of one record (§5.4). The state decides the three state flags; the tier (5.6) decides
    the counted and held flags and the repointed `contributes_to_true_revenue` (verified or counted). A record with
    no tier contributes to neither middle tier and not to True revenue."""
    return {
        "contributes_to_verified_revenue": state == "verified_revenue",
        "contributes_to_unverified_deposit": state == "unverified_deposit",
        "contributes_to_non_revenue": state == "non_revenue",
        "contributes_to_counted_flagged": tier == "counted_flagged",
        "contributes_to_excluded_pending_review": tier == "excluded_pending_review",
        # Deprecated aliases remain serialized for existing API consumers. They
        # are derived from the canonical state and tier and are never scanned separately.
        # 5.6 (T9): repointed to the new True revenue, verified plus counted.
        "contributes_to_true_revenue": tier in ("verified", "counted_flagged"),
        "contributes_to_potential_revenue": state == "unverified_deposit",
    }


def tier_of_state(state: RevenueState | None) -> str | None:
    """The tier a state fixes on its own: verified for verified_revenue and non_revenue for non_revenue; None for an
    unverified deposit, whose tier the true-revenue pass sets."""
    return {"verified_revenue": "verified", "non_revenue": "non_revenue"}.get(state or "")


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


def _tiered(records: list[dict]) -> bool:
    """5.6 (§12): whether the posted credits carry tiers. A payload analysed before 5.6 carries none, and one whose
    records carry a tier only in part is refused, as a missing state is."""
    carrying = {isinstance(record.get("revenue_tier"), str) for record in records}
    if len(carrying) > 1:
        raise ValueError(_MIXED_TIERS)
    return carrying != {False}  # an account with no posted credit has nothing to be tier-less about


#: The fixed refusals of the rebuild and the review writer (webapp/app.py _DECLARED_REVIEW_REFUSALS lists them).
#: analysis/metrics.py raises _TIER_DISAGREES too, so the message has one source.
_MIXED_TIERS = "every posted credit carries a revenue tier, or none does"
_TIER_DISAGREES = "every posted credit's revenue state must agree with its tier"
_ALREADY_VERIFIED = "a credit a rule verified can only be marked non-revenue"


def _rebuild_account_revenue_views(analysis: dict) -> dict:
    """One ACCOUNT's serialized revenue views, rebuilt in place. A 5.6 payload is rebuilt on its four tiers; a payload
    analysed before 5.6 takes the tier-less path (§12): today's three states, no tier totals, no agreement check, and
    no True revenue (its `true_revenue` and `true_revenue_evidence` are None and no row carries
    `contributes_to_true_revenue`)."""
    statement = analysis["statement"]
    transactions = statement.get("transactions") or []
    evidence: dict[str, list[dict]] = {state: [] for state in REVENUE_STATES}
    tier_evidence: dict[str, list[dict]] = {tier: [] for tier in REVENUE_TIERS}
    totals: dict[str, float] = {state: 0.0 for state in REVENUE_STATES}
    counts: dict[str, int] = {state: 0 for state in REVENUE_STATES}
    tier_totals: dict[str, float] = {tier: 0.0 for tier in REVENUE_TIERS}
    tier_counts: dict[str, int] = {tier: 0 for tier in REVENUE_TIERS}
    by_reason: dict[str, dict[str, list]] = {"counted_flagged": {}, "excluded_pending_review": {}}
    # R2-OW03: the non_revenue rows that carry a non_revenue code, apart from the counted and held reasons.
    non_revenue_by_reason: dict[str, list] = {}
    posted_total = 0.0
    posted_count = 0
    direction_conflict = False
    serialized_records: list[dict] = []

    posted_records = []
    for transaction in transactions:
        amount = _number(transaction.get("amount"))
        record = transaction.get("classification")
        if not isinstance(record, dict):
            if amount > 0:
                raise ValueError(
                    "every posted credit must have an authoritative classification record"
                )
            continue
        if amount > 0 and record.get("is_posted") is not False:
            posted_records.append(record)
    tiered = _tiered(posted_records)

    for transaction in transactions:
        amount = _number(transaction.get("amount"))
        record = transaction.get("classification")
        if not isinstance(record, dict):
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
        tier = record.get("revenue_tier") if tiered else None
        if tiered and STATE_OF_TIER.get(tier) != state:
            raise ValueError(_TIER_DISAGREES)
        record.update(revenue_contribution_flags(state, tier))
        if not tiered:
            record.pop("contributes_to_true_revenue", None)
        # §10.7, T7 (S4.4/S4.5 review): what needs review now is the undecided rows, so a direction conflict gates
        # only while its decision is pending; a confirmed or rejected one no longer does (a reset makes it wait again).
        if (
            record.get("revenue_match_method") == "direction_conflict"
            and record.get("revenue_review_status") == "pending"
        ):
            direction_conflict = True
        serialized_records.append(deepcopy(record))
        totals[state] += amount
        counts[state] += 1
        evidence[state].append(deepcopy(record))
        if tiered:
            tier_totals[tier] += amount
            tier_counts[tier] += 1
            tier_evidence[tier].append(deepcopy(record))
            if tier in by_reason:
                slot = by_reason[tier].setdefault(record.get("revenue_tier_reason") or "", [0, 0.0])
                slot[0] += 1
                slot[1] += amount
            elif tier == "non_revenue" and non_revenue_reason(record.get("revenue_tier_reason")):
                slot = non_revenue_by_reason.setdefault(record["revenue_tier_reason"], [0, 0.0])
                slot[0] += 1
                slot[1] += amount

    posted_total = round(posted_total, 2)
    for state in REVENUE_STATES:
        totals[state] = round(totals[state], 2)
    for tier in REVENUE_TIERS:
        tier_totals[tier] = round(tier_totals[tier], 2)
    classified_total = round(sum(totals.values()), 2)
    classified_count = sum(counts.values())
    if tiered:
        classified_total = round(sum(tier_totals.values()), 2)
        classified_count = sum(tier_counts.values())
    delta = round(classified_total - posted_total, 2)
    reconciles = delta == 0.0 and classified_count == posted_count
    true_total = round(tier_totals["verified"] + tier_totals["counted_flagged"], 2) if tiered else None
    true_evidence = (
        [deepcopy(record) for record in serialized_records if record.get("contributes_to_true_revenue")]
        if tiered else None
    )

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
        # Audit B11 (I31): the four-tier identity under its own name; `revenue_reconciles` stays as its deprecated
        # alias for API consumers. Neither is a reconciliation against the bank's figures (that is `reconciliation.ok`).
        "revenue_tiers_sum_to_posted": reconciles,
        "revenue_reconciles": reconciles,
        "verified_revenue_evidence": evidence["verified_revenue"],
        "unverified_deposit_evidence": evidence["unverified_deposit"],
        "non_revenue_evidence": evidence["non_revenue"],
        # Deprecated aggregate aliases, all derived from canonical records. 5.6 (T9): `true_revenue` and
        # `true_revenue_evidence` are True revenue; None on a payload analysed before 5.6 (§12).
        "true_revenue": true_total,
        "confirmed_true_revenue": totals["verified_revenue"],
        "confirmed_true_revenue_total": totals["verified_revenue"],
        "confirmed_true_revenue_count": counts["verified_revenue"],
        "potential_revenue_total": totals["unverified_deposit"],
        "potential_revenue_count": counts["unverified_deposit"],
        "true_revenue_evidence": true_evidence,
        "potential_revenue_evidence": evidence["unverified_deposit"],
    })
    if tiered:
        metrics.update({
            "true_revenue_total": true_total,
            "true_revenue_count": tier_counts["verified"] + tier_counts["counted_flagged"],
            "counted_flagged_total": tier_totals["counted_flagged"],
            "counted_flagged_count": tier_counts["counted_flagged"],
            "excluded_pending_review_total": tier_totals["excluded_pending_review"],
            "excluded_pending_review_count": tier_counts["excluded_pending_review"],
            "counted_flagged_by_reason": _by_reason(by_reason["counted_flagged"]),
            "excluded_pending_review_by_reason": _by_reason(by_reason["excluded_pending_review"]),
            # R2-OW03 (§9.1): the non-revenue breakdown, {code: {"count", "total"}} over NON_REVENUE_REASONS.
            "non_revenue_by_reason": _by_reason(non_revenue_by_reason),
            "revenue_review_items": tier_counts["excluded_pending_review"],
            "revenue_review_required": revenue_review_gate(
                direction_conflict=direction_conflict,
                held_total=tier_totals["excluded_pending_review"],
                posted_total=posted_total,
                tiers_sum_to_posted=reconciles,
                true_total=true_total,
            ),
            "counted_flagged_evidence": tier_evidence["counted_flagged"],
            "excluded_pending_review_evidence": tier_evidence["excluded_pending_review"],
        })
    else:
        # §12: no tier figure, and the gate is the rule the payload was analysed under.
        metrics.update({key: None for key in TIER_METRIC_KEYS})
        metrics["revenue_review_required"] = (
            counts["unverified_deposit"] > 0 or direction_conflict or not reconciles
        )

    denominator_mode = normalize_withholding_denominator_mode(
        metrics.get("withholding_denominator_mode")
    )
    metrics["withholding_denominator_mode"] = denominator_mode
    denominator = None
    if denominator_mode == "verified_revenue":
        denominator = totals["verified_revenue"]
        metrics["withholding_denominator_label"] = "Verified revenue"
        metrics["eligible_deposit_definition"] = "verified classified revenue"
    elif denominator_mode == "true_revenue" and true_total is not None:
        denominator = true_total
        metrics["withholding_denominator_label"] = "True revenue"
        metrics["eligible_deposit_definition"] = "true revenue: verified plus counted credits"
    if denominator is not None:
        metrics["eligible_deposits"] = denominator
        metrics["withholding_denominator"] = denominator
        metrics["potential_withholding_denominator"] = denominator
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
    detection["true_revenue_evidence"] = deepcopy(true_evidence)
    detection["potential_revenue_evidence"] = evidence["unverified_deposit"]
    if tiered:
        detection["counted_flagged_evidence"] = tier_evidence["counted_flagged"]
        detection["excluded_pending_review_evidence"] = tier_evidence["excluded_pending_review"]
    else:
        detection.update({key: None for key in TIER_DETECTION_KEYS})
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


def _by_reason(slots: dict[str, list]) -> dict[str, dict[str, float | int]]:
    return {reason: {"count": count, "total": round(total, 2)} for reason, (count, total) in sorted(slots.items())}


def revenue_review_gate(
    *,
    direction_conflict: bool,
    held_total: float,
    posted_total: float,
    tiers_sum_to_posted: bool,
    true_total: float | None = None,
) -> bool:
    """T7: a statement needs revenue review when an undecided credit's direction conflicts with its amount (§10.7:
    the rebuild passes only a pending conflict), when its held credits are REVENUE_REVIEW_HELD_SHARE percent or more
    of all its posted credits (non-revenue included), compared in integer cents, or when its tiers do not sum to its
    posted credits (the four-tier identity of §5.1: a classification left incomplete). Counted, flagged credits never
    gate.

    Audit B11 (I50): it also needs review when its held credits are REVENUE_REVIEW_HELD_SHARE percent or more of
    `true_total` plus held, in integer cents, and at least REVENUE_REVIEW_HELD_FLOOR dollars. An MCA advance is sized
    on True, so a statement heavy with transfers or financing no longer passes with a material share of its potential
    True held; the floor keeps a $0-True statement from gating on held cents. Without `true_total` (a caller that
    has none) the second share is not read."""
    held_cents = round(held_total * 100)
    posted_cents = round(posted_total * 100)
    held_share = held_cents > 0 and held_cents * 100 >= REVENUE_REVIEW_HELD_SHARE * posted_cents
    if true_total is not None and not held_share and held_cents >= REVENUE_REVIEW_HELD_FLOOR * 100:
        true_cents = round(true_total * 100)
        held_share = held_cents * 100 >= REVENUE_REVIEW_HELD_SHARE * (max(true_cents, 0) + held_cents)
    return direction_conflict or held_share or not tiers_sum_to_posted


def record_serialized_revenue_review(
    analysis: dict,
    *,
    source_location: str,
    decision: Literal["confirm", "reject", "reset"],
    account: int | None = None,
    reviewed_at: str | None = None,
) -> dict:
    """Write a human decision onto one reviewable posted credit's classification
    record (a counted or held deposit, or a credit a rule verified, §10.7; an
    unverified deposit on a payload analysed before 5.6; R2-OW03: a confirm or a
    reset of a Zelle deposit the owner's policy excluded) and return the record,
    WITHOUT rebuilding the revenue views.
    `apply_serialized_revenue_review` is this followed by the rebuild; a caller
    writing several decisions (the re-analysis replay, `webapp/reanalysis.py`)
    rebuilds once, after the last. Every check below comes before the first
    write, so a refused decision leaves `analysis` exactly as it was.
    `reviewed_at` is when the decision was made (default: now); a reset clears
    it.

    Every account is searched, in printed order, unless `account` (1-based, in
    printed order) names the one the posting belongs to. A reviewer acts on a
    POSTING, and a posting belongs to one account of the document; searching
    only the first would raise `transaction source location was not found` for
    every posting in the second — a message about the reviewer's request rather
    than about the shape this function was handed.

    A location numbers a posting within ITS account (`transaction:N`), so in a
    document of several accounts one location can name a posting in each. Such
    a location is refused unless `account` says which: taking the first match
    would record the decision against another account's posting.
    """
    if decision not in {"confirm", "reject", "reset"}:
        raise ValueError("decision must be confirm, reject, or reset")
    accounts = payload_accounts(analysis, surface=_REVIEW_SURFACE)
    if account is not None:
        if isinstance(account, bool) or not isinstance(account, int) or not 1 <= account <= len(accounts):
            raise LookupError("account was not found")
        accounts = [accounts[account - 1]]
    matches = [
        transaction
        for holder in accounts
        for transaction in (holder.get("statement") or {}).get("transactions") or []
        if (transaction.get("classification") or {}).get("source_location")
        == source_location
    ]
    if not matches:
        raise LookupError("transaction source location was not found")
    if len(matches) > 1:
        raise ValueError("transaction source location is in more than one account; name the account")
    target = matches[0]
    record = target.get("classification") or {}
    initial_state = record.get("revenue_initial_classification")
    initial_state = LEGACY_REVENUE_STATE_MAP.get(initial_state, initial_state)
    # 5.6 (T6, §10.7): a counted or held deposit, and a credit a rule verified, are reviewable; a credit a
    # non-revenue rule decided is not. A payload analysed before 5.6 carries no tier and keeps today's rule.
    tiered = isinstance(record.get("revenue_tier"), str)
    reviewable = {"unverified_deposit", "verified_revenue"} if tiered else {"unverified_deposit"}
    # R2-OW03 (the underwriter's Q3, "I can review"; §10.7): a Zelle deposit the owner's policy excluded may be
    # confirmed (the deposits you confirmed: Verified, its reason kept) and reset (back to non_revenue and its
    # reason). A reject is refused: the row is non-revenue already, and the replay reads a confirm only
    # (webapp/reanalysis.py _awaits_review), so the writer and the replay agree.
    valve = (
        tiered and initial_state == "non_revenue"
        and record.get("revenue_tier_reason") in REVIEWABLE_NON_REVENUE_REASONS
    )
    if (initial_state not in reviewable and not valve) or (valve and decision == "reject"):
        raise ValueError("only automatically unverified deposits can be reviewed")
    if decision == "confirm" and initial_state == "verified_revenue":
        raise ValueError(_ALREADY_VERIFIED)

    if decision == "confirm":
        state: RevenueState = "verified_revenue"
        status = "confirmed"
        note = "Reviewer confirmed this credit as operating revenue."
        tier = "verified"
    elif decision == "reject":
        state = "non_revenue"
        status = "rejected"
        note = "Reviewer rejected this credit as operating revenue."
        tier = "non_revenue"
    else:
        state = initial_state
        status = "pending" if initial_state == "unverified_deposit" else "not_required"
        note = None
        tier = record.get("revenue_initial_tier")

    record["revenue_classification"] = state
    if tiered:
        record["revenue_tier"] = tier
        record["revenue_review_required"] = tier == "excluded_pending_review"
    else:
        tier = None
        record["revenue_review_required"] = state == "unverified_deposit"
    record["revenue_review_status"] = status
    record["revenue_review_note"] = note
    record["revenue_reviewed_at"] = (
        None if decision == "reset" else reviewed_at or datetime.now(UTC).isoformat()
    )
    record.update(revenue_contribution_flags(state, tier))
    if not tiered:
        record.pop("contributes_to_true_revenue", None)
    return record


def apply_serialized_revenue_review(
    analysis: dict,
    *,
    source_location: str,
    decision: Literal["confirm", "reject", "reset"],
    account: int | None = None,
) -> dict:
    """Apply a human decision to one reviewable credit and rebuild all views:
    `record_serialized_revenue_review`, whose checks and account rules these
    are, followed by one rebuild."""
    record_serialized_revenue_review(
        analysis, source_location=source_location, decision=decision, account=account,
    )
    return rebuild_serialized_revenue_views(analysis)

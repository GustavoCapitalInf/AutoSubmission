"""Shared revenue states and serialized reviewer operations."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal, NamedTuple

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
    # lending bank's block (true_revenue.tiers.UNREAD_RUN_NAMES_FINANCING).
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
    # Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: a credit a rule verified or counted, into an account
    # whose printed title reads PREMIUM TRUST (insureds' premiums, not the agency's revenue), held by pass 7's step after
    # the $1 floor (true_revenue.trust.PREMIUM_TRUST_REASON); the end of the held group.
    "premium_trust_account": ("excluded_pending_review", "Deposit into a premium trust account"),
    # Owner ruling 2026-10-02 (the underwriter's Q4), R2-OW16: within a package, a counted deposit that prints no payer,
    # matched to an exact-cents transfer out of another of the business's accounts 0 to 2 days earlier
    # (analysis/package/passes.py `package_matches`, pass 2; package-only, never on a statement viewed alone); the end
    # of the held group.
    "own_account_transfer_matched": (
        "excluded_pending_review", "Matches a transfer out of another account in this package",
    ),
    "wire_named_sender": ("counted_flagged", "Wire from a named sender"),
    "check_deposit": ("counted_flagged", "Check deposit"),
    "no_payer_printed": ("counted_flagged", "No payer printed"),
    # Audit B10 (I05, I60): the statement printed a payer the parser did not read (true_revenue.tiers.PAYER_TEXT_NOT_READ).
    "payer_text_not_read": ("counted_flagged", "Payer text not read"),
    "p2p": ("counted_flagged", "Person-to-person"),
    "factoring_payout": ("counted_flagged", "Factoring payout"),
    # Owner ruling 2026-10-02 (the underwriter's Q9, part (c)), R2-OW05: a lender paying the business for its services
    # (a listed auto lender's payables on a statement with no dealer evidence: a repossession agency's recoveries),
    # counted, never verified (true_revenue.words.LENDER_PAID_FOR_SERVICES).
    "lender_paid_for_services": ("counted_flagged", "Lender paid for services"),
    # Owner ruling 2026-10-02 (the underwriter's Q11 (a)), R2-OW06: a builder's progress draw, counted and flagged, never
    # verified (true_revenue.words.CONSTRUCTION_PROGRESS_DRAW_REASON).
    "construction_progress_draw": ("counted_flagged", "Builder's progress draw"),
    # Owner ruling 2026-10-02 (the underwriter's Q2), R2-OW08: an insurer paying the business for its work (a holder's
    # trade, a service form, or three or more credits from one insurer within 31 days), counted, never verified
    # (true_revenue.words.INSURER_FOR_WORK_METHOD).
    "insurer_paid_for_services": ("counted_flagged", "Insurer paid for the business's work"),
    # Owner ruling 2026-10-02 (the underwriter's Q9 (a)), R2-OW09: a customer whose own name carries a finance word,
    # paying on a line that prints invoice, accounts-payable or vendor-payment wording (or a commission), released from
    # T4's financing-root hold, counted, never verified (true_revenue.FINANCE_NAMED_CUSTOMER).
    "finance_named_customer": ("counted_flagged", "Customer with a finance word in its name, paying an invoice"),
    # Owner ruling 2026-10-02 (the underwriter's Q9 (b)), R2-OW09: a rent LEASE received by a business in leasing or
    # property, released from T4's financing-root hold, counted, never verified (true_revenue.LESSOR_RENT).
    "lessor_rent": ("counted_flagged", "Rent received by a leasing or property business"),
    # Audit B11 (I53): the payer's own settlement of the merchant's sales (OQ2's BNPL providers, marketplaces), counted;
    # the label keeps the caution that the payer also lends, and never reads as financing counted in True.
    "payout_credit_entity": ("counted_flagged", "BNPL or marketplace settlement (payer also lends)"),
    # Owner ruling 2026-10-02 (Q8): a lease-to-own or patient financier's payout to the merchant for a customer's
    # financed purchase, counted, never verified (true_revenue.words.CUSTOMER_FINANCING_PAYOUT).
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
    # sale), non_revenue with this reason (true_revenue.words.ASSET_SALE_METHOD); no review path.
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
#: Audit round 3, R3-B03 (R3-20; true revenue spec §11, §17.1 the R2-OW14 follow-ups (1); the brief's default (a), an
#: owner decision): a True or Verified withholding basis under this many units of the statement's own currency is read as
#: $0 is: no rate, no potential exposure, `withholding_review_required` and a note that says why; never a gate. It is the
#: floor T7 already uses (REVENUE_REVIEW_HELD_FLOOR), so a basis of a few dollars no longer publishes a rate in the
#: thousands of percent. The legacy basis (the bank's own deposits less lender funding) keeps today's behaviour.
#: webapp/static/app.js mirrors it (WITHHOLDING_BASIS_FLOOR; tests/test_withholding_basis_floor.py pins the two equal).
WITHHOLDING_BASIS_FLOOR = REVENUE_REVIEW_HELD_FLOOR
WITHHOLDING_DENOMINATOR_MODES = (
    "legacy_eligible_deposits",
    "verified_revenue",
    # 5.6 (T8): True revenue is selectable. Owner ruling 2026-10-02 (the underwriter's Q7, audit I34; R2-OW14): it is
    # the default (DEFAULT_WITHHOLDING_DENOMINATOR_MODE).
    "true_revenue",
)
#: Owner ruling 2026-10-02 (the underwriter's Q7, audit I34; true revenue spec §11, T8; R2-OW14): "2 Make True revenue
#: the default": the withholding basis a new analysis divides by when WITHHOLDING_DENOMINATOR_MODE is unset or invalid
#: (config.Settings, load_settings, compute_metrics and the Metrics dataclass all read it). The legacy and verified bases
#: stay selectable; a STORED payload whose metrics carry no mode still reads as legacy (normalize's own default), so an
#: analysis made before the default moved keeps the basis it was made under.
DEFAULT_WITHHOLDING_DENOMINATOR_MODE = "true_revenue"
LEGACY_REVENUE_STATE_MAP = {
    "true_revenue": "verified_revenue",
    "potential_revenue": "unverified_deposit",
}
LEGACY_WITHHOLDING_DENOMINATOR_MODES = {
    "confirmed_true_revenue": "verified_revenue",
}


def normalize_withholding_denominator_mode(value: object, default: str = "legacy_eligible_deposits") -> str:
    """The withholding mode `value` names (an older name mapped to its current one), or `default` when it names none.
    The default stays the legacy basis for a stored payload, whose missing mode means it was analysed before a mode was
    recorded or before True revenue became the default (R2-OW14); the settings pass DEFAULT_WITHHOLDING_DENOMINATOR_MODE
    for a new analysis."""
    mode = str(value or default)
    mode = LEGACY_WITHHOLDING_DENOMINATOR_MODES.get(mode, mode)
    return mode if mode in WITHHOLDING_DENOMINATOR_MODES else default


def withholding_basis_below_floor(denominator: float, mode: object) -> bool:
    """Audit round 3, R3-B03 (R3-20): whether a revenue basis (True or Verified; a stored mode read with
    normalize_withholding_denominator_mode, so no mode is legacy) is above $0 and under WITHHOLDING_BASIS_FLOOR."""
    return (normalize_withholding_denominator_mode(mode) != "legacy_eligible_deposits"
            and 0 < denominator < WITHHOLDING_BASIS_FLOOR)


def withholding_basis_publishable(denominator: float, mode: object) -> bool:
    """Audit round 3, R3-B03 (R3-20; true revenue spec §11): whether a withholding rate or a potential exposure is
    published over `denominator`, the basis withholding `mode` divides by: above $0, and on a revenue basis (True or
    Verified) at least WITHHOLDING_BASIS_FLOOR. The legacy basis bypasses the floor. Every published rate and exposure
    reads it: `compute_metrics`, the review rebuild, the package's rate, its member rows and its per-match exposures."""
    return denominator > 0 and (
        normalize_withholding_denominator_mode(mode) == "legacy_eligible_deposits" or denominator >= WITHHOLDING_BASIS_FLOOR
    )


def withholding_unavailable_note(label: str, denominator: float, unit: str = "") -> str:
    """The note of a withholding rate that is not published over `denominator` (audit round 3, R3-B03: R3-20), one
    wording for `compute_metrics` and the review rebuild: R2-OW14's words at $0 or less, else the floor's. `unit` is
    " <currency>" or ""."""
    if denominator <= 0:
        return f"withholding rate is unavailable because {label} is zero or missing"
    return (f"withholding rate is unavailable because {label} ({denominator:,.2f}{unit}) is under the withholding "
            f"basis floor ({WITHHOLDING_BASIS_FLOOR:,.2f}{unit})")


def potential_withholding_unavailable_note(label: str, denominator: float, unit: str = "") -> str:
    """The potential exposure's twin of withholding_unavailable_note."""
    if denominator <= 0:
        return f"potential withholding exposure is unavailable because {label} is zero or missing"
    return (f"potential withholding exposure is unavailable because {label} ({denominator:,.2f}{unit}) is under the "
            f"withholding basis floor ({WITHHOLDING_BASIS_FLOOR:,.2f}{unit})")


#: The two notes' leading words, which the review rebuild removes before it writes the notes its basis reads.
WITHHOLDING_UNAVAILABLE_NOTE_PREFIXES = (
    "withholding rate is unavailable because ", "potential withholding exposure is unavailable because ",
)


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


class PostedCredit(NamedTuple):
    """One posted credit, filed under the state and tier its caller chose: no tier on a payload analysed before tiers,
    and no state on a package credit that carries none (it is posted all the same). `record` is the caller's own
    record of it, kept by reference."""
    amount: float
    state: RevenueState | None
    tier: str | None
    reason: str | None
    record: object


class RevenueBucket(NamedTuple):
    total: float
    count: int
    records: list


class RevenueBuckets(NamedTuple):
    posted: RevenueBucket
    states: dict[RevenueState, RevenueBucket]
    tiers: dict[RevenueTier, RevenueBucket]
    #: {tier: {reason: {"count", "total"}}}, sorted by reason: the middle tiers by their reason ("" when none), and
    #: non_revenue by NON_REVENUE_REASONS alone (true revenue spec §9.1).
    by_reason: dict[str, dict[str, dict[str, float | int]]]


#: How a money total adds its amounts to cents: one at a time and rounded once, with builtin sum() and rounded once,
#: or rounded after each amount. Float addition makes them differ: builtin sum() compensates float error and can land
#: on another cent, and it sums no amount to the integer 0.
Accumulation = Literal["sequential", "builtin_sum", "rounded_each"]


def cents_total(amounts: list[float], accumulation: Accumulation) -> float:
    """`amounts` added in the order given, to the cent, as `accumulation` says."""
    if accumulation == "builtin_sum":
        return round(sum(amounts), 2)
    total = 0.0
    if accumulation == "rounded_each":
        for amount in amounts:
            total = round(total + amount, 2)
        return total
    for amount in amounts:
        total += amount
    return round(total, 2)


def revenue_buckets(
    credits: list[PostedCredit],
    *,
    accumulation: Accumulation = "sequential",
    reason_accumulation: Accumulation = "sequential",
    reason_order: Literal["sorted", "first_seen"] = "sorted",
) -> RevenueBuckets:
    """Every credit in the posted bucket and its state bucket, and in its tier bucket when its tier is one of
    REVENUE_TIERS. Each bucket keeps its credits' records in the order given and its total rounded to cents.

    The defaults are how compute_metrics and the rebuild add: every total one credit at a time in the order given, the
    reasons sorted. The package's member figures (analysis/package/figures.py) add each bucket with builtin sum() and
    each reason total rounded after each credit, the reasons in the order they first appear."""
    reasons: dict[str, dict[str, list[PostedCredit]]] = {
        "counted_flagged": {}, "excluded_pending_review": {}, "non_revenue": {},
    }
    for credit in credits:
        if credit.tier in ("counted_flagged", "excluded_pending_review"):
            reasons[credit.tier].setdefault(credit.reason or "", []).append(credit)
        elif credit.tier == "non_revenue" and non_revenue_reason(credit.reason):
            reasons["non_revenue"].setdefault(credit.reason, []).append(credit)
    return RevenueBuckets(
        posted=_bucket(credits, accumulation),
        states={state: _bucket([credit for credit in credits if credit.state == state], accumulation)
                for state in REVENUE_STATES},
        tiers={tier: _bucket([credit for credit in credits if credit.tier == tier], accumulation)
               for tier in REVENUE_TIERS},
        by_reason={
            tier: {
                reason: {"count": len(group), "total": cents_total([credit.amount for credit in group],
                                                                   reason_accumulation)}
                for reason, group in (sorted(groups.items()) if reason_order == "sorted" else groups.items())
            }
            for tier, groups in reasons.items()
        },
    )


def _bucket(credits: list[PostedCredit], accumulation: Accumulation) -> RevenueBucket:
    return RevenueBucket(cents_total([credit.amount for credit in credits], accumulation), len(credits),
                         [credit.record for credit in credits])


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
#: Audit round 3, R3-B02 (R3-21; true revenue spec §10.7, §17.1; the owner's ruling of 2026-10-02 on the underwriter's
#: Q5, "Revenue is unaffected (the return credit is non-revenue as today)"): a confirm on a credit rule D matched to a
#: confirmed funder's payment (`returns_funder_payment`, R2-OW13) is refused; Mark Non-Revenue and Reset stay. Nothing
#: re-reads pass 7b after a review, so a Confirm would count the business's own payment coming back as Verified revenue
#: while its payment stays out of paid to lenders as a bounce.
_RETURNS_FUNDER_PAYMENT = "a credit that returns a confirmed funder's payment can only be marked non-revenue"


def _rebuild_account_revenue_views(analysis: dict) -> dict:
    """One ACCOUNT's serialized revenue views, rebuilt in place. A 5.6 payload is rebuilt on its four tiers; a payload
    analysed before 5.6 takes the tier-less path (§12): today's three states, no tier totals, no agreement check, and
    no True revenue (its `true_revenue` and `true_revenue_evidence` are None and no row carries
    `contributes_to_true_revenue`)."""
    statement = analysis["statement"]
    transactions = statement.get("transactions") or []
    posted_credits: list[PostedCredit] = []
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
        posted_credits.append(PostedCredit(amount, state, tier, record.get("revenue_tier_reason"), record))

    revenue = revenue_buckets(posted_credits)
    posted, states, tiers = revenue.posted, revenue.states, revenue.tiers
    evidence = {state: [deepcopy(record) for record in bucket.records] for state, bucket in states.items()}
    tier_evidence = {tier: [deepcopy(record) for record in bucket.records] for tier, bucket in tiers.items()}
    identity = tiers if tiered else states
    classified_total = round(sum(bucket.total for bucket in identity.values()), 2)
    classified_count = sum(bucket.count for bucket in identity.values())
    delta = round(classified_total - posted.total, 2)
    reconciles = delta == 0.0 and classified_count == posted.count
    true_total = round(tiers["verified"].total + tiers["counted_flagged"].total, 2) if tiered else None
    true_evidence = (
        [deepcopy(record) for record in serialized_records if record.get("contributes_to_true_revenue")]
        if tiered else None
    )

    metrics = analysis.setdefault("metrics", {})
    metrics.update({
        "total_posted_credits": posted.total,
        "total_posted_credit_count": posted.count,
        "verified_revenue_total": states["verified_revenue"].total,
        "verified_revenue_count": states["verified_revenue"].count,
        "unverified_deposit_total": states["unverified_deposit"].total,
        "unverified_deposit_count": states["unverified_deposit"].count,
        "non_revenue_total": states["non_revenue"].total,
        "non_revenue_count": states["non_revenue"].count,
        "maximum_revenue": round(
            states["verified_revenue"].total + states["unverified_deposit"].total, 2
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
        "confirmed_true_revenue": states["verified_revenue"].total,
        "confirmed_true_revenue_total": states["verified_revenue"].total,
        "confirmed_true_revenue_count": states["verified_revenue"].count,
        "potential_revenue_total": states["unverified_deposit"].total,
        "potential_revenue_count": states["unverified_deposit"].count,
        "true_revenue_evidence": true_evidence,
        "potential_revenue_evidence": evidence["unverified_deposit"],
    })
    if tiered:
        metrics.update({
            "true_revenue_total": true_total,
            "true_revenue_count": tiers["verified"].count + tiers["counted_flagged"].count,
            "counted_flagged_total": tiers["counted_flagged"].total,
            "counted_flagged_count": tiers["counted_flagged"].count,
            "excluded_pending_review_total": tiers["excluded_pending_review"].total,
            "excluded_pending_review_count": tiers["excluded_pending_review"].count,
            "counted_flagged_by_reason": revenue.by_reason["counted_flagged"],
            "excluded_pending_review_by_reason": revenue.by_reason["excluded_pending_review"],
            # R2-OW03 (§9.1): the non-revenue breakdown, {code: {"count", "total"}} over NON_REVENUE_REASONS.
            "non_revenue_by_reason": revenue.by_reason["non_revenue"],
            "revenue_review_items": tiers["excluded_pending_review"].count,
            "revenue_review_required": revenue_review_gate(
                direction_conflict=direction_conflict,
                held_total=tiers["excluded_pending_review"].total,
                posted_total=posted.total,
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
            states["unverified_deposit"].count > 0 or direction_conflict or not reconciles
        )

    denominator_mode = normalize_withholding_denominator_mode(
        metrics.get("withholding_denominator_mode")
    )
    metrics["withholding_denominator_mode"] = denominator_mode
    denominator = None
    if denominator_mode == "verified_revenue":
        denominator = states["verified_revenue"].total
        metrics["withholding_denominator_label"] = "Verified revenue"
        metrics["eligible_deposit_definition"] = "verified classified revenue"
    elif denominator_mode == "true_revenue" and true_total is not None:
        denominator = true_total
        metrics["withholding_denominator_label"] = "True revenue"
        metrics["eligible_deposit_definition"] = "true revenue: verified plus counted credits"
    detection = analysis.setdefault("detection", {})
    if denominator is not None:
        metrics["eligible_deposits"] = denominator
        metrics["withholding_denominator"] = denominator
        metrics["potential_withholding_denominator"] = denominator
        numerator = _number(metrics.get("withholding_numerator"))
        potential_numerator = _number(metrics.get("potential_withholding_numerator"))
        # Audit round 3, R3-B03 (R3-20): one helper decides every published rate; a revenue basis under the floor is
        # read as $0 is.
        publishable = withholding_basis_publishable(denominator, denominator_mode)
        metrics["withholding_rate"] = (
            abs(numerator) / denominator * 100 if publishable else None
        )
        metrics["potential_withholding_exposure"] = (
            abs(potential_numerator) / denominator * 100 if publishable else None
        )
        metrics["withholding_review_required"] = not publishable
        metrics["withholding_basis_below_floor"] = withholding_basis_below_floor(denominator, denominator_mode)
        _refresh_withholding_basis_readers(metrics, detection, denominator, publishable, statement.get("currency"))

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


def _refresh_withholding_basis_readers(
    metrics: dict, detection: dict, denominator: float, publishable: bool, currency: object,
) -> None:
    """Audit round 3, R3-B03 (R3-13; true revenue spec §9.1, §10.7): a review that moves a True or Verified basis
    refreshes everything the basis feeds, not only the statement's figures: each potential lender's row
    (`eligible_deposit_denominator`: the basis where a rate is published or where it is $0 or less, None under the
    floor; `potential_withholding_exposure`: its debits over the basis, `_funder_dict`'s arithmetic, None where no rate
    is published) and the basis notes (`metrics.notes`, only where it is a list: the two "unavailable" notes leave and
    the ones this basis reads take the first one's place, or join the end; a list that already reads them is left as it
    is, so the rebuild of an analysis is the analysis). Confirmed funders' entries carry no basis and are untouched; the
    legacy basis never comes here (its basis never moves on review). `currency` is the account's statement's, which the
    rebuild reads (the notes name the basis in its unit), so this helper reads no payload key."""
    lenders = detection.get("potential_lenders")
    if isinstance(lenders, list):
        for entry in lenders:
            if not isinstance(entry, dict):
                continue
            entry["eligible_deposit_denominator"] = denominator if publishable or denominator <= 0 else None
            total = entry.get("potential_lender_debit_total")
            if not isinstance(total, (int, float)) or isinstance(total, bool):
                total = entry.get("total_debited")
            entry["potential_withholding_exposure"] = (
                abs(_number(total)) / denominator * 100 if publishable else None
            )
    notes = metrics.get("notes")
    if not isinstance(notes, list):
        return
    unit = f" {currency}" if currency else ""
    label = str(metrics.get("withholding_denominator_label") or "")
    wanted: list[str] = []
    if not publishable:
        wanted.append(withholding_unavailable_note(label, denominator, unit))
        if _number(metrics.get("potential_lender_debit_count")) > 0:
            wanted.append(potential_withholding_unavailable_note(label, denominator, unit))
    positions = [index for index, note in enumerate(notes)
                 if isinstance(note, str) and note.startswith(WITHHOLDING_UNAVAILABLE_NOTE_PREFIXES)]
    if [notes[index] for index in positions] == wanted:
        return
    first = positions[0] if positions else len(notes)
    rest = [note for index, note in enumerate(notes) if index not in set(positions)]
    notes[:] = rest[:first] + wanted + rest[first:]


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
    # Audit round 3, R3-B02 (R3-21): a credit that returns a confirmed funder's payment is never confirmed as revenue.
    # A record stored before R2-OW13 carries no key and is reviewed as before.
    if decision == "confirm" and record.get("returns_funder_payment"):
        raise ValueError(_RETURNS_FUNDER_PAYMENT)

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

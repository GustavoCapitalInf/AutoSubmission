"""Stage 3a — deterministic analytics. Every number a funder cares about is
computed here in plain Python from the reconciled ledger, never by the LLM.

Average Daily Balance is the headline figure and lives in its own module,
`analysis.adb`, because it carries its own daily ledger, validation suite and
audit trail. This module consumes that result and exposes it on `Metrics`
(`average_daily_balance`, `daily_balance_sum`, `calendar_day_count`, `adb`).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
# `money_to_cents` is imported rather than reimplemented: cent rounding is a
# financial decision and this package keeps exactly one of it (R-2's
# shared-utility rule), so the variance rounds exactly as the ADB does.
from .adb import (
    AverageDailyBalanceResult,
    compute_average_daily_balance,
    money_to_cents as _money,
)
from .lender_figures import LenderRow, lender_figures
from .nsf_days import PRINTED as NSF_PRINTED, UNAVAILABLE as NSF_UNAVAILABLE, negative_day_count
from .schema import Statement
from .flag_groups import FLAG_GROUPS
from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
    flagged_payee,
)
from .revenue import (
    DEFAULT_WITHHOLDING_DENOMINATOR_MODE,
    STATE_OF_TIER,
    WITHHOLDING_DENOMINATOR_MODES,
    _TIER_DISAGREES,
    PostedCredit,
    normalize_withholding_denominator_mode,
    potential_withholding_unavailable_note,
    revenue_buckets,
    revenue_review_gate,
    withholding_basis_below_floor,
    withholding_basis_publishable,
    withholding_unavailable_note,
)
from .true_revenue import holder_unscreened, payer_text_unread, premium_trust_title

#: Owner ruling 2026-10-02 (the underwriter's Q5, audit I29; true revenue spec §11; R2-OW13): the withholding rate's
#: numerator is the confirmed lender debits paid plus the funder payments returned unpaid (the scheduled obligation
#: stands), divided by the withholding basis the statement selected (legacy eligible deposits, Verified or True
#: revenue). The package and the funder rows publish the same words. Audit round 3, final review (R3-FF), F5: the words
#: name what compute_metrics sums since R3-B02 and R3-B03: the paid debits less the worded lump-sum payoffs (R3-79, in
#: paid to lenders and out of the rate), plus the returned payments their funder did not re-debit (R3-73's re-debited
#: ones leave the rate); folded into classification 5.8 and stage 36, which no release carries yet.
WITHHOLDING_FORMULA = (
    "abs(paid lender debits - worded lump-sum payoffs + returned funder payments not re-debited) / withholding basis "
    "* 100"
)
POTENTIAL_WITHHOLDING_FORMULA = "abs(potential_lender_debit_total) / withholding basis * 100"


@dataclass
class Metrics:
    days_in_period: int | None = None
    # Bank-printed averages are comparison evidence. The label may describe a
    # collected, available, credit-only, rounded, or ledger balance.
    stated_average_balance: float | None = None
    average_daily_balance: float | None = None
    # How far the canonical underwriting ADB sits from the bank's own printed
    # average, and the best available reading of WHY. Diagnostic: never
    # authoritative, never a second ADB, and never a reason to move the first.
    # All three are None unless a validated ADB and a printed average both
    # exist - there is nothing to compare otherwise.
    bank_reported_average_variance: float | None = None
    bank_reported_average_variance_pct: float | None = None
    bank_reported_average_hypothesis: str | None = None
    # Full underwriting-grade ADB working: the daily ledger, its sum, the
    # calendar-day divisor, and every validation that was run. See analysis/adb.py.
    adb: AverageDailyBalanceResult | None = None
    daily_balance_sum: float | None = None
    calendar_day_count: int | None = None
    adb_ok: bool | None = None
    min_balance: float | None = None
    max_balance: float | None = None
    negative_days: int = 0              # every calendar day, a carried (inactive) day included
    negative_printed_days: int = 0      # printed days only: posting days and bank-printed daily balances
    # Line-item totals: computed only from extracted transaction rows.
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0
    num_deposits: int = 0
    num_withdrawals: int = 0
    # Effective underwriting totals: prefer reconciled bank summary figures when
    # available; otherwise fall back to line-item totals and expose the source.
    effective_total_deposits: float = 0.0
    effective_total_withdrawals: float = 0.0
    effective_num_deposits: int | None = None
    effective_num_withdrawals: int | None = None
    deposits_source: str = "line_items"
    withdrawals_source: str = "line_items"
    nsf_count: int = 0                     # returned / NSF line items (evidence; not the underwriting NSF since R18)
    stated_nsf_count: int | None = None    # bank-printed count this period, when available
    # R18 (Gustavo, 2026-09-18): the underwriting NSF count is the number of days in the period that END with a
    # negative balance, from the validated daily ledger; returned items are not counted. Without a validated
    # ledger the figure is not computable: 0 with nsf_source 'negative_ending_days_unavailable'.
    # Owner ruling, 2026-09-22: the default basis is PRINTED days (nsf_source 'negative_printed_days'); a day
    # with no activity that only carries the previous balance is not counted. Carrying over (every calendar
    # day, nsf_source 'negative_ending_days') is the web app's Settings option. See analysis/nsf_days.py.
    effective_nsf_count: int = 0
    nsf_source: str = NSF_PRINTED
    lender_credits: float = 0.0
    # Paid to lenders: the confirmed lender debits counted as paid (contributes_to_lender_totals).
    lender_debits: float = 0.0
    lender_debit_count: int = 0
    # Owner ruling 2026-10-02 (the underwriter's Q5, audit I29; true revenue spec §9.1, §11; R2-OW13): the confirmed
    # funders' payments the bank returned unpaid (rows with returned_funder_payment_by): out of paid to lenders, kept
    # in the withholding numerator.
    returned_funder_payment_total: float = 0.0
    returned_funder_payment_count: int = 0
    lenders_detected: int = 0
    potential_lenders_detected: int = 0
    potential_lender_debit_count: int = 0
    potential_lender_debit_total: float = 0.0
    potential_lender_debits: float = 0.0
    monthly_lender_debits: float = 0.0
    insurance_count: int = 0
    insurance_total: float = 0.0
    # Spec §6 (C5): {group key: {"count", "total", "count_credited",
    # "total_credited", "payees"}} over rows marked contributes_to_flagged_totals.
    # "count" and "total" are the debits; the credited pair is the credits a
    # flagged payee paid in (owner ruling 2026-09-26: factoring payouts). It never
    # feeds lender_*, withholding_*, eligible_deposits or potential_* figures.
    flagged_groups: dict[str, dict[str, float | int]] = field(default_factory=dict)
    verified_revenue_total: float = 0.0
    verified_revenue_count: int = 0
    unverified_deposit_total: float = 0.0
    unverified_deposit_count: int = 0
    non_revenue_total: float = 0.0
    non_revenue_count: int = 0
    verified_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    unverified_deposit_evidence: list[TransactionClassification] = field(default_factory=list)
    non_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    # 5.6 (true revenue spec §5.1, §9.1): True revenue is verified plus counted; the held credits wait for an analyst.
    true_revenue_total: float = 0.0
    true_revenue_count: int = 0
    counted_flagged_total: float = 0.0
    counted_flagged_count: int = 0
    excluded_pending_review_total: float = 0.0
    excluded_pending_review_count: int = 0
    counted_flagged_by_reason: dict[str, dict[str, float | int]] = field(default_factory=dict)
    excluded_pending_review_by_reason: dict[str, dict[str, float | int]] = field(default_factory=dict)
    # R2-OW03 (true revenue spec §9.1): the non_revenue rows that carry a code REVENUE_TIER_REASONS files under
    # non_revenue (analysis/revenue.py NON_REVENUE_REASONS: the Zelle policy's, Q12's display reason), by code; its own
    # dict, never a slot of the counted or held maps.
    non_revenue_by_reason: dict[str, dict[str, float | int]] = field(default_factory=dict)
    revenue_review_items: int = 0
    counted_flagged_evidence: list[TransactionClassification] = field(default_factory=list)
    excluded_pending_review_evidence: list[TransactionClassification] = field(default_factory=list)
    # Deprecated aliases retained for consumers of the version 3.0 API. 5.6 (T9): `true_revenue` and
    # `true_revenue_evidence` are repointed to True revenue (verified plus counted).
    true_revenue: float = 0.0
    confirmed_true_revenue: float = 0.0
    confirmed_true_revenue_total: float = 0.0
    confirmed_true_revenue_count: int = 0
    potential_revenue_total: float = 0.0
    potential_revenue_count: int = 0
    maximum_revenue: float = 0.0
    total_posted_credits: float = 0.0
    total_posted_credit_count: int = 0
    revenue_classified_total: float = 0.0
    revenue_classified_count: int = 0
    revenue_reconciliation_delta: float = 0.0
    #: Audit B11 (I31): the four-tier identity of §5.1 (verified + counted + held + non-revenue = posted credits),
    #: under its own name. It is no reconciliation against the bank's printed figures (that is `reconciliation.ok`);
    #: `revenue_reconciles` stays as its deprecated alias for API consumers.
    revenue_tiers_sum_to_posted: bool = True
    revenue_reconciles: bool = True
    revenue_review_required: bool = False
    #: Audit B9 (I13): no holder's name is known for the statement (true_revenue.holder_unscreened), so the holds that
    #: read the holder's name cannot see the holder's own money. A fact for the True card and the exports (audit B11).
    holder_unscreened: bool = False
    #: Audit B10 (I05): more than true_revenue.PAYER_TEXT_UNREAD_SHARE of the statement's posted credit rows carry the
    #: parser's 'payer text not read' mark (Transaction.payer_text_unread), so its True rests on credits whose payer
    #: nobody read; and how many posted credits carry it. A statement integrity fact for the True card (audit B11).
    payer_text_unread: bool = False
    payer_text_unread_count: int = 0
    #: Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the statement's printed title reads PREMIUM TRUST
    #: (true_revenue.premium_trust_title over its account title, account name and holder name), so pass 7 holds every
    #: credit a rule verified or counted. A statement fact for the True card and the package; no figure reads it.
    premium_trust_account: bool = False
    cash_flow: float = 0.0
    withholding_rate: float | None = None
    withholding_numerator: float = 0.0
    withholding_denominator: float = 0.0
    # R2-OW13 (the underwriter's Q5): the numerator is the confirmed lender debits paid plus the returned funder
    # payments, every row marked contributes_to_withholding_rate; the basis is the selected withholding denominator.
    # Audit round 3 (R3-B02, R3-B03; the formula's words, R3-FF F5): less the worded lump-sum payoffs and the returned
    # payments their funder re-debited.
    withholding_formula: str = WITHHOLDING_FORMULA
    withholding_review_required: bool = False
    # Audit round 3, R3-B03 (R3-20; true revenue spec §9.1, §11): the True or Verified basis is above $0 and under
    # WITHHOLDING_BASIS_FLOOR, so no rate and no potential exposure is published over it (never on the legacy basis).
    withholding_basis_below_floor: bool = False
    # The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs (Recommended)"; true revenue
    # spec §9.1, §11; R3-B03): the paid payoff-worded debits to confirmed funders (`lump_sum_payoff`), in lender_debits
    # and out of withholding_numerator: lender_debits + the standing returned payments - lump_sum_payoff_total is the
    # numerator, to the cent.
    lump_sum_payoff_total: float = 0.0
    lump_sum_payoff_count: int = 0
    potential_withholding_exposure: float | None = None
    potential_withholding_numerator: float = 0.0
    potential_withholding_denominator: float = 0.0
    potential_withholding_formula: str = POTENTIAL_WITHHOLDING_FORMULA
    potential_withholding_review_required: bool = False
    eligible_deposits: float = 0.0
    legacy_eligible_deposits: float = 0.0
    # Owner ruling 2026-10-02 (the underwriter's Q7, audit I34; R2-OW14): True revenue is the default basis; the label
    # and the definition are the default's (compute_metrics sets all three for the mode it reads).
    withholding_denominator_mode: str = DEFAULT_WITHHOLDING_DENOMINATOR_MODE
    withholding_denominator_label: str = "True revenue"
    withholding_denominator_options: tuple[str, ...] = WITHHOLDING_DENOMINATOR_MODES
    eligible_deposit_definition: str = "true revenue: verified plus counted credits"
    lender_evidence: list[TransactionClassification] = field(default_factory=list)
    # R2-OW13: the returned funder payments' debit rows (lender_evidence stays the paid rows).
    returned_funder_payment_evidence: list[TransactionClassification] = field(default_factory=list)
    potential_lender_evidence: list[TransactionClassification] = field(default_factory=list)
    insurance_evidence: list[TransactionClassification] = field(default_factory=list)
    true_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    potential_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    pos_count: int = 0
    pos_credit_count: int = 0
    atm_withdrawal_count: int = 0
    ach_credit_count: int = 0
    ach_debit_count: int = 0
    check_count: int = 0
    loan_count: int = 0
    notes: list[str] = field(default_factory=list)


def daily_closing_balances(stmt: Statement) -> dict[date, float]:
    """Each calendar day in the statement period mapped to its ending balance.

    A thin view over `compute_average_daily_balance` so there is exactly one
    implementation of the daily ledger. Returns {} when no period or opening
    balance can be established.
    """
    result = compute_average_daily_balance(stmt)
    return {date.fromisoformat(d.date): d.ending_balance for d in result.daily_balances}


#: Every reading `_bank_reported_average_hypothesis` can return. Closed set:
#: an unrecognised gap is `unexplained`, which is a finding, not a gap in the
#: vocabulary.
BANK_REPORTED_AVERAGE_HYPOTHESES = (
    "agrees",
    "credit_only_floored",
    "collected_or_float",
    "beginning_of_day_alignment",
    "n_plus_1_zero_forward",
    "indeterminate_flat",
    "unexplained",
)


def _bank_reported_average_hypothesis(
    stmt: Statement, adb: AverageDailyBalanceResult, variance: float
) -> str:
    """Why the bank's printed average differs from the canonical ADB.

    DIAGNOSTIC, NEVER AUTHORITATIVE. Nothing selects a figure on the strength
    of this string; it exists so an analyst reading a variance is told what
    was already ruled in or out. Each discriminator is an exact identity
    against the same validated ledger, tested in this order, first match wins:

    `agrees`
        The variance is exactly zero. Tested first, so a coincidental match
        below can never be reported instead of the plain fact.
    `credit_only_floored`
        The printed figure equals this ledger's mean with every overdrawn day
        floored at zero - the "average credit balance" convention.
    `beginning_of_day_alignment`
        The printed figure equals this ledger's mean valued at the balance
        ENTERING each day rather than leaving it: an off-by-one-day alignment,
        not a different set of transactions.
    `n_plus_1_zero_forward`
        On a statement whose printed balance forward is zero, the printed
        figure equals the daily sum plus the opening balance, divided by ONE
        MORE day than the printed period. The bank counted the day the account
        opened; the printed period does not. Woodforest's observed convention,
        recorded as the bank's, never adopted as ours.
    `collected_or_float`
        No arithmetic identity holds, but the bank's own printed heading names
        a collected, available or float basis - money the posted ledger cannot
        see. The label is the discriminator here precisely because the
        arithmetic cannot be.
    `indeterminate_flat`
        The daily series carries ONE distinct end-of-day balance, so the
        alternates that re-slice that series cannot discriminate anything and
        must not be allowed to appear to. See below.
    `unexplained`
        None of the above. The honest answer, and the one worth investigating.

    THE FLAT-LEDGER GUARD, and why the two alternate-equality tests are the
    only ones it suppresses
    -----------------------------------------------------------------------
    When every day of the period closes on the same balance, `credit_only` and
    `beginning_of_day` stop being different computations: over a constant
    series they are that constant, exactly as the canonical figure is. The
    degenerate case is a ONE-DAY period, where "the mean of the balances
    ENTERING each day" is just the opening balance - so a bank that simply
    printed its opening balance was being reported as evidence of an
    off-by-one-day averaging convention. Reproduced on a one-day statement
    before this guard existed, which is why it exists.

    The guard suppresses those two and nothing else, because the other two
    discriminators do not degenerate. `n_plus_1_zero_forward` is a different
    identity over different terms - `(daily_sum + opening) / (days + 1)`,
    reachable only on a printed zero balance forward - and on a flat series it
    equals the constant only when the opening equals it too, in which case the
    variance is zero and `agrees` has already returned. `collected_or_float`
    reads the bank's own printed heading and does not touch the series at all.
    Suppressing either would lose the one explanation the mid-cycle
    account-opening class actually needs.
    """
    reported = _money(stmt.bank_reported_average_balance)
    if variance == 0.0:
        return "agrees"

    alternates = adb.underwriting_adb_alternates or {}
    # One distinct end-of-day balance across the period - see the guard above.
    flat = len({entry.ending_balance for entry in adb.daily_balances}) <= 1
    if not flat:
        for name, hypothesis in (
            ("credit_only", "credit_only_floored"),
            ("beginning_of_day", "beginning_of_day_alignment"),
        ):
            value = alternates.get(name)
            if value is not None and _money(value) == reported:
                return hypothesis

    if (
        stmt.beginning_balance is not None
        and _money(stmt.beginning_balance) == Decimal("0.00")
        and adb.daily_balance_sum is not None
        and adb.opening_balance is not None
        and adb.calendar_day_count
    ):
        extended = (
            Decimal(str(adb.daily_balance_sum)) + Decimal(str(adb.opening_balance))
        ) / Decimal(adb.calendar_day_count + 1)
        if _money(extended) == reported:
            return "n_plus_1_zero_forward"

    label = (stmt.bank_reported_average_label or "").lower()
    if any(word in label for word in ("collect", "avail", "float")):
        return "collected_or_float"
    # Nothing matched. On a flat series say so, rather than calling a gap
    # "unexplained" when the evidence that would explain it cannot exist.
    return "indeterminate_flat" if flat else "unexplained"


def _summary_debits_with_service_charge(stmt: Statement) -> float | None:
    if stmt.stated_total_debits is None:
        return None
    debits = round(stmt.stated_total_debits, 2)
    sc = stmt.stated_service_charge or 0.0
    if (
        sc
        and stmt.beginning_balance is not None
        and stmt.ending_balance is not None
        and stmt.stated_total_credits is not None
    ):
        interest = stmt.stated_interest_paid or 0.0
        base = stmt.beginning_balance + stmt.stated_total_credits - debits + interest
        separate_resid = round(base - sc - stmt.ending_balance, 2)
        folded_resid = round(base - stmt.ending_balance, 2)
        if abs(separate_resid) <= 1.00 and abs(folded_resid) > 1.00:
            debits = round(debits + sc, 2)
    return debits


def compute_metrics(
    stmt: Statement,
    *,
    trust_stated_summary: bool | None = None,
    trust_running_balances: bool = True,
    source_markdown: str | None = None,
    classifications: list[TransactionClassification] | None = None,
    withholding_denominator_mode: str = DEFAULT_WITHHOLDING_DENOMINATOR_MODE,
) -> Metrics:
    withholding_denominator_mode = normalize_withholding_denominator_mode(
        withholding_denominator_mode, default=DEFAULT_WITHHOLDING_DENOMINATOR_MODE
    )
    if withholding_denominator_mode not in WITHHOLDING_DENOMINATOR_MODES:
        raise ValueError(
            "withholding_denominator_mode must be legacy_eligible_deposits, "
            "verified_revenue or true_revenue"
        )
    m = Metrics()
    m.withholding_denominator_mode = withholding_denominator_mode
    m.stated_average_balance = stmt.bank_reported_average_balance
    m.stated_nsf_count = stmt.stated_nsf_count
    records = classifications if classifications is not None else classify_statement_transactions(stmt)
    if len(records) != len(stmt.transactions):
        raise ValueError("classification count must equal transaction count")
    confirmed_entities: set[str] = set()
    potential_entities: set[str] = set()
    flagged_counts: dict[str, int] = {}
    flagged_totals: dict[str, float] = {}
    flagged_credited_counts: dict[str, int] = {}
    flagged_credited_totals: dict[str, float] = {}
    flagged_payees: dict[str, set[str]] = {}
    posted_credits: list[PostedCredit] = []
    lender_rows: list[LenderRow] = []
    direction_conflict = False
    for t, classification in zip(stmt.transactions, records):
        if t.amount >= 0:
            m.total_deposits += t.amount
            m.num_deposits += 1
        else:
            m.total_withdrawals += -t.amount
            m.num_withdrawals += 1
        if classification.is_nsf_event:
            m.nsf_count += 1
        if classification.contributes_to_lender_credit_exclusion:
            m.lender_credits += abs(t.amount)
        lender_rows.append(LenderRow(
            t.amount,
            paid=classification.contributes_to_lender_totals,
            withheld=classification.contributes_to_withholding_rate,
            returned=bool(classification.returned_funder_payment_by),
            payoff_words=bool(classification.lump_sum_payoff),
            potential=classification.contributes_to_potential_lender_totals,
            insurance=classification.contributes_to_insurance_totals,
            record=classification,
        ))
        if classification.contributes_to_lender_count and classification.canonical_entity:
            confirmed_entities.add(classification.canonical_entity)
        if classification.contributes_to_potential_lender_count and classification.canonical_entity:
            potential_entities.add(classification.potential_payee_label or classification.canonical_entity)
        if classification.contributes_to_flagged_totals and classification.flagged_group:
            group_key = classification.flagged_group
            if t.amount < 0:
                flagged_counts[group_key] = flagged_counts.get(group_key, 0) + 1
                flagged_totals[group_key] = flagged_totals.get(group_key, 0.0) + abs(t.amount)
            else:
                flagged_credited_counts[group_key] = flagged_credited_counts.get(group_key, 0) + 1
                flagged_credited_totals[group_key] = flagged_credited_totals.get(group_key, 0.0) + t.amount
            flagged_payees.setdefault(group_key, set()).add(flagged_payee(classification))
        if t.amount > 0 and classification.is_posted:
            revenue_flags = (
                classification.contributes_to_verified_revenue,
                classification.contributes_to_unverified_deposit,
                classification.contributes_to_non_revenue,
            )
            if sum(revenue_flags) != 1:
                raise ValueError(
                    "every posted credit must contribute to exactly one revenue state"
                )
            # 5.6 (§5.4): every posted credit carries exactly one tier, and its tier agrees with its state.
            tier = classification.revenue_tier
            if tier is None or STATE_OF_TIER.get(tier) != classification.revenue_classification:
                raise ValueError(_TIER_DISAGREES)
            if classification.revenue_match_method == "direction_conflict":
                direction_conflict = True
            # The flag it carries picks the state bucket; nothing above compares it with revenue_classification.
            state = (
                "verified_revenue" if classification.contributes_to_verified_revenue
                else "unverified_deposit" if classification.contributes_to_unverified_deposit
                else "non_revenue"
            )
            posted_credits.append(
                PostedCredit(t.amount, state, tier, classification.revenue_tier_reason, classification)
            )
        counts_as_settled_activity = (
            classification.duplicate_of is None
            and not classification.settlement_reversal
            and classification.reversed_by is None
        )
        if classification.is_pos_purchase and counts_as_settled_activity:
            m.pos_count += 1
        if classification.is_pos_credit_or_refund and counts_as_settled_activity:
            m.pos_credit_count += 1
        if classification.is_atm_withdrawal and counts_as_settled_activity:
            m.atm_withdrawal_count += 1
        if classification.is_ach and counts_as_settled_activity:
            if t.amount >= 0:
                m.ach_credit_count += 1
            else:
                m.ach_debit_count += 1
        if classification.is_check and counts_as_settled_activity:
            m.check_count += 1
        if classification.is_loan_payment and counts_as_settled_activity:
            m.loan_count += 1
    m.total_deposits = round(m.total_deposits, 2)
    m.total_withdrawals = round(m.total_withdrawals, 2)
    m.lender_credits = round(m.lender_credits, 2)
    lender = lender_figures(lender_rows, accumulation="sequential")
    m.lender_debits, m.lender_debit_count, m.lender_evidence = lender.paid
    (m.returned_funder_payment_total, m.returned_funder_payment_count,
     m.returned_funder_payment_evidence) = lender.returned
    m.lump_sum_payoff_total, m.lump_sum_payoff_count = lender.payoff.total, lender.payoff.count
    m.potential_lender_debit_total, m.potential_lender_debit_count, m.potential_lender_evidence = lender.potential
    m.potential_lender_debits = m.potential_lender_debit_total
    m.monthly_lender_debits = m.lender_debits
    m.insurance_total, m.insurance_count, m.insurance_evidence = lender.insurance
    m.flagged_groups = {
        group.key: {
            "count": flagged_counts.get(group.key, 0),
            "total": round(flagged_totals.get(group.key, 0.0), 2),
            "count_credited": flagged_credited_counts.get(group.key, 0),
            "total_credited": round(flagged_credited_totals.get(group.key, 0.0), 2),
            "payees": len(flagged_payees[group.key]),
        }
        for group in FLAG_GROUPS
        if group.key in flagged_payees
    }
    revenue = revenue_buckets(posted_credits)
    states, tiers = revenue.states, revenue.tiers
    m.total_posted_credits, m.total_posted_credit_count = revenue.posted.total, revenue.posted.count
    m.verified_revenue_total, m.verified_revenue_count, m.verified_revenue_evidence = states["verified_revenue"]
    m.unverified_deposit_total, m.unverified_deposit_count, m.unverified_deposit_evidence = states["unverified_deposit"]
    m.non_revenue_total, m.non_revenue_count, m.non_revenue_evidence = states["non_revenue"]
    m.counted_flagged_total, m.counted_flagged_count, m.counted_flagged_evidence = tiers["counted_flagged"]
    (m.excluded_pending_review_total, m.excluded_pending_review_count,
     m.excluded_pending_review_evidence) = tiers["excluded_pending_review"]
    m.true_revenue_total = round(m.verified_revenue_total + m.counted_flagged_total, 2)
    m.true_revenue_count = m.verified_revenue_count + m.counted_flagged_count
    m.counted_flagged_by_reason = revenue.by_reason["counted_flagged"]
    m.excluded_pending_review_by_reason = revenue.by_reason["excluded_pending_review"]
    m.non_revenue_by_reason = revenue.by_reason["non_revenue"]
    m.revenue_review_items = m.excluded_pending_review_count
    m.confirmed_true_revenue_total = m.verified_revenue_total
    m.confirmed_true_revenue_count = m.verified_revenue_count
    m.confirmed_true_revenue = m.verified_revenue_total
    m.true_revenue = m.true_revenue_total
    m.potential_revenue_total = m.unverified_deposit_total
    m.potential_revenue_count = m.unverified_deposit_count
    m.true_revenue_evidence = [
        record for record in records
        if record.contributes_to_verified_revenue or record.contributes_to_counted_flagged
    ]
    m.potential_revenue_evidence = m.unverified_deposit_evidence
    m.maximum_revenue = round(
        m.verified_revenue_total + m.unverified_deposit_total,
        2,
    )
    # 5.6 (§5.1): the four-tier identity, verified + counted + held + non-revenue = posted credits.
    m.revenue_classified_total = round(
        m.verified_revenue_total
        + m.counted_flagged_total
        + m.excluded_pending_review_total
        + m.non_revenue_total,
        2,
    )
    m.revenue_classified_count = (
        m.verified_revenue_count
        + m.counted_flagged_count
        + m.excluded_pending_review_count
        + m.non_revenue_count
    )
    m.revenue_reconciliation_delta = round(
        m.revenue_classified_total - m.total_posted_credits,
        2,
    )
    m.revenue_reconciles = (
        m.revenue_reconciliation_delta == 0.0
        and m.revenue_classified_count == m.total_posted_credit_count
    )
    # Audit B11 (I31): the identity under its own name; `revenue_reconciles` is its deprecated alias.
    m.revenue_tiers_sum_to_posted = m.revenue_reconciles
    m.revenue_review_required = revenue_review_gate(
        direction_conflict=direction_conflict,
        held_total=m.excluded_pending_review_total,
        posted_total=m.total_posted_credits,
        tiers_sum_to_posted=m.revenue_tiers_sum_to_posted,
        true_total=m.true_revenue_total,
    )
    # Audit round 2, R2-B04 (R19): the statement's own names, so a statement with no transaction is read too.
    m.holder_unscreened = holder_unscreened(records, holder_name=stmt.holder_name, account_name=stmt.account_name)
    m.payer_text_unread, m.payer_text_unread_count = payer_text_unread(stmt.transactions, records)
    # Owner ruling 2026-10-02 (the underwriter's Q10), R2-OW11: the statement's own fields, as pass 7 reads them.
    m.premium_trust_account = premium_trust_title(
        getattr(stmt, "account_title", None), stmt.account_name, stmt.holder_name
    ) is not None
    m.lenders_detected = len(confirmed_entities)
    m.potential_lenders_detected = len(potential_entities)
    m.effective_total_deposits = m.total_deposits
    m.effective_total_withdrawals = m.total_withdrawals
    m.effective_num_deposits = m.num_deposits
    m.effective_num_withdrawals = m.num_withdrawals
    m.effective_nsf_count = 0
    m.nsf_source = NSF_UNAVAILABLE

    # Always compute the ADB working so the daily ledger and its validations are
    # available for audit, even when policy says not to report the figure.
    adb = compute_average_daily_balance(stmt, source_markdown=source_markdown)
    m.adb = adb
    m.calendar_day_count = adb.calendar_day_count
    m.adb_ok = (
        trust_running_balances and adb.ok
        if adb.daily_balances
        else None
    )
    m.daily_balance_sum = adb.daily_balance_sum if m.adb_ok else None
    for warning in adb.warnings:
        if warning not in m.notes:
            m.notes.append(warning)

    balances = (
        {d.date: d.ending_balance for d in adb.daily_balances}
        if m.adb_ok
        else {}
    )
    if balances:
        vals = list(balances.values())
        m.days_in_period = adb.calendar_day_count or len(vals)
        m.average_daily_balance = adb.underwriting_adb
        m.min_balance = round(min(vals), 2)
        m.max_balance = round(max(vals), 2)
        m.negative_days = negative_day_count(adb.daily_balances, carry_over=True)
        m.negative_printed_days = negative_day_count(adb.daily_balances, carry_over=False)
        m.effective_nsf_count = m.negative_printed_days   # R18, printed-day basis (owner ruling 2026-09-22)
        m.nsf_source = NSF_PRINTED
    elif trust_running_balances and adb.daily_balances:
        m.notes.append("not reporting average daily balance because its ledger validation failed")
    elif not trust_running_balances:
        m.notes.append("not computing average balance from line items because reconciliation failed")
    else:
        m.days_in_period = stmt.days_in_period
        m.notes.append("no validated daily ledger is available for average daily balance")

    if stmt.days_in_period is not None and m.days_in_period is None:
        m.days_in_period = stmt.days_in_period

    # The bank-reported-average comparison. Only when there is a publishable
    # ADB and a printed figure to compare it against - a withheld ledger has
    # no defensible left-hand side and gets no variance rather than a
    # misleading one.
    if (
        m.average_daily_balance is not None
        and stmt.bank_reported_average_balance is not None
    ):
        variance = _money(
            Decimal(str(m.average_daily_balance))
            - Decimal(str(stmt.bank_reported_average_balance))
        )
        m.bank_reported_average_variance = float(variance)
        reported = _money(stmt.bank_reported_average_balance)
        if reported:
            m.bank_reported_average_variance_pct = float(
                (variance / abs(reported) * Decimal("100")).quantize(Decimal("0.0001"))
            )
        m.bank_reported_average_hypothesis = _bank_reported_average_hypothesis(
            stmt, adb, m.bank_reported_average_variance
        )

    if trust_stated_summary is True:
        if stmt.stated_total_credits is not None:
            m.effective_total_deposits = round(stmt.stated_total_credits, 2)
            m.deposits_source = "bank_stated_reconciled"
        if stmt.stated_total_debits is not None:
            m.effective_total_withdrawals = _summary_debits_with_service_charge(stmt) or round(stmt.stated_total_debits, 2)
            m.withdrawals_source = "bank_stated_reconciled"
        if stmt.stated_credit_count is not None:
            m.effective_num_deposits = stmt.stated_credit_count
        if stmt.stated_debit_count is not None:
            m.effective_num_withdrawals = stmt.stated_debit_count
    elif trust_stated_summary is False and (
        stmt.stated_total_credits is not None or stmt.stated_total_debits is not None
    ):
        m.notes.append("ignored bank-stated deposit/debit totals because the summary did not reconcile")
    elif trust_stated_summary is None:
        if stmt.stated_total_credits is not None:
            m.effective_total_deposits = round(stmt.stated_total_credits, 2)
            m.deposits_source = "bank_stated_unverified"
        if stmt.stated_total_debits is not None:
            m.effective_total_withdrawals = round(stmt.stated_total_debits, 2)
            m.withdrawals_source = "bank_stated_unverified"
        if stmt.stated_credit_count is not None:
            m.effective_num_deposits = stmt.stated_credit_count
        if stmt.stated_debit_count is not None:
            m.effective_num_withdrawals = stmt.stated_debit_count

    if stmt.stated_nsf_count is not None and stmt.stated_nsf_count != m.nsf_count:
        m.notes.append(
            f"bank-stated NSF count {stmt.stated_nsf_count} differs from "
            f"{m.nsf_count} classified returned item(s); the underwriting NSF count is the negative-ending days (R18)"
        )
    if m.nsf_source == NSF_UNAVAILABLE:
        m.notes.append("NSF (negative-ending days) not computable: no validated daily ledger")
    m.cash_flow = round(m.effective_total_deposits - m.effective_total_withdrawals, 2)
    m.legacy_eligible_deposits = round(
        m.effective_total_deposits - m.lender_credits,
        2,
    )
    if withholding_denominator_mode == "verified_revenue":
        m.eligible_deposits = m.verified_revenue_total
        m.eligible_deposit_definition = "verified classified revenue"
        m.withholding_denominator_label = "Verified revenue"
    elif withholding_denominator_mode == "true_revenue":
        m.eligible_deposits = m.true_revenue_total
        m.eligible_deposit_definition = "true revenue: verified plus counted credits"
        m.withholding_denominator_label = "True revenue"
    else:
        m.eligible_deposits = m.legacy_eligible_deposits
        m.eligible_deposit_definition = "effective total deposits minus recognized lender funding credits"
        m.withholding_denominator_label = "Legacy eligible deposits"
    # R2-OW13 (the underwriter's Q5): every row the rate reads, the paid lender debits and the returned funder payments
    # still standing (lender_debits + returned_funder_payment_total, less the returned payments their funder re-debited
    # (`represented_by`; audit round 3, R3-B02, "Count it once"), to the cent).
    m.withholding_numerator = lender.withholding.total
    if m.returned_funder_payment_count:
        # The money in the statement's own unit (CURRENCY DOCTRINE: never a '$' on a CAD statement).
        unit = f" {stmt.currency}" if getattr(stmt, "currency", None) else ""
        # The owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once"; R3-B02): a returned payment the
        # same funder re-debited is out of the withholding rate, its re-debit counting the obligation once.
        re_debited = [record for record in m.returned_funder_payment_evidence
                      if getattr(record, "represented_by", None)]
        payments = f"{'payment' if m.returned_funder_payment_count == 1 else 'payments'}"
        if re_debited:
            re_debited_total = round(sum(abs(record.amount) for record in re_debited), 2)
            standing = m.returned_funder_payment_count - len(re_debited)
            m.notes.append(
                f"{m.returned_funder_payment_count} returned funder {payments} "
                f"({m.returned_funder_payment_total:,.2f}{unit}): out of paid to lenders; {len(re_debited)} re-debited "
                f"by its funder ({re_debited_total:,.2f}{unit}), counted once by the re-debit"
                + (f"; {standing} kept in the withholding rate" if standing else "")
            )
        else:
            m.notes.append(
                f"{m.returned_funder_payment_count} returned funder {payments} "
                f"({m.returned_funder_payment_total:,.2f}{unit}): out of paid to lenders, kept in the withholding rate"
            )
    if m.lump_sum_payoff_count:
        # The owner's answer of 2026-10-07 to audit round 3's R3-79 ("Exclude worded payoffs (Recommended)"; R3-B03): the
        # lump sums out of the withholding rate, in the statement's own unit.
        unit = f" {stmt.currency}" if getattr(stmt, "currency", None) else ""
        payments = "payment" if m.lump_sum_payoff_count == 1 else "payments"
        m.notes.append(
            f"{m.lump_sum_payoff_count} lump-sum {payments} to confirmed lenders ({m.lump_sum_payoff_total:,.2f}{unit}): "
            "in paid to lenders, not in the withholding rate"
        )
    m.withholding_denominator = m.eligible_deposits
    m.potential_withholding_numerator = m.potential_lender_debit_total
    m.potential_withholding_denominator = m.eligible_deposits
    m.potential_withholding_review_required = m.potential_lender_debit_count > 0
    # Owner ruling 2026-10-02 (the underwriter's Q7; R2-OW14): the notes name the basis the rate divides by, True revenue
    # by default. Audit round 3, R3-B03 (R3-20): a True or Verified basis under WITHHOLDING_BASIS_FLOOR is read as $0 is
    # (no rate, no exposure, the review flag and a note naming the basis and the floor); the legacy basis bypasses it.
    basis_unit = f" {stmt.currency}" if getattr(stmt, "currency", None) else ""
    m.withholding_basis_below_floor = withholding_basis_below_floor(
        m.withholding_denominator, withholding_denominator_mode)
    if not withholding_basis_publishable(m.withholding_denominator, withholding_denominator_mode):
        m.withholding_review_required = True
        m.notes.append(withholding_unavailable_note(m.withholding_denominator_label, m.withholding_denominator,
                                                    basis_unit))
    else:
        m.withholding_rate = (
            abs(m.withholding_numerator) / m.withholding_denominator
        ) * 100
    if not withholding_basis_publishable(m.potential_withholding_denominator, withholding_denominator_mode):
        if m.potential_lender_debit_count:
            m.notes.append(potential_withholding_unavailable_note(
                m.withholding_denominator_label, m.potential_withholding_denominator, basis_unit))
    else:
        m.potential_withholding_exposure = (
            abs(m.potential_withholding_numerator) / m.potential_withholding_denominator
        ) * 100
    return m

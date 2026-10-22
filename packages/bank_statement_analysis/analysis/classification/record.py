"""TransactionClassification, states, version, FundingSeries, DealerFunding, CounterDebitReading."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from statistics import mean, pstdev
from typing import Literal, Sequence

from analysis.dates import parse_date
from analysis.flag_groups import FLAG_GROUP_BY_KEY
from analysis.revenue import RevenueState, revenue_contribution_flags, tier_of_state


ClassificationState = Literal[
    "confirmed_lender",
    "potential_lender",
    "insurance",
    "alternative_position",
    "line_of_credit",
    "vehicle_financing",
    "bank_loan",
    "mortgage",
    "lease_or_rental",
    "personal_loan",
    "floor_plan_financing",
    "factoring",
    "debt_relief",
    # Retired in classification version 5.0: no rule produces it, but records
    # stored before 5.0 carry it and must still validate (spec §4.1).
    "lease_or_equipment_financing",
    "fee",
    "transfer",
    "credit_card_payment",
    "payroll",
    "tax",
    "utility",
    "rent",
    "pos",
    "atm",
    "nsf_or_return",
    "refund_or_reversal",
    "other",
]

CLASSIFICATION_STATES: tuple[ClassificationState, ...] = (
    "confirmed_lender",
    "potential_lender",
    "insurance",
    "alternative_position",
    "line_of_credit",
    "vehicle_financing",
    "bank_loan",
    "mortgage",
    "lease_or_rental",
    "personal_loan",
    "floor_plan_financing",
    "factoring",
    "debt_relief",
    "lease_or_equipment_financing",
    "fee",
    "transfer",
    "credit_card_payment",
    "payroll",
    "tax",
    "utility",
    "rent",
    "pos",
    "atm",
    "nsf_or_return",
    "refund_or_reversal",
    "other",
)

#: Bump when a stored classification, tier, reason or review-gate reading changes: an analysis saved under an
#: older value gets the re-analyze notice. Compared as numbers (5.10 is newer than 5.9). Bump
#: `webapp.artifact_cache.ANALYSIS_STAGE_VERSION` in the same commit.
CLASSIFICATION_VERSION = "5.9"

#: The entity of an unknown obligation whose descriptor names no organisation (D11).
UNIDENTIFIED_LENDER_OBLIGATION = "Unidentified lender obligation"

#: The fixed D10 name of an MCA SERVICING payee. The two words print for two unrelated funders, so no D11 name
#: is ever built from them.
UNIDENTIFIED_MCA_SERVICER = "MCA servicer (funder not identified)"


@dataclass(frozen=True)
class _RevenueDecision:
    classification: RevenueState
    canonical_entity: str | None
    match_method: str
    matched_alias: str | None
    matched_rule: str
    confidence_score: float
    reason: str
    source_type: str | None = None
    context_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransactionClassification:
    original_description: str
    normalized_description: str
    classification: ClassificationState
    date: str = ""
    amount: float = 0.0
    direction: str = "debit"
    bank: str | None = None
    account: str | None = None
    account_name: str | None = None
    #: The statement's holder name (Statement.holder_name); the holder tests read
    #: holder_reading(account_name, holder_name).
    holder_name: str | None = None
    source_direction: str | None = None
    direction_consistent: bool = True
    source_page: int | None = None
    source_location: str | None = None
    canonical_entity: str | None = None
    match_method: str = "default"
    matched_alias: str | None = None
    matched_rule: str | None = None
    confidence_score: float = 0.5
    reason: str = "No higher-confidence classification rule matched."
    is_posted: bool = True
    review_required: bool = False
    # Spec §4.2: the FlagGroup.key of a flag-group state, otherwise None.
    flagged_group: str | None = None
    revenue_classification: RevenueState | None = None
    revenue_initial_classification: RevenueState | None = None
    revenue_canonical_entity: str | None = None
    revenue_match_method: str | None = None
    revenue_matched_alias: str | None = None
    revenue_matched_rule: str | None = None
    revenue_confidence_score: float | None = None
    revenue_reason: str | None = None
    revenue_source_type: str | None = None
    revenue_context_signals: tuple[str, ...] = ()
    revenue_related_transaction: str | None = None
    revenue_review_required: bool = False
    revenue_review_status: str | None = None
    revenue_review_note: str | None = None
    revenue_reviewed_at: str | None = None
    duplicate_of: str | None = None
    reversal_of: str | None = None
    reversed_by: str | None = None
    settlement_reversal: bool = False
    # True revenue spec §6.2, §9.1, §11: a confirmed funder's payment the bank returned unpaid. On the DEBIT, the
    # return credit's location: the row leaves paid to lenders (contributes_to_lender_totals) and stays in the
    # withholding rate and the lender count. On the CREDIT, the debit's location; its revenue reading is untouched.
    # None on every other row.
    returned_funder_payment_by: str | None = None
    returns_funder_payment: str | None = None
    # True revenue spec §6.2 pass 7c, §11: on a returned funder payment's DEBIT, the location of the same funder's
    # re-debit that re-presented it or caught it up 2x; the debit then leaves the withholding rate
    # (contributes_to_withholding_rate False), the re-debit counting the obligation once. None on every other row.
    represented_by: str | None = None
    # True revenue spec §9.1, §11: on a confirmed funder's paid debit whose own text prints a payoff word (PAYOFF, PAY
    # OFF, PAY-OFF, PREPAY, PRE-PAY, PREPAYMENT, BUYOUT, BUY OUT, PAYOUT; LUMP_SUM_PAYOFF_WORDS), the word as the bank
    # printed it; the debit is a lump sum out of the withholding rate (contributes_to_withholding_rate False), still in
    # paid to lenders and the lender count. None on every other row, a returned one included (Q5 keeps it in the rate).
    lump_sum_payoff: str | None = None
    contributes_to_lender_count: bool = False
    contributes_to_potential_lender_count: bool = False
    contributes_to_lender_totals: bool = False
    contributes_to_withholding_rate: bool = False
    contributes_to_potential_lender_totals: bool = False
    contributes_to_potential_withholding_exposure: bool = False
    contributes_to_insurance_totals: bool = False
    # Spec §4.2: a posted flag-group debit; cleared for proven duplicates and
    # settlement-reversed debits. Never read by lender, withholding or revenue math.
    contributes_to_flagged_totals: bool = False
    contributes_to_verified_revenue: bool = False
    contributes_to_unverified_deposit: bool = False
    contributes_to_true_revenue: bool = False
    contributes_to_potential_revenue: bool = False
    contributes_to_non_revenue: bool = False
    contributes_to_lender_credit_exclusion: bool = False
    is_ach: bool = False
    is_check: bool = False
    is_loan_payment: bool = False
    is_pos_context: bool = False
    classification_version: str = CLASSIFICATION_VERSION
    # The Potential Lenders line of an unnamed potential payee, one per payee key within the statement
    # ('Unidentified lender obligation (weekly, 450.00)'). None for every other row, whose line is its
    # canonical_entity.
    potential_payee_label: str | None = None
    # True revenue spec §9.1: on every potential_lender row, named or not, its payee's amount-free key (an opaque
    # digest of the entity, D6's payee words and the masked recipient: no payee word is published), which
    # analysis.lender_payment_changes reads to follow a payee across an amount change; nothing else reads it. None for
    # every other row.
    potential_payee_key: str | None = None
    # True revenue spec §5.4: the per-row contract. Every posted credit carries exactly one tier (verified,
    # counted_flagged, excluded_pending_review, non_revenue); a counted or held row carries its reason code
    # (analysis.revenue.REVENUE_TIER_REASONS). The initial tier is the one the rules gave, which a reset restores.
    revenue_tier: str | None = None
    revenue_initial_tier: str | None = None
    revenue_tier_reason: str | None = None
    contributes_to_counted_flagged: bool = False
    contributes_to_excluded_pending_review: bool = False
    # True revenue spec §5.4, §8.5: on a held wire with no sender printed (`wire_no_sender`), each Lenders or
    # Potential Lenders series that starts after it (pass 7's last step, analysis.true_revenue.funding_series_after);
    # () on every other row. A review aid: no tier, state, flag, figure or gate reads it. Serialized as a list of
    # objects.
    revenue_funding_series: tuple[FundingSeries, ...] = ()

    @property
    def is_pos_purchase(self) -> bool:
        return self.classification == "pos" and self.amount < 0

    @property
    def is_pos_credit_or_refund(self) -> bool:
        return self.classification == "refund_or_reversal" and self.is_pos_context

    @property
    def is_nsf_event(self) -> bool:
        return self.classification == "nsf_or_return"

    @property
    def is_atm_withdrawal(self) -> bool:
        return self.classification == "atm" and self.amount < 0

    @property
    def categories(self) -> tuple[str, ...]:
        categories: list[str] = [self.classification]
        if self.is_pos_purchase:
            categories.append("pos_purchase")
        if self.is_pos_credit_or_refund:
            categories.append("pos_credit_or_refund")
        if self.is_nsf_event:
            categories.append("nsf_event")
        if self.is_atm_withdrawal:
            categories.append("atm_withdrawal")
        return tuple(categories)


def classify_cadence(dates: list[date]) -> tuple[str, float | None]:
    ordered = sorted(set(dates))
    gaps = [(b - a).days for a, b in zip(ordered, ordered[1:]) if (b - a).days > 0]
    if not gaps:
        return "irregular", None
    average = mean(gaps)
    spread = pstdev(gaps) if len(gaps) > 1 else 0.0
    if average <= 1.6 and spread <= 1.5:
        return "daily", round(average, 1)
    if 5 <= average <= 9 and spread <= 2.5:
        return "weekly", round(average, 1)
    return "irregular", round(average, 1)


def flagged_payee(record: TransactionClassification) -> str:
    """The payee a flagged row is grouped under: its entity, else its group's label (spec §6)."""
    if record.canonical_entity:
        return record.canonical_entity
    group = FLAG_GROUP_BY_KEY.get(record.flagged_group or "")
    return group.label if group is not None else (record.flagged_group or "")


def _replace_revenue_state(
    record: TransactionClassification,
    state: RevenueState,
    *,
    match_method: str,
    matched_rule: str,
    confidence_score: float,
    reason: str,
    context_signals: Sequence[str],
    related_transaction: str | None = None,
) -> TransactionClassification:
    return replace(
        record,
        revenue_classification=state,
        revenue_initial_classification=state,
        revenue_tier=tier_of_state(state),
        revenue_initial_tier=tier_of_state(state),
        revenue_tier_reason=None,
        revenue_match_method=match_method,
        revenue_matched_rule=matched_rule,
        revenue_confidence_score=confidence_score,
        revenue_reason=reason,
        revenue_context_signals=tuple(dict.fromkeys(context_signals)),
        revenue_related_transaction=related_transaction,
        revenue_review_required=state == "unverified_deposit",
        revenue_review_status=(
            "pending" if state == "unverified_deposit" else "not_required"
        ),
        **revenue_contribution_flags(state, tier_of_state(state)),
    )


@dataclass(frozen=True)
class CounterDebitReading:
    """How passes 6 and 7 compare a payer with a posted debit. `legacy` is the 5.6 first distinctive word
    (_payer_first_distinctive_word, _debit_word_reading); a transfer, wire, person-to-person or lender debit still
    matches on it. `keys` are the B4 forms: the first distinctive word read without _COUNTER_DEBIT_GENERIC_WORDS, a
    three-letter payroll provider allowed, and that word glued to the next one or two ('CONTOSO RIDGE' matches
    'CONTOSORIDGE'), read on the text as printed and with its glued digit runs split off. `heads` are each first word
    with the words after it, which payer_debited_as_lender's prefix comparison reads. §5.2, §8.1: `number`, a numbered
    company's number (Quebec's NNNN NNNN joined), read only where the numbered-company form prints
    (counter_debit_payer_reading, counter_debit_debit_reading; never any digits alone), which true_revenue._same_payer
    matches before the words: a numbered company's words are a province and a legal form, which name no payer."""

    legacy: str | None
    keys: frozenset[str]
    heads: tuple[tuple[str, tuple[str, ...]], ...]
    number: str | None = None


_NO_COUNTER_DEBIT_READING = CounterDebitReading(None, frozenset(), ())


def _promotion_cadence(
    records: list[TransactionClassification],
    indexes: list[int],
    min_recurring_count: int,
) -> tuple[str, float | None] | None:
    """The daily or weekly cadence of a same-amount group, or None when it does not promote.

    A recurrence needs at least ``min_recurring_count`` different dates: several
    rows on one day are one occurrence, as classify_cadence reads them.
    """
    if len(indexes) < min_recurring_count:
        return None
    dates = [parsed for index in indexes if (parsed := parse_date(records[index].date)) is not None]
    if len(set(dates)) < min_recurring_count:
        return None
    cadence, average_gap = classify_cadence(dates)
    if cadence not in {"daily", "weekly"}:
        return None
    return cadence, average_gap


@dataclass(frozen=True)
class DealerFunding:
    """§6.1 step 4 (Q7): a dealer-funding credit's reading. `arm` is 'listed' or 'credit_union'; `entity` and `alias`
    are the listed lender and the alias that named it, or the credit union as its payer region prints it (both the
    same); `word` is the dealer-funding word (or the VHCL PURCH entry) the row prints."""

    arm: str
    entity: str
    alias: str
    word: str


@dataclass(frozen=True)
class FundingSeries:
    """§5.4, §8.5: one lender's daily or weekly payment series that starts after a held wire with no sender printed,
    the review aid's line ("possible funding").

    `payee` is the name the Lenders or Potential Lenders tab lists (the potential payee label, else the canonical
    entity; never a payee word for an unnamed payee, D11); `lender_state` its tab's state (`confirmed_lender` or
    `potential_lender`); `amount` the payment, positive; `cadence` daily or weekly and `average_gap_days` its mean gap
    (classify_cadence); `first_date` the first payment's date as printed and `days_after` its days after the deposit;
    `payments` its distinct dates; `start_observed` whether the statement shows one full gap of the series before the
    deposit; `source_locations` its rows."""

    payee: str
    lender_state: str
    amount: float
    cadence: str
    average_gap_days: float
    first_date: str
    days_after: int
    payments: int
    start_observed: bool
    source_locations: tuple[str, ...]

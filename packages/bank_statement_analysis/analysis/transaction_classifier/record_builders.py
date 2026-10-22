"""_build_record and the debit and credit record builders."""
from __future__ import annotations

import re

from analysis.classification.credit_predicates import _reversal_credit
from analysis.classification.record import ClassificationState, DealerFunding, TransactionClassification
from analysis.descriptor.credit_words import _MICRO_DEPOSIT_FLOOR
from analysis.descriptor.lexical import revenue_text
from analysis.descriptor.rails import _matches_any, _state_words
from analysis.descriptor.words import (
    _CHECK_PATTERNS,
    _EXPLICIT_REPAYMENT_PATTERNS,
    _FLAGGED_REVENUE_CREDIT_STATES,
    _LINE_OF_CREDIT_PATTERNS,
    _POS_PATTERNS,
)
from analysis.flag_groups import FLAG_GROUP_BY_STATE
from analysis.payee_matcher import PayeeMatch
from analysis.revenue import revenue_contribution_flags, tier_of_state
from analysis.transaction_classifier.credit_decision import _classify_credit_revenue
from analysis.transaction_classifier.obligations import lump_sum_payoff_words
from analysis.true_revenue.dealer import dealer_funding_reading


#: The ACH token, compiled once (it used to be re-normalized on every row).
_ACH_TOKEN = re.compile(r"(?<![A-Z0-9])ACH(?![A-Z0-9])")


def _build_record(
    *,
    description: str,
    text: str,
    classification: ClassificationState,
    amount: float,
    date_value: str,
    bank: str | None,
    account: str | None,
    account_name: str | None,
    source_direction: str | None,
    direction_consistent: bool,
    source_page: int | None,
    source_location: str | None,
    holder_name: str | None = None,
    canonical_entity: str | None = None,
    match_method: str,
    matched_alias: str | None = None,
    matched_rule: str | None = None,
    confidence_score: float,
    reason: str,
    is_posted: bool = True,
    review_required: bool = False,
    contributes_to_lender_credit_exclusion: bool = False,
    flagged_group: str | None = None,
    category_text: str | None = None,
) -> TransactionClassification:
    # The is_check, is_ach and is_pos_context flags read the category chain's text (a credit without its statement
    # furniture, classify_transaction); the row's text where none is given.
    flags_text = text if category_text is None else category_text
    is_debit = amount < 0
    contributes_lender = classification == "confirmed_lender" and is_debit and is_posted
    # A confirmed funder's paid debit printing a payoff word is a lump sum, in paid to lenders and the lender count and
    # out of the withholding numerator, beside the contribution flags. Potential lenders and every other row are
    # unchanged.
    lump_sum_payoff = lump_sum_payoff_words(description, text) if contributes_lender else None
    contributes_potential = classification == "potential_lender" and is_debit and is_posted
    contributes_insurance = classification == "insurance" and is_debit and is_posted
    flag_group = FLAG_GROUP_BY_STATE.get(classification)
    # A flag-group state names its own group. Premium financing is the one group
    # a rule passes in, on an insurance row.
    group_key = flag_group.key if flag_group is not None else flagged_group
    # A posted debit of a flag group counts in the flagged totals, and so does a
    # posted credit of a group whose credits are flagged revenue (factoring; C5
    # count_credited and total_credited).
    contributes_flagged = group_key is not None and is_posted and (
        is_debit or (amount > 0 and classification in _FLAGGED_REVENUE_CREDIT_STATES)
    )
    revenue = _classify_credit_revenue(
        text,
        amount,
        posted=is_posted,
        bank=bank,
        account_name=account_name,
        direction_consistent=direction_consistent,
        holder_name=holder_name,
        description=description,
    )
    revenue_state = revenue.classification if revenue is not None else None
    revenue_tier = tier_of_state(revenue_state)
    revenue_flags = revenue_contribution_flags(revenue_state, revenue_tier)
    # Contract C4, spec §4.4: a credit whose revenue decision is financing proceeds (D1) is
    # also excluded from eligible deposits, whichever rule named the row. A transfer or an
    # insurance term can claim a financing group's credit before step 7. A payout-credit
    # entity's credit and a premium-finance payee's credit never reach this revenue decision.
    if revenue is not None and revenue.match_method == "financing_proceeds_credit":
        contributes_to_lender_credit_exclusion = True
    return TransactionClassification(
        original_description=description,
        normalized_description=text,
        classification=classification,
        date=date_value,
        amount=amount,
        direction="debit" if amount < 0 else "credit",
        bank=bank,
        account=account,
        account_name=account_name,
        holder_name=holder_name,
        source_direction=source_direction,
        direction_consistent=direction_consistent,
        source_page=source_page,
        source_location=source_location,
        canonical_entity=canonical_entity,
        match_method=match_method,
        matched_alias=matched_alias,
        matched_rule=matched_rule,
        confidence_score=confidence_score,
        reason=reason,
        is_posted=is_posted,
        review_required=review_required,
        flagged_group=group_key,
        revenue_classification=revenue_state,
        revenue_initial_classification=revenue_state,
        revenue_tier=revenue_tier,
        revenue_initial_tier=revenue_tier,
        revenue_canonical_entity=revenue.canonical_entity if revenue else None,
        revenue_match_method=revenue.match_method if revenue else None,
        revenue_matched_alias=revenue.matched_alias if revenue else None,
        revenue_matched_rule=revenue.matched_rule if revenue else None,
        revenue_confidence_score=revenue.confidence_score if revenue else None,
        revenue_reason=revenue.reason if revenue else None,
        revenue_source_type=revenue.source_type if revenue else None,
        revenue_context_signals=revenue.context_signals if revenue else (),
        revenue_review_required=revenue_state == "unverified_deposit",
        revenue_review_status=(
            "pending" if revenue_state == "unverified_deposit"
            else "not_required" if revenue_state else None
        ),
        lump_sum_payoff=lump_sum_payoff,
        contributes_to_lender_count=contributes_lender,
        contributes_to_potential_lender_count=contributes_potential,
        contributes_to_lender_totals=contributes_lender,
        contributes_to_withholding_rate=contributes_lender and lump_sum_payoff is None,
        contributes_to_potential_lender_totals=contributes_potential,
        contributes_to_potential_withholding_exposure=contributes_potential,
        contributes_to_insurance_totals=contributes_insurance,
        contributes_to_flagged_totals=contributes_flagged,
        **revenue_flags,
        contributes_to_lender_credit_exclusion=contributes_to_lender_credit_exclusion,
        is_ach=_ACH_TOKEN.search(flags_text) is not None,
        is_check=_matches_any(flags_text, _CHECK_PATTERNS),
        is_loan_payment=_matches_any(text, _EXPLICIT_REPAYMENT_PATTERNS),
        is_pos_context=_matches_any(flags_text, _POS_PATTERNS),
    )


#: D9: known-payee groups that LOC wording moves to lines of credit.
_LOC_OVERRIDE_STATES = frozenset({"confirmed_lender", "alternative_position", "line_of_credit"})


def _field_order_debit_record(
    common: dict[str, object],
    text: str,
    match: PayeeMatch,
) -> TransactionClassification:
    """A debit to a payee read from the bank's fields: its group (D9's LOC wording still wins), with no alias."""
    if match.state in _LOC_OVERRIDE_STATES and _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        state, rule = "line_of_credit", "line_of_credit_descriptor_override"
    else:
        state, rule = match.state, f"{match.state}_field_order"
    return _build_record(
        **common,
        classification=state,
        canonical_entity=match.entity,
        match_method="known_payee_field_order",
        matched_rule=rule,
        confidence_score=0.97,
        reason=(
            f"The bank printed the originator and the entry description of {match.entity} in separate fields; "
            f"read from those fields, the row is {_state_words(state)}."
        ),
    )


def _known_payee_debit_record(
    common: dict[str, object],
    text: str,
    match: PayeeMatch,
) -> TransactionClassification:
    """Spec §4.3 step 7 and D9: a debit to a known payee takes the payee's group."""
    if match.state in _LOC_OVERRIDE_STATES and _matches_any(text, _LINE_OF_CREDIT_PATTERNS):
        return _build_record(
            **common,
            classification="line_of_credit",
            canonical_entity=match.entity,
            match_method="known_payee_alias",
            matched_alias=match.alias,
            matched_rule="line_of_credit_descriptor_override",
            confidence_score=0.97,
            reason=(
                f"Matched maintained {_state_words(match.state)} alias '{match.alias}', and the "
                "descriptor says LOC or line of credit, so the row is a line of credit (D9)."
            ),
        )
    if match.state == "confirmed_lender":
        return _build_record(
            **common,
            classification="confirmed_lender",
            canonical_entity=match.entity,
            match_method="verified_lender_alias",
            matched_alias=match.alias,
            matched_rule="confirmed_lender_registry",
            confidence_score=0.99,
            reason=f"Matched maintained lender alias '{match.alias}' after all strong exclusions.",
        )
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="known_payee_alias",
        matched_alias=match.alias,
        matched_rule=f"{match.state}_registry",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}'; "
            "it is a flagged obligation and never enters lender math."
        ),
    )


def _q7_dealer_funding(text: str, amount: float, direction_consistent: bool) -> DealerFunding | None:
    """§6.1: the credit's dealer-funding reading, read as _classify_credit_revenue reads it: a credit of $1 or more
    whose direction agrees and that no reversal marker claims (steps 2 and 3 win), which dealer_funding_reading reads
    on its revenue text; or None."""
    if amount < _MICRO_DEPOSIT_FLOOR or not direction_consistent:
        return None
    revenue = revenue_text(text)
    dealer = dealer_funding_reading(revenue)
    return None if dealer is None or _reversal_credit(revenue) else dealer


def _dealer_funding_credit_record(
    common: dict[str, object],
    dealer: DealerFunding,
) -> TransactionClassification:
    """A dealer-funding credit's record keeps its lender, as the financing-proceeds record it replaces did: the listed
    auto lender and its alias, or the credit union its payer region prints. A listed lender's dealer funding is never
    financing proceeds (D1), so it leaves the lender credits; a credit union's VHCL PURCH entry is decided by the
    statement pass (two or more verify, one alone is held)."""
    if dealer.arm == "listed":
        method, rule, confidence = "auto_lender_dealer_funding", "auto_lender_dealer_funding_credit", 0.90
        reason = (
            f"Matched listed auto lender '{dealer.entity}' (alias '{dealer.alias}') on a dealer-funding credit "
            f"({dealer.word}): the lender pays the dealer on a vehicle contract it financed, the dealer's revenue, "
            "never financing proceeds."
        )
    else:
        method, rule, confidence = "credit_union_vehicle_purchase", "credit_union_vehicle_purchase_credit", 0.60
        reason = (
            f"Credit union '{dealer.entity}' prints the {dealer.word} entry, a credit union's funding of a dealer's "
            "indirect auto loan; the statement pass counts such credits (two or more are dealer funding, one alone "
            "is held)."
        )
    return _build_record(
        **common,
        classification="other",
        canonical_entity=dealer.entity,
        match_method=method,
        matched_alias=dealer.alias,
        matched_rule=rule,
        confidence_score=confidence,
        reason=reason,
    )


def _financing_proceeds_credit_record(
    common: dict[str, object],
    amount: float,
    match: PayeeMatch,
) -> TransactionClassification:
    """D1: a credit from a financing group is proceeds, excluded from eligible deposits."""
    return _build_record(
        **common,
        classification="other",
        canonical_entity=match.entity,
        match_method="financing_proceeds_credit",
        matched_alias=match.alias,
        matched_rule="financing_proceeds_credit",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}' on a credit; "
            "financing proceeds are excluded from lender debits and eligible deposits."
        ),
        contributes_to_lender_credit_exclusion=amount > 0,
    )


def _flagged_revenue_credit_record(
    common: dict[str, object],
    match: PayeeMatch,
) -> TransactionClassification:
    """A factoring payee's credit is the business's own sales, paid by the factor.

    The row takes the payee's group, so it carries the group's flag and counts in
    the flagged totals as a credit. Its revenue decision is the operating-revenue
    path's (the payee is skipped there), so it is never financing proceeds and it
    stays in eligible deposits.
    """
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="known_payee_alias",
        matched_alias=match.alias,
        matched_rule=f"{match.state}_revenue_credit",
        confidence_score=0.97,
        reason=(
            f"Matched maintained {_state_words(match.state)} alias '{match.alias}' on a credit: a "
            "factor's payout is the business's own sales, so it stays revenue and in eligible "
            "deposits, and it is flagged as a factoring position (owner ruling)."
        ),
    )


def _unconfirmed_factoring_credit_record(
    common: dict[str, object],
    match: PayeeMatch,
) -> TransactionClassification:
    """A factoring review entity's credit is a factor's payout, as an admitted factor's is
    (_flagged_revenue_credit_record): the row takes the factoring group, carries its flag and counts in the flagged
    totals as a credit, and its revenue decision is the operating-revenue path's. The ledger has not confirmed the
    factor, so the row is marked unconfirmed (review_required), as a 5.3 review entity's debit is. Its debits keep the
    potential tier."""
    return _build_record(
        **common,
        classification=match.state,
        canonical_entity=match.entity,
        match_method="unconfirmed_flag_payee_alias",
        matched_alias=match.alias,
        matched_rule="factoring_review_revenue_credit",
        confidence_score=0.82,
        reason=(
            f"Matched maintained candidate alias '{match.alias}' of an unconfirmed factor on a credit: a factor's "
            "payout is the business's own sales, so it stays revenue and in eligible deposits; it is flagged as a "
            "factoring position, marked unconfirmed."
        ),
        review_required=True,
    )


def _descriptor_proceeds_credit_record(
    common: dict[str, object],
    amount: float,
    proceeds: tuple[str, bool],
    bank: str | None,
) -> TransactionClassification:
    """D1 by descriptor: the credit's own words say it is financing proceeds."""
    rule, names_bank = proceeds
    return _build_record(
        **common,
        classification="other",
        canonical_entity=(bank or None) if names_bank else None,
        match_method="financing_proceeds_credit",
        matched_rule=rule,
        confidence_score=0.95,
        reason=(
            f"The credit's descriptor identifies financing proceeds ({_state_words(rule)}); they are "
            "excluded from lender debits and eligible deposits."
        ),
        contributes_to_lender_credit_exclusion=amount > 0,
    )

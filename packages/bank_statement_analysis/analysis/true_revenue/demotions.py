"""Card-payout processors and the never-verified demotions."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Sequence, TYPE_CHECKING

from analysis.classification.credit_predicates import _reversal_credit
from analysis.classification.record import _replace_revenue_state
from analysis.classification_registry import CARD_PAYOUT_PROCESSOR_NAMES
from analysis.descriptor.credit_words import (
    CUSTOMER_FINANCING_LUMP_FLOOR,
    CUSTOMER_FINANCING_LUMP_ROUND,
    CUSTOMER_FINANCING_LUMP_SHARE,
    CUSTOMER_FINANCING_SERIES_MIN,
    CUSTOMER_FINANCING_SERIES_SHARE,
    _CARD_CREDIT_PUSH_WORD,
)
from analysis.descriptor.lexical import _before_receiver, _is_payer_word, revenue_text
from analysis.descriptor.rails import _matches_any
from analysis.descriptor.words import _CONSUMER_P2P_RAIL, _ELECTRONIC_PAYMENT_FORM, _POS_PATTERNS, _PUSH_RAIL
from analysis.true_revenue.counter_debit_pairing import _cents
from analysis.true_revenue.words import (
    CONSTRUCTION_PROGRESS_DRAW_REASON,
    CUSTOMER_FINANCING_PAYOUT,
    LENDER_PAID_FOR_SERVICES,
    _CARD_CREDIT_LABEL,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.1: a card credit printed first, BMO's and Regions' 'CARD CREDIT ...': a refund to the card, or a push the parser
#: cut from its payer (BMO prints the merchant on a line the parser drops), held as a possible return unless a push or
#: person-to-person rail is printed (Regions' 'CARD CREDIT CASH APP ...' and '... APPLE CASH ...' stay Q4's counted
#: pushes).
_LEADING_CARD_CREDIT = re.compile(r"^(?:\d{1,2} \d{1,2} )?CARD CREDIT\b")
_CARD_PAYOUT_LABEL = re.compile(r"(?<![A-Z])(?:DEBIT CARD CREDIT?|POS CREDIT)\b")
_CARD_PAYOUT_NAMES = {
    entity: re.compile(
        r"(?<![A-Z])(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r")(?![A-Z])"
    )
    for entity, names in CARD_PAYOUT_PROCESSOR_NAMES.items()
}


#: §8.1: the method and the matched rule pass 7 gives a settlement under the merchant's own name that an earlier rule
#: verified and that only the bare settlement word lifted from the own-push guard (_settlement_never_verified).
HOLDER_NAMED_SETTLEMENT_METHOD = "holder_named_settlement"
HOLDER_NAMED_SETTLEMENT_RULE = "holder_named_settlement_never_verified"


def _leading_card_credit(text: str) -> bool:
    """§8.1: a card credit printed first ('CARD CREDIT', BMO's with its merchant line dropped, or Regions' 'CARD
    CREDIT <merchant>'), with no push word (§7.11's) and no person-to-person or push rail (Cash App and Apple Cash are
    person-to-person rails, so Regions' pushes stay counted): held as a possible return."""
    row = _before_receiver(text)
    return _LEADING_CARD_CREDIT.match(row) is not None and not (
        _CARD_CREDIT_PUSH_WORD.search(row)
        or _CONSUMER_P2P_RAIL.search(row)
        or _PUSH_RAIL.search(row)
    )


def _card_payout_processor(row: str) -> str | None:
    """The processor (CARD_PAYOUT_PROCESSOR_NAMES) a row names, as a whole word; None for none."""
    for entity, pattern in _CARD_PAYOUT_NAMES.items():
        if pattern.search(row):
            return entity
    return None


def _card_payout_credit_processor(text: str) -> str | None:
    """The processor a card credit names as its whole payer, when step 3 read the card label alone: the row prints
    DEBIT CARD CREDIT (or Citibank's cut CREDI) or POS CREDIT, after it only the processor's name with reference tokens
    and generic words (never a financing or other word: 'STRIPE CAPITAL' is not the processor's payout), and no other
    reversal marker once the label is removed. None otherwise."""
    row = _before_receiver(text)
    label = _CARD_PAYOUT_LABEL.search(row)
    if label is None or _reversal_credit(_CARD_PAYOUT_LABEL.sub(" ", text)):
        return None
    rest = row[label.end():]
    for entity, pattern in _CARD_PAYOUT_NAMES.items():
        found = pattern.search(rest)
        if found is None:
            continue
        others = (rest[:found.start()] + " " + rest[found.end():]).split()
        if not any(_is_payer_word(word) for word in others):
            return entity
    return None


def _processor_card_payouts(
    records: Sequence[TransactionClassification], duplicate_indexes: set[int],
) -> dict[int, str]:
    """§7.11, §6.3 narrowing 9 (MCA principle and standard A1/A2: a processor's payout is sales): the card credits the
    reversal rule (step 3) took as a card refund, or a push word released and §8.1 would hold, that name a merchant
    processor as their whole payer (_card_payout_credit_processor) on a statement that also prints that processor's own
    ACH activity (its ACH payout, its ACH pull or a returned pull: any posted row naming it with an electronic-payment
    form, never another card credit) and no card purchase at it (a posted debit naming it that is a card purchase: a
    refund of that purchase cannot be told from a payout). {credit index: processor}. Never a row a rule verified, a
    pair pass 4 made, a duplicate or a direction conflict. A marketplace or a retailer (Uber, DoorDash, Amazon) names no
    processor of the table, so its card credits keep the refund reading."""
    candidates: dict[int, str] = {}
    activity: set[str] = set()
    purchases: set[str] = set()
    for index, record in enumerate(records):
        if (
            index in duplicate_indexes or not record.is_posted or record.amount == 0
            or _card_payout_processor(record.normalized_description) is None
        ):
            continue
        text = revenue_text(record.normalized_description)
        row = _before_receiver(text)
        entity = _card_payout_processor(row)
        if entity is None:
            continue
        if record.amount < 0:
            if record.classification == "pos" or _matches_any(row, _POS_PATTERNS):
                purchases.add(entity)
            elif _ELECTRONIC_PAYMENT_FORM.search(row):
                activity.add(entity)
            continue
        if _CARD_PAYOUT_LABEL.search(row) or _CARD_CREDIT_LABEL.search(text) or _LEADING_CARD_CREDIT.match(row):
            if (
                record.direction_consistent
                and record.revenue_classification != "verified_revenue"
                and record.revenue_match_method not in {"matched_reversal_pair", "direction_conflict"}
                and (
                    record.revenue_match_method == "reversal_cancellation_exclusion"
                    or record.revenue_classification == "unverified_deposit"
                )
            ):
                processor = _card_payout_credit_processor(text)
                if processor is not None:
                    candidates[index] = processor
            continue
        if _ELECTRONIC_PAYMENT_FORM.search(row):
            activity.add(entity)
    return {index: entity for index, entity in candidates.items() if entity in activity and entity not in purchases}


def _progress_draw_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.1, §8.10: a builder's progress draw that an earlier rule verified (§7.5's accounts-payable remittance, 'A P PMT
    DRAW 3') leaves verification as a new first state (unverified_deposit, method construction_progress_draw), as
    _financier_never_verified does; its reason names the rule it overruled, for the audit. The pass tiers it
    counted_flagged / construction_progress_draw."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method=CONSTRUCTION_PROGRESS_DRAW_REASON,
        matched_rule="construction_progress_draw_never_verified",
        confidence_score=0.50,
        reason=(
            "A builder pays the business a progress draw for its work: counted and flagged, never verified, by the "
            "owner's ruling on the underwriter's Q11 (a); the rule that read it "
            f"({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, CONSTRUCTION_PROGRESS_DRAW_REASON),
        related_transaction=record.revenue_related_transaction,
    )


def _factor_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.9: a factoring payer's credit that an earlier rule verified (an invoice-purpose wire, an accounts-payable
    remittance descriptor) leaves verification as a new first state (unverified_deposit, method
    factoring_payout_payer); its reason names the rule it overruled, for the audit. The pass tiers it counted_flagged /
    factoring_payout."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="factoring_payout_payer",
        matched_rule="factoring_payer_never_verified",
        confidence_score=0.50,
        reason=(
            "A factor pays the business's own invoices: its payout is counted and flagged, never verified; the rule "
            f"that read it ({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, "factoring_payout"),
        related_transaction=record.revenue_related_transaction,
    )


def _financier_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.9: a lease-to-own or patient financier's merchant payout that an earlier rule verified (a repeat, a company
    form, an operating-income descriptor) leaves verification as a new first state (unverified_deposit, method
    customer_financing_payer), as _factor_never_verified does; its reason names the rule it overruled, for the audit.
    The pass tiers it counted_flagged / customer_financing_payout."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="customer_financing_payer",
        matched_rule="customer_financing_never_verified",
        confidence_score=0.50,
        reason=(
            "A lease-to-own or patient-financing company pays the merchant for a customer's financed purchase: counted "
            f"and flagged, never verified; the rule that read it ({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, CUSTOMER_FINANCING_PAYOUT),
        related_transaction=record.revenue_related_transaction,
    )


def _lender_service_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.7: a listed auto lender's payables-only credit Q7 verified, on a statement with no dealer evidence, is a
    lender paying the business for its services (a repossession agency's recoveries), never dealer funding: it leaves
    verification as a new first state (unverified_deposit, method lender_paid_for_services, no source type), as
    _factor_never_verified does; its reason names the lender and its alias, says the statement shows no dealer evidence
    and that the owner's ruling overrules auto_lender_dealer_funding. The pass tiers it counted_flagged /
    lender_paid_for_services, or holds it as financing_named_payer when the lender also collects from the account
    (_payer_collects). The transaction side (classification, match_method, canonical_entity and every lender flag) is
    untouched."""
    lender = record.revenue_canonical_entity or "the lender"
    alias = f" ({record.revenue_matched_alias})" if record.revenue_matched_alias else ""
    return replace(
        _replace_revenue_state(
            record,
            "unverified_deposit",
            match_method=LENDER_PAID_FOR_SERVICES,
            matched_rule="q7_payables_without_dealer_evidence",
            confidence_score=0.50,
            reason=(
                f"Listed auto lender '{lender}'{alias} pays the business on a payables word alone, and the statement "
                "shows no dealer evidence (no dealer-funding credit, floor-plan financier, dealer-only auction purchase "
                "or dealer's name): a lender paying the business for its services (a repair, a recovery, a commission), "
                "counted and flagged, never verified. The owner's ruling on the underwriter's Q9 overrules "
                f"{record.revenue_match_method}."
            ),
            context_signals=(*record.revenue_context_signals, LENDER_PAID_FOR_SERVICES),
            related_transaction=record.revenue_related_transaction,
        ),
        revenue_source_type=None,
    )


def _customer_financing_lump(
    index: int,
    payouts: dict[int, str],
    records: Sequence[TransactionClassification],
    channel: str,
    posted_cents: int,
) -> bool:
    """§8.9: a financier's payout (`payouts`: the statement's customer_financing_payout rows, index -> financier) that
    is large and one-off. Large: CUSTOMER_FINANCING_LUMP_FLOOR dollars or more, and an incoming wire, a whole multiple
    of CUSTOMER_FINANCING_LUMP_ROUND dollars or at least CUSTOMER_FINANCING_LUMP_SHARE percent of the statement's
    posted credits (`posted_cents`, non-revenue included, the T7 base). One-off: the same financier makes fewer than
    CUSTOMER_FINANCING_SERIES_MIN payouts in the statement, the row included, of at least
    CUSTOMER_FINANCING_SERIES_SHARE percent of its amount. Read over every payout at once, so the hold never depends on
    the rows' order (a pair of lumps holds both); compared in integer cents."""
    cents = _cents(records[index].amount)
    if cents < CUSTOMER_FINANCING_LUMP_FLOOR * 100:
        return False
    if not (
        channel == "wire" or cents % (CUSTOMER_FINANCING_LUMP_ROUND * 100) == 0
        or cents * 100 >= CUSTOMER_FINANCING_LUMP_SHARE * posted_cents
    ):
        return False
    series = sum(
        1 for other, entity in payouts.items()
        if entity == payouts[index] and _cents(records[other].amount) * 100 >= CUSTOMER_FINANCING_SERIES_SHARE * cents
    )
    return series < CUSTOMER_FINANCING_SERIES_MIN


def _holder_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.1: the holder's own push (self_originated) that an earlier rule verified (an accounts-payable entry read by
    step 11, whose holder guard reads only a known holder's name) leaves verification as a new first state
    (unverified_deposit, method self_originated_holder), as _factor_never_verified does; its reason names the rule it
    overruled, for the audit. The pass tiers it excluded_pending_review / holder_name."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="self_originated_holder",
        matched_rule="holder_own_push_never_verified",
        confidence_score=0.40,
        reason=(
            "The row's originator is its own receiver: the holder moves its own money in, which is never revenue and "
            f"never verified; the rule that read it ({record.revenue_match_method}) is overruled, and it is held for "
            "review."
        ),
        context_signals=(*record.revenue_context_signals, "self_originated_holder"),
        related_transaction=record.revenue_related_transaction,
    )


def _settlement_never_verified(record: TransactionClassification) -> TransactionClassification:
    """§8.1: a settlement under the merchant's own name that an earlier rule verified (an operating-income or a
    claim-payment descriptor) and that only the bare settlement word lifted from the own-push guard
    (CreditFacts.settlement_released) leaves verification as a new first state (unverified_deposit, method
    HOLDER_NAMED_SETTLEMENT_METHOD), as _holder_never_verified does; its reason names the rule it overruled, for the
    audit. The pass reads it as an unverified credit: a later hold still names it, and where none does it is counted
    and flagged, named_payer_purpose_refused."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method=HOLDER_NAMED_SETTLEMENT_METHOD,
        matched_rule=HOLDER_NAMED_SETTLEMENT_RULE,
        confidence_score=0.50,
        reason=(
            "A settlement printed under the merchant's own name (a processor's, a carrier's or an operating "
            "settlement) is no holder's own push: counted and flagged, never verified; the rule that read it "
            f"({record.revenue_match_method}) is overruled."
        ),
        context_signals=(*record.revenue_context_signals, HOLDER_NAMED_SETTLEMENT_METHOD),
        related_transaction=record.revenue_related_transaction,
    )

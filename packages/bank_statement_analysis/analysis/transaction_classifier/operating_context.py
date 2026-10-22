"""Operating-source context, auction and property branches."""
from __future__ import annotations

import re
from typing import Sequence

from analysis.classification.counter_debit_reading import _payer_key
from analysis.classification.operating_sources import (
    _card_settlement_form,
    _read_inside_a_waiting_processor,
    _recurrence_veto_wording,
    _recurrence_vetoed,
)
from analysis.classification.record import TransactionClassification, _replace_revenue_state
from analysis.classification_registry import (
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    WHOLESALE_AUCTION_PAYOUT_FORMS,
    WHOLESALE_AUCTION_REFUND_NAMES,
)
from analysis.dates import parse_date
from analysis.descriptor.holder import _business_account, account_name_text
from analysis.descriptor.lexical import _before_receiver, revenue_text
from analysis.descriptor.payer import channel_gate, payer_region
from analysis.descriptor.rails import _matches_any, _without_receiver_value
from analysis.descriptor.words import _BUSINESS_ACCOUNT_PATTERNS, _ELECTRONIC_PAYMENT_FORM
from analysis.payee_matcher import registry_match


_OPERATING_PLATFORM_DEBIT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:PROCESSING|MERCHANT|PLATFORM|SERVICE) FEES?\b"),
    re.compile(r"\bCOMMISSIONS?\b"),
    re.compile(r"\bCHARGEBACK\b"),
    re.compile(r"\bSETTLEMENT ADJUSTMENT\b"),
)
#: §7.0: the operating-source methods whose rows may join the recurrence pool.
_OPERATING_POOL_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "operating_source_payout_form",
})
#: §7.8, §7.10: the operating methods an auction or property branch may touch.
_OPERATING_SOURCE_METHODS = frozenset({
    "operating_source_requires_context", "recurring_operating_source", "operating_source_related_activity",
    "operating_source_with_credit_context",
})
#: §7.8: an ACV credit printing a buyer-payment reference stays unverified.
_AUCTION_BUYER_PAYMENT = re.compile(r"(?<![A-Z])PYMT\d")
#: §7.8, §14.1: an auction credit printing a floor-plan or financing word (NextGear's NGC, AFC's FUNDNG) or a
#: consumer entry (PPD) is never the auction's payout, whatever form it prints.
_AUCTION_VETO = re.compile(
    r"(?<![A-Z])(?:FUNDING|FUNDNG|FUNDED|ADVANCES?|CAPTL|CAPITAL|FLOOR ?PLAN|FLOORPLAN|FINANC\w*|LOANS?)\b"
    r"|\b(?:ADV|NGC|PPD)\b"
)
#: §7.8: the auction refund pair's window, in days.
_AUCTION_REFUND_WINDOW_DAYS = 14
#: §7.10: owner, distribution and deposit wording on a property-management platform's row, and micro-deposits. The
#: last branch is a row shape (two originator labels), not a veto word.
_PROPERTY_PLATFORM_GUARD = re.compile(
    r"(?<![A-Z])OWNERS? ?(?:DIST\w*|DISB\w*|DRAWS?\w*|CONT\w*)|(?<![A-Z])DISTRIBUT\w*|(?<![A-Z])SEC(?:URITY)? ?DEP\w*"
    r"|(?<![A-Z])DEP(?:OSIT)? ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)|(?<![A-Z])SD ?(?:RETURN\w*|RTN\w*|RT\w*|REFUND\w*)"
    r"|(?<![A-Z])ADVANCE\w*|\bORIG CO NAME\b.*\bORIG CO NAME\b"
)
_PROPERTY_MICRO_DEPOSIT = re.compile(
    r"(?<![A-Z])ACCT ?VERIFY\w*|(?<![A-Z])MICRO ?(?:DEP\w*|ENTRY)\b|(?<![A-Z])PENNY TEST\b"
    r"|(?<![A-Z])TRIAL (?:DEP\w*|CREDIT)\b"
)
_PROPERTY_PUSH_SHAPE = re.compile(r"(?<![A-Z])(?:VISA DIRECT|PMNT RCVD|PAYMENT RECEIVED)\b|\bRTP\b")
#: §7.1: an unregistered NET SETTLE originator needs this many NET SETTLE credits in the statement.
_NET_SETTLE_MIN_CREDITS = 3
#: §7.0: the operating recurrence rule.
_RECURRENCE_MIN_CREDITS = 3
_RECURRENCE_MIN_BUSINESS_CREDITS = 2
_AUCTION_PAYOUT_FORMS = {
    entity: tuple(re.compile(pattern) for pattern in patterns)
    for entity, patterns in WHOLESALE_AUCTION_PAYOUT_FORMS.items()
}
_AUCTION_REFUND_NAMES = {entity: re.compile(pattern) for entity, pattern in WHOLESALE_AUCTION_REFUND_NAMES.items()}


def _in_operating_pool(record: TransactionClassification) -> bool:
    """§7.0: only a credit the operating registry decided, or that an operating-source method or an
    entity-naming card form verified, joins an entity's recurrence pool."""
    if record.revenue_canonical_entity is None:
        return False
    if record.revenue_match_method in _OPERATING_POOL_METHODS:
        return True
    return record.revenue_match_method == "operating_income_descriptor" and (
        record.revenue_matched_rule or ""
    ).startswith("card_settlement_form_")


def _upgrade_by_recurrence(
    record: TransactionClassification,
    *,
    entity: str,
    count: int,
    recurring: bool,
    business: bool,
    related_activity: bool,
    extra_signals: Sequence[str] = (),
) -> TransactionClassification:
    """The recurrence pass's verified record for one pooled credit (today's wording)."""
    signals = list(record.revenue_context_signals)
    if recurring:
        signals.append(f"recurring_source_{count}_credits")
    if business:
        signals.append("business_account")
    if related_activity:
        signals.append("related_platform_fee_or_chargeback")
    signals.extend(extra_signals)
    evidence_text = (
        f"recurs in {count} posted credits"
        if recurring
        else "has a related processing fee, commission, chargeback, or adjustment"
    )
    return _replace_revenue_state(
        record,
        "verified_revenue",
        match_method="recurring_operating_source" if recurring else "operating_source_related_activity",
        matched_rule=(
            "maintained_source_recurs_across_statement"
            if recurring
            else "maintained_source_has_related_operating_debit"
        ),
        confidence_score=0.90 if recurring else 0.88,
        reason=f"Maintained operating source '{entity}' {evidence_text}; the credit is verified as operating revenue.",
        context_signals=signals,
    )


def _apply_operating_source_context(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 5 (§6.2, §7.0): operating-source recurrence and related activity, fixed for every source.

    The pool admits only registry rows and operating-method rows (_in_operating_pool); it counts an entity's credits
    already verified by an operating-source method and upgrades only the unverified ones, so a per-row upgrade never
    shrinks it; a vetoed credit never counts and is never lifted (_recurrence_vetoed). A wholesale auction (§7.8) and
    a property-management platform (§7.10) take their own branches, and an unregistered NET SETTLE originator
    verifies with three such credits (§7.1). A debit names its platform as the operating reader does, with the
    receiver field's value removed (§5.2: the holder's name never names a source) and through the ledger gate."""
    updated = list(records)
    pools: dict[str, list[int]] = {}
    vetoed: dict[str, list[int]] = {}
    activity_by_entity: dict[str, list[int]] = {}
    net_settle: dict[tuple[str, ...], list[int]] = {}
    for index, record in enumerate(records):
        if index in duplicate_indexes or not record.is_posted:
            continue
        text = revenue_text(record.normalized_description)
        if record.amount < 0:
            alias_text = _without_receiver_value(text)
            found = registry_match(alias_text, OPERATING_REVENUE_READ_ALIASES)
            if found is not None and _read_inside_a_waiting_processor(alias_text, *found):
                found = None
            if found is not None and _matches_any(alias_text, _OPERATING_PLATFORM_DEBIT_CONTEXT_PATTERNS):
                activity_by_entity.setdefault(found[0], []).append(index)
            continue
        if record.amount <= 0:
            continue
        if _recurrence_vetoed(record, text):
            if _in_operating_pool(record):
                vetoed.setdefault(record.revenue_canonical_entity, []).append(index)
            continue
        if _in_operating_pool(record):
            pools.setdefault(record.revenue_canonical_entity, []).append(index)
        elif (
            record.revenue_classification == "unverified_deposit"
            and record.revenue_match_method in {"ambiguous_credit_descriptor", "unidentified_posted_credit"}
            and channel_gate(text) is None
        ):
            form = _card_settlement_form(text, bank=record.bank)
            if form is not None and form.label == "net_settle":
                key = _payer_key(payer_region(text))
                if key:
                    net_settle.setdefault(key, []).append(index)

    for entity, indexes in pools.items():
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        if source_type == "wholesale_auto_auction":
            _apply_auction_branch(updated, records, entity, indexes, duplicate_indexes)
            continue
        if source_type == "property_management_payments":
            _apply_property_branch(updated, records, entity, indexes)
            continue
        business = any(
            _business_account(records[index].account_name)
            if source_type != "customer_payment_platform"
            else _matches_any(
                account_name_text(records[index].account_name), _BUSINESS_ACCOUNT_PATTERNS
            )
            for index in indexes
        )
        count = len(indexes)
        recurring = count >= _RECURRENCE_MIN_CREDITS or (count >= _RECURRENCE_MIN_BUSINESS_CREDITS and business)
        related = bool(activity_by_entity.get(entity))
        if not recurring and not related:
            continue
        for index in indexes:
            record = updated[index]
            if record.revenue_classification != "unverified_deposit":
                continue
            updated[index] = _upgrade_by_recurrence(
                record, entity=entity, count=count, recurring=recurring, business=business, related_activity=related,
            )

    for indexes in net_settle.values():
        if len(indexes) < _NET_SETTLE_MIN_CREDITS:
            continue
        for index in indexes:
            updated[index] = _replace_revenue_state(
                updated[index],
                "verified_revenue",
                match_method="operating_income_descriptor",
                matched_rule="card_settlement_form_net_settle",
                confidence_score=0.90,
                reason=f"One originator's NET SETTLE entry recurs in {len(indexes)} posted credits: card settlements.",
                context_signals=(*updated[index].revenue_context_signals, "card_settlement_form"),
            )
    _name_vetoed_branch_rows(updated, vetoed)
    return updated


def _name_vetoed_branch_rows(updated: list[TransactionClassification], vetoed: dict[str, list[int]]) -> None:
    """§7.8, §7.10, §14.1: a vetoed pool row of a wholesale auction or a property-management platform never counts and
    is never lifted, and still carries its branch's rule. Only a direction-consistent unverified row in an operating
    method is renamed; its classification stays. An auction row takes the auction's refusal (a payout-form row vetoed
    by a pay, financing or other veto word takes the financing or consumer rule; one vetoed only by the $1 floor has
    no rule of its own and is left as it is); a property row takes the owner or deposit wording rule when it prints
    that wording."""
    for entity, indexes in vetoed.items():
        source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
        if source_type not in {"wholesale_auto_auction", "property_management_payments"}:
            continue
        forms = _AUCTION_PAYOUT_FORMS.get(entity, ())
        for index in indexes:
            record = updated[index]
            if (
                not record.direction_consistent
                or record.revenue_classification != "unverified_deposit"
                or record.revenue_match_method not in _OPERATING_SOURCE_METHODS
            ):
                continue
            text = revenue_text(record.normalized_description)
            if source_type == "property_management_payments":
                if _PROPERTY_PLATFORM_GUARD.search(_before_receiver(text)):
                    updated[index] = _property_wording_record(record, entity)
                continue
            rule = _auction_refusal(text, forms)
            if rule is None:
                if not _recurrence_veto_wording(record, text):
                    continue
                rule = "auction_credit_prints_financing_or_consumer_word"
            updated[index] = _auction_unverified_record(record, entity, rule)


def _auction_refusal(text: str, forms: Sequence[re.Pattern[str]]) -> str | None:
    """§7.8, §14.1: the rule that refuses an auction credit on its wording (a buyer-payment reference, a floor-plan or
    financing word or a consumer entry, or no observed payout form), or None when it prints the payout form. The
    payout form is read with the receiver field's value removed (§5.2): the holder's name never verifies."""
    if _AUCTION_BUYER_PAYMENT.search(text):
        return "auction_credit_prints_buyer_payment_reference"
    if _AUCTION_VETO.search(_before_receiver(text)):
        return "auction_credit_prints_financing_or_consumer_word"
    if not any(form.search(_without_receiver_value(text)) for form in forms):
        return "auction_credit_without_payout_form"
    return None


def _auction_unverified_record(
    record: TransactionClassification, entity: str, rule: str
) -> TransactionClassification:
    """§7.8: an auction credit that is not the auction's verified payout."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="operating_source_requires_context",
        matched_rule=rule,
        confidence_score=0.60,
        reason=f"A credit from the wholesale auction '{entity}' that is not its observed payout form.",
        context_signals=record.revenue_context_signals,
    )


def _property_wording_record(record: TransactionClassification, entity: str) -> TransactionClassification:
    """§7.10: a property-management platform's credit printing owner, distribution or deposit wording."""
    return _replace_revenue_state(
        record,
        "unverified_deposit",
        match_method="operating_source_requires_context",
        matched_rule="property_platform_owner_or_deposit_wording",
        confidence_score=0.60,
        reason=f"A '{entity}' credit prints owner, distribution or deposit wording.",
        context_signals=record.revenue_context_signals,
    )


def _apply_auction_branch(
    updated: list[TransactionClassification],
    records: list[TransactionClassification],
    entity: str,
    indexes: Sequence[int],
    duplicate_indexes: set[int],
) -> None:
    """§7.8: a dealer-only wholesale auction verifies only its observed payout form, never a buyer-payment reference,
    a floor-plan or financing word or a consumer entry (§14.1), and never a credit paired with an equal same-auction
    debit within 14 days (each debit used once). The payout form is read with the receiver field's value removed
    (§5.2): the holder's name never verifies."""
    forms = _AUCTION_PAYOUT_FORMS.get(entity, ())
    refund_name = _AUCTION_REFUND_NAMES.get(entity)
    used_debits: set[int] = set()
    for index in indexes:
        record = updated[index]
        rule, verified = _auction_refusal(revenue_text(record.normalized_description), forms), False
        if rule is None:
            pair = _auction_refund_pair(records, index, refund_name, used_debits, duplicate_indexes)
            if pair is not None:
                used_debits.add(pair)
                rule = "auction_credit_matches_same_source_debit"
            else:
                rule, verified = "wholesale_auto_auction_proceeds", True
        if verified:
            updated[index] = _replace_revenue_state(
                record,
                "verified_revenue",
                match_method="wholesale_auction_payout_form",
                matched_rule=rule,
                confidence_score=0.90,
                reason=f"A dealer-only wholesale auction ('{entity}') pays out in its observed payout form.",
                context_signals=(*record.revenue_context_signals, "wholesale_auction_payout_form"),
            )
        else:
            updated[index] = _auction_unverified_record(record, entity, rule)


def _auction_refund_pair(
    records: list[TransactionClassification],
    credit_index: int,
    refund_name: re.Pattern[str] | None,
    used: set[int],
    duplicate_indexes: set[int],
) -> int | None:
    """§7.8: the index of an unused posted debit that names the auction (on its row or its wire BNF line), for the
    same amount to the cent, within 14 days of the credit; or None."""
    if refund_name is None:
        return None
    credit = records[credit_index]
    credit_date = parse_date(credit.date)
    for index, debit in enumerate(records):
        if (
            index in used or index in duplicate_indexes or debit.amount >= 0 or not debit.is_posted
            or round(abs(debit.amount), 2) != round(credit.amount, 2)
            or not refund_name.search(debit.normalized_description)
            or re.search(r"\bACV CAPITAL\b", debit.normalized_description)
        ):
            continue
        debit_date = parse_date(debit.date)
        if credit_date is not None and debit_date is not None and abs(
            (credit_date - debit_date).days
        ) > _AUCTION_REFUND_WINDOW_DAYS:
            continue
        return index
    return None


def _apply_property_branch(
    updated: list[TransactionClassification],
    records: list[TransactionClassification],
    entity: str,
    indexes: Sequence[int],
) -> None:
    """§7.10: a property-management platform verifies by recurrence of its ACH payout shape only (three credits,
    or two in a business account), never by a related fee debit. A row printing owner, distribution or deposit
    wording is left out of the count and stays unverified; micro-deposits never count; a push-shaped row stays
    operating_source_requires_context. A verified row carries the property-management chip."""
    counted: list[int] = []
    for index in indexes:
        record = updated[index]
        text = revenue_text(record.normalized_description)
        row = _before_receiver(text)
        if _PROPERTY_PLATFORM_GUARD.search(row):
            updated[index] = _property_wording_record(record, entity)
            continue
        if _PROPERTY_MICRO_DEPOSIT.search(row) or _PROPERTY_PUSH_SHAPE.search(row):
            continue
        if not _ELECTRONIC_PAYMENT_FORM.search(row):
            continue
        counted.append(index)
    business = any(_business_account(records[index].account_name) for index in counted)
    count = len(counted)
    if not (count >= _RECURRENCE_MIN_CREDITS or (count >= _RECURRENCE_MIN_BUSINESS_CREDITS and business)):
        return
    for index in counted:
        record = updated[index]
        if record.revenue_classification != "unverified_deposit":
            continue
        updated[index] = _upgrade_by_recurrence(
            record, entity=entity, count=count, recurring=True, business=business, related_activity=False,
            extra_signals=("property_management_collections",),
        )

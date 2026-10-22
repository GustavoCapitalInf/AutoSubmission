"""guard_facts and hold_rule, read by the census and tests."""
from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

from analysis.classification.counter_debit_reading import _payer_key
from analysis.classification.operating_sources import _recurrence_vetoed
from analysis.classification_registry import HEALTHCARE_PAYER_ALIASES, PAYOUT_CREDIT_ENTITIES
from analysis.descriptor.credit_words import _FUNDING_SETTLEMENT_ENTITIES
from analysis.descriptor.lexical import (
    _before_receiver,
    _joined_text,
    _skip_numbered_leading_date,
    company_form,
    payer_name,
)
from analysis.descriptor.payer import entry_fields, payer_label_layout, payer_region, wire_relayed_customer
from analysis.descriptor.rails import _matches_any, _without_receiver_value
from analysis.descriptor.words import (
    _CUSTOMER_INVOICE_DESCRIPTORS,
    _NUMBERED_COMPANY_REGION,
    _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS,
)
from analysis.flag_groups import FINANCING_STATES
from analysis.payee_matcher import match_known_payee, registry_match
from analysis.true_revenue.channel import _channel, cpa_payroll_code
from analysis.true_revenue.claimed import _claimed, _customer_financier, _own_word, _own_words, registry_financing
from analysis.true_revenue.dealer import _dealer_funding_payer
from analysis.true_revenue.eligibility import _deferred_reading, _factoring_payout_payer
from analysis.true_revenue.facts import _transfer_reading
from analysis.true_revenue.finance_release import payroll_tax_credit
from analysis.true_revenue.financing_roots import _accounts_payable_wording, financing_named
from analysis.true_revenue.hold_text import _hold_text, _title_purpose_text
from analysis.true_revenue.holder_names import _holder, _holder_strip_names, _without_holder_name
from analysis.true_revenue.payroll import _direct_deposit_pay, _premium_coded, lending_bank_payer
from analysis.true_revenue.public_payers import (
    _personal_income,
    government_benefit,
    government_grant,
    government_payer,
    healthcare_payer,
    healthcare_payer_match,
    public_region,
)
from analysis.true_revenue.purpose import (
    _currency_conversion,
    _disbursement_entry,
    _disbursing_payer,
    construction_progress_draw,
    gambling_payout,
    legal_settlement,
    owner_disbursement,
    owner_money_platform,
    purpose_trade_name,
)
from analysis.true_revenue.self_originated_credits import _bank_originated_wire
from analysis.true_revenue.sender import _bank_only_payer
from analysis.true_revenue.trust import _held_personal_trust
from analysis.true_revenue.words import (
    _CREDIT_UNION_PAYER,
    _DEALER_FUNDING_VETO,
    _EARNED_WAGE_ACCESS,
    _INVESTMENT_PURPOSE,
    _PAY_WORDS,
    _TITLE_FEE_WORDING,
    _TITLE_FIRM,
    _VEHICLE_PURCHASE_ENTRY,
)
from analysis.true_revenue.zelle import pass_text

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: G2: a financing root glued inside a word of a registry row (STRIPECAPITAL, SHOPIFYCAPITAL).
_GLUED_FINANCING_ROOT = re.compile(r"CAPITAL|CAPTL|FINANC|FUNDING|FUNDNG|LENDING|LENDER|LOAN")


def registry_financing_root(record: TransactionClassification, text: str) -> bool:
    """G2 on a registry row: a registry financing word (registry_financing), or a financing root glued inside a word
    of the row before its receiver fields, the holder's own words (on a store-name platform) and §7.0's FUNDING
    settlements aside. A root inside a place name (a city whose name holds LEND) is not one: the registry's reads
    are whole words."""
    if registry_financing(record, text):
        return True
    own = _own_words(record, text)
    for word in _before_receiver(text).split():
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in _FUNDING_SETTLEMENT_ENTITIES:
            continue
        if _GLUED_FINANCING_ROOT.search(word):
            return True
    return False


def guard_facts(record: TransactionClassification, text: str, *, zelle_true_revenue: bool = False) -> dict:
    """The census's §14.3 facts of one posted credit (tools/revenue_census.py), read with these readers. The customer
    descriptor is step 11's reading (the text without the receiver field's value, or the joined originator and entry
    before the receiver fields), so a descriptor in the holder's name never marks a row. The known payee is read the
    same way, as the record's claim reads it. `claimed` is the pass's own claim (§8.1: the holds, the holder's
    included, skip a row the registry, a payout entity or a factoring payee claimed), which the census's holder guards
    read. The facts read the pass's own text, TD Canada Trust's e-Transfer code dropped (without_transfer_code).
    `zelle_true_revenue` is the snapshot's reading, which the progress_draw fact follows as the pass's payer facts do
    (credit_facts). The pass's own text is pass_text (PNC's ZEL read as ZELLE)."""
    text = pass_text(record, text)
    region = payer_region(text)
    entry = entry_fields(text)
    row = _before_receiver(text)
    words = _without_receiver_value(text)
    known = match_known_payee(words, credit=True)
    # G12 (§8.7): Q7's payer and veto words, read as dealer_funding_reading reads them (the holder's name never names a lender).
    listed = _dealer_funding_payer(words) is not None
    union = bool(_CREDIT_UNION_PAYER.search(region))
    # The pay and benefit words are read as the holds read them, without the holder's own name runs (and its
    # other business names, _holder_strip_names).
    also = _holder_strip_names(record)
    pay_row = _without_holder_name(row, _holder(record), also=also)
    return {
        "claimed": _claimed(record, text),
        "financing_root": financing_named(text, region, entry, _holder(record), bank=record.bank, also=also),
        "registry_root": registry_financing_root(record, text),
        "registry_financing": registry_financing(record, text),
        "pay_or_personal": bool(
            _PAY_WORDS.search(pay_row) or _EARNED_WAGE_ACCESS.search(pay_row) or cpa_payroll_code(pay_row, record.bank)
            # With the statement's bank, as the hold reads it.
            or _personal_income(text, pay_row, record.bank)
            # The direct-deposit words with the row's own sign of a person's pay (a person receiver, a consumer
            # entry); the account's shape is the statement's, which the pass alone reads (a row it holds on that shape
            # is out of True).
            or _direct_deposit_pay(text, pay_row, _holder(record), business=True)
        ),
        # The pass's own reading (_transfer_reading): the statement's bank, the explicit deposit forms. And an ACH pull
        # whose payer region is only a bank (_bank_only_pull).
        "transfer_no_counterparty": _transfer_reading(record, text, _channel(text, record.bank), region)[2],
        # The payer region names only a bank (_bank_only_payer), which Q6 never verifies.
        "bank_only_payer": _bank_only_payer(region, entry, record.bank, row=row),
        "known_financing": known is not None and known.state in FINANCING_STATES,
        "payout_or_factoring": known is not None and (known.entity in PAYOUT_CREDIT_ENTITIES or known.state == "factoring"),
        "numbered_region": _NUMBERED_COMPANY_REGION.search(
            _skip_numbered_leading_date(region)
        ) is not None,
        "customer_descriptor": (
            _matches_any(_without_receiver_value(text), _CUSTOMER_INVOICE_DESCRIPTORS)
            or _matches_any(_joined_text(row), _CUSTOMER_INVOICE_DESCRIPTORS)
        ),
        "q7_payer_ok": listed or union,
        "q7_listed": listed,
        "q7_credit_union": union and bool(_VEHICLE_PURCHASE_ENTRY.search(entry or row)),
        "q7_veto_word": bool(_DEALER_FUNDING_VETO.search(words)),
        "pooled_while_vetoed": (
            record.revenue_match_method in {"recurring_operating_source", "operating_source_related_activity"}
            and _recurrence_vetoed(record, text)
        ),
        # §14.2: a named payer whose channel is not printed, and whose name alone Q6 (b) or (c) would verify.
        "q6_shape": (
            company_form(payer_name(region))
            or government_payer(public_region(text)) or healthcare_payer(region)
        ),
        # Final review I7: the pass's own readings the census's demotion causes key on (the rule that fires).
        "hold_rule": hold_rule(record, text, region, entry),
        "relayed_customer": bool(wire_relayed_customer(text)),
        # The payer region reads past a bank's label, entry or reference.
        "payer_label_layout": payer_label_layout(text),
        "premium_coded": _premium_coded(text, region),
        "factoring_payer": _factoring_payout_payer(region, text),
        # The lease-to-own or patient financier whose merchant payout the row is (a ledger entity name, or None),
        # which the census's narrowing and declared demotion read.
        "customer_financing_payer": _customer_financier(record, text),
        # The row is a factoring review entity's credit, routed to the factoring payout, unconfirmed.
        "factoring_review": (
            record.classification == "factoring" and record.match_method == "unconfirmed_flag_payee_alias"
        ),
        "deferred_source": _deferred_reading(text, _channel(text), region, entry),
        "short_healthcare_alias": (
            bool(region) and registry_match(region, HEALTHCARE_PAYER_ALIASES) is not None
            and healthcare_payer_match(region) is None
        ),
        # An ordinary payer's disbursement entry, which the purpose-only spare drops from the non-sale reading when it
        # repeats in the statement (the pass's spared refused word; read here on the row).
        "spared_disbursement": bool(region) and _disbursing_payer(text, region) and _disbursement_entry(text, region),
        # A hold word only the trade-name reader's purpose arm spared (the pass's refused word, read on the hold's
        # text without the holder's names, as hold_rule reads it).
        "purpose_trade_name": purpose_trade_name(
            text, _without_holder_name(_hold_text(text), _holder(record), also=also), region
        ),
        # A builder's progress draw on a row nothing claimed, as the pass's payer facts read it
        # (CreditFacts.progress_draw).
        "progress_draw": not (_claimed(record, text) or _factoring_payout_payer(region, text))
        and construction_progress_draw(text, region, _holder(record), also=also, zelle_true_revenue=zelle_true_revenue),
        # The pass's channel and payer key as a digest (never a name), by which the census finds a Q5 or Q6 repeat whose
        # same-payer row Q11 keeps from the repeat (an asset sale, a builder's progress draw).
        "payer_key_digest": payer_key_digest(text, region, record.bank),
    }


def payer_key_digest(text: str, region: str, bank: str | None = None) -> str | None:
    """Sixteen hex digits of the SHA-256 of the row's channel and the payer key Q5 and Q6 group a repeat by (_channel,
    the classifier's _payer_key of the payer region), or None where the region names no payer. Rows of one payer on one
    channel share it; it never prints the payer's name."""
    key = _payer_key(region) if region else ()
    if not key:
        return None
    return hashlib.sha256(f"{_channel(text, bank)}|{' '.join(key)}".encode("utf-8")).hexdigest()[:16]


def hold_rule(record: TransactionClassification, text: str, region: str, entry: str) -> str | None:
    """Final review I7 (a census fact): which 5.6 hold reading of §20 names the row, in §8.10's order: a bank that
    originates the wire, a financing root, a lending bank (the financing holds); a government benefit (GOV, the
    personal-income hold); a government grant (GOV), a title firm, the holder's currency conversion, a personal trust,
    owner money (the non-sale holds); a payroll provider's tax-service credit (the non-sale hold after the
    counter-debit holds); or None. The census keys a Q5 or Q6 row's later hold on it. A gambling payout, a legal
    settlement and an owner-shaped payer's DISB, after a personal trust and before owner money. Each read as
    non_sale_purpose reads it (owner money by owner_money_platform)."""
    # The holder's other business names are stripped as the holds strip them.
    also = _holder_strip_names(record)
    row = _without_holder_name(_hold_text(text), _holder(record), also=also)
    if _bank_originated_wire(text, region, wire=_channel(text, record.bank) == "wire"):
        return "bank_originated_wire"
    if financing_named(text, region, entry, _holder(record), bank=record.bank, also=also):
        return "financing_root"
    # A lending bank named as the payer (the financing hold).
    if lending_bank_payer(text, region):
        return "lending_bank"
    if government_benefit(text):
        return "government_benefit"
    if government_grant(text):
        return "government_grant"
    if region and _TITLE_FIRM.search(region) and _TITLE_FEE_WORDING.search(_title_purpose_text(text)) is None:
        return "title_firm"
    if _currency_conversion(text, bank=record.bank):
        return "currency_conversion"
    if _held_personal_trust(text, region):
        return "personal_trust"
    if gambling_payout(text, row):
        return "gambling_payout"
    if legal_settlement(text, row, region):
        return "legal_settlement"
    if owner_disbursement(text, row, region):
        return "owner_disbursement"
    if (
        (_INVESTMENT_PURPOSE.search(row) and not _accounts_payable_wording(text))
        # Read as non_sale_purpose reads it.
        or owner_money_platform(text, row, region)
        or _matches_any(row, _SAVINGS_INVESTMENT_ORIGINATOR_PATTERNS)
    ):
        return "owner_money"
    if payroll_tax_credit(text, region):
        return "payroll_tax"
    return None

"""Registry, payout-entity and customer-financier claims."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from analysis.classification_registry import CUSTOMER_FINANCING_PAYERS, PAYOUT_CREDIT_ENTITIES
from analysis.descriptor.credit_words import (
    _FUNDING_SETTLEMENT_ENTITIES,
    _MICRO_DEPOSIT_FLOOR,
    _STORE_NAME_PAYOUT_ENTITIES,
)
from analysis.descriptor.holder import holder_words, store_name_printed, store_name_run_words
from analysis.descriptor.lexical import _before_receiver, _distinctive_words
from analysis.descriptor.payer import payer_region
from analysis.descriptor.rails import _without_receiver_value
from analysis.descriptor.words import (
    _BNPL_CONSUMER_CREDIT,
    _PAYOUT_NON_SALE_CREDIT,
    _RECEIVER_FIELD_VALUE,
    _SNAP_MERCHANT_FUNDING,
)
from analysis.payee_matcher import PayeeMatch, match_known_payee
from analysis.true_revenue.channel import _channel
from analysis.true_revenue.holder_names import _holder, _holder_names, without_receiver_and_holder
from analysis.true_revenue.model import _OwnWords
from analysis.true_revenue.payroll import _person_receiver
from analysis.true_revenue.public_payers import consumer_entry
from analysis.true_revenue.self_originated_credits import _wire_region_names_nobody
from analysis.true_revenue.words import PROCESSOR_CARD_PAYOUT_METHOD, _REGISTRY_METHODS

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.1: the financing words on a registry row: the recurrence veto's financing words (§7.0), the new-read
#: financing veto (§7.2) and the auction's financing words (§7.8). A platform's or processor's capital, advance
#: or loan credit and an auction's floor-plan or NextGear credit are never claimed by the registry.
_REGISTRY_FINANCING_WORDS = re.compile(
    r"(?<![A-Z])(?:LOANS?|CAPITAL|CAPI|CAPIT|CAPITA|CAPTL|FINANC\w*|LEND\w*|ADVANCE[SD]?|ADVNC|ADVN|ADVC"
    r"|CASH ADV\w*|FUNDING|FUNDNG|FUNDED|PROCEEDS|DRAW|FLOOR ?PLAN|FLOORPLAN)\b"
    r"|\b(?:CAP\d*(?:SEC)?|FIN|ADV|MCA|NGC)\b"
)
#: §8.9: the lease-to-own and patient financiers whose merchant payouts are the merchant's sales (the registry's
#: CUSTOMER_FINANCING_PAYERS: ledger entity -> its spelling on the payer region), read by _customer_financier; and their
#: names anywhere on the row without the receiver field's value (CUSTOMER_FINANCING_NAMES), which keep a row from Q5 and
#: Q6 (_never_q5_or_q6).
_CUSTOMER_FINANCING_PAYERS = {entity: re.compile(pattern) for entity, pattern in CUSTOMER_FINANCING_PAYERS.items()}
#: The class-action words that make a financier's credit consumer-side (Progressive Leasing's data-breach
#: settlement paid to its customers): Q8's own claim veto, read whatever the legal_settlement reads.
_LEGAL_SETTLEMENT_WORDS = re.compile(r"(?<![A-Z])(?:BREACH|LITIGAT\w*|CLASS ACTION)\b")
#: The channels a financier's merchant payout comes on (never a check, a cash or branch deposit or a person-to-person
#: rail).
_CUSTOMER_FINANCING_CHANNELS = frozenset({"wire", "ach_eft", "other"})


def _own_words(record: TransactionClassification, text: str) -> _OwnWords:
    """§7.0: the holder's own words, as the recurrence veto reads them on a store-name platform: the account name's
    distinctive words and the name the bank prints in the receiver field (a delivery platform prints the merchant's
    store there). On every other source there are none."""
    entity = record.revenue_canonical_entity
    if entity not in _STORE_NAME_PAYOUT_ENTITIES:
        return _OwnWords()
    # Final review I4: a veto word that is the whole entry field, or forms it alone with generic words, is the
    # platform's own financing wording: no store name prints, so the holder's words spare nothing.
    if not store_name_printed(text, entity, _holder(record)):
        return _OwnWords()
    own = set(holder_words(_holder(record)))
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        own.update(_distinctive_words(found.group(0).split()[1:]))
    return _OwnWords(frozenset(own), store_name_run_words(text, entity, _holder(record)))


def _own_word(word: str, own: _OwnWords) -> bool:
    """§7.0: a word of four letters or more that is one of the holder's own words or the start of one; FW wave 3: or a
    word of the store's own name, the entry's run of the holder's name ('FIN AND FORK'), at any length."""
    return word in own.run or (len(word) >= 4 and any(mine == word or mine.startswith(word) for mine in own.words))


def registry_financing(record: TransactionClassification, text: str) -> bool:
    """§8.1: a registry row whose row before its receiver fields prints a financing word, the holder's own words aside
    on a store-name platform (§7.0) and FUNDING aside on the settlements of the three platforms §7.0 names. Such a row
    is not claimed by the registry: it is held as financing_named_payer."""
    if record.revenue_match_method not in _REGISTRY_METHODS:
        return False
    own = _own_words(record, text)
    for found in _REGISTRY_FINANCING_WORDS.finditer(_before_receiver(text)):
        word = found.group(0)
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in _FUNDING_SETTLEMENT_ENTITIES:
            continue
        return True
    return False


def _payout_entity(text: str) -> PayeeMatch | None:
    """§8.9: the payout-credit entity (PAYOUT_CREDIT_ENTITIES) the row names, read without the receiver field's value
    (§5.2: the holder's name never names a payer, as the 5.5 readers read the operating alias); or None."""
    known = match_known_payee(_without_receiver_value(text), credit=True)
    return known if known is not None and known.entity in PAYOUT_CREDIT_ENTITIES else None


def _customer_financier(record: TransactionClassification, text: str, *, non_sale: bool = True) -> str | None:
    """§8.9: the lease-to-own or patient financier (CUSTOMER_FINANCING_PAYERS: Snap Finance, Koalafi, Cherry, Acima,
    Terrace Finance, Wisetack, Katapult, Progressive Leasing) whose payout to the merchant for a customer's financed
    purchase the row is, read on the payer region; or None. None, in this order, on a credit under the $1 floor; on a
    channel other than a wire, an ACH or EFT row or an unlabelled one; on a row with no payer region, or a wire's region
    that names nobody (blanked as credit_facts blanks it); on a consumer-side row (OQ2's consumer words,
    _BNPL_CONSUMER_CREDIT: a refund, a return, a withdrawal, a reward, a card or a purchase) or a class-action payout
    (_LEGAL_SETTLEMENT_WORDS), read without the receiver field's value; on a non-sale or financing credit; and on a
    consumer (PPD or WEB) entry to a person who is not the holder. Otherwise the first financier whose spelling the
    region prints; a spelling that holds LOAN (Snap's SNAP LOAN FUNDING) only in Snap's merchant form
    (_SNAP_MERCHANT_FUNDING). `non_sale=False` reads the financier without the payout non-sale veto, for
    _payout_claim_vetoed alone."""
    if record.amount < _MICRO_DEPOSIT_FLOOR:
        return None
    channel = _channel(text, record.bank)
    if channel not in _CUSTOMER_FINANCING_CHANNELS:
        return None
    region = payer_region(text)
    if channel == "wire" and _wire_region_names_nobody(text, region, record.bank, _holder_names(record)):
        region = ""
    if not region:
        return None
    words = _without_receiver_value(text)
    if _BNPL_CONSUMER_CREDIT.search(words) or _LEGAL_SETTLEMENT_WORDS.search(words):
        return None
    if non_sale and _payout_non_sale(record, text):
        return None
    holder = _holder(record)
    if consumer_entry(text, holder) and _person_receiver(text, "", holder):
        return None
    for entity, spelling in _CUSTOMER_FINANCING_PAYERS.items():
        found = spelling.search(region)
        if found is None:
            continue
        if "LOAN" in found.group(0) and not _SNAP_MERCHANT_FUNDING.search(_before_receiver(text)):
            continue
        return entity
    return None


def _claimed(record: TransactionClassification, text: str) -> bool:
    """§8.1, §8.9: the operating registry, a payout-credit entity or a factoring payee claimed the row. A registry row
    that prints a financing word is not claimed. A card credit released as its processor's instant payout is claimed by
    that processor (its pulls and fees never hold it as the payer also debited). And a lease-to-own or patient
    financier's merchant payout (_customer_financier), which skips the holds a payout entity or a factor skips (the
    insurer name, the financing, counter-debit, holder and non-sale holds); the insurer, possible-return, pay,
    personal-income and payroll-tax holds and the $1 floor still read it. A payout entity's or a financier's credit
    printing a non-sale or financing word (_payout_non_sale: an advance, capital, interest, a dividend or a rebate) is
    not claimed, so the holds read it as they read the same row from any other payer; the payout_credit_entity tier arm
    is unchanged."""
    if record.revenue_match_method == PROCESSOR_CARD_PAYOUT_METHOD:
        return True
    if record.revenue_match_method in _REGISTRY_METHODS:
        return not registry_financing(record, text)
    if record.classification == "factoring":
        return True
    if _payout_entity(text) is not None and not _payout_non_sale(record, text):
        return True
    return _customer_financier(record, text) is not None


def _payout_non_sale(record: TransactionClassification, text: str) -> bool:
    """The row, read without the receiver field's value and without the holder's names (the holder-name strip's,
    _without_holder_name with _holder_strip_names), prints a non-sale or financing word
    (classifier._PAYOUT_NON_SALE_CREDIT: ADVANCE(S), ADVNC, ADVN, ADVC, CASH ADV..., CAPITAL, CAPTL, INTEREST,
    DIVIDEND(S), REBATE(S); never FUNDING, PAYOUT, PAYMENT, LEASE FUND, PROCEEDS or a bare ADV). Such a credit of a
    payout entity or a lease-to-own or patient financier is never claimed as a merchant payout: a holder named
    'NORTHWIND CAPITAL DENTAL', in its receiver field or in Snap's merchant form, never vetoes."""
    words = without_receiver_and_holder(text, record.account_name, record.holder_name)
    return _PAYOUT_NON_SALE_CREDIT.search(words) is not None

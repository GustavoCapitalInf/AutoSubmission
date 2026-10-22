"""Q5/Q6 eligibility, deferred sources, factor payers."""
from __future__ import annotations

import re
from typing import Sequence, TYPE_CHECKING

from analysis.classification.credit_predicates import _wire_vetoed
from analysis.classification_registry import (
    CARD_SETTLEMENT_CREDIT_FORMS,
    CUSTOMER_FINANCING_NAMES,
    FACTORING_PAYOUT_PAYERS,
    OPERATING_REVENUE_READ_ALIASES,
    SECTION_15_DEFERRED_PAYERS,
)
from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.credit_words import _PAYOUT_FORMS
from analysis.descriptor.holder import holder_named
from analysis.descriptor.lexical import _before_receiver, _is_reference_token, _joined_text
from analysis.descriptor.payer import channel_gate
from analysis.descriptor.rails import _without_receiver_value
from analysis.descriptor.words import _BANK_COMPANY_FORM, _PAYOUT_NON_SALE_CREDIT, _WIRE_ORIGINATOR_LABEL
from analysis.payee_matcher import registry_match
from analysis.true_revenue.claimed import _customer_financier, _payout_entity, _payout_non_sale
from analysis.true_revenue.holder_names import _holder
from analysis.true_revenue.model import CreditFacts, _under_micro_floor
from analysis.true_revenue.public_payers import healthcare_payer
from analysis.true_revenue.self_originated_credits import _cut_wire_legal_form
from analysis.true_revenue.trust import _address_words, _not_a_place_word
from analysis.true_revenue.words import (
    INSURER_FOR_WORK_METHOD,
    PROCESSOR_CARD_PAYOUT_METHOD,
    _BANK_OR_TITLE_SENDER,
    _TRUST_ADDRESS_MAX_WORDS,
    _US_STATE_TAIL,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §15, §19 OQ4: the payers of the deferred family items (the registry's SECTION_15_DEFERRED_PAYERS), which stay
#: counted and flagged until the owner rules on each: Q5 and Q6 never verify them, they never count toward a Q5 or Q6
#: repeat, and on a wire or an ACH or EFT row their reason is named_payer_purpose_refused (never "One-off payer", as
#: a deferred source often repeats). The registry's own deferred sources are left to the registry by
#: _left_to_its_family.
_SECTION_15_DEFERRED_PAYERS = re.compile(SECTION_15_DEFERRED_PAYERS)
_CUSTOMER_FINANCING_NAMES = re.compile(CUSTOMER_FINANCING_NAMES)
#: §7.7: a bare X12 TRN*1* with no entry description, from a healthcare payer, is deferred too.
_BARE_X12_TRACE = re.compile(r"\bTRN 1\b")
#: §7.1: the NET SETTLE card form, read whether or not its refusal or the card veto matches: such a row is decided
#: by §7.1's own rule alone (its refusal and its three-credit count), never by Q5 or Q6.
_NET_SETTLE_FORM = re.compile(next(form.pattern for form in CARD_SETTLEMENT_CREDIT_FORMS if form.label == "net_settle"))


def _left_to_its_family(text: str) -> bool:
    """§7.1 to §7.3, §7.8: a row a family rule decides alone, which Q5 and Q6 never verify: the operating registry
    names an entity on it (an alias or its cut, read with the receiver field's value removed, or a payout form;
    whether or not the registry's read was vetoed or named a source, so an auction wire, a transport marketplace's
    wallet or wire credit and a TikTok row that is not ACH-shaped stay with their own rules), or it prints the NET
    SETTLE card form (§7.1: its refusal on law, trust, escrow, title and claims firms, and its three-credit count). A
    waiting processor's bare word (BRAINTREE, SMARTTAB) is no operating-registry alias, so it never takes a row from
    Q5 or Q6."""
    alias_text = _without_receiver_value(text)
    if registry_match(alias_text, OPERATING_REVENUE_READ_ALIASES) is not None:
        return True
    row = _before_receiver(text)
    joined = _joined_text(row)
    if any(pattern.search(row) or pattern.search(joined) for _, _, pattern in _PAYOUT_FORMS):
        return True
    return _NET_SETTLE_FORM.search(row) is not None or _NET_SETTLE_FORM.search(joined) is not None


def _deferred_source(text: str, facts: CreditFacts) -> bool:
    """§15, §19 OQ4: a payer of the deferred family items, counted and flagged until the owner rules: read with
    the receiver field's value removed, and a healthcare payer's bare X12 trace with no entry (an ACH or EFT
    shape: a wire's own TRN field is no X12 trace)."""
    return _deferred_reading(text, facts.channel, facts.region, facts.entry)


def _deferred_reading(text: str, channel: str, region: str, entry: str) -> bool:
    """§15 (_deferred_source) on the row's channel, payer region and entry fields."""
    if _SECTION_15_DEFERRED_PAYERS.search(_without_receiver_value(text)):
        return True
    return (
        channel != "wire" and healthcare_payer(region) and not entry
        and _BARE_X12_TRACE.search(text) is not None
    )


def _never_q5_or_q6(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """The rows Q5 and Q6 never verify and never count toward a repeat, whatever their holds: a direction conflict (§6.1
    step 2, §7.0: never lifted by any pass), a credit under $1, a row a family rule decides alone, a deferred source and
    a factoring payer's payout. And a processor's instant payout released from a card credit (counted, never verified).
    And a lease-to-own or patient financier's merchant payout, or any row that names one of them
    (CUSTOMER_FINANCING_NAMES, read without the receiver field's value). And a builder's progress draw (counted and
    flagged, never verified). And an insurer's credit released as the business's work (INSURER_FOR_WORK_METHOD). And a
    credit the financing-root release lifted (CreditFacts.q9). And a settlement the bare settlement word alone released
    from the holder hold or the own-push guard (CreditFacts.settlement_released), which never counted toward a repeat
    while held. And a payout entity's or a financier's credit whose claim the non-sale or financing veto lifted
    (_payout_claim_vetoed), so the holds read it: such a credit is counted, never verified, and where no hold reads its
    word (an abbreviated advance, ADVNC) a payout entity's is counted as payout_credit_entity, as before."""
    return (
        record.revenue_match_method == "direction_conflict"
        or record.revenue_match_method == PROCESSOR_CARD_PAYOUT_METHOD
        or record.revenue_match_method == INSURER_FOR_WORK_METHOD
        or not record.direction_consistent
        or _under_micro_floor(record)
        or _left_to_its_family(text)
        or _deferred_source(text, facts)
        or facts.factor
        or facts.financier is not None
        or _CUSTOMER_FINANCING_NAMES.search(_without_receiver_value(text)) is not None
        or facts.progress_draw
        or facts.q9 is not None
        or facts.settlement_released
        or (not facts.claimed and _payout_claim_vetoed(record, text))
    )


def _payout_claim_vetoed(record: TransactionClassification, text: str) -> bool:
    """A payout entity (_payout_entity) or a lease-to-own or patient financier (_customer_financier, read without the
    veto) names the row, whose claim the non-sale or financing veto lifted (_payout_non_sale). Such a credit is never
    verified by Q5 or Q6 and never counts toward a repeat: the holds read it as any payer's row, and where none reads
    its word (an abbreviated advance: ADVNC, ADVN, ADVC) it is counted, a payout entity's as payout_credit_entity, as
    before the batch."""
    if _PAYOUT_NON_SALE_CREDIT.search(_without_receiver_value(text)) is None:
        return False
    if not _payout_non_sale(record, text):
        return False
    return _payout_entity(text) is not None or _customer_financier(record, text, non_sale=False) is not None


def _vetoed_financier(record: TransactionClassification, text: str) -> str | None:
    """The lease-to-own or patient financier (_customer_financier, read without the veto) whose claim the non-sale or
    financing veto lifted (_payout_non_sale), or None. The lump-sum test reads such a counted credit as that financier's
    payout, as before the veto, so an abbreviated advance (ADVNC, ADVN, ADVC), which no hold reads, is never a way into
    True for a large one-off sum; a payout entity's credit, which no lump-sum test reads, is not one."""
    if _PAYOUT_NON_SALE_CREDIT.search(_without_receiver_value(text)) is None:
        return None
    if not _payout_non_sale(record, text):
        return None
    return _customer_financier(record, text, non_sale=False)


def _factoring_payout_payer(region: str, text: str = "") -> bool:
    """§8.9: a freight-factoring payer the registry names for this pass alone (FACTORING_PAYOUT_PAYERS). Its credit is
    the carrier's own invoices paid by the factor: counted and flagged as factoring_payout, never verified by any path.
    Read only as the payer region (the ACH originator or the wire sender), which is the alias, followed only by company
    forms: a longer name that starts with it ('<alias> FOR PETS LLC') or another payer's purpose citing it names
    another payer. The words after the alias (_factor_tail) may also be a company form glued to its last word
    ('<alias>LLC'), a DBA tail, an entry word, a date or a number that falls into the region, and on a B/O field
    (`text`'s originator label) the sender's address: its city, state, ZIP and country (the trust rule's place
    reading)."""
    words = (region or "").split()
    for aliases in FACTORING_PAYOUT_PAYERS.values():
        for alias in aliases:
            head = alias.split()
            if not words or len(words) < len(head) or words[: len(head) - 1] != head[:-1]:
                continue
            last = words[len(head) - 1]
            if last == head[-1]:
                tail = words[len(head):]
            elif last.startswith(head[-1]) and _BANK_COMPANY_FORM.fullmatch(last[len(head[-1]):]):
                # A company form glued to the alias's last word ('SOLUTIONSLLC').
                tail = [last[len(head[-1]):], *words[len(head):]]
            else:
                continue
            if _factor_tail(tail, b_o=_b_o_field(text)):
                return True
    return False


#: §8.9: the entry words a layout with no entry field prints into the payer region after its name.
_FACTOR_ENTRY_WORDS = frozenset({"PAYMENT", "PAYMENTS", "PMT", "PMTS", "PYMT"})


def _b_o_field(text: str) -> bool:
    """The wire's originator label is B/O (Fedwire, CHIPS, Chase's book transfer), a field that prints the
    sender's address after its name."""
    found = _WIRE_ORIGINATOR_LABEL.search(text or "")
    return found is not None and found.group(0).strip() == "B O"


def _factor_tail(tail: Sequence[str], *, b_o: bool) -> bool:
    """§8.9: the words after a factor's alias add nothing to its name: company forms (glued or spaced), entry words
    (_FACTOR_ENTRY_WORDS), dates and numbers (reference tokens), then either nothing, a DBA tail (the factor's trade
    name, any words), or, on a B/O field, an address: place words ending in a US state code, at most
    _TRUST_ADDRESS_MAX_WORDS of the address's own, as the personal-trust rule reads one, and never a connector word
    (_FACTOR_CONNECTOR_WORDS: FOR, OF, AND, THE; [A3H-m1])."""
    words = list(tail)
    while words and (
        _BANK_COMPANY_FORM.fullmatch(words[0]) or words[0] in _FACTOR_ENTRY_WORDS
        or _is_reference_token(words[0])
    ):
        words.pop(0)
    if not words or words[0] == "DBA":
        return True
    if not b_o:
        return False
    while words and words[-1] in {"US", "USA"}:
        words.pop()
    return (
        bool(words) and words[-1] in _US_STATE_TAIL
        and len(_address_words(words[:-1])) <= _TRUST_ADDRESS_MAX_WORDS
        and not any(_not_a_place_word(word) or word in _FACTOR_CONNECTOR_WORDS for word in words[:-1])
    )


#: [A3H-m1]: a connector word after a factor's alias joins a longer name ('<alias> FOR PETS <city>
#: <state>'), never the sender's address.
_FACTOR_CONNECTOR_WORDS = frozenset({"FOR", "OF", "AND", "THE"})


def _wire_verifies(record: TransactionClassification, text: str, facts: CreditFacts, repeats: int) -> bool:
    """§8.5 (Q5): the same company wires twice or more, and the row passes every veto of §7.9 (the 5.5 reader,
    _wire_vetoed: a non-sale purpose, a financing root, any known payee, the own account, a brand-word affiliate, a cut
    financing originator, a title or escrow firm). The holder test is read here too, so a row the holds skip (one the
    registry claimed) never verifies from the holder's name (§6 precedence: Q5 never verifies a row the holder test
    or the numbered-company guard matches)."""
    if not facts.wire_n1 or facts.hold is not None or not facts.region or facts.numbered:
        return False
    if holder_named(facts.region, _holder(record)):
        return False
    if channel_gate(text) is not None:
        return False
    # An LLC the originator field cut and glued to the address counts as the company form here only.
    if not (facts.company_form or facts.public_or_healthcare or _cut_wire_legal_form(facts.region)) or repeats < 2:
        return False
    if _BANK_OR_TITLE_SENDER.search(facts.name) or facts.refused_word:
        return False
    return not _wire_vetoed(text, facts.region, _holder(record))


def _q6_method(facts: CreditFacts, repeats: int, all_consumer: bool) -> str | None:
    """§8.6 (Q6): the verifying method of an eligible named ACH or EFT payer, or None. A PPD or WEB entry never
    verifies by repetition alone (a) or by its company form, and neither does a bank or a title or escrow firm's
    company form (§8.5's senders)."""
    if repeats >= 2 and not all_consumer:
        return "named_payer_repeats"
    if facts.company_form and not facts.consumer_entry and not _BANK_OR_TITLE_SENDER.search(facts.name):
        return "named_payer_company_form"
    if facts.public_or_healthcare:
        return "public_or_healthcare_payer"
    return None


def _q6_eligible(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """§8.6: an unverified posted credit with an electronic-payment form and a payer region, which the channel gate
    leaves open, no transfer wording in its entry fields, no wire, no registry, payout or factoring claim, no hold, and
    no numbered company. Nor a payer region that names only a bank (_bank_only_payer): a bank's name, or the
    statement's own bank's channel ('CHASE ONLINE'), is no customer, so its repetition proves nothing (Q6 refused a
    bank on its company-form arm only before)."""
    return (
        facts.electronic and bool(facts.region) and facts.channel == "ach_eft"
        and channel_gate(text) is None
        and not _TRANSFER_WORDING.search(facts.entry)
        and not facts.wire_n1 and not facts.claimed and facts.hold is None and not facts.numbered
        # A payer region that is only a bank's name and an account description names no payer.
        and not facts.transfer_no_counterparty
        and not facts.bank_only
    )

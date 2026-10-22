"""Operating-source reading and the §7.0 recurrence veto."""
from __future__ import annotations

import re
from dataclasses import dataclass

from analysis.classification.payees import _is_payroll_provider_row
from analysis.classification.record import TransactionClassification
from analysis.classification_registry import (
    CARD_ISSUER_CONTEXT_ALIASES,
    CARD_SETTLEMENT_CREDIT_FORMS,
    CardSettlementForm,
    GATED_PROCESSOR_ALIASES,
    OPERATING_ALIASES_READ_WITH_VETOES,
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    OPERATING_SOURCES_READ_WITH_VETOES,
    OPERATING_SOURCE_CONTEXT_WORDS,
)
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.credit_words import (
    _FUNDING_SETTLEMENT_ENTITIES,
    _FUNDING_WORD,
    _MICRO_DEPOSIT_FLOOR,
    _PAYOUT_FORMS,
    _PROCESSOR_CONTEXT_TYPES,
    _RECURRENCE_VETO,
    _STORE_NAME_PAYOUT_ENTITIES,
)
from analysis.descriptor.holder import holder_reading, holder_words, store_name_printed, store_name_run_words
from analysis.descriptor.lexical import _before_receiver, _distinctive_words, _joined_text, _originator_segment
from analysis.descriptor.rails import _matches_any, _with_served_cuts, _without_receiver_value
from analysis.descriptor.words import _PAYROLL_PATTERNS, _RECEIVER_FIELD_VALUE
from analysis.payee_matcher import registry_match


_OPERATING_CREDIT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:SETTLEMENT|PAYOUT|DISBURSEMENT)\b"),
    re.compile(r"\bMERCHANT (?:CREDIT|DEPOSIT|PAYMENT|BATCH|PROCESSING)\b"),
    re.compile(r"\bCARD SALES?\b"),
    re.compile(r"\bSALES? (?:CREDIT|DEPOSIT|PROCEEDS)\b"),
    re.compile(r"\bDIRECT DEPOSIT MISC(?:ELLANEOUS)? PAYMENTS?\b"),
    re.compile(r"\bACH (?:CREDIT|SETTLEMENT|PAYOUT)\b"),
    re.compile(r"\bMARKETPLACE (?:PAYMENT|PAYOUT|SETTLEMENT)\b"),
    re.compile(r"\bBATCH (?:CREDIT|DEPOSIT|SETTLEMENT)\b"),
    re.compile(r"\bINVOICE (?:PAYMENT|PAID|DEPOSIT)\b"),
    re.compile(r"\bACCOUNTS? RECEIVABLE\b"),
)

#: §7.1: the card veto: neither a card form nor the processor payout context fires on a row that prints it.
_CARD_VETO = re.compile(
    r"(?<![A-Z])(?:CHBK|CHGBK|CHARGEBACKS?|DISPUTE\w*|ADJUSTMENT|BILLING|DISC|DISCOUNT|MTHLY|INTERCHANGE|PAYROLL"
    r"|LOANS?|CAPITAL|ADVANCE|FUNDING|FINANCING|FINANCE|RETURN(?:ED|S)?|ACCT ?VERIFY|ACCTVERIFY\w*|VERIFY"
    r"|VERIFICATION|INSUR\w*|ZELLE|VENMO|CASH ?APP|E ?TRANSFER|INTERAC|REWARDS?|REBATES?|CASH ?BACK|INTEREST|CLAIMS?"
    r"|CAPI|CAPIT|CAPITA|CAPSEC|FUNDS?|FUNDED|FNDG|FNDNG|FINANCIAL|FINCL|LEND\w*|PROCEEDS|DISB\w*"
    r"|PURCH\w*|CONTRIB\w*|OWNERS?|MEMBER|SHAREHOLDER|RVSL|RVRSL|INTCHG|CORR\w*|FEES|ADV(?:NC?|C)"
    r"|OVERPAY\w*|XFER|SWEEP)\b"
    r"|\b(?:ADJ|FEE|TAX|ADV|CAP\d*(?:SEC)?|MCA|RTN|RET|REV\d*|CB|DUP\w*|TFR|ZBA|BOOK)\b"
    r"|(?<![A-Z])(?:TRANSFER|XFER|TFR) (?:FROM|TO)\b|(?<![A-Z])ONLINE TRANSFER\b"
)
#: §7.1: processor payout context, for merchant_processor and invoice_and_receivables sources only (context, never
#: proof on its own).
_PROCESSOR_PAYOUT_CONTEXT = re.compile(
    r"\bSQ ?\d{6}\b|\bMISC PAYMENTS?\b|\bMSP(?: DIV)?\b|\bDAILY DEP\b|\bST [A-Z0-9]{6,}\b"
    r"|\b(?:RTP|FEDNOW|REAL TIME (?:TRANSFER|PAYMENT)|INSTANT (?:PMT|PAYMENT|TRANSFER)|VISA DIRECT|MC SEND"
    r"|PMNT RCVD|PAYMENT RECEIVED)\b"
)
#: §7.2: the vetoes on every new operating read (a payout form, and an alias added in 5.5).
_OPERATING_PAY_VETO = re.compile(
    r"(?<![A-Z])(?:PAYROLL\w*|PAYRLL|PAYROL|PAYRL|SALARY|SALARIES|REG SAL|WAGES?|DIR ?DEP|DIRDEP|DIRECT DEP|NET ?PAY"
    r"|BONUS|REIMB\w*)\b"
)
_OPERATING_FINANCING_VETO = re.compile(
    r"(?<![A-Z])(?:LOANS?|ADVANCE[SD]?|CAPITAL|LENDING|LENDER|FINANC\w*|FUNDING|FUNDED|PROCEEDS|DRAW)\b|\bADV\b"
)
_OPERATING_REVERSAL_VETO = re.compile(
    r"(?<![A-Z])(?:RETURN(?:ED|S)?|REFUND(?:ED|S)?|RFND|REFND|REVERS(?:AL|ED|E)|VOID(?:ED)?"
    r"|CANCEL(?:LED|ED|LATION)?|CNCL|ADJUSTMENT|ADJUSTED|DISPUTE[DS]?|CHARGEBACK|CREDIT MEMO|REJECT(?:ED)?)\b"
    r"|\b(?:RTN|RFD|ADJ|NSF)\b"
)
_OPERATING_P2P_VETO = re.compile(r"(?<![A-Z])(?:ZELLE|VENMO|CASH APP|E ?TRANSFER|ETRANSFER|INTERAC)\b")


#: §7.2: the aliases of older entities whose reads carry the vetoes above, with their cuts ('RTP CREDIT AMAZO').
_OPERATING_ALIASES_VETOED = _with_served_cuts(OPERATING_ALIASES_READ_WITH_VETOES)
#: §7.2: an employer-type alias (TikTok, Amazon's RTP alias) also refuses these pay words, and the TikTok aliases count
#: only on an ACH-shaped row. Each set holds its aliases' cuts too (§7.0).
_EMPLOYER_PAY_WORDS = re.compile(r"(?<![A-Z])(?:DIR DEP|DIRECT DEP|PAYRL|REIMB|EXP REIMB)\b")
_EMPLOYER_TYPE_ALIASES = _with_served_cuts(
    frozenset({"TIKTOK INC", "TIKTOK USA", "TIKTOK SHOP", "RTP CREDIT AMAZON COM"})
)
_TIKTOK_ALIASES = _with_served_cuts(frozenset({"TIKTOK INC", "TIKTOK USA", "TIKTOK SHOP"}))
_ACH_SHAPED_ROW = re.compile(r"\b(?:ACH|CCD|PPD|ORIG CO NAME|DEPOSIT|PAYMENT|PAYOUT|CORP|CORPORATE)\b")
#: §7.3: a transport marketplace's credit never counts toward recurrence with a wallet, subscription or wire word.
_TRANSPORT_EXTRA_VETO = re.compile(
    r"(?<![A-Z])(?:CASHOUT|CASH OUT|SUBSCRIPTION|MEMBERSHIP|WIRE|FEDWIRE)\b|\b(?:WT|OBI|BNF)\b"
)
#: §7.8: each wholesale auction's aliases as a registry of its own, read on the originator segment.
_AUCTION_ALIAS_REGISTRIES = {
    entity: {entity: OPERATING_REVENUE_READ_ALIASES[entity]}
    for entity, source_type in OPERATING_REVENUE_SOURCE_TYPES.items()
    if source_type == "wholesale_auto_auction"
}
_CARD_FORMS = tuple(
    (form, re.compile(form.pattern), re.compile(form.refusal) if form.refusal else None)
    for form in CARD_SETTLEMENT_CREDIT_FORMS
)
_OPERATING_CONTEXT_WORDS = {
    entity: re.compile(r"\b(?:" + "|".join(words) + r")\b") for entity, words in OPERATING_SOURCE_CONTEXT_WORDS.items()
}
#: §7.1 (the ledger gate): each waiting processor's bare aliases, as whole words, longest first.
_GATED_PROCESSOR_PATTERNS = {
    processor: re.compile(r"\b(?:" + "|".join(
        re.escape(normalize_transaction_description(alias)) for alias in sorted(aliases, key=len, reverse=True)
    ) + r")\b")
    for processor, aliases in GATED_PROCESSOR_ALIASES.items()
}


@dataclass(frozen=True)
class _OperatingSource:
    """§7.2: what the operating-source reader found on one credit."""

    entity: str
    alias: str
    source_type: str | None
    payout_form: bool


def _operating_read_vetoed(row: str, entity: str, alias: str, payout_form: bool) -> bool:
    """§7.2, §7.3: the vetoes of a new operating read (a payout form, or an alias this release added), read on the row
    before its receiver fields: pay, financing, reversal and adjustment, and person-to-person words. An employer-type
    alias also refuses DIR DEP, PAYRL and REIMB, and the TikTok aliases count only on an ACH-shaped row. A transport
    marketplace also refuses wallet, subscription and wire words. A sixteen-character cut carries its alias's vetoes
    (§7.0)."""
    new_read = payout_form or entity in OPERATING_SOURCES_READ_WITH_VETOES or alias in _OPERATING_ALIASES_VETOED
    if not new_read:
        return False
    if (
        _OPERATING_PAY_VETO.search(row)
        or _matches_any(row, _PAYROLL_PATTERNS)
        or _is_payroll_provider_row(row)
        or _OPERATING_FINANCING_VETO.search(row)
        or _OPERATING_REVERSAL_VETO.search(row)
        or _OPERATING_P2P_VETO.search(row)
    ):
        return True
    if alias in _EMPLOYER_TYPE_ALIASES and _EMPLOYER_PAY_WORDS.search(row):
        return True
    if alias in _TIKTOK_ALIASES and not _ACH_SHAPED_ROW.search(row):
        return True
    return OPERATING_REVENUE_SOURCE_TYPES.get(entity) == "transport_marketplace" and bool(
        _TRANSPORT_EXTRA_VETO.search(row)
    )


def _read_inside_a_waiting_processor(text: str, entity: str, alias: str) -> bool:
    """§7.1: the operating alias read lies inside the bare alias of another processor the ledger has not cleared
    ('BY STRI' inside 'JOBBER BY STRI'), so it names no source while that processor waits."""
    return any(
        processor != entity and any(alias in found.group(0) for found in pattern.finditer(text))
        for processor, pattern in _GATED_PROCESSOR_PATTERNS.items()
    )


def _operating_source(text: str) -> _OperatingSource | None:
    """§7.2: the operating source a credit's revenue text names: a payout form first (it names the entity and counts
    as payout context), else the longest operating alias or its sixteen-character cut, read with the receiver
    field's value removed (§5.2). A wholesale-auction alias counts only on the originator segment. A new read that a
    veto of §7.2 refuses names no source, and so does an alias read inside a waiting processor's bare alias (§7.1).
    One helper for step 10 and the recurrence pass."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    for entity, label, pattern in _PAYOUT_FORMS:
        if pattern.search(row) or pattern.search(joined):
            if _operating_read_vetoed(row, entity, label, True):
                return None
            return _OperatingSource(entity, label, OPERATING_REVENUE_SOURCE_TYPES.get(entity), True)
    alias_text = _without_receiver_value(text)
    found = registry_match(alias_text, OPERATING_REVENUE_READ_ALIASES)
    if found is None or _read_inside_a_waiting_processor(alias_text, *found):
        return None
    entity, alias = found
    source_type = OPERATING_REVENUE_SOURCE_TYPES.get(entity)
    if source_type == "wholesale_auto_auction" and registry_match(
        _originator_segment(text), _AUCTION_ALIAS_REGISTRIES[entity]
    ) is None:
        return None
    if _operating_read_vetoed(row, entity, alias, False):
        return None
    return _OperatingSource(entity, alias, source_type, False)


def _card_settlement_form(text: str, *, bank: str | None) -> CardSettlementForm | None:
    """§7.1: the first card-settlement form a credit prints, read on the row before its receiver fields and on the
    joined text, unless the form's own refusal or the card veto matches. NET SETTLE is returned too; the caller
    decides it (an unregistered originator needs three such credits, which the recurrence pass counts)."""
    row = _before_receiver(text)
    joined = _joined_text(row)
    if _CARD_VETO.search(row):
        return None
    for form, pattern, refusal in _CARD_FORMS:
        if form.bank is not None and (bank or "").upper() != form.bank:
            continue
        if not (pattern.search(row) or pattern.search(joined)):
            continue
        if refusal is not None and (refusal.search(row) or refusal.search(joined)):
            continue
        # §7.1 (structural S53): the generic credit-card sales words never read on a row that names a card issuer.
        if form.label == "generic_card_sales" and registry_match(row, CARD_ISSUER_CONTEXT_ALIASES) is not None:
            continue
        return form
    return None


def _has_operating_context(text: str, source: _OperatingSource, *, bank: str | None) -> bool:
    """§7.1, §7.2: a registry alias verifies one row with payout context: a payout form, the operating-context words
    (read on the row and the joined text), a card-settlement form, the entity's own context words, or, for a
    merchant processor or an invoice platform, the processor payout context. The card veto refuses the last two."""
    if source.payout_form:
        return True
    row = _before_receiver(text)
    joined = _joined_text(row)
    if _matches_any(text, _OPERATING_CREDIT_CONTEXT_PATTERNS) or _matches_any(joined, _OPERATING_CREDIT_CONTEXT_PATTERNS):
        return True
    words = _OPERATING_CONTEXT_WORDS.get(source.entity)
    if words is not None and words.search(row):
        return True
    form = _card_settlement_form(text, bank=bank)
    if form is not None and form.label != "net_settle":
        return True
    return (
        source.source_type in _PROCESSOR_CONTEXT_TYPES
        and not _CARD_VETO.search(row)
        and _PROCESSOR_PAYOUT_CONTEXT.search(row) is not None
    )


def _recurrence_vetoed(record: TransactionClassification, text: str) -> bool:
    """§7.0: a credit that never counts toward recurrence and is never lifted by it: payroll, the recurrence veto
    words and card-credit labels (read on the row before its receiver fields), FUNDING outside the three platforms
    that print it on settlements, under the $1 floor, or a direction conflict."""
    return (
        _recurrence_veto_wording(record, text)
        or record.amount < _MICRO_DEPOSIT_FLOOR
        or record.revenue_match_method == "direction_conflict"
        or not record.direction_consistent
    )


def _recurrence_veto_wording(record: TransactionClassification, text: str) -> bool:
    """§7.0: the worded part of the recurrence veto: payroll, a veto word or card-credit label, or FUNDING
    outside the three platforms that print it on settlements."""
    entity = record.revenue_canonical_entity
    # The holder's own words are read on the holder's name when the parser read it.
    holder = holder_reading(record.account_name, record.holder_name)
    return (
        record.classification == "payroll"
        or _recurrence_veto_word(text, holder, entity)
        or (
            entity not in _FUNDING_SETTLEMENT_ENTITIES
            and _recurrence_veto_word(text, holder, entity, _FUNDING_WORD)
        )
    )


def _recurrence_veto_word(
    text: str, account_name: str | None, entity: str | None, pattern: re.Pattern[str] = _RECURRENCE_VETO
) -> bool:
    """§7.0: the recurrence veto on the row before its receiver fields. On a store-name platform
    (_STORE_NAME_PAYOUT_ENTITIES) a veto word that is one of the holder's own words (its account name, or the name the
    bank prints in the receiver field), or the start of one (four letters or more), is not read: the platform prints
    the merchant's store name, which is the holder's, in its entry field ('DOORDASH INC DES:<store> CAPITA ...
    INDN:<store> CAPITAL GROUP'). On every other source, and on a row no registry source decided, a veto word always
    vetoes."""
    if entity not in _STORE_NAME_PAYOUT_ENTITIES or not store_name_printed(text, entity, account_name):
        return pattern.search(_before_receiver(text)) is not None
    holder = set(holder_words(account_name))
    for found in _RECEIVER_FIELD_VALUE.finditer(text):
        holder.update(_distinctive_words(found.group(0).split()[1:]))
    # FW wave 3 (W2-1): the words of a store name that is a run of the holder's name are spared at any length.
    run = store_name_run_words(text, entity, account_name)
    row = _before_receiver(text)
    for found in pattern.finditer(row):
        word = found.group(0)
        if word in run or (len(word) >= 4 and any(own == word or own.startswith(word) for own in holder)):
            continue
        return True
    return False

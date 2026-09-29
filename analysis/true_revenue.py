"""Classification 5.6: the true-revenue pass (docs/superpowers/specs/2026-09-28-true-revenue-design.md §5, §8).

Statement pass 7 (§6.2) runs after every verifying rule of `analysis/transaction_classifier.py`. It reads each posted
credit's payer facts (channel family, payer region, payer name and key, entry fields, the holds of §8.1), then runs
the Q5 and Q6 verifications (§8.5, §8.6), which refuse any row a hold names, and last gives every posted credit its
tier and reason (§5.3), in the order of §8.10.

It imports the classifier's readers at call time (`_classifier`), never at load: the classifier imports this module
at its own load, so a load-time import back would be circular.

The payer region, payer name, entry fields and wire reading are the 5.5 readers' (S2.1 to S2.4): a holder's name in
the receiver field never names a payer (§5.2), a glued leading date never changes a reading (revenue_text), the
§7.9 wire vetoes are `_wire_vetoed` itself, and a wire is any row the 5.5 wire vetoes read as one
(`_wire_vetoes_apply`). The hold words follow the owner's veto convention (S2.2 review, item A): a spelling of four
letters or more (all its words counted) takes a (?<![A-Z]) left boundary, so a digit glued on its left never hides
it; a spelling of three letters or fewer keeps \\b.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Sequence

from .classification_registry import (
    DEALER_FUNDING_PAYERS,
    HEALTHCARE_PAYER_ALIASES,
    PAYOUT_CREDIT_ENTITIES,
)
from .flag_groups import FINANCING_STATES
from .payee_matcher import PayeeMatch, match_known_payee, registry_match
from .revenue import revenue_contribution_flags

if TYPE_CHECKING:
    from .transaction_classifier import TransactionClassification

#: §8.1: the posting labels removed before a hold reads a row: §7.5's credit posting labels, the branch, card and
#: batch CREDIT labels, and the channel phrases.
_HOLD_POSTING_LABELS = re.compile(
    r"\b(?:ELECTRONIC|ACH|RTP|ONLINE|WIRE|BOOK|CORP|CORPORATE|ZELLE|MISC|DIRECT|PAYMENT|DEPOSIT|TRANSFER|MOBILE|EFT"
    r"|CHIPS|FEDWIRE|INSTANT|REAL TIME|COUNTER|POS|ATM|TELLER|BRANCH|CARD|BATCH|MERCHANT|VISA|CHECKCARD|PURCHASE)"
    r"\s+CREDIT\b|^CREDIT\b"
    r"|\bCREDIT FROM\b|\bFUNDS (?:TRANSFER|AVAILABLE)\b|\bINSTANT FUNDS\b"
)
#: §8.1, T4: the credit-side financing roots. A whole-word CREDIT counts only inside a payer name, next to another
#: name word; glued, it always counts. The roots have no left boundary; of the whole words, those of four letters or
#: more take (?<![A-Z]) (the veto convention).
_FINANCING_ROOT = re.compile(
    r"(?:(?<!RE)FUND|CAPIT|CAPTL|LOAN|LEND|FINANC|ADVANC|MORTG|ACCEPTANCE|SERVICING|SERVICER|LEASING|PORTFOL)"
    r"|CRED(?=ORA|IBLY)|[A-Z]CREDIT|CREDIT[A-Z]"
    r"|\b(?:CAP|FIN|ADV|MTG|MCA|RTR|SPV)\b|(?<![A-Z])(?:CAPI|FINA|FINAN|FINL|FNCL|LEASE)\b"
)
_WHOLE_CREDIT = re.compile(r"\bCREDITS?\b")
#: §8.7: the dealer-funding words.
DEALER_FUNDING_WORDS = re.compile(
    r"(?<![A-Z])(?:VHCL PURCH\w*|VEHICLE PURCHASE\b|DEAL ?FUND\w*|FUNDLOAN\b|DEALER (?:FUND\w*|FND|PMT|PAY\w*)\b"
    r"|DLR PMT\b|AUTODLRPMT\b|CONTRACT FUND\w*|VADMIN FEE\b)"
)
#: §8.1: an insurer's name on the payer region.
_INSURER_NAME = re.compile(
    r"(?<![A-Z])(?:INSUR\w*|ASSURANCE\b|MUTUAL\b|CASUALTY\b|INDEMNITY\b|UNDERWRIT\w*)"
)
_CLAIM_WORD = re.compile(r"(?<![A-Z])CLAIMS?\b")
_POSSIBLE_RETURN = re.compile(
    r"(?<![A-Z])RETURN(?:ED|S)?\b|\bADJ\b|(?<![A-Z])ADJ(?:USTMENT|USTED)\b|(?<![A-Z])DISPUTE[DS]?\b"
    r"|(?<![A-Z])CREDIT MEMO\b|(?<![A-Z])OVERPA\w*"
    # §7.8: an auction's guarantee or arbitration refund of a vehicle the dealer bought.
    r"|(?<![A-Z])DEALSHIELD\b|(?<![A-Z])ARB(?:ITRATION)? CREDIT\b"
)
#: §8.1, §7.11: a card credit's posting labels (a refund to the card unless a form or the registry verified it).
_CARD_CREDIT_LABEL = re.compile(
    r"(?<![A-Z])(?:DEBIT CARD CREDIT|POS CREDIT|VISA CREDIT|CHECKCARD CREDIT|PURCHASE CREDIT)\b"
)
#: §8.1 (Q8): pay wording, read on the row before its receiver fields.
_PAY_WORDS = re.compile(
    r"(?<![A-Z])(?:PAYROLL\w*|PAYRLL\b|PAYROL\b|PAYRL\b|SALARY\b|SALARIES\b|REG SAL\b|WAGES?\b|NET ?PAY\b"
    r"|BONUS(?:ES)?\b|PAY PAY\b|PAIE\b|SALAIRES?\b|PAYCHECKS?\b|PAYCHK\b|PR PAY\w*|EMPLOYEE PAY\w*|EMP PAY\b"
    r"|DIR ?DEP\b|DIRDEP\b|DIRECT DEP\b(?!OSIT)|(?:DES|CO ENTRY DESCR) DIRECT DEPOSIT\b"
    r"|EXP(?:ENSE)? REIMB\w*)"
)
#: §8.1: benefit and pension credits.
_PERSONAL_INCOME = re.compile(
    r"(?<![A-Z])(?:XX)?SOC SEC\b|\bSSA\b|\bSSI\b|(?<![A-Z])SUPP SEC\b|(?<![A-Z])(?:XX)?VA BEN\w*"
    r"|(?<![A-Z])UNEMPLOY\w*|(?<![A-Z])UI BEN\w*"
    r"|(?<![A-Z])CHI?LD ?SUPP\w*\b|(?<![A-Z])CHILD ?CTC\b|(?<![A-Z])PENSION\b|(?<![A-Z])ANNUIT\w*"
    r"|(?<![A-Z])RETIRE\w*"
)
#: §8.1: a non-sale purpose.
_NON_SALE_PURPOSE = re.compile(
    r"(?<![A-Z])(?:INVEST\w*|DISTRIB(?!UTORS?\b|UTING\b)\w*|DIVIDENDS?\b|EQUITY\b|CONTRIB\w*|SHAREHOLDER\w*"
    r"|OWNERS?\b(?! OP\b| OPERATORS?\b)|STOCK\b|INTERCO\w*|INTER COMPANY\b|DUE FROM\b|SWEEP\b|ZERO BAL\w*"
    r"|REPAY\w*|PRINCIPAL\b|PAYOFF\b|PROMISSORY\b|CONVERTIBLE\b|TRANCHE\b|DRAWS?\b|DRAWDOWNS?\b"
    r"|DISBURS\w*"
    r"|ESCROW\b|EARNEST\b|SECURITY DEPOSIT\b|DEPOSIT BACK\b|SURPLUS\b"
    r"|GRANTS?\b|DONATION\w*|GIFT\b(?! CARD\b)|COURT\b|JUDGMENT\b"
    r"|REBATES?\b|REIMB\w*|INTEREST\b|REWARDS?\b|CASH ?BACK\b"
    r"|RFND\w*|REFND\w*)"
    r"|\bZBA\b|[A-Z]*REFUND\w*"
)
#: §8.1: a healthcare payer's member or premium credit.
_HEALTHCARE_MEMBER_WORDS = re.compile(
    r"(?<![A-Z])(?:REIMB\w*|MEMBER\b|SUBSCRIBER\b|PREMIUM\b)|\bMBR\b"
)
#: §8.4, T13: an account designation printed by a named transfer.
_ACCOUNT_DESIGNATION = re.compile(
    r"(?<![A-Z])(?:CHECKING|CHKG|SAVINGS|SAVING|SVGS|MONEY MARKET|ACCOUNT|ACCT|EVERYDAY)\b|\b(?:CHK|SAV|MMA|DDA)\b"
    r"|\bX{2,}\d{2,}\b|(?<![A-Z])ENDING (?:IN )?\d{3,}\b"
)
_ACCOUNT_WORDS = frozenset({
    "CHECKING", "CHK", "CHKG", "SAVINGS", "SAVING", "SAV", "SVGS", "MONEY", "MARKET", "MMA", "DDA", "ACCOUNT", "ACCT",
    "EVERYDAY",
})
#: §8.5: the loose wire words, for tiering only (a row the 5.5 wire vetoes read as a wire is one too: _channel).
_LOOSE_WIRE = re.compile(
    r"(?<![A-Z])(?:WIRE|FEDWIRE|FED WIRE|CHIPS CREDIT|SWIFT|FOREIGN REMITTANCE|WT FED|FED REF)\b|\bIWT\b"
)
#: §8.5: a sender that names a bank, a title or an escrow firm never verifies by repetition.
_BANK_OR_TITLE_SENDER = re.compile(
    r"\b(?:BANK|BANCO|BANCORP|N A|TRUST COMPANY|CREDIT UNION|FCU|SAVINGS|TITLE|ESCROW|CLOSING|SETTLEMENT)\b"
)
#: §8.6: the verification-only words: sales wording often enough to count, never proof.
_VERIFICATION_ONLY = re.compile(
    r"(?<![A-Z])(?:SETTLEMENT\b|TAXES\b|FEES\b|SUBSCRIPTIONS?\b|DISCOUNT\w*|COMM?ISS?IONS?\b"
    r"|COMPENSATION\b|EXPENSES?\b|AFFILIATE\b|PERSONAL\b|CLOSING\b|SUPPLY CHAIN\b"
    r"|EARLY PAY(?:MENT)?\b|ALLOWANCES?\b|SHORTAGES?\b)"
    r"|\b(?:TAX|IRS|CRA|FEE|SCF|RMA)\b"
)
_ENTRY_VERIFICATION_ONLY = re.compile(r"(?<![A-Z])(?:FLOOR ?PLAN\b|FLOORPLAN\b|EQUIP\w*)|\bVIN\b")
_CONSUMER_ENTRY = re.compile(r"\b(?:PPD|WEB)\b")
#: §8.6 method names.
_Q6_METHODS = ("named_payer_repeats", "named_payer_company_form", "public_or_healthcare_payer")
#: §8.1 (review C2): the financing words on a registry row: the recurrence veto's financing words (§7.0), the
#: new-read financing veto (§7.2) and the auction's financing words (§7.8). A platform's or processor's capital,
#: advance or loan credit and an auction's floor-plan or NextGear credit are never claimed by the registry.
_REGISTRY_FINANCING_WORDS = re.compile(
    r"(?<![A-Z])(?:LOANS?|CAPITAL|CAPI|CAPIT|CAPITA|CAPTL|FINANC\w*|LEND\w*|ADVANCE[SD]?|ADVNC|ADVN|ADVC"
    r"|CASH ADV\w*|FUNDING|FUNDNG|FUNDED|PROCEEDS|DRAW|FLOOR ?PLAN|FLOORPLAN)\b"
    r"|\b(?:CAP\d*(?:SEC)?|FIN|ADV|MCA|NGC)\b"
)
#: G2 (review I1): a financing root glued inside a word of a registry row (STRIPECAPITAL, SHOPIFYCAPITAL).
_GLUED_FINANCING_ROOT = re.compile(r"CAPITAL|CAPTL|FINANC|FUNDING|FUNDNG|LENDING|LENDER|LOAN")
#: The registry-family methods: a platform, processor or payout the operating registry named (§8.9).
_REGISTRY_METHODS = frozenset({
    "operating_source_requires_context", "operating_source_with_credit_context", "recurring_operating_source",
    "operating_source_related_activity", "wholesale_auction_payout_form",
})
#: §5.3: tiers by revenue state; the two middle tiers are unverified.
_TIER_OF_STATE = {"verified_revenue": "verified", "non_revenue": "non_revenue"}
#: §8.10: the lender and financing debit states payer_debited_as_lender reads.
_LENDER_DEBIT_STATES = frozenset({"confirmed_lender", "potential_lender"}) | FINANCING_STATES


@dataclass(frozen=True)
class CreditFacts:
    """§8: one posted credit's payer facts."""

    channel: str
    region: str
    name: str
    key: tuple[str, ...]
    entry: str
    hold: str | None
    claimed: bool
    wire_n1: bool
    company_form: bool
    public_or_healthcare: bool
    healthcare: bool
    numbered: bool
    electronic: bool
    refused_word: bool
    round_sum: bool
    consumer_entry: bool
    transfer_no_counterparty: bool
    account_designation: bool


def _classifier():
    from . import transaction_classifier

    return transaction_classifier


def healthcare_payer(region: str) -> bool:
    """§5.2: a payer region that matches HEALTHCARE_PAYER_ALIASES."""
    return bool(region) and registry_match(region, HEALTHCARE_PAYER_ALIASES) is not None


def government_payer(region: str) -> bool:
    """§5.2: a payer region the public-payer patterns of §7.6 match at its start, and the payer-name veto does not."""
    classifier = _classifier()
    if not region:
        return False
    name = classifier._PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    found = classifier._PUBLIC_PAYER_NAME.match(name)
    return (
        found is not None
        and not any(ch.isdigit() for ch in found.group(1))
        and classifier._PUBLIC_PAYER_NAME_VETO.search(name) is None
    )


def public_region(text: str) -> str:
    """§5.2: the region a government payer is read on: the payee region of the row before its receiver fields, with
    the template prefixes removed, before the digit cut, so 'TREAS 310' keeps its digits."""
    classifier = _classifier()
    return classifier._payee_region(classifier._strip_revenue_template(classifier._before_receiver(text))).strip()


def _public_named(region: str) -> bool:
    """§8.1: the payer region matches a §7.6 payer pattern or the payer-name veto (a public payer of any kind)."""
    classifier = _classifier()
    if not region:
        return False
    name = classifier._PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    return classifier._PUBLIC_PAYER_NAME.match(name) is not None or bool(
        re.search(r"(?<![A-Z])(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR"
                  r"|UNEMPLOYMENT|WORKFORCE)\b", name)
    )


def _hold_text(text: str) -> str:
    """§8.1: the row before its receiver fields with the posting labels removed."""
    classifier = _classifier()
    return _HOLD_POSTING_LABELS.sub(" ", classifier._before_receiver(text))


def financing_named(text: str, region: str, entry: str, account_name: str | None) -> bool:
    """§8.1, T4: a financing root in the payer region or the entry fields (posting labels removed, and a run equal to
    the holder's whole account name removed first), or, on a row with no payer region, in the row before its
    receiver fields. A whole-word CREDIT counts only inside a payer name, next to another name word."""
    classifier = _classifier()
    holder = classifier.account_name_text(account_name)
    parts = []
    if region:
        payer = _HOLD_POSTING_LABELS.sub(" ", region)
        if len(holder.split()) >= 2:
            payer = payer.replace(holder, " ")
        parts.append(payer)
        name_words = classifier.payer_name(payer).split()
        if len(name_words) >= 2 and _WHOLE_CREDIT.search(" ".join(name_words)):
            return True
        if entry:
            parts.append(_HOLD_POSTING_LABELS.sub(" ", entry))
    else:
        row = _hold_text(text)
        if len(holder.split()) >= 2:
            row = row.replace(holder, " ")
        parts.append(row)
    return any(_FINANCING_ROOT.search(part) for part in parts)


def non_sale_purpose(text: str, region: str) -> bool:
    """§8.1: a non-sale purpose, a public payer's refund or benefit, or a healthcare payer's member or premium credit."""
    classifier = _classifier()
    row = _hold_text(text)
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    healthcare = healthcare_payer(region)
    purpose = _NON_SALE_PURPOSE.search(row)
    if purpose is not None:
        return True
    if _CLAIM_WORD.search(row) and not claim_entry and not (healthcare and re.search(r"(?<![A-Z])CLAIM PMT\b", row)):
        return True
    if _public_named(public_region(text)) and classifier._PUBLIC_PAYER_NON_SALE_WORDS.search(
        classifier._TREASURY_BOILERPLATE.sub(" ", text)
    ):
        return True
    return healthcare and _HEALTHCARE_MEMBER_WORDS.search(row) is not None


def _dealer_funding_payer(text: str) -> str | None:
    """§8.7: the listed auto lender the originator segment names: a vehicle_financing registry entity or a
    DEALER_FUNDING_PAYERS entry; or None."""
    classifier = _classifier()
    segment = classifier._originator_segment(text)
    known = match_known_payee(segment)
    if known is not None and known.state == "vehicle_financing":
        return known.entity
    found = registry_match(segment, DEALER_FUNDING_PAYERS)
    return found[0] if found is not None else None


def _first_word(region: str) -> str | None:
    return _classifier()._payer_first_distinctive_word(region)


def _debit_words(records: Sequence[TransactionClassification], duplicates: set[int]) -> tuple[set[str], set[str]]:
    """The first distinctive words of the statement's posted debits (pass 6's reading, _debit_first_distinctive_word):
    (lender and financing debits, the others)."""
    classifier = _classifier()
    lender: set[str] = set()
    other: set[str] = set()
    for index, record in enumerate(records):
        if index in duplicates or record.amount >= 0 or not record.is_posted:
            continue
        word = classifier._debit_first_distinctive_word(record)
        if word is None:
            continue
        (lender if record.classification in _LENDER_DEBIT_STATES else other).add(word)
    return lender, other


def _channel(text: str) -> str:
    """§5.2: the channel family: wire, ach_eft, person_to_person, check, cash_branch_atm or other. A row the 5.5 wire
    vetoes read as a wire (_wire_vetoes_apply: an incoming-wire label, a third-party book transfer, or WIRE printed
    outside the receiver's value, a glued reference included) is a wire, so Q6 never reads it as an ACH payer."""
    classifier = _classifier()
    row = classifier._before_receiver(text)
    if classifier._is_wire_row(text):
        return "wire"
    if classifier._CONSUMER_P2P_RAIL.search(row) or classifier._PUSH_RAIL.search(row):
        return "person_to_person"
    if classifier._CHECK_DEPOSIT_FORM.search(row):
        return "check"
    if (not classifier._ELECTRONIC_PAYMENT_FORM.search(row) and classifier._CASH_BRANCH_ATM_FORM.search(row)):
        return "cash_branch_atm"
    if classifier._TRANSFER_WORDING.search(row):
        return "person_to_person"
    if _LOOSE_WIRE.search(row) or classifier._wire_vetoes_apply(text):
        return "wire"
    if classifier._ELECTRONIC_PAYMENT_FORM.search(row):
        return "ach_eft"
    return "other"


def _own_words(record: TransactionClassification, text: str) -> set[str]:
    """§7.0: the holder's own words, as the recurrence veto reads them on a store-name platform: the account name's
    distinctive words and the name the bank prints in the receiver field (a delivery platform prints the merchant's
    store there). On every other source there are none (S2.4 review: a veto word always vetoes there)."""
    classifier = _classifier()
    if record.revenue_canonical_entity not in classifier._STORE_NAME_PAYOUT_ENTITIES:
        return set()
    own = set(classifier.holder_words(record.account_name))
    for found in classifier._RECEIVER_FIELD_VALUE.finditer(text):
        own.update(classifier._distinctive_words(found.group(0).split()[1:]))
    return own


def _own_word(word: str, own: set[str]) -> bool:
    """§7.0: a word of four letters or more that is one of the holder's own words or the start of one."""
    return len(word) >= 4 and any(mine == word or mine.startswith(word) for mine in own)


def registry_financing(record: TransactionClassification, text: str) -> bool:
    """§8.1 (review C2): a registry row whose row before its receiver fields prints a financing word, the holder's own
    words aside on a store-name platform (§7.0, S2.4 review) and FUNDING aside on the settlements of the three
    platforms §7.0 names. Such a row is not claimed by the registry: it is held as financing_named_payer."""
    if record.revenue_match_method not in _REGISTRY_METHODS:
        return False
    classifier = _classifier()
    own = _own_words(record, text)
    for found in _REGISTRY_FINANCING_WORDS.finditer(classifier._before_receiver(text)):
        word = found.group(0)
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in classifier._FUNDING_SETTLEMENT_ENTITIES:
            continue
        return True
    return False


def _payout_entity(text: str) -> PayeeMatch | None:
    """§8.9: the payout-credit entity (PAYOUT_CREDIT_ENTITIES) the row names, read without the receiver field's value
    (§5.2: the holder's name never names a payer, as the 5.5 readers read the operating alias); or None."""
    known = match_known_payee(_classifier()._without_receiver_value(text))
    return known if known is not None and known.entity in PAYOUT_CREDIT_ENTITIES else None


def _claimed(record: TransactionClassification, text: str) -> bool:
    """§8.1, §8.9: the operating registry, a payout-credit entity or a factoring payee claimed the row. A registry row
    that prints a financing word is not claimed (review C2)."""
    if record.revenue_match_method in _REGISTRY_METHODS:
        return not registry_financing(record, text)
    if record.classification == "factoring":
        return True
    return _payout_entity(text) is not None


def _transfer_counterparty_words(text: str) -> list[str]:
    """§8.2: the payer words a transfer prints once template prefixes, generic words, account words and reference
    tokens are removed."""
    classifier = _classifier()
    row = classifier._strip_revenue_template(classifier._before_receiver(text))
    return [
        token for token in row.split()
        if classifier._is_payer_word(token) and token not in _ACCOUNT_WORDS
        and not classifier._TRANSFER_WORDING.fullmatch(token)
        and token not in {"TRANSFER", "TRNSFR", "XFER", "TFR", "BR", "TO", "BANKING", "INTERNET"}
    ]


def credit_facts(
    record: TransactionClassification,
    text: str,
    *,
    lender_words: set[str],
    debit_words: set[str],
) -> CreditFacts:
    """§8.1 to §8.9: one posted credit's payer facts, including the first hold of §8.10's order 2 to 11. The payer
    region, name, key and entry fields are the 5.5 readers' (payer_region, payer_name, _payer_key, entry_fields)."""
    classifier = _classifier()
    region = classifier.payer_region(text)
    name = classifier.payer_name(region)
    entry = classifier.entry_fields(text)
    channel = _channel(text)
    row = classifier._before_receiver(text)
    claimed = _claimed(record, text)
    healthcare = healthcare_payer(region) and bool(classifier._ELECTRONIC_PAYMENT_FORM.search(row))
    public = government_payer(public_region(text))
    transfer_words = _transfer_counterparty_words(text) if channel == "person_to_person" else []
    transfer_row = (
        classifier._TRANSFER_WORDING.search(row) is not None
        and classifier._CONSUMER_P2P_RAIL.search(row) is None
        and classifier._PUSH_RAIL.search(row) is None
    )
    hold = _first_hold(
        record, text, region=region, entry=entry, claimed=claimed, lender_words=lender_words,
        debit_words=debit_words,
    )
    return CreditFacts(
        channel=channel,
        region=region,
        name=name,
        key=classifier._payer_key(region),
        entry=entry,
        hold=hold,
        claimed=claimed,
        wire_n1=classifier._is_wire_row(text),
        company_form=classifier.company_form(name),
        public_or_healthcare=public or healthcare,
        healthcare=healthcare,
        numbered=classifier.numbered_company(text, region),
        electronic=classifier._ELECTRONIC_PAYMENT_FORM.search(row) is not None,
        refused_word=bool(
            _VERIFICATION_ONLY.search(entry) or _VERIFICATION_ONLY.search(region)
            or _ENTRY_VERIFICATION_ONLY.search(entry)
        ),
        round_sum=classifier.is_round_sum(record.amount),
        consumer_entry=_CONSUMER_ENTRY.search(text) is not None,
        transfer_no_counterparty=transfer_row and not transfer_words,
        account_designation=transfer_row and bool(transfer_words) and _ACCOUNT_DESIGNATION.search(row) is not None,
    )


def _first_hold(
    record: TransactionClassification,
    text: str,
    *,
    region: str,
    entry: str,
    claimed: bool,
    lender_words: set[str],
    debit_words: set[str],
) -> str | None:
    """§8.1 in §8.10's order (2 to 11): the first hold that names the row, or None. A row the registry, a payout
    entity or a factoring payee claimed takes only the insurer, possible-return, pay and benefit holds; a registry row
    that prints a financing word is held as financing_named_payer (review C2)."""
    classifier = _classifier()
    row = _hold_text(text)
    if record.revenue_match_method == "insurer_customer_payment":
        return "insurer_payer"
    claim_entry = classifier._HCCLAIMPMT.search(text) is not None
    if not claimed and region and (
        _INSURER_NAME.search(region)
        or (_CLAIM_WORD.search(region) and not claim_entry and not healthcare_payer(region))
    ):
        return "insurer_named_payer"
    if record.revenue_match_method != "reversal_cancellation_exclusion" and (
        _POSSIBLE_RETURN.search(row)
        or (_CARD_CREDIT_LABEL.search(text) and record.revenue_classification != "verified_revenue")
    ):
        return "possible_return"
    if not claimed and (
        financing_named(text, region, entry, record.account_name)
        or registry_financing(record, text)
        or _dealer_funding_payer(text) is not None
        or DEALER_FUNDING_WORDS.search(row) is not None
    ):
        return "financing_named_payer"
    word = _first_word(region) if region else None
    if not claimed and word is not None and word in lender_words:
        return "payer_debited_as_lender"
    if not claimed and region and classifier.holder_named(region, record.account_name):
        return "holder_name"
    if _PAY_WORDS.search(classifier._before_receiver(text)) or classifier._is_payroll_provider_row(
        classifier._before_receiver(text)
    ):
        return "payroll_or_salary"
    if _PERSONAL_INCOME.search(classifier._before_receiver(text)):
        return "personal_income"
    if not claimed and non_sale_purpose(text, region):
        return "non_sale_purpose"
    if not claimed and (
        record.revenue_match_method == "payer_remittance_with_counter_debit"
        or (word is not None and word in debit_words)
    ):
        return "payer_also_debited"
    return None


def _wire_verifies(record: TransactionClassification, text: str, facts: CreditFacts, repeats: int) -> bool:
    """§8.5 (Q5): the same company wires twice or more, and the row passes every veto of §7.9 (the 5.5 reader,
    _wire_vetoed: a non-sale purpose, a financing root, any known payee, the own account, a brand-word affiliate, a cut
    financing originator, a title or escrow firm). The holder test is read here too, so a row the holds skip (one the
    registry claimed) never verifies from the holder's name (§6 precedence: Q5 never verifies a row the holder test
    or the numbered-company guard matches)."""
    classifier = _classifier()
    if not facts.wire_n1 or facts.hold is not None or not facts.region or facts.numbered:
        return False
    if classifier.holder_named(facts.region, record.account_name):
        return False
    if classifier.channel_gate(text) is not None:
        return False
    if not (facts.company_form or facts.public_or_healthcare) or repeats < 2:
        return False
    if _BANK_OR_TITLE_SENDER.search(facts.name) or facts.refused_word:
        return False
    return not classifier._wire_vetoed(text, facts.region, record.account_name)


def _q6_method(facts: CreditFacts, repeats: int, all_consumer: bool) -> str | None:
    """§8.6 (Q6): the verifying method of an eligible named ACH or EFT payer, or None. A PPD or WEB entry never
    verifies by repetition alone (a) or by its company form (b, review I6), and neither does a bank or a title or
    escrow firm's company form (§8.5's senders)."""
    if repeats >= 2 and not all_consumer:
        return "named_payer_repeats"
    if facts.company_form and not facts.consumer_entry and not _BANK_OR_TITLE_SENDER.search(facts.name):
        return "named_payer_company_form"
    if facts.public_or_healthcare:
        return "public_or_healthcare_payer"
    return None


def _q6_eligible(record: TransactionClassification, text: str, facts: CreditFacts) -> bool:
    """§8.6: an unverified posted credit with an electronic-payment form and a payer region, which the channel gate
    leaves open, no transfer wording in its entry fields, no wire, no registry, payout or factoring claim, no hold,
    and no numbered company."""
    classifier = _classifier()
    return (
        facts.electronic and bool(facts.region) and facts.channel == "ach_eft"
        and classifier.channel_gate(text) is None
        and not classifier._TRANSFER_WORDING.search(facts.entry)
        and not facts.wire_n1 and not facts.claimed and facts.hold is None and not facts.numbered
    )


def _tier_reason(record: TransactionClassification, text: str, facts: CreditFacts, round_repeat: bool) -> tuple[str, str]:
    """§8.10: the tier and reason of an unverified posted credit, in order."""
    classifier = _classifier()
    if record.revenue_match_method == "direction_conflict":
        return "excluded_pending_review", "direction_conflict"
    if facts.hold is not None:
        return "excluded_pending_review", facts.hold
    if facts.channel == "wire" and not facts.claimed:
        if not facts.region:
            return "excluded_pending_review", "wire_no_sender"
        if facts.refused_word:
            return "counted_flagged", "named_payer_purpose_refused"
        return "counted_flagged", "wire_named_sender"
    if facts.transfer_no_counterparty and not facts.claimed:
        return "excluded_pending_review", "transfer_no_counterparty"
    if facts.account_designation and not facts.claimed:
        return "excluded_pending_review", "transfer_account_designation"
    if facts.channel == "check":
        return "counted_flagged", "check_deposit"
    if facts.channel == "cash_branch_atm":
        return "counted_flagged", "no_payer_printed"
    if facts.channel == "person_to_person" and not facts.claimed:
        return ("excluded_pending_review", "p2p_round_repeat") if round_repeat else ("counted_flagged", "p2p")
    if record.revenue_match_method in _REGISTRY_METHODS:
        return "counted_flagged", "platform_unconfirmed"
    if record.classification == "factoring":
        return "counted_flagged", "factoring_payout"
    if _payout_entity(text) is not None:
        return "counted_flagged", "payout_credit_entity"
    if facts.numbered:
        return "counted_flagged", "numbered_company_payer"
    if facts.region and facts.refused_word:
        return "counted_flagged", "named_payer_purpose_refused"
    if facts.region and facts.electronic:
        return "counted_flagged", "named_payer_one_off"
    if facts.region and not classifier._is_bare_row(text):
        return "counted_flagged", "named_payer_unlabelled"
    return "counted_flagged", "no_payer_printed"


def _with_tier(record: TransactionClassification, tier: str, reason: str | None) -> TransactionClassification:
    """A record with its 5.6 tier, initial tier, reason and contribution flags. The review flag is set for a held
    row only; a counted row is reviewable, not required."""
    return replace(
        record,
        revenue_tier=tier,
        revenue_initial_tier=tier,
        revenue_tier_reason=reason,
        revenue_review_required=tier == "excluded_pending_review",
        **revenue_contribution_flags(record.revenue_classification, tier),
    )


def _verify(record: TransactionClassification, method: str, reason: str, confidence: float) -> TransactionClassification:
    classifier = _classifier()
    return classifier._replace_revenue_state(
        record,
        "verified_revenue",
        match_method=method,
        matched_rule=f"verified_{method}",
        confidence_score=confidence,
        reason=reason,
        context_signals=(*record.revenue_context_signals, method),
    )


def apply_true_revenue_pass(
    records: list[TransactionClassification],
    duplicate_indexes: set[int],
) -> list[TransactionClassification]:
    """Statement pass 7 (§6.2): payer facts, the Q5 and Q6 verifications, then the tiers."""
    classifier = _classifier()
    updated = list(records)
    credits = [
        index for index, record in enumerate(records)
        if index not in duplicate_indexes and record.amount > 0 and record.is_posted
        and record.revenue_classification is not None
    ]
    lender_words, debit_words = _debit_words(records, duplicate_indexes)
    texts = {index: classifier.revenue_text(updated[index].normalized_description) for index in credits}
    facts = {
        index: credit_facts(updated[index], texts[index], lender_words=lender_words, debit_words=debit_words)
        for index in credits
    }
    # §5.2: repeats count a verified credit, or an unverified one no hold names; never a held or conflicting one.
    counting = Counter()
    consumer_only: dict[tuple[str, tuple[str, ...]], bool] = {}
    for index in credits:
        record, fact = updated[index], facts[index]
        if not fact.key or record.revenue_classification == "non_revenue":
            continue
        if record.revenue_match_method == "direction_conflict" or (
            record.revenue_classification == "unverified_deposit" and fact.hold is not None
        ):
            continue
        group = (fact.channel, fact.key)
        counting[group] += 1
        consumer_only[group] = consumer_only.get(group, True) and fact.consumer_entry
    # §8.4: a sender with two or more round sums on the rails or through named transfers.
    round_sums = Counter(
        facts[index].key for index in credits
        if facts[index].channel == "person_to_person" and facts[index].round_sum and facts[index].key
    )
    for index in credits:
        record, fact, text = updated[index], facts[index], texts[index]
        if record.revenue_classification != "unverified_deposit":
            continue
        group = (fact.channel, fact.key)
        repeats = counting[group] if fact.key else 0
        if fact.channel == "wire" and _wire_verifies(record, text, fact, repeats):
            updated[index] = _verify(record, "repeat_wire_sender",
                                     "The same company wires the business twice or more in the statement.", 0.85)
            continue
        if _q6_eligible(record, text, fact) and not fact.refused_word:
            method = _q6_method(fact, repeats, consumer_only.get(group, True))
            if method is not None:
                updated[index] = _verify(record, method, _Q6_REASONS[method], 0.85)
    for index in credits:
        record, fact = updated[index], facts[index]
        tier = _TIER_OF_STATE.get(record.revenue_classification)
        if tier is not None:
            updated[index] = _with_tier(record, tier, None)
            continue
        round_repeat = fact.round_sum and bool(fact.key) and round_sums[fact.key] >= 2
        tier, reason = _tier_reason(record, texts[index], fact, round_repeat)
        updated[index] = _with_tier(record, tier, reason)
    return updated


_Q6_REASONS = {
    "named_payer_repeats": "The same named payer pays the business twice or more in the statement.",
    "named_payer_company_form": "A named company pays the business by ACH or EFT.",
    "public_or_healthcare_payer": "A government or healthcare payer pays the business.",
}


def registry_financing_root(record: TransactionClassification, text: str) -> bool:
    """G2 (§14.3, review I1) on a registry row: a registry financing word (registry_financing), or a financing root
    glued inside a word of the row before its receiver fields, the holder's own words (on a store-name platform) and
    §7.0's FUNDING settlements aside. A root inside a place name (a city whose name holds LEND) is not one: the
    registry's reads are whole words."""
    classifier = _classifier()
    if registry_financing(record, text):
        return True
    own = _own_words(record, text)
    for word in classifier._before_receiver(text).split():
        if _own_word(word, own):
            continue
        if word in {"FUNDING", "FUNDED"} and record.revenue_canonical_entity in classifier._FUNDING_SETTLEMENT_ENTITIES:
            continue
        if _GLUED_FINANCING_ROOT.search(word):
            return True
    return False


def guard_facts(record: TransactionClassification, text: str) -> dict:
    """The census's §14.3 facts of one posted credit (tools/revenue_census.py), read with these readers. The customer
    descriptor is step 11's reading (the text without the receiver field's value, or the joined originator and entry
    before the receiver fields), so a descriptor in the holder's name never marks a row."""
    classifier = _classifier()
    region = classifier.payer_region(text)
    entry = classifier.entry_fields(text)
    row = classifier._before_receiver(text)
    known = match_known_payee(text)
    return {
        "financing_root": financing_named(text, region, entry, record.account_name),
        "registry_root": registry_financing_root(record, text),
        "registry_financing": registry_financing(record, text),
        "pay_or_personal": bool(_PAY_WORDS.search(row) or _PERSONAL_INCOME.search(row)),
        "transfer_no_counterparty": (
            classifier._TRANSFER_WORDING.search(row) is not None
            and not classifier._CONSUMER_P2P_RAIL.search(row) and not classifier._PUSH_RAIL.search(row)
            and not _transfer_counterparty_words(text)
        ),
        "known_financing": known is not None and known.state in FINANCING_STATES,
        "payout_or_factoring": known is not None and (known.entity in PAYOUT_CREDIT_ENTITIES or known.state == "factoring"),
        "numbered_region": classifier._NUMBERED_COMPANY_REGION.search(region) is not None,
        "customer_descriptor": (
            classifier._matches_any(classifier._without_receiver_value(text), classifier._CUSTOMER_INVOICE_DESCRIPTORS)
            or classifier._matches_any(classifier._joined_text(row), classifier._CUSTOMER_INVOICE_DESCRIPTORS)
        ),
        "pooled_while_vetoed": (
            record.revenue_match_method in {"recurring_operating_source", "operating_source_related_activity"}
            and classifier._recurrence_vetoed(record, text)
        ),
        # §14.2: a named payer whose channel is not printed, and whose name alone Q6 (b) or (c) would verify.
        "q6_shape": (
            classifier.company_form(classifier.payer_name(region))
            or government_payer(public_region(text)) or healthcare_payer(region)
        ),
    }

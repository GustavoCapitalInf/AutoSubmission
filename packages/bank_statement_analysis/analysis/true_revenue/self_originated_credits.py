"""Self-originated wires, platform credits, processor payouts."""
from __future__ import annotations

import re
from functools import cache
from typing import Sequence, TYPE_CHECKING

from analysis.classification.credit_predicates import wire_sender_is_beneficiary
from analysis.classification_registry import (
    BARE_PLATFORM_NAMES,
    CARD_PAYOUT_PROCESSOR_NAMES,
    OPERATING_REVENUE_READ_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
)
from analysis.description_text import normalize_transaction_description
from analysis.descriptor.holder import account_name_text, holder_named, holder_receiver_block
from analysis.descriptor.lexical import (
    _before_receiver,
    bank_by_form,
    company_form_outside_address,
    originator_address,
    payer_name,
)
from analysis.descriptor.payer import _is_transfer_or_p2p_row, payer_region
from analysis.descriptor.rails import _bare_incoming_wire, _is_wire_row, _loose_wire_originator
from analysis.descriptor.words import (
    BANK_SETTLEMENT_ORIGINATOR,
    HOLDER_NOISE,
    REVENUE_GENERIC_WORDS,
    _AMEX_ACH_CREDIT,
    _CREDIT_WIRE_BENEFICIARY_VALUE,
    _HOLDER_TRADE_NAME,
    _NUMBERED_COMPANY_REGION,
    _NUMBERED_PROVINCE_START,
    _PUSH_RAIL,
    _RECEIVER_FIELD_VALUE,
    _WIRE_ORIGINATOR_LABEL,
    _WIRE_SENDER_AFTER_LABEL,
)
from analysis.true_revenue.channel import _p2p_rail
from analysis.true_revenue.hold_text import _hold_text
from analysis.true_revenue.holder_names import _holder_names, _without_holder_name
from analysis.true_revenue.sender import _bank_only_payer
from analysis.true_revenue.words import (
    _HOLDER_NAMED_SETTLEMENT_ENTRY,
    _RECEIVER_LABEL,
    _US_STATE_TAIL,
    _WIRE_LAYOUT_WORDS,
    _WIRE_PARTY_LEGAL_FORMS,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


#: §8.1, T4: a wire's originator that reads as a bank by its own form (the classifier's BANK_FORM_ORIGINATOR), never a
#: bank's settlement form (BANK_SETTLEMENT_ORIGINATOR). Money a bank sends on its own behalf is more often loan
#: proceeds or the bank's own funds than a customer's payment: held as financing_named_payer. A3-G refinement: a bank
#: that names the ultimate originator only relays, and the payer region reads that customer (relayed_customer_text).
#: A3-G refinement: a sender the payer region reads as bare channel words names nobody (credit_facts).
_BARE_CHANNEL_WORDS = frozenset({"WIRE", "WIRES", "TRANSFER", "BOOK", "CREDIT"})
#: §8.5, Q5: on the wire channel, a sender the payer region reads only as a bank's or a layout's labels names nobody
#: (Navy Federal's 'BANK WIRE DEPOSIT', 'INCOMING BANK WIRE'), and neither does a region with no name word (TD's glued
#: '<reference>S<reference>WIRE'): wire_no_sender. Falcon Bank's 'INTERNATIONAL IWT' is an incoming-wire label whose
#: sender the classifier reads after the bank's own wire field, now that the reader keeps the text Falcon prints after
#: the amount; a row that prints none names nobody. The label words are the bare channel words, every wire layout word
#: (_WIRE_LAYOUT_WORDS: FEDWIRE, FED, INBOUND, INBD, CHIPS, SWIFT, WT, IWT, DOMESTIC, INTL, INTERNATIONAL, INCOMING ...)
#: and BANK, DEPOSIT, DEP, IN, RECEIVED and CR, so the label rule reads in one place: 'INCOMING FEDWIRE', 'FEDWIRE CR',
#: 'INBOUND WIRE' name no sender.
_WIRE_LABEL_ONLY_WORDS = _BARE_CHANNEL_WORDS | _WIRE_LAYOUT_WORDS | frozenset({
    "BANK", "DEPOSIT", "DEP", "IN", "RECEIVED", "CR",
})
#: §8.5, Q5: the Fedwire and CHIPS originator field's width. A legal form the field cuts to LL and glues to the
#: address after it ('<name> MANAGEMENT LL<city>') ends within two to four characters of the width (the normalizer
#: drops the name's punctuation); a word that starts with LL earlier in the name is a name word ('LLOYD').
_WIRE_ORIGINATOR_WIDTH = 35
_WIRE_CUT_FORM_SLACK = 4
_CUT_LLC = re.compile(r"LL[A-Z]{2,}")
#: A3-G: Bank of America's sending-bank field, up to its next field.
_SENDING_BANK_FIELD = re.compile(r"\bSND BK\b (.*?)(?=\b(?:ID|PMT DET|OBI|RMR|BNF|TRN|IMAD|SRF|RFB)\b|$)")
#: A3-G: an originator equal to the sending bank keeps at least this many letters on its shorter side.
_SENDING_BANK_MIN_LETTERS = 8


def _wire_label_only(region: str) -> bool:
    """§8.5, Q5: a wire's payer region that names nobody: no name word (payer_name is empty), or only a bank's or a
    layout's labels (_WIRE_LABEL_ONLY_WORDS)."""
    words = payer_name(region).split()
    return all(word in _WIRE_LABEL_ONLY_WORDS for word in words)


#: §8.5, Q5: the words a wire's region may print besides its labels that name nobody, beside the classifier's generic
#: words (REVENUE_GENERIC_WORDS, joined at call time: _wire_designation_words): the account-designation and product
#: words, the holder-noise name words, the filler and purpose words and the legal forms. Never a place or nationality
#: word (a numbered company's or a real name's: the provinces, CANADA, USA, AMERICA, AMERICAN, NATIONAL), and never
#: INTEREST or another word a non-sale hold reads ('WIRE TRANSFER IN <ref> INTEREST' keeps its non-sale hold).
_WIRE_DESIGNATION_OWN_WORDS = frozenset({
    # Account designations and products.
    "BUSINESS", "OPERATING", "OPERATIONS", "CHECKING", "SAVINGS", "ACCOUNT", "ACCT", "DDA", "SAV", "CHK", "MONEY",
    "MARKET", "COMMERCIAL", "ANALYZED", "PREMIUM", "PLATINUM", "SELECT", "PREFERRED", "STANDARD", "BASIC", "SIMPLE",
    "ESSENTIALS", "FUNDAMENTALS", "COMPLETE", "ADVANTAGE", "PERFORMANCE", "EVERYDAY", "PLUS", "ELITE", "FREE", "SMALL",
    "TOTAL",
    # Holder-noise name words.
    "TRUST", "GROUP", "HOLDINGS", "SERVICES", "SOLUTIONS", "MANAGEMENT", "ENTERPRISES", "DBA",
    # Filler and purpose words.
    "AMOUNT", "RENT", "THE", "OF", "AND",
    # Legal forms.
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "PLLC", "ULC",
    "PLC",
})
#: §8.5, Q5 (Q5: a wire with a named sender is counted): the product and holder-noise words a company's own name
#: is made of ('PREMIUM SOLUTIONS LLC', 'TOTAL SERVICES INC', 'ELITE MANAGEMENT GROUP LLC', 'ADVANTAGE GROUP LLC',
#: 'SELECT HOLDINGS LLC', 'COMMERCIAL SERVICES INC'), which _wire_generic_company reads as a sender. Never an
#: account-designation word (BUSINESS, OPERATING, OPERATIONS, CHECKING, SAVINGS, ACCOUNT, ACCT, DDA, SAV, CHK, MONEY,
#: MARKET, ANALYZED), a purpose or filler word, TRUST or DBA, a legal form, a generic word or a label word: each of
#: those keeps the no-sender reading.
_WIRE_COMPANY_NAME_WORDS = frozenset({
    "COMMERCIAL", "PREMIUM", "PLATINUM", "SELECT", "PREFERRED", "STANDARD", "BASIC", "SIMPLE", "ESSENTIALS",
    "FUNDAMENTALS", "COMPLETE", "ADVANTAGE", "PERFORMANCE", "EVERYDAY", "PLUS", "ELITE", "FREE", "SMALL", "TOTAL",
    "GROUP", "HOLDINGS", "SERVICES", "SOLUTIONS", "MANAGEMENT", "ENTERPRISES",
})
#: R3-FF F4, the holder-noise name words, one of which a generic company's name must print beside another name word. A
#: lone one ('GROUP LLC', 'SERVICES INC', 'WIRE FROM <ref> SERVICES') is the no-sender shape, and account
#: product words alone ('PLATINUM SELECT', 'ADVANTAGE PLUS LLC') read as an account product's designation: both keep
#: the no-sender hold.
_WIRE_HOLDER_NOISE_NAME_WORDS = frozenset({"GROUP", "HOLDINGS", "SERVICES", "SOLUTIONS", "MANAGEMENT", "ENTERPRISES"})
#: The words that join a company's name words ('THE ADVANTAGE GROUP') and its legal forms.
_WIRE_NAME_CONNECTORS = frozenset({"THE", "OF", "AND"})
_WIRE_LEGAL_FORMS = frozenset({
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LP", "LLP", "PLLC", "ULC",
    "PLC",
})


@cache
def _wire_designation_words() -> frozenset[str]:
    """§8.5, Q5: _WIRE_DESIGNATION_OWN_WORDS and the classifier's generic words."""
    return _WIRE_DESIGNATION_OWN_WORDS | REVENUE_GENERIC_WORDS


def _wire_generic_company(words: Sequence[str], labelled: bool, holder_names: Sequence[str] = ()) -> bool:
    """§8.5, Q5: a sender's name made only of product and holder-noise words that still names a company: two or more
    different name words (_WIRE_COMPANY_NAME_WORDS), at least one of them a holder-noise word
    (_WIRE_HOLDER_NOISE_NAME_WORDS), joined only by THE, OF or AND and legal forms, printed behind an originator label
    (`labelled`: the classifier's _WIRE_ORIGINATOR_LABEL, ORG, B/O, WIRE FROM ...) or ending in a legal form ('WIRE
    TRANSFER IN SELECT HOLDINGS LLC', 'INCOMING WIRE ORG PREMIUM SOLUTIONS REF 1'). A designation, purpose,
    holder-designation (TRUST, DBA), generic or label word anywhere in it keeps the no-sender reading ('BUSINESS LLC',
    'WIRE FROM BUSINESS ACCOUNT', 'ORG OPERATING ACCOUNT', 'TOTAL BUSINESS SERVICES LLC'), and so does a name with no
    label and no form ('WIRE TRANSFER IN SELECT HOLDINGS'). So does a lone name word with a form or behind a label
    ('GROUP LLC', 'SERVICES INC', 'WIRE FROM <ref> SERVICES', 'ORG THE GROUP': the no-sender shapes, which a repeat
    would otherwise verify), and so do product words alone ('PLATINUM SELECT', 'ADVANTAGE PLUS LLC', 'FREE LLC': an
    account product's designation). So does a name whose name words are all words of one of the holder's names
    (`holder_names`, _holder_names): the holder test reads distinctive words, and these are all its noise, so it cannot
    see the holder's own money there; the wire stays held as before."""
    names = [word for word in words if word in _WIRE_COMPANY_NAME_WORDS]
    if len(set(names)) < 2 or not set(names) & _WIRE_HOLDER_NOISE_NAME_WORDS:
        return False
    if not all(word in _WIRE_COMPANY_NAME_WORDS or word in _WIRE_NAME_CONNECTORS or word in _WIRE_LEGAL_FORMS
               for word in words):
        return False
    if any(set(names) <= set(account_name_text(holder).split()) for holder in holder_names if holder):
        return False
    return labelled or words[-1] in _WIRE_LEGAL_FORMS


def _wire_names_nobody(region: str, *, labelled: bool = False, holder_names: Sequence[str] = ()) -> bool:
    """§8.5, Q5: a wire's payer region that names no sender: only labels (_wire_label_only), or only label, holder-noise,
    account-designation, purpose, filler or legal-form words (_WIRE_LABEL_ONLY_WORDS, _wire_designation_words:
    'BUSINESS', 'OPERATING ACCOUNT', 'BUSINESS LLC', 'THE AMOUNT OF'), on every wire layout and the labelled path. A
    numbered company keeps its reading (the classifier's _NUMBERED_COMPANY_REGION or _NUMBERED_PROVINCE_START: '1234567
    ONTARIO INC', '1234567 B C LTD', OQ3). And so does a company named only with product and holder-noise words,
    two or more of them and one a holder-noise word, behind an originator label (`labelled`) or ending in a legal form,
    unless those are the holder's own name's words (`holder_names`; _wire_generic_company)."""
    if _wire_label_only(region):
        return True
    if (
        _NUMBERED_COMPANY_REGION.search(region) is not None
        or _NUMBERED_PROVINCE_START.match(region) is not None
    ):
        return False
    nobody = _WIRE_LABEL_ONLY_WORDS | _wire_designation_words()
    words = payer_name(region).split()
    return all(word in nobody for word in words) and not _wire_generic_company(words, labelled, holder_names)


def _sending_bank_after_label(text: str, region: str, bank: str | None) -> bool:
    """§8.5, Q5: on a row the classifier reads its sender after the wire's label (_WIRE_SENDER_AFTER_LABEL, no
    originator label: _WIRE_ORIGINATOR_LABEL), a region that is only a bank's channel name (_bank_only_payer: a listed
    sending bank's name or the statement's own bank's, after reference tokens and a trailing ACH or N A) names no sender
    ('INBOUND WIRE <sending bank>'). A bank by its own form keeps the bank-originated hold."""
    if _WIRE_SENDER_AFTER_LABEL.match(text) is None or _WIRE_ORIGINATOR_LABEL.search(text):
        return False
    return _bank_only_payer(region, "", bank) in {"sending", "own"}


def _wire_region_names_nobody(text: str, region: str, bank: str | None, holder_names: Sequence[str] = ()) -> bool:
    """§8.5, Q5: the wire channel's blank point (_facts_region, _customer_financier): a region that names nobody
    (_wire_names_nobody), a bare incoming wire (the classifier's _bare_incoming_wire) or a sending bank's channel name
    printed after the wire's label (_sending_bank_after_label). The region's name is read as labelled where the row
    prints an originator label (the classifier's _WIRE_ORIGINATOR_LABEL), beside the holder's names (`holder_names`)."""
    return bool(region) and (
        _wire_names_nobody(region, labelled=_WIRE_ORIGINATOR_LABEL.search(text) is not None,
                           holder_names=holder_names)
        or _bare_incoming_wire(text) or _sending_bank_after_label(text, region, bank)
    )


def _cut_wire_legal_form(region: str) -> bool:
    """§8.5, Q5's repeat arm: a wire sender whose LLC the originator field cut to LL and glued to the address after it
    ('<name> MANAGEMENT LL<city>'): a word after the first that is LL and two or more letters, ending the field (its
    LL within _WIRE_CUT_FORM_SLACK characters of _WIRE_ORIGINATOR_WIDTH). Never a two-letter prefix of another form
    (CO, IN, LI), never a name word that starts with LL earlier in the name ('JOHN LLOYD'), and never read by Q6's
    company form (company_form)."""
    words = region.split()
    for index in range(1, len(words)):
        if _CUT_LLC.fullmatch(words[index]):
            width = len(" ".join(words[:index])) + len(" LL")
            return _WIRE_ORIGINATOR_WIDTH - _WIRE_CUT_FORM_SLACK <= width <= _WIRE_ORIGINATOR_WIDTH
    return False


def _bank_originated_wire(text: str, region: str, *, wire: bool = False) -> bool:
    """§8.1, T4: a wire whose originator reads as a bank: by its own form (the classifier's BANK_FORM_ORIGINATOR: BANK,
    BANCORP, BANK N A, CREDIT UNION, SAVINGS BANK, FEDERAL SAVINGS), or equal to Bank of America's sending bank (SND
    BK) with the field's line-wrap splits read run together (the originator's letters start the sending bank's, or the
    reverse). Only the originator field (the payer region) is read, never the sending or receiving bank field or the
    text after it, and never a bank's merchant-services, bankcard or processor form (BANK_SETTLEMENT_ORIGINATOR), a
    settlement. A3-G refinement: a bank that names its customer after a relay label only relays; the payer region then
    reads the customer (relayed_customer_text), so the bank's form is held only when no customer prints. The form arm
    is the classifier's bank_by_form (never a food or blood bank, never a company whose name holds the bank word); the
    sending-bank arm compares the letters with spaces removed, needs _SENDING_BANK_MIN_LETTERS letters on the shorter
    side and an originator that prints no company form. Both arms read CO or NV as the address's state only in its
    address context (the classifier's originator_address: a ZIP or the country code after it, or the end of a Fedwire
    or CHIPS B/O city and state).

    Read on every row pass 7's wire channel reads (`wire`), not only on a row an incoming-wire label starts ('<BANK> N
    A WIRE', Mercury's '<sender> WIRE' layout); never on a region of labels alone ('BANK WIRE DEPOSIT' names no
    sender: _wire_label_only)."""
    if (
        not region or not (wire or _is_wire_row(text)) or BANK_SETTLEMENT_ORIGINATOR.search(region)
        or _wire_label_only(region)
    ):
        return False
    after, city_state_end = originator_address(text, region)
    if bank_by_form(region, after, city_state_end=city_state_end):
        return True
    sending = _SENDING_BANK_FIELD.search(text)
    if sending is None or company_form_outside_address(region, after, city_state_end=city_state_end):
        return False
    originator = "".join(ch for ch in payer_name(region) if ch.isalpha())
    bank = "".join(ch for ch in sending.group(1) if ch.isalpha())
    shorter = min(len(originator), len(bank))
    return shorter >= _SENDING_BANK_MIN_LETTERS and (bank.startswith(originator) or originator.startswith(bank))


def region_names_holder(record: TransactionClassification, text: str, region: str) -> bool:
    """§14.3 G3: the census's holder fact, read as pass 7's holder hold reads the payer region: any of the holder's
    names (_holder_names), the row's layout setting where another payer's receiver block can print
    (classifier.holder_receiver_block), a processor's settlement under the merchant's own name aside
    (merchant_settlement), and a platform's payout known by its payout id (processor_payout), and a processor's, a
    platform's or a franchisor's credit printing the merchant's own name (platform_credit)."""
    names = _holder_names(record)
    if (
        not region or not names or merchant_settlement(text, names) or processor_payout(text)
        or platform_credit(text, region, names)
    ):
        return False
    block = holder_receiver_block(text, record.bank)
    return any(holder_named(region, name, receiver_block=block) for name in names)


#: §8.1: a processor's or a platform's settlement or payout entry, which prints the merchant's own name as its
#: originator and its receiver (Worldpay's NET SETTLE, Stripe's NETSWEEP, a beverage distributor's FINTECHEFT, the
#: BANKCARD and MERCH deposit forms): never the holder's own push, never held as the holder's name.
_MERCHANT_SETTLEMENT_ENTRY = re.compile(
    r"(?<![A-Z])(?:NET (?:SETTLE|SETLMT|STLMT|SETL)|NETSWEEP|FINTECHEFT|BANKCARD|BANKCD|BNKCD|BKCD|BKCRD|BNKCRD"
    r"|MERCH|MERCHANT|MERCHPAYO\w*|MRCHNTSRVS)(?:SEC)?(?![A-Z])"
)
#: §8.1: Capital One's incoming ACH row, which prints the receiver (the holder) with no label after the originator, its
#: entry and a digit run.
_CAPITAL_ONE_BANK = re.compile(r"(?<![A-Z])CAPITAL ONE\b", re.IGNORECASE)
_CAPITAL_ONE_TRAILING_RECEIVER = re.compile(
    r"^ACH DEPOSIT (?P<originator>[A-Z][A-Z ]*?) \d{4,} (?P<receiver>[A-Z][A-Z ]*?)(?= \S*\d|$)"
)
#: §8.1: the tails Mercury's push prints on Capital One's row, its product after the originator ('<holder>
#: MERCURYACH') and its code after the receiver ('<holder> MRCR <ref>'), read off before the self test compares the
#: two names.
_CAPITAL_ONE_ORIGINATOR_TAIL = re.compile(r"\s*\bMERCURYACH$")
_CAPITAL_ONE_RECEIVER_TAIL = re.compile(r"\s*\bMRCR$")
#: §8.1: the legal forms an originator or a receiver field prints after the name or leaves off (a field cut inside L
#: L C leaves a single letter). CO and COMPANY stay: left off, they would make an insurer's 'X INS CO' the start of
#: an agency's 'X INS AGENCY'.
_SELF_TEST_LEGAL_FORMS = frozenset({"LLC", "INC", "CORP", "LTD", "LIMITED", "LP", "LLP", "PLLC", "L", "C"})
#: §8.1: a name one field cut names the other's holder with this many characters or more.
_SELF_TEST_CUT_CHARACTERS = 15


def _self_test_name(name: str) -> str:
    """§8.1: a name as the self test compares it: its words of letters, the legal forms at its end left off."""
    words = [word for word in name.split() if word.isalpha()]
    while words and words[-1] in _SELF_TEST_LEGAL_FORMS:
        words.pop()
    return " ".join(words)


def _same_name(originator: str, receiver: str) -> bool:
    """§8.1: two fields print one name: equal, or one starts the other at a word with two words or more, or as a cut of
    _SELF_TEST_CUT_CHARACTERS characters or more (the census's class B reading). One shared first word is not one name
    ('NORTHWIND' and 'NORTHWIND MARINE')."""
    ours, theirs = _self_test_name(originator), _self_test_name(receiver)
    if len(ours.replace(" ", "")) < 3 or len(theirs.replace(" ", "")) < 3:
        return False
    shorter, longer = sorted((ours, theirs), key=len)
    if shorter == longer:
        return True
    return longer.startswith(shorter) and (
        len(shorter) >= _SELF_TEST_CUT_CHARACTERS or (longer[len(shorter)] == " " and len(shorter.split()) >= 2)
    )


def merchant_settlement(text: str, names: Sequence[str] = (), *, bare_settlement: bool = True) -> bool:
    """§8.1: the row prints a processor's or a platform's settlement or payout entry under the merchant's own name
    (_MERCHANT_SETTLEMENT_ENTRY), read before the receiver fields: the holder holds skip it. The entry is read outside
    the holder's own name (each of `names`, each side of a DBA name, its runs as _without_holder_name removes them), so
    a holder whose name prints MERCHANT, MERCH or BANKCARD keeps its own money held, and never on an incoming wire or a
    person-to-person or push rail, which print no processor's settlement. A bare SETTLEMENT, SETTLMT or STLMT read
    there too (_HOLDER_NAMED_SETTLEMENT_ENTRY), on a row that is no transfer or person-to-person row (a transfer
    printing the word is the holder's own money): the holds skip it, and it takes its own reading, counted and never
    verified. With `bare_settlement` False that arm is not read (B9's words alone), the reading credit_facts compares
    to name a row the bare word alone released (CreditFacts.settlement_released)."""
    if _is_wire_row(text) or _loose_wire_originator(text):
        return False
    row = _before_receiver(text)
    if _p2p_rail(row) or _PUSH_RAIL.search(row):
        return False
    outside = _outside_holder_names(row, names)
    if _MERCHANT_SETTLEMENT_ENTRY.search(outside) is not None:
        return True
    return (
        bare_settlement and _HOLDER_NAMED_SETTLEMENT_ENTRY.search(outside) is not None
        and not _is_transfer_or_p2p_row(text)
    )


def _outside_holder_names(row: str, names: Sequence[str]) -> str:
    """§8.1: `row` without the holder's own names: each of `names`, whole, each side of a DBA name, and its runs as
    _without_holder_name removes them (merchant_settlement's reading; platform_credit's)."""
    for name in names:
        printed = account_name_text(name)
        for side in (printed, *_HOLDER_TRADE_NAME.split(printed)) if printed else ():
            row = _without_holder_name(row, side, whole_name=True)
    return row


#: §8.1: the operating registry's source types whose entity is a processor or a platform that pays the merchant its
#: own sales (every type but a known operating counterparty).
_PLATFORM_SOURCE_TYPES = frozenset({
    "merchant_processor", "customer_payment_platform", "ecommerce_platform", "ecommerce_marketplace",
    "delivery_marketplace", "booking_marketplace", "transport_marketplace", "invoice_and_receivables",
    "property_management_payments", "wholesale_auto_auction",
})
#: §8.1: a franchisor's or a platform's fee entry, which a franchise system's marketing, technology or royalty fund
#: prints when it credits a location under the location's own name ('FRAN <n> MARKETING FEE', 'TECHNOLOGY FEES').
_PLATFORM_FEE_ENTRY = re.compile(r"(?<![A-Z])(?:FRAN[A-Z]*|ROYALTY|MARKETING|TECHNOLOGY|ADVERTISING) FEES?(?![A-Z])")
#: §8.1: a bank's field that cuts a processor's or a platform's one-word name at the originator's end keeps this many
#: letters or more and drops at most _PLATFORM_CUT_DROPS (a ten-letter processor's name printed with its last letter
#: cut), and the cut is no generic or holder-noise word, so a whole word that starts a name ('SHOP', 'PAYMENT' for
#: 'PAYMENTECH', 'BUILDER' for 'BUILDERTREND') is never read as one.
_PLATFORM_CUT_LETTERS = 7
_PLATFORM_CUT_DROPS = 2


@cache
def _platform_names() -> tuple[re.Pattern[str], tuple[str, ...]]:
    """§8.1: the processors' and platforms' names as a whole-word pattern (the operating registry's aliases and
    their sixteen-character cuts for the _PLATFORM_SOURCE_TYPES entities, the bare platform names and the
    card-payout processors' names), and their one-word names a bank may cut."""
    names = {
        alias for entity, aliases in OPERATING_REVENUE_READ_ALIASES.items()
        if OPERATING_REVENUE_SOURCE_TYPES.get(entity) in _PLATFORM_SOURCE_TYPES for alias in aliases
    }
    names.update(BARE_PLATFORM_NAMES)
    names.update(name for spellings in CARD_PAYOUT_PROCESSOR_NAMES.values() for name in spellings)
    normalized = {normalize_transaction_description(name).strip() for name in names} - {""}
    pattern = re.compile(
        r"(?<![A-Z0-9])(?:" + "|".join(re.escape(name) for name in sorted(normalized, key=len, reverse=True))
        + r")(?![A-Z0-9])"
    )
    words = tuple(sorted(name for name in normalized if name.isalpha() and len(name) > _PLATFORM_CUT_LETTERS))
    return pattern, words


def platform_credit(text: str, region: str, names: Sequence[str] = ()) -> bool:
    """§8.1 (standard A1, A2): the row is a processor's, a platform's or a franchisor's credit that prints the
    merchant's own name, never the holder's own money: read outside the holder's names (`names`,
    _outside_holder_names), its originator (the payer region, or the row's hold text when it prints none) prints a
    processor's or a platform's name (_platform_names: the operating registry's processors and platforms, the bare
    platform names such as INTUIT, the card-payout processors), or its last word is one of their one-word names cut by
    the bank's field (_PLATFORM_CUT_LETTERS letters or more, at most _PLATFORM_CUT_DROPS dropped, never a generic or
    holder-noise word: 'LIGHTSPEE'); or the row prints a franchisor's or a platform's fee entry (_PLATFORM_FEE_ENTRY).
    Never on an incoming wire or a person-to-person or push rail (merchant_settlement's gate), which keep the holder
    hold. It lifts the holder holds only (pass 7's and the census's holder fact, region_names_holder), never verifies."""
    if _is_wire_row(text) or _loose_wire_originator(text):
        return False
    row = _before_receiver(text)
    if _p2p_rail(row) or _PUSH_RAIL.search(row):
        return False
    if _PLATFORM_FEE_ENTRY.search(_outside_holder_names(row, names)) is not None:
        return True
    originator = _outside_holder_names(region or _hold_text(text), names).split()
    if not originator:
        return False
    pattern, words = _platform_names()
    if pattern.search(" ".join(originator)) is not None:
        return True
    last = originator[-1]
    if len(last) < _PLATFORM_CUT_LETTERS or last in HOLDER_NOISE:
        return False
    return any(
        word != last and word.startswith(last) and len(word) - len(last) <= _PLATFORM_CUT_DROPS for word in words
    )


#: §8.1: a platform's payout id printed in the ACH id field, normalized: Bank of America's 'ID:ST-<id>' and Chase's
#: 'IND ID:ST-<id>' (Stripe's payout id, ten characters or more), which a platform's payout under the merchant's
#: statement descriptor prints ('<descriptor> DES:<descriptor> ID:ST-<id> INDN:<merchant>'). The id holds letters and
#: digits, as _PAYOUT_FORMS's ST id does: a town printed after an ID label ('ID:ST <town>') or a number alone is no
#: payout id.
_PROCESSOR_PAYOUT_ID = re.compile(
    r"(?<![A-Z0-9])ID ST (?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10,}(?![A-Z0-9])"
)


def processor_payout(text: str) -> bool:
    """§8.1 (standard A1): the row is a platform's payout, known by its payout id (_PROCESSOR_PAYOUT_ID), whatever
    originator or entry it prints (a payout under the merchant's own descriptor included), never on an incoming wire or
    a person-to-person or push rail (merchant_settlement's gate). It replaces B9's entry-word reading (an entry leading
    with the originator's first word, which the holder's own push printing its name passes too). It lifts holds only
    (the holder holds, region_names_holder, and the counter-debit hold beside the platform's own pull, also_debited),
    never verifies: a platform also pays claims, treasury and capital forms, which the other rules decide."""
    if _PROCESSOR_PAYOUT_ID.search(text) is None:
        return False
    if _is_wire_row(text) or _loose_wire_originator(text):
        return False
    row = _before_receiver(text)
    return not (_p2p_rail(row) or _PUSH_RAIL.search(row))


#: §8.1: the label a wire's beneficiary field prints before its value.
_WIRE_BENEFICIARY_LABEL = re.compile(r"^(?:N?BNF|BENEFICIARY)(?: NAME)?\s*")


#: §8.1: the state codes a wire party's address prints after its town (_US_STATE_TAIL without the country codes),
#: and the country codes it may print after the state.
_WIRE_PARTY_STATES = _US_STATE_TAIL - {"US", "CAUS"}
_WIRE_PARTY_COUNTRIES = frozenset({"US", "USA"})
#: §8.1: the fewest words a party's field prints when a town and a state follow its name (two name words, the town, the
#: state).
_WIRE_PARTY_TOWN_STATE_WORDS = 4


def _wire_party(value: str) -> str:
    """§8.1: the name a wire's sender or beneficiary field prints: its words up to its first token with a digit (the
    address's number), cut after its first legal form. A name no legal form ends is read without the town and state
    its address prints after it ('NORTHWIND MARINE SAMPLEVILLE TX', a country code after the state included), read as
    one town word before the state (a two-word town leaves its first word, which the class-B prefix reading of
    _same_name still matches against a one-word town), when two name words stay before them."""
    words: list[str] = []
    for word in value.split():
        if any(character.isdigit() for character in word):
            break
        words.append(word)
        if word in _WIRE_PARTY_LEGAL_FORMS:
            return " ".join(words)
    if len(words) >= 2 and words[-1] in _WIRE_PARTY_COUNTRIES and words[-2] in _WIRE_PARTY_STATES:
        words.pop()
    if len(words) >= _WIRE_PARTY_TOWN_STATE_WORDS and words[-1] in _WIRE_PARTY_STATES:
        words = words[:-2]
    return " ".join(words)


def _wire_sent_by_its_beneficiary(text: str, region: str) -> bool:
    """§8.1: an incoming wire whose sender is its beneficiary, the holder sending from its account at another bank:
    the originator's first two words are the beneficiary's (classifier. wire_sender_is_beneficiary, the reading
    _wire_vetoed refuses Q5 with) and the two whole names are one (_same_name, each read by _wire_party), so two
    companies sharing two first words ('THE SAMPLE COMPANY INC' and 'THE SAMPLE BAKERY LLC') are never one sender."""
    if not region or not wire_sender_is_beneficiary(text, region):
        return False
    beneficiary = _CREDIT_WIRE_BENEFICIARY_VALUE.search(text)
    if beneficiary is None:
        return False
    return _same_name(_wire_party(region), _wire_party(_WIRE_BENEFICIARY_LABEL.sub("", beneficiary.group(0).strip())))


def self_originated(text: str, region: str, bank: str | None = None, *, bare_settlement: bool = True) -> bool:
    """§8.1: the row moves the holder's own money in, read on the row alone: an incoming wire whose sender is its
    beneficiary (_wire_sent_by_its_beneficiary), or an ACH or EFT credit whose originator is the row's own receiver
    field (INDN, IND NAME, RECEIVER NAME; Capital One's unlabelled trailing receiver), one name by _same_name. A
    processor's or a platform's settlement or payout under the merchant's own name (merchant_settlement, read outside
    that name; a platform's payout id, processor_payout) is no own push. Held as holder_name. American Express's
    unlabelled receiver block is paired too, and Capital One's pair is read without Mercury's MERCURYACH and MRCR tails.
    `bare_settlement` is merchant_settlement's (False: B9's settlement words alone)."""
    if _is_wire_row(text):
        return _wire_sent_by_its_beneficiary(text, region)
    if processor_payout(text):
        return False
    pairs: list[tuple[str, str]] = []
    if region:
        originator = payer_name(region)
        pairs.extend(
            (originator, _RECEIVER_LABEL.sub("", found.group(0), count=1))
            for found in _RECEIVER_FIELD_VALUE.finditer(text)
        )
    # American Express's receiver block (B5's _AMEX_ACH_CREDIT, read on the regex, so a TRANSFER entry is paired too,
    # on any statement's bank): the originator, and, when the payer region holds two words or more, the region
    # without its last word, the entry the template prints into it ('CONTOSO LLC PAYMENT').
    amex = _AMEX_ACH_CREDIT.match(text)
    if amex is not None and region:
        pairs.append((payer_name(region), amex.group("receiver")))
        words = region.split()
        if len(words) >= 2:
            pairs.append((" ".join(words[:-1]), amex.group("receiver")))
    if bank and _CAPITAL_ONE_BANK.search(bank):
        trailing = _CAPITAL_ONE_TRAILING_RECEIVER.match(text)
        if trailing is not None:
            # Mercury's push prints its product after the originator (MERCURYACH) and its code after the receiver
            # (MRCR), which are no words of either name.
            pairs.append((
                _CAPITAL_ONE_ORIGINATOR_TAIL.sub("", trailing.group("originator")),
                _CAPITAL_ONE_RECEIVER_TAIL.sub("", trailing.group("receiver")),
            ))
    return any(
        _same_name(originator, receiver)
        and not merchant_settlement(text, (receiver, originator), bare_settlement=bare_settlement)
        for originator, receiver in pairs
    )


def _facts_region(text: str, channel: str, bank: str | None = None, holder_names: Sequence[str] = ()) -> str:
    """The payer region the pass's facts read (credit_facts): the classifier's payer_region, '' on the wire channel where
    it names no sender. A wire's region of labels alone, or with no name word, names no sender (_wire_label_only). Nor
    does a row an incoming-wire label starts that prints only a reference (the classifier's _bare_incoming_wire),
    whatever word of it the payer reader keeps (a month, a stray TT or FROM): it left the own-account reading only to be
    held as a wire with no sender, never counted. Nor a region of label, holder-noise, account-designation, purpose,
    filler or legal-form words, nor a sending bank's channel name printed after the wire's label:
    _wire_region_names_nobody. A company named only with product and holder-noise words is a sender, behind an
    originator label or ending in a legal form, unless they are the holder's own name's words (`holder_names`)."""
    region = payer_region(text)
    if channel == "wire" and _wire_region_names_nobody(text, region, bank, holder_names):
        return ""
    return region

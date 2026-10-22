"""Channel family, transfer wording and counterparty, CPA codes."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from analysis.classification.credit_predicates import _wire_originator_run
from analysis.classification_registry import P2P_SENDING_BANK_NAMES
from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.lexical import (
    _before_receiver,
    _is_payer_word,
    _is_reference_token,
    _leading_name_words,
    _originator_payer_words,
    _strip_revenue_template,
    company_form,
)
from analysis.descriptor.payer import _sender_payer_region, credit_transfer_wording, payer_region
from analysis.descriptor.rails import _is_wire_row, _wire_vetoes_apply
from analysis.descriptor.words import (
    HOLDER_NOISE,
    REVENUE_GENERIC_WORDS,
    _ACH_ORIGINATOR_FIELD,
    _CASH_BRANCH_ATM_FORM,
    _CHECK_DEPOSIT_FORM,
    _CONSUMER_P2P_RAIL,
    _ELECTRONIC_PAYMENT_FORM,
    _INTERNAL_ACCOUNT_SOURCE_WORDS,
    _OWN_ACCOUNT_PRODUCT_WORDS,
    _PUSH_RAIL,
    _SENDER_END,
)
from analysis.true_revenue.sender import _numbered_province_sender, _statement_bank_names
from analysis.true_revenue.words import (
    _CPA_PAYMENT_CODE,
    _CURRENCY_CONVERSION,
    _DEPOSIT_CHANNELS,
    _INTERAC_COURRIEL,
    _P2P_LAYOUT_PHRASES,
    _RECEIVER_BANK_WORDS,
    _TRANSFER_FIELD_LABEL_WORDS,
    _VIREMENT,
    _WIRE_LAYOUT_WORDS,
)

if TYPE_CHECKING:
    from analysis.classification.record import TransactionClassification


_ACCOUNT_WORDS = frozenset({
    "CHECKING", "CHK", "CHKG", "SAVINGS", "SAVING", "SAV", "SVGS", "MONEY", "MARKET", "MMA", "DDA", "ACCOUNT", "ACCT",
    "EVERYDAY", "CHCKING", "CHKING", "CKG",
})


#: §8.5: the loose wire words, for tiering only (a row the 5.5 wire vetoes read as a wire is one too: _channel).
_LOOSE_WIRE = re.compile(
    r"(?<![A-Z])(?:WIRE|FEDWIRE|FED WIRE|CHIPS CREDIT|SWIFT|FOREIGN REMITTANCE|WT FED|FED REF)\b|\bIWT\b"
)
#: §8.5: on a row that prints transfer wording, the loose wire words and a bare CHIPS ('INCOMING CHIPS TRANSFER') name
#: the wire channel (_channel). A bare CHIPS elsewhere may be a payer's own word, so _LOOSE_WIRE keeps CHIPS CREDIT.
_TRANSFER_WIRE_WORDS = re.compile(_LOOSE_WIRE.pattern + r"|(?<![A-Z])CHIPS\b")
#: §8.2: a reference label and the value after it, letters only or not ('REF IBEABCD').
_TRANSFER_REFERENCE_VALUE = re.compile(
    r"\b(?:REF|REFERENCE|CONF|CONFIRMATION|TRN|TRACE|ID|SEQ|TRANSACTION)\b(?: (?:NO|NUM|NUMBER|NBR))? \S+"
)
#: PAR COURRIEL is an Interac form, so the singular 'VIREMENT PAR COURRIEL' is the rail in _p2p_rail and no
#: transfer wording in _transfer_wording.
_INTERAC_FORM = re.compile(r"(?<![A-Z])(?:INTERAC|E ?TRANSFER|ETRANSFER|E ?TFR|AUTODEPOSIT|PAR COURRIEL)\b")
#: §8.2 (S4.2 follow-up 2): the French transfer and posting words, never a transfer's counterparty ('VIREMENT EN LIGNE
#: TF <reference>', 'VIREMENT ENTRE COMPTES', 'VIREMENT DE FONDS', 'VIREMENT RECU', 'VIREMENT PAR BANQUE EN DIRECT').
_VIREMENT_TRANSFER_WORDS = frozenset({
    "VIREMENT", "LIGNE", "TF", "ENTRE", "COMPTE", "COMPTES", "FONDS", "RECU", "RECUE", "ENTRANT", "ENTRANTE", "PAR",
})
#: §8.2: the French month names and abbreviations a date prints ('02 JUIN VIREMENT EN LIGNE TF <reference>'),
#: never a transfer's counterparty (the English ones are reference tokens already). S4.2 fix round 4: only where
#: a date prints them (_without_date_months): MARS and MAI are also names.
_FRENCH_MONTHS = frozenset({
    "JANV", "JANVIER", "FEVR", "FEVRIER", "MARS", "AVR", "AVRIL", "MAI", "JUIN", "JUIL", "JUILLET", "AOUT", "SEPT",
    "SEPTEMBRE", "OCT", "OCTOBRE", "NOV", "NOVEMBRE", "DEC", "DECEMBRE",
})
#: §8.2 (S4.2 fix round 4): a day of the month printed as its own word beside a month ('02 JUIN', 'JUIN 2').
_DAY_NUMBER = re.compile(r"0?[1-9]|[12]\d|3[01]")
#: §8.2: a bank branch a transfer prints ('AVIS VIREMENT <n> CTR BANCAIRE <branch>'), never its counterparty.
_BANK_BRANCH_WORDS = re.compile(r"(?<![A-Z])(?:CTR BANCAIRE|CENTRE BANCAIRE|SUCCURSALE|BRANCH)\b")
#: §8.6, Q6, Q8 (Payments Canada Standard 007): TD Canada Trust prints the CPA transaction code as the row's last
#: word, with no ACH word: AP (460, accounts payable), MSP (450, miscellaneous payment), BPY (430, bill payment) and
#: APY (439) are an electronic-payment form; PAY (the 200 family, payroll deposit) is pay wording. DIV (250, a
#: dividend) is neither. Read on TD Canada Trust's statements only: a US row's last word is its own.
_CPA_CODE_BANK = re.compile(r"(?<![A-Z])(?:TD )?CANADA TRUST\b", re.IGNORECASE)
_CPA_PAYROLL_CODE = re.compile(r"(?<= )PAY$")
#: §5.2, §8.4: TD Canada Trust prints an incoming e-Transfer with a per-transfer code of two to four letters or digits
#: after masked asterisks, where a sender would stand ('E-TRANSFER ***<code>', 'E-TFR ***<code> EPAY'), read on the
#: row's original description: never a sender, a payer word or a CPA code.
_TD_TRANSFER_CODE = re.compile(r"^E[- ]?(?:TRANSFER|TFR)\s+\*{2,}(?P<code>[A-Za-z0-9]{2,4})\b")
#: §8.1: the company forms that name a currency-exchange company on an originator field beside currency wording
#: ('CURRENCY EXCHANGE INTERNATIONAL DES:PAYMENT', 'FOREIGN EXCHANGE CO DES:PAYMENT'). INTERNATIONAL and INTL are
#: organisation words the generic and wire-layout words drop, and CO a field label the transfer reader drops, so the
#: counterparty reading alone never names such a company.
_CURRENCY_COMPANY_WORDS = frozenset({"LLC", "INC", "CORP", "CO", "LTD", "INTERNATIONAL", "INTL"})


def _cpa_code_bank(bank: str | None) -> bool:
    """The statement is TD Canada Trust's, which prints the CPA transaction code as the row's last word
    (_CPA_CODE_BANK)."""
    return bool(bank) and _CPA_CODE_BANK.search(bank) is not None


def cpa_payment_code(row: str, bank: str | None) -> bool:
    """§8.6: TD Canada Trust's row ends with an electronic-payment CPA code (AP, MSP, BPY, APY)."""
    return _cpa_code_bank(bank) and _CPA_PAYMENT_CODE.search(row) is not None


def cpa_payroll_code(row: str, bank: str | None) -> bool:
    """§8.1, Q8: TD Canada Trust's row ends with the CPA payroll-deposit code (PAY)."""
    return _cpa_code_bank(bank) and _CPA_PAYROLL_CODE.search(row) is not None


def _transfer_code(record: TransactionClassification) -> str | None:
    """The per-transfer code a TD Canada Trust e-Transfer credit prints after its rail (_TD_TRANSFER_CODE, on the
    original description), upper-cased as the normalized text prints it; None on any other row or bank."""
    if not _cpa_code_bank(record.bank):
        return None
    found = _TD_TRANSFER_CODE.match(record.original_description or "")
    return found.group("code").upper() if found is not None else None


def without_transfer_code(record: TransactionClassification, text: str) -> str:
    """§5.2, §8.4: a credit's revenue text without TD Canada Trust's per-transfer code after its e-Transfer rail ('E
    TRANSFER PAY' reads 'E TRANSFER'), the text pass 7's payer facts, holds, CPA-code readers and counter-debit reading
    read (and the census's facts, guard_facts), so a code that spells a word (PAY, CAP, MTG) is never pay wording, a
    financing root or a payer's name. Every other row's text is returned as it is; the reversal and cancel rules, which
    decided before pass 7, stay first."""
    code = _transfer_code(record)
    if code is None:
        return text
    return re.sub(rf"^(E ?(?:TRANSFER|TFR)) {re.escape(code)}(?= |$)", r"\1", text, count=1)


#: §8.2, §8.3: an explicit cash, ATM or check deposit form, which Q2 and Q3 count even when the row also prints
#: transfer wording (Square's 'CASH DEPOSIT TRANSFER IN', 'MOBILE CHECK DEPOSIT TRANSFER'). A teller, branch or
#: counter transfer prints none and stays held ('TELLER TRANSFER').
_EXPLICIT_DEPOSIT_FORM = re.compile(
    r"(?<![A-Z])CASH DEP(?:OSIT)?\b|(?<![A-Z])ATM\b.*(?<![A-Z])DEP(?:OSIT)?\b|(?<![A-Z])DEP(?:OSIT)?\b.*(?<![A-Z])ATM\b"
    r"|(?<![A-Z])(?:MOBILE|REMOTE)(?: ONLINE)? (?:CHECK |CHEQUE )?(?:DEPOSIT|DEP)\b"
    r"|(?<![A-Z])(?:ATM )?CHE(?:CK|QUE)S? (?:DEPOSIT|DEP)\b"
)


def _channel(text: str, bank: str | None = None) -> str:
    """§5.2: the channel family: wire, ach_eft, person_to_person, check, cash_branch_atm or other. A row the 5.5 wire
    vetoes read as a wire (_wire_vetoes_apply: an incoming-wire label, a third-party book transfer, or WIRE printed
    outside the receiver's value, a glued reference included) is a wire, so Q6 never reads it as an ACH payer.

    A3 (precision sample): a transfer that prints the loose wire words (§8.5: FEDWIRE, WIRE, CHIPS, SWIFT ...) and
    names no counterparty ('INCOMING FEDWIRE TRANSFER') is a wire with no sender (Q5: held as wire_no_sender); one that
    names its counterparty keeps the named-transfer reading (T13).

    A check, cash, branch or ATM row that prints transfer wording, no explicit deposit form (_EXPLICIT_DEPOSIT_FORM)
    and names its counterparty once its deposit-channel words are removed ('BRANCH TRANSFER FROM <company>') is a
    named transfer (T13); the statement's bank (`bank`) names no counterparty. 'names its counterparty' is FROM and a
    sender, or a company form (_deposit_transfer_names_counterparty): a reference and a town printed after a branch's
    transfer ('BRANCH TRANSFER <ref> <town>', the booking branch) name nobody, so the row stays held.

    American Express's incoming-ACH label ('ONLINE TRANSFER PAYMENT CREDIT' at the row's start) is no transfer
    wording and is an electronic-payment form, so its template is ACH; the originator's own entry word (TRANSFER)
    still reads as transfer wording, as Bank of America's 'DES:TRANSFER' does. A TD Canada Trust row that ends with
    an electronic-payment CPA code is ACH too (cpa_payment_code)."""
    row = _before_receiver(text)
    if _is_wire_row(text):
        return "wire"
    if _p2p_rail(row) or _PUSH_RAIL.search(row):
        return "person_to_person"
    deposit = None
    if _CHECK_DEPOSIT_FORM.search(row):
        deposit = "check"
    elif (not _ELECTRONIC_PAYMENT_FORM.search(row) and _CASH_BRANCH_ATM_FORM.search(row)):
        deposit = "cash_branch_atm"
    if deposit is not None:
        if (
            _transfer_wording(row) and _EXPLICIT_DEPOSIT_FORM.search(row) is None
            and _deposit_transfer_names_counterparty(text, bank)
        ):
            return "person_to_person"
        return deposit
    if _transfer_wording(row):
        if _TRANSFER_WIRE_WORDS.search(row) and not _transfer_counterparty_words(text, bank):
            return "wire"
        return "person_to_person"
    if _LOOSE_WIRE.search(row) or _wire_vetoes_apply(text):
        return "wire"
    if _ELECTRONIC_PAYMENT_FORM.search(row) or cpa_payment_code(row, bank):
        return "ach_eft"
    return "other"


def _deposit_transfer_names_counterparty(text: str, bank: str | None = None) -> bool:
    """§8.2, T13 (Q2): a check, cash, branch or ATM row's transfer names its counterparty once its deposit-channel words
    are removed (_without_deposit_channel_words): it prints a counterparty word (_transfer_counterparty_words) and,
    after FROM, a sender (_counterparty_tokens of the sender region), or, with no FROM, a company form among the words
    after its transfer wording (_after_transfer_wording). A reference and a town, a street or a name with no form
    printed after a teller's, a branch's or a counter's transfer ('BRANCH TRANSFER 00123 <town>', 'BRANCH TRANSFER <two
    words>') name nobody: the bank prints the booking branch there, and the row stays held (transfer_no_counterparty)."""
    stripped = _without_deposit_channel_words(text)
    if not _transfer_counterparty_words(stripped, bank):
        return False
    if re.search(r"\bFROM\b", _before_receiver(stripped)) is not None:
        return bool(_counterparty_tokens(_sender_payer_region(stripped)))
    tokens = _counterparty_tokens(_after_transfer_wording(stripped))
    return bool(tokens) and company_form(" ".join(tokens))


def _without_deposit_channel_words(text: str) -> str:
    """§8.2, §8.3: the text without its check, cash, branch, teller and ATM forms (the classifier's
    _CHECK_DEPOSIT_FORM and _CASH_BRANCH_ATM_FORM), which never name a transfer's counterparty ('TELLER TRANSFER')."""
    return _CASH_BRANCH_ATM_FORM.sub(" ", _CHECK_DEPOSIT_FORM.sub(" ", text))


def _explicit_deposit(channel: str, row: str) -> bool:
    """§8.2, §8.3: a check, cash, branch or ATM row that prints an explicit deposit form."""
    return channel in _DEPOSIT_CHANNELS and _EXPLICIT_DEPOSIT_FORM.search(row) is not None


def _p2p_rail(row: str) -> bool:
    """§8.4 in pass 7 (S4.2 follow-up 2): the row prints one of the classifier's consumer person-to-person rails
    (_CONSUMER_P2P_RAIL), a VIREMENT counting only in its Interac forms (_INTERAC_FORM). Or Interac's French form,
    singular or plural (_INTERAC_COURRIEL: 'DEPOT AUTO VIREMENTS PAR COURRIEL <sender>'), which _channel reads before
    a cash or branch DEPOT."""
    if _INTERAC_COURRIEL.search(row) is not None:
        return True
    return any(
        found.group(0) != "VIREMENT" or _INTERAC_FORM.search(row) is not None
        for found in _CONSUMER_P2P_RAIL.finditer(row)
    )


def _transfer_wording(row: str) -> bool:
    """§8.2 in pass 7 (S4.2 follow-up 2): the classifier's transfer wording, or a VIREMENT printed without an Interac
    form ('VIREMENT EN LIGNE', 'VIREMENT ENTRE COMPTES'). The transfer wording outside a company-formed ACH
    originator's own name (classifier.credit_transfer_wording), so a company whose name prints TRF, XFR or TRANSFER is
    an ACH payer Q6 reads (the channel, the transfer row and reading, Q7's refusals)."""
    return credit_transfer_wording(row) is not None or (
        _VIREMENT.search(row) is not None and _INTERAC_FORM.search(row) is None
    )


def _transfer_row(row: str) -> bool:
    """§8.2: transfer wording on a row that prints no person-to-person or push rail, which the transfer rules read (a
    counterparty, or none: transfer_no_counterparty)."""
    return _transfer_wording(row) and not _p2p_rail(row) and _PUSH_RAIL.search(row) is None


#: §8.2, §20: the online-banking channel codes and account descriptions a transfer prints, never its counterparty:
#: Citi Business Online (CBUSOL), online banking (OLB), an external transfer (EXT, EXTERNAL), CIBC's CMO, telephone
#: banking (and TELEPHONE before transfer wording), PHONE, a card (CRD), a federal savings bank (FSB), an overdraft
#: sweep's PROTECTION and OVERDRAFT, Found's name, BUSINESS BANKING and OPERATING ACCOUNT, and FUNDING beside TRANSFER
#: ('FUNDING TRANSFER CREDIT'). A custodian's name is not one.
_TRANSFER_CHANNEL_CODES = re.compile(
    r"(?<![A-Z])(?:CBUSOL|OLB|EXT|EXTERNAL|CMO|TELEPHONE BANKING|PHONE|CRD|FSB|PROTECTION|OVERDRAFT|FOUND"
    r"|BUSINESS BANKING|OPERATING ACCOUNT)\b"
    r"|(?<![A-Z])TELEPHONE(?= (?:TRANSFER|TRNSFR|TRSFR|TRANSF|XFER|XFR|TFR|TRF)\b)"
    r"|(?<![A-Z])FUNDING(?= (?:TRANSFER|XFER)\b)|(?<=\bTRANSFER )FUNDING\b"
)
#: §8.2: a credit union's institution name, the one word before CU or FCU ('ACH TRANSFER FROM <name> CU'): a bank's
#: name, never a sender's. A person's name before it keeps its other words.
_CREDIT_UNION_NAME = re.compile(r"(?<![A-Z])[A-Z]+ F?CU\b")
#: §8.2: a sending bank's name glued to its transfer wording ('USAAFSBTRNSFER').
_GLUED_BANK_TRANSFER = re.compile(
    r"(?<![A-Z])(?:"
    + "|".join(re.escape(name.replace(" ", "")) for name in sorted(P2P_SENDING_BANK_NAMES, key=len, reverse=True))
    + r")(?:FSB)?(?:TRANSFER|TRNSFER|TRNSFR|TRSFR|XFER|XFR|TFR|TRF)\b"
)


def _without_bank_and_channel_words(text: str, bank: str | None = None) -> str:
    """§8.2, §20 (the registry's note: a bank's name is never the sender's name): the text without a sending bank's
    name (the registry's P2P_SENDING_BANK_NAMES, _P2P_LAYOUT_PHRASES), the statement's own bank's names (`bank`,
    _statement_bank_names), a bank's name glued to its transfer wording, a credit union's institution name, the
    receiver fields' bank words (_RECEIVER_BANK_WORDS) and the channel codes and account descriptions
    (_TRANSFER_CHANNEL_CODES), so none of them names a transfer's counterparty."""
    stripped = _P2P_LAYOUT_PHRASES.sub(" ", text)
    own = _statement_bank_names(bank) if bank else None
    if own is not None:
        stripped = own.sub(" ", stripped)
    for pattern in (_GLUED_BANK_TRANSFER, _CREDIT_UNION_NAME, _RECEIVER_BANK_WORDS, _TRANSFER_CHANNEL_CODES):
        stripped = pattern.sub(" ", stripped)
    return " ".join(stripped.split())


def _transfer_counterparty_words(text: str, bank: str | None = None) -> list[str]:
    """§8.2: the payer words a transfer prints once template prefixes, generic words, account words and reference
    tokens are removed. The ACH field labels, SEC codes and reference labels are removed with the reference printed
    after them, letters only or not ('REF IBEABCD'), and what is left is read as S2.3 reads a transfer's originator
    (_originator_payer_words), so an account description ('FROM HELOC', 'FROM TAX RESERVE', 'FROM OPERATING') is
    never a counterparty. Failing that, a short or company-formed name after FROM is one
    (_short_or_formed_counterparty). S4.2 follow-up 2: the French transfer and posting words
    (_VIREMENT_TRANSFER_WORDS) are removed too. So are a French month and a bank branch. S4.2 fix round 4: a French
    month only where a date prints it (_without_date_months), on the row's start too. A3 (precision sample): a
    wire's channel and layout words (_WIRE_LAYOUT_WORDS: 'INCOMING FEDWIRE TRANSFER') and currency-conversion
    wording (_CURRENCY_CONVERSION: 'ONLINE BANKING FOREIGN EXCHANGE') are never a counterparty. Nor is a bank's
    name, the statement's own bank (`bank`) included, a channel code or an account description
    (_without_bank_and_channel_words)."""
    text = _without_bank_and_channel_words(text, bank)
    row = _TRANSFER_REFERENCE_VALUE.sub(" ", _BANK_BRANCH_WORDS.sub(" ", _without_date_months(
        _without_currency_conversion(_strip_revenue_template(_before_receiver(text))), row=True
    )))
    words = [
        token for token in row.split()
        if _is_payer_word(token) and not _is_reference_token(token)
        and token not in _ACCOUNT_WORDS and token not in _TRANSFER_FIELD_LABEL_WORDS
        and not _TRANSFER_WORDING.fullmatch(token) and token not in _VIREMENT_TRANSFER_WORDS
        and token not in {"TRANSFER", "TRNSFR", "XFER", "TFR", "BR", "TO", "BANKING", "INTERNET"}
        and token not in _WIRE_LAYOUT_WORDS
    ]
    return _originator_payer_words(" ".join(words)) or _short_or_formed_counterparty(text)


#: §8.2: the HOLDER_NOISE words that describe one of the holder's own accounts or a bank product, never a
#: counterparty's name (a company's name words such as AMERICAN, NATIONAL, HOLDINGS are kept).
_ACCOUNT_DESCRIPTION_WORDS = frozenset({
    "BUSINESS", "PLATINUM", "COMPLETE", "ANALYZED", "COMMERCIAL", "ADVANTAGE", "FUNDAMENTALS", "SIMPLE", "BASIC",
    "PREFERRED", "INTEREST", "OPERATING", "PERFORMANCE", "SELECT", "ESSENTIALS", "CHECK", "TOTAL", "PREMIUM", "SMALL",
    "STANDARD", "FREE", "PLUS", "ELITE", "COMPTE", "DIVERS", "ENTREPRISE", "AFFAIRES", "OPERATIONS", "BANK", "BANQUE",
    "CAISSE", "CU", "FCU", "DBA",
})


def _short_or_formed_counterparty(text: str) -> list[str]:
    """§8.2, T13: a counterparty printed after FROM that the distinctive-word reading drops: two name words of any
    length ('LI WU', 'LE VU'), or a company form ('JD LLC', 'AMERICAN NATIONAL INC', 'USA HOLDINGS LLC'). Read on the
    sender after FROM (the payer region, cut at §5.2's sender ends), without field labels, reference labels and their
    values, reference tokens, generic words, transfer words, account and product words and single letters (payer_name
    drops those too); the name words also leave out HOLDER_NOISE. An account description or a field label after FROM
    ('FROM OPERATING LLC', 'FROM NAME COMPANY LLC') is still no counterparty. [] otherwise.

    On a row that prints no FROM, the company form is read on the words after the transfer wording
    (_after_transfer_wording), so a company, a numbered one included, is a counterparty with or without FROM
    ('VIREMENT RECU 1234567 QUEBEC INC', 'ONLINE TRANSFER 1234567 ONTARIO INC'): counted and flagged, never verified
    (§19 OQ3), under T13's two holds (S4.2 fix round 5, _named_transfer_sender)."""
    if re.search(r"\bFROM\b", _before_receiver(text)) is None:
        tokens = _counterparty_tokens(_after_transfer_wording(text))
        return tokens if tokens and company_form(" ".join(tokens)) else []
    tokens = _counterparty_tokens(_sender_payer_region(text))
    names = [token for token in tokens if token not in HOLDER_NOISE]
    if len(names) >= 2 or (tokens and company_form(" ".join(tokens))):
        return tokens
    return []


def _counterparty_tokens(words: str) -> list[str]:
    """§8.2: a transfer sender's words without bank branches, reference labels and their values, reference tokens,
    field labels, generic words, account and product words, transfer words, French months printed as a date (S4.2 fix
    round 4, _without_date_months) and single letters. A3: nor a wire's channel and layout words, nor
    currency-conversion wording."""
    sender = _TRANSFER_REFERENCE_VALUE.sub(" ", _BANK_BRANCH_WORDS.sub(" ", _without_date_months(
        _without_currency_conversion(words)
    )))
    return [
        token for token in _INTERNAL_ACCOUNT_SOURCE_WORDS.sub(" ", sender).split()
        if len(token) > 1 and not _is_reference_token(token)
        and token not in _TRANSFER_FIELD_LABEL_WORDS and token not in REVENUE_GENERIC_WORDS
        and token not in _ACCOUNT_WORDS and token not in _OWN_ACCOUNT_PRODUCT_WORDS
        and token not in _ACCOUNT_DESCRIPTION_WORDS and not _TRANSFER_WORDING.fullmatch(token)
        and token not in _VIREMENT_TRANSFER_WORDS and token not in _WIRE_LAYOUT_WORDS
    ]


def _without_currency_conversion(words: str) -> str:
    """§8.1, §8.2: the words without currency-conversion wording, which never names a counterparty."""
    return _CURRENCY_CONVERSION.sub(" ", words)


def _named_currency_company(text: str) -> bool:
    """§8.1: a named currency-exchange company: an originator field names it (an ACH originator, the name before DES
    or CO ENTRY DESCR, or after ORIG CO NAME; or a wire's labelled sender, _wire_originator_run), and that name
    prints the wording with a company form beside it (_CURRENCY_COMPANY_WORDS: LLC, INC, CORP, CO, LTD, INTERNATIONAL
    or INTL). A row with no originator field names no company this way ('INTL FOREIGN EXCHANGE DEPOSIT' stays the
    holder's own conversion). Any other name word beside the wording already names the payer, on any row
    (_counterparty_tokens)."""
    if _is_wire_row(text):
        if _wire_originator_run(text) is None:
            return False
    elif _ACH_ORIGINATOR_FIELD.search(_before_receiver(text)) is None:
        return False
    region = payer_region(text)
    if not region or _CURRENCY_CONVERSION.search(region) is None:
        return False
    return any(token in _CURRENCY_COMPANY_WORDS for token in _without_currency_conversion(region).split())


def _without_date_months(words: str, *, row: bool = False) -> str:
    """§8.2 (S4.2 fix round 4): the words without a French month printed as a date: beside a day number ('02 JUIN',
    'JUIN 02'; glued, '02JUIN' is a reference token already) or, read on the row itself (`row`), at its start (after
    a leading date's digits only) before the transfer wording ('JANV VIREMENT PAR BANQUE EN DIRECT <n>'). A month word
    anywhere else is a name's ('TRANSFER FROM MARS INC', 'ONLINE TRANSFER FROM MAI LE')."""
    tokens = words.split()
    kept = []
    for index, token in enumerate(tokens):
        if token in _FRENCH_MONTHS:
            beside_day = any(
                _DAY_NUMBER.fullmatch(tokens[at]) for at in (index - 1, index + 1) if 0 <= at < len(tokens)
            )
            rest = " ".join(tokens[index + 1:])
            # The transfer wording outside a company-formed ACH originator's own name.
            leading = row and all(_is_reference_token(before) for before in tokens[:index]) and (
                credit_transfer_wording(rest) is not None or _VIREMENT.search(rest) is not None
            )
            if beside_day or leading:
                continue
        kept.append(token)
    return " ".join(kept)


def _after_transfer_wording(text: str) -> str:
    """§8.2: the words a transfer printed without FROM prints after its first transfer wording (the classifier's,
    or a VIREMENT), before its receiver fields and up to TO (a recipient). The classifier's wording outside a
    company-formed ACH originator's own name (credit_transfer_wording)."""
    row = _before_receiver(text)
    found = [
        match for match in (credit_transfer_wording(row), _VIREMENT.search(row)) if match is not None
    ]
    if not found:
        return ""
    rest = row[min(found, key=lambda match: match.start()).end():]
    return re.split(r"\bTO\b", rest, maxsplit=1)[0]


#: T13 (S4.2 fix round 5): a numbered company's number printed right before its name: six or more digits, or Quebec's
#: two four-digit groups.
_NUMBER_BEFORE_NAME = re.compile(r"(?:^|\s)(\d{6,}|\d{4} \d{4})\s*$")


def _named_transfer_sender(text: str) -> str:
    """T13, §8.2 (S4.2 fix round 5): the counterparty of a named transfer printed without FROM, read for the two holds
    a counted named transfer stays under (the holder test and the round-sum repeat's key), as the FROM form's payer
    region is read: the words after the transfer wording, up to TO (_after_transfer_wording), from the first word the
    company-form arm keeps (_counterparty_tokens) up to a reference token or one of §5.2's sender ends, read as that
    arm reads them. A numbered company's number printed right before the name is kept on §5.2's province arm
    (_numbered_province_sender), so the holder test reads its digit run and two numbered companies are two senders
    ('ONLINE TRANSFER 1234567 ONTARIO INC', 'ONLINE BANKING TRANSFER 1234-5678 QUEBEC INC'). '' when no word is kept."""
    words = _after_transfer_wording(text)
    tokens = _counterparty_tokens(words)
    if not tokens:
        return ""
    first = re.search(rf"(?<!\S){re.escape(tokens[0])}(?!\S)", words)
    if first is None:
        return ""
    rest = _leading_name_words(words[first.start():])
    end = _SENDER_END.search(rest)
    names = _counterparty_tokens(rest[: end.start()] if end is not None else rest)
    number = _NUMBER_BEFORE_NAME.search(words[: first.start()])
    if names and number is not None and _numbered_province_sender().match(" ".join([number.group(1), *names])):
        return " ".join([number.group(1), *names])
    return " ".join(names)

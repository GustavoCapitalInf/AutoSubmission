"""Revenue text, statement furniture, receiver boundary, reference tokens, company and address forms."""
from __future__ import annotations

import re
from typing import Sequence

from analysis.descriptor.words import (
    BANK_SETTLEMENT_ORIGINATOR,
    HOLDER_NOISE,
    REVENUE_GENERIC_WORDS,
    _ACH_FIELD_SEGMENT,
    _AMEX_ACH_CREDIT,
    _BANK_COMPANY_FORM,
    _COMPANY_FORM,
    _CONSUMER_P2P_RAIL_WORDS,
    _CREDIT_RECEIVER_FIELD,
    _ENTITY_NAME_LABELS,
    _ENTITY_NOISE,
    _GLUED_SEC_CODE,
    _INTERNAL_ACCOUNT_SOURCE_WORDS,
    _NAME_STARTERS,
    _OWN_ACCOUNT_PRODUCT_WORDS,
    _PAYEE_TEMPLATE_PREFIX,
    _RECEIVER_FIELD_LABELS,
    _RELAY_ORIGINATOR_LABEL,
    _REVENUE_TEMPLATE_PREFIX,
    _WIRE_ORIGINATOR_LABEL,
)


#: §7.0: a date the bank prints at the row's start, glued to the first word ('01/02Zelle ...'
#: normalizes to '01 02ZELLE ...'). Two numbers of one or two digits, each 1 to 31 (a month and a day, in either
#: order), then a letter with no space before it; no other leading number is removed. A spaced pair is kept: '5 3 ...'
#: is Fifth Third's 5/3 brand (fix round 2). The channel gate reads a spaced row through its own patterns: their left
#: boundary is (?<![A-Z]) and a form anchored at the row's start accepts a leading date (fix round 3).
_LEADING_DATE = re.compile(r"^(?:0?[1-9]|[12]\d|3[01]) (?:0?[1-9]|[12]\d|3[01])(?=[A-Z])")
#: §7.0: the fields between Chase's originator and its entry description, and Bank of America's DES label.
_CHASE_FIELDS_BETWEEN = re.compile(r" ORIG ID \S+ DESC DATE(?: \S+)? CO (?:ENTRY )?DESCR ")
_BOFA_DES_FIELD = re.compile(r" DES ")
#: §7.0, §8.4: a consumer rail's word with a reference's digits glued after it, as CIBC prints its e-Transfer
#: ('E-TRANSFER<reference> <sender> <card>'; Chase's 'ZELLE<reference>' reads the same way). The revenue text splits the
#: digits off (revenue_text), so the rail, whose right boundary stays \b, reads the row as it reads the spaced twin.
#: Only a rail's word is split: CIBC's 'CMO TRANSFER<n>' stays glued transfer wording.
_GLUED_RAIL_REFERENCE = re.compile(r"(?<![A-Z])(" + _CONSUMER_P2P_RAIL_WORDS + r")(?=\d)")
#: The statement furniture a parser glues onto a row's description, each form starting a tail that runs to the row's end,
#: never a transaction's words: TD's footer and its "How to balance your account" back panel ('CALL 1 <phone> FOR 24 HOUR
#: BANK BY PHONE ...', 'BANK DEPOSITS FDIC INSURED ...', 'HOW TO BALANCE YOUR ACCOUNT ... FOR CONSUMER LOAN ACCOUNTS
#: ONLY ...
#: ADD ANY INTEREST EARNED ...'); a Symitar credit union's balance summary, check recap and fee summary (the ending
#: balance's date and amount before ENDING BALANCE, 'CLEARED CHECK RECAP', 'FEE SUMMARY THIS PERIOD', '... TOTAL RETURNED
#: ITEM FEES'); a statement's page header ('<n> STATEMENT OF ACCOUNT ... STATEMENT PERIOD', TD's and Symitar's), Citizens'
#: continued-page header and footer ('PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE', 'MEMBER FDIC <mark> EQUAL HOUSING
#: LENDER', 'CONTINUED DEPOSITS AND CREDITS'), Fifth Third's disclosure line ('FOR ADDITIONAL INFORMATION AND ACCOUNT
#: DISCLOSURES ...') and a page number ('PAGE <n> OF <n>', after Citibank's form code '<nnn> R<n> <nn>F<nnn>' and a
#: repeated 'PAGE <n>'). A row the furniture would leave with no letter keeps its text (without_statement_furniture). And
#: Zions' legal-name footer, which its reader glues with the page break's counters onto the last row before it ('DEPOSIT
#: A DIVISION OF ZIONS BANCORPORATION N A <n> PAGE <n> PAGE <n> OF <n> ...'), only before a page counter, so a wire
#: relayed by a Zions division ('... VIA <bank> A DIVISION OF ZIONS BANCORPORATION N A REF...') is never cut; Navy
#: Federal's page header, 'JOINT OWNER(S): <names|NONE>' after
#: or without 'STATEMENT OF ACCOUNT', so its OWNER never holds a deposit.
_STATEMENT_FURNITURE = re.compile(
    r"(?<![A-Z])(?:"
    r"CALL \d \d{3} \d{3} \d{4} FOR \d{2} HOUR BANK BY PHONE\b"
    r"|BANK DEPOSITS FDIC INSURED\b"
    r"|HOW TO BALANCE YOUR ACCOUNT\b"
    r"|(?:\d+ )*ENDING BALANCE (?=CLEARED CHECK RECAP\b|YOUR MINIMUM BALANCE\b)"
    r"|CLEARED CHECK RECAP\b"
    r"|FEE SUMMARY THIS PERIOD\b"
    r"|THIS PERIOD YEAR TO DATE TOTAL (?:OVERDRAFT|RETURNED ITEM) FEES\b"
    r"|(?:\d{1,3} )?STATEMENT OF ACCOUNT\b(?=.*\bSTATEMENT PERIOD\b)"
    r"|PLEASE SEE ADDITIONAL INFORMATION ON NEXT PAGE\b"
    r"|MEMBER FDIC(?: (?:[A-Z]|\d))? EQUAL HOUSING LENDER\b"
    r"|CONTINUED DEPOSITS AND CREDITS\b|DEPOSITS AND CREDITS CONTINUED\b"
    r"|FOR ADDITIONAL INFORMATION AND ACCOUNT DISCLOSURES\b"
    r"|(?:\d{3} R\d \d{2}F\d{3} )?(?:PAGE \d+ )?PAGE \d+ OF \d+\b"
    r"|A DIVISION OF ZIONS BANCORPORATION N A(?=(?: \d+)* PAGE \d+\b)"
    r"|(?:STATEMENT OF ACCOUNT )?JOINT OWNER S\b"
    r")"
)


def revenue_text(text: str) -> str:
    """§7.0: the text every credit revenue rule reads: the normalized row without a glued leading date ('01 02ZELLE
    PAYMENT' becomes 'ZELLE PAYMENT', so a glued date never hides a rail from the channel gate or a label from a
    reader anchored at the row's start; a spaced '5 3...' is kept), and with Chase's glued SEC code split ('CO ENTRY
    DESCR HCCLAIMPMTSEC CCD' becomes 'CO ENTRY DESCR HCCLAIMPMT SEC CCD'). And without the statement furniture a
    parser glued onto it (without_statement_furniture), so a footer's LOAN, INTEREST EARNED or RETURNED ITEM never
    decides a deposit. And with a reference glued after a consumer rail's word split off it (_GLUED_RAIL_REFERENCE:
    CIBC's 'E TRANSFER<n> <sender>' reads 'E TRANSFER <n> <sender>'), so the rail reads the row on every bank as it
    reads the spaced form. Debits keep their text."""
    text = _GLUED_RAIL_REFERENCE.sub(r"\1 ", _LEADING_DATE.sub("", text, count=1))
    return _GLUED_SEC_CODE.sub(r"\1 SEC \2", without_statement_furniture(text))


def without_statement_furniture(text: str) -> str:
    """§7.0: the row up to the first statement furniture a parser glued onto it (_STATEMENT_FURNITURE: a footer, a
    back panel, a balance or fee summary, a page header or number), every word after it dropped. A row whose words
    before the furniture hold no letter keeps its text (the furniture would leave it nothing to read)."""
    found = _STATEMENT_FURNITURE.search(text)
    if found is None:
        return text
    kept = text[: found.start()].rstrip()
    return kept if any(character.isalpha() for character in kept) else text


def _joined_text(text: str) -> str:
    """§7.0: the originator and the entry description side by side: Bank of America's ' DES ' and Chase's 'ORIG
    ID <id> DESC DATE [<date>] CO ENTRY DESCR' removed between them."""
    return _BOFA_DES_FIELD.sub(" ", _CHASE_FIELDS_BETWEEN.sub(" ", text, count=1), count=1)


def _before_receiver(text: str) -> str:
    """§5.2: the row up to its first receiver field (description_text.RECEIVER_FIELD_LABELS: INDN, IND NAME, RECEIVER
    NAME, RECV NAME, IND ID). On American Express's incoming-ACH template, up to its id: the receiver block that
    follows prints no label (_AMEX_ACH_CREDIT).

    On the template, the id is followed by the template's own EXTERNAL label (the receiver block between them cut out;
    the sending bank and trace after EXTERNAL still dropped), so every reader of the label's three exceptions
    (_TRANSFER_WORDING, _ELECTRONIC_PAYMENT_FORM, _REVENUE_TEMPLATE_PREFIX) reads the full template on the row too
    (_AMEX_LABEL_ORIGINATOR's template arm), whatever the originator's first word. The row is the text's own prefix up
    to the id; EXTERNAL is never a payer word (REVENUE_GENERIC_WORDS), and the payer region still ends at the id (a
    reference token)."""
    amex = _AMEX_ACH_CREDIT.match(text)
    if amex is not None:
        return text[: amex.end("id")] + text[amex.end("receiver"): amex.end()]
    return _CREDIT_RECEIVER_FIELD.split(text, 1)[0].rstrip()


def _strip_revenue_template(row: str) -> str:
    """§5.2: the row with the bank's template words before the payer removed."""
    for _ in range(3):
        stripped = _PAYEE_TEMPLATE_PREFIX.sub("", row, count=1).lstrip()
        stripped = _REVENUE_TEMPLATE_PREFIX.sub("", stripped, count=1).lstrip()
        if stripped == row:
            break
        row = stripped
    return row


def _leading_name_words(region: str) -> str:
    """The region's words up to the first reference token after a name word; leading reference tokens are kept, so a
    numbered company keeps its number (§5.2)."""
    words: list[str] = []
    started = False
    for token in region.split():
        if _is_reference_token(token):
            if started:
                break
        else:
            started = True
        words.append(token)
    return " ".join(words)


#: A wire originator that reads as a bank by its own form (BANK, BANCORP, BANK N A, CREDIT UNION, SAVINGS BANK,
#: FEDERAL SAVINGS), and a bank's merchant-services, bankcard, processor and settlement forms, which are settlements,
#: never a bank's own money nor a relay. The true-revenue pass holds a bank originator (financing_named_payer). Never
#: a food or blood bank, and never a company whose name holds the word (bank_by_form). And BANKING ('WESTPAC BANKING
#: CORP', whose BANK the word boundary missed) and the non-English bank words (_NON_ENGLISH_BANK_WORDS: BANCO, BANCA,
#: BANQUE, BANCAIRE, SPARKASSE).
BANK_FORM_ORIGINATOR = re.compile(
    r"(?<![A-Z])(?:BANK(?:ING)?|BANCORP|BANCO|BANCA|BANQUE|BANCAIRE|SPARKASSE|CREDIT UNION|FEDERAL SAVINGS)\b"
)
#: A non-English bank word leads or sits inside the bank's own name ('BANCO <name> SA', 'BANCA <name> DI <town> SPA',
#: 'UNION BANCAIRE PRIVEE UBP SA'), so a company form after it is the bank's own.
_NON_ENGLISH_BANK_WORDS = frozenset({"BANCO", "BANCA", "BANQUE", "BANCAIRE", "SPARKASSE"})
#: A food or blood bank is no bank. Nor a sperm, eye, tissue, milk, bone or cord-blood bank (a customer paying by
#: ACH, never a bank's pull); read through bank_by_form, so the relay reader and the bank-originated wire refuse
#: them too.
_NOT_A_BANK = re.compile(r"(?<![A-Z])(?:FOOD|BLOOD|SPERM|EYE|TISSUE|MILK|BONE|CORD BLOOD) BANK\b")
_BANK_OWN_FORM_WORDS = frozenset({"CO", "PUBLIC", "N", "A", "NA", "AND", "TRUST"})
_BANK_OF_PLACE_WORDS = 4
#: The company-form words that are also US state codes (Colorado, Nevada). Printed as the address's state they are
#: never a company form: 'NORTHWIND BANK DENVER CO 80202 US'. The word is the state only when a ZIP or the country
#: code follows it (_AFTER_ADDRESS_STATE, read on the region and the row's text after it), or when it ends a Fedwire
#: or CHIPS B/O field's city and state (_CITY_STATE_WIRE_LAYOUT); never at the end of any other field, so Bank of
#: America's 'ORIG:LEFT BANK TRADING CO' and Chase's 'B O WEST BANK OIL CO REF' print a company form.
_STATE_CODE_FORM_WORDS = frozenset({"CO", "NV"})
_AFTER_ADDRESS_STATE = re.compile(r"\s*(?:\d{5}\b|(?:US|USA|UNITED STATES)\b)")
#: The wire layouts whose B/O field prints the sender's city and state last.
_CITY_STATE_WIRE_LAYOUT = re.compile(r"^(?:FEDWIRE|CHIPS) CREDIT\b")


def company_form_outside_address(
    region: str, after: str = "", *, city_state_end: bool = False
) -> re.Match[str] | None:
    """The first company form (_BANK_COMPANY_FORM) of the region that is not the address's state. CO or NV is the
    state when a ZIP or the country code follows it, in the region or in `after` (the row's text right after the
    region), or when it ends the region and `city_state_end` says the region is a Fedwire or CHIPS B/O field
    (originator_address)."""
    region = region or ""
    tail = region + after
    for form in _BANK_COMPANY_FORM.finditer(region):
        if form.group(0) in _STATE_CODE_FORM_WORDS and (
            _AFTER_ADDRESS_STATE.match(tail, form.end()) is not None
            or (city_state_end and not region[form.end():].strip())
        ):
            continue
        return form
    return None


def originator_address(text: str, region: str) -> tuple[str, bool]:
    """The address context of a wire's originator region: the row's text right after the region, and whether the
    region is a Fedwire or CHIPS B/O field, which prints the sender's city and state last. ('', False) when no
    originator label starts the region (a sender printed after the wire's label, Santander's layout, or a relayed
    customer)."""
    found = _WIRE_ORIGINATOR_LABEL.search(text or "")
    if found is None or not region:
        return "", False
    rest = text[found.end():]
    if not rest.startswith(region):
        return "", False
    city_state = found.group(0).strip() == "B O" and _CITY_STATE_WIRE_LAYOUT.match(text) is not None
    return rest[len(region):], city_state


def bank_by_form(region: str, after: str = "", *, city_state_end: bool = False) -> bool:
    """The originator reads as a bank by its own form (BANK_FORM_ORIGINATOR), never a bank's settlement form
    (BANK_SETTLEMENT_ORIGINATOR), a food or blood bank, or a company whose name holds the bank word: a company form
    (_BANK_COMPANY_FORM) counts only as the bank's own, right after its bank word, after 'OF <place>'
    (_BANK_OF_PLACE_WORDS words) or the bank's own form words (_BANK_OWN_FORM_WORDS). Read on the originator up to a
    relay label, whose relayed customer is no part of the bank's name. `after` and `city_state_end` are the region's
    address context (originator_address), read for the address's state only. A non-English bank word
    (_NON_ENGLISH_BANK_WORDS) leads or sits inside the bank's own name, so any company form after it is the bank's own;
    BANKING keeps the English rule ('WESTPAC BANKING CORP' is a bank, 'CONTOSO BANKING SOLUTIONS LLC' is not)."""
    relay = next((label for label in _RELAY_ORIGINATOR_LABEL.finditer(region or "") if label.start() > 0), None)
    if relay is not None:
        after = region[relay.start():] + after
    region = (region or "")[: relay.start()] if relay is not None else (region or "")
    found = BANK_FORM_ORIGINATOR.search(region)
    if found is None or BANK_SETTLEMENT_ORIGINATOR.search(region) or _NOT_A_BANK.search(region):
        return False
    form = company_form_outside_address(region, after, city_state_end=city_state_end)
    if form is None:
        return True
    if form.start() < found.start():
        return False
    if found.group(0) in _NON_ENGLISH_BANK_WORDS:
        return True
    between = region[found.end(): form.start()].split()
    if not between or all(word in _BANK_OWN_FORM_WORDS for word in between):
        return True
    return between[0] == "OF" and len(between) <= _BANK_OF_PLACE_WORDS


def _is_payer_word(token: str) -> bool:
    """§8.2: a token that may name a payer: not a generic word, a single letter, a masked number or a month. A
    token that holds digits names one only through three or more letters glued to them ('2054BANKCARD' after a
    glued date with a year, 'MRCH22064280019')."""
    if token in REVENUE_GENERIC_WORDS or len(token) < 2 or _MASKED_TOKEN.fullmatch(token) or token in _ENTITY_MONTHS:
        return False
    if not any(ch.isdigit() for ch in token):
        return True
    letters = "".join(ch for ch in token if ch.isalpha())
    return len(letters) >= 3 and letters not in REVENUE_GENERIC_WORDS


def payer_name(region: str) -> str:
    """§5.2: the payer region's words without the tokens that hold a digit and the single letters."""
    return " ".join(
        token for token in region.split() if not any(ch.isdigit() for ch in token) and len(token) > 1
    )


def _distinctive_words(words: Sequence[str]) -> list[str]:
    """§5.2: the words that may name a holder or a payer: no noise word, no digit, three letters or more."""
    return [
        word for word in words
        if word not in HOLDER_NOISE and not any(ch.isdigit() for ch in word) and len(word) > 2
    ]


def _first_distinctive_word(words: Sequence[str]) -> str | None:
    """§5.2: the first word of four or more letters that is not a common name-starter."""
    return next((word for word in words if len(word) >= 4 and word not in _NAME_STARTERS), None)


#: A date the bank prints at the row's start, before a numbered company's number or a numbered template: 'MM DD ',
#: 'MMDD ', or 'MM ' before a day glued to the number ('03/021234567 ONTARIO INC' normalizes to '03 021234567
#: ONTARIO INC', whose glued run is itself six or more digits). Only the numbered-company guard reads past it,
#: failing closed (more rows are numbered); revenue_text keeps a spaced pair, so Fifth Third's '5 3...' is
#: otherwise untouched.
_NUMBERED_LEADING_DATE = re.compile(
    r"^(?:\d{1,2} \d{1,2} |\d{4} |\d{1,2} )"
    # The lookahead takes every template of _NUMBERED_COMPANY_TEMPLATE, PMT included.
    r"(?=\d{6,}\b|\d{4} \d{4} [A-Z]|(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT)"
    r" \d{6,}\b)"
)


def _skip_numbered_leading_date(text: str) -> str:
    """The text without a leading date printed before a numbered company's number."""
    return _NUMBERED_LEADING_DATE.sub("", text, count=1)


def company_form(name: str) -> bool:
    """§5.2: a legal-form word after the payer name's first word, or an institution word."""
    return _COMPANY_FORM.search(name) is not None


def is_round_sum(amount: float) -> bool:
    """§5.2: at least $100 and a whole multiple of $100, compared in integer cents."""
    cents = round(abs(amount) * 100)
    return cents >= _ROUND_SUM_DOLLARS * 100 and cents % (_ROUND_SUM_DOLLARS * 100) == 0


#: §8.10: the round sum's step, in whole dollars.
_ROUND_SUM_DOLLARS = 100


def _originator_payer_words(words: str) -> list[str]:
    """The words of a transfer's originator that may name a payer: no reference token, no _INTERNAL_ACCOUNT_SOURCE
    account word, no HOLDER_NOISE or generic word (_distinctive_words) and no account-type or product word. An
    originator that prints none describes one of the holder's own accounts."""
    return [
        word for word in _distinctive_words(_INTERNAL_ACCOUNT_SOURCE_WORDS.sub(" ", words).split())
        if word not in _OWN_ACCOUNT_PRODUCT_WORDS and not _is_reference_token(word)
    ]


_ENTITY_MONTHS = {
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT", "NOV",
    "DEC", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
    "OCTOBER", "NOVEMBER", "DECEMBER",
}
_MASKED_TOKEN = re.compile(r"X{2,}[A-Z0-9]*")
#: A wire's beneficiary starts after BNF (Wells Fargo /Bnf=, Bank of America BNF:), else after the account
#: label of Chase's 'Wire Transfer Via: <bank> A/C: <beneficiary>'.
_WIRE_BENEFICIARY_PATTERNS = (
    re.compile(r"\bBNF(?: FFC)?\b"),
    re.compile(r"\bWIRE TRANSFER VIA\b.*?\bA C\b"),
)
#: The receiver fields. The account holder's own name prints there (Bank of America INDN, Chase IND NAME). The one
#: tuple's field labels, as _CREDIT_RECEIVER_FIELD reads them.
_RECEIVER_NAME_FIELD = re.compile(rf"\b(?:{_RECEIVER_FIELD_LABELS})\b")
#: Bill-payment prefix words a bank prints before the payee. The leading payee words start after them.
_LEADING_PREFIX_WORDS = frozenset({
    "BILL", "BILLS", "PRE", "AUTHORIZED", "AUTHORISED", "RECURRING", "RECUR", "INTERNET", "BANKING", "PAIEMENT",
    "FACTURE", "BM", "CABLE", "TV", "TELEPHONE", "PCS", "SVC", "ON",
})


def _is_reference_token(token: str) -> bool:
    return (
        any(character.isdigit() for character in token)
        or _MASKED_TOKEN.fullmatch(token) is not None
        or token in _ENTITY_MONTHS
    )


def _payee_region(text: str) -> str:
    """D11: the payee part of a normalized row: originator-name labels removed, cut at the first ACH field segment
    (so never an ID, INDN, IND NAME, CO ID or TRACE field). `_unknown_payee_tokens` reads its words."""
    text = _ENTITY_NAME_LABELS.sub(" ", text)
    segment = _ACH_FIELD_SEGMENT.search(text)
    return text[: segment.start()] if segment is not None else text


def _row_before_receiver(text: str) -> str:
    """The normalized row up to its first receiver field, so the account holder's own name never decides a D6 skip.
    The entry-description fields stay (DES:FACTS, DES:CHILD SUPP). A row with no receiver field is read whole: a
    label-less format prints the holder unmarked, which the payee-word readers cover instead."""
    return _RECEIVER_NAME_FIELD.split(text, 1)[0]


def _leading_payee_words(text: str) -> str:
    """The payee's leading words: the payee region after channel words, bill-payment prefix words and any leading
    reference, up to the next reference token. A word printed after the payee's own name (a receiver in a
    label-less format) is never a leading word."""
    words: list[str] = []
    for token in _payee_region(text).split():
        if not words:
            if token in _ENTITY_NOISE or token in _LEADING_PREFIX_WORDS or _is_reference_token(token):
                continue
        elif _is_reference_token(token):
            break
        words.append(token)
    return " ".join(words)


def _originator_segment(text: str) -> str:
    """D11's reading of the originator without the four-word cap and keeping channel words: the payee region up
    to the first reference token after a name word. Provider and benefit-administrator names are read here, never
    in a receiver field."""
    words: list[str] = []
    started = False
    for token in _payee_region(text).split():
        if _is_reference_token(token):
            if started:
                break
            continue
        words.append(token)
        started = started or (token not in _ENTITY_NOISE and len(token) > 1)
    return " ".join(words)


def _wire_beneficiary(text: str) -> str | None:
    """The text after a wire's beneficiary label, or None for a row that is no such wire."""
    for pattern in _WIRE_BENEFICIARY_PATTERNS:
        found = pattern.search(text)
        if found is not None:
            return text[found.end():]
    return None

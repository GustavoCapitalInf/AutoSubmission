"""Payer region, entry fields, ACH and wire payer, channel gate, numbered companies."""
from __future__ import annotations

import re

from analysis.description_text import _TRANSFER_WORDING
from analysis.descriptor.lexical import (
    _before_receiver,
    _is_payer_word,
    _is_reference_token,
    _leading_name_words,
    _payee_region,
    _skip_numbered_leading_date,
    _strip_revenue_template,
    bank_by_form,
    originator_address,
)
from analysis.descriptor.rails import _is_wire_row, _loose_wire_label
from analysis.descriptor.words import (
    _ACH_ORIGINATOR_FIELD,
    _AMEX_ACH_CREDIT,
    _BOFA_ENTRY_FIELD,
    _CASH_BRANCH_ATM_FORM,
    _CHASE_ENTRY_FIELD,
    _CHECK_DEPOSIT_FORM,
    _COMPANY_FORM,
    _CONSUMER_P2P_RAIL,
    _CONTRA_BANK_FIELD,
    _ELECTRONIC_PAYMENT_FORM,
    _MEMO_ENTRY_FIELD,
    _NUMBERED_COMPANY_REGION,
    _NUMBERED_PROVINCE_START,
    _PROVINCE_NOT_A_NAME_START,
    _PUSH_RAIL,
    _RELAY_ORIGINATOR_LABEL,
    _SANTANDER_WIRE,
    _SENDER_END,
    _WIRE_FIELD_END,
    _WIRE_ORIGINATOR_LABEL,
    _WIRE_SENDER_AFTER_LABEL,
    _WIRE_SENDER_AFTER_LABEL_END,
)


_WIRE_ENTRY_FIELD = re.compile(
    r"\b(?:OBI|RMR|PMT DET|RFB|REF)\b (.*?)(?=\b(?:BNF|NBNF|BBI|OBI|SRF|TRN|IMAD|ACCT|SND BK|RFB|ORIG|B O|ORG)\b|$)"
)
_NUMBERED_COMPANY_TEMPLATE = re.compile(
    rf"^(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT) \d{{6,10}}"
    rf"(?:$| {_PROVINCE_NOT_A_NAME_START})"
)
#: A reference of six to fifteen digits printed in the same slot, before the payer's name: no part of the payer
#: region, unless a province or territory (or a cut of one), Quebec's form or BMO's code tail follows it (a numbered
#: company's number, or BMO's merchant reference before its code, which names no payer). Only when that word is no
#: name's first word (_PROVINCE_NOT_A_NAME_START).
_REFERENCE_BEFORE_PAYER = re.compile(
    r"^(?:DIRECT DEPOSIT|ACC(?:OUN)?TS? PAYABLE(?: PMT)?|MISC PAYMENT|BILL PAYMENT) (?P<reference>\d{6,15}) (?=\S)"
)
_KEEPS_ITS_NUMBER = re.compile(_PROVINCE_NOT_A_NAME_START)
#: §5.2: RBC's `ACCOUNT PAYABLE PMT` and Scotiabank's `ACCOUNTS PAYABLE` label printed before a numbered company's
#: number: removed before the payer region is read, so `ACCOUNT PAYABLE PMT 1234567 ONTARIO` reads the region
#: `1234567 ONTARIO`, as `MISC PAYMENT 1234567 ONTARIO` does, and the holder test reads the holder's own number. A
#: word-named payer after a reference keeps its region (`ACCOUNTS PAYABLE <reference> NORTHWIND SUPPLY INC`).
_AP_LABEL_BEFORE_NUMBERED = re.compile(rf"^ACC(?:OUN)?TS? PAYABLE(?: PMT)? (?=\d{{6,10}} {_PROVINCE_NOT_A_NAME_START})")


def _is_transfer_or_p2p_row(text: str) -> bool:
    """§8.4: a person-to-person rail, or transfer wording, on a row that is no wire. The transfer wording a credit's
    row prints outside a company-formed ACH originator's own name (credit_transfer_wording)."""
    row = _before_receiver(text)
    return _CONSUMER_P2P_RAIL.search(row) is not None or _PUSH_RAIL.search(row) is not None or (
        credit_transfer_wording(row) is not None
    )


#: The ACH originator fields that open an originator's own name for credit_transfer_wording: Chase's labels, or Bank of
#: America's DES with a field of its layout after its entry (ID, INDN, CO ID, IND NAME, IND ID or an ACH class code, the
#: entry five words at most, as _BOFA_ENTRY_FIELD ends it). A DES with none of them after it is no field: a town's word
#: ('TRANSFER FROM CONTOSO LLC DES MOINES IA', 'XFER CONTOSO LLC DES PLAINES IL'), a French word or a wire's cut text. A
#: town's DES never opens the field, whatever field word follows the town ('TRANSFER CONTOSO LLC DES MOINES IA TEL <n>',
#: '... DES PLAINES IL ID <n>'): Des Moines, Des Plaines, Des Peres, Des Allemands, Des Lacs (Des Arc is left out: ARC is
#: also an ACH class code).
_ORIGINATOR_NAME_FIELD = re.compile(
    r"\b(?:CO ENTRY DESCR|ORIG CO NAME)\b"
    r"|\bDES(?! (?:MOINES|PLAINES|PERES|ALLEMANDS|LACS)\b)(?: \S+){0,5}? "
    r"(?:ID|INDN|CO ID|IND NAME|IND ID|CCD|CTX|PPD|WEB|IAT|TEL|POP|BOC|ARC|RCK|CIE)\b"
)
#: A transfer's phrase words ('TRANSFER FROM CONTOSO LLC', 'XFER FRM ...', 'TRANSFER FR ...', 'TRF TO ...', 'TRANSFER
#: BETWEEN ...'): a name that prints one is a transfer's text, never a company's own name.
_TRANSFER_PHRASE_WORD = re.compile(r"\b(?:FROM|FRM|FR|TO|BETWEEN)\b")


def credit_transfer_wording(row: str) -> re.Match[str] | None:
    """§8.2, §8.6: the transfer wording a credit's row prints (_TRANSFER_WORDING), a company-formed ACH originator's own
    name aside. On a row that prints an ACH originator field (_ACH_ORIGINATOR_FIELD: DES, CO ENTRY DESCR, ORIG CO NAME)
    whose originator name (_ach_payer_region) prints transfer wording and, that wording removed, a company form
    (_COMPANY_FORM: 'CONTOSO TRF LLC', 'TRF INDUSTRIES INC', 'CONTOSO TRANSFER INC'), the name's transfer tokens are
    blanked inside the name's span only (the row's length kept, so the match's positions are the row's own) before the
    row is read: the entry field's wording ('DES:TRANSFER', 'CO ENTRY DESCR:BANK XFER') is still read, and a name with
    no company form ('SAMPLE BANK XFER', 'TRANSFER AND STORAGE CO', 'ONLINE TRANSFER') keeps its transfer reading. Any
    other row is read as _TRANSFER_WORDING reads it. The credit's readers use it (the channel, the transfer row, the
    bare row, the payer region); a debit's reader, the token filters and Q6's entry-field refusal keep
    _TRANSFER_WORDING.

    The field is Chase's label or Bank of America's DES with its layout after the entry (_ORIGINATOR_NAME_FIELD), never a
    town's DES, and a name printing a transfer's phrase word (_TRANSFER_PHRASE_WORD: 'TRANSFER FROM CONTOSO LLC') is no
    company's own name: such a named transfer keeps its transfer reading (Q4, T13)."""
    found = _TRANSFER_WORDING.search(row)
    if found is None or _ORIGINATOR_NAME_FIELD.search(row) is None:
        return found
    name = _ach_payer_region(row)
    if not name or _TRANSFER_WORDING.search(name) is None or _TRANSFER_PHRASE_WORD.search(name) is not None:
        return found
    if _COMPANY_FORM.search(" ".join(_TRANSFER_WORDING.sub(" ", name).split())) is None:
        return found
    span = re.search(r"(?<!\S)" + re.escape(name) + r"(?!\S)", row)
    if span is None:
        return found
    blanked = _TRANSFER_WORDING.sub(lambda token: " " * len(token.group(0)), name)
    return _TRANSFER_WORDING.search(row[: span.start()] + blanked + row[span.end():])


def _wire_payer_region(text: str, start: int = 0) -> str:
    """§5.2: a wire's originator, after its label, up to the next wire field; on Santander's layout, the words after
    the account number (the words after WIRE IN FROM are the sending bank). The label is searched from `start` (a
    loose-wire row's own label, _loose_wire_label; 0 on an incoming-wire row)."""
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        return _leading_name_words(santander.group("originator").strip())
    found = _WIRE_ORIGINATOR_LABEL.search(text, start)
    if found is None:
        return _wire_sender_after_label(text)
    region, customer = _labelled_originator(text, found)
    return _leading_name_words(customer) if customer else region


def _labelled_originator(text: str, found: re.Match[str]) -> tuple[str, str]:
    """§5.2: a labelled wire originator's region, and the relaying bank's customer it names after a relay label
    ('' when it names none, relayed_customer_text)."""
    # A SWIFT 50F line number is dropped by the normalizer, where its slash still shows.
    rest = text[found.end():]
    end = _WIRE_FIELD_END.search(rest)
    region = _leading_name_words(rest[: end.start()] if end is not None else rest)
    after, city_state_end = originator_address(text, region)
    return region, relayed_customer_text(region, rest, after=after, city_state_end=city_state_end) or ""


def wire_relayed_customer(text: str) -> str:
    """The relaying bank's customer a labelled wire's payer region reads, or '' (no label, Santander's layout, or
    no relay)."""
    if _SANTANDER_WIRE.match(text) is not None:
        return ""
    found = _WIRE_ORIGINATOR_LABEL.search(text)
    return _labelled_originator(text, found)[1] if found is not None else ""


_RELAY_CUSTOMER_END = re.compile(
    _WIRE_FIELD_END.pattern + r"|\b(?:OGB|ORIGINATING BANK|OCMT|CHGS|INS|BBK|INT BK|INTERMEDIARY)\b"
)


def relayed_customer_text(region: str, rest: str, *, after: str = "", city_state_end: bool = False) -> str:
    """§8.5: when a wire's originator (`region`, read from `rest`, the text after the originator label) reads as a
    bank, and a relay label after it names the ultimate originator, that customer's text up to its end
    (_RELAY_CUSTOMER_END), after its account number and any SWIFT line number: the bank only relays, so the customer is
    the sender, read normally. '' when the originator is no bank by form (bank_by_form, read with the region's address
    context, A3-G re-review 2), or no relay label names a customer (a bank sending on its own behalf). A numbered
    company is a named payer (§5.2), so a relayed name that starts as one once its account number is dropped
    (_NUMBERED_PROVINCE_START: '1234567 B C LTD', whose single letters and legal form are no payer words) is the
    customer too."""
    if not region or not bank_by_form(region, after, city_state_end=city_state_end):
        return ""
    for label in _RELAY_ORIGINATOR_LABEL.finditer(rest):
        if label.start() == 0:
            continue
        after = rest[label.end():]
        end = _RELAY_CUSTOMER_END.search(after)
        tokens = (after[: end.start()] if end is not None else after).split()
        while tokens and _is_reference_token(tokens[0]) and _NUMBERED_PROVINCE_START.match(" ".join(tokens)) is None:
            tokens.pop(0)
        name = " ".join(tokens)
        if _NUMBERED_PROVINCE_START.match(name) is not None or any(
            _is_payer_word(token) and not _is_reference_token(token) and token not in _WIRE_LABEL_WORDS
            for token in _leading_name_words(name).split()
        ):
            return name
    return ""


#: A3: the words of the label layouts, never a sender's name ('WIRE TRANSFER DEPOSIT WIRE REF ...'), and a legal form
#: or an article, which alone names nobody (as the person-to-person reader holds: 'WIRE TRANSFER INCOMING 1ABC LLC',
#: whose name the reference reading drops, stays a wire with no sender).
_WIRE_LABEL_WORDS = frozenset({
    "INCOMING", "WIRE", "PAYMENT", "TRANSFER", "DEPOSIT", "CREDIT", "IN", "FROM",
    "LLC", "INC", "INCORPORATED", "CORP", "CORPORATION", "COMPANY", "CO", "LTD", "LIMITED", "LP", "LLP", "PLLC", "ULC",
    "PLC", "THE", "OF", "AND",
})


def _wire_sender_after_label(text: str) -> str:
    """A3: the sender a wire prints right after its label (_WIRE_SENDER_AFTER_LABEL), read as the originator is: up to
    the next wire field, NOTPROVIDED or WIRE PAYMENT, and to the first reference token after a name word
    (_leading_name_words). A reference printed before the sender is no part of it, except a numbered company's number
    before its province ('CA 1234567 ONTARIO INC', §5.2). '' when no payer word is left."""
    found = _WIRE_SENDER_AFTER_LABEL.match(text)
    if found is None:
        return ""
    rest = text[found.end():]
    end = _WIRE_SENDER_AFTER_LABEL_END.search(rest)
    tokens = (rest[: end.start()] if end is not None else rest).split()
    while tokens and tokens[0].isdigit() and _NUMBERED_PROVINCE_START.match(" ".join(tokens)) is None:
        tokens.pop(0)
    region = _leading_name_words(" ".join(tokens))
    named = any(
        _is_payer_word(token) and not _is_reference_token(token) and token not in _WIRE_LABEL_WORDS
        for token in region.split()
    )
    return region if named else ""


def _sender_payer_region(text: str) -> str:
    """§5.2: a person-to-person or transfer sender: the words after FROM, up to ON, REF, CONF, MEMO, TRN, ID, FOR,
    NOTE, PMT INFO, PAYMENT INFO, PAYMENT ID (Truist's business-Zelle label, whose PAYMENT is no part of the
    sender) or a reference token. Venmo and Cash App cash-outs print no sender. The sender after the next FROM when
    the first prints Chase's contra-bank label (_CONTRA_BANK_FIELD)."""
    row = _CONTRA_BANK_FIELD.sub(" ", _before_receiver(text), count=1)
    found = re.search(r"\bFROM\b ?", row)
    if found is None:
        return ""
    rest = row[found.end():]
    end = _SENDER_END.search(rest)
    return _leading_name_words(rest[: end.start()] if end is not None else rest)


#: PNC prints 'CORPORATE ACH <entry> <reference(s)> <payer> <reference>': its entry description (ten characters at
#: most, one or two words) and a reference before the payer's name. A row whose words after the label are no such
#: entry and reference ('CORPORATE ACH PAYROLL <payer> <reference>') keeps its reading.
_PNC_CORPORATE_ACH = "CORPORATE ACH "
_PNC_ENTRY_WIDTH = 10


def pnc_corporate_ach(row: str) -> tuple[str, str] | None:
    """PNC's CORPORATE ACH layout read as (entry, the text from the payer's name on), or None."""
    if not row.startswith(_PNC_CORPORATE_ACH):
        return None
    tokens = row[len(_PNC_CORPORATE_ACH):].split()
    for size in (1, 2):
        entry = tokens[:size]
        if len(entry) < size or len(" ".join(entry)) > _PNC_ENTRY_WIDTH:
            return None
        rest = tokens[size:]
        references = 0
        while references < len(rest) and _is_reference_token(rest[references]):
            references += 1
        if references and references < len(rest):
            return " ".join(entry), " ".join(rest[references:])
    return None


#: Navy Federal's 'DEPOSIT ACH PAID FROM <digits> <payer>' and Symitar's 'EXTERNAL DEPOSIT <digits> <payer>' print
#: a block of four or more digits before the payer's name: the payer is read past it (a numbered company's number
#: before its province is kept).
_DIGIT_BLOCK_BEFORE_PAYER = re.compile(r"^(?:DEPOSIT ACH PAID FROM|EXTERNAL DEPOSIT) (?P<reference>\d{4,}) (?=[A-Z])")
#: An ACH originator label printed with no value ('ORIG CO ACH CREDIT', a Chase export that keeps only the label) is
#: no payer, and CO ENTRY DESCR starts the entry field ('CO ENTRY' is no payer either). CO alone stays a possible name
#: word (_EMPTY_ACH_FIELD_LABELS reads label sequences only).
_BARE_ORIG_CO_LABEL = re.compile(r"\bORIG CO\b(?! NAME\b)")
_CO_ENTRY_DESCR_LABEL = re.compile(r"\bCO ENTRY DESCR\b")
_EMPTY_ACH_FIELD_LABELS = re.compile(r"\b(?:ORIG CO NAME|ORIG CO|CO ENTRY DESCR|ORIG ID|IND NAME|IND ID)\b")


def _without_reference_before_payer(row: str) -> str:
    """The row without the reference printed before the payer's name (after DIRECT DEPOSIT, ACCOUNTS PAYABLE, MISC
    PAYMENT or BILL PAYMENT, unless a province, Quebec's form or BMO's code tail follows it: _REFERENCE_BEFORE_PAYER,
    _KEEPS_ITS_NUMBER), and without Navy Federal's or Symitar's digit block (_DIGIT_BLOCK_BEFORE_PAYER)."""
    found = _REFERENCE_BEFORE_PAYER.match(row)
    if found is not None and _KEEPS_ITS_NUMBER.match(row, found.end()) is None:
        return row[: found.start("reference")] + row[found.end():]
    found = _DIGIT_BLOCK_BEFORE_PAYER.match(row)
    if found is not None and _NUMBERED_PROVINCE_START.match(row[found.start("reference"):]) is None:
        return row[: found.start("reference")] + row[found.end():]
    return row


def _ach_payer_region(text: str) -> str:
    """§5.2: an ACH or EFT payer: the row before its receiver fields, template prefixes removed, originator labels
    removed, cut at the first ACH field, up to the first reference token after a name word. PNC's payer after its
    entry and reference (pnc_corporate_ach); no reference printed before the payer's name
    (_without_reference_before_payer); an empty ORIG CO label removed and CO ENTRY DESCR read as the entry field it
    starts. RBC's and Scotiabank's accounts-payable label before a numbered company's number removed
    (_AP_LABEL_BEFORE_NUMBERED), so the region keeps the number."""
    row = _before_receiver(text)
    pnc = pnc_corporate_ach(row)
    if pnc is not None:
        return _leading_name_words(_payee_region(pnc[1]))
    row = _CO_ENTRY_DESCR_LABEL.sub("DESCR", _BARE_ORIG_CO_LABEL.sub("", row)).strip()
    row = _AP_LABEL_BEFORE_NUMBERED.sub("", row, count=1)
    return _leading_name_words(_payee_region(_strip_revenue_template(_without_reference_before_payer(row))))


def _amex_ach_credit(text: str) -> bool:
    """American Express's incoming-ACH template (_AMEX_ACH_CREDIT) on a row that prints no
    person-to-person or push rail."""
    if _AMEX_ACH_CREDIT.match(text) is None:
        return False
    row = _before_receiver(text)
    return _CONSUMER_P2P_RAIL.search(row) is None and _PUSH_RAIL.search(row) is None


def payer_label_layout(text: str) -> bool:
    """The row prints a layout whose payer the payer region reads past a bank's label, entry, reference or code, or
    where only an empty label prints: Chase's contra-bank field (_CONTRA_BANK_FIELD), PNC's CORPORATE ACH entry and
    reference (pnc_corporate_ach), an empty ORIG CO label or a row that starts with CO ENTRY DESCR, a reference
    before the payer or Navy Federal's or Symitar's digit block (_without_reference_before_payer) and
    American Express's incoming-ACH template (_amex_ach_credit)."""
    row = _before_receiver(text)
    return bool(
        _CONTRA_BANK_FIELD.search(row)
        or pnc_corporate_ach(row) is not None
        or _BARE_ORIG_CO_LABEL.search(row)
        or row.startswith("CO ENTRY DESCR")
        or _without_reference_before_payer(row) != row
        or _amex_ach_credit(text)
    )


def _prints_no_payer(text: str) -> bool:
    """§5.2, §6.1: a check, cash, branch, ATM or bare row: a channel that prints no payer."""
    row = _before_receiver(text)
    if _CHECK_DEPOSIT_FORM.search(row):
        return True
    if (
        not _ELECTRONIC_PAYMENT_FORM.search(row)
        and not _CONSUMER_P2P_RAIL.search(row)
        and _CASH_BRANCH_ATM_FORM.search(row)
    ):
        return True
    return _is_bare_row(text)


def _is_bare_row(text: str) -> bool:
    """§8.2: a bare deposit, credit or EFT: once the template prefixes, the generic words, the reference tokens and
    single letters are removed, no payer word remains, and the row prints no transfer wording. No transfer wording
    outside a company-formed ACH originator's own name (credit_transfer_wording)."""
    row = _before_receiver(text)
    if credit_transfer_wording(row):
        return False
    # An ACH field label printed with no value names no payer.
    row = _EMPTY_ACH_FIELD_LABELS.sub(" ", row).strip()
    return not any(_is_payer_word(token) for token in _strip_revenue_template(row).split())


def payer_region(text: str) -> str:
    """§5.2: the payer region of a credit's revenue text, read by its channel: a wire's originator, a
    person-to-person or transfer sender, an ACH or EFT payer, or nothing on a check, cash, branch, ATM or bare row.
    Read before any token is filtered, so a numbered company's leading digits and a legal word are kept. A
    loose-wire row's originator label is read as an incoming wire's (_loose_wire_originator), and American
    Express's incoming-ACH template is read as ACH, its entry's transfer word aside (_amex_ach_credit). A
    loose-wire row is read from its own label, the first after the row's first WIRE word (_loose_wire_label), so a
    label word inside a '<sender> WIRE' row's name never cuts it."""
    if _is_wire_row(text):
        return _wire_payer_region(text)
    loose = _loose_wire_label(text)
    if loose is not None:
        # _before_receiver returns a prefix of the text, so the label's offset is the text's own.
        return _wire_payer_region(text, loose.start())
    if _is_transfer_or_p2p_row(text) and not _amex_ach_credit(text):
        sender = _sender_payer_region(text)
        row = _before_receiver(text)
        # A transfer-worded row that prints an ACH originator field and no FROM sender names its payer the ACH way
        # ('CONTOSO BAKERY LLC DES:TRANSFER'), so the holder test and the counter-debit hold read it.
        if (
            not sender
            and _ACH_ORIGINATOR_FIELD.search(row)
            and not _CONSUMER_P2P_RAIL.search(row)
            and not _PUSH_RAIL.search(row)
        ):
            return _ach_payer_region(text)
        return sender
    if _prints_no_payer(text):
        return ""
    return _ach_payer_region(text)


def entry_fields(text: str) -> str:
    """§5.2: the words the payer prints about the payment: Bank of America's DES field, Chase's CO ENTRY DESCR field,
    a wire's OBI, RMR, PMT DET, RFB and REF text, a transfer's memo. Empty when the layout has none (its entry words
    sit inside the payer region, which the holds read too)."""
    row = _before_receiver(text)
    fields = []
    for pattern in (_BOFA_ENTRY_FIELD, _CHASE_ENTRY_FIELD):
        found = pattern.search(row)
        if found is not None:
            fields.append(found.group(1).strip())
    # PNC's entry description, printed before its reference and the payer (pnc_corporate_ach).
    pnc = pnc_corporate_ach(row)
    if pnc is not None:
        fields.append(pnc[0])
    if _is_wire_row(text):
        fields.extend(found.group(1).strip() for found in _WIRE_ENTRY_FIELD.finditer(text))
    elif _is_transfer_or_p2p_row(text):
        fields.extend(found.group(1).strip() for found in _MEMO_ENTRY_FIELD.finditer(row))
    return " ".join(field for field in fields if field)


def numbered_company(text: str, region: str | None = None) -> bool:
    """§5.2: the payer is a Canadian numbered company: a template prefix followed by six or more digits, or a payer
    region that begins with six or more digits and then a province, territory, CANADA or a cut of one, or up to four
    words and a legal form, or with Quebec's form: four digits, a hyphen and four digits, then QUEBEC, a cut of it or
    QC (S4.2 round 4; fix round 5: Quebec's words only, '1234-5678 QUEBEC INC'). Both read past a leading date."""
    if _NUMBERED_COMPANY_TEMPLATE.search(_skip_numbered_leading_date(_before_receiver(text))):
        return True
    region = payer_region(text) if region is None else region
    return _NUMBERED_COMPANY_REGION.search(_skip_numbered_leading_date(region)) is not None


def channel_gate(text: str) -> str | None:
    """5.5 (§6.1 step 9b), read on a credit's revenue text: 'closed' when a consumer person-to-person rail, a
    check-deposit form, a cash, branch or ATM form, or no payer word at all is printed (no step verifies it);
    'push' for a real-time or push rail (only the operating registry may verify it); None otherwise."""
    row = _before_receiver(text)
    if _CONSUMER_P2P_RAIL.search(row):
        return "closed"
    if _prints_no_payer(text) and not _is_wire_row(text):
        return "closed"
    if _PUSH_RAIL.search(row):
        return "push"
    return None

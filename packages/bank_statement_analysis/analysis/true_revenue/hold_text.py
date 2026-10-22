"""The text §8.1 holds read: hold text, payer-name field, layout entry, title purpose."""
from __future__ import annotations

import re

from analysis.descriptor.credit_words import _PUBLIC_PAYER_NAME, _PUBLIC_PAYER_TEMPLATE
from analysis.descriptor.lexical import _before_receiver
from analysis.descriptor.payer import _is_transfer_or_p2p_row, _sender_payer_region
from analysis.descriptor.rails import _is_wire_row
from analysis.descriptor.words import (
    _ACH_ORIGINATOR_FIELD,
    _BOFA_ENTRY_FIELD,
    _CHASE_ENTRY_FIELD,
    _MEMO_ENTRY_FIELD,
    _SANTANDER_WIRE,
)
from analysis.true_revenue.channel import _channel
from analysis.true_revenue.words import (
    _DEPOSIT_CHANNELS,
    _DISBURSEMENT_ACCOUNT,
    _DISBURSEMENT_KEEP,
    _DISBURSEMENT_WORD,
    _ENTRY_COMPANY_FORM,
    _HOLD_POSTING_LABELS,
    _STREET_NAME,
    _STREET_SUFFIXES,
)


_NUMBERED_STREET_NAME = re.compile(
    rf"(?<![A-Z0-9])(?P<number>\d+[A-Z]?(?: [A-Z]+)?) [A-Z]+(?= (?:{_STREET_SUFFIXES})\b)"
)
#: §8.1 non_sale_purpose: DISTRIB... and STOCK are a business's name words (a distributor, a goods stock) more often
#: than owner money. They are not read inside the payer's name field (an ACH originator, a wire's sender, a transfer's
#: sender after FROM), inside a name that a company form ends ('<NAME> DISTRIBUTION INC', after a name word, with at
#: most one more name word and no connector word before the form: never 'DISTRIBUTION FROM <NAME> LLC'), in a
#: joint-stock company's or bank's legal form ('JOINT STOCK COMPANY', 'JOINT STOCK COMMERCIAL BANK'), or, STOCK, on a
#: row that cites an invoice ('INV <n> STOCK AND FREIGHT': goods). A purpose or entry field still holds them
#: ('DES:DISTRIB', 'QUARTERLY PARTNER DISTRIBUTION').
_NAME_NON_SALE_WORDS = re.compile(r"(?<![A-Z])(?:DISTRIB(?!UTORS?\b|UTING\b)\w*|STOCK\b)")
_JOINT_STOCK = re.compile(r"(?<![A-Z])JOINT STOCK\b")
#: The word before DISTRIB... or STOCK must be a name word (letters only, none of _NOT_A_NAME_WORD_BEFORE: a period, a
#: member's or owner's word, a memo's or a field's label, a connector, a company form), so a purpose before a formed
#: name ('QUARTERLY DISTRIBUTION <NAME> LLC', 'MEMO DISTRIBUTION <NAME> LLC', 'PMT DET <n> MEMBER DISTRIBUTION <NAME>
#: INC') still holds.
_FORMED_NAME_NON_SALE = re.compile(
    r"(?<![A-Z0-9])(?P<before>[A-Z0-9]+) (?:DISTRIB(?!UTORS?\b|UTING\b)\w*|STOCK)"
    r"(?= (?:(?!(?:FROM|TO|OF|FOR|BY|PER|AND|THE)\b)[A-Z]+ )?(?:LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO"
    r"|COMPANY|LTD|LIMITED|LP|LLP|PLLC|PLC|GMBH)\b)"
)
_NOT_A_NAME_WORD_BEFORE = frozenset({
    "QUARTERLY", "MONTHLY", "ANNUAL", "ANNUALLY", "YEARLY", "WEEKLY", "FINAL", "INTERIM", "SPECIAL", "MEMBER", "MEMBERS",
    "PARTNER", "PARTNERS", "OWNER", "OWNERS", "SHAREHOLDER", "SHAREHOLDERS", "PROFIT", "PROFITS", "CAPITAL", "EQUITY",
    "CASH", "INCOME", "DIVIDEND", "TRUST", "ESTATE", "MEMO", "OBI", "DET", "REF", "RE", "INFO", "NOTE", "DESC", "DES",
    "RMK", "FOR", "OF", "TO", "FROM", "BY", "PER", "AND", "THE", "LLC", "INC", "CORP", "LP", "LLP", "LTD",
    # A tax, year-end, partnership, half-year, preferred, estimated or retained distribution, and the months (the
    # classifier's _ENTITY_MONTHS, copied: the classifier imports this module).
    "TAX", "TAXES", "PARTNERSHIP", "YEAR", "END", "YEAREND", "YE", "SEMIANNUAL", "BIANNUAL", "PREFERRED", "ESTIMATED",
    "RETAINED",
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "SEPT", "OCT", "NOV", "DEC", "JANUARY", "FEBRUARY",
    "MARCH", "APRIL", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
    # An earnings, liquidating or pro-rata distribution.
    "EARNINGS", "EARNING", "LIQUIDATING", "LIQUIDATION", "PRORATA",
})
#: A period's code before DISTRIB... or STOCK is no name word ('Q4 DISTRIBUTION', 'K1', 'FY2054', '2054Q4', '4TH'),
#: nor a reference (a word of three digits or more, 'AB1234'), while a name word that holds a letter and one or two
#: digits is one ('A1 DISTRIBUTION LLC', 'H2O DISTRIBUTION INC'). Nor a month and year, or a day and month, glued
#: ('JAN54', 'SEPT54', '15JAN', '1JAN54').
_PERIOD_MONTHS = r"(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEPT?|OCT|NOV|DEC)"
_PERIOD_CODE = re.compile(
    r"Q[1-4]|[1-4]Q|H[12]|K1|FY\d*|\d{2,4}Q[1-4]|Q[1-4]\d{2,4}|\d+(?:ST|ND|RD|TH)"
    rf"|{_PERIOD_MONTHS}\d{{2,4}}|\d{{1,4}}{_PERIOD_MONTHS}(?:\d{{2,4}})?"
)
_NAME_WORD_MAX_DIGITS = 2
_STOCK_WORD = re.compile(r"(?<![A-Z])STOCK\b")
_INVOICE_WORD = re.compile(r"(?<![A-Z])(?:INVOICES?|INV)\b|(?<![A-Z])INV ?\d")
#: §8.1: a wire's purpose fields, each up to the next wire field: OBI, RMR, PMT DET, RFB, and a URI label wherever it
#: prints (Chase prints its URI inside OBI, a book transfer inside REF, a line wrap may split it: 'U RI'). A REF field
#: is never read: on the Fedwire layout it is the sender's bank reference ('REF COMM BANK NYC'), and Bank of America's
#: SERVICE REF is its own reference; Santander's REF is its purpose (_title_purpose_text). ORIG FEE is purpose
#: wording, never the start of an originator field.
_WIRE_PURPOSE_FIELD = re.compile(
    r"\b(?:OBI|RMR|PMT DET|RFB|U ?R ?I)\b (.*?)"
    r"(?=\b(?:BNF|NBNF|BBI|OBI|SRF|TRN|IMAD|ACCT|SND BK|RFB|RMR|PMT DET|REF|ORIG(?! FEE\b)|B O|ORG)\b|$)"
)


def _public_named(region: str) -> bool:
    """§8.1: the payer region matches a §7.6 payer pattern or the payer-name veto (a public payer of any kind)."""
    if not region:
        return False
    name = _PUBLIC_PAYER_TEMPLATE.sub("", region, count=1)
    return _PUBLIC_PAYER_NAME.match(name) is not None or bool(
        re.search(r"(?<![A-Z])(?:DEPT OF REVENUE|DEPARTMENT OF REVENUE|TAXATION|COMPTROLLER|TREASURER|DEPT OF LABOR"
                  r"|UNEMPLOYMENT|WORKFORCE)\b", name)
    )


def _hold_text(text: str) -> str:
    """§8.1: the row before its receiver fields with the posting labels removed."""
    return _HOLD_POSTING_LABELS.sub(" ", _before_receiver(text))


def _prints_payer_name_field(text: str) -> bool:
    """§8.1, T4: the payer region is a payer's name field: a wire's sender, an ACH originator (the row prints DES, CO
    ENTRY DESCR or ORIG CO NAME) or a transfer's sender after FROM. An unlabelled row's words ('ACHCRED 12345678') are
    no name field."""
    if _is_wire_row(text):
        return True
    row = _before_receiver(text)
    if _ACH_ORIGINATOR_FIELD.search(row) is not None:
        return True
    return _is_transfer_or_p2p_row(text) and bool(_sender_payer_region(text))


def _layout_entry(text: str) -> str:
    """§8.6 Q6c, §8.1: the entry field the layout prints, Bank of America's DES and Chase's CO ENTRY DESCR,
    joined; '' on a row that prints none."""
    return " ".join(
        found.group(1)
        for field in (_BOFA_ENTRY_FIELD, _CHASE_ENTRY_FIELD)
        for found in field.finditer(text or "")
    )


def _non_sale_reading(
    text: str, row: str, region: str, *, disbursing: bool = False, bank: str | None = None,
) -> str:
    """§8.1 non_sale_purpose: the words _NON_SALE_PURPOSE reads, the non-sale words only as a purpose: without a
    street's name (after a street number only, _NUMBERED_STREET_NAME: '<n> GRANT AVE'; on a payer-less check, cash,
    branch or ATM deposit, whose location is never a purpose, B7's _STREET_NAME with no number, as _financing_root
    reads that row's location; `bank` is the statement's bank, for _channel), a joint-stock company's or bank's form
    (_JOINT_STOCK), DISTRIB... or STOCK inside a name a company form ends or inside the payer's name field (the payer
    region of a row that prints one, _prints_payer_name_field: 'ORIG CO NAME:<NAME> DISTRIBUTIO'; its name proper only,
    _payer_name_proper), STOCK on a row citing an invoice (_INVOICE_WORD), the payer's own DISBURSEMENT ACCOUNT, and
    (`disbursing`) the disbursement entry of an ordinary payer that repeats in the statement (_recurring_disbursers),
    which no loan, escrow, title or proceeds word stands beside (_DISBURSEMENT_KEEP)."""
    if not region and _channel(text, bank) in _DEPOSIT_CHANNELS:
        row = _STREET_NAME.sub(" ", row)
    else:
        row = _NUMBERED_STREET_NAME.sub(r"\g<number> ", row)
    row = _JOINT_STOCK.sub(" ", row)
    row = _FORMED_NAME_NON_SALE.sub(_spare_a_formed_name_word, row)
    if region and _prints_payer_name_field(text):
        name = _payer_name_proper(text, region)
        named = _NAME_NON_SALE_WORDS.sub(" ", name)
        if named != name:
            row = row.replace(name, named)
    if _INVOICE_WORD.search(row):
        row = _STOCK_WORD.sub(" ", row)
    row = _DISBURSEMENT_ACCOUNT.sub(" ", row)
    if disbursing and _DISBURSEMENT_KEEP.search(row) is None:
        row = _DISBURSEMENT_WORD.sub(" ", row)
    return row


def _payer_name_proper(text: str, region: str) -> str:
    """§8.1 non_sale_purpose: the part of a payer's name field (_prints_payer_name_field) that is the payer's name,
    where the purpose-only spare reads DISTRIB... and STOCK as name words: on a wire's sender (_is_wire_row) or an ACH
    originator field (_ACH_ORIGINATOR_FIELD before the receiver fields), the whole region; on a transfer's or a
    person-to-person sender after FROM, the region up to and including its first company form (_ENTRY_COMPANY_FORM:
    'FROM <NAME> HOLDINGS LLC PROFIT DISTRIBUTION' reads '<NAME> HOLDINGS LLC'), or, with no form, the whole region only
    when the row prints more after it before the receiver fields (a label of _SENDER_END or a reference closes the
    sender: 'FROM <NAME> DISTRIBUTION CONF <n>'). A sender that runs to the row's end with no form (Wealthsimple's
    'TRANSFER IN FROM <sender> <memo>') may hold the payer's memo, so none of it is spared ('')."""
    if _is_wire_row(text):
        return region
    row = _before_receiver(text)
    if _ACH_ORIGINATOR_FIELD.search(row) is not None:
        return region
    form = _ENTRY_COMPANY_FORM.search(region)
    if form is not None:
        return region[: form.end()]
    sender = re.search(r"\bFROM\b", row)
    at = row.find(region, sender.end()) if sender is not None else -1
    return region if at >= 0 and row[at + len(region):].strip() else ""


def _spare_a_formed_name_word(found: re.Match[str]) -> str:
    """§8.1 non_sale_purpose: a _FORMED_NAME_NON_SALE match keeps its word before and drops DISTRIB... or STOCK only
    when that word is a name word (not in _NOT_A_NAME_WORD_BEFORE; holding a letter, at most _NAME_WORD_MAX_DIGITS
    digits and no period's code, _PERIOD_CODE, so 'A1 DISTRIBUTION LLC' is a name and 'Q4 DISTRIBUTION' or 'AB1234
    DISTRIBUTION' is not); otherwise the match is left as printed, so a purpose before a formed name still holds."""
    before = found.group("before")
    if (
        any(character.isalpha() for character in before)
        and sum(character.isdigit() for character in before) <= _NAME_WORD_MAX_DIGITS
        and _PERIOD_CODE.fullmatch(before) is None and before not in _NOT_A_NAME_WORD_BEFORE
    ):
        return before + " "
    return found.group(0)


def _title_purpose_text(text: str) -> str:
    """§8.1: the words a payment prints about its purpose, which the title fee exemption reads: Bank of America's DES
    field, Chase's CO ENTRY DESCR field, a wire's purpose fields (_WIRE_PURPOSE_FIELD: OBI, RMR, PMT DET, RFB and a
    URI label, never a REF field), a transfer's memo. entry_fields reads a wire's REF field too, which on the Fedwire
    layout is the sender's bank reference, never the purpose. On Santander's layout ('ACCT <n> <originator> REF
    <purpose>', _SANTANDER_WIRE) the REF field is the purpose, and is read."""
    row = _before_receiver(text)
    fields = [
        found.group(1) for found in (
            pattern.search(row) for pattern in (_BOFA_ENTRY_FIELD, _CHASE_ENTRY_FIELD)
        ) if found is not None
    ]
    santander = _SANTANDER_WIRE.match(text)
    if santander is not None:
        purpose = re.match(r"\s*\bREF\b(.*)$", text[santander.end():])
        if purpose is not None:
            fields.append(purpose.group(1))
    if _is_wire_row(text):
        fields.extend(found.group(1) for found in _WIRE_PURPOSE_FIELD.finditer(text))
    elif _is_transfer_or_p2p_row(text):
        fields.extend(found.group(1) for found in _MEMO_ENTRY_FIELD.finditer(row))
    return " ".join(field.strip() for field in fields if field.strip())

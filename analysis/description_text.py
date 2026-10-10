"""Normalization of transaction descriptions, shared by the classifier and the payee matcher.

It lives in its own module so that ``analysis.payee_matcher`` can normalize registry aliases at
import time without importing ``analysis.transaction_classifier``, which imports the matcher.
``analysis.transaction_classifier`` re-exports the function under its old import path.
"""
from __future__ import annotations

import re
import unicodedata

#: 5.6 (true revenue spec §5.2, §20; final review I2): the receiver-name labels, where a bank prints the account
#: holder on an incoming ACH row: Bank of America's INDN, Chase's IND NAME, PNC's RECEIVER NAME and its short RECV
#: NAME. Every receiver-field vocabulary of the classifier and the true-revenue pass is built from this one tuple.
RECEIVER_NAME_LABELS: tuple[str, ...] = ("INDN", "IND NAME", "RECEIVER NAME", "RECV NAME")
#: ... and the labels that open a receiver block: the name labels and Chase's IND ID, the receiver's id, printed
#: before its IND NAME (it carries no name, so it is no name label).
RECEIVER_FIELD_LABELS: tuple[str, ...] = (*RECEIVER_NAME_LABELS, "IND ID")

#: 5.5 (true revenue spec §7.11): a street address ends in LN: a token of digits, then one to three alphabetic
#: tokens, then LN ('12 OAK LN'). Such an LN is a lane, never a loan, unless a loan-product word sits among those
#: tokens or LN is followed by a loan-payment word ('1234 COMMERCIAL LN PMT', '000123 AUTO LN DISB' read LOAN).
_STREET_BEFORE_LN = re.compile(r"(?:^| )\d+((?: [A-Z]+){1,3}) $")
#: The loan-product words include the banks' loan abbreviations (S2.1 review finding 2): CML, COML and COMM
#: (commercial), SB and SBA (small business), VEH (vehicle), EIDL and PPP (the SBA's disaster and paycheck loans), LOC
#: (line of credit), CRE (commercial real estate), MORT and MTG (mortgage), EQUIP (equipment). S2.1 re-review (fix round
#: 3), loan abbreviations that keep the LOAN reading 5.4 gave them:
#:   CREDIT: a credit loan or line ('4521 CREDIT LN'), beside LOC and LINE;
#:   PERS: personal, beside PERSONAL;
#:   INST: installment, beside INSTALLMENT and INSTL;
#:   CONS: consumer, beside CONSUMER;
#:   EQUITY: a home-equity loan, beside HOME and HELOC.
#: CR is never one: in an address it is County Road.
_LOAN_PRODUCT_WORDS = frozenset({
    "COMMERCIAL", "COMM", "AUTO", "BUSINESS", "BUS", "TERM", "PERSONAL", "MORTGAGE", "MTG", "EQUIPMENT", "EQUIP",
    "INSTALLMENT", "INSTL", "CONSUMER", "HOME", "HELOC", "STUDENT", "VEHICLE", "SBA", "BRIDGE", "CONSTRUCTION", "LINE",
    "CML", "COML", "SB", "VEH", "EIDL", "PPP", "LOC", "CRE", "MORT",
    "CREDIT", "PERS", "INST", "CONS", "EQUITY",
})
#: Every payment spelling, the ones rewritten below (PAYMT becomes PAYMENT) among them: the LN rule runs before that
#: rewrite, so it reads the printed spelling, and a row normalized twice reads what it read once (S2.1 review).
_LOAN_WORD_AFTER_LN = re.compile(
    r" (?:PMTS?|PYMTS?|PAYMENTS?|PAYMT|PAYMNT|PMNT|PYMNT|REPAYMENTS?|DISB|DISBURSEMENT|ADV|ADVANCE|PROCEEDS|DRAW)\b"
)
_LN_WORD = re.compile(r"\bLN\b")
#: 5.6 (true revenue spec §20, A3-G review): a SWIFT field-50F line number printed with its slash right after a wire's
#: originator label ('ORIG:1/NORTHWIND', 'B/O 1/NORTHWIND'; lines 1 to 3 hold the name, the address and the country
#: and town). It is never part of the name, and the slash is lost below, so the number is dropped here, where the
#: slash still shows. A name that starts with a number ('ORIG:2 NORTHWIND BAKERS LLC') keeps it.
_SWIFT_LINE_NUMBER = re.compile(r"(\b(?:ORIG|ORG|ORIGINATOR|B/O|BY ORDER OF)\b\s*[:=]?\s*)[1-3] ?/ ?(?=[A-Z])")


def _loan_or_lane(match: re.Match[str]) -> str:
    """LN reads LOAN, except where it ends a street address (5.5, §7.11)."""
    text = match.string
    street = _STREET_BEFORE_LN.search(text[: match.start()])
    if (
        street is not None
        and not _LOAN_WORD_AFTER_LN.match(text[match.end():])
        and not set(street.group(1).split()) & _LOAN_PRODUCT_WORDS
    ):
        return "LN"
    return "LOAN"


def _before_ln_rewrite(description: str) -> str:
    """The row as normalize_transaction_description builds it before its LN rule (audit round 3, R3-B07: one reading,
    shared with ln_name_spans)."""
    decomposed = unicodedata.normalize("NFKD", description or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.upper().replace("&", " AND ")
    normalized = _SWIFT_LINE_NUMBER.sub(r"\1", normalized)
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    normalized = re.sub(r"\b1NSURANCE\b|\bINSURANCF\b", "INSURANCE", normalized)
    return re.sub(r"\bF1NANCE\b", "FINANCE", normalized)


def normalize_transaction_description(description: str) -> str:
    """Normalize matching text while retaining the exact source separately."""
    normalized = _LN_WORD.sub(_loan_or_lane, _before_ln_rewrite(description))
    normalized = re.sub(r"\bPAYMT\b", "PAYMENT", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


#: Audit round 3, R3-B07 (R3-46; true revenue spec §7.11): the legal forms that end a company name holding LN, and the
#: most name words between LN and its form.
_LN_NAME_LEGAL_FORMS = (
    ("LLC",), ("L", "L", "C"), ("INC",), ("CORP",), ("CORPORATION",), ("CO",), ("COMPANY",), ("LTD",), ("LIMITED",),
    ("LP",), ("LLP",), ("PLLC",),
)
_LN_NAME_MAX_WORDS = 4
#: R3-46: the ACH or EFT posting label before a name ('ACH CREDIT LN TRUCKING LLC'), whose CREDIT is no loan product.
_ACH_CREDIT = (["ACH", "CREDIT"], ["EFT", "CREDIT"])


def _ln_form_after(tokens: list[str], start: int) -> tuple[int, int] | None:
    """The first legal form (_LN_NAME_LEGAL_FORMS) at or after `start` with only alphabetic name words before it (at
    most _LN_NAME_MAX_WORDS of them): (the index just past the form, the number of name words); None when none
    follows."""
    for words in range(_LN_NAME_MAX_WORDS + 1):
        at = start + words
        if at >= len(tokens) or (words and not tokens[at - 1].isalpha()):
            return None
        for form in _LN_NAME_LEGAL_FORMS:
            if tuple(tokens[at: at + len(form)]) == form:
                return at + len(form), words
    return None


def ln_name_spans(description: str) -> tuple[tuple[str, str], ...]:
    """Audit round 3, R3-B07 (R3-46; true revenue spec §7.11): the company names that hold LN, read on the row as
    normalize_transaction_description builds it before its LN rule (whose output this never changes). An LN is one
    when the LN rule would read it LOAN (no street address before it), no loan-payment word follows it
    (_LOAN_WORD_AFTER_LN), no loan-product word (_LOAN_PRODUCT_WORDS) stands right before it (the CREDIT of an ACH or
    EFT posting label is none: _ACH_CREDIT, 'ACH CREDIT LN TRUCKING LLC'), and it sits inside a name
    that ends in a legal form: LN and one to four alphabetic name words before LLC, L L C, INC, CORP, CORPORATION, CO,
    COMPANY, LTD, LIMITED, LP, LLP or PLLC ('LN TRUCKING LLC'), or a name word before LN and a legal form after it
    ('CONTOSO LN HOLDINGS LLC', 'CONTOSO LN LLC'). None on a row that prints transfer wording (the classifier's
    _TRANSFER_WORDING, read at call time: the classifier imports this module at its own load), where 'FROM LN <name>'
    designates the holder's own loan account. Each name is returned as the normalized row prints it (LN read LOAN) and
    with that LOAN blanked to spaces of its length, for the credit decision's strong non-revenue reading only."""
    from .transaction_classifier import _TRANSFER_WORDING

    before = _before_ln_rewrite(description)
    tokens = before.split()
    if "LN" not in tokens:
        return ()
    normalized = normalize_transaction_description(description)
    if _TRANSFER_WORDING.search(normalized):
        return ()
    printed = normalized.split()
    if len(tokens) != len(printed):
        return ()
    starts = [found.start() for found in re.finditer(r"\S+", before)]
    spans: list[tuple[str, str]] = []
    for found in _LN_WORD.finditer(before):
        if _loan_or_lane(found) != "LOAN" or _LOAN_WORD_AFTER_LN.match(before[found.end():]):
            continue
        index = starts.index(found.start())
        if index and tokens[index - 1] in _LOAN_PRODUCT_WORDS and tokens[max(index - 2, 0): index] not in _ACH_CREDIT:
            continue
        form = _ln_form_after(tokens, index + 1)
        if form is None:
            continue
        end, words = form
        first = index
        if not words:
            # No name word between LN and its form: a name word must stand right before LN.
            if not index or not tokens[index - 1].isalpha() or len(tokens[index - 1]) < 2:
                continue
            first = index - 1
        name = printed[first:end]
        blanked = [" " * len(word) if at == index - first else word for at, word in enumerate(name)]
        spans.append((" ".join(name), " ".join(blanked)))
    return tuple(spans)


def ln_name_word(description: str) -> bool:
    """Audit round 3, R3-B07 (R3-46): the row prints a company name that holds LN (ln_name_spans)."""
    return bool(ln_name_spans(description))

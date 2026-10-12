"""Normalization of transaction descriptions, shared by the classifier and the payee matcher.

It lives in its own module so that ``analysis.payee_matcher`` can normalize registry aliases at
import time without importing ``analysis.transaction_classifier``, which imports the matcher.
``analysis.transaction_classifier`` re-exports the function under its old import path.
"""
from __future__ import annotations

import re
import unicodedata
from functools import cache

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
#: Audit round 4, R4-66 (true revenue spec §7.11; the owner's Q5 of 2026-09-28, standard A5): the second lane arm. A
#: house number right before LN ('77 LN', no alphabetic word between) and, right after it, one to three town words, a
#: state's two-letter code and a ZIP, its four-digit extension optional ('<n> LN <town> <ST> <ZIP>': '77 LN MAPLE GROVE
#: MN 55311 0000', the ZIP's hyphen normalized to a space). Both ends are needed: a loan account's number can print
#: before LN. _LOAN_WORD_AFTER_LN and _LOAN_PRODUCT_WORDS guard this arm as they guard the street arm. The 50 states,
#: DC and PR (a local copy: true_revenue, which holds _US_STATE_TAIL, imports this module).
_HOUSE_NUMBER_BEFORE_LN = re.compile(r"(?:^| )\d+ $")
_US_STATE_CODES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR",
)
_ADDRESS_AFTER_LN = re.compile(
    r" ((?:[A-Z]+ ){1,3})(?:" + "|".join(_US_STATE_CODES) + r") \d{5}(?: \d{4})?(?![0-9])"
)
#: 5.6 (true revenue spec §20, A3-G review): a SWIFT field-50F line number printed with its slash right after a wire's
#: originator label ('ORIG:1/NORTHWIND', 'B/O 1/NORTHWIND'; lines 1 to 3 hold the name, the address and the country
#: and town). It is never part of the name, and the slash is lost below, so the number is dropped here, where the
#: slash still shows. A name that starts with a number ('ORIG:2 NORTHWIND BAKERS LLC') keeps it.
_SWIFT_LINE_NUMBER = re.compile(r"(\b(?:ORIG|ORG|ORIGINATOR|B/O|BY ORDER OF)\b\s*[:=]?\s*)[1-3] ?/ ?(?=[A-Z])")


def _loan_or_lane(match: re.Match[str]) -> str:
    """LN reads LOAN, except where it ends a street address (5.5, §7.11). Audit round 4, R4-66: or where a house number
    stands right before it and a town, a state's code and a ZIP right after it (_HOUSE_NUMBER_BEFORE_LN,
    _ADDRESS_AFTER_LN), with no loan-payment word after LN and no loan-product word among the town words."""
    text = match.string
    street = _STREET_BEFORE_LN.search(text[: match.start()])
    if (
        street is not None
        and not _LOAN_WORD_AFTER_LN.match(text[match.end():])
        and not set(street.group(1).split()) & _LOAN_PRODUCT_WORDS
    ):
        return "LN"
    if _HOUSE_NUMBER_BEFORE_LN.search(text[: match.start()]) is not None:
        address = _ADDRESS_AFTER_LN.match(text, match.end())
        if (
            address is not None
            and not _LOAN_WORD_AFTER_LN.match(text[match.end():])
            and not set(address.group(1).split()) & _LOAN_PRODUCT_WORDS
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
#: Audit round 4, R4-13 (§7.11; the owner's standing rule that loans never become revenue, standard C2): a loan's purpose
#: printed right after LN ('LN DEPOSIT', 'LN CREDIT', 'LN FORGIVENESS', 'LN SERVICING', 'LN REFI', 'LN PAY', 'LN INT',
#: 'LN ESCROW'): the loan's own wording, never a customer company's name. Read by ln_name_spans only, never by
#: _loan_or_lane (_LOAN_WORD_AFTER_LN is unchanged, so the normalizer's output does not move).
_LN_LOAN_PURPOSE_AFTER = re.compile(
    r" (?:DEPOSIT|DEP|CREDIT|FORGIVENESS|FORGIVEN|FORGIVE|SERVICING|SERVICER|SVCG|SVC|SRV|REFI|REFINANCE|PAY|PAYOFF|PYT"
    r"|INT|INTEREST|ESCROW)\b"
)
#: R4-13: the bank-form words that end a bank's name before LN ('<bank> LN ...'; CREDIT UNION read by its UNION), after
#: a trailing N A or NA is dropped.
_LN_BANK_FORM_WORDS = frozenset({"BANK", "BK", "BANCORP", "BANKING", "FSB", "CU", "FCU", "UNION"})
#: R4-13: the listed sending banks' names whose trailing BANK is dropped are names too (CHASE, PNC, TD, CITIZENS,
#: REGIONS, HUNTINGTON, SANTANDER, ALLY), never these, which name no bank alone.
_LN_BANK_NAME_NOT_ALONE = frozenset({"US", "U S", "ROYAL", "NATIONAL"})


@cache
def _ln_bank_names() -> tuple[tuple[str, ...], ...]:
    """R4-13: the listed sending banks' names (the registry's P2P_SENDING_BANK_NAMES, read at call time: the registry
    imports this module at its load) and each such name without its trailing BANK (_LN_BANK_NAME_NOT_ALONE aside), as
    word tuples."""
    from .classification_registry import P2P_SENDING_BANK_NAMES

    names = {tuple(name.split()) for name in P2P_SENDING_BANK_NAMES}
    for name in P2P_SENDING_BANK_NAMES:
        words = name.split()
        if len(words) > 1 and words[-1] == "BANK" and " ".join(words[:-1]) not in _LN_BANK_NAME_NOT_ALONE:
            names.add(tuple(words[:-1]))
    return tuple(sorted(names, key=len, reverse=True))


def _bank_before_ln(tokens: list[str]) -> bool:
    """R4-13: the words before LN end in a bank's name or form (_LN_BANK_FORM_WORDS, _ln_bank_names), once a trailing
    N A or NA is dropped ('JPMORGAN CHASE BANK N A LN ...', 'TRUIST LN ...', 'WOODGROVE BANK LN ...')."""
    before = list(tokens)
    if before[-2:] == ["N", "A"]:
        before = before[:-2]
    elif before[-1:] == ["NA"]:
        before = before[:-1]
    if not before:
        return False
    if before[-1] in _LN_BANK_FORM_WORDS:
        return True
    return any(tuple(before[-len(name):]) == name for name in _ln_bank_names())


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


def ln_name_spans(description: str, *, holder: str | None = None) -> tuple[tuple[str, str], ...]:
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
    with that LOAN blanked to spaces of its length, for the credit decision's strong non-revenue reading only.

    Audit round 4, R4-13 (§7.11; the owner's standing rule that loans never become revenue, standard C2): R3-46's name
    is a customer company's, so an LN is none after a bank's name or form (_bank_before_ln: '<bank> LN ...'), before a
    loan-purpose word (_LN_LOAN_PURPOSE_AFTER: 'LN DEPOSIT', 'LN SERVICING', 'LN REFI', 'LN PAY'), or where the span's
    words other than its LN name the holder (`holder`, holder_reading's name; the classifier's holder_named, read at
    call time): such a row keeps the strong rule's LOAN."""
    from .transaction_classifier import _TRANSFER_WORDING, holder_named

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
        # R4-13: a loan's purpose after LN, or a bank's name or form before it, is the loan's own wording.
        if _LN_LOAN_PURPOSE_AFTER.match(before[found.end():]):
            continue
        index = starts.index(found.start())
        if index and tokens[index - 1] in _LOAN_PRODUCT_WORDS and tokens[max(index - 2, 0): index] not in _ACH_CREDIT:
            continue
        if index and _bank_before_ln(tokens[:index]):
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
        # R4-13: the holder's own name after LN is the holder's loan, never a customer.
        if holder and holder_named(" ".join(word for at, word in enumerate(name) if at != index - first), holder):
            continue
        blanked = [" " * len(word) if at == index - first else word for at, word in enumerate(name)]
        spans.append((" ".join(name), " ".join(blanked)))
    return tuple(spans)


def ln_name_word(description: str, *, holder: str | None = None) -> bool:
    """Audit round 3, R3-B07 (R3-46): the row prints a company name that holds LN (ln_name_spans; audit round 4, R4-13:
    read with the holder's name, `holder`)."""
    return bool(ln_name_spans(description, holder=holder))

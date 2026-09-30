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


def normalize_transaction_description(description: str) -> str:
    """Normalize matching text while retaining the exact source separately."""
    decomposed = unicodedata.normalize("NFKD", description or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.upper().replace("&", " AND ")
    normalized = _SWIFT_LINE_NUMBER.sub(r"\1", normalized)
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    normalized = re.sub(r"\b1NSURANCE\b|\bINSURANCF\b", "INSURANCE", normalized)
    normalized = re.sub(r"\bF1NANCE\b", "FINANCE", normalized)
    normalized = _LN_WORD.sub(_loan_or_lane, normalized)
    normalized = re.sub(r"\bPAYMT\b", "PAYMENT", normalized)
    return re.sub(r"\s+", " ", normalized).strip()

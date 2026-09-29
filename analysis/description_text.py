"""Normalization of transaction descriptions, shared by the classifier and the payee matcher.

It lives in its own module so that ``analysis.payee_matcher`` can normalize registry aliases at
import time without importing ``analysis.transaction_classifier``, which imports the matcher.
``analysis.transaction_classifier`` re-exports the function under its old import path.
"""
from __future__ import annotations

import re
import unicodedata

#: 5.5 (true revenue spec §7.11): a street address ends in LN: a token of digits, then one to three alphabetic
#: tokens, then LN ('12 OAK LN'). Such an LN is a lane, never a loan, unless a loan-product word sits among those
#: tokens or LN is followed by a loan-payment word ('1234 COMMERCIAL LN PMT', '000123 AUTO LN DISB' read LOAN).
_STREET_BEFORE_LN = re.compile(r"(?:^| )\d+((?: [A-Z]+){1,3}) $")
#: The loan-product words include the banks' loan abbreviations (S2.1 review finding 2): CML, COML and COMM
#: (commercial), SB and SBA (small business), VEH (vehicle), EIDL and PPP (the SBA's disaster and paycheck loans), LOC
#: (line of credit), CRE (commercial real estate), MORT and MTG (mortgage), EQUIP (equipment).
_LOAN_PRODUCT_WORDS = frozenset({
    "COMMERCIAL", "COMM", "AUTO", "BUSINESS", "BUS", "TERM", "PERSONAL", "MORTGAGE", "MTG", "EQUIPMENT", "EQUIP",
    "INSTALLMENT", "INSTL", "CONSUMER", "HOME", "HELOC", "STUDENT", "VEHICLE", "SBA", "BRIDGE", "CONSTRUCTION", "LINE",
    "CML", "COML", "SB", "VEH", "EIDL", "PPP", "LOC", "CRE", "MORT",
})
#: Every payment spelling, the ones rewritten below (PAYMT becomes PAYMENT) among them: the LN rule runs before that
#: rewrite, so it reads the printed spelling, and a row normalized twice reads what it read once (S2.1 review).
_LOAN_WORD_AFTER_LN = re.compile(
    r" (?:PMTS?|PYMTS?|PAYMENTS?|PAYMT|PAYMNT|PMNT|PYMNT|REPAYMENTS?|DISB|DISBURSEMENT|ADV|ADVANCE|PROCEEDS|DRAW)\b"
)
_LN_WORD = re.compile(r"\bLN\b")


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
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    normalized = re.sub(r"\b1NSURANCE\b|\bINSURANCF\b", "INSURANCE", normalized)
    normalized = re.sub(r"\bF1NANCE\b", "FINANCE", normalized)
    normalized = _LN_WORD.sub(_loan_or_lane, normalized)
    normalized = re.sub(r"\bPAYMT\b", "PAYMENT", normalized)
    return re.sub(r"\s+", " ", normalized).strip()

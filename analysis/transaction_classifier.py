from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class TransactionClassification:
    original_description: str
    normalized_description: str
    is_pos_purchase: bool = False
    is_pos_credit_or_refund: bool = False
    is_nsf_event: bool = False
    is_atm_withdrawal: bool = False

    @property
    def categories(self) -> tuple[str, ...]:
        categories: list[str] = []
        if self.is_pos_purchase:
            categories.append("pos_purchase")
        if self.is_pos_credit_or_refund:
            categories.append("pos_credit_or_refund")
        if self.is_nsf_event:
            categories.append("nsf_event")
        if self.is_atm_withdrawal:
            categories.append("atm_withdrawal")
        return tuple(categories)


def normalize_transaction_description(description: str) -> str:
    """Normalize text for matching without changing the source description."""
    decomposed = unicodedata.normalize("NFKD", description)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = ascii_text.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    normalized = re.sub(r"\bP0S\b", "POS", normalized)
    normalized = re.sub(r"\bN(?:\s|5)*S(?:\s)*F\b|\bN5F\b", "NSF", normalized)
    normalized = re.sub(r"\bA(?:\s)*[T7](?:\s)*M\b", "ATM", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


_POS_PURCHASE_PATTERNS = (
    re.compile(r"\bPOS\b"),
    re.compile(r"\bPOINT OF SALE\b"),
    re.compile(r"\bCARD PURCHASE\b"),
    re.compile(r"\bDEBIT CARD PURCHASE\b"),
    re.compile(r"\bINTERAC PURCHASE\b"),
    re.compile(r"\bCONTACTLESS PURCHASE\b"),
    re.compile(r"\bTAP PURCHASE\b"),
    re.compile(r"\bVISA DEBIT PURCHASE\b"),
    re.compile(r"\bMASTER ?CARD DEBIT PURCHASE\b"),
    re.compile(r"\bCHECK ?CARD\b"),
    re.compile(r"\bPURCHASE AUTHORI[ZS]ED\b"),
)
_POS_CONTEXT_PATTERNS = _POS_PURCHASE_PATTERNS + (
    re.compile(r"\bPOS CREDIT\b"),
    re.compile(r"\bPURCHASE (?:REFUND|RETURN(?:ED)?)\b"),
)
_POS_CREDIT_PATTERNS = (
    re.compile(r"\bPOS CREDIT\b"),
    re.compile(r"\bCREDIT ADJUSTMENT\b"),
    re.compile(r"\bREFUND\b"),
    re.compile(r"\bREVERS(?:AL|ED)\b"),
    re.compile(r"\bVOID(?:ED)?\b"),
    re.compile(r"\bCANCEL(?:LED|ED|LATION)?\b"),
    re.compile(r"\bPURCHASE RETURN(?:ED)?\b"),
    re.compile(r"\bRETURNED PURCHASE\b"),
    re.compile(r"\bMERCHANT RETURN\b"),
)
_POS_EXCLUSION_PATTERNS = (
    re.compile(r"\bATM\b"),
    re.compile(r"\bCASH WITHDRAWAL\b"),
    re.compile(r"\bCASH ADVANCE\b"),
    re.compile(r"\b(?:E TRANSFER|ETRANSFER|TRANSFER|XFER)\b"),
    re.compile(r"\bACH\b"),
    re.compile(r"\bCHEQUES?\b"),
    re.compile(r"\bCHECKS?\b(?!\s*CARD\b)"),
    re.compile(r"\bBILL PAY(?:MENT)?\b"),
    re.compile(
        r"\b(?:ATM|BANK|MONTHLY|SERVICE|TRANSACTION|OVERDRAFT|NSF|"
        r"RETURN(?:ED)? ITEM|CARD)\s+FEES?\b"
    ),
    re.compile(r"\bFEES?\s+(?:CHARGE|CHARGED|ASSESSED)\b"),
)

_NSF_PATTERNS = (
    re.compile(r"\bNSF\b"),
    re.compile(r"\bNON ?SUFFICIENT FUNDS?\b"),
    re.compile(r"\bINSUFFICIENT FUNDS?\b"),
    re.compile(r"\b(?:RETURNED|RETURN) ITEM FEE\b"),
    re.compile(r"\bRETURNED (?:CHECK|CHEQUE) FEE\b"),
    re.compile(r"\bUNPAID ITEM FEE\b"),
)

_ATM_WITHDRAWAL_PATTERNS = (
    re.compile(r"\bATM\s+(?:CASH\s+)?WITHDRAW(?:AL)?\b"),
    re.compile(r"\bATM\s+(?:W D|WD|WDL)\b"),
    re.compile(r"\bCASH WITHDRAWAL\b.*\bATM\b"),
)
_ATM_EXCLUSION_PATTERNS = (
    re.compile(r"\bDEPOSIT\b"),
    re.compile(r"\bFEES?\b"),
    re.compile(r"\bBALANCE (?:INQUIRY|ENQUIRY)\b"),
    re.compile(r"\bTRANSFER\b"),
)


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) is not None for pattern in patterns)


def classify_transaction(description: str, amount: float) -> TransactionClassification:
    text = normalize_transaction_description(description)

    has_pos_context = _matches_any(text, _POS_CONTEXT_PATTERNS)
    has_pos_credit_marker = _matches_any(text, _POS_CREDIT_PATTERNS)
    has_pos_exclusion = _matches_any(text, _POS_EXCLUSION_PATTERNS)
    is_pos_credit_or_refund = has_pos_context and (
        amount >= 0 or has_pos_credit_marker
    )
    is_pos_purchase = (
        amount < 0
        and _matches_any(text, _POS_PURCHASE_PATTERNS)
        and not has_pos_credit_marker
        and not has_pos_exclusion
    )

    is_nsf_event = _matches_any(text, _NSF_PATTERNS)
    is_atm_withdrawal = (
        amount < 0
        and _matches_any(text, _ATM_WITHDRAWAL_PATTERNS)
        and not _matches_any(text, _ATM_EXCLUSION_PATTERNS)
    )

    return TransactionClassification(
        original_description=description,
        normalized_description=text,
        is_pos_purchase=is_pos_purchase,
        is_pos_credit_or_refund=is_pos_credit_or_refund,
        is_nsf_event=is_nsf_event,
        is_atm_withdrawal=is_atm_withdrawal,
    )

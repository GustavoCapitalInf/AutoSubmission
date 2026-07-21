from __future__ import annotations
import re
from ..models import OCRLine, Transaction, AccountInfo
from ..parse_helpers import parse_money, find_amounts, normalize_date

_CREDIT_WORDS = ("deposit", "credit", "ach credit", "transfer in", "stripe",
                 "interest", "refund", "zelle deposit")
_DEBIT_WORDS = ("debit", "withdrawal", "purchase", "pos", "atm", "check",
                "payment", "fee", "charge", "transfer out", "ach debit")

_DATE_TOKEN_RE = re.compile(r"^(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|[A-Za-z]{3,}\.?\s+\d{1,2})")

def is_credit_line(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _CREDIT_WORDS)

def is_debit_line(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in _DEBIT_WORDS)

class BankProfile:
    name: str = "generic"
    header_keywords: list[str] = []

    def matches(self, page_text: str) -> bool:
        t = page_text.lower()
        return any(k.lower() in t for k in self.header_keywords)

    def parse_account_info(self, lines: list[OCRLine]) -> AccountInfo:
        return AccountInfo(bank=self.name)

    def parse_transactions(self, lines: list[OCRLine], year_hint: int | None) -> list[Transaction]:
        raise NotImplementedError

class GenericProfile(BankProfile):
    name = "generic"

    def parse_transactions(self, lines, year_hint):
        txns: list[Transaction] = []
        for ln in lines:
            text = ln.text.strip()
            m = _DATE_TOKEN_RE.match(text)
            if not m:
                continue
            date = normalize_date(m.group(0), year_hint)
            if date is None:
                continue
            amounts = find_amounts(text[m.end():])
            if not amounts:
                continue
            balance = parse_money(amounts[-1]) if len(amounts) >= 2 else None
            amount_tok = amounts[-2] if len(amounts) >= 2 else amounts[-1]
            amount = parse_money(amount_tok)
            first_amt_pos = text.find(amounts[0], m.end())
            description = text[m.end():first_amt_pos].strip() if first_amt_pos > 0 else ""
            debit = credit = None
            if is_credit_line(text):
                credit = amount
            else:
                debit = amount
            txns.append(Transaction(date=date, description=description,
                                    debit=debit, credit=credit, balance=balance,
                                    raw_line=text))
        return txns

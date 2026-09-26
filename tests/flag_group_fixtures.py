"""Fabricated rows and payees for the lender-detection classifier tests (spec §9).

Every descriptor, name and amount here is fabricated: no statement text, no
real amount, no customer name. Amounts are whole dollars.
"""
from __future__ import annotations

from analysis.schema import Transaction


def txn(day: str, description: str, amount: float, *, balance: float | None = None) -> Transaction:
    return Transaction(
        date=day,
        description=description,
        amount=amount,
        direction="credit" if amount >= 0 else "debit",
        running_balance=balance,
    )

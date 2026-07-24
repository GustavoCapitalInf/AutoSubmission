"""Normalized bank-statement data model.

This is the hand-off contract between the LLM extraction stage (which fills these
objects from the OCR markdown) and the deterministic stages (reconciliation,
metrics, detection) that do all the math. Amounts are always signed: negative =
money leaving the account (debit), positive = money entering (credit).
"""
from __future__ import annotations
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    date: str = Field(description="Transaction date as ISO YYYY-MM-DD.")
    description: str = Field(description="Full transaction description as printed.")
    amount: float = Field(
        description="Signed amount: negative for debits (money out), positive for credits (money in)."
    )
    direction: str = Field(description='Either "debit" or "credit".')
    running_balance: float | None = Field(
        default=None, description="Account balance printed after this transaction, if any."
    )


class Statement(BaseModel):
    bank: str | None = Field(default=None, description="Bank name, e.g. 'Chase'.")
    account_name: str | None = Field(default=None, description="Account holder / product name.")
    account_number: str | None = Field(default=None, description="Account number as printed.")
    period_start: str | None = Field(default=None, description="Statement period start, ISO YYYY-MM-DD.")
    period_end: str | None = Field(default=None, description="Statement period end, ISO YYYY-MM-DD.")
    beginning_balance: float | None = Field(default=None, description="Opening balance for the period.")
    ending_balance: float | None = Field(default=None, description="Closing balance for the period.")
    currency: str = Field(default="USD", description="ISO currency code.")

    # Figures the bank prints in its own summary block. These are authoritative and
    # let us (a) report the bank's own average balance without computing it and
    # (b) measure how completely the line-item detail was captured vs mangled OCR.
    days_in_period: int | None = Field(default=None, description="Bank-stated number of days in the period.")
    stated_total_credits: float | None = Field(default=None, description="Bank-stated total of deposits/credits (positive).")
    stated_total_debits: float | None = Field(default=None, description="Bank-stated total of checks/debits, as a POSITIVE magnitude.")
    stated_credit_count: int | None = Field(default=None, description="Bank-stated number of deposits/credits.")
    stated_debit_count: int | None = Field(default=None, description="Bank-stated number of checks/debits.")
    stated_average_balance: float | None = Field(
        default=None,
        description="Bank-printed average balance if shown ('Average Ledger', 'Average Collected', 'Average Daily Balance'). Prefer the ledger/daily figure.",
    )

    transactions: list[Transaction] = Field(default_factory=list)

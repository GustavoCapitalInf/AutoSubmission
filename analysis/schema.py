"""Normalized bank-statement data model.

This is the hand-off contract between the LLM extraction stage (which fills these
objects from the OCR markdown) and the deterministic stages (reconciliation,
metrics, detection) that do all the math. Amounts are always signed: negative =
money leaving the account (debit), positive = money entering (credit).
"""
from __future__ import annotations
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field


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


class StatementDailyBalance(BaseModel):
    date: str = Field(description="Calendar date as ISO YYYY-MM-DD.")
    balance: float = Field(description="Bank-printed end-of-day book or ledger balance.")


class Statement(BaseModel):
    # `populate_by_name` so a caller may use either the canonical field name or
    # a deprecated alias declared below; both resolve to the same storage.
    model_config = ConfigDict(populate_by_name=True)

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
    # The bank's OWN printed average. It is evidence to preserve, never the
    # platform's Average Daily Balance: the canonical underwriting ADB is
    # computed in `analysis/adb.py` over the printed period's calendar days and
    # no bank's convention redefines it. The two are published side by side and
    # `analysis/metrics.py` records their signed variance and a diagnostic
    # hypothesis for it.
    bank_reported_average_balance: float | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "bank_reported_average_balance", "stated_average_balance"
        ),
        description="Bank-printed average balance if shown ('Average Ledger', 'Average Collected', 'Average Daily Balance'). Prefer the ledger/daily figure.",
    )
    bank_reported_average_label: str | None = Field(
        default=None,
        description=(
            "The heading the bank printed the average under, verbatim - the "
            "basis it claims for its own figure. Set only by a parser that "
            "actually read the printed average."
        ),
    )
    stated_service_charge: float | None = Field(
        default=None, description="Bank-stated total service charge / fees for the period, as a POSITIVE magnitude.")
    stated_interest_paid: float | None = Field(
        default=None, description="Bank-stated interest paid/credited for the period, as a POSITIVE magnitude.")
    stated_nsf_count: int | None = Field(
        default=None, description="Bank-stated count of NSF / overdraft / returned items THIS period (not year-to-date), if printed.")

    stated_daily_balances: list[StatementDailyBalance] = Field(
        default_factory=list,
        description=(
            "Bank-printed dated book/ledger balance snapshots. These are source "
            "evidence, not averages; missing calendar dates carry the prior balance."
        ),
    )
    #: How many LEADING transactions this parser proved, from the document's
    #: own printed evidence, to be account-opening postings dated before the
    #: printed period. Zero everywhere except where a parser has declared it;
    #: `analysis/adb.py` re-checks every condition itself before folding them
    #: into the opening balance, and never changes the ADB divisor.
    initialization_transaction_count: int = Field(
        default=0,
        description=(
            "Number of leading transactions the parser proved are "
            "account-opening postings dated before the statement period."
        ),
    )

    transactions: list[Transaction] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stated_average_balance(self) -> float | None:
        """DEPRECATED alias for `bank_reported_average_balance`.

        Serialized as well as readable so that payload consumers of the old
        name keep working: the rename is additive on the wire, not a removal.
        Writable so the parsers that assign it keep working unchanged. Note
        that `model_copy(update={...})` bypasses attribute assignment, so the
        four parsers that build their statement that way use the canonical
        key - pydantic would silently drop the alias there.
        """
        return self.bank_reported_average_balance

    @stated_average_balance.setter
    def stated_average_balance(self, value: float | None) -> None:
        self.bank_reported_average_balance = value

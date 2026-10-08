"""Normalized bank-statement data model.

This is the hand-off contract between the LLM extraction stage (which fills these
objects from the OCR markdown) and the deterministic stages (reconciliation,
metrics, detection) that do all the math. Amounts are always signed: negative =
money leaving the account (debit), positive = money entering (credit).
"""
from __future__ import annotations
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, model_serializer
from pydantic.json_schema import SkipJsonSchema

# ---------------------------------------------------------------------------
# WHERE A PUBLISHED CURRENCY CAME FROM (CURRENCY_DOCTRINE §B, made explicit)
# ---------------------------------------------------------------------------
#
# `Statement.currency` alone cannot be audited: `"USD"` on a Chase statement
# that read nothing, `"USD"` on a Desjardins document whose product line prints
# the code, and `"USD"` on an ATB statement no reader ever asked about are three
# different facts wearing one label. The doctrine's evidence hierarchy already
# exists in prose and in each reader's comments; this vocabulary puts it in the
# DATA, so a consumer can tell a read denomination from an unread assumption
# without reading the parser.
#
# A CLOSED set, ordered here from strongest evidence to weakest. The rule that
# makes it worth anything: **a reader may not set a source it did not earn.**
# Each member below names what the reader must actually have to publish it, and
# `tests/test_currency_source.py` feeds every class a printing that lacks its
# evidence and asserts the class is refused.
#
#   printed
#       An explicit currency word or ISO code the document itself prints, read
#       off the page — `Currency: CAD` in BMO's header block, RBC's `U.S. Funds`
#       denomination line, the code CIBC prints on its closing-balance row, the
#       `AMOUNT (CAD) BALANCE (CAD)` grid header Wealthsimple's registration
#       REQUIRES.
#   product
#       The denomination is read THROUGH a printed product/account
#       designation — RBC's `CAD CHEQUING ACCOUNT` / `US BUSINESS ACCOUNT`
#       mailing-header map, TD Canada's `ACCOUNT - CAD` suffix, Desjardins'
#       `USD DESJARDINS CORPORATE BUILD-UP ACCOUNT`, the `COMPTE COURANT
#       CANADIEN` product line of the unknown-issuer Quebec layout.
#
#       The designation may or may not spell the code out: TD Canada's and
#       Desjardins' do, RBC's `CAD CHEQUING ACCOUNT` does, and the Quebec
#       layout's names a jurisdiction instead. What separates this class from
#       `printed` is not whether a code appears but WHERE it is read — inside
#       a product name the reader had to recognise first, rather than as a
#       statement of denomination the page makes on its own line. That is a
#       narrower claim about the same evidence, which is the direction this
#       vocabulary errs in: a class is filed weaker than the evidence
#       supports, never stronger.
#   jurisdiction_default
#       The ratified RBC Canada rule (doctrine §B): a PROVEN bank/jurisdiction
#       account whose page states no denomination takes its native default —
#       affirmative conjunction, refusals first, never an absence inference.
#       Only `analysis/rbc.py::_jurisdiction_currency` earns this today.
#   institution_default
#       The reader asserts the denomination from the institution's identity
#       WITHOUT reading it: `Statement(bank="Chase", currency="USD")`. True of
#       most U.S. registrations and of five Canadian ones. This is the class
#       that owes evidence — doctrine §B's final paragraph wants a proven
#       jurisdiction base before any of these becomes a `jurisdiction_default`,
#       and naming them in the payload is what makes that debt visible instead
#       of indistinguishable from a read.
#   model_extracted
#       The LLM extraction stage returned the currency (`analysis/extract.py`,
#       reached from `pipeline.py` only when no deterministic parser claimed the
#       document and `parse_mode="auto"`). The platform did not verify the
#       evidence, and the model may not certify its own provenance: whatever
#       `currency_source` the model fills into the response schema is DISCARDED
#       and replaced by this class at the boundary.
#   schema_default
#       No evidence class was earned and the published value is this field's
#       default `"USD"` — either because the reader never set `currency` at all
#       (most registrations, including every ATB document) or because it
#       explicitly re-asserted the default where its own evidence was absent
#       (`analysis/desjardins.py`, whose caisse is Canadian: writing
#       `institution_default` there would assert a USD institution that does
#       not exist).
#
# NOT a currency conversion story. This field records provenance only: no FX,
# no cross-currency aggregation, no value moves because of it
# (CURRENCY_DOCTRINE §A/§E/§F, Gustavo 2026-08-21).
CURRENCY_SOURCES: tuple[str, ...] = (
    "printed",
    "product",
    "jurisdiction_default",
    "institution_default",
    "model_extracted",
    "schema_default",
)

CurrencySource = Literal[
    "printed",
    "product",
    "jurisdiction_default",
    "institution_default",
    "model_extracted",
    "schema_default",
]


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
    # Audit B10 (I05, I60): a deterministic parser sets this on a CREDIT whose published description is only its own
    # type or section label because the payer text the statement printed for the row could not be read (an
    # indeterminate flush of merchant blocks, a description overlay that failed closed). The true-revenue pass then
    # counts the row as 'payer text not read', never as Q2's 'no payer printed', which is for a row whose statement
    # prints no payer. Kept out of the extraction response schema (`SkipJsonSchema`, so the extractor is told nothing
    # new and tests/test_extraction_schema_prompt_surface.py's digest holds) and out of every serialized transaction
    # that does not carry it (`_serialize`), so no stored payload gains a key it did not have.
    payer_text_unread: SkipJsonSchema[bool] = False
    # Audit round 2, R2-B07 (R07): on a credit the parser marked (`payer_text_unread`) because a flush of several rows'
    # merchant blocks could not be attributed, the flush's text, joined: what the statement printed for SOME row of
    # that flush, never proven this row's, so it is no description. The true-revenue pass reads it only to hold a
    # marked credit whose run prints a lender's block (never to verify, to name a payer or to count a lender credit),
    # and the review card prints it so a reviewer can release a customer's row. Kept out of the extraction response
    # schema and out of every serialized transaction that does not carry it, as `payer_text_unread` is.
    unread_payer_text: SkipJsonSchema[str] = ""

    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if isinstance(data, dict):
            if not self.payer_text_unread:
                data.pop("payer_text_unread", None)
            if not self.unread_payer_text:
                data.pop("unread_payer_text", None)
        return data


class StatementDailyBalance(BaseModel):
    date: str = Field(description="Calendar date as ISO YYYY-MM-DD.")
    balance: float = Field(description="Bank-printed end-of-day book or ledger balance.")


class Statement(BaseModel):
    # ONE ACCOUNT's statement — which is what this model has always meant.
    #
    # Every field below is singular by construction: one account number, one
    # period, one opening and closing balance, one ledger. That is not a
    # limitation to be widened. A PDF may print several accounts of one member,
    # and the object for that is `analysis.pipeline.DocumentReport`, which
    # holds one of these PER ACCOUNT plus the facts that belong to the document
    # rather than to any account. The word "statement" keeps meaning "one
    # account's statement"; the word for "one PDF" is DOCUMENT. So a reader
    # that finds a second account on the page does not stretch this model to
    # carry it, and a surface that needs one value for a document does not take
    # it from one of these.
    #
    # DELIBERATELY A COMMENT AND NOT A DOCSTRING, which is the one place this
    # class cannot say it: `analysis/extract.py`:222 passes `Statement` as the
    # extraction call's `response_schema`, and pydantic publishes a model's
    # docstring as its JSON-schema `description` — so a docstring here is
    # prompt text sent to the extractor, and prose addressed to implementers
    # would silently become an instruction addressed to a model. The words
    # belong to the reader of this file; the schema keeps the shape it had.

    # `populate_by_name` so a caller may use either the canonical field name or
    # a deprecated alias declared below; both resolve to the same storage.
    model_config = ConfigDict(populate_by_name=True)

    bank: str | None = Field(default=None, description="Bank name, e.g. 'Chase'.")
    account_name: str | None = Field(
        default=None, description="The name printed for the account: a product, a nickname, or on some layouts a person."
    )
    #: Audit B9 (I13): the holder's own name, kept apart from `account_name` (which a parser fills with a product, a
    #: nickname or nothing), so the revenue holds can read who owns the account. None when the parser reads none.
    holder_name: str | None = Field(
        default=None, description="Account holder's name as printed in the header or mailing address block."
    )
    # Owner ruling 2026-10-02 (the underwriter's Q10), audit round 2, R2-OW10: the title the bank prints after the
    # holder's name (a premium trust, an operating or a wire account), read from the holder reader's own anchor
    # (analysis.holder_name.HolderReading); provenance for the revenue rule. Kept out of the extraction response schema
    # (`SkipJsonSchema`: the extractor is told nothing new) and out of every serialized statement that carries none
    # (`_serialize`), so no stored payload gains a key it did not have.
    account_title: SkipJsonSchema[str | None] = None
    account_number: str | None = Field(default=None, description="Account number as printed.")
    period_start: str | None = Field(default=None, description="Statement period start, ISO YYYY-MM-DD.")
    period_end: str | None = Field(default=None, description="Statement period end, ISO YYYY-MM-DD.")
    beginning_balance: float | None = Field(default=None, description="Opening balance for the period.")
    ending_balance: float | None = Field(default=None, description="Closing balance for the period.")
    currency: str = Field(default="USD", description="ISO currency code.")
    #: The evidence class that produced `currency` — see `CURRENCY_SOURCES`
    #: above. Defaults to `schema_default` so that a reader which never sets
    #: `currency` publishes the truth about it rather than looking like a read.
    #: Additive and provenance-only: no financial value depends on it.
    currency_source: CurrencySource = Field(
        default="schema_default",
        description=(
            "Where `currency` came from: printed | product | "
            "jurisdiction_default | institution_default | model_extracted | "
            "schema_default."
        ),
    )

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
    #: How many LEADING transactions this parser proved, from the document's
    #: own printed evidence, are postings the bank dated on the day its
    #: previous-balance line names (the day before the printed period) and
    #: counted in THIS cycle's printed totals: activity posted after the last
    #: statement closed. They set the balance day one opens with. Zero
    #: everywhere except where a parser has declared it (Capital One, owner
    #: report 2026-10-08); `analysis/adb.py` re-checks every condition itself
    #: before folding them into the opening balance, never makes their day a
    #: ledger day and never changes the ADB divisor. Serialized only when
    #: declared (see `_serialize`).
    pre_period_carry_in_count: int = Field(
        default=0,
        description=(
            "Number of leading transactions the parser proved are postings "
            "dated on the printed previous-balance day and counted in this "
            "cycle's printed totals."
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

    # Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: `account_title` is serialized only when a reader set it,
    # as Transaction._serialize drops its unset parser marks. A comment, not a docstring (see the class's comment).
    # Owner report 2026-10-08: `pre_period_carry_in_count` likewise only when a parser declared one, so every other
    # statement's payload is unchanged.
    @model_serializer(mode="wrap")
    def _serialize(self, handler):
        data = handler(self)
        if isinstance(data, dict) and self.account_title is None:
            data.pop("account_title", None)
        if isinstance(data, dict) and not self.pre_period_carry_in_count:
            data.pop("pre_period_carry_in_count", None)
        return data

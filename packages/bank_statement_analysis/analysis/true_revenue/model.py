"""CreditFacts, CounterDebits, CounterCredit, InsurerReading and the micro floor."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from analysis.descriptor.credit_words import _MICRO_DEPOSIT_FLOOR

if TYPE_CHECKING:
    from analysis.classification.record import CounterDebitReading, TransactionClassification


@dataclass(frozen=True)
class CreditFacts:
    """§8: one posted credit's payer facts."""

    channel: str
    region: str
    name: str
    key: tuple[str, ...]
    entry: str
    hold: str | None
    claimed: bool
    wire_n1: bool
    company_form: bool
    public_or_healthcare: bool
    healthcare: bool
    numbered: bool
    electronic: bool
    refused_word: bool
    round_sum: bool
    consumer_entry: bool
    transfer_no_counterparty: bool
    account_designation: bool
    #: §8.9: the payer is a factor FACTORING_PAYOUT_PAYERS names (_factoring_payout_payer).
    factor: bool = False
    #: §8.2, §8.6: the payer region names only a bank (_bank_only_payer): 'sending', 'own', 'form', or None.
    bank_only: str | None = None
    #: §8.1: the row moves the holder's own money in on its face (self_originated) and nothing claimed it, the
    #: guard _first_hold reads: never verified, never a repeat.
    self_own: bool = False
    #: §8.9: the lease-to-own or patient financier whose merchant payout the row is (_customer_financier: the
    #: ledger entity CUSTOMER_FINANCING_PAYERS names), or None.
    financier: str | None = None
    #: §8.1, §8.10: a builder's progress draw (construction_progress_draw) on a row nothing claimed: counted and
    #: flagged, never verified, never a repeat.
    progress_draw: bool = False
    #: §8.1: on IAA's row the insurer-name hold names (its INSURANCE is the auction's name), the hold of §8.10's
    #: order that would name it after that hold, or None: Q11 reads the row only when none would, so every other hold
    #: keeps an IAA seller payout held.
    hold_past_insurer_name: str | None = None
    #: §8.1, §8.10: the reason T4's financing-root hold was lifted with (finance_named_customer, lessor_rent or
    #: lender_paid_for_services: finance_named_release), set only where no hold names the row then; never verified,
    #: never a repeat, its counted reason relabelled last.
    q9: str | None = None
    #: §8.1, §8.6: the bare settlement word alone (merchant_settlement's _HOLDER_NAMED_SETTLEMENT_ENTRY arm) lifted from
    #: the row the pass-7 holder hold (an unverified credit) or the row-alone own-push guard (self_originated): whatever
    #: slot or boundary the word sits in, refused as proof (refused_word), never a repeat (_never_q5_or_q6), and, where
    #: an earlier rule verified the row under the own-push guard, overruled (_settlement_never_verified).
    settlement_released: bool = False


@dataclass(frozen=True)
class _CounterDebit:
    """One posted debit as the counter-debit holds read it: its reading, its kind (lender, receiving_fee, circular,
    processor_fee, bill or other), its amount in cents, the registry lender it names (a lender debit) and whether
    another debit of the payer's word posts the same amount (recurring). `payout`, the debit prints a platform's payout
    id (processor_payout: the platform's own pull under the merchant's descriptor); `person_key`, on a person-to-person
    or push debit whose recipient prints a name of two words or more, that name's first two words glued (the only key a
    credit matches it by, a debit for the credit's own amount aside); `card`, a card purchase in a form the card-form
    prefix misses, which keeps its own kind (a fee, a bill or another debit): the card form only lifts a payout's hold
    (also_debited). A lender debit's reading keeps the place words (classifier._without_not_a_payer). `premium`, a
    non-lender debit printing a premium or a retry of one (_PREMIUM_DEBIT, on its kind text with Chase's glued SEC code
    split off); a lender debit's is always False."""

    reading: CounterDebitReading
    kind: str
    cents: int
    entity: str | None
    recurring: bool
    payout: bool = False
    person_key: str | None = None
    card: bool = False
    premium: bool = False


@dataclass(frozen=True)
class CounterDebits:
    """The statement's posted debits that may hold a payer: the lender and financing debits, the others."""

    lender: tuple[_CounterDebit, ...]
    other: tuple[_CounterDebit, ...]


@dataclass(frozen=True)
class CounterCredit:
    """One posted credit as the counter-debit holds read it. `payout`, the credit prints a platform's payout id
    (processor_payout); `person_key`, on a person-to-person or push credit whose sender prints a name of two words
    or more and no company form, that name's first two words glued (a company's push is compared by the B4 forms
    as before); `lender_reading`, the reading the lender hold compares (the place words kept; None: `reading`).
    `released_insurer`, the credit the Q2 release counted as an insurer paying for the business's work
    (INSURER_FOR_WORK_METHOD)."""

    reading: CounterDebitReading
    cents: int
    entity: str | None
    settlement: bool
    insurer: bool
    payout: bool = False
    person_key: str | None = None
    lender_reading: CounterDebitReading | None = None
    released_insurer: bool = False


@dataclass(frozen=True)
class _OwnWords:
    """§7.0: the holder's own words on a store-name platform (`words`), and (FW wave 3) the platform entry's words when
    they are a consecutive run of the holder's name (`run`: the store's own name, spared at any length)."""

    words: frozenset[str] = frozenset()
    run: frozenset[str] = frozenset()


@dataclass(frozen=True)
class InsurerReading:
    """§8.1: an insurer read on a credit's payer region. `key` is the carrier the frequency of the underwriter's Q2
    counts by (the registry's or the brand table's entity name, so one carrier is one key however it prints; otherwise
    the payer key of the region without the holder's names); `kind` is 'registry' (a listed insurer, §6.1 step 5),
    'brand' (INSURER_CREDIT_BRANDS), 'named' (an insurer word, spelling or claim word) or 'title' (a title insurer,
    whose credit is a property closing's proceeds); `for_work` is False only for a title insurer and a government
    payer, whose insurance programme's credit is a personal benefit or a public insurer's, never the business's work."""

    key: str
    kind: str
    for_work: bool


def _under_micro_floor(record: TransactionClassification) -> bool:
    """§7.0: a credit under the absolute micro-deposit floor ($1, _MICRO_DEPOSIT_FLOOR)."""
    return record.amount < _MICRO_DEPOSIT_FLOOR

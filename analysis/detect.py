"""Authoritative lender, potential-lender, and insurance evidence views."""
from __future__ import annotations

from dataclasses import dataclass, field

from .dates import parse_date
from .schema import Statement, Transaction
from .transaction_classifier import (
    TransactionClassification,
    classify_cadence,
    classify_statement_transactions,
)


@dataclass
class FunderMatch:
    funder: str
    matched_alias: str | None
    classification: str = "confirmed_lender"
    transactions: list[Transaction] = field(default_factory=list)
    evidence: list[TransactionClassification] = field(default_factory=list)
    total_debited: float = 0.0
    status: str = "confirmed"


@dataclass
class InsuranceMatch:
    provider: str
    matched_alias: str | None
    transactions: list[Transaction] = field(default_factory=list)
    evidence: list[TransactionClassification] = field(default_factory=list)
    count: int = 0
    total_debited: float = 0.0


@dataclass
class RecurringDebit:
    description_key: str
    amount: float
    count: int
    cadence: str
    avg_gap_days: float | None
    transactions: list[Transaction] = field(default_factory=list)
    evidence: list[TransactionClassification] = field(default_factory=list)


@dataclass
class DetectionResult:
    known_funders: list[FunderMatch] = field(default_factory=list)
    potential_lenders: list[FunderMatch] = field(default_factory=list)
    insurance_providers: list[InsuranceMatch] = field(default_factory=list)
    recurring_debits: list[RecurringDebit] = field(default_factory=list)
    lender_evidence: list[TransactionClassification] = field(default_factory=list)
    insurance_evidence: list[TransactionClassification] = field(default_factory=list)
    manual_review: list[TransactionClassification] = field(default_factory=list)


def _records(
    stmt: Statement,
    classifications: list[TransactionClassification] | None,
) -> list[TransactionClassification]:
    records = classifications if classifications is not None else classify_statement_transactions(stmt)
    if len(records) != len(stmt.transactions):
        raise ValueError("classification count must equal transaction count")
    return records


def _group_funders(
    stmt: Statement,
    records: list[TransactionClassification],
    *,
    state: str,
) -> list[FunderMatch]:
    matches: dict[str, FunderMatch] = {}
    for transaction, record in zip(stmt.transactions, records):
        contributes = (
            record.contributes_to_lender_count
            if state == "confirmed_lender"
            else record.contributes_to_potential_lender_count
        )
        if record.classification != state or not record.canonical_entity or not contributes:
            continue
        match = matches.get(record.canonical_entity)
        if match is None:
            match = FunderMatch(
                funder=record.canonical_entity,
                matched_alias=record.matched_alias,
                classification=state,
                status="confirmed" if state == "confirmed_lender" else "review_required",
            )
        match.transactions.append(transaction)
        match.evidence.append(record)
        if state == "confirmed_lender" and record.contributes_to_lender_totals:
            match.total_debited += abs(record.amount)
        matches[record.canonical_entity] = match
    for match in matches.values():
        match.total_debited = round(match.total_debited, 2)
    return sorted(matches.values(), key=lambda item: (-item.total_debited, item.funder))


def find_known_funders(
    stmt: Statement,
    classifications: list[TransactionClassification] | None = None,
) -> list[FunderMatch]:
    return _group_funders(stmt, _records(stmt, classifications), state="confirmed_lender")


def find_potential_lenders(
    stmt: Statement,
    classifications: list[TransactionClassification] | None = None,
) -> list[FunderMatch]:
    return _group_funders(stmt, _records(stmt, classifications), state="potential_lender")


def find_insurance(
    stmt: Statement,
    classifications: list[TransactionClassification] | None = None,
) -> list[InsuranceMatch]:
    records = _records(stmt, classifications)
    matches: dict[str, InsuranceMatch] = {}
    for transaction, record in zip(stmt.transactions, records):
        if not record.contributes_to_insurance_totals:
            continue
        provider = record.canonical_entity or "Insurance provider not identified"
        match = matches.get(provider)
        if match is None:
            match = InsuranceMatch(provider=provider, matched_alias=record.matched_alias)
        match.transactions.append(transaction)
        match.evidence.append(record)
        match.count += 1
        match.total_debited += abs(record.amount)
        matches[provider] = match
    for match in matches.values():
        match.total_debited = round(match.total_debited, 2)
    return sorted(matches.values(), key=lambda item: (-item.total_debited, item.provider))


def find_recurring_debits(
    stmt: Statement,
    *,
    min_count: int = 3,
    classifications: list[TransactionClassification] | None = None,
) -> list[RecurringDebit]:
    records = _records(stmt, classifications)
    groups: dict[tuple[str, float], list[int]] = {}
    for index, record in enumerate(records):
        if (
            record.classification == "potential_lender"
            and record.match_method == "recurring_financing_counterparty"
            and record.contributes_to_potential_lender_count
            and record.canonical_entity
        ):
            groups.setdefault((record.canonical_entity, round(abs(record.amount), 2)), []).append(index)

    output: list[RecurringDebit] = []
    for (entity, amount), indexes in groups.items():
        if len(indexes) < min_count:
            continue
        dates = [parsed for index in indexes if (parsed := parse_date(records[index].date)) is not None]
        cadence, average_gap = classify_cadence(dates)
        output.append(
            RecurringDebit(
                description_key=entity,
                amount=amount,
                count=len(indexes),
                cadence=cadence,
                avg_gap_days=average_gap,
                transactions=[stmt.transactions[index] for index in indexes],
                evidence=[records[index] for index in indexes],
            )
        )
    return sorted(output, key=lambda item: (-item.count, item.description_key))


def detect(
    stmt: Statement,
    *,
    min_count: int = 3,
    classifications: list[TransactionClassification] | None = None,
) -> DetectionResult:
    records = _records(stmt, classifications)
    lender_evidence = [record for record in records if record.contributes_to_lender_totals]
    insurance_evidence = [record for record in records if record.contributes_to_insurance_totals]
    manual_review = [record for record in records if record.review_required]
    return DetectionResult(
        known_funders=find_known_funders(stmt, records),
        potential_lenders=find_potential_lenders(stmt, records),
        insurance_providers=find_insurance(stmt, records),
        recurring_debits=find_recurring_debits(stmt, min_count=min_count, classifications=records),
        lender_evidence=lender_evidence,
        insurance_evidence=insurance_evidence,
        manual_review=manual_review,
    )

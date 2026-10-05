"""Authoritative lender, potential-lender, insurance and flagged-position evidence views."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .cadence import describe_cadence
from .dates import parse_date
from .flag_groups import FLAG_GROUPS
from .metrics import POTENTIAL_WITHHOLDING_FORMULA
from .schema import Statement, Transaction
from .transaction_classifier import (
    TransactionClassification,
    classify_cadence,
    classify_statement_transactions,
    flagged_payee,
)


@dataclass
class FunderMatch:
    funder: str
    matched_alias: str | None
    classification: str = "confirmed_lender"
    transactions: list[Transaction] = field(default_factory=list)
    evidence: list[TransactionClassification] = field(default_factory=list)
    debit_count: int = 0
    total_debited: float = 0.0
    eligible_deposit_denominator: float | None = None
    potential_withholding_exposure: float | None = None
    potential_withholding_formula: str | None = None
    review_required: bool = False
    status: str = "confirmed"
    # Owner ruling 2026-10-02 (the underwriter's Q5, audit I29; R2-OW13): a confirmed funder's payments the bank
    # returned unpaid, listed with the funder but never counted in debit_count or total_debited (paid to lenders):
    # how many, their total, and one {amount, debit_date, debit_location, credit_date, credit_location} each.
    returned_count: int = 0
    returned_total: float = 0.0
    returned_payments: list[dict] = field(default_factory=list)


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
class FlaggedPositionMatch:
    """One payee of one flagged group (spec §6): never a lender, never in lender math.

    `count` and `total_debited` are the payee's debits; `count_credited` and
    `total_credited` are the credits it paid in (owner ruling 2026-09-26: a
    factor's payouts, which stay revenue). The cadence and the dates read every
    row that counts, debit or credit."""

    group: str
    payee: str
    matched_alias: str | None
    count: int = 0
    total_debited: float = 0.0
    count_credited: int = 0
    total_credited: float = 0.0
    cadence: str = "single"
    avg_gap_days: float | None = None
    first_date: str | None = None
    last_date: str | None = None
    source_locations: list[str] = field(default_factory=list)
    # 5.3 (owner ruling 2026-09-27): the payee is a review entity of the ledger routed to its flag, unconfirmed.
    review_required: bool = False


@dataclass
class DetectionResult:
    known_funders: list[FunderMatch] = field(default_factory=list)
    potential_lenders: list[FunderMatch] = field(default_factory=list)
    insurance_providers: list[InsuranceMatch] = field(default_factory=list)
    flagged_positions: list[FlaggedPositionMatch] = field(default_factory=list)
    recurring_debits: list[RecurringDebit] = field(default_factory=list)
    lender_evidence: list[TransactionClassification] = field(default_factory=list)
    potential_lender_evidence: list[TransactionClassification] = field(default_factory=list)
    insurance_evidence: list[TransactionClassification] = field(default_factory=list)
    # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): one item per returned funder payment, the dashboard's
    # warning: {funder, amount, debit_date, debit_location, credit_date, credit_location, credit_description}, the
    # credit's description as the bank printed it.
    returned_funder_payments: list[dict] = field(default_factory=list)
    verified_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    unverified_deposit_evidence: list[TransactionClassification] = field(default_factory=list)
    # 5.6 (true revenue spec §9.1): the counted and the held credits.
    counted_flagged_evidence: list[TransactionClassification] = field(default_factory=list)
    excluded_pending_review_evidence: list[TransactionClassification] = field(default_factory=list)
    # Deprecated aliases for version 3.0 API consumers. 5.6 (T9): true_revenue_evidence is True revenue's rows,
    # verified plus counted.
    true_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    potential_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    non_revenue_evidence: list[TransactionClassification] = field(default_factory=list)
    manual_review: list[TransactionClassification] = field(default_factory=list)


def _records(
    stmt: Statement,
    classifications: list[TransactionClassification] | None,
) -> list[TransactionClassification]:
    records = classifications if classifications is not None else classify_statement_transactions(stmt)
    if len(records) != len(stmt.transactions):
        raise ValueError("classification count must equal transaction count")
    return records


#: The keys of a funder's returned_payments item (R2-OW13).
_RETURNED_PAYMENT_KEYS = ("amount", "debit_date", "debit_location", "credit_date", "credit_location")


def _returned_funder_payments(records: list[TransactionClassification]) -> list[dict]:
    """Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): one item per confirmed funder's payment returned unpaid
    (a debit with returned_funder_payment_by), in the debits' row order: the funder, the amount, the debit's and the
    return credit's dates and locations, and the credit's description as the bank printed it (the warning quotes it, so
    a business's reversal of the debit reads apart from a bank's bounce)."""
    by_location = {record.source_location or f"transaction:{index + 1}": record for index, record in enumerate(records)}
    items: list[dict] = []
    for index, record in enumerate(records):
        if not record.returned_funder_payment_by or record.amount >= 0:
            continue
        credit = by_location.get(record.returned_funder_payment_by)
        items.append({
            "funder": record.canonical_entity,
            "amount": round(abs(record.amount), 2),
            "debit_date": record.date,
            "debit_location": record.source_location or f"transaction:{index + 1}",
            "credit_date": credit.date if credit is not None else None,
            "credit_location": record.returned_funder_payment_by,
            "credit_description": credit.original_description if credit is not None else None,
        })
    return items


def _group_funders(
    stmt: Statement,
    records: list[TransactionClassification],
    *,
    state: str,
    eligible_deposits: float | None = None,
) -> list[FunderMatch]:
    matches: dict[str, FunderMatch] = {}
    returned = (
        {item["debit_location"]: item for item in _returned_funder_payments(records)}
        if state == "confirmed_lender" else {}
    )
    for index, (transaction, record) in enumerate(zip(stmt.transactions, records)):
        paid = (
            record.contributes_to_lender_totals
            if state == "confirmed_lender"
            else record.contributes_to_potential_lender_totals
        )
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): a confirmed funder's payment returned unpaid joins
        # its funder, so a funder whose every payment bounced is still listed; debit_count and total_debited stay paid.
        returned_payment = state == "confirmed_lender" and bool(record.returned_funder_payment_by)
        if record.classification != state or not record.canonical_entity or not (paid or returned_payment):
            continue
        # 5.3 (2026-09-27): an unnamed potential payee is listed under its own label, one per payee key.
        name = record.potential_payee_label or record.canonical_entity
        match = matches.get(name)
        if match is None:
            match = FunderMatch(
                funder=name,
                matched_alias=record.matched_alias,
                classification=state,
                status="confirmed" if state == "confirmed_lender" else "review_required",
                review_required=state == "potential_lender",
            )
        match.transactions.append(transaction)
        match.evidence.append(record)
        if paid:
            match.debit_count += 1
            match.total_debited += abs(record.amount)
        if returned_payment:
            item = returned.get(record.source_location or f"transaction:{index + 1}")
            match.returned_count += 1
            match.returned_total += abs(record.amount)
            if item is not None:
                match.returned_payments.append({key: item[key] for key in _RETURNED_PAYMENT_KEYS})
        matches[name] = match
    for match in matches.values():
        match.total_debited = round(match.total_debited, 2)
        match.returned_total = round(match.returned_total, 2)
        if state == "potential_lender":
            match.eligible_deposit_denominator = eligible_deposits
            match.potential_withholding_formula = POTENTIAL_WITHHOLDING_FORMULA
            if eligible_deposits is not None and eligible_deposits > 0:
                match.potential_withholding_exposure = (
                    abs(match.total_debited) / eligible_deposits
                ) * 100
    return sorted(matches.values(), key=lambda item: (-item.total_debited, item.funder))


def find_known_funders(
    stmt: Statement,
    classifications: list[TransactionClassification] | None = None,
) -> list[FunderMatch]:
    return _group_funders(stmt, _records(stmt, classifications), state="confirmed_lender")


def find_potential_lenders(
    stmt: Statement,
    classifications: list[TransactionClassification] | None = None,
    *,
    eligible_deposits: float | None = None,
) -> list[FunderMatch]:
    return _group_funders(
        stmt,
        _records(stmt, classifications),
        state="potential_lender",
        eligible_deposits=eligible_deposits,
    )


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


def find_flagged_positions(
    stmt: Statement,
    classifications: list[TransactionClassification] | None = None,
) -> list[FlaggedPositionMatch]:
    """Spec §6: one entry per flagged group and payee, over rows marked
    contributes_to_flagged_totals, sorted by group (FLAG_GROUPS order), then
    total debited plus total credited (descending), then payee. A payee whose
    counted rows are all credits is an entry too, with a count of 0."""
    records = _records(stmt, classifications)
    matches: dict[tuple[str, str], FlaggedPositionMatch] = {}
    dates: dict[tuple[str, str], list[date]] = {}
    for index, record in enumerate(records):
        if not record.contributes_to_flagged_totals or not record.flagged_group:
            continue
        payee = flagged_payee(record)
        key = (record.flagged_group, payee)
        match = matches.get(key)
        if match is None:
            match = FlaggedPositionMatch(
                group=record.flagged_group,
                payee=payee,
                matched_alias=record.matched_alias,
            )
            matches[key] = match
            dates[key] = []
        if record.amount < 0:
            match.count += 1
            match.total_debited += abs(record.amount)
        else:
            match.count_credited += 1
            match.total_credited += record.amount
        match.review_required = match.review_required or record.review_required
        match.source_locations.append(record.source_location or f"transaction:{index + 1}")
        parsed = parse_date(record.date)
        if parsed is not None:
            dates[key].append(parsed)
    for key, match in matches.items():
        match.total_debited = round(match.total_debited, 2)
        match.total_credited = round(match.total_credited, 2)
        match.cadence, match.avg_gap_days = describe_cadence(dates[key])
        if dates[key]:
            match.first_date = min(dates[key]).isoformat()
            match.last_date = max(dates[key]).isoformat()
    order = {group.key: position for position, group in enumerate(FLAG_GROUPS)}
    return sorted(
        matches.values(),
        key=lambda item: (
            order.get(item.group, len(order)),
            -(item.total_debited + item.total_credited),
            item.payee,
        ),
    )


#: The recurrence tier's match methods (spec §4.3 statement pass 2): the
#: financing-keyword promotion and D6's fixed daily or weekly debits.
_RECURRING_MATCH_METHODS = frozenset({"recurring_financing_counterparty", "recurring_fixed_debit"})


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
            and record.match_method in _RECURRING_MATCH_METHODS
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
    eligible_deposits: float | None = None,
) -> DetectionResult:
    records = _records(stmt, classifications)
    lender_evidence = [record for record in records if record.contributes_to_lender_totals]
    potential_lender_evidence = [
        record for record in records if record.contributes_to_potential_lender_totals
    ]
    insurance_evidence = [record for record in records if record.contributes_to_insurance_totals]
    verified_revenue_evidence = [
        record for record in records if record.contributes_to_verified_revenue
    ]
    unverified_deposit_evidence = [
        record for record in records if record.contributes_to_unverified_deposit
    ]
    non_revenue_evidence = [record for record in records if record.contributes_to_non_revenue]
    counted_flagged_evidence = [record for record in records if record.contributes_to_counted_flagged]
    excluded_pending_review_evidence = [
        record for record in records if record.contributes_to_excluded_pending_review
    ]
    true_revenue_evidence = [
        record for record in records
        if record.contributes_to_verified_revenue or record.contributes_to_counted_flagged
    ]
    # 5.6: a row's revenue_review_required is set for a held credit only (§5.4).
    manual_review = [
        record
        for record in records
        if record.review_required or record.revenue_review_required
    ]
    return DetectionResult(
        known_funders=find_known_funders(stmt, records),
        potential_lenders=find_potential_lenders(
            stmt,
            records,
            eligible_deposits=eligible_deposits,
        ),
        insurance_providers=find_insurance(stmt, records),
        flagged_positions=find_flagged_positions(stmt, records),
        recurring_debits=find_recurring_debits(stmt, min_count=min_count, classifications=records),
        lender_evidence=lender_evidence,
        potential_lender_evidence=potential_lender_evidence,
        insurance_evidence=insurance_evidence,
        returned_funder_payments=_returned_funder_payments(records),
        verified_revenue_evidence=verified_revenue_evidence,
        unverified_deposit_evidence=unverified_deposit_evidence,
        counted_flagged_evidence=counted_flagged_evidence,
        excluded_pending_review_evidence=excluded_pending_review_evidence,
        true_revenue_evidence=true_revenue_evidence,
        potential_revenue_evidence=unverified_deposit_evidence,
        non_revenue_evidence=non_revenue_evidence,
        manual_review=manual_review,
    )

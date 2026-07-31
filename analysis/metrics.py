"""Stage 3a — deterministic analytics. Every number a funder cares about is
computed here in plain Python from the reconciled ledger, never by the LLM.

Average Daily Balance is the headline figure and lives in its own module,
`analysis.adb`, because it carries its own daily ledger, validation suite and
audit trail. This module consumes that result and exposes it on `Metrics`
(`average_daily_balance`, `daily_balance_sum`, `calendar_day_count`, `adb`).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from .adb import AverageDailyBalanceResult, compute_average_daily_balance
from .schema import Statement
from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
)


@dataclass
class Metrics:
    days_in_period: int | None = None
    # Bank-printed average balance ("Average Ledger" etc.) when the statement shows
    # one — authoritative and needs no computation. `average_daily_balance` below is
    # our own figure computed from dated running balances (used when there's no
    # printed one, or to cross-check it).
    stated_average_balance: float | None = None
    average_balance: float | None = None
    average_balance_source: str | None = None
    average_daily_balance: float | None = None
    # Full underwriting-grade ADB working: the daily ledger, its sum, the
    # calendar-day divisor, and every validation that was run. See analysis/adb.py.
    adb: AverageDailyBalanceResult | None = None
    daily_balance_sum: float | None = None
    calendar_day_count: int | None = None
    adb_ok: bool | None = None
    min_balance: float | None = None
    max_balance: float | None = None
    negative_days: int = 0
    # Line-item totals: computed only from extracted transaction rows.
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0
    num_deposits: int = 0
    num_withdrawals: int = 0
    # Effective underwriting totals: prefer reconciled bank summary figures when
    # available; otherwise fall back to line-item totals and expose the source.
    effective_total_deposits: float = 0.0
    effective_total_withdrawals: float = 0.0
    effective_num_deposits: int | None = None
    effective_num_withdrawals: int | None = None
    deposits_source: str = "line_items"
    withdrawals_source: str = "line_items"
    nsf_count: int = 0                     # from line items (a lower bound if detail is incomplete)
    stated_nsf_count: int | None = None    # bank-printed count this period, when available
    effective_nsf_count: int = 0
    nsf_source: str = "classified_line_items"
    lender_credits: float = 0.0
    lender_debits: float = 0.0
    lender_debit_count: int = 0
    lenders_detected: int = 0
    potential_lenders_detected: int = 0
    monthly_lender_debits: float = 0.0
    insurance_count: int = 0
    insurance_total: float = 0.0
    true_revenue: float = 0.0
    cash_flow: float = 0.0
    withholding_rate: float | None = None
    withholding_numerator: float = 0.0
    withholding_denominator: float = 0.0
    withholding_formula: str = "abs(total_qualifying_lender_debits) / eligible_deposits * 100"
    withholding_review_required: bool = False
    eligible_deposits: float = 0.0
    eligible_deposit_definition: str = (
        "effective total deposits minus recognized lender funding credits"
    )
    lender_evidence: list[TransactionClassification] = field(default_factory=list)
    insurance_evidence: list[TransactionClassification] = field(default_factory=list)
    pos_count: int = 0
    pos_credit_count: int = 0
    atm_withdrawal_count: int = 0
    ach_credit_count: int = 0
    ach_debit_count: int = 0
    check_count: int = 0
    loan_count: int = 0
    notes: list[str] = field(default_factory=list)


def daily_closing_balances(stmt: Statement) -> dict[date, float]:
    """Each calendar day in the statement period mapped to its ending balance.

    A thin view over `compute_average_daily_balance` so there is exactly one
    implementation of the daily ledger. Returns {} when no period or opening
    balance can be established.
    """
    result = compute_average_daily_balance(stmt)
    return {date.fromisoformat(d.date): d.ending_balance for d in result.daily_balances}


def _summary_debits_with_service_charge(stmt: Statement) -> float | None:
    if stmt.stated_total_debits is None:
        return None
    debits = round(stmt.stated_total_debits, 2)
    sc = stmt.stated_service_charge or 0.0
    if (
        sc
        and stmt.beginning_balance is not None
        and stmt.ending_balance is not None
        and stmt.stated_total_credits is not None
    ):
        interest = stmt.stated_interest_paid or 0.0
        base = stmt.beginning_balance + stmt.stated_total_credits - debits + interest
        separate_resid = round(base - sc - stmt.ending_balance, 2)
        folded_resid = round(base - stmt.ending_balance, 2)
        if abs(separate_resid) <= 1.00 and abs(folded_resid) > 1.00:
            debits = round(debits + sc, 2)
    return debits


def compute_metrics(
    stmt: Statement,
    *,
    trust_stated_summary: bool | None = None,
    trust_running_balances: bool = True,
    source_markdown: str | None = None,
    classifications: list[TransactionClassification] | None = None,
) -> Metrics:
    m = Metrics()
    m.stated_average_balance = stmt.stated_average_balance
    m.stated_nsf_count = stmt.stated_nsf_count
    records = classifications if classifications is not None else classify_statement_transactions(stmt)
    if len(records) != len(stmt.transactions):
        raise ValueError("classification count must equal transaction count")
    confirmed_entities: set[str] = set()
    potential_entities: set[str] = set()
    for t, classification in zip(stmt.transactions, records):
        if t.amount >= 0:
            m.total_deposits += t.amount
            m.num_deposits += 1
        else:
            m.total_withdrawals += -t.amount
            m.num_withdrawals += 1
        if classification.is_nsf_event:
            m.nsf_count += 1
        if classification.contributes_to_lender_credit_exclusion:
            m.lender_credits += abs(t.amount)
        if classification.contributes_to_lender_totals:
            m.lender_debits += abs(t.amount)
            m.lender_debit_count += 1
            m.lender_evidence.append(classification)
        if classification.contributes_to_lender_count and classification.canonical_entity:
            confirmed_entities.add(classification.canonical_entity)
        if classification.contributes_to_potential_lender_count and classification.canonical_entity:
            potential_entities.add(classification.canonical_entity)
        if classification.contributes_to_insurance_totals:
            m.insurance_count += 1
            m.insurance_total += abs(t.amount)
            m.insurance_evidence.append(classification)
        if classification.is_pos_purchase and classification.duplicate_of is None:
            m.pos_count += 1
        if classification.is_pos_credit_or_refund and classification.duplicate_of is None:
            m.pos_credit_count += 1
        if classification.is_atm_withdrawal and classification.duplicate_of is None:
            m.atm_withdrawal_count += 1
        if classification.is_ach and classification.duplicate_of is None:
            if t.amount >= 0:
                m.ach_credit_count += 1
            else:
                m.ach_debit_count += 1
        if classification.is_check and classification.duplicate_of is None:
            m.check_count += 1
        if classification.is_loan_payment and classification.duplicate_of is None:
            m.loan_count += 1
    m.total_deposits = round(m.total_deposits, 2)
    m.total_withdrawals = round(m.total_withdrawals, 2)
    m.lender_credits = round(m.lender_credits, 2)
    m.lender_debits = round(m.lender_debits, 2)
    m.monthly_lender_debits = m.lender_debits
    m.insurance_total = round(m.insurance_total, 2)
    m.lenders_detected = len(confirmed_entities)
    m.potential_lenders_detected = len(potential_entities)
    m.effective_total_deposits = m.total_deposits
    m.effective_total_withdrawals = m.total_withdrawals
    m.effective_num_deposits = m.num_deposits
    m.effective_num_withdrawals = m.num_withdrawals
    m.effective_nsf_count = m.nsf_count

    # Always compute the ADB working so the daily ledger and its validations are
    # available for audit, even when policy says not to report the figure.
    adb = compute_average_daily_balance(stmt, source_markdown=source_markdown)
    m.adb = adb
    m.calendar_day_count = adb.calendar_day_count
    m.daily_balance_sum = adb.daily_balance_sum
    m.adb_ok = adb.ok if adb.daily_balances else None
    for warning in adb.warnings:
        if warning not in m.notes:
            m.notes.append(warning)

    balances = {d.date: d.ending_balance for d in adb.daily_balances} if trust_running_balances else {}
    if balances:
        vals = list(balances.values())
        m.days_in_period = adb.calendar_day_count or len(vals)
        m.average_daily_balance = adb.average_daily_balance
        m.min_balance = round(min(vals), 2)
        m.max_balance = round(max(vals), 2)
        m.negative_days = sum(1 for v in vals if v < 0)
    elif m.stated_average_balance is None:
        if trust_running_balances:
            m.notes.append(
                "no average balance available: statement prints none and lacks dated "
                "running balances to compute one"
            )
        else:
            m.notes.append("not computing average balance from line items because reconciliation failed")
    else:
        m.days_in_period = stmt.days_in_period
        if trust_running_balances:
            m.notes.append("using the bank's printed average balance (no running balances to compute our own)")
        else:
            m.notes.append("using the bank's printed average balance because line-item balances did not reconcile")

    # Underwriting policy: report OUR computed ADB whenever the daily ledger
    # fully validates. Banks usually print an average COLLECTED balance, which
    # lags by float days and is not the same measure as average ledger balance
    # — comparing them is apples to oranges, and only the computed figure is
    # reproducible from the parsed statement. The printed figure is the fallback
    # for statements whose ledger cannot be validated, and is always still
    # available as `stated_average_balance` for cross-checking.
    if m.average_daily_balance is not None and m.adb_ok:
        m.average_balance = m.average_daily_balance
        m.average_balance_source = "computed_daily_ledger"
    elif m.stated_average_balance is not None:
        m.average_balance = m.stated_average_balance
        m.average_balance_source = "bank_stated"
    elif m.average_daily_balance is not None:
        m.average_balance = m.average_daily_balance
        m.average_balance_source = "computed_daily_ledger_unvalidated"

    if stmt.days_in_period is not None and m.days_in_period is None:
        m.days_in_period = stmt.days_in_period

    if trust_stated_summary is True:
        if stmt.stated_total_credits is not None:
            m.effective_total_deposits = round(stmt.stated_total_credits, 2)
            m.deposits_source = "bank_stated_reconciled"
        if stmt.stated_total_debits is not None:
            m.effective_total_withdrawals = _summary_debits_with_service_charge(stmt) or round(stmt.stated_total_debits, 2)
            m.withdrawals_source = "bank_stated_reconciled"
        if stmt.stated_credit_count is not None:
            m.effective_num_deposits = stmt.stated_credit_count
        if stmt.stated_debit_count is not None:
            m.effective_num_withdrawals = stmt.stated_debit_count
    elif trust_stated_summary is False and (
        stmt.stated_total_credits is not None or stmt.stated_total_debits is not None
    ):
        m.notes.append("ignored bank-stated deposit/debit totals because the summary did not reconcile")
    elif trust_stated_summary is None:
        if stmt.stated_total_credits is not None:
            m.effective_total_deposits = round(stmt.stated_total_credits, 2)
            m.deposits_source = "bank_stated_unverified"
        if stmt.stated_total_debits is not None:
            m.effective_total_withdrawals = round(stmt.stated_total_debits, 2)
            m.withdrawals_source = "bank_stated_unverified"
        if stmt.stated_credit_count is not None:
            m.effective_num_deposits = stmt.stated_credit_count
        if stmt.stated_debit_count is not None:
            m.effective_num_withdrawals = stmt.stated_debit_count

    if stmt.stated_nsf_count is not None and stmt.stated_nsf_count != m.nsf_count:
        m.notes.append(
            f"bank-stated NSF count {stmt.stated_nsf_count} differs from "
            f"{m.nsf_count} classified posted row(s); using the row count"
        )
    m.true_revenue = round(m.effective_total_deposits - m.lender_credits, 2)
    m.cash_flow = round(m.effective_total_deposits - m.effective_total_withdrawals, 2)
    m.eligible_deposits = m.true_revenue
    m.withholding_numerator = m.lender_debits
    m.withholding_denominator = m.eligible_deposits
    if m.withholding_denominator <= 0:
        m.withholding_review_required = True
        m.notes.append("withholding rate is unavailable because eligible deposits are zero or missing")
    else:
        m.withholding_rate = (
            abs(m.withholding_numerator) / m.withholding_denominator
        ) * 100
    return m

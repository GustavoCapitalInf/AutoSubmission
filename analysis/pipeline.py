"""Orchestrates the analysis stages: extract -> reconcile -> (escalate) ->
metrics -> detect. Extraction runs on the cheap flash-lite model; only a
statement that fails reconciliation is re-extracted with the stronger model."""
from __future__ import annotations
from dataclasses import dataclass
from .config import Settings, load_settings
from .schema import Statement
from .extract import extract_statement
from .reconcile import reconcile, ReconResult
from .metrics import compute_metrics, Metrics
from .detect import detect, DetectionResult
from .td_can import parse_td_canada_statement
from .bofa import parse_bofa_statement, repair_bofa_summary
from .regions import parse_regions_statement, repair_regions_summary
from .first_community import repair_first_community_posted_activity
from .bmo import parse_bmo_statement
from .capital_one import parse_capital_one_statement
from .chase import parse_chase_statement
from .farmers_merchants import parse_farmers_merchants_statement
from .rbc import parse_rbc_statement
from .scotia import parse_scotiabank_statement
from .wells import parse_wells_statement
from .bank_repairs import (
    repair_b1_beginning_balance,
    repair_capital_one_running_amount,
    repair_chase_remote_deposit_count_column,
    repair_regions_transactions,
    repair_santander_signs_from_balances,
    repair_scotiabank_misc_payment_sign,
    repair_single_row_signs_from_balances,
    repair_truist_converted_checks,
)


def normalize_statement(stmt: Statement) -> Statement:
    """Remove rows the extractor occasionally misclassifies as transactions."""
    transactions = []
    for t in stmt.transactions:
        desc = t.description.strip().upper()
        amount = round(t.amount, 2)
        balance = round(t.running_balance, 2) if t.running_balance is not None else None
        is_daily_balance = desc.startswith(("DAILY BALANCE", "DAILY BALANCE SUMMARY")) and (
            amount == 0.0 or balance is not None
        )
        is_balance_marker = desc.startswith((
            "BEGINNING BALANCE",
            "BALANCE FORWARD",
            "BALANCE BROUGHT FORWARD",
            "OPENING BALANCE",
            "CLOSING BALANCE",
        )) and (
            (balance is not None and amount == balance)
            or (stmt.beginning_balance is not None and amount == round(stmt.beginning_balance, 2))
            or (stmt.ending_balance is not None and amount == round(stmt.ending_balance, 2))
        )
        if is_daily_balance or is_balance_marker:
            continue
        transactions.append(t)
    if len(transactions) == len(stmt.transactions):
        return stmt
    return stmt.model_copy(update={"transactions": transactions})


def apply_statement_repairs(markdown: str, stmt: Statement) -> Statement:
    stmt = repair_bofa_summary(markdown, stmt)
    stmt = repair_regions_summary(markdown, stmt)
    stmt = repair_first_community_posted_activity(stmt)
    stmt = repair_b1_beginning_balance(stmt)
    stmt = repair_capital_one_running_amount(stmt)
    stmt = repair_chase_remote_deposit_count_column(stmt)
    stmt = repair_regions_transactions(markdown, stmt)
    stmt = repair_truist_converted_checks(stmt)
    stmt = repair_santander_signs_from_balances(stmt)
    stmt = repair_scotiabank_misc_payment_sign(stmt)
    stmt = repair_single_row_signs_from_balances(stmt)
    return normalize_statement(stmt)


@dataclass
class Quality:
    level: str
    transaction_detail_reliable: bool
    summary_totals_reliable: bool
    aggregate_rows: int = 0
    corporate_use: str = "review"
    notes: list[str] | None = None


@dataclass
class Report:
    statement: Statement
    reconciliation: ReconResult
    metrics: Metrics
    detection: DetectionResult
    quality: Quality
    model_used: str
    escalated: bool


def assess_quality(stmt: Statement, recon: ReconResult) -> Quality:
    aggregate_rows = sum(1 for t in stmt.transactions if "UNCAPTURED" in t.description.upper())
    notes: list[str] = []
    if aggregate_rows:
        notes.append(
            "transaction list includes bank-summary aggregate rows for activity not available as individual postings"
        )
    if not recon.ok and recon.summary_ok is True:
        notes.append(
            "bank summary reconciles, but transaction-level detail is incomplete or internally inconsistent"
        )
        if recon.credit_coverage is not None and (recon.credit_coverage < 0.98 or recon.credit_coverage > 1.02):
            notes.append("captured credit line items do not match the bank-stated credit total")
        if recon.debit_coverage is not None and (recon.debit_coverage < 0.98 or recon.debit_coverage > 1.02):
            notes.append("captured debit line items do not match the bank-stated debit total")
    if recon.ok and aggregate_rows == 0:
        return Quality(
            level="transaction_level",
            transaction_detail_reliable=True,
            summary_totals_reliable=recon.summary_ok is not False,
            corporate_use="approved",
            notes=notes,
        )
    if recon.ok and aggregate_rows:
        return Quality(
            level="summary_aggregate",
            transaction_detail_reliable=False,
            summary_totals_reliable=recon.summary_ok is True,
            aggregate_rows=aggregate_rows,
            corporate_use="summary_only",
            notes=notes,
        )
    if recon.summary_ok is True:
        return Quality(
            level="summary_trusted",
            transaction_detail_reliable=False,
            summary_totals_reliable=True,
            aggregate_rows=aggregate_rows,
            corporate_use="summary_only",
            notes=notes,
        )
    return Quality(
        level="needs_review",
        transaction_detail_reliable=False,
        summary_totals_reliable=False,
        aggregate_rows=aggregate_rows,
        corporate_use="manual_review_required",
        notes=notes,
    )


def analyze_markdown(markdown: str, *, settings: Settings | None = None) -> Report:
    settings = settings or load_settings()

    model_used = settings.model
    deterministic_stmt = (
        parse_td_canada_statement(markdown)
        or parse_rbc_statement(markdown)
        or parse_scotiabank_statement(markdown)
        or parse_wells_statement(markdown)
        or parse_bofa_statement(markdown)
        or parse_regions_statement(markdown)
        or parse_farmers_merchants_statement(markdown)
        or parse_bmo_statement(markdown)
        or parse_capital_one_statement(markdown)
        or parse_chase_statement(markdown)
    )
    if deterministic_stmt is not None:
        stmt = apply_statement_repairs(markdown, normalize_statement(deterministic_stmt))
        bank_label = (stmt.bank or "bank").lower().replace(" ", "-")
        model_used = f"{bank_label}-deterministic"
    else:
        stmt = normalize_statement(extract_statement(markdown, settings=settings, model=model_used))
        stmt = apply_statement_repairs(markdown, stmt)
    recon = reconcile(stmt)

    escalated = False
    # Cheap model's mistakes surface as reconciliation failures — re-extract those
    # with the stronger model before trusting the numbers. On small-bank / image
    # statements the line items are often incomplete (coverage always fails), so
    # what matters most is a SELF-RECONCILING SUMMARY: escalate whenever the summary
    # is inconsistent (or fully clean), and prefer whichever extraction's summary
    # reconciles, falling back to fewer overall issues.
    needs_escalation = not recon.ok and (recon.summary_ok is not True)
    if deterministic_stmt is None and needs_escalation and settings.escalation_model != settings.model:
        try:
            alt = normalize_statement(extract_statement(markdown, settings=settings, model=settings.escalation_model))
            alt = apply_statement_repairs(markdown, alt)
            alt_recon = reconcile(alt)
            better_summary = bool(alt_recon.summary_ok) and not recon.summary_ok
            fewer_issues = alt_recon.summary_ok == recon.summary_ok and len(alt_recon.issues) < len(recon.issues)
            if alt_recon.ok or better_summary or fewer_issues:
                stmt, recon, model_used, escalated = alt, alt_recon, settings.escalation_model, True
        except Exception as e:
            recon.issues.append(
                f"escalation extraction failed ({type(e).__name__}); using primary extraction with review guards"
            )

    metrics = compute_metrics(
        stmt,
        trust_stated_summary=recon.summary_ok,
        trust_running_balances=recon.ok and not any("UNCAPTURED" in t.description.upper() for t in stmt.transactions),
    )
    quality = assess_quality(stmt, recon)
    if quality.level == "summary_aggregate":
        metrics.notes = [
            note for note in metrics.notes
            if note != "not computing average balance from line items because reconciliation failed"
        ]
        if "not computing average balance from aggregate-backed transaction detail" not in metrics.notes:
            metrics.notes.append("not computing average balance from aggregate-backed transaction detail")
    if quality.notes:
        for note in quality.notes:
            if note not in metrics.notes:
                metrics.notes.append(note)

    return Report(
        statement=stmt,
        reconciliation=recon,
        metrics=metrics,
        detection=detect(stmt),
        quality=quality,
        model_used=model_used,
        escalated=escalated,
    )

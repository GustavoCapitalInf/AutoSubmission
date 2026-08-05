"""Orchestrates the analysis stages: extract -> reconcile -> (escalate) ->
metrics -> detect. Extraction runs on the cheap flash-lite model; only a
statement that fails reconciliation is re-extracted with the stronger model."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from .config import Settings, load_settings
from .schema import Statement
from .dates import assign_transaction_years
from .extract import ExtractionAttempt, extract_statement
from .grounding import SourceValidation, parser_validated_source, validate_generic_source
from .reconcile import reconcile, ReconResult
from .metrics import compute_metrics, Metrics
from .detect import detect, DetectionResult
from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
)
from .parser_registry import parse_deterministic_statement
from .td_can import _parse_money
from .bofa import repair_bofa_summary
from .regions import repair_regions_summary
from .first_community import repair_first_community_posted_activity
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
    # Statement periods that cross a year boundary: parsers stamp one year on
    # every MM/DD row, so re-derive the year from the period before anything
    # chronological (ADB, daily ledger) is built on these dates.
    stmt = assign_transaction_years(stmt)
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
class DocumentIntegrity:
    risk_level: str
    flags: list[str]
    notes: list[str]
    possible_document_issue: bool = False


@dataclass
class Report:
    statement: Statement
    reconciliation: ReconResult
    metrics: Metrics
    detection: DetectionResult
    quality: Quality
    integrity: DocumentIntegrity
    model_used: str
    escalated: bool
    classifications: list[TransactionClassification] = field(default_factory=list)
    extraction_attempts: list[ExtractionAttempt] = field(default_factory=list)
    source_validation: SourceValidation = field(default_factory=parser_validated_source)


def assess_quality(stmt: Statement, recon: ReconResult) -> Quality:
    aggregate_rows = sum(1 for t in stmt.transactions if "UNCAPTURED" in t.description.upper())
    notes: list[str] = []
    if stmt.account_selection_status == "ambiguous":
        notes.append("multiple source accounts could not be isolated into one unambiguous ledger")
        return Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=False,
            aggregate_rows=aggregate_rows,
            corporate_use="manual_review_required",
            notes=notes,
        )
    if stmt.bank == "Chase Transaction Export":
        notes.append("Chase for Business transaction export lacks a formal statement summary/period")
        return Quality(
            level="needs_review",
            transaction_detail_reliable=recon.ok,
            summary_totals_reliable=False,
            aggregate_rows=aggregate_rows,
            corporate_use="manual_review_required",
            notes=notes,
        )
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
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=True,
            aggregate_rows=aggregate_rows,
            corporate_use="manual_review_required",
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


def _bmo_summary_contradictions(markdown: str, stmt: Statement) -> list[str]:
    if (stmt.bank or "").upper() != "BMO":
        return []
    text = " ".join(markdown.split())

    contradictions: list[str] = []
    secondary = re.search(
        r"Account Summary Totals\s+(.*?)(?:Important Information|Page 2 of 2|$)",
        text,
        re.IGNORECASE,
    )
    secondary_text = secondary.group(1) if secondary else ""

    def secondary_amount(label: str) -> float | None:
        if not secondary_text:
            return None
        m = re.search(
            label + r"\s+\$?\s*(-?\d[\d,]*\.\d{2})",
            secondary_text,
            re.IGNORECASE,
        )
        if not m:
            return None
        return _parse_money(m.group(1))

    page_total_deposits = secondary_amount(r"Total Deposits")
    if (
        stmt.stated_total_credits is not None
        and page_total_deposits is not None
        and abs(stmt.stated_total_credits - page_total_deposits) > 0.01
    ):
        contradictions.append(
            "conflicting bank-stated deposit totals across summary sections"
        )

    page_total_withdrawals = secondary_amount(r"Total Withdrawals")
    page_interest = secondary_amount(r"Interest Earned")
    page_fees = secondary_amount(r"Service Fees")
    page_final = secondary_amount(r"Final Balance")
    if (
        stmt.beginning_balance is not None
        and page_total_deposits is not None
        and page_total_withdrawals is not None
        and page_final is not None
    ):
        base = (
            stmt.beginning_balance
            + page_total_deposits
            - page_total_withdrawals
            + (page_interest or 0.0)
        )
        # Some statements include fees in withdrawals; others list them separately.
        residuals = [base - page_final]
        if page_fees is not None:
            residuals.append(base - page_fees - page_final)
        if min(abs(residual) for residual in residuals) > 1.0:
            contradictions.append(
                "secondary bank-stated summary does not reconcile to the opening and final balances"
            )
    return contradictions


def assess_document_integrity(
    stmt: Statement,
    recon: ReconResult,
    quality: Quality,
    *,
    markdown: str = "",
    source_validation: SourceValidation | None = None,
) -> DocumentIntegrity:
    flags: list[str] = []
    notes: list[str] = []

    if stmt.account_selection_status == "ambiguous":
        flags.append("ambiguous_account_selection")
        notes.append("the document contains multiple accounts and no unique account ledger was selected")
    elif (
        stmt.document_account_count is not None
        and stmt.document_account_count > 1
        and stmt.account_selection_status == "selected_primary"
    ):
        flags.append("multiple_accounts_present")
        notes.append("metrics are scoped to the selected primary account; other document accounts were excluded")
    if source_validation is not None and not source_validation.ok:
        flags.append("generic_source_grounding_failed")
        notes.extend(source_validation.notes)

    if recon.summary_ok is False:
        flags.append("summary_math_inconsistent")
        notes.append("bank-stated summary totals do not reconcile to beginning and ending balances")
    if recon.sum_delta is not None and abs(recon.sum_delta) > 1.0:
        flags.append("ledger_sum_mismatch")
        notes.append("transaction sum does not reconcile to the printed ending balance")
    if recon.continuity_breaks:
        flags.append("running_balance_breaks")
        notes.append(f"{recon.continuity_breaks} printed running-balance continuity break(s) detected")
    if recon.credit_coverage is not None and (recon.credit_coverage < 0.98 or recon.credit_coverage > 1.02):
        flags.append("credit_detail_coverage_mismatch")
        notes.append("line-item credits do not match the bank-stated credit total")
    if recon.debit_coverage is not None and (recon.debit_coverage < 0.98 or recon.debit_coverage > 1.02):
        flags.append("debit_detail_coverage_mismatch")
        notes.append("line-item debits do not match the bank-stated debit total")
    if quality.level in {"summary_aggregate", "summary_trusted"} or (
        quality.summary_totals_reliable and not quality.transaction_detail_reliable
    ):
        flags.append("transaction_detail_not_corporate_reliable")
        notes.append("summary figures may be usable, but transaction-level detail is not reliable enough for corporate approval")
    if stmt.bank == "Chase Transaction Export":
        flags.append("not_a_formal_statement")
        notes.append("document is a Chase online transaction export, not a complete bank statement")
    contradictions = _bmo_summary_contradictions(markdown, stmt) if markdown else []
    if contradictions:
        flags.append("conflicting_statement_summaries")
        notes.extend(contradictions)
    declared_pages = [
        (int(current), int(total))
        for current, total in re.findall(
            r"\bPage\s*:?\s*(\d+)\s+of\s+(\d+)\b",
            markdown,
            re.IGNORECASE,
        )
    ]
    if declared_pages:
        declared_total = max(total for _, total in declared_pages)
        present = {current for current, total in declared_pages if total == declared_total}
        missing = sorted(set(range(1, declared_total + 1)) - present)
        if missing:
            flags.append("missing_declared_statement_page")
            notes.append(
                "statement declares "
                f"{declared_total} bank page(s), but page label(s) "
                f"{', '.join(str(page) for page in missing)} are absent from the supplied PDF"
            )

    unique_flags = list(dict.fromkeys(flags))
    unique_notes = list(dict.fromkeys(notes))
    possible_document_issue = (
        stmt.account_selection_status == "ambiguous"
        or recon.summary_ok is False
        or recon.continuity_breaks >= 3
        or bool(contradictions)
        or (
            quality.level == "summary_trusted"
            and recon.continuity_breaks > 0
            and any("coverage_mismatch" in flag for flag in unique_flags)
        )
    )
    if possible_document_issue:
        risk_level = "high"
    elif unique_flags:
        risk_level = "review"
    else:
        risk_level = "clear"

    return DocumentIntegrity(
        risk_level=risk_level,
        flags=unique_flags,
        notes=unique_notes,
        possible_document_issue=possible_document_issue,
    )


def _deterministic_statement(markdown: str) -> Statement | None:
    return parse_deterministic_statement(markdown)


def analyze_markdown(
    markdown: str,
    *,
    settings: Settings | None = None,
    parse_mode: str = "auto",
    external_attempt_budget: int | None = None,
) -> Report:
    settings = settings or load_settings()
    if parse_mode not in {"auto", "deterministic"}:
        raise ValueError(f"unknown parse_mode: {parse_mode}")

    model_used = settings.model
    extraction_attempts: list[ExtractionAttempt] = []
    attempt_limit = settings.max_external_extraction_attempts
    if external_attempt_budget is not None:
        attempt_limit = max(0, min(attempt_limit, external_attempt_budget))
    deterministic_stmt = _deterministic_statement(markdown)
    if deterministic_stmt is not None:
        stmt = apply_statement_repairs(markdown, normalize_statement(deterministic_stmt))
        bank_label = (stmt.bank or "bank").lower().replace(" ", "-")
        model_used = f"{bank_label}-deterministic"
    else:
        if parse_mode == "deterministic":
            raise RuntimeError("no deterministic parser matched this statement")
        if attempt_limit == 0:
            raise RuntimeError(
                "external extraction budget exhausted; no deterministic parser matched this statement"
            )
        stmt = normalize_statement(
            extract_statement(
                markdown,
                settings=settings,
                model=model_used,
                attempt_sink=extraction_attempts.append,
            )
        )
        stmt = apply_statement_repairs(markdown, stmt)
    recon = reconcile(stmt)
    source_validation = (
        parser_validated_source()
        if deterministic_stmt is not None
        else validate_generic_source(stmt, markdown)
    )

    escalated = False
    # Cheap-model mistakes surface through arithmetic or source-grounding
    # failures. Permit one stronger extraction inside the document-wide budget,
    # then prefer grounded output before comparing reconciliation quality.
    needs_escalation = (
        (not recon.ok and recon.summary_ok is not True)
        or not source_validation.ok
    )
    if (
        deterministic_stmt is None
        and needs_escalation
        and settings.escalation_model != settings.model
        and len(extraction_attempts) < attempt_limit
    ):
        try:
            alt = normalize_statement(
                extract_statement(
                    markdown,
                    settings=settings,
                    model=settings.escalation_model,
                    attempt_sink=extraction_attempts.append,
                )
            )
            alt = apply_statement_repairs(markdown, alt)
            alt_recon = reconcile(alt)
            alt_source_validation = validate_generic_source(alt, markdown)
            better_grounding = alt_source_validation.ok and not source_validation.ok
            better_summary = bool(alt_recon.summary_ok) and not recon.summary_ok
            fewer_issues = alt_recon.summary_ok == recon.summary_ok and len(alt_recon.issues) < len(recon.issues)
            equally_grounded = alt_source_validation.ok == source_validation.ok
            if better_grounding or (
                equally_grounded and (alt_recon.ok or better_summary or fewer_issues)
            ):
                stmt, recon, model_used, escalated = alt, alt_recon, settings.escalation_model, True
                source_validation = alt_source_validation
        except Exception as e:
            recon.issues.append(
                f"escalation extraction failed ({type(e).__name__}); using primary extraction with review guards"
            )

    classifications = classify_statement_transactions(stmt)
    metrics = compute_metrics(
        stmt,
        trust_stated_summary=recon.summary_ok,
        trust_running_balances=recon.ok and not any("UNCAPTURED" in t.description.upper() for t in stmt.transactions),
        # the source text lets the ADB engine prove the parser did not fold
        # several posting dates into one
        source_markdown=markdown,
        classifications=classifications,
        withholding_denominator_mode=settings.withholding_denominator_mode,
    )
    quality = assess_quality(stmt, recon)
    if not source_validation.ok:
        quality = Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=False,
            aggregate_rows=quality.aggregate_rows,
            corporate_use="manual_review_required",
            notes=list(dict.fromkeys((quality.notes or []) + source_validation.notes)),
        )
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
    integrity = assess_document_integrity(
        stmt,
        recon,
        quality,
        markdown=markdown,
        source_validation=source_validation,
    )
    if integrity.possible_document_issue and quality.corporate_use != "approved":
        quality = Quality(
            level="needs_review",
            transaction_detail_reliable=False,
            summary_totals_reliable=False,
            aggregate_rows=quality.aggregate_rows,
            corporate_use="manual_review_required",
            notes=(quality.notes or []) + ["document integrity issue prevents automated corporate approval"],
        )
    if integrity.possible_document_issue:
        note = "document integrity review recommended; inconsistent source data can be a fraud-risk signal but is not proof of fraud"
        if note not in metrics.notes:
            metrics.notes.append(note)

    return Report(
        statement=stmt,
        reconciliation=recon,
        metrics=metrics,
        detection=detect(
            stmt,
            classifications=classifications,
            eligible_deposits=metrics.eligible_deposits,
        ),
        quality=quality,
        integrity=integrity,
        model_used=model_used,
        escalated=escalated,
        classifications=classifications,
        extraction_attempts=extraction_attempts,
        source_validation=source_validation,
    )

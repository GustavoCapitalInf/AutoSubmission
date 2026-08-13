"""Orchestrates the analysis stages: extract -> reconcile -> (escalate) ->
metrics -> detect. Extraction runs on the cheap flash-lite model; only a
statement that fails reconciliation is re-extracted with the stronger model."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Callable
from .config import Settings, load_settings
from .count_semantics import counts_comparable
from .schema import Statement
from .dates import assign_transaction_years
from .extract import extract_statement
from .reconcile import reconcile, ReconResult
from .metrics import compute_metrics, Metrics
from .detect import detect, DetectionResult
from .transaction_classifier import (
    TransactionClassification,
    classify_statement_transactions,
)
from .bofa import repair_bofa_summary
from .regions import repair_regions_summary
from .first_community import repair_first_community_posted_activity
from .parser_registry import (
    AmbiguousParserError,
    Dispatch,
    ParserCrashError,
    Registration,
    by_bank_label,
    resolve,
    run_integrity_checks,
)
from . import parser_registry_entries as _parser_registry_entries  # noqa: F401  - populates the registry
from .structurer import STRUCTURER_MODEL, structure_unclaimed
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


def _registration_for(stmt: Statement, dispatch: Dispatch | None) -> Registration | None:
    """The parser whose knowledge applies to this statement.

    The claiming registration when one exists. Otherwise the registration whose
    bank label matches - an LLM extraction that named a bank we do have a
    parser for still gets that parser's document knowledge, which is what the
    pre-R-3 `stmt.bank == ...` literals gave it.
    """
    if dispatch is not None and dispatch.registration is not None:
        return dispatch.registration
    return by_bank_label(stmt.bank)


def assess_quality(
    stmt: Statement, recon: ReconResult, *, dispatch: Dispatch | None = None
) -> Quality:
    aggregate_rows = sum(1 for t in stmt.transactions if "UNCAPTURED" in t.description.upper())
    notes: list[str] = []
    registration = _registration_for(stmt, dispatch)
    if registration is not None and not registration.formal_statement:
        notes.append(registration.informal_quality_note)
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


def assess_document_integrity(
    stmt: Statement,
    recon: ReconResult,
    quality: Quality,
    *,
    markdown: str = "",
    dispatch: Dispatch | None = None,
) -> DocumentIntegrity:
    flags: list[str] = []
    notes: list[str] = []

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
    registration = _registration_for(stmt, dispatch)
    if registration is not None and not registration.formal_statement:
        flags.append("not_a_formal_statement")
        notes.append(registration.informal_integrity_note)
    # The bank printed a per-direction COUNT and we captured rows; did they
    # agree? Computed in reconcile (no issue appended, so `recon.ok` and the
    # ADB are untouched) and made a consequence here, where it is a flag and
    # never a refusal. Three gates, all required:
    #
    #   `formal`        — a count on a document class that is not a bank
    #                     statement is not a finding.
    #   `counts_comparable` — the printed figure must denote the same set of
    #                     rows `direction` does. A parser absent from
    #                     `analysis/count_semantics.py` is UNSURVEYED, which is
    #                     not comparable, so a NEW registration emits nothing
    #                     until its printed summary has been read. That default
    #                     is structural: this check can only get quieter when
    #                     the registry grows.
    #   `is False`      — load-bearing, not style: `None` is not-applicable
    #                     (no printed count, or aggregate-backed rows), and
    #                     `not None` would flag every document that never ran
    #                     the check.
    #
    # Keyed on the CLAIMING parser only: `_registration_for` also resolves by
    # bank label for LLM extractions, and a semantics entry is evidence about
    # what one parser's reader produced, not about the bank's paper.
    formal = registration is None or registration.formal_statement
    claiming = dispatch.parser_id if dispatch is not None and dispatch.outcome == "claimed" else None
    if formal and counts_comparable(claiming, "credit") and recon.stated_credit_count_matches is False:
        flags.append("credit_count_mismatch")
        notes.append("captured credit rows do not match the bank-stated credit count")
    if formal and counts_comparable(claiming, "debit") and recon.stated_debit_count_matches is False:
        flags.append("debit_count_mismatch")
        notes.append("captured debit rows do not match the bank-stated debit count")
    if dispatch is not None and dispatch.outcome == "ambiguous":
        flags.append("parser_ambiguous")
        notes.append(
            "more than one deterministic parser claimed this document ("
            + ", ".join(name for name, _score in dispatch.candidates)
            + "); routed to review rather than resolved by guesswork"
        )
    if dispatch is not None and dispatch.outcome == "parser_exception":
        flags.append("parser_exception")
        notes.append(
            "a deterministic parser raised on this document ("
            + ", ".join(dispatch.crashed)
            + "); routed to review rather than reported as unrecognised"
        )
    contradictions: list[str] = []
    if markdown and registration is not None:
        contradictions, check_failures = run_integrity_checks(registration, markdown, stmt)
        for failure in check_failures:
            flags.append("integrity_check_exception")
            notes.append(
                f"a registered document-integrity check raised ({failure.parser_id}: "
                f"{failure.exception}); its finding is unavailable, so the document is "
                "routed to review rather than reported as clear"
            )
    if contradictions:
        flags.append("conflicting_statement_summaries")
        notes.extend(contradictions)
    # `CONTINUED ON NEXT PAGE` is a continuation footer, not a page
    # declaration. Banks print it immediately above the page number, and PDF
    # flattening joins the two lines, so "…NEXT PAGE" + "2 of 20" reads as
    # "Page 2 of 20" to a pattern that only looks for the word.
    #
    # RESTRICTION-ONLY PROPERTY, and the reason this hunk is safe: a negative
    # lookbehind can only REMOVE matches from the set the pattern found
    # before, never add one. `declared_pages` can therefore only shrink, so
    # `missing_declared_statement_page` can only be withdrawn from a document
    # that carried it — this change cannot raise the flag on any document that
    # did not already have it, and cannot move a validated document to review.
    declared_pages = [
        (int(current), int(total))
        for current, total in re.findall(
            r"(?<!NEXT )\bPage\s*:?\s*(\d+)\s+of\s+(\d+)\b",
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
        recon.summary_ok is False
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


def analyze_markdown(markdown: str, *, settings: Settings | None = None,
                     parse_mode: str = "auto",
                     document_geometry: object | None = None,
                     on_dispatch: Callable[[Dispatch], None] | None = None) -> Report:
    settings = settings or load_settings()
    if parse_mode not in {"auto", "deterministic"}:
        raise ValueError(f"unknown parse_mode: {parse_mode}")

    model_used = settings.model
    dispatch = resolve(markdown)
    if on_dispatch is not None:
        # H-3 telemetry seam: write-only side-band, nothing here is read back.
        # The callback's contract is "must not raise, must not mutate", and it
        # is discharged on the telemetry side (telemetry/collect.py) rather
        # than by a try/except here — swallowing exceptions inside this module
        # would be new control flow in the orchestrator to cover a defect in an
        # observer.
        #
        # Deliberately a callback and NOT a `Dispatch` field on `Report`:
        # `Dispatch.statement` is the parsed Statement — every amount and
        # description — so hanging it off `Report` would put the full financial
        # record one generic `asdict()` away from anything that walks a report.
        # Telemetry projects ids and scores out of `dispatch` and stores
        # nothing else. Do not "simplify" this into a Report field.
        on_dispatch(dispatch)
    deterministic_stmt = dispatch.statement
    # W3-3c: the generic structurer is a fallback on the UNCLAIMED branch. It
    # never competes with a claiming parser, and it is deliberately not reached
    # for `ambiguous` or `parser_exception`, which have their own fail-closed
    # outcomes: structuring either would bury a finding a human must see under
    # a plausible-looking answer. Off unless GENERIC_STRUCTURER_ENABLED is set,
    # and it returns None rather than raising, so this line cannot change any
    # existing behaviour until the opt-in is flipped.
    structured_stmt = (
        structure_unclaimed(markdown, geometry=document_geometry)
        if deterministic_stmt is None and dispatch.outcome == "unclaimed"
        else None
    )
    if deterministic_stmt is not None:
        stmt = apply_statement_repairs(markdown, normalize_statement(deterministic_stmt))
        bank_label = (stmt.bank or "bank").lower().replace(" ", "-")
        model_used = f"{bank_label}-deterministic"
    elif structured_stmt is not None:
        # No `apply_statement_repairs`: its repairs are bank-specific and this
        # branch is where no bank was identified. The one correction the
        # structurer needs (assign_transaction_years) already ran inside the
        # subsystem, BEFORE grounding, so the date grounding accepted is the
        # date that ships.
        stmt = normalize_statement(structured_stmt)
        model_used = STRUCTURER_MODEL
    else:
        if dispatch.outcome == "ambiguous" and parse_mode == "deterministic":
            raise AmbiguousParserError(dispatch.candidates)
        if dispatch.outcome == "parser_exception" and parse_mode == "deterministic":
            # Not "no parser matched": that would file our own defect as a gap
            # in our layout knowledge, in the one report a human reads.
            raise ParserCrashError(dispatch.exceptions)
        if parse_mode == "deterministic":
            raise RuntimeError("no deterministic parser matched this statement")
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
    quality = assess_quality(stmt, recon, dispatch=dispatch)
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
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown, dispatch=dispatch)
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
    )

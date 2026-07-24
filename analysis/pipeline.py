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


@dataclass
class Report:
    statement: Statement
    reconciliation: ReconResult
    metrics: Metrics
    detection: DetectionResult
    model_used: str
    escalated: bool


def analyze_markdown(markdown: str, *, settings: Settings | None = None) -> Report:
    settings = settings or load_settings()

    model_used = settings.model
    stmt = extract_statement(markdown, settings=settings, model=model_used)
    recon = reconcile(stmt)

    escalated = False
    # Cheap model's mistakes surface as reconciliation failures — re-extract those
    # with the stronger model before trusting the numbers. On small-bank / image
    # statements the line items are often incomplete (coverage always fails), so
    # what matters most is a SELF-RECONCILING SUMMARY: escalate whenever the summary
    # is inconsistent (or fully clean), and prefer whichever extraction's summary
    # reconciles, falling back to fewer overall issues.
    needs_escalation = not recon.ok and (recon.summary_ok is not True)
    if needs_escalation and settings.escalation_model != settings.model:
        alt = extract_statement(markdown, settings=settings, model=settings.escalation_model)
        alt_recon = reconcile(alt)
        better_summary = bool(alt_recon.summary_ok) and not recon.summary_ok
        fewer_issues = alt_recon.summary_ok == recon.summary_ok and len(alt_recon.issues) < len(recon.issues)
        if alt_recon.ok or better_summary or fewer_issues:
            stmt, recon, model_used, escalated = alt, alt_recon, settings.escalation_model, True

    return Report(
        statement=stmt,
        reconciliation=recon,
        metrics=compute_metrics(stmt),
        detection=detect(stmt),
        model_used=model_used,
        escalated=escalated,
    )

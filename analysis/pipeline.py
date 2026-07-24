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
    # (and only those) with the stronger model before trusting the numbers.
    if not recon.ok and settings.escalation_model != settings.model:
        alt = extract_statement(markdown, settings=settings, model=settings.escalation_model)
        alt_recon = reconcile(alt)
        # Keep the escalated result if it reconciles, or at least isn't worse.
        if alt_recon.ok or len(alt_recon.issues) < len(recon.issues):
            stmt, recon, model_used, escalated = alt, alt_recon, settings.escalation_model, True

    return Report(
        statement=stmt,
        reconciliation=recon,
        metrics=compute_metrics(stmt),
        detection=detect(stmt),
        model_used=model_used,
        escalated=escalated,
    )

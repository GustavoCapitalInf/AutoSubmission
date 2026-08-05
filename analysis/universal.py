"""The universal ("any bank") statement path.

A never-before-seen layout has no deterministic parser, so something has to turn
its markdown into a `Statement`. This module owns that step and nothing else:

    document -> markdown -> [structurer fills Statement] -> reconcile -> gate

The structurer may only fill the schema in `analysis/schema.py`. It never
computes a total, an average, a rate or an approval; `analysis.reconcile` and the
corporate approval gate in `analysis.pipeline` decide whether the result can be
trusted, exactly as they do for a certified per-bank parser. When structuring
fails, or when the gate fails, the outcome is manual review with a stated
reason — never a plausible estimate.

Vendor structuring is opt-in. `PROJECT_GOAL.md` requires the production path to
stay at negligible marginal cost and to route an unsupported format to review
rather than to a paid call, so `allow_vendor_structurer` defaults to False: an
unknown layout with no local structurer configured comes back as manual review
without any vendor request.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from .config import Settings, load_settings
from .extract import extract_statement
from .pipeline import (
    Report,
    analyze_markdown,
    apply_statement_repairs,
    build_report,
    deterministic_statement,
    normalize_statement,
)
from .reconcile import ReconResult, reconcile
from .schema import Statement

# Document source labels, so a review queue can tell a scan from a digital PDF.
NATIVE_TEXT = "native_pdf_text"
OCR_MARKDOWN = "ocr_markdown"
PROVIDED_MARKDOWN = "provided_markdown"

# Routes.
DETERMINISTIC = "deterministic"
UNIVERSAL = "universal"
UNSTRUCTURED = "unstructured"

MANUAL_REVIEW = "manual_review_required"

_MAX_FEEDBACK_ISSUES = 8


@runtime_checkable
class StatementStructurer(Protocol):
    """Fills `Statement` from statement markdown. Computes nothing."""

    name: str

    def __call__(self, markdown: str, *, feedback: str | None = None) -> Statement:
        ...


def _accepts_feedback(fn: Callable[..., object]) -> bool:
    try:
        parameters = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    if "feedback" in parameters:
        return True
    return any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )


@dataclass(frozen=True)
class CallableStructurer:
    """Wrap any callable as a named structurer (local models, replay, tests)."""

    name: str
    fn: Callable[..., Statement]

    def __call__(self, markdown: str, *, feedback: str | None = None) -> Statement:
        if _accepts_feedback(self.fn):
            return self.fn(markdown, feedback=feedback)
        return self.fn(markdown)


@dataclass(frozen=True)
class GeminiStructurer:
    """Vendor structurer. Opt-in only; it still has to clear the frozen gate."""

    model: str
    settings: Settings | None = None

    @property
    def name(self) -> str:
        return f"gemini:{self.model}"

    def __call__(self, markdown: str, *, feedback: str | None = None) -> Statement:
        return extract_statement(
            markdown,
            settings=self.settings,
            model=self.model,
            extra_instructions=feedback,
        )


def default_structurers(
    settings: Settings | None = None,
    *,
    allow_vendor_structurer: bool = False,
) -> tuple[StatementStructurer, ...]:
    """The structuring ladder for unknown layouts.

    Empty by default: with no local structuring model deployed, the zero-vendor
    cost path routes an unknown layout to review instead of paying per document.
    """
    if not allow_vendor_structurer:
        return ()
    settings = settings or load_settings()
    models = [settings.model]
    if settings.escalation_model and settings.escalation_model != settings.model:
        models.append(settings.escalation_model)
    return tuple(GeminiStructurer(model=model, settings=settings) for model in models)


@dataclass(frozen=True)
class StructuringAttempt:
    """One structuring attempt and how the reconciliation gate judged it."""

    stage: str
    backend: str
    parsed: bool
    accepted: bool
    reconciled: bool = False
    summary_reconciled: bool | None = None
    issue_count: int = 0
    transaction_count: int = 0
    error: str | None = None


@dataclass
class UniversalStructureResult:
    statement: Statement | None = None
    reconciliation: ReconResult | None = None
    backend_used: str | None = None
    escalated: bool = False
    attempts: list[StructuringAttempt] = field(default_factory=list)
    manual_review_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.statement is not None


def _feedback_for(recon: ReconResult) -> str | None:
    if not recon.issues:
        return None
    return "\n".join(f"- {issue}" for issue in recon.issues[:_MAX_FEEDBACK_ISSUES])


def _is_better(candidate: ReconResult, incumbent: ReconResult | None) -> bool:
    """The pipeline's escalation preference, applied to any structuring backend."""
    if incumbent is None:
        return True
    if candidate.ok:
        return True
    if bool(candidate.summary_ok) and not incumbent.summary_ok:
        return True
    return (
        candidate.summary_ok == incumbent.summary_ok
        and len(candidate.issues) < len(incumbent.issues)
    )


def structure_statement(
    markdown: str,
    *,
    structurers: tuple[StatementStructurer, ...] | list[StatementStructurer],
    settings: Settings | None = None,
) -> UniversalStructureResult:
    """Fill `Statement` from markdown, escalating on reconciliation failure.

    Walks the backends in order and keeps the best-reconciling attempt. Stops as
    soon as an attempt fully reconciles, or as soon as the bank's own stated
    summary reconciles (the point past which a stronger model adds no trust —
    the same rule `analyze_markdown` already uses). Every attempt is recorded.
    """
    result = UniversalStructureResult()
    if not structurers:
        result.manual_review_reason = (
            "no deterministic parser matched and no statement structurer is "
            "configured for unknown layouts"
        )
        return result

    feedback: str | None = None
    for index, structurer in enumerate(structurers):
        stage = "primary" if index == 0 else f"escalation_{index}"
        backend = getattr(structurer, "name", None) or type(structurer).__name__
        try:
            candidate = structurer(markdown, feedback=feedback)
        except Exception as exc:  # a failing backend must not abort the ladder
            result.attempts.append(
                StructuringAttempt(
                    stage=stage,
                    backend=backend,
                    parsed=False,
                    accepted=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        if not isinstance(candidate, Statement):
            result.attempts.append(
                StructuringAttempt(
                    stage=stage,
                    backend=backend,
                    parsed=False,
                    accepted=False,
                    error="structurer did not return a validated Statement",
                )
            )
            continue

        candidate = apply_statement_repairs(markdown, normalize_statement(candidate))
        candidate_recon = reconcile(candidate)
        accepted = _is_better(candidate_recon, result.reconciliation)
        result.attempts.append(
            StructuringAttempt(
                stage=stage,
                backend=backend,
                parsed=True,
                accepted=accepted,
                reconciled=candidate_recon.ok,
                summary_reconciled=candidate_recon.summary_ok,
                issue_count=len(candidate_recon.issues),
                transaction_count=len(candidate.transactions),
            )
        )
        if accepted:
            result.statement = candidate
            result.reconciliation = candidate_recon
            result.backend_used = backend
            result.escalated = index > 0

        incumbent = result.reconciliation
        if incumbent is not None and (incumbent.ok or incumbent.summary_ok is True):
            break
        feedback = _feedback_for(candidate_recon)

    if result.statement is None:
        failures = "; ".join(
            attempt.error or "structuring failed"
            for attempt in result.attempts
            if attempt.error
        )
        result.manual_review_reason = (
            f"every structuring attempt failed ({failures})"
            if failures
            else "no structuring attempt produced a validated Statement"
        )
    return result


@dataclass
class UniversalOutcome:
    """What the universal path decided, and why."""

    route: str
    corporate_use: str
    approved: bool
    document_source: str
    report: Report | None = None
    structuring: UniversalStructureResult | None = None
    manual_review_reason: str | None = None
    model_used: str | None = None

    @property
    def parsed(self) -> bool:
        return self.report is not None

    @property
    def reconciled(self) -> bool:
        return self.report is not None and self.report.reconciliation.ok

    @property
    def summary_reconciled(self) -> bool | None:
        return self.report.reconciliation.summary_ok if self.report else None

    @property
    def adb_validated(self) -> bool:
        return bool(self.report and self.report.metrics.adb_ok)


def manual_review_reason(report: Report) -> str | None:
    """The most specific reason this report cannot be approved automatically."""
    if report.quality.corporate_use == "approved":
        return None
    recon, integrity, quality = report.reconciliation, report.integrity, report.quality
    if "not_a_formal_statement" in integrity.flags:
        return "document is not a complete bank statement"
    if recon.summary_ok is False:
        return "bank-stated summary does not reconcile"
    if recon.sum_delta is not None and abs(recon.sum_delta) > 0.01:
        return (
            "ledger does not sum to the printed ending balance "
            f"(off by {recon.sum_delta:+.2f})"
        )
    if recon.computed_ending is None:
        return "statement is missing the beginning or ending balance"
    if any("coverage_mismatch" in flag for flag in integrity.flags):
        return "line-item detail does not cover the bank-stated totals"
    if recon.continuity_breaks:
        return f"{recon.continuity_breaks} printed running-balance continuity break(s)"
    if "missing_declared_statement_page" in integrity.flags:
        return "a page the statement declares is absent from the supplied PDF"
    if quality.aggregate_rows:
        return f"{quality.aggregate_rows} bank-summary aggregate row(s) replace posted detail"
    if report.metrics.adb_ok is not True:
        return "daily-balance ledger did not validate"
    if recon.issues:
        return recon.issues[0]
    return f"quality level {quality.level} is not approvable"


def _outcome_from_report(
    report: Report,
    *,
    route: str,
    document_source: str,
    structuring: UniversalStructureResult | None = None,
) -> UniversalOutcome:
    approved = report.quality.corporate_use == "approved"
    return UniversalOutcome(
        route=route,
        corporate_use=report.quality.corporate_use,
        approved=approved,
        document_source=document_source,
        report=report,
        structuring=structuring,
        manual_review_reason=manual_review_reason(report),
        model_used=report.model_used,
    )


def analyze_any_bank_markdown(
    markdown: str,
    *,
    settings: Settings | None = None,
    structurers: tuple[StatementStructurer, ...] | list[StatementStructurer] | None = None,
    allow_vendor_structurer: bool = False,
    document_source: str = PROVIDED_MARKDOWN,
) -> UniversalOutcome:
    """Analyze any statement markdown: certified parser first, universal second.

    A recognized layout takes the deterministic route untouched. An unknown
    layout is structured into the same `Statement` and then handed to the same
    frozen reconcile / ADB / classify / metrics / approval gate.
    """
    settings = settings or load_settings()
    if deterministic_statement(markdown) is not None:
        report = analyze_markdown(markdown, settings=settings, parse_mode="deterministic")
        return _outcome_from_report(
            report,
            route=DETERMINISTIC,
            document_source=document_source,
        )

    chain = (
        structurers
        if structurers is not None
        else default_structurers(
            settings,
            allow_vendor_structurer=allow_vendor_structurer,
        )
    )
    structuring = structure_statement(markdown, structurers=chain, settings=settings)
    if structuring.statement is None or structuring.reconciliation is None:
        return UniversalOutcome(
            route=UNSTRUCTURED,
            corporate_use=MANUAL_REVIEW,
            approved=False,
            document_source=document_source,
            structuring=structuring,
            manual_review_reason=structuring.manual_review_reason,
        )

    report = build_report(
        markdown,
        structuring.statement,
        structuring.reconciliation,
        settings=settings,
        model_used=f"universal:{structuring.backend_used}",
        escalated=structuring.escalated,
    )
    return _outcome_from_report(
        report,
        route=UNIVERSAL,
        document_source=document_source,
        structuring=structuring,
    )


@dataclass(frozen=True)
class DocumentSource:
    """The markdown a statement PDF yielded, and where it came from."""

    markdown: str
    source: str
    extractor: str
    page_count: int


def resolve_document_markdown(
    pdf_bytes: bytes,
    *,
    source_file: str = "",
    dpi: int = 300,
    force_ocr: bool = False,
    parse_fn: Callable[..., object] | None = None,
) -> DocumentSource:
    """Prefer a reliable native text layer; otherwise fall back to visual OCR.

    Thin wrapper over `ocr.pipeline.parse_statement`, which already does the
    native-first routing, so there is one implementation of that decision. The
    wrapper's job is to label which source was used.
    """
    if parse_fn is None:
        from ocr.pipeline import parse_statement as parse_fn  # noqa: PLC0415 (optional dep)
    document = parse_fn(
        pdf_bytes,
        source_file=source_file,
        dpi=dpi,
        force_ocr=force_ocr,
    )
    extractor = getattr(document, "model", "") or ""
    source = NATIVE_TEXT if extractor.startswith("native-pdf-text") else OCR_MARKDOWN
    return DocumentSource(
        markdown=document.to_markdown(),
        source=source,
        extractor=extractor,
        page_count=len(getattr(document, "pages", []) or []),
    )


def analyze_any_bank_pdf(
    pdf_bytes: bytes,
    *,
    source_file: str = "",
    dpi: int = 300,
    force_ocr: bool = False,
    settings: Settings | None = None,
    structurers: tuple[StatementStructurer, ...] | list[StatementStructurer] | None = None,
    allow_vendor_structurer: bool = False,
    parse_fn: Callable[..., object] | None = None,
) -> UniversalOutcome:
    """PDF -> markdown (native text or OCR) -> Statement -> frozen gate."""
    document = resolve_document_markdown(
        pdf_bytes,
        source_file=source_file,
        dpi=dpi,
        force_ocr=force_ocr,
        parse_fn=parse_fn,
    )
    return analyze_any_bank_markdown(
        document.markdown,
        settings=settings,
        structurers=structurers,
        allow_vendor_structurer=allow_vendor_structurer,
        document_source=document.source,
    )

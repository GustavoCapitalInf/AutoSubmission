"""The telemetry record: one JSON object per statement per run.

Schema and rationale: `docs/moneythumb-replacement/H3_SCHEMA.md`. This module
is the single definition of the shape; both storage backends serialise exactly
this object (H3_SCHEMA I2), so a field that is not built here does not exist.

**Sensitivity invariant (I1), enforced by test.** A record carries hashes,
registry ids, enum codes, counts and timings — never customer or business
names, account numbers, amounts, statement dates, transaction text, or
filenames. Two traps this module is written to avoid:

- **No filename.** Customer names live in paths (`SALON BARK LLC March.pdf`).
  Documents are identified by `content_sha256` alone; a run that needs to act
  on a finding keeps its own hash->path map outside telemetry.
- **No extracted bank label.** `parser_id` is a constant from our registry and
  is safe; `Statement.bank` is read *out of the document*, and on the LLM path
  for an unknown institution that string can be a business name.

Exception **class names** only, never messages: a traceback message routinely
quotes a fragment of the document.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from .diagnostics import diagnose
from .prices import estimate


def utc_now_iso() -> str:
    """Same convention as ``webapp.storage.utc_now_iso``, defined locally.

    Telemetry must stay importable from ``batch.py`` without pulling in the
    webapp (asserted by test), so this one-line helper is duplicated rather
    than imported. If the two ever disagree, they are both wrong.
    """
    return datetime.now(UTC).isoformat()

TELEMETRY_VERSION = 1

#: Cap on the near-miss score vector (H3_SCHEMA §4). Measured sparsity is 2-7
#: non-zero scores of 46 registrations, so this is a safety valve for a
#: pathological document, not a policy. `scores_capped` records when it bites.
SCORE_CAP = 12

OUTCOME_CLASSES = ("validated", "review", "withheld", "failed", "deferred")

#: Reasons a document may be DEFERRED — recorded work that a tranche
#: deliberately did not do. Deferral is always an explicit declaration by the
#: caller, never inferred from an absent payload: the difference between "we
#: did not try" and "we tried and it broke" is the whole point of the class,
#: and inferring it would let a real failure hide as a decision.
DEFERRED_REASONS = ("deferred_scanned", "deferred_visual_ocr", "profile_only")
SOURCE_PATHS = ("native", "local_tesseract", "visual", "none")
DISPATCH_SOURCES = ("live", "cached", "unavailable")

#: The complete key set of a record, asserted by test so a new field cannot be
#: added without being reviewed against the sensitivity invariant.
TOP_LEVEL_KEYS = frozenset({
    "telemetry_version", "record_id", "run_id", "emitted_at", "emitter",
    "job_id", "document", "source", "dispatch", "stages", "models", "outcome",
    "diagnostics",
})


def new_run_id() -> str:
    """A run id that sorts chronologically and is unique per process run."""
    return f"{utc_now_iso()}-{uuid.uuid4().hex[:8]}"


def source_path_for(model: str | None) -> str:
    """Which intake rung produced the text, derived from StatementMarkdown.model.

    `model` is the one signal both the webapp and the CLI share — the ladder's
    `on_stage` rung is the same fact but is only wired up in the worker.
    """
    if not model:
        return "none"
    if model.startswith("native-pdf-text"):
        return "native"
    if model == "local-tesseract-ocr":
        return "local_tesseract"
    if model == "deterministic-native-preflight":
        return "none"
    return "visual"


def document_section(
    content_sha256: str,
    byte_size: int,
    profile: Any | None = None,
    *,
    duplicate_of_prior_record: bool = False,
) -> dict:
    """Document facts, from the O-1 preflight profile when there is one.

    A non-PDF input (batch.py accepts pre-OCR'd markdown) has no profile: the
    hash and size are still true, and the PDF-shaped fields report `unknown`
    rather than a fabricated `digital`.
    """
    section = {
        "content_sha256": content_sha256,
        "byte_size": byte_size,
        "page_count": 0,
        "classification": "unknown",
        "valid_pdf": False,
        "encrypted": False,
        "malformed_page_count": 0,
        "likely_account_count": 0,
        "duplicate_of_prior_record": duplicate_of_prior_record,
    }
    if profile is not None:
        section.update(
            page_count=profile.page_count,
            classification=profile.classification,
            valid_pdf=profile.valid_pdf,
            encrypted=profile.encrypted,
            malformed_page_count=len(profile.malformed_pages),
            likely_account_count=profile.likely_account_count,
        )
    return section


def source_section(doc: Any | None) -> dict:
    """OCR-path and truncation facts, read off the StatementMarkdown.

    Truncation is correct on a cache hit as well as a fresh read: D-3b
    round-trips `page_integrity` through the artifact cache. An empty
    `page_integrity` means NOT ASSESSED, which is distinct from "zero truncated
    pages" and is reported as such (H3_SCHEMA I5).
    """
    if doc is None:
        return {
            "path": "none",
            "model": None,
            "page_count": 0,
            "truncation": {
                "assessed": False,
                "truncated_page_count": 0,
                "truncated_page_indices": [],
                "signals": [],
            },
        }
    integrity = list(getattr(doc, "page_integrity", []) or [])
    truncated = [item.page_index for item in integrity if item.truncated]
    signals = sorted({signal for item in integrity for signal in (item.signals or [])})
    return {
        "path": source_path_for(doc.model),
        "model": doc.model,
        "page_count": len(doc.pages),
        "truncation": {
            "assessed": bool(integrity),
            "truncated_page_count": len(truncated),
            "truncated_page_indices": truncated,
            "signals": signals,
        },
    }


def dispatch_section(
    dispatch: Any | None,
    scores: list[tuple[str, float]],
    registration_count: int,
    *,
    source: str,
) -> dict:
    """Routing facts, projected from the R-3 Dispatch.

    PROJECTED, never stored whole: `Dispatch.statement` holds the parsed
    Statement — every amount and description — and must never reach a record.
    Only ids, scores and enum outcomes cross this boundary.

    `source="cached"` is the deliberate, documented degradation: on a D-3
    analysis cache hit `analyze_markdown` never ran, so there is no dispatch of
    record. The score vector is still populated (detect is pure), and the
    outcome class still comes from the cached payload, so the coverage rate
    stays computable — only the parser diagnostics thin out.

    `exceptions` (W3-1) carries `[parser_id, stage, exception_class]` triples.
    Before the boundary existed a parser crash escaped `resolve`, so no
    `Dispatch` was ever built and the only surviving fact was the top-level
    `outcome.error_type` — one class name for the whole document, with no way
    to say WHICH parser broke. Discovery's 53 crashes were diagnosable only by
    re-running the archive by hand. The exception CLASS NAME is the whole
    payload here, deliberately: a message quotes the document (I1).
    """
    capped = scores[:SCORE_CAP]
    section = {
        "source": source,
        "outcome": None,
        "parser_id": None,
        "score": None,
        "candidates": [],
        "attempted": [],
        "exceptions": [],
        "scores": [[parser_id, score] for parser_id, score in capped],
        "scores_floor": 0.0,
        "scores_capped": len(scores) > SCORE_CAP,
        "registration_count": registration_count,
    }
    if dispatch is not None:
        detection = getattr(dispatch, "detection", None)
        section.update(
            outcome=dispatch.outcome,
            parser_id=dispatch.parser_id,
            score=detection.score if detection is not None else None,
            candidates=[[parser_id, score] for parser_id, score in dispatch.candidates],
            attempted=list(dispatch.attempted),
            exceptions=[
                [failure.parser_id, failure.stage, failure.exception]
                for failure in getattr(dispatch, "exceptions", ())
            ],
        )
    return section


def model_calls_for(doc: Any | None, payload: dict | None) -> list[dict]:
    """Model calls we can actually count, with tokens only where reported.

    Countable today: visual-OCR pages sent, and extraction calls (1, or 2 when
    the report escalated). Token counts exist only for the visual rung on a
    LIVE read — `PageText` carries `completion_tokens`, and the artifact cache
    normalises pages back to plain `str`, so a cache hit reports `None` rather
    than a stale number. Prompt tokens are not captured anywhere in the
    platform today; they are `None`, never estimated from character counts
    (H3_SCHEMA §9).
    """
    calls: list[dict] = []
    if doc is not None and source_path_for(doc.model) == "visual":
        reported = [getattr(page, "completion_tokens", None) for page in doc.pages]
        known = [value for value in reported if value is not None]
        calls.append({
            "stage": "ocr",
            "model": doc.model,
            "purpose": "visual_ocr",
            "calls": len(doc.pages),
            "prompt_tokens": None,
            "completion_tokens": sum(known) if known else None,
        })
    elif doc is not None:
        calls.append({
            "stage": "ocr",
            "model": doc.model,
            "purpose": source_path_for(doc.model),
            "calls": 1,
            "prompt_tokens": None,
            "completion_tokens": None,
        })

    model_used = (payload or {}).get("model_used") or ""
    if payload is not None and model_used and not model_used.endswith("-deterministic"):
        calls.append({
            "stage": "analysis",
            "model": model_used,
            "purpose": "extraction",
            "calls": 2 if payload.get("escalated") else 1,
            "prompt_tokens": None,
            "completion_tokens": None,
        })
    return calls


def classify_outcome(
    payload: dict | None,
    *,
    error_type: str | None = None,
    error_reason: str | None = None,
    deferred: str | None = None,
) -> tuple[str, str]:
    """(class, reason) for one document. Precedence order, top down.

    `deferred` is work a tranche chose not to do — a scanned statement in an
    offline tranche, say. It outranks everything because it is a statement
    about the RUN, not about the document, and it is only ever reached by an
    explicit `deferred=` declaration from the caller.

    `failed` therefore means exactly one thing: attempted, and errored.
    `withheld` is the platform refusing to publish an authoritative value —
    the same fail-closed state the corpus gate calls WITHHELD. `review` is a
    finer partition of the gate's PASS: a number exists, but approval is
    blocked. The corpus anchor test pins both halves.
    """
    if deferred is not None:
        if deferred not in DEFERRED_REASONS:
            raise ValueError(f"unknown deferral reason: {deferred!r}")
        return "deferred", deferred
    if payload is None:
        return "failed", error_reason or ("exception" if error_type else "no_analysis")

    metrics = payload.get("metrics") or {}
    quality = payload.get("quality") or {}
    integrity = payload.get("integrity") or {}

    if metrics.get("average_daily_balance") is None:
        return "withheld", "withheld_adb"

    flags = list(integrity.get("flags") or [])
    if "parser_ambiguous" in flags:
        return "review", "parser_ambiguous"
    # A document that reached a value despite a parser crashing on it is a
    # review case with a named cause, not an anonymous "integrity_flags" one:
    # the crash cluster it belongs to is what ranks the underlying defect.
    if "parser_exception" in flags:
        return "review", "parser_exception"
    if flags:
        return "review", "integrity_flags"
    if quality.get("corporate_use") != "approved":
        return "review", "quality_needs_review"
    return "validated", "approved"


def build_record(
    *,
    run_id: str,
    emitter: str,
    document: dict,
    source: dict,
    dispatch: dict,
    stages: dict,
    model_calls: list[dict],
    payload: dict | None,
    escalated: bool = False,
    error_type: str | None = None,
    error_reason: str | None = None,
    deferred: str | None = None,
    fallback_reason: str | None = None,
    job_id: str | None = None,
) -> dict:
    outcome_class, reason = classify_outcome(
        payload, error_type=error_type, error_reason=error_reason, deferred=deferred
    )
    return {
        "telemetry_version": TELEMETRY_VERSION,
        "record_id": uuid.uuid4().hex,
        "run_id": run_id,
        "emitted_at": utc_now_iso(),
        "emitter": emitter,
        "job_id": job_id,
        "document": document,
        "source": source,
        "dispatch": dispatch,
        "stages": stages,
        "models": {"calls": model_calls, "cost": estimate(model_calls)},
        "outcome": {
            "class": outcome_class,
            "reason": reason,
            "escalated": escalated,
            "error_type": error_type,
            "fallback_reason": fallback_reason,
        },
        # W3-2. Computed here, from the payload every emitter already passes,
        # so batch, the webapp worker and the discovery runner all pick the
        # diagnostics up with no change of their own. A read-only projection:
        # `diagnose` does not mutate `payload` and never stores a string that
        # came out of a statement (see telemetry/diagnostics.py).
        "diagnostics": diagnose(payload, outcome_class),
    }

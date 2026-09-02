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
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from analysis.payload_shape import (
    DOCUMENT_KEY,
    is_document_payload,
    payload_accounts,
    payload_document_block,
    refuse_document_payload,
)

from .collect import DETERMINISTIC_MODEL_SUFFIX, reconstructed_claim
from .diagnostics import diagnose, diagnose_document
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
#: P21-ROUTING (Phase 2.1) adds `"paddle"`, between `"local_tesseract"` and
#: `"visual"` — the same slot PaddleOCR takes in `ocr.escalation.
#: EXTRACTOR_ORDER`.
SOURCE_PATHS = ("native", "local_tesseract", "paddle", "visual", "none")

#: P20-ROUTER (Phase 2.0). Mirrored, by value, from `ocr.escalation` — held
#: equal to it by `tests/test_escalation_tripwires.py` so the two never drift.
#: Not imported from there directly: `ocr/escalation.py` must import nothing
#: from `telemetry` (see its module docstring), and a one-way mirror the
#: OTHER direction (this module importing `ocr.escalation`) would put a
#: telemetry-layer dependency on the OCR router for two string tuples. A row
#: or record token from outside either vocabulary is refused by the
#: `discovery.runner` row projection.
FAILURE_CLASSES = ("A", "B", "C", "")
EXTRACTION_TRIGGERS = (
    "image_only_document",
    "mixed_document_pages_without_native_text",
    "offline_rungs_produced_no_text",
    "extractor_output_unusable",
    "extractor_failed",
    "operator_forced_visual",
    "truncation_flagged",
)

#: The outcome ladder, ranked worst to best. `discovery/compare.py::LADDER` is
#: the same tuple and is the one the whole non-regression regime is measured
#: on; it is not imported because `discovery` imports THIS module and a cycle
#: is a worse coupling than a pinned duplicate.
#: `tests/test_document_outcome.py` holds the two equal, so a divergence is a
#: red test rather than a document fold that ranks by a private order.
#: `deferred` is deliberately absent: it is a statement about the RUN, so it is
#: not a rung and a document fold may not produce it.
DOCUMENT_LADDER = ("failed", "withheld", "review", "validated")

#: L1-C17. The CLOSED vocabulary an omitted sibling section's `reason` comes
#: from (`analysis/pipeline.py::SiblingOmission`), every member of which names
#: PRINTED evidence — design §4's table. Declared here, beside `DEFERRED_REASONS`
#: and for the same reason: this module is where a token from a closed
#: vocabulary decides an outcome, and a caller that invents one must be refused
#: rather than believed.
#:
#: The list is closed against ABSENCE and open to EVIDENCE:
#: `absence_of_parsed_rows` is the member this condition exists to refuse, and
#: a member names the evidence rather than the reader that read it — two
#: modules reading one printed fact share one token.
RATIFIED_OMISSION_REASONS = (
    "printed_dormancy_declaration",
    "printed_zero_activity_summary",
    "yield_only_arithmetic_with_summary_equality",
    "printed_pair_coincides_and_no_row_printed",
)

#: How this record's routing block was established. The vocabulary is
#: unchanged since H-3 shipped; what changed at #TELCOV is that all three
#: emitters now reach it through one derivation in `dispatch_section` instead
#: of asserting it, and that `cached` is finally reachable from the CLI paths.
SOURCE_LIVE = "live"
SOURCE_CACHED = "cached"
SOURCE_UNAVAILABLE = "unavailable"
DISPATCH_SOURCES = (SOURCE_LIVE, SOURCE_CACHED, SOURCE_UNAVAILABLE)

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


#: F-7 closure: the closed set of model tokens `source_path_for` will call
#: "visual". Before this, ANY model string that matched none of the other
#: branches fell through to `"visual"` — correct only because the only rung
#: that has ever produced an unrecognised token IS the visual one; a future
#: extractor's model string (e.g. a `paddle+...` prefix) would have been
#: silently mis-attributed to the GPU/paid path by the same fallthrough. The
#: fallthrough now returns `"none"` for anything not explicitly named here,
#: which is loud (see `source_path_unrecognized_model`) rather than a guess.
#: PaddleOCR gets its own member in Phase 2.1, not this one (no PaddleOCR
#: token here in Phase 2.0).
#:
#: Case-sensitive BY DESIGN, matching every other branch in
#: `source_path_for` (`"local-tesseract-ocr"`, `"deterministic-native-
#: preflight"` are exact, case-sensitive comparisons too — a parser or
#: extractor never has reason to vary the case of its OWN constant token).
#: `"baidu/unlimited-ocr"` (lowercase) is therefore an UNRECOGNISED token,
#: not a case-insensitive match for the real one — the same defensive
#: default as any other token this module has never seen, surfaced the same
#: way (`source_path_unrecognized_model`), never silently normalised.
#:
#: Placed immediately above `source_path_for`, the function it belongs to
#: (MINOR-4, PHASE2_P20SEAM_REVIEW.md) — cell A's `FAILURE_CLASSES` /
#: `EXTRACTION_TRIGGERS` insert immediately after `SOURCE_PATHS` above,
#: which is a different anchor, so the two cells no longer collide on the
#: same line range at compose time.
VISUAL_MODEL_TOKENS = frozenset({"baidu/Unlimited-OCR"})

#: P21-ROUTING (Phase 2.1). A LITERAL mirror of `ocr.paddle_config.
#: PADDLE_MODEL_TOKEN` — not imported, for the same reason `VISUAL_MODEL_TOKENS`
#: is a literal rather than an import: `telemetry` stays free of a load-bearing
#: dependency on `ocr` for two string constants. `tests/test_telemetry.py`
#: holds this literal equal to `ocr.paddle_config.PADDLE_MODEL_TOKEN` by test,
#: so the two cannot silently drift apart.
PADDLE_MODEL_TOKENS = frozenset({"paddle-ocr+ppocrv5"})


def source_path_for(model: str | None) -> str:
    """Which intake rung produced the text, derived from StatementMarkdown.model.

    `model` is the one signal both the webapp and the CLI share — the ladder's
    `on_stage` rung is the same fact but is only wired up in the worker.

    F-7 closure: the fallthrough is CLOSED, not a guess. `"visual"` is
    returned only for a token in `VISUAL_MODEL_TOKENS` (case-sensitive);
    `"paddle"` only for the exact `PADDLE_MODEL_TOKENS` member (P21-ROUTING);
    any other non-empty, unrecognised token — including a `paddle`-LOOKING
    string that is not the registered token — returns `"none"` rather than
    being assumed to be either rung. See `source_path_unrecognized_model` for
    the companion predicate a caller can use to surface that as an explicit
    diagnostic instead of a silent mis-attribution.
    """
    if not model:
        return "none"
    if model.startswith("native-pdf-text"):
        return "native"
    if model == "local-tesseract-ocr":
        return "local_tesseract"
    if model == "deterministic-native-preflight":
        return "none"
    if model in PADDLE_MODEL_TOKENS:
        return "paddle"
    if model in VISUAL_MODEL_TOKENS:
        return "visual"
    return "none"


def source_path_unrecognized_model(model: str | None) -> bool:
    """True when `model` is non-empty but matches none of `source_path_for`'s
    known branches (F-7): a document whose provenance token cannot be
    attributed to any known rung. A caller building a record's diagnostics
    can surface `source_path_unrecognized_model: true` from this rather than
    let the token silently fall through to `"none"` unremarked.
    """
    if not model:
        return False
    if model.startswith("native-pdf-text"):
        return False
    if model == "local-tesseract-ocr":
        return False
    if model == "deterministic-native-preflight":
        return False
    if model in PADDLE_MODEL_TOKENS:
        return False
    if model in VISUAL_MODEL_TOKENS:
        return False
    return True


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

    P21-ROUTING (design item 4): `evidence_sha256` / `provider` /
    `execution_class` are read from `doc.evidence.runtime` when present —
    `None` for every rung that carries no canonical evidence (every read
    before Phase 2.1, and every non-Paddle read since).
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
            "evidence_sha256": None,
            "provider": None,
            "execution_class": None,
        }
    integrity = list(getattr(doc, "page_integrity", []) or [])
    truncated = [item.page_index for item in integrity if item.truncated]
    signals = sorted({signal for item in integrity for signal in (item.signals or [])})
    evidence = getattr(doc, "evidence", None)
    runtime = getattr(evidence, "runtime", None) if evidence is not None else None
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
        "evidence_sha256": getattr(evidence, "evidence_sha256", None) if evidence is not None else None,
        "provider": (runtime or {}).get("provider") if runtime is not None else None,
        "execution_class": (runtime or {}).get("execution_class") if runtime is not None else None,
    }


def dispatch_section(
    dispatch: Any | None,
    scores: list[tuple[str, float]],
    registration_count: int,
    *,
    payload: dict | None,
) -> dict:
    """Routing facts: observed from the R-3 Dispatch, or reconstructed.

    PROJECTED, never stored whole: `Dispatch.statement` holds the parsed
    Statement — every amount and description — and must never reach a record.
    Only ids, scores and enum outcomes cross this boundary.

    **`source` is DERIVED HERE, from the two facts that decide it, and is not
    the caller's to assert (#TELCOV).** It had been a required keyword, and all
    three emitters computed it themselves: the worker said `cached`, while
    `batch.py` and the discovery runner said `unavailable` for the identical
    state. Measured on the warm archive re-run `b7b40c73`, that spelled
    `dispatch.source = "unavailable"` over 2,561 records the analysis cache had
    just served in full — H3_SCHEMA I5's own example of what the field exists
    to prevent ("`dispatch.source = "cached"` is not `unclaimed`"), written the
    other way round. One rule now, in one place:

    * `live` — a `Dispatch` was observed. The verdict is an OBSERVATION,
      including `unclaimed`, where the observation is that nobody claimed.
    * `cached` — no `Dispatch`, but a payload exists, which happens on exactly
      one path: the D-3 analysis cache served it. `outcome`/`parser_id`/`score`
      /`candidates` are then RECONSTRUCTED where `reconstructed_claim` can do
      it soundly, and stay null where it refuses.
    * `unavailable` — no `Dispatch` and no payload: the analysis stage never
      produced anything for this document (invalid PDF, OCR failure, a deferred
      tranche). Not a degradation, an absence.

    `payload` is keyword-only and REQUIRED, with no default, for the same
    reason `source` was: a caller that forgets it would otherwise get
    `unavailable` on every cache hit — this exact defect, silently
    reintroduced — instead of a `TypeError` at the call site.

    So `source` doubles as the provenance mark, with no new field and no new
    enum member: `cached` + a parser id is a reconstruction by construction,
    `live` + a parser id is an observation, and `cached` + null is the
    reconstruction refusing to name one (the REGFP instrument). The
    §DISCOBS row vocabulary maps onto it exactly — `live_dispatch`,
    `live_detect`, and the `unavailable` mark that names no parser.

    NOT reconstructed, in either sense: `attempted` and `exceptions`. See
    `reconstructed_claim` for why each says nothing rather than saying zero.

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
        "source": SOURCE_LIVE if dispatch is not None else (
            SOURCE_CACHED if payload is not None else SOURCE_UNAVAILABLE
        ),
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
    elif payload is not None:
        claim = reconstructed_claim(scores, payload)
        if claim is not None:
            parser_id, score = claim
            section.update(
                outcome="claimed",
                parser_id=parser_id,
                score=score,
                candidates=[[parser_id, score]],
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

    OQ3 provenance (MAJOR-2, PHASE2_P20SEAM_REVIEW.md): every OCR-stage call
    entry also carries `endpoint_class` and `remote_opt_in`, read from
    `ocr.config.load_settings()` AT RECORD TIME — the identical pattern
    `webapp.artifact_cache.ocr_settings_key` already uses (loaded fresh when
    not supplied, so a caller that never itself touches the OCR service still
    records correctly if `OCR_BASE_URL` / `OCR_REMOTE_OPT_IN` changed under
    it). Deliberately NOT threaded through `StatementMarkdown`:
    `ocr/document.py`'s object is the OCR RESULT (what text a rung produced),
    not a place to carry an intake SETTING, and re-reading `load_settings()`
    here is exactly as cheap as `ocr_settings_key`'s own re-read. The fields
    describe the run's CURRENT endpoint configuration, not necessarily the
    one THIS document's rung used (a native/local read touched no endpoint at
    all) — recorded anyway on every OCR entry because OQ3's "recorded opt-in"
    is a property of the RUN's audit trail, not only of a live network call.

    F-7 (MAJOR-3): an unrecognised model token (`source_path_unrecognized_
    model`) is reported the SAME shape as a visual read — one call per page,
    completion tokens summed where reported — never silently downgraded to
    `purpose: "none"` / `calls: 1`, which would under-report a real per-page
    GPU read as a single untimed call. Its `purpose` is `"unrecognized_
    model"`, distinct from both `"visual_ocr"` and every `source_path_for`
    value, so a rollup can tell the three apart.

    NEW-6 (re-review, closure 1cc759e): `load_settings()` raises
    `ProvenanceTokenError` for a hostile `OCR_MODEL`; caught here so a
    misconfigured environment costs `endpoint_class` / `remote_opt_in`
    (both `None`) rather than the whole record — every `_emit` call site
    wraps this function's caller (`build_record`) in `except Exception:
    pass`, so an uncaught raise here would silently drop a telemetry record
    for a document that otherwise processed fine.
    """
    calls: list[dict] = []
    if doc is not None:
        path = source_path_for(doc.model)
        unrecognized = source_path_unrecognized_model(doc.model)
        # NEW-6 (re-review, closure 1cc759e): load_settings() validates
        # OCR_MODEL and raises ProvenanceTokenError for a hostile value
        # (BLOCK-1's own closure). Read defensively — a misconfigured
        # environment costs these two fields, never the whole record: every
        # `_emit` call site wraps the WHOLE build_record(...) call
        # (model_calls_for included) in `except Exception: pass`
        # (H3_SCHEMA I4, "cannot fail a job"), so an uncaught raise here
        # would silently drop the entire telemetry record for a document
        # that otherwise processed fine, rather than degrading two fields
        # of it.
        try:
            from ocr.config import ProvenanceTokenError, load_settings as _load_ocr_settings

            ocr_settings = _load_ocr_settings()
            endpoint_class = ocr_settings.endpoint_class
            remote_opt_in = ocr_settings.remote_opt_in
        except ProvenanceTokenError:
            endpoint_class = None
            remote_opt_in = None
        if path == "visual" or unrecognized:
            reported = [getattr(page, "completion_tokens", None) for page in doc.pages]
            known = [value for value in reported if value is not None]
            calls.append({
                "stage": "ocr",
                "model": doc.model,
                "purpose": "visual_ocr" if path == "visual" else "unrecognized_model",
                "calls": len(doc.pages),
                "prompt_tokens": None,
                "completion_tokens": sum(known) if known else None,
                "endpoint_class": endpoint_class,
                "remote_opt_in": remote_opt_in,
            })
        elif path == "paddle":
            # P21-ROUTING: one call per Paddle page. Paddle pages are plain
            # `str` (D9's derived text), not the visual rung's `PageText`, so
            # there is no completion-token signal to sum here — the model is
            # named and priced (or not) exactly like any other model; it is
            # deliberately NOT in `telemetry.prices.FREE_MODELS` (remote_paid
            # is not free), so `estimate()` reports it `unpriced` and the
            # actual cost is measured operationally, never invented.
            calls.append({
                "stage": "ocr",
                "model": doc.model,
                "purpose": "paddle_ocr",
                "calls": len(doc.pages),
                "prompt_tokens": None,
                "completion_tokens": None,
                "endpoint_class": endpoint_class,
                "remote_opt_in": remote_opt_in,
            })
        else:
            calls.append({
                "stage": "ocr",
                "model": doc.model,
                "purpose": path,
                "calls": 1,
                "prompt_tokens": None,
                "completion_tokens": None,
                "endpoint_class": endpoint_class,
                "remote_opt_in": remote_opt_in,
            })

    model_used = (payload or {}).get("model_used") or ""
    # The same suffix `reconstructed_claim` reads, through the same constant:
    # both are asking whether a model produced this payload, and two string
    # literals asking one question is how they drift apart (#TELCOV).
    if (
        payload is not None
        and model_used
        and not model_used.endswith(DETERMINISTIC_MODEL_SUFFIX)
    ):
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
    # This function answers about ONE account, and measured (design §1.4) it
    # answers a document-shaped payload `withheld/withheld_adb` — a refusal
    # naming a check nobody ran, on a document whose every account may have
    # validated. `classify_document` below is the fold; this is the rung.
    refuse_document_payload(payload, surface="telemetry/record.py::classify_outcome")

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
    if "integrity_check_exception" in flags:
        return "review", "integrity_check_exception"
    if flags:
        return "review", "integrity_flags"
    if quality.get("corporate_use") != "approved":
        return "review", "quality_needs_review"
    return "validated", "approved"


def classify_document(
    payload: dict | None,
    *,
    error_type: str | None = None,
    error_reason: str | None = None,
    deferred: str | None = None,
) -> tuple[str, str]:
    """(class, reason) for one DOCUMENT: the WEAKEST account's, fail-closed.

    One outcome per document is not a convenience. `discovery/compare.py` ranks
    on `LADDER` keyed on `content_sha256` alone, and that ladder is what the
    whole non-regression regime is measured on — so the document's answer is a
    FOLD over its accounts, never a list.

    Today's answer on every document that carries one account, by construction
    rather than by measurement: an account payload never reaches the fold, and
    a `deferred` declaration is a statement about the RUN that outranks the
    document's contents exactly as it always did.

    Three document-level overrides sit on top of the fold, and each can only
    LOWER the result:

    * no account at all — a publisher defect rather than a document, so it
      `failed`s instead of being scored on an empty minimum;
    * an omission whose `reason` is not in `RATIFIED_OMISSION_REASONS`
      (L1-C17): the section should never have been published as omitted, so
      the document `failed`s rather than being graded around it.

    **The design's third override is deliberately NOT wired** (Ocean, from the
    L1-S2 review; ruling Q10 is with Gustavo). §1.5 proposed that an omission on
    RATIFIED evidence should stop a document being `validated` and file it
    `review/sibling_section_omitted`. L1-S2 records exactly such omissions on
    15 documents that batch 8 validated, every one admitted on printed evidence
    — so wiring that override would fold 15 protected documents from
    `validated` to `review`. That is a regression under the batch-9 doctrine
    whatever its merits as a policy, and it is not a thing a stage that moves
    zero documents may decide on its own. A ratified omission therefore leaves
    the fold alone until the ruling lands; an UNRATIFIED one still fails the
    document, because that one is a defect rather than a policy.

    `validated` on a document therefore means *every account validated, and
    nothing was omitted except on ratified printed evidence*, which on a
    one-account document IS today's meaning.

    **The contract at the door**, and it is part of the contract rather than a
    nicety: what this reads is a published PAYLOAD — a mapping, or `None` for a
    document that produced none. Anything else raises `TypeError` HERE, naming
    the shape it wanted, rather than being passed on to `classify_outcome` to
    fail several frames down inside a `.get`. The L1-S3 review found what the
    quiet version cost: `tests/test_l1s2_document_outcome.py`'s resolver
    discovers this fold by AST and probes it with two call shapes — the
    `DocumentReport` object first, then the payload — narrowing on `TypeError`
    to mean *not this call shape, try the other*. Delegating the object instead
    produced `AttributeError` two frames down, the resolver never reached the
    payload leg, and eleven of L1-S2's Q10 pins went red at the merged tree.
    `TypeError` at this door is therefore a published contract that a sibling
    stage already depends on, not an implementation detail.
    """
    if payload is not None and not isinstance(payload, Mapping):
        raise TypeError(
            f"classify_document reads a published payload — a mapping, or None "
            f"for a document that produced none; got {type(payload).__name__}. "
            f"A `DocumentReport` is the OBJECT; its payload is what "
            f"`analysis.serialization.document_report_to_dict` returns for it"
        )
    surface = "telemetry/record.py::classify_document"
    # L1-C17's override, asked of BOTH shapes. A single-account document can
    # carry a surfaced omission too (L1-S4 gives it a `document` block beside
    # today's payload), and an omission whose reason is not a ratified evidence
    # class is a publisher defect on ONE account exactly as it is on three. The
    # check runs before the shape branch so neither shape can walk past it.
    if deferred is None and isinstance(payload, Mapping) and DOCUMENT_KEY in payload:
        for omission in payload_document_block(
            payload, surface=surface).get("omitted_sections") or []:
            reason = omission.get("reason") if isinstance(omission, Mapping) else None
            if reason not in RATIFIED_OMISSION_REASONS:
                return "failed", "document_omission_unratified"
    if deferred is not None or not is_document_payload(payload):
        return classify_outcome(
            payload, error_type=error_type, error_reason=error_reason,
            deferred=deferred,
        )
    accounts = (payload.get("accounts") or []) if isinstance(payload, dict) else []
    if not accounts:
        # Refusing here rather than letting `payload_accounts` raise: an
        # outcome function that raises inside a run kills the record, and a
        # document that publishes no account is a finding to be FILED.
        return "failed", "document_publishes_no_account"
    per = [classify_outcome(account) for account in payload_accounts(payload, surface=surface)]
    for klass, _reason in per:
        if klass not in DOCUMENT_LADDER:
            # Ranking an unranked class LOWEST would make it the document's
            # class, and `discovery/compare.py::direction` scores an unranked
            # class as neither an improvement nor a regression — invisible to
            # the whole non-regression regime. Unreachable today (the
            # per-account call is made without `deferred=`), and a refusal is
            # what an unreachable state should get.
            raise ValueError(
                f"account outcome {klass!r} is not on the ladder; a document "
                f"fold over an unranked class would be invisible to the "
                f"non-regression regime"
            )
    omitted = payload_document_block(payload, surface=surface).get("omitted_sections") or []
    for omission in omitted:
        reason = omission.get("reason") if isinstance(omission, dict) else None
        if reason not in RATIFIED_OMISSION_REASONS:
            return "failed", "document_omission_unratified"
    # Printed order breaks ties: `min` is stable, so the FIRST account holding
    # the weakest rung supplies the reason, and printed order is printed
    # evidence about a sequence rather than a selection of one account.
    weakest = min(per, key=lambda pair: DOCUMENT_LADDER.index(pair[0]))
    if weakest[0] == "validated":
        # A ratified omission does NOT lower the document here. See the
        # docstring: the design proposed it, 15 batch-8 validated documents
        # carry one, and lowering them is a ruling (Q10) rather than a stage's
        # decision.
        return "validated", "approved"
    return weakest[0], f"account_{weakest[1]}"


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
    # The DOCUMENT's outcome. `classify_document` is `classify_outcome` on
    # every payload the tree publishes today (an account payload never reaches
    # the fold), so this record is byte-identical until a document publishes a
    # second account.
    outcome_class, reason = classify_document(
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
        # `diagnose_document` is `diagnose` verbatim on an account payload and
        # the per-account union on a document one, so a record never carries
        # one account's diagnosis under the document's name.
        #
        # `source_path_unrecognized_model` (F-7 / MAJOR-3,
        # PHASE2_P20SEAM_REVIEW.md) is added alongside `diagnose_document`'s
        # own closed taxonomy, not INTO it: it is read straight off `source`
        # (the already-built `source_section(doc)` dict this function
        # receives, `source["model"]` being `doc.model` verbatim) rather than
        # from the payload, so it is an orthogonal fact about PROVENANCE, not
        # a member of the payload-derived check taxonomy `telemetry/
        # diagnostics.py` owns and versions (`DIAGNOSTICS_VERSION`) — adding
        # it there would mean a new taxonomy member with no check behind it.
        "diagnostics": {
            **diagnose_document(payload, outcome_class),
            "source_path_unrecognized_model": source_path_unrecognized_model(
                source.get("model")
            ),
        },
    }

"""The per-document pipeline and the wave controller: render → models → assemble → gate → receipts.

Review closures (CEILING-HARNESS-REVIEW-X):
* BLOCK-1  public receipts carry counts/hashes only (the proposals module no longer emits digits).
* BLOCK-2  a wave with model endpoints refuses unless the declaration is remote (this experiment has
           no local serving path) AND the Stage A worker echoes the same provider/execution_class as
           the local declaration, before the first page.
* BLOCK-3  the data scope is bound to the manifest (`manifest_scope`) and must equal the context's.
* MAJOR-5  resume skips only receipts without a failure.
* MAJOR-6  an interrupted wave is receipted as `aborted` with controller_exit 1.
* MAJOR-7  weights (fetch receipts) and the prompt TEMPLATES are pinned in launch.json.
* RES-2    `skipped_existing` counts only resumed receipts; `--limit` is reported as `limited_out`.
* MINOR    Stage B wall span recorded beside the per-call sum; the wall time is named wave_wall_hours.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from vlm import HARNESS_VERSION
from vlm.assemble import CandidateRow, blocks_from_worker, rows_from_blocks, text_lines_from_blocks
from vlm.client import TransportError
from vlm.gate import GATE_VERSION, GateVerdict, gate
from vlm.metadata import EMPTY_META, AccountMeta, extract_meta, merge_meta, year_from_meta
from vlm.partitions import Member
from vlm.prompts import prompt_manifest, stage_b_prompt
from vlm.proposals import PageProposal, merge_pages
from vlm.receipts import Refused, dump_new, need, sha256_file, utc_now
from vlm.render import RenderedPage, render_document, render_settings
from vlm.schema import PAGE_PROPOSAL_SCHEMA, SCHEMA_VERSION, schema_sha256, validate_page_proposal
from vlm.truth import ReaderTruth, TruthAccount, match_rows

ARMS = ("reader_baseline", "stage_a_rules", "stage_b_only", "hybrid")
MODEL_ARMS = ("stage_a_rules", "stage_b_only", "hybrid")
MAX_PARSER_CONTEXT_CHARS = 10000   # DEV wave: one hybrid prompt exceeded the 16k context (http_400)
MAX_CONSECUTIVE_TRANSPORT_FAILURES = 3
PREFETCH_DEPTH = 2


@dataclass
class RunContext:
    arm: str
    stage_a: Any | None
    stage_b: Any | None
    stage_b_model: str
    truth: ReaderTruth | None
    long_edge: int
    quality: int
    seed: int
    data_scope: str
    hourly_rate: float | None
    concurrency: int = 1
    identity_client: Any | None = None   # a Stage A worker client used only for /version (defaults to stage_a)
    max_tokens: int = 12000   # DEV wave: dense pages exceeded 4,096 output tokens and were lost as invalid JSON
    doc_concurrency: int = 1   # documents in flight at once (each fans its pages out up to `concurrency`)


@dataclass(frozen=True)
class DocumentInput:
    member: Member
    raw: bytes


def default_authorize(data_scope: str) -> None:
    from ocr.paddle_config import check_remote_authorization, load_paddle_settings

    check_remote_authorization(load_paddle_settings(), data_scope)


def default_settings():
    from ocr.paddle_config import load_paddle_settings

    return load_paddle_settings()


def verify_identity(ctx: RunContext, settings) -> dict:
    """BLOCK-2: before any page moves, the declaration must be checkable. Model arms require a remote
    declaration (there is no local serving path in this experiment) and a worker echo equal to it."""
    declared = {"provider": str(getattr(settings, "provider", "")), "execution_class": str(getattr(settings, "execution_class", ""))}
    if ctx.arm not in MODEL_ARMS:
        return {"declared": declared, "checked": False}
    need(bool(getattr(settings, "is_remote", False)), "local_declaration_with_model_endpoints")
    probe = ctx.identity_client or ctx.stage_a
    need(probe is not None, "identity_probe_missing")
    echo = probe.version()
    need(isinstance(echo, dict), "vlm_identity_echo_shape")
    need(echo.get("provider") == declared["provider"] and echo.get("execution_class") == declared["execution_class"],
         "vlm_identity_mismatch")
    return {"declared": declared, "echo": {"provider": echo.get("provider"), "execution_class": echo.get("execution_class"),
                                           "retention": echo.get("retention"), "pipeline_version": echo.get("pipeline_version")},
            "checked": True}


MIN_PROMPT_TOKENS = 8192   # a dense hybrid page: 10k characters of parser context + the image + the template


def verify_stage_b_context(ctx: RunContext) -> dict:
    """CTRL wave: a Stage B server left at a 16k context refused every dense page as http_400 (prompt plus
    the 12,000 reserved completion tokens over the limit) and 10 of 114 documents failed. The served
    context must leave MIN_PROMPT_TOKENS once the completion budget is reserved; the launch records it."""
    limits_fn = getattr(ctx.stage_b, "model_limits", None) if ctx.stage_b is not None else None
    if limits_fn is None:
        return {"checked": False}
    try:
        limits = limits_fn()
    except TransportError as exc:
        raise Refused(f"stage_b_unreachable:{exc}") from None
    need(ctx.stage_b_model in limits, "stage_b_model_not_served")
    max_tokens = int(getattr(ctx, "max_tokens", 12000))
    context = limits[ctx.stage_b_model]
    if context is not None:
        need(context >= max_tokens + MIN_PROMPT_TOKENS, "stage_b_context_too_small")
    return {"checked": True, "max_model_len": context, "max_tokens": max_tokens, "min_prompt_tokens": MIN_PROMPT_TOKENS}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _parser_context(blocks) -> str:
    parts = []
    for block in blocks:
        parts.append(block.content if block.label == "table" else "\n".join(text_lines_from_blocks([block])))
    return "\n".join(parts)[:MAX_PARSER_CONTEXT_CHARS]


def _stage_a_pages(doc: DocumentInput, pages: list[RenderedPage], ctx: RunContext, timings: dict, private: dict):
    blocks_by_page = []
    for page in pages:
        started = time.perf_counter()
        raw = ctx.stage_a.parse_page(page.jpeg, request_id=f"{doc.member.sha[:16]}.p{page.index}", page_index=page.index)
        timings["stage_a_ms"] += (time.perf_counter() - started) * 1000.0
        blocks_by_page.append(blocks_from_worker(raw, page=page.index, width=page.width, height=page.height))
    private["stage_a_blocks"] = [[asdict(b) for b in blocks] for blocks in blocks_by_page]
    return blocks_by_page


def _stage_a_rows(blocks_by_page, *, fallback_year: int | None = None) -> tuple[list[CandidateRow], AccountMeta]:
    meta = EMPTY_META
    for blocks in blocks_by_page:
        meta = merge_meta(meta, extract_meta(text_lines_from_blocks(blocks)))
    year_hint = year_from_meta(meta) or fallback_year   # hybrid: the model's period supplies the year when the rules found none
    rows: list[CandidateRow] = []
    for blocks in blocks_by_page:
        rows.extend(rows_from_blocks(blocks, year_hint=year_hint))
    return rows, meta


def _stage_b_call(ctx: RunContext, page: RenderedPage, prompt: str):
    started = time.perf_counter()
    result = ctx.stage_b.chat(ctx.stage_b_model, prompt, image_jpeg=page.jpeg, schema=PAGE_PROPOSAL_SCHEMA, seed=ctx.seed,
                              max_tokens=getattr(ctx, 'max_tokens', 12000))
    return result, (time.perf_counter() - started) * 1000.0


def _stage_b_pages(doc: DocumentInput, pages: list[RenderedPage], ctx: RunContext, timings: dict, private: dict,
                   contexts: list[str] | None) -> list[PageProposal]:
    """One structured call per page. Pages of a document are sent concurrently up to `ctx.concurrency`
    (vLLM batches them); results are consumed in page order so receipts stay deterministic."""
    proposals: list[PageProposal] = []
    texts = []
    prompts = [stage_b_prompt(parser_context=contexts[position] if contexts else None,
                              page_number=position + 1, page_total=len(pages)) for position in range(len(pages))]
    workers = max(1, int(getattr(ctx, "concurrency", 1) or 1))
    span_started = time.perf_counter()
    if workers > 1 and len(pages) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(workers, len(pages))) as pool:
            calls = list(pool.map(lambda pair: _stage_b_call(ctx, pair[0], pair[1]), zip(pages, prompts)))
    else:
        calls = [_stage_b_call(ctx, page, prompt) for page, prompt in zip(pages, prompts)]
    timings["stage_b_wall_ms"] += (time.perf_counter() - span_started) * 1000.0
    for page, (result, call_ms) in zip(pages, calls):
        timings["stage_b_ms"] += call_ms
        timings["prompt_tokens"] += result.prompt_tokens
        timings["completion_tokens"] += result.completion_tokens
        if result.parsed is None:
            proposals.append(PageProposal(page.index, {}, (result.parse_error or "json_invalid",)))
        else:
            errors = tuple(validate_page_proposal(result.parsed))
            proposals.append(PageProposal(page.index, result.parsed, errors))
        texts.append({"page": page.index, "finish_reason": result.finish_reason, "request_sha256": result.request_sha256,
                      "response_sha256": result.response_sha256, "content_sha256": result.content_sha256, "text": result.text})
    private["stage_b"] = texts
    private["stage_b_content_hashes"] = [t["content_sha256"] for t in texts]
    return proposals


ANCHOR_FIELDS = ("beginning_balance", "ending_balance", "stated_total_credits", "stated_total_debits")


def _corroborate(model_meta: AccountMeta, rule_meta: AccountMeta) -> dict:
    """Per anchor field: agree | disagree | model_only | rules_only | absent. Summary: 'disagreement' if
    any field disagrees; 'corroborated' if beginning and ending both agree; 'partial' if one of them
    agrees; 'model_only' if the rules read neither; 'rules_only' if the model read neither; else 'absent'."""
    fields: dict[str, str] = {}
    for name in ANCHOR_FIELDS:
        a, b = getattr(model_meta, name), getattr(rule_meta, name)
        if a is None and b is None:
            fields[name] = "absent"
        elif a is None:
            fields[name] = "rules_only"
        elif b is None:
            fields[name] = "model_only"
        else:
            fields[name] = "agree" if abs(a) == abs(b) else "disagree"
    model_period = model_meta.period_end or model_meta.period_start
    rule_period = rule_meta.period_end or rule_meta.period_start
    if model_period is None and rule_period is None:
        fields["period_year"] = "absent"
    elif model_period is None:
        fields["period_year"] = "rules_only"
    elif rule_period is None:
        fields["period_year"] = "model_only"
    else:   # gate v5: a model period year the printed text contradicts is a disagreement
        fields["period_year"] = "agree" if model_period[:4] == rule_period[:4] else "disagree"
    anchors = (fields["beginning_balance"], fields["ending_balance"])
    if "disagree" in fields.values():
        summary = "disagreement"
    elif anchors == ("agree", "agree"):
        summary = "corroborated"
    elif "agree" in anchors:
        summary = "partial"
    elif all(v in ("model_only", "absent") for v in anchors) and "model_only" in anchors:
        summary = "model_only"
    elif all(v in ("rules_only", "absent") for v in anchors) and "rules_only" in anchors:
        summary = "rules_only"
    else:
        summary = "absent"
    return {"summary": summary, "fields": fields}


def _truth_account(accounts: list[TruthAccount], meta: AccountMeta) -> TruthAccount | None:
    if not accounts:
        return None
    if meta.account_last4:
        for account in accounts:
            if account.account_number and str(account.account_number)[-4:] == meta.account_last4:
                return account
    return accounts[0]


def process_document(doc: DocumentInput, ctx: RunContext) -> tuple[dict, dict]:
    started = time.perf_counter()
    timings = {"render_ms": 0.0, "encode_ms": 0.0, "stage_a_ms": 0.0, "stage_b_ms": 0.0, "stage_b_wall_ms": 0.0,
               "gate_ms": 0.0, "prompt_tokens": 0, "completion_tokens": 0}
    public: dict[str, Any] = {"sha": doc.member.sha, "arm": ctx.arm, "harness_version": HARNESS_VERSION,
                              "reader_outcome": doc.member.outcome_class, "family": doc.member.folder_label}
    private: dict[str, Any] = {"sha": doc.member.sha, "arm": ctx.arm}
    if ctx.arm == "reader_baseline":
        public.update({"pages": doc.member.page_count, "page_hashes": [], "rows_proposed": 0, "gate": None,
                       "timings": timings, "stats": {}, "match": None, "agreement": None, "failure": None})
        return public, private
    pages = render_document(doc.raw, long_edge=ctx.long_edge, quality=ctx.quality)
    timings["render_ms"] = sum(p.render_ms for p in pages)
    timings["encode_ms"] = sum(p.encode_ms for p in pages)
    public["pages"] = len(pages)
    public["page_hashes"] = [p.jpeg_sha256 for p in pages]
    public["upload_bytes"] = sum(len(p.jpeg) for p in pages)
    stats: dict[str, Any] = {}
    agreement = None
    if ctx.arm == "stage_a_rules":
        blocks_by_page = _stage_a_pages(doc, pages, ctx, timings, private)
        rows, meta = _stage_a_rows(blocks_by_page)
    elif ctx.arm == "stage_b_only":
        proposals = _stage_b_pages(doc, pages, ctx, timings, private, None)
        rows, meta, stats = merge_pages(proposals)
        private["proposals"] = [asdict(p) for p in proposals]
    elif ctx.arm == "hybrid":
        blocks_by_page = _stage_a_pages(doc, pages, ctx, timings, private)
        contexts = [_parser_context(blocks) for blocks in blocks_by_page]
        proposals = _stage_b_pages(doc, pages, ctx, timings, private, contexts)
        rows, meta, stats = merge_pages(proposals)
        private["proposals"] = [asdict(p) for p in proposals]
        a_rows, a_meta = _stage_a_rows(blocks_by_page, fallback_year=year_from_meta(meta))
        # RR-1: the rule reading is the independent witness for the model's claimed anchors. Agreement is
        # recorded per field; a disagreement refuses; a model-only anchor is admitted but counted apart.
        corroboration = _corroborate(meta, a_meta)
        stats["anchor_corroboration"] = corroboration["summary"]
        stats["anchor_fields"] = corroboration["fields"]
        private["meta_stage_b"] = _jsonable(meta)
        private["meta_rules"] = _jsonable(a_meta)
        meta = merge_meta(meta, a_meta)
        keys = {(r.date, r.amount, r.direction) for r in rows}
        agreement = {"stage_a_rows": len(a_rows), "stage_b_rows": len(rows),
                     "matched": sum(1 for r in a_rows if (r.date, r.amount, r.direction) in keys)}
    else:
        raise Refused("arm_unknown")
    if ctx.arm == "stage_b_only":
        stats["anchor_corroboration"] = "model_only"
    gate_started = time.perf_counter()
    extra_reasons: list[str] = []
    if stats.get("currency_conflict"):
        extra_reasons.append("currency_conflict")
    if stats.get("anchor_corroboration") == "disagreement":
        extra_reasons.append("anchor_disagreement")
    admitted_candidate = None
    if ctx.arm == "hybrid":
        from vlm.candidates import gate_candidates

        verdict, admitted_candidate, candidate_reasons = gate_candidates(rows, a_rows, meta, extra_reasons=tuple(extra_reasons))
        stats["candidate_reasons"] = candidate_reasons
        if verdict.admitted:
            rows = list(verdict.admitted_rows)   # the admitted set is what the truth comparison must see
    else:
        verdict = gate(rows, meta)
        missing = tuple(r for r in extra_reasons if r not in verdict.reasons)
        if missing:
            verdict = GateVerdict(False, verdict.reasons + missing, verdict.row_count, (), verdict.computed_ending,
                                  verdict.continuity_breaks, verdict.chain_derived_directions, verdict.checks, verdict.anchored)
    timings["gate_ms"] = (time.perf_counter() - gate_started) * 1000.0
    match = None
    if ctx.truth is not None:
        accounts = ctx.truth.accounts(doc.member.sha)
        account = _truth_account(accounts or [], meta)
        if account is not None:
            match = asdict(match_rows(rows, account))
            match["truth_accounts"] = len(accounts or [])
    timings["total_ms"] = (time.perf_counter() - started) * 1000.0
    public.update({
        "rows_proposed": len(rows),
        "gate": {"admitted": verdict.admitted, "reasons": list(verdict.reasons), "row_count": verdict.row_count,
                 "continuity_breaks": verdict.continuity_breaks, "chain_derived_directions": verdict.chain_derived_directions,
                 "derived": verdict.checks.get("derived", []), "anchored": verdict.anchored,
                 "repeats": verdict.checks.get("repeats"), "summary_ok": verdict.checks.get("summary_ok"),
                 "admitted_candidate": admitted_candidate, "gate_version": GATE_VERSION},
        "meta_sources": list(meta.sources), "timings": timings, "stats": stats, "match": match, "agreement": agreement,
        "stage_b_content_hashes": private.get("stage_b_content_hashes", []),
        "failure": None,
    })
    private.update({"rows": _jsonable(rows), "meta": _jsonable(meta), "gate_checks": _jsonable(verdict.checks)})
    return public, private


def _load(member: Member, archive_root: Path) -> DocumentInput:
    return DocumentInput(member, (Path(archive_root) / member.relative_path).read_bytes())


def _model_identity(ctx: RunContext) -> dict:
    identity: dict[str, Any] = {"stage_b_model": ctx.stage_b_model if ctx.stage_b is not None else None}
    if ctx.stage_a is not None:
        identity["stage_a"] = ctx.stage_a.version()
    if ctx.stage_b is not None:
        identity["stage_b_models_served"] = ctx.stage_b.models()
    return identity


def _executing_tip() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _failure_receipt(out: Path, sha: str, arm: str, klass: str, code: str) -> None:
    dump_new(out / "results" / f"{sha}.json", {"sha": sha, "arm": arm, "failure": {"class": klass, "code": code}})


def _completed_shas(resume_from: Path) -> set[str]:
    """MAJOR-5: only receipts WITHOUT a failure count as done."""
    done: set[str] = set()
    for path in (Path(resume_from) / "results").glob("*.json"):
        if path.name.endswith(".private.json"):
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if receipt.get("failure") is None and receipt.get("sha"):
            done.add(receipt["sha"])
    return done


def run_wave(members: list[Member], ctx: RunContext, out_dir: Path, *, archive_root: Path, manifest_binding: dict,
             manifest_scope: str, limit: int | None = None, authorize: Callable[[str], None] | None = None,
             git_tip: str | None = None, resume_from: Path | list[Path] | None = None, settings=None,
             weights: dict | None = None) -> dict:
    need(ctx.arm in ARMS, "arm_unknown")
    need(manifest_scope == ctx.data_scope, "data_scope_disagrees_with_manifest")
    out = Path(out_dir)
    need(not os.path.lexists(out), "wave_already_attempted")
    (authorize or default_authorize)(ctx.data_scope)
    if settings is None and ctx.arm in MODEL_ARMS:
        settings = default_settings()
    identity = verify_identity(ctx, settings)
    stage_b_context = verify_stage_b_context(ctx)
    out.mkdir(parents=True)
    (out / "results").mkdir()
    resumes = [Path(p) for p in (resume_from if isinstance(resume_from, (list, tuple)) else ([resume_from] if resume_from else []))]
    existing: set[str] = set().union(*(_completed_shas(p) for p in resumes)) if resumes else set()
    launch = {
        "arm": ctx.arm, "harness_version": HARNESS_VERSION, "manifest": manifest_binding, "manifest_scope": manifest_scope,
        "models": _model_identity(ctx), "weights": weights or {}, "identity": identity, "stage_b_context": stage_b_context,
        "render": {**render_settings(), "long_edge": ctx.long_edge, "jpeg_quality": ctx.quality},
        "schema": {"version": SCHEMA_VERSION, "sha256": schema_sha256()},
        "prompt": prompt_manifest(),
        "gate_version": GATE_VERSION, "seed": ctx.seed, "data_scope": ctx.data_scope, "concurrency": ctx.concurrency,
        "max_tokens": getattr(ctx, "max_tokens", 12000),
        "executing_tip": git_tip or _executing_tip(), "started_at": utc_now(), "requested": len(members),
        "limit": limit, "resume_from": (str(resumes[0]) if len(resumes) == 1 else [str(p) for p in resumes]) if resumes else None,
        "doc_concurrency": max(1, int(getattr(ctx, "doc_concurrency", 1) or 1)),
    }
    dump_new(out / "launch.json", launch)
    remaining = [m for m in members if m.sha not in existing]
    todo = remaining[: limit if limit is not None else None]
    counts = {"requested": len(members), "attempted": 0, "admitted": 0, "refused_by_gate": 0, "failed": 0,
              "skipped_existing": len(members) - len(remaining), "limited_out": len(remaining) - len(todo),
              "reader_validated": sum(1 for m in members if m.outcome_class == "validated")}
    totals = {"render_ms": 0.0, "encode_ms": 0.0, "stage_a_ms": 0.0, "stage_b_ms": 0.0, "stage_b_wall_ms": 0.0, "gate_ms": 0.0,
              "total_ms": 0.0, "pages": 0, "upload_bytes": 0, "prompt_tokens": 0, "completion_tokens": 0}
    loaded: queue.Queue = queue.Queue(maxsize=PREFETCH_DEPTH)

    def producer() -> None:
        for member in todo:
            try:
                loaded.put(("ok", _load(member, archive_root)))
            except OSError as exc:
                loaded.put(("error", (member, type(exc).__name__)))
        loaded.put(("done", None))

    threading.Thread(target=producer, daemon=True).start()
    status, failure_code, failure_class = "complete", None, None
    consecutive_transport = 0
    wall_started = time.perf_counter()
    # Documents are pipelined up to `ctx.doc_concurrency` at a time, each fanning its pages out up to
    # `ctx.concurrency`: on the 96 GB card the server idled between documents when they ran one at a time.
    # Receipts are written and counted in this thread only, in completion order; exclusive-create keeps
    # them one per document.
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    doc_workers = max(1, int(getattr(ctx, "doc_concurrency", 1) or 1))
    stop_submitting = False

    def work(doc: DocumentInput) -> tuple:
        try:
            public, private = process_document(doc, ctx)
            return ("ok", doc, public, private)
        except TransportError as exc:
            return ("transport", doc, str(exc))
        except Exception as exc:  # noqa: BLE001 — recorded per document, never silent
            return ("error", doc, type(exc).__name__, getattr(exc, "code", "unexpected_failure"))

    def record(outcome: tuple) -> None:
        nonlocal consecutive_transport, status, failure_code, failure_class, stop_submitting
        kind, doc = outcome[0], outcome[1]
        if kind == "ok":
            public, private = outcome[2], outcome[3]
            consecutive_transport = 0
            dump_new(out / "results" / f"{doc.member.sha}.json", public)
            dump_new(out / "results" / f"{doc.member.sha}.private.json", _jsonable(private))
            if public.get("gate"):
                counts["admitted" if public["gate"]["admitted"] else "refused_by_gate"] += 1
            for key in totals:
                if key in ("pages", "upload_bytes"):
                    totals[key] += public.get(key, 0) or 0
                else:
                    totals[key] += public["timings"].get(key, 0) or 0
        elif kind == "transport":
            consecutive_transport += 1
            counts["failed"] += 1
            _failure_receipt(out, doc.member.sha, ctx.arm, "TransportError", outcome[2])
            if consecutive_transport >= MAX_CONSECUTIVE_TRANSPORT_FAILURES:
                status, failure_code, failure_class = "failed", "transport_failing", "TransportError"
                stop_submitting = True
        else:
            counts["failed"] += 1
            _failure_receipt(out, doc.member.sha, ctx.arm, outcome[2], outcome[3])

    try:
        with ThreadPoolExecutor(max_workers=doc_workers) as pool:
            in_flight: set = set()
            while not stop_submitting:
                kind, item = loaded.get()
                if kind == "done":
                    break
                if kind == "error":
                    member, klass = item
                    counts["failed"] += 1
                    _failure_receipt(out, member.sha, ctx.arm, klass, "document_unreadable")
                    continue
                doc: DocumentInput = item
                counts["attempted"] += 1
                in_flight.add(pool.submit(work, doc))
                while len(in_flight) >= doc_workers and not stop_submitting:
                    done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
                    for future in done:
                        record(future.result())
            while in_flight:
                done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)
                for future in done:
                    record(future.result())
    except BaseException as exc:  # MAJOR-6: an interrupted or crashed controller is receipted as aborted
        status = "aborted"
        failure_code = "interrupted" if isinstance(exc, KeyboardInterrupt) else "controller_failure"
        failure_class = type(exc).__name__
        raise
    finally:
        wall_s = time.perf_counter() - wall_started
        hours = wall_s / 3600.0
        result = {**launch, "status": status, "failure_code": failure_code, "failure_class": failure_class, "counts": counts,
                  "timings": totals, "wall_s": wall_s, "wave_wall_hours": hours,
                  "cost_usd": (hours * ctx.hourly_rate) if ctx.hourly_rate else "rate not measured", "finished_at": utc_now()}
        dump_new(out / "result.json", result)
        dump_new(out / "release.json", {"arm": ctx.arm, "controller_exit": 0 if status == "complete" else 1,
                                        "result_sha256": sha256_file(out / "result.json")})
    return result

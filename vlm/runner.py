"""The per-document pipeline and the wave controller: render → models → assemble → gate → receipts."""
from __future__ import annotations

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
from vlm.prompts import PROMPT_VERSION, prompt_sha256, stage_b_prompt
from vlm.proposals import PageProposal, merge_pages
from vlm.receipts import Refused, dump_new, need, sha256_file, utc_now
from vlm.render import RenderedPage, render_document, render_settings
from vlm.schema import PAGE_PROPOSAL_SCHEMA, SCHEMA_VERSION, schema_sha256, validate_page_proposal
from vlm.truth import ReaderTruth, TruthAccount, match_rows

ARMS = ("reader_baseline", "stage_a_rules", "stage_b_only", "hybrid")
MAX_PARSER_CONTEXT_CHARS = 12000
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


@dataclass(frozen=True)
class DocumentInput:
    member: Member
    raw: bytes


def default_authorize(data_scope: str) -> None:
    from ocr.paddle_config import check_remote_authorization, load_paddle_settings

    check_remote_authorization(load_paddle_settings(), data_scope)


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


def _stage_a_rows(blocks_by_page) -> tuple[list[CandidateRow], AccountMeta]:
    meta = EMPTY_META
    for blocks in blocks_by_page:
        meta = merge_meta(meta, extract_meta(text_lines_from_blocks(blocks)))
    year_hint = year_from_meta(meta)
    rows: list[CandidateRow] = []
    for blocks in blocks_by_page:
        rows.extend(rows_from_blocks(blocks, year_hint=year_hint))
    return rows, meta


def _stage_b_call(ctx: RunContext, page: RenderedPage, prompt: str):
    started = time.perf_counter()
    result = ctx.stage_b.chat(ctx.stage_b_model, prompt, image_jpeg=page.jpeg, schema=PAGE_PROPOSAL_SCHEMA, seed=ctx.seed)
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
    if workers > 1 and len(pages) > 1:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(workers, len(pages))) as pool:
            calls = list(pool.map(lambda pair: _stage_b_call(ctx, pair[0], pair[1]), zip(pages, prompts)))
    else:
        calls = [_stage_b_call(ctx, page, prompt) for page, prompt in zip(pages, prompts)]
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
                      "response_sha256": result.response_sha256, "text": result.text})
    private["stage_b"] = texts
    return proposals


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
    timings = {"render_ms": 0.0, "encode_ms": 0.0, "stage_a_ms": 0.0, "stage_b_ms": 0.0, "gate_ms": 0.0,
               "prompt_tokens": 0, "completion_tokens": 0}
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
        a_rows, a_meta = _stage_a_rows(blocks_by_page)
        meta = merge_meta(meta, a_meta)
        keys = {(r.date, r.amount, r.direction) for r in rows}
        agreement = {"stage_a_rows": len(a_rows), "stage_b_rows": len(rows),
                     "matched": sum(1 for r in a_rows if (r.date, r.amount, r.direction) in keys)}
    else:
        raise Refused("arm_unknown")
    gate_started = time.perf_counter()
    verdict: GateVerdict = gate(rows, meta)
    if stats.get("currency_conflict") and "currency_conflict" not in verdict.reasons:
        verdict = GateVerdict(False, verdict.reasons + ("currency_conflict",), verdict.row_count, (), verdict.computed_ending,
                              verdict.continuity_breaks, verdict.chain_derived_directions, verdict.checks)
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
                 "derived": verdict.checks.get("derived", []), "gate_version": GATE_VERSION},
        "meta_sources": list(meta.sources), "timings": timings, "stats": stats, "match": match, "agreement": agreement,
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


def run_wave(members: list[Member], ctx: RunContext, out_dir: Path, *, archive_root: Path, manifest_binding: dict,
             limit: int | None = None, authorize: Callable[[str], None] | None = None, git_tip: str | None = None,
             resume_from: Path | None = None) -> dict:
    need(ctx.arm in ARMS, "arm_unknown")
    out = Path(out_dir)
    need(not os.path.lexists(out), "wave_already_attempted")
    (authorize or default_authorize)(ctx.data_scope)
    out.mkdir(parents=True)
    (out / "results").mkdir()
    existing: set[str] = set()
    if resume_from is not None:
        existing = {p.name[:-5] for p in (Path(resume_from) / "results").glob("*.json") if not p.name.endswith(".private.json")}
    launch = {
        "arm": ctx.arm, "harness_version": HARNESS_VERSION, "manifest": manifest_binding, "models": _model_identity(ctx),
        "render": {**render_settings(), "long_edge": ctx.long_edge, "jpeg_quality": ctx.quality},
        "schema": {"version": SCHEMA_VERSION, "sha256": schema_sha256()},
        "prompt": {"version": PROMPT_VERSION, "sha256": prompt_sha256(stage_b_prompt(page_number=1, page_total=1))},
        "gate_version": GATE_VERSION, "seed": ctx.seed, "data_scope": ctx.data_scope,
        "executing_tip": git_tip or _executing_tip(), "started_at": utc_now(), "requested": len(members),
        "limit": limit, "resume_from": str(resume_from) if resume_from else None,
    }
    dump_new(out / "launch.json", launch)
    counts = {"requested": len(members), "attempted": 0, "admitted": 0, "refused_by_gate": 0, "failed": 0,
              "skipped_existing": 0, "reader_validated": sum(1 for m in members if m.outcome_class == "validated")}
    totals = {"render_ms": 0.0, "encode_ms": 0.0, "stage_a_ms": 0.0, "stage_b_ms": 0.0, "gate_ms": 0.0, "total_ms": 0.0,
              "pages": 0, "upload_bytes": 0, "prompt_tokens": 0, "completion_tokens": 0}
    todo = [m for m in members if m.sha not in existing][: limit if limit is not None else None]
    counts["skipped_existing"] = len(members) - len(todo)
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
    try:
        while True:
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
            try:
                public, private = process_document(doc, ctx)
                consecutive_transport = 0
            except TransportError as exc:
                consecutive_transport += 1
                counts["failed"] += 1
                _failure_receipt(out, doc.member.sha, ctx.arm, "TransportError", str(exc))
                if consecutive_transport >= MAX_CONSECUTIVE_TRANSPORT_FAILURES:
                    status, failure_code, failure_class = "failed", "transport_failing", "TransportError"
                    break
                continue
            except Exception as exc:  # noqa: BLE001 — recorded per document, never silent
                counts["failed"] += 1
                _failure_receipt(out, doc.member.sha, ctx.arm, type(exc).__name__, getattr(exc, "code", "unexpected_failure"))
                continue
            dump_new(out / "results" / f"{doc.member.sha}.json", public)
            dump_new(out / "results" / f"{doc.member.sha}.private.json", _jsonable(private))
            if public.get("gate"):
                counts["admitted" if public["gate"]["admitted"] else "refused_by_gate"] += 1
            for key in totals:
                if key in ("pages", "upload_bytes"):
                    totals[key] += public.get(key, 0) or 0
                else:
                    totals[key] += public["timings"].get(key, 0) or 0
    finally:
        wall_s = time.perf_counter() - wall_started
        hours = wall_s / 3600.0
        result = {**launch, "status": status, "failure_code": failure_code, "failure_class": failure_class, "counts": counts,
                  "timings": totals, "wall_s": wall_s, "instance_hours": hours,
                  "cost_usd": (hours * ctx.hourly_rate) if ctx.hourly_rate else "rate not measured", "finished_at": utc_now()}
        dump_new(out / "result.json", result)
        dump_new(out / "release.json", {"arm": ctx.arm, "controller_exit": 0 if status == "complete" else 1,
                                        "result_sha256": sha256_file(out / "result.json")})
    return result

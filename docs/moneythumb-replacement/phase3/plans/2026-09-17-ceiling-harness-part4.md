# Phase 3 Ceiling Experiment — Offline Harness Implementation Plan (part 4 of 4)

> Continues parts 1–3 (header, Global Constraints, File Structure apply verbatim). Tasks 14–16: the runner with receipts and render prefetch, the report, the CLI. Ends with the self-review checklist.

---

### Task 14: Runner — arms, per-document pipeline, receipts, prefetch, resume

**Files:**
- Create: `vlm/runner.py`
- Test: `tests/test_vlm_runner.py`

**Interfaces:**
- Consumes: everything from Tasks 1–13; `ocr.paddle_config.load_paddle_settings`, `check_remote_authorization`, `DATA_SCOPE_CUSTOMER`, `DATA_SCOPE_SYNTHETIC`; `vlm.partitions.Member`.
- Produces: `ARMS = ("reader_baseline", "stage_a_rules", "stage_b_only", "hybrid")`, `RunContext` dataclass, `DocumentInput` dataclass, `process_document(doc, ctx) -> tuple[dict, dict]` (public receipt, private receipt), `run_wave(members, ctx, out_dir, *, archive_root, manifest_binding, limit=None, authorize=None, git_tip=None) -> dict` (the result receipt), `default_authorize(data_scope) -> None`.

Receipt layout of a wave directory (exclusive-create, never reused):

```
<out_dir>/launch.json            arm, manifest binding, models, render/schema/prompt/gate versions, data_scope, started_at
<out_dir>/results/<SHA>.json     public per-document receipt (hashes, counts, timings, verdict codes)
<out_dir>/results/<SHA>.private.json   rows, metadata, proposals, blocks (customer content; gitignored)
<out_dir>/result.json            {**launch, status, counts, timings, hours, cost, finished_at}
<out_dir>/release.json           {controller_exit, result_sha256, arm}
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_runner.py
import json
from decimal import Decimal
from pathlib import Path

import pytest

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from vlm import runner
from vlm.partitions import Member
from vlm.schema import empty_proposal

SHA = "F" * 64


def _table_html(n=4):
    rows = "".join(f"<tr><td>2031-01-{i:02d}</td><td>SYNTHETIC ROW {i:02d}</td><td>{i*10:.2f}</td><td>{500 + sum(range(1, i+1))*10:.2f}</td></tr>" for i in range(1, n + 1))
    return f"<table><tr><th>Date</th><th>Description</th><th>Deposits</th><th>Balance</th></tr>{rows}</table>"


class FakeStageA:
    def __init__(self):
        self.calls = 0

    def version(self):
        return {"model": "fake-parser", "pipeline_version": "v1.6"}

    def parse_page(self, jpeg, *, request_id, page_index):
        self.calls += 1
        return {"blocks": [
            {"label": "text", "bbox": [0, 0, 100, 10], "content": "Beginning Balance 500.00\nEnding Balance 600.00\nStatement Period 01/01/2031 - 01/31/2031", "order": 0},
            {"label": "table", "bbox": [0, 20, 100, 90], "content": _table_html(), "order": 1}],
            "timing": {"total_ms": 2.0}}


class FakeStageB:
    def __init__(self, good=True):
        self.good = good
        self.calls = 0

    def models(self):
        return ["fake-vlm"]

    def chat(self, model, prompt, *, image_jpeg=None, schema=None, **kwargs):
        from vlm.client import ChatResult
        self.calls += 1
        proposal = empty_proposal("statement_page")
        proposal["account"].update({"beginning_balance": 500.0, "ending_balance": 600.0 if self.good else 601.0,
                                    "period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"})
        balance = 500.0
        for i in range(1, 5):
            balance += i * 10
            proposal["rows"].append({"date": f"2031-01-{i:02d}", "date_text": f"01/{i:02d}", "description": f"SYNTHETIC ROW {i:02d}",
                                     "amount": float(i * 10), "direction": "credit", "balance": balance, "section_index": None,
                                     "continues_previous": False, "box": None})
        text = json.dumps(proposal)
        return ChatResult(text=text, parsed=proposal, parse_error=None, finish_reason="stop", prompt_tokens=100,
                          completion_tokens=50, total_ms=3.0, request_sha256="a" * 64, response_sha256="b" * 64)


def _member(tmp_path) -> tuple[Member, Path]:
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "doc.pdf").write_bytes(render_native_pdf(build_ledger_page(n_rows=4)))
    return Member(SHA, "fam/doc.pdf", 100, 1, "fam", "validated", 1), archive


def _ctx(arm, stage_a=None, stage_b=None):
    return runner.RunContext(arm=arm, stage_a=stage_a, stage_b=stage_b, stage_b_model="fake-vlm", truth=None,
                             long_edge=800, quality=85, seed=0, data_scope="synthetic", hourly_rate=None)


def test_stage_a_rules_arm_admits_synthetic_ledger(tmp_path):
    member, archive = _member(tmp_path)
    ctx = _ctx("stage_a_rules", stage_a=FakeStageA())
    result = runner.run_wave([member], ctx, tmp_path / "wave", archive_root=archive, manifest_binding={"path": "m", "sha256": "0" * 64},
                             authorize=lambda scope: None, git_tip="deadbeef")
    assert result["status"] == "complete" and result["counts"]["admitted"] == 1 and result["counts"]["attempted"] == 1
    public = json.loads((tmp_path / "wave" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["gate"]["admitted"] and public["rows_proposed"] == 4 and public["pages"] == 1
    assert public["timings"]["stage_a_ms"] >= 0 and len(public["page_hashes"]) == 1
    assert "fam/doc.pdf" not in json.dumps(public)
    private = json.loads((tmp_path / "wave" / "results" / f"{SHA}.private.json").read_text(encoding="utf-8"))
    assert private["rows"][0]["amount"] == "10.00" and private["meta"]["beginning_balance"] == "500.00"
    assert (tmp_path / "wave" / "release.json").exists() and (tmp_path / "wave" / "launch.json").exists()


def test_stage_b_and_hybrid_arms(tmp_path):
    member, archive = _member(tmp_path)
    b = FakeStageB()
    result = runner.run_wave([member], _ctx("stage_b_only", stage_b=b), tmp_path / "w1", archive_root=archive,
                             manifest_binding={"path": "m", "sha256": "0" * 64}, authorize=lambda s: None, git_tip="x")
    assert result["counts"]["admitted"] == 1 and b.calls == 1
    a = FakeStageA()
    result = runner.run_wave([member], _ctx("hybrid", stage_a=a, stage_b=FakeStageB()), tmp_path / "w2", archive_root=archive,
                             manifest_binding={"path": "m", "sha256": "0" * 64}, authorize=lambda s: None, git_tip="x")
    assert result["counts"]["admitted"] == 1 and a.calls == 1
    public = json.loads((tmp_path / "w2" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["agreement"]["stage_a_rows"] == 4 and public["agreement"]["matched"] == 4


def test_gate_refusal_is_recorded_not_raised(tmp_path):
    member, archive = _member(tmp_path)
    result = runner.run_wave([member], _ctx("stage_b_only", stage_b=FakeStageB(good=False)), tmp_path / "w", archive_root=archive,
                             manifest_binding={"path": "m", "sha256": "0" * 64}, authorize=lambda s: None, git_tip="x")
    assert result["counts"]["admitted"] == 0 and result["counts"]["refused_by_gate"] == 1
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert "sum_mismatch" in public["gate"]["reasons"]


def test_reader_baseline_arm_needs_no_models(tmp_path):
    member, archive = _member(tmp_path)
    result = runner.run_wave([member], _ctx("reader_baseline"), tmp_path / "w", archive_root=archive,
                             manifest_binding={"path": "m", "sha256": "0" * 64}, authorize=lambda s: None, git_tip="x")
    public = json.loads((tmp_path / "w" / "results" / f"{SHA}.json").read_text(encoding="utf-8"))
    assert public["reader_outcome"] == "validated" and result["counts"]["reader_validated"] == 1


def test_resume_skips_existing_and_wave_dir_is_never_reused(tmp_path):
    member, archive = _member(tmp_path)
    ctx = _ctx("stage_a_rules", stage_a=FakeStageA())
    runner.run_wave([member], ctx, tmp_path / "w", archive_root=archive, manifest_binding={"path": "m", "sha256": "0" * 64},
                    authorize=lambda s: None, git_tip="x")
    with pytest.raises(runner.Refused) as exc:
        runner.run_wave([member], ctx, tmp_path / "w", archive_root=archive, manifest_binding={"path": "m", "sha256": "0" * 64},
                        authorize=lambda s: None, git_tip="x")
    assert exc.value.code == "wave_already_attempted"
    result = runner.run_wave([member], ctx, tmp_path / "w2", archive_root=archive, manifest_binding={"path": "m", "sha256": "0" * 64},
                             authorize=lambda s: None, git_tip="x", resume_from=tmp_path / "w")
    assert result["counts"]["skipped_existing"] == 1 and result["counts"]["attempted"] == 0


def test_transport_failure_recorded_and_aborts_after_three(tmp_path):
    from vlm.client import TransportError

    class Broken:
        def version(self):
            return {}

        def parse_page(self, *a, **k):
            raise TransportError("connection_failed:ConnectionRefusedError")

    members = [Member(f"{i:064X}", "fam/doc.pdf", 100, 1, "fam", "failed", 1) for i in range(5)]
    _, archive = _member(tmp_path)
    result = runner.run_wave(members, _ctx("stage_a_rules", stage_a=Broken()), tmp_path / "w", archive_root=archive,
                             manifest_binding={"path": "m", "sha256": "0" * 64}, authorize=lambda s: None, git_tip="x")
    assert result["status"] == "failed" and result["failure_code"] == "transport_failing" and result["counts"]["failed"] == 3


def test_authorize_is_called_with_scope(tmp_path):
    member, archive = _member(tmp_path)
    seen = []
    runner.run_wave([member], _ctx("stage_a_rules", stage_a=FakeStageA()), tmp_path / "w", archive_root=archive,
                    manifest_binding={"path": "m", "sha256": "0" * 64}, authorize=lambda s: seen.append(s), git_tip="x")
    assert seen == ["synthetic"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_runner.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.runner'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/runner.py
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
from vlm.receipts import Refused, bound, dump_new, need, sha256_file, utc_now
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


def _stage_b_pages(doc: DocumentInput, pages: list[RenderedPage], ctx: RunContext, timings: dict, private: dict,
                   contexts: list[str] | None) -> list[PageProposal]:
    proposals: list[PageProposal] = []
    texts = []
    for position, page in enumerate(pages):
        prompt = stage_b_prompt(parser_context=contexts[position] if contexts else None, page_number=position + 1, page_total=len(pages))
        started = time.perf_counter()
        result = ctx.stage_b.chat(ctx.stage_b_model, prompt, image_jpeg=page.jpeg, schema=PAGE_PROPOSAL_SCHEMA, seed=ctx.seed)
        timings["stage_b_ms"] += (time.perf_counter() - started) * 1000.0
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
                dump_new(out / "results" / f"{member.sha}.json", {"sha": member.sha, "arm": ctx.arm, "failure": {"class": klass, "code": "document_unreadable"}})
                continue
            doc: DocumentInput = item
            counts["attempted"] += 1
            try:
                public, private = process_document(doc, ctx)
                consecutive_transport = 0
            except TransportError as exc:
                consecutive_transport += 1
                counts["failed"] += 1
                dump_new(out / "results" / f"{doc.member.sha}.json", {"sha": doc.member.sha, "arm": ctx.arm, "failure": {"class": "TransportError", "code": str(exc)}})
                if consecutive_transport >= MAX_CONSECUTIVE_TRANSPORT_FAILURES:
                    status, failure_code, failure_class = "failed", "transport_failing", "TransportError"
                    break
                continue
            except Exception as exc:  # noqa: BLE001 — recorded per document, never silent
                counts["failed"] += 1
                dump_new(out / "results" / f"{doc.member.sha}.json", {"sha": doc.member.sha, "arm": ctx.arm, "failure": {"class": type(exc).__name__, "code": getattr(exc, "code", "unexpected_failure")}})
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_runner.py -q -p no:cacheprovider`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/runner.py tests/test_vlm_runner.py
git commit -m "vlm: wave runner with receipts, prefetch and resume" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 15: Report — per-arm metrics and failure taxonomy

**Files:**
- Create: `vlm/report.py`
- Test: `tests/test_vlm_report.py`

**Interfaces:**
- Consumes: a wave directory written by `run_wave`.
- Produces: `build_report(wave_dir) -> dict`, `render_markdown(report) -> str`, `write_report(wave_dir) -> Path` (writes `report-<UTC>.json` and `REPORT-<UTC>.md`, exclusive), `percentiles(values, (50, 95, 99)) -> dict`.

Report fields: `arm`, `documents {requested, attempted, admitted, refused_by_gate, failed, skipped_existing}`, `admission_rate` (admitted / attempted), `reasons` (histogram of gate reason codes), `by_family` ({family: {attempted, admitted}}), `by_reader_outcome` ({outcome: {attempted, admitted}} — on U755 the "repair rate" is admitted among reader-failed), `rows` ({proposed, truth, matched, exact_balance, exact_description, missing, extra, match_rate}) when matches exist, `pages_by_role` aggregated, `chain_derived_directions`, `latency` (per-document p50/p95/p99 of `total_ms`, per-page inference means for stage_a/stage_b, render/encode per page), `throughput_pages_per_s`, `upload_bytes_per_page`, `tokens` (mean prompt/completion per page), `instance_hours`, `cost_usd`, `failures` (histogram of failure codes), `taxonomy` (top 10 reason combinations).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_report.py
import json
from pathlib import Path

from vlm import report
from vlm.receipts import dump_new


def _wave(tmp_path: Path) -> Path:
    wave = tmp_path / "wave"
    (wave / "results").mkdir(parents=True)
    dump_new(wave / "launch.json", {"arm": "hybrid", "started_at": "t"})
    docs = [
        {"sha": "A" * 64, "arm": "hybrid", "family": "famA", "reader_outcome": "failed", "pages": 2, "rows_proposed": 10,
         "gate": {"admitted": True, "reasons": [], "chain_derived_directions": 1}, "timings": {"total_ms": 1000.0, "stage_a_ms": 400.0, "stage_b_ms": 500.0, "render_ms": 50.0, "encode_ms": 10.0, "gate_ms": 1.0, "prompt_tokens": 2000, "completion_tokens": 400},
         "stats": {"pages_by_role": {"statement_page": 2}}, "match": {"truth_rows": 10, "candidate_rows": 10, "matched": 9, "exact_balance": 9, "exact_description": 8, "missing": 1, "extra": 1}, "upload_bytes": 300000, "failure": None},
        {"sha": "B" * 64, "arm": "hybrid", "family": "famA", "reader_outcome": "validated", "pages": 1, "rows_proposed": 3,
         "gate": {"admitted": False, "reasons": ["sum_mismatch", "continuity_break"], "chain_derived_directions": 0}, "timings": {"total_ms": 3000.0, "stage_a_ms": 1000.0, "stage_b_ms": 1500.0, "render_ms": 30.0, "encode_ms": 5.0, "gate_ms": 1.0, "prompt_tokens": 1000, "completion_tokens": 200},
         "stats": {"pages_by_role": {"statement_page": 1}}, "match": None, "upload_bytes": 150000, "failure": None},
        {"sha": "C" * 64, "arm": "hybrid", "failure": {"class": "TransportError", "code": "http_500"}},
    ]
    for doc in docs:
        dump_new(wave / "results" / f"{doc['sha']}.json", doc)
    dump_new(wave / "result.json", {"arm": "hybrid", "status": "complete", "counts": {"requested": 3, "attempted": 3, "admitted": 1, "refused_by_gate": 1, "failed": 1, "skipped_existing": 0},
                                    "timings": {"pages": 3}, "wall_s": 10.0, "instance_hours": 10 / 3600, "cost_usd": "rate not measured"})
    return wave


def test_build_report_metrics(tmp_path):
    wave = _wave(tmp_path)
    rep = report.build_report(wave)
    assert rep["arm"] == "hybrid" and rep["documents"]["admitted"] == 1 and rep["admission_rate"] == 0.5
    assert rep["reasons"] == {"continuity_break": 1, "sum_mismatch": 1}
    assert rep["by_reader_outcome"]["failed"] == {"attempted": 1, "admitted": 1}
    assert rep["rows"]["matched"] == 9 and rep["rows"]["match_rate"] == 0.9
    assert rep["latency"]["document_total_ms"]["p50"] == 2000.0
    assert rep["latency"]["stage_b_ms_per_page"] == (500.0 + 1500.0) / 3
    assert rep["failures"] == {"http_500": 1} and rep["pages_by_role"] == {"statement_page": 3}
    assert rep["taxonomy"][0]["reasons"] == ["sum_mismatch", "continuity_break"]
    assert rep["cost_usd"] == "rate not measured" and rep["upload_bytes_per_page"] == 150000.0


def test_write_report_and_markdown(tmp_path):
    wave = _wave(tmp_path)
    path = report.write_report(wave)
    assert path.exists() and path.name.startswith("report-") and path.with_suffix(".md").name.replace("report-", "REPORT-") in {p.name for p in wave.iterdir()}
    text = report.render_markdown(report.build_report(wave))
    assert "hybrid" in text and "sum_mismatch" in text and "A" * 64 not in text


def test_percentiles():
    assert report.percentiles([1, 2, 3, 4], (50, 95, 99)) == {"p50": 2.5, "p95": 3.85, "p99": 3.97}
    assert report.percentiles([], (50,)) == {"p50": None}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_report.py -q -p no:cacheprovider`
Expected: FAIL with `ModuleNotFoundError: No module named 'vlm.report'`

- [ ] **Step 3: Write the implementation**

```python
# vlm/report.py
"""Per-wave metrics and the failure taxonomy, from public receipts only (no customer content)."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from vlm.receipts import dump_new


def percentiles(values: list[float], marks: tuple[int, ...]) -> dict[str, float | None]:
    if not values:
        return {f"p{m}": None for m in marks}
    ordered = sorted(float(v) for v in values)
    out: dict[str, float | None] = {}
    for mark in marks:
        position = (len(ordered) - 1) * mark / 100.0
        low, high = int(position), min(int(position) + 1, len(ordered) - 1)
        out[f"p{mark}"] = round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 4)
    return out


def _load_results(wave: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((wave / "results").glob("*.json")) if not p.name.endswith(".private.json")]


def build_report(wave_dir: Path) -> dict:
    wave = Path(wave_dir)
    result = json.loads((wave / "result.json").read_text(encoding="utf-8"))
    docs = _load_results(wave)
    ok = [d for d in docs if d.get("failure") is None and d.get("gate")]
    failures = Counter(d["failure"]["code"] for d in docs if d.get("failure"))
    reasons: Counter = Counter()
    by_family: dict[str, dict] = {}
    by_outcome: dict[str, dict] = {}
    roles: Counter = Counter()
    combos: Counter = Counter()
    rows = {"proposed": 0, "truth": 0, "matched": 0, "exact_balance": 0, "exact_description": 0, "missing": 0, "extra": 0}
    matched_docs = 0
    chain = 0
    for doc in ok:
        gate = doc["gate"]
        reasons.update(gate.get("reasons", []))
        if gate.get("reasons"):
            combos[tuple(gate["reasons"])] += 1
        chain += gate.get("chain_derived_directions", 0)
        for bucket, key in ((by_family, doc.get("family", "")), (by_outcome, doc.get("reader_outcome", ""))):
            entry = bucket.setdefault(key, {"attempted": 0, "admitted": 0})
            entry["attempted"] += 1
            entry["admitted"] += 1 if gate.get("admitted") else 0
        roles.update((doc.get("stats") or {}).get("pages_by_role") or {})
        rows["proposed"] += doc.get("rows_proposed", 0)
        if doc.get("match"):
            matched_docs += 1
            for key in ("truth_rows", "candidate_rows", "matched", "exact_balance", "exact_description", "missing", "extra"):
                target = "truth" if key == "truth_rows" else key
                if target in rows:
                    rows[target] += doc["match"].get(key, 0)
    pages = sum(d.get("pages", 0) for d in ok)
    totals = Counter()
    for doc in ok:
        totals.update({k: v for k, v in doc["timings"].items() if isinstance(v, (int, float))})
    attempted = result["counts"].get("attempted", 0)
    report = {
        "arm": result.get("arm"), "status": result.get("status"), "documents": result["counts"],
        "admission_rate": (result["counts"].get("admitted", 0) / attempted) if attempted else None,
        "reasons": dict(sorted(reasons.items())),
        "by_family": dict(sorted(by_family.items())), "by_reader_outcome": dict(sorted(by_outcome.items())),
        "rows": {**rows, "documents_with_truth": matched_docs, "match_rate": (rows["matched"] / rows["truth"]) if rows["truth"] else None},
        "pages_by_role": dict(sorted(roles.items())), "chain_derived_directions": chain,
        "latency": {
            "document_total_ms": percentiles([d["timings"]["total_ms"] for d in ok], (50, 95, 99)),
            "stage_a_ms_per_page": (totals["stage_a_ms"] / pages) if pages else None,
            "stage_b_ms_per_page": (totals["stage_b_ms"] / pages) if pages else None,
            "render_ms_per_page": (totals["render_ms"] / pages) if pages else None,
            "encode_ms_per_page": (totals["encode_ms"] / pages) if pages else None,
        },
        "throughput_pages_per_s": (pages / result["wall_s"]) if result.get("wall_s") else None,
        "upload_bytes_per_page": (sum(d.get("upload_bytes", 0) for d in ok) / pages) if pages else None,
        "tokens": {"prompt_per_page": (totals["prompt_tokens"] / pages) if pages else None,
                   "completion_per_page": (totals["completion_tokens"] / pages) if pages else None},
        "instance_hours": result.get("instance_hours"), "cost_usd": result.get("cost_usd"),
        "failures": dict(sorted(failures.items())),
        "taxonomy": [{"reasons": list(k), "documents": v} for k, v in combos.most_common(10)],
    }
    return report


def render_markdown(report: dict) -> str:
    lines = [f"# Ceiling wave report — arm `{report['arm']}` ({report['status']})", ""]
    docs = report["documents"]
    lines += ["| requested | attempted | admitted | refused by gate | failed | admission rate |", "|---|---|---|---|---|---|",
              f"| {docs.get('requested')} | {docs.get('attempted')} | {docs.get('admitted')} | {docs.get('refused_by_gate')} | {docs.get('failed')} | {report['admission_rate']} |", ""]
    lines += ["## Gate reasons", ""] + [f"- {k}: {v}" for k, v in report["reasons"].items()] + [""]
    lines += ["## By reader outcome", ""] + [f"- {k}: {v['admitted']}/{v['attempted']} admitted" for k, v in report["by_reader_outcome"].items()] + [""]
    lines += ["## Rows vs reader (where truth exists)", "", f"- {report['rows']}", ""]
    lines += ["## Latency and cost", "", f"- {report['latency']}", f"- throughput pages/s: {report['throughput_pages_per_s']}",
              f"- upload bytes/page: {report['upload_bytes_per_page']}", f"- tokens: {report['tokens']}",
              f"- instance hours: {report['instance_hours']}; cost: {report['cost_usd']}", ""]
    lines += ["## Failures", ""] + [f"- {k}: {v}" for k, v in report["failures"].items()] + [""]
    lines += ["## Taxonomy (top reason combinations)", ""] + [f"- {t['reasons']}: {t['documents']}" for t in report["taxonomy"]] + [""]
    return "\n".join(lines)


def write_report(wave_dir: Path) -> Path:
    wave = Path(wave_dir)
    report = build_report(wave)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = wave / f"report-{stamp}.json"
    dump_new(path, report)
    (wave / f"REPORT-{stamp}.md").write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_report.py -q -p no:cacheprovider`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add vlm/report.py tests/test_vlm_report.py
git commit -m "vlm: wave report and failure taxonomy" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 16: CLI

**Files:**
- Create: `tools/vlm_ceiling.py`
- Test: `tests/test_vlm_ceiling_cli.py`

**Interfaces:**
- Produces: `main(argv) -> int` with subcommands `partitions --out DIR`, `run --arm ARM --manifest PRIVATE_MANIFEST --out WAVE_DIR [--limit N] [--data-scope customer|synthetic] [--stage-a-url URL] [--stage-b-url URL] [--stage-b-model NAME] [--truth] [--hourly-rate X] [--resume-from DIR] [--long-edge N] [--jpeg-quality N]`, `report --wave WAVE_DIR`. Defaults: stage A worker `http://127.0.0.1:18003`, stage B `http://127.0.0.1:18002`, truth cache `.claude/recovery/webapp_data_train12_cold` + the run of record. `run` builds `RunContext`, binds the manifest, loads members, and calls `run_wave` with the real `default_authorize`. Exit codes: 0 ok, 2 refused (prints `{"error": code}`), 3 wave failed.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vlm_ceiling_cli.py
import json
from pathlib import Path

from tests.paddle_synthetic import build_ledger_page, render_native_pdf
from tools import vlm_ceiling
from vlm.receipts import dump_new

SHA = "E" * 64


def test_run_reader_baseline_and_report(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    (archive / "fam").mkdir(parents=True)
    (archive / "fam" / "d.pdf").write_bytes(render_native_pdf(build_ledger_page(2)))
    private = tmp_path / "X.manifest.private.json"
    dump_new(private, {"manifest_version": 1, "name": "X", "set_sha256": "0" * 64, "archive_root": str(archive),
                       "members": [{"sha": SHA, "relative_path": "fam/d.pdf", "byte_size": 1, "page_count": 1,
                                    "folder_label": "fam", "classification": "digital", "outcome_class": "validated", "account_count": 1}]})
    monkeypatch.setattr(vlm_ceiling, "default_authorize", lambda scope: None)
    code = vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave"), "--data-scope", "synthetic"])
    assert code == 0
    assert vlm_ceiling.main(["report", "--wave", str(tmp_path / "wave")]) == 0
    assert any(p.name.startswith("report-") for p in (tmp_path / "wave").iterdir())
    assert vlm_ceiling.main(["run", "--arm", "reader_baseline", "--manifest", str(private), "--out", str(tmp_path / "wave"), "--data-scope", "synthetic"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vlm_ceiling_cli.py -q -p no:cacheprovider`
Expected: FAIL with `ImportError: cannot import name 'vlm_ceiling'`

- [ ] **Step 3: Write the implementation**

```python
# tools/vlm_ceiling.py
"""CLI for the Phase 3 ceiling experiment: partitions, run, report. See plan v1 §11 and R16."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vlm import partitions, report
from vlm.client import StageAWorkerClient, VlmClient
from vlm.receipts import Refused, bound
from vlm.runner import ARMS, RunContext, default_authorize, run_wave
from vlm.truth import ReaderTruth

DEFAULT_STAGE_A_URL = "http://127.0.0.1:18003"
DEFAULT_STAGE_B_URL = "http://127.0.0.1:18002"
DEFAULT_STAGE_B_MODEL = "Qwen/Qwen3.5-4B"
DEFAULT_TRUTH_CACHE = Path(".claude/recovery/webapp_data_train12_cold")
DEFAULT_OUT = Path("discovery_reports/train13-logs/p3ceiling")


def _run(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    members = partitions.load_private_manifest(manifest_path)
    archive_root = Path(json.loads(manifest_path.read_text(encoding="utf-8"))["archive_root"])
    stage_a = StageAWorkerClient(args.stage_a_url, token=None) if args.arm in ("stage_a_rules", "hybrid") else None
    stage_b = VlmClient(args.stage_b_url) if args.arm in ("stage_b_only", "hybrid") else None
    truth = ReaderTruth(Path(args.truth_cache), partitions.DEFAULT_RUN_OF_RECORD) if args.truth else None
    ctx = RunContext(arm=args.arm, stage_a=stage_a, stage_b=stage_b, stage_b_model=args.stage_b_model, truth=truth,
                     long_edge=args.long_edge, quality=args.jpeg_quality, seed=0, data_scope=args.data_scope,
                     hourly_rate=args.hourly_rate)
    try:
        result = run_wave(members, ctx, Path(args.out), archive_root=archive_root, manifest_binding=bound(manifest_path),
                          limit=args.limit, authorize=default_authorize, resume_from=Path(args.resume_from) if args.resume_from else None)
    finally:
        if truth is not None:
            truth.close()
    print(json.dumps({"status": result["status"], "counts": result["counts"], "instance_hours": result["instance_hours"]}))
    return 0 if result["status"] == "complete" else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_ceiling")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("partitions")
    p.add_argument("--out", default=str(DEFAULT_OUT / "manifests"))
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=ARMS, required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--data-scope", choices=("customer", "synthetic"), default="customer")
    r.add_argument("--stage-a-url", default=DEFAULT_STAGE_A_URL)
    r.add_argument("--stage-b-url", default=DEFAULT_STAGE_B_URL)
    r.add_argument("--stage-b-model", default=DEFAULT_STAGE_B_MODEL)
    r.add_argument("--truth", action="store_true")
    r.add_argument("--truth-cache", default=str(DEFAULT_TRUTH_CACHE))
    r.add_argument("--hourly-rate", type=float, default=None)
    r.add_argument("--resume-from", default=None)
    r.add_argument("--long-edge", type=int, default=1540)
    r.add_argument("--jpeg-quality", type=int, default=90)
    q = sub.add_parser("report")
    q.add_argument("--wave", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "partitions":
            summary = partitions.write_manifests(Path(args.out))
            print(json.dumps({name: {"documents": s["documents"], "pages": s["pages"]} for name, s in summary.items()}))
            return 0
        if args.command == "run":
            return _run(args)
        if args.command == "report":
            path = report.write_report(Path(args.wave))
            print(json.dumps({"report": str(path)}))
            return 0
    except Refused as exc:
        print(json.dumps({"error": exc.code}))
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vlm_ceiling_cli.py -q -p no:cacheprovider`
Expected: `1 passed`

- [ ] **Step 5: Run the whole harness suite and commit**

Run: `python -m pytest tests/test_vlm_receipts.py tests/test_vlm_partitions.py tests/test_vlm_render.py tests/test_vlm_schema.py tests/test_vlm_client.py tests/test_vlm_textparse.py tests/test_vlm_tables.py tests/test_vlm_assemble.py tests/test_vlm_metadata.py tests/test_vlm_gate.py tests/test_vlm_truth.py tests/test_vlm_prompts.py tests/test_vlm_proposals.py tests/test_vlm_runner.py tests/test_vlm_report.py tests/test_vlm_ceiling_cli.py -q -p no:cacheprovider`
Expected: all pass (74 tests).

Run: `python -m pytest tests/test_truth_firewall.py tests/test_paddle_routing.py tests/test_experiments_are_not_wired.py -q -p no:cacheprovider`
Expected: pass (the new package must not trip the holdout firewall or the routing pins).

```bash
git add tools/vlm_ceiling.py tests/test_vlm_ceiling_cli.py
git commit -m "vlm: ceiling CLI (partitions, run, report)" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review (run after all sixteen tasks)

1. **Spec coverage (plan v1 §11):** partitions with holdout check (Task 2) ✓; render at model-fit resolution with hashes (Task 3) ✓; arms 1–4 (Task 14) ✓, arm 5 dropped by R16 note (disk) ✓; per-phase timings, tokens, upload bytes (Tasks 5, 14) ✓; row-level exact match vs reader (Task 11) ✓; gate outcomes with reason codes, false accepts measurable via CTRL matching (Tasks 10, 15) ✓; multi-page continuity through merged rows and the reconcile chain (Tasks 13, 10) ✓; failure taxonomy (Task 15) ✓; determinism (seed, temperature 0, hashes) ✓; nondeterminism measurement = a second wave on the DEV manifest compared by `page_hashes` and `response_sha256` (part B) ✓; cost from hours × rate (Task 14) ✓.
2. **Placeholder scan:** no TBD/TODO; every step has code and an expected result.
3. **Type consistency:** `CandidateRow` fields and order are identical in Tasks 8, 10, 11, 13, 14; `AccountMeta` in Tasks 9, 10, 13, 14; `GateVerdict` in Tasks 10, 14; `ChatResult` in Tasks 5, 14; `Member` in Tasks 2, 14, 16; `PageProposal` in Tasks 13, 14.
4. **Firewall:** `vlm/` imports `discovery.runner` for the digest only; never `tools.holdout`; never the sealed-store variable name.
5. **Privacy:** public receipts contain sha, arm, family label, counts, hashes, timings, codes; relative paths appear only in `*.private.json` and the private manifest.

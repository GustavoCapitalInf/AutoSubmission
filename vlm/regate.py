"""Re-gate a completed wave under the CURRENT gate without touching the models.

The private receipts hold the proposal rows and metadata; the row match against the reader's truth does
not depend on the gate, so it is carried over. The new wave directory binds the source wave and records
`regated_from`, so a gate change can be measured on the same model outputs for free.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from vlm.assemble import CandidateRow
from vlm.gate import GATE_VERSION, GateVerdict, gate
from vlm.metadata import AccountMeta
from vlm.receipts import bound, dump_new, need, sha256_file, utc_now


def _dec(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _rows_from_private(items: list[dict]) -> list[CandidateRow]:
    return [CandidateRow(date=r.get("date"), date_text=r.get("date_text", ""), description=r.get("description", ""),
                         amount=Decimal(str(r["amount"])), direction=r.get("direction", "unknown"), balance=_dec(r.get("balance")),
                         page=int(r.get("page", 0)), source=r.get("source", "stage_b"), locator=r.get("locator", ""),
                         direction_source=r.get("direction_source", "printed")) for r in items]


def _meta_from_private(item: dict) -> AccountMeta:
    return AccountMeta(_dec(item.get("beginning_balance")), _dec(item.get("ending_balance")), item.get("period_start"),
                       item.get("period_end"), item.get("currency"), item.get("account_last4"), item.get("bank"),
                       tuple(item.get("sources") or ()), _dec(item.get("stated_total_credits")), _dec(item.get("stated_total_debits")),
                       item.get("stated_credit_count"), item.get("stated_debit_count"))


def regate_wave(source: Path, out: Path) -> dict:
    source, out = Path(source), Path(out)
    need((source / "result.json").is_file(), "source_wave_missing")
    need(not os.path.lexists(out), "wave_already_attempted")
    out.mkdir(parents=True)
    (out / "results").mkdir()
    launch = json.loads((source / "launch.json").read_text(encoding="utf-8"))
    launch = {**launch, "regated_from": {"launch": bound(source / "launch.json"), "result": bound(source / "result.json")},
              "gate_version": GATE_VERSION, "regated_at": utc_now()}
    dump_new(out / "launch.json", launch)
    source_result = json.loads((source / "result.json").read_text(encoding="utf-8"))
    counts = dict(source_result["counts"])
    counts["admitted"] = counts["refused_by_gate"] = 0
    started = time.perf_counter()
    for path in sorted((source / "results").glob("*.json")):
        if path.name.endswith(".private.json"):
            continue
        public = json.loads(path.read_text(encoding="utf-8"))
        private_path = path.with_name(path.name[:-5] + ".private.json")
        if public.get("failure") is not None or not public.get("gate") or not private_path.exists():
            dump_new(out / "results" / path.name, public)
            continue
        private = json.loads(private_path.read_text(encoding="utf-8"))
        rows = _rows_from_private(private.get("rows") or [])
        meta = _meta_from_private(private.get("meta") or {})
        verdict: GateVerdict = gate(rows, meta)
        extra = []
        stats = public.get("stats") or {}
        if stats.get("currency_conflict") and "currency_conflict" not in verdict.reasons:
            extra.append("currency_conflict")
        if stats.get("anchor_corroboration") == "disagreement" and "anchor_disagreement" not in verdict.reasons:
            extra.append("anchor_disagreement")
        if extra:
            verdict = GateVerdict(False, verdict.reasons + tuple(extra), verdict.row_count, (), verdict.computed_ending,
                                  verdict.continuity_breaks, verdict.chain_derived_directions, verdict.checks, verdict.anchored)
        public["gate"] = {"admitted": verdict.admitted, "reasons": list(verdict.reasons), "row_count": verdict.row_count,
                          "continuity_breaks": verdict.continuity_breaks, "chain_derived_directions": verdict.chain_derived_directions,
                          "derived": verdict.checks.get("derived", []), "anchored": verdict.anchored,
                          "repeats": verdict.checks.get("repeats"), "summary_ok": verdict.checks.get("summary_ok"),
                          "gate_version": GATE_VERSION, "regated": True}
        private["gate_checks"] = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in verdict.checks.items()}
        counts["admitted" if verdict.admitted else "refused_by_gate"] += 1
        dump_new(out / "results" / path.name, public)
        dump_new(out / "results" / private_path.name, private)
    result = {**launch, "status": "complete", "failure_code": None, "failure_class": None, "counts": counts,
              "timings": source_result.get("timings", {}), "wall_s": source_result.get("wall_s"),
              "wave_wall_hours": source_result.get("wave_wall_hours"), "cost_usd": source_result.get("cost_usd"),
              "regate_wall_s": time.perf_counter() - started, "finished_at": utc_now()}
    dump_new(out / "result.json", result)
    dump_new(out / "release.json", {"arm": launch.get("arm"), "controller_exit": 0, "result_sha256": sha256_file(out / "result.json"),
                                    "regated_from_result_sha256": launch["regated_from"]["result"]["sha256"]})
    return result

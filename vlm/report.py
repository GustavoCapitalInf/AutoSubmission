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
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((wave / "results").glob("*.json"))
            if not p.name.endswith(".private.json")]


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
            for key in ("truth_rows", "matched", "exact_balance", "exact_description", "missing", "extra"):
                target = "truth" if key == "truth_rows" else key
                rows[target] += doc["match"].get(key, 0)
    pages = sum(d.get("pages", 0) for d in ok)
    totals: Counter = Counter()
    for doc in ok:
        totals.update({k: v for k, v in doc["timings"].items() if isinstance(v, (int, float))})
    attempted = result["counts"].get("attempted", 0)
    return {
        "arm": result.get("arm"), "status": result.get("status"), "documents": result["counts"],
        "admission_rate": (result["counts"].get("admitted", 0) / attempted) if attempted else None,
        "reasons": dict(sorted(reasons.items())),
        "by_family": dict(sorted(by_family.items())), "by_reader_outcome": dict(sorted(by_outcome.items())),
        "rows": {**rows, "documents_with_truth": matched_docs,
                 "match_rate": (rows["matched"] / rows["truth"]) if rows["truth"] else None},
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

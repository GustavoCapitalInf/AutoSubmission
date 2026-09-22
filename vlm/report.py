"""Per-wave metrics and the failure taxonomy, from public receipts only (no customer content).

Review closures (MAJOR-3, MINOR-6): false accepts against reader truth, strict vs anchored-one-side
admissions, chain-direction admissions, derived-anchor aggregation, a validated-only row match rate,
and an optional excluded slice (the DEV documents prompts were tuned on) so CTRL \\ DEV is reportable.
"""
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


def _is_false_accept(doc: dict) -> bool:
    """An admitted document whose rows contradict the reader's validated rows ARITHMETICALLY: a missing
    or extra row, or a printed balance that differs on a matched row. Description differences are
    reported apart (`admitted_with_description_mismatches`): on the DEV wave they were formatting
    variants of matched rows, not wrong rows (RR-3)."""
    match = doc.get("match")
    if not (doc.get("gate", {}).get("admitted") and match):
        return False
    return match.get("missing", 0) > 0 or match.get("extra", 0) > 0 or match.get("balance_mismatch", 0) > 0


def _metrics(docs: list[dict], counts: dict, wall_s: float | None) -> dict:
    ok = [d for d in docs if d.get("failure") is None and d.get("gate")]
    failures = Counter(d["failure"]["code"] for d in docs if d.get("failure"))
    reasons: Counter = Counter()
    by_family: dict[str, dict] = {}
    by_outcome: dict[str, dict] = {}
    roles: Counter = Counter()
    combos: Counter = Counter()
    derived: Counter = Counter()
    rows = {"proposed": 0, "truth": 0, "matched": 0, "exact_balance": 0, "exact_description": 0, "missing": 0, "extra": 0}
    validated_rows = {"truth": 0, "matched": 0}
    matched_docs = chain_docs = strict = one_side = repeats_admitted = description_mismatch_docs = 0
    corroboration: Counter = Counter()
    by_candidate: Counter = Counter()
    false_accepts: list[str] = []
    for doc in ok:
        gate = doc["gate"]
        admitted = bool(gate.get("admitted"))
        reasons.update(gate.get("reasons", []))
        if gate.get("reasons"):
            combos[tuple(gate["reasons"])] += 1
        derived.update(gate.get("derived", []))
        if admitted:
            strict += 1   # every admission is strict: a derived anchor is never admitted (gate reason anchor_derived)
            by_candidate[gate.get("admitted_candidate") or "single"] += 1
            if gate.get("chain_derived_directions", 0):
                chain_docs += 1
            if (gate.get("repeats") or {}).get("unverifiable", 0):
                repeats_admitted += 1   # RR-2: must stay 0; the gate refuses unverifiable repeats
            corroboration[(doc.get("stats") or {}).get("anchor_corroboration") or "n/a"] += 1
            match = doc.get("match") or {}
            if match and match.get("exact_description", 0) < match.get("matched", 0):
                description_mismatch_docs += 1
        elif tuple(gate.get("reasons", [])) == ("anchor_derived",):
            one_side += 1   # would have reconciled with one printed anchor; reported apart, never admitted
        for bucket, key in ((by_family, doc.get("family", "")), (by_outcome, doc.get("reader_outcome", ""))):
            entry = bucket.setdefault(key, {"attempted": 0, "admitted": 0})
            entry["attempted"] += 1
            entry["admitted"] += 1 if admitted else 0
        roles.update((doc.get("stats") or {}).get("pages_by_role") or {})
        rows["proposed"] += doc.get("rows_proposed", 0)
        if doc.get("match"):
            matched_docs += 1
            match = doc["match"]
            for key in ("matched", "exact_balance", "exact_description", "missing", "extra"):
                rows[key] += match.get(key, 0)
            rows["truth"] += match.get("truth_rows", 0)
            if doc.get("reader_outcome") == "validated":
                validated_rows["truth"] += match.get("truth_rows", 0)
                validated_rows["matched"] += match.get("matched", 0)
            if _is_false_accept(doc):
                false_accepts.append(doc["sha"])
    pages = sum(d.get("pages", 0) for d in ok)
    totals: Counter = Counter()
    for doc in ok:
        totals.update({k: v for k, v in doc["timings"].items() if isinstance(v, (int, float))})
    attempted = counts.get("attempted", 0)
    admitted_total = counts.get("admitted", 0)
    return {
        "documents": counts,
        "admission_rate": (admitted_total / attempted) if attempted else None,
        "admitted_strict": strict,
        "would_admit_with_derived_anchor": one_side,
        "admitted_with_chain_directions": chain_docs,
        "admitted_with_unverifiable_repeats": repeats_admitted,
        "admitted_by_anchor_corroboration": dict(sorted(corroboration.items())),
        "admitted_by_candidate": dict(sorted(by_candidate.items())),
        "admitted_with_description_mismatches": description_mismatch_docs,
        "strict_admission_rate": (strict / attempted) if attempted else None,
        "false_accepts": {"count": len(false_accepts), "documents": false_accepts},
        "derived_anchors": dict(sorted(derived.items())),
        "reasons": dict(sorted(reasons.items())),
        "by_family": dict(sorted(by_family.items())), "by_reader_outcome": dict(sorted(by_outcome.items())),
        "rows": {**rows, "documents_with_truth": matched_docs,
                 "match_rate": (rows["matched"] / rows["truth"]) if rows["truth"] else None,
                 "validated_match_rate": (validated_rows["matched"] / validated_rows["truth"]) if validated_rows["truth"] else None},
        "pages_by_role": dict(sorted(roles.items())),
        "latency": {
            "document_total_ms": percentiles([d["timings"]["total_ms"] for d in ok], (50, 95, 99)),
            "stage_a_ms_per_page": (totals["stage_a_ms"] / pages) if pages else None,
            "stage_b_ms_per_page": (totals["stage_b_ms"] / pages) if pages else None,
            "stage_b_wall_ms_per_page": (totals["stage_b_wall_ms"] / pages) if pages and totals.get("stage_b_wall_ms") else None,
            "render_ms_per_page": (totals["render_ms"] / pages) if pages else None,
            "encode_ms_per_page": (totals["encode_ms"] / pages) if pages else None,
        },
        "throughput_pages_per_s": (pages / wall_s) if wall_s else None,
        "upload_bytes_per_page": (sum(d.get("upload_bytes", 0) for d in ok) / pages) if pages else None,
        "tokens": {"prompt_per_page": (totals["prompt_tokens"] / pages) if pages else None,
                   "completion_per_page": (totals["completion_tokens"] / pages) if pages else None},
        "failures": dict(sorted(failures.items())),
        "taxonomy": [{"reasons": list(k), "documents": v} for k, v in combos.most_common(10)],
    }


def build_report(wave_dir: Path, *, exclude_shas: frozenset[str] = frozenset()) -> dict:
    wave = Path(wave_dir)
    result = json.loads((wave / "result.json").read_text(encoding="utf-8"))
    docs = _load_results(wave)
    report = {"arm": result.get("arm"), "status": result.get("status"), "wave_wall_hours": result.get("wave_wall_hours"),
              "cost_usd": result.get("cost_usd"), **_metrics(docs, result["counts"], result.get("wall_s"))}
    if exclude_shas:
        kept = [d for d in docs if d.get("sha") not in exclude_shas]
        kept_counts = {"requested": len(kept), "attempted": sum(1 for d in kept if d.get("failure") is None or d.get("gate")),
                       "admitted": sum(1 for d in kept if (d.get("gate") or {}).get("admitted")),
                       "refused_by_gate": sum(1 for d in kept if d.get("gate") and not d["gate"].get("admitted")),
                       "failed": sum(1 for d in kept if d.get("failure")), "skipped_existing": 0}
        report["excluded_documents"] = len(docs) - len(kept)
        report["primary_without_excluded"] = _metrics(kept, kept_counts, None)
    return report


def render_markdown(report: dict) -> str:
    lines = [f"# Ceiling wave report — arm `{report['arm']}` ({report['status']})", ""]
    docs = report["documents"]
    lines += ["| requested | attempted | admitted | strict | refused by gate | failed | admission rate | strict rate | false accepts |",
              "|---|---|---|---|---|---|---|---|---|",
              f"| {docs.get('requested')} | {docs.get('attempted')} | {docs.get('admitted')} | {report['admitted_strict']} | {docs.get('refused_by_gate')} | {docs.get('failed')} | {report['admission_rate']} | {report['strict_admission_rate']} | {report['false_accepts']['count']} |", ""]
    lines += [f"- would admit with one derived anchor (NOT admitted): {report['would_admit_with_derived_anchor']}; with chain-derived directions: {report['admitted_with_chain_directions']}; derived anchors: {report['derived_anchors']}", ""]
    lines += ["## Gate reasons", ""] + [f"- {k}: {v}" for k, v in report["reasons"].items()] + [""]
    lines += ["## By reader outcome", ""] + [f"- {k}: {v['admitted']}/{v['attempted']} admitted" for k, v in report["by_reader_outcome"].items()] + [""]
    lines += ["## Rows vs reader (where truth exists)", "", f"- {report['rows']}", ""]
    lines += ["## Latency and cost", "", f"- {report['latency']}", f"- throughput pages/s: {report['throughput_pages_per_s']}",
              f"- upload bytes/page: {report['upload_bytes_per_page']}", f"- tokens: {report['tokens']}",
              f"- wave wall hours: {report['wave_wall_hours']}; cost: {report['cost_usd']}", ""]
    lines += ["## Failures", ""] + [f"- {k}: {v}" for k, v in report["failures"].items()] + [""]
    lines += ["## Taxonomy (top reason combinations)", ""] + [f"- {t['reasons']}: {t['documents']}" for t in report["taxonomy"]] + [""]
    if "primary_without_excluded" in report:
        p = report["primary_without_excluded"]
        lines += ["## Primary slice (excluded documents removed)", "",
                  f"- excluded: {report['excluded_documents']}; admitted {p['documents']['admitted']}/{p['documents']['attempted']}; strict {p['admitted_strict']}; false accepts {p['false_accepts']['count']}; validated row match rate {p['rows']['validated_match_rate']}", ""]
    return "\n".join(lines)


def write_report(wave_dir: Path, *, exclude_shas: frozenset[str] = frozenset()) -> Path:
    wave = Path(wave_dir)
    report = build_report(wave, exclude_shas=exclude_shas)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = wave / f"report-{stamp}.json"
    dump_new(path, report)
    (wave / f"REPORT-{stamp}.md").write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return path

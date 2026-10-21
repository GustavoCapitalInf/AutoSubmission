"""train8_compare.py — the batch-8 comparison with the ACCOUNTING quarantine.

    python -m tools.train8_compare --base <run A dir> --candidate <train-8 run dir> \
        --quarantine tools/train/recon_b7_quarantine_nonnative_208.shas \
        [--report <path.md>] [--fail-on-regression]

Why this exists: the historical run
of record is gone; the comparison base is the REGENERATED batch-7 run
`47be5963` (Tesseract 5.5.3 on this host). Its native side reproduces the
batch-7 state by every durable record; its scanned side could not be made
equivalent because the original Windows OCR environment is unrecoverable. The
208 non-native content shas of that run are therefore an accounting
quarantine — never a safety one:

1. they are excluded from the historical batch-7 → batch-8 headline gain;
2. positive movement on a quarantined sha is reported separately and never
   counted toward the official historical-comparable improvement total;
3. negative movement on a quarantined sha is REAL under the shared current
   environment and fails `--fail-on-regression` exactly like any other —
   quarantine suppresses or excuses nothing;
4. comparable shas keep `discovery.compare`'s normal semantics;
5. the full per-sha movement table for the quarantined set is written with
   every comparison.

The movement itself is `discovery.compare`'s: the same `load_run` (documents
keyed by content sha, duplicates collapsed) and the same ladder
(`failed < withheld < review < validated`; `deferred` unranked). This tool
adds only the partition and the five-way accounting:

  (a) historical-comparable improvements     (b) quarantined OCR-environment improvements
  (c) regressions on comparable shas         (d) regressions on quarantined shas
  (e) total observed current-environment validated count

and it prints the historical-comparable validated delta with the quarantined
shas removed from BOTH sides of the subtraction. "2,469 → N" is never printed
as the headline.

Exit: with `--fail-on-regression`, 2 if ANY shared document (comparable or
quarantined) moved down the ladder; otherwise 0. Documents are named by the
first 16 hex characters of their sha, never by path.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from discovery.compare import (
    ALL_CLASSES,
    LADDER,
    RawDenominatorMismatch,
    compare,
    direction,
    render,
)
from discovery.evidence import load_run

_Q = "quarantined"
_C = "comparable"


def read_quarantine(path: Path) -> set[str]:
    return {line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")}


def partitioned(base, candidate, quarantine: set[str]) -> dict:
    """Movement over the shared shas, split into comparable and quarantined."""
    shared = sorted(set(base.documents) & set(candidate.documents))
    rows = []
    for sha in shared:
        before, after = base.documents[sha], candidate.documents[sha]
        rows.append({
            "sha": sha, "bucket": _Q if sha in quarantine else _C,
            "before": before.outcome_class, "after": after.outcome_class,
            "before_reason": before.outcome_reason, "after_reason": after.outcome_reason,
            "before_parser": before.parser_id or "-", "after_parser": after.parser_id or "-",
            "folder": after.folder_label or before.folder_label or "-",
            "direction": direction(before.outcome_class, after.outcome_class),
        })
    counts = {bucket: Counter(r["direction"] for r in rows if r["bucket"] == bucket) for bucket in (_C, _Q)}
    validated = {
        bucket: {
            "base": sum(1 for r in rows if r["bucket"] == bucket and r["before"] == "validated"),
            "candidate": sum(1 for r in rows if r["bucket"] == bucket and r["after"] == "validated"),
        } for bucket in (_C, _Q)
    }
    candidate_totals = Counter(doc.outcome_class for doc in candidate.documents.values())
    base_totals = Counter(doc.outcome_class for doc in base.documents.values())
    return {
        "shared": len(shared),
        "comparable_shas": sum(1 for r in rows if r["bucket"] == _C),
        "quarantined_shas": sum(1 for r in rows if r["bucket"] == _Q),
        "quarantine_absent": sorted(quarantine - set(shared)),
        "counts": counts, "validated": validated, "rows": rows,
        "candidate_totals": dict(candidate_totals), "base_totals": dict(base_totals),
        "any_regression": any(r["direction"] == "regressed" for r in rows),
    }


def render_denominators_and_matrix(canonical: dict) -> list[str]:
    """P22-TRUTHTABLE (R11): both denominators and the EXACT transition matrix,
    in the partitioned report itself rather than only inside the appended
    canonical block.

    The RAW denominator is printed first and is never replaced. The
    CONFIRMED-COMPLETE-LEGIBLE denominator is not computable here at all — the
    adjudicated set lives in the sealed truth store, which this tool may not
    read (the leakage firewall) — so this says so by name instead of printing
    a proxy under the CCL heading. `tools/truth_report.py` is the instrument
    that joins the two.
    """
    raw, coverage = canonical["raw_denominator"], canonical["raw_coverage"]
    matrix = canonical["transition_matrix"]
    lines = [
        "## Denominators (R11: the raw one first, never replaced)", "",
        "| denominator | base | candidate |", "|---|---:|---:|",
        f"| raw (distinct content shas) | {raw['baseline']} | {raw['candidate']} |",
        f"| raw coverage (validated / raw) | {coverage['baseline']['validated']} / "
        f"{coverage['baseline']['denominator']} | {coverage['candidate']['validated']} / "
        f"{coverage['candidate']['denominator']} |",
        "| ccl_adjudicated | not available in this tool | not available in this tool |",
        "",
        "`ccl_adjudicated` is read from the sealed truth store by "
        "`tools/truth_report.py`; this tool never reads it (the leakage firewall).",
        "",
        "## Transition matrix (exact; rows = base class, columns = candidate class)", "",
        "| from \\ to | " + " | ".join(ALL_CLASSES) + " |",
        "|---" * (len(ALL_CLASSES) + 1) + "|",
    ]
    lines += [
        f"| {source} | " + " | ".join(str(matrix[source][target]) for target in ALL_CLASSES) + " |"
        for source in ALL_CLASSES
    ]
    lines.append("")
    return lines


def render_partition(p: dict, *, base_id: str, candidate_id: str,
                     canonical: dict | None = None) -> str:
    c, q = p["counts"][_C], p["counts"][_Q]
    vc, vq = p["validated"][_C], p["validated"][_Q]
    ct, bt = p["candidate_totals"], p["base_totals"]
    lines = [
        f"# train-8 comparison with the accounting quarantine — {base_id} → {candidate_id}", "",
        f"shared {p['shared']} = comparable {p['comparable_shas']} + quarantined {p['quarantined_shas']}"
        + (f"; quarantine shas absent from the shared set: {len(p['quarantine_absent'])}" if p["quarantine_absent"] else ""),
        "",
        "## Five-way accounting", "",
        "| | comparable (historical) | quarantined (OCR environment) |", "|---|---:|---:|",
        f"| (a)/(b) improved | **{c.get('improved', 0)}** | {q.get('improved', 0)} (reported separately, not counted) |",
        f"| (c)/(d) regressed | **{c.get('regressed', 0)}** | **{q.get('regressed', 0)}** (real; investigated normally) |",
        f"| unchanged | {c.get('unchanged', 0)} | {q.get('unchanged', 0)} |",
        f"| unranked (deferred in/out) | {c.get('unranked', 0)} | {q.get('unranked', 0)} |",
        f"| validated, base → candidate | {vc['base']} → {vc['candidate']} ({vc['candidate'] - vc['base']:+d}) | {vq['base']} → {vq['candidate']} ({vq['candidate'] - vq['base']:+d}) |",
        "",
        f"**Official historical-comparable validated delta (quarantine removed from both sides): "
        f"{vc['base']} → {vc['candidate']} = {vc['candidate'] - vc['base']:+d}.**",
        f"(e) total observed current-environment validated count: **{ct.get('validated', 0)}** of {sum(ct.values())} "
        f"(base run: {bt.get('validated', 0)} of {sum(bt.values())}). The historical run of record's 2,469 is NOT the base of this delta.",
        "",
        "candidate outcome totals: " + ", ".join(f"{k} {ct.get(k, 0)}" for k in ALL_CLASSES),
        "",
    ]
    if canonical is not None:
        lines += render_denominators_and_matrix(canonical)
    movers = [r for r in p["rows"] if r["bucket"] == _C and r["direction"] in ("improved", "regressed", "unranked")]
    lines += ["## Comparable movers", ""]
    if movers:
        lines += ["| direction | sha16 | folder | before | after | parser |", "|---|---|---|---|---|---|"]
        lines += [f"| {r['direction']} | {r['sha'][:16]} | {r['folder']} | {r['before']}/{r['before_reason']} | "
                  f"{r['after']}/{r['after_reason']} | {r['before_parser']} → {r['after_parser']} |"
                  for r in sorted(movers, key=lambda r: (r["direction"], r["sha"]))]
    else:
        lines.append("none")
    lines += ["", "## Quarantined set — full per-sha movement table", "",
              "| direction | sha16 | folder | before | after | parser |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['direction']} | {r['sha'][:16]} | {r['folder']} | {r['before']}/{r['before_reason']} | "
              f"{r['after']}/{r['after_reason']} | {r['before_parser']} → {r['after_parser']} |"
              for r in sorted((r for r in p["rows"] if r["bucket"] == _Q),
                              key=lambda r: ({"regressed": 0, "improved": 1, "unranked": 2, "unchanged": 3}[r["direction"]], r["sha"]))]
    if p["quarantine_absent"]:
        lines += ["", "quarantine shas absent from the shared set: " + ", ".join(s[:16] for s in p["quarantine_absent"])]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:  # a cp1252 console cannot print the report's arrows; the FILE is the record, never the console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--quarantine", required=True, type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--fail-on-regression", action="store_true",
                        help="exit 2 if ANY shared document — comparable or quarantined — moved down")
    args = parser.parse_args(argv)

    base, candidate = load_run(args.base), load_run(args.candidate)
    try:
        canonical = compare(base, candidate)
    except RawDenominatorMismatch as mismatch:
        # R11: never silently re-based. Exit 3, distinct from the regression
        # exit 2 — "not comparable" and "regressed" are different findings.
        print(f"train8_compare: {mismatch}", file=sys.stderr)
        return 3
    p = partitioned(base, candidate, read_quarantine(args.quarantine))
    text = (render_partition(p, base_id=base.run_id, candidate_id=candidate.run_id,
                             canonical=canonical)
            + "\n## discovery.compare (canonical, unpartitioned)\n\n```\n" + render(canonical) + "\n```\n")
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text)
    if args.fail_on_regression and p["any_regression"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

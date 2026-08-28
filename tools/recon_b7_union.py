"""recon_b7_union.py — compose a whole-corpus run view from a full run plus a
scoped re-run of a subset, and name every document the re-run moved.

    python -m tools.recon_b7_union --full <run A dir> --subset <run B dir> \
        --out <union dir> [--label "..."]

Written for the batch-7 baseline's single toolchain-equivalence attempt
(BATCH8_TRANSITION, Option A): run A is the regenerated baseline over the
frozen corpus (Tesseract 5.5.3); run B re-reads ONLY the non-native documents
under an isolated Tesseract 5.5.0 with its own cold cache. The union takes
run B's record for every content sha run B processed and run A's for the rest,
so the frozen checker (`tools.recon_b7_check`) can judge the composed run
exactly as it judges a real one. Nothing historical is synthesised: every
record in the union was measured by one of the two runs, and `union.json`
says which.

What is composed, and how:

* `telemetry.jsonl` — run A's records with every record whose
  `document.content_sha256` run B processed REPLACED by run B's record(s).
* `rows.csv` — the same substitution by `content_sha256` (a duplicate path
  keeps run B's row for that sha).
* `summary.json` — run A's summary (its `inventory`, `dedup` and `mode`
  describe the whole corpus and are unchanged by a re-read), with `reasons`
  and `deferred_reasons` recomputed from the union rows and a `union` block
  naming the two sources.
* `diff_A_B.md` — every sha run B processed whose outcome class, reason,
  parser or intake rung differs from run A's (sha16 only, never a path).

Exit 0 on success. The union is a derived artifact for acceptance checking;
the two source runs remain the evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


def _records(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _sha(record: dict) -> str:
    return ((record.get("document") or {}).get("content_sha256") or "").upper()


def compose(full: Path, subset: Path, out: Path, *, label: str = "") -> dict:
    out.mkdir(parents=True, exist_ok=True)
    a_records = _records(full / "telemetry.jsonl")
    b_records = _records(subset / "telemetry.jsonl")
    b_shas = {_sha(r) for r in b_records if _sha(r)}
    union_records = [r for r in a_records if _sha(r) not in b_shas] + b_records
    with (out / "telemetry.jsonl").open("w", encoding="utf-8") as handle:
        for record in union_records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    with (full / "rows.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        a_rows = list(reader)
    with (subset / "rows.csv").open(encoding="utf-8", newline="") as handle:
        b_rows = list(csv.DictReader(handle))
    union_rows = [r for r in a_rows if r["content_sha256"].upper() not in b_shas] + b_rows
    with (out / "rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in union_rows:
            writer.writerow({k: row.get(k, "") for k in fields})

    summary = json.loads((full / "summary.json").read_text(encoding="utf-8"))
    summary["reasons"] = dict(Counter(r["outcome_reason"] for r in union_rows))
    summary["deferred_reasons"] = dict(
        Counter(r["outcome_reason"] for r in union_rows if r["outcome_class"] == "deferred"))
    summary["outcome"] = dict(Counter(r["outcome_class"] for r in union_rows))
    summary["union"] = {
        "label": label,
        "full_run": str(full), "subset_run": str(subset),
        "subset_shas": len(b_shas), "subset_records": len(b_records),
        "records_replaced": sum(1 for r in a_records if _sha(r) in b_shas),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")

    # per-sha diff, run A -> run B, over the subset
    def view(rows: list[dict]) -> dict[str, dict]:
        seen: dict[str, dict] = {}
        for r in rows:
            seen.setdefault(r["content_sha256"].upper(), r)
        return seen
    a_view, b_view = view(a_rows), view(b_rows)
    diffs = []
    for sha in sorted(b_shas):
        a, b = a_view.get(sha), b_view.get(sha)
        if a is None or b is None:
            diffs.append((sha, "(absent in one run)", "", "", "", "", ""))
            continue
        keys = ("outcome_class", "outcome_reason", "parser_id", "source_path")
        if any(a.get(k, "") != b.get(k, "") for k in keys):
            diffs.append((sha, a["outcome_class"], b["outcome_class"],
                          f"{a['outcome_reason']} -> {b['outcome_reason']}",
                          f"{a.get('parser_id') or '-'} -> {b.get('parser_id') or '-'}",
                          f"{a.get('source_path')} -> {b.get('source_path')}", b.get("folder_label", "")))
    lines = [f"# run A -> run B over {len(b_shas)} shas ({label})", "",
             f"changed: {len(diffs)}", "",
             "| sha16 | A class | B class | reason | parser | rung | folder |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {d[0][:16]} | {d[1]} | {d[2]} | {d[3]} | {d[4]} | {d[5]} | {d[6]} |" for d in diffs]
    (out / "diff_A_B.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "union.json").write_text(json.dumps(summary["union"], indent=1), encoding="utf-8")
    return {"subset_shas": len(b_shas), "records": len(union_records), "rows": len(union_rows),
            "changed": len(diffs), "diffs": diffs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--full", required=True, type=Path)
    parser.add_argument("--subset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)
    result = compose(args.full, args.subset, args.out, label=args.label)
    print(f"union written to {args.out}: {result['records']} records / {result['rows']} rows; "
          f"subset {result['subset_shas']} shas; changed A->B: {result['changed']}")
    print((args.out / "diff_A_B.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

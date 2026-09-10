"""tools/p22truthtable_measure.py — the run-of-record measurement for
P22-TRUTHTABLE: the layered taxonomy, the diagnostic labels and the funnel,
over a run that predates every one of those columns.

    python tools/p22truthtable_measure.py --run <run dir>
        --census <private classify_census csv> [--out <private>.md]

Why it reads a run it cannot re-run
-----------------------------------
The run of record was written before these columns existed, so its `rows.csv`
carries the FACTS (outcome, reason, evidence verdict, truncation, dispatch,
source) but none of the DERIVED columns this card adds. Every derived value
here is therefore computed by the SHIPPING code — `telemetry.unresolved_
taxonomy.diagnose_unresolved` over the row, the withheld-taxonomy diagnosis
from the run's own telemetry, and the classifier's verdict from
`tools/classify_census.py`'s per-sha census — rather than by a second
implementation that could disagree with what a live run would record. A
measurement produced by different code than the runner would run is a
measurement of something else.

Offline and read-only, entirely: the run directory and the census CSV, both
already on disk. It opens no document, runs no analysis, reads no archive
file, and never touches the reconstruction mode.

Sensitivity: stdout is AGGREGATES. Documents are named by sha16 and kind, and
only in the private `--out` file, which must be git-ignored.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

from telemetry.unresolved_taxonomy import (
    LAYER_NAMES,
    LAYERS,
    KindFacts,
    diagnose_unresolved,
)

#: The run of record's rows predate the funnel columns, so the stages are
#: derived HERE by the same rules `discovery/runner.py::_project_funnel`
#: applies — read off facts the row already carries, never inferred. Paddle
#: stages are `not_attempted` on this run by construction: no real document
#: has ever been read by Paddle.
STAGE_NOT_ATTEMPTED = "not_attempted"


def _rows_by_sha(run: Path) -> tuple[list[str], dict[str, list[dict]]]:
    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if not sha:
                continue
            if sha not in groups:
                groups[sha] = []
                order.append(sha)
            groups[sha].append(row)
    return order, groups


def _diagnostics_by_sha(run: Path) -> dict[str, dict]:
    """The withheld-taxonomy section the RUN ITSELF recorded, per document."""
    found: dict[str, dict] = {}
    path = run / "telemetry.jsonl"
    if not path.is_file():
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            sha = ((record.get("document") or {}).get("content_sha256") or "").strip().upper()
            diagnostics = record.get("diagnostics")
            if sha and isinstance(diagnostics, dict) and diagnostics.get("evaluated"):
                found[sha] = diagnostics
    return found


def _census_by_sha(path: Path | None) -> dict[str, KindFacts]:
    if path is None:
        return {}
    facts: dict[str, KindFacts] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if not sha:
                continue
            findings = tuple(f for f in (row.get("findings") or "").replace(",", ";").split(";") if f)
            facts[sha] = KindFacts(
                kind=(row.get("kind") or "KIND_UNCERTAIN").strip(),
                sub_kind=(row.get("sub_kind") or "").strip() or None,
                findings=findings,
            )
    return facts


def _funnel(row: dict) -> dict[str, str]:
    source = (row.get("source_path") or "none").strip()
    dispatch = (row.get("dispatch_outcome") or "").strip()
    return {
        "stage_extract": source or "none",
        "stage_evidence": (STAGE_NOT_ATTEMPTED if source == "none"
                           else "present" if (row.get("evidence_sha256") or "").strip()
                           else "absent"),
        "stage_geometry": STAGE_NOT_ATTEMPTED,
        "stage_layout": STAGE_NOT_ATTEMPTED,
        "stage_candidate": dispatch or STAGE_NOT_ATTEMPTED,
        "stage_verdict": (row.get("outcome_class") or "").strip() or STAGE_NOT_ATTEMPTED,
    }


def _table(title: str, counter: collections.Counter, header: tuple[str, ...]) -> list[str]:
    lines = [f"\n## {title}", "| " + " | ".join(header) + " | n |", "|" + "---|" * (len(header) + 1)]
    for key, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        cells = key if isinstance(key, tuple) else (key,)
        lines.append("| " + " | ".join(str(c) for c in cells) + f" | {count} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--census", type=Path, default=None,
                        help="tools/classify_census.py's per-sha CSV (git-ignored)")
    parser.add_argument("--out", type=Path, default=None,
                        help="a git-ignored path for the per-document exceptions (sha16 + kind)")
    args = parser.parse_args(argv)

    order, groups = _rows_by_sha(args.run)
    diagnostics = _diagnostics_by_sha(args.run)
    census = _census_by_sha(args.census)

    validated = {sha for sha in order
                 if any((r.get("outcome_class") or "") == "validated" for r in groups[sha])}
    unresolved = [sha for sha in order if sha not in validated]

    by_kind_archive: collections.Counter = collections.Counter()
    by_kind_unresolved: collections.Counter = collections.Counter()
    primary_layer: collections.Counter = collections.Counter()
    primary_code: collections.Counter = collections.Counter()
    layer_present: collections.Counter = collections.Counter()
    funnel: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    exceptions: list[tuple[str, str]] = []

    for sha in order:
        row = groups[sha][0]
        facts = census.get(sha)
        by_kind_archive[facts.kind if facts else "(not classified)"] += 1
        for stage, value in _funnel(row).items():
            funnel[stage][value] += 1
        if sha in validated:
            if facts is not None and facts.kind != "STATEMENT_COMPLETE":
                exceptions.append((sha[:16], facts.kind))
            continue
        by_kind_unresolved[facts.kind if facts else "(not classified)"] += 1
        diagnosis = diagnose_unresolved(row, diagnostics.get(sha), facts)
        primary_layer[f"{diagnosis.primary_layer} {LAYER_NAMES.get(diagnosis.primary_layer, '')}"] += 1
        primary_code[(diagnosis.primary_layer, diagnosis.primary_code)] += 1
        for layer in LAYERS:
            if getattr(diagnosis, f"reason_{layer}"):
                layer_present[f"{layer} {LAYER_NAMES[layer]}"] += 1

    labels = {
        "R  (deferred_visual_ocr)": sum(
            1 for sha in order
            if any((r.get("outcome_reason") or "") == "deferred_visual_ocr" for r in groups[sha])),
        "U  (tesseract read, unclaimed)": sum(
            1 for sha in order
            if any((r.get("source_path") or "") == "local_tesseract"
                   and (r.get("dispatch_outcome") or "") != "claimed" for r in groups[sha])),
        "failure class A": sum(1 for sha in order if (groups[sha][0].get("failure_class") or "") == "A"),
        "failure class B": sum(1 for sha in order if (groups[sha][0].get("failure_class") or "") == "B"),
        "failure class C": sum(1 for sha in order if (groups[sha][0].get("failure_class") or "") == "C"),
        "truncation flagged": sum(
            1 for sha in order
            if any((r.get("truncated_pages") or "0").strip() not in ("", "0") for r in groups[sha])),
        "refused": sum(
            1 for sha in order
            if any((r.get("outcome_class") or "") == "refused" for r in groups[sha])),
    }

    lines = [
        f"# P22-TRUTHTABLE run-of-record measurement — {args.run.name}",
        "",
        f"documents (distinct content shas): {len(order)}",
        f"validated: {len(validated)}    unresolved: {len(unresolved)}",
        f"disjoint sum over archive:    {sum(by_kind_archive.values())} == {len(order)}"
        f"   {'OK' if sum(by_kind_archive.values()) == len(order) else 'MISMATCH'}",
        f"disjoint sum over unresolved: {sum(by_kind_unresolved.values())} == {len(unresolved)}"
        f"   {'OK' if sum(by_kind_unresolved.values()) == len(unresolved) else 'MISMATCH'}",
    ]
    lines += _table("primary kind — archive", by_kind_archive, ("kind",))
    lines += _table("primary kind — unresolved", by_kind_unresolved, ("kind",))
    lines += _table("primary reason LAYER — unresolved", primary_layer, ("layer",))
    lines += _table("primary reason CODE — unresolved", primary_code, ("layer", "code"))
    lines += _table("layers PRESENT (a document carries several; never summed)",
                    layer_present, ("layer",))
    for stage in ("stage_extract", "stage_evidence", "stage_geometry", "stage_layout",
                  "stage_candidate", "stage_verdict"):
        lines += _table(f"funnel — {stage}", funnel[stage], ("value",))
    lines += ["\n## diagnostic labels (overlapping; never summed)", "| label | n |", "|---|---|"]
    lines += [f"| {name} | {count} |" for name, count in labels.items()]
    lines += [
        "",
        f"validated documents NOT classified STATEMENT_COMPLETE: {len(exceptions)}"
        " (named by sha16 and kind in the private --out only)",
    ]
    for kind, count in collections.Counter(kind for _, kind in exceptions).most_common():
        lines.append(f"  {kind}: {count}")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            "# validated documents not classified STATEMENT_COMPLETE (PRIVATE)\n\n"
            "| sha16 | kind |\n|---|---|\n"
            + "".join(f"| {sha16} | {kind} |\n" for sha16, kind in sorted(exceptions)),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Report emission: per-set JSON, cross-set rollup JSON, CSV summary, and a
human-readable markdown summary.

All artifacts are written to a gitignored directory and pass through
``masking.mask_structure`` so no unmasked account number, full ledger, or
holder identity is ever emitted.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .classify import ComparisonRow, Outcome
from .masking import mask_structure

OUTCOME_ORDER = [outcome.value for outcome in Outcome]


def outcome_counts(rows: list[ComparisonRow]) -> dict[str, int]:
    counts = {name: 0 for name in OUTCOME_ORDER}
    for row in rows:
        counts[row.outcome.value] += 1
    return {name: count for name, count in counts.items() if count}


def write_set_report(out_dir: Path, set_report: dict[str, Any]) -> Path:
    set_dir = out_dir / set_report["set"]
    set_dir.mkdir(parents=True, exist_ok=True)
    path = set_dir / "report.json"
    path.write_text(
        json.dumps(mask_structure(set_report), indent=2, default=str),
        encoding="utf-8",
    )
    return path


def write_rollup(out_dir: Path, rollup: dict[str, Any]) -> Path:
    path = out_dir / "rollup.json"
    path.write_text(
        json.dumps(mask_structure(rollup), indent=2, default=str),
        encoding="utf-8",
    )
    return path


def write_csv_summary(out_dir: Path, set_reports: list[dict[str, Any]]) -> Path:
    path = out_dir / "summary.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["set", "field", "outcome", "ours", "moneythumb", "expected",
             "ours_withheld", "evidence_kind", "for_ocean", "rationale"]
        )
        for report in set_reports:
            for row in report["rows"]:
                masked = mask_structure(row)
                writer.writerow([
                    masked["set"], masked["field"], masked["outcome"],
                    json.dumps(masked["ours"], default=str),
                    json.dumps(masked["mt"], default=str),
                    json.dumps(masked["expected"], default=str),
                    masked["ours_withheld"],
                    (masked.get("evidence") or {}).get("kind", ""),
                    masked["for_ocean"],
                    masked["rationale"],
                ])
    return path


def _markdown_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "-"
    return str(value)


def write_markdown_summary(
    out_dir: Path,
    set_reports: list[dict[str, Any]],
    rollup: dict[str, Any],
) -> Path:
    lines: list[str] = []
    add = lines.append
    add("# MoneyThumb Comparison Harness - Summary")
    add("")
    add(f"Generated: {rollup['generated_at']} | offline deterministic run")
    add("")
    add("MoneyThumb is never automatic ground truth; see the per-row rationale "
        "and evidence pointers in each set's `report.json`.")
    add("")

    add("## Outcome counts per set")
    add("")
    header = "| set | " + " | ".join(OUTCOME_ORDER) + " |"
    add(header)
    add("|" + "---|" * (len(OUTCOME_ORDER) + 1))
    for name, counts in rollup["sets"].items():
        add(
            f"| {name} | "
            + " | ".join(str(counts.get(o, 0)) for o in OUTCOME_ORDER)
            + " |"
        )
    totals = rollup["total_counts"]
    add(
        "| **total** | "
        + " | ".join(str(totals.get(o, 0)) for o in OUTCOME_ORDER)
        + " |"
    )
    add("")

    add("## MoneyThumb field coverage (no silent omissions)")
    add("")
    coverage = rollup["coverage"]
    add(f"- distinct MT JSON paths observed: **{coverage['total_paths']}**")
    for disposition, count in sorted(coverage["counts"].items()):
        add(f"- {disposition}: **{count}**")
    add(f"- unmapped: **{len(coverage['unmapped'])}** "
        f"({'COMPLETE' if coverage['complete'] else 'INCOMPLETE - ' + str(coverage['unmapped'])})")
    add("")

    add("## Findings by set (non-BOTH_MATCH_EXPECTED rows)")
    for report in set_reports:
        add("")
        add(f"### {report['set']}")
        add("")
        if report.get("capability_findings"):
            for finding in report["capability_findings"]:
                add(f"- CAPABILITY: **{finding['title']}** - {finding['detail']}")
            add("")
        interesting = [
            row for row in report["rows"]
            if row["outcome"] != Outcome.BOTH_MATCH_EXPECTED.value
        ]
        if not interesting and not report.get("capability_findings"):
            add("All compared fields match the audited/source expectations.")
            continue
        if interesting:
            add("| field | outcome | ours | moneythumb | expected | rationale |")
            add("|---|---|---|---|---|---|")
            for row in interesting:
                masked = mask_structure(row)
                add(
                    "| {field} | {outcome} | {ours} | {mt} | {expected} | {rationale} |".format(
                        field=masked["field"],
                        outcome=masked["outcome"],
                        ours=_markdown_value(masked["ours"]),
                        mt=_markdown_value(masked["mt"]),
                        expected=_markdown_value(masked["expected"]),
                        rationale=str(masked["rationale"]).replace("|", "/")[:400],
                    )
                )

    add("")
    add("## For Ocean ruling (UNRESOLVED + queued registry questions)")
    add("")
    queued = rollup["for_ocean"]
    if not queued:
        add("None.")
    for row in queued:
        masked = mask_structure(row)
        add(f"- **{masked['set']} / {masked['field']}** [{masked['outcome']}]: "
            f"ours={_markdown_value(masked['ours'])}, "
            f"mt={_markdown_value(masked['mt'])} - {masked['rationale']}")
    add("")
    add("## Capability findings (cross-set)")
    add("")
    for finding in rollup["capability_findings"]:
        add(f"- **{finding['set']} / {finding['title']}**: {finding['detail']}")
    add("")

    path = out_dir / "SUMMARY.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

"""Deterministic-coverage in one command, from either storage backend.

    python -m telemetry.report --jsonl telemetry_runs/<run_id>.jsonl
    python -m telemetry.report --sqlite webapp_data
    python -m telemetry.report --jsonl <file> --by parser
    python -m telemetry.report --jsonl <file> --diagnostics    # W3-2 rollup

Both backends carry the identical record (H3_SCHEMA I2), so both produce the
identical report from the same run - asserted by test.

Deliberately ASCII-only: this is printed by a CLI, and a console in a legacy
code page must not be able to turn a measurement into a UnicodeEncodeError.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .diagnostics import UNATTRIBUTED
from .emit import read_jsonl


def load_records(*, jsonl: str | None = None, sqlite: str | None = None,
                 run_id: str | None = None) -> list[dict]:
    if jsonl:
        records = read_jsonl(jsonl)
    elif sqlite:
        # Imported lazily: the CLI path must stay free of the webapp.
        from webapp.storage import Storage

        records = Storage(Path(sqlite)).telemetry_records(run_id=run_id)
    else:
        raise ValueError("one of --jsonl or --sqlite is required")
    if run_id:
        records = [record for record in records if record.get("run_id") == run_id]
    return records


def summarize(records: list[dict]) -> dict:
    """Every number the report prints. Pure, so the tests can assert on it."""
    total = len(records)
    dispatch = Counter(
        (record["dispatch"]["outcome"] or "no_dispatch") for record in records
    )
    dispatch_source = Counter(record["dispatch"]["source"] for record in records)
    outcome = Counter(record["outcome"]["class"] for record in records)
    reasons = Counter(record["outcome"]["reason"] for record in records)
    source_path = Counter(record["source"]["path"] for record in records)
    parsers = Counter(
        record["dispatch"]["parser_id"] for record in records
        if record["dispatch"]["parser_id"]
    )

    assessed = sum(1 for r in records if r["source"]["truncation"]["assessed"])
    flagged_pages = sum(r["source"]["truncation"]["truncated_page_count"] for r in records)
    flagged_docs = sum(1 for r in records if r["source"]["truncation"]["truncated_page_count"])

    cache = {}
    for record in records:
        for stage, entry in record["stages"].items():
            counts = cache.setdefault(stage, Counter())
            counts[entry["cache"]] += 1

    calls = Counter()
    unpriced: set[str] = set()
    cost_total = 0.0
    cost_known = False
    for record in records:
        for call in record["models"]["calls"]:
            calls[call["purpose"]] += call["calls"]
        cost = record["models"]["cost"]
        unpriced.update(cost.get("unpriced_models") or [])
        if cost.get("amount") is not None:
            cost_total += cost["amount"]
            cost_known = True

    claimed = dispatch.get("claimed", 0)
    return {
        "total": total,
        "deterministic_coverage": (claimed / total) if total else 0.0,
        "dispatch": dict(dispatch),
        "dispatch_source": dict(dispatch_source),
        "outcome": dict(outcome),
        "reasons": dict(reasons),
        "source_path": dict(source_path),
        "parsers": dict(parsers),
        "truncation": {
            "assessed": assessed,
            "flagged_pages": flagged_pages,
            "flagged_documents": flagged_docs,
        },
        "cache": {stage: dict(counts) for stage, counts in cache.items()},
        "model_calls": dict(calls),
        "cost": {
            "amount": round(cost_total, 6) if cost_known else None,
            "unpriced_models": sorted(unpriced),
        },
    }


def _line(label: str, count: int, total: int) -> str:
    share = f"{count / total:6.1%}" if total else "     -"
    return f"  {label:<24}{count:>7}   {share}"


def render(summary: dict, run_id: str | None = None) -> str:
    total = summary["total"]
    lines = [f"run {run_id or '(all)'} | {total} documents", ""]

    claimed = summary["dispatch"].get("claimed", 0)
    lines.append(
        f"deterministic coverage    {claimed:>7} / {total}   "
        f"{summary['deterministic_coverage']:.1%}"
    )
    for key in ("ambiguous", "unclaimed", "no_dispatch"):
        if key in summary["dispatch"]:
            lines.append(_line(key, summary["dispatch"][key], total))

    lines.append("outcome")
    for key in ("validated", "review", "withheld", "failed", "deferred"):
        if key in summary["outcome"]:
            lines.append(_line(key, summary["outcome"][key], total))

    lines.append("reason")
    for key, count in sorted(summary["reasons"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_line(key, count, total))

    lines.append(
        "source path   "
        + " | ".join(f"{key} {count}" for key, count in sorted(summary["source_path"].items()))
    )
    truncation = summary["truncation"]
    lines.append(
        f"truncation    assessed {truncation['assessed']} | "
        f"flagged {truncation['flagged_pages']} pages across "
        f"{truncation['flagged_documents']} documents"
    )
    if summary["cache"]:
        lines.append(
            "cache         "
            + " | ".join(
                f"{stage} " + " ".join(f"{k} {v}" for k, v in sorted(counts.items()))
                for stage, counts in sorted(summary["cache"].items())
            )
        )
    dispatch_source = summary["dispatch_source"]
    lines.append(
        "dispatch src  "
        + " | ".join(f"{key} {count}" for key, count in sorted(dispatch_source.items()))
    )
    cost = summary["cost"]
    amount = f"${cost['amount']:.4f}" if cost["amount"] is not None else "$unpriced"
    unpriced = f"   (unpriced: {', '.join(cost['unpriced_models'])})" if cost["unpriced_models"] else ""
    calls = " | ".join(f"{k} {v}" for k, v in sorted(summary["model_calls"].items())) or "none"
    lines.append(f"cost          {amount}{unpriced}   calls: {calls}")
    return "\n".join(lines)


def _diagnostics(record: dict) -> dict:
    """A record's diagnostics section, tolerant of pre-W3-2 records.

    A run emitted before this section existed is not an error and must not
    crash the rollup; it reports as not-evaluated, which is true.
    """
    section = record.get("diagnostics")
    return section if isinstance(section, dict) else {"evaluated": False}


class UnattributedParsers(RuntimeError):
    """A failure-class x parser rollup was asked for over a run with no parsers.

    Raised rather than degraded (W3-2b, Ocean ruling 2), for the same reason
    `discovery.adjudication` raises: on a D-3 analysis cache hit
    `analyze_markdown` never ran, so the record carries the diagnosis and no
    `parser_id` (H3_SCHEMA 5.4). The rollup then prints a complete-LOOKING
    table in which every parser column reads `(none)`, and nothing in the
    output says the question was not answered.
    """


def diagnostics_rollup(records: list[dict], *, allow_unattributed: bool = False) -> dict:
    """Failure class x parser x volume over one run. Pure, so tests assert on it.

    The question this answers is W3-2's: of the documents the platform refused
    to publish, which CHECK refused, and for which parser - so remediation is
    ranked by check-class and volume instead of done statement by statement.
    """
    diagnosed = [r for r in records if _diagnostics(r).get("evaluated")]
    unattributed = [r for r in diagnosed if not r["dispatch"].get("parser_id")]
    if unattributed and not allow_unattributed:
        raise UnattributedParsers(
            f"{len(unattributed)} of {len(diagnosed)} diagnosed documents carry "
            "no parser_id, so a failure-class x parser rollup cannot be built.\n"
            "This is the H3_SCHEMA 5.4 cache-hit hole: a run served from the "
            "analysis cache never re-dispatched, so it has the diagnoses and "
            "not the claims.\n"
            "  re-run discovery with --no-cache   the run then carries its own "
            "parser attribution\n"
            "  --allow-unattributed               build the rollup anyway; the "
            "affected rows are labelled '(parser unknown)' explicitly"
        )
    versions: Counter = Counter()
    classes: Counter = Counter()
    codes: Counter = Counter()
    checks: Counter = Counter()
    pairs: Counter = Counter()
    parsers: Counter = Counter()
    unmapped_names: Counter = Counter()
    unmapped_issues = 0
    unmapped_warnings = 0

    for record in diagnosed:
        section = _diagnostics(record)
        versions[section.get("diagnostics_version")] += 1
        parser = record["dispatch"].get("parser_id") or UNATTRIBUTED
        primary = section.get("primary_class") or "undiagnosed"
        classes[primary] += 1
        parsers[parser] += 1
        pairs[(primary, parser)] += 1
        for code in section.get("codes") or []:
            codes[code] += 1
        for check in section.get("adb_checks_failed") or []:
            checks[check] += 1
        for name in section.get("unmapped") or []:
            unmapped_names[name] += 1
        counts = section.get("counts") or {}
        unmapped_issues += counts.get("unmapped_reconciliation_issues") or 0
        unmapped_warnings += counts.get("unmapped_adb_warnings") or 0

    return {
        "total": len(records),
        "diagnosed": len(diagnosed),
        # More than one entry means the rollup spans a vocabulary change, so
        # the class column is not comparing like with like. Surfaced, never
        # reconciled silently.
        "unattributed_documents": len(unattributed),
        "diagnostics_versions": {
            str(version): count for version, count in sorted(
                versions.items(), key=lambda kv: (kv[0] is None, kv[0])
            )
        },
        "classes": dict(classes),
        "codes": dict(codes),
        "adb_checks_failed": dict(checks),
        "parsers": dict(parsers),
        "class_parser": [
            [failure_class, parser, count]
            for (failure_class, parser), count in sorted(
                pairs.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1])
            )
        ],
        "unmapped": {
            "names": dict(unmapped_names),
            "reconciliation_issues": unmapped_issues,
            "adb_warnings": unmapped_warnings,
        },
    }


def render_diagnostics(rollup: dict, run_id: str | None = None, *, top: int = 20) -> str:
    """The W3-2 table. ASCII only."""
    total, diagnosed = rollup["total"], rollup["diagnosed"]
    lines = [
        f"run {run_id or '(all)'} | withheld diagnostics",
        f"diagnosed {diagnosed} of {total} documents",
    ]
    versions = rollup.get("diagnostics_versions") or {}
    if len(versions) > 1:
        lines.append(
            "  WARNING mixed taxonomy versions: "
            + " | ".join(f"v{key} {count}" for key, count in versions.items())
            + " - class counts span a vocabulary change and are NOT comparable"
        )
    lines.extend([
        "",
        f"  {'failure class':<26}{'parser':<22}{'docs':>6}",
    ])
    for failure_class, parser, count in rollup["class_parser"]:
        lines.append(f"  {failure_class:<26}{parser:<22}{count:>6}")
    if not rollup["class_parser"]:
        lines.append("  (none)")

    lines.extend(["", "failure class totals"])
    for key, count in sorted(rollup["classes"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_line(key, count, diagnosed))
    if not rollup["classes"]:
        lines.append("  (none)")

    lines.extend(["", f"top codes (of {len(rollup['codes'])})"])
    ranked = sorted(rollup["codes"].items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    for key, count in ranked:
        lines.append(f"  {key:<52}{count:>6}")
    if not ranked:
        lines.append("  (none)")

    if rollup.get("unattributed_documents"):
        lines.extend([
            "",
            f"WARNING --allow-unattributed: {rollup['unattributed_documents']} "
            f"diagnosed documents have no parser and are grouped under "
            f"'{UNATTRIBUTED}';",
            "         those rows answer no class x parser question.",
        ])

    unmapped = rollup["unmapped"]
    lines.extend([
        "",
        "unmapped     "
        + f"names {len(unmapped['names'])} | "
        + f"recon issues {unmapped['reconciliation_issues']} | "
        + f"adb warnings {unmapped['adb_warnings']}",
    ])
    for name, count in sorted(unmapped["names"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"  UNMAPPED {name:<43}{count:>6}")
    return "\n".join(lines)


def render_breakdown(records: list[dict], field: str) -> str:
    if field == "parser":
        counts = Counter(r["dispatch"]["parser_id"] or "(none)" for r in records)
    elif field == "source_path":
        counts = Counter(r["source"]["path"] for r in records)
    elif field == "outcome":
        counts = Counter(r["outcome"]["class"] for r in records)
    elif field == "diagnostic_class":
        counts = Counter(
            _diagnostics(r).get("primary_class") or "(not diagnosed)" for r in records
        )
    else:
        raise ValueError(f"unknown breakdown: {field}")
    total = len(records)
    lines = [f"by {field}"]
    for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(_line(key, count, total))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Telemetry coverage report.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--jsonl", help="A JSONL telemetry file (CLI/batch runs).")
    source.add_argument("--sqlite", help="A webapp data directory (schema v4).")
    parser.add_argument("--run-id", help="Restrict to one run.")
    parser.add_argument(
        "--by", choices=("parser", "source_path", "outcome", "diagnostic_class")
    )
    parser.add_argument(
        "--diagnostics", action="store_true",
        help="W3-2 withheld-diagnostics rollup: failure class x parser x volume.",
    )
    parser.add_argument(
        "--allow-unattributed", action="store_true",
        help="Build the diagnostics rollup even when some diagnosed documents "
             "have no parser; those rows are labelled '(parser unknown)'.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the summary as JSON.")
    args = parser.parse_args(argv)

    records = load_records(jsonl=args.jsonl, sqlite=args.sqlite, run_id=args.run_id)
    if not records:
        print("no telemetry records found", file=sys.stderr)
        return 1

    run_id = args.run_id or (
        records[0].get("run_id")
        if len(set(r.get("run_id") for r in records)) == 1
        else None
    )
    if args.diagnostics:
        try:
            rollup = diagnostics_rollup(
                records, allow_unattributed=args.allow_unattributed
            )
        except UnattributedParsers as error:
            print(f"telemetry.report: {error}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rollup, indent=2, sort_keys=True))
        else:
            print(render_diagnostics(rollup, run_id))
        return 0

    summary = summarize(records)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render(summary, run_id))
        if args.by:
            print()
            print(render_breakdown(records, args.by))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

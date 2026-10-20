"""Harness orchestration + CLI.

One command produces classified reports for all six benchmark sets, fully
offline::

    C:/Python314/python.exe -m benchmark --mt-results <path-to-moneythumbResults>

``moneythumbResults/`` is consumed strictly read-only; reports go to the
gitignored ``benchmark_reports/`` directory.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .classify import ComparisonRow
from bank_statements import ENV_VAR, bank_statements_dir

from .compare import (
    _mt_summary_for,
    _primary_result,
    build_daily_series_row,
    build_mca_rows,
    build_package_rows,
    build_position_count_row,
    build_revenue_statistics_row,
    build_statement_rows,
    build_withholding_row,
)
from .coverage import coverage_summary
from .expectations import Expectation, load_expectations
from .manifest import SETS, BenchmarkSet, verify_manifest
from .masking import mask_account
from .normalize import MTSet, load_mt_set
from .ourside import OurFileResult, OurSetResult, run_set
from .report import (
    outcome_counts,
    write_csv_summary,
    write_markdown_summary,
    write_rollup,
    write_set_report,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december",
           "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct",
           "nov", "dec")


def _prefix_for(filename: str, index: int, multi: bool) -> str:
    if not multi:
        return ""
    lowered = filename.lower()
    for month in _MONTHS:
        if month in lowered:
            return f"{month}."
    return f"file{index}."


def _our_file_summary(our_file: OurFileResult) -> dict[str, Any]:
    statement = our_file.statement
    metrics = our_file.metrics
    funders = [
        {
            "funder": f.get("funder"),
            "classification": f.get("classification"),
            "debit_count": f.get("debit_count"),
            "total_debited": f.get("total_debited"),
        }
        for f in (our_file.detection.get("known_funders") or [])
        + (our_file.detection.get("potential_lenders") or [])
    ]
    return {
        "file": our_file.relative_path,
        "source_type": our_file.source_type,
        "bank": statement.get("bank"),
        "account": mask_account(statement.get("account_number")),
        "period": f"{statement.get('period_start')} to {statement.get('period_end')}",
        "beginning_balance": statement.get("beginning_balance"),
        "ending_balance": statement.get("ending_balance"),
        "ending_balance_withheld": statement.get("ending_balance") is None,
        "average_daily_balance": metrics.get("average_daily_balance"),
        "adb_withheld": metrics.get("adb_ok") is not True,
        "total_credits": metrics.get("effective_total_deposits"),
        "num_credits": metrics.get("effective_num_deposits"),
        "total_debits": metrics.get("effective_total_withdrawals"),
        "num_debits": metrics.get("effective_num_withdrawals"),
        "nsf_count": metrics.get("nsf_count"),
        "negative_days": metrics.get("negative_days"),
        "min_balance": metrics.get("min_balance"),
        "max_balance": metrics.get("max_balance"),
        "cash_flow": metrics.get("cash_flow"),
        "true_revenue_total": metrics.get("true_revenue_total"),
        "verified_revenue_total": metrics.get("verified_revenue_total"),
        "unverified_deposit_total": metrics.get("unverified_deposit_total"),
        "non_revenue_total": metrics.get("non_revenue_total"),
        "withholding_rate": metrics.get("withholding_rate"),
        "quality": (our_file.payload.get("quality") or {}).get("corporate_use"),
        "integrity": (our_file.payload.get("integrity") or {}).get("risk_level"),
        "reconciliation_ok": our_file.reconciliation.get("ok"),
        "funders": funders,
    }


def _secondary_account_finding(
    set_name: str, mt: MTSet, primary_last4: str | None
) -> dict[str, Any] | None:
    secondary = [
        row for row in mt.result_rows
        if row.account_last4 and row.account_last4 != primary_last4
    ]
    if not secondary:
        return None
    detail_rows = ", ".join(
        f"{mask_account(row.account_number)} ({row.num_transactions} txns, "
        f"{row.start_date} to {row.end_date})"
        for row in secondary
    )
    return {
        "set": set_name,
        "title": "multi_account_emission",
        "detail": (
            f"MoneyThumb split the document(s) into multiple accounts and "
            f"emitted rows for secondary account(s): {detail_rows}. Our "
            "pipeline analyzes the primary account per statement and has no "
            "multi-account schema yet (FIELD_MAPPING s1/s3 ADOPT; PARITY #14)."
        ),
    }


def compare_set(
    benchmark_set: BenchmarkSet,
    mt: MTSet,
    ours: OurSetResult,
    expectations: dict[str, Expectation],
) -> dict[str, Any]:
    rows: list[ComparisonRow] = []
    capability: list[dict[str, Any]] = []

    if mt.is_stub:
        capability.append({
            "set": benchmark_set.name,
            "title": "moneythumb_no_result",
            "detail": (
                f"MoneyThumb returned HTTP {mt.http_status} with no analysis "
                f"('{mt.stub_message}') for this scanned document - a webhook "
                "is required to ever receive results. Our pipeline analyzed it "
                "fully offline from the committed OCR artifact "
                "(tests/corpus_cache) and reconciles; both audit CSVs record "
                "PASS for this statement. Recorded as a capability finding, "
                "not a field comparison (Ocean pre-ruling)."
            ),
        })
    else:
        multi = len(ours.files) > 1
        primary_last4 = None
        for index, our_file in enumerate(ours.files):
            filename = our_file.relative_path.rsplit("/", 1)[-1]
            expectation = expectations.get(filename)
            mt_result = _primary_result(mt, filename)
            mt_summary = _mt_summary_for(mt, mt_result)
            primary_last4 = primary_last4 or (
                mt_result.account_last4 if mt_result else None
            )
            prefix = _prefix_for(filename, index, multi)
            rows.extend(
                build_statement_rows(
                    benchmark_set.name, prefix, our_file, mt,
                    mt_result, mt_summary, expectation,
                )
            )
            series_row = build_daily_series_row(
                benchmark_set.name, prefix, our_file, mt, mt_summary, expectation
            )
            if series_row is not None:
                rows.append(series_row)

        revenue_row = build_revenue_statistics_row(benchmark_set.name, mt, ours)
        if revenue_row is not None:
            rows.append(revenue_row)
        rows.extend(build_mca_rows(benchmark_set.name, ours, mt))
        first_summary = _mt_summary_for(
            mt, _primary_result(mt, ours.files[0].relative_path.rsplit("/", 1)[-1])
        )
        withholding_row = build_withholding_row(benchmark_set.name, ours, first_summary)
        if withholding_row is not None:
            rows.append(withholding_row)
        position_row = build_position_count_row(
            benchmark_set.name, ours, mt.summary_rows
        )
        if position_row is not None:
            rows.append(position_row)
        rows.extend(
            build_package_rows(benchmark_set.name, benchmark_set, ours, mt, expectations)
        )

        finding = _secondary_account_finding(benchmark_set.name, mt, primary_last4)
        if finding is not None:
            capability.append(finding)
        capability.append({
            "set": benchmark_set.name,
            "title": "mt_omits_full_ledger",
            "detail": (
                "MoneyThumb's response carries no full transaction ledger "
                "(results[].transactions is null; csv/log/output URLs are "
                "deprecated) - only credit/large/repeating subsets. Our JSON "
                "carries the complete classified ledger with per-row evidence "
                "(FIELD_MAPPING s2/s8: a competitive advantage to preserve)."
            ),
        })

    return {
        "set": benchmark_set.name,
        "files": [
            {"path": relative, "sha256": digest}
            for relative, digest in zip(benchmark_set.files, benchmark_set.sha256)
        ],
        "moneythumb": {
            "http_status": mt.http_status,
            "uploaded_at": mt.uploaded_at,
            "is_stub": mt.is_stub,
            "distinct_json_paths": len(mt.paths),
        },
        "our_summary": [_our_file_summary(f) for f in ours.files],
        "rows": [row.to_dict() for row in rows],
        "outcome_counts": outcome_counts(rows),
        "capability_findings": capability,
        "notes": benchmark_set.notes,
        "_row_objects": rows,   # stripped before emission
    }


def run_harness(
    mt_results: Path,
    corpus_root: Path,
    ocr_cache: Path,
    out_dir: Path,
    set_names: list[str] | None = None,
) -> int:
    check = verify_manifest(corpus_root)
    if not check.ok:
        print("MANIFEST VERIFICATION FAILED - stopping (ask Ocean):")
        for problem in check.problems:
            print(f"  - {problem}")
        return 2

    results_root = mt_results / "results"
    if not results_root.is_dir():
        print(f"MoneyThumb results not found under {mt_results} (read-only input).")
        return 2

    expectations = load_expectations(REPO_ROOT / "docs")
    selected = [
        s for s in SETS if set_names is None or s.name in set_names
    ]

    set_reports: list[dict[str, Any]] = []
    all_rows: list[ComparisonRow] = []
    all_paths: set[str] = set()
    for benchmark_set in selected:
        mt = load_mt_set(results_root, benchmark_set.name)
        ours = run_set(benchmark_set, corpus_root, ocr_cache)
        report = compare_set(benchmark_set, mt, ours, expectations)
        all_rows.extend(report.pop("_row_objects"))
        all_paths |= mt.paths
        set_reports.append(report)
        print(f"[{benchmark_set.name}] rows={len(report['rows'])} "
              f"outcomes={report['outcome_counts']} "
              f"capability={len(report['capability_findings'])}")

    coverage = coverage_summary(all_paths)
    if not coverage["complete"]:
        print("COVERAGE INCOMPLETE - unmapped MoneyThumb fields:")
        for path in coverage["unmapped"]:
            print(f"  - {path}")

    rollup = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {
            "mt_results": str(mt_results),
            "corpus_root": str(corpus_root),
            "ocr_cache": str(ocr_cache),
            "offline": True,
        },
        "manifest": [
            {"set": s.name, "files": list(s.files), "sha256": list(s.sha256),
             "notes": s.notes}
            for s in selected
        ],
        "sets": {r["set"]: r["outcome_counts"] for r in set_reports},
        "total_counts": outcome_counts(all_rows),
        "for_ocean": [row.to_dict() for row in all_rows if row.for_ocean],
        "capability_findings": [
            finding for r in set_reports for finding in r["capability_findings"]
        ],
        "coverage": coverage,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    for report in set_reports:
        write_set_report(out_dir, report)
    write_rollup(out_dir, rollup)
    write_csv_summary(out_dir, set_reports)
    write_markdown_summary(out_dir, set_reports, rollup)
    print(f"Reports written to {out_dir} (gitignored; never committed).")
    print(f"Coverage: {coverage['total_paths']} MT paths - "
          f"{coverage['counts']} - complete={coverage['complete']}")
    return 0 if coverage["complete"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="MoneyThumb comparison harness (offline).",
    )
    parser.add_argument(
        "--mt-results",
        default=str(REPO_ROOT / "moneythumbResults"),
        help="Path to the read-only moneythumbResults directory "
        "(default: <repo>/moneythumbResults).",
    )
    parser.add_argument(
        "--corpus", default=bank_statements_dir(),
        help=f"Corpus root containing the benchmark PDFs (default: ${ENV_VAR}).",
    )
    parser.add_argument(
        "--cache", default=str(REPO_ROOT / "tests" / "corpus_cache"),
        help="Committed OCR artifact cache (offline OCR source).",
    )
    parser.add_argument(
        "--out", default=str(REPO_ROOT / "benchmark_reports"),
        help="Report output directory (gitignored).",
    )
    parser.add_argument(
        "--sets", nargs="*", default=None,
        help="Optional subset of benchmark set names.",
    )
    args = parser.parse_args(argv)
    if args.corpus is None:
        parser.error(f"pass --corpus or set {ENV_VAR}")
    return run_harness(
        Path(args.mt_results),
        Path(args.corpus),
        Path(args.cache),
        Path(args.out),
        args.sets,
    )

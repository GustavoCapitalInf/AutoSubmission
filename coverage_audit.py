"""Audit bank-statement coverage across a folder.

This is stricter than batch.py: it records parse/analyze timings, reconciliation
status, coverage ratios, output paths, and any error so bank-specific failures
can be fixed systematically.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import traceback
from dataclasses import asdict
from pathlib import Path

from analyze import _json_safe
from analysis.pipeline import analyze_markdown
from ocr.pipeline import parse_statement


FIELDS = [
    "file", "folder", "pages", "parse_model", "analysis_model",
    "parse_seconds", "analysis_seconds", "status", "quality", "corporate_use",
    "transaction_detail_reliable", "aggregate_rows", "bank", "account",
    "period_start", "period_end", "transactions", "summary_reconciles",
    "reconciles", "credit_coverage", "debit_coverage", "average_daily_balance",
    "deposits", "deposit_count", "withdrawals",
    "withdrawal_count", "total_posted_credits", "verified_revenue_total",
    "verified_revenue_count", "unverified_deposit_total", "unverified_deposit_count",
    "non_revenue_total", "non_revenue_count", "maximum_revenue",
    "revenue_reconciles", "revenue_reconciliation_delta", "cash_flow", "lender_credits",
    "lender_debits", "lender_debit_count", "lenders_detected",
    "potential_lenders_detected", "insurance_count", "insurance_total",
    "potential_lender_debit_count", "potential_lender_debit_total",
    "withholding_numerator", "withholding_denominator", "withholding_rate",
    "potential_withholding_numerator", "potential_withholding_denominator",
    "potential_withholding_exposure", "potential_withholding_review_required", "pos_count",
    "pos_credit_count", "atm_withdrawal_count", "loan_count",
    "nsf", "known_funders", "recurring_debit_groups",
    "markdown", "json", "error",
]


def _status(report) -> str:
    if report.metrics.revenue_review_required or not report.metrics.revenue_reconciles:
        return "needs_review"
    if report.quality.level == "summary_aggregate":
        return "summary_aggregate"
    r = report.reconciliation
    if r.ok:
        return "clean"
    if r.summary_ok is True:
        return "summary_trusted"
    if r.summary_ok is False:
        return "needs_review"
    return "needs_review"


def _pct(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else ""


def _row(path: Path, root: Path, markdown_path: Path, json_path: Path, doc, report, parse_s: float, analysis_s: float) -> dict:
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    return {
        "file": path.name,
        "folder": str(path.parent.relative_to(root)) if path.parent != root else ".",
        "pages": len(doc.pages),
        "parse_model": doc.model,
        "analysis_model": report.model_used,
        "parse_seconds": f"{parse_s:.2f}",
        "analysis_seconds": f"{analysis_s:.2f}",
        "status": _status(report),
        "quality": report.quality.level,
        "corporate_use": report.quality.corporate_use,
        "transaction_detail_reliable": "yes" if report.quality.transaction_detail_reliable else "no",
        "aggregate_rows": report.quality.aggregate_rows,
        "bank": s.bank or "",
        "account": s.account_number or "",
        "period_start": s.period_start or "",
        "period_end": s.period_end or "",
        "transactions": len(s.transactions),
        "summary_reconciles": {True: "yes", False: "no", None: "n/a"}[r.summary_ok],
        "reconciles": "yes" if r.ok else "no",
        "credit_coverage": _pct(r.credit_coverage),
        "debit_coverage": _pct(r.debit_coverage),
        "average_daily_balance": (
            f"{m.average_daily_balance:.2f}"
            if m.average_daily_balance is not None
            else ""
        ),
        "deposits": f"{m.effective_total_deposits:.2f}",
        "deposit_count": m.effective_num_deposits,
        "withdrawals": f"{m.effective_total_withdrawals:.2f}",
        "withdrawal_count": m.effective_num_withdrawals,
        "total_posted_credits": f"{m.total_posted_credits:.2f}",
        "verified_revenue_total": f"{m.verified_revenue_total:.2f}",
        "verified_revenue_count": m.verified_revenue_count,
        "unverified_deposit_total": f"{m.unverified_deposit_total:.2f}",
        "unverified_deposit_count": m.unverified_deposit_count,
        "non_revenue_total": f"{m.non_revenue_total:.2f}",
        "non_revenue_count": m.non_revenue_count,
        "maximum_revenue": f"{m.maximum_revenue:.2f}",
        "revenue_reconciles": "yes" if m.revenue_reconciles else "no",
        "revenue_reconciliation_delta": f"{m.revenue_reconciliation_delta:.2f}",
        "cash_flow": f"{m.cash_flow:.2f}",
        "lender_credits": f"{m.lender_credits:.2f}",
        "lender_debits": f"{m.lender_debits:.2f}",
        "lender_debit_count": m.lender_debit_count,
        "lenders_detected": m.lenders_detected,
        "potential_lenders_detected": m.potential_lenders_detected,
        "potential_lender_debit_count": m.potential_lender_debit_count,
        "potential_lender_debit_total": f"{m.potential_lender_debit_total:.2f}",
        "insurance_count": m.insurance_count,
        "insurance_total": f"{m.insurance_total:.2f}",
        "withholding_numerator": f"{m.withholding_numerator:.2f}",
        "withholding_denominator": f"{m.withholding_denominator:.2f}",
        "withholding_rate": f"{m.withholding_rate:.2f}" if m.withholding_rate is not None else "",
        "potential_withholding_numerator": f"{m.potential_withholding_numerator:.2f}",
        "potential_withholding_denominator": f"{m.potential_withholding_denominator:.2f}",
        "potential_withholding_exposure": (
            f"{m.potential_withholding_exposure:.2f}"
            if m.potential_withholding_exposure is not None
            else ""
        ),
        "potential_withholding_review_required": m.potential_withholding_review_required,
        "pos_count": m.pos_count,
        "pos_credit_count": m.pos_credit_count,
        "atm_withdrawal_count": m.atm_withdrawal_count,
        "loan_count": m.loan_count,
        "nsf": m.effective_nsf_count,
        "known_funders": "; ".join(fm.funder for fm in d.known_funders),
        "recurring_debit_groups": sum(1 for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")),
        "markdown": str(markdown_path),
        "json": str(json_path),
        "error": "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit statement parsing coverage.")
    ap.add_argument("path", help="PDF file or folder of PDFs.")
    ap.add_argument("--out", default="output/coverage_audit.csv", help="CSV output path.")
    ap.add_argument("--artifacts", default="output/coverage_audit", help="Folder for markdown/json artifacts.")
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N PDFs.")
    ap.add_argument("--start", type=int, default=1, help="One-based file index to start from.")
    ap.add_argument("--indexes", default="", help="Comma-separated one-based file indexes to process.")
    args = ap.parse_args()

    root = Path(args.path)
    files = [root] if root.is_file() else sorted(root.rglob("*.pdf"))
    selected_indexes: list[int] | None = None
    if args.indexes:
        selected_indexes = [int(part.strip()) for part in args.indexes.split(",") if part.strip()]
        files = [files[i - 1] for i in selected_indexes]
    elif args.start > 1:
        files = files[args.start - 1:]
    if args.limit is not None:
        files = files[:args.limit]
    artifact_root = Path(args.artifacts)
    artifact_root.mkdir(parents=True, exist_ok=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for local_index, path in enumerate(files, args.start):
            offset = selected_indexes[local_index - args.start] if selected_indexes else local_index
            print(f"[{offset}] {path}", flush=True)
            stem = f"{offset:03d}_{path.stem}"
            markdown_path = artifact_root / f"{stem}.md"
            json_path = artifact_root / f"{stem}.json"
            try:
                t0 = time.perf_counter()
                doc = parse_statement(path.read_bytes(), source_file=path.name)
                markdown = doc.to_markdown()
                parse_s = time.perf_counter() - t0
                markdown_path.write_text(markdown, encoding="utf-8")

                t1 = time.perf_counter()
                report = analyze_markdown(markdown)
                analysis_s = time.perf_counter() - t1
                json_path.write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")
                row = _row(path, root if root.is_dir() else path.parent, markdown_path, json_path, doc, report, parse_s, analysis_s)
            except Exception as e:
                traceback.print_exc()
                row = {**{k: "" for k in FIELDS}, "file": path.name,
                       "folder": str(path.parent), "status": "failed",
                       "markdown": str(markdown_path), "json": str(json_path),
                       "error": f"{type(e).__name__}: {e}"}
            writer.writerow(row)
            f.flush()
            rows.append(row)

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"Wrote {len(rows)} rows to {out}: {counts}")


if __name__ == "__main__":
    main()

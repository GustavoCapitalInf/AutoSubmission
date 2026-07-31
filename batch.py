"""Batch-analyze a folder of bank statements into one triage CSV.

Accepts OCR'd markdown files (fast) and/or PDFs (OCR'd first via the running OCR
server — set OCR_BASE_URL/OCR_API_KEY). One row per statement with the key
underwriting figures and a needs_review flag so clean statements flow through and
only the questionable ones get human eyes.

Usage:
  .venv/bin/python batch.py output/ --out triage.csv          # a folder of .md
  OCR_BASE_URL=http://localhost:8000/v1 OCR_API_KEY=EMPTY \\
      .venv/bin/python batch.py BankStatements/ --out triage.csv   # PDFs (OCR+analyze)
"""
from __future__ import annotations
import argparse
import csv
import sys
import traceback
from pathlib import Path

from analysis.pipeline import analyze_markdown, Report

FIELDS = [
    "file", "bank", "account", "period_start", "period_end",
    "summary_reconciles", "avg_balance", "total_deposits", "total_debits",
    "true_revenue", "cash_flow", "lender_credits", "lender_debits",
    "monthly_lender_debits", "withholding_rate", "pos_count", "pos_credit_count",
    "atm_withdrawal_count", "loan_count",
    "debit_coverage", "nsf", "mca_funders", "recurring_debit_groups",
    "quality", "transaction_detail_reliable", "corporate_use", "needs_review",
    "model", "error",
]


def _markdown_for(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from ocr.pipeline import parse_statement
        doc = parse_statement(path.read_bytes(), source_file=path.name)
        return doc.to_markdown()
    return path.read_text(encoding="utf-8")


def _row(path: Path, report: Report) -> dict:
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    # A statement needs human review when the bank's own summary doesn't reconcile
    # (mis-extracted or internally inconsistent) — the figures can't be trusted.
    needs_review = report.quality.corporate_use == "manual_review_required"
    return {
        "file": path.name,
        "bank": s.bank or "",
        "account": s.account_number or "",
        "period_start": s.period_start or "",
        "period_end": s.period_end or "",
        "summary_reconciles": {True: "yes", False: "NO", None: "n/a"}[r.summary_ok],
        "avg_balance": f"{m.average_balance:.2f}" if m.average_balance is not None else "",
        "total_deposits": f"{m.effective_total_deposits:.2f}",
        "total_debits": f"{m.effective_total_withdrawals:.2f}",
        "true_revenue": f"{m.true_revenue:.2f}",
        "cash_flow": f"{m.cash_flow:.2f}",
        "lender_credits": f"{m.lender_credits:.2f}",
        "lender_debits": f"{m.lender_debits:.2f}",
        "monthly_lender_debits": f"{m.monthly_lender_debits:.2f}",
        "withholding_rate": f"{m.withholding_rate:.2f}" if m.withholding_rate is not None else "",
        "pos_count": m.pos_count,
        "pos_credit_count": m.pos_credit_count,
        "atm_withdrawal_count": m.atm_withdrawal_count,
        "loan_count": m.loan_count,
        "debit_coverage": f"{r.debit_coverage:.0%}" if r.debit_coverage is not None else "",
        "nsf": m.effective_nsf_count,
        "mca_funders": "; ".join(fm.funder for fm in d.known_funders),
        "recurring_debit_groups": sum(1 for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")),
        "quality": report.quality.level,
        "transaction_detail_reliable": "yes" if report.quality.transaction_detail_reliable else "no",
        "corporate_use": report.quality.corporate_use,
        "needs_review": "REVIEW" if needs_review else "",
        "model": report.model_used,
        "error": "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch-analyze statements into a triage CSV.")
    ap.add_argument("path", help="A file or directory of .md and/or .pdf statements.")
    ap.add_argument("--out", metavar="FILE", help="Write CSV here (default stdout).")
    args = ap.parse_args()

    root = Path(args.path)
    if root.is_dir():
        files = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".md", ".pdf"))
    else:
        files = [root]
    if not files:
        print(f"no .md/.pdf statements found under {root}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for path in files:
        print(f"analyzing {path.name} ...", file=sys.stderr, flush=True)
        try:
            report = analyze_markdown(_markdown_for(path))
            rows.append(_row(path, report))
        except Exception as e:  # keep going; record the failure in its row
            traceback.print_exc()
            rows.append({**{k: "" for k in FIELDS}, "file": path.name,
                         "needs_review": "REVIEW", "error": f"{type(e).__name__}: {e}"})

    out = open(args.out, "w", newline="", encoding="utf-8") if args.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    if args.out:
        out.close()
        need = sum(1 for r in rows if r["needs_review"])
        print(f"\nWrote {len(rows)} rows to {args.out}  ({need} flagged for review)", file=sys.stderr)


if __name__ == "__main__":
    main()

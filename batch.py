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
    "debit_coverage", "nsf", "mca_funders", "recurring_debit_groups",
    "needs_review", "model", "error",
]


def _markdown_for(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from ocr.pipeline import parse_statement
        doc = parse_statement(path.read_bytes(), source_file=path.name)
        return doc.to_markdown()
    return path.read_text(encoding="utf-8")


def _row(path: Path, report: Report) -> dict:
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    avg = m.stated_average_balance if m.stated_average_balance is not None else m.average_daily_balance
    nsf = m.stated_nsf_count if m.stated_nsf_count is not None else m.nsf_count
    # A statement needs human review when the bank's own summary doesn't reconcile
    # (mis-extracted or internally inconsistent) — the figures can't be trusted.
    needs_review = r.summary_ok is False or (r.summary_ok is None and not r.ok)
    return {
        "file": path.name,
        "bank": s.bank or "",
        "account": s.account_number or "",
        "period_start": s.period_start or "",
        "period_end": s.period_end or "",
        "summary_reconciles": {True: "yes", False: "NO", None: "n/a"}[r.summary_ok],
        "avg_balance": f"{avg:.2f}" if avg is not None else "",
        "total_deposits": f"{s.stated_total_credits:.2f}" if s.stated_total_credits is not None else f"{m.total_deposits:.2f}",
        "total_debits": f"{s.stated_total_debits:.2f}" if s.stated_total_debits is not None else f"{m.total_withdrawals:.2f}",
        "debit_coverage": f"{r.debit_coverage:.0%}" if r.debit_coverage is not None else "",
        "nsf": nsf,
        "mca_funders": "; ".join(fm.funder for fm in d.known_funders),
        "recurring_debit_groups": sum(1 for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")),
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

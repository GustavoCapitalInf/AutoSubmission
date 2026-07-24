"""Analyze an OCR'd bank statement (markdown) into structured metrics and
MCA/lender findings.

Usage:
  .venv/bin/python analyze.py output/ace.md              # human-readable report
  .venv/bin/python analyze.py output/ace.md --json out.json
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from analysis.pipeline import analyze_markdown, Report


def _render(report: Report) -> str:
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    L: list[str] = []
    L.append(f"# {s.bank or 'Bank'} — {s.account_name or 'Account'}")
    if s.account_number:
        L.append(f"Account: {s.account_number}")
    L.append(f"Period: {s.period_start} -> {s.period_end}")
    L.append(f"Balance: {s.beginning_balance} -> {s.ending_balance}   "
             f"({len(s.transactions)} transactions)")
    L.append(f"Model: {report.model_used}{'  (escalated)' if report.escalated else ''}")

    L.append("\n## Reconciliation")
    # The backbone signal: is the bank's own printed summary internally consistent?
    if r.summary_ok is True:
        L.append("  Bank summary: reconciles ✓  (stated totals are trustworthy)")
    elif r.summary_ok is False:
        L.append("  Bank summary: INCONSISTENT ✗  (stated totals look mis-extracted — needs review)")
    L.append("  OK" if r.ok else "  ISSUES FOUND — trust the bank-stated figures over line-item sums:")
    for issue in r.issues:
        L.append(f"    - {issue}")
    if r.debit_coverage is not None:
        L.append(f"  Line-item coverage    : {r.debit_coverage:.0%} of stated debits, "
                 + (f"{r.credit_coverage:.0%} of stated credits" if r.credit_coverage is not None else "credits n/a"))

    L.append("\n## Metrics")
    if m.stated_average_balance is not None:
        L.append(f"  Average balance (bank): ${m.stated_average_balance:,.2f}   [as printed on the statement]")
    adb = f"${m.average_daily_balance:,.2f}" if m.average_daily_balance is not None else "n/a"
    L.append(f"  Average daily balance : {adb}"
             + (f"  (computed over {m.days_in_period} days)" if m.average_daily_balance is not None and m.days_in_period else "  [computed]"))
    if m.min_balance is not None:
        L.append(f"  Min / max balance     : ${m.min_balance:,.2f} / ${m.max_balance:,.2f}")
    L.append(f"  Negative days         : {m.negative_days}")
    dep = f"  Deposits (line items) : ${m.total_deposits:,.2f}  ({m.num_deposits})"
    if s.stated_total_credits is not None:
        dep += f"   | bank-stated ${s.stated_total_credits:,.2f} ({s.stated_credit_count})"
    L.append(dep)
    wd = f"  Withdrawals (line item): ${m.total_withdrawals:,.2f}  ({m.num_withdrawals})"
    if s.stated_total_debits is not None:
        wd += f"   | bank-stated ${s.stated_total_debits:,.2f} ({s.stated_debit_count})"
    L.append(wd)
    nsf = f"  NSF / overdraft       : {m.nsf_count} (line items)"
    if m.stated_nsf_count is not None:
        nsf += f"   | bank-stated {m.stated_nsf_count}"
    L.append(nsf)
    for note in m.notes:
        L.append(f"  note: {note}")

    L.append("\n## MCA / lender detection")
    if d.known_funders:
        L.append("  Known funders matched:")
        for fm in d.known_funders:
            L.append(f"    - {fm.funder}: {len(fm.transactions)} txns, "
                     f"${fm.total_debited:,.2f} debited (alias '{fm.matched_alias}')")
    else:
        L.append("  Known funders matched: none")
    regular = [rc for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")]
    if regular:
        L.append("  Recurring fixed debits (MCA remittance pattern):")
        for rc in regular:
            L.append(f"    - ${rc.amount:,.2f} x{rc.count} [{rc.cadence}] : {rc.description_key[:50]}")
    else:
        L.append("  Recurring fixed debits: none with a regular cadence")
    return "\n".join(L)


def _json_safe(report: Report) -> dict:
    d = {
        "statement": report.statement.model_dump(),
        "reconciliation": asdict(report.reconciliation),
        "metrics": asdict(report.metrics),
        "detection": {
            "known_funders": [
                {**{k: v for k, v in asdict(fm).items() if k != "transactions"},
                 "transactions": [t.model_dump() for t in fm.transactions]}
                for fm in report.detection.known_funders
            ],
            "recurring_debits": [
                {**{k: v for k, v in asdict(rc).items() if k != "transactions"},
                 "transactions": [t.model_dump() for t in rc.transactions]}
                for rc in report.detection.recurring_debits
            ],
        },
        "model_used": report.model_used,
        "escalated": report.escalated,
    }
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze an OCR'd bank statement.")
    ap.add_argument("markdown", help="Path to the OCR markdown file.")
    ap.add_argument("--json", metavar="FILE", help="Also write the full report as JSON.")
    args = ap.parse_args()

    with open(args.markdown, encoding="utf-8") as f:
        markdown = f.read()

    report = analyze_markdown(markdown)
    print(_render(report))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(_json_safe(report), f, indent=2)
        print(f"\nWrote JSON report to {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()

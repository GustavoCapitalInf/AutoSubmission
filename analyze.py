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
from analysis.pipeline import analyze_markdown, Report
from analysis.serialization import report_to_dict


def _render(report: Report) -> str:
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    L: list[str] = []
    L.append(f"# {s.bank or 'Bank'} - {s.account_name or 'Account'}")
    if s.account_number:
        L.append(f"Account: {s.account_number}")
    L.append(f"Period: {s.period_start} -> {s.period_end}")
    L.append(f"Balance: {s.beginning_balance} -> {s.ending_balance}   "
             f"({len(s.transactions)} transactions)")
    L.append(f"Model: {report.model_used}{'  (escalated)' if report.escalated else ''}")
    L.append(
        f"Quality: {report.quality.level} "
        f"(corporate_use={report.quality.corporate_use}, "
        f"transaction_detail_reliable={report.quality.transaction_detail_reliable})"
    )
    L.append(
        f"Integrity: {report.integrity.risk_level} "
        f"(possible_document_issue={report.integrity.possible_document_issue})"
    )

    L.append("\n## Reconciliation")
    # The backbone signal: is the bank's own printed summary internally consistent?
    if r.summary_ok is True:
        L.append("  Bank summary: reconciles OK  (stated totals are trustworthy)")
    elif r.summary_ok is False:
        L.append("  Bank summary: INCONSISTENT  (stated totals look mis-extracted - needs review)")
    L.append("  OK" if r.ok else "  ISSUES FOUND - trust the bank-stated figures over line-item sums:")
    for issue in r.issues:
        L.append(f"    - {issue}")
    if r.debit_coverage is not None:
        L.append(f"  Line-item coverage    : {r.debit_coverage:.0%} of stated debits, "
                 + (f"{r.credit_coverage:.0%} of stated credits" if r.credit_coverage is not None else "credits n/a"))

    L.append("\n## Metrics")
    avg = f"${m.average_balance:,.2f}" if m.average_balance is not None else "n/a"
    L.append(f"  Average balance       : {avg}"
             + (f"  [{m.average_balance_source}]" if m.average_balance_source else ""))
    if m.stated_average_balance is not None and m.average_daily_balance is not None:
        L.append(f"  Average daily balance : ${m.average_daily_balance:,.2f}  (computed over {m.days_in_period} days)")
    if m.min_balance is not None:
        L.append(f"  Min / max balance     : ${m.min_balance:,.2f} / ${m.max_balance:,.2f}")
    L.append(f"  Negative days         : {m.negative_days}")
    dep = (f"  Deposits              : ${m.effective_total_deposits:,.2f}  "
           f"({m.effective_num_deposits}) [{m.deposits_source}]")
    if m.deposits_source != "line_items":
        dep += f"   | line items ${m.total_deposits:,.2f} ({m.num_deposits})"
    L.append(dep)
    wd = (f"  Withdrawals           : ${m.effective_total_withdrawals:,.2f}  "
          f"({m.effective_num_withdrawals}) [{m.withdrawals_source}]")
    if m.withdrawals_source != "line_items":
        wd += f"   | line items ${m.total_withdrawals:,.2f} ({m.num_withdrawals})"
    L.append(wd)
    L.append(
        f"  Verified revenue      : ${m.verified_revenue_total:,.2f}  "
        f"({m.verified_revenue_count} credit(s))"
    )
    L.append(
        f"  Unverified deposits   : ${m.unverified_deposit_total:,.2f}  "
        f"({m.unverified_deposit_count} credit(s); review required)"
    )
    L.append(
        f"  Non-revenue credits   : ${m.non_revenue_total:,.2f}  "
        f"({m.non_revenue_count} credit(s))"
    )
    L.append(f"  Maximum revenue       : ${m.maximum_revenue:,.2f}")
    L.append(
        f"  Revenue reconciliation: {'balanced' if m.revenue_reconciles else 'REVIEW'}  "
        f"(delta ${m.revenue_reconciliation_delta:,.2f})"
    )
    L.append(f"  Cash flow             : ${m.cash_flow:,.2f}")
    withholding = f"{m.withholding_rate:.2f}%" if m.withholding_rate is not None else "n/a"
    L.append(
        f"  Lender debits         : {m.lender_debit_count} row(s), ${m.lender_debits:,.2f}  "
        f"(withholding {withholding})"
    )
    L.append(
        f"  Withholding working   : ${m.withholding_numerator:,.2f} / "
        f"${m.withholding_denominator:,.2f} eligible deposits"
    )
    potential_exposure = (
        f"{m.potential_withholding_exposure:.2f}%"
        if m.potential_withholding_exposure is not None
        else "n/a"
    )
    potential_status = "review required" if m.potential_withholding_review_required else "clear"
    L.append(
        f"  Potential debits      : {m.potential_lender_debit_count} row(s), "
        f"${m.potential_lender_debit_total:,.2f} "
        f"(exposure {potential_exposure}; {potential_status})"
    )
    L.append(
        f"  Potential working     : ${m.potential_withholding_numerator:,.2f} / "
        f"${m.potential_withholding_denominator:,.2f} eligible deposits"
    )
    L.append(f"  Insurance debits      : {m.insurance_count} row(s), ${m.insurance_total:,.2f}")
    L.append(
        f"  POS purchases/credits : {m.pos_count} / {m.pos_credit_count}"
    )
    L.append(f"  ATM withdrawals       : {m.atm_withdrawal_count}")
    L.append(f"  Loan count            : {m.loan_count}")
    L.append(f"  NSF events            : {m.effective_nsf_count} [{m.nsf_source}]")
    for note in m.notes:
        L.append(f"  note: {note}")
    if report.quality.notes:
        for note in report.quality.notes:
            L.append(f"  quality note: {note}")
    for note in report.integrity.notes:
        L.append(f"  integrity note: {note}")

    L.append("\n## MCA / lender detection")
    if d.known_funders:
        L.append("  Known funders matched:")
        for fm in d.known_funders:
            L.append(f"    - {fm.funder}: {len(fm.transactions)} txns, "
                     f"${fm.total_debited:,.2f} debited (alias '{fm.matched_alias}')")
    else:
        L.append("  Known funders matched: none")
    if d.potential_lenders:
        L.append("  Potential lenders requiring review:")
        for fm in d.potential_lenders:
            exposure = (
                f"{fm.potential_withholding_exposure:.2f}%"
                if fm.potential_withholding_exposure is not None
                else "n/a"
            )
            denominator = (
                f"${fm.eligible_deposit_denominator:,.2f}"
                if fm.eligible_deposit_denominator is not None
                else "n/a"
            )
            L.append(
                f"    - {fm.funder}: {fm.debit_count} debit(s), "
                f"${fm.total_debited:,.2f}; {exposure} exposure / {denominator} deposits"
            )
    else:
        L.append("  Potential lenders: none")
    if d.insurance_providers:
        L.append("  Insurance providers:")
        for provider in d.insurance_providers:
            L.append(
                f"    - {provider.provider}: {provider.count} debit(s), "
                f"${provider.total_debited:,.2f}"
            )
    else:
        L.append("  Insurance providers: none")
    regular = [rc for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")]
    if regular:
        L.append("  Recurring fixed debits (MCA remittance pattern):")
        for rc in regular:
            L.append(f"    - ${rc.amount:,.2f} x{rc.count} [{rc.cadence}] : {rc.description_key[:50]}")
    else:
        L.append("  Recurring fixed debits: none with a regular cadence")
    return "\n".join(L)


def _json_safe(report: Report) -> dict:
    return report_to_dict(report)


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

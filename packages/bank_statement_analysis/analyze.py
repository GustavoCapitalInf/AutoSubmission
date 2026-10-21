"""Analyze an OCR'd bank statement (markdown) into structured metrics and
MCA/lender findings.

Usage:
  .venv/bin/python analyze.py output/ace.md              # human-readable report
  .venv/bin/python analyze.py output/ace.md --json out.json
  .venv/bin/python analyze.py output/ace.md --zelle-true-revenue no

`--zelle-true-revenue` is the owner's "Mark Zelle Payments as True Revenue"
(the underwriter's Q3, amended 2026-10-06): yes (the default, as the
Settings page's) counts Zelle deposits as the rules read them; no excludes
them. The CLI reads no webapp setting.
"""
from __future__ import annotations
import argparse
import json
import sys
from analysis import zelle_view
from analysis.active_positions import statement_active_positions
from analysis.pipeline import analyze_document, DocumentReport, Report
from analysis.revenue_view import (
    LARGE_UNSOURCED_DEPOSIT_FLOOR, apply_revenue_view, revenue_flags, withholding_basis_unestablished,
)
from analysis.serialization import document_report_to_dict
from analysis.flag_groups import FLAG_GROUP_BY_KEY

#: Audit round 2, R2-B16 (R52): a revenue figure the account's flags do not establish.
_NOT_ESTABLISHED = "N/A (not established)"


def _revenue_flags(report: Report) -> tuple[bool, bool]:
    """Audit round 2, R2-B16 (R52; true revenue spec §10.4): `(verified_revenue_established, revenue_established)` of
    one account in the reading shown, from its serialized payload (analysis/revenue_view.py `revenue_flags`, the
    flags the dashboard and the downloads read). The account is serialized through the document entry point as a
    document of its one account, which RULE S publishes as that account's payload (the L1-S3 seam rule); never in
    revenue_view, which does not import the serializer."""
    return revenue_flags(document_report_to_dict(DocumentReport(accounts=[report])))


def _unit_money(value: float, currency: str | None) -> str:
    """Audit round 3, final review (R3-FF), F6: money in the statement's own unit: '$1,234.56' on a USD statement (the
    CLI's '$', which every other line prints) or one that declares none, '1,234.56 CAD' on any other (the metrics notes'
    form; CURRENCY DOCTRINE: never a '$' on a CAD statement)."""
    unit = str(currency or "").strip().upper()
    return f"{value:,.2f} {unit}" if unit and unit != "USD" else f"${value:,.2f}"


def _large_unsourced_line(report: Report) -> str | None:
    """Audit round 3, R3-B24 (R3-16; §13): "  Large deposits to source: N, $X (each $10,000.00 or more and over 25% of
    True; information only)" where the account's served copy (analysis/revenue_view.py apply_revenue_view, over the
    payload `_revenue_flags` reads) flags one, else None. Audit round 3, final review (R3-FF), F6: the total and the floor
    (LARGE_UNSOURCED_DEPOSIT_FLOOR, compared in the statement's own unit) are written in that unit (_unit_money)."""
    served = apply_revenue_view(document_report_to_dict(DocumentReport(accounts=[report])))
    metrics = served.get("metrics") if isinstance(served, dict) else None
    count = metrics.get("large_unsourced_deposit_count") if isinstance(metrics, dict) else None
    if not count:
        return None
    currency = report.statement.currency
    return (f"  Large deposits to source: {count}, {_unit_money(metrics['large_unsourced_deposit_total'], currency)} "
            f"(each {_unit_money(LARGE_UNSOURCED_DEPOSIT_FLOOR, currency)} or more and over 25% of True; "
            "information only)")


def _revenue_reconciliation_label(ledger_reconciles: bool, established: bool) -> str:
    """R52: "Balanced" where the ledger reconciles and the revenue is established (app.js statementRevenueBalanced),
    otherwise "Review required" and why: the ledger does not reconcile, or the captured credits are not the money the
    bank's total counts."""
    if ledger_reconciles and established:
        return "Balanced"
    if not ledger_reconciles:
        return "Review required (ledger does not reconcile)"
    return "Review required (captured credits differ from the bank-stated total)"


def _zelle_line(stored: Report, shown: Report, *, established: bool = True) -> str | None:
    """The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): under Yes, where the statement has Zelle
    policy rows, one line saying where the Zelle money sits (analysis/zelle_view.py's figures over the records).

    Audit round 3, R3-B20 (R3-48; §10.4's I51 and R52): where the revenue is not `established`, the line keeps what the
    captured rows say (the Zelle total and count, and the non-revenue part) and reads the parts in True revenue and held
    for review as N/A, as the True and Held lines do; the established line is unchanged."""
    figures = zelle_view.record_zelle_figures(stored.classifications, shown.classifications)
    if figures is None:
        return None
    parts = zelle_view.figure_parts(figures)
    out = f", ${parts['out']:,.2f} non-revenue" if parts["out"] > 0 else ""
    if not established:
        return (
            f"  Zelle deposits: ${figures['total']:,.2f} ({figures['count']}), captured rows only; in True revenue and "
            f"held for review: {_NOT_ESTABLISHED}{out} (Mark Zelle Payments as True Revenue: Yes; "
            "--zelle-true-revenue no excludes them)"
        )
    return (
        f"  Zelle deposits: ${figures['total']:,.2f} ({figures['count']}): ${parts['in_true']:,.2f} in True revenue, "
        f"${parts['held']:,.2f} held for review{out} (Mark Zelle Payments as True Revenue: Yes; "
        "--zelle-true-revenue no excludes them)"
    )


def _active_positions_text(report: Report) -> str:
    """The owner's request of 2026-10-10 (active positions by month): "2" or "2 (+1 possible)", the statement's
    confirmed and possible active positions over its printed period (analysis/active_positions.py, from its
    classification records)."""
    s = report.statement
    found = statement_active_positions(report.classifications, period_start=s.period_start,
                                       period_end=s.period_end, currency=s.currency)
    possible = found["possible_positions"]
    return f"{found['active_positions']}" + (f" (+{possible} possible)" if possible else "")


def _payment_change_line(item: dict) -> str:
    """The owner's request of 2026-10-06 (lender payment changes; R2-OW18, I1): one statement-level item as a CLI
    line."""
    potential = " (potential)" if item.get("lender_state") == "potential" else ""
    label = item.get("lender_label") or item.get("lender")
    kind = item.get("kind")
    if kind in ("decrease", "increase", "cadence_change"):
        name = "schedule change" if kind == "cadence_change" else kind
        changed = item.get("cadence_changed") is True
        after = f"{item['cadence_after']} " if changed else ""
        percent = f"{item['change_percent']:+d}%" if item["change_percent"] else "0%"
        measure = f"weekly equivalent {percent}" if changed else percent
        possible = ", possible: new schedule not yet confirmed" if item.get("schedule_confirmed") is False else ""
        # R2-OW18 review round 1: the unreported levels with the step into each, then the last step.
        via = [entry for entry in item.get("via") or [] if isinstance(entry, dict)]
        steps = ""
        if via:
            steps = ", via " + ", ".join(
                f"{entry['cadence']} ${entry['amount']:,.2f}"
                + (f" ({entry['change_percent']:+d}%)" if isinstance(entry.get("change_percent"), int) else "")
                for entry in via)
            if isinstance(item.get("last_step_percent"), int):
                steps += f", then {item['last_step_percent']:+d}%"
        return (f"{name}{potential}: {label} {item['cadence_before']} ${item['amount_before']:,.2f} -> {after}"
                f"${item['amount_after']:,.2f} ({measure}) from {item['first_after_date']}, "
                f"{item['payments_after']} payments (was {item['payments_before']}){possible}{steps}")
    if kind == "pause":
        # R2-OW18 review round 1: a bounced attempt or a payment at another amount that ended the pause is named.
        ended = item.get("first_after_kind")
        what = "no payment or attempt" if ended == "attempt" else "no payment"
        tail = ""
        if ended == "attempt":
            tail = f"; a returned attempt on {item['first_after_date']}, payments resumed on {item.get('resumed_date')}"
        elif ended == "other_amount":
            tail = (f"; a payment at another amount on {item['first_after_date']}, payments resumed on "
                    f"{item.get('resumed_date')}")
        elif ended == "catch_up":
            # Audit round 3, R3-25: an exact 2x to 6x debit ended the pause.
            tail = (f"; a catch-up of {item.get('first_after_multiple')}x on {item['first_after_date']}, payments "
                    f"resumed on {item.get('resumed_date')}")
        # R3-B05 review round 1: a catch-up after the presence that ended the pause, before payments resumed.
        tail += "".join(f"; a catch-up of {entry.get('multiple')}x on {entry.get('date')} before payments resumed"
                        for entry in item.get("catch_ups_inside") or [] if isinstance(entry, dict))
        return (f"pause{potential}: {label} {item['cadence']} ${item['last_payment_amount']:,.2f}, {what} "
                f"{item['last_before_date']} to {item['first_after_date']}, {item['pause_business_days']} business days "
                f"(grace {item['grace_business_days']}){tail}")
    if kind == "catch_up":
        # The owner's answer of 2026-10-07 to audit round 3's R3-25 ("Add a 'Caught up' line").
        missed = item.get("missed_payments")
        span = item.get("missed_first_date")
        if item.get("missed_last_date") and item.get("missed_last_date") != span:
            span = f"{span} to {item['missed_last_date']}"
        return (f"catch-up{potential}: {label} {item['cadence']} ${item['last_payment_amount']:,.2f}, no payment on "
                f"{missed} scheduled {'payment' if missed == 1 else 'payments'} {span}, then {item['multiple']}x "
                f"${item['catch_up_amount']:,.2f} on {item['catch_up_date']}")
    if kind == "new_stream":
        alongside = " and ".join(f"{other['cadence']} ${other['amount']:,.2f}" for other in item.get("alongside") or [])
        return (f"new stream{potential}: {label} {item['cadence_after']} ${item['amount_after']:,.2f} from "
                f"{item['first_after_date']} alongside {alongside}, weekly total {item['change_percent']:+d}%")
    end = "the period end" if item.get("coverage_end_source") == "period_end" else "the last transaction"
    lead = "stop" if item.get("stop_confirmed") is True else "possible stop"
    # R2-OW18 review round 1: the quiet days run from the last presence; a returned attempt there is named.
    attempt = item.get("last_attempt_returned")
    returned = f", a returned attempt on {attempt.get('date')}" if isinstance(attempt, dict) else ""
    # Audit round 3, R3-85: the later debits at other amounts are named, and where the last presence is not the last
    # payment the count names its anchor.
    others = item.get("other_debits_after")
    later = ""
    if isinstance(others, dict):
        count = others.get("count")
        later = (f"; {count} later {'debit' if count == 1 else 'debits'} at other amounts, the last on "
                 f"{others.get('last_date')}")
    presence = item.get("last_presence_date")
    anchor = f" after {presence}" if presence and presence != item.get("last_payment_date") else ""
    return (f"{lead}{potential}: {label} {item['cadence']}, last ${item['last_payment_amount']:,.2f} on "
            f"{item['last_payment_date']}{returned}{later}{'; ' if later else ', '}{item['quiet_business_days']} "
            f"business days{anchor} to {end} (grace {item['grace_business_days']})")


def _render(stored: Report, zelle_true_revenue: bool = True) -> str:
    """One account's report in the Zelle reading asked for: the counted reading (`Report.zelle_counted`) under Yes
    where the statement has one, else the stored Report. Under No it prints today's lines exactly."""
    report = stored.zelle_counted if zelle_true_revenue and stored.zelle_counted is not None else stored
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
    adb = (
        f"${m.average_daily_balance:,.2f}  (computed over {m.days_in_period} days)"
        if m.average_daily_balance is not None
        else "n/a"
    )
    L.append(f"  Average daily balance : {adb}")
    if m.stated_average_balance is not None:
        L.append(f"  Bank-printed average  : ${m.stated_average_balance:,.2f}  (comparison only)")
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
    # 5.6 (true revenue spec §5.1): True revenue first, then its verified part, the counted and held credits. Audit
    # round 2, R2-B16 (R52; §10.4): a figure the account's revenue flags do not establish reads N/A, as the dashboard
    # and the downloads read it.
    verified_established, established = _revenue_flags(report)

    def figure(text: str, shown: bool) -> str:
        return text if shown else _NOT_ESTABLISHED

    L.append(
        "  True revenue          : "
        + figure(f"${m.true_revenue_total:,.2f}  ({m.true_revenue_count} credit(s))", established)
    )
    L.append(
        "  Verified revenue      : "
        + figure(f"${m.verified_revenue_total:,.2f}  ({m.verified_revenue_count} credit(s))", verified_established)
    )
    L.append(
        "  Counted, not verified : "
        + figure(f"${m.counted_flagged_total:,.2f}  ({m.counted_flagged_count} credit(s))", established)
    )
    L.append(
        "  Held for review       : "
        + figure(f"${m.excluded_pending_review_total:,.2f}  ({m.excluded_pending_review_count} credit(s))",
                 established)
    )
    # Audit round 3, R3-B24 (R3-16; true revenue spec §13; standard G7, P22): the counted credits whose source the
    # statement does not prove that are large beside its True, as the account is served (only where one is flagged on a
    # statement whose revenue is established); information only.
    large = _large_unsourced_line(report)
    if large is not None:
        L.append(large)
    L.append(
        "  Unverified deposits   : "
        + figure(f"${m.unverified_deposit_total:,.2f}  ({m.unverified_deposit_count} credit(s): counted plus held)",
                 established)
    )
    L.append(
        f"  Non-revenue credits   : ${m.non_revenue_total:,.2f}  "
        f"({m.non_revenue_count} credit(s))"
    )
    zelle = _zelle_line(stored, report, established=established) if zelle_true_revenue else None
    if zelle is not None:
        L.append(zelle)
    L.append("  Maximum revenue       : " + figure(f"${m.maximum_revenue:,.2f}", established))
    # R52 (audit B11's I31 on the CLI): "Balanced" only where the ledger reconciles and the revenue is established (the
    # dashboard's rule, app.js statementRevenueBalanced); the four-tier identity under its own name beside it.
    L.append(f"  Revenue reconciliation: {_revenue_reconciliation_label(r.ok is True, established)}")
    L.append(
        f"  Tiers sum to posted   : {'yes' if m.revenue_tiers_sum_to_posted else 'NO'} "
        f"(delta ${m.revenue_reconciliation_delta:,.2f})"
    )
    L.append(f"  Cash flow             : ${m.cash_flow:,.2f}")
    # The final review of round 2, F1 (§10.4, §11): no rate over a withholding basis that is not established (True
    # revenue where the revenue is not, Verified where Verified is not); the legacy basis prints as before.
    basis_unestablished = withholding_basis_unestablished(
        m.withholding_denominator_mode, verified_established=verified_established, established=established)

    def basis(value: float) -> str:
        return _NOT_ESTABLISHED if basis_unestablished else f"${value:,.2f}"

    if basis_unestablished:
        withholding = _NOT_ESTABLISHED
    else:
        withholding = f"{m.withholding_rate:.2f}%" if m.withholding_rate is not None else "n/a"
    L.append(
        f"  Lender debits         : {m.lender_debit_count} row(s), ${m.lender_debits:,.2f}  "
        f"(withholding {withholding})"
    )
    # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): the funder payments returned unpaid, out of the lender
    # debits above and in the withholding numerator below.
    # The owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once"; R3-B02): a returned payment the same
    # funder re-debited is out of the withholding numerator, its re-debit counting the obligation once.
    re_debited = [record for record in m.returned_funder_payment_evidence if getattr(record, "represented_by", None)]
    if re_debited:
        kept = m.returned_funder_payment_count - len(re_debited)
        L.append(
            f"  Returned funder payments: {m.returned_funder_payment_count} row(s), "
            f"${m.returned_funder_payment_total:,.2f} ({len(re_debited)} re-debited by the funder, "
            f"${sum(abs(record.amount) for record in re_debited):,.2f}, counted once; {kept} kept in withholding)"
        )
    else:
        L.append(
            f"  Returned funder payments: {m.returned_funder_payment_count} row(s), "
            f"${m.returned_funder_payment_total:,.2f} (kept in withholding)"
        )
    # Owner ruling 2026-10-02 (the underwriter's Q7; R2-OW14): the working lines name the basis, True revenue by default.
    L.append(
        f"  Withholding working   : ${m.withholding_numerator:,.2f} / "
        f"{basis(m.withholding_denominator)} {m.withholding_denominator_label}"
    )
    if basis_unestablished:
        potential_exposure = _NOT_ESTABLISHED
    else:
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
        f"{basis(m.potential_withholding_denominator)} {m.withholding_denominator_label}"
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
            # R2-OW13: the paid debits, then the payments returned unpaid (listed with the funder, never paid).
            returned = f", {fm.returned_count} returned unpaid" if fm.returned_count else ""
            L.append(f"    - {fm.funder}: {fm.debit_count} txns{returned}, "
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
            if basis_unestablished:
                # F1 (final review of round 2): no exposure over a basis that is not established.
                exposure = denominator = _NOT_ESTABLISHED
            L.append(
                f"    - {fm.funder}: {fm.debit_count} debit(s), "
                f"${fm.total_debited:,.2f}; {exposure} exposure / {denominator} deposits"
            )
    else:
        L.append("  Potential lenders: none")
    # The owner's request of 2026-10-10 (active positions by month): the statement's active positions over its printed
    # period, the confirmed lenders' and, apart, the potential lenders' (information only).
    L.append(f"  Active positions      : {_active_positions_text(report)}")
    # The owner's request of 2026-10-06 (R2-OW18): the statement's lender payment changes (information only). One
    # statement at a time, so never a change seen only across months.
    if d.lender_payment_changes:
        L.append("  Lender payment changes:")
        L.extend(f"    - {_payment_change_line(item)}" for item in d.lender_payment_changes)
    else:
        L.append("  Lender payment changes: none")
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

    # Spec §7: flagged obligations, analysis time only (no Settings are read).
    L.append("\n## Flagged positions (not lenders; outside lender math)")
    if d.flagged_positions:
        for fp in d.flagged_positions:
            group = FLAG_GROUP_BY_KEY.get(fp.group)
            label = group.label if group is not None else fp.group
            # Owner ruling 2026-09-26: a factor's payouts are credits the payee paid in.
            received = (
                f"; {fp.count_credited} credit(s) received, ${fp.total_credited:,.2f}"
                if fp.count_credited else ""
            )
            L.append(
                f"  - {label}: {fp.payee}: {fp.count} debit(s), "
                f"${fp.total_debited:,.2f}{received} ({fp.cadence})"
            )
    else:
        L.append("  Flagged positions: none")
    return "\n".join(L)


def _json_safe(document: DocumentReport, zelle_true_revenue: bool = True) -> dict:
    """The DOCUMENT's payload. RULE S: one account publishes today's, verbatim. R2-OW17: in the Zelle reading shown
    (analysis/zelle_view.py apply_zelle_view): under No, on a fresh analysis, today's JSON (the edits key gone, no
    display key). Audit round 2, R2-B16 (R52): then the revenue view the dashboard serves (analysis/revenue_view.py
    apply_revenue_view, after the Zelle reading as analysis/served_view.py `displayed` applies them), so each account's
    metrics carry `revenue_established` and `verified_revenue_established`; every figure is kept."""
    return apply_revenue_view(zelle_view.apply_zelle_view(document_report_to_dict(document),
                                                          counted=zelle_true_revenue))


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze an OCR'd bank statement.")
    ap.add_argument("markdown", help="Path to the OCR markdown file.")
    ap.add_argument("--json", metavar="FILE", help="Also write the full report as JSON.")
    ap.add_argument("--zelle-true-revenue", choices=("yes", "no"), default="yes",
                    help="Mark Zelle Payments as True Revenue (default yes, the Settings default)")
    args = ap.parse_args()
    zelle_true_revenue = args.zelle_true_revenue == "yes"

    # Audit 2026-10-13, EXP-5: this CLI reads a statement's markdown. A PDF, by its name or its first bytes, gets one
    # line naming the tools that read PDFs (it used to die with a UnicodeDecodeError traceback).
    with open(args.markdown, "rb") as f:
        lead = f.read(5)
    if args.markdown.lower().endswith(".pdf") or lead == b"%PDF-":
        print("error: analyze.py reads a statement's markdown; extract it with parse.py first, "
              "or run batch.py on the PDF", file=sys.stderr)
        sys.exit(2)
    # EXP-5: the report goes to stdout as UTF-8, as --json writes. A redirected stdout on Windows is cp1252, which
    # cannot encode the ligatures and private-use glyphs statement text carries. A stream without reconfigure is
    # written as it is.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

    with open(args.markdown, encoding="utf-8") as f:
        markdown = f.read()

    document = analyze_document(markdown)
    # One rendering per ACCOUNT, in printed order. Printing the first and
    # stopping would drop an account without saying so, which is the one thing
    # this whole model exists to stop.
    for account in document.accounts:
        print(_render(account, zelle_true_revenue))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(_json_safe(document, zelle_true_revenue), f, indent=2)
        print(f"\nWrote JSON report to {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()

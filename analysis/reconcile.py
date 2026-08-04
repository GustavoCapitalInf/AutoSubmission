"""Stage 2 — deterministic reconciliation. Verify the extracted ledger is
internally consistent BEFORE computing anything on it. A mismatch usually means
an OCR digit error or a dropped/duplicated row — catch it here instead of
computing a wrong average on top of it.

Two independent checks:
  1. Sum check:  beginning_balance + Σ(amounts) == ending_balance
  2. Running-balance continuity:  prev_balance + amount == this row's balance
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .schema import Statement

# Money is compared to the cent; allow a hair of float slop.
_TOL = 0.01


@dataclass
class ReconResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    # The backbone signal for small-bank/image statements: did the bank's OWN
    # stated summary reconcile? None when there aren't enough stated fields to tell.
    summary_ok: bool | None = None
    # Filled when the inputs are present, for reporting.
    computed_ending: float | None = None
    stated_beginning: float | None = None
    stated_ending: float | None = None
    sum_delta: float | None = None
    continuity_breaks: int = 0
    # Coverage: how much of the bank's stated totals the line items captured
    # (< 1.0 means OCR/extraction dropped detail — stated summary is still usable).
    credit_coverage: float | None = None
    debit_coverage: float | None = None
    coverage_adjusted_for_reversals: bool = False
    reversal_pair_count: int = 0
    gross_credit_total: float | None = None
    gross_debit_total: float | None = None
    settled_credit_detail: float | None = None
    settled_debit_detail: float | None = None


def _debit_coverage_target(
    stmt: Statement,
    beginning: float | None,
) -> float | None:
    target = stmt.stated_total_debits
    service_charge = stmt.stated_service_charge or 0.0
    if (
        target is None
        or not service_charge
        or beginning is None
        or stmt.ending_balance is None
        or stmt.stated_total_credits is None
    ):
        return target
    interest = stmt.stated_interest_paid or 0.0
    base = beginning + stmt.stated_total_credits - target + interest
    if (
        abs(round(base - service_charge - stmt.ending_balance, 2)) <= 1.00
        and abs(round(base - stmt.ending_balance, 2)) > 1.00
    ):
        return round(target + service_charge, 2)
    return target


def _coverage_mismatch(captured: float, target: float | None) -> bool:
    if not target:
        return False
    coverage = captured / target
    return coverage < 0.98 or coverage > 1.02


def reconcile(stmt: Statement) -> ReconResult:
    issues: list[str] = []
    summary_ok: bool | None = None

    total = sum(t.amount for t in stmt.transactions)
    computed_ending = stated_ending = sum_delta = None
    implied_beginning = None
    if (stmt.beginning_balance is None and stmt.ending_balance is not None
            and stmt.stated_total_credits is not None and stmt.stated_total_debits is not None):
        interest = stmt.stated_interest_paid or 0.0
        implied_beginning = round(
            stmt.ending_balance - stmt.stated_total_credits + stmt.stated_total_debits,
            2,
        )
    beginning_for_checks = stmt.beginning_balance if stmt.beginning_balance is not None else implied_beginning
    if beginning_for_checks is not None and stmt.ending_balance is not None:
        computed_ending = round(beginning_for_checks + total, 2)
        stated_ending = round(stmt.ending_balance, 2)
        sum_delta = round(computed_ending - stated_ending, 2)
        if abs(sum_delta) > _TOL:
            issues.append(
                f"sum check off by {sum_delta:+.2f}: beginning {beginning_for_checks:.2f} "
                f"+ transactions {total:+.2f} = {computed_ending:.2f}, "
                f"but stated ending is {stated_ending:.2f}"
            )
    else:
        issues.append("cannot run sum check: missing beginning or ending balance")

    # Running-balance continuity across rows that carry balances. Many banks print
    # balances only at the end of a same-day group, so accumulate all intervening
    # transaction amounts since the last printed balance.
    breaks = 0
    prev = beginning_for_checks
    pending = 0.0
    for i, t in enumerate(stmt.transactions):
        pending = round(pending + t.amount, 2)
        if t.running_balance is not None:
            if prev is not None:
                expected = round(prev + pending, 2)
                if abs(expected - round(t.running_balance, 2)) > _TOL:
                    breaks += 1
                    if breaks <= 5:  # cap the noise; count them all
                        issues.append(
                            f"row {i} ({t.date} {t.description[:30]!r}): balance jumped to "
                            f"{t.running_balance:.2f}, expected {expected:.2f} "
                            f"({prev:.2f} plus intervening transactions {pending:+.2f})"
                        )
            prev = t.running_balance
            pending = 0.0

    # Does the bank's OWN stated summary reconcile? This is the backbone check for
    # small-bank / image statements where line items are incomplete but the summary
    # is authoritative. Catches a scrambled extraction (credits/debits swapped, a
    # count read as an amount). The exact identity is:
    #     beginning + credits - debits - service_charge + interest == ending
    # but some banks fold the service charge into the debit total, so we accept the
    # summary if it reconciles either WITH or WITHOUT subtracting it.
    if (stmt.ending_balance is not None
            and stmt.stated_total_credits is not None and stmt.stated_total_debits is not None
            and beginning_for_checks is not None):
        sc = stmt.stated_service_charge or 0.0
        interest = stmt.stated_interest_paid or 0.0
        beginning = beginning_for_checks
        base = beginning + stmt.stated_total_credits - stmt.stated_total_debits
        base_with_interest = base + interest
        residuals = (
            round(base - sc - stmt.ending_balance, 2),            # service charge separate
            round(base - stmt.ending_balance, 2),                 # service charge folded into debits
            round(base_with_interest - sc - stmt.ending_balance, 2),
            round(base_with_interest - stmt.ending_balance, 2),
        )
        resid = min(residuals, key=abs)
        summary_ok = abs(resid) <= 1.00
        if not summary_ok:
            issues.append(
                f"bank-stated summary does not reconcile (off by {resid:+.2f}): "
                f"beginning {beginning:.2f} + credits {stmt.stated_total_credits:.2f} "
                f"- debits {stmt.stated_total_debits:.2f} != ending {stmt.ending_balance:.2f} "
                f"— the summary figures look mis-extracted; don't trust them either"
            )

    # Coverage vs the bank's own stated totals (informational, not pass/fail):
    # reveals when line-item detail is incomplete. The cause may be extraction loss
    # or an internally inconsistent source document, so do not diagnose OCR here.
    credits = round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2)
    debits = round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2)
    settled_credits = credits
    settled_debits = debits
    reversal_pair_count = 0
    coverage_adjusted = False
    debit_target = _debit_coverage_target(stmt, beginning_for_checks)
    needs_reversal_coverage = (
        _coverage_mismatch(credits, stmt.stated_total_credits)
        or _coverage_mismatch(debits, debit_target)
    )
    if stmt.transactions and needs_reversal_coverage:
        from .transaction_classifier import classify_statement_transactions

        classifications = classify_statement_transactions(stmt)
        reversal_credits = round(
            sum(
                record.amount
                for record in classifications
                if record.amount > 0 and record.settlement_reversal
            ),
            2,
        )
        reversed_debits = round(
            -sum(
                record.amount
                for record in classifications
                if record.amount < 0 and record.reversed_by is not None
            ),
            2,
        )
        reversal_pair_count = sum(
            1 for record in classifications if record.settlement_reversal
        )
        candidate_credits = round(credits - reversal_credits, 2)
        candidate_debits = round(debits - reversed_debits, 2)
        if (
            stmt.stated_total_credits
            and abs(candidate_credits - stmt.stated_total_credits)
            < abs(credits - stmt.stated_total_credits)
        ):
            settled_credits = candidate_credits
            coverage_adjusted = True

        if (
            debit_target
            and abs(candidate_debits - debit_target) < abs(debits - debit_target)
        ):
            settled_debits = candidate_debits
            coverage_adjusted = True

    credit_cov = debit_cov = None
    if stmt.stated_total_credits:
        credit_cov = round(settled_credits / stmt.stated_total_credits, 3)
        if credit_cov < 0.98 or credit_cov > 1.02:
            issues.append(
                f"captured ${settled_credits:,.2f} of the bank's stated ${stmt.stated_total_credits:,.2f} "
                f"in credits ({credit_cov:.0%}) - line-item detail is inconsistent "
                f"or incomplete; do not use it for daily-balance reconstruction"
            )
    if stmt.stated_total_debits:
        assert debit_target is not None
        debit_cov = round(settled_debits / debit_target, 3)
        if debit_cov < 0.98 or debit_cov > 1.02:
            issues.append(
                f"captured ${settled_debits:,.2f} of the bank's stated ${debit_target:,.2f} "
                f"in debits ({debit_cov:.0%}) - line-item detail is inconsistent "
                f"or incomplete; do not use it for daily-balance reconstruction"
            )

    ok = not issues
    return ReconResult(
        ok=ok, issues=issues, summary_ok=summary_ok,
        computed_ending=computed_ending,
        stated_beginning=(
            round(stmt.beginning_balance, 2)
            if stmt.beginning_balance is not None
            else None
        ),
        stated_ending=stated_ending,
        sum_delta=sum_delta, continuity_breaks=breaks,
        credit_coverage=credit_cov, debit_coverage=debit_cov,
        coverage_adjusted_for_reversals=coverage_adjusted,
        reversal_pair_count=reversal_pair_count,
        gross_credit_total=credits,
        gross_debit_total=debits,
        settled_credit_detail=settled_credits,
        settled_debit_detail=settled_debits,
    )

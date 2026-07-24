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
    # Filled when the inputs are present, for reporting.
    computed_ending: float | None = None
    stated_ending: float | None = None
    sum_delta: float | None = None
    continuity_breaks: int = 0
    # Coverage: how much of the bank's stated totals the line items captured
    # (< 1.0 means OCR/extraction dropped detail — stated summary is still usable).
    credit_coverage: float | None = None
    debit_coverage: float | None = None


def reconcile(stmt: Statement) -> ReconResult:
    issues: list[str] = []

    total = sum(t.amount for t in stmt.transactions)
    computed_ending = stated_ending = sum_delta = None
    if stmt.beginning_balance is not None and stmt.ending_balance is not None:
        computed_ending = round(stmt.beginning_balance + total, 2)
        stated_ending = round(stmt.ending_balance, 2)
        sum_delta = round(computed_ending - stated_ending, 2)
        if abs(sum_delta) > _TOL:
            issues.append(
                f"sum check off by {sum_delta:+.2f}: beginning {stmt.beginning_balance:.2f} "
                f"+ transactions {total:+.2f} = {computed_ending:.2f}, "
                f"but stated ending is {stated_ending:.2f}"
            )
    else:
        issues.append("cannot run sum check: missing beginning or ending balance")

    # Running-balance continuity across consecutive rows that both carry a balance.
    breaks = 0
    prev = None
    for i, t in enumerate(stmt.transactions):
        if t.running_balance is not None and prev is not None:
            expected = round(prev + t.amount, 2)
            if abs(expected - round(t.running_balance, 2)) > _TOL:
                breaks += 1
                if breaks <= 5:  # cap the noise; count them all
                    issues.append(
                        f"row {i} ({t.date} {t.description[:30]!r}): balance jumped to "
                        f"{t.running_balance:.2f}, expected {expected:.2f} "
                        f"({prev:.2f} {t.amount:+.2f})"
                    )
        if t.running_balance is not None:
            prev = t.running_balance

    # Does the bank's OWN stated summary reconcile? Catches a scrambled summary
    # extraction (credits/debits swapped, a count read as an amount) — otherwise
    # we'd "fall back" to figures that are themselves wrong. A small residual is
    # normal (a service charge listed outside the debit total).
    if (stmt.beginning_balance is not None and stmt.ending_balance is not None
            and stmt.stated_total_credits is not None and stmt.stated_total_debits is not None):
        resid = round(stmt.beginning_balance + stmt.stated_total_credits
                      - stmt.stated_total_debits - stmt.ending_balance, 2)
        if abs(resid) > max(50.0, 0.02 * abs(stmt.ending_balance)):
            issues.append(
                f"bank-stated summary does not reconcile (off by {resid:+.2f}): "
                f"beginning {stmt.beginning_balance:.2f} + stated credits "
                f"{stmt.stated_total_credits:.2f} - stated debits {stmt.stated_total_debits:.2f} "
                f"!= ending {stmt.ending_balance:.2f} — the summary figures look "
                f"mis-extracted; don't trust them either"
            )

    # Coverage vs the bank's own stated totals (informational, not pass/fail):
    # reveals when the line-item detail is incomplete because of bad OCR.
    credits = round(sum(t.amount for t in stmt.transactions if t.amount > 0), 2)
    debits = round(-sum(t.amount for t in stmt.transactions if t.amount < 0), 2)
    credit_cov = debit_cov = None
    if stmt.stated_total_credits:
        credit_cov = round(credits / stmt.stated_total_credits, 3)
    if stmt.stated_total_debits:
        debit_cov = round(debits / stmt.stated_total_debits, 3)
        # Only flag genuine UNDER-coverage. Over-coverage means the stated total is
        # too small (a mis-extracted summary), which the summary check above owns.
        if debit_cov < 0.98:
            issues.append(
                f"captured ${debits:,.2f} of the bank's stated ${stmt.stated_total_debits:,.2f} "
                f"in debits ({debit_cov:.0%}) — line-item detail is incomplete "
                f"(likely mangled OCR); rely on the bank's stated summary figures"
            )

    ok = not issues
    return ReconResult(
        ok=ok, issues=issues,
        computed_ending=computed_ending, stated_ending=stated_ending,
        sum_delta=sum_delta, continuity_breaks=breaks,
        credit_coverage=credit_cov, debit_coverage=debit_cov,
    )

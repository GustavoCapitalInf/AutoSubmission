"""Underwriting-grade Average Daily Balance.

ADB is the single figure a funder leans on hardest, so it is computed here in
one deterministic, auditable pass that behaves identically for every supported
bank. The definition implemented is the commercial-underwriting one:

    ADB = (sum of each calendar day's ending balance) / (calendar days in period)

Every calendar day in the statement period counts exactly once — weekends,
holidays, and days with no posting activity included. A day with no activity
inherits the previous day's ending balance. Negative balances are summed as
negative; they are never clamped or excluded. The divisor is always the
inclusive calendar-day count of the period, never the number of posting days.

Explicitly NOT what this computes:
  - the mean of per-transaction running balances
  - the mean over posting days only
  - anything that drops, weights, or clamps a day

Balance sourcing, per day, in priority order:
  1. `printed`       — the bank's own running balance on the last row that day
  2. `reconstructed` — previous day's ending balance plus that day's amounts
  3. `carried`       — no activity, so the previous day's ending balance stands

That ordering honours the printed record where it exists and reconstructs only
what the statement leaves out, which keeps the result reproducible from the
parsed statement while surviving banks that print balances sparsely (or not at
all). Every day records which rule produced it, so any figure can be traced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .dates import parse_date
from .schema import Statement

# Money is compared to the cent; allow a hair of float slop.
_TOL = 0.01
# Closing-balance drift we will report but still return a figure for.
_CLOSING_TOL = 1.00


@dataclass
class DailyBalance:
    """One calendar day's ending balance and how it was determined."""

    date: str
    ending_balance: float
    source: str  # printed | reconstructed | carried
    transaction_count: int = 0

    def __str__(self) -> str:
        return f"{self.date} {self.ending_balance:.2f}"


@dataclass
class AverageDailyBalanceResult:
    average_daily_balance: float | None = None
    daily_balance_sum: float | None = None
    calendar_day_count: int | None = None
    daily_balances: list[DailyBalance] = field(default_factory=list)

    period_start: str | None = None
    period_end: str | None = None
    opening_balance: float | None = None
    closing_balance: float | None = None
    # Where the opening balance came from: stated | derived_from_closing | first_printed_balance
    opening_balance_source: str | None = None
    # Closing balance implied by opening + all parsed transactions.
    computed_closing_balance: float | None = None
    total_credits: float = 0.0
    total_debits: float = 0.0

    ok: bool = False
    reconciled: bool | None = None
    validations: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def posting_days(self) -> int:
        return sum(1 for d in self.daily_balances if d.transaction_count)

    @property
    def negative_days(self) -> int:
        return sum(1 for d in self.daily_balances if d.ending_balance < 0)

    def debug_report(self) -> str:
        """Exactly how the ADB was calculated, line by line."""
        lines: list[str] = []
        lines.append("Average Daily Balance - calculation trace")
        lines.append("=" * 52)
        lines.append(f"Statement period : {self.period_start} through {self.period_end}")
        lines.append(f"Calendar days    : {self.calendar_day_count}")
        opening = "n/a" if self.opening_balance is None else f"{self.opening_balance:,.2f}"
        lines.append(f"Opening balance  : {opening} ({self.opening_balance_source or 'unavailable'})")
        closing = "n/a" if self.closing_balance is None else f"{self.closing_balance:,.2f}"
        lines.append(f"Closing balance  : {closing}")
        if self.computed_closing_balance is not None:
            lines.append(
                f"Opening {self.opening_balance or 0:,.2f} "
                f"+ credits {self.total_credits:,.2f} "
                f"- debits {self.total_debits:,.2f} "
                f"= {self.computed_closing_balance:,.2f}"
            )
        lines.append("")
        lines.append("Daily ending balances (every calendar day):")
        for entry in self.daily_balances:
            marker = {"printed": " ", "reconstructed": "*", "carried": "="}.get(entry.source, "?")
            txns = f"{entry.transaction_count} txn" if entry.transaction_count else "no activity"
            lines.append(f"  {marker} {entry.date}  {entry.ending_balance:>14,.2f}   {txns}")
        lines.append("")
        lines.append("  legend:   (blank) bank-printed balance   * reconstructed   = carried forward")
        lines.append("")
        if self.daily_balance_sum is not None and self.calendar_day_count:
            lines.append(f"Sum of daily balances : {self.daily_balance_sum:,.2f}")
            lines.append(f"Divided by days       : {self.calendar_day_count}")
            lines.append(f"Average Daily Balance : ${self.average_daily_balance:,.2f}")
        else:
            lines.append("Average Daily Balance : not computable")
        if self.validations:
            lines.append("")
            lines.append("Validations:")
            for name, passed in self.validations.items():
                lines.append(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
        return "\n".join(lines)


def _resolve_period(stmt: Statement, dated: list[tuple[date, object]]) -> tuple[date | None, date | None, list[str]]:
    """Statement period from the header, falling back to the transaction span."""
    warnings: list[str] = []
    start = parse_date(stmt.period_start)
    end = parse_date(stmt.period_end)
    if start is None and dated:
        start = min(d for d, _ in dated)
        warnings.append(
            "statement period start missing; using the earliest transaction date "
            f"({start.isoformat()}) - ADB divisor may not match the bank's period"
        )
    if end is None and dated:
        end = max(d for d, _ in dated)
        warnings.append(
            "statement period end missing; using the latest transaction date "
            f"({end.isoformat()}) - ADB divisor may not match the bank's period"
        )
    if start is not None and end is not None and start > end:
        warnings.append(
            f"statement period is inverted ({start.isoformat()} after {end.isoformat()}); "
            "swapping start and end"
        )
        start, end = end, start
    return start, end, warnings


def _resolve_opening(
    stmt: Statement,
    ordered: list[tuple[date, object]],
    total: float,
) -> tuple[float | None, str | None]:
    """The balance entering the period, before day one's activity posts."""
    if stmt.beginning_balance is not None:
        return round(stmt.beginning_balance, 2), "stated"
    if stmt.ending_balance is not None:
        # Closing minus everything that posted during the period.
        return round(stmt.ending_balance - total, 2), "derived_from_closing"
    # Last resort: work backwards from the first printed running balance.
    for index, (_, txn) in enumerate(ordered):
        if txn.running_balance is not None:
            prior = sum(t.amount for _, t in ordered[: index + 1])
            return round(txn.running_balance - prior, 2), "first_printed_balance"
    return None, None


def compute_average_daily_balance(stmt: Statement) -> AverageDailyBalanceResult:
    """Reconstruct a daily balance ledger for the statement period and average it.

    Returns a result even when validation fails, with `ok=False` and populated
    `warnings`, so callers can decide whether to surface the figure, flag it for
    review, or fall back to a bank-printed average.
    """
    result = AverageDailyBalanceResult()

    dated: list[tuple[date, object]] = []
    undated = 0
    for txn in stmt.transactions:
        parsed = parse_date(txn.date)
        if parsed is None:
            undated += 1
            continue
        dated.append((parsed, txn))

    if undated:
        result.warnings.append(
            f"{undated} transaction(s) have no parseable date and cannot be placed "
            "on a calendar day; ADB excludes them"
        )

    start, end, period_warnings = _resolve_period(stmt, dated)
    result.warnings.extend(period_warnings)
    result.period_start = start.isoformat() if start else None
    result.period_end = end.isoformat() if end else None

    if start is None or end is None:
        result.warnings.append(
            "cannot determine a statement period: no header period and no dated "
            "transactions; ADB not computable"
        )
        return result

    calendar_days = (end - start).days + 1
    result.calendar_day_count = calendar_days

    # Chronological order is what makes the reconstruction deterministic. Bank
    # parsers emit rows grouped by section (deposits, then checks, then
    # withdrawals), so list order is NOT date order. Ties inside a day keep the
    # statement's own order, which is what "last row of the day" means for the
    # printed-balance rule; the reconstructed rule sums the day and so is
    # order-independent either way.
    ordered = sorted(enumerate(dated), key=lambda pair: (pair[1][0], pair[0]))
    ordered = [entry for _, entry in ordered]

    total = round(sum(txn.amount for _, txn in ordered), 2)
    result.total_credits = round(sum(t.amount for _, t in ordered if t.amount > 0), 2)
    result.total_debits = round(-sum(t.amount for _, t in ordered if t.amount < 0), 2)

    opening, opening_source = _resolve_opening(stmt, ordered, total)
    result.opening_balance = opening
    result.opening_balance_source = opening_source
    result.closing_balance = round(stmt.ending_balance, 2) if stmt.ending_balance is not None else None

    if opening is None:
        result.warnings.append(
            "no opening balance and none derivable (statement lacks both beginning "
            "and ending balance, and no row prints a running balance); ADB not computable"
        )
        return result

    result.computed_closing_balance = round(opening + total, 2)

    # Transactions dated outside the period still belong to the ledger - the
    # closing balance reflects them - so clamp them onto the nearest in-period
    # day rather than dropping them, and say so.
    by_day: dict[date, list[object]] = {}
    clamped = 0
    for day, txn in ordered:
        if day < start:
            day = start
            clamped += 1
        elif day > end:
            day = end
            clamped += 1
        by_day.setdefault(day, []).append(txn)
    if clamped:
        result.warnings.append(
            f"{clamped} transaction(s) fall outside the statement period and were "
            "applied to the nearest in-period day to preserve the closing balance"
        )

    # Single forward walk across every calendar day.
    carry = opening
    daily: list[DailyBalance] = []
    day = start
    while day <= end:
        txns = by_day.get(day, [])
        printed = None
        for txn in txns:  # statement order within the day; last printed wins
            if txn.running_balance is not None:
                printed = round(txn.running_balance, 2)
        if printed is not None:
            carry = printed
            source = "printed"
        elif txns:
            carry = round(carry + sum(t.amount for t in txns), 2)
            source = "reconstructed"
        else:
            source = "carried"
        daily.append(
            DailyBalance(
                date=day.isoformat(),
                ending_balance=carry,
                source=source,
                transaction_count=len(txns),
            )
        )
        day += timedelta(days=1)

    result.daily_balances = daily
    result.daily_balance_sum = round(sum(d.ending_balance for d in daily), 2)
    result.average_daily_balance = round(result.daily_balance_sum / calendar_days, 2)

    _validate(result, stmt, start, end, calendar_days, opening, total)
    return result


def _validate(
    result: AverageDailyBalanceResult,
    stmt: Statement,
    start: date,
    end: date,
    calendar_days: int,
    opening: float,
    total: float,
) -> None:
    daily = result.daily_balances
    checks: dict[str, bool] = {}

    checks["daily_balance_count_equals_calendar_days"] = len(daily) == calendar_days
    if not checks["daily_balance_count_equals_calendar_days"]:
        result.warnings.append(
            f"reconstructed {len(daily)} daily balances for a {calendar_days}-day period"
        )

    # No gaps and no duplicates: consecutive days from start to end.
    expected = start
    contiguous = True
    for entry in daily:
        if entry.date != expected.isoformat():
            contiguous = False
            break
        expected += timedelta(days=1)
    checks["daily_balances_contiguous"] = contiguous and (not daily or expected - timedelta(days=1) == end)
    if not checks["daily_balances_contiguous"]:
        result.warnings.append("daily balance series has a gap or an out-of-order date")

    checks["covers_opening_day"] = bool(daily) and daily[0].date == start.isoformat()
    checks["covers_closing_day"] = bool(daily) and daily[-1].date == end.isoformat()

    # Last reconstructed balance must equal the statement's closing balance.
    if result.closing_balance is not None and daily:
        drift = round(daily[-1].ending_balance - result.closing_balance, 2)
        checks["final_balance_matches_statement_closing"] = abs(drift) <= _CLOSING_TOL
        if abs(drift) > _CLOSING_TOL:
            result.warnings.append(
                f"final reconstructed balance {daily[-1].ending_balance:,.2f} differs from the "
                f"statement closing balance {result.closing_balance:,.2f} by {drift:+,.2f}"
            )
    else:
        checks["final_balance_matches_statement_closing"] = False
        result.warnings.append(
            "statement prints no closing balance; cannot verify the reconstructed ledger ends correctly"
        )

    # opening + credits - debits == closing
    if result.closing_balance is not None:
        residual = round(opening + total - result.closing_balance, 2)
        result.reconciled = abs(residual) <= _TOL
        checks["ledger_reconciles_to_closing"] = result.reconciled
        if not result.reconciled:
            result.warnings.append(
                f"ledger does not reconcile (off by {residual:+,.2f}): opening {opening:,.2f} "
                f"+ credits {result.total_credits:,.2f} - debits {result.total_debits:,.2f} "
                f"= {result.computed_closing_balance:,.2f}, statement closing is "
                f"{result.closing_balance:,.2f}"
            )

    if stmt.beginning_balance is not None:
        checks["opening_balance_matches_statement"] = (
            abs(round(stmt.beginning_balance, 2) - opening) <= _TOL
        )
    else:
        checks["opening_balance_matches_statement"] = False
        result.warnings.append(
            f"statement prints no beginning balance; opening balance was {result.opening_balance_source}"
        )

    # Cross-check the bank's own printed average, when it prints one.
    if stmt.stated_average_balance is not None and result.average_daily_balance is not None:
        gap = abs(round(stmt.stated_average_balance - result.average_daily_balance, 2))
        tolerance = max(1.00, abs(stmt.stated_average_balance) * 0.01)
        checks["agrees_with_bank_stated_average"] = gap <= tolerance
        if gap > tolerance:
            result.warnings.append(
                f"computed ADB {result.average_daily_balance:,.2f} differs from the bank-printed "
                f"average {stmt.stated_average_balance:,.2f} by {gap:,.2f} - the bank may average "
                "collected rather than ledger balances, or detail may be missing"
            )

    # `ok` gates on the structural guarantees, the reconstructed ledger ending on
    # the printed closing balance, and the ledger identity reconciling.
    #
    # Deliberately NOT gated on:
    #   - agrees_with_bank_stated_average: banks commonly print average COLLECTED
    #     balance (which lags by float days) rather than average ledger balance,
    #     so a small gap is normal and is reported as a warning instead.
    #   - opening_balance_matches_statement: many statements omit a printed
    #     beginning balance, and deriving it from the closing balance is exact.
    result.validations = checks
    required = [
        "daily_balance_count_equals_calendar_days",
        "daily_balances_contiguous",
        "covers_opening_day",
        "covers_closing_day",
        "final_balance_matches_statement_closing",
    ]
    if "ledger_reconciles_to_closing" in checks:
        required.append("ledger_reconciles_to_closing")
    result.ok = all(checks.get(name, False) for name in required)

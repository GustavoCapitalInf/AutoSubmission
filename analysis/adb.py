"""Deterministic Average Daily Balance reconstruction.

The authoritative calculation is:

    ADB = sum(each calendar day's ending ledger balance) / calendar days

Every day in the inclusive statement period contributes exactly once. Missing
activity days carry the previous ending balance, and negative balances remain
negative. Transaction running balances are validation evidence only; they never
replace the ledger reconstructed from the opening balance and signed postings.

When a statement prints a dated daily book/ledger balance history, those explicit
end-of-day snapshots outrank transaction-date reconstruction. Missing dates
between snapshots still carry or reconstruct normally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .dates import parse_date, source_posting_dates
from .schema import Statement


_CENT = Decimal("0.01")


def _decimal(value: float | int | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value: float | int | str | Decimal) -> Decimal:
    """Round currency to cents using conventional financial half-up rounding."""
    return _decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass
class DailyBalance:
    """One calendar day's ending balance and how it was determined."""

    date: str
    ending_balance: float
    source: str  # bank_daily_summary | reconstructed | carried
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
    # stated | derived_from_closing | first_printed_balance
    opening_balance_source: str | None = None
    computed_closing_balance: float | None = None
    total_credits: float = 0.0
    total_debits: float = 0.0

    ok: bool = False
    reconciled: bool | None = None
    validations: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    parsed_posting_days: int | None = None
    source_posting_days: int | None = None
    missing_posting_dates: list[str] = field(default_factory=list)
    out_of_period_transaction_count: int = 0
    stated_daily_balance_count: int = 0

    @property
    def posting_days(self) -> int:
        return sum(1 for day in self.daily_balances if day.transaction_count)

    @property
    def negative_days(self) -> int:
        return sum(1 for day in self.daily_balances if day.ending_balance < 0)

    def debug_report(self) -> str:
        """Return the complete, human-readable ADB calculation trace."""
        lines: list[str] = [
            "Average Daily Balance - calculation trace",
            "=" * 52,
            f"Statement period : {self.period_start} through {self.period_end}",
            f"Calendar days    : {self.calendar_day_count}",
        ]
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

        lines.extend(["", "Daily ending balances (every calendar day):"])
        markers = {"bank_daily_summary": "B", "reconstructed": "*", "carried": "="}
        for entry in self.daily_balances:
            marker = markers.get(entry.source, "?")
            txns = f"{entry.transaction_count} txn" if entry.transaction_count else "no activity"
            lines.append(f"  {marker} {entry.date}  {entry.ending_balance:>14,.2f}   {txns}")
        lines.extend([
            "",
            "  legend: B bank daily summary   * reconstructed   = carried forward",
            "",
        ])
        if self.daily_balance_sum is not None and self.calendar_day_count:
            lines.extend([
                f"Sum of daily balances : {self.daily_balance_sum:,.2f}",
                f"Divided by days       : {self.calendar_day_count}",
                f"Average Daily Balance : ${self.average_daily_balance:,.2f}",
            ])
        else:
            lines.append("Average Daily Balance : not computable")
        if self.validations:
            lines.extend(["", "Validations:"])
            for name, passed in self.validations.items():
                lines.append(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if self.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"  - {warning}" for warning in self.warnings)
        return "\n".join(lines)


def _resolve_period(
    stmt: Statement, dated: list[tuple[date, Any]]
) -> tuple[date | None, date | None, list[str]]:
    """Resolve the period, retaining a transaction-span fallback for diagnostics."""
    warnings: list[str] = []
    start = parse_date(stmt.period_start)
    end = parse_date(stmt.period_end)
    if start is None and dated:
        start = min(day for day, _ in dated)
        warnings.append(
            "statement period start missing; using the earliest transaction date "
            f"({start.isoformat()}) - ADB divisor may not match the bank's period"
        )
    if end is None and dated:
        end = max(day for day, _ in dated)
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
    ordered: list[tuple[date, Any]],
    total: Decimal,
) -> tuple[Decimal | None, str | None]:
    """Resolve the balance entering day one, before that day's activity."""
    if stmt.beginning_balance is not None:
        return _money(stmt.beginning_balance), "stated"
    if stmt.ending_balance is not None:
        return _money(_decimal(stmt.ending_balance) - total), "derived_from_closing"
    for index, (_, txn) in enumerate(ordered):
        if txn.running_balance is not None:
            prior = sum(
                (_decimal(row.amount) for _, row in ordered[: index + 1]),
                Decimal("0"),
            )
            return _money(_decimal(txn.running_balance) - prior), "first_printed_balance"
    return None, None


def compute_average_daily_balance(
    stmt: Statement, *, source_markdown: str | None = None
) -> AverageDailyBalanceResult:
    """Build one inclusive end-of-day ledger and compute its arithmetic mean."""
    result = AverageDailyBalanceResult()

    dated: list[tuple[date, Any]] = []
    undated = 0
    for txn in stmt.transactions:
        parsed = parse_date(txn.date)
        if parsed is None:
            undated += 1
        else:
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

    indexed = sorted(enumerate(dated), key=lambda item: (item[1][0], item[0]))
    all_ordered = [entry for _, entry in indexed]
    ordered = [(day, txn) for day, txn in all_ordered if start <= day <= end]
    outside = [(day, txn) for day, txn in all_ordered if not start <= day <= end]
    result.out_of_period_transaction_count = len(outside)
    if outside:
        shown = ", ".join(day.isoformat() for day, _ in outside[:6])
        more = f" (+{len(outside) - 6} more)" if len(outside) > 6 else ""
        result.warnings.append(
            f"{len(outside)} transaction(s) fall outside the statement period "
            f"({shown}{more}); they were excluded rather than moved to a boundary day"
        )

    total = sum((_decimal(txn.amount) for _, txn in ordered), Decimal("0"))
    credits = sum(
        (_decimal(txn.amount) for _, txn in ordered if txn.amount > 0),
        Decimal("0"),
    )
    debits = -sum(
        (_decimal(txn.amount) for _, txn in ordered if txn.amount < 0),
        Decimal("0"),
    )
    result.total_credits = float(_money(credits))
    result.total_debits = float(_money(debits))

    opening, opening_source = _resolve_opening(stmt, ordered, total)
    result.opening_balance = float(opening) if opening is not None else None
    result.opening_balance_source = opening_source
    result.closing_balance = (
        float(_money(stmt.ending_balance)) if stmt.ending_balance is not None else None
    )
    if opening is None:
        result.warnings.append(
            "no opening balance and none derivable (statement lacks both beginning "
            "and ending balance, and no row prints a running balance); ADB not computable"
        )
        return result
    result.computed_closing_balance = float(_money(opening + total))

    by_day: dict[date, list[Any]] = {}
    for day, txn in ordered:
        by_day.setdefault(day, []).append(txn)

    snapshot_map: dict[date, Decimal] = {}
    snapshot_dates_valid = True
    for snapshot in stmt.stated_daily_balances:
        snapshot_day = parse_date(snapshot.date)
        if snapshot_day is None or not start <= snapshot_day <= end:
            snapshot_dates_valid = False
            result.warnings.append(
                f"bank daily balance has invalid or out-of-period date {snapshot.date!r}"
            )
            continue
        if snapshot_day in snapshot_map:
            snapshot_dates_valid = False
            result.warnings.append(
                f"bank daily balance history contains duplicate date {snapshot_day.isoformat()}"
            )
        snapshot_map[snapshot_day] = _money(snapshot.balance)
    result.stated_daily_balance_count = len(snapshot_map)

    carry = opening
    daily: list[DailyBalance] = []
    day = start
    while day <= end:
        txns = by_day.get(day, [])
        if txns:
            carry = _money(
                carry
                + sum((_decimal(txn.amount) for txn in txns), Decimal("0"))
            )
            source = "reconstructed"
        else:
            source = "carried"
        if day in snapshot_map:
            carry = snapshot_map[day]
            source = "bank_daily_summary"
        daily.append(
            DailyBalance(
                date=day.isoformat(),
                ending_balance=float(carry),
                source=source,
                transaction_count=len(txns),
            )
        )
        day += timedelta(days=1)

    result.daily_balances = daily
    daily_sum = sum((_decimal(entry.ending_balance) for entry in daily), Decimal("0"))
    result.daily_balance_sum = float(_money(daily_sum))
    result.average_daily_balance = float(
        _money(daily_sum / Decimal(calendar_days))
    )

    _validate(
        result,
        stmt,
        start,
        end,
        calendar_days,
        opening,
        total,
        ordered,
        undated=undated,
        snapshot_dates_valid=snapshot_dates_valid,
        source_markdown=source_markdown,
    )
    return result


def _validate(
    result: AverageDailyBalanceResult,
    stmt: Statement,
    start: date,
    end: date,
    calendar_days: int,
    opening: Decimal,
    total: Decimal,
    ordered: list[tuple[date, Any]],
    *,
    undated: int,
    snapshot_dates_valid: bool,
    source_markdown: str | None = None,
) -> None:
    daily = result.daily_balances
    checks: dict[str, bool] = {}

    stated_start = parse_date(stmt.period_start)
    stated_end = parse_date(stmt.period_end)
    checks["statement_period_dates_valid"] = (
        stated_start is not None
        and stated_end is not None
        and stated_start <= stated_end
        and stated_start == start
        and stated_end == end
    )
    if not checks["statement_period_dates_valid"]:
        result.warnings.append(
            "statement does not provide a valid, ordered start and end date; "
            "a transaction-span fallback cannot support a reportable ADB"
        )

    checks["all_transactions_dated"] = undated == 0
    checks["transactions_within_period"] = result.out_of_period_transaction_count == 0
    checks["bank_daily_balance_dates_valid"] = snapshot_dates_valid
    checks["daily_balance_count_equals_calendar_days"] = len(daily) == calendar_days
    if not checks["daily_balance_count_equals_calendar_days"]:
        result.warnings.append(
            f"reconstructed {len(daily)} daily balances for a {calendar_days}-day period"
        )

    expected = start
    contiguous = True
    for entry in daily:
        if entry.date != expected.isoformat():
            contiguous = False
            break
        expected += timedelta(days=1)
    checks["daily_balances_contiguous"] = contiguous and (
        not daily or expected - timedelta(days=1) == end
    )
    if not checks["daily_balances_contiguous"]:
        result.warnings.append("daily balance series has a gap or an out-of-order date")

    checks["covers_opening_day"] = bool(daily) and daily[0].date == start.isoformat()
    checks["covers_closing_day"] = bool(daily) and daily[-1].date == end.isoformat()

    if result.closing_balance is not None and daily:
        drift = _money(
            _decimal(daily[-1].ending_balance) - _decimal(result.closing_balance)
        )
        checks["final_balance_matches_statement_closing"] = drift == Decimal("0.00")
        if drift:
            result.warnings.append(
                f"final reconstructed balance {daily[-1].ending_balance:,.2f} differs from the "
                f"statement closing balance {result.closing_balance:,.2f} by {float(drift):+,.2f}"
            )
    else:
        checks["final_balance_matches_statement_closing"] = False
        result.warnings.append(
            "statement prints no closing balance; cannot verify the reconstructed ledger ends correctly"
        )

    if result.closing_balance is not None:
        residual = _money(opening + total - _decimal(result.closing_balance))
        result.reconciled = residual == Decimal("0.00")
        checks["ledger_reconciles_to_closing"] = result.reconciled
        if not result.reconciled:
            result.warnings.append(
                f"ledger does not reconcile (off by {float(residual):+,.2f}): "
                f"opening {float(opening):,.2f} + credits {result.total_credits:,.2f} "
                f"- debits {result.total_debits:,.2f} = "
                f"{result.computed_closing_balance:,.2f}, statement closing is "
                f"{result.closing_balance:,.2f}"
            )

    if stmt.beginning_balance is not None:
        checks["opening_balance_matches_statement"] = (
            _money(stmt.beginning_balance) == opening
        )
    else:
        checks["opening_balance_matches_statement"] = False
        result.warnings.append(
            f"statement prints no beginning balance; opening balance was {result.opening_balance_source}"
        )

    daily_map = {entry.date: _money(entry.ending_balance) for entry in daily}
    printed_by_day: dict[date, list[Decimal]] = {}
    for day, txn in ordered:
        if txn.running_balance is not None:
            printed_by_day.setdefault(day, []).append(_money(txn.running_balance))
    if printed_by_day:
        mismatches = [
            day
            for day, balances in printed_by_day.items()
            if daily_map.get(day.isoformat()) != balances[-1]
        ]
        checks["running_balances_support_daily_ledger"] = not mismatches
        if mismatches:
            shown = ", ".join(day.isoformat() for day in mismatches[:6])
            more = f" (+{len(mismatches) - 6} more)" if len(mismatches) > 6 else ""
            result.warnings.append(
                "transaction running balances do not support the reconstructed "
                f"end-of-day balance on {shown}{more}"
            )

    if source_markdown:
        source_dates = set(source_posting_dates(source_markdown, start, end))
        parsed_dates = {
            parsed
            for parsed in (parse_date(txn.date) for txn in stmt.transactions)
            if parsed is not None and start <= parsed <= end
        }
        result.parsed_posting_days = len(parsed_dates)
        result.source_posting_days = len(source_dates)
        missing = sorted(source_dates - parsed_dates)
        result.missing_posting_dates = [day.isoformat() for day in missing]
        checks["posting_dates_cover_source"] = not missing
        if missing:
            shown = ", ".join(day.isoformat() for day in missing[:6])
            more = f" (+{len(missing) - 6} more)" if len(missing) > 6 else ""
            result.warnings.append(
                f"parser produced {len(parsed_dates)} posting date(s) but the statement "
                f"prints {len(source_dates)}: no transaction was dated {shown}{more}. "
                "Posting dates have been folded together, so end-of-day balances are "
                "attributed to the wrong days and the ADB is not trustworthy"
            )

    required = [
        "statement_period_dates_valid",
        "all_transactions_dated",
        "transactions_within_period",
        "bank_daily_balance_dates_valid",
        "daily_balance_count_equals_calendar_days",
        "daily_balances_contiguous",
        "covers_opening_day",
        "covers_closing_day",
        "final_balance_matches_statement_closing",
    ]
    if "ledger_reconciles_to_closing" in checks:
        required.append("ledger_reconciles_to_closing")
    if "running_balances_support_daily_ledger" in checks:
        required.append("running_balances_support_daily_ledger")
    if "posting_dates_cover_source" in checks:
        required.append("posting_dates_cover_source")
    result.ok = all(checks.get(name, False) for name in required)

    if (
        result.ok
        and stmt.stated_average_balance is not None
        and result.average_daily_balance is not None
    ):
        gap = abs(
            _money(stmt.stated_average_balance)
            - _money(result.average_daily_balance)
        )
        checks["agrees_with_bank_stated_average"] = gap == Decimal("0.00")
        if gap:
            result.warnings.append(
                f"computed ADB {result.average_daily_balance:,.2f} differs from the bank-printed "
                f"average {stmt.stated_average_balance:,.2f} by {float(gap):,.2f}; the printed "
                "figure may use collected/available balances or another disclosed basis"
            )

    result.validations = checks

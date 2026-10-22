"""Deterministic Average Daily Balance reconstruction.

The authoritative calculation — the CANONICAL UNDERWRITING ADB — is:

    ADB = sum(each calendar day's ending ledger balance) / calendar days
          of the printed statement period

Every day in the inclusive statement period contributes exactly once. Missing
activity days carry the previous ending balance, and negative balances remain
negative. Transaction running balances are validation evidence only; they never
replace the ledger reconstructed from the opening balance and signed postings.

When a statement prints a dated daily book/ledger balance history, those explicit
end-of-day snapshots outrank transaction-date reconstruction. Missing dates
between snapshots still carry or reconstruct normally. Whether each snapshot
agreed with the balance the rows reach that day is RECORDED (the advisory
validation `bank_daily_balances_agree_with_rows`, audit 2026-10-13 REC-1) and
decides nothing: the snapshot is used either way.

THE DOCTRINE THIS MODULE IMPLEMENTS (ratified 2026-08-15)
---------------------------------------------------------
One statement or package yields exactly ONE user-facing "Average Daily
Balance", and it is always the figure above: uniform across every bank,
country, parser family, weekend and holiday. A bank's own printed average is
EVIDENCE to preserve, never a definition to adopt, and no bank's proprietary
convention may redefine it. `underwriting_adb_basis` and
`underwriting_adb_policy` are frozen literals stamped on every result rather
than knobs, so no code path can substitute another basis without the corpus
gate going red.

`underwriting_adb_alternates` computes the same ledger under five other
denominator conventions. They exist for audit, diagnostics and provenance
only: nothing selects between them, no dashboard renders them, and an
unvalidated ledger yields no valid figure on ANY basis. They are the evidence
that would be needed before a funder-policy profile could ever be argued for,
not a policy profile.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .dates import parse_date, source_posting_dates
from .schema import Statement


_CENT = Decimal("0.01")

#: The one basis every published Average Daily Balance is computed on. Frozen:
#: the corpus gate asserts this exact string on all 109 pinned documents.
UNDERWRITING_ADB_BASIS = "calendar_day_printed_period"

#: The revision of the canonical rule the basis belongs to. A future rule
#: change is a new policy name plus a ceremony, never a silent redefinition.
UNDERWRITING_ADB_POLICY = "canonical_v1"

#: Internal-only alternate denominators, in the order they are reported.
UNDERWRITING_ADB_ALTERNATE_BASES = (
    "banking_day",
    "weekday_only",
    "posting_day",
    "credit_only",
    "beginning_of_day",
)

#: The validations that are RECORDED and decide nothing: never in the
#: `required` list of `compute_average_daily_balance`, so `ok` (and the
#: published ADB) is the same whatever they say. The bank's printed average is
#: evidence, never a definition (the doctrine above); a bank-printed daily
#: balance that disagrees with the rows is used anyway (REC-1 step 1). Readers
#: that print the validations name these as advisory (the statement CSV/XLSX,
#: `webapp/statement_export.py::_adb_rows`; the audit's final review, finding 3), so a
#: False here is not read as a failed required check. telemetry's
#: `ADVISORY_CODES` lists the same names (pinned by a test).
ADVISORY_VALIDATIONS = frozenset({
    "agrees_with_bank_stated_average",
    "bank_daily_balances_agree_with_rows",
})


def _decimal(value: float | int | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def money_to_cents(value: float | int | str | Decimal) -> Decimal:
    """Round currency to cents using conventional financial half-up rounding.

    Public because `analysis/metrics.py` computes the bank-reported-average
    variance to the cent and must round it the same way this module rounds
    the ADB. One implementation of a financial decision, reached by its name
    rather than by importing a private helper across modules.
    """
    return _decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)


#: This module's own short name for it; every call site below uses this.
_money = money_to_cents


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    """The nth (1-based) `weekday` of a month; nth=-1 means the last one."""
    if nth > 0:
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + timedelta(days=offset + 7 * (nth - 1))
    following = date(year + (month == 12), (month % 12) + 1, 1)
    last = following - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _federal_bank_holidays(year: int) -> set[date]:
    """US federal holidays as BANK closures, observed.

    The calendar assumption is stated explicitly because it is the only place
    an alternate basis could smuggle in an undisclosed convention: this is the
    Federal Reserve Bank holiday schedule, not the OPM federal-employee one.
    The eleven statutory holidays, with the Reserve Banks' observance rule —
    a holiday falling on a SUNDAY closes the following Monday; a holiday
    falling on a SATURDAY closes nothing, because the Reserve Banks stay open
    the preceding Friday.

    ONE STATED LIMITATION. Juneteenth National Independence Day became a
    federal holiday in June 2021, and this calendar counts it in every year
    rather than carrying an effective-date constant. For a statement period
    that both predates the enactment AND contains June 19, the `banking_day`
    alternate would divide by one day too few. That is bounded and it is
    internal: the alternates are diagnostics, never published, and the
    canonical calendar-day ADB does not consult this calendar at all. It is
    written this way on purpose — a literal year in the parser layer is
    exactly what `tests/test_no_statement_hardcodes.py` exists to refuse, and
    an honest limitation in a diagnostic is a better trade than an exemption
    carved into that guard.
    """
    fixed = [
        date(year, 1, 1),    # New Year's Day
        date(year, 6, 19),   # Juneteenth National Independence Day
        date(year, 7, 4),    # Independence Day
        date(year, 11, 11),  # Veterans Day
        date(year, 12, 25),  # Christmas Day
    ]
    holidays = {
        _nth_weekday(year, 1, 0, 3),    # Birthday of Martin Luther King, Jr.
        _nth_weekday(year, 2, 0, 3),    # Washington's Birthday
        _nth_weekday(year, 5, 0, -1),   # Memorial Day
        _nth_weekday(year, 9, 0, 1),    # Labor Day
        _nth_weekday(year, 10, 0, 2),   # Columbus Day
        _nth_weekday(year, 11, 3, 4),   # Thanksgiving Day
    }
    for day in fixed:
        if day.weekday() == 6:
            holidays.add(day + timedelta(days=1))
        elif day.weekday() != 5:
            holidays.add(day)
    return holidays


# The owner's request of 2026-10-06 (lender payment changes; R2-OW18): the two calendar helpers published under public
# names, the same function objects, for analysis.lender_payment_changes' business days (no ADB reading moves).
federal_bank_holidays = _federal_bank_holidays
nth_weekday = _nth_weekday


def _is_banking_day(day: date, holidays: dict[int, set[date]]) -> bool:
    calendar = holidays.setdefault(day.year, _federal_bank_holidays(day.year))
    return day.weekday() < 5 and day not in calendar


def _mean_cents(values: list[Decimal]) -> float | None:
    if not values:
        return None
    return float(_money(sum(values, Decimal("0")) / Decimal(len(values))))


def _alternate_bases(
    daily: list[DailyBalance], opening: Decimal
) -> dict[str, float | None]:
    """The same validated ledger under five other denominator conventions.

    INTERNAL ONLY. One pass over the daily series the canonical ADB already
    built, so nothing here can disagree with it about what a day's balance is —
    they differ only in which days are counted, or in what a "balance" is taken
    to mean. Every basis whose day set is empty reports None rather than a
    number computed over nothing.

      banking_day       Monday-Friday excluding observed federal bank
                        holidays. MoneyThumb's observable construction; a
                        benchmark, never ground truth.
      weekday_only      Monday-Friday, holidays counted. The difference from
                        `banking_day` is exactly the holiday question.
      posting_day       Only days that carry at least one posting. What a
                        bank that averages "activity days" reports.
      credit_only       Every calendar day, each overdrawn day floored at
                        zero. Banks printing an "average credit balance" or
                        "average positive balance" answer this question.
      beginning_of_day  Every calendar day, valued at the balance ENTERING
                        the day: the opening balance on day one and the prior
                        day's close after that.
    """
    holidays: dict[int, set[date]] = {}
    banking: list[Decimal] = []
    weekday: list[Decimal] = []
    posting: list[Decimal] = []
    credit: list[Decimal] = []
    beginning: list[Decimal] = []
    carry = opening
    for entry in daily:
        day = date.fromisoformat(entry.date)
        balance = _decimal(entry.ending_balance)
        if _is_banking_day(day, holidays):
            banking.append(balance)
        if day.weekday() < 5:
            weekday.append(balance)
        if entry.transaction_count:
            posting.append(balance)
        credit.append(balance if balance > 0 else Decimal("0"))
        beginning.append(carry)
        carry = balance
    return {
        "banking_day": _mean_cents(banking),
        "weekday_only": _mean_cents(weekday),
        "posting_day": _mean_cents(posting),
        "credit_only": _mean_cents(credit),
        "beginning_of_day": _mean_cents(beginning),
    }


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
    #: The canonical underwriting ADB. `average_daily_balance` below is the
    #: deprecated alias for this exact value and nothing else.
    underwriting_adb: float | None = None
    daily_balance_sum: float | None = None
    calendar_day_count: int | None = None
    daily_balances: list[DailyBalance] = field(default_factory=list)

    period_start: str | None = None
    period_end: str | None = None
    opening_balance: float | None = None
    closing_balance: float | None = None
    # stated | derived_from_closing | first_printed_balance | initialization_event
    # | pre_period_carry_in
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

    # ------------------------------------------------------------------
    # The doctrine stamps. Defaults rather than assignments on purpose: a
    # result object cannot exist without declaring the basis it was computed
    # on, so no early return and no future branch can publish a figure whose
    # basis is unknown. Neither is a knob - `UNDERWRITING_ADB_BASIS` is the
    # only value the corpus gate accepts on any of the 109 pinned documents.
    # ------------------------------------------------------------------
    underwriting_adb_basis: str = UNDERWRITING_ADB_BASIS
    underwriting_adb_policy: str = UNDERWRITING_ADB_POLICY
    #: Internal-only: the same ledger under the alternate denominators named
    #: in `UNDERWRITING_ADB_ALTERNATE_BASES`. Diagnostics and provenance, never
    #: a published metric and never a selectable policy. Empty until the daily
    #: ledger exists; nulled alongside the canonical value at publication when
    #: the required checks fail, because an unvalidated ledger yields no valid
    #: figure on any basis.
    underwriting_adb_alternates: dict[str, float | None] = field(default_factory=dict)

    @property
    def average_daily_balance(self) -> float | None:
        """DEPRECATED alias for `underwriting_adb`; identical value.

        Retained so no consumer of the pre-doctrine name breaks. It is a
        property rather than a second field on purpose: `dataclasses.asdict`
        does not see properties, so the nested ADB object cannot start
        carrying a second ADB number into the payload behind
        `analysis/serialization.py`'s single-public-value rule.
        """
        return self.underwriting_adb

    @average_daily_balance.setter
    def average_daily_balance(self, value: float | None) -> None:
        self.underwriting_adb = value

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

    # ACCOUNT-OPENING INITIALIZATION EVENT - narrow, declared, fail-closed.
    #
    # An account opened mid-cycle can have its funding deposit posted the day
    # before the period the statement prints, counted in the bank's own printed
    # totals and printed in the bank's own daily balance history, while the
    # printed period still begins the next day. That posting is not period
    # activity: it is what day one opens WITH. It is folded into the opening
    # balance, so it never becomes a period day, the ADB divisor stays the
    # printed period's calendar length, and no row is moved to a boundary day.
    #
    # This is NOT a general tolerance for out-of-period transactions. It is
    # reachable only when the parser has DECLARED, from the document's own
    # printed evidence, exactly how many leading postings opened the account
    # (`Statement.initialization_transaction_count`), and only when every
    # condition below also holds of the ledger itself. Any row after the
    # period, any pre-period row beyond the declared count, a non-zero stated
    # opening balance, or a ledger that closes either without the event or not
    # at all with it, leaves `out_of_period_transaction_count` intact and the
    # document withheld.
    initialization: list[tuple[date, Any]] = []
    declared = stmt.initialization_transaction_count
    # The boundary is re-enforced HERE, not inherited from the declaring
    # parser: `day == start - 1`, not `day < start`. A consuming layer that
    # trusts its caller to have checked is a consuming layer with no check.
    if (
        declared
        and len(outside) == declared
        and all(day == start - timedelta(days=1) for day, _ in outside)
    ):
        seeded = sum((_decimal(txn.amount) for _, txn in outside), Decimal("0"))
        in_period = sum((_decimal(txn.amount) for _, txn in ordered), Decimal("0"))
        if (
            stmt.beginning_balance is not None
            and _money(stmt.beginning_balance) == Decimal("0.00")
            and stmt.ending_balance is not None
            # An account is opened by money ARRIVING. Without this a debit
            # dated the day before a zero-forward statement folds a NEGATIVE
            # opening balance in and publishes it as an account opening.
            #
            # BOTH halves, and the direction half is not redundant. The sign of
            # `amount` and the column the bank printed the row in are two
            # different statements, and a row can carry one without the other:
            # a `+1000.00` posting labelled `direction="debit"` satisfies the
            # amount test and is still a row the producer described as money
            # LEAVING. This layer does not get to assume the declaring parser
            # checked - that is the whole reason it re-checks the boundary too
            # - so it holds the invariant its own comment states.
            and seeded > Decimal("0")
            and all(
                txn.direction == "credit" and txn.amount > 0
                for _, txn in outside
            )
            # The event is REQUIRED: the whole printed ledger closes on the
            # printed closing balance with it, and does not close without it.
            and _money(seeded + in_period) == _money(stmt.ending_balance)
            and _money(in_period) != _money(stmt.ending_balance)
        ):
            initialization = outside
            outside = []
            result.out_of_period_transaction_count = 0
            result.warnings.append(
                f"{len(initialization)} account-opening posting(s) dated before the "
                f"statement period ("
                + ", ".join(day.isoformat() for day, _ in initialization)
                + ") were folded into the opening balance as initialization "
                "context; the ADB basis remains the printed period"
            )

    # PREVIOUS-BALANCE-DAY CARRY-IN - narrow, declared, fail-closed (owner
    # report 2026-10-08).
    #
    # A bank can open a statement's detail with postings dated the day its
    # previous-balance line names - the day before the printed period, after
    # the previous statement closed - and count them in THIS cycle: in its
    # printed totals, and in the printed resulting balance it chains through
    # them. They are what day one opens WITH, so they are folded into the
    # opening balance exactly as the initialization event above is: their day
    # never becomes a ledger day (so never an NSF day), the divisor stays the
    # printed period's calendar length, and no row is moved to a boundary day.
    #
    # Reachable only when the parser has DECLARED, from the document's printed
    # evidence, how many leading postings these are
    # (`Statement.pre_period_carry_in_count`), and only when this layer proves
    # of the ledger itself that: the declared count is every out-of-period row;
    # each is dated the day immediately before the period; they are the
    # statement's leading rows, in its order; each one's printed running
    # balance is the printed previous balance walked through them; and the
    # whole ledger closes on the printed closing balance with them and not
    # without them. Anything else - a row after the period, a row two days
    # early, one not at the head of the ledger, a broken chain - leaves
    # `out_of_period_transaction_count` intact and the document withheld.
    carry_in: list[tuple[date, Any]] = []
    declared_carry_in = stmt.pre_period_carry_in_count
    if (
        declared_carry_in
        and not initialization
        and len(outside) == declared_carry_in
        and all(day == start - timedelta(days=1) for day, _ in outside)
        and len(stmt.transactions) >= declared_carry_in
        and all(
            txn is leading
            for (_, txn), leading in zip(outside, stmt.transactions[:declared_carry_in])
        )
        and stmt.beginning_balance is not None
        and stmt.ending_balance is not None
    ):
        printed_opening = _money(stmt.beginning_balance)
        walked = printed_opening
        chained = True
        for _, txn in outside:
            walked = _money(walked + _decimal(txn.amount))
            if txn.running_balance is None or _money(txn.running_balance) != walked:
                chained = False
                break
        in_period = sum((_decimal(txn.amount) for _, txn in ordered), Decimal("0"))
        closing = _money(stmt.ending_balance)
        if (
            chained
            # REQUIRED: the ledger closes with them, and does not without them.
            and _money(walked + in_period) == closing
            and _money(printed_opening + in_period) != closing
        ):
            carry_in = outside
            outside = []
            result.out_of_period_transaction_count = 0
            result.warnings.append(
                f"{len(carry_in)} carry-in posting(s) dated on the previous-balance day ("
                + ", ".join(day.isoformat() for day, _ in carry_in)
                + "), before the statement period and counted in its printed cycle, were "
                "folded into the opening balance; the ADB basis remains the printed period"
            )

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
    seeded_total = sum(
        (_decimal(txn.amount) for _, txn in initialization + carry_in), Decimal("0")
    )
    if initialization and opening is not None:
        opening = _money(opening + seeded_total)
        opening_source = "initialization_event"
    elif carry_in and opening is not None:
        opening = _money(opening + seeded_total)
        opening_source = "pre_period_carry_in"
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
    # The days whose printed balance is not the carry the rows reach that day,
    # recorded BEFORE the printed figure replaces it (audit 2026-10-13 REC-1,
    # step 1). Day over day, from the same carry the override uses, so a seeded
    # opening and an earlier override are where the comparison starts. Advisory
    # only: the override itself is unchanged, see `_validate`.
    snapshot_disagreements: list[date] = []
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
            if carry != snapshot_map[day]:
                snapshot_disagreements.append(day)
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
    result.underwriting_adb = float(
        _money(daily_sum / Decimal(calendar_days))
    )
    # One pass over the ledger just built. Computed always so the audit trail
    # is complete even on documents nobody will ever ask about; published
    # never, and nulled with the canonical value when validation fails.
    result.underwriting_adb_alternates = _alternate_bases(daily, opening)

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
        seeded_total=seeded_total,
        snapshot_days=len(snapshot_map),
        snapshot_disagreements=snapshot_disagreements,
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
    seeded_total: Decimal = Decimal("0"),
    snapshot_days: int = 0,
    snapshot_disagreements: list[date] | None = None,
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
        # `opening` carries any initialization event or previous-balance-day
        # carry-in; the printed figure is the balance BEFORE it, so the
        # comparison subtracts what was folded in.
        checks["opening_balance_matches_statement"] = (
            _money(stmt.beginning_balance) == _money(opening - seeded_total)
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
        # H1. The day the period opens with is the seed of every later day, so
        # a ledger whose opening is inferred rather than printed cannot support
        # a reportable ADB no matter how well the rest of it reconciles. This
        # was measured before it was promoted: the opening is bank-stated on
        # every document in the archive that publishes an ADB, so promoting it
        # moved nothing - the check simply stopped being able to fail silently.
        "opening_balance_matches_statement",
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
        and stmt.bank_reported_average_balance is not None
        and result.underwriting_adb is not None
    ):
        gap = abs(
            _money(stmt.bank_reported_average_balance)
            - _money(result.underwriting_adb)
        )
        checks["agrees_with_bank_stated_average"] = gap == Decimal("0.00")
        if gap:
            result.warnings.append(
                f"computed ADB {result.underwriting_adb:,.2f} differs from the bank-printed "
                f"average {stmt.bank_reported_average_balance:,.2f} by {float(gap):,.2f}; the printed "
                "figure may use collected/available balances or another disclosed basis"
            )

    # Audit 2026-10-13 REC-1, step 1: ADVISORY, and deliberately NOT in
    # `required`. A bank-printed daily balance overrides the carry for its day
    # (the bank's table outranks reconstruction, by design), and until now
    # nothing recorded whether the two agreed: `running_balances_support_daily_ledger`
    # reads the ledger after the override, so a wrong printed cell on a day
    # with no posting, healed by a later cell, passed every check. This
    # records the disagreement and changes nothing it touches: `ok`, the
    # override, the ADB and the NSF days are what they were. Present only when
    # the statement publishes an in-period daily balance. Making it required
    # is an owner ruling (step 2), not this change.
    if snapshot_days:
        disagreeing = list(snapshot_disagreements or ())
        checks["bank_daily_balances_agree_with_rows"] = not disagreeing
        if disagreeing:
            shown = ", ".join(day.isoformat() for day in disagreeing[:6])
            more = f" (+{len(disagreeing) - 6} more)" if len(disagreeing) > 6 else ""
            result.warnings.append(
                f"{len(disagreeing)} bank-printed daily balance(s) disagree with the balance "
                f"the transactions reach on the same day ({shown}{more}); the bank's daily "
                "balance was used for those days"
            )

    result.validations = checks

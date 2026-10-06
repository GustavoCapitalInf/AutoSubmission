"""Lender payment changes: the owner's request of 2026-10-06 (true revenue spec §2.2, §9.1, §9.2, §17.1; R2-OW18).

The owner: "can we also detect when a payment to lender has decreased? That would be a really important metric to
track." Clarified (2026-10-06): "Decreases, increases, stops", "Sustained, 10%+ drop" (the regular payment drops by at
least 10% and stays at the new amount for 2 or more payments; one-off short payments are not counted; bounced payments
are left out of the series), "Confirmed + potential" (potential lenders labelled 'potential').

INFORMATION ONLY. Nothing here moves paid to lenders, the withholding numerator, denominator or rate, the potential
exposure, the lender or potential-lender count, any lender, potential or flagged row, revenue or the review gate: the
module reads classification records (or their serialized dicts) and returns new items, nothing else. It never reads a
description, and never imports serialization or the webapp.

The model (the brief's parts A and B):

* A **series** is one lender's paid debits: a confirmed funder's (`canonical_entity`) or a potential lender's payee
  (`potential_payee_key`, the classifier's amount-free payee digest). Its **payments** are posted debits with the paid
  flag and no duplicate, reversal or returned-unpaid mark; its **attempts** (a bounced or reversed debit of the series)
  are presence, never an amount.
* Payments of one amount (equal cents, near-equal amounts within LEVEL_MERGE_PERCENT merged) seen twice or more form a
  **level**, with a cadence (`payment_cadence`); a payment seen once is a **one-off**. Levels that run at the same time
  with both beats kept are separate **positions** (two streams with one funder); a position far smaller than the
  series' largest on the weekly total is a **fee stream** and is dropped.
* Inside a position the payments form **regimes** (runs of one regular level held for 2 or more payments, catch-up
  multiples and one-offs set aside, a short regime at another schedule dropped). Each regime is compared with the last
  REPORTED level of its position (the orchestrator's choice of 2026-10-06, the brief's § Still open 23): a decrease or
  an increase of 10% or more, compared on the weekly equivalent when the schedule differs, or a schedule change. A
  change at a new schedule held 2 payments but not yet the 3 (5 if daily) that confirm the schedule is a "possible"
  change, "new schedule not yet confirmed" (the orchestrator's choice of 2026-10-06, § Still open 18).
* A **pause** is a gap inside one regime longer than the schedule's grace window; a **new stream** is a second position
  that starts while another keeps paying and raises the funder's weekly total by 10% or more; a **stop** is a position
  of 3 or more payments followed by no presence (a payment, a payment-sized debit or a bounced attempt) for longer than
  the grace window before the covered period ends.

Business days follow the statement's calendar: the Federal Reserve's holidays (`analysis.adb.federal_bank_holidays`),
or Payments Canada's non-processing days on a CAD statement (`_canadian_bank_holidays`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
from functools import lru_cache
from statistics import median
from typing import Any, Iterable, Mapping, NamedTuple, Sequence

from .adb import federal_bank_holidays, nth_weekday
from .dates import parse_date
from .transaction_classifier import UNIDENTIFIED_LENDER_OBLIGATION, UNIDENTIFIED_MCA_SERVICER

# ------------------------------------------------------------------------------------------------------- constants
#: A decrease or an increase moves the compared amount by this many percent or more.
CHANGE_THRESHOLD_PERCENT = 10
#: "stays at the new amount for 2 or more payments".
MIN_PAYMENTS_HELD = 2
#: A stop or a new stream needs a position of this many payments.
MIN_STOP_PAYMENTS = 3
#: Two amounts within this many percent of the level's representative are one level.
LEVEL_MERGE_PERCENT = 1
#: A position whose weekly weight is under this share of the series' largest is a fee stream; a one-off of at least
#: this share of the reference amount is presence (A3b).
FEE_STREAM_PERCENT = 5
#: A catch-up multiple: within this many percent of 2x or 3x the dominant amount, never run longer than 2 payments.
CATCH_UP_TOLERANCE_PERCENT = 2
CATCH_UP_MULTIPLES = (2, 3)
CATCH_UP_MAX_RUN = 2
#: Two levels are concurrent when at least this share of the minor's dates inside the major's span keep its beat.
BEAT_KEPT_PERCENT = 60
#: A regime spanning under this share of one cycle is short (A8); later statements covering this share of one cycle
#: confirm a package stop (B4).
SHORT_REGIME_CYCLE_PERCENT = 80
#: A change at a new schedule is confirmed when the new regime has this many payments (daily: the second figure).
CADENCE_CHANGE_MIN_PAYMENTS = 3
CADENCE_CHANGE_MIN_DAILY = 5
#: The days a major payment may stand from a minor one and still keep the major's beat (A7).
BEAT_TOLERANCE_DAYS = {"daily": 0, "daily_irregular": 1, "weekly": 3, "biweekly": 7, "semimonthly": 7, "monthly": 16}
BEAT_TOLERANCE_OTHER_DAYS = 3
#: The grace windows, in business days, of a stop and a pause (B4, B7).
STOP_GRACE_BUSINESS_DAYS = {"daily": 5, "daily_irregular": 6, "weekly": 10, "biweekly": 15, "semimonthly": 15,
                            "monthly": 25}
#: Payments a week of each schedule (A5); a cycle is 7 days divided by it.
WEEKLY_EQUIVALENT = {"daily": Fraction(5), "weekly": Fraction(1), "biweekly": Fraction(1, 2),
                     "semimonthly": Fraction(24, 52), "monthly": Fraction(12, 52)}
#: The funding note's window around the new amount's first payment, in calendar days (B3).
FUNDING_NOTE_DAYS_BEFORE = 20
FUNDING_NOTE_DAYS_AFTER = 5
#: A one-off at this multiple of the regular amount or more is a payoff, never presence (A3b, B5).
PAYOFF_MULTIPLE = 2
#: Another series that starts at an amount within this many percent of the stopped one continues it (B5).
HANDOFF_PERCENT = 10
#: A debt relief program's first debit within this multiple of the grace window after a stop is noted (B5).
DEBT_RELIEF_GRACE_MULTIPLE = 2
#: A potential series' item under this weekly equivalent, in cents, is not produced (A10).
POTENTIAL_MIN_WEEKLY_CENTS = 10000

#: The item kinds, in the order the items are listed within one date.
PAYMENT_CHANGE_KINDS = ("decrease", "increase", "cadence_change", "pause", "new_stream", "stop")
_REGULAR = ("daily", "weekly", "biweekly", "semimonthly", "monthly")
_UNNAMED_ENTITIES = frozenset({UNIDENTIFIED_LENDER_OBLIGATION, UNIDENTIFIED_MCA_SERVICER})
_DEBT_RELIEF_GROUP = "debt_relief"


class StatementRows(NamedTuple):
    """One statement of a chain: its rows (classification records or their serialized dicts), its printed period and
    its declared currency."""

    rows: Sequence[Any]
    period_start: str | date | None
    period_end: str | date | None
    currency: str | None


# --------------------------------------------------------------------------------------------------------- calendar
def calendar_for(currency: object) -> str:
    """'CA' on a statement that declares CAD (currency doctrine: CAD comes from Canadian bank names), else 'US'."""
    return "CA" if str(currency or "").strip().upper() == "CAD" else "US"


def _easter_sunday(year: int) -> date:
    """Easter Sunday of the Gregorian calendar (the anonymous Gregorian computation)."""
    golden = year % 19
    century, of_century = divmod(year, 100)
    leap_century, century_rest = divmod(century, 4)
    correction = (century + 8) // 25
    moon = (century - correction + 1) // 3
    epact = (19 * golden + century - leap_century - moon + 15) % 30
    leap_year, year_rest = divmod(of_century, 4)
    weekday = (32 + 2 * century_rest + 2 * leap_year - epact - year_rest) % 7
    shift = (golden + 11 * epact + 22 * weekday) // 451
    month, day = divmod(epact + weekday - 7 * shift + 114, 31)
    return date(year, month, day + 1)


def _monday_before(day: date) -> date:
    """The last Monday strictly before `day`."""
    return day - timedelta(days=day.weekday() or 7)


def _next_open_days(days: Iterable[date]) -> set[date]:
    """Each holiday that falls on a weekend, or on a day an earlier holiday already closes, moved to the next weekday
    that no holiday closes; the others where they fall."""
    closed: set[date] = set()
    for day in sorted(days):
        while day.weekday() >= 5 or day in closed:
            day += timedelta(days=1)
        closed.add(day)
    return closed


def _canadian_bank_holidays(year: int) -> set[date]:
    """Payments Canada's system closure (non-processing) days, Lynx and ACSS, as its published schedule lists them
    (https://www.payments.ca/system-closure-schedule, read 2026-10-06): New Year's Day, Good Friday, Victoria Day,
    Canada Day, Labour Day, the National Day for Truth and Reconciliation, Thanksgiving, Remembrance Day, Christmas Day
    and Boxing Day; a holiday that falls on a weekend closes the next business day (Boxing Day on a Saturday is
    observed on the Monday). The Civic Holiday (the first Monday of August) is NOT a closure day: the published
    schedule leaves it out, so this calendar does too (the brief's draft list had it; verified against the schedule).

    ONE STATED LIMITATION, as analysis.adb's Juneteenth: the National Day for Truth and Reconciliation is counted in
    every year rather than from its first observance, so no year literal enters the module."""
    return _next_open_days((
        date(year, 1, 1),                                   # New Year's Day
        _easter_sunday(year) - timedelta(days=2),           # Good Friday
        _monday_before(date(year, 5, 25)),                  # Victoria Day
        date(year, 7, 1),                                   # Canada Day
        nth_weekday(year, 9, 0, 1),                         # Labour Day
        date(year, 9, 30),                                  # National Day for Truth and Reconciliation
        nth_weekday(year, 10, 0, 2),                        # Thanksgiving
        date(year, 11, 11),                                 # Remembrance Day
        date(year, 12, 25),                                 # Christmas Day
        date(year, 12, 26),                                 # Boxing Day
    ))


@lru_cache(maxsize=None)
def _holidays(calendar: str, year: int) -> frozenset[date]:
    if calendar == "CA":
        return frozenset(_canadian_bank_holidays(year))
    return frozenset(federal_bank_holidays(year))


def business_days_between(first: date, second: date, calendar: str = "US") -> int:
    """The business days strictly after `first`, up to and including `second` (0 when `second` is not later): the
    weekdays that are no holiday of the calendar ('US' or 'CA')."""
    if second <= first:
        return 0
    weeks, rest = divmod((second - first).days, 7)
    count = 5 * weeks + sum(1 for step in range(1, rest + 1) if (first.weekday() + step) % 7 < 5)
    for year in range(first.year, second.year + 1):
        count -= sum(1 for day in _holidays(calendar, year) if first < day <= second and day.weekday() < 5)
    return count


# ---------------------------------------------------------------------------------------------------------- cadence
def payment_cadence(dates: Iterable[date], calendar: str = "US") -> str:
    """The schedule of a level from its distinct dates (A5): m = the median calendar gap, bm = the median business-day
    gap. daily (bm <= 1 and m <= 3); weekly (5..9); semimonthly or biweekly (12..17: semi-monthly on 3 or more dates,
    m != 14 and every day of month near the 1st or the 15th or the 28th or later); monthly (25..35); daily_irregular
    (1 < m < 5 and bm <= 2); else irregular; one date is single."""
    ordered = sorted(set(dates))
    if len(ordered) < 2:
        return "single"
    pairs = list(zip(ordered, ordered[1:]))
    gap = median((later - earlier).days for earlier, later in pairs)
    business_gap = median(business_days_between(earlier, later, calendar) for earlier, later in pairs)
    if business_gap <= 1 and gap <= 3:
        return "daily"
    if 5 <= gap <= 9:
        return "weekly"
    if 12 <= gap <= 17:
        if len(ordered) >= 3 and gap != 14 and all(
                abs(day.day - 1) <= 2 or abs(day.day - 15) <= 2 or day.day >= 28 for day in ordered):
            return "semimonthly"
        return "biweekly"
    if 25 <= gap <= 35:
        return "monthly"
    if 1 < gap < 5 and business_gap <= 2:
        return "daily_irregular"
    return "irregular"


def _regular(cadence: str) -> str | None:
    """The schedule a cadence is read as: daily_irregular as daily; None for irregular or single."""
    cadence = "daily" if cadence == "daily_irregular" else cadence
    return cadence if cadence in _REGULAR else None


def _weekly(cents: int, cadence: str) -> Fraction | None:
    regular = _regular(cadence)
    return None if regular is None else cents * WEEKLY_EQUIVALENT[regular]


def _cycle_days(cadence: str) -> Fraction:
    return Fraction(7) / WEEKLY_EQUIVALENT[_regular(cadence) or "weekly"]


def _grace(cadence: str) -> int | None:
    return STOP_GRACE_BUSINESS_DAYS.get(cadence)


# --------------------------------------------------------------------------------------------------------- the rows
def _field(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def _cents(value: object) -> int | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    return int((amount.copy_abs() * 100).to_integral_value(rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class _Row:
    """The row view (A1): the fields this module reads, from a record or its serialized dict."""

    statement: int
    position: int
    day: date
    cents: int
    debit: bool
    classification: str | None
    entity: str | None
    label: str | None
    payee_key: str | None
    posted: bool
    duplicate: bool
    reversed: bool
    returned: bool
    paid_lender: bool
    paid_potential: bool
    revenue_entity: str | None
    location: str
    flagged_group: str | None


def _row(record: Any, statement: int = 0, position: int = 0) -> _Row | None:
    """The row view of a TransactionClassification or of its serialized dict; None for an undated row, an
    unparseable date or an unreadable amount. Amounts are the row's absolute integer cents."""
    day = parse_date(_field(record, "date"))
    raw = _field(record, "amount")
    cents = _cents(raw) if raw is not None else None
    if day is None or cents is None:
        return None
    try:
        debit = Decimal(str(raw)) < 0
    except (InvalidOperation, ValueError):
        return None
    return _Row(
        statement=statement, position=position, day=day, cents=cents, debit=debit,
        classification=_field(record, "classification"), entity=_field(record, "canonical_entity"),
        label=_field(record, "potential_payee_label"), payee_key=_field(record, "potential_payee_key"),
        posted=_field(record, "is_posted") is not False, duplicate=bool(_field(record, "duplicate_of")),
        reversed=bool(_field(record, "reversed_by")), returned=bool(_field(record, "returned_funder_payment_by")),
        paid_lender=_field(record, "contributes_to_lender_totals") is True,
        paid_potential=_field(record, "contributes_to_potential_lender_totals") is True,
        revenue_entity=_field(record, "revenue_canonical_entity"),
        location=_field(record, "source_location") or f"transaction:{position + 1}",
        flagged_group=_field(record, "flagged_group"),
    )


def _series_key(row: _Row) -> tuple[str, str] | None:
    """A2: ('confirmed', canonical_entity) or ('potential', potential_payee_key); None for any other row."""
    if row.classification == "confirmed_lender" and row.entity:
        return ("confirmed", row.entity)
    if row.classification == "potential_lender" and row.payee_key:
        return ("potential", row.payee_key)
    return None


def _is_payment(row: _Row, key: tuple[str, str]) -> bool:
    """A2: a posted debit with no duplicate, reversal or returned-unpaid mark, carrying its state's paid flag."""
    if not (row.debit and row.posted) or row.duplicate or row.reversed or row.returned:
        return False
    return row.paid_lender if key[0] == "confirmed" else row.paid_potential


def _is_attempt(row: _Row) -> bool:
    """A3: a posted, non-duplicate debit of the series that bounced (returned unpaid) or was reversed."""
    return row.debit and row.posted and not row.duplicate and (row.returned or row.reversed)


@dataclass(frozen=True)
class _Pay:
    day: date
    cents: int
    statement: int
    position: int
    location: str
    label: str | None

    @property
    def order(self) -> tuple:
        return (self.day, self.cents, self.statement, self.position)


@dataclass
class _Series:
    key: tuple[str, str]
    entity: str
    payments: list[_Pay] = field(default_factory=list)
    attempts: list[_Pay] = field(default_factory=list)


@dataclass
class _Chain:
    """The rows of a statement or of a package chain, read once."""

    series: dict[tuple[str, str], _Series]
    credits: list[_Row]
    debt_relief: list[_Row]
    last_day: date | None
    periods: list[tuple[date | None, date | None]]
    calendar: str


def _pay(row: _Row) -> _Pay:
    return _Pay(row.day, row.cents, row.statement, row.position, row.location, row.label)


def _read_chain(statements: Sequence[StatementRows]) -> _Chain:
    """Every statement's rows, with part F4's overlap de-duplication: inside an overlap, a later statement's payment or
    attempt dated on or before the earlier statement's period end that equals one of the earlier statement's (series
    key, day, cents) is dropped, each earlier row consumed once."""
    series: dict[tuple[str, str], _Series] = {}
    credits: list[_Row] = []
    debt_relief: list[_Row] = []
    last_day: date | None = None
    periods = [(parse_date(item.period_start), parse_date(item.period_end)) for item in statements]
    previous: dict[tuple, list[date]] = {}
    for index, item in enumerate(statements):
        boundary = periods[index - 1][1] if index else None
        start = periods[index][0]
        overlap = boundary is not None and start is not None and start <= boundary
        current: dict[tuple, list[date]] = {}
        for position, record in enumerate(item.rows or ()):
            row = _row(record, index, position)
            if row is None:
                continue
            last_day = row.day if last_day is None or row.day > last_day else last_day
            if not row.debit:
                if row.posted and not row.duplicate:
                    credits.append(row)
                continue
            if row.flagged_group == _DEBT_RELIEF_GROUP and row.posted and not row.duplicate:
                debt_relief.append(row)
            key = _series_key(row)
            if key is None:
                continue
            kind = "payment" if _is_payment(row, key) else "attempt" if _is_attempt(row) else None
            if kind is None:
                continue
            signature = (kind, key, row.day, row.cents)
            if overlap and row.day <= boundary and row.day in previous.get(signature, ()):
                previous[signature].remove(row.day)
                continue
            current.setdefault(signature, []).append(row.day)
            entry = series.setdefault(key, _Series(key, row.entity or ""))
            (entry.payments if kind == "payment" else entry.attempts).append(_pay(row))
        previous = current
    for entry in series.values():
        entry.payments.sort(key=lambda pay: pay.order)
        entry.attempts.sort(key=lambda pay: pay.order)
    currencies = [item.currency for item in statements]
    calendar = calendar_for(next((currency for currency in currencies if currency), None))
    return _Chain(series, credits, debt_relief, last_day, periods, calendar)


# ----------------------------------------------------------------------------------------- levels and positions
@dataclass
class _Level:
    amount: int
    pays: list[_Pay]
    cadence: str

    @property
    def first(self) -> date:
        return self.pays[0].day

    @property
    def last(self) -> date:
        return self.pays[-1].day

    @property
    def n(self) -> int:
        return len(self.pays)

    @property
    def dates(self) -> list[date]:
        return sorted({pay.day for pay in self.pays})


def _levels(payments: list[_Pay], calendar: str) -> tuple[list[_Level], list[_Pay]]:
    """A4: payments grouped by exact cents; amounts visited by (-count, amount), each joining the first cluster whose
    representative (its first, most frequent amount) is within LEVEL_MERGE_PERCENT. A cluster of 2 or more payments is
    a level; one payment is a one-off. Levels come in (first date, -payments) order."""
    by_cents: dict[int, list[_Pay]] = {}
    for pay in payments:
        by_cents.setdefault(pay.cents, []).append(pay)
    clusters: list[list[int]] = []
    for cents in sorted(by_cents, key=lambda value: (-len(by_cents[value]), value)):
        for cluster in clusters:
            if 100 * abs(cents - cluster[0]) <= LEVEL_MERGE_PERCENT * cluster[0]:
                cluster.append(cents)
                break
        else:
            clusters.append([cents])
    levels: list[_Level] = []
    singles: list[_Pay] = []
    for cluster in clusters:
        pays = sorted((pay for cents in cluster for pay in by_cents[cents]), key=lambda pay: pay.order)
        if len(pays) >= 2:
            levels.append(_Level(cluster[0], pays, payment_cadence((pay.day for pay in pays), calendar)))
        else:
            singles.extend(pays)
    levels.sort(key=lambda level: (level.first, -level.n))
    return levels, sorted(singles, key=lambda pay: pay.order)


def _concurrent(one: _Level, other: _Level) -> bool:
    """A7: the minor level (fewer distinct dates, then fewer payments) has 2 or more distinct dates inside the major's
    span, and at least BEAT_KEPT_PERCENT of them have a major payment within the major cadence's beat tolerance."""
    major, minor = (one, other) if (len(one.dates), one.n) >= (len(other.dates), other.n) else (other, one)
    inside = [day for day in minor.dates if major.first <= day <= major.last]
    if len(inside) < 2:
        return False
    tolerance = BEAT_TOLERANCE_DAYS.get(major.cadence, BEAT_TOLERANCE_OTHER_DAYS)
    major_dates = major.dates
    kept = sum(1 for day in inside if any(abs((other_day - day).days) <= tolerance for other_day in major_dates))
    return 100 * kept >= BEAT_KEPT_PERCENT * len(inside)


@dataclass
class _Position:
    levels: list[_Level]
    number: int = 0

    @property
    def pays(self) -> list[_Pay]:
        return sorted((pay for level in self.levels for pay in level.pays), key=lambda pay: pay.order)

    @property
    def first(self) -> date:
        return min(level.first for level in self.levels)

    @property
    def last(self) -> date:
        return max(level.last for level in self.levels)

    @property
    def n(self) -> int:
        return sum(level.n for level in self.levels)

    @property
    def last_level(self) -> _Level:
        return max(self.levels, key=lambda level: level.last)

    def weight(self) -> Fraction | None:
        values = [weekly for level in self.levels if (weekly := _weekly(level.amount, level.cadence)) is not None]
        return max(values) if values else None


def _positions(levels: list[_Level]) -> list[_Position]:
    """A7: each level joins the existing position it is concurrent with no level of, the one whose latest payment is
    latest; otherwise it starts a new position."""
    positions: list[_Position] = []
    for level in levels:
        best: _Position | None = None
        for position in positions:
            if any(_concurrent(level, other) for other in position.levels):
                continue
            if best is None or position.last > best.last:
                best = position
        if best is None:
            positions.append(_Position([level]))
        else:
            best.levels.append(level)
    return positions


def _paying_positions(positions: list[_Position]) -> list[_Position]:
    """A7's fee test: a position whose weight (its largest regular weekly equivalent) is under FEE_STREAM_PERCENT of
    the series' largest weight is dropped; a position with no regular level compares its largest raw level amount
    with the series' largest raw level amount. The others are numbered 1..n by first payment date."""
    weights = [weight for position in positions if (weight := position.weight()) is not None]
    largest_weight = max(weights) if weights else None
    largest_raw = max(level.amount for position in positions for level in position.levels)

    def fee(position: _Position) -> bool:
        weight = position.weight()
        if weight is not None and largest_weight:
            return 100 * weight < FEE_STREAM_PERCENT * largest_weight
        return 100 * max(level.amount for level in position.levels) < FEE_STREAM_PERCENT * largest_raw

    kept = sorted((position for position in positions if not fee(position)), key=lambda position: position.first)
    for number, position in enumerate(kept, start=1):
        position.number = number
    return kept


# ------------------------------------------------------------------------------------------------------- regimes
@dataclass
class _Regime:
    level: int
    amount: int
    cadence: str
    pays: list[_Pay]

    @property
    def first(self) -> date:
        return self.pays[0].day

    @property
    def last(self) -> date:
        return self.pays[-1].day

    @property
    def n(self) -> int:
        return len(self.pays)

    @property
    def span(self) -> int:
        return (self.last - self.first).days


def _regimes(position: _Position, calendar: str) -> list[_Regime]:
    """A8: the position's payments in date order (ties by level) compressed into runs of one level; a run of an
    irregular or single level, of under MIN_PAYMENTS_HELD payments, or of a catch-up multiple is noise, which neither
    forms nor breaks a regime; consecutive non-noise runs of one level merge. A regime's cadence is its own when
    regular, else its level's."""
    levels = position.levels
    tagged = sorted(((pay, index) for index, level in enumerate(levels) for pay in level.pays),
                    key=lambda item: (item[0].day, item[1], item[0].order))
    runs: list[tuple[int, list[_Pay]]] = []
    for pay, index in tagged:
        if runs and runs[-1][0] == index:
            runs[-1][1].append(pay)
        else:
            runs.append((index, [pay]))
    dominant = max(range(len(levels)), key=lambda index: (levels[index].n, -index))
    longest: dict[int, int] = {}
    for index, pays in runs:
        longest[index] = max(longest.get(index, 0), len(pays))
    catch_up = {
        index for index, level in enumerate(levels)
        if index != dominant and longest.get(index, 0) <= CATCH_UP_MAX_RUN
        and any(100 * abs(level.amount - multiple * levels[dominant].amount) <= CATCH_UP_TOLERANCE_PERCENT * level.amount
                for multiple in CATCH_UP_MULTIPLES)
    }
    regimes: list[_Regime] = []
    for index, pays in runs:
        cadence = _regular(levels[index].cadence)
        if cadence is None or len(pays) < MIN_PAYMENTS_HELD or index in catch_up:
            continue
        if regimes and regimes[-1].level == index:
            regimes[-1].pays.extend(pays)
        else:
            regimes.append(_Regime(index, levels[index].amount, cadence, list(pays)))
    for regime in regimes:
        own = _regular(payment_cadence((pay.day for pay in regime.pays), calendar))
        if own is not None:
            regime.cadence = own
    return regimes


def _spans_a_cycle(regime: _Regime, cadence: str, other_cadence: str) -> bool:
    """The regime spans at least SHORT_REGIME_CYCLE_PERCENT of one cycle of the slower of the two cadences."""
    slower = max(_cycle_days(cadence), _cycle_days(other_cadence))
    return 100 * regime.span >= SHORT_REGIME_CYCLE_PERCENT * slower


def _enough_payments(regime: _Regime) -> bool:
    """3 or more payments, 5 or more when daily: the payments that confirm a schedule."""
    needed = CADENCE_CHANGE_MIN_DAILY if regime.cadence == "daily" else CADENCE_CHANGE_MIN_PAYMENTS
    return regime.n >= needed


def _short(regime: _Regime, other_cadence: str) -> bool:
    return not (_enough_payments(regime) and _spans_a_cycle(regime, regime.cadence, other_cadence))


def _drop_short(regimes: list[_Regime]) -> tuple[list[_Regime], list[_Regime]]:
    """A8's short off-cadence regimes: a regime that is short (daily under 5 payments, under 3 payments, or spanning
    under 80% of one cycle of the slower of its cadence and its neighbour's) and whose cadence differs from every
    neighbour's is dropped; after each drop, same-level neighbours merge; repeated until nothing changes. Returns the
    kept regimes and the dropped ones (§ Still open 18's candidates)."""
    kept = [_Regime(regime.level, regime.amount, regime.cadence, list(regime.pays)) for regime in regimes]
    dropped: list[_Regime] = []
    changed = True
    while changed and len(kept) > 1:
        changed = False
        for index, regime in enumerate(kept):
            neighbours = [kept[other].cadence for other in (index - 1, index + 1) if 0 <= other < len(kept)]
            if neighbours and all(cadence != regime.cadence for cadence in neighbours) and _short(regime, neighbours[0]):
                dropped.append(regime)
                del kept[index]
                if 0 < index < len(kept) and kept[index - 1].level == kept[index].level:
                    kept[index - 1].pays.extend(kept[index].pays)
                    del kept[index]
                changed = True
                break
    return kept, sorted(dropped, key=lambda regime: regime.first)


def _same_level(one: _Regime, other: _Regime) -> bool:
    return one.level == other.level and one.cadence == other.cadence


def _at_level(regime: _Regime, reference: _Regime) -> bool:
    """B3's reverted test: the regime's amount is within LEVEL_MERGE_PERCENT of the reference's, at its cadence."""
    return (100 * abs(regime.amount - reference.amount) <= LEVEL_MERGE_PERCENT * reference.amount
            and regime.cadence == reference.cadence)


# ------------------------------------------------------------------------------------------------------ the series
@dataclass(frozen=True)
class _Mark:
    """One presence date of a position (A3b): a payment, an attempt or a payment-sized one-off of the series."""

    day: date
    kind: str
    pay: _Pay

    @property
    def order(self) -> tuple:
        return (self.day, ("one_off", "attempt", "payment").index(self.kind), self.pay.order)


@dataclass
class _Reading:
    """One series read: its levels, one-offs, every position and the paying (non-fee) positions."""

    series: _Series
    singles: list[_Pay]
    positions: list[_Position]

    @property
    def state(self) -> str:
        return self.series.key[0]

    @property
    def named(self) -> bool:
        return self.state == "confirmed" or self.series.entity not in _UNNAMED_ENTITIES


@dataclass
class _Scope:
    chain: _Chain
    scope: str
    coverage_end: date | None
    coverage_source: str
    holes: list[tuple[date, date]]
    readings: dict[tuple[str, str], _Reading]

    def business_days(self, first: date, second: date) -> int:
        return business_days_between(first, second, self.chain.calendar)


def _band(pay: _Pay, reference: int) -> bool:
    """A3b: a one-off of at least FEE_STREAM_PERCENT and under PAYOFF_MULTIPLE times the reference amount."""
    return FEE_STREAM_PERCENT * reference <= 100 * pay.cents < 100 * PAYOFF_MULTIPLE * reference


def _presence(reading: _Reading, position: _Position, reference: int) -> list[_Mark]:
    """A3b, the one presence definition: the position's payments, the series' attempts and the series' payment-sized
    one-offs (`_band` of the reference amount), in date order."""
    marks = [_Mark(pay.day, "payment", pay) for pay in position.pays]
    marks += [_Mark(pay.day, "attempt", pay) for pay in reading.series.attempts]
    marks += [_Mark(pay.day, "one_off", pay) for pay in reading.singles if _band(pay, reference)]
    return sorted(marks, key=lambda mark: mark.order)


def _first_mark_after(marks: list[_Mark], day: date) -> _Mark | None:
    return next((mark for mark in marks if mark.day > day), None)


def _under_floor(reading: _Reading, *weeklies: Fraction | None) -> bool:
    """A10: a potential series' item whose weekly equivalent (the largest given) is under POTENTIAL_MIN_WEEKLY_CENTS."""
    if reading.state != "potential":
        return False
    values = [value for value in weeklies if value is not None]
    return not values or max(values) < POTENTIAL_MIN_WEEKLY_CENTS


def _money(cents: int | Fraction) -> float:
    return round(float(cents) / 100, 2)


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day is not None else None


def _label(pay: _Pay, reading: _Reading) -> str:
    return pay.label or reading.series.entity


def _common(kind: str, reading: _Reading, position: _Position, positions: int, scope: _Scope, label: str) -> dict:
    return {
        "kind": kind, "lender": reading.series.entity, "lender_label": label, "lender_state": reading.state,
        "position": position.number, "positions": positions, "scope": scope.scope,
    }


def _after_funding(reading: _Reading, scope: _Scope, first: date) -> dict | None:
    """B3: the latest posted, non-duplicate credit of the series' entity (canonical or revenue entity) dated from
    FUNDING_NOTE_DAYS_BEFORE days before to FUNDING_NOTE_DAYS_AFTER days after the new amount's first payment; for a
    confirmed series, or a potential series whose entity is named."""
    if not reading.named:
        return None
    entity = reading.series.entity
    window = (first - timedelta(days=FUNDING_NOTE_DAYS_BEFORE), first + timedelta(days=FUNDING_NOTE_DAYS_AFTER))
    credits = [row for row in scope.chain.credits
               if (row.entity == entity or row.revenue_entity == entity) and window[0] <= row.day <= window[1]]
    if not credits:
        return None
    latest = max(credits, key=lambda row: (row.day, row.statement, row.position))
    return {"date": latest.day.isoformat(), "amount": _money(latest.cents)}


def _compared(before: _Regime, new: _Regime) -> Fraction:
    """B1: the raw amounts at one cadence, the weekly equivalents at two; exact arithmetic."""
    if before.cadence == new.cadence:
        return Fraction(new.amount, before.amount)
    return (new.amount * WEEKLY_EQUIVALENT[new.cadence]) / (before.amount * WEEKLY_EQUIVALENT[before.cadence])


def _change(reading: _Reading, position: _Position, positions: int, scope: _Scope, *, before: _Regime,
            previous: _Regime, previous_last: date, new: _Regime, via: list[_Regime], earlier: list[_Regime],
            later: list[_Regime], at_end: bool, dropped: bool) -> tuple[dict | None, bool]:
    """One transition (B1, B2, B3), compared with `before`, the last reported regime of the position (§ Still open
    23's alternative); the pause is read from `previous`, the regime just before. Returns (item or None, whether it is
    reported as a confirmed level, which then becomes the reference)."""
    cadence_changed = before.cadence != new.cadence
    if dropped and not cadence_changed:
        return None, False
    ratio = _compared(before, new)
    marks = _presence(reading, position, previous.amount)
    resume = _first_mark_after(marks, previous_last)
    pause_end = min(resume.day, new.first) if resume is not None else new.first
    pause = scope.business_days(previous_last, pause_end)
    restart = pause > max(_grace(previous.cadence) or 0, _grace(new.cadence) or 0)
    if 100 * ratio <= 100 - CHANGE_THRESHOLD_PERCENT:
        kind = "decrease"
    elif 100 * ratio >= 100 + CHANGE_THRESHOLD_PERCENT:
        kind = "increase"
    elif cadence_changed and not restart:
        kind = "cadence_change"
    else:
        return None, False
    confirmed = not dropped and (not cadence_changed or (
        _enough_payments(new) and _spans_a_cycle(new, before.cadence, new.cadence)))
    if not confirmed:
        # § Still open 18's alternative (the orchestrator's choice of 2026-10-06): a decrease or an increase at a new
        # schedule held 2 payments but not yet confirmed is a possible change, when it is the position's last regime,
        # or mid-position when its payments span the confirmation's share of a cycle.
        if kind == "cadence_change":
            return None, False
        if not (at_end or _spans_a_cycle(new, before.cadence, new.cadence)):
            return None, False
    weekly_before = before.amount * WEEKLY_EQUIVALENT[before.cadence]
    weekly_after = new.amount * WEEKLY_EQUIVALENT[new.cadence]
    if _under_floor(reading, weekly_before, weekly_after):
        return None, False
    reverted_on = None
    for regime in later:
        if _at_level(regime, before):
            reverted_on = min((pay.day for pay in regime.pays if pay.day > new.last), default=None)
            if reverted_on is not None:
                break
    item = _common(kind, reading, position, positions, scope, _label(before.pays[-1], reading))
    item.update({
        "lender_label_after": _label(new.pays[0], reading),
        "cadence_before": before.cadence, "cadence_after": new.cadence,
        "amount_before": _money(before.amount), "amount_after": _money(new.amount),
        "change_percent": round((ratio - 1) * 100),
        "cadence_changed": cadence_changed,
        "schedule_confirmed": confirmed,
    })
    if cadence_changed:
        item["weekly_equivalent_before"] = _money(weekly_before)
        item["weekly_equivalent_after"] = _money(weekly_after)
    item.update({
        "payments_before": before.n, "payments_after": new.n,
        "last_before_date": _iso(before.last), "first_after_date": _iso(new.first), "last_after_date": _iso(new.last),
        "restart": restart, "pause_business_days": pause if restart else None,
        "back_to_earlier": any(regime.level == new.level for regime in earlier),
        "reverted": reverted_on is not None, "reverted_date": _iso(reverted_on),
    })
    if via:
        item["via"] = [{"amount": _money(regime.amount), "cadence": regime.cadence} for regime in via]
    funding = _after_funding(reading, scope, new.first)
    if funding is not None:
        item["after_funding"] = funding
    item["locations"] = {"last_before": before.pays[-1].location, "first_after": new.pays[0].location}
    item.update({"_from_statement": before.pays[-1].statement, "_to_statement": new.pays[1].statement,
                 "_source_statement": new.pays[0].statement})
    return item, confirmed


def _transitions(reading: _Reading, position: _Position, positions: int, scope: _Scope) -> list[dict]:
    """B1-B3 over one position's regimes. The reference starts at the first regime and moves to each regime a
    confirmed change reports (§ Still open 23's alternative: steps under 10% add up against it); a regime at the
    reference's level takes its place. The regimes A8 dropped are read afterwards, each against the reference in force
    after the kept regime before it, and give at most a possible change (§ Still open 18's alternative)."""
    regimes = _regimes(position, scope.chain.calendar)
    kept, dropped = _drop_short(regimes)
    if not kept:
        return []
    last_day = position.last
    items: list[dict] = []
    reference = 0
    references = [0]
    for index in range(1, len(kept)):
        previous, new = kept[index - 1], kept[index]
        if _same_level(previous, kept[reference]):
            reference = index - 1
        item, reported = _change(
            reading, position, positions, scope, before=kept[reference], previous=previous,
            previous_last=previous.last, new=new, via=kept[reference + 1:index], earlier=kept[:index],
            later=kept[index + 1:], at_end=index == len(kept) - 1 and new.last >= last_day, dropped=False)
        if item is not None:
            items.append(item)
        if reported:
            reference = index
        references.append(reference)
    for regime in dropped:
        prior = [(max(pay.day for pay in kept_regime.pays if pay.day < regime.first), number)
                 for number, kept_regime in enumerate(kept) if kept_regime.first < regime.first]
        if not prior:
            continue
        previous_last, number = max(prior)
        reference = references[number]
        if _same_level(kept[number], kept[reference]):
            reference = number
        # A kept regime that the drop merged across this one is read up to it: its payments before it.
        before, previous = (_Regime(kept_regime.level, kept_regime.amount, kept_regime.cadence,
                                    [pay for pay in kept_regime.pays if pay.day < regime.first])
                            for kept_regime in (kept[reference], kept[number]))
        item, _reported = _change(
            reading, position, positions, scope, before=before, previous=previous,
            previous_last=previous_last, new=regime, via=kept[reference + 1:number + 1],
            earlier=[kept_regime for kept_regime in kept if kept_regime.first < regime.first],
            later=[kept_regime for kept_regime in kept if kept_regime.last > regime.last],
            at_end=regime.last >= last_day, dropped=True)
        if item is not None:
            items.append(item)
    return items


def _pauses(reading: _Reading, position: _Position, positions: int, scope: _Scope) -> list[dict]:
    """B7: inside one regime (after A8), a gap from a payment to the next presence (the regime's amount the band's
    reference) longer than the regime cadence's grace window, with no chain coverage hole between them."""
    items: list[dict] = []
    kept, _dropped = _drop_short(_regimes(position, scope.chain.calendar))
    for regime in kept:
        grace = _grace(regime.cadence)
        if grace is None or _under_floor(reading, regime.amount * WEEKLY_EQUIVALENT[regime.cadence]):
            continue
        marks = _presence(reading, position, regime.amount)
        last_on: dict[date, _Pay] = {}
        for pay in regime.pays:
            last_on[pay.day] = pay
        days = sorted(last_on)
        for first, _second in zip(days, days[1:]):
            resume = _first_mark_after(marks, first)
            if resume is None:
                continue
            pause = scope.business_days(first, resume.day)
            if pause <= grace or any(first <= end and start <= resume.day for end, start in scope.holes):
                continue
            item = _common("pause", reading, position, positions, scope, _label(last_on[first], reading))
            item.update({
                "cadence": regime.cadence, "last_payment_amount": _money(regime.amount),
                "last_before_date": _iso(first), "first_after_date": _iso(resume.day),
                "pause_business_days": pause, "grace_business_days": grace,
                "locations": {"last_before": last_on[first].location, "first_after": resume.pay.location},
                "_source_statement": resume.pay.statement,
            })
            items.append(item)
    return items


def _first_position(reading: _Reading) -> _Position | None:
    return min(reading.positions, key=lambda position: position.first, default=None)


def _starting_series(scope: _Scope, reading: _Reading, after: date, grace: int) -> list[tuple[_Reading, _Position]]:
    """B5: every other series of the statement (chain) whose first payment falls after `after`, within `grace` business
    days, with its first paying position; the earliest first."""
    found = []
    for key, other in scope.readings.items():
        if key == reading.series.key or not other.series.payments:
            continue
        first = _first_position(other)
        if first is None or other.series.payments[0].day <= after:
            continue
        if scope.business_days(after, first.first) <= grace:
            found.append((first.first, other.state != "confirmed", other.series.entity, key, other, first))
    return [(item[4], item[5]) for item in sorted(found, key=lambda item: item[:4])]


def _first_level(position: _Position) -> _Level:
    return min(position.levels, key=lambda level: (level.first, -level.n))


def _series_note(other: _Reading, position: _Position) -> dict:
    level = _first_level(position)
    return {"lender": other.series.entity, "lender_label": _label(position.pays[0], other),
            "lender_state": other.state, "amount": _money(level.amount), "cadence": _regular(level.cadence) or level.cadence,
            "first_date": _iso(position.first)}


def _stops(reading: _Reading, positions: list[_Position], scope: _Scope) -> list[dict]:
    """B4 and B5: a position of MIN_STOP_PAYMENTS or more payments whose last-paying level is regular, followed by no
    presence for more than its grace window before the coverage end."""
    items: list[dict] = []
    if scope.coverage_end is None:
        return items
    for position in positions:
        level = position.last_level
        grace = _grace(level.cadence)
        if position.n < MIN_STOP_PAYMENTS or grace is None:
            continue
        reference = level.amount
        marks = _presence(reading, position, reference)
        last_mark = max(marks, key=lambda mark: mark.order)
        quiet = scope.business_days(last_mark.day, scope.coverage_end)
        if quiet <= grace or _under_floor(reading, _weekly(reference, level.cadence)):
            continue
        last_pay = position.pays[-1]
        item = _common("stop", reading, position, len(positions), scope, _label(last_pay, reading))
        confirmed = False
        statements = len(scope.chain.periods)
        later = last_mark.pay.statement + 1
        if scope.scope == "package" and later < statements and scope.coverage_source == "period_end":
            later_start = scope.chain.periods[later][0]
            if later_start is not None:
                covered = (scope.coverage_end - later_start).days + 1
                factor = WEEKLY_EQUIVALENT[_regular(level.cadence)]
                confirmed = 100 * covered * factor >= SHORT_REGIME_CYCLE_PERCENT * 7
        item.update({
            "cadence": level.cadence, "last_payment_date": _iso(last_pay.day),
            "last_payment_amount": _money(last_pay.cents), "payments": position.n,
            "last_presence_date": _iso(last_mark.day), "quiet_business_days": quiet, "grace_business_days": grace,
            "coverage_end": _iso(scope.coverage_end), "coverage_end_source": scope.coverage_source,
            "stop_confirmed": confirmed,
        })
        after_last = [pay for pay in reading.singles if pay.day > last_pay.day]
        band_after = [pay for pay in after_last if _band(pay, reference)]
        if band_after:
            item["other_debits_after"] = {"count": len(band_after), "last_date": _iso(band_after[-1].day)}
        payoffs = [pay for pay in after_last if pay.cents >= PAYOFF_MULTIPLE * reference]
        if payoffs:
            item["payoff"] = {"date": _iso(payoffs[-1].day), "amount": _money(payoffs[-1].cents)}
        handoff = [(other, found) for other, found in _starting_series(scope, reading, last_pay.day, grace)
                   if 100 * abs(_first_level(found).amount - reference) <= HANDOFF_PERCENT * reference]
        if handoff:
            note = _series_note(*handoff[0])
            item["continues_as"] = {key: note[key] for key in ("lender", "lender_label", "lender_state", "amount",
                                                               "first_date")}
        streams = [other for other in positions if other is not position and other.last > last_pay.day]
        if streams:
            stream_level = streams[0].last_level
            item["other_stream_continues"] = {"amount": _money(stream_level.amount),
                                              "cadence": _regular(stream_level.cadence) or stream_level.cadence}
        if last_mark.kind == "attempt":
            item["last_attempt_returned"] = {"date": _iso(last_mark.day)}
        relief = min((row.day for row in scope.chain.debt_relief), default=None)
        if relief is not None and relief > last_mark.day and (
                scope.business_days(last_mark.day, relief) <= DEBT_RELIEF_GRACE_MULTIPLE * grace):
            item["debt_relief_after"] = {"date": _iso(relief)}
        if "continues_as" not in item:
            starting = _starting_series(scope, reading, last_mark.day, grace)
            if starting:
                item["new_lender_after"] = _series_note(*starting[0])
        item["locations"] = {"last_payment": last_pay.location}
        item["_source_statement"] = last_mark.pay.statement
        item["_last_presence"] = _iso(last_mark.day)
        items.append(item)
    return items


def _new_streams(reading: _Reading, positions: list[_Position], scope: _Scope) -> list[dict]:
    """B8: a position P (3 or more payments, a regular last cadence) that starts at least one grace window after
    another such position Q began, while Q still pays 3 or more times on or after P's first payment, and raises the
    funder's weekly total by CHANGE_THRESHOLD_PERCENT or more."""
    items: list[dict] = []
    real = [position for position in positions
            if position.n >= MIN_STOP_PAYMENTS and _grace(position.last_level.cadence) is not None]
    for stream in real:
        alongside = [
            other for other in real
            if other is not stream and other.first < stream.first
            and scope.business_days(other.first, stream.first) >= _grace(other.last_level.cadence)
            and sum(1 for pay in other.pays if pay.day >= stream.first) >= MIN_STOP_PAYMENTS
        ]
        if not alongside:
            continue
        level = stream.last_level
        weekly = _weekly(level.amount, level.cadence)
        before = sum(_weekly(other.last_level.amount, other.last_level.cadence) for other in alongside)
        if _under_floor(reading, weekly) or 100 * weekly < CHANGE_THRESHOLD_PERCENT * before:
            continue
        item = _common("new_stream", reading, stream, len(positions), scope, _label(stream.pays[-1], reading))
        item.update({
            "cadence_after": _regular(level.cadence), "amount_after": _money(level.amount),
            "first_after_date": _iso(stream.first), "payments_after": stream.n,
            "alongside": [{"position": other.number, "cadence": _regular(other.last_level.cadence),
                           "amount": _money(other.last_level.amount)} for other in alongside],
            "weekly_total_before": _money(before), "weekly_total_after": _money(before + weekly),
            "change_percent": round(((before + weekly) / before - 1) * 100),
            "locations": {"first_after": stream.pays[0].location},
            "_source_statement": stream.pays[0].statement,
        })
        items.append(item)
    return items


def _read_series(series: _Series, calendar: str) -> _Reading:
    levels, singles = _levels(series.payments, calendar)
    positions = _paying_positions(_positions(levels)) if levels else []
    return _Reading(series, singles, positions)


_KIND_RANK = {kind: rank for rank, kind in enumerate(PAYMENT_CHANGE_KINDS)}


def _item_order(item: dict) -> tuple:
    day = item.get("first_after_date") or item.get("last_payment_date") or ""
    key = item.get("_series_key") or ("", "")
    return (item["lender_state"] != "confirmed", item["lender"] or "", key[1], item["position"], day,
            _KIND_RANK[item["kind"]])


def payment_changes(statements: Sequence[StatementRows | tuple], *, scope: str = "package") -> list[dict]:
    """The lender payment changes of a chain: the statements of one account in period order, each (rows,
    period_start, period_end, currency). One dict per signal (decrease, increase, cadence_change, pause, new_stream,
    stop), ordered by (confirmed first, lender, series, position, date, kind). Part F4's overlap de-duplication is
    applied here. Each item also carries internal keys, each starting with '_': the module statement indexes
    (`_source_statement`: the first payment at the new amount, the resuming presence or the last presence;
    `_from_statement` and `_to_statement` on a change: the last old payment and the new regime's second payment), the
    series key (`_series_key`) and, on a stop, `_last_presence`; the package turns them into its source fields and
    drops them (statement_payment_changes drops them too). The coverage end is the last statement's printed period
    end, else the last dated row (`coverage_end_source` 'last_transaction')."""
    rows = [item if isinstance(item, StatementRows) else StatementRows(*item) for item in statements]
    if not rows:
        return []
    chain = _read_chain(rows)
    coverage_end, source = chain.periods[-1][1], "period_end"
    if coverage_end is None:
        coverage_end, source = chain.last_day, "last_transaction"
    holes = [(earlier[1], later[0]) for earlier, later in zip(chain.periods, chain.periods[1:])
             if earlier[1] is not None and later[0] is not None and (later[0] - earlier[1]).days > 1]
    readings = {key: _read_series(series, chain.calendar) for key, series in chain.series.items()}
    context = _Scope(chain, scope, coverage_end, source, holes, readings)
    items: list[dict] = []
    for key, reading in readings.items():
        positions = reading.positions
        found: list[dict] = []
        for position in positions:
            found.extend(_transitions(reading, position, len(positions), context))
            found.extend(_pauses(reading, position, len(positions), context))
        found.extend(_new_streams(reading, positions, context))
        found.extend(_stops(reading, positions, context))
        for item in found:
            item["_series_key"] = key
        items.extend(found)
    items.sort(key=_item_order)
    return items


def public_item(item: Mapping[str, Any]) -> dict:
    """The item without the module's internal keys (those starting with '_')."""
    return {key: value for key, value in item.items() if not key.startswith("_")}


def statement_payment_changes(rows: Sequence[Any], *, period_start: str | date | None = None,
                              period_end: str | date | None = None, currency: str | None = None) -> list[dict]:
    """The lender payment changes of one statement (scope 'statement'): `payment_changes` on a chain of one, its
    internal keys dropped. A stop inside one statement is never confirmed (a possible stop)."""
    return [public_item(item) for item in payment_changes(
        [StatementRows(rows, period_start, period_end, currency)], scope="statement")]


def series_activity_after(statements: Sequence[StatementRows | tuple], series_key: Sequence[str],
                          after: str | date) -> dict | None:
    """F5: the earliest payment or attempt of `series_key` dated after `after` in a chain (another account of the
    package), as {'statement': module index, 'date', 'amount'}; None when there is none."""
    rows = [item if isinstance(item, StatementRows) else StatementRows(*item) for item in statements]
    chain = _read_chain(rows)
    series = chain.series.get(tuple(series_key))
    cutoff = parse_date(after)
    if series is None or cutoff is None:
        return None
    later = sorted((pay for pay in (*series.payments, *series.attempts) if pay.day > cutoff), key=lambda pay: pay.order)
    if not later:
        return None
    return {"statement": later[0].statement, "date": _iso(later[0].day), "amount": _money(later[0].cents)}

"""Active positions by month: the owner's request of 2026-10-10 (true revenue spec §2.2, §9.1, §9.2, §10, §20).

The owner: "One thing i want to add right now and it should also be included in the demo website is the active
Position count by month." His answers of 2026-10-10 (all the recommended options): confirmed lenders count (MCA funders
and equipment financing, the lender ruling of 2026-09-24) and potential lenders are shown beside them, apart ("2 active
positions (+1 possible)"), alternative positions, lines of credit, credit cards, bank loans, leases and every other
flag group staying out; one funder paying on two schedules is 2 positions (each payment stream counts, by the app's
existing stream detection; a small fee stream is never a position); a position is active in a month when a payment
cleared that month (bounced attempts alone do not count; a paused position counts only in the months it paid).

INFORMATION ONLY, computed when served from the stored rows: nothing here is stored, and nothing moves paid to lenders,
the withholding rate, a lender or potential lender row, revenue or the payment changes. The module reads
classification records (or their serialized dicts) through `analysis.lender_payment_changes.series_positions` and
never detects a stream of its own:

* A **position** is one paying position of a lender series as the payment changes read it: the series' levels grouped
  into positions (`_positions`), fee levels and fee positions dropped (`_fee_levels`, `_paying_positions`). Two
  concurrent streams of one funder are two positions. Three readings the precision sample of 2026-10-10 asked for
  (`_counted`): a position whose every level holds 2 payments or fewer at exactly 2 or 3 times a level of another
  position of the series, which holds more payments and missed a payment before it or had one bounce it has not paid
  past (A8's premise, review rounds 1 and 2 of 2026-10-11), is that position catching up (A8's catch-up, which the
  module reads only inside a position, after A7 has formed them), so its payments are the other's; a position that
  pays only on days another pays on, a level of each adding up to the series' payment or attempt just before it began
  (the payment that was split; review round 2: never an older level or attempt; review round 3: read per stream, so
  a stream of the funder that keeps paying beside the parts at its level before them was not split and never hides
  the whole), is one payment split into two debits, one position; and a potential series' position none of whose
  payments, and not its regular weekly equivalent either, reaches A10's floor (POTENTIAL_MIN_WEEKLY_CENTS, the basis
  its one-offs are tested on) is no possible position.
* A position is **active in a period** when one of its payments is dated inside it. A payment is A2's: a posted debit
  carrying its state's paid flag (the rows paid to lenders count) with no duplicate, reversal or returned-funder-payment
  mark, so a bounced attempt never makes a position active and R3-73's re-debit is the payment it is.
* A series' payment that joins no level (A4's one-off: the only payment at its amount) is the series paying. In a
  period where none of its positions paid, such a payment makes the series ONE active position, unless it is a fee
  (under FEE_STREAM_PERCENT of the largest level of the series' paying positions or of its regular attempt, the median
  of its bounced debits) or, on a potential series, under A10's floor: a monthly payment seen once in a statement, or a
  re-debit at twice the amount in a month the regular amount never cleared, is one position, never zero; a token
  charge beside payments that all bounced is none.
* **Confirmed**: the positions of confirmed-lender series (`confirmed_lender`). **Possible**: the positions of
  potential-lender series, counted apart. Nothing else is a series, so nothing else counts.
* **Periods**: a statement's printed period (a missing bound is open). A chain (one account's statements as the
  payment changes chain them) is read once, so a stream that runs across months is the same position in each; a
  package of several accounts adds each account's positions up, and a position the payment changes link across
  accounts (R3-83's "continues from another account") counts once in a month where it is handed over: the stopped
  position paid there and the other account's position paid there only on or after the continuation (review round 1:
  a position of the other account that paid beside the stopped one is a second position in those months). Review
  round 2: one continuation takes over one stopped position at most, the nearest in amount, and two positions of one
  account are never counted as one, so a month never reads below one account's own count there. Review round 3: a
  stop the nearest amounts leave is handed over to a continuation they leave that began on or after the link's day,
  whatever its amount (a bank switch that re-priced both of a funder's positions), as A7 reads a level that follows
  another in one account.
* **N/A, never 0**, where the lender reading is not available: an account whose detection carries no
  `lender_payment_changes` (analysed before the check) or whose statement holds no rows list (`account_active_positions`);
  the package's members never analysed are N/A by webapp/app.py.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from typing import NamedTuple

from analysis.dates import parse_date
from analysis.lender_payment_changes import (
    CATCH_UP_MAX_RUN,
    CATCH_UP_MULTIPLES,
    CATCH_UP_TOLERANCE_PERCENT,
    FEE_STREAM_PERCENT,
    LEVEL_MERGE_PERCENT,
    POTENTIAL_MIN_WEEKLY_CENTS,
    PayingPosition,
    SeriesPositions,
    StatementRows,
    missed_payments,
    series_positions,
)
from analysis.payload_shape import (
    ACCOUNTS_KEY,
    DOCUMENT_SHAPE,
    PayloadShapeError,
    assert_payload_shape,
    payload_accounts,
)

_SURFACE = "analysis/active_positions.py::apply_active_positions_view"

#: The served keys: the confirmed count and, apart, the possible (potential lender) count.
ACTIVE_POSITIONS_KEY = "active_positions"
POSSIBLE_POSITIONS_KEY = "possible_positions"
#: The series state each key counts.
_COUNTED = {"confirmed": ACTIVE_POSITIONS_KEY, "potential": POSSIBLE_POSITIONS_KEY}
#: Where the lender reading is not available: N/A, never 0.
NOT_AVAILABLE = {ACTIVE_POSITIONS_KEY: None, POSSIBLE_POSITIONS_KEY: None}
#: The position number that stands for a series' one-off payments in a period none of its positions paid.
ONE_OFFS = 0
#: Review round 1 (2026-10-11): a catch-up recovers a payment of its position that bounced in this many days before it.
#: Review round 2: a split payment is one paid or attempted in this many days before its parts began.
CATCH_UP_LOOKBACK_DAYS = 31

Identity = tuple[tuple[str, str], int]


class PositionLink(NamedTuple):
    """A position the package's payment changes link across accounts (R3-83's "continues from another account"): the
    stop's chain, series key and position number, and the other chain with the first payment or attempt it reads there
    (its day and amount)."""

    chain: int
    key: tuple[str, str]
    position: int
    other_chain: int
    day: date | None
    amount: float | None


def _bounds(start: object, end: object) -> tuple[date | None, date | None]:
    return parse_date(start) if start not in (None, "") else None, parse_date(end) if end not in (None, "") else None


def _inside(day: date, start: date | None, end: date | None) -> bool:
    return (start is None or day >= start) and (end is None or day <= end)


def _payments(position: PayingPosition) -> int:
    return sum(payments for _amount, payments, _first in position.levels)


def _catch_up_multiple(amount: int, reference: int) -> bool:
    """`amount` is within CATCH_UP_TOLERANCE_PERCENT of exactly 2 or 3 times `reference` (A8's catch-up multiples)."""
    return any(100 * abs(amount - multiple * reference) <= CATCH_UP_TOLERANCE_PERCENT * amount
               for multiple in CATCH_UP_MULTIPLES)


def _near(cents: int, amount: int) -> bool:
    """`cents` is within LEVEL_MERGE_PERCENT of `amount` (A4's merge test)."""
    return 100 * abs(cents - amount) <= LEVEL_MERGE_PERCENT * amount


def _bounced_near(series: SeriesPositions, levels: Sequence[tuple[int, int, date]], since: date,
                  before: date) -> list[date]:
    """The days of the series' attempts within LEVEL_MERGE_PERCENT of one of `levels`, dated from `since` to the day
    before `before`."""
    return [day for day, cents in series.attempts
            if since <= day < before and any(_near(cents, amount) for amount, _count, _first in levels)]


def _missed_or_bounced(base: PayingPosition, position: PayingPosition, series: SeriesPositions) -> bool:
    """A8's premise (review rounds 1 and 2 of 2026-10-11): before `first`, the first payment of `position` (the level
    catching up), the `base` position missed a payment or one of its payments bounced and the base has not paid past
    it. Missed: a payment of the base's level in force (the latest one begun before `first`) scheduled after the base's
    last payment before `first` and missed before it, as the catch-up line reads it (`missed_payments`). Bounced: an
    attempt of the series within LEVEL_MERGE_PERCENT of a level of `base`, dated in the CATCH_UP_LOOKBACK_DAYS days
    before `first`, after the base's last payment before `first` (review round 2: a bounce the base paid past is no
    premise, as the catch-up line reads missed payments from the last paid presence), or before that payment where the
    catch-up amount itself (an attempt within LEVEL_MERGE_PERCENT of a level of `position`) was presented and bounced
    in those days too: the funder collecting the bounced payment as a multiple (the precision sample's catch-up shape,
    a weekly stream whose one bounce came a payment before the 2x debits, which had bounced first)."""
    first = position.days[0]
    since = first - timedelta(days=CATCH_UP_LOOKBACK_DAYS)
    paid = [day for day in base.days if day < first]
    bounces = _bounced_near(series, base.levels, since, first)
    if any(not paid or day > paid[-1] for day in bounces):
        return True
    if bounces and _bounced_near(series, position.levels, since, first):
        return True
    begun = [(level_first, cadence) for (_amount, _count, level_first), cadence in zip(base.levels, base.cadences)
             if level_first < first]
    if not paid or not begun:
        return False
    return bool(missed_payments(paid[-1], first, max(begun)[1], series.calendar))


def _catches_up(position: PayingPosition, other: PayingPosition, series: SeriesPositions) -> bool:
    """The precision sample's catch-up shape (A8): every level of `position` holds CATCH_UP_MAX_RUN payments or fewer
    at an exact catch-up multiple of a level of `other`, which holds more payments and missed or bounced a payment
    before it (`_missed_or_bounced`: A8's premise; a new stream that starts at twice another's amount beside a stream
    that paid every time is a position of its own). The module forms positions before it reads catch-ups (A7 before
    A8), so such a level, concurrent with its stream, reads as a position of its own; it is that stream catching up."""
    return _payments(other) > _payments(position) and all(
        payments <= CATCH_UP_MAX_RUN and any(_catch_up_multiple(amount, base) for base, _count, _first in other.levels)
        for amount, payments, _first in position.levels) and _missed_or_bounced(other, position, series)


def _carries_on(before: Sequence[tuple[date, int]], after: Sequence[tuple[date, int]]) -> bool:
    """Review round 3 of 2026-10-11: a position keeps paying beside the parts at the level it paid before they began:
    one of its payments on its first paying day from the parts' first day on (`after`) is within LEVEL_MERGE_PERCENT
    of one on its last paying day before it (`before`)."""
    if not before or not after:
        return False
    last, first = before[-1][0], after[0][0]
    return any(_near(cents, amount) for day, cents in after if day == first
               for other_day, amount in before if other_day == last)


def _split_wholes(position: PayingPosition, series: SeriesPositions) -> list[int]:
    """The amounts (cents) the parts of `position` may add up to (review round 2 of 2026-10-11): the series' payment or
    attempt just before `position` began, the payment that was split, never an older level or attempt. Each other
    position's payments on its last paying day before it, and the series' one-offs and attempts on the last day before
    it that one of them falls on, where no position of the series paid after that day; each dated in the
    CATCH_UP_LOOKBACK_DAYS days before `position` began. Review round 3 of 2026-10-11: read per stream, so another
    position that keeps paying beside the parts at the level it paid before they began (`_carries_on`: a daily stream
    of the same funder that carries on unchanged) was not split; it is neither a whole nor the latest payment before
    the parts, and the bounced or one-off whole just before them still counts beside it. A position whose level
    changes where the parts begin (a weekly 1,250 that becomes 1,000 and 250) is the one split."""
    first = position.days[0]
    since = first - timedelta(days=CATCH_UP_LOOKBACK_DAYS)
    wholes: list[int] = []
    latest: date | None = None
    for other in series.positions:
        before = [(day, cents) for day, cents in other.pays if day < first]
        if other.number == position.number or not before:
            continue
        if _carries_on(before, [(day, cents) for day, cents in other.pays if day >= first]):
            continue
        last = before[-1][0]
        latest = last if latest is None else max(latest, last)
        if last >= since:
            wholes.extend(cents for day, cents in before if day == last)
    loose = [(day, cents) for day, cents in (*series.one_offs, *series.attempts) if since <= day < first]
    if loose:
        last = max(day for day, _cents in loose)
        if latest is None or last >= latest:
            wholes.extend(cents for day, cents in loose if day == last)
    return wholes


def _splits(position: PayingPosition, other: PayingPosition, series: SeriesPositions) -> bool:
    """The precision sample's split shape: `position` pays only on days `other` pays on, and a level of each adds up
    (within LEVEL_MERGE_PERCENT) to the payment that was split, the series' payment or attempt just before `position`
    began (`_split_wholes`; review round 2 of 2026-10-11: never an older level, such as the other's own before a
    decrease, or an older bounced attempt, so a stream the payment changes read as a new concurrent stream stays one).
    One payment debited as two parts on the same days, which the module reads as two concurrent positions (A7), is one
    position."""
    if not set(position.days) <= set(other.days):
        return False
    wholes = _split_wholes(position, series)
    return any(100 * abs(part + rest - whole) <= LEVEL_MERGE_PERCENT * whole
               for part, _count, _day in position.levels for rest, _other_count, _other_day in other.levels
               for whole in wholes)


def _under_floor(position: PayingPosition) -> bool:
    """A10's floor on a potential position, on the basis its one-offs are tested on (review round 1 of 2026-10-11):
    neither a payment of it (its largest level amount) nor its regular weekly equivalent (`weight`) reaches
    POTENTIAL_MIN_WEEKLY_CENTS. A payment of $100 or more counts as a one-off and as a level alike, so a potential
    lender paid once a month reads the same in a statement alone (a one-off) and across a chain (a monthly level, whose
    weekly equivalent is under a quarter of its payment); a daily payee under $100 a payment counts on its week."""
    largest = max(amount for amount, _count, _first in position.levels)
    return largest < POTENTIAL_MIN_WEEKLY_CENTS and (
        position.weight is None or position.weight < POTENTIAL_MIN_WEEKLY_CENTS)


def _fee_reference(series: SeriesPositions) -> int:
    """The amount a one-off of `series` is a fee beside (under FEE_STREAM_PERCENT of it): the largest level amount of
    its paying positions or, when larger, its regular attempt, the median (the lower middle) of its bounced or reversed
    debits. Review round 1 of 2026-10-11: never its largest attempt, so a bounced catch-up or payoff attempt far larger
    than the payments never makes a cleared regular payment a fee."""
    attempts = sorted(cents for _day, cents in series.attempts)
    regular = attempts[(len(attempts) - 1) // 2] if attempts else 0
    return max(series.largest_level_cents or 0, regular)


class _Counted(NamedTuple):
    """One series as it is counted: its counted positions (number -> the days of its payments, a catch-up position's
    days joined to the position it catches up), each position number mapped to the counted one it stands for (None
    for one not counted), and the days of its one-offs that count."""

    key: tuple[str, str]
    positions: dict[int, set[date]]
    stands_for: dict[int, int | None]
    one_off_days: tuple[date, ...]


def _counted(series: SeriesPositions) -> _Counted:
    """The series' counted positions: the paying positions the module reads, less (a) a position that catches another
    up (`_catches_up`) or (b) is one part of another's payment split in two (`_splits`), whose payments are that
    position's, and (c) on a potential series, a position under A10's floor (`_under_floor`: a card purchase on a
    schedule reads as a payee, and the payment changes never report it). Its one-offs count unless they are a fee
    (under FEE_STREAM_PERCENT of `_fee_reference`, the series' largest level or its regular attempt: a token charge
    beside payments that bounced is no payment of the position) or, on a potential series, under the floor (a payment
    under POTENTIAL_MIN_WEEKLY_CENTS, the basis `_under_floor` tests a position's payments on)."""
    potential = series.key[0] == "potential"
    positions = {position.number: set(position.days) for position in series.positions}
    stands_for: dict[int, int | None] = {position.number: position.number for position in series.positions}
    for position in sorted(series.positions, key=lambda item: (_payments(item), item.number)):
        bases = [other for other in series.positions if other is not position and stands_for[other.number] == other.number
                 and (_catches_up(position, other, series)
                      or (_payments(other) >= _payments(position) and _splits(position, other, series)))]
        if bases:
            base = max(bases, key=lambda other: (_payments(other), -other.number))
            positions[base.number] |= positions.pop(position.number)
            for number, target in stands_for.items():
                if target == position.number:
                    stands_for[number] = base.number
    for position in series.positions:
        if potential and stands_for[position.number] == position.number and _under_floor(position):
            positions.pop(position.number)
            stands_for[position.number] = None
    for number, target in stands_for.items():
        if target is not None and target not in positions:
            stands_for[number] = None
    reference = _fee_reference(series)
    one_offs = tuple(day for day, cents in series.one_offs
                     if 100 * cents >= FEE_STREAM_PERCENT * reference
                     and not (potential and cents < POTENTIAL_MIN_WEEKLY_CENTS))
    return _Counted(series.key, positions, stands_for, one_offs)


class ChainPositions:
    """One chain read once (`series_positions`): its statements and every lender series' paying positions, as counted
    (`_counted`)."""

    def __init__(self, statements: Sequence[StatementRows | tuple]):
        self.statements = [item if isinstance(item, StatementRows) else StatementRows(*item) for item in statements]
        self.series = series_positions(self.statements)
        self.counted = [_counted(series) for series in self.series]

    def active(self, start: date | None, end: date | None) -> set[Identity]:
        """(series key, position number) of every counted position with a payment dated from `start` to `end` (either
        bound open when None); (series key, ONE_OFFS) for a series none of whose counted positions paid there but which
        paid a one-off that counts."""
        found: set[Identity] = set()
        for series in self.counted:
            numbers = {number for number, days in series.positions.items() if any(_inside(day, start, end) for day in days)}
            if not numbers and any(_inside(day, start, end) for day in series.one_off_days):
                numbers = {ONE_OFFS}
            found.update((series.key, number) for number in numbers)
        return found

    def statement_active(self, index: int) -> set[Identity]:
        """The positions active in the printed period of the chain's statement `index`."""
        statement = self.statements[index]
        return self.active(*_bounds(statement.period_start, statement.period_end))

    def _index(self, key: Sequence[str]) -> int | None:
        return next((number for number, item in enumerate(self.series) if item.key == tuple(key)), None)

    def counted_number(self, key: Sequence[str], number: int) -> int | None:
        """The counted position that the module's position `number` of series `key` stands for; None where it stands for
        none (a potential position under the floor) or the series is not read here."""
        index = self._index(key)
        return None if index is None else self.counted[index].stands_for.get(number)

    def days_of(self, key: Sequence[str], number: int) -> tuple[date, ...]:
        """The payment days of the counted position `number` of series `key` (its counted one-offs' for ONE_OFFS)."""
        index = self._index(key)
        if index is None:
            return ()
        counted = self.counted[index]
        return (tuple(sorted(counted.one_off_days)) if number == ONE_OFFS
                else tuple(sorted(counted.positions.get(number, ()))))

    def module_amounts(self, key: Sequence[str], number: int) -> tuple[int, ...]:
        """The level amounts (cents) of the module's position `number` of series `key` (review round 2 of 2026-10-11)."""
        index = self._index(key)
        if index is None:
            return ()
        return tuple(amount for position in self.series[index].positions if position.number == number
                     for amount, _count, _first in position.levels)

    def amounts_of(self, key: Sequence[str], number: int) -> tuple[int, ...]:
        """The level amounts (cents) of every module position the counted position `number` of series `key` stands for,
        or its counted one-offs' amounts for ONE_OFFS (review round 2 of 2026-10-11)."""
        index = self._index(key)
        if index is None:
            return ()
        series, counted = self.series[index], self.counted[index]
        if number == ONE_OFFS:
            days = set(counted.one_off_days)
            return tuple(cents for day, cents in series.one_offs if day in days)
        return tuple(amount for position in series.positions if counted.stands_for.get(position.number) == number
                     for amount, _count, _first in position.levels)

    def position_of(self, key: Sequence[str], day: date | None, amount: float | None) -> int | None:
        """The counted position of series `key` a payment or attempt on `day` belongs to: the position holding a payment
        on that day, else the first position whose first payment is on or after it (each read as the counted position it
        stands for), else ONE_OFFS where the series has no counted position but a counted one-off on that day; None
        otherwise."""
        index = self._index(key)
        if index is None or day is None:
            return None
        series, counted = self.series[index], self.counted[index]
        holding = [position.number for position in series.positions if day in position.days]
        later = sorted((position.days[0], position.number) for position in series.positions
                       if position.days and position.days[0] >= day)
        for number in [*holding, *(number for _first, number in later)]:
            if counted.stands_for.get(number) is not None:
                return counted.stands_for[number]
        if not counted.positions and day in counted.one_off_days:
            return ONE_OFFS
        return None


def _counts(states: Iterable[str]) -> dict:
    """{'active_positions': how many of `states` are 'confirmed', 'possible_positions': how many 'potential'}."""
    counted = {ACTIVE_POSITIONS_KEY: 0, POSSIBLE_POSITIONS_KEY: 0}
    for state in states:
        name = _COUNTED.get(state)
        if name is not None:
            counted[name] += 1
    return counted


def _statement_counts(reading: ChainPositions, index: int) -> dict:
    return _counts(key[0] for key, _number in reading.statement_active(index))


def chain_active_positions(statements: Sequence[StatementRows | tuple]) -> list[dict]:
    """Each statement of a chain (one account's statements in period order), in order: its confirmed and possible
    active positions over its printed period, read across the whole chain."""
    reading = ChainPositions(statements)
    return [_statement_counts(reading, index) for index in range(len(reading.statements))]


def statement_active_positions(rows: Sequence[object], *, period_start: str | date | None = None,
                               period_end: str | date | None = None, currency: str | None = None) -> dict:
    """One statement read alone: {'active_positions', 'possible_positions'} over its printed period."""
    return chain_active_positions([StatementRows(rows, period_start, period_end, currency)])[0]


def _month_label(month: int) -> str:
    """`year * 12 + month - 1` (webapp/app.py `_statement_month`) as 'YYYY-MM'."""
    return f"{month // 12:04d}-{month % 12 + 1:02d}"


class _Join(NamedTuple):
    """A link as the package reads it: the stopped node (chain, series key, counted number), the other chain, the
    counted position there the link's first payment or attempt belongs to (`position_of`; None for none), the link's
    day, the stopped position's level amounts and the link's amount (cents, None for none)."""

    stop: tuple
    other_chain: int
    named: int | None
    day: date
    stop_amounts: tuple[int, ...]
    amount: int | None


def _distance(amounts: Sequence[int], others: Sequence[int]) -> int | None:
    """The smallest gap (cents) between one of `amounts` and one of `others`; None where either is empty."""
    return min((abs(one - other) for one in amounts for other in others), default=None)


def _hand_overs(joins: Sequence[_Join], nodes: set[tuple], readings: Sequence[ChainPositions],
                spans: Mapping[int, Sequence[tuple[date | None, date | None]]]) -> list[tuple[int, int, tuple, tuple]]:
    """Review round 2 of 2026-10-11: each (pass, gap, stopped node, continuation node) a month may join, in the order
    they are tried. A continuation is a node of the link's other chain and series that paid in the month only on or
    after the link's day (`spans`: each chain's statement periods of the month). The first pass (0): the position the
    link's first payment or attempt belongs to (`named`), its gap the stopped position's level nearest the link's
    amount; or another one that began on or after the link's day at a level within LEVEL_MERGE_PERCENT of the stopped
    position's (the same stream moved, where the link names the funder's first debit there, which another stop's
    continuation took), its gap the nearest two levels. Review round 3 of 2026-10-11, the second pass (1): any other
    one that began on or after the link's day, whatever its amount, its gap the nearest two levels, so a stop the
    first pass left is handed over to a continuation it left (a bank switch that re-priced both of a funder's
    positions), as A7 reads a level that follows another in one account (it joins the position it is not concurrent
    with, whatever its amount)."""
    pairs: list[tuple[int, int, tuple, tuple]] = []
    for join in joins:
        if join.stop not in nodes:
            continue
        reading = readings[join.other_chain]
        for node in sorted(nodes):
            chain_index, key, number = node
            if chain_index != join.other_chain or key != join.stop[1]:
                continue
            days = reading.days_of(key, number)
            paid = [day for day in days if any(_inside(day, start, end) for start, end in spans[chain_index])]
            if not paid or min(paid) < join.day:
                continue
            amounts = reading.amounts_of(key, number)
            if number == join.named:
                tier, gap = 0, _distance(join.stop_amounts, (join.amount,) if join.amount is not None else amounts)
            elif days[0] >= join.day:
                tier = 0 if any(_near(one, other) or _near(other, one)
                                for one in join.stop_amounts for other in amounts) else 1
                gap = _distance(join.stop_amounts, amounts)
            else:
                continue
            pairs.append((tier, 0 if gap is None else gap, join.stop, node))
    return sorted(pairs)


def package_active_positions(chains: Sequence[Sequence[StatementRows]], *, months: Sequence[Sequence[int | None]],
                             links: Iterable[PositionLink] = (), unread_months: Iterable[int] = ()
                             ) -> tuple[list[list[dict]], list[dict]]:
    """A package's active positions: (per chain, per statement, its counts over its printed period; per month, in
    calendar order, {'month': 'YYYY-MM', 'active_positions', 'possible_positions'}).

    `months[c][i]` is the calendar month statement i of chain c stands for (`year * 12 + month - 1`, None for one that
    prints no period or whose reading is not available: it joins no month). A month's figure is every position active
    in the period of one of its statements, each chain's positions once (a series' one-offs never beside one of its
    positions), the chains added up, and a position `links` joins (the payment changes' "continues from another
    account") counted once in a month where it is handed over: the stopped position paid there (its payments all come
    on or before its last presence) and the other chain's position paid there only on or after the continuation's day.
    Review round 1 of 2026-10-11: the link holds around the hand-off only, so a position of the other account that
    paid beside the stopped one (before the continuation, in the same month or an earlier one) is a second position
    there. Review round 2 of 2026-10-11: a continuation takes over one stopped position at most and a stopped position
    is handed over once (`_hand_overs`, the nearest amounts first), and no two positions of one chain are ever counted
    as one, so a month never reads below a chain's own count there: the payment changes read every stop of a funder in
    one account as continuing from the funder's first debit in the other, so two positions that stop together and one
    continuation there are still two in the hand-off month. Review round 3 of 2026-10-11: a stop that pass leaves is
    then handed over to a continuation it leaves that began on or after the link's day, whatever its amount (a bank
    switch that re-priced both positions reads 2 in its hand-off month, not 3), as A7 reads a level that follows
    another in one account; one to one, so a consolidation and a pay-off beside a move still read 2. A month of
    `unread_months` (one of whose statements the lender reading is not available for) is N/A."""
    readings = [ChainPositions(chain) for chain in chains]
    per_statement = [[_statement_counts(reading, index) for index in range(len(reading.statements))]
                     for reading in readings]
    joins: list[_Join] = []
    for link in links:
        if link.day is None:
            continue
        key = tuple(link.key)
        one = readings[link.chain].counted_number(key, link.position)
        if one is None:
            continue
        stop_amounts = (readings[link.chain].module_amounts(key, link.position)
                        or readings[link.chain].amounts_of(key, one))
        joins.append(_Join((link.chain, key, one), link.other_chain,
                           readings[link.other_chain].position_of(key, link.day, link.amount), link.day, stop_amounts,
                           None if link.amount is None else round(abs(link.amount) * 100)))
    by_month: dict[int, dict[tuple, set[int]]] = {}
    periods: dict[int, dict[int, list[tuple[date | None, date | None]]]] = {}
    for chain_index, reading in enumerate(readings):
        for index, statement in enumerate(reading.statements):
            month = months[chain_index][index]
            if month is None:
                continue
            slot = by_month.setdefault(month, {})
            periods.setdefault(month, {}).setdefault(chain_index, []).append(
                _bounds(statement.period_start, statement.period_end))
            for key, number in reading.statement_active(index):
                slot.setdefault((chain_index, key), set()).add(number)
    unread = set(unread_months)
    result: list[dict] = []
    for month in sorted(set(by_month) | unread):
        if month in unread:
            result.append({"month": _month_label(month), **NOT_AVAILABLE})
            continue
        nodes: set[tuple] = set()
        for (chain_index, key), numbers in by_month[month].items():
            if len(numbers) > 1:
                numbers = numbers - {ONE_OFFS}
            nodes.update((chain_index, key, number) for number in numbers)
        parent: dict[tuple, tuple] = {}
        held: dict[tuple, set[int]] = {node: {node[0]} for node in nodes}

        def root(node: tuple) -> tuple:
            while parent.get(node, node) != node:
                node = parent[node]
            return node

        stopped: set[tuple] = set()
        continued: set[tuple] = set()
        for _tier, _gap, stop, node in _hand_overs(joins, nodes, readings, periods[month]):
            if stop in stopped or node in continued:
                continue
            first, second = root(stop), root(node)
            if first == second or held[first] & held[second]:
                continue
            kept, joined = min(first, second), max(first, second)
            parent[joined] = kept
            held[kept] |= held.pop(joined)
            stopped.add(stop)
            continued.add(node)
        groups = {root(node) for node in nodes}
        result.append({"month": _month_label(month), **_counts(key[0] for _chain, key, _number in groups)})
    return per_statement, result


def account_active_positions(account: Mapping) -> dict:
    """One ACCOUNT payload's {'active_positions', 'possible_positions'}, read alone over its printed period from its
    stored rows' classification records; N/A (None, None) where the lender reading is not available: its detection
    carries no `lender_payment_changes` list (analysed before the check) or its statement no rows list."""
    statement = account.get("statement")
    detection = account.get("detection")
    if (not isinstance(statement, Mapping) or not isinstance(statement.get("transactions"), list)
            or not isinstance(detection, Mapping) or not isinstance(detection.get("lender_payment_changes"), list)):
        return dict(NOT_AVAILABLE)
    rows = [row["classification"] for row in statement["transactions"]
            if isinstance(row, Mapping) and isinstance(row.get("classification"), Mapping)]
    return statement_active_positions(rows, period_start=statement.get("period_start"),
                                      period_end=statement.get("period_end"), currency=statement.get("currency"))


def _view_account(account: object) -> object:
    if not isinstance(account, Mapping) or not isinstance(account.get("metrics"), Mapping):
        return account
    return {**account, "metrics": {**account["metrics"], **account_active_positions(account)}}


def apply_active_positions_view(payload: object) -> object:
    """A copy of a published analysis payload whose every account's metrics carry `active_positions` and
    `possible_positions` (computed when served, never stored). The input is never mutated; a payload of neither
    published shape is returned as it is."""
    try:
        shape = assert_payload_shape(payload, surface=_SURFACE)
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    if shape == DOCUMENT_SHAPE:
        return {**payload, ACCOUNTS_KEY: [_view_account(account) for account in accounts]}
    return _view_account(payload)

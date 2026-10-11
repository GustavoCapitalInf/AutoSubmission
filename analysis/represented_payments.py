"""Re-presented returned funder payments: the owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once
(Recommended)"; true revenue spec §6.2 pass 7c and the package passes, §11, §17.1, §19.1; audit round 3, R3-B02).

The owner's ruling of 2026-10-02 on the underwriter's Q5 keeps a confirmed funder's payment the bank returned unpaid in
the withholding numerator, "the obligation standing" (R2-OW13). Once the same funder re-debits that payment, the paid
re-debit already counts the obligation, so the returned attempt would count it twice. The owner's answer: a returned
payment LEAVES the withholding numerator once the same funder re-debits it,

* the same cents OFF its cycle, dated on or after the return and within one cadence gap after it (a re-presentment), or
* an exact 2x debit dated on or after the return and within one cadence gap after it (a catch-up, which covers the
  bounced payment once); since audit round 4, R4-75 (the owner's "Count it once" for the shapes his option text, "a 2x
  catch-up", did not foresee; its question's default (a)), an exact 2x to 6x debit that pays several bounced payments
  covers each of them once (step 3);

until such a re-debit exists the returned attempt stays in the numerator exactly as Q5 rules. Paid to lenders, the
lender count and revenue do not move: only the numerator (and the rate), by exactly the matched attempts.

This module reads neutral rows only (`Attempt`, `Returned`), so the classifier (one statement, pass 7c) and the package
(across a member boundary) apply one rule. It reads no description and writes nothing.

The rule, per returned payment R (its funder E, its cents c, its return dated C), in (return date, R's order) order:

1. The series: E's dated attempts (paid payments and returned attempts) at c cents and at a companion's cents, 2c for a
   same-cents or a 2c candidate and k*c for a k*c candidate (k in CATCH_UP_MULTIPLES, audit round 4, R4-75), the
   re-debits already taken left out (a multiple keeps its own date while it has capacity left). Its schedule is
   `payment_cadence` of the series' dates (a same-cents candidate's own date left out;
   daily_irregular read as daily), else, where 2c debits off the cycle blur it, of its c-cent dates alone; each read
   only on MIN_SCHEDULE_DATES distinct dates or more (two dates a fortnight apart read biweekly whatever the series is);
   irregular, single or no schedule reads nothing. Audit round 4, R4-01: the c-cent dates alone are also preferred
   where the series' dates read daily but they read weekly, biweekly, semi-monthly or monthly (a second position's 2x
   payments on a nearby weekday blur a weekly 1x series into a daily one, which skipped step 3's level windows).
2. A same-cents candidate X (c cents, dated on or after C and after R, at most one cycle after C) is a re-presentment
   when the schedule is weekly, biweekly or monthly and X is OFF its cycle: the schedule's phase (the weekday of a
   weekly or biweekly series, the day of the month of a monthly one) that the most attempts of the series keep, within
   CYCLE_TOLERANCE_DAYS, held by more than half of them and by no clearly other phase as many, is more than
   CYCLE_TOLERANCE_DAYS from X's, and X's own phase is no recurring one: fewer than RECURRING_PHASE_ANCHORS other
   attempts of the series keep it, or every one of them follows another return of the series within one cycle (two
   or more, one of them following no return, are a twice-weekly schedule or a second position at the same cents,
   whose next payment cannot be told from a re-presentment; review round 1 of R3-B02; attempts that each follow
   another return are that return's re-presentments, a funder re-presenting every bounce on one weekday, no schedule;
   review round 2 of R3-B02). A daily or semi-monthly schedule reads no same-cents re-debit: every business day is a
   daily series' cycle, and a second debit on one day (or on the payment's own day) cannot be told from two positions.
3. A multiple candidate X (exactly k*c cents for k in CATCH_UP_MULTIPLES, 2 to 6; before audit round 4, R4-75, only
   2c; dated on or after C and after R) is a catch-up of R when (the window and the run, R4-75) it is at most one cycle
   after the return of L (one business day on a daily schedule), L the latest standing returned payment of the series
   (its c-cent returned payments still in the numerator, not yet re-debited, paid before X and returned on or before
   X), and R is L or an earlier standing one whose payment is dated at most k-1 cycles (daily: k-1 business days)
   before L's (for one bounce, R is L: one cycle after C); when (the capacity, R4-75) X covers fewer returned payments
   than k, and than k-1 where X stands in for that day's own payment (`_stands_in`: on a weekly, biweekly or monthly
   schedule X keeps the series' phase, on a daily one it falls on a business day, and no other attempt of the series at
   c cents is dated X's day; where no phase can be read, semi-monthly, k-1), so a 2x on the cycle with no regular
   payment beside it covers one bounce, as before, and an off-cycle 2x after two bounces covers both; and when (the
   levels, read at X's cents) E has fewer than LEVEL_ATTEMPTS attempts at X's cents (X included) within one
   cycle of it, and at least a week, and (a schedule other than daily) fewer than LEVEL_ATTEMPTS - 1 2c attempts
   cycle of it, and at least a week, and (a schedule other than daily) fewer than LEVEL_ATTEMPTS - 1 2c attempts
   within LEVEL_WINDOW_CYCLES cycles after it and fewer than LEVEL_ATTEMPTS - 1 within LEVEL_WINDOW_CYCLES cycles
   before it, on the series' cycle or not, the re-debits already taken left out (a 2c level of its own is not a
   catch-up: a step-up or a second position that starts with X, review round 1 of R3-B02, on another weekday too, or
   one that ran before X and whose next payment falls past the statement's end or never comes, review round 2 of
   R3-B02). Audit round 4, R4-01, on any schedule: X is no catch-up either where it is the regular payment of a 2c
   stream of its own (`_keeps_its_own_stream`): E's 2c attempts not yet taken as re-debits (X included) span
   MIN_SCHEDULE_DATES distinct dates or more and read weekly, biweekly, semi-monthly or monthly, X keeps that stream's
   phase, and RECURRING_PHASE_ANCHORS or more other attempts of the stream keep X's phase, one of which follows no other
   return of the series within one of the stream's cycles (a second position's payment at the stream's edge, or a
   biweekly second position, which the level count and windows miss; alternating catch-ups that each follow a return
   stay catch-ups). The level windows and the stream read X's own cents (2c above stands for them).
4. The earliest qualifying candidate (date, then order) is taken. A same-cents re-debit covers one returned payment; a
   multiple covers as many as its capacity, the returns read in (return date, order) order, so it covers the earliest
   qualifying bounces first (a run longer than its capacity leaves the latest standing).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from .lender_payment_changes import business_days_between, payment_cadence

#: The kind of re-debit that took a returned payment out of the withholding numerator.
RE_PRESENTED = "re_presented"
CAUGHT_UP = "caught_up"
#: Audit round 4, R4-75: the exact multiples of the payment a catch-up may be (R3-25's, the lender payment changes'
#: CATCH_UP_PRESENCE_MULTIPLES; exact cents here, pass 7c's own tolerance, where the payment changes allow 2%).
CATCH_UP_MULTIPLES = (2, 3, 4, 5, 6)
#: One cycle of each schedule, in calendar days: a re-debit's window after the return.
CYCLE_DAYS = {"weekly": 7, "biweekly": 14, "semimonthly": 16, "monthly": 31}
#: The days a payment may stand from its schedule's phase and still keep it (a weekend or holiday shift). A weekly and a
#: biweekly series keep a weekday; a monthly one a day of the month.
CYCLE_TOLERANCE_DAYS = {"weekly": 1, "biweekly": 1, "monthly": 3}
#: A daily schedule's catch-up is at most this many business days after the return.
DAILY_CATCH_UP_BUSINESS_DAYS = 1
#: A 2c candidate with LEVEL_ATTEMPTS or more 2c attempts of the funder (itself included) within this many calendar
#: days of it is a level of its own, a second position, not a catch-up (a daily series: a week; any other: its cycle,
#: and at least a week).
DAILY_LEVEL_DAYS = 7
LEVEL_ATTEMPTS = 3
#: The series dates a schedule is read from (the candidate's own date left out where it is the same cents): fewer read
#: nothing, since two dates a fortnight apart read biweekly whatever the series is.
MIN_SCHEDULE_DATES = 3
#: A same-cents candidate whose own phase (within CYCLE_TOLERANCE_DAYS) this many other attempts of the series keep is
#: on a second recurring phase, a twice-weekly schedule or a second position at the same cents, which cannot be told
#: from a re-presentment: no re-debit (review round 1 of R3-B02). One of them must follow no other return of the
#: series within one cycle: attempts that each follow another return are that return's re-presentments, no schedule
#: (review round 2 of R3-B02).
RECURRING_PHASE_ANCHORS = 2
#: A 2c candidate with LEVEL_ATTEMPTS - 1 or more 2c attempts of the funder within LEVEL_WINDOW_CYCLES cycles (and the
#: schedule's tolerance) after it, or as many before it, on the series' cycle or not (a re-debit already taken left
#: out), is a level of its own (a renewal or a modified payment that starts with it, or a second position, running on
#: or ended), not a catch-up (review rounds 1 and 2 of R3-B02); a daily schedule's level is read within
#: DAILY_LEVEL_DAYS of the candidate.
LEVEL_WINDOW_CYCLES = 2
#: Audit round 4, R4-01: the schedules a 2c stream of its own reads (step 3's stream guard), and the slower schedules
#: the c-cent dates alone may read that step 1 prefers over a daily reading of the series' dates.
STREAM_SCHEDULES = ("weekly", "biweekly", "semimonthly", "monthly")


@dataclass(frozen=True)
class Attempt:
    """One dated, posted, non-duplicate debit of a confirmed funder: a paid payment or a returned attempt. `key`
    identifies it to the caller; `order` sorts it among the rows of one day (the row, or the member and the row)."""

    key: Hashable
    entity: str
    day: date
    cents: int
    order: tuple


@dataclass(frozen=True)
class Returned:
    """A returned payment still in the withholding numerator, and the date of the credit that returned it."""

    attempt: Attempt
    returned_on: date


def catch_up_multiple(payment_cents: int, re_debit_cents: int) -> int | None:
    """Audit round 4, R4-75: the k of CATCH_UP_MULTIPLES whose k times the payment's cents the re-debit's cents are
    exactly (a catch-up's multiple), else None (a same-cents re-debit is a re-presentment)."""
    if payment_cents <= 0:
        return None
    multiple, rest = divmod(re_debit_cents, payment_cents)
    return multiple if rest == 0 and multiple in CATCH_UP_MULTIPLES else None


def out_of_rate_payment(returned_funder_payment_by: object, contributes_to_withholding_rate: object) -> bool:
    """Audit round 3, final review (R3-FF), F3: a PAID attempt (no return took it) that the withholding rate leaves out,
    today exactly R3-79's worded lump-sum payoff (`lump_sum_payoff`, out of the rate, in paid to lenders). It is never a
    returned payment's re-debit: the returned attempt would leave the numerator by R3-73 beside the payoff leaving it by
    R3-79, so the bounced obligation would count zero times. It stays an attempt of the series (its schedule and its 2x
    level read it). A returned attempt is never one, whatever its rate: a re-presentment that bounced again, and was
    re-debited in its turn, still re-presents the payment before it."""
    return not returned_funder_payment_by and contributes_to_withholding_rate is not True


def _schedule(days: Sequence[date], calendar: str) -> str | None:
    cadence = payment_cadence(days, calendar)
    cadence = "daily" if cadence == "daily_irregular" else cadence
    return cadence if cadence in ("daily", "weekly", "biweekly", "semimonthly", "monthly") else None


def _read(days: Sequence[date], calendar: str) -> str | None:
    """The schedule of `days`, read only on MIN_SCHEDULE_DATES distinct dates or more (step 1)."""
    return _schedule(days, calendar) if len(set(days)) >= MIN_SCHEDULE_DATES else None


def _series_schedule(series_days: list[date], single_days: list[date], calendar: str) -> tuple[str | None, list[date]]:
    """Step 1: (the schedule, the dates it was read from): the series' dates; the c-cent dates alone where those read
    nothing; and, audit round 4, R4-01 (the round-3 reviewer's sketch of R3-B02's review round 3), the c-cent dates alone
    where the series' dates read daily but those read a slower schedule (STREAM_SCHEDULES): a 1x weekly position and a
    2x second position on a nearby weekday read daily together, which skipped step 3's level windows, and a weekly
    series is no daily one (so its same-cents re-presentment is read too)."""
    together = _read(series_days, calendar)
    if together is not None and together != "daily":
        return together, series_days
    alone = _read(single_days, calendar)
    if together is None:
        return (alone, single_days) if alone is not None else (None, [])
    if alone in STREAM_SCHEDULES:
        return alone, single_days
    return together, series_days


def _phase(day: date, schedule: str) -> tuple[int, int]:
    """(phase, modulus) of a day in its schedule: the weekday (a weekly or biweekly series), or the day of the month."""
    if schedule in ("weekly", "biweekly"):
        return day.toordinal() % 7, 7
    return day.day, 31


def _distance(first: int, second: int, modulus: int) -> int:
    gap = abs(first - second) % modulus
    return min(gap, modulus - gap)


def _cycle(anchors: Sequence[date], schedule: str) -> tuple[set[int], int, int] | None:
    """The phase the anchors keep (step 2): (its leading phases, the modulus, the tolerance), or None where the
    schedule has no tolerance or no phase is clear (held by more than half of the anchors, no other as many)."""
    tolerance = CYCLE_TOLERANCE_DAYS.get(schedule)
    if tolerance is None or not anchors:
        return None
    phases = [_phase(day, schedule) for day in anchors]
    modulus = phases[0][1]
    kept = Counter()
    for phase, _ in phases:
        kept[phase] = sum(1 for other, _ in phases if _distance(phase, other, modulus) <= tolerance)
    best = max(kept.values())
    leaders = {phase for phase, count in kept.items() if count == best}
    # Leaders within the tolerance of each other are one phase; two apart are no clear phase.
    if any(_distance(one, other, modulus) > 2 * tolerance for one in leaders for other in leaders):
        return None
    if best * 2 <= len(anchors):
        return None
    return leaders, modulus, tolerance


def _on_cycle(day: date, cycle: tuple[set[int], int, int], schedule: str) -> bool:
    leaders, modulus, tolerance = cycle
    phase = _phase(day, schedule)[0]
    return any(_distance(phase, leader, modulus) <= tolerance for leader in leaders)


def _follows_a_return(day: date, other_returns: Sequence[tuple[date, date]], schedule: str) -> bool:
    """Whether `day` could be the re-debit of another return of the series: dated after that payment, on or after its
    return and at most one cycle after it (step 2's window)."""
    return any(paid < day and returned_on <= day and (day - returned_on).days <= CYCLE_DAYS[schedule]
               for paid, returned_on in other_returns)


def _off_cycle(candidate: date, anchors: Sequence[date], schedule: str,
               other_returns: Sequence[tuple[date, date]] = ()) -> bool:
    """Whether `candidate` is off the phase the anchors keep (step 2); False where no phase is clear, and False where
    the candidate's own phase is a recurring one (RECURRING_PHASE_ANCHORS or more anchors keep it, one of them following
    none of `other_returns`, the series' other returned payments as (payment's date, return's date))."""
    cycle = _cycle(anchors, schedule)
    if cycle is None:
        return False
    _leaders, modulus, tolerance = cycle
    phase = _phase(candidate, schedule)[0]
    # Review round 1 of R3-B02: a phase other attempts of the series keep is a second recurring phase (a twice-weekly
    # schedule, or a second position at the same cents), whose next payment is its own schedule's, never a re-debit.
    # Review round 2: unless every one of them follows another return of the series within one cycle, each then that
    # return's re-presentment (a funder re-presenting every bounce on one weekday), no schedule.
    keeping = [day for day in anchors if _distance(_phase(day, schedule)[0], phase, modulus) <= tolerance]
    if len(keeping) >= RECURRING_PHASE_ANCHORS and not all(
            _follows_a_return(day, other_returns, schedule) for day in keeping):
        return False
    return not _on_cycle(candidate, cycle, schedule)


def _keeps_its_own_stream(candidate: Attempt, family: Sequence[Attempt], used: Mapping[Hashable, int],
                          other_returns: Sequence[tuple[date, date]], calendar: str) -> bool:
    """Step 3's stream guard (audit round 4, R4-01; the owner's answer of 2026-10-07 to R3-73, "Count it once": only a
    real re-debit takes a bounce out): whether the multiple candidate is the regular payment of a stream of its own at
    its cents. The series' attempts at the candidate's cents not yet taken as re-debits (`used`; the candidate included)
    span MIN_SCHEDULE_DATES distinct dates or more and read a STREAM_SCHEDULES schedule; the candidate keeps the stream's
    phase (`_cycle` of its dates; a semi-monthly stream's days of the month are its phase, which every date of such a
    reading keeps); and RECURRING_PHASE_ANCHORS or more other attempts of the stream keep the candidate's phase, one of
    them following no other return of the series within one of the stream's cycles (`_follows_a_return`, `other_returns`
    the series' other returned payments as (payment's date, return's date)). Attempts that each follow another return
    are that return's catch-ups (alternating bounces each caught up the next cycle), no stream."""
    stream = [attempt for attempt in family if attempt.cents == candidate.cents
              and (attempt.key == candidate.key or not used.get(attempt.key))]
    days = sorted({attempt.day for attempt in stream})
    schedule = _read(days, calendar)
    if schedule not in STREAM_SCHEDULES:
        return False
    others = [attempt.day for attempt in stream if attempt.key != candidate.key]
    if schedule == "semimonthly":
        keeping = others
    else:
        cycle = _cycle(days, schedule)
        if cycle is None or not _on_cycle(candidate.day, cycle, schedule):
            return False
        _leaders, modulus, tolerance = cycle
        phase = _phase(candidate.day, schedule)[0]
        keeping = [day for day in others if _distance(_phase(day, schedule)[0], phase, modulus) <= tolerance]
    return len(keeping) >= RECURRING_PHASE_ANCHORS and not all(
        _follows_a_return(day, other_returns, schedule) for day in keeping)


def _within(start: date, day: date, schedule: str, calendar: str, cycles: int = 1) -> bool:
    """`day` is at most `cycles` cycles of `schedule` after `start` (on a daily schedule DAILY_CATCH_UP_BUSINESS_DAYS
    business days where `cycles` is 1, else `cycles` business days; on another, CYCLE_DAYS calendar days each)."""
    if schedule == "daily":
        limit = DAILY_CATCH_UP_BUSINESS_DAYS if cycles == 1 else cycles
        return business_days_between(start, day, calendar) <= limit
    return (day - start).days <= cycles * CYCLE_DAYS[schedule]


def _stands_in(candidate: Attempt, family: Sequence[Attempt], payment_cents: int, anchors: Sequence[date],
               schedule: str, calendar: str) -> bool:
    """Step 3's capacity (audit round 4, R4-75): whether a multiple candidate stands in for its own day's payment, so it
    covers k-1 returned payments, not k: no other attempt of the series at the payment's cents is dated its day, and on
    a weekly, biweekly or monthly schedule it keeps the series' phase (`_cycle` of the schedule's anchors), on a daily
    one it falls on a business day; where no phase can be read (a semi-monthly schedule, or no clear phase) it stands
    in (the conservative side: it covers k-1)."""
    if any(attempt.day == candidate.day and attempt.cents == payment_cents for attempt in family):
        return False
    if schedule == "daily":
        return business_days_between(date.fromordinal(candidate.day.toordinal() - 1), candidate.day, calendar) == 1
    cycle = _cycle(anchors, schedule)
    return cycle is None or _on_cycle(candidate.day, cycle, schedule)


def re_debits(
    returned: Sequence[Returned],
    attempts: Sequence[Attempt],
    calendar: str = "US",
    *,
    may_re_debit: Callable[[Returned, Attempt], bool] | None = None,
    taken: Sequence[Hashable] | Mapping[Hashable, int] = (),
    returns: Sequence[Returned] | None = None,
    standing: Sequence[Returned] | None = None,
) -> dict[Hashable, tuple[Hashable, str]]:
    """{returned attempt's key: (its re-debit's key, RE_PRESENTED or CAUGHT_UP)} for every returned payment the same
    funder re-debited (the module's rule). `attempts` holds every dated attempt of the funders (the returned ones
    included); `may_re_debit` narrows the candidates of a returned payment (the package: another member); `taken` are
    re-debits already taken elsewhere (a statement's own reading), each key listed once per returned payment it covers
    or given as a mapping key -> count (audit round 4, R4-75: a multiple covers several); `returns` are every returned
    payment the caller knows, the re-debited ones included, which step 2's recurring-phase guard reads (`returned` where
    not given); `standing` are the returned payments still in the numerator that step 3's run reads its latest bounce L
    from (`returned` where not given; the package passes its members' own, R4-75), the ones re-debited here left out.
    A multiple's kind is CAUGHT_UP; its k is `catch_up_multiple` of the two cents."""
    used: Counter = Counter(taken)
    known_returns = list(returned) if returns is None else list(returns)
    pending = list(returned) if standing is None else list(standing)
    found: dict[Hashable, tuple[Hashable, str]] = {}
    for item in sorted(returned, key=lambda entry: (entry.returned_on, entry.attempt.order)):
        payment, returned_on = item.attempt, item.returned_on
        if returned_on < payment.day:
            continue
        # Audit round 4, R4-75: the candidates are the payment's cents and its exact 2x to 6x multiples.
        multiples = {multiple * payment.cents: multiple for multiple in CATCH_UP_MULTIPLES}
        family = [attempt for attempt in attempts
                  if attempt.entity == payment.entity and attempt.key != payment.key
                  and (attempt.cents == payment.cents or attempt.cents in multiples)]
        # The series' other returned payments at the same cents (step 2: an attempt following one is its re-debit).
        other_returns = [(entry.attempt.day, entry.returned_on) for entry in known_returns
                         if entry.attempt.entity == payment.entity and entry.attempt.cents == payment.cents
                         and entry.attempt.key != payment.key]
        # Step 3's run (R4-75): the series' returned payments still standing, R included.
        series_standing = [entry for entry in pending
                           if entry.attempt.entity == payment.entity and entry.attempt.cents == payment.cents
                           and entry.attempt.key not in found and entry.attempt.key != payment.key
                           and entry.returned_on >= entry.attempt.day] + [item]
        for candidate in sorted(family, key=lambda attempt: (attempt.day, attempt.order)):
            same_cents = candidate.cents == payment.cents
            multiple = 1 if same_cents else multiples[candidate.cents]
            if (used[candidate.key] >= multiple or candidate.day < returned_on or candidate.day <= payment.day
                    or (may_re_debit is not None and not may_re_debit(item, candidate))):
                continue
            companion = 2 * payment.cents if same_cents else candidate.cents
            pool = [attempt for attempt in family if attempt.cents in (payment.cents, companion)
                    and (not used[attempt.key] or (attempt.key == candidate.key and not same_cents))
                    and (attempt.key != candidate.key or not same_cents)]
            # The schedule of the series at c and its companion's cents, else (multiples off the cycle can blur it) at c
            # cents alone; audit round 4, R4-01: the c cents alone also where the series reads daily but they read a
            # slower schedule.
            schedule, anchors = _series_schedule(
                [payment.day] + [attempt.day for attempt in pool],
                [payment.day] + [attempt.day for attempt in pool if attempt.cents == payment.cents], calendar)
            if schedule is None:
                continue
            if same_cents:
                if not _within(returned_on, candidate.day, schedule, calendar):
                    continue
                if not _off_cycle(candidate.day, anchors, schedule, other_returns):
                    continue
                kind = RE_PRESENTED
            else:
                # R4-75's window and run: one cycle after the latest standing bounce's return, R no more than k-1
                # cycles before it (for one bounce, R itself: one cycle after its return, as before).
                latest = max((entry for entry in series_standing
                              if entry.attempt.day < candidate.day and entry.returned_on <= candidate.day),
                             key=lambda entry: (entry.returned_on, entry.attempt.order))
                if not _within(latest.returned_on, candidate.day, schedule, calendar):
                    continue
                if latest is not item and not _within(payment.day, latest.attempt.day, schedule, calendar,
                                                      cycles=multiple - 1):
                    continue
                # R4-75's capacity: k returned payments, k-1 where the multiple stands in for its day's own payment.
                capacity = multiple - 1 if _stands_in(candidate, family, payment.cents, anchors, schedule,
                                                      calendar) else multiple
                if used[candidate.key] >= capacity:
                    continue
                level_days = DAILY_LEVEL_DAYS if schedule == "daily" else max(DAILY_LEVEL_DAYS, CYCLE_DAYS[schedule])
                if sum(1 for attempt in family if attempt.cents == candidate.cents
                       and abs((attempt.day - candidate.day).days) <= level_days) >= LEVEL_ATTEMPTS:
                    continue
                # A 2c level that starts with the candidate (a step-up right after the bounce, review round 1 of
                # R3-B02) shows only after it, and one that ran before it (its next payment past the statement's end,
                # or none) only before it; a second position's level keeps its own weekday, so every 2c attempt counts,
                # on the series' cycle or not, but a re-debit already taken (another bounce's catch-up) is no level
                # payment (review round 2 of R3-B02).
                if schedule != "daily":
                    window = LEVEL_WINDOW_CYCLES * CYCLE_DAYS[schedule] + CYCLE_TOLERANCE_DAYS.get(schedule, 1)
                    gaps = [(attempt.day - candidate.day).days for attempt in family
                            if attempt.cents == candidate.cents and not used[attempt.key]]
                    if (sum(1 for gap in gaps if 0 < gap <= window) >= LEVEL_ATTEMPTS - 1
                            or sum(1 for gap in gaps if 0 < -gap <= window) >= LEVEL_ATTEMPTS - 1):
                        continue
                # Audit round 4, R4-01: on any schedule, a 2c stream's own regular payment is no catch-up (at the
                # stream's edge, where the level count and windows see too few of its payments, or a biweekly stream).
                if _keeps_its_own_stream(candidate, family, used, other_returns, calendar):
                    continue
                kind = CAUGHT_UP
            used[candidate.key] += 1
            found[payment.key] = (candidate.key, kind)
            break
    return found

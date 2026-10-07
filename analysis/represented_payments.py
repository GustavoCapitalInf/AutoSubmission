"""Re-presented returned funder payments: the owner's answer of 2026-10-07 to audit round 3's R3-73 ("Count it once
(Recommended)"; true revenue spec §6.2 pass 7c and the package passes, §11, §17.1, §19.1; audit round 3, R3-B02).

The owner's ruling of 2026-10-02 on the underwriter's Q5 keeps a confirmed funder's payment the bank returned unpaid in
the withholding numerator, "the obligation standing" (R2-OW13). Once the same funder re-debits that payment, the paid
re-debit already counts the obligation, so the returned attempt would count it twice. The owner's answer: a returned
payment LEAVES the withholding numerator once the same funder re-debits it,

* the same cents OFF its cycle, dated on or after the return and within one cadence gap after it (a re-presentment), or
* an exact 2x debit dated on or after the return and within one cadence gap after it (a catch-up, which covers the
  bounced payment once);

until such a re-debit exists the returned attempt stays in the numerator exactly as Q5 rules. Paid to lenders, the
lender count and revenue do not move: only the numerator (and the rate), by exactly the matched attempts.

This module reads neutral rows only (`Attempt`, `Returned`), so the classifier (one statement, pass 7c) and the package
(across a member boundary) apply one rule. It reads no description and writes nothing.

The rule, per returned payment R (its funder E, its cents c, its return dated C), in (return date, R's order) order:

1. The series: E's dated attempts (paid payments and returned attempts) at c or 2c cents, the re-debits already taken
   left out. Its schedule is `payment_cadence` of the series' dates (a same-cents candidate's own date left out;
   daily_irregular read as daily), else, where 2c debits off the cycle blur it, of its c-cent dates alone; each read
   only on MIN_SCHEDULE_DATES distinct dates or more (two dates a fortnight apart read biweekly whatever the series is);
   irregular, single or no schedule reads nothing.
2. A same-cents candidate X (c cents, dated on or after C and after R, at most one cycle after C) is a re-presentment
   when the schedule is weekly, biweekly or monthly and X is OFF its cycle: the schedule's phase (the weekday of a
   weekly or biweekly series, the day of the month of a monthly one) that the most attempts of the series keep, within
   CYCLE_TOLERANCE_DAYS, held by more than half of them and by no clearly other phase as many, is more than
   CYCLE_TOLERANCE_DAYS from X's. A daily or semi-monthly schedule reads no same-cents re-debit: every business day is
   a daily series' cycle, and a second debit on one day (or on the payment's own day) cannot be told from two positions.
3. A 2x candidate X (exactly 2c cents, dated on or after C and after R) is a catch-up when it is at most one cycle after C
   (one business day on a daily schedule) and E has fewer than LEVEL_ATTEMPTS 2c attempts (X included) within one
   cycle of it, and at least a week (a 2c level of its own is a second position, not a catch-up).
4. The earliest qualifying candidate (date, then order) is taken; each re-debit covers one returned payment.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from datetime import date

from .lender_payment_changes import business_days_between, payment_cadence

#: The kind of re-debit that took a returned payment out of the withholding numerator.
RE_PRESENTED = "re_presented"
CAUGHT_UP = "caught_up"
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


def _schedule(days: Sequence[date], calendar: str) -> str | None:
    cadence = payment_cadence(days, calendar)
    cadence = "daily" if cadence == "daily_irregular" else cadence
    return cadence if cadence in ("daily", "weekly", "biweekly", "semimonthly", "monthly") else None


def _phase(day: date, schedule: str) -> tuple[int, int]:
    """(phase, modulus) of a day in its schedule: the weekday (a weekly or biweekly series), or the day of the month."""
    if schedule in ("weekly", "biweekly"):
        return day.toordinal() % 7, 7
    return day.day, 31


def _distance(first: int, second: int, modulus: int) -> int:
    gap = abs(first - second) % modulus
    return min(gap, modulus - gap)


def _off_cycle(candidate: date, anchors: Sequence[date], schedule: str) -> bool:
    """Whether `candidate` is off the phase the anchors keep (step 2); False where no phase is clear."""
    tolerance = CYCLE_TOLERANCE_DAYS.get(schedule)
    if tolerance is None or not anchors:
        return False
    phases = [_phase(day, schedule) for day in anchors]
    modulus = phases[0][1]
    kept = Counter()
    for phase, _ in phases:
        kept[phase] = sum(1 for other, _ in phases if _distance(phase, other, modulus) <= tolerance)
    best = max(kept.values())
    leaders = {phase for phase, count in kept.items() if count == best}
    # Leaders within the tolerance of each other are one phase; two apart are no clear phase.
    if any(_distance(one, other, modulus) > 2 * tolerance for one in leaders for other in leaders):
        return False
    if best * 2 <= len(anchors):
        return False
    phase = _phase(candidate, schedule)[0]
    return all(_distance(phase, leader, modulus) > tolerance for leader in leaders)


def re_debits(
    returned: Sequence[Returned],
    attempts: Sequence[Attempt],
    calendar: str = "US",
    *,
    may_re_debit: Callable[[Returned, Attempt], bool] | None = None,
    taken: Sequence[Hashable] = (),
) -> dict[Hashable, tuple[Hashable, str]]:
    """{returned attempt's key: (its re-debit's key, RE_PRESENTED or CAUGHT_UP)} for every returned payment the same
    funder re-debited (the module's rule). `attempts` holds every dated attempt of the funders (the returned ones
    included); `may_re_debit` narrows the candidates of a returned payment (the package: another member); `taken` are
    re-debits already taken elsewhere (a statement's own reading)."""
    used: set[Hashable] = set(taken)
    found: dict[Hashable, tuple[Hashable, str]] = {}
    for item in sorted(returned, key=lambda entry: (entry.returned_on, entry.attempt.order)):
        payment, returned_on = item.attempt, item.returned_on
        if returned_on < payment.day:
            continue
        family = [attempt for attempt in attempts
                  if attempt.entity == payment.entity and attempt.key != payment.key
                  and attempt.cents in (payment.cents, 2 * payment.cents)]
        for candidate in sorted(family, key=lambda attempt: (attempt.day, attempt.order)):
            if (candidate.key in used or candidate.day < returned_on or candidate.day <= payment.day
                    or (may_re_debit is not None and not may_re_debit(item, candidate))):
                continue
            same_cents = candidate.cents == payment.cents
            pool = [attempt for attempt in family if attempt.key not in used
                    and (attempt.key != candidate.key or not same_cents)]
            # The schedule of the series at c and 2c cents, else (2c debits off the cycle can blur it) at c cents alone.
            schedule, anchors = None, []
            for dates in ([payment.day] + [attempt.day for attempt in pool],
                          [payment.day] + [attempt.day for attempt in pool if attempt.cents == payment.cents]):
                if len(set(dates)) >= MIN_SCHEDULE_DATES and (read := _schedule(dates, calendar)) is not None:
                    schedule, anchors = read, dates
                    break
            if schedule is None:
                continue
            if schedule == "daily":
                within = business_days_between(returned_on, candidate.day, calendar) <= DAILY_CATCH_UP_BUSINESS_DAYS
            else:
                within = (candidate.day - returned_on).days <= CYCLE_DAYS[schedule]
            if not within:
                continue
            if same_cents:
                if not _off_cycle(candidate.day, anchors, schedule):
                    continue
                kind = RE_PRESENTED
            else:
                level_days = DAILY_LEVEL_DAYS if schedule == "daily" else max(DAILY_LEVEL_DAYS, CYCLE_DAYS[schedule])
                if sum(1 for attempt in family if attempt.cents == candidate.cents
                       and abs((attempt.day - candidate.day).days) <= level_days) >= LEVEL_ATTEMPTS:
                    continue
                kind = CAUGHT_UP
            used.add(candidate.key)
            found[payment.key] = (candidate.key, kind)
            break
    return found

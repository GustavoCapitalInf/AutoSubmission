"""Days and months as the package reads statement periods."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP


_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def iso_day(value: object):
    """A `YYYY-MM-DD` day, or None for anything else (an impossible date included), as app.js isoDay reads it."""
    from datetime import date

    match = _ISO_DAY.fullmatch(str(value or ""))
    if not match:
        return None
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return None


def statement_month(period_start: object, period_end: object) -> int | None:
    """The calendar month a statement stands for, as `year * 12 + month - 1`: the month holding most of its period's
    days, the earlier on a tie (app.js statementMonth, the Monthly Statements table's rule). A statement running
    2031-03-02 to 2031-04-01 is March 2031. None when neither day reads."""
    from datetime import timedelta

    start, end = iso_day(period_start), iso_day(period_end)
    if start is None and end is None:
        return None
    if start is None or end is None or end < start:
        day = start or end
        return day.year * 12 + day.month - 1
    days: dict[int, int] = {}
    day, counted = start, 0
    while day <= end and counted < 400:
        key = day.year * 12 + day.month - 1
        days[key] = days.get(key, 0) + 1
        day += timedelta(days=1)
        counted += 1
    return max(days.items(), key=lambda item: (item[1], -item[0]))[0]


#: The days of an average calendar month (365.25 / 12), the unit the days an account's statements cover are read
#: in.
_AVERAGE_MONTH_DAYS = Decimal("30.4375")


def covered_days(period_start: object, period_end: object) -> set:
    """The days a statement's printed period covers, its first and last included; empty unless both days read and
    the end is not before the start; at most 400 days, as `statement_month` reads."""
    from datetime import timedelta

    start, end = iso_day(period_start), iso_day(period_end)
    if start is None or end is None or end < start:
        return set()
    days, day = set(), start
    while day <= end and len(days) < 400:
        days.add(day)
        day += timedelta(days=1)
    return days


def months_covered(days: int) -> int:
    """A count of days as whole calendar months, half up (90 days are 3, 59 are 2, 45 are 1)."""
    return int((Decimal(days) / _AVERAGE_MONTH_DAYS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

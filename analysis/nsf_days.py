"""The underwriting NSF count: negative-ending days, on one of two bases.

R18 (Gustavo, 2026-09-18) made the underwriting NSF count the number of days
that end with a negative balance in the validated daily ledger. The ledger is
calendar-day: a day with no activity carries the previous day's ending balance
forward (``DailyBalance.source == "carried"``), which the ADB doctrine needs.

Owner ruling, 2026-09-22: the NSF count defaults to PRINTED days, the days
whose ending balance the statement itself establishes (a posting day, or a day
the bank printed in its daily balance table). A carried day is not counted:

    03-10 ends -10 (activity), 03-11 no activity, 03-12 ends +20
    printed basis: 1 negative day; carry-over basis: 2 (03-11 carries -10)

The carry-over basis (R18 as first built) is kept as an option, chosen in the
web app's Settings page. The ADB and the ledger itself are unchanged by either.

Owner request, 2026-09-27 ("Two chips"): the served metrics also list the days
the count counts, ``metrics.nsf_days``, so the dashboard's NSFs chip shows
exactly the tile's days. Each day is shown by the posting that ended it: the
day's last posting in statement order, or for a day with no posting (a carried
day, a bank-printed balance) the last posting before it. In the example above,
both carried-basis days are shown by the posting of the 10th.
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from datetime import date, datetime

from analysis.dates import parse_date
from analysis.payload_shape import ACCOUNTS_KEY, PayloadShapeError, is_document_payload, payload_accounts

_SURFACE = "analysis/nsf_days.py::apply_nsf_basis_to_payload"
#: The printed-day basis, the default.
PRINTED = "negative_printed_days"
#: The carry-over basis: every calendar day, inactive days carrying the previous balance.
CARRIED = "negative_ending_days"
#: No validated ledger: the count is not computable on either basis.
UNAVAILABLE = "negative_ending_days_unavailable"

LABELS = {
    PRINTED: "Negative-ending days (printed days only)",
    CARRIED: "Negative-ending days (balance carried over inactive days)",
    UNAVAILABLE: "Not computable: no validated daily ledger",
}


def _field(day: object, name: str):
    return day.get(name) if isinstance(day, Mapping) else getattr(day, name, None)


def negative_day_count(daily_balances: Iterable, *, carry_over: bool) -> int:
    """Days ending below zero. Without ``carry_over``, carried (inactive) days are not counted.

    Accepts ledger entries as objects (``analysis.adb.DailyBalance``) or as their serialized dicts."""
    count = 0
    for day in daily_balances:
        if not carry_over and _field(day, "source") == "carried":
            continue
        balance = _field(day, "ending_balance")
        if isinstance(balance, (int, float)) and not isinstance(balance, bool) and balance < 0:
            count += 1
    return count


def apply_nsf_basis(metrics: Mapping, *, carry_over: bool) -> dict:
    """A copy of serialized metrics whose ``effective_nsf_count`` and ``nsf_source`` follow the chosen basis.

    Only a negative-day count is re-based; an unavailable count, or any other source, is returned as is.
    The count comes from the payload's own fields, or for a payload written before the printed basis
    existed, from its validated ledger. With neither, the payload keeps the count it was written with,
    under its own label, rather than show a figure it cannot support."""
    result = dict(metrics)
    if result.get("nsf_source") not in (PRINTED, CARRIED):
        return result
    field = "negative_days" if carry_over else "negative_printed_days"
    count = result.get(field)
    if not isinstance(count, int) or isinstance(count, bool):
        ledger = (result.get("adb") or {}).get("daily_balances") if isinstance(result.get("adb"), Mapping) else None
        if not ledger:
            return result
        count = negative_day_count(ledger, carry_over=carry_over)
    result["effective_nsf_count"] = count
    result["nsf_source"] = CARRIED if carry_over else PRINTED
    return result


def _day(value: object) -> date | None:
    """A ledger or posting date as a plain calendar day, or None when it is not one."""
    try:
        parsed = parse_date(value) if isinstance(value, (str, date)) else None
    except (TypeError, ValueError):
        return None
    if isinstance(parsed, datetime):
        return parsed.date()
    return parsed


def _postings(transactions: object) -> list[tuple[date, int, str]]:
    """Every dated posting as (day, statement position, source location), in ledger order: by day, then as printed.

    A posting is named by its classification's ``source_location``, else by its position (``transaction:<n>``, the
    name the classifier gives it). A row that is not a posting, or has no date, is left out."""
    if not isinstance(transactions, (list, tuple)):
        return []
    postings = []
    for position, row in enumerate(transactions):
        if not isinstance(row, Mapping):
            continue
        day = _day(row.get("date"))
        if day is None:
            continue
        record = row.get("classification")
        location = record.get("source_location") if isinstance(record, Mapping) else None
        if not isinstance(location, str) or not location.strip():
            location = f"transaction:{position + 1}"
        postings.append((day, position, location))
    postings.sort(key=lambda posting: (posting[0], posting[1]))
    return postings


def list_negative_days(daily_balances: object, transactions: object, *, carry_over: bool) -> list[dict]:
    """The days ``negative_day_count`` counts, each with the posting that ended it.

    Each day is ``{"date", "ending_balance", "source", "source_location"}``: the source is the ledger day's own
    (``reconstructed``, ``bank_daily_summary`` or ``carried``), and the location names the day's last posting in
    statement order, or for a day with no posting the last posting before it (None when the statement has no
    posting on or before that day). A day that went below zero during the day but ended at or above zero is not
    listed. A malformed ledger lists no day; this never raises."""
    if not isinstance(daily_balances, (list, tuple)):
        return []
    postings = _postings(transactions)
    posting_days = [posting[0] for posting in postings]
    listed = []
    for entry in daily_balances:
        if not carry_over and _field(entry, "source") == "carried":
            continue
        balance = _field(entry, "ending_balance")
        if not (isinstance(balance, (int, float)) and not isinstance(balance, bool) and balance < 0):
            continue
        day = _day(_field(entry, "date"))
        if day is None:
            return []  # a counted day with no date: the ledger is malformed, and no day of it is listed
        ended_by = bisect_right(posting_days, day)
        source = _field(entry, "source")
        listed.append({
            "date": day.isoformat(),
            "ending_balance": float(balance),
            "source": source if isinstance(source, str) else None,
            "source_location": postings[ended_by - 1][2] if ended_by else None,
        })
    return listed


def _listed_days(metrics: Mapping, statement: object) -> list[dict]:
    """``metrics.nsf_days``: the days ``effective_nsf_count`` counts on the basis in force (``nsf_source``).

    Empty when the count is not a negative-day count (unavailable, or a result saved before R18), and when the ledger
    cannot list exactly the days the count counts: a list of another length is never published."""
    source = metrics.get("nsf_source")
    if source not in (PRINTED, CARRIED):
        return []
    adb = metrics.get("adb")
    ledger = adb.get("daily_balances") if isinstance(adb, Mapping) else None
    transactions = statement.get("transactions") if isinstance(statement, Mapping) else None
    days = list_negative_days(ledger, transactions, carry_over=source == CARRIED)
    count = metrics.get("effective_nsf_count")
    if not isinstance(count, int) or isinstance(count, bool) or len(days) != count:
        return []
    return days


def _rebased_account(account: Mapping, *, carry_over: bool, list_days: bool) -> dict:
    result = dict(account)
    if isinstance(result.get("metrics"), Mapping):
        metrics = apply_nsf_basis(result["metrics"], carry_over=carry_over)
        if list_days:
            metrics["nsf_days"] = _listed_days(metrics, result.get("statement"))
        result["metrics"] = metrics
    return result


def apply_nsf_basis_to_payload(payload: object, *, carry_over: bool, list_days: bool = True) -> object:
    """A copy of a published analysis payload with every account's metrics re-based: the account shape, or
    each account of the document shape (analysis/payload_shape.py). The input is never mutated.

    With ``list_days`` (the dashboard), each account's metrics also list the days the count counts
    (``nsf_days``); the exports leave it out, so a download carries exactly what it carried before.

    A presentation step, so it never refuses: anything that is not a well-formed payload (no analysis, a
    malformed document) is returned unchanged, for the readers that refuse it to refuse it."""
    if not isinstance(payload, Mapping):
        return payload
    if not is_document_payload(payload):
        return _rebased_account(payload, carry_over=carry_over, list_days=list_days)
    try:
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    return {**payload, ACCOUNTS_KEY: [_rebased_account(account, carry_over=carry_over, list_days=list_days)
                                     for account in accounts]}

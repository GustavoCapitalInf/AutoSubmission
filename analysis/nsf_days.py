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
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

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


def _rebased_account(account: Mapping, *, carry_over: bool) -> dict:
    result = dict(account)
    if isinstance(result.get("metrics"), Mapping):
        result["metrics"] = apply_nsf_basis(result["metrics"], carry_over=carry_over)
    return result


def apply_nsf_basis_to_payload(payload: object, *, carry_over: bool) -> object:
    """A copy of a published analysis payload with every account's metrics re-based: the account shape, or
    each account of the document shape (analysis/payload_shape.py). The input is never mutated.

    A presentation step, so it never refuses: anything that is not a well-formed payload (no analysis, a
    malformed document) is returned unchanged, for the readers that refuse it to refuse it."""
    if not isinstance(payload, Mapping):
        return payload
    if not is_document_payload(payload):
        return _rebased_account(payload, carry_over=carry_over)
    try:
        accounts = payload_accounts(payload, surface=_SURFACE)
    except PayloadShapeError:
        return payload
    return {**payload, ACCOUNTS_KEY: [_rebased_account(account, carry_over=carry_over) for account in accounts]}

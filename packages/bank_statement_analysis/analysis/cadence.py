"""The rhythm of a flagged payee's payments (lender-detection design, spec §6).

`describe_cadence` names a payee's debit rhythm for display: the Flagged
positions panel, its exports and the package roll-up. It is deliberately
separate from `classification.record.classify_cadence`, whose daily/weekly
answer gates potential-lender promotion and must not move.
"""
from __future__ import annotations

from datetime import date
from statistics import mean, pstdev
from typing import Sequence


def describe_cadence(dates: Sequence[date]) -> tuple[str, float | None]:
    """One of daily, weekly, biweekly, monthly, irregular or single, and the mean gap.

    Dates are de-duplicated and sorted first. One distinct date is `single`
    with no gap. The mean gap is in days, rounded to one decimal.
    """
    ordered = sorted(set(dates))
    if len(ordered) < 2:
        return "single", None
    gaps = [(later - earlier).days for earlier, later in zip(ordered, ordered[1:])]
    average = mean(gaps)
    spread = pstdev(gaps) if len(gaps) > 1 else 0.0
    rounded = round(float(average), 1)
    if average <= 1.6 and spread <= 1.5:
        return "daily", rounded
    if 5 <= average <= 9 and spread <= 2.5:
        return "weekly", rounded
    if 12 <= average <= 16 and spread <= 3:
        return "biweekly", rounded
    if 26 <= average <= 35 and spread <= 5:
        return "monthly", rounded
    return "irregular", rounded

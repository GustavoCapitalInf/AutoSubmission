from __future__ import annotations

from datetime import date

import pytest

from analysis.cadence import describe_cadence
from analysis.classification.record import classify_cadence


def _days(*isos: str) -> list[date]:
    return [date.fromisoformat(value) for value in isos]


@pytest.mark.parametrize(
    ("dates", "expected"),
    [
        ([], ("single", None)),
        (_days("2054-01-05"), ("single", None)),
        (_days("2054-01-05", "2054-01-05"), ("single", None)),
        (_days("2054-01-05", "2054-01-06", "2054-01-07", "2054-01-08", "2054-01-09"), ("daily", 1.0)),
        (_days("2054-01-05", "2054-01-12", "2054-01-19", "2054-01-26"), ("weekly", 7.0)),
        (_days("2054-01-19", "2054-01-05", "2054-01-12"), ("weekly", 7.0)),
        (_days("2054-01-01", "2054-01-15", "2054-01-29"), ("biweekly", 14.0)),
        (_days("2054-01-15", "2054-02-15", "2054-03-15"), ("monthly", 29.5)),
        (_days("2054-01-05", "2054-02-04"), ("monthly", 30.0)),
        (_days("2054-01-01", "2054-01-03", "2054-01-20"), ("irregular", 9.5)),
    ],
)
def test_describe_cadence_names_the_rhythm_of_a_payees_dates(dates, expected):
    assert describe_cadence(dates) == expected


def test_the_promotion_cadence_is_unchanged_for_a_monthly_series():
    # classify_cadence gates potential-lender promotion (daily/weekly only) and must not move.
    assert classify_cadence(_days("2054-01-15", "2054-02-15", "2054-03-15")) == ("irregular", 29.5)

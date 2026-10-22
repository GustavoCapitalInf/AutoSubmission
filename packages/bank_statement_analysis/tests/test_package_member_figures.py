"""A package reads each member once and adds what it read to its sums, member after member. Every job it reads stays as
it was, and a second read of the same jobs gives the same package. Each monthly row is that member's documents row, so
the active positions set after the members reach both. Each sum adds a member's figure to the running total and rounds
it to the cent before the next member; the funder and insurer roll-ups add each detection match the same way, and the
days-weighted ADB is a decimal mean rounded half up. Fabricated statements of CONTOSO BAKERY LLC, 2031."""
from __future__ import annotations

import copy

import pytest

from tests.test_active_positions import three_months
from tests.test_package_matching import (
    _account_a,
    _account_b,
    _owners_example,
    _rows_a,
    _rows_b,
    _two_account_document,
)
from tests.test_webapp_true_revenue import DETECTED_ROWS, _payload


def _jobs(*payloads, failed: bool = False):
    from webapp.jobs import Job

    jobs = [Job(id=f"job-{index}", filename=f"statement-{index}.pdf", status="done", analysis=payload,
                content_sha256=f"job-{index}") for index, payload in enumerate(payloads, start=1)]
    if failed:
        jobs.append(Job(id="job-failed", filename="failed.pdf", status="error", analysis=None, error="fabricated"))
    return jobs


def _package(jobs):
    from analysis.package import package_analysis

    return package_analysis(jobs, settings={})


def _with_metrics(payload: dict, **metrics) -> dict:
    payload = copy.deepcopy(payload)
    payload["metrics"].update(metrics)
    return payload


def _month(payload: dict, month: int) -> dict:
    payload = copy.deepcopy(payload)
    payload["statement"]["period_start"] = f"2031-{month:02d}-01"
    payload["statement"]["period_end"] = f"2031-{month:02d}-28"
    return payload


SCENARIOS = {
    # Pass 1 overlays April's rows: a March deposit returned in April.
    "returned_deposit": lambda: _owners_example(),
    # R-d's designated pair inside one document leaves both accounts' contributions.
    "internal_transfer_pair": lambda: (_two_account_document(_rows_a("ONLINE TRANSFER TO CHK 2020"),
                                                             _rows_b("ONLINE TRANSFER FROM CHK 1010")),),
    # Pass 2 moves B's counted deposit out of its basis.
    "own_account_transfer": lambda: (_account_a(), _account_b()),
    # Known funders, insurers and potential lenders, with a Zelle reading on the second month.
    "detections": lambda: (_payload(DETECTED_ROWS), _month(_payload(DETECTED_ROWS), 4)),
    # Lender chains whose active positions are set on the member rows.
    "lender_chain": three_months,
}


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_a_package_leaves_the_jobs_it_reads_as_it_found_them(scenario):
    jobs = _jobs(*SCENARIOS[scenario](), failed=True)
    stored = [copy.deepcopy(job.analysis) for job in jobs]
    first = _package(jobs)
    assert [job.analysis for job in jobs] == stored
    assert _package(jobs) == first


def test_each_monthly_row_is_its_members_documents_row():
    package = _package(_jobs(*three_months(), failed=True))
    documents = {id(row): row for row in package["documents"]}
    assert [row["id"] for row in package["documents"]] == ["job-1", "job-2", "job-3", "job-failed"]
    assert [row["id"] for row in package["monthly"]] == ["job-1", "job-2", "job-3"]
    assert all(id(row) in documents for row in package["monthly"])
    # Set on the documents rows after the members are added, and read on the monthly rows.
    assert [row["active_positions"] for row in package["monthly"]] == [1, 2, 2]


def test_every_package_sum_is_rounded_after_each_member():
    # 0.005, 0.015 and 0.025 add to 0.06 rounded after each member, 0.04 rounded once, and 0.05 with each member's
    # figure rounded before it is added.
    base = _payload(DETECTED_ROWS)
    payloads = [_month(_with_metrics(base, effective_total_deposits=figure, effective_total_withdrawals=figure,
                                     cash_flow=figure, withholding_denominator=figure), month)
                for month, figure in ((3, 0.005), (4, 0.015), (5, 0.025))]
    totals = _package(_jobs(*payloads))["totals"]
    assert (totals["total_credits"], totals["total_debits"], totals["cash_flow"],
            totals["withholding_denominator"]) == (0.06, 0.06, 0.06, 0.06)


def test_the_funder_and_insurer_roll_ups_round_after_each_match():
    # Four matches of 0.005 add to 0.01 rounded after each, 0.02 rounded once, and 0.04 each rounded first.
    base = _payload(DETECTED_ROWS)
    funder = {**base["detection"]["known_funders"][0], "total_debited": 0.005, "returned_payment_total": 0.005}
    insurer = {**base["detection"]["insurance_providers"][0], "total_debited": 0.005}
    payloads = []
    for month in (3, 4):
        payload = _month(base, month)
        payload["detection"]["known_funders"] = [funder, funder]
        payload["detection"]["insurance_providers"] = [insurer, insurer]
        payloads.append(payload)
    package = _package(_jobs(*payloads))
    [rolled_funder] = package["funders"]
    [rolled_insurer] = package["insurance_providers"]
    assert (rolled_funder["documents"], rolled_funder["total_debited"], rolled_funder["returned_payment_total"]) == (
        4, 0.01, 0.01)
    assert (rolled_insurer["documents"], rolled_insurer["total_debited"]) == (4, 0.01)


def test_the_package_adb_is_a_decimal_days_weighted_mean_rounded_half_up():
    # 1.005 is 1.00499999999999989... as a float; the decimal mean of its text rounds half up to 1.01.
    base = _payload(DETECTED_ROWS)
    package = _package(_jobs(_with_metrics(base, average_daily_balance=1.005, calendar_day_count=1, adb_ok=True)))
    assert round(1.005, 2) == 1.0
    assert package["totals"]["average_daily_balance"] == 1.01
    weighted = _package(_jobs(_with_metrics(base, average_daily_balance=1.0, calendar_day_count=3, adb_ok=True),
                              _month(_with_metrics(base, average_daily_balance=2.0, calendar_day_count=1, adb_ok=True),
                                     4)))
    assert weighted["totals"]["average_daily_balance"] == 1.25

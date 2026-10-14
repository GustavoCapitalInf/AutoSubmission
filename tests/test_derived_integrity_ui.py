"""The dashboard's integrity fallback reads the sum check as the server does (the audit's final review, finding 4).

`derivedIntegrity` (webapp/static/app.js) rebuilds an integrity block for a payload stored without one. It flagged
`ledger_sum_mismatch` only above one DOLLAR and knew nothing of a sum check that could not run, the two rules audit
REC-4 changed on the server (`analysis/pipeline.py::assess_document_integrity`): the flag fires above the sum check's
own tolerance (`analysis/reconcile.py::SUM_CHECK_TOLERANCE`, one cent), and a failed reconciliation with no sum delta
is `ledger_sum_uncheckable`. A report carrying its own integrity block is shown as it is, as before.

The whole app.js runs in node on the fake page (tests/webapp_js_harness.py). Fabricated statements only: neutral
figures, the year 2054.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict

import pytest

from tests.webapp_js_harness import APP_JS, NODE, run_dashboard

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

LEDGER_FLAGS = ("ledger_sum_mismatch", "ledger_sum_uncheckable")


def _derived(reports: list[dict]) -> list[dict]:
    return run_dashboard(f"console.log(JSON.stringify({json.dumps(reports)}.map((r) => derivedIntegrity(r))));")


@pytest.mark.parametrize("delta, flags, risk", [
    (0.0, [], "clear"),
    (0.01, [], "clear"),
    (-0.01, [], "clear"),
    (0.02, ["ledger_sum_mismatch"], "review"),
    (-0.5, ["ledger_sum_mismatch"], "review"),
    (1.0, ["ledger_sum_mismatch"], "review"),
    (1.01, ["ledger_sum_mismatch"], "review"),
    ("0.02", ["ledger_sum_mismatch"], "review"),
])
def test_the_fallback_flags_a_sum_mismatch_above_one_cent(delta, flags, risk):
    [integrity] = _derived([{"reconciliation": {"ok": abs(float(delta)) <= 0.01, "sum_delta": delta}}])
    assert integrity["flags"] == flags
    assert integrity["risk_level"] == risk
    assert integrity["possible_document_issue"] is False


@pytest.mark.parametrize("reconciliation", [
    {"ok": False, "sum_delta": None},
    {"ok": False},
])
def test_the_fallback_knows_a_sum_check_that_could_not_run(reconciliation):
    [integrity] = _derived([{"reconciliation": reconciliation}])
    assert integrity["flags"] == ["ledger_sum_uncheckable"]
    assert integrity["risk_level"] == "review"


@pytest.mark.parametrize("report", [
    {"reconciliation": {"ok": True, "sum_delta": None}},  # a hand-built reconciliation that passed (as the server)
    {"reconciliation": {}},
    {},
])
def test_no_sum_check_flag_where_the_server_raises_none(report):
    [integrity] = _derived([report])
    assert integrity["flags"] == [] and integrity["risk_level"] == "clear"


def test_a_report_carrying_its_own_integrity_block_is_shown_as_it_is():
    own = {"risk_level": "clear", "flags": [], "notes": [], "possible_document_issue": False}
    [integrity] = _derived([{"integrity": own, "reconciliation": {"ok": False, "sum_delta": 5.0}}])
    assert integrity == own


def test_the_other_rules_are_unchanged():
    [summary, breaks, many_breaks] = _derived([
        {"reconciliation": {"ok": False, "summary_ok": False, "sum_delta": 0.0}},
        {"reconciliation": {"ok": False, "sum_delta": 0.0, "continuity_breaks": 1}},
        {"reconciliation": {"ok": False, "sum_delta": 2.0, "continuity_breaks": 3}},
    ])
    assert summary["flags"] == ["summary_math_inconsistent"] and summary["risk_level"] == "high"
    assert breaks["flags"] == ["running_balance_breaks"] and breaks["risk_level"] == "review"
    assert many_breaks["flags"] == ["ledger_sum_mismatch", "running_balance_breaks"]
    assert many_breaks["risk_level"] == "high" and many_breaks["possible_document_issue"] is True


def test_the_fallback_reads_the_server_s_tolerance():
    from analysis.reconcile import SUM_CHECK_TOLERANCE

    [value] = re.findall(r"^const SUM_CHECK_TOLERANCE = ([0-9.]+);", APP_JS, re.MULTILINE)
    assert float(value) == SUM_CHECK_TOLERANCE


def _server_case(*, credit: float = 75.0, beginning: float | None = 100.0, ending: float | None = 150.0):
    from analysis.pipeline import assess_document_integrity, assess_quality
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    def txn(day: str, amount: float) -> Transaction:
        return Transaction(date=day, description="DEPOSIT" if amount > 0 else "WITHDRAWAL", amount=amount,
                           direction="credit" if amount > 0 else "debit")

    stmt = Statement(bank="SAMPLE BANK", period_start="2054-01-01", period_end="2054-01-31",
                     beginning_balance=beginning, ending_balance=ending,
                     transactions=[txn("2054-01-05", credit), txn("2054-01-10", -25.0)])
    recon = reconcile(stmt)
    quality = assess_quality(stmt, recon)
    integrity = assess_document_integrity(stmt, recon, quality)
    report = {"reconciliation": asdict(recon), "quality": asdict(quality)}
    return report, integrity


def test_the_fallback_agrees_with_the_server_on_the_sum_check():
    """The same fabricated statements through the server's integrity block and through the fallback (the payload's
    reconciliation and quality blocks, its integrity block left out): the same sum-check flag and the same risk."""
    cases = [_server_case(credit=credit) for credit in (75.0, 75.01, 75.02, 75.5, 76.0, 76.01)]
    cases += [_server_case(beginning=None), _server_case(ending=None)]
    derived = _derived([report for report, _ in cases])
    seen = set()
    for (_, server), fallback in zip(cases, derived):
        assert [f for f in fallback["flags"] if f in LEDGER_FLAGS] == [f for f in server.flags if f in LEDGER_FLAGS]
        assert fallback["risk_level"] == server.risk_level
        seen.update(f for f in server.flags if f in LEDGER_FLAGS)
        seen.add(server.risk_level)
    assert seen == {"ledger_sum_mismatch", "ledger_sum_uncheckable", "clear", "review"}

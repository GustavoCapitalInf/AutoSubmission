"""A failed sum check is never published as integrity "clear" (audit 2026-10-13 REC-4).

`analysis/reconcile.py` fails the sum check (beginning + rows == ending) at
more than one cent, and when the beginning or ending balance is missing. The
integrity block flagged `ledger_sum_mismatch` only above ONE DOLLAR and had no
flag at all for a sum check that could not run, so a document whose
reconciliation had failed could publish `risk_level: clear` with an empty flag
list (its outcome was still withheld, because a failed reconciliation never
publishes an ADB). Every other kind of reconcile issue already carried a flag
at reconcile's own threshold; the sum check was the one exception.

Fabricated statements only: neutral figures, the year 2054.
"""
from __future__ import annotations

import pytest

from analysis.pipeline import assess_document_integrity, assess_quality
from analysis.reconcile import SUM_CHECK_TOLERANCE, ReconResult, reconcile
from analysis.schema import Statement, Transaction


def _txn(day: str, amount: float) -> Transaction:
    return Transaction(
        date=day, description="DEPOSIT" if amount > 0 else "WITHDRAWAL", amount=amount,
        direction="credit" if amount > 0 else "debit",
    )


def _statement(*, beginning: float | None = 100.0, ending: float | None = 150.0,
               credit: float = 75.0) -> Statement:
    """No stated totals and no running balances: the sum check is the only
    identity this statement can be held to."""
    return Statement(
        bank="SAMPLE BANK", period_start="2054-01-01", period_end="2054-01-31",
        beginning_balance=beginning, ending_balance=ending,
        transactions=[_txn("2054-01-05", credit), _txn("2054-01-10", -25.0)],
    )


def _integrity(stmt: Statement):
    recon = reconcile(stmt)
    return recon, assess_document_integrity(stmt, recon, assess_quality(stmt, recon))


@pytest.mark.parametrize("credit", [75.02, 75.50, 75.99, 76.00])
def test_a_sum_check_reconcile_fails_is_flagged_whatever_its_size(credit):
    recon, integrity = _integrity(_statement(credit=credit))
    assert recon.ok is False
    assert integrity.flags == ["ledger_sum_mismatch"]
    assert integrity.risk_level == "review"


def test_the_flag_still_fires_above_a_dollar_as_it_always_did():
    recon, integrity = _integrity(_statement(credit=76.50))
    assert integrity.flags == ["ledger_sum_mismatch"]
    assert integrity.risk_level == "review"


def test_the_threshold_is_reconciles_own():
    """Not a restated constant: the integrity flag and the sum check are the
    same comparison, so a statement either reconciles or carries the flag."""
    assert SUM_CHECK_TOLERANCE == 0.01
    recon, integrity = _integrity(_statement(credit=75.01))   # off by exactly the tolerance
    assert recon.ok is True
    assert integrity.flags == [] and integrity.risk_level == "clear"


@pytest.mark.parametrize("missing", ["beginning", "ending"])
def test_a_sum_check_that_could_not_run_is_flagged(missing):
    stmt = _statement(**{missing: None})
    recon, integrity = _integrity(stmt)
    assert recon.ok is False and recon.sum_delta is None
    assert integrity.flags == ["ledger_sum_uncheckable"]
    assert integrity.risk_level == "review"
    assert any("sum check could not run" in note for note in integrity.notes)


def test_a_reconciled_statement_stays_clear():
    recon, integrity = _integrity(_statement())
    assert recon.ok is True
    assert integrity.flags == [] and integrity.risk_level == "clear"


def test_a_hand_built_reconciliation_that_passed_raises_no_uncheckable_flag():
    """The flag needs the reconciliation to have FAILED as well as lacking a
    delta, so a caller's own passing ReconResult (the worker tests build one)
    is not flagged."""
    stmt = _statement(beginning=None)
    recon = ReconResult(ok=True)
    integrity = assess_document_integrity(stmt, recon, assess_quality(stmt, recon))
    assert "ledger_sum_uncheckable" not in integrity.flags


def test_the_note_carries_no_figure():
    _, integrity = _integrity(_statement(beginning=None))
    note = next(n for n in integrity.notes if "sum check could not run" in n)
    assert not any(ch.isdigit() for ch in note)


def test_the_outcome_class_does_not_move():
    """Withheld outranks flags: a failed reconciliation never publishes an ADB,
    so the document stays withheld and only its integrity block changes."""
    from analysis.config import load_settings
    from analysis.pipeline import _account_report
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    for stmt in (_statement(credit=75.50), _statement(beginning=None)):
        recon = reconcile(stmt)
        report = _account_report(
            stmt, recon, dispatch=None, settings=load_settings(), markdown="",
            source_markdown="", sheets=(), repair_failure=None,
            model_used="sample-deterministic", escalated=False,
        )
        payload = report_to_dict(report)
        assert payload["metrics"]["adb_ok"] is False
        assert classify_outcome(payload)[0] == "withheld"
        assert payload["integrity"]["risk_level"] == "review"

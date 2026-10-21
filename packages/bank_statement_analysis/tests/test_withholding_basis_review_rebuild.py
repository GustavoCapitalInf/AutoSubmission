"""Audit round 3, R3-B03 (R3-13; true revenue spec §9.1, §10.7, §11): a review decision refreshes everything the
withholding basis feeds.

`_rebuild_account_revenue_views` recomputed the statement's basis, rate, potential exposure and review flag on a True
or Verified basis after a Confirm or a Reject, but never each potential lender's `eligible_deposit_denominator` and
`potential_withholding_exposure` (set once by `detect`) nor the "unavailable" notes (written once by `compute_metrics`).
Since R2-OW14 made True the default basis, every Confirm or Reject moves it, so the lender row and the downloads
contradicted the card: a Reject that lowered True left the row understating the position's burden, a Reject to $0 left
the row publishing its old exposure on a basis that no longer exists, and a Confirm lifting a $0 statement published a
rate beside "unavailable" notes. The rebuild now refreshes each potential lender's row and the basis notes too, with
R3-20's floor.

Fabricated statements only (CONTOSO TILE LLC at Sample Bank, March 2054: FABRIKAM SUPPLY sales, held INCOMING WIRE
TRANSFER credits (`wire_no_sender`), KAPITUS its confirmed funder, NORTHWIND FUNDING WEB PMT a weekly potential payee,
a ZELLE FROM SAMPLE PERSON deposit where the readings must differ; neutral amounts), analysed by the real per-account
path and reviewed through `zelle_view.with_both_readings(shown=True)`, as the /revenue-review route writes."""
from __future__ import annotations

import copy
import json

import pytest

KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO TILE LLC CO ID:0000000002 CCD"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO TILE LLC CO ID:0000000001 CCD"
WIRE = "INCOMING WIRE TRANSFER"
POTENTIAL = "NORTHWIND FUNDING WEB PMT"
ZELLE = "ZELLE FROM SAMPLE PERSON ON 03/22 REF # 0001"
UNAVAILABLE = ("withholding rate is unavailable because ", "potential withholding exposure is unavailable because ")


def _stored(monkeypatch, credits, *, mode="true_revenue"):
    """One month of CONTOSO TILE LLC with `credits` ((day, description, amount) rows), four KAPITUS payments of 700.00
    and five NORTHWIND FUNDING payments of 750.00 (3,750.00), as its stored payload."""
    from analysis import pipeline
    from analysis.config import load_settings
    from analysis.pipeline import DocumentReport
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction
    from analysis.serialization import document_report_to_dict

    monkeypatch.setenv("WITHHOLDING_DENOMINATOR_MODE", mode)
    rows = list(credits) + [(day, KAPITUS, -700.0) for day in (5, 12, 19, 26)]
    rows += [(day, POTENTIAL, -750.0) for day in (3, 10, 17, 24, 31)]
    rows.sort(key=lambda row: row[0])
    balance, transactions = 40000.0, []
    for day, text, amount in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                                        direction="credit" if amount > 0 else "debit", running_balance=balance))
    statement = Statement(
        bank="Sample Bank", account_name="CONTOSO TILE LLC", account_number="000000002020",
        period_start="2054-03-01", period_end="2054-03-31", beginning_balance=40000.0, ending_balance=balance,
        currency="USD", currency_source="printed",
        stated_total_credits=round(sum(t.amount for t in transactions if t.amount > 0), 2),
        stated_total_debits=round(-sum(t.amount for t in transactions if t.amount < 0), 2),
        transactions=transactions,
    )
    report = pipeline._account_report(
        statement, reconcile(statement), dispatch=None, settings=load_settings(), markdown="", source_markdown="",
        sheets=[], repair_failure=None, model_used="fabricated-test", escalated=False,
    )
    return document_report_to_dict(DocumentReport(accounts=[report]))


def _served(payload, zelle=True):
    from analysis.served_view import displayed
    return displayed(copy.deepcopy(payload), settings={"zelle_true_revenue": zelle})


def _review(stored, decisions, shown=True):
    from analysis import zelle_view
    return zelle_view.with_both_readings(copy.deepcopy(stored), shown=shown, decisions=decisions)


def _location(stored, description, amount):
    (location,) = [row["classification"]["source_location"] for row in stored["statement"]["transactions"]
                   if row["description"] == description and row["amount"] == amount]
    return location


def _row(served):
    (lender,) = served["detection"]["potential_lenders"]
    assert lender["funder"] == "Northwind Funding" and lender["total_debited"] == 3750.0
    return lender["eligible_deposit_denominator"], lender["potential_withholding_exposure"]


def _basis_notes(metrics):
    return [note for note in metrics["notes"] if note.startswith(UNAVAILABLE)]


def _export_cells(served):
    from webapp.app import _account_analysis_rows
    from analysis.served_view import displayed
    rows = {(section, field): value for section, field, value in _account_analysis_rows(served)}
    lenders = json.loads(rows[("detection", "potential_lenders")])
    notes = json.loads(rows[("metrics", "notes")])
    return [(item["eligible_deposit_denominator"], item["potential_withholding_exposure"]) for item in lenders], notes


SALES = [(2, SALE, 10000.0), (9, SALE, 10000.0)]


def test_a_a_confirm_moves_each_potential_lender_s_row_with_the_card(monkeypatch):
    stored = _stored(monkeypatch, [*SALES, (20, WIRE, 20000.0)])
    before = _served(stored)
    assert before["metrics"]["potential_withholding_exposure"] == pytest.approx(18.75)
    assert _row(before) == (20000.0, 18.75)
    reviewed = _review(stored, [(_location(stored, WIRE, 20000.0), "confirm", None)])
    served = _served(reviewed)
    metrics = served["metrics"]
    assert metrics["withholding_denominator"] == metrics["potential_withholding_denominator"] == 40000.0
    assert metrics["potential_withholding_exposure"] == pytest.approx(9.375)
    assert _row(served) == (40000.0, pytest.approx(9.375))  # was (20000.0, 18.75)
    assert _export_cells(_served_export(reviewed))[0] == [(40000.0, pytest.approx(9.375))]


def _served_export(payload):
    from analysis.served_view import displayed
    return displayed(copy.deepcopy(payload), settings={"zelle_true_revenue": True}, export=True)


def test_b_a_confirm_lifting_a_zero_basis_publishes_the_row_and_drops_the_notes(monkeypatch):
    stored = _stored(monkeypatch, [(20, WIRE, 20000.0)])
    before = _served(stored)["metrics"]
    assert before["withholding_rate"] is None and len(_basis_notes(before)) == 2
    reviewed = _review(stored, [(_location(stored, WIRE, 20000.0), "confirm", None)])
    served = _served(reviewed)
    metrics = served["metrics"]
    assert metrics["withholding_rate"] == pytest.approx(14.0)
    assert metrics["potential_withholding_exposure"] == pytest.approx(18.75)
    assert _row(served) == (20000.0, pytest.approx(18.75))  # was (0.0, None)
    assert _basis_notes(metrics) == []  # the two "unavailable" notes stayed
    lenders, notes = _export_cells(_served_export(reviewed))
    assert lenders == [(20000.0, pytest.approx(18.75))]
    assert not [note for note in notes if note.startswith(UNAVAILABLE)]


def test_c_a_reject_to_zero_takes_the_row_to_zero_and_adds_the_notes(monkeypatch):
    stored = _stored(monkeypatch, [(2, SALE, 6000.0), (9, SALE, 6000.0)])
    before = _served(stored)
    assert _row(before) == (12000.0, pytest.approx(31.25)) and _basis_notes(before["metrics"]) == []
    sales = [location for location in (row["classification"]["source_location"]
                                       for row in stored["statement"]["transactions"] if row["description"] == SALE)]
    reviewed = _review(stored, [(location, "reject", None) for location in sales])
    served = _served(reviewed)
    metrics = served["metrics"]
    assert metrics["true_revenue_total"] == 0.0 and metrics["withholding_rate"] is None
    assert _row(served) == (0.0, None)  # was (12000.0, 31.25)
    assert _basis_notes(metrics) == [
        "withholding rate is unavailable because True revenue is zero or missing",
        "potential withholding exposure is unavailable because True revenue is zero or missing",
    ]
    lenders, notes = _export_cells(_served_export(reviewed))
    assert lenders == [(0.0, None)] and len([note for note in notes if note.startswith(UNAVAILABLE)]) == 2


def test_d_a_reset_returns_every_value_to_the_analysis(monkeypatch):
    stored = _stored(monkeypatch, [*SALES, (20, WIRE, 20000.0)])
    location = _location(stored, WIRE, 20000.0)
    confirmed = _review(stored, [(location, "confirm", None)])
    assert confirmed["detection"]["potential_lenders"] != stored["detection"]["potential_lenders"]
    reset = _review(confirmed, [(location, "reset", None)])
    assert reset["detection"]["potential_lenders"] == stored["detection"]["potential_lenders"]
    assert reset["metrics"] == stored["metrics"]
    assert reset == stored


def test_e_a_confirm_under_the_floor_reads_the_floor_then_a_larger_one_publishes(monkeypatch):
    stored = _stored(monkeypatch, [(20, WIRE, 20000.0), (21, WIRE, 5.0)])
    small = _review(stored, [(_location(stored, WIRE, 5.0), "confirm", None)])
    served = _served(small)
    metrics = served["metrics"]
    assert metrics["true_revenue_total"] == 5.0
    assert metrics["withholding_rate"] is None and metrics["withholding_basis_below_floor"] is True
    assert metrics["withholding_review_required"] is True
    assert _row(served) == (None, None)
    assert _basis_notes(metrics) == [
        "withholding rate is unavailable because True revenue (5.00 USD) is under the withholding basis floor "
        "(500.00 USD)",
        "potential withholding exposure is unavailable because True revenue (5.00 USD) is under the withholding "
        "basis floor (500.00 USD)",
    ]
    large = _review(small, [(_location(stored, WIRE, 20000.0), "confirm", None)])
    served = _served(large)
    metrics = served["metrics"]
    assert metrics["withholding_rate"] == pytest.approx(2800.0 / 20005.0 * 100)
    assert metrics["withholding_basis_below_floor"] is False and metrics["withholding_review_required"] is False
    assert _row(served) == (20005.0, pytest.approx(3750.0 / 20005.0 * 100))
    assert _basis_notes(metrics) == []


def test_f_the_legacy_basis_leaves_every_row_and_note_as_stored(monkeypatch):
    stored = _stored(monkeypatch, [*SALES, (20, WIRE, 20000.0)], mode="legacy_eligible_deposits")
    reviewed = _review(stored, [(_location(stored, WIRE, 20000.0), "confirm", None)])
    assert reviewed["detection"]["potential_lenders"] == stored["detection"]["potential_lenders"]
    assert reviewed["metrics"]["notes"] == stored["metrics"]["notes"]
    assert reviewed["metrics"]["withholding_rate"] == stored["metrics"]["withholding_rate"]


def test_f_the_verified_basis_moves_the_rows_with_verified(monkeypatch):
    stored = _stored(monkeypatch, [*SALES, (20, WIRE, 20000.0)], mode="verified_revenue")
    assert _row(_served(stored)) == (20000.0, pytest.approx(18.75))
    served = _served(_review(stored, [(_location(stored, WIRE, 20000.0), "confirm", None)]))
    assert served["metrics"]["withholding_denominator"] == 40000.0
    assert _row(served) == (40000.0, pytest.approx(9.375))


def test_g_both_zelle_readings_carry_rows_equal_to_their_own_card(monkeypatch):
    from analysis import zelle_view
    from analysis.revenue import rebuild_serialized_revenue_views

    stored = _stored(monkeypatch, [*SALES, (20, WIRE, 20000.0), (22, ZELLE, 4000.0)])
    assert zelle_view.ZELLE_EDITS_KEY in stored
    reviewed = _review(stored, [(_location(stored, WIRE, 20000.0), "confirm", None)])
    for zelle, basis in ((True, 44000.0), (False, 40000.0)):
        served = _served(reviewed, zelle=zelle)
        metrics = served["metrics"]
        assert metrics["potential_withholding_denominator"] == basis
        assert _row(served) == (basis, pytest.approx(metrics["potential_withholding_exposure"]))
    no, yes, carrying = zelle_view.split_readings(reviewed)
    assert carrying
    (no_account,), (yes_account,) = [no], [yes]
    lean = zelle_view.reading_edits(no_account, yes_account)
    assert rebuild_serialized_revenue_views(zelle_view.apply_reading_edits(no_account, lean)) == yes_account

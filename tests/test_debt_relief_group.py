"""5.3 (owner ruling 2026-09-27): the twelfth flag group, Debt relief. Fabricated descriptors and a fabricated
debt-relief table; every amount is whole dollars."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier
from analysis.detect import find_flagged_positions
from analysis.flag_groups import FINANCING_STATES, FLAG_GROUP_BY_KEY
from analysis.payee_matcher import AliasIndex
from analysis.schema import Statement
from analysis.transaction_classifier import classify_statement_transactions, classify_transaction
from tests.flag_group_fixtures import fake_payees, txn  # noqa: F401  (fixture)

FABRICATED_RELIEF = {"Fabrikam Settlement Payments": ("FABRIKAM SETTLE PMT", "FABRIKAM DEBT RELIEF")}


def test_the_group_is_a_flag_and_never_financing():
    group = FLAG_GROUP_BY_KEY["debt_relief"]
    assert (group.state, group.setting, group.label) == ("debt_relief", "flag_debt_relief", "Debt relief")
    assert "debt_relief" not in FINANCING_STATES


@pytest.fixture
def relief_payees(monkeypatch):
    index = AliasIndex({"debt_relief": FABRICATED_RELIEF}, run_together=True)
    monkeypatch.setattr(transaction_classifier, "match_debt_relief_payee", index.match)


@pytest.mark.parametrize(
    "printed",
    [
        "FABRIKAM SETTLE PMT 0001",
        "Electronic Withdrawal To FABRIKAM SETTLE PMT",
        "FABRIKAMSETTLEPMT DES:DEPOSIT ID:0001",                      # the run-together form
        "Orig CO Name:Fabrikam Debt Relief Orig ID:0001 Desc Date: CO Entry Descr:Pmt Sec:PPD Ind Name:Pat Example",
        # a card purchase at a debt-relief firm is that firm's (the POS exception, D8)
        "Debit Card Purchase: 0105 PURCHASE 12 FABRIKAM DEBT RELIEF NEW YORK NY",
    ],
)
def test_a_debit_to_a_debt_relief_payee_is_flagged_debt_relief(relief_payees, printed):
    record = classify_transaction(printed, -400.0)
    assert (record.classification, record.canonical_entity, record.flagged_group) == (
        "debt_relief", "Fabrikam Settlement Payments", "debt_relief")
    assert (record.match_method, record.matched_rule) == ("known_payee_alias", "debt_relief_registry")
    assert record.contributes_to_flagged_totals
    assert not record.contributes_to_lender_totals and not record.contributes_to_potential_lender_totals


def test_the_account_holders_own_name_never_makes_a_row_debt_relief(relief_payees, fake_payees):
    funder = classify_transaction(
        "FABRICATED LENDER DES:PAYMENT ID:0001 INDN:FABRIKAM DEBT RELIEF CO ID:0002 CCD", -400.0)
    assert (funder.classification, funder.canonical_entity) == ("confirmed_lender", "Fabricated Lender")
    unknown = classify_transaction("FAB UNLISTED ADVANCE DES:DEBIT ID:0001 INDN:FABRIKAM DEBT RELIEF CO ID:1 CCD",
                                   -400.0)
    assert unknown.classification != "debt_relief"


def test_a_known_payee_outranks_a_debt_relief_alias_on_the_same_row(relief_payees, fake_payees):
    record = classify_transaction("FABRIKAM SETTLE PMT DES:FABRICATED LENDER ID:0001 PPD", -400.0)
    assert record.classification == "confirmed_lender"


def test_credits_and_fees_keep_todays_rules(relief_payees):
    refund = classify_transaction("FABRIKAM SETTLE PMT 0001", 400.0)
    assert refund.classification != "debt_relief" and refund.flagged_group is None
    assert classify_transaction("WIRE FEE FOR WIRE TRANSFER TO FABRIKAM DEBT RELIEF", -25.0).classification == "fee"


def test_debt_relief_rows_are_a_flagged_position_and_never_a_d6_payee(relief_payees):
    statement = Statement(bank="Fabricated Bank", transactions=[
        txn(day, "FABRIKAM SETTLE PMT 0001", -300.0) for day in ("2054-01-05", "2054-01-12", "2054-01-19")
    ])
    records = classify_statement_transactions(statement)
    assert {record.classification for record in records} == {"debt_relief"}
    [position] = find_flagged_positions(statement, records)
    assert (position.group, position.payee, position.count, position.cadence) == (
        "debt_relief", "Fabrikam Settlement Payments", 3, "weekly")

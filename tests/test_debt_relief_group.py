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

from __future__ import annotations

import re

import pytest

from analysis.altana import parse_altana_statement
from tests.data.parser_conformance_fixtures import FIXTURES


@pytest.fixture
def altana_markdown():
    issuer, product = FIXTURES["altana"].splitlines()
    product = re.sub(r"\d+\b", "7812", product)
    return f"""{issuer}
Date Range: 03/01/2055 - 03/31/2055
{product} Beginning Balance $100.00-
1 Total Deposits for 50.00-
1 Total Withdrawals for 20.00-
Ending Balance $130.00-
03/02 Deposit Sample credit 50.00 150.00
03/03 Withdrawal Sample debit 20.00 130.00
Fees Paid
"""


@pytest.mark.parametrize("account", ["7812", "0007"])
def test_parse_altana_statement_uses_printed_account_number(altana_markdown, account):
    markdown = altana_markdown.replace("7812", account)

    stmt = parse_altana_statement(markdown)

    assert stmt is not None and stmt.account_number == account


@pytest.mark.parametrize("account", ["", "XXXX", "7812oops"])
def test_parse_altana_statement_refuses_missing_or_invalid_account_number(altana_markdown, account):
    markdown = altana_markdown.replace("7812", account)

    assert parse_altana_statement(markdown) is None

"""Audit 2026-10-13, REC-8: the Banco Popular reader skips the holder line of a page header by POSITION, never by name.

Every page of a FlexiCuenta de Negocios statement repeats its header: the period, the product line, "Page N", the
"Account Number" line and, right after it, the holder's line. A row that crosses a page break reads the next page's
header lines as its continuation. The reader used to skip the holder line only when it equalled one literal business
name, so on any other holder's statement the name was appended to the description of every row that crossed a page
(and could then reach the classifier's keyword rules). It now skips the line right after a page-header "Account
Number" line when it equals the holder line the statement prints under its first "Account Number" line. A
continuation line that prints the holder's name anywhere else (own-money evidence) is kept.

Fabricated statement only (CONTOSO / FABRIKAM / NORTHWIND / SAMPLE; neutral amounts and dates).
"""
from __future__ import annotations

import pytest

from analysis.banco_popular import parse_banco_popular_statement
from analysis.reconcile import reconcile

HOLDER = "CONTOSO SAMPLE HOLDINGS LLC"


def _statement(holder: str = HOLDER) -> str:
    page_header = (
        "From: March 01, 2054\n"
        "To: March 31, 2054\n"
        "FLEXICUENTA DE NEGOCIOS\n"
        "Page {n}\n"
        "Account Number 000-000123\n"
        f"{holder}\n"
    )
    page_1 = (
        "Account Statement From: March 01, 2054\n"
        "To: March 31, 2054\n"
        "Banco Popular\n"
        f"{holder} 100 SAMPLE STREET SAMPLE CITY\n"
        "FLEXICUENTA DE NEGOCIOS\n"
        "Page 1\n"
        "Account Number 000-000123\n"
        f"{holder}\n"
        "FlexiChecking\n"
        "Beginning Balance $1,000.00 3 Additions + 600.00\n"
        "2 Subtractions - 300.00 Service charges - 10.00 Ending Balance $1,290.00\n"
        "FlexInvestments\n"
        "Account Detail FlexiChecking Beginning Balance $1,000.00\n"
        "Additions\n"
        "Other credits\n"
        "Date Reference Description Amount\n"
        "03-02 0000000001 DEPOSIT FROM FABRIKAM 200.00\n"
        "03-05 0000000002 DEPOSIT FROM NORTHWIND 150.00"
    )
    page_2 = (
        page_header.format(n=2)
        + "Additions (continued)\n"
        "Other credits (continued)\n"
        "Date Reference Description Amount\n"
        "03-20 0000000003 DEPOSIT FROM FABRIKAM 250.00\n"
        "Total Other credits 600.00\n"
        "Subtractions\n"
        "Other debits\n"
        "Date Reference Description Amount\n"
        "03-10 0000000004 PAYMENT TO SAMPLE SUPPLY 100.00\n"
        "03-25 0000000005 TRANSFER TO 200.00\n"
        f"{holder}\n"
        "Total Other debits 300.00\n"
        "Service Charges\n"
        "Service charges 10.00"
    )
    return (
        "<!-- source: fabricated.pdf | pages: 2 | model: native-pdf-text | empty: 0 -->\n\n\n\n"
        f"--- Page 1 ---\n\n{page_1}\n\n--- Page 2 ---\n\n{page_2}\n"
    )


def _descriptions(stmt) -> dict[str, str]:
    """Each row's description by its fabricated reference number."""
    return {t.description.split()[0]: t.description for t in stmt.transactions if t.description[:1].isdigit()}


@pytest.mark.parametrize("holder", [HOLDER, "NORTHWIND INSURANCE AGENCY LLC", "FABRIKAM LEASING CORP"])
def test_a_row_crossing_a_page_break_does_not_carry_the_holder_line(holder):
    stmt = parse_banco_popular_statement(_statement(holder))
    assert stmt is not None
    assert reconcile(stmt).ok
    descriptions = _descriptions(stmt)
    assert len(descriptions) == 5
    # The last credit row of page 1 crosses the break: the next page's header follows it.
    crossing = descriptions["0000000002"]
    assert holder not in crossing
    assert crossing.startswith("0000000002 DEPOSIT FROM NORTHWIND")


def test_the_holder_name_printed_as_a_row_continuation_is_kept():
    """Positional, not by name: the holder line is skipped only right after a page-header Account Number line, so a
    transfer whose continuation prints the holder's own name keeps it (own-money evidence)."""
    stmt = parse_banco_popular_statement(_statement())
    assert stmt is not None
    assert _descriptions(stmt)["0000000005"] == f"0000000005 TRANSFER TO {HOLDER}"


def test_the_rows_dates_amounts_and_directions_are_read_as_printed():
    stmt = parse_banco_popular_statement(_statement())
    assert stmt is not None
    rows = sorted((t.date, t.amount, t.direction) for t in stmt.transactions)
    assert rows == [
        ("2054-03-02", 200.0, "credit"),
        ("2054-03-05", 150.0, "credit"),
        ("2054-03-10", -100.0, "debit"),
        ("2054-03-20", 250.0, "credit"),
        ("2054-03-25", -200.0, "debit"),
        ("2054-03-31", -10.0, "debit"),
    ]
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.0, 1290.0)


def test_a_statement_without_a_holder_line_reads_every_row():
    """No line under the first Account Number line is a holder candidate when it is itself a row: nothing is
    skipped, so no transaction can be lost to the rule."""
    md = _statement().replace(f"Account Number 000-000123\n{HOLDER}\n", "Account Number 000-000123\n")
    stmt = parse_banco_popular_statement(md)
    assert stmt is not None
    assert len(_descriptions(stmt)) == 5
    assert reconcile(stmt).ok

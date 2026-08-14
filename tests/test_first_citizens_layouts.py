"""FC-E layout variants for the First Citizens `At A Glance` family.

Each fixture reproduces one structural trait measured across the 39 documents
that carry the `Central Bank Operations - DAC02` + `Your Account(s) At A
Glance` signature. They are synthetic statements, not copies of customer
documents, and every one of them balances on the arithmetic the bank prints:

    beginning + deposits + other credits - checks - other debits
        - monthly service charge = ending

Against the pre-rebuild parser, the month-generality fixture fails (it pinned
`03`), the no-serial cheque fixture fails, the renamed-debits fixture fails,
the summary-order fixture fails, and both decline fixtures fail by parsing
something they had no evidence for.
"""
from __future__ import annotations

import pytest

from analysis.first_citizens import parse_first_citizens_statement
from analysis.reconcile import reconcile

MONTH_NAMES = {
    3: "March",
    4: "April",
    11: "November",
}


def statement(
    *,
    month: int = 4,
    days: int = 30,
    summary_order: str = "days_first",
    cheque_serial: str = "1001",
    debits_header: str = "Other Debits From Your Account",
    service_charge: str | None = None,
) -> str:
    """A minimal, self-consistent statement in this family.

    beginning 1,000.00 + deposits 1,000.00 + other credits 500.00
        - cheques 250.00 - other debits 750.00 - service charge = ending
    """
    mm = f"{month:02d}"
    name = MONTH_NAMES[month]
    charge_row = f"{service_charge}-" if service_charge else "0.00"
    ending = "1,500.00" if not service_charge else "1,495.00"

    head = [
        "Central Bank Operations - DAC02 P.O. Box 27131 Raleigh, NC 27611-7131",
        "Your Account(s) At A Glance",
        "Checking Balance",
        "+",
        ending,
        f"Statement Period: {name} 1 , 2026     Thru {name} {days}, 2026 "
        "Account Number : 000111222333",
        "Business Banking",
        "Account Number :   000111222333 Enclosures In Statement:   0",
        "Statement Period Days Average Ledger Balance",
        f"+ 1 + 1 500.00+ 1 250.00- 1 750.00- {charge_row}",
    ]
    # The extractor emits `days` before the beginning balance on most documents
    # and after it on others; both orders are real.
    if summary_order == "days_first":
        head += [str(days), "1,000.00"]
    else:
        head += ["1,000.00", str(days)]
    head += [
        "Beginning Balance",
        "Deposits Other Credits Checks Other Debits Monthly Service Charge",
        "1,000.00",
        "1,800.00+",
        "+",
        ending,
        "Ending  Balance",
    ]

    body = [
        "Deposits To Your Account",
        "Date Amount Date Amount Date Amount",
        f"{mm}             1,000.00",
        "-05",
        "Other Credits To Your Account",
        "Date Description Amount Acme Supply Payout",
        f"{mm}-10",
        "500.00",
        "Total",
        "500.00",
        "Checks Paid From Your Account",
        "Check No. Date Amount Check No. Date Amount Check No. Date Amount",
        # The continuation marker prints ABOVE the rows on some documents and
        # below them on others; it is not a section boundary either way.
        "* *",
        f"{cheque_serial} {mm}-12 250.00".strip(),
        "*Prior Check Number(s) Not Included or Out of Sequence.",
        debits_header,
        "Date Description Amount Beta Freight Co",
        f"{mm}-20",
        "750.00",
        "Total",
        "750.00",
    ]
    if service_charge:
        body += [
            "Monthly Service Charge Description",
            "Date Description Total Items Item Fee Amount Excess Dr/Cr Fee",
            f"{mm}-{days} 10",
            f"0.5000 {service_charge}",
            "Total",
            service_charge,
        ]
    body += [
        "Daily Balance Summary",
        "Date Balance Date Balance Date Balance",
        f"{mm}             1,500.00+",
        "-20",
        "An updated Master Treasury Management Services Agreement (MSA) is now available.",
    ]
    return "\n".join(head + body) + "\n"


def test_base_layout_reads_both_balances_from_the_printed_summary():
    stmt = parse_first_citizens_statement(statement())
    assert stmt is not None
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1500.00
    assert stmt.stated_total_credits == 1500.00
    assert stmt.stated_total_debits == 1000.00
    assert stmt.stated_credit_count == 2
    assert stmt.stated_debit_count == 2
    assert stmt.days_in_period == 30
    assert stmt.stated_average_balance == 1800.00
    assert len(stmt.transactions) == 4
    assert reconcile(stmt).ok


@pytest.mark.parametrize("month, days", [(3, 31), (4, 30), (11, 30)])
def test_any_month_parses(month, days):
    """FC-A. The month was a literal `03` in two row regexes."""
    stmt = parse_first_citizens_statement(statement(month=month, days=days))
    assert stmt is not None
    assert stmt.period_start == f"2026-{month:02d}-01"
    assert [t.date for t in stmt.transactions] == [
        f"2026-{month:02d}-05",
        f"2026-{month:02d}-10",
        f"2026-{month:02d}-12",
        f"2026-{month:02d}-20",
    ]
    assert reconcile(stmt).ok


def test_summary_cells_may_arrive_in_either_order():
    """The extractor emits `days` before or after the beginning balance."""
    first = parse_first_citizens_statement(statement(summary_order="days_first"))
    second = parse_first_citizens_statement(statement(summary_order="balance_first"))
    assert first is not None and second is not None
    assert first.beginning_balance == second.beginning_balance == 1000.00
    assert first.days_in_period == second.days_in_period == 30


def test_cheque_with_no_printed_serial_is_still_a_cheque():
    """A cheque the bank could not read prints an empty number column."""
    stmt = parse_first_citizens_statement(statement(cheque_serial=""))
    assert stmt is not None
    cheques = [t for t in stmt.transactions if t.description.startswith("Check")]
    assert [t.description for t in cheques] == ["Check"]
    assert cheques[0].amount == -250.00
    assert reconcile(stmt).ok


def test_debits_section_renamed_when_a_service_charge_is_billed():
    """The header becomes `Other Debits And Monthly Service Charge`, and the
    charge is itemised outside the four section totals with its own date."""
    stmt = parse_first_citizens_statement(
        statement(
            debits_header="Other Debits And Monthly Service Charge",
            service_charge="5.00",
        )
    )
    assert stmt is not None
    assert stmt.stated_service_charge == 5.00
    assert stmt.ending_balance == 1495.00
    billed = [t for t in stmt.transactions if t.description == "Monthly Service Charge"]
    assert len(billed) == 1
    assert billed[0].amount == -5.00
    assert billed[0].date == "2026-04-30"
    assert reconcile(stmt).ok


def test_single_posting_section_keeps_its_printed_description():
    stmt = parse_first_citizens_statement(statement())
    assert stmt is not None
    assert any(t.description == "Acme Supply Payout" for t in stmt.transactions)
    assert any(t.description == "Beta Freight Co" for t in stmt.transactions)


def test_section_totals_are_checked_against_the_printed_ones():
    """FC-B. The gate is the document's own figures, not remembered ones."""
    damaged = statement().replace(
        "Date Description Amount Beta Freight Co\n04-20\n750.00",
        "Date Description Amount Beta Freight Co\n04-20\n700.00",
    )
    assert parse_first_citizens_statement(damaged) is None


def test_statement_with_no_control_row_is_declined():
    """The dormant statements in the archive print no control row at all."""
    dormant = statement().replace("+ 1 + 1 500.00+ 1 250.00- 1 750.00- 0.00\n", "")
    assert parse_first_citizens_statement(dormant) is None


def test_document_carrying_the_name_but_no_summary_is_not_claimed():
    """R4-3. Two archive documents name the bank and print no statement."""
    not_a_statement = (
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ACH DEBIT PAYMENT TO First Citizens 250.00\n"
    )
    assert parse_first_citizens_statement(not_a_statement) is None


def test_missing_deposits_section_is_not_fatal():
    """FC-C. Every section is optional; a printed count of 0 means absent."""
    no_deposits = statement().replace(
        "+ 1 + 1 500.00+ 1 250.00- 1 750.00- 0.00",
        "+ 0 1 500.00+ 1 250.00- 1 750.00- 0.00",
    )
    no_deposits = no_deposits.replace(
        "Deposits To Your Account\n"
        "Date Amount Date Amount Date Amount\n"
        "04             1,000.00\n"
        "-05\n",
        "",
    )
    # Beginning rises by the deposits that are no longer printed, so the
    # summary still closes: 2,000.00 + 500.00 - 250.00 - 750.00 = 1,500.00.
    no_deposits = no_deposits.replace("30\n1,000.00\n", "30\n2,000.00\n")
    no_deposits = no_deposits.replace(
        "Deposits Other Credits Checks Other Debits Monthly Service Charge\n1,000.00\n",
        "Deposits Other Credits Checks Other Debits Monthly Service Charge\n0.00\n",
    )
    stmt = parse_first_citizens_statement(no_deposits)
    assert stmt is not None
    assert stmt.beginning_balance == 2000.00
    assert len(stmt.transactions) == 3
    assert reconcile(stmt).ok

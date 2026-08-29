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
        f"Statement Period: {name} 1 , 2054     Thru {name} {days}, 2054 "
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
    assert stmt.period_start == f"2054-{month:02d}-01"
    assert [t.date for t in stmt.transactions] == [
        f"2054-{month:02d}-05",
        f"2054-{month:02d}-10",
        f"2054-{month:02d}-12",
        f"2054-{month:02d}-20",
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
    assert billed[0].date == "2054-04-30"
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


# ---------------------------------------------------------------------------
# FCX — the printed descriptions, overlaid on the postings already read
# ---------------------------------------------------------------------------
#
# `ocr/native_text.py::parse_native_first_citizens` recovers this bank's
# description column from the printed table's geometry and reports one row per
# posting at the end of the document. The parser lays those rows over the
# postings it read positionally out of the flattened column, and only where the
# two readings agree on every date and every amount of the section, in printed
# order. These fixtures pin both halves: the recovery, and every way it refuses.


def flattened(
    *,
    rows: str | None = None,
    credit_run: str = "Acme Supply Payout Zeta Logistics",
    debit_run: str = "Beta Freight Co Delta Utilities Epsilon Fuel",
) -> str:
    """A statement whose described sections hold more than one posting each.

    beginning 1,000.00 + deposits 1,000.00 + other credits 500.00
        - cheques 250.00 - other debits 750.00 = ending 1,500.00

    The description column arrives welded exactly as the generic native reader
    delivers it; `rows` is the layout extractor's report, appended where the
    intake appends it.
    """
    body = "\n".join(
        [
            "Central Bank Operations - DAC02 P.O. Box 27131 Raleigh, NC 27611-7131",
            "Your Account(s) At A Glance",
            "Checking Balance",
            "+",
            "1,500.00",
            "Statement Period: April 1 , 2054     Thru April 30, 2054 "
            "Account Number : 000111222333",
            "Business Banking",
            "Account Number :   000111222333 Enclosures In Statement:   0",
            "Statement Period Days Average Ledger Balance",
            "+ 1 + 2 500.00+ 1 250.00- 3 750.00- 0.00",
            "30",
            "1,000.00",
            "Beginning Balance",
            "Deposits Other Credits Checks Other Debits Monthly Service Charge",
            "1,000.00",
            "1,800.00+",
            "+",
            "1,500.00",
            "Ending  Balance",
            "Deposits To Your Account",
            "Date Amount Date Amount Date Amount",
            "04             1,000.00",
            "-05",
            "Other Credits To Your Account",
            f"Date Description Amount {credit_run}",
            "04-08 04-10",
            "200.00 300.00",
            "Total",
            "500.00",
            "Checks Paid From Your Account",
            "Check No. Date Amount Check No. Date Amount Check No. Date Amount",
            "1001 04-12 250.00",
            "*Prior Check Number(s) Not Included or Out of Sequence.",
            "Other Debits From Your Account",
            f"Date Description Amount {debit_run}",
            "04-18 04-20 04-22",
            "100.00 250.00 400.00",
            "Total",
            "750.00",
            "Daily Balance Summary",
            "Date Balance Date Balance Date Balance",
            "04             1,500.00+",
            "-20",
            "An updated Master Treasury Management Services Agreement (MSA) is available.",
        ]
    )
    if rows is not None:
        body += "\nFC_NATIVE_TRANSACTIONS\n" + rows + "\nFC_NATIVE_TRANSACTIONS_END"
    return body + "\n"


REPORTED = "\n".join(
    [
        "FC_TX|Other Credits To Your Account|04-08|200.00|Acme Supply Payout",
        "FC_TX|Other Credits To Your Account|04-10|300.00|Zeta Logistics",
        "FC_TX|Other Debits From Your Account|04-18|100.00|Beta Freight Co",
        "FC_TX|Other Debits From Your Account|04-20|250.00|Delta Utilities",
        "FC_TX|Other Debits From Your Account|04-22|400.00|Epsilon Fuel",
    ]
)

LABELLED = [
    "Deposit",
    "Other Credit",
    "Other Credit",
    "Check #1001",
    "Other Debit",
    "Other Debit",
    "Other Debit",
]

PRINTED = [
    "Deposit",
    "Acme Supply Payout",
    "Zeta Logistics",
    "Check #1001",
    "Beta Freight Co",
    "Delta Utilities",
    "Epsilon Fuel",
]


def described(markdown: str) -> list[str]:
    stmt = parse_first_citizens_statement(markdown)
    assert stmt is not None
    return [t.description for t in stmt.transactions]


def test_a_document_without_the_extractor_report_is_labelled_exactly_as_before():
    """The floor: everything the batch-3 parser did on flat text, it still does."""
    stmt = parse_first_citizens_statement(flattened())
    assert stmt is not None
    assert [t.description for t in stmt.transactions] == LABELLED
    assert reconcile(stmt).ok


def test_the_printed_descriptions_are_published_when_both_readings_agree():
    assert described(flattened(rows=REPORTED)) == PRINTED


def test_the_overlay_moves_no_money_no_date_and_no_count():
    """It is text and nothing else; the gates above it have already run."""
    plain = parse_first_citizens_statement(flattened())
    overlaid = parse_first_citizens_statement(flattened(rows=REPORTED))
    assert plain is not None and overlaid is not None
    assert [(t.date, t.amount, t.direction) for t in plain.transactions] == [
        (t.date, t.amount, t.direction) for t in overlaid.transactions
    ]
    assert plain.model_dump(exclude={"transactions"}) == overlaid.model_dump(
        exclude={"transactions"}
    )
    assert reconcile(overlaid).ok


def test_a_section_whose_amounts_disagree_keeps_its_labels():
    damaged = REPORTED.replace("|04-20|250.00|", "|04-20|251.00|")
    # The credits section still agrees and publishes; the debits section does not.
    assert described(flattened(rows=damaged)) == PRINTED[:4] + LABELLED[4:]


def test_a_section_whose_dates_disagree_keeps_its_labels():
    damaged = REPORTED.replace("|04-18|100.00|", "|04-19|100.00|")
    assert described(flattened(rows=damaged)) == PRINTED[:4] + LABELLED[4:]


def test_a_section_reported_with_the_wrong_number_of_rows_keeps_its_labels():
    short = "\n".join(line for line in REPORTED.splitlines() if "Epsilon" not in line)
    assert described(flattened(rows=short)) == PRINTED[:4] + LABELLED[4:]


def test_a_date_the_printed_period_cannot_place_keeps_the_labels():
    outside = REPORTED.replace("|04-18|", "|11-18|")
    assert described(flattened(rows=outside)) == PRINTED[:4] + LABELLED[4:]


def test_rows_cannot_describe_a_section_they_were_not_printed_under():
    """Credit rows may not name debit postings, nor the reverse."""
    swapped = REPORTED.replace(
        "Other Credits To Your Account", "Other Debits From Your Account"
    )
    assert described(flattened(rows=swapped)) == LABELLED


@pytest.mark.parametrize(
    "damage",
    [
        ("FC_TX|Other Credits To Your Account|04-08|200.00|", "junk "),
        ("|04-08|200.00|", "|04-08|"),
        ("|200.00|", "|two hundred|"),
        ("|04-08|", "|2054-04-08|"),
    ],
)
def test_a_malformed_report_is_read_as_no_report_at_all(damage):
    assert described(flattened(rows=REPORTED.replace(*damage))) == LABELLED


def test_a_row_the_bank_printed_with_no_description_keeps_its_label():
    blank = REPORTED.replace("|04-10|300.00|Zeta Logistics", "|04-10|300.00|")
    assert described(flattened(rows=blank))[1:3] == ["Acme Supply Payout", "Other Credit"]


def test_a_renamed_debits_section_is_still_described():
    """The bank renames the section when it bills a service charge."""
    renamed = flattened(rows=REPORTED).replace(
        "Other Debits From Your Account", "Other Debits And Monthly Service Charge"
    )
    assert described(renamed) == PRINTED


def test_the_report_is_not_mistaken_for_statement_text():
    """It sits after everything the document prints and is not part of it."""
    stmt = parse_first_citizens_statement(flattened(rows=REPORTED))
    assert stmt is not None
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1500.00
    assert stmt.stated_total_credits == 500.00 + 1000.00
    assert stmt.stated_total_debits == 250.00 + 750.00
    assert len(stmt.transactions) == 7


def test_the_report_is_cut_out_before_any_reader_scans_the_document():
    """Every row repeats the heading it was printed under.

    `_section_blocks` splits the document on those headings and
    `_service_charge_posting` scans it for a charge itemisation, so a report
    left in place would be a SECOND printing of `Other Debits From Your
    Account` — five of them here — inside the text both of them read. The
    report is removed at the parse seam, so the document those readers see is
    the document, and this asserts the property rather than the symptom.
    """
    from analysis.first_citizens import _OTHER_DEBITS, _report, _section_blocks

    with_report = flattened(rows=REPORTED)
    assert with_report.count("Other Debits From Your Account") == 4
    reported, document = _report(with_report)
    assert len(reported) == 5
    assert document == flattened()
    assert document.count("Other Debits From Your Account") == 1
    assert len(_section_blocks(document, _OTHER_DEBITS)) == len(
        _section_blocks(flattened(), _OTHER_DEBITS)
    ) == 1


def test_a_malformed_report_is_still_cut_out():
    reported, document = _report_of(flattened(rows=REPORTED.replace("FC_TX|", "X|")))
    assert reported == []
    assert document == flattened()


def _report_of(markdown):
    from analysis.first_citizens import _report

    return _report(markdown)


def unitemised(rows: str | None = None, trap: bool = False) -> str:
    """A statement that BILLS a service charge and itemises it nowhere.

    beginning 1,000.00 + deposits 1,000.00 + other credits 500.00
        - cheques 250.00 - other debits 750.00 - charge 400.00 = ending 1,100.00

    `_service_charge_posting` has nothing to find, so the honest outcome is that
    the charge row is omitted and the detail does not close — the one path
    FI14.2 identified as still able to fail reconciliation.
    """
    body = flattened(rows=rows)
    if trap:
        # A merchant whose printed memo happens to END in `<Word> Service
        # Charge` — the exact shape `_SERVICE_CHARGE_BLOCKS`' second pattern
        # looks for — with the charge's own amount printed BELOW it in the row
        # that follows. There is nothing else in the document of that shape.
        body = body.replace("|04-20|250.00|Delta Utilities", "|04-20|250.00|Delta April Service Charge")
    body = body.replace(
        "+ 1 + 2 500.00+ 1 250.00- 3 750.00- 0.00",
        "+ 1 + 2 500.00+ 1 250.00- 3 750.00- 400.00-",
    )
    return body.replace("1,500.00", "1,100.00")


def test_a_billed_charge_with_no_itemisation_is_omitted_not_invented():
    """The floor this trap is measured against."""
    stmt = parse_first_citizens_statement(unitemised())
    assert stmt is not None
    assert stmt.stated_service_charge == 400.00
    assert not [t for t in stmt.transactions if t.description == "Monthly Service Charge"]
    assert len(stmt.transactions) == 7
    assert not reconcile(stmt).ok  # honest: the detail cannot close without it


def test_a_recovered_description_cannot_invent_the_billed_service_charge():
    """The report is not an itemisation, however much one row looks like one.

    `_service_charge_posting` scans the document for the charge's own printed
    table, and one of its two patterns is `<Word> Service Charge` at end of
    line. A report read as document text offers exactly that shape — and the
    rows below it supply a date and the charge's own amount — so a charge the
    bank never itemised gets invented, dated off a merchant name, on a document
    whose four section totals still agree because `_matches` never sees it.

    Red before `b71fc07`; the excision is what makes it green.
    """
    trapped = parse_first_citizens_statement(unitemised(rows=REPORTED, trap=True))
    assert trapped is not None
    assert trapped.stated_service_charge == 400.00
    assert not [t for t in trapped.transactions if t.description == "Monthly Service Charge"]
    assert len(trapped.transactions) == 7
    # And the trap row is still published as the printed text it is.
    assert "Delta April Service Charge" in [t.description for t in trapped.transactions]

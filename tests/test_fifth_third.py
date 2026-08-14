"""The Fifth Third commercial print stream (W3 §UNID-B, card 5).

Every fixture here is synthetic. The layout is reproduced faithfully — the
page-repeated print-stream header, the flattened one-line account summary, the
three-up cheque grid with its flags, the `- continued` section headings and the
`Daily Balance Summary` — but no customer, account, date or amount from the
archive appears in this file.

The tests are organised around the four instruments the parser requires to
agree, one adversarial fixture per instrument, plus the summary grammar itself:
a component whose count and amount are both absent means the component is
absent, and that reading is only accepted when the detail section is absent too.
"""
from __future__ import annotations

from analysis.fifth_third import detect, parse_fifth_third_statement

PRINT_STREAM = "FTCSTMT000 000 00000000 UDSPDFSTMT 0000000000000000000 DDA"
PERIOD = (
    "Statement Period Date: 3/1/2026 - 3/31/2026 "
    "Account Type: SYNTHETIC BUS CKG Account Number: 1234567890"
)
FOOTER = (
    "For additional information and account disclosures, "
    "please visit www.53.com/businessbanking"
)
CHECK_LEGEND = (
    "* Indicates gap in check sequence i = Electronic Image s = Substitute Check\n"
    "Number Date Paid Amount Number Date Paid Amount Number Date Paid Amount"
)


def document(
    *,
    summary: str = (
        "03/01 Beginning Balance $100.00 Number of Days in Period 31 "
        "2 Checks $(30.00) 1 Withdrawals / Debits $(20.00) "
        "2 Deposits / Credits $150.00 03/31 Ending Balance $200.00"
    ),
    checks_head: str | None = "Checks 2 checks totaling $30.00",
    check_rows: str = "1001 i 03/02 10.00 1002*i 03/03 20.00",
    debits_head: str | None = (
        "Withdrawals / Debits 1 items totaling $20.00 Date Amount Description "
        "03/04 20.00 SYNTHETIC DEBIT"
    ),
    credits_head: str = (
        "Deposits / Credits 2 items totaling $150.00 Date Amount Description "
        "03/02 50.00 SYNTHETIC DEPOSIT 03/05 100.00 SYNTHETIC DEPOSIT TWO"
    ),
    daily: str = "03/02 140.00 03/03 120.00 03/04 100.00 03/05 200.00",
) -> str:
    page_one = [PRINT_STREAM, PERIOD, "Account Summary - 1234567890", summary]
    if checks_head is not None:
        page_one += [checks_head, CHECK_LEGEND, check_rows]
    page_one += [FOOTER, "Page 1 of 2"]

    page_two = [PRINT_STREAM]
    if debits_head is not None:
        page_two.append(debits_head)
    page_two += [
        credits_head,
        "Daily Balance Summary Date Amount Date Amount Date Amount",
        daily,
        "Page 2 of 2",
    ]
    return (
        "<!-- source: synthetic.pdf | pages: 2 | model: native-pdf-text | empty: 0 -->\n\n"
        "--- Page 1 ---\n\n" + "\n".join(page_one) + "\n\n"
        "--- Page 2 ---\n\n" + "\n".join(page_two) + "\n"
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_detects_the_print_stream():
    assert detect(document()).claims


def test_does_not_claim_without_the_print_stream_header():
    assert not detect(document().replace(PRINT_STREAM, "")).claims


def test_does_not_claim_without_the_issuer_domain():
    """The folder a document was filed in is not evidence of who issued it."""
    assert not detect(document().replace("www.53.com/businessbanking", "")).claims


def test_detection_ignores_the_source_filename_comment():
    plain = document()
    renamed = plain.replace("synthetic.pdf", "fifth third statement.pdf")
    assert detect(plain).score == detect(renamed).score


def test_a_header_with_no_ledger_is_not_a_statement():
    header_only = (
        f"--- Page 1 ---\n\n{PRINT_STREAM}\n{PERIOD}\nAccount Summary\n{FOOTER}\n"
    )
    assert detect(header_only).claims
    assert parse_fifth_third_statement(header_only) is None


# ---------------------------------------------------------------------------
# The three-component summary
# ---------------------------------------------------------------------------

def test_reads_all_three_summary_components():
    stmt = parse_fifth_third_statement(document())
    assert stmt is not None
    assert stmt.bank == "Fifth Third Bank"
    assert stmt.account_number == "1234567890"
    assert stmt.period_start == "2026-03-01"
    assert stmt.period_end == "2026-03-31"
    assert stmt.days_in_period == 31
    assert stmt.beginning_balance == 100.00
    assert stmt.ending_balance == 200.00
    assert stmt.stated_total_credits == 150.00
    # THE TRAP: cheques are a debit component of their own, separate from
    # `Withdrawals / Debits`. 30 + 20, not 20.
    assert stmt.stated_total_debits == 50.00
    assert stmt.stated_credit_count == 2
    assert stmt.stated_debit_count == 3


def test_folding_the_cheque_total_away_would_break_the_closing_identity():
    """Guards the reading, not just the result: with the cheque component
    dropped the printed figures no longer close, which is exactly why a
    two-component reading cannot be right."""
    stmt = parse_fifth_third_statement(document())
    assert stmt is not None
    two_component = stmt.beginning_balance + stmt.stated_total_credits - 20.00
    assert two_component != stmt.ending_balance
    three_component = stmt.beginning_balance + stmt.stated_total_credits - 50.00
    assert three_component == stmt.ending_balance


def test_transactions_carry_every_section():
    stmt = parse_fifth_third_statement(document())
    assert stmt is not None
    assert len(stmt.transactions) == 5
    assert [t.date for t in stmt.transactions] == sorted(t.date for t in stmt.transactions)
    cheques = [t for t in stmt.transactions if t.description.startswith("Check ")]
    assert [t.description for t in cheques] == ["Check 1001", "Check 1002"]
    assert all(t.amount < 0 for t in cheques)
    assert sum(t.amount for t in stmt.transactions if t.amount > 0) == 150.00
    assert sum(t.amount for t in stmt.transactions if t.amount < 0) == -50.00


def test_daily_balances_are_published_as_source_evidence():
    stmt = parse_fifth_third_statement(document())
    assert stmt is not None
    assert [(d.date, d.balance) for d in stmt.stated_daily_balances] == [
        ("2026-03-02", 140.00),
        ("2026-03-03", 120.00),
        ("2026-03-04", 100.00),
        ("2026-03-05", 200.00),
    ]


# ---------------------------------------------------------------------------
# A bare label means the component is absent
# ---------------------------------------------------------------------------

def test_a_bare_cheques_label_means_no_cheques_that_period():
    """`... Period 31 Checks 1 Withdrawals / Debits $(20.00) ...` — the word
    `Checks` carries neither a count nor an amount, and the cheque section is
    absent from the document as well."""
    stmt = parse_fifth_third_statement(document(
        summary=(
            "03/01 Beginning Balance $100.00 Number of Days in Period 31 "
            "Checks 1 Withdrawals / Debits $(20.00) "
            "2 Deposits / Credits $150.00 03/31 Ending Balance $230.00"
        ),
        checks_head=None,
        daily="03/02 150.00 03/04 130.00 03/05 230.00",
    ))
    assert stmt is not None
    assert stmt.stated_total_debits == 20.00
    assert stmt.stated_debit_count == 1
    assert not [t for t in stmt.transactions if t.description.startswith("Check ")]


def test_a_bare_withdrawals_label_means_no_other_debits_that_period():
    stmt = parse_fifth_third_statement(document(
        summary=(
            "03/01 Beginning Balance $100.00 Number of Days in Period 31 "
            "2 Checks $(30.00) Withdrawals / Debits "
            "2 Deposits / Credits $150.00 03/31 Ending Balance $220.00"
        ),
        debits_head=None,
        daily="03/02 140.00 03/03 120.00 03/05 220.00",
    ))
    assert stmt is not None
    assert stmt.stated_total_debits == 30.00
    assert stmt.stated_debit_count == 2


def test_a_bare_label_with_its_section_still_present_is_refused():
    """Absence has to be agreed by both printings. One of them saying the
    component is absent while the other prints it is a document we do not
    understand, not a component we may guess at."""
    assert parse_fifth_third_statement(document(
        summary=(
            "03/01 Beginning Balance $100.00 Number of Days in Period 31 "
            "Checks 1 Withdrawals / Debits $(20.00) "
            "2 Deposits / Credits $150.00 03/31 Ending Balance $230.00"
        ),
        daily="03/02 150.00 03/04 130.00 03/05 230.00",
    )) is None


def test_a_component_amount_with_no_count_is_refused():
    assert parse_fifth_third_statement(document(
        summary=(
            "03/01 Beginning Balance $100.00 Number of Days in Period 31 "
            "Checks $(30.00) 1 Withdrawals / Debits $(20.00) "
            "2 Deposits / Credits $150.00 03/31 Ending Balance $200.00"
        ),
    )) is None


# ---------------------------------------------------------------------------
# One adversarial fixture per instrument
# ---------------------------------------------------------------------------

def test_instrument_1_a_summary_that_does_not_close_is_refused():
    assert parse_fifth_third_statement(document(
        summary=(
            "03/01 Beginning Balance $100.00 Number of Days in Period 31 "
            "2 Checks $(30.00) 1 Withdrawals / Debits $(20.00) "
            "2 Deposits / Credits $150.00 03/31 Ending Balance $201.00"
        ),
    )) is None


def test_instrument_2_a_section_heading_disagreeing_with_the_summary_is_refused():
    assert parse_fifth_third_statement(
        document(checks_head="Checks 3 checks totaling $30.00")
    ) is None
    assert parse_fifth_third_statement(
        document(checks_head="Checks 2 checks totaling $31.00")
    ) is None


def test_instrument_3_rows_that_do_not_match_their_own_heading_are_refused():
    assert parse_fifth_third_statement(
        document(check_rows="1001 i 03/02 10.00")
    ) is None
    assert parse_fifth_third_statement(
        document(check_rows="1001 i 03/02 10.00 1002*i 03/03 21.00")
    ) is None


def test_instrument_4_a_broken_daily_balance_walk_is_refused():
    assert parse_fifth_third_statement(
        document(daily="03/02 140.00 03/03 120.00 03/04 100.00 03/05 201.00")
    ) is None


def test_instrument_4_a_missing_daily_balance_day_is_refused():
    assert parse_fifth_third_statement(
        document(daily="03/02 140.00 03/03 120.00 03/05 200.00")
    ) is None


def test_a_document_with_no_daily_balance_summary_is_refused():
    assert parse_fifth_third_statement(document(daily="")) is None


# ---------------------------------------------------------------------------
# Printed shapes the layout really uses
# ---------------------------------------------------------------------------

def test_parenthesised_negatives_are_read_as_overdrawn_balances():
    stmt = parse_fifth_third_statement(document(
        summary=(
            "03/01 Beginning Balance $(100.00) Number of Days in Period 31 "
            "2 Checks $(30.00) 1 Withdrawals / Debits $(20.00) "
            "2 Deposits / Credits $150.00 03/31 Ending Balance $0.00"
        ),
        daily="03/02 (60.00) 03/03 (80.00) 03/04 (100.00) 03/05 0.00",
    ))
    assert stmt is not None
    assert stmt.beginning_balance == -100.00
    assert stmt.ending_balance == 0.00
    assert stmt.stated_daily_balances[0].balance == -60.00


def test_cheque_flags_are_optional_and_independent():
    stmt = parse_fifth_third_statement(
        document(check_rows="1001 03/02 10.00 1002* 03/03 20.00")
    )
    assert stmt is not None
    assert [t.description for t in stmt.transactions if t.description.startswith("Check ")] == [
        "Check 1001",
        "Check 1002",
    ]


def test_sections_are_gathered_across_page_breaks_and_reprinted_furniture():
    """The cheque grid is split over two pages, the second reprinting the
    address block before resuming under `Checks  - continued`."""
    split = document(check_rows="1001 i 03/02 10.00").replace(
        "Page 1 of 2\n\n--- Page 2 ---\n\n" + PRINT_STREAM,
        "Page 1 of 2\n\n--- Page 2 ---\n\n"
        + PRINT_STREAM
        + "\n"
        + PERIOD
        + "\nChecks  - continued\n"
        + CHECK_LEGEND
        + "\n1002*i 03/03 20.00",
    )
    stmt = parse_fifth_third_statement(split)
    assert stmt is not None
    assert len([t for t in stmt.transactions if t.description.startswith("Check ")]) == 2


def test_reprinted_page_furniture_never_leaks_into_a_section():
    """A page boundary closes whatever section was open, so the address block
    reprinted at the top of the next page cannot be read as section content."""
    noisy = document().replace(
        "--- Page 2 ---\n\n" + PRINT_STREAM,
        "--- Page 2 ---\n\n" + PRINT_STREAM + "\n" + PERIOD + "\n9999 i 03/09 99.00",
    )
    assert parse_fifth_third_statement(noisy) is not None

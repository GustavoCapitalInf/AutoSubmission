"""The Fifth Third commercial print stream (W3 §UNID-B card 5; §SCAN-A).

Every fixture here is synthetic. The layout is reproduced faithfully — the
page-repeated print-stream header, the flattened one-line account summary, the
three-up cheque grid with its flags, the `- continued` section headings and the
`Daily Balance Summary` — but no customer, account, date or amount from the
archive appears in this file.

The tests are organised around the four instruments the parser requires to
agree, one adversarial fixture per instrument, plus the summary grammar itself:
a component whose count and amount are both absent means the component is
absent, and that reading is only accepted when the detail section is absent too.

The last section covers the **scanned** issue of the same statement (§SCAN-A),
which is the same layout photographed rather than printed to PDF: no print
stream, the account summary broken one component per line, and OCR speckle
welded to the printed numbers. Each tolerance introduced for it has an
adversarial twin asserting that the corroborating printing still bites.
"""
from __future__ import annotations

from analysis.fifth_third import (
    _SUMMARY_RE,
    _SUMMARY_SPAN,
    _summary,
    detect,
    parse_fifth_third_statement,
)

PRINT_STREAM = "FTCSTMT000 000 00000000 UDSPDFSTMT 0000000000000000000 DDA"
PERIOD = (
    "Statement Period Date: 3/1/2054 - 3/31/2054 "
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


def test_does_not_claim_without_either_printing_of_the_print_product():
    """This fixture's product line does not name a `5/3` product, so removing
    the print-stream header leaves the document with neither printing of the
    evidence the `print_product` marker accepts."""
    stripped = document().replace(PRINT_STREAM, "")
    assert "Account Type: SYNTHETIC BUS CKG" in stripped
    assert not detect(stripped).claims


def test_does_not_claim_without_the_issuer_domain():
    """The folder a document was filed in is not evidence of who issued it."""
    assert not detect(document().replace("www.53.com/businessbanking", "")).claims


def test_a_custodian_disclosure_naming_the_bank_is_not_a_claim():
    """The archive's most pointed counter-example, in synthetic form.

    A third-party banking product names its custodian bank in the disclosure
    at the foot of page one — every document of one such family in the archive
    names Fifth Third, and not one of them is a Fifth Third statement. This is
    why detection keys on the print stream and the issuer's own domain rather
    than on the bank's name.
    """
    custodian = (
        "--- Page 1 ---\n\n"
        "Synthetic Balance\nStatement summary\n"
        "Starting balance $10.00\nAccount balance as of 03/31/2054 $10.00\n"
        "This product partners for money transmission services with funds held "
        "at Fifth Third Bank, Member FDIC.\n"
    )
    assert not detect(custodian).claims


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
    assert stmt.period_start == "2054-03-01"
    assert stmt.period_end == "2054-03-31"
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
        ("2054-03-02", 140.00),
        ("2054-03-03", 120.00),
        ("2054-03-04", 100.00),
        ("2054-03-05", 200.00),
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


# ===========================================================================
# The scanned issue of the same statement (§SCAN-A)
# ===========================================================================

#: The scan's page furniture. There is no print stream: what identifies the
#: document is the product the statement itself names, printed on the page and
#: therefore photographable. The leading `3` is the speck OCR habitually reads
#: off the logo block, and it is left in because the real scans carry it.
SCAN_PRODUCT = "3 Account Type: 5/3 SYNTHETIC CKG"
SCAN_PERIOD = "Statement Period Date: 3/1/2054 - 3/31/2054"
SCAN_ACCOUNT = "FIFTH THIRD Account Number: 1234567890"


def scanned_document(
    *,
    beginning: str = "03/01 Beginning Balance $100.00 Number of Days in Period 31",
    summary_components: str = (
        "2 Checks $(30.00)\n"
        "1 Withdrawals / Debits $(20.00)\n"
        "2 Deposits / Credits $150.00"
    ),
    ending: str = "03/31 Ending Balance $200.00",
    checks_head: str = "Checks 2 checks totaling $30.00",
    check_rows: str = "1001 i 03/02 10.00 1002%i 03/03 20.00",
    credits_head: str = "Deposits / Credits 2 items totaling $150.00",
    daily: tuple[str, ...] = ("03/02 140.00 03/03 120.00 03/04 100.00", "03/05 200.00"),
) -> str:
    """The same statement photographed: no print stream, and the account
    summary broken one component per printed line."""
    page_one = [
        SCAN_PERIOD,
        SCAN_PRODUCT,
        SCAN_ACCOUNT,
        "P.O. BOX 000000 SYNTHETIC CITY OH 00000-0000 Banking Center: Synthetic",
        "Account Summary - 1234567890",
        beginning,
        summary_components,
        ending,
        checks_head,
        CHECK_LEGEND,
        check_rows,
        "Withdrawals / Debits 1 items totaling $20.00",
        "Date Amount Description",
        "03/04 20.00 SYNTHETIC DEBIT",
        FOOTER + " Page 1 of 2",
    ]
    page_two = [
        "FIFTH THIRD",
        credits_head,
        "Date Amount Description",
        "03/02 50.00 SYNTHETIC DEPOSIT",
        "03/05 100.00 SYNTHETIC DEPOSIT TWO",
        "Daily Balance Summary",
        "Date Amount Date Amount Date Amount",
        *daily,
        "Page 2 of 2",
    ]
    return (
        "<!-- source: synthetic-scan.pdf | pages: 2 | model: local-tesseract-ocr | empty: 0 -->\n\n"
        "--- Page 1 ---\n\n" + "\n".join(page_one) + "\n\n"
        "--- Page 2 ---\n\n" + "\n".join(page_two) + "\n"
    )


def test_the_printed_product_line_identifies_a_scan_that_has_no_print_stream():
    assert PRINT_STREAM not in scanned_document()
    assert detect(scanned_document()).claims


def test_the_printed_product_line_alone_is_still_not_enough():
    """The product line replaces one marker, not the requirement for three."""
    assert not detect(
        f"--- Page 1 ---\n\n{SCAN_PERIOD}\n{SCAN_PRODUCT}\n{SCAN_ACCOUNT}\n"
    ).claims


def test_the_issuers_domain_is_what_holds_the_widened_marker_set_together():
    """Someone else's statement carrying BOTH of the other two markers.

    It prints `Account Summary` as its own heading and its ledger names Fifth
    Third — and the product — as the counterparty of a payment. The only thing
    withholding the claim is the issuer's own domain, which is why the product
    line was added as a second branch of `print_product` rather than as a
    loosening of `issuer_domain`.

    Not hypothetical: 55 documents in the discovery archive name Fifth Third
    without carrying `53.com`, and nine of those also print `Account Summary`
    (eight Bank of America statements and one Bluevine). Accepting the bank's
    NAME as issuer evidence would leave every one of them a single marker away
    from a wrong-parser claim.
    """
    foreign = (
        "--- Page 1 ---\n\nCOMMUNITY TRUST BANK\nStatement of Account\n"
        "Account Summary\n"
        "03/04 250.00 ACH DEBIT TO FIFTH THIRD BANK Account Type: 5/3 BUSINESS CKG\n"
    )
    assert "53.com" not in foreign.lower()
    assert not detect(foreign).claims


def test_the_scanned_layout_reads_end_to_end():
    """One summary component per printed line, and every instrument agreeing."""
    stmt = parse_fifth_third_statement(scanned_document())
    assert stmt is not None
    assert stmt.bank == "Fifth Third Bank"
    assert stmt.account_number == "1234567890"
    # The scan prints `Account Number:` on the NEXT line, in the next column,
    # so the account-type field has no terminator to read up to. None is the
    # honest reading; the alternative would splice in the logo block's text.
    assert stmt.account_name is None
    assert stmt.beginning_balance == 100.00
    assert stmt.ending_balance == 200.00
    assert stmt.stated_total_debits == 50.00
    assert stmt.stated_credit_count == 2
    assert len(stmt.transactions) == 5


def test_a_foreign_ending_balance_is_refused_by_the_closing_identity():
    """The span DOES reach a foreign close, and instrument 1 is what stops it.

    Recorded because the obvious reading of the bound is wrong, and this cell
    recorded the wrong reading first. A scan can lose the statement's own
    ending-balance line; the summary span then runs on to a later block's close
    in 188 characters — well inside the bound, with every component printed
    exactly once, so the duplicate-label refusal never fires and `_summary`
    returns this beginning balance paired with someone else's ending balance.
    What refuses the document is the walked closing identity: 100 + 150 - 30 -
    20 is 200, not 77,777.

    Instrument 4's terminal check reads the same close a second way, and
    measured against this fixture either one alone is sufficient: with
    instrument 1 deleted it is still refused, with instrument 4's terminal
    check deleted it is still refused, and with BOTH deleted the foreign
    pairing publishes with `ending_balance` 77,777.00. Two independent
    readings of one close, and neither of them is the duplicate-label refusal.

    The three assertions below are the corrected reasoning, each of them
    falsifiable: the pairing IS read (so the bound is not the fence), every
    component appears exactly once (so the duplicate-label refusal is not the
    fence), the span is inside the bound (so the bound was never consulted) —
    and the document is refused anyway.
    """
    lost_close = scanned_document().replace(
        "03/31 Ending Balance $200.00",
        "Analysis Period: 02/01/54 - 02/28/54\n"
        "Standard Monthly Service Charge $0.00\n"
        "PAPER ACCOUNT STATEMENT FEE $3.00\n"
        "03/31 Ending Balance $77,777.00",
    )
    read = _summary(lost_close)
    assert read is not None, "the span is expected to reach the foreign close"
    beginning, _, ending, components = read
    assert (beginning, ending) == (100.00, 77777.00)
    assert sorted(components) == ["Checks", "Deposits / Credits", "Withdrawals / Debits"]
    assert len(_SUMMARY_RE.search(lost_close).group(4)) < _SUMMARY_SPAN
    # ... and the document is still refused, by the identity rather than the span.
    assert parse_fifth_third_statement(lost_close) is None


def test_a_printed_day_printed_twice_is_refused_rather_than_averaged():
    """The daily walk corroborates every tolerance this parser now grants, so
    the list it walks against has to be a function of the day.

    A scan can print one day twice — a row photographed across a fold, an OCR
    pass that emits a line and then re-emits it. `by_day` is built with `dict`,
    so the LAST copy silently wins the walk and a bogus FIRST copy costs the
    walk nothing at all. It does not cost `stated_daily_balances` nothing:
    both copies are published, and the phantom lands in the balances the
    average daily balance is computed from.

    Measured with the uniqueness guard deleted, on this exact fixture: five
    printed days published instead of four, `999,999.99` among them, and the
    mean of the published closes 200,112.00 instead of 140.00. Every other
    instrument passes — the walk still reaches the printed ending balance —
    which is why this is pinned here rather than left to them.
    """
    duplicated = scanned_document(
        daily=("03/02 140.00 03/03 999999.99 03/03 120.00 03/04 100.00", "03/05 200.00")
    )
    assert parse_fifth_third_statement(duplicated) is None
    # The same document with the day printed once is read, so it is the
    # duplication being refused and not the fixture being malformed.
    assert parse_fifth_third_statement(scanned_document()) is not None


def test_the_summary_span_is_bounded_so_it_cannot_reach_a_foreign_close():
    """The middle of the summary may cross printed lines. It may not run far
    enough to pair this block's beginning balance with a later block's ending
    balance — which is the failure an unbounded `[\\s\\S]*?` would allow."""
    filler = "\n".join(f"03/{day:02d} 1.00 SYNTHETIC FILLER ROW {day}" for day in range(1, 20))
    assert len(filler) > 400
    padded = scanned_document().replace(
        "03/31 Ending Balance $200.00", filler + "\n03/31 Ending Balance $200.00"
    )
    assert parse_fifth_third_statement(padded) is None


def test_a_full_stop_welded_to_a_component_count_is_absorbed():
    """`13. Deposits / Credits` — the speck loses the count, and with it the
    document, even though the same count is printed again at the section head."""
    stmt = parse_fifth_third_statement(scanned_document(
        summary_components=(
            "2 Checks $(30.00)\n"
            "1 Withdrawals / Debits $(20.00)\n"
            "2. Deposits / Credits $150.00"
        ),
    ))
    assert stmt is not None
    assert stmt.stated_credit_count == 2


def test_the_absorbed_count_is_still_read_off_the_summary_not_the_heading():
    """The tolerance absorbs a speck; it never completes the summary from the
    section heading. A count that disagrees with its second printing refuses."""
    assert parse_fifth_third_statement(scanned_document(
        summary_components=(
            "2 Checks $(30.00)\n"
            "1 Withdrawals / Debits $(20.00)\n"
            "3. Deposits / Credits $150.00"
        ),
    )) is None


def test_a_cheque_flag_the_scan_misread_still_yields_its_row():
    """`1002%i` is a sequence-gap asterisk photographed badly. Losing the row
    would silently drop a cheque from a total the document also prints."""
    stmt = parse_fifth_third_statement(scanned_document())
    assert stmt is not None
    cheques = [t for t in stmt.transactions if t.description.startswith("Check ")]
    assert [t.description for t in cheques] == ["Check 1001", "Check 1002"]
    assert sum(t.amount for t in cheques) == -30.00


#: A third cheque whose number is separated from its paid date by a run far
#: longer than any flag cluster. Everything else about this document is
#: consistent WITH the row read: the summary closes, both printings of the
#: cheque count and total say three and $35.00, and the daily walk lands on
#: every printed close. So the only thing that can refuse it is the shape of
#: the gap — which is what makes this a test of the bound rather than a test
#: of some other instrument catching the fallout.
_THREE_CHEQUES = dict(
    summary_components=(
        "3 Checks $(35.00)\n"
        "1 Withdrawals / Debits $(20.00)\n"
        "2 Deposits / Credits $150.00"
    ),
    ending="03/31 Ending Balance $195.00",
    checks_head="Checks 3 checks totaling $35.00",
    daily=("03/02 140.00 03/03 120.00 03/04 95.00", "03/05 195.00"),
)


def test_the_glyph_tolerance_is_a_bounded_shape_not_an_open_gap():
    """Two glyphs is the flag cluster the layout prints. A longer run between
    the number and its paid date is not a flag, so the row is not admitted —
    and the section's own printed count then refuses the whole document."""
    assert parse_fifth_third_statement(scanned_document(
        check_rows="1001 i 03/02 10.00 1002%i 03/03 20.00 1003 abc 03/04 5.00",
        **_THREE_CHEQUES,
    )) is None


def test_the_bounded_shape_is_what_refuses_it_and_nothing_else():
    """The twin of the test above, and the reason it can be trusted: with the
    same third cheque printed with a real two-glyph flag cluster, every
    instrument agrees and the document is read. Without this, a bound that had
    been quietly widened would still look tested."""
    stmt = parse_fifth_third_statement(scanned_document(
        check_rows="1001 i 03/02 10.00 1002%i 03/03 20.00 1003*i 03/04 5.00",
        **_THREE_CHEQUES,
    ))
    assert stmt is not None
    assert [t.description for t in stmt.transactions if t.description.startswith("Check ")] == [
        "Check 1001",
        "Check 1002",
        "Check 1003",
    ]


def test_a_misread_cheque_row_that_breaks_the_section_total_is_refused():
    assert parse_fifth_third_statement(
        scanned_document(check_rows="1001 i 03/02 10.00 1002%i 03/03 21.00")
    ) is None


def test_an_overdrawn_scan_publishes_the_printed_daily_balances_it_averages():
    """The archive's scanned months run overdrawn, and one of them publishes a
    NEGATIVE average daily balance. That figure is only ever as good as the
    printed daily balances behind it, so the parser publishes those alongside
    it — after the day-by-day walk has had to agree with every one of them.

    Here the printed closes are read as overdrawn, and their own average is
    negative, exactly as it is on the archive document."""
    stmt = parse_fifth_third_statement(scanned_document(
        beginning="03/01 Beginning Balance $(100.00) Number of Days in Period 31",
        ending="03/31 Ending Balance $0.00",
        daily=("03/02 (60.00) 03/03 (80.00) 03/04 (100.00)", "03/05 0.00"),
    ))
    assert stmt is not None
    assert stmt.beginning_balance == -100.00
    printed = [(d.date, d.balance) for d in stmt.stated_daily_balances]
    assert printed == [
        ("2054-03-02", -60.00),
        ("2054-03-03", -80.00),
        ("2054-03-04", -100.00),
        ("2054-03-05", 0.00),
    ]
    assert sum(balance for _, balance in printed) / len(printed) < 0

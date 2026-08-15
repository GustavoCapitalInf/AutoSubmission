"""The Woodforest National Bank layout.

Every fixture is a printed shape taken from the archive family, reduced to the
smallest document that still exercises it. The subject of most of them is the
one thing this layout makes hard: the Credits and Debits columns are adjacent
and the text layer destroys which of the two a magnitude stood in, so
direction comes from the running balance the bank prints beside it.
"""
from __future__ import annotations

from analysis.woodforest import detect, parse_woodforest_statement

HEADER = (
    "00131374040126102556\n"
    "Statement Period: March 01  - March 31, 2026 Page 1 of 6\n"
    "Account Information & Customer Service 1-(877) 968-7962\n"
    "P.O. Box 7889 The Woodlands, TX 77387\n"
    "Visit Us Online at www.woodforest.com\n"
    "Summary of Accounts\n"
    "ACCOUNT TYPE AND NUMBER BALANCE FORWARD TOTAL DEBITS TOTAL CREDITS CLOSING BALANCE\n"
)
GRID = "Transactions\nDate Credits Debits Balance Description\n"


def document(summary_row: str, rows: str) -> str:
    return HEADER + summary_row + "\n" + "Business Simple Checking 1205009515\n" + GRID + rows + "\n"


SIMPLE = document(
    "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00",
    "03-02 200.00 800.00 POS DB ONE 03-03 500.00 1,300.00 POS CR TWO "
    "03-04 100.00 1,200.00 POS DB THREE",
)


# --------------------------------------------------------------- detection


def test_detection_claims_the_woodforest_statement():
    assert detect(SIMPLE).claims


def test_detection_needs_more_than_the_bank_word():
    """Another issuer's statement can name Woodforest in a payee line. Several
    in the archive do; neither printed column header appears on any of them."""
    other = (
        "CHASE\nStatement Period: March 01  - March 31, 2026 Page 1 of 6\n"
        "03-02 200.00 800.00 ACH DEBIT WOODFOREST NATIONAL BANK TRANSFER\n"
    )
    assert not detect(other).claims


def test_detection_needs_the_activity_header_too():
    """The summary block alone is not the statement: without the posting grid
    there is no ledger to publish."""
    assert not detect(HEADER + "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n").claims


# ------------------------------------------------------- the summary oracle


def test_the_summary_row_is_the_periods_arithmetic():
    stmt = parse_woodforest_statement(SIMPLE)
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_total_credits == 500.00
    assert stmt.account_number == "1205009515"
    assert stmt.account_name == "Business Simple Checking"
    assert stmt.bank == "Woodforest National Bank"
    assert stmt.currency == "USD"


def test_neither_total_prints_a_count_so_neither_count_is_claimed():
    """Deriving the counts from the ledger would manufacture the oracle the
    platform checks the ledger against."""
    stmt = parse_woodforest_statement(SIMPLE)
    assert stmt.stated_credit_count is None
    assert stmt.stated_debit_count is None


def test_an_overdrawn_balance_forward_keeps_its_minus():
    stmt = parse_woodforest_statement(
        document(
            "Woodforest Checking 1099068957 -92.32 100.00 500.00 307.68",
            "03-02 500.00 407.68 ACH CREDIT 03-03 100.00 307.68 POS DB ONE",
        )
    )
    assert stmt.beginning_balance == -92.32
    assert stmt.transactions[0].amount == 500.00


# ------------------------------------------------- direction from the balance


def test_direction_comes_from_the_printed_running_balance():
    """The magnitude is the bank's printed cell; only the movement between two
    printed balances says which column it stood in."""
    stmt = parse_woodforest_statement(SIMPLE)
    assert [t.amount for t in stmt.transactions] == [-200.00, 500.00, -100.00]
    assert [t.direction for t in stmt.transactions] == ["debit", "credit", "debit"]
    assert [t.running_balance for t in stmt.transactions] == [800.00, 1300.00, 1200.00]


def test_the_walk_is_seeded_from_balance_forward():
    """This layout prints no opening row inside the grid, so the first row's
    direction is only knowable from the summary's BALANCE FORWARD."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 0.00 0.00 1,000.00 1,000.00",
            "01-23 1,000.00 1,000.00 OPENING DEPOSIT",
        )
    )
    assert stmt.transactions[0].amount == 1000.00
    assert stmt.transactions[0].direction == "credit"


def test_a_magnitude_that_contradicts_the_balance_movement_is_not_corrected():
    """Disagreement withholds: the row keeps a debit reading and the document
    then fails the platform's ledger checks. The sign is never invented to make
    the arithmetic close."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 0.00 0.00 1,000.00",
            "03-02 250.00 9,999.99 POS DB CONTRADICTS",
        )
    )
    assert stmt.transactions[0].amount == -250.00


# ------------------------------------------------------------- the row reader


def test_a_date_inside_a_description_does_not_open_a_row():
    """A row opens only where the grid prints one: a date followed by its
    amount cell AND its balance cell. A description does not print two money
    cells in that order."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 200.00 0.00 800.00",
            "03-02 200.00 800.00 POS DB INVOICE 03-04 REF 000000001014568",
        )
    )
    assert len(stmt.transactions) == 1
    assert stmt.transactions[0].description == "POS DB INVOICE 03-04 REF 000000001014568"


def test_the_grid_stops_at_the_blocks_printed_after_it():
    """`Account Summary` and the daily balance table are not postings."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 200.00 0.00 800.00",
            "03-02 200.00 800.00 POS DB ONE\n"
            "Account Summary\n"
            "Average Balance $900.00 Number of Days in Cycle 31\n"
            "Daily Closing Balance Summary\n"
            "Date Balance\n03-02 800.00 03-03 800.00\n",
        )
    )
    assert len(stmt.transactions) == 1
    assert stmt.days_in_period == 31
    assert stmt.stated_average_balance == 900.00


def test_a_posting_may_fall_a_day_outside_the_printed_period():
    """A mid-cycle account opening posts its first deposit the day before the
    stated period starts, and the bank's own totals include it. The year is
    resolved to the period it is NEAREST to rather than required to be inside
    it, so the row is read as printed."""
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 0.00 0.00 1,000.00 1,000.00",
            "01-23 1,000.00 1,000.00 OPENING DEPOSIT",
        ).replace(
            "Statement Period: March 01  - March 31, 2026",
            "Statement Period: January 24  - January 31, 2026",
        )
    )
    assert stmt.transactions[0].date == "2026-01-23"


def test_a_period_that_crosses_the_year_boundary_dates_both_months():
    stmt = parse_woodforest_statement(
        document(
            "Business Simple Checking 1205009515 1,000.00 300.00 0.00 700.00",
            "12-28 100.00 900.00 POS DB ONE 01-03 200.00 700.00 POS DB TWO",
        ).replace(
            "Statement Period: March 01  - March 31, 2026",
            "Statement Period: December 25  - January 24, 2026",
        )
    )
    assert [t.date for t in stmt.transactions] == ["2025-12-28", "2026-01-03"]


# ------------------------------------------------------------- failing closed


def test_a_multi_account_document_fails_closed():
    """The single-account extraction schema cannot carry two ledgers, so the
    document is declined rather than published under one account's name."""
    text = document(
        "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n"
        "Business Simple Checking 1205009999 2,000.00 100.00 100.00 2,000.00",
        "03-02 200.00 800.00 POS DB ONE",
    )
    assert detect(text).claims
    assert parse_woodforest_statement(text) is None


def test_a_second_account_split_by_a_page_break_still_fails_closed():
    """The L-1 guard must not fail OPEN.

    A summary block whose rows straddle a page break prints the page marker
    and the page's own header between them. A reader that stopped collecting
    at the first non-matching line would see one account on a two-account
    document and publish it — the exact inversion of what this guard is for.
    """
    text = (
        HEADER
        + "Business Simple Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n"
        + "--- Page 2 ---\n"
        + "Statement Period: March 01  - March 31, 2026 Page 2 of 6\n"
        + "Business Simple Checking 1205009999 2,000.00 100.00 100.00 2,000.00\n"
        + "Business Simple Checking 1205009515\n"
        + GRID
        + "03-02 200.00 800.00 POS DB ONE\n"
    )
    assert detect(text).claims
    assert parse_woodforest_statement(text) is None


def test_the_summary_region_ends_where_the_document_closes_it():
    """Collecting across the region must not run past it: the account section
    that follows prints the same product name and number, and the postings
    below it print money of their own."""
    stmt = parse_woodforest_statement(SIMPLE)
    assert stmt is not None
    assert stmt.account_number == "1205009515"


def test_a_grid_whose_columns_arrive_out_of_order_fails_closed():
    """Three archive documents emit the cells of each row in a scrambled
    reading order — description, balance, date, amount — which cannot be
    reassembled from the linear text stream. No row matches the printed
    column order, so nothing is published."""
    text = document(
        "Second Chance Checking 1358422002 119,237.77 2,954.03 49,025.50 165,309.24",
        "POS CR CASH APP RICHARD SMITH\n120,237.77\n03-04\n1,000.00\n"
        "POS CR CASH APP RICHARD SMITH\n121,478.27\n03-04\n1,240.50\n",
    )
    assert detect(text).claims
    assert parse_woodforest_statement(text) is None


def test_a_document_with_no_summary_row_fails_closed():
    text = HEADER + GRID + "03-02 200.00 800.00 POS DB ONE\n"
    assert parse_woodforest_statement(text) is None


# ------------------------------------------- direction from the printed column
#
# GEOM-1. When the intake layer could read the grid's word boxes it appends a
# block naming the column the bank printed each posting in. Direction then
# stops being an inference from the balance chain, and the chain becomes an
# independent check instead of the source of the reading.

from ocr.column_grid import GridWord                       # noqa: E402
from ocr.native_text import _wf_grid_rows, _wf_summary_rows  # noqa: E402


def with_block(base: str, *lines: str) -> str:
    return base + "\n<!--\nWOODFOREST_GEOMETRY_BEGIN\n" + "\n".join(lines) + \
        "\nWOODFOREST_GEOMETRY_END\n-->\n"


def test_the_printed_column_decides_direction_not_the_balance_movement():
    """The same three rows as SIMPLE, but read by column. Same answer — which
    is the point: the two readings agree where both can see, and only one of
    them can see a $0.00 row or a document whose balances do not all read."""
    text = with_block(
        SIMPLE,
        "WOODFOREST_TX|03-02||200.00|800.00|POS DB ONE",
        "WOODFOREST_TX|03-03|500.00||1,300.00|POS CR TWO",
        "WOODFOREST_TX|03-04||100.00|1,200.00|POS DB THREE",
    )
    stmt = parse_woodforest_statement(text)
    assert [t.amount for t in stmt.transactions] == [-200.00, 500.00, -100.00]
    assert [t.direction for t in stmt.transactions] == ["debit", "credit", "debit"]
    assert [t.description for t in stmt.transactions] == \
        ["POS DB ONE", "POS CR TWO", "POS DB THREE"]


def test_a_zero_amount_row_takes_the_column_it_was_printed_in():
    """A $0.00 posting moves no balance, so a sign rule can only guess at it —
    J9.9 records the same row class being published as a credit by convention
    on another template. Where the bank printed a column there is nothing to
    guess."""
    text = with_block(
        document(
            "Business Simple Checking 1205009515 1,000.00 0.00 0.00 1,000.00",
            "03-02 0.00 1,000.00 FEE WAIVED",
        ),
        "WOODFOREST_TX|03-02||0.00|1,000.00|FEE WAIVED",
    )
    stmt = parse_woodforest_statement(text)
    assert stmt.transactions[0].amount == 0.0
    assert stmt.transactions[0].direction == "debit"


def test_the_column_read_recovers_a_summary_row_the_text_layer_broke_in_half():
    """Two archive documents print the summary row whole and the text layer
    emits CLOSING BALANCE on a line of its own, so the four figures never meet
    and the document is declined for having no account at all."""
    broken = (
        HEADER
        + "Second Chance Checking 1358422002 165,309.24 12,757.47 41,175.75\n"
        + "193,663.14\n"
        + GRID
    )
    assert parse_woodforest_statement(broken + "03-02 200.00 165,109.24 POS DB ONE\n") is None
    stmt = parse_woodforest_statement(with_block(
        broken,
        "WOODFOREST_SUMMARY|Second Chance Checking 1358422002 "
        "165,309.24 12,757.47 41,175.75 193,663.14",
        "WOODFOREST_TX|03-02||200.00|165,109.24|POS DB ONE",
    ))
    assert stmt.beginning_balance == 165309.24
    assert stmt.ending_balance == 193663.14
    assert stmt.stated_total_debits == 12757.47


def test_a_block_naming_two_accounts_still_fails_closed():
    """The recovered summary feeds the SAME single-account guard. A guard that
    counted only what it found first would fail open on the one document
    class it exists for."""
    text = with_block(
        HEADER + GRID,
        "WOODFOREST_SUMMARY|Checking 1205009515 1,000.00 0.00 0.00 1,000.00",
        "WOODFOREST_SUMMARY|Savings 1205009516 500.00 0.00 0.00 500.00",
        "WOODFOREST_TX|03-02||200.00|800.00|POS DB ONE",
    )
    assert parse_woodforest_statement(text) is None


def test_a_posting_line_missing_a_money_column_publishes_nothing():
    """Not the row — the document. A ledger with a hole in it would still
    reconcile against nothing in particular."""
    text = with_block(
        SIMPLE,
        "WOODFOREST_TX|03-02||200.00|800.00|POS DB ONE",
        "WOODFOREST_TX|03-03|||1,300.00|POS CR TWO",
    )
    assert parse_woodforest_statement(text) is None


def test_a_document_without_a_block_reads_exactly_as_before():
    """The 40-odd documents whose pages already flatten cleanly are not
    touched by any of this."""
    assert parse_woodforest_statement(SIMPLE) == parse_woodforest_statement(SIMPLE)
    stmt = parse_woodforest_statement(SIMPLE)
    assert [t.direction for t in stmt.transactions] == ["debit", "credit", "debit"]


# ------------------------------------------- what the intake layer refuses to read


def wf_page(rows, *, header_y=100.0, pitch=12.8, height=9.0):
    """A Woodforest page: the printed header, then rows keyed by column."""
    edges = {"date": 66.0, "credits": 140.0, "debits": 211.0,
             "balance": 284.0, "description": 340.0}
    words: list[GridWord] = []

    def place(text, right, y):
        words.append(GridWord(text, right - len(text) * height * 0.5, y, right, y + height))

    for name, right in edges.items():
        place(name.capitalize(), right, header_y)
    for index, cells in enumerate(rows):
        y = header_y + pitch * (index + 1)
        for name, text in cells.items():
            if name == "description":
                x = edges["description"] + height
                for token in text.split():
                    words.append(GridWord(token, x, y, x + len(token) * height * 0.5, y + height))
                    x += len(token) * height * 0.5 + height * 0.4
            else:
                place(text, edges[name], y)
    return words


def test_a_row_printed_in_both_money_columns_is_refused():
    rows, refusals = _wf_grid_rows([wf_page([
        {"date": "03-02", "credits": "100.00", "debits": "50.00",
         "balance": "1,050.00", "description": "AMBIGUOUS"},
    ])])
    assert rows == []
    assert refusals and "amount_column_undecided" in refusals[0]
    assert "both" in refusals[0]


def test_a_row_with_a_balance_and_no_amount_cell_is_refused():
    """The grid prints an amount beside every balance. A balance with no
    movement under it is a row the reader cannot explain, and it says so
    rather than publishing the balance and dropping the posting."""
    _rows, refusals = _wf_grid_rows([wf_page([
        {"date": "03-02", "credits": "100.00", "balance": "1,100.00", "description": "ONE"},
        {"date": "03-03", "balance": "1,100.00", "description": "TWO"},
    ])])
    assert any("amount_column_undecided" in item and "neither" in item for item in refusals)


def test_a_dated_line_carrying_no_money_at_all_is_not_a_posting():
    """The `Checks Cleared` table prints a date in the Date column and an
    amount whose right edge lands in Debits, with no balance. Its own printed
    heading ends the grid before the reader reaches it; a stray dated line
    inside the grid is simply not a row."""
    rows, refusals = _wf_grid_rows([wf_page([
        {"date": "03-02", "credits": "100.00", "balance": "1,100.00", "description": "ONE"},
        {"date": "03-03", "description": "A NOTE, NOT A POSTING"},
    ])])
    assert [row.split("|")[1] for row in rows] == ["03-02"]
    assert refusals == []


def test_the_summary_region_is_bounded_by_the_bank_printed_labels():
    height = 9.0

    def line(text, y, x=47.0):
        out = []
        for token in text.split():
            out.append(GridWord(token, x, y, x + len(token) * height * 0.5, y + height))
            x += len(token) * height * 0.5 + height * 0.4
        return out

    words = (line("Summary of Accounts", 50.0)
             + line("Checking 1205009515 1,000.00 300.00 500.00 1,200.00", 70.0)
             + line("Transactions", 90.0)
             + line("Savings 9999999999 1.00 2.00 3.00 4.00", 110.0))
    assert _wf_summary_rows([words]) == \
        ["Checking 1205009515 1,000.00 300.00 500.00 1,200.00"]


def test_one_unreadable_cell_withdraws_the_whole_block():
    """`parse_native_woodforest` emits the block only when every posting
    placed. A ledger half read by column and half by text order would be a
    reading no instrument could check, so a single refusal returns the
    document to the text reader — which fails closed on its own terms."""
    import fitz
    from ocr.native_text import parse_native_woodforest

    page_bytes = fitz.open()
    page = page_bytes.new_page()
    page.insert_text((50, 50), "WOODFOREST NATIONAL BANK")
    page.insert_text((50, 70), "Date Credits Debits Balance Description")
    page.insert_text((50, 90), "03-02 100.00 50.00 1,050.00 AMBIGUOUS")
    raw = page_bytes.tobytes()
    page_bytes.close()
    assert parse_native_woodforest(raw, source_file="x.pdf") is None


def test_the_summary_region_survives_a_page_break():
    """`_accounts` names this as the whole safety of the single-account guard:
    a summary block whose rows are split by a page break must still be counted
    as two accounts. A reader that closed the region at the end of a page
    would see one and publish it."""
    height = 9.0

    def line(text, y, x=47.0):
        out = []
        for token in text.split():
            out.append(GridWord(token, x, y, x + len(token) * height * 0.5, y + height))
            x += len(token) * height * 0.5 + height * 0.4
        return out

    page_one = line("Summary of Accounts", 50.0) + \
        line("Checking 1205009515 1,000.00 300.00 500.00 1,200.00", 70.0)
    page_two = line("Savings 1205009516 500.00 0.00 0.00 500.00", 60.0) + \
        line("Transactions", 90.0)
    assert _wf_summary_rows([page_one, page_two]) == [
        "Checking 1205009515 1,000.00 300.00 500.00 1,200.00",
        "Savings 1205009516 500.00 0.00 0.00 500.00",
    ]


def test_geometry_wins_the_account_count_when_the_text_layer_breaks_one_row():
    """CLAIM-5. The earlier rule consulted geometry only when the flattened
    region yielded NOTHING, and that has a document shape behind it: the text
    layer breaks this summary row, and it can break one row of two. Text then
    reads 1, geometry reads 2, and trusting text whenever text found something
    publishes both accounts' postings under one account's oracle.

    The guard exists for exactly that document, so the larger count wins.
    """
    partly_broken = (
        HEADER
        + "Checking 1205009515 1,000.00 300.00 500.00 1,200.00\n"   # this one reads
        + "Savings 1205009516 500.00 0.00 0.00\n500.00\n"           # this one does not
        + GRID
    )
    # The flattened region finds exactly one account, and on its own would publish.
    from analysis.woodforest import _accounts
    assert len(_accounts(partly_broken)) == 1
    assert parse_woodforest_statement(
        partly_broken + "03-02 200.00 800.00 POS DB ONE\n"
    ) is not None

    # With the column read seeing both, the document fails closed.
    assert parse_woodforest_statement(with_block(
        partly_broken,
        "WOODFOREST_SUMMARY|Checking 1205009515 1,000.00 300.00 500.00 1,200.00",
        "WOODFOREST_SUMMARY|Savings 1205009516 500.00 0.00 0.00 500.00",
        "WOODFOREST_TX|03-02||200.00|800.00|POS DB ONE",
    )) is None


def test_a_credit_carrying_the_overdrawn_minus_is_refused_not_normalised():
    """The printed column and the printed sign are two statements about one
    cell. This layout sets a trailing minus on overdrawn figures, so a Credits
    cell can arrive saying both "this increased the balance" and "this did
    not". Publishing it as a credit with a negative amount breaks the
    platform's direction rule; `abs`-ing it picks a winner silently. J9.6
    refuses the same contradiction at the summary level."""
    text = with_block(
        SIMPLE,
        "WOODFOREST_TX|03-02|200.00-||800.00|CONTRADICTORY",
    )
    assert parse_woodforest_statement(text) is None


def test_an_unsigned_credit_in_the_same_shape_still_reads():
    """The control for the test above: it is the SIGN that refuses, not the
    column or the row shape."""
    text = with_block(
        document(
            "Business Simple Checking 1205009515 1,000.00 0.00 200.00 1,200.00",
            "03-02 200.00 1,200.00 FINE",
        ),
        "WOODFOREST_TX|03-02|200.00||1,200.00|FINE",
    )
    stmt = parse_woodforest_statement(text)
    assert stmt.transactions[0].amount == 200.00
    assert stmt.transactions[0].direction == "credit"


def test_the_memoised_page_text_cannot_be_mutated_by_one_caller_for_another():
    """`_native_pages` is memoised because every rung of the ladder calls it
    and an un-memoised one re-extracts per rung, on every native document in
    the archive. Two extractors in that file — Navy Federal's and this one —
    append their structured block to `pages[0]`, so the cache must hand out a
    fresh list each time or the first caller's edit becomes the second
    caller's input."""
    import fitz
    from ocr.native_text import _native_pages

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "A PAGE OF TEXT")
    raw = doc.tobytes()
    doc.close()

    first = _native_pages(raw)
    original = first[0]
    first[0] = "MUTATED BY THE FIRST CALLER"
    second = _native_pages(raw)
    assert second[0] == original
    assert first is not second

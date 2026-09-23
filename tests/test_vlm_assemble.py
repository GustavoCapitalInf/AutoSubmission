from decimal import Decimal

from vlm import assemble
from vlm.tables import classify_columns

WORKER_RAW = {
    "blocks": [
        {"label": "text", "bbox": [10, 10, 500, 40], "content": "SYNTHETIC BANK  Statement Period 01/01/2031 - 01/31/2031", "order": 0},
        {"label": "table", "bbox": [10, 50, 700, 300], "order": 1, "content": (
            "<table><tr><th>Date</th><th>Description</th><th>Amount</th><th>Balance</th></tr>"
            "<tr><td>01/01</td><td>SYNTHETIC ROW 01</td><td>10.00</td><td>510.00</td></tr>"
            "<tr><td></td><td>continued text</td><td></td><td></td></tr>"
            "<tr><td>01/02</td><td>SYNTHETIC ROW 02</td><td>-5.00</td><td>505.00</td></tr>"
            "<tr><td>01/03</td><td>Total</td><td>5.00</td><td></td></tr></table>")},
    ],
}


def test_blocks_from_worker_normalises_boxes():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    assert [b.label for b in blocks] == ["text", "table"]
    assert blocks[0].bbox == (0.01, 0.005, 0.5, 0.02) and blocks[0].page == 0


def test_rows_from_blocks_with_continuation_and_totals():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    rows = assemble.rows_from_blocks(blocks, year_hint=2031)
    assert len(rows) == 2
    first, second = rows
    assert first.date == "2031-01-01" and first.description == "SYNTHETIC ROW 01 continued text"
    assert first.amount == Decimal("10.00") and first.direction == "unknown" and first.balance == Decimal("510.00")
    assert second.amount == Decimal("5.00") and second.direction == "debit" and second.direction_source == "printed"
    assert first.locator == "t0r1" and first.source == "stage_a" and first.page == 0


def test_rows_from_grid_debit_credit_columns_and_date_carry():
    grid = [["Date", "Description", "Debits", "Credits", "Balance"],
            ["01/02", "A", "", "10.00", "510.00"],
            ["", "B", "5.00", "", "505.00"]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=3, year_hint=2031)
    assert [(r.date, r.direction, r.direction_source, r.amount) for r in rows] == [
        ("2031-01-02", "credit", "column", Decimal("10.00")), ("2031-01-02", "debit", "column", Decimal("5.00"))]
    assert rows[1].date_text == "" and rows[1].locator == "t3r2"


def test_an_account_analysis_table_is_charges_not_transactions():
    grid = [["Description", "Volume", "Amount"], ["FABRICATED ITEMS PROCESSED", "40", "20.00"],
            ["FABRICATED MONTHLY SERVICE", "1", "15.00"]]
    assert assemble.rows_from_grid(grid, classify_columns(grid), page=4, table_index=0, year_hint=2031) == []
    priced = [["Service", "Quantity", "Unit Price", "Amount"], ["FABRICATED WIRE", "2", "15.00", "30.00"]]
    assert assemble.rows_from_grid(priced, classify_columns(priced), page=4, table_index=0) == []


def test_a_dated_activity_table_with_a_quantity_column_is_transactions():
    grid = [["Date", "Description", "Quantity", "Amount", "Balance"],
            ["01/02", "FABRICATED FUND PURCHASE", "10", "-100.00", "900.00"]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031)
    assert [(row.amount, row.balance) for row in rows] == [(Decimal("100.00"), Decimal("900.00"))]


def test_a_description_that_names_a_store_is_not_a_header():
    # "OFFICE DEPOT" in a headerless table's data row once read as a French "Dépôts" header (review 4).
    grid = [["01/02", "FABRICATED OFFICE DEPOT", "Debit", "25.00", "975.00"],
            ["01/03", "FABRICATED RETRAIT GAB", "Debit", "40.00", "935.00"]]
    columns = classify_columns(grid)
    assert columns.header_row is None or columns.header_row != 0


def _cell(category, box, text):
    return {"category": category, "bbox": box, "text": text}


def test_a_layout_with_one_block_per_cell_still_reads_as_rows():
    # dots.mocr sometimes returns a table as one Text block per cell (Citizens): Date | Amount | Description.
    layout = [_cell("Section-header", [150, 670, 400, 720], "Other Debits"),
              _cell("Text", [150, 740, 250, 780], "04/01"), _cell("Text", [470, 740, 620, 780], "1,582.44"),
              _cell("Text", [680, 740, 1500, 780], "FABRICATED LENDER 7 11111"),
              _cell("Text", [150, 790, 250, 830], "04/01"), _cell("Text", [520, 790, 620, 830], "35.00"),
              _cell("Text", [680, 790, 1080, 830], "RETURNED ITEM FEE"),
              _cell("Text", [680, 840, 890, 880], "( 1 AT $35 )"),
              _cell("Section-header", [150, 950, 400, 1000], "Deposits & Credits"),
              _cell("Text", [150, 1020, 250, 1060], "04/02"), _cell("Text", [470, 1020, 620, 1060], "2,961.35"),
              _cell("Text", [680, 1020, 1400, 1060], "FABRICATED PAYMENT 260101")]
    import json
    rows = assemble.parse_dots_layout(json.dumps(layout), page=2, width=2550, height=3300, year_hint=2031).rows
    assert [(row.date, row.amount, row.direction, row.description) for row in rows] == [
        ("2031-04-01", Decimal("1582.44"), "debit", "FABRICATED LENDER 7 11111"),
        ("2031-04-01", Decimal("35.00"), "debit", "RETURNED ITEM FEE ( 1 AT $35 )"),
        ("2031-04-02", Decimal("2961.35"), "credit", "FABRICATED PAYMENT 260101")]
    assert len({row.locator for row in rows}) == 3


def test_a_table_opening_with_a_section_title_across_its_columns_reads_under_its_real_header():
    table = ("<table><tr><td>Deposits &amp; Credits</td><td>Deposits &amp; Credits</td><td>Deposits &amp; Credits</td>"
             "<td>Total Deposits &amp; Credits</td></tr>"
             "<tr><td>Date</td><td>Amount</td><td>Description</td><td>58,236.90</td></tr>"
             "<tr><td>04/01</td><td>2,961.35</td><td>FABRICATED PAYMENT</td><td></td></tr></table>")
    import json
    layout = [{"category": "Table", "bbox": [100, 100, 2400, 900], "text": table}]
    rows = assemble.parse_dots_layout(json.dumps(layout), page=3, width=2550, height=3300, year_hint=2031).rows
    assert [(row.amount, row.direction, row.description) for row in rows] == [
        (Decimal("2961.35"), "credit", "FABRICATED PAYMENT")]


def test_a_note_under_a_section_heading_keeps_the_sections_direction():
    table = ("<table><tr><th>Date</th><th>Amount</th><th>Description</th></tr>"
             "<tr><td>04/23</td><td>175.00</td><td>FABRICATED FEE</td></tr></table>")
    note = ("**May include checks that have been processed electronically by the payee or merchant, and other "
            "fabricated wording that runs well past a heading's length.")
    import json
    layout = [{"category": "Section-header", "bbox": [100, 100, 900, 150], "text": "Debits (Continued)"},
              {"category": "Text", "bbox": [100, 160, 2400, 200], "text": note},
              {"category": "Table", "bbox": [100, 220, 2400, 900], "text": table}]
    rows = assemble.parse_dots_layout(json.dumps(layout), page=3, width=2550, height=3300, year_hint=2031).rows
    assert [(row.amount, row.direction) for row in rows] == [(Decimal("175.00"), "debit")]


def test_deductions_and_purchases_sections_are_debits():
    for heading in ("ACH Deductions", "Other Deductions", "Card Purchases"):
        assert assemble.section_direction(heading) == "debit", heading


def test_text_lines_from_blocks():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    lines = assemble.text_lines_from_blocks(blocks)
    assert lines and lines[0].startswith("SYNTHETIC BANK")


def test_unmappable_table_yields_no_rows():
    blocks = [assemble.Block("table", (0, 0, 1, 1), "<table><tr><td>a</td><td>b</td></tr></table>", 0, 0)]
    assert assemble.rows_from_blocks(blocks) == []


def test_section_heading_gives_a_single_amount_table_its_direction():
    from decimal import Decimal
    table = ("<table><tr><th>Date</th><th>Description</th><th>Amount</th></tr>"
             "<tr><td>01/03</td><td>CHECK 101</td><td>25.00</td></tr></table>")
    blocks = [assemble.Block("paragraph_title", (0, 0, 1, 0.1), "Checks Paid", 0, 0),
              assemble.Block("table", (0, 0.1, 1, 0.5), table, 1, 0),
              assemble.Block("paragraph_title", (0, 0.5, 1, 0.6), "Deposits and Other Credits", 2, 0),
              assemble.Block("table", (0, 0.6, 1, 0.9), table.replace("CHECK 101", "DEPOSIT"), 3, 0),
              assemble.Block("text", (0, 0.9, 1, 0.95), "Deposits and withdrawals summary", 4, 0),
              assemble.Block("table", (0, 0.95, 1, 1.0), table, 5, 0)]
    rows = assemble.rows_from_blocks(blocks, year_hint=2031)
    assert [(r.direction, r.direction_source) for r in rows] == [("debit", "section"), ("credit", "section"), ("unknown", "printed")]
    assert rows[0].amount == Decimal("25.00")
    assert assemble.section_direction("Withdrawals and other debits") == "debit" and assemble.section_direction("Summary") is None


def test_a_row_written_without_its_empty_date_cell_is_put_back_in_its_columns():
    # A date printed once for the day: the proposer wrote the day's later rows one cell short, every cell one
    # column left (a credit in the debit column, a balance as the credit).
    from vlm.tables import classify_columns
    grid = [["Date", "Description", "Withdrawals ($)", "Deposits ($)", "Balance ($)"],
            ["29 Dec", "FABRICATED PAYMENT", "", "412.60", ""],
            ["FABRICATED CHEQUE - 101", "97.00", "", "1,315.60"],
            ["FABRICATED DEPOSIT", "", "46.15", "1,361.75"]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031,
                                   day_first=True)
    assert [(row.description, row.amount, row.direction, row.balance) for row in rows] == [
        ("FABRICATED PAYMENT", Decimal("412.60"), "credit", None),
        ("FABRICATED CHEQUE - 101", Decimal("97.00"), "debit", Decimal("1315.60")),
        ("FABRICATED DEPOSIT", Decimal("46.15"), "credit", Decimal("1361.75"))]
    assert [row.date_text for row in rows] == ["29 Dec", "", ""]


def test_a_row_short_of_another_cell_whose_first_cell_is_a_compact_date_stays_as_written():
    # Review finding 1: a trailing empty balance cell omitted, the first cell a compact printed date ("DEC31"):
    # putting an empty date in front would slide a withdrawal into the deposits column.
    from vlm.tables import classify_columns
    header = ["Date", "Description", "Withdrawals", "Deposits", "Balance"]
    for date_text in ("DEC31", "Mar05", "5-Mar", "05-MAR-26", "03.05.2026", "2026/03/05"):
        grid = [header, [date_text, "FABRICATED CARD PAYMENT", "50.00", ""]]
        rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031)
        assert [(row.amount, row.direction) for row in rows] == [(Decimal("50.00"), "debit")], date_text
    # A restored row must read as a row: a figure where the description goes, or text in a money column,
    # leaves the row as written.
    grid = [header, ["FABRICATED NOTE", "SEE REVERSE", "", "1,315.60"]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031)
    assert all(row.date_text != "" or row.description != "FABRICATED NOTE" for row in rows)


def test_a_same_day_cheque_or_a_continuation_line_written_one_cell_short_is_put_back():
    # Review 5 follow-up: a cheque number is a description, not a figure; a continuation line prints no amount.
    from vlm.tables import classify_columns
    grid = [["Date", "Check #", "Amount"], ["01/05", "1032", "400.00"], ["1033", "500.00"]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031)
    assert [(row.description, row.amount, row.date_text) for row in rows] == [
        ("1032", Decimal("400.00"), "01/05"), ("1033", Decimal("500.00"), "")]
    grid = [["Date", "Description", "Withdrawals", "Deposits", "Balance"],
            ["01/05", "FABRICATED TRANSFER TO", "75.00", "", "925.00"], ["FABRICATED SAVINGS 0001", "", "", ""]]
    rows = assemble.rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031)
    assert [row.description for row in rows] == ["FABRICATED TRANSFER TO FABRICATED SAVINGS 0001"]


def test_a_k_up_table_does_not_carry_a_date_from_the_neighbouring_column_group():
    from vlm.tables import classify_columns, unfold_side_by_side
    grid = [["DATE", "CHECK #", "AMOUNT($)"] * 2,
            ["03/23", "301", "81.40", "", "302", "46.15"]]
    unfolded = unfold_side_by_side(grid)
    rows = assemble.rows_from_grid(unfolded, classify_columns(unfolded), page=1, table_index=0, year_hint=2031,
                                   carry_dates=False)
    assert [(row.description, row.date) for row in rows] == [("301", "2031-03-23"), ("302", None)]
    assert all(row.side_by_side for row in rows)

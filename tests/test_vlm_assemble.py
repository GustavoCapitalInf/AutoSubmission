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


def test_text_lines_from_blocks():
    blocks = assemble.blocks_from_worker(WORKER_RAW, page=0, width=1000, height=2000)
    lines = assemble.text_lines_from_blocks(blocks)
    assert lines and lines[0].startswith("SYNTHETIC BANK")


def test_unmappable_table_yields_no_rows():
    blocks = [assemble.Block("table", (0, 0, 1, 1), "<table><tr><td>a</td><td>b</td></tr></table>", 0, 0)]
    assert assemble.rows_from_blocks(blocks) == []

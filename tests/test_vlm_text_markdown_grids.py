"""Fabricated coverage; customer-receipt regressions run outside the checkout."""
import json
from decimal import Decimal

from vlm.assemble import parse_dots_layout


def test_markdown_grid_in_multiline_text_preserves_cells_and_source_category():
    text = (
        "| Date | Description | Ref Number | Amount |\n"
        "| --- | --- | --- | --- |\n"
        "| 01/02 | FABRICATED  first merchant | 123456 | 10.25 |\n"
        "| 01/03 | FABRICATED second merchant | 789012 | 20.50 |"
    )
    layout = parse_dots_layout(json.dumps([
        {"category": "Section-header", "bbox": [0, 0, 100, 10], "text": "Withdrawals"},
        {"category": "Text", "bbox": [0, 10, 100, 90], "text": text},
    ]), page=3, width=100, height=100)
    assert not layout.errors and len(layout.rows) == 2
    assert layout.blocks[1].label == "text" and layout.blocks[1].content == text
    assert [row.amount for row in layout.rows] == [Decimal("10.25"), Decimal("20.50")]
    assert [row.description for row in layout.rows] == [
        "FABRICATED  first merchant 123456", "FABRICATED second merchant 789012"]
    assert [row.date_text for row in layout.rows] == ["01/02", "01/03"]
    assert [row.locator for row in layout.rows] == ["b1t0r1", "b1t0r2"]
    assert all(row.page == 3 and row.direction == "debit" for row in layout.rows)


def test_plain_multiline_text_still_tests_each_line_independently():
    layout = parse_dots_layout(json.dumps([
        {"category": "Text", "bbox": [0, 0, 100, 100],
         "text": "FABRICATED heading\n01/02 FABRICATED first 10.25\n01/03 FABRICATED second 20.50"}
    ]), page=1, width=100, height=100)
    assert len(layout.rows) == 2
    assert [row.locator for row in layout.rows] == ["b0l1", "b0l2"]


def test_a_pipe_in_ordinary_text_does_not_suppress_plain_date_lines():
    layout = parse_dots_layout(json.dumps([
        {"category": "Text", "bbox": [0, 0, 100, 100],
         "text": "FABRICATED heading\n01/02 FABRICATED reference | merchant 10.25"}
    ]), page=1, width=100, height=100)
    assert len(layout.rows) == 1 and layout.rows[0].locator == "b0l1"


def test_plain_date_line_with_a_pipe_requires_no_markdown_interpretation():
    layout = parse_dots_layout(json.dumps([
        {"category": "Text", "bbox": [0, 0, 100, 100],
         "text": "01/02 FABRICATED reference | merchant 10.25"}
    ]), page=1, width=100, height=100)
    assert len(layout.rows) == 1 and layout.rows[0].locator == "b0l0"

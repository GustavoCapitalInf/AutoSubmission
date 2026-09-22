"""Fabricated page-opening evidence; no model calls or customer values."""
from dataclasses import replace

import pytest

from vlm.assemble import parse_dots_layout
from vlm.segment_openings import extract_printed_opening


def layout(opening="BALANCE FORWARD", value="100.00", extra="", *, position="before"):
    header = "<tr><th>Description</th><th>Debit</th><th>Credit</th><th>Date</th><th>Balance</th></tr>"
    anchor = f"<tr><td>{opening}</td><td>{extra}</td><td></td><td></td><td>{value}</td></tr>"
    transaction = "<tr><td>FABRICATED PURCHASE</td><td>10.00</td><td></td><td>01/02</td><td>90.00</td></tr>"
    body = anchor + transaction if position == "before" else transaction + anchor
    return parse_dots_layout([{"category": "Table", "bbox": [0, 0, 100, 100],
                               "text": "<table>" + header + body + "</table>"}],
                             page=1, width=100, height=100)


@pytest.mark.parametrize("label", ["BALANCE FORWARD", "Beginning Balance:", "opening balance", "BALANCE BROUGHT FORWARD"])
def test_unique_explicit_label_before_rows_is_bound_to_source(label):
    source = layout(label)
    observed = extract_printed_opening(source, evidence_sha256="a" * 64)
    assert observed["value"] == 100 and observed["page"] == 1
    assert observed["locator"] == "b0t0r1"
    assert observed["evidence_sha256"] == "a" * 64
    assert observed["source"] == "stage_a_printed_opening"


@pytest.mark.parametrize("source", [
    layout("FABRICATED LABEL"), layout(extra="1.00"), layout(value=""),
    layout(position="after"), replace(layout(), errors=("layout_invalid_json",)),
    replace(layout(), truncated=True), replace(layout(), rows=()),
    replace(layout(), rows=tuple(replace(row, locator="crop0/row0") for row in layout().rows)),
    replace(layout(), blocks=layout().blocks + layout().blocks),
])
def test_ambiguous_failed_or_unbound_openings_cannot_supply_anchor(source):
    assert extract_printed_opening(source, evidence_sha256="a" * 64) is None


def test_invalid_source_hash_is_refused():
    assert extract_printed_opening(layout(), evidence_sha256="invalid") is None


def test_compact_date_in_date_column_is_not_a_second_money_cell():
    source = layout()
    block = source.blocks[0]
    block = replace(block, content=block.content.replace(
        "<td>BALANCE FORWARD</td><td></td><td></td><td></td>",
        "<td>BALANCE FORWARD</td><td></td><td></td><td>JAN01</td>"))
    source = replace(source, blocks=(block,))
    assert extract_printed_opening(source, evidence_sha256="a" * 64)["value"] == 100

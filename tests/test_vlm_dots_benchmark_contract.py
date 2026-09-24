"""Fabricated layouts for the restored full dots.mocr benchmark prompt."""
from decimal import Decimal
import json

import pytest

from vlm.assemble import parse_dots_layout
from vlm.prompts import STAGE_A_DOTS_PROMPT, prompt_sha256


TABLE = (
    '<table><tr><th>Date</th><th>Description</th><th>Credit</th></tr>'
    '<tr><td>2031-01-02</td><td>SYNTHETIC  exact &amp; literal</td><td>12.34</td></tr>'
    '</table>'
)


def _block(category, text=None, *, box=None):
    result = {"category": category, "bbox": box or [0, 0, 200, 100]}
    if text is not None:
        result["text"] = text
    return result


def _parse(raw, *, finish_reason="stop"):
    return parse_dots_layout(raw, page=3, width=200, height=400, finish_reason=finish_reason)


def test_full_benchmark_prompt_exact_hash():
    assert len(STAGE_A_DOTS_PROMPT) == 887
    assert prompt_sha256(STAGE_A_DOTS_PROMPT) == (
        "fae8e6aafb9682d0501ad64372db852d179b23f99de60198ef4a58b1468235d5"
    )


@pytest.mark.parametrize("encoded", [False, True])
def test_table_html_in_existing_list_contract_is_preserved_and_parsed(encoded):
    blocks = [_block("Table", TABLE)]
    layout = _parse(json.dumps(blocks) if encoded else blocks)
    assert not layout.errors and not layout.truncated
    assert len(layout.blocks) == 1 and layout.blocks[0].content == TABLE
    assert layout.blocks[0].bbox == (0, 0, 1, .25)
    assert len(layout.rows) == 1
    row = layout.rows[0]
    assert row.description == "SYNTHETIC  exact & literal"
    assert row.amount == Decimal("12.34") and row.direction == "credit"
    assert row.printed_amount == Decimal("12.34")
    assert row.date == "2031-01-02" and row.locator == "b0t0r1"
    assert row.page == 3 and row.bbox == layout.blocks[0].bbox


@pytest.mark.parametrize("encoded", [False, True])
def test_single_layout_object_uses_the_existing_element_validation(encoded):
    block = _block("Table", TABLE)
    layout = _parse(json.dumps(block) if encoded else block)
    assert layout == _parse([block])
    assert not layout.errors and len(layout.rows) == 1


@pytest.mark.parametrize("wrapper", ["blocks", "elements", "layout", "result"])
def test_unknown_object_envelopes_are_not_guessed_or_silently_unwrapped(wrapper):
    layout = _parse(json.dumps({wrapper: [_block("Table", TABLE)]}))
    assert layout.errors == ("layout_not_array",)
    assert not layout.blocks and not layout.rows


@pytest.mark.parametrize("block,error", [
    ({"category": 7, "bbox": [0, 0, 200, 100], "text": TABLE}, "layout_element_invalid:0"),
    ({"category": "Table", "bbox": [0, 0, 201, 100], "text": TABLE}, "layout_box_invalid:0"),
    ({"category": "Table", "bbox": [0, 0, 200, 100]}, "layout_element_invalid:0"),
])
def test_single_layout_object_cannot_bypass_required_fields_or_box_validation(block, error):
    layout = _parse(json.dumps(block))
    assert layout.errors == (error,)
    assert not layout.blocks and not layout.rows


@pytest.mark.parametrize("category,text", [
    ("Caption", "**SYNTHETIC caption**"),
    ("Footnote", "_SYNTHETIC footnote_"),
    ("List-item", "- SYNTHETIC list item"),
    ("Page-footer", "SYNTHETIC footer"),
    ("Page-header", "# SYNTHETIC header"),
    ("Section-header", "## SYNTHETIC section"),
    ("Text", "SYNTHETIC  exact text\n\n**source formatting**"),
    ("Title", "# SYNTHETIC title"),
    ("Formula", r"\(x^2 + y^2 = z^2\)"),
])
def test_non_table_markdown_and_latex_are_retained_verbatim(category, text):
    layout = _parse(json.dumps([_block(category, text)]))
    assert not layout.errors and not layout.truncated
    assert len(layout.blocks) == 1 and not layout.rows
    assert layout.blocks[0].content == text
    assert layout.blocks[0].label == category.lower().replace("-", "_")


def test_picture_omitted_text_and_reading_order_remain_supported():
    blocks = [
        _block("Title", "# SYNTHETIC title", box=[0, 0, 200, 40]),
        _block("Picture", box=[0, 40, 200, 80]),
        _block("Table", TABLE, box=[0, 80, 200, 180]),
    ]
    layout = _parse(json.dumps(blocks))
    assert not layout.errors and not layout.truncated
    assert [block.order for block in layout.blocks] == [0, 1, 2]
    assert [block.label for block in layout.blocks] == ["title", "picture", "table"]
    assert layout.blocks[1].content == ""
    assert layout.rows[0].locator == "b2t0r1"


def test_complete_json_at_length_finish_remains_truncated():
    layout = _parse(json.dumps([_block("Table", TABLE)]), finish_reason="length")
    assert layout.truncated and "stage_a_truncated" in layout.errors
    assert len(layout.rows) == 1


def test_single_object_at_length_finish_keeps_candidates_and_truncation():
    layout = _parse(json.dumps(_block("Table", TABLE)), finish_reason="length")
    assert layout.truncated and layout.errors == ("stage_a_truncated",)
    assert len(layout.rows) == 1


def test_incomplete_object_is_never_repaired_to_fit_the_prompt_contract():
    raw = json.dumps(_block("Table", TABLE))[:-1]
    layout = _parse(raw, finish_reason="length")
    assert layout.truncated
    assert layout.errors == ("stage_a_truncated", "layout_invalid_json")
    assert not layout.blocks and not layout.rows

"""Synthetic format regressions; SVG drawings never become OCR evidence."""
import json

import pytest

from vlm.assemble import parse_dots_layout


SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500">'
       '<rect width="500" height="500" fill="white"/>'
       '<path d="M 10 20 L 30 40"/>'
       '<text x="20" y="30">01/02 FABRICATED Merchant 10.00</text></svg>')


@pytest.mark.parametrize('raw', [SVG, SVG.replace('svg', 'SVG'),
                                '<?xml version="1.0"?>\n' + SVG,
                                '```svg\n' + SVG + '\n```',
                                '```SVG\n' + SVG + '\n```'])
def test_complete_svg_is_explicitly_refused_instead_of_misreported_as_json_damage(raw):
    layout = parse_dots_layout(raw, page=4, width=100, height=100, finish_reason='stop')
    assert layout.page == 4 and layout.errors == ('layout_unsupported_svg',)
    assert layout.blocks == () and layout.rows == () and layout.truncated is False


def test_incomplete_repeated_svg_keeps_truncation_and_unsupported_format_refusals():
    raw = '<svg width="500" height="500">' + '<text x="0" y="0">SYNTHETIC</text>' * 30
    layout = parse_dots_layout(raw, page=7, width=100, height=100, finish_reason='length')
    assert layout.errors == ('stage_a_truncated', 'layout_unsupported_svg')
    assert layout.truncated and not layout.blocks and not layout.rows


def test_complete_svg_at_token_limit_still_refuses_both_format_and_truncation():
    layout = parse_dots_layout(SVG, page=7, width=100, height=100, finish_reason='length')
    assert layout.errors == ('stage_a_truncated', 'layout_unsupported_svg')
    assert layout.truncated and not layout.rows


def test_truncated_json_is_not_repaired_or_salvaged():
    raw = '[{"category":"Text","bbox":[0,0,100,100],"text":"01/02 SYNTHETIC 10.00'
    layout = parse_dots_layout(raw, page=1, width=100, height=100, finish_reason='length')
    assert layout.errors == ('stage_a_truncated', 'layout_invalid_json')
    assert layout.truncated and not layout.blocks and not layout.rows


def test_incidental_svg_inside_a_valid_layout_remains_literal_source_content():
    raw = json.dumps([{'category': 'Picture', 'bbox': [0, 0, 100, 100], 'text': SVG}])
    layout = parse_dots_layout(raw, page=4, width=100, height=100, finish_reason='stop')
    assert not layout.errors and not layout.rows
    assert len(layout.blocks) == 1 and layout.blocks[0].content == SVG


def test_invalid_json_does_not_extract_an_embedded_complete_layout():
    raw = 'SYNTHETIC commentary [{"category":"Text","bbox":[0,0,100,100],"text":"01/02 SYNTHETIC 10.00"}]'
    layout = parse_dots_layout(raw, page=1, width=100, height=100, finish_reason='stop')
    assert layout.errors == ('layout_invalid_json',) and not layout.rows

"""Reason-reporting metadata uses fabricated values and mocked readers only."""
from copy import deepcopy
import io
import json
from types import SimpleNamespace

import pytest

from tools.phase3_pair.check_synthetic import reason_count_report
from tools.phase3_pair import check_judgment


def _gate():
    return {'admitted': False, 'reasons': ['date_unparsed', 'currency_missing'], 'reason_counts': {
        'date_unparsed': {'count': 5, 'pages': [{'page': 3, 'count': 2}, {'page': 1, 'count': 3}],
                          'document_count': 0},
        'currency_missing': {'count': 1, 'pages': [], 'document_count': 1},
    }}


def test_counter_report_copies_metadata_and_counts_occurrences_not_reason_codes():
    gate = _gate()
    gate['reason_counts']['date_unparsed']['source_text'] = 'FABRICATED HIDDEN'
    report = reason_count_report(gate)
    assert report['gate_reason_count'] == 6
    assert report['gate_reason_counts']['date_unparsed']['pages'] == [
        {'page': 1, 'count': 3}, {'page': 3, 'count': 2}]
    assert report['gate_reason_counts']['currency_missing']['document_count'] == 1
    assert 'FABRICATED' not in json.dumps(report)
    assert reason_count_report({'reasons': [], 'reason_counts': {}}) == {
        'gate_reason_count': 0, 'gate_reason_counts': {}}


@pytest.mark.parametrize('gate', [
    {'reasons': ['date_unparsed']},
    {'reasons': ['date_unparsed'], 'reason_counts': {}},
    {'reasons': ['FABRICATED SOURCE'], 'reason_counts': {'FABRICATED SOURCE': {}}},
    {'reasons': ['date_unparsed'], 'reason_counts': {'date_unparsed': {
        'count': True, 'pages': [], 'document_count': 1}}},
    {'reasons': ['date_unparsed'], 'reason_counts': {'date_unparsed': {
        'count': 9, 'pages': [], 'document_count': 1}}},
])
def test_unavailable_legacy_or_invalid_counts_are_never_guessed(gate):
    assert reason_count_report(gate) == {'gate_reason_count': None, 'gate_reason_counts': None}


@pytest.mark.parametrize('legacy', [False, True])
def test_judgment_console_keeps_counts_and_page_mapping_without_source_values(tmp_path, monkeypatch, legacy):
    gate = deepcopy(_gate())
    if legacy:
        gate.pop('reason_counts')
    pair = {'gate': gate, 'confidence': {'counts': {'unresolved': 5}}, 'row_evidence': [],
            'statement': None, 'field_evidence': []}
    document = SimpleNamespace(source_file='FABRICATED PATH', model='FABRICATED MODEL',
                               pages=['FABRICATED PAGE'], page_integrity=[], visual_pair=pair)
    monkeypatch.setattr(check_judgment, 'sha256_file', lambda path: 'f' * 64)
    monkeypatch.setattr(check_judgment, '_write_private', lambda *args: None)
    monkeypatch.setattr(check_judgment, '_native_pages', lambda path: [])
    monkeypatch.setattr('vlm.pair.extract_visual_pair', lambda *a, **k: document)
    monkeypatch.setattr('vlm.pair_adapter.analyze_visual_pair', lambda *a, **k: pytest.fail('analysis reached'))
    console = io.StringIO()
    result = check_judgment._run_document({'id': 'J01', 'path': tmp_path / 'unused.pdf', 'sha256': 'f' * 64},
                                         output=tmp_path, evidence=tmp_path, settings=object(), console=console)
    assert result['gate_reason_count'] == (None if legacy else 6)
    assert result['gate_reason_counts'] == (None if legacy else reason_count_report(gate)['gate_reason_counts'])
    printed = console.getvalue()
    assert json.loads(printed)['gate_reason_count'] == (None if legacy else 6)
    assert 'FABRICATED' not in printed and str(tmp_path) not in printed

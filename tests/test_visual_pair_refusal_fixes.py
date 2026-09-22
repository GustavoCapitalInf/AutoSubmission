"""Fabricated row payloads and mocked transports; no real page or model reads."""
from copy import deepcopy

import pytest

from tests.test_visual_pair_pipeline import LAYOUT, _review, wired
from vlm.client import ChatResult
from vlm.currency import CurrencyResolution
from vlm.receipts import canonical_json, sha256_bytes
from vlm.render import RenderedPage


@pytest.mark.parametrize('bad_pages', [{1}, {2}, {2, 3}])
@pytest.mark.parametrize('failure', ['truncated', 'errored'])
def test_incomplete_pages_do_not_invalidate_other_pages(wired, monkeypatch, bad_pages, failure):
    pair, pdf, directory, calls, _ = wired
    pages = [RenderedPage(i, 100, 100, f'synthetic-page-{i+1}'.encode(),
                          sha256_bytes(f'synthetic-page-{i+1}'.encode()), 'pixels', 72, 72, 0, 0, 0)
             for i in range(3)]
    monkeypatch.setattr('vlm.render.render_pages', lambda *a, **kw: pages)

    def chat(self, model, prompt, **kwargs):
        page = next(p.index + 1 for p in pages if p.jpeg == kwargs['image_jpeg'])
        calls.append((model, kwargs))
        if self.is_a:
            obj = deepcopy(LAYOUT)
            for item in obj:
                item['text'] = item['text'].replace('EXACT', f'PAGE {page} EXACT')
            if page in bad_pages and failure == 'errored':
                obj.append({'bbox': [100, 100, 0, 0], 'category': 'Text', 'text': 'SYNTHETIC BAD BOX'})
            parsed = None
        else:
            obj = _review()
            for item in obj['reviews']:
                item['candidate_id'] = item['candidate_id'].replace('p1r', f'p{page}r')
                item['observed_description'] = item['observed_description'].replace('EXACT', f'PAGE {page} EXACT')
            parsed = obj
        text = canonical_json(obj)
        request = canonical_json({'model': model, 'page': page}).encode()
        raw = text.encode()
        finish = 'length' if self.is_a and page in bad_pages and failure == 'truncated' else 'stop'
        return ChatResult(text, parsed, None, finish, 10, 30, 1,
                          sha256_bytes(request), sha256_bytes(raw), sha256_bytes(raw), request, raw)

    monkeypatch.setattr(pair.VlmClient, 'chat', chat)
    audit = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic').visual_pair
    assert audit['statement'] is None and not audit['gate']['admitted']
    assert audit['gate']['reasons'] == ['page_unresolved']
    assert audit['gate']['checks']['document_checks_deferred']
    assert audit['gate']['reason_counts']['page_unresolved'] == {
        'count': len(bad_pages), 'document_count': 0,
        'pages': [{'page': p, 'count': 1} for p in sorted(bad_pages)],
    }
    for page in audit['pages']:
        bad = page['page'] in bad_pages
        assert page['review_status'] == ('unresolved' if bad else 'reviewed')
        assert page['counts']['unresolved'] == (2 if bad else 0)
        assert page['counts']['agreed'] == (0 if bad else 2)
        assert bool(page['reason_counts']) is bad
    for row in audit['row_evidence']:
        assert row['state'] == ('unresolved' if row['page'] in bad_pages else 'agreed')


def test_currency_absence_on_a_canadian_statement_is_distinct_from_currency_conflict(wired, monkeypatch):
    # Owner ruling, 2026-09-22: the USD default never applies to a Canadian bank, so absence stays absence.
    pair, pdf, directory, _, data = wired
    data['review']['account'].update(currency=None, bank='TD Canada Trust')
    monkeypatch.setattr('vlm.currency.resolve_currency', lambda *a, **kw:
                        CurrencyResolution('unresolved', 'bridge_unclaimed'))
    audit = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic').visual_pair
    assert audit['gate']['reasons'] == ['currency_missing']
    assert audit['gate']['reason_counts']['currency_missing'] == {
        'count': 1, 'document_count': 1, 'pages': [],
    }
    assert not audit['gate']['admitted']
    assert audit['currency_default']['canadian_evidence'] == ['canadian_institution_name']


def test_currency_absence_on_a_non_canadian_statement_defaults_to_usd(wired, monkeypatch):
    # Owner ruling, 2026-09-22: no printed currency and no Canadian evidence means USD, published as a
    # schema default exactly as the production readers publish an unlabelled US statement.
    pair, pdf, directory, _, data = wired
    data['review']['account']['currency'] = None
    monkeypatch.setattr('vlm.currency.resolve_currency', lambda *a, **kw:
                        CurrencyResolution('unresolved', 'bridge_unclaimed'))
    audit = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic').visual_pair
    assert 'currency_missing' not in audit['gate']['reasons']
    assert audit['gate']['admitted']
    assert audit['statement']['currency'] == 'USD'
    assert audit['statement']['currency_source'] == 'schema_default'
    assert audit['currency_default']['currency'] == 'USD'


def test_currency_resolution_runs_with_other_gate_failures_and_clears_only_absence(wired, monkeypatch):
    pair, pdf, directory, _, data = wired
    data['review']['account'].update(currency=None, ending_balance=999)
    resolutions = []

    def resolve(source, text, **kwargs):
        resolutions.append(deepcopy(source))
        assert source['currency'] is None
        assert len(source['transactions']) == 2
        return CurrencyResolution('resolved', 'existing_parser_rule', 'USD',
                                  'institution_default', 'synthetic_reader', 'institution_default')

    monkeypatch.setattr('vlm.currency.resolve_currency', resolve)
    audit = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic').visual_pair
    assert len(resolutions) == 1
    assert audit['currency_resolution']['status'] == 'resolved'
    assert 'sum_mismatch' in audit['gate']['reasons']
    assert 'currency_missing' not in audit['gate']['reasons']
    assert 'currency_conflict' not in audit['gate']['reasons']
    assert 'currency_missing' not in audit['gate']['reason_counts']
    assert all(e['code'] != 'currency_missing' for e in audit['gate']['reason_occurrences'])
    assert not audit['gate']['admitted'] and audit['statement'] is None


def test_currency_bridge_does_not_turn_unknown_direction_into_source_evidence(wired, monkeypatch):
    pair, pdf, directory, _, data = wired
    data['review']['account']['currency'] = None
    # A reviewer correction to an unknown direction cannot become a fabricated
    # debit just because the legacy Statement projection needs a placeholder.
    from dataclasses import replace
    original_merge = __import__('vlm.review', fromlist=['merge_review']).merge_review

    def merge(*args, **kwargs):
        merged = original_merge(*args, **kwargs)
        return replace(merged, rows=tuple(replace(row, direction='unknown', balance=None) for row in merged.rows))

    observed = []
    monkeypatch.setattr('vlm.review.merge_review', merge)
    monkeypatch.setattr('vlm.currency.resolve_currency', lambda source, *a, **kw:
                        observed.append(source) or CurrencyResolution('unresolved', 'source_statement_invalid'))
    audit = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic').visual_pair
    assert len(observed) == 1
    assert all(row['direction'] == 'unknown' for row in observed[0]['transactions'])
    assert 'direction_unknown' in audit['gate']['reasons']


def test_occurrence_summary_preserves_repetitions_and_document_scope():
    from vlm.reason_counts import summarize_occurrences
    events = [{'code': 'anchor_disagreement', 'page': p} for p in (2, 2, 3, None)]
    assert summarize_occurrences(events) == {'anchor_disagreement': {
        'count': 4, 'document_count': 1, 'pages': [{'page': 2, 'count': 2}, {'page': 3, 'count': 1}],
    }}

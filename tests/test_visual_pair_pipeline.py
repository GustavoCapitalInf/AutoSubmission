"""Synthetic end-to-end pair wiring, without network or customer documents."""
import json
from pathlib import Path
from dataclasses import replace

import pytest

from ocr.visual_pair_config import VisualPairSettings, PROPOSER_REVISION, REVIEWER_REVISION
from vlm.client import ChatResult
from vlm.receipts import canonical_json, sha256_bytes
from vlm.render import RenderedPage
from vlm.schema import empty_review

LAYOUT = [{'bbox': [0, 0, 100, 100], 'category': 'Table', 'text':
 '<table><tr><th>Date</th><th>Description</th><th>Credit</th><th>Debit</th><th>Balance</th></tr>'
 '<tr><td>2031-01-02</td><td>ACME PAYROLL EXACT 01</td><td>20.00</td><td></td><td>120.00</td></tr>'
 '<tr><td>2031-01-03</td><td>POS BUY EXACT</td><td></td><td>5.00</td><td>115.00</td></tr></table>'}]


def _review():
    obj = empty_review('statement_page')
    obj['account'].update(bank='Synthetic Bank', account_number='123456', currency='USD',
                           period_start='2031-01-01', period_end='2031-01-31',
                           beginning_balance=100, ending_balance=115,
                           stated_total_credits=20, stated_total_debits=5,
                           stated_credit_count=1, stated_debit_count=1)
    obj['account_numbers_seen'] = ['123456']
    descriptions = ('ACME PAYROLL EXACT 01', 'POS BUY EXACT')
    obj['reviews'] = [{'candidate_id': f'p1r{i}', 'observed_description': description,
                       'verdict': 'confirm', 'corrections': [], 'reason': ''}
                      for i, description in enumerate(descriptions)]
    return obj


@pytest.fixture
def wired(tmp_path, monkeypatch):
    import vlm.pair as pair
    import vlm.render as render
    pdf = tmp_path/'synthetic.pdf'
    pdf.write_bytes(b'%PDF fabricated stub only')
    page = RenderedPage(0,100,100,b'image',sha256_bytes(b'image'),'pixels',72,72,0,0,0)
    monkeypatch.setattr(render, 'render_pages', lambda *a, **kw: [page])
    calls = []
    mutable = {'review': _review(), 'finish': 'stop', 'layout': LAYOUT}

    class Client:
        def __init__(self, url, **kw): self.is_a = '18013' in url
        def get_json(self, path):
            return {'data': [{'id': 'dotsmocr' if self.is_a else 'qwen3.8-27b-nvfp4',
                              'root': '/snapshots/'+(PROPOSER_REVISION if self.is_a else REVIEWER_REVISION)}]}
        def chat(self, model, prompt, **kwargs):
            calls.append((model, kwargs))
            obj = mutable['layout'] if self.is_a else mutable['review']
            text = canonical_json(obj)
            request = canonical_json({'model':model,'prompt':prompt}).encode()
            raw = text.encode()
            return ChatResult(text, None if self.is_a else obj, None,
                              mutable['finish'] if self.is_a else 'stop',10,30,1,
                              sha256_bytes(request),sha256_bytes(raw),sha256_bytes(raw),request,raw)
    monkeypatch.setattr(pair, 'VlmClient', Client)
    return pair, pdf, tmp_path/'evidence', calls, mutable


def test_success_receipts_cache_and_generic_metrics(wired):
    pair,pdf,directory,calls,_ = wired
    doc = pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    assert len(calls)==2
    assert doc.visual_pair['gate']['admitted']
    assert doc.visual_pair['confidence']['counts']['agreed']==2
    assert doc.visual_pair['statement']['transactions'][1]['amount']==-5
    from vlm.pair_adapter import analyze_visual_pair
    report=analyze_visual_pair(doc,review_policy='admit_gated')
    assert report.accounts[0].reconciliation.ok
    assert report.accounts[0].statement.transactions[0].description=='ACME PAYROLL EXACT 01'
    cached=pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    assert len(calls)==2
    assert cached.visual_pair==doc.visual_pair
    for blob in (directory/'blobs').glob('*/*'):
        assert sha256_bytes(blob.read_bytes())==blob.name
    assert len(doc.page_integrity)==1
    assert all(c[1]['max_tokens']==12000 for c in calls)
    assert calls[1][1]['schema']
    assert 'preserve_schema_order' not in calls[0][1]
    assert calls[1][1]['preserve_schema_order'] is True


def test_printed_dates_resolve_from_reviewed_period_without_changing_model_evidence(wired):
    pair, pdf, directory, calls, data = wired
    data['layout'] = [{**LAYOUT[0], 'text': LAYOUT[0]['text']
                       .replace('2031-01-02', 'Jan 02').replace('2031-01-03', 'Jan 03')}]
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    audit = doc.visual_pair
    assert audit['gate']['admitted']
    assert len(calls) == 2
    assert [row['date'] for row in audit['statement']['transactions']] == ['2031-01-02', '2031-01-03']
    assert all(row['state'] == 'agreed' and row['original']['date'] is None
               and row['row']['date'] is None for row in audit['row_evidence'])
    assert audit['date_resolution']['resolved_count'] == 2
    assert audit['date_resolution']['unresolved_count'] == 0
    from vlm.pair_adapter import analyze_visual_pair
    report = analyze_visual_pair(doc, review_policy='admit_gated')
    assert report.accounts[0].reconciliation.ok
    assert report.accounts[0].metrics.adb_ok is True


def test_missing_reviewed_period_does_not_supply_a_row_year(wired):
    pair, pdf, directory, _, data = wired
    data['layout'] = [{**LAYOUT[0], 'text': LAYOUT[0]['text']
                       .replace('2031-01-02', 'Jan 02').replace('2031-01-03', 'Jan 03')}]
    data['review']['account']['period_start'] = None
    data['review']['account']['period_end'] = None
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    assert doc.visual_pair['date_resolution']['resolved_count'] == 0
    assert doc.visual_pair['date_resolution']['unresolved_count'] == 2
    assert not doc.visual_pair['gate']['admitted']
    assert 'date_unparsed' in doc.visual_pair['gate']['reasons']


def test_manifest_pins_ordered_schema_separately_from_semantic_schema(monkeypatch):
    import vlm.pair as pair
    import vlm.schema as schema
    original = pair.visual_pair_manifest()
    assert original['reviewer_serialization_policy'] == 'declared_schema_order_v1'
    assert original['review_schema_ordered_sha256'] == schema.review_schema_ordered_sha256()
    reordered = {**schema.PAGE_REVIEW_SCHEMA,
                 'properties': dict(reversed(list(schema.PAGE_REVIEW_SCHEMA['properties'].items())))}
    monkeypatch.setattr(schema, 'PAGE_REVIEW_SCHEMA', reordered)
    changed = pair.visual_pair_manifest()
    assert changed['review_schema_sha256'] == original['review_schema_sha256']
    assert changed['review_schema_ordered_sha256'] != original['review_schema_ordered_sha256']


def test_manifest_pins_page_integrity_rules(monkeypatch):
    import vlm.pair as pair
    original = pair.visual_pair_manifest()
    assert 'ocr/truncation.py' in original['source_sha256']
    digest = pair.sha256_file
    monkeypatch.setattr(pair, 'sha256_file', lambda path: 'changed-integrity-rules'
                        if str(path).endswith('/ocr/truncation.py') else digest(path))
    changed = pair.visual_pair_manifest()
    assert original['source_sha256']['ocr/truncation.py'] != changed['source_sha256']['ocr/truncation.py']


def test_truncated_proposal_keeps_slot_and_refuses(wired):
    pair,pdf,directory,_,data=wired
    data['finish']='length'
    doc=pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    assert len(doc.pages)==1 and doc.truncated_pages==[0]
    assert not doc.visual_pair['gate']['admitted']
    assert 'page_unresolved' in doc.visual_pair['gate']['reasons']
    assert doc.visual_pair['confidence']['counts']['unresolved']==2
    assert doc.visual_pair['statement'] is None


def test_missing_review_is_never_partially_admitted(wired):
    pair,pdf,directory,_,data=wired
    data['review']['reviews'].pop()
    doc=pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    assert not doc.visual_pair['gate']['admitted']
    assert doc.visual_pair['statement'] is None


def test_different_full_accounts_same_suffix_refused(wired):
    pair,pdf,directory,_,data=wired
    data['review']['account_numbers_seen']=['123456','993456']
    doc=pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    assert 'proposal_invalid' in doc.visual_pair['gate']['reasons']


def test_customer_scope_fenced_even_after_synthetic_cache(wired):
    pair,pdf,directory,calls,_=wired
    pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    from ocr.visual_pair_config import VisualPairAuthorizationError
    with pytest.raises(VisualPairAuthorizationError):
        pair.extract_visual_pair(pdf,evidence_dir=directory)
    assert len(calls)==2


def test_wrong_model_revision_refused_before_pages(wired, monkeypatch):
    pair,pdf,directory,calls,_=wired
    monkeypatch.setattr(pair.VlmClient,'get_json',lambda *_: {'data':[{'id':'dotsmocr','root':'/snapshots/wrong'}]})
    with pytest.raises(pair.VisualPairError,match='revision_unverified'):
        pair.extract_visual_pair(pdf,evidence_dir=directory,data_scope='synthetic')
    assert calls==[]

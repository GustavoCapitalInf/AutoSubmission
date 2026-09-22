"""Recovery is a receipted second generation, never an unmarked partial read."""
import io
import json

from PIL import Image
import pytest

from tests.test_visual_pair_pipeline import wired, LAYOUT, _review
from vlm.client import ChatResult
from vlm.receipts import canonical_json, sha256_bytes
from vlm.render import RenderedPage


def test_nontruncated_proposal_failure_holds_only_its_source_candidates(wired):
    pair, pdf, directory, _, mutable = wired
    mutable['layout'] = [*LAYOUT, {'bbox': [100, 100, 0, 0], 'category': 'Text',
                                  'text': 'SYNTHETIC INVALID GEOMETRY'}]
    # The fabricated non-JPEG in this fixture makes crop recovery fail. The
    # reviewer still confirms both proposals, but their failed source response
    # holds those candidates without invalidating the review response.
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    audit = doc.visual_pair
    assert not audit['gate']['admitted'] and audit['statement'] is None
    assert not audit['pages'][0]['truncated']
    assert 'layout_box_invalid:2' in audit['pages'][0]['proposal_errors']  # LAYOUT is table + summary text
    assert 'proposal_recovery_failed' in audit['pages'][0]['proposal_errors']
    assert audit['pages'][0]['errors'] == []
    assert audit['confidence']['counts']['unresolved'] == 2
    assert audit['confidence']['counts']['agreed'] == 0
    assert audit['confidence']['invalid_page_count'] == 0
    assert set(audit['confidence']['pages'][0]['errors']) == set(audit['pages'][0]['errors'])
    assert all(item['review_verdict'] == 'confirm' and item['row'] is None
               for item in audit['row_evidence'])


@pytest.mark.parametrize("original_has_rows", [False, True])
def test_crop_recovery_receipts_and_every_candidate_review(wired, monkeypatch, original_has_rows):
    pair, pdf, directory, calls, _ = wired
    image = Image.new("RGB", (100, 100), "white")
    image.paste('gray', (0, 50, 100, 100))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    raw = buffer.getvalue()
    monkeypatch.setattr("vlm.render.render_pages", lambda *a, **k: [
        RenderedPage(0, 100, 100, raw, sha256_bytes(raw), "pixels", 72, 72, 0, 0, 0)])
    proposer_count = 0

    def chat(self, model, prompt, **kwargs):
        nonlocal proposer_count
        calls.append((model, kwargs))
        if self.is_a:
            proposer_count += 1
            if proposer_count == 1:
                text = canonical_json(LAYOUT) if original_has_rows else '<svg viewBox="0 0 100 100"></svg>'
                finish = 'length' if original_has_rows else 'stop'
            else:
                table = LAYOUT[0]['text']
                header, first, second, end = table.split('</tr>')
                body = first if proposer_count == 2 else second
                blocks = [{'bbox': [0, 0, 100, 56], 'category': 'Table',
                           'text': header + '</tr>' + body + '</tr></table>'}]
                if proposer_count == 2:  # the summary printed on the page lies in the first crop
                    blocks.append({'bbox': [0, 0, 100, 10], 'category': 'Text', 'text': LAYOUT[1]['text']})
                text = canonical_json(blocks)
                finish = 'stop'
            parsed = None
        else:
            parsed = _review()
            if original_has_rows:
                clean_reviews = [{**item, 'candidate_id': f'p1r{i+2}'}
                                 for i, item in enumerate(parsed['reviews'])]
                for item in parsed['reviews']:
                    item.update(verdict='reject', observed_description=None,
                                reason='Same printed occurrence as complete crop candidate.')
                parsed['reviews'].extend(clean_reviews)
            text, finish = canonical_json(parsed), 'stop'
        request = canonical_json({'model': model, 'prompt': prompt,
                                  'image_sha256': sha256_bytes(kwargs['image_jpeg']),
                                  'test_call': len(calls)}).encode()
        response = text.encode()
        return ChatResult(text, parsed, None, finish, 10, 100, 1,
                          sha256_bytes(request), sha256_bytes(response), sha256_bytes(response), request, response)

    monkeypatch.setattr(pair.VlmClient, 'chat', chat)
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    audit = doc.visual_pair
    assert len(calls) == 4
    assert audit['gate']['admitted']
    assert len(doc.pages) == 1 and not doc.has_truncated_pages
    recovery = audit['proposal_recoveries'][0]
    assert recovery['attempted'] and recovery['recovered']
    assert recovery['original']['layout']['truncated'] is original_has_rows
    assert len(audit['row_evidence']) == (4 if original_has_rows else 2)
    assert audit['confidence']['counts']['rejected'] == (2 if original_has_rows else 0)
    assert all(item['original'] is not None for item in audit['row_evidence'])
    assert len(audit['statement']['transactions']) == 2
    receipt_sha = audit['receipt_sha256']
    receipt = json.loads((directory / 'blobs' / receipt_sha[:2] / receipt_sha).read_bytes())
    assert [item['purpose'] for item in receipt['calls']] == [
        'full_page', 'crop_recovery', 'crop_recovery', 'full_page']
    assert receipt['calls'][-1]['image_sha256'] == sha256_bytes(raw)
    assert all(item['manifest']['pipeline']['proposal_recovery']['maximum_crop_calls'] == 2
               for item in receipt['calls'])

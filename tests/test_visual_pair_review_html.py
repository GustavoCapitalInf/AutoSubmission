"""Held pages stay inspectable without trusting model markup or admitting rows."""
from webapp.visual_pair_review import retained_evidence_html


def test_invalid_page_keeps_original_and_corrected_source_visible_and_escaped():
    output = retained_evidence_html({
        'gate': {'admitted': False, 'reasons': ['proposal_invalid', 'date_unparsed']},
        'row_evidence': [{'page': 2, 'state': 'unresolved',
                          'original': {'description': 'FABRICATED <script>bad()</script>', 'amount': 10},
                          'corrected': {'description': 'FABRICATED COMPLETE', 'amount': 10},
                          'row': None}],
    })
    assert 'incomplete' in output and 'dates are missing' in output
    assert 'Page 2, row 1: Unresolved — not admitted' in output
    assert 'FABRICATED &lt;script&gt;bad()&lt;/script&gt;' in output
    assert 'FABRICATED COMPLETE' in output
    assert '<script>' not in output
    assert 'Original proposal' in output and 'Reviewer result' in output


def test_rejected_original_and_unresolved_addition_remain_reviewable():
    output = retained_evidence_html({'row_evidence': [
        {'page': 1, 'state': 'rejected', 'original': {'description': 'FABRICATED TOTAL'}, 'row': None},
        {'page': 1, 'state': 'unresolved', 'original': None, 'row': {'description': 'FABRICATED ADDITION'}},
    ]})
    assert 'FABRICATED TOTAL' in output and 'FABRICATED ADDITION' in output
    assert 'Rejected — excluded' in output and 'Unresolved — not admitted' in output


def test_unknown_gate_reason_is_not_echoed_as_markup_or_source_data():
    output = retained_evidence_html({'gate': {'reasons': ['<img src=x onerror=alert(1)>']}})
    assert 'statement check requires review' in output
    assert '<img' not in output


def test_app_resolved_date_is_attributed_separately_from_unchanged_model_output():
    output = retained_evidence_html({
        'row_evidence': [{'page': 1, 'locator': 'g0/t0r1', 'state': 'agreed',
                          'original': {'date': None, 'date_text': 'Jan 02'},
                          'row': {'date': None, 'date_text': 'Jan 02'}}],
        'date_resolution': {'rows': [{'page': 1, 'locator': 'g0/t0r1', 'resolved_date': '2031-01-02'}]},
    })
    assert 'Date resolved from the printed date and statement period' in output
    assert '<strong>2031-01-02</strong>' in output
    assert 'reader outputs above are unchanged' in output
    assert output.count('Jan 02') == 2

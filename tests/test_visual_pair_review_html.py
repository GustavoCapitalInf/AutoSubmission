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


def test_reason_counts_keep_repeated_pages_and_document_level_failures_distinct():
    output = retained_evidence_html({'gate': {
        'reasons': ['continuity_break', 'continuity_break', 'currency_missing', 'page_unresolved'],
        'reason_counts': {
            'continuity_break': {'count': 7, 'pages': [{'page': 5, 'count': 4}, {'page': 2, 'count': 3}],
                                 'document_count': 0},
            'currency_missing': {'count': 1, 'pages': [], 'document_count': 1},
            'page_unresolved': {'count': 2, 'pages': [{'page': 3, 'count': 2}], 'document_count': 0},
        },
    }})
    assert output.count('7 occurrences') == 1
    assert 'Page 2: 3; Page 5: 4' in output
    assert 'Document level: 1 (no page attribution)' in output
    assert 'printed statement currency is missing' in output
    assert 'unresolved reading or review evidence' in output
    assert '2 occurrences · Page 3: 2' in output
    assert 'Counts unavailable' not in output


def test_legacy_reason_flags_do_not_invent_occurrence_counts():
    output = retained_evidence_html({'gate': {'reasons': ['sum_mismatch', 'currency_conflict']}})
    assert output.count('Counts unavailable.') == 2
    assert 'occurrence' not in output
    assert 'printed statement currencies conflict' in output


def test_invalid_count_metadata_is_not_rendered_as_content_or_a_plausible_count():
    output = retained_evidence_html({'gate': {
        'reasons': ['sum_mismatch', 'date_unparsed'],
        'reason_counts': {
            'sum_mismatch': {'count': 7, 'pages': [], 'document_count': 1},
            'date_unparsed': {'count': '<script>FABRICATED</script>', 'pages': [], 'document_count': 0},
        },
    }})
    assert output.count('Counts unavailable.') == 2
    assert 'FABRICATED' not in output and '<script>' not in output

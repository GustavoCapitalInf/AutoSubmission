"""Synthetic source-lineage and pipeline checks; no inference or customer data."""
from dataclasses import replace

from tests.test_visual_pair_pipeline import wired
from tests.test_vlm_pair_review import _candidate, _review
from vlm.assemble import DotsLayout
from vlm.pair import proposal_candidate_errors
from vlm.review import candidate_records, merge_review


def test_failed_sources_are_attributed_by_lineage_not_shared_source_label():
    rows = (
        replace(_candidate(0), locator='g0/original', source='stage_a_original'),
        replace(_candidate(1), locator='g1c0/complete', source='stage_a_recovery'),
        replace(_candidate(2), locator='g1c1/r0/held', source='stage_a_recovery'),
    )
    layout = DotsLayout(1, (), rows, ('stage_a_truncated', 'proposal_recovery_failed'), True)
    recovery = {
        'attempted': True,
        'original': {'layout': {'errors': ['stage_a_truncated'], 'truncated': True}},
        'original_candidate_lineage': [{'locator': rows[0].locator}],
        'crops': [
            {'complete': True, 'lineage': {'rows': [{'locator': rows[1].locator}]}},
            {'complete': False, 'layout': {'errors': ['layout_invalid_json'], 'truncated': True},
             'failure': 'proposal_recovery_crop_incomplete',
             'lineage': {'rows': [{'locator': rows[2].locator,
                                  'held_reason': 'proposal_recovery_crop_incomplete'}]}},
        ],
    }
    errors = proposal_candidate_errors(layout, recovery)
    assert set(errors) == {'p1r0', 'p1r2'}
    assert errors['p1r0'] == ('stage_a_truncated',)
    assert 'layout_invalid_json' in errors['p1r2']
    payload = _review(rows)
    added = {**candidate_records([_candidate(3)])[0]['row'], 'description': 'Synthetic addition'}
    payload['added'] = [{'row': added, 'after_candidate_id': 'p1r2'}]
    result = merge_review(rows, payload, page=1, candidate_validation_errors=errors)
    assert result.errors == ()
    assert result.counts == {'agreed': 1, 'corrected': 0, 'added': 1, 'rejected': 0, 'unresolved': 2}
    assert [row.locator for row in result.rows] == [rows[1].locator, 'added0']
    assert all(item['reason'] != 'page_review_invalid' for item in result.evidence)


def test_a_cut_off_stage_a_read_holds_its_page_even_when_stage_b_adds_every_row(wired):
    # Owner ruling, 2026-09-22 ("Hold"): a proposer read that was cut off holds its page. Here the proposer
    # produced nothing before the cut and the reviewer added both rows, so every row would be single-read;
    # admitting it would pass one model's reading off as a paired one.
    pair, pdf, directory, _, mutable = wired
    from vlm.assemble import parse_dots_layout
    from tests.test_visual_pair_pipeline import LAYOUT
    records = candidate_records(parse_dots_layout(LAYOUT, page=1, width=100, height=100).rows)
    mutable['layout'] = []
    mutable['finish'] = 'length'
    mutable['review']['reviews'] = []
    mutable['review']['added'] = [{'row': item['row'], 'after_candidate_id': None} for item in records]
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    audit = doc.visual_pair
    assert not audit['gate']['admitted'] and audit['statement'] is None
    assert 'page_unresolved' in audit['gate']['reasons']
    assert audit['confidence']['counts']['added'] == 2
    assert audit['pages'][0]['proposal_errors']
    assert audit['pages'][0]['truncated'] and not audit['pages'][0]['review_truncated']
    assert doc.has_truncated_pages


def test_one_bad_observation_preserves_other_pipeline_rows_and_metadata(wired):
    pair, pdf, directory, _, mutable = wired
    mutable['review']['reviews'][0]['observed_description'] = 'Synthetic mismatch'
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    audit = doc.visual_pair
    assert audit['confidence']['counts']['agreed'] == 1
    assert audit['confidence']['counts']['unresolved'] == 1
    assert audit['pages'][0]['errors'] == []
    assert audit['confidence']['invalid_page_count'] == 0
    assert any(item['field'] == 'period_start' for item in audit['field_evidence'])
    assert not audit['gate']['admitted']  # document completeness policy is unchanged
    assert audit['row_evidence'][0]['validation_errors'] == ['review_description_observation_mismatch']
    assert audit['row_evidence'][1]['state'] == 'agreed'


def test_failed_proposal_rejection_remains_a_valid_rejection():
    rows = [_candidate()]
    payload = _review(rows)
    payload['reviews'][0].update(verdict='reject', observed_description='Synthetic stray observation')
    result = merge_review(rows, payload, page=1,
                          candidate_validation_errors={'p1r0': ('stage_a_truncated',)})
    assert result.counts['rejected'] == 1 and result.counts['unresolved'] == 0
    assert not result.errors
    assert result.evidence[0]['observed_description'] is None
    assert result.evidence[0]['raw_review']['observed_description'] == 'Synthetic stray observation'


def test_invalid_metadata_keeps_rows_but_does_not_silently_authorize_publication(wired):
    pair, pdf, directory, _, mutable = wired
    mutable['review']['account_numbers_seen'].append(123)
    doc = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope='synthetic')
    audit = doc.visual_pair
    assert audit['confidence']['counts']['agreed'] == 2
    assert audit['confidence']['counts']['unresolved'] == 0
    assert audit['pages'][0]['errors'] == []
    assert audit['review_metadata_evidence']
    assert not audit['gate']['admitted']
    assert audit['gate']['checks']['unresolved_pages'] == [1]

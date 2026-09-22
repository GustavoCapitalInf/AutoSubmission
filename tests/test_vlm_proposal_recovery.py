"""Fabricated pixels/layouts only; the recovery helper never performs inference."""
from dataclasses import replace
from decimal import Decimal
import io
import json

from PIL import Image
import pytest

from vlm.assemble import Block, CandidateRow, DotsLayout, parse_dots_layout
from vlm.proposal_recovery import (ProposalRecoveryError, needs_proposal_recovery,
                                   proposal_recovery_manifest, recover_proposal_page)
from vlm.receipts import canonical_json, sha256_bytes


def _jpeg(width=100, height=100):
    image = Image.new('RGB', (width, height))
    image.putdata([(x % 256, y % 256, (x + y) % 256) for y in range(height) for x in range(width)])
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=90, subsampling=0)
    image.close()
    return out.getvalue()


def _solid_jpeg(color='white', *, changed_pixel=None):
    image = Image.new('RGB', (100, 100), color)
    if changed_pixel:
        image.putpixel((10, 10), changed_pixel)
    out = io.BytesIO()
    image.save(out, format='JPEG', quality=100, subsampling=0)
    image.close()
    return out.getvalue()


def _failed():
    return DotsLayout(7, (), (), ('stage_a_truncated', 'layout_invalid_json'), True)


def _valid(crop, *, box=(0.0, 0.0, 1.0, 1.0), description='SYNTHETIC exact  reference', duplicate=False):
    row = CandidateRow('2031-01-02', '01/02', description, Decimal('12.34'), 'unknown', None,
                       crop.page, 'stage_a', 'b0t0r0', 'printed', box, None)
    rows = (row, replace(row, locator='b0t0r1')) if duplicate else (row,)
    return DotsLayout(crop.page, (Block('table', box, 'SYNTHETIC source content', 0, crop.page),),
                      rows, (), False)


def test_manifest_pins_split_rounding_encoding_and_no_deduplication():
    manifest = proposal_recovery_manifest()
    assert manifest == proposal_recovery_manifest()
    assert manifest['vertical_fraction_numerators'] == [[0, 56], [44, 100]]
    assert manifest['maximum_crop_calls'] == 2 and manifest['vertical_fraction_denominator'] == 100
    assert manifest['pixel_rounding'] == {'top_end': 'ceil', 'bottom_start': 'floor'}
    assert manifest['resize'] is manifest['enhancement'] is manifest['deduplicate'] is False
    assert manifest['jpeg_quality'] == 90 and manifest['jpeg_subsampling'] == 0
    assert manifest['empty_region_proof'] == {
        'method': 'exact_rgb_white',
        'pixel_stage': 'decoded_source_jpeg_before_crop_reencoding',
        'required_channel_extrema': [[255, 255], [255, 255], [255, 255]],
        'threshold_or_variance': False,
    }
    assert len(manifest['source_sha256']) == 64


def test_two_deterministic_crops_have_exact_bounds_and_source_pixel_provenance():
    jpeg = _jpeg()
    seen = []

    def read(crop):
        seen.append(crop)
        return _valid(crop)

    result = recover_proposal_page(jpeg, _failed(), read, original_receipt_sha256='a' * 64)
    assert result.attempted and result.recovered and not result.layout.truncated and not result.layout.errors
    assert [crop.bounds_px for crop in seen] == [(0, 0, 100, 56), (0, 44, 100, 100)]
    assert [crop.bbox_fullpage for crop in seen] == [(0, 0, 1, .56), (0, .44, 1, 1)]
    with Image.open(io.BytesIO(jpeg)) as source:
        for crop in seen:
            assert crop.width == 100 and crop.height == 56
            assert crop.source_jpeg_sha256 == sha256_bytes(jpeg)
            assert crop.jpeg_sha256 == sha256_bytes(crop.jpeg)
            assert crop.pixel_sha256 == sha256_bytes(source.crop(crop.bounds_px).tobytes())
            assert crop.config_sha256 == sha256_bytes(canonical_json(result.audit['manifest']).encode())
            assert 'jpeg' not in crop.metadata()
    assert result.audit['original']['receipt_sha256'] == 'a' * 64
    assert result.audit['original']['layout']['truncated'] is True
    assert result.audit['effective_complete'] is True
    again = recover_proposal_page(jpeg, _failed(), _valid)
    assert [crop.jpeg for crop in again.crops] == [crop.jpeg for crop in result.crops]


def test_odd_height_rounding_preserves_full_coverage_and_overlap():
    result = recover_proposal_page(_jpeg(height=101), _failed(), _valid)
    assert [crop.bounds_px for crop in result.crops] == [(0, 0, 100, 57), (0, 44, 100, 101)]
    assert result.crops[0].bbox_fullpage[3] == 57 / 101
    assert result.crops[1].bbox_fullpage[1] == 44 / 101
    assert result.layout.rows[0].bbox == (0, 0, 1, round(57 / 101, 6))


def test_exact_white_crop_skips_model_with_source_pixel_bound_proof():
    jpeg = _solid_jpeg(changed_pixel=(0, 0, 0))
    seen = []

    def read(crop):
        seen.append(crop.index)
        return _valid(crop)

    result = recover_proposal_page(jpeg, _failed(), read)
    assert seen == [0] and result.recovered
    assert len(result.layout.rows) == 1
    assert result.audit['model_call_count'] == result.audit['exact_white_region_count'] == 1
    first, blank = result.audit['crops']
    assert first['model_called'] and first['origin'] == 'stage_a_model'
    assert 'empty_region_proof' not in first
    assert not blank['model_called'] and blank['origin'] == 'deterministic_empty_region'
    assert blank['complete'] and blank['layout']['rows'] == []
    proof = blank['empty_region_proof']
    assert proof['method'] == 'exact_rgb_white'
    assert proof['source_jpeg_sha256'] == sha256_bytes(jpeg)
    assert proof['pixel_sha256'] == result.crops[1].pixel_sha256
    assert proof['source_rgb_extrema'] == ((255, 255),) * 3
    assert proof['bounds_px'] == (0, 44, 100, 100)
    assert proof['width'] == 100 and proof['height'] == 56 and proof['pixel_mode'] == 'RGB'
    with Image.open(io.BytesIO(jpeg)) as image:
        pixels = image.convert('RGB').crop(proof['bounds_px'])
        assert pixels.getextrema() == ((255, 255),) * 3
        assert sha256_bytes(pixels.tobytes()) == proof['pixel_sha256']
    assert 'receipt_sha256' not in blank and 'response_sha256' not in blank
    canonical_json(result.audit)


def test_one_nonwhite_source_pixel_requires_model_for_its_crop():
    jpeg = _solid_jpeg(changed_pixel=(0, 0, 0))
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.convert('RGB').getpixel((10, 10)) != (255, 255, 255)
    seen = []

    def read(crop):
        seen.append(crop.index)
        return replace(_valid(crop), errors=('stage_a_truncated',), truncated=True)

    result = recover_proposal_page(jpeg, _failed(), read)
    assert seen == [0]
    assert not result.recovered and result.layout.truncated
    assert not result.audit['effective_complete']
    assert result.audit['crops'][1]['complete']
    assert 'proposal_recovery_failed' in result.layout.errors


@pytest.mark.parametrize('color', [(254, 254, 254), (255, 255, 254), (0, 0, 0)])
def test_near_white_nonwhite_channel_and_black_crops_never_skip_model(color):
    seen = []

    def read(crop):
        seen.append(crop.index)
        return _valid(crop)

    result = recover_proposal_page(_solid_jpeg(color), _failed(), read)
    assert seen == [0, 1]
    assert result.audit['model_call_count'] == 2
    assert result.audit['exact_white_region_count'] == 0
    assert all('empty_region_proof' not in item for item in result.audit['crops'])


def test_both_exact_white_regions_need_no_model_and_invent_no_rows_or_metadata():
    failed = _failed()
    result = recover_proposal_page(
        _solid_jpeg(), failed, lambda crop: pytest.fail('unexpected model call'),
        original_receipt_sha256='a' * 64)
    assert result.recovered and result.audit['effective_complete']
    assert not result.layout.rows and not result.layout.blocks
    assert not result.layout.errors and not result.layout.truncated
    assert result.audit['model_call_count'] == 0 and result.audit['exact_white_region_count'] == 2
    assert result.audit['original']['layout']['errors'] == list(failed.errors)
    assert result.audit['original']['layout']['truncated']
    assert result.audit['original']['receipt_sha256'] == 'a' * 64
    assert all(item['complete'] and not item['model_called'] and not item['layout']['blocks']
               and not item['layout']['rows'] and 'receipt_sha256' not in item
               for item in result.audit['crops'])


def test_exact_white_proof_keeps_original_proposal_for_explicit_review():
    original = CandidateRow(None, '01/02', 'ORIGINAL FAILED CANDIDATE', Decimal('1.00'),
                            'unknown', None, 7, 'stage_a', 'b0t0r0', bbox=(0, 0, 1, 1))
    result = recover_proposal_page(
        _solid_jpeg(), replace(_failed(), rows=(original,)),
        lambda crop: pytest.fail('unexpected model call'))
    assert result.recovered and len(result.layout.rows) == 1
    assert result.layout.rows[0].locator == 'g0/b0t0r0'
    assert result.layout.rows[0].description == original.description
    assert result.audit['original_candidate_lineage'][0]['requires_full_page_review']


def test_crop_geometry_maps_to_full_image_without_changing_source_fields():
    original = []

    def read(crop):
        layout = _valid(crop, box=(.1, .2, .9, .8))
        original.append(layout)
        return layout

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert [row.bbox for row in result.layout.rows] == [(.1, .112, .9, .448), (.1, .552, .9, .888)]
    assert [block.bbox for block in result.layout.blocks] == [row.bbox for row in result.layout.rows]
    assert [row.locator for row in result.layout.rows] == ['g1c0/b0t0r0', 'g1c1/b0t0r0']
    assert [block.order for block in result.layout.blocks] == [0, 1]
    for row, old in zip(result.layout.rows, original):
        assert row.description == old.rows[0].description
        assert row.amount == old.rows[0].amount and row.direction == 'unknown'
        assert row.date == old.rows[0].date and row.balance is None and row.printed_amount is None
        assert row.source == 'stage_a_recovery' and row.page == 7
        assert old.rows[0].bbox == (.1, .2, .9, .8)


def test_overlap_and_legitimate_identical_rows_are_all_preserved_for_review():
    result = recover_proposal_page(_jpeg(), _failed(), lambda crop: _valid(crop, duplicate=True))
    assert len(result.layout.rows) == 4
    assert len({row.locator for row in result.layout.rows}) == 4
    assert len({(row.date, row.description, row.amount) for row in result.layout.rows}) == 1
    assert result.audit['deduplicated'] is False
    assert result.audit['review_image'] == 'original_full_page'
    assert all(row['requires_full_page_review'] and row['box_touches_cut_boundary']
               for item in result.audit['crops'] for row in item['lineage']['rows'])


def test_original_failed_rows_are_also_reviewed_alongside_the_new_generation():
    original = CandidateRow(None, '01/02', 'ORIGINAL FAILED CANDIDATE', Decimal('1.00'),
                            'unknown', None, 7, 'stage_a', 'b0t0r0', bbox=(0, 0, 1, 1))
    failed = replace(_failed(), rows=(original,))
    result = recover_proposal_page(_jpeg(), failed, _valid)
    assert result.recovered and original not in result.layout.rows
    assert len(result.layout.rows) == 3
    retained = result.layout.rows[0]
    assert retained.description == original.description and retained.amount == original.amount
    assert retained.bbox == original.bbox and retained.locator == 'g0/b0t0r0'
    assert retained.source == 'stage_a_original'
    assert len({row.locator for row in result.layout.rows}) == 3
    assert result.audit['original_candidate_count'] == 1
    assert result.audit['crop_candidate_count'] == 2
    assert result.audit['original_candidate_lineage'][0]['requires_full_page_review']
    assert result.audit['original']['layout']['rows'][0]['description'] == original.description
    assert result.audit['original']['layout']['rows'][0]['amount'] == '1.00'
    assert failed.rows == (original,)
    canonical_json(result.audit)


def test_failed_crop_recovery_retains_every_original_candidate_for_unresolved_review():
    original = CandidateRow(None, '01/02', 'ORIGINAL FAILED CANDIDATE', Decimal('1.00'),
                            'unknown', None, 7, 'stage_a', 'b0t0r0', bbox=(0, 0, 1, 1))
    failed = replace(_failed(), rows=(original, replace(original, locator='b0t0r1')))

    def read(crop):
        layout = _valid(crop)
        return replace(layout, errors=('layout_invalid_json',), truncated=True)

    result = recover_proposal_page(_jpeg(), failed, read)
    assert not result.recovered and result.layout.truncated
    assert len(result.layout.rows) == 4
    assert [row.description for row in result.layout.rows[:2]] == [row.description for row in failed.rows]
    assert all(row.locator.startswith('g0/') for row in result.layout.rows[:2])
    assert result.audit['original_candidate_count'] == 2 and result.audit['crop_candidate_count'] == 2
    assert result.audit['effective_complete'] is False
    assert 'proposal_recovery_failed' in result.layout.errors


@pytest.mark.parametrize('bad_index', [0, 1])
def test_both_crop_reads_are_bounded_but_any_failure_holds_entire_effective_page(bad_index):
    seen = []

    def read(crop):
        seen.append(crop.index)
        layout = _valid(crop)
        return replace(layout, truncated=True, errors=('stage_a_truncated',)) if crop.index == bad_index else layout

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert seen == [0, 1] and not result.recovered
    assert result.layout.page == 7 and result.layout.truncated
    assert len(result.layout.rows) == 2
    assert all(row.bbox is not None for row in result.layout.rows)
    assert len({row.locator for row in result.layout.rows}) == 2
    assert result.audit['effective_complete'] is False
    assert 'proposal_recovery_failed' in result.layout.errors
    assert len(result.audit['crops']) == 2
    assert sum(item['complete'] for item in result.audit['crops']) == 1


def test_reader_failure_message_never_enters_audit():
    def read(crop):
        if crop.index == 0:
            raise RuntimeError('PRIVATE CUSTOMER DETAILS')
        return _valid(crop)

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert not result.recovered and len(result.layout.rows) == 1
    assert result.layout.rows[0].locator.startswith('g1c1/')
    assert result.audit['crops'][0]['error_type'] == 'RuntimeError'
    assert 'PRIVATE CUSTOMER DETAILS' not in canonical_json(result.audit)


@pytest.mark.parametrize('box', [None, (0, 0, 1), (-.01, 0, 1, 1), (0, 0, 2, 1),
                                (0, 0, 0, 1), (False, 0, 1, 1), (0, float('nan'), 1, 1),
                                (0, 0, float('inf'), 1), (0, 0, .00000001, 1)])
def test_unmappable_geometry_retains_candidates_but_never_yields_a_complete_page(box):
    result = recover_proposal_page(_jpeg(), _failed(), lambda crop: _valid(crop, box=box))
    assert not result.recovered and len(result.layout.rows) == 2
    assert all(row.bbox is None for row in result.layout.rows)
    assert all(item['failure'] == 'proposal_recovery_unmappable_box' for item in result.audit['crops'])
    assert all(item['lineage']['rows'][0]['geometry_held_reason'] == 'proposal_recovery_unmappable_box'
               for item in result.audit['crops'])
    assert result.audit['effective_complete'] is False
    canonical_json(result.audit)  # Even invalid numeric geometry has safe audit encoding.


def test_unboxed_complete_html_crop_is_held_because_geometry_is_unknown():
    table = '<table><tr><th>Date</th><th>Description</th><th>Amount</th></tr><tr><td>01/02</td><td>SYNTHETIC</td><td>1.00</td></tr></table>'

    def read(crop):
        return parse_dots_layout(table, page=crop.page, width=crop.width, height=crop.height)

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert not result.recovered and len(result.layout.rows) == 2
    assert all(row.bbox is None for row in result.layout.rows)
    assert all(item['failure'] == 'proposal_recovery_unmappable_box' for item in result.audit['crops'])


def test_mismatched_page_is_held():
    result = recover_proposal_page(_jpeg(), _failed(), lambda crop: replace(_valid(crop), page=99))
    assert not result.recovered
    assert len(result.layout.rows) == 2 and all(row.bbox is None for row in result.layout.rows)
    assert all(item['failure'] == 'proposal_recovery_page_mismatch' for item in result.audit['crops'])


def test_duplicate_crop_locators_are_held_without_silent_deduplication():
    def read(crop):
        layout = _valid(crop)
        return replace(layout, rows=(layout.rows[0], layout.rows[0]))

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert not result.recovered and len(result.layout.rows) == 4
    assert len({row.locator for row in result.layout.rows}) == 4
    assert all(item['failure'] == 'proposal_recovery_duplicate_locator' for item in result.audit['crops'])


def test_successful_first_crop_and_failed_second_keep_all_proposals_and_original():
    original = CandidateRow(None, '01/02', 'ORIGINAL FAILED CANDIDATE', Decimal('1.00'),
                            'unknown', None, 7, 'stage_a', 'b0t0r0', bbox=(0, 0, 1, 1))

    def read(crop):
        layout = _valid(crop, description='SYNTHETIC CROP ' + str(crop.index))
        if crop.index == 1:
            return replace(layout, errors=('stage_a_truncated',), truncated=True,
                           rows=(replace(layout.rows[0], bbox=None),))
        return layout

    result = recover_proposal_page(_jpeg(), replace(_failed(), rows=(original,)), read)
    assert not result.recovered and not result.audit['effective_complete']
    assert result.layout.truncated and 'proposal_recovery_failed' in result.layout.errors
    assert len(result.layout.rows) == 3
    assert [row.description for row in result.layout.rows] == [
        original.description, 'SYNTHETIC CROP 0', 'SYNTHETIC CROP 1']
    assert result.layout.rows[1].bbox == (0, 0, 1, .56)
    assert result.layout.rows[2].bbox is None
    assert len({row.locator for row in result.layout.rows}) == 3
    assert result.audit['candidate_count'] == 3
    assert result.audit['crops'][1]['lineage']['rows'][0]['geometry_status'] == 'unmappable'


@pytest.mark.parametrize('errors', [(), ('proposer_transport_failed',), ('unrelated_error',)])
def test_recovery_is_only_triggered_by_format_or_truncation_failure(errors):
    layout = DotsLayout(7, (), (), errors, False)
    result = recover_proposal_page(_jpeg(), layout, lambda crop: pytest.fail('unexpected crop call'))
    assert not result.attempted and not result.recovered and result.layout is layout
    assert not needs_proposal_recovery(layout)


def test_svg_crop_is_still_refused_and_cannot_trigger_a_third_attempt():
    seen = []

    def read(crop):
        seen.append(crop.index)
        return parse_dots_layout('<svg></svg>', page=crop.page, width=crop.width, height=crop.height)

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert seen == [0, 1] and not result.recovered
    assert all(item['layout']['errors'] == ['layout_unsupported_svg'] for item in result.audit['crops'])


def test_bad_input_image_is_held_without_calling_reader():
    result = recover_proposal_page(b'not a jpeg', _failed(), lambda crop: pytest.fail('unexpected crop call'))
    assert result.attempted and not result.recovered and result.audit['failure'] == 'proposal_recovery_jpeg_required'
    assert result.layout.truncated and 'proposal_recovery_failed' in result.layout.errors


def test_real_parser_callback_uses_crop_dimensions_before_fullpage_mapping():
    def read(crop):
        data = [{'category': 'Text', 'bbox': [0, 0, crop.width, crop.height],
                 'text': '01/02 SYNTHETIC exact  text 10.00'}]
        return parse_dots_layout(json.dumps(data), page=crop.page, width=crop.width, height=crop.height,
                                 finish_reason='stop', year_hint=2031)

    result = recover_proposal_page(_jpeg(), _failed(), read)
    assert result.recovered and len(result.layout.rows) == 2
    assert [row.bbox for row in result.layout.rows] == [(0, 0, 1, .56), (0, .44, 1, 1)]
    assert all(row.description == 'SYNTHETIC exact  text' for row in result.layout.rows)


def test_no_error_message_or_receipt_value_is_accepted_as_a_binding():
    with pytest.raises(ProposalRecoveryError, match='proposal_recovery_receipt_invalid'):
        recover_proposal_page(_jpeg(), _failed(), _valid, original_receipt_sha256='PRIVATE CONTENT')

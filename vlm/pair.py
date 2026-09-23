"""Pinned, receipted two-reader visual fallback. Source fields only; arithmetic is downstream.

All content lives under the caller's private evidence directory. Every page retains
its slot, including failures. An incomplete read can never reach admission.
"""
from __future__ import annotations

import html
import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path
from typing import Callable

from ocr.document import StatementMarkdown
from ocr.truncation import PageIntegrity, PageText, assess_pages
from ocr.visual_pair_config import (MODEL_TOKEN, VisualPairSettings, check_remote_authorization,
                                    load_visual_pair_settings, visual_pair_settings_key_material)
from vlm.client import ChatResult, VlmClient, TransportError
from vlm.receipts import canonical_json, sha256_bytes, sha256_file
from vlm.pair_metadata import merge_metadata as _merge_metadata, page_break_figures

PAIR_VERSION = 1


class VisualPairError(RuntimeError):
    """Only fixed, content-free failure codes cross the worker boundary."""


def visual_pair_manifest() -> dict:
    from vlm.gate import GATE_VERSION
    from vlm.prompts import STAGE_A_DOTS_PROMPT, STAGE_B_REVIEW_PROMPT, prompt_sha256
    from vlm.schema import SCHEMA_VERSION, review_schema_sha256, review_schema_ordered_sha256
    from vlm.render import render_settings
    from vlm.review_batches import review_batching_manifest
    from vlm.proposal_recovery import proposal_recovery_manifest
    from vlm.currency import currency_resolution_manifest
    from vlm.dates import DATE_RESOLVER_VERSION
    from vlm.segments import SEGMENT_VERSION, SEGMENT_POLICY
    root = Path(__file__).resolve().parents[1]
    sources = ('vlm/pair.py', 'vlm/review.py', 'vlm/assemble.py', 'vlm/tables.py',
               'vlm/textparse.py', 'vlm/metadata.py', 'vlm/gate.py', 'vlm/pair_adapter.py',
               'vlm/prompts.py', 'vlm/schema.py', 'vlm/render.py', 'vlm/client.py',
               'vlm/receipts.py', 'vlm/review_batches.py', 'vlm/proposal_recovery.py', 'vlm/currency.py',
               'ocr/visual_pair_config.py', 'ocr/private_artifacts.py', 'ocr/truncation.py',
               'vlm/dates.py', 'vlm/pair_metadata.py', 'vlm/reason_counts.py',
               'vlm/segments.py', 'vlm/segment_openings.py', 'vlm/segment_reconcile.py', 'vlm/native_text.py',
               'vlm/summary_box.py', 'vlm/confidence.py')
    return {
        'version': PAIR_VERSION, 'schema_version': SCHEMA_VERSION,
        'review_schema_sha256': review_schema_sha256(), 'gate_version': GATE_VERSION,
        'review_schema_ordered_sha256': review_schema_ordered_sha256(),
        'reviewer_serialization_policy': 'declared_schema_order_v1',
        'review_batching': review_batching_manifest(),
        'proposal_recovery': proposal_recovery_manifest(),
        'currency_resolution': currency_resolution_manifest(),
        'date_resolution': {'version': DATE_RESOLVER_VERSION,
                            'policy': 'unique_reviewed_period_date_v1'},
        'page_segments': {'version': SEGMENT_VERSION, 'policy': SEGMENT_POLICY},
        'proposer_prompt_sha256': prompt_sha256(STAGE_A_DOTS_PROMPT),
        'reviewer_prompt_sha256': prompt_sha256(STAGE_B_REVIEW_PROMPT),
        'renderer': render_settings(dpi=VisualPairSettings.render_dpi,
                                    image_format=VisualPairSettings.render_format),
        'source_sha256': {name: sha256_file(root / name) for name in sources},
    }


def _blob(root: Path, raw: bytes) -> str:
    digest = sha256_bytes(raw)
    target = root / 'blobs' / digest[:2] / digest
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with target.open('xb') as handle:
            handle.write(raw)
        target.chmod(0o600)
    except FileExistsError:
        if sha256_file(target) != digest:
            raise VisualPairError('visual_pair_evidence_changed') from None
    return digest


def _json_blob(root: Path, obj: object) -> str:
    return _blob(root, canonical_json(obj).encode())


def _check_model(client: VlmClient, model: str, revision: str) -> dict:
    # Checking the served name alone would allow another snapshot under the alias.
    items = client.get_json('/v1/models').get('data', [])
    match = [item for item in items if item.get('id') == model]
    if len(match) != 1 or str(match[0].get('root', '')).rstrip('/').split('/')[-1] != revision:
        raise VisualPairError('visual_pair_model_revision_unverified')
    return {'model': model, 'revision': revision,
            'model_metadata_sha256': sha256_bytes(canonical_json(match[0]).encode())}


def _client(url: str, timeout: float) -> VlmClient:
    return VlmClient(url.rstrip('/').removesuffix('/v1'), timeout=timeout, transport_retries=0)


def _chat_once(root: Path, client: VlmClient, model: str, prompt: str, *, manifest: dict,
               **kwargs) -> ChatResult:
    """Resume a partially completed document without silently re-reading a page."""
    material = {**kwargs, 'image_jpeg': sha256_bytes(kwargs['image_jpeg']),
                'model': model, 'prompt': prompt,
                'manifest': {key: value for key, value in manifest.items() if key != 'served_models'}}
    key = sha256_bytes(canonical_json(material).encode())
    folder = root / 'calls'
    folder.mkdir(exist_ok=True, mode=0o700)
    index = folder / (key + '.json')
    def read_blob(digest):
        raw = (root / 'blobs' / digest[:2] / digest).read_bytes()
        if sha256_bytes(raw) != digest:
            raise VisualPairError('visual_pair_evidence_changed')
        return raw
    if index.exists():
        pointer = json.loads(index.read_text())
        saved = json.loads(read_blob(pointer['call_sha256']))
        if saved.get('failure'):
            error = TransportError(saved['failure'])
            error.receipt_sha256 = saved['receipt_sha256']
            raise error
        if sha256_bytes(saved['text'].encode()) != saved['content_sha256']:
            raise VisualPairError('visual_pair_evidence_changed')
        return ChatResult(**{**saved, 'cached': True}, request_bytes=read_blob(saved['request_sha256']),
                          response_bytes=read_blob(saved['response_sha256']))
    attempt = {'model': model, 'manifest': manifest,
               'image_sha256': sha256_bytes(kwargs['image_jpeg']),
               'prompt_sha256': _blob(root, prompt.encode())}
    client.evidence_sink = lambda label, raw: attempt.update({label + '_sha256': _blob(root, raw)})
    try:
        result = client.chat(model, prompt, **kwargs)
    except TransportError as error:
        attempt['failure'] = str(error)
        receipt_sha = _json_blob(root, attempt)
        from vlm.receipts import dump_new
        failure = {'failure': str(error), 'receipt_sha256': receipt_sha}
        dump_new(index, {'call_sha256': _json_blob(root, failure)})
        index.chmod(0o600)
        error.receipt_sha256 = receipt_sha
        raise
    _blob(root, result.request_bytes)
    _blob(root, result.response_bytes)
    saved = asdict(result)
    saved.pop('request_bytes')
    saved.pop('response_bytes')
    from vlm.receipts import dump_new
    dump_new(index, {'call_sha256': _json_blob(root, saved)})
    index.chmod(0o600)
    return result


def _record_call(root: Path, result, prompt: str, *, page: int, stage: str,
                 image_sha: str, manifest: dict, purpose: str | None = None,
                 batch_index: int | None = None, batch_count: int | None = None) -> dict:
    # Exact request and response bytes, not just the model's extracted message.
    request_sha = _blob(root, result.request_bytes)
    response_sha = _blob(root, result.response_bytes)
    content_sha = _blob(root, result.text.encode())
    if request_sha != result.request_sha256 or response_sha != result.response_sha256:
        raise VisualPairError('visual_pair_transport_evidence_mismatch')
    receipt = {'page': page, 'stage': stage, 'image_sha256': image_sha,
               'request_sha256': request_sha, 'response_sha256': response_sha,
               'content_sha256': content_sha, 'prompt_sha256': _blob(root, prompt.encode()),
               'manifest': manifest, 'finish_reason': result.finish_reason,
               'prompt_tokens': result.prompt_tokens, 'completion_tokens': result.completion_tokens,
               'total_ms': result.total_ms, 'cached': result.cached}
    receipt.update({key: value for key, value in {'purpose': purpose, 'batch_index': batch_index,
                                                'batch_count': batch_count}.items() if value is not None})
    receipt['receipt_sha256'] = _json_blob(root, receipt)
    return receipt


def _account_meta(account: dict, daily=()):
    from vlm.metadata import AccountMeta
    dec = lambda key: None if account.get(key) is None else Decimal(str(account[key]))
    return AccountMeta(dec('beginning_balance'), dec('ending_balance'), account.get('period_start'),
                       account.get('period_end'), account.get('currency'),
                       account.get('account_number') or account.get('account_number_last4'), account.get('bank'), ('visual_pair',),
                       dec('stated_total_credits'), dec('stated_total_debits'),
                       account.get('stated_credit_count'), account.get('stated_debit_count'),
                       account_name=account.get('account_name'), account_number=account.get('account_number'),
                       days_in_period=account.get('days_in_period'),
                       stated_service_charge=dec('stated_service_charge'),
                       stated_interest_paid=dec('stated_interest_paid'),
                       stated_nsf_count=account.get('stated_nsf_count'),
                       bank_reported_average_balance=dec('bank_reported_average_balance'),
                       bank_reported_average_label=account.get('bank_reported_average_label'),
                       stated_daily_balances=tuple((v['date'], Decimal(str(v['balance']))) for v in daily))


def _statement(rows, account: dict, daily: list[dict], *, currency_source: str = 'model_extracted') -> dict:
    from vlm.gate import statement_from
    from analysis.schema import Statement
    base = statement_from(list(rows), _account_meta(account)).model_dump(exclude_computed_fields=True)
    for key, value in account.items():
        if key in Statement.model_fields and key not in {'currency_source', 'transactions'}:
            base[key] = value
    base['account_number'] = account.get('account_number') or account.get('account_number_last4')
    base['currency_source'] = currency_source
    base['stated_daily_balances'] = daily
    return Statement.model_validate(base).model_dump(exclude_computed_fields=True)


def ledger_rows(merges) -> tuple[list, int]:
    """(rows entering the ledger, rows excluded). A cheque picture page (review.picture_page) shows cheques or
    deposit slips whose transactions are already listed elsewhere in the statement, so its rows never enter
    the ledger. If a real transaction page were taken for pictures, its missing rows break the arithmetic and
    the gate refuses: this fails closed. Descriptions are published on one line and a bare cheque number is
    named by its column's printed label (assemble.published_row)."""
    from vlm.assemble import published_row
    from vlm.review import picture_page
    rows, excluded = [], 0
    for merged in merges:
        if picture_page(merged):
            excluded += len(merged.rows)
            continue
        rows.extend(published_row(row) for row in merged.rows)
    return rows, excluded


_SUMMARY_FIELDS = ('stated_total_credits', 'stated_total_debits', 'stated_credit_count', 'stated_debit_count')


def apply_summary_box(account: dict, reasons: list, occurrences: list, field_evidence: list, pages) -> dict | None:
    """When the statement's printed account summary is proven (vlm/summary_box.py: every category line of the
    box balances this statement's beginning to its ending, to the cent), its sums are the statement's totals and
    counts. A reviewer figure they replace is recorded as superseded, and a disagreement between reviewer
    figures for a proven field is settled by the proof, not held. A proof never supersedes reviewer totals that
    balance the statement on their own: two different readings that both balance leave the printed reviewer
    figures in place (the gate then checks the ledger against them). Mutates the merged account and reasons in
    place; returns the audit entry, or None when nothing is proven."""
    from vlm.summary_box import prove_summary_box
    proof = prove_summary_box(pages, beginning=account.get('beginning_balance'), ending=account.get('ending_balance'))
    if proof is None:
        return None
    reviewer = [account.get(field) for field in ('stated_total_credits', 'stated_total_debits')]
    if None not in reviewer:
        credits, debits = (Decimal(str(value)) for value in reviewer)
        balances = (Decimal(str(account['beginning_balance'])) + credits - debits
                    == Decimal(str(account['ending_balance'])))
        if balances and (credits, debits) != (proof.stated_total_credits, proof.stated_total_debits):
            return {'proven': True, 'applied': False, 'reason': 'reviewer_totals_also_balance',
                    'page': proof.page, 'category_lines': proof.line_count}
    proven = {}
    for field in _SUMMARY_FIELDS:
        value = getattr(proof, field)
        if value is not None:
            proven[field] = float(value) if isinstance(value, Decimal) else value
    superseded = sorted(field for field, value in proven.items()
                        if account.get(field) is not None and Decimal(str(account[field])) != Decimal(str(value)))
    account.update(proven)
    # A count the box does not print is the reviewer's reading. Read on the proven summary page it is the
    # statement's own count; a different count read on another page is a section's (a cheques section's own
    # count). It stands, and the gate still checks it against the ledger.
    counts_from_summary_page = []
    for field in ('stated_credit_count', 'stated_debit_count'):
        if field in proven or account.get(field) is None:
            continue
        read_there = any(item.get('field') == field and item.get('page') == proof.page
                         and item.get('source') == 'reviewer' and item.get('value') == account[field]
                         for item in field_evidence)
        if read_there and any(item.get('code') == 'anchor_disagreement' and item.get('field') == field
                              for item in occurrences):
            counts_from_summary_page.append(field)
    settled = [item for item in occurrences if item.get('code') == 'anchor_disagreement'
               and item.get('field') in (*proven, *counts_from_summary_page)]
    for item in settled:
        occurrences.remove(item)
        reasons.remove('anchor_disagreement')
    field_evidence.extend({'field': field, 'page': proof.page, 'source': 'summary_box', 'value': value}
                          for field, value in proven.items())
    return {'proven': True, 'applied': True, 'page': proof.page, 'category_lines': proof.line_count,
            'fields': sorted(proven), 'superseded_reviewer_fields': superseded, 'settled_disagreements': len(settled),
            'counts_from_summary_page': counts_from_summary_page}


def statement_bank_names(field_evidence, merges) -> list[str]:
    """Distinct bank names the reviewer read on the statement's own pages, in page order. Names read on cheque
    picture pages are other parties' banks and never count."""
    from vlm.review import picture_page
    pictures = {merged.page for merged in merges if picture_page(merged)}
    names = [str(item['value']) for item in field_evidence
             if item.get('field') == 'bank' and item.get('value') and item.get('page') not in pictures]
    return list(dict.fromkeys(names))


def held_pages(merges, page_errors, truncated) -> list[int]:
    """Page numbers that hold the statement.

    Owner ruling, 2026-09-22 ("Hold"): a cut-off read holds its page. `truncated` is the proposer's read after
    crop recovery OR the reviewer's; a proposal that recovery completed is not cut off. Errors, unresolved
    rows and quarantined metadata hold it too. A cheque picture page (review.picture_page) never holds."""
    from vlm.review import picture_page
    held = []
    for idx, (errors, cut) in enumerate(zip(page_errors, truncated)):
        merged = merges[idx]
        if picture_page(merged):
            continue
        if errors or cut or merged.counts.get('unresolved', 0) or merged.metadata_evidence:
            held.append(idx + 1)
    return held


def page_texts(merges, truncated) -> list[PageText]:
    """The page text offered to a bank reader, one per page. A cheque picture page offers none, and is
    complete: nothing read from it is used."""
    from vlm.review import picture_page
    return [PageText('', finish_reason='stop') if picture_page(merged)
            else PageText(_markdown_page(merged), finish_reason='length' if cut else 'stop')
            for merged, cut in zip(merges, truncated)]


def _markdown_page(merged, *, rows=None) -> str:
    # A normalized projection of reviewed evidence; original model text is never
    # accidentally offered to a bank parser after a correction or rejection.
    parts = []
    labels = {'bank': 'Bank', 'account_name': 'Account name', 'account_number_last4': 'Account', 'account_number': 'Account',
              'currency': 'Currency', 'period_start': 'Period start', 'period_end': 'Period end',
              'beginning_balance': 'Beginning balance', 'ending_balance': 'Ending balance',
              'stated_total_credits': 'Total deposits and credits', 'stated_total_debits': 'Total withdrawals and debits'}
    for key, value in merged.account.items():
        if value is not None:
            parts.append(f'{labels.get(key, key)}: {html.escape(str(value))}')
    parts.append('<table><tr><th>Date</th><th>Description</th><th>Debit</th><th>Credit</th><th>Balance</th></tr>')
    from vlm.assemble import published_row
    # The bank reader is offered the descriptions the gated statement carries (one line; a cheque named by its
    # column).
    for row in map(published_row, merged.rows if rows is None else rows):
        amount = row.printed_amount if row.printed_amount is not None else row.amount
        values = (row.date or row.date_text, row.description,
                  str(amount) if row.direction == 'debit' else '',
                  str(amount) if row.direction == 'credit' else '',
                  '' if row.balance is None else str(row.balance))
        parts.append('<tr>' + ''.join('<td>'+html.escape(str(v))+'</td>' for v in values) + '</tr>')
    parts.append('</table>')
    if merged.daily_balances:
        parts.append('Daily balances\n'+'\n'.join(f"{v['date']} {v['balance']}" for v in merged.daily_balances))
    return '\n'.join(parts)


def proposal_candidate_errors(layout, recovery: dict) -> dict[str, tuple[str, ...]]:
    """Attribute failed Stage A responses to their own candidate occurrences.

    A complete crop and a failed crop share a page and source label. Only the
    recorded lineage identifies which response produced each candidate. These
    errors never apply to Stage B additions or independently reviewed metadata.
    """
    from vlm.review import candidate_records

    def source_errors(source: dict, *extra) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*source.get('errors', ()),
                                   *(('stage_a_truncated',) if source.get('truncated') else ()),
                                   *(code for code in extra if code))))

    if not recovery.get('attempted'):
        errors = source_errors({'errors': layout.errors, 'truncated': layout.truncated})
        return {item['candidate_id']: errors for item in candidate_records(layout.rows)} if errors else {}

    by_locator = {}
    original = recovery.get('original', {}).get('layout', {})
    original_errors = source_errors(original)
    for item in recovery.get('original_candidate_lineage', ()):
        by_locator[item['locator']] = original_errors
    for crop in recovery.get('crops', ()):
        errors = () if crop.get('complete') else source_errors(crop.get('layout', {}), crop.get('failure'))
        for item in crop.get('lineage', {}).get('rows', ()):
            by_locator[item['locator']] = tuple(dict.fromkeys((*errors,
                *(code for code in (item.get('held_reason'), item.get('geometry_held_reason')) if code))))
    # A failure before crops/lineage were created leaves the original rows intact.
    if not recovery.get('original_candidate_lineage') and not recovery.get('crops'):
        for row in layout.rows:
            by_locator[row.locator] = source_errors(original, recovery.get('failure'))
    result = {}
    for item in candidate_records(layout.rows):
        errors = by_locator.get(item['locator'], ('proposal_candidate_provenance_missing',))
        if errors:
            result[item['candidate_id']] = errors
    return result


def extract_visual_pair(pdf: Path, *, settings: VisualPairSettings | None = None,
                        evidence_dir: Path, progress: Callable[[str], None] | None = None,
                        data_scope: str = 'customer') -> StatementMarkdown:
    from vlm.assemble import parse_dots_layout
    from vlm.gate import gate
    from vlm.prompts import STAGE_A_DOTS_PROMPT, stage_b_review_prompt
    from vlm.render import render_pages
    from vlm.review import merge_review, confidence_summary
    from vlm.review_batches import REVIEW_BATCH_THRESHOLD, ReviewReply, review_batched_page
    from vlm.proposal_recovery import recover_proposal_page
    from vlm.schema import PAGE_REVIEW_SCHEMA, empty_review

    cfg = settings or load_visual_pair_settings()
    report = progress or (lambda _: None)
    from ocr.private_artifacts import validate_private_artifact_path
    evidence_dir = validate_private_artifact_path(evidence_dir)
    raw = Path(pdf).read_bytes()
    if not raw.startswith(b'%PDF'):
        raise VisualPairError('visual_pair_pdf_required')
    pdf_sha = sha256_bytes(raw)
    check_remote_authorization(cfg, data_scope=data_scope, pdf_sha256=pdf_sha)
    evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = visual_pair_settings_key_material(cfg)
    run_key = sha256_bytes(canonical_json({'pdf': pdf_sha, 'config': manifest}).encode())
    index = evidence_dir / (run_key + '.json')
    if index.exists():
        cached = json.loads(index.read_text())
        body = cached['document']
        if _json_blob(evidence_dir, body) != cached['document_sha256']:
            raise VisualPairError('visual_pair_cache_changed')
        return StatementMarkdown(source_file=Path(pdf).name, model=MODEL_TOKEN,
                                 pages=body['pages'], page_extractor=[MODEL_TOKEN]*len(body['pages']),
                                 page_integrity=[PageIntegrity(**item) for item in body['page_integrity']],
                                 visual_pair=body['visual_pair'])
    proposer, reviewer = _client(cfg.proposer_url, cfg.timeout), _client(cfg.reviewer_url, cfg.timeout)
    manifest['served_models'] = [_check_model(proposer, cfg.proposer_model, cfg.proposer_revision),
                                 _check_model(reviewer, cfg.reviewer_model, cfg.reviewer_revision)]
    _blob(evidence_dir, raw)
    report('visual_pair_rendering')
    pages = render_pages(raw, dpi=cfg.render_dpi, image_format=cfg.render_format)
    if not pages:
        raise VisualPairError('visual_pair_no_pages')
    layouts, calls, failed_calls, page_errors, truncated, recoveries = [], [], [], [], [], []
    proposal_errors, review_truncated, candidate_errors = [], [], []
    # Every page is proposed before review; a failure retains its position.
    for page in pages:
        report(f'visual_pair_proposing:{page.index+1}/{len(pages)}')
        image_sha = _blob(evidence_dir, page.jpeg)
        errors = []
        cut = False
        original_receipt = None
        try:
            result = _chat_once(evidence_dir, proposer, cfg.proposer_model, STAGE_A_DOTS_PROMPT,
                                   manifest=manifest, image_jpeg=page.jpeg,
                                   max_tokens=cfg.max_tokens, seed=cfg.seed, disable_thinking=False)
            calls.append(_record_call(evidence_dir, result, STAGE_A_DOTS_PROMPT,
                                     page=page.index+1, stage='proposer', image_sha=image_sha,
                                     manifest=manifest, purpose='full_page'))
            original_receipt = calls[-1]['receipt_sha256']
            cut = result.finish_reason != 'stop' or result.completion_tokens >= cfg.max_tokens
            layout = parse_dots_layout(result.text, page=page.index+1, width=page.width,
                                       height=page.height, finish_reason=result.finish_reason)
            errors.extend(layout.errors)
            cut = cut or layout.truncated
        except TransportError as exc:
            failed_calls.append({'page': page.index+1, 'stage': 'proposer',
                                 'receipt_sha256': getattr(exc, 'receipt_sha256', None)})
            layout = parse_dots_layout([], page=page.index+1, width=page.width, height=page.height)
            errors.append('proposer_transport_failed')
        layout = replace(layout, errors=tuple(errors), truncated=cut)

        def read_crop(crop):
            report(f'visual_pair_proposing:{page.index+1}/{len(pages)}:crop:{crop.index+1}/2')
            crop_sha = _blob(evidence_dir, crop.jpeg)
            try:
                result = _chat_once(evidence_dir, proposer, cfg.proposer_model, STAGE_A_DOTS_PROMPT,
                                    manifest=manifest, image_jpeg=crop.jpeg,
                                    max_tokens=cfg.max_tokens, seed=cfg.seed, disable_thinking=False)
                calls.append(_record_call(evidence_dir, result, STAGE_A_DOTS_PROMPT,
                                          page=page.index+1, stage='proposer', image_sha=crop_sha,
                                          manifest=manifest, purpose='crop_recovery',
                                          batch_index=crop.index+1, batch_count=2))
                parsed = parse_dots_layout(result.text, page=page.index+1, width=crop.width,
                                           height=crop.height, finish_reason=result.finish_reason)
                return replace(parsed, truncated=parsed.truncated or result.finish_reason != 'stop'
                               or result.completion_tokens >= cfg.max_tokens)
            except TransportError as exc:
                failed_calls.append({'page': page.index+1, 'stage': 'proposer',
                                     'purpose': 'crop_recovery', 'batch_index': crop.index+1,
                                     'receipt_sha256': getattr(exc, 'receipt_sha256', None)})
                raise

        recovery = recover_proposal_page(page.jpeg, layout, read_crop,
                                          original_receipt_sha256=original_receipt)
        recoveries.append(recovery.audit)
        layout = recovery.layout
        layouts.append(layout)
        proposal_errors.append(list(layout.errors))
        # A partial proposal (a truncated read that still produced rows) is held row by row. A proposer that
        # produced NO reading of the page is different: every row on it would come from the reviewer alone,
        # with no second reader, so the page itself is unresolved. Scoping this failure to "its rows" would
        # hold nothing and let a single-read page pass as a paired one.
        page_errors.append(['proposer_transport_failed']
                           if 'proposer_transport_failed' in layout.errors and not layout.rows else [])
        truncated.append(layout.truncated)
        review_truncated.append(False)
        candidate_errors.append(proposal_candidate_errors(layout, recovery.audit))
    merges = []
    # Printed dates found by the deterministic assembler may appear on a later
    # summary page. They may resolve row years, never supply absent anchors.
    from vlm.assemble import text_lines_from_blocks
    from vlm.metadata import extract_meta
    preliminary = extract_meta(text_lines_from_blocks([b for layout in layouts for b in layout.blocks]))
    metadata_context = {field: getattr(preliminary, field) for field in ('period_start', 'period_end')
                        if getattr(preliminary, field) is not None}
    # What each page shows in print from sources other than the reviewer: the PDF's own text layer (None for a
    # scanned page) and the proposer's reading. Local only. It settles a reviewer that contradicts itself about
    # a description and drops reported figures printed nowhere (vlm/native_text.py).
    from vlm.native_text import PrintedEvidence, layout_text, native_page_texts
    from vlm.summary_box import page_lines
    try:
        native_texts = native_page_texts(raw)
    except Exception:  # an unreadable text layer is simply absent evidence
        native_texts = []
    printed_pages = [PrintedEvidence(native=native_texts[index] if index < len(native_texts) else None,
                                     proposer=layout_text(layout.blocks))
                     for index, layout in enumerate(layouts)]
    # A page with neither a text layer nor a proposer reading has nothing to ground against: no printed evidence.
    printed_pages = [evidence if evidence.native or evidence.proposer.strip() else None for evidence in printed_pages]
    for page, layout in zip(pages, layouts):
        def request_review(prompt, schema, schema_name, *, purpose, batch_index=None, batch_count=None):
            context = {key: value for key, value in {'purpose': purpose, 'batch_index': batch_index,
                                                    'batch_count': batch_count}.items() if value is not None}
            suffix = (f':batch:{batch_index}/{batch_count}' if batch_index is not None else
                      ':discovery' if purpose == 'page_discovery' else '')
            report(f'visual_pair_reviewing:{page.index+1}/{len(pages)}{suffix}')
            try:
                result = _chat_once(evidence_dir, reviewer, cfg.reviewer_model, prompt,
                                   manifest=manifest, image_jpeg=page.jpeg, schema=schema, schema_name=schema_name,
                                   max_tokens=cfg.max_tokens, seed=cfg.seed, disable_thinking=True,
                                   preserve_schema_order=True)
                calls.append(_record_call(evidence_dir, result, prompt, page=page.index+1,
                                         stage='reviewer', image_sha=page.jpeg_sha256, manifest=manifest, **context))
                cut = result.finish_reason != 'stop' or result.completion_tokens >= cfg.max_tokens
                return ReviewReply(result.parsed, cut, ('reviewer_json_invalid',) if result.parsed is None else ())
            except TransportError as exc:
                failed_calls.append({'page': page.index+1, 'stage': 'reviewer', **context,
                                     'receipt_sha256': getattr(exc, 'receipt_sha256', None)})
                return ReviewReply(None, errors=('reviewer_transport_failed',))

        if len(layout.rows) > REVIEW_BATCH_THRESHOLD:
            reviewed = review_batched_page(
                layout.rows, page_number=page.index+1, page_total=len(pages), call=request_review,
                metadata_context=metadata_context,
                candidate_validation_errors=candidate_errors[page.index],
                printed=printed_pages[page.index],
            )
            merged = reviewed.merged
            review_truncated[page.index] = reviewed.truncated
            truncated[page.index] |= reviewed.truncated
        else:
            prompt = stage_b_review_prompt(list(layout.rows), page_number=page.index+1,
                                           page_total=len(pages), metadata_context=metadata_context)
            reply = request_review(prompt, PAGE_REVIEW_SCHEMA, 'page_review', purpose='full_page')
            review_truncated[page.index] = reply.truncated
            truncated[page.index] |= reply.truncated
            merged = merge_review(list(layout.rows), reply.payload if reply.payload is not None else empty_review(),
                                  page=page.index+1, truncated=reply.truncated,
                                  validation_errors=reply.errors,
                                  candidate_validation_errors=candidate_errors[page.index],
                                  printed=printed_pages[page.index])
        merges.append(merged)
        page_errors[page.index].extend(merged.errors)
        for field in ('period_start', 'period_end'):
            if merged.account.get(field) is not None:
                metadata_context.setdefault(field, merged.account[field])
    report('visual_pair_gating')
    # Cheque pictures echoed as transactions are recognized from the ledger itself, whatever the page label;
    # every consumer below (segments, metadata, ledger, holds, confidence, page text) sees the same pages.
    from vlm.review import mark_ledger_echoes
    merges = mark_ledger_echoes(merges)
    occurrences = []
    from vlm.segment_openings import extract_printed_opening
    from vlm.segment_reconcile import reconcile_page_segments
    from vlm.segments import detect_page_segments
    opening_observations = {}
    for layout in layouts:
        # Bind the observation to the exact parsed source, including page,
        # block text and geometry. No reviewer observation is overwritten.
        source = {'page': layout.page, 'blocks': [asdict(block) for block in layout.blocks],
                  'errors': list(layout.errors), 'truncated': layout.truncated}
        source_sha = _json_blob(evidence_dir, source)
        observation = extract_printed_opening(layout, evidence_sha256=source_sha)
        if observation is not None:
            opening_observations[layout.page] = observation
    segment_plan = detect_page_segments(merges, opening_observations=opening_observations)
    account, daily, reasons, field_evidence = _merge_metadata(
        merges, occurrences=occurrences, segment_plan=segment_plan)
    summary_box = apply_summary_box(
        account, reasons, occurrences, field_evidence,
        [page_lines(native_texts[index] if index < len(native_texts) else None, layout.blocks)
         for index, layout in enumerate(layouts)])
    rows, cheque_rows_excluded = ledger_rows(merges)
    # The reviewed printed month/day and reviewed period can determine a
    # missing ISO date without another model reading. This is a separate
    # deterministic record, never a rewrite of either model's source evidence.
    from vlm.dates import DATE_RESOLVER_VERSION, resolve_reviewed_dates
    dates = resolve_reviewed_dates(
        rows,
        period_start=account.get('period_start') if 'period_mismatch' not in reasons else None,
        period_end=account.get('period_end') if 'period_mismatch' not in reasons else None,
    )
    rows = list(dates.rows)
    # A mid-day figure at a page break is not the day's close when no later page prints one.
    page_break_dates = page_break_figures(merges, rows)
    daily = [item for item in daily if item['date'] not in page_break_dates]
    segment_checks, segment_occurrences = reconcile_page_segments(segment_plan, rows)
    occurrences.extend(segment_occurrences)
    reasons.extend(item['code'] for item in segment_occurrences)
    unresolved_pages = held_pages(merges, page_errors, truncated)
    for page_number in unresolved_pages:
        reasons.append('page_unresolved')
        occurrences.append({'code': 'page_unresolved', 'page': page_number, 'source': 'page_review'})
    verdict = None
    try:
        # Incomplete ledgers retain independent row checks. Whole-document
        # arithmetic waits for the missing pages, avoiding false sum/summary
        # failures without hiding defects on the pages already reviewed.
        verdict = gate(rows, _account_meta(account, daily), complete_document=not unresolved_pages)
        reasons.extend(verdict.reasons)
        occurrences.extend(verdict.occurrences)
        checks = verdict.checks
        if unresolved_pages:
            checks['unresolved_pages'] = unresolved_pages
    except (ValueError, TypeError, ArithmeticError):
        checks = {}
        reasons.append('proposal_invalid')
        occurrences.append({'code': 'proposal_invalid', 'page': None, 'source': 'gate_input'})
    currency_resolution = None
    currency_bridge_source_sha = None
    currency_source = 'model_extracted'
    # Currency evidence is independent of other failures. A faithful existing
    # parser rule may fill absence, but cannot erase a contradictory currency
    # observation or clear any unrelated gate reason.
    if not account.get('currency'):
        from vlm.currency import CurrencyResolution, resolve_currency
        visual_pages = ['\n'.join(block.content for block in layout.blocks) for layout in layouts]
        visual_markdown = '\n\n'.join(visual_pages)
        currency_bridge_source_sha = _blob(evidence_dir, visual_markdown.encode())
        try:
            source_rows = verdict.admitted_rows if verdict is not None and verdict.admitted else rows
            reviewed_source = _statement(source_rows, account, daily)
            reviewed_source['currency'] = None  # never inherit Statement's legacy USD default
            # The bridge must see unknown source fields as unknown. The legacy
            # Statement projection uses placeholders that are not evidence.
            for transaction, row in zip(reviewed_source['transactions'], source_rows):
                transaction['direction'] = row.direction
                transaction['date'] = row.date
            resolution = resolve_currency(reviewed_source, visual_markdown, sheets=visual_pages)
        except (ValueError, TypeError, ArithmeticError):
            resolution = CurrencyResolution('unresolved', 'source_statement_invalid')
        currency_resolution = asdict(resolution)
        if resolution.resolved:
            account['currency'] = resolution.currency
            currency_source = resolution.currency_source
            reasons = [reason for reason in reasons if reason != 'currency_missing']
            occurrences = [event for event in occurrences if event['code'] != 'currency_missing']
            field_evidence.append({'field': 'currency', 'page': None, 'source': 'existing_parser_rule',
                                   'value': resolution.currency, 'currency_source': currency_source,
                                   'parser_id': resolution.parser_id,
                                   'visual_source_sha256': currency_bridge_source_sha})
    # Owner ruling, 2026-09-22: no printed currency means USD unless the bank is Canadian. Only when nothing
    # printed and no proven rule decided it, and never over two conflicting printed currencies.
    currency_default = None
    if not account.get('currency') and 'currency_conflict' not in reasons:
        from vlm.currency import usd_default
        # Every bank name the statement's own pages print counts: a Canadian one on any page refuses the default.
        currency_default = usd_default(' '.join(statement_bank_names(field_evidence, merges)) or account.get('bank'),
                                       ['\n'.join(block.content for block in layout.blocks) for layout in layouts])
        if currency_default['currency']:
            account['currency'] = currency_default['currency']
            currency_source = currency_default['currency_source']
            reasons = [reason for reason in reasons if reason != 'currency_missing']
            occurrences = [event for event in occurrences if event['code'] != 'currency_missing']
            field_evidence.append({'field': 'currency', 'page': None, 'source': 'owner_ruling_default',
                                   'value': currency_default['currency'], 'currency_source': currency_source,
                                   'ruling': currency_default['ruling']})
    from vlm.reason_counts import summarize_occurrences
    reasons = list(dict.fromkeys(reasons))
    reason_counts = summarize_occurrences(occurrences)
    admitted = verdict is not None and verdict.admitted and not reasons
    confidence = confidence_summary(merges, gate_admitted=admitted, gate_reasons=reasons)
    # The statement's score is its verification coverage (vlm/confidence.py); the per-page review agreement
    # stays alongside it.
    from vlm.confidence import completion_only, statement_confidence
    row_states = {(item['page'], item['locator']): (item['state'], (item.get('resolution') or {}).get('method'),
                                                    completion_only(item))
                  for merged in merges for item in merged.evidence}
    confidence.update(statement_confidence(
        admitted=admitted and confidence['gate_admitted'], checks=checks, account=account,
        rows=verdict.admitted_rows if admitted else rows, row_states=row_states, printed_pages=printed_pages,
        reasons=reasons))
    statement = _statement(verdict.admitted_rows, account, daily, currency_source=currency_source) if admitted else None
    page_text = page_texts(merges, truncated)
    integrity = assess_pages(page_text)
    audit = {'version': PAIR_VERSION, 'account_count': 1, 'statement': statement,
             'gate': {'admitted': admitted, 'reasons': reasons, 'checks': checks,
                      'reason_occurrences': occurrences, 'reason_counts': reason_counts},
             'confidence': confidence, 'field_evidence': field_evidence,
             'page_segments': {'plan': json.loads(canonical_json(asdict(segment_plan))),
                               'reconciliation': segment_checks},
             'date_resolution': {
                 'version': DATE_RESOLVER_VERSION,
                 'resolved_count': sum(item.get('resolved_date') is not None for item in dates.evidence),
                 'unresolved_count': dates.unresolved,
                 'rows': list(dates.evidence),
                 'period_evidence': [item for item in field_evidence
                                     if item['field'] in ('period_start', 'period_end')],
             },
             'source_daily_balance_count': len(daily),
             'row_evidence': [item for merged in merges for item in merged.evidence],
             'review_diagnostics': [item for merged in merges for item in merged.diagnostics],
             'review_metadata_evidence': [item for merged in merges for item in merged.metadata_evidence],
             'proposal_recoveries': recoveries,
             'pages': [{'page': idx+1, 'errors': errors, 'truncated': truncated[idx],
                        'review_truncated': review_truncated[idx],
                        'proposal_errors': proposal_errors[idx],
                        'source_candidate_error_count': len(candidate_errors[idx]),
                        'review_status': 'unresolved' if idx+1 in unresolved_pages else 'reviewed',
                        'reason_counts': summarize_occurrences(
                            event for event in occurrences if event['page'] == idx+1),
                        'initial_proposer_truncated': bool(recoveries[idx].get('original', {}).get('layout', {}).get('truncated')),
                        'proposal_recovery_attempted': recoveries[idx]['attempted'],
                        'proposal_recovered': recoveries[idx].get('recovered', False),
                        'counts': merges[idx].counts,
                        'warnings': list(getattr(layouts[idx], 'warnings', ()))}
                       for idx, errors in enumerate(page_errors)]}
    if currency_resolution is not None:
        audit['currency_resolution'] = currency_resolution
        audit['currency_bridge_source_sha256'] = currency_bridge_source_sha
    if currency_default is not None:
        audit['currency_default'] = currency_default
    audit['cheque_image_rows_excluded'] = cheque_rows_excluded
    audit['ledger_echo_pages'] = [merged.page for merged in merges if merged.ledger_echo]
    audit['summary_box'] = summary_box
    audit['daily_page_break_figures_dropped'] = sorted(page_break_dates)
    if admitted:
        from vlm.review import row_record
        audit['gate_rows'] = [{**row_record(row), 'page': row.page, 'locator': row.locator,
                              'direction_source': row.direction_source,
                              'source': 'deterministic_gate'} for row in verdict.admitted_rows]
    receipt = {'version': PAIR_VERSION, 'pdf_sha256': pdf_sha, 'manifest': manifest,
               'calls': calls, 'failed_calls': failed_calls,
               'result_sha256': _json_blob(evidence_dir, audit)}
    audit['receipt_sha256'] = _json_blob(evidence_dir, receipt)
    body = {'pages': list(map(str, page_text)), 'page_integrity': [asdict(v) for v in integrity],
            'visual_pair': audit}
    record = {'document': body, 'document_sha256': _json_blob(evidence_dir, body)}
    # Exclusive creation: reruns never silently replace model evidence.
    from vlm.receipts import dump_new
    dump_new(index, record)
    index.chmod(0o600)
    return StatementMarkdown(source_file=Path(pdf).name, model=MODEL_TOKEN,
                             pages=body['pages'], page_extractor=[MODEL_TOKEN]*len(pages),
                             page_integrity=integrity, visual_pair=audit,
                             extraction_telemetry={'execution_class': cfg.execution_class,
                                                  'customer_data_opt_in': cfg.customer_data_opt_in,
                                                  'pages': [{'page': c['page'], 'stage': c['stage'],
                                                              'total_ms': c['total_ms'],
                                                              'prompt_tokens': c['prompt_tokens'],
                                                              'completion_tokens': c['completion_tokens'],
                                                              'execution_class': cfg.execution_class}
                                                              for c in calls if not c['cached']]})

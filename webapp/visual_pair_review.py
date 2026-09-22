"""Local review of retained visual evidence, including rows withheld by the gate."""
from __future__ import annotations

from html import escape


_REASONS = {
    'no_rows': 'No complete transaction rows were recovered.',
    'proposal_invalid': 'One or more page readings or row reviews are incomplete.',
    'anchors_underdetermined': 'Opening and closing balance evidence is insufficient.',
    'anchor_derived': 'A required balance was calculated rather than read from the statement.',
    'missing_beginning_balance': 'The printed opening balance is missing.',
    'missing_ending_balance': 'The printed closing balance is missing.',
    'direction_unknown': 'Some transaction debit or credit directions are unknown.',
    'chain_direction_unanchored': 'Transaction directions lack independent balance evidence.',
    'date_unparsed': 'Some transaction dates are missing or unreadable.',
    'duplicate_row': 'Possible duplicate transactions need review.',
    'sum_mismatch': 'The transactions do not reconcile with the printed balances.',
    'continuity_break': 'The printed running balances do not reconcile.',
    'summary_mismatch': 'The transactions do not match the printed totals.',
    'count_mismatch': 'The transaction count differs from the printed count.',
    'coverage_mismatch': 'Transaction coverage is incomplete.',
    'currency_conflict': 'The statement currency is missing or conflicting.',
    'anchor_disagreement': 'Pages contain conflicting statement fields.',
    'period_mismatch': 'The statement period is missing or inconsistent.',
    'date_order_chained': 'Transaction dates and running balance order disagree.',
}
_STATES = {'agreed': 'Confirmed', 'corrected': 'Corrected', 'added': 'Reviewer added',
           'rejected': 'Rejected — excluded', 'unresolved': 'Unresolved — not admitted'}
_FIELDS = (('date_text', 'Printed date'), ('date', 'Resolved date'),
           ('description', 'Description'), ('amount', 'Amount'),
           ('direction', 'Debit / credit'), ('balance', 'Printed balance'))


def _value(row: dict, field: str) -> str:
    value = row.get(field)
    return '<span style="color:#666">Not supplied</span>' if value is None else escape(str(value))


def retained_evidence_html(evidence: dict) -> str:
    """Render data as escaped text only; no model-generated markup is trusted."""
    gate = evidence.get('gate')
    reasons = gate.get('reasons', []) if isinstance(gate, dict) else []
    reasons = reasons if isinstance(reasons, list) else []
    messages = list(dict.fromkeys(_REASONS.get(reason, 'A statement check requires review.')
                                  for reason in reasons if isinstance(reason, str)))
    output = ['<section class="visual-pair-evidence">']
    if messages:
        output.append('<h2>Why this extraction is held</h2><ul>' +
                      ''.join('<li>' + escape(message) + '</li>' for message in messages) + '</ul>')
    rows = evidence.get('row_evidence')
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    resolution = evidence.get('date_resolution')
    resolutions = resolution.get('rows', []) if isinstance(resolution, dict) else []
    resolved_dates = {
        (item['page'], item['locator']): item['resolved_date']
        for item in resolutions if isinstance(item, dict)
        and type(item.get('page')) is int and isinstance(item.get('locator'), str)
        and isinstance(item.get('resolved_date'), str)
    } if isinstance(resolutions, list) else {}
    if rows:
        output.append('<details><summary>Review every proposed row (' + str(len(rows)) + ')</summary>'
                      '<p>Original readings and reviewer changes are retained below. '
                      'Unresolved and rejected rows are not admitted for analysis. '
                      'A confirmed row does not by itself validate the statement.</p>')
        for index, row in enumerate(rows, 1):
            state = _STATES.get(row.get('state'), 'Unknown — not admitted')
            page = row.get('page')
            page_label = str(page) if type(page) is int and page > 0 else '?'
            original = row.get('original') if isinstance(row.get('original'), dict) else {}
            reviewed = next((row[key] for key in ('corrected', 'row')
                             if isinstance(row.get(key), dict)), {})
            # An unchanged confirmation/rejection still has a retained original.
            if not reviewed and row.get('state') == 'agreed':
                reviewed = original
            output.append(f'<details style="margin:1rem 0"><summary>Page {page_label}, row {index}: '
                          f'{escape(state)}</summary><div style="overflow:auto"><table>'
                          '<thead><tr><th>Field</th><th>Original proposal</th>'
                          '<th>Reviewer result</th></tr></thead><tbody>')
            for field, label in _FIELDS:
                output.append('<tr><th>' + label + '</th>' +
                              ''.join('<td style="white-space:pre-wrap;overflow-wrap:anywhere">' +
                                      _value(source, field) + '</td>' for source in (original, reviewed)) + '</tr>')
            output.append('</tbody></table></div>')
            locator = row.get('locator')
            resolved = resolved_dates.get((page, locator)) if type(page) is int and isinstance(locator, str) else None
            if resolved is not None:
                output.append('<p>Date resolved from the printed date and statement period: <strong>'
                              + escape(resolved) + '</strong>. The reader outputs above are unchanged.</p>')
            output.append('</details>')
        output.append('</details>')
    output.append('</section>')
    return ''.join(output)

"""Each account of a statement that prints several, judged on its own (owner rulings R-b, R-e, R-f): the rows
printed under its heading (vlm/accounts.py), the figures printed in its own section, and the same gate every
single-account statement passes. An account is published only when its own ledger reconciles to its own printed
figures; another account's failure never holds it, and nothing is combined across accounts (R-c).

Statuses: "verified" (gated; publishable), "idle" (its section prints equal opening and closing balances, zero or no
totals and no row, on a page with a text layer: no activity), "held" (anything else, with its reasons).
"""
from __future__ import annotations

import html
from decimal import Decimal

from collections import Counter
from dataclasses import replace

from vlm.accounts import (DEPOSIT_KINDS, UNPLACED, assign_rows, listing_echoes, plan_accounts,
                          section_activity_lines, section_figures, summary_table_figures, summary_table_rows)

ACCOUNTS_VERSION = 1
# Document facts every account shares: without them no account can be judged.
_DOCUMENT_BLOCKERS = ("period_mismatch", "currency_conflict", "currency_missing")
_CENT = Decimal("1E-2")  # a cent


def _float(value):
    return None if value is None else float(value)


def _figures_account(figures: dict, document: dict, section) -> tuple[dict, dict]:
    """(account fields for the gate, figure evidence). Totals count only when they carry the printed opening
    balance to the printed closing one; otherwise they describe something else (a year-to-date column)."""
    value = {name: (figures.get(name) or {}).get("value") for name in
             ("beginning_balance", "ending_balance", "stated_total_credits", "stated_total_debits")}
    account = {key: document.get(key) for key in ("period_start", "period_end", "currency", "bank")}
    account.update(account_name=section.title, account_number=section.number,
                   beginning_balance=_float(value["beginning_balance"]),
                   ending_balance=_float(value["ending_balance"]))
    evidence = {"figures": figures, "totals_used": False}
    opening, closing = value["beginning_balance"], value["ending_balance"]
    credits, debits = value["stated_total_credits"], value["stated_total_debits"]
    if None not in (opening, closing, credits, debits) and (opening + credits - debits).quantize(_CENT) == closing:
        account.update(stated_total_credits=float(credits), stated_total_debits=float(debits))
        evidence["totals_used"] = True
    return account, evidence


def _print_style(rows, statement_style: frozenset) -> list:
    """An account's rows with the statement's print style: a debits column printing every amount with a minus
    ("-$5.00") is a style the gate learns from two or more amounts (minus_styled), so an account printing fewer of a
    direction takes it from the statement's other rows; its amounts then count by their magnitude."""
    counts = Counter(row.direction for row in rows if row.printed_amount is not None)
    return [replace(row, printed_amount=abs(row.printed_amount))
            if (row.printed_amount is not None and row.direction in statement_style and counts[row.direction] < 2)
            else row for row in rows]


def _balance_only_additions(rows, opening, dropped=None) -> set:
    """(page, locator) of reviewer additions that move nothing: the amount read is the balance the row prints, and
    that balance is the balance before it (the account's opening balance for its first row). An informational line
    printing only the balance (an "Interest Rate Change" line), which the proposer never read as a transaction.
    ``dropped``: (page, locator) -> the balance the reviewer read where the review dropped it because the row's line
    prints that figure only once (review._ground_balances): that single figure is then the one the amount copies."""
    excluded, before = set(), None if opening is None else Decimal(str(opening))
    for row in rows:
        balance = row.balance if row.balance is not None else (dropped or {}).get((row.page, row.locator))
        if (str(row.locator).startswith("added") and before is not None and balance is not None
                and row.amount != 0 and row.amount == abs(balance) and balance == before):
            excluded.add((row.page, row.locator))
            continue
        before = row.balance
    return excluded


def _balance_line(description) -> bool:
    """A printed balance line ("Beginning Balance", "Ending Balance as of 03/31"): no transaction."""
    from vlm.accounts import _label
    from vlm.assemble import BALANCE_LINE
    text = " ".join(str(description or "").split())
    return bool(text) and (bool(BALANCE_LINE.match(text)) or _label(text) is not None)


def _markdown(rows, account: dict) -> str:
    """The account's own reviewed rows as the analysis's source text: its posting dates are exactly its rows'."""
    from vlm.assemble import published_row
    parts = [f"Account name: {html.escape(str(account.get('account_name') or ''))}",
             f"Period start: {account.get('period_start')}", f"Period end: {account.get('period_end')}",
             f"Beginning balance: {account.get('beginning_balance')}",
             f"Ending balance: {account.get('ending_balance')}",
             '<table><tr><th>Date</th><th>Description</th><th>Debit</th><th>Credit</th><th>Balance</th></tr>']
    for row in map(published_row, rows):
        amount = row.printed_amount if row.printed_amount is not None else row.amount
        values = (row.date or row.date_text, row.description, str(amount) if row.direction == 'debit' else '',
                  str(amount) if row.direction == 'credit' else '', '' if row.balance is None else str(row.balance))
        parts.append('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>' for v in values) + '</tr>')
    parts.append('</table>')
    return '\n'.join(parts)


def judge_accounts(layouts, merges, rows, *, recoveries=(), printed_pages=None, printed_lines=None,
                   document: dict, document_reasons=(), page_errors=(), truncated=(), moneyless_pages=frozenset(),
                   currency_source: str = 'model_extracted', row_states=None, plan=None) -> dict | None:
    """The statement's accounts, each judged on its own; None when it prints fewer than two accounts with content
    (a heading printing no row and no figure is no account)."""
    from vlm.confidence import statement_confidence
    from vlm.gate import gate, minus_styled
    from vlm.pair import _account_meta, _statement, exclude_undirected_by_totals, printed_repeat_groups
    from vlm.review import picture_page, row_record

    plan = plan or plan_accounts(layouts, recoveries)
    if len(plan.sections) < 2:
        return None
    kept, evidence = assign_rows(plan, merges)
    summary = summary_table_figures(plan, layouts, printed_pages)
    statement_style = minus_styled(rows)  # the statement's own print style, from every row it prints
    # Balances the review dropped because the row's line prints the figure only once (review._ground_balances).
    dropped_balances = {(merged.page, item.get('locator')): Decimal(str(item['row']['balance']))
                        for merged in merges for item in merged.evidence
                        if item.get('balance_dropped') and isinstance(item.get('row'), dict)
                        and isinstance(item['row'].get('balance'), (int, float))}
    states = {(merged.page, item.get('locator')): item.get('state') for merged in merges for item in merged.evidence}
    # Proposer rows the reviewer rejected, other than balance lines and daily-balance grids: a printed line that may
    # have been a transaction, so the account it was printed in is never shown to be idle.
    rejected = {(merged.page, item.get('locator')) for merged in merges for item in merged.evidence
                if item.get('state') == 'rejected' and isinstance(item.get('original'), dict)
                and item.get('reason') != 'figure_grid_row'
                and not _balance_line(item['original'].get('description'))}
    pictures = {merged.page for merged in merges if picture_page(merged)}
    pages = sorted({merged.page for merged in merges})
    problem_pages = set()
    for index, merged in enumerate(merges):
        errors = page_errors[index] if index < len(page_errors) else ()
        cut = (truncated[index] if index < len(truncated) else False) and merged.page not in moneyless_pages
        # As on a single account (pair.held_pages): errors, a cut-off read, and reviewer metadata the page's print
        # contradicts hold the page, here the accounts it prints.
        if merged.page not in pictures and (errors or cut or merged.metadata_evidence):
            problem_pages.add(merged.page)
    blockers = [reason for reason in _DOCUMENT_BLOCKERS if reason in document_reasons]
    unplaced = [key for key, section in kept.items() if section == UNPLACED]
    unplaced_pages = {page for page, _ in unplaced}
    unplaced_pages |= {page for (page, locator), section in evidence.items()
                       if section == UNPLACED and states.get((page, locator)) == 'unresolved'}
    # Rows read from a summary table (its rows name the accounts under figure columns) are no account's rows and
    # no sign of an account whose heading went unrecognized.
    descriptions = {(row.page, row.locator): row.description for row in rows}
    for merged in merges:
        for item in merged.evidence:
            row = next((value for value in (item.get('row'), item.get('original')) if isinstance(value, dict)), {})
            descriptions.setdefault((merged.page, item.get('locator')), row.get('description'))
    summary_rows = summary_table_rows(plan, layouts, descriptions)
    outside = [key for key, section in kept.items() if section is None and key not in summary_rows]
    unresolved_outside = [key for key, section in evidence.items()
                          if section is None and states.get(key) == 'unresolved' and key not in summary_rows]
    if outside or unresolved_outside:
        # Rows printed before every recognized heading: an account whose heading was not recognized (the business
        # checking account itself, perhaps). Judging the others alone would drop it from the statement.
        return {'version': ACCOUNTS_VERSION, 'skipped': 'rows_outside_accounts',
                'rows_outside_accounts': len(outside) + len(unresolved_outside)}
    entries, content = [], 0
    for section in plan.sections:
        figures = section_figures(plan, section.index, layouts, printed_pages, summary)
        account_rows = _print_style([row for row in rows if kept.get((row.page, row.locator)) == section.index],
                                    statement_style)
        echoes = listing_echoes(account_rows, plan)
        account_rows = [row for row in account_rows if (row.page, row.locator) not in echoes]
        unmoved = _balance_only_additions(account_rows, (figures.get('beginning_balance') or {}).get('value'),
                                          dropped_balances)
        account_rows = [row for row in account_rows if (row.page, row.locator) not in unmoved]
        unresolved = sorted({page for (page, locator), index in evidence.items()
                             if index == section.index and states.get((page, locator)) == 'unresolved'})
        section_pages = [page for page in pages if section.index in plan.page_sections(page)]
        if not account_rows and not unresolved and not any(item.get('value') is not None for item in figures.values()):
            continue  # a heading with nothing under it (a promotion, a product line): no account
        content += 1
        account, figure_evidence = _figures_account(figures, document, section)
        reasons = list(blockers)
        held_pages = sorted((set(section_pages) & problem_pages) | set(unresolved))
        if held_pages:
            reasons.append('page_unresolved')
        if set(section_pages) & unplaced_pages:
            reasons.append('rows_unplaced')
        entry = {'index': len(entries), 'section': section.index, 'title': section.title, 'kind': section.kind,
                 'deposit_account': section.kind in DEPOSIT_KINDS if section.kind else None,
                 'business': 'business' in section.title.lower(), 'number': section.number,
                 'number_key': section.key, 'pages': section_pages, 'held_pages': held_pages,
                 'headings': [{'page': h.page, 'order': h.order, 'continued': h.continued} for h in section.headings],
                 'row_count': len(account_rows), 'listing_echo_rows': len(echoes),
                 'balance_only_additions': len(unmoved), **figure_evidence}
        statement, verdict, checks = None, None, {}
        if not account_rows:
            opening, closing = account.get('beginning_balance'), account.get('ending_balance')
            totals = [(figures.get(name) or {}).get('value') for name in ('stated_total_credits', 'stated_total_debits')]
            native = all(printed_pages and 0 < page <= len(printed_pages) and printed_pages[page - 1] is not None
                         and printed_pages[page - 1].native for page in section_pages)
            activity = section_activity_lines(plan, section.index, layouts)
            entry['activity_lines'] = activity
            entry['rejected_rows'] = sum(1 for key, placed in evidence.items()
                                         if placed == section.index and key in rejected)
            if (not reasons and opening is not None and opening == closing and native and not activity
                    and not entry['rejected_rows'] and all(total in (None, Decimal('0')) for total in totals)):
                entry.update(status='idle', reasons=[], balance=opening)
            else:
                entry.update(status='held', reasons=reasons + ['no_rows'])
            entries.append(entry)
            continue
        try:
            account_rows, undirected = exclude_undirected_by_totals(account_rows, account)
            verdict = gate(account_rows, _account_meta(account), complete_document=not held_pages,
                           printed_repeats=printed_repeat_groups(account_rows, printed_lines or []))
            reasons.extend(verdict.reasons)
            checks = verdict.checks
            entry['undirected_rows_excluded_by_totals'] = undirected
        except (ValueError, TypeError, ArithmeticError):
            reasons.append('proposal_invalid')
        reasons = list(dict.fromkeys(reasons))
        admitted = verdict is not None and verdict.admitted and not reasons
        if admitted:
            statement = _statement(verdict.admitted_rows, account, [], currency_source=currency_source)
            entry['markdown'] = _markdown(verdict.admitted_rows, account)
            entry['gate_rows'] = [{**row_record(row), 'page': row.page, 'locator': row.locator,
                                   'direction_source': row.direction_source, 'source': 'deterministic_gate'}
                                  for row in verdict.admitted_rows]
        entry.update(status='verified' if admitted else 'held', reasons=reasons, statement=statement,
                     gate={'admitted': admitted, 'reasons': reasons, 'checks': checks})
        entry['confidence'] = statement_confidence(
            admitted=admitted, checks=checks, account=account,
            rows=verdict.admitted_rows if admitted else account_rows, row_states=row_states or {},
            printed_pages=printed_pages or [], reasons=reasons, daily_balances=())
        entries.append(entry)
    if content < 2:
        return None
    for entry in entries:
        if entry.get('balance') is not None:
            entry['balance'] = float(entry['balance'])
        for item in (entry.get('figures') or {}).values():
            item['value'] = None if item.get('value') is None else float(item['value'])
    return {'version': ACCOUNTS_VERSION, 'accounts': entries,
            # Kept rows printed before every account heading (a summary table the reviewer kept), and rows whose
            # place among a page's accounts is unknown (they hold that page's accounts).
            'rows_outside_accounts': len(outside), 'rows_unplaced': len(unplaced),
            'verified': sum(entry['status'] == 'verified' for entry in entries),
            'idle': sum(entry['status'] == 'idle' for entry in entries)}

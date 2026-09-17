"""Stage B page proposals → candidate rows and account metadata; multi-page merge."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.metadata import EMPTY_META, AccountMeta, merge_meta
from vlm.textparse import parse_date, to_decimal


@dataclass(frozen=True)
class PageProposal:
    page: int
    proposal: dict
    errors: tuple[str, ...]


def _money(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return to_decimal(value)
    except ValueError:
        return None


def rows_from_proposal(proposal: dict, *, page: int, year_hint: int | None = None) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    for index, item in enumerate(proposal.get("rows") or []):
        if not isinstance(item, dict):
            continue
        amount = _money(item.get("amount"))
        if amount is None or amount <= 0:
            if item.get("continues_previous") and rows and item.get("description"):
                rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + str(item["description"])).strip())
            continue
        if item.get("continues_previous") and rows:
            rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + str(item.get("description") or "")).strip())
            continue
        date_text = str(item.get("date_text") or "")
        date = item.get("date") if isinstance(item.get("date"), str) else None
        if date is not None and parse_date(date) is None:
            date = None
        if date is None and date_text:
            date = parse_date(date_text, year_hint=year_hint)
        direction = item.get("direction") if item.get("direction") in ("credit", "debit") else "unknown"
        rows.append(CandidateRow(date=date, date_text=date_text, description=str(item.get("description") or ""),
                                 amount=amount, direction=direction, balance=_money(item.get("balance")), page=page,
                                 source="stage_b", locator=f"p{page}r{index}", direction_source="printed"))
    return rows


def meta_from_proposal(proposal: dict) -> AccountMeta:
    account = proposal.get("account") or {}
    period_start = parse_date(account.get("period_start")) if account.get("period_start") else None
    period_end = parse_date(account.get("period_end")) if account.get("period_end") else None
    currency = str(account["currency"]).upper() if account.get("currency") else None
    last4 = str(account["account_number_last4"])[-4:] if account.get("account_number_last4") else None
    meta = AccountMeta(_money(account.get("beginning_balance")), _money(account.get("ending_balance")), period_start,
                       period_end, currency, last4, account.get("bank") or None, ())
    populated = any(getattr(meta, f) is not None for f in ("beginning_balance", "ending_balance", "period_start", "currency"))
    return replace(meta, sources=("meta:stage_b",) if populated else ())


def merge_pages(pages: list[PageProposal]) -> tuple[list[CandidateRow], AccountMeta, dict]:
    rows: list[CandidateRow] = []
    meta = EMPTY_META
    roles: Counter = Counter()
    currencies: list[str] = []
    last4s: list[str] = []
    dropped = 0
    for page in sorted(pages, key=lambda p: p.page):
        if page.errors:
            roles["invalid"] += 1
            continue
        role = page.proposal.get("page_role") or "blank_or_other"
        roles[role] += 1
        page_meta = meta_from_proposal(page.proposal)
        meta = merge_meta(meta, page_meta)
        if page_meta.currency and page_meta.currency not in currencies:
            currencies.append(page_meta.currency)
        if page_meta.account_last4 and page_meta.account_last4 not in last4s:
            last4s.append(page_meta.account_last4)
        if role == "statement_page":
            year_hint = int(meta.period_end[:4]) if meta.period_end else (int(meta.period_start[:4]) if meta.period_start else None)
            items = page.proposal.get("rows") or []
            page_rows = rows_from_proposal(page.proposal, page=page.page, year_hint=year_hint)
            continuations = sum(1 for r in items if isinstance(r, dict) and r.get("continues_previous"))
            dropped += max(0, len(items) - len(page_rows) - continuations)
            rows.extend(page_rows)
    stats = {"pages_by_role": dict(sorted(roles.items())), "invalid_pages": roles.get("invalid", 0),
             "currency_conflict": len(currencies) > 1, "account_last4_values": last4s, "rows_dropped_nonpositive": dropped}
    return rows, meta, stats

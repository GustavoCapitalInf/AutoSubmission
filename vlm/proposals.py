"""Stage B page proposals → candidate rows and account metadata; multi-page merge.

Review closures: BLOCK-1 (no extracted account digits in the public stats: count + digest only),
MAJOR-8 (a row that carries its own amount is never treated as a continuation; the case is counted),
MAJOR-4 (the printed totals and counts flow into AccountMeta).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.metadata import EMPTY_META, AccountMeta, merge_meta
from vlm.receipts import canonical_json, sha256_bytes
from vlm.textparse import parse_date, to_decimal


@dataclass(frozen=True)
class PageProposal:
    page: int
    proposal: dict
    errors: tuple[str, ...]


def _money(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return to_decimal(value)
    except ValueError:
        return None


def _count(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def rows_from_proposal(proposal: dict, *, page: int, year_hint: int | None = None) -> tuple[list[CandidateRow], dict]:
    """Rows in printed order plus a drop ledger: {"nonpositive": n, "continuation_merged": n,
    "continuation_with_amount": n}. A `continues_previous` row WITH a positive amount is kept as a
    row (the flag is ignored and counted), never merged."""
    rows: list[CandidateRow] = []
    drops = {"nonpositive": 0, "continuation_merged": 0, "continuation_with_amount": 0}
    for index, item in enumerate(proposal.get("rows") or []):
        if not isinstance(item, dict):
            drops["nonpositive"] += 1
            continue
        amount = _money(item.get("amount"))
        continues = bool(item.get("continues_previous"))
        if amount is None or amount <= 0:
            if continues and rows and item.get("description"):
                rows[-1] = replace(rows[-1], description=(rows[-1].description + " " + str(item["description"])).strip())
                drops["continuation_merged"] += 1
            else:
                drops["nonpositive"] += 1
            continue
        if continues:
            drops["continuation_with_amount"] += 1
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
    return rows, drops


def meta_from_proposal(proposal: dict) -> AccountMeta:
    account = proposal.get("account") or {}
    period_start = parse_date(account.get("period_start")) if account.get("period_start") else None
    period_end = parse_date(account.get("period_end")) if account.get("period_end") else None
    currency = str(account["currency"]).upper() if account.get("currency") else None
    last4 = str(account["account_number_last4"])[-4:] if account.get("account_number_last4") else None
    credits_total = _money(account.get("stated_total_credits"))
    debits_total = _money(account.get("stated_total_debits"))
    meta = AccountMeta(_money(account.get("beginning_balance")), _money(account.get("ending_balance")), period_start,
                       period_end, currency, last4, account.get("bank") or None, (),
                       abs(credits_total) if credits_total is not None else None,
                       abs(debits_total) if debits_total is not None else None,
                       _count(account.get("stated_credit_count")), _count(account.get("stated_debit_count")))
    populated = any(getattr(meta, f) is not None for f in ("beginning_balance", "ending_balance", "period_start", "currency",
                                                           "stated_total_credits", "stated_total_debits"))
    return replace(meta, sources=("meta:stage_b",) if populated else ())


def merge_pages(pages: list[PageProposal]) -> tuple[list[CandidateRow], AccountMeta, dict]:
    rows: list[CandidateRow] = []
    meta = EMPTY_META
    roles: Counter = Counter()
    currencies: list[str] = []
    last4s: list[str] = []
    drops = Counter()
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
            page_rows, page_drops = rows_from_proposal(page.proposal, page=page.page, year_hint=year_hint)
            drops.update(page_drops)
            rows.extend(page_rows)
    stats = {
        "pages_by_role": dict(sorted(roles.items())),
        "invalid_pages": roles.get("invalid", 0),
        "currency_conflict": len(currencies) > 1,
        "account_last4_count": len(last4s),
        "account_last4_set_sha256": sha256_bytes(canonical_json(sorted(last4s)).encode("utf-8")) if last4s else None,
        "rows_dropped_nonpositive": drops.get("nonpositive", 0),
        "continuation_rows_merged": drops.get("continuation_merged", 0),
        "continuation_rows_with_amount": drops.get("continuation_with_amount", 0),
    }
    return rows, meta, stats

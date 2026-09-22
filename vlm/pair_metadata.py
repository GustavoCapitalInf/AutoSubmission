"""Field-aware merge of reviewed page metadata, without arithmetic or inference.

Policies:
* Every non-null account-field occurrence is retained verbatim in provenance.
  Bank/name/average-label restatements compare case, whitespace and punctuation
  insensitively; their first printed representation is retained. Currency uses
  case/outer-whitespace comparison only. Missing currency is not a conflict.
* Account IDs ignore formatting punctuation/case. Explicit masking characters
  and repeated Xs hide variable-width spans; bare four-character IDs are suffix
  evidence. Every visible character constrains compatibility. Two complete IDs
  must match in full. The most informative compatible account-field spelling
  is retained; no complete number is manufactured from masked observations.
* The earliest opening and latest closing are statement anchors. A differing
  page balance is a continuation only on valid transaction-bearing pages, with
  a matching final reviewed running balance or adjacent closing/opening pair.
  Summary, empty, failed and nonadjacent pages cannot supply that proof.
* Period dates retain the existing exact-restatement/ISO/order policy. Totals,
  counts, days, fees, interest, NSF counts and printed averages are period-wide
  figures: repeated values must agree; never sum them or choose a maximum.
  Unknown future fields also require exact agreement.
* Daily snapshots retain the existing date validation and final-observation
  behavior; contradictory values still refuse the document. They are not
  inferred from transaction rows.

The optional occurrence sink carries only code, page, field and source. No
source value is placed in an error or occurrence. Inputs are never mutated.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re


_IDENTITY_FIELDS = {"bank", "account_name", "bank_reported_average_label"}
_NUMBER_FIELDS = {"account_number", "account_number_last4"}
_BALANCE_FIELDS = {"beginning_balance", "ending_balance"}


def _text_identity(value) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _account_pattern(value) -> str:
    raw = re.sub(r"x{2,}", "*", str(value).casefold())
    raw = "".join("*" if character in "*•●" else character
                  for character in raw if character.isalnum() or character in "*•●")
    raw = re.sub(r"\*+", "*", raw)
    return "*" + raw if len(raw) == 4 and "*" not in raw else raw


def _compatible(left: str, right: str) -> bool:
    """Whether two anchored literal/masked patterns have a possible common ID.

    A small product automaton preserves all visible prefix, interior and suffix
    characters, including conflicts between masked observations. A mask never
    permits two unequal complete identifiers to pass a suffix-only comparison.
    """
    pending = [(0, 0)]
    seen = set()
    while pending:
        i, j = pending.pop()
        if (i, j) in seen:
            continue
        seen.add((i, j))
        if i == len(left) and j == len(right):
            return True
        a = left[i] if i < len(left) else None
        b = right[j] if j < len(right) else None
        if a == "*":
            pending.append((i + 1, j))
        if b == "*":
            pending.append((i, j + 1))
        if a is not None and b is not None and (a == b or a == "*" or b == "*"):
            pending.append((i + (a != "*"), j + (b != "*")))
    return False


def _information(pattern: str) -> tuple[bool, int]:
    return "*" not in pattern, len(pattern.replace("*", ""))


def _equal(left, right) -> bool:
    numeric = (int, float, Decimal)
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, numeric) and isinstance(right, numeric):
        try:
            a, b = Decimal(str(left)), Decimal(str(right))
            return a.is_finite() and b.is_finite() and a == b
        except InvalidOperation:
            return False
    return left == right


def _page(index, merged):
    return merged.page if isinstance(merged.page, int) and merged.page > 0 else index + 1


def _transaction_page(merged) -> bool:
    return not merged.errors and merged.page_role == "statement_page" and bool(merged.rows)


def _adjacent(merges, left, right) -> bool:
    return (0 <= left < right < len(merges) and right == left + 1
            and _page(left, merges[left]) + 1 == _page(right, merges[right])
            and _transaction_page(merges[left]) and _transaction_page(merges[right]))


def _continuation(merges, index: int, field: str, value) -> bool:
    current = merges[index]
    if not _transaction_page(current):
        return False
    if field == "beginning_balance":
        if not _adjacent(merges, index - 1, index):
            return False
        previous = merges[index - 1]
        boundary = previous.rows[-1].balance
        endpoint = previous.account.get("ending_balance")
        return ((boundary is not None and _equal(value, boundary))
                or (endpoint is not None and _equal(value, endpoint)))
    boundary = current.rows[-1].balance
    if boundary is not None and _equal(value, boundary):
        return True
    return (_adjacent(merges, index, index + 1)
            and merges[index + 1].account.get("beginning_balance") is not None
            and _equal(value, merges[index + 1].account["beginning_balance"]))


def merge_metadata(merges, *, occurrences: list[dict] | None = None) -> tuple[dict, list[dict], list[str], list[dict]]:
    """Merge page observations; disagreements remain held with field provenance."""
    merges = list(merges)
    account, daily, reasons, provenance = {}, {}, [], []
    identities = []
    source_pages = {}
    balances = {field: [] for field in _BALANCE_FIELDS}

    def fail(code, page, field):
        reasons.append(code)
        if occurrences is not None:
            occurrences.append({"code": code, "page": page, "field": field, "source": "metadata"})

    def identity(value, page, field):
        pattern = _account_pattern(value)
        if not pattern:
            return False
        compatible = all(_compatible(pattern, previous) for previous in identities)
        if not compatible:
            fail("proposal_invalid", page, field)
        if pattern not in identities:
            identities.append(pattern)
        return compatible

    for index, merged in enumerate(merges):
        page = _page(index, merged)
        for key, value in merged.account.items():
            if value is None:
                continue
            provenance.append({"field": key, "page": page, "source": "reviewer", "value": value})
            if key in _BALANCE_FIELDS:
                balances[key].append((index, page, value))
                continue
            if key in _NUMBER_FIELDS:
                compatible = identity(value, page, key)
                pattern = _account_pattern(value)
                if pattern and (key not in account or
                                (compatible and _information(pattern) > _information(_account_pattern(account[key])))):
                    account[key] = value
                    source_pages[key] = page
                continue
            if key in _IDENTITY_FIELDS:
                if not _text_identity(value):
                    continue
                equal = key not in account or _text_identity(value) == _text_identity(account[key])
            elif key == "currency":
                if not str(value).strip():
                    continue
                equal = key not in account or str(value).strip().casefold() == str(account[key]).strip().casefold()
            else:
                equal = key not in account or _equal(value, account[key])
            if not equal:
                fail("currency_conflict" if key == "currency" else
                     "period_mismatch" if key in ("period_start", "period_end") else "anchor_disagreement", page, key)
            elif key not in account:
                account[key] = value
                source_pages[key] = page
        for value in merged.account_numbers_seen:
            if value:
                identity(value, page, "account_numbers_seen")
        for item in merged.daily_balances:
            when, balance = item.get("date"), item.get("balance")
            try:
                date.fromisoformat(when)
            except (TypeError, ValueError):
                fail("date_unparsed", page, "daily_balances")
                continue
            if when in daily and not _equal(daily[when], balance):
                fail("anchor_disagreement", page, "daily_balances")
            daily[when] = balance

    for field in ("beginning_balance", "ending_balance"):
        candidates = balances[field]
        if not candidates:
            continue
        chosen = candidates[0] if field == "beginning_balance" else candidates[-1]
        account[field] = chosen[2]
        for index, page, value in candidates:
            if not _equal(value, chosen[2]) and not _continuation(merges, index, field, value):
                fail("anchor_disagreement", page, field)

    for field in ("period_start", "period_end"):
        try:
            date.fromisoformat(account.get(field))
        except (TypeError, ValueError):
            fail("period_mismatch", source_pages.get(field), field)
    if account.get("period_start") and account.get("period_end"):
        if account["period_start"] > account["period_end"]:
            fail("period_mismatch", source_pages.get("period_end"), "period_end")
    if not account.get("currency"):
        fail("currency_missing", None, "currency")
    return account, [{"date": when, "balance": value} for when, value in sorted(daily.items())], reasons, provenance

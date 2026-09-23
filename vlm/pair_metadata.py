"""Field-aware merge of reviewed page metadata with explicit scope proofs.

Policies:
* Every non-null account-field occurrence is retained verbatim in provenance.
  Bank and account names are descriptive, not identity (the account number is):
  the first printed value stands and variants stay in provenance, never held.
  Average-label restatements compare case, whitespace and punctuation
  insensitively (a different basis still conflicts); their first printed
  representation is retained. Currency uses
  case/outer-whitespace comparison only. Missing currency is not a conflict.
* Account IDs ignore formatting punctuation/case, and zeros padding a complete
  number of eight or more digits. Explicit masking characters
  and repeated Xs hide variable-width spans; bare four-character IDs are suffix
  evidence. Every visible character constrains compatibility. Two complete IDs
  must match in full. The most informative compatible account-field spelling
  is retained; no complete number is manufactured from masked observations.
* The earliest opening and latest closing are statement anchors. A differing
  page balance is a continuation only on valid transaction-bearing pages, with
  a matching final reviewed running balance or adjacent closing/opening pair.
  Summary, empty, failed and nonadjacent pages cannot supply that proof.
  Complete page-summary boxes additionally require an arithmetic segment proof;
  a matching transaction balance cannot excuse a contradictory printed opening.
* Period dates retain the existing exact-restatement/ISO/order policy. Totals,
  counts, days, fees, interest, NSF counts and printed averages are period-wide
  figures: repeated values must agree; never sum them or choose a maximum.
  Unknown future fields also require exact agreement.
  The sole exception is a proven chain of adjacent printed page summaries:
  select its first opening and final printed closing, and sum each printed
  credit/debit total/count separately. Segment boundaries remain attributed to
  their printed page fields. Callers must independently reconcile every segment
  and the whole ledger; scope proof alone cannot admit a document.
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

from vlm.review import picture_page
from vlm.segments import SCOPED_FIELDS, SegmentPlan, detect_page_segments


_IDENTITY_FIELDS = {"bank", "account_name", "bank_reported_average_label"}
# Printed figures no admission check depends on (the gate proves the ledger with the opening and closing
# balances, totals, counts and running balances). Two pages that disagree about one (a fee-analysis page's
# service charge against the summary's) leave it unknown, recorded as disputed, and hold nothing.
_AUXILIARY_FIGURES = {"stated_service_charge", "stated_interest_paid", "stated_nsf_count", "days_in_period",
                      "bank_reported_average_balance"}
_NAME_FIELDS = {"bank", "account_name"}
_NUMBER_FIELDS = {"account_number", "account_number_last4"}
_BALANCE_FIELDS = {"beginning_balance", "ending_balance"}


def _text_identity(value) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _account_pattern(value) -> str:
    raw = re.sub(r"x{2,}", "*", str(value).casefold())
    raw = "".join("*" if character in "*•●" else character
                  for character in raw if character.isalnum() or character in "*•●")
    raw = re.sub(r"\*+", "*", raw)
    # A complete number printed with zeros in front ("000000012345678" on the first page, "12345678" on the
    # activity pages) is the same number: the zeros pad a field.
    if raw.isdigit() and len(raw) >= 8:
        raw = raw.lstrip("0") or "0"
    return "*" + raw if len(raw) == 4 and "*" not in raw else raw


def _alnum(value) -> str:
    return re.sub(r"[^0-9A-Z]", "", str(value).upper())


def _transaction_texts(merged) -> list[str]:
    """Every description the page's review saw, in any row state, as upper-case letters and digits."""
    texts = [row.description for row in merged.rows]
    for item in merged.evidence:
        if not isinstance(item, dict):
            continue
        for key in ("row", "original", "corrected"):
            record = item.get(key)
            if isinstance(record, dict) and record.get("description"):
                texts.append(record["description"])
        if item.get("observed_description"):
            texts.append(item["observed_description"])
    return [_alnum(text) for text in texts if text]


def _printed_in_a_transaction(value, texts: list[str]) -> bool:
    """A number printed inside a transaction row is the other side of a transfer or a reference, not a
    claim about which account this statement is. Six characters is the floor: a shorter fragment could
    match an amount or a date."""
    key = _alnum(value)
    return len(key) >= 6 and any(key in text for text in texts)


def _dated_entries(merged) -> list[dict]:
    entries = []
    for item in merged.daily_balances:
        try:
            date.fromisoformat(item.get("date"))
        except (TypeError, ValueError, AttributeError):
            continue
        entries.append(item)
    return entries


def _daily_dates(merged) -> list[str]:
    return [item["date"] for item in _dated_entries(merged)]


# A sibling account's own figures and identity, which a reviewer reports as the page's when it reads that account's
# summary first (dormant_siblings).
_SIBLING_FIELDS = ("beginning_balance", "ending_balance", "stated_total_credits", "stated_total_debits",
                   "stated_credit_count", "stated_debit_count", "account_number", "account_number_last4",
                   "account_name", "bank_reported_average_balance", "bank_reported_average_label")
_MOVEMENT_FIELDS = ("stated_total_credits", "stated_total_debits", "stated_credit_count", "stated_debit_count")


def dormant_siblings(merges) -> dict[int, dict]:
    """Pages whose reviewer reported a sibling account that did not move, not the statement's: that account's
    beginning and ending balance are printed and equal, it reports no money in or out (totals and counts absent or
    zero), the statement has transactions, and another page reports the account they move, at another balance. A
    credit union prints its membership savings share first ("Savings $25.00 ... $25.00"), then the checking
    share that carries every transaction; a reviewer reading a page's first summary reports the savings.

    Returns {merge index: {field: value}}: the sibling's fields, set aside rather than merged as the statement's.
    Nothing is set aside when no page reports another balance: a statement whose own balance did not move keeps its
    figures. The arithmetic still decides: the moving account must reconcile to its own printed figures."""
    if not any(merged.rows for merged in merges if not picture_page(merged)):
        return {}

    def still(account) -> Decimal | None:
        begin, end = account.get("beginning_balance"), account.get("ending_balance")
        if begin is None or end is None or not _equal(begin, end):
            return None
        for key in _MOVEMENT_FIELDS:
            value = account.get(key)
            if value is not None and not _equal(value, 0):
                return None
        try:
            return abs(Decimal(str(begin))).quantize(Decimal("0.01"))
        except (ArithmeticError, TypeError, ValueError):
            return None

    stills = {index: still(merged.account) for index, merged in enumerate(merges) if not picture_page(merged)}
    moving, printed = set(), set()
    for index, merged in enumerate(merges):
        if picture_page(merged):
            continue
        for row in merged.rows:
            if row.balance is not None:
                printed.add(abs(Decimal(str(row.balance))).quantize(Decimal("0.01")))
        if stills.get(index) is not None:
            continue
        for key in _BALANCE_FIELDS:
            value = merged.account.get(key)
            try:
                if value is not None:
                    moving.add(abs(Decimal(str(value))).quantize(Decimal("0.01")))
            except (ArithmeticError, TypeError, ValueError):
                continue
    # A still figure the moving account itself reaches (a running balance on a row) is that account's own summary
    # contradicting its opening, not a sibling: it stays a disagreement.
    return {index: {key: merges[index].account[key] for key in _SIBLING_FIELDS
                    if merges[index].account.get(key) is not None}
            for index, value in stills.items()
            if value is not None and moving and value not in moving and value not in printed}


def _newest_first(merges) -> bool | None:
    """Whether the statement lists its rows newest first (True) or oldest first (False): every page whose row
    dates run one way agrees on that way. None when no page shows an order, or pages disagree."""
    orders = set()
    for merged in merges:
        dates = [row.date for row in merged.rows if row.date]
        if len(set(dates)) < 2:
            continue
        if dates == sorted(dates):
            orders.add(False)
        elif dates == sorted(dates, reverse=True):
            orders.add(True)
    return orders.pop() if len(orders) == 1 else None


def _day_closes(merged, newest_first: bool | None = None) -> tuple[list[dict], int]:
    """A page's daily balances with each day once. A page listing one date several times, every such value a
    running balance printed on one of its own rows (or the page's own opening or closing balance), transcribed its
    running balances (a statement printing a balance on every row): the day's close is its last value in listing
    order, or its first when the page lists newest first. A page listing a single date takes the statement's listing order (newest_first) and keeps its
    entries when that is unknown. Anything else is returned as it is (repeated dates with other values stay a
    disagreement). Returns (entries, how many running values were folded into their day's close)."""
    items = list(merged.daily_balances)
    dated = _dated_entries(merged)
    dates = [item["date"] for item in dated]
    repeated = {when for when in dates if dates.count(when) > 1}
    if not repeated or len(dated) != len(items):
        return items, 0
    cent = Decimal("0.01")
    # The page's printed opening (a "beginning balance" line on the first date) and closing count as its figures.
    figures = [row.balance for row in merged.rows] + [merged.account.get(key)
                                                      for key in ("beginning_balance", "ending_balance")]
    try:
        printed = {abs(Decimal(str(value))).quantize(cent) for value in figures if value is not None}
        values = {abs(Decimal(str(item["balance"]))).quantize(cent) for item in dated if item["date"] in repeated}
    except (ArithmeticError, TypeError, ValueError):
        return items, 0
    if not values <= printed:
        return items, 0
    ascending, descending = dates == sorted(dates), dates == sorted(dates, reverse=True)
    if ascending and descending:
        ascending, descending = newest_first is False, newest_first is True
    if ascending:
        ordered = dated
    elif descending:
        ordered = list(reversed(dated))
    else:
        return items, 0
    closes: dict[str, dict] = {}
    for item in ordered:
        closes[item["date"]] = item
    return sorted(closes.values(), key=lambda item: item["date"]), len(items) - len(closes)


def _carried_forward_date(merges, index: int) -> str | None:
    """The date a page carries forward: its FIRST daily entry repeats exactly (same date, same balance) the
    LAST daily entry of the previous adjacent clean statement page. That is the printed BALANCE FORWARD,
    the balance where the previous page stopped, not a closing balance for the day."""
    if index == 0 or not _adjacent(merges, index - 1, index):
        return None
    before, after = _dated_entries(merges[index - 1]), _dated_entries(merges[index])
    if (before and after and before[-1]["date"] == after[0]["date"]
            and _equal(before[-1].get("balance"), after[0].get("balance"))):
        return after[0]["date"]
    return None


def _page_break_checkpoint(merges, earlier: int, later: int, when: str) -> bool:
    """A date that ends one clean statement page and begins the next adjacent one straddles the page
    break: the earlier figure is where the page ended, part-way through the day, and the later one
    carries the day on to its close. That is a checkpoint, not a contradiction. "Ends" means both the
    last entry in printed order and the latest date; "begins" means both the first entry and the earliest
    date. A conflicting figure printed anywhere else on the page is still a contradiction."""
    if not _adjacent(merges, earlier, later):
        return False
    before, after = _daily_dates(merges[earlier]), _daily_dates(merges[later])
    return (bool(before) and bool(after)
            and before[-1] == when and max(before) == when
            and after[0] == when and min(after) == when)


def page_break_figures(merges, rows) -> set[str]:
    """Dates whose only printed daily figure is where a page ended part-way through the day.

    The checkpoint rule above accepts that figure when the next page prints the day's close. When no later
    page prints a figure for the day (no daily table, or one whose dates were not read), the earlier figure
    would stand as the day's closing balance although the day's later transactions follow on the next page.
    That day has no printed close; the ledger reconstructs it. Narrow on purpose: the figure is the last
    entry and the latest date on its page; the page's own ledger breaks inside that day (its last row carries
    the date and prints a running balance equal to the figure; without one, on a sectioned statement, the
    table figure is the only day-attribution evidence and must stand); the next adjacent
    clean page's first ledger row carries the same date; and no later page prints a figure for it. A
    whole-period table printed before another section fails the break test, so its true close stands.
    `rows` are the resolved ledger rows in printed order."""
    first_row, last_row = {}, {}
    for row in rows:
        first_row.setdefault(row.page, row)
        last_row[row.page] = row
    dropped = set()
    for index in range(len(merges) - 1):
        if not _adjacent(merges, index, index + 1):
            continue
        entries = _dated_entries(merges[index])
        if not entries or entries[-1]["date"] != max(item["date"] for item in entries):
            continue
        when, figure = entries[-1]["date"], entries[-1].get("balance")
        ending, opening = last_row.get(_page(index, merges[index])), first_row.get(_page(index + 1, merges[index + 1]))
        if (ending is not None and ending.date == when
                and ending.balance is not None and _equal(ending.balance, figure)
                and opening is not None and opening.date == when
                and not any(when in _daily_dates(later) for later in merges[index + 1:])):
            dropped.add(when)
    return dropped


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
    # A cheque picture page is never continuation or page-break evidence, whatever it was labelled.
    return (not merged.errors and merged.page_role == "statement_page" and bool(merged.rows)
            and not picture_page(merged))


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


def merge_metadata(merges, *, occurrences: list[dict] | None = None,
                   segment_plan: SegmentPlan | None = None,
                   opening_observations: dict | None = None) -> tuple[dict, list[dict], list[str], list[dict]]:
    """Merge page observations; disagreements remain held with field provenance."""
    merges = list(merges)
    segment_plan = (detect_page_segments(merges, opening_observations=opening_observations)
                    if segment_plan is None else segment_plan)
    segment_pages = {segment.page for segment in segment_plan.segments} if segment_plan.proven else set()
    account, daily, reasons, provenance = {}, {}, [], []
    disputed: set[str] = set()
    daily_source: dict[str, int] = {}
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

    segment_failures = {(item["page"], item["field"]) for item in segment_plan.occurrences}
    for item in segment_plan.occurrences:
        fail(item["code"], item["page"], item["field"])
    newest_first = _newest_first(merges)
    aside = dormant_siblings(merges)
    sibling_numbers = [_account_pattern(value) for fields in aside.values() for key, value in fields.items()
                       if key in _NUMBER_FIELDS and _account_pattern(value)]

    for index, merged in enumerate(merges):
        page = _page(index, merged)
        if picture_page(merged):
            # Pictures of cheques and deposit slips carry OTHER parties' names, banks and accounts. They are not
            # statement metadata: keep the raw observations as provenance and compare nothing.
            for key, value in merged.account.items():
                if value is not None:
                    provenance.append({"field": key, "page": page, "source": "reviewer", "value": value})
            continue
        for key, value in merged.account.items():
            if value is None:
                continue
            provenance.append({"field": key, "page": page, "source": "reviewer", "value": value})
            if key in aside.get(index, ()):
                continue  # a sibling account that did not move (dormant_siblings), never the statement's
            if page in segment_pages and key in SCOPED_FIELDS:
                continue
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
            if key in _NAME_FIELDS:
                # A bank or account name is descriptive, not identity (the account number is): a statement prints
                # its brand on one page and its legal name on another, and a reviewer reads a logo. The first
                # printed value stands; every variant stays in the field evidence (provenance above).
                if _text_identity(value) and key not in account:
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
            if not equal and key in _AUXILIARY_FIGURES:
                disputed.add(key)
            elif not equal:
                fail("currency_conflict" if key == "currency" else
                     "period_mismatch" if key in ("period_start", "period_end") else "anchor_disagreement", page, key)
            elif key not in account:
                account[key] = value
                source_pages[key] = page
        # The reviewer is asked to list EVERY account number visible on the page, which includes the other
        # side of a transfer and reference numbers inside transaction rows. Only numbers that are not
        # printed inside any transaction on the page are claims about which account this statement is;
        # registering the others made a later page's correct own-account number conflict with them.
        printed = _transaction_texts(merged)
        for value in merged.account_numbers_seen:
            if (value and not _printed_in_a_transaction(value, printed)
                    and not any(_compatible(_account_pattern(value), sibling) for sibling in sibling_numbers)):
                identity(value, page, "account_numbers_seen")
        carried = _carried_forward_date(merges, index)
        carry_open = carried is not None
        previous_date = None
        entries, folded = _day_closes(merged, newest_first)
        if folded:
            provenance.append({"field": "daily_balances", "page": page, "source": "running_balances_day_close",
                               "value": folded})
        for item in entries:
            when, balance = item.get("date"), item.get("balance")
            try:
                date.fromisoformat(when)
            except (TypeError, ValueError):
                fail("date_unparsed", page, "daily_balances")
                continue
            if when in daily and not _equal(daily[when], balance):
                # After a carried-forward opening, the SAME day printed again immediately below it is that
                # day's close. It may close only once.
                continuation = (carry_open and when == carried and previous_date == when
                                and daily_source.get(when) == index)
                if continuation:
                    carry_open = False
                elif not _page_break_checkpoint(merges, daily_source[when], index, when):
                    fail("anchor_disagreement", page, "daily_balances")
            daily[when] = balance
            daily_source[when] = index
            previous_date = when

    for index, fields in sorted(aside.items()):
        provenance.append({"field": "dormant_sibling_account", "page": _page(index, merges[index]),
                           "source": "dormant_sibling_account", "value": fields})

    for field in ("beginning_balance", "ending_balance"):
        candidates = balances[field]
        if not candidates:
            continue
        chosen = candidates[0] if field == "beginning_balance" else candidates[-1]
        account[field] = chosen[2]
        for index, page, value in candidates:
            if (not _equal(value, chosen[2])
                    and (page in segment_plan.strict_balance_pages or not _continuation(merges, index, field, value))
                    and (page, field) not in segment_failures):
                fail("anchor_disagreement", page, field)

    if segment_plan.proven:
        account.update(segment_plan.document_fields)

    if "bank_reported_average_balance" in disputed:
        # The label names the disputed figure; without the figure it describes nothing.
        account.pop("bank_reported_average_label", None)
    for field in sorted(disputed):
        account.pop(field, None)
        provenance.append({"field": field, "page": None, "source": "disputed_between_pages", "value": None})

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

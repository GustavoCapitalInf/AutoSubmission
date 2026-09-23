"""The deterministic gate. The model proposes; `analysis.reconcile.reconcile` (the reader's own
arithmetic) decides, with anchor, date, duplicate and direction checks on top. Never partial admission.

Review closures (CEILING-HARNESS-REVIEW-X):
* MAJOR-1  at most ONE anchor may be derived from the rows; with neither balance printed the gate refuses
           (`anchors_underdetermined`), because a proposal would then be checked only against itself.
* GATE-3   chain-derived directions are accepted only when BOTH anchors are printed (the sum check is then
           independent of the chain); otherwise `chain_direction_unanchored`.
* MAJOR-2  a repeated (date, description, amount, direction) is a `duplicate_row` unless printed balances
           distinguish the two rows, or the bank's printed per-direction count vouches for the pair.
* MAJOR-4  the bank's printed totals and counts reach `reconcile`; a failing summary identity is
           `summary_mismatch`, a failing count is `count_mismatch`.
* MAJOR-2 amendment (gate 10) a repeat is also distinguished when the layout model read the two rows as
           separate printed lines: different pages, or the SAME read of one page at different grid
           positions. Rows from different reads of one page (full page versus crop, or two crops) may
           overlap, and reviewer additions carry no position, so those stay unverifiable. Where both rows
           still print a balance after same-day runs are collapsed, balances decide, as before. RR-2 is
           unchanged: a matching count never distinguishes a repeat, and the arithmetic still refuses a
           row that is not on the page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from analysis.reconcile import _TOL as RECONCILE_TOLERANCE, reconcile
from analysis.schema import Statement, Transaction
from vlm.assemble import CandidateRow
from vlm.metadata import AccountMeta
from vlm.textparse import normalise_description

# v11: a labelled column that prints every value with a minus is signed by its style (minus_styled).
# v12: two lines of one proposer text block are separate printed lines, like two rows of one table; an anchor
#      derived from the balance printed at one end stands when the printed totals and counts prove the ledger
#      complete.
# v13: the sum must hold to the cent: a one-cent difference is a missing or misread cent, not float noise.
GATE_VERSION = 13
REASONS = ("no_rows", "proposal_invalid", "anchors_underdetermined", "anchor_derived", "missing_beginning_balance",
           "missing_ending_balance", "direction_unknown", "chain_direction_unanchored", "date_unparsed",
           "duplicate_row", "sum_mismatch", "continuity_break",
           "summary_mismatch", "count_mismatch", "coverage_mismatch", "currency_conflict", "currency_missing",
           "anchor_disagreement", "period_mismatch", "date_order_chained", "page_unresolved")
PERIOD_GRACE_DAYS = 5


@dataclass(frozen=True)
class GateVerdict:
    admitted: bool
    reasons: tuple[str, ...]
    row_count: int
    admitted_rows: tuple[CandidateRow, ...]
    computed_ending: Decimal | None
    continuity_breaks: int
    chain_derived_directions: int
    checks: dict
    anchored: str = "none"   # "both" | "one" | "none" — how many anchors were PRINTED
    occurrences: tuple[dict, ...] = ()


def resolve_directions(rows: list[CandidateRow], beginning: Decimal | None) -> tuple[list[CandidateRow], int]:
    resolved: list[CandidateRow] = []
    previous = beginning
    flagged = 0
    for row in rows:
        current = row
        if row.direction == "unknown" and previous is not None and row.balance is not None:
            delta = row.balance - previous
            if abs(delta) == row.amount and row.amount > 0:
                current = replace(row, direction="credit" if delta > 0 else "debit", direction_source="chain")
                flagged += 1
        resolved.append(current)
        if current.balance is not None:
            previous = current.balance
    return resolved, flagged


def minus_styled(rows) -> frozenset:
    """Directions whose labelled column prints every value with a minus or brackets: the bank's print style
    ("-$30.00" in a debits column), not a reversal. It takes at least two printed values, every one negative;
    a negative among positive values of its column stays a reversal (the money moved the other way). Read
    wrongly either way, the balance and sum checks refuse the statement."""
    styled = set()
    for direction in ("credit", "debit"):
        printed = [row.printed_amount for row in rows
                   if row.direction == direction and getattr(row, "printed_amount", None) is not None]
        if len(printed) >= 2 and all(value < 0 for value in printed):
            styled.add(direction)
    return frozenset(styled)


def signed_amount(row: CandidateRow, styled: frozenset = frozenset()) -> Decimal:
    """The row's effect on the balance: its printed amount in a labelled column (negative there is a reversal,
    unless the column's print style is a minus, minus_styled), else its magnitude, signed by direction."""
    printed = getattr(row, "printed_amount", None)
    if printed is not None and row.direction in styled:
        printed = abs(printed)
    amount = row.amount if printed is None else printed
    return amount if row.direction == "credit" else -amount


def _signed(row: CandidateRow, styled: frozenset = frozenset()) -> float:
    return float(signed_amount(row, styled))


def _proven_complete(statement: Statement, meta: AccountMeta, result) -> bool:
    """Whether the statement's printed totals AND counts prove the ledger complete: the credits and the
    debits read sum to the printed totals to the cent, and their numbers are the printed counts. A read cut
    off at one end cannot pass that, so an anchor derived from the balance printed at that end stands
    (a statement that prints its opening balance and totals but no closing line: ScotiaBank)."""
    cent = Decimal("0.01")
    if meta.stated_total_credits is None or meta.stated_total_debits is None:
        return False
    amounts = [Decimal(str(transaction.amount)) for transaction in statement.transactions]
    credits = sum((amount for amount in amounts if amount > 0), Decimal("0")).quantize(cent)
    debits = sum((-amount for amount in amounts if amount < 0), Decimal("0")).quantize(cent)
    return (credits == Decimal(str(meta.stated_total_credits)).quantize(cent)
            and debits == Decimal(str(meta.stated_total_debits)).quantize(cent)
            and result.stated_credit_count_matches is True and result.stated_debit_count_matches is True)


def _f(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def statement_from(rows: list[CandidateRow], meta: AccountMeta) -> Statement:
    styled = minus_styled(rows)
    return Statement(
        bank=meta.bank, account_name=meta.account_name,
        account_number=meta.account_number or meta.account_last4,
        period_start=meta.period_start, period_end=meta.period_end,
        beginning_balance=_f(meta.beginning_balance), ending_balance=_f(meta.ending_balance),
        currency=meta.currency or "USD",
        stated_total_credits=_f(meta.stated_total_credits), stated_total_debits=_f(meta.stated_total_debits),
        stated_credit_count=meta.stated_credit_count, stated_debit_count=meta.stated_debit_count,
        days_in_period=meta.days_in_period,
        stated_service_charge=_f(meta.stated_service_charge),
        stated_interest_paid=_f(meta.stated_interest_paid), stated_nsf_count=meta.stated_nsf_count,
        bank_reported_average_balance=_f(meta.bank_reported_average_balance),
        bank_reported_average_label=meta.bank_reported_average_label,
        stated_daily_balances=[{'date': when, 'balance': float(balance)}
                               for when, balance in (meta.stated_daily_balances or ())],
        transactions=[Transaction(date=row.date or "", description=row.description, amount=_signed(row, styled),
                                  direction=row.direction if row.direction != "unknown" else "debit",
                                  running_balance=_f(row.balance))
                      for row in rows],
    )


def orient(rows: list[CandidateRow]) -> tuple[list[CandidateRow], bool]:
    """Statements that list newest first are reversed into chronological order (a deterministic rule keyed
    on the printed dates: more descending than ascending steps). Returns (rows, reversed)."""
    dates = [row.date for row in rows if row.date]
    down = sum(1 for a, b in zip(dates, dates[1:]) if b < a)
    up = sum(1 for a, b in zip(dates, dates[1:]) if b > a)
    if down > up:
        return list(reversed(rows)), True
    return list(rows), False


def collapse_daily_balances(rows: list[CandidateRow]) -> tuple[list[CandidateRow], int]:
    """Banks that print one end-of-day balance repeat it on every row of that day. Keep it on the LAST
    row of each same-date run of identical balances (the reader's continuity check accumulates the
    day's amounts up to a printed balance). Returns (rows, collapsed_count)."""
    out = list(rows)
    collapsed = 0
    index = 0
    while index < len(out):
        run_end = index
        while (run_end + 1 < len(out) and out[run_end + 1].date == out[index].date
               and out[run_end + 1].balance is not None and out[run_end + 1].balance == out[index].balance):
            run_end += 1
        if run_end > index and out[index].balance is not None:
            for position in range(index, run_end):
                out[position] = replace(out[position], balance=None)
                collapsed += 1
        index = run_end + 1
    return out, collapsed


# A row the layout model read at a grid position: optional read prefix (g0/ for a recovery original,
# g<gen>c<crop>/ for a crop), then block, table and row. Reviewer additions ("added<n>") and anything
# else carry no position.
# A proposer row's place in its read: a table row (b3t0r12) or a line of a text block (b6l43).
_LAYOUT_LOCATOR = re.compile(r"^(?P<read>(?:g\d+(?:c\d+)?/)?)b\d+(?:t\d+r\d+|l\d+)$")


def _separate_printed_lines(first: CandidateRow, second: CandidateRow) -> bool:
    """True when the layout read the two rows as different printed lines of the statement."""
    one = _LAYOUT_LOCATOR.match(first.locator or "")
    two = _LAYOUT_LOCATOR.match(second.locator or "")
    if one is None or two is None or first.locator == second.locator:
        return False
    if first.page != second.page:
        return True   # one printed line cannot sit on two pages
    # Same page: only the same read is known not to overlap itself.
    return one.group("read") == two.group("read")


def _duplicates(rows: list[CandidateRow], *, occurrences: list[dict] | None = None,
                positional: list[int] | None = None) -> tuple[int, int]:
    """(distinguished_repeats, unverifiable_repeats): a repeat of (date, description, amount, direction)
    is distinguished when both rows print balances and they differ, or, when at least one carries no
    balance (including after same-day balance runs are collapsed), when the layout read them as
    separate printed lines."""
    seen: dict[tuple, list[CandidateRow]] = {}
    distinguished = unverifiable = 0
    for row in rows:
        key = (row.date, normalise_description(row.description), row.amount, row.direction)
        twins = seen.setdefault(key, [])
        repeated = False
        for twin in twins:
            if twin.balance is not None and row.balance is not None:
                separate = twin.balance != row.balance
            else:
                separate = _separate_printed_lines(twin, row)
                if separate and positional is not None:
                    positional[0] += 1
            if separate:
                distinguished += 1
            else:
                unverifiable += 1
                repeated = True
        if repeated and occurrences is not None:
            # Count a later offending row once, even when it matches several
            # predecessors. The historical pair count above is unchanged.
            occurrences.append({"code": "duplicate_row", "page": row.page, "source": "gate"})
        twins.append(row)
    return distinguished, unverifiable


def _continuity_failure_rows(rows: list[CandidateRow], statement: Statement) -> list[CandidateRow]:
    """Locate uncapped continuity failures using the reader's exact rounding.

    This replay supplies provenance only. Admission and the authoritative count
    still come from reconcile; its human-readable issue list stops at five rows.
    """
    failed = []
    previous = statement.beginning_balance
    pending = 0.0
    for row, transaction in zip(rows, statement.transactions):
        pending = round(pending + transaction.amount, 2)
        if transaction.running_balance is not None:
            if previous is not None:
                expected = round(previous + pending, 2)
                if abs(expected - round(transaction.running_balance, 2)) > RECONCILE_TOLERANCE:
                    failed.append(row)
            previous = transaction.running_balance
            pending = 0.0
    return failed


def gate(rows: list[CandidateRow], meta: AccountMeta, *, tolerance: Decimal = Decimal("0.005"),
         complete_document: bool = True) -> GateVerdict:
    """``tolerance`` absorbs the reader's float arithmetic only: a sum one cent off is a missing or misread cent
    (a $0.01 credit printed ".01"), never noise (gate v13)."""
    reasons: list[str] = []
    occurrences: list[dict] = []

    def record(code: str, *, row: CandidateRow | None = None, field: str | None = None) -> None:
        reasons.append(code)
        item = {"code": code, "page": row.page if row is not None else None, "source": "gate"}
        if field is not None:
            item["field"] = field
        occurrences.append(item)

    checks: dict = {"gate_version": GATE_VERSION, "derived": []}
    if not rows and complete_document:
        record("no_rows")
        return GateVerdict(False, ("no_rows",), 0, (), None, 0, 0, checks, occurrences=tuple(occurrences))
    for row in rows:
        if row.amount <= 0:
            record("proposal_invalid", row=row, field="amount")
    for row in rows:
        if getattr(row, "printed_amount", None) is not None and abs(row.printed_amount) != row.amount:
            record("proposal_invalid", row=row, field="printed_amount")
    if not complete_document:
        # Complete reviewed pages still carry independently checkable source
        # fields. Missing pages prohibit treating their union as a ledger:
        # no order heuristic, inferred direction, derived anchor or arithmetic.
        checks["document_checks_deferred"] = True
        for row in rows:
            if row.direction == "unknown":
                record("direction_unknown", row=row, field="direction")
        for row in rows:
            if row.date is None:
                record("date_unparsed", row=row, field="date")
        parsed_rows = [(row, date.fromisoformat(row.date)) for row in rows if row.date]
        outside = 0
        if meta.period_start and meta.period_end and parsed_rows:
            lower = date.fromisoformat(meta.period_start) - timedelta(days=PERIOD_GRACE_DAYS)
            upper = date.fromisoformat(meta.period_end) + timedelta(days=PERIOD_GRACE_DAYS)
            for row, value in parsed_rows:
                if value < lower or value > upper:
                    outside += 1
                    record("period_mismatch", row=row, field="date")
        checks["dates_outside_period"] = outside
        duplicates = []
        positional = [0]
        distinguished, unverifiable = _duplicates(rows, occurrences=duplicates, positional=positional)
        checks["repeats"] = {"distinguished": distinguished, "unverifiable": unverifiable}
        checks["repeats_by_position"] = positional[0]
        if unverifiable:
            reasons.append("duplicate_row")
            occurrences.extend(duplicates)
        anchored = ("both" if meta.beginning_balance is not None and meta.ending_balance is not None
                    else "one" if meta.beginning_balance is not None or meta.ending_balance is not None
                    else "none")
        return GateVerdict(False, tuple(dict.fromkeys(reasons)), len(rows), (), None, 0, 0,
                           checks, anchored, tuple(occurrences))
    rows, reversed_order = orient(rows)
    rows, collapsed = collapse_daily_balances(rows)
    checks["reversed_order"] = reversed_order
    checks["collapsed_daily_balances"] = collapsed
    printed_beginning, printed_ending = meta.beginning_balance is not None, meta.ending_balance is not None
    anchored = "both" if printed_beginning and printed_ending else ("one" if printed_beginning or printed_ending else "none")
    checks["anchored"] = anchored
    beginning, ending = meta.beginning_balance, meta.ending_balance
    first, last = rows[0], rows[-1]
    if anchored == "none":
        record("anchors_underdetermined")
    else:
        if beginning is None and first.balance is not None and first.direction in ("credit", "debit"):
            beginning = first.balance - Decimal(str(_signed(first, minus_styled(rows))))
            checks["derived"].append("beginning_balance")
        if ending is None and last.balance is not None:
            ending = last.balance
            checks["derived"].append("ending_balance")
    if beginning is None and "anchors_underdetermined" not in reasons:
        record("missing_beginning_balance", field="beginning_balance")
    if ending is None and "anchors_underdetermined" not in reasons:
        record("missing_ending_balance", field="ending_balance")
    # A derived anchor leaves one end of the ledger unverified (a truncated read at that end still reconciles),
    # so the verdict is recorded but NOT admitted, unless the statement's printed totals and counts prove the
    # ledger complete (decided after reconciliation, below, and recorded at this point of the order).
    derived_at = (len(reasons), len(occurrences))
    resolved, flagged = resolve_directions(rows, beginning)
    for row in resolved:
        if row.direction == "unknown":
            record("direction_unknown", row=row, field="direction")
    if flagged and anchored != "both":
        for original, row in zip(rows, resolved):
            if original.direction == "unknown" and row.direction != "unknown":
                record("chain_direction_unanchored", row=row, field="direction")
    for row in resolved:
        if row.date is None:
            record("date_unparsed", row=row, field="date")
    parsed_rows = [(row, date.fromisoformat(row.date)) for row in resolved if row.date]
    parsed = [value for _, value in parsed_rows]
    # Date order is RECORDED, not a refusal reason: sectioned statements restart dates per section and
    # banks list checks by number. Period membership REFUSES (gate v5, CTRL wave): a reconciled ledger
    # carried 82 rows dated two years off (an unprinted year the model supplied). Every row of all 114
    # validated control accounts lies inside its printed period, so the check costs no valid document.
    outside = 0
    if meta.period_start and meta.period_end and parsed:
        lower = date.fromisoformat(meta.period_start) - timedelta(days=PERIOD_GRACE_DAYS)
        upper = date.fromisoformat(meta.period_end) + timedelta(days=PERIOD_GRACE_DAYS)
        for row, value in parsed_rows:
            if value < lower or value > upper:
                outside += 1
                record("period_mismatch", row=row, field="date")
    checks["dates_outside_period"] = outside
    checks["date_order_breaks"] = sum(1 for earlier, later in zip(parsed, parsed[1:]) if later < earlier)
    # Gate v6 (27B DEV wave): a statement that prints a running balance on EVERY row is chronological by
    # construction, so a date-order break there is a misread date (16 rows dated a day early, every amount
    # and balance exact). All 37 balance-chained validated control accounts have zero breaks; the 26
    # sectioned accounts that do break order carry no per-row balance and stay recorded only.
    chained = bool(resolved) and all(row.balance is not None for row in resolved)
    checks["balance_chained"] = chained
    if chained and checks["date_order_breaks"]:
        for (_, earlier), (row, later) in zip(parsed_rows, parsed_rows[1:]):
            if later < earlier:
                record("date_order_chained", row=row, field="date")
    duplicate_occurrences: list[dict] = []
    positional = [0]
    distinguished, unverifiable = _duplicates(resolved, occurrences=duplicate_occurrences, positional=positional)
    checks["repeats"] = {"distinguished": distinguished, "unverifiable": unverifiable}
    checks["repeats_by_position"] = positional[0]
    computed_ending: Decimal | None = None
    continuity_breaks = 0
    counts_vouch = False
    if beginning is not None and ending is not None and "direction_unknown" not in reasons and "proposal_invalid" not in reasons:
        meta_for_reader = replace(meta, beginning_balance=beginning, ending_balance=ending)
        statement = statement_from(resolved, meta_for_reader)
        result = reconcile(statement)
        if result.computed_ending is not None:
            computed_ending = Decimal(str(result.computed_ending)).quantize(Decimal("0.01"))
        continuity_breaks = int(result.continuity_breaks or 0)
        checks["reader_issues"] = list(result.issues)
        checks["summary_ok"] = result.summary_ok
        checks["credit_count_matches"] = result.stated_credit_count_matches
        checks["debit_count_matches"] = result.stated_debit_count_matches
        delta = abs(Decimal(str(result.sum_delta))) if result.sum_delta is not None else None
        if delta is None or delta > tolerance:
            record("sum_mismatch")
        if continuity_breaks:
            reasons.append("continuity_break")
            failures = _continuity_failure_rows(resolved, statement)
            for row in failures[:continuity_breaks]:
                record("continuity_break", row=row, field="balance")
            # If the reader's algorithm changes, keep its authoritative count
            # without inventing a page or altering the admission decision.
            for _ in range(max(0, continuity_breaks - len(failures))):
                record("continuity_break", field="balance")
        if result.summary_ok is False:
            record("summary_mismatch")
        if result.stated_credit_count_matches is False:
            record("count_mismatch", field="stated_credit_count")
        if result.stated_debit_count_matches is False:
            record("count_mismatch", field="stated_debit_count")
        if not result.ok and not any(r in reasons for r in ("sum_mismatch", "summary_mismatch")):
            # RR-7 includes any remaining reconcile issue. Only actual failed
            # coverage fields get field attribution; a catch-all stays global.
            fields = [field for field, coverage in (
                ("stated_total_credits", result.credit_coverage),
                ("stated_total_debits", result.debit_coverage),
            ) if coverage is not None and (coverage < 0.98 or coverage > 1.02)]
            if fields:
                for field in fields:
                    record("coverage_mismatch", field=field)
            else:
                record("coverage_mismatch")
        if checks["derived"]:
            checks["derived_anchor_proven_complete"] = _proven_complete(statement, meta, result)
    if checks["derived"] and not checks.get("derived_anchor_proven_complete"):
        for offset, field in enumerate(checks["derived"]):
            reasons.insert(derived_at[0] + offset, "anchor_derived")
            occurrences.insert(derived_at[1] + offset, {"code": "anchor_derived", "page": None, "source": "gate",
                                                        "field": field})
    if unverifiable:
        reasons.append("duplicate_row")   # RR-2: an unverifiable repeat is never amnestied by a matching count
        occurrences.extend(duplicate_occurrences)
    ordered = tuple(dict.fromkeys(reasons))
    admitted = not ordered
    return GateVerdict(admitted, ordered, len(resolved), tuple(resolved) if admitted else (), computed_ending,
                       continuity_breaks, flagged, checks, anchored, tuple(occurrences))

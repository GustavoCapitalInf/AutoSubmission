"""A statement whose own printed figures contradict the transactions it lists: a failure of the statement, not of
the reading (owner ruling, 2026-09-23: "If a statement's transactions genuinely do not add up, do not spend time
trying to validate something that cannot be validated. First verify from the statement evidence that the
contradiction exists and is not caused by an extraction or program error." Such a statement is a valid failure,
shown as "Fail: Statement <x> contradiction").

The contradiction is said only when the PDF's own text layer proves the reading complete and exact, so that nothing
but the statement itself can be the cause:

* the gate held the statement for arithmetic alone (sum, summary, count or running-balance mismatches), never for
  an unresolved page or row, an unknown direction, a disagreement between the readers or an invalid reading;
* every page has a text layer, and when the pages print "Page X of N" every one of the N pages is in the file;
* every row is directed, and its amount is printed on its own page, on a line of its own row;
* no amount printed on any page is unaccounted for, except on a line printing only a statement figure ("Ending
  Balance", "Electronic Withdrawals", "Total Service Charges") or a sentence (a notice, a disclosure); and no
  selection of those unaccounted amounts closes the difference (a missed row would);
* the beginning and ending balances (and the printed totals it compares) are printed in the text layer;
* the rows' directions are proven: a printed total equals its listed side to the cent, or every row prints its
  running balance.

Then the listed transactions do not reach the printed ending balance, and the reason is named: a printed total the
listed side does not make, else the ending balance itself. Any doubt leaves the statement held for review, as before.
"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from itertools import combinations

from vlm.native_text import _ROW_START, _money_spans

SOURCE_CONTRADICTION_VERSION = 1
# Gate reasons that are arithmetic about a complete reading; any other reason is a doubt about the reading.
ARITHMETIC_REASONS = frozenset({"sum_mismatch", "summary_mismatch", "count_mismatch", "continuity_break"})
_DIFFERENCE_REASONS = frozenset({"sum_mismatch", "summary_mismatch", "continuity_break"})
KINDS = ("debit_total", "credit_total", "ending_balance")
_PAGE_MARK = re.compile(r"\bpage\s+(\d{1,3})\s+of\s+(\d{1,3})\b", re.I)
# The words a line printing only a statement figure is made of (a summary box, a totals line).
_FIGURE_WORDS = frozenset((
    "beginning ending opening closing previous new balance balances total totals subtotal credits credit debits debit "
    "deposits deposit withdrawals withdrawal additions subtractions checks check cheques cheque paid fees fee charges "
    "charge service services interest earned average ledger collected daily minimum maximum low other electronic "
    "regular and the of for this period statement cycle ytd year to date days in number count items item overdraft "
    "overdrafts returned card cards atm pos purchases purchase account summary available current apy annual "
    "percentage yield rate amount by as at on per less plus net activity").split())
_CENT = Decimal("1e-2")
_MAX_UNCLAIMED = 20


def _decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value)).quantize(_CENT)
    except (InvalidOperation, ValueError):
        return None


def _figure_line(text: str) -> bool:
    """A line printing only a statement figure: no date first, and nothing but figure words besides its amounts."""
    if _ROW_START.match(text):
        return False
    words = re.findall(r"[A-Za-z]+", _strip_money(text))
    return bool(words) and all(word.lower() in _FIGURE_WORDS for word in words)


def _prose_line(text: str) -> bool:
    """A sentence (a notice, a disclosure): five words or more, three of them in lower case."""
    words = re.findall(r"[A-Za-z]+", _strip_money(text))
    return len(words) >= 5 and sum(word.islower() for word in words) >= 3


def _strip_money(text: str) -> str:
    kept, last = [], 0
    for start, end, _ in _money_spans(text):
        kept.append(text[last:start])
        last = end
    kept.append(text[last:])
    return " ".join(kept)


def _closes(amounts: list[Decimal], targets: set[Decimal]) -> bool:
    """Whether some selection of the unaccounted amounts adds up to a difference (a row the reading missed would)."""
    targets = {target for target in targets if target > 0}
    for size in range(1, len(amounts) + 1):
        for chosen in combinations(amounts, size):
            if sum(chosen, Decimal("0")) in targets:
                return True
    return False


def verify_source_contradiction(*, reasons, rows, account: dict, printed_pages) -> dict | None:
    """The statement's verified contradiction (see the module docstring), or None when anything leaves a doubt."""
    held_for = set(reasons or ())
    if not held_for or not held_for <= ARITHMETIC_REASONS or not held_for & _DIFFERENCE_REASONS:
        return None
    pages = list(printed_pages or ())
    if not pages or any(page is None or not page.native for page in pages):
        return None
    marks = {(int(number), int(count)) for page in pages for number, count in _PAGE_MARK.findall(page.native)}
    if marks:
        counts = {count for _, count in marks}
        if len(counts) != 1 or {number for number, _ in marks} != set(range(1, counts.pop() + 1)) \
                or max(number for number, _ in marks) > len(pages):
            return None
    rows = list(rows or ())
    if not rows:
        return None
    listed = {"credit": Decimal("0"), "debit": Decimal("0")}
    claims = Counter()
    for row in rows:
        amount = _decimal(getattr(row, "amount", None))
        if getattr(row, "direction", None) not in listed or amount is None or not 0 < row.page <= len(pages):
            return None
        page = pages[row.page - 1]
        if not page.amount_in_text_layer(amount) or not page.row_line_numbers(amount, row.date_text, row.balance):
            return None
        listed[row.direction] += abs(amount)
        claims[(row.page, abs(amount))] += 1
        balance = _decimal(row.balance)
        if balance is not None:
            claims[(row.page, abs(balance))] += 1
    begin, end = _decimal(account.get("beginning_balance")), _decimal(account.get("ending_balance"))
    printed_credits = _decimal(account.get("stated_total_credits"))
    printed_debits = _decimal(account.get("stated_total_debits"))

    def printed(value: Decimal | None) -> bool:
        return value is not None and any(page.amount_in_text_layer(abs(value)) for page in pages)

    if not printed(begin) or not printed(end):
        return None
    printed_credits = printed_credits if printed(printed_credits) else None
    printed_debits = printed_debits if printed(printed_debits) else None
    reached = begin + listed["credit"] - listed["debit"]
    if reached == end:
        return None
    proven = ((printed_credits is not None and listed["credit"] == printed_credits)
              or (printed_debits is not None and listed["debit"] == printed_debits)
              or all(_decimal(row.balance) is not None for row in rows))
    if not proven:
        return None
    # Lines that could be rows claim the rows' amounts first; an amount left on one is a row the reading may have
    # missed. Then what the rows did not claim may be left only on a figure line or a sentence.
    lines = [(number, " ".join(line.split())) for number, page in enumerate(pages, start=1) for line in page.text_lines]
    unclaimed = []
    for statement_line in (False, True):
        for number, text in lines:
            if (_figure_line(text) or _prose_line(text)) != statement_line:
                continue
            free = []
            for _, _, amount in _money_spans(text):
                if claims[(number, amount)] > 0:
                    claims[(number, amount)] -= 1
                else:
                    free.append(amount)
            if free and not statement_line:
                return None   # an amount on a line that could be a row the reading missed
            unclaimed.extend(free)
    targets = {abs(reached - end)}
    if printed_credits is not None:
        targets.add(abs(printed_credits - listed["credit"]))
    if printed_debits is not None:
        targets.add(abs(printed_debits - listed["debit"]))
    if len(unclaimed) > _MAX_UNCLAIMED or _closes(unclaimed, targets):
        return None
    if printed_debits is not None and listed["debit"] != printed_debits and (
            printed_credits is None or listed["credit"] == printed_credits):
        kind, listed_value, printed_value = "debit_total", listed["debit"], printed_debits
    elif printed_credits is not None and listed["credit"] != printed_credits and (
            printed_debits is None or listed["debit"] == printed_debits):
        kind, listed_value, printed_value = "credit_total", listed["credit"], printed_credits
    else:
        kind, listed_value, printed_value = "ending_balance", reached, end
    return {
        "version": SOURCE_CONTRADICTION_VERSION, "kind": kind,
        "listed": str(listed_value), "printed": str(printed_value),
        "beginning_balance": str(begin), "ending_balance": str(end), "reached_balance": str(reached),
        "listed_credits": str(listed["credit"]), "listed_debits": str(listed["debit"]),
        "printed_total_credits": None if printed_credits is None else str(printed_credits),
        "printed_total_debits": None if printed_debits is None else str(printed_debits),
        "rows": len(rows), "pages": len(pages), "unclaimed_statement_figures": len(unclaimed),
        "currency": account.get("currency"),
    }


def _money(value: Decimal, currency) -> str:
    code = str(currency or "USD").upper()
    text = f"{abs(value):,.2f}"
    sign = "-" if value < 0 else ""
    if code == "USD":
        return f"{sign}${text}"
    if code == "CAD":
        return f"{sign}CA${text}"
    return f"{sign}{text} {code}" if re.fullmatch(r"[A-Z]{3}", code) else f"{sign}{text}"


_DASHBOARD_MESSAGE = re.compile(r"^Fail: Statement (?:debit total|credit total|ending balance) \([^()]{1,80}\) "
                                r"contradiction$")


def is_source_contradiction(message) -> bool:
    """Whether a job's analysis error is a verified source contradiction's message (SourceContradictionError)."""
    return isinstance(message, str) and _DASHBOARD_MESSAGE.fullmatch(message) is not None


class SourceContradictionError(RuntimeError):
    """The worker-boundary refusal of a statement with a verified source contradiction. Built only from the verdict's
    closed set of reasons and its figures (never from free text), so the dashboard can say why."""

    def __init__(self, kind: str, listed: Decimal, printed: Decimal, currency=None):
        if kind not in KINDS:
            raise ValueError("unknown source contradiction")
        self.kind, self.listed, self.printed, self.currency = kind, listed, printed, currency
        super().__init__(self.dashboard_message())

    @classmethod
    def from_verdict(cls, verdict) -> "SourceContradictionError | None":
        """The refusal for a stored verdict, or None when it is not a well-formed one."""
        if not isinstance(verdict, dict) or verdict.get("version") != SOURCE_CONTRADICTION_VERSION:
            return None
        listed, printed = _decimal(verdict.get("listed")), _decimal(verdict.get("printed"))
        currency = verdict.get("currency")
        if verdict.get("kind") not in KINDS or listed is None or printed is None or listed == printed:
            return None
        if currency is not None and not (isinstance(currency, str) and re.fullmatch(r"[A-Za-z]{3}", currency)):
            return None
        return cls(verdict["kind"], listed, printed, currency)

    def dashboard_message(self) -> str:
        listed, printed = _money(self.listed, self.currency), _money(self.printed, self.currency)
        reason = {
            "debit_total": f"debit total ({listed} listed, {printed} printed)",
            "credit_total": f"credit total ({listed} listed, {printed} printed)",
            "ending_balance": f"ending balance ({listed} from the listed transactions, {printed} printed)",
        }[self.kind]
        return f"Fail: Statement {reason} contradiction"

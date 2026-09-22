"""The printed account summary as a proof of the statement's totals and counts.

Many banks print no "total credits" line. The summary lists categories between the beginning and the ending
balance (customer deposits, other deposits, withdrawals, checks, fees), and each transaction section prints
its own subtotal. A reviewer asked for one total then invents it or picks a section subtotal.

A summary box is the contiguous run of lines around the printed beginning and ending balance. It is proven
when every category line in it satisfies

    beginning + sum(credit lines) - sum(debit lines) = ending

exactly, to the cent, with this statement's beginning and ending balance. The statement's totals and counts
are then the sums of those printed lines: arithmetic by the application over printed figures, never by a
model. Every category line of the box is used (no subset is searched for), so an accidental proof needs an
exact coincidence. A line whose direction cannot be told, or a box that does not balance, proves nothing.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from decimal import Decimal

from vlm.metadata import BEGIN_RE, END_RE, MONEY_TOKEN
from vlm.tables import parse_html_tables
from vlm.textparse import parse_money

_AMOUNT = r"\(?-?\$?\s?\d{1,3}(?:,\d{3})*\.\d{2}\)?-?|\(?-?\$?\s?\d+\.\d{2}\)?-?"
_CATEGORY = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z &/,'().-]{{1,60}}?)\s+(?:(?P<count>\d{{1,4}})\s+)?(?P<amount>{_AMOUNT})$")
_CREDIT_WORDS = re.compile(r"\b(?:deposits?|credits?|additions?|interest (?:paid|earned)|dividends?)\b", re.I)
_DEBIT_WORDS = re.compile(r"\b(?:withdrawals?|debits?|checks?|cheques?|fees?|charges?|subtractions?|payments?|"
                          r"purchases?|interest charged)\b", re.I)
_NOT_CATEGORY = re.compile(r"\b(?:total|totals|subtotal|balance|balances|average|ytd|year)\b", re.I)
_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class SummaryProof:
    page: int
    stated_total_credits: Decimal
    stated_total_debits: Decimal
    stated_credit_count: int | None
    stated_debit_count: int | None
    line_count: int


def page_lines(native: str | None, blocks=()) -> list[str]:
    """A page as text lines: its text layer when it has one, else the proposer's blocks, one line per table
    row (cells joined by spaces) and one per text line."""
    if native:
        return native.splitlines()
    lines: list[str] = []
    for block in blocks:
        content = str(getattr(block, "content", "") or "")
        if "<table" in content.lower():
            for grid in parse_html_tables(content):
                lines.extend(" ".join(cell for cell in row if cell) for row in grid)
        else:
            lines.extend(html.unescape(_TAG.sub(" ", content)).splitlines())
    return lines


def _balance(text: str, pattern: re.Pattern) -> Decimal | None:
    match = pattern.search(text)
    if not match:
        return None
    for token in MONEY_TOKEN.finditer(text, match.end()):
        value = parse_money(token.group(0).strip())
        if value is not None:
            return value
    return None


def _category(text: str) -> tuple[str | None, Decimal, int | None] | None:
    """(direction or None when it cannot be told, magnitude, printed count) for a category line; None when the
    line is not one."""
    match = _CATEGORY.match(text)
    if not match or _NOT_CATEGORY.search(match.group("label")):
        return None
    label, amount_text = match.group("label"), match.group("amount").strip()
    credit_word, debit_word = bool(_CREDIT_WORDS.search(label)), bool(_DEBIT_WORDS.search(label))
    if not credit_word and not debit_word:
        return None
    value = parse_money(amount_text)
    if value is None:
        return None
    negative = amount_text.endswith("-") or amount_text.startswith(("-", "(")) or value < 0
    if negative:
        direction = "debit" if not (credit_word and not debit_word) else None
    else:
        direction = "credit" if credit_word and not debit_word else "debit" if debit_word and not credit_word else None
    count = int(match.group("count")) if match.group("count") else None
    return direction, abs(value), count


def _box(texts: list[str], start: int):
    """The summary box that starts at a balance line: read forward, collecting category lines and the two
    balances; a total line inside the box is passed over. The box ends at the first other line once both
    balances and a category have been read. Any other money line before that means this is not a clean box.
    Returns (beginning, ending, categories) or None."""
    begin = end = None
    categories = []
    for text in texts[start:]:
        if not text:
            continue
        if BEGIN_RE.search(text):
            begin = begin if begin is not None else _balance(text, BEGIN_RE)
            continue
        if END_RE.search(text):
            end = end if end is not None else _balance(text, END_RE)
            continue
        found = _category(text)
        if found is not None:
            if found[0] is None:
                return None  # a category the box prints but whose direction cannot be told: no proof
            categories.append(found)
            continue
        complete = begin is not None and end is not None and categories
        if MONEY_TOKEN.search(text):
            if _NOT_CATEGORY.search(text) and not complete:
                continue  # a total or another balance printed inside the box
            if complete:
                break
            return None
        if complete:
            break
    return begin, end, categories


def _page_proof(number: int, lines: list[str], beginning: Decimal, ending: Decimal) -> SummaryProof | None:
    texts = [" ".join(str(line).split()) for line in lines]
    starts = [index for index, text in enumerate(texts) if BEGIN_RE.search(text) or END_RE.search(text)]
    for start in starts:
        proof = _box_proof(number, _box(texts, start), beginning, ending)
        if proof is not None:
            return proof
    return None


def _box_proof(number, box, beginning: Decimal, ending: Decimal) -> SummaryProof | None:
    if box is None:
        return None
    begin, end, categories = box
    if begin is None or end is None or not categories:
        return None
    if abs(begin) != abs(beginning) or abs(end) != abs(ending):
        return None
    credits = sum((value for direction, value, _ in categories if direction == "credit"), Decimal("0"))
    debits = sum((value for direction, value, _ in categories if direction == "debit"), Decimal("0"))
    if beginning + credits - debits != ending:
        return None

    def count(direction):
        counts = [printed for side, _, printed in categories if side == direction]
        return sum(counts) if counts and all(printed is not None for printed in counts) else None

    return SummaryProof(number, credits, debits, count("credit"), count("debit"), len(categories))


def prove_summary_box(page_texts, *, beginning, ending) -> SummaryProof | None:
    """The first page whose printed category summary balances this statement's beginning to its ending."""
    if beginning is None or ending is None:
        return None
    try:
        start, finish = Decimal(str(beginning)), Decimal(str(ending))
    except ArithmeticError:
        return None
    for number, text in enumerate(page_texts, start=1):
        lines = text if isinstance(text, list) else str(text or "").splitlines()
        proof = _page_proof(number, lines, start, finish)
        if proof is not None:
            return proof
    return None

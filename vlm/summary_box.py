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

Some boxes print each line's arithmetic sign apart from its figure, after it ("Returned Checks $17.00 +", "Fees
$3.00 -", "Ending Balance $5.00 -" when overdrawn) or before it ("Checks - 2.00", "Deposits, credits and
interest + 9.00"). The printed sign is the line's direction, whatever its words say, and
a balance's printed minus is its own. When only the printed signs balance the box, the reader dropped a sign
(an overdrawn ending read as positive) and the proof restores it.

A proven box also names its sections: a heading printed on the transaction pages exactly as a category's label
("RETURNED CHECKS", "Returned Checks (continued)") heads that category's rows. When the rows printed under it
add up to the category's printed amount to the cent, each of them moves the balance the category's way
(settle_section_directions).
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
# A sign printed apart from the figure, after it ("$53.00 +", "$65.00 -") or before it ("- 2.00", "+ 9.00"); a
# minus joined to the figure is the amount's.
_CATEGORY = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z &/,'().-]{{1,60}}?)\s+(?:(?P<count>\d{{1,4}})\s+)?(?:(?P<lead>[+\-−])\s+)?"
    rf"(?P<amount>{_AMOUNT})(?:\s+(?P<sign>[+\-−]))?$")
_TRAILING_MINUS = re.compile(r"\s*[-−]\s*$")
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
    # The balances the box proves: the statement's as read, or the printed ones when only their printed signs
    # balance the box.
    beginning_balance: Decimal | None = None
    ending_balance: Decimal | None = None
    # (label, direction, magnitude) of every category line, in printed order.
    categories: tuple = ()


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
            # A minus printed apart after the figure, closing the line, is the balance's ("$5.00 -", overdrawn).
            if value > 0 and _TRAILING_MINUS.fullmatch(text[token.end():]):
                value = -value
            return value
    return None


def _category(text: str, *, lead_signs: bool = True) -> tuple[str | None, Decimal, int | None, str] | None:
    """(direction or None when it cannot be told, magnitude, printed count, label) for a category line; None
    when the line is not one. A sign printed apart from the figure is the line's direction, whatever its words
    say ("Returned Checks $17.00 +" adds to the balance), and makes a line without a direction word a category.
    A dash before the figure is a sign only in a box that prints a "+" there too (`lead_signs`); otherwise it
    separates the label from the figure ("Deposits - 100.00")."""
    match = _CATEGORY.match(text)
    if not match or _NOT_CATEGORY.search(match.group("label")):
        return None
    label, amount_text = match.group("label"), match.group("amount").strip()
    lead = match.group("lead") if lead_signs or match.group("lead") == "+" else None
    signs = [sign for sign in (lead, match.group("sign")) if sign]
    sign = signs[0] if len(signs) == 1 else None
    credit_word, debit_word = bool(_CREDIT_WORDS.search(label)), bool(_DEBIT_WORDS.search(label))
    if not credit_word and not debit_word and not signs:
        return None
    value = parse_money(amount_text)
    if value is None:
        return None
    negative = amount_text.endswith("-") or amount_text.startswith(("-", "(")) or value < 0
    count = int(match.group("count")) if match.group("count") else None
    if signs:
        # A figure printed negative and signed again, or signed on both sides, cannot be told.
        direction = None if negative or sign is None else "credit" if sign == "+" else "debit"
        return direction, abs(value), count, label
    if negative:
        direction = "debit" if not (credit_word and not debit_word) else None
    else:
        direction = "credit" if credit_word and not debit_word else "debit" if debit_word and not credit_word else None
    return direction, abs(value), count, label


def _box(texts: list[str], start: int):
    """The summary box that starts at a balance line: read forward, collecting category lines and the two
    balances; a total line inside the box is passed over. The box ends at the first other line once both
    balances and a category have been read. Any other money line before that means this is not a clean box.
    Returns (beginning, ending, categories) or None."""
    begin = end = None
    categories, lines = [], []
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
            lines.append(text)
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
    # Dashes before the figures are signs only in a box that prints a "+" there too.
    if not any(_CATEGORY.match(text).group("lead") == "+" for text in lines):
        categories = [_category(text, lead_signs=False) for text in lines]
        if any(found is None or found[0] is None for found in categories):
            return None
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
    # A box prints a count on every category line or on none. An uncounted line among counted ones is not the
    # box's own line (a fee or a returned item printed just under it), and two such lines can cancel out.
    if len({printed is None for _, _, printed, _ in categories}) > 1:
        return None
    credits = sum((value for direction, value, _, _ in categories if direction == "credit"), Decimal("0"))
    debits = sum((value for direction, value, _, _ in categories if direction == "debit"), Decimal("0"))
    # The statement's balances as read, else as printed: a sign the reader dropped (an overdrawn ending printed
    # "$5.00 -" read as 5.00) is restored when only the printed signs balance the box.
    if beginning + credits - debits == ending:
        opening, closing = beginning, ending
    elif begin + credits - debits == end:
        opening, closing = begin, end
    else:
        return None

    def count(direction):
        counts = [printed for side, _, printed, _ in categories if side == direction]
        return sum(counts) if counts and all(printed is not None for printed in counts) else None

    return SummaryProof(number, credits, debits, count("credit"), count("debit"), len(categories), opening, closing,
                        tuple((label, direction, value) for direction, value, _, label in categories))


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


_CONTINUED = re.compile(r"\s*(?:\((?:continued|cont'd|cont\.?)\)|-?\s*continued)$")
_TOTAL_LINE = re.compile(rf"^total\s+(?P<label>.+?)\s+(?:{_AMOUNT})(?:\s+[+\-−])?$")
_CENT = Decimal("0.01")


def _heading_key(text) -> str:
    """A printed line or a category label as a section title: case, spacing, a closing colon and a
    "(continued)" left out."""
    key = " ".join(str(text or "").split()).lower()
    return _CONTINUED.sub("", key).strip().rstrip(":").strip()


def settle_section_directions(rows, printed_pages, categories):
    """Rows printed under a heading that is a proven category's label ("RETURNED CHECKS" under the box line
    "Returned Checks $17.00 +") move the balance the category's way, when that section's rows add up to the
    category's printed amount to the cent.

    A row is in a section when every text-layer line that is this row's (PrintedEvidence.row_line_numbers) lies
    under that heading. A heading holds until the next one or its own "Total ..." line, across pages; a page
    without a text layer ends it. A section whose rows do not add up to the category's amount, or holding a row
    whose direction a labelled debit or credit column printed the other way, changes nothing: the gate then
    judges the rows as read. Returns (rows, audit)."""
    from dataclasses import replace

    # Headings are matched without spaces: a text layer can run two printed words together
    # ("Otherwithdrawals, debits and service charges" under the box's "Other withdrawals, ...").
    labels: dict[str, set] = {}
    for item in categories or ():
        if item.get("direction") in ("credit", "debit"):
            key = _heading_key(item["label"])
            labels.setdefault(key.replace(" ", ""), set()).add(
                (item["direction"], Decimal(str(item["amount"])).quantize(_CENT), key))
    # A label the box prints twice with different figures names no one section.
    labels = {key: next(iter(found)) for key, found in labels.items() if key and len(found) == 1}
    audit = {"sections": [], "settled_rows": []}
    rows = list(rows)
    if not labels or not rows:
        return rows, audit
    under: list[list | None] = []
    current = None
    for evidence in printed_pages or ():
        if evidence is None or not evidence.native:
            under.append(None)
            current = None
            continue
        page = []
        for line in evidence.text_lines:
            key = _heading_key(line)
            if key.replace(" ", "") in labels:
                current = key.replace(" ", "")
            page.append(current)
            total = _TOTAL_LINE.match(key)
            if total and _heading_key(total.group("label")).replace(" ", "") == current:
                current = None
        under.append(page)
    members: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        page = under[row.page - 1] if 0 < row.page <= len(under) else None
        if page is None:
            continue
        lines = printed_pages[row.page - 1].row_line_numbers(row.amount, row.date_text, row.balance)
        sections = {page[line] for line in lines or ()}
        if len(sections) == 1 and None not in sections:
            members.setdefault(sections.pop(), []).append(index)
    settled = list(rows)
    for compact, indexes in members.items():
        direction, amount, key = labels[compact]
        total = sum((rows[index].amount for index in indexes), Decimal("0")).quantize(_CENT)
        contrary = [index for index in indexes if rows[index].direction != direction]
        columned = [index for index in contrary if rows[index].printed_amount is not None]
        proven = total == amount and not columned
        audit["sections"].append({"section": key, "direction": direction, "rows": len(indexes),
                                  "sums_to_category": total == amount, "column_conflicts": len(columned),
                                  "settled": len(contrary) if proven else 0})
        if not proven:
            continue
        for index in contrary:
            row = rows[index]
            settled[index] = replace(row, direction=direction, direction_source="printed_section")
            audit["settled_rows"].append({"page": row.page, "locator": row.locator, "section": key,
                                          "read": row.direction, "settled": direction})
    return settled, audit

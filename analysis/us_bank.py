from __future__ import annotations

import re
from datetime import date

from .money import EITHER_MINUS_SPACED, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, group_rows

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_DATE_RE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
_MONEY_RE = r"\$?\s*[\d,]+\.\d{2}-?"

#: The Account Summary categories U.S. Bank prints, and the detail section each
#: one is itemized in. This is the bank's printed vocabulary — the same class of
#: knowledge as a column heading — and nothing here is keyed on a customer, an
#: amount, a date or an account. The DIRECTION of a category is deliberately NOT
#: in this table: the summary prints a trailing minus on every outflow line, so
#: the sign is read from the grid (see `_summary`).
#:
#: The summary is the index to the ledger: whichever categories a statement
#: prints are exactly the sections it itemizes. A U.S. Bank statement that
#: itemizes no card activity simply prints no card line, so a fixed list of
#: three sections — which is what this parser had — silently dropped every
#: category outside it from BOTH the stated totals and the ledger.
_DETAIL_HEADING = {
    "Customer Deposits": "Customer Deposits",
    "Other Deposits": "Other Deposits",
    "Card Deposits": "Card Deposits",
    "Card Withdrawals": "Card Withdrawals",
    "Other Withdrawals": "Other Withdrawals",
    "Checks Paid": "Checks Presented Conventionally",
}
_SECTION_HEADINGS = frozenset(_DETAIL_HEADING.values())

_SUMMARY_CATEGORY_RE = re.compile(
    r"(" + "|".join(re.escape(name) for name in _DETAIL_HEADING) + r")"
    r"\s+(\d+)\s+([\d,]+\.\d{2})(-?)(?![\d.])"
)

#: A row begins where the printed grid begins one: a physical line whose first
#: cell is the Date column, optionally preceded by the row's own number column
#: (the check number in `Checks Presented Conventionally`, the deposit ticket
#: number in `Customer Deposits`) and its gap marker.
_ROW_START_RE = re.compile(r"^(?:(\d{1,10})(\*?)\s+)?(" + _DATE_RE + r")\b\s*(.*)$")

#: U.S. Bank prints the numbered sections in several column groups per physical
#: line, so one line can carry four printed rows. A row ends at its Amount cell,
#: so the seam is an amount followed by the next row's number-or-date cell.
_SEAM_RE = re.compile(
    r"(?<=\.\d{2})\s+(?=(?:\d{1,10}\*?\s+)?" + _DATE_RE + r"\b)"
    r"|(?<=\.\d{2}-)\s+(?=(?:\d{1,10}\*?\s+)?" + _DATE_RE + r"\b)"
)

#: Grid furniture inside a section: the column header (reprinted for every card
#: sub-block and after every page break), the card sub-block heading, and the
#: bank's own per-card subtotal. Each closes the row above it and opens nothing.
_ROW_FURNITURE_RE = re.compile(
    r"^(?:Date Description of Transaction|Number Date Ref Number Amount"
    r"|Check Date Ref Number Amount|Card Number:"
    r"|Card \S+ (?:Deposit|Withdrawals) Subtotal)"
)

#: What ends a detail section: the bank's own printed total for it, the checks
#: section's differently-worded total and its gap-marker footnote, a page break
#: (the section re-enters at its `(continued)` heading), the page footer, and
#: the headings of the blocks that follow the ledger.
_CHECKS_TOTAL_RE = re.compile(r"^Conventional Checks Paid \(\d+\)")
_SECTION_END_PREFIXES = (
    "--- Page",
    "Products and services available",
    "This page intentionally",
    "Balance Summary",
    "Account Summary",
    "* Gap in check sequence",
)


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_SPACED)


def _iso(month_day: str, year: int) -> str:
    month, day = month_day.split()
    return date(year, _MONTHS[month], int(day)).isoformat()


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"(?P<start_month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(?P<start_day>\d{1,2}),\s+(?P<start_year>\d{4})\s+through\s+"
        r"(?P<end_month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(?P<end_day>\d{1,2}),\s+(?P<end_year>\d{4})",
        markdown,
    )
    if not m:
        return None
    start = date(int(m.group("start_year")), _MONTHS[m.group("start_month")], int(m.group("start_day")))
    end = date(int(m.group("end_year")), _MONTHS[m.group("end_month")], int(m.group("end_day")))
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _summary(markdown: str) -> dict | None:
    """The printed Account Summary, read as the grid U.S. Bank prints.

    The block is `Beginning Balance`, then one `<category> <# items> <amount>`
    line per category the statement has activity in — outflows carrying the
    bank's trailing minus — then `Ending Balance`. Reading the categories rather
    than three memorized ones is what makes the stated totals complete.
    """
    m = re.search(
        r"Beginning Balance on \w+ \d+\s+\$\s*(?P<open>[\d,]+\.\d{2}-?)"
        r"(?P<categories>.*?)"
        r"Ending Balance on\s+\w+ \d+,\s+\d{4}\s+\$\s*(?P<close>[\d,]+\.\d{2}-?)",
        markdown,
        re.DOTALL,
    )
    days = re.search(r"Number of Days in Statement Period\s+(\d+)", markdown)
    if not m or not days:
        return None
    interest = re.search(r"Interest Earned this Period\s+\$\s*([\d,]+\.\d{2})", markdown)
    categories: list[tuple[str, int, float]] = []
    for c in _SUMMARY_CATEGORY_RE.finditer(m.group("categories")):
        amount = _money(c.group(3)) or 0.0
        categories.append((c.group(1), int(c.group(2)), -amount if c.group(4) else amount))
    if not categories:
        return None
    return {
        "beginning": _money(m.group("open")) or 0.0,
        "ending": _money(m.group("close")) or 0.0,
        "days": int(days.group(1)),
        "categories": categories,
        # Interest is an OPTIONAL summary line, exactly like the optional
        # categories above: a non-interest-bearing account simply does not print
        # one. Discovery found 36 documents whose summary omits it, and
        # dereferencing the unmatched regex raised AttributeError out of the
        # parser. No printed interest is zero interest — the same reading the
        # categories take, and one reconciliation independently checks.
        "interest": (_money(interest.group(1)) or 0.0) if interest else 0.0,
    }


def _section_lines(markdown: str) -> dict[str, list[str]]:
    """Every printed detail section, as the physical lines printed inside it.

    A heading owns its line, so a summary line or a sentence of disclosure prose
    that happens to contain the heading's words never opens a section. A page
    break leaves the section and its `(continued)` heading re-enters it, which
    is what keeps the reprinted letterhead out of the ledger.
    """
    sections: dict[str, list[str]] = {heading: [] for heading in _SECTION_HEADINGS}
    current: str | None = None
    for raw in markdown.splitlines():
        line = compact_whitespace(raw)
        if not line:
            continue
        heading = line[: -len(" (continued)")] if line.endswith(" (continued)") else line
        if heading in _SECTION_HEADINGS:
            current = heading
            continue
        if current is None:
            continue
        if (
            line.startswith(f"Total {current} ")
            or _CHECKS_TOTAL_RE.match(line)
            or line.startswith(_SECTION_END_PREFIXES)
        ):
            current = None
            continue
        sections[current].append(line)
    return sections


_TRAILING_MONEY_RE = re.compile(_MONEY_RE + r"\s*$")


def _amount_cell(parts: list[str]) -> tuple[str, int] | None:
    """The row's Amount cell: `(text, offset in " ".join(parts))`.

    The Amount column is printed right-aligned and last, so the cell is the
    money token that TERMINATES a printed line — and the first such token in
    the row, because everything after it is the description continuing. That
    distinction is what a foreign-currency row needs: the bank prints
    `Exchg Amt: $54.63 Orig Curr:936.38` on a continuation line, so a
    "last money token" rule reads the original-currency figure as the amount,
    and a "last line-terminating token" rule reads it too.

    The fallback — the last money token anywhere in the row — is for a row
    whose amount cell is followed on its own line by text the flattening moved,
    and it is only ever reached when no line in the row ends in money.
    """
    body = " ".join(parts)
    offset = 0
    for part in parts:
        m = _TRAILING_MONEY_RE.search(part)
        if m:
            return m.group(0), offset + m.start()
        offset += len(part) + 1
    tokens = list(re.finditer(_MONEY_RE, body))
    if not tokens:
        return None
    return tokens[-1].group(0), tokens[-1].start()


def _rows(lines: list[str], *, year: int, sign: int) -> list[Transaction]:
    pieces: list[str] = []
    for line in lines:
        pieces.extend(compact_whitespace(part) for part in _SEAM_RE.split(line))
    txns: list[Transaction] = []
    for group in group_rows(
        pieces, starts_row=_ROW_START_RE.match, ends_row=_ROW_FURNITURE_RE.match
    ):
        opener = _ROW_START_RE.match(group[0])
        if opener is None:  # pragma: no cover - group_rows only opens a row here
            continue
        number, marker, month_day, head = opener.groups()
        parts = [part for part in [head, *group[1:]] if part]
        cell = _amount_cell(parts)
        if cell is None:
            continue
        amount_text, cut = cell
        amount = abs(_money(amount_text) or 0.0) * sign
        if number is not None:
            # A numbered row's own number is the description the bank printed
            # for it; the Ref Number that follows is the bank's internal
            # tracing id and is not a description.
            description = f"Check {number}{marker}"
        else:
            description = " ".join(parts)[:cut]
        txns.append(
            Transaction(
                date=_iso(month_day, year),
                description=compact_whitespace(description),
                amount=round(amount, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "U.S. Bank National Association" in t),
    required("section", lambda t: "Account Summary" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_us_bank_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None

    categories = summary["categories"]
    credits = sum(amount for _, _, amount in categories if amount > 0)
    debits = -sum(amount for _, _, amount in categories if amount < 0)
    # The summary states its own identity, so our reading of it can be checked
    # against the statement itself: beginning + every category = ending. A
    # category we failed to read makes this miss by exactly that category, so
    # refusing here is what stops an incomplete summary being published as a
    # complete one.
    if abs(summary["beginning"] + credits - debits - summary["ending"]) > 0.02:
        return None

    period_start, period_end, period_days = period
    stmt = Statement(
        bank="U.S. Bank",
        account_name="Platinum Business Money Market",
        period_start=period_start,
        period_end=period_end,
        days_in_period=int(summary.get("days") or period_days),
        beginning_balance=float(summary["beginning"]),
        ending_balance=float(summary["ending"]),
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_credit_count=sum(count for _, count, amount in categories if amount > 0),
        stated_debit_count=sum(count for _, count, amount in categories if amount < 0),
        stated_interest_paid=float(summary["interest"]),
    )
    acct = re.search(r"Account Number\s+([0-9 -]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1).strip()

    year = int(period_end[:4])
    sections = _section_lines(markdown)
    txns: list[Transaction] = []
    for name, _, amount in categories:
        rows = _rows(sections[_DETAIL_HEADING[name]], year=year, sign=1 if amount > 0 else -1)
        # Each category prints its own total, so each section is checkable on
        # its own before anything is published. Failing here means the detail we
        # read does not account for the money the bank says is in that section.
        if abs(sum(t.amount for t in rows) - amount) > 0.02:
            return None
        txns.extend(rows)

    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - stmt.stated_total_credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - stmt.stated_total_debits) > 0.02:
        return None
    stmt.transactions = txns
    return stmt

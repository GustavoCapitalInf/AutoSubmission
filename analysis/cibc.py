"""The two CIBC layouts: the French `Détail de vos opérations` statement and
the English `CIBC Account Statement`.

They are different documents, not one document in two languages. The French
one prints a self-checking summary the parser verifies against before it will
publish anything; the English one prints a three-column posting grid
(`Withdrawals ($) | Deposits ($) | Balance ($)`) whose column of origin the
text layer destroys — the same grid RBC prints, read by the same shared
`tables.read_grid_rows`. Each has its own detection markers and its own
registration; nothing is shared between them but the bank word.
"""
from __future__ import annotations

import re
from datetime import date

from .money import parse_french_amount, parse_money, read_money
from .parser_registry import excluding, make_detector, required
from .schema import Statement, Transaction
from .tables import glyph_damaged, read_grid_rows

_MONTHS = {
    "jan": 1,
    "fev": 2,
    "fév": 2,
    "mar": 3,
    "avr": 4,
    "mai": 5,
    "jun": 6,
    "juin": 6,
    "jul": 7,
    "juil": 7,
    "aou": 8,
    "aoû": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "déc": 12,
}
_MONEY_RE = re.compile(r"(?<![A-Za-z0-9])-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}(?![A-Za-z0-9])")


def _money(value: str) -> float:
    return parse_french_amount(value)


def _money_candidates(value: str) -> list[tuple[float, int]]:
    candidates = [(_money(value), 0)]
    if " " in value:
        tail_start = value.rfind(" ") + 1
        candidates.append((_money(value[tail_start:]), tail_start))
    return candidates


def _month(token: str) -> int:
    key = token.lower()[:4] if token.lower().startswith("juil") else token.lower()[:3]
    return _MONTHS[key]


def _summary(markdown: str) -> tuple[float, float, float, float] | None:
    money = r"(-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2})"
    beginning = re.search(r"Solde d'ouverture.*?" + money + r"\s*\$", markdown, re.IGNORECASE)
    debits = re.search(r"Retraits\s*-\s*" + money, markdown, re.IGNORECASE)
    credits = re.search(r"D.p.ts\s*\+\s*" + money, markdown, re.IGNORECASE)
    ending = re.search(r"Solde de cl.ture.*?=\s*" + money + r"\s*\$", markdown, re.IGNORECASE)
    if not beginning or not debits or not credits or not ending:
        return None
    return _money(beginning.group(1)), _money(credits.group(1)), _money(debits.group(1)), _money(ending.group(1))


def _activity_lines(markdown: str) -> list[str]:
    start = markdown.find("Date Description Retraits")
    if start == -1:
        return []
    end = markdown.find("Solde de cl", start)
    if end == -1:
        return []
    lines: list[str] = []
    for raw in markdown[start:end].splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if "Date Description Retraits" in line:
            marker = "Solde ($)"
            idx = line.find(marker)
            line = line[idx + len(marker):].strip() if idx != -1 else ""
            if not line:
                continue
        if (
            "suite" in line
            or re.fullmatch(r"\d+ de \d+", line)
            or line.startswith(("10774F", "Relev", "Num", "Transit"))
        ):
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+(?=\d{1,2}\s+[A-Za-zÃ©Ã‰Ã»Ã¼Ã´ÃöÃàÃâ]{3,4}\b)", "\n", text)
    return text.splitlines()


def _parse_transactions(markdown: str, *, year: int, beginning: float) -> list[Transaction]:
    rows: list[Transaction] = []
    current_date: str | None = None
    prev_balance = beginning
    for line in _activity_lines(markdown):
        dm = re.match(r"^(\d{1,2})\s+([A-Za-zÃ©Ã‰Ã»Ã¼ÃôÃöÃàÃâ]{3,4})\s+(.*)$", line)
        if dm:
            current_date = date(year, _month(dm.group(2)), int(dm.group(1))).isoformat()
            remaining = dm.group(3).strip()
        else:
            remaining = line.strip()
        remaining = re.sub(
            r"^Solde d'ouverture\s+-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\s*\$?\s+\d{1,2}\s+\w+\s+",
            "",
            remaining,
        )
        remaining = re.sub(
            r"^Solde report\w+\s+-?(?:\d{1,3}(?: \d{3})+|\d+),\d{2}\s*\$?\s*",
            "",
            remaining,
        )
        while current_date is not None:
            tokens = list(_MONEY_RE.finditer(remaining))
            if len(tokens) < 2:
                break
            found: tuple[int, int, float, float, float, int] | None = None
            for balance_index in range(1, len(tokens)):
                balance = _money(tokens[balance_index].group(0))
                delta = round(balance - prev_balance, 2)
                for amount_index in range(balance_index - 1, -1, -1):
                    for candidate, offset in _money_candidates(tokens[amount_index].group(0)):
                        if abs(abs(delta) - candidate) <= 0.02:
                            found = (amount_index, balance_index, candidate, balance, delta, offset)
                            break
                    if found:
                        break
                if found:
                    break
            if not found:
                return []
            amount_index, balance_index, _candidate, balance, delta, offset = found
            amount_token = tokens[amount_index]
            amount_start = amount_token.start() + offset
            desc = remaining[:amount_start].strip()
            if not desc:
                return []
            rows.append(
                Transaction(
                    date=current_date,
                    description=re.sub(r"\s+", " ", desc),
                    amount=delta,
                    direction="credit" if delta > 0 else "debit",
                    running_balance=balance,
                )
            )
            prev_balance = balance
            remaining = remaining[tokens[balance_index].end():].strip()
    return rows


_OPERATIONS_RE = re.compile(r"D.tail de vos op.rations")

DETECTION_MARKERS = (
    required("bank_name", lambda t: "CIBC" in t),
    required("activity_section", lambda t: bool(_OPERATIONS_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS)


def parse_cibc_french_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = re.search(r"Du\s+(\d{1,2})\s+(\w+)\s+au\s+(\d{1,2})\s+(\w+)\s+(\d{4})", markdown)
    summary = _summary(markdown)
    if not period or summary is None:
        return None
    start_day, start_month, end_day, end_month, year_text = period.groups()
    year = int(year_text)
    beginning, credits, debits, ending = summary
    stmt = Statement(
        bank="CIBC",
        currency="CAD",
        period_start=date(year, _month(start_month), int(start_day)).isoformat(),
        period_end=date(year, _month(end_month), int(end_day)).isoformat(),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
    )
    acct = re.search(r"Num.ro de compte\s*:?\s*([0-9-]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)

    txns = _parse_transactions(markdown, year=year, beginning=beginning)
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - debits) > 0.02:
        return None
    if abs((txns[-1].running_balance or 0.0) - ending) > 0.02:
        return None
    stmt.transactions = txns
    return stmt


# ---------------------------------------------------------------------------
# The English layout: `CIBC Account Statement`
# ---------------------------------------------------------------------------

_EN_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
#: The posting-date token this layout prints in its Date column: `Nov 1`,
#: month first, no year. The year comes from the printed statement period.
_EN_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b")
_EN_MONEY_RE = re.compile(r"(?<![#\w])-?\$?[\d,]+\.\d{2}(?!\w)")
#: One printed cell of the account-summary block, with the sign wherever the
#: block sets it (see `rbc._SUMMARY_MONEY` for the same three placements).
_EN_SUMMARY_MONEY = r"((?:-\s*)?\$?(?:-\s*)?[\d,]+\.\d{2})"
#: `For Nov 1 to Nov 30, 2025` — the printed period, and the only source of the
#: year for every posting date in the document.
_EN_PERIOD_RE = re.compile(
    r"For\s+([A-Za-z]{3})\w*\s+(\d{1,2})\s+to\s+([A-Za-z]{3})\w*\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)
#: The activity table's own printed column header. It both opens the table and
#: re-opens it on a continuation page, and everything printed after it on the
#: same physical line is already grid content.
_EN_GRID_RE = re.compile(
    r"Date\s+Description\s+Withdrawals\s*\(\$\)\s*Deposits\s*\(\$\)\s*Balance\s*\(\$\)",
    re.IGNORECASE,
)
#: Grid furniture printed inside the table's span: the page-break note and the
#: form-number footer that follows it.
_EN_FOOTER_RE = re.compile(
    r"^(\(continued on next page\)|\S*\s*BUS-\d{4}/\d{2}\s+Page \d+ of \d+)$",
    re.IGNORECASE,
)
_EN_MONEY_TAIL_RE = re.compile(r"[\d,]+\.\d{2}$")

EN_DETECTION_MARKERS = (
    excluding("glyph_damage", glyph_damaged),
    required("bank_name", lambda t: "CIBC ACCOUNT STATEMENT" in t),
    required("activity_section", lambda t: "TRANSACTION DETAILS" in t),
    required("activity_header", lambda t: bool(_EN_GRID_RE.search(t))),
)


def en_detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


detect_en = make_detector(EN_DETECTION_MARKERS, en_detection_text)


def _en_amount(token: str) -> float:
    return read_money(token) or 0.0


def _en_summary_amount(token: str) -> float | None:
    return parse_money(re.sub(r"\s+", "", token))


def _en_date(month: str, day: str, *, start: date, end: date) -> str | None:
    """The unique in-period date for a printed `Mon D`, else None.

    The layout prints no year on its posting dates and a period can straddle a
    year boundary, so the year is the one that puts the date inside the printed
    period. An ambiguous or out-of-period token fails closed rather than
    guessing a year the document does not state.
    """
    hits = []
    for year in {start.year, end.year}:
        try:
            candidate = date(year, _EN_MONTHS[month[:3].upper()], int(day))
        except (KeyError, ValueError):
            continue
        if start <= candidate <= end:
            hits.append(candidate)
    return hits[0].isoformat() if len(hits) == 1 else None


def _en_split_dates(line: str) -> list[tuple[str, tuple[str, str] | None]]:
    """Cut one physical line into `(text, date token or None)` segments.

    A date token is the Date column — and therefore a row start — only where
    the grid can print one: at the start of the table's text, or right after a
    completed money cell, which is the Balance column of the row before it. A
    `May` inside a merchant name is not preceded by a printed balance, so it
    never splits a row.
    """
    cuts: list[tuple[int, int, tuple[str, str]]] = []
    for match in _EN_DATE_RE.finditer(line):
        before = line[:match.start()].strip()
        if before and not _EN_MONEY_TAIL_RE.search(before):
            continue
        cuts.append((match.start(), match.end(), (match.group(1), match.group(2))))

    if not cuts:
        return [(line.strip(), None)]
    segments: list[tuple[str, tuple[str, str] | None]] = []
    head = line[:cuts[0][0]].strip()
    if head:
        segments.append((head, None))
    for index, (_, end_at, token) in enumerate(cuts):
        stop = cuts[index + 1][0] if index + 1 < len(cuts) else len(line)
        segments.append((line[end_at:stop].strip(), token))
    return segments


def _en_entries(markdown: str, *, start: date, end: date) -> list[tuple[str, str, bool]]:
    """The activity table as `(text, posting date, opens a date group)`.

    This layout compresses the grid horizontally: the column header, the
    opening row and the first posting arrive on ONE physical line, and a line
    routinely carries the tail of one row and the whole of the next. So the
    Date column is consumed wherever it is printed rather than only at the
    start of a line — `_en_split_dates` decides where that is.
    """
    entries: list[tuple[str, str, bool]] = []
    current: str | None = None
    in_activity = False

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line.startswith("--- Page"):
            # A page break leaves the table; the reprinted column header
            # re-enters it, so the page's own header block never reaches the
            # grid reader.
            in_activity = False
            continue
        header = _EN_GRID_RE.search(line)
        if header:
            in_activity = True
            line = line[header.end():].strip()
            if not line:
                continue
        if not in_activity:
            continue
        if _EN_FOOTER_RE.match(line):
            continue

        for text, token in _en_split_dates(line):
            if token is not None:
                resolved = _en_date(token[0], token[1], start=start, end=end)
                if resolved is None:
                    continue
                current = resolved
            if text:
                entries.append((text, current, token is not None))
    return entries


def _en_sign_from_balances(rows: list[dict], opening: float | None) -> None:
    """Direction from the statement's own running balances.

    This layout prints a balance on every posting row and destroys the column
    the amount stood in, so the direction is read off the arithmetic the bank
    printed: the movement between two printed balances IS the signed amount.
    Where the printed magnitude and that movement disagree, or where there is
    no balance to close against, the row keeps a debit reading and the document
    then fails the platform's ledger and coverage checks — the sign is never
    invented to make the arithmetic work.
    """
    previous = opening
    for row in rows:
        row["amount"] = -row["abs_amount"]
        balance = row["balance"]
        if balance is None:
            continue
        if previous is not None:
            delta = round(balance - previous, 2)
            if abs(abs(delta) - row["abs_amount"]) <= 0.01 and delta:
                row["amount"] = delta
        previous = balance


def parse_cibc_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    """The English `CIBC Account Statement`."""
    if not detect_en(markdown).claims:
        return None

    period = _EN_PERIOD_RE.search(markdown)
    if not period:
        return None
    start_month, start_day, end_month, end_day, year_text = period.groups()
    try:
        first, last = _EN_MONTHS[start_month.upper()], _EN_MONTHS[end_month.upper()]
        end = date(int(year_text), last, int(end_day))
        # Only the closing year is printed. A period that starts in a later
        # month than it ends crossed a year boundary.
        start = date(int(year_text) - (1 if first > last else 0), first, int(start_day))
    except (KeyError, ValueError):
        return None
    if end < start:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "CIBC"
    stmt.period_start = start.isoformat()
    stmt.period_end = end.isoformat()
    stmt.currency = "CAD"

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        m = re.search(r"Account number:?\s*([0-9-]+)", line, re.IGNORECASE)
        if m:
            stmt.account_number = m.group(1)
        m = re.search(r"Opening balance on\b.*?" + _EN_SUMMARY_MONEY, line, re.IGNORECASE)
        if m:
            stmt.beginning_balance = _en_summary_amount(m.group(1))
        m = re.search(r"Closing balance on\b(.*?)=\s*" + _EN_SUMMARY_MONEY, line, re.IGNORECASE)
        if m:
            stmt.ending_balance = _en_summary_amount(m.group(2))
            # A foreign-currency account prints its code on this row, between
            # the period and the `=`. That is the ACCOUNT's currency, and this
            # is the only row that states it.
            code = re.search(r"\b([A-Z]{3})\b", m.group(1))
            if code:
                stmt.currency = code.group(1)
        # The two total rows print their direction as their own cell, so the
        # marker is consumed OUTSIDE the figure and both totals stay
        # magnitudes. Neither row prints an instance count, so both stated
        # counts stay None rather than being derived from the ledger.
        m = re.match(r"Withdrawals\s*-\s*" + _EN_SUMMARY_MONEY + r"\s*$", line, re.IGNORECASE)
        if m:
            stmt.stated_total_debits = _en_summary_amount(m.group(1))
        m = re.match(r"Deposits\s*\+\s*" + _EN_SUMMARY_MONEY + r"\s*$", line, re.IGNORECASE)
        if m:
            stmt.stated_total_credits = _en_summary_amount(m.group(1))

    rows, _ = read_grid_rows(
        _en_entries(markdown, start=start, end=end),
        pattern=_EN_MONEY_RE,
        to_amount=_en_amount,
        # `Balance forward` is the same row as `Opening balance`: the running
        # balance re-printed after a page break, with no amount beside it.
        opening_label=("OPENING BALANCE", "BALANCE FORWARD"),
        closing_label="CLOSING BALANCE",
    )
    rows = [row for row in rows if row["description"] and row["date"]]
    if not rows:
        return None

    _en_sign_from_balances(rows, stmt.beginning_balance)
    stmt.transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            direction="credit" if row["amount"] > 0 else "debit",
            running_balance=row["balance"],
        )
        for row in rows
    ]
    return stmt

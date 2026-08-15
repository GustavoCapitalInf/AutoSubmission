"""The Woodforest National Bank statement.

The document prints a `Summary of Accounts` block whose single row states the
period's whole arithmetic —

    BALANCE FORWARD - TOTAL DEBITS + TOTAL CREDITS = CLOSING BALANCE

— and then a posting grid headed `Date Credits Debits Balance Description`.

The grid is the reason this parser exists in the shape it does. Credits and
debits stand in two ADJACENT columns and the text layer destroys the column of
origin: every posting arrives as one bare magnitude between the date and the
running balance, with nothing in the row itself saying which of the two
columns it stood in. `POS DB` and `POS CR` prefixes appear in some
descriptions and not others, so the description is not an oracle either.

There are therefore two readings here, and which one runs depends on what the
intake layer could recover — never on which produces a better answer.

**The printed column, when the page gave one up.**
`ocr/native_text.py::parse_native_woodforest` reads the grid from the word
boxes and appends a block naming, for each posting, the money column the bank
printed it in. Then direction is evidence rather than inference, and the
balance chain below becomes an INDEPENDENT check of the ledger instead of its
source. The block appears only when every posting placed unambiguously; one
cell the page could not resolve and there is no block at all.

**The running balance, when it did not.** Flattened text still has the balance
AFTER each posting, and the movement between two printed balances IS the
signed amount. Where movement and printed magnitude disagree the row keeps a
debit reading and the document then fails the platform's ledger and coverage
checks: the sign is never invented to make the arithmetic close. That is the
standard `analysis/scotia.py` established and `analysis/cibc.py` applies to
the same problem.

Both readings answer to the same instruments — the summary's printed identity
and the printed balance chain — and neither publishes anything the bank did
not print. The opening balance for the walk is the summary's `BALANCE
FORWARD`, because this layout prints no opening row inside the grid.
"""
from __future__ import annotations

import re
from datetime import date

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: The printed money cell. Woodforest sets an ASCII minus on an overdrawn
#: summary figure and prints no other sign glyph.
_MONEY = r"-?[\d,]+\.\d{2}"

#: `Statement Period: March 01  - March 31, 2026`. Only the closing year is
#: printed, exactly as the CIBC layout does it.
_PERIOD_RE = re.compile(
    r"Statement\s+Period:\s*([A-Za-z]+)\s+(\d{1,2})\s*-\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
    re.IGNORECASE,
)

#: The `Summary of Accounts` column header. Its row states the period's whole
#: arithmetic and is this parser's oracle.
_SUMMARY_HEADER_RE = re.compile(
    r"ACCOUNT\s+TYPE\s+AND\s+NUMBER\s+BALANCE\s+FORWARD\s+TOTAL\s+DEBITS"
    r"\s+TOTAL\s+CREDITS\s+CLOSING\s+BALANCE",
    re.IGNORECASE,
)
#: One account's summary row: a product name ending in the account number,
#: then the four figures of the identity above.
_SUMMARY_ROW_RE = re.compile(
    r"^(?P<label>.*?(?P<number>\d{6,}))\s+(?P<forward>%s)\s+(?P<debits>%s)"
    r"\s+(?P<credits>%s)\s+(?P<closing>%s)\s*$" % ((_MONEY,) * 4)
)

#: The activity table's own printed column header. It opens the table and
#: re-opens it on every continuation page.
_GRID_RE = re.compile(
    r"Date\s+Credits\s+Debits\s+Balance\s+Description", re.IGNORECASE
)

#: The blocks printed after the grid. Each ends the activity table; none of
#: them is a posting row.
_GRID_END_RE = re.compile(
    r"^(Account\s+Summary|Daily\s+Closing\s+Balance\s+Summary|ACCOUNT\s+RECONCILIATION)\b",
    re.IGNORECASE,
)

#: What closes the `Summary of Accounts` region. The per-account sections
#: follow it, and each opens with this label above its own column header.
_SUMMARY_CLOSE_RE = re.compile(r"^Transactions\s*$", re.IGNORECASE)

#: A posting row: the Date column, then the amount cell, then the Balance
#: cell. Requiring BOTH money cells straight after the date is what keeps a
#: `03-05` printed inside a description from opening a row — a description
#: does not print two money cells in the grid's order.
_ROW_RE = re.compile(r"(?<![\d-])(\d{2})-(\d{2})\s+(%s)\s+(%s)(?![\d.,])" % (_MONEY, _MONEY))

#: The intake layer's column read (`ocr/native_text.py::parse_native_woodforest`).
#: Present only when every posting placed unambiguously in a printed column;
#: absent means the page did not read that way and this module falls back to
#: the text-order reader below, which fails closed on its own terms.
_GEOM_BEGIN_RE = re.compile(r"^WOODFOREST_GEOMETRY_BEGIN\s*$")
_GEOM_END_RE = re.compile(r"^WOODFOREST_GEOMETRY_END\s*$")
_GEOM_TX_RE = re.compile(
    r"^WOODFOREST_TX\|(?P<date>\d{2}-\d{2})\|(?P<credit>[^|]*)\|(?P<debit>[^|]*)"
    r"\|(?P<balance>[^|]*)\|(?P<description>.*)$"
)
_GEOM_SUMMARY_RE = re.compile(r"^WOODFOREST_SUMMARY\|(?P<row>.*)$")

_ACCOUNT_SUMMARY_RE = re.compile(
    r"Average\s+Balance\s*\$?\s*(%s)" % _MONEY, re.IGNORECASE
)
_DAYS_RE = re.compile(r"Number\s+of\s+Days\s+in\s+Cycle\s+(\d+)", re.IGNORECASE)

_BANK_RE = re.compile(r"WOODFOREST", re.IGNORECASE)

DETECTION_MARKERS = (
    # The institution, and the two printed column headers that make this its
    # statement rather than a document that merely names it. Another bank's
    # statement can carry `WOODFOREST` in a payee line — several in the
    # archive do — and neither header appears on any of them.
    #
    # Every marker scans the document as it arrives. No normalization is
    # declared deliberately: the registry runs each registration's normalize
    # on every document, so a whole-document copy here is per-document
    # overhead on the discovery run (RFC risk 7), and `\s+` in these patterns
    # already spans the line breaks a collapsing pass would have removed.
    required("bank_name", lambda t: bool(_BANK_RE.search(t))),
    required("summary_header", lambda t: bool(_SUMMARY_HEADER_RE.search(t))),
    required("activity_header", lambda t: bool(_GRID_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS)

_MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}


def _money(token: str) -> float | None:
    return parse_money(token)


def _row_date(month: int, day: int, *, start: date, end: date) -> str | None:
    """The printed `MM-DD` resolved against the printed period.

    The grid prints no year. A posting can fall a little outside the stated
    period — the opening deposit of a mid-month account often posts the day
    before the period starts — so the rule is not "inside the period" but
    "nearest to it": of the years the period spans, the one that puts this
    date closest to the printed interval, and only when that is unique.
    """
    best: list[tuple[int, date]] = []
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate < start:
            distance = (start - candidate).days
        elif candidate > end:
            distance = (candidate - end).days
        else:
            distance = 0
        best.append((distance, candidate))
    if not best:
        return None
    best.sort()
    if len(best) > 1 and best[0][0] == best[1][0]:
        return None
    return best[0][1].isoformat()


def _accounts(markdown: str) -> list[re.Match]:
    """Every row of the `Summary of Accounts` block.

    More than one means a multi-account document, which the single-account
    extraction schema cannot represent (L-1); the caller fails closed rather
    than publishing one account's ledger under the whole document's name.

    The region is bounded by its own printed close — the `Transactions` label
    or the activity grid's column header — and NOT by line adjacency. That
    distinction is the whole safety of the L-1 guard: a summary block whose
    rows are split by a page break prints `--- Page 2 ---` and the page's own
    header between them, and a reader that stopped at the first non-matching
    line would see one account on a two-account document and publish it. A
    guard that exists to fail closed must not fail open, so every summary row
    in the region is collected and anything else in it is skipped.
    """
    lines = [re.sub(r"\s+", " ", raw).strip() for raw in markdown.splitlines()]
    lines = [line for line in lines if line]
    found: list[re.Match] = []
    inside = False
    for line in lines:
        if not inside:
            header = _SUMMARY_HEADER_RE.search(line)
            if not header:
                continue
            inside = True
            # The header may carry its first account row on the same line.
            tail = line[header.end():].strip()
            if tail:
                match = _SUMMARY_ROW_RE.match(tail)
                if match:
                    found.append(match)
            continue
        if _SUMMARY_CLOSE_RE.match(line) or _GRID_RE.search(line):
            break
        match = _SUMMARY_ROW_RE.match(line)
        if match:
            found.append(match)
    return found


def _activity_text(markdown: str) -> str:
    """The grid's text with the page furniture removed.

    The table re-opens with its printed header on every continuation page, and
    a page break leaves it, so the address block and the statement-period line
    at the top of each page never reach the row reader.
    """
    parts: list[str] = []
    inside = False
    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if line.startswith("--- Page"):
            inside = False
            continue
        header = _GRID_RE.search(line)
        if header:
            inside = True
            line = line[header.end():].strip()
            if not line:
                continue
        if not inside:
            continue
        if _GRID_END_RE.match(line):
            inside = False
            continue
        parts.append(line)
    return " ".join(parts)


def _postings(text: str, *, start: date, end: date) -> list[dict] | None:
    """Every posting row, as `(date, magnitude, printed balance, description)`.

    Returns None when the grid yields nothing, so a document whose text layer
    does not present the columns in their printed order fails closed instead
    of publishing a partial ledger.
    """
    hits = list(_ROW_RE.finditer(text))
    if not hits:
        return None
    rows: list[dict] = []
    for index, match in enumerate(hits):
        posted = _row_date(int(match.group(1)), int(match.group(2)), start=start, end=end)
        amount = _money(match.group(3))
        balance = _money(match.group(4))
        if posted is None or amount is None or balance is None:
            return None
        stop = hits[index + 1].start() if index + 1 < len(hits) else len(text)
        rows.append(
            {
                "date": posted,
                "abs_amount": abs(amount),
                "balance": balance,
                "description": text[match.end():stop].strip(),
            }
        )
    return rows


def _geometry_block(markdown: str) -> tuple[list[str], list[str]] | None:
    """The intake layer's column read: `(summary rows, posting rows)`.

    None when the block is absent. An empty posting list is returned as None
    too — a block that carries no row is not evidence of anything.
    """
    summary: list[str] = []
    postings: list[str] = []
    inside = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if not inside:
            if _GEOM_BEGIN_RE.match(line):
                inside = True
            continue
        if _GEOM_END_RE.match(line):
            break
        found = _GEOM_SUMMARY_RE.match(line)
        if found:
            summary.append(found.group("row"))
            continue
        if _GEOM_TX_RE.match(line):
            postings.append(line)
    if not postings:
        return None
    return summary, postings


def _geometry_postings(lines: list[str], *, start: date, end: date) -> list[dict] | None:
    """Postings whose direction is the column the bank printed them in.

    This is the difference the geometry read buys, and it is worth naming
    precisely. The text-order reader below cannot see a column, so it derives
    direction from the movement between two printed balances — which means the
    balance chain is not an independent check of that ledger, it is its
    source. Here direction is the printed column and magnitude is the printed
    cell, so the chain becomes what it is supposed to be: a second, separate
    statement by the bank that either agrees or does not.

    Nothing is inferred. A row missing either cell returns None for the whole
    document rather than a ledger with a hole in it.
    """
    rows: list[dict] = []
    for line in lines:
        match = _GEOM_TX_RE.match(line)
        if match is None:
            return None
        month, day = match.group("date").split("-")
        posted = _row_date(int(month), int(day), start=start, end=end)
        balance = _money(match.group("balance"))
        credit = _money(match.group("credit")) if match.group("credit") else None
        debit = _money(match.group("debit")) if match.group("debit") else None
        if posted is None or balance is None:
            return None
        if (credit is None) == (debit is None):
            return None
        # The printed column and the printed sign are two statements by the
        # bank about the same cell, and where they contradict each other this
        # parser has no basis for preferring one. A magnitude in the Credits
        # column carrying the trailing minus this layout uses for overdrawn
        # figures says both "this increased the balance" and "this did not";
        # normalising it with `abs` would pick a winner silently. J9.6 refuses
        # the same contradiction at the summary level, for the same reason.
        printed = credit if credit is not None else debit
        if printed is not None and printed < 0:
            return None
        amount = credit if credit is not None else -abs(debit)
        rows.append({
            "date": posted,
            "abs_amount": abs(amount),
            "amount": amount,
            "direction": "credit" if credit is not None else "debit",
            "balance": balance,
            "description": match.group("description").strip(),
        })
    return rows or None


def _sign_from_balances(rows: list[dict], opening: float | None) -> None:
    """Direction from the statement's own running balances.

    Identical in argument to `cibc._en_sign_from_balances`: the movement
    between two printed balances is the signed amount. A row whose printed
    magnitude does not equal that movement keeps a debit reading, so the
    document fails the ledger checks rather than being quietly corrected.

    The ±0.01 tolerance is inherited verbatim from that function and is a
    ROUNDING allowance, not a repair budget: where it admits the movement, the
    published amount becomes the movement rather than the printed magnitude.
    Measured over this family it never does anything but agree — across all
    1,887 rows the two differ by a non-zero amount within the tolerance
    **zero times**, so every published amount here is the bank's own printed
    cell. Recorded because the convention silently prefers the delta, and that
    only stays invisible while the census stays at zero.
    """
    previous = opening
    for row in rows:
        row["amount"] = -row["abs_amount"]
        balance = row["balance"]
        if previous is not None:
            delta = round(balance - previous, 2)
            if delta and abs(abs(delta) - row["abs_amount"]) <= 0.01:
                row["amount"] = delta
        previous = balance


def parse_woodforest_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    """The Woodforest National Bank statement."""
    if not detect(markdown).claims:
        return None

    period = _PERIOD_RE.search(markdown)
    if not period:
        return None
    start_month, start_day, end_month, end_day, year_text = period.groups()
    try:
        first = _MONTHS[start_month.upper()]
        last = _MONTHS[end_month.upper()]
        end = date(int(year_text), last, int(end_day))
        # Only the closing year is printed; a period whose first month is
        # later than its last crossed a year boundary.
        start = date(int(year_text) - (1 if first > last else 0), first, int(start_day))
    except (KeyError, ValueError):
        return None
    if end < start:
        return None

    geometry = _geometry_block(markdown)

    accounts = _accounts(markdown)
    if geometry is not None:
        # The two readings of the summary region are two counts of the same
        # thing, and the guard below must see the LARGER of them.
        #
        # Consulting geometry only when the flattened count is zero was a hole
        # with a document shape behind it: the text layer breaks this summary
        # row (three archive documents print it whole and the flattened text
        # emits CLOSING BALANCE on a line of its own), and it can break ONE
        # row of two. Text then reads 1, geometry reads 2, and a rule that
        # trusts text whenever text found something publishes both accounts'
        # postings under one account's oracle. The guard exists to fail closed
        # on exactly that document.
        recovered = [
            match for match in (_SUMMARY_ROW_RE.match(row) for row in geometry[0])
            if match is not None
        ]
        if len(recovered) > len(accounts):
            accounts = recovered
    # Zero: the summary block did not read, so there is no oracle. More than
    # one: a multi-account document the single-account schema cannot carry.
    if len(accounts) != 1:
        return None
    account = accounts[0]

    forward = _money(account.group("forward"))
    debits = _money(account.group("debits"))
    credits = _money(account.group("credits"))
    closing = _money(account.group("closing"))
    if None in (forward, debits, credits, closing):
        return None

    if geometry is not None:
        rows = _geometry_postings(geometry[1], start=start, end=end)
    else:
        rows = _postings(_activity_text(markdown), start=start, end=end)
    if not rows:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Woodforest National Bank"
    stmt.account_number = account.group("number")
    stmt.account_name = account.group("label")[: -len(account.group("number"))].strip() or None
    stmt.period_start = start.isoformat()
    stmt.period_end = end.isoformat()
    stmt.currency = "USD"
    stmt.beginning_balance = forward
    stmt.ending_balance = closing
    # Both totals are printed as positive magnitudes under their own column
    # headings. Neither carries an instance count, so both stated counts stay
    # None rather than being derived from the ledger this parser publishes.
    stmt.stated_total_debits = debits
    stmt.stated_total_credits = credits

    days = _DAYS_RE.search(markdown)
    if days:
        stmt.days_in_period = int(days.group(1))
    average = _ACCOUNT_SUMMARY_RE.search(markdown)
    if average:
        stmt.stated_average_balance = _money(average.group(1))

    if geometry is None:
        _sign_from_balances(rows, forward)
    stmt.transactions = [
        Transaction(
            date=row["date"],
            description=row["description"],
            amount=row["amount"],
            # Where the bank printed a column, that column IS the direction —
            # including on a $0.00 row, which moves no balance and which a
            # sign rule can therefore only guess at. Where it did not, the
            # sign recovered from the balance chain is all there is.
            direction=row.get("direction") or ("credit" if row["amount"] > 0 else "debit"),
            running_balance=row["balance"],
        )
        for row in rows
    ]
    return stmt

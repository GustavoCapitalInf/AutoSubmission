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

What the bank does print on every row is the balance AFTER the posting. The
movement between two printed balances IS the signed amount, so direction is
read from the bank's own arithmetic and magnitude from the bank's own printed
cell. Where the two disagree the row keeps a debit reading and the document
then fails the platform's ledger and coverage checks: the sign is never
invented to make the arithmetic close. That is the standard `analysis/scotia.py`
established and `analysis/cibc.py` applies to the same problem.

The opening balance for that walk is the summary's `BALANCE FORWARD`, because
this layout prints no opening row inside the grid.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .adb import compute_average_daily_balance
from .dates import parse_date
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

_ACCOUNT_SUMMARY_RE = re.compile(
    r"Average\s+Balance\s*\$?\s*(%s)" % _MONEY, re.IGNORECASE
)
_DAYS_RE = re.compile(r"Number\s+of\s+Days\s+in\s+Cycle\s+(\d+)", re.IGNORECASE)

#: The `Daily Closing Balance Summary` block. It prints one dated balance per
#: day the account had activity — and on a mid-cycle account opening it prints
#: the OPENING day, which the statement's own printed period excludes. Read as
#: evidence only: the table is PARTIAL on most documents in this family, so it
#: is deliberately never published as `stated_daily_balances` (§UNID-A UA2).
_DAILY_SUMMARY_RE = re.compile(
    r"Daily\s+Closing\s+Balance\s+Summary(?P<body>.*?)"
    r"(?=ACCOUNT\s+RECONCILIATION|Account\s+Item\s+Images|\Z)",
    re.IGNORECASE | re.DOTALL,
)
#: One row of that table: a date and the day's closing balance. Unlike the
#: posting grid this table prints ONE money cell per date.
_DAILY_ROW_RE = re.compile(r"(?<![\d-])(\d{2})-(\d{2})\s+(%s)(?![\d.,])" % _MONEY)

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

    accounts = _accounts(markdown)
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

    _sign_from_balances(rows, forward)
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


def _daily_closing_balances(
    markdown: str, *, start: date, end: date
) -> dict[str, float]:
    """Every dated balance the `Daily Closing Balance Summary` prints.

    The grid prints no year, so each date is resolved the same way a posting
    row's is — against the period the statement states, nearest-wins.
    """
    flat = re.sub(r"\s+", " ", markdown)
    found: dict[str, float] = {}
    for block in _DAILY_SUMMARY_RE.finditer(flat):
        for row in _DAILY_ROW_RE.finditer(block.group("body")):
            posted = _row_date(
                int(row.group(1)), int(row.group(2)), start=start, end=end
            )
            balance = _money(row.group(3))
            if posted is not None and balance is not None:
                found[posted] = balance
    return found


def initialization_postings(markdown: str, stmt: Statement) -> list[Transaction]:
    """The account-opening postings this document PROVES, or an empty list.

    An account opened mid-cycle can have its funding deposit posted the day
    BEFORE the period the statement prints, while the bank still counts it in
    its own printed totals and prints a closing balance for that day. Such a
    posting is not period activity — it is what the period's first day opens
    WITH — and the platform's ADB engine, which requires every transaction to
    fall inside the period, refuses the document today.

    This function is the EVIDENCE half of the narrow exception. It answers one
    question and publishes nothing: does the document itself prove, in print,
    that its out-of-period rows opened the account? Every condition below must
    hold; any one of them failing returns an empty list and the document stays
    withheld. It is deliberately not a rule about out-of-period transactions in
    general, and there is no threshold, tolerance or per-document constant in
    it — each condition is an identity the document either satisfies exactly or
    does not.

    G1  The bank prints `BALANCE FORWARD` of zero: the account carried nothing
        into the period, which is what an account that did not yet exist does.
    G2  Every out-of-period posting is dated the day IMMEDIATELY before the
        printed period, and no posting is dated after it. A row two days early,
        or any row after the period end, is not an opening and refuses here.
    G3  Those postings are the LEADING rows of the grid and their walk from
        `BALANCE FORWARD` reproduces each printed running balance exactly, so
        the account's balance history begins with them and nothing else.
    G4  They are REQUIRED: the whole printed ledger closes on the printed
        closing balance WITH them, and does not close without them.
    G5  The bank's own `Daily Closing Balance Summary` prints a balance for
        that day equal to the last opening posting's printed balance — the
        bank's independent statement that the day belongs to this account's
        balance history.
    G6  `Number of Days in Cycle` equals the printed period's calendar length,
        so the period this evidence is measured against is the one the bank
        printed and was read correctly.
    G7  The bank's own printed `Average Balance` is reproduced EXACTLY, to the
        cent, by the platform's own daily-balance engine run over the window
        that starts on the opening day — and that run reconciles the full
        ledger. This is the strongest of the seven and the least forgeable: it
        is an independent printed figure that the parser did not use to build
        the ledger, and it moves if either the opening posting's DATE or its
        AMOUNT is wrong. Measured over the whole family, the two account
        openings reproduce it with a residual of exactly 0.00 while every
        ongoing statement in the family misses its own printed average by
        0.38–0.50 (the collected-funds convention `adb.py` already warns
        about) — so this identity is not something Woodforest statements
        satisfy by accident.

    The window in G7 is EVIDENCE ONLY. Nothing here widens the statement
    period, moves a row to a boundary day, or changes what the ADB is computed
    over: the consumer of this list folds the postings into the opening balance
    so the published ADB basis stays exactly the printed period.

    Deliberately NOT wired into `parse_woodforest_statement`. Consuming it
    requires the ADB engine to accept the folded opening, and `analysis/adb.py`
    is protected (MASTER_PLAN §4) — that half is Ocean's ruling to make. Until
    it does, the two documents this proves stay withheld, which is the
    fail-closed default the ruling asks for.
    """
    start = parse_date(stmt.period_start)
    end = parse_date(stmt.period_end)
    if start is None or end is None:
        return []

    dated = [(parse_date(txn.date), txn) for txn in stmt.transactions]
    if any(day is None for day, _ in dated):
        return []
    before = [txn for day, txn in dated if day < start]
    after = [txn for day, txn in dated if day > end]
    if not before or after:
        return []

    # G2 — immediately before the printed activity period.
    opening_day = start - timedelta(days=1)
    if any(parse_date(txn.date) != opening_day for txn in before):
        return []

    # G3 — the leading rows, walking from the printed BALANCE FORWARD.
    if stmt.transactions[: len(before)] != before:
        return []
    if stmt.beginning_balance is None or stmt.ending_balance is None:
        return []
    # G1 — nothing was carried into the period.
    if round(stmt.beginning_balance, 2) != 0:
        return []
    carry = round(stmt.beginning_balance, 2)
    for txn in before:
        carry = round(carry + txn.amount, 2)
        if txn.running_balance is None or round(txn.running_balance, 2) != carry:
            return []

    # G4 — required: the ledger closes with them and not without them.
    inside = round(
        sum(txn.amount for day, txn in dated if start <= day <= end), 2
    )
    closing = round(stmt.ending_balance, 2)
    if round(carry + inside, 2) != closing:
        return []
    if round(stmt.beginning_balance + inside, 2) == closing:
        return []

    # G5 — the bank prints that day in its own daily balance history.
    printed = _daily_closing_balances(markdown, start=start, end=end)
    if printed.get(opening_day.isoformat()) != carry:
        return []

    # G6 — the printed cycle length is the printed period.
    if stmt.days_in_period != (end - start).days + 1:
        return []

    # G7 — the bank's own printed average, reproduced exactly over the
    # opening-extended window by the platform's own engine. The probe is a
    # throwaway copy; `stmt` is not touched and nothing computed here is
    # published.
    probe = stmt.model_copy(deep=True)
    probe.period_start = opening_day.isoformat()
    probed = compute_average_daily_balance(probe)
    if not probed.ok:
        return []
    if not probed.validations.get("agrees_with_bank_stated_average"):
        return []

    return before

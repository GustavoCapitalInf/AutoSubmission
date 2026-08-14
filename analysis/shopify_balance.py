"""The Shopify Balance ledger statement.

Shopify Balance is a deposit account Shopify operates with Stripe, with the
money held at partner banks (the disclosure names Evolve Bank & Trust and
Fifth Third Bank). The archive files it under the partner bank, which is a
folder label rather than evidence: nothing in the document is a Fifth Third
statement, and the registration below is written against the layout's own
printed furniture — the `Shopify Balance` masthead, the `Statement summary`
block, and the `Transaction history` grid.

The layout is unusually well-behaved: every posting row prints both of its
dates in full (no year has to be inferred), the amount carries its own sign,
and a running balance closes every row. The document also prints its net
movement a second time, in a `Totals` row, which is registered as an
integrity check rather than consumed silently.

One structural fact drives the rest of this module: a single PDF can carry
MORE THAN ONE account. Every such document in the surveyed population carries
a second, unfunded block — zero opening, zero deposits, zero withdrawals, zero
closing, and `No transactions during this period.` — and the platform's schema
holds one account (L-1). Reading only the funded block is exact rather than
approximate *because* the other blocks are inert, so that inertness is
asserted rather than assumed: a document with two funded blocks is declined.
"""
from __future__ import annotations

import re

from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

#: One printed money cell. The layout always prints the currency symbol and
#: sets a debit's minus to the LEFT of it (`-$36.49`), which is what keeps the
#: sign attached to the figure rather than to the column.
_MONEY = r"-?\$[\d,]+\.\d{2}"
_MONEY_RE = re.compile(_MONEY)

#: `Dec 01, 2025` — the token both date columns print, always with its year.
_DATE = r"[A-Z][a-z]{2} \d{1,2}, \d{4}"
#: A posting row opens where the grid prints BOTH date columns back to back.
#: One date alone is not a row start: descriptions carry month names.
_ROW_RE = re.compile(rf"(?<!\S)({_DATE}) ({_DATE}) ")
_DATE_RE = re.compile(rf"^({_DATE})$")

#: The masthead that opens each account's own block. A statement of two
#: accounts prints it twice, once per account.
_MASTHEAD_RE = re.compile(r"^Shopify Balance$", re.MULTILINE)
#: The activity grid's printed column header. It re-prints on every page.
_GRID_HEADER_RE = re.compile(
    r"Posted Date\s+Transaction Date\s+Description\s+Amount\s+Account balance",
    re.IGNORECASE,
)
#: The row that closes the grid: the period's net movement and the closing
#: balance, printed a second time. `_totals` reads it; `totals_contradictions`
#: is what compares it with the summary block.
_TOTALS_RE = re.compile(
    rf"Totals\s+Amount\s+Account balance as of\s+\d{{2}}/\d{{2}}/\d{{4}}\s+({_MONEY})\s+({_MONEY})"
)
#: Page furniture, each printed on its own line, that carries no statement
#: content anywhere in the document.
_FOOTER_RE = re.compile(
    r"^(--- Page \d+( \(empty\))? ---|Page \d+/\d+ If you have any questions.*)$"
)
#: The grid's own repeated section heading and the period line beneath it.
#: Dropped ONLY inside the grid span: the identical period line also opens the
#: summary block, where it is the statement's period and not furniture.
_GRID_FURNITURE_RE = re.compile(
    r"^(Transaction history|[A-Z][a-z]+ \d{1,2}, \d{4} to [A-Z][a-z]+ \d{1,2}, \d{4})$"
)

_SUMMARY_PERIOD_RE = re.compile(
    r"Statement summary\s+([A-Z][a-z]+ \d{1,2}, \d{4}) to ([A-Z][a-z]+ \d{1,2}, \d{4})"
)
_STARTING_RE = re.compile(rf"Starting balance\s+({_MONEY})")
_DEPOSITS_RE = re.compile(rf"Deposits and credits\s+({_MONEY})")
_WITHDRAWALS_RE = re.compile(rf"Withdrawals and debits\s+({_MONEY})")
_ENDING_RE = re.compile(rf"Account balance as of \d{{2}}/\d{{2}}/\d{{4}}\s+({_MONEY})")
_ACCOUNT_RE = re.compile(r"Account:\s*#(\S+)")
_NO_ACTIVITY_RE = re.compile(r"No transactions during this period", re.IGNORECASE)

DETECTION_MARKERS = (
    required("bank_name", lambda t: "SHOPIFY BALANCE" in t),
    required("summary_section", lambda t: "STATEMENT SUMMARY" in t),
    required("activity_section", lambda t: "TRANSACTION HISTORY" in t),
    required("activity_header", lambda t: bool(_GRID_HEADER_RE.search(t))),
)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


detect = make_detector(DETECTION_MARKERS, detection_text)


def _long_date(token: str) -> str | None:
    """`Dec 01, 2025` -> `2025-12-01`, or None if the token is not a date."""
    match = re.fullmatch(r"([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4})", token.strip())
    if not match:
        return None
    month = _MONTHS.get(match.group(1).upper())
    if month is None:
        return None
    day, year = int(match.group(2)), int(match.group(3))
    if not 1 <= day <= 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _amount(token: str) -> float | None:
    return parse_money(token)


def _blocks(markdown: str) -> list[str]:
    """The document's account blocks, in printed order.

    Each begins at the `Shopify Balance` masthead, which is printed once per
    account and never repeated inside one account's pages.
    """
    starts = [match.start() for match in _MASTHEAD_RE.finditer(markdown)]
    if not starts:
        return []
    bounds = starts + [len(markdown)]
    return [markdown[bounds[i]:bounds[i + 1]] for i in range(len(starts))]


def _collapsed(block: str) -> list[str]:
    """The block's lines, whitespace-collapsed, furniture dropped."""
    out: list[str] = []
    for raw in block.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line and not _FOOTER_RE.match(line):
            out.append(line)
    return out


def _summary(block: str) -> dict | None:
    """The four figures and the period the summary block prints."""
    text = " ".join(_collapsed(block))
    period = _SUMMARY_PERIOD_RE.search(text)
    starting = _STARTING_RE.search(text)
    deposits = _DEPOSITS_RE.search(text)
    withdrawals = _WITHDRAWALS_RE.search(text)
    ending = _ENDING_RE.search(text)
    if not (period and starting and deposits and withdrawals and ending):
        return None
    period_start = _long_date(period.group(1))
    period_end = _long_date(period.group(2))
    if period_start is None or period_end is None:
        return None
    figures = [
        _amount(starting.group(1)),
        _amount(deposits.group(1)),
        _amount(withdrawals.group(1)),
        _amount(ending.group(1)),
    ]
    if any(value is None for value in figures):
        return None
    beginning, credits, debits, closing = figures
    return {
        "period_start": period_start,
        "period_end": period_end,
        "beginning": beginning,
        # The two total cells are printed with the direction they carry: the
        # deposits figure positive, the withdrawals figure negative. The
        # schema holds both as magnitudes.
        "credits": abs(credits),
        "debits": abs(debits),
        "ending": closing,
        "account": (_ACCOUNT_RE.search(text).group(1) if _ACCOUNT_RE.search(text) else None),
    }


def _totals(block: str) -> tuple[float, float] | None:
    """The `Totals` row: the period's net movement and the closing balance."""
    match = _TOTALS_RE.search(" ".join(_collapsed(block)))
    if not match:
        return None
    net, closing = _amount(match.group(1)), _amount(match.group(2))
    if net is None or closing is None:
        return None
    return net, closing


def _rows(block: str) -> list[Transaction] | None:
    """The block's posting rows, or None if any row is unreadable.

    The grid is read from the joined text of the block rather than line by
    line: a long description wraps, so its amount and balance are printed on
    the NEXT physical line, and only the date pair reliably says where one row
    ends and the next begins.
    """
    lines = _collapsed(block)
    start = None
    for index, line in enumerate(lines):
        if _GRID_HEADER_RE.search(line):
            start = index
            break
    if start is None:
        return None

    span: list[str] = []
    for line in lines[start:]:
        header = _GRID_HEADER_RE.search(line)
        if header:
            line = line[header.end():].strip()
            if not line:
                continue
        if line.startswith("Totals "):
            break
        if _GRID_FURNITURE_RE.match(line):
            continue
        span.append(line)
    text = " ".join(span)

    cuts = [(m.start(), m.end(), m.group(1), m.group(2)) for m in _ROW_RE.finditer(text)]
    if not cuts:
        return [] if _NO_ACTIVITY_RE.search(text) else None

    rows: list[Transaction] = []
    for index, (_, body_at, posted, _transaction_date) in enumerate(cuts):
        stop = cuts[index + 1][0] if index + 1 < len(cuts) else len(text)
        body = text[body_at:stop].strip()
        # The row's last two money cells are the Amount and Account balance
        # columns; everything before them is the Description column.
        cells = list(_MONEY_RE.finditer(body))
        if len(cells) < 2:
            return None
        amount = _amount(cells[-2].group(0))
        balance = _amount(cells[-1].group(0))
        posted_date = _long_date(posted)
        description = body[:cells[-2].start()].strip()
        if amount is None or balance is None or posted_date is None or not description:
            return None
        rows.append(
            Transaction(
                date=posted_date,
                description=description,
                amount=amount,
                direction="credit" if amount > 0 else "debit",
                running_balance=balance,
            )
        )
    return rows


def _inert(summary: dict, rows: list[Transaction] | None) -> bool:
    """Does this account block contribute nothing to any published figure?

    True only when the bank prints zero for all four of its summary figures
    and the block carries no posting row. Such a block is arithmetically
    absent: consolidating it with the funded account would change nothing,
    which is what makes publishing the funded account alone exact.
    """
    return (
        not rows
        and summary["beginning"] == 0.0
        and summary["credits"] == 0.0
        and summary["debits"] == 0.0
        and summary["ending"] == 0.0
    )


def parse_shopify_balance_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    if not detect(markdown).claims:
        return None

    blocks = _blocks(markdown)
    if not blocks:
        return None

    funded: list[tuple[dict, list[Transaction], str]] = []
    for block in blocks:
        summary = _summary(block)
        if summary is None:
            return None
        rows = _rows(block)
        if rows is None:
            return None
        if _inert(summary, rows):
            continue
        funded.append((summary, rows, block))

    # Two funded accounts on one PDF is a multi-account document, and the
    # schema holds one account (L-1). Publishing either half alone would be a
    # partial answer presented as a whole one, so the document fails closed.
    # Zero funded accounts is a whole-statement zero-activity document, a
    # class the platform rules on per parser and this registration does not
    # claim.
    if len(funded) != 1:
        return None
    summary, rows, block = funded[0]
    if not rows:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Shopify Balance"
    stmt.account_number = summary["account"]
    stmt.period_start = summary["period_start"]
    stmt.period_end = summary["period_end"]
    stmt.beginning_balance = summary["beginning"]
    stmt.ending_balance = summary["ending"]
    # The grid prints no instance count beside either total, so both stated
    # counts stay None: deriving them from the ledger would manufacture the
    # oracle the platform checks the ledger against.
    stmt.stated_total_credits = summary["credits"]
    stmt.stated_total_debits = summary["debits"]
    stmt.transactions = rows
    return stmt


def totals_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The `Totals` row against the summary block that opens the statement.

    The layout prints its net movement and its closing balance twice — once
    as `Deposits and credits` / `Withdrawals and debits` / `Account balance`
    at the top, once as the grid's closing `Totals` row. Where the two
    disagree the document contradicts itself, and no reading of it is
    authoritative.
    """
    flags: list[str] = []
    for block in _blocks(markdown):
        summary = _summary(block)
        totals = _totals(block)
        if summary is None or totals is None:
            continue
        rows = _rows(block)
        if rows is not None and _inert(summary, rows):
            continue
        net, closing = totals
        expected = round(summary["credits"] - summary["debits"], 2)
        if abs(net - expected) > 0.01:
            flags.append(
                "printed Totals net does not equal the summary block's own "
                "deposits less withdrawals"
            )
        if abs(closing - summary["ending"]) > 0.01:
            flags.append(
                "printed Totals closing balance does not equal the summary "
                "block's account balance"
            )
    return flags

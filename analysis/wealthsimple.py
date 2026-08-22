"""The Wealthsimple `Chequing monthly statement`.

Two things about this layout decide the shape of the parser.

**The minus is a printed glyph, not an ASCII hyphen.** A withdrawal is set as
`–$403.00` with U+2013 EN DASH; the family prints no ASCII minus anywhere in
its money at all. So the sign is read as an explicit class of printed
sign glyphs standing immediately before the amount's currency symbol — the
position that makes it this cell's sign rather than punctuation belonging to
the description before it. That class is `money.MINUS_GLYPHS`, the platform's
one canon; this reader spelled a private copy of it until W3 §MGD, and the
copy had drifted.

**A row is opened by its two dates and closed by its Balance cell.** The
Balance column is the row's last, so reading the row as "everything from the
dates up to and including the amount/balance pair" is what lets a long
description wrap onto a later physical line, and — *while the final row
closes* — keeps the page furniture printed after it out of that row.

That conditional is exact, and two constructions break it. If a wrapped
description happens to END in something the tail pattern reads as an
amount/balance pair, the row closes early and the rest of the description
becomes furniture. If the final row never closes, the boilerplate that
follows is accumulated into it until something completes the pair. Neither
occurs in the family — every one of the 16 documents reads with zero unread
rows — and both fail closed downstream, because a row published with the
wrong amount breaks the balance walk the summary block is checked against.
They are recorded rather than guarded so the claim is not read as
unconditional.

The document states which of its two dates is the accounting one — "Posted
date is when the transaction is processed and finalized. Use this for
accounting purposes." — so the posted date is what this parser publishes.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import PERIOD_DASH
from .money import MINUS_GLYPHS
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: The printed sign glyphs this layout can set before a money cell. U+2013 is
#: the one the family actually prints (2,140 occurrences over the 16 archive
#: documents, and no other glyph in a sign position at all); the rest of the
#: class is admitted so a sibling issue set with a true U+2212 or an ASCII
#: hyphen reads identically rather than silently losing its sign.
#:
#: Now the SHARED class rather than a private copy of it. The copy was written
#: while the shared class was being built in a parallel cell and the two could
#: not yet be proven to agree; it then drifted in exactly the way a copy does,
#: admitting U+2014 EM DASH, which the canon rules out on the archive's own
#: evidence (the one document that prints an em dash before a bare figure
#: prints it as a COLUMN PLACEHOLDER on a positive balance, so reading it as a
#: sign would flip a printed positive — W3 §MGD). A parser is now unable to
#: disagree with the grammar about what a minus is.
_SIGN_GLYPHS = MINUS_GLYPHS

#: The product line and the activity grid's own printed column header. Both
#: are required: a statement from ANOTHER bank can name Wealthsimple in a
#: payee line — three CIBC statements in the archive do — and neither of
#: these appears on any of them.
_PRODUCT_RE = re.compile(r"CHEQUING\s+MONTHLY\s+STATEMENT", re.IGNORECASE)
_GRID_RE = re.compile(
    r"DATE\s+POSTED\s+DATE\s+DESCRIPTION\s+AMOUNT\s*\(\s*CAD\s*\)\s*"
    r"BALANCE\s*\(\s*CAD\s*\)",
    re.IGNORECASE,
)

_ISSUER_RE = re.compile(r"WEALTHSIMPLE", re.IGNORECASE)

# Every marker scans the document as it arrives; no normalization is declared,
# so no whole-document copy is built per detect (RFC risk 7). The `\s+` in
# these patterns already spans the line breaks a collapsing pass would remove.
DETECTION_MARKERS = (
    required("product", lambda t: bool(_PRODUCT_RE.search(t))),
    required("issuer", lambda t: bool(_ISSUER_RE.search(t))),
    required("activity_header", lambda t: bool(_GRID_RE.search(t))),
)

detect = make_detector(DETECTION_MARKERS)

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

#: `Jun 1 - Jun 30, 2025`. Only the closing year is printed.
#:
#: The separator is `PERIOD_DASH`, not the sign class this line used to
#: borrow. A dash between two dates is punctuation: it carries no value, so
#: admitting a wide class costs nothing, while failing to match costs the
#: document its period. A dash before a FIGURE is the opposite bet. Same four
#: glyphs as before the split, so this pattern is unchanged; all 16 archive
#: documents print the ASCII hyphen here (W3 §MGD).
_PERIOD_RE = re.compile(
    r"([A-Za-z]{3})[a-z]*\s+(\d{1,2})\s*" + PERIOD_DASH
    + r"\s*([A-Za-z]{3})[a-z]*\s+(\d{1,2}),\s*(\d{4})"
)

#: `Your June summary JUN 1 BALANCE JUN 30 BALANCE $0.00 $0.00` — the two
#: labels are printed first and their two figures after, so the pairing is
#: positional. Each label carries its own date, which is what lets the parser
#: CHECK the pairing instead of assuming it.
_SUMMARY_RE = re.compile(
    r"Your\s+\w+\s+summary\s+([A-Za-z]{3})[a-z]*\s+(\d{1,2})\s+BALANCE\s+"
    r"([A-Za-z]{3})[a-z]*\s+(\d{1,2})\s+BALANCE\s+"
    r"([%s]?)\$([\d,]+\.\d{2})\s+([%s]?)\$([\d,]+\.\d{2})" % (_SIGN_GLYPHS, _SIGN_GLYPHS),
    re.IGNORECASE,
)

_ACCOUNT_RE = re.compile(r"Account\s+number:\s*(\S+)", re.IGNORECASE)

#: A row opens on the two printed dates.
_ROW_OPEN_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s*(.*)$")
#: ...and closes on its amount cell followed by its Balance cell.
_ROW_TAIL_RE = re.compile(
    r"^(?P<description>.*?)\s*(?P<sign>[%s]?)\$(?P<amount>[\d,]+\.\d{2})\s+"
    r"(?P<balance_sign>[%s]?)\$(?P<balance>[\d,]+\.\d{2})\s*$"
    % (_SIGN_GLYPHS, _SIGN_GLYPHS)
)
#: Furniture printed between the grid's rows: the page footer and the two
#: notes explaining the date columns.
_FURNITURE_RE = re.compile(
    r"^(Wealthsimple Payments Inc\.|Date is when|Posted date is when|Activity$"
    r"|DATE\s+POSTED\s+DATE)",
    re.IGNORECASE,
)


def _amount(sign: str, token: str) -> float:
    value = float(token.replace(",", ""))
    return -value if sign else value


def _postings(markdown: str) -> list[dict]:
    """Every posting row, description joined across its wrapped lines."""
    collected: list[tuple[str, str, str]] = []
    current: list[str] | None = None
    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or line.startswith("--- Page"):
            continue
        opened = _ROW_OPEN_RE.match(line)
        if opened:
            if current:
                collected.append(tuple(current))
            current = [opened.group(1), opened.group(2), opened.group(3)]
        elif current is not None:
            if _FURNITURE_RE.match(line):
                continue
            current[2] += " " + line
        # The Balance cell is the row's last column: once it is present the
        # row is complete and nothing printed after it belongs to it.
        if current is not None and _ROW_TAIL_RE.match(current[2].strip()):
            collected.append(tuple(current))
            current = None
    if current:
        collected.append(tuple(current))

    rows: list[dict] = []
    for _happened, posted, text in collected:
        tail = _ROW_TAIL_RE.match(text.strip())
        if tail is None:
            # A row whose amount and balance never arrived is not published;
            # the balance walk then fails and the document is withheld rather
            # than shipped a transaction short.
            continue
        rows.append(
            {
                "date": posted,
                "description": tail.group("description").strip(),
                "amount": _amount(tail.group("sign"), tail.group("amount")),
                "balance": _amount(tail.group("balance_sign"), tail.group("balance")),
            }
        )
    return rows


def parse_wealthsimple_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    """The Wealthsimple `Chequing monthly statement`."""
    if not detect(markdown).claims:
        return None

    flat = re.sub(r"\s+", " ", markdown)
    period = _PERIOD_RE.search(flat)
    summary = _SUMMARY_RE.search(flat)
    if not period or not summary:
        return None

    start_month, start_day, end_month, end_day, year_text = period.groups()
    try:
        first = _MONTHS[start_month.upper()]
        last = _MONTHS[end_month.upper()]
        end = date(int(year_text), last, int(end_day))
        start = date(int(year_text) - (1 if first > last else 0), first, int(start_day))
    except (KeyError, ValueError):
        return None
    if end < start:
        return None

    # The summary's two labels are printed before their two figures. Each
    # label carries its own month and day, so the pairing is verified against
    # the printed period rather than assumed from the order.
    try:
        opening_label = (_MONTHS[summary.group(1).upper()], int(summary.group(2)))
        closing_label = (_MONTHS[summary.group(3).upper()], int(summary.group(4)))
    except (KeyError, ValueError):
        return None
    if opening_label != (start.month, start.day) or closing_label != (end.month, end.day):
        return None

    rows = _postings(markdown)
    if not rows:
        # A zero-activity statement prints the grid header and no rows. It is
        # declined rather than published as an empty ledger: admitting it is
        # the platform's zero-activity rule, not this parser's to assume.
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Wealthsimple"
    stmt.account_name = "Chequing"
    stmt.period_start = start.isoformat()
    stmt.period_end = end.isoformat()
    # Not a schema default and not an assumption about the issuer: `_GRID_RE`
    # is a REQUIRED detection marker and it matches only
    # `AMOUNT (CAD) BALANCE (CAD)`, so a document that reaches this line has
    # printed `CAD` over both of its money columns. A Wealthsimple statement
    # denominated in anything else does not carry that header, is therefore not
    # claimed by this registration at all, and can never be published in the
    # wrong currency by this constant — which is what
    # `test_a_non_cad_activity_grid_is_not_claimed` holds in place.
    stmt.currency = "CAD"
    # `printed`, not `institution_default`: the code above is the required
    # grid header, so the page itself printed CAD over both money columns.
    stmt.currency_source = "printed"
    stmt.beginning_balance = _amount(summary.group(5), summary.group(6))
    stmt.ending_balance = _amount(summary.group(7), summary.group(8))

    account = _ACCOUNT_RE.search(markdown)
    if account:
        stmt.account_number = account.group(1)

    # The layout prints no period totals and no instance counts, so every
    # stated total and count stays None rather than being derived from the
    # ledger the platform checks against them.
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

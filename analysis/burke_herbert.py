"""Burke & Herbert Bank — the mainframe `ACTIVITY IN DATE ORDER` statement.

Filed in the archive under a Huntington folder label, and it is not a
Huntington statement: the issuer is Burke & Herbert Bank of Moorefield, WV.
The word "Huntington" is on these documents because the account holder's
address is in Huntington, WV and because several of the card transactions were
made at a Huntington Bank ATM — the counterparty hazard R4-3 names, arriving
this time in a folder label rather than in a marker.

The layout is a fixed-pitch mainframe print, and the PDF text layer flattens
each page's whole activity region onto ONE physical line: the banner, then
every row, then each row's continuation text, run together. There are no
columns left to read.

What survives the flattening is the thing that matters — **every row prints its
own running balance**. So the reading is checked row by row rather than in
aggregate: opening balance plus the first row's amount must equal the first
row's printed balance, and so on to the last, which must equal the printed
ENDING BALANCE. A mis-split row, a description digit read as money or a missed
row all break the chain at the point they occur. Over the surveyed population
that chain closes on 215 of 215 rows with zero breaks.

The summary adds two more oracles this platform rarely gets: the bank prints
the COUNT as well as the total of each direction (`2 DEPOSITS/CREDITS
26,245.24`), so the published ledger is checked against the bank's own row
counts in both directions, not only against its money.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from .dates import resolve_year
from .money import STRICT_UNSIGNED, pad_leading_decimal, parse_amount
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, Transaction

#: This print's money: grouped thousands, two decimals, sub-dollar amounts
#: without their leading zero (`.50-`), and the mainframe trailing minus.
_MONEY = r"(?:\d{1,3}(?:,\d{3})*)?\.\d{2}-?"
_MONEY_RE = re.compile(_MONEY)

#: A row opens on `M/DD`. The negative lookahead is what keeps it from opening
#: inside a description: those print the full `M/DD/YY`, and card rows carry
#: one (`ATM W/D 1339 02/16/26 00000264`). The lookbehind keeps it out of the
#: middle of a longer number.
_ROW_DATE_RE = re.compile(r"(?<![\d/])(\d{1,2}/\d{2})(?!/)")

#: The activity banner. The region's content is the remainder of the physical
#: line the banner sits on — see the module docstring. A page whose activity
#: wrapped differently would yield the wrong row count and be refused by the
#: bank's own printed counts rather than published.
_ACTIVITY_RE = re.compile(r"=+\s*ACTIVITY IN DATE ORDER\s*=+(.*)$")

_PERIOD_RE = re.compile(
    r"Statement Dates\s+(\d{1,2}/\d{2}/\d{2})\s+thru\s+(\d{1,2}/\d{2}/\d{2})"
)
_PREVIOUS_RE = re.compile(r"PREVIOUS BALANCE\s+(" + _MONEY + ")")
_ENDING_RE = re.compile(r"ENDING BALANCE\s+(" + _MONEY + ")")
_CREDITS_RE = re.compile(r"(\d+) DEPOSITS/CREDITS\s+(" + _MONEY + ")")
_DEBITS_RE = re.compile(r"(\d+) CHECKS/DEBITS\s+(" + _MONEY + ")")
_SERVICE_RE = re.compile(r"SERVICE CHARGE\s+(" + _MONEY + ")")
_INTEREST_RE = re.compile(r"INTEREST\s+(" + _MONEY + ")")
_DAYS_RE = re.compile(r"DAYS THIS STATEMENT PERIOD\s+(\d+)")
_ACCOUNT_RE = re.compile(r"ACCOUNT NUMBER\s+([X\d]+)")
_PRODUCT_RE = re.compile(r"^([A-Z][A-Za-z ]*?Checking)\s{2,}", re.M)

_EXACT = 0.005


def _figure(token: str) -> float | None:
    negative = token.endswith("-")
    magnitude = parse_amount(pad_leading_decimal(token.rstrip("-")), STRICT_UNSIGNED)
    if magnitude is None:
        return None
    return round(-magnitude if negative else magnitude, 2)


# ----------------------------------------------------------------- detection

def detection_text(markdown: str) -> str:
    return markdown.upper()


DETECTION_MARKERS = (
    # The issuer's own domain, printed in the page footer of its statements.
    required("issuer_domain", lambda t: "BURKEANDHERBERTBANK.COM" in t),
    # `ACTIVITY IN DATE ORDER` is a mainframe platform's banner, not this
    # bank's: LINKBANK prints it too. It is the LAYOUT half of the conjunction,
    # and on its own it identifies no issuer.
    required("activity_banner", lambda t: "ACTIVITY IN DATE ORDER" in t),
    # The summary grid of the same platform. CORROBORATING, deliberately: the
    # parse already requires every figure this marker looks for, so requiring
    # it here would only change how a Burke statement with an unreadable
    # summary is REPORTED — from `parser_declined` (we know this issuer and
    # this document needs work) to `no_parser_matched` (a bank nobody has
    # seen), which is the less useful of the two. It raises the score where it
    # fires and nothing rests on it.
    corroborating(
        "summary_grid",
        lambda t: re.search(r"PREVIOUS BALANCE\s+" + _MONEY, t) is not None
        and "DAYS THIS STATEMENT PERIOD" in t,
    ),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


# ------------------------------------------------------------------ the read

def _rows(markdown: str, start: date, end: date):
    """`(date, amount, printed_balance, description)` for every activity row.

    The amount and the balance are the first two money tokens of the row: the
    reference numbers this print puts between them and the date — cheque
    serials, card sequence numbers, the `02/16/26` of a card transaction — are
    not money-shaped, and anything that slipped through would break the chain
    `_validate` walks.
    """
    rows = []
    for line in markdown.splitlines():
        match = _ACTIVITY_RE.search(line)
        if match is None:
            continue
        body = match.group(1)
        starts = [m.start() for m in _ROW_DATE_RE.finditer(body)]
        for index, begin in enumerate(starts):
            stop = starts[index + 1] if index + 1 < len(starts) else len(body)
            chunk = body[begin:stop]
            day = _ROW_DATE_RE.match(chunk).group(1)
            tokens = _MONEY_RE.findall(chunk)
            if len(tokens) < 2:
                return None
            amount, balance = _figure(tokens[0]), _figure(tokens[1])
            # The year is not printed on a row. This platform's period crosses
            # a month boundary as a matter of course (`2/02/26 thru 3/01/26`)
            # and can cross a year one, so the year comes from the platform's
            # own rule and the result must land inside the printed period.
            month, day_of_month = (int(part) for part in day.split("/"))
            year = resolve_year(month, day_of_month, start, end)
            if amount is None or balance is None or year is None:
                return None
            try:
                posted = date(year, month, day_of_month)
            except ValueError:
                return None
            if not start <= posted <= end:
                return None
            head = chunk[len(day):chunk.index(tokens[0], len(day))]
            tail = chunk[chunk.index(tokens[1], len(day)) + len(tokens[1]):]
            description = " ".join(f"{head.strip()} {tail.strip()}".split())
            rows.append((posted, amount, balance, description))
    return rows


def _validate(
    rows, previous: float, ending: float,
    credits: tuple[int, float], debits: tuple[int, float],
) -> bool:
    """The three independent checks. All must hold.

    The summary identity (`previous + credits - debits == ending`) is NOT
    listed: it follows from the chain closing on `ending` and the two
    direction totals matching, so no document can isolate it.
    """
    if not rows:
        return False

    # 1. The chain, row by row, from the opening balance to the printed close.
    #    This is the check that no aggregate can make: it fails at the row
    #    where the reading went wrong, so a mis-split row cannot be absorbed by
    #    another row's error.
    walk = previous
    for _posted, amount, balance, _description in rows:
        walk = round(walk + amount, 2)
        if abs(walk - balance) > _EXACT:
            return False
    if abs(walk - ending) > _EXACT:
        return False

    # 2. Each direction's money, against the total the bank printed for it.
    credit_count, credit_total = credits
    debit_count, debit_total = debits
    if abs(round(sum(a for _d, a, _b, _t in rows if a > 0), 2) - credit_total) > _EXACT:
        return False
    if abs(round(-sum(a for _d, a, _b, _t in rows if a < 0), 2) - debit_total) > _EXACT:
        return False

    # 3. Each direction's ROW COUNT, against the count the bank printed for it.
    #    Independent of the money: a row split in two, or two rows merged into
    #    one, can leave both totals right and both counts wrong.
    if sum(1 for _d, a, _b, _t in rows if a > 0) != credit_count:
        return False
    if sum(1 for _d, a, _b, _t in rows if a < 0) != debit_count:
        return False
    return True


def parse_burke_herbert_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    dates = _PERIOD_RE.search(markdown)
    if dates is None:
        return None
    try:
        period = (
            datetime.strptime(dates.group(1), "%m/%d/%y").date(),
            datetime.strptime(dates.group(2), "%m/%d/%y").date(),
        )
    except ValueError:
        return None
    if period[0] > period[1]:
        return None
    previous = _PREVIOUS_RE.search(markdown)
    ending = _ENDING_RE.search(markdown)
    credits = _CREDITS_RE.search(markdown)
    debits = _DEBITS_RE.search(markdown)
    if not all((previous, ending, credits, debits)):
        return None
    start, end = period
    opening = _figure(previous.group(1))
    closing = _figure(ending.group(1))
    credit_total = _figure(credits.group(2))
    debit_total = _figure(debits.group(2))
    if None in (opening, closing, credit_total, debit_total):
        return None
    # The two summary totals are magnitudes in a named direction; the print
    # gives neither of them a sign.
    if credit_total < 0 or debit_total < 0:
        return None

    rows = _rows(markdown, start, end)
    if rows is None:
        return None
    if not _validate(
        rows, opening, closing,
        (int(credits.group(1)), credit_total),
        (int(debits.group(1)), debit_total),
    ):
        return None

    service = _SERVICE_RE.search(markdown)
    interest = _INTEREST_RE.search(markdown)
    days = _DAYS_RE.search(markdown)
    account = _ACCOUNT_RE.search(markdown)
    product = _PRODUCT_RE.search(markdown)
    return Statement(
        bank="Burke & Herbert Bank",
        account_name=product.group(1).strip() if product else None,
        account_number=account.group(1) if account else None,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        beginning_balance=opening,
        ending_balance=closing,
        days_in_period=int(days.group(1)) if days else None,
        stated_total_credits=credit_total,
        stated_total_debits=debit_total,
        stated_credit_count=int(credits.group(1)),
        stated_debit_count=int(debits.group(1)),
        stated_service_charge=_figure(service.group(1)) if service else None,
        stated_interest_paid=_figure(interest.group(1)) if interest else None,
        transactions=[
            Transaction(
                date=posted.isoformat(),
                description=description,
                amount=amount,
                direction="credit" if amount > 0 else "debit",
                running_balance=balance,
            )
            for posted, amount, balance, description in rows
        ],
    )

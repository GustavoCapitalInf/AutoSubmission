from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day_year
from .holder_name import first_page, holder_from_name, page_lines
from .money import LEADING_MINUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: Audit round 2, R2-B05 (R04 part 2): Bluevine's phone line in its page-1 letterhead, which the holder's name follows
#: on the same line ('+1 (555) 000-0000 CONTOSO TRADING LLC'); the mailing block's next line (an owner's or a
#: contact's name) is never read.
_PHONE_NAME_LINE = re.compile(r"^\+1 \(\d{3}\) \d{3}-\d{4}\s+(?P<name>\S.*)$")


def _holder_name(markdown: str) -> str | None:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name after page 1's phone line; None without it."""
    for line in page_lines(first_page(markdown)):
        match = _PHONE_NAME_LINE.match(line)
        if match is not None:
            return holder_from_name(match.group("name"))
    return None


def _money(value: str | None) -> float | None:
    return parse_amount(value, LEADING_MINUS)


def _iso(mmddyy: str) -> str:
    return iso_from_month_day_year(mmddyy, century="always")


#: Bluevine prints the same statement period two ways: the month spelled out
#: ("February 1, 2026") and the month abbreviated with its abbreviating period
#: ("Feb. 1, 2026"). Both are the SAME field of the same sentence, so this
#: reads a month NAME rather than one spelling of it.
#:
#: The vocabulary is exact - each month's full name and its abbreviation, with
#: the abbreviating period optional. It deliberately does NOT accept a
#: three-letter stem followed by anything, the looser idiom some readers in
#: this package use: inside a pattern this permissive a word that merely
#: STARTS like a month ("Janubry") would be silently read as that month, and a
#: statement period is the field every other date in the document is resolved
#: against.
_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_MONTHS: dict[str, int] = {}
for _number, _name in enumerate(_MONTH_NAMES, start=1):
    _MONTHS[_name.lower()] = _number
    _MONTHS[_name[:3].lower()] = _number
_MONTHS["sept"] = 9

#: Longest first, so "June" is preferred over "Jun" and the optional period
#: attaches to the whole name rather than truncating it.
_MONTH_TOKEN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_LONG_DATE = r"(?i:" + _MONTH_TOKEN + r")\.?\s+\d{1,2},\s+\d{4}"
_LONG_DATE_PARTS = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})")


def _long_date(token: str) -> date | None:
    """"February 1, 2026" / "Feb. 1, 2026" -> a date, else None.

    None is "this is not a date I can read", which the caller treats as a
    declined document - never as an exception. Two ways in: a month name
    outside the vocabulary, and a day the month does not have. The second is
    the reason for the `try`. `_LONG_DATE` admits a one-or-two-digit day because
    a statement period is not the place to encode a calendar, so "Feb. 30,
    2026" reaches here; `date()` raises ValueError on it, and an escaping
    ValueError is a `parser_exception` - a crash - where this document
    deserves a named decline. Terminally both are non-publishing, but only one
    of them is honest about which queue the document belongs in.
    """
    parts = _LONG_DATE_PARTS.fullmatch(token.strip())
    if not parts:
        return None
    month = _MONTHS.get(parts.group(1).lower())
    if month is None:
        return None
    try:
        return date(int(parts.group(3)), month, int(parts.group(2)))
    except ValueError:
        return None


DETECTION_MARKERS = (
    required("bank_name", lambda t: "Bluevine Inc." in t),
    required("section", lambda t: "Activity summary" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_bluevine_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = re.search(
        r"Statement Period:\s+.+?\((" + _LONG_DATE + r") - (" + _LONG_DATE + r")\)",
        markdown,
    )
    summary = re.search(
        r"Beginning Balance on \d{2}/\d{2}/\d{4}\s+\$([\d,]+\.\d{2})\s+"
        r"Deposits/credits\s+\$([\d,]+\.\d{2})\s+"
        r"Withdrawals/debits\s+\$(-?[\d,]+\.\d{2})\s+"
        r"Ending balance on \d{2}/\d{2}/\d{4}\s+\$([\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    if not period or not summary:
        return None
    period_start = _long_date(period.group(1))
    period_end = _long_date(period.group(2))
    if period_start is None or period_end is None:
        return None
    beginning, credits, debits, ending = [_money(part) for part in summary.groups()]
    if None in (beginning, credits, debits, ending):
        return None

    stmt = Statement(
        bank="Bluevine",
        holder_name=_holder_name(markdown),
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        days_in_period=(period_end - period_start).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=abs(debits or 0.0),
    )
    acct = re.search(r"Account Number:\s*([0-9]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)

    txns: list[Transaction] = []
    for m in re.finditer(r"(?m)^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+\$(-?[\d,]+\.\d{2})\s*$", markdown):
        amount = _money(m.group(3))
        if amount is None:
            return None
        txns.append(
            Transaction(
                date=_iso(m.group(1)),
                description=re.sub(r"\s+", " ", m.group(2)).strip(),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
            )
        )
    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - (credits or 0.0)) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - abs(debits or 0.0)) > 0.02:
        return None
    stmt.transactions = txns
    return stmt

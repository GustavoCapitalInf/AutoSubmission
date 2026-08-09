from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day_strict
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: The Activity Detail sections that print the `Date posted / Amount /
#: Transaction description / Reference number` column group, and the direction
#: each one is printed under in the `Deposits and Other Additions` /
#: `Checks and Other Deductions` pair of subtotal tables.
#:
#: PNC prints its own index of this list: a `Description Items Amount` table
#: giving the item count and total of every section it itemizes. This dict must
#: cover it, because the list is doing two jobs at once — it is also the list of
#: SECTION BOUNDARIES, so a section missing from it is not merely unread: it is
#: swallowed by the section printed above it, taking that section's sign and
#: gluing its own heading and column header onto the last description.
_SECTION_SIGNS = {
    "Deposits": 1,
    "ATM Deposits and Additions": 1,
    "ACH Additions": 1,
    "Other Additions": 1,
    "Fee Refunds": 1,
    "Debit Card Purchases": -1,
    "POS Purchases": -1,
    "ATM/Misc. Debit Card Transactions": -1,
    "ACH Deductions": -1,
    "Service Charges and Fees": -1,
    "Other Deductions": -1,
}
#: Cheques are itemized in their own section under a different column group
#: (`Date posted / Check number / Amount / Reference number`), so the heading is
#: a section boundary like the others but its rows are read by `_parse_checks`.
_CHECKS_HEADING = "Checks and Substitute Checks"
#: `04/21 1100 * 50.28` — date, check number, optional sequence-gap marker,
#: amount. Several column groups are printed per physical line. The Reference
#: number that follows carries no decimal point, so it cannot be read as money.
_CHECK_ROW_RE = re.compile(r"(\d{2}/\d{2})\s+(\d+)\s*(\*?)\s+(\d[\d,]*\.\d{2}|\.\d{2})")
#: A Balance Summary figure. PNC drops the leading zero on a sub-dollar amount,
#: so a balance of eighty-seven cents is printed `.87` — and a `\b` before the
#: point does not match after a space, which is how the old pattern skipped such
#: a figure and then read the NEXT one (the average ledger balance) as the
#: closing balance. The boundary here is "not preceded by a digit, comma or
#: point", which is a statement about the grid rather than about word
#: characters.
_SUMMARY_MONEY_RE = re.compile(r"(?<![\d.,])(?:\d[\d,]*)?\.\d{2}-?")
#: A heading owns its line — except that PNC prints the cheque section's
#: gap-marker footnote on the same line as its heading, so that suffix is
#: furniture rather than a different heading.
_HEADING_SUFFIX = (r"(?:\s+-\s+continued|\s+continued on next page)?"
                   r"(?:\s*\*\s*Gap in check sequence)?\s*$")
#: The two umbrella headings the Activity Detail prints over the sections of
#: each direction. They itemize nothing themselves, but they own their line and
#: they close whatever section stands above them.
_GROUP_HEADINGS = ("Deposits and Other Additions", "Checks and Other Deductions")
_SECTION_BOUNDARY = re.compile(
    r"(?im)^\s*(?:"
    + "|".join(re.escape(name) for name in
               sorted([*_SECTION_SIGNS, _CHECKS_HEADING, *_GROUP_HEADINGS],
                      key=len, reverse=True))
    + r")" + _HEADING_SUFFIX
    + r"|^\s*Detail of Services Used\b|^\s*Daily Balance\b|^\s*--- Page\b"
)


def _money(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value.startswith("."):
        value = "0" + value
    return parse_money(value)


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(r"For the Period\s+(\d{2})/(\d{2})/(\d{4})\s+to\s+(\d{2})/(\d{2})/(\d{4})", markdown)
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), int(sm), int(sd)).isoformat(),
        date(int(ey), int(em), int(ed)).isoformat(),
    )


def _summary_amounts(text: str) -> tuple[float, float, float, float] | None:
    summary = re.search(r"Balance Summary(?P<body>.*?)(?:Overdraft and Returned Item Fee Summary|Activity Detail)", text, re.DOTALL | re.IGNORECASE)
    if not summary:
        return None
    amounts = _SUMMARY_MONEY_RE.findall(summary.group("body"))
    if len(amounts) < 4:
        return None
    values = [_money(amount) for amount in amounts[:4]]
    if any(value is None for value in values):
        return None
    return values[0], abs(values[1]), abs(values[2]), values[3]  # type: ignore[return-value]


def _average_balance(text: str) -> float | None:
    m = re.search(r"Average ledger\s+Average collected\s+balance\s+([\d,]+\.\d{2})", text, re.IGNORECASE)
    if not m:
        m = re.search(r"Average ledger.*?balance\s+([\d,]+\.\d{2})", text, re.IGNORECASE | re.DOTALL)
    return abs(_money(m.group(1)) or 0.0) if m else None


def _section_chunks(markdown: str, heading: str) -> list[str]:
    activity = re.search(r"Activity Detail(?P<body>.*?)(?:Detail of Services Used During Current Period|Member FDIC|$)", markdown, re.DOTALL | re.IGNORECASE)
    if not activity:
        return []
    body = activity.group("body")
    start_re = re.compile(rf"(?im)^\s*{re.escape(heading)}" + _HEADING_SUFFIX)
    chunks: list[str] = []
    for match in start_re.finditer(body):
        start = match.end()
        end_match = _SECTION_BOUNDARY.search(body, start)
        chunks.append(body[start:end_match.start() if end_match else len(body)])
    return chunks


def _parse_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for chunk in _section_chunks(markdown, heading):
        chunk = re.sub(r"(?im)^\s*(?:Date posted|Amount|Transaction description|Reference|number)\s*$", " ", chunk)
        chunk = re.sub(r"\s+", " ", chunk).strip()
        rows = re.split(r"\s+(?=\d{2}/\d{2}\s+(?:\d[\d,]*\.\d{2}|\.\d{2})\s)", chunk)
        for row in rows:
            m = re.match(r"^(\d{2}/\d{2})\s+(\d[\d,]*\.\d{2}|\.\d{2})\s+(.+?)\s*$", row)
            if not m:
                continue
            txn_date = iso_from_month_day_strict(m.group(1), year)
            amount = _money(m.group(2))
            if txn_date is None or amount is None:
                continue
            signed = round(abs(amount) * sign, 2)
            txns.append(Transaction(
                date=txn_date,
                description=re.sub(r"\s+", " ", m.group(3)).strip(),
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=None,
            ))
    return txns


def _parse_checks(markdown: str, *, year: int) -> list[Transaction]:
    """The `Checks and Substitute Checks` section, which prints its own column
    group: `Date posted | Check number | Amount | Reference number`."""
    txns: list[Transaction] = []
    for chunk in _section_chunks(markdown, _CHECKS_HEADING):
        chunk = re.sub(
            r"(?im)^\s*(?:Date posted|Date|Check number|Check|Amount|Transaction|Reference|number|posted)\s*$",
            " ", chunk)
        chunk = re.sub(r"\s+", " ", chunk).strip()
        for mmdd, number, marker, amount in _CHECK_ROW_RE.findall(chunk):
            txn_date = iso_from_month_day_strict(mmdd, year)
            value = _money(amount)
            if txn_date is None or value is None:
                continue
            txns.append(Transaction(
                date=txn_date,
                description=f"Check {number}{marker}",
                amount=round(-abs(value), 2),
                direction="debit",
                running_balance=None,
            ))
    return txns


DETECTION_MARKERS = (
    required("bank_name", lambda t: "PNC Bank" in t),
    required("product", lambda t: "Business Checking" in t),
    required("section", lambda t: "Balance Summary" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_pnc_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _summary_amounts(markdown)
    if period is None or summary is None:
        return None
    year = int(period[1][:4])
    beginning, credits, debits, ending = summary
    stmt = Statement(
        bank="PNC Bank",
        account_name="Business Checking",
        period_start=period[0],
        period_end=period[1],
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_average_balance=_average_balance(markdown),
    )
    acct = re.search(r"Primary Account Number:\s*([X0-9-]+)", markdown, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)

    txns: list[Transaction] = []
    for heading, sign in _SECTION_SIGNS.items():
        txns.extend(_parse_section(markdown, heading, year=year, sign=sign))
    txns.extend(_parse_checks(markdown, year=year))
    if not txns:
        return None
    stmt.transactions = txns
    return stmt

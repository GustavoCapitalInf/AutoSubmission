from __future__ import annotations

import re
from datetime import date

from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace


_MONEY_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?: \d{3})+|\d+)\.\d{2}(?!\d)")
_ROW_RE = re.compile(r"^\s*([A-Z]{3})\s+(\d{1,2})\s+([A-Z]{2,4})\s+(.*)")
_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def _money(value: str) -> float:
    return float(value.replace(" ", ""))


def _period(markdown: str) -> tuple[str, str, int] | None:
    m = re.search(
        r"From\s+([A-Za-z]+)\s+(\d{1,2})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
        re.IGNORECASE,
    )
    if not m:
        return None
    months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    start_month, start_day, end_month, end_day, year = m.groups()
    y = int(year)
    start = date(y, months[start_month.lower()], int(start_day))
    end = date(y, months[end_month.lower()], int(end_day))
    return start.isoformat(), end.isoformat(), y


def _account_number(markdown: str) -> str | None:
    m = re.search(r"\b(SJ\s+\d{3}-\d{5}-\d)\b", markdown)
    return compact_whitespace(m.group(1)) if m else None


def _beginning_balance(markdown: str) -> float | None:
    m = re.search(r"Balance forward\s+([\d ]+\.\d{2})", markdown)
    return _money(m.group(1)) if m else None


def _transaction_blocks(markdown: str) -> list[list[str]]:
    rows: list[list[str]] = []
    current: list[str] | None = None
    for line in markdown.splitlines():
        if _ROW_RE.match(line):
            if current:
                rows.append(current)
            current = [line]
            continue
        if current is None:
            continue
        stripped = line.strip()
        if (
            stripped.startswith(("PCA", "SHR", "Notify", "--- Page"))
            or "STATEMENT OF ACCOUNT" in line
            or ("Page " in line and " of " in line)
        ):
            rows.append(current)
            current = None
            continue
        current.append(line)
    if current:
        rows.append(current)
    return rows


def _signed_amount(raw_amount: float, raw_balance: float, previous_balance: float) -> tuple[float, float] | None:
    for amount in (raw_amount, -raw_amount):
        for balance in (raw_balance, -raw_balance):
            if abs(round(previous_balance + amount, 2) - balance) <= 0.01:
                return round(amount, 2), round(balance, 2)
    return None


def _description(block_text: str, first_line: str, amount_token: str) -> str:
    m = _ROW_RE.match(first_line)
    desc = m.group(4) if m else first_line
    if len(block_text.splitlines()) > 1:
        desc = block_text[block_text.find(desc):]
    amount_idx = desc.rfind(amount_token)
    if amount_idx > 0:
        desc = desc[:amount_idx]
    return compact_whitespace(desc)


def _transactions(markdown: str, *, year: int, beginning_balance: float) -> list[Transaction] | None:
    txns: list[Transaction] = []
    previous = beginning_balance
    for block in _transaction_blocks(markdown):
        first = block[0]
        row = _ROW_RE.match(first)
        if not row:
            return None
        month_name, day, code, _ = row.groups()
        month = _MONTHS.get(month_name.upper())
        if month is None:
            return None
        text = "\n".join(block)
        money = _MONEY_RE.findall(text)
        if len(money) < 2:
            return None
        raw_amount = _money(money[-2])
        raw_balance = _money(money[-1])
        signed = _signed_amount(raw_amount, raw_balance, previous)
        if signed is None:
            return None
        amount, balance = signed
        desc = _description(text, first, money[-2])
        txns.append(
            Transaction(
                date=date(year, month, int(day)).isoformat(),
                description=f"{code} {desc}".strip(),
                amount=amount,
                direction="credit" if amount >= 0 else "debit",
                running_balance=balance,
            )
        )
        previous = balance
    return txns


#: The product line that heads the ledger, with the denomination the caisse
#: prints in front of the product name: `PCA   USD DESJARDINS CORPORATE
#: BUILD-UP ACCOUNT`. The product name is what detection requires; the code in
#: front of it is what the account is denominated in, and it is the only
#: currency word on the page — the column headers print bare `Charges`,
#: `Withdrawal`, `Deposit`, `Balance` with no unit at all.
#:
#: `_ADMISSIBLE_CURRENCIES` is a closed set on purpose. The token immediately
#: before the product name is a three-letter code either way (`PCA` is the
#: account-type mark that precedes it in the same header row), so a matcher
#: that published whatever three letters it captured would publish `PCA` as a
#: currency the first time the caisse set that row without a denomination. The
#: same class of defect is live elsewhere in the archive: a scanned deposit
#: slip OCRs as `Af 'CURRENCY KLR Enterpriees`, and a labelled-code reader
#: without a closed set would publish `KLR`.
#:
#: The set's cost is recorded rather than hidden: a REAL but unattested ISO
#: code (a EUR issue of this product) is not admitted, falls into the same
#: "prints nothing" branch as `PCA`, and publishes the USD default beside a
#: page that says otherwise. That residual is named in W3 §CUR6; the rule for
#: closing it is that a newly attested code extends THIS SET, never the
#: fallback.
_PRODUCT_CURRENCY_RE = re.compile(
    r"\b([A-Z]{3})\s+DESJARDINS CORPORATE BUILD-UP ACCOUNT\b")
_ADMISSIBLE_CURRENCIES = frozenset({"CAD", "USD"})


def _printed_currency(markdown: str) -> str | None:
    """The denomination printed in front of the product name, or None.

    None where the layout prints no admissible code, and None where it prints
    more than one: a document stating two denominations does not state one.
    """
    found = {
        code
        for code in _PRODUCT_CURRENCY_RE.findall(markdown.upper())
        if code in _ADMISSIBLE_CURRENCIES
    }
    if len(found) != 1:
        return None
    return found.pop()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "CAISSE DESJARDINS" in t),
    required("product", lambda t: "DESJARDINS CORPORATE BUILD-UP ACCOUNT" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_desjardins_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    account = _account_number(markdown)
    beginning = _beginning_balance(markdown)
    if period is None or account is None or beginning is None:
        return None
    start, end, year = period
    txns = _transactions(markdown, year=year, beginning_balance=beginning)
    if not txns:
        return None
    ending = txns[-1].running_balance
    if ending is None:
        return None
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    printed_currency = _printed_currency(markdown)
    return Statement(
        bank="Desjardins",
        account_name="USD Desjardins Corporate Build-Up Account",
        account_number=account,
        period_start=start,
        period_end=end,
        days_in_period=(end_date - start_date).days + 1,
        beginning_balance=beginning,
        ending_balance=ending,
        # From the product line, not from the reader's expectation of it. Every
        # archive document of this layout prints `USD`, so this publishes the
        # same value it always did — but a Canadian-dollar issue of the same
        # product would now publish CAD instead of being labelled USD by a
        # constant. Where no admissible code is printed the default stands.
        currency=printed_currency or "USD",
        # `schema_default` and NOT `institution_default` on the fallback arm:
        # this caisse is Canadian, so "USD because Desjardins" is a claim no
        # one can make. Where the product line prints no admissible code the
        # honest statement is that nothing was read and the field's own
        # default `"USD"` is standing — which is what §CUR6's named residual
        # is, now visible in the payload instead of only in this comment.
        currency_source="product" if printed_currency else "schema_default",
        transactions=txns,
    )

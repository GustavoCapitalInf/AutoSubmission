"""The Zions Bancorporation `Statement of Accounts` layout.

Zions Bancorporation, N.A. trades under a different name in each of its
markets and prints the same mainframe statement under all of them. The
archive holds two: one carrying `WWW.NSBANK.COM` (Nevada State Bank) and one
carrying `WWW.AMEGYBANK.COM` and `Amegy Bank of Texas`. Neither trade name is
what identifies the document — registering on either would leave the other
unclaimed, which is the mistake `rbc_french` made with its two products. What
every one of them prints is the corporate footer `A division of Zions
Bancorporation, N.A.` together with the layout's own furniture, and that is
what this registration is written against.

The layout is generous with oracles and this module uses all of them:

* a summary grid that prints, per account, `Previous Balance`,
  `Deposits/Credits`, `Withdrawals/Debits`, `Checks Processed` and
  `Ending Balance` as amounts, with an INSTANCE COUNT above three of them;
* two posting sections, `DEPOSITS/CREDITS` and `CHARGES/DEBITS`, whose rows
  print the sign the section implies;
* a `DAILY BALANCE` block of the bank's own end-of-day balances;
* `Number Of Days This Statement Period`, which is checked against the period
  the statement's two dates describe.

Two things are deliberately NOT published. `CHECKS PROCESSED` is a register of
cheques that have already been posted in `CHARGES/DEBITS`; reading it would
publish every cheque twice. And `Total Items` under `ACTIVITY COUNT` is not
the transaction count — measured across the family it exceeds the summary's
own counts by between 0 and 12 — so it is not used as an oracle.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_unique_in_period
from .money import parse_money
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction

_MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "MAY": 5, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11,
    "DECEMBER": 12,
}

#: A printed amount, with the trailing minus this layout uses for money out.
_AMOUNT = r"[\d,]+\.\d{2}-?"
#: One posting row: the Posting and Effective date columns, then the Amount
#: column, then the Description column.
_ROW_RE = re.compile(
    rf"(?<![\d/])(\d{{2}})/(\d{{2}})\s+(\d{{2}})/(\d{{2}})\s+({_AMOUNT})(?![\d.,])"
)
#: One `DAILY BALANCE` cell: a date and the bank's end-of-day balance.
_DAILY_RE = re.compile(rf"(?<![\d/])(\d{{2}})/(\d{{2}})\s+\$({_AMOUNT})(?![\d.,])")

#: The dotted rule the layout draws before every section title.
_SECTION_RE = re.compile(
    r"\.{6,}\s*(DEPOSITS/CREDITS|CHARGES/DEBITS|CHECKS PROCESSED|ACTIVITY COUNT|"
    r"DAILY BALANCE|INTEREST|AGGREGATE OVERDRAFT AND RETURNED ITEM FEES)\b"
)
#: One account's summary grid. The product name is read but never matched
#: against a list: this bank renames its products mid-archive (`BUSINESS
#: GROWTH CHECKING` became `BUSINESS ELEVATE CHECKING`), so what identifies
#: the grid is the printed column legend.
_BLOCK_RE = re.compile(
    r"(?P<product>[A-Z][A-Z &'./-]*[A-Z])\s+(?P<account>\d{8,17})\s+\d{4}\s+(?:a\s+)?"
    r"Previous Balance\s+Deposits/Credits\s+Withdrawals/Debits\s+"
    r"(?P<checks>Checks Processed\s+)?Ending Balance"
)
_COUNT_AMOUNT_RE = re.compile(
    rf"Count:\s*(?P<counts>(?:\d+\s+)*\d+)?\s*Amount:\s*"
    rf"(?P<amounts>(?:{_AMOUNT}\s+)*{_AMOUNT})"
)
_PERIOD_RE = re.compile(
    r"This Statement:\s*([A-Za-z]+ \d{1,2}, \d{4})\s*Last Statement:\s*([A-Za-z]+ \d{1,2}, \d{4})"
)
_DAYS_RE = re.compile(r"Number Of Days This Statement Period\s+(\d+)")
_NO_ACTIVITY_RE = re.compile(r"There were no transactions this period", re.IGNORECASE)
_TOTAL_ROW_RE = re.compile(rf"Total\s+\$({_AMOUNT})")
_SUMMARY_HEADER_RE = re.compile(r"SUMMARY OF ACCOUNT BALANCES?")

DETECTION_MARKERS = (
    required("issuer", lambda t: "ZIONS BANCORPORATION" in t),
    required("statement_title", lambda t: "STATEMENT OF ACCOUNTS" in t),
    required("balance_summary", lambda t: bool(_SUMMARY_HEADER_RE.search(t))),
    required(
        "activity_columns",
        lambda t: "PREVIOUS BALANCE" in t
        and "DEPOSITS/CREDITS" in t
        and "WITHDRAWALS/DEBITS" in t,
    ),
)


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


detect = make_detector(DETECTION_MARKERS, detection_text)


def _amount(token: str) -> float | None:
    return parse_money(token)


def _long_date(token: str) -> date | None:
    match = re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", token.strip())
    if not match:
        return None
    month = _MONTHS.get(match.group(1).upper())
    if month is None:
        return None
    try:
        return date(int(match.group(3)), month, int(match.group(2)))
    except ValueError:
        return None


def _flatten(markdown: str) -> str:
    return " ".join(
        re.sub(r"\s+", " ", line).strip()
        for line in markdown.splitlines()
        if line.strip()
    )


def _period(text: str) -> tuple[date, date] | None:
    """The period the statement's two printed dates describe.

    `Last Statement` is the closing date of the PREVIOUS statement, so this
    period opens the day after it. `Number Of Days This Statement Period` is
    the bank's own count of that span and is checked against it rather than
    trusted separately.
    """
    match = _PERIOD_RE.search(text)
    if not match:
        return None
    end = _long_date(match.group(1))
    last = _long_date(match.group(2))
    if end is None or last is None:
        return None
    start = last + timedelta(days=1)
    return (start, end) if start <= end else None


def _sections(block: str) -> dict[str, str]:
    """The block's printed sections, by title."""
    marks = [(m.start(), m.end(), m.group(1)) for m in _SECTION_RE.finditer(block)]
    found: dict[str, str] = {}
    for index, (_, body_at, title) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(block)
        found.setdefault(title, block[body_at:stop])
    return found


def _blocks(text: str) -> list[dict]:
    """Each account's summary grid and the sections printed beneath it."""
    heads = list(_BLOCK_RE.finditer(text))
    out: list[dict] = []
    for index, head in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        body = text[head.end():stop]
        grid = _COUNT_AMOUNT_RE.match(body.strip()) or _COUNT_AMOUNT_RE.search(body)
        if grid is None:
            return []
        counts = [int(value) for value in (grid.group("counts") or "").split()]
        amounts = [_amount(value) for value in grid.group("amounts").split()]
        if any(value is None for value in amounts):
            return []
        # The grid has one amount per printed column and one count per column
        # that can hold instances -- every column but the two balances.
        columns = 5 if head.group("checks") else 4
        if len(amounts) != columns or len(counts) != columns - 2:
            return []
        out.append(
            {
                "product": head.group("product").strip(),
                "account": head.group("account"),
                "has_checks_column": bool(head.group("checks")),
                "counts": counts,
                "amounts": amounts,
                "sections": _sections(body),
            }
        )
    return out


def _rows(block: dict, *, start: date, end: date) -> list[Transaction] | None:
    """The block's posting rows, or None if any row is unreadable.

    `CHECKS PROCESSED` is not read: it is a register of cheques already posted
    in `CHARGES/DEBITS`, and reading it would publish each of them twice.
    """
    rows: list[Transaction] = []
    for title, outgoing in (("DEPOSITS/CREDITS", False), ("CHARGES/DEBITS", True)):
        body = block["sections"].get(title)
        if body is None:
            return None
        if _NO_ACTIVITY_RE.search(body) and not _ROW_RE.search(body):
            continue
        cuts = list(_ROW_RE.finditer(body))
        for index, cut in enumerate(cuts):
            stop = cuts[index + 1].start() if index + 1 < len(cuts) else len(body)
            amount = _amount(cut.group(5))
            posting = iso_unique_in_period(int(cut.group(1)), int(cut.group(2)), start=start, end=end)
            description = re.sub(r"\s+", " ", body[cut.end():stop]).strip()
            if amount is None or posting is None or not description:
                return None
            # The section IS the direction column, and the row prints the sign
            # that column implies. Where the two disagree the row has not been
            # read correctly, so the document fails closed instead of picking
            # one of them.
            if outgoing != (amount < 0):
                return None
            rows.append(
                Transaction(
                    date=posting,
                    description=description,
                    amount=amount,
                    direction="debit" if outgoing else "credit",
                )
            )
    rows.sort(key=lambda row: row.date)
    return rows


def _daily_balances(block: dict, *, start: date, end: date) -> list[StatementDailyBalance]:
    """The bank's own end-of-day balances.

    The block opens on the day the period opens, which the layout prints even
    when nothing posted that day, and lists only the days the balance moved.
    """
    body = block["sections"].get("DAILY BALANCE")
    if not body:
        return []
    out: list[StatementDailyBalance] = []
    for match in _DAILY_RE.finditer(body):
        balance = _amount(match.group(3))
        when = iso_unique_in_period(int(match.group(1)), int(match.group(2)), start=start, end=end)
        if balance is None or when is None:
            continue
        out.append(StatementDailyBalance(date=when, balance=balance))
    out.sort(key=lambda item: item.date)
    return out


def _inert(block: dict, rows: list[Transaction]) -> bool:
    """Does this account block contribute nothing to any published figure?"""
    return not rows and all(value == 0.0 for value in block["amounts"])


def parse_zions_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    if not detect(markdown).claims:
        return None

    text = _flatten(markdown)
    period = _period(text)
    if period is None:
        return None
    start, end = period

    blocks = _blocks(text)
    if not blocks:
        return None

    funded = []
    for block in blocks:
        rows = _rows(block, start=start, end=end)
        if rows is None:
            return None
        if not _inert(block, rows):
            funded.append((block, rows))

    # More than one funded account on one PDF is a multi-account document and
    # the schema holds one account (L-1). An account block printing zero for
    # every column and carrying no row is arithmetically absent, so a funded
    # account published beside such blocks is exact rather than partial.
    if len(funded) != 1:
        return None
    block, rows = funded[0]
    if not rows:
        return None

    amounts = block["amounts"]
    if block["has_checks_column"]:
        beginning, credits, debits, checks, ending = amounts
        credit_count, debit_count, check_count = block["counts"]
    else:
        beginning, credits, debits, ending = amounts
        checks, check_count = 0.0, 0
        credit_count, debit_count = block["counts"]

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Zions Bancorporation"
    stmt.account_name = block["product"]
    stmt.account_number = block["account"]
    stmt.period_start = start.isoformat()
    stmt.period_end = end.isoformat()
    stmt.beginning_balance = beginning
    stmt.ending_balance = ending
    stmt.stated_total_credits = abs(credits)
    stmt.stated_credit_count = credit_count
    # The layout splits money out across two printed columns, so the debit
    # total is both of them and the debit COUNT must cover the same scope --
    # a count narrower than its own total is what W3 §FIXUPS-1 corrected on
    # `first_community`.
    #
    # Rounded because this is the one published figure this parser ADDS rather
    # than reads: binary floating point turns 175,923.68 + 43,557.86 into
    # 219481.53999999998, which reconciles fine and then serializes as an
    # artifact nobody printed. Every other summing parser rounds at the same
    # seam (`analysis/bofa.py:417`, `analysis/chase.py:449`).
    stmt.stated_total_debits = round(abs(debits) + abs(checks), 2)
    stmt.stated_debit_count = debit_count + check_count

    days = _DAYS_RE.search(text)
    if days is None:
        return None
    printed_days = int(days.group(1))
    # The bank counts the period's days itself. If that count disagrees with
    # the span its own two statement dates describe, the period has not been
    # read correctly and every dated figure below it is suspect.
    if printed_days != (end - start).days + 1:
        return None
    stmt.days_in_period = printed_days

    stmt.stated_daily_balances = _daily_balances(block, start=start, end=end)
    stmt.transactions = rows
    return stmt


def balance_summary_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The balance-summary table against the account grid it precedes.

    A statement of several accounts opens with `SUMMARY OF ACCOUNT BALANCES`
    listing each account's closing balance and a `Total`. Where that total
    does not equal the published closing balance, the accounts this parser
    treated as inert were not inert, and the published figure is a part
    presented as the whole.
    """
    if stmt.ending_balance is None:
        return []
    text = _flatten(markdown)
    match = _TOTAL_ROW_RE.search(text)
    if not match:
        return []
    total = _amount(match.group(1))
    if total is None or abs(total - stmt.ending_balance) <= 0.01:
        return []
    return [
        "the printed SUMMARY OF ACCOUNT BALANCES total does not equal the "
        "published closing balance"
    ]

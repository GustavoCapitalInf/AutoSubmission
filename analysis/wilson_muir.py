"""Wilson & Muir — the `SMALL BUSINESS PACKAGE SUMMARY` layout.

The summary strip is a TABLE, not a sentence
--------------------------------------------
The platform prints, under its own `Category Number Amount` heading, a strip
bounded by two dated balance rows::

    Balance Forward From 12/31/25  64,389.89
    Deposits                    8   99,844.00+
    Debits                      7   17,275.00
    Automatic Teller Withdrawals 1     300.00
    Automatic Withdrawals      74  182,067.68
    Automatic Deposits         11   60,528.14+
    Card Activity               9    1,151.69
    Miscellaneous Fees          1       10.00
    Ending Balance On 01/30/26  23,957.66

Three facts about that strip are load-bearing and were previously memorized
instead of read (§DECLINESD D2, and the same shape §DECLB found in two other
banks):

* **The category list is open.** `Automatic Teller Withdrawals` and
  `Miscellaneous Fees` are printed by this same account in other months. A
  fixed chain of six named categories cannot see them, and — because the
  chain welded the categories together with a whitespace run — one
  unmemorized row standing between two memorized ones refused the whole
  document on its summary.
* **`+` is the platform's own direction marker.** Every credit category
  carries it and no debit category does, so direction is read off the
  printing rather than inferred from a category NAME this reader would
  otherwise have to know.
* **A category with no items prints no count.** `Debits 0.00` is the
  platform saying "none", the same convention `core_processor_sectioned.
  _counts` names; requiring a count refused three of this account's
  statements on a row that says zero.

What keeps an unmemorized category safe to read is the strip's own arithmetic:
`Balance Forward + Σcredits − Σdebits = Ending Balance`, checked to the cent
before anything is published. A category read on the wrong side of that
identity moves it by twice its amount, so the identity is what the `+` marker
is trusted against. Two further gates follow it — the ledger's credit sum and
debit sum must each equal the strip's — so a strip this reader understood and
a ledger it did not cannot both pass.

Nothing in the strip may go unread: whatever the category pattern does not
consume between the two balance rows is a row shape this module has not seen,
and the document is declined rather than published with it dropped.

The ledger's sections end where the NEXT one begins
---------------------------------------------------
`CHECKS AND OTHER DEBITS` is printed only when the period contains cheques.
Three of this account's statements print none, and closing the electronic-debit
section at that heading made the section empty on exactly those documents — the
whole debit ledger read as zero while the strip said six figures. The section
now ends at whichever of the family's own following headings the document
actually prints.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_month_day_year
from .money import STRICT_EITHER_MINUS_OR_PLUS, parse_amount
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import section_between


def _money(value: str | None) -> float | None:
    return parse_amount(value, STRICT_EITHER_MINUS_OR_PLUS)


def _parse_mmddyy(raw: str) -> str:
    return iso_from_month_day_year(raw, century="always")


def _dated_amount_rows(section: str, sign: int) -> list[Transaction]:
    body = re.sub(r"\s+", " ", section)
    rows: list[Transaction] = []
    for part in re.split(r"(?=\d{2}/\d{2}/\d{2}\s+)", body):
        m = re.match(r"(\d{2}/\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s|$)", part)
        if not m:
            continue
        date_raw, desc, amount_raw = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            return []
        rows.append(
            Transaction(
                date=_parse_mmddyy(date_raw),
                description=re.sub(r"\s+", " ", desc).strip(),
                amount=round(abs(amount) * sign, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return rows


def _check_rows(section: str) -> list[Transaction]:
    body = re.sub(r"\s+", " ", section)
    rows: list[Transaction] = []
    for m in re.finditer(r"(\d{2}/\d{2}/\d{2})\s+(?:(\d+\*?)\s+)?([\d,]+\.\d{2})", body):
        date_raw, check_no, amount_raw = m.groups()
        amount = _money(amount_raw)
        if amount is None:
            return []
        desc = "Check"
        if check_no:
            desc = f"Check {check_no.rstrip('*')}"
        rows.append(
            Transaction(
                date=_parse_mmddyy(date_raw),
                description=desc,
                amount=round(-abs(amount), 2),
                direction="debit",
            )
        )
    return rows


DETECTION_MARKERS = (
    required("bank_name", lambda t: "WILSON & MUIR" in t),
    required("section", lambda t: "SMALL BUSINESS PACKAGE SUMMARY" in t),
)

detect = make_detector(DETECTION_MARKERS)

#: The account this statement is for, printed in its own header line above the
#: summary strip. Read separately from the strip because it is a different
#: printing: welding the two into one pattern made a header that moved refuse a
#: strip that had not.
_HEADER_RE = re.compile(
    r"Statement Date:\s+(\d{2}/\d{2}/\d{4})\s+Account No\.:\s+#?(\d+)", re.IGNORECASE
)

#: The summary strip: its two dated balance rows and everything between them.
#: The bounds are the platform's own, and they are what keeps the category
#: pattern below off the ledger — every section of this statement prints
#: `<text> <amount>` pairs, and only inside this strip are they categories.
_STRIP_RE = re.compile(
    r"Balance Forward From\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})"
    r"(.*?)"
    r"Ending Balance On\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})",
    re.IGNORECASE | re.DOTALL,
)

#: One category row of the strip: a printed name, the item count the platform
#: omits when there were none, the amount, and the `+` that marks a credit.
#: The name class is deliberately narrow — letters and the punctuation this
#: platform prints inside a category name — so a stray figure cannot be read as
#: one, and it is lazy so that the count is preferred over the tail of the name.
_CATEGORY_RE = re.compile(
    r"([A-Za-z][A-Za-z ()&/'.-]*?)\s+(?:([0-9]{1,4})\s+)?([\d,]+\.\d{2})(\+?)"
)

#: The period's ledger average, printed after the closing balance beside the
#: platform's item statistics. Evidence, not a gate.
_AVERAGE_RE = re.compile(r"Average Balance \(Ledger\)\s+([\d,]+\.\d{2})\+?", re.IGNORECASE)

#: What follows the electronic-debit section. `CHECKS AND OTHER DEBITS` is
#: printed only when the period contains cheques, so the alternation is what
#: makes the boundary the document's own rather than this reader's assumption.
_AFTER_ELECTRONIC = r"(?:CHECKS AND OTHER DEBITS|DAILY BALANCE SUMMARY)"


class _Strip:
    """The summary strip, read as the table it is printed as."""

    __slots__ = ("beginning_date", "beginning", "ending_date", "ending",
                 "credits", "debits", "credit_count", "debit_count")

    def __init__(self, **fields) -> None:
        for name, value in fields.items():
            setattr(self, name, value)


def _summary_strip(markdown: str) -> _Strip | None:
    """Every category the strip prints, totalled by the printed `+` marker.

    None — rather than a partial reading — whenever the strip holds anything
    this pattern did not consume, or whenever the platform's own identity does
    not close over what it did.
    """
    match = _STRIP_RE.search(markdown)
    if match is None:
        return None
    beginning = _money(match.group(2))
    ending = _money(match.group(5))
    if beginning is None or ending is None:
        return None

    body = re.sub(r"\s+", " ", match.group(3)).strip()
    categories = _CATEGORY_RE.findall(body)
    if _CATEGORY_RE.sub("", body).strip():
        # A row shape this reader has not seen. Declining is the honest answer:
        # a category silently dropped here would be a category missing from the
        # totals the ledger is then gated against.
        return None

    credits_ = debits = 0.0
    credit_count = debit_count = 0
    for _label, count, amount_raw, marker in categories:
        amount = _money(amount_raw)
        if amount is None:
            return None
        if marker == "+":
            credits_ += amount
            credit_count += int(count) if count else 0
        else:
            debits += amount
            debit_count += int(count) if count else 0
    credits_, debits = round(credits_, 2), round(debits, 2)

    # The strip's own arithmetic, which is what makes an unmemorized category
    # safe to read: a row taken on the wrong side of it moves the identity by
    # twice its amount.
    if abs(beginning + credits_ - debits - ending) > 0.005:
        return None
    return _Strip(
        beginning_date=match.group(1), beginning=beginning,
        ending_date=match.group(4), ending=ending,
        credits=credits_, debits=debits,
        credit_count=credit_count, debit_count=debit_count,
    )


def parse_wilson_muir_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    header = _HEADER_RE.search(markdown)
    strip = _summary_strip(markdown)
    if header is None or strip is None:
        return None
    statement_date, account = header.groups()
    beginning_date, ending_date = strip.beginning_date, strip.ending_date
    beginning, ending = strip.beginning, strip.ending
    average_match = _AVERAGE_RE.search(markdown)
    average = _money(average_match.group(1)) if average_match else None

    credit_section = section_between(markdown, r"ALL CREDIT ACTIVITY", r"ELECTRONIC DEBITS")
    electronic_section = section_between(markdown, r"ELECTRONIC DEBITS", _AFTER_ELECTRONIC)
    check_section = section_between(markdown, r"CHECKS AND OTHER DEBITS", r"DAILY BALANCE SUMMARY")
    txns = _dated_amount_rows(credit_section, 1)
    txns.extend(_dated_amount_rows(electronic_section, -1))
    txns.extend(_check_rows(check_section))

    if not txns:
        return None
    stated_credits = strip.credits
    stated_debits = strip.debits
    if abs(sum(t.amount for t in txns if t.amount > 0) - stated_credits) > 0.01:
        return None
    if abs(-sum(t.amount for t in txns if t.amount < 0) - stated_debits) > 0.01:
        return None

    end_month, end_day, end_year = [int(part) for part in ending_date.split("/")]
    _stmt_month, _stmt_day, stmt_year = [int(part) for part in statement_date.split("/")]
    period_end = date(2000 + end_year, end_month, end_day)
    start_month, start_day, start_year = [int(part) for part in beginning_date.split("/")]
    # The "balance forward" date is the previous cycle close; activity starts the next calendar day.
    period_start = date(2000 + start_year, start_month, start_day) + timedelta(days=1)
    stmt = Statement(
        bank="Wilson & Muir Bank & Trust",
        account_name="Small Business Package",
        account_number=f"#{account}",
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        # Derived from the printed period bounds (R-1 item 10 - previously a
        # hardcoded 30-day guess). The year-consistency check keeps the value
        # fail-closed when the statement date conflicts with the period end.
        days_in_period=(
            (period_end - period_start).days + 1
            if stmt_year == period_end.year
            else None
        ),
        beginning_balance=beginning,
        ending_balance=ending,
        stated_total_credits=stated_credits,
        stated_total_debits=stated_debits,
        # Every count the strip printed on that side, not the three categories
        # this module used to know: a period whose debits include an ATM
        # withdrawal or a miscellaneous fee states a debit count that includes
        # them, and a stated count short of the printed one is a false
        # contradiction against a ledger that is complete.
        stated_credit_count=strip.credit_count,
        stated_debit_count=strip.debit_count,
        bank_reported_average_balance=average,
        bank_reported_average_label=(
            "Average Balance (Ledger)" if average is not None else None
        ),
        transactions=txns,
    )
    return stmt

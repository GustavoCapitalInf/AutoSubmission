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
#: The space thousands separators `analysis/money.py` already surveys — its
#: format axes list `1 234.56` (:17) and `EITHER_MINUS_SPACED` (:214) exists to
#: strip them — written out as the ASCII space plus the two no-break spaces a
#: PDF text layer emits in its place.
_THOUSANDS_SPACE = "\u0020\u00a0\u202f"

#: A Balance Summary figure. PNC drops the leading zero on a sub-dollar amount,
#: so a balance of eighty-seven cents is printed `.87` — and a `\b` before the
#: point does not match after a space, which is how the old pattern skipped such
#: a figure and then read the NEXT one (the average ledger balance) as the
#: closing balance. The boundary here is "not preceded by a digit, comma or
#: point", which is a statement about the grid rather than about word
#: characters.
#:
#: The body is a FLATTENED grid, so one space character does two jobs: it
#: separates the columns, and in a figure printed `1 000.00` it groups the
#: thousands. What tells the two apart is not the character but what stands to
#: its left — a complete `.dd` figure ENDS a column, so a space after one is a
#: column gap; anywhere else a digit run adjoining a `<space><3 digits>` group
#: is the head of one figure rather than the whole of two.
#:
#: Both halves of that rule are load-bearing, and they fail in opposite
#: directions. Without the grouped integer part `1 000.00` cannot match whole.
#: Without the boundary guard the match that DOES fit — the `000.00` tail — is
#: a silent truncation of it, and a truncated summary is not caught downstream:
#: all four columns truncate together, so every printed identity still closes
#: and the statement publishes approved with each figure wrong by the same
#: thousand. The guard makes the fragment unmatchable, so a figure this parser
#: cannot read whole is not read at all and the document fails closed.
_SUMMARY_MONEY_RE = re.compile(
    rf"(?<![\d.,])"
    rf"(?:(?<=\.\d\d[{_THOUSANDS_SPACE}])|(?<![\d][{_THOUSANDS_SPACE}]))"
    rf"(?:\d[\d,]*(?:[{_THOUSANDS_SPACE}]\d{{3}})*)?\.\d{{2}}-?"
)

#: The same printed figure where a label rather than a column position finds it,
#: so the two readings of the Balance Summary block cannot disagree about what a
#: figure is. Not optional-integer: these lines print a labelled balance.
_LABELLED_FIGURE = rf"\d[\d,]*(?:[{_THOUSANDS_SPACE}]\d{{3}})*\.\d{{2}}"
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
    # A figure read whole from the grid can carry the space thousands separator
    # the patterns above admit. `parse_money` removes `$`, `,` and `*` but not
    # spaces, and it SEARCHES rather than anchors, so it would read `1 000.00`
    # as one dollar — the same truncation by a different route.
    for space in _THOUSANDS_SPACE:
        value = value.replace(space, "")
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
    # The average ledger balance is printed in the same Balance Summary block
    # and in the same figure format as the four columns above it, so it reads
    # the same figure grammar. Reading it with a narrower one would mean a
    # document whose columns this parser now reads whole could still publish a
    # truncated average beside them.
    m = re.search(rf"Average ledger\s+Average collected\s+balance\s+({_LABELLED_FIGURE})",
                  text, re.IGNORECASE)
    if not m:
        m = re.search(rf"Average ledger.*?balance\s+({_LABELLED_FIGURE})",
                      text, re.IGNORECASE | re.DOTALL)
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


def _posts(amount: float) -> bool:
    """Whether an Activity Detail row is a POSTING rather than furniture.

    A posting is a movement of money, and the Activity Detail also carries
    dated lines that state a fact about the period instead of moving anything —
    an overdraft-fee notice, a period marker. Those print in the same column
    group as a posting and the row grammar cannot tell them apart: PNC prints
    genuine sub-dollar amounts with the leading zero dropped (`02/02 .82 ACH
    Credit ...` — 54 such postings in the archive), so `.dd` has to stay
    readable, and a `.00` line then satisfies the row pattern exactly as a
    posting does.

    What separates them is the figure itself: a row that moves nothing is not a
    posting. That is also the only reading a downstream check could ever
    recover, because such a row is invisible to every identity the fail-closed
    gate applies — it adds zero to both the ledger sum and the section total,
    so a fabricated one leaves beginning + activity == ending intact. PNC
    discloses no per-direction count oracle (`analysis/count_semantics.py`
    SECTION_LEVEL_ORACLES), so the row count cannot catch it either. The
    refusal has to happen here or nowhere.

    Structural, not a vocabulary: nothing here reads the description, so a
    furniture wording this parser has never seen is refused on the same
    grounds, and a real posting is never refused for how it is worded.
    """
    return amount != 0


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
            if txn_date is None or amount is None or not _posts(amount):
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
            if txn_date is None or value is None or not _posts(value):
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

"""Frost Bank business checking, as the mainframe prints it — W3 §FROSTOZK.

WHAT THE ARCHIVE HOLDS. Nine documents, two accounts, four and five
consecutive months, each month's printed `BALANCE THIS STATEMENT` the next
month's printed `BALANCE LAST STATEMENT`.

THE PRINTED SHAPE. A monospace print stream with rule-drawn furniture. Every
figure, name, account number and date below and in `tests/test_frost.py` is
INVENTED, and the fixture's cycle deliberately sits in a year the archive does
not contain.

That is a CHECKED claim and not a promise, and the distinction is the point: an
earlier revision of this docstring made the promise while the tests carried
three real cycle dates, and the scan that was supposed to catch them had been
written through a shell heredoc that ate its own word-boundary escapes and
could not match a date at all. W3 §FZ10.3 records the inert instrument, the
literals its repair found, and the four class counts it now reports::

    |          DEPOSITS           |       WITHDRAWALS           |
    |_____________________________|_____________________________|
    BALANCE LAST STATEMENT | NO. | AMOUNT | NO. | AMOUNT | BALANCE THIS STATEMENT
    |       |              |     |        | 1,000.00   2   500.00   3   200.00   1,300.00

— then dash-ruled sections (`DEPOSITS/CREDITS`, `CHECKS PAID`, `OTHER
WITHDRAWALS/DEBITS`, `DAILY BALANCE`), each with its own column-head line, and
each packed several logical rows to one physical line separated by `|`.

THE SUMMARY IS BOUND BY ITS OWN HEADER, NOT BY POSITION. The value row is a
bare run of six figures. This reader does not assume their order: it reads the
`| DEPOSITS | WITHDRAWALS |` box line and the label line beneath it, derives
the sequence of six field ROLES from those two printed lines, and only then
zips the values onto them (:func:`_summary_layout`). It then type-checks the
binding — a `NO.` slot must be a bare integer and a money slot must carry
cents — and refuses the document if the printed arithmetic
`last + deposits - withdrawals == this` does not close. Three independent
readings of one strip; a document that prints the box the other way round is
read that way or refused, never mis-bound.

THE COLUMN ORDER OF A SECTION IS ALSO READ, NOT ASSUMED. One
`DEPOSITS/CREDITS` section can carry two different layouts back to back, each
under its own head line (`DATE TRANSACTION AMOUNT` two-up, and
`DATE AMOUNT TRANSACTION DESCRIPTION` one-up). :func:`_columns` maps a head
line to a known layout and the reader refuses a head it does not know, so an
unmodelled printing fails closed instead of being read in the wrong order.

WHAT THIS READER REFUSES:

* a summary strip whose header this reader cannot map, whose value row does
  not type-check against it, or whose printed arithmetic does not close;
* a section column head it does not know;
* any non-blank line inside a section region that is neither that section's
  head, one of the two footnote legends, a rule, nor a row this reader can
  parse — an illegible printing fails the document closed rather than
  contributing a partial ledger;
* a captured credit total or debit total that does not reproduce the printed
  `AMOUNT` beside `DEPOSITS` / `WITHDRAWALS`;
* a `DAILY BALANCE` grid whose first cell is not the printed
  `BALANCE LAST STATEMENT`, or whose last cell by date is not the printed
  `BALANCE THIS STATEMENT`;
* a date the `STATEMENT ISSUED` line cannot place, or a document printing two
  different `STATEMENT ISSUED` dates or two different account banners.

WHAT THIS READER DOES NOT PUBLISH, AND WHY.

*No statement period.* This printing states a `STATEMENT ISSUED` date and
nothing else: there is no printed period range anywhere in any of the nine
archive documents. The ratified ADB doctrine computes ONE user-facing average
over the PRINTED period, so `period_start` and `period_end` stay `None` and
`analysis/adb.py` withholds the average — its required
`statement_period_dates_valid` check is exactly the doctrine, enforced. That
is the honest outcome and not a defect of this reader: a period inferred from
the cycle date and the previous cycle's carry-forward cell is a derivation,
and deriving one is a doctrinal decision rather than a parser's. W3 §FROSTOZK
measures what it would be worth and hands the question up.

*No count comparison on the debit side.* The printed withdrawal `NO.` counts a
DIFFERENT set of rows than this reader's debit rows do, and the difference is
not recoverable from any figure the bank prints. See
`analysis/count_semantics.py` for the measurement; the entry there is what
keeps the platform from manufacturing a mismatch flag out of a scope
difference.

*No average and no interest.* Neither is printed anywhere in the family, and a
figure computed from our own rows is not a figure the bank stated.
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_or_none
from .money import EITHER_MINUS_PADDED, parse_amount
from .parser_registry import corroborating, make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import unique_match

# ---------------------------------------------------------------------------
# Printed money and printed dates
# ---------------------------------------------------------------------------

#: One printed amount. Sub-dollar figures print with NO integer part (`.07`),
#: and an overdrawn balance prints its minus AFTER the digits, so both
#: spellings are part of the token. `analysis.money.EITHER_MINUS_PADDED` is the
#: surveyed format that reads exactly that pair.
_AMOUNT = r"(?:\d[\d,]{0,15})?\.\d{2}-?"

#: A bare integer, which is what the two `NO.` cells of the summary carry.
_COUNT = r"\d{1,6}"

#: The posting date every row opens with. The year is not printed on a row.
_MMDD = r"(\d{2})-(\d{2})"


def _cents(token: str | None) -> int | None:
    """One printed amount, in whole cents, or None if it is not money."""
    value = parse_amount(token, EITHER_MINUS_PADDED)
    return None if value is None else int(round(value * 100))


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

#: The bank's own information ladder, printed at the head of page one of every
#: document. Institution furniture — a heading and a toll-free number — and
#: not a customer, product or amount literal.
_LADDER_RE = re.compile(r"FOR INFORMATION CALL")
_TOLL_FREE_RE = re.compile(r"1-800-513-7678")

#: The product banner the statement rules its ledger under, repeated with
#: `(CONTINUED)` on every continuation page.
_BANNER_RE = re.compile(
    r"FROST BUSINESS CHECKING\s*:\s*ACCOUNT NO\.\s*([\d ]{4,20}?)\s*(?:\(CONTINUED\)|_|$)"
)

#: The two printed lines that head the boxed summary strip.
_SUMMARY_HEAD_RE = re.compile(r"BALANCE LAST STATEMENT.*BALANCE THIS STATEMENT")
#: EITHER ORDER, deliberately. Anchoring this on `DEPOSITS` first would make
#: `_summary_layout`'s whole reading of the box unreachable — the layout would
#: be decided by the pattern that found the line rather than by the line — and
#: a box printed the other way round would be refused as unrecognised rather
#: than READ. W3 §FROSTOZK's mutation table found exactly that: with the order
#: baked in here, a mutant that ignored the box line survived every test.
_SIDE = r"(?:DEPOSITS|WITHDRAWALS)"
_BOX_HEAD_RE = re.compile(rf"\|\s*{_SIDE}\s*\|\s*{_SIDE}\s*\|")
_ISSUED_RE = re.compile(r"STATEMENT ISSUED\s+(\d{2})-(\d{2})-(\d{4})")


def _has_ladder(text: str) -> bool:
    return _LADDER_RE.search(text) is not None and _TOLL_FREE_RE.search(text) is not None


def _has_banner(text: str) -> bool:
    return _BANNER_RE.search(text) is not None


def _has_summary_strip(text: str) -> bool:
    return (
        _SUMMARY_HEAD_RE.search(text) is not None
        and _BOX_HEAD_RE.search(text) is not None
    )


DETECTION_MARKERS = (
    required("frost_information_ladder", _has_ladder),
    required("frost_business_checking_banner", _has_banner),
    required("boxed_summary_strip", _has_summary_strip),
    corroborating("statement_issued", lambda text: _ISSUED_RE.search(text) is not None),
)

detect = make_detector(DETECTION_MARKERS)


# ---------------------------------------------------------------------------
# The summary strip, bound by the header the bank drew above it
# ---------------------------------------------------------------------------

#: What one side of the box contributes, in the order the label line prints it.
#: The box line names the sides; the label line names the cells; neither is
#: assumed.
_SIDE_ROLES = {
    "DEPOSITS": ("credit_count", "credit_total"),
    "WITHDRAWALS": ("debit_count", "debit_total"),
}

_LABEL_SPLIT_RE = re.compile(r"\s*\|\s*")
_BOX_SIDES_RE = re.compile(r"\|([^|]+)\|([^|]+)\|")


def _summary_layout(box_line: str, label_line: str) -> tuple[str, ...] | None:
    """The six field roles, in the order these two printed lines declare them.

    The value row below is a bare run of figures whose meaning comes only from
    this pair of lines, so the pair is READ rather than assumed. `None` when
    either line says something this reader does not recognise — a refusal, not
    a fallback.
    """
    sides = _BOX_SIDES_RE.search(box_line)
    if sides is None:
        return None
    first, second = (side.strip() for side in sides.groups())
    if first not in _SIDE_ROLES or second not in _SIDE_ROLES or first == second:
        return None

    cells = [
        cell.strip()
        for cell in _LABEL_SPLIT_RE.split(label_line.strip())
        if cell.strip()
    ]
    if len(cells) != 6:
        return None
    head, no_a, amount_a, no_b, amount_b, tail = cells
    # The mainframe closes the line with an underscore rule.
    tail = tail.split("_")[0].strip()
    if (head, no_a, no_b) != ("BALANCE LAST STATEMENT", "NO.", "NO."):
        return None
    if (amount_a, amount_b) != ("AMOUNT", "AMOUNT"):
        return None
    if tail != "BALANCE THIS STATEMENT":
        return None
    return (
        "opening",
        _SIDE_ROLES[first][0],
        _SIDE_ROLES[first][1],
        _SIDE_ROLES[second][0],
        _SIDE_ROLES[second][1],
        "closing",
    )


#: The value row: the six figures the box skeleton leads into.
_VALUE_RE = re.compile(rf"(?:{_AMOUNT}|{_COUNT})")
_COUNT_ONLY_RE = re.compile(rf"{_COUNT}\Z")
_AMOUNT_ONLY_RE = re.compile(rf"{_AMOUNT}\Z")


def _summary(lines: list[str]) -> dict[str, int] | None:
    """The six printed summary figures, keyed by the role their header gave them.

    The type of each cell is a second, independent reading of the binding: a
    `NO.` slot must be a bare integer and a money slot must carry cents, so a
    value row zipped onto the wrong roles is refused before its arithmetic is
    ever tried.
    """
    box_index = next(
        (i for i, line in enumerate(lines) if _BOX_HEAD_RE.search(line)), None
    )
    if box_index is None:
        return None
    label_index = next(
        (
            i
            for i in range(box_index, min(box_index + 4, len(lines)))
            if _SUMMARY_HEAD_RE.search(lines[i])
        ),
        None,
    )
    if label_index is None:
        return None
    roles = _summary_layout(lines[box_index], lines[label_index])
    if roles is None:
        return None
    for line in lines[label_index + 1: label_index + 4]:
        tokens = _VALUE_RE.findall(line.split("|")[-1])
        if len(tokens) < len(roles):
            continue
        if len(tokens) != len(roles):
            return None
        summary: dict[str, int] = {}
        for role, token in zip(roles, tokens):
            if role.endswith("_count"):
                if _COUNT_ONLY_RE.match(token) is None:
                    return None
                summary[role] = int(token)
                continue
            if _AMOUNT_ONLY_RE.match(token) is None:
                return None
            value = _cents(token)
            if value is None:
                return None
            summary[role] = value
        return summary
    return None


# ---------------------------------------------------------------------------
# The dash-ruled sections
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(
    r"^-{3,}\s*(DEPOSITS/CREDITS|CHECKS PAID|OTHER WITHDRAWALS/DEBITS|DAILY BALANCE)"
    r"\s*-{3,}$"
)

#: A section region ends at the page furniture that follows it. Continuation
#: pages re-open the section with its rule and its head line.
_REGION_END_RE = re.compile(r"^(?:--- Page |Please examine your bank statement)")

#: The two legends `CHECKS PAID` prints under its grid.
_LEGEND_RE = re.compile(r"^[*#] [A-Z]")

#: The skeleton line of empty cells the mainframe draws under a column head.
_SKELETON_RE = re.compile(r"^[|\s]*$")

#: Column head -> layout name. The head line is the section's own statement
#: about its column order, so it is read; an unknown head is a refusal.
_LAYOUTS = {
    ("DATE", "TRANSACTION", "AMOUNT"): "date_transaction_amount",
    ("DATE", "AMOUNT", "TRANSACTION", "DESCRIPTION"): "date_amount_transaction",
    ("DATE", "CHECK", "AMOUNT"): "date_check_amount",
    ("DATE", "BALANCE"): "date_balance",
}
_HEAD_WORD_RE = re.compile(
    r"^(?:DATE|AMOUNT|TRANSACTION|DESCRIPTION|CHECK|BALANCE)(?:\s|$)"
)


def _columns(line: str) -> str | None:
    """The layout a column-head line declares, or None if it is not one."""
    cell = line.split("|")[0].strip()
    if not cell or _HEAD_WORD_RE.match(cell) is None:
        return None
    return _LAYOUTS.get(tuple(cell.split()))


_ROW_RES = {
    "date_transaction_amount": re.compile(rf"^{_MMDD}\s+(\S.*?)\s\s+({_AMOUNT})$"),
    "date_amount_transaction": re.compile(rf"^{_MMDD}\s+({_AMOUNT})\s\s+(\S.*)$"),
    "date_check_amount": re.compile(
        rf"^{_MMDD}\s+(\d{{1,10}})\s*\*?\s*#?\s+({_AMOUNT})$"
    ),
    "date_balance": re.compile(rf"^{_MMDD}\s+({_AMOUNT})(?:\s+OD)?$"),
}


class _Row:
    """One parsed ledger cell: a posting date, cents, and what it was called."""

    __slots__ = ("month", "day", "cents", "description")

    def __init__(self, month: int, day: int, cents: int, description: str) -> None:
        self.month = month
        self.day = day
        self.cents = cents
        self.description = description


def _row_from(layout: str, cell: str) -> _Row | None:
    """One packed cell, read in the column order its head line declared."""
    match = _ROW_RES[layout].match(cell)
    if match is None:
        return None
    groups = match.groups()
    if layout == "date_amount_transaction":
        amount, description = groups[2], groups[3]
    elif layout == "date_transaction_amount":
        amount, description = groups[3], groups[2]
    elif layout == "date_check_amount":
        amount, description = groups[3], f"CHECK {groups[2]}"
    else:
        amount, description = groups[2], ""
    cents = _cents(amount)
    if cents is None:
        return None
    return _Row(int(groups[0]), int(groups[1]), cents, " ".join(description.split()))


def _read_sections(lines: list[str]) -> dict[str, list[_Row]] | None:
    """Every section's rows, or None if any line inside a region did not parse.

    The completeness rule: inside a section region every non-blank line is
    either that section's own head, a legend, the cell skeleton, or a row. A
    line that is none of those is an unmodelled printing, and the document
    fails closed rather than publishing the rows around it.
    """
    sections: dict[str, list[_Row]] = {}
    section: str | None = None
    layout: str | None = None
    for line in lines:
        stripped = line.strip()
        match = _SECTION_RE.match(stripped)
        if match is not None:
            section, layout = match.group(1), None
            sections.setdefault(section, [])
            continue
        if section is None:
            continue
        if _REGION_END_RE.match(stripped):
            section, layout = None, None
            continue
        if not stripped or _SKELETON_RE.match(stripped) or _LEGEND_RE.match(stripped):
            continue
        head = _columns(line)
        if head is not None:
            layout = head
            continue
        if layout is None:
            return None
        for cell in line.split("|"):
            cell = cell.strip()
            if not cell:
                continue
            row = _row_from(layout, cell)
            if row is None:
                return None
            sections[section].append(row)
    return sections


def _iso(row: _Row, issued: date) -> str | None:
    """A row's ISO date.

    The year is not printed on a row; the cycle date carries it, and a month
    LATER than the cycle's belongs to the year before — which is how the
    `DAILY BALANCE` grid's carry-forward cell crosses a year boundary.
    """
    year = issued.year - 1 if row.month > issued.month else issued.year
    return iso_or_none(year, row.month, row.day)


def parse_frost_statement(markdown: str) -> Statement | None:
    """One Frost business-checking statement, or None."""
    lines = markdown.splitlines()
    banner = unique_match(markdown, _BANNER_RE)
    issued_match = unique_match(markdown, _ISSUED_RE)
    if banner is None or issued_match is None:
        return None
    month, day, year = (int(part) for part in issued_match.groups())
    if iso_or_none(year, month, day) is None:
        return None
    issued = date(year, month, day)

    summary = _summary(lines)
    if summary is None:
        return None
    # The fail-fast, and the third reading of the binding: the strip's own
    # arithmetic. A mis-bound strip does not close.
    if (
        summary["opening"] + summary["credit_total"] - summary["debit_total"]
        != summary["closing"]
    ):
        return None

    sections = _read_sections(lines)
    if sections is None:
        return None

    transactions: list[Transaction] = []
    credit_total = debit_total = 0
    for name, direction in (
        ("DEPOSITS/CREDITS", "credit"),
        ("CHECKS PAID", "debit"),
        ("OTHER WITHDRAWALS/DEBITS", "debit"),
    ):
        for row in sections.get(name, ()):
            iso = _iso(row, issued)
            if iso is None:
                return None
            if direction == "credit":
                credit_total += row.cents
                signed = row.cents
            else:
                debit_total += row.cents
                signed = -row.cents
            transactions.append(
                Transaction(
                    date=iso,
                    description=row.description,
                    amount=round(signed / 100, 2),
                    direction=direction,
                )
            )
    if not transactions:
        return None
    # The captured money against the two figures the bank printed for it. The
    # COUNTS are deliberately not gated: the printed withdrawal `NO.` counts a
    # different set of rows (`analysis/count_semantics.py`), and gating on the
    # deposit `NO.` would turn the platform's own count check into a tautology
    # on the one direction where it is informative.
    if credit_total != summary["credit_total"] or debit_total != summary["debit_total"]:
        return None

    daily = sections.get("DAILY BALANCE", [])
    if not daily:
        return None
    printed_by_day: dict[str, int] = {}
    for row in daily:
        iso = _iso(row, issued)
        if iso is None:
            return None
        # One day, one printed balance. A grid that prints a day twice with two
        # different figures is the document contradicting itself about its own
        # ledger, and there is no rule that says which cell to believe — taking
        # either would be picking one. A repeat that AGREES is free
        # corroboration and is accepted. No archive document of this family
        # prints a duplicate at all, so this closes a hole rather than
        # describing one.
        if printed_by_day.setdefault(iso, row.cents) != row.cents:
            return None
    # The grid is printed column-major, so it arrives out of order; sorting by
    # date is what recovers the walk. Its two ends are a second, independent
    # reading of the two balances the strip printed.
    dated = sorted(printed_by_day.items())
    if dated[0][1] != summary["opening"] or dated[-1][1] != summary["closing"]:
        return None

    stmt = Statement(
        bank="Frost Bank",
        account_number=" ".join(banner.group(1).split()),
        beginning_balance=round(summary["opening"] / 100, 2),
        ending_balance=round(summary["closing"] / 100, 2),
        stated_total_credits=round(summary["credit_total"] / 100, 2),
        stated_total_debits=round(summary["debit_total"] / 100, 2),
        stated_credit_count=summary["credit_count"],
        stated_debit_count=summary["debit_count"],
        # §CURRENCY. Every document of this family prints two Texas post-box
        # addresses with `Member FDIC` and a US toll-free ladder, and no
        # currency code of any kind. That is the institution's identity, not a
        # printed denomination and not a product designation, so the class is
        # `institution_default` (CURRENCY_DOCTRINE §B; `analysis/schema.py`).
        currency="USD",
        currency_source="institution_default",
    )
    # The bank's own end-of-day balances, exactly as printed. The grid lists
    # only the days the account moved; `analysis/adb.py` owns the forward fill.
    stmt.stated_daily_balances = [
        StatementDailyBalance(date=iso, balance=round(value / 100, 2))
        for iso, value in dated
    ]
    stmt.transactions = transactions
    return stmt

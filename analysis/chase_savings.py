"""Chase savings — the `SAVINGS SUMMARY` / `TRANSACTION DETAIL` product.

A distinct printed product from the checking statement `analysis/chase.py`
reads, on the same native template and behind the same `*start*…*end*` text
layer sentinels:

    *start*summary
    Chase Business Total Savings
    SAVINGS SUMMARY
    INSTANCES AMOUNT
    Beginning Balance $…
    Deposits and Additions <n> …
    Ending Balance <n> $…
    Annual Percentage Yield Earned This Period …%
    *end*summary
    *start*transaction detail
    TRANSACTION DETAIL
    DATE DESCRIPTION AMOUNT BALANCE
    Beginning Balance $…
    <MM/DD> <description> <amount> <balance>
    Ending Balance $…
    *end*transaction detail

`chase.py` cannot read it and does not try: it hard-requires `CHECKING
SUMMARY` and then reads six named checking sections that this product does not
print. It prints ONE grid instead, and that grid has a Balance column the
checking sections do not have.

Three things about this grid are load-bearing, and each is anchored on what the
statement prints rather than on what a description says:

**The grid's own Beginning/Ending Balance rows are bounds, not transactions.**
They carry money and no date, they open and close the printed grid, and
publishing them as rows would double-count the period's endpoints. They are
this grid's `ends_row` furniture, exactly as a section total is in `chase.py`.

**The amount cell wraps onto the line ABOVE its row** — the mirror image of the
F1 family, where a wide description pushes the amount cell DOWN. When the
Description column is full the producer emits the Amount cell before the row's
own date line, leaving a bare money token standing alone. The rule that
recovers it is structural and reads no vocabulary: **a group's trailing
bare-money line is the next row's amount cell.** A bare money token is a
wrapped AMOUNT when the line after it opens a row, and a wrapped BALANCE when
it stands inside one — and the difference is exactly the row-group boundary,
which is why this is decided after grouping and not by pattern-matching the
token. (The `square_checking` footer lesson: a claim about what a line
*contains* is not a claim about where the row *ends*.)

**Direction is printed, not inferred.** The Amount column carries its own sign,
detached from the currency symbol in this layout's spelling (`- 530.00`), so no
description wording and no arithmetic orients a row. Where the printed sign and
the printed Balance column disagree, the running-balance walk breaks and the
platform withholds the document — a mis-read row must fail closed, never
quietly balance against a figure derived from itself. Nothing here derives an
amount from a balance for that reason.
"""
from __future__ import annotations

import re

from .date_tokens import iso_from_month_day, period_from_long_dates
from .money import parse_digit_scrubbed
from .parser_registry import excluding, make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, group_rows

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)

#: The digits of a money cell, as this grid prints them.
_MONEY_TOKEN = r"[0-9][0-9,]*\.[0-9]{2}"
#: One printed money cell. The sign stands OUTSIDE the currency symbol and the
#: column's padding may fall between the two, so a debit reads `- 530.00` as
#: readily as `-$530.00`. The lookbehind keeps the tail of a longer digit run
#: (a masked account, a transaction reference) out of the money columns, and
#: the lookahead keeps a percentage rate's digits from being taken as a cell.
_MONEY = re.compile(rf"(?<![\d.,])-?\s*\$?\s*{_MONEY_TOKEN}(?![\d])")
#: The same cell standing alone on its own physical line: a wrapped column.
_BARE_MONEY = re.compile(rf"^-?\s*\$?\s*{_MONEY_TOKEN}$")
#: Scrubbing is only allowed on a token shaped like a printed cell.
_AMOUNT_GUARD = re.compile(rf"-?\s*\$?\s*{_MONEY_TOKEN}")

#: A row starts where the grid starts one: the printed Date column. A transfer
#: row prints a second MM/DD (the transaction date) immediately after the
#: posting date; the posting date is the one the row is dated by, because the
#: other attributes an end-of-day balance to a day the bank does not recognise
#: (`posting_dates_cover_source` in analysis/adb.py).
_ROW_START = re.compile(r"^(\d{2}/\d{2})(?:\s+\d{2}/\d{2})?(?:\s|$)")
#: The grid's own bounds. They carry the period's endpoints, they are printed
#: without a date, and they are not transactions.
_GRID_BOUND = re.compile(r"(?i)^(?:beginning|ending)\s+balance\b")
#: The printed column header of the activity grid, and the section heading
#: above it. Both are furniture; neither opens a row.
_GRID_HEADER = "DATE DESCRIPTION AMOUNT BALANCE"
_FURNITURE = re.compile(
    rf"(?i)^(?:transaction\s+detail(?:\s*\(continued\))?|{_GRID_HEADER}|\(continued\))\s*$"
)
#: Some producers flatten the whole grid onto ONE physical line. A new row
#: starts only where an amount cell ends and a date column begins — the seam is
#: "amount then date", never a bare date, so the second MM/DD printed inside a
#: transfer row (preceded by words) can never split it.
_INLINE_ROW_SPLIT = re.compile(rf"(?<=\.\d{{2}})\s+(?=\d{{2}}/\d{{2}}(?:\s|$))")
#: The same flattening puts the grid's CLOSING bound at the end of the last
#: row's physical line, where its figure would be read as that row's Balance
#: cell — the `square_checking` money-bearing-footer defect in this layout's
#: shape. The remedy is the same and it is structural: a bound is grid
#: furniture that ends whatever row precedes it, wherever the producer happens
#: to have printed it, so it is split back onto its own line before the rows
#: are grouped. This reuses the bound marker the parser already declares
#: rather than introducing new vocabulary.
_BOUND_SPLIT = re.compile(r"(?<=\S)\s+(?=(?:Beginning|Ending)\s+Balance\b)", re.IGNORECASE)

_SUMMARY_AMOUNT = rf"-?\s*\$?\s*{_MONEY_TOKEN}"
#: The summary rows that are debits, as this product prints them. A savings
#: statement prints only the sections that occurred, so every one is optional.
#: The last entry is the combined row one layout prints instead of separate
#: `Other Withdrawals` and `Fees` sections; it cannot collide with those two
#: shorter entries, because they are only matched when a count follows
#: immediately and here a comma does.
_SUMMARY_DEBIT_LABELS = (
    "Checks Paid",
    "ATM & Debit Card Withdrawals",
    "Electronic Withdrawals",
    "Other Withdrawals",
    "Fees",
    "Other Withdrawals, Fees & Charges",
)


def _money(value: str) -> float | None:
    return parse_digit_scrubbed(value, leading_minus=True, guard=_AMOUNT_GUARD)


def _normalized(markdown: str) -> str:
    """The statement with the text layer's spacing normalized and nothing else.

    Inter-word spacing is a property of the text layer rather than of the
    statement (the §BMO-LAYOUTS M3.1 rule) — this product's own sentinels
    arrive as both `*start*transaction detail` and `*start*transactiondetail`
    out of different producers. Case is preserved, because the Description
    column is text this platform publishes.
    """
    return "\n".join(compact_whitespace(line) for line in _IMG_RE.sub("", markdown).splitlines())


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in: normalized spacing, upper
    case, so a producer's capitalisation cannot decide whether we claim."""
    return _normalized(markdown).upper()


#: Issuer furniture only (R-4b): Chase's own PDF text-layer section sentinel
#: (the marker R4-3 added to `chase`, because a bank NAME is wire boilerplate
#: that appears in other banks' statements), the printed product heading, and
#: the printed column header of the one grid this product carries. None of
#: these can be satisfied by another bank's statement naming Chase in a row.
#:
#: `CHECKING SUMMARY` is an EXCLUDING marker, not merely an absent one. It is
#: what makes this registration structurally unable to claim the checking
#: product, which is the safety property the `supersedes` edge over `chase`
#: rests on: a combined statement printing both summaries stays with `chase`,
#: which owns the checking sections, rather than being silently narrowed to a
#: savings grid that is only part of it.
DETECTION_MARKERS = (
    required("section_sentinels", lambda t: "*START*SUMMARY" in t),
    required("savings_summary", lambda t: "SAVINGS SUMMARY" in t),
    required("transaction_detail_grid", lambda t: _GRID_HEADER in t),
    excluding("checking_summary", lambda t: "CHECKING SUMMARY" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def _summary_block(text: str) -> str | None:
    match = re.search(r"SAVINGS SUMMARY(.*?)\*end\*summary", text, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else None


def _read_summary(summary: str, stmt: Statement) -> bool:
    """The figures the bank states about the period, from its own summary."""
    beginning = re.search(rf"Beginning Balance\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
    ending = re.search(rf"Ending Balance(?:\s+\d+)?\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
    if beginning:
        stmt.beginning_balance = _money(beginning.group(1))
    if ending:
        stmt.ending_balance = _money(ending.group(1))

    deposits = re.search(
        rf"Deposits and Additions\s+(\d+)\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE
    )
    if deposits:
        stmt.stated_credit_count = int(deposits.group(1))
        stmt.stated_total_credits = abs(_money(deposits.group(2)) or 0.0)

    debit_total = 0.0
    debit_count = 0
    for label in _SUMMARY_DEBIT_LABELS:
        row = re.search(rf"{re.escape(label)}\s+(\d+)\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
        if not row:
            continue
        debit_count += int(row.group(1))
        amount = abs(_money(row.group(2)) or 0.0)
        debit_total += amount
        if label == "Fees":
            stmt.stated_service_charge = amount
    stmt.stated_debit_count = debit_count or None
    stmt.stated_total_debits = round(debit_total, 2) if debit_total else None

    interest = re.search(
        rf"Interest Paid This Period\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE
    )
    if interest:
        stmt.stated_interest_paid = abs(_money(interest.group(1)) or 0.0)

    return stmt.beginning_balance is not None and stmt.ending_balance is not None


def _grid_lines(text: str):
    """The transaction-detail grid's printed lines, furniture removed.

    The block is found by the column header it prints rather than by its
    sentinel's spelling, because the sentinel arrives with and without its
    inner spaces out of different producers.
    """
    for match in re.finditer(r"\*start\*[^\n]*\n(.*?)\*end\*", text, re.IGNORECASE | re.DOTALL):
        block = match.group(1)
        if _GRID_HEADER not in block.upper():
            continue
        for raw in block.splitlines():
            line = compact_whitespace(raw)
            if not line or _FURNITURE.match(line):
                continue
            for piece in _INLINE_ROW_SPLIT.split(line):
                for part in _BOUND_SPLIT.split(piece):
                    part = part.strip()
                    if part:
                        yield part


def _grid_rows(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """(wrapped amount cell, the row's printed lines) for each row in the grid.

    Grouping is `tables.group_rows` over the printed Date column. The wrapped
    amount is handled around it rather than inside it, in the one way that is
    structural: a bare money line is this row's amount only when a row starts
    on the line after it, which is a fact about the group boundary and not
    about the token. `group_rows` drops what stands before the first row by
    contract, so the leading run — where the first row's wrapped amount lives,
    just under the grid's Beginning Balance bound — is kept here.
    """
    first = next((i for i, line in enumerate(lines) if _ROW_START.match(line)), None)
    if first is None:
        return []
    leading, rest = lines[:first], lines[first:]

    carried = leading[-1] if leading and _BARE_MONEY.match(leading[-1]) else None
    rows: list[tuple[str | None, list[str]]] = []
    for group in group_rows(rest, starts_row=_ROW_START.match, ends_row=_GRID_BOUND.match):
        wrapped = None
        if group and _BARE_MONEY.match(group[-1]):
            # The row this group opened is finished; a money cell printed after
            # it, on a line of its own, is the NEXT row's amount column.
            group, wrapped = group[:-1], group[-1]
        rows.append((carried, group))
        carried = wrapped
    return rows


def _transaction(carried: str | None, group: list[str], *, year: int) -> Transaction | None:
    joined = compact_whitespace(" ".join(group))
    posted = _ROW_START.match(joined)
    if posted is None:
        return None
    cells = list(_MONEY.finditer(joined))
    if carried is not None:
        # The amount wrapped above its row, so the row's own printing ends at
        # the Balance column.
        if not cells:
            return None
        amount, balance, cut = _money(carried), _money(cells[-1].group(0)), cells[-1].start()
    else:
        # The printed column order decides which cell is which: the grid header
        # reads AMOUNT then BALANCE, so the row's last two cells are read in
        # that order rather than by guessing which of the two is larger.
        if len(cells) < 2:
            return None
        amount, balance, cut = _money(cells[-2].group(0)), _money(cells[-1].group(0)), cells[-2].start()
    if amount is None or balance is None:
        return None
    #: Matches, not strings: an amount's characters occur again inside the
    #: balance printed beside it, so the description is sliced by position.
    description = compact_whitespace(joined[posted.end():cut])
    if not description:
        #: A row with no description left is dropped rather than published with
        #: an invented one. Dropping loses the amount, so the ledger stops
        #: reconciling and the document is withheld: fail closed.
        return None
    return Transaction(
        date=iso_from_month_day(posted.group(1), year),
        description=description,
        amount=round(amount, 2),
        direction="credit" if amount >= 0 else "debit",
        running_balance=round(balance, 2),
    )


def parse_chase_savings_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None

    text = _normalized(markdown)
    summary = _summary_block(text)
    if summary is None:
        return None

    period = period_from_long_dates(text)
    if period is None:
        return None
    period_start, period_end = period

    stmt = Statement(bank="Chase Savings", period_start=period_start, period_end=period_end)
    if not _read_summary(summary, stmt):
        return None

    account = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if account:
        stmt.account_number = account.group(1)
    name = re.search(r"^(.*?)\s*SAVINGS SUMMARY", summary, re.IGNORECASE)
    if name and name.group(1):
        stmt.account_name = name.group(1).strip()

    year = int(period_end[:4])
    transactions = [
        txn
        for carried, group in _grid_rows(list(_grid_lines(text)))
        if (txn := _transaction(carried, group, year=year)) is not None
    ]
    if not transactions:
        return None
    stmt.transactions = transactions
    return stmt

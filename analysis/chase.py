from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day, period_from_long_dates
from .money import MINUS_CLASS, parse_digit_scrubbed
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import clean_cell, compact_whitespace, group_rows, table_rows, tables_after

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_EXPORT_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


#: A Chase amount cell as printed: optional parenthesis/minus/dollar wrapper
#: around a grouped decimal. Scrubbing is only allowed on tokens matching this.
#:
#: The gap after a leading sign is the one `_SUMMARY_AMOUNT` already admits,
#: and it is here so that this GUARD admits everything that FINDER finds.
#: Chase prints the sign outside the currency symbol and the column's padding
#: can fall between the two, so a summary row reads "- $530,178.70" as readily
#: as "-$530,178.70" or "- 530,178.70". While the two disagreed the finder
#: matched such a row, the guard refused to scrub it, `_money` returned None,
#: and `abs(... or 0.0)` published **0.00** for a figure the bank had plainly
#: printed — silently, because on a statement whose other debits are small the
#: resulting error can sit inside the reconciliation tolerance.
#:
#: The gap is bound to the sign (`(?:-\s*)?`) rather than floated across the
#: whole prefix, so this admits the detached-sign spelling and NOTHING else:
#: an unclosed "( $X" stays out, as it was before. (W3 §CHASE-CLOSURE card C.)
_AMOUNT_RE = re.compile(r"\(?(?:-\s*)?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})?-?\)?")


def _money(value: str) -> float | None:
    return parse_digit_scrubbed(
        value, parens=True, leading_minus=True, trailing_minus=True, guard=_AMOUNT_RE
    )


def _money_required(value: str) -> float:
    amount = _money(value)
    if amount is None:
        raise ValueError(value)
    return amount


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in: page images carry no words."""
    return _IMG_RE.sub("", markdown)


EXPORT_DETECTION_MARKERS = (
    required("export_header", lambda t: "Printed from Chase for Business" in t),
    required("transactions_section", lambda t: "Transactions" in t),
)

DETECTION_MARKERS = (
    required("bank_name", lambda t: "JPMorgan Chase Bank" in t or "\nCHASE\n" in t),
    # R4-3: the bank name alone is wire boilerplate - it appears in ACH
    # originator strings and remittance advice on other banks' statements, and
    # Chase is the largest folder in the discovery archive. Chase's own PDF
    # text layer delimits its sections with these sentinels.
    required("section_sentinels", lambda t: "*start*summary" in t.lower()),
)

detect_export = make_detector(EXPORT_DETECTION_MARKERS, detection_text)
detect = make_detector(DETECTION_MARKERS, detection_text)


#: An amount cell in the web export's flattened row. The sign is matched
#: through the shared class rather than a bare ``-``: this export prints
#: U+2212 MINUS, and while the finder knew only ASCII it matched the token
#: from the ``$`` onwards — dropping the sign the bank had plainly printed and
#: booking every debit as a credit. (W3 §MONEY-GRAMMAR card 1.)
_EXPORT_AMOUNT_RE = rf"{MINUS_CLASS}?\$\d[\d,]*\.\d{{2}}"


def _parse_chase_business_export(markdown: str) -> Statement | None:
    if not detect_export(markdown).claims:
        return None
    if "CHECKING SUMMARY" in markdown:
        return None

    account = re.search(r"BUS COMPLETE CHK\s+\(\.\.\.(\d+)\)", markdown, re.IGNORECASE)
    name = re.search(
        r"BUS COMPLETE CHK\s+\(\.\.\.\d+\)\s*\nBUS COMPLETE CHK\s+\(\.\.\.\d+\)\s*\n([A-Z0-9 &.'-]+)",
        markdown,
    )
    display_rows: list[Transaction] = []
    current_date: date | None = None
    month_names = "|".join(_EXPORT_MONTHS)
    row_date_re = re.compile(
        rf"^({month_names})[a-z]*\s+(\d{{1,2}}),?\s*(\d{{4}})\s+(.+)$",
        re.IGNORECASE,
    )

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("---") or line.lower().startswith("pending "):
            continue
        date_match = row_date_re.match(line)
        if date_match:
            raw_month, raw_day, raw_year, line = date_match.groups()
            current_date = date(int(raw_year), _EXPORT_MONTHS[raw_month[:3].title()], int(raw_day))
        if current_date is None:
            continue
        money_matches = list(re.finditer(_EXPORT_AMOUNT_RE, line))
        if len(money_matches) < 2:
            continue
        amount_match = money_matches[-2]
        balance_match = money_matches[-1]
        description = line[:amount_match.start()].strip()
        if not description:
            continue
        amount = _money_required(amount_match.group(0))
        balance = _money_required(balance_match.group(0))
        display_rows.append(Transaction(
            date=current_date.isoformat(),
            description=clean_cell(description),
            amount=round(amount, 2),
            direction="credit" if amount > 0 else "debit",
            running_balance=round(balance, 2),
        ))

    if len(display_rows) < 3:
        return None
    transactions = list(reversed(display_rows))
    beginning = round((transactions[0].running_balance or 0.0) - transactions[0].amount, 2)
    ending = transactions[-1].running_balance
    if ending is None:
        return None
    stmt = Statement(
        bank="Chase Transaction Export",
        account_name=name.group(1).strip() if name else None,
        account_number=f"...{account.group(1)}" if account else None,
        period_start=transactions[0].date,
        period_end=transactions[-1].date,
        beginning_balance=beginning,
        ending_balance=ending,
        currency="USD",
        transactions=transactions,
    )
    return stmt


def _tables_after(markdown: str, heading: str) -> list[str]:
    #: Chase spells a section that breaks across pages "<heading> (continued)".
    return tables_after(markdown, heading, continued=r"(?: \(continued\))?")


#: A section heading, as Chase's text layer prints it: the heading owns the
#: line, optionally carrying "(continued)" and/or the column header. It is
#: anchored this way — rather than "heading followed by any whitespace" —
#: because ACH description furniture wraps onto continuation lines that begin
#: with a heading word ("Fees Sec:PPD Trace#..."), and the loose form claimed
#: the enclosing ELECTRONIC WITHDRAWALS block as the FEES section, counting
#: every row in it twice. The same anchor keeps the CHECKING SUMMARY block —
#: whose lines read "Fees 1 -15.00" — from being read as a detail section.
_HEADING_TAIL = r"\s*(?:\(continued\))?\s*(?:$|DATE\b)"


def _native_blocks(markdown: str, heading: str) -> list[str]:
    blocks = []
    for match in re.finditer(r"\*start\*[^\n]*\n(.*?)\*end\*", markdown, re.IGNORECASE | re.DOTALL):
        block = match.group(1)
        if re.search(rf"(?im)^\s*{re.escape(heading)}{_HEADING_TAIL}", block):
            blocks.append(block)
    return blocks


#: The money grammar of an amount cell. `(?![\d])` is load-bearing: a foreign
#: currency row prints its conversion factor ("4967200 X 0.000668276 (Exchg
#: Rte)") and without the boundary `0.000668276` reads as the amount `0.00`.
_MONEY_TOKEN = r"[0-9][0-9,]*\.[0-9]{2}"
#: A row begins where the printed statement begins one: at the MM/DD posting
#: date in the DATE column. Card and transfer rows print a second MM/DD (the
#: transaction date) immediately after it.
_ROW_START_RE = re.compile(r"^(\d{2}/\d{2})(?:\s+\d{2}/\d{2})?(?:\s|$)")
#: The same posting date, looked for ANYWHERE in the document rather than at
#: the head of a segmented line: at the start of any physical line, or after an
#: amount cell on a line a producer has flattened. Used only by the
#: zero-activity guard, which refuses when this matches — so it is deliberately
#: liberal and deliberately section-blind. Every false positive here costs one
#: refusal of a document that would otherwise publish an empty ledger, which is
#: the safe direction; a false negative would let a statement that plainly
#: prints rows be published as though nothing had happened.
_DATED_ROW_RE = re.compile(
    r"(?m)^[ \t]*\d{2}/\d{2}(?:\s|$)|(?<=\.\d{2})[ \t]+\d{2}/\d{2}(?:\s|$)"
)
#: Lines that end a row without starting one: the section total, and the
#: headings of whatever follows the section inside the same block.
_ROW_STOP_RE = re.compile(
    r"(?i)^(?:total\b|atm & debit card summary\b|daily ending balance\b)"
)
#: A page break inside a section prints "(continued)" on its own line. It is
#: furniture, NOT a row boundary: a row whose description is too wide can be
#: cut by the page break, so the lines that open a continued block belong to
#: the row the previous block left open.
_CONTINUED_RE = re.compile(r"(?i)^\(continued\)$")
#: Column headers, stripped before segmentation because some exports print
#: them inline ahead of the first row rather than on their own line.
_COLUMN_HEADER_RE = re.compile(
    r"(?i)^(?:date\s+description\s+amount|date\s+paid\s+amount|date\s+amount"
    r"|check\s+no\.\s+description|instances\s+amount)\s*"
)
#: Some exports flatten a whole section onto ONE physical line. A new row
#: starts only where an amount cell ends and a date column begins — the seam
#: is "amount then date", never a bare date, so the second MM/DD printed
#: inside a card row (preceded by words) can never split it.
_INLINE_ROW_SPLIT_RE = re.compile(r"(?<=\.\d{2})\s+(?=\d{2}/\d{2}(?:\s|$))")
#: The amount column is right-aligned, so the amount always terminates a
#: physical line; and when the description is too wide the amount cell wraps
#: onto a line of its own.
_AMOUNT_CELL_RE = re.compile(rf"^\$?\s?({_MONEY_TOKEN})$")
_AMOUNT_AT_LINE_END_RE = re.compile(rf"(?<![\d.,])\$?\s?({_MONEY_TOKEN})$")
_ANY_AMOUNT_RE = re.compile(rf"(?<![\d.,])\$?\s?({_MONEY_TOKEN})(?![\d])")


def _physical_lines(block: str, heading: str):
    """The block's printed lines, with section furniture removed and lines
    that carry several rows broken at the amount/date seam."""
    head_re = re.compile(rf"(?i)^{re.escape(heading)}\s*(?:\(continued\))?\s*")
    for raw in block.splitlines():
        line = compact_whitespace(raw)
        if not line:
            continue
        if _CONTINUED_RE.match(line):
            continue
        line = head_re.sub("", line, count=1)
        line = _COLUMN_HEADER_RE.sub("", line, count=1)
        if not line:
            continue
        for piece in _INLINE_ROW_SPLIT_RE.split(line):
            piece = piece.strip()
            if piece:
                yield piece


def _native_rows(lines) -> list[list[str]]:
    """Group a section's printed lines into rows.

    Segmentation is structural, not lexical. Before W3 Track A this function
    split the flattened block ahead of a closed list of 23 description
    prefixes ("Zelle Payment", "Card Purchase", ...), which meant any row
    Chase described some other way — a reversal, a wire, a named fee, a CHIPS
    credit — was folded into its predecessor: the row disappeared AND the
    predecessor took the swallowed row's amount. That single rule is why the
    217-document `chase x detail_coverage` withheld cell existed.

    The rule that replaced it is not Chase's alone — td_can and rbc reached
    the same one — so it lives in `tables.group_rows` (W3 §GROUPER). What
    stays here is the part that IS Chase's: the DATE column's grammar and the
    vocabulary of the lines that end a section.
    """
    return group_rows(lines, starts_row=_ROW_START_RE.match, ends_row=_ROW_STOP_RE.match)


def _row_amount(lines: list[str]) -> tuple[float, int, int] | None:
    """The row's amount, and where in `lines` it was printed.

    Preference order follows the printed grid: a wrapped amount cell standing
    alone on its own line, then the token that terminates a line (the
    right-aligned column), then any money token. The first is what
    distinguishes a purchase-with-cash-back row — whose description carries
    "Purchase $352.94 Cash Back $40.00" — from its actual $392.94 amount cell.
    """
    for index, line in enumerate(lines[1:], start=1):
        match = _AMOUNT_CELL_RE.match(line)
        if match:
            return _money(match.group(1)) or 0.0, index, match.start(1)
    for index, line in enumerate(lines):
        match = _AMOUNT_AT_LINE_END_RE.search(line)
        if match:
            amount = _money(match.group(1))
            if amount is not None:
                return amount, index, match.start(1)
    for index, line in enumerate(lines):
        match = _ANY_AMOUNT_RE.search(line)
        if match:
            amount = _money(match.group(1))
            if amount is not None:
                return amount, index, match.start(1)
    return None


def _row_description(lines: list[str], amount_line: int, amount_start: int) -> str:
    parts = []
    for index, line in enumerate(lines):
        if index == amount_line:
            line = line[:amount_start].rstrip().rstrip("$").rstrip()
        if line:
            parts.append(line)
    body = compact_whitespace(" ".join(parts))
    return re.sub(r"^\d{2}/\d{2}(?:\s+\d{2}/\d{2})?\s*", "", body)


def _parse_native_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    #: The section's blocks are grouped as ONE line stream, in document order,
    #: because a page break can cut a row in half: the block that opens after
    #: it begins with the tail of the row the previous block left open.
    stream: list[str] = []
    for block in _native_blocks(markdown, heading):
        stream.extend(_physical_lines(block, heading))
    for lines in _native_rows(stream):
        found = _row_amount(lines)
        if found is None:
            continue
        #: The DATE column is the POSTING date. Card and transfer rows print
        #: the transaction date second; dating a row by that one attributes
        #: its end-of-day balance to a day the bank does not recognise
        #: (`posting_dates_cover_source` in analysis/adb.py).
        posted = _ROW_START_RE.match(lines[0])
        if posted is None:
            continue
        amount, amount_line, amount_start = found
        desc = _row_description(lines, amount_line, amount_start)
        #: A row with no description left is dropped rather than published
        #: with an invented one. Dropping loses the amount, so the ledger
        #: stops reconciling and the document is withheld: fail closed.
        if not desc or desc.lower().startswith("total"):
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=iso_from_month_day(posted.group(1), year),
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


#: A check row starts at the check number in the CHECK NO. column. The number
#: is bounded at 10 digits so the long page-barcode digit run Chase prints
#: inside some blocks cannot open a row.
_CHECK_START_RE = re.compile(r"^\d{1,10}(?:\s|$)")
_CHECK_INLINE_SPLIT_RE = re.compile(r"(?<=\.\d{2})\s+(?=\d{1,10}(?:\s|$))")
#: check no. | skip/image markers | (an electronic check's description) |
#: date paid | (a second printed date) | amount.
_CHECK_ROW_RE = re.compile(
    rf"^(\d{{1,10}})\s+(?:[*^]\s*)*(?:.*?\s)??"
    rf"(\d{{2}}/\d{{2}})(?:\s+\d{{2}}/\d{{2}})?\s+\$?\s*({_MONEY_TOKEN})(?![\d])"
)


def _check_pieces(block: str):
    """The CHECKS PAID block's printed lines, with section furniture removed
    and lines carrying several check rows broken at the amount/number seam.
    The CHECKS PAID counterpart of `_physical_lines`."""
    for raw in block.splitlines():
        line = compact_whitespace(raw)
        if not line:
            continue
        line = re.sub(r"(?i)^CHECKS PAID\s*(?:\(continued\))?\s*", "", line, count=1)
        line = _COLUMN_HEADER_RE.sub("", line, count=1)
        if not line:
            continue
        for piece in _CHECK_INLINE_SPLIT_RE.split(line):
            piece = piece.strip()
            if piece:
                yield piece


def _check_rows(block: str) -> list[list[str]]:
    """The same grouping rule as `_native_rows`, over the CHECK NO. column.

    A check row opens at its printed check number rather than at a date — F8's
    electronic checks print an ACH description between the number and the
    date — which is exactly the substitution `tables.group_rows` takes as an
    argument.
    """
    return group_rows(
        _check_pieces(block), starts_row=_CHECK_START_RE.match, ends_row=_ROW_STOP_RE.match
    )


def _parse_native_checks(markdown: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for block in _native_blocks(markdown, "CHECKS PAID"):
        for lines in _check_rows(block):
            match = _CHECK_ROW_RE.match(" ".join(lines))
            if not match:
                continue
            check_no, mmdd, amount_text = match.groups()
            amount = _money(amount_text)
            if amount is None:
                continue
            txns.append(Transaction(
                date=iso_from_month_day(mmdd, year),
                description=f"Check Paid {check_no}",
                amount=round(-abs(amount), 2),
                direction="debit",
                running_balance=None,
            ))
    return txns


#: A CHECKING SUMMARY amount. The Commercial Checking layout prints its debit
#: rows with a space between the sign and the figure ("- 530,178.70"), so a
#: pattern that demands `-?` immediately before the digits reads NONE of that
#: statement's debit rows and leaves `stated_total_debits` unset — the summary
#: then cannot be checked against the ledger at all.
_SUMMARY_AMOUNT = r"-?\s*\$?\s*[0-9][0-9,]*\.[0-9]{2}"
#: The summary rows that are debits. The last entry is the Commercial Checking
#: layout's combined row; it cannot collide with the shorter "Other
#: Withdrawals" or "Fees" entries because those are only matched when a count
#: follows immediately, and here a comma does.
_SUMMARY_DEBIT_LABELS = (
    "Checks Paid",
    "ATM & Debit Card Withdrawals",
    "Electronic Withdrawals",
    "Other Withdrawals",
    "Fees",
    "Other Withdrawals, Fees & Charges",
)


def _parse_native_summary(text: str, stmt: Statement) -> bool:
    match = re.search(r"CHECKING SUMMARY(.*?)\*end\*summary", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return False
    summary = re.sub(r"\s+", " ", match.group(1)).strip()

    # An overdrawn balance is printed with the sign outside the currency
    # symbol, exactly as every other row of this summary prints a debit. These
    # two rows carried their own unsigned copy of the money pattern and so
    # could not read one; they now use the module's sign-aware `_SUMMARY_AMOUNT`
    # like the rest of the block. (W3 §CHASE-LAYOUTS C6.1.)
    beginning = re.search(rf"Beginning Balance\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
    ending = re.search(rf"Ending Balance(?:\s+\d+)?\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
    deposits = re.search(rf"Deposits and Additions\s+(\d+)\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
    if beginning:
        stmt.beginning_balance = _money(beginning.group(1))
    if ending:
        stmt.ending_balance = _money(ending.group(1))
    if deposits:
        stmt.stated_credit_count = int(deposits.group(1))
        stmt.stated_total_credits = abs(_money(deposits.group(2)) or 0.0)

    debit_total = 0.0
    debit_count = 0
    for label in _SUMMARY_DEBIT_LABELS:
        m = re.search(rf"{re.escape(label)}\s+(\d+)\s+({_SUMMARY_AMOUNT})", summary, re.IGNORECASE)
        if not m:
            continue
        debit_count += int(m.group(1))
        amount = abs(_money(m.group(2)) or 0.0)
        debit_total += amount
        if label == "Fees":
            stmt.stated_service_charge = amount
    stmt.stated_debit_count = debit_count or None
    stmt.stated_total_debits = round(debit_total, 2) if debit_total else None
    return stmt.beginning_balance is not None and stmt.ending_balance is not None


def _parse_txn_table(table: str, *, year: int, sign: int) -> tuple[list[Transaction], list[tuple[str, str]]]:
    txns: list[Transaction] = []
    missing_amounts: list[tuple[str, str]] = []
    for cells in table_rows(table):
        if len(cells) < 3:
            continue
        if cells[0].upper() == "DATE" or cells[0].lower().startswith("total"):
            continue
        if not re.fullmatch(r"\d{2}/\d{2}", cells[0]):
            continue
        amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
        if amount_idx is None:
            desc = " ".join(cells[1:]).strip()
            if desc:
                missing_amounts.append((iso_from_month_day(cells[0], year), desc))
            continue
        amount = _money(cells[amount_idx])
        if amount is None:
            continue
        desc = " ".join(cells[1:amount_idx]).strip()
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=iso_from_month_day(cells[0], year),
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns, missing_amounts


def _table_total(table: str, label: str) -> float | None:
    for cells in table_rows(table):
        if len(cells) < 2:
            continue
        if label.lower() not in cells[0].lower():
            continue
        for cell in reversed(cells):
            amount = _money(cell)
            if amount is not None:
                return abs(amount)
    return None


def _parse_section(markdown: str, heading: str, *, total_label: str, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    missing_amounts: list[tuple[str, str]] = []
    stated_total = 0.0
    for table in _tables_after(markdown, heading):
        table_txns, table_missing = _parse_txn_table(table, year=year, sign=sign)
        txns.extend(table_txns)
        missing_amounts.extend(table_missing)
        total = _table_total(table, total_label)
        if total is not None:
            stated_total += total

    parsed_total = round(sum(abs(t.amount) for t in txns), 2)
    missing_total = round(stated_total - parsed_total, 2) if stated_total else 0.0
    if len(missing_amounts) == 1 and missing_total > 0:
        txn_date, desc = missing_amounts[0]
        signed = round(missing_total * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def parse_chase_statement(markdown: str) -> Statement | None:
    text = _IMG_RE.sub("", markdown)
    export = _parse_chase_business_export(text)
    if export is not None:
        return export
    if not detect(markdown).claims:
        return None
    if "CHECKING SUMMARY" not in text:
        return None

    period = period_from_long_dates(text)
    if period is None:
        return None
    period_start, period_end = period
    year = int(period_end[:4])

    stmt = Statement(bank="Chase", period_start=period_start, period_end=period_end)
    acct = re.search(r"Account Number:\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    name = re.search(r"CHECKING SUMMARY\s*\n([^\n<]+)", text, re.IGNORECASE)
    if name:
        stmt.account_name = name.group(1).strip()

    summary_match = re.search(r"CHECKING SUMMARY.*?(<table>.*?</table>)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        debit_total = 0.0
        debit_count = 0
        for cells in table_rows(summary_match.group(1)):
            if len(cells) < 3:
                continue
            label = cells[0].lower()
            instances = re.sub(r"[^0-9]", "", cells[1])
            amount = _money(cells[2])
            if "beginning balance" in label:
                stmt.beginning_balance = amount
            elif "deposits and additions" in label:
                stmt.stated_credit_count = int(instances) if instances else None
                stmt.stated_total_credits = amount
            elif any(name in label for name in ("checks paid", "atm", "electronic withdrawals", "other withdrawals", "fees")):
                if amount is not None:
                    debit_total += abs(amount)
                if instances:
                    debit_count += int(instances)
                if "fees" in label and amount is not None:
                    stmt.stated_service_charge = abs(amount)
            elif "ending balance" in label:
                stmt.ending_balance = amount
        stmt.stated_total_debits = round(debit_total, 2) if debit_total else None
        stmt.stated_debit_count = debit_count or None
    elif not _parse_native_summary(text, stmt):
        return None

    txns: list[Transaction] = []
    txns.extend(_parse_section(
        text,
        "DEPOSITS AND ADDITIONS",
        total_label="Total Deposits and Additions",
        year=year,
        sign=1,
    ))
    txns.extend(_parse_section(
        text,
        "ATM & DEBIT CARD WITHDRAWALS",
        total_label="Total ATM & Debit Card Withdrawals",
        year=year,
        sign=-1,
    ))
    txns.extend(_parse_section(
        text,
        "ELECTRONIC WITHDRAWALS",
        total_label="Total Electronic Withdrawals",
        year=year,
        sign=-1,
    ))
    txns.extend(_parse_section(
        text,
        "FEES",
        total_label="Total Fees",
        year=year,
        sign=-1,
    ))
    if not txns:
        txns.extend(_parse_native_section(text, "DEPOSITS AND ADDITIONS", year=year, sign=1))
        txns.extend(_parse_native_checks(text, year=year))
        txns.extend(_parse_native_section(text, "ATM & DEBIT CARD WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(text, "ELECTRONIC WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(text, "OTHER WITHDRAWALS", year=year, sign=-1))
        #: The Commercial Checking layout prints one combined section instead
        #: of separate OTHER WITHDRAWALS and FEES sections, and names it the
        #: same way in CHECKING SUMMARY. Without it the summary states a debit
        #: total whose detail is never read. The anchored heading match means
        #: the two spellings cannot both claim the same block.
        txns.extend(_parse_native_section(text, "OTHER WITHDRAWALS, FEES & CHARGES", year=year, sign=-1))
        txns.extend(_parse_native_section(text, "FEES", year=year, sign=-1))

    if stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    # A period in which nothing happened is still a statement, and Chase prints
    # one: an opening balance, a closing balance equal to it, and NO detail
    # section — on the real population every such document prints no section
    # rows at all, so the stated count and total fields come back None rather
    # than 0. "The bank stated zero" is therefore NOT what fires here, and the
    # rule must not be read that way.
    #
    # The discriminator is three facts together: the two balances agree, the
    # summary states no instances and no totals, and **the document prints no
    # posting row**. The last is load-bearing and is the reason the first two
    # are not enough on their own: an empty `txns` with unset stated fields is
    # also exactly what THIS READER FAILING TO READ THE SUMMARY looks like —
    # a summary whose rows carry no instance count, or amounts without cents,
    # or an HTML summary whose cells are short or whose columns are shifted,
    # all leave every stated field None while the statement plainly prints
    # money. Each of those still prints its dated rows, and that is what
    # separates them from a period in which nothing was posted. Beginning ==
    # ending does not separate them: a sweep account or a net-zero month is a
    # real shape.
    #
    # Fail closed in the direction that matters: emptiness is never its own
    # proof that the period was empty.
    # (W3 §CHASE-CLOSURE card A′, amended after Ocean's adversarial review.)
    if not txns and not (
        not stmt.stated_credit_count
        and not stmt.stated_debit_count
        and not stmt.stated_total_credits
        and not stmt.stated_total_debits
        and stmt.beginning_balance == stmt.ending_balance
        and not _DATED_ROW_RE.search(text)
    ):
        return None
    stmt.transactions = txns
    return stmt


#: Public entry point for the Chase online transaction export, which R-3
#: registers in its own right. `parse_chase_statement` still tries it first;
#: that inner call goes away when the pipeline switches to registry dispatch.
parse_chase_export_statement = _parse_chase_business_export

from __future__ import annotations

import re
from datetime import date
from typing import NamedTuple

from .date_tokens import iso_or_none
from .holder_name import NO_READING, HolderReading, first_page, page_lines, read_name
from .money import parse_money, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import table_rows, tables_after

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
#: Audit round 2, R2-B05 (R04 part 2): the period line Bank of America prints above the holder's name on page 1
#: ('for May 1, 2054 to May 31, 2054 Account number: 0000 0000 0000').
_HOLDER_ANCHOR = re.compile(
    r"^for [A-Z][a-z]+ \d{1,2}, \d{4} to [A-Z][a-z]+ \d{1,2}, \d{4} Account number:", re.IGNORECASE
)
#: The page's own headings that can follow the period line where no name prints.
_NOT_A_HOLDER_LINE = re.compile(r"^(?:Account summary|Your |Page \d)", re.IGNORECASE)


def _holder_reading(markdown: str) -> HolderReading:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name, the line Bank of America prints after page 1's period
    line ('for <period> Account number: <number>'). NO_READING without that line or where a heading follows it.
    `account_name` keeps the product line ('Your <product> for <period>'). Owner ruling 2026-10-02 (Q10), audit round
    2, R2-OW10: with the account title that line prints after the name."""
    lines = page_lines(first_page(_IMG_RE.sub("", markdown)))
    for index, line in enumerate(lines[:-1]):
        if _HOLDER_ANCHOR.match(line):
            following = lines[index + 1]
            return NO_READING if _NOT_A_HOLDER_LINE.match(following) else read_name(following)
    return NO_READING


def _money(value: str) -> float | None:
    text = value.strip()
    if not re.fullmatch(r"-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})|-?\$?0(?:\.00)?", text):
        return None
    return parse_money(text)


def _parse_date(value: str) -> str | None:
    """The row's posting date, or None when that token is not a date.

    Every caller already skips a row this returns None for, which is the right
    handling for a token of the right shape that no calendar can hold: BofA
    native text puts a column that is not the date column at the head of a row
    often enough that discovery found 16 documents where it raised here
    (`iso_or_none`).
    """
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2})", value.strip())
    if not m:
        return None
    month, day, year = m.groups()
    return iso_or_none(2000 + int(year), int(month), int(day))


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"for\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\s+to\s+([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})",
        markdown,
    )
    if not m:
        return None
    months = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    }
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), months[sm], int(sd)).isoformat(),
        date(int(ey), months[em], int(ed)).isoformat(),
    )


def _tables_after(markdown: str, heading: str) -> list[str]:
    #: BofA spells a section that breaks across pages "<heading> - continued".
    return tables_after(markdown, heading, continued=r"(?: - continued)?")


# ---------------------------------------------------------------------------
# The printed native grid
#
# BofA's native statements are a two-column grid — `Date Description Amount`,
# the Amount column right-aligned and printed last — inside named sections that
# each publish their own total. Two section vocabularies exist: the business
# one ("Deposits and other credits" / "Withdrawals and other debits") and the
# consumer one ("Deposits and other additions" / "ATM and debit card
# subtractions" / "Other subtractions"). Both print Checks and Service fees the
# same way.
#
# The reader below is a state machine over the PHYSICAL lines the text layer
# emits, because that is the structure the bank printed. Its three rules:
#
#   * a section is entered by a line the heading OWNS (the heading, optionally
#     " - continued", optionally the column header, then either nothing or the
#     first row) and is left at the printed section total, a page break, or the
#     next heading. A summary line is heading words followed by an amount, and
#     never opens a section;
#   * a row begins at a physical line whose FIRST token is the MM/DD/YY posting
#     date. A date-shaped token anywhere else on the line is description text —
#     wire details print `PMT DET:… 26/02/03 …` and adjustment rows print
#     `Temporary Credit Adjustment on 03/31/26`, and neither starts a row;
#   * a row ends at its amount cell: the money token that terminates a physical
#     line. Until then the following lines continue it, which is how a wrapped
#     description whose amount wraps onto its own line is read as one row.
#
# Nothing here keys on what a row *says*. A description that begins with the
# word "Total" (a counterparty name) is a row like any other; section furniture
# is recognised by not being date-headed.
# ---------------------------------------------------------------------------

_CREDIT, _DEBIT = 1, -1


class _Section(NamedTuple):
    """One printed detail section: its heading, its printed total, its side."""

    heading: str
    total: str
    sign: int
    checks: bool = False


#: In printed order — which is also the order rows are published in. Headings
#: are matched anchored at the start of a line, so no entry can claim another's.
_SECTIONS = (
    _Section("Deposits and other credits", "Total deposits and other credits", _CREDIT),
    _Section("Deposits and other additions", "Total deposits and other additions", _CREDIT),
    _Section("Withdrawals and other debits", "Total withdrawals and other debits", _DEBIT),
    _Section("ATM and debit card subtractions", "Total ATM and debit card subtractions", _DEBIT),
    _Section("Other subtractions", "Total other subtractions", _DEBIT),
    _Section("Checks", "Total checks", _DEBIT, checks=True),
    _Section("Service fees", "Total service fees", _DEBIT),
)

#: Printed blocks that are not detail sections. They close whatever section is
#: open so a balance series or an image index can never be read as activity.
_CLOSING_HEADINGS = (
    "Withdrawals and other subtractions",
    "Daily ledger balances",
    "Check images",
    "Account summary",
)

_MONEY_CELL = r"-?\$?\s*[0-9][0-9,]*\.[0-9]{2}"
_ROW_HEAD = re.compile(r"^(\d{2}/\d{2}/\d{2})(?:\s+(.*))?$")
_AMOUNT_CELL = re.compile(rf"({_MONEY_CELL})\s*$")
_LEADING_MONEY = re.compile(rf"^\s*{_MONEY_CELL}")
#: The Amount column wrapping onto a line of its own.
_BARE_CELL = re.compile(_MONEY_CELL)
_COLUMN_HEADER = re.compile(
    r"^\s*Date\s+(?:Transaction\s+)?[Dd]escription\s+Amount\b", re.IGNORECASE
)
_PAGE_BREAK = re.compile(r"^\s*---\s*Page\b", re.IGNORECASE)
_PAGE_FOOTER = re.compile(r"^\s*(?:continued on the next page|Page \d+ of \d+)", re.IGNORECASE)
_SECTION_FURNITURE = re.compile(r"^\s*(?:Total|Subtotal)\b", re.IGNORECASE)
_SUBTOTAL = re.compile(r"(?:^|\s)Subtotal\b", re.IGNORECASE)


def _before_subtotal(text: str) -> str:
    m = _SUBTOTAL.search(text)
    return text if m is None else text[: m.start()]
#: `<date> [<check number>[*]] <amount>` — the check number is what the bank
#: printed for it, and BofA does not always print one.
_CHECK_ROW = re.compile(
    rf"(\d{{2}}/\d{{2}}/\d{{2}})\s+(?:(\d{{1,10}}\*?)\s+)?({_MONEY_CELL})"
)


def _heading_at(line: str) -> tuple[_Section | None, str]:
    """The section this line opens, and whatever follows the column header.

    A heading owns its line: `Checks -7,500.00` is the account summary's checks
    line, not the Checks section, and is rejected because an amount follows the
    words rather than a column header or a row.
    """
    for section in _SECTIONS:
        m = re.match(rf"\s*{re.escape(section.heading)}(?:\s+-\s+continued)?\b", line, re.IGNORECASE)
        if not m:
            continue
        rest = line[m.end():]
        if _LEADING_MONEY.match(rest):
            return None, ""
        header = _COLUMN_HEADER.match(rest)
        if header:
            rest = rest[header.end():]
        return section, rest.strip()
    return None, ""


def _closes_section(line: str) -> bool:
    return any(
        re.match(rf"\s*{re.escape(h)}\b", line, re.IGNORECASE) and not _LEADING_MONEY.match(
            line[re.match(rf"\s*{re.escape(h)}\b", line, re.IGNORECASE).end():])
        for h in _CLOSING_HEADINGS
    )


class _RowStream:
    """Accumulates one section's physical lines into rows."""

    def __init__(self) -> None:
        self.section: _Section | None = None
        self._date: str | None = None
        self._parts: list[str] = []
        self._out: dict[str, list[Transaction]] = {}

    def _emit(self) -> None:
        """Publish the pending row if the grid gave it an amount cell."""
        date, parts = self._date, self._parts
        self._date, self._parts = None, []
        if date is None or not parts:
            return
        text = " ".join(parts)
        cell = _AMOUNT_CELL.search(text)
        if cell is None:
            return                                  # no amount cell: fail closed
        amount = _money(cell.group(1))
        iso = _parse_date(date)
        if amount is None or iso is None:
            return
        desc = re.sub(r"\s+", " ", text[:cell.start()]).strip()
        if not desc:
            return
        assert self.section is not None
        signed = round(abs(amount) * self.section.sign, 2)
        self._out.setdefault(self.section.heading, []).append(Transaction(
            date=iso,
            description=desc,
            # The section the bank printed the row in decides its direction; a
            # waived fee of `-0.00` is still an outflow row.
            amount=signed,
            direction="credit" if self.section.sign > 0 else "debit",
            running_balance=None,
        ))

    def _closed(self) -> bool:
        """A row is closed by its amount cell — the right-aligned last column."""
        return bool(self._parts) and _AMOUNT_CELL.search(" ".join(self._parts)) is not None

    def close_row(self) -> None:
        self._emit()

    def close_section(self) -> None:
        self._emit()
        self.section = None

    def feed(self, text: str, lookahead: str | None = None) -> None:
        if self.section is None or not text.strip():
            return
        if self.section.checks:
            self._checks(text)
            return
        head = _ROW_HEAD.match(text.strip())
        if head:
            self._emit()
            self._date, self._parts = head.group(1), [head.group(2) or ""]
        elif self._date is None or _SECTION_FURNITURE.match(text):
            self._emit()
            return
        else:
            self._parts.append(text.strip())
        # A cell printed alone on its own line is the Amount column wrapping,
        # and it outranks a money-shaped token that merely ends the description
        # line (`… PRODUCT(S): 101.40 S&H: 9.62 MI TAX: 6.66`). So a row that
        # looks complete stays open while the next printed line is that cell.
        if self._closed() and not (lookahead and _BARE_CELL.fullmatch(lookahead.strip())):
            self._emit()

    def _checks(self, text: str) -> None:
        for raw_date, number, raw_amount in _CHECK_ROW.findall(text):
            amount = _money(raw_amount)
            iso = _parse_date(raw_date)
            if amount is None or iso is None:
                continue
            assert self.section is not None
            self._out.setdefault(self.section.heading, []).append(Transaction(
                date=iso,
                description=f"Check {number}" if number else "Check",
                amount=round(-abs(amount), 2),
                direction="debit",
                running_balance=None,
            ))

    def transactions(self, only: frozenset[str] | None = None) -> list[Transaction]:
        """Rows in printed section order: credits, debits, checks, fees."""
        out: list[Transaction] = []
        for section in _SECTIONS:
            if only is None or section.heading in only:
                out.extend(self._out.get(section.heading, ()))
        return out


#: The two sections the HTML-table path has never read; it keeps reading them
#: through the native reader, exactly as it always has.
_TABLE_PATH_EXTRAS = frozenset({"Checks", "Service fees"})


def _consume(stream: _RowStream, line: str, lookahead: str | None = None) -> None:
    """Route one physical line into the row stream.

    A single printed line can carry a section heading, its column header, a
    row, that row's card-account subtotal and the section's own total, in that
    order — BofA glues them together whenever the page break falls there. So
    the line is walked rather than classified once.
    """
    while line.strip():
        section, rest = _heading_at(line)
        if section is not None:
            stream.close_section()
            stream.section = section
            line = rest if rest and (section.checks or _ROW_HEAD.match(rest)) else ""
            continue
        if stream.section is None:
            return
        total = re.search(re.escape(stream.section.total), line, re.IGNORECASE)
        if total is not None:
            # The printed section total ends the section wherever it is printed.
            stream.feed(_before_subtotal(line[: total.start()]))
            stream.close_section()
            line = line[total.end():]
            figure = _LEADING_MONEY.match(line)
            line = line[figure.end():] if figure else line
            continue
        subtotal = _SUBTOTAL.search(line)
        if subtotal is not None:
            # A card-account subtotal is the bank's own label for a figure that
            # is not a row, and it is printed inline after the row it follows.
            stream.feed(line[: subtotal.start()])
            stream.close_row()
            return
        if _closes_section(line):
            stream.close_section()
            return
        stream.feed(line, lookahead)
        return


def _parse_native_sections(text: str, only: frozenset[str] | None = None) -> list[Transaction]:
    stream = _RowStream()
    lines = text.splitlines()
    for index, raw in enumerate(lines):
        line = raw.rstrip()
        if not line.strip():
            stream.close_row()
            continue
        if _PAGE_BREAK.match(line):
            stream.close_section()
            continue
        if _PAGE_FOOTER.match(line):
            stream.close_row()
            continue
        _consume(stream, line, lines[index + 1] if index + 1 < len(lines) else None)
    stream.close_section()
    return stream.transactions(only)


def _native_money_after(text: str, label: str, *, absolute: bool = True) -> float | None:
    """The amount printed after `label`, or None when the label is ABSENT.

    The two Nones this returned used to mean opposite things. "The statement
    prints no such line" is legitimate, and the callers' `or 0.0` is the right
    arithmetic identity for a section that is not there — a statement with no
    Checks line really does have zero checks. "The line IS there and the
    grammar refused its amount" is a fail-open: a figure the bank printed,
    published as 0.00, folded into `stated_total_debits`, and reconciled
    against. Only the first is a None now; a refusal raises out of
    `read_money`. (W3 §MG-C2.)
    """
    m = re.search(label + r"\s+(-?\$?\s*[0-9][0-9,]*\.[0-9]{2})", text, re.IGNORECASE)
    if not m:
        return None
    amount = read_money(m.group(1), _money)
    if amount is None:  # pragma: no cover - the capture group is never blank
        return None
    return abs(amount) if absolute else amount


def _summary_outflows(text: str) -> list[float]:
    """Every outflow line the account summary prints, in either vocabulary.

    The business summary prints one `Withdrawals and other debits` line; the
    consumer summary splits the same total across `ATM and debit card
    subtractions` and `Other subtractions`. Checks and Service fees are printed
    as their own lines by both, and the stated debit total is their sum.
    """
    found = [
        _native_money_after(text, re.escape(label))
        for label in (
            "Withdrawals and other debits",
            "ATM and debit card subtractions",
            "Other subtractions",
        )
    ]
    return [value for value in found if value is not None]


# ---------------------------------------------------------------------------
# `_SUMMARY_COUNT_SCOPE` — what `# of withdrawals/debits: N` counts
#
# ONE documented scope, shared by all three summary readers in this module
# (`_parse_native_summary`, the HTML-table branch of `parse_bofa_statement`,
# and `repair_bofa_summary`). They used to disagree: two stored the printed
# figure and the repair stored `debit_count + (check_count or 0)`, so the same
# field meant two different things across one bank's population.
#
# WHAT THE BANK PRINTS. The account summary is two printed columns that the
# text layer flattens into one interleaved run of lines. The left column is
# money — `Deposits and other credits`, `Withdrawals and other debits`,
# `Checks`, `Service fees` — and the right column is a STATISTICS BOX whose
# items are `# of deposits/credits`, `# of withdrawals/debits`,
# `# of items-previous cycle`, `# of days in cycle`, `Average ledger balance`.
# The two columns are independent lists, which is why `# of days in cycle`
# lands next to `Service fees`: the count lines are NOT paired one-to-one with
# the money lines above them, and no printed figure scopes
# `# of withdrawals/debits` to the `Withdrawals and other debits` money line.
#
# THE SCOPE, MEASURED. Over every archive document that prints the figure
# (344 of 360), the raw printed count equals the rows in the debit column
# exactly — 344 of 344 — and the cheques are inside it: on the 107 documents
# that also print `Total # of checks M`, that M is exactly the number of Check
# rows, and the printed debit count still reproduces the whole debit column
# WITHOUT adding M (`raw + M` matched 0 of 107). The credit sibling in the
# same printed box is the control and is also 344 of 344.
#
# The asymmetry worth naming, because it is what made `+ check_count` look
# right: the cheque MONEY genuinely is outside `Withdrawals and other debits`
# (the summary prints `Checks` as its own line, equal to the section's own
# `Total checks` figure on 107 of 107, and `stated_total_debits` therefore
# does sum the lines). The cheque COUNT is not outside — it is already folded
# into the printed statistic. Money scope and count scope differ, and reading
# one off the other is the defect this note exists to prevent.
# ---------------------------------------------------------------------------


def _parse_native_summary(text: str, stmt: Statement) -> bool:
    stmt.beginning_balance = _native_money_after(text, r"Beginning balance on [^\n$]+", absolute=False)
    stmt.ending_balance = _native_money_after(text, r"Ending balance on [^\n$]+", absolute=False)
    stmt.stated_total_credits = _native_money_after(text, r"Deposits and other credits")
    if stmt.stated_total_credits is None:
        stmt.stated_total_credits = _native_money_after(text, r"Deposits and other additions")
    outflows = _summary_outflows(text)
    checks = _native_money_after(text, r"Checks")
    service = _native_money_after(text, r"Service fees")
    if outflows:
        stmt.stated_total_debits = round(sum(outflows) + (checks or 0.0) + (service or 0.0), 2)
    if service is not None:
        stmt.stated_service_charge = service
    avg = _native_money_after(text, r"Average ledger balance:")
    if avg is not None:
        stmt.bank_reported_average_balance = avg
        stmt.bank_reported_average_label = "Average ledger balance"
    days = re.search(r"# of days in cycle:\s*(\d+)", text, re.IGNORECASE)
    if days:
        stmt.days_in_period = int(days.group(1))
    credit_count = re.search(r"# of deposits/credits:\s*(\d+)", text, re.IGNORECASE)
    if credit_count:
        stmt.stated_credit_count = int(credit_count.group(1))
    # THE PRINTED SCOPE (see the note above `_SUMMARY_COUNT_SCOPE`): the figure
    # is stored raw, because it already counts every row in the debit column —
    # cheques and service fees included.
    debit_count = re.search(r"# of withdrawals/debits:\s*(\d+)", text, re.IGNORECASE)
    if debit_count:
        stmt.stated_debit_count = int(debit_count.group(1))
    return stmt.beginning_balance is not None and stmt.ending_balance is not None


def _table_total(table: str, label: str) -> float | None:
    for cells in table_rows(table):
        if len(cells) < 2 or label.lower() not in cells[0].lower():
            continue
        for cell in reversed(cells):
            amount = _money(cell)
            if amount is not None:
                return abs(amount)
    return None


def _parse_section(markdown: str, heading: str, *, total_label: str, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    missing: list[tuple[str, str]] = []
    stated_total = 0.0

    for table in _tables_after(markdown, heading):
        for cells in table_rows(table):
            if len(cells) < 3 or cells[0].lower() == "date":
                continue
            txn_date = _parse_date(cells[0])
            if txn_date is None:
                continue
            amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
            if amount_idx is None:
                desc = " ".join(cells[1:]).strip()
                if desc:
                    missing.append((txn_date, desc))
                continue
            amount = _money(cells[amount_idx])
            if amount is None:
                continue
            signed = round(abs(amount) * sign, 2)
            txns.append(Transaction(
                date=txn_date,
                description=" ".join(cells[1:amount_idx]).strip(),
                amount=signed,
                direction="credit" if signed >= 0 else "debit",
                running_balance=None,
            ))
        total = _table_total(table, total_label)
        if total is not None:
            stated_total += total

    parsed_total = round(sum(abs(t.amount) for t in txns), 2)
    missing_total = round(stated_total - parsed_total, 2) if stated_total else 0.0
    if len(missing) == 1 and missing_total > 0:
        txn_date, desc = missing[0]
        signed = round(missing_total * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=desc,
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return _IMG_RE.sub("", markdown).upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "BANK OF AMERICA" in t),
    required("summary_section", lambda t: "ACCOUNT SUMMARY" in t),
    # A TD statement paying a Bank of America card carries both of the above.
    # Require the issuer's own domain, the same class of evidence eight other
    # parsers already detect on (R3_DETECTION_FINDING.md).
    required("issuer_domain", lambda t: "BANKOFAMERICA.COM" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_bofa_statement(markdown: str) -> Statement | None:
    text = _IMG_RE.sub("", markdown)
    if not detect(markdown).claims:
        return None
    period = _period(text)
    if period is None:
        return None

    holder = _holder_reading(markdown)
    stmt = Statement(
        bank="Bank of America", holder_name=holder.name, account_title=holder.title, period_start=period[0],
        period_end=period[1],
    )
    acct = re.search(r"Account number:\s*([0-9 ]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = re.sub(r"\s+", "", acct.group(1))
    acct_name = re.search(r"Your\s+(.+?)\s+for\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+to", text, re.IGNORECASE | re.DOTALL)
    if acct_name:
        stmt.account_name = re.sub(r"\s+", " ", acct_name.group(1)).strip()

    summary_match = re.search(r"Account summary\s*(<table>.*?</table>)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        for cells in table_rows(summary_match.group(1)):
            if len(cells) < 2:
                continue
            label = cells[0].lower()
            amount = _money(cells[1])
            extra = cells[2] if len(cells) > 2 else ""
            if "beginning balance" in label:
                stmt.beginning_balance = abs(amount) if amount is not None else None
            elif "deposits and other credits" in label:
                stmt.stated_total_credits = abs(amount) if amount is not None else None
            elif "withdrawals and other debits" in label:
                stmt.stated_total_debits = abs(amount) if amount is not None else None
            elif label == "checks" and amount is not None:
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + abs(amount), 2)
            elif "service fees" in label and amount is not None:
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + abs(amount), 2)
                stmt.stated_service_charge = abs(amount)
            elif "ending balance" in label:
                stmt.ending_balance = abs(amount) if amount is not None else None

            count = re.search(r"# of deposits/credits:\s*(\d+)", extra, re.IGNORECASE)
            if count:
                stmt.stated_credit_count = int(count.group(1))
            # Same printed line as the native reader's, reached through a
            # table cell instead of a physical line, so the same scope applies
            # (`_SUMMARY_COUNT_SCOPE`): stored raw. Recorded honestly — NO
            # archive document takes this branch (0 of 360 render the account
            # summary as an HTML table), so the scope here is inherited from
            # the identical printed figure rather than measured on this path.
            count = re.search(r"# of withdrawals/debits:\s*(\d+)", extra, re.IGNORECASE)
            if count:
                stmt.stated_debit_count = int(count.group(1))
            avg = re.search(r"Average ledger balance:\s*(\$?[\d,]+\.\d{2})", extra, re.IGNORECASE)
            if avg:
                stmt.bank_reported_average_balance = abs(read_money(avg.group(1)) or 0.0)
                stmt.bank_reported_average_label = "Average ledger balance"
    elif not _parse_native_summary(text, stmt):
        return None

    txns = []
    txns.extend(_parse_section(text, "Deposits and other credits", total_label="Total deposits and other credits", sign=1))
    txns.extend(_parse_section(text, "Withdrawals and other debits", total_label="Total withdrawals and other debits", sign=-1))
    txns.extend(_parse_native_sections(text, _TABLE_PATH_EXTRAS if txns else None))
    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt


def repair_bofa_summary(markdown: str, stmt: Statement) -> Statement:
    """Normalize Bank of America summary fields.

    BofA prints withdrawals/debits, checks, and service fees as separate account
    summary lines. For underwriting outflow totals and reconciliation, those must
    be treated as one debit total.
    """
    text = markdown
    if "BANK OF AMERICA" not in text.upper() or "ACCOUNT SUMMARY" not in text.upper():
        return stmt

    def money_after(label: str, *, absolute: bool = True) -> float | None:
        """The amount after `label`, or None when the label is ABSENT.

        The same absence-is-not-refusal separation as `_native_money_after`
        above: this reader's None means the summary does not print the line,
        which is what makes the `checks or 0.0` / `service or 0.0` identities
        below correct. A line that IS printed and whose amount the grammar
        refuses raises instead of being folded in as zero. (W3 §MG-C2.)
        """
        m = re.search(label + r"\s+(-?\$?[\d,]+\.\d{2})", text, re.IGNORECASE)
        if not m:
            return None
        amount = read_money(m.group(1))
        if amount is None:  # pragma: no cover - the capture group is never blank
            return None
        return abs(amount) if absolute else amount

    def int_after(label: str) -> int | None:
        m = re.search(label + r"\s+(\d+)", text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    updates = {}
    beginning = money_after(r"Beginning balance on [A-Z][a-z]+ \d{1,2}, \d{4}", absolute=False)
    ending = money_after(r"Ending balance on [A-Z][a-z]+ \d{1,2}, \d{4}", absolute=False)
    credits = money_after(r"Deposits and other credits")
    if credits is None:
        credits = money_after(r"Deposits and other additions")
    outflows = [
        value for value in (
            money_after(r"Withdrawals and other debits"),
            money_after(r"ATM and debit card subtractions"),
            money_after(r"Other subtractions"),
        ) if value is not None
    ]
    withdrawals = round(sum(outflows), 2) if outflows else None
    checks = money_after(r"Checks")
    service = money_after(r"Service fees")
    avg = money_after(r"Average ledger balance:")
    credit_count = int_after(r"# of deposits/credits:")
    debit_count = int_after(r"# of withdrawals/debits:")
    # `Total # of checks` is deliberately NOT read any more. It used to be
    # added to the printed debit count here, which double-counted the cheques
    # the printed statistic already includes (`_SUMMARY_COUNT_SCOPE`): the
    # mapping fired on the 107 archive documents that print it and was wrong
    # on all 107, while the two other readers stored the raw figure — one
    # field, two meanings. The cheque money is still summed into
    # `stated_total_debits` below, because the money scope really is separate.

    if beginning is not None:
        updates["beginning_balance"] = beginning
    if ending is not None:
        updates["ending_balance"] = ending
    if credits is not None:
        updates["stated_total_credits"] = credits
    if withdrawals is not None:
        updates["stated_total_debits"] = round(withdrawals + (checks or 0.0) + (service or 0.0), 2)
    if credit_count is not None:
        updates["stated_credit_count"] = credit_count
    if debit_count is not None:
        updates["stated_debit_count"] = debit_count
    if avg is not None:
        updates["bank_reported_average_balance"] = avg
        updates["bank_reported_average_label"] = "Average ledger balance"
    if service is not None:
        updates["stated_service_charge"] = None

    repaired = stmt.model_copy(update=updates) if updates else stmt
    if any(t.running_balance is not None for t in repaired.transactions):
        repaired = repaired.model_copy(update={
            "transactions": [t.model_copy(update={"running_balance": None}) for t in repaired.transactions]
        })
    return repaired

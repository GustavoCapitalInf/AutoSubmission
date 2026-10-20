from __future__ import annotations

import re
from datetime import date

from .holder_name import CITY_STATE_ZIP, NO_READING, HolderReading, first_page, page_lines, read_address_line
from .money import EITHER_MINUS_SPACED, parse_amount, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import compact_whitespace, group_rows

#: Audit round 2, R2-B05 (R04 part 2): the customer-service panel's heading U.S. Bank prints right after the mailing
#: address on page 1.
_CONTACT_HEADING = re.compile(r"^To Contact U\.?\s?S\.? Bank\b", re.IGNORECASE)
#: The lines read back from the heading for the mailing line (a barcode remnant such as '%' between them).
_MAILING_LINE_WINDOW = 3
#: An attention line the bank prints before the holder's name ('ATTN: JORDAN SAMPLE CONTOSO LLC' reads no person).
_ATTENTION_PREFIX = re.compile(r"^(?:ATTN|ATTENTION)\b:?\s*", re.IGNORECASE)


def _holder_reading(markdown: str) -> HolderReading:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name from the mailing line U.S. Bank prints before page 1's
    'To Contact U.S. Bank' panel: the nearest line within _MAILING_LINE_WINDOW lines before it that closes on a state
    and ZIP, without the address (analysis.holder_name.read_address_line, which drops an ATTN contact after the name).
    A line that opens on an attention contact names no holder we can place: NO_READING. `account_name` keeps the
    product. Owner ruling 2026-10-02 (Q10), audit round 2, R2-OW10: with the account title that line prints after the
    name (never the contact, except a contact whose words are the premium-trust designation itself, which is the
    account's title in any spacing: audit round 3, R3-B11, R3-61 and its review round 1)."""
    lines = page_lines(first_page(markdown))
    anchor = next((index for index, line in enumerate(lines) if _CONTACT_HEADING.match(line)), None)
    if anchor is None:
        return NO_READING
    for line in reversed(lines[max(0, anchor - _MAILING_LINE_WINDOW):anchor]):
        if CITY_STATE_ZIP.search(line):
            return NO_READING if _ATTENTION_PREFIX.match(line) else read_address_line(line)
    return NO_READING

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_DATE_RE = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}"
_MONEY_RE = r"\$?\s*[\d,]+\.\d{2}-?"

#: An Account Summary category line, read as the grid prints it:
#: `<category> [<# items>] <amount>[-]`. The category NAME is read, not chosen
#: from a memorized list, because U.S. Bank prints more than one summary
#: vocabulary — the business grid itemizes `Customer Deposits` / `Other
#: Deposits` / `Card Deposits` / `Card Withdrawals` / `Other Withdrawals` /
#: `Checks Paid`, the consumer grid folds every inflow into a single
#: `Deposits / Credits`. A memorized vocabulary matched nothing on a consumer
#: statement and the parser declined the document whole.
#:
#: The `# Items` cell is OPTIONAL because the consumer grid does not print a
#: count column at all (it prints no `# Items` heading either). A count that is
#: not printed is not a zero; see `_direction_count`.
#:
#: The DIRECTION of a category is deliberately not encoded: the summary prints a
#: trailing minus on every outflow line, so the sign is read from the grid.
#:
#: The summary is the index to the ledger: whichever categories a statement
#: prints are exactly the sections it itemizes, so this one reading drives both
#: the stated totals and which detail sections are collected.
_SUMMARY_CATEGORY_RE = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z /&'.-]*?)\s+(?:(?P<count>\d+)\s+)?"
    r"(?P<amount>[\d,]+\.\d{2})(?P<minus>-?)(?![\d.])"
)

#: Checks are the one category whose detail sections are not printed under the
#: category's own name: the summary says `Checks Paid` and the ledger presents
#: them by the MANNER of presentation — `Checks Presented Conventionally` and,
#: when the statement has any, `Checks Presented Electronically`. Both roll up
#: to the single `Checks Paid` figure, so both feed one category. Matching the
#: manner rather than enumerating manners is what lets a statement that
#: itemizes electronic cheques be read at all; a one-heading-per-category map —
#: which is what this parser had — dropped the electronic block's rows and then
#: refused the document on its own section-total check.
_CHECKS_CATEGORY = "Checks Paid"
_CHECKS_SECTION_RE = re.compile(r"^Checks Presented\b")

#: A row begins where the printed grid begins one: a physical line whose first
#: cell is the Date column, optionally preceded by the row's own number column
#: (the check number in `Checks Presented Conventionally`, the deposit ticket
#: number in `Customer Deposits`) and its gap marker.
_ROW_START_RE = re.compile(r"^(?:(\d{1,10})(\*?)\s+)?(" + _DATE_RE + r")\b\s*(.*)$")

#: U.S. Bank prints the numbered sections in several column groups per physical
#: line, so one line can carry four printed rows. A row ends at its Amount cell,
#: so the seam is an amount followed by the next row's number-or-date cell.
_SEAM_RE = re.compile(
    r"(?<=\.\d{2})\s+(?=(?:\d{1,10}\*?\s+)?" + _DATE_RE + r"\b)"
    r"|(?<=\.\d{2}-)\s+(?=(?:\d{1,10}\*?\s+)?" + _DATE_RE + r"\b)"
)

#: Grid furniture inside a section: the column header (reprinted for every card
#: sub-block and after every page break), the card sub-block heading, and the
#: bank's own per-card subtotal. Each closes the row above it and opens nothing.
_ROW_FURNITURE_RE = re.compile(
    r"^(?:Date Description of Transaction|Number Date Ref Number Amount"
    r"|Check Date Ref Number Amount|Card Number:"
    r"|Card \S+ (?:Deposit|Withdrawals) Subtotal)"
)

#: What ends a detail section: the bank's own printed total for it, the checks
#: sections' differently-worded per-manner subtotals and the gap-marker
#: footnote, a page break (the section re-enters at its `(continued)` heading),
#: the page footer, and the headings of the blocks that follow the ledger.
#: `<Manner> Checks Paid (n)` closes one manner's block; the category's own
#: `Total Checks Paid` line is closed by the generic `Total <category>` rule.
_CHECKS_TOTAL_RE = re.compile(r"^[A-Za-z]+ Checks Paid \(\d+\)")
_SECTION_END_PREFIXES = (
    "--- Page",
    "Products and services available",
    "This page intentionally",
    "Balance Summary",
    "Account Summary",
    "* Gap in check sequence",
)


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_SPACED)


def _iso(month_day: str, year: int) -> str:
    month, day = month_day.split()
    return date(year, _MONTHS[month], int(day)).isoformat()


def _full_date_pattern(prefix: str = "") -> str:
    return (
        rf"(?P<{prefix}month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        rf"(?P<{prefix}day>\d{{1,2}}),\s+(?P<{prefix}year>\d{{4}})"
    )


_PERIOD_LABEL_RE = re.compile(r"Statement Period:?")
_PERIOD_START_RE = re.compile(_full_date_pattern())
_PERIOD_END_RE = re.compile(r"through\s+" + _full_date_pattern())
_ADJACENT_PERIOD_RE = re.compile(
    _full_date_pattern() + r"\s+through\s+" + _full_date_pattern("end_")
)

#: How far past the `Statement Period` label the period's two halves can be
#: printed. The label, the start date and `through <end>` are one column of the
#: page header; flattening a page interleaves the neighbouring columns' lines
#: between them, so the halves are adjacent in the text only by luck.
_PERIOD_WINDOW = 600


def _full_date(m: re.Match[str], prefix: str = "") -> date:
    return date(
        int(m.group(f"{prefix}year")),
        _MONTHS[m.group(f"{prefix}month")],
        int(m.group(f"{prefix}day")),
    )


def _span(start: date, end: date) -> tuple[str, str, int] | None:
    if end < start:
        return None
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _period(markdown: str) -> tuple[str, str, int] | None:
    """The period the bank prints, read from its own `Statement Period` label.

    Reading from the LABEL is what makes a single-page statement readable. The
    label, the start date and `through <end>` are one column of the page header;
    flattening a page interleaves the neighbouring columns' lines between them,
    so the two halves are adjacent in the text only by luck. A multi-page
    statement reprints the header on every page and somewhere in those repeats
    the halves land together — a one-page statement gets exactly one printing to
    be lucky in, and when it is not, the whole document was declined.

    The bare `<start> through <end>` pair is still read when no label is printed
    above one, so this is strictly the older reading plus the interleaved case.
    """
    for label in _PERIOD_LABEL_RE.finditer(markdown):
        window = markdown[label.end(): label.end() + _PERIOD_WINDOW]
        opening = _PERIOD_START_RE.search(window)
        if opening is None:
            continue
        closing = _PERIOD_END_RE.search(window, opening.end())
        if closing is None:
            continue
        span = _span(_full_date(opening), _full_date(closing))
        if span is not None:
            return span
    adjacent = _ADJACENT_PERIOD_RE.search(markdown)
    if adjacent is None:
        return None
    return _span(_full_date(adjacent), _full_date(adjacent, "end_"))


#: The block U.S. Bank prints immediately above every Account Summary:
#:
#:     <PRODUCT NAME>
#:     Member FDIC
#:     U.S. Bank National Association     <- these two are printed in either
#:     Account Number 1-575-0037-6890     <- order, depending on the layout
#:
#: The product name is the line that OPENS that block, and reading it is the
#: only way to publish the account's actual name: this parser serves at least
#: five U.S. Bank products (Silver, Gold and Platinum business accounts, the
#: unprefixed `SILVER BUSINESS CHECKING` layout, and consumer Smartly
#: Checking), and it used to publish one memorized product name on all of them
#: — wrong on 36 of the 40 documents it had validated.
#:
#: Anchoring on the whole block rather than on `Member FDIC` alone is load
#: bearing: `Member FDIC` is also printed as the footer of the credit-bureau
#: disclosure page, above which the nearest line is disclosure prose.
_HEADER_FURNITURE = ("Member FDIC", "U.S. Bank National Association")
_ACCOUNT_NUMBER_LINE_RE = re.compile(r"^Account Number\b")

#: What a product line LOOKS like, as against a sentence. U.S. Bank sets its
#: product register in capitals — `U.S. BANK SILVER - BUSINESS CHECKING`,
#: `PLATINUM BUSINESS MONEY MARKET`, `U.S. BANK SMARTLY CHECKING` — so a line
#: carrying lower-case words is prose, not a product.
#:
#: Checking the SHAPE and not merely the position is what stops the anchor
#: publishing whatever happens to sit above the header block when the product
#: line is missing: the page that precedes an Account Summary can be a wall of
#: disclosure, and a marketing sentence published as the account's name is a
#: worse answer than admitting the product was not printed.
_PRODUCT_LINE_RE = re.compile(r"[A-Z0-9][A-Z0-9 .&'/-]*[A-Z0-9]")
_PRODUCT_LINE_MAX = 60


def _looks_like_a_product(line: str) -> bool:
    return (
        len(line) <= _PRODUCT_LINE_MAX
        and any(character.isalpha() for character in line)
        and bool(_PRODUCT_LINE_RE.fullmatch(line))
    )


def _product_name(markdown: str) -> str | None:
    lines = [line for line in map(compact_whitespace, markdown.splitlines()) if line]
    for index, line in enumerate(lines):
        if line != "Account Summary":
            continue
        cursor, saw_member = index - 1, False
        while cursor >= 0 and index - cursor <= len(_HEADER_FURNITURE) + 1:
            above = lines[cursor]
            if above in _HEADER_FURNITURE:
                saw_member = saw_member or above == "Member FDIC"
            elif not _ACCOUNT_NUMBER_LINE_RE.match(above):
                break
            cursor -= 1
        if saw_member and cursor >= 0 and _looks_like_a_product(lines[cursor]):
            return lines[cursor]
    return None


def _summary(markdown: str) -> dict | None:
    """The printed Account Summary, read as the grid U.S. Bank prints.

    The block is `Beginning Balance`, then one `<category> <# items> <amount>`
    line per category the statement has activity in — outflows carrying the
    bank's trailing minus — then `Ending Balance`. Reading the categories rather
    than three memorized ones is what makes the stated totals complete.
    """
    m = re.search(
        r"Beginning Balance on \w+ \d+\s+\$\s*(?P<open>[\d,]+\.\d{2}-?)"
        r"(?P<categories>.*?)"
        r"Ending Balance on\s+\w+ \d+,\s+\d{4}\s+\$\s*(?P<close>[\d,]+\.\d{2}-?)",
        markdown,
        re.DOTALL,
    )
    if not m:
        return None
    # `Number of Days in Statement Period` is an OPTIONAL summary line, like the
    # interest line below and like the categories themselves: the business
    # layouts that print no `# Items` column print no days line either. Treating
    # it as required refused 11 otherwise-complete documents over a figure the
    # printed period already states — and `parse_us_bank_statement` has always
    # had that fallback, so nothing new is being inferred here.
    days = re.search(r"Number of Days in Statement Period\s+(\d+)", markdown)
    interest = re.search(r"Interest Earned this Period\s+\$\s*([\d,]+\.\d{2})", markdown)
    categories: list[tuple[str, int | None, float]] = []
    for c in _SUMMARY_CATEGORY_RE.finditer(m.group("categories")):
        amount = read_money(c.group("amount"), _money) or 0.0
        count = c.group("count")
        categories.append(
            (
                c.group("name").strip(),
                int(count) if count is not None else None,
                -amount if c.group("minus") else amount,
            )
        )
    if not categories:
        return None
    return {
        "beginning": read_money(m.group("open"), _money) or 0.0,
        "ending": read_money(m.group("close"), _money) or 0.0,
        "days": int(days.group(1)) if days else None,
        "categories": categories,
        # Interest is an OPTIONAL summary line, exactly like the optional
        # categories above: a non-interest-bearing account simply does not print
        # one. Discovery found 36 documents whose summary omits it, and
        # dereferencing the unmatched regex raised AttributeError out of the
        # parser. No printed interest is zero interest — the same reading the
        # categories take, and one reconciliation independently checks.
        "interest": (read_money(interest.group(1), _money) or 0.0) if interest else 0.0,
    }


def _section_lines(markdown: str, categories: list[str]) -> dict[str, list[str]]:
    """The lines printed inside each summary category's detail section(s).

    Keyed by CATEGORY, not by heading, because one category can be itemized
    under more than one heading — cheques are presented conventionally and
    electronically, under a heading each, and both roll up to the summary's
    single `Checks Paid` figure.

    A heading owns its line, so a summary line or a sentence of disclosure prose
    that happens to contain the heading's words never opens a section. A page
    break leaves the section and its `(continued)` heading re-enters it, which
    is what keeps the reprinted letterhead out of the ledger.
    """
    wanted = set(categories)
    sections: dict[str, list[str]] = {name: [] for name in wanted}
    current: str | None = None
    for raw in markdown.splitlines():
        line = compact_whitespace(raw)
        if not line:
            continue
        heading = line[: -len(" (continued)")] if line.endswith(" (continued)") else line
        if heading in wanted:
            current = heading
            continue
        if _CHECKS_CATEGORY in wanted and _CHECKS_SECTION_RE.match(heading):
            current = _CHECKS_CATEGORY
            continue
        if current is None:
            continue
        if (
            line.startswith(f"Total {current} ")
            or _CHECKS_TOTAL_RE.match(line)
            or line.startswith(_SECTION_END_PREFIXES)
        ):
            current = None
            continue
        sections[current].append(line)
    return sections


_TRAILING_MONEY_RE = re.compile(_MONEY_RE + r"\s*$")
#: Audit B10 (I12): the originator field an incoming wire prints below its
#: amount (`ORG=<sender>`).
_ORIGINATOR_LINE_RE = re.compile(r"(?<![A-Z0-9])ORG=")
#: Audit B10 (review round 1): the next wire field after ORG= (`BNF=`, `OBI=`,
#: `REF=` ...), which ends the originator's own field.
_NEXT_WIRE_FIELD_RE = re.compile(r"(?<![A-Z0-9])[A-Z]{2,5}=")


def _originator_field(rest: str) -> str | None:
    """Audit B10 (I12; review round 1): the sender an incoming wire prints in
    its ORG= field below the amount, or None when the field names nobody.

    `rest` is what the row printed after its amount, one printed line per
    line. The field wraps the sender's name and its address together onto the
    lines below (`ORG=<name>` / `INC. <number> <street>`), so the sender is
    the field's text up to the next wire field and up to the street number
    (the first all-digit token after a name word; a numbered company's
    leading number is its name). An ORG= that prints nothing on its own line
    names nobody: its address is never read as the sender."""
    found = _ORIGINATOR_LINE_RE.search(rest)
    if found is None:
        return None
    field = rest[found.end():]
    following = _NEXT_WIRE_FIELD_RE.search(field)
    if following is not None:
        field = field[: following.start()]
    if not field.split("\n", 1)[0].strip():
        return None
    words: list[str] = []
    for token in field.split():
        if token.isdigit() and any(not word.isdigit() for word in words):
            break
        words.append(token)
    return f"ORG={' '.join(words)}" if any(not word.isdigit() for word in words) else None


def _amount_cell(parts: list[str]) -> tuple[str, int] | None:
    """The row's Amount cell: `(text, offset in " ".join(parts))`.

    The Amount column is printed right-aligned and last, so the cell is the
    money token that TERMINATES a printed line — and the first such token in
    the row, because everything after it is the description continuing. That
    distinction is what a foreign-currency row needs: the bank prints
    `Exchg Amt: $54.63 Orig Curr:936.38` on a continuation line, so a
    "last money token" rule reads the original-currency figure as the amount,
    and a "last line-terminating token" rule reads it too.

    The fallback — the last money token anywhere in the row — is for a row
    whose amount cell is followed on its own line by text the flattening moved,
    and it is only ever reached when no line in the row ends in money.
    """
    body = " ".join(parts)
    offset = 0
    for part in parts:
        m = _TRAILING_MONEY_RE.search(part)
        if m:
            return m.group(0), offset + m.start()
        offset += len(part) + 1
    tokens = list(re.finditer(_MONEY_RE, body))
    if not tokens:
        return None
    return tokens[-1].group(0), tokens[-1].start()


def _rows(lines: list[str], *, year: int, sign: int) -> list[Transaction]:
    pieces: list[str] = []
    for line in lines:
        pieces.extend(compact_whitespace(part) for part in _SEAM_RE.split(line))
    txns: list[Transaction] = []
    for group in group_rows(
        pieces, starts_row=_ROW_START_RE.match, ends_row=_ROW_FURNITURE_RE.match
    ):
        opener = _ROW_START_RE.match(group[0])
        if opener is None:  # pragma: no cover - group_rows only opens a row here
            continue
        number, marker, month_day, head = opener.groups()
        parts = [part for part in [head, *group[1:]] if part]
        cell = _amount_cell(parts)
        if cell is None:
            continue
        amount_text, cut = cell
        amount = abs(read_money(amount_text, _money) or 0.0) * sign
        if number is not None:
            # A numbered row's own number is the description the bank printed
            # for it; the Ref Number that follows is the bank's internal
            # tracing id and is not a description.
            description = f"Check {number}{marker}"
        else:
            description = " ".join(parts)[:cut]
            if sign > 0:
                # Audit B10 (I12): an incoming wire prints its sender on the
                # continuation lines BELOW its amount (`ORG=<sender>`, the
                # name wrapping onto the next line with the start of its
                # address), so the row's ORG= field is read
                # (`_originator_field`); nothing else printed after a credit's
                # amount is kept. A debit keeps its description until the
                # owner admits the debit readings (G7). The parts are joined
                # with line breaks here, which keeps every offset of the
                # space-joined row (`cut`) and the field's own line.
                sender = _originator_field("\n".join(parts)[cut + len(amount_text):])
                if sender is not None:
                    description = f"{description} {sender}"
        txns.append(
            Transaction(
                date=_iso(month_day, year),
                description=compact_whitespace(description),
                amount=round(amount, 2),
                direction="credit" if sign > 0 else "debit",
            )
        )
    return txns


def _direction_count(
    categories: list[tuple[str, int | None, float]], *, credit: bool
) -> int | None:
    """The bank's stated item count for one direction, or None if unstated.

    The count published for a direction is the sum of the `# Items` cells of
    that direction's categories — the same scope `count_semantics` surveyed and
    promoted to comparable for this parser, unchanged.

    The consumer grid prints no count column at all. A count that was never
    printed is NOT zero, and publishing zero would turn a document the bank
    says nothing about into one that claims it had no deposits — so a direction
    whose categories are not all counted publishes nothing, and the stated-count
    check reads that as `not_printed` rather than comparing against a fiction.

    A direction with no categories at all sums to zero here, which mirrors the
    zero total the same absence produces in `stated_total_credits` /
    `stated_total_debits`: the grid states its own identity, so a direction it
    itemizes nothing in is a direction that had no activity.
    """
    counts = [
        count
        for _, count, amount in categories
        if (amount > 0 if credit else amount < 0)
    ]
    if any(count is None for count in counts):
        return None
    return sum(counts)


DETECTION_MARKERS = (
    required("bank_name", lambda t: "U.S. Bank National Association" in t),
    required("section", lambda t: "Account Summary" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_us_bank_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    summary = _summary(markdown)
    if period is None or summary is None:
        return None

    categories = summary["categories"]
    credits = sum(amount for _, _, amount in categories if amount > 0)
    debits = -sum(amount for _, _, amount in categories if amount < 0)
    # The summary states its own identity, so our reading of it can be checked
    # against the statement itself: beginning + every category = ending. A
    # category we failed to read makes this miss by exactly that category, so
    # refusing here is what stops an incomplete summary being published as a
    # complete one.
    if abs(summary["beginning"] + credits - debits - summary["ending"]) > 0.02:
        return None

    period_start, period_end, period_days = period
    holder = _holder_reading(markdown)
    stmt = Statement(
        bank="U.S. Bank",
        account_name=_product_name(markdown),
        holder_name=holder.name,
        account_title=holder.title,
        period_start=period_start,
        period_end=period_end,
        days_in_period=int(summary.get("days") or period_days),
        beginning_balance=float(summary["beginning"]),
        ending_balance=float(summary["ending"]),
        stated_total_credits=credits,
        stated_total_debits=debits,
        stated_credit_count=_direction_count(categories, credit=True),
        stated_debit_count=_direction_count(categories, credit=False),
        stated_interest_paid=float(summary["interest"]),
    )
    acct = re.search(r"Account Number\s+([0-9 -]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1).strip()

    year = int(period_end[:4])
    sections = _section_lines(markdown, [name for name, _, _ in categories])
    txns: list[Transaction] = []
    for name, _, amount in categories:
        rows = _rows(sections[name], year=year, sign=1 if amount > 0 else -1)
        # Each category prints its own total, so each section is checkable on
        # its own before anything is published. Failing here means the detail we
        # read does not account for the money the bank says is in that section.
        if abs(sum(t.amount for t in rows) - amount) > 0.02:
            return None
        txns.extend(rows)

    if not txns:
        return None
    if abs(sum(t.amount for t in txns if t.amount > 0) - stmt.stated_total_credits) > 0.02:
        return None
    if abs(sum(abs(t.amount) for t in txns if t.amount < 0) - stmt.stated_total_debits) > 0.02:
        return None
    stmt.transactions = txns
    return stmt

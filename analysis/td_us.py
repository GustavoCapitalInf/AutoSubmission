from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day_strict
from .money import PARENS_OR_LEADING_MINUS, parse_amount, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _money(value: str | None) -> float | None:
    return parse_amount(value, PARENS_OR_LEADING_MINUS)


def _period(markdown: str) -> tuple[str, str] | None:
    m = re.search(
        r"Statement Period:\s+([A-Z][a-z]{2})\s+(\d{2})\s+(\d{4})-([A-Z][a-z]{2})\s+(\d{2})\s+(\d{4})",
        markdown,
    )
    if not m:
        return None
    sm, sd, sy, em, ed, ey = m.groups()
    return (
        date(int(sy), _MONTHS[sm], int(sd)).isoformat(),
        date(int(ey), _MONTHS[em], int(ed)).isoformat(),
    )


def _summary(markdown: str, stmt: Statement) -> Statement:
    text = re.sub(r"\s+", " ", markdown)
    # Every balance row of this summary can print negative — TD writes an
    # overdrawn figure as a leading minus, the same way it already writes the
    # closing one. A pattern that cannot stand next to the sign does not read a
    # smaller number, it reads nothing: the field goes None and (:196) discards
    # the document. `_money` has parsed a leading minus all along.
    fields = {
        "beginning_balance": r"Beginning Balance\s+(-?[\d,]+\.\d{2})",
        "bank_reported_average_balance": r"Average Collected Balance\s+(-?[\d,]+\.\d{2})",
        "days_in_period": r"Days in Period\s+(\d+)",
        "ending_balance": r"Ending Balance\s+(-?[\d,]+\.\d{2})",
    }
    updates: dict[str, float | int | str] = {}
    for key, pattern in fields.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        updates[key] = int(m.group(1)) if key == "days_in_period" else (read_money(m.group(1), _money) or 0.0)
        if key == "bank_reported_average_balance":
            updates["bank_reported_average_label"] = "Average Collected Balance"

    credits = 0.0
    debits = 0.0
    for label in ("Deposits", "Electronic Deposits", "Other Credits"):
        label_pattern = r"(?<!Electronic )\bDeposits\b" if label == "Deposits" else re.escape(label)
        m = re.search(rf"{label_pattern}\s+([\d,]+\.\d{{2}})", text, re.IGNORECASE)
        if m:
            credits += abs(read_money(m.group(1), _money) or 0.0)
    for label in ("Checks Paid", "Electronic Payments", "Other Withdrawals", "Service Charges"):
        m = re.search(rf"\b{re.escape(label)}\s+([\d,]+\.\d{{2}})", text, re.IGNORECASE)
        if m:
            amount = abs(read_money(m.group(1), _money) or 0.0)
            debits += amount
            if label == "Service Charges":
                updates["stated_service_charge"] = amount
    updates["stated_total_credits"] = round(credits, 2)
    updates["stated_total_debits"] = round(debits, 2)
    return stmt.model_copy(update=updates) if updates else stmt


#: The seven headings TD prints over `DAILY ACCOUNT ACTIVITY`, in the order the
#: statement prints them. They are the bank's own section legend — not a
#: merchant or counterparty vocabulary — and they appear TWICE on every
#: statement: once in `ACCOUNT SUMMARY` as `<heading> <total>`, and once as the
#: heading of the detail section itself.
_SECTION_HEADINGS = (
    "Deposits", "Electronic Deposits", "Other Credits",
    "Checks Paid", "Electronic Payments", "Other Withdrawals", "Service Charges",
)
#: A money token sitting on the rest of the heading's own line. That is what
#: makes an occurrence the SUMMARY line (`<heading> <total>`) rather than a
#: section heading: the detail heading carries no figure of its own, and on a
#: scan it stands alone with whatever Tesseract left beside it.
_MONEY_ON_THE_SAME_LINE = r"(?![^\S\n]*\$?-?[\d,]+\.\d{2})"
#: ...and the column legend the bank prints under every detail heading, which
#: is the second half of the same discriminator. It is matched on `POSTING`
#: alone (and on the cheque section's own legend) because that is the part of
#: it Tesseract keeps: across the scanned statements of this family the rest of
#: the line arrives as `POSTING BATE DESCRIPTION AGRCUNT`, `POSTING DATE
#: DESCRUPTION SSROLINT` and `POSTING DATE ?- DESCRIPTION AMOUNT`, and
#: requiring the legend verbatim discarded whole sections over it.
#:
#: The WINDOW is what keeps the page footer from opening a section: `Bank
#: Deposits FDIC insured | TD Bank, N.A. ...` matches the `Deposits` heading
#: (the existing `(?<!Electronic )` guard is about the other heading, not this
#: one), and before this the verbatim legend was the only thing stopping it. A
#: real heading's legend is a line or two below it; the footer's nearest
#: `POSTING` is a page away.
_LEGEND_WITHIN = r"(?=.{0,40}?(?:POSTING|No\. ?Checks|DATE SERIAL NO))"
#: A heading opens a section; the same words inside a sentence do not. TD's
#: cheque legend carries the footnote `*Indicates break in serial sequence or
#: check processed electronically and listed under Electronic Payments`, whose
#: last two words are a section heading followed — within the window above — by
#: the legend `DATE SERIAL NO. AMOUNT`. A heading is preceded by a line break,
#: by `DAILY ACCOUNT ACTIVITY`, or by the previous section's `Subtotal:
#: <total>`; never by a lower-case word.
#:
#: `(?-i: ... )` because the heading itself is matched case-insensitively and
#: the whole content of this rule is a case distinction: under `IGNORECASE` the
#: class also matches `Y`, and `DAILY ACCOUNT ACTIVITY Electronic Deposits` —
#: the flattened text layer's own way of opening the detail block — is rejected
#: as prose.
_NOT_MID_SENTENCE = r"(?-i:(?<![a-z])(?<![a-z] ))"
#: The line the bank closes each detail section with.
_SUBTOTAL_RE = re.compile(r"Subtotal:\s*(?P<total>[\d,]+\.\d{2})")


def _heading_pattern(heading: str) -> str:
    """The heading as printed, at the start of its own line."""
    if heading == "Deposits":
        return r"(?<!Electronic )\bDeposits\b"
    return re.escape(heading)


def _section(markdown: str, heading: str) -> tuple[str, float | None]:
    """One detail section's body and the `Subtotal:` the bank printed under it.

    Two properties this has to have, and did not.

    **It may not cross into another section.** The body used to be an
    unconstrained `.*?` up to the first `Subtotal:`, so a section whose OWN
    subtotal line came through mangled ran on to the NEXT section's — taking
    that section's rows with it and reporting that section's figure as its
    total. Measured over the 40 archive documents of this family: 7 such
    bindings in 5 documents, one of them a plain heading-to-heading crossing
    (W3 §WITHHELDTD). The body is now tempered against every OTHER heading, so
    a section with no readable subtotal of its own matches nothing and is
    skipped — the rows it held are lost, `reconcile` measures the shortfall
    against the bank's stated totals, and the document fails closed there.
    A reprint of THIS section's own heading (`... (continued)`, printed at
    every page break) is not another section and is deliberately admitted.

    **The column legend is furniture, not a gate.** Requiring
    `POSTING DATE DESCRIPTION AMOUNT` immediately after the heading discarded
    whole sections over OCR noise beside the heading or inside the legend
    itself (`... ARMOUNT`, `DESCRUPTION SSROLINT`, a stray glyph between the
    two lines) — 8 printed sections missed across the same 40 documents, every
    one of them on a document the ADB already refused. The legend now sits in
    the body, where the row reader steps over it exactly as it steps over the
    page furniture already there, and the summary line is excluded by the one
    thing that actually distinguishes it: it carries the section's money on the
    heading's own line.
    """
    opened = None
    for start, end, name in _heading_marks(markdown):
        if opened is None:
            if name == heading:
                opened = end
            continue
        if name != heading:                     # the next section starts here
            return _closed(markdown[opened:start])
    if opened is None:
        return "", None
    return _closed(markdown[opened:])


def _closed(slice_: str) -> tuple[str, float | None]:
    """A section slice cut back to the `Subtotal:` the bank printed under it."""
    m = _SUBTOTAL_RE.search(slice_)
    if not m:
        return "", None
    return slice_[:m.start()], abs(read_money(m.group("total"), _money) or 0.0)


def _heading_marks(markdown: str) -> list[tuple[int, int, str]]:
    """Every detail-section heading in the document, in printed order.

    Linear and computed once per lookup rather than expressed as a regex that
    tempers `.` against six alternatives: the tempered form is quadratic in the
    document, and on the 15k-character scans of this family it made a parse
    take minutes.
    """
    marks: list[tuple[int, int, str]] = []
    for heading in _SECTION_HEADINGS:
        pattern = (_NOT_MID_SENTENCE + _heading_pattern(heading)
                   + _MONEY_ON_THE_SAME_LINE + _LEGEND_WITHIN)
        for m in re.finditer(pattern, markdown, re.IGNORECASE | re.DOTALL):
            marks.append((m.start(), m.end(), heading))
    marks.sort()
    return marks


def _line_items(section_text: str, *, year: int, sign: int) -> list[Transaction]:
    expanded = re.sub(r"\s+(?=\d{2}/\d{2}\s+)", "\n", section_text)
    lines = [line.strip() for line in expanded.splitlines()]
    txns: list[Transaction] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        start = re.match(r"^(\d{2}/\d{2})\s+(.+)", line)
        if not start:
            idx += 1
            continue
        date_text = start.group(1)
        parts = [start.group(2)]
        idx += 1
        while idx < len(lines) and not re.match(r"^\d{2}/\d{2}\s+", lines[idx]) and not lines[idx].startswith("Subtotal:"):
            parts.append(lines[idx])
            idx += 1
        amount = _amount_from_parts(parts)
        if amount is None:
            continue
        # A row-date token of the right shape that is not a date (`42/13`, from
        # an OCR misread of a numeric column) means this is not a posting row,
        # and is skipped like a row with no readable amount. Discovery found
        # one scanned document where building a date out of it raised.
        txn_date = iso_from_month_day_strict(date_text, year)
        if txn_date is None:
            continue
        desc_parts = _description_parts(parts, amount)
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=re.sub(r"\s+", " ", " ".join(desc_parts)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _amount_from_parts(parts: list[str]) -> float | None:
    first_line_amounts = re.findall(r"\b\d[\d,]*\.\d{2}\b", parts[0])
    if first_line_amounts:
        return _money(first_line_amounts[-1])
    for part in parts[1:]:
        if re.fullmatch(r"\$?[\d,]+\.\d{2}", part.strip()):
            return _money(part)
    return None


def _description_parts(parts: list[str], amount: float) -> list[str]:
    amount_text = f"{abs(amount):,.2f}"
    out: list[str] = []
    removed = False
    for part in parts:
        if not removed:
            new = re.sub(rf"\$?{re.escape(amount_text)}\b", "", part, count=1).strip()
            if new != part:
                removed = True
            if new:
                out.append(new)
        else:
            out.append(part)
    return out


def _checks(section_text: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for mmdd, serial, amount in re.findall(r"(\d{2}/\d{2})\s+(\d+\*?)\s+([\d,]+\.\d{2})", section_text):
        # Same shaped-but-impossible-token rule as `_line_items`: a check row
        # whose date column is not a date is not a check row.
        txn_date = iso_from_month_day_strict(mmdd, year)
        if txn_date is None:
            continue
        txns.append(Transaction(
            date=txn_date,
            description=f"Check {serial}",
            amount=round(-abs(read_money(amount, _money) or 0.0), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def _parse_section(markdown: str, heading: str, *, year: int, sign: int) -> tuple[list[Transaction], float | None]:
    body, total = _section(markdown, heading)
    if total is None:
        return [], None
    if heading == "Checks Paid":
        return _checks(body, year=year), total
    return _line_items(body, year=year, sign=sign), total


DETECTION_MARKERS = (
    required("bank_name", lambda t: "TD Bank, N.A." in t),
    required("title", lambda t: "STATEMENT OF ACCOUNT" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_td_us_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    period = _period(markdown)
    if period is None:
        return None
    year = int(period[1][:4])
    stmt = Statement(bank="TD Bank", account_name="TD Business Simple Checking", period_start=period[0], period_end=period[1])
    acct = re.search(r"Primary Account #:\s*([0-9-]+)", markdown)
    if acct:
        stmt.account_number = acct.group(1)
    stmt = _summary(markdown, stmt)
    if stmt.beginning_balance is None or stmt.ending_balance is None:
        return None

    all_txns: list[Transaction] = []
    section_specs = [
        ("Deposits", 1),
        ("Electronic Deposits", 1),
        ("Other Credits", 1),
        ("Checks Paid", -1),
        ("Electronic Payments", -1),
        ("Other Withdrawals", -1),
        ("Service Charges", -1),
    ]
    for heading, sign in section_specs:
        txns, total = _parse_section(markdown, heading, year=year, sign=sign)
        if total is None:
            continue
        # Rows that do not add up to their own section's printed subtotal are
        # a defective READ OF THAT SECTION — on the scanned statements in this
        # population, Tesseract losing a row out of forty, or misreading the
        # subtotal line itself. Discarding the document over it threw away a
        # complete, self-consistent summary and every other section's exact
        # rows, and filed an OCR defect as an unclaimed layout. The rows that
        # were read are kept and the shortfall is left where the platform can
        # see it: `reconcile` measures the ledger against the bank's stated
        # totals, so an incomplete ledger fails CLOSED there — withheld or
        # review with a named coverage gap, never validated.
        #
        # This is a TRADE and the residual is exact, so it is written down
        # rather than argued away: that gate compares DIRECTION-LEVEL totals,
        # so two misreads of equal and opposite size WITHIN one direction
        # cancel and it sees nothing, where this check saw both. Nothing in the
        # 40-document population does that, and the check as written destroyed
        # 43 correct rows over a comma in one subtotal line. The capability
        # belongs in an integrity check registered for this parser, where a
        # failure reports instead of discarding — W3 §TDFIX-1 T7.1.
        all_txns.extend(txns)
    if not all_txns:
        return None
    stmt.transactions = all_txns
    return stmt

from __future__ import annotations

import re
from datetime import date, timedelta

from .date_tokens import iso_from_month_day
from .holder_name import holder_from_address_line
from .money import EITHER_MINUS_DROPPED, parse_amount, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction


def _money(value: str | None) -> float | None:
    return parse_amount(value, EITHER_MINUS_DROPPED)


#: Truist prints its currency symbol as its own cell, so the text layer emits it
#: either against the figure (`= $662.35`) or apart from it (`= $ 662.35`). The
#: gap is a printed-grid fact and carries no meaning, so every money pattern in
#: this module admits it. It is not cosmetic: the `Total checks` terminator is
#: what bounds the Checks section, and requiring the tight spelling dropped the
#: whole section — and with it every cheque — on 20 archive documents.
#:
#: The Account summary's three activity rows are read with it for the same
#: reason and no other: they are printed in the same grid as the two balance
#: rows beside them, so a statement that spells one `$ 662.35` spells them all
#: that way. Omitting it there did not lose a field, it lost the DOCUMENT — the
#: summary is the parser's entry gate, so a single un-admitted symbol returned
#: None for the whole statement.
_DOLLAR = r"\$?\s*"
#: Audit B9 (I13): the mail-routing code line Truist prints above 'Contact us': the sort fields, then the holder's name
#: and mailing address run together ('<code> <holder> <street> <city> <ST>  <ZIP>').
_MAIL_ROUTING_LINE = re.compile(
    r"^\d{3}-\d{2}-\d{2}-\d{2}\s+\d{5}(?:\s+[A-Z])?\s+\d{1,3}\s+C\s+\d{3}\s+\d{2}(?:\s+[A-Z])*\s+\d{2}\s+\d{3}\s+"
    r"(?P<rest>\S[^\n]*)$",
    re.MULTILINE,
)
_CITY_STATE_ZIP = re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\s*$")


def _holder_name(markdown: str) -> str | None:
    """Audit B9 (I13): the holder's name after Truist's mail-routing code, without the address and any contact or
    designation after the name; None without the code line or an address that closes on a state and ZIP. `account_name`
    keeps the parser's product."""
    match = _MAIL_ROUTING_LINE.search(markdown)
    if match is None or not _CITY_STATE_ZIP.search(match.group("rest")):
        return None
    return holder_from_address_line(match.group("rest"))


def _summary(markdown: str) -> tuple[Statement, int] | None:
    m = re.search(
        r"(?:TRUIST\s+)?[A-Z0-9 ]+CHECKING[^\n]*?\s+(\d{4,})\s+"
        r"Account summary Your previous balance as of (\d{2})/(\d{2})/(\d{4})\s+"
        + _DOLLAR + r"(-?[\d,]+\.\d{2})\s+"
        r"Checks\s+-\s+" + _DOLLAR + r"([\d,]+\.\d{2})\s+"
        r"Other withdrawals, debits and service charges\s+-\s+" + _DOLLAR + r"([\d,]+\.\d{2})\s+"
        r"Deposits, credits and interest\s+\+\s+" + _DOLLAR + r"([\d,]+\.\d{2})\s+"
        r"Your new balance as of (\d{2})/(\d{2})/(\d{4})\s+=\s+" + _DOLLAR
        + r"(-?[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    acct, sm, sd, sy, beginning, checks, other_debits, credits, em, ed, ey, ending = m.groups()
    start = date(int(sy), int(sm), int(sd)) + timedelta(days=1)
    end = date(int(ey), int(em), int(ed))
    stmt = Statement(
        bank="Truist",
        account_name="Checking",
        account_number=acct,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        beginning_balance=_money(beginning),
        ending_balance=_money(ending),
        stated_total_credits=abs(read_money(credits, _money) or 0.0),
        stated_total_debits=round(abs(read_money(checks, _money) or 0.0) + abs(read_money(other_debits, _money) or 0.0), 2),
    )
    return stmt, end.year


def _first_account_block(markdown: str) -> str:
    starts = list(re.finditer(
        r"(?:TRUIST\s+)?[A-Z0-9 \-]+CHECKING[^\n]*?\d{4,}\s+Account summary",
        markdown,
        re.IGNORECASE,
    ))
    for idx, start in enumerate(starts):
        next_start = starts[idx + 1].start() if idx + 1 < len(starts) else len(markdown)
        block = markdown[start.start():next_start]
        if "Account summary Your previous balance" in block:
            return block
    return markdown


def _section(block: str, heading: str, total_label: str) -> tuple[str, float | None]:
    pattern = re.compile(
        rf"{re.escape(heading)}\s+DATE .*? AMOUNT\(\$\)\s+(.*?)\s+"
        rf"{re.escape(total_label)}\s*=\s*{_DOLLAR}([\d,]+\.\d{{2}})",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(block)
    if not m:
        return "", None
    return m.group(1), abs(read_money(m.group(2), _money) or 0.0)


def _parse_dated_amount_rows(text: str, *, year: int, sign: int) -> list[Transaction]:
    text = re.sub(
        r"\s+continued\s+.*?--- Page \d+ ---\s+.*?\(continued\)\s+DATE DESCRIPTION AMOUNT\(\$\)\s+",
        " ",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    clean = re.sub(r"Â§ PAGE\s+\d+\s+OF\s+\d+\s+\d*", " ", text)
    clean = re.sub(r"\s+\d+\s+Â?§\s+", " ", clean)
    clean = re.sub(r"Page \d+ of \d+ [0-9/]+ [A-Z]{2} \d+", " ", clean)
    clean = re.sub(r"\bcontinued\b", " ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+", " ", clean).strip()
    rows = re.split(r"\s+(?=\d{2}/\d{2}\s+)", clean)
    txns: list[Transaction] = []
    for row in rows:
        m = re.match(r"^(\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s*$", row)
        if not m:
            continue
        amount = _money(m.group(3))
        if amount is None:
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=iso_from_month_day(m.group(1), year),
            description=re.sub(r"\s+", " ", m.group(2)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


#: A cheque row is `DATE [skip marker] [CHECK #] AMOUNT($)`. Both middle cells
#: are printed only when the bank has one to print: the skip marker stands apart
#: from the number in the single-column table, and a cheque the bank prints no
#: number for carries neither. The Amount cell is the money-shaped token, and it
#: is the only cell of the four that is always printed.
_CHECK_ROW_RE = re.compile(r"(\d{2}/\d{2})\s+(\*\s*)?(\d+~?\s+)?([\d,]+\.\d{2})")
#: The Checks table's column header.
_CHECK_HEADER = r"DATE CHECK # AMOUNT\(\$\)"
#: The Checks table prints one or more `DATE CHECK # AMOUNT($)` column groups on
#: its header line — three where the statement has many cheques, one where it has
#: few — and closes with its own printed total.
_CHECKS_SECTION_RE = re.compile(
    r"Checks\s+(?:" + _CHECK_HEADER + r"\s*)+(.*?)Total checks\s*=\s*"
    + _DOLLAR + r"([\d,]+\.\d{2})",
    re.IGNORECASE | re.DOTALL,
)
#: Where the table resumes after a page break the bank REPRINTS that header, so
#: a header at the end of the run of text between two rows is the printed
#: evidence that the second one is still a row of this table.
_CHECKS_RESUMED_RE = re.compile(_CHECK_HEADER + r"\s*\Z", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z]")


def _is_row_boundary(gap: str) -> bool:
    """Whether a cheque row may legitimately follow the text `gap`.

    The Checks table has three columns — DATE, CHECK #, AMOUNT($) — and prints
    no words in any of them, so between two of its rows there is normally
    nothing but cells: other rows, and the numbers-only cross-reference cells
    (`05/26 1645~`) of cheques converted electronically. The one exception is a
    page break, and the bank closes that by reprinting the column header.

    Anything else with words in it is a note ABOUT the table rather than a row
    of it, and the date it quotes is not a posting date.
    """
    return not _WORD_RE.search(gap) or bool(_CHECKS_RESUMED_RE.search(gap))


def _parse_checks(block: str, *, year: int) -> tuple[list[Transaction], float | None]:
    """The Checks table's rows and the total the bank printed under them."""
    m = _CHECKS_SECTION_RE.search(block)
    if not m:
        return [], None
    text = re.sub(r"\* indicates.*", " ", m.group(1), flags=re.IGNORECASE | re.DOTALL)
    txns: list[Transaction] = []
    cursor = 0
    for row in _CHECK_ROW_RE.finditer(text):
        gap, cursor = text[cursor:row.start()], row.end()
        # A figure quoted inside a note about the table is not a posting. The
        # sequence-gap note — `Gap in check sequence 02/28 1099 0.00` — carries
        # a date, a cheque number and an amount in that order, so the row
        # pattern matches it wherever it is printed, and it WOULD have been
        # published as a cheque for -0.00 (latent: attested on pnc, synthetic
        # for truist). Truist has no count oracle (`count_semantics`
        # UNSURVEYED, correctly), so nothing downstream saw the extra row.
        #
        # Skipping is safe because the table prints its own total: dropping a
        # row that WAS a posting breaks the identity below and withholds the
        # document rather than publishing a short ledger.
        if not _is_row_boundary(gap):
            continue
        # An optional group the bank did not print is None here, where the
        # previous `findall` read yielded "": both middle cells are optional.
        mmdd, marker, check_no, amount = row.groups(default="")
        printed_number = ("*" if marker else "") + check_no.strip()
        txns.append(Transaction(
            date=iso_from_month_day(mmdd, year),
            description=f"Check {printed_number}" if printed_number else "Check",
            amount=round(-abs(read_money(amount, _money) or 0.0), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns, abs(read_money(m.group(2), _money) or 0.0)


DETECTION_MARKERS = (
    required("bank_name", lambda t: "TRUIST" in t.upper()),
    required("section", lambda t: "Account summary Your previous balance" in t),
)

detect = make_detector(DETECTION_MARKERS)


def parse_truist_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    block = _first_account_block(markdown)
    parsed_summary = _summary(block)
    if parsed_summary is None:
        return None
    stmt, year = parsed_summary

    checks, printed_check_total = _parse_checks(block, year=year)
    other_text, other_total = _section(
        block,
        "Other withdrawals, debits and service charges",
        "Total other withdrawals, debits and service charges",
    )
    credit_text, credit_total = _section(
        block,
        "Deposits, credits and interest",
        "Total deposits, credits and interest",
    )
    other = _parse_dated_amount_rows(other_text, year=year, sign=-1)
    credits = _parse_dated_amount_rows(credit_text, year=year, sign=1)

    if other_total is None or credit_total is None:
        return None
    if abs(sum(abs(t.amount) for t in other) - other_total) > 0.02:
        return None
    if abs(sum(t.amount for t in credits) - credit_total) > 0.02:
        return None
    # The Checks table prints its own total, so the cheques are checkable against
    # the bank rather than against the residue of two other figures. Where the
    # table is printed at all, its rows must reproduce it.
    if printed_check_total is not None:
        if abs(sum(abs(t.amount) for t in checks) - printed_check_total) > 0.02:
            return None
    elif checks and stmt.stated_total_debits is not None:
        check_total = sum(abs(t.amount) for t in checks)
        expected_checks = round(stmt.stated_total_debits - other_total, 2)
        if abs(check_total - expected_checks) > 0.02:
            return None

    txns = checks + other + credits
    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    # Audit B9 (I13): the holder's name from the mailing block the whole document prints once.
    stmt.holder_name = _holder_name(markdown)
    return stmt

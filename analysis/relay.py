from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from .date_tokens import parsed_datetime
from .money import parse_decimal
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: The one printed date format this layout uses (period ends and row dates).
_DATE_FORMAT = "%b %d, %Y"


#: A transaction row's tail: the four printed columns that carry its meaning.
#: Every one of them is a fixed shape, which is what lets the label in front of
#: them be optional (see `_CONTINUATION_RE`).
_ROW_TAIL = (
    r"(?P<date>[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+"
    r"(?P<status>Settled|Returned)\s+"
    r"(?P<amount>[+-]\$[\d,]+\.\d{2})\s+"
    r"(?P<balance>-?\$[\d,]+\.\d{2})$"
)
#: The ordinary row: label and tail on one line.
_ROW_RE = re.compile(r"^(?P<label>.*?)\s+" + _ROW_TAIL)
#: The same row after its label wrapped onto the line above it. `_ROW_RE`
#: cannot match this - it requires whitespace between label and date - so a
#: wrapped row was silently invisible, and a statement missing one row fails
#: its own balance walk and is refused whole.
_CONTINUATION_RE = re.compile(r"^" + _ROW_TAIL)

#: A BLACKLIST of exactly two furniture shapes, and no more than that: the OCR
#: page separator and the platform's per-page footer. A wrapped row sitting
#: directly under either has its label on the far side of a page break, where
#: this reader cannot reach it, so the document is refused.
#:
#: Be clear about what this is NOT: it is not a positive test that the line
#: above LOOKS like a transaction label. Any other non-row line directly above
#: a wrapped row is accepted as its label, so furniture this pattern does not
#: name would be taken as a description. That is bounded - a wrong label is a
#: wrong description, never a wrong figure, because the row's own date, amount
#: and balance are read from the wrapped line itself and still have to survive
#: the balance walk - but it is a real gap. Upgrading to a positive label test
#: is a recorded residual (W3 log, §DECLINES-C DC7.6); it needs a
#: characterisation of what a label looks like across the population, which
#: this cell's three documents cannot supply.
_NOT_A_LABEL_RE = re.compile(r"^-{3} Page \d+|Page \d+ of \d+")


#: Some Relay statements embed a subset font whose ToUnicode table leaves four
#: glyphs unmapped, so characters the statement PRINTS arrive in the Unicode
#: private-use area instead: the amount signs `+` and `-`, and a pair of
#: round brackets that appear throughout the document's text.
#:
#: The two SIGNS are not assumed - they are proven by the document's own
#: arithmetic. Every row's running balance must chain exactly from the printed
#: opening balance to the printed closing balance, and the signed sums must
#: equal the printed Deposits and Withdrawals totals exactly (`Decimal`
#: equality below, no tolerance anywhere). A sign read backwards breaks that
#: chain at the first row it touches, so a mis-mapping cannot reach a
#: published number: it declines the document instead.
#:
#: The two BRACKETS are NOT certified by anything. They are an assumption, and
#: an earlier version of this comment justified them by position - "only ever a
#: matched pair around an account's last four digits" - which measurement
#: refutes: across the six documents the open and close counts do not even
#: balance in two of them (23/20, 30/27), and 10 to 20 pairs per document wrap
#: something else entirely (disclosure numerals "(10)", "(60)", "(90)", a
#: masked account "(XXXXXX-3373)", short tokens "(CD)", "(WM)").
#:
#: What bounds the risk is not position, it is REACH: no number flows through
#: these two glyphs. `(` and `)` appear in no pattern this module matches a
#: figure with - not the amount, not the balance, not the date, not
#: `Account Number:\s*([X\d-]+)` - so the only fields they can reach are a
#: row's label and the holder name, which are free text either way. A wrong
#: bracket mapping produces a cosmetically wrong description or account name
#: and cannot move a published figure. The evidence for
#: `(`/`)` is only that statements from this platform whose font maps correctly
#: print parentheses in the same construct ("Business Checking (8923) Transfer
#: From"); that is suggestive, not proof, and it is recorded as such.
#:
#: Note the sign glyphs DO reach one non-arithmetic field: `U+E088` restores
#: the hyphen in the masked account number. That glyph is the certified one.
#:
#: This lives here, at the reader, and not in `ocr/`: the mapping is a fact
#: about ONE issuer's embedded font, not about PDF text extraction. A census
#: over the archive found the private-use phenomenon recurs under other
#: issuers with entirely different codepoints and no shared meaning, so there
#: is no platform table to write - only per-issuer ones.
_PUA_GLYPHS = {
    "\ue09d": "+",
    "\ue088": "-",
    "\ue081": "(",
    "\ue082": ")",
}
_PUA_RE = re.compile("[" + "".join(_PUA_GLYPHS) + "]")


def _restore_glyphs(markdown: str) -> str:
    """Printed characters that arrived as private-use codepoints, put back."""
    return _PUA_RE.sub(lambda m: _PUA_GLYPHS[m.group(0)], markdown)


def _money(value: str) -> Decimal:
    return parse_decimal(value)


def _description(label: str, status: str, amount: Decimal) -> str:
    label = re.sub(r"\s+", " ", label).strip()
    prefix = "Returned " if status == "Returned" else ""

    transfer = re.match(r"^(.*?)\s+Transfer\s+(From|To)$", label, re.IGNORECASE)
    if transfer:
        account, direction = transfer.groups()
        return f"{prefix}Internal Account Transfer {direction.title()}: {account.strip()}"

    if label.upper().endswith(" ACH PULL"):
        entity = label[:-9].strip()
        return f"{prefix}ACH Pull: {entity}"
    if label.upper().endswith(" ACH"):
        entity = label[:-4].strip()
        direction = "Credit" if amount > 0 else "Debit"
        if amount > 0 and re.fullmatch(r"INTUIT\s+\d{6,}", entity, re.IGNORECASE):
            entity = f"Intuit Payments {entity.split()[-1]}"
        return f"{prefix}ACH {direction}: {entity}"
    if label.upper().endswith(" VISA"):
        entity = label[:-5].strip()
        kind = "Debit Card Credit" if amount > 0 else "Debit Card Purchase"
        return f"{prefix}{kind}: {entity}"
    if label.upper() == "ATM WITHDRAWAL ATM WITHDRAWAL":
        return f"{prefix}ATM Withdrawal"
    return f"{prefix}{label}".strip()


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


DETECTION_MARKERS = (
    required("platform_name", lambda t: "RELAY FINANCIALS TECHNOLOGY" in t),
    required("title", lambda t: "ACCOUNT STATEMENT" in t),
    required("opening_label", lambda t: "OPENING BALANCE" in t),
    required("closing_label", lambda t: "CLOSING BALANCE" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_relay_statement(markdown: str) -> Statement | None:
    if not detect(markdown).claims:
        return None
    # Detection runs on the document as extracted; everything after it reads
    # the characters the statement actually printed.
    markdown = _restore_glyphs(markdown)

    period = re.search(
        r"(?P<holder>[^\n|]+?)\s*\|\s*"
        r"(?P<start>[A-Z][a-z]{2}\s+\d{1,2})\s*-\s*"
        r"(?P<end>[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})",
        markdown,
    )
    summary = re.search(
        r"Opening Balance\s+\$?(?P<opening>[\d,]+\.\d{2})\s+"
        r"Closing Balance\s+\$?(?P<closing>-?[\d,]+\.\d{2})\s+"
        r"Deposits\s+\+\$?(?P<credits>[\d,]+\.\d{2})\s+"
        r"Withdrawals\s+-\$?(?P<debits>[\d,]+\.\d{2})",
        markdown,
        re.IGNORECASE,
    )
    account = re.search(r"Account Number:\s*([X\d-]+)", markdown, re.IGNORECASE)
    if not period or not summary or not account:
        return None

    # `parsed_datetime`, not `datetime.strptime`: strptime's own ValueError is
    # ``time data '<the printed date>' does not match format '...'`` and would
    # carry the printed cell across an exception boundary (W3 §PRIVACY3). The
    # `start` token is worse than a cell: it is the printed start SPLICED to
    # the printed end's year. Control flow is unchanged.
    end = parsed_datetime(period.group("end"), _DATE_FORMAT, reader="relay.end").date()
    start = parsed_datetime(
        f"{period.group('start')}, {end.year}", _DATE_FORMAT, reader="relay.start"
    ).date()
    opening = _money(summary.group("opening"))
    closing = _money(summary.group("closing"))
    credits = _money(summary.group("credits"))
    debits = _money(summary.group("debits"))

    source_rows: list[tuple[datetime, Decimal, Decimal, str]] = []
    previous_line = ""
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        match = _ROW_RE.match(line)
        if match:
            label = match.group("label")
        else:
            wrapped = _CONTINUATION_RE.match(line)
            if not wrapped:
                if line:
                    previous_line = line
                continue
            # A row whose label wrapped onto the line above. Attribute it to
            # that line only when that line can BE a label: not another row,
            # not page furniture, not already consumed. Anything else and the
            # document is refused rather than given a guessed description -
            # the balance walk below would happily accept a mislabelled row.
            if not previous_line or _NOT_A_LABEL_RE.search(previous_line):
                return None
            label, match = previous_line, wrapped
        previous_line = ""
        txn_date = parsed_datetime(match.group("date"), _DATE_FORMAT, reader="relay.row")
        amount = _money(match.group("amount"))
        balance = _money(match.group("balance"))
        description = _description(label, match.group("status"), amount)
        source_rows.append((txn_date, amount, balance, description))

    if not source_rows:
        return None

    # Relay prints newest first, including reverse posting order within a day.
    # Reversing the full row list restores the exact ledger order.
    transactions = [
        Transaction(
            date=txn_date.date().isoformat(),
            description=description,
            amount=float(amount),
            direction="credit" if amount > 0 else "debit",
            running_balance=float(balance),
        )
        for txn_date, amount, balance, description in reversed(source_rows)
    ]

    previous = opening
    for transaction in transactions:
        expected = previous + Decimal(str(transaction.amount))
        actual = Decimal(str(transaction.running_balance))
        if expected != actual:
            return None
        previous = actual
    if previous != closing:
        return None
    if sum((Decimal(str(t.amount)) for t in transactions if t.amount > 0), Decimal()) != credits:
        return None
    if -sum((Decimal(str(t.amount)) for t in transactions if t.amount < 0), Decimal()) != debits:
        return None

    holder = re.sub(r"\s+", " ", period.group("holder")).strip()
    return Statement(
        bank="Thread Bank (Relay)",
        account_name=f"{holder} - Operations",
        account_number=account.group(1),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        days_in_period=(end - start).days + 1,
        beginning_balance=float(opening),
        ending_balance=float(closing),
        stated_total_credits=float(credits),
        stated_total_debits=float(debits),
        transactions=transactions,
    )

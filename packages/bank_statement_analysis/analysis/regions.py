from __future__ import annotations

import re
from datetime import date
from html import unescape

from .date_tokens import iso_from_month_day_strict, period_from_long_dates
from .money import MINUS_CLASS, normalize_sign_glyphs, parse_money, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction
from .tables import TAG_RE, table_rows, tables_after

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_NATIVE_HEADINGS = (
    "DEPOSITS & CREDITS",
    "WITHDRAWALS",
    "FEES",
    "RETURNED CHECKS",
    "CHECKS",
    "DAILY BALANCE SUMMARY",
)


def _money(value: str) -> float | None:
    """Read one Regions cell as money, or answer None. NEVER raises.

    This is a PROBE as well as a reader. `_parse_section` walks a row's cells
    right-to-left asking "is this the amount column?" — so it is handed dates,
    check numbers, descriptions and `N/A` by design, and a cell that is not
    money is an ANSWER, not an error. Raising here would let one unreadable
    cell in one row kill a document that parses perfectly. (W3 §MG-C2 D3.)

    A refusal still does not become `0.0`: it becomes `None`, which is what
    the probe's `is not None` test needs and what the old
    `abs(parse_money(...) or 0.0)` destroyed — under that idiom a refused cell
    answered 0.0, the probe accepted it as the amount column, and the row
    published a zero. Refusal propagates; it just propagates as None here
    rather than as an exception.

    THE SIGN GLYPHS ARE THE SHARED CANON'S, not this module's. The line below
    was `value.strip().replace("–", "-")` — half of `normalize_sign_glyphs`,
    handling U+2013 and missing U+2212 (W3 §MGD MGD10 finding 3). A cell whose
    minus the generator set as a true MINUS SIGN lost it twice over: the
    `neg` test below never saw it, and the non-ASCII scrub two lines down
    deleted the glyph before `parse_money` could read it, so the cell came back
    POSITIVE.

    Its MEASURED reach was zero, and the distinction is worth keeping straight.
    The only field that WOULD keep this reader's sign is `ending_balance` in
    the `<table>` summary branch — every other consumer takes `abs()` and
    applies a section direction — and that branch cannot publish at all today:
    it builds its transactions from `tables_after` over TAG-STRIPPED text, so
    `txns` is empty and `parse_regions_statement` returns None before any
    balance ships (W3 §SIGNREADER SR10 finding 1). So this fix corrects a
    reading that reaches no published figure until that branch is repaired.
    """
    text = normalize_sign_glyphs(value.strip())
    if not re.search(r"\d+(?:\.\d{2})?", text):
        return None
    neg = text.endswith("-") or text.startswith("-")
    amount = parse_money(re.sub(r"[^0-9,.-]", "", text))
    if amount is None:
        return None
    return -abs(amount) if neg else abs(amount)


def _plain_text(markdown: str) -> str:
    text = _IMG_RE.sub("", markdown)
    text = unescape(TAG_RE.sub(" ", text))
    return re.sub(r"[ \t]+", " ", text)


def _tables_after(markdown: str, heading: str) -> list[str]:
    #: Regions repeats the bare heading on each page; no "continued" suffix.
    return tables_after(markdown, heading)


def _parse_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for table in _tables_after(markdown, heading):
        for cells in table_rows(table):
            if len(cells) < 3:
                continue
            txn_date = iso_from_month_day_strict(cells[0], year)
            if txn_date is None:
                continue
            amount_idx = next((idx for idx in range(len(cells) - 1, 1, -1) if _money(cells[idx]) is not None), None)
            if amount_idx is None:
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
    return txns


def _native_chunks(markdown: str, heading: str) -> list[str]:
    heading_re = re.escape(heading)
    start_re = re.compile(rf"(?im)^\s*{heading_re}(?:\s+\(CONTINUED\))?\s*$")
    boundary_re = re.compile(
        r"(?im)^\s*(?:"
        + "|".join(re.escape(h) for h in _NATIVE_HEADINGS)
        + r")(?:\s+\(CONTINUED\))?\s*$|^\s*Total\b|^\s*For all your banking needs\b|^\s*--- Page\b"
    )
    chunks: list[str] = []
    for match in start_re.finditer(markdown):
        start = match.end()
        end_match = boundary_re.search(markdown, start)
        chunks.append(markdown[start:end_match.start() if end_match else len(markdown)])
    return chunks


#: The trailers that can be printed under a section's LAST row, each cut off
#: the row they were flattened onto. The first two were already here; the
#: third is the sign-off this issuer prints at the foot of a page, and it is
#: the same kind of thing - printed furniture, not row text.
#:
#: Why it has to be cut rather than left in place: a row is read by an
#: ANCHORED pattern that requires the line to END in its amount
#: (`_parse_native_section`), so a footer welded onto the last row of a page
#: does not misread that row - it deletes it. Measured over the archive's
#: seven live-detected Regions documents on the native path, exactly one
#: withdrawal row per document was lost this way on three of them, which is
#: why their ledgers missed the printed `Total Withdrawals` by a single row
#: and could not reconcile to the printed closing balance. The other four
#: (all four pinned) print no row in that position and do not move.
#:
#: Institution furniture, and the SAME spelling the detector already requires
#: of every Regions statement (`DETECTION_MARKERS.issuer_footer`), named once
#: here so the two cannot drift apart.
ISSUER_FOOTER = "Thank You For Banking With Regions!"

_ROW_TRAILER_RE = re.compile(
    r"\s+Total\b|For all your banking needs\b|" + re.escape(ISSUER_FOOTER),
    re.IGNORECASE,
)


def _native_rows(markdown: str, heading: str) -> list[str]:
    rows: list[str] = []
    for chunk in _native_chunks(markdown, heading):
        chunk = re.sub(r"(?im)^\s*Date\s+Check\s+No\.\s+Amount\s*", "", chunk)
        parts = re.split(r"\s+(?=\d{2}/\d{2}\s)", chunk.strip())
        for part in parts:
            row = _ROW_TRAILER_RE.split(part.strip(), maxsplit=1)[0].strip()
            if re.match(r"^\d{2}/\d{2}\b", row):
                rows.append(row)
    return rows


def _parse_native_section(markdown: str, heading: str, *, year: int, sign: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for row in _native_rows(markdown, heading):
        m = re.match(r"^(\d{2}/\d{2})\s+(.+)\s+(\d[\d,]*\.\d{2})(?:\s+\*)?\s*$", row)
        if not m:
            continue
        txn_date = iso_from_month_day_strict(m.group(1), year)
        amount = _money(m.group(3))
        if txn_date is None or amount is None:
            continue
        signed = round(abs(amount) * sign, 2)
        txns.append(Transaction(
            date=txn_date,
            description=re.sub(r"\s+", " ", m.group(2)).strip(),
            amount=signed,
            direction="credit" if signed >= 0 else "debit",
            running_balance=None,
        ))
    return txns


def _parse_native_checks(markdown: str, *, year: int) -> list[Transaction]:
    txns: list[Transaction] = []
    for row in _native_rows(markdown, "CHECKS"):
        m = re.match(r"^(\d{2}/\d{2})\s+(\d{3,})\s+\*?\s*(\d[\d,]*\.\d{2})\b", row)
        if m:
            txn_date = iso_from_month_day_strict(m.group(1), year)
            amount = _money(m.group(3))
            description = f"Check {m.group(2)}"
        else:
            m = re.match(r"^(\d{2}/\d{2})\s+(\d[\d,]*\.\d{2})\b", row)
            if not m:
                continue
            txn_date = iso_from_month_day_strict(m.group(1), year)
            amount = _money(m.group(2))
            description = "Check"
        if txn_date is None or amount is None:
            continue
        txns.append(Transaction(
            date=txn_date,
            description=description,
            amount=round(-abs(amount), 2),
            direction="debit",
            running_balance=None,
        ))
    return txns


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return _plain_text(markdown).upper()


DETECTION_MARKERS = (
    required("bank_name", lambda t: "REGIONS" in t),
    required("summary_section", lambda t: "SUMMARY" in t),
    # Both markers above are generic enough to co-occur in another bank's
    # statement whenever Regions appears as an ACH originator - it does in all
    # three Amex documents. Require the footer Regions prints on its own
    # statements (R3_DETECTION_FINDING.md).
    required("issuer_footer", lambda t: ISSUER_FOOTER.upper() in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_regions_statement(markdown: str) -> Statement | None:
    text = _plain_text(markdown)
    if not detect(markdown).claims:
        return None
    period = period_from_long_dates(text)
    if period is None:
        return None
    year = int(period[1][:4])

    stmt = Statement(bank="Regions Bank", period_start=period[0], period_end=period[1])
    acct = re.search(r"ACCOUNT #\s*([0-9]+)", text, re.IGNORECASE)
    if acct:
        stmt.account_number = acct.group(1)
    name = re.search(r"Page 1 of \d+\s*\n([A-Z][A-Z0-9 &-]+)\s*\n[A-Z][a-z]+ \d{1,2},", text)
    if name:
        stmt.account_name = name.group(1).strip()
    else:
        name = re.search(r"\n([A-Z][A-Z0-9 &/-]+)\s*\n[A-Z][a-z]+ \d{1,2},", text)
        if name:
            stmt.account_name = name.group(1).strip()

    summary_match = re.search(r"SUMMARY\s*(<table>.*?</table>)", markdown, re.IGNORECASE | re.DOTALL)
    if not summary_match:
        stmt = repair_regions_summary(text, stmt)
        txns = []
        txns.extend(_parse_native_section(markdown, "DEPOSITS & CREDITS", year=year, sign=1))
        txns.extend(_parse_native_section(markdown, "WITHDRAWALS", year=year, sign=-1))
        txns.extend(_parse_native_section(markdown, "FEES", year=year, sign=-1))
        txns.extend(_parse_native_section(markdown, "RETURNED CHECKS", year=year, sign=1))
        txns.extend(_parse_native_checks(markdown, year=year))
        if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
            return None
        stmt.transactions = txns
        return stmt

    fees = checks = 0.0
    for cells in table_rows(summary_match.group(1)):
        if len(cells) < 2:
            continue
        label = cells[0].lower()
        amount = _money(cells[1])
        if "beginning balance" in label:
            stmt.beginning_balance = abs(amount) if amount is not None else None
        elif "deposits" in label:
            stmt.stated_total_credits = abs(amount) if amount is not None else None
        elif "withdrawals" in label:
            stmt.stated_total_debits = abs(amount) if amount is not None else None
        elif "fees" in label and amount is not None:
            fees = abs(amount)
            stmt.stated_service_charge = fees
        elif label == "checks" and amount is not None:
            checks = abs(amount)
        elif "ending balance" in label:
            stmt.ending_balance = amount
        if len(cells) >= 4 and "average balance" in cells[2].lower():
            # A RAW table cell, not a regex-guaranteed token: the label in
            # cells[2] is what was matched, and cells[3] is whatever the grid
            # put beside it — `N/A`, `--`, or nothing at all on a statement
            # that prints the row but not the figure. That is ABSENCE, and
            # absence leaves the field unset rather than either raising (which
            # would kill the document over an optional figure) or publishing a
            # 0.00 average balance nobody printed. (W3 §MG-C2 D2.)
            average = _money(cells[3])
            if average is not None:
                stmt.bank_reported_average_balance = abs(average)
                # The heading the grid actually printed, verbatim.
                stmt.bank_reported_average_label = cells[2].strip() or None
    if stmt.stated_total_debits is not None:
        stmt.stated_total_debits = round(stmt.stated_total_debits + fees + checks, 2)

    txns = []
    txns.extend(_parse_section(text, "DEPOSITS & CREDITS", year=year, sign=1))
    txns.extend(_parse_section(text, "WITHDRAWALS", year=year, sign=-1))
    txns.extend(_parse_section(text, "FEES", year=year, sign=-1))
    if not txns or stmt.beginning_balance is None or stmt.ending_balance is None:
        return None
    stmt.transactions = txns
    return stmt


def _money_after(label: str, text: str) -> float | None:
    """The summary figure printed after `label`, with Regions' trailing sign.

    The sign group is `money.MINUS_CLASS`, the same class `_money` above reads
    through `normalize_sign_glyphs`. It was a bare ASCII hyphen — the same
    absence-shaped half-opinion, on the branch that actually runs: this
    module's `<table>` path never publishes (its transactions come from
    `tables_after` over TAG-STRIPPED text and are always empty), so the native
    path below is the only one whose sign reaches a published field.

    Nothing in the archive moves on this: no live-detected Regions document
    carries U+2212, U+2013 or U+2014 anywhere in its text — all 24 print the
    ASCII hyphen and nothing else — so the widened class is inert today and
    correct the day a generator's font map changes (W3 §SIGNREADER).
    """
    m = re.search(
        label + r"\s+\$?([\d,]+(?:\.\d{2})?)(?:\s*(" + MINUS_CLASS + r"))?",
        text, re.IGNORECASE,
    )
    if not m:
        return None
    value = abs(read_money(m.group(1)) or 0.0)
    return -value if m.group(2) else value


def repair_regions_summary(markdown: str, stmt: Statement) -> Statement:
    """Normalize Regions summary fields, including trailing minus signs."""
    if "REGIONS" not in markdown.upper() or "SUMMARY" not in markdown.upper():
        return stmt

    text = unescape(re.sub(r"<[^>]+>", " ", markdown))
    beginning = _money_after(r"Beginning Balance", text)
    deposits = _money_after(r"Total Deposits & Credits", text) or _money_after(r"Deposits & Credits", text)
    withdrawals = _money_after(r"Total Withdrawals", text) or _money_after(r"Withdrawals", text)
    fees = _money_after(r"Total Fees", text) or _money_after(r"Fees", text)
    returned = _money_after(r"Total Returned Checks", text) or _money_after(r"Returned Checks", text)
    checks = _money_after(r"Total Checks", text) or _money_after(r"(?<!Returned )Checks", text)
    ending = _money_after(r"Ending Balance", text)
    average_label = "Average Monthly Statement Balance"
    avg = _money_after(average_label, text)
    if avg is None:
        average_label = "Average Balance"
        avg = _money_after(average_label, text)

    updates = {}
    if beginning is not None:
        updates["beginning_balance"] = beginning
    if ending is not None:
        updates["ending_balance"] = ending
    if deposits is not None:
        total_credits = abs(deposits) + abs(returned or 0.0)
        updates["stated_total_credits"] = round(total_credits, 2)
    if withdrawals is not None:
        total_debits = abs(withdrawals) + abs(fees or 0.0) + abs(checks or 0.0)
        updates["stated_total_debits"] = round(total_debits, 2)
        updates["stated_service_charge"] = None
    if avg is not None:
        updates["bank_reported_average_balance"] = abs(avg)
        updates["bank_reported_average_label"] = average_label
    return stmt.model_copy(update=updates) if updates else stmt

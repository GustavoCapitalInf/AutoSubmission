from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from .money import MINUS_GLYPHS, normalize_sign_glyphs, parse_decimal_mixed_separator
from .parser_registry import make_detector, required
from .schema import Statement, StatementDailyBalance, Transaction
from .tables import section_between


_MONEY = r"\d[\d,]*[\.,]\d{2}"

#: A balance slot in the summary strip. Beginning, low, average and ending are
#: BALANCES and a business account goes overdrawn, so the sign is part of the
#: printing: this account's June statement prints `Low balance -$10,816.06` and
#: its daily grid prints three negative days. The two FLOW figures
#: (`Deposits/Additions`, `Withdrawals/Subtractions`) and `Interest earned`
#: keep the unsigned pattern — this template prints them as magnitudes whose
#: direction is the label — so a signed printing of one of those declines
#: instead of being read as a magnitude.
#:
#: The class is `money.MINUS_GLYPHS`, so the em dash is NOT a sign here either
#: (W3 §MGD3, whose decisive attestation is this very family's `03-16 —
#: 39,692.35`). An em dash in a sign position therefore declines the summary
#: rather than flipping a figure the bank printed positive.
_SIGN = "[" + re.escape(MINUS_GLYPHS) + "]"
_BALANCE = rf"{_SIGN}?\s?\$?{_MONEY}"

#: OCR debris between two printed CELLS of a scanned grid: a column rule read
#: as `|`, a leader read as `—` or `_`, a stray `.`. Never a letter, a digit, a
#: currency symbol or a sign glyph — so it can swallow neither a label, nor a
#: figure, nor the sign of one. The measured need: across four consecutive
#: statements of one account the summary strip's cell boundaries print as
#: `4166 Beginning balance` three times and `4166 — Beginning balance` once,
#: and as `$4,831.08 Deposits/Additions` / `-$10,816.06  Deposits/Additions`
#: three times and `$3,304.13 | Deposits/Additions` once. They are one printed
#: strip, and a reader that admits only whitespace publishes two of the four.
_DEBRIS = r"[^\s0-9A-Za-z$" + re.escape(MINUS_GLYPHS) + r"]"

#: The gap AFTER a cell's value and before the next cell's LABEL: whitespace,
#: optionally with a run of debris in it. At least one whitespace character, so
#: it can never join two tokens the bank printed adjacent.
#:
#: Deliberately not used between a label and its own value. Debris only ever
#: appears after a value in these printings (`XXXXXX4166 — Beginning balance`,
#: `$3,304.13 | Deposits/Additions`), and a tolerance in front of a figure
#: would swallow an em dash standing in a sign position and publish
#: `—$100.00` as `+100.00` — the exact misreading W3 §MGD3 ruled against.
_GAP = rf"\s+(?:{_DEBRIS}+\s*)?"


def _columns(*labels: str) -> str:
    """A section's column-header row, tolerant of the debris between its cells.

    `Date Description Additions` and `Date —_ Description Additions` are the
    same printed row; the second is what Tesseract makes of the column rule on
    three of this account's four statements. The header row is the second half
    of every section's start pattern — the half that keeps the section masthead
    apart from the same words in the summary strip — so a reader that spells it
    as literal single spaces does not merely lose the header: it bounds the
    section from the wrong place, or not at all.

    Debris may not cross a line. The header is ONE printed row, and a gap that
    spanned lines could join a `Date` in one section's header to a
    `Description` in the next.
    """
    return rf"(?:[^\S\n]|{_DEBRIS})*".join(labels)


def _section(head: str, *labels: str) -> str:
    """A ledger section's start: its masthead on its own line, then its
    column-header row.

    The masthead starts its own line. `Deposits/Additions` is a SUFFIX of both
    `Other Deposits/ Additions` and `ACH and Electronic Deposits/Additions`,
    and `Checks` of `Total Checks paid:` — so an unanchored masthead bounds a
    section from another section's heading whenever the one it names is
    absent, which April (no plain deposit section) is the printing that makes
    real. What may precede it on its line is debris and nothing else: April
    prints `——. Other Withdrawals/Subtractions`, and since `_DEBRIS` admits no
    letter, no word of a longer heading can hide in that tolerance.

    The column-header row is what keeps the masthead apart from the same words
    in the summary strip, and it is read through `_columns`.
    """
    return rf"\n(?:[^\S\n]|{_DEBRIS})*{head}\s+" + _columns("", *labels)


@dataclass(frozen=True)
class _Row:
    date: date
    description: str
    amount: Decimal
    sequence: int


def _money(value: str) -> Decimal:
    return parse_decimal_mixed_separator(value)


def _signed(value: str) -> Decimal:
    """A summary BALANCE cell -> `Decimal`, the printed sign preserved.

    `money.parse_signed_decimal` is the same reading over `parse_decimal`; this
    template needs the sign over `parse_decimal_mixed_separator`, because its
    scans render the cents separator as a comma often enough that `_money` is
    the module's numeric reader everywhere else. The sign class is
    `money.MINUS_GLYPHS` either way, read through `normalize_sign_glyphs`
    rather than by re-spelling the glyphs here.
    """
    text = normalize_sign_glyphs(value.strip())
    negative = text.startswith("-")
    if negative:
        text = text[1:].lstrip()
    amount = _money(text)
    return -amount if negative else amount


def _clean_description(value: str) -> str:
    text = re.sub(r"^[\s=_~â€”â€“-]+", "", value)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^AGH\b", "ACH", text, flags=re.IGNORECASE)
    text = re.sub(r"^ACH GREDIT\b", "ACH Credit", text, flags=re.IGNORECASE)
    text = re.sub(r"^AGH CREDIT\b", "ACH Credit", text, flags=re.IGNORECASE)
    return text


def _rows(block: str, *, start: date, end: date, sequence: int) -> tuple[list[_Row], int]:
    output: list[_Row] = []
    line_re = re.compile(
        rf"^[^0-9\n]{{0,16}}(?P<month>\d{{2}})-(?P<day>\d{{2}})\b"
        rf"(?P<description>.*?)\s+(?P<amount>{_MONEY})\s*$"
    )
    for raw_line in block.splitlines():
        match = line_re.match(raw_line.strip())
        if not match:
            continue
        raw_month = int(match.group("month"))
        raw_day = int(match.group("day"))
        description = _clean_description(match.group("description"))
        txn_month = raw_month
        txn_day = raw_day
        if raw_month != start.month or not 1 <= raw_month <= 12:
            embedded = re.search(r"\b(20\d{2})(\d{2})(\d{2})\b", description)
            if embedded:
                _, embedded_month, embedded_day = embedded.groups()
                txn_month, txn_day = int(embedded_month), int(embedded_day)
            else:
                txn_month = start.month
        try:
            txn_date = date(end.year, txn_month, txn_day)
        except ValueError:
            continue
        if not start <= txn_date <= end:
            continue
        output.append(
            _Row(
                date=txn_date,
                description=description,
                amount=_money(match.group("amount")),
                sequence=sequence,
            )
        )
        sequence += 1
    return output, sequence


#: A row is published at the figure the text prints, or it is not published.
#:
#: This module used to hold two REPAIRS between `_rows` and the section gates
#: below — one that replaced a row's amount with its counterparty group's modal
#: amount whenever that moved the section nearer its printed total, and one that
#: rewrote a single row's amount BY the section's whole residual and kept the
#: candidate whose reconstruction best matched the daily grid. Both ran before
#: the gates, so each gate tested its own repair's objective function rather
#: than the document, and on the archive's one publishing statement of this
#: cohort three of the amounts a reader saw were parser-WRITTEN rather than
#: read. Gustavo's ruling of 2026-08-21 removed them: "Parsers must never
#: rewrite transaction amounts just to force reconciliation. Replace
#: repair-by-rewrite with discard-and-flag / fail-closed."
#:
#: FAIL CLOSED is what this template takes, and the choice is evidential rather
#: than stylistic. The defect class the repairs were built for is OCR digit
#: corruption in a scan; a section total detects it and cannot locate it. On the
#: cohort's one publishing statement the ACH debit section missed its printed
#: total by 3,001.00 and the shipped machinery needed BOTH heuristics, on two
#: different rows, to close that one gap — which is proof by construction that
#: the grid does not locate the defect to a single row. Publishing the rows as
#: printed under a flag would put a ledger with at least three known-corrupt
#: figures, and no way to say which three, in front of an underwriter, and it
#: would need the ledger-chain gate below weakened as well, because such a
#: ledger does not reach the printed ending balance. The other five sections of
#: this template have always failed closed on exactly this condition, and the
#: cohort's other three statements already refuse on it. Removing the repairs
#: makes the reader uniform: every section against its own printed total, no
#: exceptions, no amount ever written.


#: A cell of the Daily Balances grid: `mm-dd`, whitespace, and then the figure
#: — optionally carrying a SIGN from `money.MINUS_GLYPHS`, and nothing else.
#:
#: Both halves of that are load-bearing, and this family is the archive's whole
#: attestation for the strict half. `88AAC06119FC` prints
#:
#:     03-04 56,767.53   03-16 —  39,692.35   03-26 34,167.30
#:
#: where the `—` is the grid's empty-column placeholder and 39,692.35 is a
#: POSITIVE running balance between its two neighbours (W3 §MGD3). A reader
#: that lets ANYTHING stand between the date and the figure has three ways to
#: be wrong and no way to know which: it can publish the placeholder as a sign
#: and invert a balance the bank printed positive, it can bind a date to the
#: NEXT column's figure when its own is unreadable, and — the failure this
#: family actually suffered — it can carry the cell into the LEDGER as a
#: transaction of 39,692.35 (W3 §COUNTSP3). The em dash is not in
#: `MINUS_GLYPHS`, by that same ruling, so this pattern refuses the cell
#: outright: 03-16 is simply not a snapshot this reader will vouch for.
#:
#: The sign IS admitted, because it is a figure the bank printed and not
#: debris: `2E667295DFCB16BA` is an overdrawn month whose grid prints
#: `06-22 -2,209.18`, `06-23 -2,209.18` and `06-25 -3,133.90`. Reading only
#: unsigned cells drops exactly the days an underwriter most needs to see, and
#: reading them WITHOUT the sign would publish an overdraft as a balance three
#: times its true distance from zero. One class separates the two cases at a
#: glance: a sign glyph is a sign, an em dash is punctuation.
#:
#: What refusing still costs on `88AAC06119FC` is the two cells whose figure
#: the scan preceded with debris (03-02 `___57,697.72` and 03-16). They are
#: absent from `stated_daily_balances` rather than present and wrong.
_GRID_CELL = re.compile(rf"(\d{{2}})-(\d{{2}})\s+({_SIGN}?{_MONEY})")


def _daily_snapshots(block: str, *, year: int) -> dict[date, Decimal]:
    snapshots: dict[date, Decimal] = {}
    for month, day, amount in _GRID_CELL.findall(block):
        try:
            snapshots[date(year, int(month), int(day))] = _signed(amount)
        except ValueError:
            continue
    return snapshots


def _ending_by_date(opening: Decimal, rows: list[tuple[_Row, int]]) -> dict[date, Decimal]:
    balance = opening
    output: dict[date, Decimal] = {}
    for row, sign in sorted(rows, key=lambda item: (item[0].date, item[0].sequence)):
        balance += row.amount * sign
        output[row.date] = balance
    return output


#: A row of the two-column cheque grid (`Check # Amount Date Check # Amount
#: Date`). The serial is the row's leading cell and it is OPTIONAL, because on
#: this account's March statement the scan reads `4177` as `A777`.
#:
#: The three readings of that cell are not equivalent. Taking any trailing
#: digit run publishes `Check 777` — a serial the bank did not print, on a
#: cheque that cleared for $17,263.50. REQUIRING a clean serial loses the row,
#: and with it the section's agreement with the printed `Withdrawals/
#: Subtractions` total, so the whole statement declines over a damaged label.
#: What is printed and readable is the AMOUNT and the DATE — the two things the
#: ledger and the reconciliation need — so the row is published as a bare
#: `Check` and the serial is simply not asserted. The same discipline as the
#: third core processor's structural serial read (W3 §LCPERIOD), in the shape
#: this two-per-line grid takes.
#:
#: `\$` is required on the amount, and that is what lets the serial be
#: optional: without it a serial-less row's amount and the next row's serial
#: are the same shape. Every cheque amount in this family prints the symbol; a
#: printing that omitted it would lose the row and fail the debit total, which
#: is the fail-closed direction.
_CHEQUE_ROW = re.compile(
    rf"(?:(?<![0-9A-Za-z])(\d{{3,}})\s+)?\$({_MONEY})\s+(\d{{2}})-(\d{{2}})"
)


def _printed_total(markdown: str, label: str) -> Decimal | None:
    """The figure a section's own `Total ...` row prints, or None if absent.

    Every section in this template closes with its own total, and those totals
    are this reader's oracles: no section's rows are believed until they add up
    to the figure the bank printed under them. Shared so that the two sections
    a month may or may not print are read exactly like the three it always
    does — an absent section is `None` here, never a silent zero.
    """
    found = re.search(rf"{label}\s+\$?({_MONEY})", markdown, re.IGNORECASE)
    return None if found is None else _money(found.group(1))


def _prints_section(markdown: str, start: str) -> bool:
    """Whether the document prints a section's masthead and column header.

    Asked separately from `tables.section_between` because that function
    returns `""` both for "no such section" and for "the section's closing
    total is missing", and those are opposite facts: the first is a month with
    nothing to report, the second is a section whose rows this reader can see
    and cannot reconcile. Conflating them would let an unclosed section's rows
    be silently dropped from a ledger that still balanced without them.
    """
    return re.search(start, markdown, re.IGNORECASE | re.DOTALL) is not None


def detection_text(markdown: str) -> str:
    """The text this parser recognises itself in."""
    return markdown.upper()


#: The issuer's NAME is deliberately not among these, and the reason is
#: measured rather than stylistic. This account's four consecutive statements
#: are one printing; the masthead is a logo, so whether `COLUMBIA BANK` appears
#: in the text at all is a property of the SCAN and not of the document. Over
#: the four: April's logo OCRs to the name and May's does not, but May happens
#: to carry a one-off overdraft-disclosure paragraph that mentions "the
#: columbia Bank welcome booklet"; March's and June's logos OCR to
#: `sbedet eye ffgeef tLe lpg f apg gle ete` and
#: `Aun | rou ae nn nro) cell Mazo LOTT`, and neither prints the name anywhere
#: else. A required issuer name therefore claimed two of four statements of one
#: account by accidents of Tesseract and of a paragraph the bank printed twice
#: and then stopped printing.
#:
#: What replaces it is the debit ledger's heading. Be exact about what that
#: buys, because it is less than "the masthead the reader requires": this is a
#: SUBSTRING test over the upper-cased document, so it also fires on the
#: section's own closing row `Total ACH and Electronic Payments/Subtractions`
#: and on any longer phrase containing it (`Corrected ACH and Electronic
#: Payments/Subtractions`). `credits_section` has carried the identical
#: weakness since the registration was written. The claim such a document wins
#: is worthless — the reader still has to bound the section by its masthead AND
#: its column-header row and reconcile its rows against its printed total, so
#: every one of those documents declines at parse — but the marker is evidence
#: that the phrase is PRINTED, not that the section is. Measured archive-wide
#: over all 3,351 readable documents: `ACH AND ELECTRONIC PAYMENTS/
#: SUBTRACTIONS` appears in exactly the 4 statements of this cohort, so the
#: weakness is a property of the shape and not of anything the archive prints.
#:
#: What the swap does buy is the two things the card needed: the marker count
#: stays at four, so the claim score stays 0.5 and the two statements already
#: claimed keep the score they had; and the evidence moves off a logo whose
#: survival is a property of the scan.
#:
#: `MARKETPLACE CHECKING` remains, and it is the load-bearing issuer evidence
#: now that the name is gone. Census over the same 3,351: the product masthead
#: appears in 4 documents and the four markers are satisfied together by 4 —
#: the same four, this account's own statements. `DEPOSITS/ADDITIONS` appears
#: in 21 and `DAILY BALANCES` in 290, which is what makes the product name the
#: discriminating half. So "this template has one issuer" is a census result
#: rather than an assertion, and it is why this registration still publishes a
#: bank NAME the two unlabelled scans do not print.
DETECTION_MARKERS = (
    required("product", lambda t: "MARKETPLACE CHECKING" in t),
    required("credits_section", lambda t: "DEPOSITS/ADDITIONS" in t),
    required("debits_section", lambda t: "ACH AND ELECTRONIC PAYMENTS/SUBTRACTIONS" in t),
    required("daily_balances", lambda t: "DAILY BALANCES" in t),
)

detect = make_detector(DETECTION_MARKERS, detection_text)


def parse_columbia_bank_statement(markdown: str) -> Statement | None:
    upper = markdown.upper()
    if not detect(markdown).claims:
        return None

    dates = re.search(
        # The colon is optional on both labels: April's scan drops the one
        # after `Last statement` and prints the same two-line period strip.
        r"Last statement:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s+"
        r"This statement:?\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
        markdown,
    )
    summary = re.search(
        rf"Account number\s+([X\d]+){_GAP}Beginning balance\s+({_BALANCE}){_GAP}"
        rf"Low balance\s+({_BALANCE}){_GAP}Deposits/Additions\s+\$?({_MONEY}){_GAP}"
        rf"Average balance\s+({_BALANCE}){_GAP}Withdrawals/Subtractions\s+\$?({_MONEY})\s+"
        rf".*?Interest earned\s+\$?({_MONEY}){_GAP}Ending balance\s+({_BALANCE})",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    if not dates or not summary:
        return None

    previous_end = datetime.strptime(dates.group(1), "%B %d, %Y").date()
    period_end = datetime.strptime(dates.group(2), "%B %d, %Y").date()
    period_start = previous_end + timedelta(days=1)
    account, opening_raw, _low, credits_raw, average_raw, debits_raw, interest_raw, ending_raw = summary.groups()
    opening = _signed(opening_raw)
    ending = _signed(ending_raw)
    total_credits = _money(credits_raw)
    total_debits = _money(debits_raw)

    deposit_head = _section(r"Deposits/Additions", "Date", "Description", "Additions")
    deposit_block = section_between(markdown, deposit_head, r"Total Additions")
    ach_debit_block = section_between(
        markdown,
        _section(r"ACH and Electronic Payments/Subtractions",
                 "Date", "Description", "Subtractions"),
        r"Total ACH and Electronic Payments/Subtractions",
    )
    ach_credit_block = section_between(
        markdown,
        _section(r"ACH and Electronic Deposits/Additions",
                 "Date", "Description", "Additions"),
        r"Total ACH and Electronic Deposits/Additions",
    )
    # Printed only in months that have one, and only ONE of this account's four
    # statements does. Its head and its own printed total travel together: a
    # head with no total, or a total with no head, is a section this reader
    # cannot reconcile and the document declines.
    other_credit_head = _section(
        r"Other Deposits/\s*Additions", "Date", "Description", "Additions")
    other_credit_block = section_between(
        markdown, other_credit_head, r"Total Other Deposits/\s*Additions")
    other_debit_block = section_between(
        markdown,
        _section(r"Other Withdrawals/Subtractions", "Date", "Description", "Subtractions"),
        r"Total Other Withdrawals/Subtractions",
    )
    daily_block = section_between(markdown, r"Daily Balances", r"Overdraft Fee Summary")
    checks_block = section_between(
        markdown,
        _section(r"Checks", "Check #", "Amount", "Date"),
        r"\(\* Skip in check sequence",
    )
    if not all((ach_debit_block, ach_credit_block, other_debit_block, daily_block, checks_block)):
        return None

    sequence = 0
    deposits, sequence = _rows(deposit_block, start=period_start, end=period_end, sequence=sequence)
    ach_debits, sequence = _rows(ach_debit_block, start=period_start, end=period_end, sequence=sequence)
    ach_credits, sequence = _rows(ach_credit_block, start=period_start, end=period_end, sequence=sequence)
    other_credits, sequence = _rows(other_credit_block, start=period_start, end=period_end, sequence=sequence)
    other_debits, sequence = _rows(other_debit_block, start=period_start, end=period_end, sequence=sequence)

    checks: list[_Row] = []
    for check_number, amount, month, day in _CHEQUE_ROW.findall(checks_block):
        checks.append(
            _Row(
                date=date(period_end.year, int(month), int(day)),
                description=f"Check {check_number}" if check_number else "Check",
                amount=_money(amount),
                sequence=sequence,
            )
        )
        sequence += 1

    ach_debit_total = _printed_total(
        markdown, r"Total ACH and Electronic Payments/Subtractions")
    ach_credit_total = _printed_total(
        markdown, r"Total ACH and Electronic Deposits/Additions")
    other_total = _printed_total(markdown, r"Total Other Withdrawals/Subtractions")
    if ach_debit_total is None or ach_credit_total is None or other_total is None:
        return None
    # The two sections a month may or may not print. Each is read only against
    # its OWN printed total, and the two must travel together: a masthead with
    # no closing total is a section whose rows this reader can see and cannot
    # reconcile, and a closing total with no masthead is a figure with no rows
    # under it. Both refuse. The masthead is asked for directly rather than
    # inferred from an empty block, because an unclosed section produces the
    # same empty block as an absent one and the two mean opposite things.
    deposit_total = _printed_total(markdown, r"Total Additions")
    other_credit_total = _printed_total(markdown, r"Total Other Deposits/\s*Additions")
    if _prints_section(markdown, deposit_head) != (deposit_total is not None):
        return None
    if _prints_section(markdown, other_credit_head) != (other_credit_total is not None):
        return None
    deposit_total = Decimal() if deposit_total is None else deposit_total
    other_credit_total = Decimal() if other_credit_total is None else other_credit_total

    snapshots = _daily_snapshots(daily_block, year=period_end.year)

    # Every section against its OWN printed total, then the two summary
    # figures against the sum of the section totals. No row is believed on its
    # own and no section total is believed without the rows under it, and a
    # section that disagrees with the figure the bank printed under it declines
    # the DOCUMENT rather than being brought into agreement with it.
    if sum((row.amount for row in deposits), Decimal()) != deposit_total:
        return None
    if sum((row.amount for row in other_credits), Decimal()) != other_credit_total:
        return None
    if sum((row.amount for row in ach_debits), Decimal()) != ach_debit_total:
        return None
    if sum((row.amount for row in ach_credits), Decimal()) != ach_credit_total:
        return None
    if sum((row.amount for row in other_debits), Decimal()) != other_total:
        return None
    if deposit_total + other_credit_total + ach_credit_total != total_credits:
        return None
    if ach_debit_total + other_total + sum((row.amount for row in checks), Decimal()) != total_debits:
        return None

    signed_rows = (
        [(row, 1) for row in deposits + other_credits + ach_credits]
        + [(row, -1) for row in ach_debits + other_debits + checks]
    )
    reconstructed = _ending_by_date(opening, signed_rows)
    if not reconstructed or reconstructed[max(reconstructed)] != ending:
        return None

    ordered = sorted(signed_rows, key=lambda item: (item[0].date, item[0].sequence))
    last_index_by_date: dict[date, int] = {}
    transactions: list[Transaction] = []
    for row, sign in ordered:
        amount = row.amount * sign
        last_index_by_date[row.date] = len(transactions)
        transactions.append(
            Transaction(
                date=row.date.isoformat(),
                description=row.description,
                amount=float(amount),
                direction="credit" if amount > 0 else "debit",
            )
        )
    for txn_date, index in last_index_by_date.items():
        transactions[index] = transactions[index].model_copy(
            update={"running_balance": float(reconstructed[txn_date])}
        )

    # `stated_daily_balances` is BANK evidence: `analysis/adb.py` lets a
    # snapshot OVERRIDE the reconstructed carry for its day, so whatever is put
    # here is read as the figure the bank printed. This reader used to publish
    # `reconstructed.get(day, snapshots[day])` — its own arithmetic wherever it
    # had any, and the printed cell only where it had none — which handed the
    # ADB a parser-computed balance under the name of a bank-printed one. The
    # printed cell is published, always. Where the ledger under the grid
    # reconstructs a different balance for that day the two are left
    # disagreeing and `daily_grid_contradictions` publishes the disagreement;
    # substituting is what turned it invisible. Unreadable cells (the em-dash
    # placeholder class documented at `_GRID_CELL`) stay omitted.
    daily_evidence: list[StatementDailyBalance] = []
    for snapshot_date in sorted(snapshots):
        if not period_start <= snapshot_date <= period_end:
            continue
        daily_evidence.append(
            StatementDailyBalance(
                date=snapshot_date.isoformat(), balance=float(snapshots[snapshot_date])
            )
        )

    name = re.search(r"\n([A-Z][A-Z ]+ (?:PLLC|LLC))\s*\n", markdown)
    return Statement(
        bank="Columbia Bank",
        account_name=(
            f"{name.group(1).title()} - Marketplace Checking" if name else "Marketplace Checking"
        ),
        account_number=account,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        days_in_period=(period_end - period_start).days + 1,
        beginning_balance=float(opening),
        ending_balance=float(ending),
        stated_total_credits=float(total_credits),
        stated_total_debits=float(total_debits),
        bank_reported_average_balance=float(_signed(average_raw)),
        bank_reported_average_label="Average balance",
        stated_interest_paid=float(_money(interest_raw)),
        stated_daily_balances=daily_evidence,
        transactions=transactions,
    )


def _cents(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def daily_grid_contradictions(markdown: str, stmt: Statement) -> list[str]:
    """The Daily Balances grid, read again and held against what was published.

    The grid is a SECOND printing of a balance the ledger above it already
    determines, so a document whose two printings disagree contradicts itself.
    Neither printing is preferred: the disagreement is reported, which is what
    a human needs and what preferring one of them destroyed.

    Two findings, and the difference between them matters.

    **A published snapshot that is not the printed cell** is this module's own
    doctrine violated — parser arithmetic served to `analysis/adb.py` under the
    name of bank evidence, which is what `stated_daily_balances` used to carry.
    It cannot happen through `parse_columbia_bank_statement` any more, and this
    check is what makes that a measured fact on every document rather than a
    property of the code as it stands today.

    **A printed cell the ledger does not reconstruct** is the document
    disagreeing with itself. It is a finding, not a defect of the read: the
    rows are the figures the bank printed, the cell is the figure the bank
    printed, and only the bank can say which one is wrong.

    The grid is re-read from the DOCUMENT rather than taken from the statement,
    so the check keeps working against a reader that has stopped publishing the
    printed cell. Guarded by the registry like every other integrity check.
    """
    if not stmt.period_start or not stmt.period_end:
        return []
    try:
        start = date.fromisoformat(stmt.period_start)
        end = date.fromisoformat(stmt.period_end)
    except ValueError:
        return []
    block = section_between(markdown, r"Daily Balances", r"Overdraft Fee Summary")
    if not block:
        return []
    printed = {
        day: amount
        for day, amount in _daily_snapshots(block, year=end.year).items()
        if start <= day <= end
    }
    if not printed:
        return []

    notes: list[str] = []
    for snapshot in stmt.stated_daily_balances:
        try:
            day = date.fromisoformat(snapshot.date)
        except ValueError:
            continue
        cell = printed.get(day)
        if cell is not None and _cents(snapshot.balance) != cell:
            notes.append(
                f"the daily balance published for {day.isoformat()} "
                f"({snapshot.balance:,.2f}) is not the figure the Daily Balances "
                f"grid prints for that day ({float(cell):,.2f})"
            )

    if stmt.beginning_balance is None:
        return notes
    movement: dict[date, Decimal] = {}
    for txn in stmt.transactions:
        try:
            day = date.fromisoformat(txn.date)
        except ValueError:
            return notes
        movement[day] = movement.get(day, Decimal()) + _cents(txn.amount)

    carry = _cents(stmt.beginning_balance)
    day = start
    while day <= end:
        carry += movement.get(day, Decimal())
        cell = printed.get(day)
        if cell is not None and cell != carry:
            notes.append(
                f"the Daily Balances grid prints {float(cell):,.2f} for "
                f"{day.isoformat()} but the ledger printed above it reconstructs "
                f"{float(carry):,.2f}"
            )
        day += timedelta(days=1)
    return notes

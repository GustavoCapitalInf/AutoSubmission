from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
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
#: its daily grid walks through six negative days. The two FLOW figures
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
#: figure, nor the sign of one. Four consecutive statements of one account
#: print, between the same two summary cells, ` ` / `  ` / ` — ` / ` | `; they
#: are one printed strip and a reader that admits only the first two publishes
#: two of the four.
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


def _counterparty_key(description: str) -> str:
    normalized = re.sub(r"[^A-Z0-9 ]+", " ", description.upper())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = re.sub(r"^ACH (?:CREDIT|DEBIT) ", "", normalized)
    tokens: list[str] = []
    for token in normalized.split():
        if any(char.isdigit() for char in token):
            break
        if token in {"ACHPMT", "HCCLAIMPMT", "HCLAIMPMT", "CLAIMPMT", "EDIRPAY"}:
            break
        tokens.append(token)
        if len(tokens) == 3:
            break
    return " ".join(tokens)


def _repair_repeated_amounts(rows: list[_Row], target: Decimal) -> list[_Row]:
    repaired = list(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(repaired):
        groups[_counterparty_key(row.description)].append(index)

    while True:
        current = sum((row.amount for row in repaired), Decimal())
        current_error = abs(current - target)
        best: tuple[Decimal, int, Decimal] | None = None
        for indexes in groups.values():
            counts = Counter(repaired[index].amount for index in indexes)
            mode, frequency = counts.most_common(1)[0]
            if frequency < 3 or frequency * 2 < len(indexes):
                continue
            for index in indexes:
                if repaired[index].amount == mode:
                    continue
                candidate_error = abs(current - repaired[index].amount + mode - target)
                if candidate_error >= current_error:
                    continue
                candidate = (candidate_error, index, mode)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            return repaired
        _, index, mode = best
        repaired[index] = replace(repaired[index], amount=mode)


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


def _repair_single_section_delta(
    debit_rows: list[_Row],
    *,
    target: Decimal,
    opening: Decimal,
    all_credit_rows: list[_Row],
    other_debits: list[_Row],
    checks: list[_Row],
    snapshots: dict[date, Decimal],
) -> list[_Row] | None:
    current = sum((row.amount for row in debit_rows), Decimal())
    delta = current - target
    if delta == 0:
        return debit_rows

    groups: dict[str, list[_Row]] = defaultdict(list)
    for row in debit_rows:
        groups[_counterparty_key(row.description)].append(row)

    candidates: list[tuple[int, int, list[_Row]]] = []
    for index, row in enumerate(debit_rows):
        related = groups[_counterparty_key(row.description)]
        mode, frequency = Counter(item.amount for item in related).most_common(1)[0]
        if frequency >= 3 and frequency * 2 >= len(related) and row.amount == mode:
            continue
        candidate_amount = row.amount - delta
        if candidate_amount <= 0 or candidate_amount.as_tuple().exponent != -2:
            continue
        candidate_rows = list(debit_rows)
        candidate_rows[index] = replace(row, amount=candidate_amount)
        signed_rows = (
            [(item, 1) for item in all_credit_rows]
            + [(item, -1) for item in candidate_rows]
            + [(item, -1) for item in other_debits]
            + [(item, -1) for item in checks]
        )
        reconstructed = _ending_by_date(opening, signed_rows)
        score = sum(reconstructed.get(day) == amount for day, amount in snapshots.items())
        candidates.append((score, -index, candidate_rows))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    if candidates[0][0] < max(3, len(snapshots) * 3 // 4):
        return None
    return candidates[0][2]


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
#: What replaces it is the section masthead the reader REQUIRES: the debit
#: ledger it must find and reconcile against that section's own printed total.
#: This keeps the marker count at four and the claim score at 0.5 — the two
#: statements already claimed keep the score they had — and it moves the
#: evidence from something a scan can lose to something the parser cannot
#: proceed without. `MARKETPLACE CHECKING` remains: it is the issuer's own
#: product masthead, and it is why this registration still publishes a bank
#: NAME the two unlabelled scans do not print (the printing is Columbia Bank's,
#: and the registration is Columbia Bank's).
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

    ach_debits = _repair_repeated_amounts(ach_debits, ach_debit_total)
    ach_credits = _repair_repeated_amounts(ach_credits, ach_credit_total)
    snapshots = _daily_snapshots(daily_block, year=period_end.year)
    ach_debits = _repair_single_section_delta(
        ach_debits,
        target=ach_debit_total,
        opening=opening,
        all_credit_rows=deposits + other_credits + ach_credits,
        other_debits=other_debits,
        checks=checks,
        snapshots=snapshots,
    )
    if ach_debits is None:
        return None

    # Every section against its OWN printed total, then the two summary
    # figures against the sum of the section totals. No row is believed on its
    # own and no section total is believed without the rows under it.
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

    daily_evidence: list[StatementDailyBalance] = []
    for snapshot_date in sorted(snapshots):
        if not period_start <= snapshot_date <= period_end:
            continue
        amount = reconstructed.get(snapshot_date, snapshots[snapshot_date])
        daily_evidence.append(
            StatementDailyBalance(date=snapshot_date.isoformat(), balance=float(amount))
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

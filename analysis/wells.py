"""Wells Fargo — the printed page, read as the grid the bank prints.

Three structural facts about a Wells Fargo statement drive this module, and
every rule below is anchored on one of them rather than on wording, position or
any statement's data:

1. **A statement is a sequence of account sections.** Each section opens with
   the account's own ``Account number:`` line, and exactly one of them carries
   the bank's ``(primary account)`` marker. Everything printed after that line
   — the account's activity summary, its transaction history, its fee summary —
   belongs to that account until the next such line. The platform's
   ``Statement`` is single-account (MASTER_PLAN L-1), so what is published is
   the primary account's ledger measured against the primary account's summary.
   Reading the union of every account's rows against one account's summary is
   arithmetic on two different ledgers.

2. **The activity summary is a two-column label/value block, not a sentence.**
   Wells prints four labelled rows — ``Beginning balance on M/D``,
   ``Deposits/<direction>``, ``Withdrawals/<direction>`` and
   ``Ending balance on M/D`` (``Closing balance on M/D`` when the account was
   closed in the period). The native text layer emits one PyMuPDF *block* per
   line in (y, x) order, and the page furniture printed in the same band — the
   account-terms line, the routing-number lines, the account holder's name —
   lands *between* those rows. So each label owns its own printed row and
   claims the amount cell printed on it; nothing may be assumed about what is
   adjacent to what.

   The period itself is printed **inside the labels**, not in the cells, so a
   statement whose amount column is unreadable still dates itself.

3. **A transaction row is a delimited record whose description can contain the
   delimiter.** ``ocr/native_text.py`` emits
   ``WF_TX|<date>|<description>|<credit>|<debit>|<balance>``; ACH descriptions
   quote EDI text that contains ``|``. Only the description can, and exactly
   three cells follow it, so the record is split from the right.

Fail closed, never guess: a row whose amount landed in neither money column, or
in both, is dropped rather than assigned a direction the grid did not print;
a label whose cell is unreadable yields no value; and a statement that prints
no year evidence is not parsed at all (R-1 item 9).
"""
from __future__ import annotations

import re
from datetime import date

from .date_tokens import iso_from_month_day
from .holder_name import CITY_STATE_ZIP, first_page, holder_from_address_line, page_lines
from .money import parse_money, read_money
from .parser_registry import make_detector, required
from .schema import Statement, Transaction

#: Audit round 2, R2-B05 (R04 part 2): the heading of the customer-service panel Wells Fargo prints beside the mailing
#: address on page 1, and the panel line that opens the bank's own address ('Write: Wells Fargo Bank, N.A. (000)').
_QUESTIONS_HEADING = re.compile(r"^Questions\?$", re.IGNORECASE)
_BANK_ADDRESS_LINE = re.compile(r"^Write:", re.IGNORECASE)
#: The panel lines read before the mailing line at most (the phone hours, a relay line).
_MAILING_LINE_WINDOW = 4


def _holder_name(markdown: str) -> str | None:
    """Audit round 2, R2-B05 (R04 part 2): the holder's name from the mailing line Wells Fargo prints after page 1's
    'Questions?' heading: the first line within _MAILING_LINE_WINDOW lines that closes on a state and ZIP, before the
    bank's own 'Write:' address, without the address (analysis.holder_name.holder_from_address_line). None without the
    heading or such a line."""
    lines = page_lines(first_page(markdown))
    start = next((index for index, line in enumerate(lines) if _QUESTIONS_HEADING.match(line)), None)
    if start is None:
        return None
    for line in lines[start + 1:start + 1 + _MAILING_LINE_WINDOW]:
        if _BANK_ADDRESS_LINE.match(line):
            return None
        if CITY_STATE_ZIP.search(line):
            return holder_from_address_line(line)
    return None

#: Opens an account's section. The trailing marker is the bank's own
#: designation of which account the statement is for.
_ACCOUNT_LINE_RE = re.compile(
    r"^Account number:\s*(?P<number>\d+)(?P<primary>\s*\(primary account\))?",
    re.IGNORECASE,
)

#: The account number wherever it is printed inside the chosen section. The
#: section boundary is a line-owning heading (above); the identity it carries
#: is read tolerantly so a layout that indents the line still names its
#: account.
_ACCOUNT_NUMBER_RE = re.compile(r"Account number:\s*(?P<number>\d+)", re.IGNORECASE)

#: The activity summary's heading. It owns its line.
_SUMMARY_HEADING_RE = re.compile(r"^Statement period activity summary\b", re.IGNORECASE)

#: The printed headings that follow the summary block. A heading owns its line,
#: so a line that merely mentions one of these words does not close the block.
_SUMMARY_END_RE = re.compile(
    r"^(?:Overdraft Protection|Interest summary|Transaction history|Summary of accounts)\b",
    re.IGNORECASE,
)

#: One cell of the summary's amount column. A balance keeps whatever sign the
#: bank printed; an activity row's direction is its LABEL's, so its cell is
#: taken as a magnitude — the minus in front of a withdrawal is not always in
#: the text layer even when the row is.
_SUMMARY_CELL_RE = re.compile(r"-?\$?\s?\d[\d,]*\.\d{2}")

#: The four printed row labels. The two balance labels carry the period date
#: the row is for; the two activity labels carry the direction in their first
#: word, which is why the second word is read as data (``Credits`` on a
#: business statement, ``Additions`` on a consumer one) rather than enumerated.
_SUMMARY_LABEL_RE = re.compile(
    r"(?P<opening>Beginning balance on (?P<bm>\d{1,2})/(?P<bd>\d{1,2}))"
    r"|(?P<closing>(?:Ending|Closing) balance on (?P<em>\d{1,2})/(?P<ed>\d{1,2}))"
    r"|(?P<credits>Deposits/\S+)"
    r"|(?P<debits>Withdrawals/\S+)",
    re.IGNORECASE,
)

_AVG_RE = re.compile(r"Average ledger balance\s+\$?[\d,]+\.\d{2}\s+(-?\$?[\d,]+\.\d{2})", re.IGNORECASE)

_TX_PREFIX = "WF_TX|"
#: The record's fixed tail: credit, debit, balance. Only the description can
#: carry the delimiter, so the tail is taken from the right.
_TX_TRAILING_CELLS = 3

#: The transaction history closes with the bank's own restatement of it —
#: `Totals $<credits> $<debits>` — and that row is set in the same two money
#: columns the postings are. Where its band meets the last posting's, the grid
#: emits ONE record carrying both, and the restatement's figures then read as
#: that posting's amount: the statement's whole debit total published as a
#: single debit that never happened.
#:
#: The currency symbol is what separates the two, and it is the layout's own
#: distinction rather than a threshold: Wells sets `$` on the summary block, on
#: the `Totals` row and on nothing else. Measured over every document this
#: reader claimed in the run of record — 221 documents, 30,347 records, 30,339
#: printed money cells and 4,218 balance cells — exactly 2 money cells carry
#: the symbol, both are a `Totals` row's figure merged into the last posting,
#: and no balance cell carries it at all.
#:
#: A row whose amount cell is a restatement is DROPPED, in the same fail-closed
#: direction as a row whose amount landed in neither column: the reader loses
#: an amount rather than publishing one the grid did not print as a posting,
#: and reconciliation decides what that costs the document.
_RESTATEMENT_CELL = re.compile(r"[$]")


def _infer_year(markdown: str) -> int | None:
    """First 4-digit year printed in the document, or None.

    No fabricated default: a statement whose text carries no year evidence
    cannot be dated, and the parser fails closed instead of guessing (R-1
    item 9 - the previous hardcoded ``2026`` fallback invented dates).
    """
    years = [int(y) for y in re.findall(r"\b(20\d{2})\b", markdown)]
    return years[0] if years else None


def _published_section(lines: list[str]) -> list[str]:
    """The lines of the account the statement is for.

    A section runs from its ``Account number:`` line to the next one, and the
    published section is the one the bank marks ``(primary account)`` — else
    the first section printed. A document that prints no such line at line
    start is treated as one section, so the reader degrades to whole-document
    behaviour rather than losing the statement.
    """
    starts = [
        (index, match)
        for index, line in enumerate(lines)
        for match in [_ACCOUNT_LINE_RE.match(line)]
        if match
    ]
    if not starts:
        return lines
    chosen = next((k for k, (_, match) in enumerate(starts) if match.group("primary")), 0)
    end = starts[chosen + 1][0] if chosen + 1 < len(starts) else len(lines)
    return lines[starts[chosen][0]:end]


class _ActivitySummary:
    """What the activity summary block prints, row by row.

    Each field is absent (``None``) unless the bank printed it: the two period
    dates come from the labels, the four amounts from the cell printed on the
    label's own row.
    """

    __slots__ = ("period_start", "period_end", "beginning_balance", "ending_balance",
                 "stated_total_credits", "stated_total_debits")

    #: The amount fields, in the order the block prints them.
    AMOUNTS = ("beginning_balance", "stated_total_credits", "stated_total_debits", "ending_balance")

    def __init__(self) -> None:
        for name in self.__slots__:
            setattr(self, name, None)

    def _set(self, name: str, value) -> None:
        if getattr(self, name) is None:
            setattr(self, name, value)


def _read_activity_summary(lines: list[str]) -> _ActivitySummary:
    """Read the activity summary as the printed label/value rows it is."""
    summary = _ActivitySummary()
    heading = next((i for i, line in enumerate(lines) if _SUMMARY_HEADING_RE.match(line)), None)
    if heading is None:
        return summary

    for line in lines[heading + 1:]:
        if _SUMMARY_END_RE.match(line) or _SUMMARY_HEADING_RE.match(line):
            break
        labels = list(_SUMMARY_LABEL_RE.finditer(line))
        for index, label in enumerate(labels):
            limit = labels[index + 1].start() if index + 1 < len(labels) else len(line)
            cell = _SUMMARY_CELL_RE.search(line, label.end(), limit)
            value = parse_money(cell.group(0)) if cell else None
            if label.group("opening"):
                summary._set("period_start", (int(label.group("bm")), int(label.group("bd"))))
                if value is not None:
                    summary._set("beginning_balance", value)
            elif label.group("closing"):
                summary._set("period_end", (int(label.group("em")), int(label.group("ed"))))
                if value is not None:
                    summary._set("ending_balance", value)
            elif value is None:
                continue
            elif label.group("credits"):
                summary._set("stated_total_credits", abs(value))
            elif label.group("debits"):
                summary._set("stated_total_debits", abs(value))
    return summary


def _transaction_rows(lines: list[str]) -> list[tuple[str, str, str, str, str]]:
    """The ``WF_TX`` records printed in these lines, split from the right.

    ``WF_TX|<date>|<description>|<credit>|<debit>|<balance>``. The description
    is the only field that can contain the delimiter (ACH rows quote EDI
    reference text), and exactly three grid cells follow it, so taking the tail
    from the right reconstructs every field including a description that
    carries pipes. Splitting left to right shifts every field after such a
    description by one and reads reference text as an amount.
    """
    rows = []
    for line in lines:
        if not line.startswith(_TX_PREFIX):
            continue
        head, credit, debit, balance = (
            line.rsplit("|", _TX_TRAILING_CELLS) + ["", "", ""]
        )[:4]
        _, mmdd, description = (head.split("|", 2) + ["", ""])[:3]
        rows.append((mmdd, description.strip(), credit, debit, balance))
    return rows


DETECTION_MARKERS = (
    required("native_block", lambda t: "WF_NATIVE_TRANSACTIONS" in t),
    required("bank_name", lambda t: "WELLS FARGO" in t.upper()),
)

detect = make_detector(DETECTION_MARKERS)


def parse_wells_statement(markdown: str, base: Statement | None = None) -> Statement | None:
    if not detect(markdown).claims:
        return None
    year = _infer_year(markdown)
    if year is None:
        return None
    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "Wells Fargo"
    stmt.holder_name = _holder_name(markdown) or stmt.holder_name

    section = _published_section(markdown.splitlines())
    account = next(
        (match for line in section for match in [_ACCOUNT_NUMBER_RE.search(line)] if match), None
    )
    if account:
        stmt.account_number = account.group("number")

    summary = _read_activity_summary(section)
    if summary.period_start:
        stmt.period_start = date(year, *summary.period_start).isoformat()
    if summary.period_end:
        stmt.period_end = date(year, *summary.period_end).isoformat()
    if stmt.period_start and stmt.period_end and stmt.period_end < stmt.period_start:
        # A period that crosses New Year: the year evidence names the closing
        # year, so the opening date belongs to the year before it.
        stmt.period_start = date(year - 1, *summary.period_start).isoformat()
    for field in summary.AMOUNTS:
        value = getattr(summary, field)
        if value is not None:
            setattr(stmt, field, value)

    avg = _AVG_RE.search("\n".join(section))
    if avg:
        stmt.bank_reported_average_balance = parse_money(avg.group(1))
        stmt.bank_reported_average_label = "Average ledger balance"

    txns: list[Transaction] = []
    for mmdd, description, credit, debit, balance in _transaction_rows(section):
        if not description or description.upper().startswith(("TOTALS", "ENDING BALANCE")):
            continue
        if _RESTATEMENT_CELL.search(credit) or _RESTATEMENT_CELL.search(debit):
            # The bank's own restatement of the history, emitted into a
            # posting's record because the two printed rows share a band
            # (`_RESTATEMENT_CELL`). It is not this row's amount and it is not
            # any row's amount.
            continue
        if bool(credit) == bool(debit):
            # Neither money column carries the amount, or both do: the printed
            # grid did not say which side this row is on. Direction is not
            # inferred from the description — the row is dropped and
            # reconciliation decides whether what remains is publishable.
            continue
        amount = abs(read_money(credit if credit else debit) or 0.0)
        signed = amount if credit else -amount
        txns.append(Transaction(
            date=iso_from_month_day(mmdd, year=year),
            description=description,
            amount=round(signed, 2),
            direction="credit" if signed > 0 else "debit",
            running_balance=parse_money(balance) if balance else None,
        ))

    if not txns:
        return None
    stmt.transactions = txns
    return stmt

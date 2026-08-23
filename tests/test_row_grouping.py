"""W3 §GROUPER — the row grouper's promotion into `analysis/tables.py`.

`tables.group_rows` is the row-grouping rule that `chase.py`, `td_can.py` and
`rbc.py` each arrived at independently in W3 Track A: a row starts where the
printed grid starts one, every other physical line continues the row it is
inside, and a terminator line closes the open row without starting another.

Moving a rule that three parsers depend on is only safe if it is proved to be
the SAME rule. This module carries that proof in the R-2 idiom
(`tests/test_shared_parser_utils.py`, `tests/test_money.py`): each parser's
pre-promotion implementation is reproduced here **verbatim** as a frozen
oracle, spliced back into the live parser, and the two readings of the same
document are asserted byte-identical over an adversarial matrix built from the
layout families Track A characterised — Chase's twelve, TD Canada's six and
RBC's eleven, in both languages — plus each suite's negative fixtures.

Nothing here is a new capability test: the family suites
(`test_chase_native_variants.py`, `test_td_can_native_variants.py`,
`test_rbc_variants.py`) own that, and they run unchanged. This module answers
one question only: does the promoted primitive read every one of those
documents exactly as the parser-local code did?
"""
from __future__ import annotations

import json
import re

import pytest

from analysis import chase, rbc, td_can
from analysis.schema import Statement
from analysis import tables
from analysis.tables import compact_whitespace, group_rows
from analysis.money import parse_money

from tests.test_chase_native_variants import (
    F1 as CHASE_F1,
    F2B as CHASE_F2B,
    F3 as CHASE_F3,
    F4 as CHASE_F4,
    F5 as CHASE_F5,
    F6 as CHASE_F6,
    F7 as CHASE_F7,
    F8 as CHASE_F8,
    F9 as CHASE_F9,
    F10 as CHASE_F10,
    F11 as CHASE_F11,
    _doc as chase_doc,
    _f2 as chase_f2,
    _summary as chase_summary,
)
from tests.test_rbc_variants import FR as RBC_FRENCH, statement as rbc_statement
from tests.test_td_can_native_variants import _statement as td_statement


# ===========================================================================
# The primitive on its own terms
# ===========================================================================

def _digit(line: str) -> bool:
    return bool(re.match(r"\d", line))


def _total(line: str) -> bool:
    return line.lower().startswith("total")


def test_a_row_starts_at_a_start_line_and_takes_the_lines_that_follow():
    assert group_rows(
        ["1 first", "wrapped", "2 second"], starts_row=_digit
    ) == [["1 first", "wrapped"], ["2 second"]]


def test_lines_before_the_first_row_belong_to_no_row():
    """Section furniture printed above the first row is not a row, and a
    parser must not publish a row the grid never opened."""
    assert group_rows(["DATE DESCRIPTION AMOUNT", "1 first"], starts_row=_digit) == [
        ["1 first"]
    ]


def test_a_terminator_closes_the_open_row_and_starts_nothing():
    assert group_rows(
        ["1 first", "wrapped", "Total 9.99", "trailing"],
        starts_row=_digit,
        ends_row=_total,
    ) == [["1 first", "wrapped"]]


def test_a_row_after_a_terminator_is_still_read():
    assert group_rows(
        ["1 first", "Total 9.99", "2 second"], starts_row=_digit, ends_row=_total
    ) == [["1 first"], ["2 second"]]


def test_a_terminator_without_an_open_row_emits_nothing():
    assert group_rows(["Total 9.99"], starts_row=_digit, ends_row=_total) == []


def test_the_last_row_is_closed_by_the_end_of_the_stream():
    assert group_rows(["1 only", "wrapped"], starts_row=_digit) == [["1 only", "wrapped"]]


def test_an_empty_stream_has_no_rows():
    assert group_rows([], starts_row=_digit) == []


def test_a_stream_with_no_start_line_has_no_rows():
    assert group_rows(["wrapped", "wrapped"], starts_row=_digit) == []


def test_without_a_terminator_predicate_nothing_closes_a_row_early():
    assert group_rows(["1 first", "Total 9.99"], starts_row=_digit) == [
        ["1 first", "Total 9.99"]
    ]


def test_the_grouper_is_not_restricted_to_strings():
    """RBC groups `(text, date, opens_a_date_group)` entries, not lines."""
    entries = [("a", "2026-01-01", True), ("b", "2026-01-01", False),
               ("c", "2026-01-02", True)]
    assert group_rows(entries, starts_row=lambda e: e[2]) == [
        [entries[0], entries[1]], [entries[2]]
    ]


def test_the_grouper_consumes_a_generator_once():
    assert group_rows((line for line in ["1 a", "b"]), starts_row=_digit) == [["1 a", "b"]]


# ===========================================================================
# Chase — frozen oracles for the two grouping call sites
# ===========================================================================

def _legacy_chase_native_rows(lines) -> list[list[str]]:
    """`analysis/chase.py::_native_rows`, verbatim as of `8ce6abc`."""
    rows: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if chase._ROW_START_RE.match(line):
            if current:
                rows.append(current)
            current = [line]
        elif chase._ROW_STOP_RE.match(line):
            if current:
                rows.append(current)
            current = None
        elif current is not None:
            current.append(line)
    if current:
        rows.append(current)
    return rows


def _legacy_chase_check_rows(block: str) -> list[list[str]]:
    """`analysis/chase.py::_check_rows`, verbatim as of `8ce6abc`.

    Note the predicate order: the legacy loop tested the terminator BEFORE the
    row start, and the promoted primitive tests the row start first. The two
    orders can only differ on a line both predicates match, which
    `test_the_chase_row_predicates_cannot_both_match_one_line` proves is not a
    line either predicate accepts.
    """
    rows: list[list[str]] = []
    current: list[str] | None = None
    for raw in block.splitlines():
        line = compact_whitespace(raw)
        if not line:
            continue
        line = re.sub(r"(?i)^CHECKS PAID\s*(?:\(continued\))?\s*", "", line, count=1)
        line = chase._COLUMN_HEADER_RE.sub("", line, count=1)
        if not line:
            continue
        for piece in chase._CHECK_INLINE_SPLIT_RE.split(line):
            piece = piece.strip()
            if not piece:
                continue
            if chase._ROW_STOP_RE.match(piece):
                if current:
                    rows.append(current)
                current = None
            elif chase._CHECK_START_RE.match(piece):
                if current:
                    rows.append(current)
                current = [piece]
            elif current is not None:
                current.append(piece)
    if current:
        rows.append(current)
    return rows


#: Every printed line shape the Chase families put through the grouper: a
#: start line, a wrapped description, a wrapped amount cell, a second printed
#: date inside a row, a terminator, and the furniture that must open nothing.
CHASE_LINES = (
    "01/05 Wire Credit Via: Meridian Trust B/O: Quarry Lane Foods",
    "1,300.00",
    "Ref: Nbnf=Blue Harbor Sec:CCD Trace#:100000000000001 Eed:260105 Ind",
    "01/06 12/29 Card Purchase 12/28 Riverbend Supply 392.94",
    "12/29 Online Transfer To Chk ...0001 Transaction#: 00000001 500.00",
    "01/07 Purchase $352.94 Cash Back $40.00 Riverbend Supply",
    "392.94",
    "01/08 Foreign Exch Rt Adj 4967200 X 0.000668276 (Exchg Rte) 33.19",
    "Total Deposits and Additions $4,300.00",
    "Total ATM & Debit Card Withdrawals $1,000.00",
    "ATM & DEBIT CARD SUMMARY",
    "DAILY ENDING BALANCE",
    "Fees Sec:PPD Trace#:100000000000009 Eed:260109",
    "(continued)",
    "DATE DESCRIPTION AMOUNT",
    "0000000123456789012345",
    "1234 01/09 250.00",
    "1234 * ^ 01/09 01/08 250.00",
    "Total 9.99",
    "total checks paid",
    "TOTAL",
    "",
    " ",
    "01/10",
    "01/10 ",
    "99/99 not a calendar date but the printed shape",
)


def _chase_line_streams() -> list[list[str]]:
    """Adversarial line streams: every single line alone, every ordered pair,
    the whole matrix in order and reversed, and the real streams the family
    fixtures produce through `_physical_lines`."""
    streams: list[list[str]] = [[line] for line in CHASE_LINES]
    streams += [[a, b] for a in CHASE_LINES for b in CHASE_LINES]
    streams.append(list(CHASE_LINES))
    streams.append(list(reversed(CHASE_LINES)))
    streams.append([])
    for markdown in CHASE_DOCUMENTS:
        for heading in CHASE_HEADINGS:
            stream: list[str] = []
            for block in chase._native_blocks(markdown, heading):
                stream.extend(chase._physical_lines(block, heading))
            if stream:
                streams.append(stream)
    return streams


CHASE_HEADINGS = (
    "DEPOSITS AND ADDITIONS",
    "ATM & DEBIT CARD WITHDRAWALS",
    "ELECTRONIC WITHDRAWALS",
    "OTHER WITHDRAWALS",
    "OTHER WITHDRAWALS, FEES & CHARGES",
    "FEES",
    "CHECKS PAID",
)

#: The negative fixtures the Chase suite asserts inline, rebuilt here so the
#: differential matrix carries them too.
CHASE_NEGATIVE_INLINE_DATE = chase_doc(
    chase_summary(**{"Deposits and Additions": "1 500.00", "Ending Balance": "1 $1,500.00"}),
    """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
01/05 Card Purchase 01/04 Riverbend Supply Card 0001 500.00
Total Deposits and Additions $500.00
*end*deposits and additions
""",
)

CHASE_NEGATIVE_BARCODE = chase_doc(
    chase_summary(**{"Checks Paid": "1 -250.00", "Ending Balance": "1 $750.00"}),
    """*start*checks paid
CHECKS PAID
CHECK NO. DESCRIPTION DATE PAID AMOUNT
00000012345678901234567890
1234 01/09 250.00
Total Checks Paid $250.00
*end*checks paid
""",
)

CHASE_NEGATIVE_DATELESS = chase_doc(
    chase_summary(**{"Deposits and Additions": "1 500.00", "Ending Balance": "1 $1,500.00"}),
    """*start*deposits and additions
DEPOSITS AND ADDITIONS
DATE DESCRIPTION AMOUNT
Orphaned continuation with no printed date 500.00
01/05 Real Row 500.00
Total Deposits and Additions $500.00
*end*deposits and additions
""",
)

CHASE_DOCUMENTS = (
    CHASE_F1, CHASE_F2B, CHASE_F3, CHASE_F4, CHASE_F5, CHASE_F6,
    CHASE_F7, CHASE_F8, CHASE_F9, CHASE_F10, CHASE_F11,
    chase_f2("Zelle Payment To Riverbend Supply"),
    chase_f2("Reversal Of Wire Fee"),
    chase_f2("Chips Credit Via: Meridian Trust"),
    chase_f2("Recurring Card Purchase 01/05"),
    chase_f2("Something No Whitelist Ever Listed"),
    CHASE_NEGATIVE_INLINE_DATE,
    CHASE_NEGATIVE_BARCODE,
    CHASE_NEGATIVE_DATELESS,
)

CHASE_CHECK_BLOCKS = tuple(
    block
    for markdown in CHASE_DOCUMENTS
    for block in chase._native_blocks(markdown, "CHECKS PAID")
) + (
    "CHECKS PAID\nCHECK NO. DESCRIPTION DATE PAID AMOUNT\n1234 01/09 250.00\n",
    "CHECKS PAID (continued)\n1234 * 01/09 01/08 250.00 5678 ^ 01/10 125.00\n",
    "CHECKS PAID\n0000000123456789012345\n1234 01/09 250.00\nTotal Checks Paid $250.00\n",
    "CHECKS PAID\n12345678\nAch Debit Origination Riverbend Supply\n01/09 250.00\n",
    "",
    "CHECKS PAID\nTotal Checks Paid $0.00\n",
)


def test_the_chase_row_predicates_cannot_both_match_one_line():
    """What licenses the reordering inside `_check_rows`: a terminator line
    starts with a word, and both row-start rules require a leading digit, so
    no line can be both. Proved over the whole adversarial matrix rather than
    asserted."""
    both = [
        line
        for line in CHASE_LINES
        if chase._ROW_STOP_RE.match(line)
        and (chase._ROW_START_RE.match(line) or chase._CHECK_START_RE.match(line))
    ]
    assert both == []
    #: and structurally, not only over the matrix: both row-start rules are
    #: anchored on a digit and every terminator alternative on a letter.
    assert chase._ROW_START_RE.pattern.startswith(r"^(\d")
    assert chase._CHECK_START_RE.pattern.startswith(r"^\d")
    assert chase._ROW_STOP_RE.pattern.startswith("(?i)^(?:")
    assert not re.search(r"\^\(\?:\W*\d", chase._ROW_STOP_RE.pattern)


def test_chase_native_rows_reads_every_stream_as_the_frozen_oracle_did():
    streams = _chase_line_streams()
    mismatches = [
        stream
        for stream in streams
        if chase._native_rows(list(stream)) != _legacy_chase_native_rows(list(stream))
    ]
    assert len(streams) > 700
    assert not mismatches, f"row grouping drift on {len(mismatches)} streams: {mismatches[:3]}"


@pytest.mark.parametrize("block", CHASE_CHECK_BLOCKS)
def test_chase_check_rows_reads_every_block_as_the_frozen_oracle_did(block):
    assert chase._check_rows(block) == _legacy_chase_check_rows(block)


#: Fields the frozen oracles below CANNOT carry, because they did not exist
#: when the oracles were frozen. Excluded rather than back-filled: an oracle
#: whose body is edited is no longer "verbatim as of <sha>", and the whole
#: value of these tests is that their right-hand side has not been touched.
#: Each is proved independently, by name, elsewhere:
#:   `bank_reported_average_label`      tests/test_td_french_layouts.py,
#:                                      tests/test_analysis.py (per parser)
#:   `initialization_transaction_count` tests/test_woodforest.py
#:   `currency_source`                   tests/test_currency_source.py (one
#:                                       publication and one refusal test per
#:                                       evidence class, plus the AST surfaces
#:                                       and the pinned gate map)
#:
#: `currency_source` is the §CURRSRC provenance field. It is the same situation
#: `currency` itself is already in on the TD oracle — the frozen body writes
#: `stmt.currency = "CAD"` while the live reader has since learned to read the
#: `ACCOUNT - CAD` suffix, and the two agree on this matrix only because every
#: fixture prints CAD. The provenance of that read is a field the oracle has no
#: way to carry, and back-filling it would edit a body whose whole value is
#: that it has not been edited.
_FIELDS_NEWER_THAN_THE_ORACLES = (
    "bank_reported_average_label",
    "currency_source",
    "initialization_transaction_count",
)


def _statement_json(stmt: Statement | None) -> str | None:
    """The statement as JSON, minus fields postdating the frozen oracles."""
    if stmt is None:
        return None
    return json.dumps(
        {
            key: value
            for key, value in stmt.model_dump().items()
            if key not in _FIELDS_NEWER_THAN_THE_ORACLES
        },
        sort_keys=True,
        default=str,
    )


@pytest.mark.parametrize("markdown", CHASE_DOCUMENTS)
def test_chase_parses_every_family_document_identically_to_the_oracle(markdown, monkeypatch):
    """The proof at the level that matters: the whole parser, reading the same
    document with the frozen grouping code spliced back in."""
    live = _statement_json(chase.parse_chase_statement(markdown))
    monkeypatch.setattr(chase, "_native_rows", _legacy_chase_native_rows)
    monkeypatch.setattr(chase, "_check_rows", _legacy_chase_check_rows)
    assert live == _statement_json(chase.parse_chase_statement(markdown))


# ===========================================================================
# RBC — frozen oracle for the grid reader's row segmentation
# ===========================================================================

def _legacy_rbc_read_grid_rows(entries, *, pattern, to_amount, opening_label, closing_label):
    """`analysis/rbc.py::_read_grid_rows`, verbatim as of `8ce6abc`.

    Now promoted to `analysis/tables.py::read_grid_rows` (W3 §RBCCIBC) and
    hardened there, so this oracle proves two things at once: that the move
    was behaviour-preserving, and that the card-D fixes reach only the shapes
    they name. Every input below still reads identically — the fixed shapes
    (a bare minus signing a balance, an opening row sharing its line) are
    pinned separately in tests/test_rbc_variants.py, because they are the
    places this oracle is deliberately no longer authoritative."""
    rows: list[dict] = []
    opening: float | None = None
    description: list[str] = []
    open_row: dict | None = None
    centred_amount = False
    opens = re.compile(re.escape(opening_label), re.IGNORECASE)
    closes = re.compile(re.escape(closing_label), re.IGNORECASE)

    for text, tx_date, opens_group in entries:
        if opens_group:
            description = []
            open_row = None
            centred_amount = False
        if not text:
            continue
        stop = closes.search(text)
        if stop:
            text = text[:stop.start()].strip()
            if not text:
                break
        cells = tables._grid_cells(text, pattern)
        if opens.match(text):
            if cells:
                opening = to_amount(cells[-1].group(0))
            description, open_row, centred_amount = [], None, False
            continue
        if not cells:
            if open_row is not None and centred_amount:
                open_row["description"] = f"{open_row['description']} {text}".strip()
            else:
                description.append(text)
            centred_amount = False
            continue

        cells_only = (
            not text[:cells[0].start()].strip()
            and not text[cells[-1].end():].strip()
            and all(not text[a.end():b.start()].strip() for a, b in zip(cells, cells[1:]))
        )
        position = 0
        for match in cells:
            gap = text[position:match.start()].strip()
            if gap:
                description.append(gap)
                open_row = None
            value = to_amount(match.group(0))
            if open_row is not None and open_row["balance"] is None:
                open_row["balance"] = value
                open_row = None
            else:
                row = {
                    "date": tx_date,
                    "description": " ".join(description).strip(),
                    "abs_amount": abs(value),
                    "amount": -abs(value),
                    "balance": None,
                }
                description = []
                rows.append(row)
                open_row = row
            position = match.end()
        tail = text[position:].strip()
        if tail:
            description.append(tail)
            open_row = None
        centred_amount = cells_only

    return rows, opening


def _rbc(body: str, **printed) -> str:
    printed.setdefault("opening", "1,000.00")
    printed.setdefault("closing", "1,000.00")
    printed.setdefault("credits", "0.00")
    printed.setdefault("credit_count", 0)
    printed.setdefault("debits", "0.00")
    printed.setdefault("debit_count", 0)
    return rbc_statement(body, **printed)


#: The English grid's families: the dual money cell (F1), a compressed line
#: (F3), a wrapped row (F4), a vertically centred amount cell (F5), printed
#: rate operands (F6), a printed reference number (F7), a closing-balance cell
#: inside a row line (F8), a repeated posting date (F9), and the negatives.
RBC_DOCUMENTS = (
    _rbc("02 Mar Deposit item 1,000.00\nWithdrawal item 300.00 1,700.00\n",
         closing="1,700.00", credits="1,000.00", credit_count=1,
         debits="300.00", debit_count=1),
    _rbc("02 Mar Lone cell row 250.00\n"),
    _rbc("02 Mar Row one 4.40 900.00\n03 Mar Row two 100.00 800.00\n"),
    _rbc("02 Mar First row 10,000.00 11,000.00 Misc Payment 783.48 10,216.52\n"),
    _rbc("02 Mar Description opens the row\nand wraps onto this line 500.00 1,500.00\n"),
    _rbc("02 Mar Description above\n500.00\ndescription below\n03 Mar Next 10.00\n"),
    _rbc("02 Mar Regular transaction fee 17 Drs @ 2.50 42.50\n"),
    _rbc("02 Mar Overdraft interest @ RBP+05.00%P.A 0.04 4,820.18\n"),
    _rbc("02 Mar Handling fee 2 @ $ 5.00 10.00\n"),
    _rbc("02 Mar Water Bill Payment 00314.06 1,432.28 -28,340.36\n"),
    _rbc("02 Mar Small cell 0.45 999.55\n"),
    _rbc("02 Mar Online Transfer 4,000.00 4.40 Closing balance 4.40\n"),
    _rbc("02 Mar Row one 100.00\n1 of 16\n02 Mar Row two 50.00 850.00\n"),
    _rbc("02 Mar Row one 100.00\n02 Mar 02 Mar Row two 50.00 850.00\n"),
    _rbc("02 Mar Reference 000123456789 in the description 100.00 900.00\n"),
    _rbc("02 Mar Three adjacent cells 100.00 900.00 800.00\n"),
    _rbc("A line printed before any posting date 100.00\n02 Mar Row 50.00\n"),
    _rbc(""),
    # The three shapes that turn on the row boundary itself: a new posting
    # date must discard a description that never got an amount cell, must not
    # let the previous row take the next day's first cell as its balance, and
    # must not let a centred amount cell adopt the next day's first line.
    _rbc("02 Mar Description that never gets an amount cell\n"
         "03 Mar Row 100.00 900.00\n"),
    _rbc("02 Mar Row 100.00\n03 Mar 900.00 Next row 50.00\n"),
    _rbc("02 Mar Description above\n500.00\n03 Mar Next day row 10.00 490.00\n"),
    _rbc("02 Mar Row one 100.00\n02 Mar Row two 50.00\n03 Mar Row three 25.00 825.00\n"),
    RBC_FRENCH.format(body="5 mars Article un 500,00 1 500,00\n"
                           "12 mars Article deux 300,00 1 200,00\n"),
    RBC_FRENCH.format(body="5 mars Article un 500,00\n"
                           "12 mars Article deux 300,00 1 200,00\n"),
    RBC_FRENCH.format(body="5 mars Article un 500,00 1 500,00\n"
                           "12 mars Article deux 00314,06 300,00 1 200,00\n"),
    RBC_FRENCH.format(body="5 mars Description qui\nse poursuit ici 500,00 1 500,00\n"
                           "1 de 7\n12 mars Article deux 300,00 1 200,00\n"),
)


@pytest.mark.parametrize("markdown", RBC_DOCUMENTS)
def test_rbc_parses_every_grid_document_identically_to_the_oracle(markdown, monkeypatch):
    live = _statement_json(rbc.parse_rbc_statement(markdown))
    monkeypatch.setattr(rbc, "read_grid_rows", _legacy_rbc_read_grid_rows)
    assert live == _statement_json(rbc.parse_rbc_statement(markdown))


#: Entry streams handed straight to the grid reader, including the shapes the
#: two callers cannot currently produce — an entry stream that opens with a
#: line belonging to no posting date, which is the one input on which "items
#: before the first row start belong to no row" could have changed the reading.
RBC_ENTRY_STREAMS = (
    [],
    [("Opening balance 1,000.00", None, False)],
    [("A stray line", "2026-03-02", False), ("Row 100.00", "2026-03-02", True)],
    [("Row 100.00 900.00", "2026-03-02", True), ("", "2026-03-02", False)],
    [("Row 100.00", "2026-03-02", True), ("Closing balance 900.00", "2026-03-02", False)],
    [("Closing balance", "2026-03-02", True)],
    [("Opening balance 1,000.00", None, False), ("Row 100.00 900.00", "2026-03-02", True)],
    [("Leading description", None, False), ("100.00", None, False),
     ("02 Mar row", "2026-03-02", True)],
)


@pytest.mark.parametrize("entries", RBC_ENTRY_STREAMS)
def test_rbc_grid_reader_matches_the_oracle_on_raw_entry_streams(entries):
    kwargs = dict(
        pattern=rbc._MONEY_RE,
        to_amount=lambda token: parse_money(token) or 0.0,
        opening_label="OPENING BALANCE",
        closing_label="CLOSING BALANCE",
    )
    assert tables.read_grid_rows(list(entries), **kwargs) == _legacy_rbc_read_grid_rows(
        list(entries), **kwargs
    )


# ===========================================================================
# TD Canada — frozen oracle for the whole native reader
# ===========================================================================

def _legacy_parse_native_td_canada(markdown: str, base: Statement | None = None):
    """`analysis/td_can.py::_parse_native_td_canada`, verbatim as of `8ce6abc`.

    Frozen whole rather than in part: TD's row selection was interleaved with
    its statement-field extraction in one pass, and splitting that pass is the
    change this oracle exists to prove harmless.
    """
    if not td_can.detect_native(markdown).claims:
        return None

    stmt = base.model_copy(deep=True) if base is not None else Statement()
    stmt.bank = "TD Canada Trust"
    stmt.currency = "CAD"
    stmt.beginning_balance = None
    stmt.ending_balance = None
    stmt.stated_total_credits = None
    stmt.stated_total_debits = None
    stmt.stated_credit_count = None
    stmt.stated_debit_count = None
    stmt.stated_average_balance = None
    rows: list[td_can._NativeRow] = []
    groups: list[tuple[list[int], float]] = []
    pending: list[int] = []
    ending_balance: float | None = None
    in_ledger = False
    default_year: int | None = None

    for raw in markdown.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        upper = line.upper()
        period = td_can._parse_period(line)
        if period:
            stmt.period_start, stmt.period_end = period
            default_year = int(stmt.period_end[:4])
        account = re.search(r"\b\d{4}-\d{6,}\b", line)
        if account:
            stmt.account_number = account.group(0)
        if "BUSINESS CHEQUING" in upper:
            stmt.account_name = "BUSINESS CHEQUING ACCOUNT - CAD"
        if upper.startswith("MONTHLY AVER. CR. BAL."):
            avg = parse_money(line)
            if avg is not None:
                stmt.stated_average_balance = abs(avg)
        if upper.startswith("CREDITS "):
            credit = td_can._parse_summary_count_amount(line)
            if credit:
                stmt.stated_credit_count = (stmt.stated_credit_count or 0) + credit[0]
                stmt.stated_total_credits = round((stmt.stated_total_credits or 0.0) + credit[1], 2)
        if upper.startswith("DEBITS "):
            debit = td_can._parse_summary_count_amount(line)
            if debit:
                stmt.stated_debit_count = (stmt.stated_debit_count or 0) + debit[0]
                stmt.stated_total_debits = round((stmt.stated_total_debits or 0.0) + debit[1], 2)

        if upper.startswith("DESCRIPTION CHEQUE/DEBIT DEPOSIT/CREDIT DATE BALANCE"):
            in_ledger = True
            continue
        if in_ledger and td_can._CHQS_ENCLOSED_RE.match(upper):
            in_ledger = False
            continue
        if not in_ledger or default_year is None:
            continue

        tokens = line.split()
        date_index = next(
            (i for i, token in enumerate(tokens) if td_can._native_date_token(token)), None
        )
        if date_index is None:
            continue

        tx_date = td_can._native_date_to_iso(tokens[date_index], default_year=default_year)
        balance = parse_money(tokens[date_index + 1]) if date_index + 1 < len(tokens) else None
        if upper.startswith("BALANCE FORWARD"):
            if balance is None:
                continue
            if stmt.beginning_balance is None:
                stmt.beginning_balance = balance
            elif pending:
                groups.append((pending, balance))
                pending = []
            continue

        amount_index = None
        amount = None
        for i in range(date_index - 1, -1, -1):
            parsed = parse_money(tokens[i])
            if parsed is not None and "." in tokens[i]:
                amount_index = i
                amount = abs(parsed)
                break
        if amount_index is None or amount is None:
            continue
        desc = " ".join(tokens[:amount_index])
        if not desc:
            continue
        rows.append(td_can._NativeRow(tx_date, desc, td_can._to_cents(amount), balance))
        pending.append(len(rows) - 1)
        if balance is not None:
            groups.append((pending, balance))
            pending = []
            ending_balance = balance

    if not rows:
        return None
    credits = td_can._resolve_native_directions(rows, groups, stmt.beginning_balance)
    stmt.transactions = [
        td_can._tx(row.date, row.description,
                   row.amount / 100 if is_credit else -row.amount / 100)
        for row, is_credit in zip(rows, credits)
    ]
    stmt.ending_balance = ending_balance
    return stmt


#: TD's families: the two-money-column row (T-F1), the page-carried balance
#: (T-F2), the cheque-enclosure terminator (T-F3), an underdetermined group
#: (T-F4), a converted-amount row (T-F5), an overdraft-suffixed balance
#: (T-F6), plus furniture that must not open a row.
TD_LEDGERS = (
    """
BALANCE FORWARD JAN31 100.00
UNLISTED VENDOR ABC 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01 130.00
""",
    """
BALANCE FORWARD JAN31 100.00
UNLISTED VENDOR ABC 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01 50.00
""",
    """
BALANCE FORWARD JAN31 100.00
SOMEWHERE INC MSP 40.00 FEB01
MONTHLY PLAN FEE 10.00 FEB01 50.00
""",
    """
BALANCE FORWARD JAN31 100.00
FIRST UNCODED ROW 40.00 FEB01
SECOND UNCODED ROW 25.00 FEB02
THIRD UNCODED ROW 10.00 FEB03 155.00
""",
    """
BALANCE FORWARD JAN31 100.00
ROW BEFORE THE PAGE BREAK 40.00 FEB01
--- Page 2 ---
Accounts issued by: THE TORONTO-DOMINION BANK
BALANCE FORWARD FEB01 140.00
ROW AFTER THE CARRY 20.00 FEB02 120.00
""",
    """
BALANCE FORWARD JAN31 100.00
TRANSFER OUT BUS 30.00 FEB01
TRANSFER FEE 30.00 FEB01 40.00
""",
    """
BALANCE FORWARD JAN31 100.00
FOREIGN ROW $ 8.00 11.00 FEB01 111.00
""",
    """
BALANCE FORWARD JAN31 371.96OD
UNCODED ROW 40.00 FEB01 331.96OD
""",
    """
BALANCE FORWARD JAN31 100.00
A DESCRIPTION MENTIONING CHQS MID LEDGER 40.00 FEB01 60.00
""",
    """
BALANCE FORWARD JAN31 100.00
A CONTINUATION LINE WITH NO DATE AND NO AMOUNT
UNCODED ROW 40.00 FEB01 140.00
""",
    """
BALANCE FORWARD JAN31 100.00
NO AMOUNT ON THIS ROW FEB01
UNCODED ROW 40.00 FEB01 140.00
""",
    """
40.00 FEB01 140.00
""",
    """
BALANCE FORWARD JAN31 100.00
ROW WITH NO PRINTED BALANCE ANYWHERE 40.00 FEB01
""",
    "\nBALANCE FORWARD JAN31 100.00\n",
    "\n",
)

TD_DOCUMENTS = tuple(
    td_statement(ledger, credits=credits, debits=debits)
    for ledger in TD_LEDGERS
    for credits, debits in (("0 0.00", "0 0.00"), ("1 40.00", "1 10.00"))
) + tuple(
    # T-F3: the terminator carries the enclosed-cheque COUNT, and a row-shaped
    # probe below it must stay outside the ledger whatever the count is.
    td_statement(
        "\nBALANCE FORWARD JAN31 100.00\nUNCODED ROW 40.00 FEB01 140.00\n"
    ).replace("0 CHQS ENCLOSED", f"{count} CHQS ENCLOSED")
    + "\nPROBE ROW BELOW THE TERMINATOR 99.00 FEB02 41.00\n"
    for count in (0, 1, 7, 23)
) + (
    # A ledger line printed before the statement period is known.
    td_statement("\nBALANCE FORWARD JAN31 100.00\nUNCODED ROW 40.00 FEB01 140.00\n")
    .replace("JAN 31/26 - FEB 28/26", "no printed period here"),
)


@pytest.mark.parametrize("markdown", TD_DOCUMENTS)
def test_td_canada_native_reads_every_document_identically_to_the_oracle(markdown):
    assert _statement_json(td_can._parse_native_td_canada(markdown)) == _statement_json(
        _legacy_parse_native_td_canada(markdown)
    )


@pytest.mark.parametrize("markdown", TD_DOCUMENTS)
def test_td_canada_native_reads_a_carried_base_statement_identically(markdown):
    base = Statement(bank="carried", account_name="carried name")
    assert _statement_json(td_can._parse_native_td_canada(markdown, base)) == _statement_json(
        _legacy_parse_native_td_canada(markdown, base)
    )


def test_the_frozen_oracles_are_not_silently_passing_on_nothing():
    """A differential proof over inputs that all parse to `None` proves
    nothing. Every matrix must contain documents that really parse."""
    assert sum(chase.parse_chase_statement(m) is not None for m in CHASE_DOCUMENTS) >= 15
    assert sum(rbc.parse_rbc_statement(m) is not None for m in RBC_DOCUMENTS) >= 15
    assert sum(
        _legacy_parse_native_td_canada(m) is not None for m in TD_DOCUMENTS
    ) >= 15

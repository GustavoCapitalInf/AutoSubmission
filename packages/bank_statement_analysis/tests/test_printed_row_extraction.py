"""DESCCOLS — the `+printed-rows` intake rung (`ocr/native_text.py`).

`_native_pages` joins the lines INSIDE a MuPDF block with a single space. A
block is MuPDF's grouping, not a printed row, so a described ledger arrives
with several postings' text welded onto one line and no boundary in it. W3
§DESCATTRIB closed the harm by refusing to publish a welded span; this rung is
how the refused text comes back, by reading the printed rows out of the line
boxes the flattening threw away.

These fixtures are synthetic PDFs drawn with PyMuPDF at coordinates chosen
here — a date column, a label column, a detail column indented under it, a
right-aligned amount, detail that wraps onto the row's following lines — with
invented merchants, dates and figures. Nothing in this file is copied from a
document.

Each one pins a rule the rung must hold:

* a welded ledger publishes ONE line per printed row, carrying that row's own
  description and no other row's;
* every line of the page outside a repaired ledger is byte-identical, in the
  same place, and no token is invented, dropped or altered anywhere;
* the recovered row reaches the READER: `tables.dated_cells` +
  `tables.attributed_descriptions` publish each row's full printed
  description, which is the whole point of the seam;
* a template that prints the amount ABOVE the merchant detail is declined —
  re-serialising it would move the text no closer to the reader's span;
* a multi-column balance ladder, an unwelded ledger, a two-row coincidence and
  an indented paragraph are all left exactly as the flattening left them;
* a document with nothing to repair is not claimed at all, so the ladder falls
  through to the generic rung and the bytes are exactly today's;
* a ledger whose money right edges disagree, and a right-hand column of bare
  reference figures, are both left alone — the two clauses of G3 the review
  found unpinned;
* a line another page prints at the same band position — page furniture on a
  posting's row — refuses that ledger, while the same line printed once is
  absorbed, which is the residual reach this seam has and the reason G9 exists;
* a malformed line box is a REFUSAL and never an exception, on nine shapes.

A note on what a pin here is worth: a test named after a gate is not a test of
that gate, so every gate label in this file names the gate whose mutant the
test kills, and several pins assert their own
premise (this fixture IS welded / IS repaired when the clause is satisfied)
before they assert a refusal.
"""
from __future__ import annotations

import copy

import fitz
import pytest

import re

from analysis.tables import attributed_descriptions, dated_cells

from ocr.native_text import (
    native_statement,
    parse_native_pdf_text,
    parse_native_printed_rows,
)

FONT_SIZE = 7.0
DATE_X = 23.0
LABEL_X = 65.0
DETAIL_X = 149.0
AMOUNT_RIGHT = 569.0
ROW_PITCH = 9.8
#: The detail column's baseline sits a fraction under the date's, which is why
#: a row is a band rather than an equality.
DETAIL_DROP = 0.7

FILLER = "Notice to members about the deposit agreement. " * 20


def _right(page, y, text):
    width = fitz.get_text_length(text, fontsize=FONT_SIZE)
    page.insert_text((AMOUNT_RIGHT - width, y), text, fontsize=FONT_SIZE)


def _ledger_pdf(rows, *, heading="WIDGET DEBITS", amount_last=True, header=True):
    """A one-page statement printing one described ledger.

    `rows` is `[(date, label, [detail line, ...], amount)]`. With
    `amount_last` the amount is printed on the row's LAST line, under the
    wrapped detail, which is the arrangement the rung repairs; without it the
    amount is printed on the row's FIRST line and the detail below it, which
    is the arrangement it declines.

    **The two columns are drawn in two passes, and that is the point.** A
    producer that emits the grid cells and the description cells as separate
    runs is what makes MuPDF group them into separate BLOCKS, which is what
    makes the flattening weld several postings' detail onto one line with no
    boundary in it. Drawing the page row by row instead produces one block per
    table and no weld at all — a fixture that would let every pin below pass
    without the rung doing anything.
    """
    doc = fitz.open()
    page = doc.new_page()
    grid, detail = [], []
    y = 111.0
    if header:
        grid += [(DATE_X, y, "Date"), (LABEL_X, y, "Description"), (None, y, "Debits")]
        y += 9.1
    for date, label, lines, amount in rows:
        grid += [(DATE_X, y, date), (LABEL_X, y, label)]
        if lines:
            detail.append((DETAIL_X, y - DETAIL_DROP, lines[0]))
        if not amount_last:
            grid.append((None, y, amount))
        if len(lines) < 2:
            if amount_last:
                grid.append((None, y, amount))
            y += ROW_PITCH
            continue
        y += ROW_PITCH
        for extra in lines[1:]:
            detail.append((LABEL_X, y - DETAIL_DROP, extra))
            if extra is not lines[-1]:
                y += ROW_PITCH
        if amount_last:
            grid.append((None, y, amount))
        y += ROW_PITCH
    page.insert_text((DATE_X, 100.0), heading, fontsize=FONT_SIZE)
    for group in (grid, detail):
        for x, at, text in group:
            if x is None:
                _right(page, at, text)
            else:
                page.insert_text((x, at), text, fontsize=FONT_SIZE)
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    return doc.tobytes()


#: Four postings. Two print their detail on one line, two wrap it; every
#: merchant, date and figure is invented for this file.
WELDED_ROWS = [
    ("1-4", "Scheduled Transfer", ["ORCHARD SUPPLY QUARTERLY"], "101.00"),
    ("1-5", "Scheduled Transfer",
     ["MERIDIAN LEASING CO PERIODIC", "AGREEMENT 55-42 SERIES B"], "202.00"),
    ("1-6", "Scheduled Transfer", ["QUILLON UTILITIES LODGEMENT"], "303.00"),
    ("1-7", "Scheduled Transfer",
     ["ATLAS FREIGHT NETWORK ACCT", "99-1 REMITTANCE"], "404.00"),
]

#: What each of those rows PRINTS, read off the fixture rather than off the
#: extractor: the row's own line, in reading order.
WELDED_LINES = [
    "1-4 Scheduled Transfer ORCHARD SUPPLY QUARTERLY 101.00",
    "1-5 Scheduled Transfer MERIDIAN LEASING CO PERIODIC AGREEMENT 55-42 SERIES B 202.00",
    "1-6 Scheduled Transfer QUILLON UTILITIES LODGEMENT 303.00",
    "1-7 Scheduled Transfer ATLAS FREIGHT NETWORK ACCT 99-1 REMITTANCE 404.00",
]


@pytest.fixture(scope="module")
def welded():
    return _ledger_pdf(WELDED_ROWS)


def _lines(document):
    return [line for page in document.pages for line in page.split("\n")]


def test_the_fixture_really_is_welded_before_the_rung_sees_it(welded):
    """The premise, asserted rather than assumed (the §DESCATTRIB M6 lesson).

    A fixture that is not welded would let every pin below pass without the
    rung doing anything.
    """
    flattened = "\n".join(parse_native_pdf_text(welded).pages)
    welded_lines = [line for line in flattened.split("\n")
                    if len(re.findall(r"\d-\d", line)) > 1]
    assert welded_lines, "the flattening did not weld this fixture"


def test_a_welded_ledger_publishes_one_line_per_printed_row(welded):
    document = parse_native_printed_rows(welded)
    assert document is not None
    assert document.model == "native-pdf-text+printed-rows"
    assert [line for line in _lines(document) if line[:1].isdigit()] == WELDED_LINES


def test_no_token_is_invented_dropped_or_altered(welded):
    before = "\n".join(parse_native_pdf_text(welded).pages)
    after = "\n".join(parse_native_printed_rows(welded).pages)
    assert sorted(after.split()) == sorted(before.split())
    assert after != before


def test_every_line_outside_the_repaired_ledger_is_untouched(welded):
    """The fallback, at line granularity: the rung moves the ledger's lines and
    nothing else's, and it moves them nowhere else on the page."""
    ledger = {"Date", "Description", "Debits"}
    for date, label, detail, amount in WELDED_ROWS:
        ledger.update((date, amount, *label.split()))
        for line in detail:
            ledger.update(line.split())

    def outside(text):
        return [line for line in text.splitlines()
                if not set(line.split()) & ledger]

    before = parse_native_pdf_text(welded).pages[0]
    after = parse_native_printed_rows(welded).pages[0]
    assert outside(after) == outside(before)
    assert outside(after)  # the fixture does print lines outside the ledger


def test_the_recovered_row_reaches_the_reader(welded):
    """The seam's purpose: each row's OWN full description is published.

    Run through the two shared functions both core-processor readers call, with
    the same shape they call them in. Before the repair the welded run
    publishes a bare label on every row (§DESCATTRIB's fail-closed count);
    after it, every row publishes what the statement printed for it.
    """
    date_re = re.compile(r"(?<![\w-])((?:1[0-2]|[1-9])-(?:3[01]|[12][0-9]|[1-9]))(?![\w-])")
    figure_re = re.compile(r"(?<![\w.])([0-9][0-9,]*\.[0-9]{2})(?![\w.])")

    def published(pdf_bytes, extractor):
        run = "\n".join(extractor(pdf_bytes).pages)
        run = run[run.index("Date Description Debits"):]
        cells = dated_cells(run, date_pattern=date_re, value_pattern=figure_re)
        return attributed_descriptions([cells], strip=" |", limit=200)[0]

    after = published(welded, parse_native_printed_rows)
    assert after == [
        "Scheduled Transfer ORCHARD SUPPLY QUARTERLY",
        "Scheduled Transfer MERIDIAN LEASING CO PERIODIC AGREEMENT 55-42 SERIES B",
        "Scheduled Transfer QUILLON UTILITIES LODGEMENT",
        "Scheduled Transfer ATLAS FREIGHT NETWORK ACCT 99-1 REMITTANCE",
    ]
    before = published(welded, parse_native_pdf_text)
    assert before != after
    for description in before:
        assert "MERIDIAN" not in description or "ORCHARD" not in description


def test_a_wrapped_detail_never_lands_on_the_row_below_it(welded):
    lines = _lines(parse_native_printed_rows(welded))
    following = next(line for line in lines if line.startswith("1-6"))
    assert "AGREEMENT" not in following
    assert "MERIDIAN" not in following


# ---------------------------------------------------------------------------
# The gates, each pinned by a printing that must NOT be repaired
# ---------------------------------------------------------------------------


def _declined(pdf_bytes):
    """The rung answers None and the generic rung's bytes are what survive."""
    assert parse_native_printed_rows(pdf_bytes) is None
    ladder = native_statement(pdf_bytes)
    generic = parse_native_pdf_text(pdf_bytes)
    assert generic is not None
    assert list(ladder.pages) == list(generic.pages)
    assert ladder.model == generic.model


def test_a_template_printing_the_amount_above_its_detail_is_declined():
    """G8. The amount is on the row's FIRST line and the detail below it, so a
    reader's span (date to first figure) cannot hold the detail however the
    lines are cut — re-serialising would change the text for no gain."""
    _declined(_ledger_pdf(WELDED_ROWS, amount_last=False))


def test_a_multi_column_balance_ladder_is_left_alone():
    """G8, and the reason there is no separate multi-column gate: four (date,
    figure) pairs side by side means the row's FIRST money is never its last
    printed cell, so the amount-last gate declines it. Measured rather than
    reasoned about — an explicit `at most one money cell` gate was written
    first and proved to change no answer."""
    doc = fitz.open()
    page = doc.new_page()
    y = 100.0
    page.insert_text((DATE_X, y), "DAILY WIDGET BALANCES", fontsize=FONT_SIZE)
    y += 11.0
    for row in range(6):
        for column in range(4):
            x = DATE_X + column * 140.0
            page.insert_text((x, y), f"5-{row + 1}", fontsize=FONT_SIZE)
            page.insert_text((x + 40.0, y), f"{row + 1}{column + 1}0.00", fontsize=FONT_SIZE)
        y += ROW_PITCH
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    _declined(doc.tobytes())


def test_a_ledger_the_layer_did_not_weld_is_not_claimed():
    """G5. Every gate above passes — an anchor column, four rows, a
    right-aligned money column, a description — and no block spans more than
    one band, so the flattening ALREADY prints one line per row. Claiming it
    would rotate the document's cache key for an identical reading.

    The rows are drawn one at a time with a wide pitch, which is what makes
    MuPDF give each its own block. The fixture asserts that premise: without
    it the region would be refused higher up and this would pin nothing.
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((DATE_X, 100.0), "WIDGET DEBITS", fontsize=FONT_SIZE)
    y = 120.0
    for date, label, lines, amount in WELDED_ROWS:
        page.insert_text((DATE_X, y), date, fontsize=FONT_SIZE)
        page.insert_text((LABEL_X, y), label, fontsize=FONT_SIZE)
        page.insert_text((DETAIL_X, y), lines[0], fontsize=FONT_SIZE)
        _right(page, y, amount)
        y += 30.0
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    raw = doc.tobytes()

    import ocr.native_text as native_text
    with fitz.open(stream=raw, filetype="pdf") as opened:
        printed = native_text._printed_lines(opened[0])
        bands = native_text._row_bands(printed)
        regions = native_text._candidate_regions(printed, bands)
    assert regions, "the fixture must reach the weld gate, not be refused above it"
    assert len(regions[0][1]) >= 3

    _declined(raw)


def test_two_rows_are_not_a_grid():
    """G2. Three printed rows are the smallest thing this rung calls a grid,
    and the fixture prints exactly TWO — one short — so a mutant that lowers
    the floor by one repairs it and dies here."""
    _declined(_ledger_pdf(WELDED_ROWS[:2], header=False))


def test_an_indented_paragraph_is_not_a_ledger():
    """G4/G5. Lines under a heading, indented, with no right-aligned money
    column: an address block has the shape of a row grid and none of its
    substance."""
    doc = fitz.open()
    page = doc.new_page()
    y = 100.0
    for line in ("REMITTANCE ADDRESS", "WIDGET CLEARING CENTRE",
                 "PO BOX 4120 WHARFSIDE MAIN", "FICTIONVILLE ZZ 00000",
                 "REMITTANCE ADDRESS", "WIDGET CLEARING CENTRE"):
        page.insert_text((LABEL_X, y), line, fontsize=FONT_SIZE)
        page.insert_text((DETAIL_X + 200.0, y), "OVERLEAF", fontsize=FONT_SIZE)
        y += ROW_PITCH
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    _declined(doc.tobytes())


def test_a_ledger_without_three_described_rows_is_left_alone():
    """G4, isolated — and the pin that kills the floor mutation by ANSWER.

    Four rows, every one carrying a money cell at the same right edge, so the
    money floor and the right-edge agreement are both satisfied and the region
    reaches G4 with nothing above it refusing. Only TWO rows carry a cell that
    is neither the row's anchor nor its money, so there is not enough
    description here to give back and the region is declined for that reason
    alone.

    The address-block pin above used to kill the floor mutation by CRASH: with
    the floors removed `max(edges, …)` ran on an empty list and the
    `ValueError` escaped the rung. F8's fail-closed guard converts that crash
    into a refusal, which is the right behaviour and a worse test — a mutation
    must die on a wrong ANSWER, not on an exception the platform now catches.
    """
    doc = fitz.open()
    page = doc.new_page()
    grid, detail = [], []
    y = 111.0
    for date, lines, amount in (
            ("2031-05-03", ["ORCHARD SUPPLY QUARTERLY",
                            "AGREEMENT 55-42 SERIES B"], "101.00"),
            ("2031-05-04", ["MERIDIAN LEASING CO PERIODIC",
                            "AGREEMENT 77-11 SERIES C"], "202.00"),
            ("2031-05-05", [], "303.00"),
            ("2031-05-06", [], "404.00")):
        grid.append((DATE_X, y, date))
        for offset, line in enumerate(lines):
            detail.append((DETAIL_X, y + offset * ROW_PITCH - DETAIL_DROP, line))
        y += ROW_PITCH * max(len(lines), 1)
        grid.append((None, y - ROW_PITCH, amount))
    for group in (grid, detail):
        for x, at, text in group:
            if x is None:
                _right(page, at, text)
            else:
                page.insert_text((x, at), text, fontsize=FONT_SIZE)
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    raw = doc.tobytes()

    import ocr.native_text as native_text
    with fitz.open(stream=raw, filetype="pdf") as opened:
        printed = native_text._printed_lines(opened[0])
        bands = native_text._row_bands(printed)
        regions = native_text._candidate_regions(printed, bands)
    assert regions, "the fixture must reach the floors, not be refused above them"
    end, starts = regions[0]
    assert len(starts) == 4
    rows = [[p for band in range(start, (starts + [end])[order + 1])
             for p in bands[band]]
            for order, start in enumerate(starts)]
    money = [[p for p in row if native_text._ROW_MONEY_RE.match(printed[p].text)]
             for row in rows]
    assert all(len(cells) == 1 and cells[0] == row[-1]
               for cells, row in zip(money, rows)), "every row's money is last"
    edges = {round(printed[cells[0]].right, 1) for cells in money}
    assert len(edges) == 1, "the money column agrees, so G3 cannot be the refusal"
    described = sum(any(p != row[0] and p not in cells for p in row)
                    for row, cells in zip(rows, money))
    assert described == 2, "two described rows: one short of the floor"

    _declined(raw)


def test_a_document_with_no_native_text_is_not_claimed():
    doc = fitz.open()
    doc.new_page()
    assert parse_native_printed_rows(doc.tobytes()) is None


def test_a_pdf_that_cannot_be_opened_is_not_claimed():
    assert parse_native_printed_rows(b"not a pdf at all") is None


def test_the_ladder_claims_the_repaired_document_and_keeps_the_generic_last(welded):
    document = native_statement(welded)
    assert document.model == "native-pdf-text+printed-rows"
    assert list(document.pages) == list(parse_native_printed_rows(welded).pages)
    assert list(document.pages) != list(parse_native_pdf_text(welded).pages)


def test_an_unreadable_text_layer_is_a_refusal_and_not_a_crash(monkeypatch, welded):
    """The RUNG-SEAM class: MuPDF raising out of `get_text` must reach this
    rung as a refusal, not as an escaped exception."""
    import ocr.native_text as native_text

    real = native_text._page_text

    def explode(page, *args, **kwargs):
        if args and args[0] == "dict":
            raise native_text._UnreadableTextLayer("RuntimeError: cycle in resources")
        return real(page, *args, **kwargs)

    monkeypatch.setattr(native_text, "_page_text", explode)
    assert native_text.parse_native_printed_rows(welded) is None


def test_a_detail_that_looks_like_a_date_does_not_steal_the_row(welded):
    """A merchant reference of the row-date's own shape sits INSIDE the span
    after the repair, where a reader's date grammar will meet it. The pairing
    of a date to the figure that closes it must survive that."""
    rows = [
        ("1-4", "Scheduled Transfer", ["ORCHARD SUPPLY INVOICE 5-2"], "101.00"),
        ("1-5", "Scheduled Transfer",
         ["MERIDIAN LEASING CO INVOICE 6-3", "AGREEMENT 55-42 SERIES B"], "202.00"),
        ("1-6", "Scheduled Transfer", ["QUILLON UTILITIES LODGEMENT 7-4"], "303.00"),
    ]
    document = parse_native_printed_rows(_ledger_pdf(rows))
    assert document is not None
    printed = [line for line in _lines(document) if line[:1].isdigit()]
    assert printed == [
        "1-4 Scheduled Transfer ORCHARD SUPPLY INVOICE 5-2 101.00",
        "1-5 Scheduled Transfer MERIDIAN LEASING CO INVOICE 6-3 AGREEMENT 55-42 SERIES B 202.00",
        "1-6 Scheduled Transfer QUILLON UTILITIES LODGEMENT 7-4 303.00",
    ]


def test_a_row_may_wrap_more_than_once_and_still_be_one_line():
    rows = [
        ("1-4", "Scheduled Transfer", ["ORCHARD SUPPLY QUARTERLY"], "101.00"),
        ("1-5", "Scheduled Transfer",
         ["MERIDIAN LEASING CO PERIODIC", "AGREEMENT 55-42 SERIES B",
          "REMITTANCE ADVICE ENCLOSED"], "202.00"),
        ("1-6", "Scheduled Transfer", ["QUILLON UTILITIES LODGEMENT"], "303.00"),
    ]
    document = parse_native_printed_rows(_ledger_pdf(rows))
    assert document is not None
    printed = [line for line in _lines(document) if line[:1].isdigit()]
    assert printed[1] == (
        "1-5 Scheduled Transfer MERIDIAN LEASING CO PERIODIC "
        "AGREEMENT 55-42 SERIES B REMITTANCE ADVICE ENCLOSED 202.00")


def test_a_block_straddling_the_ledger_boundary_refuses_the_whole_document():
    """G6. A block with lines inside AND outside a repairable region cannot be
    half re-serialised and half left alone, and guessing which half is which is
    the kind of repair this platform refuses. `_printed_row_page` is called
    directly because a straddle is a property of MuPDF's own grouping and no
    fixture can be relied on to produce one on demand."""
    import ocr.native_text as native_text

    class _Page:
        def get_text(self, mode, *args, **kwargs):
            # one block (0) holding a heading AND the grid cells of three rows,
            # one block (1) holding the description column
            spans = [
                (0, 100.0, 108.0, 23.0, 90.0, "WIDGET DEBITS"),
                (0, 111.0, 119.0, 23.0, 37.0, "1-4"),
                (0, 111.0, 119.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 111.0, 119.0, 530.0, 569.0, "101.00"),
                (0, 121.0, 129.0, 23.0, 37.0, "1-5"),
                (0, 121.0, 129.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 121.0, 129.0, 530.0, 569.0, "202.00"),
                (0, 131.0, 139.0, 23.0, 37.0, "1-6"),
                (0, 131.0, 139.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 131.0, 139.0, 530.0, 569.0, "303.00"),
                (1, 111.7, 119.7, 149.0, 400.0, "ORCHARD SUPPLY QUARTERLY"),
                (1, 121.7, 129.7, 149.0, 400.0, "MERIDIAN LEASING CO PERIODIC"),
                (1, 131.7, 139.7, 149.0, 400.0, "QUILLON UTILITIES LODGEMENT"),
            ]
            blocks: dict[int, dict] = {}
            for block, top, bottom, left, right, text in spans:
                blocks.setdefault(block, {"type": 0, "lines": []})["lines"].append(
                    {"bbox": (left, top, right, bottom),
                     "spans": [{"text": text}]})
            return {"blocks": [blocks[key] for key in sorted(blocks)]}

    flattened = "\n".join((
        "WIDGET DEBITS 1-4 Scheduled Transfer 101.00 1-5 Scheduled Transfer "
        "202.00 1-6 Scheduled Transfer 303.00",
        "ORCHARD SUPPLY QUARTERLY MERIDIAN LEASING CO PERIODIC "
        "QUILLON UTILITIES LODGEMENT",
    ))
    assert native_text._printed_row_page(_Page(), flattened) is None


def _one_ledger_page():
    """A page object whose `dict` blocks print one welded described ledger.

    Hand-built rather than drawn, because the two pins below need the page and
    the flattened text to be supplied independently of each other.
    """
    import ocr.native_text as native_text  # noqa: F401 — parity with the caller

    class _Page:
        def get_text(self, mode, *args, **kwargs):
            spans = [
                (0, 111.0, 119.0, 23.0, 37.0, "1-4"),
                (0, 111.0, 119.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 111.0, 119.0, 530.0, 569.0, "101.00"),
                (0, 121.0, 129.0, 23.0, 37.0, "1-5"),
                (0, 121.0, 129.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 121.0, 129.0, 530.0, 569.0, "202.00"),
                (0, 131.0, 139.0, 23.0, 37.0, "1-6"),
                (0, 131.0, 139.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 131.0, 139.0, 530.0, 569.0, "303.00"),
                (1, 111.7, 119.7, 149.0, 400.0, "ORCHARD SUPPLY QUARTERLY"),
                (1, 121.7, 129.7, 149.0, 400.0, "MERIDIAN LEASING CO PERIODIC"),
                (1, 131.7, 139.7, 149.0, 400.0, "QUILLON UTILITIES LODGEMENT"),
            ]
            blocks: dict[int, dict] = {}
            for block, top, bottom, left, right, text in spans:
                blocks.setdefault(block, {"type": 0, "lines": []})["lines"].append(
                    {"bbox": (left, top, right, bottom), "spans": [{"text": text}]})
            return {"blocks": [blocks[key] for key in sorted(blocks)]}

    flattened = "\n".join((
        "1-4 Scheduled Transfer 101.00 1-5 Scheduled Transfer 202.00 "
        "1-6 Scheduled Transfer 303.00",
        "ORCHARD SUPPLY QUARTERLY MERIDIAN LEASING CO PERIODIC QUILLON UTILITIES LODGEMENT",
    ))
    return _Page(), flattened


def test_the_hand_built_page_is_repaired_when_its_tokens_agree():
    """The premise of the pin below: this page IS repairable, so a refusal
    there is the conservation check firing and not the page being declined."""
    import ocr.native_text as native_text

    page, flattened = _one_ledger_page()
    assert native_text._printed_row_page(page, flattened) == "\n".join((
        "1-4 Scheduled Transfer ORCHARD SUPPLY QUARTERLY 101.00",
        "1-5 Scheduled Transfer MERIDIAN LEASING CO PERIODIC 202.00",
        "1-6 Scheduled Transfer QUILLON UTILITIES LODGEMENT 303.00",
    ))


def test_a_token_the_flattening_saw_and_the_boxes_did_not_refuses_the_page():
    """G7. The rung re-serialises what `get_text("dict")` reports and hands the
    result to readers who were given what `get_text("blocks")` reported. The
    two are different extractions of the same page and are not contractually
    identical — a ligature, a soft hyphen or a future MuPDF could separate
    them. Conservation is checked on the emitted text, so any such divergence
    is a refusal rather than a silently altered document."""
    import ocr.native_text as native_text

    page, flattened = _one_ledger_page()
    assert native_text._printed_row_page(page, flattened + " STATEMENT") is None
    assert native_text._printed_row_page(
        page, flattened.replace("QUILLON UTILITIES LODGEMENT", "QUILLON UTILITIES")) is None


def test_the_repaired_page_prints_its_lines_where_the_page_prints_them(welded):
    """Placement, not just content: a repaired row stands where the ledger
    stood, between the heading above it and the notice below it."""
    lines = parse_native_printed_rows(welded).pages[0].splitlines()
    assert lines[:6] == ["WIDGET DEBITS", "Date Description Debits", *WELDED_LINES]
    assert lines[6].startswith("Notice to members")


def test_a_line_printed_left_of_the_anchor_ends_the_ledger():
    """G1. A band that starts to the LEFT of the anchor is not a continuation
    of the row above it — the page has moved on to something else — and the
    ledger must end there rather than swallow it."""
    doc = fitz.open()
    page = doc.new_page()
    grid, detail = [], []
    y = 111.0
    for date, label, lines, amount in WELDED_ROWS[:3]:
        grid += [(DATE_X, y, date), (LABEL_X, y, label), (None, y, amount)]
        detail.append((DETAIL_X, y - DETAIL_DROP, lines[0]))
        y += ROW_PITCH
    page.insert_text((DATE_X, 100.0), "WIDGET DEBITS", fontsize=FONT_SIZE)
    for group in (grid, detail):
        for x, at, text in group:
            if x is None:
                _right(page, at, text)
            else:
                page.insert_text((x, at), text, fontsize=FONT_SIZE)
    page.insert_text((10.0, y + 40.0), "CONTINUED OVERLEAF", fontsize=FONT_SIZE)
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)

    document = parse_native_printed_rows(doc.tobytes())
    assert document is not None
    printed = document.pages[0].splitlines()
    assert "CONTINUED OVERLEAF" in printed
    assert not any("CONTINUED OVERLEAF" in line and line != "CONTINUED OVERLEAF"
                   for line in printed)


def test_a_row_with_several_money_cells_can_never_pass_the_amount_last_gate():
    """Why there is no separate multi-column gate, pinned rather than argued.

    An explicit `at most one money cell per row` gate was written first and the
    mutation harness proved it changed no answer. The reason is structural: the
    cells of a row are in printed reading order, so a row's FIRST money cell
    can only be its LAST printed cell when it is the only one. Anything with
    two money cells therefore fails the amount-last gate before any
    multi-column rule could be consulted.

    Asserted over every arrangement of up to five cells rather than on one
    example, because the claim is about the ordering and not about a layout.
    """
    import itertools

    import ocr.native_text as native_text

    for size in range(2, 6):
        for shape in itertools.product("md", repeat=size):
            money = [index for index, kind in enumerate(shape) if kind == "m"]
            if len(money) < 2:
                continue
            assert money[0] != size - 1, (
                f"a row shaped {''.join(shape)} would reach the multi-column case")
    # and the gate the rung actually applies is that same comparison
    assert "if money[0] != row[-1]:" in native_text.__loader__.get_source(
        "ocr.native_text")


def test_a_region_whose_blocks_do_not_weld_is_left_alone():
    """G5, isolated. The rows here are printed as two blocks on each band — a
    grid block and a description block — and NO block spans more than one
    band, so the flattening loses no row boundary and there is nothing to give
    back. Re-serialising anyway would still change the text (three lines
    instead of six) and rotate the document's cache key for a reading that is
    already correct.

    Hand-built rather than drawn, for the reason the straddle pin gives: which
    lines MuPDF groups into a block is MuPDF's decision, and every synthetic
    PDF that puts a column in three consecutive bands has it group that column
    into one spanning block — i.e. into a weld. The arrangement this gate
    exists for cannot be produced on demand, so it is stated directly.
    """
    import ocr.native_text as native_text

    rows = [("1-4", "101.00", "ORCHARD SUPPLY QUARTERLY"),
            ("1-5", "202.00", "MERIDIAN LEASING CO PERIODIC"),
            ("1-6", "303.00", "QUILLON UTILITIES LODGEMENT")]

    class _Page:
        def get_text(self, mode, *args, **kwargs):
            blocks = []
            for index, (date, amount, detail) in enumerate(rows):
                top = 111.0 + index * 10.0
                blocks.append({"type": 0, "lines": [
                    {"bbox": (23.0, top, 37.0, top + 8.0), "spans": [{"text": date}]},
                    {"bbox": (65.0, top, 146.0, top + 8.0),
                     "spans": [{"text": "Scheduled Transfer"}]},
                    {"bbox": (530.0, top, 569.0, top + 8.0), "spans": [{"text": amount}]},
                ]})
                blocks.append({"type": 0, "lines": [
                    {"bbox": (149.0, top + 0.7, 400.0, top + 8.7),
                     "spans": [{"text": detail}]},
                ]})
            return {"blocks": blocks}

    flattened = "\n".join(
        line for date, amount, detail in rows
        for line in (f"{date} Scheduled Transfer {amount}", detail))
    page = _Page()

    # the premise: every band holds two blocks and no block spans two bands
    printed = native_text._printed_lines(page)
    bands = native_text._row_bands(printed)
    assert len(bands) == len(rows)
    assert all(len({printed[p].block for p in band}) == 2 for band in bands)
    spans: dict[int, set[int]] = {}
    for index, band in enumerate(bands):
        for position in band:
            spans.setdefault(printed[position].block, set()).add(index)
    assert all(len(seen) == 1 for seen in spans.values())
    assert native_text._candidate_regions(printed, bands), "must reach the weld gate"

    assert native_text._printed_row_page(page, flattened) == flattened


# ---------------------------------------------------------------------------
# The malformed line box: a refusal is an answer and an exception is not
# ---------------------------------------------------------------------------
#
# This rung calls `get_text("dict")` on EVERY native-text document in the
# archive, so any shape MuPDF can hand back is a shape that reaches production.
# The review's probe found three of six shapes escaping the rung as exceptions
# — `KeyError: 'bbox'`, `ValueError: not enough values to unpack` and
# `TypeError: unsupported operand type(s) for -` — which crashes the OCR stage
# for that document instead of falling through to the generic rung. Each shape
# below is pinned to the same answer: the page keeps the flattening's own
# text, the document is not claimed, and the ladder's bytes are byte-identical
# to the generic rung's.


# ---------------------------------------------------------------------------
# G3 is one row of the gate table and TWO independent checks in the code
# ---------------------------------------------------------------------------
#
# The review deleted each half on its own and no test died for either: the
# floor (`≥3 rows carry a money cell`) is mutated by M4, but the RIGHT-EDGE
# AGREEMENT that makes those cells a printed money COLUMN was unpinned, and so
# was `_ROW_MONEY_RE`, the regex that decides which cells are money at all and
# therefore decides both G3 and G8. Both fixtures below are hand-built for the
# reason the straddle pin gives — the arrangement is a property of where the
# ink is — and each is asserted in BOTH directions, so a refusal is known to be
# the clause under test rather than something above it.


def _hand_built_ledger(right_cells, edges):
    """A page printing one welded described ledger, and its flattened text.

    Each row is a date and its description on one band, and a right-hand cell
    on the band under it — so the row's last printed cell is the right-hand one
    whatever it says, and G8 is satisfied for every arrangement below.
    """
    dates = ("2031-06-02", "2031-06-03", "2031-06-04")
    described = ("ORCHARD SUPPLY QUARTERLY", "MERIDIAN LEASING CO PERIODIC",
                 "QUILLON UTILITIES LODGEMENT")
    grid, detail = [], []
    for index, (date, text) in enumerate(zip(dates, described)):
        top = 111.0 + index * 20.0
        grid.append({"bbox": (DATE_X, top, 60.0, top + 8.0), "spans": [{"text": date}]})
        detail.append({"bbox": (DETAIL_X, top, 400.0, top + 8.0),
                       "spans": [{"text": text}]})
        grid.append({"bbox": (edges[index] - 39.0, top + 10.0, edges[index], top + 18.0),
                     "spans": [{"text": right_cells[index]}]})

    class _Page:
        def get_text(self, mode, *args, **kwargs):
            return {"blocks": [{"type": 0, "lines": grid},
                               {"type": 0, "lines": detail}]}

    flattened = "\n".join((
        " ".join(f"{date} {cell}" for date, cell in zip(dates, right_cells)),
        " ".join(described),
    ))
    return _Page(), flattened


#: Three printed amounts, invented here.
AMOUNTS = ("101.00", "202.00", "303.00")
#: The same column printed as bare reference figures instead of amounts.
REFERENCES = ("44190", "44207", "44231")
#: A right-aligned money column: one edge, shared.
ALIGNED = (569.0, 569.0, 569.0)
#: The same three cells with their right edges 25 and 55 points apart.
RAGGED = (489.0, 544.0, 569.0)


def test_money_cells_whose_right_edges_disagree_are_not_a_money_column():
    """G3, second half. Three money cells do not make a ledger; three money
    cells sharing a printed right edge do. A region whose figures are scattered
    across the page is something else — a form, a summary, an invoice block —
    and re-serialising it would move text a reader's span never asked for."""
    import ocr.native_text as native_text

    page, flattened = _hand_built_ledger(AMOUNTS, ALIGNED)
    aligned = native_text._printed_row_page(page, flattened)
    assert aligned is not None and aligned != flattened, (
        "the premise: this ledger IS repaired when its money column agrees")

    page, flattened = _hand_built_ledger(AMOUNTS, RAGGED)
    assert native_text._printed_row_page(page, flattened) == flattened


def test_a_right_hand_column_of_bare_figures_is_not_a_money_column():
    """`_ROW_MONEY_RE` decides which cells are money, and therefore decides
    both G3 and G8. A right-hand column of bare reference figures is not a
    printed money column: nothing in this region is an amount, so there is no
    ledger here and the region is left exactly as the flattening left it."""
    import ocr.native_text as native_text

    page, flattened = _hand_built_ledger(AMOUNTS, ALIGNED)
    assert native_text._printed_row_page(page, flattened) != flattened, (
        "the premise: the same geometry with printed amounts IS repaired")

    page, flattened = _hand_built_ledger(REFERENCES, ALIGNED)
    assert native_text._printed_row_page(page, flattened) == flattened
    assert not any(native_text._ROW_MONEY_RE.match(cell) for cell in REFERENCES)
    assert all(native_text._ROW_MONEY_RE.match(cell) for cell in AMOUNTS)


# ---------------------------------------------------------------------------
# Page furniture on a posting's band (G9), and the ledger's own columns (G10)
# ---------------------------------------------------------------------------
#
# A repaired row carries every cell printed on its band left of its money, so a
# line the page prints there for its own reasons — a running header, a footer,
# a column caption, an overleaf notice — lands INSIDE the row, between its date
# and its amount, which is exactly where a reader's span looks. The card's own
# WORD-box oracle reads a row's truth from the words printed between its date
# and its amount, so it cannot see this class at all: the absorbed line is part
# of the truth it compares against.
#
# G9 refuses the ledger it happens in. The test of "is this the page's
# furniture or this row's text" is REPETITION: furniture prints on more than
# one page at the same band position, a posting's own text does not.

#: Where an overleaf notice is printed: left of the money column, so G8 cannot
#: catch it, and inside the ledger's columns, so G10 cannot either.
NOTE_X = 420.0
#: The band the notice shares — the first posting's own row on both pages.
NOTE_Y = 111.0

PAGE_A_ROWS = [
    ("2031-06-02", "Scheduled Transfer", ["ORCHARD SUPPLY QUARTERLY"], "101.00"),
    ("2031-06-03", "Scheduled Transfer",
     ["MERIDIAN LEASING CO PERIODIC", "AGREEMENT 55-42 SERIES B"], "202.00"),
    ("2031-06-04", "Scheduled Transfer", ["QUILLON UTILITIES LODGEMENT"], "303.00"),
]
PAGE_B_ROWS = [
    ("2031-07-05", "Recurring Payment", ["ATLAS FREIGHT NETWORK ACCT"], "505.00"),
    ("2031-07-06", "Recurring Payment", ["ORCHARD SUPPLY MONTHLY"], "606.00"),
    ("2031-07-07", "Recurring Payment", ["QUILLON UTILITIES SETTLEMENT"], "707.00"),
]
NOTICE = "OVERLEAF NOTICE"


def _draw_ledger(page, rows, note=None):
    """One described ledger, grid pass then detail pass then the notice.

    Three passes for the reason the family's builder gives for two: which lines
    MuPDF groups into a block is decided by the order they are drawn, and page
    furniture that arrives in the grid's own block is not the adversarial case.
    """
    grid, detail = [], []
    y = NOTE_Y
    for date, label, lines, amount in rows:
        grid += [(DATE_X, y, date), (LABEL_X, y, label)]
        if lines:
            detail.append((DETAIL_X, y - DETAIL_DROP, lines[0]))
        if len(lines) < 2:
            grid.append((None, y, amount))
            y += ROW_PITCH
            continue
        y += ROW_PITCH
        for extra in lines[1:]:
            detail.append((LABEL_X, y - DETAIL_DROP, extra))
            if extra is not lines[-1]:
                y += ROW_PITCH
        grid.append((None, y, amount))
        y += ROW_PITCH
    for group in (grid, detail):
        for x, at, text in group:
            if x is None:
                _right(page, at, text)
            else:
                page.insert_text((x, at), text, fontsize=FONT_SIZE)
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    if note:
        page.insert_text((NOTE_X, NOTE_Y), note, fontsize=FONT_SIZE)


def _two_page_pdf(notes=(None, None)):
    """Two pages of the same template printing DIFFERENT postings.

    Different on purpose: two identical pages would make every line of both
    repeated furniture, which is a true answer to a question nobody asked.
    """
    doc = fitz.open()
    for rows, note in zip((PAGE_A_ROWS, PAGE_B_ROWS), notes):
        _draw_ledger(doc.new_page(), rows, note)
    return doc.tobytes()


def _furniture_marks(pdf_bytes):
    import ocr.native_text as native_text

    with fitz.open(stream=pdf_bytes, filetype="pdf") as opened:
        printed = [native_text._printed_lines(page) for page in opened]
        return printed, native_text._repeated_furniture(printed)


def test_two_pages_of_one_template_are_repaired_when_nothing_repeats_in_the_ledger():
    """The premise of the two pins below, and the pin that G9 is not a blanket
    refusal of every multi-page document: these two pages DO share repeated
    furniture — the notice paragraph at the foot of each — and it sits outside
    both ledgers, so both ledgers are repaired."""
    raw = _two_page_pdf()
    printed, marks = _furniture_marks(raw)
    assert any(marks), "the two pages share no furniture at all; the pins below are vacuous"

    document = parse_native_printed_rows(raw)
    assert document is not None
    generic = parse_native_pdf_text(raw)
    assert [page for page in document.pages] != list(generic.pages)
    for index in range(2):
        assert document.pages[index] != generic.pages[index], (
            f"page {index} was not repaired, so it cannot show G9 refusing one")


def test_repeated_page_furniture_on_a_posting_band_refuses_that_ledger():
    """G9, and the review's F3 shape drawn as a page.

    The same notice is printed on BOTH pages at the same band position, on a
    posting's own row, left of the money column — where G8 cannot catch it
    (the row's money is still its last cell) and G10 cannot either (it is
    inside the ledger's columns). Without G9 that notice is folded into the
    posting's published description; with it, both ledgers refuse and the
    document keeps the flattening's own text.
    """
    raw = _two_page_pdf((NOTICE, NOTICE))
    printed, marks = _furniture_marks(raw)
    for index in range(2):
        notice = [position for position, line in enumerate(printed[index])
                  if line.text == NOTICE]
        assert notice, f"page {index} does not print the notice"
        assert set(notice) <= marks[index], "G9 has to recognise it as repeated"

    _declined(raw)


def test_a_repaired_row_absorbs_a_same_band_line_left_of_the_money_column():
    """The residual reach, named and pinned rather than left latent.

    The SAME notice printed on one page only is not furniture by any test this
    rung can make, and the row absorbs it: the emitted line is what the page
    prints on that row, which is this platform's contract, and the reader
    publishes it as part of the row's description. A future editor reading this
    pin knows the behaviour is intended and knows exactly what bounds it — the
    repetition test above, and nothing else.
    """
    raw = _two_page_pdf((NOTICE, None))
    printed, marks = _furniture_marks(raw)
    notice = [position for position, line in enumerate(printed[0])
              if line.text == NOTICE]
    assert notice and not set(notice) & marks[0], (
        "printed once, the notice is not furniture by any test this rung can make")

    document = parse_native_printed_rows(raw)
    assert document is not None
    first = [line for line in document.pages[0].splitlines()
             if line.startswith(PAGE_A_ROWS[0][0])]
    assert len(first) == 1
    assert NOTICE in first[0], "the row absorbs the line printed on its own band"
    assert first[0].endswith(PAGE_A_ROWS[0][3]), "and its money is still last"


def test_a_line_printed_beyond_the_money_column_refuses_the_ledger():
    """G10. A cell printed to the RIGHT of the widest money edge is not part of
    a row of this ledger, and it reaches the row without G8 noticing because
    the row's own money is still the last cell of its last band.

    Hand-built for the reason the straddle pin gives: the arrangement is a
    property of where the ink is, and a drawn page cannot be relied on to
    produce this one on demand.
    """
    import ocr.native_text as native_text

    def page_and_text(note_left):
        rows = (("2031-06-02", "ORCHARD SUPPLY QUARTERLY", "101.00"),
                ("2031-06-03", "MERIDIAN LEASING CO PERIODIC", "202.00"),
                ("2031-06-04", "QUILLON UTILITIES LODGEMENT", "303.00"))
        grid, detail, notes = [], [], []
        for index, (date, described, amount) in enumerate(rows):
            top = 111.0 + index * 20.0
            grid.append({"bbox": (23.0, top, 60.0, top + 8.0),
                         "spans": [{"text": date}]})
            grid.append({"bbox": (530.0, top + 10.0, 569.0, top + 18.0),
                         "spans": [{"text": amount}]})
            detail.append({"bbox": (149.0, top + 10.0, 400.0, top + 18.0),
                           "spans": [{"text": described}]})
            notes.append({"bbox": (note_left, top, note_left + 25.0, top + 8.0),
                          "spans": [{"text": "SEE OVER"}]})

        class _Page:
            def get_text(self, mode, *args, **kwargs):
                return {"blocks": [{"type": 0, "lines": block}
                                   for block in (grid, detail, notes)]}

        flattened = "\n".join((
            " ".join(f"{date} {amount}" for date, _d, amount in rows),
            " ".join(described for _date, described, _a in rows),
            " ".join("SEE OVER" for _row in rows),
        ))
        return _Page(), flattened

    inside, flattened = page_and_text(420.0)
    repaired = native_text._printed_row_page(inside, flattened)
    assert repaired is not None and repaired != flattened, (
        "the premise: this ledger IS repaired while the cell sits in its columns")

    beyond, flattened = page_and_text(575.0)
    assert native_text._printed_row_page(beyond, flattened) == flattened


def _first_text_line(read):
    for block in read.get("blocks", []):
        if block.get("type") == 0 and block.get("lines"):
            return block["lines"][0]
    raise AssertionError("this page prints no text line to mangle")


def _no_blocks_key(read):
    read.pop("blocks")


def _blocks_is_not_a_list(read):
    read["blocks"] = {"0": read["blocks"][0]}


def _no_bbox_key(read):
    _first_text_line(read).pop("bbox")


def _bbox_of_three_numbers(read):
    line = _first_text_line(read)
    line["bbox"] = tuple(line["bbox"])[:3]


def _bbox_of_strings(read):
    line = _first_text_line(read)
    line["bbox"] = tuple(str(value) for value in line["bbox"])


def _bbox_of_nones(read):
    _first_text_line(read)["bbox"] = (None, None, None, None)


def _bbox_with_no_height(read):
    line = _first_text_line(read)
    x0, y0, x1, _y1 = tuple(line["bbox"])
    line["bbox"] = (x0, y0, x1, y0)


def _no_spans_key(read):
    _first_text_line(read).pop("spans")


def _no_spans_at_all(read):
    _first_text_line(read)["spans"] = []


#: The six shapes the review probed, and two more the fail-closed rule names:
#: a degenerate box and a line with no spans. Every one is a page the rung must
#: REFUSE rather than read on a guess or raise out of.
MALFORMED = {
    "no blocks key at all": _no_blocks_key,
    "blocks is not a list": _blocks_is_not_a_list,
    "a line with no bbox key": _no_bbox_key,
    "a bbox of three numbers": _bbox_of_three_numbers,
    "a bbox of strings": _bbox_of_strings,
    "a bbox of Nones": _bbox_of_nones,
    "a bbox with no height": _bbox_with_no_height,
    "a line with no spans key": _no_spans_key,
    "a line with no spans at all": _no_spans_at_all,
}


@pytest.fixture
def mangled(monkeypatch):
    """Install a mangler on the `dict` read only, and leave every other alone.

    `parse_native_pdf_text` reads `blocks` and is what the fallback is measured
    against, so mangling every mode would measure nothing.
    """
    import ocr.native_text as native_text

    real = native_text._page_text

    def install(mangle):
        def read(page, *args, **kwargs):
            answer = real(page, *args, **kwargs)
            if args and args[0] == "dict":
                answer = copy.deepcopy(answer)
                mangle(answer)
            return answer

        monkeypatch.setattr(native_text, "_page_text", read)

    return install


@pytest.mark.parametrize("shape", sorted(MALFORMED))
def test_a_malformed_line_box_refuses_the_page_and_never_raises(shape, mangled, welded):
    """F8. Each shape is answered with the flattening's own text for the page,
    so the document is not claimed and the ladder's bytes are today's."""
    mangled(MALFORMED[shape])
    _declined(welded)


def test_an_exception_class_the_page_text_guard_does_not_convert_is_a_refusal(
        monkeypatch, welded):
    """`_page_text` converts the classes MuPDF raises TODAY (`RuntimeError` and
    the `FzErrorBase` family). A future binding raising anything else must
    still reach this rung as a refusal — it reads every native-text document in
    the archive, and a crash there takes the whole OCR stage down for that
    document."""
    import ocr.native_text as native_text

    real = native_text._page_text

    def explode(page, *args, **kwargs):
        if args and args[0] == "dict":
            raise ValueError("a future binding raised a class nobody converted")
        return real(page, *args, **kwargs)

    monkeypatch.setattr(native_text, "_page_text", explode)
    _declined(welded)


def test_the_box_guard_admits_the_ordinary_page(welded):
    """The premise of the nine pins above: `_line_box` is not refusing
    everything. Every printed line of the fixture's own page passes it."""
    import ocr.native_text as native_text

    with fitz.open(stream=welded, filetype="pdf") as opened:
        read = native_text._page_text(opened[0], "dict")
    boxes = [native_text._line_box(line)
             for block in read["blocks"] if block.get("type") == 0
             for line in block["lines"]]
    assert boxes and all(box is not None for box in boxes)
    assert native_text._printed_lines(fitz.open(stream=welded, filetype="pdf")[0])

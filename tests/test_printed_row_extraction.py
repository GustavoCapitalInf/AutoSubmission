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
  through to the generic rung and the bytes are exactly today's.
"""
from __future__ import annotations

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
    ("4-1", "Scheduled Transfer", ["ORCHARD SUPPLY QUARTERLY"], "101.00"),
    ("4-2", "Scheduled Transfer",
     ["MERIDIAN LEASING CO MONTHLY", "AGREEMENT 55-42 SERIES B"], "202.00"),
    ("4-3", "Scheduled Transfer", ["ZEPHYR UTILITIES BILL"], "303.00"),
    ("4-4", "Scheduled Transfer",
     ["ATLAS FREIGHT NETWORK ACCT", "99-1 REMITTANCE"], "404.00"),
]

#: What each of those rows PRINTS, read off the fixture rather than off the
#: extractor: the row's own line, in reading order.
WELDED_LINES = [
    "4-1 Scheduled Transfer ORCHARD SUPPLY QUARTERLY 101.00",
    "4-2 Scheduled Transfer MERIDIAN LEASING CO MONTHLY AGREEMENT 55-42 SERIES B 202.00",
    "4-3 Scheduled Transfer ZEPHYR UTILITIES BILL 303.00",
    "4-4 Scheduled Transfer ATLAS FREIGHT NETWORK ACCT 99-1 REMITTANCE 404.00",
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
        "Scheduled Transfer MERIDIAN LEASING CO MONTHLY AGREEMENT 55-42 SERIES B",
        "Scheduled Transfer ZEPHYR UTILITIES BILL",
        "Scheduled Transfer ATLAS FREIGHT NETWORK ACCT 99-1 REMITTANCE",
    ]
    before = published(welded, parse_native_pdf_text)
    assert before != after
    for description in before:
        assert "MERIDIAN" not in description or "ORCHARD" not in description


def test_a_wrapped_detail_never_lands_on_the_row_below_it(welded):
    lines = _lines(parse_native_printed_rows(welded))
    following = next(line for line in lines if line.startswith("4-3"))
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
    """G9. The amount is on the row's FIRST line and the detail below it, so a
    reader's span (date to first figure) cannot hold the detail however the
    lines are cut — re-serialising would change the text for no gain."""
    _declined(_ledger_pdf(WELDED_ROWS, amount_last=False))


def test_a_multi_column_balance_ladder_is_left_alone():
    """G8, and the reason there is no separate multi-column gate: four (date,
    figure) pairs side by side means the row's FIRST money is never its last
    printed cell, so the amount-last gate declines it. Measured rather than
    reasoned about — an explicit `at most one money cell` gate was written
    first and `tools/desccols_mutate.py` proved it changed no answer."""
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
                 "PO BOX 4120 STATION MAIN", "FICTION CITY ZZ 00000",
                 "REMITTANCE ADDRESS", "WIDGET CLEARING CENTRE"):
        page.insert_text((LABEL_X, y), line, fontsize=FONT_SIZE)
        page.insert_text((DETAIL_X + 200.0, y), "SEE REVERSE", fontsize=FONT_SIZE)
        y += ROW_PITCH
    page.insert_textbox(fitz.Rect(DATE_X, 700, 560, 780), FILLER, fontsize=FONT_SIZE)
    _declined(doc.tobytes())


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
        ("4-1", "Scheduled Transfer", ["ORCHARD SUPPLY INVOICE 5-2"], "101.00"),
        ("4-2", "Scheduled Transfer",
         ["MERIDIAN LEASING CO REF 6-3", "AGREEMENT 55-42 SERIES B"], "202.00"),
        ("4-3", "Scheduled Transfer", ["ZEPHYR UTILITIES BILL 7-4"], "303.00"),
    ]
    document = parse_native_printed_rows(_ledger_pdf(rows))
    assert document is not None
    printed = [line for line in _lines(document) if line[:1].isdigit()]
    assert printed == [
        "4-1 Scheduled Transfer ORCHARD SUPPLY INVOICE 5-2 101.00",
        "4-2 Scheduled Transfer MERIDIAN LEASING CO REF 6-3 AGREEMENT 55-42 SERIES B 202.00",
        "4-3 Scheduled Transfer ZEPHYR UTILITIES BILL 7-4 303.00",
    ]


def test_a_row_may_wrap_more_than_once_and_still_be_one_line():
    rows = [
        ("4-1", "Scheduled Transfer", ["ORCHARD SUPPLY QUARTERLY"], "101.00"),
        ("4-2", "Scheduled Transfer",
         ["MERIDIAN LEASING CO MONTHLY", "AGREEMENT 55-42 SERIES B",
          "REMITTANCE ADVICE ENCLOSED"], "202.00"),
        ("4-3", "Scheduled Transfer", ["ZEPHYR UTILITIES BILL"], "303.00"),
    ]
    document = parse_native_printed_rows(_ledger_pdf(rows))
    assert document is not None
    printed = [line for line in _lines(document) if line[:1].isdigit()]
    assert printed[1] == (
        "4-2 Scheduled Transfer MERIDIAN LEASING CO MONTHLY "
        "AGREEMENT 55-42 SERIES B REMITTANCE ADVICE ENCLOSED 202.00")


def test_a_block_straddling_the_ledger_boundary_refuses_the_whole_document():
    """G7. A block with lines inside AND outside a repairable region cannot be
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
                (0, 111.0, 119.0, 23.0, 37.0, "4-1"),
                (0, 111.0, 119.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 111.0, 119.0, 530.0, 569.0, "101.00"),
                (0, 121.0, 129.0, 23.0, 37.0, "4-2"),
                (0, 121.0, 129.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 121.0, 129.0, 530.0, 569.0, "202.00"),
                (0, 131.0, 139.0, 23.0, 37.0, "4-3"),
                (0, 131.0, 139.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 131.0, 139.0, 530.0, 569.0, "303.00"),
                (1, 111.7, 119.7, 149.0, 400.0, "ORCHARD SUPPLY QUARTERLY"),
                (1, 121.7, 129.7, 149.0, 400.0, "MERIDIAN LEASING CO MONTHLY"),
                (1, 131.7, 139.7, 149.0, 400.0, "ZEPHYR UTILITIES BILL"),
            ]
            blocks: dict[int, dict] = {}
            for block, top, bottom, left, right, text in spans:
                blocks.setdefault(block, {"type": 0, "lines": []})["lines"].append(
                    {"bbox": (left, top, right, bottom),
                     "spans": [{"text": text}]})
            return {"blocks": [blocks[key] for key in sorted(blocks)]}

    flattened = "\n".join((
        "WIDGET DEBITS 4-1 Scheduled Transfer 101.00 4-2 Scheduled Transfer "
        "202.00 4-3 Scheduled Transfer 303.00",
        "ORCHARD SUPPLY QUARTERLY MERIDIAN LEASING CO MONTHLY "
        "ZEPHYR UTILITIES BILL",
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
                (0, 111.0, 119.0, 23.0, 37.0, "4-1"),
                (0, 111.0, 119.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 111.0, 119.0, 530.0, 569.0, "101.00"),
                (0, 121.0, 129.0, 23.0, 37.0, "4-2"),
                (0, 121.0, 129.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 121.0, 129.0, 530.0, 569.0, "202.00"),
                (0, 131.0, 139.0, 23.0, 37.0, "4-3"),
                (0, 131.0, 139.0, 65.0, 146.0, "Scheduled Transfer"),
                (0, 131.0, 139.0, 530.0, 569.0, "303.00"),
                (1, 111.7, 119.7, 149.0, 400.0, "ORCHARD SUPPLY QUARTERLY"),
                (1, 121.7, 129.7, 149.0, 400.0, "MERIDIAN LEASING CO MONTHLY"),
                (1, 131.7, 139.7, 149.0, 400.0, "ZEPHYR UTILITIES BILL"),
            ]
            blocks: dict[int, dict] = {}
            for block, top, bottom, left, right, text in spans:
                blocks.setdefault(block, {"type": 0, "lines": []})["lines"].append(
                    {"bbox": (left, top, right, bottom), "spans": [{"text": text}]})
            return {"blocks": [blocks[key] for key in sorted(blocks)]}

    flattened = "\n".join((
        "4-1 Scheduled Transfer 101.00 4-2 Scheduled Transfer 202.00 "
        "4-3 Scheduled Transfer 303.00",
        "ORCHARD SUPPLY QUARTERLY MERIDIAN LEASING CO MONTHLY ZEPHYR UTILITIES BILL",
    ))
    return _Page(), flattened


def test_the_hand_built_page_is_repaired_when_its_tokens_agree():
    """The premise of the pin below: this page IS repairable, so a refusal
    there is the conservation check firing and not the page being declined."""
    import ocr.native_text as native_text

    page, flattened = _one_ledger_page()
    assert native_text._printed_row_page(page, flattened) == "\n".join((
        "4-1 Scheduled Transfer ORCHARD SUPPLY QUARTERLY 101.00",
        "4-2 Scheduled Transfer MERIDIAN LEASING CO MONTHLY 202.00",
        "4-3 Scheduled Transfer ZEPHYR UTILITIES BILL 303.00",
    ))


def test_a_token_the_flattening_saw_and_the_boxes_did_not_refuses_the_page():
    """G8. The rung re-serialises what `get_text("dict")` reports and hands the
    result to readers who were given what `get_text("blocks")` reported. The
    two are different extractions of the same page and are not contractually
    identical — a ligature, a soft hyphen or a future MuPDF could separate
    them. Conservation is checked on the emitted text, so any such divergence
    is a refusal rather than a silently altered document."""
    import ocr.native_text as native_text

    page, flattened = _one_ledger_page()
    assert native_text._printed_row_page(page, flattened + " STATEMENT") is None
    assert native_text._printed_row_page(
        page, flattened.replace("ZEPHYR UTILITIES BILL", "ZEPHYR UTILITIES")) is None


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

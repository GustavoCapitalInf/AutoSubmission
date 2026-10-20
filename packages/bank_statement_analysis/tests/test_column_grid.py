"""The page-derived column grid (GEOM-1).

Every fixture is a printed shape reduced to the smallest page that still
exercises it. The subject throughout is the thing this module exists for: a
fact that lives ONLY in a cell's horizontal position, and the ways a page can
fail to say it clearly enough to be read.

Coordinates are laid out by helpers rather than written as literals, so a test
says "the amount is in the Debits column" instead of "the amount is at 186".
That is not cosmetics: the defect this module replaces was a reader that knew
the number and not the reason.
"""
from __future__ import annotations

import re

from ocr.column_grid import GridWord, find_columns, read_rows

DATE = re.compile(r"\d{2}-\d{2}")
MONEY = re.compile(r"-?[\d,]+\.\d{2}")
LABELS = ("date", "credits", "debits", "balance", "description")


class Page:
    """A page laid out the way a statement is: columns at x, rows at a pitch."""

    def __init__(self, *, height: float = 9.0, pitch: float = 12.8, scale: float = 1.0):
        self.height = height * scale
        self.pitch = pitch * scale
        self.scale = scale
        self.words: list[GridWord] = []
        self.columns: dict[str, float] = {}

    def _place(self, text: str, *, right: float, y: float) -> GridWord:
        width = len(text) * self.height * 0.5
        word = GridWord(text, right - width, y, right, y + self.height)
        self.words.append(word)
        return word

    def header(self, y: float, columns: dict[str, float]) -> "Page":
        """The printed column header. `columns` maps label -> its RIGHT edge."""
        self.columns = {name: right * self.scale for name, right in columns.items()}
        for name, right in self.columns.items():
            self._place(name.capitalize(), right=right, y=y * self.scale)
        return self

    def row(self, y: float, cells: dict[str, str], *, offsets: dict[str, float] | None = None,
            free: str = "", free_dy: float = 0.0) -> "Page":
        """One printed row. `offsets` shifts a named column's own baseline."""
        offsets = offsets or {}
        base = y * self.scale
        for name, text in cells.items():
            self._place(text, right=self.columns[name],
                        y=base + offsets.get(name, 0.0) * self.scale)
        if free:
            left = self.columns["description"]
            x = left + self.height
            for token in free.split():
                width = len(token) * self.height * 0.5
                self.words.append(GridWord(token, x, base + free_dy * self.scale,
                                           x + width, base + free_dy * self.scale + self.height))
                x += width + self.height * 0.4
        return self


def grid(page: Page, **kwargs):
    columns = find_columns(page.words, LABELS)
    assert columns, "the header this page prints was not found"
    return read_rows(
        page.words, columns[0], page=1, anchor="date",
        anchor_pattern=DATE, cell_pattern=MONEY,
        cell_columns=("credits", "debits", "balance"),
        free_text="description", **kwargs,
    )


def statement(scale: float = 1.0) -> Page:
    page = Page(scale=scale)
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "credits": "1,000.00", "balance": "1,120.00"},
             free="POS CR ONE")
    page.row(133, {"date": "03-05", "debits": "20.00", "balance": "1,100.00"},
             free="POS DB TWO")
    return page


# --------------------------------------------------------------- the header

def test_columns_come_from_the_page_not_from_constants():
    columns = find_columns(statement().words, LABELS)
    assert len(columns) == 1
    assert columns[0].right_edge("credits") == 140
    assert columns[0].right_edge("debits") == 211


def test_a_page_that_prints_no_header_has_no_grid():
    """The honest answer, and the reason this module cannot guess a band."""
    page = Page()
    page.columns = {"date": 66, "credits": 140, "debits": 211,
                    "balance": 284, "description": 340}
    page.row(120, {"date": "03-04", "credits": "1,000.00", "balance": "1,120.00"})
    assert find_columns(page.words, LABELS) == []


def demanding(scale: float) -> Page:
    """A page whose reading DEPENDS on every tolerance being page-derived.

    The plain `statement()` fixture does not: its cells sit exactly on their
    column edges and exactly on their anchor's baseline, so a hardcoded
    tolerance reads it correctly at any scale and a test built on it pins
    nothing. Every offset here is a fraction of the page's own type size, the
    way a real document's are:

    * the balance typeset slightly ABOVE its row's date (exercises the lift),
    * a money column carrying its own lower baseline (exercises row identity),
    * cells whose right edges miss their column's by a little (exercises snap),
    * a description wrapping one pitch down (exercises the last-row floor).
    """
    page = Page(scale=scale)
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.columns["credits"] -= 2.2 * scale      # cells miss the label's edge
    page.row(120, {"date": "03-04"})
    page.row(120, {"credits": "1,000.00"}, offsets={"credits": 5.6})
    page.row(120, {"balance": "1,120.00"}, offsets={"balance": -0.8})
    page.row(120, {}, free="POS CR ONE")
    page.row(133, {"date": "03-05", "debits": "20.00"})
    page.row(133, {"balance": "1,100.00"}, offsets={"balance": -0.8})
    page.row(133, {}, free="POS DB TWO")
    page.row(133, {}, free="REF 000000000565054", free_dy=12.8)
    return page


def test_the_same_layout_at_any_scale_reads_identically():
    """`_wells_rows` reads its bands from constants (395, 452, 520) and a page
    set at another size drops every cell outside them. Every tolerance here is
    a fraction of the page's own type size, so the scale cancels.

    The range is what gives the test teeth. A hardcoded tolerance can be
    tuned to pass at one scale; it cannot pass at a tenth and ten times it,
    because the offsets it has to straddle scale with the type and it does
    not. Verified by construction: replacing the derived lift with a constant
    breaks the 10x case, and replacing the derived snap breaks it too.
    """
    reference = None
    for scale in (0.1, 0.5, 1.0, 2.5, 10.0):
        rows, refusals = grid(demanding(scale))
        assert refusals == [], f"scale {scale}: {refusals}"
        shape = [(r.anchor, r.cells, r.free_text) for r in rows]
        if reference is None:
            reference = shape
        assert shape == reference, f"scale {scale} read differently from 0.1"
    assert reference == [
        ("03-04", {"credits": ("1,000.00",), "debits": (), "balance": ("1,120.00",)},
         "POS CR ONE"),
        ("03-05", {"credits": (), "debits": ("20.00",), "balance": ("1,100.00",)},
         "POS DB TWO REF 000000000565054"),
    ]


# ----------------------------------------------------------------- the rows

def test_each_amount_is_read_in_the_column_the_page_printed_it_in():
    rows, refusals = grid(statement())
    assert refusals == []
    assert [(r.anchor, r.one("credits"), r.one("debits"), r.one("balance")) for r in rows] == [
        ("03-04", "1,000.00", None, "1,120.00"),
        ("03-05", None, "20.00", "1,100.00"),
    ]


def test_a_money_column_with_its_own_baseline_still_belongs_to_its_row():
    """Woodforest sets the money columns about 0.6 line below the rest of the
    row. A generic line grouper splits that into two lines; the row is the
    anchor and everything under it, so it does not."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "credits": "1,000.00", "balance": "1,120.00"},
             offsets={"credits": 5.6})
    page.row(133, {"date": "03-05", "credits": "500.00", "balance": "1,620.00"},
             offsets={"credits": 5.9})
    rows, refusals = grid(page)
    assert refusals == []
    assert [(r.anchor, r.one("credits")) for r in rows] == [
        ("03-04", "1,000.00"), ("03-05", "500.00"),
    ]


def test_a_cell_typeset_a_hair_above_the_anchor_stays_on_its_own_row():
    """The balance sits a fraction of a point ABOVE the date on the same
    printed row. Reading rows as "at or below the anchor" puts every balance
    one row late — measured, and the totals still looked plausible."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "credits": "1,000.00"}, offsets={})
    page.row(120, {"balance": "1,120.00"}, offsets={"balance": -0.8})
    page.row(133, {"date": "03-05", "credits": "500.00"})
    page.row(133, {"balance": "1,620.00"}, offsets={"balance": -0.8})
    rows, _ = grid(page)
    assert [(r.anchor, r.one("balance")) for r in rows] == [
        ("03-04", "1,120.00"), ("03-05", "1,620.00"),
    ]


def test_a_wrapped_description_keeps_its_reading_order():
    """Sorting a row's words by x alone interleaves a wrapped line into the
    one above it. The row is read line by line, then left to right."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "20.00", "balance": "1,100.00"},
             free="ATM WDL MAIN STREET")
    page.row(120, {}, free="000000000565054", free_dy=9.6)
    rows, _ = grid(page)
    assert rows[0].free_text == "ATM WDL MAIN STREET 000000000565054"


def test_the_last_row_does_not_annex_a_block_printed_below_the_grid():
    """Five archive documents print a fee table under the grid whose right
    column lands inside Description. Without a floor the final posting eats
    it."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "20.00", "balance": "1,100.00"},
             free="POS DB ONE")
    page.row(120, {}, free="Total for This Year", free_dy=40.0)
    rows, _ = grid(page)
    assert rows[0].free_text == "POS DB ONE"


def test_a_continuation_one_pitch_below_the_last_row_is_kept():
    """The counterpart of the test above, and the reason the floor is not a
    fixed depth: a wrapped line arrives exactly one pitch down."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "20.00", "balance": "1,100.00"},
             free="POS DB ONE")
    page.row(120, {}, free="000000000565054", free_dy=12.8)
    rows, _ = grid(page)
    assert rows[0].free_text == "POS DB ONE 000000000565054"


def test_rows_below_the_printed_stop_are_not_read():
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "20.00", "balance": "1,100.00"})
    page.row(160, {"date": "03-09", "debits": "99.00", "balance": "1,001.00"})
    rows, _ = grid(page, stop_y=150.0)
    assert [r.anchor for r in rows] == ["03-04"]


# ------------------------------------------------------------- the refusals

def test_a_cell_in_no_printed_column_is_refused_not_guessed():
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "balance": "1,100.00"})
    page._place("77.00", right=175.0, y=120.0)     # between Credits and Debits
    rows, refusals = grid(page)
    assert [r.reason for r in refusals] == ["cell_in_no_column"]
    assert "77.00" in refusals[0].detail


def test_two_cells_in_one_column_are_refused():
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "credits": "1,000.00", "balance": "1,120.00"})
    page.row(120, {"credits": "2,000.00"}, offsets={"credits": 4.0})
    rows, refusals = grid(page)
    assert [r.reason for r in refusals] == ["column_collision"]
    assert rows[0].one("credits") is None   # ambiguous reads as absent, never as one


def test_a_row_the_page_never_anchored_yields_nothing():
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"credits": "1,000.00", "balance": "1,120.00"})
    rows, refusals = grid(page)
    assert rows == [] and refusals == []


def test_a_cell_split_across_two_word_boxes_is_refused_not_truncated():
    """The blocker this module's contract said it could not have.

    A page can emit one printed number as two word boxes. The fragment does
    not match the money pattern, and skipping it silently books the remainder
    as the whole cell: on a real archive document `1,` vanished and `682.89`
    was published, losing exactly a thousand dollars with no refusal, no flag
    and a ledger that still looked like a ledger.

    A right-edge test cannot see the fragment — it sits well left of the
    column's edge — so membership here is the column's REGION, bounded by
    whatever the header prints before it.
    """
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "682.89", "balance": "1,100.00"})
    page._place("1,", right=185.7, y=120.0)
    rows, refusals = grid(page)
    assert [r.reason for r in refusals] == ["cell_split_across_word_boxes"]
    assert "'1,'" in refusals[0].detail and "debits" in refusals[0].detail


def test_a_word_left_of_the_money_columns_is_not_a_split_cell():
    """The refusal is scoped to the money columns' own regions. Prose in the
    anchor column's gutter is not a fragment of anything."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 211,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "20.00", "balance": "1,100.00"})
    page._place("CHQ", right=100.0, y=120.0)
    rows, refusals = grid(page)
    assert refusals == []
    assert rows[0].one("debits") == "20.00"


def test_columns_closer_together_than_the_cell_tolerance_refuse_the_grid():
    """Assignment needs the columns to be separated by more than the distance
    a cell is allowed to miss its edge by. Where they are not, no per-cell
    rule can recover, so the grid is refused whole rather than read with a
    tie-break standing in for evidence."""
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 144,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "debits": "20.00", "balance": "1,100.00"})
    rows, refusals = grid(page)
    assert rows == []
    assert [r.reason for r in refusals] == ["columns_not_separated"]
    assert "credits" in refusals[0].detail and "debits" in refusals[0].detail


def test_a_cell_two_columns_both_admit_is_refused_not_awarded_to_the_first():
    """Assignment was an ordered scan that booked a cell against whichever
    column was DECLARED first, which on overlapping spans is not the column it
    was printed in — a Debits cell read as a CREDIT, with zero refusals. The
    page either says which column it is or it does not."""
    page = Page(height=9.0)
    page.header(100, {"date": 66, "credits": 140, "debits": 151,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "balance": "1,100.00"})
    page._place("20.00", right=145.5, y=120.0)   # 5.5 from credits, 5.5 from debits
    rows, refusals = grid(page)
    assert [r.reason for r in refusals] == ["cell_admitted_by_two_columns"]
    assert rows[0].one("credits") is None and rows[0].one("debits") is None


def test_a_cell_is_booked_against_its_nearest_column_not_the_first_that_fits():
    page = Page()
    page.header(100, {"date": 66, "credits": 140, "debits": 154,
                      "balance": 284, "description": 340})
    page.row(120, {"date": "03-04", "balance": "1,100.00"})
    page._place("20.00", right=152.0, y=120.0)   # 12 from credits, 2 from debits
    rows, refusals = grid(page)
    assert refusals == []
    assert rows[0].one("debits") == "20.00" and rows[0].one("credits") is None

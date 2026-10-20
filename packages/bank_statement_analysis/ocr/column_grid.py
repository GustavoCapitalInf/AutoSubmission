"""Read a printed column grid from the page's own header.

The defect this exists to close
-------------------------------
A statement grid prints each posting in a named column, and the column is
often the ONLY place a fact is written. Woodforest prints
``Date Credits Debits Balance Description`` and puts one bare magnitude under
either ``Credits`` or ``Debits``; nothing else in the row says which. Flatten
the page to a line of text and that fact is gone — not hard to read, *gone*.
The same shape recurs on every two-money-column layout in the archive.

The lesson this module is built from
------------------------------------
``_wells_rows`` in :mod:`ocr.native_text` already reads columns by position,
but it reads them from **constants** (``395``, ``452``, ``520``), and the
Track A log named that as the defect rather than the fix: "geometry read as
constants rather than as the page's own column positions". A statement set at
another scale drops every cell outside every band, silently.

So the rule here is: **a column exists only where the document printed its
name.** Bands come from the header's own word boxes. A page that does not
print the header has no grid, and this module says so instead of guessing.

What it will not do
-------------------
It never decides what a column *means* and never repairs a row. A cell that
lands in no column, a row that carries two cells in one column, an anchor
with no row — each is returned as a :class:`GridRefusal`. The caller fails
closed on them. Inventing a value from position is exactly the failure this
module is supposed to prevent, so it has no code path that can.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median

__all__ = [
    "GridWord",
    "GridColumns",
    "GridRow",
    "GridRefusal",
    "page_words",
    "find_columns",
    "read_rows",
]


#: Characters a printed money cell is made of. A token built only from these
#: that is NOT a whole cell is a FRAGMENT of one — the shape a page takes when
#: it splits a single printed number across two word boxes.
#:
#: Deliberately admits a token with no digit in it (a lone `-`, `(`, `$`).
#: Narrowing it to "must contain a digit" would read better and would lose the
#: case that matters most: a cell split as `1,682.89` + `-` would book the
#: magnitude and drop the sign, silently, which is the exact class this
#: constant exists to prevent. The cost is that a layout printing a bare dash
#: for an empty money cell will refuse until someone teaches this module about
#: it. That is the fail-closed direction, and it is a decision rather than an
#: oversight: measured over the archive it costs nothing today (one refusal in
#: 3,615 documents, and it is a real split cell).
_FRAGMENT_RE = re.compile(r"[\d.,()$−+-]+")


@dataclass(frozen=True)
class GridWord:
    """One word as printed, box in PDF points, origin top-left.

    Deliberately local. ``ocr/`` is the intake layer and does not import
    ``analysis/`` (``analysis.structurer.geometry`` states that separation in
    its own docstring); duplicating five floats is the cheaper side of that
    boundary.
    """

    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


@dataclass(frozen=True)
class GridColumns:
    """The printed header: each label with the box the page drew it in.

    ``y`` is the header's baseline; rows below it belong to this grid.
    """

    y: float
    labels: dict[str, GridWord]

    def right_edge(self, label: str) -> float:
        return self.labels[label].x1

    def left_edge(self, label: str) -> float:
        return self.labels[label].x0


@dataclass(frozen=True)
class GridRow:
    """One printed row: the anchor cell, and each column's cells in x order."""

    page: int
    anchor: str
    y: float
    cells: dict[str, tuple[str, ...]]
    free_text: str

    def one(self, label: str) -> str | None:
        """The single cell printed in this column, or None if the column is
        empty. Raises nothing: two cells is a refusal the caller has already
        been handed, not an exception."""
        found = self.cells.get(label) or ()
        return found[0] if len(found) == 1 else None


@dataclass(frozen=True)
class GridRefusal:
    """A place the page did not present an unambiguous grid."""

    page: int
    reason: str
    detail: str


def page_words(page) -> list[GridWord]:
    """Every non-blank word on a PyMuPDF page. Never raises."""
    try:
        raw = page.get_text("words")
    except Exception:
        return []
    return [
        GridWord(str(item[4]), float(item[0]), float(item[1]), float(item[2]), float(item[3]))
        for item in raw
        if str(item[4]).strip()
    ]


def _baseline_groups(words: list[GridWord], tolerance: float) -> list[list[GridWord]]:
    """Words sharing a baseline, top to bottom, each left to right."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w.mid_y, w.x0))
    groups: list[list[GridWord]] = [[ordered[0]]]
    for word in ordered[1:]:
        if abs(word.mid_y - groups[-1][-1].mid_y) <= tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])
    for group in groups:
        group.sort(key=lambda w: w.x0)
    return groups


def find_columns(words: list[GridWord], labels: tuple[str, ...]) -> list[GridColumns]:
    """Every printed row that names ALL of ``labels``, top to bottom.

    Matching is case-insensitive on whole words. A grid that re-opens with its
    header on each continuation page yields one entry per page, which is what
    lets a column shift between pages without the reader noticing too late.

    The baseline tolerance is the page's own median type height, not a
    constant — a header set in 6pt and one set in 11pt are the same header.
    """
    if not words:
        return []
    wanted = {label.lower() for label in labels}
    tolerance = max(0.5, median(word.height for word in words) * 0.3)
    found: list[GridColumns] = []
    for group in _baseline_groups(words, tolerance):
        picked: dict[str, GridWord] = {}
        for word in group:
            key = word.text.strip().lower()
            if key in wanted and key not in picked:
                picked[key] = word
        if len(picked) == len(wanted):
            found.append(GridColumns(max(w.y1 for w in picked.values()), picked))
    return found


def _last_row_floor(words, anchor, anchor_ids, pitch: float, grid_height: float) -> float:
    """Where the grid's LAST row stops.

    Every other row is bounded by the anchor beneath it. The last one on a
    page has none, so without a floor it annexes whatever the bank printed
    below the grid — on five archive documents a trailing fee table whose
    right-hand column sits inside the Description column, which then lands in
    the final posting's text.

    The floor is not a fixed depth. A description that wraps prints its
    continuation exactly one row pitch below, and cutting at one pitch drops
    it (measured: a reference number, `000000000565054`, lost from a
    Woodforest row whose text wrapped). So the row extends downward for as
    long as printed lines keep arriving AT the grid's own line spacing, and
    stops at the first gap wider than that. A continuation line follows the
    rhythm; a different block does not.
    """
    step = max(grid_height / 3.0, 0.1)
    reach = pitch * 1.25
    # Group by quantised baseline so jitter within one printed line does not
    # read as a gap, but carry each group's ACTUAL top: the floor is compared
    # against real coordinates, and a rounded one can land below the very word
    # it is meant to exclude.
    groups: dict[int, float] = {}
    for word in words:
        if id(word) in anchor_ids or word.mid_y <= anchor.mid_y:
            continue
        key = round(word.mid_y / step)
        groups[key] = min(groups.get(key, word.mid_y), word.mid_y)
    floor = anchor.mid_y
    for _key, top in sorted(groups.items()):
        if top - floor > reach:
            return top
        floor = top
    return float("inf")


def read_rows(
    words: list[GridWord],
    columns: GridColumns,
    *,
    page: int,
    anchor: str,
    anchor_pattern: re.Pattern[str],
    cell_pattern: re.Pattern[str],
    cell_columns: tuple[str, ...],
    free_text: str,
    stop_y: float | None = None,
) -> tuple[list[GridRow], list[GridRefusal]]:
    """Rows of one printed grid, each cell in the column the page printed it in.

    ``anchor`` names the column whose cell opens a row (a Date column, in
    practice). ``cell_columns`` are the columns read by position;
    ``free_text`` is the column whose words are kept as prose.

    Two properties of real statements shape the row rule, and both were
    measured on the archive rather than assumed:

    * **A column may carry its own baseline.** Woodforest sets the money
      columns roughly 0.6 line below the rest of the row, which is enough to
      split the row in two under a generic line grouper. So a row is not "a
      visual line"; it is an anchor cell plus every cell between that anchor
      and the next one.
    * **The anchor is not always the topmost cell of its row.** The balance
      cell sits a fraction of a point ABOVE the date on the same printed row,
      so the row's upper edge is the anchor's baseline less a tolerance.

    Both tolerances derive from the grid's own type size and row pitch. The
    grid's, specifically — a page median would be dragged down by the small
    print in the footer, and was: at a page-median tolerance the balance cell
    fell to the row above and every balance in the document read one row late,
    while the totals still looked plausible.
    """
    refusals: list[GridRefusal] = []
    below = [w for w in words if w.mid_y > columns.y]
    if stop_y is not None:
        below = [w for w in below if w.mid_y < stop_y]
    if not below:
        return [], refusals

    anchor_left = columns.left_edge(anchor)
    anchor_slack = max(1.0, median(w.height for w in below))
    anchors = sorted(
        (w for w in below
         if anchor_pattern.fullmatch(w.text) and abs(w.x0 - anchor_left) <= anchor_slack),
        key=lambda w: w.mid_y,
    )
    if not anchors:
        return [], refusals

    grid_height = median(w.height for w in anchors)
    gaps = [b.mid_y - a.mid_y for a, b in zip(anchors, anchors[1:])
            if b.mid_y - a.mid_y > grid_height * 0.5]
    pitch = median(gaps) if gaps else grid_height * 1.4
    # Above-the-anchor slack: enough for a cell typeset a hair high on the same
    # row, never enough to reach the row above (a quarter of the row pitch).
    lift = min(grid_height * 0.5, pitch * 0.25)

    buckets: list[dict] = [
        {"anchor": w, "cells": {name: [] for name in cell_columns}, "free": []}
        for w in anchors
    ]
    anchor_ids = {id(w) for w in anchors}
    last_floor = _last_row_floor(below, anchors[-1], anchor_ids, pitch, grid_height)
    free_left = columns.left_edge(free_text)
    edges = {name: columns.right_edge(name) for name in cell_columns}
    # A cell belongs to a column when its RIGHT edge matches the column's:
    # money is set right-aligned, so the left edge moves with the digit count
    # and the right edge does not.
    snap = grid_height * 0.8

    # Columns must be far enough apart that "which one is this in" has an
    # answer. Two edges closer than the snap distance admit the same cell, and
    # no per-cell rule can recover from that — so the grid is refused whole
    # rather than read with a tie-break standing in for evidence.
    ordered = sorted(cell_columns, key=lambda name: edges[name])
    for left, right in zip(ordered, ordered[1:]):
        if edges[right] - edges[left] < snap:
            refusals.append(GridRefusal(
                page, "columns_not_separated",
                f"printed columns {left!r} and {right!r} are "
                f"{edges[right] - edges[left]:.1f}pt apart, closer than the {snap:.1f}pt "
                f"cell tolerance — no cell between them can be attributed",
            ))
            return [], refusals

    # Each money column's cell region runs from whatever column the header
    # prints before it to its own right edge. Needed because a cell SPLIT
    # across two word boxes leaves a fragment well left of the right edge,
    # where a right-edge test cannot see it.
    label_edges = sorted(word.x1 for word in columns.labels.values())
    region_left = {}
    for name in ordered:
        prior = [x for x in label_edges if x < edges[name] - 0.5]
        region_left[name] = max(prior) if prior else float("-inf")

    for word in below:
        if id(word) in anchor_ids:
            continue
        index = None
        for position, bucket in enumerate(buckets):
            if word.mid_y >= bucket["anchor"].mid_y - lift:
                index = position
            else:
                break
        if index is None or (index == len(buckets) - 1 and word.mid_y >= last_floor):
            continue
        bucket = buckets[index]
        if word.x0 >= free_left - grid_height * 0.5:
            bucket["free"].append(word)
            continue

        if cell_pattern.fullmatch(word.text):
            # Nearest edge, not the first one that happens to fit: an ordered
            # scan books a cell against whichever column is declared first,
            # which on overlapping spans is not the column it was printed in.
            admitting = [name for name in ordered if abs(word.x1 - edges[name]) <= snap]
            if len(admitting) > 1:
                refusals.append(GridRefusal(
                    page, "cell_admitted_by_two_columns",
                    f"{word.text!r} right edge {word.x1:.1f} is within {snap:.1f}pt of "
                    f"{admitting} — the page does not say which",
                ))
            elif admitting:
                bucket["cells"][admitting[0]].append(word)
            else:
                refusals.append(GridRefusal(
                    page, "cell_in_no_column",
                    f"{word.text!r} right edge {word.x1:.1f} matches no printed column",
                ))
            continue

        # Not a whole cell. If it is money-SHAPED and standing inside a money
        # column, the page has split one printed cell across two word boxes
        # (`1,` + `682.89`), and skipping it silently books 682.89 as the
        # amount and loses a thousand dollars without a word. Nothing inside a
        # money column is ever dropped in silence.
        if not _FRAGMENT_RE.fullmatch(word.text):
            continue
        for name in ordered:
            if word.x0 >= region_left[name] - 0.5 and word.x1 <= edges[name] + snap:
                refusals.append(GridRefusal(
                    page, "cell_split_across_word_boxes",
                    f"{word.text!r} at x[{word.x0:.1f}, {word.x1:.1f}] stands inside the "
                    f"{name!r} column but is not a whole cell",
                ))
                break

    rows: list[GridRow] = []
    for bucket in buckets:
        cells = {
            name: tuple(w.text for w in sorted(found, key=lambda w: w.x0))
            for name, found in bucket["cells"].items()
        }
        for name, found in cells.items():
            if len(found) > 1:
                refusals.append(GridRefusal(
                    page, "column_collision",
                    f"row {bucket['anchor'].text!r} prints {len(found)} cells in {name!r}: {list(found)}",
                ))
        # Reading order, not x order: a description that wraps puts a second
        # printed line under the first, and sorting the row's words by x alone
        # interleaves the two into nonsense. Baselines are quantised to a
        # third of the type height so that the small vertical jitter within
        # one printed line does not reorder it.
        step = max(grid_height / 3.0, 0.1)
        rows.append(GridRow(
            page=page,
            anchor=bucket["anchor"].text,
            y=bucket["anchor"].mid_y,
            cells=cells,
            free_text=" ".join(
                w.text for w in sorted(bucket["free"], key=lambda w: (round(w.mid_y / step), w.x0))
            ),
        ))
    return rows, refusals

"""cpdecl_mutants.py — the table itself, held apart from the harness that runs it.

Split out of `tools/cpdecl_mutation_table.py` at the CP-DECLINES review closure
for one practical reason: every row is an EXACT excerpt of production source,
newlines and quoting included, and a table of those is the one file in this card
that must never be edited through a shell heredoc — a heredoc turned this table's
``\\n`` escapes into real newlines once, and the file stopped parsing. Kept as
data in its own module, it is written and read with a file tool and the harness
imports it.

`Mutant.expect` is the harness's; the fields are documented on the dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass

ENCLOSURES = "analysis/core_processor_enclosures.py"
PARTITION = "analysis/category_partition.py"
T_ENCLOSURES = "tests/test_core_processor_enclosures.py"
T_PARTITION = "tests/test_category_partition.py"


@dataclass(frozen=True)
class Mutant:
    """One row of the table: the gate, the edit, and what must happen."""

    id: str
    gate: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    #: The test that MUST fail. A row whose killer survives is a gate this
    #: branch added without a test, and the run fails.
    killer: str


MUTANTS: tuple[Mutant, ...] = (
    # --- core_processor_enclosures._without_non_opening_dates --------------
    Mutant(
        "M1", "the rule itself: a date that opens no row is read as one",
        ENCLOSURES,
        "    pairs = _non_opening_dates(run)\n    if not pairs:\n        return run",
        "    pairs = []\n    if not pairs:\n        return run",
        (T_ENCLOSURES,),
        "test_a_date_with_another_date_before_the_next_amount_opens_no_row",
    ),
    Mutant(
        "M2", "the bound: a run that STOPS mid-row must still be refused",
        ENCLOSURES,
        "    for index, found in enumerate(dates[:-1]):\n"
        "        stop = dates[index + 1].start()",
        "    for index, found in enumerate(dates):\n"
        "        stop = (dates[index + 1].start() if index + 1 < len(dates)\n"
        "                else len(run))",
        (T_ENCLOSURES,),
        "test_a_run_that_ends_on_a_date_closing_no_cell_is_still_declined",
    ),
    Mutant(
        "M3", "WHICH token is blanked: the one that closes no cell, never the "
              "one that opens the row",
        ENCLOSURES,
        "    for found, _opener in pairs:\n"
        "        blanked.append(run[cursor:found.start(1)])",
        "    for _closes_no_cell, found in pairs:\n"
        "        blanked.append(run[cursor:found.start(1)])",
        (T_ENCLOSURES,),
        "test_a_note_emitted_before_the_posting_date_leaves_the_posting_day_standing",
    ),
    Mutant(
        "M4", "the test itself: a date that DOES close a cell must be left alone",
        ENCLOSURES,
        "        if _LEDGER_FIGURE_RE.search(run[found.end():stop]) is None:\n"
        "            pairs.append((found, dates[index + 1]))",
        "        if _LEDGER_FIGURE_RE.search(run[found.end():stop]) is not None:\n"
        "            pairs.append((found, dates[index + 1]))",
        (T_ENCLOSURES,),
        "test_a_complete_statement_publishes_every_printed_figure",
    ),
    Mutant(
        "M5", "blanked, not removed: the run keeps every other character",
        ENCLOSURES,
        "        blanked.append(\" \" * len(found.group(1)))\n"
        "        cursor = found.end(1)",
        "        cursor = found.end(1)",
        (T_ENCLOSURES,),
        "test_a_date_with_another_date_before_the_next_amount_opens_no_row",
    ),
    # --- the different-day requirement (CP-DECLINES review BLOCK-1) --------
    Mutant(
        "M8", "a blanked pair naming two DIFFERENT days REQUIRES the printed "
              "grid: without one the published day came from the layer's "
              "emission order and no count or total can see it",
        ENCLOSURES,
        "    if from_a_different_day and not printed_grid:\n        return None\n",
        "",
        (T_ENCLOSURES,),
        "test_a_note_emitted_after_the_posting_date_is_refused_without_the_grid",
    ),
    Mutant(
        "M9", "the DIRECTION of that comparison: the DIFFERENT-day pair owes a "
              "grid, not the same-day one",
        ENCLOSURES,
        "    return any(_printed_day(found.group(1)) != _printed_day(opener.group(1))",
        "    return any(_printed_day(found.group(1)) == _printed_day(opener.group(1))",
        (T_ENCLOSURES,),
        "test_a_same_day_pair_needs_no_grid_because_the_choice_cannot_move_a_posting",
    ),
    # --- category_partition: the per-day evidence rule ---------------------
    Mutant(
        "M6", "the ADB doctrine's decision is not the reader's: a document "
              "printing no per-day evidence must still publish",
        PARTITION,
        "    if unified and not _walks_to_the_printed_ending(rows, summary):\n"
        "        return None\n",
        "    if unified and not _walks_to_the_printed_ending(rows, summary):\n"
        "        return None\n"
        "    if grid is None and not unified:\n"
        "        return None\n",
        (T_PARTITION,),
        "test_a_collected_grids_cells_are_never_published_on_the_sectioned_issue",
    ),
    Mutant(
        "M7", "the collected grid's CELLS are still never read",
        PARTITION,
        "    if _LEDGER_GRID_HEADING in sections:\n"
        "        grid = _grid(sections[_LEDGER_GRID_HEADING], summary=summary)",
        "    if _LEDGER_GRID_HEADING in sections or _COLLECTED_GRID_HEADING in sections:\n"
        "        grid = _grid(sections.get(_LEDGER_GRID_HEADING)\n"
        "                     or sections[_COLLECTED_GRID_HEADING], summary=summary)",
        (T_PARTITION,),
        "test_a_collected_grid_cell_is_never_published_as_a_daily_balance",
    ),
)

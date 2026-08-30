"""The mutant table for WH-ROW-CAPTURE — one decision per row.

Every `old` below is an EXACT excerpt of the production source and every `new`
is the same excerpt with one decision broken in the direction that would
publish something wrong. The table lives in its own module because that makes
the "written and read with a file tool, never through a shell heredoc" rule
enforceable by looking: a heredoc has twice turned an escape in a table like
this one into a control byte, and a mutant table with a 0x08 in it silently
never applies.

The harness (`tools/rowcap_mutation_table.py`) refuses to run unless each `old`
occurs exactly ONCE in its file, so a mutant can never apply somewhere else.
"""
from __future__ import annotations

from typing import NamedTuple


class Mutant(NamedTuple):
    ident: str
    target: str
    rule: str
    what: str
    old: str
    new: str
    suite: tuple[str, ...]


SCOTIA = "analysis/scotia.py"
SCOTIA_TESTS = ("tests/test_scotia_layouts.py",)
WELLS = "analysis/wells.py"
WELLS_TESTS = ("tests/test_wells_variants.py",)


MUTANTS: tuple[Mutant, ...] = (
    Mutant(
        "S1", SCOTIA, "the postings are ordered by the date the bank printed",
        "the binder's order is taken for the ledger's order, so a sheet "
        "boundary is walked as a step in the running-balance chain and the "
        "last printed row's balance is published as the closing balance",
        '    return sorted(printed, key=lambda row: row["date"])',
        "    return list(printed)",
        SCOTIA_TESTS,
    ),
    Mutant(
        "S2", SCOTIA, "the ordering is STABLE within one printed date",
        "rows sharing a date are re-ordered by a second key, so each row is "
        "paired with a balance it was not printed beside",
        '    return sorted(printed, key=lambda row: row["date"])',
        '    return sorted(printed, key=lambda row: (row["date"], row["balance"]))',
        SCOTIA_TESTS,
    ),
    Mutant(
        "S3", SCOTIA, "the direction walk starts at the printed opening balance",
        "the walk seeds itself from the first posting's own balance, so the "
        "first row of the period can never be read as a fall",
        "    txns: list[Transaction] = []\n    previous = opening",
        "    txns: list[Transaction] = []\n    previous = rows[0][\"balance\"] if rows else opening",
        SCOTIA_TESTS,
    ),
    Mutant(
        "W1", WELLS, "the history's own restatement is not a posting",
        "the `Totals` row's figures, emitted into the last posting's record, "
        "are published as that posting's amount — the statement's whole debit "
        "total as a single debit that never happened",
        "        if _RESTATEMENT_CELL.search(credit) or _RESTATEMENT_CELL.search(debit):",
        "        if False:",
        WELLS_TESTS,
    ),
    Mutant(
        "W2", WELLS, "only the two money COLUMNS are read for the symbol",
        "a currency symbol quoted inside a posting's own description refuses "
        "the row, so an ordinary posting is dropped for its description text",
        "        if _RESTATEMENT_CELL.search(credit) or _RESTATEMENT_CELL.search(debit):",
        "        if (_RESTATEMENT_CELL.search(description)\n"
        "                or _RESTATEMENT_CELL.search(credit)\n"
        "                or _RESTATEMENT_CELL.search(debit)):",
        WELLS_TESTS,
    ),
)

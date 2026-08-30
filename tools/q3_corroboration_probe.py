"""Q3-CORROBORATION-PROBE — READ-ONLY measurement of the seven conditions.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION.**
It changes nothing. It measures one thing and then exists only as the record of
that measurement.

WHY THIS EXISTS
---------------
Gustavo ruled Q3 (2026-08-30, `BATCH9_TRANSITION` §8.8) GRANTED WITH
CORROBORATION: the omission class `printed_pair_coincides_and_no_row_printed`
(L1-C17's vocabulary) admits a sibling section only under all SEVEN conditions
below, the seventh being an independent roll-up witness. The instruction is
literal — *"Do not assume the roll-up witness. Measure it."* — so this probe
decides each condition per section from the OCR-v4 artifact in the cold cache
and reports PASS / FAIL / UNDECIDABLE with the evidence's LOCATION.

    1. the section prints its own opening caption AND figure;
    2. the section prints its own closing caption AND figure;
    3. opening and closing coincide to the cent;
    4. no dated ledger row is printed in that section;
    5. no counts / totals are printed for that section;
    6. no daily-balance table is printed for that section;
    7. the ROLL-UP WITNESS — the document prints an account roll-up /
       enumerating table; its column roles are identifiable under L1-C5; that
       table's row for THIS section is located by the section's own label; and
       the closing figure in that row equals the section's own closing caption
       figure to the cent. Any link missing is a FAIL naming the link. L1-C5 is
       NOT widened to make a witness appear: a table that prints the closing
       under a column whose role is not printed anywhere is a FAIL with that
       reason, which is the case the ruling's wording turns on.

THE POPULATION IS NOT CHOSEN
----------------------------
The design's own instruments emit it. `tools/l1_split_prototype.py::run_document`
is called over `tools/l1_split_prototype.py::_population` exactly as
`tools/l1_design_idle_evidence.py` calls it, and the population is the sections
that instrument classes as trivially idle ON the documents whose every section
closes or is trivially idle (`DocResult.all_close_allowing_idle`) — the six the
design measured in §2.3. No document is named by hand here. A count other than
the design's is a STOP, not a probe result: `--expect-sections` (default 6)
makes that a non-zero exit with the count printed.

NOTHING IS RE-IMPLEMENTED
-------------------------
Every reader is IMPORTED: the section's own opening / closing caption readers
(`_figure`, `_OPEN_FIG`, `_CLOSE_FIG` and their figure-left twins), the roll-up
column-role map and its row reader (`ROLLUP_COLUMN_ROLES`, `_rollup_pair`), the
dated-row, counts and daily-table readers (`DATED_ROW`, `COUNTS_ROW`,
`has_daily_table`) and the structure census's own `structure`. This module adds
one thing only: a LOCATOR that turns an offset into a page index and a line
index, so the evidence can be cited without being quoted.

A PROBE THAT CANNOT FAIL IS NOT A PROBE
---------------------------------------
This measurement's honest answer might be six PASSes, and six PASSes from an
instrument nobody has tried to break are worth nothing. So the probe attacks
its own result on the SAME sections, in memory: the roll-up's closing figure
mis-read by a cent, the roll-up's printed column caption removed, the row not
located by the section's own label, the document printing no roll-up at all,
and one dated row printed in the section. Each mutant names the condition it
must flip and the refusal class it must flip it to, and a mutant that does NOT
kill is reported and makes the exit non-zero.

EXIT CODES
----------
0 — every cell of the 6 x 7 table is decided (PASS and FAIL are both results).
3 — some cell is UNDECIDABLE.
2 — the population is not the size the design measured (a STOP).
4 — a mutant did not kill the cell it names (the instrument is not binding).

PRIVACY
-------
Content sha16s, census group names, condition ids, verdicts, refusal-class
names, caption / column ROLE names, page indices, line indices and counts. No
printed value, name, account number, amount or date is read into the output;
figures are compared in local variables and never emitted.

Usage:

    python -m tools.q3_corroboration_probe \
        --census-dir docs/moneythumb-replacement/census_batch9 \
        --data-dir .claude/recovery/webapp_data_train8_cold \
        [--run <run of record>] [--json <private>.json]
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import load_census  # noqa: E402
from tools.l1_split_prototype import (  # noqa: E402
    _CLOSE_FIG,
    _CLOSE_FIG_LEFT,
    _OPEN_FIG,
    _OPEN_FIG_LEFT,
    ROLLUP_COLUMN_ROLES,
    _figure,
    _money_value,
    _population,
    _rollup_pair,
    run_document,
)
from tools.l1_structure_census import (  # noqa: E402
    COUNTS_ROW,
    DAILY_CAPTION,
    DATED_ROW,
    MONEY,
    PAGE_MARKER,
    _flat,
    _norm,
    has_daily_table,
    structure,
)

#: The split prototype's own name for the class this probe measures.
IDLE = "trivially-idle-opening-equals-closing-and-no-row-printed"

PASS = "PASS"
FAIL = "FAIL"
UNDECIDABLE = "UNDECIDABLE"

#: The seven conditions, in the ruling's order. The id is what the table's
#: columns are keyed by; the text is the ruling's own wording, shortened.
CONDITIONS: tuple[tuple[str, str], ...] = (
    ("C1", "prints its own opening caption AND figure"),
    ("C2", "prints its own closing caption AND figure"),
    ("C3", "opening and closing coincide to the cent"),
    ("C4", "no dated ledger row printed in the section"),
    ("C5", "no counts / totals printed for the section"),
    ("C6", "no daily-balance table printed for the section"),
    ("C7", "the roll-up witness reproduces the section's closing"),
)

#: A cent, the way every comparison in the design expresses it.
CENT = 0.005


# ---------------------------------------------------------------------------
# the locator — the one thing this module adds
# ---------------------------------------------------------------------------


class Locator:
    """(page index, line index) for a line of the NORMALISED document text.

    `tools.l1_structure_census._norm` replaces each page-marker line with an
    empty line and touches nothing else, so line indices are the SAME in the
    raw markdown and in the normalised text this probe searches. The page index
    is therefore the number of page markers at or before that line: 1 on the
    first page, 0 for a line printed before any marker."""

    def __init__(self, markdown: str) -> None:
        self.marker_lines = [
            index for index, line in enumerate(markdown.splitlines())
            if PAGE_MARKER.match(line.strip())
        ]

    def at(self, line: int) -> str:
        page = bisect.bisect_right(self.marker_lines, line)
        return f"page {page}, line {line}"


def _line_of(haystack: str, offset: int) -> int:
    """The 0-based line index of `offset` within `haystack`."""
    return haystack.count("\n", 0, max(0, int(offset)))


def line_locator(locator: Locator, first_line: int):
    """A callable mapping a line index RELATIVE to a section to a location."""
    def locate(relative_line: int) -> str:
        return locator.at(first_line + relative_line)
    return locate


def plain_locator(relative_line: int) -> str:
    """The locator a constructed fixture gets: no pages exist, only lines."""
    return f"line {relative_line}"


# ---------------------------------------------------------------------------
# the seven conditions
# ---------------------------------------------------------------------------


@dataclass
class Cell:
    """One condition, decided, with the evidence's LOCATION and never its text."""
    verdict: str
    reason: str | None = None
    location: str | None = None
    role: str | None = None

    def as_dict(self) -> dict:
        return {"verdict": self.verdict, "reason": self.reason,
                "location": self.location, "role": self.role}


@dataclass
class RollUpWitness:
    """What the DOCUMENT prints that condition 7 asks about.

    Every field is read from the structure census's own `RollUp`; `block` is
    the row's money block, held to be compared in memory and never emitted."""
    printed: bool = False
    caption_class: str | None = None
    header: str | None = None
    block: str | None = None
    row_located: bool = False
    row_location: str | None = None
    caption_location: str | None = None
    #: every OTHER enumerated row's money block, held to ask whether this
    #: witness discriminates between the document's accounts at all
    other_blocks: list[str] = field(default_factory=list)


def decide_section(section_text: str, witness: RollUpWitness,
                   locate=plain_locator,
                   dated_ledger_rows: int | None = None) -> dict[str, Cell]:
    """The seven conditions for ONE section, each PASS / FAIL / UNDECIDABLE.

    Pure: it reads the section's text and the witness, and returns verdicts.
    That is what lets a constructed fixture decide the same cells the archive
    does — the mutation checks of this card's test file are exactly that.

    `dated_ledger_rows` is the split prototype's own count over the section's
    LEDGER region, offered as a cross-check. Where it disagrees with this
    probe's count over the whole section, condition 4 fails closed and says so;
    a corroboration probe that resolved a disagreement in the section's favour
    would be the assumption the ruling forbids."""
    cells: dict[str, Cell] = {}

    own_open = _figure(section_text, _OPEN_FIG, _OPEN_FIG_LEFT)
    own_close = _figure(section_text, _CLOSE_FIG, _CLOSE_FIG_LEFT)

    # ---- 1 / 2: the section's own printed captions and figures -------------
    cells["C1"] = (
        Cell(PASS, location=locate(_line_of(section_text, own_open[1])),
             role="the section's own opening-balance caption")
        if own_open is not None else
        Cell(FAIL, reason="section_prints_no_opening_caption_with_a_figure"))
    cells["C2"] = (
        Cell(PASS, location=locate(_line_of(section_text, own_close[1])),
             role="the section's own closing-balance caption")
        if own_close is not None else
        Cell(FAIL, reason="section_prints_no_closing_caption_with_a_figure"))

    # ---- 3: the two coincide ----------------------------------------------
    if own_open is None or own_close is None:
        missing = "opening" if own_open is None else "closing"
        cells["C3"] = Cell(FAIL, reason=f"no_printed_pair_the_{missing}_is_not_printed")
    elif abs(own_open[0] - own_close[0]) <= CENT:
        cells["C3"] = Cell(
            PASS, location=locate(_line_of(section_text, own_close[1])),
            role="the section's own opening and closing captions")
    else:
        cells["C3"] = Cell(
            FAIL, reason="printed_opening_and_closing_differ",
            location=locate(_line_of(section_text, own_close[1])),
            role="the section's own opening and closing captions")

    # ---- 4: no dated ledger row -------------------------------------------
    dated = list(DATED_ROW.finditer(section_text))
    if dated:
        cells["C4"] = Cell(
            FAIL, reason=f"dated_row_printed_in_the_section_count_{len(dated)}",
            location=locate(_line_of(section_text, dated[0].start())),
            role="a dated row (a printed date and a money token on one line)")
    elif dated_ledger_rows:
        cells["C4"] = Cell(
            FAIL,
            reason=("the_design_instrument_counts_a_dated_ledger_row_this_probe_"
                    f"does_not_count_{dated_ledger_rows}"),
            role="the split prototype's own ledger-region count")
    else:
        cells["C4"] = Cell(PASS, role="no dated row anywhere in the section")

    # ---- 5: no counts / totals --------------------------------------------
    flat = _flat(section_text)
    counts = COUNTS_ROW.search(flat)
    cells["C5"] = (
        Cell(FAIL, reason="the_section_prints_its_own_counts_or_totals",
             location=locate(_line_of(flat, counts.start())),
             role="a stated counts / totals row")
        if counts is not None else
        Cell(PASS, role="no counts or totals row in the section"))

    # ---- 6: no daily-balance table ----------------------------------------
    if has_daily_table(section_text):
        caption = DAILY_CAPTION.search(section_text)
        cells["C6"] = Cell(
            FAIL, reason="the_section_prints_its_own_daily_balance_table",
            location=locate(_line_of(section_text, caption.start() if caption else 0)),
            role="a daily-balance caption with its rows")
    else:
        cells["C6"] = Cell(PASS, role="no daily-balance table in the section")

    # ---- 7: the roll-up witness -------------------------------------------
    cells["C7"] = _decide_witness(witness, own_close[0] if own_close else None)
    return cells


def _decide_witness(witness: RollUpWitness, own_closing: float | None) -> Cell:
    """Condition 7, link by link, each missing link named.

    L1-C5 is applied as written and is never widened: the roles of a roll-up's
    columns are established by the COLUMN CAPTION the table prints, from the
    closed vocabulary `ROLLUP_COLUMN_ROLES`. A table with no such caption states
    nowhere which figure is the closing, so a figure of that row COINCIDING
    with the section's closing is a coincidence and not a witness — it is
    reported as its own refusal class, because that is precisely the case the
    ruling's `where the document prints ... with identifiable column roles`
    clause turns on."""
    if not witness.printed:
        return Cell(FAIL, reason="no_rollup_or_enumerating_table_printed_by_the_document")

    roles = ROLLUP_COLUMN_ROLES.get(witness.header or "")
    if roles is None:
        coincides = (
            own_closing is not None and witness.block is not None
            and any(abs((_money_value(token) or 0.0) - own_closing) <= CENT
                    for token in MONEY.findall(witness.block)))
        reason = (
            "rollup_prints_the_closing_under_a_column_whose_role_is_not_identifiable"
            if coincides else
            "rollup_column_roles_not_identifiable_no_column_caption_in_L1_C5s_vocabulary")
        return Cell(FAIL, reason=reason, location=witness.caption_location,
                    role=f"roll-up caption class `{witness.caption_class}`, "
                         f"column caption class `{witness.header}`")

    if not witness.row_located or witness.block is None:
        return Cell(FAIL,
                    reason="no_rollup_row_located_by_the_sections_own_label",
                    location=witness.caption_location,
                    role=f"roll-up caption class `{witness.caption_class}`")

    _table_open, table_close = _rollup_pair(witness.block, witness.header)
    if table_close is None:
        return Cell(FAIL,
                    reason="rollup_row_figures_do_not_match_the_printed_column_roles",
                    location=witness.row_location,
                    role=f"column caption class `{witness.header}`")
    if own_closing is None:
        return Cell(FAIL,
                    reason="section_prints_no_closing_for_the_rollup_to_corroborate",
                    location=witness.row_location,
                    role=f"the `close` column of caption class `{witness.header}`")
    if abs(table_close - own_closing) > CENT:
        return Cell(FAIL,
                    reason="rollup_closing_does_not_reproduce_the_sections_closing",
                    location=witness.row_location,
                    role=f"the `close` column of caption class `{witness.header}`")
    return Cell(PASS, location=witness.row_location,
                role=f"the `close` column of caption class `{witness.header}`")


# ---------------------------------------------------------------------------
# the population — the design's instruments, unchanged
# ---------------------------------------------------------------------------


@dataclass
class Target:
    """One measured section of the design's own population."""
    sha16: str
    group: str
    band: str
    section_index: int
    dated_ledger_rows: int
    markdown: str = field(repr=False, default="")
    pages: int = 0


def measured_population(census_dir: Path, data_dir: Path) -> tuple[list[Target], int]:
    """The design's six, derived the way `l1_design_idle_evidence` derives them.

    Returns the targets and the number of DOCUMENTS they sit on. Nothing here
    selects a document: `run_document` is the split prototype's own, the idle
    class is its own refusal string, and `all_close_allowing_idle` is its own
    property — the three facts §2.3's `6 sections on 6 documents` is made of."""
    groups, opportunities, per_sha = load_census(census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(data_dir)

    targets: list[Target] = []
    for band, group, sha16 in _population(groups, opportunities):
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        document = run_document(sha16, group, band, markdown, len(pages))
        if not document.all_close_allowing_idle:
            continue
        for index, section in enumerate(document.sections):
            if section.refusal != IDLE:
                continue
            targets.append(Target(sha16, group, band, index,
                                  section.dated_ledger_rows, markdown, len(pages)))
    return targets, len({t.sha16 for t in targets})


def _rollup_row_line(text: str, rollup, index: int) -> int | None:
    """The line index of one enumerated row, found by its own money block.

    A LOCATOR and not a reader: the block is the structure census's own, and
    what is returned is where it sits, never what it says."""
    row = rollup.rows[index]
    window_end = max(rollup.window_end, rollup.caption_at)
    window = text[rollup.caption_at:window_end]
    line = _line_of(text, rollup.caption_at)
    for raw in window.splitlines():
        if row.block and row.block in _flat(raw):
            return line
        line += 1
    return None


def witness_for(text: str, document, section, locator: Locator) -> RollUpWitness:
    """Condition 7's facts for ONE section, read off the structure census."""
    rollup = document.rollup
    witness = RollUpWitness(
        printed=bool(rollup.caption and rollup.rows),
        caption_class=rollup.caption,
        header=rollup.header,
        caption_location=(locator.at(_line_of(text, rollup.caption_at))
                          if rollup.caption else None),
    )
    # A roll-up ROW is this section's row only where the boundary itself came
    # from the roll-up: that is what makes `identity_index` a row index, and it
    # is what "located by the section's own label" means here — the section was
    # found by searching for the label the roll-up row printed
    # (`_sections_from_rollup`).
    if (witness.printed and document.boundary.startswith("rollup-oracle")
            and 0 <= section.identity_index < len(rollup.rows)):
        witness.row_located = True
        witness.block = rollup.rows[section.identity_index].block
        witness.other_blocks = [row.block for index, row in enumerate(rollup.rows)
                                if index != section.identity_index and row.block]
        line = _rollup_row_line(text, rollup, section.identity_index)
        witness.row_location = (locator.at(line) if line is not None
                                else witness.caption_location)
    return witness


# ---------------------------------------------------------------------------
# supplementary facts — measured, and NOT conditions of the class
# ---------------------------------------------------------------------------


def rollup_movement_columns_zero(witness: RollUpWitness) -> bool | None:
    """Does the roll-up row also print ZERO under its MOVEMENT columns?

    Read through L1-C5's own role map, on the roles `_rollup_pair` discards.
    This is NOT one of the seven conditions and is never used to decide one; it
    is reported because the ruling's stated intent is the OCR-loss shape where
    ledger rows disappear while the two captions survive and happen to net to
    zero, and a table that ALSO prints nothing moved is evidence about exactly
    that. `None` means the table states no movement column."""
    roles = ROLLUP_COLUMN_ROLES.get(witness.header or "")
    if roles is None or witness.block is None:
        return None
    values = [v for v in (_money_value(token) for token in MONEY.findall(witness.block))
              if v is not None]
    if len(values) != len(roles):
        return None
    movements = [value for value, role in zip(values, roles) if role == "movement"]
    if not movements:
        return None
    return all(abs(value) <= CENT for value in movements)


def witness_discriminates(witness: RollUpWitness,
                          own_closing: float | None) -> bool | None:
    """Would ANOTHER row of the same table have corroborated this closing?

    The vacuity question condition 7 cannot answer about itself. Two accounts of
    one member closing at the same figure make the roll-up witness true of a
    section whatever row it was tied to, and a corroboration that cannot tell
    the document's own accounts apart corroborates nothing. Reported, never used
    to decide a cell: which row is this section's row is settled by the printed
    label (L1-C3), and this measures how much work that link is doing.

    `None` where there is no other row, or no readable role map."""
    roles = ROLLUP_COLUMN_ROLES.get(witness.header or "")
    if roles is None or own_closing is None or not witness.other_blocks:
        return None
    for block in witness.other_blocks:
        _opening, closing = _rollup_pair(block, witness.header)
        if closing is not None and abs(closing - own_closing) <= CENT:
            return False
    return True


# ---------------------------------------------------------------------------
# the mutants — each names the cell it must flip and the class it must flip to
# ---------------------------------------------------------------------------


@dataclass
class Mutant:
    name: str
    condition: str
    expected: str
    note: str


MUTANTS: tuple[Mutant, ...] = (
    Mutant("rollup-closing-misread-by-a-cent", "C7",
           "rollup_closing_does_not_reproduce_the_sections_closing",
           "the witness must reproduce the closing, not merely exist"),
    Mutant("rollup-column-caption-removed", "C7",
           "rollup_prints_the_closing_under_a_column_whose_role_is_not_identifiable",
           "L1-C5 is not widened: position is never evidence, and this is the "
           "case the ruling's wording turns on"),
    Mutant("rollup-row-not-located-by-the-sections-label", "C7",
           "no_rollup_row_located_by_the_sections_own_label",
           "a table that enumerates somebody else is not this section's witness"),
    Mutant("document-prints-no-rollup", "C7",
           "no_rollup_or_enumerating_table_printed_by_the_document",
           "the `where the document prints` clause is a link, not a licence"),
    Mutant("one-dated-row-printed-in-the-section", "C4",
           "dated_row_printed_in_the_section_count_1",
           "a section that posted is never idle"),
)


def _misread_last_figure(block: str) -> str | None:
    """The row's LAST figure moved by one cent, in memory and never emitted.

    Returns `None` where the mutation would change the row's figure COUNT,
    because that would kill the cell through the wrong link."""
    matches = list(MONEY.finditer(block))
    if not matches:
        return None
    last = matches[-1]
    value = _money_value(last.group(0))
    if value is None:
        return None
    mutated = f"{block[:last.start()]}{value + 0.01:,.2f}{block[last.end():]}"
    return mutated if len(MONEY.findall(mutated)) == len(matches) else None


def apply_mutant(mutant: Mutant, body: str,
                 witness: RollUpWitness) -> tuple[str, RollUpWitness] | None:
    """The section and its witness under one mutation, or `None` if the mutation
    does not apply to this section (which is itself reported)."""
    facts = RollUpWitness(**vars(witness))
    if mutant.name == "rollup-closing-misread-by-a-cent":
        if facts.block is None:
            return None
        mutated = _misread_last_figure(facts.block)
        if mutated is None:
            return None
        facts.block = mutated
        return body, facts
    if mutant.name == "rollup-column-caption-removed":
        facts.header = None
        return body, facts
    if mutant.name == "rollup-row-not-located-by-the-sections-label":
        facts.row_located = False
        facts.block = None
        return body, facts
    if mutant.name == "document-prints-no-rollup":
        facts.printed = False
        return body, facts
    if mutant.name == "one-dated-row-printed-in-the-section":
        return body + "\n03/14 A CONSTRUCTED ROW 25.00", facts
    return None  # pragma: no cover


@dataclass
class Kill:
    mutant: str
    sha16: str
    killed: bool
    got: str | None


@dataclass
class Record:
    sha16: str
    group: str
    band: str
    section_index: int
    boundary: str
    section_location: str
    cells: dict[str, Cell]
    sections_in_document: int = 0
    rollup_rows: int = 0
    rollup_movement_columns_zero: bool | None = None
    witness_discriminates: bool | None = None
    identities_distinct: bool = False
    kills: list[Kill] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        return all(c.verdict == PASS for c in self.cells.values())

    @property
    def undecided(self) -> list[str]:
        return [k for k, c in self.cells.items() if c.verdict == UNDECIDABLE]

    def as_dict(self) -> dict:
        return {
            "sha16": self.sha16, "census_group": self.group, "band": self.band,
            "section_index": self.section_index, "boundary": self.boundary,
            "section_location": self.section_location,
            "conditions": {k: c.as_dict() for k, c in self.cells.items()},
            "passes_all_seven": self.all_pass,
            "supplementary": {
                "sections_in_document": self.sections_in_document,
                "rollup_rows": self.rollup_rows,
                "rollup_movement_columns_zero": self.rollup_movement_columns_zero,
                "witness_discriminates": self.witness_discriminates,
                "identities_distinct": self.identities_distinct,
            },
            "mutants": [{"mutant": k.mutant, "killed": k.killed, "got": k.got}
                        for k in self.kills],
        }


def measure(targets: list[Target]) -> list[Record]:
    """Decide the 7 conditions for each target section."""
    records: list[Record] = []
    for target in targets:
        document = structure(target.sha16, target.group, target.band,
                             target.markdown, target.pages)
        text = _norm(target.markdown)
        locator = Locator(target.markdown)
        if target.section_index >= len(document.sections):
            records.append(Record(
                target.sha16, target.group, target.band, target.section_index,
                document.boundary, "unresolved",
                {key: Cell(UNDECIDABLE, reason="section_span_not_reproducible")
                 for key, _text in CONDITIONS}))
            continue
        section = document.sections[target.section_index]
        body = text[section.start:section.end]
        first_line = _line_of(text, section.start)
        locate = line_locator(locator, first_line)
        witness = witness_for(text, document, section, locator)
        own_close = _figure(body, _CLOSE_FIG, _CLOSE_FIG_LEFT)
        indices = [s.identity_index for s in document.sections]
        record = Record(
            target.sha16, target.group, target.band, target.section_index,
            document.boundary, locator.at(first_line),
            decide_section(body, witness, locate, target.dated_ledger_rows),
            sections_in_document=len(document.sections),
            rollup_rows=len(document.rollup.rows),
            rollup_movement_columns_zero=rollup_movement_columns_zero(witness),
            witness_discriminates=witness_discriminates(
                witness, own_close[0] if own_close else None),
            identities_distinct=len(set(indices)) == len(indices))
        record.kills = attack(body, witness, locate, target)
        records.append(record)
    return records


def attack(body: str, witness: RollUpWitness, locate,
           target: Target) -> list[Kill]:
    """Every mutant applied to THIS section, and whether it killed its cell."""
    kills: list[Kill] = []
    for mutant in MUTANTS:
        applied = apply_mutant(mutant, body, witness)
        if applied is None:
            kills.append(Kill(mutant.name, target.sha16, False, "not-applicable"))
            continue
        mutant_body, mutant_witness = applied
        cell = decide_section(mutant_body, mutant_witness, locate,
                              target.dated_ledger_rows)[mutant.condition]
        killed = cell.verdict == FAIL and cell.reason == mutant.expected
        kills.append(Kill(mutant.name, target.sha16, killed,
                          None if killed else f"{cell.verdict}/{cell.reason}"))
    return kills


def exit_code(records: list[Record]) -> int:
    """0 when every cell is decided, 3 when any is UNDECIDABLE, 4 when a mutant
    did not kill the cell it names."""
    if any(record.undecided for record in records):
        return 3
    if any(not kill.killed for record in records for kill in record.kills):
        return 4
    return 0


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


_MARK = {PASS: "PASS", FAIL: "FAIL", UNDECIDABLE: "UNDEC"}


def render(records: list[Record], documents: int, run: str | None) -> None:
    print("# Q3-CORROBORATION-PROBE — the seven conditions, measured")
    print()
    print("Every reader below is the design's own, imported: the section's own "
          "opening / closing caption readers, the roll-up column-role map and "
          "row reader (L1-C5), and the dated-row, counts and daily-table "
          "readers. This instrument adds a LOCATOR and nothing else, so the "
          "evidence is cited by page and line and never quoted.")
    print()
    if run:
        print(f"Run of record: `{run}`")
        print()
    print(f"| measure | value |")
    print("|---|---:|")
    print(f"| sections measured | **{len(records)}** |")
    print(f"| documents they sit on | **{documents}** |")
    print(f"| sections passing ALL SEVEN (N) | **{sum(1 for r in records if r.all_pass)}** |")
    print(f"| undecided cells | {sum(len(r.undecided) for r in records)} |")
    print()

    print("| # | document | census group | section | " +
          " | ".join(key for key, _t in CONDITIONS) + " | all seven |")
    print("|---:|---|---|---:|" + "---|" * len(CONDITIONS) + "---|")
    for position, record in enumerate(records, 1):
        marks = " | ".join(_MARK[record.cells[key].verdict] for key, _t in CONDITIONS)
        print(f"| {position} | `{record.sha16}` | `{record.group}` | "
              f"{record.section_index} | {marks} | "
              f"{'**YES**' if record.all_pass else 'no'} |")
    print()

    print("| condition | the ruling's wording |")
    print("|---|---|")
    for key, text in CONDITIONS:
        print(f"| **{key}** | {text} |")
    print()

    print("## Evidence, by location")
    print()
    print("| document | section | condition | verdict | location | role / reason |")
    print("|---|---:|---|---|---|---|")
    for record in records:
        for key, _text in CONDITIONS:
            cell = record.cells[key]
            detail = cell.role or ""
            if cell.reason:
                detail = f"{detail} — `{cell.reason}`" if detail else f"`{cell.reason}`"
            print(f"| `{record.sha16}` | {record.section_index} | {key} | "
                  f"{cell.verdict} | {cell.location or '—'} | {detail or '—'} |")
    print()

    print("## Supplementary, measured and NOT conditions of the class")
    print()
    print("The witness's independence is a LOCATION fact — the roll-up row and "
          "the section's own captions are different printed lines — and the "
          "last two columns are the vacuity questions condition 7 cannot ask "
          "about itself.")
    print()
    print("| document | section opens | roll-up row | sections | roll-up rows | "
          "identities distinct | movement columns all zero | witness discriminates |")
    print("|---|---|---|---:|---:|---|---|---|")
    words = {True: "yes", False: "**no**", None: "not readable"}
    for record in records:
        witness_at = record.cells["C7"].location or "—"
        print(f"| `{record.sha16}` | {record.section_location} | {witness_at} | "
              f"{record.sections_in_document} | {record.rollup_rows} | "
              f"{words[record.identities_distinct]} | "
              f"{words[record.rollup_movement_columns_zero]} | "
              f"{words[record.witness_discriminates]} |")
    print()

    print("## The mutation table — every mutant applied to the SAME sections")
    print()
    print("| mutant | must flip | to | killed / applied | why it is here |")
    print("|---|---|---|---:|---|")
    for mutant in MUTANTS:
        kills = [k for r in records for k in r.kills if k.mutant == mutant.name]
        killed = sum(1 for k in kills if k.killed)
        print(f"| `{mutant.name}` | {mutant.condition} | `{mutant.expected}` | "
              f"**{killed} / {len(kills)}** | {mutant.note} |")
    print()
    survivors = [(r.sha16, k) for r in records for k in r.kills if not k.killed]
    if survivors:
        print("**Mutants that did NOT kill** — the instrument is not binding here:")
        print()
        for sha16, kill in survivors:
            print(f"* `{sha16}` · `{kill.mutant}` → got `{kill.got}`")
        print()

    passing = sum(1 for r in records if r.all_pass)
    print(f"**N = {passing}** — the sections passing all seven conditions.")
    print(f"**S4 demonstrated target = 2 + {passing} = {min(2 + passing, 8)}** "
          f"(maximum 8, never forced).")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q3 corroboration probe (read-only)")
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--run", type=str, default=None,
                        help="the run of record, recorded as provenance only")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--expect-sections", type=int, default=6,
                        help="the design's measured population; a different "
                             "count at this base is a STOP (exit 2)")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    targets, documents = measured_population(args.census_dir, args.data_dir)
    if len(targets) != args.expect_sections:
        print("# Q3-CORROBORATION-PROBE — STOP")
        print()
        print(f"The design's instruments emit {len(targets)} section(s) on "
              f"{documents} document(s) at this base; the card's population is "
              f"{args.expect_sections}. The probe does not choose a population, "
              f"so it stops here and reports the count.")
        return 2

    records = measure(targets)
    render(records, documents, args.run)
    if args.json:
        args.json.write_text(json.dumps({
            "run": args.run,
            "sections": len(records),
            "documents": documents,
            "n_passing_all_seven": sum(1 for r in records if r.all_pass),
            "s4_demonstrated_target": min(
                2 + sum(1 for r in records if r.all_pass), 8),
            "conditions": [{"id": key, "text": text} for key, text in CONDITIONS],
            "mutation_table": [
                {"mutant": m.name, "condition": m.condition, "expected": m.expected,
                 "killed": sum(1 for r in records for k in r.kills
                               if k.mutant == m.name and k.killed),
                 "applied": sum(1 for r in records for k in r.kills
                                if k.mutant == m.name)}
                for m in MUTANTS],
            "records": [record.as_dict() for record in records],
        }, indent=1), encoding="utf-8")
    return exit_code(records)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

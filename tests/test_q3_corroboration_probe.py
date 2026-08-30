"""Q3-CORROBORATION-PROBE — the probe decides, and a mutant flips the cell.

The probe is a MEASUREMENT, so the only thing worth testing about it is that
its cells move when the evidence moves. Every fixture below is CONSTRUCTED:
captions from the structural vocabulary the design already treats as furniture,
and round figures that belong to no statement. Nothing here reads the archive.

The three checks this card owes, and they are the first three:

* a mis-read roll-up figure flips condition 7 to FAIL;
* a section printing one dated row flips condition 4;
* a roll-up whose column roles are NOT identifiable yields FAIL WITH A REASON
  and never PASS — including the case the ruling's wording turns on, where the
  row does carry a figure equal to the section's closing but the table states
  nowhere which column that is.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import l1_split_prototype, l1_structure_census  # noqa: E402
from tools.q3_corroboration_probe import (  # noqa: E402
    CONDITIONS,
    FAIL,
    MUTANTS,
    PASS,
    UNDECIDABLE,
    Cell,
    Kill,
    Locator,
    Record,
    RollUpWitness,
    apply_mutant,
    decide_section,
    exit_code,
    rollup_movement_columns_zero,
    witness_discriminates,
)

#: A section that satisfies conditions 1-6: its own opening caption and figure,
#: its own closing caption and figure, the two coinciding, no dated row, no
#: counts or totals, no daily-balance table.
IDLE_SECTION = "\n".join([
    "REGULAR SHARES Suffix 0002",
    "Beginning Balance 1,250.00",
    "Ending Balance 1,250.00",
])

#: The roll-up row's money block for that account under a printed column
#: caption whose roles ARE in L1-C5's closed vocabulary: (open, close).
GOOD_BLOCK = "1,250.00 1,250.00"
#: The same table, with the closing figure mis-read by a cent.
MISREAD_BLOCK = "1,250.00 1,249.99"


def witness(**overrides) -> RollUpWitness:
    facts = {
        "printed": True,
        "caption_class": "account_summary",
        "header": "type_begin_end",
        "block": GOOD_BLOCK,
        "row_located": True,
        "row_location": "page 1, line 4",
        "caption_location": "page 1, line 3",
    }
    facts.update(overrides)
    return RollUpWitness(**facts)


def verdicts(cells) -> dict[str, str]:
    return {key: cells[key].verdict for key, _text in CONDITIONS}


# ---------------------------------------------------------------------------
# the baseline the mutants are measured against
# ---------------------------------------------------------------------------


def test_a_corroborated_idle_section_passes_all_seven():
    cells = decide_section(IDLE_SECTION, witness())
    assert verdicts(cells) == {key: PASS for key, _text in CONDITIONS}
    assert cells["C7"].role == "the `close` column of caption class `type_begin_end`"
    assert cells["C1"].location == "line 1"
    assert cells["C2"].location == "line 2"


def test_every_condition_reports_a_location_or_a_reason_and_never_a_figure():
    cells = decide_section(IDLE_SECTION, witness())
    for key, _text in CONDITIONS:
        cell = cells[key]
        assert cell.verdict in (PASS, FAIL, UNDECIDABLE)
        assert cell.location or cell.role or cell.reason
        rendered = f"{cell.reason} {cell.location} {cell.role}"
        assert "1,250.00" not in rendered and "1250" not in rendered


# ---------------------------------------------------------------------------
# MUTANT 1 — a mis-read roll-up figure flips condition 7
# ---------------------------------------------------------------------------


def test_a_misread_rollup_figure_flips_condition_7_to_fail():
    cells = decide_section(IDLE_SECTION, witness(block=MISREAD_BLOCK))
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == "rollup_closing_does_not_reproduce_the_sections_closing"
    # and only that condition moves: the section's own evidence is unchanged
    assert {key: cells[key].verdict for key, _t in CONDITIONS if key != "C7"} == {
        "C1": PASS, "C2": PASS, "C3": PASS, "C4": PASS, "C5": PASS, "C6": PASS}


def test_a_rollup_row_whose_figures_do_not_match_the_printed_roles_fails():
    """Three figures under a two-role caption states nothing about either."""
    cells = decide_section(IDLE_SECTION, witness(block="1,250.00 0.00 1,250.00"))
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == "rollup_row_figures_do_not_match_the_printed_column_roles"


# ---------------------------------------------------------------------------
# MUTANT 2 — one dated row flips condition 4
# ---------------------------------------------------------------------------


def test_one_dated_row_flips_condition_4_to_fail():
    posted = IDLE_SECTION + "\n03/14 SHARE DRAFT 25.00"
    cells = decide_section(posted, witness())
    assert cells["C4"].verdict == FAIL
    assert cells["C4"].reason == "dated_row_printed_in_the_section_count_1"
    assert cells["C4"].location == "line 3"
    assert cells["C1"].verdict == PASS and cells["C2"].verdict == PASS


def test_the_design_instruments_own_ledger_count_fails_condition_4_closed():
    """A disagreement is resolved AGAINST the section, never for it."""
    cells = decide_section(IDLE_SECTION, witness(), dated_ledger_rows=1)
    assert cells["C4"].verdict == FAIL
    assert cells["C4"].reason.startswith("the_design_instrument_counts_a_dated_ledger_row")


# ---------------------------------------------------------------------------
# MUTANT 3 — column roles that are not identifiable are a FAIL WITH A REASON
# ---------------------------------------------------------------------------


def test_a_rollup_with_no_column_caption_is_a_fail_with_a_reason():
    cells = decide_section(IDLE_SECTION, witness(header=None, block="0.00 0.00"))
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == (
        "rollup_column_roles_not_identifiable_no_column_caption_in_L1_C5s_vocabulary")


def test_a_column_caption_outside_L1_C5s_vocabulary_is_not_widened():
    """A caption the table prints that the closed vocabulary does not name is
    not evidence, however plausible it reads."""
    cells = decide_section(IDLE_SECTION,
                           witness(header="balance_forward_current", block="0.00 0.00"))
    assert cells["C7"].verdict == FAIL
    assert "not_identifiable" in cells["C7"].reason


def test_a_rollup_printing_the_closing_under_an_unidentifiable_column_is_named():
    """The case the ruling's wording turns on.

    The row carries a figure equal to the section's closing, and the table
    states nowhere which column that is. Position is never evidence (L1-C5), so
    this is a FAIL and it is reported under its OWN class rather than folded
    into the generic one."""
    cells = decide_section(IDLE_SECTION, witness(header=None, block=GOOD_BLOCK))
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == (
        "rollup_prints_the_closing_under_a_column_whose_role_is_not_identifiable")


def test_a_document_printing_no_rollup_at_all_names_that_link():
    cells = decide_section(IDLE_SECTION, witness(printed=False))
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == "no_rollup_or_enumerating_table_printed_by_the_document"


def test_a_row_not_located_by_the_sections_own_label_names_that_link():
    cells = decide_section(IDLE_SECTION, witness(row_located=False, block=None))
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == "no_rollup_row_located_by_the_sections_own_label"


# ---------------------------------------------------------------------------
# the other conditions move too
# ---------------------------------------------------------------------------


def test_a_section_printing_its_own_counts_flips_condition_5():
    cells = decide_section(IDLE_SECTION + "\nTotal Deposits 0.00", witness())
    assert cells["C5"].verdict == FAIL
    assert cells["C5"].reason == "the_section_prints_its_own_counts_or_totals"


def test_a_section_printing_a_daily_balance_table_flips_condition_6():
    daily = IDLE_SECTION + "\n".join([
        "", "Daily Balance", "03/01 1,250.00", "03/02 1,250.00"])
    cells = decide_section(daily, witness())
    assert cells["C6"].verdict == FAIL
    assert cells["C6"].reason == "the_section_prints_its_own_daily_balance_table"


def test_an_opening_and_closing_that_differ_flip_condition_3():
    moved = IDLE_SECTION.replace("Ending Balance 1,250.00", "Ending Balance 1,300.00")
    cells = decide_section(moved, witness(block="1,250.00 1,300.00"))
    assert cells["C3"].verdict == FAIL
    assert cells["C3"].reason == "printed_opening_and_closing_differ"
    # the pair still corroborates, which is why 3 and 7 are separate conditions
    assert cells["C7"].verdict == PASS


def test_a_section_printing_no_closing_caption_fails_2_3_and_7():
    only_open = "REGULAR SHARES Suffix 0002\nBeginning Balance 1,250.00"
    cells = decide_section(only_open, witness())
    assert cells["C2"].verdict == FAIL
    assert cells["C3"].reason == "no_printed_pair_the_closing_is_not_printed"
    assert cells["C7"].verdict == FAIL
    assert cells["C7"].reason == "section_prints_no_closing_for_the_rollup_to_corroborate"


# ---------------------------------------------------------------------------
# the locator, and the exit contract
# ---------------------------------------------------------------------------


def test_the_locator_reports_the_page_the_marker_stream_says():
    markdown = "\n".join([
        "preamble", "--- Page 1 ---", "a", "b",
        "--- Page 2 ---", "c",
    ])
    locator = Locator(markdown)
    # a line printed before any marker belongs to no page
    assert locator.at(0) == "page 0, line 0"
    # the marker line itself opens its page
    assert locator.at(1) == "page 1, line 1"
    assert locator.at(3) == "page 1, line 3"
    assert locator.at(5) == "page 2, line 5"


def test_the_locator_agrees_with_the_normalised_text_line_for_line():
    """`_norm` empties the marker line and touches nothing else, which is the
    whole reason an offset in the normalised text can be cited by raw line."""
    markdown = "--- Page 1 ---\nBeginning Balance 1,250.00\n--- Page 2 ---\nx"
    normalised = l1_structure_census._norm(markdown)
    assert len(normalised.splitlines()) == len(markdown.splitlines())


def _record(*verdict_list: str) -> Record:
    return Record("0" * 16, "g", "CU-SUFFIX", 0, "rollup-oracle:suffix_word", "page 1, line 0",
                  {key: Cell(verdict_list[index])
                   for index, (key, _text) in enumerate(CONDITIONS)})


def test_exit_is_zero_when_every_cell_is_decided_and_three_when_one_is_not():
    decided = _record(PASS, PASS, PASS, FAIL, PASS, PASS, FAIL)
    assert exit_code([decided]) == 0
    assert decided.all_pass is False
    undecided = _record(PASS, PASS, PASS, PASS, PASS, PASS, UNDECIDABLE)
    assert exit_code([decided, undecided]) == 3
    assert undecided.undecided == ["C7"]


def test_a_section_passing_all_seven_is_reported_as_such():
    assert _record(*([PASS] * 7)).all_pass is True


def test_a_mutant_that_did_not_kill_makes_the_exit_non_zero():
    """A probe whose mutants survive is reporting nothing, and says so."""
    survived = _record(*([PASS] * 7))
    survived.kills = [Kill("rollup-closing-misread-by-a-cent", "0" * 16, False, "PASS/None")]
    assert exit_code([survived]) == 4
    survived.kills = [Kill("rollup-closing-misread-by-a-cent", "0" * 16, True, None)]
    assert exit_code([survived]) == 0


# ---------------------------------------------------------------------------
# the mutants themselves, applied to the constructed section
# ---------------------------------------------------------------------------


def test_every_mutant_kills_the_cell_it_names_on_a_corroborated_section():
    """The same attack the probe runs over the archive, run over a fixture: if
    any mutant survives HERE the archive's six PASSes mean nothing."""
    for mutant in MUTANTS:
        applied = apply_mutant(mutant, IDLE_SECTION, witness())
        assert applied is not None, f"{mutant.name} did not apply"
        body, facts = applied
        cell = decide_section(body, facts)[mutant.condition]
        assert cell.verdict == FAIL, f"{mutant.name} left {mutant.condition} at {cell.verdict}"
        assert cell.reason == mutant.expected, f"{mutant.name} gave {cell.reason}"


def test_the_misread_mutant_moves_one_cent_and_not_the_figure_count():
    applied = apply_mutant(MUTANTS[0], IDLE_SECTION, witness())
    assert applied is not None
    _body, facts = applied
    assert facts.block != GOOD_BLOCK
    assert len(l1_structure_census.MONEY.findall(facts.block)) == 2


def test_a_mutant_never_edits_the_witness_it_was_handed():
    original = witness()
    apply_mutant(MUTANTS[1], IDLE_SECTION, original)
    assert original.header == "type_begin_end"


# ---------------------------------------------------------------------------
# the supplementary reading, which decides nothing
# ---------------------------------------------------------------------------


def test_the_movement_columns_are_read_through_the_same_role_map():
    four = witness(header="type_prev_dep_wd_end", block="1,250.00 0.00 0.00 1,250.00")
    assert rollup_movement_columns_zero(four) is True
    moved = witness(header="type_prev_dep_wd_end", block="1,250.00 25.00 0.00 1,275.00")
    assert rollup_movement_columns_zero(moved) is False
    # a caption with no movement column, and a caption outside the vocabulary
    assert rollup_movement_columns_zero(witness()) is None
    assert rollup_movement_columns_zero(witness(header=None)) is None


def test_a_witness_that_cannot_tell_the_documents_accounts_apart_says_so():
    """Two accounts closing at the same figure make the roll-up true of a
    section whichever row it was tied to — reported, and never a verdict."""
    twin = witness(other_blocks=["1,250.00 1,250.00"])
    assert witness_discriminates(twin, 1250.00) is False
    apart = witness(other_blocks=["900.00 900.00"])
    assert witness_discriminates(apart, 1250.00) is True
    assert witness_discriminates(witness(), 1250.00) is None
    assert witness_discriminates(apart, None) is None


def test_the_discrimination_reading_never_moves_a_cell():
    """It is diagnostic: a non-discriminating witness still PASSES condition 7,
    because which row is this section's row is settled by the printed label."""
    twin = witness(other_blocks=["1,250.00 1,250.00"])
    assert decide_section(IDLE_SECTION, twin)["C7"].verdict == PASS
    assert witness_discriminates(twin, 1250.00) is False


# ---------------------------------------------------------------------------
# the readers are the design's, imported and not copied
# ---------------------------------------------------------------------------


def test_the_probe_reuses_the_designs_readers_rather_than_cloning_them():
    from tools import q3_corroboration_probe as probe

    assert probe._figure is l1_split_prototype._figure
    assert probe._rollup_pair is l1_split_prototype._rollup_pair
    assert probe.ROLLUP_COLUMN_ROLES is l1_split_prototype.ROLLUP_COLUMN_ROLES
    assert probe.run_document is l1_split_prototype.run_document
    assert probe.DATED_ROW is l1_structure_census.DATED_ROW
    assert probe.COUNTS_ROW is l1_structure_census.COUNTS_ROW
    assert probe.has_daily_table is l1_structure_census.has_daily_table
    assert probe.structure is l1_structure_census.structure

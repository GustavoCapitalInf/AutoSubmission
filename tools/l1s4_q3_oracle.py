"""l1s4_q3_oracle.py — the production Q3 class against the probe that measured it.

    python -m tools.l1s4_q3_oracle --census-dir <census> --data-dir <cold cache>

Gustavo granted `printed_pair_coincides_and_no_row_printed` WITH CORROBORATION
and ordered the roll-up witness MEASURED before S4 relied on it
(BATCH9_TRANSITION §8.8). `tools/q3_corroboration_probe.py` did that: six
sections, seven conditions, 42 cells decided, N = 6, and five mutants that each
name in advance the cell they must flip and the refusal class they must flip it
to — 30 / 30.

That probe is therefore the ORACLE this card's implementation is judged against,
and this instrument is the judgement. For every one of the six sections it:

* asks the PROBE for its seven cells, from the probe's own readers;
* asks the PRODUCTION class
  `analysis.sibling_omission.prints_pair_coinciding_with_no_row_printed`,
  supplied with the same readings — and, for the seventh condition, with the
  binding the production reader establishes: the roll-up row found by the
  section's own printed LABEL and the row found by its own IDENTITY TOKEN,
  which must be the same row;
* requires them to AGREE — the implementation admits exactly what the probe
  passes and refuses exactly what it fails;

and then repeats the whole comparison under each of the probe's FIVE MUTANTS,
because a class that agrees only where nothing is wrong has been tested against
nothing.

**Where the two are deliberately allowed to differ, and in which direction.**
The probe cannot see a MIS-BINDING (its review's MINOR-3): it inherits "the row
for this section" from the boundary layer that located the section FROM that
row, so the index is correct by construction and a row tied to the wrong
heading would be invisible. The production class therefore asks for BOTH
printed handles and refuses when they disagree, which can only ever be
STRICTER. A section the probe passes and production refuses is reported as a
DISAGREEMENT and makes the exit non-zero — it is not silently allowed — because
on this population the two handles do agree, and a card may not ship a class
that is stricter in a way it has not measured.

Read-only. Prints condition verdicts, refusal-class names, booleans and shas;
never a figure, a label, a date or a description. It calls no analysis path: it
compares one probe's verdicts with one production predicate over the same six
sections.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import q3_corroboration_probe as probe  # noqa: E402
from tools.l1_structure_census import _norm, structure  # noqa: E402


#: The five mutants, translated into the PRODUCTION class's argument space.
#: Each names the same cell the probe's mutant of that name names, and flips it
#: the same way — a cent on the witness's closing, a column caption the paper
#: no longer states, a row the section's own label no longer finds, a document
#: with no enumerating table at all, and one dated row printed in the section.
#: A translation rather than a re-derivation: the probe mutates the TEXT it
#: reads, and production is asked its question in the arguments a reader
#: supplies, so the two meet at the condition rather than at the bytes.
_MUTANT_TRANSLATIONS: dict[str, str] = {
    "rollup-closing-misread-by-a-cent": "closing_off_by_a_cent",
    "rollup-column-caption-removed": "column_roles_not_printed",
    "rollup-row-not-located-by-the-sections-label": "row_not_located_by_label",
    "document-prints-no-rollup": "no_rollup_printed",
    "one-dated-row-printed-in-the-section": "one_dated_row",
}


def _production_inputs(markdown: str, identity: str) -> dict | None:
    """What the PRODUCTION reader reads off this section, as its own arguments.

    The reader's own private helpers, called on the same document: its section
    locator (which runs a section from its OWN heading to its OWN printed
    closing, so the span carries the section's printed label and stops before
    the sibling's), its roll-up reader, its dated-line, counts and
    daily-balance readers, and its two-handle witness binding. Nothing is
    re-derived here — a second opinion about what the section prints would make
    this instrument a comparison of two readers rather than a judgement of one.
    """
    from analysis import member_statement as reader

    caption, rows, _total = reader._read_rollup(markdown)
    sections = reader._locate_sections(markdown)
    if caption is None or not rows or not sections:
        return None
    section = next((s for s in sections if s.identity == identity), None)
    if section is None:
        return None
    witness = reader._witness_for(section, caption, rows)
    return {
        "opening": section.opening,
        "closing": section.closing,
        "dated_row_count": len(reader._DATED_LINE_RE.findall(section.text)),
        "prints_counts_or_totals": bool(reader._COUNTS_ROW_RE.search(section.text)),
        "prints_daily_balance_table": reader._prints_daily_table(section.text),
        "witness": witness,
    }


def _production_admits(inputs: dict, mutant: str | None = None) -> bool:
    """The PRODUCTION class's verdict, optionally under one translated mutant."""
    from analysis.sibling_omission import (
        RollupWitness,
        prints_pair_coinciding_with_no_row_printed,
    )

    witness = inputs["witness"]
    dated = inputs["dated_row_count"]
    fields = dict(
        printed=witness.printed,
        column_roles_printed=witness.column_roles_printed,
        row_located_by_label=witness.row_located_by_label,
        row_located_by_identity=witness.row_located_by_identity,
        locators_agree=witness.locators_agree,
        closing=witness.closing,
    )
    if mutant == "closing_off_by_a_cent" and fields["closing"] is not None:
        fields["closing"] = round(fields["closing"] + 0.01, 2)
    elif mutant == "column_roles_not_printed":
        fields["column_roles_printed"] = False
    elif mutant == "row_not_located_by_label":
        fields["row_located_by_label"] = False
        fields["locators_agree"] = False
    elif mutant == "no_rollup_printed":
        fields = dict(printed=False, column_roles_printed=False,
                      row_located_by_label=False, row_located_by_identity=False,
                      locators_agree=False, closing=None)
    elif mutant == "one_dated_row":
        dated = 1
    return prints_pair_coinciding_with_no_row_printed(
        opening=inputs["opening"],
        closing=inputs["closing"],
        dated_row_count=dated,
        prints_counts_or_totals=inputs["prints_counts_or_totals"],
        prints_daily_balance_table=inputs["prints_daily_balance_table"],
        rollup=RollupWitness(**fields),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--expect-sections", type=int, default=6)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    targets, documents = probe.measured_population(args.census_dir, args.data_dir)
    if len(targets) != args.expect_sections:
        print(f"POPULATION={len(targets)} EXPECTED={args.expect_sections} — STOP")
        return 2

    rows: list[tuple[str, bool, bool, int, int]] = []
    disagreements: list[str] = []
    mutant_rows: dict[str, list[int]] = {}
    for target in targets:
        document = structure(target.sha16, target.group, target.band,
                             target.markdown, target.pages)
        text = _norm(target.markdown)
        section = document.sections[target.section_index]
        body = text[section.start:section.end]
        witness = probe.witness_for(text, document, section,
                                    probe.Locator(target.markdown))
        cells = probe.decide_section(body, witness, probe.plain_locator,
                                     target.dated_ledger_rows)
        probe_pass = all(cell.verdict == probe.PASS for cell in cells.values())

        # The section the PRODUCTION reader locates, matched to the probe's by
        # the identity token the roll-up printed for it — never by position.
        identity = document.rollup.rows[section.identity_index].token.lstrip("*xX#")
        inputs = _production_inputs(target.markdown, identity)
        if inputs is None:
            disagreements.append(
                f"{target.sha16} section {target.section_index}: the production "
                f"reader locates no section for this identity")
            rows.append((target.sha16, probe_pass, False, 0, len(probe.MUTANTS)))
            continue
        admitted = _production_admits(inputs)
        if probe_pass != admitted:
            disagreements.append(
                f"{target.sha16} section {target.section_index}: probe "
                f"{'PASS' if probe_pass else 'FAIL'}, production "
                f"{'admits' if admitted else 'refuses'}")

        agreed = 0
        for mutant in probe.MUTANTS:
            applied = probe.apply_mutant(mutant, body, witness)
            translated = _MUTANT_TRANSLATIONS[mutant.name]
            bucket = mutant_rows.setdefault(mutant.name, [0, 0])
            bucket[1] += 1
            mutant_probe_pass = True
            if applied is not None:
                mutant_body, mutant_witness = applied
                mutant_probe_pass = all(
                    cell.verdict == probe.PASS
                    for cell in probe.decide_section(
                        mutant_body, mutant_witness, probe.plain_locator,
                        target.dated_ledger_rows).values())
            mutant_admitted = _production_admits(inputs, translated)
            if not mutant_probe_pass and not mutant_admitted:
                bucket[0] += 1
                agreed += 1
            else:
                disagreements.append(
                    f"{target.sha16} under `{mutant.name}`: probe "
                    f"{'PASS' if mutant_probe_pass else 'FAIL'}, production "
                    f"{'admits' if mutant_admitted else 'refuses'}")
        rows.append((target.sha16, probe_pass, admitted, agreed,
                     len(probe.MUTANTS)))

    print("# L1-S4 — the Q3 class as code, against the probe that measured it\n")
    print("| section | probe (7 conditions) | production class | mutants both refuse |")
    print("|---|---|---|---:|")
    for sha16, probe_pass, admitted, agreed, total in sorted(rows):
        print(f"| `{sha16}` | {'PASS' if probe_pass else 'FAIL'} | "
              f"{'ADMITS' if admitted else 'REFUSES'} | {agreed} / {total} |")
    print(f"\n* sections: {len(targets)} on {documents} documents")
    print(f"* the probe passes: {sum(1 for _s, p, _a, _g, _t in rows if p)}")
    print(f"* the production class admits: {sum(1 for _s, _p, a, _g, _t in rows if a)}")
    for name, (killed, applied) in sorted(mutant_rows.items()):
        print(f"* mutant `{name}`: both refuse {killed} / {applied}")
    print(f"* DISAGREEMENTS: {len(disagreements)}")
    for line in disagreements:
        print(f"  * {line}")
    total_mutants = sum(applied for _killed, applied in mutant_rows.values())
    total_agreed = sum(killed for killed, _applied in mutant_rows.values())
    print(f"\nSECTIONS={len(targets)} PROBE_PASS="
          f"{sum(1 for _s, p, _a, _g, _t in rows if p)} "
          f"PRODUCTION_ADMITS={sum(1 for _s, _p, a, _g, _t in rows if a)} "
          f"MUTANTS_APPLIED={total_mutants} MUTANTS_BOTH_REFUSE={total_agreed} "
          f"DISAGREEMENTS={len(disagreements)}")
    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Candidate row sets for the hybrid arm: two independent readers, one deterministic gate.

The model's rows (Stage B) are tried first; if the gate refuses, the parser's rows (Stage A) are tried;
then their union, deduplicated on (date, amount, direction, normalised description) with Stage B's
version kept. The first set the gate admits wins and the receipt records WHICH one. Nothing here changes
the gate: every candidate set passes the same arithmetic against the same printed anchors.
"""
from __future__ import annotations

from dataclasses import replace

from vlm.assemble import CandidateRow
from vlm.gate import GateVerdict, gate
from vlm.metadata import AccountMeta
from vlm.textparse import normalise_description

CANDIDATE_ORDER = ("stage_b", "stage_a", "union")


def union_rows(primary: list[CandidateRow], secondary: list[CandidateRow]) -> list[CandidateRow]:
    """Primary rows plus every secondary row whose (date, amount, direction, description) key the primary
    does not already carry; page order is preserved by a stable sort on (page, locator) afterwards."""
    keys = {(r.date, r.amount, r.direction, normalise_description(r.description)) for r in primary}
    extra = [replace(r, source="stage_a+union") for r in secondary
             if (r.date, r.amount, r.direction, normalise_description(r.description)) not in keys]
    merged = list(primary) + extra
    return sorted(merged, key=lambda r: (r.page, r.date or "", r.locator))


def gate_candidates(stage_b_rows: list[CandidateRow], stage_a_rows: list[CandidateRow], meta: AccountMeta,
                    *, extra_reasons: tuple[str, ...] = ()) -> tuple[GateVerdict, str, dict]:
    """Returns (verdict, admitted_candidate | "none", per-candidate reason summary)."""
    sets = {"stage_b": stage_b_rows, "stage_a": stage_a_rows, "union": union_rows(stage_b_rows, stage_a_rows)}
    summary: dict[str, list[str]] = {}
    first: GateVerdict | None = None
    for name in CANDIDATE_ORDER:
        rows = sets[name]
        verdict = gate(rows, meta)
        if extra_reasons and any(r not in verdict.reasons for r in extra_reasons):
            verdict = GateVerdict(False, verdict.reasons + tuple(r for r in extra_reasons if r not in verdict.reasons),
                                  verdict.row_count, (), verdict.computed_ending, verdict.continuity_breaks,
                                  verdict.chain_derived_directions, verdict.checks, verdict.anchored)
        summary[name] = list(verdict.reasons)
        if first is None:
            first = verdict
        if verdict.admitted:
            return verdict, name, summary
    assert first is not None
    return first, "none", summary

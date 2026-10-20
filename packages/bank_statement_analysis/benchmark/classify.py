"""Eight-outcome discrepancy classifier with documented precedence.

MoneyThumb is NEVER automatic ground truth.  Precedence (H-2 prompt):

1. Pre-rulings by Ocean (cited, never re-litigated).
2. An audited expectation exists -> compare BOTH outputs against it
   (BOTH_MATCH_EXPECTED / OUR_SYSTEM_CORRECT / MONEYTHUMB_CORRECT /
   BOTH_INCORRECT).
3. No audited expectation, but the source document provides direct evidence
   (printed summary values, printed balances) -> same four outcomes, citing
   the evidence.
4. Semantic mismatch with documented differing definitions ->
   DIFFERENT_DEFINITION (both values and definitions recorded, no winner).
5. The source document contradicts itself on this field ->
   SOURCE_CONTRADICTION (our fail-closed withholding recorded as the
   defensible behaviour; MoneyThumb's value as commentary, not as correct).
6. Otherwise -> INSUFFICIENT_EVIDENCE (including bare agreement, which is
   not evidence) or UNRESOLVED (material difference queued for Ocean).

A difference never lands in a "correct" bucket without evidence, and our
fail-closed withholding is never scored as "incorrect".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    BOTH_MATCH_EXPECTED = "BOTH_MATCH_EXPECTED"
    OUR_SYSTEM_CORRECT = "OUR_SYSTEM_CORRECT"
    MONEYTHUMB_CORRECT = "MONEYTHUMB_CORRECT"
    BOTH_INCORRECT = "BOTH_INCORRECT"
    DIFFERENT_DEFINITION = "DIFFERENT_DEFINITION"
    SOURCE_CONTRADICTION = "SOURCE_CONTRADICTION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNRESOLVED = "UNRESOLVED"


#: Sentinel distinguishing "no expectation available" from "expected None".
UNSET = object()

#: Money tolerance: audited values are exact to the cent.
MONEY_TOLERANCE = 0.011


@dataclass
class PreRuling:
    """An Ocean pre-ruling applied verbatim (cited, not re-litigated)."""

    outcome: Outcome
    citation: str


#: Ocean pre-rulings from the H-2 prompt, keyed by (set name or "*", field).
PRE_RULINGS: dict[tuple[str, str], PreRuling] = {
    ("*", "mt_total_revenue_row"): PreRuling(
        outcome=Outcome.DIFFERENT_DEFINITION,
        citation=(
            "Ocean pre-ruling (H-2 prompt): MT revenue_statistics row 'Total "
            "Revenue' actually equals net cash flow - DIFFERENT_DEFINITION "
            "with an MT-mislabel note (FIELD_MAPPING section 7: IGNORE, "
            "'mislabeled in MT - a defect we must not copy')."
        ),
    ),
    ("bmo_jan", "ending_balance"): PreRuling(
        outcome=Outcome.SOURCE_CONTRADICTION,
        citation=(
            "Ocean pre-ruling (H-2 prompt): MT bmo_jan headline ending_balance "
            "reports the printed 985,600.00 despite MT's own reconciled=false / "
            "calculated 520,426.00 - SOURCE_CONTRADICTION, with commentary that "
            "MT surfaced an unverified headline while we withhold."
        ),
    ),
}


@dataclass
class ComparisonRow:
    """One compared field with its full classification record."""

    set_name: str
    field: str
    outcome: Outcome
    ours: Any = None
    mt: Any = None
    expected: Any = None
    ours_withheld: bool = False
    evidence: dict[str, Any] | None = None
    definitions: dict[str, str] | None = None
    rationale: str = ""
    for_ocean: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "set": self.set_name,
            "field": self.field,
            "outcome": self.outcome.value,
            "ours": self.ours,
            "mt": self.mt,
            "expected": self.expected,
            "ours_withheld": self.ours_withheld,
            "evidence": self.evidence,
            "definitions": self.definitions,
            "rationale": self.rationale,
            "for_ocean": self.for_ocean,
        }


def values_match(left: Any, right: Any, tolerance: float = MONEY_TOLERANCE) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) is bool(right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return str(left).strip().casefold() == str(right).strip().casefold()


def classify(
    set_name: str,
    field_name: str,
    ours: Any,
    mt: Any,
    *,
    expected: Any = UNSET,
    expected_evidence: dict[str, Any] | None = None,
    source_value: Any = UNSET,
    source_evidence: dict[str, Any] | None = None,
    ours_withheld: bool = False,
    contradiction: str | None = None,
    different_definition: dict[str, str] | None = None,
    material: bool = True,
    note: str = "",
) -> ComparisonRow:
    """Apply the precedence rules and return a fully recorded row."""

    def build(outcome: Outcome, rationale: str, *, evidence: dict | None = None,
              for_ocean: bool = False) -> ComparisonRow:
        text = rationale if not note else f"{rationale} {note}".strip()
        return ComparisonRow(
            set_name=set_name,
            field=field_name,
            outcome=outcome,
            ours=ours,
            mt=mt,
            expected=None if expected is UNSET else expected,
            ours_withheld=ours_withheld,
            evidence=evidence,
            definitions=different_definition,
            rationale=text,
            for_ocean=for_ocean,
        )

    # Rule 1: Ocean pre-rulings.
    ruling = PRE_RULINGS.get((set_name, field_name)) or PRE_RULINGS.get(("*", field_name))
    if ruling is not None:
        return build(ruling.outcome, ruling.citation,
                     evidence={"kind": "ocean_pre_ruling", "citation": ruling.citation})

    # Rule 2: audited expectation.
    if expected is not UNSET and expected is not None:
        ours_ok = not ours_withheld and values_match(ours, expected)
        mt_ok = values_match(mt, expected)
        if ours_ok and mt_ok:
            return build(Outcome.BOTH_MATCH_EXPECTED,
                         "Both outputs match the audited expectation.",
                         evidence=expected_evidence)
        if ours_ok:
            return build(Outcome.OUR_SYSTEM_CORRECT,
                         "Our output matches the audited expectation; MoneyThumb's does not.",
                         evidence=expected_evidence)
        if mt_ok:
            if ours_withheld:
                return build(
                    Outcome.MONEYTHUMB_CORRECT,
                    "MoneyThumb matches the audited expectation. Our value is "
                    "withheld by design (fail-closed), which is defensible but "
                    "means only MT reports the audited number here.",
                    evidence=expected_evidence,
                )
            return build(Outcome.MONEYTHUMB_CORRECT,
                         "MoneyThumb matches the audited expectation; our output does not.",
                         evidence=expected_evidence)
        if ours_withheld:
            if contradiction:
                return build(Outcome.SOURCE_CONTRADICTION, contradiction,
                             evidence=expected_evidence)
            return build(
                Outcome.UNRESOLVED,
                "An audited expectation exists, our value is withheld by design, "
                "and MoneyThumb's value does not match the expectation - queued "
                "for Ocean ruling.",
                evidence=expected_evidence, for_ocean=True,
            )
        return build(Outcome.BOTH_INCORRECT,
                     "Neither output matches the audited expectation.",
                     evidence=expected_evidence)

    # Rule 3: direct source-document evidence.
    if source_value is not UNSET and source_value is not None:
        ours_ok = not ours_withheld and values_match(ours, source_value)
        mt_ok = values_match(mt, source_value)
        evidence = source_evidence or {"kind": "source_document"}
        if ours_ok and mt_ok:
            return build(Outcome.BOTH_MATCH_EXPECTED,
                         "Both outputs match the source-document evidence.",
                         evidence=evidence)
        if ours_ok:
            return build(Outcome.OUR_SYSTEM_CORRECT,
                         "Our output matches the source-document evidence; MoneyThumb's does not.",
                         evidence=evidence)
        if mt_ok:
            return build(Outcome.MONEYTHUMB_CORRECT,
                         "MoneyThumb matches the source-document evidence; our output does not.",
                         evidence=evidence)
        if ours_withheld and contradiction:
            return build(Outcome.SOURCE_CONTRADICTION, contradiction, evidence=evidence)
        return build(Outcome.BOTH_INCORRECT,
                     "Neither output matches the source-document evidence.",
                     evidence=evidence)

    # Rule 4: documented differing definitions (no forced winner).
    if different_definition is not None:
        return build(
            Outcome.DIFFERENT_DEFINITION,
            "Values are computed under documented differing definitions; both "
            "recorded, no winner forced.",
        )

    # Rule 5: the source contradicts itself on this field.
    if contradiction:
        return build(Outcome.SOURCE_CONTRADICTION, contradiction)

    # Rule 6: no evidence.
    if values_match(ours, mt) and not ours_withheld:
        return build(
            Outcome.INSUFFICIENT_EVIDENCE,
            "Values agree, but agreement is not evidence: no audited "
            "expectation and no direct source evidence for this field.",
        )
    if material:
        return build(
            Outcome.UNRESOLVED,
            "Values differ and no audited expectation or source evidence "
            "resolves the difference - queued for Ocean ruling.",
            for_ocean=True,
        )
    return build(
        Outcome.INSUFFICIENT_EVIDENCE,
        "Values differ but the field is immaterial and no evidence exists "
        "either way.",
    )

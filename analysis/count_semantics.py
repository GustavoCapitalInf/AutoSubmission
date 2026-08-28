"""What a bank's PRINTED per-direction count actually denotes.

The platform compares the bank's printed `stated_credit_count` /
`stated_debit_count` against the rows it captured
(`analysis/reconcile.py`), and `analysis/pipeline.py` turns a disagreement
into an integrity flag. That comparison is only a defect detector where the
two sides count **the same set of rows**. This module is the table that
decides where they do.

Why a table rather than an equality test
----------------------------------------
Twenty parser modules fill those two fields from twenty different printed
summaries, and the summaries do not all mean the same thing:

- some banks print ONE figure per direction meaning "every row printed in
  this column" — comparable;
- some print a category subtotal, or a sum over a closed label list, so the
  EXPECTED side is only as complete as the parser's label list;
- some print a figure that excludes a line the parser nonetheless records as
  a row (a service charge, a cheque block), so the two sides differ by scope
  while the money reconciles to the cent.

Comparing the second and third classes by equality does not find defects; it
manufactures them. Measured before any of this was wired up: treating the
four banks in that position as comparable would have moved 14 pinned-PASS
corpus documents into the flagged population, at least 5 of them because the
check was misreading the document
(`docs/moneythumb-replacement/COUNTS_P1_MEASUREMENT.md` §7.2).

The third class is not incomparable — it is UNMAPPED (W3 §COUNTSMAP)
------------------------------------------------------------------
A bank that prints "N Checks/Debits" beside a separate "Service Charges"
line is not printing an unknowable figure. It is printing a KNOWN figure
about a known subset, and the difference between that subset and our rows is
a row class the bank named on the same page. :class:`CountMapping` is the
field that says so: `expected = printed + (1 if the bank BILLED a service
charge else 0)`, declared per parser and per direction, applied in
`analysis/reconcile.py` where the expected side is read.

Three properties make that safe to have at all, and each is asserted:

* it is a LOOKUP, not a callable. The rule is one of :data:`RULES` and the
  evidence is one of :data:`PRINTED_EVIDENCE_FIELDS` — a table a reviewer can
  audit by reading it, not a hook whose behaviour lives somewhere else;
* it reads BANK-PRINTED evidence only. `stated_service_charge` is a figure the
  parser lifted off the printed summary, so the expected side stays
  independent of the rows it is checking. A mapping keyed on what we captured
  would let a parser satisfy the check with its own output, which is the one
  thing this whole check exists to avoid;
* a mapping implies `comparable=True`. An entry that declares an adjustment
  and then refuses to compare is dead code pretending to be a decision.

The alternative was measured, twice, and it is a regression: promoting
`capital_one:debit` or `first_citizens:debit` to a plain COMPARABLE — the
equality test with the mapping BLIND — moves 11 and 9 documents respectively
from `validated/approved` to `review/integrity_flags`, every one of them a
ledger that reconciles to the cent (W3 §COUNTSP3 CP3). The mapping field
exists to make those two promotions safe, and W3 §COUNTSMAP measures the
result: 0 flag movers, 0 outcome movers, 22 of 22 and 35 of 35.

The default is INCOMPARABLE, and that is load-bearing
-----------------------------------------------------
:func:`semantics_for` returns :data:`UNSURVEYED` — `comparable=False` — for
any parser id absent from :data:`SEMANTICS`. A parser that starts populating
a printed count without a table entry therefore emits **nothing**: no flag,
no outcome movement, no silent assumption that its printed figure means what
some other bank's means. Registering a new parser can only make this check
quieter, never louder, and that property is what makes the table's
completeness auditable rather than assumed. It is asserted directly by
`tests/test_count_semantics.py`.

Provenance
----------
Every entry carries the argument that put it there, with its `file:line`
evidence, taken from the phase-1 measurement
(`COUNTS_P1_MEASUREMENT.md` §3) which Gustavo signed off on 2026-08-13.
The three promotions to comparable (chase debit, us_bank both directions,
wilson_muir both directions) were re-proven against the current archive
before they were written here; each entry records the counterfactual that
earned it.

Two banks are deliberately absent: :data:`SECTION_LEVEL_ORACLES` records
printed count evidence this schema has nowhere to put, so the disclosure
travels as data instead of as a paragraph someone must remember.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: The two printed directions. `Transaction.direction` is required and is one
#: of exactly these (`analysis/schema.py:18`) — the column the bank printed
#: the row in, never the sign of the amount.
DIRECTIONS = ("credit", "debit")


def _plus_one_when_billed(value: float | None) -> int:
    """The bank prints a count for one named subset of the direction and bills
    ONE further row of that direction on its own printed line, outside the
    counted subset. Expected = printed + 1 exactly when that line is billed.
    """
    return 1 if value is not None and value > 0 else 0


#: The CLOSED set of adjustments this schema can express, as name -> arithmetic.
#: One entry today, and the list is short on purpose: every rule is a sentence
#: a reviewer has to be able to check against a printed page, so it is added by
#: the cell that measured a bank needing it and never "in case".
#:
#: A dict rather than a tuple beside a hand-written `if`, so a rule cannot be
#: NAMED without being IMPLEMENTED: :data:`RULES` is derived from it, and
#: `CountMapping.adjustment` dispatches through it rather than assuming there
#: is only ever one.
_RULE_ADJUSTMENTS = {"plus_one_when_billed": _plus_one_when_billed}

#: The rule names an entry may use. Derived, never restated.
RULES = tuple(_RULE_ADJUSTMENTS)

#: The ONLY `Statement` fields a mapping may read. Bank-printed evidence, and
#: nothing else: these are figures a parser lifted off the printed summary, so
#: an expected side built from them is still independent of the rows it is
#: being compared against. Adding a field here is adding a way for the
#: expected side to move, so it is a deliberate edit with a test behind it
#: (`tests/test_count_semantics.py`), and a CAPTURED-side field — anything
#: derived from `transactions` — may never appear.
PRINTED_EVIDENCE_FIELDS = ("stated_service_charge",)


def printed_evidence(source: Any, field: str) -> float | None:
    """One printed figure, read from a `Statement` or from a serialized one.

    Both shapes exist and both must get the same answer: `analysis/reconcile.py`
    holds a `Statement`, and the phase-1 count observer in `telemetry/` holds
    the payload mapping the artifact cache stored. An observer that predicted a
    different expected side from the one production emits would be measuring
    the wrong thing.

    Anything that is not a real number reads as absent — fail-closed, because
    an unreadable figure must never be treated as a billed one.
    """
    if field not in PRINTED_EVIDENCE_FIELDS:
        raise ValueError(f"not printed evidence: {field!r}")
    value = source.get(field) if isinstance(source, Mapping) else getattr(source, field, None)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


@dataclass(frozen=True)
class CountMapping:
    """How a printed count that EXCLUDES a named row class becomes comparable.

    Declarative and closed by construction: `rule` names one of :data:`RULES`
    and `printed_field` names one of :data:`PRINTED_EVIDENCE_FIELDS`, both
    checked here rather than at the call site, so an entry that cannot be
    applied cannot be written. There is deliberately no callable — a table
    whose behaviour is a function object somewhere else is not a table a
    reviewer can audit.

    `excluded_row_class` is what the printed count leaves out and our rows
    include, in the bank's own vocabulary. It is the sentence the mapping is
    making, and it is what a future reader checks against a printed page.
    """

    rule: str
    printed_field: str
    excluded_row_class: str

    def __post_init__(self) -> None:
        if self.rule not in RULES:
            raise ValueError(f"unknown count-mapping rule: {self.rule!r}")
        if self.printed_field not in PRINTED_EVIDENCE_FIELDS:
            raise ValueError(f"not printed evidence: {self.printed_field!r}")
        if not self.excluded_row_class:
            raise ValueError("a mapping must name the row class the printed count excludes")

    def adjustment(self, source: Any) -> int:
        """How many rows the printed count leaves out of THIS document.

        For the one rule that exists: +1 when the bank BILLED the excluded row,
        else 0 — `> 0`, not truthiness of a signed number, because
        `stated_service_charge` is documented as a POSITIVE magnitude
        (`analysis/schema.py`) and a negative one would be a refund. A refund
        adds nothing to the DEBIT side under either mapped parser, and they
        differ in how: `first_citizens` emits no row at all
        (`_service_charge_posting` returns None on `charge <= 0`,
        analysis/first_citizens.py:506-507), while `capital_one` reads its
        detail rows and would record the refund in the column the document
        printed it in. Fail-closed: anything that is not a positive number
        adjusts by nothing.

        The threshold is `> 0` and not `>= 0.01`, so a printed sub-cent charge
        would adjust by one. Stated rather than guarded: no bank in the archive
        prints one, and rounding money to the cent is the reader's job
        (`analysis/reconcile.py` holds the tolerances), not this table's.
        """
        return _RULE_ADJUSTMENTS[self.rule](printed_evidence(source, self.printed_field))

    def expected(self, printed_count: int, source: Any) -> int:
        """The printed count, in the scope our rows are counted in."""
        return printed_count + self.adjustment(source)


@dataclass(frozen=True)
class CountSemantics:
    """What one bank's printed count for one direction denotes.

    `comparable` is the whole decision: False means the printed figure counts
    a different set of rows than `direction == <this direction>` does, so an
    equality test between them is not a defect detector — it is a mis-reading
    of the document. `scope` is the short label a rollup groups by; `reason`
    carries the argument and its `file:line` provenance.

    `mapping` is the third state, between the two: the printed figure counts a
    different set of rows AND the difference is a closed, printed-evidence
    adjustment, so the comparison is a defect detector once it is applied. A
    mapping therefore requires `comparable=True` — an entry declaring an
    adjustment nothing will ever apply is a decision that has not been made.
    """

    comparable: bool
    scope: str
    reason: str
    mapping: CountMapping | None = None

    def __post_init__(self) -> None:
        if self.mapping is not None and not self.comparable:
            raise ValueError(
                "a mapped direction must be comparable: the mapping is what makes "
                "the comparison meaningful, so declaring one and then refusing to "
                "compare would leave the adjustment unreachable"
            )


def _whole(printed: str, provenance: str) -> CountSemantics:
    """A bank that prints ONE count meaning 'every row in this direction'."""
    return CountSemantics(
        comparable=True,
        scope="whole_direction",
        reason=f"prints {printed}; one printed figure per direction ({provenance})",
    )


#: Per parser id (`analysis/parser_registry_entries.py`), per direction.
#:
#: Only parsers that ASSIGN a printed count are listed. Everything else falls
#: to :data:`UNSURVEYED`.
SEMANTICS: dict[str, dict[str, CountSemantics]] = {
    # -- comparable: one printed figure per direction ------------------
    "atb": {
        "credit": _whole("a credit count and a debit count in one summary block", "analysis/atb.py:121-122"),
        "debit": _whole("a credit count and a debit count in one summary block", "analysis/atb.py:121-122"),
    },
    # W3 §COUNTSP3. Surveyed on a fresh counterfactual over all 3 archive
    # documents of the family; the entry exists mostly to say out loud that
    # the agreement is a TAUTOLOGY, because a live check that cannot fail is
    # worse undisclosed than disclosed.
    "burke_herbert": {
        "credit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "prints '<N> DEPOSITS/CREDITS <total>' — one printed figure "
                "per direction (analysis/burke_herbert.py:60, assigned :267). "
                "Measured over all 3 archive documents of the family: 3/3 "
                "agree, 0 disagreements, 0 flags raised. DISCLOSURE, in the "
                "idiom of the `community_section` comment below: that 3/3 is "
                "a TAUTOLOGY and carries no information — and it is a tautology "
                "EXACTLY here, which the debit direction cannot say. The "
                "parser's acceptance gate refuses any document whose count of "
                "POSITIVE-amount rows differs from the printed credit figure "
                "(`a > 0`, analysis/burke_herbert.py:200-201), and this parser "
                "sets `direction='credit'` on exactly `amount > 0` (:277), so "
                "the gate's set and this check's set are the same set and a "
                "claimed document agrees by construction. The gate keys on the "
                "SIGN, not on `Transaction.direction`; the two coincide on this "
                "side and DIVERGE on the debit side, where the gate's `a < 0` "
                "omits a $0.00 row this check counts — see that entry's "
                "falsifier. The entry is written "
                "anyway because the alternative — UNSURVEYED — reads as 'not "
                "yet examined' when the truth is 'examined, and structurally "
                "silent'. The independent oracle for this bank is the "
                "row-by-row running-balance chain (:186, module docstring), "
                "which no summary figure can reproduce."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "prints '<N> CHECKS/DEBITS <total>' "
                "(analysis/burke_herbert.py:61, assigned :268); 3/3 agree "
                "over the whole family, and tautologically, for the reason "
                "the credit direction states. TWO THINGS RECORDED so nobody "
                "re-derives them. (1) The printed label is the capital_one / "
                "texas_bank label — 'CHECKS/DEBITS' beside a SEPARATE "
                "'SERVICE CHARGE' line (:62) — and all 3 archive documents "
                "bill a ZERO charge, so the archive cannot distinguish "
                "'whole direction' from 'service-charge excluded' here any "
                "more than COUNTS-P1's 12 all-charged capital_one documents "
                "could distinguish '+1 always' from '+1 iff charged'. What "
                "closes it is not evidence but the gate: the parser also "
                "requires the negative rows to SUM to the printed "
                "'CHECKS/DEBITS' total (:194-195), so a Burke statement whose "
                "billed charge sat outside that figure would go UNCLAIMED "
                "rather than mis-flagged. Fail-closed, not proven-absent. "
                "(2) FALSIFIER: the gate counts `a > 0` / `a < 0` — the SIGN "
                "— while this check counts `Transaction.direction`, and the "
                "parser sets `direction` at `amount > 0` (:277), so a "
                "genuine $0.00 row is counted by NEITHER side of the gate and "
                "as a DEBIT by this check. That is the exact divergence W3 "
                "§JHA-CELL found on `community_section`. No archive document "
                "of this family has one (0 zero-amount rows over 3 "
                "documents); if one appears, this direction manufactures a "
                "flag on a complete ledger and the remedy is the gate, not "
                "this entry."
            ),
        ),
    },
    # W3 §COUNTSMAP. The first of the two service-charge-class promotions the
    # `mapping` field was built for. Held incomparable through COUNTS-P1, P2
    # and P3 not because the evidence was thin — it was 22 of 22 — but because
    # the schema had nowhere to put the adjustment and a plain COMPARABLE
    # installs the equality test the adjustment exists to avoid.
    "capital_one": {
        # "N Deposits/Credits" is a whole-direction figure and cheques ARE
        # inside the printed debit figure by the bank's own label — folded on
        # both sides, which is comparable (cf. bofa, folded on one side only).
        "credit": _whole("'N Deposits/Credits'", "analysis/capital_one.py:81-88, :106"),
        "debit": CountSemantics(
            comparable=True,
            # The scope label is a fact about the DOCUMENT and it has not
            # changed: the printed figure still enumerates a strict subset. What
            # changed is that the table can now say what the subset excludes.
            scope="service_charge_excluded_from_printed_debit_count",
            mapping=CountMapping(
                rule="plus_one_when_billed",
                printed_field="stated_service_charge",
                excluded_row_class=(
                    "the monthly service charge, printed on its own summary "
                    "line with no count of its own"
                ),
            ),
            reason=(
                "PROMOTED to comparable WITH A MAPPING. The printed summary is "
                "a LIST of lines — 'N Checks/Debits ($x)' AND a separate "
                "'Service Charges ($y)' (analysis/capital_one.py:79-113 native, "
                ":337-343 grid). The service charge is its own printed line "
                "with no count, and the parser records it as a debit ROW, so "
                "the printed debit count enumerates a strict subset of the "
                "parser's debit rows. The mapping is the whole of that "
                "difference: `printed + 1 exactly when the bank billed a "
                "charge`. "
                "NOT A TAUTOLOGY, unlike three other comparable entries in "
                "this table: this parser gates on no printed count and no "
                "printed total — it accepts a document whose detail rows exist "
                "and whose balances are readable (:390-391) — so the mapped "
                "comparison is a live check on the whole debit column rather "
                "than a restatement of an acceptance gate. "
                "THE PLATFORM ALREADY MAPS THIS BANK'S DEBIT TOTAL THE SAME "
                "WAY, which is the precedent and was also the correction. "
                "`_debit_coverage_target` (analysis/reconcile.py:63-84) adds "
                "`stated_service_charge` back to the printed debit TOTAL "
                "whenever the summary's own arithmetic says the charge sits "
                "outside it — the money analogue of this mapping, keyed on the "
                "same printed field, shipping since before COUNTS-P1. Measured "
                "on all 12 billed documents: `beginning + credits - printed "
                "debits` misses `ending` by the charge and closes only with it "
                "subtracted separately, so the charge is OUTSIDE the printed "
                "debit total on 12 of 12 and that adjustment fires on every "
                "one. This entry used to assert the opposite — 'its money is "
                "inside the printed debit TOTAL' — inherited from COUNTS-P1 "
                "and never measured; it is corrected here. Count scope and "
                "money scope agree on this bank, and both exclude the charge. "
                "MEASURED FRESH over all 22 archive documents of the family "
                "(18 rows plus 4 recovered by replaying dispatch, the run of "
                "record's `parser_id` column being empty on analysis-cache "
                "hits): 10 agree exactly, every one with a ZERO printed service "
                "charge; 12 disagree by exactly +1, every one with a BILLED "
                "charge; UNDER THE MAPPING 22 of 22 agree, 0 disagree. Credit "
                "direction 22/22. `debit_coverage` is 1.0 and `sum_delta` 0.00 "
                "on all 22 — the rows are right and the scopes differ. "
                "CORRECTION OF A STALE SENTENCE, carried from W3 §COUNTSP3 "
                "CP4.1: this entry used to read '12 of 12 capital_one documents "
                "disagree by EXACTLY +1', true of the 12-document population it "
                "was measured on and misleading about the family, which is 22 "
                "with a 10-document zero-charge control arm. The arm is what "
                "distinguishes '+1 always' from '+1 iff charged', and it is "
                "measured here rather than assumed. "
                "WHAT THE NAIVE PROMOTION COSTS, so nobody re-derives it: "
                "flipping `comparable` without the mapping is the equality test "
                "on a printed subset, and §COUNTSP3 CP3 measured it end to end "
                "— 11 documents `validated/approved` -> `review/integrity_flags` "
                "(the 12th charged document is already withheld), FOUR OF THEM "
                "PINNED corpus documents, with `corpus_gate.py` reporting GREEN "
                "over the move because `validated` and `review` both sit inside "
                "its PASS bucket (§COUNTSP3 CP7). "
                "INDEPENDENCE HOLDS: the adjustment reads "
                "`stated_service_charge`, the magnitude the parser lifted off "
                "the printed summary cell, and nothing derived from a captured "
                "row. "
                "FALSIFIER, two ways, both with the tell stated. (1) A cycle "
                "that posts TWO separately-printed charge rows against ONE "
                "printed 'Service Charges' total is +2 where the mapping adds "
                "1, and this direction flags a complete ledger; the tell is a "
                "captured debit count exceeding `printed + 1` by exactly the "
                "extra charge rows. (2) A REFUNDED cycle. "
                "`stated_service_charge` is published as a MAGNITUDE: the "
                "native reader refuses a summary whose printed cell contradicts "
                "its column (`_magnitude`, :68-77, returns None and the summary "
                "is not read at all), so a refund cannot reach the field there, "
                "but the GRID reader publishes `abs(value)` (:343) and keeps "
                "the sign only for the cycle-date guard (:320-323, :392-394) — "
                "so a refunded cycle read through the grid would map +1 while "
                "the refund is a CREDIT row. The archive contains no such "
                "cycle: on all 12 billed documents every row whose magnitude "
                "equals the printed charge posts as an OUTFLOW, and the other "
                "10 bill zero, so the family has no refund to test the hazard "
                "against. Note what that evidence cannot be: `stated_service_"
                "charge` is a magnitude, so the FIELD THE MAPPING READS cannot "
                "tell a charge from a refund at all, and the bound comes "
                "entirely from the two readers. The remedy if one appears is "
                "the grid reader making the refusal the native reader already "
                "makes, not a table edit. "
                "WHAT THE MAPPING DELIBERATELY DOES NOT HIDE: a billed cycle "
                "whose charge ROW the parser failed to record reads "
                "`captured == printed` against an expected `printed + 1` and "
                "FLAGS. That is the finding, not a false positive — the ledger "
                "really is short a row the bank printed on the same page as the "
                "figure it is being checked against. "
                "AND THE DISCRIMINATOR, because those two cases present the "
                "IDENTICAL observable: a future layout that FOLDED the charge "
                "into the printed `Checks/Debits` count would also read "
                "`captured == printed` on a complete ledger, and this direction "
                "would flag it. What separates the finding from the false "
                "positive is the MONEY scope, which is measured per document "
                "and not assumed: `_debit_coverage_target` "
                "(analysis/reconcile.py:63-84) fires only where "
                "`beginning + credits - printed debits` misses `ending` by the "
                "charge — i.e. only where the charge is OUTSIDE the printed "
                "total — and it fires on 12 of 12 today. A document that flags "
                "here while that adjustment does NOT fire is a folded layout "
                "and this entry is wrong about it; one that flags while it DOES "
                "fire is a ledger missing a row."
            ),
        ),
    },
    "chase": {
        "credit": _whole("'Deposits and Additions  N  $x'", "analysis/chase.py:428 (native), :581 (table label)"),
        "debit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence. The debit figure "
                "is a SUM over a closed label list (_SUMMARY_DEBIT_LABELS, "
                "analysis/chase.py:380-387; summed at :409-418 and :535-543) "
                "rather than a printed whole-direction count, so it is "
                "comparable only as long as the label list is complete for the "
                "layouts we see. It reproduces the captured debit rows on "
                "387 of 387 chase documents that print one — 0 disagreements "
                "in the phase-1 archive measurement (COUNTS_P1_MEASUREMENT.md "
                "§3.3) and 0 again when re-measured against the current "
                "archive before this entry was written. CAVEAT, recorded "
                "because it is the failure mode this entry buys: a label-list "
                "sum is only as complete as its label list, so a NEW Chase "
                "layout printing a debit category the list does not name "
                "under-counts the EXPECTED side quietly rather than failing "
                "loudly, and would surface here as a count mismatch on correct "
                "rows. That is a flag, never a withholding, and the "
                "remediation is the Chase parser card."
            ),
        ),
    },
    "chase_export": {
        "credit": _whole("'Deposits and Additions  N  $x'", "analysis/chase.py:428 (native), :581 (table label)"),
        "debit": CountSemantics(
            comparable=False,
            scope="category_subtotal_sum",
            reason=(
                "same summary reader as `chase` (analysis/chase.py:380-387), "
                "but NOT promoted with it: no chase_export document in the "
                "archive prints a debit count at all (4 of 4 report the "
                "expected side absent), so the counterfactual that earned "
                "chase's promotion does not exist here and there is nothing to "
                "promote on. Kept incomparable deliberately — an unproven "
                "mapping stays unproven."
            ),
        ),
    },
    # W3 §COUNTSP3. The savings product reads its own summary block, not
    # `chase`'s (`SAVINGS SUMMARY`, analysis/chase_savings.py:185), so it is
    # surveyed in its own right rather than inheriting either sibling's entry.
    "chase_savings": {
        "credit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "prints 'Deposits and Additions  N  $x' in the SAVINGS SUMMARY "
                "block; one printed figure per direction "
                "(analysis/chase_savings.py:198-203). Measured over all 10 "
                "archive documents of the family: 10/10 agree, 0 "
                "disagreements. Unlike the debit sibling this is a single "
                "printed label, not a sum, and unlike `burke_herbert:credit` "
                "it is NOT gated — `parse_chase_savings_statement` compares no "
                "count against anything (:317-350), so the agreement is "
                "measured rather than construed. FALSIFIER, and it is a real "
                "one because a savings product is where a second credit "
                "category would appear: if a layout prints a COUNT beside any "
                "credit line other than 'Deposits and Additions' — an interest "
                "or bonus category, say; the parser already reads 'Interest "
                "Paid This Period' for its AMOUNT and no count (:219-222) — "
                "the expected side under-counts and this entry manufactures a "
                "mismatch on correct rows. The tell is a captured credit count "
                "that exceeds the printed one by exactly the rows of the "
                "unnamed category."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence, and on the same "
                "construction as `chase:debit`: the debit figure is a SUM over "
                "a closed label list (_SUMMARY_DEBIT_LABELS, "
                "analysis/chase_savings.py:130-137; summed and assigned at "
                ":207-216) rather than a printed whole-direction count. "
                "Measured over all 10 archive documents of the family: 6 print "
                "a debit count and 6 of 6 agree; the other 4 print none and "
                "report `not_printed`. 0 disagreements. STATE THE DENOMINATOR "
                "HONESTLY: the debit direction rests on 6 comparisons, not 10 "
                "— the family is savings statements, and four of them posted "
                "no debit category at all. That is still a counterfactual, "
                "which is what separates this from `chase_export:debit`, held "
                "incomparable precisely because 4 of 4 print nothing and there "
                "is no counterfactual to promote on. TWO CAVEATS. (1) The "
                "label-list caveat `chase:debit` carries applies unchanged: a "
                "new savings layout printing a debit category the list does "
                "not name under-counts the EXPECTED side and surfaces here as "
                "a mismatch on correct rows — a flag, never a withholding. "
                "(2) `stated_debit_count = debit_count or None` (:216) maps a "
                "genuine ZERO to absent, so a period with no debits reports "
                "`not_printed` rather than `0`; the check can therefore never "
                "raise a false mismatch from a zero, and can never confirm a "
                "true one either. (3) THE FOLDED-CHARGE ARM IS UNEXERCISED, "
                "stated with the same candour as `burke_herbert:debit`: `Fees` "
                "IS one of the summed labels and its count is added to the "
                "expected side (:135, :207-216), so BY CONSTRUCTION this bank "
                "folds its service charge inside the printed debit figure and "
                "cannot be in the capital_one class — but 0 of the 10 archive "
                "documents print a `Fees` row at all "
                "(`stated_service_charge` is unset on every one), so the claim "
                "rests on `_SUMMARY_DEBIT_LABELS` construction and NOT on a "
                "measured control arm. Construction is the stronger of the two "
                "here, because the count and the money come off the same "
                "printed line and the parser cannot take one without the "
                "other; it is still not evidence, and the distinction is the "
                "one COUNTS-P1's 12 all-charged capital_one documents taught. "
                "FALSIFIER: a savings layout printing a debit category the "
                "label list does not name — including a fee line spelled "
                "anything other than `Fees` — under-counts the EXPECTED side; "
                "the tell is a captured debit count exceeding the printed one "
                "by exactly the rows of the unnamed category, and if that "
                "category proves to be a charge printed OUTSIDE the summed "
                "labels this bank joins the capital_one class and the "
                "direction goes back to incomparable."
            ),
        ),
    },
    "farmers_merchants": {
        "credit": _whole("a credit count in the printed account summary", "analysis/farmers_merchants.py:56-57"),
        "debit": _whole("a debit count in the printed account summary", "analysis/farmers_merchants.py:56-57"),
    },
    # W3 §COUNTSP3, on the correction §FI14.3 made to its own §FI10
    # recommendation, then W3 §COUNTSMAP. Both directions are comparable now
    # and they are worth opposite amounts: the credit direction is a TAUTOLOGY
    # the parser's own section gate guarantees, and the debit direction — the
    # capital_one class, comparable only WITH its mapping — is the one check
    # anywhere on the platform that the service-charge recovery fired. A plain
    # COMPARABLE on the debit side, with the mapping blind, was measured and is
    # a REGRESSION of 9 documents; see the entry.
    "first_citizens": {
        "credit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "the expected side is `deposits + other credits` — a two-way "
                "sum of the printed section counts in `Your Account(s) At A "
                "Glance` (analysis/first_citizens.py:610). Measured over all "
                "35 archive documents of the family: 35/35 agree, 0 "
                "disagreements, 0 flags raised. DISCLOSURE, and it is the "
                "whole of what this direction is worth: that 35/35 is a "
                "TAUTOLOGY. `_matches` refuses the document unless each "
                "section's parsed posting count equals the count the bank "
                "printed for it (:526-531, applied :584-589), and both credit "
                "sections publish `direction='credit'` uniformly (:417, :444), "
                "so a claimed document agrees by construction. Written down "
                "rather than left UNSURVEYED for the reason the "
                "`community_section` comment gives: 'examined and "
                "structurally silent' and 'not yet examined' are different "
                "facts and the table is where the difference is recorded. "
                "FALSIFIER: this holds only while every credit-direction row "
                "comes from a gated section. The debit direction already "
                "breaks that pattern — `billed`, the service-charge posting, "
                "is appended OUTSIDE the four gated sections (:594-597, :614) "
                "— so an interest credit recovered the same way would make "
                "this direction disagree by +1 on correct rows."
            ),
        ),
        # W3 §COUNTSMAP. The second service-charge-class promotion, and the one
        # that buys information rather than restating a gate — see the entry.
        "debit": CountSemantics(
            comparable=True,
            scope="service_charge_excluded_from_printed_debit_count",
            mapping=CountMapping(
                rule="plus_one_when_billed",
                printed_field="stated_service_charge",
                excluded_row_class=(
                    "the monthly service charge, billed outside the four "
                    "printed section totals and recovered from its own "
                    "itemisation"
                ),
            ),
            reason=(
                "PROMOTED to comparable WITH A MAPPING, the capital_one class, "
                "and the parser proves it on itself. The expected side is "
                "`checks + other debits` (analysis/first_citizens.py:720) — the "
                "two GATED debit sections — while the published debit rows are "
                "those two sections PLUS `billed`, the monthly service charge, "
                "which the bank prints outside the four section totals and the "
                "parser recovers from its own itemisation (:489-532) and "
                "appends at :701-706, :723. Same money, different scope, and "
                "the mapping is exactly that difference. "
                "MEASURED FRESH over all 35 archive documents of the family "
                "(34 rows plus 1 recovered by replaying dispatch, the run of "
                "record's `parser_id` column being empty on analysis-cache "
                "hits): 26 agree exactly, every one with a ZERO service charge; "
                "9 disagree by exactly +1, every one with a BILLED charge; "
                "UNDER THE MAPPING 35 of 35 agree, 0 disagree. Credit direction "
                "35/35. `sum_delta` is 0.00 on all 35, and the charge is "
                "measurably OUTSIDE the printed section totals on all 9 billed "
                "documents — `beginning + credits - printed debits` closes on "
                "`ending` only with the charge subtracted separately — so "
                "count scope and money scope agree and both exclude it. Every "
                "row whose magnitude equals the printed charge posts as an "
                "OUTFLOW on all 9, so the family carries no refunded cycle. "
                "This reproduces "
                "§FI14.3's 26/9 split on the current archive, and §COUNTSP3 CP3 "
                "measured what promoting it WITHOUT the mapping costs: 9 "
                "documents `validated/approved` -> `review/integrity_flags`, 9 "
                "manufactured flags on ledgers that reconcile to the cent. "
                "THIS DIRECTION IS NOT A TAUTOLOGY, and it is the one place in "
                "this family where that is true. `_matches` gates each of the "
                "four printed sections into agreement (:618-624, applied "
                ":681-687), which is why the CREDIT direction's 35/35 carries "
                "no information — but `billed` is appended OUTSIDE all four "
                "(:701-706), so the mapped comparison tests exactly one thing "
                "nothing else tests: that the charge posting was recovered iff "
                "the bank billed one. It is the platform's only per-document "
                "check on `_service_charge_posting`. "
                "THE CLAUSE §FI14.3 ASKED FOR, AND WHY IT IS NOT IN THE "
                "MAPPING. §FI14.3 proposed `+1 where the billed service charge "
                "was RECOVERED AS A POSTING`, because `_service_charge_posting` "
                "returns nothing when the itemisation cannot be located (:532; "
                "the module docstring names it as the one path that can still "
                "fail reconciliation, :24-28), so a charged document whose "
                "charge was not found is +0. That clause is DELIBERATELY "
                "ABSENT: 'was it recovered as a posting' is a fact about OUR "
                "ROWS, and an expected side that reads the captured side lets "
                "the parser satisfy the check with its own output — the exact "
                "property the phase-1 sign-off's independence rule, and the "
                "observer's forbidden-expected-sources list, exist to protect. "
                "So the mapping "
                "keys on the PRINTED charge and the un-recovered case flags. "
                "That is correct rather than costly: a billed charge the parser "
                "could not locate is a debit row the ledger is missing, and a "
                "second independent witness to it is worth more than silence. "
                "THE ARM IS UNEXERCISED and this sentence is the disclosure "
                "§COUNTSP3 D2 made binding: all 9 charged documents in the "
                "archive were located, so 0 documents exercise the "
                "billed-but-not-recovered path and the claim that flagging it "
                "is right rests on the argument above, not on a measurement. "
                "FALSIFIER: a posting recovered outside the four gated sections "
                "the way `billed` is — a second fee class, or an interest "
                "credit — puts a row on a side the printed counts cannot see, "
                "and this direction then flags a complete ledger; the tell is a "
                "captured debit count exceeding `printed + 1` by exactly the "
                "rows of the unnamed class. The credit sibling's falsifier is "
                "the same shape on the other side."
            ),
        ),
    },
    "first_community": {
        "credit": _whole("a credit count in the printed summary line", "analysis/first_community.py:150-151"),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "prints 'N Debits This Period $X' — one printed figure per "
                "direction (analysis/first_community.py:151). DISCLOSURE, in "
                "the idiom of the bank_of_america entry: the expected side "
                "actually compared here is POST-REPAIR, not the raw printed "
                "read. `repair_first_community_posted_activity` drops the "
                "bank's balance-neutral failed-EFT attempt rows from the "
                "posted activity and, when it does, narrows the printed debit "
                "COUNT and the printed debit TOTAL together "
                "(analysis/first_community.py:209-211, applied at "
                "analysis/pipeline.py:78). The two halves move as a pair or "
                "not at all, and an absent half is never narrowed from the "
                "other. That pairing is what makes this direction comparable: "
                "rewriting the total alone left the count describing a set of "
                "rows the statement no longer reports, which is exactly the "
                "`semantics_difference` D5 adjudicated on the one pinned-PASS "
                "document (`08B2A61B…`), and it is why that document reads "
                "`match` since FIXUPS-1 `acd0b07`. Independence holds: the "
                "repair narrows the expected side from PRINTED "
                "balance-neutrality evidence, never from what we captured, so "
                "nothing derived is read back. If that repair is ever changed "
                "to rewrite one half without the other, this entry stops "
                "being true and must go back to incomparable."
            ),
        ),
    },
    "first_farmers": {
        "credit": _whole("a printed credit count", "analysis/first_farmers.py:152-153"),
        "debit": _whole("a printed debit count", "analysis/first_farmers.py:152-153"),
    },
    "ibc": {
        "credit": _whole("a printed credit count", "analysis/ibc.py:241-242"),
        "debit": _whole("a printed debit count", "analysis/ibc.py:241-242"),
    },
    "linkbank": {
        "credit": _whole("a printed credit count", "analysis/linkbank.py:70-71"),
        "debit": _whole("a printed debit count", "analysis/linkbank.py:70-71"),
    },
    "midflorida": {
        "credit": _whole("a printed credit count", "analysis/midflorida.py:119-120"),
        "debit": _whole("a printed debit count", "analysis/midflorida.py:119-120"),
    },
    "rbc": {
        "credit": _whole("'Total deposits & credits (N)  + $x'", "analysis/rbc.py:298-308 (business; the personal layout prints no counts and assigns none)"),
        "debit": _whole("'Total cheques & debits (N)  - $x'", "analysis/rbc.py:298-308 (business; the personal layout prints no counts and assigns none)"),
    },
    "rbc_french": {
        "credit": _whole("the French twin of 'Total deposits et credits (N)'", "analysis/rbc.py:565-578 — LIVE since W3 RBCCIBC: the business layout prints and assigns both counts (19 docs, all match); the personal product prints none"),
        "debit": _whole("the French twin of 'Total cheques et debits (N)'", "analysis/rbc.py:565-578 — LIVE since W3 RBCCIBC: see credit note"),
    },
    "scotiabank": {
        "credit": _whole("'No. of Credits' in the printed summary grid", "analysis/scotia.py:176-181"),
        "debit": _whole("'No. of Debits' in the printed summary grid", "analysis/scotia.py:176-181"),
    },
    "td_canada": {
        "credit": _whole("'CREDITS  N  $x'", "analysis/td_can.py:449-453"),
        "debit": _whole("'DEBITS  N  $x'", "analysis/td_can.py:454-457"),
    },
    # W3 §COUNTSP3. The one entry in this table whose comparison is neither a
    # tautology nor a restatement: on this layout the printed per-direction
    # counts are the ONLY independent check on which column a row was in.
    "td_canada_french": {
        "credit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "PROMOTED to comparable on measured evidence. The French "
                "layout prints a per-page `CREDITS <n> <total>` footer and the "
                "parser accumulates them (_PAGE_TOTAL_RE, "
                "analysis/td_canada_french.py:92; assigned :401-405) — the "
                "`td_canada_native` idiom, one whole-direction figure per "
                "printed block, summed because a statement can print the "
                "block per page. WHY THIS DIRECTION IS WORTH MORE THAN MOST: "
                "the PDF text layer collapses the RETRAITS and DEPOTS columns "
                "into one token, so which column an amount was printed in does "
                "NOT survive extraction; the parser solves it back out of the "
                "running balance the bank prints at the end of each date group "
                "(`_resolve_directions`, :468, direction assigned :474). The "
                "printed count is therefore an oracle on the solver, read off "
                "the page, and independence is strict — the solver takes the "
                "rows, the groups and the opening balance, and never reads "
                "`stated_credit_count`, which this module writes and nothing "
                "here reads back. MEASURED FRESH over all 13 archive documents "
                "of the family (12 rows plus 1 recovered by replaying "
                "dispatch, the run of record's `parser_id` column being empty "
                "on analysis-cache hits): 9 of 13 agree, 4 of 13 disagree. "
                "All 9 agreeing "
                "are the family's `validated` documents; all 4 disagreeing are "
                "already `withheld/withheld_adb` and already carry "
                "`ledger_sum_mismatch`, so promoting this direction adds two "
                "flags to four withheld documents and moves NO outcome — "
                "measured end to end over the whole archive, 4 flag movers, 0 "
                "outcome movers. Those 4 are not noise: each disagrees "
                "SYMMETRICALLY (credit −n, debit +n for n = 1, 2, 2, 6), which "
                "is the solver putting n rows in the wrong column and is "
                "exactly the defect class this check exists to name. "
                "FALSIFIER: if a French statement is found whose per-page "
                "footers are REPRINTED rather than per-page, the accumulation "
                "doubles the expected side and this entry manufactures a "
                "mismatch on correct rows — the tell is an expected side that "
                "is an exact integer multiple of the captured one. The "
                "`td_canada_native` entry records the same hazard for the "
                "same reason."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "PROMOTED with the credit direction and on the same evidence "
                "and the same argument: the per-page `DEBITS <n> <total>` "
                "footer (analysis/td_canada_french.py:92, assigned :407-408), "
                "accumulated, checked against a column the parser SOLVED "
                "rather than read. 9 of 13 agree, the same 4 withheld "
                "documents disagree, by +1/+2/+2/+6 against their credit "
                "direction's −1/−2/−2/−6. FALSIFIER: the credit direction's, "
                "unchanged — a REPRINTED rather than per-page footer doubles "
                "the expected side, and the tell is an expected side that is "
                "an exact integer multiple of the captured one."
            ),
        ),
    },
    "td_canada_native": {
        # Accumulated across every printed summary line (`(or 0) + n`,
        # analysis/td_can.py:451/456 and :586-598) because a TD statement can
        # print the block more than once. Each line is still a whole-direction
        # figure, so the sum is one; a REPEATED block would double the expected
        # side, which is a defect worth flagging rather than a semantics
        # difference this table should hide.
        "credit": _whole("'CREDITS  N  $x', summed over printed summary lines", "analysis/td_can.py:451, :586-592"),
        "debit": _whole("'DEBITS  N  $x', summed over printed summary lines", "analysis/td_can.py:456, :598"),
    },
    "texas_bank": {
        "credit": _whole("'Deposits ( N ) + $x'", "analysis/texas_bank.py:68, :129"),
        "debit": CountSemantics(
            comparable=False,
            scope="service_charge_excluded_from_printed_debit_count",
            reason=(
                "the same shape as capital_one, and the parser proves it on "
                "itself: the summary prints 'Checks/Debits ( N ) - $x' and a "
                "SEPARATE 'Service Charge - $y' (analysis/texas_bank.py:70-71), "
                "and the parser's own acceptance gate is "
                "`debit_sum == debits + service_charge` (:108, :111-112) — it "
                "requires the service-charge row to be a debit row whose money "
                "is OUTSIDE the printed 'Checks/Debits' figure. The printed "
                "count therefore cannot enumerate it. Measured: the single "
                "texas_bank document disagrees by exactly +1."
            ),
        ),
    },
    "demo_national": {
        "credit": _whole("a printed credit count", "analysis/demo_national.py:50-51"),
        "debit": _whole("a printed debit count", "analysis/demo_national.py:50-51"),
    },
    # `community_section` and `scanned_small_bank` already run a count
    # comparison AS A CLAIM GATE — on mismatch the parser returns None and the
    # document goes unclaimed (analysis/community_section.py (gate),
    # analysis/scanned_small_bank.py:206-207, :368-369, :525-527). A document
    # they claimed has, by construction, matching counts — and for the three
    # `community_section` registrations that is now matching counts UNDER THIS
    # CHECK'S OWN KEY.
    #
    # RECORD OF A CHANGE (W3 §JHA-CELL). Until that cell the gate keyed on
    # `amount > 0` / `amount < 0` — the SIGN — while this check keys on
    # `Transaction.direction`, the column the bank printed the row in. A
    # zero-amount row is on neither side of a sign test and on exactly one side
    # of a column test, so the two could disagree and these parsers were NOT
    # immune to this check. The gate now keys on `direction` as well, for the
    # reason the difference exists: this platform posts genuine `$0.00` rows (a
    # returned ACH), the bank counts them, and a sign-keyed gate therefore
    # rejected documents whose ledgers were complete — three archive documents
    # measurably so. The two keys are now the same key.
    #
    # What that costs is stated plainly: these three parsers are now immune to
    # this check BY CONSTRUCTION, so a `match` here is a tautology and carries
    # no information. It is not a silent one — this paragraph is the
    # disclosure, and the independent evidence for these parsers is the printed
    # per-section `N item(s) totaling $X` trailer, which
    # `_section_oracle_disagrees` checks and which no summary figure can
    # reproduce.
    "mission_valley": {
        "credit": _whole("a printed credit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
        "debit": _whole("a printed debit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
    },
    "dakota_west": {
        "credit": _whole("a printed credit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
        "debit": _whole("a printed debit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
    },
    "community_section": {
        "credit": _whole("a printed credit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
        "debit": _whole("a printed debit count (parser-gated, direction-keyed)", "analysis/community_section.py `_summary` (assignment), gate in `_parse_sectioned_statement`"),
    },
    "apex_scanned": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
    },
    "southside_scanned": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
    },
    "us_bank": {
        "credit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence. Both counts are "
                "sums over the printed Account Summary's category lines, split "
                "into credit and debit BY THE SIGN OF THE CATEGORY AMOUNT "
                "(analysis/us_bank.py:399-412, :467-468) — a summary-level sign split, "
                "which is why this was held incomparable until it had been "
                "measured. It reproduces the captured rows on 40 of 40 us_bank "
                "documents in both directions (COUNTS_P1_MEASUREMENT.md §3.3), "
                "re-measured as 40/40 with 0 disagreements against the current "
                "archive before this entry was written. Note what the evidence "
                "does and does not cover: the categories are printed by the "
                "bank per direction, so the split is over printed subtotals "
                "and not over individual row amounts — no zero-amount row can "
                "move across it."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="category_subtotal_sum_proven_complete",
            reason=(
                "PROMOTED with the credit direction and on the same evidence: "
                "the printed Account Summary category sums split by the sign "
                "of the category amount (analysis/us_bank.py:399-412, :467-468), "
                "reproducing the captured debit rows on 40 of 40 documents in "
                "the phase-1 measurement and 40 of 40 again when re-measured "
                "against the current archive."
            ),
        ),
    },
    "wilson_muir": {
        "credit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "PROMOTED to comparable on measured evidence. The expected "
                "side is `deposit_count + automatic_deposit_count` "
                "(analysis/wilson_muir.py:162) — a two-way sum of printed "
                "category counts — and the parser gates on the printed TOTALS "
                "rather than on the counts (:133-136), so a count "
                "disagreement is reachable rather than gated away. It "
                "reproduces the captured credit rows on 8 of 8 wilson_muir "
                "documents (COUNTS_P1_MEASUREMENT.md §3.3), re-measured 8/8 "
                "with 0 disagreements against the current archive. Same "
                "caveat as any category sum: a printed category this parser "
                "does not add would under-count the expected side."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "PROMOTED with the credit direction. The expected side is the "
                "three-way sum `debit_count + automatic_withdrawal_count + "
                "card_count` (analysis/wilson_muir.py:163), reproducing the "
                "captured debit rows on 8 of 8 documents in the phase-1 "
                "measurement and 8 of 8 again when re-measured against the "
                "current archive."
            ),
        ),
    },
    # -- incomparable, each with its own argument ----------------------
    "altana": {
        # BOTH directions, on one argument. The parser's acceptance gate is
        # `label_deposits != deposit_count -> return None` and
        # `label_withdrawals != withdrawal_count -> return None`
        # (analysis/altana.py:187-190): what the printed counts are proven
        # equal to is the count of LABEL-MATCHED rows, not the count of rows in
        # that direction. Classifying only the debit side incomparable — which
        # the parser's comment names explicitly — while comparing the credit
        # side on the identical construction would be an inconsistency this
        # check would then report as a defect.
        "credit": CountSemantics(
            comparable=False,
            scope="label_scoped_subset",
            reason=(
                "the printed deposit count is gated equal to the count of "
                "LABEL-MATCHED deposit rows (analysis/altana.py:187), not to "
                "every row the parser records as a credit. Measured: 3 of 3 "
                "altana documents record 1-2 more credit rows than the "
                "printed figure, and altana sets no stated_total_credits at "
                "all, so nothing else in the payload can even see it. An "
                "altana parser card owns the label scope; until it lands, "
                "this direction says nothing."
            ),
        ),
        "debit": CountSemantics(
            comparable=False,
            scope="label_scoped_subset",
            reason=(
                "the parser's own comment records it: \"the statement's "
                "withdrawal summary is LABEL-BASED and excludes some "
                "balance-increasing adjustment rows\" "
                "(analysis/altana.py:203-206), and the gate at :189 pins the "
                "printed figure to the labelled subset. The parser "
                "deliberately keeps the line-item rows rather than the "
                "summary's scope."
            ),
        ),
    },
    "bank_of_america": {
        "credit": _whole("'# of deposits/credits: N'", "analysis/bofa.py:427-428, :552-554, :639-641"),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "PROMOTED to comparable once the three readers were made to "
                "agree (BOFA-COUNTS). The history is the argument: BofA prints "
                "'# of withdrawals/debits' and, on some layouts, a SEPARATE "
                "'Total # of checks', and the Checks section's rows are "
                "recorded as debits by the parser — so the repair path added "
                "`debit_count + (check_count or 0)` while the native and table "
                "readers stored the raw printed figure. One field, two "
                "meanings, and the payload records nowhere which ran. "
                "CHARACTERISED FIRST, from the archive's own documents: the "
                "raw printed figure reproduces the captured debit rows on "
                "344 of 344 documents that print it, and `raw + check_count` "
                "on 0 of the 107 that also print a cheque count — the printed "
                "statistic ALREADY counts cheques, and the mapping "
                "double-counted them on every document where it fired. The "
                "control is the credit sibling in the same printed statistics "
                "box, 344 of 344. The repair now stores the raw figure "
                "(analysis/bofa.py:642) and all three readers store one "
                "documented scope (`_SUMMARY_COUNT_SCOPE`, :368-403). "
                "WHY THE MAPPING LOOKED RIGHT, recorded so nobody re-derives "
                "it: the cheque MONEY genuinely is outside 'Withdrawals and "
                "other debits' — the summary prints 'Checks' as its own line, "
                "equal to the section's own 'Total checks' figure on 107 of "
                "107, and `stated_total_debits` really does sum those lines. "
                "Money scope and count scope differ on this bank, and reading "
                "one off the other is the defect. "
                "SCOPE OF THE EVIDENCE: all 344 are the native business "
                "summary; the 16 consumer-vocabulary documents print no debit "
                "count at all (the check is `not_printed` there, never a "
                "comparison), and NO archive document renders the account "
                "summary as an HTML table, so the table reader's scope is "
                "inherited from the identical printed line rather than "
                "measured. Independence holds: the expected side is the "
                "integer the bank printed, read straight off the page, with "
                "nothing derived from a captured row. FALSIFIER: if a BofA "
                "layout is ever found whose '# of withdrawals/debits' excludes "
                "the cheque block — the tell is `raw + Total # of checks` "
                "matching where `raw` does not — this entry stops being true "
                "and the direction goes back to incomparable rather than the "
                "readers going back to disagreeing."
            ),
        ),
    },
    # W3 §GRAM4. The fourth summary grammar of the third core processor is
    # the first registration in the complex to print a count at all: the
    # second prints one per direction, the third prints none (§LCPERIOD L7.7),
    # and this one prints SIX — three categories per direction, each with its
    # own count and total, each heading a ledger section of the same name.
    "core_processor_counted": {
        "credit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "The summary prints `Deposits (N)`, `Electronic cr (N)` and "
                "`Other credits (N)`, and the expected side is their sum "
                "(analysis/core_processor_counted.py:_CATEGORIES, published "
                "at :parse_core_processor_counted_statement). The category "
                "list is CLOSED and the closure is checked rather than "
                "assumed: `_counted_partition` requires all six categories to "
                "read or the document is refused, so a fourth printed credit "
                "category would fail the document closed instead of "
                "under-counting the expected side — the failure mode every "
                "other category-sum entry in this table has to caveat. "
                "DISCLOSURE, in `burke_herbert`'s idiom: the agreement is a "
                "TAUTOLOGY and carries no information. The parser gates each "
                "category's printed count against the number of rows it read "
                "from the section that category heads "
                "(`_matches_the_printed_partition`), and it sets "
                "`Transaction.direction` from the category, so this check's "
                "set and the gate's set are the same set and a claimed "
                "document agrees by construction. Measured over all 8 archive "
                "documents of the family: 8/8 agree, 0 disagreements, 0 flags "
                "raised. NO falsifier of the `burke_herbert` kind exists "
                "here: that gate keys on the SIGN of an amount and diverges "
                "from `direction` on a $0.00 row, while this one counts ROWS "
                "per section and is blind to the amount, so a genuine $0.00 "
                "posting is counted identically by both sides. The entry is "
                "written rather than left UNSURVEYED because 'examined, and "
                "structurally silent' is a different fact from 'not yet "
                "examined'. The independent oracles for this family are the "
                "six printed category TOTALS and the daily-balance grid, "
                "neither of which any count can reproduce."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "`Checks paid (N)`, `Electronic db (N)` and `Other debits "
                "(N)`, summed, for the reason and with the construction the "
                "credit direction states — and TAUTOLOGICAL on the same "
                "gate, restated here rather than cross-referenced because an "
                "entry that cannot be read on its own is an entry nobody "
                "checks. Two things recorded so nobody "
                "re-derives them. (1) The cheque category is INSIDE the "
                "printed debit partition and inside the printed `Total "
                "debits`, and its rows are published as debits, so count and "
                "total cover one scope on both sides — the alignment W3 "
                "§FIXUPS-1 corrected on `first_community`, satisfied here by "
                "the printing itself. (2) There is no separate service-charge "
                "line outside the partition on any of the 8: a charge this "
                "issuer bills arrives as an `Electronic db` or `Other debits` "
                "row and is therefore already counted, which is why this "
                "direction needs no `CountMapping`. If an issue of this "
                "template ever prints one outside the six categories, the "
                "direction totals would stop summing to `Total debits` and "
                "the document would go UNCLAIMED rather than mis-flagged: "
                "fail-closed, not proven-absent. 8/8 agree over the family."
            ),
        ),
    },
    # W3 §CITI3 card C. A new registration, surveyed here rather than left
    # UNSURVEYED because its printed counts and the rows this parser captures
    # are the same set BY CONSTRUCTION, and that construction is checked.
    # W3 §WELCH. Comparable and TAUTOLOGICAL, and surveyed rather than
    # left UNSURVEYED for the reason `burke_herbert` gives: the silence
    # is a recorded fact, not an unexamined one.
    "welch_state_bank": {
        "credit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason="prints '<N> Deposits/Other Credits <total>' with the count LEADING its label, one printed figure per direction (analysis/welch_state_bank.py `_SUMMARY_RE`, assigned in `parse_welch_state_bank_statement`). Measured over all 17 archive documents of the family: 17/17 agree, 0 disagreements, 0 flags raised. DISCLOSURE, in the idiom of the `burke_herbert` and `community_section` entries above: that 17/17 is a TAUTOLOGY and carries no information. The parser's acceptance gate refuses any document whose count of credit rows differs from this printed figure, and the rows it counts there are the same rows it publishes with direction='credit' — the gate's set and this check's set are the same set, so a claimed document agrees by construction. There is therefore NO FALSIFIER to state: no document, real or constructed, can make this direction disagree, which is the `burke_herbert:credit` position and is exempted for the same reason. Written anyway rather than left UNSURVEYED because 'examined, and structurally silent' is a different fact from 'not yet examined'. The independent oracles for this template are the printed per-direction TOTALS and the day-by-day replay against its printed Daily Ending Balance grid, neither of which any count can reproduce.",
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason="prints '<N> Checks/Other Debits <total>', count leading, and the printed figure INCLUDES the separately-tabled `Checks Cleared` rows — a reader that skipped that table would be one to five rows short on most documents, which is mutant M13. 17/17 agree, and tautologically, for the reason the credit direction states: the acceptance gate refuses any document whose debit-row count differs from this figure, and those rows are exactly the ones published with direction='debit'. NO FALSIFIER, on the same argument. Recorded so nobody re-derives it: this template prints its overdraft and returned-item fees as ledger ROWS inside the debit section, not as a separate service-charge line, so this entry is NOT in the capital_one / texas_bank scope class and needs no mapping.",
        ),
    },
    "zions": {
        "credit": CountSemantics(
            comparable=True,
            # The existing label, not a new one: this IS "one printed figure
            # per direction". The grid prints one instance count above the
            # `Deposits/Credits` column and the parser publishes exactly the
            # rows of the `DEPOSITS/CREDITS` section that column heads.
            scope="whole_direction",
            reason=(
                "The summary grid prints one instance count above the "
                "`Deposits/Credits` column (analysis/zions.py:_blocks), and "
                "the parser's credit rows are exactly the rows of the "
                "`DEPOSITS/CREDITS` section that column heads — one printed "
                "column, one published direction. Two things stop the sides "
                "drifting apart silently: the parser refuses any row whose "
                "printed sign contradicts its section, and it parses the "
                "grid's column legend rather than assuming it, so a layout "
                "printing an unknown extra column fails the document closed "
                "instead of under-counting (analysis/zions.py:_rows, "
                ":_blocks). Measured over all 13 archive documents of the "
                "family: 13/13 agree, 0 disagreements, 0 flags raised."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="multi_category_sum_proven_complete",
            reason=(
                "The layout splits money out across TWO printed columns, "
                "`Withdrawals/Debits` and `Checks Processed`, each with its "
                "own instance count; the expected side is their sum, and the "
                "debit TOTAL is the sum of the same two columns, so count and "
                "total cover one scope — the alignment W3 §FIXUPS-1 corrected "
                "on `first_community`. Both categories post into the single "
                "`CHARGES/DEBITS` section, which is what the parser reads; "
                "`CHECKS PROCESSED` is a register of rows already posted "
                "there and is deliberately not read, so no cheque is counted "
                "twice. Measured over all 13 archive documents: 13/13 agree, "
                "0 disagreements, 0 flags raised. Same caveat as any category "
                "sum — a third printed debit category this parser did not add "
                "would under-count the expected side; the family prints none, "
                "and the grid's column legend is parsed rather than assumed, "
                "so an unknown third column fails the document closed."
            ),
        ),
    },
    # W3 §FROSTOZK. The Texas mainframe printing, and the reason this table
    # has a THIRD state that is neither `comparable` nor `unsurveyed`: one
    # direction of one bank can be comparable while the other is not, and
    # saying so is the whole content of the entry.
    "frost": {
        "credit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "The boxed summary strip prints `NO.` under `DEPOSITS` beside "
                "`AMOUNT` (analysis/frost.py::_summary_layout, assigned in "
                "`parse_frost_statement`), and it counts every row of the "
                "`DEPOSITS/CREDITS` section, which is the only section this "
                "reader posts as `credit`. Measured over all 9 archive "
                "documents of the family: 9/9 agree, 0 disagreements, 0 flags "
                "raised, over deposit counts from 5 to 41. "
                "NOT A TAUTOLOGY, and that is a deliberate build decision "
                "rather than luck. The reader's acceptance gates are the "
                "strip's own arithmetic, the two printed TOTALS and the two "
                "ends of the daily-balance grid — no gate reads a COUNT — so "
                "a document whose deposit rows this reader over- or "
                "under-counted while still summing to the printed total (a "
                "row split in two, a duplicated zero-amount row) publishes "
                "and this check flags it. Gating on the count instead would "
                "have made the agreement true by construction on the one "
                "direction where it carries information, which is the shape "
                "`burke_herbert` below has to disclose and this one does not."
            ),
        ),
        "debit": CountSemantics(
            comparable=False,
            scope="named_row_classes_excluded",
            reason=(
                "The printed `NO.` under `WITHDRAWALS` counts a NARROWER set "
                "of rows than this reader's debit rows, while the printed "
                "`AMOUNT` beside it counts the WIDER one — the split that "
                "makes a count check a false-positive generator on a ledger "
                "reconciling to the cent. Measured over all 9 archive "
                "documents with `tools/frostozk_family_replay.py`: the "
                "captured debit rows exceed the printed figure by 0, 9, 4, 0, "
                "8, 5, 0, 0 and 3, and on 9 of 9 that excess is EXACTLY the "
                "number of rows in two named classes — rows the bank printed "
                "under its own `SERVICE CHARGE/FEE` transaction type (10 "
                "across the family, 2 on each of the 5 documents that carry "
                "any) and rows printed with a ZERO amount (19 across the "
                "family; the bank prints an inquiry that moved no money in "
                "its withdrawals section). The two classes never overlap. "
                "Meanwhile the printed `AMOUNT` reproduces the sum of ALL of "
                "them, 9/9 — which is why the reader can gate on the total "
                "and must not gate on the count. "
                "WHY NO `CountMapping`: the adjustment would be "
                "`+ (service-charge rows) + (zero-amount rows)`, and both "
                "terms are facts about OUR ROWS. This family prints no "
                "service-charge summary cell at all — no `stated_service_"
                "charge`, no printed fee total, no count of inquiries — so "
                "there is no bank-printed figure the mapping could read, and "
                "a mapping keyed on the captured side is exactly what "
                "`PRINTED_EVIDENCE_FIELDS` exists to forbid. Incomparable is "
                "therefore the measured answer and not an unread default: the "
                "difference is understood exactly, and it is still not "
                "expressible as printed evidence. "
                "FALSIFIER: if a Frost printing appears whose withdrawal "
                "`NO.` equals the row count on a document carrying a "
                "`SERVICE CHARGE/FEE` row, the scope claim above is wrong and "
                "this entry becomes a plain `whole_direction` comparable."
            ),
        ),
    },
    # W3 §FROSTOZK. The Arkansas sentence-summary layout, whose reader SOLVES
    # the direction of each row against the printed daily balances and uses
    # these two counts as the constraint that makes the solve unique. Both
    # directions are therefore tautological, and the entry exists to say so:
    # `UNSURVEYED` would read as "not yet examined" when the truth is
    # "examined, and structurally silent" (the `burke_herbert` idiom).
    "bank_ozk": {
        "credit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "The summary sentence prints `PLUS <N> DEPOSITS AND OTHER "
                "CREDITS` (analysis/bank_ozk.py::_SUMMARY_RE), one figure for "
                "the whole direction, and the reader posts every row of the "
                "two printed grids and no others. Measured over all 8 archive "
                "documents: 8/8 agree, 0 disagreements, 0 flags raised. "
                "DISCLOSURE: that 8/8 is a TAUTOLOGY and carries no "
                "information. This layout does not print the direction of a "
                "row anywhere — the text layer collapses its `DEBITS` and "
                "`CREDITS` columns onto one position — so the reader recovers "
                "direction by solving each day against the printed "
                "`BALANCE BY DATE` step and uses THIS COUNT as the cross-day "
                "constraint that picks between a day's competing sign "
                "assignments. It also refuses any document whose captured row "
                "count is not `N + M`. A claimed document therefore agrees by "
                "construction, and the entry is written anyway because a live "
                "check that cannot fail is worse undisclosed than disclosed. "
                "The independent oracles for this bank are the summary's own "
                "arithmetic, the printed day count against the two printed "
                "as-of dates, and the printed credit and debit TOTALS — which "
                "come from the summary block while each day's credit sum is "
                "fixed by the daily grid, so their agreement is two printed "
                "sources meeting rather than one restating itself."
            ),
        ),
        "debit": CountSemantics(
            comparable=True,
            scope="whole_direction",
            reason=(
                "The summary sentence prints `LESS <M> CHECKS AND OTHER "
                "DEBITS`, one figure for the whole direction, and it INCLUDES "
                "the cheque block — the reader posts `CHECK TRANSACTIONS` and "
                "`OTHER TRANSACTIONS` into the one direction the figure "
                "covers, so nothing is folded on one side only. 8/8 agree "
                "over the whole family, and tautologically, for the reason "
                "the credit direction states: the reader refuses a document "
                "whose captured rows are not `N + M`, so `M` follows from `N` "
                "and the row count. RECORDED so nobody re-derives it: unlike "
                "`frost` above, this bank's printed debit count and printed "
                "debit total cover the SAME rows — the fees this layout bills "
                "post as ordinary rows of the debit grid and are inside both "
                "figures, which the row-count equality proves on all 8 — and "
                "that is why the two families sit on opposite sides of this "
                "table despite printing the same kind of summary."
            ),
        ),
    },
}

#: Applied to any parser that populated a printed count but is not in
#: :data:`SEMANTICS`. Fail-closed for the CHECK, which means SILENT: an unread
#: semantics is not a comparable one, so the flag is never raised.
UNSURVEYED = CountSemantics(
    comparable=False,
    scope="unsurveyed",
    reason=(
        "this parser is not in the surveyed semantics table but populated a "
        "printed count. The check refuses to compare semantics nobody has "
        "read rather than default to equality, so it says nothing at all "
        "about this direction."
    ),
)

#: Banks whose printed count evidence exists but is PER SECTION, which the
#: `Statement` schema has no field for, so it is not expressible in this
#: check's schema at all. Recorded here so the disclosure is data rather than
#: a paragraph someone must remember to write: PNC prints an item count per
#: section (`W3_TRACKA_LOG.md` §3.3, §3.7 item 3) and is the witness that
#: caught the swallowed-section defect, but a PER-DIRECTION check would not
#: have caught the `Fee Refunds` case because the direction totals were right.
#: Wells prints a per-account `Totals` line nothing reads (§W7.4). Neither
#: parser assigns a per-direction count, so both are silent here — which is
#: TRUE of the schema and FALSE of the document, and that distinction is the
#: disclosure.
SECTION_LEVEL_ORACLES = {
    "pnc": "prints a per-SECTION item count the Statement schema cannot hold (W3_TRACKA_LOG.md sec 3.3, sec 3.7 item 3); no per-direction field is assigned",
    "wells_fargo": "prints a per-account `Totals` line that no parser reads (W3_TRACKA_LOG.md sec W7.4)",
    "core_processor_enclosures": (
        "prints BOTH per-direction counts, and both EXCLUDE a row class the "
        "ledger posts: the credit count excludes the interest the bank "
        "credited (5 of the 48 archive members this parser publishes) and the "
        "debit count excludes the service charge it billed (19 of the 48, two "
        "of them posting it as two rows; both figures re-derived by "
        "tools/coreenc_count_scope.py). A "
        "CountMapping could express the debit half and there is no printed "
        "evidence field for the credit half, so declaring it would flag every "
        "interest-bearing member; the parser gates both scopes internally "
        "instead (W3_TRACKA_LOG.md sec COREENC)"
    ),
}


def semantics_for(parser_id: str | None, direction: str) -> CountSemantics:
    """The count semantics for one parser and one printed direction.

    An unknown parser — including `None`, which is what an LLM extraction or
    an unclaimed document has — gets :data:`UNSURVEYED`, never a comparison.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction: {direction!r}")
    table = SEMANTICS.get(parser_id or "")
    if table is None:
        return UNSURVEYED
    return table[direction]


def counts_comparable(parser_id: str | None, direction: str) -> bool:
    """Does this parser's printed count for this direction denote our rows?

    The one predicate the integrity check calls. False is the default for
    everything unproven, so a caller that forgets to ask gets no flag rather
    than a wrong one.
    """
    return semantics_for(parser_id, direction).comparable


def expected_count(
    parser_id: str | None, direction: str, printed_count: int, source: Any
) -> int:
    """The printed count, restated in the scope our rows are counted in.

    The one function that applies a :class:`CountMapping`, called by BOTH
    `analysis/reconcile.py` (which decides what is published) and the phase-1
    count observer in `telemetry/` (which predicts it). One table and one
    arithmetic: an observer that applied a different adjustment would forecast
    a flag population production does not emit.

    Returns `printed_count` unchanged for every parser without a mapping —
    which is 29 of the 31 in the table and everything outside it — so this is
    an identity for all of them and nothing about their comparison moved when
    the field arrived.

    `source` is the statement the printed count came off: a `Statement` or the
    serialized mapping of one. It is read for `PRINTED_EVIDENCE_FIELDS` and
    nothing else.
    """
    semantics = semantics_for(parser_id, direction)
    if semantics.mapping is None or not semantics.comparable:
        return printed_count
    return semantics.mapping.expected(printed_count, source)


def claiming_parser_id(dispatch: Any) -> str | None:
    """The parser whose count semantics govern this document, or None.

    A CLAIM, and nothing weaker. `analysis/pipeline.py`'s `_registration_for`
    also resolves a registration by BANK LABEL for an LLM extraction, which is
    right for document knowledge and wrong here: an entry in this table is
    evidence about what one parser's summary reader produced, not about the
    bank's paper. No claim, no semantics, no mapping, no flag.

    It lives here, beside the table, because two call sites need the identical
    answer — `reconcile`, which APPLIES the mapping, and
    `assess_document_integrity`, which decides whether the result may be
    flagged. Two copies of this expression could drift into applying an
    adjustment under one table row and judging it under another; one function
    cannot. Duck-typed on purpose, so this module still imports nothing but the
    standard library.
    """
    if dispatch is None or getattr(dispatch, "outcome", None) != "claimed":
        return None
    return getattr(dispatch, "parser_id", None)

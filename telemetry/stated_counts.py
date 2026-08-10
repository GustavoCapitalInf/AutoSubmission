"""COUNTS-P1 — the stated-count integrity observer, PHASE 1: OBSERVE ONLY.

The platform extracts ``stated_credit_count`` / ``stated_debit_count`` from
twenty parser modules and **publishes them as its own deposit and withdrawal
counts** (``analysis/metrics.py:353-356``, ``:368-371``) without ever comparing
them against the rows it publishes beside them. `PROPOSAL_STATED_COUNTS.md`
proposes that comparison; Gustavo's 2026-08-10 sign-off
(`WAVE2_EXECUTION_LOG.md`) made a two-phase rollout MANDATORY and this module
is phase 1 of it.

**Phase 1 changes nothing.** Nothing here is imported by ``analysis/``,
``ocr/``, ``webapp/`` or ``discovery/``; no flag is emitted; no outcome class
moves; no payload is written. This is a measuring instrument pointed at
already-cached artifacts, and its whole output is a statistic. The production
path is phase-2 material and phase 2 exists only after Gustavo reviews the
measurement this module produces.

The closed result vocabulary (binding, from the sign-off)
--------------------------------------------------------
Per document **per direction**, exactly one of:

``match``
    the bank's printed count for this direction equals the count we recomputed
    from the rows.
``mismatch``
    both sides exist, the semantics are comparable, and they disagree.
``not_printed``
    no printed count exists on the expected side — the bank printed none, or
    the claiming parser does not read it. Absence is a fact about the
    document, never a failure, and a missing count is never inferred from the
    other direction.
``semantics_incomparable``
    a printed count exists but it does not denote the same set of rows our
    ``direction`` field denotes (cheques folded into a debit category, category
    subtotals, three-way sums, per-section counts the schema cannot hold).
    **An incomparable direction can never emit ``mismatch``** — that is the
    forced-mismatch prohibition, and it is enforced structurally by the order
    of :func:`evaluate`, not by a caller remembering to check.
``check_unavailable``
    the check could not be run: no cached payload for this document, no
    statement in the payload, no rows, aggregate-backed rows standing in for
    many postings, or a row with no ``direction``.

Two rules the sign-off made binding, and how they are honoured here
-------------------------------------------------------------------
**Independence.** The expected side is *bank-printed evidence*: only
``statement.stated_credit_count`` / ``statement.stated_debit_count``, the
fields a parser fills from the printed summary. The captured side is
recomputed **here**, in this module, from ``statement.transactions[].direction``.
``metrics.effective_num_deposits`` / ``effective_num_withdrawals`` /
``num_deposits`` / ``num_withdrawals`` are **never read** — they are where the
bank's printed count is copied *to*, so reading them would let a parser satisfy
the check by handing back its own input. :data:`EXPECTED_FIELDS` and
:data:`CAPTURED_FIELDS` are the provenance of both sides, and
``tests/test_stated_counts.py`` asserts the ``metrics`` section is never
touched.

**Direction, not sign.** ``analysis/schema.py:18`` makes ``direction`` a
required field recording *the column the bank printed the row in*; the sign
records the money. ``analysis/metrics.py:186-191`` counts ``t.amount >= 0`` as
a deposit, so a **zero-amount row is counted as a deposit whatever column it
was printed in** — exactly the class RBC §5.5 names (six already-validated
documents whose per-direction count contradicted the bank's own summary). A
count check keyed on sign would inherit the defect it exists to catch. This
module counts by ``direction`` and reports the sign-keyed count alongside as
evidence, never as the answer.

Sensitivity
-----------
H3_SCHEMA I1 applies absolutely: what leaves this module is hashes, registry
ids, enum codes and integers. Filenames are read (the markdown header the
analysis cache is keyed on contains one, so the artifact join needs it) and are
**never** emitted — see :func:`_ArtifactJoin`. No description, amount, date,
account number or bank-printed string ever reaches an observation.

    python -m telemetry.stated_counts --run discovery_reports/<run> \\
        --data-dir webapp_data [--corpus-audit docs/adb-audit-results.csv] \\
        [--json]

Mapping rationale, per bank: `docs/moneythumb-replacement/COUNTS_P1_MEASUREMENT.md` §3.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

#: Bumped when the vocabulary, the evaluation order or the semantics table
#: changes, so two measurement runs can be told apart. Phase 1 ships at 1.
OBSERVER_VERSION = 1

# ----------------------------------------------------------------------
# the closed vocabulary
# ----------------------------------------------------------------------

MATCH = "match"
MISMATCH = "mismatch"
NOT_PRINTED = "not_printed"
SEMANTICS_INCOMPARABLE = "semantics_incomparable"
CHECK_UNAVAILABLE = "check_unavailable"

#: Gustavo's closed vocabulary, in the order the sign-off states it. Nothing
#: outside this tuple may ever be an observation's `result`.
RESULTS = (MATCH, MISMATCH, NOT_PRINTED, SEMANTICS_INCOMPARABLE, CHECK_UNAVAILABLE)

#: The two printed directions. `Transaction.direction` is required and is one
#: of exactly these (`analysis/schema.py:18`).
DIRECTIONS = ("credit", "debit")

#: Why a direction got the result it got. A closed enum, like every other
#: string this module emits — never a message, never document content.
REASON_PAYLOAD_ABSENT = "payload_absent"
REASON_STATEMENT_ABSENT = "statement_absent"
REASON_NO_TRANSACTIONS = "no_transactions"
REASON_AGGREGATE_BACKED = "aggregate_backed"
REASON_DIRECTION_MISSING = "direction_missing"
REASON_NOT_A_FORMAL_STATEMENT = "not_a_formal_statement"
REASON_NO_PRINTED_COUNT = "no_printed_count"
REASON_INCOMPARABLE = "incomparable"
REASON_UNSURVEYED_PARSER = "unsurveyed_parser"
REASON_COMPARED = "compared"

REASONS = (
    REASON_PAYLOAD_ABSENT,
    REASON_STATEMENT_ABSENT,
    REASON_NO_TRANSACTIONS,
    REASON_AGGREGATE_BACKED,
    REASON_DIRECTION_MISSING,
    REASON_NOT_A_FORMAL_STATEMENT,
    REASON_NO_PRINTED_COUNT,
    REASON_INCOMPARABLE,
    REASON_UNSURVEYED_PARSER,
    REASON_COMPARED,
)

#: The ONLY fields the expected side may come from — bank-printed evidence as
#: the parser extracted it. `analysis/schema.py:45-46`.
EXPECTED_FIELDS = {
    "credit": ("statement", "stated_credit_count"),
    "debit": ("statement", "stated_debit_count"),
}

#: The ONLY fields the captured side is recomputed from, here, by us.
#: `analysis/schema.py:18` — the printed column, not the sign of the money.
CAPTURED_FIELDS = ("statement", "transactions", "[]", "direction")

#: Never read. Named so the independence rule is checkable rather than
#: promised: these are where `metrics` COPIES the bank's printed count to
#: (`analysis/metrics.py:353-356`, `:368-371`), so sourcing the expected side
#: from any of them would let a parser satisfy the check with its own input.
FORBIDDEN_EXPECTED_SOURCES = (
    ("metrics", "effective_num_deposits"),
    ("metrics", "effective_num_withdrawals"),
    ("metrics", "num_deposits"),
    ("metrics", "num_withdrawals"),
    ("metrics", "total_posted_credit_count"),
)

#: `analysis/pipeline.py:140` — one aggregate row stands for many postings by
#: design, so the count check is structurally guaranteed to disagree and would
#: say nothing. Matched on the description the pipeline itself writes.
AGGREGATE_MARKER = "UNCAPTURED"


# ----------------------------------------------------------------------
# the per-bank count semantics table
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Semantics:
    """What a bank's printed count for one direction actually denotes.

    `comparable` is the whole decision: False means the printed figure counts a
    different set of rows than `direction == <this direction>` does, so an
    equality test between them is not a defect detector — it is a mis-reading of
    the document. `scope` is the short label used in the rollup; `reason`
    carries the argument and its `file:line` provenance.
    """

    comparable: bool
    scope: str
    reason: str


def _whole(printed: str, provenance: str) -> Semantics:
    """A bank that prints ONE count meaning 'every row in this direction'."""
    return Semantics(
        comparable=True,
        scope="whole_direction",
        reason=f"prints {printed}; one printed figure per direction ({provenance})",
    )


#: Per parser id (`analysis/parser_registry_entries.py`), per direction.
#:
#: Only the parsers that ASSIGN `stated_credit_count`/`stated_debit_count` are
#: listed. A parser absent from this table never populates the expected side
#: in the deterministic path, so its documents report `not_printed`; if one
#: ever does populate it, :func:`semantics_for` returns the unsurveyed default,
#: which is INCOMPARABLE — the observer refuses to compare semantics nobody has
#: read, rather than defaulting to a comparison that could manufacture a
#: mismatch. That default is what makes this table's completeness auditable.
SEMANTICS: dict[str, dict[str, Semantics]] = {
    # -- comparable: one printed figure per direction ------------------
    "atb": {
        "credit": _whole("a credit count and a debit count in one summary block", "analysis/atb.py:121-122"),
        "debit": _whole("a credit count and a debit count in one summary block", "analysis/atb.py:121-122"),
    },
    "capital_one": {
        # "N Deposits/Credits" is a whole-direction figure and cheques ARE
        # inside the printed debit figure by the bank's own label — folded on
        # both sides, which is comparable (cf. bofa, folded on one side only).
        "credit": _whole("'N Deposits/Credits'", "analysis/capital_one.py:37-39, :189-193"),
        "debit": Semantics(
            comparable=False,
            scope="service_charge_excluded_from_printed_debit_count",
            reason=(
                "the printed summary is a LIST of lines — 'N Checks/Debits "
                "($x)' AND a separate 'Service Charges ($y)' "
                "(analysis/capital_one.py:20-28, :189-197). The service charge "
                "is its own printed line with no count, its money is inside "
                "the printed debit TOTAL, and the parser records it as a debit "
                "ROW. So the printed debit count enumerates a strict subset of "
                "the parser's debit rows: same money, different scope. "
                "Measured: 12 of 12 capital_one documents disagree by EXACTLY "
                "+1 captured debit with a non-zero stated_service_charge on "
                "every one, and debit_coverage is 1.0 with sum_delta 0.0 "
                "throughout — the rows are right and the scopes differ. "
                "`stated_debit_count + 1 where a service charge is printed` is "
                "the mapping a phase-2 parser card should encode; asserting it "
                "here would be phase 1 changing the expected side, which it "
                "may not do."
            ),
        ),
    },
    "chase": {
        "credit": _whole("'Deposits and Additions  N  $x'", "analysis/chase.py:404-405, :531"),
        "debit": Semantics(
            comparable=False,
            scope="category_subtotal_sum",
            reason=(
                "the debit figure is a SUM over a closed label list "
                "(_SUMMARY_DEBIT_LABELS, analysis/chase.py:380-387; summed at "
                ":409-418 and :535-543), not a printed whole-direction count. "
                "The expected side therefore depends on which labels this "
                "parser knows, so a Chase layout printing a debit category the "
                "list does not name under-counts the EXPECTED side and would "
                "manufacture a mismatch against correct rows. Category "
                "subtotals are named incomparable in the 2026-08-10 sign-off."
            ),
        ),
    },
    "chase_export": {
        "credit": _whole("'Deposits and Additions  N  $x'", "analysis/chase.py:404-405, :531"),
        "debit": Semantics(
            comparable=False,
            scope="category_subtotal_sum",
            reason="same summary reader as `chase` (analysis/chase.py:380-387).",
        ),
    },
    "farmers_merchants": {
        "credit": _whole("a credit count in the printed account summary", "analysis/farmers_merchants.py:56-57"),
        "debit": _whole("a debit count in the printed account summary", "analysis/farmers_merchants.py:56-57"),
    },
    "first_community": {
        "credit": _whole("a credit count in the printed summary line", "analysis/first_community.py:150-151"),
        "debit": _whole("a debit count in the printed summary line", "analysis/first_community.py:150-151"),
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
        "credit": _whole("'Total deposits & credits (N)  + $x'", "analysis/rbc.py:399-401"),
        "debit": _whole("'Total cheques & debits (N)  - $x'", "analysis/rbc.py:403-405"),
    },
    "rbc_french": {
        "credit": _whole("the French twin of 'Total deposits & credits (N)'", "analysis/rbc.py:399-405"),
        "debit": _whole("the French twin of 'Total cheques & debits (N)'", "analysis/rbc.py:399-405"),
    },
    "scotiabank": {
        "credit": _whole("'No. of Credits' in the printed summary grid", "analysis/scotia.py:80-82"),
        "debit": _whole("'No. of Debits' in the printed summary grid", "analysis/scotia.py:80-82"),
    },
    "td_canada": {
        "credit": _whole("'CREDITS  N  $x'", "analysis/td_can.py:449-453"),
        "debit": _whole("'DEBITS  N  $x'", "analysis/td_can.py:454-457"),
    },
    "td_canada_native": {
        # Accumulated across every printed summary line (`(or 0) + n`,
        # analysis/td_can.py:451/456 and :586-598) because a TD statement can
        # print the block more than once. Each line is still a whole-direction
        # figure, so the sum is one; a REPEATED block would double the expected
        # side, which is a defect the measurement can see rather than a
        # semantics difference the observer should hide.
        "credit": _whole("'CREDITS  N  $x', summed over printed summary lines", "analysis/td_can.py:451, :586-592"),
        "debit": _whole("'DEBITS  N  $x', summed over printed summary lines", "analysis/td_can.py:456, :598"),
    },
    "texas_bank": {
        "credit": _whole("'Deposits ( N ) + $x'", "analysis/texas_bank.py:68, :129"),
        "debit": Semantics(
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
    # document goes unclaimed (analysis/community_section.py:205-210,
    # analysis/scanned_small_bank.py:206-207, :368-369, :525-527). A document
    # they claimed has, by construction, matching counts... under the gate's
    # OWN key, which is `amount > 0` / `amount < 0` — the SIGN. A zero-amount
    # row is on neither side of that gate but is on exactly one side of ours.
    # So these parsers are immune to a sign-keyed check and NOT immune to this
    # one, which makes them the sharpest available direction-vs-sign probe.
    # Semantics are comparable; the immunity claim is the thing to measure.
    "mission_valley": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/community_section.py:192-193, :205-210"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/community_section.py:192-193, :205-210"),
    },
    "dakota_west": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/community_section.py:192-193, :205-210"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/community_section.py:192-193, :205-210"),
    },
    "apex_scanned": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
    },
    "southside_scanned": {
        "credit": _whole("a printed credit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
        "debit": _whole("a printed debit count (parser-gated, sign-keyed)", "analysis/scanned_small_bank.py:287-288, :466-467"),
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
        # side on the identical construction would be an inconsistency the
        # measurement would then report as a defect.
        "credit": Semantics(
            comparable=False,
            scope="label_scoped_subset",
            reason=(
                "the printed deposit count is gated equal to the count of "
                "LABEL-MATCHED deposit rows (analysis/altana.py:187), not to "
                "every row the parser records as a credit. Measured: 3 of 3 "
                "altana documents record 1-2 more credit rows than the "
                "printed figure, and altana sets no stated_total_credits at "
                "all, so nothing else in the payload can even see it."
            ),
        ),
        "debit": Semantics(
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
        "credit": _whole("'# of deposits/credits: N'", "analysis/bofa.py:388-390, :511-513, :574"),
        "debit": Semantics(
            comparable=False,
            scope="cheques_excluded_from_printed_debits",
            reason=(
                "BofA prints '# of withdrawals/debits' and a SEPARATE "
                "'Total # of checks'; the Checks section's rows are recorded "
                "as debits by the parser. Only ONE of the three BofA summary "
                "readers applies the mapping — the repair path adds "
                "`debit_count + (check_count or 0)` (analysis/bofa.py:589) "
                "while the native path (:391-393) and the table path (:515-516) "
                "store the raw figure. The payload does not record which path "
                "ran, so the expected side means two different things across "
                "one bank's population and neither the raw nor the mapped form "
                "is safe to assert. Comparable-with-mapping was considered and "
                "REJECTED for phase 1 for that reason; the advisory block "
                "measures both forms so phase 2 can decide with numbers. This "
                "is the 'cheques folded into debit categories' class the "
                "2026-08-10 sign-off names."
            ),
        ),
    },
    "us_bank": {
        "credit": Semantics(
            comparable=False,
            scope="category_subtotal_sum_split_by_sign",
            reason=(
                "both counts are sums over the printed Account Summary's "
                "category lines, split into credit and debit BY THE SIGN OF THE "
                "CATEGORY AMOUNT (analysis/us_bank.py:293-294). The expected "
                "side is therefore sign-derived at the summary level — the very "
                "key this check exists to avoid — and it is a category subtotal "
                "sum. Named in the 2026-08-10 sign-off."
            ),
        ),
        "debit": Semantics(
            comparable=False,
            scope="category_subtotal_sum_split_by_sign",
            reason="see the credit direction (analysis/us_bank.py:293-294).",
        ),
    },
    "wilson_muir": {
        "credit": Semantics(
            comparable=False,
            scope="multi_category_sum",
            reason=(
                "`deposit_count + automatic_deposit_count` "
                "(analysis/wilson_muir.py:162) — a two-way sum of printed "
                "category counts, and the parser gates on the printed TOTALS, "
                "not on the counts (:133-136), so a count disagreement is "
                "reachable. The 'Wilson & Muir three-way' class named in the "
                "2026-08-10 sign-off."
            ),
        ),
        "debit": Semantics(
            comparable=False,
            scope="multi_category_sum",
            reason=(
                "`debit_count + automatic_withdrawal_count + card_count` "
                "(analysis/wilson_muir.py:163) — the three-way sum itself."
            ),
        ),
    },
}

#: Applied to any parser that populated a printed count but is not in
#: :data:`SEMANTICS`. Fail-closed for the OBSERVER: an unread semantics is not
#: a comparable one.
UNSURVEYED = Semantics(
    comparable=False,
    scope="unsurveyed",
    reason=(
        "this parser is not in the surveyed semantics table but populated a "
        "printed count. The observer refuses to compare semantics nobody has "
        "read rather than default to equality."
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
#: parser assigns `stated_credit_count`/`stated_debit_count`, so both report
#: `not_printed` — which is TRUE of the schema and FALSE of the document, and
#: that distinction is the disclosure.
SECTION_LEVEL_ORACLES = {
    "pnc": "prints a per-SECTION item count the Statement schema cannot hold (W3_TRACKA_LOG.md sec 3.3, sec 3.7 item 3); no per-direction field is assigned",
    "wells_fargo": "prints a per-account `Totals` line that no parser reads (W3_TRACKA_LOG.md sec W7.4)",
}


def semantics_for(parser_id: str | None, direction: str) -> Semantics:
    """The count semantics for one parser and one printed direction."""
    if direction not in DIRECTIONS:
        raise ValueError(f"unknown direction: {direction!r}")
    table = SEMANTICS.get(parser_id or "")
    if table is None:
        return UNSURVEYED
    return table[direction]


# ----------------------------------------------------------------------
# observations
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class DirectionObservation:
    """One direction of one document, in the closed vocabulary."""

    direction: str
    result: str
    reason: str
    stated: int | None = None
    captured: int | None = None
    captured_by_sign: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "result": self.result,
            "reason": self.reason,
            "stated": self.stated,
            "captured": self.captured,
            "captured_by_sign": self.captured_by_sign,
        }


@dataclass(frozen=True)
class Observation:
    """One document. Hashes, ids, enum codes and integers only."""

    parser_id: str | None
    credit: DirectionObservation
    debit: DirectionObservation
    transactions: int = 0
    zero_amount_rows: int = 0
    direction_sign_disagreements: int = 0
    #: Non-vocabulary sub-measurements. NEVER part of a rollup's outcome
    #: counts: these exist so phase 2 can be decided with numbers on the
    #: populations phase 1 refuses to compare.
    advisory: dict[str, Any] = field(default_factory=dict)

    def directions(self) -> tuple[DirectionObservation, DirectionObservation]:
        return (self.credit, self.debit)

    def as_dict(self) -> dict[str, Any]:
        return {
            "parser_id": self.parser_id,
            "credit": self.credit.as_dict(),
            "debit": self.debit.as_dict(),
            "transactions": self.transactions,
            "zero_amount_rows": self.zero_amount_rows,
            "direction_sign_disagreements": self.direction_sign_disagreements,
            "advisory": dict(self.advisory),
        }


def _unavailable(parser_id: str | None, reason: str) -> Observation:
    return Observation(
        parser_id=parser_id,
        credit=DirectionObservation("credit", CHECK_UNAVAILABLE, reason),
        debit=DirectionObservation("debit", CHECK_UNAVAILABLE, reason),
    )


def unavailable(parser_id: str | None, reason: str = REASON_PAYLOAD_ABSENT) -> Observation:
    """The observation for a document with no cached payload to read.

    Every document the archive contains gets an observation — a document that
    could not be analyzed at all is `check_unavailable`, not absent from the
    denominator. Coverage that quietly drops its misses is not coverage.
    """
    if reason not in REASONS:
        raise ValueError(f"unknown reason: {reason!r}")
    return _unavailable(parser_id, reason)


def _as_int(value: Any) -> int | None:
    """A printed count is an integer or it is not evidence."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and value != int(value):
        return None
    return int(value)


def evaluate(
    payload: Mapping[str, Any] | None,
    *,
    parser_id: str | None = None,
    formal_statement: bool = True,
) -> Observation:
    """Compare bank-printed counts against rows, for one cached payload.

    `payload` is a serialized analysis report (`analysis/serialization.py`
    ``report_to_dict``) exactly as the D-3 artifact cache stores it. It is READ
    and never written: nothing here mutates the mapping or anything reachable
    from it, and `tests/test_stated_counts.py` pins that with a deep
    before/after comparison.

    Evaluation order, and why it is this order:

    1. no payload / no ``statement`` -> ``check_unavailable``. Nothing is
       knowable, including whether a count was printed.
    2. the expected side is absent -> ``not_printed``. Ranked ABOVE the
       captured-side guards because it is the one thing we can assert with
       certainty about the document even when the rows are unusable, and
       because absence of printed evidence ends the check outright: there is
       nothing to be independent of.
    3. the semantics are not comparable -> ``semantics_incomparable``. Ranked
       ABOVE the comparison, which is what makes the forced-mismatch
       prohibition structural: no code path reaches ``mismatch`` from a
       direction whose :class:`Semantics` says ``comparable=False``.
    4. the captured side cannot be computed -> ``check_unavailable``.
    5. compare, exactly, no tolerance -> ``match`` / ``mismatch``. A count is
       an integer the bank printed; the ±2% band `analysis/reconcile.py:67-71`
       uses for money exists because OCR and rounding make money approximate,
       and neither applies to an integer.

    Reversals are counted GROSS. `analysis/reconcile.py:165-207` nets
    settlement reversals out of the MONEY coverage because banks net them in
    printed totals; a reversal is nonetheless a printed row the bank counted,
    so netting it out of a COUNT would create the mismatch it was meant to
    remove.
    """
    if not isinstance(payload, Mapping):
        return _unavailable(parser_id, REASON_PAYLOAD_ABSENT)
    statement = payload.get("statement")
    if not isinstance(statement, Mapping):
        return _unavailable(parser_id, REASON_STATEMENT_ABSENT)

    rows = statement.get("transactions")
    rows = list(rows) if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)) else []

    # -- the captured side, recomputed here, by direction ---------------
    captured: dict[str, int] = {"credit": 0, "debit": 0}
    captured_by_sign: dict[str, int] = {"credit": 0, "debit": 0}
    zero_amount_rows = 0
    disagreements = 0
    direction_missing = False
    aggregate_backed = False
    for row in rows:
        if not isinstance(row, Mapping):
            direction_missing = True
            continue
        description = row.get("description")
        if isinstance(description, str) and AGGREGATE_MARKER in description.upper():
            aggregate_backed = True
        direction = row.get("direction")
        amount = row.get("amount")
        amount = amount if isinstance(amount, (int, float)) and not isinstance(amount, bool) else None
        # `metrics.py:186-191` reads `t.amount >= 0` as a deposit, so a
        # zero-amount row lands in the credit bucket whatever column printed
        # it. Reproduced here EXACTLY, as the counterfactual, never as the
        # answer.
        sign_direction = "credit" if (amount is None or amount >= 0) else "debit"
        captured_by_sign[sign_direction] += 1
        if amount == 0:
            zero_amount_rows += 1
        if direction not in DIRECTIONS:
            direction_missing = True
            continue
        captured[direction] += 1
        if direction != sign_direction:
            disagreements += 1

    observations: dict[str, DirectionObservation] = {}
    for direction in DIRECTIONS:
        _section, field_name = EXPECTED_FIELDS[direction]
        stated = _as_int(statement.get(field_name))
        semantics = semantics_for(parser_id, direction)

        if stated is None:
            observations[direction] = DirectionObservation(
                direction, NOT_PRINTED, REASON_NO_PRINTED_COUNT
            )
            continue
        if not semantics.comparable:
            observations[direction] = DirectionObservation(
                direction,
                SEMANTICS_INCOMPARABLE,
                REASON_UNSURVEYED_PARSER
                if semantics is UNSURVEYED
                else REASON_INCOMPARABLE,
                stated=stated,
            )
            continue
        if not formal_statement:
            observations[direction] = DirectionObservation(
                direction, CHECK_UNAVAILABLE, REASON_NOT_A_FORMAL_STATEMENT, stated=stated
            )
            continue
        if not rows:
            observations[direction] = DirectionObservation(
                direction, CHECK_UNAVAILABLE, REASON_NO_TRANSACTIONS, stated=stated
            )
            continue
        if aggregate_backed:
            observations[direction] = DirectionObservation(
                direction, CHECK_UNAVAILABLE, REASON_AGGREGATE_BACKED, stated=stated
            )
            continue
        if direction_missing:
            observations[direction] = DirectionObservation(
                direction, CHECK_UNAVAILABLE, REASON_DIRECTION_MISSING, stated=stated
            )
            continue
        observations[direction] = DirectionObservation(
            direction,
            MATCH if captured[direction] == stated else MISMATCH,
            REASON_COMPARED,
            stated=stated,
            captured=captured[direction],
            captured_by_sign=captured_by_sign[direction],
        )

    return Observation(
        parser_id=parser_id,
        credit=observations["credit"],
        debit=observations["debit"],
        transactions=len(rows),
        zero_amount_rows=zero_amount_rows,
        direction_sign_disagreements=disagreements,
        advisory=_advisory(payload, statement, parser_id, captured, rows),
    )


def _advisory(
    payload: Mapping[str, Any],
    statement: Mapping[str, Any],
    parser_id: str | None,
    captured: Mapping[str, int],
    rows: Sequence[Any],
) -> dict[str, Any]:
    """Sub-measurements that are NOT the vocabulary and never rolled into it.

    Phase 1's job is to tell Gustavo what phase 2 would do. For the
    incomparable populations the vocabulary answer is deliberately silent, so
    the counterfactual is measured here and labelled as a counterfactual: what
    the comparison WOULD have said, and — for BofA — what it would say under
    the `+ check_count` mapping one of its three readers already applies
    (`analysis/bofa.py:589`).
    """
    out: dict[str, Any] = {}
    for direction in DIRECTIONS:
        semantics = semantics_for(parser_id, direction)
        if semantics.comparable:
            continue
        stated = _as_int(statement.get(EXPECTED_FIELDS[direction][1]))
        if stated is None or not rows:
            continue
        out[f"{direction}_would_be"] = (
            MATCH if captured[direction] == stated else MISMATCH
        )
        out[f"{direction}_delta"] = captured[direction] - stated
    if parser_id in ("bank_of_america",):
        # The mapped form of the BofA debit expected side. `check_count` is a
        # metrics-side COUNT OF ROWS, not the bank's printed 'Total # of
        # checks' — it is used ONLY here, in an explicitly-labelled
        # counterfactual, and never as the expected side of a vocabulary
        # result, so the independence rule is untouched.
        stated = _as_int(statement.get("stated_debit_count"))
        metrics = payload.get("metrics")
        checks = _as_int(metrics.get("check_count")) if isinstance(metrics, Mapping) else None
        if stated is not None and checks is not None and rows:
            out["debit_would_be_with_check_mapping"] = (
                MATCH if captured["debit"] == stated + checks else MISMATCH
            )
    return out


# ----------------------------------------------------------------------
# rollup
# ----------------------------------------------------------------------


def rollup(
    observations: Iterable[tuple[Mapping[str, Any], Observation]],
) -> dict[str, Any]:
    """Parser x direction x result, plus the populations the sign-off asks for.

    `observations` is `(context, observation)` where `context` carries the
    non-sensitive facts the artifact payload does not: `content_sha256`,
    `outcome_class` and `corpus_status`. Nothing else from the context is read.
    """
    totals: Counter[str] = Counter()
    totals_sign: Counter[str] = Counter()
    per_parser: dict[str, dict[str, Counter[str]]] = {}
    coverage = Counter()
    flagged: dict[str, dict[str, list[str]]] = {}
    corpus_pass_mismatch: list[dict[str, Any]] = []
    corpus_pass_advisory_mismatch: list[dict[str, Any]] = []
    advisory: dict[str, Counter[str]] = {}
    direction_vs_sign: dict[str, Counter[str]] = {}

    total_docs = 0
    for context, obs in observations:
        total_docs += 1
        parser = obs.parser_id or "(unclaimed)"
        table = per_parser.setdefault(parser, {d: Counter() for d in DIRECTIONS})
        results = set()
        for direction_obs in obs.directions():
            table[direction_obs.direction][direction_obs.result] += 1
            totals[direction_obs.result] += 1
            results.add(direction_obs.result)

        if results & {MATCH, MISMATCH}:
            coverage["comparable_document"] += 1
        if MISMATCH in results:
            coverage["mismatch_document"] += 1
        if results == {NOT_PRINTED}:
            coverage["no_printed_count_document"] += 1
        if results == {CHECK_UNAVAILABLE}:
            coverage["unavailable_document"] += 1
        if SEMANTICS_INCOMPARABLE in results:
            coverage["incomparable_document"] += 1

        counter = direction_vs_sign.setdefault(parser, Counter())
        counter["documents"] += 1
        counter["zero_amount_rows"] += obs.zero_amount_rows
        counter["direction_sign_disagreements"] += obs.direction_sign_disagreements
        if obs.zero_amount_rows:
            counter["documents_with_zero_amount_rows"] += 1
        if obs.direction_sign_disagreements:
            counter["documents_where_sign_would_differ"] += 1
        # The counterfactual the sign-off asks to be proved: rerun the SAME
        # comparison keyed on `amount >= 0` (`analysis/metrics.py:186-191`)
        # instead of on `direction`, and count where the answer would flip.
        # `sign_false_mismatch` is the damage a sign-keyed check would do —
        # correct rows called wrong.
        for direction_obs in obs.directions():
            if direction_obs.result not in (MATCH, MISMATCH):
                continue
            sign_result = (
                MATCH if direction_obs.captured_by_sign == direction_obs.stated else MISMATCH
            )
            if sign_result == direction_obs.result:
                continue
            counter[
                "sign_false_mismatch" if direction_obs.result == MATCH else "sign_false_match"
            ] += 1
            totals_sign[
                "sign_false_mismatch" if direction_obs.result == MATCH else "sign_false_match"
            ] += 1

        for key, value in obs.advisory.items():
            advisory.setdefault(parser, Counter())[f"{key}={value}"] += 1

        if MISMATCH in results:
            outcome = str(context.get("outcome_class") or "(unknown)")
            bucket = flagged.setdefault(outcome, {})
            bucket.setdefault(parser, []).append(str(context.get("content_sha256") or ""))
        if context.get("corpus_status") == "PASS":
            record = {
                "content_sha256": context.get("content_sha256"),
                "parser_id": obs.parser_id,
                "credit": obs.credit.as_dict(),
                "debit": obs.debit.as_dict(),
                "advisory": dict(obs.advisory),
            }
            if MISMATCH in results:
                corpus_pass_mismatch.append(record)
            elif any(value == MISMATCH for value in obs.advisory.values()):
                # A pinned PASS document the vocabulary declines to compare but
                # whose counterfactual disagrees. Reported SEPARATELY and never
                # as a mismatch: D5 is adjudication-first material and the
                # distinction between "we say this is wrong" and "we decline to
                # say" is the whole point of the closed vocabulary.
                corpus_pass_advisory_mismatch.append(record)

    return {
        "observer_version": OBSERVER_VERSION,
        "documents": total_docs,
        "direction_results": dict(totals),
        "coverage": dict(coverage),
        "per_parser": {
            parser: {d: dict(c) for d, c in table.items()}
            for parser, table in sorted(per_parser.items())
        },
        "would_be_flagged": {
            outcome: {p: {"documents": len(h), "hashes": sorted(h)} for p, h in sorted(parsers.items())}
            for outcome, parsers in sorted(flagged.items())
        },
        "corpus_pass_mismatch": corpus_pass_mismatch,
        "corpus_pass_advisory_mismatch": corpus_pass_advisory_mismatch,
        "advisory": {p: dict(c) for p, c in sorted(advisory.items())},
        "sign_keyed_counterfactual": dict(totals_sign),
        "direction_vs_sign": {p: dict(c) for p, c in sorted(direction_vs_sign.items())},
        "section_level_oracles": dict(SECTION_LEVEL_ORACLES),
    }


def render(summary: Mapping[str, Any]) -> str:
    """The rollup as text. Counts and ids; never a filename, never content."""
    lines = [
        f"stated-count observer v{summary['observer_version']} (PHASE 1 - OBSERVE ONLY)",
        f"documents: {summary['documents']}",
        "",
        "direction results (2 per document)",
    ]
    total = sum(summary["direction_results"].values()) or 1
    for name in RESULTS:
        count = summary["direction_results"].get(name, 0)
        lines.append(f"  {name:<24} {count:>6}  {100.0 * count / total:5.1f}%")
    lines += ["", "coverage (documents)"]
    for key, value in sorted(summary["coverage"].items()):
        lines.append(f"  {key:<32} {value:>6}")
    lines += ["", "per parser (credit / debit)"]
    header = f"  {'parser':<22}" + "".join(f"{n[:9]:>11}" for n in RESULTS)
    lines.append(header)
    for parser, table in summary["per_parser"].items():
        for direction in DIRECTIONS:
            counts = table[direction]
            if not sum(counts.values()):
                continue
            label = f"{parser}:{direction}"
            lines.append(
                f"  {label:<22}" + "".join(f"{counts.get(n, 0):>11}" for n in RESULTS)
            )
    lines += ["", "would-be-flagged (mismatch) by current outcome class"]
    if not summary["would_be_flagged"]:
        lines.append("  (none)")
    for outcome, parsers in summary["would_be_flagged"].items():
        for parser, info in parsers.items():
            lines.append(f"  {outcome:<12} {parser:<22} {info['documents']:>5}")
    lines += [
        "",
        f"pinned-corpus PASS documents with mismatch: {len(summary['corpus_pass_mismatch'])}",
        "pinned-corpus PASS documents with an ADVISORY-only disagreement: "
        f"{len(summary['corpus_pass_advisory_mismatch'])}",
        "",
        "direction-vs-sign counterfactual (compared directions only)",
    ]
    counterfactual = summary["sign_keyed_counterfactual"]
    lines.append(f"  sign_false_mismatch {counterfactual.get('sign_false_mismatch', 0):>6}")
    lines.append(f"  sign_false_match    {counterfactual.get('sign_false_match', 0):>6}")
    lines += ["", "section-level printed oracles NOT expressible in this schema"]
    for parser, note in summary["section_level_oracles"].items():
        lines.append(f"  {parser}: {note}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# sources — the read-only join over cached artifacts
# ----------------------------------------------------------------------


class _ArtifactJoin:
    """Resolve a discovery run's documents to their cached analysis payloads.

    The two caches are keyed on different things by design
    (`webapp/artifact_cache.py`): the OCR stage on the PDF's `content_sha256`,
    the ANALYSIS stage on `text_sha256` of the exact markdown analyzed. So the
    join is: PDF hash -> cached OCR artifact -> rebuild the `StatementMarkdown`
    -> `to_markdown()` -> markdown hash -> cached analysis artifact. Every step
    is a read; nothing is computed that was not already computed, no OCR runs,
    no model is called, and `compute` is never invoked because we go through the
    cache's typed getters rather than the memoizing wrappers.

    The markdown header carries the source FILENAME
    (`ocr/document.py:38-41`), so the filename is load-bearing for the hash and
    is read here. It never leaves this class: what a caller gets back is a
    payload and a hash.
    """

    def __init__(self, data_dir: str | Path):
        from webapp.artifact_cache import (  # imported lazily: telemetry must
            analysis_settings_key,            # not drag in webapp plumbing on
            ocr_settings_key,                 # `import telemetry` (T12).
            text_sha256,
        )

        self._text_sha256 = text_sha256
        self._root = Path(data_dir) / "artifacts"
        # sqlite3 direct, `mode=ro`, rather than `webapp.storage.Storage`:
        # constructing a Storage runs `_ensure_schema`, which WRITES (a
        # forward-only migration) to the store it opens. An observer that can
        # write to the thing it observes is not an observer.
        self._db = Path(data_dir) / "webapp.db"
        self._analysis_key = analysis_settings_key(parse_mode="deterministic")
        # Both offline partitions: `allow_local_ocr` is cache-key material and
        # the archive was read across tranches with it both on and off.
        self._ocr_keys = [
            ocr_settings_key(force_ocr=False, allow_local_ocr=True, allow_visual_ocr=False),
            ocr_settings_key(force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False),
            ocr_settings_key(force_ocr=True, allow_local_ocr=False, allow_visual_ocr=True),
        ]
        self._ocr_index: dict[str, dict[str, str]] = {}
        self._analysis_index: dict[str, str] = {}
        for settings_key, input_sha, path in self._rows("ocr"):
            self._ocr_index.setdefault(input_sha, {})[settings_key] = path
        for settings_key, input_sha, path in self._rows("analysis"):
            if settings_key == self._analysis_key:
                self._analysis_index[input_sha] = path

    def _rows(self, stage: str) -> list[tuple[str, str, str]]:
        import sqlite3

        uri = f"file:{self._db.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            return [
                (str(a), str(b), str(c))
                for a, b, c in conn.execute(
                    "SELECT settings_key, input_sha256, artifact_path "
                    "FROM artifact_cache WHERE stage = ?",
                    (stage,),
                )
            ]
        finally:
            conn.close()

    @property
    def analysis_settings_key(self) -> str:
        return self._analysis_key

    def _read(self, relative_path: str) -> dict[str, Any] | None:
        path = self._root / relative_path
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            # A missing or unreadable payload is a MISS, exactly as
            # `ArtifactCache.get` treats it. It degrades to
            # `check_unavailable`, never to a wrong answer.
            return None

    def payload_for(self, content_sha256: str, source_file: str) -> dict[str, Any] | None:
        """The cached analysis payload for one archive document, or None."""
        from ocr.document import StatementMarkdown

        for settings_key in self._ocr_keys:
            path = self._ocr_index.get(content_sha256, {}).get(settings_key)
            if not path:
                continue
            payload = self._read(path)
            if payload is None:
                continue
            document = (payload.get("artifact") or {}).get("document")
            if not isinstance(document, Mapping):
                continue
            markdown = StatementMarkdown(
                source_file=source_file,
                model=str(document.get("model") or ""),
                pages=list(document.get("pages") or []),
            ).to_markdown()
            analysis_path = self._analysis_index.get(self._text_sha256(markdown))
            if not analysis_path:
                continue
            analysis = self._read(analysis_path)
            if analysis is None:
                continue
            result = (analysis.get("artifact") or {}).get("analysis")
            return result if isinstance(result, dict) else None
        return None


def load_run_rows(run_dir: str | Path) -> list[dict[str, str]]:
    """The `rows.csv` of a discovery run, one row per document processed."""
    path = Path(run_dir) / "rows.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_corpus_status(audit_csv: str | Path, corpus_root: str | Path) -> dict[str, str]:
    """`content_sha256 -> PASS|WITHHELD` for the pinned 109.

    Hashes the pinned PDFs directly rather than trusting a name join: the
    corpus root is shared with untracked discovery material
    (`corpus_gate.py` docstring), so a path is not an identity and a hash is.
    """
    import hashlib

    root = Path(corpus_root)
    out: dict[str, str] = {}
    with Path(audit_csv).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            pdf = root / row["folder"] / row["statement"]
            if not pdf.is_file():
                continue
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest().upper()
            out[digest] = row.get("status") or ""
    return out


def observe_run(
    run_dir: str | Path,
    data_dir: str | Path,
    *,
    corpus_status: Mapping[str, str] | None = None,
    distinct: bool = True,
) -> list[tuple[dict[str, Any], Observation]]:
    """Every document of one discovery run, observed.

    `distinct=True` collapses the run's rows to DISTINCT documents by
    `content_sha256` — the archive contains the same bytes under several paths
    and counting one document twice would inflate every rate in the rollup.
    """
    join = _ArtifactJoin(data_dir)
    corpus_status = corpus_status or {}
    seen: set[str] = set()
    out: list[tuple[dict[str, Any], Observation]] = []
    for row in load_run_rows(run_dir):
        content_sha256 = row.get("content_sha256") or ""
        if distinct:
            if content_sha256 in seen:
                continue
            seen.add(content_sha256)
        parser_id = row.get("parser_id") or None
        context = {
            "content_sha256": content_sha256,
            "outcome_class": row.get("outcome_class") or "",
            "corpus_status": corpus_status.get(content_sha256),
        }
        payload = join.payload_for(content_sha256, Path(row.get("relative_path") or "").name)
        if payload is None:
            out.append((context, unavailable(parser_id, REASON_PAYLOAD_ABSENT)))
            continue
        out.append((context, evaluate(payload, parser_id=parser_id)))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="COUNTS-P1 stated-count observer (phase 1, observe only)."
    )
    parser.add_argument("--run", required=True, help="A discovery run directory (contains rows.csv).")
    parser.add_argument("--data-dir", required=True, help="The webapp data directory holding the D-3 artifact cache.")
    parser.add_argument("--corpus-audit", help="docs/adb-audit-results.csv - pins the 109.")
    parser.add_argument("--corpus-root", default="Bank Statements", help="Corpus root for --corpus-audit.")
    parser.add_argument("--all-rows", action="store_true", help="Do not collapse duplicate documents.")
    parser.add_argument("--json", action="store_true", help="Emit the rollup as JSON.")
    args = parser.parse_args(argv)

    corpus_status = (
        load_corpus_status(args.corpus_audit, args.corpus_root) if args.corpus_audit else None
    )
    observations = observe_run(
        args.run, args.data_dir, corpus_status=corpus_status, distinct=not args.all_rows
    )
    if not observations:
        print("no documents found in the run", file=sys.stderr)
        return 1
    summary = rollup(observations)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

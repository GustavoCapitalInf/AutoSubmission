"""The stated-count observer: a measuring instrument for the count check, observe only.

The platform extracts ``stated_credit_count`` / ``stated_debit_count`` from
parser modules and publishes them as ``Metrics.effective_num_deposits`` /
``effective_num_withdrawals`` (``metrics.compute_metrics``). ``reconcile``
compares them with the rows, and ``assess_document_integrity`` raises
``credit_count_mismatch`` / ``debit_count_mismatch``. This module measures that
comparison over already-cached artifacts.

**This module changes nothing.** Nothing here is imported by ``analysis/``,
``ocr/``, ``webapp/`` or ``discovery/``; no flag is emitted; no outcome class
moves; no payload is written. Its whole output is a statistic.

The per-bank semantics table is imported from ``analysis/count_semantics.py``,
the table the shipping integrity check reads, so the instrument that predicts
the flag population and the code that emits it cannot disagree. See
:data:`OBSERVER_VERSION`.

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

**Direction, not sign.** ``Transaction.direction`` (``analysis/schema.py``) is a
required field recording *the column the bank printed the row in*; the sign
records the money. ``metrics.compute_metrics`` counts ``t.amount >= 0`` as
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

# The count semantics table, imported from where the SHIPPING check reads it
# so the two can never disagree. `analysis/count_semantics` imports nothing
# but `dataclasses`, and `analysis/__init__.py` is empty, so this costs the
# T12 property nothing: `import telemetry.stated_counts` still pulls in no
# `webapp` module.
# Re-exported deliberately: this module's public surface is unchanged, so a
# caller that imported `SEMANTICS` or `semantics_for` from here still gets
# them — now resolved to the one table that decides the shipped flag.
from analysis.payload_shape import payload_accounts, refuse_document_payload
from analysis.count_semantics import (  # noqa: F401
    DIRECTIONS,
    SECTION_LEVEL_ORACLES,
    SEMANTICS,
    UNSURVEYED,
    CountSemantics as Semantics,
    expected_count,
    semantics_for,
)
from bank_statements import ENV_VAR, bank_statements_dir

#: Bump when the vocabulary, the evaluation order or the semantics table changes, so two measurement runs can be
#: told apart; see git log for history.
OBSERVER_VERSION = 6

# ----------------------------------------------------------------------
# the closed vocabulary
# ----------------------------------------------------------------------

MATCH = "match"
MISMATCH = "mismatch"
NOT_PRINTED = "not_printed"
SEMANTICS_INCOMPARABLE = "semantics_incomparable"
CHECK_UNAVAILABLE = "check_unavailable"

#: The owner's closed vocabulary, in its ruled order. Nothing
#: outside this tuple may ever be an observation's `result`.
RESULTS = (MATCH, MISMATCH, NOT_PRINTED, SEMANTICS_INCOMPARABLE, CHECK_UNAVAILABLE)

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
#: the parser extracted it (`Statement.stated_credit_count` / `stated_debit_count`).
EXPECTED_FIELDS = {
    "credit": ("statement", "stated_credit_count"),
    "debit": ("statement", "stated_debit_count"),
}

#: The ONLY fields the captured side is recomputed from, here, by us.
#: `Transaction.direction`: the printed column, not the sign of the money.
CAPTURED_FIELDS = ("statement", "transactions", "[]", "direction")

#: Never read. Named so the independence rule is checkable rather than
#: promised: these are where `metrics` COPIES the bank's printed count to
#: (`metrics.compute_metrics`), so sourcing the expected side
#: from any of them would let a parser satisfy the check with its own input.
FORBIDDEN_EXPECTED_SOURCES = (
    ("metrics", "effective_num_deposits"),
    ("metrics", "effective_num_withdrawals"),
    ("metrics", "num_deposits"),
    ("metrics", "num_withdrawals"),
    ("metrics", "total_posted_credit_count"),
)

#: An aggregate row, recognised by this word in its description as `pipeline.assess_quality` and `reconcile` read it:
#: one row stands for many postings by design, so the count check is structurally guaranteed to disagree and would
#: say nothing.
AGGREGATE_MARKER = "UNCAPTURED"

# ----------------------------------------------------------------------
# the per-bank count semantics table — imported, never copied
# ----------------------------------------------------------------------
#
# The table lives in `analysis/count_semantics.py`, where the SHIPPING
# integrity check reads it. It is imported at the top of this module
# rather than restated here: an observer that measures a copy of the rule is
# measuring the wrong thing the moment the copy drifts, and the value of this
# instrument is that its answer is the production answer.
#
# The dependency runs telemetry -> analysis and never the other way.
# `analysis/` still does not mention this module, and
# `tests/test_stated_counts.py::test_the_observer_is_not_wired_into_any_production_module`
# still proves it.



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
    #: `stated` put through this parser's declared mapping — the number the
    #: comparison actually used, equal to `stated` for every bank without one.
    #: Reported because on a mapped direction `stated != captured` is a `match`,
    #: and a record that showed only the two would read as a contradiction.
    expected: int | None = None
    captured: int | None = None
    captured_by_sign: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "result": self.result,
            "reason": self.reason,
            "stated": self.stated,
            "expected": self.expected,
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
    #: counts: they measure the populations the comparison refuses to compare.
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
       an integer the bank printed; the ±2% band `reconcile._coverage_mismatch`
       uses for money exists because OCR and rounding make money approximate,
       and neither applies to an integer. What is compared is the printed
       figure through this parser's declared mapping
       (``analysis.count_semantics.expected_count``, an identity for every bank
       that has none) — the SAME function the shipping check applies, for the
       same reason the table is imported rather than copied.

    Reversals are counted GROSS. `reconcile` nets
    settlement reversals out of the MONEY coverage because banks net them in
    printed totals; a reversal is nonetheless a printed row the bank counted,
    so netting it out of a COUNT would create the mismatch it was meant to
    remove.
    """
    if not isinstance(payload, Mapping):
        return _unavailable(parser_id, REASON_PAYLOAD_ABSENT)
    # A bank prints its counts per SECTION, so a count check answers about one
    # account. Measured (design §1.4), a document payload came back here as
    # `check_unavailable/statement_absent` — "this document printed no counts"
    # about a document whose every account printed them. `check_unavailable`
    # is for evidence that is genuinely unknowable, and a shape this function
    # was not taught is not that.
    refuse_document_payload(payload, surface="telemetry/stated_counts.py::evaluate")
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
        # `metrics.compute_metrics` reads `t.amount >= 0` as a deposit, so a
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
        # The expected side, through the SAME function production applies
        # (`analysis/count_semantics.expected_count`) and off the SAME payload
        # the parser filled — never `metrics`, never a captured row.
        expected = expected_count(parser_id, direction, stated, statement)
        observations[direction] = DirectionObservation(
            direction,
            MATCH if captured[direction] == expected else MISMATCH,
            REASON_COMPARED,
            stated=stated,
            expected=expected,
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


def evaluate_accounts(
    payload: Mapping[str, Any] | None,
    *,
    parser_id: str | None = None,
    formal_statement: bool = True,
) -> list[Observation]:
    """One :class:`Observation` per ACCOUNT, in printed order.

    A list rather than a fold, because a count check has no document-level
    meaning: two sections print two count pairs, and adding them would compare
    a sum the bank never printed against a total it never stated. A document
    payload therefore yields several observations and an account payload
    yields exactly one — the same one :func:`evaluate` returns for it, from the
    same call.
    """
    if payload is None or "accounts" not in payload:
        return [evaluate(payload, parser_id=parser_id,
                         formal_statement=formal_statement)]
    return [
        evaluate(account, parser_id=parser_id, formal_statement=formal_statement)
        for account in payload_accounts(
            payload, surface="telemetry/stated_counts.py::evaluate_accounts")
    ]


def _advisory(
    payload: Mapping[str, Any],
    statement: Mapping[str, Any],
    parser_id: str | None,
    captured: Mapping[str, int],
    rows: Sequence[Any],
) -> dict[str, Any]:
    """Sub-measurements that are NOT the vocabulary and never rolled into it.

    For the incomparable populations the vocabulary answer is deliberately
    silent, so the counterfactual is measured here and labelled as one: what
    the comparison WOULD have said, and, for BofA, what it would say under a
    `+ check_count` mapping, which no parser applies.
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
        # comparison keyed on `amount >= 0` (as `metrics.compute_metrics` counts)
        # instead of on `direction`, and count where the answer would flip.
        # `sign_false_mismatch` is the damage a sign-keyed check would do —
        # correct rows called wrong.
        for direction_obs in obs.directions():
            if direction_obs.result not in (MATCH, MISMATCH):
                continue
            # Against `expected`, not `stated`: the counterfactual changes ONE
            # thing — the key the captured side is counted on — so it must run
            # against the same expected side the real comparison used, or a
            # mapped direction would score every document as a sign difference.
            sign_result = (
                MATCH if direction_obs.captured_by_sign == direction_obs.expected else MISMATCH
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
    the ANALYSIS stage on `analysis_input_sha` — a digest over the ADMISSIBLE
    text of the markdown analyzed (the document with its `<!-- source: ... -->`
    header removed) AND over the intake page partition the analysis also reads.
    So the join is: PDF hash -> cached OCR artifact -> rebuild the
    `StatementMarkdown` -> `to_markdown()` + its page list -> analysis input
    hash -> cached analysis artifact. Every step is a read; nothing is computed
    that was not already computed, no OCR runs, no model is called, and
    `compute` is never invoked because we go through the cache's typed getters
    rather than the memoizing wrappers.

    The markdown header carries the source FILENAME (`StatementMarkdown.to_markdown`),
    and the filename is deliberately NOT load-bearing for the hash: the
    analysis stage keys on the admissible text, so a
    rename cannot change the answer and must not change the key either. This
    class MUST derive the hash exactly as the cache does, or the join silently
    misses every document and the instrument goes blind — failing safe
    (`REASON_PAYLOAD_ABSENT` on every row) while measuring nothing. That is why
    it IMPORTS `analysis_input_sha` instead of recomposing it. `source_file` is still passed in and stamped onto the
    reconstructed document, because `to_markdown()` requires one and the
    reconstruction must be faithful; it simply cannot reach the hash. It never
    leaves this class: what a caller gets back is a payload and a hash.

    After any change to the analysis input hash's material, expect ZERO
    resolutions until the next archive run re-analyzes: every stored artifact
    sits under the old key, so `observe_run` reports `REASON_PAYLOAD_ABSENT` on
    every row. It fails safe, and the tests cannot warn about it because they
    seed their own fixture through `cached_analysis`; only an empty rollup over
    the real archive shows it.

    **Artifact selection (OQ10).** OCR-side selection resolves through
    `telemetry/run_of_record.py`'s ONE selection policy: the `run_dir` this instance is built
    against supplies `RunPartitions` (recorded, or reconstructed and verified against THIS
    `data_dir`'s own cache index), `payload_for` resolves each document's OCR partition from
    ITS OWN row (`source_path` / `visual_rung` — never a preference walk), and the analysis
    filter uses the RUN's recorded analysis key rather than recomputing one from the current
    tree (a historical run's analysis key can differ from what this tree would compute today
    — the registry fingerprint alone rotates at nearly every wave).
    """

    def __init__(self, data_dir: str | Path, run_dir: str | Path):
        # Both imports are lazy: `telemetry` must not drag in webapp/discovery
        # plumbing on plain `import telemetry` (T12) — `run_of_record.py`
        # carries the same discipline for its own `discovery.runner` import.
        import sqlite3

        from telemetry.run_of_record import analysis_partition, partitions_for_run
        from webapp.artifact_cache import analysis_input_sha

        # THE analysis input hash, imported rather than recomposed: a private
        # copy would miss every document as soon as the key material changed,
        # and report `REASON_PAYLOAD_ABSENT` across the archive while looking
        # healthy.
        self._analysis_input_sha = analysis_input_sha
        self._root = Path(data_dir) / "artifacts"
        # sqlite3 direct, `mode=ro`, rather than `webapp.storage.Storage`:
        # constructing a Storage runs `_ensure_schema`, which WRITES (a
        # forward-only migration) to the store it opens. An observer that can
        # write to the thing it observes is not an observer. Kept open for
        # this instance's lifetime — `select_artifact` is now a per-document
        # indexed lookup (`idx_artifact_cache_input`), not a one-time full
        # scan, so there is no upfront index to build.
        self._conn = sqlite3.connect(f"file:{Path(data_dir).as_posix()}/webapp.db?mode=ro", uri=True)
        try:
            # Raises `telemetry.run_of_record.RunOfRecordError` on a malformed
            # record or an unverifiable reconstruction — propagated to the CLI
            # boundary (`main`), never guessed past. Closed here on that path
            # too: a `with _ArtifactJoin(...)` never reaches
            # `__enter__`/`__exit__` if the constructor itself raises.
            self.partitions = partitions_for_run(run_dir, conn=self._conn)
        except BaseException:
            self._conn.close()
            raise
        self._analysis_key = analysis_partition(self.partitions)

    def close(self) -> None:
        """Review the old `_rows()` opened and closed a connection PER CALL, in
        a `finally`; the per-document `select_artifact` design keeps ONE
        connection open for the instance's lifetime instead, and nothing
        released it. On Windows an unclosed `mode=ro` handle cannot corrupt the
        (read-only) cold caches, but it can hold a file handle open past a
        `tmp_path` fixture's teardown. Idempotent."""
        self._conn.close()

    def __enter__(self) -> "_ArtifactJoin":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

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

    def payload_for(
        self, content_sha256: str, source_file: str, row: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """The cached analysis payload for one archive document, or None.

        ``row`` is the document's OWN discovery-run row (at minimum
        ``source_path`` / ``visual_rung``) — REQUIRED, because the OCR
        partition it resolves to is a property of that row, never of a
        preference order this class declares. A row naming a partition this
        run's `RunPartitions` does not carry (e.g. `visual_rung="recovered"`
        on a run with no visual partition) resolves to ``None``, never to the
        offline partition or any other fallback.
        """
        from ocr.document import StatementMarkdown
        from telemetry.run_of_record import ocr_partition_for_row, select_artifact

        ocr_key = ocr_partition_for_row(row, self.partitions)
        ocr_path = select_artifact(self._conn, "ocr", content_sha256, ocr_key)
        if not ocr_path:
            return None
        payload = self._read(ocr_path)
        if payload is None:
            return None
        document = (payload.get("artifact") or {}).get("document")
        if not isinstance(document, Mapping):
            return None
        pages = list(document.get("pages") or [])
        markdown = StatementMarkdown(
            source_file=source_file,
            model=str(document.get("model") or ""),
            pages=pages,
        ).to_markdown()
        # The stage's own input hash, over BOTH halves of what the analysis
        # read: the filename-free text and the page partition. The
        # reconstruction supplies the same page list a wired production
        # caller supplied, which is why the join still resolves.
        analysis_path = select_artifact(
            self._conn, "analysis", self._analysis_input_sha(markdown, pages), self._analysis_key
        )
        if not analysis_path:
            return None
        analysis = self._read(analysis_path)
        if analysis is None:
            return None
        result = (analysis.get("artifact") or {}).get("analysis")
        return result if isinstance(result, dict) else None


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

    Raises `telemetry.run_of_record.RunOfRecordError` if `run_dir`'s partitions
    cannot be determined or a reconstruction does not verify against
    `data_dir`'s own cache index — never a guess; `main()` reports this as exit
    5.
    """
    corpus_status = corpus_status or {}
    seen: set[str] = set()
    out: list[tuple[dict[str, Any], Observation]] = []
    with _ArtifactJoin(data_dir, run_dir) as join:  # review closed on every exit
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
            payload = join.payload_for(content_sha256, Path(row.get("relative_path") or "").name, row)
            if payload is None:
                out.append((context, unavailable(parser_id, REASON_PAYLOAD_ABSENT)))
                continue
            # ONE observation per ACCOUNT, in printed order. `evaluate_accounts`
            # returns exactly `[evaluate(payload)]` for every payload this tree
            # publishes, so this loop is unchanged today — and it is the only entry
            # point the observer has, so wiring it here is what keeps the
            # renders-per-account reader reachable rather than written and unused.
            # Left on `evaluate`, this CLI would RAISE on
            # the first multi-account document instead of observing its accounts.
            for observation in evaluate_accounts(payload, parser_id=parser_id):
                out.append((context, observation))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="COUNTS-P1 stated-count observer (phase 1, observe only)."
    )
    parser.add_argument("--run", required=True, help="A discovery run directory (contains rows.csv).")
    parser.add_argument("--data-dir", required=True, help="The webapp data directory holding the D-3 artifact cache.")
    parser.add_argument("--corpus-audit", help="docs/adb-audit-results.csv - pins the 109.")
    parser.add_argument("--corpus-root", default=bank_statements_dir(), help=f"Corpus root for --corpus-audit (default: ${ENV_VAR}).")
    parser.add_argument("--all-rows", action="store_true", help="Do not collapse duplicate documents.")
    parser.add_argument("--json", action="store_true", help="Emit the rollup as JSON.")
    args = parser.parse_args(argv)
    if args.corpus_audit and args.corpus_root is None:
        parser.error(f"--corpus-audit needs --corpus-root or {ENV_VAR}")

    corpus_status = (
        load_corpus_status(args.corpus_audit, args.corpus_root) if args.corpus_audit else None
    )
    from telemetry.run_of_record import RunOfRecordError

    try:
        observations = observe_run(
            args.run, args.data_dir, corpus_status=corpus_status, distinct=not args.all_rows
        )
    except RunOfRecordError as exc:
        print(f"artifact-selection policy failed: {exc}", file=sys.stderr)
        return 5
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

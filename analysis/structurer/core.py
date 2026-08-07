"""The rung itself: source -> `Statement`, or a refusal with a reason.

Placement (W3-3b ruling 2): this is a **fallback on the unclaimed branch**. It
never competes with a parser. A registration that claimed a document on proven
issuer evidence keeps it, ambiguity still goes to review, and a crash is still
a crash. The rung runs only where the platform would otherwise have said
"nothing here recognises this document".

Publication rule (ruling 3): a structured `Statement` is returned **only if it
is grounded** — every transaction and every published summary figure located in
the source text, with span uniqueness, and a printed period. Ungrounded
candidates exist inside this module and never leave it. Reconciliation, ADB and
the approval gate then apply unchanged, so a published value has passed both
axes: it adds up, and it was printed.

Totality: `structure_unclaimed` never raises. The pipeline calls it directly,
and a structurer defect must not become the escaped-exception class that W3-1
just closed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..dates import assign_transaction_years
from ..schema import Statement, Transaction
from .geometry import DocumentGeometry
from .grounding import GroundingResult, ground_statement
from .rows import build_rows, source_lines_from_geometry, source_lines_from_text
from .summary import read_period, read_summary
from .tokens import document_year

__all__ = [
    "STRUCTURER_ENV",
    "STRUCTURER_MODEL",
    "StructureOutcome",
    "structure_document",
    "structure_unclaimed",
    "structurer_enabled",
]

#: Opt-in. Default OFF until Ocean flips it after measured validation
#: (W3-3b ruling 6). Absent or "0"/"false"/"" means the rung does not run, and
#: `analyze_markdown` behaves exactly as it does today.
STRUCTURER_ENV = "GENERIC_STRUCTURER_ENABLED"

#: What `Report.model_used` says when this rung produced the statement. The
#: `-deterministic` suffix is not decoration: telemetry treats that suffix as
#: "no model call" when costing a run (`telemetry/record.model_calls_for`), and
#: this rung makes none. The prefix keeps it distinguishable from every parser,
#: which is what lets coverage statistics separate "a parser claimed this" from
#: "the generic rung structured this".
STRUCTURER_MODEL = "generic-structurer-deterministic"

#: Summary figures a published statement must carry, and therefore must ground.
#: Beginning and ending balance only: they are what reconciliation's identity
#: and the ADB engine's opening/closing anchors are built on. Totals are read
#: when printed but are not required, because plenty of layouts do not print
#: them and the ledger identity does not need them.
PUBLISHED_SUMMARY_FIELDS = ("beginning_balance", "ending_balance")


def structurer_enabled() -> bool:
    return os.environ.get(STRUCTURER_ENV, "").strip().lower() not in ("", "0", "false", "no")


@dataclass(frozen=True)
class StructureOutcome:
    """What the rung concluded, including when it concluded nothing."""

    statement: Statement | None
    reason: str
    grounding: GroundingResult | None = None
    rows: int = 0
    row_lines: int = 0
    chained: bool = False
    chain_agreement: float = 0.0
    input_kind: str = "text"
    sign_sources: dict[str, int] = field(default_factory=dict)

    @property
    def publishable(self) -> bool:
        return self.statement is not None


def _outcome(reason: str, **fields) -> StructureOutcome:
    return StructureOutcome(statement=None, reason=reason, **fields)


def structure_document(
    markdown: str,
    *,
    geometry: DocumentGeometry | None = None,
    require_grounding: bool = True,
) -> StructureOutcome:
    """Structure one document. Diagnostic entry point — returns refusals too.

    `require_grounding=False` exists for the measurement harness, which needs
    to report how far ungrounded candidates get in order to say what grounding
    is actually rejecting. Production never passes it.
    """
    lines = source_lines_from_geometry(geometry) if geometry is not None else \
        source_lines_from_text(markdown)
    input_kind = "geometry" if geometry is not None else "text"
    if not lines:
        return _outcome("no_text", input_kind=input_kind)

    summary = read_summary(lines)
    period = read_period(lines, summary)
    default_year = int(period.end[:4]) if period else document_year([line.text for line in lines])

    row_set = build_rows(
        lines,
        default_year=default_year,
        opening_balance=summary["beginning_balance"].value if "beginning_balance" in summary else None,
    )
    common = {
        "rows": len(row_set.rows),
        "row_lines": row_set.seen_row_lines,
        "chained": row_set.chained,
        "chain_agreement": round(row_set.chain_agreement, 4),
        "input_kind": input_kind,
        "sign_sources": _sign_sources(row_set),
    }
    if not row_set.rows:
        return _outcome(row_set.reason, **common)
    if period is None:
        # The ADB engine divides by the period length; deriving one from the
        # first and last transaction would shorten every period whose opening
        # days had no activity, and quietly inflate the average.
        return _outcome("no_printed_period", **common)

    statement = Statement(
        bank=None,
        period_start=period.start,
        period_end=period.end,
        transactions=[
            Transaction(
                date=row.date,
                description=row.description,
                amount=row.amount,
                direction=row.direction,
                running_balance=row.running_balance,
            )
            for row in sorted(row_set.rows, key=lambda row: (row.date, row.line_index))
        ],
        **{name: value.value for name, value in summary.items()},
    )
    # Row dates carry one year; a period that crosses a year boundary makes some
    # of them wrong. The platform already owns that correction, so it runs here
    # BEFORE grounding rather than after — a date grounding accepted must be the
    # date that ships.
    statement = assign_transaction_years(statement)

    # The rows must belong to the period we just read. A row outside it means
    # one of the two is wrong — the period was mis-read, or the file holds more
    # than one statement — and both are reasons to say nothing rather than to
    # publish a ledger the ADB engine will integrate over the wrong window.
    outside = [
        transaction.date for transaction in statement.transactions
        if not (period.start <= transaction.date <= period.end)
    ]
    if outside:
        return _outcome("period_excludes_rows", **common)

    # The ledger must reach the closing balance the document itself prints.
    # Reconciliation would catch this downstream and withhold — but a rung that
    # can check its own completeness before speaking should, because "some of
    # the rows" is not a weaker statement than the truth, it is a different
    # and false one. This is what makes "published implies the ledger identity
    # holds" an invariant of the subsystem rather than a downstream accident.
    if statement.beginning_balance is not None and statement.ending_balance is not None:
        reached = round(statement.beginning_balance + sum(t.amount for t in statement.transactions), 2)
        if abs(reached - statement.ending_balance) > 0.02:
            return _outcome("ledger_incomplete", **common)

    grounding = ground_statement(
        row_set.rows,
        summary,
        period,
        markdown,
        published_fields=PUBLISHED_SUMMARY_FIELDS,
    )
    if require_grounding and not grounding.ok:
        return _outcome("ungrounded", grounding=grounding, **common)

    return StructureOutcome(statement=statement, reason="structured", grounding=grounding, **common)


def _sign_sources(row_set) -> dict[str, int]:
    tally: dict[str, int] = {}
    for row in row_set.rows:
        tally[row.sign_source] = tally.get(row.sign_source, 0) + 1
    return tally


def structure_unclaimed(
    markdown: str, *, geometry: DocumentGeometry | None = None
) -> Statement | None:
    """The pipeline's entire view of this subsystem: a `Statement`, or None.

    None means "no opinion" and the caller proceeds exactly as it does today.
    Every refusal reason, every ungrounded candidate and every diagnostic stays
    inside this module: the orchestrator gains one call and no vocabulary.

    Never raises, including on a defect of its own — a structurer exception is
    a refusal, not an escaped exception (W3-1).
    """
    if not structurer_enabled():
        return None
    try:
        return structure_document(markdown, geometry=geometry).statement
    except Exception:
        return None

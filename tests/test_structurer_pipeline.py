"""The pipeline seam for the generic rung — APPROVED and landed.

`analysis/pipeline.py` is a protected file and this wave's protocol is
propose-first (W3-1b set the precedent and the idiom). The diff below was
pinned here as strict xfails while it awaited Ocean; it was approved on
2026-08-07 as pinned, and the xfails are now plain assertions.

The diff, in full, as landed:

    --- a/analysis/pipeline.py
    +++ b/analysis/pipeline.py
    @@ imports
    +from .structurer import STRUCTURER_MODEL, structure_unclaimed
    @@
     def analyze_markdown(markdown: str, *, settings: Settings | None = None,
                          parse_mode: str = "auto",
    +                     document_geometry: object | None = None,
                          on_dispatch: Callable[[Dispatch], None] | None = None) -> Report:
    @@
         deterministic_stmt = dispatch.statement
    +    # W3-3c: the generic rung is a fallback on the UNCLAIMED branch. It never
    +    # competes with a claiming parser, and it is not reached for `ambiguous`
    +    # or `parser_exception`, which have their own fail-closed outcomes.
    +    structured_stmt = (
    +        structure_unclaimed(markdown, geometry=document_geometry)
    +        if deterministic_stmt is None and dispatch.outcome == "unclaimed"
    +        else None
    +    )
         if deterministic_stmt is not None:
             stmt = apply_statement_repairs(
                 markdown, normalize_statement(deterministic_stmt), dispatch=dispatch
             )
             bank_label = (stmt.bank or "bank").lower().replace(" ", "-")
             model_used = f"{bank_label}-deterministic"
    +    elif structured_stmt is not None:
    +        stmt = normalize_statement(structured_stmt)
    +        model_used = STRUCTURER_MODEL
         else:
             ... unchanged ...

Six added lines, one import, one optional keyword, and no re-indentation of
existing code. `apply_statement_repairs` is deliberately NOT applied to the
structured statement: its repairs are bank-specific, the rung runs precisely
where no bank was identified, and the year correction the structurer needs
(`assign_transaction_years`) has already run inside the subsystem — before
grounding, so that the date grounding accepted is the date that ships.

Notes for the review:

* `document_geometry` is inert for every existing caller (default None), so
  the corpus proof holds by construction. Wiring callers that hold the PDF
  bytes (webapp worker, discovery runner) is a separate, coordinated change —
  `discovery/` is HARBOR's file.
* `model_used` ends in `-deterministic` because it IS deterministic and makes
  no model call, which is what `telemetry.record.model_calls_for` reads that
  suffix to mean. The `generic-structurer-` prefix keeps it distinguishable
  from every parser, so coverage statistics never conflate "a parser claimed
  this" with "the generic rung structured this" — no telemetry change needed.
"""
from __future__ import annotations

import pytest

from analysis.pipeline import analyze_markdown
from analysis.structurer import STRUCTURER_MODEL

# A document no registration claims, that the structurer can read.
UNCLAIMED = """--- Page 1 ---
NORTHWIND MUTUAL BANK
Statement period 03/01/2026 to 03/31/2026
Beginning balance 5,000.00
Ending balance 5,090.00
Date Description Amount Balance
03/02 ORCHARD SUPPLY CO 150.00 4,850.00
03/05 CUSTOMER DEPOSIT ZEPHYR 900.00 5,750.00
03/09 TOLL BRIDGE AUTHORITY 60.00 5,690.00
03/14 QUARRY FREIGHT LLC 400.00 5,290.00
03/21 CUSTOMER DEPOSIT MARLIN 300.00 5,590.00
03/28 UTILITY DISTRICT 12 500.00 5,090.00
"""


@pytest.fixture
def rung_on(monkeypatch):
    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "1")


# ---------------------------------------------------------------------------
# The guarantees that hold on both sides of the diff
# ---------------------------------------------------------------------------

def test_the_document_is_genuinely_unclaimed():
    """Everything below is meaningless if a parser claims this document."""
    from analysis.parser_registry import resolve

    assert resolve(UNCLAIMED).outcome == "unclaimed"


def test_with_the_rung_off_the_pipeline_refuses_exactly_as_before(monkeypatch):
    """Ruling 6: default off. The platform's behaviour is unchanged until
    Ocean flips the opt-in after measured validation."""
    monkeypatch.delenv("GENERIC_STRUCTURER_ENABLED", raising=False)

    with pytest.raises(RuntimeError, match="no deterministic parser matched"):
        analyze_markdown(UNCLAIMED, parse_mode="deterministic")


def test_a_claimed_document_never_reaches_the_rung(rung_on):
    """Ruling 2: proven issuer-evidence registrations retain precedence. The
    rung expands capability where identification failed; it never competes."""
    from analysis.parser_registry import resolve
    from tests.test_telemetry import claimed_markdown

    markdown = claimed_markdown()
    assert resolve(markdown).outcome == "claimed"

    report = analyze_markdown(markdown, parse_mode="deterministic")
    assert report.model_used.endswith("-deterministic")
    assert not report.model_used.startswith("generic-structurer")


# ---------------------------------------------------------------------------
# The rung itself
# ---------------------------------------------------------------------------

def test_the_rung_structures_an_unclaimed_document_in_deterministic_mode(rung_on):
    report = analyze_markdown(UNCLAIMED, parse_mode="deterministic")

    assert report.model_used == STRUCTURER_MODEL
    assert len(report.statement.transactions) == 6
    assert report.reconciliation.ok


def test_the_pipeline_accepts_word_geometry_for_the_rung(rung_on):
    """The geometry input the 3a measurement identified as the primary lever
    reaches the structurer through one optional, inert keyword."""
    report = analyze_markdown(UNCLAIMED, parse_mode="deterministic", document_geometry=None)

    assert report.model_used == STRUCTURER_MODEL


def test_a_crashed_document_is_not_rescued_by_the_rung(rung_on):
    """Only the unclaimed branch. A crash is a defect of ours, and structuring
    the document instead would bury the finding under a plausible-looking
    answer. True today (the rung is not wired) and required to stay true after
    the diff lands, which is why it is an assertion rather than an xfail: the
    `dispatch.outcome == "unclaimed"` condition in the proposed diff is exactly
    what this protects."""
    from analysis import parser_registry as pr

    def explode(markdown: str):
        raise AttributeError("'NoneType' object has no attribute 'group'")

    registration = pr.register(pr.Registration(
        id="_structurer_precedence_probe",
        bank="Structurer Precedence Probe",
        markers=(pr.required("probe", lambda t: "NORTHWIND MUTUAL BANK" in t),),
        parse=explode,
    ))
    try:
        with pytest.raises(pr.ParserCrashError):
            analyze_markdown(UNCLAIMED, parse_mode="deterministic")
    finally:
        pr._REGISTRY.pop(registration.id, None)

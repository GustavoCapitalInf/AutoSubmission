"""REPAIR-GUARD (W3 §MG-C2 D1 / §REPAIR-GUARD / §PIPE5).

`apply_statement_repairs` runs AFTER dispatch, so it stood outside the seam
`parser_registry` states the law for: "no code path from `resolve` through
`parse` raises", every crash reduced to a `ParserFailure` carrying the
exception's CLASS NAME and never its message. A repair that raised propagated
out of `analyze_markdown` as a bare exception, and `webapp/worker.py` stores
`str(exc)` as the durable job error — so the fragment of the document the
exception quoted landed in the job store and in front of a user.

These tests pin the seam, not any one repair: what happens when a repair
raises, whatever it is and whatever it says.
"""
from __future__ import annotations

import json

import pytest

from analysis.parser_registry import Dispatch, Marker, Registration
from analysis.pipeline import analyze_markdown, assess_document_integrity
from analysis.schema import Statement, Transaction
from analysis.serialization import report_to_dict
from telemetry.diagnostics import (
    ADVISORY_CODES,
    CLASS_OF,
    INTEGRITY_FLAGS,
    VOCABULARY,
    diagnose,
)
from telemetry.record import classify_outcome

#: The fragment of the document a repair's exception message would quote. An
#: account-shaped token, because that is the shape MG-C2 measured escaping.
PROVOKING_TOKEN = "4021-9987-3315-0042"

MARKDOWN = f"""<!-- source: seam.pdf | pages: 1 | model: native -->

--- Page 1 ---
ACCOUNT {PROVOKING_TOKEN}
Beginning Balance 1,000.00
02/03 CARD PURCHASE 100.00 900.00
Ending Balance 900.00
"""


def _statement() -> Statement:
    return Statement(
        bank="Seam Bank",
        # `period_start`/`period_end` are the real field names. The first draft
        # of this fixture wrote `statement_period_*`, which pydantic silently
        # DROPPED (the model does not forbid extras), so the fixture carried no
        # period at all and the tests still passed. W3 §PIPE5 D6.
        period_start="2054-02-01",
        period_end="2054-02-28",
        beginning_balance=1000.0,
        ending_balance=900.0,
        transactions=[
            Transaction(
                date="2054-02-03",
                description="CARD PURCHASE",
                amount=-100.0,
                direction="debit",
                running_balance=900.0,
            )
        ],
    )


def _claimed(statement: Statement, parser_id: str = "seam_parser") -> Dispatch:
    """A claiming `Dispatch`, built directly so the live registry is untouched."""
    registration = Registration(
        id=parser_id,
        bank=statement.bank or "Seam Bank",
        markers=(Marker("m", lambda text: True),),
        parse=lambda markdown: None,
    )
    return Dispatch("claimed", registration=registration, statement=statement)


@pytest.fixture
def raising_repair(monkeypatch):
    """One step of the repair stage raises, with the document in its message.

    `repair_first_community_posted_activity` stands in for the five steps the
    stage runs — the point is the SEAM, so which one raises is deliberately
    not part of the property under test. (It was the B1 repair until the
    audit of 2026-10-13 keyed that one on its own registration, PARSERS-1: it
    no longer runs for this fixture's claiming parser. The First Community
    repair is still called for every statement and reads its label inside.)
    """
    def boom(stmt):
        raise ValueError(f"invalid literal for int(): {PROVOKING_TOKEN}")

    monkeypatch.setattr("analysis.pipeline.repair_first_community_posted_activity", boom)


@pytest.fixture
def claimed(monkeypatch):
    statement = _statement()
    monkeypatch.setattr("analysis.pipeline.resolve", lambda markdown: _claimed(statement))
    return statement


def test_a_raising_repair_does_not_escape_the_pipeline(claimed, raising_repair):
    """The whole card, in one line: it returns instead of raising."""
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert report.statement is not None


def test_the_unrepaired_statement_stands(claimed, raising_repair):
    """A repair that raises produced nothing, exactly as a crashing `parse`
    does. The published statement is what this branch published before repairs
    existed — not a partially-repaired one, and not a refusal."""
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert report.statement.beginning_balance == 1000.0
    assert report.statement.ending_balance == 900.0
    assert [t.description for t in report.statement.transactions] == ["CARD PURCHASE"]


def test_the_crash_is_flagged_and_routed_to_review(claimed, raising_repair):
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert "repair_exception" in report.integrity.flags
    assert report.integrity.risk_level == "review"
    # Not a document-integrity finding: the document did not contradict itself,
    # our code broke. `possible_document_issue` is the fraud-adjacent signal and
    # a crash of ours must never raise it.
    assert report.integrity.possible_document_issue is False


def test_the_note_names_the_exception_class_and_nothing_else(claimed, raising_repair):
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    note = next(n for n in report.integrity.notes if "repair stage raised" in n)
    assert "ValueError" in note
    assert PROVOKING_TOKEN not in note
    assert "invalid literal" not in note


def test_the_note_names_the_STAGE_and_not_one_repair(claimed, raising_repair):
    """W3 §PIPE5 D3. The stage is twelve steps and only ONE is a bank-summary
    repair, so a note saying "a bank-summary repair raised" misdescribes the
    other eleven — and is flatly wrong when the raise came AFTER the
    bank-summary repair had already succeeded and is being discarded with the
    rest. The note must name the stage and say the discard was total."""
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    note = next(n for n in report.integrity.notes if "repair stage raised" in n)
    assert "statement-repair stage" in note
    assert "discarded whole" in note
    assert "bank-summary" not in note


def test_the_message_is_nowhere_in_the_serialized_payload(claimed, raising_repair):
    """The invariant the card exists for (H3_SCHEMA I1). The exception message
    quoted the account number; the published report must not carry it, in any
    field, at any depth."""
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    blob = json.dumps(report_to_dict(report))
    assert PROVOKING_TOKEN not in blob
    assert "invalid literal" not in blob


def test_a_repair_that_does_not_raise_is_unflagged(claimed):
    """The control half: without a crash the flag is absent, so this cell
    cannot put `repair_exception` on a document whose repairs all ran."""
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert "repair_exception" not in report.integrity.flags
    assert report.integrity.risk_level == "clear"


def test_the_flag_is_off_by_default_for_every_other_caller():
    """`repair_failure` defaults to None, so every existing call site of
    `assess_document_integrity` is byte-identical."""
    from analysis.pipeline import Quality
    from analysis.reconcile import reconcile

    stmt = _statement()
    recon = reconcile(stmt)
    quality = Quality(
        level="transaction_level",
        transaction_detail_reliable=True,
        summary_totals_reliable=True,
        corporate_use="approved",
    )
    without = assess_document_integrity(stmt, recon, quality)
    explicit = assess_document_integrity(stmt, recon, quality, repair_failure=None)
    assert without == explicit
    assert "repair_exception" not in without.flags


def test_the_discard_publishes_uncorrected_dates_on_a_year_boundary(monkeypatch):
    """W3 §PIPE5 D4 — the consequence the first wording hid, measured.

    `assign_transaction_years` is INSIDE the discarded stage. On a statement
    whose period crosses a year boundary the parser stamps one year on every
    `MM/DD` row and that step is what re-derives it, so discarding the stage
    publishes WRONG TRANSACTION DATES — not merely uncorrected summary figures.
    Dates feed the dated ledger, the daily-balance series and the ADB, so this
    is a strictly larger blast radius than the summary, and it is pinned here
    so the trade is measured rather than asserted.

    It remains the right trade: the alternatives are a half-repaired statement
    nobody can characterise, or an escaped exception carrying the document's
    text into the durable job store. The discard is the only fail-closed
    option, and it is never silent — the flag routes the document to review.
    """
    december = Statement(
        bank="Seam Bank",
        period_start="2053-12-01",
        period_end="2054-01-31",
        beginning_balance=1000.0,
        ending_balance=900.0,
        transactions=[
            # The parser stamped the period-START year on both rows, which is
            # exactly the defect `assign_transaction_years` exists to repair.
            Transaction(date="2053-12-15", description="DECEMBER ROW",
                        amount=-40.0, direction="debit", running_balance=960.0),
            Transaction(date="2053-01-09", description="JANUARY ROW",
                        amount=-60.0, direction="debit", running_balance=900.0),
        ],
    )
    monkeypatch.setattr(
        "analysis.pipeline.resolve", lambda markdown: _claimed(december)
    )

    # Control: the stage runs, and the January row's year is corrected.
    healthy = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert [t.date for t in healthy.statement.transactions] == [
        "2053-12-15", "2054-01-09"
    ]
    assert "repair_exception" not in healthy.integrity.flags

    # Discard: the correction is lost with the rest of the stage, and the
    # WRONG date is what gets published.
    def boom(stmt):
        raise ValueError(f"invalid literal for int(): {PROVOKING_TOKEN}")

    monkeypatch.setattr("analysis.pipeline.repair_first_community_posted_activity", boom)
    discarded = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert [t.date for t in discarded.statement.transactions] == [
        "2053-12-15", "2053-01-09"   # ← the January row keeps the wrong year
    ]
    # ...and the document is not published as clear: a human sees it.
    assert "repair_exception" in discarded.integrity.flags
    assert discarded.integrity.risk_level == "review"


def test_the_flag_does_not_by_itself_block_corporate_approval(claimed, raising_repair):
    """Recorded, not changed (W3 §PIPE5 D-followups).

    `quality.corporate_use` is computed from reconciliation, not from the
    integrity flags, so a document whose repair stage crashed can still read
    `approved` in `quality` while `integrity.risk_level` says `review`. That
    asymmetry is PRE-EXISTING and symmetric — `parser_exception` and
    `integrity_check_exception` behave identically — and the published outcome
    is still `review`, because `classify_outcome` reads the flags. Pinned here
    so the behaviour is a recorded property rather than a surprise; changing it
    would be a decision about every crash flag, not about this one.
    """
    report = analyze_markdown(MARKDOWN, parse_mode="deterministic")
    assert "repair_exception" in report.integrity.flags
    assert report.quality.corporate_use == "approved"
    assert classify_outcome(report_to_dict(report))[0] == "review"


def test_the_flag_is_a_registered_diagnosable_code():
    """The vocabulary is closed (`telemetry/diagnostics.py`), so a flag the
    pipeline can raise and the taxonomy has never heard of is a defect."""
    assert "repair_exception" in INTEGRITY_FLAGS
    assert CLASS_OF["integrity:repair_exception"] == "extraction_failure"


def test_a_swallowed_repair_outranks_the_financial_classes_it_can_cause():
    """A repair rewrites published balances and stated totals, so a ledger or
    summary finding taken on the UNREPAIRED figures may be the crash's symptom.
    The primary class must name the crash, not the symptom."""
    payload = {
        "metrics": {"adb": {"validations": {}, "warnings": []}},
        "reconciliation": {"issues": ["sum check off by 250.00"]},
        "integrity": {"flags": ["repair_exception", "ledger_sum_mismatch"]},
        "statement": {},
    }
    result = diagnose(payload, "withheld")
    assert "integrity:repair_exception" in result["codes"]
    assert result["primary_class"] == "extraction_failure"


def test_the_diagnostics_version_moves_when_the_vocabulary_does():
    """W3 §PIPE5 D1, mirroring COUNTS-P3's `OBSERVER_VERSION` guard.

    `DIAGNOSTICS_VERSION`'s own contract is "bumped when a code is added,
    removed or re-classed", and it travels in every record so a rollup over
    mixed runs can tell which vocabulary produced a row. Nothing enforced it:
    this cell added `integrity:repair_exception` and left the version at 3,
    which is the same omission COUNTS-P2 made one wave earlier and the reason
    COUNTS-P3 built this guard for the observer table.

    Pinning the version against the vocabulary's SHAPE makes the contract
    self-enforcing. Adding, removing or re-classing a code fails here until
    the version is deliberately moved and its comment says what moved — which
    matters most when the new code fires on zero documents, because then the
    version is the ONLY observable difference between two rollups.
    """
    import telemetry.diagnostics as diagnostics

    # v5 — P22-TRUTHTABLE (Phase 2.2), the fence cell's consequence. NO code
    # was added, removed or re-classed: the four vocabulary sizes are
    # unchanged, and the version moved because the set of codes a LIVE
    # analysis can still PRODUCE shrank (the escalation-extraction writer was
    # removed by R9, so its anchor can never fire again while staying in the
    # vocabulary for the records that already carry it). That is precisely
    # the case this guard's docstring calls out — the new state fires on zero
    # documents, so the version is the only observable difference between a
    # v4 rollup and a v5 one. See `W3_2_TAXONOMY.md` §11 v5.
    #
    # v6 - the owner report of 2026-10-08 (Capital One daily ledger): ONE
    # advisory code added, `adb_state:pre_period_carry_in_folded`, the
    # disclosure the engine writes when it folds a parser-declared
    # previous-balance-day carry-in into the opening balance. Vocabulary
    # 60 -> 61 and advisory 7 -> 8; nothing re-classed, CLASS_OF unchanged.
    # See `W3_2_TAXONOMY.md` §11 v6.
    assert (
        diagnostics.DIAGNOSTICS_VERSION,
        len(VOCABULARY),
        len(CLASS_OF),
        len(ADVISORY_CODES),
        len(diagnostics.DIAGNOSABLE_CLASSES),
    ) == (6, 61, 53, 8, 2)
    # 60/7, not 59/6: the batch-5 train composed TWO vocabulary changes into
    # the one v4 bump — this cell's `integrity:repair_exception` and
    # ADB-SPLIT's advisory `adb_state:initialization_event_folded` — the same
    # composed-bump policy ANALYSIS_STAGE_VERSION follows at every train.


def test_the_new_label_cannot_collide_with_a_hyphenated_bank_label():
    """W3 §PIPE5 D5. MODEL-LABEL publishes `<registration.id>-deterministic`
    for a bank=None publisher, while every other document publishes
    `<hyphenated bank label>-deterministic`. Eleven hyphenated labels in the
    live registry are also parser ids (`chase`, `bmo`, `truist`, `cibc`, …),
    so a bank=None publisher whose id landed on one of them would re-create
    the exact ambiguity this hunk removed — two parsers under one label.

    None of today's four bank=None publishers collides. This forbids the
    fifth. LIMITATION, stated rather than hidden: the four are pinned by name
    because "publishes bank=None" cannot be decided statically
    (`core_processor_sectioned` decides it per document), so a NEW bank=None
    parser must be added to this list — the guard catches a rename, not an
    unlisted newcomer.
    """
    from analysis import parser_registry_entries  # noqa: F401 - populates registry
    from analysis.parser_registry import registrations

    bank_none_publishers = {
        "releve_facturation",
        "balance_by_date",
        "core_processor_sectioned",
        "community_section",
    }
    live = list(registrations())
    known = {registration.id for registration in live}
    assert bank_none_publishers <= known, "a pinned bank=None publisher was renamed"

    hyphenated = {
        (registration.bank or "bank").lower().replace(" ", "-")
        for registration in live
    }
    collisions = sorted(bank_none_publishers & hyphenated)
    assert not collisions, (
        f"{collisions} would publish a label indistinguishable from a "
        "bank-labelled document's; rename the parser or key the label "
        "differently"
    )


def test_classify_outcome_routes_the_flag_to_review():
    """No change was needed in `classify_outcome`: any integrity flag is a
    review cause already. Pinned so a later precedence edit cannot silently
    drop a crashed repair back into `validated`."""
    payload = {
        "metrics": {"average_daily_balance": 950.0},
        "quality": {"corporate_use": "approved"},
        "integrity": {"flags": ["repair_exception"]},
    }
    assert classify_outcome(payload) == ("review", "integrity_flags")

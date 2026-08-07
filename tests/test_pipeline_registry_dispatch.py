"""The pipeline's registry seam: bank knowledge, LLM-path coverage, ambiguity.

R-3.4 removed the last bank-name literals from `analysis/pipeline.py`. Two of
them guarded real behaviour:

* `stmt.bank == "Chase Transaction Export"` forced review and flagged the
  document as not a formal statement;
* `(stmt.bank or "").upper() != "BMO"` gated a second-summary contradiction
  check.

Both now come from registration data. The registration-based path is the
primary one, but the literals also fired for a statement the LLM extracted and
labelled with that bank, and Ocean's ruling is that nothing narrows: today's
semantics must remain a strict subset of the new behaviour. `by_bank_label`
provides the fallback, and the tests below are the ones that would catch its
removal.
"""
from __future__ import annotations

import pytest

from analysis import parser_registry as pr
from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis.pipeline import (
    _registration_for,
    assess_document_integrity,
    assess_quality,
)
from analysis.reconcile import reconcile
from analysis.schema import Statement, Transaction


def statement(bank: str, **kwargs) -> Statement:
    return Statement(bank=bank, **kwargs)


def recon_for(stmt: Statement):
    return reconcile(stmt)


# ---------------------------------------------------------------------------
# Registration lookup
# ---------------------------------------------------------------------------

def test_a_claimed_document_uses_its_claiming_registration():
    dispatch = pr.Dispatch("claimed", registration=pr.by_id("chase_export"))
    assert _registration_for(statement("anything"), dispatch).id == "chase_export"


def test_an_unclaimed_document_falls_back_to_the_bank_label():
    """The LLM path: no registration claimed, but the extractor named a bank we
    know. That statement keeps the bank's document knowledge."""
    assert _registration_for(statement("BMO"), None).id == "bmo"
    assert _registration_for(statement("Chase Transaction Export"), None).id == "chase_export"


def test_an_unknown_bank_label_yields_no_registration():
    assert _registration_for(statement("Bank Of Nowhere"), None) is None
    assert _registration_for(statement(None), None) is None


# ---------------------------------------------------------------------------
# Ocean ruling 2: LLM-path coverage is kept, not narrowed
# ---------------------------------------------------------------------------

def test_llm_extracted_chase_export_is_still_flagged_and_routed_to_review():
    """No registration claimed it; the extractor labelled it. Pre-R-3 the
    `stmt.bank` literal caught this, and it still must."""
    stmt = statement("Chase Transaction Export")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=None)
    assert quality.level == "needs_review"
    assert quality.corporate_use == "manual_review_required"
    assert any("transaction export" in note for note in quality.notes)

    integrity = assess_document_integrity(stmt, recon, quality, markdown="x", dispatch=None)
    assert "not_a_formal_statement" in integrity.flags


def test_llm_extracted_bmo_still_runs_the_summary_contradiction_check():
    """The BMO check used to be gated on the bank label. It is now registered
    to the BMO parser, and an LLM-labelled BMO statement must still get it."""
    markdown = (
        "BMO Account Summary Totals Total Deposits $ 999.00 Total Withdrawals $ 0.00 "
        "Final Balance $ 100.00 Important Information"
    )
    stmt = statement(
        "BMO",
        beginning_balance=100.0,
        ending_balance=200.0,
        stated_total_credits=50.0,
        transactions=[
            Transaction(date="2026-01-05", description="DEP", amount=100.0, direction="credit")
        ],
    )
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=None)
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown, dispatch=None)
    assert "conflicting_statement_summaries" in integrity.flags, (
        "the BMO contradiction check did not run on an LLM-extracted BMO statement"
    )


def test_the_bmo_check_does_not_run_for_another_bank():
    """It is registered to BMO, so a Chase statement never sees it — which is
    what removing the bank literal was for."""
    markdown = (
        "Account Summary Totals Total Deposits $ 999.00 Total Withdrawals $ 0.00 "
        "Final Balance $ 100.00"
    )
    stmt = statement("Chase", beginning_balance=100.0, ending_balance=200.0, stated_total_credits=50.0)
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=None)
    integrity = assess_document_integrity(stmt, recon, quality, markdown=markdown, dispatch=None)
    assert "conflicting_statement_summaries" not in integrity.flags


def test_a_formal_statement_is_not_flagged():
    stmt = statement("Chase")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=None)
    integrity = assess_document_integrity(stmt, recon, quality, markdown="x", dispatch=None)
    assert "not_a_formal_statement" not in integrity.flags


def test_only_the_export_registration_is_informal():
    informal = [reg.id for reg in pr.registrations() if not reg.formal_statement]
    assert informal == ["chase_export"]


# ---------------------------------------------------------------------------
# Ambiguity surfacing
# ---------------------------------------------------------------------------

def test_an_ambiguous_dispatch_is_flagged_and_names_its_candidates():
    dispatch = pr.Dispatch("ambiguous", candidates=(("bank_a", 0.5), ("bank_b", 0.5)))
    stmt = statement("Bank Of Nowhere")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=dispatch)
    integrity = assess_document_integrity(stmt, recon, quality, markdown="x", dispatch=dispatch)
    assert "parser_ambiguous" in integrity.flags
    note = next(n for n in integrity.notes if "more than one deterministic parser" in n)
    assert "bank_a" in note and "bank_b" in note
    assert "guesswork" in note


def test_deterministic_mode_refuses_an_ambiguous_document():
    from analysis.pipeline import analyze_markdown

    original = pr._REGISTRY.copy()
    try:
        pr.clear_registry()
        for name in ("bank_a", "bank_b"):
            pr.register(
                pr.Registration(
                    id=name,
                    bank=name,
                    markers=(pr.required("shared", lambda t: "SHARED PHRASE" in t),),
                    parse=lambda md, _n=name: Statement(bank=_n),
                )
            )
        with pytest.raises(pr.AmbiguousParserError) as excinfo:
            analyze_markdown("SHARED PHRASE", parse_mode="deterministic")
        assert {name for name, _score in excinfo.value.candidates} == {"bank_a", "bank_b"}
    finally:
        pr.clear_registry()
        pr._REGISTRY.update(original)


def test_deterministic_mode_still_refuses_an_unclaimed_document():
    from analysis.pipeline import analyze_markdown

    with pytest.raises(RuntimeError, match="no deterministic parser matched"):
        analyze_markdown("a lease agreement, not a bank statement", parse_mode="deterministic")


def test_pipeline_names_no_bank(tmp_path):
    """The acceptance criterion: adding a parser touches zero orchestrator code."""
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "analysis" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    banks = [reg.bank for reg in pr.registrations()]
    offenders = [bank for bank in banks if bank in source]
    assert not offenders, f"analysis/pipeline.py still names banks: {offenders}"
    assert "_deterministic_statement" not in source
    assert not re.search(r"parse_\w+_statement", source), "pipeline still imports parser functions"




# ---------------------------------------------------------------------------
# Crash surfacing (W3-1b) — Ocean-approved pipeline diff, 2026-08-07
# ---------------------------------------------------------------------------
#
# The W3-1 registry boundary stops a parser crash escaping `resolve()`. What it
# cannot do from inside the registry is tell the pipeline to route the document
# to a human, and on the `auto` path that mattered: before the boundary a crash
# surfaced as "no analysis, here is the error", and after it the document fell
# through to LLM extraction with nothing recording that a parser we DO have for
# this bank broke on it. A worker-side check could not close that — the D-3
# cache stores the analysis payload, so the fact has to be IN the payload.
#
# Two of the tests below were the strict xfails that pinned the proposal while
# it awaited Ocean; they are now plain assertions, joined by three more that
# cover the extension Ocean approved with it. Two surfaces, three states:
#
#   parser_exception          — nothing produced a statement because something
#                               raised (auto: flag + review; deterministic:
#                               ParserCrashError, not "no parser matched")
#   integrity_check_exception — a registration's own integrity check raised
#                               after a successful claim; its finding is
#                               UNKNOWN, which is not the same as "clear"


def test_a_parser_exception_is_flagged_for_review():
    dispatch = pr.Dispatch(
        "parser_exception",
        exceptions=(pr.ParserFailure("us_bank", "parse", "AttributeError"),),
    )
    stmt = statement("Bank Of Nowhere")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=dispatch)
    integrity = assess_document_integrity(stmt, recon, quality, markdown="x", dispatch=dispatch)

    assert "parser_exception" in integrity.flags
    assert any("us_bank" in note for note in integrity.notes)
    assert integrity.risk_level == "review"


def test_the_crash_note_names_the_parser_and_never_the_exception_message():
    """The flag exists to be actionable; it must not become a leak."""
    dispatch = pr.Dispatch(
        "parser_exception",
        exceptions=(pr.ParserFailure("bank_of_america", "parse", "ValueError"),),
    )
    stmt = statement("Bank Of Nowhere")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=dispatch)
    integrity = assess_document_integrity(stmt, recon, quality, markdown="x", dispatch=dispatch)

    note = next(note for note in integrity.notes if "bank_of_america" in note)
    assert "month must be in" not in note
    assert set(dispatch.crashed) == {"bank_of_america"}


def test_deterministic_mode_says_a_parser_crashed_rather_than_that_none_matched():
    from analysis.pipeline import analyze_markdown

    def explode(markdown: str):
        raise AttributeError(f"'NoneType' object has no attribute 'group': {markdown}")

    registration = pr.register(pr.Registration(
        id="_synthetic_crash_probe_pipeline",
        bank="Synthetic Crash Probe Pipeline",
        markers=(pr.required("probe", lambda t: "SYNTHETIC CRASH PROBE DOCUMENT" in t),),
        parse=explode,
    ))
    document = "SYNTHETIC CRASH PROBE DOCUMENT ACME PLUMBING LLC"
    try:
        with pytest.raises(pr.ParserCrashError) as raised:
            analyze_markdown(document, parse_mode="deterministic")
    finally:
        pr._REGISTRY.pop(registration.id, None)

    message = str(raised.value)
    assert "_synthetic_crash_probe_pipeline" in message and "AttributeError" in message
    assert "no deterministic parser matched" not in message
    assert "ACME PLUMBING" not in message, "the parser's own message must not travel"
    # Existing callers catch the deterministic refusal as RuntimeError.
    assert isinstance(raised.value, RuntimeError)


def test_a_crashing_integrity_check_becomes_a_flag_and_the_analysis_completes():
    """The one place registry-supplied code runs outside the resolve seam.

    An integrity check that raises has no finding — which is emphatically not
    the same as having nothing to report, so the document says so and goes to
    review instead of being reported as clear.
    """
    def explode(markdown: str, stmt: Statement) -> list[str]:
        raise ZeroDivisionError("division by zero while comparing summaries")

    registration = pr.Registration(
        id="_synthetic_check_probe",
        bank="Synthetic Check Probe",
        markers=(pr.required("probe", lambda t: "PROBE" in t),),
        parse=lambda md: None,
        integrity_checks=(explode,),
    )
    dispatch = pr.Dispatch("claimed", registration=registration, detection=pr.Detection(0.5))
    stmt = statement("Synthetic Check Probe")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=dispatch)

    integrity = assess_document_integrity(stmt, recon, quality, markdown="PROBE", dispatch=dispatch)

    assert "integrity_check_exception" in integrity.flags
    note = next(note for note in integrity.notes if "_synthetic_check_probe" in note)
    assert "ZeroDivisionError" in note
    assert "division by zero" not in note
    # A check that could not run is not a contradiction it found.
    assert "conflicting_statement_summaries" not in integrity.flags
    assert integrity.possible_document_issue is False


def test_a_healthy_integrity_check_still_reports_its_contradictions():
    def contradicts(markdown: str, stmt: Statement) -> list[str]:
        return ["the printed summary contradicts the second summary block"]

    registration = pr.Registration(
        id="_synthetic_check_probe_ok",
        bank="Synthetic Check Probe Ok",
        markers=(pr.required("probe", lambda t: "PROBE" in t),),
        parse=lambda md: None,
        integrity_checks=(contradicts,),
    )
    dispatch = pr.Dispatch("claimed", registration=registration, detection=pr.Detection(0.5))
    stmt = statement("Synthetic Check Probe Ok")
    recon = recon_for(stmt)
    quality = assess_quality(stmt, recon, dispatch=dispatch)

    integrity = assess_document_integrity(stmt, recon, quality, markdown="PROBE", dispatch=dispatch)

    assert "conflicting_statement_summaries" in integrity.flags
    assert "integrity_check_exception" not in integrity.flags
    assert integrity.possible_document_issue is True

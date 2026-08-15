"""MODEL-LABEL (W3 §PIPE5).

`Report.model_used` was `f"{(stmt.bank or 'bank').lower().replace(' ', '-')}-deterministic"`,
so every document whose parser publishes no issuer — the honest-unknown-issuer
registrations and the issuer-agnostic core-processor templates, which claim on a
PLATFORM's paper — was published as `bank-deterministic`. Four parsers'
output aggregated under one label that names none of them.

The population is exact and was measured live over the archive (PIPE5 §M2):
41 documents, `releve_facturation` 16, `balance_by_date` 11,
`core_processor_sectioned` 9, `community_section` 5 — every one of them
`Statement.bank is None`, every one of them `validated`.
"""
from __future__ import annotations

from analysis.parser_registry import Dispatch, Marker, Registration
from analysis.pipeline import analyze_markdown
from analysis.schema import Statement, Transaction
from telemetry.record import model_calls_for

MARKDOWN = """<!-- source: label.pdf | pages: 1 | model: native -->

--- Page 1 ---
Beginning Balance 1,000.00
02/03 CARD PURCHASE 100.00 900.00
Ending Balance 900.00
"""


def _statement(bank: str | None) -> Statement:
    return Statement(
        bank=bank,
        statement_period_start="2026-02-01",
        statement_period_end="2026-02-28",
        beginning_balance=1000.0,
        ending_balance=900.0,
        transactions=[
            Transaction(
                date="2026-02-03",
                description="CARD PURCHASE",
                amount=-100.0,
                direction="debit",
                running_balance=900.0,
            )
        ],
    )


def _report(monkeypatch, *, bank: str | None, parser_id: str, registered_bank: str):
    statement = _statement(bank)
    registration = Registration(
        id=parser_id,
        bank=registered_bank,
        markers=(Marker("m", lambda text: True),),
        parse=lambda markdown: None,
    )
    dispatch = Dispatch("claimed", registration=registration, statement=statement)
    monkeypatch.setattr("analysis.pipeline.resolve", lambda markdown: dispatch)
    return analyze_markdown(MARKDOWN, parse_mode="deterministic")


def test_a_bank_none_document_is_labelled_with_the_parser_that_claimed_it(monkeypatch):
    report = _report(
        monkeypatch,
        bank=None,
        parser_id="releve_facturation",
        registered_bank="Relevé de facturation",
    )
    assert report.model_used == "releve_facturation-deterministic"


def test_two_bank_none_parsers_no_longer_share_one_label(monkeypatch):
    """The dishonesty the card names: before this hunk both of these published
    `bank-deterministic`, so an aggregation read four parsers as one."""
    first = _report(
        monkeypatch, bank=None, parser_id="balance_by_date", registered_bank="X"
    )
    second = _report(
        monkeypatch, bank=None, parser_id="community_section", registered_bank="Y"
    )
    assert first.model_used == "balance_by_date-deterministic"
    assert second.model_used == "community_section-deterministic"
    assert first.model_used != second.model_used


def test_a_document_with_a_bank_label_is_untouched(monkeypatch):
    """The non-movement half, and the reason the archive sweep moves exactly
    41 documents: a statement that names its issuer takes the byte-identical
    old expression — the BANK label, never the parser id."""
    report = _report(
        monkeypatch, bank="Regions Bank", parser_id="regions", registered_bank="Regions Bank"
    )
    assert report.model_used == "regions-bank-deterministic"


def test_the_old_expression_survives_for_every_labelled_shape(monkeypatch):
    """Spaces to hyphens, casefolded, punctuation kept — pinned so the
    `is None` branch cannot be widened into a rewrite of the labelled ones."""
    for bank, expected in [
        ("TD Canada Trust", "td-canada-trust-deterministic"),
        ("Farmers & Merchants Bank", "farmers-&-merchants-bank-deterministic"),
        ("BMO", "bmo-deterministic"),
    ]:
        report = _report(
            monkeypatch, bank=bank, parser_id="whatever", registered_bank=bank
        )
        assert report.model_used == expected


def test_the_deterministic_suffix_is_preserved(monkeypatch):
    """Load-bearing: `telemetry.record.model_calls_for` reads the suffix to
    mean "no model call was made". A renamed label that lost it would invent
    an extraction call, and a cost, for every bank=None document."""
    report = _report(
        monkeypatch, bank=None, parser_id="releve_facturation", registered_bank="X"
    )
    assert report.model_used.endswith("-deterministic")
    assert model_calls_for(None, {"model_used": report.model_used}) == []


def test_an_unclaimed_extraction_is_out_of_scope(monkeypatch):
    """The LLM path has no registration, so it keeps today's behaviour
    exactly — this hunk is keyed on a claim, not on the absence of a bank."""
    from analysis.pipeline import _registration_for

    assert _registration_for(_statement(None), Dispatch("unclaimed")) is None

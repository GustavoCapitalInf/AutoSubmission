"""The recorded parser baseline is complete and agrees with the audited truth.

`tests/data/parser_expectations.json` records which parser claimed each of the
109 pinned corpus documents under the pre-R-3 or-chain. Every later R-3 stage is
judged against it, so it needs its own integrity checks: a baseline that has
quietly shrunk, or that pins documents the audits do not, would let a dispatch
regression through while still reporting green.

These tests are fast and offline — they read the JSON and the committed CSVs,
never a PDF. The expensive comparison against live dispatch is
`tests/test_parser_parity.py`, which is corpus-marked.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXPECTATIONS = ROOT / "tests" / "data" / "parser_expectations.json"
BALANCE_CSV = ROOT / "docs" / "balance-metrics-audit-results.csv"
ADB_CSV = ROOT / "docs" / "adb-audit-results.csv"
EXPECTED_ROWS = 109

#: Parser id -> the attribute in `analysis.pipeline` that the or-chain calls.
#: Ids follow the naming baseline of the reviewed prototype registry
#: (`git show 54a9e8d:analysis/parser_registry.py`); its dispatch semantics are deliberately NOT reused.
PIPELINE_ENTRY_POINTS: dict[str, str] = {
    "columbia_bank": "parse_columbia_bank_statement",
    "first_farmers": "parse_first_farmers_statement",
    "navigant": "parse_navigant_statement",
    "relay": "parse_relay_statement",
    "td_canada": "parse_td_canada_statement",
    "td_us": "parse_td_us_statement",
    "altana": "parse_altana_statement",
    "american_express": "parse_amex_statement",
    "atb": "parse_atb_statement",
    "b1": "parse_b1_statement",
    "banco_popular": "parse_banco_popular_statement",
    "bluevine": "parse_bluevine_statement",
    "cibc_french": "parse_cibc_french_statement",
    "consumers": "parse_consumers_statement",
    "demo_national": "parse_demo_national_statement",
    "desjardins": "parse_desjardins_statement",
    "ibc": "parse_ibc_statement",
    "mission_valley": "parse_mission_valley_statement",
    "dakota_west": "parse_dakota_west_statement",
    "linkbank": "parse_linkbank_statement",
    "midflorida": "parse_midflorida_statement",
    "navy_federal": "parse_navy_federal_statement",
    "santander": "parse_santander_statement",
    "southside_scanned": "parse_southside_scanned_statement",
    "apex_scanned": "parse_apex_scanned_statement",
    "texas_bank": "parse_texas_bank_statement",
    "truist": "parse_truist_statement",
    "us_bank": "parse_us_bank_statement",
    "rbc": "parse_rbc_statement",
    "scotiabank": "parse_scotiabank_statement",
    "secu": "parse_secu_statement",
    "wells_fargo": "parse_wells_statement",
    "wilson_muir": "parse_wilson_muir_statement",
    "bank_of_america": "parse_bofa_statement",
    "regions": "parse_regions_statement",
    "pnc": "parse_pnc_statement",
    "farmers_merchants": "parse_farmers_merchants_statement",
    "first_community": "parse_first_community_statement",
    "first_citizens": "parse_first_citizens_statement",
    "bmo": "parse_bmo_statement",
    "capital_one": "parse_capital_one_statement",
    "chase": "parse_chase_statement",
    "citizens": "parse_citizens_statement",
}

#: Nested sub-dispatches: variant id -> (module, private function, outer id).
SUB_DISPATCHES: dict[str, tuple[str, str, str]] = {
    "chase_export": ("analysis.chase", "_parse_chase_business_export", "chase"),
    "rbc_french": ("analysis.rbc", "_parse_rbc_french_statement", "rbc"),
    "td_canada_native": ("analysis.td_can", "_parse_native_td_canada", "td_canada"),
}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def baseline() -> dict:
    return json.loads(EXPECTATIONS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def documents(baseline) -> list[dict]:
    return baseline["documents"]


def test_baseline_covers_every_pinned_corpus_document(documents):
    pinned = {row["path"] for row in _rows(BALANCE_CSV)}
    recorded = {row["path"] for row in documents}
    assert recorded == pinned, (
        f"missing from baseline: {sorted(pinned - recorded)}; "
        f"not pinned by the audits: {sorted(recorded - pinned)}"
    )
    assert len(documents) == EXPECTED_ROWS


def test_baseline_agrees_with_both_audits_on_the_document_set(documents):
    """Neither audit may be the sole authority for what the baseline covers."""
    recorded = {row["path"] for row in documents}
    assert recorded == {row["path"] for row in _rows(BALANCE_CSV)}
    assert {Path(p).name for p in recorded} == {
        Path(row["statement"]).name for row in _rows(ADB_CSV)
    }


def test_every_document_pins_its_source_bytes(documents):
    for row in documents:
        assert row["sha256"], f"{row['path']} has no source digest"
        assert row["sha256"] == row["sha256"].upper()
        assert len(row["sha256"]) == 64
    digests = [row["sha256"] for row in documents]
    assert len(set(digests)) == len(digests), "two baseline rows share a source digest"


def test_source_digests_match_the_balance_audit(documents):
    """The digest pins the row to the document; it must be the audited one."""
    audited = {row["path"]: row["sha256"] for row in _rows(BALANCE_CSV)}
    mismatches = [
        f"{row['path']}: baseline {row['sha256']}, audit {audited[row['path']]}"
        for row in documents
        if audited[row["path"]] != row["sha256"]
    ]
    assert not mismatches, mismatches


def test_every_document_names_a_claiming_parser(documents):
    missing = [row["path"] for row in documents if not row["parser_id"]]
    assert not missing, f"documents with no recorded claimant: {missing}"


def test_recorded_variants_belong_to_their_outer_parser(documents):
    for row in documents:
        variant = row["variant_id"]
        if variant is None:
            continue
        assert variant in SUB_DISPATCHES, f"unknown variant {variant}"
        _module, _attribute, outer = SUB_DISPATCHES[variant]
        assert row["parser_id"] == outer, (
            f"{row['path']}: variant {variant} recorded under {row['parser_id']}, "
            f"expected {outer}"
        )


def test_recorded_parser_ids_are_all_registered_entry_points(documents):
    unknown = {row["parser_id"] for row in documents} - set(PIPELINE_ENTRY_POINTS)
    assert not unknown, f"baseline names parsers the recorder does not know: {unknown}"


def test_chain_declined_ids_are_a_prefix_of_the_dispatch_order(documents):
    """`chain_declined_ids` is what the or-chain ran before the claimant.

    It must therefore be an ordered prefix of the dispatch order ending
    immediately before the claiming parser — if it is not, the recording caught
    something other than the chain and the baseline is not trustworthy.
    """
    order = list(PIPELINE_ENTRY_POINTS)
    for row in documents:
        expected = order[: order.index(row["parser_id"])]
        assert row["chain_declined_ids"] == expected, (
            f"{row['path']}: recorded prefix {row['chain_declined_ids']} "
            f"is not the dispatch prefix {expected}"
        )


#: Parsers with no document in the pinned corpus. R-4's synthetic
#: conformance fixtures are their only coverage, so the set is asserted rather
#: than discovered: it must not grow without someone noticing.
CORPUS_UNREPRESENTED = {"demo_national"}


def test_the_corpus_exercises_all_but_one_registered_parser(documents):
    """A named, deliberate record of what the corpus does not cover.

    Every parser except those in `CORPUS_UNREPRESENTED` claims at least one
    corpus document. Handed to R-4 (RFC §6.2/10) as a required entry in its
    conformance-completeness list.
    """
    claiming = {row["parser_id"] for row in documents}
    uncovered = set(PIPELINE_ENTRY_POINTS) - claiming
    assert uncovered == CORPUS_UNREPRESENTED, (
        f"corpus coverage of the parser set changed: uncovered={sorted(uncovered)}"
    )

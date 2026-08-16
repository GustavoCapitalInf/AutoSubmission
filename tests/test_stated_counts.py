"""COUNTS-P1 — the stated-count observer, phase 1 (observe only).

Every value in the closed vocabulary is pinned here in both directions, the
forced-mismatch prohibition is pinned structurally, and the two rules the
2026-08-10 sign-off made binding — independence of the expected side, and
direction-not-sign on the captured side — each have a test that fails if the
implementation quietly reverts to the easy version.

Nothing here touches `analysis/`, `ocr/`, `webapp/` or `discovery/`.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from telemetry.stated_counts import (
    CHECK_UNAVAILABLE,
    DIRECTIONS,
    MATCH,
    MISMATCH,
    NOT_PRINTED,
    REASONS,
    RESULTS,
    SECTION_LEVEL_ORACLES,
    SEMANTICS,
    SEMANTICS_INCOMPARABLE,
    UNSURVEYED,
    Observation,
    evaluate,
    rollup,
    semantics_for,
    unavailable,
)

ROOT = Path(__file__).resolve().parents[1]


# --- fixtures ---------------------------------------------------------------


def row(direction: str, amount: float, description: str = "ROW") -> dict:
    return {"direction": direction, "amount": amount, "description": description}


def payload(
    *,
    credit: int | None,
    debit: int | None,
    rows: list[dict],
    metrics: object | None = None,
    service_charge: float | None = None,
) -> dict:
    out: dict = {
        "statement": {
            "stated_credit_count": credit,
            "stated_debit_count": debit,
            "transactions": rows,
        }
    }
    if service_charge is not None:
        # The one printed field a count mapping may read (W3 §COUNTSMAP).
        out["statement"]["stated_service_charge"] = service_charge
    if metrics is not None:
        out["metrics"] = metrics
    return out


#: A parser the table maps rather than compares raw: its printed debit count
#: excludes the separately-printed service charge the parser records as a row.
MAPPED = "capital_one"


#: A parser whose semantics are surveyed and comparable in both directions.
COMPARABLE = "rbc"
#: A parser the table declares incomparable in both directions. Was `us_bank`
#: until COUNTS-P2 promoted it to comparable on the phase-1 counterfactual
#: (40/40 in both directions, re-proven against the current archive); `altana`
#: is the remaining both-directions incomparable, and its argument is the
#: sharper one anyway — the printed figure is gated equal to LABEL-MATCHED
#: rows, so it can never be the count of rows in a direction.
INCOMPARABLE = "altana"


# --- the closed vocabulary, one test per value ------------------------------


def test_match_when_printed_counts_equal_the_rows():
    obs = evaluate(
        payload(credit=2, debit=1, rows=[row("credit", 10), row("credit", 5), row("debit", -3)]),
        parser_id=COMPARABLE,
    )
    assert (obs.credit.result, obs.debit.result) == (MATCH, MATCH)
    assert (obs.credit.stated, obs.credit.captured) == (2, 2)
    assert (obs.debit.stated, obs.debit.captured) == (1, 1)


def test_mismatch_when_a_row_sits_in_the_wrong_direction():
    """The RBC class: the money is unchanged, the columns are not."""
    rows = [row("credit", 10), row("debit", 5), row("debit", -3)]
    obs = evaluate(payload(credit=2, debit=1, rows=rows), parser_id=COMPARABLE)
    assert (obs.credit.result, obs.debit.result) == (MISMATCH, MISMATCH)
    assert (obs.credit.stated, obs.credit.captured) == (2, 1)
    assert (obs.debit.stated, obs.debit.captured) == (1, 2)


def test_not_printed_is_per_direction_and_never_inferred():
    """A bank that prints one count gets one check, not two."""
    obs = evaluate(
        payload(credit=1, debit=None, rows=[row("credit", 10), row("debit", -3)]),
        parser_id=COMPARABLE,
    )
    assert obs.credit.result == MATCH
    assert obs.debit.result == NOT_PRINTED
    assert obs.debit.stated is None and obs.debit.captured is None


def test_semantics_incomparable_for_a_bank_whose_printed_count_means_something_else():
    obs = evaluate(
        payload(credit=99, debit=99, rows=[row("credit", 10), row("debit", -3)]),
        parser_id=INCOMPARABLE,
    )
    assert (obs.credit.result, obs.debit.result) == (
        SEMANTICS_INCOMPARABLE,
        SEMANTICS_INCOMPARABLE,
    )


def test_a_mapped_direction_is_compared_against_the_mapped_expectation():
    """W3 §COUNTSMAP. The bank printed `Checks/Debits (1)` and billed a charge
    it prints on its own line with no count; the parser records the charge as a
    debit ROW, so a complete ledger has two. The observer must reach the same
    answer the shipping check does, through the same function."""
    rows = [row("credit", 10), row("debit", -3), row("debit", -15, "SERVICE CHARGE")]
    obs = evaluate(payload(credit=1, debit=1, rows=rows, service_charge=15.0),
                   parser_id=MAPPED)
    assert obs.debit.result == MATCH
    # `stated` is what the bank printed; `expected` is the number compared.
    assert (obs.debit.stated, obs.debit.expected, obs.debit.captured) == (1, 2, 2)
    assert obs.credit.result == MATCH
    assert (obs.credit.stated, obs.credit.expected) == (1, 1)


def test_a_mapped_direction_still_reports_mismatch_when_a_row_is_missing():
    """The mapping restates the expected side; it does not soften it. A billed
    cycle whose charge row never made it into the ledger is a MISMATCH — and
    the raw equality test, which would compare 1 against 1, is blind to it."""
    rows = [row("credit", 10), row("debit", -3)]
    obs = evaluate(payload(credit=1, debit=1, rows=rows, service_charge=15.0),
                   parser_id=MAPPED)
    assert obs.debit.result == MISMATCH
    assert (obs.debit.stated, obs.debit.expected, obs.debit.captured) == (1, 2, 1)


def test_an_unbilled_cycle_of_a_mapped_bank_is_compared_raw():
    rows = [row("credit", 10), row("debit", -3)]
    for charge in (0.0, None):
        obs = evaluate(payload(credit=1, debit=1, rows=rows, service_charge=charge),
                       parser_id=MAPPED)
        assert obs.debit.result == MATCH, charge
        assert (obs.debit.stated, obs.debit.expected) == (1, 1), charge


def test_check_unavailable_with_no_payload():
    obs = unavailable("chase")
    assert (obs.credit.result, obs.debit.result) == (CHECK_UNAVAILABLE, CHECK_UNAVAILABLE)
    assert evaluate(None, parser_id="chase").credit.result == CHECK_UNAVAILABLE
    assert evaluate({}, parser_id="chase").credit.result == CHECK_UNAVAILABLE


def test_check_unavailable_for_aggregate_backed_statements():
    """One `UNCAPTURED` row stands for many postings by design."""
    rows = [row("credit", 900, "UNCAPTURED DEPOSIT ACTIVITY"), row("debit", -3)]
    obs = evaluate(payload(credit=40, debit=1, rows=rows), parser_id=COMPARABLE)
    assert (obs.credit.result, obs.debit.result) == (CHECK_UNAVAILABLE, CHECK_UNAVAILABLE)
    assert obs.credit.stated == 40  # the printed evidence is still reported


def test_check_unavailable_with_no_rows_and_with_a_directionless_row():
    empty = evaluate(payload(credit=3, debit=3, rows=[]), parser_id=COMPARABLE)
    assert empty.credit.result == CHECK_UNAVAILABLE
    broken = evaluate(
        payload(credit=1, debit=1, rows=[row("credit", 5), {"amount": -1}]),
        parser_id=COMPARABLE,
    )
    assert (broken.credit.result, broken.debit.result) == (
        CHECK_UNAVAILABLE,
        CHECK_UNAVAILABLE,
    )


def test_check_unavailable_when_the_registration_is_not_a_formal_statement():
    obs = evaluate(
        payload(credit=1, debit=1, rows=[row("credit", 5), row("debit", -1)]),
        parser_id=COMPARABLE,
        formal_statement=False,
    )
    assert (obs.credit.result, obs.debit.result) == (CHECK_UNAVAILABLE, CHECK_UNAVAILABLE)


def test_every_result_a_direction_can_carry_is_in_the_closed_vocabulary():
    seen = set()
    cases = [
        (payload(credit=1, debit=1, rows=[row("credit", 1), row("debit", -1)]), COMPARABLE, True),
        (payload(credit=9, debit=9, rows=[row("credit", 1), row("debit", -1)]), COMPARABLE, True),
        (payload(credit=None, debit=None, rows=[row("credit", 1)]), COMPARABLE, True),
        (payload(credit=1, debit=1, rows=[row("credit", 1)]), INCOMPARABLE, True),
        (payload(credit=1, debit=1, rows=[]), COMPARABLE, True),
    ]
    for body, parser, formal in cases:
        obs = evaluate(body, parser_id=parser, formal_statement=formal)
        for direction_obs in obs.directions():
            seen.add(direction_obs.result)
            assert direction_obs.result in RESULTS
            assert direction_obs.reason in REASONS
    assert seen == set(RESULTS)


# --- the forced-mismatch prohibition ---------------------------------------


@pytest.mark.parametrize("parser_id", sorted(SEMANTICS))
def test_an_incomparable_direction_can_never_emit_mismatch(parser_id):
    """Structural, not incidental: no input reaches `mismatch` through a
    direction whose semantics say `comparable=False`."""
    rows = [row("credit", 1), row("credit", 2), row("debit", -3), row("debit", -4)]
    obs = evaluate(payload(credit=999, debit=999, rows=rows), parser_id=parser_id)
    for direction in DIRECTIONS:
        result = getattr(obs, direction).result
        if not semantics_for(parser_id, direction).comparable:
            assert result == SEMANTICS_INCOMPARABLE
        else:
            assert result == MISMATCH


def test_an_unsurveyed_parser_is_incomparable_rather_than_assumed_comparable():
    assert semantics_for("a_parser_nobody_surveyed", "credit") is UNSURVEYED
    obs = evaluate(
        payload(credit=99, debit=99, rows=[row("credit", 1)]),
        parser_id="a_parser_nobody_surveyed",
    )
    assert (obs.credit.result, obs.debit.result) == (
        SEMANTICS_INCOMPARABLE,
        SEMANTICS_INCOMPARABLE,
    )


def test_a_parser_with_no_printed_count_reports_not_printed_not_incomparable():
    """`not_printed` outranks `semantics_incomparable`: with no expected side
    there is nothing for the semantics to be about."""
    obs = evaluate(payload(credit=None, debit=None, rows=[row("credit", 1)]), parser_id=INCOMPARABLE)
    assert (obs.credit.result, obs.debit.result) == (NOT_PRINTED, NOT_PRINTED)


# --- direction, not sign ----------------------------------------------------


def test_a_zero_amount_row_is_counted_by_its_printed_column():
    """`analysis/metrics.py:186-191` counts `amount >= 0` as a deposit, so a
    zero-amount row printed in the withdrawals column is a deposit to a
    sign-keyed count and a debit to this one. The bank printed 1 and 1."""
    rows = [row("credit", 500), row("debit", 0.0, "REVERSED FEE")]
    obs = evaluate(payload(credit=1, debit=1, rows=rows), parser_id=COMPARABLE)
    assert (obs.credit.result, obs.debit.result) == (MATCH, MATCH)
    # the counterfactual is measured, and it is wrong on both directions
    assert obs.credit.captured_by_sign == 2
    assert obs.debit.captured_by_sign == 0
    assert obs.zero_amount_rows == 1
    assert obs.direction_sign_disagreements == 1


def test_the_rollup_counts_what_a_sign_keyed_check_would_have_got_wrong():
    rows = [row("credit", 500), row("debit", 0.0)]
    obs = evaluate(payload(credit=1, debit=1, rows=rows), parser_id=COMPARABLE)
    summary = rollup([({"content_sha256": "A" * 64, "outcome_class": "validated"}, obs)])
    assert summary["sign_keyed_counterfactual"]["sign_false_mismatch"] == 2
    assert "sign_false_match" not in summary["sign_keyed_counterfactual"]


def test_reversals_are_counted_gross():
    """`reconcile.py:165-207` nets settlement reversals out of the MONEY
    coverage; a reversal is still a printed row the bank counted."""
    rows = [row("credit", 100, "SETTLEMENT"), row("debit", -100, "SETTLEMENT REVERSAL")]
    obs = evaluate(payload(credit=1, debit=1, rows=rows), parser_id=COMPARABLE)
    assert (obs.credit.result, obs.debit.result) == (MATCH, MATCH)


def test_the_comparison_is_exact_with_no_tolerance():
    rows = [row("credit", 1)] * 100 + [row("debit", -1)] * 100
    obs = evaluate(payload(credit=101, debit=100, rows=rows), parser_id=COMPARABLE)
    assert obs.credit.result == MISMATCH
    assert obs.debit.result == MATCH


# --- independence of the expected side --------------------------------------


class _Tripwire(Mapping):
    """A mapping that refuses to be read. Anything the observer reaches for
    here is a violation of the independence rule."""

    def __getitem__(self, key):  # pragma: no cover - the point is not to run
        raise AssertionError(f"the observer read metrics[{key!r}]")

    def get(self, key, default=None):  # pragma: no cover - same
        raise AssertionError(f"the observer read metrics.get({key!r})")

    def __iter__(self):  # pragma: no cover - same
        raise AssertionError("the observer iterated metrics")

    def __len__(self):  # pragma: no cover - same
        raise AssertionError("the observer sized metrics")


def test_the_expected_side_never_comes_from_metrics():
    body = payload(
        credit=1,
        debit=1,
        rows=[row("credit", 5), row("debit", -5)],
        metrics=_Tripwire(),
    )
    obs = evaluate(body, parser_id=COMPARABLE)
    assert (obs.credit.result, obs.debit.result) == (MATCH, MATCH)


def test_metrics_cannot_change_a_vocabulary_result():
    """The one place `metrics` is read at all is the BofA ADVISORY block, which
    is explicitly not the vocabulary. Removing metrics must not move a single
    vocabulary result."""
    rows = [row("credit", 5), row("debit", -5), row("debit", -1, "CHECK 1041")]
    with_metrics = evaluate(
        payload(credit=1, debit=2, rows=rows, metrics={"check_count": 1,
                                                       "effective_num_deposits": 99,
                                                       "num_deposits": 99}),
        parser_id="bank_of_america",
    )
    without = evaluate(payload(credit=1, debit=2, rows=rows), parser_id="bank_of_america")
    assert with_metrics.credit.as_dict() == without.credit.as_dict()
    assert with_metrics.debit.as_dict() == without.debit.as_dict()
    assert "debit_would_be_with_check_mapping" in with_metrics.advisory
    assert "debit_would_be_with_check_mapping" not in without.advisory


# --- the payload is never mutated -------------------------------------------


def test_the_observer_never_mutates_the_payload():
    body = payload(
        credit=2,
        debit=1,
        rows=[row("credit", 10), row("debit", 0.0), row("debit", -3)],
        metrics={"check_count": 1, "num_deposits": 7},
    )
    before = copy.deepcopy(body)
    frozen = json.dumps(body, sort_keys=True)
    for parser_id in (COMPARABLE, INCOMPARABLE, "bank_of_america", None):
        evaluate(body, parser_id=parser_id)
    assert body == before
    assert json.dumps(body, sort_keys=True) == frozen


def test_an_observation_is_immutable():
    obs = evaluate(payload(credit=1, debit=1, rows=[row("credit", 1), row("debit", -1)]),
                   parser_id=COMPARABLE)
    with pytest.raises(Exception):
        obs.credit.result = MISMATCH  # type: ignore[misc]
    with pytest.raises(Exception):
        obs.parser_id = "x"  # type: ignore[misc]


# --- the semantics table itself ---------------------------------------------


def test_every_semantics_entry_covers_both_directions_and_carries_a_reason():
    for parser_id, table in SEMANTICS.items():
        assert set(table) == set(DIRECTIONS), parser_id
        for direction, semantics in table.items():
            assert semantics.scope, f"{parser_id}:{direction}"
            assert len(semantics.reason) > 40, f"{parser_id}:{direction} reason is not an argument"


def test_the_table_only_names_parsers_that_exist_in_the_registry():
    source = (ROOT / "analysis" / "parser_registry_entries.py").read_text(encoding="utf-8")
    for parser_id in SEMANTICS:
        assert f'("{parser_id}"' in source, parser_id


def test_the_table_only_names_parsers_that_assign_a_stated_count():
    """Read-only drift guard over `analysis/`: a parser in the semantics table
    that no longer assigns a printed count is a table entry describing nothing,
    and a parser that starts assigning one without a table entry falls to
    `UNSURVEYED` — which is safe, but should be a deliberate choice."""
    assigning = set()
    for path in (ROOT / "analysis").glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "stated_credit_count=" in text or "stated_credit_count =" in text:
            assigning.add(path.stem)
    modules = {
        "altana", "atb", "bofa", "capital_one", "chase", "community_section",
        "demo_national", "farmers_merchants", "first_community", "first_farmers",
        "ibc", "linkbank", "midflorida", "rbc", "scanned_small_bank", "scotia",
        "td_can", "texas_bank", "us_bank", "wilson_muir",
    }
    assert modules <= assigning, modules - assigning


def test_the_section_level_oracles_are_disclosed_and_not_silently_compared():
    """PNC's evidence is per SECTION and the schema cannot hold it; Wells'
    printed Totals line is unread. Neither may appear in the semantics table
    as if this check covered it."""
    assert set(SECTION_LEVEL_ORACLES) == {"pnc", "wells_fargo"}
    assert not set(SECTION_LEVEL_ORACLES) & set(SEMANTICS)
    for note in SECTION_LEVEL_ORACLES.values():
        assert len(note) > 40


# --- the rollup -------------------------------------------------------------


def test_the_rollup_separates_would_be_flagged_populations_by_outcome_class():
    bad = evaluate(payload(credit=2, debit=1, rows=[row("credit", 1), row("debit", -1)]),
                   parser_id=COMPARABLE)
    good = evaluate(payload(credit=1, debit=1, rows=[row("credit", 1), row("debit", -1)]),
                    parser_id=COMPARABLE)
    summary = rollup([
        ({"content_sha256": "A" * 64, "outcome_class": "validated"}, bad),
        ({"content_sha256": "B" * 64, "outcome_class": "withheld"}, bad),
        ({"content_sha256": "C" * 64, "outcome_class": "validated"}, good),
    ])
    assert summary["documents"] == 3
    assert summary["would_be_flagged"]["validated"][COMPARABLE]["documents"] == 1
    assert summary["would_be_flagged"]["withheld"][COMPARABLE]["documents"] == 1
    assert summary["would_be_flagged"]["validated"][COMPARABLE]["hashes"] == ["A" * 64]
    assert summary["coverage"]["mismatch_document"] == 2
    assert set(summary["direction_results"]) <= set(RESULTS)


def test_a_pinned_pass_document_is_reported_separately_from_its_advisory_twin():
    real = evaluate(payload(credit=2, debit=1, rows=[row("credit", 1), row("debit", -1)]),
                    parser_id=COMPARABLE)
    advisory_only = evaluate(payload(credit=9, debit=9, rows=[row("credit", 1), row("debit", -1)]),
                             parser_id=INCOMPARABLE)
    summary = rollup([
        ({"content_sha256": "A" * 64, "outcome_class": "validated", "corpus_status": "PASS"}, real),
        ({"content_sha256": "B" * 64, "outcome_class": "validated", "corpus_status": "PASS"}, advisory_only),
    ])
    assert [r["content_sha256"] for r in summary["corpus_pass_mismatch"]] == ["A" * 64]
    assert [r["content_sha256"] for r in summary["corpus_pass_advisory_mismatch"]] == ["B" * 64]


def test_the_rollup_emits_no_document_content():
    obs = evaluate(
        payload(credit=1, debit=1, rows=[row("credit", 1, "ACME PAYROLL 4491"),
                                         row("debit", -1, "CHECK 1041")]),
        parser_id=COMPARABLE,
    )
    text = json.dumps(rollup([({"content_sha256": "A" * 64, "outcome_class": "validated"}, obs)]))
    assert "ACME" not in text and "1041" not in text


# --- structural: phase 1 stays out of the production path -------------------


def test_importing_telemetry_still_does_not_drag_in_the_webapp():
    """T12 extended: the observer's webapp/ocr reads are lazy, so the plain
    `import telemetry` path the CLI depends on is unchanged."""
    code = (
        "import sys, telemetry, telemetry.stated_counts;"
        "print([m for m in sys.modules if m == 'webapp' or m.startswith('webapp.')])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]", result.stdout


def test_the_observer_is_not_wired_into_any_production_module():
    """Phase 1 lands ZERO production-path change. Nothing in `analysis/`,
    `ocr/`, `webapp/` or `discovery/` may reference it, and neither may the
    telemetry record path."""
    for package in ("analysis", "ocr", "webapp", "discovery"):
        for path in (ROOT / package).rglob("*.py"):
            assert "stated_counts" not in path.read_text(encoding="utf-8", errors="ignore"), path
    for name in ("record.py", "diagnostics.py", "emit.py", "collect.py", "__init__.py"):
        text = (ROOT / "telemetry" / name).read_text(encoding="utf-8")
        assert "stated_counts" not in text, name


def test_unavailable_rejects_a_reason_outside_the_closed_enum():
    with pytest.raises(ValueError):
        unavailable("chase", "because I said so")
    with pytest.raises(ValueError):
        semantics_for("chase", "sideways")


def test_an_observation_carries_only_ids_codes_and_integers():
    obs = evaluate(
        payload(credit=1, debit=1, rows=[row("credit", 1, "ACME PAYROLL")]),
        parser_id=COMPARABLE,
    )
    assert isinstance(obs, Observation)
    for value in obs.as_dict().values():
        assert not isinstance(value, float)
    assert "ACME" not in json.dumps(obs.as_dict())


# --- the artifact join: the observer's one integration point ----------------
#
# `_ArtifactJoin` resolves the analysis cache key. It used to REIMPLEMENT it —
# a second copy of a computation that lives in `webapp/artifact_cache.py`, and
# copies drift: W3 FILENAME-BOUNDARY changed the analysis stage to key on
# `text_sha256(admissible_text(markdown))` and this copy kept hashing the raw
# reconstruction, which misses on EVERY document — `payload_for` returns None
# for all of them and `observe_run` emits `payload_absent` on 100% of rows. The
# instrument fails safe and measures nothing, which is the worst kind of green.
# W3 §WIRING would have done it a second time by adding the sheet partition to
# the key, so the copy is gone: the join imports `analysis_input_sha`. What it
# still owns is the SHAPE it hands that function — markdown plus page list —
# and these are the tests that catch that.


def _seed_one_document(data_dir, *, cached_under: str, pages=("LEDGER PAGE",)):
    """Write one real OCR + analysis artifact pair, exactly as the worker does.

    Returns `(content_sha, payload)`. Nothing is faked: the analysis entry goes
    in through `cached_analysis`, so the key under test is the key production
    writes.
    """
    from ocr.document import StatementMarkdown
    from ocr.inspect import content_sha256
    from webapp.artifact_cache import (
        ArtifactCache,
        cached_analysis,
        ocr_settings_key,
    )
    from webapp.storage import Storage

    pdf_bytes = b"%PDF-1.7\nstated-counts join fixture"
    cache = ArtifactCache(Storage(data_dir))
    document = StatementMarkdown(
        source_file=cached_under, model="fake-ocr", pages=list(pages)
    )
    cache.put_ocr(
        content_sha256(pdf_bytes),
        ocr_settings_key(force_ocr=False, allow_local_ocr=False, allow_visual_ocr=False),
        document,
    )
    payload = {"statement": {"bank": "Test Bank"}, "counts": {"credit": 1}}
    result = cached_analysis(
        document.to_markdown(),
        compute=lambda: payload,
        cache=cache,
        parse_mode="deterministic",
        # As a WIRED production caller writes it: the page partition is part of
        # the analysis input hash, so a fixture that omitted it would seed a key
        # no archive document can ever have (W3 §WIRING W3).
        sheets=document.pages,
    )
    assert not result.cached, "fixture must have WRITTEN the analysis entry"
    return content_sha256(pdf_bytes), payload


def test_the_artifact_join_resolves_a_document_to_its_analysis_payload(tmp_path):
    """The join works at all — the coverage this integration point never had."""
    from telemetry.stated_counts import _ArtifactJoin

    data_dir = tmp_path / "data"
    content_sha, payload = _seed_one_document(data_dir, cached_under="statement.pdf")

    join = _ArtifactJoin(data_dir)
    assert join.payload_for(content_sha, "statement.pdf") == payload


def test_the_artifact_join_survives_a_rename_of_the_document(tmp_path):
    """The join must key on the same text the analysis stage keys on.

    The archive reconstructs `StatementMarkdown` with whatever `source_file` the
    run row carries, so if the filename reached the hash the join would break
    the moment a document were re-filed — and it would break SILENTLY, as a
    universal `payload_absent`. Since the analysis stage is filename-blind, so
    is this.
    """
    from telemetry.stated_counts import _ArtifactJoin

    data_dir = tmp_path / "data"
    content_sha, payload = _seed_one_document(data_dir, cached_under="original name.pdf")

    join = _ArtifactJoin(data_dir)
    assert join.payload_for(content_sha, "renamed 2020 copy.pdf") == payload


def test_the_artifact_join_computes_the_same_key_the_analysis_cache_writes(tmp_path):
    """Pins the join to the cache's own derivation, so a future change to the
    key material is a failure here rather than a blind instrument in production.

    There is no longer a second copy to drift — the join imports
    `analysis_input_sha` — but the SHAPE it feeds that function is still its
    own: it must reconstruct the page list as well as the markdown. Hashing the
    text alone, or the raw reconstruction with its filename header, misses on
    every document.
    """
    from analysis.parser_registry import admissible_text
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import analysis_input_sha, text_sha256
    from telemetry.stated_counts import _ArtifactJoin

    data_dir = tmp_path / "data"
    _seed_one_document(data_dir, cached_under="s.pdf")
    join = _ArtifactJoin(data_dir)

    pages = ["LEDGER PAGE"]
    markdown = StatementMarkdown(
        source_file="s.pdf", model="fake-ocr", pages=pages
    ).to_markdown()
    assert "<!-- source:" in markdown, "fixture must carry the header"
    # The key the cache wrote is over the admissible text AND the page
    # partition, and it is the only one the join's index knows.
    assert analysis_input_sha(markdown, pages) in join._analysis_index
    assert analysis_input_sha(markdown, None) not in join._analysis_index
    assert text_sha256(admissible_text(markdown)) not in join._analysis_index
    assert text_sha256(markdown) not in join._analysis_index


def test_the_join_settings_key_is_the_production_analysis_key(tmp_path):
    """The other half of the key: the SETTINGS side.

    The join indexes the whole artifact table on one value of the analysis
    settings key, so anything the key gains must be something this class can
    reproduce. W3 §REGFP added the parser registry's fingerprint to it — a
    per-RUN constant, which is why it belongs in the settings key and not in
    the input hash — and the join reaches it for free because it imports
    `analysis_settings_key` rather than assembling the settings dict itself.
    Pinned here so that a future copy of that dict fails a test instead of
    silently emptying the index.
    """
    from telemetry.stated_counts import _ArtifactJoin
    from webapp.artifact_cache import analysis_settings_key

    data_dir = tmp_path / "data"
    _seed_one_document(data_dir, cached_under="s.pdf")

    join = _ArtifactJoin(data_dir)
    assert join.analysis_settings_key == analysis_settings_key(parse_mode="deterministic")
    # Not vacuous: that key is the one the seeded entry was written under, so
    # the index the join built from it is non-empty.
    assert join._analysis_index


def test_the_join_resolves_a_payload_from_a_process_that_never_loaded_the_parsers(tmp_path):
    """The observer's real process: artifacts written here, read over there.

    `telemetry` deliberately does not import `analysis.pipeline` (T12), so the
    registry fingerprint W3 §REGFP put in the settings key would be computed
    over an EMPTY registry in the observer's process unless deriving it LOADS
    the registry. The failure would be invisible in exactly the way
    FILENAME-BOUNDARY was: a key no run ever wrote, `payload_for` None on every
    document, `REASON_PAYLOAD_ABSENT` on every row, and an instrument that stays
    green while measuring nothing. The in-process tests above cannot see it —
    pytest imported the parsers long before they run — so this one seeds through
    `cached_analysis` here and resolves in a subprocess that asserts the parser
    package is unimported at the moment the join is built.
    """
    data_dir = tmp_path / "data"
    content_sha, payload = _seed_one_document(data_dir, cached_under="s.pdf")

    code = (
        "import sys, json;"
        "from telemetry.stated_counts import _ArtifactJoin;"
        "assert 'analysis.parser_registry_entries' not in sys.modules, "
        "'the parsers were already loaded; this proves nothing';"
        f"join = _ArtifactJoin({str(data_dir)!r});"
        f"print(json.dumps(join.payload_for({content_sha!r}, 's.pdf')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip().splitlines()[-1]) == payload

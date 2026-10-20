"""H-2 MoneyThumb comparison harness tests - synthetic fixtures ONLY.

No real benchmark content, no corpus statement content: every payload below
is hand-written fake data.  The only test touching the real corpus is the
manifest smoke test, which reads nothing but file bytes for hashing and
skips (named skip) when the corpus is absent.
"""
from __future__ import annotations

import json

import pytest

from benchmark.classify import (
    Outcome,
    PRE_RULINGS,
    UNSET,
    classify,
    values_match,
)
from benchmark.coverage import coverage_summary
from benchmark.manifest import SETS, verify_manifest
from benchmark.masking import mask_account, mask_structure, mask_text, transaction_ref
from benchmark.normalize import (
    MTStatementRow,
    collect_paths,
    last4,
    parse_bool,
    parse_date_any,
    parse_int,
    parse_money,
)
from benchmark.report import outcome_counts, write_csv_summary, write_set_report
from tests.statements import statements_dir


# --------------------------------------------------------------------------
# Classifier precedence: all 8 outcomes reachable.
# --------------------------------------------------------------------------

class TestClassifierPrecedence:
    def test_both_match_expected(self):
        row = classify("s", "f", 100.0, 100.0, expected=100.0)
        assert row.outcome is Outcome.BOTH_MATCH_EXPECTED

    def test_our_system_correct_against_audited_expectation(self):
        row = classify("s", "f", 100.0, 99.0, expected=100.0)
        assert row.outcome is Outcome.OUR_SYSTEM_CORRECT

    def test_moneythumb_correct_against_audited_expectation(self):
        row = classify("s", "f", 99.0, 100.0, expected=100.0)
        assert row.outcome is Outcome.MONEYTHUMB_CORRECT

    def test_both_incorrect(self):
        row = classify("s", "f", 98.0, 99.0, expected=100.0)
        assert row.outcome is Outcome.BOTH_INCORRECT

    def test_source_evidence_used_when_no_expectation(self):
        row = classify(
            "s", "f", 50.0, 51.0,
            source_value=50.0,
            source_evidence={"kind": "printed_summary", "detail": "fake"},
        )
        assert row.outcome is Outcome.OUR_SYSTEM_CORRECT
        assert row.evidence["kind"] == "printed_summary"

    def test_different_definition_never_forces_winner(self):
        row = classify(
            "s", "f", {"ours": 1}, {"mt": 2},
            different_definition={"ours": "def A", "moneythumb": "def B"},
        )
        assert row.outcome is Outcome.DIFFERENT_DEFINITION
        assert row.definitions == {"ours": "def A", "moneythumb": "def B"}

    def test_source_contradiction_with_withheld_value(self):
        row = classify(
            "s", "f", None, 985600.0,
            ours_withheld=True,
            contradiction="the document contradicts itself on this field",
        )
        assert row.outcome is Outcome.SOURCE_CONTRADICTION

    def test_agreement_without_evidence_is_insufficient(self):
        # Agreement is NOT evidence: never a "correct" bucket.
        row = classify("s", "f", 7, 7)
        assert row.outcome is Outcome.INSUFFICIENT_EVIDENCE

    def test_material_difference_without_evidence_is_unresolved(self):
        row = classify("s", "f", 7, 9, material=True)
        assert row.outcome is Outcome.UNRESOLVED
        assert row.for_ocean is True

    def test_immaterial_difference_without_evidence(self):
        row = classify("s", "f", 7, 9, material=False)
        assert row.outcome is Outcome.INSUFFICIENT_EVIDENCE

    def test_expectation_beats_source_evidence(self):
        # Precedence rule 2 before rule 3.
        row = classify(
            "s", "f", 100.0, 99.0,
            expected=100.0,
            source_value=99.0,
            source_evidence={"kind": "printed_summary"},
        )
        assert row.outcome is Outcome.OUR_SYSTEM_CORRECT

    def test_withheld_value_is_never_scored_incorrect(self):
        row = classify("s", "f", None, 5.0, expected=4.0, ours_withheld=True)
        assert row.outcome is Outcome.UNRESOLVED  # queued, not BOTH_INCORRECT
        row2 = classify("s", "f", None, 4.0, expected=4.0, ours_withheld=True)
        assert row2.outcome is Outcome.MONEYTHUMB_CORRECT
        assert "withheld by design" in row2.rationale


class TestPreRulings:
    def test_total_revenue_pre_ruling(self):
        row = classify("any_set", "mt_total_revenue_row", 1.0, 2.0, expected=1.0)
        assert row.outcome is Outcome.DIFFERENT_DEFINITION
        assert "net cash flow" in row.rationale
        assert row.evidence["kind"] == "ocean_pre_ruling"

    def test_bmo_ending_balance_pre_ruling(self):
        # Pre-ruling wins even when an expectation argument is supplied.
        row = classify("bmo_jan", "ending_balance", 1000000.0, 985600.0,
                       expected=1000000.0)
        assert row.outcome is Outcome.SOURCE_CONTRADICTION
        assert "985,600.00" in row.rationale

    def test_pre_ruling_scoped_to_set(self):
        row = classify("chase_dec", "ending_balance", 5.0, 5.0, expected=5.0)
        assert row.outcome is Outcome.BOTH_MATCH_EXPECTED

    def test_all_three_pre_rulings_present(self):
        assert ("*", "mt_total_revenue_row") in PRE_RULINGS
        assert ("bmo_jan", "ending_balance") in PRE_RULINGS
        # klr_may is a capability finding, not a field pre-ruling.
        assert not any(key[0] == "klr_may" for key in PRE_RULINGS)


# --------------------------------------------------------------------------
# Normalizer: synthetic MT payload value quirks.
# --------------------------------------------------------------------------

class TestNormalizer:
    def test_string_typed_numbers(self):
        assert parse_money("23250.00") == 23250.0
        assert parse_money("-255500.00") == -255500.0
        assert parse_money("1,234.56") == 1234.56

    def test_dot_zero_zero_is_zero(self):
        assert parse_money(".00") == 0.0

    def test_percent_strings(self):
        assert parse_money("0%") == 0.0
        assert parse_money("33%") == 33.0

    def test_null_and_garbage(self):
        assert parse_money(None) is None
        assert parse_money("") is None
        assert parse_money("null") is None
        assert parse_money("not-a-number") is None

    def test_bool_strings(self):
        assert parse_bool("true") is True
        assert parse_bool("false") is False
        assert parse_bool(True) is True
        assert parse_bool(None) is None
        assert parse_bool("maybe") is None

    def test_both_date_renderings(self):
        assert parse_date_any("Jan 1, 2054") == "2054-01-01"
        assert parse_date_any("2054-01-31") == "2054-01-31"
        assert parse_date_any("") is None

    def test_parse_int(self):
        assert parse_int("14") == 14
        assert parse_int(".00") == 0
        assert parse_int(None) is None

    def test_last4(self):
        assert last4("000000123456789") == "6789"
        assert last4("xxxx1234") == "1234"
        assert last4("unknown") is None
        assert last4("#299") == "299"

    def test_statement_row_from_synthetic_payload(self):
        raw = {
            "account": "xxxx1234",
            "start_date": "Jan 1, 2054",
            "ending_date": "Jan 31, 2054",
            "reconciled": "false",
            "starting_balance": "100.00",
            "ending_balance": ".00",
            "total_credits": "23250.00",
            "num_credits": "14",
            "total_debits": "255500.00",
            "num_debits": "27",
            "mca_withhold_percent": "12%",
        }
        row = MTStatementRow.from_raw(raw)
        assert row.account_last4 == "1234"
        assert row.start_date == "2054-01-01"
        assert row.reconciled is False
        assert row.ending_balance == 0.0
        assert row.num_credits == 14
        assert row.mca_withhold_percent == 12.0

    def test_collect_paths_collapses_list_indices(self):
        payload = {"a": [{"b": "1"}, {"b": "2", "c": None}], "d": []}
        paths = collect_paths(payload)
        assert paths == {"a[].b", "a[].c", "d[]"}


# --------------------------------------------------------------------------
# Masking on report emission.
# --------------------------------------------------------------------------

class TestMasking:
    def test_mask_account(self):
        assert mask_account("000000123456789") == "****6789"
        assert mask_account("1234") == "1234"
        assert mask_account(None) is None
        assert mask_account("unknown") == "unknown"

    def test_mask_text_long_digit_runs(self):
        assert mask_text("acct 123456789 ok") == "acct ****6789 ok"
        # Decimal amounts and ISO dates are untouched.
        assert mask_text("amount 255500.00 on 2054-01-31") == \
            "amount 255500.00 on 2054-01-31"

    def test_mask_text_mt_style(self):
        assert mask_text("xxxx1905") == "****1905"

    def test_transaction_ref_truncates(self):
        ref = transaction_ref({
            "date": "2054-01-02",
            "amount": -11788.0,
            "description": "X" * 100,
        })
        assert len(ref["description"]) == 40

    def test_report_emission_masks_synthetic_account_numbers(self, tmp_path):
        fake_report = {
            "set": "synthetic_set",
            "files": [{"path": "fake.pdf", "sha256": "AB" * 32}],
            "rows": [
                {
                    "set": "synthetic_set",
                    "field": "account_number",
                    "outcome": "UNRESOLVED",
                    "ours": "987654321",
                    "mt": "accountNumber 000000727099999",
                    "expected": None,
                    "ours_withheld": False,
                    "evidence": {"kind": "none", "detail": "acct 555666777 cited"},
                    "definitions": None,
                    "rationale": "synthetic row with 123456789 inside",
                    "for_ocean": True,
                },
            ],
            "outcome_counts": {"UNRESOLVED": 1},
            "capability_findings": [],
            "our_summary": [],
            "moneythumb": {},
            "notes": "",
        }
        path = write_set_report(tmp_path, fake_report)
        emitted = path.read_text(encoding="utf-8")
        for full in ("987654321", "000000727099999", "555666777", "123456789"):
            assert full not in emitted
        assert "****4321" in emitted and "****9999" in emitted
        csv_path = write_csv_summary(tmp_path, [fake_report])
        csv_text = csv_path.read_text(encoding="utf-8")
        for full in ("987654321", "000000727099999", "555666777", "123456789"):
            assert full not in csv_text

    def test_mask_structure_recurses(self):
        masked = mask_structure({"a": ["7000000001", {"b": "xxxx0002"}]})
        assert masked == {"a": ["****0001", {"b": "****0002"}]}


# --------------------------------------------------------------------------
# Coverage completeness on synthetic payloads.
# --------------------------------------------------------------------------

class TestCoverage:
    def test_known_paths_are_mapped(self):
        payload = {
            "appinfo": {"owner": "X", "webSearch": {"industry": None}},
            "file_status": [{"filename": "f.pdf", "statusCode": 200}],
            "scorecard": {
                "statements_summary": [{"total_credits": "1.00", "num_payroll": "0"}],
                "mca_transactions": [{"lender": "L", "amount": "-1.00"}],
                "daily_balances": [
                    {"event_date": "2054-01-01",
                     "balances": [{"acctid": "x", "balance": "1.00",
                                   "od_balance": "1.00", "true_balance": "1.00"}]}
                ],
            },
            "statement_summaries": [
                {"tid": "t", "results": [{"bankName": "B", "startBalance": 0.0}]}
            ],
        }
        summary = coverage_summary(collect_paths(payload))
        assert summary["complete"], summary["unmapped"]
        paths = summary["paths"]
        assert paths["scorecard.statements_summary[].total_credits"]["disposition"] == "compared"
        assert paths["appinfo.webSearch.industry"]["verdict"] == "IGNORE"
        assert paths["scorecard.daily_balances[].balances[].od_balance"]["verdict"] == "IGNORE (P3)"

    def test_unknown_path_fails_completeness(self):
        summary = coverage_summary({"scorecard.some_brand_new_field"})
        assert not summary["complete"]
        assert summary["unmapped"] == ["scorecard.some_brand_new_field"]

    def test_every_disposition_is_valid(self):
        from benchmark.coverage import RULES
        assert {rule.disposition for rule in RULES} <= {
            "compared", "skipped_by_verdict", "capability"
        }


# --------------------------------------------------------------------------
# Manifest smoke test (real corpus paths + hashes; named skip when absent).
# --------------------------------------------------------------------------

class TestManifest:
    def test_manifest_paths_and_hashes(self):
        corpus = statements_dir()
        if not corpus.is_dir():
            pytest.skip(f"benchmark corpus absent ({corpus} not found)")
        check = verify_manifest(corpus)
        assert check.ok, check.problems

    def test_manifest_covers_all_six_sets(self):
        assert [s.name for s in SETS] == [
            "bmo_jan", "chase_dec", "chase_jan_feb_mar",
            "field_trucking_nov", "klr_may", "wmb_may",
        ]
        for benchmark_set in SETS:
            assert len(benchmark_set.files) == len(benchmark_set.sha256)
            for digest in benchmark_set.sha256:
                assert len(digest) == 64

    def test_missing_file_reported(self, tmp_path):
        check = verify_manifest(tmp_path)
        assert not check.ok
        assert any("missing file" in p for p in check.problems)


# --------------------------------------------------------------------------
# Small helpers.
# --------------------------------------------------------------------------

class TestHelpers:
    def test_values_match_money_tolerance(self):
        assert values_match(100.0, 100.01)
        assert not values_match(100.0, 100.02)
        assert values_match("BMO", "bmo")
        assert values_match(None, None)
        assert not values_match(None, 0.0)

    def test_outcome_counts(self):
        rows = [
            classify("s", "a", 1, 1, expected=1),
            classify("s", "b", 1, 2, expected=1),
            classify("s", "c", 1, 2),
        ]
        counts = outcome_counts(rows)
        assert counts == {
            "BOTH_MATCH_EXPECTED": 1,
            "OUR_SYSTEM_CORRECT": 1,
            "UNRESOLVED": 1,
        }


# --------------------------------------------------------------------------
# Lender detection (2026-09-24, spec §7): flagged lenders are not misses.
# --------------------------------------------------------------------------

class TestFlaggedHere:
    @staticmethod
    def _set(flagged_positions):
        from benchmark.normalize import MTSet
        from benchmark.ourside import OurFileResult, OurSetResult

        mt = MTSet(
            name="synthetic", ok=True, http_status=200, uploaded_at=None,
            source_files=[], stub_message=None,
            response={"scorecard": {"mca_transactions": [
                {"lender": "FABRICATED ALT CAPITAL", "amount": "-100.00", "date": "2054-01-02"},
                {"lender": "FABRICATED ALT CAPITAL", "amount": "-100.00", "date": "2054-01-09"},
            ]}},
            paths=set(), summary_rows=[], result_rows=[],
        )
        payload = {
            "statement": {"transactions": []},
            "metrics": {},
            "detection": {
                "known_funders": [],
                "potential_lenders": [],
                "flagged_positions": flagged_positions,
            },
        }
        ours = OurSetResult(
            set_name="synthetic",
            files=[OurFileResult(relative_path="synthetic.pdf", source_type="digital/native",
                                 markdown="", payload=payload)],
        )
        return ours, mt

    def test_a_flagged_moneythumb_lender_is_flagged_here_not_missed(self):
        from benchmark.compare import build_mca_rows

        ours, mt = self._set([{
            "group": "alternative_positions", "payee": "FABRICATED ALT CAPITAL",
            "matched_alias": "FABRICATED ALT CAPITAL", "count": 2, "total_debited": 200.0,
            "cadence": "weekly", "avg_gap_days": 7.0, "first_date": "2054-01-02",
            "last_date": "2054-01-09", "source_locations": ["transaction:1", "transaction:2"],
        }])
        rows = {row.field: row for row in build_mca_rows("synthetic", ours, mt)}
        count_row = rows["mca.FABRICATED ALT CAPITAL.withdrawal_count"]
        assert count_row.outcome is Outcome.DIFFERENT_DEFINITION
        assert not count_row.for_ocean
        assert (count_row.ours, count_row.mt) == (2, 2)
        assert "flagged here" in count_row.rationale
        aggregate = rows["mca_lender_set"]
        assert aggregate.outcome is Outcome.DIFFERENT_DEFINITION
        assert "FABRICATED ALT CAPITAL" in aggregate.rationale

    def test_an_unflagged_moneythumb_lender_is_still_a_miss(self):
        from benchmark.compare import build_mca_rows

        ours, mt = self._set([])
        rows = {row.field: row for row in build_mca_rows("synthetic", ours, mt)}
        count_row = rows["mca.FABRICATED ALT CAPITAL.withdrawal_count"]
        assert count_row.outcome is not Outcome.DIFFERENT_DEFINITION
        assert count_row.for_ocean

    def test_the_old_non_mca_scope_set_is_gone(self):
        import benchmark.lenders as lenders

        assert not hasattr(lenders, "NON_MCA_SCOPE")

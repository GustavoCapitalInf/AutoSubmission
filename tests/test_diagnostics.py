"""W3-2 withheld diagnostics: the taxonomy, the invariants, and the drift guard.

The corpus-wide anchor (the pinned 3 withheld reproduce their documented
diagnosis, the 106 produce nothing) is corpus-marked and lives in
`test_telemetry_corpus.py`. Everything here is fast and runs by default.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from telemetry import build_record, dispatch_section, document_section, source_section
from telemetry.diagnostics import (
    ADB_CHECKS,
    ADB_WARNING_ANCHORS,
    ADVISORY_CODES,
    CLASS_OF,
    CLASS_PRECEDENCE,
    DIAGNOSABLE_CLASSES,
    INTEGRITY_FLAGS,
    RECON_ISSUE_ANCHORS,
    SUMMARY_FIELDS,
    UNATTRIBUTED,
    VOCABULARY,
    diagnose,
    empty_diagnostics,
)
from telemetry.report import (
    UnattributedParsers,
    diagnostics_rollup,
    render_diagnostics,
)

ROOT = Path(__file__).resolve().parents[1]

DIAGNOSTICS_KEYS = {
    "evaluated", "diagnostics_version", "primary_class", "classes", "codes",
    "adb_checks_failed", "integrity_flags", "summary_fields_absent", "counts",
    "unmapped",
}


def _payload(**overrides) -> dict:
    payload = {
        "statement": {"transactions": []},
        "reconciliation": {"issues": [], "continuity_breaks": 0},
        "metrics": {"average_daily_balance": None, "adb": {"validations": {}, "warnings": []}},
        "integrity": {"flags": []},
        "quality": {"corporate_use": "manual_review_required"},
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


# --- scope ------------------------------------------------------------------


def test_only_refused_and_flagged_documents_are_diagnosed():
    """A document nobody questioned needs no autopsy.

    COUNTS-P2 widened this from `withheld` alone to `withheld` and `review`,
    per the standing 2026-08-10 Ocean ruling. The reason is not that `review`
    became interesting in general: it is that phase 2 emits count codes whose
    ONLY outcome class is `review`, so a `withheld`-only scope would have made
    the new vocabulary unreadable in the rollup that exists. `validated` is
    the class that must stay silent, and it is the one this asserts.
    """
    assert DIAGNOSABLE_CLASSES == ("withheld", "review")
    for outcome in ("validated", "failed", "deferred"):
        assert diagnose(_payload(), outcome) == empty_diagnostics()


def test_a_review_document_is_diagnosed_from_the_flags_that_put_it_there():
    """The point of widening the scope: the count codes reach the rollup."""
    payload = _payload(integrity={"flags": ["credit_count_mismatch"]})
    section = diagnose(payload, "review")
    assert section["evaluated"] is True
    assert "integrity:credit_count_mismatch" in section["codes"]
    assert section["primary_class"] == "detail_coverage"


def test_an_empty_diagnostic_reports_no_counts_rather_than_zeros():
    """H3_SCHEMA I5: a validated document has no failing-check count of zero."""
    empty = empty_diagnostics()
    assert empty["evaluated"] is False
    assert empty["counts"] == {}
    assert empty["primary_class"] is None
    assert set(empty) == DIAGNOSTICS_KEYS


def test_a_withheld_document_with_no_payload_is_not_diagnosed():
    assert diagnose(None, "withheld") == empty_diagnostics()


# --- the taxonomy ------------------------------------------------------------


def test_a_failing_adb_check_becomes_its_own_code():
    payload = _payload(metrics={
        "average_daily_balance": None,
        "adb": {
            "validations": {
                "ledger_reconciles_to_closing": False,
                "covers_opening_day": True,
            },
            "warnings": [],
        },
    })
    result = diagnose(payload, "withheld")
    assert result["adb_checks_failed"] == ["ledger_reconciles_to_closing"]
    assert "adb:ledger_reconciles_to_closing" in result["codes"]
    assert "adb:covers_opening_day" not in result["codes"]
    assert result["primary_class"] == "ledger_identity"


@pytest.mark.parametrize(
    ("issue", "code"),
    [
        ("cannot run sum check: missing beginning or ending balance",
         "recon:sum_check_inputs_missing"),
        ("sum check off by +2943.45: beginning -78.68 + transactions +6319.55 = "
         "6240.87, but stated ending is 3297.42", "recon:sum_check_failed"),
        ("bank-stated summary does not reconcile (off by +1203.77): beginning ...",
         "recon:summary_identity_failed"),
        ("captured $1,009.67 of the bank's stated $3,953.12 in credits (26%) - ...",
         "recon:credit_coverage_short"),
        ("captured $1,009.67 of the bank's stated $3,953.12 in debits (26%) - ...",
         "recon:debit_coverage_short"),
        ("escalation extraction failed (ValueError); using primary extraction",
         "recon:escalation_extraction_failed"),
        ("row 7 ('ACH DEBIT PAYMENT'): balance jumped to 2763.69, expected 14014.31",
         "recon:running_balance_break"),
    ],
)
def test_every_reconciliation_issue_shape_maps(issue: str, code: str):
    payload = _payload(reconciliation={"issues": [issue], "continuity_breaks": 0})
    assert code in diagnose(payload, "withheld")["codes"]


def test_a_reconciliation_issue_is_anchored_on_our_prefix_not_the_description():
    """A statement must not be able to choose its own diagnostic bucket.

    The continuity issue interpolates a transaction description, so matching on
    a bare substring would let a document containing another rule's wording
    misroute itself. Prefix-anchoring puts the decision in text analysis/ wrote.
    """
    hostile = (
        "row 3 ('PAYMENT sum check off by 1.00 cannot run sum check bank-stated "
        "summary does not reconcile'): balance jumped to 10.00, expected 11.00"
    )
    codes = diagnose(
        _payload(reconciliation={"issues": [hostile], "continuity_breaks": 1}),
        "withheld",
    )["codes"]
    assert codes == ["recon:running_balance_break"]


@pytest.mark.parametrize("needle,code", list(ADB_WARNING_ANCHORS))
def test_every_adb_warning_anchor_maps(needle: str, code: str):
    payload = _payload(metrics={
        "average_daily_balance": None,
        "adb": {"validations": {}, "warnings": [f"prefix {needle} suffix"]},
    })
    assert code in diagnose(payload, "withheld")["codes"]


def test_an_integrity_flag_becomes_its_own_code():
    payload = _payload(integrity={"flags": ["conflicting_statement_summaries"]})
    result = diagnose(payload, "withheld")
    assert result["integrity_flags"] == ["conflicting_statement_summaries"]
    assert result["primary_class"] == "source_contradiction"


def test_summary_field_absence_is_reported_by_name():
    payload = _payload(statement={
        "transactions": [],
        "period_start": "2026-01-01",
        "beginning_balance": 10.0,
    })
    absent = diagnose(payload, "withheld")["summary_fields_absent"]
    assert "period_start" not in absent
    assert "beginning_balance" not in absent
    assert "ending_balance" in absent
    assert set(absent) <= set(SUMMARY_FIELDS)


# --- precedence --------------------------------------------------------------


def test_the_primary_class_names_the_cause_not_the_symptom():
    """A ledger that fails BECAUSE detail is incomplete reports the coverage.

    This is the Ace_Auto ordering: `detail_coverage` outranks `ledger_identity`
    precisely so remediation is aimed at the missing detail rather than at the
    arithmetic that noticed it.
    """
    payload = _payload(
        reconciliation={
            "issues": [
                "sum check off by +1.00: ...",
                "captured $1.00 of the bank's stated $2.00 in debits (50%) - ...",
            ],
            "continuity_breaks": 0,
        },
        integrity={"flags": ["ledger_sum_mismatch", "debit_detail_coverage_mismatch"]},
    )
    result = diagnose(payload, "withheld")
    assert result["primary_class"] == "detail_coverage"
    assert result["classes"] == ["detail_coverage", "ledger_identity"]


def test_classes_are_listed_in_precedence_order():
    payload = _payload(
        reconciliation={"issues": ["sum check off by +1.00: ..."], "continuity_breaks": 0},
        integrity={"flags": [
            "conflicting_statement_summaries", "missing_declared_statement_page",
        ]},
    )
    classes = diagnose(payload, "withheld")["classes"]
    ranks = [CLASS_PRECEDENCE.index(name) for name in classes]
    assert ranks == sorted(ranks)
    assert classes[0] == "source_contradiction"


def test_a_withheld_document_the_taxonomy_cannot_explain_says_so():
    """Silence is a finding, not a pass."""
    result = diagnose(_payload(), "withheld")
    assert result["evaluated"] is True
    assert result["codes"] == []
    assert result["primary_class"] == "undiagnosed"


def test_a_crashed_integrity_check_makes_the_diagnosis_incomplete():
    """W3-2b. A registered integrity check that RAISED means its finding is
    UNKNOWN, not clean - so the diagnosis outranks every financial class.

    Concretely: the check that crashed is typically the one that would have
    produced `source_contradiction`. Reporting `ledger_identity` because the
    contradiction check never got to run would present an incomplete diagnosis
    as a confident one.
    """
    payload = _payload(
        reconciliation={"issues": ["sum check off by +1.00: ..."], "continuity_breaks": 0},
        integrity={"flags": ["ledger_sum_mismatch", "integrity_check_exception"]},
    )
    result = diagnose(payload, "withheld")
    assert result["primary_class"] == "check_unavailable"
    assert result["classes"] == ["check_unavailable", "ledger_identity"]
    assert "integrity:integrity_check_exception" in result["codes"]


def test_check_unavailable_outranks_every_financial_class():
    financial = (
        "source_contradiction", "period_integrity", "summary_field_missing",
        "summary_identity", "detail_coverage", "posting_date_coverage",
        "balance_continuity", "ledger_identity", "daily_ledger_structure",
        "page_coverage",
    )
    rank = CLASS_PRECEDENCE.index("check_unavailable")
    for name in financial:
        assert rank < CLASS_PRECEDENCE.index(name), name


def test_a_parser_crash_leaves_no_diagnosis_to_be_incomplete():
    """The distinction W3-2b turns on, asserted directly.

    A crashed integrity check happens INSIDE a diagnosis and makes it partial.
    A crashed parser happens BEFORE any claim, so the document produces no
    diagnosis at all - it lands in `failed`, which is not diagnosable. The flag
    stays advisory so a crash can never outrank the financial check that
    actually withheld a document that did reach the checks.
    """
    assert "integrity:parser_exception" in ADVISORY_CODES
    assert "integrity:integrity_check_exception" not in ADVISORY_CODES

    # A parser that crashed outright: no payload, so nothing is diagnosed.
    assert diagnose(None, "failed") == empty_diagnostics()

    # And on a document that DID reach the checks, the crash flag is evidence
    # but never the class.
    payload = _payload(
        integrity={"flags": ["parser_exception", "ledger_sum_mismatch"]},
    )
    result = diagnose(payload, "withheld")
    assert "integrity:parser_exception" in result["codes"]
    assert result["primary_class"] == "ledger_identity"


def test_advisory_only_evidence_gets_its_own_class():
    payload = _payload(integrity={"flags": ["transaction_detail_not_corporate_reliable"]})
    assert diagnose(payload, "withheld")["primary_class"] == "advisory_only"


# --- nothing is silently dropped ---------------------------------------------


def test_an_unknown_adb_check_lands_in_the_unmapped_bucket():
    payload = _payload(metrics={
        "average_daily_balance": None,
        "adb": {"validations": {"a_brand_new_check": False}, "warnings": []},
    })
    result = diagnose(payload, "withheld")
    assert "adb:unmapped" in result["codes"]
    assert result["unmapped"] == ["adb:a_brand_new_check"]
    assert result["primary_class"] == "unmapped"
    assert "a_brand_new_check" in result["adb_checks_failed"]


def test_an_unknown_integrity_flag_lands_in_the_unmapped_bucket():
    result = diagnose(_payload(integrity={"flags": ["a_brand_new_flag"]}), "withheld")
    assert "integrity:unmapped" in result["codes"]
    assert result["unmapped"] == ["integrity:a_brand_new_flag"]


def test_an_unknown_free_text_issue_is_counted_never_stored():
    """The unmapped bucket for free text is a COUNT: the string may quote a
    transaction, so it can never travel."""
    payload = _payload(
        reconciliation={
            "issues": ["SOMETHING NEW about ACME PLUMBING LLC for 1,234.56"],
            "continuity_breaks": 0,
        },
        metrics={
            "average_daily_balance": None,
            "adb": {"validations": {}, "warnings": ["also new: 2026-01-01 999.99"]},
        },
    )
    result = diagnose(payload, "withheld")
    assert result["codes"] == ["adb_state:unmapped_warning", "recon:unmapped_issue"]
    assert result["counts"]["unmapped_reconciliation_issues"] == 1
    assert result["counts"]["unmapped_adb_warnings"] == 1
    assert result["unmapped"] == []
    blob = json.dumps(result)
    assert "ACME PLUMBING" not in blob
    assert "1,234.56" not in blob
    assert "999.99" not in blob


# --- the vocabulary is closed and matches analysis/ --------------------------


def test_every_code_is_either_classed_or_declared_advisory():
    """A new code cannot fall out of the class map by accident."""
    assert set(CLASS_OF) | ADVISORY_CODES == set(VOCABULARY)
    assert not (set(CLASS_OF) & ADVISORY_CODES)
    assert set(CLASS_OF.values()) <= set(CLASS_PRECEDENCE)


def test_the_class_precedence_list_has_no_duplicates():
    assert len(set(CLASS_PRECEDENCE)) == len(CLASS_PRECEDENCE)


def test_the_precedence_table_in_the_taxonomy_doc_matches_the_code():
    """Doc/code guard, added in W3-2b.

    Inserting `check_unavailable` at rank 4 left every row below it numbered
    one too low. The ranking is what W3-4's remediation queue inherits, so a
    stale table is a wrong instruction, not a typo.
    """
    import re

    doc = (ROOT / "docs" / "moneythumb-replacement" / "W3_2_TAXONOMY.md")
    rows = re.findall(
        r"^\| (\d+) \| `([a-z_]+)` \|", doc.read_text(encoding="utf-8"), re.MULTILINE
    )
    table = [(int(rank), name) for rank, name in rows if name in set(CLASS_PRECEDENCE)]
    assert table == [
        (index + 1, name) for index, name in enumerate(CLASS_PRECEDENCE)
    ], "W3_2_TAXONOMY.md section 4 no longer matches CLASS_PRECEDENCE"


def test_adb_check_names_match_the_analysis_source():
    """Drift guard: a new check in analysis/adb.py fails this, loudly."""
    source = (ROOT / "analysis" / "adb.py").read_text(encoding="utf-8")
    found = set(re.findall(r'checks\["([a-z_]+)"\]\s*=', source))
    assert found == set(ADB_CHECKS), (
        "analysis/adb.py's validation vocabulary changed; update "
        "telemetry/diagnostics.py ADB_CHECKS and W3_2_TAXONOMY.md"
    )


def test_integrity_flag_names_match_the_analysis_source():
    source = (ROOT / "analysis" / "pipeline.py").read_text(encoding="utf-8")
    found = set(re.findall(r'flags\.append\("([a-z_]+)"\)', source))
    assert found == set(INTEGRITY_FLAGS), (
        "analysis/pipeline.py's integrity vocabulary changed; update "
        "telemetry/diagnostics.py INTEGRITY_FLAGS and W3_2_TAXONOMY.md"
    )


def test_reconciliation_issue_sites_match_the_anchor_count():
    """Issue strings are f-strings, so the guard counts CALL SITES.

    A new `issues.append(...)` anywhere in the two files that write them means
    a shape this module has never seen; it would land in `recon:unmapped_issue`
    (never dropped), and this test says so before the run does.
    """
    sites = sum(
        len(re.findall(r"issues\.append\(", (ROOT / name).read_text(encoding="utf-8")))
        for name in ("analysis/reconcile.py", "analysis/pipeline.py")
    )
    assert sites == len(RECON_ISSUE_ANCHORS), (
        "a reconciliation issue was added or removed; update "
        "telemetry/diagnostics.py RECON_ISSUE_ANCHORS and W3_2_TAXONOMY.md"
    )


def test_adb_warning_sites_match_the_anchor_count():
    source = (ROOT / "analysis" / "adb.py").read_text(encoding="utf-8")
    sites = len(re.findall(r"warnings\.append\(", source))
    assert sites == len(ADB_WARNING_ANCHORS), (
        "an ADB warning was added or removed; update "
        "telemetry/diagnostics.py ADB_WARNING_ANCHORS and W3_2_TAXONOMY.md"
    )


def test_summary_field_names_exist_on_the_statement_schema():
    from analysis.schema import Statement

    assert set(SUMMARY_FIELDS) <= set(Statement.model_fields)


# --- read-only, and non-sensitive --------------------------------------------


def test_diagnosis_does_not_touch_the_payload():
    """Diagnostics are a projection. Proven, not asserted in prose."""
    payload = _payload(
        reconciliation={"issues": ["sum check off by +1.00: ..."], "continuity_breaks": 2},
        integrity={"flags": ["ledger_sum_mismatch"]},
        metrics={
            "average_daily_balance": None,
            "adb": {"validations": {"covers_closing_day": False}, "warnings": ["x"]},
        },
    )
    before = copy.deepcopy(payload)
    diagnose(payload, "withheld")
    assert payload == before
    assert json.dumps(payload, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_no_statement_text_reaches_the_diagnostics_section():
    """The I1 canary: every free-text source is poisoned, nothing survives."""
    canary_desc = "ZZCANARYDESC PAYROLL ACME"
    canary_amount = "98,765.43"
    canary_date = "2031-07-04"
    payload = _payload(
        statement={
            "transactions": [
                {"description": canary_desc, "amount": 98765.43, "running_balance": 1.0},
            ],
            "bank": "ZZCANARYBANK",
            "account_number": "9911223344",
            "period_start": canary_date,
        },
        reconciliation={
            "issues": [
                f"row 0 ({canary_date} '{canary_desc}'): balance jumped to {canary_amount}, "
                f"expected 1.00 (0.00 plus intervening transactions +{canary_amount})",
                f"sum check off by +{canary_amount}: beginning {canary_amount} ...",
            ],
            "continuity_breaks": 1,
        },
        metrics={
            "average_daily_balance": None,
            "adb": {
                "validations": {"ledger_reconciles_to_closing": False},
                "warnings": [
                    f"ledger does not reconcile (off by +{canary_amount}): opening ...",
                    f"transaction running balances do not support the reconstructed "
                    f"end-of-day balance on {canary_date}",
                ],
                "missing_posting_dates": [canary_date, "2031-07-05"],
                "calendar_day_count": 31,
            },
        },
        integrity={"flags": ["ledger_sum_mismatch"], "notes": [canary_desc]},
    )
    blob = json.dumps(diagnose(payload, "withheld"), sort_keys=True)
    for canary in (canary_desc, canary_amount, canary_date, "ZZCANARYBANK", "9911223344"):
        assert canary not in blob, f"{canary!r} leaked into diagnostics"
    # the dates are gone but the COUNT of them survives, which is the point
    assert json.loads(blob)["counts"]["missing_posting_dates"] == 2
    assert json.loads(blob)["counts"]["calendar_days"] == 31


# --- the record and the rollup ----------------------------------------------


def _record(payload, parser_id="chase") -> dict:
    class _Dispatch:
        outcome = "claimed"
        parser_id = None
        detection = None
        candidates = ()
        attempted = ()

    dispatch = _Dispatch()
    dispatch.parser_id = parser_id
    return build_record(
        run_id="run-1",
        emitter="batch",
        document=document_section("A" * 64, 10, None),
        source=source_section(None),
        dispatch=dispatch_section(dispatch, [], 46),
        stages={},
        model_calls=[],
        payload=payload,
    )


def test_the_record_carries_the_diagnostics_section():
    record = _record(_payload(integrity={"flags": ["summary_math_inconsistent"]}))
    assert record["outcome"]["class"] == "withheld"
    assert set(record["diagnostics"]) == DIAGNOSTICS_KEYS
    assert record["diagnostics"]["primary_class"] == "summary_identity"


def test_a_validated_record_carries_an_empty_diagnostics_section():
    payload = _payload(
        metrics={"average_daily_balance": 100.0, "adb": {}},
        quality={"corporate_use": "approved"},
    )
    record = _record(payload)
    assert record["outcome"]["class"] == "validated"
    assert record["diagnostics"] == empty_diagnostics()


def test_the_rollup_is_failure_class_by_parser_by_volume():
    records = [
        _record(_payload(integrity={"flags": ["summary_math_inconsistent"]}), "chase"),
        _record(_payload(integrity={"flags": ["summary_math_inconsistent"]}), "chase"),
        _record(_payload(integrity={"flags": ["missing_declared_statement_page"]}), "bmo"),
        _record(
            _payload(metrics={"average_daily_balance": 1.0, "adb": {}},
                     quality={"corporate_use": "approved"}),
            "wells",
        ),
    ]
    rollup = diagnostics_rollup(records)
    assert rollup["total"] == 4
    assert rollup["diagnosed"] == 3
    assert rollup["classes"] == {"summary_identity": 2, "page_coverage": 1}
    assert rollup["class_parser"] == [
        ["summary_identity", "chase", 2],
        ["page_coverage", "bmo", 1],
    ]
    assert rollup["codes"]["integrity:summary_math_inconsistent"] == 2
    assert rollup["unmapped"] == {
        "names": {}, "reconciliation_issues": 0, "adb_warnings": 0,
    }
    rendered = render_diagnostics(rollup, "run-1")
    assert "summary_identity" in rendered and "chase" in rendered
    assert rendered.isascii()


def test_an_unattributed_rollup_errors_rather_than_printing_a_none_column():
    """W3-2b ruling 2, applied to the W3-2 rollup as well as the W3-4 tooling.

    Both are class x parser views and both had the same footgun: a cache-served
    run printed a complete-LOOKING table whose every parser column read
    `(none)`. Measured on the pinned 109 served from the D-3 cache, that is
    exactly what happened.
    """
    records = [
        _record(_payload(integrity={"flags": ["summary_math_inconsistent"]}), None)
        for _ in range(3)
    ]
    with pytest.raises(UnattributedParsers) as caught:
        diagnostics_rollup(records)
    message = str(caught.value)
    assert "3 of 3" in message
    assert "--no-cache" in message
    assert "--allow-unattributed" in message

    rollup = diagnostics_rollup(records, allow_unattributed=True)
    assert rollup["unattributed_documents"] == 3
    assert rollup["class_parser"] == [["summary_identity", UNATTRIBUTED, 3]]
    rendered = render_diagnostics(rollup)
    assert "WARNING --allow-unattributed" in rendered
    assert rendered.isascii()


def test_an_attributed_rollup_needs_no_flag():
    records = [_record(_payload(integrity={"flags": ["summary_math_inconsistent"]}))]
    rollup = diagnostics_rollup(records)
    assert rollup["unattributed_documents"] == 0
    assert "WARNING --allow-unattributed" not in render_diagnostics(rollup)


def test_a_mixed_vocabulary_rollup_says_so():
    """The re-baseline must be visible, not reconciled silently."""
    old = _record(_payload(integrity={"flags": ["summary_math_inconsistent"]}))
    old["diagnostics"]["diagnostics_version"] = 1
    new = _record(_payload(integrity={"flags": ["summary_math_inconsistent"]}))
    rollup = diagnostics_rollup([old, new])
    # `new` is emitted at whatever the CURRENT vocabulary is, so this literal
    # moves with every bump — which is the point: a rollup spanning versions
    # must name them. v4 is REPAIR-GUARD/PIPE5 (`integrity:repair_exception`
    # added, classed `extraction_failure`); v3 was COUNTS-P2 (two new codes AND
    # a widened diagnosable scope, doubly non-comparable).
    assert rollup["diagnostics_versions"] == {"1": 1, "4": 1}
    assert "WARNING mixed taxonomy versions" in render_diagnostics(rollup)


def test_the_rollup_survives_a_record_written_before_diagnostics_existed():
    record = _record(_payload())
    record.pop("diagnostics")
    rollup = diagnostics_rollup([record])
    assert rollup == {
        "total": 1, "diagnosed": 0, "classes": {}, "codes": {},
        "adb_checks_failed": {}, "parsers": {}, "class_parser": [],
        "diagnostics_versions": {}, "unattributed_documents": 0,
        "unmapped": {"names": {}, "reconciliation_issues": 0, "adb_warnings": 0},
    }
    assert render_diagnostics(rollup).isascii()


def test_the_rollup_command_runs_over_a_jsonl_file(tmp_path, capsys):
    from telemetry.emit import JsonlSink
    from telemetry.report import main

    sink = JsonlSink(tmp_path / "run.jsonl")
    sink.write(_record(_payload(integrity={"flags": ["summary_math_inconsistent"]})))
    sink.write(_record(_payload(integrity={"flags": ["ledger_sum_mismatch"]}), "bmo"))
    assert main(["--jsonl", str(sink.path), "--diagnostics"]) == 0
    out = capsys.readouterr().out
    assert "withheld diagnostics" in out
    assert "diagnosed 2 of 2 documents" in out
    assert "summary_identity" in out and "ledger_identity" in out


def test_the_rollup_command_emits_json(tmp_path, capsys):
    from telemetry.emit import JsonlSink
    from telemetry.report import main

    sink = JsonlSink(tmp_path / "run.jsonl")
    sink.write(_record(_payload(integrity={"flags": ["summary_math_inconsistent"]})))
    assert main(["--jsonl", str(sink.path), "--diagnostics", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["classes"] == {"summary_identity": 1}


def test_breakdown_by_diagnostic_class(tmp_path):
    from telemetry.report import render_breakdown

    records = [
        _record(_payload(integrity={"flags": ["summary_math_inconsistent"]})),
        _record(
            _payload(metrics={"average_daily_balance": 1.0, "adb": {}},
                     quality={"corporate_use": "approved"}),
        ),
    ]
    rendered = render_breakdown(records, "diagnostic_class")
    assert "summary_identity" in rendered
    assert "(not diagnosed)" in rendered

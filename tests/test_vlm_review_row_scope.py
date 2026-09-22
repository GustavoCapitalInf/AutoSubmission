"""Synthetic row/metadata isolation; no customer files, network or inference."""
import copy
import json
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.review import candidate_records, confidence_summary, merge_review
from vlm.review_batches import ReviewReply, review_batched_page
from vlm.schema import PAGE_REVIEW_SCHEMA, empty_review


def _rows(count=2):
    return [CandidateRow("2031-01-02", "01/02", f"SYNTHETIC exact {index}", Decimal("10"),
                         "credit", None, 1, "stage_a", f"b0t0r{index}", "column", None, Decimal("10"))
            for index in range(count)]


def _payload(rows, *, added=True):
    payload = empty_review("statement_page")
    payload["account"].update(bank="SYNTHETIC BANK", currency="USD", beginning_balance=100,
                              ending_balance=120, period_start="2031-01-01", period_end="2031-01-31")
    payload["account_numbers_seen"] = ["SYNTHETIC-001"]
    payload["daily_balances"] = [{"date": "2031-01-02", "balance": 120}]
    payload["reviews"] = [{"candidate_id": record["candidate_id"], "verdict": "confirm",
                           "observed_description": record["row"]["description"],
                           "corrections": [], "reason": ""} for record in candidate_records(rows)]
    if added:
        row = {**candidate_records(rows)[0]["row"], "description": "SYNTHETIC added"}
        payload["added"] = [{"row": row, "after_candidate_id": "p1r0"}]
    return payload


def _correction(payload, rows, *, field, corrected, original=None):
    source = candidate_records(rows)[0]["row"]
    payload["reviews"][0].update(verdict="correct", corrections=[{
        "field": field, "original": source[field] if original is None else original, "corrected": corrected,
    }])
    if field == "description":
        payload["reviews"][0]["observed_description"] = corrected


@pytest.mark.parametrize("mutation", [
    lambda p, r: p["reviews"][0].update(observed_description="SYNTHETIC different"),
    lambda p, r: p["reviews"][0].update(observed_description=None),
    lambda p, r: p["reviews"][0].update(verdict="unresolved", observed_description=None),
    lambda p, r: p["reviews"][0].update(verdict="correct"),
    lambda p, r: p["reviews"][0].update(verdict="unrecognized"),
    lambda p, r: p["reviews"][0].pop("verdict"),
    lambda p, r: p["reviews"][0].update(extra="SYNTHETIC unsupported field"),
    lambda p, r: _correction(p, r, field="date", corrected="2031-02-30"),
    lambda p, r: _correction(p, r, field="amount", corrected=True),
    lambda p, r: _correction(p, r, field="description", corrected="SYNTHETIC corrected", original="wrong original"),
    lambda p, r: p["reviews"][0].update(verdict="correct", corrections=[{"field": "not_a_field", "original": None, "corrected": None}]),
    lambda p, r: p["reviews"][0].update(verdict="correct", corrections="malformed"),
])
def test_bad_identified_row_preserves_peer_addition_metadata_and_raw_evidence(mutation):
    rows = _rows()
    payload = _payload(rows)
    mutation(payload, rows)
    original = copy.deepcopy(payload)
    result = merge_review(rows, payload, page=1)
    assert result.errors == ()
    assert result.counts == {"agreed": 1, "corrected": 0, "added": 1, "rejected": 0, "unresolved": 1}
    assert [row.description for row in result.rows] == ["SYNTHETIC added", rows[1].description]
    assert result.account == payload["account"]
    assert result.daily_balances == tuple(payload["daily_balances"])
    bad = next(item for item in result.evidence if item["candidate_id"] == "p1r0")
    assert bad["validation_errors"] and bad["state"] == "unresolved"
    assert bad["raw_review"] == original["reviews"][0]
    assert payload == original and rows[0].source == "stage_a"
    assert confidence_summary([result], gate_admitted=True)["score"] == 0


@pytest.mark.parametrize("observation", ["SYNTHETIC stray", "", 123, [], {"synthetic": True}])
def test_reject_stray_observation_is_warning_with_raw_evidence_preserved(observation):
    rows = _rows()
    payload = _payload(rows)
    payload["reviews"][0].update(verdict="reject", observed_description=observation, reason="Not a transaction")
    before = copy.deepcopy(payload)
    result = merge_review(rows, payload, page=1)
    assert result.errors == () and result.counts["rejected"] == 1 and result.counts["unresolved"] == 0
    rejected = next(item for item in result.evidence if item["candidate_id"] == "p1r0")
    assert rejected["observed_description"] is None
    assert rejected["raw_observed_description"] == observation
    assert rejected["raw_review"] == before["reviews"][0]
    assert rejected["validation_errors"] == []
    assert rejected["validation_warnings"] == ["review_unexpected_description_observation"]
    assert result.counts["agreed"] == result.counts["added"] == 1
    assert payload == before
    payload["reviews"][0]["observed_description"] = "changed afterward"
    assert rejected["raw_review"] == before["reviews"][0]


def test_reject_normalization_does_not_ignore_other_invalid_protocol_fields():
    rows = _rows()
    payload = _payload(rows)
    payload["reviews"][0].update(verdict="reject", observed_description="SYNTHETIC stray",
                                   corrections=[{"field": "amount", "original": 10, "corrected": 11}])
    result = merge_review(rows, payload, page=1)
    assert not result.errors and result.counts["unresolved"] == 1
    assert result.counts["agreed"] == result.counts["added"] == 1
    assert "review_unexpected_replacement" in result.evidence[0]["validation_errors"]


@pytest.mark.parametrize("verdict,expected", [("confirm", "unresolved"), ("correct", "unresolved"), ("reject", "rejected")])
def test_source_candidate_errors_apply_only_to_that_retained_candidate(verdict, expected):
    rows = _rows()
    payload = _payload(rows)
    if verdict == "correct":
        _correction(payload, rows, field="description", corrected="SYNTHETIC corrected")
    elif verdict == "reject":
        payload["reviews"][0].update(verdict="reject", observed_description=None)
    result = merge_review(rows, payload, page=1,
                          candidate_validation_errors={"p1r0": ("proposal_recovery_crop_incomplete",)})
    assert not result.errors and result.counts[expected] == 1
    assert result.counts["agreed"] == result.counts["added"] == 1
    item = next(item for item in result.evidence if item["candidate_id"] == "p1r0")
    assert item["validation_errors"] == ["proposal_recovery_crop_incomplete"]
    assert all("proposal_recovery_crop_incomplete" not in item["validation_errors"]
               for item in result.evidence if item["candidate_id"] != "p1r0")


@pytest.mark.parametrize("bad_addition", [
    None,
    {},
    {"row": {"description": "SYNTHETIC partial"}, "after_candidate_id": "p1r1"},
])
def test_malformed_addition_is_attributable_by_index_and_does_not_hold_peers(bad_addition):
    rows = _rows()
    payload = _payload(rows)
    payload["added"].append(bad_addition)
    result = merge_review(rows, payload, page=1)
    assert not result.errors and len(result.rows) == 3
    assert result.counts["agreed"] == 2 and result.counts["added"] == result.counts["unresolved"] == 1
    bad = next(item for item in result.evidence if item["candidate_id"] == "p1a1")
    assert bad["raw_addition"] == bad_addition
    assert bad["validation_errors"] == ["review_addition_schema_invalid"]


@pytest.mark.parametrize("change", ["unknown_anchor", "missing_anchor", "amount", "bbox"])
def test_invalid_addition_keeps_valid_addition_and_source_fields(change):
    rows = _rows()
    payload = _payload(rows)
    bad = copy.deepcopy(payload["added"][0])
    if change == "unknown_anchor":
        bad["after_candidate_id"] = "UNKNOWN SOURCE ID"
    elif change == "missing_anchor":
        bad.pop("after_candidate_id")
    elif change == "amount":
        bad["row"]["amount"] = 0
    else:
        bad["row"]["bbox"] = [0, 0, 100, 100]
    payload["added"].append(bad)
    result = merge_review(rows, payload, page=1)
    assert not result.errors and len(result.rows) == 3
    assert result.counts["unresolved"] == 1
    item = next(item for item in result.evidence if item["candidate_id"] == "p1a1")
    assert item["validation_errors"] and item["raw_addition"] == bad
    assert "UNKNOWN SOURCE ID" not in str(result.diagnostics)


def test_attributable_metadata_errors_preserve_other_fields_rows_and_raw_observations():
    rows = _rows()
    payload = _payload(rows)
    payload["account"].update(period_end="2031-02-30", stated_nsf_count=-1, ending_balance="not numeric")
    payload["account"].pop("account_name")
    payload["daily_balances"].extend([{"date": None, "balance": 10}, {"date": "2031-01-03", "balance": "invalid"}])
    payload["account_numbers_seen"].append(123)
    before = copy.deepcopy(payload)
    result = merge_review(rows, payload, page=1)
    assert not result.errors and len(result.rows) == 3
    assert result.account["bank"] == payload["account"]["bank"]
    assert result.account["beginning_balance"] == 100
    assert result.account["period_end"] is result.account["stated_nsf_count"] is result.account["ending_balance"] is None
    assert result.account["account_name"] is None
    assert result.daily_balances == (before["daily_balances"][0],)
    assert result.account_numbers_seen == ("SYNTHETIC-001",)
    assert len(result.metadata_evidence) == 7
    assert {item["scope"] for item in result.diagnostics} == {"account", "daily_balances", "account_numbers_seen"}
    assert all("raw_value" in item for item in result.metadata_evidence)
    assert payload == before


@pytest.mark.parametrize("field", ["account", "daily_balances", "account_numbers_seen"])
def test_invalid_metadata_container_does_not_poison_identified_rows(field):
    rows = _rows()
    payload = _payload(rows)
    payload[field] = "SYNTHETIC invalid metadata container"
    result = merge_review(rows, payload, page=1)
    assert not result.errors and len(result.rows) == 3
    assert result.diagnostics and result.metadata_evidence[0]["raw_value"] == payload[field]


@pytest.mark.parametrize("mutation", [
    lambda p: p["reviews"].pop(),
    lambda p: p["reviews"].append(copy.deepcopy(p["reviews"][0])),
    lambda p: p["reviews"][0].update(candidate_id="UNKNOWN SOURCE ID"),
    lambda p: p["reviews"][0].pop("candidate_id"),
    lambda p: p["reviews"].__setitem__(0, None),
    lambda p: p.update(reviews=None),
    lambda p: p.update(added=None),
    lambda p: p.update(extra_root_key=True),
    lambda p: p.pop("account"),
])
def test_unusable_envelope_or_candidate_coverage_remains_page_fatal(mutation):
    rows = _rows()
    payload = _payload(rows)
    mutation(payload)
    result = merge_review(rows, payload, page=1)
    assert result.errors and not result.rows
    assert result.counts["agreed"] == result.counts["corrected"] == result.counts["added"] == result.counts["rejected"] == 0
    assert result.counts["unresolved"] >= len(rows)
    assert all(item["state"] == "unresolved" for item in result.evidence)
    assert "UNKNOWN SOURCE ID" not in str(result.errors)


@pytest.mark.parametrize("payload", [None, [], "SYNTHETIC invalid JSON", {}])
def test_non_object_or_incomplete_response_remains_fatal(payload):
    result = merge_review(_rows(), payload, page=1)
    assert "review_schema_invalid" in result.errors and not result.rows
    assert result.counts["unresolved"] == 2


@pytest.mark.parametrize("kwargs", [{"truncated": True}, {"validation_errors": ("reviewer_transport_failed",)}])
def test_fatal_response_failure_preserves_attempted_correction_but_no_usable_rows(kwargs):
    rows = _rows()
    payload = _payload(rows)
    _correction(payload, rows, field="description", corrected="SYNTHETIC corrected")
    result = merge_review(rows, payload, page=1, **kwargs)
    assert result.errors and not result.rows and result.counts["unresolved"] == 3
    first = next(item for item in result.evidence if item["candidate_id"] == "p1r0")
    assert first["corrected"]["description"] == "SYNTHETIC corrected"
    assert first["raw_review"] == payload["reviews"][0]


@pytest.mark.parametrize("failure", ["observation", "entry_schema", "source"])
def test_row_local_batch_failure_still_calls_discovery_and_keeps_other_rows(failure):
    rows = _rows(16)
    payload = _payload(rows)
    calls = []

    def call(prompt, schema, schema_name, **context):
        calls.append(schema_name)
        if schema_name == "page_review_batch":
            assigned = schema["properties"]["reviews"]["items"]["properties"]["candidate_id"]["enum"]
            reviews = copy.deepcopy([item for item in payload["reviews"] if item["candidate_id"] in assigned])
            if "p1r0" in assigned:
                if failure == "observation":
                    reviews[0]["observed_description"] = "SYNTHETIC wrong description"
                elif failure == "entry_schema":
                    reviews[0].pop("observed_description")
            return ReviewReply({"reviews": reviews})
        context_rows = json.loads(prompt.split("Completed page reviews with effective rows and original candidate IDs, in source order:\n", 1)[1])
        assert context_rows[0]["state"] == "unresolved"
        assert context_rows[0]["row"] == candidate_records(rows)[0]["row"]
        discovery = copy.deepcopy(payload)
        discovery.pop("reviews")
        return ReviewReply(discovery)

    source_errors = {"p1r0": ("proposal_recovery_crop_incomplete",)} if failure == "source" else None
    result = review_batched_page(rows, page_number=1, page_total=1, call=call,
                                 candidate_validation_errors=source_errors)
    assert calls == ["page_review_batch", "page_review_batch", "page_discovery"]
    assert not result.merged.errors and not result.truncated
    assert result.merged.counts["agreed"] == 15
    assert result.merged.counts["added"] == result.merged.counts["unresolved"] == 1
    assert result.merged.account == payload["account"]


def test_merge_does_not_modify_the_model_wire_schema():
    schema = copy.deepcopy(PAGE_REVIEW_SCHEMA)
    payload = _payload(_rows())
    payload["reviews"][0].pop("reason")
    merge_review(_rows(), payload, page=1)
    assert PAGE_REVIEW_SCHEMA == schema

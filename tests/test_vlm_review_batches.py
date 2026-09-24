"""Synthetic bounded review: no network, customer files or model inference."""
import copy
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from ocr.visual_pair_config import PROPOSER_REVISION, REVIEWER_REVISION
from vlm.assemble import CandidateRow
from vlm.client import ChatResult, TransportError
from vlm.receipts import canonical_json, sha256_bytes
from vlm.review import merge_review
from vlm.review_batches import (ReviewReply, build_review_plan, collect_batch_reviews,
                                review_batched_page, review_batching_manifest)
from vlm.schema import empty_review


def _rows(count=31, page=3):
    return [CandidateRow("2031-01-02", "2031-01-02", f"TRUNCATED-{index:02d}", Decimal("1"),
                         "credit", Decimal(101 + index), page, "stage_a", f"b0t0r{index + 1}",
                         "column", (0.1, 0.2, 0.9, 0.8), Decimal("1")) for index in range(count)]


def _review(record):
    original = record["row"]["description"]
    description = original.replace("TRUNCATED-", "PRINTED COMPLETE ")
    return {"candidate_id": record["candidate_id"], "observed_description": description,
            "verdict": "correct", "corrections": [{"field": "description", "original": original,
                                                     "corrected": description}], "reason": "Missing text"}


def _discovery(count=31):
    value = empty_review("statement_page")
    value.pop("reviews")
    value["account"].update(bank="Synthetic Bank", account_number="123456", currency="USD",
                            period_start="2031-01-01", period_end="2031-01-31",
                            beginning_balance=100, ending_balance=100 + count,
                            stated_total_credits=count, stated_total_debits=0,
                            stated_credit_count=count, stated_debit_count=0)
    value["account_numbers_seen"] = ["123456"]
    return value


def _batch_reply(prompt, schema):
    records = json.loads(prompt.split("All original page candidates, in source order:\n", 1)[1])
    assigned = schema["properties"]["reviews"]["items"]["properties"]["candidate_id"]["enum"]
    return {"reviews": [_review(record) for record in records if record["candidate_id"] in assigned]}


def test_global_ids_full_context_corrections_and_single_discovery_owner():
    rows = _rows()
    calls = []

    def call(prompt, schema, schema_name, **context):
        calls.append((schema_name, context))
        if schema_name == "page_review_batch":
            records = json.loads(prompt.split("All original page candidates, in source order:\n", 1)[1])
            assert len(records) == 31 and records[-1]["candidate_id"] == "p3r30"
            return ReviewReply(_batch_reply(prompt, schema))
        reviewed = json.loads(prompt.split("Completed page reviews with effective rows and original candidate IDs, in source order:\n", 1)[1])
        assert [item["candidate_id"] for item in reviewed] == [f"p3r{i}" for i in range(31)]
        assert all(item["state"] == "corrected" and item["row"]["description"].startswith("PRINTED COMPLETE ")
                   for item in reviewed)
        return ReviewReply(_discovery())

    result = review_batched_page(rows, page_number=3, page_total=3, call=call)
    assert not result.merged.errors and not result.truncated
    assert result.merged.counts["corrected"] == 31
    assert [context.get("batch_index") for _, context in calls] == [1, 2, 3, None]
    assert [kind for kind, _ in calls] == ["page_review_batch"] * 3 + ["page_discovery"]
    assert result.merged.evidence[-1]["original"]["description"] == "TRUNCATED-30"
    assert result.merged.evidence[-1]["corrected"]["description"] == "PRINTED COMPLETE 30"
    assert rows[-1].description == "TRUNCATED-30"


@pytest.mark.parametrize("kind", ["missing", "duplicate", "other_batch", "added"])
def test_batch_coverage_and_discovery_ownership_fail_closed(kind):
    rows = _rows()
    plan = build_review_plan(rows)
    lookup = {record["candidate_id"]: record for record in plan.records}
    payloads = [{"reviews": [_review(lookup[key]) for key in batch.candidate_ids]} for batch in plan.batches]
    if kind == "missing":
        payloads[0]["reviews"].pop()
    elif kind == "duplicate":
        payloads[0]["reviews"][1] = copy.deepcopy(payloads[0]["reviews"][0])
    elif kind == "other_batch":
        payloads[1]["reviews"][0] = copy.deepcopy(payloads[0]["reviews"][0])
    else:
        payloads[0]["added"] = []
    payload, errors = collect_batch_reviews(plan, payloads)
    result = merge_review(rows, payload, page=3, validation_errors=errors)
    assert errors and not result.rows and result.counts["unresolved"] == 31


def test_legitimate_identical_added_occurrences_are_never_value_deduplicated():
    rows = _rows(16)

    def call(prompt, schema, schema_name, **context):
        if schema_name == "page_review_batch":
            return ReviewReply(_batch_reply(prompt, schema))
        discovery = _discovery(18)
        # Two distinct printed occurrences can have identical source values.
        # Keep both; the later whole-document gate decides financial admission.
        row = {"date": "2031-01-03", "date_text": "2031-01-03", "description": "Same printed description",
               "amount": 1, "direction": "credit", "balance": None, "bbox": None, "printed_amount": 1}
        discovery["added"] = [{"row": row, "after_candidate_id": "p3r15"},
                              {"row": copy.deepcopy(row), "after_candidate_id": "p3r15"}]
        return ReviewReply(discovery)

    result = review_batched_page(rows, page_number=3, page_total=3, call=call)
    assert not result.merged.errors and result.merged.counts["added"] == 2
    assert len(result.merged.rows) == 18
    assert [item["candidate_id"] for item in result.merged.evidence if item["state"] == "added"] == ["p3a0", "p3a1"]


def test_identical_original_values_in_different_batches_keep_both_candidate_ids():
    rows = _rows(16)
    rows[-1] = replace(rows[0], locator="separately_printed_occurrence")

    def call(prompt, schema, schema_name, **context):
        return ReviewReply(_batch_reply(prompt, schema) if schema_name == "page_review_batch" else _discovery(16))

    result = review_batched_page(rows, page_number=3, page_total=3, call=call)
    assert not result.merged.errors and len(result.merged.rows) == 16
    assert result.merged.rows[0].description == result.merged.rows[-1].description
    assert result.merged.evidence[0]["candidate_id"] == "p3r0"
    assert result.merged.evidence[-1]["candidate_id"] == "p3r15"


@pytest.mark.parametrize("failure", ["batch_truncated", "batch_transport", "discovery_truncated", "discovery_schema"])
def test_one_failed_response_holds_whole_page_and_retains_successful_corrections(failure):
    rows = _rows(16)
    calls = []

    def call(prompt, schema, schema_name, **context):
        calls.append((schema_name, context.get("batch_index")))
        if schema_name == "page_review_batch":
            payload = _batch_reply(prompt, schema)
            if context["batch_index"] == 2 and failure == "batch_transport":
                return ReviewReply(None, errors=("reviewer_transport_failed",))
            return ReviewReply(payload, truncated=context["batch_index"] == 2 and failure == "batch_truncated")
        return ReviewReply({} if failure == "discovery_schema" else _discovery(16),
                           truncated=failure == "discovery_truncated")

    result = review_batched_page(rows, page_number=3, page_total=3, call=call)
    assert result.merged.page == 3 and not result.merged.rows
    assert result.merged.counts["unresolved"] == 16 and result.merged.errors
    assert result.merged.evidence[0]["corrected"]["description"] == "PRINTED COMPLETE 00"
    assert result.truncated is failure.endswith("truncated")
    assert len(calls) == (2 if failure.startswith("batch_") else 3)


def test_batch_policy_rotates_the_pair_cache_manifest(monkeypatch):
    import vlm.review_batches as batching
    from vlm.pair import visual_pair_manifest

    before = visual_pair_manifest()
    assert before["review_batching"] == review_batching_manifest()
    assert before["review_batching"]["batch_size"] == before["review_batching"]["threshold"] == 15
    monkeypatch.setattr(batching, "REVIEW_BATCH_SIZE", 14)
    after = visual_pair_manifest()
    assert before != after
    assert before["review_batching"]["batch_schema"]["ordered_sha256"]
    assert before["review_batching"]["discovery_schema"]["ordered_sha256"]


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    import vlm.pair as pair
    import vlm.render as renderer
    from vlm.render import RenderedPage

    pdf = tmp_path / "synthetic.pdf"
    pdf.write_bytes(b"%PDF fabricated only")
    jpeg = b"same full page synthetic image"
    monkeypatch.setattr(renderer, "render_pages", lambda *a, **k: [
        RenderedPage(0, 100, 100, jpeg, sha256_bytes(jpeg), "pixels", 72, 72, 0, 0, 0)])
    frozen_manifest = pair.visual_pair_manifest()
    monkeypatch.setattr(pair, "visual_pair_manifest", lambda: copy.deepcopy(frozen_manifest))
    state = {"calls": [], "failure": None}
    layout = [{"category": "Table", "bbox": [0, 0, 100, 100], "text":
               "<table><tr><th>Date</th><th>Description</th><th>Credit</th><th>Balance</th></tr>" +
               "".join(f"<tr><td>2031-01-02</td><td>TRUNCATED-{i:02d}</td><td>1.00</td><td>{101+i}.00</td></tr>"
                       for i in range(16)) + "</table>"},
              # The proposer reads the whole page: the summary the discovery pass reports is printed there too.
              {"category": "Text", "bbox": [0, 0, 100, 100], "text": "Summary figures 100.00 116.00 16.00 0.00 16 0"}]

    class Client:
        def __init__(self, url, **kwargs):
            self.proposer = "18013" in url

        def get_json(self, path):
            return {"data": [{"id": "dotsmocr" if self.proposer else "qwen3.8-27b-nvfp4",
                              "root": "/snapshots/" + (PROPOSER_REVISION if self.proposer else REVIEWER_REVISION)}]}

        def chat(self, model, prompt, **kwargs):
            mode = kwargs.get("schema_name", "proposal")
            state["calls"].append((mode, kwargs))
            if state["failure"] == mode:
                raise TransportError("connection_failed")
            obj = layout if self.proposer else (_batch_reply(prompt, kwargs["schema"])
                  if mode == "page_review_batch" else _discovery(16))
            text = canonical_json(obj)
            request = canonical_json({"model": model, "prompt": prompt, "mode": mode}).encode()
            response = text.encode()
            return ChatResult(text, None if self.proposer else obj, None, "stop", 10, 30, 1,
                              sha256_bytes(request), sha256_bytes(response), sha256_bytes(response), request, response)

    monkeypatch.setattr(pair, "VlmClient", Client)
    return pair, pdf, tmp_path / "evidence", state, jpeg


def test_pair_integration_receipts_each_batch_same_image_and_cache_restoration(pipeline):
    pair, pdf, directory, state, jpeg = pipeline
    document = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope="synthetic")
    assert document.visual_pair["gate"]["admitted"]
    assert document.visual_pair["confidence"]["counts"]["corrected"] == 16
    assert [mode for mode, _ in state["calls"]] == ["proposal", "page_review_batch", "page_review_batch", "page_discovery"]
    assert all(kwargs["image_jpeg"] == jpeg for _, kwargs in state["calls"])
    digest = document.visual_pair["receipt_sha256"]
    receipt = json.loads((directory / "blobs" / digest[:2] / digest).read_text())
    reviews = [call for call in receipt["calls"] if call["stage"] == "reviewer"]
    assert [call["purpose"] for call in reviews] == ["candidate_batch", "candidate_batch", "page_discovery"]
    assert [call.get("batch_index") for call in reviews] == [1, 2, None]
    again = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope="synthetic")
    assert again.visual_pair == document.visual_pair and len(state["calls"]) == 4


def test_failed_discovery_is_receipted_and_not_silently_retried(pipeline):
    pair, pdf, directory, state, _ = pipeline
    state["failure"] = "page_discovery"
    document = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope="synthetic")
    assert document.visual_pair["statement"] is None
    assert document.visual_pair["confidence"]["counts"]["unresolved"] == 16
    digest = document.visual_pair["receipt_sha256"]
    receipt = json.loads((directory / "blobs" / digest[:2] / digest).read_text())
    assert receipt["failed_calls"][0]["stage"] == "reviewer"
    assert receipt["failed_calls"][0]["purpose"] == "page_discovery"
    state["failure"] = None
    again = pair.extract_visual_pair(pdf, evidence_dir=directory, data_scope="synthetic")
    assert again.visual_pair == document.visual_pair and len(state["calls"]) == 4

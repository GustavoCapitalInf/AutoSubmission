"""Bounded candidate review with one owner for page discovery.

The original page order defines IDs once. No row is deduplicated by value, and
all responses must be complete before a page can contribute usable rows.
Discovery remains one full-page response; overflow is a refusal, not recovery.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

import jsonschema

from vlm.receipts import canonical_json, sha256_bytes
from vlm.review import PageReviewMerge, candidate_records, merge_review
from vlm.schema import (PAGE_DISCOVERY_SCHEMA, REVIEW_BATCH_SCHEMA, empty_review,
                        review_batch_schema, review_discovery_schema)

REVIEW_BATCH_VERSION = 1
REVIEW_BATCH_SIZE = 15
REVIEW_BATCH_THRESHOLD = 15


@dataclass(frozen=True)
class ReviewBatch:
    index: int
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReviewPlan:
    records: tuple[dict, ...]
    batches: tuple[ReviewBatch, ...]

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(record["candidate_id"] for record in self.records)


@dataclass(frozen=True)
class ReviewReply:
    payload: object
    truncated: bool = False
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatchedPageReview:
    merged: PageReviewMerge
    truncated: bool


def build_review_plan(candidates, *, batch_size: int = REVIEW_BATCH_SIZE) -> ReviewPlan:
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("review_batch_size_invalid")
    records = tuple(candidate_records(candidates))
    ids = tuple(record["candidate_id"] for record in records)
    batches = tuple(ReviewBatch(index + 1, ids[offset:offset + batch_size])
                    for index, offset in enumerate(range(0, len(ids), batch_size)))
    return ReviewPlan(records, batches)


def collect_batch_reviews(plan: ReviewPlan, payloads) -> tuple[dict, tuple[str, ...]]:
    """Retain complete responses; reject missing, duplicated or misplaced IDs."""
    payloads = list(payloads)
    combined = empty_review("statement_page")
    errors = []
    if len(payloads) != len(plan.batches):
        errors.append("review_batch_count_mismatch")
    for batch, payload in zip(plan.batches, payloads):
        if not jsonschema.Draft202012Validator(review_batch_schema(batch.candidate_ids)).is_valid(payload):
            errors.append("review_batch_schema_invalid")
            continue
        reviews = payload["reviews"]
        ids = [item["candidate_id"] for item in reviews]
        if len(ids) != len(set(ids)):
            errors.append("review_batch_duplicate_candidate_id")
        if set(ids) != set(batch.candidate_ids):
            errors.append("review_batch_coverage_invalid")
        combined["reviews"].extend(copy.deepcopy(reviews))
    return combined, tuple(dict.fromkeys(errors))


def reviewed_candidate_context(merged) -> tuple[dict, ...]:
    if merged.errors:
        raise ValueError("review_discovery_requires_valid_reviews")
    # Corrected text is the context for discovery. Rejected source rows remain
    # visible as rejected occurrences, never as transactions to add back.
    return tuple({"candidate_id": item["candidate_id"], "page": item["page"],
                  "locator": item["locator"], "state": item["state"],
                  "row": copy.deepcopy(item["row"] if item["row"] is not None else item["original"])}
                 for item in merged.evidence)


def combine_discovery(plan: ReviewPlan, review_payload: dict, discovery: object) -> tuple[dict, tuple[str, ...]]:
    if not jsonschema.Draft202012Validator(review_discovery_schema(plan.candidate_ids)).is_valid(discovery):
        return copy.deepcopy(review_payload), ("review_discovery_schema_invalid",)
    return {**copy.deepcopy(discovery), "reviews": copy.deepcopy(review_payload["reviews"])}, ()


def review_batched_page(candidates, *, page_number: int, page_total: int, call,
                         metadata_context: dict | None = None, truncated: bool = False,
                         validation_errors=()) -> BatchedPageReview:
    """One attempt per batch, then discovery only after complete valid review.

    ``call`` owns transport and receipts and returns a content-free failure in
    ReviewReply.errors. Partial responses never authorize a discovery pass or
    usable page rows. Successfully reviewed corrections remain audit evidence.
    """
    from vlm.prompts import stage_b_batch_review_prompt, stage_b_discovery_prompt

    candidates = list(candidates)
    plan = build_review_plan(candidates)
    errors = list(validation_errors)
    payloads = []
    for batch in plan.batches:
        prompt = stage_b_batch_review_prompt(
            plan.records, batch.candidate_ids, page_number=page_number, page_total=page_total,
            batch_index=batch.index, batch_total=len(plan.batches), metadata_context=metadata_context,
        )
        reply = call(prompt, review_batch_schema(batch.candidate_ids), "page_review_batch",
                     purpose="candidate_batch", batch_index=batch.index, batch_count=len(plan.batches))
        payloads.append(reply.payload)
        truncated |= reply.truncated
        errors.extend(reply.errors)
    payload, collection_errors = collect_batch_reviews(plan, payloads)
    errors.extend(collection_errors)
    reviewed = merge_review(candidates, payload, page=page_number,
                            truncated=truncated, validation_errors=errors)
    if reviewed.errors:
        return BatchedPageReview(reviewed, truncated)

    prompt = stage_b_discovery_prompt(reviewed_candidate_context(reviewed), page_number=page_number,
                                      page_total=page_total, metadata_context=metadata_context)
    reply = call(prompt, review_discovery_schema(plan.candidate_ids), "page_discovery",
                 purpose="page_discovery", batch_count=len(plan.batches))
    truncated |= reply.truncated
    errors.extend(reply.errors)
    payload, discovery_errors = combine_discovery(plan, payload, reply.payload)
    errors.extend(discovery_errors)
    merged = merge_review(candidates, payload, page=page_number,
                          truncated=truncated, validation_errors=errors)
    return BatchedPageReview(merged, truncated)


def review_batching_manifest() -> dict:
    from vlm.prompts import STAGE_B_BATCH_REVIEW_PROMPT, STAGE_B_DISCOVERY_PROMPT, prompt_sha256

    def hashes(schema):
        return {"semantic_sha256": sha256_bytes(canonical_json(schema).encode()),
                "ordered_sha256": sha256_bytes(json.dumps(schema, separators=(",", ":"), allow_nan=False).encode())}

    return {"version": REVIEW_BATCH_VERSION, "threshold": REVIEW_BATCH_THRESHOLD,
            "batch_size": REVIEW_BATCH_SIZE, "discovery_owner": "one_full_page_pass",
            "batch_template_sha256": prompt_sha256(STAGE_B_BATCH_REVIEW_PROMPT),
            "discovery_template_sha256": prompt_sha256(STAGE_B_DISCOVERY_PROMPT),
            "batch_schema": hashes(REVIEW_BATCH_SCHEMA), "discovery_schema": hashes(PAGE_DISCOVERY_SCHEMA)}

"""Fabricated scope checks independent of whole-document offsets."""
from dataclasses import replace
from decimal import Decimal

from tests.test_visual_pair_segments import chain
from vlm.segment_reconcile import reconcile_page_segments
from vlm.segments import detect_page_segments


def test_each_printed_segment_reconciles_without_currency_or_evidence_mutation():
    pages = chain()
    for page in pages:
        page.account.pop("currency")
    plan = detect_page_segments(pages)
    rows = [row for page in pages for row in page.rows]
    checks, failures = reconcile_page_segments(plan, rows)
    assert checks["performed"] and not failures
    assert len(checks["pages"]) == 3 and all(page["ok"] for page in checks["pages"])
    assert "currency" not in plan.document_fields


def test_compensating_page_errors_do_not_hide_behind_document_total():
    pages = chain()
    plan = detect_page_segments(pages)
    rows = [row for page in pages for row in page.rows]
    rows[0] = replace(rows[0], amount=rows[0].amount + Decimal(5))
    rows[2] = replace(rows[2], amount=rows[2].amount - Decimal(5))
    _, failures = reconcile_page_segments(plan, rows)
    assert {(item["page"], item["code"]) for item in failures} >= {
        (1, "sum_mismatch"), (2, "sum_mismatch"), (1, "continuity_break"), (2, "continuity_break")}
    assert all(item["source"] == "page_segment" for item in failures)


def test_per_direction_counts_are_checked_on_each_page():
    pages = chain()
    plan = detect_page_segments(pages)
    rows = [row for page in pages for row in page.rows]
    rows[0] = replace(rows[0], page=2)
    _, failures = reconcile_page_segments(plan, rows)
    assert {(item["page"], item["field"]) for item in failures if item["code"] == "count_mismatch"} == {
        (1, "stated_credit_count"), (2, "stated_credit_count")}
    assert not any(item["code"] == "duplicate_row" for item in failures)


def test_unproven_scope_never_reconciles_manufactured_segments():
    pages = chain()
    pages[1].account["beginning_balance"] = None
    checks, failures = reconcile_page_segments(detect_page_segments(pages), [])
    assert checks == {"performed": False, "pages": []} and not failures

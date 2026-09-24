"""Constructed page summaries only; no PDFs, private data, files or network."""
from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.pair_metadata import merge_metadata
from vlm.receipts import canonical_json
from vlm.review import PageReviewMerge, mark_ledger_echoes
from vlm.segments import (COUNT_FIELDS, OPENING_OBSERVATION_RULE, OPENING_OBSERVATION_SOURCE,
                          SCOPED_FIELDS, SUMMARY_FIELDS, detect_page_segments)


def page(number, opening, credits, debits, closing, *, credit_count=1, debit_count=1):
    running = Decimal(str(opening))
    rows = []
    for direction, amount in (("credit", credits), ("debit", debits)):
        if not amount:
            continue
        amount = Decimal(str(amount))
        running += amount if direction == "credit" else -amount
        rows.append(CandidateRow(f"2031-01-{number:02d}", f"01/{number:02d}",
                                 f"FABRICATED {number} {direction}", amount, direction,
                                 running, number, "stage_a+stage_b", f"row{len(rows)}"))
    account = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD",
               "beginning_balance": opening, "ending_balance": closing,
               "stated_total_credits": credits, "stated_total_debits": debits,
               "stated_credit_count": credit_count, "stated_debit_count": debit_count}
    return PageReviewMerge(number, tuple(rows), (), {"agreed": len(rows), "unresolved": 0}, (),
                           account, (), "statement_page")


def chain(*, closing="page"):
    pages = [page(1, 100, 30, 10, 120), page(2, 120, 15, 20, 115), page(3, 115, 40, 10, 145)]
    for merged in pages[:-1]:
        merged.account["ending_balance"] = {"page": merged.account["ending_balance"],
                                              "document": 145, "missing": None}[closing]
    return pages


def checked(merges, *, opening_observations=None):
    before = deepcopy(merges)
    observations_before = deepcopy(opening_observations)
    plan = detect_page_segments(merges, opening_observations=opening_observations)
    occurrences = []
    result = merge_metadata(merges, segment_plan=plan, occurrences=occurrences)
    assert merges == before
    assert opening_observations == observations_before
    assert result[2] == [item["code"] for item in occurrences]
    assert [item for item in result[3] if item["source"] == "reviewer"] == [
        {"field": key, "page": merged.page, "source": "reviewer", "value": value}
        for merged in merges for key, value in merged.account.items() if value is not None]
    return plan, result, occurrences


@pytest.mark.parametrize("closing", ["page", "document", "missing"])
def test_proven_chain_scopes_six_fields_and_preserves_all_printed_observations(closing):
    pages = chain(closing=closing)
    plan, (account, _, reasons, _), occurrences = checked(pages)
    assert plan.proven and not reasons and not occurrences
    assert account["beginning_balance"] == 100 and account["ending_balance"] == 145
    assert account["stated_total_credits"] == 85 and account["stated_total_debits"] == 40
    assert account["stated_credit_count"] == account["stated_debit_count"] == 3
    assert [item.account["beginning_balance"] for item in plan.segments] == [100, 120, 115]
    assert [item.account["ending_balance"] for item in plan.segments] == [120, 115, 145]
    assert all(set(item.account) == set(SCOPED_FIELDS) for item in plan.segments)
    if closing == "page":
        assert plan.segments[0].closing_source == {"page": 1, "field": "ending_balance", "source": "reviewer"}
    else:
        assert plan.segments[0].closing_source == {"page": 2, "field": "beginning_balance", "source": "reviewer"}
    assert merge_metadata(pages) == (account, [], reasons, checked(pages)[1][3])
    canonical_json(asdict(plan))  # Runtime accounts are JSON numbers, not Decimal objects.


def test_running_balance_cannot_excuse_contradictory_printed_opening():
    pages = [page(1, 100, 30, 10, None), page(2, 999, 15, 20, 994)]
    pages[0] = replace(pages[0], rows=pages[0].rows[:-1] + (replace(pages[0].rows[-1], balance=Decimal(999)),))
    plan, (_, _, reasons, _), occurrences = checked(pages)
    assert plan.status == "invalid" and not plan.proven and not plan.segments
    assert "anchor_disagreement" in reasons
    assert {"code": "anchor_disagreement", "page": 2, "field": "beginning_balance", "source": "metadata"} in occurrences
    assert sum(item["page"] == 2 and item["field"] == "beginning_balance" for item in occurrences) == 1
    assert any(item["code"] == "segment_opening_chain_mismatch" for item in plan.checks)


def test_printed_closing_matching_neither_endpoint_nor_document_anchor_is_contradiction():
    pages = chain()
    pages[0].account["ending_balance"] = 777
    pages[0] = replace(pages[0], rows=pages[0].rows[:-1] + (replace(pages[0].rows[-1], balance=Decimal(777)),))
    plan, (_, _, reasons, _), occurrences = checked(pages)
    assert plan.status == "invalid" and "anchor_disagreement" in reasons
    assert any(item["page"] == 1 and item["field"] == "ending_balance" for item in occurrences)


def test_wrong_final_printed_closing_is_never_replaced_by_computed_or_row_value():
    pages = chain(closing="missing")
    pages[-1].account["ending_balance"] = 146
    plan, (account, _, reasons, _), occurrences = checked(pages)
    assert not plan.proven and "anchor_disagreement" in reasons
    assert account["ending_balance"] == 146 and not plan.document_fields
    assert any(item["page"] == 3 and item["field"] == "ending_balance" for item in occurrences)


def test_repeated_document_summary_is_never_multiplied_by_page_count():
    pages = chain()
    for merged in pages:
        merged.account.update(beginning_balance=100, ending_balance=145, stated_total_credits=85,
                              stated_total_debits=40, stated_credit_count=3, stated_debit_count=3)
    plan, (account, _, reasons, _), _ = checked(pages)
    assert plan.status == "not_applicable" and not reasons
    assert account["stated_total_credits"] == 85 and account["stated_total_debits"] == 40
    assert account["stated_credit_count"] == account["stated_debit_count"] == 3


def test_zero_net_boxes_can_prove_page_scope_using_each_reviewed_direction_count():
    pages = [page(index, 100, 10, 10, 100) for index in (1, 2, 3)]
    plan, (account, _, reasons, _), _ = checked(pages)
    assert plan.proven and not reasons
    assert account["stated_total_credits"] == account["stated_total_debits"] == 30
    assert account["stated_credit_count"] == account["stated_debit_count"] == 3


@pytest.mark.parametrize("change", ["whole_counts", "unknown_direction"])
def test_ambiguous_zero_net_boxes_keep_ordinary_restatement_scope(change):
    pages = [page(index, 100, 10, 10, 100) for index in (1, 2)]
    if change == "whole_counts":
        for merged in pages:
            merged.account.update(stated_credit_count=2, stated_debit_count=2)
    else:
        pages[0] = replace(pages[0], rows=(replace(pages[0].rows[0], direction="unknown"), pages[0].rows[1]))
    plan, (account, _, reasons, _), _ = checked(pages)
    assert plan.status == "unproven" and not reasons
    assert account["stated_total_credits"] == account["stated_total_debits"] == 10


@pytest.mark.parametrize("field", ["beginning_balance", *SUMMARY_FIELDS])
def test_missing_page_box_field_never_aggregates_partial_evidence(field):
    pages = chain()
    pages[1].account[field] = None
    plan, (_, _, reasons, _), _ = checked(pages)
    assert not plan.proven and not plan.document_fields
    assert "anchor_disagreement" in reasons


@pytest.mark.parametrize("failure", ["row", "fatal", "metadata", "evidence", "empty", "role"])
def test_unresolved_page_cannot_supply_a_segment_proof(failure):
    pages = chain()
    change = {"row": {"counts": {"agreed": 1, "unresolved": 1}},
              "fatal": {"errors": ("review_schema_invalid",)},
              "metadata": {"metadata_evidence": ({"validation_errors": ["review_account_field_missing"]},)},
              "evidence": {"evidence": ({"state": "unresolved"},)},
              "empty": {"rows": (), "counts": {"unresolved": 1}},
              "role": {"page_role": "summary_page"}}[failure]
    pages[1] = replace(pages[1], **change)
    plan, _, _ = checked(pages)
    assert not plan.proven and not plan.document_fields
    assert any(item["code"] == "segment_page_unresolved" for item in plan.checks)


@pytest.mark.parametrize("failure", ["missing", "intervening", "order", "mixed_scope"])
def test_missing_or_mixed_scope_pages_never_produce_partial_segment_aggregation(failure):
    pages = chain()
    if failure == "missing":
        pages.pop(1)
    elif failure == "intervening":
        pages[1] = replace(pages[1], rows=(), counts={}, account={})
    elif failure == "order":
        pages.reverse()
    else:
        pages.append(PageReviewMerge(4, (), (), {}, (), {"ending_balance": 145}, (), "summary_page"))
    plan, _, _ = checked(pages)
    assert not plan.proven and not plan.document_fields


def test_missing_final_printed_closing_is_not_filled_from_rows_or_arithmetic():
    pages = chain(closing="missing")
    pages[-1].account["ending_balance"] = None
    plan, (account, _, _, _), _ = checked(pages)
    assert not plan.proven and "ending_balance" not in account
    assert any(item["code"] == "segment_final_closing_missing" for item in plan.checks)


@pytest.mark.parametrize("field,value", [("stated_credit_count", 1.5), ("stated_debit_count", True),
                                          ("stated_total_credits", -1), ("stated_total_debits", float("inf"))])
def test_invalid_counts_or_magnitudes_do_not_create_scope_proof(field, value):
    pages = chain()
    pages[1].account[field] = value
    assert not detect_page_segments(pages).proven


def test_exact_decimal_chain_and_independent_count_amount_aggregation():
    pages = [page(1, 0.1, 0.2, 0.1, None), page(2, 0.2, 0.3, 0.2, 0.3)]
    plan, (account, _, reasons, _), _ = checked(pages)
    assert plan.proven and not reasons
    assert account["stated_total_credits"] == 0.5 and account["stated_total_debits"] == 0.3
    assert all(account[name] == 2 for name in COUNT_FIELDS)


def test_exact_chain_does_not_tolerate_an_unprinted_cent_adjustment():
    pages = chain()
    pages[1].account["beginning_balance"] = 120.01
    plan, (_, _, reasons, _), _ = checked(pages)
    assert not plan.proven and "anchor_disagreement" in reasons


def test_segment_scope_changes_no_currency_period_or_other_period_figure_policy():
    pages = chain()
    for merged in pages:
        merged.account["currency"] = None
        merged.account["stated_service_charge"] = 2
        merged.account["days_in_period"] = 31
    pages[1].account["period_end"] = "2031-01-30"
    pages[-1].account["stated_service_charge"] = 3
    plan, (account, _, reasons, provenance), _ = checked(pages)
    assert plan.proven
    # A disputed auxiliary figure (the service charge) is unknown, recorded, and holds nothing.
    assert set(reasons) == {"currency_missing", "period_mismatch"}
    assert "currency" not in account and "stated_service_charge" not in account
    assert {"field": "stated_service_charge", "page": None, "source": "disputed_between_pages",
            "value": None} in provenance
    assert account["days_in_period"] == 31
    assert all("currency" not in segment.account for segment in plan.segments)


def test_segment_plan_does_not_alias_source_or_mutate_raw_metadata():
    pages = chain()
    plan, _, _ = checked(pages)
    plan.segments[0].account["beginning_balance"] = 999
    plan.document_fields["ending_balance"] = 888
    assert pages[0].account["beginning_balance"] == 100
    assert pages[-1].account["ending_balance"] == 145


def observation(page, value):
    return {"page": page, "value": value, "source": OPENING_OBSERVATION_SOURCE,
            "locator": "b0t0r0", "evidence_sha256": "a" * 64, "rule": OPENING_OBSERVATION_RULE}


def test_explicit_bound_opening_can_supplement_missing_review_without_rewriting_it():
    pages = chain(closing="missing")
    observations = {merged.page: observation(merged.page, Decimal(str(merged.account["beginning_balance"])))
                    for merged in pages}
    pages[1].account["beginning_balance"] = pages[2].account["beginning_balance"] = None
    plan, (account, _, reasons, provenance), _ = checked(pages, opening_observations=observations)
    assert plan.proven and not reasons
    assert account["beginning_balance"] == 100 and account["ending_balance"] == 145
    assert [item.account["beginning_balance"] for item in plan.segments] == [100, 120, 115]
    assert [item["status"] for item in plan.opening_observations] == [
        "agreed_with_reviewed", "selected_when_reviewed_missing", "selected_when_reviewed_missing"]
    for index in (1, 2):
        assert pages[index].account["beginning_balance"] is None
        source = plan.segments[index].opening_source
        assert source == {**{key: value for key, value in observations[index + 1].items() if key != "value"},
                          "field": "beginning_balance"}
        assert plan.segments[index - 1].closing_source == source
    assert all(not (item["field"] == "beginning_balance" and item["page"] in (2, 3)) for item in provenance)
    assert merge_metadata(pages, opening_observations=observations)[0] == account


def test_first_opening_supplement_retains_its_source_instead_of_claiming_reviewer_evidence():
    pages = chain()
    pages[0].account["beginning_balance"] = None
    plan, (account, _, reasons, provenance), _ = checked(pages, opening_observations={1: observation(1, 100)})
    assert plan.proven and not reasons and account["beginning_balance"] == 100
    assert plan.segments[0].opening_source["source"] == OPENING_OBSERVATION_SOURCE
    assert not any(item["page"] == 1 and item["field"] == "beginning_balance" for item in provenance)


def test_matching_supplement_is_retained_but_never_replaces_reviewed_opening_provenance():
    pages = chain()
    plan, _, _ = checked(pages, opening_observations={2: observation(2, Decimal("120.00"))})
    assert plan.proven and plan.opening_observations[0]["status"] == "agreed_with_reviewed"
    assert plan.segments[1].opening_source == {"page": 2, "field": "beginning_balance", "source": "reviewer"}
    assert plan.opening_observations[0]["observation"]["value"] == Decimal("120.00")


def test_conflicting_printed_source_is_real_anchor_disagreement_not_an_override():
    pages = chain()
    plan, (_, _, reasons, provenance), occurrences = checked(pages, opening_observations={2: observation(2, 999)})
    assert plan.status == "invalid" and not plan.document_fields and "anchor_disagreement" in reasons
    assert plan.opening_observations[0]["status"] == "conflict"
    assert pages[1].account["beginning_balance"] == 120
    assert any(item["page"] == 2 and item["field"] == "beginning_balance" and item["value"] == 120
               for item in provenance)
    assert {"code": "anchor_disagreement", "page": 2, "field": "beginning_balance", "source": "metadata"} in occurrences


def test_wrong_supplement_cannot_be_excused_by_previous_row_balance():
    pages = chain()
    pages[1].account["beginning_balance"] = None
    pages[0] = replace(pages[0], rows=pages[0].rows[:-1] + (replace(pages[0].rows[-1], balance=Decimal(999)),))
    plan, (_, _, reasons, _), _ = checked(pages, opening_observations={2: observation(2, 999)})
    assert plan.status == "invalid" and "anchor_disagreement" in reasons
    assert any(item["code"] == "segment_opening_chain_mismatch" for item in plan.checks)
    assert pages[1].account["beginning_balance"] is None


@pytest.mark.parametrize("change", ["missing", "ambiguous", "hash", "page", "rule", "source", "locator", "extra", "bool", "nan"])
def test_missing_ambiguous_or_unbound_opening_cannot_fill_reviewed_absence(change):
    pages = chain()
    pages[1].account["beginning_balance"] = None
    supplied = observation(2, 120)
    observations = {2: supplied}
    if change == "missing":
        observations = {}
    elif change == "ambiguous":
        observations[2] = [supplied, observation(2, 121)]
    elif change == "hash":
        supplied["evidence_sha256"] = "unbound"
    elif change == "page":
        supplied["page"] = 3
    elif change == "rule":
        supplied["rule"] = "previous_closing_or_backsolve"
    elif change == "source":
        supplied["source"] = "derived"
    elif change == "locator":
        supplied["locator"] = " "
    elif change == "extra":
        supplied["extra"] = True
    elif change == "bool":
        supplied["value"] = True
    else:
        supplied["value"] = float("nan")
    plan = detect_page_segments(pages, opening_observations=observations)
    assert not plan.proven and not plan.document_fields
    assert pages[1].account["beginning_balance"] is None
    if change != "missing":
        assert plan.opening_observations[0]["status"] == "invalid"


def test_supplementary_input_and_plan_evidence_do_not_alias():
    pages = chain()
    pages[1].account["beginning_balance"] = None
    observations = {2: observation(2, 120)}
    plan, _, _ = checked(pages, opening_observations=observations)
    plan.opening_observations[0]["observation"]["locator"] = "changed"
    plan.segments[1].opening_source["locator"] = "also_changed"
    assert observations[2]["locator"] == "b0t0r0" and pages[1].account["beginning_balance"] is None


def test_a_cheque_picture_page_never_stops_a_proven_chain():
    # Owner ruling, 2026-09-22 ("dont hold cheque picture pages"): its reviewer-added rows are not segment
    # evidence. It repeats the statement header (period, currency, bank) but prints no summary box.
    header = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD", "bank": "FABRICATED BANK"}
    # Page 1 posts a 30 credit on the 1st; the pictured deposit slip is dated that day and prints no running
    # balance, so it repeats that posting (cheque-echo backstop).
    slip = CandidateRow("2031-01-01", "01/01", "FABRICATED DEPOSIT SLIP", Decimal("30"), "credit", None, 4,
                        "stage_b", "added0")
    pictures = replace(page(4, 0, 30, 0, 30), rows=(slip,), page_role="cheque_images", account=header,
                       counts={"added": 1, "unresolved": 1})
    plan = detect_page_segments(mark_ledger_echoes(chain() + [pictures]))
    assert plan.proven
    assert [item.account["ending_balance"] for item in plan.segments] == [120, 115, 145]


def test_an_invalid_review_labelled_cheque_images_still_stops_the_chain():
    broken = replace(page(4, 0, 30, 0, 30), page_role="cheque_images", account={"currency": "USD"},
                     errors=("review_missing_candidate_id",))
    assert not detect_page_segments(chain() + [broken]).proven


@pytest.mark.parametrize("position", ["last", "first"])
def test_a_real_summary_page_labelled_cheque_images_still_refuses(position):
    # Review finding on b0f6321: a page printing its own summary box is a statement page whatever the reviewer
    # called it. Absorbing it would prove the chain over the other pages and lose its rows.
    pages = chain()
    if position == "last":
        pages = pages + [replace(page(4, 145, 20, 5, 160), page_role="cheque_images")]
    else:
        pages = [replace(page(1, 80, 25, 5, 100), page_role="cheque_images")] + [
            replace(item, page=item.page + 1, rows=tuple(replace(row, page=row.page + 1) for row in item.rows))
            for item in pages]
    plan = detect_page_segments(pages)
    assert not plan.proven
    _, _, reasons, _ = merge_metadata(pages, segment_plan=plan)
    assert "anchor_disagreement" in reasons

"""Synthetic contract tests; no customer documents or inference requests."""
import copy
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow, parse_dots_layout
from vlm.prompts import STAGE_A_DOTS_PROMPT, stage_b_review_prompt
from vlm.review import candidate_records, confidence_summary, merge_review
from vlm.schema import empty_review, review_schema_sha256, validate_page_review


def _candidate(index=0):
    return CandidateRow("2031-01-02", "01/02", f"Synthetic Exact CASE {index}", Decimal("20.00"),
                        "credit", Decimal("520.00"), 1, "stage_a", f"b1t0r{index}",
                        "column", (0.1, 0.2, 0.9, 0.8), Decimal("20.00"))


def _review(rows):
    value = empty_review("statement_page")
    value["reviews"] = [{"candidate_id": record["candidate_id"], "verdict": "confirm",
                         "observed_description": record["row"]["description"], "corrections": [], "reason": ""}
                        for record in candidate_records(rows)]
    return value


def _correct(payload, original, corrected, index=0):
    payload["reviews"][index].update(
        verdict="correct", observed_description=corrected["description"],
        corrections=[{"field": field, "original": original[field], "corrected": value}
                     for field, value in corrected.items() if value != original[field]],
    )


def _layout():
    return [{"category": "Section-header", "bbox": [10, 10, 90, 20], "text": "Deposits"},
            {"category": "Table", "bbox": [10, 20, 90, 80], "text": (
                "<table><tr><th>Date</th><th>Description</th><th>Amount</th><th>Balance</th></tr>"
                "<tr><td>01/02</td><td>MiXeD Merchant-123</td><td>20.00</td><td>520.00</td></tr></table>")},
            {"category": "Text", "bbox": [10, 80, 90, 95], "text": "01/03 Another Text Merchant 5.00 525.00"}]


def test_dots_layout_table_text_and_boxes():
    result = parse_dots_layout(json.dumps(_layout()), page=1, width=100, height=100, year_hint=2031)
    assert result.errors == ()
    assert len(result.rows) == 2
    assert result.rows[0].bbox == (0.1, 0.2, 0.9, 0.8)
    assert result.rows[0].locator == "b1t0r1"
    assert result.rows[0].direction == "credit"
    assert result.rows[0].description == "MiXeD Merchant-123"
    assert result.rows[1].description == "Another Text Merchant"
    assert result.rows[1].date == "2031-01-03"


def test_dots_split_description_columns_are_preserved():
    elements = [{"bbox": [0, 0, 100, 100], "category": "Table", "text": (
        "<table><tr><th>Date</th><th>Description</th><th></th><th>Debit</th><th>Balance</th></tr>"
        "<tr><td>2031-01-02</td><td>SYNTHETIC</td><td>ROW 01</td><td>-20.00</td><td>520.00</td></tr></table>")}]
    row = parse_dots_layout(elements, page=1, width=100, height=100).rows[0]
    assert row.description == "SYNTHETIC ROW 01"
    assert row.amount == Decimal("20.00") and row.printed_amount == Decimal("-20.00")
    assert row.direction == "debit" and row.direction_source == "column"


def test_dots_descriptions_preserve_internal_spaces_and_picture_elements():
    elements = [{"bbox": [0, 0, 100, 90], "category": "Table", "text": (
        "<table><tr><th>Date</th><th>Description</th><th>Amount</th></tr>"
        "<tr><td>2031-01-02</td><td>Exact  Merchant    REF</td><td>20.00</td></tr></table>")},
        {"bbox": [0, 90, 100, 100], "category": "Picture"}]
    layout = parse_dots_layout(elements, page=1, width=100, height=100)
    assert not layout.errors and len(layout.blocks) == 2
    assert layout.rows[0].description == "Exact  Merchant    REF"


def test_bare_complete_html_table_is_unboxed_source_evidence():
    table = _layout()[1]["text"]
    for raw in (table, f"```html\n{table}\n```"):
        layout = parse_dots_layout(raw, page=3, width=100, height=100, year_hint=2031)
        assert not layout.errors and layout.warnings == ("layout_unboxed",)
        assert layout.page == 3 and len(layout.rows) == 1
        assert layout.blocks[0].bbox is None and layout.rows[0].bbox is None
        assert layout.rows[0].locator == "b0t0r1"
        assert layout.rows[0].description == "MiXeD Merchant-123"


def test_bare_html_fragments_and_finish_length_remain_refused():
    table = _layout()[1]["text"]
    for raw in (table.removesuffix("</table>"), table.replace("</td>", "", 1)):
        layout = parse_dots_layout(raw, page=3, width=100, height=100)
        assert layout.errors and not layout.rows
    cut = parse_dots_layout(table, page=3, width=100, height=100, finish_reason="length")
    assert cut.rows and cut.truncated and cut.errors == ("stage_a_truncated",)
    assert cut.warnings == ("layout_unboxed",)


@pytest.mark.parametrize("box", [[83, 122, 865, 142], [0, 0, 1], [-0.1, 0, 1, 1], [0, 0, 1, 1, 1]])
def test_guided_schema_rejects_pixel_or_malformed_boxes(box):
    value = empty_review("statement_page")
    row = {**candidate_records([_candidate()])[0]["row"], "bbox": box}
    value["added"] = [{"row": row, "after_candidate_id": None}]
    assert validate_page_review(value)


def test_layout_truncation_and_invalid_elements_never_lose_page_slot():
    truncated = parse_dots_layout('[{"bbox":', page=7, width=100, height=100, finish_reason="length")
    assert truncated.page == 7 and truncated.truncated
    assert set(truncated.errors) == {"stage_a_truncated", "layout_invalid_json"}
    complete_but_truncated = parse_dots_layout(_layout(), page=8, width=100, height=100, finish_reason="length")
    assert complete_but_truncated.rows and complete_but_truncated.errors == ("stage_a_truncated",)
    invalid = parse_dots_layout([{"category": "Text", "bbox": [0, 0, 200, 100], "text": "x"}],
                                page=9, width=100, height=100)
    assert invalid.page == 9 and invalid.errors


def test_duplicate_printed_rows_are_kept_for_review():
    block = {"category": "Text", "bbox": [0, 0, 100, 100],
             "text": "01/02 Same Merchant 20.00\n01/02 Same Merchant 20.00"}
    result = parse_dots_layout([block], page=1, width=100, height=100)
    assert len(result.rows) == 2 and result.rows[0].locator != result.rows[1].locator


def test_schema_contains_all_printed_source_fields_and_no_classification():
    value = empty_review()
    assert validate_page_review(value) == []
    assert {"account_number", "days_in_period", "stated_nsf_count", "stated_service_charge",
            "stated_interest_paid", "bank_reported_average_label", "bank_reported_average_balance"} <= value["account"].keys()
    value["lenders"] = []
    assert validate_page_review(value)
    assert len(review_schema_sha256()) == 64


def test_all_review_states_immutable_sources_and_added_order():
    rows = [_candidate(i) for i in range(3)]
    payload = _review(rows)
    original = candidate_records(rows)[1]["row"]
    corrected = {**original, "description": "Actually Printed Description"}
    _correct(payload, original, corrected, index=1)
    payload["reviews"][2].update(verdict="reject", observed_description=None, reason="Printed subtotal")
    extra = {**original, "description": "Reviewer only", "amount": 1, "printed_amount": 1}
    payload["added"] = [{"row": extra, "after_candidate_id": "p1r0"}]
    before = copy.deepcopy(payload)
    result = merge_review(rows, payload, page=1)
    assert result.errors == ()
    assert result.counts == {"agreed": 1, "corrected": 1, "added": 1, "rejected": 1, "unresolved": 0}
    assert [row.description for row in result.rows] == [rows[0].description, "Reviewer only", corrected["description"]]
    assert payload == before and rows[1].description == "Synthetic Exact CASE 1"
    correction = next(item for item in result.evidence if item["state"] == "corrected")
    assert correction["original"] == original and correction["corrected"] == corrected
    assert correction["field_provenance"]["description"]["source"] == "stage_b"
    assert correction["field_provenance"]["amount"]["source"] == "stage_a+stage_b"
    assert correction["observed_description"] == "Actually Printed Description"
    payload["reviews"][1]["corrections"][0]["corrected"] = "mutated"
    assert correction["corrected"]["description"] == "Actually Printed Description"


@pytest.mark.parametrize("label", ["BALANCE FORWARD", "Opening balance", "Balance brought forward 01/02",
                                   "Solde reporté", "Solde reporte", "SOLDE PRÉCÉDENT", "Nouveau solde"])
def test_reviewer_addition_of_a_printed_balance_line_never_enters_the_ledger(label):
    # Stage A already skips these lines; a reviewer proposing one as a missed transaction must not bypass that.
    rows = [_candidate(0)]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    payload["added"] = [{"row": {**original, "description": label, "direction": "unknown", "printed_amount": None},
                         "after_candidate_id": None}]
    result = merge_review(rows, payload, page=1)
    assert result.errors == ()
    assert result.counts == {"agreed": 1, "corrected": 0, "added": 0, "rejected": 1, "unresolved": 0}
    assert [row.description for row in result.rows] == [rows[0].description]
    evidence = next(item for item in result.evidence if item["candidate_id"] == "p1a0")
    assert evidence["reason"] == "addition_is_balance_line" and evidence["row"] is None
    assert evidence["raw_addition"]["row"]["description"] == label


def test_undated_daily_balance_is_unknown_like_a_null_account_field_and_holds_nothing():
    rows = [_candidate(0)]
    payload = _review(rows)
    payload["daily_balances"] = [{"date": None, "balance": 520.0}, {"date": "2031-01-02", "balance": 520.0}]
    result = merge_review(rows, payload, page=1)
    assert result.metadata_evidence == ()
    assert result.daily_balances == ({"date": "2031-01-02", "balance": 520.0},)
    assert result.diagnostics == ({"scope": "daily_balances", "page": 1, "index": 0, "code": "review_daily_balance_undated"},)


@pytest.mark.parametrize("entry", [{"date": "2031-13-45", "balance": 520.0}, {"date": "01/02", "balance": 520.0}])
def test_misread_daily_balance_date_is_still_quarantined(entry):
    rows = [_candidate(0)]
    payload = _review(rows)
    payload["daily_balances"] = [entry]
    result = merge_review(rows, payload, page=1)
    assert result.daily_balances == ()
    assert [item["validation_errors"] for item in result.metadata_evidence] == [["review_invalid_daily_balance"]]


def test_reviewer_addition_of_a_merchant_named_total_is_kept():
    rows = [_candidate(0)]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    payload["added"] = [{"row": {**original, "description": "Total Synthetic Wine Shop"}, "after_candidate_id": "p1r0"}]
    result = merge_review(rows, payload, page=1)
    assert result.counts["added"] == 1 and result.counts["rejected"] == 0
    assert [row.description for row in result.rows][-1] == "Total Synthetic Wine Shop"


@pytest.mark.parametrize("mutation,reason", [
    (lambda data: data["reviews"].pop(), "review_missing_candidate_id"),
    (lambda data: data["reviews"].append(copy.deepcopy(data["reviews"][0])), "review_duplicate_candidate_id"),
    (lambda data: data["reviews"][0].update(candidate_id="unknown"), "review_unknown_candidate_id"),
])
def test_incomplete_or_invalid_review_refuses_whole_page(mutation, reason):
    rows = [_candidate(0), _candidate(1)]
    payload = _review(rows)
    mutation(payload)
    result = merge_review(rows, payload, page=1)
    assert reason in result.errors and result.rows == () and result.page == 1
    assert result.counts["unresolved"] == 2


@pytest.mark.parametrize("mutation,reason", [
    (lambda data: data["reviews"][0].update(verdict="unresolved", observed_description=None), "review_unresolved"),
    (lambda data: data["reviews"][0].update(verdict="correct"), "review_correction_missing"),
])
def test_identified_invalid_review_preserves_its_peer(mutation, reason):
    rows = [_candidate(0), _candidate(1)]
    payload = _review(rows)
    mutation(payload)
    result = merge_review(rows, payload, page=1)
    assert result.errors == () and result.rows == (replace(rows[1], source="stage_a+stage_b"),)
    assert reason in result.evidence[0]["validation_errors"]
    assert result.counts["unresolved"] == 1


def test_correction_must_repeat_original_exactly_and_change_a_value():
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    payload["reviews"][0].update(verdict="correct", corrections=[{
        "field": "description", "original": original["description"], "corrected": original["description"],
    }])
    result = merge_review(rows, payload, page=1)
    assert not result.errors and "review_correction_unchanged" in result.evidence[0]["validation_errors"]
    payload["reviews"][0]["corrections"][0]["original"] = "rewritten"
    result = merge_review(rows, payload, page=1)
    assert not result.errors and "review_original_mismatch" in result.evidence[0]["validation_errors"]


def test_redundant_patch_beside_real_correction_preserves_evidence_and_provenance():
    rows = [_candidate(0), _candidate(1)]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    corrected = {**original, "description": "Complete printed description"}
    _correct(payload, original, corrected)
    payload["reviews"][0]["corrections"].append(
        {"field": "balance", "original": original["balance"], "corrected": original["balance"]},
    )
    before = copy.deepcopy(payload)
    result = merge_review(rows, payload, page=1)
    assert not result.errors
    assert result.counts == {"agreed": 1, "corrected": 1, "added": 0, "rejected": 0, "unresolved": 0}
    evidence = result.evidence[0]
    assert evidence["original"] == original and evidence["corrected"] == corrected
    assert evidence["corrections"] == before["reviews"][0]["corrections"]
    assert evidence["field_provenance"]["balance"]["source"] == "stage_a+stage_b"
    assert evidence["field_provenance"]["description"]["source"] == "stage_b"
    assert payload == before
    payload["reviews"][0]["corrections"][1]["corrected"] = 999
    assert evidence["corrections"][1]["corrected"] == original["balance"]


def test_redundant_patch_must_still_bind_to_the_original_value():
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, "description": "Complete printed description"})
    payload["reviews"][0]["corrections"].append(
        {"field": "balance", "original": 530, "corrected": 530},
    )
    result = merge_review(rows, payload, page=1)
    assert not result.errors and not result.rows
    assert "review_original_mismatch" in result.evidence[0]["validation_errors"]


def test_numeric_equality_does_not_allow_boolean_redundant_patch():
    rows = [replace(_candidate(), amount=Decimal("1"), printed_amount=Decimal("1"))]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, "description": "Complete printed description"})
    payload["reviews"][0]["corrections"].append(
        {"field": "amount", "original": 1, "corrected": True},
    )
    result = merge_review(rows, payload, page=1)
    assert not result.errors and not result.rows
    assert "review_entry_schema_invalid" in result.evidence[0]["validation_errors"]


def test_redundant_patch_does_not_bypass_reconstructed_row_semantics():
    rows = [replace(_candidate(), amount=Decimal("0"), printed_amount=Decimal("0"))]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, "description": "Complete printed description"})
    payload["reviews"][0]["corrections"].append(
        {"field": "amount", "original": 0, "corrected": 0},
    )
    result = merge_review(rows, payload, page=1)
    assert not result.errors and not result.rows
    assert "review_invalid_amount:p1r0" in result.evidence[0]["validation_errors"]


@pytest.mark.parametrize("field,value", [("date", "2031-02-30"), ("amount", float("nan")),
                                         ("bbox", [0, 0, 1]), ("printed_amount", -90)])
def test_semantic_invalid_rows_fail_closed(field, value):
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, field: value})
    result = merge_review(rows, payload, page=1)
    assert not result.errors and not result.rows
    assert result.evidence[0]["validation_errors"] and result.counts["unresolved"] == 1


@pytest.mark.parametrize("change", [{"date": "2031-02-30"}, {"amount": Decimal("-20")},
                                    {"description": "  "}, {"bbox": (0, 0, 2, 1)},
                                    {"printed_amount": Decimal("-90")}])
def test_bad_candidate_cannot_be_confirmed_but_can_be_rejected(change):
    rows = [replace(_candidate(), **change)]
    payload = _review(rows)
    invalid = merge_review(rows, payload, page=1)
    assert not invalid.errors and not invalid.rows and invalid.evidence[0]["validation_errors"]
    payload["reviews"][0].update(verdict="reject", observed_description=None)
    result = merge_review(rows, payload, page=1)
    assert not result.errors and result.counts["rejected"] == 1


def test_invalid_page_retains_correction_beside_original():
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    correction = {**original, "description": "Readable correction"}
    _correct(payload, original, correction)
    result = merge_review(rows, payload, page=1, truncated=True)
    assert result.evidence[0]["original"] == original
    assert result.evidence[0]["corrected"] == correction
    assert result.evidence[0]["state"] == "unresolved" and not result.rows


def test_untrusted_candidate_id_never_enters_failure_codes():
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, "date": "bad"})
    payload["reviews"][0].update(candidate_id="PRIVATE SOURCE TEXT")
    errors = merge_review(rows, payload, page=1).errors
    assert errors and all("PRIVATE" not in item for item in errors)


def test_truncated_page_and_gate_refusal_zero_confidence():
    rows = [_candidate()]
    good = merge_review(rows, _review(rows), page=1)
    assert confidence_summary([good], gate_admitted=True)["score"] == 1.0
    refused = confidence_summary([good], gate_admitted=False, gate_reasons=("sum_mismatch",))
    assert refused["score"] == 0 and refused["agreement_ratio"] == 1.0
    assert refused["provisional"] and "band" not in refused
    assert refused["pages"][0]["counts"] == good.counts and refused["pages"][0]["gate_scope"] == "document"
    truncated = merge_review(rows, _review(rows), page=1, truncated=True)
    assert not truncated.rows and truncated.counts["unresolved"] == 1
    assert confidence_summary([truncated], gate_admitted=True)["score"] == 0


def test_prompt_uses_frozen_dots_and_forbids_arithmetic_and_classification():
    from hashlib import sha256
    assert sha256(STAGE_A_DOTS_PROMPT.encode()).hexdigest() == (
        "fae8e6aafb9682d0501ad64372db852d179b23f99de60198ef4a58b1468235d5"
    )
    prompt = stage_b_review_prompt([_candidate()], page_number=1, page_total=2,
                                    metadata_context={"period_start": "2031-01-01"})
    assert "Copy every value exactly as printed. Never compute, infer or invent a value." in prompt
    assert "Never classify transactions" in prompt
    assert '"candidate_id":"p1r0"' in prompt and "Synthetic Exact CASE 0" in prompt


def test_false_confirmation_of_incomplete_description_is_unresolved():
    rows = [replace(_candidate(), description="SYNTHETIC 01")]
    payload = _review(rows)
    payload["reviews"][0]["observed_description"] = "SYNTHETIC ROW 01"
    result = merge_review(rows, payload, page=1)
    assert result.errors == ()
    assert result.evidence[0]["validation_errors"] == ["review_description_observation_mismatch"]
    assert not result.rows and result.counts["unresolved"] == 1
    assert result.evidence[0]["original"]["description"] == "SYNTHETIC 01"
    assert result.evidence[0]["observed_description"] == "SYNTHETIC ROW 01"


@pytest.mark.parametrize("observation", [None, "", " ", "Synthetic Exact CASE 9", "Synthetic Exact CASE"])
def test_confirm_requires_exact_nonempty_description_observation(observation):
    rows = [_candidate()]
    payload = _review(rows)
    payload["reviews"][0]["observed_description"] = observation
    result = merge_review(rows, payload, page=1)
    assert not result.errors and not result.rows and result.evidence[0]["validation_errors"]


@pytest.mark.parametrize("observation", ["Synthetic Exact CASE  0", "Synthetic Exact\nCASE 0", "Synthetic<br>Exact CASE 0"])
def test_a_confirmed_description_observed_with_other_line_breaks_or_spacing_is_the_same_reading(observation):
    # Line breaks and spacing inside a printed cell are layout: the proposer's Markdown grid writes "<br>",
    # the reviewer a newline. The words and their order must still be exactly the same.
    rows = [_candidate()]
    payload = _review(rows)
    payload["reviews"][0]["observed_description"] = observation
    result = merge_review(rows, payload, page=1)
    assert result.counts["agreed"] == 1 and result.rows[0].description == "Synthetic Exact CASE 0"


def test_correction_requires_observation_matching_corrected_description():
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, "description": "Complete printed description"})
    payload["reviews"][0]["observed_description"] = original["description"]
    result = merge_review(rows, payload, page=1)
    assert not result.errors
    assert "review_description_observation_mismatch" in result.evidence[0]["validation_errors"]


@pytest.mark.parametrize("field,value", [("description", 10), ("amount", "20"), ("direction", None),
                                         ("date_text", None), ("amount", True), ("bbox", "box")])
def test_sparse_correction_field_types_cannot_bypass_full_row_schema(field, value):
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, field: value})
    result = merge_review(rows, payload, page=1)
    assert not result.errors and not result.rows and result.evidence[0]["validation_errors"]


def test_duplicate_field_corrections_and_unexpected_replacements_fail_closed():
    rows = [_candidate()]
    payload = _review(rows)
    original = candidate_records(rows)[0]["row"]
    _correct(payload, original, {**original, "description": "Actual printed description"})
    payload["reviews"][0]["corrections"] *= 2
    result = merge_review(rows, payload, page=1)
    assert not result.errors and "review_duplicate_correction_field" in result.evidence[0]["validation_errors"]
    payload["reviews"][0]["verdict"] = "confirm"
    result = merge_review(rows, payload, page=1)
    assert not result.errors and "review_unexpected_replacement" in result.evidence[0]["validation_errors"]


def test_dense_description_corrections_retain_full_evidence_without_wire_duplication():
    rows = [replace(_candidate(i), description=f"SYNTHETIC {i:02d}") for i in range(60)]
    payload = _review(rows)
    for index, record in enumerate(candidate_records(rows)):
        original = record["row"]
        _correct(payload, original, {**original, "description": f"SYNTHETIC ROW {index:02d}"}, index)
    result = merge_review(rows, payload, page=1)
    assert not result.errors and result.counts["corrected"] == 60
    assert all(item["original"]["description"].replace("SYNTHETIC ", "SYNTHETIC ROW ") ==
               item["corrected"]["description"] == item["observed_description"] for item in result.evidence)
    assert all(set(item) == {"candidate_id", "observed_description", "verdict", "corrections", "reason"}
               for item in payload["reviews"])

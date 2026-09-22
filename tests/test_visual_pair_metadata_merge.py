"""Constructed synthetic metadata/rows only; no files, corpus, or network reads."""
from copy import deepcopy
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.pair_metadata import merge_metadata
from vlm.review import PageReviewMerge


BASE = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"}


def page(number, fields=None, *, balances=(), errors=(), role="statement_page", seen=(), daily=(), base=True):
    account = dict(BASE) if number == 1 and base else {}
    account.update(fields or {})
    rows = tuple(CandidateRow("2031-01-02", "01/02", "FABRICATED ROW", Decimal("1.00"),
                              "credit", Decimal(str(value)) if value is not None else None,
                              number, "stage_a+stage_b", f"row{index}")
                 for index, value in enumerate(balances))
    return PageReviewMerge(number, rows, (), {"agreed": len(rows)}, tuple(errors), account,
                           tuple(daily), role, tuple(seen))


def check(merges):
    before = deepcopy(merges)
    occurrences = []
    result = merge_metadata(merges, occurrences=occurrences)
    assert merges == before
    assert result[2] == [item["code"] for item in occurrences]
    assert all(set(item) == {"code", "page", "field", "source"} and item["source"] == "metadata"
               for item in occurrences)
    expected = [{"field": field, "page": merged.page, "source": "reviewer", "value": value}
                for merged in merges for field, value in merged.account.items() if value is not None]
    assert result[3] == expected  # Raw values and every restatement survive.
    return result, occurrences


def test_single_page_preserves_shape_and_source_values():
    merged = page(1, {"beginning_balance": 0, "ending_balance": 2, "account_number": "0001-2345"})
    (account, daily, reasons, _), occurrences = check([merged])
    assert account == merged.account and daily == [] and reasons == occurrences == []
    assert len(merge_metadata([merged])) == 4


@pytest.mark.parametrize("currency", [None, "", "   "])
def test_absent_currency_is_document_absence_not_contradiction(currency):
    (_, _, reasons, _), occurrences = check([page(1, {"currency": currency})])
    assert reasons == ["currency_missing"]
    assert occurrences == [{"code": "currency_missing", "page": None, "field": "currency", "source": "metadata"}]


def test_currency_case_and_outer_whitespace_restatements_keep_first_printed_value():
    (account, _, reasons, _), _ = check([page(1, {"currency": " usd "}), page(2, {"currency": "USD"})])
    assert not reasons and account["currency"] == " usd "


def test_actual_currency_disagreement_identifies_triggering_page():
    (account, _, reasons, _), occurrences = check([page(1), page(2, {"currency": "CAD"})])
    assert account["currency"] == "USD" and reasons == ["currency_conflict"]
    assert occurrences[0]["page"] == 2 and occurrences[0]["field"] == "currency"


def test_bank_and_account_headers_ignore_formatting_without_rewriting_provenance():
    first = {"bank": "FABRICATED Bank, N.A.", "account_name": "Synthetic  Widget Co., Inc."}
    second = {"bank": "fabricated bank n a", "account_name": "SYNTHETIC WIDGET CO INC"}
    (account, _, reasons, _), _ = check([page(1, first), page(2, second)])
    assert not reasons
    assert all(account[field] == value for field, value in first.items())


@pytest.mark.parametrize("field", ["bank", "account_name"])
def test_real_identity_name_disagreement_is_not_formatting(field):
    (_, _, reasons, _), occurrences = check([page(1, {field: "FABRICATED ALPHA"}), page(2, {field: "FABRICATED BETA"})])
    assert reasons == ["anchor_disagreement"]
    assert occurrences[0]["page"] == 2 and occurrences[0]["field"] == field


def test_masked_and_full_numbers_use_all_visible_characters_and_keep_full_spelling():
    (account, _, reasons, _), _ = check([
        page(1, {"account_number": "12-XXXX-5678"}, seen=("••••5678",)),
        page(2, {"account_number": "12 3456 5678", "account_number_last4": "5678"}, seen=("1234565678",)),
    ])
    assert not reasons and account["account_number"] == "12 3456 5678"


def test_compatible_interior_digits_are_not_dropped():
    (_, _, reasons, _), _ = check([page(1, {"account_number": "12**34**78"}),
                                   page(2, {"account_number": "1299348878"})])
    assert not reasons


@pytest.mark.parametrize("left,right", [
    ("12345678", "99345678"),       # Full IDs cannot agree by last four alone.
    ("12XXXX5678", "9934565678"),   # Visible masked prefix contradicts a full ID.
    ("12**34**78", "1299558878"),   # Visible interior digits contradict the full ID.
    ("12****5678", "99****5678"),
    ("****1234", "****9934"),
    ("ABX12345", "ABY12345"),      # A single literal X is not a masking run.
])
def test_contradictory_visible_number_evidence_refuses(left, right):
    (account, _, reasons, _), occurrences = check([page(1, {"account_number": left}), page(2, {"account_number": right})])
    assert reasons == ["proposal_invalid"]
    assert account["account_number"] == left
    assert occurrences == [{"code": "proposal_invalid", "page": 2, "field": "account_number", "source": "metadata"}]


def test_account_numbers_seen_also_constrain_cross_page_identity():
    (_, _, reasons, _), occurrences = check([page(1, seen=("12345678",)), page(2, seen=("99345678",))])
    assert reasons == ["proposal_invalid"] and occurrences[0]["field"] == "account_numbers_seen"


def test_case_punctuation_and_last_four_are_compatible_without_inventing_a_number():
    (account, _, reasons, _), _ = check([
        page(1, {"account_number_last4": "5678"}, seen=("AB-12.345678",)),
        page(2, {"account_number": "ab 12345678"}),
    ])
    assert not reasons and account["account_number"] == "ab 12345678"
    assert account["account_number_last4"] == "5678"


def test_first_opening_final_closing_with_reviewed_running_balance_continuations():
    (account, _, reasons, _), _ = check([
        page(1, {"beginning_balance": 100, "ending_balance": 150}, balances=(120, 150)),
        page(2, {"beginning_balance": 150, "ending_balance": 250}, balances=(200, 250)),
        page(3, {"beginning_balance": 250, "ending_balance": 300}, balances=(300,)),
    ])
    assert not reasons and account["beginning_balance"] == 100 and account["ending_balance"] == 300


def test_repeated_document_anchors_are_not_mistaken_for_page_balances():
    fields = {"beginning_balance": 100, "ending_balance": 300}
    (account, _, reasons, _), _ = check([page(1, fields, balances=(150,)), page(2, fields, balances=(250,)), page(3, fields, balances=(300,))])
    assert not reasons and account["beginning_balance"] == 100 and account["ending_balance"] == 300


def test_adjacent_page_endpoint_pairs_can_prove_continuation_without_running_balances():
    (account, _, reasons, _), _ = check([
        page(1, {"beginning_balance": 100, "ending_balance": 150}, balances=(None,)),
        page(2, {"beginning_balance": 150, "ending_balance": 200}, balances=(None,)),
    ])
    assert not reasons and account["beginning_balance"] == 100 and account["ending_balance"] == 200


def test_unsupported_opening_difference_is_not_silently_discarded():
    (_, _, reasons, _), occurrences = check([
        page(1, {"beginning_balance": 100}, balances=(150,)),
        page(2, {"beginning_balance": 999, "ending_balance": 200}, balances=(200,)),
    ])
    assert reasons == ["anchor_disagreement"]
    assert occurrences[0]["field"] == "beginning_balance" and occurrences[0]["page"] == 2


def test_first_summary_closing_contradiction_cannot_be_excused_as_continuation():
    (_, _, reasons, _), occurrences = check([
        page(1, {"beginning_balance": 100, "ending_balance": 299}, role="summary_page"),
        page(2, {"ending_balance": 300}, balances=(300,)),
    ])
    assert reasons == ["anchor_disagreement"]
    assert occurrences[0]["field"] == "ending_balance" and occurrences[0]["page"] == 1


def test_final_summary_opening_contradiction_cannot_be_excused_as_continuation():
    (_, _, reasons, _), occurrences = check([
        page(1, {"beginning_balance": 100}, balances=(150,)),
        page(2, {"beginning_balance": 150, "ending_balance": 150}, role="summary_page"),
    ])
    assert reasons == ["anchor_disagreement"] and occurrences[0]["page"] == 2


@pytest.mark.parametrize("invalid_page", [1, 2])
def test_failed_page_cannot_supply_continuation_proof(invalid_page):
    (_, _, reasons, _), occurrences = check([
        page(1, {"beginning_balance": 100, "ending_balance": 150}, balances=(150,),
             errors=("review_unresolved",) if invalid_page == 1 else ()),
        page(2, {"beginning_balance": 150, "ending_balance": 200}, balances=(200,),
             errors=("review_unresolved",) if invalid_page == 2 else ()),
    ])
    assert "anchor_disagreement" in reasons
    assert any(item["field"] == "beginning_balance" and item["page"] == 2 for item in occurrences)


@pytest.mark.parametrize("balances", [(), (150, None)])
def test_empty_page_or_nonfinal_running_balance_does_not_prove_next_opening(balances):
    (_, _, reasons, _), _ = check([
        page(1, {"beginning_balance": 100}, balances=balances),
        page(2, {"beginning_balance": 150, "ending_balance": 200}, balances=(200,)),
    ])
    assert reasons == ["anchor_disagreement"]


def test_first_current_row_balance_is_not_an_opening_balance():
    (_, _, reasons, _), _ = check([
        page(1, {"beginning_balance": 100}, balances=(None,)),
        page(2, {"beginning_balance": 150, "ending_balance": 200}, balances=(150, 200)),
    ])
    assert reasons == ["anchor_disagreement"]


def test_nonadjacent_physical_page_balance_does_not_prove_continuation():
    (_, _, reasons, _), _ = check([
        page(1, {"beginning_balance": 100}, balances=(150,)),
        page(3, {"beginning_balance": 150, "ending_balance": 200}, balances=(200,)),
    ])
    assert reasons == ["anchor_disagreement"]


def test_zero_negative_and_decimal_balances_use_exact_equality():
    (account, _, reasons, _), _ = check([
        page(1, {"beginning_balance": 0, "ending_balance": Decimal("-5.00")}, balances=(-5,)),
        page(2, {"beginning_balance": -5.0, "ending_balance": 0}, balances=(0,)),
    ])
    assert not reasons and account["beginning_balance"] == account["ending_balance"] == 0


@pytest.mark.parametrize("field", [
    "stated_total_credits", "stated_total_debits", "stated_credit_count", "stated_debit_count",
    "days_in_period", "stated_service_charge", "stated_interest_paid", "stated_nsf_count",
    "bank_reported_average_balance", "future_source_figure",
])
def test_period_figures_are_restatements_not_summed_or_maximized(field):
    (account, _, reasons, _), occurrences = check([page(1, {field: 10}), page(2, {field: 10.0}), page(3, {field: 11})])
    assert account[field] == 10 and reasons == ["anchor_disagreement"]
    assert occurrences[0]["page"] == 3 and occurrences[0]["field"] == field


def test_printed_average_labels_accept_formatting_but_not_changed_basis():
    (account, _, reasons, _), occurrences = check([
        page(1, {"bank_reported_average_label": "Average Ledger Balance"}),
        page(2, {"bank_reported_average_label": "AVERAGE-LEDGER BALANCE"}),
        page(3, {"bank_reported_average_label": "Average Collected Balance"}),
    ])
    assert account["bank_reported_average_label"] == "Average Ledger Balance"
    assert reasons == ["anchor_disagreement"] and occurrences[0]["page"] == 3


@pytest.mark.parametrize("field,value", [("period_start", "2031-01-02"), ("period_end", "2031-01-30")])
def test_period_restatements_still_require_exact_dates(field, value):
    (account, _, reasons, _), occurrences = check([page(1), page(2, {field: value})])
    assert account[field] == BASE[field] and reasons == ["period_mismatch"]
    assert occurrences[0]["page"] == 2 and occurrences[0]["field"] == field


def test_missing_invalid_and_reversed_periods_preserve_refusal_policy():
    (_, _, reasons, _), occurrences = check([page(1, {"currency": "USD"}, base=False)])
    assert reasons == ["period_mismatch", "period_mismatch"]
    assert [(v["page"], v["field"]) for v in occurrences] == [(None, "period_start"), (None, "period_end")]
    (_, _, reasons, _), occurrences = check([page(1, {"period_start": "invalid"})])
    assert "period_mismatch" in reasons and occurrences[0]["page"] == 1
    (_, _, reasons, _), occurrences = check([page(1, {"period_end": "2030-12-31"})])
    assert reasons == ["period_mismatch"] and occurrences[0]["field"] == "period_end"


def test_daily_snapshots_keep_last_observation_but_flag_every_conflict_and_bad_date():
    (_, daily, reasons, _), occurrences = check([
        page(1, daily=({"date": "2031-01-03", "balance": 30}, {"date": "2031-01-02", "balance": 20})),
        page(2, daily=({"date": "2031-01-02", "balance": 20.0}, {"date": "2031-01-03", "balance": 31},
                       {"date": None, "balance": 40})),
    ])
    assert daily == [{"date": "2031-01-02", "balance": 20.0}, {"date": "2031-01-03", "balance": 31}]
    assert reasons == ["anchor_disagreement", "date_unparsed"]
    assert all(item["page"] == 2 and item["field"] == "daily_balances" for item in occurrences)


def test_occurrence_sink_appends_without_source_values_or_resetting_prior_entries():
    sentinel = {"code": "earlier_failure", "page": 0, "field": None, "source": "earlier"}
    sink = [sentinel.copy()]
    merge_metadata([page(1, {"account_name": "FABRICATED FIRST"}),
                    page(2, {"account_name": "FABRICATED SECOND"})], occurrences=sink)
    assert sink[0] == sentinel and len(sink) == 2
    assert set(sink[1]) == {"code", "page", "field", "source"}
    assert "FABRICATED" not in repr(sink)

"""The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue spec §2.1, §8.4, §9.1, §9.2, §10.7, §19.1;
R2-OW17): "Mark Zelle Payments as True Revenue", a Settings choice, Yes by default. Yes counts every Zelle deposit as
the rules read it (a person-to-person credit, with its holds); No keeps the underwriter's Q3 exclusion
(`zelle_excluded`). Both readings are computed when a statement is analysed (classify_statement_readings, the pipeline's
`Report.zelle_counted`); the stored payload is the No reading, unchanged, and carries the lean edits to the Yes reading
(analysis/zelle_view.py), which the served view applies. Fabricated rows only (tests/zelle_setting_fixtures.py)."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from analysis import true_revenue, zelle_view
from analysis.metrics import compute_metrics
from analysis.revenue import rebuild_serialized_revenue_views
from analysis.schema import Statement, Transaction
from analysis.serialization import _account_payload, report_to_dict
from analysis.transaction_classifier import (
    classify_statement_readings,
    classify_statement_transactions,
    revenue_text,
)
from tests import zelle_setting_fixtures as fx

HELD = "excluded_pending_review"
COUNTED = "counted_flagged"
EXCLUDED = ("non_revenue", "zelle_excluded")
FIXTURE = Path(__file__).parent / "fixtures" / "zelle_setting_no_view.json"


def _statement(name):
    rows, holder, title = fx.CASES[name]
    return fx.statement(rows, holder=holder, title=title)


def _readings(name):
    return classify_statement_readings(_statement(name))


def _tier(record):
    if isinstance(record, dict):
        return record["revenue_tier"], record["revenue_tier_reason"]
    return record.revenue_tier, record.revenue_tier_reason


def _credits(records):
    return [record for record in records if record.amount > 0]


def _metrics(name, records):
    return compute_metrics(_statement(name), classifications=records)


def _record(payload, text):
    return fx.row(payload, text)["classification"]


# --- Z1: a mixed statement --------------------------------------------------------------------------------------


def test_z1_the_stored_reading_is_today_s():
    no, _yes = _readings("Z1")
    zelle = [record for record in _credits(no) if "ZELLE" in record.original_description]
    assert [_tier(record) for record in zelle] == [EXCLUDED] * 4
    assert [true_revenue.zelle_prior_reading(record) for record in zelle] == [
        (COUNTED, "p2p"), (HELD, "p2p_round_repeat"), (HELD, "p2p_round_repeat"), (HELD, "holder_name")]
    metrics = _metrics("Z1", no)
    assert metrics.true_revenue_total == 10300.00
    assert metrics.non_revenue_by_reason == {"zelle_excluded": {"count": 4, "total": 7734.56}}
    assert metrics.revenue_review_required is False
    assert metrics.withholding_denominator_mode == "true_revenue"
    assert round(metrics.withholding_rate, 4) == 8.2524


def test_z1_the_counted_reading_counts_zelle_with_the_person_to_person_holds():
    _no, yes = _readings("Z1")
    zelle = [record for record in _credits(yes) if "ZELLE" in record.original_description]
    assert [_tier(record) for record in zelle] == [
        (COUNTED, "p2p"), (HELD, "p2p_round_repeat"), (HELD, "p2p_round_repeat"), (HELD, "holder_name")]
    assert zelle[0].revenue_review_status == "pending"
    assert all(record.revenue_match_method != true_revenue.ZELLE_POLICY_METHOD for record in zelle)
    assert all(true_revenue.zelle_prior_reading(record) is None for record in zelle)
    metrics = _metrics("Z1", yes)
    assert metrics.true_revenue_total == 11534.56
    assert metrics.excluded_pending_review_total == 6500.00
    assert metrics.non_revenue_total == 0.00
    assert metrics.revenue_review_required is True
    assert round(metrics.withholding_rate, 4) == 7.3692


def _zel(text):
    """PNC's spelling of a Z1 Zelle sender: 'ZEL FROM <sender> ...' for 'ZELLE PAYMENT FROM <sender> ...'."""
    return text.replace("ZELLE PAYMENT FROM ", "ZEL FROM ")


def test_z1_pnc_s_zel_twin_reads_as_the_zelle_rows_under_yes():
    """Audit round 3, R3-12 (R3-B12; the owner's amendment of 2026-10-06: "holds as for other P2P"): on a PNC statement
    the Z1 Zelle senders printed 'ZEL FROM' take the same tiers and reasons as the same senders printed 'ZELLE', the
    person-to-person holds included (before the batch the round pair counted as named_payer_unlabelled)."""
    zel_rows = [(_zel(text), *rest) for text, *rest in fx.Z1]
    zel = classify_statement_transactions(fx.statement(zel_rows, bank="PNC Bank"), zelle_true_revenue=True)
    zelle = classify_statement_transactions(fx.statement(fx.Z1, bank="PNC Bank"), zelle_true_revenue=True)
    zel_rows_read = [record for record in _credits(zel) if record.original_description.startswith("ZEL FROM")]
    zelle_rows_read = [record for record in _credits(zelle) if "ZELLE" in record.original_description]
    assert [_tier(record) for record in zel_rows_read] == [_tier(record) for record in zelle_rows_read] == [
        (COUNTED, "p2p"), (HELD, "p2p_round_repeat"), (HELD, "p2p_round_repeat"), (HELD, "holder_name")]
    assert [_tier(record) for record in zel] == [_tier(record) for record in zelle]


def test_z1_venmo_is_counted_in_both_readings():
    no, yes = _readings("Z1")
    venmo = [index for index, record in enumerate(no) if record.original_description == fx.VENMO]
    assert [_tier(no[index]) for index in venmo] == [(COUNTED, "p2p")]
    assert [no[index] for index in venmo] == [yes[index] for index in venmo]


# --- Z2: True off zero ---------------------------------------------------------------------------------------------


def test_z2_yes_lifts_true_off_zero_and_the_rate_returns():
    no, yes = _readings("Z2")
    unavailable = "withholding rate is unavailable because True revenue is zero or missing"
    stored, counted = _metrics("Z2", no), _metrics("Z2", yes)
    assert (stored.true_revenue_total, stored.withholding_rate) == (0.0, None)
    assert unavailable in stored.notes
    assert (counted.true_revenue_total, counted.withholding_rate) == (1500.0, 10.0)
    assert unavailable not in counted.notes


# --- Z3: a premium trust account ------------------------------------------------------------------------------------


def test_z3_a_premium_trust_account_holds_the_counted_zelle_deposit():
    no, yes = _readings("Z3")
    assert _tier(no[0]) == EXCLUDED
    assert true_revenue.zelle_prior_reading(no[0]) == (COUNTED, "p2p")
    # The counted reading is NOT the prior: the premium-trust hold runs after the Zelle step.
    assert _tier(yes[0]) == (HELD, "premium_trust_account")
    assert _metrics("Z3", yes).excluded_pending_review_total == 3245.67


# --- Z4: the carve-outs (§ Still open 1's default: asset sale and builder draw lifted, lessor kept) ----------------


def test_z4_a_zelle_truck_sale_is_an_asset_sale_in_the_counted_reading():
    no, yes = _readings("Z4_TRUCK")
    assert _tier(no[0]) == EXCLUDED
    assert (yes[0].revenue_tier, yes[0].revenue_tier_reason, yes[0].revenue_match_method) == (
        "non_revenue", "asset_sale_proceeds", "asset_sale_proceeds")


def test_z4_a_builder_s_zelle_draw_counts_in_the_counted_reading():
    no, yes = _readings("Z4_DRAW")
    assert _tier(no[0]) == EXCLUDED
    assert true_revenue.zelle_prior_reading(no[0]) == (HELD, "non_sale_purpose")
    assert _tier(yes[0]) == (COUNTED, "construction_progress_draw")
    text = revenue_text(no[0].normalized_description)
    assert true_revenue.guard_facts(yes[0], text, zelle_true_revenue=True)["progress_draw"] is True
    assert true_revenue.guard_facts(yes[0], text)["progress_draw"] is False


def test_z4_no_fabricated_pair_reaches_a_person_to_person_repeat_verification():
    """A Zelle sale leaves Q5's and Q6's repeats in the counted reading, as a Venmo sale does. A person-to-person
    partner of the same sender is never verified by a repeat (Q6 reads named ACH payers, Q5 wires), so no fabricated
    pair moves a partner between readings: the partner reads the same in both, and equals the counted call's."""
    statement = _statement("Z4_PARTNER")
    no, yes = classify_statement_readings(statement)
    assert _tier(no[0]) == EXCLUDED and _tier(yes[0]) == ("non_revenue", "asset_sale_proceeds")
    assert _tier(no[1]) == (COUNTED, "p2p") and no[1] == yes[1]
    assert yes == classify_statement_transactions(statement, zelle_true_revenue=True)
    for records in (no, yes):
        assert all(record.revenue_classification != "verified_revenue" for record in _credits(records))


def test_z4_the_lessor_carve_out_is_kept_in_both_readings():
    """Zelle tenants never make the business a lessor (the fact keeps its Zelle skip in both readings), so the non-Zelle
    rent LEASE reads the same in both; a third, non-Zelle rent payer completes the fact and releases it in both."""
    no, yes = _readings("Z4_LESSOR")
    lease = next(index for index, record in enumerate(no) if record.original_description == fx.LEASE)
    assert _tier(no[lease]) == (HELD, "financing_named_payer")
    assert no[lease] == yes[lease]
    assert [_tier(record) for record in yes[:2]] == [(COUNTED, "p2p")] * 2
    no, yes = _readings("Z4_LESSOR_COMPLETE")
    assert _tier(no[lease]) == _tier(yes[lease]) == (COUNTED, "lessor_rent")
    assert no[lease] == yes[lease]


# --- Z5: rule D follows the reading ---------------------------------------------------------------------------------


def test_z5_a_counted_zelle_bounce_form_leaves_the_funder_debit_unpaired():
    no, yes = _readings("Z5")
    debit, credit = no
    assert debit.returned_funder_payment_by == "transaction:2" and credit.returns_funder_payment == "transaction:1"
    stored = _metrics("Z5", no)
    assert (stored.lender_debits, stored.withholding_numerator) == (0.0, 850.0)
    assert stored.returned_funder_payment_count == 1
    debit, credit = yes
    assert _tier(credit) == (COUNTED, "p2p")
    assert debit.returned_funder_payment_by is None and credit.returns_funder_payment is None
    counted = _metrics("Z5", yes)
    assert (counted.lender_debits, counted.withholding_numerator) == (850.0, 850.0)
    assert counted.returned_funder_payment_count == 0


def test_z5_a_returned_credit_pairs_in_both_readings_and_an_nsf_is_decided_first():
    no, yes = _readings("Z5_RETURNED")
    assert no[0].returned_funder_payment_by == yes[0].returned_funder_payment_by == "transaction:2"
    assert _tier(yes[1]) == (HELD, "possible_return")
    no, yes = _readings("Z5_NSF")
    assert no[1].revenue_match_method == yes[1].revenue_match_method == "reversal_cancellation_exclusion"
    assert no == yes


# --- Z6: the $1 floor ------------------------------------------------------------------------------------------------


def test_z6_a_sub_dollar_zelle_credit_is_never_counted():
    statement = _statement("Z6")
    no, yes = classify_statement_readings(statement)
    assert yes == classify_statement_transactions(statement, zelle_true_revenue=True)
    assert _tier(yes[0]) == (HELD, "non_sale_purpose")
    assert not yes[0].contributes_to_true_revenue
    assert _tier(yes[1]) == (COUNTED, "p2p")


# --- Z7: rows a non-revenue rule decided first ---------------------------------------------------------------------


def test_z7_the_rows_decided_first_read_the_same_in_both_readings():
    no, yes = _readings("Z7")
    assert yes is not None
    assert no == yes
    assert [(record.revenue_tier, record.revenue_match_method) for record in no] == [
        ("non_revenue", "financing_proceeds_credit"), (HELD, "direction_conflict"),
        ("non_revenue", "reversal_cancellation_exclusion")]
    assert "zelle_counted_reading" not in fx.case("Z7")


# --- Z8: the fork -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(fx.CASES))
def test_z8_the_fork_equals_two_full_calls(name):
    statement = _statement(name)
    no, yes = classify_statement_readings(statement)
    assert no == classify_statement_transactions(statement)
    assert yes == classify_statement_transactions(statement, zelle_true_revenue=True)


@pytest.mark.parametrize("rows", [
    fx.FREE,
    [("HAZEL SUPPLY LLC DES:PAYMENT ID:1", 800.0, 2), ("NORTHWIND ROSZELL LLC DES:PAYMENT ID:1", 700.0, 3)],
])
def test_z8_a_statement_without_a_zelle_credit_has_one_reading(rows):
    statement = fx.statement(rows)
    no, yes = classify_statement_readings(statement)
    assert yes is None
    assert no == classify_statement_transactions(statement) == classify_statement_transactions(
        statement, zelle_true_revenue=True)
    assert "zelle_counted_reading" not in fx.payload(rows)


# --- Z9: invariants through the pipeline and the publisher ----------------------------------------------------------


def _normalised(node, version):
    if isinstance(node, dict):
        return {key: (version if key == "classification_version" else _normalised(value, version))
                for key, value in node.items()}
    if isinstance(node, list):
        return [_normalised(value, version) for value in node]
    return node


#: The owner's request of 2026-10-06 (lender payment changes; R2-OW18, part N): the keys that batch adds to every record
#: (`potential_payee_key`), every account's detection (`lender_payment_changes`) and a package
#: (`lender_payment_changes`, `lender_payment_changes_unchecked`).
R2_OW18_KEYS = frozenset({"potential_payee_key", "lender_payment_changes", "lender_payment_changes_unchecked"})
#: Audit round 3, R3-B02 (the owner's answer of 2026-10-07 to R3-73): the record field every record gains
#: (`represented_by`, null on every row of Z1).
R3_B02_KEYS = frozenset({"represented_by"})
#: Audit round 3, R3-B03: the metrics flag of R3-20's floor (`withholding_basis_below_floor`, false on Z1) and the
#: owner's answer of 2026-10-07 to R3-79's keys (the record field `lump_sum_payoff`, null on every row of Z1; the metrics
#: `lump_sum_payoff_total` and `_count`, 0; the detection list `lump_sum_payoffs`, empty).
R3_B03_KEYS = frozenset({"withholding_basis_below_floor", "lump_sum_payoff", "lump_sum_payoff_total",
                         "lump_sum_payoff_count", "lump_sum_payoffs"})


def _without_r2_ow18(node):
    """R2-OW18 (part N): the payload without the keys the owner's request of 2026-10-06 adds (and, audit round 3,
    R3-B02, the record field `represented_by`, and R3-B03's keys), applied to BOTH sides of the golden comparison, as
    `_normalised` reads every classification_version as one. The pinned fixture is never rewritten."""
    if isinstance(node, dict):
        return {key: _without_r2_ow18(value) for key, value in node.items()
                if key not in R2_OW18_KEYS and key not in R3_B02_KEYS and key not in R3_B03_KEYS}
    if isinstance(node, list):
        return [_without_r2_ow18(value) for value in node]
    return node


def test_z9_i_no_the_no_view_of_z1_is_byte_identical_to_r2_ow16():
    fixture_text = FIXTURE.read_text(encoding="utf-8")
    fixture = json.loads(fixture_text)
    version = fixture["statement"]["transactions"][0]["classification"]["classification_version"]
    stored = json.loads(json.dumps(fx.case("Z1")))
    view = zelle_view.apply_zelle_view(stored, counted=False)
    assert "zelle_counted_reading" not in view and "zelle_deposits" not in view["metrics"]
    assert json.dumps(fixture, indent=1) + "\n" == fixture_text
    assert (json.dumps(_without_r2_ow18(_normalised(view, version)), indent=1) + "\n"
            == json.dumps(_without_r2_ow18(fixture), indent=1) + "\n")


@pytest.mark.parametrize("name", sorted(fx.CASES))
def test_z9_i_no_and_i_yes(name):
    document = fx.case_document(name)
    report = document.accounts[0]
    stored = json.loads(json.dumps(report_to_dict(report)))
    no_only = {key: value for key, value in stored.items() if key != "zelle_counted_reading"}
    assert no_only == json.loads(json.dumps(_account_payload(report)))
    assert zelle_view.apply_zelle_view(stored, counted=False) == no_only
    if report.zelle_counted is None:
        assert "zelle_counted_reading" not in stored
        return
    counted = json.loads(json.dumps(_account_payload(report.zelle_counted)))
    served = zelle_view.apply_zelle_view(stored, counted=True)
    stripped = copy.deepcopy(served)
    for key in zelle_view.ZELLE_VIEW_KEYS:
        stripped["metrics"].pop(key, None)
    for transaction in stripped["statement"]["transactions"]:
        transaction.pop(zelle_view.ZELLE_ROW_TAG, None)
    assert stripped == counted
    assert zelle_view.reading(stored, counted=True) == counted


def test_z9_i_notes_the_integrity_notes_are_the_same_in_both_readings(monkeypatch):
    from analysis import pipeline

    real_quality = pipeline.assess_quality

    def quality(stmt, recon, dispatch=None):
        found = real_quality(stmt, recon, dispatch=dispatch)
        return pipeline.Quality(level=found.level, transaction_detail_reliable=found.transaction_detail_reliable,
                                summary_totals_reliable=found.summary_totals_reliable,
                                aggregate_rows=found.aggregate_rows, corporate_use="review",
                                notes=["fabricated quality note"])

    monkeypatch.setattr(pipeline, "assess_quality", quality)
    monkeypatch.setattr(pipeline, "assess_document_integrity", lambda *args, **kwargs: pipeline.DocumentIntegrity(
        risk_level="high", flags=["fabricated_flag"], notes=["fabricated"], possible_document_issue=True))
    report = fx.case_document("Z1").accounts[0]
    assert report.quality.corporate_use == "manual_review_required"
    assert report.metrics.notes == report.zelle_counted.metrics.notes
    assert "fabricated quality note" in report.metrics.notes
    assert not any("corporate approval" in note for note in report.metrics.notes)
    edits = report_to_dict(report)["zelle_counted_reading"]
    assert not any(edit[0][:2] == ["metrics", "notes"] for edit in edits)


@pytest.mark.parametrize("name", sorted(fx.CASES))
def test_z9_i_rules_the_counted_reading_is_the_prior_but_where_declared(name):
    """Every Zelle policy row's counted (tier, reason) is its stored zelle_prior, except the declared rows: the premium
    trust account (Z3) and the lifted carve-outs (Z4's truck, draw and partner sale). Z6's sub-dollar row is held by the
    rules already, so its prior is its counted reading."""
    no, yes = _readings(name)
    declared = {"Z3": {0}, "Z4_TRUCK": {0}, "Z4_DRAW": {0}, "Z4_PARTNER": {0}}.get(name, set())
    for index, record in enumerate(no):
        prior = true_revenue.zelle_prior_reading(record)
        if prior is None:
            continue
        if index in declared:
            assert _tier(yes[index]) != prior
        else:
            assert _tier(yes[index]) == prior, (name, index)


# --- Z10: the edits -------------------------------------------------------------------------------------------------


NESTED = [
    ({"a": [1, 2, 3], "b": {"c": None, "d": [{"e": 1}]}}, {"a": [1, 2], "b": {"d": [{"e": 2, "f": None}]}, "g": 1}),
    ({"a": [{"x": [1, {"y": 2}]}]}, {"a": [{"x": [1, {"y": 3, "z": [None]}]}]}),
    ({"a": 1, "b": True}, {"a": 1.0, "b": 1}),
    ([1, {"a": 1}], [1, {"a": 2}]),
    ({"a": (1, 2)}, {"a": (1, 3)}),
]


@pytest.mark.parametrize(("a", "b"), NESTED)
def test_z10_the_full_diff_is_exact_and_never_mutates(a, b):
    before_a, before_b = copy.deepcopy(a), copy.deepcopy(b)
    edits = zelle_view._full_diff(a, b)
    json.dumps(edits)
    applied = zelle_view.apply_reading_edits(a, edits)
    assert applied == b and all(type(x) is type(y) for x, y in zip(_leaves(applied), _leaves(b)))
    assert (a, b) == (before_a, before_b)
    assert zelle_view._full_diff(a, a) == []
    assert zelle_view.reading_edits({"statement": {}}, {"statement": {}}) == []


def _leaves(node):
    if isinstance(node, dict):
        return [leaf for value in node.values() for leaf in _leaves(value)]
    if isinstance(node, list):
        return [leaf for value in node for leaf in _leaves(value)]
    return [node]


def test_z10_apply_never_mutates_its_edits():
    a, b = NESTED[0]
    edits = zelle_view._full_diff(a, b)
    frozen = copy.deepcopy(edits)
    result = zelle_view.apply_reading_edits(a, edits)
    result["b"]["d"][0]["f"] = "changed"
    assert edits == frozen


@pytest.mark.parametrize("name", [name for name in sorted(fx.CASES) if name not in {"Z5_NSF", "Z7"}])
def test_z10_the_cases_take_the_lean_list(name):
    report = fx.case_document(name).accounts[0]
    no = _account_payload(report)
    yes = _account_payload(report.zelle_counted)
    lean = zelle_view.reading_edits(no, yes)
    assert lean and not any(zelle_view._rebuilt(edit[0]) for edit in lean)
    assert rebuild_serialized_revenue_views(zelle_view.apply_reading_edits(no, lean)) == yes
    assert len(json.dumps(lean)) < len(json.dumps(zelle_view._full_diff(no, yes)))


def test_z10_on_z1_the_lean_list_is_under_a_quarter_of_the_payload():
    stored = fx.case("Z1")
    edits = stored.pop("zelle_counted_reading")
    assert len(json.dumps(edits)) * 4 < len(json.dumps(stored))


def test_z10_a_planted_difference_under_a_rebuilt_key_falls_back_to_the_full_list():
    report = fx.case_document("Z1").accounts[0]
    no = _account_payload(report)
    yes = _account_payload(report.zelle_counted)
    yes["metrics"]["withholding_rate"] = 99.0  # not what the rebuild derives from the records
    edits = zelle_view.reading_edits(no, yes)
    assert edits == zelle_view._full_diff(no, yes)
    assert zelle_view.apply_reading_edits(no, edits) == yes


def _written_keys(payload):
    """The paths the rebuild writes on `payload`, whose metrics and detection start empty (but for the inputs the
    rebuild reads) and which carries no classifications view. Audit round 3, R3-B03 (R3-13): and the keys the rebuild
    writes on each `detection.potential_lenders` entry, whose sample carries none of them."""
    top = set(payload)
    lenders_before = [set(entry) for entry in (payload.get("detection") or {}).get("potential_lenders") or []]
    rebuilt = rebuild_serialized_revenue_views(payload)
    keys = {("metrics", key) for key in rebuilt["metrics"]} | {("detection", key) for key in rebuilt["detection"]}
    keys |= {(key,) for key in set(rebuilt) - top}
    for transaction in rebuilt["statement"]["transactions"]:
        before = {key for key in transaction["classification"]}
        keys |= {("statement", "transactions", "*", "classification", key) for key in before
                 if key.startswith("contributes_to_") and key in zelle_view._REBUILT_RECORD_FLAGS}
    for before, entry in zip(lenders_before, rebuilt["detection"].get("potential_lenders") or []):
        keys |= {("detection", "potential_lenders", "*", key) for key in set(entry) - before}
    return keys


def _sample(mode):
    payload = json.loads(json.dumps(fx.case("Z1")))
    payload.pop("zelle_counted_reading")
    payload["metrics"] = {"withholding_denominator_mode": mode, "withholding_numerator": 850.0,
                          "potential_withholding_numerator": 450.0, "potential_lender_debit_count": 3}
    # R3-13: one potential lender's entry, without the basis and exposure the rebuild writes.
    payload["detection"] = {"potential_lenders": [{"funder": "Northwind Funding", "classification": "potential_lender",
                                                   "total_debited": 450.0, "potential_lender_debit_total": 450.0}]}
    payload.pop("classifications")
    return payload


#: The inputs the rebuild reads from the sample and never writes.
_READ_ONLY = {("metrics", "withholding_numerator"), ("metrics", "potential_withholding_numerator"),
              ("metrics", "potential_lender_debit_count"), ("detection", "potential_lenders")}


def test_z10_rebuilt_keys_are_the_keys_the_rebuild_writes():
    written = _written_keys(_sample("true_revenue"))
    written -= _READ_ONLY
    assert written == set(zelle_view.REBUILT_KEYS)
    for mode in ("verified_revenue", "legacy_eligible_deposits"):
        assert _written_keys(_sample(mode)) - _READ_ONLY <= set(zelle_view.REBUILT_KEYS)


# --- Z11: the view's robustness --------------------------------------------------------------------------------------


def test_z11_a_zelle_free_payload_is_returned_as_the_same_object():
    payload = fx.payload(fx.FREE)
    assert zelle_view.apply_zelle_view(payload, counted=True) is payload
    assert zelle_view.apply_zelle_view(payload, counted=False) is payload
    assert zelle_view.reading(payload, counted=True) is payload


def _without_edits(name):
    payload = fx.case(name)
    payload.pop("zelle_counted_reading")
    return payload


def test_z11_a_payload_analysed_before_the_setting_is_served_as_stored():
    """Zelle policy rows and no edits: analysed between R2-OW02 and R2-OW17."""
    payload = _without_edits("Z1")
    frozen = copy.deepcopy(payload)
    yes = zelle_view.apply_zelle_view(payload, counted=True)
    figures = yes["metrics"]["zelle_deposits"]
    assert (figures["setting_applied"], figures["counted_as_true_revenue"]) == (False, False)
    assert figures["by_tier"] == {"non_revenue": {"count": 4, "total": 7734.56}}
    assert yes["metrics"]["true_revenue_total"] == payload["metrics"]["true_revenue_total"] == 10300.0
    assert zelle_view.apply_zelle_view(payload, counted=False) is payload
    assert payload == frozen


def _legacy():
    """A stand-in for a payload analysed before R2-OW02: the counted reading stored, with no edits."""
    report = fx.case_document("Z1").accounts[0]
    return json.loads(json.dumps(_account_payload(report.zelle_counted)))


def test_z11_a_legacy_payload_is_served_as_stored_in_both_modes():
    payload = _legacy()
    assert zelle_view.zelle_rows(payload) == ([1, 2, 3, 4], True)
    no = zelle_view.apply_zelle_view(payload, counted=False)
    figures = no["metrics"]["zelle_deposits"]
    assert (figures["setting_applied"], figures["counted_as_true_revenue"]) == (False, True)
    assert no["metrics"]["true_revenue_total"] == 11534.56
    yes = zelle_view.apply_zelle_view(payload, counted=True)
    assert (yes["metrics"]["zelle_deposits"]["setting_applied"],
            yes["metrics"]["zelle_deposits"]["counted_as_true_revenue"]) == (True, True)


@pytest.mark.parametrize("name", sorted(fx.CASES))
def test_z11_the_legacy_test_never_fires_on_a_fresh_no_payload(name):
    payload = fx.case(name)
    positions, legacy = zelle_view.zelle_rows(payload)
    assert legacy is False


@pytest.mark.parametrize("edits", [
    [[["statement", "transactions", 999, "classification", "revenue_tier"], "verified"]],
    [[["metrics", "no_such_key", "deeper"], 1]],
    "not a list",
    [["not a path"]],
    [[["statement", "transactions", 1, "classification", "revenue_tier"], "no_such_tier"]],
])
def test_z11_corrupt_edits_are_served_as_stored_without_an_exception(edits):
    payload = _without_edits("Z1")
    payload["zelle_counted_reading"] = edits
    frozen = copy.deepcopy(payload)
    yes = zelle_view.apply_zelle_view(payload, counted=True)
    assert yes["metrics"]["zelle_deposits"]["setting_applied"] is False
    assert yes["metrics"]["true_revenue_total"] == 10300.0
    assert "zelle_counted_reading" not in yes
    assert zelle_view.reading_with_status(payload, counted=True)[1] == [1]
    assert payload == frozen


def test_z11_a_two_account_document_serves_each_account_in_its_own_reading():
    from analysis.pipeline import DocumentReport
    from analysis.serialization import document_report_to_dict

    first = fx.case_document("Z1").accounts[0]
    second = fx.document(fx.FREE, number="000000005678").accounts[0]
    payload = document_report_to_dict(DocumentReport(accounts=[first, second]))
    assert "zelle_counted_reading" in payload["accounts"][0] and "zelle_counted_reading" not in payload["accounts"][1]
    frozen = copy.deepcopy(payload)
    yes = zelle_view.apply_zelle_view(payload, counted=True)
    assert yes["accounts"][0]["metrics"]["true_revenue_total"] == 11534.56
    assert yes["accounts"][1] is payload["accounts"][1]
    no = zelle_view.apply_zelle_view(payload, counted=False)
    assert no["accounts"][0]["metrics"]["true_revenue_total"] == 10300.0
    assert "zelle_counted_reading" not in no["accounts"][0]
    assert payload == frozen


def test_z11_the_figures_and_the_row_tag():
    payload = fx.case("Z1")
    yes = zelle_view.apply_zelle_view(payload, counted=True)
    assert yes["metrics"]["zelle_deposits"] == {
        "counted_as_true_revenue": True, "setting_applied": True, "count": 4, "total": 7734.56,
        "by_tier": {COUNTED: {"count": 1, "total": 1234.56}, HELD: {"count": 3, "total": 6500.0}}}
    tagged = [transaction["description"] for transaction in yes["statement"]["transactions"]
              if transaction.get("zelle_deposit") is True]
    assert tagged == [fx.PAT, fx.FABRIKAM_1, fx.FABRIKAM_2, fx.OWN]
    no = zelle_view.apply_zelle_view(payload, counted=False)
    assert "zelle_deposits" not in no["metrics"]
    assert no["metrics"]["non_revenue_by_reason"] == {"zelle_excluded": {"count": 4, "total": 7734.56}}
    assert not any("zelle_deposit" in transaction for transaction in no["statement"]["transactions"])


def test_z11_the_figure_function():
    figures = zelle_view.zelle_deposit_figures([("non_revenue", 0.1), (COUNTED, 0.2), ("verified", 1), (HELD, 2.0)])
    assert figures == {"count": 4, "total": 3.3, "by_tier": {
        "verified": {"count": 1, "total": 1.0}, COUNTED: {"count": 1, "total": 0.2},
        HELD: {"count": 1, "total": 2.0}, "non_revenue": {"count": 1, "total": 0.1}}}


# --- Z12: decisions on Zelle rows, through the routes (spec §10.7) ---------------------------------------------------

PAT_ROW, FABRIKAM_ROW, OWN_ROW = "transaction:2", "transaction:3", "transaction:5"


@pytest.fixture
def zelle_store(monkeypatch, tmp_path):
    """A job store of its own under tmp_path, installed where the routes read it, and its own settings file."""
    from webapp import app as webapp_app
    from webapp.jobs import JobStore
    from webapp.storage import Storage

    store = JobStore(Storage(tmp_path / "data"))
    monkeypatch.setattr(webapp_app, "store", store)
    return store


def _job(store, payload):
    created = store.create("fabricated-zelle.pdf")
    store.set_result(created.id, "# Fabricated", "<p>Fabricated</p>", analysis=payload)
    return created.id


def _shown(store, value: bool):
    from webapp.settings import save_settings
    save_settings(store.storage.data_dir, {"zelle_true_revenue": value})


def _review(job_id, location, decision):
    from webapp.app import app
    return app.test_client().post(f"/analysis/{job_id}/revenue-review",
                                  json={"source_location": location, "decision": decision})


def _state(store, job_id, location, *, counted):
    stored = store.get(job_id).analysis
    view = zelle_view.reading(stored, counted=counted)
    record = next(transaction["classification"] for transaction in view["statement"]["transactions"]
                  if transaction["classification"]["source_location"] == location)
    return record["revenue_tier"], record["revenue_tier_reason"], record["revenue_review_status"]


def test_z12_a_yes_shown_reject_rejects_the_counted_reading_only(zelle_store):
    job = _job(zelle_store, fx.case("Z1"))
    assert _review(job, PAT_ROW, "reject").status_code == 200
    assert _state(zelle_store, job, PAT_ROW, counted=True) == ("non_revenue", "p2p", "rejected")
    # The stored (No) reading refuses a reject (the R2-OW03 valve), so it is at its analysis state: Confirm offered.
    assert _state(zelle_store, job, PAT_ROW, counted=False) == ("non_revenue", "zelle_excluded", "not_required")
    _shown(zelle_store, False)
    from webapp.app import app
    shown = app.test_client().get(f"/analysis/{job}").get_json()["analysis"]
    record = fx.row(shown, fx.PAT)["classification"]
    assert record["revenue_initial_classification"] == "non_revenue"
    assert record["revenue_tier_reason"] == "zelle_excluded"


def test_z12_a_confirm_in_either_mode_verifies_both_readings_and_a_reset_restores_both(zelle_store):
    job = _job(zelle_store, fx.case("Z1"))
    assert _review(job, OWN_ROW, "confirm").status_code == 200  # Yes shown, the held holder's-name row
    for counted in (True, False):
        assert _state(zelle_store, job, OWN_ROW, counted=counted)[0::2] == ("verified", "confirmed")
    assert _review(job, OWN_ROW, "reset").status_code == 200
    assert _state(zelle_store, job, OWN_ROW, counted=True) == (HELD, "holder_name", "pending")
    assert _state(zelle_store, job, OWN_ROW, counted=False) == ("non_revenue", "zelle_excluded", "not_required")
    _shown(zelle_store, False)
    assert _review(job, PAT_ROW, "confirm").status_code == 200
    for counted in (True, False):
        assert _state(zelle_store, job, PAT_ROW, counted=counted)[0::2] == ("verified", "confirmed")
    assert _review(job, PAT_ROW, "reset").status_code == 200
    assert _state(zelle_store, job, PAT_ROW, counted=True) == (COUNTED, "p2p", "pending")
    assert _state(zelle_store, job, PAT_ROW, counted=False) == ("non_revenue", "zelle_excluded", "not_required")
    assert "zelle_counted_reading" in zelle_store.get(job).analysis


@pytest.mark.parametrize("first_shown", [True, False])
def test_z12_the_latest_decision_sets_every_reading(zelle_store, first_shown):
    """Confirm (Yes or No), then reject (Yes): the counted reading is rejected and the stored one, which refuses the
    reject, goes back to its analysis state: never left Verified."""
    job = _job(zelle_store, fx.case("Z1"))
    _shown(zelle_store, first_shown)
    assert _review(job, PAT_ROW, "confirm").status_code == 200
    _shown(zelle_store, True)
    assert _review(job, PAT_ROW, "reject").status_code == 200
    assert _state(zelle_store, job, PAT_ROW, counted=True) == ("non_revenue", "p2p", "rejected")
    assert _state(zelle_store, job, PAT_ROW, counted=False) == ("non_revenue", "zelle_excluded", "not_required")
    no_view = zelle_view.apply_zelle_view(zelle_store.get(job).analysis, counted=False)
    assert no_view["metrics"]["true_revenue_total"] == 10300.0


def test_z12_one_call_writes_one_time_to_both_readings(zelle_store):
    job = _job(zelle_store, fx.case("Z1"))
    assert _review(job, OWN_ROW, "confirm").status_code == 200
    stored = zelle_store.get(job).analysis
    times = {fx.row(zelle_view.reading(stored, counted=counted), fx.OWN)["classification"]["revenue_reviewed_at"]
             for counted in (True, False)}
    assert len(times) == 1 and None not in times


def test_z12_a_yes_batch_that_holds_a_zelle_reject_is_applied(zelle_store):
    from webapp.app import app
    job = _job(zelle_store, fx.case("Z1"))
    response = app.test_client().post(f"/analysis/{job}/revenue-reviews", json={"decisions": [
        {"source_location": PAT_ROW, "decision": "reject"}, {"source_location": FABRIKAM_ROW, "decision": "confirm"}]})
    assert response.status_code == 200 and response.get_json()["applied"] == 2
    assert _state(zelle_store, job, PAT_ROW, counted=True)[0::2] == ("non_revenue", "rejected")
    assert _state(zelle_store, job, PAT_ROW, counted=False)[0::2] == ("non_revenue", "not_required")
    for counted in (True, False):
        assert _state(zelle_store, job, FABRIKAM_ROW, counted=counted)[0::2] == ("verified", "confirmed")


def test_z12_a_yes_shown_reject_of_an_asset_sale_is_refused_and_writes_nothing(zelle_store):
    payload = fx.case("Z4_TRUCK")
    job = _job(zelle_store, payload)
    before = copy.deepcopy(zelle_store.get(job).analysis)
    response = _review(job, "transaction:1", "reject")
    assert response.status_code == 400
    assert response.get_json() == {"error": "only automatically unverified deposits can be reviewed"}
    assert zelle_store.get(job).analysis == before
    assert zelle_store.review_history(job) == []


def test_z12_a_no_shown_confirm_of_an_asset_sale_leaves_the_counted_reading_at_its_analysis_state(zelle_store):
    job = _job(zelle_store, fx.case("Z4_TRUCK"))
    _shown(zelle_store, False)
    assert _review(job, "transaction:1", "confirm").status_code == 200
    assert _state(zelle_store, job, "transaction:1", counted=False)[0::2] == ("verified", "confirmed")
    assert _state(zelle_store, job, "transaction:1", counted=True) == (
        "non_revenue", "asset_sale_proceeds", "not_required")


@pytest.mark.parametrize("edits", [[[["statement", "transactions", 999, "revenue_tier"], "verified"]], "corrupt"])
def test_z12_unusable_edits_take_today_s_path_and_drop_the_key(zelle_store, edits):
    payload = fx.case("Z1")
    payload["zelle_counted_reading"] = edits
    job = _job(zelle_store, payload)
    response = _review(job, PAT_ROW, "confirm")
    assert response.status_code == 200
    stored = zelle_store.get(job).analysis
    assert "zelle_counted_reading" not in stored
    assert fx.row(stored, fx.PAT)["classification"]["revenue_review_status"] == "confirmed"
    # Today's valve: a reject on the stored reading's excluded row is refused, never a 404 or a 500.
    assert _review(job, FABRIKAM_ROW, "reject").status_code == 400


def test_z12_the_audit_row_records_the_reading_shown(zelle_store):
    job = _job(zelle_store, fx.case("Z1"))
    assert _review(job, PAT_ROW, "reject").status_code == 200
    prior = json.loads(zelle_store.review_history(job)[0]["prior_state"])
    assert (prior["revenue_tier"], prior["revenue_tier_reason"]) == (COUNTED, "p2p")
    _shown(zelle_store, False)
    assert _review(job, FABRIKAM_ROW, "confirm").status_code == 200
    prior = json.loads(zelle_store.review_history(job)[1]["prior_state"])
    assert (prior["revenue_tier"], prior["revenue_tier_reason"]) == EXCLUDED


def test_z12_a_batch_materialises_the_shown_reading_once(zelle_store, monkeypatch):
    from webapp import jobs

    job = _job(zelle_store, fx.case("Z1"))
    calls = []
    real = jobs.zelle_view.reading

    def spy(payload, *, counted):
        calls.append(counted)
        return real(payload, counted=counted)

    monkeypatch.setattr(jobs.zelle_view, "reading", spy)
    zelle_store.apply_reviews(job, zelle_store.get(job).analysis, decisions=[
        (PAT_ROW, "confirm", None), (FABRIKAM_ROW, "confirm", None), (OWN_ROW, "confirm", None)],
        zelle_true_revenue=True)
    assert calls == [True]


def test_z12_a_copy_whose_only_decision_is_a_yes_reject_ranks_as_decided(zelle_store):
    from webapp.app import _copy_rank

    job = _job(zelle_store, fx.case("Z1"))
    assert _copy_rank(zelle_store.get(job))[2] == 1
    assert _review(job, PAT_ROW, "reject").status_code == 200
    stored = zelle_store.get(job).analysis
    assert not any(transaction["classification"].get("revenue_review_status") in {"confirmed", "rejected"}
                   for transaction in stored["statement"]["transactions"])
    assert _copy_rank(zelle_store.get(job))[2] == 0


# --- Z13: the replay (webapp/reanalysis.py) --------------------------------------------------------------------------


def _readings_of(payload, location):
    return {counted: next((transaction["classification"]["revenue_tier"],
                           transaction["classification"]["revenue_tier_reason"],
                           transaction["classification"]["revenue_review_status"])
                          for transaction in zelle_view.reading(payload, counted=counted)["statement"]["transactions"]
                          if transaction["classification"]["source_location"] == location)
            for counted in (True, False)}


def test_z13_a_yes_reject_and_a_confirm_are_replayed_into_their_readings(zelle_store):
    from webapp.reanalysis import replay_reviews

    job = _job(zelle_store, fx.case("Z1"))
    assert _review(job, PAT_ROW, "reject").status_code == 200
    assert _review(job, OWN_ROW, "confirm").status_code == 200
    history = zelle_store.review_history(job)
    replay = replay_reviews(fx.case("Z1"), history)
    assert len(replay.replayed) == 2 and replay.not_replayed == () and replay.decided_by_rules == ()
    live = zelle_store.get(job).analysis
    for location in (PAT_ROW, OWN_ROW, FABRIKAM_ROW):
        assert _readings_of(replay.analysis, location) == _readings_of(live, location)
    assert _readings_of(replay.analysis, PAT_ROW) == {
        True: ("non_revenue", "p2p", "rejected"), False: ("non_revenue", "zelle_excluded", "not_required")}


@pytest.mark.parametrize("first_shown", [True, False])
def test_z13_the_replay_reproduces_a_confirm_then_reject(zelle_store, first_shown):
    from webapp.reanalysis import replay_reviews

    job = _job(zelle_store, fx.case("Z1"))
    _shown(zelle_store, first_shown)
    assert _review(job, PAT_ROW, "confirm").status_code == 200
    _shown(zelle_store, True)
    assert _review(job, PAT_ROW, "reject").status_code == 200
    replay = replay_reviews(fx.case("Z1"), zelle_store.review_history(job))
    assert _readings_of(replay.analysis, PAT_ROW) == _readings_of(zelle_store.get(job).analysis, PAT_ROW) == {
        True: ("non_revenue", "p2p", "rejected"), False: ("non_revenue", "zelle_excluded", "not_required")}

"""A package member's revenue figures are its own sums over its rows, and they add up differently from the statement
viewed alone: builtin sum() per figure, each reason total rounded after every credit, the counted and held reasons in
the order they first appear. These packages pin that arithmetic, and what the member loop accepts from a payload the
analysis would never write: an unknown tier, a tier that disagrees with its state, a credit with no classification
record, a mix of tiered and tier-less credits, and a member whose rows carry no record at all. Fabricated CONTOSO
BANK statements of CONTOSO BAKERY LLC, 2031."""
from __future__ import annotations

import json

from tests.test_webapp_true_revenue import _package, _payload

#: The row positions of test_webapp_true_revenue.ROWS: a verified customer payment, a counted check deposit, a held
#: financing credit, a non-revenue transfer and a card debit.
VERIFIED, COUNTED, HELD, NON_REVENUE, DEBIT = range(5)


def _with(payload: dict, position: int, **record) -> dict:
    payload["statement"]["transactions"][position]["classification"].update(record)
    return payload


def _member(*payloads) -> dict:
    return _package(*payloads)["documents"][0]


def test_a_member_adds_its_credits_with_builtin_sum():
    # 0.215 + 0.2 + 0.3 is 0.7150000000000001 added one at a time and 0.715 (just under) in builtin sum().
    payload = _payload([(2, "MOBILE DEPOSIT", 0.215), (3, "MOBILE DEPOSIT", 0.2), (4, "MOBILE DEPOSIT", 0.3)])
    package = _package(payload)
    member = package["documents"][0]
    assert payload["metrics"]["total_posted_credits"] == 0.72
    assert (member["total_posted_credits"], member["unverified_deposit_total"],
            member["excluded_pending_review_total"]) == (0.71, 0.71, 0.71)
    assert (package["totals"]["total_posted_credits"], package["totals"]["excluded_pending_review_total"]) == (0.71, 0.71)
    # builtin sum() of no credit is the integer 0, and the downloads print it so.
    assert json.dumps([member["verified_revenue_total"], member["counted_flagged_total"]]) == "[0, 0]"


def test_a_member_rounds_each_reason_total_after_every_credit():
    payload = _payload([(2, "MOBILE DEPOSIT", 0.004), (3, "MOBILE DEPOSIT", 0.004),
                        (4, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0)])
    package = _package(payload)
    member = package["documents"][0]
    assert payload["metrics"]["excluded_pending_review_by_reason"] == {"non_sale_purpose": {"count": 2, "total": 0.01}}
    assert member["excluded_pending_review_total"] == 0.01
    assert member["excluded_pending_review_by_reason"] == {"non_sale_purpose": {"count": 2, "total": 0.0}}
    assert package["totals"]["excluded_pending_review_by_reason"] == {"non_sale_purpose": {"count": 2, "total": 0.0}}


def test_an_established_member_with_no_credit_prints_zero_as_its_rows_add_it():
    # Rows that carry records add their figures, and builtin sum() of no credit is the integer 0. A statement of no
    # row adds none: its figures are the stored and default floats.
    figures = ("total_posted_credits", "true_revenue_total", "counted_flagged_total", "excluded_pending_review_total")
    debits_only = _member(_payload([(9, "CARD PURCHASE FABRIKAM SUPPLY", -120.0)]))
    no_row = _member(_payload([]))
    assert debits_only["revenue_established"] and no_row["revenue_established"]
    assert json.dumps([debits_only[key] for key in figures]) == "[0, 0, 0, 0]"
    assert json.dumps([no_row[key] for key in figures]) == "[0.0, 0.0, 0.0, 0.0]"


def test_counted_reasons_keep_their_ledger_order_and_non_revenue_reasons_are_sorted():
    payload = _payload([(day, "MOBILE DEPOSIT", amount) for day, amount in
                        ((2, 300.0), (3, 200.0), (4, 100.0), (5, 50.0), (6, 25.0))])
    _with(payload, 0, revenue_tier_reason="p2p")
    _with(payload, 2, revenue_tier_reason="wire_named_sender")
    for position, reason in ((3, "zelle_excluded"), (4, "asset_sale_proceeds")):
        _with(payload, position, revenue_classification="non_revenue", revenue_tier="non_revenue",
              revenue_tier_reason=reason)
    package = _package(payload)
    member = package["documents"][0]
    assert list(member["counted_flagged_by_reason"]) == ["p2p", "check_deposit", "wire_named_sender"]
    assert list(member["non_revenue_by_reason"]) == ["asset_sale_proceeds", "zelle_excluded"]
    assert list(package["totals"]["counted_flagged_by_reason"]) == ["p2p", "check_deposit", "wire_named_sender"]
    assert list(package["totals"]["non_revenue_by_reason"]) == ["asset_sale_proceeds", "zelle_excluded"]


def test_a_credit_with_an_unknown_tier_counts_in_its_state_and_in_no_tier():
    member = _member(_with(_payload(), COUNTED, revenue_tier="legacy_tier"))
    assert (member["revenue_established"], member["unverified_deposit_total"], member["counted_flagged_total"],
            member["true_revenue_total"], member["counted_flagged_by_reason"]) == (True, 1200.0, 0, 700.0, {})
    assert member["revenue_reconciles"]


def test_a_credit_whose_tier_disagrees_with_its_state_counts_in_both():
    member = _member(_with(_payload(), VERIFIED, revenue_tier="counted_flagged", revenue_tier_reason="p2p"))
    assert (member["verified_revenue_total"], member["counted_flagged_total"], member["true_revenue_total"]) == (
        700.0, 1000.0, 1000.0)
    assert member["counted_flagged_by_reason"] == {"p2p": {"count": 1, "total": 700.0},
                                                   "check_deposit": {"count": 1, "total": 300.0}}
    assert member["revenue_reconciles"]


def test_a_credit_with_no_record_is_posted_in_no_state_and_the_non_revenue_reasons_stay():
    unrecorded = _with(_payload(), NON_REVENUE, revenue_tier_reason="zelle_excluded")
    del unrecorded["statement"]["transactions"][COUNTED]["classification"]
    stateless = _with(_with(_payload(), NON_REVENUE, revenue_tier_reason="zelle_excluded"), COUNTED,
                      revenue_classification="unknown_state")
    for payload in (unrecorded, stateless):
        package = _package(payload)
        member = package["documents"][0]
        assert (member["total_posted_credits"], member["total_posted_credit_count"], member["unverified_deposit_total"],
                member["revenue_reconciles"], member["revenue_established"]) == (2000.0, 4, 900.0, False, False)
        assert (member["true_revenue_total"], member["counted_flagged_by_reason"]) == (None, None)
        assert member["non_revenue_by_reason"] == {"zelle_excluded": {"count": 1, "total": 100.0}}
        assert package["totals"]["non_revenue_by_reason"] == {"zelle_excluded": {"count": 1, "total": 100.0}}


def test_a_member_tiered_only_in_part_has_no_tier_figure_and_keeps_its_non_revenue_reasons():
    package = _package(_with(_with(_payload(), NON_REVENUE, revenue_tier_reason="zelle_excluded"), COUNTED,
                             revenue_tier=None))
    member = package["documents"][0]
    assert (member["revenue_reconciles"], member["revenue_established"], member["true_revenue_total"],
            member["excluded_pending_review_by_reason"]) == (True, False, None, None)
    assert member["non_revenue_by_reason"] == {"zelle_excluded": {"count": 1, "total": 100.0}}
    assert package["totals"]["non_revenue_by_reason"] == {"zelle_excluded": {"count": 1, "total": 100.0}}


def test_a_member_reconciles_on_cents_alone_and_the_package_on_counts_too():
    # The tenth of a cent with no record is a posted credit in no state: the cents agree, the counts do not.
    payload = _payload([(2, "NORTHWIND SUPPLY LLC DES:PAYMENT ID:1", 700.0), (3, "MOBILE DEPOSIT", 0.001)])
    del payload["statement"]["transactions"][1]["classification"]
    package = _package(payload)
    member = package["documents"][0]
    assert (member["total_posted_credits"], member["total_posted_credit_count"], member["verified_revenue_count"]) == (
        700.0, 2, 1)
    assert member["revenue_reconciles"]
    assert not package["totals"]["revenue_reconciles"]


def test_one_classification_record_moves_a_member_from_its_stored_figures_to_its_rows():
    stored_reasons = {"zelle_excluded": {"count": 9, "total": 9.0}}
    stored = _payload()
    stored["metrics"]["non_revenue_by_reason"] = stored_reasons
    for row in stored["statement"]["transactions"]:
        del row["classification"]
    member = _member(stored)
    assert (member["total_posted_credits"], member["verified_revenue_total"], member["unverified_deposit_total"],
            member["revenue_reconciles"], member["non_revenue_by_reason"]) == (2000.0, 700.0, 1200.0, True,
                                                                              stored_reasons)
    rows = _payload()
    rows["metrics"]["non_revenue_by_reason"] = stored_reasons
    for row in rows["statement"]["transactions"][:DEBIT]:
        del row["classification"]
    member = _member(rows)
    assert (member["total_posted_credits"], member["total_posted_credit_count"], member["verified_revenue_total"],
            member["unverified_deposit_total"], member["revenue_reconciles"], member["non_revenue_by_reason"]) == (
        2000.0, 4, 0, 0, False, {})

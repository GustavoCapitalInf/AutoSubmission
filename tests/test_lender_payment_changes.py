"""The owner's request of 2026-10-06 (lender payment changes; true revenue spec §2.2, §9.1, §17.1, §20; R2-OW18): "can
we also detect when a payment to lender has decreased? That would be a really important metric to track." Clarified:
"Decreases, increases, stops", "Sustained, 10%+ drop", "Confirmed + potential".

The pure module (analysis/lender_payment_changes.py) on fabricated rows: classification records built by `_row` (or
their asdict() dicts, L29), posted, with the paid flag set. Information only: the module reads records and returns new
items; nothing else moves.

Fabricated rows only: KAPITUS, ONDECK and CanaCap (public funders of the registry, as the lender tests use them),
'Unidentified lender obligation' and 'Northwind Funding' potential payees with fabricated keys, 2054 dates, neutral
whole amounts. 2054 facts: Good Friday 03-27 (a CA holiday only), Memorial Day 05-25 (US), Victoria Day 05-18 (CA),
Juneteenth 06-19 (US, a Friday), July 4 a Saturday (no Fed closure)."""
from __future__ import annotations

import itertools
from dataclasses import asdict
from datetime import date, timedelta

import pytest

from analysis import lender_payment_changes as lpc
from analysis.transaction_classifier import TransactionClassification

UNNAMED = "Unidentified lender obligation"


def M(day):  # noqa: N802
    return date(2054, 3, day)


def A(day):  # noqa: N802
    return date(2054, 4, day)


def F(day):  # noqa: N802
    return date(2054, 2, day)


def Y(day):  # noqa: N802
    return date(2054, 5, day)


def J(day):  # noqa: N802
    return date(2054, 6, day)


def bdays(first, last, calendar="US"):
    """The business days from `first` to `last` of the module's calendar."""
    days, day = [], first
    while day <= last:
        if day.weekday() < 5 and day not in lpc._holidays(calendar, day.year):
            days.append(day)
        day += timedelta(days=1)
    return days


def every(first, last, step=7):
    days, day = [], first
    while day <= last:
        days.append(day)
        day += timedelta(days=step)
    return days


def _row(day, amount, entity="KAPITUS", state="confirmed_lender", **flags):
    """One posted debit of `amount` (a positive figure) to `entity`, with its state's paid flag."""
    values = dict(original_description="FABRICATED DEBIT", normalized_description="FABRICATED DEBIT",
                  classification=state, date=day.isoformat(), amount=-float(amount), direction="debit",
                  canonical_entity=entity, contributes_to_lender_totals=state == "confirmed_lender",
                  contributes_to_potential_lender_totals=state == "potential_lender")
    values.update(flags)
    return TransactionClassification(**values)


def _rows(days, amount, **kwargs):
    return [_row(day, amount, **kwargs) for day in days]


def _potential(days, amount, key="0000aaaa0000aaaa", entity=UNNAMED, label=None, **flags):
    return _rows(days, amount, entity=entity, state="potential_lender", potential_payee_key=key,
                 potential_payee_label=label, **flags)


def _credit(day, amount, entity="KAPITUS", **flags):
    values = dict(original_description="FABRICATED CREDIT", normalized_description="FABRICATED CREDIT",
                  classification="other", date=day.isoformat(), amount=float(amount), direction="credit",
                  canonical_entity=entity)
    values.update(flags)
    return TransactionClassification(**values)


def _located(rows):
    ordered = sorted(rows, key=lambda record: record.date)
    return [TransactionClassification(**{**asdict(record), "source_location": f"transaction:{index}"})
            for index, record in enumerate(ordered, start=1)]


def changes(rows, start=M(1), end=M(31), currency="USD"):
    return lpc.statement_payment_changes(_located(rows), period_start=start and start.isoformat(),
                                         period_end=end and end.isoformat(), currency=currency)


def only(rows, **kwargs):
    [item] = changes(rows, **kwargs)
    return item


# ------------------------------------------------------------------------------------------------ L1-L5: the rule
def test_l1_a_sustained_decrease_is_one_item_with_its_fields():
    item = only(_rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600))
    assert (item["kind"], item["change_percent"], item["payments_before"], item["payments_after"]) == (
        "decrease", -29, 10, 8)
    assert (item["last_before_date"], item["first_after_date"], item["last_after_date"]) == (
        "2054-03-13", "2054-03-16", "2054-03-25")
    assert (item["lender"], item["lender_label"], item["lender_label_after"], item["lender_state"]) == (
        "KAPITUS", "KAPITUS", "KAPITUS", "confirmed")
    assert (item["position"], item["positions"], item["scope"]) == (1, 1, "statement")
    assert (item["cadence_before"], item["cadence_after"], item["amount_before"], item["amount_after"]) == (
        "daily", "daily", 850.0, 600.0)
    assert item["cadence_changed"] is False and item["schedule_confirmed"] is True
    assert "weekly_equivalent_before" not in item and "weekly_equivalent_after" not in item
    assert (item["restart"], item["pause_business_days"], item["back_to_earlier"], item["reverted"],
            item["reverted_date"]) == (False, None, False, False, None)
    assert item["locations"] == {"last_before": "transaction:10", "first_after": "transaction:11"}
    # Every nested note is absent when not set, and no internal key or `account` key is published.
    assert not {"after_funding", "via"} & set(item)
    assert not any(key.startswith("_") or key in ("account", "account_number") for key in item)


def test_l2_a_sustained_increase_mirrors_the_decrease():
    item = only(_rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 1050))
    assert (item["kind"], item["change_percent"]) == ("increase", 24)


def test_l3_a_one_off_short_payment_is_no_item():
    assert changes(_rows(bdays(M(2), M(13)), 850) + _rows([M(16)], 425) + _rows(bdays(M(17), M(26)), 850)) == []


def test_l4_the_new_amount_must_hold_for_two_payments():
    assert changes(_rows(bdays(M(2), M(30)), 850) + _rows([M(31)], 600)) == []
    item = only(_rows(bdays(M(2), M(27)), 850) + _rows([M(30), M(31)], 600))
    assert (item["kind"], item["payments_before"], item["payments_after"]) == ("decrease", 20, 2)


@pytest.mark.parametrize("amount,expected", [(774, None), (765, ("decrease", -10)), (935, ("increase", 10)),
                                             (926, None)])
def test_l5_the_threshold_is_exact_arithmetic(amount, expected):
    found = changes(_rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), amount))
    assert [(item["kind"], item["change_percent"]) for item in found] == ([expected] if expected else [])


def test_l6_a_catch_up_double_is_no_item():
    rows = _rows(bdays(M(2), M(6)), 500) + _rows([M(11), M(12)], 1000) + _rows(bdays(M(13), M(31)), 500)
    assert changes(rows) == []


def test_l7_a_weekly_payment_split_into_daily_debits_is_no_item():
    assert changes(_rows([M(2), M(9), M(16), M(30)], 1500) + _rows([M(23), M(24), M(25)], 500)) == []


# ----------------------------------------------------------------------------------------- L8-L9b: schedule changes
def test_l8_a_schedule_change_at_an_equal_weekly_equivalent_is_never_an_increase():
    item = only(_rows(bdays(M(2), M(20)), 500) + _rows(every(M(23), A(13)), 2500), end=A(17))
    assert (item["kind"], item["change_percent"], item["cadence_changed"]) == ("cadence_change", 0, True)
    assert (item["weekly_equivalent_before"], item["weekly_equivalent_after"]) == (2500.0, 2500.0)
    assert (item["cadence_before"], item["cadence_after"], item["payments_before"], item["payments_after"]) == (
        "daily", "weekly", 15, 4)


def test_l9_a_schedule_change_with_a_lower_weekly_equivalent_is_a_decrease():
    item = only(_rows(bdays(M(2), M(20)), 500) + _rows(every(M(23), A(13)), 1500), end=A(17))
    assert (item["kind"], item["cadence_changed"], item["change_percent"], item["schedule_confirmed"]) == (
        "decrease", True, -40, True)
    assert (item["weekly_equivalent_before"], item["weekly_equivalent_after"]) == (2500.0, 1500.0)


def test_l9b_an_unconfirmed_pure_schedule_change_is_no_item_and_no_stop():
    assert changes(_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30)], 2500)) == []


# The orchestrator's choice of 2026-10-06 (§ Still open 18's alternative, following the owner's "2 or more payments"):
# a decrease or an increase at a new schedule held 2 payments, but not yet the 3 (5 if daily) that confirm it.
def test_still_open_18_a_change_at_a_new_schedule_held_two_payments_is_a_possible_decrease_at_the_end():
    item = only(_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30)], 1600))
    assert (item["kind"], item["schedule_confirmed"], item["cadence_changed"], item["change_percent"]) == (
        "decrease", False, True, -36)
    assert (item["payments_before"], item["payments_after"], item["first_after_date"]) == (15, 2, "2054-03-23")
    # The same daily payments split weekly into 4 daily debits at the end: a possible decrease too.
    item = only(_rows(every(M(2), M(16)), 2500) + _rows(bdays(M(23), M(26)), 300), end=M(27))
    assert (item["kind"], item["schedule_confirmed"], item["change_percent"], item["payments_after"]) == (
        "decrease", False, -40, 4)


def test_still_open_18_once_the_confirming_payments_exist_it_reads_as_the_confirmed_line():
    item = only(_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30), A(6)], 1600), end=A(10))
    assert (item["kind"], item["schedule_confirmed"], item["payments_after"]) == ("decrease", True, 3)


def test_still_open_18_mid_position_the_change_shows_when_its_two_payments_span_the_cycle():
    rows = _rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30)], 1600)
    found = changes(rows + _rows(bdays(A(6), A(17)), 400), end=A(17))
    assert [(item["kind"], item["schedule_confirmed"], item["change_percent"], item["first_after_date"])
            for item in found] == [("decrease", False, -36, "2054-03-23"), ("decrease", True, -20, "2054-04-06")]
    # Back at the earlier payment: one possible decrease, marked temporary.
    [item] = changes(rows + _rows(bdays(A(6), A(17)), 500), end=A(17))
    assert (item["schedule_confirmed"], item["payments_before"], item["last_before_date"], item["reverted"],
            item["reverted_date"]) == (False, 15, "2054-03-20", True, "2054-04-06")


def test_still_open_18_a_daily_split_mid_position_never_holds_a_weekly_equivalent():
    # L7's split, mid-position (it returns to the weekly payment): its 3 daily debits span 2 days, under a cycle.
    assert changes(_rows([M(2), M(9), M(16), M(30)], 1500) + _rows([M(23), M(24), M(25)], 500)) == []


# The orchestrator's choice of 2026-10-06 (§ Still open 23's alternative): each regime is compared with the last
# REPORTED level of its position, so steps under 10% add up.
def test_still_open_23_steps_under_ten_percent_are_reported_once_they_add_up():
    rows = (_rows(every(M(2), M(23)), 1000) + _rows(every(M(30), A(20)), 950)
            + _rows(every(A(27), Y(18)), 880))
    item = only(rows, end=Y(20))
    assert (item["kind"], item["amount_before"], item["amount_after"], item["change_percent"]) == (
        "decrease", 1000.0, 880.0, -12)
    # R2-OW18 review round 1: each unreported level carries the step into it, and the item the last step.
    assert item["via"] == [{"amount": 950.0, "cadence": "weekly", "change_percent": -5}]
    assert item["last_step_percent"] == -7
    assert (item["payments_before"], item["payments_after"], item["first_after_date"]) == (4, 4, "2054-04-27")


def test_still_open_23_a_drift_that_returns_is_never_reported():
    rows = (_rows(every(M(2), M(23)), 1000) + _rows(every(M(30), A(20)), 1080)
            + _rows(every(A(27), Y(18)), 970))
    assert changes(rows, end=Y(20)) == []


def test_still_open_23_the_reference_moves_to_each_reported_level():
    rows = (_rows(every(M(2), M(23)), 1000) + _rows(every(M(30), A(20)), 700)
            + _rows(every(A(27), Y(18)), 660) + _rows(every(Y(25), J(15)), 600))
    found = changes(rows, end=J(19))
    assert [(item["kind"], item["amount_before"], item["amount_after"], item.get("via"), item.get("last_step_percent"))
            for item in found] == [
        ("decrease", 1000.0, 700.0, None, None),
        ("decrease", 700.0, 600.0, [{"amount": 660.0, "cadence": "weekly", "change_percent": -6}], -9)]


# ------------------------------------------------------------------------------------------------ L10: positions
def test_l10_two_positions_with_one_funder_are_separate_series():
    rows = (_rows(every(M(2), A(27)), 1000) + _rows(every(M(4), A(8)), 2100) + _rows(every(A(15), A(29)), 1500))
    item = only(rows, end=A(30))
    assert (item["kind"], item["position"], item["positions"], item["change_percent"], item["payments_before"],
            item["payments_after"]) == ("decrease", 2, 2, -29, 6, 3)


def test_l10b_a_second_stream_that_starts_while_the_first_pays_is_a_new_stream():
    item = only(_rows(every(M(2), A(27)), 1000) + _rows(every(M(18), A(29)), 2100), end=A(30))
    assert (item["kind"], item["position"], item["positions"], item["amount_after"], item["cadence_after"],
            item["first_after_date"], item["payments_after"]) == (
        "new_stream", 2, 2, 2100.0, "weekly", "2054-03-18", 7)
    assert item["alongside"] == [{"position": 1, "cadence": "weekly", "amount": 1000.0}]
    assert (item["weekly_total_before"], item["weekly_total_after"], item["change_percent"]) == (1000.0, 3100.0, 210)
    assert item["locations"] == {"first_after": "transaction:4"}


def test_l10b_controls():
    # Starting 7 business days after the first stream, inside its grace: nothing.
    assert changes(_rows(every(M(2), A(27)), 1000) + _rows(every(M(11), A(29)), 2100), end=A(30)) == []
    # The first stream pays only twice after the second starts: no new stream (its stop is L23's shape).
    found = changes(_rows(every(M(2), M(30)), 1000) + _rows(every(M(18), A(29)), 2100), end=A(30))
    assert [item["kind"] for item in found] == ["stop"]
    # A stream of 6% of the weekly total, above the fee test's 5%: no item.
    assert changes(_rows(every(M(2), A(27)), 1000) + _rows(every(M(18), A(29)), 60), end=A(30)) == []


# ------------------------------------------------------------------------------- L12: bounced and reversed rows
def test_l12_a_series_whose_last_payments_bounce_has_not_stopped():
    paid = _rows(every(M(4), A(8)), 1000)
    attempts = _rows(every(A(15), A(29)), 1000, returned_funder_payment_by="transaction:99")
    assert changes(paid + attempts, end=A(30)) == []
    item = only(paid, end=A(30))
    assert (item["kind"], item["quiet_business_days"], item["grace_business_days"], item["stop_confirmed"]) == (
        "stop", 16, 10, False)


def test_l12_the_last_presence_an_attempt_is_named():
    paid = _rows(every(M(4), A(1)), 1000)
    attempt = _rows([A(8)], 1000, returned_funder_payment_by="transaction:99")
    item = only(paid + attempt, end=Y(1))
    assert (item["last_presence_date"], item["last_payment_date"], item["last_attempt_returned"]) == (
        "2054-04-08", "2054-04-01", {"date": "2054-04-08"})


# --------------------------------------------------------------------------------------------- L13, L14, L15: notes
def test_l13_a_renewal_names_the_funding_credit():
    rows = _rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 1050)
    item = only(rows + [_credit(M(13), 25000)])
    assert (item["kind"], item["change_percent"], item["after_funding"]) == (
        "increase", 24, {"date": "2054-03-13", "amount": 25000.0})
    # The revenue entity counts as well.
    assert only(rows + [_credit(M(13), 25000, entity=None, revenue_canonical_entity="KAPITUS")])["after_funding"] == {
        "date": "2054-03-13", "amount": 25000.0}
    # More than 20 days before, or more than 5 days after, the new amount's first payment: no note.
    assert "after_funding" not in only(rows + [_credit(F(20), 25000)])
    assert "after_funding" not in only(rows + [_credit(M(23), 25000)])


def test_l14_a_temporary_cut_and_its_restoration():
    rows = _rows(bdays(M(2), M(11)), 850) + _rows(bdays(M(12), M(18)), 600) + _rows(bdays(M(19), M(26)), 850)
    decrease, increase = changes(rows)
    assert (decrease["kind"], decrease["change_percent"], decrease["reverted"], decrease["reverted_date"]) == (
        "decrease", -29, True, "2054-03-19")
    assert (increase["kind"], increase["change_percent"], increase["back_to_earlier"]) == ("increase", 42, True)


def test_l15_a_restart_after_a_pause():
    item = only(_rows(every(M(2), M(23)), 1000) + _rows(every(A(20), Y(4)), 700), end=Y(8))
    assert (item["kind"], item["change_percent"], item["restart"], item["pause_business_days"]) == (
        "decrease", -30, True, 20)


# ------------------------------------------------------------------------------------------- L16-L21: stops
@pytest.mark.parametrize("days,start,end,expected", [
    # Daily, grace 5: Memorial Day 05-25 is not counted.
    (bdays(Y(1), Y(21)), Y(1), Y(29), None),
    (bdays(Y(1), Y(20)), Y(1), Y(29), (6, 5)),
    # Weekly, grace 10.
    (every(A(2), Y(14)), A(1), Y(29), None),
    (every(A(1), Y(13)), A(1), Y(29), (11, 10)),
    # Biweekly, grace 15 (Thursdays then Wednesdays, across weekends and Memorial Day).
    ([A(9), A(23), Y(7)], A(1), Y(29), None),
    ([A(8), A(22), Y(6)], A(1), Y(29), (16, 15)),
    # Monthly, grace 25 (across Memorial Day and Juneteenth).
    ([M(22), A(22), Y(22)], M(1), J(30), None),
    ([M(21), A(21), Y(21)], M(1), J(30), (26, 25)),
])
def test_l16_the_stop_windows_one_business_day_either_side(days, start, end, expected):
    found = changes(_rows(days, 1000), start=start, end=end)
    if expected is None:
        assert found == []
        return
    [item] = found
    assert (item["kind"], item["quiet_business_days"], item["grace_business_days"], item["stop_confirmed"]) == (
        "stop", *expected, False)
    assert (item["coverage_end"], item["coverage_end_source"]) == (end.isoformat(), "period_end")


def test_l16_the_weekly_stop_item_fields():
    item = only(_rows(every(A(1), Y(13)), 1000), start=A(1), end=Y(29))
    assert (item["cadence"], item["last_payment_date"], item["last_payment_amount"], item["payments"],
            item["last_presence_date"]) == ("weekly", "2054-05-13", 1000.0, 7, "2054-05-13")
    assert item["locations"] == {"last_payment": "transaction:7"}
    assert not {"other_debits_after", "payoff", "continues_as", "other_stream_continues", "last_attempt_returned",
                "debt_relief_after", "new_lender_after", "continues_in_other_account"} & set(item)


def test_l17_statement_end_truncation_for_a_potential_series():
    assert changes(_potential(bdays(Y(1), Y(21)), 300), start=Y(1), end=Y(29)) == []
    item = only(_potential(bdays(Y(1), Y(20)), 300), start=Y(1), end=Y(29))
    assert (item["kind"], item["lender_state"], item["stop_confirmed"], item["scope"]) == (
        "stop", "potential", False, "statement")


def test_l18_no_printed_period_end_reads_to_the_last_transaction():
    other = TransactionClassification(original_description="FABRICATED", normalized_description="FABRICATED",
                                      classification="other", date=M(31).isoformat(), amount=-50.0)
    item = only(_rows([F(13), F(20), F(27), M(6)], 1000) + [other], start=None, end=None)
    assert (item["kind"], item["quiet_business_days"], item["coverage_end"], item["coverage_end_source"]) == (
        "stop", 17, "2054-03-31", "last_transaction")


def test_l19_fewer_than_three_payments_never_stop():
    assert changes(_rows([M(2), M(9)], 1000), end=A(30)) == []


def test_l20_a_final_large_debit_is_a_possible_payoff():
    item = only(_rows([F(2), M(2), A(2)], 2000) + _rows([A(20)], 5000), start=F(1), end=J(30))
    assert (item["kind"], item["quiet_business_days"], item["grace_business_days"], item["payoff"]) == (
        "stop", 61, 25, {"date": "2054-04-20", "amount": 5000.0})


def test_l21_another_funder_at_the_same_amount_continues_it():
    kapitus = _rows(bdays(M(2), M(13)), 850)
    item = only(kapitus + _rows(bdays(M(17), M(31)), 860, entity="ONDECK"))
    assert (item["kind"], item["quiet_business_days"]) == ("stop", 12)
    assert item["continues_as"] == {"lender": "ONDECK", "lender_label": "ONDECK", "lender_state": "confirmed",
                                    "amount": 860.0, "first_date": "2054-03-17"}
    assert "new_lender_after" not in item


def test_l21_another_funder_at_another_amount_is_a_new_lender_series():
    item = only(_rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(17), M(31)), 1000, entity="ONDECK"))
    assert "continues_as" not in item
    assert item["new_lender_after"] == {"lender": "ONDECK", "lender_label": "ONDECK", "lender_state": "confirmed",
                                        "amount": 1000.0, "cadence": "daily", "first_date": "2054-03-17"}


def _relief(day):
    return TransactionClassification(original_description="FABRICATED", normalized_description="FABRICATED",
                                     classification="debt_relief", date=day.isoformat(), amount=-300.0,
                                     flagged_group="debt_relief")


def test_l21_a_debt_relief_program_starting_after_the_stop_is_noted():
    kapitus = _rows(bdays(M(2), M(13)), 850)
    assert only(kapitus + [_relief(M(18)), _relief(M(25))])["debt_relief_after"] == {"date": "2054-03-18"}
    assert "debt_relief_after" not in only(kapitus + [_relief(M(5)), _relief(M(18))])


# ---------------------------------------------------------------------------------------- L22, L23: fee streams
def test_l22_a_fee_stream_is_never_a_signal():
    assert changes(_rows(every(F(2), Y(25)), 1000) + _rows([F(2), M(2), A(1)], 15), start=F(1), end=Y(29)) == []


def test_l22b_a_fee_stream_is_read_on_its_weekly_equivalent():
    rows = _rows(bdays(F(2), Y(29)), 1000) + _rows([F(2), M(2), A(1)], 100)
    assert changes(rows, start=F(1), end=Y(29)) == []


def test_l23_an_overlapping_amount_change_reads_as_a_stop_with_another_stream():
    item = only(_rows(every(M(2), M(30)), 1000) + _rows(every(M(18), A(29)), 1200), end=A(30))
    assert (item["kind"], item["position"], item["positions"], item["quiet_business_days"]) == ("stop", 1, 2, 23)
    assert item["other_stream_continues"] == {"amount": 1200.0, "cadence": "weekly"}


# --------------------------------------------------------------------------------------- L24-L25: potential payees
def test_l24_a_potential_payee_is_followed_across_its_labels():
    rows = (_potential(bdays(M(2), M(13)), 300, label=f"{UNNAMED} (daily, 300.00)")
            + _potential(bdays(M(16), M(25)), 250, label=f"{UNNAMED} (daily, 250.00)"))
    item = only(rows)
    assert (item["kind"], item["lender_state"], item["change_percent"], item["lender"]) == (
        "decrease", "potential", -17, UNNAMED)
    assert (item["lender_label"], item["lender_label_after"]) == (f"{UNNAMED} (daily, 300.00)",
                                                                  f"{UNNAMED} (daily, 250.00)")


def test_l25_potential_rows_with_different_keys_are_never_one_series():
    rows = _potential(bdays(M(2), M(13)), 300, key="1111") + _potential(bdays(M(16), M(25)), 250, key="2222")
    assert [item["kind"] for item in changes(rows)] == ["stop"]
    rows = _potential(bdays(M(2), M(6)), 300, key="1111") + _potential(bdays(M(9), M(13)), 300, key="2222")
    assert all(item["kind"] == "stop" for item in changes(rows))


def test_a_potential_row_without_a_key_is_no_payment():
    assert changes(_potential(bdays(M(2), M(13)), 300, key=None)) == []


# ------------------------------------------------------------------------------------------ L26, L27: calendars
def test_l26_the_canadian_calendar_on_a_cad_statement():
    canadian = only(_rows(bdays(Y(1), Y(21), "CA"), 850, entity="CanaCap"), start=Y(1), end=Y(29), currency="CAD")
    assert (canadian["kind"], canadian["quiet_business_days"]) == ("stop", 6)
    assert changes(_rows(bdays(Y(1), Y(21)), 850, entity="CanaCap"), start=Y(1), end=Y(29)) == []


def test_l27_juneteenth_is_a_us_holiday():
    assert changes(_rows(bdays(J(1), J(18)), 850), start=J(1), end=J(26)) == []


def test_the_canadian_calendar_is_payments_canadas_published_closure_schedule():
    # https://www.payments.ca/system-closure-schedule (2026), read 2026-10-06: the Civic Holiday is not a closure day,
    # and Boxing Day on a Saturday closes the Monday.
    assert sorted(lpc._canadian_bank_holidays(2026)) == [
        date(2026, 1, 1), date(2026, 4, 3), date(2026, 5, 18), date(2026, 7, 1), date(2026, 9, 7),
        date(2026, 9, 30), date(2026, 10, 12), date(2026, 11, 11), date(2026, 12, 25), date(2026, 12, 28)]
    assert {date(2054, 3, 27), date(2054, 5, 18)} <= lpc._canadian_bank_holidays(2054)
    assert date(2054, 3, 27) not in lpc._holidays("US", 2054) and date(2054, 5, 25) in lpc._holidays("US", 2054)
    assert lpc.calendar_for("CAD") == "CA" and lpc.calendar_for("USD") == "US" and lpc.calendar_for(None) == "US"


def test_business_days_and_cadence():
    assert lpc.business_days_between(Y(22), Y(26)) == 1  # Memorial Day and the weekend
    assert lpc.business_days_between(Y(26), Y(22)) == 0
    assert lpc.payment_cadence(bdays(M(2), M(13))) == "daily"
    assert lpc.payment_cadence(every(M(2), M(30))) == "weekly"
    assert lpc.payment_cadence([M(1), M(16), A(1), A(16)]) == "semimonthly"
    assert lpc.payment_cadence([M(1), M(15), A(1), A(15)]) == "biweekly"  # a median gap of 14 days
    assert lpc.payment_cadence(every(M(2), A(27), 14)) == "biweekly"
    assert lpc.payment_cadence([F(2), M(2), A(2)]) == "monthly"
    assert lpc.payment_cadence([M(2), M(4), M(6), M(9)]) == "daily_irregular"
    assert lpc.payment_cadence([M(2)]) == "single"


# ------------------------------------------------------------------------------------------- L28, L29: the rows
def test_l28_duplicates_reversals_and_unposted_rows():
    rows = _rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600)
    base = only(rows)
    assert only(rows + _rows([M(20)], 600, duplicate_of="transaction:1"))["payments_after"] == base["payments_after"]
    assert only(rows + _rows([M(31)], 600, is_posted=False)) == base
    # A reversed debit is an attempt: presence, never an amount.
    paid = _rows(every(M(4), A(8)), 1000)
    reversed_rows = _rows(every(A(15), A(29)), 1000, reversed_by="transaction:99",
                          contributes_to_lender_totals=False)
    assert changes(paid + reversed_rows, end=A(30)) == []


def test_a_row_without_the_paid_flag_is_no_payment():
    rows = _rows(bdays(M(2), M(13)), 850, contributes_to_lender_totals=False)
    assert changes(rows) == []


def test_l29_records_and_their_dicts_give_equal_items():
    rows = _located(_rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600) + [_credit(M(13), 25000)])
    as_records = lpc.statement_payment_changes(rows, period_start="2054-03-01", period_end="2054-03-31",
                                               currency="USD")
    as_dicts = lpc.statement_payment_changes([asdict(row) for row in rows], period_start="2054-03-01",
                                             period_end="2054-03-31", currency="USD")
    assert as_records == as_dicts and as_records[0]["after_funding"]["amount"] == 25000.0


def test_an_undated_row_is_left_out():
    rows = _rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600)
    located = _located(rows)
    undated = TransactionClassification(**{**asdict(_row(M(2), 600)), "date": "", "source_location": "transaction:99"})
    period = {"period_start": "2054-03-01", "period_end": "2054-03-31", "currency": "USD"}
    assert lpc.statement_payment_changes(located + [undated], **period) == lpc.statement_payment_changes(located,
                                                                                                         **period)


def test_l30_the_constants_are_named_integers_and_fractions():
    assert (lpc.CHANGE_THRESHOLD_PERCENT, lpc.MIN_PAYMENTS_HELD, lpc.MIN_STOP_PAYMENTS, lpc.LEVEL_MERGE_PERCENT,
            lpc.FEE_STREAM_PERCENT, lpc.BEAT_KEPT_PERCENT, lpc.SHORT_REGIME_CYCLE_PERCENT) == (10, 2, 3, 1, 5, 60, 80)
    assert lpc.STOP_GRACE_BUSINESS_DAYS == {"daily": 5, "daily_irregular": 6, "weekly": 10, "biweekly": 15,
                                            "semimonthly": 15, "monthly": 25}
    assert (lpc.FUNDING_NOTE_DAYS_BEFORE, lpc.FUNDING_NOTE_DAYS_AFTER, lpc.PAYOFF_MULTIPLE, lpc.HANDOFF_PERCENT,
            lpc.DEBT_RELIEF_GRACE_MULTIPLE, lpc.POTENTIAL_MIN_WEEKLY_CENTS) == (20, 5, 2, 10, 2, 10000)
    assert (lpc.CATCH_UP_TOLERANCE_PERCENT, lpc.CATCH_UP_MULTIPLES, lpc.CATCH_UP_MAX_RUN) == (2, (2, 3), 2)
    # Audit round 3, R3-25: the exact multiples a one-off catch-up may be, and the late allowance of a due date.
    assert (lpc.CATCH_UP_PRESENCE_MULTIPLES, lpc.CATCH_UP_LATE_BUSINESS_DAYS) == ((2, 3, 4, 5, 6), 1)
    assert "catch_up" in lpc.PAYMENT_CHANGE_KINDS
    assert (lpc.CADENCE_CHANGE_MIN_PAYMENTS, lpc.CADENCE_CHANGE_MIN_DAILY) == (3, 5)
    # Audit round 3, R3-82: a credit this many days after a payment or attempt of its amount returns it (R2-OW13's
    # rule D window), never a funding.
    assert lpc.FUNDING_NOTE_RETURN_DAYS == 7
    # Audit round 4, R4-84: a regime whose own dates read no schedule borrows its level's only across gaps of this many
    # cycles of it (plus its beat tolerance).
    assert lpc.SPARSE_RUN_CYCLES == 2


# ------------------------------------------------------------------------------------------ L31-L33: the revision
def test_l31_payment_sized_debits_are_presence():
    rows = _rows(bdays(M(2), M(20)), 850) + _rows([M(23)], 400) + _rows([M(25)], 300) + _rows([M(26)], 500)
    assert changes(rows) == []


def test_l31_a_stop_after_other_debits_names_them():
    rows = _rows(bdays(M(2), M(13)), 850) + _rows([M(16)], 400) + _rows([M(17)], 300) + _rows([M(19)], 500)
    item = only(rows)
    assert (item["kind"], item["last_payment_date"], item["last_presence_date"], item["quiet_business_days"]) == (
        "stop", "2054-03-13", "2054-03-19", 8)
    assert item["other_debits_after"] == {"count": 3, "last_date": "2054-03-19"}


# Audit round 3, R3-25: the payoff-sized case is 1,750 (2.06x, no exact multiple); exactly 2x (1,700) is a catch-up
# since then, presence, and its own "Caught up" line (test_r3_25_the_l31_shape_at_exactly_twice_is_a_catch_up).
@pytest.mark.parametrize("amount", [20, 1750])
def test_l31_a_fee_sized_or_payoff_sized_debit_is_not_presence(amount):
    item = only(_rows(bdays(M(2), M(20)), 850) + _rows([M(26)], amount))
    assert (item["kind"], item["last_presence_date"], item["quiet_business_days"]) == ("stop", "2054-03-20", 7)
    assert item.get("payoff") == ({"date": "2054-03-26", "amount": 1750.0} if amount == 1750 else None)


def test_l32_a_pause_that_resumes_at_the_same_payment():
    item = only(_rows(bdays(M(2), M(6)) + bdays(M(16), M(31)), 850))
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"],
            item["grace_business_days"], item["cadence"], item["last_payment_amount"]) == (
        "pause", "2054-03-06", "2054-03-16", 6, 5, "daily", 850.0)
    assert (item["position"], item["positions"], item["lender_label"]) == (1, 1, "KAPITUS")
    assert item["locations"] == {"last_before": "transaction:5", "first_after": "transaction:6"}
    assert changes(_rows(bdays(M(2), M(6)) + bdays(M(13), M(31)), 850)) == []
    assert changes(_rows(bdays(M(2), M(6)) + bdays(M(16), M(31)), 850) + _rows([M(11)], 425)) == []


def test_l33_the_potential_materiality_floor():
    weeks = every(F(2), A(27))
    assert changes(_potential(weeks[:8], 60) + _potential(weeks[8:12], 40), start=F(1), end=A(30)) == []
    item = only(_potential(weeks[:8], 150) + _potential(weeks[8:12], 100), start=F(1), end=A(30))
    assert (item["kind"], item["lender_state"]) == ("decrease", "potential")
    item = only(_rows(weeks[:8], 60) + _rows(weeks[8:12], 40), start=F(1), end=A(30))
    assert (item["kind"], item["lender_state"]) == ("decrease", "confirmed")


def test_a_named_potential_series_reads_its_funding_credit():
    rows = (_potential(bdays(M(2), M(13)), 850, entity="Northwind Funding")
            + _potential(bdays(M(16), M(25)), 1050, entity="Northwind Funding"))
    assert only(rows + [_credit(M(13), 25000, entity="Northwind Funding")])["after_funding"]["amount"] == 25000.0
    unnamed = _potential(bdays(M(2), M(13)), 850) + _potential(bdays(M(16), M(25)), 1050)
    assert "after_funding" not in only(unnamed + [_credit(M(13), 25000, entity=UNNAMED)])


# --------------------------------------------------------------------------------------------- chains (part F4)
def test_a_chain_reads_across_statements_and_drops_an_overlap_repeat():
    march = _located(_rows(every(M(2), M(30)), 1000))
    april = _located(_rows([M(30)], 1000) + _rows(every(A(6), A(27)), 700))
    chain = [lpc.StatementRows(march, "2054-03-01", "2054-03-31", "USD"),
             lpc.StatementRows(april, "2054-03-29", "2054-04-30", "USD")]
    [item] = lpc.payment_changes(chain)
    assert (item["kind"], item["scope"], item["_from_statement"], item["_to_statement"], item["_source_statement"]) == (
        "decrease", "package", 0, 1, 1)
    # The 03-30 payment both statements print is counted once.
    assert (item["payments_before"], item["payments_after"], item["first_after_date"]) == (5, 4, "2054-04-06")
    assert item["_series_key"] == ("confirmed", "KAPITUS")


def test_a_one_statement_chain_equals_the_statement_but_for_its_scope_and_internal_keys():
    rows = _located(_rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600))
    [chain_item] = lpc.payment_changes([lpc.StatementRows(rows, "2054-03-01", "2054-03-31", "USD")])
    [statement_item] = lpc.statement_payment_changes(rows, period_start="2054-03-01", period_end="2054-03-31",
                                                     currency="USD")
    assert {**lpc.public_item(chain_item), "scope": "statement"} == statement_item


# ------------------------------------------------------------------- R2-OW18 review round 1 (fabricated rows only)
def _chain(*statements):
    """A module chain of (rows, period_start, period_end) statements, in USD."""
    return lpc.payment_changes([lpc.StatementRows(_located(rows), start.isoformat(), end.isoformat(), "USD")
                                for rows, start, end in statements])


def test_r1_a_change_through_unreported_levels_names_each_step_and_the_last_one():
    # An abrupt cut after a small drift: 1,000 -> 950 (-5%) -> 650 (-32%). The item is compared with 1,000 (§ Still
    # open 23) and names the step into each unreported level and the last step, so the cut never reads as drift.
    item = only(_rows(every(M(2), M(16)), 1000) + _rows(every(M(23), A(6)), 950) + _rows(every(A(13), A(27)), 650),
                end=A(30))
    assert (item["kind"], item["amount_before"], item["amount_after"], item["change_percent"]) == (
        "decrease", 1000.0, 650.0, -35)
    assert item["via"] == [{"amount": 950.0, "cadence": "weekly", "change_percent": -5}]
    assert item["last_step_percent"] == -32
    # No unreported level, no step fields.
    assert not {"via", "last_step_percent"} & set(only(_rows(bdays(M(2), M(13)), 850)
                                                      + _rows(bdays(M(16), M(25)), 600)))


def test_r1_a_possible_change_never_becomes_the_reference():
    # daily 500 -> weekly 1,600 held 2 (a possible decrease, § Still open 18) -> weekly 2,300 held 3: the second line
    # is compared with the daily 500 (the last confirmed level), and its steps show the rise from the possible level.
    possible, change = changes(_rows(bdays(M(2), M(13)), 500) + _rows([M(16), M(23)], 1600)
                               + _rows([M(30), A(6), A(13)], 2300), end=A(17))
    assert (possible["kind"], possible["schedule_confirmed"], possible["change_percent"]) == ("decrease", False, -36)
    assert "via" not in possible
    assert (change["kind"], change["cadence_before"], change["amount_before"], change["change_percent"]) == (
        "cadence_change", "daily", 500.0, -8)
    assert change["via"] == [{"amount": 1600.0, "cadence": "weekly", "change_percent": -36}]
    assert change["last_step_percent"] == 44


def test_r1_a_restart_pause_leaves_out_the_days_no_statement_covers():
    # March, then a statement from 04-08: the 5 business days of the hole are no pause, so no restart.
    [item] = _chain((_rows(bdays(M(2), M(31)), 500), M(1), M(31)), (_rows(bdays(A(8), Y(7)), 400), A(8), Y(7)))
    assert (item["kind"], item["change_percent"], item["restart"], item["pause_business_days"]) == (
        "decrease", -20, False, None)
    # A real pause beside a 2-day hole: the 15 business days from 03-13 to 04-03 less the hole's 2.
    [item] = _chain((_rows(bdays(M(2), M(13)), 500), M(1), M(31)), (_rows(bdays(A(3), Y(1)), 400), A(3), Y(1)))
    assert (item["kind"], item["restart"], item["pause_business_days"]) == ("decrease", True, 13)


def test_r1_a_pause_names_what_ended_it_and_when_payments_resumed():
    regular = _rows(bdays(M(2), M(6)) + bdays(M(23), M(31)), 850)
    item = only(regular + _rows([M(16)], 850, returned_funder_payment_by="transaction:99"))
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"]) == (
        "pause", "2054-03-06", "2054-03-16", 6)
    assert (item["first_after_kind"], item["resumed_date"]) == ("attempt", "2054-03-23")
    item = only(regular + _rows([M(16)], 425))
    assert (item["first_after_kind"], item["first_after_date"], item["resumed_date"]) == (
        "other_amount", "2054-03-16", "2054-03-23")
    # L32: the regime's own payment ends it.
    item = only(_rows(bdays(M(2), M(6)) + bdays(M(16), M(31)), 850))
    assert (item["first_after_kind"], item["first_after_date"], item["resumed_date"]) == (
        "payment", "2054-03-16", "2054-03-16")


def test_r1_a_stream_first_seen_within_one_cycle_of_the_coverage_start_is_not_new():
    # A monthly stream first paid 19 days into the chain may have been paying before it: no new stream.
    daily = bdays(M(2), Y(29))
    monthly = [M(20), A(20), Y(20)]
    months = ((M(1), M(31)), (A(1), A(30)), (Y(1), Y(29)))
    found = _chain(*((_rows([day for day in daily if start <= day <= end], 500)
                      + _rows([day for day in monthly if start <= day <= end], 2000), start, end)
                     for start, end in months))
    assert [item["kind"] for item in found] == []
    # First paid 50 days into the chain, a month after a covered date: a new stream.
    daily = bdays(M(2), J(30))
    monthly = [A(20), Y(20), J(22)]
    months += ((J(1), J(30)),)
    [item] = _chain(*((_rows([day for day in daily if start <= day <= end], 500)
                       + _rows([day for day in monthly if start <= day <= end], 2000), start, end)
                      for start, end in months))
    assert (item["kind"], item["cadence_after"], item["first_after_date"], item["change_percent"]) == (
        "new_stream", "monthly", "2054-04-20", 18)


def test_r1_a_stream_whose_previous_cycle_falls_in_a_coverage_hole_is_not_new():
    # Daily payments across a hole (03-31 to 04-08); a weekly stream first seen on 04-10 would have paid on 04-03,
    # inside the hole: no new stream. First seen on 04-17 (04-10 covered): a new stream.
    march, later = _rows(bdays(M(2), M(31)), 500), _rows(bdays(A(8), Y(29)), 500)
    for first, expected in ((A(10), []), (A(17), [("new_stream", "2054-04-17", 40)])):
        found = _chain((march, M(1), M(31)), (later + _rows(every(first, Y(29)), 1000), A(8), Y(29)))
        assert [(item["kind"], item["first_after_date"], item["change_percent"]) for item in found] == expected


# --------------------------------------------- audit round 3, R3-B04: how a series is read (fabricated rows only)
def _returned(days, amount, **kwargs):
    """Debits of the series the bank returned unpaid: attempts (presence, never an amount or a payment)."""
    return _rows(days, amount, returned_funder_payment_by="transaction:99", **kwargs)


def _split(days, amount, paid):
    """`days` at `amount`: the days `paid` keeps are paid, the others returned unpaid."""
    return (_rows([day for day in days if paid(day)], amount)
            + _returned([day for day in days if not paid(day)], amount))


def _fridays(day):
    return day.weekday() == 4


def _wednesdays(day):
    return day.weekday() == 2


def _steps(found):
    return [(item["kind"], item["cadence_before"], item["cadence_after"], item["change_percent"],
             item["payments_before"], item["payments_after"], item["first_after_date"]) for item in found]


# R3-23: a level's and a regime's schedule read the series' attempts at the same amount beside the paid dates, only
# when that gives a regular schedule faster than the paid dates' own; attempts never set an amount or a payment count.
def test_r3_23_a_cut_read_through_bounced_attempts():
    # Daily 850, then daily 600 paid only on Fridays (the other days returned), then daily 300. The base read the 600
    # level weekly from its paid Fridays: "daily -> weekly -86%", then "weekly -> daily +150%".
    rows = (_rows(bdays(M(2), M(13)), 850) + _split(bdays(M(16), A(10)), 600, _fridays)
            + _rows(bdays(A(13), A(24)), 300))
    assert _steps(changes(rows, end=A(30))) == [
        ("decrease", "daily", "daily", -29, 10, 4, "2054-03-20"),
        # The 4 is the paid count: attempts never count as payments.
        ("decrease", "daily", "daily", -50, 4, 10, "2054-04-13")]


def test_r3_23_a_restoration_read_through_bounced_attempts():
    # Daily 850, cut to daily 340, restored to daily 850 that is paid only on Wednesdays. The base read the restoration
    # weekly: no "temporary" mark on the cut, and "daily -> weekly -50%" for the restoration.
    rows = (_rows(bdays(M(2), M(27)), 850) + _rows(bdays(M(30), A(10)), 340)
            + _split(bdays(A(13), Y(8)), 850, _wednesdays))
    decrease, increase = changes(rows, end=Y(8))
    assert (decrease["kind"], decrease["change_percent"], decrease["reverted"], decrease["reverted_date"]) == (
        "decrease", -60, True, "2054-04-15")
    assert _steps([increase]) == [("increase", "daily", "daily", 150, 10, 4, "2054-04-15")]
    assert increase["back_to_earlier"] is True and increase["cadence_changed"] is False


def test_r3_23_a_weekly_cut_whose_new_payments_mostly_bounce():
    # Weekly 1,000, then weekly 700 of which 3 of 8 are paid (every third week): the base read the 700 level as
    # irregular from its paid dates (21-day gaps) and reported nothing.
    cut = every(A(6), Y(25))
    paid = {cut[0], cut[3], cut[6]}
    rows = _rows(every(M(2), A(1)), 1000) + _split(cut, 700, lambda day: day in paid)
    assert _steps(changes(rows, end=Y(29))) == [("decrease", "weekly", "weekly", -30, 5, 3, "2054-04-06")]


def _retried(mondays, amount, retried):
    """Weekly Monday debits; on a `retried` Monday the debit is returned unpaid and re-presented (paid) that
    Wednesday, two days later (a NACHA re-presentment inside one cycle)."""
    rows = []
    for monday in mondays:
        if retried(monday):
            rows += _returned([monday], amount) + _rows([monday + timedelta(days=2)], amount)
        else:
            rows += _rows([monday], amount)
    return rows


def test_r3_23_a_retry_never_makes_a_weekly_schedule_faster():
    mondays = every(M(2), Y(25))
    # (a) every other week re-presented; (b) every week re-presented.
    alternate = _retried(mondays, 1000, lambda monday: mondays.index(monday) % 2 == 1)
    assert changes(alternate, end=Y(29)) == []
    assert changes(_retried(mondays, 1000, lambda monday: True), end=Y(29)) == []


def test_r3_23_a_retry_inside_one_cycle_never_changes_the_compared_schedule():
    # Every Monday re-presented on the Wednesday, then a cut to weekly 700 paid on Mondays: weekly -> weekly -30%.
    rows = _retried(every(M(2), A(20)), 1000, lambda monday: True) + _rows(every(A(27), Y(25)), 700)
    assert _steps(changes(rows, end=Y(29))) == [("decrease", "weekly", "weekly", -30, 8, 5, "2054-04-27")]
    rows = (_retried(every(M(2), A(20)), 1000, lambda monday: monday.day % 2 == 0)
            + _rows(every(A(27), Y(25)), 700))
    assert [item["change_percent"] for item in changes(rows, end=Y(29))] == [-30]


def test_r3_23_a_retry_inside_one_cycle_keeps_the_weekly_stop_window():
    # The Mondays and the Wednesdays together read "daily_irregular" by their median gap (2 days), which is regular
    # and faster than weekly; they keep no daily cycle (2 and 3 business days in turn), so the level stays weekly:
    # 8 quiet business days after the last Wednesday are inside the weekly window (10), no daily stop (6).
    mondays = every(M(2), A(20))
    wednesdays = [monday + timedelta(days=2) for monday in mondays]
    assert lpc.payment_cadence(mondays + wednesdays) == "daily_irregular"
    assert lpc._beat_cadence("weekly", wednesdays, mondays, "US") == "weekly"
    assert changes(_retried(mondays, 1000, lambda monday: True), end=Y(4)) == []
    # A daily level paid only on Fridays, its other days returned, does keep the daily cycle.
    days = bdays(M(16), A(10))
    assert lpc._beat_cadence("weekly", [day for day in days if _fridays(day)],
                             [day for day in days if not _fridays(day)], "US") == "daily"


def test_r3_23_attempts_never_form_a_level_or_set_an_amount():
    # Returned 600s alone between two paid levels: no level, no amount, no payment; L12's bounced tail unchanged.
    rows = _rows(bdays(M(2), M(13)), 850) + _returned(bdays(M(16), M(20)), 600) + _rows(bdays(M(23), A(3)), 850)
    assert [item["kind"] for item in changes(rows, end=A(3))] == []


# R3-24: a level under 5% of the weekly weight of a schedule-confirmed level whose beat its dates keep is a fee level,
# dropped before positions are formed; the per-position test stays after it.
def test_r3_24_a_fee_level_across_two_steps_is_dropped():
    rows = (_rows(bdays(M(2), M(31)), 1500) + _rows(bdays(A(1), Y(15)), 1300) + _rows(bdays(Y(18), J(30)), 1100)
            + _rows([M(2), A(1), Y(1), J(1)], 45))
    found = changes(rows, start=M(1), end=J(30))
    assert _steps(found) == [("decrease", "daily", "daily", -13, 22, 33, "2054-04-01"),
                             ("decrease", "daily", "daily", -15, 33, 30, "2054-05-18")]
    assert {(item["position"], item["positions"]) for item in found} == {(1, 1)}


def test_r3_24_a_fee_level_never_hides_a_new_stream():
    rows = (_rows(every(F(2), Y(25)), 2000) + _rows([F(3), M(3), A(3)], 59) + _rows(every(M(23), Y(25)), 800))
    item = only(rows, start=F(1), end=Y(29))
    assert (item["kind"], item["position"], item["positions"], item["change_percent"]) == ("new_stream", 2, 2, 40)
    assert item["alongside"] == [{"position": 1, "cadence": "weekly", "amount": 2000.0}]
    assert (item["weekly_total_before"], item["weekly_total_after"]) == (2000.0, 2800.0)
    assert (item["first_after_date"], item["payments_after"]) == ("2054-03-23", 10)


def test_r3_24_a_daily_step_beside_a_monthly_fee():
    rows = _rows(bdays(M(2), A(10)), 500) + _rows(bdays(A(13), Y(29)), 400) + _rows([M(2), A(1), Y(1)], 25)
    item = only(rows, start=M(1), end=Y(29))
    assert (item["kind"], item["change_percent"], item["position"], item["positions"]) == ("decrease", -20, 1, 1)


def test_r3_24_a_token_payment_that_replaces_the_payment_is_never_a_fee():
    # Guard 2: a hardship cut to a token payment keeps no date on the main level's beat, so it is kept (never a stop).
    token = _rows(bdays(M(2), M(31)), 1000) + _rows(bdays(A(1), A(30)), 40)
    item = only(token, end=A(30))
    assert (item["kind"], item["change_percent"]) == ("decrease", -96)
    decrease, increase = changes(token + _rows(bdays(Y(1), Y(29)), 1000), end=Y(29))
    assert (decrease["kind"], decrease["change_percent"], decrease["reverted"], decrease["reverted_date"]) == (
        "decrease", -96, True, "2054-05-01")
    assert (increase["kind"], increase["change_percent"], increase["back_to_earlier"]) == ("increase", 2400, True)


def test_r3_24_a_short_daily_level_never_drops_a_monthly_level():
    # Guard 1's corpus shape: a monthly level beside a 2-payment daily level; no item, as on the base.
    assert changes(_rows([M(2), A(1), Y(1), J(1)], 1500) + _rows([A(14), A(15)], 3000), start=M(1), end=J(30)) == []


def _levels_of(*groups):
    """The module's levels of fabricated (days, cents) groups, in US business days."""
    pays = [lpc._Pay(day, cents, 0, number * 1000 + index, f"transaction:{number * 1000 + index}", None)
            for number, (days, cents) in enumerate(groups) for index, day in enumerate(days)]
    levels, _singles = lpc._levels(sorted(pays, key=lambda pay: pay.order), "US")
    return levels


def _kept_amounts(*groups):
    return sorted(level.amount for level in lpc._fee_levels(_levels_of(*groups)))


def test_r3_24_the_fee_test_reads_each_level():
    # Two dates on a confirmed daily level's days: a fee level, dropped.
    assert _kept_amounts((bdays(M(2), M(31)), 150000), ([M(2), M(16)], 4500)) == [150000]
    # A level that keeps no date on a reference's beat is kept, whatever its size (guard 2).
    assert _kept_amounts((bdays(M(2), M(13)), 150000), ([M(23), A(23)], 4500)) == [4500, 150000]
    # One date on the beat is not enough; 2 of 4 is under BEAT_KEPT_PERCENT.
    assert _kept_amounts((bdays(M(2), M(13)), 150000), ([M(2), A(1)], 4500)) == [4500, 150000]
    assert _kept_amounts((bdays(M(2), M(13)), 150000), ([M(2), M(9), A(20), Y(20)], 4500)) == [4500, 150000]
    # Guard 1: a reference confirms its schedule, 5 payments if daily, 3 otherwise.
    assert _kept_amounts(([A(14), A(15)], 300000), ([A(14), A(15)], 5000)) == [5000, 300000]
    assert _kept_amounts((bdays(A(13), A(17)), 300000), ([A(14), A(15)], 5000)) == [300000]
    assert _kept_amounts(([M(2), M(9)], 300000), ([M(2), M(9)], 1000)) == [1000, 300000]
    assert _kept_amounts(([M(2), M(9), M(16)], 300000), ([M(2), M(9)], 1000)) == [300000]
    # 5% of the weekly weight is not under it (L10b's 6% stream stays a stream).
    assert _kept_amounts((every(M(2), A(27)), 100000), (every(M(4), A(29)), 5000)) == [5000, 100000]
    assert _kept_amounts((every(M(2), A(27)), 100000), (every(M(4), A(29)), 4999)) == [100000]
    # An irregular level is compared on raw amounts with the reference.
    assert _kept_amounts((bdays(M(2), M(31)), 100000), ([M(2), M(3), M(24)], 4999)) == [100000]
    assert _kept_amounts((bdays(M(2), M(31)), 100000), ([M(2), M(3), M(24)], 5000)) == [5000, 100000]


# R3-70: a 2x or 3x level stays a catch-up unless one of its 2-payment runs reads a SLOWER regular schedule than the
# main level's; then it is § Still open 18's possible change.
@pytest.mark.parametrize("rows,end,expected", [
    (_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30)], 1500), M(31),
     ("decrease", "daily", "weekly", -40, 15, 2, "2054-03-23")),
    (_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30)], 1000), M(31),
     ("decrease", "daily", "weekly", -60, 15, 2, "2054-03-23")),
    (_rows(every(M(2), A(20)), 1000) + _rows([A(27), Y(11)], 3000), Y(15),
     ("increase", "weekly", "biweekly", 50, 8, 2, "2054-04-27")),
    (_rows(every(M(2), A(20)), 1000) + _rows([A(27), Y(27)], 3000), Y(29),
     ("decrease", "weekly", "monthly", -31, 8, 2, "2054-04-27")),
])
def test_r3_70_a_new_schedule_at_two_or_three_times_held_two_is_a_possible_change(rows, end, expected):
    item = only(rows, end=end)
    assert _steps([item]) == [expected]
    assert (item["schedule_confirmed"], item["cadence_changed"]) == (False, True)


def test_r3_70_controls():
    # L6: a 2x double between daily payments; a 2x held 2 on the same schedule (§ Still open 22's disclosed case).
    assert changes(_rows(bdays(M(2), M(6)), 500) + _rows([M(11), M(12)], 1000) + _rows(bdays(M(13), M(31)), 500)) == []
    assert changes(_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(24)], 1000)) == []
    # A 3x run of 3 is no catch-up already: the confirmed -40%.
    item = only(_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(30), A(6)], 1500), end=A(10))
    assert (item["kind"], item["change_percent"], item["schedule_confirmed"]) == ("decrease", -40, True)


# ------------------- audit round 3, R3-B04, review round 1: re-presentments never make a schedule faster (fabricated)
def _presented(fridays, amount, twice):
    """Weekly Friday debits at `amount`; on a week `twice` keeps (by its index), the debit is first presented on the
    Monday and re-presented on the Wednesday, both returned unpaid, then paid on the Friday (NACHA's two
    re-presentments)."""
    rows = []
    for index, friday in enumerate(fridays):
        if twice(index):
            rows += _returned([friday - timedelta(days=4), friday - timedelta(days=2)], amount)
        rows += _rows([friday], amount)
    return rows


def _retried_on(mondays, amount, gap):
    """Each Monday's debit returned unpaid and re-presented, paid, `gap` days later."""
    rows = []
    for monday in mondays:
        rows += _returned([monday], amount) + _rows([monday + timedelta(days=gap)], amount)
    return rows


def test_r3_b04_r1_twice_re_presented_weekly_debits_never_read_daily():
    # Weekly 1,000 cut to weekly 700 over 11 Fridays. Mondays, Wednesdays and Fridays together read "daily irregular"
    # by their median gap, but one debit's three presentments never fill 4 of 5 consecutive business days, so the
    # level stays weekly whichever weeks are re-presented twice: every week, every other week, or only the last 4 of
    # 11 (the review round read "+250% weekly -> daily", a confirmed increase, in place of the -30%).
    clean = _rows(every(M(6), A(10)), 1000)
    cut = every(A(17), J(26))
    for twice in (lambda index: True, lambda index: index % 2 == 0, lambda index: index >= 7):
        found = changes(clean + _presented(cut, 700, twice), end=J(30))
        assert _steps(found) == [("decrease", "weekly", "weekly", -30, 6, 11, "2054-04-17")]
    # One level re-presented twice every week, 8 quiet business days after its last Friday: inside the weekly window
    # (10), no daily-irregular stop (6).
    assert changes(_presented(every(M(6), A(24)), 1000, lambda index: True), end=A(24) + timedelta(days=12)) == []


def test_r3_b04_r1_a_retry_on_a_short_level_never_reads_daily():
    # A Monday debit re-presented on the Wednesday (or the Tuesday) for 2 or 3 weeks, then 7 or 8 quiet business days:
    # no daily or daily-irregular stop, alone or beside the -30% cut (the review round read a possible stop).
    for weeks, gap in ((2, 2), (3, 2), (3, 1)):
        mondays = every(A(13), A(13) + timedelta(days=7 * (weeks - 1)))
        end = mondays[-1] + timedelta(days=gap + 10)
        assert changes(_retried_on(mondays, 1000, gap), start=A(1), end=end) == []
        found = changes(_rows(every(M(2), A(6)), 1000) + _retried_on(mondays, 700, gap), end=end)
        first = (A(13) + timedelta(days=gap)).isoformat()
        assert _steps(found) == [("decrease", "weekly", "weekly", -30, 6, weeks, first)]


def test_r3_b04_r1_a_daily_schedule_read_through_attempts_fills_four_of_five_business_days():
    days = bdays(M(16), A(10))
    fridays = [day for day in days if _fridays(day)]
    # Fridays paid, every other day returned: daily.
    assert lpc._beat_cadence("weekly", fridays, [day for day in days if not _fridays(day)], "US") == "daily"
    # Mondays and Wednesdays returned, Fridays paid: 3 of 5 business days, one debit's presentments: weekly.
    returned = [friday - timedelta(days=offset) for friday in fridays for offset in (4, 2)]
    assert lpc.payment_cadence(fridays + returned) == "daily_irregular"
    assert lpc._beat_cadence("weekly", fridays, returned, "US") == "weekly"
    # A Monday returned and paid on the Tuesday, 3 weeks: weekly.
    mondays = every(A(13), A(27))
    assert lpc._beat_cadence("weekly", [monday + timedelta(days=1) for monday in mondays], mondays, "US") == "weekly"
    # A daily level another amount interrupts for two weeks still reads daily: paid on a Wednesday, returned Thursday
    # to Tuesday, paid again on a Wednesday and a Thursday three weeks later.
    paid = [M(4), M(25), M(26)]
    assert lpc.payment_cadence(paid) == "irregular"
    assert lpc._beat_cadence("irregular", paid, [M(5), M(6), M(9), M(10)], "US") == "daily"


def test_r3_b04_r1_a_weekly_debit_whose_every_other_presentment_bounces_stays_weekly():
    # R3-23's corpus shape: weekly 1,000 cut to weekly 700, every other 700 returned unpaid, reads -30% weekly ->
    # weekly (the paid dates alone read biweekly). A biweekly debit re-presented one week later presents the same
    # dates, so it reads weekly too: a disclosed shape (spec §17.1 (20)), never told apart on dates.
    cut = every(A(13), Y(25))
    rows = _rows(every(M(2), A(6)), 1000) + _split(cut, 700, lambda day: cut.index(day) % 2 == 0)
    assert _steps(changes(rows, end=Y(29))) == [("decrease", "weekly", "weekly", -30, 6, 4, "2054-04-13")]


def test_r3_b04_r1_a_second_stream_beside_a_daily_level_read_through_its_attempts():
    # A daily 1,000 paid only on Fridays (its other days returned) reads daily (R3-23); a weekly debit on Wednesdays
    # from April is a second advance. The concurrency test reads the daily level's attempts beside its payments, as its
    # schedule does, so the Wednesdays keep its beat and the weekly debit is a new stream (the review round lost it in
    # one position).
    main = _split(bdays(M(2), Y(29)), 1000, _fridays)
    for amount, percent in ((500, 10), (3000, 60)):
        item = only(main + _rows(every(A(1), Y(27)), amount), end=Y(29))
        assert (item["kind"], item["position"], item["positions"], item["change_percent"]) == (
            "new_stream", 2, 2, percent)
        assert item["alongside"] == [{"position": 1, "cadence": "daily", "amount": 1000.0}]
        assert (item["first_after_date"], item["payments_after"]) == ("2054-04-01", 9)


def test_r3_b04_r1_the_fee_test_reads_a_reference_through_its_attempts():
    # A monthly 45 on Tuesdays beside that daily 1,000: its Tuesdays are the daily level's returned days, so it is a
    # fee level, dropped.
    days = bdays(M(2), Y(29))
    pays = sorted([lpc._Pay(day, 100000, 0, index, f"transaction:{index}", None)
                   for index, day in enumerate(day for day in days if _fridays(day))]
                  + [lpc._Pay(day, 4500, 0, 500 + index, f"transaction:{500 + index}", None)
                     for index, day in enumerate([M(3), A(7), Y(5)])], key=lambda pay: pay.order)
    attempts = [lpc._Pay(day, 100000, 0, 900 + index, f"transaction:{900 + index}", None)
                for index, day in enumerate(day for day in days if not _fridays(day))]
    levels, _singles = lpc._levels(pays, "US", attempts)
    assert sorted((level.amount, level.cadence) for level in levels) == [(4500, "monthly"), (100000, "daily")]
    assert [level.amount for level in lpc._fee_levels(levels)] == [100000]


def test_r3_b04_r1_a_double_on_the_paying_weekday_of_a_level_read_through_its_attempts_is_a_catch_up():
    # Daily 500 paid only on Fridays (its other days returned); on two Fridays the funder takes 1,000 in its place.
    # The 2x run keeps the paid Fridays' own weekly beat: no slower schedule, a catch-up, no item (the review round
    # read "possible decrease daily -> weekly -60%").
    days = bdays(M(2), Y(29))
    fridays = [day for day in days if _fridays(day)]
    double = fridays[5:7]
    rows = (_rows([day for day in fridays if day not in double], 500) + _rows(double, 1000)
            + _returned([day for day in days if not _fridays(day)], 500))
    assert changes(rows, end=Y(29)) == []


# --------------- audit round 3, R3-B04, review round 2: two debits' re-presentments never add up to daily (fabricated)
def N(day):  # noqa: N802
    return date(2054, 11, day)


def D(day):  # noqa: N802
    return date(2054, 12, day)


def S(day):  # noqa: N802
    return date(2054, 9, day)


def _chains(mondays, amount, patterns):
    """Weekly Monday debits at `amount`; the week of index i follows patterns[i % len(patterns)] = (the offsets, in
    days from its Monday, of the presentments the bank returned unpaid, the offset of the paid one): NACHA's original
    entry and at most two re-presentments, each chain ending before the next Monday."""
    rows = []
    for index, monday in enumerate(mondays):
        bounced, paid = patterns[index % len(patterns)]
        rows += _returned([monday + timedelta(days=offset) for offset in bounced], amount)
        rows += _rows([monday + timedelta(days=paid)], amount)
    return rows


# C: the Monday returned, the Friday paid. D: the Monday and the Tuesday returned, the Thursday paid.
_C, _D = ((0,), 4), ((0, 1), 3)


@pytest.mark.parametrize("weeks", [2, 6, 10])
def test_r3_b04_r2_alternating_re_presentment_chains_stay_weekly(weeks):
    # Weekly 1,000 cut to weekly 700 whose chains alternate C and D. Every chain is NACHA's (3 presentments at most,
    # over before the next Monday), but the Thursday and Friday of one week and the Monday and Tuesday of the next fill
    # 4 of 5 business days, so the stretch test alone read "+250% weekly -> daily" (confirmed at 6 and 10 weeks).
    # Between two paid dates lie at most 2 returned presentments, one debit's: no daily reading, the base's -30% weekly.
    mondays = every(M(16), M(16) + timedelta(days=7 * (weeks - 1)))
    rows = _rows(every(F(3), M(10)), 1000) + _chains(mondays, 700, (_C, _D))
    found = changes(rows, start=F(1), end=mondays[-1] + timedelta(days=7))
    assert _steps(found) == [("decrease", "weekly", "weekly", -30, 6, weeks, "2054-03-20")]
    days = sorted({date.fromisoformat(row.date) for row in _chains(mondays, 700, (_C, _D))})
    paid = sorted({date.fromisoformat(row.date) for row in _chains(mondays, 700, (_C, _D))
                   if not row.returned_funder_payment_by})
    assert lpc._beat_cadence(lpc.payment_cadence(paid), paid, sorted(set(days) - set(paid)), "US") == (
        lpc.payment_cadence(paid))


def test_r3_b04_r2_a_holiday_week_never_makes_two_re_presented_weeks_daily():
    # Thanksgiving (Thursday 2054-11-26) puts the Monday, Wednesday and Friday of its week and the next Monday in 5
    # business days. A 2-week level re-presented twice each week (the Monday and the Wednesday returned, the Friday
    # paid) read "daily irregular": a false possible stop (8 or 10 quiet business days, grace 6) beside the correct
    # -30%. The base read the -30% alone; so does this round.
    rows = _rows(every(S(4), N(20)), 1000) + _presented([N(27), D(4)], 700, lambda index: True)
    for end in (D(16), D(18)):
        assert _steps(changes(rows, start=S(1), end=end)) == [
            ("decrease", "weekly", "weekly", -30, 12, 2, "2054-11-27")]
    # Veterans Day (Wednesday 2054-11-11): the Monday returned, the Thursday returned, the Friday paid, then the Monday
    # and Wednesday returned and the Friday paid.
    veterans = (_returned([N(9), N(12)], 700) + _rows([N(13)], 700) + _returned([N(16), N(18)], 700)
                + _rows([N(20)], 700))
    assert _steps(changes(_rows(every(S(4), N(6)), 1000) + veterans, start=S(1), end=D(4))) == [
        ("decrease", "weekly", "weekly", -30, 10, 2, "2054-11-13")]


def _twice_weekly(mondays, amount):
    """A twice-weekly debit: each Monday's and each Thursday's returned unpaid and re-presented, paid, the next business
    day."""
    rows = []
    for monday in mondays:
        rows += _returned([monday, monday + timedelta(days=3)], amount)
        rows += _rows([monday + timedelta(days=1), monday + timedelta(days=4)], amount)
    return rows


def test_r3_b04_r2_a_twice_weekly_debit_re_presented_the_next_day_never_reads_daily():
    # Mondays and Thursdays returned, Tuesdays and Fridays paid: 4 of 5 business days presented, but each paid date
    # follows one returned presentment. The stretch test alone read it daily: a move to weekly 2,000 (the same weekly
    # total) read a confirmed "-60% daily -> weekly", and a quiet stretch a false daily stop. The base read the
    # twice-weekly paid dates as irregular, no schedule, and gave no item; so does this round.
    mondays = every(M(2), A(6))
    assert changes(_twice_weekly(mondays, 1000) + _rows(every(A(17), Y(29)), 2000), end=Y(29)) == []
    assert changes(_twice_weekly(mondays, 1000), end=A(20)) == []


def test_r3_b04_r2_a_daily_reading_through_attempts_needs_more_than_one_debits_re_presentments_between_payments():
    days = bdays(M(16), A(10))
    fridays = [day for day in days if _fridays(day)]
    # Fridays paid, every other day returned: 4 attempts between two paid Fridays, daily.
    assert lpc._beat_cadence("weekly", fridays, [day for day in days if not _fridays(day)], "US") == "daily"
    # A daily level another amount interrupts (paid on a Wednesday, returned Thursday to Tuesday, paid again three
    # weeks later on a Wednesday and a Thursday): the one paid interval with room for 3 attempts holds 4: daily.
    assert lpc._beat_cadence("irregular", [M(4), M(25), M(26)], [M(5), M(6), M(9), M(10)], "US") == "daily"
    # The same dates with only two attempts between the payments: one debit's re-presentments, no daily reading.
    assert lpc._beat_cadence("irregular", [M(4), M(10), M(11)], [M(5), M(6)], "US") == "irregular"
    # A daily level paid every few days, each business day between returned: the one interval with room for 3
    # attempts (Thursday to Wednesday) holds 3; the shorter ones (2 business days inside) tell nothing and are not
    # counted: daily.
    paid = [M(4), M(5), M(11), M(16), M(19)]
    assert lpc.payment_cadence(paid) == "irregular"
    assert lpc._beat_cadence("irregular", paid, [M(6), M(9), M(10), M(12), M(13), M(17), M(18)], "US") == "daily"
    # Alternating C and D chains fill 4 of 5 business days across each week's end, yet hold 1 or 2 attempts between
    # two paid dates: weekly.
    paid = [M(20), M(26), A(3), A(9)]
    tried = [M(16), M(23), M(24), M(30), A(6), A(7)]
    assert lpc._fills_daily_stretches(sorted(paid + tried), "US")
    assert lpc._beat_cadence("weekly", paid, tried, "US") == "weekly"
    # A Friday paid, then the next Monday and Tuesday returned and the Wednesday paid: the only interval has 2 business
    # days inside, no room for more than one debit's re-presentments: no daily reading.
    assert lpc._beat_cadence("weekly", [M(6), M(11)], [M(2), M(9), M(10)], "US") == "weekly"
    # Two payments on one day and three returned presentments after them: no interval at all, no daily reading.
    assert lpc._beat_cadence("single", [M(6), M(6)], [M(9), M(10), M(11)], "US") == "single"


def _next_business_day(day):
    return bdays(day, day + timedelta(days=6))[0]


def _chain_layouts(entries):
    """Every NACHA chain layout of a weekly debit entered on `entries[:-1]`: each week's debit paid on its entry, or
    returned and re-presented once or twice on later business days before the next entry, the last presentment
    paid."""
    weeks = []
    for entry, limit in zip(entries, entries[1:]):
        later = bdays(entry + timedelta(days=1), limit - timedelta(days=1))
        week = [((), entry)]
        for index, paid in enumerate(later):
            week.append(((entry,), paid))
            week += [((entry, middle), paid) for middle in later[:index]]
        weeks.append(week)
    return itertools.product(*weeks)


@pytest.mark.parametrize("first", [M(2), M(3), M(4), M(5), M(6), N(4), N(16), N(18), N(20)])
def test_r3_b04_r2_no_layout_of_weekly_chains_that_end_paid_reads_daily(first):
    # Every entry weekday, and the weeks of Veterans Day and Thanksgiving: whichever days each week's chain uses, its
    # attempts never make the level daily (the review round's stretch test alone read 22 of the 121 two-week layouts
    # of each weekday daily).
    for weeks in (2, 3):
        entries = [_next_business_day(first + timedelta(days=7 * week)) for week in range(weeks + 1)]
        for layout in _chain_layouts(entries):
            returned = [day for chain in layout for day in chain[0]]
            paid = [chain[1] for chain in layout]
            own = lpc.payment_cadence(paid)
            read = lpc._beat_cadence(own, paid, returned, "US")
            assert read == own or lpc._regular(read) != "daily", (paid, returned)


def test_r3_b04_r2_one_missed_week_never_makes_a_weekly_level_daily():
    # Weekly 1,000 cut to weekly 700 over 10 weeks whose chains alternate C and D, one week returned all three times
    # (the Monday, the Thursday and the Friday): 1 of the 8 intervals between its 9 paid dates holds 3 attempts or
    # more, under 60%: still weekly.
    mondays = every(M(16), Y(18))
    rows = [row for row in _chains(mondays, 700, (_C, _D)) if date.fromisoformat(row.date) not in (A(13), A(17))]
    rows += _returned([A(13), A(16), A(17)], 700)
    found = changes(_rows(every(F(3), M(10)), 1000) + rows, start=F(1), end=Y(25))
    assert _steps(found) == [("decrease", "weekly", "weekly", -30, 6, 9, "2054-03-20")]


# R3-70's slower-run test reads the main level's paid schedule only while that level is still presented, paid or
# returned, on every beat of its schedule strictly inside the 2x or 3x run (each business day for a daily one; within
# the schedule's beat tolerance otherwise; audit round 4, R4-10: one presentment anywhere inside the span read as
# "still presented"), as P4's catch-up is; a main level that is no longer presented there is read on its attempt-read
# schedule.
@pytest.mark.parametrize("rows,end,expected", [
    # Weekly 1,000 with every other debit returned (its paid dates read biweekly), then biweekly 3,000 held 2.
    (_split(every(M(2), A(20)), 1000, lambda day: (day - M(2)).days % 14 == 0) + _rows([Y(4), Y(18)], 3000), Y(22),
     ("increase", "weekly", "biweekly", 50, 4, 2, "2054-05-04")),
    # Daily 500 paid only on Fridays, then weekly 1,000 held 2 and no more 500.
    (_split(bdays(M(2), A(17)), 500, _fridays) + _rows([A(24), Y(1)], 1000), Y(5),
     ("decrease", "daily", "weekly", -60, 7, 2, "2054-04-24")),
    # Daily 500 paid on scattered days (the others returned), then weekly 1,500 held 2.
    (_split(bdays(M(2), A(17)), 500, lambda day: day in {M(4), M(12), M(17), M(25), A(2), A(8), A(16)})
     + _rows([A(24), Y(1)], 1500), Y(5),
     ("decrease", "daily", "weekly", -40, 7, 2, "2054-04-24")),
    # Daily 500 paid on days whose gaps read irregular (10 and 11 days; the others returned), then weekly 1,500 held 2.
    (_split(bdays(M(2), A(17)), 500, lambda day: day in {M(2), M(12), M(23), A(2), A(13)})
     + _rows([A(24), Y(1)], 1500), Y(5),
     ("decrease", "daily", "weekly", -40, 5, 2, "2054-04-24")),
])
def test_r3_b04_r2_a_slower_run_after_a_main_level_read_through_its_attempts_is_a_possible_change(rows, end,
                                                                                                    expected):
    # The review round compared these runs with the main level's paid schedule (biweekly, weekly or none) and read a
    # catch-up: no item, where the clean twin of each reads the possible change.
    item = only(rows, end=end)
    assert _steps([item]) == [expected]
    assert (item["schedule_confirmed"], item["cadence_changed"]) == (False, True)


# Audit round 4, R4-B05 (R4-10): "still presented through the run" is presented, paid or returned, on every beat of the
# main level's schedule strictly inside the 2x or 3x run, as the docs say; one presentment anywhere inside its span (a
# single returned attempt, maybe one re-presentment of an earlier return) is not.
def test_r4_10_one_stray_attempt_inside_the_run_never_silences_the_possible_change():
    # Daily 500 that clears only on Fridays, then 1,000 on two Fridays: a possible -60% daily -> weekly.
    thin = _split(bdays(M(2), A(17)), 500, _fridays)
    double = _rows([A(24), Y(1)], 1000)
    expected = [("decrease", "daily", "weekly", -60, 7, 2, "2054-04-24")]
    assert _steps(changes(thin + double, end=Y(5))) == expected
    # One returned 500 on the Wednesday inside the run: the same possible change (the base read "still presented"
    # and a catch-up: no item).
    assert _steps(changes(thin + double + _returned([A(29)], 500), end=Y(5))) == expected
    # The 500 presented on every business day inside the run: the funder still presents the old payment, so the run
    # is a catch-up, no item (as on the base).
    assert changes(thin + double + _returned(bdays(A(27), A(30)), 500), end=Y(5)) == []


def test_r4_10_a_weekly_stray_on_or_near_the_interior_beat_stays_a_catch_up():
    # Weekly 1,000 whose every other debit bounced, then 3,000 on 05-04 and 05-18: a possible +50% weekly -> biweekly
    # (its clean twin's reading). A returned 1,000 on the run's only interior weekly beat (05-11), or within the weekly
    # beat tolerance of 3 days of it (05-08, 05-13), presents the main level on every interior beat: a catch-up, no
    # item, on the base and now.
    w = _split(every(M(2), A(20)), 1000, lambda day: (day - M(2)).days % 14 == 0)
    tri = _rows([Y(4), Y(18)], 3000)
    assert _steps(changes(w + tri, end=Y(22))) == [("increase", "weekly", "biweekly", 50, 4, 2, "2054-05-04")]
    for stray in (Y(11), Y(13), Y(8)):
        assert changes(w + tri + _returned([stray], 1000), end=Y(22)) == [], stray


# ------------------------------- audit round 3, R3-B05 (R3-25, R3-84; the owner's answer of 2026-10-07; fabricated)
def _other(days, amount, classification="other"):
    """Posted debits of `amount` that no lender rule claimed (another description; class `other` by default)."""
    return [TransactionClassification(original_description="FABRICATED DEBIT",
                                      normalized_description="FABRICATED DEBIT", classification=classification,
                                      date=day.isoformat(), amount=-float(amount), direction="debit") for day in days]


def _kinds(found):
    return [item["kind"] for item in found]


def _catch_up_fields(item):
    return (item["kind"], item["cadence"], item["last_payment_amount"], item["last_before_date"],
            item["missed_payments"], item["missed_first_date"], item["missed_last_date"], item["multiple"],
            item["catch_up_date"], item["catch_up_amount"])


# R3-25: an exact 2x-6x one-off is a catch-up: presence for pauses, restarts and stops, never a payoff. The owner's
# answer of 2026-10-07 ("Add a 'Caught up' line"): where it follows one or more missed scheduled payments, one
# `catch_up` item, unless a pause or a stop line that still shows names it.
def test_r3_25_a_catch_up_after_one_missed_week_is_presence():
    # Before: a possible stop, quiet 18, its "payoff" the 2x. The 2x ends 8 business days before the end, inside the
    # weekly grace of 10: no stop; the missed week before it gives the one Caught up item.
    [item] = changes(_rows(every(M(3), A(14)), 1000) + _rows([A(28)], 2000), start=M(1), end=Y(8))
    assert _catch_up_fields(item) == ("catch_up", "weekly", 1000.0, "2054-04-14", 1, "2054-04-21", "2054-04-21", 2,
                                      "2054-04-28", 2000.0)
    assert (item["lender"], item["lender_state"], item["position"], item["positions"], item["scope"]) == (
        "KAPITUS", "confirmed", 1, 1, "statement")
    assert item["locations"] == {"last_before": "transaction:7", "catch_up": "transaction:8"}
    assert not any(key.startswith("_") for key in item)


def test_r3_25_a_missed_week_caught_up_is_no_pause():
    # Before: a pause 2054-04-14 -> 2054-05-05 (15 business days); the 2x two weeks after the last payment ends the
    # gap at 10 business days, within the grace.
    found = changes(_rows(every(M(3), A(14)) + every(Y(5), Y(26)), 1000) + _rows([A(28)], 2000), start=M(1), end=Y(29))
    assert _kinds(found) == ["catch_up"]
    assert _catch_up_fields(found[0])[4:] == (1, "2054-04-21", "2054-04-21", 2, "2054-04-28", 2000.0)


def test_r3_25_a_pause_ended_by_a_catch_up_names_it():
    # Before: a pause 03-06 -> 03-23, 11 business days, ended by the regime's payment. The 6x is presence: the pause
    # ends at it, names it, and is the one line for the gap (no separate Caught up item).
    item = only(_rows(bdays(M(2), M(6)) + bdays(M(23), M(31)), 300) + _rows([M(16)], 1800))
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"],
            item["first_after_kind"], item["first_after_amount"], item["first_after_multiple"],
            item["resumed_date"]) == ("pause", "2054-03-06", "2054-03-16", 6, "catch_up", 1800.0, 6, "2054-03-23")
    assert "larger_debits_inside" not in item and "same_amount_debits" not in item
    assert item["locations"] == {"last_before": "transaction:5", "first_after": "transaction:6"}


def test_r3_25_a_larger_debit_that_is_no_multiple_is_named_inside_the_pause():
    # 1,300 is 4.33x the payment, no exact multiple: no presence, no catch-up, named inside the gap.
    item = only(_rows(bdays(M(2), M(6)) + bdays(M(23), M(31)), 300) + _rows([M(16)], 1300))
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"],
            item["first_after_kind"], item["resumed_date"]) == (
        "pause", "2054-03-06", "2054-03-23", 11, "payment", "2054-03-23")
    assert item["larger_debits_inside"] == [{"date": "2054-03-16", "amount": 1300.0}]
    assert "first_after_amount" not in item and "first_after_multiple" not in item


def test_r3_25_a_stop_after_catch_ups_names_them_and_no_payoff():
    # Before: a possible stop, quiet 98, its payoff the 3x. Monthly 2x and 3x, each on or before the next due date (no
    # missed payment): presence, no Caught up line; the stop runs from the 3x and counts both as catch-ups.
    item = only(_rows([F(13), M(13), A(13)], 1000) + _rows([Y(13)], 2000) + _rows([J(12)], 3000), start=F(1),
                end=date(2054, 8, 31))
    assert (item["kind"], item["stop_confirmed"], item["last_presence_date"], item["quiet_business_days"]) == (
        "stop", False, "2054-06-12", 55)
    assert item["other_debits_after"] == {"count": 2, "last_date": "2054-06-12", "catch_ups": 2}
    assert "payoff" not in item


def test_r3_25_the_payoff_counts_earlier_large_debits():
    # 4,500 (2.25x) and 5,000 (2.5x): no exact multiple, so neither is presence; the payoff is the last and counts
    # the one before it.
    item = only(_rows([F(2), M(2), A(2)], 2000) + _rows([A(10)], 4500) + _rows([A(20)], 5000), start=F(1), end=J(30))
    assert (item["kind"], item["last_presence_date"], item["quiet_business_days"]) == ("stop", "2054-04-02", 61)
    assert item["payoff"] == {"date": "2054-04-20", "amount": 5000.0, "earlier": 1}
    assert "other_debits_after" not in item


def test_r3_25_a_stop_names_a_catch_up_after_its_last_payment_and_adds_no_line():
    # The catch-up after the last payment is the stop's last presence; the stop line names it (one line per gap).
    item = only(_rows(bdays(M(2), M(13)), 850) + _rows([M(17)], 1700))
    assert (item["kind"], item["last_payment_date"], item["last_presence_date"], item["quiet_business_days"]) == (
        "stop", "2054-03-13", "2054-03-17", 10)
    assert item["other_debits_after"] == {"count": 1, "last_date": "2054-03-17", "catch_ups": 1}
    assert "payoff" not in item


def test_r3_25_the_l31_shape_at_exactly_twice_is_a_catch_up():
    # L31's payoff-sized debit at exactly 2x, after 3 missed business days: no stop, one Caught up item.
    [item] = changes(_rows(bdays(M(2), M(20)), 850) + _rows([M(26)], 1700))
    assert _catch_up_fields(item) == ("catch_up", "daily", 850.0, "2054-03-20", 3, "2054-03-23", "2054-03-25", 2,
                                      "2054-03-26", 1700.0)


@pytest.mark.parametrize("amount,multiple", [(1700, 2), (1667, 2), (1734, 2), (2550, 3), (3400, 4), (4250, 5),
                                             (5100, 6), (5202, 6), (1666, None), (1735, None), (5950, None),
                                             (1275, None), (6800, None)])
def test_r3_25_the_catch_up_multiple_is_within_two_percent_of_2_to_6_times(amount, multiple):
    pay = lpc._Pay(M(16), amount * 100, 0, 0, "transaction:1", None)
    assert lpc._catch_up_multiple(pay, 85000) == multiple


def test_r3_25_controls():
    # L20: a 2.5x final debit is the payoff; L6 and § Still open 22: a 2x level held 2 is a catch-up level, no item;
    # L31: payment-sized debits are presence; L12: bounced attempts are presence.
    item = only(_rows([F(2), M(2), A(2)], 2000) + _rows([A(20)], 5000), start=F(1), end=J(30))
    assert (item["kind"], item["quiet_business_days"], item["payoff"]) == (
        "stop", 61, {"date": "2054-04-20", "amount": 5000.0})
    assert changes(_rows(bdays(M(2), M(6)), 500) + _rows([M(11), M(12)], 1000) + _rows(bdays(M(13), M(31)), 500)) == []
    assert changes(_rows(bdays(M(2), M(20)), 500) + _rows([M(23), M(24)], 1000)) == []
    rows = _rows(bdays(M(2), M(20)), 850) + _rows([M(23)], 400) + _rows([M(25)], 300) + _rows([M(26)], 500)
    assert changes(rows) == []
    paid = _rows(every(M(4), A(8)), 1000)
    attempts = _rows(every(A(15), A(29)), 1000, returned_funder_payment_by="transaction:99")
    assert changes(paid + attempts, end=A(30)) == []


# The owner's answer of 2026-10-07: the Caught up line (fabricated, as the owner's own example's shape).
def test_r3_25_owner_a_daily_double_after_one_missed_day_is_caught_up():
    [item] = changes(_rows(bdays(M(2), M(13)) + bdays(M(18), M(31)), 850) + _rows([M(17)], 1700))
    assert _catch_up_fields(item) == ("catch_up", "daily", 850.0, "2054-03-13", 1, "2054-03-16", "2054-03-16", 2,
                                      "2054-03-17", 1700.0)
    # Two missed days.
    [item] = changes(_rows(bdays(M(2), M(13)) + bdays(M(19), M(31)), 850) + _rows([M(18)], 1700))
    assert _catch_up_fields(item)[4:] == (2, "2054-03-16", "2054-03-17", 2, "2054-03-18", 1700.0)


def test_r3_25_owner_a_bounced_payment_is_a_missed_payment():
    rows = (_rows(bdays(M(2), M(13)) + bdays(M(18), M(31)), 850) + _rows([M(17)], 1700)
            + _rows([M(16)], 850, returned_funder_payment_by="transaction:99"))
    [item] = changes(rows)
    assert _catch_up_fields(item)[3:] == ("2054-03-13", 1, "2054-03-16", "2054-03-16", 2, "2054-03-17", 1700.0)


def test_r3_25_owner_a_weekly_triple_after_two_missed_weeks_is_named_by_its_pause():
    # Two missed weeks put the triple 15 business days after the last payment, past the weekly grace: the pause line
    # still shows and carries the catch-up; no separate Caught up item (one line per event).
    found = changes(_rows(every(M(3), M(17)) + every(A(14), Y(26)), 1000) + _rows([A(7)], 3000), start=M(1), end=Y(29))
    assert _kinds(found) == ["pause"]
    item = found[0]
    assert (item["last_before_date"], item["first_after_date"], item["pause_business_days"], item["first_after_kind"],
            item["first_after_amount"], item["first_after_multiple"], item["resumed_date"]) == (
        "2054-03-17", "2054-04-07", 15, "catch_up", 3000.0, 3, "2054-04-14")


def test_r3_25_owner_a_weekly_triple_inside_the_grace_is_caught_up():
    # A triple 10 days after the last weekly payment (one missed due date): within the grace, one Caught up item.
    [item] = changes(_rows(every(M(3), M(17)) + every(M(31), Y(26)), 1000) + _rows([M(27)], 3000), start=M(1),
                     end=Y(29))
    assert _catch_up_fields(item) == ("catch_up", "weekly", 1000.0, "2054-03-17", 1, "2054-03-24", "2054-03-24", 3,
                                      "2054-03-27", 3000.0)


def test_r3_25_owner_a_multiple_with_no_missed_payment_gets_no_line():
    # A 2x on the next business day after a payment (daily), and a 2x on its weekly due date: nothing was missed.
    daily = [day for day in bdays(M(2), M(31)) if day != M(16)]
    assert changes(_rows(daily, 850) + _rows([M(16)], 1700)) == []
    weekly = [day for day in every(M(3), A(28)) if day != A(7)]
    assert changes(_rows(weekly, 1000) + _rows([A(7)], 2000), end=A(30)) == []
    # A weekly 2x one business day after its due date is on time (CATCH_UP_LATE_BUSINESS_DAYS).
    assert changes(_rows(weekly, 1000) + _rows([A(8)], 2000), end=A(30)) == []


def test_r3_25_owner_a_potential_lender_s_catch_up():
    label = f"{UNNAMED} (daily, 300.00)"
    rows = (_potential(bdays(M(2), M(13)) + bdays(M(18), M(31)), 300, label=label)
            + _potential([M(17)], 600, label=label))
    [item] = changes(rows)
    assert (item["kind"], item["lender_state"], item["lender_label"], item["multiple"], item["missed_payments"]) == (
        "catch_up", "potential", label, 2, 1)


def test_r3_25_owner_a_package_catch_up_names_its_statement():
    march = _rows(bdays(M(2), M(27)), 850)
    april = _rows([A(2)], 1700) + _rows(bdays(A(3), A(30)), 850)
    [item] = _chain((march, M(1), M(31)), (april, A(1), A(30)))
    assert (item["kind"], item["scope"], item["missed_payments"], item["missed_first_date"], item["catch_up_date"],
            item["_source_statement"]) == ("catch_up", "package", 3, "2054-03-30", "2054-04-02", 1)


def test_r3_25_owner_a_hole_before_the_catch_up_gives_no_line():
    # The days between the two statements are covered by neither: no missed payment can be read there.
    march = _rows(bdays(M(2), M(27)), 850)
    april = _rows([A(8)], 1700) + _rows(bdays(A(9), A(30)), 850)
    assert _chain((march, M(1), M(27)), (april, A(6), A(30))) == []


def test_r3_25_the_missed_due_dates():
    missed = lpc._missed_payments
    assert missed(M(13), M(17), "daily", 0, "US") == [M(16)]
    assert missed(M(13), M(17), "daily", 1, "US") == []
    assert missed(M(13), M(18), "daily", 1, "US") == [M(16)]
    assert missed(A(14), A(28), "weekly", 1, "US") == [A(21)]
    assert missed(A(14), A(22), "weekly", 1, "US") == []
    assert missed(A(14), A(23), "weekly", 1, "US") == [A(21)]
    assert missed(M(17), A(7), "weekly", 1, "US") == [M(24), M(31)]
    # A due date on a holiday moves to the next business day (Memorial Day 2054-05-25).
    assert missed(Y(18), Y(27), "weekly", 1, "US") == []
    assert missed(Y(18), Y(28), "weekly", 1, "US") == [Y(26)]
    # Monthly: the same day of the next month (its last day where it has none), moved to a business day.
    assert missed(A(13), Y(13), "monthly", 1, "US") == []
    assert missed(A(13), Y(14), "monthly", 1, "US") == []
    assert missed(A(13), Y(19), "monthly", 1, "US") == [Y(13)]
    assert missed(date(2054, 1, 31), M(4), "monthly", 1, "US") == [date(2054, 3, 2)] == [
        lpc._open_day(date(2054, 2, 28), "US")]
    # Semi-monthly: 16 days (15 1/6 rounded up), so the 15th to the 1st of a 31-day month is on time.
    assert missed(M(15), A(1), "semimonthly", 1, "US") == []
    assert missed(M(15), A(6), "semimonthly", 1, "US") == [M(31)]


# R3-84: same-cents debits no rule claimed, on the series' schedule inside its gap, are named; never presence.
def test_r3_84_a_statement_stop_names_same_cents_debits_on_the_schedule():
    item = only(_rows(bdays(M(2), M(13)), 850) + _other(bdays(M(16), M(31)), 850))
    assert (item["kind"], item["quiet_business_days"], item["stop_confirmed"], item["last_presence_date"]) == (
        "stop", 12, False, "2054-03-13")
    assert item["same_amount_debits"] == {"count": 12, "first_date": "2054-03-16", "last_date": "2054-03-31"}


def test_r3_84_a_package_pause_names_them():
    march = _rows(bdays(M(2), M(13)), 850) + _other(bdays(M(16), M(31)), 850)
    [item] = _chain((march, M(1), M(31)), (_rows(bdays(A(1), A(30)), 850), A(1), A(30)))
    assert (item["kind"], item["last_before_date"], item["first_after_date"], item["pause_business_days"],
            item["first_after_kind"]) == ("pause", "2054-03-13", "2054-04-01", 13, "payment")
    assert item["same_amount_debits"] == {"count": 12, "first_date": "2054-03-16", "last_date": "2054-03-31"}


def test_r3_84_such_a_stop_is_never_confirmed():
    march = _rows(bdays(M(2), M(13)), 850) + _other(bdays(M(16), M(31)), 850)
    [before] = _chain((_rows(bdays(M(2), M(13)), 850), M(1), M(31)), (_other([A(1)], 20), A(1), A(30)))
    assert (before["kind"], before["stop_confirmed"]) == ("stop", True)
    [item] = _chain((march, M(1), M(31)), (_other(bdays(A(1), A(30)), 850), A(1), A(30)))
    assert (item["kind"], item["stop_confirmed"]) == ("stop", False)
    assert item["same_amount_debits"] == {"count": len(bdays(M(16), M(31))) + len(bdays(A(1), A(30))),
                                          "first_date": "2054-03-16", "last_date": "2054-04-30"}


@pytest.mark.parametrize("others", [
    _other(bdays(M(16), M(31)), 850, "fee"),
    _other(bdays(M(16), M(31)), 850, "nsf_or_return"),
    _other(bdays(M(16), M(31)), 851),
    _other([M(16), M(23), M(30)], 850),
    _other([M(16), M(18), M(20), M(24), M(26)], 850),
])
def test_r3_84_controls_give_no_note(others):
    # Another class (a fee, a return), other cents, another schedule (weekly), or too few of the gap's payments.
    item = only(_rows(bdays(M(2), M(13)), 850) + others)
    assert (item["kind"], item["quiet_business_days"]) == ("stop", 12)
    assert "same_amount_debits" not in item


def test_r3_84_a_reprinted_overlap_day_counts_once():
    march = _rows(bdays(M(2), M(13)), 850) + _other(bdays(M(16), M(31)), 850)
    april = _other([M(30), M(31)], 850) + _rows(bdays(A(1), A(30)), 850)
    [item] = _chain((march, M(1), M(31)), (april, M(29), A(30)))
    assert item["kind"] == "pause"
    assert item["same_amount_debits"] == {"count": 12, "first_date": "2054-03-16", "last_date": "2054-03-31"}


def test_r3_84_never_presence_and_never_a_payment():
    # The note changes no figure of the item: the same stop, quiet and confirmation reading as without the debits.
    plain = only(_rows(bdays(M(2), M(13)), 850))
    noted = only(_rows(bdays(M(2), M(13)), 850) + _other(bdays(M(16), M(31)), 850))
    assert {key: value for key, value in noted.items() if key not in ("same_amount_debits", "locations")} == {
        key: value for key, value in plain.items() if key != "locations"}


# ------------------------------------- audit round 3, R3-B05, review round 1 (findings 1 and 2; fabricated rows only)
@pytest.mark.parametrize("march,catch_up", [
    # Weekly: the last payment on 03-17, a 2x on 03-27 (the 03-24 due date missed); daily: the last payment on 03-13,
    # a 2x on 03-17 (03-16 missed). The next statement prints no debit of the funder.
    (_rows([M(3), M(10), M(17)], 1000) + _rows([M(27)], 2000), "2054-03-27"),
    (_rows(bdays(M(2), M(13)), 850) + _rows([M(17)], 1700), "2054-03-17"),
])
def test_r3_b05_r1_a_package_stop_whose_last_presence_is_a_catch_up(march, catch_up):
    # Finding 1: the package's confirmation branch read a stop whose last presence (a catch-up) sits in a statement
    # before the last one; the stop names the catch-up and confirms on the later statement, and no Caught up item
    # repeats it (one line per event).
    found = _chain((march, M(1), M(31)), (_other([A(6)], 25), A(1), A(30)))
    assert _kinds(found) == ["stop"]
    [item] = found
    assert (item["scope"], item["stop_confirmed"], item["last_presence_date"]) == ("package", True, catch_up)
    assert item["other_debits_after"] == {"count": 1, "last_date": catch_up, "catch_ups": 1}
    assert "payoff" not in item
    # Three statements, the catch-up in the first: the same reading.
    feb = _rows([F(2), F(9), F(16)], 1000) + _rows([F(25)], 3000)
    found = _chain((feb, F(1), F(28)), (_other([M(6)], 25), M(1), M(31)), (_other([A(6)], 25), A(1), A(30)))
    assert [(item["kind"], item["stop_confirmed"], item["other_debits_after"]["catch_ups"]) for item in found] == [
        ("stop", True, 1)]


def _inside(item):
    return item.get("catch_ups_inside")


def test_r3_b05_r1_a_catch_up_after_a_bounced_attempt_that_ended_the_pause_is_named_on_the_pause():
    # Finding 2: daily 850 paid 03-02 to 03-06; a bounced attempt on 03-16 ends the pause; a 2x on 03-17; payments
    # resume on 03-18. One line for the gap: the pause names the 2x, and no Caught up item repeats the missed days.
    attempt = _rows([M(16)], 850, returned_funder_payment_by="transaction:99")
    found = changes(_rows(bdays(M(2), M(6)) + bdays(M(18), M(31)), 850) + attempt + _rows([M(17)], 1700))
    assert _kinds(found) == ["pause"]
    [item] = found
    assert (item["first_after_kind"], item["first_after_date"], item["resumed_date"]) == (
        "attempt", "2054-03-16", "2054-03-18")
    assert _inside(item) == [{"date": "2054-03-17", "amount": 1700.0, "multiple": 2}]
    # Weekly: a bounced attempt on 04-07, a 3x on 04-09, payments resume on 04-14.
    found = changes(_rows(every(M(3), M(17)) + every(A(14), Y(26)), 1000)
                    + _rows([A(7)], 1000, returned_funder_payment_by="transaction:99") + _rows([A(9)], 3000),
                    start=M(1), end=Y(29))
    assert _kinds(found) == ["pause"]
    assert (found[0]["first_after_kind"], _inside(found[0])) == (
        "attempt", [{"date": "2054-04-09", "amount": 3000.0, "multiple": 3}])


def test_r3_b05_r1_a_catch_up_after_a_payment_sized_one_off_that_ended_the_pause_is_named_on_the_pause():
    # Finding 2: a 500 one-off on 03-16 ends the pause and a 3x follows on 03-17; before, the 3x was named nowhere
    # (counted from the one-off, nothing was missed before it).
    found = changes(_rows(bdays(M(2), M(6)) + bdays(M(18), M(31)), 850) + _rows([M(16)], 500) + _rows([M(17)], 2550))
    assert _kinds(found) == ["pause"]
    assert (found[0]["first_after_kind"], _inside(found[0])) == (
        "other_amount", [{"date": "2054-03-17", "amount": 2550.0, "multiple": 3}])
    # Weekly: a 500 one-off on 04-07 ends the pause, the 04-14 payment is missed and a 3x follows on 04-21, before
    # payments resume on 05-05: the pause line names the 3x; before, a separate Caught up line counted from 04-07.
    found = changes(_rows(every(M(3), M(17)) + every(Y(5), Y(26)), 1000) + _rows([A(7)], 500) + _rows([A(21)], 3000),
                    start=M(1), end=Y(29))
    assert _kinds(found) == ["pause"]
    assert (found[0]["first_after_kind"], found[0]["resumed_date"], _inside(found[0])) == (
        "other_amount", "2054-05-05", [{"date": "2054-04-21", "amount": 3000.0, "multiple": 3}])


def test_r3_b05_r1_a_catch_up_on_the_day_payments_resume_is_named_on_the_pause():
    # The 2x posts with the resuming payment on 03-18 (as a catch-up on the regime's next payment day ends a pause).
    attempt = _rows([M(16)], 850, returned_funder_payment_by="transaction:99")
    found = changes(_rows(bdays(M(2), M(6)) + bdays(M(18), M(31)), 850) + attempt + _rows([M(18)], 1700))
    assert _kinds(found) == ["pause"]
    assert _inside(found[0]) == [{"date": "2054-03-18", "amount": 1700.0, "multiple": 2}]


def test_r3_b05_r1_controls_name_no_catch_up_on_the_pause():
    # A pause ended by a catch-up, by an attempt with no multiple after it, or by the regime's payment carries no
    # list; a catch-up after payments resumed is its own event (its own line where it follows a missed payment).
    pause = only(_rows(bdays(M(2), M(6)) + bdays(M(23), M(31)), 300) + _rows([M(16)], 1800))
    assert pause["first_after_kind"] == "catch_up" and "catch_ups_inside" not in pause
    attempt = _rows([M(16)], 850, returned_funder_payment_by="transaction:99")
    alone = only(_rows(bdays(M(2), M(6)) + bdays(M(18), M(31)), 850) + attempt)
    assert alone["first_after_kind"] == "attempt" and "catch_ups_inside" not in alone
    later = [day for day in bdays(M(18), M(31)) if day != M(24)]
    found = changes(_rows(bdays(M(2), M(6)) + later, 850) + attempt + _rows([M(25)], 1700))
    assert _kinds(found) == ["pause", "catch_up"]
    assert "catch_ups_inside" not in found[0]
    assert (found[1]["missed_payments"], found[1]["missed_first_date"], found[1]["catch_up_date"]) == (
        1, "2054-03-24", "2054-03-25")


# --------------------------------------------------- audit round 3, R3-B06 (R3-81, R3-82; fabricated rows only)
def test_r3_81_a_new_stream_names_the_level_paying_when_it_began():
    # Position 1 pays daily 250 in March and April, then 112 from May; position 2 pays daily 170 from 03-16. The new
    # stream began beside the 250 payment: the base named the 112 paid only from May (560.00 -> 1,410.00, +152%).
    found = changes(_rows(bdays(M(2), A(30)), 250) + _rows(bdays(Y(1), J(30)), 112)
                    + _rows(bdays(M(16), J(30)), 170), start=M(1), end=J(30))
    assert _kinds(found) == ["decrease", "new_stream"]
    decrease, stream = found
    assert (decrease["position"], decrease["amount_before"], decrease["amount_after"], decrease["change_percent"],
            decrease["first_after_date"]) == (1, 250.0, 112.0, -55, "2054-05-01")
    assert stream["alongside"] == [{"position": 1, "cadence": "daily", "amount": 250.0}]
    assert (stream["weekly_total_before"], stream["weekly_total_after"], stream["change_percent"]) == (
        1250.0, 2100.0, 68)
    # P's own figures stay its last level (R2-OW18's B8).
    assert (stream["position"], stream["amount_after"], stream["cadence_after"], stream["first_after_date"]) == (
        2, 170.0, "daily", "2054-03-16")


def test_r3_81_the_gate_reads_the_level_paying_when_it_began():
    # (a) Position 1 pays weekly 1,000 to 04-27, then 2,000 from 05-04; a weekly 150 from 03-31 raised the 1,000 paying
    # that day by 15%: a new stream (the base compared it with the later 2,000, 7.5%, and showed none).
    found = changes(_rows(every(M(2), A(27)), 1000) + _rows(every(Y(4), J(29)), 2000)
                    + _rows(every(M(31), J(30)), 150), start=M(1), end=J(30))
    assert [(item["kind"], item["change_percent"]) for item in found] == [("increase", 100), ("new_stream", 15)]
    stream = found[1]
    assert stream["alongside"] == [{"position": 1, "cadence": "weekly", "amount": 1000.0}]
    assert (stream["weekly_total_before"], stream["weekly_total_after"]) == (1000.0, 1150.0)
    # (b) Position 1 pays weekly 2,000, then 500 from 05-04; a weekly 110 from 03-31 was 5.5% of the 2,000 paying that
    # day: no new stream (the base read +22% beside the later 500).
    found = changes(_rows(every(M(2), A(27)), 2000) + _rows(every(Y(4), J(29)), 500)
                    + _rows(every(M(31), J(30)), 110), start=M(1), end=J(30))
    assert [(item["kind"], item["change_percent"]) for item in found] == [("decrease", -75)]


# Audit round 4, R4-B05 (R4-07): the other stream's level at the new stream's start is its KEPT regime (A8, after
# `_drop_short`) holding its latest payment on or before that day: never a 2x or 3x catch-up level (§17.1 (22)) or a
# dropped possible level (§17.1 (18)). Position 1 pays weekly 1,000 on Mondays; the new stream pays on Tuesdays.
_R4_07_MONDAYS = every(M(2), J(29))
_R4_07_WEEKLY = [{"position": 1, "cadence": "weekly", "amount": 1000.0}]


def _r4_07_stream(rows):
    """The one item of `rows` (March to June 2054), a new stream: its change, `alongside` and weekly totals."""
    [item] = changes(rows, start=M(1), end=J(30))
    assert item["kind"] == "new_stream"
    return item["change_percent"], item["alongside"], item["weekly_total_before"], item["weekly_total_after"]


def _r4_07_catch_up_pair(multiple):
    """Position 1's Mondays, 03-23 and 03-30 paid at `multiple` times 1,000 (a catch-up level, run of 2)."""
    pair = {M(23), M(30)}
    return (_rows([day for day in _R4_07_MONDAYS if day not in pair], 1000)
            + _rows(sorted(pair), 1000 * multiple))


def test_r4_07_a_catch_up_pair_before_the_new_stream_never_doubles_the_base():
    tuesdays = every(M(31), J(30))
    # 150 from 03-31. Base: no item (the 2,000 pair read as the level paying, so 150 was 7.5%).
    assert _r4_07_stream(_r4_07_catch_up_pair(2) + _rows(tuesdays, 150)) == (15, _R4_07_WEEKLY, 1000.0, 1150.0)
    # 300. Base: +15% alongside weekly 2,000.00, 2,000.00 -> 2,300.00.
    assert _r4_07_stream(_r4_07_catch_up_pair(2) + _rows(tuesdays, 300)) == (30, _R4_07_WEEKLY, 1000.0, 1300.0)
    # A 3x pair and 350. Base: +12% against 3,000.00.
    assert _r4_07_stream(_r4_07_catch_up_pair(3) + _rows(tuesdays, 350)) == (35, _R4_07_WEEKLY, 1000.0, 1350.0)


def test_r4_07_two_catch_ups_a_month_apart_never_read_a_monthly_level():
    # Position 1 misses 03-09 and 04-06 and pays 2,000 the Monday after each (03-16 and 04-13, 28 days apart: a
    # "monthly" 2,000 level, a catch-up); the new stream pays on Tuesdays from 04-14.
    miss, double = {M(9), A(6)}, {M(16), A(13)}
    rows = (_rows([day for day in _R4_07_MONDAYS if day not in miss | double], 1000)
            + _rows(sorted(double), 2000))
    tuesdays = every(A(14), J(30))
    # 60: 6% of the weekly 1,000, no item (base: a false +13% "alongside monthly 2,000.00", 461.54 -> 521.54).
    assert changes(rows + _rows(tuesdays, 60), start=M(1), end=J(30)) == []
    # 150: +15% (base: +32%, 461.54 -> 611.54).
    assert _r4_07_stream(rows + _rows(tuesdays, 150)) == (15, _R4_07_WEEKLY, 1000.0, 1150.0)


def test_r4_07_controls_the_clean_twin_reads_as_before():
    assert _r4_07_stream(_rows(_R4_07_MONDAYS, 1000) + _rows(every(A(14), J(30)), 150)) == (
        15, _R4_07_WEEKLY, 1000.0, 1150.0)


R3_82_ROWS = _rows(bdays(M(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600)


def _funding(rows):
    item = only(rows)
    assert (item["kind"], item["change_percent"]) == ("decrease", -29)
    return item.get("after_funding")


def test_r3_82_the_funding_note_never_cites_a_credit_the_size_of_the_change_s_payments():
    # The new payment's size (600.00 on 03-18), and the old payment's (850.00 on 03-12, a payment of that day returned).
    assert _funding(R3_82_ROWS + [_credit(M(18), 600)]) is None
    assert _funding(R3_82_ROWS + [_credit(M(12), 850)]) is None
    # Within 1% of a payment amount: 605.00 leaves too; 610.00 (1.7% off) is cited.
    assert _funding(R3_82_ROWS + [_credit(M(18), 605)]) is None
    assert _funding(R3_82_ROWS + [_credit(M(18), 610)]) == {"date": "2054-03-18", "amount": 610.0}


def test_r3_82_the_funding_note_never_cites_a_credit_that_returns_a_payment_just_made():
    # A 700.00 one-off of the series on 03-09 (no amount of the change): a 700.00 credit 0 to 7 days after it returns
    # it; 8 days after, it is cited. An attempt of the series counts as a payment does.
    one_off = R3_82_ROWS + _rows([M(9)], 700)
    assert _funding(one_off + [_credit(M(9), 700)]) is None
    assert _funding(one_off + [_credit(M(16), 700)]) is None
    assert _funding(one_off + [_credit(M(17), 700)]) == {"date": "2054-03-17", "amount": 700.0}
    attempt = R3_82_ROWS + _rows([M(9)], 700, returned_funder_payment_by="transaction:99")
    assert _funding(attempt + [_credit(M(13), 700)]) is None


def test_r3_82_the_funding_note_never_cites_the_old_level_s_own_funding():
    # The old level's first payment is 03-04; a 25,000.00 credit on 03-03 funded it, not the new 600.00 level.
    rows = _rows(bdays(M(4), M(13)), 850) + _rows(bdays(M(16), M(25)), 600)
    assert _funding(rows + [_credit(M(3), 25000)]) is None
    assert _funding(rows + [_credit(M(4), 25000)]) is None
    assert _funding(rows + [_credit(M(5), 25000)]) == {"date": "2054-03-05", "amount": 25000.0}


def test_r3_82_a_payment_sized_credit_never_hides_a_real_funding():
    # The latest credit is cited, as before, among the credits the rules leave: the 600.00 on 03-18 no longer hides the
    # 25,000.00 on 03-13.
    assert _funding(R3_82_ROWS + [_credit(M(13), 25000), _credit(M(18), 600)]) == {
        "date": "2054-03-13", "amount": 25000.0}


@pytest.mark.parametrize("mark", ["returns_funder_payment", "reversal_of"])
def test_r3_82_a_credit_that_returns_or_reverses_a_payment_is_never_a_funding(mark):
    # 900.00 matches no payment of the series: only the mark leaves it out (R2-OW13's pairs).
    assert _funding(R3_82_ROWS + [_credit(M(13), 900, **{mark: "transaction:5"})]) is None
    assert _funding(R3_82_ROWS + [_credit(M(13), 900)]) == {"date": "2054-03-13", "amount": 900.0}


def test_r3_82_a_possible_change_reads_the_kept_regime_before_it():
    # A dropped short regime (§ Still open 18's possible change): daily 500 from 03-09 to 03-20, then weekly 1,600 on
    # 03-23 and 03-30. The regime just before is the daily 500 one, cut before the dropped regime: its own first
    # payment (03-09) bounds the note, and the change's amounts are 500 and 1,600.
    rows = _rows(bdays(M(9), M(20)), 500) + _rows([M(23), M(30)], 1600)

    def funding(credits):
        item = only(rows + credits)
        assert (item["kind"], item["schedule_confirmed"], item["change_percent"]) == ("decrease", False, -36)
        return item.get("after_funding")

    assert funding([_credit(M(5), 25000)]) is None
    assert funding([_credit(M(24), 1600)]) is None
    assert funding([_credit(M(10), 25000), _credit(M(24), 1600)]) == {"date": "2054-03-10", "amount": 25000.0}


def test_r3_82_controls():
    # A small genuine draw, 1.08x the new payment, is still cited (no size floor: revolving draws are payment-sized).
    assert _funding(R3_82_ROWS + [_credit(M(13), 650)]) == {"date": "2054-03-13", "amount": 650.0}
    # The window is unchanged (L13): 20 days before to 5 days after the new amount's first payment (the old level here
    # paying since February, so its own first payment is no bound).
    longer = _rows(bdays(F(2), M(13)), 850) + _rows(bdays(M(16), M(25)), 600)

    def funding(rows):
        return only(rows, start=F(1)).get("after_funding")

    assert funding(longer + [_credit(F(24), 25000)]) == {"date": "2054-02-24", "amount": 25000.0}
    assert funding(longer + [_credit(F(23), 25000)]) is None
    assert funding(longer + [_credit(M(21), 25000)]) == {"date": "2054-03-21", "amount": 25000.0}
    assert funding(longer + [_credit(M(22), 25000)]) is None


# ------------------------------- audit round 4, R4-B03 (R4-75): the Caught up line names the payments its debit re-debited
def _classified(rows, end):
    """The classifier's records of a fabricated Bank of America statement printed from March 1, 2054 to `end`: a sale on
    March 2, then the rows (day, description, amount) in date order (pass 7c reads the returns and re-debits)."""
    from analysis import transaction_classifier as tc
    from analysis.schema import Statement, Transaction
    from tests.test_returned_funder_payments import BOFA, HOLDER, SALE

    ordered = sorted([(M(2), SALE, 24000.0), *rows], key=lambda row: row[0])
    statement = Statement(account_name=HOLDER, bank=BOFA, period_start="2054-03-01", period_end=end.isoformat(),
                          transactions=[Transaction(date=day.isoformat(), description=text, amount=amount,
                                                    direction="credit" if amount > 0 else "debit")
                                        for day, text, amount in ordered])
    return tc.classify_statement_transactions(statement)


def _off_cycle_2x(amount=2000.0):
    """KAPITUS's 1,000.00 on the Fridays of March and April 2054; the 13th's returned on the 15th, the 20th's on the
    22nd; `amount` on Monday the 23rd (2,000.00: R4-75's off-cycle 2x that pays both bounces)."""
    from tests.test_returned_funder_payments import BOFA_RETURN, KAPITUS

    return ([(day, KAPITUS, -1000.0) for day in every(M(6), A(24))]
            + [(M(15), BOFA_RETURN, 1000.0), (M(22), BOFA_RETURN, 1000.0), (M(23), KAPITUS, -amount)])


def test_r4_75_the_caught_up_line_names_the_payments_its_debit_re_debited():
    """The off-cycle 2x pays both bounces (pass 7c takes both out of the rate, each naming it), so its Caught up line
    names both: the 13th and the 20th. Before, the line counted only the 13th (the 20th is one business day before the
    catch-up, on time by CATCH_UP_LATE_BUSINESS_DAYS) while both returned notes said "caught up"."""
    records = _classified(_off_cycle_2x(), A(30))
    [debit] = [record for record in records if record.amount == -2000.0]
    assert {record.date: record.represented_by for record in records if record.represented_by} == {
        "2054-03-13": debit.source_location, "2054-03-20": debit.source_location}
    [item] = lpc.statement_payment_changes(records, period_start="2054-03-01", period_end="2054-04-30",
                                           currency="USD")
    assert _catch_up_fields(item) == ("catch_up", "weekly", 1000.0, "2054-03-06", 2, "2054-03-13", "2054-03-20", 2,
                                      "2054-03-23", 2000.0)


def test_r4_75_controls_a_daily_3x_reads_as_before_and_a_near_multiple_keeps_its_own_dates():
    from tests.test_represented_funder_payments import MULTIPLE_CASES, _statement

    # R4-75's daily 3x: both bounces are already the line's missed business days (unchanged).
    statement = _statement(MULTIPLE_CASES["daily_3x"][0])
    from analysis import transaction_classifier as tc

    [item] = [entry for entry in lpc.statement_payment_changes(
        tc.classify_statement_transactions(statement), period_start="2054-03-01", period_end="2054-03-31",
        currency="USD") if entry["kind"] == "catch_up"]
    assert (item["kind"], item["missed_payments"], item["missed_first_date"], item["missed_last_date"],
            item["multiple"]) == ("catch_up", 2, "2054-03-05", "2054-03-06", 3)
    # 2,995.00, within the line's 2% of 3x but no exact multiple: pass 7c takes no bounce out (both returned notes say
    # "still counts"), so the line keeps its own missed dates (the recorded limit, spec §17.1 (24)).
    records = _classified(_off_cycle_2x(2995.0), A(30))
    assert not any(record.represented_by for record in records)
    [item] = lpc.statement_payment_changes(records, period_start="2054-03-01", period_end="2054-04-30",
                                           currency="USD")
    assert (item["kind"], item["missed_payments"], item["missed_first_date"], item["missed_last_date"],
            item["multiple"]) == ("catch_up", 1, "2054-03-13", "2054-03-13", 3)


def test_r4_75_a_re_debit_named_in_another_statement_of_the_chain_is_not_the_line_s():
    """The module reads `represented_by` as its own statement's location: March's returned 13th naming
    'transaction:1' is April's first row only by its words, so April's Caught up line (2,000.00 on Wednesday the 8th,
    after the missed 3rd) does not take it."""
    march = _rows([M(6), M(20), M(27)], 1000) + _rows(
        [M(13)], 1000, contributes_to_lender_totals=False, returned_funder_payment_by="transaction:99",
        represented_by="transaction:1")
    april = _rows([A(8)], 2000) + _rows(every(A(10), A(24)), 1000)
    [item] = [entry for entry in _chain((march, M(1), M(31)), (april, A(1), A(30))) if entry["kind"] == "catch_up"]
    assert (item["missed_payments"], item["missed_first_date"], item["catch_up_date"], item["_source_statement"]) == (
        1, "2054-04-03", "2054-04-08", 1)
    assert item["_missed_dates"] == ["2054-04-03"]


# ---------------------------- audit round 4, R4-84: a sparse run never borrows its level's schedule (fabricated rows)
# The owner's 2026-10-06 rule ("stays at the new amount for 2 or more payments; one-off short payments are not counted")
# counts payments that keep a schedule: a regime whose own dates (its payments and the attempts at its amount inside its
# span) read no regular schedule takes its level's only while no gap between those dates is more than SPARSE_RUN_CYCLES
# cycles of it plus its beat tolerance; a sparser one is noise, as a run under MIN_PAYMENTS_HELD is (spec §17.1 (32)).
def _r4_84_far_apart():
    """50 on 03-09 and 04-14 (36 days apart), daily 75 from 04-21 to 04-30, then daily 50 from 05-12 (the 50 level
    reads daily on all its dates)."""
    return _rows([M(9), A(14)], 50) + _rows(bdays(A(21), A(30)), 75) + _rows(bdays(Y(12), Y(29)), 50)


def test_r4_84_two_payments_far_apart_never_borrow_a_daily_schedule():
    # The base read the two 50s as a daily regime held 2 payments: a pause 03-09 -> 04-14 (26 business days), a
    # confirmed +50% "after 2 at the old" (reverted) and the -33% "back to the earlier".
    [item] = changes(_r4_84_far_apart(), start=M(1), end=Y(29))
    assert _steps([item]) == [("decrease", "daily", "daily", -33, 8, 13, "2054-05-12")]
    assert (item["back_to_earlier"], item["restart"], item["pause_business_days"]) == (False, True, 8)


def test_r4_84_bounced_attempts_at_another_amount_never_fill_the_gap():
    # The corpus shape (a defaulted account): between the two 50s only bounced attempts at another amount (285), which
    # are presence (no pause) but never the regime's dates. The base read the +50% and the -33% "back to the earlier".
    found = changes(_r4_84_far_apart() + _returned(bdays(M(10), A(13))[::5], 285), start=M(1), end=Y(29))
    assert _steps(found) == [("decrease", "daily", "daily", -33, 8, 13, "2054-05-12")]
    assert found[0]["back_to_earlier"] is False


def test_r4_84_a_weekly_pair_six_weeks_apart_never_borrows_weekly():
    # 1,000 on 01-05 and 02-16 (42 days apart), weekly 1,500 from 02-23 to 03-16, weekly 1,000 from 03-23. The base read
    # a pause 01-05 -> 02-16 (28 business days), +50% after 2 at the old (reverted) and the -33% "back to the earlier".
    found = changes(_rows([date(2054, 1, 5), F(16)], 1000) + _rows(every(F(23), M(16)), 1500)
                    + _rows(every(M(23), A(27)), 1000), start=date(2054, 1, 1), end=A(30))
    assert _steps(found) == [("decrease", "weekly", "weekly", -33, 4, 6, "2054-03-23")]
    assert found[0]["back_to_earlier"] is False


def test_r4_84_a_trailing_pair_36_days_apart_is_noise():
    # Weekly 1,000 in February, weekly 1,500 from 03-02 to 03-16, then 1,000 on 03-23 and 04-28. The base read the
    # +50% (reverted), a -33% held 2 "back to the earlier" and a weekly pause 03-23 -> 04-28 (26 business days).
    found = changes(_rows(every(F(2), F(23)), 1000) + _rows(every(M(2), M(16)), 1500) + _rows([M(23), A(28)], 1000),
                    start=F(1), end=Y(1))
    assert _steps(found) == [("increase", "weekly", "weekly", 50, 4, 3, "2054-03-02")]
    assert found[0]["reverted"] is False


def test_r4_84_controls_a_skipped_week_keeps_weekly_and_a_monthly_pair_its_own_reading():
    weekly = _rows(every(F(2), F(23)), 1000) + _rows(every(M(2), M(16)), 1500)
    # A skipped week (gaps 14 and 7, the largest within 17 days): the 1,000 regime keeps its level's weekly schedule.
    found = changes(weekly + _rows([M(23), A(6), A(13)], 1000), start=F(1), end=A(17))
    assert _steps(found) == [("increase", "weekly", "weekly", 50, 4, 3, "2054-03-02"),
                             ("decrease", "weekly", "weekly", -33, 3, 3, "2054-03-23")]
    assert (found[0]["reverted"], found[1]["back_to_earlier"]) == (True, True)
    # A trailing pair 35 days apart reads monthly by its own dates (no fallback): the possible -85% stays.
    found = changes(weekly + _rows([M(23), A(27)], 1000), start=F(1), end=Y(1))
    assert _steps(found) == [("increase", "weekly", "weekly", 50, 4, 3, "2054-03-02"),
                             ("decrease", "weekly", "monthly", -85, 3, 2, "2054-03-23")]
    assert (found[1]["schedule_confirmed"], found[1]["back_to_earlier"]) == (False, True)


@pytest.mark.parametrize("cadence,bound", [("daily", 3), ("weekly", 17), ("biweekly", 35), ("semimonthly", 38),
                                           ("monthly", 77)])
def test_r4_84_the_sparse_bound_is_two_cycles_and_the_beat_tolerance(cadence, bound):
    def regime(*gaps):
        days = [date(2054, 1, 5)]
        for gap in gaps:
            days.append(days[-1] + timedelta(days=gap))
        pays = [lpc._Pay(day, 100000, 0, index, f"transaction:{index}", None) for index, day in enumerate(days)]
        return lpc._Regime(0, 100000, cadence, pays)

    assert lpc._sparse_gap(regime(bound), ()) is False
    assert lpc._sparse_gap(regime(bound + 1), ()) is True
    # An attempt at the regime's amount inside the gap splits it.
    long = regime(bound + 1)
    assert lpc._sparse_gap(long, (long.first + timedelta(days=1),)) is False

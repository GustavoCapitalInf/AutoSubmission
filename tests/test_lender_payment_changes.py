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
    assert (lpc.CADENCE_CHANGE_MIN_PAYMENTS, lpc.CADENCE_CHANGE_MIN_DAILY) == (3, 5)


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


@pytest.mark.parametrize("amount", [20, 1700])
def test_l31_a_fee_sized_or_payoff_sized_debit_is_not_presence(amount):
    item = only(_rows(bdays(M(2), M(20)), 850) + _rows([M(26)], amount))
    assert (item["kind"], item["last_presence_date"], item["quiet_business_days"]) == ("stop", "2054-03-20", 7)
    assert item.get("payoff") == ({"date": "2054-03-26", "amount": 1700.0} if amount == 1700 else None)


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

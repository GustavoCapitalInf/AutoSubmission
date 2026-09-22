"""Fabricated pages only. A date that straddles a page break is observed twice: the earlier page shows the
balance where the page ends, partway through the day, and the next page carries the day on to its close.
That is a checkpoint, not a contradiction. Everything else that disagrees still refuses.
"""
from copy import deepcopy
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.pair_metadata import merge_metadata
from vlm.review import PageReviewMerge

BASE = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"}


def _page(number, daily, *, role="statement_page", errors=(), rows=1):
    account = dict(BASE) if number == 1 else {}
    body = tuple(CandidateRow("2031-01-02", "01/02", "FABRICATED ROW", Decimal("1.00"), "credit", None,
                              number, "stage_a+stage_b", f"b1t0r{index}") for index in range(rows))
    return PageReviewMerge(number, body, (), {"agreed": len(body)}, tuple(errors), account,
                           tuple({"date": d, "balance": b} for d, b in daily), role, ())


def _merge(pages):
    before = deepcopy(pages)
    occurrences = []
    account, daily, reasons, _ = merge_metadata(pages, occurrences=occurrences)
    assert pages == before
    return daily, reasons, occurrences


def test_a_day_continued_on_the_next_page_keeps_its_closing_balance_without_a_conflict():
    daily, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),     # page ends partway through the 12th
        _page(2, [("2031-01-12", 70), ("2031-01-15", 40)]),     # the 12th continues and closes at 70
    ])
    assert "anchor_disagreement" not in reasons
    assert {"date": "2031-01-12", "balance": 70} in daily


def test_every_page_break_in_a_chain_is_a_checkpoint():
    daily, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 70), ("2031-01-15", 40)]),
        _page(3, [("2031-01-15", 45), ("2031-01-22", 20)]),
    ])
    assert "anchor_disagreement" not in reasons
    assert {"date": "2031-01-15", "balance": 45} in daily


def test_a_date_that_is_not_the_last_on_the_earlier_page_still_conflicts():
    _, reasons, occurrences = _merge([
        _page(1, [("2031-01-12", 80), ("2031-01-13", 60)]),     # the 12th closed on page 1
        _page(2, [("2031-01-12", 70), ("2031-01-15", 40)]),
    ])
    assert "anchor_disagreement" in reasons
    assert [o["page"] for o in occurrences if o["code"] == "anchor_disagreement"] == [2]


def test_a_date_that_is_not_the_first_on_the_later_page_still_conflicts():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-11", 90), ("2031-01-12", 70)]),
    ])
    assert "anchor_disagreement" in reasons


def test_a_conflicting_figure_listed_out_of_printed_order_still_conflicts():
    # The adversarial case: the earlier date is the smallest on the next page but printed after later
    # dates, so it cannot be the continuation of the previous page's last day.
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-15", 40), ("2031-01-12", 70)]),
    ])
    assert "anchor_disagreement" in reasons


def test_the_last_entry_must_also_be_the_latest_date_on_the_earlier_page():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-13", 60), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 70), ("2031-01-15", 40)]),
    ])
    assert "anchor_disagreement" in reasons


def test_a_carried_forward_opening_then_the_days_close_on_the_same_page_is_not_a_conflict():
    # The shape measured on a real statement: the continuation page first restates the previous page's
    # last daily figure (the BALANCE FORWARD), then prints the same day's close further down.
    daily, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 80), ("2031-01-12", 70), ("2031-01-15", 40)]),
    ])
    assert "anchor_disagreement" not in reasons
    assert {"date": "2031-01-12", "balance": 70} in daily


def test_every_carried_forward_page_in_a_chain_is_accepted():
    daily, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 80), ("2031-01-12", 70), ("2031-01-15", 40)]),
        _page(3, [("2031-01-15", 40), ("2031-01-15", 45), ("2031-01-22", 20)]),
        _page(4, [("2031-01-22", 20), ("2031-01-23", 10)]),
    ])
    assert "anchor_disagreement" not in reasons
    assert {"date": "2031-01-15", "balance": 45} in daily


def test_a_carried_day_may_close_only_once():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 80), ("2031-01-12", 70), ("2031-01-12", 60)]),
    ])
    assert "anchor_disagreement" in reasons


def test_a_first_entry_that_does_not_repeat_the_previous_figure_is_not_a_carry():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 75), ("2031-01-12", 70), ("2031-01-15", 40)]),
    ])
    assert "anchor_disagreement" in reasons


def test_a_carry_must_be_the_first_entry_on_its_page():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-11", 90), ("2031-01-12", 80), ("2031-01-12", 70)]),
    ])
    assert "anchor_disagreement" in reasons


def test_non_adjacent_pages_still_conflict():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(3, [("2031-01-12", 70), ("2031-01-15", 40)]),
    ])
    assert "anchor_disagreement" in reasons


def test_a_page_that_is_not_a_clean_statement_page_cannot_supply_a_checkpoint():
    for broken in (dict(errors=("review_truncated",)), dict(role="summary_page"), dict(rows=0)):
        _, reasons, _ = _merge([
            _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
            _page(2, [("2031-01-12", 70), ("2031-01-15", 40)], **broken),
        ])
        assert "anchor_disagreement" in reasons, broken


def test_the_same_value_on_both_sides_is_not_a_conflict_either_way():
    _, reasons, _ = _merge([
        _page(1, [("2031-01-10", 50), ("2031-01-12", 80)]),
        _page(2, [("2031-01-12", 80), ("2031-01-15", 40)]),
    ])
    assert "anchor_disagreement" not in reasons

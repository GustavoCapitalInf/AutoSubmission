"""Fabricated pages only. The deterministic cheque-echo backstop.

A picture of a cheque or deposit slip shows a transaction already listed in the statement. When every row
the review kept on a page repeats, one to one, a transaction on an EARLIER ledger page, the page is a cheque
picture page whatever the reviewer called it (owner ruling, 2026-09-22: "dont hold cheque picture pages").
A repeat is the same amount, the same direction when the picture's is known, and a ledger posting dated on or
after the picture's date: a cheque is written before it clears, while a real later page lists later
postings. A pictured cheque prints no running balance and no daily-balance table. A page whose kept rows do
not all repeat earlier transactions is not pictures, even if the reviewer labelled it cheque_images: its rows
enter the ledger and the arithmetic judges them.
"""
from dataclasses import replace
from decimal import Decimal

from ocr.truncation import assess_pages
from vlm.assemble import CandidateRow
from vlm.pair import held_pages, ledger_rows, page_texts
from vlm.review import PageReviewMerge, confidence_summary, mark_ledger_echoes, picture_page

HEADER = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"}


def _row(number, index, spec, source):
    # spec: an amount, or a dict overriding amount / direction / date / balance.
    spec = spec if isinstance(spec, dict) else {"amount": spec}
    when = spec.get("date", "2031-01-05")
    balance = spec.get("balance")
    return CandidateRow(when, when[5:] if when else "", f"FABRICATED {number}-{index}", Decimal(str(spec["amount"])),
                        spec.get("direction", "debit"), None if balance is None else Decimal(str(balance)),
                        number, source, f"added{index}")


def _page(number, amounts, *, role="statement_page", source="stage_b", counts=None, account=None, errors=(),
          daily=()):
    rows = tuple(_row(number, index, spec, source) for index, spec in enumerate(amounts))
    state = "added" if source == "stage_b" else "agreed"
    return PageReviewMerge(number, rows, (), counts or {state: len(rows)}, tuple(errors),
                           {**HEADER, **(account or {})}, tuple(daily), role, ())


def _ledger(number=1):
    # An oldest-first listing; the default picture date (the 5th) precedes every posting.
    postings = [("120.00", "2031-01-06"), ("45.10", "2031-01-08"), ("45.10", "2031-01-10"), ("300.00", "2031-01-15"),
                ("9.99", "2031-01-20")]
    return _page(number, [{"amount": amount, "date": when} for amount, when in postings], source="stage_a+stage_b")


def _echoes(pages):
    return [merged.page for merged in mark_ledger_echoes(pages) if merged.ledger_echo]


def test_a_page_whose_added_rows_all_repeat_earlier_transactions_is_pictures_whatever_its_label():
    for role in ("statement_page", "cheque_images"):
        pages = mark_ledger_echoes([_ledger(), _page(2, ["45.10", "300.00", "120.00"], role=role)])
        assert [merged.ledger_echo for merged in pages] == [False, True], role
        assert picture_page(pages[1]), role
        rows, excluded = ledger_rows(pages)
        assert len(rows) == 5 and excluded == 3, role
        assert held_pages(pages, [[], []], [False, True]) == [], role
        assert confidence_summary(pages, gate_admitted=True)["counts"]["added"] == 0, role
        texts = page_texts(pages, [False, True])
        assert texts[1] == "" and [item.truncated for item in assess_pages(texts)] == [False, False], role


def test_the_match_is_one_to_one():
    # Two pictured cheques of 120.00 but only one such transaction: not an echo.
    assert _echoes([_ledger(), _page(2, ["120.00", "120.00"])]) == []
    assert _echoes([_ledger(), _page(2, ["45.10", "45.10"])]) == [2]


def test_two_picture_pages_cannot_claim_the_same_transaction():
    assert _echoes([_ledger(), _page(2, ["300.00", "9.99"]), _page(3, ["300.00", "45.10"])]) == [2]


def test_only_earlier_pages_are_the_ledger():
    assert _echoes([_page(1, ["120.00", "45.10"]), _ledger(2)]) == []


def test_an_unlabelled_page_needs_two_repeating_rows_a_labelled_one_needs_one():
    assert _echoes([_ledger(), _page(2, ["300.00"])]) == []
    assert _echoes([_ledger(), _page(2, ["300.00"], role="cheque_images")]) == [2]


def test_a_partial_match_is_a_statement_page():
    pages = mark_ledger_echoes([_ledger(), _page(2, ["300.00", "45.10", "77.77"])])
    assert not pages[1].ledger_echo and not picture_page(pages[1])
    rows, excluded = ledger_rows(pages)
    assert len(rows) == 8 and excluded == 0


def test_a_labelled_page_whose_rows_do_not_repeat_the_ledger_is_not_pictures():
    # Closes a single-reader path: the proposer read nothing from a real page (for example it failed), the
    # reviewer added every row and called the page cheque_images. Those rows are new, so the page counts.
    pages = mark_ledger_echoes([_ledger(), _page(2, ["61.00", "18.50"], role="cheque_images")])
    assert not picture_page(pages[1])
    assert held_pages(pages, [[], ["proposer_transport_failed"]], [False, False]) == [2]
    rows, _ = ledger_rows(pages)
    assert len(rows) == 7


def test_proposer_rows_the_review_kept_may_echo_too():
    # The shape of a cheque page the proposer read text from: some rows confirmed, some corrected, some added.
    kept = replace(_page(2, ["45.10", "9.99", "120.00"], source="stage_a+stage_b"),
                   counts={"agreed": 1, "corrected": 1, "added": 1})
    assert _echoes([_ledger(), kept]) == [2]


def test_a_summary_figure_or_an_invalid_review_never_echoes():
    for change in (dict(account={"ending_balance": 160}), dict(account={"stated_debit_count": 2}),
                   dict(errors=("review_missing_candidate_id",))):
        pages = mark_ledger_echoes([_ledger(), _page(2, ["45.10", "300.00"], **change)])
        assert not pages[1].ledger_echo and not picture_page(pages[1]), change


def test_a_labelled_page_with_no_rows_is_still_pictures():
    pages = mark_ledger_echoes([_ledger(), _page(2, [], role="cheque_images", counts={"rejected": 2})])
    assert not pages[1].ledger_echo and picture_page(pages[1])


def test_marking_never_mutates_and_keeps_every_page_slot():
    pages = [_ledger(), _page(2, ["45.10", "300.00"]), _page(3, [])]
    marked = mark_ledger_echoes(pages)
    assert [merged.page for merged in marked] == [1, 2, 3]
    assert not any(merged.ledger_echo for merged in pages)
    assert [replace(merged, ledger_echo=False) for merged in marked] == pages


# --- hardening after the independent review of e25b7bc ------------------------------------------------------
# F1: a real last page of a per-page-summary statement, its box unread, whose amounts recur earlier.
# F2: a real zero-net page (a fee and its refund, a transfer out and back) on any statement.
# Both were taken for pictures by amount alone and the statement admitted without them.

def test_a_real_later_page_repeating_earlier_amounts_is_not_pictures():
    later = [{"amount": "45.10", "date": "2031-01-12"}, {"amount": "300.00", "date": "2031-01-14"}]
    assert _echoes([_ledger(), _page(2, later)]) == []
    assert _echoes([_ledger(), _page(2, later, role="cheque_images")]) == []


def test_a_zero_net_pair_is_not_pictures():
    fee_and_refund = [{"amount": "45.10", "date": "2031-01-12"},
                      {"amount": "45.10", "direction": "credit", "date": "2031-01-12"}]
    assert _echoes([_ledger(), _page(2, fee_and_refund)]) == []


def test_a_row_printing_a_running_balance_is_never_a_picture():
    assert _echoes([_ledger(), _page(2, [{"amount": "45.10", "balance": "160.00"}, "300.00"])]) == []


def test_a_daily_balance_table_is_never_pictures():
    daily = [{"date": "2031-01-05", "balance": 150}]
    assert _echoes([_ledger(), _page(2, ["45.10", "300.00"], daily=daily)]) == []
    labelled = mark_ledger_echoes([_ledger(), _page(2, [], role="cheque_images", counts={"rejected": 1}, daily=daily)])
    assert not picture_page(labelled[1])
    quarantined = replace(_page(2, ["45.10", "300.00"]), metadata_evidence=({"scope": "daily_balances", "page": 2},))
    assert _echoes([_ledger(), quarantined]) == []


def test_a_known_direction_must_agree():
    assert _echoes([_ledger(), _page(2, [{"amount": "45.10", "direction": "credit"}, "300.00"])]) == []
    assert _echoes([_ledger(), _page(2, [{"amount": "45.10", "direction": "unknown"}, "300.00"])]) == [2]


def test_an_undated_row_cannot_be_shown_to_repeat_anything():
    assert _echoes([_ledger(), _page(2, [{"amount": "45.10", "date": None}, "300.00"])]) == []
    undated_ledger = _page(1, [{"amount": "45.10", "date": None}, {"amount": "300.00", "date": None}],
                           source="stage_a+stage_b")
    assert _echoes([undated_ledger, _page(2, ["45.10", "300.00"])]) == []


def test_a_picture_dated_before_its_posting_repeats_it():
    written_earlier = [{"amount": "45.10", "date": "2031-01-02"}, {"amount": "300.00", "date": "2031-01-05"}]
    assert _echoes([_ledger(), _page(2, written_earlier)]) == [2]


def test_the_assignment_is_a_true_matching_not_first_come():
    # The unknown-direction row must take the credit so the debit row can take the debit.
    ledger = _page(1, [{"amount": "10.00", "direction": "debit", "date": "2031-01-10"},
                       {"amount": "10.00", "direction": "credit", "date": "2031-01-11"}], source="stage_a+stage_b")
    pictures = _page(2, [{"amount": "10.00", "direction": "unknown", "date": "2031-01-05"},
                         {"amount": "10.00", "direction": "debit", "date": "2031-01-05"}])
    assert _echoes([ledger, pictures]) == [2]


# --- second review round (045380e) -------------------------------------------------------------------------
# R1: newest-first listings invert the date test. R2: a real continuation page repeating same-day postings.
# R3: pictures printed BEFORE the listing must not become the ledger that the listing then "repeats".

def test_a_newest_first_or_undetermined_listing_allows_no_echo():
    newest_first = _page(1, [{"amount": "500.00", "direction": "credit", "date": "2031-01-28"},
                             {"amount": "45.10", "date": "2031-01-25"},
                             {"amount": "500.00", "date": "2031-01-20"},
                             {"amount": "45.10", "date": "2031-01-18"}], source="stage_a+stage_b")
    older = [{"amount": "500.00", "date": "2031-01-10"}, {"amount": "500.00", "direction": "credit", "date": "2031-01-12"}]
    assert _echoes([newest_first, _page(2, older)]) == []
    unknown = [dict(row, direction="unknown") for row in older]
    assert _echoes([newest_first, _page(2, unknown)]) == []
    one_day = _page(1, [{"amount": "45.10"}, {"amount": "300.00"}], source="stage_a+stage_b")
    assert _echoes([one_day, _page(2, ["45.10", "300.00"], role="cheque_images")]) == []


def test_a_continuation_repeating_same_day_postings_is_not_pictures():
    # Identical fees straddling a page break: the real next page's rows are dated on the last posting day.
    ledger = _page(1, [{"amount": "35.00", "date": "2031-01-02"}, {"amount": "35.00", "date": "2031-01-03"},
                       {"amount": "35.00", "date": "2031-01-03"}], source="stage_a+stage_b")
    same_day = [{"amount": "35.00", "date": "2031-01-03"}, {"amount": "35.00", "date": "2031-01-03"}]
    assert _echoes([ledger, _page(2, same_day)]) == []
    assert _echoes([ledger, _page(2, same_day[:1], role="cheque_images")]) == []


def test_only_pages_whose_proposer_rows_were_kept_are_the_ledger():
    # Pictures printed before the listing, not recognized, added by the reviewer only: they are no ledger for
    # the real listing page after them to repeat.
    pictures_first = _page(1, [{"amount": "45.10", "date": "2031-01-06"}, {"amount": "300.00", "date": "2031-01-09"}])
    listing = _page(2, [{"amount": "45.10", "date": "2031-01-04"}, {"amount": "300.00", "date": "2031-01-08"}],
                    source="stage_a+stage_b")
    assert _echoes([pictures_first, listing]) == []


def test_any_printed_statement_figure_or_an_unread_daily_table_is_statement_evidence():
    for name, value in (("stated_service_charge", 12), ("stated_interest_paid", 0.5), ("stated_nsf_count", 1),
                        ("days_in_period", 31), ("bank_reported_average_balance", 900)):
        assert _echoes([_ledger(), _page(2, ["45.10", "300.00"], account={name: value})]) == [], name
    undated = replace(_page(2, ["45.10", "300.00"]),
                      diagnostics=({"scope": "daily_balances", "page": 2, "index": 0, "code": "review_daily_balance_undated"},))
    assert _echoes([_ledger(), undated]) == []


def test_unresolved_rows_on_a_picture_page_do_not_hold_it():
    # Owner ruling: nothing on a cheque picture page holds the statement. The kept rows prove the page.
    pictures = replace(_page(2, ["45.10", "300.00"]), counts={"added": 2, "unresolved": 1})
    marked = mark_ledger_echoes([_ledger(), pictures])
    assert marked[1].ledger_echo and held_pages(marked, [[], []], [False, False]) == []

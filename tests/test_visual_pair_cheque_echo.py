"""Fabricated pages only. The deterministic cheque-echo backstop.

A picture of a cheque or deposit slip shows a transaction already listed in the statement. When every row
the review kept on a page repeats, amount for amount and one to one, a transaction on an EARLIER ledger page,
the page is a cheque picture page whatever the reviewer called it (owner ruling, 2026-09-22: "dont hold
cheque picture pages"). A cheque image carries the date it was written, not the posting date, so only the
amount is compared. A page whose kept rows do not all repeat earlier transactions is not pictures, even if
the reviewer labelled it cheque_images: its rows enter the ledger and the arithmetic judges them.
"""
from dataclasses import replace
from decimal import Decimal

from ocr.truncation import assess_pages
from vlm.assemble import CandidateRow
from vlm.pair import held_pages, ledger_rows, page_texts
from vlm.review import PageReviewMerge, confidence_summary, mark_ledger_echoes, picture_page

HEADER = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"}


def _page(number, amounts, *, role="statement_page", source="stage_b", counts=None, account=None, errors=()):
    rows = tuple(CandidateRow("2031-01-05", "01/05", f"FABRICATED {number}-{index}", Decimal(str(amount)),
                              "debit", None, number, source, f"added{index}")
                 for index, amount in enumerate(amounts))
    state = "added" if source == "stage_b" else "agreed"
    return PageReviewMerge(number, rows, (), counts or {state: len(rows)}, tuple(errors),
                           {**HEADER, **(account or {})}, (), role, ())


def _ledger(number=1):
    return _page(number, ["120.00", "45.10", "45.10", "300.00", "9.99"], source="stage_a+stage_b")


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

"""Fabricated pages only. The reviewer is asked to list EVERY account number visible on a page, so the list
includes the other side of a transfer and reference numbers printed inside transaction rows. Those are not
claims about which account this statement is. A number that is NOT printed inside any transaction on its
page (a second account's own header, say) still counts, so a PDF holding two accounts is still refused.
"""
from copy import deepcopy
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.pair_metadata import merge_metadata
from vlm.review import PageReviewMerge

BASE = {"period_start": "2031-01-01", "period_end": "2031-01-31", "currency": "USD"}
OWN = "9-000-1111-2222"


def _page(number, *, account_number=OWN, seen=(), descriptions=("FABRICATED ROW",), evidence=()):
    account = dict(BASE) if number == 1 else {}
    if account_number is not None:
        account["account_number"] = account_number
    rows = tuple(CandidateRow("2031-01-02", "01/02", text, Decimal("1.00"), "credit", None, number,
                              "stage_a+stage_b", f"b1t0r{index}") for index, text in enumerate(descriptions))
    return PageReviewMerge(number, rows, tuple(evidence), {"agreed": len(rows)}, (), account, (),
                           "statement_page", tuple(seen))


def _reasons(pages):
    before = deepcopy(pages)
    occurrences = []
    account, _, reasons, _ = merge_metadata(pages, occurrences=occurrences)
    assert pages == before
    return account, reasons, occurrences


def test_counterparty_numbers_printed_in_transfers_are_not_identity_claims():
    account, reasons, _ = _reasons([
        _page(1, seen=(OWN, "400012345678", "400087654321"),
              descriptions=("MOBILE TRANSFER FROM ACCOUNT 400012345678", "MOBILE TRANSFER FROM ACCOUNT 400087654321")),
        _page(2, seen=(OWN,)),
    ])
    assert "proposal_invalid" not in reasons
    assert account["account_number"] == OWN


def test_a_later_page_repeating_the_own_account_is_not_poisoned_by_earlier_counterparties():
    # The failure seen on a real statement: page 1's counterparties were registered as identities, so
    # page 3's correct own account number then conflicted with them.
    _, reasons, occurrences = _reasons([
        _page(1, seen=("400012345678",), descriptions=("TRANSFER FROM ACCOUNT 400012345678",)),
        _page(2, account_number=OWN, seen=(OWN,)),
    ])
    assert "proposal_invalid" not in reasons and occurrences == []


def test_masked_counterparties_are_matched_as_printed():
    _, reasons, _ = _reasons([
        _page(1, seen=("XXXXX4775",), descriptions=("ONLINE TRANSFER FROM XXXXX4775 AT 1/02/31",)),
    ])
    assert "proposal_invalid" not in reasons


def test_numbers_in_rejected_or_unresolved_rows_also_count_as_printed_in_a_transaction():
    evidence = ({"state": "rejected", "original": {"description": "SUMMARY LINE 400012345678"}},)
    _, reasons, _ = _reasons([_page(1, seen=("400012345678",), evidence=evidence)])
    assert "proposal_invalid" not in reasons


def test_a_second_account_that_is_not_printed_in_any_transaction_is_still_refused():
    _, reasons, occurrences = _reasons([
        _page(1, seen=(OWN, "9-000-3333-4444")),
    ])
    assert reasons == ["proposal_invalid"]
    assert occurrences[0]["field"] == "account_numbers_seen"


def test_a_second_accounts_own_header_on_a_later_page_is_still_refused():
    _, reasons, _ = _reasons([_page(1), _page(2, account_number="9-000-3333-4444")])
    assert reasons == ["proposal_invalid"]


def test_short_fragments_never_excuse_a_number():
    # Six characters is the floor: a four-digit fragment could match an amount or a date.
    _, reasons, _ = _reasons([_page(1, seen=(OWN, "4444"), descriptions=("FEE 4444.00",))])
    assert reasons == ["proposal_invalid"]

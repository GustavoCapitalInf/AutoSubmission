"""A statement whose own printed figures contradict the transactions it lists is a valid failure, said only when the
PDF's text layer proves the reading complete and exact (vlm/source_contradiction.py; owner ruling, 2026-09-23).
Fabricated statements only."""
from dataclasses import replace
from decimal import Decimal

import pytest

from vlm.assemble import CandidateRow
from vlm.native_text import PrintedEvidence
from vlm.source_contradiction import (SourceContradictionError, is_source_contradiction,
                                      verify_source_contradiction)

PAGE_ONE = ("FABRICATED BANK\nFABRICATED BUSINESS CHECKING\nBeginning Balance $10.00\nCredits (+) 300.00\n"
            "Debits (-) 250.00\nOther Debits 250.00\nEnding Balance $60.00\nDeposits (+)\nDate Amount Description\n"
            "03/02 300.00 FABRICATED DEPOSIT\nPage 1 of 2\n")
PAGE_TWO = ("Other Debits (-)\nDate Amount Description\n03/05 100.00 FABRICATED TRANSFER TO CHECKING\n"
            "03/09 50.00 FABRICATED PURCHASE\nPage 2 of 2\n")
ACCOUNT = {"beginning_balance": 10.0, "ending_balance": 60.0, "stated_total_credits": 300.0,
           "stated_total_debits": 250.0, "currency": "USD"}


def _row(page, date_text, amount, direction):
    return CandidateRow(f"2031-{date_text.replace('/', '-')}", date_text, "FABRICATED", Decimal(amount), direction,
                        None, page, "stage_a+stage_b", f"b1t0r{page}{date_text[-2:]}", "column",
                        (0.125, 0.225, 0.875, 0.325), Decimal(amount))


ROWS = [_row(1, "03/02", "300.00", "credit"), _row(2, "03/05", "100.00", "debit"), _row(2, "03/09", "50.00", "debit")]


def _verify(pages=(PAGE_ONE, PAGE_TWO), rows=ROWS, account=ACCOUNT, reasons=("sum_mismatch", "summary_mismatch")):
    return verify_source_contradiction(reasons=list(reasons), rows=rows, account=dict(account),
                                       printed_pages=[PrintedEvidence(native=text) for text in pages])


def test_a_statement_listing_fewer_debits_than_it_prints_is_a_verified_contradiction():
    verdict = _verify()
    assert verdict["kind"] == "debit_total" and (verdict["listed"], verdict["printed"]) == ("150.00", "250.00")
    assert verdict["reached_balance"] == "160.00" and verdict["ending_balance"] == "60.00"
    error = SourceContradictionError.from_verdict(verdict)
    assert error.dashboard_message() == "Fail: Statement debit total ($150.00 listed, $250.00 printed) contradiction"
    assert is_source_contradiction(str(error))


@pytest.mark.parametrize("change", [
    # An amount on a line that could be a row, which no row accounts for: the reading may have missed it.
    lambda: {"pages": (PAGE_ONE, PAGE_TWO.replace("Page 2 of 2", "03/12 100.00 FABRICATED FEE\nPage 2 of 2"))},
    # A doubt about the reading itself, not arithmetic.
    lambda: {"reasons": ("sum_mismatch", "page_unresolved")},
    lambda: {"reasons": ("count_mismatch",)},
    # A page without a text layer cannot be checked.
    lambda: {"pages": (PAGE_ONE, None)},
    # The pages say there are three; the file has two.
    lambda: {"pages": (PAGE_ONE.replace("Page 1 of 2", "Page 1 of 3"), PAGE_TWO.replace("Page 2 of 2", "Page 2 of 3"))},
    # A statement figure equal to the difference could be a row the reading missed.
    lambda: {"pages": (PAGE_ONE.replace("Other Debits 250.00", "Other Debits 150.00\nElectronic Withdrawals 100.00"),
                       PAGE_TWO)},
    # No printed total equals its listed side and no row prints its balance: the directions are not proven.
    lambda: {"account": {**ACCOUNT, "stated_total_credits": 301.0}},
    # A row printed nowhere on its page.
    lambda: {"rows": ROWS[:2] + [replace(ROWS[2], amount=Decimal("51.00"))]},
    # The listed transactions do reach the printed ending balance.
    lambda: {"account": {**ACCOUNT, "ending_balance": 160.0}, "pages": (PAGE_ONE.replace("$60.00", "$160.00"), PAGE_TWO)},
])
def test_any_doubt_about_the_reading_leaves_the_statement_held(change):
    arguments = change()
    if arguments.get("pages") and None in arguments["pages"]:
        pages = [PrintedEvidence(native=text) if text else None for text in arguments["pages"]]
        assert verify_source_contradiction(reasons=["sum_mismatch"], rows=ROWS, account=dict(ACCOUNT),
                                           printed_pages=pages) is None
        return
    assert _verify(**arguments) is None


def test_the_ending_balance_is_named_when_no_printed_total_is_contradicted():
    pages = (PAGE_ONE.replace("Credits (+) 300.00\nDebits (-) 250.00\nOther Debits 250.00\n", ""), PAGE_TWO)
    rows = [replace(row, balance=balance) for row, balance in zip(ROWS, (Decimal("310.00"), Decimal("210.00"),
                                                                       Decimal("160.00")))]
    pages = (pages[0].replace("03/02 300.00 FABRICATED DEPOSIT", "03/02 300.00 FABRICATED DEPOSIT 310.00"),
             pages[1].replace("100.00 FABRICATED TRANSFER TO CHECKING", "100.00 FABRICATED TRANSFER TO CHECKING 210.00")
             .replace("50.00 FABRICATED PURCHASE", "50.00 FABRICATED PURCHASE 160.00"))
    verdict = _verify(pages=pages, rows=rows, account={**ACCOUNT, "stated_total_credits": None,
                                                        "stated_total_debits": None})
    assert verdict["kind"] == "ending_balance" and (verdict["listed"], verdict["printed"]) == ("160.00", "60.00")
    assert SourceContradictionError.from_verdict(verdict).dashboard_message() == (
        "Fail: Statement ending balance ($160.00 from the listed transactions, $60.00 printed) contradiction")


def test_only_a_well_formed_verdict_becomes_the_refusal():
    for verdict in (None, {}, {"version": 1, "kind": "free text", "listed": "1.00", "printed": "2.00"},
                    {"version": 1, "kind": "debit_total", "listed": "1.00", "printed": "1.00"},
                    {"version": 1, "kind": "debit_total", "listed": "x", "printed": "2.00"},
                    {"version": 1, "kind": "debit_total", "listed": "1.00", "printed": "2.00", "currency": "US DOLLARS"}):
        assert SourceContradictionError.from_verdict(verdict) is None, verdict
    assert not is_source_contradiction("visual pair gate refused the document")
    assert not is_source_contradiction("Fail: Statement account 1234567 contradiction")


def test_the_adapter_refuses_a_held_statement_with_its_verified_contradiction():
    from vlm.pair_adapter import VisualPairAdmissionError, analyze_visual_pair

    class _Doc:
        visual_pair = {"version": 1, "account_count": 1,
                       "gate": {"admitted": False, "reasons": ["sum_mismatch"],
                                "source_contradiction": _verify()}}
    with pytest.raises(SourceContradictionError) as raised:
        analyze_visual_pair(_Doc())
    assert str(raised.value) == "Fail: Statement debit total ($150.00 listed, $250.00 printed) contradiction"
    _Doc.visual_pair = {**_Doc.visual_pair, "gate": {"admitted": False, "reasons": ["sum_mismatch"],
                                                     "source_contradiction": {"kind": "debit_total"}}}
    with pytest.raises(VisualPairAdmissionError):
        analyze_visual_pair(_Doc())


# The dashboard's display of a stored contradiction moved to tests/test_stored_job_display.py (model-code removal,
# slice S1), rebuilt on a fabricated message of the stored shape so it needs no vlm import.

"""A statement whose own printed figures contradict the transactions it lists is a valid failure, said only when the
PDF's text layer proves the reading complete and exact (vlm/source_contradiction.py; owner ruling, 2026-09-23).
Fabricated statements only."""
import json
import shutil
import subprocess
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

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


def test_the_worker_publishes_the_contradiction_and_withholds_a_forged_one():
    from webapp.worker import _analysis_failure
    error = SourceContradictionError("credit_total", Decimal("100.00"), Decimal("120.00"), "CAD")
    assert _analysis_failure(error) == "Fail: Statement credit total (CA$100.00 listed, CA$120.00 printed) contradiction"
    forged = RuntimeError("Fail: Statement debit total ($1.00 listed, $2.00 printed) contradiction")
    assert "message withheld" in _analysis_failure(forged)


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


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_dashboard_shows_the_contradiction_as_the_statements_failure():
    source_js = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

    def function(name):
        return source_js[source_js.index(f"function {name}("):].split("\n}\n")[0] + "\n}\n"

    harness = """
let currentAnalysis = null;
const els = {};
for (const key of ["statusBanner", "statusMark", "statusCopy", "validationValue", "statusHeading", "summaryBox",
                   "decisionPill", "statusList"]) els[key] = {textContent: "", className: "", innerHTML: ""};
function setInitialState() {}
function setProgress() {}
function escapeHtml(value) { return String(value); }
""" + "".join(function(name) for name in ("setBanner", "statusRowHtml", "setStatusRows", "friendlyAnalysisError",
                                          "sourceContradiction", "renderExtractionReview"))
    results = []
    for message in ("Fail: Statement debit total ($150.00 listed, $250.00 printed) contradiction",
                    "visual pair gate refused the document"):
        script = harness + f"""
renderExtractionReview({json.dumps(message)});
console.log(JSON.stringify({{heading: els.statusHeading.textContent, banner: els.statusCopy.textContent,
                            pill: els.decisionPill.textContent, state: els.statusBanner.className}}));
"""
        run = subprocess.run([NODE, "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=15)
        assert run.returncode == 0, run.stderr
        results.append(json.loads(run.stdout))
    failed, held = results
    assert failed["heading"] == "Fail: Statement debit total ($150.00 listed, $250.00 printed) contradiction"
    assert failed["pill"] == "fail" and "error" in failed["state"] and "does not add up" in failed["banner"]
    assert held["heading"] == "Extraction needs review" and held["pill"] == "review required"

"""Fabricated text only. What a page shows in print, from sources other than the reviewer: the PDF's own text
layer and the proposer's reading. Used to settle a reviewer that contradicts itself and to keep a figure the
reviewer reports only when it is printed.
"""
import copy
from decimal import Decimal

from vlm.assemble import Block, CandidateRow
from vlm.native_text import PrintedEvidence, layout_text
from vlm.review import candidate_records, merge_review
from vlm.schema import empty_review

NATIVE = """FABRICATED SAVINGS BANK
Statement period 2031-01-01 to 2031-01-31
Beginning balance 1,000.00   Deposits and credits 2,500.00   Ending balance 3,275.50
01/02 ACH CREDIT FABRICATED PAYROLL, INC. 2,500.00
01/05 CARD PURCHASE FABRICATED HARDWARE STORE #12 224.50
Service charge 0.00   Days in period 31   Credits 1
"""


def _row(description, amount="2500.00", index=0):
    return CandidateRow("2031-01-02", "01/02", description, Decimal(amount), "credit", None, 1, "stage_a",
                        f"b1t0r{index}", "column", (0.1, 0.2, 0.9, 0.3), Decimal(amount))


def _payload(rows, **reviews):
    value = empty_review("statement_page")
    value["reviews"] = [{"candidate_id": record["candidate_id"], "verdict": "confirm",
                         "observed_description": record["row"]["description"], "corrections": [], "reason": ""}
                        for record in candidate_records(rows)]
    for index, update in reviews.items():
        value["reviews"][int(index[1:])].update(update)
    return value


def test_printed_amounts_integers_and_descriptions():
    printed = PrintedEvidence(native=NATIVE)
    assert printed.amount_printed(3275.5) and printed.amount_printed("1000") and printed.amount_printed(0)
    assert not printed.amount_printed(3257.50)
    assert printed.integer_printed(31) and not printed.integer_printed(45)
    assert printed.description_printed("ACH CREDIT  FABRICATED PAYROLL, INC.") is True
    assert printed.description_printed("ACH CREDIT FABRICATED PAYROLL INC") is False      # punctuation counts
    assert PrintedEvidence(native=None, proposer="x").description_printed("x") is None     # no text layer


def test_the_proposer_reading_counts_for_figures_but_never_for_descriptions():
    proposer = layout_text([Block("Table", None, "<table><tr><td>Total fees</td><td>12.75</td></tr></table>", 0, 1)])
    printed = PrintedEvidence(native=None, proposer=proposer)
    assert printed.amount_printed(12.75)
    assert printed.description_printed("Total fees") is None


def test_a_self_contradicting_punctuation_correction_is_settled_by_the_text_layer():
    # The reviewer "corrects" punctuation but its own observation repeats the proposer's reading.
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows, r0={"verdict": "correct", "observed_description": "ACH CREDIT FABRICATED PAYROLL, INC.",
                                 "corrections": [{"field": "description", "original": "ACH CREDIT FABRICATED PAYROLL, INC.",
                                                  "corrected": "ACH CREDIT FABRICATED PAYROLL INC."}]})
    unsettled = merge_review(rows, copy.deepcopy(payload), page=1)
    assert unsettled.counts["unresolved"] == 1
    settled = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=NATIVE))
    assert settled.counts == {"agreed": 1, "corrected": 0, "added": 0, "rejected": 0, "unresolved": 0}
    assert settled.rows[0].description == "ACH CREDIT FABRICATED PAYROLL, INC."
    evidence = settled.evidence[0]
    assert evidence["resolution"] == {"method": "text_layer", "chosen": "proposer",
                                      "resolved_errors": ["review_description_observation_mismatch"]}


def test_a_confirm_whose_observation_is_the_printed_reading_becomes_a_correction():
    rows = [_row("CARD PURCHASE FABRICATED HARDWARE STOR #12", "224.50")]
    payload = _payload(rows, r0={"observed_description": "CARD PURCHASE FABRICATED HARDWARE STORE #12"})
    settled = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=NATIVE))
    assert settled.counts["corrected"] == 1 and settled.rows[0].description == "CARD PURCHASE FABRICATED HARDWARE STORE #12"
    assert settled.evidence[0]["resolution"]["chosen"] == "reviewer_observation"


def test_the_fuller_printed_reading_wins_when_one_contains_the_other():
    rows = [_row("CARD PURCHASE FABRICATED HARDWARE STORE #12", "224.50")]
    payload = _payload(rows, r0={"observed_description": "CARD PURCHASE FABRICATED HARDWARE"})
    settled = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=NATIVE))
    assert settled.counts["agreed"] == 1 and settled.evidence[0]["resolution"]["chosen"] == "proposer"


def test_no_text_layer_or_no_single_printed_reading_leaves_the_row_unresolved():
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows, r0={"observed_description": "SOMETHING NOT PRINTED"})
    assert merge_review(rows, copy.deepcopy(payload), page=1,
                        printed=PrintedEvidence(native=None, proposer=NATIVE)).counts["unresolved"] == 1
    neither = _payload([_row("NOT PRINTED EITHER")], r0={"observed_description": "NOR THIS"})
    assert merge_review([_row("NOT PRINTED EITHER")], neither, page=1,
                        printed=PrintedEvidence(native=NATIVE)).counts["unresolved"] == 1


def test_only_a_description_mismatch_is_ever_settled():
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows, r0={"observed_description": "ACH CREDIT FABRICATED PAYROLL, INC.", "verdict": "correct",
                                 "corrections": [{"field": "amount", "original": 2500.0, "corrected": -5.0}]})
    merged = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=NATIVE))
    assert merged.counts["unresolved"] == 1 and "resolution" not in merged.evidence[0]


def test_figures_not_printed_are_dropped_not_held():
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows)
    payload["account"].update(beginning_balance=1000.0, ending_balance=3275.5, stated_total_credits=2750.0,
                              stated_credit_count=1, days_in_period=45, stated_service_charge=0.0)
    payload["daily_balances"] = [{"date": "2031-01-02", "balance": 3500.0}, {"date": "2031-01-05", "balance": 3275.5}]
    merged = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=NATIVE))
    assert merged.account["beginning_balance"] == 1000.0 and merged.account["ending_balance"] == 3275.5
    assert merged.account["stated_total_credits"] is None and merged.account["days_in_period"] is None
    assert merged.account["stated_credit_count"] == 1 and merged.account["stated_service_charge"] == 0.0
    assert merged.daily_balances == ({"date": "2031-01-05", "balance": 3275.5},)
    assert merged.metadata_evidence == ()
    codes = {(item.get("field") or item.get("index"), item["code"]) for item in merged.diagnostics}
    assert ("stated_total_credits", "review_figure_not_printed") in codes
    assert ("days_in_period", "review_figure_not_printed") in codes
    assert (0, "review_daily_balance_not_printed") in codes


def test_without_printed_evidence_nothing_changes():
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows)
    payload["account"].update(stated_total_credits=2750.0)
    assert merge_review(rows, payload, page=1).account["stated_total_credits"] == 2750.0

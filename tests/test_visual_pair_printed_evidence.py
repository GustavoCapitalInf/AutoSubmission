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


def test_settling_reads_only_the_lines_that_carry_the_rows_own_amount():
    # Review finding F1: "1234" is printed on the page (another cheque), but not on the line of this 45.10 row.
    native = "Check Nbr Date Amount\n123 03/05 45.10\n1234 03/06 300.00\n"
    rows = [CandidateRow("2031-03-05", "03/05", "123", Decimal("45.10"), "debit", None, 1, "stage_a", "b1t0r1",
                         "column", (0.1, 0.2, 0.9, 0.3), None)]
    payload = _payload(rows, r0={"observed_description": "1234"})
    settled = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=native))
    assert settled.counts["agreed"] == 1 and settled.rows[0].description == "123"


def test_a_word_printed_elsewhere_on_the_page_never_settles_a_row():
    # Neither reading is printed on the row's own line: the proposer's has a stray period, and the reviewer's
    # observation is a heading word printed elsewhere. The row stays unresolved.
    native = "DEPOSIT ACCOUNT STATEMENT\n03/02 ONLINE TRANSFER FROM SAVINGS 0001 1,000.00\n"
    rows = [_row("ONLINE TRANSFER FROM SAVINGS 0001.", "1000.00")]
    payload = _payload(rows, r0={"observed_description": "DEPOSIT"})
    merged = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=native))
    assert merged.counts["unresolved"] == 1 and "resolution" not in merged.evidence[0]


def test_a_wrapped_description_is_read_across_the_amount_column_on_its_own_lines():
    # The description wraps to the next line and the text layer prints the amount between its two parts; only
    # money and date tokens may be skipped, and the reading must touch the line that prints the amount.
    native = "03/02 ONLINE TRANSFER TO 1,000.00\nFABRICATED SAVINGS 0001\n"
    rows = [_row("ONLINE TRANSFER TO", "1000.00")]
    payload = _payload(rows, r0={"observed_description": "ONLINE TRANSFER TO FABRICATED SAVINGS 0001"})
    merged = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=native))
    assert merged.counts["corrected"] == 1
    assert merged.rows[0].description == "ONLINE TRANSFER TO FABRICATED SAVINGS 0001"
    printed = PrintedEvidence(native=native)
    assert printed.description_printed_near("ONLINE TO", Decimal("1000.00")) is False   # a word may not be skipped
    assert printed.description_words_near("ONLINE TRANSFER TO FABRICATED SAVINGS 0001", Decimal("1000.00")) is True


MULTI_LINE = """Apr 29 Wire Transfer Fee 2900000001 40.00-
Apr 29 Wire Debit REF000001
BNF=FABRICATED PAYEE CO
FAKEBANK NYC 260429FAB01
12 FABRICATED STREET WEST
2,500.00-
Apr 30 Wire Debit REF000002
BNF=OTHER FABRICATED CO
90.00-
Apr 30 Monthly Maintenance Fee 3000000001 15.00-
"""


def test_a_description_over_several_lines_above_an_amount_line_of_its_own_is_its_rows_print():
    printed = PrintedEvidence(native=MULTI_LINE)
    full = "Wire Debit REF000001 BNF=FABRICATED PAYEE CO FAKEBANK NYC 260429FAB01 12 FABRICATED STREET WEST"
    assert printed.description_printed_near(full, Decimal("2500.00")) is True
    assert printed.description_words_near(full, Decimal("2500.00")) is True
    # A reading that stops short of the amount line, with unread text between, is not directly against it.
    assert printed.description_printed_near("Wire Debit REF000001 BNF=FABRICATED PAYEE CO", Decimal("2500.00")) is False


def test_a_rows_block_never_reaches_the_next_or_the_previous_row():
    printed = PrintedEvidence(native=MULTI_LINE)
    # The next row starts with its own date: its text is not printed as the 2,500.00 row.
    assert printed.description_printed_near("Wire Debit REF000002 BNF=OTHER FABRICATED CO", Decimal("2500.00")) is False
    assert printed.description_words_near("BNF=OTHER FABRICATED CO", Decimal("2500.00")) is False
    # Nor is the previous row's, whose line prints its own amount.
    assert printed.description_printed_near("Wire Transfer Fee 2900000001", Decimal("2500.00")) is False
    # A continuation printed above another row's own line of text does not belong to that row.
    neighbour = PrintedEvidence(native="01/02 FABRICATED A 100.00\nREF 123\n01/03 FABRICATED B 50.00\n")
    assert neighbour.description_printed_near("REF 123", Decimal("50.00")) is False
    assert neighbour.description_printed_near("FABRICATED A FABRICATED B", Decimal("50.00")) is False


def test_a_multi_line_row_the_reviewer_contradicts_itself_about_is_settled_by_its_block():
    # The proposer's reading keeps its line-break markup; the reviewer confirmed it but observed plain text.
    rows = [_row("Wire Debit REF000001<br>BNF=FABRICATED PAYEE CO", "2500.00")]
    observed = "Wire Debit REF000001 BNF=FABRICATED PAYEE CO FAKEBANK NYC 260429FAB01 12 FABRICATED STREET WEST"
    merged = merge_review(rows, _payload(rows, r0={"observed_description": observed}), page=1,
                          printed=PrintedEvidence(native=MULTI_LINE))
    assert merged.counts["corrected"] == 1 and merged.rows[0].description == observed
    assert merged.evidence[0]["resolution"]["chosen"] == "reviewer_observation"


def test_a_line_break_written_as_a_tag_or_a_newline_is_the_same_reading():
    # dots.mocr's Markdown grids write a line break inside a cell as "<br>"; the reviewer writes a newline.
    # Both are layout: the reviewer agrees with the proposer, and the ledger publishes one line.
    from vlm.native_text import spaced
    from vlm.pair import ledger_rows

    assert spaced("A<br>B<BR/>C <br /> D\nE") == "A B C D E"
    rows = [_row("ONLINE PAYMENT<br>FABRICATED CARD 0001", "2500.00")]
    payload = _payload(rows, r0={"observed_description": "ONLINE PAYMENT\nFABRICATED CARD 0001"})
    merged = merge_review(rows, payload, page=1)
    assert merged.counts["agreed"] == 1
    ledger, excluded = ledger_rows([merged])
    assert excluded == 0 and ledger[0].description == "ONLINE PAYMENT FABRICATED CARD 0001"
    # A different reading is still a contradiction.
    other = _payload(rows, r0={"observed_description": "ONLINE PAYMENT\nFABRICATED CARD 0002"})
    assert merge_review(rows, other, page=1).counts["unresolved"] == 1


def test_decimal_comma_with_space_thousands_is_money():
    printed = PrintedEvidence(native="Solde de fermeture 1 500,25\nDépôts 12 345,67\n")
    assert printed.amount_printed(1500.25) and printed.amount_printed(12345.67)


def test_amounts_in_the_text_layer_exclude_the_proposer_reading():
    printed = PrintedEvidence(native="01/02 PAYROLL 2,500.00", proposer="01/02 PAYROLL 2,600.00")
    assert printed.amount_printed(2600) and not printed.amount_in_text_layer(2600)
    assert printed.amount_in_text_layer(2500)
    assert PrintedEvidence(native=None, proposer="2,600.00").amount_in_text_layer(2600) is None


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


def test_a_whole_dollar_figure_printed_without_cents_is_printed():
    # "Average daily checking balance $1,813" prints no cents; the reviewer reports 1813.0.
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows)
    payload["account"].update(bank_reported_average_balance=1813.0, stated_interest_paid=4.0,
                              stated_service_charge=31.0)
    native = NATIVE + "Average daily checking balance $1,813\nPage 4 of 4\n"
    merged = merge_review(rows, payload, page=1, printed=PrintedEvidence(native=native))
    assert merged.account["bank_reported_average_balance"] == 1813.0
    # A bare integer on the page (a day of the period, a page number) is not a money figure (review 4).
    assert merged.account["stated_interest_paid"] is None and merged.account["stated_service_charge"] is None


def test_without_printed_evidence_nothing_changes():
    rows = [_row("ACH CREDIT FABRICATED PAYROLL, INC.")]
    payload = _payload(rows)
    payload["account"].update(stated_total_credits=2750.0)
    assert merge_review(rows, payload, page=1).account["stated_total_credits"] == 2750.0

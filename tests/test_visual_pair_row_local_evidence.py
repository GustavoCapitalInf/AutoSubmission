"""Fabricated text layers only. Which printed text is a row's own, the only evidence allowed to choose between
two readings of its description (review rounds on 4866821): never a neighbour that prints the same amount,
another column of a cheque line, the next row's text, or a heading."""
from decimal import Decimal

from vlm.assemble import CandidateRow
from vlm.native_text import _ROW_START, PrintedEvidence
from vlm.review import candidate_records, merge_review, picture_page
from vlm.schema import empty_review


def _row(description, amount, *, date="2031-01-03", date_text=None):
    return CandidateRow(date, date_text or date[5:].replace("-", "/"), description, Decimal(amount), "debit", None,
                        1, "stage_a", "b1t0r0", "column", (0.1, 0.2, 0.9, 0.3), None)


def _settle(rows, native, observed):
    payload = empty_review("statement_page")
    payload["reviews"] = [{"candidate_id": record["candidate_id"], "verdict": "confirm",
                           "observed_description": observed, "corrections": [], "reason": ""}
                          for record in candidate_records(rows)]
    return merge_review(rows, payload, page=1, printed=PrintedEvidence(native=native))


def test_a_row_whose_amount_a_neighbour_also_prints_is_told_apart_by_its_date():
    twins = "FABRICATED BANK STATEMENT\n01/02 FABRICATED GYM MEMBERSHIP 15.00 985.00\n" \
            "01/03 FABRICATED STREAMING SERVICE 15.00 970.00\n"
    # The reviewer observed the neighbour's text for this 15.00 row: not this row's print.
    merged = _settle([_row("FABRICATED STREAMING SERVICES", "15.00")], twins, "FABRICATED GYM MEMBERSHIP")
    assert merged.counts["unresolved"] == 1
    # Its own reading is found on its own line, told apart by the date.
    printed = PrintedEvidence(native=twins)
    assert printed.description_printed_near("FABRICATED STREAMING SERVICE", Decimal("15.00"), "01/03") is True
    assert printed.description_printed_near("FABRICATED GYM MEMBERSHIP", Decimal("15.00"), "01/03") is False
    # Without a date that tells them apart, no reading is chosen at all.
    assert printed.description_printed_near("FABRICATED GYM MEMBERSHIP", Decimal("15.00"), None) is None
    same_day = PrintedEvidence(native="01/03 FABRICATED A 15.00\n01/03 FABRICATED B 15.00\n")
    assert same_day.description_printed_near("FABRICATED A", Decimal("15.00"), "01/03") is None


def test_a_neighbours_balance_equal_to_the_rows_amount_is_not_the_rows_line():
    balances = "01/02 FABRICATED DEPOSIT 500.00 600.00\n01/03 FABRICATED WITHDRAWAL 600.00 0.00\n"
    merged = _settle([_row("FABRICATED WITHDRAWL", "600.00")], balances, "FABRICATED DEPOSIT")
    assert merged.counts["unresolved"] == 1
    printed = PrintedEvidence(native=balances)
    assert printed.description_printed_near("FABRICATED WITHDRAWAL", Decimal("600.00"), "01/03") is True


def test_each_cheque_of_a_multi_column_line_owns_only_its_own_segment():
    two = "Checks Paid\nCheck Nbr Date Amount Check Nbr Date Amount\n123 03/05 45.10 1234 03/06 300.00\n"
    row = _row("123", "45.10", date="2031-03-05")
    merged = _settle([row], two, "1234")
    assert merged.counts["agreed"] == 1 and merged.rows[0].description == "123"   # the exact print wins
    three = "123 03/05 45.10 124 * 03/06 300.00 125 03/07 12.00\n"
    merged = _settle([_row("124*", "300.00", date="2031-03-06")], three, "125")
    assert merged.counts["unresolved"] == 1
    printed = PrintedEvidence(native=three)
    assert printed.description_printed_near("124 *", Decimal("300.00"), "03/06") is True
    assert printed.description_printed_near("125", Decimal("300.00"), "03/06") is False


def test_a_fragment_is_inside_a_fuller_reading_only_as_whole_words():
    # "123" and "1234" both printed on the row's own line: neither contains the other, so neither is chosen.
    merged = _settle([_row("123", "45.10", date="2031-03-05")], "1234 123 03/05 45.10\n", "1234")
    assert merged.counts["unresolved"] == 1


def test_a_column_ordered_text_layer_settles_no_row():
    column_major = "Date Description Amount\n04/29\n04/30\nWire Debit REF000001\nWire Debit REF000002\n" \
                   "2,500.00-\n90.00-\n"
    printed = PrintedEvidence(native=column_major)
    for reading in ("Wire Debit REF000001", "Wire Debit REF000002"):
        assert printed.description_printed_near(reading, Decimal("2500.00"), "04/29") is False
    merged = _settle([_row("Wire Debit REF000001", "2500.00", date="2031-04-29")], column_major,
                     "Wire Debit REF000002")
    assert merged.counts["unresolved"] == 1


def test_text_after_a_date_and_amount_line_is_the_next_rows():
    layout = "Wire Debit REF000001\nBNF=FABRICATED PAYEE CO\n04/29 2,500.00-\nWire Debit REF000002\n" \
             "BNF=OTHER FABRICATED CO\n04/30 90.00-\n"
    printed = PrintedEvidence(native=layout)
    other = "Wire Debit REF000002 BNF=OTHER FABRICATED CO"
    assert printed.description_printed_near(other, Decimal("2500.00"), "04/29") is False
    assert printed.description_words_near(other, Decimal("2500.00"), "04/29") is False


def test_a_heading_against_a_figures_only_line_is_not_the_rows_print():
    above = PrintedEvidence(native="Checks Paid\nCheck Nbr Date Amount\n123 03/05 45.10\n1234 03/06 300.00\n")
    assert above.description_printed_near("Check Nbr Date Amount", Decimal("45.10"), "03/05") is False
    below = "Apr 30 Wire Debit REF000002\nBNF=OTHER FABRICATED CO\n90.00-\nDeposits and Other Credits\n" \
            "Continued on next page\n"
    printed = PrintedEvidence(native=below)
    assert printed.description_printed_near("Deposits and Other Credits", Decimal("90.00"), "Apr 30") is False
    merged = _settle([_row("Wire Debit REF000002 BNF=OTHER FABRICATD CO", "90.00", date="2031-04-30",
                           date_text="Apr 30")], below, "Deposits and Other Credits")
    assert merged.counts["unresolved"] == 1


def test_a_small_amount_on_a_line_of_its_own_is_not_a_date():
    for amount_line in ("90.00", "90.00-"):
        printed = PrintedEvidence(native=f"Apr 30 Wire Debit REF000002\nBNF=OTHER FABRICATED CO\n{amount_line}\n")
        text = "Wire Debit REF000002 BNF=OTHER FABRICATED CO"
        assert printed.description_printed_near(text, Decimal("90.00"), "Apr 30") is True
        assert printed.description_words_near(text, Decimal("90.00"), "Apr 30") is True
    assert not any(_ROW_START.match(token) for token in ("90.00", "15.00", "5.00", "0.25"))
    assert all(_ROW_START.match(text) for text in ("Apr 29, 2026 Wire Debit", "02.03.2026 FABRICATED",
                                                   "03/02 FABRICATED", "29 avr. FABRICATED"))


def test_a_count_or_day_number_a_reviewer_repeats_does_not_make_a_picture_page_a_statement_page():
    printed = PrintedEvidence(native="FABRICATED CHEQUE IMAGES PAGE\nCheck 123 Check 124\n")
    for field, value in (("days_in_period", 31), ("stated_nsf_count", 0)):
        payload = empty_review("cheque_images")
        payload["account"][field] = value
        merged = merge_review([], payload, page=3, printed=printed)
        assert any(item["code"] == "review_figure_not_printed" for item in merged.diagnostics)
        assert picture_page(merged) is True
    # A money figure it reports that the page does not print still says it saw a statement page.
    payload = empty_review("cheque_images")
    payload["account"]["ending_balance"] = 1234.56
    assert picture_page(merge_review([], payload, page=3, printed=printed)) is False

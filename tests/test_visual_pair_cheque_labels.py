"""Fabricated tables only. A cheque listed in a cheque-number column is named the way the statement names the
column: the printed label ("Check", from a "Check Nbr" heading) followed by the number, as the production
parsers write it ("Check 1234", "CHECK 1234"). The analysis counts cheques by that word. The label rides on
the row as structure and is applied to the ledger after review, because the reviewer rightly reads only the
number in the cell."""
from decimal import Decimal

from vlm.assemble import CandidateRow, labelled_description, rows_from_grid
from vlm.pair import ledger_rows
from vlm.review import PageReviewMerge, candidate_records, merge_review
from vlm.schema import empty_review
from vlm.tables import classify_columns


def _rows(header, *body):
    grid = [list(header), *[list(row) for row in body]]
    return rows_from_grid(grid, classify_columns(grid), page=1, table_index=0, year_hint=2031)


def test_a_cheque_number_column_labels_its_rows_with_the_printed_word():
    for heading, word in (("Check Nbr", "Check"), ("Check No.", "Check"), ("CHECK #", "CHECK"),
                          ("Cheque Number", "Cheque"), ("Chk No", "Chk")):
        rows = _rows((heading, "Date", "Amount"), ("1234", "01/05", "45.10"), ("1236*", "01/07", "300.00"))
        assert [row.description for row in rows] == ["1234", "1236*"], heading
        assert {row.description_label for row in rows} == {word}, heading


def test_other_tables_carry_no_label():
    assert {row.description_label for row in _rows(("Description", "Date", "Amount"), ("1234", "01/05", "45.10"))} == {None}
    two_text_columns = _rows(("Check Nbr", "Payee", "Date", "Amount"), ("1234", "FABRICATED PAYEE", "01/05", "45.10"))
    assert {row.description_label for row in two_text_columns} == {None}


def test_the_label_names_only_a_bare_cheque_number():
    base = CandidateRow("2031-01-05", "01/05", "1234", Decimal("45.10"), "debit", None, 1, "stage_a", "t0r1",
                        description_label="Check")
    assert labelled_description(base).description == "Check 1234"
    assert labelled_description(CandidateRow(**{**base.__dict__, "description": "#1236*"})).description == "Check #1236*"
    assert labelled_description(CandidateRow(**{**base.__dict__, "description": "FABRICATED PAYEE"})).description == "FABRICATED PAYEE"
    assert labelled_description(CandidateRow(**{**base.__dict__, "description_label": None})).description == "1234"


def test_the_bank_reader_is_offered_the_labelled_description_the_ledger_carries():
    # Review finding F7: the bank-reader bridge compares its reading with the gated statement; offering it the
    # bare number while the statement says "Check 1234" meant a cheque table could never match.
    from vlm.pair import _markdown_page
    rows = _rows(("Check Nbr", "Date", "Amount"), ("1234", "01/05", "45.10"))
    merged = PageReviewMerge(1, tuple(rows), (), {"agreed": 1}, (), {}, (), "statement_page", ())
    assert "<td>Check 1234</td>" in _markdown_page(merged)


def test_the_label_survives_a_correction_and_reaches_the_ledger():
    rows = _rows(("Check Nbr", "Date", "Amount"), ("1234", "01/05", "45.10"), ("1235", "01/06", "12.00"))
    payload = empty_review("statement_page")
    records = candidate_records(rows)
    payload["reviews"] = [
        {"candidate_id": records[0]["candidate_id"], "verdict": "confirm", "observed_description": "1234",
         "corrections": [], "reason": ""},
        {"candidate_id": records[1]["candidate_id"], "verdict": "correct", "observed_description": "1235",
         "corrections": [{"field": "amount", "original": 12.0, "corrected": 21.0}], "reason": "misread"}]
    merged = merge_review(rows, payload, page=1)
    assert merged.counts["agreed"] == 1 and merged.counts["corrected"] == 1
    ledger, _ = ledger_rows([merged])
    assert [row.description for row in ledger] == ["Check 1234", "Check 1235"]
    assert [row.amount for row in ledger] == [Decimal("45.10"), Decimal("21.0")]


def test_a_break_in_sequence_mark_before_the_number_is_part_of_a_bare_cheque_number():
    base = CandidateRow("2031-01-05", "01/05", "*218", Decimal("45.10"), "debit", None, 1, "stage_a", "t0r1",
                        description_label="CHECK")
    assert labelled_description(base).description == "CHECK *218"
    rows = _rows(("DATE", "CHECK #", "AMOUNT($)"), ("01/05", "*218", "45.10"))
    assert [(row.description, row.description_label) for row in rows] == [("*218", "CHECK")]


def test_a_copy_of_the_rows_own_date_in_front_of_its_description_is_not_its_description():
    from dataclasses import replace

    from vlm.assemble import published_row
    base = CandidateRow("2031-01-05", "01/05", "01/05 1234", Decimal("45.10"), "debit", None, 1, "stage_b", "t0r1",
                        description_label="Check")
    assert published_row(base).description == "Check 1234"
    other_date = replace(base, description="01/04 FABRICATED TRANSFER", description_label=None)
    assert published_row(other_date).description == "01/04 FABRICATED TRANSFER"
    only_date = replace(base, description="01/05", description_label=None)
    assert published_row(only_date).description == "01/05"

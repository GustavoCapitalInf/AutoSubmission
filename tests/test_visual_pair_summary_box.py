"""Fabricated text only. The printed account summary as a proof.

Many banks print no "total credits" line: the summary lists categories (customer deposits, other deposits,
withdrawals, checks, fees) between the beginning and the ending balance, and each section prints its own
subtotal. A reviewer asked for one total either invents it or picks a section subtotal. When every category
line of a page's summary satisfies beginning + credits - debits = ending exactly, the summary is proven, and
the statement's totals and counts are the sums of its printed lines: arithmetic by the application, never by
a model. A summary that does not balance proves nothing and changes nothing.
"""
from decimal import Decimal

from vlm.assemble import Block
from vlm.summary_box import page_lines, prove_summary_box

US_STYLE = """FABRICATED DEPOSIT ACCOUNT
Account Summary
Beginning Balance on Jan 1 1,000.00
Customer Deposits 5 2,000.00
Other Deposits 1 10,000.50
Other Withdrawals 32 11,500.25-
Ending Balance on Jan 31 1,500.25
Total Customer Deposits 2,000.00
"""


def test_a_balanced_category_summary_is_proven_and_totals_are_its_sums():
    proof = prove_summary_box([US_STYLE], beginning=Decimal("1000.00"), ending=Decimal("1500.25"))
    assert proof is not None
    assert proof.page == 1
    assert proof.stated_total_credits == Decimal("12000.50") and proof.stated_total_debits == Decimal("11500.25")
    assert proof.stated_credit_count == 6 and proof.stated_debit_count == 32
    assert proof.line_count == 3


def test_signs_come_from_the_printed_minus_or_from_the_category_word():
    text = """Previous Balance 500.00
Deposits and Other Credits 3 900.00
Checks Paid 2 150.00
Service Charges 1 10.00
New Balance 1,240.00
"""
    proof = prove_summary_box([text], beginning=Decimal("500"), ending=Decimal("1240"))
    assert proof.stated_total_credits == Decimal("900.00") and proof.stated_total_debits == Decimal("160.00")
    assert proof.stated_debit_count == 3


def test_an_unbalanced_summary_proves_nothing():
    unbalanced = US_STYLE.replace("10,000.50", "10,000.60")
    assert prove_summary_box([unbalanced], beginning=Decimal("1000.00"), ending=Decimal("1500.25")) is None


def test_the_summary_must_be_this_statements():
    # A box printed for another period (or account) balances on its own figures, not on this statement's.
    assert prove_summary_box([US_STYLE], beginning=Decimal("900.00"), ending=Decimal("1500.25")) is None
    assert prove_summary_box([US_STYLE], beginning=None, ending=Decimal("1500.25")) is None


def test_the_box_is_the_run_of_lines_around_the_balances_not_the_whole_page():
    # A text layer can print the ending balance before the beginning, and the page's own transaction section
    # (with lines that look like categories) follows the box.
    text = """Ending Balance on Jan 31 1,500.25
Total Customer Deposits 2,000.00
Beginning Balance on Jan 1 1,000.00
Customer Deposits 5 2,000.00
Other Deposits 1 10,000.50
Other Withdrawals 32 11,500.25-
Customer Deposits
Mobile Deposit 400.00
Branch Deposit 1,600.00
"""
    proof = prove_summary_box([text], beginning=Decimal("1000.00"), ending=Decimal("1500.25"))
    assert proof is not None and proof.line_count == 3 and proof.stated_total_credits == Decimal("12000.50")


def test_a_transaction_line_inside_an_unfinished_box_means_no_box():
    text = """Beginning Balance 1,000.00
01/05 CARD PURCHASE FABRICATED 20.00
Withdrawals 1 20.00
Ending Balance 980.00
"""
    assert prove_summary_box([text], beginning=Decimal("1000"), ending=Decimal("980")) is None


def test_a_box_whose_lines_mix_printed_counts_proves_nothing():
    # Review finding F2: two keyworded lines printed right under the box (no counts) cancel out, so the box
    # still balances with them absorbed and would "prove" totals 50.00 too high on each side.
    text = """Beginning Balance 10,000.00
Deposits and Other Credits 1 6,000.00
Withdrawals and Other Debits 2 5,000.00
Ending Balance 11,000.00
Overdraft Fees 50.00
Deposits Returned 50.00
"""
    assert prove_summary_box([text], beginning=Decimal("10000"), ending=Decimal("11000")) is None


def test_a_proof_never_supersedes_reviewer_totals_that_balance_on_their_own():
    from vlm.pair import apply_summary_box
    # Two different readings both balance the statement: the reviewer's printed figures stand and the proof is
    # not applied (the gate then checks the ledger against them).
    text = """Beginning Balance 10,000.00
Deposits and Other Credits 6,000.00
Withdrawals and Other Debits 5,000.00
Ending Balance 11,000.00
Overdraft Fees 50.00
Deposits Returned 50.00
"""
    account = {"beginning_balance": 10000.0, "ending_balance": 11000.0,
               "stated_total_credits": 6000.0, "stated_total_debits": 5000.0}
    reasons, occurrences, evidence = [], [], []
    audit = apply_summary_box(account, reasons, occurrences, evidence, [text])
    assert account["stated_total_credits"] == 6000.0 and account["stated_total_debits"] == 5000.0
    categories = audit.pop("categories")
    assert audit == {"proven": True, "applied": False, "reason": "reviewer_totals_also_balance",
                     "page": 1, "category_lines": 4}
    assert [item["label"] for item in categories] == ["Deposits and Other Credits", "Withdrawals and Other Debits",
                                                      "Overdraft Fees", "Deposits Returned"]
    assert evidence == []


def test_a_box_prints_counts_on_every_line_or_on_none():
    # One line without a count among counted lines is not the box's own line (see the mixed-counts test).
    mixed = US_STYLE.replace("Customer Deposits 5 2,000.00", "Customer Deposits 2,000.00")
    assert prove_summary_box([mixed], beginning=Decimal("1000.00"), ending=Decimal("1500.25")) is None
    uncounted = (US_STYLE.replace("Customer Deposits 5 2,000.00", "Customer Deposits 2,000.00")
                 .replace("Other Deposits 1 10,000.50", "Other Deposits 10,000.50")
                 .replace("Other Withdrawals 32 11,500.25-", "Other Withdrawals 11,500.25-"))
    proof = prove_summary_box([uncounted], beginning=Decimal("1000.00"), ending=Decimal("1500.25"))
    assert proof is not None and proof.stated_credit_count is None and proof.stated_debit_count is None
    assert proof.stated_total_credits == Decimal("12000.50")


def test_totals_balances_and_undirected_lines_are_never_category_lines():
    # "Total ..." lines, balances and a line naming both directions without a sign are not categories; without
    # a direction the box cannot be proven from them.
    text = """Beginning Balance 100.00
Deposits and Withdrawals 50.00
Ending Balance 150.00
"""
    assert prove_summary_box([text], beginning=Decimal("100"), ending=Decimal("150")) is None


def test_a_proven_box_supplies_the_totals_and_settles_reviewer_disagreements():
    from vlm.pair import apply_summary_box
    # The reviewer took a section subtotal for the statement's credits total on one page and printed a
    # conflicting figure on another; the proven box settles both.
    account = {"beginning_balance": 1000.0, "ending_balance": 1500.25, "stated_total_credits": 10000.5,
               "stated_total_debits": 11500.25}
    reasons = ["anchor_disagreement", "count_mismatch"]
    occurrences = [{"code": "anchor_disagreement", "page": 3, "field": "stated_total_credits", "source": "metadata"},
                   {"code": "count_mismatch", "page": None, "field": None, "source": "gate"}]
    evidence = []
    audit = apply_summary_box(account, reasons, occurrences, evidence, [US_STYLE])
    assert account["stated_total_credits"] == 12000.5 and account["stated_credit_count"] == 6
    assert reasons == ["count_mismatch"] and [item["code"] for item in occurrences] == ["count_mismatch"]
    assert audit == {"proven": True, "applied": True, "page": 1, "category_lines": 3,
                     "fields": ["stated_credit_count", "stated_debit_count", "stated_total_credits",
                                "stated_total_debits"],
                     "superseded_reviewer_fields": ["stated_total_credits"], "settled_disagreements": 1,
                     "counts_from_summary_page": [],
                     "categories": [{"label": "Customer Deposits", "direction": "credit", "amount": 2000.0},
                                    {"label": "Other Deposits", "direction": "credit", "amount": 10000.5},
                                    {"label": "Other Withdrawals", "direction": "debit", "amount": 11500.25}]}
    assert {"field": "stated_total_credits", "page": 1, "source": "summary_box", "value": 12000.5} in evidence


def test_a_count_read_on_the_proven_summary_page_stands_over_a_sections_count_read_elsewhere():
    from vlm.pair import apply_summary_box
    # The box prints no counts. The reviewer read the statement's debit count on the summary page (page 1) and,
    # on a cheques page, that section's own count as the statement's: page 1's count stands and the gate
    # checks it against the ledger.
    uncounted = (US_STYLE.replace("Customer Deposits 5 2,000.00", "Customer Deposits 2,000.00")
                 .replace("Other Deposits 1 10,000.50", "Other Deposits 10,000.50")
                 .replace("Other Withdrawals 32 11,500.25-", "Other Withdrawals 11,500.25-"))
    account = {"beginning_balance": 1000.0, "ending_balance": 1500.25, "stated_debit_count": 32}
    reasons = ["anchor_disagreement"]
    occurrences = [{"code": "anchor_disagreement", "page": 3, "field": "stated_debit_count", "source": "metadata"}]
    evidence = [{"field": "stated_debit_count", "page": 1, "source": "reviewer", "value": 32},
                {"field": "stated_debit_count", "page": 3, "source": "reviewer", "value": 4}]
    audit = apply_summary_box(account, reasons, occurrences, evidence, [uncounted])
    assert account["stated_debit_count"] == 32 and reasons == [] and occurrences == []
    assert audit["counts_from_summary_page"] == ["stated_debit_count"]
    # A count the summary page did not print (read only elsewhere) is not settled: the disagreement holds.
    account = {"beginning_balance": 1000.0, "ending_balance": 1500.25, "stated_debit_count": 4}
    reasons = ["anchor_disagreement"]
    occurrences = [{"code": "anchor_disagreement", "page": 5, "field": "stated_debit_count", "source": "metadata"}]
    evidence = [{"field": "stated_debit_count", "page": 3, "source": "reviewer", "value": 4},
                {"field": "stated_debit_count", "page": 5, "source": "reviewer", "value": 9}]
    audit = apply_summary_box(account, reasons, occurrences, evidence, [uncounted])
    assert reasons == ["anchor_disagreement"] and audit["counts_from_summary_page"] == []


def test_nothing_changes_without_a_proof():
    from vlm.pair import apply_summary_box
    account = {"beginning_balance": 1000.0, "ending_balance": 9999.0, "stated_total_credits": 10000.5}
    reasons = ["anchor_disagreement"]
    assert apply_summary_box(account, reasons, [], [], [US_STYLE]) is None
    assert account["stated_total_credits"] == 10000.5 and reasons == ["anchor_disagreement"]


def test_a_table_read_by_the_proposer_gives_one_line_per_row():
    blocks = [Block("Table", None, "<table><tr><td>Beginning Balance</td><td>1,000.00</td></tr>"
                                   "<tr><td>Deposits</td><td>3</td><td>600.00</td></tr>"
                                   "<tr><td>Withdrawals</td><td>2</td><td>100.00-</td></tr>"
                                   "<tr><td>Ending Balance</td><td>1,500.00</td></tr></table>", 0, 1)]
    lines = page_lines(None, blocks)
    assert "Deposits 3 600.00" in lines
    proof = prove_summary_box(["\n".join(lines)], beginning=Decimal("1000"), ending=Decimal("1500"))
    assert proof is not None and proof.stated_total_credits == Decimal("600.00")


# A box that prints each line's arithmetic sign after its figure, as some banks do. The ending is overdrawn:
# 2,000.00 + 5,000.00 + 0.00 + 900.00 - 6,500.00 - 40.00 - 1,700.00 = -340.00, printed "$340.00 -".
SIGNED_STYLE = """FABRICATED BUSINESS CHECKING
SUMMARY
Beginning Balance $2,000.00
Deposits & Credits $5,000.00 +
Withdrawals $6,500.00 -
Fees $40.00 -
Automatic Transfers $0.00 +
Returned Checks $900.00 +
Checks $1,700.00 -
Ending Balance $340.00 -
Minimum Daily Balance $1,200 -
Average Monthly Statement Balance $800
"""


def test_a_sign_printed_after_the_figure_is_the_lines_direction_whatever_its_words():
    proof = prove_summary_box([SIGNED_STYLE], beginning=Decimal("2000"), ending=Decimal("-340"))
    assert proof is not None and proof.line_count == 6
    assert proof.stated_total_credits == Decimal("5900.00") and proof.stated_total_debits == Decimal("8240.00")
    # "Returned Checks ... +" adds to the balance although "checks" is a debit word; "Automatic Transfers"
    # names no direction and its printed sign makes it a category.
    assert ("Returned Checks", "credit", Decimal("900.00")) in proof.categories
    assert ("Automatic Transfers", "credit", Decimal("0.00")) in proof.categories
    assert proof.ending_balance == Decimal("-340")


def test_a_balance_sign_the_reader_dropped_is_restored_only_by_a_box_that_balances_with_it():
    # The reader took the overdrawn "$340.00 -" for 340.00: only the printed sign balances the box.
    proof = prove_summary_box([SIGNED_STYLE], beginning=Decimal("2000"), ending=Decimal("340"))
    assert proof is not None and proof.ending_balance == Decimal("-340.00")
    # A box that does not balance with its printed signs either proves nothing.
    unbalanced = SIGNED_STYLE.replace("Fees $40.00 -", "Fees $41.00 -")
    assert prove_summary_box([unbalanced], beginning=Decimal("2000"), ending=Decimal("340")) is None
    # A figure printed negative and signed again cannot be told.
    doubled = SIGNED_STYLE.replace("Fees $40.00 -", "Fees -$40.00 -")
    assert prove_summary_box([doubled], beginning=Decimal("2000"), ending=Decimal("-340")) is None


def test_a_proven_signed_box_restores_the_ending_sign_and_the_totals():
    from vlm.pair import apply_summary_box
    # The reviewer read the first category of each side as the totals and the ending without its minus.
    account = {"beginning_balance": 2000.0, "ending_balance": 340.0, "stated_total_credits": 5000.0,
               "stated_total_debits": 6500.0}
    reasons, occurrences, evidence = [], [], []
    audit = apply_summary_box(account, reasons, occurrences, evidence, [SIGNED_STYLE])
    assert account["ending_balance"] == -340.0 and account["beginning_balance"] == 2000.0
    assert account["stated_total_credits"] == 5900.0 and account["stated_total_debits"] == 8240.0
    assert audit["superseded_reviewer_fields"] == ["ending_balance", "stated_total_credits", "stated_total_debits"]
    assert {"field": "ending_balance", "page": 1, "source": "summary_box", "value": -340.0} in evidence
    # Nothing changes when the box does not balance.
    account = {"beginning_balance": 2000.0, "ending_balance": 340.0}
    assert apply_summary_box(account, [], [], [], [SIGNED_STYLE.replace("$900.00 +", "$901.00 +")]) is None
    assert account["ending_balance"] == 340.0


SECTION_PAGE_1 = SIGNED_STYLE + """DEPOSITS & CREDITS
01/02 FABRICATED CUSTOMER DEPOSIT 5,000.00
Total Deposits & Credits $5,000.00
WITHDRAWALS
01/03 FABRICATED SUPPLIER PAYMENT 6,500.00
Total Withdrawals $6,500.00
FEES
01/05 FABRICATED ITEM FEE 40.00
Total Fees $40.00
RETURNED CHECKS
01/06 Credit-Returned Ck# 101 400.00
"""
SECTION_PAGE_2 = """RETURNED CHECKS (CONTINUED)
01/07 Credit-Returned Ck# 102 500.00
Total Returned Checks $900.00
CHECKS
Date Check No. Amount
01/04 101 400.00
01/04 102 500.00
01/05 103 800.00
Total Checks $1,700.00
"""


def _section_rows():
    from vlm.assemble import CandidateRow

    def row(page, locator, date_text, description, amount, direction):
        return CandidateRow(f"2031-{date_text.replace('/', '-')}", date_text, description, Decimal(amount), direction,
                            None, page, "stage_b", locator)
    # The returned cheque on page 1 was read as a cheque paid; its continuation on page 2 as a credit.
    return [row(1, "b1l0", "01/02", "FABRICATED CUSTOMER DEPOSIT", "5000.00", "credit"),
            row(1, "b2l0", "01/03", "FABRICATED SUPPLIER PAYMENT", "6500.00", "debit"),
            row(1, "b3l0", "01/05", "FABRICATED ITEM FEE", "40.00", "debit"),
            row(1, "b4l0", "01/06", "Credit-Returned Ck# 101", "400.00", "debit"),
            row(2, "b0l0", "01/07", "Credit-Returned Ck# 102", "500.00", "credit"),
            row(2, "b1t0r1", "01/04", "101", "400.00", "debit"),
            row(2, "b1t0r2", "01/04", "102", "500.00", "debit"),
            row(2, "b1t0r3", "01/05", "103", "800.00", "debit")]


def _categories():
    proof = prove_summary_box([SIGNED_STYLE], beginning=Decimal("2000"), ending=Decimal("-340"))
    return [{"label": label, "direction": direction, "amount": float(value)}
            for label, direction, value in proof.categories]


def _printed(page_1=SECTION_PAGE_1, page_2=SECTION_PAGE_2):
    from vlm.native_text import PrintedEvidence
    return [PrintedEvidence(native=page_1), PrintedEvidence(native=page_2)]


def test_rows_under_a_proven_categorys_heading_that_add_up_to_it_take_its_direction():
    from vlm.summary_box import settle_section_directions
    rows, audit = settle_section_directions(_section_rows(), _printed(), _categories())
    assert rows[3].direction == "credit" and rows[3].direction_source == "printed_section"
    assert [row.direction for row in rows] == ["credit", "debit", "debit", "credit", "credit", "debit", "debit",
                                               "debit"]
    assert audit["settled_rows"] == [{"page": 1, "locator": "b4l0", "section": "returned checks", "read": "debit",
                                      "settled": "credit"}]
    returned = next(item for item in audit["sections"] if item["section"] == "returned checks")
    assert returned == {"section": "returned checks", "direction": "credit", "rows": 2, "sums_to_category": True,
                        "column_conflicts": 0, "settled": 1}
    # The cheques paid, with the same amounts, stay under their own heading.
    checks = next(item for item in audit["sections"] if item["section"] == "checks")
    assert checks["rows"] == 3 and checks["sums_to_category"] and checks["settled"] == 0


def test_a_section_that_does_not_add_up_or_is_read_from_a_labelled_column_changes_nothing():
    from dataclasses import replace

    from vlm.native_text import PrintedEvidence
    from vlm.summary_box import settle_section_directions
    # The category's printed amount is not the section's rows: they are not all of it, or not only it.
    short = [dict(item, amount=950.0) if item["label"] == "Returned Checks" else item for item in _categories()]
    rows, audit = settle_section_directions(_section_rows(), _printed(), short)
    assert rows[3].direction == "debit" and audit["settled_rows"] == []
    # A direction printed by a labelled debit column is the row's own evidence: the section stays as read.
    columned = _section_rows()
    columned[3] = replace(columned[3], printed_amount=Decimal("400.00"), direction_source="column")
    rows, audit = settle_section_directions(columned, _printed(), _categories())
    assert rows[3].direction == "debit" and audit["settled_rows"] == []
    # A page without a text layer ends the heading: the continuation's rows cannot be placed, and the rows that
    # can do not add up to the category.
    rows, audit = settle_section_directions(_section_rows(), [_printed()[0], PrintedEvidence(native=None)],
                                            _categories())
    assert rows[3].direction == "debit" and audit["settled_rows"] == []


def test_only_a_heading_printed_as_the_categorys_label_names_its_section():
    from vlm.summary_box import settle_section_directions
    page_1 = SECTION_PAGE_1.replace("RETURNED CHECKS\n", "RETURNED CHECKS AND ADJUSTMENTS\n")
    page_2 = SECTION_PAGE_2.replace("RETURNED CHECKS (CONTINUED)", "RETURNED CHECKS AND ADJUSTMENTS (CONTINUED)")
    rows, audit = settle_section_directions(_section_rows(), _printed(page_1, page_2), _categories())
    assert rows[3].direction == "debit" and audit["settled_rows"] == []


def test_a_sign_printed_before_the_figure_is_the_lines_direction():
    # 1,000.00 - 150.25 - 600.50 + 900.00 = 1,149.25
    text = """Account summary
Your previous balance as of 03/18/2031 $1,000.00
Checks - 150.25
Other withdrawals, debits and service charges - 600.50
Deposits, credits and interest + 900.00
Your new balance as of 04/17/2031 = $1,149.25
Checks
"""
    proof = prove_summary_box([text], beginning=Decimal("1000"), ending=Decimal("1149.25"))
    assert proof is not None and proof.line_count == 3
    assert proof.stated_total_credits == Decimal("900.00") and proof.stated_total_debits == Decimal("750.75")
    # Signed on both sides, a line cannot be told.
    both = text.replace("Checks - 150.25", "Checks - 150.25 -")
    assert prove_summary_box([both], beginning=Decimal("1000"), ending=Decimal("1149.25")) is None


def test_a_heading_the_text_layer_runs_together_still_names_its_section():
    from vlm.summary_box import settle_section_directions
    page_1 = SECTION_PAGE_1.replace("RETURNED CHECKS\n", "RETURNEDCHECKS\n")
    rows, audit = settle_section_directions(_section_rows(), _printed(page_1), _categories())
    assert rows[3].direction == "credit"
    assert [item["section"] for item in audit["settled_rows"]] == ["returned checks"]

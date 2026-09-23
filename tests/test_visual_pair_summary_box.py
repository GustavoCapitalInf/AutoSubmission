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
    assert audit == {"proven": True, "applied": False, "reason": "reviewer_totals_also_balance",
                     "page": 1, "category_lines": 4}
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
                     "counts_from_summary_page": []}
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

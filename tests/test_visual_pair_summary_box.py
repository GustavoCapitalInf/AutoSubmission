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


def test_counts_only_when_every_line_prints_one():
    text = US_STYLE.replace("Customer Deposits 5 2,000.00", "Customer Deposits 2,000.00")
    proof = prove_summary_box([text], beginning=Decimal("1000.00"), ending=Decimal("1500.25"))
    assert proof is not None and proof.stated_credit_count is None and proof.stated_debit_count == 32


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
    assert audit == {"proven": True, "page": 1, "category_lines": 3,
                     "fields": ["stated_credit_count", "stated_debit_count", "stated_total_credits",
                                "stated_total_debits"],
                     "superseded_reviewer_fields": ["stated_total_credits"], "settled_disagreements": 1}
    assert {"field": "stated_total_credits", "page": 1, "source": "summary_box", "value": 12000.5} in evidence


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

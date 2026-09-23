"""Fabricated layouts only. A statement printing several accounts (vlm/accounts.py, vlm/pair_accounts.py): account
headings, where each account's rows are printed, the figures each account's own section prints, listings that
repeat the ledger, and each account judged on its own."""
from dataclasses import replace
from decimal import Decimal

import pytest

from vlm.accounts import (UNPLACED, assign_rows, listing_echoes, number_line, parse_heading, plan_accounts,
                          section_figures)
from vlm.assemble import Block, CandidateRow, DotsLayout
from vlm.native_text import PrintedEvidence
from vlm.review import PageReviewMerge


@pytest.mark.parametrize("text,kind,title,number,continued", [
    ("Business Savings Account Summary", "savings", "Business Savings", None, False),
    ("Business Free Checking Account (continued)", "checking", "Business Free Checking Account", None, True),
    ("## Business Free Checking Account (continued)", "checking", "Business Free Checking Account", None, True),
    ("S 0001 SAVINGS PRIME SHARE / SAVINGS", "savings", "SAVINGS PRIME SHARE / SAVINGS", "0001", False),
    ("S 0010 CHECKING LOW VOLUME BUSINESS CHECKING (Continued)", "checking",
     "CHECKING LOW VOLUME BUSINESS CHECKING", "0010", True),
    ("FABRICATED MEMBERSHIP SAVINGS ID 0001", "savings", "FABRICATED MEMBERSHIP SAVINGS", "0001", False),
    ("SMALL BUSINESS CHECKING 4321", "checking", "SMALL BUSINESS CHECKING", "4321", False),
    ("## ACCOUNT ACTIVITY FOR BUSINESS SAVINGS 1111", "savings", "BUSINESS SAVINGS", "1111", False),
    ("ACCOUNT ANALYSIS FOR BUSINESS ACCESS CHECKING 2222", "checking", "BUSINESS ACCESS CHECKING", "2222", False),
    ("01 FABRICATED PRIMARY SHARE", "savings", "01 FABRICATED PRIMARY SHARE", None, False),
    ("09 FABRICATED GOLD ACCOUNT CONTINUED", None, "09 FABRICATED GOLD ACCOUNT", None, True),
    ("Fabricated Regular Savings - Account#: XXXXXX1234", "savings", "Fabricated Regular Savings", "1234", False),
    ("Fabricated Basic Checking - Account#: XXXXXX5678 (continued)", "checking", "Fabricated Basic Checking",
     "5678", True),
    ("BUSINESS PREMIER CHECKING (0010) - Continued", "checking", "BUSINESS PREMIER CHECKING", "0010", True),
    ("## Fabricated Ownership - XXXXXX1234 (continued)", None, "Fabricated Ownership", "1234", True),
    ("Fabricated Money Market Savings 12345678", "money_market", "Fabricated Money Market Savings", "12345678",
     False),
    ("Share Draft Checking ID 70", "checking", "Share Draft Checking", "70", False),
])
def test_a_printed_title_names_an_account(text, kind, title, number, continued):
    heading = parse_heading(text)
    assert heading is not None
    assert (heading.kind, heading.title, heading.number, heading.continued) == (kind, title, number, continued)


@pytest.mark.parametrize("text", [
    "Account Number 1234567890123", "Account # 1234", "WITHDRAWAL SUMMARY", "DEPOSIT SUMMARY", "Summary of Accounts",
    "Account Summary", "Account Activity", "Statement Summary", "Summary of Checks Cleared", "CHECKS RECAP SUMMARY",
    "Deposit Accounts", "Primary Account", "Your Account Balances as of 03/31", "## Fabricated Loan Information",
    "Account Balances at a Glance", "Daily Balances", "Continued from previous page.", "Account Activity - continued",
    "TRANSACTION DETAIL (continued)", "Deposits and Other Credits", "Withdrawals and Other Charges", "Checks Cleared",
    "Beginning Balance: $100.00 Ending Balance: $100.00", "Total Shares: $1,234.56",
    "If you have questions about your checking account please call us", "", None,
])
def test_listings_notices_figures_and_sentences_name_no_account(text):
    assert parse_heading(text) is None


def test_an_account_number_line_names_the_account_headed_above():
    assert number_line("Account Number 1234567890123") == "1234567890123"
    assert number_line("Account Number: XXXXXX1234") == "1234"
    assert number_line("Member Number 12345") is None and number_line("Business Checking") is None


def _block(order, label, content, page=1):
    return Block(label, (0.125, 0.125 * order, 0.875, 0.125 * order + 0.045), content, order, page)


def _table(*rows):
    return "<table>" + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows) + \
        "</table>"


def _row(page, locator, date, amount, direction, balance, description="FABRICATED PAYEE"):
    return CandidateRow(date, date[5:].replace("-", "/"), description, Decimal(amount), direction,
                        None if balance is None else Decimal(balance), page, "stage_a+stage_b", locator,
                        "column", (0.125, 0.225, 0.875, 0.325), Decimal(amount))


def _merge(page, rows, *, unresolved=(), role="statement_page"):
    evidence = [{"page": page, "locator": row.locator, "state": "agreed"} for row in rows]
    evidence += [{"page": page, "locator": locator, "state": "unresolved"} for locator in unresolved]
    order = {row.locator: index for index, row in enumerate(rows)}
    evidence.sort(key=lambda item: order.get(item["locator"], len(order)))
    counts = {"agreed": len(rows), "unresolved": len(unresolved)}
    return PageReviewMerge(page, tuple(rows), tuple(evidence), counts, (), {}, (), role)


LEDGER_HEADER = ("Date", "Description", "Deposits", "Withdrawals", "Balance")
PAGE_ONE = DotsLayout(1, (
    _block(0, "page_header", "Account Number XXXXXX9999"),
    _block(1, "section_header", "Summary of Accounts"),
    _block(2, "table", _table(("Account", "Beginning Balance", "Ending Balance"),
                              ("FABRICATED SAVINGS 0001", "$50.00", "$50.00"),
                              ("FABRICATED CHECKING 0010", "$1,000.00", "$1,250.00"))),
    _block(3, "section_header", "FABRICATED SAVINGS (0001)"),
    _block(4, "text", "Beginning Balance: $50.00 Ending Balance: $50.00"),
    _block(5, "section_header", "FABRICATED BUSINESS CHECKING (0010)"),
    _block(6, "table", _table(("Beginning Balance", "$1,000.00", "Total Deposits", "$400.00"),
                              ("Total Withdrawals", "$150.00", "Ending Balance", "$1,250.00"))),
    _block(7, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"),
                              ("03/05", "FABRICATED CARD", "", "100.00", "1,300.00"))),
), (), (), False)
PAGE_TWO = DotsLayout(2, (
    _block(0, "page_header", "Account Number XXXXXX9999", page=2),
    _block(1, "section_header", "FABRICATED BUSINESS CHECKING (0010) - Continued", page=2),
    _block(2, "table", _table(LEDGER_HEADER, ("03/20", "FABRICATED FEE", "", "50.00", "1,250.00")), page=2),
    _block(3, "section_header", "WITHDRAWAL SUMMARY", page=2),
    _block(4, "table", _table(("Date", "Description", "Amount"), ("03/05", "FABRICATED CARD", "100.00"),
                              ("03/20", "FABRICATED FEE", "50.00")), page=2),
), (), (), False)
ROWS_ONE = [_row(1, "b7t0r1", "2031-03-02", "400.00", "credit", "1400.00"),
            _row(1, "b7t0r2", "2031-03-05", "100.00", "debit", "1300.00")]
ROWS_TWO = [_row(2, "b2t0r1", "2031-03-20", "50.00", "debit", "1250.00"),
            _row(2, "b4t0r1", "2031-03-05", "100.00", "debit", None),
            _row(2, "b4t0r2", "2031-03-20", "50.00", "debit", None)]


def test_the_plan_follows_each_account_across_pages():
    plan = plan_accounts([PAGE_ONE, PAGE_TWO])
    assert [(section.kind, section.title, section.number) for section in plan.sections] == [
        ("savings", "FABRICATED SAVINGS", "0001"), ("checking", "FABRICATED BUSINESS CHECKING", "0010")]
    # The summary table before every heading is no account's; page furniture never switches accounts.
    assert plan.section_at(1, 2) is None and plan.section_at(1, 4) == 0 and plan.section_at(1, 7) == 1
    assert plan.section_at(2, 0) == 1 and plan.section_at(2, 4) == 1
    assert plan.page_sections(1) == {0, 1} and plan.page_sections(2) == {1}
    assert [heading.continued for heading in plan.sections[1].headings] == [False, True]


def test_rows_belong_to_the_account_headed_above_them():
    plan = plan_accounts([PAGE_ONE, PAGE_TWO])
    added = _row(1, "added0", "2031-03-03", "5.00", "debit", "1395.00")
    merges = [_merge(1, [ROWS_ONE[0], added, ROWS_ONE[1]]), _merge(2, ROWS_TWO, unresolved=("b2t0r9",))]
    kept, evidence = assign_rows(plan, merges)
    assert kept[(1, "b7t0r1")] == 1 and kept[(1, "added0")] == 1 and kept[(2, "b4t0r2")] == 1
    assert evidence[(2, "b2t0r9")] == 1
    # A reviewer's addition on a page printing two accounts and no proposer row cannot be placed.
    alone = [_merge(1, [_row(1, "added0", "2031-03-03", "5.00", "debit", None)]), _merge(2, [])]
    assert assign_rows(plan, alone)[0][(1, "added0")] == UNPLACED


def test_each_account_takes_only_the_figures_its_own_section_prints():
    plan = plan_accounts([PAGE_ONE, PAGE_TWO])
    savings = section_figures(plan, 0, [PAGE_ONE, PAGE_TWO])
    checking = section_figures(plan, 1, [PAGE_ONE, PAGE_TWO])
    assert {name: item["value"] for name, item in savings.items()} == {
        "beginning_balance": Decimal("50.00"), "ending_balance": Decimal("50.00")}
    assert {name: item["value"] for name, item in checking.items()} == {
        "beginning_balance": Decimal("1000.00"), "ending_balance": Decimal("1250.00"),
        "stated_total_credits": Decimal("400.00"), "stated_total_debits": Decimal("150.00")}
    # A figure the page's text layer does not print is a misread, never a candidate.
    printed = [PrintedEvidence(native="FABRICATED BUSINESS CHECKING Beginning Balance $1,000.00 Ending Balance "
                                      "$1,250.00 Total Deposits $400.00 Total Withdrawals $150.00"), None]
    assert "beginning_balance" not in section_figures(plan, 0, [PAGE_ONE, PAGE_TWO], printed)


def test_figures_under_a_row_of_labels_and_conflicting_figures():
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED CHECKING 0010"),
        _block(1, "table", _table(("Opening Balance", "Total Deposits(2)", "Total Withdrawals(1)", "Ending Balance"),
                                  ("1,000.00", "400.00", "150.00", "1,250.00"))),
        _block(2, "table", _table(LEDGER_HEADER, ("", "Beginning Balance", "", "", "1,000.00"),
                                  ("03/02", "Transfer balance forward from savings", "25.00", "", "1,025.00"))),
        _block(3, "text", "Ending Balance: $1,300.00"),
    ), (), (), False)
    plan = plan_accounts([layout])
    figures = section_figures(plan, 0, [layout])
    assert figures["beginning_balance"]["value"] == Decimal("1000.00")
    assert figures["stated_total_credits"]["value"] == Decimal("400.00")
    # Two different closing figures: the last one printed is the account's closing (its own arithmetic decides
    # whether it is); both stay in the evidence.
    assert figures["ending_balance"]["value"] == Decimal("1300.00")
    assert figures["ending_balance"]["values"] == ["1250.00", "1300.00"]


def test_a_listing_that_repeats_the_ledger_is_not_more_transactions():
    plan = plan_accounts([PAGE_ONE, PAGE_TWO])
    rows = ROWS_ONE + ROWS_TWO
    assert listing_echoes(rows, plan) == {(2, "b4t0r1"), (2, "b4t0r2")}
    # A listing whose rows the ledger does not print is the ledger itself.
    other = [_row(2, "b4t0r1", "2031-03-06", "100.00", "debit", None)]
    assert listing_echoes(ROWS_ONE + ROWS_TWO[:1] + other, plan) == set()


def test_a_crop_recovered_row_takes_its_full_page_block():
    recovery = {"crops": [{"descriptor": {"page": 1}, "lineage": {"blocks": [
        {"fullpage_order": 7, "crop_order": 2, "crop_index": 1}]}}]}
    plan = plan_accounts([PAGE_ONE, PAGE_TWO], [recovery])
    assert plan.position(1, "g1c1/b2t0r0") == 7 and plan.position(1, "g0/b7t0r1") is None
    assert plan.section_at(1, plan.position(1, "g1c1/b2t0r0")) == 1


def _judge(merges, layouts=(PAGE_ONE, PAGE_TWO), **kwargs):
    from vlm.pair_accounts import judge_accounts
    rows = [row for merged in merges for row in merged.rows]
    document = {"period_start": "2031-03-01", "period_end": "2031-03-31", "currency": "USD", "bank": "FABRICATED"}
    return judge_accounts(list(layouts), merges, rows, document=document, page_errors=[[] for _ in merges],
                          truncated=[False for _ in merges], **kwargs)


def test_each_account_is_judged_on_its_own():
    result = _judge([_merge(1, ROWS_ONE), _merge(2, ROWS_TWO)])
    savings, checking = result["accounts"]
    assert (savings["status"], savings.get("balance")) == ("held", None)  # no text layer: idle needs one
    assert checking["status"] == "verified" and checking["listing_echo_rows"] == 2
    statement = checking["statement"]
    assert (statement["beginning_balance"], statement["ending_balance"]) == (1000.0, 1250.0)
    assert [row["amount"] for row in statement["transactions"]] == [400.0, -100.0, -50.0]
    assert statement["account_name"] == "FABRICATED BUSINESS CHECKING" and statement["account_number"] == "0010"
    printed = [PrintedEvidence(native="Beginning Balance: $50.00 Ending Balance: $50.00 $1,000.00 $1,250.00 "
                                      "$400.00 $150.00 1,400.00 1,300.00"), PrintedEvidence(native="1,250.00")]
    result = _judge([_merge(1, ROWS_ONE), _merge(2, ROWS_TWO)], printed_pages=printed)
    assert [(account["status"], account.get("balance")) for account in result["accounts"]] == [
        ("idle", 50.0), ("verified", None)]


def test_one_accounts_failure_never_holds_another():
    # A row of the savings account the reviewer could not settle holds the savings account only.
    savings_row = _row(1, "b4l0", "2031-03-10", "5.00", "credit", None)
    layout = DotsLayout(1, PAGE_ONE.blocks[:5] + (_block(4, "text", "03/10 FABRICATED DIVIDEND 5.00"),)
                        + PAGE_ONE.blocks[5:], (), (), False)
    result = _judge([_merge(1, [savings_row] + ROWS_ONE, unresolved=("b4l1",)), _merge(2, ROWS_TWO)],
                    layouts=(layout, PAGE_TWO))
    savings, checking = result["accounts"]
    assert savings["status"] == "held" and "page_unresolved" in savings["reasons"]
    assert checking["status"] == "verified"
    # A cut-off read of page 2 holds the account printed on it, not the one that ended on page 1.
    from vlm.pair_accounts import judge_accounts
    merges = [_merge(1, ROWS_ONE), _merge(2, ROWS_TWO)]
    document = {"period_start": "2031-03-01", "period_end": "2031-03-31", "currency": "USD"}
    result = judge_accounts([PAGE_ONE, PAGE_TWO], merges, ROWS_ONE + ROWS_TWO, document=document,
                            page_errors=[[], []], truncated=[False, True])
    assert [account["status"] for account in result["accounts"]] == ["held", "held"]
    assert "page_unresolved" in result["accounts"][1]["reasons"]
    assert "page_unresolved" not in result["accounts"][0]["reasons"]


def test_a_statement_printing_one_account_is_not_judged_by_account():
    layout = DotsLayout(1, (PAGE_ONE.blocks[5], PAGE_ONE.blocks[6], PAGE_ONE.blocks[7]), (), (), False)
    assert _judge([_merge(1, ROWS_ONE)], layouts=(layout,)) is None
    # A document fact every account needs (the period) holds them all.
    result = _judge([_merge(1, ROWS_ONE), _merge(2, ROWS_TWO)], document_reasons=["period_mismatch"])
    assert all("period_mismatch" in account["reasons"] for account in result["accounts"])


@pytest.mark.parametrize("text", ["Member Number xxxxxx1234", "Account number: 1234567890 (primary account)",
                                  "Thanks for saving with Fabricated Bank", "For inquiries, contact 555-555-FABR (1234)",
                                  "Fabricated Savings Service 1-800-555-0100"])
def test_identifier_lines_and_courtesies_name_no_account(text):
    assert parse_heading(text) is None


def test_a_title_naming_only_the_kind_is_the_account_of_that_kind():
    # A summary's "Checking Accounts" heading and the ledger's "Business Checking" heading: one checking account.
    layout = DotsLayout(1, (
        _block(0, "section_header", "Checking Accounts"),
        _block(1, "text", "Beginning Balance: $1,000.00 Ending Balance: $1,250.00"),
        _block(2, "text", "Business Checking"),
        _block(3, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"))),
        _block(4, "section_header", "Checking Account Activity - Main Account"),
    ), (), (), False)
    assert len(plan_accounts([layout]).sections) == 1
    # Titles that each name something of their own, or print different numbers, are different accounts.
    other = DotsLayout(1, (
        _block(0, "section_header", "360 Checking - 12345678901"),
        _block(1, "text", "360 CHECKING | JOINT WITH FABRICATED PERSON"),
        _block(2, "section_header", "360 Performance Savings - 12345678902"),
        _block(3, "section_header", "360 Performance Savings - 12345678903"),
    ), (), (), False)
    assert len(plan_accounts([other]).sections) == 4


def test_a_summary_table_gives_an_account_the_figure_its_section_does_not_print():
    from vlm.accounts import summary_table_figures
    layout = DotsLayout(1, (
        _block(0, "section_header", "Statement Summary"),
        _block(1, "table", _table(("Deposit Accounts", "Beginning Balance", "Deposits", "Withdrawals",
                                   "Ending Balance"),
                                  ("Fabricated Savings - XXXXXX0001", "$50.00", "$0.00", "$0.00", "$50.00"),
                                  ("Fabricated Checking - XXXXXX0010", "$1,000.00", "$400.00", "$150.00",
                                   "$1,250.00"))),
        _block(2, "section_header", "Fabricated Savings - Account#: XXXXXX0001"),
        _block(3, "section_header", "Fabricated Checking - Account#: XXXXXX0010"),
        _block(4, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"),
                                  ("03/31", "Ending Balance", "", "", "1,250.00"))),
    ), (), (), False)
    plan = plan_accounts([layout])
    summary = summary_table_figures(plan, [layout])
    assert {name: [value for value, _ in found] for name, found in summary[1].items()} == {
        "beginning_balance": [Decimal("1000.00")], "ending_balance": [Decimal("1250.00")]}
    figures = section_figures(plan, 1, [layout], summary=summary)
    assert (figures["beginning_balance"]["value"], figures["beginning_balance"]["source"]) == (
        Decimal("1000.00"), "summary_table")
    assert (figures["ending_balance"]["value"], figures["ending_balance"]["source"]) == (Decimal("1250.00"), "section")


def test_an_addition_with_no_proposer_row_beside_it_takes_the_account_above_its_box():
    plan = plan_accounts([PAGE_ONE, PAGE_TWO])
    item = {"page": 1, "locator": "added0", "state": "added", "row": {"bbox": [0.125, 0.725, 0.875, 0.745]}}
    merged = PageReviewMerge(1, (_row(1, "added0", "2031-03-03", "5.00", "debit", None),), (item,), {"added": 1},
                             (), {}, (), "statement_page")
    assert assign_rows(plan, [merged, _merge(2, [])])[0][(1, "added0")] == 1  # under the checking heading
    item["row"]["bbox"] = [0.125, 0.455, 0.875, 0.475]
    assert assign_rows(plan, [merged, _merge(2, [])])[0][(1, "added0")] == 0  # between savings and checking


def test_a_reviewer_addition_that_moves_nothing_is_no_transaction():
    from vlm.pair_accounts import _balance_only_additions
    # "Interest Rate Change ..." printing only the balance, read at that balance: the balance did not move.
    info = _row(1, "added0", "2031-03-12", "7.134", "credit", "7.134", description="Interest Rate Change")
    interest = _row(1, "added1", "2031-03-31", "0.041", "credit", "7.175", description="Monthly Interest Paid")
    assert _balance_only_additions([info, interest], Decimal("7.134")) == {(1, "added0")}
    # A first deposit into an empty account moves its whole balance; a proposer's row is never excluded.
    deposit = _row(1, "added0", "2031-03-12", "7.134", "credit", "7.134")
    assert _balance_only_additions([deposit], Decimal("0.00")) == set()
    assert _balance_only_additions([replace(info, locator="b3t0r1")], Decimal("7.134")) == set()
    # The review dropped the balance (the line prints its one figure once); that figure still says nothing moved.
    unbalanced = replace(info, balance=None)
    assert _balance_only_additions([unbalanced], 7.134, {(1, "added0"): Decimal("7.134")}) == {(1, "added0")}
    assert _balance_only_additions([unbalanced], Decimal("6.125"), {(1, "added0"): Decimal("7.134")}) == set()


def test_an_account_printing_one_withdrawal_takes_the_statements_minus_style():
    # The statement prints withdrawals as "-100.00": the savings account's one withdrawal "-5.00" is no reversal.
    layout = DotsLayout(1, tuple(_block(4, "text", "Beginning Balance: $50.00 Ending Balance: $45.00")
                                 if block.order == 4 else block for block in PAGE_ONE.blocks), (), (), False)
    savings = replace(_row(1, "b4l0", "2031-03-10", "5.00", "debit", "45.00"), printed_amount=Decimal("-5.00"))
    signed = [replace(row, printed_amount=-row.amount) if row.direction == "debit" else row
              for row in ROWS_ONE + ROWS_TWO[:1]]
    result = _judge([_merge(1, [savings] + signed[:2]), _merge(2, signed[2:])], layouts=(layout, PAGE_TWO))
    assert [account["status"] for account in result["accounts"]] == ["verified", "verified"]


# Review 7 (independent adversarial review of the multi-account change): its reproductions, fabricated.
REVIEW_PAGE = DotsLayout(1, (
    _block(0, "section_header", "FABRICATED BUSINESS CHECKING (0010)"),
    _block(1, "table", _table(("Beginning Balance", "$1,000.00", "Total Deposits", "$400.00"),
                              ("Total Withdrawals", "$150.00", "Ending Balance", "$1,250.00"))),
    _block(2, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"),
                              ("03/05", "FABRICATED CARD", "", "100.00", "1,300.00"),
                              ("03/20", "FABRICATED FEE", "", "50.00", "1,250.00"))),
    _block(3, "section_header", "FABRICATED SAVINGS (0001)"),
    _block(4, "text", "Beginning Balance: $50.00 Ending Balance: $50.00"),
    _block(5, "text", "03/10 TRANSFER IN 500.00\n03/15 TRANSFER OUT 500.00"),
), (), (), False)
REVIEW_ROWS = [_row(1, "b2t0r1", "2031-03-02", "400.00", "credit", "1400.00"),
               _row(1, "b2t0r2", "2031-03-05", "100.00", "debit", "1300.00"),
               _row(1, "b2t0r3", "2031-03-20", "50.00", "debit", "1250.00")]


def _added(locator, date, amount, direction, top):
    return replace(_row(1, locator, date, amount, direction, None), bbox=(0.125, top, 0.875, top + 1 / 50))


def test_an_addition_whose_neighbour_and_box_name_different_accounts_is_unplaced():
    # The reviewer adds the savings account's two transfers after the checking account's last row, with boxes under
    # the savings heading: neither account may take them (finding 1).
    additions = [_added("added0", "2031-03-10", "500.00", "credit", 0.63),
                 _added("added1", "2031-03-15", "500.00", "debit", 0.66)]
    rows = REVIEW_ROWS + additions
    evidence = [{"page": 1, "locator": row.locator, "state": "added" if row.locator.startswith("added") else "agreed",
                 "row": {"bbox": list(row.bbox)}} for row in rows]
    merged = PageReviewMerge(1, tuple(rows), tuple(evidence), {"agreed": 3, "added": 2}, (), {}, (), "statement_page")
    plan = plan_accounts([REVIEW_PAGE])
    kept, _ = assign_rows(plan, [merged])
    assert kept[(1, "added0")] == UNPLACED and kept[(1, "added1")] == UNPLACED
    result = _judge([merged], layouts=(REVIEW_PAGE,))
    assert [(account["status"], "rows_unplaced" in account["reasons"]) for account in result["accounts"]] == [
        ("held", True), ("held", True)]


def test_an_account_printing_a_transaction_line_is_never_idle():
    # The savings section prints two dated transfers the readers did not keep: its equal opening and closing
    # balances do not make it idle (finding 1).
    printed = [PrintedEvidence(native="Beginning Balance: $50.00 Ending Balance: $50.00 $1,000.00 $1,250.00 $400.00 "
                                      "$150.00 1,400.00 1,300.00 1,250.00")]
    result = _judge([_merge(1, REVIEW_ROWS)], layouts=(REVIEW_PAGE,), printed_pages=printed)
    checking, savings = result["accounts"]
    assert checking["status"] == "verified"
    assert (savings["status"], savings["activity_lines"]) == ("held", 2) and "no_rows" in savings["reasons"]


def test_a_table_emitted_before_its_heading_is_placed_by_neither():
    # The reading order puts the savings table under the checking heading, the page puts it under the savings
    # heading: no account takes its rows (finding 1).
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED BUSINESS CHECKING (0010)"),
        _block(1, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"))),
        replace(_block(2, "table", _table(LEDGER_HEADER, ("03/10", "TRANSFER IN", "500.00", "", "550.00"))),
                bbox=(0.125, 7 / 10, 0.875, 8 / 10)),
        replace(_block(3, "section_header", "FABRICATED SAVINGS (0001)"), bbox=(0.125, 6 / 10, 0.875, 13 / 20)),
    ), (), (), False)
    plan = plan_accounts([layout])
    assert plan.block_section(1, 1) == 0 and plan.block_section(1, 2) == UNPLACED


def test_short_titles_printing_sentence_words_still_name_accounts():
    # Finding 2: the business checking account's own heading must not go unrecognized.
    for text, kind, title in (("Your Business Checking (0010)", "checking", "Business Checking"),
                              ("YOUR REGULAR SAVINGS 0001", "savings", "REGULAR SAVINGS"),
                              ("US Bank Business Checking 1234", "checking", "US Bank Business Checking"),
                              ("Business Checking Activity for May", "checking", "Business Checking"),
                              ("Daily Interest Savings 0002", "savings", "Daily Interest Savings")):
        heading = parse_heading(text)
        assert heading is not None and (heading.kind, heading.title) == (kind, title), text
    assert parse_heading("Daily Balances") is None
    assert parse_heading("If you have questions about your checking account") is None


def test_rows_printed_before_every_recognized_heading_stop_the_account_by_account_judgement():
    # An unrecognized first heading with its rows, then two recognized accounts: judging only those two would drop
    # the first account from the statement (finding 2).
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED OPERATING"),
        _block(1, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"))),
        _block(2, "section_header", "FABRICATED SAVINGS (0001)"),
        _block(3, "text", "Beginning Balance: $50.00 Ending Balance: $55.00"),
        _block(4, "table", _table(LEDGER_HEADER, ("03/31", "DIVIDEND", "5.00", "", "55.00"))),
        _block(5, "section_header", "FABRICATED CLUB (0002)"),
        _block(6, "text", "Beginning Balance: $25.00 Ending Balance: $25.00"),
    ), (), (), False)
    rows = [_row(1, "b1t0r1", "2031-03-02", "400.00", "credit", "1400.00"),
            _row(1, "b4t0r1", "2031-03-31", "5.00", "credit", "55.00")]
    result = _judge([_merge(1, rows)], layouts=(layout,))
    assert result["skipped"] == "rows_outside_accounts" and result["rows_outside_accounts"] == 1


def test_a_number_read_from_an_account_number_line_does_not_make_a_second_account():
    # Finding 7: "FABRICATED SAVINGS" + "Account Number ...7890", later "FABRICATED SAVINGS (0001)": one account.
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED SAVINGS"),
        _block(1, "text", "Account Number 1234567890"),
        _block(2, "section_header", "FABRICATED CHECKING (0010)"),
        _block(3, "section_header", "FABRICATED SAVINGS (0001)"),
    ), (), (), False)
    assert [section.title for section in plan_accounts([layout]).sections] == ["FABRICATED SAVINGS",
                                                                              "FABRICATED CHECKING"]


def test_a_transaction_beginning_with_a_balance_label_is_no_figure():
    # Finding 8: "NEW BALANCE TRANSFER TO SAVINGS" is a transaction of the ledger, not the account's closing.
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED CHECKING (0010)"),
        _block(1, "table", _table(LEDGER_HEADER, ("", "Beginning Balance", "", "", "1,000.00"),
                                  ("03/05", "NEW BALANCE TRANSFER TO SAVINGS", "", "100.00", "900.00"),
                                  ("03/31", "Ending Balance", "", "", "900.00"))),
    ), (), (), False)
    figures = section_figures(plan_accounts([layout]), 0, [layout])
    assert figures["ending_balance"]["values"] == ["900.00"] and figures["beginning_balance"]["value"] == \
        Decimal("1000.00")


# Review 8 (verification of e36267e): its reproductions, fabricated.
REVIEW8_PRINT = [PrintedEvidence(native="Beginning Balance: $50.00 Ending Balance: $50.00 $1,000.00 $1,250.00 $400.00 "
                                        "$150.00 1,400.00 1,300.00 1,250.00")]


def test_a_transaction_printed_with_its_date_second_keeps_its_account_from_idle():
    # Finding 2: "Description | Date | Amount" rows the readers did not keep are activity all the same.
    layout = DotsLayout(1, REVIEW_PAGE.blocks[:5] + (
        _block(5, "table", _table(("Description", "Date", "Amount"), ("TRANSFER IN", "03/10", "500.00"),
                                  ("TRANSFER OUT", "03/15", "500.00"))),), (), (), False)
    savings = _judge([_merge(1, REVIEW_ROWS)], layouts=(layout,), printed_pages=REVIEW8_PRINT)["accounts"][1]
    assert (savings["status"], savings["activity_lines"]) == ("held", 2)


def test_a_proposer_row_the_reviewer_rejected_keeps_its_account_from_idle():
    # Finding 2: a line read as a row and rejected may have been a transaction; a rejected balance line is not.
    layout = DotsLayout(1, REVIEW_PAGE.blocks[:5], (), (), False)

    def savings(description):
        merged = _merge(1, REVIEW_ROWS)
        rejected = {"page": 1, "locator": "b4l0", "state": "rejected", "reason": "",
                    "original": {"description": description, "amount": 500.0}}
        merged = replace(merged, evidence=merged.evidence + (rejected,))
        return _judge([merged], layouts=(layout,), printed_pages=REVIEW8_PRINT)["accounts"][1]

    assert savings("Beginning Balance")["status"] == "idle"
    held = savings("FABRICATED TRANSFER")
    assert (held["status"], held["rejected_rows"]) == ("held", 1)


@pytest.mark.parametrize("text", [
    "Your savings are insured by the NCUA", "We value your checking relationship",
    "Your checking account may earn interest", "Your savings federally insured to 250,000",
    "Business Checking has changed",
])
def test_a_sentence_about_an_account_names_no_account(text):
    # Finding 4.
    assert parse_heading(text) is None


def test_product_names_printing_a_word_of_a_sentence_still_name_accounts():
    for text, title in (("Pay As You Go Checking", "Pay As You Go Checking"),
                        ("Best Value Business Checking 1234", "Best Value Business Checking")):
        heading = parse_heading(text)
        assert heading is not None and heading.title == title, text


def test_a_number_lines_identifier_is_replaced_by_the_titles_own_once():
    # Finding 7: "(0001)" is the savings account the number line named; "(0002)" is another account.
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED SAVINGS"),
        _block(1, "text", "Account Number 1234567890"),
        _block(2, "section_header", "FABRICATED CHECKING (0010)"),
        _block(3, "section_header", "FABRICATED SAVINGS (0001)"),
        _block(4, "section_header", "FABRICATED SAVINGS (0002)"),
    ), (), (), False)
    assert [(section.title, section.key) for section in plan_accounts([layout]).sections] == [
        ("FABRICATED SAVINGS", "0001"), ("FABRICATED CHECKING", "0010"), ("FABRICATED SAVINGS", "0002")]


def test_a_balance_line_printing_when_it_stands_is_still_the_figure():
    # Finding 8.
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED CHECKING (0010)"),
        _block(1, "table", _table(LEDGER_HEADER, ("", "Beginning Balance as of 03/01", "", "", "1,000.00"),
                                  ("03/05", "NEW BALANCE TRANSFER TO SAVINGS", "", "100.00", "900.00"),
                                  ("", "Ending Balance on 03/31", "", "", "900.00"))),
    ), (), (), False)
    figures = section_figures(plan_accounts([layout]), 0, [layout])
    assert figures["beginning_balance"]["value"] == Decimal("1000.00")
    assert figures["ending_balance"]["values"] == ["900.00"]


def test_rows_read_from_a_summary_table_are_no_accounts_rows():
    # Finding 5: the summary table printed before every heading, read as rows and kept by the reviewer.
    summary = [_row(1, "b2t0r1", "2031-03-31", "50.00", "credit", None, description="FABRICATED SAVINGS 0001 $50.00"),
               _row(1, "b2t0r2", "2031-03-31", "1250.00", "credit", None,
                    description="FABRICATED CHECKING 0010 $1,000.00")]
    result = _judge([_merge(1, summary + ROWS_ONE), _merge(2, ROWS_TWO)])
    assert "skipped" not in result and result["accounts"][1]["status"] == "verified"
    # A row outside every heading that names no account still stops the account-by-account judgement.
    stray = [_row(1, "b2t0r1", "2031-03-31", "50.00", "credit", None, description="FABRICATED DEPOSIT")]
    assert _judge([_merge(1, stray + ROWS_ONE), _merge(2, ROWS_TWO)])["skipped"] == "rows_outside_accounts"


# Review 9 (verification of d62bd8b): its reproductions, fabricated.
def test_a_table_the_page_prints_as_balances_is_known_by_its_caption_or_header():
    from vlm.accounts import balance_table_blocks
    layout = DotsLayout(1, (
        _block(0, "section_header", "DAILY BALANCE"),
        _block(1, "table", _table(("03/02", "1,400.00"), ("03/05", "1,300.00"))),
        _block(2, "section_header", "Items Credited and Items Charged"),
        _block(3, "table", _table(("03/10", "500.00"), ("03/15", "500.00"))),
        _block(4, "table", _table(("Date", "Balance", "Date", "Balance"), ("03/20", "1,250.00", "03/25", "1,250.00"))),
        _block(5, "table", _table(LEDGER_HEADER, ("03/02", "FABRICATED DEPOSIT", "400.00", "", "1,400.00"))),
        # A Markdown table printed as a text block under its caption is a table all the same.
        _block(6, "section_header", "## Daily Balances"),
        _block(7, "text", "| Date | Amount | Date | Amount |\n|---|---|---|---|\n| 03/30 | $1,250.00 | 03/31 | $1,250.00 |"),
    ), (), (), False)
    assert balance_table_blocks(layout) == frozenset({1, 4, 7})


def test_a_ledger_whose_header_names_figure_columns_is_never_a_summary_table():
    # Finding 3: the unrecognized operating account's ledger ("Deposits and Credits | Withdrawals and Debits") names
    # a sibling in its transfers; its rows are not summary rows, so the statement is not judged without it.
    layout = DotsLayout(1, (
        _block(0, "section_header", "Fabricated Advantage Plus Banking 0010"),
        _block(1, "table", _table(("Date", "Description", "Deposits and Credits", "Withdrawals and Debits", "Balance"),
                                  ("03/05", "ONLINE TRANSFER TO SAVINGS 0001", "", "100.00", "1,200.00"))),
        _block(2, "section_header", "FABRICATED SAVINGS (0001)"),
        _block(3, "text", "Beginning Balance: $50.00 Ending Balance: $150.00"),
        _block(4, "section_header", "FABRICATED MONEY MARKET (0002)"),
        _block(5, "text", "Beginning Balance: $25.00 Ending Balance: $25.00"),
    ), (), (), False)
    from vlm.accounts import summary_table_rows
    plan = plan_accounts([layout])
    assert summary_table_rows(plan, [layout], {(1, "b1t0r1"): "ONLINE TRANSFER TO SAVINGS 0001"}) == set()
    rows = [_row(1, "b1t0r1", "2031-03-05", "100.00", "debit", "1200.00", description="ONLINE TRANSFER TO SAVINGS 0001")]
    assert _judge([_merge(1, rows)], layouts=(layout,))["skipped"] == "rows_outside_accounts"


@pytest.mark.parametrize("text", [
    "Grow your savings faster", "Savings made simple", "Checking that pays you back", "Open a savings account today",
])
def test_running_text_in_sentence_case_is_no_account_heading(text):
    # Finding 5: printed as running text (a text block), a sentence-case line naming an account word is marketing.
    layout = DotsLayout(1, (_block(0, "section_header", "FABRICATED CHECKING (0010)"), _block(1, "text", text),
                            _block(2, "section_header", "FABRICATED SAVINGS (0001)")), (), (), False)
    assert [section.title for section in plan_accounts([layout]).sections] == ["FABRICATED CHECKING",
                                                                              "FABRICATED SAVINGS"]


@pytest.mark.parametrize("text,title", [
    ("Earn More Savings", "Earn More Savings"), ("Be Free Checking", "Be Free Checking"),
    ("Your Business Advantage Checking Account 1234", "Business Advantage Checking"),
    ("Your Fabricated Business Checking Account XXXX1234", "Fabricated Business Checking Account"),
])
def test_product_names_opening_with_a_verb_or_printing_their_number_still_name_accounts(text, title):
    # Finding 6.
    heading = parse_heading(text)
    assert heading is not None and heading.title == title, text


def test_a_number_line_confirmed_by_its_titles_own_identifier_is_not_reused_for_the_next():
    # Finding 7's residual: the number line's last four digits are the first title's suffix; the next suffix is
    # another account.
    layout = DotsLayout(1, (
        _block(0, "section_header", "FABRICATED SAVINGS"),
        _block(1, "text", "Account Number 1234560001"),
        _block(2, "section_header", "FABRICATED CHECKING (0010)"),
        _block(3, "section_header", "FABRICATED SAVINGS (0001)"),
        _block(4, "section_header", "FABRICATED SAVINGS (0002)"),
    ), (), (), False)
    assert [(section.title, section.key) for section in plan_accounts([layout]).sections] == [
        ("FABRICATED SAVINGS", "0001"), ("FABRICATED CHECKING", "0010"), ("FABRICATED SAVINGS", "0002")]


def test_an_account_whose_only_row_was_set_aside_as_moving_nothing_is_never_idle():
    # Finding 9: the reviewer added a transfer at the opening balance; set aside, it must not make the account idle.
    page_one = DotsLayout(1, REVIEW_PAGE.blocks[:3], (), (), False)
    page_two = DotsLayout(2, (_block(0, "section_header", "FABRICATED SAVINGS (0001)", page=2),
                              _block(1, "text", "Beginning Balance: $50.00 Ending Balance: $50.00", page=2)),
                          (), (), False)
    addition = _row(2, "added0", "2031-03-10", "50.00", "credit", "50.00", description="TRANSFER IN")
    savings_page = PageReviewMerge(2, (addition,), ({"page": 2, "locator": "added0", "state": "added"},),
                                   {"added": 1}, (), {}, (), "statement_page")
    printed = [REVIEW8_PRINT[0],
               PrintedEvidence(native="Beginning Balance: $50.00 Ending Balance: $50.00\n03/10 TRANSFER IN 50.00")]
    savings = _judge([_merge(1, REVIEW_ROWS), savings_page], layouts=(page_one, page_two),
                     printed_pages=printed)["accounts"][1]
    assert savings["balance_only_additions"] == 1 and savings["status"] == "held"


def test_dates_printed_dotted_or_compact_are_activity_too():
    # Finding 8.
    for date_text in ("10.03.2031", "10MAR", "MAR10"):
        layout = DotsLayout(1, REVIEW_PAGE.blocks[:5] + (
            _block(5, "table", _table(("Description", "Date", "Amount"), ("TRANSFER IN", date_text, "500.00"))),),
                            (), (), False)
        savings = _judge([_merge(1, REVIEW_ROWS)], layouts=(layout,), printed_pages=REVIEW8_PRINT)["accounts"][1]
        assert (savings["status"], savings["activity_lines"]) == ("held", 1), date_text


def test_page_metadata_the_print_contradicts_holds_the_accounts_on_that_page():
    # Finding 9: as on a single account, quarantined reviewer metadata holds the page.
    merged = replace(_merge(2, ROWS_TWO), metadata_evidence=({"field": "ending_balance"},))
    result = _judge([_merge(1, ROWS_ONE), merged])
    assert "page_unresolved" in result["accounts"][1]["reasons"]

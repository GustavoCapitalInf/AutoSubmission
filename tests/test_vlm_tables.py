from vlm import tables

HTML = """
<html><body><table>
<tr><th>Date</th><th>Description</th><th>Withdrawals</th><th>Deposits</th><th>Balance</th></tr>
<tr><td>01/02</td><td>SYNTHETIC<br>ROW 01</td><td></td><td>10.00</td><td>510.00</td></tr>
<tr><td>01/03</td><td>SYNTHETIC ROW 02</td><td>5.00</td><td></td><td>505.00</td></tr>
</table>
<table><tr><td colspan="2">Totals</td><td>5.00</td></tr></table>
</body></html>
"""


def test_parse_html_tables_grid():
    grids = tables.parse_html_tables(HTML)
    assert len(grids) == 2
    assert grids[0][0] == ["Date", "Description", "Withdrawals", "Deposits", "Balance"]
    assert grids[0][1] == ["01/02", "SYNTHETIC ROW 01", "", "10.00", "510.00"]
    assert grids[1][0] == ["Totals", "Totals", "5.00"]


def test_classify_columns_with_header():
    grid = tables.parse_html_tables(HTML)[0]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.debit, cm.credit, cm.amount, cm.balance, cm.header_row) == (0, 1, 2, 3, None, 4, 0)


def test_classify_columns_without_header_single_amount():
    grid = [["2031-01-01", "SYNTHETIC ROW 01", "10.00", "510.00"],
            ["2031-01-02", "SYNTHETIC ROW 02", "20.00", "530.00"],
            ["2031-01-03", "SYNTHETIC ROW 03", "30.00", "560.00"]]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.amount, cm.balance, cm.header_row) == (0, 1, 2, 3, None)
    assert cm.debit is None and cm.credit is None


def test_classify_columns_without_header_two_money_columns_and_balance():
    grid = [["01/02", "A", "", "10.00", "510.00"], ["01/03", "B", "5.00", "", "505.00"], ["01/04", "C", "1.00", "", "504.00"]]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.debit, cm.credit, cm.balance) == (0, 1, 2, 3, 4)


def test_classify_columns_empty_grid():
    cm = tables.classify_columns([])
    assert cm.date is None and cm.balance is None


def test_a_currency_after_a_header_word_is_the_columns_unit_not_its_role():
    grid = [["DATE", "DESCRIPTION", "AMOUNT($)"], ["03/19", "FABRICATED PURCHASE", "57.25"]]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.amount, cm.header_row) == (0, 1, 2, 0)
    for header in ("Amount (USD)", "Balance ($)", "Montant $"):
        assert tables._header_role(header) is not None, header


def test_a_table_printed_three_up_reads_as_one_table_left_to_right_then_down():
    header = ["DATE", "CHECK #", "AMOUNT($)"] * 3
    grid = [header,
            ["03/23", "301~", "", "03/24", "302", "81.40", "04/02", "303", "46.15"],
            ["03/24", "304", "412.60", "03/31", "*305", "97.00", "", "", ""]]
    unfolded = tables.unfold_side_by_side(grid)
    # The cheque listed without an amount (converted, posted elsewhere) and the empty slot are no rows.
    assert unfolded == [["DATE", "CHECK #", "AMOUNT($)"], ["03/24", "302", "81.40"], ["04/02", "303", "46.15"],
                        ["03/24", "304", "412.60"], ["03/31", "*305", "97.00"]]


def test_only_a_repeated_group_naming_a_money_column_is_unfolded():
    ordinary = [["Date", "Description", "Debit", "Credit", "Balance"], ["01/02", "FABRICATED", "1.00", "", "9.00"]]
    assert tables.unfold_side_by_side(ordinary) == ordinary
    names = [["Name", "Title", "Name", "Title"], ["FABRICATED", "OWNER", "FABRICATED", "PARTNER"]]
    assert tables.unfold_side_by_side(names) == names
    uneven = [["Date", "Amount", "Date", "Amount", "Date"], ["01/02", "1.00", "01/03", "2.00", "01/04"]]
    assert tables.unfold_side_by_side(uneven) == uneven

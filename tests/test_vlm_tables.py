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


def test_a_sign_after_a_header_word_is_the_columns_arithmetic_not_its_role():
    # "Checks & Other Debits (-)" once named no role, so every row printing only a debit was dropped.
    grid = [["Posting Date", "Transaction Description", "Deposits & Other Credits (+)", "Checks & Other Debits (-)",
             "Daily Balance"], ["04/17/2031", "FABRICATED CHECK 101", "", "1,111.11", "5,000.00"]]
    cm = tables.classify_columns(grid)
    assert (cm.date, cm.description, cm.credit, cm.debit, cm.balance, cm.header_row) == (0, 1, 2, 3, 4, 0)
    assert tables._header_role("Withdrawals (−)") == "debit" and tables._header_role("(+)") is None


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


def test_abbreviated_date_headers_are_dates_and_a_second_date_is_no_description():
    from vlm.assemble import rows_from_grid
    grid = [["Post.", "Eff.", "Description", "Deposits", "Withdrawals", "Balance"],
            ["03/05", "03/04", "FABRICATED TRANSFER", "105.25", "", "347.75"],
            ["03/06", "03/06", "FABRICATED CARD", "", "12.50", "335.25"]]
    columns = tables.classify_columns(grid)
    assert (columns.date, columns.other_dates, columns.description) == (0, (1,), 2)
    rows = rows_from_grid(grid, columns, page=1, table_index=0, year_hint=2031)
    assert [(row.date, row.description, row.direction) for row in rows] == [
        ("2031-03-05", "FABRICATED TRANSFER", "credit"), ("2031-03-06", "FABRICATED CARD", "debit")]


def test_a_category_column_of_direction_words_directs_unsigned_amounts():
    from vlm.assemble import rows_from_grid
    grid = [["DATE", "DESCRIPTION", "CATEGORY", "AMOUNT", "BALANCE"],
            ["Mar 5", "FABRICATED CARD PURCHASE", "Debit", "12.50", "335.25"],
            ["Mar 6", "FABRICATED DEPOSIT", "Credit", "40.00", "375.25"],
            ["Mar 7", "FABRICATED FEE", "Debit", "-3.00", "372.25"]]
    columns = tables.classify_columns(grid)
    assert columns.direction == 2
    rows = rows_from_grid(grid, columns, page=1, table_index=0, year_hint=2031)
    assert [(row.description, row.direction, row.direction_source) for row in rows] == [
        ("FABRICATED CARD PURCHASE", "debit", "column"), ("FABRICATED DEPOSIT", "credit", "column"),
        ("FABRICATED FEE", "debit", "printed")]
    # A category naming anything but a direction stays the description's words.
    spending = [row[:] for row in grid]
    spending[2][2] = "Groceries"
    columns = tables.classify_columns(spending)
    assert columns.direction is None
    assert rows_from_grid(spending, columns, page=1, table_index=0, year_hint=2031)[1].description == \
        "FABRICATED DEPOSIT Groceries"

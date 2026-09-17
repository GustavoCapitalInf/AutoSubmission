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

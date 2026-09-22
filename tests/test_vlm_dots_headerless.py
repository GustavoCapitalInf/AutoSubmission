"""Fabricated layout regressions for dots' headerless single-money tables."""
from decimal import Decimal
import html

import pytest

from vlm.assemble import parse_dots_layout, rows_from_grid
from vlm.tables import classify_columns


def _table(grid):
    return '<table>' + ''.join('<tr>' + ''.join('<td>' + html.escape(cell) + '</td>'
                                                for cell in row) + '</tr>' for row in grid) + '</table>'


def _dots(grid, heading=None):
    blocks = []
    if heading is not None:
        blocks.append({'category': 'Section-header', 'bbox': [0, 0, 100, 10], 'text': heading})
    blocks.append({'category': 'Table', 'bbox': [0, 10, 100, 100], 'text': _table(grid)})
    return parse_dots_layout(blocks, page=1, width=100, height=100, year_hint=2031)


def test_dots_retains_headerless_date_description_single_amount_without_guessing_credit():
    grid = [['01/02', '  SYNTHETIC  exact text ', '12.34'],
            ['01/03', 'SYNTHETIC signed row', '-5.00']]
    rows = _dots(grid).rows
    assert len(rows) == 2
    assert rows[0].description == 'SYNTHETIC  exact text'
    assert [(row.amount, row.balance, row.direction, row.direction_source) for row in rows] == [
        (Decimal('12.34'), None, 'unknown', 'printed'),
        (Decimal('5.00'), None, 'debit', 'printed')]
    assert all(row.printed_amount is None for row in rows)


def test_other_column_classifier_consumers_keep_historical_default():
    grid = [['01/02', 'SYNTHETIC exact text', '12.34']]
    old = classify_columns(grid)
    opted_in = classify_columns(grid, headerless_transaction_amount=True)
    assert old.amount is None and old.balance == 2
    assert rows_from_grid(grid, old, page=1, table_index=0) == []
    assert opted_in.amount == 2 and opted_in.balance is None


@pytest.mark.parametrize('grid', [
    [['01/02', '510.00'], ['01/03', '515.00']],
    [['01/02', '', '510.00'], ['01/03', '', '515.00']],
    [['Date', 'Description', 'Balance'], ['01/02', 'Opening snapshot', '510.00']],
    [['Date', 'Daily balance'], ['01/02', '510.00']],
    [['', '', 'Daily balance'], ['01/02', 'Snapshot', '510.00'], ['01/03', 'Snapshot', '515.00']],
])
def test_balance_only_and_explicitly_labeled_balance_tables_stay_out(grid):
    assert _dots(grid).rows == ()


@pytest.mark.parametrize('heading', ['Daily Balances', 'Daily Ledger Balances', 'Balance Summary'])
def test_explicit_balance_section_does_not_enable_transaction_fallback(heading):
    assert _dots([['01/02', 'SYNTHETIC snapshot', '510.00']], heading=heading).rows == ()


def test_existing_amount_plus_balance_mapping_is_unchanged():
    grid = [['01/02', 'SYNTHETIC credit', '10.00', '510.00'],
            ['01/03', 'SYNTHETIC debit', '-5.00', '505.00']]
    old = classify_columns(grid)
    assert classify_columns(grid, headerless_transaction_amount=True) == old
    rows = _dots(grid).rows
    assert [(row.amount, row.balance) for row in rows] == [
        (Decimal('10.00'), Decimal('510.00')), (Decimal('5.00'), Decimal('505.00'))]


def test_explicit_debit_credit_columns_keep_their_printed_directions():
    grid = [['Date', 'Description', 'Debits', 'Credits', 'Balance'],
            ['01/02', 'SYNTHETIC credit', '', '10.00', '510.00'],
            ['01/03', 'SYNTHETIC debit', '5.00', '', '505.00']]
    assert classify_columns(grid, headerless_transaction_amount=True) == classify_columns(grid)
    rows = _dots(grid).rows
    assert [row.direction for row in rows] == ['credit', 'debit']
    assert [row.printed_amount for row in rows] == [Decimal('10.00'), Decimal('5.00')]


def test_a_printed_transaction_section_can_still_supply_direction():
    rows = _dots([['01/02', 'SYNTHETIC receipt', '10.00']], heading='Deposits and Credits').rows
    assert len(rows) == 1 and rows[0].direction == 'credit' and rows[0].direction_source == 'section'


def _fragmented_card_rows():
    rows = []
    for index in range(54):
        reference = ['1111', '2222'][index % 2]
        description = ['SYNTHETIC Card purchase' if index < 34 else 'SYNTHETIC purchase',
                       'FABRICATED MERCHANT', 'FABRICATED LOCATION']
        if index < 39:
            suffix = reference
        elif index < 44:
            description[-1], suffix = '1111', ''
        else:
            suffix = ''
        rows.append(['01/02', *description, suffix, f'{index + 1}.25'])
    return rows


def test_fragmented_optional_card_suffix_is_description_and_decimal_column_is_amount():
    grid = _fragmented_card_rows()
    rows = _dots(grid).rows
    assert len(rows) == 54
    for source, row in zip(grid, rows):
        assert row.amount == Decimal(source[-1])
        assert row.balance is None
        assert row.description == ' '.join(cell for cell in source[1:-1] if cell)
        assert row.direction == 'unknown' and row.printed_amount is None
    assert classify_columns(grid).amount == 4  # Other consumers retain historical behavior.


@pytest.mark.parametrize('change', ['no_card_context', 'no_fragment_shift', 'unproven_suffix',
                                   'no_optional_suffix', 'non_decimal_last_column'])
def test_ambiguous_numeric_fragments_are_not_reinterpreted_as_card_references(change):
    grid = _fragmented_card_rows()
    if change == 'no_card_context':
        for row in grid:
            row[1] = row[1].replace('Card ', '')
    elif change == 'no_fragment_shift':
        for row in grid:
            if row[3] == '1111':
                row[3] = 'FABRICATED LOCATION'
    elif change == 'unproven_suffix':
        grid[35][4] = '3333'
    elif change == 'no_optional_suffix':
        for row in grid:
            row[4] = '1111'
    elif change == 'non_decimal_last_column':
        for row in grid:
            row[-1] = row[-1].split('.')[0]
    assert classify_columns(grid, headerless_transaction_amount=True) == classify_columns(grid)


def test_integer_amount_and_decimal_balance_remain_financial_columns():
    grid = [['01/02', 'SYNTHETIC Card payment', '1000', '2000.25'],
            ['01/03', 'SYNTHETIC Card payment', '500', '1500.25']]
    columns = classify_columns(grid, headerless_transaction_amount=True)
    assert columns == classify_columns(grid)
    assert columns.amount == 2 and columns.balance == 3
    rows = _dots(grid).rows
    assert [(row.amount, row.balance) for row in rows] == [
        (Decimal('1000'), Decimal('2000.25')), (Decimal('500'), Decimal('1500.25'))]


def test_explicit_integer_amount_and_balance_headers_override_fragment_heuristic():
    grid = [['Date', 'Description', 'Merchant', 'Location', 'Amount', 'Balance'], *_fragmented_card_rows()]
    columns = classify_columns(grid, headerless_transaction_amount=True)
    assert columns == classify_columns(grid)
    assert columns.amount == 4 and columns.balance == 5

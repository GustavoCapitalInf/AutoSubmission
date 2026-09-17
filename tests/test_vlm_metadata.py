from decimal import Decimal

from vlm import metadata as md

LINES = [
    "SYNTHETIC BANK",
    "Account Number: XXXX-XXXX-0001",
    "Statement Period 01/01/2031 - 01/31/2031",
    "Beginning Balance 500.00",
    "Deposits and Credits 360.00",
    "Ending Balance",
    "860.00",
    "All amounts in CAD",
]


def test_extract_meta_rules():
    meta = md.extract_meta(LINES)
    assert meta.beginning_balance == Decimal("500.00") and meta.ending_balance == Decimal("860.00")
    assert (meta.period_start, meta.period_end) == ("2031-01-01", "2031-01-31")
    assert meta.currency == "CAD" and meta.account_last4 == "0001"
    assert "beginning:rule" in meta.sources and "ending:rule" in meta.sources and "period:rule" in meta.sources


def test_extract_meta_missing_fields_are_none():
    meta = md.extract_meta(["nothing here"])
    assert meta.beginning_balance is None and meta.period_start is None and meta.currency is None
    assert meta.sources == ()


def test_merge_meta_first_non_null_wins():
    a = md.extract_meta(["Ending Balance 10.00"])
    b = md.extract_meta(["Beginning Balance 5.00", "Ending Balance 99.00"])
    merged = md.merge_meta(a, b)
    assert merged.ending_balance == Decimal("10.00") and merged.beginning_balance == Decimal("5.00")


def test_year_from_meta():
    assert md.year_from_meta(md.extract_meta(LINES)) == 2031
    assert md.year_from_meta(md.extract_meta([])) is None

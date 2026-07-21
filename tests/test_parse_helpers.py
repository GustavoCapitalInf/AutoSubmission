from ocr.parse_helpers import parse_money, find_amounts, normalize_date

def test_parse_money_variants():
    assert parse_money("$1,234.56") == 1234.56
    assert parse_money("(45.00)") == 45.0
    assert parse_money("1,000.00-") == 1000.0
    assert parse_money("hello") is None

def test_find_amounts_reading_order():
    assert find_amounts("02/03 ACME 250.00 984.56") == ["250.00", "984.56"]

def test_normalize_date_infers_year():
    assert normalize_date("02/03", 2026) == "2026-02-03"
    assert normalize_date("02/03/2025", None) == "2025-02-03"
    assert normalize_date("garbage", 2026) is None

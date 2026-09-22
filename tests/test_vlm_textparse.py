from decimal import Decimal

from vlm import textparse as tp


def test_parse_money_shapes():
    assert tp.parse_money("1,234.56") == Decimal("1234.56")
    assert tp.parse_money("$1,234.56") == Decimal("1234.56")
    assert tp.parse_money("(1,234.56)") == Decimal("-1234.56")
    assert tp.parse_money("1,234.56-") == Decimal("-1234.56")
    assert tp.parse_money("-12.00") == Decimal("-12.00")
    assert tp.parse_money("−12.00") == Decimal("-12.00")
    assert tp.parse_money("12.00 CR") == Decimal("12.00")
    assert tp.parse_money("12.00 DR") == Decimal("-12.00")
    assert tp.parse_money("CAD 5.00") == Decimal("5.00")
    assert tp.parse_money("500") == Decimal("500.00")
    assert tp.parse_money("") is None and tp.parse_money("abc") is None and tp.parse_money("01/02") is None
    assert tp.parse_money("1.2.3") is None


def test_is_money_like_and_date_like():
    assert tp.is_money_like("1,234.56") and tp.is_money_like("(3.00)") and not tp.is_money_like("Jan 3")
    assert tp.is_date_like("01/02/2031") and tp.is_date_like("Jan 3") and tp.is_date_like("2031-01-02")
    assert not tp.is_date_like("1,234.56") and not tp.is_date_like("SYNTHETIC")


def test_parse_date_formats():
    assert tp.parse_date("2031-01-02") == "2031-01-02"
    assert tp.parse_date("01/02/2031") == "2031-01-02"
    assert tp.parse_date("1/2/31") == "2031-01-02"
    assert tp.parse_date("01/02", year_hint=2031) == "2031-01-02"
    assert tp.parse_date("01/02") is None
    assert tp.parse_date("Jan 2, 2031") == "2031-01-02"
    assert tp.parse_date("2 Jan 2031") == "2031-01-02"
    assert tp.parse_date("Jan 2", year_hint=2031) == "2031-01-02"
    assert tp.parse_date("02/01/2031", day_first=True) == "2031-01-02"
    assert tp.parse_date("13/01/2031") == "2031-01-13"
    assert tp.parse_date("2031-02-30") is None and tp.parse_date("garbage") is None


def test_normalise_description_and_decimals():
    assert tp.normalise_description("  POS  Purchase\tSTORE #12 ") == "pos purchase store 12"
    assert tp.to_decimal(530.0) == Decimal("530.00") and tp.to_decimal("1,000") == Decimal("1000.00")
    assert tp.money_str(Decimal("-5")) == "-5.00"

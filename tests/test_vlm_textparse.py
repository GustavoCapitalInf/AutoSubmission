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


def test_parse_money_decimal_comma_as_french_and_canadian_statements_print_it():
    assert tp.parse_money("3 000,00") == Decimal("3000.00")
    assert tp.parse_money("3 000,00") == Decimal("3000.00") and tp.parse_money("3 000,00") == Decimal("3000.00")
    assert tp.parse_money("1 234 567,89") == Decimal("1234567.89")
    assert tp.parse_money("1.234,56") == Decimal("1234.56")
    assert tp.parse_money("218,37") == Decimal("218.37")
    assert tp.parse_money("-307,62") == Decimal("-307.62")
    assert tp.parse_money("25,19 $") == Decimal("25.19") and tp.parse_money("5.00 CAD") == Decimal("5.00")
    # Cents printed without a leading zero (a one-cent credit on Citizens statements).
    assert tp.parse_money(".01") == Decimal("0.01") and tp.parse_money("(.01)") == Decimal("-0.01")
    assert tp.parse_money(".5") is None
    # US thousands without cents stay US; a comma with three digits after it is never a decimal comma.
    assert tp.parse_money("12,345") == Decimal("12345.00")
    assert tp.parse_money("3 000") is None and tp.parse_money("1,2") is None


def test_parse_date_french_month_names_with_or_without_accents():
    for text, iso in (("16 oct", "2025-10-16"), ("12 déc", "2025-12-12"), ("12 dec", "2025-12-12"),
                      ("3 févr", "2025-02-03"), ("3 fevr.", "2025-02-03"), ("15 août", "2025-08-15"),
                      ("2 janv", "2025-01-02"), ("9 juil", "2025-07-09"), ("6 juin", "2025-06-06"),
                      ("4 avr", "2025-04-04"), ("5 mai", "2025-05-05"), ("8 sept", "2025-09-08"),
                      ("1 décembre 2024", "2024-12-01")):
        assert tp.parse_date(text, year_hint=2025) == iso, text
    assert tp.is_date_like("15 août") and tp.is_date_like("3 févr")
    # Whole month words only (review 4): a street or a word that starts like a month is not a date.
    assert not any(tp.is_date_like(text) for text in ("Main 12", "Mail 5", "Maison 3", "Marsh 4", "Decker 7"))
    assert tp.is_date_like("Sept. 9") and tp.is_date_like("December 31, 2025") and tp.is_date_like("9 juillet")
    # A trailing three-letter word is a currency only when it is one.
    assert tp.parse_money("25.00 ACH") is None and tp.parse_money("35.00 NSF") is None
    assert tp.parse_money("25.00 CAD") == Decimal("25.00")
    assert tp.month_number("Juillet") == 7 and tp.month_number("juin") == 6 and tp.month_number("xyz") is None


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

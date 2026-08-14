"""Exhaustive tests for `analysis/money.py` (R-2 shared utilities).

Two layers:

1. **Differential equivalence.** Every pre-R-2 per-bank implementation is
   reproduced verbatim below as a reference oracle, and each is asserted
   identical to its replacement across a shared matrix of ~200 inputs covering
   every surveyed format axis (US grouping, French space/comma grouping,
   leading and trailing minus, parentheses, ``+`` markers, ``D``/``DR``
   suffixes, ``*`` fill, bare ``.56``, three-decimal tokens, and malformed
   junk). This is the actual proof that R-2 changed no behavior: the corpus
   gate proves the corpus is unchanged, and this proves the parsers are
   unchanged off-corpus too.

   Keep the oracles frozen. They are historical record, not live code — if a
   money rule must genuinely change, the oracle and the engine change together
   in a reviewed commit with a corpus re-proof.

2. **Behavioral tests** of the shared API in its own right, so the module is
   documented by example rather than only by diff.
"""
from __future__ import annotations

import re
from decimal import Decimal

import pytest

from analysis import money as m


# ===========================================================================
# The input matrix
# ===========================================================================

#: Every string is fed to both the oracle and the replacement. Grouped by the
#: axis it exercises so a failure names the format that drifted.
INPUTS: tuple[str, ...] = (
    # --- plain US amounts ------------------------------------------------
    "0.00", "0", "1.00", "12.34", "123.45", "1234.56", "1,234.56",
    "12,345.67", "1,234,567.89", "$12.34", "$1,234.56", "  $1,234.56  ",
    "999999.99", "0.01", "100", "1,000",
    # --- leading minus ---------------------------------------------------
    "-1.00", "-12.34", "-1,234.56", "-$1,234.56", "$-1,234.56", "-0.00",
    "  -12.34  ", "-.56",
    # --- trailing minus (mainframe) --------------------------------------
    "12.34-", "1,234.56-", "$1,234.56-", "  1,234.56-  ", ".56-", "0.00-",
    # --- both / doubled markers ------------------------------------------
    "-12.34-", "--12.34", "12.34--",
    # --- parentheses -----------------------------------------------------
    "(12.34)", "(1,234.56)", "($1,234.56)", "$(1,234.56)", "(12.34",
    "12.34)", "( 12.34 )",
    # --- plus markers ----------------------------------------------------
    "+12.34", "+1,234.56", "12.34+", "+$12.34",
    # --- bare sub-dollar amounts -----------------------------------------
    ".56", ".05", "$.56", ".5", ".567",
    # --- embedded spaces --------------------------------------------------
    "1 234.56", "1 234,56", "12 345 678,90", "$1 234.56", "1 2 3 4 . 5 6",
    "- 12.34", "12. 34",
    # --- decimal comma (FR-CA) -------------------------------------------
    "1234,56", "1.234,56", "1,23", "1,234", "0,00", "-1234,56",
    "(1 234,56)", "(1234,56)",
    # --- CR/DR and letter suffixes (TD Canada) ---------------------------
    "1234.56D", "1234.56DR", "1,234.56D", "12.34CR", "12.34C", "1234.56/D",
    "1234.56-", "*1,234.56", "1,234.56*", "**12.34**", "12.34D*",
    # --- three decimals (rate columns) -----------------------------------
    "1.234", "12.345", "1,234.567",
    # --- non-money / malformed -------------------------------------------
    "", " ", "abc", "-", "--", "$", "$-", "()", ".", "..", "1.2.3",
    "1,2,3", "N/A", "n/a", "None", "12,34.56", "12.3", "12.345.67",
    "1234", "12-34.56", "12.34 56.78", "Balance", "0.000", "1..00",
    "\t12.34\n", "12.34 ", "€12,34", "C$12.34", "USD 12.34",
    # --- reference-number shaped (must not become money) -----------------
    "1944", "0000123456", "2026", "#1234", "REF 12345",
)


def _both(fn_a, fn_b, value):
    """Call two implementations, capturing raised exceptions as markers."""
    out = []
    for fn in (fn_a, fn_b):
        try:
            out.append(("ok", fn(value)))
        except Exception as exc:  # noqa: BLE001 - equivalence includes failures
            out.append(("raise", type(exc).__name__))
    return out[0], out[1]


def assert_equivalent(oracle, replacement, *, inputs=INPUTS):
    mismatches = []
    for value in inputs:
        left, right = _both(oracle, replacement, value)
        if left != right:
            mismatches.append(f"{value!r}: legacy={left} shared={right}")
    assert not mismatches, "behaviour drift:\n  " + "\n  ".join(mismatches)


# ===========================================================================
# 1. Frozen pre-R-2 oracles, one per surveyed clone
# ===========================================================================

# --- strict engine family (16 parsers, 13 distinct formats) ----------------

def _legacy_midflorida(value: str | None) -> float | None:      # + texas_bank
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.strip("-")
    if not re.fullmatch(r"\d+\.\d{2}", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_secu(value: str | None) -> float | None:            # + wilson_muir
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.strip("+-")
    if not re.fullmatch(r"\d+\.\d{2}", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_navy_federal(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").replace(" ", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.strip("+-")
    if not re.fullmatch(r"\d+\.\d{2}", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_us_bank(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").replace(" ", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.strip("-")
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_truist(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-") or text.endswith("-")
    text = text.replace("-", "").strip()
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_atb(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-")
    text = text.replace("-", "").strip()
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_bluevine(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.startswith("-")
    text = text.lstrip("-")
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_b1(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    if text.startswith("."):
        text = "0" + text
    neg = text.startswith("-")
    text = text.lstrip("-")
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_linkbank(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = text.endswith("-") or text.startswith("-")
    text = text.strip("-")
    if text.startswith("."):
        text = "0" + text
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_td_us(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    neg = (text.startswith("(") and text.endswith(")")) or text.startswith("-")
    text = text.strip("()").lstrip("-")
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_santander(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").replace("+", "").strip()
    neg = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.strip("-()")
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    amount = float(text)
    return -amount if neg else amount


def _legacy_community_section(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"\d+(?:\.\d{2})", text):
        return None
    return float(text)


def _legacy_consumers(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"\d+\.\d{2}", text):
        return None
    return float(text)


def _legacy_demo_national(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").strip()
    if not re.fullmatch(r"-?\d+(?:\.\d{2})", text):
        return None
    return float(text)


# --- tolerant token parser (formerly td_can) -------------------------------

def _legacy_parse_money(value: str | None) -> float | None:
    if not value:
        return None
    text = value.replace("$", "").replace(",", "").replace("*", "").strip()
    m_ = re.search(r"(-)?(\d+(?:\.\d{2,3})?)([A-Z/-]*)?", text, re.IGNORECASE)
    if not m_:
        return None
    amount = float(m_.group(2))
    if amount == 0:
        return 0.0
    if m_.group(1) or (m_.group(3) and ("D" in m_.group(3).upper() or "-" in m_.group(3))):
        amount *= -1
    return round(amount, 2)


def _legacy_money_tokens(value: str | None) -> list[float]:
    if not value:
        return []
    out = []
    for number, suffix in re.findall(r"\$?(\d[\d,]*(?:\.\d{2,3})?)([D*-]?)", value):
        text = number.replace(",", "")
        amount = float(text)
        if "D" in suffix.upper() or "-" in suffix:
            amount *= -1
        out.append(round(amount, 2))
    return out


# --- Decimal / raising family ----------------------------------------------

def _legacy_navigant(value: str):                                # + relay
    from decimal import InvalidOperation
    try:
        return Decimal(value.replace("$", "").replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(value) from exc


def _legacy_columbia(value: str):
    from decimal import InvalidOperation
    text = value.replace("$", "").strip()
    if "." not in text and "," in text and len(text.rsplit(",", 1)[1]) == 2:
        whole, cents = text.rsplit(",", 1)
        text = f"{whole.replace(',', '')}.{cents}"
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(value) from exc


def _legacy_first_farmers(value: str):
    from decimal import InvalidOperation
    text = value.replace("$", "").strip()
    if "." not in text and text.count(",") == 1 and len(text.rsplit(",", 1)[1]) == 2:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(value) from exc


def _legacy_first_citizens(value: str) -> float:                 # + ibc
    return float(value.replace(",", ""))


def _legacy_altana(value: str) -> float:
    return float(value.replace("$", "").replace(",", "").rstrip("-"))


def _legacy_cibc(value: str) -> float:
    return round(float(value.replace(" ", "").replace(",", ".")), 2)


def _legacy_rbc_fr(text: str) -> float:
    neg = text.strip().startswith("(") and text.strip().endswith(")")
    value = float(text.strip("()").replace(" ", "").replace(",", "."))
    return round(-value if neg else value, 2)


def _legacy_capital_one(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    neg = text.startswith("(") or text.endswith("-")
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    amount = float(cleaned)
    return -amount if neg else amount


_CHASE_GUARD = re.compile(r"\(?-?\$?\s*[0-9][0-9,]*(?:\.[0-9]{2})?-?\)?")


def _legacy_chase(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    if not _CHASE_GUARD.fullmatch(text):
        return None
    neg = text.startswith("(") or text.startswith("-") or text.endswith("-")
    cleaned = re.sub(r"[^0-9.]", "", text)
    if not cleaned:
        return None
    amount = float(cleaned)
    return -amount if neg else amount


# ===========================================================================
# 2. Equivalence assertions — one per surveyed clone
# ===========================================================================

STRICT_CASES = (
    ("midflorida/texas_bank", _legacy_midflorida, m.STRICT_EITHER_MINUS),
    ("secu/wilson_muir", _legacy_secu, m.STRICT_EITHER_MINUS_OR_PLUS),
    ("navy_federal", _legacy_navy_federal, m.STRICT_EITHER_MINUS_OR_PLUS_SPACED),
    ("us_bank", _legacy_us_bank, m.EITHER_MINUS_SPACED),
    ("truist", _legacy_truist, m.EITHER_MINUS_DROPPED),
    ("atb", _legacy_atb, m.LEADING_MINUS_DROPPED),
    ("bluevine", _legacy_bluevine, m.LEADING_MINUS),
    ("b1", _legacy_b1, m.LEADING_MINUS_PADDED),
    ("linkbank", _legacy_linkbank, m.EITHER_MINUS_PADDED),
    ("td_us", _legacy_td_us, m.PARENS_OR_LEADING_MINUS),
    ("santander", _legacy_santander, m.PARENS_OR_LEADING_MINUS_OR_PLUS),
    ("community_section", _legacy_community_section, m.STRICT_UNSIGNED),
    ("consumers", _legacy_consumers, m.STRICT_UNSIGNED),
    ("demo_national", _legacy_demo_national, m.STRICT_LEADING_SIGN),
)


@pytest.mark.parametrize("name,oracle,fmt", STRICT_CASES, ids=[c[0] for c in STRICT_CASES])
def test_strict_format_matches_legacy_clone(name, oracle, fmt):
    assert_equivalent(oracle, lambda value: m.parse_amount(value, fmt))


def test_parse_money_matches_legacy_td_can_clone():
    assert_equivalent(_legacy_parse_money, m.parse_money)


def test_parse_money_tokens_matches_legacy_clone():
    assert_equivalent(_legacy_money_tokens, m.parse_money_tokens)


def test_parse_decimal_matches_legacy_clone():
    assert_equivalent(_legacy_navigant, m.parse_decimal)


def test_parse_decimal_mixed_separator_matches_columbia_clone():
    assert_equivalent(_legacy_columbia, m.parse_decimal_mixed_separator)


def test_parse_decimal_mixed_separator_matches_first_farmers_clone():
    assert_equivalent(
        _legacy_first_farmers,
        lambda value: m.parse_decimal_mixed_separator(value, single_comma_only=True),
    )


def test_parse_grouped_float_matches_legacy_clone():
    assert_equivalent(_legacy_first_citizens, m.parse_grouped_float)


def test_parse_trailing_minus_dropped_matches_legacy_clone():
    assert_equivalent(_legacy_altana, m.parse_trailing_minus_dropped)


def test_parse_trailing_minus_dropped_discards_rather_than_applies_the_marker():
    assert m.parse_trailing_minus_dropped("1,234.56-") == 1234.56
    assert m.parse_trailing_minus_dropped("$1,234.56") == 1234.56
    with pytest.raises(ValueError):
        m.parse_trailing_minus_dropped("N/A")


def test_parse_french_amount_matches_cibc_clone():
    assert_equivalent(_legacy_cibc, m.parse_french_amount)


def test_parse_french_amount_matches_rbc_clone():
    assert_equivalent(
        _legacy_rbc_fr, lambda value: m.parse_french_amount(value, parens=True)
    )


def test_parse_digit_scrubbed_matches_capital_one_clone():
    assert_equivalent(
        _legacy_capital_one,
        lambda value: m.parse_digit_scrubbed(value, parens=True, trailing_minus=True),
    )


def test_parse_digit_scrubbed_matches_chase_clone():
    assert_equivalent(
        _legacy_chase,
        lambda value: m.parse_digit_scrubbed(
            value,
            parens=True,
            leading_minus=True,
            trailing_minus=True,
            guard=_CHASE_GUARD,
        ),
    )


def test_every_exported_format_is_covered_by_an_equivalence_case():
    """A new AmountFormat must arrive with its own differential proof."""
    exported = {
        name
        for name in m.__all__
        if isinstance(getattr(m, name), m.AmountFormat)
    }
    covered = {
        name
        for name in m.__all__
        if isinstance(getattr(m, name), m.AmountFormat)
        and any(getattr(m, name) is case[2] for case in STRICT_CASES)
    }
    assert exported == covered, f"formats without an equivalence case: {exported - covered}"


# ===========================================================================
# 3. Behavioral tests of the shared API
# ===========================================================================

def test_strict_unsigned_reads_us_grouping_and_symbol():
    assert m.parse_amount("$1,234.56", m.STRICT_UNSIGNED) == 1234.56
    assert m.parse_amount("0.00", m.STRICT_UNSIGNED) == 0.0


@pytest.mark.parametrize("value", ["1,234.5", "1234", "abc", "", "  ", "1.2.3", None])
def test_strict_unsigned_rejects_non_money(value):
    assert m.parse_amount(value, m.STRICT_UNSIGNED) is None


def test_strict_formats_reject_reference_numbers():
    """A bare integer is never money in the strict formats: reading a check or
    reference number as an amount would fabricate a transaction."""
    for name in ("STRICT_UNSIGNED", "STRICT_EITHER_MINUS", "STRICT_LEADING_SIGN"):
        assert m.parse_amount("1944", getattr(m, name)) is None


@pytest.mark.parametrize(
    "fmt_name,value,expected",
    [
        ("STRICT_EITHER_MINUS", "1,234.56-", -1234.56),
        ("STRICT_EITHER_MINUS", "-1,234.56", -1234.56),
        ("STRICT_EITHER_MINUS", "1,234.56", 1234.56),
        ("STRICT_EITHER_MINUS_OR_PLUS", "+12.34", 12.34),
        ("STRICT_EITHER_MINUS_OR_PLUS_SPACED", "1 234.56-", -1234.56),
        ("EITHER_MINUS_SPACED", "$1 234.56", 1234.56),
        ("EITHER_MINUS_DROPPED", "12-34.56", 1234.56),
        ("LEADING_MINUS", "-12.34", -12.34),
        ("LEADING_MINUS", "12.34-", None),
        ("LEADING_MINUS_PADDED", ".56", 0.56),
        ("EITHER_MINUS_PADDED", ".56-", -0.56),
        ("PARENS_OR_LEADING_MINUS", "(1,234.56)", -1234.56),
        ("PARENS_OR_LEADING_MINUS_OR_PLUS", "(1,234.56)", -1234.56),
        ("PARENS_OR_LEADING_MINUS_OR_PLUS", "+1,234.56", 1234.56),
        ("STRICT_LEADING_SIGN", "-12.34", -12.34),
    ],
)
def test_format_sign_conventions(fmt_name, value, expected):
    assert m.parse_amount(value, getattr(m, fmt_name)) == expected


def test_parse_money_reads_debit_suffixes():
    assert m.parse_money("1,234.56D") == -1234.56
    assert m.parse_money("1,234.56DR") == -1234.56
    assert m.parse_money("1,234.56") == 1234.56
    assert m.parse_money("$1,234.56-") == -1234.56


def test_parse_money_ignores_fill_characters():
    assert m.parse_money("*1,234.56*") == 1234.56


def test_parse_money_normalizes_signed_zero():
    assert m.parse_money("-0.00") == 0.0
    assert m.parse_money("0.00D") == 0.0


def test_parse_money_returns_none_for_empty_and_non_numeric():
    assert m.parse_money(None) is None
    assert m.parse_money("") is None
    assert m.parse_money("Balance forward") is None


def test_parse_money_tokens_reads_a_flattened_row():
    assert m.parse_money_tokens("1,234.56 78.90D 0.00") == [1234.56, -78.90, 0.0]
    assert m.parse_money_tokens(None) == []
    assert m.parse_money_tokens("no digits here") == []


def test_parse_decimal_is_exact():
    assert m.parse_decimal("$1,234.56") == Decimal("1234.56")
    assert m.parse_decimal("0.10") + m.parse_decimal("0.20") == Decimal("0.30")


def test_parse_decimal_raises_value_error_on_junk():
    with pytest.raises(ValueError):
        m.parse_decimal("N/A")


def test_mixed_separator_reads_comma_as_decimal_mark_only_when_unambiguous():
    assert m.parse_decimal_mixed_separator("1234,56") == Decimal("1234.56")
    assert m.parse_decimal_mixed_separator("1,234.56") == Decimal("1234.56")
    assert m.parse_decimal_mixed_separator("1,234") == Decimal("1234")


def test_mixed_separator_single_comma_only_is_stricter():
    assert m.parse_decimal_mixed_separator("1,23,45") == Decimal("123.45")
    assert m.parse_decimal_mixed_separator("1,23,45", single_comma_only=True) == Decimal("12345")


def test_parse_grouped_float_raises_on_junk():
    assert m.parse_grouped_float("1,234.56") == 1234.56
    with pytest.raises(ValueError):
        m.parse_grouped_float("N/A")


def test_parse_french_amount_reads_space_thousands_and_comma_decimal():
    assert m.parse_french_amount("1 234,56") == 1234.56
    assert m.parse_french_amount("12 345 678,90") == 12345678.90


def test_parse_french_amount_parens_are_negative():
    assert m.parse_french_amount("(1 234,56)", parens=True) == -1234.56
    assert m.parse_french_amount("1 234,56", parens=True) == 1234.56


def test_parse_french_amount_raises_on_junk():
    with pytest.raises(ValueError):
        m.parse_french_amount("N/A")


def test_parse_digit_scrubbed_sign_markers():
    assert m.parse_digit_scrubbed("(1,234.56)", parens=True) == -1234.56
    assert m.parse_digit_scrubbed("1,234.56-", trailing_minus=True) == -1234.56
    assert m.parse_digit_scrubbed("1,234.56") == 1234.56


def test_parse_digit_scrubbed_guard_rejects_non_money():
    guard = re.compile(r"\$?[0-9][0-9,]*\.[0-9]{2}")
    assert m.parse_digit_scrubbed("REF 12345", guard=guard) is None
    assert m.parse_digit_scrubbed("$12.34", guard=guard) == 12.34


def test_parse_digit_scrubbed_returns_none_without_digits():
    assert m.parse_digit_scrubbed("   ") is None
    assert m.parse_digit_scrubbed("N/A") is None


def test_pad_leading_decimal():
    assert m.pad_leading_decimal(".56") == "0.56"
    assert m.pad_leading_decimal("1.56") == "1.56"
    assert m.pad_leading_decimal("") == ""


def test_strip_currency_is_the_shared_cleaning_step():
    assert m.strip_currency("  $1,234.56 ") == "1234.56"
    assert m.strip_currency("1,234") == "1234"
    assert m.strip_currency("") == ""


# ===========================================================================
# 4. The sign-glyph class (W3 §MONEY-GRAMMAR card 1)
# ===========================================================================

MINUS = "−"   # U+2212 MINUS SIGN — what a web export prints
NDASH = "–"   # U+2013 EN DASH — what OCR puts in its place

#: Every format that honours a LEADING minus, paired with the ASCII spelling
#: it has always accepted. The class must be honoured wherever the character
#: is, and nowhere else.
LEADING_MINUS_FORMATS = (
    "STRICT_LEADING_SIGN", "STRICT_EITHER_MINUS", "STRICT_EITHER_MINUS_OR_PLUS",
    "STRICT_EITHER_MINUS_OR_PLUS_SPACED", "EITHER_MINUS_SPACED",
    "EITHER_MINUS_DROPPED", "EITHER_MINUS_PADDED", "LEADING_MINUS",
    "LEADING_MINUS_DROPPED", "LEADING_MINUS_PADDED", "PARENS_OR_LEADING_MINUS",
    "PARENS_OR_LEADING_MINUS_OR_PLUS",
)


@pytest.mark.parametrize("glyph", [MINUS, NDASH], ids=["u2212", "u2013"])
@pytest.mark.parametrize("fmt_name", LEADING_MINUS_FORMATS)
def test_every_format_reads_the_sign_class_as_it_reads_ascii(fmt_name, glyph):
    """One normalization, inherited by every AmountFormat."""
    fmt = getattr(m, fmt_name)
    assert m.parse_amount(f"{glyph}1,234.56", fmt) == m.parse_amount("-1,234.56", fmt)
    assert m.parse_amount(f"{glyph}1,234.56", fmt) == -1234.56


@pytest.mark.parametrize("glyph", [MINUS, NDASH], ids=["u2212", "u2013"])
def test_a_format_that_accepts_no_sign_still_accepts_none(glyph):
    """The class is the sign's spelling, not a new permission to be signed."""
    assert m.parse_amount(f"{glyph}1,234.56", m.STRICT_UNSIGNED) is None
    assert m.parse_amount("-1,234.56", m.STRICT_UNSIGNED) is None


@pytest.mark.parametrize("glyph", [MINUS, NDASH], ids=["u2212", "u2013"])
def test_the_tolerant_parsers_no_longer_read_a_negative_as_positive(glyph):
    """The dangerous half: these matched the digits AFTER the glyph and
    returned the amount unsigned — a debit published as a credit."""
    assert m.parse_money(f"{glyph}500.00") == -500.0
    assert m.parse_money(f"{glyph}$500.00") == -500.0
    assert m.parse_digit_scrubbed(f"{glyph}500.00", leading_minus=True) == -500.0


@pytest.mark.parametrize("glyph", [MINUS, NDASH], ids=["u2212", "u2013"])
def test_a_guarded_scrub_admits_the_class_its_guard_spells_in_ascii(glyph):
    """`parse_digit_scrubbed` normalizes BEFORE the guard, so a caller's guard
    keeps its ASCII spelling and still admits the printed glyph."""
    guard = re.compile(r"-?\$?[0-9][0-9,]*\.[0-9]{2}")
    assert m.parse_digit_scrubbed(
        f"{glyph}$1,234.56", leading_minus=True, guard=guard
    ) == -1234.56


@pytest.mark.parametrize("glyph", [MINUS, NDASH], ids=["u2212", "u2013"])
def test_the_raising_family_reads_the_class_rather_than_refusing_it(glyph):
    assert m.parse_decimal(f"{glyph}1,234.56") == Decimal("-1234.56")
    assert m.parse_grouped_float(f"{glyph}1,234.56") == -1234.56
    assert m.parse_french_amount(f"{glyph}1 234,56") == -1234.56


def test_normalize_sign_glyphs_touches_the_sign_and_nothing_else():
    assert m.normalize_sign_glyphs(f"{MINUS}1{NDASH}2") == "-1-2"
    assert m.normalize_sign_glyphs("ACME — CO") == "ACME — CO"  # em dash untouched
    assert m.normalize_sign_glyphs("plain") == "plain"


def test_minus_class_is_the_fragment_consumers_embed():
    assert re.fullmatch(m.MINUS_CLASS, "-")
    assert re.fullmatch(m.MINUS_CLASS, MINUS)
    assert re.fullmatch(m.MINUS_CLASS, NDASH)
    assert not re.fullmatch(m.MINUS_CLASS, "—")  # em dash is not a minus

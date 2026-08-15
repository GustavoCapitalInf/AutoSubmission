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
    # --- the sign class, welded to the amount (W3 §MONEY-GRAMMAR card 1) --
    # Added after the fact: the pre-R-2 matrix had no non-ASCII row at all,
    # so cards 1 and 3 would otherwise sit OUTSIDE the differential proof.
    "−500.00", "–500.00", "−$1,234.56",
    "$1,234.56−", "1,234.56–",
    # --- U+2014 EM DASH, in every position the class rows above occupy ------
    # The glyph the canon RULES OUT (W3 §MGD). These rows carry no divergence
    # declaration anywhere below, and that absence is the finding: to the
    # whole strict engine and to every tolerant parser the em dash was always
    # punctuation, exactly as the frozen pre-R-2 clones read it. Only the
    # shadowed second `MINUS_GLYPHS` disagreed, and it reached just two
    # consumers — `SIGNED_MONEY_TOKEN` and `parse_signed_decimal` — neither of
    # which has a pre-R-2 oracle to sit in this matrix. Their em-dash pins are
    # the behavioural tests in section 4.
    "—500.00", "—$1,234.56", "$1,234.56—", "1,234.56—", "— 500.00",
    # --- digit runs past the bound (card 3) -------------------------------
    "99999999999999.00",                  # 14 integer digits, one past
    "99999999999999999999999999.00",      # 26 — the adb crash width
    "1" * 54,                             # the longest bare run in the archive
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


#: The inputs on which the shared grammar deliberately no longer agrees with
#: the frozen pre-R-2 oracle, each with the card that changed it. The oracles
#: stay frozen — they are the historical record — so a deliberate change is
#: declared HERE, and anything not declared must still be identical.
#:
#: Every entry is one shape: a token that is not a whole money number is no
#: longer read as one (W3 §MONEY-GRAMMAR card 2). The legacy readings are all
#: wrong values rather than refusals, which is why refusing is the fix:
#:
#:   '12.3'       -> 12.0   now None    the one-decimal truncation itself
#:   '1.2.3'      -> 1.0    now None    a version string read as money
#:   '12.345.67'  -> 12.35  now None    two numbers welded, read as one
#:   '1.234,56'   -> 1.23   now None    an FR-CA amount read by the US grammar
#:   '.56'        -> 56.0   now 0.56    a sub-dollar amount, read 100x too
#:                                      large by the legacy clone and now
#:                                      padded (the module's documented
#:                                      tolerance, which never actually held)
#:
#: A layout that prints one decimal pads it at its own call site (scotia).
ONE_DECIMAL_DIVERGENCES: frozenset[str] = frozenset({
    "12.3", "1.2.3", "12.345.67", "1.234,56",
    ".5", ".56", ".05", ".567", "$.56", "-.56", ".56-",
})
#: `parse_money_tokens` scans a whole flattened cell, so it additionally stops
#: emitting the fragments left over from a malformed token.
TOKENS_ONLY_DIVERGENCES: frozenset[str] = frozenset({"1..00"})

# --- card 1 and card 3 divergences over the rows added above ---------------
#: A leading sign glyph, with and without the currency symbol. The symbol
#: matters: a parser that does not strip `$` refuses both spellings either
#: way, so the row is only divergent for the parsers that do.
GLYPH_LEADING_PLAIN: frozenset[str] = frozenset({"−500.00", "–500.00"})
GLYPH_LEADING_DOLLAR: frozenset[str] = frozenset({"−$1,234.56"})
#: A trailing sign glyph — divergent only where a trailing `-` means anything.
GLYPH_TRAILING: frozenset[str] = frozenset({"$1,234.56−", "1,234.56–"})
#: Runs past `MAX_INTEGER_DIGITS`. Divergent EVERYWHERE: the legacy clones all
#: read them as amounts (up to 1e+53), which is what reached `adb.py` and
#: raised `decimal.InvalidOperation` rather than declining the document.
BOUND_DIVERGENCES: frozenset[str] = frozenset({
    "99999999999999.00", "99999999999999999999999999.00", "1" * 54,
})


def _format_reads_a_leading_minus(fmt: m.AmountFormat) -> bool:
    """Either the engine detects the marker, or the pattern admits it."""
    return fmt.leading_minus or fmt.pattern.startswith("-?")


def _format_reacts_to_a_trailing_minus(fmt: m.AmountFormat) -> bool:
    """Honoured as a sign, or merely stripped/deleted — both change the read."""
    return fmt.trailing_minus or "-" in (fmt.strip_chars + fmt.remove_chars)


def strict_divergences(fmt: m.AmountFormat) -> frozenset[str]:
    """The rows on which `fmt` deliberately leaves its pre-R-2 clone behind.

    Derived from the format's OWN declared fields rather than hand-listed per
    bank, which is the stronger claim: card 1 says a format that honours a
    printed minus now honours every spelling of it, and this asserts that
    uniformly across the family. `assert_equivalent` checks it in both
    directions, so an over- or under-declaration fails the test.
    """
    rows = set(BOUND_DIVERGENCES)
    if _format_reads_a_leading_minus(fmt):
        rows |= GLYPH_LEADING_PLAIN | GLYPH_LEADING_DOLLAR
    if _format_reacts_to_a_trailing_minus(fmt):
        rows |= GLYPH_TRAILING
    # a bare 54-digit run has no decimals, so no `ddd.dd` format ever read it
    return frozenset(rows - {"1" * 54})


def assert_equivalent(oracle, replacement, *, inputs=INPUTS, diverges=frozenset()):
    """Every input reads identically to the frozen clone, except the declared
    divergences — which must actually differ, so a stale declaration fails."""
    mismatches, undivergent = [], []
    for value in inputs:
        left, right = _both(oracle, replacement, value)
        if value in diverges:
            if left == right:
                undivergent.append(f"{value!r}: declared divergent but identical ({left})")
        elif left != right:
            mismatches.append(f"{value!r}: legacy={left} shared={right}")
    assert not mismatches, "undeclared behaviour drift:\n  " + "\n  ".join(mismatches)
    assert not undivergent, "stale divergence declaration:\n  " + "\n  ".join(undivergent)


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
    assert_equivalent(oracle, lambda value: m.parse_amount(value, fmt),
                      diverges=strict_divergences(fmt))


def test_parse_money_matches_legacy_td_can_clone():
    assert_equivalent(
        _legacy_parse_money, m.parse_money,
        diverges=(ONE_DECIMAL_DIVERGENCES | BOUND_DIVERGENCES
                  | GLYPH_LEADING_PLAIN | GLYPH_LEADING_DOLLAR | GLYPH_TRAILING),
    )


def test_parse_money_tokens_matches_legacy_clone():
    # no leading-sign rule in this parser, so only the TRAILING glyph moves
    assert_equivalent(
        _legacy_money_tokens, m.parse_money_tokens,
        diverges=(ONE_DECIMAL_DIVERGENCES | TOKENS_ONLY_DIVERGENCES
                  | BOUND_DIVERGENCES | GLYPH_TRAILING),
    )


def test_parse_decimal_matches_legacy_clone():
    assert_equivalent(
        _legacy_navigant, m.parse_decimal,
        diverges=BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN | GLYPH_LEADING_DOLLAR,
    )


def test_parse_decimal_mixed_separator_matches_columbia_clone():
    assert_equivalent(
        _legacy_columbia, m.parse_decimal_mixed_separator,
        diverges=BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN | GLYPH_LEADING_DOLLAR,
    )


def test_parse_decimal_mixed_separator_matches_first_farmers_clone():
    assert_equivalent(
        _legacy_first_farmers,
        lambda value: m.parse_decimal_mixed_separator(value, single_comma_only=True),
        diverges=BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN | GLYPH_LEADING_DOLLAR,
    )


def test_parse_grouped_float_matches_legacy_clone():
    # this one never stripped `$`, so the dollar-bearing glyph row still raises
    assert_equivalent(_legacy_first_citizens, m.parse_grouped_float,
                      diverges=BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN)


def test_parse_trailing_minus_dropped_matches_legacy_clone():
    assert_equivalent(
        _legacy_altana, m.parse_trailing_minus_dropped,
        diverges=(BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN
                  | GLYPH_LEADING_DOLLAR | GLYPH_TRAILING),
    )


def test_parse_trailing_minus_dropped_discards_rather_than_applies_the_marker():
    assert m.parse_trailing_minus_dropped("1,234.56-") == 1234.56
    assert m.parse_trailing_minus_dropped("$1,234.56") == 1234.56
    with pytest.raises(ValueError):
        m.parse_trailing_minus_dropped("N/A")


def test_parse_french_amount_matches_cibc_clone():
    assert_equivalent(_legacy_cibc, m.parse_french_amount,
                      diverges=BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN)


def test_parse_french_amount_matches_rbc_clone():
    assert_equivalent(
        _legacy_rbc_fr, lambda value: m.parse_french_amount(value, parens=True),
        diverges=BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN,
    )


def test_parse_digit_scrubbed_matches_capital_one_clone():
    # capital_one passes no `leading_minus`, so only the trailing glyph moves
    assert_equivalent(
        _legacy_capital_one,
        lambda value: m.parse_digit_scrubbed(value, parens=True, trailing_minus=True),
        diverges=BOUND_DIVERGENCES | GLYPH_TRAILING,
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
        diverges=(BOUND_DIVERGENCES | GLYPH_LEADING_PLAIN
                  | GLYPH_LEADING_DOLLAR | GLYPH_TRAILING),
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


@pytest.mark.parametrize("printed,expected", [
    # unsigned
    ("$1,234.56", "1234.56"),
    # every glyph a surveyed statement sets where a minus belongs, welded to
    # the currency symbol and set one cell away from it
    ("-$1,234.56", "-1234.56"),
    ("- $1,234.56", "-1234.56"),
    ("−$1,234.56", "-1234.56"),
    ("− $1,234.56", "-1234.56"),
    ("–$1,234.56", "-1234.56"),
    ("– $1,234.56", "-1234.56"),
    # an explicit credit marker is a marker, not a digit
    ("+$3.57", "3.57"),
    ("+ $3.57", "3.57"),
])
def test_parse_signed_decimal_reads_every_printed_sign_glyph(printed, expected):
    assert m.parse_signed_decimal(printed) == Decimal(expected)


def test_parse_signed_decimal_is_exact():
    assert (m.parse_signed_decimal("- $0.10") + m.parse_signed_decimal("$0.30")
            == Decimal("0.20"))


@pytest.mark.parametrize("junk", ["N/A", "", "--", "-", "$", "- N/A"])
def test_parse_signed_decimal_refuses_anything_that_is_not_money(junk):
    """The sign reading is added on top of `parse_decimal`; the refusal to
    guess at a non-money token is inherited unchanged."""
    with pytest.raises(ValueError):
        m.parse_signed_decimal(junk)


def test_the_signed_money_token_pattern_carries_no_capturing_groups():
    """It is composed into row patterns whose own group numbers must not shift
    underneath them."""
    assert re.compile(m.SIGNED_MONEY_TOKEN).groups == 0
    assert re.fullmatch(m.SIGNED_MONEY_TOKEN, "− $1,234.56")
    assert not re.fullmatch(m.SIGNED_MONEY_TOKEN, "1,234.56")


# ===========================================================================
# 3b. ONE minus class — the shadowed second definition (W3 §MGD)
# ===========================================================================
#
# `money.py` carried TWO module-scope bindings of `MINUS_GLYPHS`: the 2-glyph
# canon at the top, and a 4-glyph rebinding beside `parse_signed_decimal` that
# added ASCII hyphen and U+2014 EM DASH. `MINUS_CLASS` and `_MINUS_TABLE` had
# already been evaluated against the first, so the module answered one question
# two ways, and two EXPORTED parsers read one token with opposite signs.
#
# These tests pin the canon, its derivation, and the ruling that put the em
# dash outside it.

EMDASH = "—"  # U+2014 — punctuation, not a sign


def test_the_module_binds_each_exported_name_exactly_once():
    """THE STRUCTURAL FIX. A second binding of an exported name is invisible at
    the import site and silently shadows the first for every importer, while
    anything already derived from the first keeps the old value — which is
    precisely the state this cell found. An AST count is what makes that
    unrepresentable rather than merely fixed once.
    """
    import ast
    import pathlib

    source = pathlib.Path(m.__file__).read_text(encoding="utf-8")
    bindings: dict[str, int] = {}
    for node in ast.parse(source).body:            # module scope only
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = bindings.get(target.id, 0) + 1
    doubled = {name: n for name, n in bindings.items() if n > 1}
    assert not doubled, f"module-scope names bound more than once: {doubled}"


def test_the_minus_class_is_derived_from_the_canon_and_not_re_spelled():
    """`MINUS_CLASS` is the canon in brackets. Pinned as a STRING as well as by
    membership: the ASCII hyphen must stay first, where a regex reads it as a
    literal — move it into the middle and `[−-–]` becomes a codepoint RANGE.
    """
    assert m.MINUS_CLASS == "[" + m.MINUS_GLYPHS + "]"
    assert m.MINUS_CLASS == "[-−–]"
    compiled = re.compile(m.MINUS_CLASS)
    for glyph in m.MINUS_GLYPHS:
        assert compiled.fullmatch(glyph), glyph
    # nothing else in the neighbourhood, including the three carried
    # candidates and the em dash the shadow admitted
    for other in EMDASH + "‒―_~+.0aZ‐‑－":
        assert not compiled.fullmatch(other), other


def test_the_sign_table_and_the_class_cover_the_same_glyphs():
    """`normalize_sign_glyphs` and `MINUS_CLASS` are the same class stated as a
    translation and as a pattern. A glyph one honours and the other refuses is
    the shadow's exact shape."""
    compiled = re.compile(m.MINUS_CLASS)
    for codepoint in range(0x20, 0x3000):
        glyph = chr(codepoint)
        normalized = m.normalize_sign_glyphs(glyph) == "-"
        assert normalized == bool(compiled.fullmatch(glyph)), hex(codepoint)


def test_the_finder_and_the_parser_read_the_same_sign_class():
    """`SIGNED_MONEY_TOKEN` finds the cells `parse_signed_decimal` then reads.
    A finder wider than its parser hands over tokens the parser must decline;
    a finder narrower than its parser drops rows silently. They are one class,
    so neither can happen."""
    for glyph in m.MINUS_GLYPHS:
        token = f"{glyph}$1,234.56"
        assert re.fullmatch(m.SIGNED_MONEY_TOKEN, token), glyph
        assert m.parse_signed_decimal(token) == Decimal("-1234.56"), glyph
    assert not re.fullmatch(m.SIGNED_MONEY_TOKEN, f"{EMDASH}$1,234.56")


@pytest.mark.parametrize("printed", [
    f"{EMDASH}$500.00", f"{EMDASH} $500.00", f"{EMDASH}$1,234.56",
])
def test_an_em_dash_is_not_a_sign_and_the_cell_declines(printed):
    """THE RULING (W3 §MGD), and it is a REFUSAL rather than a reading.

    The em dash survives into `parse_decimal`, which cannot convert it, so the
    document declines instead of publishing a figure nobody printed. Both
    alternatives are wrong in a way that publishes: `+500.00` is the tolerant
    parsers' answer — a debit booked as a credit — and `-500.00` was the
    shadowed class's, which would have inverted the one archive document that
    prints the shape (`88AAC06119FC`, Columbia, where `03-16 — 39,692.35` is a
    POSITIVE running balance behind an empty-column placeholder).
    """
    with pytest.raises(ValueError):
        m.parse_signed_decimal(printed)


def test_the_two_exported_parsers_no_longer_answer_one_token_two_ways():
    """The measured symptom, pinned so it cannot come back: `parse_money` and
    `parse_signed_decimal` disagreed in DIRECTION on `—$500.00` (+500.0 against
    -500.00). They now agree that no minus was printed — one by returning the
    figure positive, the other by refusing the cell, which is the same claim
    made at two different strictnesses."""
    assert m.parse_money(f"{EMDASH}$500.00") == 500.0
    with pytest.raises(ValueError):
        m.parse_signed_decimal(f"{EMDASH}$500.00")
    # and for every glyph that IS a sign, both read it as one
    for glyph in m.MINUS_GLYPHS:
        assert m.parse_money(f"{glyph}$500.00") == -500.0, glyph
        assert m.parse_signed_decimal(f"{glyph}$500.00") == Decimal("-500.00"), glyph


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


# ===========================================================================
# 5. One decimal place is not money (W3 §MONEY-GRAMMAR card 2)
# ===========================================================================

@pytest.mark.parametrize("value", ["34.9", "1,234.5", "0.5", "12.3", "$7.1"])
def test_a_one_decimal_token_is_refused_rather_than_truncated(value):
    """The defect: the optional decimal group let the integer part match
    alone, so `34.9` returned `34.0` — a plausible, silently wrong amount."""
    assert m.parse_money(value) is None
    assert m.parse_money_tokens(value) == []


@pytest.mark.parametrize("value,expected", [
    ("34.90", 34.9), ("34.99", 34.99), ("0.00", 0.0),
    ("34.999", 35.0),            # a rate column still prints three
    ("1234", 1234.0),            # a whole number of dollars is money
    ("1,234.56", 1234.56),
])
def test_the_surveyed_money_shapes_still_read(value, expected):
    assert m.parse_money(value) == expected


def test_refusing_the_shape_does_not_re_enter_it_one_digit_later():
    """Without the leading boundary the trailing one is defeated: `34.9`
    would refuse `34` and then match `9` on the next position."""
    assert m.parse_money("34.9") is None
    assert m.parse_money_tokens("12.5 34.9") == []


def test_a_padded_one_decimal_reads_which_is_how_a_caller_supplies_one():
    """The division money.py documents: the engine is shared, the format
    stays with the bank. `analysis/scotia.py::_amount_value` is the surveyed
    example — it restores the trailing zero its bank strips."""
    assert m.parse_money("34.90") == 34.9
    assert m.parse_money(m.pad_leading_decimal(".5") + "0") == 0.5


@pytest.mark.parametrize("value,expected", [
    (".56", 0.56), ("$.56", 0.56), ("-.56", -0.56), (".56-", -0.56),
    (".00", 0.0), (".567", 0.57),
])
def test_a_bare_sub_dollar_amount_reads_as_cents_not_as_dollars(value, expected):
    """The legacy clone skipped the dot and matched the digits after it, so
    `.56` read as 56.00 — a hundred times the printed amount. The leading zero
    is restored before the token is matched."""
    assert m.parse_money(value) == expected


@pytest.mark.parametrize("value", [".", "..", ".a", "-."])
def test_padding_never_manufactures_a_zero_out_of_punctuation(value):
    assert m.parse_money(value) is None


def test_a_number_that_continues_is_not_a_money_token():
    assert m.parse_money("1.2.3") is None
    assert m.parse_money("12.345.67") is None
    assert m.parse_money("34.9999") is None


# ===========================================================================
# 6. The digit bound — a barcode is not an amount (W3 §MONEY-GRAMMAR card 3)
# ===========================================================================

def _run(digits: int) -> str:
    return "9" * digits


@pytest.mark.parametrize("digits", [1, 2, 7, 12, 13])
def test_an_amount_within_the_bound_still_reads(digits):
    assert m.parse_money(f"{_run(digits)}.00") == float(f"{_run(digits)}.00")
    assert m.parse_decimal(f"{_run(digits)}.00") == Decimal(f"{_run(digits)}.00")
    assert m.parse_grouped_float(f"{_run(digits)}.00") == float(f"{_run(digits)}.00")


@pytest.mark.parametrize("digits", [14, 20, 25, 26, 27, 54])
def test_a_digit_run_past_the_bound_is_not_money(digits):
    """A barcode or reference number pushed into an amount column."""
    assert m.parse_money(f"{_run(digits)}.00") is None
    assert m.parse_money(_run(digits)) is None
    assert m.parse_money_tokens(f"{_run(digits)}.00") == []
    assert m.parse_amount(f"{_run(digits)}.00", m.STRICT_UNSIGNED) is None
    assert m.parse_digit_scrubbed(f"{_run(digits)}.00") is None


@pytest.mark.parametrize("digits", [14, 26, 54])
def test_the_raising_family_refuses_the_same_run(digits):
    for fn in (m.parse_decimal, m.parse_grouped_float,
               m.parse_trailing_minus_dropped, m.parse_french_amount,
               m.parse_decimal_mixed_separator):
        with pytest.raises(ValueError):
            fn(f"{_run(digits)}.00")


def test_the_bound_is_below_the_decimal_context_that_crashes_adb():
    """THE CRASH CLASS. `analysis/adb.py` quantizes to cents in the default
    28-digit Decimal context, so a 26-integer-digit amount raises
    `decimal.InvalidOperation` and the document dies with a crash instead of
    a decline. adb.py is protected: the bound is enforced HERE, so no such
    value can ever reach it."""
    from decimal import InvalidOperation

    from analysis.adb import _money as adb_money

    # the boundary, measured: 25 integer digits quantize, 26 do not
    assert adb_money(float(f"1{'0' * 24}")) is not None
    with pytest.raises(InvalidOperation):
        adb_money(float(f"1{'0' * 26}"))

    # and the grammar refuses long before it, so adb never sees one
    assert m.parse_money(f"1{'0' * 26}.00") is None
    assert m.MAX_INTEGER_DIGITS < 26


# ===========================================================================
# 7. The debit marker is a token, not a letter (W3 §MONEY-GRAMMAR card 4)
# ===========================================================================

@pytest.mark.parametrize("value,expected", [
    ("1234.56D", -1234.56),      # TD Canada's own marker
    ("1234.56DR", -1234.56),
    ("1234.56/D", -1234.56),     # "/" is a separator TD prints, not a marker
    ("12.34D*", -12.34),         # fill characters are stripped first
    ("371.96OD", -371.96),       # TD Canada overdraft on a running balance
    ("1234.56-", -1234.56),      # the trailing-minus convention
])
def test_a_real_debit_marker_still_marks_a_debit(value, expected):
    assert m.parse_money(value) == expected


@pytest.mark.parametrize("value", [
    "100.00CREDIT",   # the defect: "CREDIT" contains a D
    "100.00DEBIT",    # not a marker anyone prints welded; not in the set
    "100.00USD", "100.00CAD",
    "100.00CR", "100.00C",
    "20.00DC",
])
def test_a_suffix_that_merely_contains_a_d_does_not_invert_the_sign(value):
    """The rule was 'the suffix CONTAINS a D', which is not a rule about
    markers: any word a flattened cell welds to an amount could flip it."""
    assert m.parse_money(value) == 100.0 or m.parse_money(value) == 20.0
    assert m.parse_money(value) > 0


def test_the_marker_set_is_what_the_archive_prints():
    """OD is in the set on evidence, not by taste: it is TD Canada's
    overdraft marker on 50 archive documents, 39 of them claimed. An
    'exact D/DR' reading would have inverted every one of their balances."""
    assert m.MAX_INTEGER_DIGITS  # module imported
    assert m.parse_money("371.96OD") == -371.96
    assert m.parse_money("371.96") == 371.96


# --- the detached-marker trap ----------------------------------------------
# THE MARKER MUST BE WELDED. The suffix group cannot cross whitespace, and
# that boundary is load-bearing rather than incidental: a DETACHED OD/DR/D is
# description text. The archive prints detached markers 212 times across 23
# documents, 6 of them VALIDATED — so relaxing the boundary to "read the next
# word as a marker" would negate real amounts on documents that pass today.

@pytest.mark.parametrize("value,expected", [
    # PNC, validated (2 documents): an overdraft FEE is a positive amount
    ("36.00 OD Fee", 36.0),
    ("100.00 OD Fee", 100.0),
    # Huntington: OD opens a description, it does not close an amount
    ("282.12 OD PROTECTION TRANSFER FROM CREDIT CARD", 282.12),
    # Beem Credit Union prints its running balance and a spaced DR
    ("6,649.65  DR", 6649.65),
    # BMO prints a spaced D between two amounts
    ("500.00 D", 500.0),
])
def test_a_detached_marker_is_description_text_and_leaves_the_sign_alone(
    value, expected
):
    assert m.parse_money(value) == expected


@pytest.mark.parametrize("welded,detached", [
    ("371.96OD", "371.96 OD"),
    ("1234.56DR", "1234.56 DR"),
    ("1234.56D", "1234.56 D"),
])
def test_welding_is_what_makes_a_marker_a_marker(welded, detached):
    """The same letters, one space apart, mean opposite things."""
    assert m.parse_money(welded) < 0
    assert m.parse_money(detached) > 0


# --- the rule as implemented, not as summarized ----------------------------

def test_a_searching_parser_yields_the_next_token_not_none():
    """Refusing a token is not the same as returning None: the search
    resumes. This is the behaviour a caller actually sees."""
    assert m.parse_money("34.9 100.00") == 100.0
    assert m.parse_money("0.5 7.25") == 7.25
    # None only when nothing in the input qualifies
    assert m.parse_money("34.9") is None
    assert m.parse_money("12.5 34.9") is None


def test_parse_digit_scrubbed_never_got_the_token_rule():
    """It keeps digits and dots and calls float, so it reads the TRUE value
    rather than a truncation. It was never the defect; callers bound it with
    `guard`. Pinned so the asymmetry is deliberate rather than forgotten."""
    assert m.parse_digit_scrubbed("34.9") == 34.9
    assert m.parse_digit_scrubbed("1,234.5") == 1234.5
    assert m.parse_digit_scrubbed("34.99999") == 34.99999
    assert m.parse_money("34.9") is None      # the contrast


@pytest.mark.parametrize("value", ["34.9999", "0.000668276", "1.2.3", "12.345.67"])
def test_the_refusal_covers_more_than_one_decimal_place(value):
    """Four-or-more decimals and dot-adjacent tokens are refused too — the
    `0.000668276` case is the exchange-rate factor chase's own local grammar
    already had to defend against."""
    assert m.parse_money(value) is None


def test_minus_class_is_the_fragment_consumers_embed():
    assert re.fullmatch(m.MINUS_CLASS, "-")
    assert re.fullmatch(m.MINUS_CLASS, MINUS)
    assert re.fullmatch(m.MINUS_CLASS, NDASH)
    assert not re.fullmatch(m.MINUS_CLASS, "—")  # em dash is not a minus


# ===========================================================================
# W3 §MG-C2 — read_money: absence is not a refusal
# ===========================================================================


def test_read_money_returns_none_when_there_was_no_token_at_all():
    """Absence is legitimate and must stay expressible. A statement that does
    not print a Checks line really does have zero checks, and its caller's
    `or 0.0` is the right arithmetic identity — so absence may not raise."""
    assert m.read_money(None) is None
    assert m.read_money("") is None
    assert m.read_money("   ") is None
    assert m.read_money("\t\n") is None


@pytest.mark.parametrize(
    "token, expected",
    [
        ("$1,234.56", 1234.56),
        ("-$1,234.56", -1234.56),
        (f"{MINUS}$1,234.56", -1234.56),
        ("$0.00", 0.0),
        (".56", 0.56),
        ("1234.56-", -1234.56),
    ],
)
def test_read_money_passes_a_readable_token_through_unchanged(token, expected):
    """The checked wrapper is not a second grammar: whatever `parse_money`
    reads, it returns, including a genuine printed zero."""
    assert m.read_money(token) == expected
    assert m.read_money(token) == m.parse_money(token)


@pytest.mark.parametrize(
    "token",
    [
        "34.9",                     # §MG3 one decimal place is not money
        "1.2.3",                    # §MG3 dot-adjacent
        "0.000668276",              # §MG3 four or more decimals (an FX factor)
        "1" * 14 + ".00",           # §MG4 past MAX_INTEGER_DIGITS
        "no digits here",
    ],
)
def test_read_money_raises_on_a_token_the_grammar_refuses(token):
    """The whole point. Every one of these returns None from `parse_money`,
    and under `parse_money(x) or 0.0` every one of them published 0.00 — a
    figure the bank printed replaced by one it did not. §MG3 and §MG4 widened
    this refusal set deliberately; each addition needed this to be a raise."""
    assert m.parse_money(token) is None
    with pytest.raises(ValueError, match="refused a printed token"):
        m.read_money(token)


@pytest.mark.parametrize(
    "token, expected_class",
    [
        ("34.9", "decimal places are neither two nor three"),
        ("0.000668276", "decimal places are neither two nor three"),
        ("1" * 14 + ".00", "integer run longer than the 13-digit bound"),
        ("N/A", "no digits in the cell"),
        ("no digits here", "no digits in the cell"),
    ],
)
def test_read_money_reports_the_refusal_class_and_never_the_token(token, expected_class):
    """W3 §MG-C2 D1 — the privacy seam.

    This exception crosses an exception boundary: a repair-stage refusal
    escapes `analyze_markdown`, and `webapp/worker.py` returns `str(exc)` as
    the job error a user can see. The exception-boundary law is registry ids
    and class names only, so the message may name the READER and the refusal
    CLASS and must never echo the statement's own text — an account-number-
    shaped run, a balance, or anything else the cell happened to hold.
    """
    with pytest.raises(ValueError) as excinfo:
        m.read_money(token)
    message = str(excinfo.value)
    assert expected_class in message
    assert "reader=parse_money" in message
    assert token not in message
    assert token.strip() not in message


def test_the_refusal_message_leaks_nothing_from_an_account_shaped_token():
    """The reviewer's own example, pinned: a long digit run must not survive
    into the message in any form, whole or in fragments."""
    token = "-$,123456789012345.99"
    with pytest.raises(ValueError) as excinfo:
        m.read_money(token)
    message = str(excinfo.value)
    assert "123456789012345" not in message
    assert not any(run in message for run in ("1234", "2345", "99"))
    assert message == (
        "money grammar refused a printed token "
        "(integer run longer than the 13-digit bound; reader=parse_money)"
    )


def test_read_money_uses_the_callers_own_reader():
    """The grammar is shared but the FORMAT is local, so a parser that anchors
    with its own guard hands that reader over rather than reimplementing the
    absence/refusal split. Here the caller's reader refuses what the shared
    one would happily read."""
    refuse_everything = lambda token: None            # noqa: E731
    with pytest.raises(ValueError, match="refused a printed token"):
        m.read_money("$1,234.56", refuse_everything)
    assert m.read_money("$1,234.56") == 1234.56       # the shared reader still reads it


def test_read_money_absence_short_circuits_before_the_reader_runs():
    """An absent token must not reach the reader at all: a reader that raises
    on garbage would otherwise turn a legitimately absent field into an
    error."""
    calls = []

    def recording(token):
        calls.append(token)
        raise AssertionError("the reader must not be called for an absent token")

    assert m.read_money(None, recording) is None
    assert m.read_money("  ", recording) is None
    assert calls == []


def test_a_money_token_may_not_begin_part_way_through_a_reference_number():
    r"""The left digit boundary, pinned because a sibling grammar lacked it.

    W3 §UNKNOWN-ISSUER hit this in a parser-local French grammar: with no
    left boundary, `…D77100000001337 150,00` matched from part-way inside the
    reference number and read `337 150,00` — a fabricated $337,150.00 debit
    out of a $150.00 one. The shared grammar's `(?<![\d.])` is what stops the
    same class here, and it is asserted rather than assumed.

    Note what this does NOT promise. `parse_money` SEARCHES, so a caller that
    hands it a whole LINE still gets the line's first money-shaped token,
    reference numbers included (§MG8 finding 3, out of scope by brief). The
    boundary guarantees a token is never read starting mid-number; it cannot
    guarantee the token found is the one the caller meant. Callers must pass
    a cell.
    """
    # The 14-digit run is past MAX_INTEGER_DIGITS and no sub-run of it may be
    # entered part-way, so the reference number is skipped entirely.
    assert m.parse_money("D77100000001337 150.00") == 150.0
    assert m.parse_money_tokens("D77100000001337 150.00") == [150.0]

    # No thousands group is ever welded across the boundary.
    assert m.parse_money("REF1337 150.00") != 1337150.0
    assert m.parse_money("1,337,150.00") == 1337150.0

    # The boundary is a property of the pattern, not of these examples.
    assert m._TOKEN_RE.pattern.startswith(r"(?<![\d.])")
    for text in ("1234567", "99.99", "1.2.3"):
        for start in range(1, len(text)):
            match = m._TOKEN_RE.search(text)
            assert match is None or match.start() == 0, (
                f"{text!r} was entered at offset {match.start()}"
            )

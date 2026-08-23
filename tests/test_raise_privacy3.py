"""RAISE-PRIVACY-3 (#HYGIENE8): the five sites §PRIVACY3 listed and could not own.

W3 §PRIVACY3 P10 is a ledger of raise sites in OTHER cells' files, each of the
same class the money and date grammars closed for themselves: an exception whose
message quotes the printed cell, crossing `webapp/worker.py`'s boundary into a
durable store, a CSV cell and three HTTP routes. The five:

| # | site | shape |
|---|---|---|
| 1 | `analysis/chase.py:_money_required` | `raise ValueError(value)` |
| 2 | `analysis/scanned_small_bank.py:_money` | `raise ValueError(value)` |
| 3 | `analysis/scanned_small_bank.py:_iso` | `raise ValueError(value)`, a DATE cell |
| 4 | `analysis/columbia_bank.py` period | two escaping `strptime` calls |
| 5 | `analysis/scotia.py` period | one escaping `strptime` call |

Sites 4 and 5 had no `raise` to grep for at all — `strptime`'s own ValueError is
``time data '<the printed date>' does not match format '<ours>'``, the
inherited-leak shape §MONEYPRIV MP0 named.

The sixth item is a CONTRACT defect rather than a privacy one, pinned by
§PRIVACY3 and closed here: `date()` raises `OverflowError`, which is an
`ArithmeticError` and not a `ValueError`, so a bare `except ValueError` let it
out of helpers documented to return `None`.

Proofs are the three kinds §PRIVACY3 established, because the property has three
ways to break: poisoned input through the real callables, an AST chain-guard for
the branches no input reaches (registered in
`tests/test_privacy3_boundaries.py::CHAIN_GUARDED`), and a structural census.
"""
from __future__ import annotations

import ast
from datetime import date as _date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from analysis import chase, columbia_bank, date_tokens as dt, scanned_small_bank, scotia  # noqa: E402
from tests.test_privacy3_boundaries import (                              # noqa: E402
    CANARY, CHAIN_GUARDED, DIGITS, POISONED_DATE_TOKENS, _chain_offenders,
    assert_private,
)

#: Money cells that cannot be read, one per refusal branch of the money
#: grammar plus three that carry no canary at all — a proof that only looked
#: for the canary would pass on those (§MONEYPRIV MP12 MINOR-6).
POISONED_MONEY_TOKENS = {
    "plain-junk": CANARY,
    "junk+digits": f"{CANARY} {DIGITS}",
    "digits+junk": f"{DIGITS} {CANARY}",
    "glued": f"${DIGITS}{CANARY}",
    "over-long-integer": f"{DIGITS}{DIGITS}.00",   # NO canary
    "three-decimals": "1,234.5678",                # NO canary
    "sign-only": "--",                             # NO canary
    "empty": "   ",
}

#: The two money sites, and the tokens each one ACCEPTS rather than refuses.
#: Measured, not assumed — see `test_the_two_money_sites_do_not_read_the_same
#: _grammar`, which is where the asymmetry is argued.
MONEY_SITES = {
    "chase._money_required": (chase._money_required, frozenset()),
    "scanned_small_bank._money": (
        scanned_small_bank._money,
        frozenset({"junk+digits", "digits+junk", "glued"}),
    ),
}


# ---------------------------------------------------------------------------
# 1. Sites 1-3 — poisoned input through the real callables
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("site", sorted(MONEY_SITES))
@pytest.mark.parametrize("shape", sorted(POISONED_MONEY_TOKENS))
def test_the_parser_money_sites_refuse_without_quoting(site, shape):
    callable_, accepted = MONEY_SITES[site]
    token = POISONED_MONEY_TOKENS[shape]
    if shape in accepted:
        pytest.skip(f"{site} READS this shape; see the asymmetry test")
    with pytest.raises(ValueError) as raised:
        callable_(token)
    assert_private(raised.value, token)
    assert f"reader={site}" in str(raised.value)


def test_the_two_money_sites_do_not_read_the_same_grammar():
    """A FINDING, pinned rather than fixed, and it is not this card's to fix.

    `chase._money_required` goes through `parse_digit_scrubbed` with an
    `_AMOUNT_RE` GUARD, so a cell has to look like an amount before any digit is
    scrubbed out of it. `scanned_small_bank._money` goes through bare
    `parse_money`, which extracts the digit run and ignores whatever letters
    surround it: measured, it READS `"<canary> <ten digits>"`,
    `"<ten digits> <canary>"` and `"$<ten digits><canary>"` as one amount.

    That is a READING defect and not a privacy one — nothing is quoted, an
    amount is invented — and it belongs to `analysis/money.py`'s shared grammar
    and to the scanned reader's choice of entry point, both of which move the
    archive. RAISE-PRIVACY-3 changed what the refusals SAY and nothing about
    what is refused, so the asymmetry is measured here so it cannot drift, and
    reported rather than closed.
    """
    for site, (callable_, accepted) in MONEY_SITES.items():
        measured = set()
        for shape, token in POISONED_MONEY_TOKENS.items():
            try:
                callable_(token)
            except ValueError:
                continue
            measured.add(shape)
        assert measured == set(accepted), (
            f"{site}: the set of poison cells it READS moved: {sorted(measured)}"
        )


@pytest.mark.parametrize("shape", sorted(POISONED_DATE_TOKENS))
def test_the_scanned_small_bank_date_site_refuses_without_quoting(shape):
    token = POISONED_DATE_TOKENS[shape]
    with pytest.raises(ValueError) as raised:
        scanned_small_bank._iso(token)
    assert_private(raised.value, token)
    assert "reader=scanned_small_bank._iso" in str(raised.value)


def test_the_refusals_stay_ValueError_because_four_handlers_catch_them():
    """`analysis/scanned_small_bank.py` catches its own `_money`/`_iso` in six
    places. `date_refusal` and `money_refusal` both return a `ValueError`, so
    the class is unchanged and only the message moved — which is what makes
    this a zero-movement change rather than a re-route."""
    source = (PROJECT_ROOT / "analysis" / "scanned_small_bank.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    caught = [
        ast.unparse(handler.type)
        for node in ast.walk(tree) if isinstance(node, ast.Try)
        for handler in node.handlers if handler.type is not None
    ]
    assert caught.count("ValueError") >= 4, caught
    for callable_ in (scanned_small_bank._money, scanned_small_bank._iso):
        with pytest.raises(ValueError):
            callable_(CANARY)


# ---------------------------------------------------------------------------
# 2. Sites 4-5 — the strptime class, closed by there being no call left
# ---------------------------------------------------------------------------

def _strptime_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strptime"
    ]


@pytest.mark.parametrize("module", ["columbia_bank", "scotia"])
def test_the_repointed_period_readers_call_strptime_nowhere(module):
    """§PRIVACY3 named these as `columbia_bank.py:449-450` and
    `scotia.py:162`; on this tree they sat at 384-385 and 197. The drift is
    line numbers, not the site — which is the reason this is asserted as
    "no call anywhere in the module" rather than as a line."""
    assert _strptime_calls(PROJECT_ROOT / "analysis" / f"{module}.py") == []


@pytest.mark.parametrize("token", [
    CANARY,
    f"{CANARY} {DIGITS}, 2026",
    "February 30, 2026",          # NO canary: strptime echoes the whole token
    f"April {DIGITS}, {DIGITS}",
])
def test_the_shared_strptime_seam_refuses_without_quoting(token):
    """The seam both repointed readers now go through. Driven directly,
    because the readers reach it only from a regex that has already proved a
    shape — and the branch a regex cannot reach is exactly the one that leaks
    on the day the regex is widened."""
    for reader, fmt in (("columbia_bank.period", "%B %d, %Y"),
                        ("scotia.period", "%b %d %Y")):
        with pytest.raises(ValueError) as raised:
            dt.parsed_datetime(token, fmt, reader=reader)
        assert_private(raised.value, token)
        assert f"reader={reader}" in str(raised.value)
        assert fmt not in str(raised.value), (
            "the caller's format constant is not the document's, but it is "
            "also not needed to identify the site"
        )


def test_the_two_period_readers_still_read_a_well_formed_period():
    """A refusal that also refused the good case would be a regression wearing
    a fix's clothes. Both formats, through the shared seam, on INVENTED dates."""
    assert dt.parsed_datetime(
        "March 4, 2019", "%B %d, %Y", reader="columbia_bank.period"
    ).date().isoformat() == "2019-03-04"
    assert dt.parsed_datetime(
        "Mar 4 2019", "%b %d %Y", reader="scotia.period"
    ).date().isoformat() == "2019-03-04"


# ---------------------------------------------------------------------------
# 3. The AST chain-guard registration
# ---------------------------------------------------------------------------

def test_the_five_sites_modules_are_chain_guarded():
    """§PRIVACY3 MINOR-2's rule, applied to the modules this card touched: the
    dynamic sweep above drives the raises that exist, and the AST guard is what
    covers a raise nothing executes — which is how a fourth one arrives, in a
    commit about something else."""
    for relative in ("analysis/chase.py", "analysis/scanned_small_bank.py",
                     "analysis/columbia_bank.py", "analysis/scotia.py"):
        assert relative in CHAIN_GUARDED, f"{relative} is not chain-guarded"
        offenders = _chain_offenders(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8"),
            relative, CHAIN_GUARDED[relative],
        )
        assert offenders == [], offenders


def test_the_chain_guard_would_catch_a_naked_raise_in_one_of_them():
    """The mutant, because a guard nobody has watched fail is not a guard.
    Three shapes, one per way the property breaks."""
    for source, expected in (
        # a naked raise that quotes the cell — one offender
        ("def f(v):\n    raise ValueError(v)\n", 1),
        # the same raise moved INTO the handler — one offender (__context__)
        ("def f(v):\n    try:\n        int(v)\n    except ValueError:\n"
         "        raise money_refusal('m', v)\n", 1),
        # explicit chain INSIDE the handler — TWO, because both clauses fire,
        # which is the point of the guard having three clauses rather than one
        ("def f(v):\n    try:\n        int(v)\n    except ValueError as e:\n"
         "        raise money_refusal('m', v) from e\n", 2),
        # the two clean shapes: a guard that flags everything is not a guard
        ("def f(v):\n    raise money_refusal('m', v)\n", 0),
        ("def f(v):\n    raise date_refusal('d', v)\n", 0),
    ):
        offenders = _chain_offenders(
            source, "synthetic.py",
            frozenset({"money_refusal", "date_refusal"}),
        )
        assert len(offenders) == expected, (source, offenders)


# ---------------------------------------------------------------------------
# 4. The OverflowError contract — CLOSED, not carried
# ---------------------------------------------------------------------------

#: Every public entry point of `analysis/date_tokens.py` that reaches `date()`
#: or `int()` with a number the document supplies, and what its own docstring
#: promises. `None` = "returns None"; `refusal` = "raises through
#: `date_refusal`". Nothing here may raise `OverflowError`.
_OVERFLOW_CASES = {
    "iso_or_none/year": (lambda n: dt.iso_or_none(n, 1, 1), None),
    "iso_or_none/day": (lambda n: dt.iso_or_none(2026, 1, n), None),
    "iso_from_month_day": (lambda n: dt.iso_from_month_day(f"1/{n}", 2026), "refusal"),
    "iso_from_month_day_strict": (
        lambda n: dt.iso_from_month_day_strict(f"1/{n}", 2026), None),
    "iso_from_month_day_year": (
        lambda n: dt.iso_from_month_day_year(f"1/1/{n}"), "refusal"),
    "iso_from_named_month_day": (
        lambda n: dt.iso_from_named_month_day("April", str(n), "2026"), None),
    "iso_unique_in_period": (
        lambda n: dt.iso_unique_in_period(
            1, n, start=_date(2026, 1, 1), end=_date(2026, 3, 1)), None),
    "year_within_period": (
        lambda n: dt.year_within_period(
            1, n, _date(2026, 1, 1), _date(2026, 3, 1)), None),
    "iso_within_period": (
        lambda n: dt.iso_within_period(
            f"1/{n}", _date(2026, 1, 1), _date(2026, 3, 1)), None),
    "period_from_long_dates": (
        lambda n: dt.period_from_long_dates(f"April {n}, 2026 through May 4, 2026"),
        None),
    "parsed_datetime": (lambda n: dt.parsed_datetime(str(n), "%Y", reader="p"),
                        "refusal"),
}

#: An integer past a C long. `date()` converts through one, so this is the
#: whole mechanism — not a large-looking string.
_HUGE = int(DIGITS)


def test_the_huge_integer_really_does_overflow_date():
    """The vacuity check: if CPython ever widened this conversion, every case
    below would pass for the wrong reason."""
    with pytest.raises(OverflowError) as raised:
        _date(2026, 1, _HUGE)
    assert DIGITS not in str(raised.value), (
        "the OverflowError itself must stay content-free; if CPython ever "
        "echoes the integer, this becomes a privacy defect as well"
    )


@pytest.mark.parametrize("case", sorted(_OVERFLOW_CASES))
def test_no_date_token_helper_lets_an_overflow_error_escape(case):
    """§PRIVACY3 P10 items 6-7, closed. The ledger said "three of those helpers
    are documented to return None"; the census here measures ELEVEN entry
    points, of which EIGHT let the `OverflowError` out before this change and
    two of the three that did not were saved by a regex bound on the token
    rather than by a handler.

    The decision is REFUSE: each entry point now honours the contract its own
    docstring states — `None` where it promises None, `date_refusal` where it
    promises to raise — and no caller has to know which arithmetic a particular
    `date()` can overflow on.
    """
    call, contract = _OVERFLOW_CASES[case]
    if contract is None:
        assert call(_HUGE) is None
        return
    with pytest.raises(ValueError) as raised:
        call(_HUGE)
    assert "date grammar refused a printed token" in str(raised.value)
    assert_private(raised.value, str(_HUGE))


def test_every_conversion_guard_in_the_date_module_catches_both():
    """The structural half, so a NINTH handler added later cannot be the one
    that is narrow again. Asserted on the AST: no `except ValueError` alone
    survives in `analysis/date_tokens.py`."""
    tree = ast.parse(
        (PROJECT_ROOT / "analysis" / "date_tokens.py").read_text(encoding="utf-8"))
    caught = [
        ast.unparse(handler.type)
        for node in ast.walk(tree) if isinstance(node, ast.Try)
        for handler in node.handlers if handler.type is not None
    ]
    assert caught, "the module has no handlers left; this rule is vacuous"
    assert set(caught) == {"(ValueError, OverflowError)"}, caught


def test_the_dates_module_is_named_as_still_narrow():
    """NOT closed here, and stated as a measurement rather than left silent.

    §PRIVACY3 P10 item 6 also named `analysis/dates.py`'s `_with_year` and
    `parse_date`. That module is not this card's, its two handlers guard
    `strptime` (which raises `ValueError`, not `OverflowError`) and a
    `date()` whose arguments come from a `strptime` result rather than from a
    token — so the escape this card closed is not reachable there today. The
    assertion is the SHAPE, so that the day a raw token reaches one of them the
    difference is visible rather than assumed.
    """
    tree = ast.parse(
        (PROJECT_ROOT / "analysis" / "dates.py").read_text(encoding="utf-8"))
    caught = sorted({
        ast.unparse(handler.type)
        for node in ast.walk(tree) if isinstance(node, ast.Try)
        for handler in node.handlers if handler.type is not None
    })
    assert caught == ["ValueError"], (
        f"analysis/dates.py's handler set moved ({caught}); re-read whether "
        "an OverflowError can now reach it"
    )

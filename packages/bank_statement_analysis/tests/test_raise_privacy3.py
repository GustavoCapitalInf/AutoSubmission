"""RAISE-PRIVACY-3 (#HYGIENE8): the five sites §PRIVACY3 listed and could not own.

W3 §PRIVACY3 P10 is a ledger of raise sites in OTHER cells' files, each of the
same class the money and date grammars closed for themselves: an exception whose
message quotes the printed cell.

WHERE SUCH A MESSAGE STILL GOES, restated by the #HYGIENE8 closure session
(review MINOR-6). This
docstring used to say "crossing `webapp/worker.py`'s boundary into a durable
store, a CSV cell and three HTTP routes", which has been stale since batch 6's
§WORKER-PRIVACY: `webapp/worker.py:_stage_failure` withholds every message and
stores the exception's CLASS NAME, and the dispatch seam reduces a parser crash
the same way. The surviving sinks are the CSV writers — `batch.py:266`,
`coverage_audit.py:193` and `deterministic_coverage_audit.py:241`, each
`f"{type(e).__name__}: {e}"` into a cell — and any direct caller. The law is
about what this tree may RAISE and carries no clause about who catches it, so
the reroute is right in front of a boundary nobody has written yet. The five:

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
    f"{CANARY} {DIGITS}, 2031",
    "February 30, 2031",          # NO canary: strptime echoes the whole token
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
        "March 4, 2031", "%B %d, %Y", reader="columbia_bank.period"
    ).date().isoformat() == "2031-03-04"
    assert dt.parsed_datetime(
        "Mar 4 2031", "%b %d %Y", reader="scotia.period"
    ).date().isoformat() == "2031-03-04"


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
# 3b. The reader NAME is a source symbol, never the document
# ---------------------------------------------------------------------------

#: Every constructor in the refusal family, and how to find its two arguments.
#: `parsed_datetime(token, fmt, *, reader)`; the three refusal constructors are
#: `(reader, token)`.
_REFUSAL_CALLS = ("parsed_datetime", "date_refusal", "money_refusal", "_refusal")


def _refusal_call_sites():
    """(path, lineno, name, reader_expr, token_expr) for every call in the
    production tree. Tests are excluded: a test may legitimately build a reader
    name out of a fixture."""
    skip = {".git", ".claude", ".venv", "__pycache__", "node_modules"}
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        try:
            relative = path.relative_to(PROJECT_ROOT)
        except ValueError:
            continue
        if set(relative.parts) & skip or relative.parts[0] == "tests":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else None)
            if name not in _REFUSAL_CALLS:
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords}
            if name == "parsed_datetime":
                token = node.args[0] if node.args else keywords.get("token")
                reader = keywords.get("reader")
            else:
                reader = node.args[0] if node.args else keywords.get("reader")
                token = node.args[1] if len(node.args) > 1 else keywords.get("token")
            yield relative.as_posix(), node.lineno, name, reader, token


def test_no_refusal_call_derives_its_reader_name_from_the_token():
    """A MUTANT FOUND THIS GAP, and it is the sharpest thing this card learned.

    Every proof above is about what the CONSTRUCTOR does with `token`: it is
    measured into a four-value class and never quoted. None of them says
    anything about `reader`, which is interpolated verbatim — and a call site
    can put the document into the message by writing
    ``reader=f"scotia.period {raw}"``. Mutant R11 did exactly that and survived
    a poisoned sweep, a chain guard and a strptime census, because no test
    drove the parser rather than the seam.

    The rule is the one the family's docstrings already state ("the reader's
    NAME, a symbol in this file"): a reader expression may not mention any name
    the token expression mentions. It is stronger than "must be a literal",
    which would fail four honest sites: the two constructors forwarding their
    own parameter, `money.py`'s `getattr(reader, "__name__", ...)`, and
    `community_section._strptime`'s module prefix concatenation.
    """
    sites = list(_refusal_call_sites())
    assert len(sites) >= 25, f"the walk found only {len(sites)} call sites"
    offenders = []
    for path, lineno, name, reader, token in sites:
        if reader is None or token is None:
            offenders.append(f"{path}:{lineno}: {name} - arguments not resolvable")
            continue
        shared = ({n.id for n in ast.walk(reader) if isinstance(n, ast.Name)}
                  & {n.id for n in ast.walk(token) if isinstance(n, ast.Name)})
        if shared:
            offenders.append(
                f"{path}:{lineno}: {name} builds its reader name out of "
                f"{sorted(shared)}, which is the token"
            )
    assert offenders == [], offenders


def test_the_reader_name_rule_can_see_the_mutant_that_beat_the_others():
    """The guard watched failing, on R11's exact shape and on the honest ones
    it must NOT flag."""
    def offenders_for(source: str) -> int:
        tree = ast.parse(source)
        found = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "parsed_datetime":
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords}
            token, reader = node.args[0], keywords["reader"]
            found += bool(
                {n.id for n in ast.walk(reader) if isinstance(n, ast.Name)}
                & {n.id for n in ast.walk(token) if isinstance(n, ast.Name)}
            )
        return found

    assert offenders_for('parsed_datetime(raw, F, reader=f"scotia.period {raw}")') == 1
    assert offenders_for('parsed_datetime(raw, F, reader="scotia.period " + raw)') == 1
    assert offenders_for('parsed_datetime(raw, F, reader="scotia.period")') == 0
    assert offenders_for('parsed_datetime(v, F, reader="cs." + reader)') == 0


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
        lambda n: dt.period_from_long_dates(f"April {n}, 2031 through May 4, 2031"),
        None),
    "parsed_datetime": (lambda n: dt.parsed_datetime(str(n), "%Y", reader="p"),
                        "refusal"),
}

#: An integer past 2**31, the C `int` `date()` parses its arguments into on
#: every platform (review MINOR-4). `date()` converts through it, so this is the
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


# ---------------------------------------------------------------------------
# 5. REVIEW MAJOR-2 - the four `date()` sites of the "site 6" class that still
#    stood in the four chain-guarded readers at `af98349`
# ---------------------------------------------------------------------------
#
# The card closed site 6 (`scanned_small_bank._iso`) and wrote fifteen lines
# about why a row-date regex proves a token's SHAPE and nothing more. The
# hostile review applied that standard to the branch's own four files and found
# the same shape four more times - one of them twenty lines below the fix. None
# is inside a `try`, and two of the four modules hold no `raise` at all, so the
# AST chain guard's registration for them was vacuous by construction.
#
# THE FIXTURES ARE INVENTED. Every label below is a detection marker or a
# column header already committed in the reader's own source at `10cc722`; the
# account digits are repeated patterns; the figures are rendered from whole
# units at build time (the poison sweep's rule) so this file carries no
# amount-shaped literal; every date is 2031. Nothing here has been inside a
# document.

#: The figures the four fixtures print, as WHOLE UNITS. Arbitrary, four digits
#: or fewer, and rendered rather than written: an invented fixture stays out of
#: the amount scans by construction instead of arguing with them afterwards.
_ROW_UNITS = {
    "amount": 10, "second": 20, "third": 30,
    "balance_one": 90, "balance_two": 110, "balance_three": 140,
    "opening": 1000, "balance_after": 990,
    "low": 900, "credits": 500, "average": 950, "debits": 400,
    "interest": 0, "ending": 1100,
}


def _figure(name: str) -> str:
    return f"{_ROW_UNITS[name]:,.2f}"


#: Chase's web export. `EXPORT_DETECTION_MARKERS` needs the printed header and
#: the `Transactions` section word; `_parse_chase_business_export` publishes
#: only at three rows or more, so the poisoned row is followed by two valid
#: ones and the VALID drive reaches a published payload rather than a decline.
CHASE_EXPORT_ROW_FIXTURE = f"""\
Printed from Chase for Business
Transactions
BUS COMPLETE CHK (...{'0' * 4})
BUS COMPLETE CHK (...{'0' * 4})
INVENTED HOLDER NAME
{{token}} INVENTED DESCRIPTION ONE ${_figure('amount')} ${_figure('balance_one')}
Mar 11, 2031 INVENTED DESCRIPTION TWO ${_figure('second')} ${_figure('balance_two')}
Mar 12, 2031 INVENTED DESCRIPTION THREE ${_figure('third')} ${_figure('balance_three')}
"""

#: Columbia's cheque table. The five blocks `parse_columbia_bank_statement`
#: requires are present and empty; the period strip is valid and in 2031, so
#: the only thing the poisoned token can refuse is the cheque row's own date.
COLUMBIA_CHEQUE_FIXTURE = f"""\
MARKETPLACE CHECKING

Last statement: November 30, 2031
This statement: December 31, 2031

Account number {'X' * 8}
Beginning balance {_figure('opening')}
Low balance {_figure('low')}
Deposits/Additions {_figure('credits')}
Average balance {_figure('average')}
Withdrawals/Subtractions {_figure('debits')}
Interest earned {_figure('interest')}
Ending balance {_figure('ending')}

DEPOSITS/ADDITIONS
Date Description Additions
Total Additions

ACH AND ELECTRONIC PAYMENTS/SUBTRACTIONS
Date Description Subtractions
Total ACH and Electronic Payments/Subtractions

ACH and Electronic Deposits/Additions
Date Description Additions
Total ACH and Electronic Deposits/Additions

Other Withdrawals/Subtractions
Date Description Subtractions
Total Other Withdrawals/Subtractions

DAILY BALANCES
Overdraft Fee Summary

Checks
Check # Amount Date
${_figure('amount')} {{token}}
(* Skip in check sequence
"""

#: Scotiabank's posting table. The trademark footer line is the reader's own
#: detection marker; the grid header is the one `_TABLE_HEADER` declares. A
#: `BALANCE FORWARD` row opens the table so the VALID drive publishes.
SCOTIA_POSTING_FIXTURE = f"""\
SCOTIABANK
THE BANK OF NOVA SCOTIA

Business Account {'0' * 4} {'1' * 4} Jan 01 2031 Jan 31 2031

ACCOUNT DETAILS
Date Description Withdrawals/Debits ($) Deposits/Credits ($) Balance ($)
01/02/2031 BALANCE FORWARD {_figure('opening')}
{{token}} INVENTED DESCRIPTION {_figure('amount')} {_figure('balance_after')}
"""

#: The two-column `MM/DD` grid `_parse_two_column_mdyy_rows` reads, which is
#: where `_date_from_mdyy` is reached from.
SSB_MDYY_ROW_FIXTURE = f"{{token}} INVENTED DESCRIPTION {_figure('amount')}"

#: Out-of-range rows, one per site, each matching the site's OWN row regex and
#: each failing `date()`. Invented shapes, never transcriptions. A printed
#: month or day is a two-digit run, which is why the sweep's digit-run floor
#: drops to two for these cells.
MAJOR2_ROW_TOKENS = {
    "chase.export_row": {
        "day-30-in-february": "Feb 30, 2031",
        "day-31-where-30-is-the-last": "Apr 31, 2031",
        "day-31-in-june": "Jun 31, 2031",
    },
    "columbia_bank.cheque_row": {
        "month-out-of-range": "13-40",
        "day-30-in-february": "02-30",
        "day-31-where-30-is-the-last": "04-31",
    },
    "scotia.posting_row": {
        "month-out-of-range": "13/40/2031",
        "day-30-in-february": "02/30/2031",
        "day-31-where-30-is-the-last": "04/31/2031",
    },
    "scanned_small_bank.mdyy_row": {
        "month-out-of-range": "13/40",
        "day-30-in-february": "02/30",
        "day-31-where-30-is-the-last": "04/31",
    },
}

#: A row the reader CAN read, per site: the same drive with an in-range date.
#: The point of carrying it is that a refusal which also refused the good case
#: would be a regression wearing a fix's clothes.
MAJOR2_VALID_ROWS = {
    "chase.export_row": "Feb 10, 2031",
    "columbia_bank.cheque_row": "12-10",
    "scotia.posting_row": "01/10/2031",
    "scanned_small_bank.mdyy_row": "01/10",
}

#: The reader name each site's refusal must carry, so a drive cannot be
#: satisfied by SOME other refusal raised earlier in the same parser.
MAJOR2_READERS = {
    "chase.export_row": "chase._parse_chase_business_export",
    "columbia_bank.cheque_row": "columbia_bank.cheque_row",
    "scotia.posting_row": "scotia.posting_row",
    "scanned_small_bank.mdyy_row": "scanned_small_bank._date_from_mdyy",
}

#: The (site, shape) CELLS, flattened, so the parametrisation is exactly the
#: twelve drives that exist rather than a cross-product with holes in it.
MAJOR2_CELLS = [
    (site, shape)
    for site in sorted(MAJOR2_ROW_TOKENS)
    for shape in sorted(MAJOR2_ROW_TOKENS[site])
]


#: The `_parse_two_column_mdyy_rows` arguments, as CONSTANTS rather than
#: literals at the call site, and that is not style. A rendered traceback
#: quotes the SOURCE line of every frame it walks; `_leaking_surfaces`
#: subtracts the line `extract_tb` reports, but a call broken across lines
#: leaves its continuations in the text. A `year=2031` written there is a
#: four-digit run in the traceback of a drive whose token is `04/31`, and at
#: the row cells' two-digit floor that is indistinguishable from a leak. Every
#: drive below is therefore ONE source line and carries no digit.
_MDYY_YEAR = 2031
_MDYY_SIGN = -1


def major2_drives(package: str) -> dict:
    """The four sites, driven through the REAL reader, inside one package.

    Parameterised by package name and shared with `tools.hygiene8_poison_sweep`,
    which imports this rather than restating it.
    """
    import importlib

    chase_ = importlib.import_module(f"{package}.chase")
    columbia_ = importlib.import_module(f"{package}.columbia_bank")
    scotia_ = importlib.import_module(f"{package}.scotia")
    scanned_ = importlib.import_module(f"{package}.scanned_small_bank")

    def chase_export_row(token: str):
        markdown = CHASE_EXPORT_ROW_FIXTURE.format(token=token)
        return chase_._parse_chase_business_export(markdown)

    def columbia_cheque_row(token: str):
        markdown = COLUMBIA_CHEQUE_FIXTURE.format(token=token)
        return columbia_.parse_columbia_bank_statement(markdown)

    def scotia_posting_row(token: str):
        markdown = SCOTIA_POSTING_FIXTURE.format(token=token)
        return scotia_.parse_scotiabank_statement(markdown)

    def scanned_mdyy_row(token: str):
        row = SSB_MDYY_ROW_FIXTURE.format(token=token)
        return scanned_._parse_two_column_mdyy_rows(row, year=_MDYY_YEAR, sign=_MDYY_SIGN)

    return {
        "chase.export_row": chase_export_row,
        "columbia_bank.cheque_row": columbia_cheque_row,
        "scotia.posting_row": scotia_posting_row,
        "scanned_small_bank.mdyy_row": scanned_mdyy_row,
    }


def _leaking(exc: BaseException, token: str) -> list:
    """The poison sweep's own surface rule, imported rather than restated.

    The digit-run floor is TWO here and three there: a printed month or day is
    a two-digit run, so a three-digit floor cannot see `month must be in 1..12,
    not 13` at all. Narrowing the floor can only make this test stricter.
    """
    from tests.test_privacy3_boundaries import _digit_runs
    from tools.hygiene8_poison_sweep import _leaking_surfaces

    return _leaking_surfaces(exc, token, CANARY, set(_digit_runs(token, 2)))


@pytest.mark.parametrize("site,shape", MAJOR2_CELLS)
def test_the_four_date_sites_refuse_without_quoting_at_the_branch(site, shape):
    """REVIEW MAJOR-2, closed. Same drive, same fixture, this tree: the
    document still refuses with the same class, and no digit of the printed
    token reaches `str`, `repr`, `args`, the chain or a rendered traceback."""
    token = MAJOR2_ROW_TOKENS[site][shape]
    with pytest.raises(ValueError) as raised:
        major2_drives("analysis")[site](token)
    assert _leaking(raised.value, token) == []
    assert f"reader={MAJOR2_READERS[site]}" in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__context__ is None


#: The date each in-range row prints, as the reader publishes it. The Columbia
#: fixture carries no printed totals, so the reader publishes no statement; the
#: row must still not refuse.
MAJOR2_VALID_READINGS = {
    "chase.export_row": "2031-02-10",
    "columbia_bank.cheque_row": None,
    "scotia.posting_row": "2031-01-10",
    "scanned_small_bank.mdyy_row": "2031-01-10",
}


@pytest.mark.parametrize("site", sorted(MAJOR2_VALID_ROWS))
def test_the_four_date_sites_read_an_in_range_row(site):
    published = major2_drives("analysis")[site](MAJOR2_VALID_ROWS[site])
    expected = MAJOR2_VALID_READINGS[site]
    if expected is None:
        assert published is None
    else:
        assert expected in repr(published)


def test_the_refusal_class_at_the_four_sites_is_still_ValueError():
    """The dispatch seam reduces a parser crash to `type(exc).__name__`, so a
    changed CLASS would move an outcome even though no figure moved. Asserted
    at the drive rather than at the constructor, because it is the class that
    ESCAPES the reader that the seam sees."""
    for site, tokens in MAJOR2_ROW_TOKENS.items():
        for token in tokens.values():
            with pytest.raises(ValueError):
                major2_drives("analysis")[site](token)


# ---------------------------------------------------------------------------
# 6. THE IMPLICIT-CONVERSION CENSUS over every CHAIN_GUARDED module
# ---------------------------------------------------------------------------
#
# REVIEW MAJOR-2's other half. `_chain_offenders` inspects `raise` statements,
# and the whole lesson of §PRIVACY3 is that the dangerous half has no `raise` to
# grep for: `columbia_bank.py` and `scotia.py` held ZERO raises at `af98349`, so
# their `CHAIN_GUARDED` entries proved nothing at all. The four sites the review
# found were invisible to every proof this branch had.
#
# THE RULE. A conversion call - `date`, `datetime`, `int`, `float`, `Decimal`,
# `strptime`, `fromisoformat` - whose argument DERIVES from a regex group or a
# parsed token, and that stands lexically OUTSIDE any handler catching
# `ValueError`, is reported. A value produced by a `date_tokens` funnel is
# CLEANSED: the funnel is where the guard lives, so `date.fromisoformat(iso)`
# on an `iso` that `iso_or_none` returned is not a finding.
#
# Taint is intra-function and deliberately over-approximates - a name bound
# from `.group()`, `.groups()`, `.findall()`, `.finditer()` or `.split()`, and
# anything bound from such a name, transitively. Over-approximation is the
# right direction: it can only report more, never fewer.
#
# THE ALLOWLIST IS EXPLICIT AND EVERY ENTRY CARRIES A REASON. Two lists,
# because two different things are being said. `_CANNOT_ECHO` is "this call
# cannot put a document token in a message" and is the ordinary case.
# `_CARRIED_ECHOING_SITES` is "this call CAN, it is the MAJOR-2 class, and it is
# outside this closure's mandate" - eight at the time, in three modules that
# closure does not own, each measured in this session and named in W3 §H14 for
# the batch-9 card. A site that leaves either list, or arrives in neither,
# fails this test loudly, which is the whole point: the next `date()` on a
# regex group is visible the day it is written.

#: The calls whose own exception message quotes what they were given.
_CONVERSION_CALLS = frozenset({
    "date", "datetime", "int", "float", "Decimal", "strptime", "fromisoformat",
})

#: How a document token gets into a local name in these readers.
_TAINT_SEEDS = frozenset({
    "group", "groups", "groupdict", "findall", "finditer", "split",
})

#: `analysis/date_tokens.py`'s guarded conversions. A name bound directly from
#: one of these is CLEAN: the guard is inside the funnel.
_FUNNELS = frozenset({
    "iso_or_none", "iso_from_month_day", "iso_from_month_day_strict",
    "iso_from_month_day_year", "iso_from_named_month_day",
    "iso_unique_in_period", "iso_within_period", "year_within_period",
    "parsed_datetime", "period_from_long_dates",
})

#: A handler that catches any of these catches a conversion's ValueError.
_CATCHES_VALUE_ERROR = frozenset({"ValueError", "Exception", "BaseException"})


def _mentioned_names(node: ast.AST) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _mentions_a_seed(node: ast.AST) -> bool:
    return any(
        isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and sub.func.attr in _TAINT_SEEDS
        for sub in ast.walk(node)
    )


def _is_funnel_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = (func.id if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else None)
    return name in _FUNNELS


def _bound_names(target: ast.AST) -> set:
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def _tainted_names(function: ast.AST) -> set:
    """Names inside `function` that can hold a document token, to a fixpoint."""
    tainted: set = set()
    for _ in range(8):
        before = set(tainted)
        for node in ast.walk(function):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is None or _is_funnel_call(value):
                    continue
                if _mentions_a_seed(value) or (_mentioned_names(value) & tainted):
                    targets = (node.targets if isinstance(node, ast.Assign)
                               else [node.target])
                    for target in targets:
                        tainted |= _bound_names(target)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                if _mentions_a_seed(node.iter) or (_mentioned_names(node.iter) & tainted):
                    tainted |= _bound_names(node.target)
        if tainted == before:
            break
    return tainted


def _guarded_call_ids(tree: ast.AST) -> set:
    """Every node inside a `try` body whose handlers catch a ValueError."""
    guarded: set = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(
            handler.type is not None
            and (_mentioned_names(handler.type) & _CATCHES_VALUE_ERROR)
            for handler in node.handlers
        ):
            continue
        for statement in node.body:
            guarded.update(id(sub) for sub in ast.walk(statement))
    return guarded


def implicit_conversion_census(modules) -> list:
    """`module:function: call` for every unguarded conversion of a token.

    Keyed on the UNPARSED call rather than a line number: a line number drifts
    with every edit above it, and a census whose keys drift is a census nobody
    keeps.
    """
    found: set = set()
    for relative in modules:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source)
        guarded = _guarded_call_ids(tree)
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            tainted = _tainted_names(function)
            for node in ast.walk(function):
                if not isinstance(node, ast.Call) or id(node) in guarded:
                    continue
                func = node.func
                name = (func.id if isinstance(func, ast.Name)
                        else func.attr if isinstance(func, ast.Attribute) else None)
                if name not in _CONVERSION_CALLS:
                    continue
                arguments = list(node.args) + [kw.value for kw in node.keywords]
                if not any(
                    _mentions_a_seed(argument)
                    or (_mentioned_names(argument) & tainted)
                    for argument in arguments
                ):
                    continue
                found.add(f"{relative}:{function.name}: {ast.unparse(node)}")
    return sorted(found)


#: The reasons, written once and referenced, so a reason cannot drift between
#: two entries that share it.
_DIGITS_ONLY_GROUP = (
    "int() of a group whose pattern is digits only (\\d+, \\d{2}, \\d{4}); the "
    "conversion cannot raise, so there is no message to echo into"
)
_DIGITS_ONLY_SPLIT = (
    "int() of a digits-only group split on its own separator; every part is "
    "\\d+ by the pattern that produced it"
)
_ISDIGIT_GUARDED = (
    "int() reached only through an explicit `.isdigit()` test on the same text"
)
_ALREADY_A_NUMBER = (
    "float() of a value this module has already parsed into a Decimal or a "
    "float; the argument is not a document token"
)
_PATTERN_FULLMATCHED = (
    "float() of text a full-match against the format's own numeric pattern has "
    "just proved is a float literal"
)
_OUR_OWN_ISO = (
    "int() of the first four characters of an ISO date this tree produced, "
    "never a printed token"
)
_PROVEN_UNRAISABLE = (
    "date() on a triple `year_within_period` already constructed inside its "
    "own try; documented at the site as a measurement, not a hope"
)

#: Every unguarded conversion of a token in the CHAIN_GUARDED modules that
#: cannot put a document token into an exception message. Hand-verified by the
#: closure session against the pattern that produces each argument.
_CANNOT_ECHO = {
    "analysis/bmo.py:parse_bmo_statement: int(part)": _DIGITS_ONLY_SPLIT,
    "analysis/chase.py:_parse_chase_business_export: int(raw_day)": _DIGITS_ONLY_GROUP,
    "analysis/chase.py:_parse_chase_business_export: int(raw_year)": _DIGITS_ONLY_GROUP,
    "analysis/chase.py:_summary_row: int(counted.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/chase.py:parse_chase_statement: int(instances)": _ISDIGIT_GUARDED,
    # Audit 2026-10-13 PARSERS-2: the grid reader dates its cells through the
    # printed period, so it converts `_GRID_CELL`'s two `(\d{2})` groups itself
    # (it used to hand them to a `date()` inside a try).
    "analysis/columbia_bank.py:_daily_snapshots: int(day)": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:_daily_snapshots: int(month)": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:_rows: int(embedded_day)": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:_rows: int(embedded_month)": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:_rows: int(match.group('day'))": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:_rows: int(match.group('month'))": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(_money(interest_raw))": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(_signed(average_raw))": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(amount)": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(ending)": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(opening)": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(reconstructed[txn_date])": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(snapshots[snapshot_date])": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(total_credits)": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: float(total_debits)": _ALREADY_A_NUMBER,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: int(day)": _DIGITS_ONLY_GROUP,
    "analysis/columbia_bank.py:parse_columbia_bank_statement: int(month)": _DIGITS_ONLY_GROUP,
    "analysis/date_tokens.py:iso_from_month_day_strict: int(m.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/date_tokens.py:iso_from_month_day_strict: int(m.group(2))": _DIGITS_ONLY_GROUP,
    "analysis/date_tokens.py:iso_within_period: date(year, month, day)": _PROVEN_UNRAISABLE,
    "analysis/date_tokens.py:iso_within_period: int(part)": _ISDIGIT_GUARDED,
    "analysis/farmers_merchants.py:_parse_summary: int(m.group('credit_count'))": _DIGITS_ONLY_GROUP,
    "analysis/farmers_merchants.py:_parse_summary: int(m.group('days'))": _DIGITS_ONLY_GROUP,
    "analysis/farmers_merchants.py:_parse_summary: int(m.group('debit_count'))": _DIGITS_ONLY_GROUP,
    "analysis/farmers_merchants.py:_parse_summary: int(m.group('end').split('/')[-1])": _DIGITS_ONLY_SPLIT,
    "analysis/farmers_merchants.py:_parse_summary: int(part)": _DIGITS_ONLY_SPLIT,
    "analysis/farmers_merchants.py:_statement_year: int(match.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/money.py:parse_money: float(m.group(2))": _PATTERN_FULLMATCHED,
    "analysis/money.py:parse_money_tokens: float(text)": _PATTERN_FULLMATCHED,
    "analysis/scanned_small_bank.py:_daily_balances: int(year_match.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:_date_from_mdyy: int(part)": _DIGITS_ONLY_SPLIT,
    "analysis/scanned_small_bank.py:_iso: int(day)": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:_iso: int(month)": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:_iso: int(raw_year)": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:_southside_day: int(canonical.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:_southside_day: int(canonical.group(2))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:_southside_summary: float(found['credit_total'])": _ALREADY_A_NUMBER,
    "analysis/scanned_small_bank.py:_southside_summary: float(found['debit_total'])": _ALREADY_A_NUMBER,
    "analysis/scanned_small_bank.py:_southside_summary: float(found['ending'])": _ALREADY_A_NUMBER,
    "analysis/scanned_small_bank.py:_southside_summary: float(found['previous'])": _ALREADY_A_NUMBER,
    "analysis/scanned_small_bank.py:_southside_summary: int(count)": _ISDIGIT_GUARDED,
    # Composed on train8: this entry was `int(m.group(1))` on the HYGIENE-8a
    # branch; SCAN-HYGIENE's SS-UNIQUE-MATCH hunk (efc5ced) rebinds the same
    # "Days in Statement Period" read to `days = unique_match(text, _SS_DAYS_RE)`.
    # Same site, same `(\d+)` group, same reason — one key renamed, none added.
    "analysis/scanned_small_bank.py:_southside_summary: int(days.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:parse_apex_scanned_statement: int(sm.group('credit_count'))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:parse_apex_scanned_statement: int(sm.group('days'))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:parse_apex_scanned_statement: int(sm.group('debit_count'))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:parse_southside_scanned_statement: int(stmt.period_end[:4])": _OUR_OWN_ISO,
    "analysis/scanned_small_bank.py:parse_texas_first_scanned_statement: int(credit_summary.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/scanned_small_bank.py:parse_texas_first_scanned_statement: int(debit_summary.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/scotia.py:parse_scotiabank_statement: int(m.group(1))": _DIGITS_ONLY_GROUP,
    "analysis/scotia.py:parse_scotiabank_statement: int(m.group(2))": _DIGITS_ONLY_GROUP,
    "analysis/scotia.py:parse_scotiabank_statement: int(m.group(3))": _DIGITS_ONLY_GROUP,
    "analysis/scotia.py:parse_scotiabank_statement: int(summary.group('credit_count'))": _DIGITS_ONLY_GROUP,
    "analysis/scotia.py:parse_scotiabank_statement: int(summary.group('debit_count'))": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_date_tokens: int(day)": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_date_tokens: int(yy)": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_native_date_to_iso: int(m.group(2))": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_parse_native_td_canada: int(stmt.period_end[:4])": _OUR_OWN_ISO,
    "analysis/td_can.py:_parse_period: int(ed)": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_parse_period: int(ey)": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_parse_period: int(sd)": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_parse_period: int(sy)": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_parse_summary_count_amount: float(m.group(2))": _DIGITS_ONLY_GROUP,
    "analysis/td_can.py:_parse_summary_count_amount: int(m.group(1))": _DIGITS_ONLY_GROUP,
}

#: THE MAJOR-2 CLASS THIS CLOSURE DISCLOSED RATHER THAN CLOSED — and it is now
#: EMPTY, which is the outcome the disclosure was for.
#:
#: #HYGIENE8 measured eight of them, in three modules its own mandate did not
#: own (`bmo._statement_period` x2, `farmers_merchants._parse_summary` x2,
#: `td_can._parse_period` x2 / `_date_tokens` / `_native_date_to_iso`), drove
#: every one, recorded the message each echoed in W3 §H14.3, and carded them
#: for batch 9 rather than editing three unreviewed readers on a closure
#: commit. Batch 9's RAISE-PRIVACY-4 closed all eight through the same funnel
#: and the same both-tree drive (W3 §RAISEPRIV4), so the census no longer finds
#: them and this list is empty — dropped here rather than kept as history,
#: because the test below asserts the list is not stale and a comfortable stale
#: entry is exactly the suppression the two-list design exists to prevent.
#:
#: It is kept as an empty dict rather than deleted because the NEXT session
#: that must disclose a site it cannot close needs somewhere honest to put it,
#: and `test_every_entry_of_the_conversion_allowlist_carries_a_reason` already
#: guards what goes in.
_CARRIED_ECHOING_SITES: dict[str, str] = {}


def test_no_unguarded_conversion_of_a_document_token_is_unaccounted_for():
    """REVIEW MAJOR-2's method, committed. The four sites the review found are
    absent from both lists below because they now funnel through
    `date_tokens`; reverting any one of them puts it back in the census and
    fails here, which is what mutants M1-M4 assert."""
    census = implicit_conversion_census(sorted(CHAIN_GUARDED))
    accounted = set(_CANNOT_ECHO) | set(_CARRIED_ECHOING_SITES)
    unaccounted = sorted(set(census) - accounted)
    stale = sorted(accounted - set(census))
    assert unaccounted == [], (
        "an unguarded conversion of a document token arrived in a "
        f"chain-guarded module and is in neither list: {unaccounted}"
    )
    assert stale == [], (
        f"the census no longer finds these; drop them from the list: {stale}"
    )


def test_every_entry_of_the_conversion_allowlist_carries_a_reason():
    """A list without reasons is a suppression. Both lists, so a site cannot be
    parked in the carried one without saying what it echoes."""
    for entry, reason in {**_CANNOT_ECHO, **_CARRIED_ECHOING_SITES}.items():
        assert isinstance(reason, str) and len(reason) >= 40, entry


def test_the_four_closed_sites_are_absent_from_the_census():
    """Stated as its own assertion rather than left implicit in the set
    difference, because this is the sentence review MAJOR-2 asks for."""
    census = implicit_conversion_census(sorted(CHAIN_GUARDED))
    for closed in (
        "analysis/chase.py:_parse_chase_business_export: date(",
        "analysis/columbia_bank.py:parse_columbia_bank_statement: date(",
        "analysis/scotia.py:parse_scotiabank_statement: date(",
        "analysis/scanned_small_bank.py:_date_from_mdyy: date(",
    ):
        assert not any(entry.startswith(closed) for entry in census), (
            f"{closed}...) is back in the census: the funnel was reverted"
        )


def test_the_census_can_see_a_date_on_a_regex_group_arriving():
    """The guard watched failing, on the exact shape of the four sites and on
    the two shapes it must NOT flag."""
    import tempfile

    cases = (
        # the site-6 shape: a group straight into date()
        ("def f(t):\n    m = R.search(t)\n    return date(2031, int(m.group(1)), 1)\n", 2),
        # the same call inside a handler that catches ValueError - not a finding
        ("def f(t):\n    m = R.search(t)\n    try:\n        return date(2031, int(m.group(1)), 1)\n"
         "    except ValueError:\n        return None\n", 0),
        # the funnel shape this closure installed - not a finding
        ("def f(t):\n    m = R.search(t)\n    iso = iso_or_none(2031, int(m.group(1)), 1)\n"
         "    return date.fromisoformat(iso)\n", 1),
        # nothing derived from a token at all
        ("def f():\n    return date(2031, 1, 1)\n", 0),
    )
    with tempfile.TemporaryDirectory() as directory:
        for index, (source, expected) in enumerate(cases):
            path = Path(directory) / f"synthetic_{index}.py"
            path.write_text(source, encoding="utf-8")
            found = _census_over_source(source, path.name)
            assert len(found) == expected, (source, found)


def _census_over_source(source: str, relative: str) -> list:
    """`implicit_conversion_census` over a string, for the mutant above."""
    tree = ast.parse(source)
    guarded = _guarded_call_ids(tree)
    found = []
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        tainted = _tainted_names(function)
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or id(node) in guarded:
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else None)
            if name not in _CONVERSION_CALLS:
                continue
            arguments = list(node.args) + [kw.value for kw in node.keywords]
            if any(
                _mentions_a_seed(argument) or (_mentioned_names(argument) & tainted)
                for argument in arguments
            ):
                found.append(f"{relative}:{function.name}: {ast.unparse(node)}")
    return sorted(found)

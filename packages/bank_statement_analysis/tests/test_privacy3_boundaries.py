"""PRIVACY-3: the remaining exception-text boundaries, proven (W3 §PRIVACY3).

Five carried findings, one law: **no exception this tree raises may quote the
document, and no boundary may publish one that does.**

Batch 6 closed the law three times — `analysis/money.py` (§MONEYPRIV),
`webapp/worker.py` (§WORKERPRIV), `analysis/extract.py` (§EXTRACTPRIV) — and
each closure ended with a ledger of sites it could see but did not own. This
file is the proof for those sites:

* the **date grammar** (`analysis/date_tokens.py`), which leaked exactly the
  way the money grammar did and was invisible for exactly the same reason:
  `int()` and `date()` were the raise, so there was no `raise` to grep for;
* the **three parser raise sites** this cell owns (`bmo`, `farmers_merchants`,
  `td_can`) and the fourteen escaping `strptime` calls in the three parser
  modules it owns;
* `webapp/app.py:revenue_review`, whose `str(exc)` HTTP body a browser puts
  straight into a `window.alert` (APP-PRIVACY);
* `webapp/worker.py`'s `BaseException` hole (#WORKERPRIV m-7), which is a
  fail-closed-status defect rather than an exception-text one;
* `analysis/pipeline.py`'s escalation guard, which had no `parse_mode` clause
  (§EXTRACTPRIV XP9 finding 2);
* and the census guard's own blind spots (#WORKERPRIV m-3).

Three kinds of proof, because the property has three ways to break and no one
kind sees all of them:

1. **Poisoned input**, driven through the real callables: neither the canary,
   nor the whole token, nor any digit run of three or more survives into
   `str(exc)`, the `__cause__`/`__context__` chain, or a rendered traceback.
2. **AST guards**, for the branches no input reaches — the two failures a
   dynamic sweep structurally cannot see are `raise X(...) from exc` and the
   same raise moved three lines up INTO the handler, where `__context__` is
   attached implicitly with nothing visible at the raise site (§MONEYPRIV
   MP12 MINOR-1, whose reviewer's mutants survived a one-clause guard).
3. **Structural census**, for the invariants that are about WHERE a value can
   travel rather than about what it says.
"""
from __future__ import annotations

import ast
import importlib
import traceback
from collections.abc import Mapping
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# The poison
# ---------------------------------------------------------------------------

#: A word no statement grammar can read and no source file contains. If it
#: comes out of an exception, it came out of the input.
CANARY = "ACMEPAYROLL"

#: A digit run of account-number length. Pinned separately from the canary
#: because §MONEYPRIV MP12 MINOR-6 measured that the canary-detected subset
#: UNDERSTATED the defect: nine of eighty leaking cells carried no canary at
#: all, they just echoed the figures.
DIGITS = "4471009238"

#: One per refusal branch of the date grammar, plus the two shapes that carry
#: no canary — so a proof that only looked for the canary would pass on them.
POISONED_DATE_TOKENS = {
    "plain-junk": CANARY,
    "junk+digits": f"{CANARY} {DIGITS}",
    "digits+junk": f"{DIGITS} {CANARY}",
    "empty": "   ",
    "over-long": f"{CANARY}/{CANARY}/{CANARY}/{DIGITS}/{DIGITS}",
    "month-out-of-range": "99/01/54",           # NO canary: date() echoes the 99
    "day-out-of-range": "02/30/54",             # NO canary: date() echoes the 30
    "year-out-of-range": "01/01/999999",        # NO canary: date() echoes the year
    "wrong-separator": f"01-15-{DIGITS}",
    "partial": "01",
}


def _leak_surfaces(exc: BaseException) -> dict[str, str]:
    """Everywhere a message can come out. All four, because closing one and
    leaving another is the failure §MONEYPRIV MP2 named: `raise ... from exc`
    passes any test written on `str(exc)` and leaks on the first traceback."""
    return {
        "str": str(exc),
        "repr": repr(exc),
        "args": repr(getattr(exc, "args", ())),
        "chain": " ".join(
            str(link)
            for link in (exc.__cause__, exc.__context__)
            if link is not None
        ),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }


def _digit_runs(text: str, minimum: int = 3) -> list[str]:
    runs: list[str] = []
    current = ""
    for char in text + " ":
        if char.isdigit():
            current += char
            continue
        if len(current) >= minimum:
            runs.append(current)
        current = ""
    return runs


def assert_private(exc: BaseException, token: str) -> None:
    """The whole law, in one assertion, over every surface."""
    poisoned_runs = set(_digit_runs(token))
    for surface, text in _leak_surfaces(exc).items():
        if surface == "traceback":
            # A traceback quotes the SOURCE line of every frame it walks, and a
            # source line that mentions the `token` VARIABLE is expected — it
            # cannot contain the token's runtime value. Subtract exactly those
            # lines, taken from `extract_tb` rather than guessed at by prefix:
            # a prefix filter ("drop lines starting with `raise`") would also
            # drop a real leak that happened to start that way, and it drifts
            # every time the production source is reindented.
            quoted = {
                frame.line.strip()
                for frame in traceback.extract_tb(exc.__traceback__)
                if frame.line
            }
            text = "\n".join(
                line for line in text.splitlines()
                if line.strip() not in quoted
                and not line.strip().startswith('File "')
            )
        assert CANARY not in text, f"canary in {surface}: {text[:200]}"
        if token.strip():
            assert token not in text, f"whole token in {surface}: {text[:200]}"
        for run in poisoned_runs:
            assert run not in text, f"digit run {run!r} in {surface}: {text[:200]}"
    assert exc.__cause__ is None, "the refusal carries a __cause__"
    assert exc.__context__ is None, "the refusal carries a __context__"


def _repository_modules(*, include_tests: bool = False):
    """(relative posix path, parsed AST) for every source module in the tree.

    NOTE THE FILTER, because getting it wrong makes a whole-repository
    assertion pass VACUOUSLY and look green: this test file runs from a git
    WORKTREE under `.claude/worktrees/<cell>/`, so every absolute path has
    `.claude` in its parts and a filter written on `path.parts` skips the
    entire repository. The filter is on the path RELATIVE to `PROJECT_ROOT`,
    and the count assertion below is what would catch it if it ever regressed.
    """
    skip = {".git", ".claude", ".venv", "__pycache__", "node_modules"}
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        try:
            relative = path.relative_to(PROJECT_ROOT)
        except ValueError:
            continue
        if set(relative.parts) & skip:
            continue
        if not include_tests and relative.parts[0] == "tests":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        yield relative.as_posix(), tree


def test_the_repository_walk_actually_sees_the_repository():
    """The vacuity check for every whole-tree assertion in this file. A filter
    written on the ABSOLUTE path's parts skips everything under a worktree and
    turns each of those tests into `assert [] == []`."""
    modules = dict(_repository_modules(include_tests=True))
    assert "analysis/money.py" in modules
    assert "ocr/local_tesseract.py" in modules
    assert "webapp/worker.py" in modules
    assert "tests/test_privacy3_boundaries.py" in modules
    assert len(modules) > 100, len(modules)
    assert dict(_repository_modules()).keys().isdisjoint(
        {"tests/test_privacy3_boundaries.py"}
    )


# ---------------------------------------------------------------------------
# 1. The date grammar (`analysis/date_tokens.py`)
# ---------------------------------------------------------------------------

from analysis import date_tokens as dt                                   # noqa: E402


#: Every raising entry point of the date grammar, with a call that reaches its
#: refusal. Driven by `__all__` below, so a reader added later cannot escape.
DATE_INVOCATIONS = {
    "iso_from_month_day": lambda token: dt.iso_from_month_day(token, 2054),
    "iso_from_month_day_year": lambda token: dt.iso_from_month_day_year(token),
    "parsed_datetime": lambda token: dt.parsed_datetime(
        token, "%m/%d/%Y", reader="probe"
    ),
}


@pytest.mark.parametrize("shape", sorted(POISONED_DATE_TOKENS))
@pytest.mark.parametrize("reader", sorted(DATE_INVOCATIONS))
def test_no_date_refusal_quotes_the_token(reader, shape):
    token = POISONED_DATE_TOKENS[shape]
    with pytest.raises(ValueError) as raised:
        DATE_INVOCATIONS[reader](token)
    assert_private(raised.value, token)


#: Spans that MATCH `_LONG_PERIOD_RE` and are not dates. The pattern's own
#: `(\d{1,2})` / `(\d{4})` bound what can reach `date()` here, so the poison is
#: an out-of-range day or year rather than a canary: this is precisely one of
#: §MONEYPRIV MP12 MINOR-6's "quoting without a canary" shapes, and a proof
#: that only looked for `ACMEPAYROLL` would pass on every row of it.
POISONED_LONG_PERIODS = {
    "day-out-of-range": "April 99, 2054 through May 4, 2054",
    "second-day-out-of-range": "April 4, 2054 through May 77, 2054",
    "february-30": "February 30, 2054 through March 4, 2054",
    "year-zero": "April 4, 0000 through May 4, 0000",
}


@pytest.mark.parametrize("shape", sorted(POISONED_LONG_PERIODS))
def test_period_from_long_dates_refuses_privately(shape):
    """The one raiser whose input is a whole markdown document rather than a
    cell. Before this cell, `date(int(sy), start_month, int(sd))` was the raise
    and Python 3.13+ echoes the offending number back —
    ``day 99 must be in range 1..30 for month 4 in year 2054`` — so the printed
    day AND the printed year rode out on the message of a helper documented to
    return None."""
    span = POISONED_LONG_PERIODS[shape]
    markdown = f"Statement period: {span}. {CANARY} {DIGITS}"
    with pytest.raises(ValueError) as raised:
        dt.period_from_long_dates(markdown)
    assert_private(raised.value, markdown)
    assert "reader=period_from_long_dates" in str(raised.value)


def test_the_date_refusal_vocabulary_is_closed_and_enumerable():
    """Four categories, and the set is writable without a document in hand —
    the property `_refusal_class` exists to have."""
    produced = {
        dt._refusal_class(token) for token in POISONED_DATE_TOKENS.values()
    } | {dt._refusal_class("01/15/2054"), dt._refusal_class("")}
    assert produced == {
        "the cell is empty",
        "no digits in the cell",
        f"longer than the {dt.MAX_DATE_TOKEN_CHARS}-character bound",
        "not a date in the reader's format",
    }


def test_a_date_refusal_names_the_reader_that_actually_refused():
    """The reason is only worth carrying if it is actionable. Both halves are
    pinned so a reworded message fails here rather than degrading silently."""
    with pytest.raises(ValueError) as raised:
        dt.iso_from_month_day(CANARY, 2054)
    message = str(raised.value)
    assert message.startswith("date grammar refused a printed token")
    assert "reader=iso_from_month_day" in message
    assert "no digits in the cell" in message


def test_the_century_mode_refusal_names_the_legal_values_and_not_the_illegal_one():
    """An API misuse by our own caller, not a reading of a document — but it
    used to echo its argument, and `century` is a parameter a future caller
    could hand a document-derived string."""
    with pytest.raises(ValueError) as raised:
        dt.iso_from_month_day_year("1/15/54", century=CANARY)
    assert CANARY not in str(raised.value)
    assert str(raised.value) == "unknown century mode: expected 'short' or 'always'"


#: Exported raisers whose poison is not a TOKEN, so they cannot be driven by
#: `DATE_INVOCATIONS` and are swept by a test of their own. Declared rather
#: than left implicit, because the coverage test below is only honest if the
#: things it skips are named: `period_from_long_dates` takes a whole markdown
#: document and refuses only on a span that MATCHES `_LONG_PERIOD_RE`, which no
#: entry in `POISONED_DATE_TOKENS` does — so a coverage test driven by tokens
#: alone would silently report it clean.
SWEPT_BY_THEIR_OWN_TEST = {
    "period_from_long_dates": "test_period_from_long_dates_refuses_privately",
}


def test_the_separately_swept_exports_really_are_swept():
    """The exemption above may not outlive the test it points at."""
    for name, test_name in SWEPT_BY_THEIR_OWN_TEST.items():
        assert name in dt.__all__, f"{name} is no longer exported"
        assert test_name in globals(), f"{test_name} no longer exists"


def test_every_raising_export_of_the_date_grammar_is_swept():
    """A privacy law is a property of the exported surface, and a hand-list
    proves only the members someone remembered (§MONEYPRIV MP6). A reader added
    to `__all__` that RAISES on a poisoned token must join `DATE_INVOCATIONS`
    or this fails.

    KNOWN LIMIT, stated rather than left for a reviewer to find: this drives
    each export with one and two positional arguments and a `century` keyword,
    so it sees the raisers whose poison is a TOKEN. `SWEPT_BY_THEIR_OWN_TEST`
    names the ones it structurally cannot reach, and a raiser that is in
    neither place is what this assertion is for.
    """
    unswept = []
    for name in dt.__all__:
        member = getattr(dt, name)
        if not callable(member) or name in DATE_INVOCATIONS:
            continue
        if name in SWEPT_BY_THEIR_OWN_TEST:
            continue
        for token in POISONED_DATE_TOKENS.values():
            for call in (
                lambda: member(token),
                lambda: member(token, 2054),
                lambda: member(token, century="short"),
            ):
                try:
                    call()
                except (ValueError, LookupError, ArithmeticError) as exc:
                    unswept.append(f"{name}: raises {type(exc).__name__}")
                except Exception:
                    pass                       # a signature mismatch, not a raiser
    assert unswept == [], (
        "a raising export of analysis/date_tokens.py is outside the poisoned "
        f"sweep; add it to DATE_INVOCATIONS: {sorted(set(unswept))}"
    )


def test_iso_within_period_cannot_raise_because_the_triple_is_already_proven():
    """The site this cell deliberately did NOT wrap, asserted rather than
    argued: `year_within_period` returns a year only for a candidate it already
    constructed with the same month/day inside its own `try`, so the `date()`
    below it has no failing input. A handler here would be a handler that can
    never fire."""
    from datetime import date as _date

    start, end = _date(2054, 1, 1), _date(2054, 12, 31)
    for token in ("99/99", "02/30", "13/01", "00/00"):
        assert dt.iso_within_period(token, start, end) is None


# ---------------------------------------------------------------------------
# CARRIED FINDING, now CLOSED by #HYGIENE8 (RAISE-PRIVACY-3): `date()` raises
# OverflowError, and OverflowError is not a ValueError
# ---------------------------------------------------------------------------

def test_the_overflow_contract_is_closed_and_the_scope_of_the_constructor_claim():
    """This section used to PIN the defect
    (`test_an_over_long_integer_reaches_date_as_an_overflow_error_not_a_refusal`).

    `datetime.date(2054, 1, 4471009238)` raises `OverflowError: Python int too
    large to convert to C long`, an `ArithmeticError` and not a `ValueError`, so
    every `except ValueError` in the date layer let it through. It was never a
    privacy defect - the message is a fixed CPython sentence - but it WAS a
    contract defect, and §PRIVACY3 carried it because changing what those
    helpers return is a behaviour change with a sweep of its own.

    #HYGIENE8 took the sweep and closed it: every conversion guard in
    `analysis/date_tokens.py` now catches both, so each entry point honours the
    contract its own docstring states. The census, the eleven entry points and
    the mutants are in `tests/test_raise_privacy3.py`; what stays here is the
    two things this file asserted about ITS OWN scope.
    """
    from datetime import date as _date

    huge = int(DIGITS)
    # 1. the mechanism is unchanged - `date()` still overflows, so the closure
    #    is a handler and not a CPython accident.
    with pytest.raises(OverflowError) as raised:
        _date(2054, 1, huge)
    assert DIGITS not in str(raised.value)
    # 2. the "one constructor" claim above is about what the date grammar
    #    RAISES, and the helpers documented to return None still return it.
    assert dt.iso_or_none(2054, 1, huge) is None
    assert dt.year_within_period(1, huge, _date(2054, 1, 1), _date(2054, 12, 31)) is None
    with pytest.raises(ValueError) as raised:
        dt.iso_from_month_day(f"1/{DIGITS}", 2054)
    assert "date grammar refused a printed token" in str(raised.value)
    assert DIGITS not in str(raised.value)


# ---------------------------------------------------------------------------
# 2. The parser raise sites this cell owns
# ---------------------------------------------------------------------------

from analysis import bmo, farmers_merchants, td_can                      # noqa: E402

#: The money-shaped poison. Separate from the date shapes because the money
#: grammar's refusal classes measure different things.
POISONED_MONEY_TOKENS = {
    "plain-junk": CANARY,
    "junk+amount": f"{CANARY} 1,234.56",
    "amount+junk": f"1,234.56 {CANARY}",
    "over-bound": f"99999999999999.00 {CANARY}",
    "emdash-sign": "—$500.00",                       # MG-D's case; NO canary
    "digits": DIGITS,
}

PARSER_INVOCATIONS = {
    "bmo._amount": bmo._amount,
    "farmers_merchants._amount": farmers_merchants._amount,
}


@pytest.mark.parametrize("shape", sorted(POISONED_MONEY_TOKENS))
@pytest.mark.parametrize("site", sorted(PARSER_INVOCATIONS))
def test_no_parser_money_refusal_quotes_the_cell(site, shape):
    token = POISONED_MONEY_TOKENS[shape]
    try:
        PARSER_INVOCATIONS[site](token)
    except ValueError as exc:
        assert_private(exc, token)
    else:
        pass                                   # the grammar read it; nothing raised


@pytest.mark.parametrize("shape", sorted(POISONED_DATE_TOKENS))
def test_the_td_can_native_date_refusal_quotes_nothing(shape):
    token = POISONED_DATE_TOKENS[shape]
    with pytest.raises(ValueError) as raised:
        td_can._native_date_to_iso(token, default_year=2054)
    assert_private(raised.value, token)


@pytest.mark.parametrize("site", sorted(PARSER_INVOCATIONS))
def test_a_parser_money_refusal_names_its_own_site(site):
    with pytest.raises(ValueError) as raised:
        PARSER_INVOCATIONS[site](CANARY)
    assert f"reader={site}" in str(raised.value)


def test_the_td_can_refusal_names_its_own_site():
    with pytest.raises(ValueError) as raised:
        td_can._native_date_to_iso(CANARY, default_year=2054)
    assert "reader=td_can._native_date_to_iso" in str(raised.value)


# ---------------------------------------------------------------------------
# 3. The strptime class — the sites, and the sites that were already closed
# ---------------------------------------------------------------------------

#: The parser modules whose `strptime` calls this cell repointed, with the
#: module-local seam each one goes through.
STRPTIME_MODULES = ("community_section", "demo_national", "relay")


def _strptime_calls(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strptime"
    ]


@pytest.mark.parametrize("module", STRPTIME_MODULES)
def test_the_repointed_modules_call_strptime_nowhere(module):
    """`datetime.strptime`'s own ValueError is
    ``time data '<the printed date>' does not match format '...'``. The whole
    class is closed in these three modules by there being no call left to
    leak."""
    assert _strptime_calls(PROJECT_ROOT / "analysis" / f"{module}.py") == []


def test_the_only_direct_strptime_left_in_the_date_layer_is_the_guarded_one():
    """`analysis/dates.py:parse_date` catches its own ValueError and returns
    None (it is §MONEYPRIV MP8's named counter-example), and
    `date_tokens.parsed_datetime` is this cell's shared seam. Any third direct
    caller in these two modules is a new leak."""
    assert len(_strptime_calls(PROJECT_ROOT / "analysis" / "dates.py")) == 1
    assert len(_strptime_calls(PROJECT_ROOT / "analysis" / "date_tokens.py")) == 1


@pytest.mark.parametrize("module,function", [
    ("burke_herbert", "parse_burke_herbert_statement"),
    ("huntington", "_period"),
])
def test_the_already_closed_strptime_sites_stay_closed(module, function):
    """The census correction, pinned. The batch-6 ledger named twenty strptime
    sites; four of them — burke_herbert's two and huntington's two — sit inside
    a `try` whose handler returns None, so their message never escapes the
    function. They are OTHER CELLS' files (DECLINES-E owns huntington), so this
    cell listed rather than edited them; this test is what makes "already
    closed" a measurement instead of a claim, and it fails if a later edit
    moves a call out of its handler."""
    path = PROJECT_ROOT / "analysis" / f"{module}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    target = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function
    )
    guarded = {
        call.lineno
        for node in ast.walk(target)
        if isinstance(node, ast.Try)
        and any(
            handler.type is not None
            and getattr(handler.type, "id", None) in {"ValueError", "Exception"}
            for handler in node.handlers
        )
        for statement in node.body
        for call in ast.walk(statement)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "strptime"
    }
    every = {
        node.lineno
        for node in ast.walk(target)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "strptime"
    }
    assert every and every == guarded, (
        f"analysis/{module}.py:{function} has an UNGUARDED strptime call: "
        f"{sorted(every - guarded)}"
    )


# ---------------------------------------------------------------------------
# 4. The AST guard — the branches no input reaches
# ---------------------------------------------------------------------------

#: The modules whose every `raise` must be a BARE raise of a declared refusal
#: constructor (or a plain string literal), standing OUTSIDE any handler.
CHAIN_GUARDED = {
    "analysis/date_tokens.py": frozenset({"date_refusal"}),
    "analysis/money.py": frozenset({"_refusal"}),
    # The three parser raise sites this cell owns (review MINOR-2). The dynamic
    # sweep already drives all three, but the AST guard is what covers a raise
    # nothing executes - and a parser is exactly where a fourth one arrives, in
    # a commit about something else.
    # RAISE-PRIVACY-4 (batch 9) closed the eight carried `date()` sites in
    # these three readers, so `bmo` and `farmers_merchants` now raise the DATE
    # constructor as well as the money one. `td_can` already declared it and
    # gained two more raises through it.
    "analysis/bmo.py": frozenset({"money_refusal", "date_refusal"}),
    "analysis/farmers_merchants.py": frozenset({"money_refusal", "date_refusal"}),
    "analysis/td_can.py": frozenset({"date_refusal"}),
    # RAISE-PRIVACY-3 (#HYGIENE8): the five sites §P10 listed in other cells'
    # files. `columbia_bank` and `scotia` hold no `raise` at all - their leak
    # was an escaping `strptime`, closed by repointing it at
    # `date_tokens.parsed_datetime` - and they are registered anyway for the
    # same reason bmo and farmers_merchants were: the guard's job is the raise
    # that ARRIVES, and a period reader is exactly where the next one lands.
    "analysis/chase.py": frozenset({"money_refusal", "date_refusal"}),
    "analysis/scanned_small_bank.py": frozenset({"money_refusal", "date_refusal"}),
    "analysis/columbia_bank.py": frozenset({"money_refusal", "date_refusal"}),
    "analysis/scotia.py": frozenset({"money_refusal", "date_refusal"}),
}


def _chain_offenders(source: str, relative: str, constructors: frozenset[str]) -> list[str]:
    """Three clauses, because the property has three ways to break.

    1. the message not coming from the constructor;
    2. an explicit `from exc`, which attaches a `__cause__` a traceback
       renderer prints;
    3. a raise sitting INSIDE an `except` handler, where `__context__` is
       attached implicitly and nothing is visible at the raise site.

    Clauses 2 and 3 are the ones a dynamic sweep structurally cannot see on an
    unreached branch (§MONEYPRIV MP12 MINOR-1, where a reviewer's mutants
    survived a guard that had only clause 1).
    """
    tree = ast.parse(source)
    handler_raises: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            handler_raises.update(
                id(child) for child in ast.walk(node) if isinstance(child, ast.Raise)
            )
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        where = f"{relative}:{node.lineno}"
        if node.cause is not None:
            offenders.append(f"{where}: `raise ... from ...` attaches a __cause__")
        if id(node) in handler_raises:
            offenders.append(f"{where}: raised INSIDE an except handler (__context__)")
        call = node.exc
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            if call.func.id in constructors:
                continue
            literal = call.args and all(
                isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                for arg in call.args
            )
            if literal:
                continue
        offenders.append(
            f"{where}: not `raise {'/'.join(sorted(constructors))}(...)` "
            "and not a plain string literal"
        )
    return offenders


@pytest.mark.parametrize("relative", sorted(CHAIN_GUARDED))
def test_every_raise_in_a_guarded_grammar_is_the_constructor_and_is_unchained(relative):
    path = PROJECT_ROOT / relative
    offenders = _chain_offenders(
        path.read_text(encoding="utf-8"), relative, CHAIN_GUARDED[relative]
    )
    assert offenders == [], f"chain-guard offenders: {offenders}"


#: One synthetic module per way the property breaks, so the guard is watched
#: failing rather than trusted. The clean shapes are here too: a guard that
#: flags everything is not a guard either.
_CHAIN_MUTANTS = [
    ("clean-constructor",
     "def f(t):\n    try:\n        return int(t)\n    except ValueError:\n"
     "        pass\n    raise date_refusal('f', t)\n", 0),
    ("clean-literal",
     "def f(t):\n    raise ValueError('a fixed reason')\n", 0),
    ("clean-bare-reraise",
     "def f(t):\n    try:\n        return int(t)\n    except ValueError:\n"
     "        raise\n", 0),
    ("explicit-chain",
     "def f(t):\n    try:\n        return int(t)\n    except ValueError as exc:\n"
     "        pass\n    raise date_refusal('f', t) from exc\n", 1),
    ("implicit-chain",
     "def f(t):\n    try:\n        return int(t)\n    except ValueError:\n"
     "        raise date_refusal('f', t)\n", 1),
    ("both-chains",
     "def f(t):\n    try:\n        return int(t)\n    except ValueError as exc:\n"
     "        raise date_refusal('f', t) from exc\n", 2),
    ("foreign-constructor",
     "def f(t):\n    raise ValueError(t)\n", 1),
    ("fstring-message",
     "def f(t):\n    raise ValueError(f'refused {t}')\n", 1),
    ("from-none",
     "def f(t):\n    try:\n        return int(t)\n    except ValueError:\n"
     "        pass\n    raise date_refusal('f', t) from None\n", 1),
]


@pytest.mark.parametrize("name,source,expected", _CHAIN_MUTANTS,
                         ids=[case[0] for case in _CHAIN_MUTANTS])
def test_the_chain_guard_can_actually_see_each_break(name, source, expected):
    offenders = _chain_offenders(source, "mutant.py", frozenset({"date_refusal"}))
    assert len(offenders) == expected, f"{name}: {offenders}"


def test_from_none_is_not_a_fix_and_the_guard_says_so():
    """Stated as its own case because it is the plausible wrong answer.
    `from None` clears `__cause__` and sets a RENDERING hint; `__context__`
    still holds the original object, so anything that walks the chain — a
    structured logger, a crash reporter, `traceback.print_exc` on some
    configurations — still has the quoted cell."""
    source = (
        "def f(t):\n    try:\n        return int(t)\n"
        "    except ValueError:\n        raise date_refusal('f', t) from None\n"
    )
    offenders = _chain_offenders(source, "mutant.py", frozenset({"date_refusal"}))
    assert any("INSIDE an except handler" in line for line in offenders)


def test_the_date_refusal_constructor_returns_rather_than_raises():
    """§MONEYPRIV MP2 / §EXTRACTPRIV XP2: returning keeps the constructor's own
    frame — which holds the token — out of the raised traceback entirely."""
    exception = dt.date_refusal("probe", CANARY)
    assert isinstance(exception, ValueError)
    assert exception.__traceback__ is None


def test_the_date_refusal_attaches_no_state_to_the_exception():
    """§EXTRACTPRIV XP12 MINOR-1's surviving mutant, closed here in advance:
    `str(exc)` stands in for "what the exception says", not for "what the
    exception CARRIES". An attribute holding the token is one `repr()`, one
    `pickle` or one structured logger away from publishing it."""
    exception = dt.date_refusal("probe", f"{CANARY} {DIGITS}")
    assert exception.__dict__ == {}
    assert len(exception.args) == 1 and isinstance(exception.args[0], str)


def test_the_date_refusal_constructor_assigns_to_no_attribute():
    """The static half of the same property: the dynamic test above sees only
    the shapes it calls."""
    tree = ast.parse((PROJECT_ROOT / "analysis" / "date_tokens.py").read_text(encoding="utf-8"))
    constructor = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "date_refusal"
    )
    offenders = [
        ast.unparse(node)
        for node in ast.walk(constructor)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign))
        and any(
            isinstance(target, (ast.Attribute, ast.Subscript))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
        )
    ]
    assert offenders == [], f"the constructor attaches state: {offenders}"


# ---------------------------------------------------------------------------
# 4b. RAISE-PRIVACY-4 — the raw `date()` census over the three rerouted readers
# ---------------------------------------------------------------------------
#
# W3 §H14 closed four `date()` sites, disclosed EIGHT more it did not own, and
# warned about the NINTH: "a parser is exactly where a fourth one arrives, in a
# commit about something else". RAISE-PRIVACY-4 closed the eight. This is the
# guard that makes the ninth visible the day it is written.
#
# It is deliberately STRICTER than `test_raise_privacy3.py`'s
# implicit-conversion census, which exempts a call standing inside a handler
# that catches `ValueError`. Two reasons, and neither is style:
#
# * `except ValueError` does NOT catch `OverflowError`, which `date()` raises
#   for a year past the C `int` it parses its arguments into. A handler-guarded
#   `date()` is only safe while its year is bounded, and that is a property of
#   the CALLER, which is exactly the kind of protection that disappears when a
#   caller changes (§PRIVACY3's measurement over `date_tokens`'s eleven entry
#   points: eight let it escape, and the two that did not were saved by a regex
#   rather than by a handler).
# * the census's exemption is a rule; this list is an ENUMERATION. A rule
#   admits the next site silently. A list of one has to be edited.
#
# So: in these three readers, every bare `date(...)` / `datetime(...)`
# CONSTRUCTION that is not built purely from literals is reported, and the
# allowlist below is the whole of what may stand. `date.fromisoformat(iso)` on
# an `iso` a `date_tokens` funnel returned is not a construction from
# components and is not reported — it is the shape the reroute installs.

#: The readers RAISE-PRIVACY-4 rerouted. Named rather than derived, because a
#: derived population ("every parser") would grow silently and this guard's
#: value is that its list of exceptions is one line long.
RAW_DATE_CENSUS_MODULES = (
    "analysis/bmo.py",
    "analysis/farmers_merchants.py",
    "analysis/td_can.py",
)

#: Every raw construction that MAY stand in those three readers, with the
#: reason that proves it cannot put a printed number into a message. Exactly
#: one entry: the ninth line, and the reason is measured in
#: `tests/test_raise_privacy4.py`, not asserted here.
RAW_DATE_ALLOWED = {
    "analysis/bmo.py:parse_bmo_statement: date(year, month, day)":
        "the transaction-row date, and the ONLY line of the nine the card "
        "listed that §H14's census did not report: it stands inside "
        "`except ValueError: continue`, so nothing it raises escapes the "
        "reader, and its year comes from `dates.resolve_year` over a period "
        "matched by `(\\d{4})`, so it cannot raise `OverflowError` either",
}


def _scoped_nodes(tree: ast.AST) -> list[tuple[str, ast.AST]]:
    """`(scope, node)` for every node under `tree`, each attributed ONCE.

    The scope is the nearest enclosing `def` / `async def` / `lambda`, dotted
    for nesting (`outer.inner`, `outer.<lambda>`), and `<module>` for the
    module body itself.

    RAISE-PRIVACY-4's review, MINOR-5: the raw-`date()` census below walked
    `FunctionDef` bodies only, so a construction at MODULE scope or inside a
    module-level `lambda` was not reported at all while its claim was written
    over "every bare `date(...)` built from anything but literals". A
    module body runs at import with no document in hand, but a module-level
    `lambda` helper called per row is an ordinary shape and it would have
    slipped past. Both censuses in this file walk through here instead, so
    the claim and the walk are the same thing — and a construction inside a
    nested `def` is now reported once rather than once per enclosing function.
    """
    found: list[tuple[str, ast.AST]] = []

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            found.append((scope, child))
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = child.name
            elif isinstance(child, ast.Lambda):
                name = "<lambda>"
            else:
                visit(child, scope)
                continue
            visit(child, name if scope == "<module>" else f"{scope}.{name}")

    visit(tree, "<module>")
    return found


def _raw_date_constructions(source: str, relative: str) -> list[str]:
    """`module:scope: call` for every `date()`/`datetime()` built from a name.

    A construction whose every argument is a literal is not a reading of a
    document and is not reported; anything else is, whether or not a handler
    stands around it, and wherever in the module it stands.
    """
    found: list[str] = []
    for scope, node in _scoped_nodes(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else None
        )
        if name not in ("date", "datetime"):
            continue
        arguments = list(node.args) + [kw.value for kw in node.keywords]
        if arguments and all(
            isinstance(argument, ast.Constant) for argument in arguments
        ):
            continue
        found.append(f"{relative}:{scope}: {ast.unparse(node)}")
    return sorted(found)


def test_no_raw_date_is_constructed_from_components_in_the_rerouted_readers():
    """RAISE-PRIVACY-4's generalisation. The eight sites are gone and the
    ninth is named; a tenth arriving in a commit about something else lands
    here with the reader and the call in the failure message."""
    found: list[str] = []
    for relative in RAW_DATE_CENSUS_MODULES:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        found.extend(_raw_date_constructions(source, relative))
    unaccounted = sorted(set(found) - set(RAW_DATE_ALLOWED))
    stale = sorted(set(RAW_DATE_ALLOWED) - set(found))
    assert unaccounted == [], (
        "a raw date construction from parsed components arrived in a rerouted "
        f"reader; funnel it through `date_tokens` or account for it: {unaccounted}"
    )
    assert stale == [], (
        f"these are no longer in the source; drop them from the list: {stale}"
    )


def test_every_entry_of_the_raw_date_allowlist_carries_a_reason():
    """A list without reasons is a suppression."""
    for entry, reason in RAW_DATE_ALLOWED.items():
        assert isinstance(reason, str) and len(reason) >= 40, entry


#: The guard watched failing — and watched NOT failing on the two shapes it
#: must not flag. A guard that flags everything is not a guard either.
_RAW_DATE_MUTANTS = [
    ("the-site-6-shape",
     "def f(t):\n    m = R.search(t)\n    return date(2059, int(m.group(1)), 1)\n", 1),
    ("inside-a-value-error-handler-is-STILL-reported",
     "def f(t):\n    m = R.search(t)\n    try:\n"
     "        return date(2059, int(m.group(1)), 1)\n"
     "    except ValueError:\n        return None\n", 1),
    ("the-attribute-spelling",
     "def f(t):\n    m = R.search(t)\n    return datetime.date(2059, int(m.group(1)), 1)\n", 1),
    ("the-funnel-shape-this-card-installed",
     "def f(t):\n    m = R.search(t)\n    iso = iso_or_none(2059, int(m.group(1)), 1)\n"
     "    if iso is None:\n        raise date_refusal('f', t)\n"
     "    return date.fromisoformat(iso)\n", 0),
    ("a-constant-only-construction",
     "def f():\n    return date(2059, 1, 1)\n", 0),
    # The three shapes review MINOR-5 measured as UNREPORTED, now reported.
    ("at-module-scope",
     "m = R.search(TEXT)\nSTAMP = date(2059, int(m.group(1)), 1)\n", 1),
    ("inside-a-module-scope-lambda",
     "stamp = lambda m: date(2059, int(m.group(1)), 1)\n", 1),
    ("inside-a-nested-def-reported-once",
     "def outer(t):\n    def inner(m):\n        return date(2059, int(m.group(1)), 1)\n"
     "    return inner\n", 1),
    ("inside-a-method",
     "class C:\n    def f(self, m):\n        return date(2059, int(m.group(1)), 1)\n", 1),
]


@pytest.mark.parametrize("name,source,expected", _RAW_DATE_MUTANTS,
                         ids=[case[0] for case in _RAW_DATE_MUTANTS])
def test_the_raw_date_census_can_see_each_shape(name, source, expected):
    found = _raw_date_constructions(source, f"synthetic/{name}.py")
    assert len(found) == expected, (name, found)


def test_the_scope_walker_attributes_every_construction_exactly_once():
    """MINOR-5's other half, stated as a property rather than as four counts:
    the walker names the scope it reports, so a census entry is readable, and
    a nested shape is one entry rather than one per enclosing function."""
    source = (
        "TOP = date(2059, int(x), 1)\n"
        "lam = lambda m: date(2059, int(m), 1)\n"
        "def outer(t):\n"
        "    def inner(m):\n"
        "        return date(2059, int(m), 1)\n"
        "    return inner\n"
        "class C:\n"
        "    def method(self, m):\n"
        "        return date(2059, int(m), 1)\n"
    )
    assert _raw_date_constructions(source, "s.py") == [
        "s.py:<lambda>: date(2059, int(m), 1)",
        "s.py:<module>: date(2059, int(x), 1)",
        "s.py:method: date(2059, int(m), 1)",
        "s.py:outer.inner: date(2059, int(m), 1)",
    ]


# ---------------------------------------------------------------------------
# 4c. RAISE-PRIVACY-5 — the LOOKUP census over the same three readers
# ---------------------------------------------------------------------------
#
# §4b's census walks CALLS, because a conversion is a call. The echo
# RAISE-PRIVACY-4 disclosed and did not close is not a call at all: it is
# `_MONTHS[sm]`, and a `KeyError`'s message IS its key, so the printed word
# rides out on `str`, `repr`, `args` and the first rendered traceback with no
# `raise` anywhere to grep for. `_CONVERSION_CALLS` in
# `tests/test_raise_privacy3.py` is `{date, datetime, int, float, Decimal,
# strptime, fromisoformat}` and neither census walked `Subscript` nodes at all,
# so nothing in this tree reported it. This is that census.
#
# WHAT IT REPORTS, exactly — the claim and the walk are the same sentence: in
# these three readers, every SUBSCRIPT READ of a MAPPING whose key is not a
# literal. A mapping is either a name this module binds to a dict literal or
# dict comprehension anywhere in its own source, or a global of the imported
# reader that is a `Mapping` at import time (including one level of attribute,
# so `dt.MONTH_NUMBERS[word]` is reported as well as `_MONTHS[word]`).
#
# WHAT IT DOES NOT REPORT, and why each is not a hole:
#
# * `_MONTHS.get(word)` — the funnel this card installs, exactly as
#   `date.fromisoformat(iso)` is the funnel §4b does not report.
# * a literal key (`_TABLE["JAN"]`) — a key written in this source cannot have
#   come from a document.
# * a slice (`text[:3]`), a list or tuple index (`cells[i]`), a match group —
#   those are not mapping lookups, and an `IndexError` carries no key. A
#   mis-shaped grid is `pipeline`'s declared `KeyError` hazard and a different
#   law (`webapp/worker.py:_stage_failure` withholds it).
# * a mapping reached through a name this module never binds and never
#   imports — e.g. an attribute two levels deep. STATED, not discovered: the
#   depth is one, and `test_the_lookup_census_resolves_a_mapping_behind_an_
#   attribute` is what pins the depth that IS covered.
#
# THE KNOWN HOLES — shapes that ARE a document token indexing a table and that
# this census does NOT report today. RAISE-PRIVACY-5's review, MINOR-1: the
# list above was the list of things that are not holes, and it was read as if
# it were the whole list. These two clauses are the rest of it, measured rather
# than imagined (`_TOKEN_LOOKUP_UNREPORTED` drives each one at 0):
#
# * AN ALIAS bound from another NAME rather than from a dict literal —
#   `t = _MONTHS` and then `t[word]`. `_dict_literal_names` follows `Assign`
#   nodes whose VALUE is a `Dict`/`DictComp`, so `t` is never recognised as a
#   table. Widening it to follow name-to-name assignment is a dataflow
#   question, not a syntax one, and it is the next lookup-census card's job.
# * A SUBSCRIPT PERFORMED BY A CALL — `operator.getitem(_MONTHS, word)`,
#   `_MONTHS.__getitem__(word)`, `dict(_MONTHS)[word]`, or a helper that
#   performs the subscript from OUTSIDE these three modules. This census walks
#   `Subscript` nodes in three named files; a call is not one, and a fourth
#   file is not walked. (A helper INSIDE the three IS reported — the review
#   probed that and the census killed it.)
#
# WHAT THEIR PRACTICAL BITE IS, and it is measured rather than assumed: every
# one of these shapes installed at one of the REAL sites was killed by the
# DRIVES, because the drives check the printed word's absence from the raised
# exception and do not care how the lookup was spelled. They bite only at a
# NEW site that nothing drives — which is exactly the case a census exists for,
# and exactly why they are written down here instead of being left for the next
# reviewer to find.
#
# ONE MORE LIMIT, and it is about the ALLOWLIST rather than the walk: the
# allowlist is keyed by `file:scope: subscript` — a LINE, not a guard. Delete
# `_date_tokens`'s `if mon not in _MONTHS: continue` and the entry still
# matches and the census still passes; what catches that is the DRIVE, and
# mutant M7 is killed by that drive and by nothing else. Keying the entry to
# the guard (an AST check that a `Compare(NotIn)` on the same table dominates
# the subscript in the same block) would close the residue and is deliberately
# NOT done here: it is a census change, not a refusal change, and it belongs to
# the card that widens this census rather than to the one that opened it.

#: The same three readers as §4b, and named for the same reason: a derived
#: population would grow silently, and this guard's value is that its list of
#: exceptions is one line long.
TOKEN_LOOKUP_CENSUS_MODULES = RAW_DATE_CENSUS_MODULES

#: Every mapping subscript that MAY stand in those three readers, with the
#: reason that proves it cannot put a printed token into a message. Exactly
#: one entry, and it is the lookup-census twin of §4b's ninth line.
TOKEN_LOOKUP_ALLOWED = {
    "analysis/td_can.py:_date_tokens: _MONTHS[mon]":
        "the row-date lookup, and the ONLY one of the four this card did not "
        "reroute: `if mon not in _MONTHS: continue` stands two lines above it "
        "in the same loop body, so the subscript cannot raise and there is no "
        "refusal here to make private. Rerouting it would turn a SKIPPED "
        "token into a raise — a new refusal, which a hygiene card may not "
        "introduce — and the guard is DRIVEN in "
        "`tests/test_raise_privacy4.py::test_the_guarded_row_date_lookup_"
        "skips_a_non_month_word_on_both_trees`, not asserted here",
}


def _dict_literal_names(tree: ast.AST) -> set[str]:
    """Every name this module binds to a dict literal or comprehension.

    Anywhere — module scope, a function body, a method — because a lookup
    table built per document inside the reader is as much a table as a module
    constant is, and the census must not depend on where it was written.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not isinstance(value, (ast.Dict, ast.DictComp)):
            continue
        names.update(
            target.id for target in targets if isinstance(target, ast.Name)
        )
    return names


def _imported_mapping_names(module) -> set[str]:
    """Every global of an imported reader that is a `Mapping`, plus one level
    of attribute (`dt.MONTH_NUMBERS`), so a table the reader imported by
    MODULE rather than by name is covered too."""
    names: set[str] = set()
    for name, value in vars(module).items():
        if isinstance(value, Mapping):
            names.add(name)
            continue
        if isinstance(value, type(ast)):        # a module object
            names.update(
                f"{name}.{attribute}"
                for attribute, member in vars(value).items()
                if isinstance(member, Mapping) and not attribute.startswith("__")
            )
    return names


def _token_lookup_subscripts(
    source: str, relative: str, mappings: set[str] | frozenset[str] = frozenset()
) -> list[str]:
    """`module:scope: subscript` for every mapping READ whose key is not a
    literal, anywhere in the module."""
    tree = ast.parse(source)
    tables = set(mappings) | _dict_literal_names(tree)
    found: list[str] = []
    for scope, node in _scoped_nodes(tree):
        if not isinstance(node, ast.Subscript) or not isinstance(node.ctx, ast.Load):
            continue
        value = node.value
        if isinstance(value, ast.Name):
            root = value.id
        elif isinstance(value, ast.Attribute):
            root = ast.unparse(value)
        else:
            continue
        if root not in tables:
            continue
        key = node.slice
        # A literal key is written in THIS source; a slice is not a mapping
        # lookup at all and cannot raise a `KeyError` carrying a document.
        if isinstance(key, (ast.Constant, ast.Slice)):
            continue
        found.append(f"{relative}:{scope}: {ast.unparse(node)}")
    return sorted(found)


def test_no_document_token_indexes_a_lookup_table_in_the_rerouted_readers():
    """RAISE-PRIVACY-5's generalisation. `KeyError('<the printed word>')` is a
    leak with no `raise` to grep for; a fifth one arriving in a commit about
    something else lands here with the reader, the scope and the subscript in
    the failure message."""
    found: list[str] = []
    for relative in TOKEN_LOOKUP_CENSUS_MODULES:
        module = importlib.import_module(f"analysis.{Path(relative).stem}")
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        found.extend(
            _token_lookup_subscripts(source, relative, _imported_mapping_names(module))
        )
    unaccounted = sorted(set(found) - set(TOKEN_LOOKUP_ALLOWED))
    stale = sorted(set(TOKEN_LOOKUP_ALLOWED) - set(found))
    assert unaccounted == [], (
        "a mapping is indexed by a token a document supplied; route it through "
        f"`.get` and refuse with a fixed message, or account for it: {unaccounted}"
    )
    assert stale == [], (
        f"these are no longer in the source; drop them from the list: {stale}"
    )


def test_every_entry_of_the_lookup_allowlist_carries_a_reason():
    """A list without reasons is a suppression."""
    for entry, reason in TOKEN_LOOKUP_ALLOWED.items():
        assert isinstance(reason, str) and len(reason) >= 40, entry


def test_the_lookup_census_is_not_vacuous_on_the_reader_it_was_written_for():
    """The census resolves `_MONTHS` as a table — so a reported zero is a
    measurement rather than a name it never recognised."""
    from analysis import td_can

    tables = _imported_mapping_names(td_can)
    assert "_MONTHS" in tables and "_MOJIBAKE_TABLE" in tables
    source = (PROJECT_ROOT / "analysis/td_can.py").read_text(encoding="utf-8")
    reverted = source.replace(
        "start_month = _MONTHS.get(sm)", "start_month = _MONTHS[sm]", 1
    )
    assert reverted != source, "the funnel this census watches has been reworded"
    assert _token_lookup_subscripts(reverted, "analysis/td_can.py", tables) == [
        "analysis/td_can.py:_date_tokens: _MONTHS[mon]",
        "analysis/td_can.py:_parse_period: _MONTHS[sm]",
    ]


def test_the_lookup_census_resolves_a_mapping_behind_an_attribute():
    """The one level of attribute the claim above states, pinned: a reader
    that imports the date grammar as a MODULE and indexes its month table is
    reported exactly as one that imported the table by name."""
    from analysis import date_tokens

    tables = _imported_mapping_names(date_tokens) | {"dt.MONTH_NUMBERS"}
    assert "MONTH_NUMBERS" in _imported_mapping_names(date_tokens)
    source = "from analysis import date_tokens as dt\n\ndef f(w):\n    return dt.MONTH_NUMBERS[w]\n"
    assert _token_lookup_subscripts(source, "s.py", tables) == [
        "s.py:f: dt.MONTH_NUMBERS[w]",
    ]


#: The guard watched failing — and watched NOT failing on the shapes it must
#: not flag. Each source binds its own table so the static half of the census
#: is what is under test; the dynamic half is pinned by the two tests above.
_TOKEN_LOOKUP_MUTANTS = [
    ("the-site-shape",
     "T = {'JAN': 1}\ndef f(m):\n    return T[m.group(1)]\n", 1),
    ("at-module-scope",
     "T = {'JAN': 1}\nm = R.search(TEXT)\nSTAMP = T[m.group(1)]\n", 1),
    ("inside-a-module-scope-lambda",
     "T = {'JAN': 1}\nstamp = lambda m: T[m.group(1)]\n", 1),
    ("inside-a-nested-def-reported-once",
     "T = {'JAN': 1}\ndef outer(t):\n    def inner(m):\n        return T[m.group(1)]\n"
     "    return inner\n", 1),
    ("a-table-built-inside-the-reader",
     "def f(cells, w):\n    table = {c: i for i, c in enumerate(cells)}\n"
     "    return table[w]\n", 1),
    ("the-membership-test-does-not-excuse-the-subscript",
     "T = {'JAN': 1}\ndef f(w):\n    if w in T:\n        return T[w]\n    return None\n", 1),
    # The shapes it must NOT flag.
    ("the-get-shape-this-card-installed",
     "T = {'JAN': 1}\ndef f(w):\n    n = T.get(w)\n    if n is None:\n"
     "        raise KeyError('a fixed sentence')\n    return n\n", 0),
    ("a-literal-key",
     "T = {'JAN': 1}\ndef f():\n    return T['JAN']\n", 0),
    ("a-slice-of-the-printed-text",
     "def f(text):\n    return text[:3]\n", 0),
    ("a-list-index",
     "def f(cells, i):\n    return cells[i]\n", 0),
    ("a-write-into-the-table",
     "T = {}\ndef f(w, n):\n    T[w] = n\n", 0),
]


@pytest.mark.parametrize("name,source,expected", _TOKEN_LOOKUP_MUTANTS,
                         ids=[case[0] for case in _TOKEN_LOOKUP_MUTANTS])
def test_the_lookup_census_can_see_each_shape(name, source, expected):
    found = _token_lookup_subscripts(source, f"synthetic/{name}.py")
    assert len(found) == expected, (name, found)


#: THE KNOWN HOLES, as drives rather than as prose. Each of these IS a document
#: token indexing a table and each is reported ZERO times today. This list is a
#: DISCLOSURE, not a property: it exists so the holes are measured, so a reader
#: cannot mistake the "not a hole" list above for the whole list, and so the
#: card that closes one of them gets a red test pointing straight at the
#: sentence it has to delete.
_TOKEN_LOOKUP_UNREPORTED = [
    ("an-alias-bound-from-another-name",
     "T = {'JAN': 1}\ndef f(w):\n    t = T\n    return t[w]\n"),
    ("operator-getitem",
     "import operator\nT = {'JAN': 1}\ndef f(w):\n    return operator.getitem(T, w)\n"),
    ("the-dunder-spelling",
     "T = {'JAN': 1}\ndef f(w):\n    return T.__getitem__(w)\n"),
    ("a-copy-of-the-table",
     "T = {'JAN': 1}\ndef f(w):\n    return dict(T)[w]\n"),
]


@pytest.mark.parametrize("name,source", _TOKEN_LOOKUP_UNREPORTED,
                         ids=[case[0] for case in _TOKEN_LOOKUP_UNREPORTED])
def test_the_known_holes_of_the_lookup_census_are_still_holes(name, source):
    """A hole nobody has written down is a hole nobody can close.

    If this goes RED the census has grown to cover the shape — which is good
    news and not a failure: move the row into `_TOKEN_LOOKUP_MUTANTS` with its
    expected count, and delete the matching clause from the KNOWN HOLES comment
    above so the comment and the walk stay the same sentence.
    """
    found = _token_lookup_subscripts(source, f"synthetic/{name}.py")
    assert found == [], (
        f"{name} is now REPORTED; the census covers it, so move it to the "
        f"must-see list and drop its clause from the KNOWN HOLES comment: {found}"
    )


def test_a_helper_inside_the_three_readers_is_reported_and_one_outside_is_not():
    """The fourth hole, which is about the POPULATION rather than the syntax.

    A helper that performs the subscript is reported when it lives in a file
    the census walks, and invisible when it lives anywhere else — because the
    census is three named files, by design (a derived population grows
    silently). Both halves are driven so the boundary is a measurement."""
    inside = (
        "T = {'JAN': 1}\n"
        "def month_of(w):\n    return T[w]\n"
        "def read(period):\n    return month_of(period[:3])\n"
    )
    assert _token_lookup_subscripts(inside, "analysis/td_can.py") == [
        "analysis/td_can.py:month_of: T[w]",
    ]
    outside = "from elsewhere import month_of\n\ndef read(period):\n    return month_of(period[:3])\n"
    assert _token_lookup_subscripts(outside, "analysis/td_can.py") == []


# ---------------------------------------------------------------------------
# 5. The `AmountFormat` / `_compiled` residency note (§MONEYPRIV MP8 item 4)
# ---------------------------------------------------------------------------

def test_no_amount_format_is_constructed_outside_the_money_grammar():
    """`parse_amount` is the last path in `analysis/money.py` by which a
    stdlib-quoting error could still return: it calls `float(text)` only after
    `_compiled(fmt.pattern).fullmatch(text)` succeeds, so the guard is the
    CALLER-SETTABLE `AmountFormat.pattern`.

    Two consequences, and the second is the one MP8 flagged and this test
    closes. A format whose pattern fullmatched something `float` cannot convert
    would raise `could not convert string to float: '<the cell>'` out of the
    module again. And `_compiled` is `lru_cache(maxsize=None)`, so a pattern
    built out of DOCUMENT TEXT would be retained, unboundedly, for the life of
    the process — a residency leak rather than a message one.

    Both are bounded by the same fact, which is now asserted instead of
    measured once: every `AmountFormat` in the repository is one of the
    thirteen constructed in `analysis/money.py`. Thirteen patterns is the
    cache's whole domain. A fourteenth construction ANYWHERE — including in a
    test, including with a pattern read off a statement — fails here.
    """
    offenders: list[str] = []
    for relative, tree in _repository_modules(include_tests=True):
        if relative in {"analysis/money.py", "tests/test_privacy3_boundaries.py"}:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "AmountFormat"
            ):
                offenders.append(f"{relative}:{node.lineno}")
    assert offenders == [], (
        "an AmountFormat is constructed outside analysis/money.py; "
        f"`_compiled`'s unbounded lru_cache is no longer domain-bounded: {offenders}"
    )


def test_the_money_grammar_constructs_exactly_the_thirteen_formats():
    """The other half: the bound is thirteen, and it is a number rather than a
    vague "only the module's own"."""
    tree = ast.parse((PROJECT_ROOT / "analysis" / "money.py").read_text(encoding="utf-8"))
    constructions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "AmountFormat"
    ]
    assert len(constructions) == 13


# ---------------------------------------------------------------------------
# 6. APP-PRIVACY — `webapp/app.py:revenue_review`
# ---------------------------------------------------------------------------

from analysis.revenue import apply_serialized_revenue_review               # noqa: E402
from webapp import app as webapp_app                                       # noqa: E402

#: A ValueError raised DEEPER than the declared refusals, carrying a cell. The
#: whole exposure: `except ValueError` is broader than the raises, and
#: `rebuild_serialized_revenue_views` sits under
#: `apply_serialized_revenue_review`.
POISONED_REVIEW_MESSAGE = f"could not convert string to float: '{CANARY} {DIGITS}'"


def test_the_declared_review_refusals_pass_through_verbatim():
    """The behaviour that must NOT be deleted. `webapp/static/app.js` throws
    `payload.error` and shows it to the analyst, so these seven are what an
    analyst actually reads when a review is refused."""
    for declared in webapp_app._DECLARED_REVIEW_REFUSALS:
        assert webapp_app._review_refusal(ValueError(declared)) == declared
        assert webapp_app._review_refusal(LookupError(declared)) == declared


#: The exact string a non-declared refusal must produce. Written out rather
#: than derived, because the mutant this kills is one character and a derived
#: expectation would mutate with it.
_REDUCED_REVIEW_ERROR = (
    "revenue review failed: ValueError "
    "(message withheld; an exception message can quote statement text)"
)


@pytest.mark.parametrize("shape", ["prefix", "suffix", "padded", "upper"])
def test_the_review_allow_list_is_exact_match_and_not_containment(shape):
    """The mutation this kills is one character: `==` to `in`.

    THE ASSERTION HAD TO BE STRENGTHENED, and the reason is worth the
    paragraph, because the first version of this test SURVIVED the mutant
    (measured, W3 §PRIVACY3 mutation round 1). Under containment the function
    still returns the tuple MEMBER, not the exception's text — so nothing
    leaks, `published != poisoned` holds, and a privacy-shaped assertion sees
    nothing wrong.

    What containment breaks is not privacy, it is TRUTH: an exception that
    quoted a cell alongside a declared literal would be published as the
    declared refusal, and `webapp/static/app.js` would show an analyst
    "transaction source location was not found" for a failure that was
    something else entirely. The boundary would be lying with one of its own
    constants. So the assertion is the exact reduced string, not the absence
    of the token.
    """
    declared = webapp_app._DECLARED_REVIEW_REFUSALS[0]
    poisoned = {
        "prefix": f"{declared}: {CANARY} {DIGITS}",
        "suffix": f"{CANARY} {DIGITS} - {declared}",
        "padded": f" {declared} ",
        "upper": declared.upper(),
    }[shape]

    published = webapp_app._review_refusal(ValueError(poisoned))

    assert published == _REDUCED_REVIEW_ERROR
    assert published != declared
    assert CANARY not in published
    assert DIGITS not in published


def test_an_undeclared_review_refusal_is_reduced_to_its_class():
    published = webapp_app._review_refusal(ValueError(POISONED_REVIEW_MESSAGE))
    assert published == _REDUCED_REVIEW_ERROR
    assert CANARY not in published and DIGITS not in published


def test_the_reduced_review_message_matches_the_worker_vocabulary():
    """Two boundaries, one sentence. An operator meeting a withheld message in
    a browser alert and a withheld message in the job store should not have to
    learn that they mean the same thing."""
    from webapp.worker import _stage_failure

    suffix = "(message withheld; an exception message can quote statement text)"
    assert webapp_app._review_refusal(RuntimeError(CANARY)).endswith(suffix)
    assert _stage_failure("analysis", RuntimeError(CANARY)).endswith(suffix)


def _analysis_with(transactions: list[dict]) -> dict:
    return {"statement": {"transactions": transactions}, "metrics": {}}


def _document_with(*accounts: list[dict]) -> dict:
    return {"document": {}, "accounts": [_analysis_with(transactions) for transactions in accounts]}


def _reviewable(source_location: str, **overrides) -> dict:
    record = {
        "source_location": source_location,
        "revenue_initial_classification": "unverified_deposit",
        "revenue_classification": "unverified_deposit",
        "is_posted": True,
    }
    record.update(overrides)
    return {"amount": 100.0, "classification": record}


#: One analysis payload per declared refusal, each reaching a DIFFERENT raise
#: in `analysis/revenue.py`. Two are the pair the batch-6 census missed: they
#: live in `rebuild_serialized_revenue_views`, which
#: `apply_serialized_revenue_review` calls on its way out. The last two came
#: with the review's account (a location numbers a posting within its account);
#: a fourth element is the account the review names.
_REVIEW_REFUSAL_DRIVERS = {
    "decision must be confirm, reject, or reset": (
        _analysis_with([]), "anywhere", CANARY,
    ),
    "transaction source location was not found": (
        _analysis_with([]), "p1:r1", "confirm",
    ),
    "only automatically unverified deposits can be reviewed": (
        _analysis_with([
            _reviewable("p1:r1", revenue_initial_classification="verified_revenue"),
        ]),
        "p1:r1", "confirm",
    ),
    "every posted credit must have an authoritative classification record": (
        _analysis_with([
            _reviewable("p1:r1"),
            {"amount": 250.0, "classification": None},
        ]),
        "p1:r1", "confirm",
    ),
    "every posted credit must have a valid revenue classification": (
        _analysis_with([
            _reviewable("p1:r1"),
            {"amount": 250.0, "classification": {
                "source_location": "p1:r2",
                "revenue_classification": CANARY,
                "is_posted": True,
            }},
        ]),
        "p1:r1", "confirm",
    ),
    "account was not found": (
        _analysis_with([_reviewable("p1:r1")]), "p1:r1", "confirm", 2,
    ),
    "transaction source location is in more than one account; name the account": (
        _document_with([_reviewable("p1:r1")], [_reviewable("p1:r1")]),
        "p1:r1", "confirm",
    ),
    # 5.6 (true revenue spec §10.7, §12): a confirm on a credit a rule verified, a record whose tier disagrees with
    # its state, and a payload whose posted credits carry a tier only in part.
    "a credit a rule verified can only be marked non-revenue": (
        _analysis_with([
            _reviewable("p1:r1", revenue_initial_classification="verified_revenue",
                        revenue_classification="verified_revenue", revenue_tier="verified",
                        revenue_initial_tier="verified"),
        ]),
        "p1:r1", "confirm",
    ),
    "every posted credit's revenue state must agree with its tier": (
        _analysis_with([
            _reviewable("p1:r1", revenue_tier="counted_flagged", revenue_initial_tier="counted_flagged"),
            {"amount": 250.0, "classification": {
                "source_location": "p1:r2", "revenue_classification": "unverified_deposit",
                "revenue_tier": "verified", "is_posted": True,
            }},
        ]),
        "p1:r1", "confirm",
    ),
    "every posted credit carries a revenue tier, or none does": (
        _analysis_with([
            _reviewable("p1:r1", revenue_tier="counted_flagged", revenue_initial_tier="counted_flagged"),
            _reviewable("p1:r2"),
        ]),
        "p1:r1", "confirm",
    ),
    # Audit round 3, R3-B02 (R3-21): a confirm on a credit that returns a confirmed funder's payment (rule D's pair).
    "a credit that returns a confirmed funder's payment can only be marked non-revenue": (
        _analysis_with([_reviewable("p1:r1", returns_funder_payment="transaction:3")]),
        "p1:r1", "confirm",
    ),
}


@pytest.mark.parametrize("declared", sorted(_REVIEW_REFUSAL_DRIVERS))
def test_every_declared_review_refusal_is_actually_raised(declared):
    """The coupling, in the direction that catches a REWORD. The allow-list is
    a copy of seven literals from another module; if one of those raises is
    reworded the tuple stops matching it and the user silently loses the named
    reason. This drives each one out of `analysis/revenue.py` for real."""
    analysis, source_location, decision, *account = _REVIEW_REFUSAL_DRIVERS[declared]
    with pytest.raises((ValueError, LookupError)) as raised:
        apply_serialized_revenue_review(
            analysis, source_location=source_location, decision=decision,
            account=account[0] if account else None,
        )
    assert str(raised.value) == declared
    assert declared in webapp_app._DECLARED_REVIEW_REFUSALS


def test_the_allow_list_holds_no_literal_that_nothing_raises():
    """The ratchet in the other direction: a stale entry is a permission
    nobody needs, and it would let a future raise of that text straight
    through."""
    assert set(webapp_app._DECLARED_REVIEW_REFUSALS) == set(_REVIEW_REFUSAL_DRIVERS)


def test_the_two_refusals_the_batch_six_census_missed_are_reachable():
    """W3 §WORKERPRIV WP6.1 counted three fixed literals in
    `analysis/revenue.py`. There are five, and the other two are reachable
    through this route because `apply_serialized_revenue_review`'s LAST
    statement calls `rebuild_serialized_revenue_views`. Measured rather than
    read off the file."""
    import inspect

    source = inspect.getsource(apply_serialized_revenue_review)
    assert "rebuild_serialized_revenue_views(analysis)" in source
    # Five, and two more since the review can name its account (a missing
    # account, and a location held by several accounts with none named), and
    # three more since 5.6's tiers (a confirm on a rule-verified credit, a tier
    # that disagrees with its state, a payload tiered only in part), and one
    # since audit round 3, R3-B02 (a confirm on a credit that returns a
    # confirmed funder's payment).
    assert len(webapp_app._DECLARED_REVIEW_REFUSALS) == 11


def test_the_browser_still_renders_the_review_error_body():
    """The other half of §WORKERPRIV WP3's lesson: an allow-list is only worth
    carrying because something shows it to a human."""
    app_js = (PROJECT_ROOT / "webapp" / "static" / "app.js").read_text(encoding="utf-8")
    assert "payload.error" in app_js


# ---------------------------------------------------------------------------
# 7. WORKER-PRIVACY m-7 — a BaseException may not strand a job
# ---------------------------------------------------------------------------

from webapp.jobs import JobStore                                           # noqa: E402
from webapp.storage import Storage                                         # noqa: E402
from webapp.worker import (                                                # noqa: E402
    _NON_TERMINAL_STATUSES,
    _STUCK_JOB_FAILURE,
    run_job,
)


class _FakeDoc:
    model = "test-model"
    pages = ["--- Page 1 ---\nBeginning Balance 1,000.00\n"]

    def to_markdown(self) -> str:
        return self.pages[0]


@pytest.fixture
def job_store(tmp_path):
    return JobStore(Storage(tmp_path / "data"))


def _arm(job_store, monkeypatch, *, raising: BaseException, at: str) -> str:
    monkeypatch.setattr(
        "webapp.worker.parse_statement",
        lambda pdf_bytes, source_file="", **kwargs: _FakeDoc(),
    )

    def boom(*args, **kwargs):
        raise raising

    monkeypatch.setattr(f"webapp.worker.{at}", boom)
    return job_store.create("m7.pdf").id


#: Every BaseException that is NOT an Exception and can plausibly reach a
#: worker thread. `SystemExit` and `GeneratorExit` arrive from the runtime,
#: `KeyboardInterrupt` from a signal.
_BASE_EXCEPTIONS = [
    KeyboardInterrupt(f"interrupted while reading {CANARY} {DIGITS}"),
    SystemExit(f"shutting down: {CANARY} {DIGITS}"),
    GeneratorExit(f"closed: {CANARY} {DIGITS}"),
]


@pytest.mark.parametrize(
    "exc", _BASE_EXCEPTIONS, ids=[type(e).__name__ for e in _BASE_EXCEPTIONS]
)
def test_a_base_exception_marks_the_job_failed_and_still_propagates(
    job_store, monkeypatch, exc
):
    """#WORKERPRIV m-7. Before this arm, a `BaseException` in the queue thread
    killed the thread with a traceback on stderr and left the job at
    `processing` with `error=None` - no durable write, no telemetry record, and
    a dashboard polling a job that would never move again. The store's startup
    `mark_interrupted` only reaches it after a RESTART, and a long-lived server
    never restarts.

    Both halves are asserted because either alone would be the wrong fix:
    swallowing a `SystemExit` would defeat a shutdown, and marking nothing
    leaves the stranded job."""
    job_id = _arm(job_store, monkeypatch, raising=exc, at="inspect_pdf")

    with pytest.raises(type(exc)):
        run_job(job_id, b"%PDF-m7", "m7.pdf", job_store)

    fetched = job_store.get(job_id)
    assert fetched.status == "error"
    assert fetched.status not in _NON_TERMINAL_STATUSES
    assert fetched.error == (
        f"preflight stage failed: {type(exc).__name__} "
        "(message withheld; an exception message can quote statement text)"
    )
    assert CANARY not in fetched.error and DIGITS not in fetched.error


def test_an_ordinary_exception_is_still_swallowed_and_not_re_raised(
    job_store, monkeypatch
):
    """The new arm must not change the arm above it. An `Exception` is the
    normal failure path and `run_job` returns rather than propagating, because
    the queue thread has more jobs to run."""
    job_id = _arm(
        job_store, monkeypatch,
        raising=ValueError(f"{CANARY} {DIGITS}"), at="inspect_pdf",
    )
    run_job(job_id, b"%PDF-ordinary", "m7.pdf", job_store)      # does not raise
    fetched = job_store.get(job_id)
    assert fetched.status == "error"
    assert "ValueError" in fetched.error
    assert CANARY not in fetched.error


def test_a_base_exception_inside_the_handler_still_leaves_a_terminal_job(
    job_store, monkeypatch
):
    """The `finally` arm, and the reason it exists: both `except` arms can
    themselves be interrupted. Here the ORDINARY arm's own `store.set_error`
    raises a `BaseException`, so nothing above the `finally` ever writes a
    status."""
    job_id = _arm(
        job_store, monkeypatch,
        raising=ValueError(f"{CANARY} {DIGITS}"), at="inspect_pdf",
    )
    calls = {"n": 0}
    original = JobStore.set_error

    def flaky(self, target_id, error):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt(f"interrupted mid-write {CANARY}")
        return original(self, target_id, error)

    monkeypatch.setattr(JobStore, "set_error", flaky)

    with pytest.raises(KeyboardInterrupt):
        run_job(job_id, b"%PDF-finally", "m7.pdf", job_store)

    fetched = job_store.get(job_id)
    assert fetched.status == "error"
    assert fetched.error == _STUCK_JOB_FAILURE
    assert CANARY not in fetched.error


def test_the_stuck_job_message_carries_no_exception_text_at_all():
    """By definition there is no exception object in the `finally`, so the
    message is a fixed literal - and it says what actually happened rather than
    naming a stage it cannot know."""
    assert "withheld" in _STUCK_JOB_FAILURE
    assert _STUCK_JOB_FAILURE.startswith("the worker stopped without publishing")


def test_the_finally_arm_is_a_no_op_on_the_success_path(job_store, monkeypatch):
    """Four `return`s live inside the `try`, so the `finally` runs on every
    successful job too. It must not overwrite a terminal state."""
    monkeypatch.setattr(
        "webapp.worker.parse_statement",
        lambda pdf_bytes, source_file="", **kwargs: _FakeDoc(),
    )

    def declined(markdown, parse_mode="auto", **kwargs):
        raise RuntimeError("no deterministic parser matched this statement")

    monkeypatch.setattr("webapp.worker.analyze_document", declined)
    job = job_store.create("ok.pdf")
    run_job(job.id, b"%PDF-ok", "ok.pdf", job_store, parse_mode="deterministic")
    fetched = job_store.get(job.id)
    assert fetched.status == "done"
    assert fetched.error is None
    assert fetched.analysis_error == "no deterministic parser matched this statement"


def test_the_non_terminal_vocabulary_matches_the_stores_own():
    """A frozenset of status strings is only correct while it matches the
    store's: a new job starts in one of them."""
    from webapp.jobs import Job

    assert Job(id="job", filename="statement.pdf").status in _NON_TERMINAL_STATUSES
    assert _NON_TERMINAL_STATUSES == frozenset({"queued", "processing"})


# ---------------------------------------------------------------------------
# 7b. MAJOR-1 - the QUEUE is not the JOB. CLOSED by #HYGIENE8
# (QUEUE-SUPERVISOR): `webapp/app.py:_process_job_queue` now releases the
# worker slot and re-arms a replacement before it re-raises, so the two
# KNOWN_LIMITATION tests that pinned the stranding here are gone. Their
# successors live in `tests/test_queue_supervisor.py`, which asserts the
# behaviour this section used to assert the absence of; P8.1's three-way
# measurement stands as the record of why the fix belongs on the supervisor
# rather than on `run_job`'s arm.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 8. PIPELINE-PARSEMODE — deterministic mode may not reach a hosted model
# ---------------------------------------------------------------------------

def test_the_escalation_guard_is_gone_and_the_escalation_model_is_never_read():
    """§EXTRACTPRIV XP9 finding 2, SUPERSEDED by P22-FENCE (ruling R9).

    Until Phase 2.2 this test asserted that the guard at the escalation call
    tested `parse_mode` FIRST — the one clause that made "no hosted-model call
    in deterministic mode" a property of the MODE rather than of the
    structurer's grounding. R9 removed the escalation call, its guard and the
    reconciliation-based selection behind it outright, so the clause this
    test defended no longer exists to be reordered. What it defended still
    holds, and now structurally in every mode: slice S3 of the model-code
    removal deleted the one hosted call R9 left (`analysis/extract.py`), and
    the test below pins that the module holds no handle to it.

    Asserted on the AST, in the inverse direction: no `If` in
    `analysis/pipeline.py` tests `settings.escalation_model`, and the name
    `escalation_model` is not read anywhere in the module — a mutant that
    re-adds the guard fails here before it fails the fence tests."""
    source = (PROJECT_ROOT / "analysis" / "pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guards = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and "escalation_model" in ast.unparse(node.test)
    ]
    assert guards == [], "the R9 escalation guard is back: " + ast.unparse(guards[0].test)
    reads = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "escalation_model"
    ]
    assert reads == [], "analysis/pipeline.py reads `escalation_model` again (R9)"


def pipeline_hosted_extraction_handles(source: str) -> list[str]:
    """Every way `analysis/pipeline.py`'s text could reach the removed hosted
    extractor: the name `extract_statement` as a name, an attribute, a
    parameter, an import alias or a string; any import of the module
    `extract` (relative or absolute, `from . import extract` included); and a
    read of the hosted model's name off the settings (`.model`, which
    `model_used` started from until slice S3). Empty when clean."""
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[-1] == "extract" or any(
                alias.name in {"extract", "extract_statement"} or alias.asname == "extract_statement"
                for alias in node.names
            ):
                found.append(f"import: {ast.unparse(node)}")
        elif isinstance(node, ast.Import):
            if any(alias.name.split(".")[-1] == "extract" for alias in node.names):
                found.append(f"import: {ast.unparse(node)}")
        elif isinstance(node, ast.Name) and node.id == "extract_statement":
            found.append(f"name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in {"extract_statement", "model"}:
            found.append(f"attribute: {ast.unparse(node)}")
        elif isinstance(node, ast.arg) and node.arg == "extract_statement":
            found.append(f"parameter: {node.arg}")
        elif isinstance(node, ast.Constant) and node.value == "extract_statement":
            found.append("string: 'extract_statement'")
    return found


def test_the_pipeline_holds_no_handle_to_a_hosted_extractor():
    """PIPELINE-PARSEMODE's property, now structural in every mode (model-code
    removal, slice S3). The two dynamic tests that stood here replaced the
    hosted extractor with a recorder and proved deterministic mode never
    called it, the structurer on or off; the extractor is deleted, so there is
    nothing left to record. What replaces them: `analysis/pipeline.py` has no
    `extract_statement` name and no import of an `extract` module, and reads
    no `.model` off its settings. A planted handle of each form fails."""
    import importlib.util

    source = (PROJECT_ROOT / "analysis" / "pipeline.py").read_text(encoding="utf-8")
    assert pipeline_hosted_extraction_handles(source) == []
    assert importlib.util.find_spec("analysis.extract") is None
    for planted in (
        "from .extract import extract_statement\n",
        "from . import extract\n",
        "import analysis.extract\n",
        "from analysis.extract import extract_statement as _hosted\n",
        "_hosted = extract_statement\n",
        "_hosted = getattr(object(), 'extract_statement', None)\n",
        "model_used = settings.model\n",
    ):
        assert pipeline_hosted_extraction_handles(source + "\n" + planted), planted



# ---------------------------------------------------------------------------
# 9. `.detail` readers in production
# ---------------------------------------------------------------------------
#
# Model-code removal, slice S2. This section guarded `ocr/availability.py`, the
# visual OCR endpoint probe, whose `VisualOcrStatus.detail` (a bounded
# transport-failure message) was read only by `message()` and printed only to a
# console. The probe was deleted with the visual OCR client, and the guards
# whose only subject it was went with it: `MAX_DETAIL_CHARS`, the probe's
# signature, the `message()` call-site census, the `VisualOcrStatus` holders and
# the `asdict` / `vars` / `__dict__` clauses scoped to them. The tree-wide half,
# which never depended on the probe, stays and still bites: a production
# `.detail` read, by ANY receiver or by `getattr` string, is allowed only where
# `ALLOWED_DETAIL_READERS` says why.


#: Every production `.detail` attribute read in the tree, and WHY each one is
#: allowed. The receiver's NAME is deliberately not part of the rule: the first
#: version of this guard matched `self`/`status` only, and the adversarial
#: review walked straight past it with
#: `def telemetry_detail(probe): return probe.detail` (review MINOR-1). A rule
#: keyed on what someone called their variable is not a rule.
ALLOWED_DETAIL_READERS = {
    "ocr/native_text.py":
        "_PageRefusal.detail - a DIFFERENT dataclass on a different object; it "
        "reaches deterministic_coverage_audit's CSV, which W3 SS-WORKERPRIV WP1 "
        "already ledgers as an internal artifact",
}


def _detail_attribute_sites() -> list[str]:
    return [
        f"{relative}:{node.lineno}"
        for relative, tree in _repository_modules()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "detail"
    ]


def _indirect_detail_reads(modules=None) -> list[str]:
    """The way to read `detail` WITHOUT writing `.detail`: `getattr(obj,
    "detail")` names the field as a string, and the attribute walk cannot see
    it. (The dataclass-wide `asdict` / `vars` / `__dict__` clauses were scoped
    to modules holding the deleted `VisualOcrStatus`, and left with it.)"""
    findings: list[str] = []
    for relative, tree in (modules if modules is not None else _repository_modules()):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) > 1
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "detail"
            ):
                findings.append(f"{relative}:{node.lineno}: getattr(..., 'detail')")
    return findings


def test_detail_is_read_in_production_only_where_allowed():
    """`detail` is read only in the files `ALLOWED_DETAIL_READERS` names, by ANY
    receiver, and never by `getattr` string. Asserted by FILE, never by line
    number: a guard that pins a line turns red the moment an unrelated change
    adds a line above it. The line numbers stay in the failure message."""
    detail_sites = _detail_attribute_sites()
    files = sorted({site.rsplit(":", 1)[0] for site in detail_sites})
    assert files == sorted(ALLOWED_DETAIL_READERS), detail_sites
    assert _indirect_detail_reads() == [], _indirect_detail_reads()


#: The reviewer's bypass, verbatim, plus the indirect read. Each must be FOUND;
#: the clean shape must not be.
_DETAIL_MUTANTS = [
    ("reviewer-bypass-any-receiver",
     "def telemetry_detail(probe):\n    return probe.detail\n", 1, 0),
    ("bare-name-receiver",
     "def f(x):\n    return x.detail\n", 1, 0),
    ("getattr-by-string",
     "def f(x):\n    return getattr(x, 'detail')\n", 0, 1),
    ("clean-unrelated-attribute",
     "def f(row):\n    return row.details\n", 0, 0),
]


@pytest.mark.parametrize("name,source,attribute_hits,indirect_hits", _DETAIL_MUTANTS,
                         ids=[case[0] for case in _DETAIL_MUTANTS])
def test_the_detail_guard_can_actually_see_each_bypass(
    name, source, attribute_hits, indirect_hits
):
    """Watched failing, in both halves. The first case is the review's own
    mutant: the previous guard keyed on the receiver being called `self` or
    `status`, so renaming it to `probe` walked straight through."""
    tree = ast.parse(source)
    attribute_sites = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "detail"
    ]
    assert len(attribute_sites) == attribute_hits, name
    assert len(_indirect_detail_reads([("mutant.py", tree)])) == indirect_hits, name
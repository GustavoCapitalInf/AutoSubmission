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
import traceback
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
    "month-out-of-range": "99/01/26",           # NO canary: date() echoes the 99
    "day-out-of-range": "02/30/26",             # NO canary: date() echoes the 30
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
    assert "ocr/availability.py" in modules
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
    "iso_from_month_day": lambda token: dt.iso_from_month_day(token, 2026),
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
    "day-out-of-range": "April 99, 2026 through May 4, 2026",
    "second-day-out-of-range": "April 4, 2026 through May 77, 2026",
    "february-30": "February 30, 2026 through March 4, 2026",
    "year-zero": "April 4, 0000 through May 4, 0000",
}


@pytest.mark.parametrize("shape", sorted(POISONED_LONG_PERIODS))
def test_period_from_long_dates_refuses_privately(shape):
    """The one raiser whose input is a whole markdown document rather than a
    cell. Before this cell, `date(int(sy), start_month, int(sd))` was the raise
    and Python 3.13+ echoes the offending number back —
    ``day 99 must be in range 1..30 for month 4 in year 2026`` — so the printed
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
    } | {dt._refusal_class("01/15/2026"), dt._refusal_class("")}
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
        dt.iso_from_month_day(CANARY, 2026)
    message = str(raised.value)
    assert message.startswith("date grammar refused a printed token")
    assert "reader=iso_from_month_day" in message
    assert "no digits in the cell" in message


def test_the_century_mode_refusal_names_the_legal_values_and_not_the_illegal_one():
    """An API misuse by our own caller, not a reading of a document — but it
    used to echo its argument, and `century` is a parameter a future caller
    could hand a document-derived string."""
    with pytest.raises(ValueError) as raised:
        dt.iso_from_month_day_year("1/15/26", century=CANARY)
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
                lambda: member(token, 2026),
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

    start, end = _date(2026, 1, 1), _date(2026, 12, 31)
    for token in ("99/99", "02/30", "13/01", "00/00"):
        assert dt.iso_within_period(token, start, end) is None


# ---------------------------------------------------------------------------
# CARRIED FINDING, pinned rather than fixed: `date()` raises OverflowError, and
# OverflowError is not a ValueError
# ---------------------------------------------------------------------------

def test_an_over_long_integer_reaches_date_as_an_overflow_error_not_a_refusal():
    """Found by this cell's own poisoned sweep, and DELIBERATELY NOT FIXED.

    `datetime.date(2026, 1, 4471009238)` raises `OverflowError: Python int too
    large to convert to C long`, and `OverflowError` is an `ArithmeticError`,
    not a `ValueError`. Every `except ValueError` in the date layer therefore
    lets it through - `iso_or_none`, `year_within_period`, `dates._with_year`,
    `dates.parse_date`, and this cell's own four new handlers.

    NOT a privacy defect: the message is a fixed sentence of CPython's with no
    document content in it, which is why this cell pins the behaviour instead
    of changing it. It IS a contract defect - three of those helpers are
    documented to return `None` rather than raise - and changing what they
    return is a behaviour change with an archive sweep of its own, which is the
    same judgement §MONEYPRIV MP3 made about `parse_digit_scrubbed`. Carried
    for whoever owns the date layer next.

    Pinned so a future fix has to come here and say so, and so the "one
    constructor" claim above is read with its real scope: every refusal the
    date grammar RAISES goes through `date_refusal`; an OverflowError is not
    one of the things it raises.
    """
    from datetime import date as _date

    huge = int(DIGITS)
    with pytest.raises(OverflowError) as raised:
        _date(2026, 1, huge)
    assert DIGITS not in str(raised.value)

    with pytest.raises(OverflowError):
        dt.iso_or_none(2026, 1, huge)
    with pytest.raises(OverflowError):
        dt.year_within_period(1, huge, _date(2026, 1, 1), _date(2026, 12, 31))
    with pytest.raises(OverflowError) as raised:
        dt.iso_from_month_day(f"1/{DIGITS}", 2026)
    assert DIGITS not in str(raised.value), (
        "the OverflowError itself must stay content-free; if CPython ever "
        "echoes the integer, this finding becomes a privacy defect"
    )


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
        td_can._native_date_to_iso(token, default_year=2026)
    assert_private(raised.value, token)


@pytest.mark.parametrize("site", sorted(PARSER_INVOCATIONS))
def test_a_parser_money_refusal_names_its_own_site(site):
    with pytest.raises(ValueError) as raised:
        PARSER_INVOCATIONS[site](CANARY)
    assert f"reader={site}" in str(raised.value)


def test_the_td_can_refusal_names_its_own_site():
    with pytest.raises(ValueError) as raised:
        td_can._native_date_to_iso(CANARY, default_year=2026)
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
    "analysis/bmo.py": frozenset({"money_refusal"}),
    "analysis/farmers_merchants.py": frozenset({"money_refusal"}),
    "analysis/td_can.py": frozenset({"date_refusal"}),
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
    `payload.error` and shows it in a `window.alert`, so these five are what an
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
#: in `analysis/revenue.py`. The last two are the pair the batch-6 census
#: missed: they live in `rebuild_serialized_revenue_views`, which
#: `apply_serialized_revenue_review` calls on its way out.
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
}


@pytest.mark.parametrize("declared", sorted(_REVIEW_REFUSAL_DRIVERS))
def test_every_declared_review_refusal_is_actually_raised(declared):
    """The coupling, in the direction that catches a REWORD. The allow-list is
    a copy of five literals from another module; if one of those raises is
    reworded the tuple stops matching it and the user silently loses the named
    reason. This drives each one out of `analysis/revenue.py` for real."""
    analysis, source_location, decision = _REVIEW_REFUSAL_DRIVERS[declared]
    with pytest.raises((ValueError, LookupError)) as raised:
        apply_serialized_revenue_review(
            analysis, source_location=source_location, decision=decision
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
    assert len(webapp_app._DECLARED_REVIEW_REFUSALS) == 5


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

    monkeypatch.setattr("webapp.worker.analyze_markdown", declined)
    job = job_store.create("ok.pdf")
    run_job(job.id, b"%PDF-ok", "ok.pdf", job_store, parse_mode="deterministic")
    fetched = job_store.get(job.id)
    assert fetched.status == "done"
    assert fetched.error is None
    assert fetched.analysis_error == "no deterministic parser matched this statement"


def test_the_non_terminal_vocabulary_matches_the_stores_own():
    """A frozenset of status strings is only correct while it matches the
    store's. `webapp/jobs.py` documents the five."""
    documented = (PROJECT_ROOT / "webapp" / "jobs.py").read_text(encoding="utf-8")
    assert '"queued" | "processing" | "done" | "error" | "interrupted"' in documented
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

def test_the_escalation_guard_tests_parse_mode_first():
    """§EXTRACTPRIV XP9 finding 2. The guard at the escalation call had four
    clauses and none of them was the MODE. `deterministic_stmt is None` is true
    on the structurer branch, so nothing in the condition stopped a
    deterministic-mode run from making a hosted-model call; the offline
    guarantee rested on the structurer only publishing statements that GROUND
    (so `recon.ok` is True and `needs_escalation` False), which is a property
    of the structurer and not of the mode.

    Asserted on the AST rather than by grep, so a reordering that drops the
    clause fails here."""
    tree = ast.parse(
        (PROJECT_ROOT / "analysis" / "pipeline.py").read_text(encoding="utf-8")
    )
    guards = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.BoolOp)
        and isinstance(node.test.op, ast.And)
        and "settings.escalation_model" in ast.unparse(node.test)
    ]
    assert len(guards) == 1, "the escalation guard moved or multiplied"
    clauses = [ast.unparse(value) for value in guards[0].test.values]
    assert clauses[0] == "parse_mode != 'deterministic'", clauses
    assert "deterministic_stmt is None" in clauses


def test_deterministic_mode_never_calls_the_extractor_even_with_the_structurer_on(
    monkeypatch,
):
    """The dynamic half. `extract_statement` is replaced by a recorder, so a
    call is a test failure rather than a vendor charge ($0 vendor, binding)."""
    from analysis import pipeline

    calls: list[str] = []

    def recorder(markdown, **kwargs):
        calls.append("called")
        raise AssertionError("deterministic mode reached the hosted model")

    monkeypatch.setattr(pipeline, "extract_statement", recorder)
    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "1")
    for markdown in (
        f"UNSUPPORTED BANK STATEMENT {CANARY}",
        f"--- Page 1 ---\n{CANARY} {DIGITS}\nBeginning Balance 1,000.00\n",
    ):
        with pytest.raises(RuntimeError):
            pipeline.analyze_markdown(markdown, parse_mode="deterministic")
    assert calls == []


def test_the_parse_mode_clause_is_what_stops_the_call_on_the_structurer_branch(
    monkeypatch,
):
    """The clause EXERCISED, not merely asserted on the AST.

    The test above cannot reach the escalation guard: an unclaimed document
    that the structurer declines raises at `pipeline.py`'s
    "no deterministic parser matched this statement" before the guard is
    evaluated. And the branch that DOES reach it cannot occur naturally,
    because the structurer only publishes a statement whose ledger GROUNDS, so
    `recon.ok` is True and `needs_escalation` is False (§EXTRACTPRIV XP9
    finding 2 measured that over four constructed variants).

    That coincidence is the whole finding, so this test removes it: the
    structurer is replaced by one that publishes a statement which does NOT
    reconcile, and the settings are given two different models. Every other
    clause of the guard is then satisfied. With the `parse_mode` clause the
    extractor is not called; without it — mutant M23 — the recorder fires and
    this fails. A hosted-model call in deterministic mode is a $0-vendor
    breach, so it is asserted rather than reasoned about.
    """
    from analysis import pipeline
    from analysis.config import Settings
    from analysis.schema import Statement, Transaction

    calls: list[str] = []

    def recorder(markdown, **kwargs):
        calls.append("called")
        raise AssertionError("deterministic mode reached the hosted model")

    def ungrounded(markdown, **kwargs):
        """A statement the structurer 'published' whose summary cannot close:
        the printed totals disagree with the one row, so `reconcile` fails and
        `needs_escalation` is True."""
        return Statement(
            bank=None,
            account_name=None,
            account_number=None,
            period_start="2026-01-01",
            period_end="2026-01-31",
            days_in_period=31,
            beginning_balance=1000.00,
            ending_balance=9999.00,
            stated_total_credits=5000.00,
            stated_total_debits=250.00,
            transactions=[Transaction(
                date="2026-01-05",
                description="A POSTING",
                amount=100.00,
                direction="credit",
                running_balance=1100.00,
            )],
        )

    monkeypatch.setattr(pipeline, "extract_statement", recorder)
    monkeypatch.setattr(pipeline, "structure_unclaimed", ungrounded)
    monkeypatch.setenv("GENERIC_STRUCTURER_ENABLED", "1")
    settings = Settings(
        api_key="",
        model="model-a",
        escalation_model="model-b",          # != model, so that clause passes
    )

    report = pipeline.analyze_markdown(
        f"UNSUPPORTED BANK STATEMENT {CANARY} {DIGITS}",
        parse_mode="deterministic",
        settings=settings,
    )

    assert calls == [], "deterministic mode made a hosted-model call"
    assert report.reconciliation.ok is False, (
        "the fixture must NOT reconcile, or the guard's other clauses would "
        "have stopped the call and this test would prove nothing"
    )
    assert settings.escalation_model != settings.model


# ---------------------------------------------------------------------------
# 9. `ocr/availability.py` — the invariant its docstring has always claimed
# ---------------------------------------------------------------------------

from ocr.availability import MAX_DETAIL_CHARS, probe_visual_ocr            # noqa: E402


def test_the_probe_detail_is_bounded():
    """`MAX_DETAIL_CHARS` as a measurement rather than a magic 200. An
    OpenAI-compatible client can raise with a whole HTML error page attached,
    and a preflight that floods a terminal is a preflight nobody reads."""
    def boom():
        raise RuntimeError("x" * 10_000)

    status = probe_visual_ocr(list_models=boom)
    assert status.available is False
    assert len(status.detail) == MAX_DETAIL_CHARS
    assert status.error_type == "RuntimeError"


def test_no_document_can_reach_the_probe():
    """The census claim, as a signature assertion: `probe_visual_ocr` takes
    settings, a timeout and an injected lister. There is no parameter that
    could be a page, a PDF, a markdown string or a cell - which is why this
    cell did NOT reduce `detail`, and why the reasoning has to be checkable
    rather than asserted in a log."""
    import inspect

    assert set(inspect.signature(probe_visual_ocr).parameters) == {
        "settings", "timeout", "list_models",
    }


#: Every production `.detail` attribute read in the tree, and WHY each one is
#: allowed. The receiver's NAME is deliberately not part of the rule: the first
#: version of this guard matched `self`/`status` only, and the adversarial
#: review walked straight past it with
#: `def telemetry_detail(probe): return probe.detail` (review MINOR-1). A rule
#: keyed on what someone called their variable is not a rule.
ALLOWED_DETAIL_READERS = {
    "ocr/availability.py":
        "VisualOcrStatus.message() - THE reader, and it renders to a console",
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
    """The three ways to read `detail` WITHOUT writing `.detail`.

    `getattr(obj, "detail")` names the field as a string; `asdict(status)` and
    `vars(status)` / `status.__dict__` take the whole dataclass, `detail`
    included, and hand it to whatever wanted a dict - a telemetry record, a
    JSON body, a CSV row. The attribute walk cannot see any of them.

    The dataclass-wide clauses are scoped to modules that actually hold a
    `VisualOcrStatus`, which `test_only_the_availability_module_names_the_status_class_in_production`
    pins at one. Elsewhere `asdict` is the serialization layer's ordinary idiom
    over unrelated dataclasses, and flagging those would be noise, not a guard.
    """
    findings: list[str] = []
    for relative, tree in (modules if modules is not None else _repository_modules()):
        names_status = any(
            isinstance(node, ast.Name) and node.id == "VisualOcrStatus"
            for node in ast.walk(tree)
        )
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
            if not names_status:
                continue
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"asdict", "vars"}
            ):
                findings.append(f"{relative}:{node.lineno}: {node.func.id}(...)")
            if isinstance(node, ast.Attribute) and node.attr == "__dict__":
                findings.append(f"{relative}:{node.lineno}: __dict__")
    return findings


def test_the_probe_detail_has_exactly_one_reader_and_it_is_a_console():
    """The invariant `ocr/availability.py`'s module docstring has claimed since
    Wave 3 - "kept for the operator console only and never travels into
    telemetry (H-3 sensitivity invariant)" - asserted for the first time.

    Four clauses, and clause 1 is the one the review widened. `detail` is read
    only in the files `ALLOWED_DETAIL_READERS` names, by ANY receiver;
    `message()` is called only from `discovery/cli.py`; both of those calls sit
    inside a `print(..., file=sys.stderr)`; and nothing in production reaches
    the field the other three ways.

    Asserted by FILE and COUNT, never by line number: a guard that pins
    `discovery/cli.py:208` turns red the moment an unrelated cell adds a line
    above it, and a composed train of ten branches is where that happens. The
    line numbers stay in the failure message, where they help.
    """
    detail_sites = _detail_attribute_sites()
    files = sorted({site.rsplit(":", 1)[0] for site in detail_sites})
    assert files == sorted(ALLOWED_DETAIL_READERS), detail_sites
    assert sum(s.startswith("ocr/availability.py") for s in detail_sites) == 1, detail_sites

    message_sites = [
        f"{relative}:{node.lineno}"
        for relative, tree in _repository_modules()
        if relative != "ocr/availability.py"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "message"
    ]
    assert sorted({s.rsplit(":", 1)[0] for s in message_sites}) == [
        "discovery/cli.py"
    ], message_sites
    assert len(message_sites) == 2, message_sites

    printed = 0
    tree = ast.parse((PROJECT_ROOT / "discovery" / "cli.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "print":
            continue
        if not any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == "message"
            for argument in node.args
            for inner in ast.walk(argument)
        ):
            continue
        keywords = {kw.arg: ast.unparse(kw.value) for kw in node.keywords}
        assert keywords.get("file") == "sys.stderr", keywords
        printed += 1
    assert printed == 2

    assert _indirect_detail_reads() == [], _indirect_detail_reads()


def test_only_the_availability_module_names_the_status_class_in_production():
    """The scope clause `_indirect_detail_reads` rests on. If a second
    production module ever holds a `VisualOcrStatus`, the `asdict`/`vars`
    clause has to widen with it, and this is what says so."""
    holders = sorted({
        relative
        for relative, tree in _repository_modules()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "VisualOcrStatus"
    })
    assert holders == ["ocr/availability.py"], holders


#: The reviewer's bypass, verbatim, plus the three indirect reads. Each must be
#: FOUND; the three clean shapes must not be.
_DETAIL_MUTANTS = [
    ("reviewer-bypass-any-receiver",
     "def telemetry_detail(probe):\n    return probe.detail\n", 1, 0),
    ("bare-name-receiver",
     "def f(x):\n    return x.detail\n", 1, 0),
    ("getattr-by-string",
     "def f(x):\n    return getattr(x, 'detail')\n", 0, 1),
    ("asdict-the-whole-status",
     "from dataclasses import asdict\n"
     "def f(status: VisualOcrStatus):\n    return asdict(status)\n", 0, 1),
    ("vars-the-whole-status",
     "def f(status: VisualOcrStatus):\n    return vars(status)\n", 0, 1),
    ("dunder-dict",
     "def f(status: VisualOcrStatus):\n    return status.__dict__\n", 0, 1),
    ("clean-class-name-only",
     "def f(status: VisualOcrStatus):\n    return type(status).__name__\n", 0, 0),
    ("clean-unrelated-asdict",
     "from dataclasses import asdict\ndef f(report):\n    return asdict(report)\n", 0, 0),
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
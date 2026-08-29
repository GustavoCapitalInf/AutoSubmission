"""RAISE-PRIVACY-4 (batch 9): the eight `date()` sites #HYGIENE8 carried.

W3 §H14.3 ran an implicit-conversion census over the nine `CHAIN_GUARDED`
modules, found 74 unguarded conversions of a document token, proved 66 of them
unable to reach an exception message — and measured EIGHT that could. All eight
stood in three readers that closure did not own (`bmo`, `farmers_merchants`,
`td_can`), all eight were driven in that session, and all eight echoed a number
the document supplied. They were DISCLOSED in `_CARRIED_ECHOING_SITES` and
carded here rather than rerouted on a closure commit.

THE LAW, unchanged since §MONEYPRIV: what this tree RAISES must not quote the
printed cell. It is a law about the raise and carries no clause about who
catches it — `parser_registry._guarded` reduces a parser crash to its class
name and `webapp/worker.py:_stage_failure` withholds every message, so the
surviving sinks are the CSV writers (`batch.py`, `coverage_audit.py`,
`deterministic_coverage_audit.py`, each `f"{type(e).__name__}: {e}"` into a
cell) and any direct caller. A grammar that never puts the cell in a message is
safe in front of a boundary nobody has written yet.

WHAT THIS FILE PROVES, and it is deliberately BOTH trees. A "0 leaking cells"
measured only on the branch measures nothing: it passes just as well when the
fixture never reached the site. So every cell runs twice — once against
`analysis/` as it stood at the base commit, materialised by
`tools.hygiene8_base_tree`, where it must ECHO, and once against this tree,
where it must refuse without quoting on `str`, `repr`, `args`, `__notes__`, the
chain and a rendered traceback.

THE NINTH LINE. The card listed nine candidate lines and §H14 measured eight
echoing sites. The difference is `bmo.py`'s transaction-row `date()`, which
stands inside `except ValueError: continue`: it cannot echo, because nothing it
raises escapes. It is NOT rerouted — a site that raises nothing has no refusal
to make private, and changing it would move behaviour this card is not allowed
to move — and it is measured here so the reconciliation is a number rather than
an argument.
"""
from __future__ import annotations

import importlib

import pytest

from analysis import date_tokens as dt
from tests.test_privacy3_boundaries import (
    CANARY, PROJECT_ROOT, _digit_runs, _leak_surfaces,
)

#: The base this card branched from. The both-tree drive is only a proof if the
#: base is the tree the card was written against.
BASE_REVISION = "2f24b06"


# ---------------------------------------------------------------------------
# The fixtures — invented, never transcribed
# ---------------------------------------------------------------------------
# Every date is 2031 and every figure is RENDERED from whole units at build
# time, so this file carries no amount-shaped literal and no date that could be
# mistaken for an archive token. The account digits are a repeated pattern.
# Nothing here has been inside a document; each fixture is built from the
# reader's OWN committed detection markers and column headers.

_UNITS = {
    "opening": 1000, "credits": 500, "debits": 400, "interest": 0,
    "fees": 10, "closing": 1090, "average": 950, "collected": 900,
    "row_one": 10, "row_two": 20, "balance_one": 990, "balance_two": 1010,
}


def _figure(name: str) -> str:
    return f"{_UNITS[name]:,.2f}"


def _whole(name: str) -> str:
    return f"{_UNITS[name]:,}"


#: BMO's own two detection markers ("BMO", "ACCOUNT SUMMARY TOTALS"), the two
#: section words `parse_bmo_statement` requires, the summary strip its own
#: regex reads, and two rows in the grid `_ROW_RE` matches. The period line is
#: the poisoned cell.
BMO_FIXTURE = f"""\
BMO Bank of Montreal
Account Number: {'0' * 7}
Currency: CAD
Statement Period: {{token}}
Account Summary
Opening Balance $ {_figure('opening')} Total Deposits $ {_figure('credits')} \
Total Withdrawals $ {_figure('debits')} Interest Earned $ {_figure('interest')} \
Fees and Charges $ {_figure('fees')} Closing Balance $ {_figure('closing')}
Transaction Details Date Description Withdrawal Deposit Balance
04/10 INVENTED DESCRIPTION ONE $ {_figure('row_one')} $ {_figure('balance_one')}
04/11 INVENTED DESCRIPTION TWO $ {_figure('row_two')} $ {_figure('balance_two')}
Account Summary Totals
"""

#: The one summary strip `farmers_merchants._parse_summary` reads, in the order
#: its own regex requires. The two `Statement Dates` cells are the poisoned
#: ones; everything else is furniture the pattern needs in order to match at
#: all, which is the point of driving the real reader.
FM_FIXTURE = f"""\
Account Number {'0' * 6} Statement Dates {{start}} thru {{end}} \
Previous Balance {_figure('opening')} \
Days in the statement period 30 \
5 Deposits/Credits {_figure('credits')} \
Average Ledger {_whole('average')} \
4 Checks/Debits {_figure('debits')} \
Average Collected {_whole('collected')} \
Service Charge {_figure('fees')} \
Interest Paid .00 \
Ending Balance {_figure('closing')}
"""

#: The year `_date_tokens` and `_native_date_to_iso` take as a PARAMETER. In
#: production it is always `int(stmt.period_end[:4])` — a year this tree
#: produced — which is why the overflow drive below has to pass one by hand.
_DEFAULT_YEAR = 2031

#: A year past the C `int` `date()` parses its arguments into. `date()` raises
#: `OverflowError` rather than `ValueError` on it, which is the contract
#: #HYGIENE8 closed in `iso_or_none` (`c455de7`, MINOR-4).
_HUGE_YEAR = 10 ** 12


def raisepriv4_drives(package: str) -> dict:
    """The eight sites, driven through the REAL reader, inside one package.

    Parameterised by package name for the same reason `major2_drives` is: the
    identical drive has to run against the base tree and against this one, in
    one interpreter, or the comparison is between two environments rather than
    between two trees.
    """
    bmo = importlib.import_module(f"{package}.bmo")
    fm = importlib.import_module(f"{package}.farmers_merchants")
    td = importlib.import_module(f"{package}.td_can")
    schema = importlib.import_module(f"{package}.schema")

    #: The two period cells of the FM strip, one poisoned at a time: a cell
    #: that refused BOTH would not say which site refused.
    _FM_VALID = "01/10/31"

    def bmo_statement_period(token: str):
        return bmo.parse_bmo_statement(BMO_FIXTURE.format(token=token))

    def fm_period_start(token: str):
        statement = schema.Statement(bank="INVENTED")
        fm._parse_summary(FM_FIXTURE.format(start=token, end=_FM_VALID), statement)
        return statement

    def fm_period_end(token: str):
        statement = schema.Statement(bank="INVENTED")
        fm._parse_summary(FM_FIXTURE.format(start=_FM_VALID, end=token), statement)
        return statement

    def td_period_start(token: str):
        return td._parse_period(f"{token} - MAR 28/31")

    def td_period_end(token: str):
        return td._parse_period(f"JAN 10/31 - {token}")

    def td_date_tokens(token: str):
        return td._date_tokens(token, default_year=_DEFAULT_YEAR)

    def td_native_date(token: str):
        return td._native_date_to_iso(token, default_year=_DEFAULT_YEAR)

    return {
        "bmo.statement_period": bmo_statement_period,
        "farmers_merchants.period_start": fm_period_start,
        "farmers_merchants.period_end": fm_period_end,
        "td_can.period_start": td_period_start,
        "td_can.period_end": td_period_end,
        "td_can.date_tokens": td_date_tokens,
        "td_can.native_date": td_native_date,
    }


#: THE POISON, one shape per way each site's own pattern admits a non-date, and
#: the NUMBER the base tree echoes for it. The number is DERIVED here rather
#: than typed twice: it is the component CPython names in its own message, and
#: writing it beside the token is how the base assertion stays honest when the
#: token changes.
#:
#: `bmo.statement_period` has exactly ONE failing shape and that is a property
#: of the site, not a gap in the table: its month comes from an index into
#: `calendar.month_name` (a non-month returns None rather than raising) and its
#: day is `1` or a `monthrange` result, so the only cell that can reach a
#: refusal is a printed year of `0000`.
POISON = {
    "bmo.statement_period": {
        "year-zero": ("April 0000", "0"),
    },
    "farmers_merchants.period_start": {
        "month-out-of-range": ("13/40/31", "13"),
        "day-30-in-february": ("02/30/31", "30"),
        "day-31-where-30-is-the-last": ("04/31/31", "31"),
    },
    "farmers_merchants.period_end": {
        "month-out-of-range": ("13/40/31", "13"),
        "day-30-in-february": ("02/30/31", "30"),
        "day-31-where-30-is-the-last": ("04/31/31", "31"),
    },
    "td_can.period_start": {
        "day-30-in-february": ("FEB 30/31", "30"),
        "day-31-where-30-is-the-last": ("APR 31/31", "31"),
        "day-zero": ("JAN 0/31", "0"),
    },
    "td_can.period_end": {
        "day-30-in-february": ("FEB 30/31", "30"),
        "day-31-where-30-is-the-last": ("APR 31/31", "31"),
        "day-zero": ("JAN 0/31", "0"),
    },
    "td_can.date_tokens": {
        "day-30-in-february": ("FEB 30", "30"),
        "day-31-where-30-is-the-last": ("APR 31", "31"),
        "day-zero": ("JAN 0", "0"),
    },
    "td_can.native_date": {
        "day-30-in-february": ("FEB30", "30"),
        "day-31-where-30-is-the-last": ("APR31", "31"),
        "day-zero": ("JAN0", "0"),
    },
}

#: The reader name each refusal must carry, so a drive cannot be satisfied by
#: SOME other refusal raised earlier in the same reader. Both `td_can`
#: `native_date` refusals name the same site on purpose: a caller cannot tell
#: the shape refusal from the calendar refusal, which is the property.
READERS = {
    "bmo.statement_period": "bmo._statement_period",
    "farmers_merchants.period_start": "farmers_merchants._parse_summary",
    "farmers_merchants.period_end": "farmers_merchants._parse_summary",
    "td_can.period_start": "td_can._parse_period",
    "td_can.period_end": "td_can._parse_period",
    "td_can.date_tokens": "td_can._date_tokens",
    "td_can.native_date": "td_can._native_date_to_iso",
}

#: The (site, shape) CELLS, flattened, so the parametrisation is exactly the
#: NINETEEN drives that exist rather than a cross-product with holes in it.
#: (Review MINOR-1: this comment said "sixteen", which is a number no reading
#: of `POISON` produces — a reader who trusted it believed three drives did
#: not exist. The count is asserted below rather than only written down, so
#: the next reword cannot drift the same way.)
CELLS = [
    (site, shape)
    for site in sorted(POISON)
    for shape in sorted(POISON[site])
]


def test_the_drive_count_this_file_states_is_the_count_it_runs():
    """MINOR-1 closed as a class rather than as a typo. `CELLS` is the
    parametrisation of the two branch drives and of the base drive, so a
    number written beside it is a claim about coverage."""
    assert len(CELLS) == 19
    assert len(CELLS) == sum(len(shapes) for shapes in POISON.values())
    assert sorted(POISON) == sorted(READERS) == sorted(VALID)

#: A cell every site CAN read. A refusal that also refused the good case would
#: be a regression wearing a fix's clothes, and the payload comparison below is
#: the other half of "only the message changed".
VALID = {
    "bmo.statement_period": "April 2031",
    "farmers_merchants.period_start": "01/10/31",
    "farmers_merchants.period_end": "02/10/31",
    "td_can.period_start": "JAN 10/31",
    "td_can.period_end": "FEB 10/31",
    "td_can.date_tokens": "JAN 10",
    "td_can.native_date": "JAN10",
}


# ---------------------------------------------------------------------------
# The surfaces
# ---------------------------------------------------------------------------

def _surfaces(exc: BaseException) -> dict:
    """`_leak_surfaces` plus `__notes__`.

    `__notes__` is a list `traceback` renders under the message and nothing in
    `_leak_surfaces` reads. Nothing in this tree calls `add_note` today, which
    is exactly why it is asserted: the surface a future `add_note` would use is
    checked before anyone writes one.
    """
    surfaces = dict(_leak_surfaces(exc))
    surfaces["notes"] = repr(getattr(exc, "__notes__", []))
    return surfaces


def _leaking(exc: BaseException, token: str) -> list:
    """Which surfaces leaked, at a TWO-digit run floor.

    The poison sweep's rule, imported rather than restated, except that the
    floor is two: a printed month or day IS a two-digit run, so a three-digit
    floor cannot see `month must be in 1..12, not 13` at all. Narrowing the
    floor can only make this stricter.
    """
    from tools.hygiene8_poison_sweep import _leaking_surfaces

    leaking = _leaking_surfaces(exc, token, CANARY, set(_digit_runs(token, 2)))
    if "notes" not in leaking and getattr(exc, "__notes__", []):
        text = repr(exc.__notes__)
        if token in text or any(run in text for run in _digit_runs(token, 2)):
            leaking.append("notes")
    return leaking


def _payload(result):
    """A comparable payload, so a base object is never compared with ours."""
    if result is None or isinstance(result, (str, int, float, bool)):
        return result
    if isinstance(result, (list, tuple)):
        return [_payload(item) for item in result]
    return result.model_dump()


@pytest.fixture(scope="module")
def base_tree(tmp_path_factory):
    """`analysis/` as it stood at the base commit, importable beside ours."""
    try:
        from tools.hygiene8_base_tree import load_base_analysis
    except ImportError as exc:                        # pragma: no cover
        pytest.skip(f"tools.hygiene8_base_tree is not importable: {exc!r}")
    try:
        return load_base_analysis(
            BASE_REVISION,
            repo=PROJECT_ROOT,
            scratch=tmp_path_factory.mktemp("raisepriv4_base"),
        )
    except Exception as exc:                          # pragma: no cover
        pytest.skip(f"the base tree {BASE_REVISION} is unavailable: {exc!r}")


# ---------------------------------------------------------------------------
# 1. The eight sites at the BASE tree — they echo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("site,shape", CELLS)
def test_the_eight_sites_echoed_the_printed_number_at_the_base_tree(
    site, shape, base_tree
):
    """The vacuity check for the fix below, and W3 §H14.3's measurement
    reproduced: without it every branch assertion could pass because the
    fixture never reached `date()` at all."""
    token, echoed = POISON[site][shape]
    with pytest.raises(ValueError) as raised:
        raisepriv4_drives(base_tree.package)[site](token)
    message = str(raised.value)
    assert "date grammar refused" not in message, (
        "the base tree is not supposed to carry the refusal; check the revision"
    )
    assert echoed in message, (
        f"{site}/{shape}: the base tree did not echo the printed number, so "
        f"the fixture probably never reached the site"
    )


# ---------------------------------------------------------------------------
# 2. The eight sites at THIS tree — they refuse, and quote nothing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("site,shape", CELLS)
def test_the_eight_sites_refuse_without_quoting_at_the_branch(site, shape):
    """RAISE-PRIVACY-4, closed. Same drive, same fixture, this tree: the
    document still refuses with the same class, and no digit of the printed
    token reaches `str`, `repr`, `args`, `__notes__`, the chain or a rendered
    traceback."""
    token, _ = POISON[site][shape]
    with pytest.raises(ValueError) as raised:
        raisepriv4_drives("analysis")[site](token)
    assert _leaking(raised.value, token) == []
    assert f"reader={READERS[site]}" in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__context__ is None


#: The one digit sequence a `date_refusal` may carry, and it is a constant of
#: THIS tree rather than anything a document printed: `_refusal_class` answers
#: "longer than the N-character bound" for a token past `MAX_DATE_TOKEN_CHARS`.
#: Review MINOR-3: the assertion below used to say "no decimal digit at all",
#: which is stronger than the refusal guarantees — it passed only because no
#: driven cell was long enough, and the day one was, it would have failed on a
#: message that is perfectly private. What the refusal DOES guarantee is
#: asserted instead, and the over-long branch is driven below rather than left
#: as an exemption nobody exercises.
_ALLOWED_CONSTANT_DIGITS = str(dt.MAX_DATE_TOKEN_CHARS)


def _document_digits(text: str) -> str:
    """`text` with this tree's own constant removed, so what is left is
    everything the message could only have got from the document."""
    return text.replace(_ALLOWED_CONSTANT_DIGITS, "")


@pytest.mark.parametrize("site,shape", CELLS)
def test_the_refusal_carries_no_digit_the_document_supplied(site, shape):
    """Stronger than the run floor, and version-proof.

    The digit-run test cannot see a one-digit echo: `year must be in 1..9999,
    not 0` quotes a printed `0000` as `0`, and CPython's wording has already
    changed once (3.13 rewrote every `date()` range message). So the assertion
    is made directly on the characters — over a message with this tree's own
    `MAX_DATE_TOKEN_CHARS` removed, which is the only digit sequence
    `_refusal_class` can produce and is not a reading of anything. The
    rendered traceback is excluded here and covered by the run test above: it
    quotes line numbers and source, which are digits that are not the
    document's.
    """
    token, _ = POISON[site][shape]
    with pytest.raises(ValueError) as raised:
        raisepriv4_drives("analysis")[site](token)
    for surface in ("str", "repr", "args", "chain", "notes"):
        text = _document_digits(_surfaces(raised.value)[surface])
        assert not any(char.isdigit() for char in text), (
            f"{site}/{shape}: a digit reached {surface}"
        )


#: A period line whose `\s*` run pushes `m.group(0)` past the bound, so the
#: refusal takes the ONE branch of `_refusal_class` that interpolates. The
#: reviewer's own shape, driven rather than described.
_OVER_LONG_PERIOD = "FEB" + " " * 40 + "30/31 - MAR 28/31"


def test_the_over_long_branch_carries_the_bound_and_still_carries_no_document():
    """MINOR-3's concrete case, promoted from a caveat to a drive.

    `td_can._parse_period` passes `m.group(0)` and `_PERIOD_RE`'s `\\s*` runs
    are unbounded, so a real period line can exceed `MAX_DATE_TOKEN_CHARS`.
    The message then carries the CONSTANT — and nothing else: not the printed
    day, not the month word, not the token. That is exactly the guarantee
    `_refusal_class` makes, so it is what is asserted."""
    from analysis import td_can

    with pytest.raises(ValueError) as raised:
        td_can._parse_period(_OVER_LONG_PERIOD)
    message = str(raised.value)
    assert f"longer than the {dt.MAX_DATE_TOKEN_CHARS}-character bound" in message
    assert "reader=td_can._parse_period" in message
    assert _leaking(raised.value, _OVER_LONG_PERIOD.strip()) == []
    # And the exemption is exactly one constant wide: with it removed, the
    # message has no digit left.
    for surface in ("str", "repr", "args", "chain", "notes"):
        text = _document_digits(_surfaces(raised.value)[surface])
        assert not any(char.isdigit() for char in text), surface


def test_the_refusal_class_vocabulary_is_what_the_digit_claim_is_made_against():
    """The exemption above is a claim about `_refusal_class`, so it is pinned
    there: four fixed strings, exactly one of which interpolates, and the
    thing it interpolates is a module constant."""
    produced = {
        dt._refusal_class(token)
        # The over-long token must carry a DIGIT: `_refusal_class` answers
        # "no digits in the cell" first, so a long alphabetic token never
        # reaches the length branch at all.
        for token in ("", "   ", CANARY, "13/40/31", "1" * 40)
    }
    assert produced == {
        "the cell is empty",
        "no digits in the cell",
        f"longer than the {dt.MAX_DATE_TOKEN_CHARS}-character bound",
        "not a date in the reader's format",
    }
    interpolating = [text for text in produced if any(c.isdigit() for c in text)]
    assert interpolating == [
        f"longer than the {dt.MAX_DATE_TOKEN_CHARS}-character bound"
    ]
    assert _ALLOWED_CONSTANT_DIGITS == str(dt.MAX_DATE_TOKEN_CHARS)
    # An exemption is only safe while it cannot blind the drive it exempts: no
    # driven token contains the constant, so removing it from a message can
    # never remove a real echo.
    assert not any(
        _ALLOWED_CONSTANT_DIGITS in token
        for shapes in POISON.values()
        for token, _ in shapes.values()
    ), "a driven token contains the constant; the exemption would hide an echo"


def test_the_refusal_class_at_the_eight_sites_is_still_ValueError():
    """The dispatch seam reduces a parser crash to `type(exc).__name__`, so a
    changed CLASS would move an outcome even though no figure moved. Asserted
    at the drive rather than at the constructor, because it is the class that
    ESCAPES the reader that the seam sees."""
    for site, shapes in POISON.items():
        for token, _ in shapes.values():
            with pytest.raises(ValueError):
                raisepriv4_drives("analysis")[site](token)


# ---------------------------------------------------------------------------
# 3. The other half of "only the message changed"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("site", sorted(VALID))
def test_every_site_reads_an_in_range_cell_identically_on_both_trees(
    site, base_tree
):
    """An in-range cell produces the same payload leaf for leaf on both trees,
    so nothing this card touched changed what any document PUBLISHES."""
    from tools.hygiene8_base_tree import leaf_diff

    token = VALID[site]
    ours = _payload(raisepriv4_drives("analysis")[site](token))
    theirs = _payload(raisepriv4_drives(base_tree.package)[site](token))
    assert leaf_diff(theirs, ours) == []
    # Truthy rather than `is not None`: an empty list is what a site that
    # silently stopped reading returns, and `leaf_diff([], []) == []` would
    # call that agreement.
    assert ours, f"{site}: the valid drive published nothing"


# ---------------------------------------------------------------------------
# 4. The shapes that never reach `date()` — no new refusal, no new acceptance
# ---------------------------------------------------------------------------
# The card asks for junk and for SUPERSCRIPT digits, and the honest answer for
# these readers is that neither reaches the sites at all: `re`'s `\d` matches
# Unicode category Nd, and a superscript is No, so `\d{1,2}` never matches one.
# What has to be proved is therefore not privacy but INVARIANCE — the reroute
# gave none of these shapes a new refusal and none of them a new acceptance —
# with privacy asserted on top wherever the shape does raise.

#: `str.isdigit()` is True for these and `int()` rejects them; `date_tokens`
#: uses `isdecimal` throughout for exactly that reason.
_SUPERSCRIPTS = "²³¹"

NON_REACHING = {
    "junk": CANARY,
    "superscript-day": f"FEB{_SUPERSCRIPTS[:2]}",
    "superscript-only": _SUPERSCRIPTS,
    "empty": "",
    "spaces": "   ",
}


@pytest.mark.parametrize("shape", sorted(NON_REACHING))
@pytest.mark.parametrize("site", sorted(POISON))
def test_a_shape_that_never_reaches_date_behaves_identically_on_both_trees(
    site, shape, base_tree
):
    """No new refusal where none existed, and no new acceptance."""
    from tools.hygiene8_base_tree import leaf_diff

    token = NON_REACHING[shape]

    def outcome(package):
        try:
            return "returned", _payload(raisepriv4_drives(package)[site](token))
        except BaseException as exc:                  # noqa: BLE001
            return f"raised {type(exc).__name__}", exc

    base_kind, base_value = outcome(base_tree.package)
    our_kind, our_value = outcome("analysis")
    assert base_kind == our_kind, f"{site}/{shape}: the outcome CLASS moved"
    if base_kind == "returned":
        assert leaf_diff(base_value, our_value) == []
    else:
        for exc in (base_value, our_value):
            assert _leaking(exc, token) == [], (
                f"{site}/{shape}: {exc!r} quotes the token"
            )


# ---------------------------------------------------------------------------
# 5. The `OverflowError` contract — the one behaviour that moves, named
# ---------------------------------------------------------------------------

#: The two sites that take a year as a PARAMETER rather than reading one. They
#: are the only place a year big enough to overflow `date()`'s C `int` can
#: arrive, and it cannot arrive from a document: `_parse_period` builds
#: `2000 + int(\d{2})` and every caller of these two passes
#: `int(stmt.period_end[:4])`, a year this tree itself produced.
_OVERFLOW_SITES = ("td_can.date_tokens", "td_can.native_date")


def _overflow_drive(package: str, site: str):
    td = importlib.import_module(f"{package}.td_can")
    token = VALID[site]
    if site == "td_can.date_tokens":
        return lambda: td._date_tokens(token, default_year=_HUGE_YEAR)
    return lambda: td._native_date_to_iso(token, default_year=_HUGE_YEAR)


@pytest.mark.parametrize("site", _OVERFLOW_SITES)
def test_a_huge_year_escaped_as_an_OverflowError_at_the_base_tree(site, base_tree):
    """The measurement, so the change below is a recorded one rather than a
    silent one. `OverflowError` is an `ArithmeticError`, not a `ValueError`."""
    with pytest.raises(OverflowError):
        _overflow_drive(base_tree.package, site)()


@pytest.mark.parametrize("site", _OVERFLOW_SITES)
def test_a_huge_year_now_refuses_through_the_one_constructor(site):
    """#HYGIENE8's contract (`c455de7`, review MINOR-4), applied to the two
    sites this card rerouted: a conversion guard catches BOTH, so a reader does
    not have to work out which arithmetic a particular `date()` can overflow
    on. The class moves `OverflowError` -> `ValueError`, which is a real change
    and is why it is measured on both trees — and it is unreachable from any
    document, because no caller of either site passes a year this tree did not
    produce."""
    with pytest.raises(ValueError) as raised:
        _overflow_drive("analysis", site)()
    assert f"reader={READERS[site]}" in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__context__ is None


def test_no_caller_of_the_two_year_taking_sites_passes_a_year_from_a_document():
    """The unreachability above, as a structural assertion rather than a
    claim. Every `default_year=` keyword in the reader is either the loop
    variable the grouper carries or `int(stmt.period_end[:4])`, and
    `period_end` is an ISO string this tree wrote."""
    import ast

    source = (PROJECT_ROOT / "analysis" / "td_can.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    passed = sorted({
        ast.unparse(keyword.value)
        for node in ast.walk(tree) if isinstance(node, ast.Call)
        for keyword in node.keywords if keyword.arg == "default_year"
    })
    assert passed == ["default_year", "year"], passed
    assigned = sorted({
        ast.unparse(node.value)
        for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "default_year"
    })
    assert assigned == ["None", "int(stmt.period_end[:4])"], assigned


# ---------------------------------------------------------------------------
# 6. The ninth line — the reconciliation with §H14's count of eight
# ---------------------------------------------------------------------------

#: A BMO grid whose first row prints a month and day no calendar holds. It
#: matches `_ROW_RE` exactly — two digit runs, a description, two figures — so
#: it reaches the transaction-row `date()`; the second row is readable, so the
#: document still publishes and the skip is visible as an absence rather than
#: as a decline.
BMO_ROW_FIXTURE = BMO_FIXTURE.replace(
    "04/10 INVENTED DESCRIPTION ONE", "13/40 INVENTED DESCRIPTION ONE"
).format(token="April 2031")


def test_the_ninth_line_raises_nothing_and_skips_the_row_it_cannot_read():
    """`bmo.py`'s transaction-row `date()` is the card's ninth candidate line
    and §H14's census reported eight. This is the difference, measured: the
    call stands inside `except ValueError: continue`, so an impossible month
    and day cost the ROW and nothing escapes the reader. There is no refusal
    here to make private, and giving it one would be a new refusal — which this
    card is not allowed to introduce.
    """
    from analysis import bmo

    statement = bmo.parse_bmo_statement(BMO_ROW_FIXTURE)
    assert statement is not None, "the fixture did not reach the ledger at all"
    assert len(statement.transactions) == 1, (
        "the unreadable row was not skipped, or the readable one was"
    )


def test_the_ninth_lines_year_cannot_overflow_because_the_period_bounds_it():
    """The other half of "it cannot echo": `except ValueError` does not catch
    `OverflowError`, so the guard would be incomplete if a huge year could
    reach the line. It cannot — `resolve_year` returns one of the printed
    period's own years, and the period comes from `(\\d{4})`."""
    import ast

    from analysis import bmo, dates

    period = bmo._statement_period("Statement Period: April 2031")
    assert period is not None
    start, end = period
    for month, day in ((13, 40), (2, 30), (1, 1)):
        year = dates.resolve_year(month, day, start, end)
        assert year is None or year in {start.year, end.year}

    source = (PROJECT_ROOT / "analysis" / "bmo.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guarded = [
        ast.unparse(node)
        for parent in ast.walk(tree) if isinstance(parent, ast.Try)
        if any(
            handler.type is not None and ast.unparse(handler.type) == "ValueError"
            for handler in parent.handlers
        )
        for statement in parent.body
        for node in ast.walk(statement)
        if isinstance(node, ast.Call) and ast.unparse(node).startswith("date(")
    ]
    assert guarded == ["date(year, month, day)"], guarded


# ---------------------------------------------------------------------------
# 7. The eight sites are gone from the census, and the census says so
# ---------------------------------------------------------------------------

def test_the_eight_carried_sites_are_absent_from_the_conversion_census():
    """Stated as its own assertion rather than left implicit in
    `test_no_unguarded_conversion_of_a_document_token_is_unaccounted_for`'s set
    difference, because this is the sentence W3 §H14.3 carded."""
    from tests.test_privacy3_boundaries import CHAIN_GUARDED
    from tests.test_raise_privacy3 import implicit_conversion_census

    census = implicit_conversion_census(sorted(CHAIN_GUARDED))
    for closed in (
        "analysis/bmo.py:_statement_period: date(",
        "analysis/farmers_merchants.py:_parse_summary: date(",
        "analysis/td_can.py:_parse_period: date(",
        "analysis/td_can.py:_date_tokens: date(",
        "analysis/td_can.py:_native_date_to_iso: date(",
    ):
        assert not any(entry.startswith(closed) for entry in census), (
            f"{closed}...) is back in the census: the funnel was reverted"
        )


def test_the_disclosure_list_this_card_emptied_is_empty():
    """#HYGIENE8 disclosed eight sites it could not close and carded them here.
    An emptied list is the outcome; a list that quietly refilled would be the
    next card, and it would have to say so."""
    from tests.test_raise_privacy3 import _CARRIED_ECHOING_SITES

    assert _CARRIED_ECHOING_SITES == {}, (
        "a site was parked in the carried list; it needs a card, not an entry"
    )


# ---------------------------------------------------------------------------
# 8. RAISE-PRIVACY-5 — the LOOKUP the conversion census could not see
# ---------------------------------------------------------------------------
#
# RAISE-PRIVACY-4's review confirmed one document-reachable echo this file's
# card disclosed and did not close, and showed it was closable without moving
# anything: `td_can._parse_period`'s `_MONTHS[sm]` / `_MONTHS[em]` raise
# `KeyError('<the printed word>')` on a period line whose three-letter word is
# not a month, and `_native_date_to_iso`'s `_MONTHS[...]` does the same behind
# a caller's guard. A `KeyError`'s message IS its key, so there is no `raise`
# to grep for and no conversion call for a census to walk — which is why
# `tests/test_privacy3_boundaries.py` §4c now walks subscripts.
#
# THE CONSTRAINT, and it is the whole shape of the fix: the raised CLASS may
# not move. `parser_registry._guarded` reduces a parser crash to
# `type(exc).__name__`, so a `KeyError` that became a `ValueError` would move
# an outcome even though no figure moved. `.get` + a FIXED sentence raised
# from OUTSIDE any handler keeps the class, the control flow and every
# published field, and takes only the word out of the message.

#: This card's base — the tree the both-tree drive below is only a proof
#: against. Distinct from `BASE_REVISION` above, which is RAISE-PRIVACY-4's:
#: at THIS base the eight `date()` sites are already funnelled and the three
#: lookups are not.
RAISEPRIV5_BASE_REVISION = "897d69e"

#: The three-letter words that are not months. Invented, and each is a shape
#: a TD period line can really carry: a word derived from this file's own
#: canary, an OCR misread of a month name, and a printed word that is simply
#: not a month. `_PERIOD_RE` and `_DATE_TOKEN_RE` both prove `[A-Z]{3}` and
#: nothing more, so all three reach the lookup.
MONTH_WORDS = {
    "canary": CANARY[:3],
    "ocr-misread-month": "JUI",
    "a-printed-word-that-is-not-a-month": "TOT",
}


def raisepriv5_drives(package: str) -> dict:
    """The three lookups, driven through the REAL reader, inside one package."""
    td = importlib.import_module(f"{package}.td_can")

    return {
        "td_can.period_start_month":
            lambda word: td._parse_period(f"{word} 10/31 - MAR 28/31"),
        "td_can.period_end_month":
            lambda word: td._parse_period(f"JAN 10/31 - {word} 28/31"),
        "td_can.native_date_month":
            lambda word: td._native_date_to_iso(f"{word}10",
                                                default_year=_DEFAULT_YEAR),
    }


#: The reader each lookup refusal must name, so a drive cannot be satisfied by
#: some other refusal of the same reader. Both `_parse_period` ends name the
#: same site on purpose — a caller cannot tell the start refusal from the end
#: one, which is the same property the two `date_refusal`s of
#: `_native_date_to_iso` have.
LOOKUP_READERS = {
    "td_can.period_start_month": "td_can._parse_period",
    "td_can.period_end_month": "td_can._parse_period",
    "td_can.native_date_month": "td_can._native_date_to_iso",
}

#: A month word each site CAN read. A refusal that also refused the good case
#: would be a regression wearing a fix's clothes.
LOOKUP_VALID = {
    "td_can.period_start_month": "JAN",
    "td_can.period_end_month": "FEB",
    "td_can.native_date_month": "MAR",
}

LOOKUP_CELLS = [
    (site, shape) for site in sorted(LOOKUP_READERS) for shape in sorted(MONTH_WORDS)
]


@pytest.fixture(scope="module")
def raisepriv5_base_tree(tmp_path_factory):
    """`analysis/` as it stood at THIS card's base, importable beside ours."""
    try:
        from tools.hygiene8_base_tree import load_base_analysis
    except ImportError as exc:                        # pragma: no cover
        pytest.skip(f"tools.hygiene8_base_tree is not importable: {exc!r}")
    try:
        return load_base_analysis(
            RAISEPRIV5_BASE_REVISION,
            repo=PROJECT_ROOT,
            scratch=tmp_path_factory.mktemp("raisepriv5_base"),
        )
    except Exception as exc:                          # pragma: no cover
        pytest.skip(
            f"the base tree {RAISEPRIV5_BASE_REVISION} is unavailable: {exc!r}"
        )


def test_the_two_base_revisions_are_different_trees(base_tree, raisepriv5_base_tree):
    """The vacuity check for the vacuity checks. Two base packages are loaded
    in this process and neither may be the other: §2's drives must echo a
    `date()` number at `2f24b06`, and §8's must echo a month WORD at the tree
    where those eight sites are already closed."""
    assert base_tree.package != raisepriv5_base_tree.package
    assert base_tree.revision != raisepriv5_base_tree.revision


# --- the base tree: the lookup echoes the printed word ---------------------

@pytest.mark.parametrize("site,shape", LOOKUP_CELLS)
def test_the_three_lookups_echoed_the_printed_word_at_the_base_tree(
    site, shape, raisepriv5_base_tree
):
    """Without this, every branch assertion below could pass because the
    fixture never reached the subscript at all."""
    word = MONTH_WORDS[shape]
    with pytest.raises(KeyError) as raised:
        raisepriv5_drives(raisepriv5_base_tree.package)[site](word)
    assert raised.value.args == (word,), (
        f"{site}/{shape}: the base did not raise the printed word as its key, "
        "so the fixture probably never reached the lookup"
    )
    assert word in str(raised.value) and word in repr(raised.value)


# --- this tree: the same class, and the word is gone -----------------------

@pytest.mark.parametrize("site,shape", LOOKUP_CELLS)
def test_the_three_lookups_refuse_without_quoting_at_the_branch(site, shape):
    """RAISE-PRIVACY-5, closed. Same drive, same fixture, this tree: the same
    CLASS still refuses, and the printed word reaches neither `str`, `repr`,
    `args`, `__notes__`, the chain nor a rendered traceback."""
    word = MONTH_WORDS[shape]
    with pytest.raises(KeyError) as raised:
        raisepriv5_drives("analysis")[site](word)
    assert _leaking(raised.value, word) == []
    assert f"reader={LOOKUP_READERS[site]}" in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__context__ is None


@pytest.mark.parametrize("site,shape", LOOKUP_CELLS)
def test_the_lookup_refusal_carries_no_digit_at_all(site, shape):
    """Unlike the `date_refusal` above, this message interpolates NOTHING —
    it is a string literal in the source — so the claim needs no exemption."""
    word = MONTH_WORDS[shape]
    with pytest.raises(KeyError) as raised:
        raisepriv5_drives("analysis")[site](word)
    for surface in ("str", "repr", "args", "chain", "notes"):
        text = _surfaces(raised.value)[surface]
        assert not any(char.isdigit() for char in text), (
            f"{site}/{shape}: a digit reached {surface}"
        )


@pytest.mark.parametrize("site,shape", LOOKUP_CELLS)
def test_the_lookup_refusal_class_is_identical_on_both_trees(
    site, shape, raisepriv5_base_tree
):
    """THE constraint of this card, measured rather than argued. The dispatch
    seam sees `type(exc).__name__` and nothing else, so this is the whole of
    what a document's outcome can depend on."""
    word = MONTH_WORDS[shape]

    def raised_by(package):
        try:
            raisepriv5_drives(package)[site](word)
        except BaseException as exc:                  # noqa: BLE001
            return type(exc).__name__
        return "<returned>"

    theirs = raised_by(raisepriv5_base_tree.package)
    assert theirs == raised_by("analysis") == "KeyError"


def test_the_two_ends_of_the_period_still_refuse_indistinguishably():
    """The property the two `date_refusal`s of this reader already have,
    extended to the lookup: a caller cannot tell WHICH end of the printed
    period was unreadable, because that would be a fact about the document."""
    from analysis import td_can

    messages = set()
    for line in (f"{CANARY[:3]} 10/31 - MAR 28/31", f"JAN 10/31 - {CANARY[:3]} 28/31"):
        with pytest.raises(KeyError) as raised:
            td_can._parse_period(line)
        messages.add(str(raised.value))
    assert len(messages) == 1, messages


# --- the other half of "only the message changed" --------------------------

@pytest.mark.parametrize("site", sorted(LOOKUP_VALID))
def test_a_readable_month_word_reads_identically_on_both_trees(
    site, raisepriv5_base_tree
):
    """A month the reader CAN read publishes the same payload leaf for leaf on
    both trees, so nothing this card touched changed what a document
    publishes."""
    from tools.hygiene8_base_tree import leaf_diff

    word = LOOKUP_VALID[site]
    ours = _payload(raisepriv5_drives("analysis")[site](word))
    theirs = _payload(raisepriv5_drives(raisepriv5_base_tree.package)[site](word))
    assert leaf_diff(theirs, ours) == []
    assert ours, f"{site}: the valid drive published nothing"


@pytest.mark.parametrize("shape", sorted(NON_REACHING))
@pytest.mark.parametrize("site", sorted(LOOKUP_READERS))
def test_a_shape_that_never_reaches_the_lookup_is_identical_on_both_trees(
    site, shape, raisepriv5_base_tree
):
    """No new refusal where none existed, and no new acceptance. These shapes
    are refused by the regex or by the earlier SHAPE refusal, so the lookup is
    never reached and the outcome must be bit-for-bit what it was."""
    from tools.hygiene8_base_tree import leaf_diff

    word = NON_REACHING[shape]

    def outcome(package):
        try:
            return "returned", _payload(raisepriv5_drives(package)[site](word))
        except BaseException as exc:                  # noqa: BLE001
            return f"raised {type(exc).__name__}", exc

    base_kind, base_value = outcome(raisepriv5_base_tree.package)
    our_kind, our_value = outcome("analysis")
    assert base_kind == our_kind, f"{site}/{shape}: the outcome CLASS moved"
    if base_kind == "returned":
        assert leaf_diff(base_value, our_value) == []
    else:
        for exc in (base_value, our_value):
            assert _leaking(exc, word) == [], f"{site}/{shape}: {exc!r} quotes it"


#: Arabic-Indic decimal digits. `re`'s `\d` matches Unicode category Nd and
#: `int()` accepts every Nd character, so these match `(\d{1,2})/(\d{2})` and
#: convert — which is the whole of why moving the month lookup ahead of
#: `2000 + int(sy)` reorders nothing a caller can observe.
_ND_DIGITS = {"ten": "١٠", "thirty-one": "٣١"}


@pytest.mark.parametrize("word", ["JAN", CANARY[:3]])
def test_the_month_lookup_moved_ahead_of_the_year_and_that_reorders_nothing(
    word, raisepriv5_base_tree
):
    """The one evaluation-order change this card makes, driven on both trees.

    At the base the lookup was the SECOND argument of `iso_or_none`, so
    `2000 + int(sy)` ran first; here it runs before the call. That is
    unobservable only if `int()` on a group `(\\d{2})` produced cannot raise,
    and the strongest available witness is a period line whose digits are not
    ASCII at all: both trees must agree, on the readable word and on the
    unreadable one."""
    line = f"{word} {_ND_DIGITS['ten']}/{_ND_DIGITS['thirty-one']} - MAR 28/31"

    def outcome(package):
        td = importlib.import_module(f"{package}.td_can")
        try:
            return "returned", td._parse_period(line)
        except BaseException as exc:                  # noqa: BLE001
            return f"raised {type(exc).__name__}", None

    assert outcome(raisepriv5_base_tree.package) == outcome("analysis")


# --- the fourth subscript: the one the census allows, and why ---------------

@pytest.mark.parametrize("shape", sorted(MONTH_WORDS))
def test_the_guarded_row_date_lookup_skips_a_non_month_word_on_both_trees(
    shape, raisepriv5_base_tree
):
    """`TOKEN_LOOKUP_ALLOWED`'s single entry, measured rather than asserted.

    `_date_tokens`'s `_MONTHS[mon]` still stands as a subscript because
    `if mon not in _MONTHS: continue` guards it in the same loop body: a
    non-month word costs the TOKEN and raises nothing. Giving it a refusal
    would be a new refusal, which this card may not introduce — so what is
    proved is that it raises nothing, on both trees, and still reads the
    month beside it."""
    word = MONTH_WORDS[shape]
    for package in (raisepriv5_base_tree.package, "analysis"):
        td = importlib.import_module(f"{package}.td_can")
        assert td._date_tokens(f"{word} 10 JAN 11", default_year=_DEFAULT_YEAR) == [
            "2031-01-11"
        ]


def test_the_native_lookup_stays_unreachable_from_its_production_caller():
    """The reachability claim in the reader's own comment, driven.

    `_native_date_index` selects a column through `_native_date_token`, which
    tests `text[:3] in _MONTHS` before anything else — so the token that would
    reach the closed lookup is never chosen, and the refusal this card
    installs there is a guard against a future caller rather than a change to
    the present one."""
    from analysis import td_can

    for shape, word in MONTH_WORDS.items():
        assert td_can._native_date_token(f"{word}10") is None, shape
        line = f"INVENTED DESCRIPTION {_figure('row_one')} {word}10 {_figure('balance_one')}"
        assert td_can._native_date_index(line) is None, shape
    # And the same line with a real month IS selected, so the assertion above
    # is about the WORD and not about the line's shape.
    readable = f"INVENTED DESCRIPTION {_figure('row_one')} JAN10 {_figure('balance_one')}"
    assert td_can._native_date_index(readable) is not None


def test_the_lookup_refusal_message_is_a_literal_and_the_reader_survives():
    """Two rules of this family in one place: the message is a plain string
    LITERAL in the source (so `CHAIN_GUARDED` can verify it without executing
    anything, and no interpolation can ever be added quietly), and `td_can`
    still declares `date_refusal` — the reroute did not trade one law for the
    other."""
    import ast

    from tests.test_privacy3_boundaries import CHAIN_GUARDED

    assert CHAIN_GUARDED["analysis/td_can.py"] == frozenset({"date_refusal"})
    tree = ast.parse((PROJECT_ROOT / "analysis" / "td_can.py").read_text(encoding="utf-8"))
    key_errors = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "KeyError"
    ]
    assert len(key_errors) == 3, [ast.unparse(node) for node in key_errors]
    for node in key_errors:
        assert node.cause is None
        assert len(node.exc.args) == 1 and not node.exc.keywords
        argument = node.exc.args[0]
        assert isinstance(argument, ast.Constant) and isinstance(argument.value, str)
        assert "reader=td_can." in argument.value
        assert not any(char.isdigit() for char in argument.value)


# ---------------------------------------------------------------------------
# 9. RAISE-PRIVACY-5's SECOND evaluation-order change, named and driven
# ---------------------------------------------------------------------------
#
# This card's review, MINOR-2. §RP5.2 and the reader's comment named ONE
# reorder — `_parse_period`'s lookup moving ahead of `2000 + int(sy)` — and
# §8's Arabic-Indic drive covered it. `_native_date_to_iso` moved its lookup
# too: it was the SECOND argument of `iso_or_none`, so `int(m.group(2))` ran
# after it and now runs after the refusal instead. The justification is the
# same one and it holds; what was missing was saying so and measuring it.
#
# THREE GLYPH CLASSES, because the argument is entirely about what `\d` matches
# and what `int()` accepts:
#
# * ASCII digits — the ordinary case, and the control;
# * ARABIC-INDIC digits — Unicode category Nd, so `\d` matches them AND `int()`
#   accepts them. This is the case where the reorder could be observable if the
#   claim were wrong, because the conversion really does run;
# * SUPERSCRIPTS — category No. `str.isdigit()` is True for them and `int()`
#   rejects them, which is the trap `date_tokens` uses `isdecimal` to avoid —
#   but `\d` never matches one, so the token fails the shape check and takes
#   the shape refusal without reaching either the lookup or `int()`.
#
# `_date_tokens` is driven beside `_native_date_to_iso` because its guarded
# lookup sits in the same grammar and the same reorder question is asked of it.

#: One day cell per glyph class, plus a day no calendar holds — that last one
#: paired with an unreadable month WORD, which is the cell that proves the
#: lookup is reached before the calendar refusal rather than after it.
_ORDER_DAYS = {
    "ascii": "10",
    "arabic-indic-Nd": "١٠",
    "superscript-No": _SUPERSCRIPTS[:2],
    "impossible-day": "30",
}

_ORDER_WORDS = {"readable": "FEB", "unreadable": CANARY[:3]}

#: 14 cells: two readers x three glyph classes x two month words, plus the
#: impossible-day cell on each reader, which is only interesting unreadable.
ORDER_CELLS = [
    (reader, glyphs, word)
    for reader in ("native_date", "date_tokens")
    for glyphs in ("ascii", "arabic-indic-Nd", "superscript-No")
    for word in sorted(_ORDER_WORDS)
] + [
    ("native_date", "impossible-day", "unreadable"),
    ("date_tokens", "impossible-day", "unreadable"),
]


def _order_outcome(package: str, reader: str, glyphs: str, word: str):
    """(what happened, the payload) for one cell inside one package."""
    td = importlib.import_module(f"{package}.td_can")
    day, month_word = _ORDER_DAYS[glyphs], _ORDER_WORDS[word]
    try:
        if reader == "native_date":
            result = td._native_date_to_iso(
                f"{month_word}{day}", default_year=_DEFAULT_YEAR
            )
        else:
            result = td._date_tokens(
                f"{month_word} {day}", default_year=_DEFAULT_YEAR
            )
    except BaseException as exc:                      # noqa: BLE001
        return f"raised {type(exc).__name__}", None
    return "returned", _payload(result)


def test_the_drive_count_of_the_second_reorder_is_the_count_it_states():
    """The same discipline MINOR-1 asked for above: a number written beside a
    parametrisation is a claim about coverage."""
    assert len(ORDER_CELLS) == 14
    assert len(set(ORDER_CELLS)) == 14


@pytest.mark.parametrize("reader,glyphs,word", ORDER_CELLS)
def test_the_second_reorder_changes_no_outcome_on_either_tree(
    reader, glyphs, word, raisepriv5_base_tree
):
    """`_native_date_to_iso`'s lookup now precedes `int(m.group(2))`, and
    `_date_tokens` is asked the same question. Base and tip must agree on what
    happened AND on what was published."""
    theirs = _order_outcome(raisepriv5_base_tree.package, reader, glyphs, word)
    ours = _order_outcome("analysis", reader, glyphs, word)
    assert theirs == ours, f"{reader}/{glyphs}/{word}: {theirs} != {ours}"


def test_the_second_reorder_drive_actually_reaches_the_conversion():
    """The vacuity check for the drive above, and the whole point of the
    Arabic-Indic cell: a non-ASCII decimal day is really READ, so the cell
    where the reorder could bite is a cell that runs the conversion rather than
    one that refuses early."""
    from analysis import td_can

    day = _ORDER_DAYS["arabic-indic-Nd"]
    assert td_can._native_date_to_iso(f"FEB{day}", default_year=_DEFAULT_YEAR) == (
        "2031-02-10"
    )
    assert td_can._date_tokens(f"FEB {day}", default_year=_DEFAULT_YEAR) == (
        ["2031-02-10"]
    )
    # And the superscript cell really does refuse before the lookup, which is
    # why it can say nothing about the conversion order.
    with pytest.raises(ValueError) as raised:
        td_can._native_date_to_iso(
            f"FEB{_ORDER_DAYS['superscript-No']}", default_year=_DEFAULT_YEAR
        )
    assert "reader=td_can._native_date_to_iso" in str(raised.value)


def test_the_month_lookup_is_reached_before_the_calendar_refusal():
    """The impossible-day cells, stated as the property they measure: with an
    unreadable month WORD and a day no calendar holds, it is the LOOKUP that
    refuses, not `iso_or_none` — on both trees, and with the class unchanged.
    That is what makes the reorder a reorder of two steps rather than a change
    of which step decides."""
    from analysis import td_can

    with pytest.raises(KeyError):
        td_can._native_date_to_iso(
            f"{CANARY[:3]}{_ORDER_DAYS['impossible-day']}", default_year=_DEFAULT_YEAR
        )
    # The same day with a READABLE word takes the calendar refusal instead, so
    # the assertion above is about the word and not about the day.
    with pytest.raises(ValueError):
        td_can._native_date_to_iso(
            f"FEB{_ORDER_DAYS['impossible-day']}", default_year=_DEFAULT_YEAR
        )

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
#: sixteen drives that exist rather than a cross-product with holes in it.
CELLS = [
    (site, shape)
    for site in sorted(POISON)
    for shape in sorted(POISON[site])
]

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


@pytest.mark.parametrize("site,shape", CELLS)
def test_the_refusal_carries_no_digit_at_all_on_the_message_surfaces(site, shape):
    """Stronger than the run floor, and version-proof.

    The digit-run test cannot see a one-digit echo: `year must be in 1..9999,
    not 0` quotes a printed `0000` as `0`, and CPython's wording has already
    changed once (3.13 rewrote every `date()` range message). The refusals this
    card installs contain no decimal digit whatsoever on the message surfaces,
    so the assertion is made directly. The rendered traceback is excluded here
    and covered by the run test above: it quotes line numbers and source, which
    are digits that are not the document's.
    """
    token, _ = POISON[site][shape]
    with pytest.raises(ValueError) as raised:
        raisepriv4_drives("analysis")[site](token)
    for surface in ("str", "repr", "args", "chain", "notes"):
        text = _surfaces(raised.value)[surface]
        assert not any(char.isdigit() for char in text), (
            f"{site}/{shape}: a digit reached {surface}"
        )


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

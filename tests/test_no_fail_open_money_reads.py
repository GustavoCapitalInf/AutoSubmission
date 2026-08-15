"""W3 §MG-C2 guard: a refused money token must never become a published zero.

`parse_money(x) or 0.0` — and its kin `abs(_money(x) or 0.0)` — reads as a
harmless default. It is not. The left side is `None` for exactly one reason at
these sites: the grammar was handed a token and REFUSED it. The `or` then
replaces a figure the bank printed with a number it did not, silently, on a
document the platform goes on to reconcile, average and approve. §CHASE-CLOSURE
found one in production (a detached-sign fee read as 0.00, hiding inside the
±1.00 reconciliation tolerance); cards §MG3 and §MG4 then deliberately WIDENED
what the grammar refuses, putting a fail-open behind every new refusal.

The census that motivated this guard, re-derived on `ea8d8e8`:

    39 sites in 15 files    a money-reading CALL directly left of `or 0`
    22 sites in  6 files    a NAME bound to a money read
    18 sites in  5 files    a NAME bound to something else
    44 sites in 19 files    an ATTRIBUTE (`stmt.stated_*`, `.running_balance`)

Only the first class is a fail-open, and this guard is about that class alone.
The others are ABSENCE defaults: a statement that prints no Checks line really
does have zero checks, and `or 0.0` is the correct arithmetic identity for a
section the document does not have. Telling the two apart is the whole point —
`analysis.money.read_money` raises on a refusal and passes absence through as
`None`, so the `or 0.0` that remains means only what it should.

The guard fails on the SHAPE, before anyone has to notice the wrong number.

WHAT THIS GUARD DOES NOT CATCH (W3 §MG-C2 D4)
---------------------------------------------
Recorded so nobody mistakes it for a proof of absence:

1. **It is a NAME allowlist, so it is evaded by renaming.** `MONEY_READERS`
   lists the readers that exist today. A parser that adds `_amt` or
   `_read_cell`, or that calls a reader through an attribute
   (`self._money(x) or 0.0`, `mod._money(x) or 0.0`), is invisible here. The
   companion defence is `test_no_parser_helper_clones.py`, which makes a new
   private money reader hard to add in the first place.
2. **Two-operand `or` only.** `a or b or 0.0` parses as one `BoolOp` with
   three values and is skipped, as is `parse_money(x) if y else 0.0` and
   `float(parse_money(x) or 0)` written with an int zero inside another call.
   The attested census contained none of these; they are gaps, not decisions.
3. **It cannot see the ARGUMENT's provenance beyond one syntactic tell.**
   `read_money` is correct only for a token a pattern has already matched. A
   raw container cell is the D2 defect and is caught below by its `Subscript`
   shape, but a raw cell passed through a local variable is not.
4. **It says nothing about non-zero fail-opens** — a refusal collapsing to
   `1.0`, to `None` where `None` is later coerced, or to a dropped row (the
   `continue` class, W3 §MG-C2 carried finding 2).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.bofa import _native_money_after, repair_bofa_summary
from analysis.money import read_money
from analysis.regions import _money as _regions_money
from analysis.schema import Statement
from analysis.tables import table_rows

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "analysis"

#: Every function in the analysis layer that reads a money token and answers
#: `None` when it will not. `read_money` is deliberately absent: it is the
#: checked wrapper, and it never returns `None` for a refusal.
MONEY_READERS = frozenset({
    "parse_money", "parse_amount", "parse_digit_scrubbed",
    "_money", "_amount", "_amount_value", "_money_value", "_parse_money",
})


def _is_zero(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and not isinstance(node.value, bool)
        and node.value in (0, 0.0)
    )


def _called_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    return node.func.id if isinstance(node.func, ast.Name) else None


def _fail_open_sites(path: Path) -> list[str]:
    """`<money reader>(...) or 0` sites in one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
            continue
        if len(node.values) != 2 or not _is_zero(node.values[1]):
            continue
        reader = _called_name(node.values[0])
        if reader in MONEY_READERS:
            found.append(f"{path.name}:{node.lineno}  {reader}(...) or 0")
    return found


def test_no_money_read_collapses_a_refusal_into_zero():
    """The shape itself is the defect, so the shape is what is banned.

    The fix is never to add an exception here. It is to call
    `analysis.money.read_money(token, reader)`, which raises on a refusal and
    returns `None` only for an absent token — so a trailing `or 0.0` keeps
    meaning "this section is not printed" and stops meaning "and also, this
    number might be a lie".
    """
    offenders = []
    for path in sorted(ANALYSIS_DIR.glob("*.py")):
        offenders.extend(_fail_open_sites(path))
    assert offenders == [], (
        "a money-read refusal is being published as 0 at:\n  "
        + "\n  ".join(offenders)
        + "\nUse analysis.money.read_money(token, reader) instead."
    )


def test_the_guard_can_actually_see_the_shape_it_bans():
    """A guard that cannot fail is not a guard. Every spelling the census
    found is put back in front of it and must be caught."""
    source = (
        "def f(m, cell):\n"
        "    a = parse_money(cell) or 0.0\n"
        "    b = abs(_money(m.group(1)) or 0.0)\n"
        "    c = round(-abs(_money(cell) or 0.0), 2)\n"
        "    d = parse_digit_scrubbed(cell) or 0\n"
        "    return a, b, c, d\n"
    )
    tree = ast.parse(source)
    caught = [
        _called_name(node.values[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.Or)
        and len(node.values) == 2
        and _is_zero(node.values[1])
        and _called_name(node.values[0]) in MONEY_READERS
    ]
    assert sorted(caught) == ["_money", "_money", "parse_digit_scrubbed", "parse_money"]


def test_absence_defaults_are_not_caught():
    """The guard must leave the legitimate class alone, or it will be
    disabled. An Optional statement field and a reader that reports an absent
    label are both honest `or 0.0` sites."""
    source = (
        "def f(stmt, txns, checks):\n"
        "    a = stmt.stated_total_debits or 0.0\n"
        "    b = txns[-1].running_balance or 0.0\n"
        "    c = abs(checks or 0.0)\n"
        "    d = read_money(cell, _money) or 0.0\n"
        "    return a, b, c, d\n"
    )
    tree = ast.parse(source)
    caught = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.Or)
        and len(node.values) == 2
        and _is_zero(node.values[1])
        and _called_name(node.values[0]) in MONEY_READERS
    ]
    assert caught == []


# ===========================================================================
# The two shapes end to end, at the readers where the archive actually
# produces a `None` today (bofa: 14 documents across both readers).
# ===========================================================================

#: A BofA account summary with no `Checks` line, which is how most of them
#: print. `checks or 0.0` must keep supplying the identity here — 21 archive
#: documents reach this branch and every one of them must stay unmoved.
NO_CHECKS_LINE = """
Bank of America
Account summary
Beginning balance on February 1, 2026 $6,767.39
Deposits and other credits 35,968.84
Withdrawals and other debits -35,626.82
Service fees -120.43
Ending balance on February 28, 2026 $1,498.58
"""

#: The same summary printing a `Checks` line the grammar cannot read: the
#: integer run is past `MAX_INTEGER_DIGITS`, the §MG4 bound that keeps a
#: barcode out of an amount column. Before §MG-C2 this folded in as 0.00 and
#: `stated_total_debits` came out as if the account had written no cheques.
UNREADABLE_CHECKS_LINE = NO_CHECKS_LINE.replace(
    "Service fees -120.43",
    "Checks -11111111111111.00\nService fees -120.43",
)


def test_an_absent_summary_line_is_still_an_honest_zero():
    """Absence must survive the fix, or 21 archive documents regress."""
    stmt = repair_bofa_summary(NO_CHECKS_LINE, Statement(bank="Bank of America"))
    assert stmt.stated_total_debits == 35747.25   # withdrawals + fees, no checks
    # The fee is folded INTO the debit total, so the separate field is cleared
    # on purpose: counting it in both places would double it.
    assert stmt.stated_service_charge is None


def test_an_unreadable_summary_line_declines_instead_of_folding_in_zero():
    """The differential. The bank printed a Checks line; the grammar refused
    its amount. Before §MG-C2 `repair_bofa_summary` published
    `stated_total_debits == 35747.25` — numerically identical to the statement
    that prints NO cheques at all, so nothing downstream could tell a document
    with unread cheques from one with none. It now raises."""
    with pytest.raises(ValueError, match="refused a printed token"):
        repair_bofa_summary(UNREADABLE_CHECKS_LINE, Statement(bank="Bank of America"))


def test_the_native_reader_separates_an_absent_label_from_a_refused_amount():
    """`_native_money_after` answered `None` for both, and its callers turned
    that single `None` into 0.00. Absence still answers `None`; a refusal
    raises."""
    assert _native_money_after(NO_CHECKS_LINE, r"Checks") is None
    assert _native_money_after(NO_CHECKS_LINE, r"Service fees") == 120.43
    with pytest.raises(ValueError, match="refused a printed token"):
        _native_money_after(UNREADABLE_CHECKS_LINE, r"Checks")


# ===========================================================================
# D4 — the one provenance tell that IS cheap to check
# ===========================================================================

#: `read_money` raises on a refusal, which is right only when a pattern has
#: already guaranteed the token. Handed a RAW container cell it turns "this
#: cell is not money" into a dead document — the D2 defect, found by review at
#: `regions.py:219` (`read_money(cells[3], _money)`, where the cell can be
#: `N/A` or `--`). A subscript argument is that shape's signature.
def _raw_cell_reads(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "read_money" or not node.args:
            continue
        if isinstance(node.args[0], ast.Subscript):
            found.append(f"{path.name}:{node.lineno}  read_money({ast.unparse(node.args[0])}, ...)")
    return found


def test_read_money_is_never_handed_a_raw_container_cell():
    """A probe must be answered, not raised at.

    `read_money` is for refusal-propagation on a token a regex already
    matched. Over a raw cell it is the wrong tool: the correct reading of a
    non-money cell there is ABSENCE, and a reader that returns `None` is what
    belongs in that position (`regions._money`).
    """
    offenders = []
    for path in sorted(ANALYSIS_DIR.glob("*.py")):
        offenders.extend(_raw_cell_reads(path))
    assert offenders == [], (
        "read_money is being handed a raw container cell at:\n  "
        + "\n  ".join(offenders)
        + "\nA non-money cell there is absence, not a refusal: use a reader "
          "that returns None."
    )


def test_the_raw_cell_guard_can_see_the_shape_it_bans():
    """The D2 line as it was written, put back in front of the guard."""
    source = (
        "def f(cells, m, _money):\n"
        "    a = abs(read_money(cells[3], _money) or 0.0)\n"
        "    b = read_money(m.group(1), _money)\n"
        "    return a, b\n"
    )
    tree = ast.parse(source)
    caught = [
        ast.unparse(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "read_money"
        and node.args
        and isinstance(node.args[0], ast.Subscript)
    ]
    assert caught == ["cells[3]"]


# ===========================================================================
# D2 / D3 — the probe must be answered, not raised at (analysis/regions.py)
# ===========================================================================


@pytest.mark.parametrize(
    "cell",
    ["N/A", "n/a", "--", "—", "", "   ", "DEPOSIT", "Balance", "1.5", "1.2.3",
     "1" * 14 + ".00"],
)
def test_the_regions_cell_probe_answers_none_and_never_raises(cell):
    """W3 §MG-C2 D3. `_parse_section` walks a row's cells right-to-left asking
    "is this the amount column?", so it is handed dates, descriptions and
    `N/A` BY DESIGN. A cell that is not money is an answer, not an error —
    raising here would let one unreadable cell in one row kill a document that
    otherwise parses perfectly."""
    assert _regions_money(cell) is None


@pytest.mark.parametrize(
    "cell, expected",
    [("1,234.56", 1234.56), ("1,234.56-", -1234.56), ("-45.00", -45.0), ("0.00", 0.0)],
)
def test_the_regions_probe_still_reads_the_cells_that_are_money(cell, expected):
    assert _regions_money(cell) == expected


def test_a_refused_regions_cell_is_none_and_not_a_zero():
    """The probe answers None rather than raising — but it must not answer
    0.0 either, which is what `abs(parse_money(...) or 0.0)` did. Under that
    idiom a refused cell reported itself as a valid 0.00 amount, the probe
    accepted it as the amount column, and the row published a zero."""
    assert _regions_money("1.5") is None          # one decimal: §MG3 refuses it
    assert _regions_money("1.50") == 1.5          # two decimals: genuinely money


#: A Regions summary grid that prints the Average Balance LABEL with no
#: figure beside it — the shape `read_money(cells[3], _money)` turned into a
#: dead document.
REGIONS_AVERAGE_BALANCE_NOT_PRINTED = (
    "<table>"
    "<tr><td>Beginning Balance</td><td>1,000.00</td>"
    "<td>Average Balance</td><td>N/A</td></tr>"
    "</table>"
)


def test_a_non_money_average_balance_cell_is_absence_not_a_dead_document():
    """W3 §MG-C2 D2. `cells[3]` is a RAW grid cell, not a regex-guaranteed
    token: a statement can print the Average Balance label with `N/A` beside
    it. That is absence — the field stays unset. It may not raise (killing a
    document over an optional figure) and it may not publish 0.00 (an average
    balance nobody printed)."""
    rows = [
        cells for cells in table_rows(REGIONS_AVERAGE_BALANCE_NOT_PRINTED)
        if len(cells) >= 4 and "average balance" in cells[2].lower()
    ]
    assert len(rows) == 1, "fixture did not produce the average-balance row"
    cell = rows[0][3]
    assert cell == "N/A"

    # The shape D2 removed: `read_money` treats a present-but-unreadable token
    # as a refusal and raises, which over a RAW cell kills the whole document.
    with pytest.raises(ValueError, match="refused a printed token"):
        read_money(cell, _regions_money)

    # What replaced it: the probe answers absence, the field stays unset, and
    # the document survives to publish everything the bank DID print.
    assert _regions_money(cell) is None

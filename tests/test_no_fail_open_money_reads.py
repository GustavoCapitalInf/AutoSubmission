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
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.bofa import _native_money_after, repair_bofa_summary
from analysis.schema import Statement

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

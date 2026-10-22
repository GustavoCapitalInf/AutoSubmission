"""Audit 2026-10-13, F4: reconcile reads the reversal pass's two fields without running the true-revenue pass.

When a statement's rows miss its stated totals, reconcile reads `settlement_reversal` and `reversed_by` (and each
record's amount) to see whether reversal pairs explain the gap. It ran the whole classification for them, true-revenue
pass, passes 7b and 7c and the duplicate finalisation included, and the pipeline then classified the statement again.
Both fields are final after pass 4: no later pass writes either. `classify_statement_reversals` returns the records
through passes 1 to 6, and reconcile reads that.

Pinned here, on fabricated statements (CONTOSO / FABRIKAM / NORTHWIND / SAMPLE rows; registry funders as the lender
tests use them; neutral amounts; 2054 dates):

* the contract: every record's (amount, settlement_reversal, reversed_by) from `classify_statement_reversals` equals
  the stored reading's and both Zelle readings', and reconcile's result is the same field for field either way;
* the source check that keeps it true: in analysis/, only pass 4 (`_apply_reversal_pair_context`) writes either field;
* reconcile no longer runs a reading (the true-revenue pass) for them.
"""
from __future__ import annotations

import ast
from dataclasses import asdict
from pathlib import Path

import pytest

from analysis import transaction_classifier as tc
from analysis.reconcile import reconcile
from tests import zelle_setting_fixtures as fx
from tests.test_represented_funder_payments import CASES as REPRESENTED
from tests.test_returned_funder_payments import CONTROLS, KAPITUS, RULE_D, SALE, _statement

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ("amount", "settlement_reversal", "reversed_by")

#: Statements of the reversal pass's own shapes: a vendor reversal, a chargeback, a returned item, a proven duplicate.
EXTRA = {
    "vendor_reversal": [(1, SALE, 10000.0), (3, "ACH DEBIT NORTHWIND SUPPLY 0001", -420.0),
                        (5, "ACH REVERSAL NORTHWIND SUPPLY 0001", 420.0)],
    "chargeback": [(1, SALE, 10000.0), (2, "CHECK 1001", -300.0), (4, "CHECK 1001 RETURNED ITEM CHARGEBACK", 300.0)],
    "cancelled_transfer": [(1, SALE, 10000.0), (2, "E TRANSFER SAMPLE PAYEE", -150.0),
                           (2, "E TRANSFER CANCELLED SAMPLE PAYEE", 150.0)],
    "funder_return": [(1, SALE, 10000.0), (2, KAPITUS, -850.0), (3, "KAPITUS RETURNED ACH ITEM 0001", 850.0)],
}


def _statements():
    built = {}
    for name, (rows, bank, *_rest) in {**RULE_D, **CONTROLS}.items():
        built[f"rule_d.{name}"] = _statement(rows, bank)
    for name, (rows, *_rest) in REPRESENTED.items():
        built[f"represented.{name}"] = _statement(rows)
    for name, rows in EXTRA.items():
        built[f"extra.{name}"] = _statement(rows)
    built["duplicate"] = _statement(EXTRA["vendor_reversal"] + [EXTRA["vendor_reversal"][-1]], balances=True)
    for name, (rows, holder, title) in fx.CASES.items():
        built[f"zelle.{name}"] = fx.statement(rows, holder=holder, title=title)
    return built


STATEMENTS = _statements()


def _missing_its_totals(statement):
    """The statement with stated totals its rows miss, so reconcile reads the reversal pairs."""
    credits = sum(t.amount for t in statement.transactions if t.amount > 0)
    debits = -sum(t.amount for t in statement.transactions if t.amount < 0)
    return statement.model_copy(update={
        "stated_total_credits": round(credits - 150.0, 2), "stated_total_debits": round(debits + 150.0, 2),
    })


def _fields(records):
    return [tuple(getattr(record, name) for name in FIELDS) for record in records]


@pytest.mark.parametrize("name", sorted(STATEMENTS))
def test_the_reversal_fields_are_final_after_pass_four(name):
    statement = STATEMENTS[name]
    prefix = _fields(tc.classify_statement_reversals(statement))

    assert _fields(tc.classify_statement_transactions(statement)) == prefix
    assert _fields(tc.classify_statement_transactions(statement, zelle_true_revenue=True)) == prefix
    stored, counted = tc.classify_statement_readings(statement)
    assert _fields(stored) == prefix
    if counted is not None:
        assert _fields(counted) == prefix


@pytest.mark.parametrize("name", sorted(STATEMENTS))
def test_reconcile_reads_the_same_with_the_whole_classification(monkeypatch, name):
    statement = _missing_its_totals(STATEMENTS[name])
    now = asdict(reconcile(statement))
    monkeypatch.setattr(tc, "classify_statement_reversals", lambda stmt: tc.classify_statement_transactions(stmt))
    assert asdict(reconcile(statement)) == now


def test_the_fixtures_reach_the_branch_and_its_pairs():
    """The parity above is not vacuous: reconcile takes the reversal branch, and some statements pair and adjust."""
    results = [reconcile(_missing_its_totals(statement)) for statement in STATEMENTS.values()]
    assert sum(result.reversal_pair_count > 0 for result in results) >= 5
    assert any(result.coverage_adjusted_for_reversals for result in results)


def test_reconcile_runs_no_reading_for_the_reversal_fields(monkeypatch):
    """F4: the coverage check classifies through pass 4's prefix only; the true-revenue pass is not run for it."""
    readings: list[object] = []
    real = tc._classify_statement_reading

    def counting(*args, **kwargs):
        readings.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(tc, "_classify_statement_reading", counting)
    result = reconcile(_missing_its_totals(_statement(EXTRA["funder_return"])))

    assert result.reversal_pair_count == 1
    assert readings == []


_PASS_FOUR = "_apply_reversal_pair_context"
_WRITTEN = {"reversed_by", "settlement_reversal"}


def _writers(tree: ast.AST) -> list[tuple[str, int]]:
    """(enclosing function, line) of every write of either field: a keyword argument, a **{...} key, a setattr."""
    found: list[tuple[str, int]] = []

    def visit(node: ast.AST, function: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in _WRITTEN:
                    found.append((function, node.lineno))
                if keyword.arg is None and isinstance(keyword.value, ast.Dict):
                    for key in keyword.value.keys:
                        if isinstance(key, ast.Constant) and key.value in _WRITTEN:
                            found.append((function, node.lineno))
            if (
                isinstance(node.func, ast.Name) and node.func.id == "setattr" and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant) and node.args[1].value in _WRITTEN
            ):
                found.append((function, node.lineno))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, "<module>")
    return found


def test_only_pass_four_writes_the_reversal_fields():
    """The contract classify_statement_reversals stands on: a later pass that wrote either field would make reconcile
    read a different value than the published records carry."""
    writers = []
    for path in sorted((ROOT / "analysis").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        writers += [(path.relative_to(ROOT).as_posix(), function, line) for function, line in _writers(tree)]
    assert writers and all(
        path == "analysis/transaction_classifier/__init__.py" and function == _PASS_FOUR for path, function, _line in writers
    ), writers


def test_the_source_check_sees_a_later_writer():
    later = ast.parse(
        "def _apply_something_later(records):\n"
        "    return [replace(r, reversed_by=None) for r in records]\n"
        "def other(r):\n"
        "    return replace(r, **{'settlement_reversal': True})\n"
        "def third(r):\n"
        "    setattr(r, 'reversed_by', 'transaction:1')\n"
    )
    assert [function for function, _line in _writers(later)] == ["_apply_something_later", "other", "third"]


def test_the_prefix_is_a_statement_scope_of_the_matcher_memo(monkeypatch):
    """The prefix-only classification opens the matcher memo like the other statement classifications."""
    from analysis import payee_matcher

    seen = []
    real = tc._classify_statement_prefix

    def watching(statement, min_recurring_count):
        seen.append(payee_matcher._MATCH_MEMO.get() is not None)
        return real(statement, min_recurring_count)

    monkeypatch.setattr(tc, "_classify_statement_prefix", watching)
    tc.classify_statement_reversals(_statement(EXTRA["funder_return"]))

    assert seen == [True]
    assert payee_matcher._MATCH_MEMO.get() is None


def test_a_statement_with_no_rows_is_still_answered():
    assert tc.classify_statement_reversals(_statement([])) == []

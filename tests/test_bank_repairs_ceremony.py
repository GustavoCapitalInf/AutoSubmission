"""The owner-ruled fence of five bank repairs (rulings S-1..S-5, 2026-09-15),
ported from Phase 2.3 cell P's ceremony tests on `wave23-precision`, which were
never composed into the shipped line (audit 2026-10-13, PARSERS-1).

`analysis/bank_repairs.py` keeps eight repair definitions. Five were ruled off
the analysis path:

* S-1 `repair_capital_one_running_amount`, S-2 `repair_regions_transactions`
  and S-3 `repair_chase_remote_deposit_count_column`: amount rewrites,
  `unsafe_rewrite` — each writes a figure the paper did not print, chosen
  because it closes the arithmetic;
* S-4 `repair_single_row_signs_from_balances`: `unsafe_rewrite`
  (anti-optimizer selection) — of several rows whose flip would reconcile a
  balance step, it publishes the first;
* S-5 `repair_truist_converted_checks`: `legacy_needing_replacement` — its
  duplicate witness can be the very row it deletes.

The rulings keep each definition as the record of what ran, require its
docstring to carry the classification and the doctrine reason, and require a
tripwire that nothing under `analysis/` can reach it: not a call, not an
import, not an alias binding or a callback argument. What this file pins:

* the tripwire, by AST over every module under `analysis/`;
* each fenced definition still declares its ruled classification and, called
  directly, still does what it always did (S-5: the paired, transfer-direction,
  orphan and unrelated-bank characterizations its ruling names);
* the invention guard `restates_a_printed_figure`, the line the
  classifications are drawn on, and the two kept direction readers held to it;
* through `apply_statement_repairs` itself, each shape claimed by its own
  registration now comes back as printed, and a statement only the rewrite
  made reconcile no longer reconciles.

The ceremony instrument (`tools/bank_repairs_ceremony.py` on that branch, with
its replay reproduction and positive controls) is NOT ported: the audit's
full-corpus replay is this change's measurement. The four helpers that read a
repair's declaration out of the module are that instrument's inventory
functions, copied as they were.

Every fixture is synthetic: literal descriptions, dates in 2031, figures built
from small integers.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.bank_repairs import (
    repair_capital_one_running_amount,
    repair_chase_remote_deposit_count_column,
    repair_regions_transactions,
    repair_santander_signs_from_balances,
    repair_scotiabank_misc_payment_sign,
    repair_single_row_signs_from_balances,
    repair_truist_converted_checks,
    restates_a_printed_figure,
)
from analysis.schema import Statement, Transaction

ROOT = Path(__file__).resolve().parent.parent
REPAIRS_MODULE = ROOT / "analysis" / "bank_repairs.py"

SAFE = "safe_evidence_preserving_normalisation"
UNSAFE = "unsafe_rewrite"
LEGACY = "legacy_needing_replacement"
#: The closed vocabulary R10 names.
CLASSIFICATIONS = (SAFE, UNSAFE, LEGACY)
CLASSIFICATION_MARKER = "R10-CLASSIFICATION:"
FENCED_CLASSIFICATIONS = {
    "repair_capital_one_running_amount": UNSAFE,
    "repair_regions_transactions": UNSAFE,
    "repair_chase_remote_deposit_count_column": UNSAFE,
    "repair_single_row_signs_from_balances": UNSAFE,
    "repair_truist_converted_checks": LEGACY,
}
FENCED = tuple(FENCED_CLASSIFICATIONS)


# ---------------------------------------------------------------------------
# the declarations, read out of the module (the ceremony instrument's
# inventory helpers, copied from `tools/bank_repairs_ceremony.py`)
# ---------------------------------------------------------------------------

def _docstring_classification(node: ast.FunctionDef) -> str | None:
    doc = ast.get_docstring(node) or ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith(CLASSIFICATION_MARKER):
            value = stripped[len(CLASSIFICATION_MARKER):].strip().split()[0] if stripped[len(CLASSIFICATION_MARKER):].strip() else ""
            return value or None
    return None


def _bank_aliases(node: ast.FunctionDef) -> set[str]:
    """Local names bound to the bank label (`bank = (stmt.bank or "").upper()`),
    so a guard written through an alias is still read as a bank guard."""
    aliases: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Assign) and any(
                isinstance(leaf, ast.Attribute) and leaf.attr == "bank" for leaf in ast.walk(child.value)):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _mentions_bank(node: ast.AST, aliases: set[str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "bank":
            return True
        if isinstance(child, ast.Name) and child.id in aliases:
            return True
    return False


def _bank_literals(node: ast.FunctionDef) -> tuple[str, ...]:
    """Every string constant this function's own guard compares the bank label
    against — read out of the comparison, never written down here."""
    aliases = _bank_aliases(node)
    found: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Compare):
            continue
        parts = [child.left, *child.comparators]
        if not any(_mentions_bank(part, aliases) for part in parts):
            continue
        for part in parts:
            for leaf in ast.walk(part):
                if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str) and leaf.value:
                    if leaf.value not in found:
                        found.append(leaf.value)
    return tuple(found)


def _declared() -> dict[str, tuple[str | None, tuple[str, ...]]]:
    """{repair name: (declared classification, bank literals)} for every
    `repair_*` function `analysis/bank_repairs.py` defines."""
    tree = ast.parse(REPAIRS_MODULE.read_text(encoding="utf-8"))
    return {
        node.name: (_docstring_classification(node), _bank_literals(node))
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("repair_")
    }


def _txn(day: int, description: str, amount: float, balance: float | None = None) -> Transaction:
    return Transaction(
        date=f"2031-03-{day:02d}", description=description, amount=amount,
        direction="credit" if amount > 0 else "debit", running_balance=balance,
    )


def _statement(bank: str, rows: list[Transaction], opening: float | None, closing: float | None) -> Statement:
    return Statement(bank=bank, transactions=rows, beginning_balance=opening, ending_balance=closing)


# ---------------------------------------------------------------------------
# the fence
# ---------------------------------------------------------------------------

def _fenced_references(source: str, name: str, *, retained_definition: bool = False) -> list[str]:
    """A function value can become a caller through a binding or argument."""
    hits: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name:
            hits.append("name reference")
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and node.attr == name:
            hits.append("attribute reference")
        if isinstance(node, ast.ImportFrom):
            hits += [f"import {a.name}" for a in node.names if a.name == name]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name and not retained_definition:
            hits.append("redefinition")
    return hits


@pytest.mark.parametrize("name", FENCED)
def test_the_fence_catches_a_function_value_before_it_can_be_called_through_an_alias(name):
    """Closure review: direct calls, alias bindings and callback arguments
    all reach the same retained repair. Its definition and mere prose do not."""
    for source in (
        f"def run(stmt):\n    return {name}(stmt)\n",
        f"def run(stmt):\n    return br.{name}(stmt)\n",
        f"from .bank_repairs import {name} as chosen\n",
        f"from . import bank_repairs as br\ndef run(stmt):\n    chosen = br.{name}\n    return chosen(stmt)\n",
        f"def run(stmt):\n    chosen = {name}\n    return chosen(stmt)\n",
        f"def run(stmt):\n    return apply(br.{name}, stmt)\n",
        f"def {name}(stmt):\n    return stmt\n",
    ):
        assert _fenced_references(source, name), source
    assert not _fenced_references(f"def {name}(stmt):\n    return stmt\n", name, retained_definition=True)
    assert not _fenced_references(f"record = {name!r}\n# {name}\n", name)
    assert not _fenced_references("chosen = br.repair_b1_beginning_balance\n", name)


@pytest.mark.parametrize("name", FENCED)
def test_the_fenced_repair_is_defined_declared_and_called_by_nothing(name):
    """R10 items S-1..S-5, ruled. The amount rewrites, direction selector
    and legacy row deletion retain their definitions as the record of what ran. Every one
    crosses the repair doctrine or anti-optimizer rule and has no caller.

    The fence is a rule about CALLERS, checked by reading rather than by
    trusting a comment: no module under `analysis/` may read its function
    value or import it. Binding it to an alias or passing it as a callback is
    already a route to a caller, even when the call uses another name."""
    declared = _declared()
    assert name in declared, f"the fenced definition is gone: {name}"
    classification, bank_literals = declared[name]
    assert classification == FENCED_CLASSIFICATIONS[name], classification
    assert bank_literals, "the fence must not be mistaken for a deletion"

    callers: dict[str, list[str]] = {}
    for path in sorted((ROOT / "analysis").rglob("*.py")):
        hits = _fenced_references(path.read_text(encoding="utf-8"), name,
                                  retained_definition=path == REPAIRS_MODULE)
        if hits:
            callers[str(path.relative_to(ROOT))] = hits
    assert not callers, f"the fenced repair is reachable from the analysis path: {callers}"


def test_every_ceremony_declaration_is_in_the_vocabulary():
    """A repair that gains a declaration outside the closed vocabulary fails
    the build; so does a fenced or kept ceremony repair that loses its one."""
    declared = _declared()
    for name, (classification, _literals) in declared.items():
        assert classification is None or classification in CLASSIFICATIONS, (name, classification)
    for name in (*FENCED, "repair_scotiabank_misc_payment_sign", "repair_santander_signs_from_balances"):
        assert declared[name][0] in CLASSIFICATIONS, name


def test_the_fenced_repair_still_works_if_a_ruling_ever_calls_it_again():
    """The fence is not a deletion and the record must show the difference:
    called directly, the function still does what it always did."""
    cibc = _statement("CIBC", [_txn(2, "SYNTHETIC ROW ONE", 1500.0, 7500.0)], 9000.0, 7500.0)
    repaired = repair_single_row_signs_from_balances(cibc)
    assert repaired.transactions[0].amount == -1500.0, repaired.transactions[0]


def test_the_fenced_selector_picks_the_first_of_two_rows_that_would_both_reconcile():
    """The S-4 reproduction the ruling was made on: two equal rows in one
    printed balance step, either of whose flip closes it. The function flips
    the earlier one and says nothing about the choice."""
    rbc = _statement("Royal Bank of Canada", [
        _txn(2, "SYNTHETIC ROW ONE", 25.0),
        _txn(2, "SYNTHETIC ROW TWO", 25.0, 1000.0),
    ], 1000.0, 1000.0)
    repaired = repair_single_row_signs_from_balances(rbc)
    assert [t.amount for t in repaired.transactions] == [-25.0, 25.0]


# ---------------------------------------------------------------------------
# the invention guard itself
# ---------------------------------------------------------------------------

def test_the_invention_guard_reads_what_it_claims_to_read():
    rows = [_txn(2, "SYNTHETIC ROW ONE", -1500.0), _txn(3, "SYNTHETIC ROW TWO", 2500.0)]
    before = _statement("SYNTHETIC BANK", rows, 9000.0, 10000.0)
    unchanged = before.model_copy(update={"transactions": list(rows)})
    sign_flipped = before.model_copy(update={"transactions": [
        rows[0].model_copy(update={"amount": 1500.0, "direction": "credit"}), rows[1]]})
    dropped = before.model_copy(update={"transactions": [rows[0]]})
    magnitude = before.model_copy(update={"transactions": [
        rows[0].model_copy(update={"amount": -1600.0}), rows[1]]})
    invented_row = before.model_copy(update={"transactions": rows + [_txn(4, "SYNTHETIC ROW THREE", 100.0)]})
    renamed = before.model_copy(update={"transactions": [
        rows[0].model_copy(update={"description": "SYNTHETIC ROW ONE CORRECTED"}), rows[1]]})

    assert restates_a_printed_figure(before, unchanged)
    assert restates_a_printed_figure(before, sign_flipped)
    assert restates_a_printed_figure(before, dropped)
    assert not restates_a_printed_figure(before, magnitude)
    assert not restates_a_printed_figure(before, invented_row)
    assert not restates_a_printed_figure(before, renamed)


def test_the_invention_guard_reads_the_fields_a_repair_is_most_dangerous_with():
    """Review MINOR-2 / mutants P8b..P8e. The guard compared transaction
    magnitudes keyed on `(date, description)` and NOTHING else, so it returned
    True for five statements no safe normalisation could ever produce — and
    its own docstring already said otherwise. The docstring was the part that
    was right."""
    rows = [_txn(2, "SYNTHETIC ROW ONE", -1500.0, 7500.0),
            _txn(3, "SYNTHETIC ROW TWO", 2500.0, 10000.0)]
    before = _statement("SYNTHETIC BANK", rows, 9000.0, 10000.0)

    def after(**update):
        return before.model_copy(update=update)

    # a balance the paper did not print, on a row
    assert not restates_a_printed_figure(before, after(transactions=[
        row.model_copy(update={"running_balance": 4200.0}) for row in rows]))
    # ... and a printed one erased: a repair may not delete a figure either
    assert not restates_a_printed_figure(before, after(transactions=[
        row.model_copy(update={"running_balance": None}) for row in rows]))
    # the statement's own two figures
    assert not restates_a_printed_figure(before, after(ending_balance=4200.0))
    assert not restates_a_printed_figure(before, after(beginning_balance=4200.0))
    # the ledger emptied: not a normalisation, a replacement
    assert not restates_a_printed_figure(before, after(transactions=[]))
    # a printed row DUPLICATED — `after` must be a sub-multiset, not a set of
    # familiar keys, which is what let one row stand in for two
    assert not restates_a_printed_figure(before, after(transactions=[rows[0], rows[0]]))
    # and the three shapes a safe normalisation IS allowed
    assert restates_a_printed_figure(before, after(transactions=[rows[0]]))
    assert restates_a_printed_figure(before, after(transactions=[
        rows[0].model_copy(update={"amount": 1500.0, "direction": "credit"}), rows[1]]))
    assert restates_a_printed_figure(before, after())


# ---------------------------------------------------------------------------
# the retained characterizations
# ---------------------------------------------------------------------------

def _truist_case() -> Statement:
    rows = [
        _txn(2, "TRUIST ONLINE TRANSFER ONLINE FROM SYNTHETIC SAVINGS", -1200.0),
        _txn(3, "CONVERTED CHECK 1001", -4500.0),
        _txn(3, "~CONVERTED CHECK 1001", -4500.0),
        _txn(4, "SYNTHETIC CARD PURCHASE", -800.0),
    ]
    return _statement("Truist Bank", rows, 9000.0, 4900.0)


def _scotiabank_case() -> Statement:
    rows = [
        _txn(2, "SYNTHETIC OPENING ROW", 1000.0, 10000.0),
        _txn(3, "MISC PAYMENT FH SYNTHETIC BILLER", 2500.0, 7500.0),
        _txn(4, "SYNTHETIC DEPOSIT", 500.0, 8000.0),
    ]
    return _statement("Scotiabank", rows, 9000.0, 8000.0)


def _santander_case() -> Statement:
    rows = [
        _txn(2, "SYNTHETIC DEBIT ROW", 1500.0, 48500.0),
        _txn(3, "SYNTHETIC CREDIT ROW", 2000.0, 50500.0),
    ]
    return _statement("Santander Bank", rows, 50000.0, 50500.0)


def test_the_fenced_legacy_repair_retains_its_paired_and_orphan_characterizations():
    assert _declared()["repair_truist_converted_checks"][0] == LEGACY
    paired = _truist_case()
    after = repair_truist_converted_checks(paired)
    assert after is not paired and len(after.transactions) == len(paired.transactions) - 1
    assert after.transactions[0].amount == abs(paired.transactions[0].amount)
    assert restates_a_printed_figure(paired, after)

    orphan = _statement("Truist Bank", [_txn(2, "~CONVERTED CHECK 17", -23.0)], 100.0, 77.0)
    dropped = repair_truist_converted_checks(orphan)
    assert len(orphan.transactions) == 1 and dropped.transactions == []
    assert not restates_a_printed_figure(orphan, dropped)
    unrelated = orphan.model_copy(update={"bank": "SYNTHETIC UNRELATED BANK"})
    assert repair_truist_converted_checks(unrelated) is unrelated


SAFE_CASES = (
    ("repair_scotiabank_misc_payment_sign", repair_scotiabank_misc_payment_sign, _scotiabank_case),
    ("repair_santander_signs_from_balances", repair_santander_signs_from_balances, _santander_case),
)


@pytest.mark.parametrize("name,repair,build", SAFE_CASES, ids=[c[0] for c in SAFE_CASES])
def test_a_safe_normalisation_restates_a_printed_figure_and_never_invents_one(name, repair, build):
    """Mutant P8: a safe normalisation made to write a figure of its own dies
    here. The fixture must also MOVE, or the tripwire would pass on a repair
    that does nothing."""
    assert _declared()[name][0] == SAFE
    before = build()
    after = repair(before)
    assert after is not before and after.transactions != before.transactions, f"{name} did not fire on its fixture"
    assert restates_a_printed_figure(before, after), f"{name} published a figure the paper did not print"


@pytest.mark.parametrize("name,repair,build", SAFE_CASES, ids=[c[0] for c in SAFE_CASES])
def test_a_safe_normalisation_leaves_a_statement_of_another_bank_alone(name, repair, build):
    other = build().model_copy(update={"bank": "SYNTHETIC UNRELATED BANK"})
    assert repair(other) is other


def test_the_unsafe_rewrites_write_a_figure_the_paper_did_not_print():
    """The classification as a MEASURED fact: each of the three produces a
    statement the invention guard refuses, on a fixture built to its own
    gates. Nothing here changes their behaviour — they are recorded, named in
    the W3 with their population, and fenced under Gustavo's ruling."""
    declared = _declared()

    # Capital One: the row's own amount was misread; the two printed balances
    # differ by 2,000.00 and the summary is short by exactly that correction.
    capital_one = _statement("Capital One", [
        _txn(2, "SYNTHETIC ROW ONE", -1000.0, 49000.0),
        _txn(3, "SYNTHETIC ROW TWO", -1000.0, 46000.0),
    ], 50000.0, 46000.0)
    repaired = repair_capital_one_running_amount(capital_one)
    assert repaired.transactions != capital_one.transactions
    assert not restates_a_printed_figure(capital_one, repaired)
    assert declared["repair_capital_one_running_amount"][0] == UNSAFE

    # Chase: an item count fused into the amount's leading digits.
    chase = _statement("Chase", [
        _txn(2, "REMOTE ONLINE DEPOSIT 1", 104098.0),
        _txn(3, "SYNTHETIC CARD PURCHASE", -1000.0),
    ], 50000.0, 53098.0)
    repaired = repair_chase_remote_deposit_count_column(chase)
    assert repaired.transactions != chase.transactions
    assert not restates_a_printed_figure(chase, repaired)
    assert declared["repair_chase_remote_deposit_count_column"][0] == UNSAFE

    # Regions: the one zero-amount card-transaction row filled from the
    # summary shortfall.
    regions = _statement("Regions Bank", [
        _txn(2, "CARD TRANSACTION SYNTHETIC MERCHANT", 0.0),
        _txn(3, "SYNTHETIC DEPOSIT", 1000.0),
    ], 50000.0, 50950.0)
    repaired = repair_regions_transactions("SYNTHETIC LEDGER", regions)
    assert repaired.transactions != regions.transactions
    assert not restates_a_printed_figure(regions, repaired)
    assert declared["repair_regions_transactions"][0] == UNSAFE


# ---------------------------------------------------------------------------
# the stage itself: each shape, claimed by its own registration
# ---------------------------------------------------------------------------

def _claimed(parser_id: str):
    from analysis.parser_registry import Dispatch, by_id

    registration = by_id(parser_id)
    assert registration is not None and registration.id == parser_id
    return Dispatch("claimed", registration=registration)


def _staged(parser_id: str, stmt: Statement, markdown: str = ""):
    """`apply_statement_repairs` exactly as `analyze_markdown` calls it for a
    claimed statement (and for each sibling account), then `reconcile` keyed
    on the same parser."""
    from analysis.pipeline import apply_statement_repairs, normalize_statement
    from analysis.reconcile import reconcile

    staged = apply_statement_repairs(markdown, normalize_statement(stmt), dispatch=_claimed(parser_id))
    return staged, reconcile(staged, parser_id=parser_id)


def _as_printed(stmt: Statement) -> list[tuple]:
    return [(t.date, t.description, round(t.amount, 2), t.direction, t.running_balance) for t in stmt.transactions]


#: (id, claiming registration, the printed statement, does it reconcile as printed?)
#: Each is a shape the fenced repair used to rewrite. The first four did not
#: reconcile as printed and the rewrite made them reconcile; the last two did
#: reconcile, and the rewrite broke them.
STAGE_CASES = (
    # S-1: the paper prints -60.00; the two running balances differ by 50.00,
    # and the summary is short by exactly the difference.
    ("S-1", "capital_one", _statement("Capital One", [
        _txn(2, "SYNTHETIC DEPOSIT", 300.0, 2300.0),
        _txn(3, "SYNTHETIC CARD PURCHASE", -60.0, 2250.0),
    ], 2000.0, 2250.0), False),
    # S-2: a zero-amount card row, and a printed summary 15.00 short.
    ("S-2", "regions", _statement("Regions Bank", [
        _txn(2, "SYNTHETIC DEPOSIT", 200.0),
        _txn(3, "CARD TRANSACTION SYNTHETIC MERCHANT", 0.0),
    ], 2000.0, 2215.0), False),
    # S-3: a deposit genuinely printed as 1,025.00 beside a 1,000.00 debit the
    # reader DROPPED. The rewrite read the deposit as a fused count and wrote
    # 25.00, hiding the missing row and understating deposits.
    ("S-3", "chase", _statement("Chase", [
        _txn(2, "REMOTE ONLINE DEPOSIT 1", 1025.0),
    ], 1000.0, 1025.0), False),
    # S-4: two equal rows in one printed balance step; either flip closes it.
    ("S-4", "rbc", _statement("Royal Bank of Canada", [
        _txn(2, "SYNTHETIC ROW ONE", 25.0),
        _txn(2, "SYNTHETIC ROW TWO", 25.0, 1000.0),
    ], 1000.0, 1000.0), False),
    # S-5: a lone tilde-marked converted check, its own duplicate witness.
    ("S-5 orphan", "truist", _statement("Truist", [
        _txn(5, "~CONVERTED CHECK 1005", -40.0),
    ], 1000.0, 960.0), True),
    # S-5: a debit flipped to a credit on its description alone.
    ("S-5 transfer", "truist", _statement("Truist", [
        _txn(5, "TRUIST ONLINE TRANSFER ONLINE FROM SAMPLE SAVINGS", -40.0),
    ], 1000.0, 960.0), True),
)


@pytest.mark.parametrize("label,parser_id,printed,reconciles", STAGE_CASES, ids=[c[0] for c in STAGE_CASES])
def test_the_repair_stage_publishes_the_fenced_shapes_as_printed(label, parser_id, printed, reconciles):
    """The ruling's effect, through the function the pipeline calls: the
    claiming registration is the repair's own, every gate the old repair had is
    satisfied, and the statement comes back with the rows the paper printed.

    Where the rewrite was the only thing that made the arithmetic close, the
    statement now fails reconciliation, which is the point: the validator
    checks the figures the paper printed, and refuses or routes to review a
    reading that does not close, instead of verifying a figure the rewrite
    supplied."""
    staged, recon = _staged(parser_id, printed)
    assert _as_printed(staged) == _as_printed(printed), label
    assert staged.beginning_balance == printed.beginning_balance
    assert staged.ending_balance == printed.ending_balance
    assert recon.ok is reconciles, (label, recon.issues)


def test_the_s3_dropped_row_is_no_longer_masked():
    """The skeptic's case, named on its own: the genuine deposit is kept at
    its printed figure and the missing debit stays visible as a failed
    reconciliation."""
    staged, recon = _staged("chase", STAGE_CASES[2][2])
    assert [round(t.amount, 2) for t in staged.transactions] == [1025.0]
    assert recon.ok is False

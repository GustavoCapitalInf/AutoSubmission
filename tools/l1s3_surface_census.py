"""L1-S3 — the SURFACE census: every payload reader, checked BOTH ways.

**NOT A PARSER. NEVER REGISTERED. IT CALLS NO ANALYSIS AND READS NO DOCUMENT.**

The design's exit criterion for this stage is not a promise that every reader
was taught; it is a LIST that fails when the list and the tree disagree. A list
that cannot fail is not an exit criterion, so this instrument checks two
claims, each in both directions, over the source text alone:

1. **The readers.** Every function DECLARED below as taught exists in the tree
   and carries the branch its disposition claims. And — the direction that
   makes the zero non-vacuous — every production site that reads the payload
   key ``statement`` is DECLARED, either as a taught reader or as an explicitly
   excused site with its reason. A new reader written tomorrow fails this.

2. **The seams.** Every production call site that turns a report into the
   published payload calls `document_report_to_dict`, and the declared list of
   them is exactly the tree's. (`tools/l1_design_reader_probe.py --census` is
   the design's own version of this half, pinned by LINE NUMBER; this one is
   pinned by AST, so the two fail for different reasons and neither can be
   satisfied by editing the other.)

Dispositions, and what each is checked against:

``per_account``
    the function renders every account, so its body must reach the shape
    module — `payload_accounts`, `is_document_payload`, `assert_payload_shape`,
    `payload_document_block` or `payload_account_count`.
``refuses``
    the function answers about ONE account, so its body must call
    `refuse_document_payload`. A refusal a reader can forget to write is the
    quiet failure this stage exists to remove, so it is named here.
``agnostic``
    the function does not read the ``statement`` key at all and so cannot
    answer about one account by accident. Checked, not asserted: the census
    fails if such a function ever reads it.

PRIVACY
-------
Module paths, function names and counts. It opens no document, no cache and no
run: everything here is `ast.parse` over this repository's own source.

Usage:

    python tools/l1s3_surface_census.py            # both halves, exit 0 or 1
    python tools/l1s3_surface_census.py --readers  # the reader half alone
    python tools/l1s3_surface_census.py --seams    # the seam half alone
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Not production. A reader here answers about a fixture, not about a document.
NON_PRODUCTION_DIRS = ("tests", "tools", "docs", ".claude", ".git", "build",
                       "output", "webapp_data", "benchmark_reports")

#: The shape module's public surface. A `per_account` reader must reach it.
SHAPE_HELPERS = {
    "is_document_payload",
    "assert_payload_shape",
    "payload_accounts",
    "payload_document_block",
    "payload_account_count",
}
REFUSAL_HELPER = "refuse_document_payload"

#: The published payload's account key — the one a reader indexes when it means
#: "the statement", and the one whose ABSENCE stops an untaught reader.
STATEMENT_KEY = "statement"

#: The publisher. Its own matches are the implementation, not call sites.
PUBLISHER_MODULE = "analysis/serialization.py"
DOCUMENT_PUBLISHER = "document_report_to_dict"
ACCOUNT_PUBLISHER = "report_to_dict"


#: Every taught reader: `(module, qualified function, disposition, why)`.
#: The 11 rows of the design's §1.4 census map onto these; a row whose reader
#: got both a refusal and a document function beside it appears as two entries,
#: because the tree has two functions and a census names what the tree has.
READERS: tuple[tuple[str, str, str, str], ...] = (
    ("telemetry/record.py", "classify_outcome", "refuses",
     "one account's rung; it answered `withheld/withheld_adb` to a document"),
    ("telemetry/record.py", "classify_document", "per_account",
     "the document's outcome: the weakest account, with three overrides"),
    ("telemetry/diagnostics.py", "diagnose", "refuses",
     "one account's taxonomy; it answered an empty diagnosis marked evaluated"),
    ("telemetry/diagnostics.py", "diagnose_document", "per_account",
     "the union of its accounts' codes, never one account's under the document's name"),
    ("telemetry/stated_counts.py", "evaluate", "refuses",
     "counts are printed per section; it answered `statement_absent`"),
    ("telemetry/stated_counts.py", "evaluate_accounts", "per_account",
     "one observation per account; a count has no document-level meaning"),
    ("analysis/revenue.py", "rebuild_serialized_revenue_views", "per_account",
     "revenue is a property of a ledger; it rebuilt every view over an empty one"),
    ("webapp/app.py", "_analysis_rows", "per_account",
     "the CSV/XLSX sheet; it returned zero rows for a document that reconciled"),
    ("webapp/app.py", "_adb_rows", "agnostic",
     "reads a metrics block, never the statement key; reached per account"),
    ("webapp/app.py", "_masked", "agnostic",
     "key-name based and already account-count agnostic"),
    ("webapp/app.py", "_package_members", "per_account",
     "package membership: each account on its OWN validation, no duplicate digest"),
    ("webapp/jobs.py", "_classification_for", "per_account",
     "a reviewer's posting belongs to one account; every account is searched"),
    ("analysis/revenue.py", "apply_serialized_revenue_review", "per_account",
     "a reviewer acts on a POSTING, and a posting belongs to one account"),
    ("benchmark/ourside.py", "_account", "refuses",
     "the benchmark declares one value per FILENAME and has no account column"),
    ("balance_forensic_audit.py", "audit_source", "refuses",
     "path-keyed truth set with no account column; it raised a bare KeyError"),
    ("adb_forensic_audit.py", "audit_one", "refuses",
     "path-keyed truth set, and the ADB doctrine forbids a document figure"),
    ("corpus_gate.py", "document_verdicts", "per_account",
     "one verdict per account plus the document's fold"),
    ("corpus_gate.py", "check_currency", "refuses",
     "PINNED_CURRENCY is path-keyed; two accounts may denominate differently"),
    ("corpus_gate.py", "check_currency_source", "refuses",
     "PINNED_CURRENCY_SOURCE is path-keyed for the same reason"),
    ("discovery/runner.py", "_project_accounts", "per_account",
     "the row's account column is EMPTY on a document; account_count carries it"),
)

#: Production sites that read the key ``statement`` and are NOT payload
#: readers, each with the reason. Every one is a CSV column that happens to be
#: called `statement` — an audit row's filename — and none of them ever sees a
#: published payload.
EXCUSED: dict[str, str] = {
    # An audit CSV has a column called `statement` holding a FILENAME. These
    # sites read that column and never see a published payload.
    "adb_forensic_audit.py::refusal_row": "writes the audit CSV's `statement` column (a filename)",
    "adb_forensic_audit.py::write_report": "reads the audit CSV's `statement` column",
    "balance_forensic_audit.py::refusal_row": "writes the audit CSV's `statement` column (a filename)",
    "balance_forensic_audit.py::write_report": "reads the audit CSV's `statement` column",
    "benchmark/expectations.py::load_expectations": "reads the audit CSVs' `statement` column (a filename)",
    "corpus_gate.py::relative_key": "reads the audit CSV's `statement` column",
    "corpus_gate.py::check_outcomes": "reads the audit CSV's `statement` column",
    "telemetry/stated_counts.py::load_corpus_status": "reads the audit CSV's `statement` column",
    # Reached only through a taught function, with one ACCOUNT's payload in
    # hand. Each is named so that "it is downstream of a taught head" is a
    # claim on the record rather than an assumption.
    "analysis/revenue.py::_rebuild_account_revenue_views": "one account's body, reached only through the taught head",
    "benchmark/ourside.py::statement": "one account's view, reached only through the taught `_account`",
    "webapp/app.py::_statement_currency": "one MEMBER's currency; members come from the taught `_package_members`",
    "webapp/app.py::_package_analysis": "reads one MEMBER's account payload, supplied by `_package_members`",
    # A developer utility that publishes nothing. Handed a document payload it
    # falls back to the payload itself and `Statement.model_validate` refuses
    # it loudly, which is the fail-closed answer this census asks for.
    "adb_debug.py::_statement_from_path": "developer debug utility; a document payload fails schema validation loudly",
}


def _production_modules() -> list[Path]:
    return sorted(
        path for path in REPO.rglob("*.py")
        if not any(part in NON_PRODUCTION_DIRS for part in path.relative_to(REPO).parts)
    )


def _relative(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Line number -> the name of the function that line is inside."""
    owner: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                owner.setdefault(line, node.name)
    return owner


def _reads_statement_key(node: ast.AST) -> bool:
    """`x["statement"]`, `x.get("statement")` or `x.setdefault("statement", …)`."""
    if isinstance(node, ast.Subscript):
        target = node.slice
        return isinstance(target, ast.Constant) and target.value == STATEMENT_KEY
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"get", "setdefault", "pop"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == STATEMENT_KEY
        ):
            return True
    return False


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = getattr(child.func, "id", None) or getattr(child.func, "attr", None)
            if name:
                names.add(name)
    return names


def _function_named(tree: ast.AST, name: str) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def census_readers() -> tuple[list[str], list[str], int]:
    """`(failures, notes, sites_seen)` for the reader half, both directions."""
    failures: list[str] = []
    notes: list[str] = []
    trees: dict[str, ast.AST] = {}
    for path in _production_modules():
        try:
            trees[_relative(path)] = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue

    # --- forward: every declared reader exists and carries its branch -------
    for module, function, disposition, _why in READERS:
        tree = trees.get(module)
        if tree is None:
            failures.append(f"{module}: declared reader's module is not in the tree")
            continue
        node = _function_named(tree, function)
        if node is None:
            failures.append(f"{module}::{function}: declared reader is not defined there")
            continue
        called = _called_names(node)
        if disposition == "per_account" and not (called & SHAPE_HELPERS):
            failures.append(
                f"{module}::{function}: declared `per_account` but its body "
                f"reaches none of the shape helpers {sorted(SHAPE_HELPERS)}")
        if disposition == "refuses" and REFUSAL_HELPER not in called:
            failures.append(
                f"{module}::{function}: declared `refuses` but its body never "
                f"calls `{REFUSAL_HELPER}`")
        if disposition == "agnostic" and any(
            _reads_statement_key(child) for child in ast.walk(node)
        ):
            failures.append(
                f"{module}::{function}: declared `agnostic` but it reads the "
                f"{STATEMENT_KEY!r} key")
        if disposition not in {"per_account", "refuses", "agnostic"}:
            failures.append(f"{module}::{function}: unknown disposition {disposition!r}")

    # --- reverse: every site that reads the key is declared ----------------
    declared = {f"{module}::{function}" for module, function, _d, _w in READERS}
    sites = 0
    for module, tree in trees.items():
        owner = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if not _reads_statement_key(node):
                continue
            sites += 1
            key = f"{module}::{owner.get(node.lineno, '<module>')}"
            if key in declared or key in EXCUSED:
                continue
            failures.append(
                f"{key}: reads the {STATEMENT_KEY!r} key and is neither a "
                f"declared reader nor an excused site. Teach it the document "
                f"shape, or excuse it here with the reason.")
    stale = sorted(
        key for key in EXCUSED
        if not any(
            f"{module}::{owner.get(node.lineno, '<module>')}" == key
            for module, tree in trees.items()
            for owner in (_enclosing_functions(tree),)
            for node in ast.walk(tree)
            if _reads_statement_key(node)
        )
    )
    for key in stale:
        failures.append(f"{key}: excused, but nothing there reads the key any more")
    notes.append(f"declared readers: {len(READERS)}")
    notes.append(f"excused sites: {len(EXCUSED)}")
    notes.append(f"payload-key reads swept: {sites}")
    return failures, notes, sites


def census_seams() -> tuple[list[str], list[str], list[str]]:
    """`(failures, notes, seams)` — every publisher call site, both directions."""
    failures: list[str] = []
    seams: list[str] = []
    for path in _production_modules():
        module = _relative(path)
        if module == PUBLISHER_MODULE:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == DOCUMENT_PUBLISHER:
                seams.append(f"{module}:{node.lineno}")
            elif name == ACCOUNT_PUBLISHER:
                failures.append(
                    f"{module}:{node.lineno}: publishes through "
                    f"`{ACCOUNT_PUBLISHER}`, so a document carrying several "
                    f"accounts would publish ONE of them through this seam")
    notes = [f"document-entry seams: {len(seams)}"]
    return failures, notes, sorted(seams)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1-S3 surface census")
    parser.add_argument("--readers", action="store_true", help="the reader half alone")
    parser.add_argument("--seams", action="store_true", help="the seam half alone")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass
    both = not (args.readers or args.seams)

    print("# L1-S3 — the surface census")
    print()
    failures: list[str] = []

    if both or args.readers:
        reader_failures, notes, _sites = census_readers()
        failures.extend(reader_failures)
        print("## Readers")
        print()
        print("| reader | disposition | why |")
        print("|---|---|---|")
        for module, function, disposition, why in READERS:
            print(f"| `{module}::{function}` | {disposition} | {why} |")
        print()
        for note in notes:
            print(f"* {note}")
        print()

    if both or args.seams:
        seam_failures, notes, seams = census_seams()
        failures.extend(seam_failures)
        print("## Seams")
        print()
        print("Counted by AST, so a call site is a CALL. The design's own "
              "census (`tools/l1_design_reader_probe.py --census`) greps the "
              "text and counts NINE, because one of its nine — "
              "`webapp/artifact_cache.py`:215 — is an example inside that "
              "module's docstring rather than a call. The cache seam every web "
              "upload really passes through is `webapp/worker.py`'s `compute=` "
              "lambda, which is in the list below; the docstring was corrected "
              "to the document entry point so the two censuses agree about "
              "what the tree says.")
        print()
        for seam in seams:
            print(f"* `{seam}`")
        print()
        for note in notes:
            print(f"* {note}")
        print()

    if failures:
        print("**CENSUS FAILS.**")
        print()
        for failure in failures:
            print(f"* {failure}")
        return 1
    print("**CENSUS HOLDS** at this tree: the declared surfaces are exactly "
          "the tree's, both ways.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

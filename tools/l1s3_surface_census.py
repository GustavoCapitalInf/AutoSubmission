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

#: The DOCUMENT shape's own key. The L1-S3 review's MAJOR-1: the first version
#: of this census swept only `statement`, so the most natural new reader — one
#: that reaches straight for `accounts` — was invisible to the direction that
#: makes "every reader is taught" falsifiable. S4 is the stage that writes
#: exactly those readers.
ACCOUNTS_KEY = "accounts"

#: Both published keys. A read of either is a payload read.
PAYLOAD_KEYS = (STATEMENT_KEY, ACCOUNTS_KEY)

#: The publisher. Its own matches are the implementation, not call sites.
PUBLISHER_MODULE = "analysis/serialization.py"

#: How many times the publisher module calls the ACCOUNT publisher inside
#: itself. Exactly two, and both inside `document_report_to_dict`: RULE S's
#: verbatim single-account return, and the per-account list comprehension.
#:
#: The L1-S3 review's MINOR-9: both censuses skip this module wholesale, which
#: is right — the module that DEFINES the publisher is not one of its call
#: sites — but wholesale meant a NEW single-account publish added inside it
#: would be invisible to both. Pinning the count is what makes the exclusion
#: narrow instead of blind: a third internal publish fails this census, and the
#: implementer has to say which of the two it is.
PUBLISHER_INTERNAL_ACCOUNT_CALLS = 2
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
    ("analysis/revenue.py", "record_serialized_revenue_review", "per_account",
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
    ("vlm/truth.py", "truth_from_payload", "per_account",
     "the Phase 3 comparison reads every cached account through payload_accounts"),
    ("webapp/worker.py", "_attach_account_confidence", "per_account",
     "each published account takes its own verification score, found through payload_accounts"),
    ("analysis/flagged_view.py", "apply_flagged_groups_to_payload", "per_account",
     "the flag groups are served per account ledger; every account is tagged, a malformed document passes untouched"),
    ("analysis/nsf_days.py", "apply_nsf_basis_to_payload", "per_account",
     "the NSF basis is a property of one account's ledger; every account is re-based, a malformed document passes untouched"),
    ("webapp/reanalysis.py", "replay_reviews", "per_account",
     "a decision names one posting of one account; every account is searched through payload_accounts"),
    ("analysis/revenue_view.py", "apply_revenue_view", "per_account",
     "the revenue flags and an older payload's nulled True revenue are served per account ledger; every account is "
     "shown, a malformed document passes untouched"),
    # Audit B11 (true revenue §9.2, §10.4, §10.8).
    ("webapp/app.py", "_stored_accounts", "per_account",
     "a package job's accounts for its duplicate test (I06): every account of a document, through payload_accounts"),
    ("webapp/app.py", "_posted_credit_table", "per_account",
     "the downloads' posted-credit table (I32): one block per account, under its section prefix"),
    ("webapp/app.py", "_export_revenue_view", "per_account",
     "the downloads' N/A rule (I51): every account's figures follow its own revenue flags"),
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue R2-OW17): the Zelle setting's readings.
    ("analysis/zelle_view.py", "reading", "per_account",
     "the Zelle reading is a property of one account's ledger; every account is materialised in the chosen reading, a "
     "malformed document passes untouched"),
    ("analysis/zelle_view.py", "apply_zelle_view", "per_account",
     "the Zelle figures and row tags are served per account ledger; every account is shown in the chosen reading, a "
     "malformed document passes untouched"),
    ("analysis/zelle_view.py", "with_both_readings", "per_account",
     "a reviewer's decision names one posting of one account, written in both readings; each account keeps its own "
     "edits, a malformed document takes today's path"),
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
    # Owner ruling 2026-10-02 (the underwriter's Q6; R2-OW15): the package passes read the same members.
    "webapp/app.py::_package_matches": "reads each MEMBER's account payload, supplied by `_package_members`",
    # The owner's request of 2026-10-06 (lender payment changes; R2-OW18): the package's chains read the same members.
    "webapp/app.py::_package_lender_payment_changes": "reads each MEMBER's account payload, supplied by "
                                                      "`_package_members`",
    # Audit B11 (I06): one ACCOUNT's statement identity, and a left-out job's identifying fields from the first
    # account; each is handed its account by the taught `_stored_accounts`.
    "webapp/app.py::_account_identities": "one ACCOUNT's identity; `_stored_accounts` hands it each account",
    "webapp/app.py::_duplicate_row": "a left-out job's identifying fields, from the first account `_stored_accounts` lists",
    "webapp/reanalysis.py::_records": "one ACCOUNT's records; `replay_reviews` hands it each account from `payload_accounts`",
    "analysis/nsf_days.py::_rebased_account": "one ACCOUNT's ledger and postings; `apply_nsf_basis_to_payload` hands it each account from `payload_accounts`",
    "analysis/revenue_view.py::_served_account": "one ACCOUNT's revenue view; `apply_revenue_view` hands it each account from `payload_accounts`",
    "analysis/revenue_view.py::revenue_flags": "one ACCOUNT's revenue flags; reached through `_served_account` with that account in hand",
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (true revenue R2-OW17): one ACCOUNT's Zelle rows and
    # served view, each handed its account by the taught `apply_zelle_view` (and `zelle_rows` by it too).
    "analysis/zelle_view.py::_posted_credits": "one ACCOUNT's posted credits; `zelle_rows` reads them for each account `apply_zelle_view` hands it from `payload_accounts`",
    "analysis/zelle_view.py::_view_account": "one ACCOUNT's served Zelle view; `apply_zelle_view` hands it each account from `payload_accounts`",
    # Audit round 2, R2-B14 (R16, R46, R14) and R2-OW17: package and copy readers handed one ACCOUNT by the taught
    # `_stored_accounts`.
    "webapp/app.py::_copy_rank": "a copy's accounts, read through the taught `_stored_accounts` in both Zelle readings (R2-OW17)",
    "webapp/app.py::_printed_account_digits": "one ACCOUNT's printed number; its callers hand it accounts `_stored_accounts` lists or members `_package_members` publishes",
    "webapp/app.py::_statement_span": "one ACCOUNT's period; `_package_superseded` hands it accounts `_stored_accounts` lists",
    "webapp/app.py::_posted_rows": "one ACCOUNT's posted rows; `_package_superseded` hands it accounts `_stored_accounts` lists",
    "webapp/app.py::_package_superseded": "reads each kept job's accounts through the taught `_stored_accounts`; its `accounts` key is its own entry's account count, not a payload",
    # A developer utility that publishes nothing. Handed a document payload it
    # falls back to the payload itself and `Statement.model_validate` refuses
    # it loudly, which is the fail-closed answer this census asks for.
    "adb_debug.py::_statement_from_path": "developer debug utility; a document payload fails schema validation loudly",
    # --- reached by the widened sweep (L1-S3 review, MAJOR-1) --------------
    # The DOCUMENT OBJECT reading its own account list. `DocumentReport` is the
    # object that holds several accounts, so iterating `document.accounts` is
    # what it is FOR — it is not a reader reaching one account out of something
    # it mistook for one account, which is the hazard this census exists for.
    "analysis/pipeline.py::document_scope_flags": "the document OBJECT's view over its own accounts",
    "analysis/serialization.py::document_report_to_dict": "the PUBLISHER assembling the account list it publishes",
    "analysis/serialization.py::_document_block": "the PUBLISHER assembling the document's own block from the document OBJECT",
    # The gate's own per-account assertions, which are HANDED the account list
    # by `document_verdicts` — the taught reader above them — and walk it to
    # check every account rather than to answer about one.
    "corpus_gate.py::_assert_document_facts": "the gate walking EVERY account it was handed, to assert a property of each",
    "analysis/serialization.py::_publishes_todays_payload": "RULE S counting the document object's own accounts",
    "analyze.py::main": "the CLI iterating the document object to render EVERY account",
    "batch.py::main": "the batch CLI iterating the document object to emit one row per account",
    # The accessor every taught reader goes through. Excusing it is not a hole:
    # a reader that calls it is declared `per_account` by the forward check,
    # which is exactly what calling it means.
    "analysis/payload_shape.py::payload_accounts": "the shared accessor the taught readers reach the accounts through",
    # NOT our payload. `benchmark/normalize.py` parses MoneyThumb's scorecard
    # JSON, whose own schema has an `accounts` key; it never sees a payload
    # this platform publishes. Measured by the reviewer and re-measured here.
    "benchmark/normalize.py::lenders": "reads MoneyThumb's scorecard JSON, whose schema has its own `accounts` key",
    # --- L1-S4: the publisher's own objects, which are not payloads ---------
    # `DocumentPartition.accounts` is a tuple of `PublishedAccount` OBJECTS
    # holding `Statement` instances, read INSIDE the module that defines them
    # and before anything is serialised. There is no payload here to answer
    # about one account of: the hazard this census exists for is a reader
    # handed a published dict, and this is a reader handed its own dataclass.
    "analysis/multi_account.py::published_statement": "the partition object reading its own account list; no payload exists yet",
    # The DOCUMENT entry point building one report per account of the partition
    # a reader established. Same fact as `document_scope_flags` above: the
    # object that HOLDS several accounts iterating them is what it is for.
    "analysis/pipeline.py::analyze_document": "the document entry point iterating the partition it is building the document from",
    "analysis/pipeline.py::_analyse": "the analysis reading the partition a reader published; `Report` objects, not a payload",
    # The ACCOUNT entry point taking the FIRST report out of the internal
    # `_Analysed` object. This is the one excusal a reviewer should press on,
    # so it says exactly what it is: `analyze_markdown`'s contract is ONE
    # ACCOUNT and has been since the schema existed, and the object it reads is
    # this module's own dataclass of `Report`s — never a published payload, and
    # never something it mistook for one account. A caller that wants the
    # document asks `analyze_document`, which is why every production seam does.
    "analysis/pipeline.py::analyze_markdown": "the ACCOUNT entry point returning the first Report of the internal _Analysed object",
    # Phase 3.1 builds sources before publication. Both bridges explicitly
    # refuse anything other than one account, and the final guard inspects
    # every report. These objects are not a serialized published payload.
    "vlm/currency.py::resolve_currency": "unpublished DocumentReport bridge; refuses multiple accounts or omitted siblings before source equality",
    "vlm/pair_adapter.py::analyze_visual_pair": "private source audit and unpublished DocumentReport bridge; refuses multiple accounts or omitted siblings",
    "vlm/pair_adapter.py::_complete_report": "checks the daily ledger validity of EVERY account in the unpublished DocumentReport",
    # The visual pair's account-by-account judgement (vlm/pair_accounts.py) is private evidence: its `accounts` list
    # and each entry's `statement` SOURCE exist before anything is analysed or published.
    "vlm/pair.py::extract_visual_pair": "reads the visual pair's private per-account judgement (`accounts`, each entry's `statement` source); no payload exists yet",
    "vlm/pair_adapter.py::_analyze_accounts": "builds one Report per verified account from the private per-account evidence (`accounts`, each `statement` source); refuses anything else",
    "webapp/worker.py::_visual_pair_summary_html": "renders the visual pair's private per-account evidence (`accounts`) into the review page; not a published payload",
    # The widened AST predicate also sees a method named `accounts`. Here it
    # is ReaderTruth.accounts(sha), which returns the complete comparison list
    # from the per-account reader declared above, not document.accounts[0].
    "vlm/runner.py::process_document": "comparison harness calls ReaderTruth.accounts(sha), not a payload or document account attribute",
    "vlm/regate.py::regate_wave": "offline regating calls ReaderTruth.accounts(sha), not a payload or document account attribute",
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


def _key_aliases(tree: ast.AST) -> set[str]:
    """Names bound to one of the payload keys — `_KEY = "statement"`.

    The review's fourth scratch reader indexed the swept key THROUGH A NAME and
    was invisible. Collecting the bindings first is what makes a non-literal
    subscript readable without flagging every `rows[i]` in the repository:
    only a subscript whose key is one of THESE names counts.
    """
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if not isinstance(value, ast.Constant) or value.value not in PAYLOAD_KEYS:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _reads_payload_key(node: ast.AST, aliases: frozenset[str] = frozenset()) -> bool:
    """Every mechanical way a reader reaches one account out of a payload.

    Five shapes, and the last four are the L1-S3 review's MAJOR-1 — it wrote
    seven readers none of which this predicate saw, and the census stayed
    exit 0 with all seven in the tree:

    * `x["statement"]` / `x["accounts"]`, and `.get` / `.setdefault` / `.pop`
      of either — the original three;
    * a subscript whose key is a NAME bound to one of those constants;
    * a comparison against one of them, which is how a `.items()` walk picks a
      key out of a payload it is iterating;
    * attribute access `.accounts`, which is how the DOCUMENT OBJECT is read.
      `.statement` is deliberately NOT swept: a `Report` IS one account by
      construction, so reading its statement is not a document-shape hazard —
      the hazard is reaching one account out of something that holds several,
      and that is `.accounts`.
    """
    if isinstance(node, ast.Subscript):
        target = node.slice
        if isinstance(target, ast.Constant) and target.value in PAYLOAD_KEYS:
            return True
        return isinstance(target, ast.Name) and target.id in aliases
    if isinstance(node, ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in {"get", "setdefault", "pop"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in PAYLOAD_KEYS
        ):
            return True
        return False
    if isinstance(node, ast.Compare):
        operands = [node.left, *node.comparators]
        return any(
            isinstance(operand, ast.Constant) and operand.value in PAYLOAD_KEYS
            for operand in operands
        )
    if isinstance(node, ast.Attribute):
        return node.attr == ACCOUNTS_KEY
    return False


#: Kept as the old name for the `agnostic` check, which asks a narrower
#: question: does this function read the ACCOUNT key at all?
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


def _is_constant_false(test: ast.AST) -> bool:
    """`if False:` — and `if False and <anything>:`, which is the same branch."""
    if isinstance(test, ast.Constant):
        return not bool(test.value)
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return any(_is_constant_false(value) for value in test.values)
    return False


def _called_names(node: ast.AST) -> set[str]:
    """Every name CALLED in this function, skipping constant-dead branches.

    The L1-S3 review's MINOR-3: this was `ast.walk` with no reachability at
    all, so a `refuses` reader satisfied the census with its refusal moved
    into `if False:` — proved on all eight refusal sites, census exit 0 at
    every one. A declaration that dead code satisfies is a name check wearing a
    behaviour check's clothes.

    Reachability in general is undecidable; a CONSTANT-false branch is not, it
    is the mutation an implementer actually writes, and it is what this skips.
    The per-reader tests remain what proves a refusal FIRES — this only stops
    the census from agreeing with a mutant.
    """
    names: set[str] = set()

    def walk(current: ast.AST) -> None:
        for child in ast.iter_child_nodes(current):
            if isinstance(child, ast.If) and _is_constant_false(child.test):
                for node in child.orelse:
                    walk(node)
                continue
            if isinstance(child, ast.While) and _is_constant_false(child.test):
                continue
            if isinstance(child, ast.Call):
                name = (getattr(child.func, "id", None)
                        or getattr(child.func, "attr", None))
                if name:
                    names.add(name)
            walk(child)

    walk(node)
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

    # --- reverse: every site that reads a payload key is declared ----------
    declared = {f"{module}::{function}" for module, function, _d, _w in READERS}
    sites = 0
    seen_sites: set[str] = set()
    for module, tree in trees.items():
        owner = _enclosing_functions(tree)
        aliases = frozenset(_key_aliases(tree))
        for node in ast.walk(tree):
            if not _reads_payload_key(node, aliases):
                continue
            sites += 1
            key = f"{module}::{owner.get(node.lineno, '<module>')}"
            seen_sites.add(key)
            if key in declared or key in EXCUSED:
                continue
            failures.append(
                f"{key}: reads a published payload key and is neither a "
                f"declared reader nor an excused site. Teach it the document "
                f"shape, or excuse it here with the reason.")
    stale = sorted(key for key in EXCUSED if key not in seen_sites)
    for key in stale:
        failures.append(f"{key}: excused, but nothing there reads the key any more")
    notes.append(f"declared readers: {len(READERS)}")
    notes.append(f"excused sites: {len(EXCUSED)}")
    notes.append(f"payload-key reads swept: {sites}")
    return failures, notes, sites


def _publisher_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """`(document publisher names, account publisher names)` in this module.

    Both include every ALIAS the module imported them under. The L1-S3
    review's MAJOR-1 imported the account publisher as
    `report_to_dict as _publish_one_account` and both censuses missed it: the
    AST one matched the call NAME, the design's probe grepped the text
    `report_to_dict(`, and an alias defeats each. An alias is one line and it
    is exactly what a reader writes when it wants a shorter name.
    """
    document = {DOCUMENT_PUBLISHER}
    account = {ACCOUNT_PUBLISHER}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if alias.asname is None:
                continue
            if alias.name == DOCUMENT_PUBLISHER:
                document.add(alias.asname)
            elif alias.name == ACCOUNT_PUBLISHER:
                account.add(alias.asname)
    return document, account


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
        document_names, account_names = _publisher_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in document_names:
                seams.append(f"{module}:{node.lineno}")
            elif name in account_names:
                failures.append(
                    f"{module}:{node.lineno}: publishes through "
                    f"`{ACCOUNT_PUBLISHER}`{'' if name == ACCOUNT_PUBLISHER else f' (aliased as `{name}`)'}, "
                    f"so a document carrying several accounts would publish "
                    f"ONE of them through this seam")
    # MINOR-9: the publisher module is excluded from the sweep above, so its
    # own internal calls are counted here instead of being unseen.
    publisher = REPO / PUBLISHER_MODULE
    internal = 0
    internal_functions: set[str] = set()
    if publisher.is_file():
        tree = ast.parse(publisher.read_text(encoding="utf-8"))
        owner = _enclosing_functions(tree)
        _document_names, account_names = _publisher_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in account_names:
                internal += 1
                internal_functions.add(owner.get(node.lineno, "<module>"))
    if internal != PUBLISHER_INTERNAL_ACCOUNT_CALLS:
        failures.append(
            f"{PUBLISHER_MODULE}: calls `{ACCOUNT_PUBLISHER}` {internal} time(s) "
            f"inside itself; {PUBLISHER_INTERNAL_ACCOUNT_CALLS} are declared "
            f"(RULE S's verbatim return and the per-account list). A new "
            f"single-account publish here is invisible to both censuses "
            f"otherwise — declare it or route it through the document function")
    if internal_functions - {"document_report_to_dict"}:
        failures.append(
            f"{PUBLISHER_MODULE}: the account publisher is called from "
            f"{sorted(internal_functions)}; only `document_report_to_dict` may "
            f"call it")
    notes = [
        f"document-entry seams: {len(seams)}",
        f"account-publisher calls inside {PUBLISHER_MODULE}: {internal} "
        f"(declared {PUBLISHER_INTERNAL_ACCOUNT_CALLS})",
    ]
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

"""OCR-LEGACY-AUDIT's census instrument — STRICTLY READ-ONLY.

WHAT THIS IS
------------
The instrument behind the numbers in
`docs/moneythumb-replacement/OCR_LEGACY_AUDIT.md`. Batch-9 rules: an
instrument that produces a headline number is committed, and every headline
number reproduces from committed evidence. These are those numbers.

READ-ONLY BY CONSTRUCTION
-------------------------
This module opens NOTHING for writing. It has no `open(..., "w")`, no
`Path.write_*`, no `os.replace`, no `shutil`, no `subprocess`, no network
client and no `sys.stdout` sink other than `print`. It:

* reads first-party `*.py` SOURCE TEXT and parses it with `ast` (never
  executing it, never importing it) — the tree census;
* optionally opens a webapp artifact-cache SQLite index with a
  `file:...?mode=ro` URI and reads the `artifact_cache` INDEX TABLE ONLY —
  never an artifact payload, never a page of text, never a PDF.

It therefore CANNOT read a bank statement's content: the index table carries
stage names, cache keys, hashes, byte sizes and timestamps and no document
text at all, and the tree census never leaves `*.py` source. It is also not an
analysis caller — it never imports or invokes `analysis.pipeline`,
`analyze_markdown`, `analyze_document`, `corpus_gate` or `ocr.pipeline` — so
it is deliberately NOT registered in `corpus_gate.EXCLUDED_ANALYSIS_CALLERS`;
that register answers a question this tool does not raise, and appending a key
to a shared surface for a tool that does not need one is a composition
conflict for nothing.

MODES
-----
`--tree` (default)
    For every module of the OCR intake layer and its satellites: line count,
    last commit (date + short sha) and commit count from `git log --follow`,
    every first-party importer split into production / tests / tools /
    scripts, and whether the module is reachable by a transitive first-party
    import walk from a declared PRODUCTION ENTRY POINT. "Reachable" here is
    the audit's `can it reach a production path today` question, computed
    rather than asserted.

`--cache-index <data-dir>`
    Read-only over the artifact-cache INDEX of a webapp data directory. Prints
    per-stage row counts and the multiplicity distribution of `input_sha256`
    inside the `ocr` stage — how many documents hold one OCR artifact, and how
    many hold more than one. That second number is the one the Phase-2
    proposal turns on: `tools/cohort_replay.py::ColdCache._payload` selects
    `rows[0]` with no ORDER BY and no settings-key filter, so a document with
    two OCR partitions is replayed from an arbitrary one of them.

Both modes print counts, paths, module names and hashes' MULTIPLICITY — never
a hash, never a filename from the archive, never a cell.

USAGE
-----
    python tools/ocr_legacy_census.py --tree
    python tools/ocr_legacy_census.py --cache-index .claude/recovery/webapp_data_train8_cold

EXIT CODES
----------
0 — the census ran.
2 — a declared component path does not exist in this tree (a STOP: the
    inventory and the tree have drifted, and a census over a stale inventory
    is worse than none).
"""
from __future__ import annotations

import argparse
import ast
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The audit's declared inventory. Every path the OCR-LEGACY-AUDIT card names,
#: plus the satellites the import census found. Order is the audit document's.
COMPONENTS: tuple[str, ...] = (
    # the intake package
    "ocr/__init__.py",
    "ocr/config.py",
    "ocr/inspect.py",
    "ocr/document.py",
    "ocr/pipeline.py",
    "ocr/native_text.py",
    "ocr/column_grid.py",
    "ocr/local_tesseract.py",
    "ocr/rasterize.py",
    "ocr/ocr_client.py",
    "ocr/availability.py",
    "ocr/truncation.py",
    "ocr/render.py",
    # the vendor-side server and its operator surface
    "local_ocr_server.py",
    # the seam into the canonical statement representation
    "webapp/worker.py",
    "webapp/artifact_cache.py",
    "discovery/runner.py",
    "discovery/cli.py",
    "corpus_artifacts.py",
    "build_corpus_cache.py",
    # legacy / dev-only CLIs from before the deterministic shift
    "parse.py",
    "sweep_ocr.py",
    "triage_scan.py",
    "coverage_audit.py",
    "deterministic_coverage_audit.py",
    "batch.py",
    # geometry: the unwired OCR-word-box seam
    "analysis/structurer/geometry.py",
)

#: What "can reach a production path today" is measured FROM. These are the
#: processes that publish a result a user or a run of record sees: the webapp
#: job worker, the discovery runner and its CLI, the corpus gate, and the two
#: shipped CLIs. `tools/` and `experiments/` are deliberately NOT entry points
#: — reachability from an instrument is not reachability from production, and
#: conflating them is how a spike becomes load-bearing.
PRODUCTION_ENTRY_POINTS: tuple[str, ...] = (
    "webapp/worker.py",
    "webapp/app.py",
    "discovery/cli.py",
    "discovery/runner.py",
    "corpus_gate.py",
    "parse.py",
    "batch.py",
    "analyze.py",
)

#: Directories whose `*.py` files are first-party for the import walk.
FIRST_PARTY_TREES: tuple[str, ...] = (
    "analysis", "ocr", "webapp", "discovery", "telemetry", "benchmark",
    "tools", "experiments", "tests",
)

_SKIP_DIR_PARTS = frozenset({".git", ".claude", "__pycache__", ".venv", ".pytest_cache"})


# ---------------------------------------------------------------------------
# module map
# ---------------------------------------------------------------------------

def _first_party_files() -> list[Path]:
    """Every first-party `*.py`, repo-root modules included."""
    files = [path for path in sorted(ROOT.glob("*.py"))]
    for tree in FIRST_PARTY_TREES:
        base = ROOT / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if _SKIP_DIR_PARTS & set(path.relative_to(ROOT).parts):
                continue
            files.append(path)
    return files


def _module_name(path: Path) -> str:
    rel = path.relative_to(ROOT)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _package_of(path: Path) -> str:
    """The dotted package a relative import inside `path` resolves against."""
    rel = path.relative_to(ROOT)
    parts = list(rel.parts[:-1])
    return ".".join(parts)


def _imports(path: Path, modules: dict[str, Path]) -> set[str]:
    """First-party dotted module names imported by `path`, absolute or relative.

    A dotted target that is not itself a module (``from ocr.pipeline import
    parse_statement``) resolves to the longest prefix that IS one, so an
    imported SYMBOL is attributed to the module that defines it.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()

    found: set[str] = set()

    def resolve(dotted: str) -> None:
        """Attribute a dotted target to the longest prefix that is a module.

        Every PACKAGE prefix on the way is recorded too: importing
        `ocr.pipeline` executes `ocr/__init__.py`, so a census that credited
        only the leaf would report the package as unreachable when it is
        imported by everything.
        """
        parts = dotted.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in modules:
                found.add(candidate)
                prefix = parts[:-1]
                while prefix:
                    package = ".".join(prefix)
                    if package in modules:
                        found.add(package)
                    prefix.pop()
                return
            parts.pop()

    package = _package_of(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolve(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")
                anchor = anchor[: len(anchor) - (node.level - 1)] if node.level > 1 else anchor
                base = ".".join([part for part in anchor if part] + ([base] if base else []))
            if not base:
                continue
            resolve(base)
            for alias in node.names:
                resolve(f"{base}.{alias.name}")
    return found


def _classify(rel: str) -> str:
    if rel.startswith("tests/"):
        return "tests"
    if rel.startswith("tools/"):
        return "tools"
    if rel.startswith("experiments/"):
        return "experiments"
    if "/" in rel:
        return "production"
    return "script"


# ---------------------------------------------------------------------------
# git recency
# ---------------------------------------------------------------------------

def _git(args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _recency(rel: str) -> tuple[str, str, int]:
    """(last date, short sha, commit count) from `git log --follow`."""
    last = _git(["log", "--follow", "-1", "--date=short", "--format=%ad %h", "--", rel])
    count_raw = _git(["log", "--follow", "--format=%h", "--", rel])
    count = len([line for line in count_raw.splitlines() if line.strip()])
    if not last:
        return ("-", "-", count)
    date, _, sha = last.partition(" ")
    return (date, sha.strip(), count)


# ---------------------------------------------------------------------------
# tree census
# ---------------------------------------------------------------------------

def census_tree() -> int:
    missing = [rel for rel in COMPONENTS if not (ROOT / rel).is_file()]
    if missing:
        print("STOP: declared component(s) absent from this tree:")
        for rel in missing:
            print(f"  {rel}")
        return 2

    files = _first_party_files()
    modules = {_module_name(path): path for path in files}
    edges = {_module_name(path): _imports(path, modules) for path in files}

    # transitive reachability from the production entry points
    reachable: set[str] = set()
    stack = [_module_name(ROOT / rel) for rel in PRODUCTION_ENTRY_POINTS
             if (ROOT / rel).is_file()]
    while stack:
        name = stack.pop()
        if name in reachable:
            continue
        reachable.add(name)
        stack.extend(edges.get(name, ()))

    importers: dict[str, list[str]] = {name: [] for name in modules}
    for path in files:
        source = str(path.relative_to(ROOT)).replace("\\", "/")
        for target in edges[_module_name(path)]:
            if target in importers:
                importers[target].append(source)

    print(f"OCR LEGACY CENSUS - tree at {_git(['rev-parse', '--short', 'HEAD']) or '?'}")
    print(f"first-party modules scanned: {len(modules)}")
    print(f"production entry points: {len(PRODUCTION_ENTRY_POINTS)}; "
          f"modules reachable from them: {len(reachable)}")
    print("")
    header = (f"{'component':38} {'loc':>5} {'last':>10} {'sha':>9} {'cmts':>5} "
              f"{'prod':>5} {'test':>5} {'tool':>5} {'reach':>6}")
    print(header)
    print("-" * len(header))
    for rel in COMPONENTS:
        path = ROOT / rel
        name = _module_name(path)
        loc = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        date, sha, count = _recency(rel)
        kinds = Counter(_classify(source) for source in importers.get(name, []))
        prod = kinds["production"] + kinds["script"]
        print(f"{rel:38} {loc:5d} {date:>10} {sha:>9} {count:5d} "
              f"{prod:5d} {kinds['tests']:5d} {kinds['tools']:5d} "
              f"{('yes' if name in reachable else 'NO'):>6}")
    print("")
    print("IMPORTERS, per component (first-party only; '-' = none)")
    for rel in COMPONENTS:
        name = _module_name(ROOT / rel)
        sources = sorted(set(importers.get(name, ())))
        print(f"  {rel}")
        if not sources:
            print("    -")
            continue
        for source in sources:
            print(f"    {_classify(source):11} {source}")
    return 0


# ---------------------------------------------------------------------------
# cache-index census
# ---------------------------------------------------------------------------

def census_cache_index(data_dir: Path) -> int:
    db = data_dir / "webapp.db"
    if not db.is_file():
        print(f"STOP: no artifact-cache index at {db}")
        return 2
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        print(f"ARTIFACT-CACHE INDEX CENSUS (read-only) - {data_dir}")
        print("index table only; no artifact payload, page or PDF is opened.")
        print("")
        rows = conn.execute(
            "SELECT stage, COUNT(*), COUNT(DISTINCT input_sha256), "
            "COUNT(DISTINCT settings_key) FROM artifact_cache GROUP BY stage "
            "ORDER BY stage"
        ).fetchall()
        print(f"{'stage':12} {'rows':>8} {'distinct inputs':>16} {'distinct settings':>18}")
        for stage, total, inputs, settings in rows:
            print(f"{str(stage):12} {total:8d} {inputs:16d} {settings:18d}")
        print("")
        for stage, *_ in rows:
            counts = Counter(
                count for (count,) in conn.execute(
                    "SELECT COUNT(*) FROM artifact_cache WHERE stage = ? "
                    "GROUP BY input_sha256", (stage,)
                )
            )
            multi = sum(n for k, n in counts.items() if k > 1)
            print(f"stage {stage!r}: artifacts per input -> "
                  + ", ".join(f"{k}x:{n}" for k, n in sorted(counts.items())))
            print(f"  inputs holding MORE THAN ONE artifact in this stage: {multi}")
            if stage == "ocr":
                print("  (cohort_replay's ColdCache._payload takes rows[0] with no "
                      "ORDER BY and no settings-key filter; >0 here means an "
                      "ambiguous replay source.)")
        return 0
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="READ-ONLY census for OCR-LEGACY-AUDIT. Writes nothing.")
    parser.add_argument("--tree", action="store_true",
                        help="census the OCR component inventory (default)")
    parser.add_argument("--cache-index", type=Path, default=None,
                        help="a webapp data directory; reads its SQLite INDEX only")
    args = parser.parse_args(argv)

    if args.cache_index is not None:
        return census_cache_index(args.cache_index)
    return census_tree()


if __name__ == "__main__":
    sys.exit(main())

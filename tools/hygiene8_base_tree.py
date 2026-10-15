"""Materialise a second, BASE copy of `analysis/` from git blobs, importable
alongside the working tree's, so one process can answer base-vs-branch.

#HYGIENE8. The three sub-cards this branch landed are declared non-outcome
changes, and "non-outcome" is a claim about what a document's published payload
does. The only honest way to check it is to analyse the same text twice in the
same interpreter — same pydantic, same registry construction order, same
floating point — and compare the two payloads leaf for leaf. Two processes
comparing two JSON files would also prove it, but it would prove it about two
interpreters, and every difference in the environment would have to be argued
away rather than eliminated.

WHY THIS IS SAFE, and it is a property of the package rather than a hope:
`analysis/` imports nothing from this repository outside itself. Every
non-relative import in the package is stdlib or third-party (measured:
`dotenv`, `google.genai`, `pydantic` and stdlib; `google.genai` left with
`analysis/extract.py` in slice S3 of the model-code removal), so a copy of the directory
under a DIFFERENT package name is an entire second analysis stack, consistent
with itself. Relative imports (`from .money import ...`) resolve to whatever package
the module actually lives in, which is the whole mechanism.

ONE MODULE IS NOT THE BASE'S (model-code removal, slice S6): a base revision
from before slice S3 holds `analysis/extract.py`, the hosted extractor, which
imports the extraction SDK (`google.genai`) at module level, and its
`analysis/pipeline.py` imports `extract_statement` from it. The SDK is no longer
installed anywhere (CI included) and the product uses no model, so the base
copy's `extract` module is a stand-in whose `extract_statement` refuses every
call (`RETIRED_EXTRACTOR`). Nothing compared here reaches it: the comparisons
drive deterministic parser and analysis paths only, and an extraction would
have refused anyway with no key. Every other base blob runs byte for byte.

    from tools.hygiene8_base_tree import load_base_analysis
    base = load_base_analysis("10cc722", repo=Path.cwd(), scratch=scratch)
    payload = base.report_to_dict(
        base.analyze_markdown(markdown, parse_mode="deterministic", sheets=pages))

READ-ONLY against the repository: the blobs come from `git archive`, which
reads the object store and writes nothing, and the copy is written to a
scratchpad outside the checkout. The working tree is never modified, so this
helper is safe to run beside a clean-tree rule.

The two stacks never share an object. `report_to_dict` is taken from the SAME
package as `analyze_markdown`, so a base `Statement` is serialised by base code
and a branch `Statement` by branch code; nothing is compared as an object and
nothing is passed across. What is compared is the two `dict`s.
"""
from __future__ import annotations

import importlib
import io
import shutil
import subprocess
import sys
import tarfile
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

#: What the stand-in for a base revision's hosted extractor raises (see the module docstring).
RETIRED_EXTRACTOR = (
    "the hosted extractor was removed (model-code removal): a base tree's extract_statement cannot run"
)


def _retired_extractor(package: str) -> types.ModuleType:
    """`<package>.extract` for a base copy: the one name its pipeline imports, refusing every call."""
    module = types.ModuleType(f"{package}.extract", RETIRED_EXTRACTOR)

    def extract_statement(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(RETIRED_EXTRACTOR)

    module.extract_statement = extract_statement
    return module


@dataclass(frozen=True)
class BaseAnalysis:
    """The base tree's analysis entry points, and the name they live under."""

    package: str
    revision: str
    analyze_markdown: Callable[..., Any]
    report_to_dict: Callable[..., Any]
    module: Any


def _extract(repo: Path, revision: str, destination: Path) -> None:
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", revision, "analysis"],
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as handle:
        handle.extractall(destination)


def load_base_analysis(revision: str, *, repo: Path, scratch: Path) -> BaseAnalysis:
    """Import `analysis/` as it stood at `revision`, under an alias package.

    The alias carries the resolved commit so two revisions can be loaded in one
    process and neither can be mistaken for the other in a traceback.
    """
    resolved = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", revision],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    package = f"analysis_base_{resolved[:8]}"
    root = scratch / f"basetree_{resolved[:8]}"
    target = root / package
    if not target.is_dir():
        tmp_dir = root / "_tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        _extract(repo, resolved, tmp_dir)
        # The directory is renamed rather than the imports rewritten: a package
        # named `analysis_base_<sha>` whose modules say `from .money import ...`
        # is a complete second stack with no edits to any blob, so what runs
        # here is byte-for-byte what the base commit holds.
        (tmp_dir / "analysis").rename(target)
        shutil.rmtree(tmp_dir, ignore_errors=True)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if (target / "extract.py").is_file() and f"{package}.extract" not in sys.modules:
        sys.modules[f"{package}.extract"] = _retired_extractor(package)
    pipeline = importlib.import_module(f"{package}.pipeline")
    serialization = importlib.import_module(f"{package}.serialization")
    return BaseAnalysis(
        package=package,
        revision=resolved,
        analyze_markdown=pipeline.analyze_markdown,
        report_to_dict=serialization.report_to_dict,
        module=importlib.import_module(package),
    )


def leaf_diff(before: Any, after: Any, *, path: str = "") -> list[str]:
    """The PATHS at which two payloads differ — never the values.

    The privacy rule is the reason this returns paths: a value diff over an
    archive document prints the document's own figures into whatever consumes
    it. A path is a source symbol (`transactions[3].amount`), so it names the
    defect without quoting the statement.
    """
    if isinstance(before, dict) and isinstance(after, dict):
        differences: list[str] = []
        for key in sorted(set(before) | set(after)):
            here = f"{path}.{key}" if path else str(key)
            if key not in before:
                differences.append(f"{here} <absent-at-base>")
            elif key not in after:
                differences.append(f"{here} <absent-at-branch>")
            else:
                differences.extend(leaf_diff(before[key], after[key], path=here))
        return differences
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [f"{path} <length {len(before)}->{len(after)}>"]
        differences = []
        for index, (left, right) in enumerate(zip(before, after)):
            differences.extend(leaf_diff(left, right, path=f"{path}[{index}]"))
        return differences
    if type(before) is not type(after):
        return [f"{path} <type {type(before).__name__}->{type(after).__name__}>"]
    return [] if before == after else [path]

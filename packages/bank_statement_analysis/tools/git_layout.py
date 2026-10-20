"""Where the analysis tool sits inside a git revision.

Since the monorepo move it lives in packages/bank_statement_analysis/; older revisions hold it at the
repository root. Git run from `project_dir(ref)` reads `ref:./path`, and a pathspec, as the same file in
either layout. `project_tree(ref)` names the tool's own tree. `git diff --name-only` and
`git ls-tree --full-tree` print paths from the repository top; `project_path` turns one from a moved
revision into a path from the package folder.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_PREFIX = "packages/bank_statement_analysis/"
_OUTSIDE = f":(top,exclude){PACKAGE_PREFIX}"
_UP = "../" * PACKAGE_PREFIX.count("/")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PACKAGE_DIR, capture_output=True, text=True, check=True,
                          errors="replace").stdout


def moved(ref: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{ref}:./"], cwd=PACKAGE_DIR, capture_output=True).returncode == 0


def project_dir(ref: str) -> Path:
    return PACKAGE_DIR if moved(ref) else PACKAGE_DIR.parents[1]


def project_tree(ref: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{ref}:./"], cwd=project_dir(ref),
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def project_path(name: str) -> str:
    if name.startswith(PACKAGE_PREFIX):
        return name.removeprefix(PACKAGE_PREFIX)
    return _UP + name


def merge_base(a: str, b: str) -> str:
    return _git("merge-base", a, b).strip()


def working_tree() -> str:
    """A commit of the tracked files as they are on disk, so a diff can take the working tree as a ref."""
    return _git("stash", "create").strip() or "HEAD"


def diff(base: str, ref: str, *options: str) -> str:
    """`git diff base ref`, pairing each file by its place in the project.

    Across the move git pairs a moved file with its old copy only when the two are alike, and reports the
    rest as wholly added. Diffing the two project trees pairs every file by path. A moved ref's files outside
    the package follow, named from the package folder (`../../README.md`).
    """
    text = _git("diff", project_tree(base), project_tree(ref), *options)
    if moved(ref):
        text += _git("diff", f"--src-prefix=a/{_UP}", f"--dst-prefix=b/{_UP}", base, ref, *options, "--", _OUTSIDE)
    return text


def changed_files(base: str, ref: str) -> list[str]:
    """The files `diff(base, ref)` covers, as paths from the package folder."""
    names = _git("diff", "--name-only", project_tree(base), project_tree(ref)).splitlines()
    if moved(ref):
        names += [project_path(name) for name in _git("diff", "--name-only", base, ref, "--", _OUTSIDE).splitlines()]
    return names

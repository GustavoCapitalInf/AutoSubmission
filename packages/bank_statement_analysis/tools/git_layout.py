"""Where the analysis tool sits inside a git revision.

Since the monorepo move it lives in packages/bank_statement_analysis/; older revisions hold it at the
repository root. Git run from `project_dir(ref)` reads `ref:./path`, and a pathspec, as the same file in
either layout. `project_tree(ref)` names the tool's own tree, so a diff of two such trees compares the
same files across the move. `git diff --name-only` and `git ls-tree --full-tree` print paths from the
repository top; `project_path` turns one from a moved revision into a path from the package folder.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_PREFIX = "packages/bank_statement_analysis/"


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
    return "../" * PACKAGE_PREFIX.count("/") + name

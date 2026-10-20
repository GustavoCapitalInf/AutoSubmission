"""Where the analysis tool sits inside a git revision.

Since the monorepo move it lives in packages/bank_statement_analysis/; older revisions hold it at the
repository root. Git run from `project_dir(ref)` reads `ref:./path`, and a pathspec, as the same file in
either layout.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]


def project_dir(ref: str) -> Path:
    moved = subprocess.run(["git", "cat-file", "-e", f"{ref}:./"], cwd=PACKAGE_DIR, capture_output=True)
    return PACKAGE_DIR if moved.returncode == 0 else PACKAGE_DIR.parents[1]

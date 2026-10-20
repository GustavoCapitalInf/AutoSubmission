"""Where the analysis tool sits inside a git revision.

Since the monorepo move it lives in packages/bank_statement_analysis/; older revisions hold it at the
repository root. Git run from `project_dir(ref)` reads `ref:./path`, and a pathspec, as the same file in
either layout. `project_tree(ref)` names the tool's own tree, and `project_spec(ref, path)` one of
its files. `git diff --name-only` and
`git ls-tree --full-tree` print paths from the repository top; `project_path` turns one from a moved
revision into a path from the package folder. Functions that take `repo` read its HEAD and working tree.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_PREFIX = "packages/bank_statement_analysis/"
_OUTSIDE = f":(top,exclude){PACKAGE_PREFIX}"
_UP = "../" * PACKAGE_PREFIX.count("/")


def _git(*args: str, repo: Path = PACKAGE_DIR, env: dict[str, str] | None = None) -> str:
    return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True,
                          errors="replace").stdout


def moved(ref: str, repo: Path = PACKAGE_DIR) -> bool:
    found = subprocess.run(["git", "cat-file", "-e", f"{ref}:{PACKAGE_PREFIX}"], cwd=repo, capture_output=True)
    return found.returncode == 0


def project_dir(ref: str) -> Path:
    return PACKAGE_DIR if moved(ref) else PACKAGE_DIR.parents[1]


def project_tree(ref: str, repo: Path = PACKAGE_DIR) -> str:
    return _git("rev-parse", f"{ref}:{PACKAGE_PREFIX}" if moved(ref, repo) else f"{ref}^{{tree}}", repo=repo).strip()


def project_spec(ref: str, path: str, repo: Path = PACKAGE_DIR) -> str:
    return f"{ref}:{PACKAGE_PREFIX if moved(ref, repo) else ''}{path}"


def project_path(name: str) -> str:
    if name.startswith(PACKAGE_PREFIX):
        return name.removeprefix(PACKAGE_PREFIX)
    return _UP + name


def merge_base(a: str, b: str, repo: Path = PACKAGE_DIR) -> str:
    return _git("merge-base", a, b, repo=repo).strip()


def working_tree(repo: Path = PACKAGE_DIR) -> str:
    """A tree of the tracked files as they are on disk, so a diff can take the working tree as a ref.

    Built in a copy of the index, which leaves the real one untouched and takes intent-to-add entries. A
    missing index is an empty one, as git treats it.
    """
    index = repo / (os.environ.get("GIT_INDEX_FILE") or _git("rev-parse", "--git-path", "index", repo=repo).strip())
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(scratch, "index")}
        if index.exists():
            shutil.copyfile(index, env["GIT_INDEX_FILE"])
        _git("add", "--update", repo=repo, env=env)
        return _git("write-tree", repo=repo, env=env).strip()


def diff(base: str, ref: str, *options: str, repo: Path = PACKAGE_DIR) -> str:
    """`git diff base ref`, pairing each file by its place in the project.

    Across the move git pairs a moved file with its old copy only when the two are alike, and reports the
    rest as wholly added. Diffing the two project trees pairs every file by path. A moved ref's files outside
    the package follow, named from the package folder (`../../README.md`).
    """
    text = _git("diff", project_tree(base, repo), project_tree(ref, repo), *options, repo=repo)
    if moved(ref, repo):
        text += _git("diff", f"--src-prefix=a/{_UP}", f"--dst-prefix=b/{_UP}", base, ref, *options, "--", _OUTSIDE,
                     repo=repo)
    return text


def changed_files(base: str, ref: str, repo: Path = PACKAGE_DIR) -> list[str]:
    """The files `diff(base, ref)` covers, as paths from the package folder."""
    names = _git("diff", "--name-only", project_tree(base, repo), project_tree(ref, repo), repo=repo).splitlines()
    if moved(ref, repo):
        names += [project_path(name) for name in _git("diff", "--name-only", base, ref, "--", _OUTSIDE,
                                                       repo=repo).splitlines()]
    return names

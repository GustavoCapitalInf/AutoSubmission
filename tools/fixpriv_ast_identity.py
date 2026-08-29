"""Is a touched production module AST-identical modulo docstrings and comments?

FIXTURE-PRIVACY moves archive-shaped figures out of docstrings and comments. A
docstring edit is invisible to behaviour; an edit that slips one character into
a regex literal, a constant or an expression is not, and the difference is not
something a diff read by eye can be trusted to see across hundreds of lines of
prose. This decides it mechanically.

    python -m tools.fixpriv_ast_identity --base <ref> --ref <ref> [path ...]

With no paths it takes every tracked `.py` that differs between the two refs.
Each file is parsed at both refs, every DOCSTRING is removed (the leading string
expression of a module, class or function), and the two trees are compared by
`ast.dump(..., include_attributes=False)`, which also drops line and column
numbers, so prose that grows or shrinks moves nothing. Comments never reach an
AST at all.

What this does NOT excuse, deliberately: a string used as anything other than a
docstring — a regex, a marker, a message — is part of the tree and any change to
it is reported as a difference. That is the point: those are behaviour.

Exit 0 when every file is identical, 1 when any differs, 2 on a parse or git
failure. $0: git and the standard library only, no archive, no cache, no network.
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_HOLDERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def strip_docstrings(tree: ast.AST) -> ast.AST:
    """Remove the leading string expression of every module, class and function."""
    for node in ast.walk(tree):
        if not isinstance(node, _HOLDERS):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            if len(body) == 1:
                # A body cannot be empty; a docstring-only body becomes `pass`,
                # the same way at both refs.
                node.body = [ast.Pass()]
            else:
                node.body = body[1:]
    return tree


def show(ref: str, path: str) -> str | None:
    proc = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                          capture_output=True, text=True, errors="replace")
    return proc.stdout if proc.returncode == 0 else None


def changed_python(base: str, ref: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}...{ref}"],
                          cwd=ROOT, capture_output=True, text=True, check=True)
    return [name for name in proc.stdout.splitlines() if name.endswith(".py")]


def dump(source: str) -> str:
    return ast.dump(strip_docstrings(ast.parse(source)), include_attributes=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)

    paths = args.paths or changed_python(args.base, args.ref)
    if not paths:
        print(f"no python file differs between {args.base} and {args.ref}")
        return 0
    identical: list[str] = []
    differing: list[str] = []
    for path in sorted(paths):
        before, after = show(args.base, path), show(args.ref, path)
        if before is None or after is None:
            print(f"MISSING {path}: at {args.base}={before is not None} "
                  f"{args.ref}={after is not None}", file=sys.stderr)
            return 2
        try:
            same = dump(before) == dump(after)
        except SyntaxError as exc:
            print(f"PARSE {path}: {exc}", file=sys.stderr)
            return 2
        (identical if same else differing).append(path)
        print(f"{'IDENTICAL' if same else 'DIFFERS  '} {path}")
    print(f"\nfiles {len(paths)} · AST-identical modulo docstrings/comments "
          f"{len(identical)} · differing {len(differing)}")
    for path in differing:
        print(f"DIFFERS {path}", file=sys.stderr)
    return 1 if differing else 0


if __name__ == "__main__":
    raise SystemExit(main())

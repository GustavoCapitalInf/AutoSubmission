"""MUTATION TABLE for the two gates FIXTURE-PRIVACY adds (batch 9).

An exclusion is the only way a candidate leaves the scan without being fixed,
so the test that guards it has to be a test OF it. A test named after a rule is
not a test of that rule: this harness proves each guard by BREAKING it in the
direction that would hide a leak — widening an exclusion, blinding a
comparison — and demanding that the guard's own suite fail, naming the tests
that failed. Two gates are covered: the scanner's exclusion table, and
`fixpriv_ast_identity`'s "no production behaviour changed" verdict.

Every mutant is a literal, documented substitution in its gate's own file. The
harness refuses to run on a dirty tree
(it restores with `git checkout --`, which would otherwise discard real work),
runs the suite WITHOUT `-x` so every killer is named, and restores the file
after each mutant whether or not the run succeeded.

    python -m tools.fixpriv_mutation_table [--out <private>.md]

Exit 0 only if EVERY mutant was killed. $0: no archive, no cache, no network.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The gates this harness proves, and the suite that must kill their mutants.
GATES: dict[str, tuple[str, str]] = {
    "scan": ("tools/privacy_scan_branch.py", "tests/test_privacy_scan_exclusions.py"),
    "ast": ("tools/fixpriv_ast_identity.py", "tests/test_fixpriv_ast_identity.py"),
    "redact": ("tools/fixpriv_w3_redact.py", "tests/test_fixpriv_w3_redact.py"),
}

#: (id, gate, rule it attacks, what the mutant does, exact old, exact new)
MUTANTS: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "M1", "scan", "words_class",
        "widen the class test so the WORDS excuse also swallows digit runs",
        'def _words_class(cls: str, path: str, token: str, line: str) -> bool:\n    return cls == "WORDS"',
        'def _words_class(cls: str, path: str, token: str, line: str) -> bool:\n    return cls in ("WORDS", "DIGITS")',
    ),
    (
        "M2", "scan", "corpus_cache",
        "match the directory name anywhere in the path instead of at its head",
        'return path.startswith("tests/corpus_cache/")',
        'return "corpus_cache" in path',
    ),
    (
        "M3", "scan", "round_money",
        "excuse any figure ending in a zero, not only whole dollars",
        'return cls == "MONEY" and token.endswith(".00")',
        'return cls == "MONEY" and token.endswith("0")',
    ),
    (
        "M4", "scan", "subunit_money",
        "search instead of fullmatch, so `818,181.81` reads as a sub-unit constant",
        'return cls == "MONEY" and re.fullmatch(r"0\\.\\d\\d", token) is not None',
        'return cls == "MONEY" and re.search(r"0\\.\\d\\d", token) is not None',
    ),
    (
        "M5", "scan", "hex_sha_substring",
        "excuse every digit run on a line that merely CONTAINS a sha",
        'return cls == "DIGITS" and any(token in run for run in HEX_RUN_RE.findall(line))',
        'return cls == "DIGITS" and HEX_RUN_RE.search(line) is not None',
    ),
    (
        "M6", "scan", "hex_sha_substring",
        "drop the hex-LETTER requirement, so any 7..64 digit run reads as a "
        "sha and a card or account number goes quiet",
        r'    r"(?<![0-9A-Z])(?=[0-9A-F]{7,64}(?![0-9A-Z]))[0-9A-F]*[A-F][0-9A-F]*(?![0-9A-Z])"',
        r'    r"(?<![0-9A-Z])(?=[0-9A-F]{7,64}(?![0-9A-Z]))[0-9A-F]*(?![0-9A-Z])"',
    ),
    (
        "M6b", "scan", "hex_sha_substring",
        "shorten the run to five, so a short mixed token reads as an object name",
        "[0-9A-F]{7,64}",
        "[0-9A-F]{5,64}",
    ),
    (
        "M7", "scan", "docs_session_date",
        "drop the era bound: every ISO date in docs/ becomes a session date",
        "        and ISO_DATE_RE.match(token) is not None\n        and token >= PROGRAM_ERA",
        "        and ISO_DATE_RE.match(token) is not None",
    ),
    (
        "M8", "scan", "docs_session_date",
        "move the era back before the archive, which has the same effect",
        'PROGRAM_ERA = "2026-07-01"',
        'PROGRAM_ERA = "2000-01-01"',
    ),
    (
        "M9", "scan", "docs_session_date",
        "drop the directory bound: a fixture date in tests/ becomes a session date",
        '        and path.startswith("docs/")\n',
        "",
    ),
    (
        "M10", "scan", "institution_zip",
        "drop the address context: any five-digit run becomes a postal code",
        "        and len(token) == 5\n        and token in ZIP_CONTEXT_RE.findall(line)",
        "        and len(token) == 5",
    ),
    (
        "M11", "scan", "institution_zip",
        "widen the gap and let it cross digits, so the rule reaches past an address",
        r'ZIP_CONTEXT_RE = re.compile(rf"\b(?:{_STATE})\b[^0-9]{{0,8}}(\d{{5}})(?!\d)")',
        r'ZIP_CONTEXT_RE = re.compile(rf"\b(?:{_STATE})\b.{{0,40}}?(\d{{5}})(?!\d)")',
    ),
    (
        "M12", "scan", "the table as a whole",
        "let a rule claim a hit before it is asked to, by excusing everything",
        "def excluded_by(cls: str, path: str, token: str, line: str) -> str | None:\n"
        '    """The first rule of the table that claims this hit, or None."""\n'
        "    for name, rule in EXCLUSIONS:",
        "def excluded_by(cls: str, path: str, token: str, line: str) -> str | None:\n"
        '    """The first rule of the table that claims this hit, or None."""\n'
        "    return EXCLUSIONS[0][0]\n"
        "    for name, rule in EXCLUSIONS:",
    ),
    (
        "A1", "ast", "the AST comparison",
        "compare only the root node type, so every tree reads as identical",
        "    return ast.dump(strip_docstrings(ast.parse(source)), include_attributes=False)",
        "    return type(ast.parse(source)).__name__",
    ),
    (
        "A2", "ast", "strip_docstrings",
        "strip EVERY bare string expression, not only the leading one, so a "
        "string moved into or out of a body stops being visible",
        "            if len(body) == 1:",
        "            node.body = [s for s in body if not (isinstance(s, ast.Expr)\n"
        "                and isinstance(s.value, ast.Constant)\n"
        "                and isinstance(s.value.value, str))] or [ast.Pass()]\n"
        "            body = node.body\n"
        "            if len(body) == 1:",
    ),
    (
        "A3", "ast", "docstring stripping at all",
        "strip nothing, so a prose-only edit reads as a behaviour change",
        "        if (\n"
        "            isinstance(first, ast.Expr)\n"
        "            and isinstance(first.value, ast.Constant)\n"
        "            and isinstance(first.value.value, str)\n"
        "        ):",
        "        if False:",
    ),
    (
        "A4", "ast", "line and column attributes",
        "include attributes, so prose that grows by a line reads as a change",
        "    return ast.dump(strip_docstrings(ast.parse(source)), include_attributes=False)",
        "    return ast.dump(strip_docstrings(ast.parse(source)), include_attributes=True)",
    ),
    (
        "R1", "redact", "the sha rule",
        "drop the span check that keeps a replacement out of a content sha",
        "        if any(start < hend and hstart < end for hstart, hend in protected):\n"
        "            continue",
        "        if False:\n"
        "            continue",
    ),
    (
        "R2", "redact", "the sha rule",
        "shorten the protected run so a sha PREFIX stops being a sha",
        "_HEX_ANY_CASE = HEX_RUN_RE.pattern",
        '_HEX_ANY_CASE = r"[0-9A-F]{48,64}"',
    ),
    (
        "R3", "redact", "the residue test",
        "redact by SHAPE alone, so the program's own counts are redacted too",
        '        if text not in residue.get(cls, ()) and text.replace(",", "") not in residue.get(cls, ()):\n'
        "            continue",
        "        if False:\n"
        "            continue",
    ),
    (
        "R4", "redact", "the separator form",
        "match only the token as printed, losing the comma-stripped form",
        '        if text not in residue.get(cls, ()) and text.replace(",", "") not in residue.get(cls, ()):',
        "        if text not in residue.get(cls, ()):",
    ),
    (
        "R5", "redact", "the overlap filter",
        "let a DIGITS run inside a money figure be replaced a second time",
        "        if kept and start < kept[-1][1]:\n            continue",
        "        if False:\n            continue",
    ),
)

_FAIL_LINE = re.compile(r"^(FAILED|ERROR) (\S+)")


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _restore(target: Path) -> None:
    subprocess.run(["git", "checkout", "--", str(target.relative_to(ROOT))],
                   cwd=ROOT, capture_output=True, text=True, check=True)


def run(out: Path | None) -> int:
    dirty = _porcelain()
    if dirty:
        print("the tree is not clean; the harness restores with `git checkout --` and "
              f"would discard real work:\n{dirty}", file=sys.stderr)
        return 3
    originals = {gate: (ROOT / path).read_text(encoding="utf-8")
                 for gate, (path, _suite) in GATES.items()}
    rows: list[tuple[str, str, str, str, str, str]] = []
    survivors = 0
    for ident, gate, rule, what, old, new in MUTANTS:
        target, suite = ROOT / GATES[gate][0], GATES[gate][1]
        original = originals[gate]
        if original.count(old) != 1:
            rows.append((ident, gate, rule, what, "NOT APPLIED",
                         f"the mutated text occurs {original.count(old)} times, not once"))
            survivors += 1
            continue
        target.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", suite, "-q", "--no-header", "-p", "no:cacheprovider"],
                cwd=ROOT, capture_output=True, text=True, errors="replace",
            )
        finally:
            _restore(target)
        killers = sorted({m.group(2) for m in
                          (_FAIL_LINE.match(line) for line in proc.stdout.splitlines()) if m})
        if proc.returncode == 0 and not killers:
            rows.append((ident, gate, rule, what, "SURVIVED", "no test failed"))
            survivors += 1
        else:
            head = "; ".join(k.split("::", 1)[-1] for k in killers[:4])
            if len(killers) > 4:
                head += f"; +{len(killers) - 4} more"
            rows.append((ident, gate, rule, what, f"KILLED ({len(killers)})",
                         head or f"exit {proc.returncode}"))
    for gate, (path, _suite) in GATES.items():
        if (ROOT / path).read_text(encoding="utf-8") != originals[gate]:
            print(f"{path} was not restored; refusing to report", file=sys.stderr)
            return 4
    lines = ["| mutant | gate | rule | what the mutant does | verdict | killed by |",
             "|---|---|---|---|---|---|"]
    lines += [f"| {i} | `{g}` | `{r}` | {w} | {v} | {k} |" for i, g, r, w, v, k in rows]
    table = "\n".join(lines)
    print(table)
    print(f"\nmutants {len(MUTANTS)} · killed {len(MUTANTS) - survivors} · survived {survivors}")
    if out is not None:
        out.write_text(table + f"\n\nmutants {len(MUTANTS)} · killed "
                       f"{len(MUTANTS) - survivors} · survived {survivors}\n", encoding="utf-8")
    return 0 if survivors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=None)
    return run(parser.parse_args(argv).out)


if __name__ == "__main__":
    raise SystemExit(main())

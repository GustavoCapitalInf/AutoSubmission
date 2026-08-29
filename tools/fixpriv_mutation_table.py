"""MUTATION TABLE for the privacy scanner's exclusion table (batch 9, FIXPRIV).

An exclusion is the only way a candidate leaves the scan without being fixed,
so the test that guards it has to be a test OF it. A test named after a rule is
not a test of that rule: this harness proves the guard by BREAKING each rule in
the direction that would hide a leak — always widening it — and demanding that
`tests/test_privacy_scan_exclusions.py` fail, naming the tests that failed.

Every mutant is a literal, documented substitution in
`tools/privacy_scan_branch.py`. The harness refuses to run on a dirty tree
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
TARGET = ROOT / "tools" / "privacy_scan_branch.py"
SUITE = "tests/test_privacy_scan_exclusions.py"

#: (id, rule it attacks, what the mutant does, exact old text, exact new text)
MUTANTS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "M1", "words_class",
        "widen the class test so the WORDS excuse also swallows digit runs",
        'def _words_class(cls: str, path: str, token: str, line: str) -> bool:\n    return cls == "WORDS"',
        'def _words_class(cls: str, path: str, token: str, line: str) -> bool:\n    return cls in ("WORDS", "DIGITS")',
    ),
    (
        "M2", "corpus_cache",
        "match the directory name anywhere in the path instead of at its head",
        'return path.startswith("tests/corpus_cache/")',
        'return "corpus_cache" in path',
    ),
    (
        "M3", "round_money",
        "excuse any figure ending in a zero, not only whole dollars",
        'return cls == "MONEY" and token.endswith(".00")',
        'return cls == "MONEY" and token.endswith("0")',
    ),
    (
        "M4", "subunit_money",
        "search instead of fullmatch, so `10.01` reads as a sub-unit constant",
        'return cls == "MONEY" and re.fullmatch(r"0\\.\\d\\d", token) is not None',
        'return cls == "MONEY" and re.search(r"0\\.\\d\\d", token) is not None',
    ),
    (
        "M5", "hex_sha_substring",
        "excuse every digit run on a line that merely CONTAINS a sha",
        'return cls == "DIGITS" and any(token in run for run in HEX_RUN_RE.findall(line))',
        'return cls == "DIGITS" and HEX_RUN_RE.search(line) is not None',
    ),
    (
        "M6", "hex_sha_substring",
        "shorten the hex run until an eight-digit account number is a `sha`",
        'HEX_RUN_RE = re.compile(r"[0-9A-F]{16,64}")',
        'HEX_RUN_RE = re.compile(r"[0-9A-F]{8,64}")',
    ),
    (
        "M7", "docs_session_date",
        "drop the era bound: every ISO date in docs/ becomes a session date",
        "        and ISO_DATE_RE.match(token) is not None\n        and token >= PROGRAM_ERA",
        "        and ISO_DATE_RE.match(token) is not None",
    ),
    (
        "M8", "docs_session_date",
        "move the era back before the archive, which has the same effect",
        'PROGRAM_ERA = "2026-07-01"',
        'PROGRAM_ERA = "2000-01-01"',
    ),
    (
        "M9", "docs_session_date",
        "drop the directory bound: a fixture date in tests/ becomes a session date",
        '        and path.startswith("docs/")\n',
        "",
    ),
    (
        "M10", "institution_zip",
        "drop the address context: any five-digit run becomes a postal code",
        "        and len(token) == 5\n        and token in ZIP_CONTEXT_RE.findall(line)",
        "        and len(token) == 5",
    ),
    (
        "M11", "institution_zip",
        "widen the gap and let it cross digits, so the rule reaches past an address",
        r'ZIP_CONTEXT_RE = re.compile(rf"\b(?:{_STATE})\b[^0-9]{{0,8}}(\d{{5}})(?!\d)")',
        r'ZIP_CONTEXT_RE = re.compile(rf"\b(?:{_STATE})\b.{{0,40}}?(\d{{5}})(?!\d)")',
    ),
    (
        "M12", "the table as a whole",
        "let a rule claim a hit before it is asked to, by excusing everything",
        "def excluded_by(cls: str, path: str, token: str, line: str) -> str | None:\n"
        '    """The first rule of the table that claims this hit, or None."""\n'
        "    for name, rule in EXCLUSIONS:",
        "def excluded_by(cls: str, path: str, token: str, line: str) -> str | None:\n"
        '    """The first rule of the table that claims this hit, or None."""\n'
        "    return EXCLUSIONS[0][0]\n"
        "    for name, rule in EXCLUSIONS:",
    ),
)

_FAIL_LINE = re.compile(r"^(FAILED|ERROR) (\S+)")


def _porcelain() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _restore() -> None:
    subprocess.run(["git", "checkout", "--", str(TARGET.relative_to(ROOT))],
                   cwd=ROOT, capture_output=True, text=True, check=True)


def run(out: Path | None) -> int:
    dirty = _porcelain()
    if dirty:
        print("the tree is not clean; the harness restores with `git checkout --` and "
              f"would discard real work:\n{dirty}", file=sys.stderr)
        return 3
    original = TARGET.read_text(encoding="utf-8")
    rows: list[tuple[str, str, str, str, str]] = []
    survivors = 0
    for ident, rule, what, old, new in MUTANTS:
        if original.count(old) != 1:
            rows.append((ident, rule, what, "NOT APPLIED",
                         f"the mutated text occurs {original.count(old)} times, not once"))
            survivors += 1
            continue
        TARGET.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", SUITE, "-q", "--no-header", "-p", "no:cacheprovider"],
                cwd=ROOT, capture_output=True, text=True, errors="replace",
            )
        finally:
            _restore()
        killers = sorted({m.group(2) for m in
                          (_FAIL_LINE.match(line) for line in proc.stdout.splitlines()) if m})
        if proc.returncode == 0 and not killers:
            rows.append((ident, rule, what, "SURVIVED", "no test failed"))
            survivors += 1
        else:
            head = "; ".join(k.split("::", 1)[-1] for k in killers[:4])
            if len(killers) > 4:
                head += f"; +{len(killers) - 4} more"
            rows.append((ident, rule, what, f"KILLED ({len(killers)})", head or f"exit {proc.returncode}"))
    if TARGET.read_text(encoding="utf-8") != original:
        print("the target was not restored; refusing to report", file=sys.stderr)
        return 4
    lines = ["| mutant | rule | what the mutant does | verdict | killed by |",
             "|---|---|---|---|---|"]
    lines += [f"| {i} | `{r}` | {w} | {v} | {k} |" for i, r, w, v, k in rows]
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

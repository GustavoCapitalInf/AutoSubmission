"""MUTATION TABLE for the gates FIXTURE-PRIVACY adds, and the one it moved.

An exclusion is the only way a candidate leaves the scan without being fixed,
so the test that guards it has to be a test OF it. A test named after a rule is
not a test of that rule: this harness proves each guard by BREAKING it in the
direction that would hide a leak — widening an exclusion, blinding a
comparison, widening a tolerance — and demanding that the guard's own suite
fail, naming the tests that failed. Four gates are covered: the scanner's
exclusion table and its diff reader, `fixpriv_ast_identity`'s "no production
behaviour changed" verdict, `fixpriv_w3_redact`'s span rules, and
`analysis/lili.py`'s `_CENT` — the last because this card rewrote the fixtures
that are the only thing guarding it.

Every mutant is a literal, documented substitution in its gate's own file. The
harness refuses to run on a dirty tree
(it restores with `git checkout --`, which would otherwise discard real work),
runs the suite WITHOUT `-x` so every killer is named, and restores the file
after each mutant whether or not the run succeeded.

THE RESTORE CANNOT DEPEND ON GIT, and this host is why. The re-review closure
watched `git checkout -- tools/privacy_scan_branch.py` die with exit 255 —
`index.lock` contention from another cell sharing this repository's `.git` —
inside the `finally`, so the restore did not happen and THE MUTANT WAS LEFT IN
THE WORKING TREE. A harness that can leave mutated source behind is worse than
one that merely reports red: the next command in that shell, in any worktree,
runs against a scanner whose exclusion table has a hole punched in it on
purpose. So the restore now has two stages and neither can raise: git first
(it is the right tool when it works), then a CONTENT restore from the original
text this harness read before it mutated anything, which needs no git at all
and is the authoritative one. Every file is verified byte-for-byte against that
original before any table is printed, and `git status --porcelain` must then
come back clean — retried, because the same contention can silence `status`.

    python -m tools.fixpriv_mutation_table [--out <private>.md]

Exit 0 only if EVERY mutant was killed; 3 if the tree was not clean (or git
would not say) BEFORE the run, 4 if a gate file was not restored to its
original bytes, 5 if the tree is not verifiably clean AFTER it. 1 means a
mutant survived, which is the only red that is about the code.
$0: no archive, no cache, no network.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The gates this harness proves, and the suite that must kill their mutants.
GATES: dict[str, tuple[str, str]] = {
    "scan": ("tools/privacy_scan_branch.py", "tests/test_privacy_scan_exclusions.py"),
    "ast": ("tools/fixpriv_ast_identity.py", "tests/test_fixpriv_ast_identity.py"),
    "redact": ("tools/fixpriv_w3_redact.py", "tests/test_fixpriv_w3_redact.py"),
    # Not a gate this card wrote: a gate this card's fixture repair had to keep
    # sharp. Scaling `tests/test_lili.py`'s figures was right; scaling its
    # deliberate ERRORS with them multiplied by 428 the slack a widened
    # tolerance could take before the file noticed, and nothing else in the
    # tree guards it (`corpus_gate` replays documents that close exactly, so a
    # wider tolerance only makes the reader more permissive and the gate stays
    # green). The `L` mutants are that ladder, committed so it can be re-run.
    "lili": ("analysis/lili.py", "tests/test_lili.py"),
    # The harness itself. Its restore is a gate like any other — it is the one
    # standing between a transient git failure on this shared host and a
    # mutated scanner left on disk — and it had never been mutated. It mutates
    # its own source, which is safe for exactly the reason the fix is: the
    # running module is already imported, the mutant is only ever read by the
    # pytest SUBPROCESS, and the restore is a byte comparison against text held
    # in memory since before anything was written.
    "harness": ("tools/fixpriv_mutation_table.py", "tests/test_fixpriv_mutation_table.py"),
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
        "    places = _occurrences(token, line)\n"
        "    return bool(places) and all(\n"
        "        any(start <= at and at + len(token) <= end for start, end in runs)\n"
        "        for at in places\n"
        "    )",
        "    return True",
    ),
    (
        "M5b", "scan", "hex_sha_substring",
        "restore the LINE-scoped reading: the token need only appear somewhere "
        "inside some sha on the line, so a run standing on its own beside the "
        "sha it is a substring of goes quiet",
        "    places = _occurrences(token, line)\n"
        "    return bool(places) and all(\n"
        "        any(start <= at and at + len(token) <= end for start, end in runs)\n"
        "        for at in places\n"
        "    )",
        "    return any(token in run for run in HEX_RUN_RE.findall(line))",
    ),
    (
        "M5c", "scan", "hex_sha_substring",
        "ask ANY occurrence instead of EVERY occurrence — the same hole, one "
        "quantifier further in",
        "    return bool(places) and all(",
        "    return bool(places) and any(",
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
        "        and len(token) == 5\n"
        "        and any(token in pattern.findall(line) for pattern in ADDRESS_ZIP_RES)",
        "        and len(token) == 5",
    ),
    (
        "M11", "scan", "institution_zip",
        "widen the gap and let it cross digits, so the rule reaches past an address",
        '_ZIP_GAP = r"[^0-9]{0,8}"',
        '_ZIP_GAP = r".{0,40}?"',
    ),
    (
        "M11b", "scan", "institution_zip",
        "restore the BARE-ABBREVIATION reading — a state token then five digits, "
        "with no address furniture asked for. This is the shape the review "
        "blocked: it reads `MEMBER ID 84213` and `AUTH OK 84213` as postal "
        "codes and silences a member number and an authorisation code",
        "        and any(token in pattern.findall(line) for pattern in ADDRESS_ZIP_RES)",
        r'        and token in re.findall(rf"\b(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)", line)',
    ),
    (
        "M11c", "scan", "institution_zip",
        "drop the city's COMMA, so any word before the abbreviation reads as a "
        "city and `AUTH OK 84213` is an address again",
        r'    rf"[A-Z]{_ADDRESS_JUNK}{{0,2}},{_ADDRESS_JUNK}{{0,4}}(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)"',
        r'    rf"[A-Z]{_ADDRESS_JUNK}{{0,4}}(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)"',
    ),
    (
        "M11d", "scan", "institution_zip",
        "unbound the post-office box to the whole LINE, so a box in one clause "
        "excuses an identifier in the next",
        r'    rf"\bP\.?\s?O\.?\s?BOX\b{_CLAUSE_CHAR}{{0,70}}?\b(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)"',
        r'    rf"\bP\.?\s?O\.?\s?BOX\b.*\b(?:{_STATE})\b{_ZIP_GAP}(\d{{5}})(?!\d)"',
    ),
    (
        "M11e", "scan", "institution_zip",
        "widen the box CLAUSE back to `[^;|]`, so the marker reaches across a "
        "full stop or a dash and an account tail standing after an address "
        "goes quiet",
        '_CLAUSE_CHAR = r"[^;|.\\-\\u2013\\u2014!?()\\[\\]]"',
        '_CLAUSE_CHAR = r"[^;|]"',
    ),
    (
        "M11f", "scan", "institution_zip",
        "put the standalone ZIP+4 branch back into the table, so a five-digit "
        "run with a four-digit suffix reads as an address with no city and no "
        "box anywhere near it",
        "ADDRESS_ZIP_RES = (CITY_STATE_ZIP, BOX_CLAUSE_ZIP)",
        "ADDRESS_ZIP_RES = (CITY_STATE_ZIP, BOX_CLAUSE_ZIP, re.compile(\n"
        "    rf\"\\b(?:{_STATE})\\b{_ZIP_GAP}(\\d{{5}})\\s?-\\s?\\d{{4}}(?![\\d-])\"))",
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
        "D1", "scan", "added_lines_from_diff",
        "restore the TEXT-based reader: classify each diff line by what it "
        "looks like, so a line of the file that begins `+++` is read as a file "
        "header, never scanned, and every line after it is numbered one low",
        "            if line.startswith(\"+\"):\n"
        "                out.append((current, line_no, line[1:].upper()))\n"
        "                line_no += 1\n"
        "                new_left -= 1",
        "            if line.startswith(\"+\") and not line.startswith(\"+++\"):\n"
        "                out.append((current, line_no, line[1:].upper()))\n"
        "                line_no += 1\n"
        "                new_left -= 1",
    ),
    (
        "D2", "scan", "added_lines_from_diff",
        "number every hunk from the file's start instead of from its own "
        "header, so a hit is reported against a line nobody can find",
        "            line_no = int(match.group(2))",
        "            line_no = 1",
    ),
    (
        "L1", "lili", "_CENT, the reconciliation tolerance",
        "widen the cent tolerance to a dollar: a reader that accepts a "
        "dollar of discrepancy between a printed summary and its own ledger",
        "_CENT = 0.005",
        "_CENT = 1.0",
    ),
    (
        "L2", "lili", "_CENT, the reconciliation tolerance",
        "widen it to ten dollars",
        "_CENT = 0.005",
        "_CENT = 10.0",
    ),
    (
        "L3", "lili", "_CENT, the reconciliation tolerance",
        "widen it to a hundred dollars — the value at which the ORIGINAL "
        "fixtures still died and the 428-scaled ones survived",
        "_CENT = 0.005",
        "_CENT = 100.0",
    ),
    (
        "L4", "lili", "_CENT, the reconciliation tolerance",
        "widen it to half a dollar, which no fixture in this file caught "
        "before the perturbations were brought back to one cent",
        "_CENT = 0.005",
        "_CENT = 0.5",
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
        "A5", "ast", "a path that is absent at one ref",
        "restore the exit-2: read absence as a git failure, so the bare "
        "invocation the card's method writes dies on any branch that adds a "
        "module",
        "        if not (at_base and at_ref):\n"
        "            skipped.append(path)",
        "        if not (at_base and at_ref):\n"
        "            return 2\n"
        "            skipped.append(path)",
    ),
    (
        "H1", "harness", "the restore",
        "restore with git and nothing else — the pre-fix form, in which a "
        "`checkout` that dies with 255 from another cell's `index.lock` raises "
        "out of the `finally` and abandons the mutant in the working tree",
        "    try:\n"
        '        _git("checkout", "--", str(target.relative_to(ROOT)))\n'
        "    except Exception:  # noqa: BLE001 — the restore is not allowed to have an opinion\n"
        "        pass\n"
        "    for attempt in range(_GIT_TRIES):\n"
        "        try:\n"
        '            if target.read_text(encoding="utf-8") == original:\n'
        "                return\n"
        '            target.write_text(original, encoding="utf-8")\n'
        "        except OSError:\n"
        "            time.sleep(_GIT_BACKOFF * (attempt + 1))",
        '    _git("checkout", "--", str(target.relative_to(ROOT)))',
    ),
    (
        "H2", "harness", "`_porcelain`",
        "read a status git would not answer as an EMPTY status, so a tree "
        "whose state is unknown passes for a tree proved clean",
        # Each `old` below carries a line of CONTEXT it does not need, because
        # this gate's mutants live in the file they mutate: a one-line literal
        # would occur twice — once in the code and once in this tuple — and the
        # harness's own "occurs N times, not once" guard would decline to apply
        # it. The context line is chosen to exist only at the real site.
        "                time.sleep(_GIT_BACKOFF * (attempt + 1))\n"
        "    return None",
        "                time.sleep(_GIT_BACKOFF * (attempt + 1))\n"
        '    return ""',
    ),
    (
        "H3", "harness", "the tree check after the run",
        "assume the tree is clean afterwards instead of asking, so anything a "
        "mutant left outside its own gate file is reported as a green table",
        "    left = _porcelain()\n"
        "    if left is None:",
        '    left = ""\n'
        "    if left is None:",
    ),
    (
        "H4", "harness", "the suite launch",
        "let a failure to LAUNCH the suite escape the loop, so the restore's "
        "`finally` runs but neither verification is ever reached and the run "
        "dies with a traceback instead of a table",
        '            failure = f"{type(error).__name__}: {error}"\n'
        "        finally:",
        "            raise\n"
        "        finally:",
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


#: This repository carries stale `.git/worktrees/*` entries that OneDrive holds
#: open, so git's automatic prune fails on them and prints a line per entry. The
#: prune is housekeeping, not the command's work, and the command's work
#: succeeds — but the exit code follows the prune, and the harness used to die
#: on it with 128 in the middle of a mutant, leaving the gate file mutated. Two
#: things fix it: `gc.auto=0`, which stops git from starting the prune at all,
#: and treating a failure whose every stderr line is prune noise as the success
#: it is. Neither weakens the harness: the tree-clean check and the
#: restore-verified check both still run on the OUTPUT, and a real git failure
#: still raises.
_PRUNE_NOISE = re.compile(
    r"^(error|warning): failed to (delete|remove) '.*[/\\]worktrees[/\\].*': .*$"
)


def _git(*args: str) -> str:
    """git, with the stale-worktree prune neither started nor scored."""
    proc = subprocess.run(["git", "-c", "gc.auto=0", *args], cwd=ROOT,
                          capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        noise = [line for line in proc.stderr.splitlines() if line.strip()]
        if not noise or not all(_PRUNE_NOISE.match(line) for line in noise):
            raise subprocess.CalledProcessError(
                proc.returncode, args, proc.stdout, proc.stderr)
    return proc.stdout


#: How many times a git call that only READS is retried, and how long the
#: harness waits between tries. `index.lock` contention from another cell in
#: another worktree of this repository is transient by construction — the lock
#: exists for the length of one write — so a status that will not answer once
#: usually answers a moment later. Reads only: a retry loop around a WRITE
#: would be a different and worse thing.
_GIT_TRIES = 3
_GIT_BACKOFF = 0.5


def _porcelain() -> str | None:
    """The working tree's status, or None if git would not answer at all.

    None and "" are different facts and the caller must not confuse them: ""
    is a tree proved clean, None is a tree whose state is unknown. Both refuse
    the run, at either end, but only one of them is a claim.
    """
    for attempt in range(_GIT_TRIES):
        try:
            return _git("status", "--porcelain").strip()
        except (subprocess.CalledProcessError, OSError):
            if attempt + 1 < _GIT_TRIES:
                time.sleep(_GIT_BACKOFF * (attempt + 1))
    return None


def _restore(target: Path, original: str) -> None:
    """Put the file back to `original`. NEVER raises, whatever git does.

    Stage one is `git checkout --`, which is the right tool and the one that
    also drops anything else a mutant might have left. Its exit code is
    IGNORED — the observed failure (255, `index.lock` held by another cell)
    reports failure while the underlying tree is fine, and the previous version
    of this function let that exception out of a `finally` and abandoned the
    mutant on disk.

    Stage two is the one that cannot fail for a reason outside this process:
    compare the bytes against the original this harness read BEFORE it mutated
    anything, and write them back if they differ. OneDrive holds files open
    transiently, so the write is retried; if every try fails the function still
    returns, and the caller's verification — which reads the file again — is
    what turns that into a refusal to report.
    """
    try:
        _git("checkout", "--", str(target.relative_to(ROOT)))
    except Exception:  # noqa: BLE001 — the restore is not allowed to have an opinion
        pass
    for attempt in range(_GIT_TRIES):
        try:
            if target.read_text(encoding="utf-8") == original:
                return
            target.write_text(original, encoding="utf-8")
        except OSError:
            time.sleep(_GIT_BACKOFF * (attempt + 1))


def run(out: Path | None) -> int:
    dirty = _porcelain()
    if dirty is None:
        print("git status would not answer after "
              f"{_GIT_TRIES} tries, so the tree cannot be proved clean; refusing to "
              "start — this harness mutates tracked source and restores it, and it "
              "will not do that against a tree it cannot see", file=sys.stderr)
        return 3
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
        proc = None
        failure = ""
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", suite, "-q", "--no-header", "-p", "no:cacheprovider"],
                cwd=ROOT, capture_output=True, text=True, errors="replace",
            )
        except Exception as error:  # noqa: BLE001
            # Launching the suite failed — not a verdict about the mutant. It
            # is recorded as a survivor (an unproved gate is not a proved one)
            # and, crucially, it does not escape `run`: the restore below and
            # the two verifications after the loop have to be reached.
            failure = f"{type(error).__name__}: {error}"
        finally:
            _restore(target, original)
        if proc is None:
            rows.append((ident, gate, rule, what, "NOT RUN", failure))
            survivors += 1
            continue
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
    # Two verifications, in this order, and no table is printed unless both
    # pass. The first is about the files this harness knowingly mutated and is
    # byte-exact against text held in memory since before the first mutant. The
    # second is about everything else — a mutant that wrote somewhere
    # unexpected, or a `git checkout` that took something with it.
    for gate, (path, _suite) in GATES.items():
        if (ROOT / path).read_text(encoding="utf-8") != originals[gate]:
            print(f"{path} was not restored; refusing to report", file=sys.stderr)
            return 4
    left = _porcelain()
    if left is None:
        print(f"git status would not answer after {_GIT_TRIES} tries, so the tree "
              "cannot be proved clean; the mutated gate files ARE verified restored "
              "byte-for-byte, but this harness does not report a table it cannot "
              "stand behind", file=sys.stderr)
        return 5
    if left:
        print(f"the tree is not clean after the run; refusing to report:\n{left}",
              file=sys.stderr)
        return 5
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

"""commsec_mutation_table.py — the mutants the community_section refusal must kill.

    python -m tools.commsec_mutation_table [--tests <file>] [--out <private>.md]

This card adds NO gate and changes NO grammar: `analysis/community_section.py`
is byte-identical to the base. What it adds is one refusal test and its
control, and a test named after a property is not a test of that property — so
each is run against the mutant it exists for.

HARNESS SAFETY is the FIXPRIV2 lesson, applied here in full:

* it REFUSES to start on a dirty tree, so a mutant can never be mistaken for
  the author's own edit;
* the restore runs in a `finally` in two stages, and neither stage can raise:
  `git checkout --` first with its exit code IGNORED (on this shared host that
  call has died with a lock contention from another worktree of the same
  `.git`), then a CONTENT restore against the original bytes the harness read
  before it mutated anything, retried for OneDrive's transient holds;
* nothing is reported unless every mutated file equals its in-memory original
  byte for byte AND `git status --porcelain` comes back clean. A status git
  will not answer is `None`, not empty: a tree whose state is unknown is not a
  tree proved clean, and that refuses the run;
* a failure to LAUNCH the suite is recorded as a SURVIVOR rather than allowed
  to escape the loop, because an unrun test kills nothing;
* the tests run WITHOUT `-x`, so one mutant's kill cannot hide another's
  survival.

Never run two mutation harnesses at once on this host.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

READER = Path("analysis/community_section.py")
DEFAULT_TESTS = Path("tests/test_community_section_layouts.py")

#: `(id, file, what it breaks, exact old text, exact new text, the killer)`.
MUTANTS = [
    (
        "M1",
        READER,
        "a posting row with no balance beside it is booked anyway, its "
        "direction taken from the only thing left - a guess",
        "        if len(monies) < 2:\n"
        "            # One figure is the opening or closing balance row the ledger\n"
        "            # prints as a bookend; it is not a posting. Its balance still\n"
        "            # anchors the chain the postings are checked against.\n"
        "            if len(monies) == 1 and previous is None:\n"
        "                previous = _balance(monies[0].group())\n"
        "            continue\n",
        "        if len(monies) < 2:\n"
        "            if len(monies) == 1 and previous is None:\n"
        "                previous = _balance(monies[0].group())\n"
        "                continue\n"
        "            if len(monies) == 1:\n"
        "                guess = _money(monies[0].group())\n"
        "                if guess is None:\n"
        "                    continue\n"
        "                credit = \"credit\" in rest.lower() or \"incoming\" in rest.lower()\n"
        "                txns.append(\n"
        "                    Transaction(\n"
        "                        date=_iso(match.group(1)),\n"
        "                        description=re.sub(r\"\\s+\", \" \", rest).strip(),\n"
        "                        amount=round(guess if credit else -guess, 2),\n"
        "                        direction=\"credit\" if credit else \"debit\",\n"
        "                    )\n"
        "                )\n"
        "            continue\n",
        "test_an_activity_ledger_printing_no_running_balance_is_declined",
    ),
    (
        "M2",
        READER,
        "the balance column is read but the row's direction is not taken from "
        "it - every row is booked a credit",
        "        signed = amount if balance >= previous else -amount\n",
        "        signed = amount\n",
        "test_the_same_ledger_publishes_once_the_bank_prints_the_balance_column",
    ),
]


def _read(path: Path) -> str:
    """The file EXACTLY as it stands, line endings included.

    `newline=""` and not the default: this tree is checked out with
    `core.autocrlf=true`, so the production sources carry CRLF, and a restore
    that wrote LF back would leave every line of the file changed. The mutants
    below are written with `\\n`, so `_newline` translates them to whatever the
    file itself uses before they are applied.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _write(path: Path, text: str) -> None:
    for attempt in range(6):
        try:
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(text)
            return
        except OSError:                      # OneDrive holds the file briefly
            if attempt == 5:
                raise
            time.sleep(1.0 + attempt)


def _porcelain() -> str | None:
    """The working tree's state, or None when git would not answer."""
    for attempt in range(6):
        try:
            done = subprocess.run(["git", "status", "--porcelain"],
                                  capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.SubprocessError):
            done = None
        if done is not None and done.returncode == 0:
            return done.stdout.strip()
        time.sleep(1.0 + attempt)
    return None


def _restore(originals: dict[Path, str]) -> bool:
    """Two stages, neither of which may raise. True only when PROVED clean."""
    try:
        subprocess.run(["git", "checkout", "--", *[str(p) for p in originals]],
                       capture_output=True, text=True, timeout=180)
    except Exception:                        # the exit code is deliberately ignored
        pass
    for path, text in originals.items():
        try:
            if _read(path) != text:
                _write(path, text)
        except Exception:
            try:
                _write(path, text)
            except Exception:
                return False
    for path, text in originals.items():
        try:
            if _read(path) != text:
                return False
        except Exception:
            return False
    return _porcelain() == ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tests", type=Path, default=DEFAULT_TESTS)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    state = _porcelain()
    if state is None:
        print("REFUSED: git would not report the working tree's state")
        return 2
    if state:
        print("REFUSED: the working tree is dirty; a mutant must never be "
              "confused with an author's edit")
        return 2

    originals = {path: _read(path) for _id, path, *_rest in MUTANTS}
    rows = []
    try:
        for mid, path, what, old, new, killer in MUTANTS:
            text = originals[path]
            eol = _newline(text)
            old, new = old.replace("\n", eol), new.replace("\n", eol)
            if text.count(old) != 1:
                rows.append((mid, what, killer, "NOT-APPLIED "
                             f"(anchor occurs {text.count(old)} times)"))
                continue
            _write(path, text.replace(old, new))
            try:
                # `-rf` and not bare `-q`: the point of the table is WHICH test
                # killed the mutant, and a short summary that does not list the
                # failures by name cannot answer that. Without `-x`, so one
                # mutant's kill can never hide another test's survival.
                done = subprocess.run(
                    [sys.executable, "-m", "pytest", str(args.tests), "-q", "-rf"],
                    capture_output=True, text=True, timeout=1800)
                failures = {line.split("::")[-1].split()[0]
                            for line in done.stdout.splitlines()
                            if line.startswith("FAILED ")}
                if done.returncode == 0:
                    detail = "SURVIVED"
                elif killer in failures:
                    detail = ("KILLED" if failures == {killer}
                              else f"KILLED (and {len(failures) - 1} other test(s))")
                else:
                    detail = ("KILLED BY ANOTHER TEST — the named killer did not "
                              f"fail ({len(failures)} failure(s))")
            except Exception as exc:
                detail = f"SURVIVED (the suite would not launch: {type(exc).__name__})"
            finally:
                _write(path, originals[path])
            rows.append((mid, what, killer, detail))
    finally:
        clean = _restore(originals)

    lines = ["# DECL-COMMUNITY-SECTION mutation table", "",
             "| mutant | what it breaks | killer | result |", "|---|---|---|---|"]
    lines += [f"| {mid} | {what} | `{killer}` | **{detail}** |"
              for mid, what, killer, detail in rows]
    lines += ["", f"working tree proved clean after the run: {clean}"]
    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    print(report)
    if not clean:
        print("REFUSED TO REPORT: the working tree was not proved clean")
        return 2
    return 0 if all(row[3].startswith("KILLED") for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())

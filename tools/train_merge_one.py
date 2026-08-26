"""train_merge_one.py <branch> <message>: merge one cell branch into the train (HEAD).

The batch-7 helper, made durable and corrected for a redacted base (batch 8).

The ONLY conflict this tool resolves is the W3 log,
`docs/moneythumb-replacement/W3_TRACKA_LOG.md`, and it resolves it by a
BYTE-EXACT rebuild rather than a textual merge: the train's copy (ours) plus
the section the branch APPENDED to the merge-base copy (theirs minus base).
Every other conflict aborts with exit 3 for manual composition (registry
count pins, conformance fixtures, `OBSERVER_VERSION`, ...).

What is asserted, and why only that:

* `theirs.startswith(base)` — the branch's log must be the merge-base log with
  ONE appended section. A cell that edited another cell's section (the LILI
  incident of batch 8) fails here, which is the point.
* NOTHING is asserted about `ours` starting with `base`. Batch 7's helper did
  assert it, and the redaction commits on main (`cc64232`, `bbeeb5c`) edited
  earlier sections in place, so a train built on a redacted main no longer
  satisfies it. Ours is trusted as the composed log so far; the rebuild appends
  the branch's section to it verbatim.

Usage, from the train worktree root with the train branch checked out:

    python tools/train_merge_one.py wave8-welch "merge wave8-welch: WELCH ..."

Exit 0 on a completed merge commit; 3 on a non-W3 conflict (merge left in
progress for manual composition, nothing committed); 4 on a W3 shape
violation (merge aborted).
"""
from __future__ import annotations

import subprocess
import sys

W3 = "docs/moneythumb-replacement/W3_TRACKA_LOG.md"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, capture_output=True, check=check)


def blob(rev: str) -> bytes:
    return run("git", "show", f"{rev}:{W3}").stdout


def main(argv: list[str]) -> int:
    # Optional third argument: `--section-only "# §HEADER"`. The strict shape
    # check refuses a branch whose log carries edits OUTSIDE its own section
    # (batch 8: a scripted substitution that rewrote four other cells' proof
    # tables; sweep rows appended to a predecessor's table). Under this flag the
    # rebuild takes the train's log plus the branch's OWN section — everything
    # from the named header to end of file — and REPORTS the discarded
    # pre-section edits, so the composition is explicit rather than silent.
    section_only = None
    if len(argv) == 5 and argv[3] == "--section-only":
        section_only = argv[4].encode()
        argv = argv[:3]
    if len(argv) != 3:
        print(__doc__)
        return 2
    branch, message = argv[1], argv[2]
    merge_base = run("git", "merge-base", "HEAD", branch).stdout.decode().strip()
    merged = run("git", "merge", "--no-ff", "--no-commit", branch, check=False)
    if merged.returncode != 0:
        conflicts = run("git", "diff", "--name-only", "--diff-filter=U").stdout.decode().split()
        print("CONFLICTS:", conflicts)
        if conflicts != [W3]:
            print("NON-W3 CONFLICT - manual composition required; merge left in progress")
            return 3
        base, ours, theirs = blob(merge_base), blob("HEAD"), blob(branch)
        if theirs.startswith(base):
            section = theirs[len(base):]
        elif section_only is not None:
            start = theirs.find(b"\n" + section_only)
            if start < 0:
                run("git", "merge", "--abort", check=False)
                print("SECTION HEADER NOT FOUND in the branch log; merge aborted")
                return 4
            section = theirs[start + 1:]
            pre = theirs[: start + 1]
            discarded = sum(1 for a, b in zip(base.split(b"\n"), pre.split(b"\n")) if a != b) + abs(
                base.count(b"\n") - pre.count(b"\n")
            )
            print(
                f"SECTION-ONLY REBUILD: the branch log carried edits outside its own section "
                f"(~{discarded} differing lines before {section_only.decode()}); they are DISCARDED "
                f"and must be recorded in the train's log"
            )
        else:
            run("git", "merge", "--abort", check=False)
            print("W3 SHAPE VIOLATION: the branch log is not the merge-base log + an appended section; merge aborted")
            return 4
        with open(W3, "wb") as handle:
            handle.write(ours + section)
        run("git", "add", W3)
        print(f"W3 rebuilt byte-exact: ours {len(ours)} + section {len(section)} bytes")
    run("git", "commit", "-q", "-m", message)
    head = run("git", "rev-parse", "--short", "HEAD").stdout.decode().strip()
    print(f"merged {branch} -> {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

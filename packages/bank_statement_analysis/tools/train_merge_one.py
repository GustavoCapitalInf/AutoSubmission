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

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.git_layout import project_dir, project_path

W3 = "docs/moneythumb-replacement/W3_TRACKA_LOG.md"
#: The two registry-count pins every registration-adding cell bumps.
REGISTRY_PINS = ["tests/test_parser_registry_entries.py", "tests/test_parser_conformance.py"]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(args, capture_output=True, check=check)


def blob(rev: str) -> bytes:
    return subprocess.run(["git", "show", f"{rev}:./{W3}"], cwd=project_dir(rev),
                          capture_output=True, check=True).stdout


def resolve_hunks(text: str, keep: str) -> str:
    """Resolve every `<<<<<<< ... ======= ... >>>>>>>` hunk of a conflicted file.

    `keep="ours"` keeps the HEAD side of each hunk; `keep="both"` keeps the HEAD
    side followed by the branch side. Everything outside the hunks — git's clean
    three-way merge — is left exactly as git wrote it. Raises if the markers do
    not nest as expected, so a malformed file is never half-resolved.
    """
    out: list[str] = []
    side = None
    ours: list[str] = []
    theirs: list[str] = []
    for line in text.split("\n"):
        if line.startswith("<<<<<<< "):
            if side is not None:
                raise ValueError("nested conflict marker")
            side, ours, theirs = "ours", [], []
        elif line.startswith("=======") and side == "ours":
            side = "theirs"
        elif line.startswith(">>>>>>> ") and side == "theirs":
            out.extend(ours if keep == "ours" else ours + theirs)
            side = None
        elif side == "ours":
            ours.append(line)
        elif side == "theirs":
            theirs.append(line)
        else:
            out.append(line)
    if side is not None:
        raise ValueError("unterminated conflict marker")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    # Optional third argument: `--section-only "# §HEADER"`. The strict shape
    # check refuses a branch whose log carries edits OUTSIDE its own section
    # (batch 8: a scripted substitution that rewrote four other cells' proof
    # tables; sweep rows appended to a predecessor's table). Under this flag the
    # rebuild takes the train's log plus the branch's OWN section — everything
    # from the named header to end of file — and REPORTS the discarded
    # pre-section edits, so the composition is explicit rather than silent.
    section_only = None
    compose_registry = None
    union_files: list[str] = []
    rest = argv[3:]
    while rest:
        if rest[0] == "--section-only" and len(rest) >= 2:
            section_only = rest[1].encode()
            rest = rest[2:]
        elif rest[0] == "--compose-registry" and len(rest) >= 2:
            compose_registry = int(rest[1])
            rest = rest[2:]
        elif rest[0] == "--union" and len(rest) >= 2:
            union_files.append(rest[1].replace("\\", "/"))
            rest = rest[2:]
        else:
            print(__doc__)
            return 2
    argv = argv[:3]
    if len(argv) != 3:
        print(__doc__)
        return 2
    branch, message = argv[1], argv[2]
    merge_base = run("git", "merge-base", "HEAD", branch).stdout.decode().strip()
    merged = run("git", "merge", "--no-ff", "--no-commit", branch, check=False)
    if merged.returncode != 0:
        conflicts = [project_path(name)
                     for name in run("git", "diff", "--name-only", "--diff-filter=U").stdout.decode().split()]
        print("CONFLICTS:", conflicts)
        # `--compose-registry N`: a cell that ADDS registrations bumps the two
        # registry-count pins from the base count to its own, so every such cell
        # conflicts with the train on exactly the count lines of those two
        # files — while its OTHER edits to them (its id inserted into the
        # dispatch-order list, its fixture rows) merge cleanly. Composition
        # therefore resolves ONLY the conflict hunks (train side) and rewrites
        # the count to N, keeping git's clean merge of everything else. (The
        # first version took the whole train-side file and lost the clean
        # insertions; the dispatch-order pin caught it.)
        if compose_registry is not None:
            for pin in [p for p in REGISTRY_PINS if p in conflicts]:
                text = resolve_hunks(open(pin, "rb").read().decode("utf-8"), keep="ours")
                current = sorted({int(m) for m in re.findall(r"(?:len\(pr\.registrations\(\)\)|len\(REGISTRATIONS\)) == (\d+)", text)})
                if len(current) != 1:
                    print(f"REGISTRY PIN in {pin} is not a single count ({current}); merge left in progress")
                    return 3
                old = current[0]
                new_text = re.sub(rf"\b{old} × {old - 1} = [\d,]+ assertions",
                                  f"{compose_registry} × {compose_registry - 1} = {compose_registry * (compose_registry - 1):,} assertions", text)
                new_text = re.sub(rf"\ball {old} registrations\b", f"all {compose_registry} registrations", new_text)
                new_text = re.sub(rf"== {old}\b", f"== {compose_registry}", new_text)
                with open(pin, "wb") as handle:
                    handle.write(new_text.encode("utf-8"))
                run("git", "add", pin)
                print(f"REGISTRY PIN composed: {pin} {old} -> {compose_registry} (conflict hunks only)")
            conflicts = [c for c in conflicts if c not in REGISTRY_PINS]
        # `--union FILE`: two cells INSERTED adjacent, independent entries at the
        # same place (a registry edge block, an excused-caller entry) and git
        # cannot order them. Both sides are kept, ours first. Used only where
        # the entries are keyed and distinct — a duplicate key would be a
        # silent override, so the caller names the file deliberately.
        for path in [p for p in union_files if p in conflicts]:
            text = resolve_hunks(open(path, "rb").read().decode("utf-8"), keep="both")
            with open(path, "wb") as handle:
                handle.write(text.encode("utf-8"))
            run("git", "add", path)
            print(f"UNION composed: {path} (both sides of each conflict hunk kept, ours first)")
        conflicts = [c for c in conflicts if c not in union_files]
        if conflicts and conflicts != [W3]:
            print("NON-W3 CONFLICT - manual composition required; merge left in progress")
            return 3
        if not conflicts:
            run("git", "commit", "-q", "-m", message)
            head = run("git", "rev-parse", "--short", "HEAD").stdout.decode().strip()
            print(f"merged {branch} -> {head}")
            return 0
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

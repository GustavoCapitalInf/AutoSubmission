"""huntington_msg_privacy_scan.py — the same scan, on the surface the other one cannot read.

    python tools/huntington_msg_privacy_scan.py --rows <run>/rows.csv \
        --where parser_id=huntington --shas <population>.txt \
        --data-dir <cold cache> --base 52f1d03 --ref wave9-huntington

`tools/privacy_scan_branch.py` reads a branch's ADDED FILE LINES. A COMMIT
MESSAGE is not a file line, so a token written into a message is invisible to
it — and a message, once merged, is as permanent as a file and travels further.
HUNT9's own review (MINOR-1) found this the expensive way: the commit that
redacted two money-shaped tokens from the log quoted both of them in its
message, and the branch's proof floor reported 0 because it was structurally
blind to the place they now lived.

This scans `git log <base>..<ref> --format=%B` with the OTHER instrument's own
patterns, population loader, cache reader and base-tree exclusion — imported,
not copied, so the two scans cannot drift apart. Per commit it reports the
subject line and any hit's class and token; the token list goes to stderr and is
never committed.

Nothing here is huntington-specific. It sits under `tools/huntington_*` because
that is this card's ownership; if Ocean rules the standing line the review asks
for, this belongs beside `privacy_scan_branch.py` as a shared mode of it rather
than as a second file.

Exit 1 on any hit, 0 on none. READ-ONLY, $0.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.privacy_scan_branch import (  # noqa: E402  (path set above)
    cached_text,
    parse_args,
    population,
    rows_by_sha,
    self_check,
    tokens_of,
    tracked_text,
)


def messages(base: str, ref: str) -> list[tuple[str, str, str]]:
    """(sha, subject, full message) for every commit of `base..ref`."""
    raw = subprocess.run(
        ["git", "log", f"{base}..{ref}", "--format=%H%x1f%s%x1f%B%x1e"],
        cwd=ROOT, capture_output=True, text=True, check=True, errors="replace",
    ).stdout
    out: list[tuple[str, str, str]] = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        sha, subject, body = record.split("\x1f", 2)
        out.append((sha, subject, body))
    return out


def main(argv: list[str] | None = None) -> int:
    self_check()
    args = parse_args(argv)
    import sqlite3

    from telemetry.run_of_record import RunOfRecordError, partitions_for_run

    root = args.data_dir / "artifacts"
    conn = sqlite3.connect(f"file:{(args.data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
    try:
        try:
            partitions = partitions_for_run(args.run, conn=conn)
        except RunOfRecordError as exc:
            print(f"artifact-selection policy failed: {exc}", file=sys.stderr)
            return 5
        rows = rows_by_sha(args.run)
        shas = population(args)
        printed: dict[str, set[str]] = {"MONEY": set(), "DIGITS": set(), "DATES": set(), "WORDS": set()}
        documents_read = 0
        missing: list[str] = []
        for sha in shas:
            text = cached_text(conn, root, sha, rows.get(sha), partitions)
            if text is None:
                missing.append(sha[:8])
                continue
            documents_read += 1
            for cls, values in tokens_of(text, args.digit_min, args.word_min).items():
                printed[cls].update(values)
        # Same refusal as the file-line scan (P20-ARTIFACTS closure MAJOR-2):
        # a non-empty population that resolves NO cached text is a wrong
        # record, not a clean scan.
        if shas and documents_read == 0:
            print(
                f"REFUSED: 0 of {len(shas)} population shas resolved any cached text — "
                "the run's partitions do not describe this data directory",
                file=sys.stderr,
            )
            return 5
    finally:
        conn.close()

    # Same exclusion as the file-line scan, for the same reason: a token that
    # already sits in the tracked tree at `--base` is not one these messages
    # introduced, and the class is overwhelmingly template vocabulary.
    base_all: set[str] = set().union(
        *tokens_of(tracked_text(args.base), args.digit_min, args.word_min).values()
    )
    distinctive = {
        cls: {token for token in values if token not in base_all}
        for cls, values in printed.items()
    }

    commits = messages(args.base, args.ref)
    hits: list[dict[str, object]] = []
    for sha, subject, body in commits:
        body_tokens = set().union(
            *tokens_of(body, args.digit_min, args.word_min).values()
        )
        for cls, tokens in distinctive.items():
            for token in tokens & body_tokens:
                hits.append({"class": cls, "commit": sha[:7], "subject": subject, "token": token})
    hits.sort(key=lambda h: (str(h["commit"]), str(h["class"]), str(h["token"])))

    for hit in hits:
        print(f"HIT {hit['class']} {hit['commit']} {hit['subject'][:60]!r} {hit['token']}",
              file=sys.stderr)
    report = {
        "population": len(shas),
        "documents_read": documents_read,
        "no_cached_text": missing,
        "commits_scanned": len(commits),
        "printed_tokens": {cls: len(v) for cls, v in printed.items()},
        "distinctive_scanned": {cls: len(v) for cls, v in distinctive.items()},
        "hits_by_class": {cls: sum(1 for h in hits if h["class"] == cls) for cls in printed},
        "hit_count": len(hits),
        "base": args.base,
        "ref": args.ref,
    }
    print(json.dumps(report, sort_keys=True))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())

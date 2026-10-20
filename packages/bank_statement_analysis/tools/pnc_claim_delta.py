"""pnc_claim_delta.py — which documents this reader claims that it did not.

    python -m tools.pnc_claim_delta [--start 0 --end 3380] [--out <private>.md]

Widening a reader's DETECTION markers widens what it takes off other readers,
and the archive sweep answers that question by re-running the whole platform.
This answers the same question directly and far more cheaply, so it can be run
on a shared host in minutes rather than hours: for every content sha in the run
of record it reads the run's own cached text and asks `analysis.pnc.detect`
whether it claims the document AT THIS TREE, then compares that against the
`parser_id` the run recorded.

Three columns, and only the third is a finding:

* **claimed then and now** — the reader's own cohort, unchanged;
* **claimed now, unclaimed by every reader then** — the widening's intended
  gain, which must be inside the card's named population;
* **claimed now, claimed by ANOTHER reader then** — a document taken off a
  different reader. Every one is a regression to explain or remove, because
  dispatch gives a claimed document to the reader that claims it.

It runs the DETECTOR only — no analysis, no OCR, no model, $0 — so it bounds
the dispatch question and nothing else. It is not a substitute for the archive
sweep, which is the only instrument that compares published PAYLOADS; it is the
cheap half of that question, available when the expensive half will not fit.

Read-only over the archive and the cold cache. Prints shas, parser ids and
counts; never a document value.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

from tools.cohort_replay import (
    DEFAULT_DATA_DIR,
    DEFAULT_RUN_POINTER,
    ColdCache,
    load_baseline_rows,
)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    run = args.run or Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())

    from analysis.pnc import detect

    rows = load_baseline_rows(run)
    cache = ColdCache(args.data_dir)
    shas = sorted(rows)[args.start: args.end]

    tally: collections.Counter[str] = collections.Counter()
    taken: list[tuple[str, str]] = []
    gained: list[str] = []
    for index, sha in enumerate(shas, 1):
        markdown, _pages = cache.text(sha)
        if markdown is None:
            tally["no_text"] += 1
            continue
        was = (rows[sha].get("parser_id") or "").strip()
        now = detect(markdown).claims
        if now and was == "pnc":
            tally["claimed_then_and_now"] += 1
        elif now and not was:
            tally["claimed_now_unclaimed_then"] += 1
            gained.append(sha[:16])
        elif now and was:
            tally["claimed_now_taken_from_another_reader"] += 1
            taken.append((sha[:16], was))
        elif was == "pnc":
            tally["claimed_then_not_now"] += 1
            taken.append((sha[:16], "pnc -> unclaimed"))
        else:
            tally["untouched"] += 1
        if index % 500 == 0:
            print(f"  {index}/{len(shas)}", file=sys.stderr, flush=True)

    lines = [f"# pnc claim delta — run `{run.name}` — documents {len(shas)}", "",
             "| measure | count |", "|---|---:|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(tally.items())]
    lines += ["", f"newly claimed shas ({len(gained)}):", ""]
    lines += [f"* `{sha}`" for sha in gained]
    lines += ["", f"taken from another reader, or dropped ({len(taken)}):", ""]
    lines += [f"* `{sha}` — {which}" for sha, which in taken]
    report = "\n".join(lines)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")
    return 0 if not taken else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""l1s4_marker_sweep.py — what does the member-statement registration CLAIM?

    python -m tools.l1s4_marker_sweep --run <run dir> --data-dir <cold cache>

A registration's blast radius is the set of documents its markers claim, and a
card that names that set from the documents it went looking for has measured
nothing. This runs `analysis.member_statement_rollup`'s own detector over EVERY
document in the run of record that resolves to cached text, and reports:

* how many documents the markers CLAIM, by content sha and by baseline outcome;
* how many of those the reader then PUBLISHES, and how many it refuses;
* every claimed document that was NOT `failed` at baseline — which is the set a
  new registration could take away from another reader, and the number that has
  to be zero.

Read-only over the archive and the cold cache. Prints shas, counts and
outcomes; never a printed value, a name or an amount.

NOT in `corpus_gate.py`'s caller register, and that is the correct state rather
than an omission. It calls `analysis.member_statement.parse_member_statement`
DIRECTLY (`_claimed`, `_published` below); it reaches no analysis entry point,
so it calls none of the names the register's guard watches
(`tests/test_corpus_gate_outcomes.py::WATCHED`). Declaring it there would not
merely be redundant — that test also refuses a STALE declaration, a registered
module that no longer calls the analysis, so a register entry for this file
would turn the guard red.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import ColdCache, DEFAULT_DATA_DIR, DEFAULT_RUN_POINTER, load_baseline_rows  # noqa: E402

REGISTRATION = "member_statement_rollup"


def _run_dir(pointer: Path, given: str | None) -> Path:
    if given:
        return Path(given)
    return Path(pointer.read_text(encoding="utf-8").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run")
    parser.add_argument("--run-pointer", default=str(DEFAULT_RUN_POINTER))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    args = parser.parse_args(argv)

    from analysis.member_statement import detect, parse_member_statement

    run = _run_dir(Path(args.run_pointer), args.run)
    rows = load_baseline_rows(run)
    cache = ColdCache(Path(args.data_dir))

    shas = sorted(rows)[args.start: args.end]
    claimed: list[tuple[str, str, bool]] = []
    read = 0
    no_text = 0
    for sha in shas:
        markdown, _pages = cache.text(sha)
        if markdown is None:
            no_text += 1
            continue
        read += 1
        if not detect(markdown).claims:
            continue
        try:
            published = parse_member_statement(markdown) is not None
        except Exception:
            published = False
        claimed.append((sha[:16], (rows[sha].get("outcome_class") or "").strip(), published))

    by_outcome = collections.Counter(outcome for _sha, outcome, _p in claimed)
    not_failed = [item for item in claimed if item[1] != "failed"]
    print(f"# `{REGISTRATION}` marker sweep\n")
    print(f"* documents in the run: {len(shas)}")
    print(f"* ... read from the cold cache: {read} (no cached text: {no_text})")
    print(f"* ... CLAIMED by these markers: {len(claimed)}")
    print(f"* ... of those, PUBLISHED by the reader: {sum(1 for _s, _o, p in claimed if p)}")
    print(f"* ... refused after claiming: {sum(1 for _s, _o, p in claimed if not p)}")
    print(f"* baseline outcomes of the claimed set: {dict(sorted(by_outcome.items()))}")
    print(f"* claimed and NOT `failed` at baseline: {len(not_failed)}")
    for sha16, outcome, published in sorted(claimed):
        print(f"  - {sha16} baseline={outcome} published={published}")
    print(f"\nCLAIMED={len(claimed)} PUBLISHED={sum(1 for _s, _o, p in claimed if p)} "
          f"NOT_FAILED_AT_BASELINE={len(not_failed)}")
    return 1 if not_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

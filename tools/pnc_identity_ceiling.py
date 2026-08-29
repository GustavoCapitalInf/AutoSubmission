"""pnc_identity_ceiling.py — the CEILING of any further widening of this reader.

    python -m tools.pnc_identity_ceiling --mode all_identities \
        --shas <private>.txt [--out <private>.md]

`analysis/pnc.py` refuses a document whose rows do not reproduce the bank's own
printed index of them, or whose ledger does not reproduce the bank's own
end-of-day ladder. This instrument answers the question that decides whether
those refusals are a reader gap or a document fact:

    if those identities were not there — or if the grammar read every printed
    row — would the PLATFORM validate these documents?

Each sha is replayed through the same call the runner makes, with the named
part of `analysis.pnc` replaced IN MEMORY (the tree on disk is never touched):

  ``no_index``      the printed-index identity always passes. The reader still
                    publishes only the rows it captured.
  ``no_ladder``     the printed-ladder identity always passes.
  ``all_identities``both. The ceiling of RELAXATION: with the payload
                    unchanged there is nothing left to relax.
  ``ordered_dates`` a READING, not a relaxation, and the only one that can beat
                    the ceiling on this population. Where the flattening emits
                    the `mm/dd` column as its own runs, detached from the rows,
                    it pairs the k-th printed day of a section with the k-th
                    row of that section and reads the ledger that produces.
                    The days are printed; the CORRESPONDENCE is geometry the
                    flattened layer does not carry, so this is a reader that
                    infers a posting date rather than reading one. It is here
                    because the record has to name the real barrier, never to
                    propose it.

**What this bounds, stated exactly.** The first three modes bound RELAXATIONS
over the payload the reader already builds. They do NOT bound every possible
reader change: a reader that builds a DIFFERENT payload is outside them, and
`ordered_dates` is the measured proof of that. Read them together or the
smaller number will be mistaken for an impossibility.

The outcome is the platform's own — `telemetry.record.classify_outcome` over
the pipeline payload — so a ceiling of zero validated is a measured fact about
the documents and the platform rather than an opinion about the grammar.

Read-only, deterministic, $0, and it prints no document value: sha, outcome
class, outcome reason and counts only. The patch lives inside this process for
the duration of one replay and is removed in a `finally`.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from pathlib import Path

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")

MODES = ("as_is", "no_index", "no_ladder", "all_identities", "ordered_dates")

#: A line that is nothing but month halves of a detached `mm/dd` column, and
#: one that is nothing but its day halves.
_MONTH_RUN = re.compile(r"(?m)^[ \t]*(\d{2})(?:[ \t]+\d{2})*[ \t]*$")
_DAY_RUN = re.compile(r"(?m)^[ \t]*/\d{2}(?:[ \t]+/\d{2})*[ \t]*$")


def _repair_detached_dates(markdown: str) -> str:
    """Re-attach a detached date column to the rows it stands beside, IN ORDER.

    The transformation, said plainly so nobody mistakes it for a reading of the
    paper: inside each section the amounts are printed in one run and the
    `mm/dd` column in another, and this pairs them by ORDER — the k-th day with
    the k-th amount. That is an inference about the page's geometry, and the
    flattened text layer carries no evidence for or against it.
    """
    from analysis import pnc

    text = pnc._CONTROL_BYTE.sub(" ", markdown)
    body = pnc._activity_body(text)
    if not body:
        return text
    head, tail = text[: text.rfind(body)], body
    days = [day for run in _DAY_RUN.finditer(tail)
            for day in re.findall(r"/(\d{2})", run.group(0))]
    months = {month for run in _MONTH_RUN.finditer(tail)
              for month in re.findall(r"\d{2}", run.group(0))}
    if not days or len(months) != 1:
        # Nothing detached to re-attach, or more than one month in the runs —
        # in which case the month halves would have to be paired too, and the
        # inference this mode is measuring would be compounded rather than
        # bounded. Refuse to guess twice.
        return text
    month = months.pop()
    tail = _MONTH_RUN.sub(" ", _DAY_RUN.sub(" ", tail))
    queue = list(days)

    def attach(match: re.Match) -> str:
        if not queue:
            return match.group(0)
        return f"{month}/{queue.pop(0)} {match.group(0)}"

    # An amount that opens a row of the described column group: preceded by no
    # date and followed by a description.
    return head + re.sub(r"(?<![\d/.,])(\d[\d,]*\.\d{2}|\.\d{2})(?=\s+[A-Za-z])",
                         attach, tail)


@contextlib.contextmanager
def relaxed(mode: str):
    """The named identity removed, for one replay only."""
    from analysis import pnc

    undo = []
    if mode in ("no_index", "all_identities"):
        original = pnc._matches_the_printed_index
        pnc._matches_the_printed_index = lambda *_a, **_k: True
        undo.append(lambda: setattr(pnc, "_matches_the_printed_index", original))
    if mode in ("no_ladder", "all_identities"):
        original_grid = pnc._matches_the_printed_grid
        pnc._matches_the_printed_grid = lambda *_a, **_k: True
        undo.append(lambda: setattr(pnc, "_matches_the_printed_grid", original_grid))
    try:
        yield
    finally:
        for restore in reversed(undo):
            restore()


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--shas", type=Path, default=None)
    ap.add_argument("--mode", choices=MODES, default="all_identities")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group and args.shas is None:
        args.group = ["WH:pnc", "DECL:pnc"]

    from tools.cohort_replay import ColdCache, load_baseline_rows, replay_one

    population: list[str] = []
    if args.group:
        groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
        for name in args.group:
            population.extend(groups.get(name, {}).get("shas16", []))
    if args.shas:
        population.extend(line.strip()[:16] for line in
                          args.shas.read_text(encoding="utf-8").splitlines() if line.strip())
    rows = load_baseline_rows(args.run)
    by16 = {sha[:16]: sha for sha in rows}
    cache = ColdCache(args.data_dir)

    table = []
    for token in sorted(set(population)):
        sha = by16.get(token.upper())
        if sha is None:
            table.append({"sha16": token, "after": "absent", "reason": "-"})
            continue
        markdown, pages = cache.text(sha)
        if markdown is None:
            table.append({"sha16": token, "after": "no_text", "reason": "-"})
            continue
        if args.mode == "ordered_dates":
            markdown = _repair_detached_dates(markdown)
        with relaxed(args.mode):
            _payload, klass, reason, _claimed = replay_one(markdown, pages)
        table.append({"sha16": token, "before": rows[sha].get("outcome_class", ""),
                      "after": klass, "reason": reason})

    validated = [entry for entry in table if entry["after"] == "validated"]
    lines = [f"# pnc identity ceiling — mode `{args.mode}` — run `{args.run.name}`", "",
             f"population {len(table)} · **validated at the ceiling: {len(validated)}**", "",
             f"| sha16 | baseline | under `{args.mode}` | reason |", "|---|---|---|---|"]
    for entry in table:
        lines.append(f"| {entry['sha16']} | {entry.get('before', '-')} | "
                     f"{entry['after']} | {entry['reason']} |")
    report = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""L1-ARCH-DESIGN instrument 4 — READ-ONLY idle-sibling evidence probe.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**

One question, and it is the one the design's largest open ruling turns on.

The checkpoint ruling admits an idle sibling ONLY when explicit statement
structure establishes the sibling AND its empty/silent state; absence of parsed
activity alone is insufficient. `tools/l1_split_prototype.py` measures that 8
documents would close if a section that prints no dated row and reads nothing
could be OMITTED rather than counted, against 2 that close without that licence.
Whether those 6 extra sections are "absence of parsed activity" or "printed
evidence of an empty account" depends on ONE fact the packet never printed:

    **where did the idle section's opening and closing figures come from?**

If they came from the SECTION's own printed captions, the paper says of that
account "it opened here and it closed at the same figure" — a printed statement
about the account, not a silence. If they came from the enumerating TABLE's row
for that account, the same is true one level up. If neither prints them, the
section is refused long before this question arises, and there is nothing to
rule on.

`tools/l1_split_prototype.py` already computes exactly this and drops it: it
sets `open_from` / `close_from` on every section it reconstructs, and its JSON
emits `pair_source`, which is populated only for a NON-EMPTY successful walk —
so for every trivially idle section it is `None` and the provenance is lost.
This instrument re-runs THAT INSTRUMENT'S OWN `run_document` and reports the two
fields it already produced. It writes no grammar, no predicate and no
arithmetic of its own; every figure here is the split prototype's.

PRIVACY
-------
Content sha16s, census group names, provenance labels (`section` / `rollup`) and
counts. No printed value, name, account number, amount or date.

Usage:

    python -m tools.l1_design_idle_evidence --census-dir <census> --data-dir <cold cache> \
        [--json <private>.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import load_census  # noqa: E402
from tools.l1_split_prototype import _population, run_document  # noqa: E402


IDLE = "trivially-idle-opening-equals-closing-and-no-row-printed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design idle-sibling evidence probe")
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    groups, opportunities, per_sha = load_census(args.census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(args.data_dir)

    results = []
    for band, group, sha16 in _population(groups, opportunities):
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        results.append(run_document(sha16, group, band, markdown, len(pages)))

    idle_all = [(r, s) for r in results for s in r.sections if s.refusal == IDLE]
    idle_ruling = [(r, s) for r, s in idle_all if r.all_close_allowing_idle]

    print("# L1-ARCH-DESIGN — where a trivially idle section's figures came from")
    print()
    print("Every number below is `tools/l1_split_prototype.py`'s own: this "
          "instrument re-runs that instrument's `run_document` and reports the "
          "`open_from` / `close_from` labels it already computes and its JSON "
          "does not emit. `section` means the figure was read from the "
          "SECTION's own printed caption; `rollup` means it was read from the "
          "enumerating table's row for that account, which the split prototype "
          "accepts only where the table prints a COLUMN CAPTION naming its "
          "columns (the packet's condition 5).")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents reconstructed | {len(results)} |")
    print(f"| trivially idle sections in the whole population | **{len(idle_all)}** |")
    print(f"| ... on the documents that would close under the ruling | "
          f"**{len(idle_ruling)}** |")
    print(f"| ... the documents themselves | "
          f"{len({r.sha16 for r, _s in idle_ruling})} |")
    print()

    for title, rows in (("The whole population's idle sections", idle_all),
                        ("Only the sections the ruling would license", idle_ruling)):
        print(f"## {title}")
        print()
        print("| opening read from | closing read from | sections |")
        print("|---|---|---:|")
        counter = collections.Counter(
            (s.open_from or "none", s.close_from or "none") for _r, s in rows)
        for (open_from, close_from), count in sorted(counter.items()):
            print(f"| `{open_from}` | `{close_from}` | {count} |")
        print()
        print("| the section also printed | sections |")
        print("|---|---:|")
        print(f"| a dated row anywhere in it | "
              f"{sum(1 for _r, s in rows if s.dated_rows)} |")
        print(f"| a dated row in its LEDGER region | "
              f"{sum(1 for _r, s in rows if s.dated_ledger_rows)} |")
        print(f"| its own counts or totals, readable | "
              f"{sum(1 for _r, s in rows if s.stated_counts_fed or s.stated_totals_fed)} |")
        print(f"| its own daily-balance table | "
              f"{sum(1 for _r, s in rows if s.stated_daily_fed)} |")
        print()

    print("## The documents the ruling would license, by census group")
    print()
    print("| census group | documents | idle sections |")
    print("|---|---:|---:|")
    by_group: collections.Counter = collections.Counter()
    docs_by_group: dict[str, set] = collections.defaultdict(set)
    for r, _s in idle_ruling:
        by_group[r.group] += 1
        docs_by_group[r.group].add(r.sha16)
    for group in sorted(by_group):
        print(f"| `{group}` | {len(docs_by_group[group])} | {by_group[group]} |")
    print()

    if args.json:
        args.json.write_text(json.dumps({
            "documents": len(results),
            "idle_sections_all": len(idle_all),
            "idle_sections_under_ruling": len(idle_ruling),
            "provenance_all": {f"{o or 'none'}/{c or 'none'}": n for (o, c), n
                               in collections.Counter(
                                   (s.open_from, s.close_from) for _r, s in idle_all).items()},
            "provenance_ruling": {f"{o or 'none'}/{c or 'none'}": n for (o, c), n
                                  in collections.Counter(
                                      (s.open_from, s.close_from) for _r, s in idle_ruling).items()},
            "sha16_under_ruling": sorted({r.sha16 for r, _s in idle_ruling}),
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

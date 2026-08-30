"""L1-ARCH-DESIGN instrument 2 — READ-ONLY regression-surface census.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**

The design has to name its regression surface by POPULATION, not by adjective:
which registrations a publication-model change puts at risk, how many of their
documents are protected (`validated` in the run of record), how many documents
in the whole archive already carry a signal that they hold more than one
account, and — the one nobody has measured — how many documents are published
TODAY with a deposit section silently dropped.

The last is the point. `analysis/symitar.py` 13-48 ratifies two idle-sibling
skips and says in its own docstring that both are silent. What the ratified
rule licenses is a skip on PRINTED evidence (its dormancy declaration, or its
yield-only arithmetic with a summary-equality test). What the module actually
executes for the first of those is `if not rows: continue` — a skip on the
ABSENCE of parsed rows. The same shape is in `analysis/community_section.py`
(a section is counted only `if stmt is not None and stmt.transactions`). Under
the L-1 checkpoint ruling — "an idle sibling is admitted ONLY when explicit
statement structure establishes the sibling AND its empty / silent state;
absence of parsed activity alone is insufficient" — those are two different
rules, and the gap between them is a population this instrument measures.

METHOD
------
* The run of record's `rows.csv` supplies every document's registration and
  outcome. Nothing is inferred from a folder label.
* `likely_account_count` is read straight out of the run: it is the OCR
  inspector's own advisory count (`ocr/inspect.py::_account_count`), annotated
  in `telemetry/record.py` as consumed by nothing. It is reported here as what
  it is — an ADVISORY signal, not a partition — because it is the only
  archive-wide multi-account signal that already exists.
* The printed-evidence probes call each module's OWN committed patterns
  (`analysis.symitar._DORMANT_RE`, `analysis.symitar._SECTION_MARK_RE`,
  `analysis.community_section._ACCOUNT_HEADING_RE` /
  `_PLATFORM_ACCOUNT_RE`). Nothing here writes a pattern of its own, so
  nothing here can measure a grammar this repository does not already run.
* The pinned exposure is computed from the pinned manifest's own SHA-256s
  against the run's rows — measured, never assumed.

WHAT IT DOES NOT CLAIM
----------------------
A section-mark count is a BOUND, not a partition: two printed section marks on
a document that publishes one account mean a section was dropped OR that the
template reprints its heading. Both bounds are printed as bounds and the
design reads them as bounds.

PRIVACY
-------
Content sha16s, registration ids and counts only. No path, no printed value,
name, account number, amount or date is read into the output — the pinned
manifest's paths are consumed to compute a digest and are never printed.

Usage:

    python -m tools.l1_design_surface_census --run <run dir> --data-dir <cold cache> \
        [--corpus <corpus dir>] [--balance-csv <csv>] [--json <private>.json]
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache, load_baseline_rows  # noqa: E402


#: Every registration whose module carries an L-1 gate or a silent sibling
#: skip today. `community_section` is one MODULE under three registration ids,
#: and each id is its own `cohort_replay --parser` population.
L1_REGISTRATIONS: tuple[str, ...] = (
    "huntington",
    "community_section",
    "dakota_west",
    "mission_valley",
    "navy_federal",
    "capital_one",
    "consumers",
    "symitar",
    "zions",
)

LADDER = ("failed", "withheld", "review", "validated", "deferred")


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()
    except OSError:
        return None


def pinned_shas(corpus: Path, balance_csv: Path) -> tuple[list[str], int]:
    """The pinned corpus, as content digests. Paths are never printed."""
    if not balance_csv.is_file() or not corpus.is_dir():
        return [], 0
    with balance_csv.open(encoding="utf-8", newline="") as handle:
        relatives = sorted({row["path"] for row in csv.DictReader(handle) if row.get("path")})
    digests = [d for d in (_digest(corpus / Path(rel)) for rel in relatives) if d]
    return digests, len(relatives)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design regression-surface census")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--balance-csv", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    rows = load_baseline_rows(args.run)
    print("# L1-ARCH-DESIGN — regression-surface census")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents in the run of record | {len(rows)} |")
    by_outcome = collections.Counter((row.get("outcome_class") or "") for row in rows.values())
    for klass in LADDER:
        print(f"| ... `{klass}` | {by_outcome.get(klass, 0)} |")
    print(f"| **the archive sweep's own scale** | **{len(rows)}** |")
    print()

    # ------------------------------------------------------------------
    # the archive-wide advisory signal
    # ------------------------------------------------------------------
    print("## The multi-account signal the archive already carries, and consumes nowhere")
    print()
    print("`likely_account_count` is `ocr/inspect.py::_account_count` — distinct "
          "printed account-number values, else 1 if any account block marker "
          "appears, else 0. It rides in `rows.csv` and in every telemetry "
          "record and NOTHING reads it. It is a bound, not a partition: it "
          "counts printed account-number VALUES, so a document reprinting one "
          "account's number in two forms counts two, and a document printing a "
          "sibling with no number counts one.")
    print()
    print("| `likely_account_count` | documents | of them `validated` |")
    print("|---:|---:|---:|")
    counts: collections.Counter = collections.Counter()
    validated_counts: collections.Counter = collections.Counter()
    for row in rows.values():
        raw = (row.get("likely_account_count") or "").strip()
        try:
            value = int(raw)
        except ValueError:
            value = -1
        bucket = value if value <= 4 else 5
        counts[bucket] += 1
        if (row.get("outcome_class") or "") == "validated":
            validated_counts[bucket] += 1
    for bucket in sorted(counts):
        label = "5 or more" if bucket == 5 else ("unreadable" if bucket < 0 else str(bucket))
        print(f"| {label} | {counts[bucket]} | {validated_counts[bucket]} |")
    multi = sum(v for k, v in counts.items() if k >= 2)
    multi_validated = sum(v for k, v in validated_counts.items() if k >= 2)
    print(f"| **2 or more (the advisory L-1 exposure)** | **{multi}** | **{multi_validated}** |")
    print()

    # ------------------------------------------------------------------
    # per-registration cohorts
    # ------------------------------------------------------------------
    print("## The cohorts a publication-model change puts at risk")
    print()
    print("Every registration whose module carries an L-1 gate or a silent "
          "sibling skip. `validated` is the protected count: a document here "
          "that leaves `validated` is a BLOCKING regression. These are the "
          "`cohort_replay --parser <id>` populations, named and sized.")
    print()
    print("| registration | documents in the run | `validated` (protected) | other outcomes |")
    print("|---|---:|---:|---|")
    cohorts: dict[str, list[str]] = {}
    for registration in L1_REGISTRATIONS:
        shas = sorted(sha for sha, row in rows.items()
                      if (row.get("parser_id") or "") == registration)
        cohorts[registration] = shas
        validated = sum(1 for sha in shas
                        if (rows[sha].get("outcome_class") or "") == "validated")
        others = collections.Counter((rows[sha].get("outcome_class") or "")
                                     for sha in shas
                                     if (rows[sha].get("outcome_class") or "") != "validated")
        rest = ", ".join(f"`{k}` {v}" for k, v in sorted(others.items())) or "—"
        print(f"| `{registration}` | {len(shas)} | **{validated}** | {rest} |")
    total = sum(len(v) for v in cohorts.values())
    total_validated = sum(1 for shas in cohorts.values() for sha in shas
                          if (rows[sha].get("outcome_class") or "") == "validated")
    print(f"| **total** | **{total}** | **{total_validated}** | |")
    print()

    # ------------------------------------------------------------------
    # the silent skip, on printed evidence
    # ------------------------------------------------------------------
    from analysis.symitar import _DORMANT_RE, _SECTION_MARK_RE
    from analysis.community_section import _ACCOUNT_HEADING_RE, _PLATFORM_ACCOUNT_RE

    cache = ColdCache(args.data_dir)
    probes = {
        "symitar": (_SECTION_MARK_RE, _DORMANT_RE),
        "community_section": (_PLATFORM_ACCOUNT_RE, _DORMANT_RE),
        "dakota_west": (_ACCOUNT_HEADING_RE, _DORMANT_RE),
        "mission_valley": (_ACCOUNT_HEADING_RE, _DORMANT_RE),
    }
    print("## The silent skip, measured on each module's OWN patterns")
    print()
    print("`section marks` is the module's own account-heading pattern; "
          "`declares` is `analysis/symitar.py::_DORMANT_RE`, the ratified "
          "wording — defined at `symitar.py:116` and, measured by grep at this "
          "tree, referenced by NO code in `analysis/` or `tests/`. The "
          "production dormant skip is `symitar.py:419-420` `if not rows: "
          "continue`, and `community_section.py:621-622` returns None from "
          "`_parse_sectioned_statement` when a block parsed no row. Both are skips on the "
          "ABSENCE of parsed rows, which the checkpoint ruling names as "
          "insufficient on its own.")
    print()
    print("| registration | `validated` documents read | print 2+ section marks | "
          "... AND publish one account | print the ratified declaration |")
    print("|---|---:|---:|---:|---:|")
    skip_detail: dict[str, dict] = {}
    for registration, (mark_re, declare_re) in probes.items():
        shas = [sha for sha in cohorts.get(registration, [])
                if (rows[sha].get("outcome_class") or "") == "validated"]
        read = 0
        multi_mark: list[str] = []
        declares: list[str] = []
        for sha in shas:
            markdown, _pages = cache.text(sha)
            if markdown is None:
                continue
            read += 1
            marks = {m.group(0) for m in mark_re.finditer(markdown)}
            if len(marks) >= 2:
                multi_mark.append(sha[:16])
            if declare_re.search(markdown):
                declares.append(sha[:16])
        skip_detail[registration] = {
            "read": read,
            "multi_mark": multi_mark,
            "declares": declares,
        }
        print(f"| `{registration}` | {read} | {len(multi_mark)} | {len(multi_mark)} | "
              f"{len(declares)} |")
    print()
    print("The third column and the fourth are the same number BY "
          "CONSTRUCTION: every document counted is one the platform published "
          "as a single account and classified `validated`. A document printing "
          "two distinct section marks and publishing one account either "
          "dropped a section or reprinted a heading, and this instrument "
          "cannot tell those apart — which is exactly why the design makes the "
          "omission a PAYLOAD FIELD rather than a count in a report.")
    print()

    # ------------------------------------------------------------------
    # pinned exposure
    # ------------------------------------------------------------------
    if args.corpus and args.balance_csv:
        digests, listed = pinned_shas(args.corpus, args.balance_csv)
        in_run = [d for d in digests if d in rows]
        print("## The pinned corpus, against these cohorts")
        print()
        print("| measure | value |")
        print("|---|---:|")
        print(f"| pinned documents listed in the manifest | {listed} |")
        print(f"| ... whose bytes were read and digested | {len(digests)} |")
        print(f"| ... present in the run of record | {len(in_run)} |")
        print(f"| ... NOT in the run (cannot be surveyed through it) | "
              f"{len(digests) - len(in_run)} |")
        print()
        pinned_by_reg = collections.Counter(
            (rows[d].get("parser_id") or "") for d in in_run
            if (rows[d].get("parser_id") or "") in L1_REGISTRATIONS)
        print("| registration | pinned documents it claims in the run |")
        print("|---|---:|")
        for registration in L1_REGISTRATIONS:
            if pinned_by_reg.get(registration):
                print(f"| `{registration}` | {pinned_by_reg[registration]} |")
        print(f"| **total pinned on an L-1 module** | **{sum(pinned_by_reg.values())}** |")
        print()
        if args.json:
            skip_detail["_pinned"] = {
                "listed": listed,
                "digested": len(digests),
                "in_run": len(in_run),
                "by_registration": dict(pinned_by_reg),
                "sha16": sorted(d[:16] for d in in_run
                                if (rows[d].get("parser_id") or "") in L1_REGISTRATIONS),
            }

    if args.json:
        args.json.write_text(json.dumps({
            "run_documents": len(rows),
            "by_outcome": dict(by_outcome),
            "likely_account_count": {str(k): v for k, v in sorted(counts.items())},
            "likely_account_count_validated": {str(k): v for k, v in sorted(validated_counts.items())},
            "cohorts": {k: [s[:16] for s in v] for k, v in cohorts.items()},
            "skip_probe": skip_detail,
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

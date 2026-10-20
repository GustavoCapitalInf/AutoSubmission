"""l1s4_document_replay.py — the cohort proof at the seam PRODUCTION publishes from.

    python -m tools.l1s4_document_replay --group FAM:... [--shas <file>] [--parser <id>]

`tools/cohort_replay.py` replays `analyze_markdown` -> `report_to_dict`, which
is the ACCOUNT seam and was the production seam until L1-S3 moved the nine
`analyze_markdown` -> `report_to_dict` call sites onto `analyze_document` ->
`document_report_to_dict`. On every single-account document the two publish the
same bytes and the same ladder outcome, which is why `cohort_replay` remains the
control for the whole archive. On a document that publishes SEVERAL accounts
they cannot: the account seam answers about one account by contract, and the
document's outcome is a FOLD over all of them.

So a card that publishes the platform's first multi-account documents owes the
same measurement at the seam the runner actually reads, and this is it. It makes
the runner's own call — `document_report_to_dict(analyze_document(markdown,
parse_mode="deterministic", on_dispatch=..., sheets=...))` — classifies with
`telemetry.record.classify_document` and the runner's own `_failure_reason`, and
compares against the baseline outcome in the run of record's `rows.csv`.

WHAT IT REPORTS, per document and in total:

* the ladder movement — `newly validated` counted by the DETERMINISTIC VALIDATOR
  at this tree and never by a plan figure, with the per-ACCOUNT evidence line
  behind each one: `reconcile.ok`, the ADB's own `ok` and its basis and policy
  stamps, and the account's `classify_outcome`;
* the published account count, the omitted sections by CLASS, the internal
  transfers flagged and the document-scope notes;
* whether each account's own payload is what `classify_outcome` calls validated,
  which is what package membership is keyed on (Q1).

Read-only over the run of record and the cold cache; no OCR, no model, $0. It
prints shas, counts, class names, check names and booleans — never an amount, a
date, a description or a name.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import (  # noqa: E402
    ColdCache,
    DEFAULT_CENSUS,
    DEFAULT_DATA_DIR,
    DEFAULT_RUN_POINTER,
    load_baseline_rows,
    load_census,
    select_cohort,
)

LADDER = ("failed", "withheld", "review", "validated")


def _replay(markdown: str, pages: list[str]):
    """The runner's own call, and the runner's own classification."""
    from analysis.pipeline import analyze_document
    from analysis.serialization import document_report_to_dict
    from discovery.runner import DispatchCollector, _failure_reason
    from telemetry.record import classify_document

    collector = DispatchCollector()
    try:
        payload = document_report_to_dict(analyze_document(
            markdown, parse_mode="deterministic", on_dispatch=collector, sheets=pages))
    except Exception as exc:
        error_type = type(exc).__name__
        dispatch = collector.dispatch if collector.seen else None
        klass, reason = classify_document(
            None, error_type=error_type,
            error_reason=_failure_reason(error_type, dispatch))
        return None, klass, reason
    klass, reason = classify_document(payload)
    return payload, klass, reason


def _accounts(payload: dict) -> list[dict]:
    from analysis.payload_shape import payload_accounts

    return payload_accounts(payload, surface="tools/l1s4_document_replay.py")


def _evidence(account: dict) -> str:
    """The validator's own words about ONE account, as check names only."""
    from telemetry.record import classify_outcome

    klass, reason = classify_outcome(account)
    recon = account.get("reconciliation") or {}
    metrics = account.get("metrics") or {}
    adb = metrics.get("adb")
    if not isinstance(adb, dict):
        adb = {}
    checks = adb.get("validations") or {}
    failed = sorted(name for name, ok in checks.items() if ok is False)
    return (
        f"{klass}/{reason}"
        f" · reconcile.ok={bool(recon.get('ok'))}"
        f" · adb.ok={bool(adb.get('ok'))}"
        f" · basis={adb.get('underwriting_adb_basis')!r}"
        f" · policy={adb.get('underwriting_adb_policy')!r}"
        f" · posting_dates_cover_source={checks.get('posting_dates_cover_source')}"
        f" · calendar_days={metrics.get('calendar_day_count')}"
        f" · postings={len((account.get('statement') or {}).get('transactions') or [])}"
        f" · adb_checks_failed={failed or 'none'}"
    )


def _leaf_paths(node, prefix: str = ""):
    """(path, type-token) for every leaf, list indices collapsed to [*].

    PRIVACY: the TYPE of a leaf, never its value. `str` is printed for a
    printed reason token exactly as it is for anything else, so no document's
    own words can reach this output.
    """
    if isinstance(node, dict):
        for key in sorted(node):
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _leaf_paths(node[key], child)
    elif isinstance(node, list):
        if not node:
            yield (f"{prefix}[]", "empty-list")
        else:
            for item in node:
                yield from _leaf_paths(item, f"{prefix}[*]")
    else:
        yield (prefix, "null" if node is None else type(node).__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run")
    parser.add_argument("--run-pointer", default=str(DEFAULT_RUN_POINTER))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--census", default=str(DEFAULT_CENSUS))
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--parser", action="append", default=[])
    parser.add_argument("--folder", action="append", default=[])
    parser.add_argument("--shas")
    parser.add_argument("--leaves", action="store_true",
                        help="enumerate every leaf of the added `document` "
                             "block, per SHA (paths and type tokens only)")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    run = Path(args.run) if args.run else Path(
        Path(args.run_pointer).read_text(encoding="utf-8").strip())
    rows = load_baseline_rows(run)
    census = load_census(Path(args.census))
    cohort = select_cohort(args, rows, census)
    cache = ColdCache(Path(args.data_dir))

    leaves: dict[str, dict[str, str]] = {}
    newly_validated: list[tuple[str, list[str]]] = []
    regressions: list[str] = []
    other_movement: list[str] = []
    table: list[str] = []
    replayed = 0
    for sha in cohort:
        markdown, pages = cache.text(sha)
        if markdown is None:
            table.append(f"| `{sha[:16]}` | — | no cached text | | | | |")
            continue
        replayed += 1
        before = (rows[sha].get("outcome_class") or "").strip()
        payload, after, reason = _replay(markdown, pages)
        accounts = _accounts(payload) if payload else []
        block = (payload or {}).get("document") or {}
        omitted = [item.get("reason") for item in (block.get("omitted_sections") or [])]
        transfers = len(block.get("internal_transfers") or [])
        notes = block.get("integrity_notes") or []
        per_account = [_evidence(account) for account in accounts]
        if block:
            leaves[sha[:16]] = dict(_leaf_paths(block))
        table.append(
            f"| `{sha[:16]}` | {before} -> {after} ({reason}) | {len(accounts)} | "
            f"{', '.join(omitted) or '—'} | {transfers} | "
            f"{', '.join(notes) or '—'} |"
        )
        if before != "validated" and after == "validated":
            newly_validated.append((sha[:16], per_account))
        elif before == "validated" and after != "validated":
            regressions.append(f"{sha[:16]} {before} -> {after} ({reason})")
        elif before != after:
            other_movement.append(f"{sha[:16]} {before} -> {after} ({reason})")

    print("# L1-S4 — the cohort at the DOCUMENT seam\n")
    print("| document | ladder | published accounts | omitted sections (class) | "
          "internal transfers | document notes |")
    print("|---|---|---:|---|---:|---|")
    for line in table:
        print(line)

    print(f"\n* cohort: {len(cohort)} · replayed: {replayed}")
    print(f"* **newly validated: {len(newly_validated)}**")
    for sha16, evidence in newly_validated:
        print(f"  * `{sha16}` — {len(evidence)} published account(s)")
        for index, line in enumerate(evidence, start=1):
            print(f"    * account {index}: {line}")
    print(f"* other ladder movement: {len(other_movement)}")
    for line in other_movement:
        print(f"  * {line}")
    print(f"* **validated regressions (BLOCKING): {len(regressions)}**")
    for line in regressions:
        print(f"  * {line}")
    if args.leaves:
        print("\n## Every leaf of the added `document` block, per SHA")
        print("\nPaths and type tokens only; no value from any document "
              "appears here.\n")
        union: dict[str, str] = {}
        for sha16 in sorted(leaves):
            paths = leaves[sha16]
            union.update(paths)
            print(f"* `{sha16}` — {len(paths)} leaf/leaves")
            for path in sorted(paths):
                print(f"  - `{path}` -> {paths[path]}")
        print(f"\n* documents carrying the block: {len(leaves)}")
        print(f"* DISTINCT leaf paths across all of them: {len(union)}")
        for path in sorted(union):
            print(f"  - `{path}` -> {union[path]}")
        print(f"\nBLOCK_DOCUMENTS={len(leaves)} DISTINCT_LEAVES={len(union)}")

    print(f"\nCOHORT={len(cohort)} REPLAYED={replayed} "
          f"NEWLY_VALIDATED={len(newly_validated)} "
          f"OTHER_MOVEMENT={len(other_movement)} REGRESSIONS={len(regressions)}")
    return 2 if regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())

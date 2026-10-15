"""`python -m discovery` — the tranche plan, encoded as modes.

    python -m discovery --dry-run                 # the pinned 109, offline. The gate.
    python -m discovery --profile-only            # tranche 0: intake facts only
    python -m discovery --digital                 # tranche 1: digital-native, offline
    python -m discovery --scanned                 # tranche 2: + local Tesseract

Every mode is fully offline: no OCR endpoint, no model client constructed.
Tranche 2 adds the local Tesseract rung and nothing else.

The model-reading modes were removed with their rungs (owner ruling of
2026-10-13: the product uses no model): `--scanned-visual` (the local
Unlimited-OCR rung) in slice S2 of the model-code removal, and
`--scanned-paddle` (the PaddleOCR rung) and `--research-paddle` (a named
population read by Paddle into a research partition) in slice S5, together
with their flags (`--population`, `--research-partition`, `--data-dir`,
`--holdout-digest`, `--no-visual-escalation`). The flags no longer exist, and
`DiscoveryRunner` refuses the retired mode names.

Every run verifies the frozen archive baseline first and refuses to proceed if
the root has moved — tranche numbers are only comparable if every tranche
measured the same corpus.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from telemetry import JsonlSink, NullSink, new_run_id, telemetry_disabled

from .inventory import (
    DedupIndex,
    baseline_deviations,
    dry_run_deviations,
    enumerate_root,
)
from .report import summarize, write_hash_map, write_report, write_rows, write_summary
from .runner import (
    LOCAL_OCR_MODES,
    MODE_DIGITAL,
    MODE_DRY_RUN,
    MODE_PROFILE_ONLY,
    MODE_SCANNED,
    DiscoveryRunner,
)

DEFAULT_ROOT = Path("Bank Statements")
DEFAULT_OUT = Path("discovery_reports")


def _select(inventory, mode: str) -> list[str]:
    """Which documents this mode processes.

    The dry run is the pinned manifest and nothing else; every other mode is
    the discovery set, i.e. everything under the root that is NOT pinned. The
    partition is the manifest, exactly as the corpus gate scopes itself.
    """
    if mode == MODE_DRY_RUN:
        return list(inventory.pinned)
    return list(inventory.discovery)


def run(
    root: Path,
    mode: str,
    out_dir: Path,
    *,
    limit: int | None = None,
    skip_baseline: bool = False,
    use_cache: bool = True,
    progress=None,
) -> dict:
    inventory = enumerate_root(root)
    # The dry run is scoped to the pinned manifest, so it checks the truth set
    # rather than the archive: it has to be runnable in a clean checkout, which
    # is where the runner gets proved before the archive is ever touched. Every
    # tranche mode checks the frozen archive itself.
    if skip_baseline:
        deviations = []
    elif mode == MODE_DRY_RUN:
        deviations = dry_run_deviations(inventory)
    else:
        deviations = baseline_deviations(inventory)
    if deviations:
        raise SystemExit(
            "discovery: the corpus root does not match its expected baseline.\n"
            + "\n".join(f"  - {line}" for line in deviations)
            + "\n\nThe archive was frozen on 2026-08-06 and is the discovery corpus of "
              "record. Re-freeze and re-baseline deliberately, or pass --skip-baseline "
              "for a scoped run whose numbers are NOT comparable to a tranche."
        )

    run_id = new_run_id()
    run_dir = out_dir / run_id.replace(":", "").replace("+", "-")
    sink = NullSink() if telemetry_disabled() else JsonlSink(run_dir / "telemetry.jsonl")

    cache = None
    if use_cache and mode != MODE_PROFILE_ONLY:
        # D-3's module API is Flask-free by design, which is what makes it
        # usable from a CLI: identical content under identical settings is
        # never re-read or re-analysed across tranches.
        from webapp.artifact_cache import open_cache

        cache = open_cache()

    selected = _select(inventory, mode)
    if limit is not None:
        selected = selected[:limit]

    runner = DiscoveryRunner(
        root, mode=mode, run_id=run_id, sink=sink, cache=cache,
        dedup=DedupIndex.with_pinned_corpus(),
    )

    rows = []
    for index, relative_path in enumerate(selected, 1):
        rows.append(runner.process(
            relative_path, inventory.folder_label(relative_path),
            disk_relative_path=inventory.disk_spelling(relative_path),
        ))
        if progress is not None:
            progress(index, len(selected), relative_path)

    cache_stats = {}
    if cache is not None:
        try:
            cache_stats = cache.stats()
        except Exception:
            cache_stats = {}

    # `escalation_budget` / `escalations_used` stay summary keys (plan D19:
    # every `summary.json` key stays) at the values every run without an
    # escalation mode always reported: unbounded and none used. The budget was
    # the retired Paddle mode's pre-run ceiling (slice S5).
    summary = summarize(
        rows, mode=mode, run_id=run_id, inventory=inventory, cache_stats=cache_stats,
        escalation_budget=None, escalations_used=0,
    )
    write_rows(run_dir / "rows.csv", rows)
    write_hash_map(run_dir / "hash_map.csv", rows)
    write_summary(run_dir / "summary.json", summary)
    write_report(run_dir / "report.txt", summary)
    summary["output_dir"] = str(run_dir)
    summary["_rows"] = rows
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m discovery",
        description="Discovery runner: intake, dispatch and outcome over a PDF corpus.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="The pinned 109 only. Offline. The acceptance gate.")
    mode.add_argument("--profile-only", action="store_true",
                      help="Tranche 0: intake profile, dedup and counts. No parsing.")
    mode.add_argument("--digital", action="store_true",
                      help="Tranche 1: the discovery set through the offline rungs.")
    mode.add_argument("--scanned", action="store_true",
                      help="Tranche 2: as --digital plus the local Tesseract rung.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Corpus root.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Report directory.")
    parser.add_argument("--limit", type=int, help="Process at most N documents.")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the D-3 cache.")
    parser.add_argument("--skip-baseline", action="store_true",
                        help="Do not verify the frozen archive baseline. Scoped runs only.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    selected_mode = (
        MODE_DRY_RUN if args.dry_run
        else MODE_PROFILE_ONLY if args.profile_only
        else MODE_DIGITAL if args.digital
        else MODE_SCANNED
    )

    if selected_mode in LOCAL_OCR_MODES:
        import shutil

        if shutil.which("tesseract") is None:
            print(f"discovery: --{selected_mode} needs a local tesseract binary on PATH",
                  file=sys.stderr)
            return 2

    def progress(index: int, total: int, relative_path: str) -> None:
        if not args.quiet:
            print(f"{index}/{total} {relative_path}", file=sys.stderr, flush=True)

    summary = run(
        Path(args.root), selected_mode, Path(args.out),
        limit=args.limit, skip_baseline=args.skip_baseline,
        use_cache=not args.no_cache,
        progress=progress,
    )
    summary.pop("_rows", None)
    from .report import render_report

    print(render_report(summary))
    print(f"\nwritten to {summary['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""`python -m discovery` — the tranche plan, encoded as modes.

    python -m discovery --dry-run                 # the pinned 109, offline. The gate.
    python -m discovery --profile-only            # tranche 0: intake facts only
    python -m discovery --digital                 # tranche 1: digital-native, offline
    python -m discovery --scanned                 # tranche 2: + local Tesseract
    python -m discovery --scanned-visual          # tranche 3: + the visual rung

Tranche 0 and 1 are fully offline: no OCR endpoint, no Gemini, no model client
constructed. Tranche 2 adds the local Tesseract rung and nothing else.

Tranche 3 (`--scanned-visual`, W3-5) is tranche 2 with the ladder's last rung
enabled: the LOCAL Unlimited-OCR server on our own GPU. Still no paid vendor,
still no Gemini — the visual rung is the same one the webapp uses, reached
through the same production ladder. Because that rung needs a server, the mode
PROBES it before enumerating a single document and refuses to start if it is not
usable: a batch of thousands must not discover the endpoint is down on document
1 and then report 3,505 identical failures. A server that dies mid-run fails
THAT document closed and the run continues.

Every run verifies the frozen archive baseline first and refuses to proceed if
the root has moved — tranche numbers are only comparable if every tranche
measured the same corpus.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ocr.availability import probe_visual_ocr
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
    MODE_SCANNED_VISUAL,
    DiscoveryRunner,
    estimate_class_a_population,
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
    visual_escalation: bool = True,
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

    # P20-ROUTER item 2f. A cheap, read-only preflight upper bound on how many
    # documents THIS run could ever legally escalate — computed before a
    # single extractor runs, over exactly the documents this run will visit.
    # `None` (unbounded) everywhere else: the ceiling exists to bound a
    # `--scanned-visual` run's own GPU spend against a population it measured
    # itself, not to change any other mode's behaviour.
    escalation_budget = None
    if mode == MODE_SCANNED_VISUAL and visual_escalation:
        escalation_budget = estimate_class_a_population(
            root, selected, disk_spelling=inventory.disk_spelling,
        )

    runner = DiscoveryRunner(
        root, mode=mode, run_id=run_id, sink=sink, cache=cache,
        dedup=DedupIndex.with_pinned_corpus(),
        visual_escalation=visual_escalation,
        escalation_budget=escalation_budget,
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

    summary = summarize(
        rows, mode=mode, run_id=run_id, inventory=inventory, cache_stats=cache_stats,
        escalation_budget=runner.escalation_budget, escalations_used=runner.escalations_used,
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
    mode.add_argument("--scanned-visual", action="store_true",
                      help="Tranche 3: as --scanned plus the LOCAL visual-OCR rung "
                           "($0 vendor). Probes the endpoint before starting.")
    parser.add_argument("--no-visual-escalation", action="store_true",
                        help="--scanned-visual only: use the visual rung solely to "
                             "recover documents the offline rungs could not read at "
                             "all; do not re-read unclaimed Tesseract output.")
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
        else MODE_SCANNED_VISUAL if args.scanned_visual
        else MODE_SCANNED
    )
    if args.no_visual_escalation and selected_mode != MODE_SCANNED_VISUAL:
        # Refuse rather than ignore: silently accepting it would let an operator
        # believe a policy was applied to a mode that has no visual rung at all.
        print("discovery: --no-visual-escalation applies to --scanned-visual only",
              file=sys.stderr)
        return 2

    if selected_mode in LOCAL_OCR_MODES:
        import shutil

        if shutil.which("tesseract") is None:
            print(f"discovery: --{selected_mode} needs a local tesseract binary on PATH",
                  file=sys.stderr)
            return 2

    if selected_mode == MODE_SCANNED_VISUAL:
        # Fail BEFORE enumerating: an unusable endpoint is an operator problem,
        # and discovering it per-document would turn one configuration mistake
        # into thousands of recorded failures. This costs one GET /v1/models and
        # zero GPU time.
        status = probe_visual_ocr()
        if not status.usable:
            print(f"discovery: --scanned-visual cannot start. {status.message()}",
                  file=sys.stderr)
            print("  start the local server (python local_ocr_server.py) or point "
                  "OCR_BASE_URL/OCR_MODEL at it, then re-run.", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"discovery: {status.message()}", file=sys.stderr)

    def progress(index: int, total: int, relative_path: str) -> None:
        if not args.quiet:
            print(f"{index}/{total} {relative_path}", file=sys.stderr, flush=True)

    summary = run(
        Path(args.root), selected_mode, Path(args.out),
        limit=args.limit, skip_baseline=args.skip_baseline,
        use_cache=not args.no_cache,
        visual_escalation=not args.no_visual_escalation,
        progress=progress,
    )
    summary.pop("_rows", None)
    from .report import render_report

    print(render_report(summary))
    print(f"\nwritten to {summary['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

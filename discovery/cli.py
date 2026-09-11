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
import json
import os
import sys
from pathlib import Path

from ocr.availability import probe_visual_ocr
from ocr.paddle_client import probe as probe_paddle_ocr
from ocr.paddle_config import (
    PADDLE_CUSTOMER_DATA_OPT_IN_ENV,
    PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL,
    PADDLE_REMOTE_OPT_IN_ENV,
    PADDLE_REMOTE_OPT_IN_LITERAL,
)
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
    MODE_RESEARCH_PADDLE,
    MODE_SCANNED,
    MODE_SCANNED_PADDLE,
    MODE_SCANNED_VISUAL,
    RESEARCH_PARTITION_PATTERN,
    DiscoveryRunner,
    estimate_class_a_population,
    holdout_sha16s_from_digest,
    read_population,
    refuse_production_data_dir,
)

DEFAULT_ROOT = Path("Bank Statements")
DEFAULT_OUT = Path("discovery_reports")

#: The ONE holdout artefact runtime code may read (the leakage firewall). See
#: `discovery.runner.holdout_sha16s_from_digest`.
DEFAULT_HOLDOUT_DIGEST = (
    Path(__file__).resolve().parents[1]
    / "docs" / "moneythumb-replacement" / "truth" / "MANIFEST_DIGEST.txt"
)


def _select(inventory, mode: str) -> list[str]:
    """Which documents this mode processes.

    The dry run is the pinned manifest and nothing else; every other mode is
    the discovery set, i.e. everything under the root that is NOT pinned. The
    partition is the manifest, exactly as the corpus gate scopes itself.
    """
    if mode == MODE_DRY_RUN:
        return list(inventory.pinned)
    return list(inventory.discovery)


def _write_research_provenance(run_dir: Path, mode: str, research_partition: str) -> None:
    """The minimum `provenance.json` that makes a research run REFUSABLE.

    D7. `telemetry/run_of_record.py` reads a run's recorded partitions and
    raises `ResearchPartitionRefused` the moment it sees a non-empty
    `research_partition` — but only if the block is there to read. A research
    run that wrote no provenance at all would be RECONSTRUCTED instead, from
    its stage versions and its mode, into a production-shaped record: the
    refusal would never fire and a research artifact could be selected as
    historical truth. So the runner writes the block itself, for research runs
    ONLY: a production run's `provenance.json` is still written by
    `tools/train/provenance.py` (the full host/toolchain/tree record), and
    nothing here changes what a production run produces.

    The three fields the reader requires before it looks at the partition
    (`offline_ocr_key`, `analysis_key`, `mode`) are computed from THIS run's
    actual flags, so the record describes the run rather than a default.
    """
    from webapp.artifact_cache import (
        ANALYSIS_STAGE_VERSION,
        OCR_STAGE_VERSION,
        analysis_settings_key,
        ocr_settings_key,
    )

    partitions = {
        "offline_ocr_key": ocr_settings_key(
            force_ocr=False, allow_local_ocr=mode in LOCAL_OCR_MODES,
            allow_visual_ocr=False, research_partition=research_partition,
        ),
        "analysis_key": analysis_settings_key(parse_mode="deterministic"),
        "mode": mode,
        "research_partition": research_partition,
    }
    # The Paddle partition key is deliberately NOT computed here.
    # `tests/test_paddle_routing.py` pins the exact set of call sites that may
    # name the Paddle capability flag, so that a Paddle READ can never appear
    # at a site nobody reviewed. This function would only be computing a
    # partition KEY, not reading anything — but weakening a pin whose whole
    # value is "this list is short and reviewed" to record one optional field
    # is a bad trade, and the field IS optional: `telemetry/run_of_record.py`
    # refuses this run on `research_partition` alone, before it reads any key.
    # An operator who wants the full provenance of a research run has
    # `tools/train/provenance.py --research-partition`, which is the reviewed
    # instrument for exactly that and already carries the pinned call site.
    partitions["paddle_ocr_key_note"] = (
        "not recorded here; run tools/train/provenance.py --research-partition for the "
        "full record (the reviewed instrument for a research run's provenance)"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "provenance.json").write_text(
        json.dumps(
            {
                "run_of_record": {"partitions": partitions},
                "tree": {
                    "OCR_STAGE_VERSION": OCR_STAGE_VERSION,
                    "ANALYSIS_STAGE_VERSION": ANALYSIS_STAGE_VERSION,
                    "analysis_settings_key_deterministic": partitions["analysis_key"],
                },
                "note": "a RESEARCH run; telemetry/run_of_record.py refuses it as historical truth",
            },
            indent=2, sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


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
    data_dir: Path | None = None,
    population: frozenset[str] | None = None,
    research_partition: str = "",
    holdout_sha16: frozenset[str] = frozenset(),
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

        # D7: a research run writes to its OWN directory, refused at the door
        # if it is (or is inside) a production or historical cache.
        cache = open_cache(data_dir) if data_dir is not None else open_cache()

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
    if mode in (MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE) and visual_escalation:
        escalation_budget = estimate_class_a_population(
            root, selected, disk_spelling=inventory.disk_spelling,
        )

    runner = DiscoveryRunner(
        root, mode=mode, run_id=run_id, sink=sink, cache=cache,
        dedup=DedupIndex.with_pinned_corpus(),
        visual_escalation=visual_escalation,
        escalation_budget=escalation_budget,
        population=population,
        research_partition=research_partition,
        holdout_sha16=holdout_sha16,
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
        research_partition=research_partition,
    )
    write_rows(run_dir / "rows.csv", rows)
    write_hash_map(run_dir / "hash_map.csv", rows)
    write_summary(run_dir / "summary.json", summary)
    write_report(run_dir / "report.txt", summary)
    if research_partition:
        _write_research_provenance(run_dir, mode, research_partition)
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
    mode.add_argument("--scanned-paddle", action="store_true",
                      help="P21-ROUTING (Phase 2.1): as --scanned plus the PaddleOCR "
                           "escalation rung in place of the visual one. Probes the "
                           "worker before starting; a real archive run is REFUSED at "
                           "the rung with remote_customer_data_refused (D8) unless "
                           "Gustavo has separately authorized the remote-data run.")
    mode.add_argument("--research-paddle", action="store_true",
                      help="P22-TRUTHTABLE (Phase 2.2, D7/D8): read the operator's NAMED "
                           "population with PaddleOCR through the router, regardless of "
                           "profile, into a research partition no run of record can select. "
                           "REQUIRES --population, --research-partition and --data-dir, and "
                           "both remote-paid opt-in literals in this process's environment. "
                           "Not a coverage mode: research admission and production admission "
                           "are different concepts.")
    parser.add_argument("--population", default=None,
                        help="--research-paddle only: a file of 64-hex content shas "
                             "('#' comments allowed). The set that will be studied.")
    parser.add_argument("--research-partition", default=None,
                        help=f"--research-paddle only: the partition id, matching "
                             f"{RESEARCH_PARTITION_PATTERN}. It is OCR-key material, so the "
                             f"run's artifacts can never collide with production's and "
                             f"telemetry/run_of_record.py refuses the run as historical truth.")
    parser.add_argument("--data-dir", default=None,
                        help="--research-paddle only: the artifact cache directory this run "
                             "writes to. A production or cold-cache directory is refused.")
    parser.add_argument("--holdout-digest", default=None,
                        help="--research-paddle only: the repository holdout digest to check "
                             "the population against (default: the committed MANIFEST_DIGEST).")
    parser.add_argument("--no-visual-escalation", action="store_true",
                        help="--scanned-visual / --scanned-paddle only: use the "
                             "escalation rung solely to recover documents the "
                             "offline rungs could not read at all; do not re-read "
                             "unclaimed Tesseract output.")
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
        else MODE_SCANNED_PADDLE if args.scanned_paddle
        else MODE_RESEARCH_PADDLE if args.research_paddle
        else MODE_SCANNED
    )

    # ----------------------------------------------------------------------
    # P22-TRUTHTABLE (D7/D8, case 23): the research mode's doors, ALL of them
    # up front, before the corpus is enumerated and before a single document
    # is read. A research run that discovered its own misconfiguration on
    # document 1 would leave a partial partition behind and thousands of
    # identical refusals in a report; and an operator who typed the wrong
    # `--data-dir` must be told so, not obeyed. These checks run BEFORE the
    # toolchain probes below on purpose: a missing authorization is a refusal
    # this tree makes on its own, and it must not be able to hide behind a
    # missing binary.
    # ----------------------------------------------------------------------
    research_flags = {
        "--population": args.population,
        "--research-partition": args.research_partition,
        "--data-dir": args.data_dir,
        "--holdout-digest": args.holdout_digest,
    }
    if selected_mode != MODE_RESEARCH_PADDLE:
        given = sorted(flag for flag, value in research_flags.items() if value is not None)
        if given:
            print(f"discovery: {', '.join(given)} is --research-paddle only", file=sys.stderr)
            return 2

    population: frozenset[str] | None = None
    holdout_sha16: frozenset[str] = frozenset()
    if selected_mode == MODE_RESEARCH_PADDLE:
        missing_literals = [
            name for name, literal in (
                (PADDLE_REMOTE_OPT_IN_ENV, PADDLE_REMOTE_OPT_IN_LITERAL),
                (PADDLE_CUSTOMER_DATA_OPT_IN_ENV, PADDLE_CUSTOMER_DATA_OPT_IN_LITERAL),
            )
            if os.environ.get(name) != literal
        ]
        if missing_literals:
            # The names, never the literals: a refusal message is not the
            # place to publish the tokens that lift it.
            print(
                "discovery: --research-paddle cannot start. Remote-paid PaddleOCR on customer "
                "documents is EXPLICITLY opted into and never defaulted; this process's "
                "environment is missing the exact authorized value of "
                + " and ".join(missing_literals),
                file=sys.stderr,
            )
            return 2
        for flag in ("--population", "--research-partition", "--data-dir"):
            if research_flags[flag] is None:
                print(f"discovery: --research-paddle requires {flag}", file=sys.stderr)
                return 2
        import re as _re

        if _re.fullmatch(RESEARCH_PARTITION_PATTERN, args.research_partition) is None:
            print(
                f"discovery: --research-partition must match {RESEARCH_PARTITION_PATTERN}",
                file=sys.stderr,
            )
            return 2
        try:
            refuse_production_data_dir(Path(args.data_dir))
        except ValueError as exc:
            print(f"discovery: {exc}", file=sys.stderr)
            return 2
        try:
            population = read_population(Path(args.population))
        except ValueError as exc:
            print(f"discovery: {exc}", file=sys.stderr)
            return 2
        digest = Path(args.holdout_digest) if args.holdout_digest else DEFAULT_HOLDOUT_DIGEST
        try:
            holdout_sha16 = holdout_sha16s_from_digest(digest)
        except ValueError as exc:
            print(f"discovery: {exc}", file=sys.stderr)
            return 2
        overlap = sum(1 for sha in population if sha[:16] in holdout_sha16)
        if overlap:
            # The COUNT, never the shas: naming them here would put holdout
            # identities in an operator's console and in whatever log catches
            # it, which is most of what an unseen holdout is protecting.
            print(
                f"discovery: --research-paddle refuses this population: {overlap} of its "
                "documents are in the holdout manifest. An opened holdout item is no longer "
                "unseen; remove them from the population deliberately, or study a different set.",
                file=sys.stderr,
            )
            return 2

    if args.no_visual_escalation and selected_mode not in (MODE_SCANNED_VISUAL, MODE_SCANNED_PADDLE):
        # Refuse rather than ignore: silently accepting it would let an operator
        # believe a policy was applied to a mode that has no escalation rung at all.
        print(
            "discovery: --no-visual-escalation applies to --scanned-visual / "
            "--scanned-paddle only",
            file=sys.stderr,
        )
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

    if selected_mode == MODE_SCANNED_PADDLE:
        # P21-ROUTING: the SAME preflight discipline as --scanned-visual,
        # mirrored onto the Paddle worker (config / opt-in / version / health)
        # rather than the visual endpoint. Never prints a host — `probe()`
        # names only a closed refusal token. `probe_paddle_ocr` is imported
        # at MODULE level (mirroring `probe_visual_ocr` above) precisely so
        # a test can monkeypatch `cli.probe_paddle_ocr` the same way it
        # already monkeypatches `cli.probe_visual_ocr` (MINOR-4).
        paddle_status = probe_paddle_ocr()
        if not paddle_status.available:
            print(f"discovery: --scanned-paddle cannot start. {paddle_status.reason}",
                  file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"discovery: paddle worker ok ({paddle_status.reason})", file=sys.stderr)

    def progress(index: int, total: int, relative_path: str) -> None:
        if not args.quiet:
            print(f"{index}/{total} {relative_path}", file=sys.stderr, flush=True)

    summary = run(
        Path(args.root), selected_mode, Path(args.out),
        limit=args.limit, skip_baseline=args.skip_baseline,
        use_cache=not args.no_cache,
        visual_escalation=not args.no_visual_escalation,
        progress=progress,
        data_dir=Path(args.data_dir) if args.data_dir else None,
        population=population,
        research_partition=args.research_partition or "",
        holdout_sha16=holdout_sha16,
    )
    summary.pop("_rows", None)
    from .report import render_report

    print(render_report(summary))
    print(f"\nwritten to {summary['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

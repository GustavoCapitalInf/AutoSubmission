"""Recompute the archive's analyses at HEAD and compare them to what a run published.

W3 §REGFP's zero-movement instrument, committed so the sweep is reproducible by
review rather than described in a log. The question it answers is narrow and is
the one a cache-key change owes an answer to: **does any document's published
analysis differ from what the run of record stored for it?**

    python -m tools.regfp_zero_movement_sweep \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        [--run <run dir>] [--start 0 --end 3380] [--out sweep.json]

READ-ONLY. Nothing is written to the archive or the artifact store; the
`webapp_data` sqlite index is opened `mode=ro` ONLY to resolve and verify each
document's own run-of-record OCR partition (below) — never to write. It makes
no model call and costs $0.00: `parse_mode="deterministic"` cannot reach the
extraction branch.

WHICH OCR ARTIFACT A DOCUMENT IS READ FROM, and why it is not a guess
(P20-ARTIFACTS closure MAJOR-2). A document can hold more than one cached OCR
artifact — one per capability partition of `ocr_settings_key` — and picking
the wrong one hands the analysis text the run never analysed. WORKER-PRIVACY's
sweep measured that trap on this archive: 55 of the 3,380 were read under a
partition holding a re-read text preparation, and feeding those the plain
native text manufactured two false movers. This tool used to "fix" that by
enumerating every one of the eight live capability-boolean combinations and
keeping whichever reconstruction resolved the run's own stored payload — a
correspondence proof, not an ordering, but still keyed on `ocr_settings_key()`
at the LIVE `OCR_STAGE_VERSION`, which the v4->v5 bump made permanently unable
to match the frozen batch-8/9 archives' v4-keyed artifacts (every document
would silently fall into `no_ocr_artifact`). It now resolves through
`telemetry.run_of_record` — the SAME policy `tools/cohort_replay.py` and
`telemetry/stated_counts.py::_ArtifactJoin` adopted — keyed on each sha's OWN
row in `--run`'s `rows.csv` (`source_path` / `visual_rung`), never an
enumeration: one deterministic partition per document, with no choice left to
make. `--baseline-settings-key` is unchanged by this: it names the ANALYSIS
side's explicit historical key (see below), which was never enumerated or
guessed.

**`--baseline-settings-key` is the analysis settings key the run wrote under**,
and it is an argument rather than a computation because the whole point of a
cache-key card is that today's key is NOT that key. §REGFP compared against
`205EB02A2C4B0A69D2AFA289F7A70B9EC81DED1004B97717751DFA64482EE9AF`, which is
`SHA256_UPPER(canonical_json({stage_version: 13, parse_mode: "deterministic",
model, escalation_model, withholding_denominator_mode}))` — the v13 composition
with no `parser_registry` and no `generic_structurer` field.

WHAT THE DOCUMENT CLASSES MEAN in the output:

* `identical` / `moved` — a payload existed under the baseline key and the
  recompute matches it byte for byte, or does not. `moved` names the document by
  `content_sha256` and lists the differing top-level fields, and nothing else:
  no document text, no filename, no amount.
* `no_payload_raises_again` — no payload existed (the analysis raised:
  unclaimed, ambiguous, or a parser crash; failures are never cached, by
  `webapp/artifact_cache.py`'s contract) and the recompute raises again. The
  exception CLASS is not compared, because the run stored none to compare
  against; equality of it is an argument, not a measurement — see the note in
  W3 §REGFP RF5.
* `no_payload_now_publishes` / `payload_now_raises` — the two ways the boundary
  between publishing and refusing can move. Both are findings and both are
  named.
* `no_ocr_artifact` — no OCR payload holding a document under ANY capability
  partition: the `invalid_pdf` refusals (no artifact at all) and the deferred
  scans (a cached NEGATIVE OCR result, which is a real cached fact and not a
  miss).

`--start`/`--end` slice the sorted distinct `content_sha256` so a long sweep can
be run in chunks; each chunk writes its own report and the counts add.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

#: Read by :func:`_resolve_run` when ``--run`` is not given (P20-ARTIFACTS
#: closure MAJOR-2 — the same default the two privacy scanners use).
DEFAULT_RUN_POINTER = Path("discovery_reports/train9-logs/train9_run_dir.txt")


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _resolve_run(run: Path | None) -> Path:
    if run is not None:
        return run
    if not DEFAULT_RUN_POINTER.is_file():
        raise SystemExit(
            f"--run not given and the default pointer {DEFAULT_RUN_POINTER} is missing"
        )
    return Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path, help="the webapp_data directory")
    parser.add_argument(
        "--baseline-settings-key",
        required=True,
        help="the analysis settings key the run's payloads were written under",
    )
    parser.add_argument("--run", type=Path, default=None,
                        help="the discovery run of record whose rows.csv names each sha's own "
                             f"OCR provenance (default: the pointer file at {DEFAULT_RUN_POINTER})")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write the full report here")
    args = parser.parse_args(argv)
    args.run = _resolve_run(args.run)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import sqlite3

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown
    from telemetry.run_of_record import (
        RunOfRecordError,
        ocr_partition_for_row,
        partitions_for_run,
        select_artifact,
    )
    from webapp.artifact_cache import STAGE_ANALYSIS, analysis_input_sha, cache_key

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"

    outcome_by_sha: dict[str, str] = {}
    row_by_sha: dict[str, dict] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha:
                outcome_by_sha.setdefault(sha, row["outcome_class"])
                row_by_sha.setdefault(sha, row)
    shas = sorted(outcome_by_sha)[args.start : args.end]

    conn = sqlite3.connect(f"file:{(args.data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
    try:
        try:
            partitions = partitions_for_run(args.run, conn=conn)
        except RunOfRecordError as exc:
            print(f"artifact-selection policy failed: {exc}", file=sys.stderr)
            return 5

        counts = {
            "compared_payload": 0,
            "identical": 0,
            "moved": 0,
            "no_ocr_artifact": 0,
            "no_payload_raises_again": 0,
            "no_payload_now_publishes": 0,
            "payload_now_raises": 0,
        }
        findings: list[dict[str, object]] = []
        started = time.perf_counter()

        for sha in shas:
            # ONE partition, named by THIS sha's own row (P20-ARTIFACTS
            # closure MAJOR-2) — never an enumeration, never a choice. See
            # the module docstring.
            row = row_by_sha.get(sha)
            key = ocr_partition_for_row(row, partitions) if row is not None else None
            path = select_artifact(conn, "ocr", sha, key) if key else None
            markdown = pages = None
            if path is not None:
                try:
                    payload = json.loads((root / path).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    payload = None
                document = (payload.get("artifact") or {}).get("document") if payload else None
                if isinstance(document, dict):
                    pages = [str(page) for page in (document.get("pages") or [])]
                    markdown = StatementMarkdown(
                        source_file="sweep.pdf", model=str(document.get("model") or ""), pages=pages
                    ).to_markdown()
            if markdown is None:
                # No resolvable artifact under this row's own partition: a
                # cached NEGATIVE OCR result (the deferred scans — a real
                # cached fact, not a miss, and no text to analyse) or no
                # cached artifact at all.
                counts["no_ocr_artifact"] += 1
                continue

            composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(markdown, pages), baseline)
            stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
            before = None
            if stored.exists():
                try:
                    before = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
                except (OSError, ValueError, KeyError):
                    before = None

            try:
                after = report_to_dict(
                    analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
                )
                raised = None
            except Exception as exc:
                after, raised = None, type(exc).__name__

            if before is None:
                if raised is not None:
                    counts["no_payload_raises_again"] += 1
                else:
                    counts["no_payload_now_publishes"] += 1
                    findings.append(
                        {
                            "content_sha256": sha,
                            "verdict": "no_payload_now_publishes",
                            "outcome_class": outcome_by_sha[sha],
                        }
                    )
                continue

            counts["compared_payload"] += 1
            if raised is not None:
                counts["payload_now_raises"] += 1
                findings.append(
                    {
                        "content_sha256": sha,
                        "verdict": "payload_now_raises",
                        "exception": raised,
                        "outcome_class": outcome_by_sha[sha],
                    }
                )
            elif canonical(before) == canonical(after):
                counts["identical"] += 1
            else:
                counts["moved"] += 1
                findings.append(
                    {
                        "content_sha256": sha,
                        "verdict": "moved",
                        "outcome_class": outcome_by_sha[sha],
                        # FIELD NAMES only. A diff of the values would print the
                        # statement's own figures into a report.
                        "fields": sorted(
                            field
                            for field in set(before) | set(after)
                            if canonical(before.get(field)) != canonical(after.get(field))
                        ),
                    }
                )
    finally:
        conn.close()

    report = {
        "range": [args.start, args.end],
        "documents": len(shas),
        "seconds": round(time.perf_counter() - started, 1),
        **counts,
        "findings": findings,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(canonical({key: value for key, value in report.items() if key != "findings"}))
    for finding in findings:
        print(canonical(finding))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

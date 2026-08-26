"""Replay a NAMED population through the real pipeline and report its outcomes.

W3 §COREENC's coverage instrument, committed so the card's headline numbers are
reproducible by review rather than described in a log. The question it answers
is the one a new registration owes: **what outcome does each named document
reach at HEAD, and what did the run of record record for it?**

    python -m tools.coreenc_family_replay \\
        --rows <reports>/<run-id>/rows.csv \\
        --data-dir <checkout>/webapp_data \\
        --shas <file with one content_sha256 per line> \\
        [--parser core_processor_enclosures] [--out replay.json]

It is the same read as `tools/regfp_zero_movement_sweep.py` one stage further
on: that instrument compares the stored analysis PAYLOAD byte for byte and is
the zero-movement proof; this one asks the pipeline for the OUTCOME CLASS the
discovery report ranks by (`validated` / `review` / `withheld` / `failed`), so
a card can say what its population moved TO rather than only that it moved.
Both are needed and neither substitutes for the other.

READ-ONLY in the same two ways. Nothing is written to the archive or the
artifact store; the `webapp_data` sqlite index is never opened — OCR payloads
are reached by DIRECT file path across every capability partition of
`ocr_settings_key`, and the longest reconstruction wins, which is the same
selection `doc_text`-style helpers use for a text-only read. It makes no model
call and costs $0.00: `parse_mode="deterministic"` cannot reach the extraction
branch.

**No document text, amount, name, account number or date is printed.** The
output names a document by `content_sha256` and carries only its outcome
class, its outcome reason, the parser that claimed it and three counts.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path,
                        help="the webapp_data directory")
    parser.add_argument("--shas", required=True, type=Path,
                        help="the named population, one content_sha256 per line")
    parser.add_argument("--parser", default=None,
                        help="report whether THIS registration claimed each document")
    parser.add_argument("--out", type=Path, default=None,
                        help="write the full report here")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from analysis.parser_registry import resolve
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from discovery.runner import _failure_reason
    from ocr.document import StatementMarkdown
    from telemetry.record import classify_outcome
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    csv.field_size_limit(10_000_000)
    recorded: dict[str, tuple[str, str, str]] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row["content_sha256"] or "").upper()
            if sha:
                recorded.setdefault(sha, (row["outcome_class"], row["outcome_reason"],
                                          row["parser_id"] or ""))
    named = [line.strip().upper() for line in
             args.shas.read_text(encoding="utf-8").split() if line.strip()]

    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for sha in named:
        best: tuple[str, list[str]] | None = None
        for key in ocr_keys:
            composed = cache_key(STAGE_OCR, sha, key)
            path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            document = (payload.get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            pages = [str(page) for page in (document.get("pages") or [])]
            markdown = StatementMarkdown(
                source_file="replay.pdf", model=str(document.get("model") or ""),
                pages=pages,
            ).to_markdown()
            if best is None or len(markdown) > len(best[0]):
                best = (markdown, pages)
        was = recorded.get(sha, ("(not in the run)", "", ""))
        if best is None:
            rows.append({"content_sha256": sha, "outcome_class": "no_ocr_artifact",
                         "was_outcome_class": was[0], "was_outcome_reason": was[1]})
            continue
        markdown, pages = best
        dispatch = resolve(markdown)
        try:
            payload = report_to_dict(
                analyze_markdown(markdown, parse_mode="deterministic", sheets=pages))
            error_type = None
        except Exception as exc:  # noqa: BLE001 — a crash is a finding, not a stop
            payload, error_type = None, type(exc).__name__
        outcome, reason = classify_outcome(
            payload, error_type=error_type,
            error_reason=_failure_reason(error_type, dispatch))
        statement = (payload or {}).get("statement") or {}
        rows.append({
            "content_sha256": sha,
            "outcome_class": outcome,
            "outcome_reason": reason or "",
            # From the DISPATCH, which is where the claimant is reported.
            # `analysis.serialization.report_to_dict` has no top-level
            # `parser_id` key — its keys are `statement`, `classifications`,
            # `reconciliation`, `metrics`, `detection`, `quality`, `integrity`,
            # `model_used`, `escalated` — so reading it from the payload made
            # this column the empty string on every document, including the
            # ones the instrument reported as validated. A silent null in a
            # measurement column is worse than no column at all.
            "parser_id": dispatch.parser_id or "",
            "claimed_by_named_parser": (
                args.parser in [candidate for candidate, _score in dispatch.candidates]
                if args.parser else None),
            "transactions": len(statement.get("transactions") or []),
            "daily_balances": len(statement.get("stated_daily_balances") or []),
            "was_outcome_class": was[0],
            "was_outcome_reason": was[1],
            "was_parser_id": was[2],
        })

    moved = [row for row in rows
             if (row.get("outcome_class"), row.get("outcome_reason", "")) !=
                (row.get("was_outcome_class"), row.get("was_outcome_reason"))]
    summary: dict[str, object] = {
        "named": len(named),
        "seconds": round(time.perf_counter() - started, 1),
        "moved": len(moved),
        "unmoved": len(rows) - len(moved),
    }
    tally: dict[str, int] = {}
    for row in rows:
        key = f'{row.get("was_outcome_class")}/{row.get("was_outcome_reason")}' \
              f' -> {row.get("outcome_class")}/{row.get("outcome_reason", "")}'
        tally[key] = tally.get(key, 0) + 1
    report = {"summary": summary, "transitions": dict(sorted(tally.items())), "rows": rows}
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    json.dump({"summary": summary, "transitions": report["transitions"]},
              sys.stdout, indent=1)
    print()
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

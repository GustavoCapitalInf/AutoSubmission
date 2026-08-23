"""Replay a named population through THIS tree's analysis — W3 §WELCH.

The closure proof a registration owes its own family: every document the card
names, analysed at the branch's HEAD in `deterministic` parse mode, reported by
the outcome class and reason `telemetry.record.classify_outcome` gives its
published payload. The whole-archive zero-movement sweep
(`tools/regfp_zero_movement_sweep.py`) answers a different question — did
anything ELSE move — and is owed once per card; this one answers whether the
population the card claimed actually publishes.

READ-ONLY and $0. OCR artifacts are reached by DIRECT file path, enumerating
every capability partition exactly like the sweep does; the `webapp_data`
sqlite index is never opened; `parse_mode="deterministic"` cannot reach the
extraction branch, so no model call is possible. Nothing is written anywhere
but the `--out` path.

    python -m tools.welch_family_replay --population <file of shas> \
        --data-dir webapp_data [--rows <run>/rows.csv] [--out replay.json]

`--rows`, when given, adds each document's outcome in the run of record beside
its outcome now, so the report carries the transition rather than only the
destination.

The report names documents by `content_sha256` and by outcome vocabulary only:
no document text, no figure, no name, no filename. Row COUNTS are reported —
how many postings and how many printed daily balances a document yielded — and
those are properties of the reader, not contents of the statement.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import time
from collections import Counter
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--population", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--rows", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from ocr.document import StatementMarkdown
    from telemetry.record import classify_outcome
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    before: dict[str, str] = {}
    if args.rows is not None:
        with args.rows.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                sha = (row.get("content_sha256") or "").strip().upper()
                if sha:
                    before.setdefault(
                        sha, f"{row.get('outcome_class')}/{row.get('outcome_reason')}"
                    )

    shas = [
        token.strip().upper()
        for token in args.population.read_text(encoding="utf-8").split()
        if token.strip()
    ]
    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    for sha in shas:
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
                source_file="replay.pdf",
                model=str(document.get("model") or ""),
                pages=pages,
            ).to_markdown()
            if best is None or len(markdown) > len(best[0]):
                best = (markdown, pages)
        if best is None:
            rows.append({"content_sha256": sha, "outcome": "no_ocr_artifact"})
            continue

        markdown, pages = best
        try:
            report = report_to_dict(
                analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
            )
            outcome_class, reason = classify_outcome(report)
        except Exception as exc:  # noqa: BLE001 — the harness reports, never hides
            rows.append({
                "content_sha256": sha,
                "outcome": "raised",
                "exception": type(exc).__name__,
                "was": before.get(sha),
            })
            continue

        statement = report.get("statement") or {}
        metrics = report.get("metrics") or {}
        integrity = report.get("integrity") or {}
        rows.append({
            "content_sha256": sha,
            "outcome": f"{outcome_class}/{reason}",
            "was": before.get(sha),
            "model_used": report.get("model_used"),
            "transactions": len(statement.get("transactions") or []),
            "printed_daily_balances": len(statement.get("stated_daily_balances") or []),
            "currency": statement.get("currency"),
            "currency_source": statement.get("currency_source"),
            "integrity_flags": sorted(integrity.get("flags") or []),
            "adb_published": metrics.get("average_daily_balance") is not None,
        })

    tally = Counter(str(row["outcome"]) for row in rows)
    transitions = Counter(
        f"{row.get('was')} -> {row['outcome']}" for row in rows if row.get("was")
    )
    report = {
        "documents": len(rows),
        "seconds": round(time.perf_counter() - started, 1),
        "outcomes": dict(tally.most_common()),
        "transitions": dict(transitions.most_common()),
        "transactions_total": sum(int(row.get("transactions") or 0) for row in rows),
        "printed_daily_balances_total": sum(
            int(row.get("printed_daily_balances") or 0) for row in rows
        ),
        "rows": rows,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(
        {key: value for key, value in report.items() if key != "rows"}, sort_keys=True
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

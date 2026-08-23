"""Who does this branch's registry claim, over the whole archive? — W3 §WELCH.

The instrument behind three of WELCH's headline numbers, committed so review
reproduces them rather than reading them:

1. THE POPULATION, re-derived. The census named a family by folder-merge and
   sampling; this sweeps every distinct `content_sha256` in a run's rows.csv
   and reports which documents carry each of the registration's markers, so
   the family is a MEASUREMENT over the archive rather than a list inherited
   from a document.
2. MARKER DISCRIMINATION. Per marker, how many documents in the whole archive
   carry it — the number that says whether a marker is furniture of this
   institution or an idiom half the industry prints.
3. THE NON-TARGET PROBE. Every document OUTSIDE the named population that the
   new registration claims, and every document ANY two registrations both
   claim. A new registration owes the first at zero; the second is the
   ambiguity surface a new claimant can widen.

READ-ONLY and $0. OCR artifacts are reached by DIRECT file path, enumerating
every capability partition exactly like `tools/regfp_zero_movement_sweep.py`;
the `webapp_data` sqlite index is never opened; no model call is reachable
because nothing here analyses — it only detects. Nothing is written anywhere
but the `--out` path.

    python -m tools.welch_detection_probe --rows <reports>/<run>/rows.csv \
        --data-dir webapp_data --population <file of shas> [--out probe.json]

The report names documents by `content_sha256` and marker id only: no document
text, no figure, no name, no filename.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import sys
import time
from pathlib import Path

#: Folder labels are operator metadata, never evidence about a document — but
#: they are what the wave's stratification rule is written in ("all Canadian
#: included"), so they are used HERE and only here, to prove the probe's
#: coverage rather than to decide anything about a document.
CANADIAN_LABEL_RE = re.compile(
    r"\b(RBC|Royal Bank|TD Canada|Scotia|BMO|CIBC|Desjardins|Tangerine|EQ Bank|"
    r"Wealthsimple|ATB|Meridian|Vancity|Simplii|Canada|Canadian|Coast Capital)\b",
    re.IGNORECASE,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument(
        "--population",
        type=Path,
        default=None,
        help="whitespace-separated content_sha256 of the named population",
    )
    parser.add_argument(
        "--registration",
        default="welch_state_bank",
        help="the registration id whose markers and claims are reported",
    )
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Importing the entries module is what POPULATES the registry; importing
    # `parser_registry` alone gets an empty one.
    from analysis import parser_registry_entries  # noqa: F401
    from analysis.parser_registry import by_id, prepare, registrations
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    subject = by_id(args.registration)
    if subject is None:
        print(f"no such registration: {args.registration}", file=sys.stderr)
        return 2
    others = [r for r in registrations() if r.id != subject.id]

    population: set[str] = set()
    if args.population is not None:
        population = {
            token.strip().upper()
            for token in args.population.read_text(encoding="utf-8").split()
            if token.strip()
        }

    meta: dict[str, dict[str, str]] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha:
                meta.setdefault(
                    sha,
                    {
                        "classification": row.get("classification", ""),
                        "folder_label": row.get("folder_label", ""),
                        "outcome_class": row.get("outcome_class", ""),
                        "outcome_reason": row.get("outcome_reason", ""),
                    },
                )
    shas = sorted(meta)[args.start : args.end]

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    marker_hits: dict[str, list[str]] = {marker.id: [] for marker in subject.markers}
    claimed: list[str] = []
    co_claimed: list[dict[str, object]] = []
    examined = scanned = canadian = no_text = 0
    started = time.perf_counter()

    for sha in shas:
        markdown = None
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
            text = StatementMarkdown(
                source_file="probe.pdf",
                model=str(document.get("model") or ""),
                pages=pages,
            ).to_markdown()
            if markdown is None or len(text) > len(markdown):
                markdown = text
        if markdown is None:
            no_text += 1
            continue

        examined += 1
        if meta[sha]["classification"] == "scanned":
            scanned += 1
        if CANADIAN_LABEL_RE.search(meta[sha]["folder_label"]):
            canadian += 1

        prepared = prepare(markdown)
        detection = subject.detect_prepared(prepared)
        for marker_id in detection.matched:
            marker_hits.setdefault(marker_id, []).append(sha)
        if not detection.claims:
            continue
        claimed.append(sha)
        rivals = sorted(
            other.id for other in others if other.detect_prepared(prepared).claims
        )
        if rivals:
            co_claimed.append({"content_sha256": sha, "also_claimed_by": rivals})

    outside = sorted(set(claimed) - population) if population else []
    missed = sorted(population - set(claimed)) if population else []
    report = {
        "registration": subject.id,
        "range": [args.start, args.end],
        "documents": len(shas),
        "examined": examined,
        "no_ocr_text": no_text,
        "scanned_examined": scanned,
        "canadian_labelled_examined": canadian,
        "seconds": round(time.perf_counter() - started, 1),
        "marker_hit_counts": {name: len(hits) for name, hits in sorted(marker_hits.items())},
        "claimed": len(claimed),
        "claimed_shas": sorted(claimed),
        "claimed_outside_population": outside,
        "population_not_claimed": missed,
        "co_claimed_with_another_registration": co_claimed,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in report.items() if not key.endswith("_shas")},
            sort_keys=True,
        )
    )
    return 1 if (outside or missed or co_claimed) else 0


if __name__ == "__main__":
    raise SystemExit(main())

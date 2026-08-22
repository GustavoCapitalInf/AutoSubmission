"""Which archive documents the core-processor complex claims, by LIVE detection.

W3 §DESCATTRIB's population instrument. The wave rule is that a family
population is derived by live detection replay or artifact-store enumeration
and never from a run's `parser_id` column alone, because that column records
what the registry looked like when the run was taken. This replays
`parser_registry.resolve` against the text the run itself analysed and reports,
per registration id, the `content_sha256` of every document the registry claims
today.

    python -m tools.descattrib_census \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        [--start 0 --end 3380] [--out census.json]

READ-ONLY and $0: the `webapp_data` sqlite index is never opened, artifacts are
reached by DIRECT file path, and nothing beyond detection runs — no extraction
branch is reachable. The OCR-artifact selection is `tools.regfp_zero_movement
_sweep`'s, for the reason that tool documents: a document can hold one cached
OCR artifact per capability partition, and the artifact whose reconstruction
resolves the run's own stored analysis payload is PROOF of which text the run
read rather than an assumption about the rung. Where no analysis payload exists
(the document was refused) the first partition holding a document is used and
the choice is recorded in `ambiguous_text`, since a refused document has no
payload to prove anything with.

The output names documents by `content_sha256` and registration id only: no
document text, no filename, no figure.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import time
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path, help="the webapp_data directory")
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument(
        "--prefix",
        default="core_processor",
        help="report ids beginning with this; empty reports every id",
    )
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def texts_for(sha: str, root: Path, ocr_keys: list[str], baseline: str,
              cache_key, analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS,
              StatementMarkdown) -> tuple[str, list[str], bool, int] | None:
    """The markdown the run analysed for `sha`, its pages, whether the choice
    was unproven, and how many partitions held a document."""
    candidates: list[tuple[str, list[str]]] = []
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
            source_file="census.pdf", model=str(document.get("model") or ""), pages=pages
        ).to_markdown()
        candidates.append((markdown, pages))
    if not candidates:
        return None
    for candidate_markdown, candidate_pages in candidates:
        composed = cache_key(
            STAGE_ANALYSIS, analysis_input_sha(candidate_markdown, candidate_pages), baseline
        )
        if (root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json").exists():
            return candidate_markdown, candidate_pages, False, len(candidates)
    return candidates[0][0], candidates[0][1], len(candidates) > 1, len(candidates)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # The import is what REGISTERS: `analysis.parser_registry` holds an empty
    # registry until `parser_registry_entries` is imported, and `registrations`
    # does not load it for you. A census that skipped this line would replay
    # detection against nothing, claim no document, and look perfectly healthy
    # — so the registry's size is asserted below rather than assumed.
    from analysis import parser_registry_entries  # noqa: F401
    from analysis.parser_registry import registrations, resolve
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS,
        STAGE_OCR,
        analysis_input_sha,
        cache_key,
        ocr_settings_key,
    )

    registry_size = len(registrations())
    if registry_size == 0:
        raise SystemExit("empty registry: nothing would claim anything")

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    outcome_by_sha: dict[str, str] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha:
                outcome_by_sha.setdefault(sha, row["outcome_class"])
    shas = sorted(outcome_by_sha)[args.start : args.end]

    claimed: dict[str, list[dict[str, object]]] = {}
    counts = {"documents": 0, "no_ocr_artifact": 0, "ambiguous_text": 0, "claimed": 0}
    started = time.perf_counter()

    for sha in shas:
        counts["documents"] += 1
        found = texts_for(
            sha, root, ocr_keys, baseline, cache_key, analysis_input_sha,
            STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown,
        )
        if found is None:
            counts["no_ocr_artifact"] += 1
            continue
        markdown, _pages, unproven, partitions = found
        if unproven:
            counts["ambiguous_text"] += 1
        dispatch = resolve(markdown)
        parser_id = dispatch.parser_id
        if parser_id is None or not parser_id.startswith(args.prefix):
            continue
        counts["claimed"] += 1
        claimed.setdefault(parser_id, []).append(
            {
                "content_sha256": sha,
                "outcome_class": outcome_by_sha[sha],
                "dispatch_outcome": dispatch.outcome,
                "unproven_text": unproven,
                "partitions": partitions,
            }
        )

    report = {
        "range": [args.start, args.end],
        "registry_size": registry_size,
        "seconds": round(time.perf_counter() - started, 1),
        **counts,
        "by_parser": {key: sorted(value, key=lambda item: item["content_sha256"])
                      for key, value in sorted(claimed.items())},
    }
    text = json.dumps(report, indent=1)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

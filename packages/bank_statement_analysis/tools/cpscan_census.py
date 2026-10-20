"""The two scanned core-processor cohorts, censused by LIVE detection replay.

W3 §CPSCAN's population instrument. The wave rule is that a family population
is derived by live detection replay and never from a run's `parser_id` column,
because that column records what the registry looked like when the run was
taken. This replays `parser_registry`'s detectors against the text the run
itself analysed and reports, per document:

* every registration whose DETECTOR claims it (`claimed_by`), which is the
  measurement W3 §SCANNEXT SN3 defines as the staffing one — a registration
  that claims and publishes leaves `dispatch.attempted` empty, so the run's
  column understates who is looking at a family;
* the live dispatch outcome and the winning registration;
* the REFUSAL SITE — module and source line of the `return` that declined —
  traced with `sys.settrace` over the parse frames of the named modules, so a
  decline is attributed to the gate that made it rather than to a guess.

    python -m tools.cpscan_census \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        [--start 0 --end 3380] [--classification non-digital] [--out census.json]

READ-ONLY and $0: the `webapp_data` sqlite index is never opened, artifacts are
reached by DIRECT file path, and nothing beyond detection and the deterministic
`parse` runs — no hosted model call is reachable.

The OCR-artifact selection is `tools.regfp_zero_movement_sweep`'s, for the
reason that tool documents: a document can hold one cached OCR artifact per
capability partition, and the artifact whose reconstruction resolves the run's
own stored analysis payload is PROOF of which text the run read rather than an
assumption about the rung. Where no analysis payload exists (the document was
refused) the first partition holding a document is used and the choice is
recorded in `unproven_text`.

The output names documents by `content_sha256`, registration id and source line
only: no document text, no filename, no figure.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from pathlib import Path

#: The registrations this card owns, plus the two that supersede them. A
#: superseding sibling is in the set because `supersedes` pruning is what
#: decides which of two claimants ever reaches `parse`, and a census that
#: reported only the general reader would report a family it does not route.
DEFAULT_IDS = "core_processor_sectioned,core_processor_daily,first_farmers,b1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path, help="a run's rows.csv")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument(
        "--classification",
        default="all",
        choices=("all", "digital", "non-digital"),
        help="restrict the swept population by the run's own classification",
    )
    parser.add_argument(
        "--ids",
        default=DEFAULT_IDS,
        help="comma-separated registration ids to report membership for",
    )
    parser.add_argument(
        "--trace-modules",
        default="core_processor_sectioned,core_processor_daily",
        help="comma-separated analysis module stems to trace refusal sites in",
    )
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def texts_for(sha, root, ocr_keys, baseline, cache_key, analysis_input_sha,
              STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown):
    """The markdown the run analysed for `sha`, whether the choice was
    unproven, and how many capability partitions held a document."""
    candidates: list[tuple[str, list[str], str]] = []
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
        model = str(document.get("model") or "")
        markdown = StatementMarkdown(
            source_file="census.pdf", model=model, pages=pages
        ).to_markdown()
        candidates.append((markdown, pages, model))
    if not candidates:
        return None
    for markdown, pages, model in candidates:
        composed = cache_key(
            STAGE_ANALYSIS, analysis_input_sha(markdown, pages), baseline
        )
        if (root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json").exists():
            return markdown, pages, model, False, len(candidates)
    markdown, pages, model = candidates[0]
    return markdown, pages, model, len(candidates) > 1, len(candidates)


class RefusalTracer:
    """Where a traced `parse` returned, by module stem and source line.

    A `return` event carries the line of the statement that returned, which is
    exactly the "refusal site" W3 §DECLINESD names its declines by. Every frame
    of a traced module is recorded, so a decline made inside a helper is
    reported as the helper's line as well as the top frame's — a gate and the
    reading it depends on are different findings.
    """

    def __init__(self, stems: set[str]) -> None:
        self.stems = stems
        self.sites: list[tuple[str, str, int, bool]] = []
        self._previous = None

    def _stem(self, frame) -> str | None:
        """The traced module stem this frame belongs to, or None.

        Comprehension and generator frames are excluded by name: an exhausted
        generator returns `None` at whatever line its expression sits on, and
        counting that as a refusal would attribute the decline to the line of a
        `sum()` rather than to the gate that read it.
        """
        if frame.f_code.co_name.startswith("<") or frame.f_code.co_name == "__init__":
            return None
        name = frame.f_globals.get("__name__", "")
        stem = name.rsplit(".", 1)[-1]
        return stem if stem in self.stems else None

    def __call__(self, frame, event, arg):
        if event != "call":
            return None
        if self._stem(frame) is None:
            return None
        return self._local

    def _local(self, frame, event, arg):
        if event == "return":
            stem = self._stem(frame)
            if stem is not None:
                self.sites.append(
                    (stem, frame.f_code.co_name, frame.f_lineno, arg is None)
                )
        return self._local

    def __enter__(self):
        self._previous = sys.gettrace()
        sys.settrace(self)
        return self

    def __exit__(self, *exc):
        sys.settrace(self._previous)
        return False

    def report(self) -> dict[str, object]:
        """The outermost traced frame's return site, and the whole stack of
        `None`-returning traced frames beneath it, innermost first."""
        if not self.sites:
            return {}
        top = self.sites[-1]
        declined = [f"{stem}.{name}:{line}"
                    for stem, name, line, is_none in self.sites if is_none]
        return {
            "refusal_site": f"{top[0]}:{top[2]}",
            "refusal_function": top[1],
            "refused": top[3],
            "declining_frames": declined[-8:],
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # The import is what REGISTERS: `analysis.parser_registry` holds an empty
    # registry until `parser_registry_entries` is imported, and `registrations`
    # does not load it for you. A census that skipped this line would replay
    # detection against nothing, claim no document, and look perfectly healthy
    # — so the registry's size is asserted below rather than assumed.
    from analysis import parser_registry_entries  # noqa: F401
    from analysis.parser_registry import (
        by_id, prepare, registrations, resolve, safe_detect,
    )
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    registry_size = len(registrations())
    if registry_size == 0:
        raise SystemExit("empty registry: nothing would claim anything")

    watched = [by_id(name) for name in args.ids.split(",") if name]
    stems = {name for name in args.trace_modules.split(",") if name}

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    run_rows: dict[str, dict[str, str]] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha:
                run_rows.setdefault(sha, row)
    shas = sorted(run_rows)
    if args.classification == "digital":
        shas = [s for s in shas if run_rows[s]["classification"] == "digital"]
    elif args.classification == "non-digital":
        shas = [s for s in shas if run_rows[s]["classification"] != "digital"]
    shas = shas[args.start : args.end]

    members: list[dict[str, object]] = []
    counts = {"documents": 0, "no_ocr_artifact": 0, "unproven_text": 0, "members": 0}
    started = time.perf_counter()

    for sha in shas:
        counts["documents"] += 1
        found = texts_for(sha, root, ocr_keys, baseline, cache_key,
                          analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown)
        if found is None:
            counts["no_ocr_artifact"] += 1
            continue
        markdown, _pages, model, unproven, partitions = found
        prepared = prepare(markdown)
        claimed_by = [reg.id for reg in watched if safe_detect(reg, prepared).claims]
        if not claimed_by:
            continue
        counts["members"] += 1
        if unproven:
            counts["unproven_text"] += 1
        with RefusalTracer(stems) as tracer:
            dispatch = resolve(prepared)
        row = run_rows[sha]
        members.append({
            "content_sha256": sha,
            "classification": row["classification"],
            "run_outcome": row["outcome_class"],
            "run_reason": row["outcome_reason"],
            "run_parser_id": row["parser_id"],
            "source_model": model,
            "model_matches_run": model == row["source_model"],
            "claimed_by": claimed_by,
            "dispatch_outcome": dispatch.outcome,
            "dispatch_parser_id": dispatch.parser_id,
            "dispatch_attempted": list(dispatch.attempted),
            "dispatch_crashed": list(dispatch.crashed),
            "unproven_text": unproven,
            "partitions": partitions,
            **tracer.report(),
        })

    report = {
        "range": [args.start, args.end],
        "classification": args.classification,
        "registry_size": registry_size,
        "watched_ids": [reg.id for reg in watched],
        "seconds": round(time.perf_counter() - started, 1),
        **counts,
        "members": sorted(members, key=lambda item: item["content_sha256"]),
    }
    text = json.dumps(report, indent=1)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

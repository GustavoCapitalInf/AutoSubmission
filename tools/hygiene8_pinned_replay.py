"""Replay the pinned 109 BASE against BRANCH, leaf for leaf, read-only.

    python -m tools.hygiene8_pinned_replay --scratch <private> [--out pinned.json]

#HYGIENE8's hard stop. The pinned manifest is the program's truth set, and the
wave rule is that truth-set movement outside an approved ceremony is a STOP —
so a branch that declares itself non-outcome owes the pinned surface a
measurement before it owes anything else. Any movement here is recorded and
left in place: this tool never fixes anything, and neither does the cell.

WHY ALL 109 AND NOT THE TOUCHED READERS' SUBSET. The subset is the population
the card names, and it is computed and reported (`by_parser`), but replaying
only the subset would assume the branch cannot reach a document it does not
claim — and `analysis/date_tokens.py`, which this branch also changed, is
reached by parsers all over the registry. The whole manifest is 109 documents;
measuring it costs minutes and assumes nothing.

The intake half is shared, deliberately: `ocr/` is byte-identical between base
and branch (this branch changes `analysis/` and `webapp/app.py` only), so the
markdown and the page list are computed ONCE and handed to both stacks. That
removes intake as a variable — what is compared is the analysis, which is what
moved or did not.

Offline and read-only, exactly as `corpus_gate.py` runs: native text through
`ocr.pipeline.parse_statement` with every OCR rung refused, and the six
image-only statements served from their committed artifacts by
`corpus_artifacts.cached_markdown`. No PDF, no CSV and no artifact is written.

A pinned REFUSAL is a pinned fact, so a document that raises on both trees is
`refused_on_both` and is compared by exception CLASS. The message is never
compared and never printed: at base three of these readers put a printed token
into it, which is the leak this branch closes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="10cc722", help="the base revision")
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo))

    import corpus_gate
    from analysis.count_semantics import claiming_parser_id
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from corpus_artifacts import DEFAULT_CACHE, cached_markdown, cached_pages
    from ocr.inspect import inspect_pdf
    from ocr.pipeline import parse_statement
    from telemetry.record import classify_outcome
    from tools.hygiene8_base_tree import leaf_diff, load_base_analysis
    from tools.hygiene8_family_replay import derive_population

    base = load_base_analysis(args.base, repo=repo, scratch=args.scratch)
    touched = set(derive_population(repo))

    corpus = args.corpus or corpus_gate.CORPUS
    manifest = corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))
    counts = {
        "pinned": len(manifest),
        "replayed": 0,
        "identical": 0,
        "moved": 0,
        "outcome_moved": 0,
        "refused_on_both": 0,
        "refusal_class_moved": 0,
        "publish_boundary_moved": 0,
        "unreadable": 0,
        "claimed_by_a_touched_reader": 0,
    }
    by_parser: dict[str, int] = {}
    findings: list[dict[str, object]] = []
    started = time.perf_counter()

    for relative in manifest:
        path = corpus / Path(relative)
        try:
            raw = path.read_bytes()
        except OSError:
            counts["unreadable"] += 1
            findings.append({"path": relative, "verdict": "unreadable_source"})
            continue

        document = parse_statement(
            raw,
            source_file=path.name,
            profile=inspect_pdf(raw),
            force_ocr=False,
            allow_local_ocr=False,
            allow_visual_ocr=False,
        )
        if document is not None:
            markdown = document.to_markdown()
            sheets = list(document.pages)
        else:
            markdown = cached_markdown(raw, DEFAULT_CACHE)
            sheets = cached_pages(raw, DEFAULT_CACHE)
            if markdown is None:
                counts["unreadable"] += 1
                findings.append({"path": relative, "verdict": "no_text_and_no_artifact"})
                continue

        counts["replayed"] += 1
        try:
            before_report = base.analyze_markdown(
                markdown, parse_mode="deterministic", sheets=sheets
            )
            before, before_raised = base.report_to_dict(before_report), None
        except Exception as exc:
            before, before_raised = None, type(exc).__name__
        try:
            after_report = analyze_markdown(markdown, parse_mode="deterministic", sheets=sheets)
            after, after_raised = report_to_dict(after_report), None
            claiming = claiming_parser_id(getattr(after_report, "dispatch", None))
        except Exception as exc:
            after, after_raised, claiming = None, type(exc).__name__, None

        if claiming:
            by_parser[claiming] = by_parser.get(claiming, 0) + 1
            if claiming in touched:
                counts["claimed_by_a_touched_reader"] += 1

        # `path` is a corpus-relative FILENAME and the manifest is committed,
        # so it is a source symbol here rather than archive content. It is also
        # the only thing that lets a STOP be acted on.
        if before_raised and after_raised:
            counts["refused_on_both"] += 1
            if before_raised != after_raised:
                counts["refusal_class_moved"] += 1
                findings.append(
                    {
                        "path": relative,
                        "verdict": "refusal_class_moved",
                        "base": before_raised,
                        "branch": after_raised,
                    }
                )
            continue
        if bool(before_raised) != bool(after_raised):
            counts["publish_boundary_moved"] += 1
            findings.append(
                {
                    "path": relative,
                    "verdict": "publish_boundary_moved",
                    "base": before_raised or "published",
                    "branch": after_raised or "published",
                }
            )
            continue

        base_outcome = classify_outcome(before)
        branch_outcome = classify_outcome(after)
        paths = leaf_diff(before, after)
        if base_outcome != branch_outcome:
            counts["outcome_moved"] += 1
            findings.append(
                {
                    "path": relative,
                    "verdict": "outcome_moved",
                    "base": list(base_outcome),
                    "branch": list(branch_outcome),
                }
            )
        if paths:
            counts["moved"] += 1
            findings.append(
                {
                    "path": relative,
                    "verdict": "moved",
                    "paths": paths[:40],
                    "path_count": len(paths),
                }
            )
        elif base_outcome == branch_outcome:
            counts["identical"] += 1

    report = {
        "base": base.revision,
        "touched_registrations": sorted(touched),
        "seconds": round(time.perf_counter() - started, 1),
        **counts,
        "by_parser": dict(sorted(by_parser.items())),
        "findings": findings,
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "findings"}, sort_keys=True))
    for finding in findings:
        print(json.dumps(finding, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

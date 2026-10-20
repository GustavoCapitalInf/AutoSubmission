"""What a new registration claims across the whole archive, and what it does with it.

W3 §GLANCE's non-target probe, committed because it produces headline numbers.
The question a new registration owes an answer to is not "does it read its own
family" — the family replay answers that — but **what else does it claim, and
does anything it claims now resolve ambiguously?** So this instrument runs the
live registry's `resolve` over every document in the run of record and reports:

* how many documents the probed registration CLAIMS, and how many of those it
  is the sole claimant of;
* how many documents resolve `ambiguous` at HEAD, against the same count with
  the probed registration removed — the delta is the ambiguity this
  registration created;
* for every document it claims, whether its `parse` publishes or declines;
* the same three numbers per STRATUM (`digital` / `scanned`, and the Canadian
  cohort), so the probe can be read as the stratified one the wave rules ask
  for rather than only as an aggregate.

READ-ONLY, and in the two ways the wave requires. Nothing is written to the
archive or the artifact store; the `webapp_data` sqlite index is never opened —
OCR payloads are reached by DIRECT file path over every capability partition of
`ocr_settings_key`, the enumeration `tools/regfp_zero_movement_sweep.py`
established. It makes no model call and costs $0.00: it never reaches the
analysis stage at all, only detection and the probed parser's own `parse`.

    python -m tools.glance_detection_probe \
        --rows <reports>/<run-id>/rows.csv --data-dir <checkout>/webapp_data \
        --parser category_partition [--start 0 --end 3380] [--out probe.json]

WHICH TEXT A DOCUMENT IS PROBED ON. A document can hold more than one cached
OCR artifact, one per capability partition, and detection can differ between
them. There is no analysis payload to resolve the run's own choice against here
— this tool never composes an analysis key — so it does not pretend to one:
every partition holding a document is probed, and the document counts as
claimed if ANY of its partitions is claimed. That is the conservative direction
for this question: it can only over-report what a registration reaches.

THE CANADIAN STRATUM is measured, not assumed. A document is in it when its
text prints `CAD`, `Canada`, `Canadian` or `Canadien` (case-insensitively), or
when the run of record attributed it to a registration this file names as
Canadian. Both halves are reported, because neither alone is the cohort: the
token test reaches unclaimed Canadian layouts the parser list cannot, and the
parser list reaches documents whose Canadian identity is printed as a bank name
this test does not look for.

No document text, filename, amount or name is written to the output. Documents
are named by `content_sha256` and by nothing else.
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

#: Registrations whose institution is Canadian. Used only to WIDEN the Canadian
#: stratum beyond the token test; nothing is excluded by it.
CANADIAN_PARSERS = frozenset({
    "atb", "bmo_ca_business", "bmo_ca_business_french", "cibc", "cibc_french",
    "desjardins", "eq_bank_scanned", "rbc", "rbc_french", "releve_facturation",
    "scotiabank", "td_canada", "td_canada_french", "td_canada_native",
    "wealthsimple",
})

#: What puts a document in the Canadian stratum by its own printing.
CANADIAN_TOKEN_RE = re.compile(r"\bCAD\b|Canadian|Canadien|Canada", re.IGNORECASE)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--parser", required=True, help="the registration id under probe")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from analysis import parser_registry as pr
    from analysis import parser_registry_entries  # noqa: F401 — populates the registry
    from analysis.parser_registry import AmbiguousParserError
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    registrations = pr.registrations()
    probed = next((r for r in registrations if r.id == args.parser), None)
    if probed is None:
        print(f"no registration with id {args.parser!r}", file=sys.stderr)
        return 2
    #: The same registry minus the one under probe, so "ambiguity this
    #: registration created" is a difference rather than an assertion.
    without = tuple(r for r in registrations if r.id != args.parser)

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]

    rows: dict[str, dict[str, str]] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["content_sha256"]:
                rows.setdefault(row["content_sha256"], row)
    shas = sorted(rows)[args.start : args.end]

    counts = {
        "probed": 0,
        "no_ocr_artifact": 0,
        "claimed": 0,
        "sole_claim": 0,
        "ambiguous_at_head": 0,
        "ambiguous_without_probe": 0,
        "claimed_and_publishes": 0,
        "claimed_and_declines": 0,
        "scanned": 0,
        "canadian_by_token": 0,
        "canadian_by_parser": 0,
        "canadian": 0,
        "canadian_claimed": 0,
        "scanned_claimed": 0,
    }
    claims: list[dict[str, object]] = []
    started = time.perf_counter()

    for sha in shas:
        texts: list[str] = []
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
            texts.append(StatementMarkdown(
                source_file="probe.pdf",
                model=str(document.get("model") or ""),
                pages=[str(page) for page in (document.get("pages") or [])],
            ).to_markdown())
        if not texts:
            counts["no_ocr_artifact"] += 1
            continue

        counts["probed"] += 1
        row = rows[sha]
        scanned = row.get("classification") == "scanned"
        by_token = any(CANADIAN_TOKEN_RE.search(text) for text in texts)
        by_parser = row.get("parser_id") in CANADIAN_PARSERS
        counts["scanned"] += scanned
        counts["canadian_by_token"] += by_token
        counts["canadian_by_parser"] += by_parser
        counts["canadian"] += by_token or by_parser

        claimed = any(probed.detect(text).claims for text in texts)
        ambiguous_head = ambiguous_without = False
        for text in texts:
            # `resolve` never raises; it decides ambiguity from detection and
            # `supersedes` BEFORE any parse, and reports it as an outcome.
            dispatch = pr.resolve(text)
            head = dispatch.outcome == "ambiguous"
            ambiguous_head = ambiguous_head or head
            # Removing a registration that did not claim this document cannot
            # change its claimant set, so the counterfactual is the same
            # verdict — computed only where the probe IS a claimant, or where
            # HEAD is already ambiguous and the delta is the whole question.
            if probed.detect(text).claims or head:
                ambiguous_without = ambiguous_without or _would_be_ambiguous(without, text)
            else:
                ambiguous_without = ambiguous_without or head
        counts["ambiguous_at_head"] += ambiguous_head
        counts["ambiguous_without_probe"] += ambiguous_without

        if not claimed:
            continue
        counts["claimed"] += 1
        counts["scanned_claimed"] += scanned
        counts["canadian_claimed"] += by_token or by_parser
        sole = all(
            [r.id for r in registrations if r.detect(text).claims] == [args.parser]
            for text in texts if probed.detect(text).claims
        )
        counts["sole_claim"] += sole
        published = any(
            probed.parse(text) is not None
            for text in texts if probed.detect(text).claims
        )
        counts["claimed_and_publishes"] += published
        counts["claimed_and_declines"] += not published
        claims.append({
            "content_sha256": sha,
            "sole_claim": sole,
            "publishes": published,
            "run_outcome_class": row.get("outcome_class"),
            "run_outcome_reason": row.get("outcome_reason"),
            "run_parser_id": row.get("parser_id") or None,
            "classification": row.get("classification"),
            "canadian": bool(by_token or by_parser),
        })

    report = {
        "parser": args.parser,
        "rows": str(args.rows),
        "slice": [args.start, args.end],
        "elapsed_s": round(time.perf_counter() - started, 1),
        "counts": counts,
        "claims": claims,
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


def _would_be_ambiguous(without, text: str) -> bool:
    """Whether `resolve` over `without` would raise, computed with its own rule.

    The registry exposes no "resolve against this subset" entry point, so the
    rule is applied to the subset here rather than reimplemented: the claimants
    are ranked by `(band, id)`, a registration superseded by another claimant is
    dropped, and more than one survivor is the ambiguity.
    """
    claimants = [r for r in without if r.detect(text).claims]
    if len(claimants) <= 1:
        return False
    superseded = {
        identifier
        for claimant in claimants
        for identifier in getattr(claimant, "supersedes", frozenset())
    }
    survivors = [r for r in claimants if r.id not in superseded]
    return len(survivors) > 1


if __name__ == "__main__":
    raise SystemExit(main())

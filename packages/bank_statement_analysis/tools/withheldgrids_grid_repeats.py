"""How often does the printed daily-balance grid print one day TWICE?

W3 §WITHHELDGRIDS's third committed instrument, for the review's MINOR-8.
`analysis/community_section.py::_daily_balances` builds `{iso: balance}` by
assignment, so a day printed twice in the region was resolved LAST-WINS and
silently. The ADB doctrine's rule for that shape is "read what is printed,
refuse on a contradiction", and the two halves of the shape are not the same
thing at all:

* the SAME day printed twice with the SAME balance is one printed fact printed
  twice — a grid continued across a page break, or the region catching the
  same block again. One cell, no contradiction, nothing to refuse;
* the same day printed twice with DIFFERENT balances is the document
  contradicting itself, and choosing the later one is the parser inventing an
  answer.

This measures both, base pattern and branch pattern, over every document of
the family in the run of record, on THE BLOCK THE PARSER ACTUALLY PASSES —
`_daily_balances` is spied on in place rather than re-implemented, so the
region, the `_clean` and the pattern are the production ones.

    python -m tools.withheldgrids_grid_repeats \
        --rows discovery_reports/<run>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex>

READ-ONLY and $0.00, by the same rules as the two instruments beside it: the
sqlite index is never opened, artifacts are reached by direct file path, every
capability partition is enumerated and the one that rebuilds the run's stored
payload is the one measured.

PRIVACY: counts, `content_sha256` prefixes and parser ids only. No date, no
balance and no other document literal reaches the output.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import sys
from collections import Counter
from pathlib import Path

#: The registrations whose `parse` reaches `community_section._daily_balances`.
FAMILY = ("community_section", "mission_valley", "dakota_west", "midflorida")


def _resolve(root, sha, ocr_keys, baseline, cache_key, analysis_input_sha,
             STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown):
    candidates = []
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
        candidates.append((
            StatementMarkdown(source_file="gridrepeats.pdf",
                              model=str(document.get("model") or ""),
                              pages=pages).to_markdown(),
            pages,
        ))
    if not candidates:
        return None, None, None
    for markdown, pages in candidates:
        composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(markdown, pages), baseline)
        stored = root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json"
        if stored.exists():
            try:
                payload = json.loads(stored.read_text(encoding="utf-8"))["artifact"]["analysis"]
            except (OSError, ValueError, KeyError):
                continue
            return markdown, pages, payload
    return candidates[0][0], candidates[0][1], None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--baseline-settings-key", required=True)
    ap.add_argument("--pinned", default="docs/balance-metrics-audit-results.csv")
    ap.add_argument("--movers", default="", help="file of content_sha256 to call out")
    ap.add_argument("--extra", default="",
                    help="file of `content_sha256 parser_id` pairs to measure as well "
                         "(a pinned document the run of record never claimed still has "
                         "a cached artifact, and the STOP condition is about it)")
    ap.add_argument("--json-out", default="")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    import analysis.community_section as cs
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    base_pattern = re.compile(r"(" + cs._DATE + r")\s+(" + cs._MONEY + r")")
    branch_pattern = re.compile(r"(" + cs._DATE + r")\s+(" + cs._SIGNED_MONEY + r")")

    seen: dict[str, str] = {}
    order: list[str] = []
    with open(args.rows, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            parser_id = (row.get("parser_id") or "").strip()
            if sha and parser_id in FAMILY and sha not in seen:
                seen[sha] = parser_id
                order.append(sha)

    extras: set[str] = set()
    if args.extra and Path(args.extra).exists():
        for entry in Path(args.extra).read_text(encoding="utf-8").splitlines():
            parts = entry.split()
            if len(parts) == 2 and parts[0].strip().upper() not in seen:
                seen[parts[0].strip().upper()] = parts[1].strip()
                order.append(parts[0].strip().upper())
                extras.add(parts[0].strip().upper())

    pinned = set()
    if Path(args.pinned).exists():
        with open(args.pinned, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = (row.get("sha256") or "").strip().upper()
                if value:
                    pinned.add(value)
    movers = set()
    if args.movers and Path(args.movers).exists():
        movers = {
            line.strip().upper()
            for line in Path(args.movers).read_text(encoding="utf-8").split()
            if line.strip()
        }

    root = Path(args.data_dir) / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
        for f, l, v in itertools.product((False, True), repeat=3)
    ]

    spy: dict[str, object] = {}
    original = cs._daily_balances

    def measure(block: str, pattern) -> tuple[int, int, int]:
        """(cells, repeated cells, DISAGREEING repeated cells) for one pattern."""
        start = re.search(
            r"Daily Balances\b(.*?)(?:Overdraft and Returned Item Fees|"
            r"Service Charge Summary|Thank you|$)",
            block, re.IGNORECASE | re.DOTALL,
        )
        if not start:
            return 0, 0, 0
        seen_days: dict[str, float] = {}
        cells = repeats = disagree = 0
        for match in pattern.finditer(cs._clean(start.group(1))):
            amount = cs._balance(match.group(2))
            if amount is None:
                continue
            try:
                iso = cs._iso(match.group(1))
            except ValueError:
                continue
            cells += 1
            if iso in seen_days:
                repeats += 1
                if seen_days[iso] != amount:
                    disagree += 1
            else:
                seen_days[iso] = amount
        return cells, repeats, disagree

    def spy_daily_balances(block: str):
        spy["base"] = measure(block, base_pattern)
        spy["branch"] = measure(block, branch_pattern)
        result = original(block)
        spy["grid_days"] = sorted(result)
        return result

    cs._daily_balances = spy_daily_balances

    from analysis.parser_registry_entries import _ENTRIES  # noqa: PLC0415

    parse_by_id = {}
    for parser_id, _label, module, _markers, _text, func in _ENTRIES:
        if parser_id in FAMILY:
            parse_by_id[parser_id] = getattr(module, func)

    totals = Counter()
    documents_with_repeat = {"base": set(), "branch": set()}
    documents_with_disagreement = {"base": set(), "branch": set()}
    rows_out = []
    measured = skipped = 0
    for sha in order:
        markdown, pages, stored = _resolve(
            root, sha, ocr_keys, args.baseline_settings_key, cache_key,
            analysis_input_sha, STAGE_OCR, STAGE_ANALYSIS, StatementMarkdown,
        )
        if markdown is None or (stored is None and sha not in extras):
            skipped += 1
            continue
        parse = parse_by_id.get(seen[sha])
        if parse is None:
            skipped += 1
            continue
        spy.clear()
        statement = None
        try:
            statement = parse(markdown)
        except Exception:  # noqa: BLE001 - a refusal is an answer
            pass
        if not spy:
            skipped += 1
            continue
        measured += 1
        grid_days = set(spy.get("grid_days") or ())
        ledger_days = {
            txn.date for txn in (statement.transactions if statement is not None else ())
        }
        for side in ("base", "branch"):
            cells, repeats, disagree = spy[side]  # type: ignore[misc]
            totals[f"{side}_cells"] += cells
            totals[f"{side}_repeats"] += repeats
            totals[f"{side}_disagree"] += disagree
            if repeats:
                documents_with_repeat[side].add(sha)
            if disagree:
                documents_with_disagreement[side].add(sha)
        rows_out.append({
            "sha8": sha[:8], "parser": seen[sha],
            "pinned": sha in pinned, "mover": sha in movers,
            "base": list(spy["base"]), "branch": list(spy["branch"]),  # type: ignore[arg-type]
            "grid_days": len(grid_days), "ledger_days": len(ledger_days),
            "grid_days_without_a_posting": len(grid_days - ledger_days),
        })

    cs._daily_balances = original

    print(f"FAMILY documents in the run={len(order)} measured={measured} skipped={skipped}")
    for side in ("base", "branch"):
        print(f"{side:6s} grid cells={totals[f'{side}_cells']:5d}  "
              f"repeated={totals[f'{side}_repeats']:4d} "
              f"(documents={len(documents_with_repeat[side])})  "
              f"DISAGREEING={totals[f'{side}_disagree']:4d} "
              f"(documents={len(documents_with_disagreement[side])})")
    for label, key in (("pinned", "pinned"), ("mover", "mover")):
        subset = [r for r in rows_out if r[key]]
        print(f"{label}: documents={len(subset)} "
              f"with a repeat={sum(1 for r in subset if r['branch'][1])} "
              f"with a DISAGREEMENT={sum(1 for r in subset if r['branch'][2])}")
    named = sorted(r["sha8"] for r in rows_out if r["branch"][2])
    print(f"DOCUMENTS WITH A DISAGREEING REPEAT (branch pattern): {len(named)} "
          + " ".join(named))
    called_out = [r for r in rows_out if r["mover"] or r["pinned"]]
    if called_out:
        print("grid vs ledger on the called-out documents "
              "(WG4's table, re-measured):")
        print(f"  {'sha8':9s} {'parser':18s} {'grid':>5s} {'ledger':>7s} "
              f"{'grid days w/o a posting':>24s}")
        for row in sorted(called_out, key=lambda r: r["sha8"]):
            print(f"  {row['sha8']:9s} {row['parser']:18s} {row['grid_days']:5d} "
                  f"{row['ledger_days']:7d} {row['grid_days_without_a_posting']:24d}")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"totals": dict(totals), "rows": rows_out}, indent=1),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""l1s2_sweep_diff.py — the archive sweep at TWO trees, differenced.

    python -m tools.l1s2_sweep_diff --base <base>_*.json --tip <tip>_*.json \
        [--population <sha16 or sha256, repeatable>]

WHY A DIFFERENCE AND NOT A SINGLE RUN
-------------------------------------
`tools/regfp_zero_movement_sweep.py` compares a tree's recomputed analysis
against the payload the RUN OF RECORD stored. The run of record is the batch-8
tree, and every batch-9 card is based on `train9`, which already carries several
composed cells. So a sweep at ANY train9 descendant reports train9's cumulative
movement as well as the card's, and reading its findings as a card's movers
would attribute other cells' work — improvements and all — to this one.

The separation is a second sweep at the card's OWN BASE over the same ranges.
A finding present at both trees is INHERITED and is not this card's; a finding
present only at the tip is this card's and must be inside its named population
by sha, or it is a regression to explain or remove; a finding present only at
the base is a finding this card REMOVED, which is equally a movement and is
reported rather than quietly enjoyed.

The comparison is per (content sha256, verdict, fields, exception), so a
document whose verdict or moved-field set CHANGED between the two trees shows up
as one finding removed and one added rather than as a silent match.

PRIVACY. Content shas, verdict classes, outcome classes, payload FIELD names and
exception CLASS names — all of them the sweep's own vocabulary. No value from
any document.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path


def load(paths: list[Path]) -> tuple[dict[tuple, dict], dict[str, int]]:
    """Findings keyed by their whole identity, plus the summed aggregates."""
    findings: dict[tuple, dict] = {}
    totals: collections.Counter = collections.Counter()
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        for key in ("documents", "compared_payload", "identical", "moved",
                    "no_payload_now_publishes", "payload_now_raises",
                    "no_payload_raises_again", "no_ocr_artifact",
                    "multi_artifact_documents"):
            totals[key] += int(report.get(key) or 0)
        for finding in report.get("findings") or []:
            identity = (
                finding.get("content_sha256", ""),
                finding.get("verdict", ""),
                tuple(finding.get("fields") or ()),
                finding.get("exception", ""),
            )
            findings[identity] = finding
    return findings, dict(totals)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", nargs="+", required=True, type=Path)
    parser.add_argument("--tip", nargs="+", required=True, type=Path)
    parser.add_argument("--population", action="append", default=[],
                        help="a sha of this card's named population (16 or 64 hex, repeatable)")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    base, base_totals = load(args.base)
    tip, tip_totals = load(args.tip)
    named = {sha.strip().upper() for sha in args.population if sha.strip()}

    inherited = sorted(set(base) & set(tip))
    added = sorted(set(tip) - set(base))
    removed = sorted(set(base) - set(tip))

    print("# L1-S2 — the archive sweep, at the base tree and at the tip, differenced")
    print()
    print("| aggregate | base tree | tip tree |")
    print("|---|---:|---:|")
    for key in ("documents", "compared_payload", "identical", "moved",
                "no_payload_now_publishes", "payload_now_raises",
                "no_payload_raises_again", "no_ocr_artifact",
                "multi_artifact_documents"):
        print(f"| `{key}` | {base_totals.get(key, 0)} | {tip_totals.get(key, 0)} |")
    print()
    print("| finding set | count |")
    print("|---|---:|")
    print(f"| present at BOTH trees — inherited from `train9`, not this card | {len(inherited)} |")
    print(f"| **present only at the TIP — this card's movers** | **{len(added)}** |")
    print(f"| present only at the BASE — findings this card removed | {len(removed)} |")
    print()

    def block(title: str, keys: list[tuple], source: dict[tuple, dict]) -> None:
        print(f"## {title} ({len(keys)})")
        print()
        if not keys:
            print("none")
            print()
            return
        print("| sha16 | verdict | baseline outcome | fields / exception | in the named population |")
        print("|---|---|---|---|---|")
        for key in keys:
            finding = source[key]
            sha = finding.get("content_sha256", "")
            detail = ", ".join(f"`{name}`" for name in (finding.get("fields") or ())) \
                or (f"`{finding['exception']}`" if finding.get("exception") else "-")
            inside = "yes" if (sha.upper() in named or sha[:16].upper() in named) else "**NO**"
            print(f"| `{sha[:16]}` | `{finding.get('verdict', '')}` | "
                  f"`{finding.get('outcome_class', '')}` | {detail} | {inside} |")
        print()

    block("This card's movers", added, tip)
    block("Findings this card removed", removed, base)

    outside = [key for key in added
               if key[0].upper() not in named and key[0][:16].upper() not in named]
    print(f"MOVERS_AT_THE_TIP={len(added)} OUTSIDE_THE_NAMED_POPULATION={len(outside)} "
          f"INHERITED={len(inherited)} REMOVED={len(removed)}")
    return 2 if outside else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

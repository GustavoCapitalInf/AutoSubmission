"""The tampering signature in the LILI family, measured — W3 §LILI §L2.

Five documents of one account in the census family print, inside five
DIFFERENT declared periods, a block of postings dated outside the period they
sit in. This tool measures whether those blocks are the same block:

    python -m tools.lili_integrity_fingerprint --data-dir <checkout>/webapp_data

READ-ONLY, $0.00, index-free — OCR payloads by direct artifact path, the
`webapp_data` sqlite index is never opened, nothing is written, no model call.

THE OUT-OF-PERIOD TOKENS SPLIT IN TWO, and the split is what makes the finding
legible:

* `historical` — dated in a calendar year the declared period does not touch.
  This is the pasted block.
* `drifted`    — dated in the period's own year but outside its range,
  including dates AFTER the period ends. A closed statement cannot post a row
  from the future.

WHAT IT PRINTS, and what it deliberately does not. Per document: how many
printed `mm/dd/yyyy` tokens it carries, how many are historical, how many are
drifted, how many distinct reference-number-shaped tokens sit in the block,
and TWO ONE-WAY FINGERPRINTS — the SHA-256 prefix of the sorted historical
DATE multiset, and of the sorted REFERENCE set. No token, figure, date,
reference number, name or amount is printed: a hash is evidence that two
blocks are the same block without reproducing either, which is exactly what
this finding needs and what the wave's privacy rule requires.

Order-independence is the point of using a SORTED multiset. These documents'
text layers shred the same rows into different line orders, so a fingerprint
over the text as printed would report five different blocks where there is
one.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

from analysis.date_tokens import MONTH_NUMBERS
from tools.lili_family_replay import (
    DEFAULT_CENSUS, DEFAULT_FAMILY, cached_text, family_shas,
)

_PRINTED_DATE_RE = re.compile(r"(?<![\d/])(\d{2})/(\d{2})/(\d{4})(?![\d/])")
_PERIOD_RE = re.compile(
    r"(?:Account\s+Number\s+Statement\s+Period|Statement\s+Period\s+Account\s+Number)"
    r"\s+\d+\s+(\d{1,2})\s+([A-Za-z]+),\s+(\d{4})\s*[-−–—]\s*"
    r"(\d{1,2})\s+([A-Za-z]+),\s+(\d{4})"
)
_REFERENCE_RE = re.compile(r"(?<![\d/])\d{6,10}(?![\d/])")
#: How far either side of an out-of-period date the block is taken to extend.
#: These text layers spread one posting over three or four lines.
_BLOCK_MARGIN = 3


def _period(text: str) -> tuple[date, date] | None:
    match = _PERIOD_RE.search(text)
    if match is None:
        return None
    try:
        start = date(int(match.group(3)), MONTH_NUMBERS[match.group(2).casefold()],
                     int(match.group(1)))
        end = date(int(match.group(6)), MONTH_NUMBERS[match.group(5).casefold()],
                   int(match.group(4)))
    except (KeyError, ValueError):
        return None
    return start, end


def _digest(values) -> str:
    return hashlib.sha256("".join(sorted(values)).encode("utf-8")).hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--census", default=DEFAULT_CENSUS, type=Path)
    parser.add_argument("--family", default=DEFAULT_FAMILY)
    args = parser.parse_args()

    artifacts = args.data_dir / "artifacts"
    header = (f"{'sha16':18} {'dates':>6} {'histor':>7} {'drift':>6} {'refs':>5} "
              f"{'date fingerprint':18} {'reference fingerprint':22}")
    print(header)
    groups: dict[tuple[str, str], list[str]] = {}
    for sha in family_shas(args.census, args.family):
        text = cached_text(artifacts, sha)
        if text is None:
            print(f"{sha[:16]:18} no cached OCR artifact")
            continue
        bounds = _period(text)
        if bounds is None:
            print(f"{sha[:16]:18} period unreadable")
            continue
        start, end = bounds
        years = {start.year, end.year}
        lines = text.splitlines()
        total = drifted = 0
        historical: list[str] = []
        marked: set[int] = set()
        for index, line in enumerate(lines):
            for match in _PRINTED_DATE_RE.finditer(line):
                total += 1
                try:
                    printed = date(int(match.group(3)), int(match.group(1)),
                                   int(match.group(2)))
                except ValueError:
                    drifted += 1
                    marked.add(index)
                    continue
                if start <= printed <= end:
                    continue
                marked.add(index)
                if printed.year in years:
                    drifted += 1
                else:
                    historical.append(printed.isoformat())
        if not marked:
            print(f"{sha[:16]:18} {total:6} {0:7} {0:6} {'-':>5} {'-':18} {'-':22}")
            continue
        low = max(0, min(marked) - _BLOCK_MARGIN)
        high = min(len(lines) - 1, max(marked) + _BLOCK_MARGIN)
        block = " ".join(lines[low:high + 1])
        references = sorted(set(_REFERENCE_RE.findall(block)))
        date_fp, reference_fp = _digest(historical), _digest(references)
        groups.setdefault((date_fp, reference_fp), []).append(sha)
        print(f"{sha[:16]:18} {total:6} {len(historical):7} {drifted:6} "
              f"{len(references):5} {date_fp:18} {reference_fp:22}")

    print("\nDocuments sharing one (historical date, reference) fingerprint:")
    for fingerprint, shas in sorted(groups.items()):
        print(f"  {fingerprint[0]} / {fingerprint[1]}   x{len(shas)}")
        for sha in sorted(shas):
            print(f"      {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

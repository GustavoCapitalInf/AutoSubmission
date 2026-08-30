"""L1-ARCH-DESIGN instrument 6 — READ-ONLY internal-transfer evidence probe.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**

The design's §3 took "7 documents / 47 pairs" from
`tools/l1_split_prototype.py::_transfer_pairs`, which pairs on date, magnitude
and sign and reads nothing else. The review's BLOCK-4 is that three different
things are wrong with using that number as the design's killer population, and
all three are measurable:

1. **No printed evidence is required and none was measured.** A member who
   deposits a sum into checking on the day they withdraw the same sum from
   savings for an unrelated purpose produces a unique, unambiguous, entirely
   non-internal pair — and the design's rule would flag it and its own
   consequence would then delete that deposit from every package total. That is
   money the paper printed, removed by an inference.
2. **The counted population does not implement the design's own rule.**
   `_transfer_pairs` takes the FIRST admissible counterpart and breaks; §3.3
   says two admissible counterparts record NOTHING.
3. **One-to-one does not hold past two ledgers.** `taken` is re-initialised per
   `(left, right)` ledger pair, so on a document with three or more live ledgers
   one posting can be counted into two pairs.

WHAT THIS MEASURES
------------------
Over the same population, from the same reconstruction (`l1_split_prototype`'s
own `run_document`, called unchanged):

* the **greedy** count — the published 47, reproduced, so the corrected figures
  are comparable with it;
* the **unique-counterpart** count, which is §3.3's own fail-closed rule: a
  posting with two or more admissible counterparts pairs with none of them;
* the **document-wide one-to-one** count, where `taken` is a single set across
  every ledger of the document rather than one per ledger pair;
* how many pairs carry a **PRINTED transfer designation** on either leg,
  decided by `analysis/transaction_classifier.py`'s OWN committed vocabularies
  (`_INTERNAL_TRANSFER_CREDIT_PATTERNS`, 13 patterns, and `_TRANSFER_PATTERNS`,
  7) — this instrument writes no transfer grammar of its own;
* how many documents reconstruct **three or more** live ledgers, which is where
  problem 3 can bite at all.

THE DESCRIPTIONS
----------------
`l1_split_prototype.SectionResult.postings` keeps `(date, amount)` and drops the
description the walk read. This probe recovers it without touching that
instrument: `chain_walk` is wrapped for the duration of the run and every `Walk`
it returns is stashed; after each section is reconstructed, the walk whose
`(date, amount)` sequence EQUALS that section's `postings` is the one that was
accepted, and its rows carry the printed text on both sides of the figures.
Where that correlation is not unique the section is reported as
`description-unavailable` and is excluded from the designation counts rather
than guessed at — the count of such sections is printed.

PRIVACY
-------
Content sha16s and counts. Descriptions are read only to ask a committed
pattern whether it matches; no description, amount or date is printed.

Usage:

    python -m tools.l1_design_transfer_probe --census-dir <census> --data-dir <cold cache> \
        [--json <private>.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import load_census  # noqa: E402
from tools import l1_split_prototype as proto  # noqa: E402


# ---------------------------------------------------------------------------
# recovering the printed text the walk read
# ---------------------------------------------------------------------------


class WalkCapture:
    """Stashes every `Walk` `chain_walk` returns, for correlation afterwards."""

    def __init__(self):
        self.walks: list = []
        self._original = None

    def __enter__(self):
        self._original = proto.chain_walk

        def watched(*args, **kwargs):
            walk = self._original(*args, **kwargs)
            self.walks.append(walk)
            return walk

        proto.chain_walk = watched
        return self

    def __exit__(self, *exc):
        proto.chain_walk = self._original
        return False


def _descriptions_for(section, walks) -> list[str] | None:
    """The printed text of each accepted posting, or None if not unique."""
    want = list(section.postings)
    matches = []
    for walk in walks:
        got = [(iso, amount) for iso, amount, _b, _t in walk.rows]
        if got == want:
            matches.append(walk)
    if len(matches) != 1:
        return None
    out: list[str] = []
    for _iso, _amount, _balance, text in matches[0].rows:
        leading, trailing = text if isinstance(text, tuple) else ("", "")
        out.append(f"{leading} {trailing}".strip())
    return out


# ---------------------------------------------------------------------------
# the printed designation, by production's OWN vocabulary
# ---------------------------------------------------------------------------


def prints_transfer_designation(description: str) -> bool:
    from analysis.transaction_classifier import (
        _INTERNAL_TRANSFER_CREDIT_PATTERNS,
        _TRANSFER_PATTERNS,
    )

    upper = description.upper()
    for pattern in _INTERNAL_TRANSFER_CREDIT_PATTERNS:
        if pattern.search(upper):
            return True
    for pattern in _TRANSFER_PATTERNS:
        if pattern.search(upper):
            return True
    return False


# ---------------------------------------------------------------------------
# the three pairing rules
# ---------------------------------------------------------------------------


@dataclass
class Posting:
    ledger: int
    index: int
    date: str
    amount: float
    description: str | None


def _admissible(a: Posting, b: Posting) -> bool:
    """Same posting date, same magnitude to the cent, opposite sign."""
    return (a.date == b.date
            and round(abs(a.amount) - abs(b.amount), 2) == 0.0
            and (a.amount > 0) != (b.amount > 0))


def pair_greedy(ledgers: list[list[Posting]]) -> list[tuple[Posting, Posting]]:
    """The published rule: first admissible counterpart wins, `taken` per pair."""
    out: list[tuple[Posting, Posting]] = []
    for i in range(len(ledgers)):
        for j in range(i + 1, len(ledgers)):
            taken: set[int] = set()
            for left in ledgers[i]:
                for right in ledgers[j]:
                    if right.index in taken:
                        continue
                    if _admissible(left, right):
                        taken.add(right.index)
                        out.append((left, right))
                        break
    return out


def pair_unique(ledgers: list[list[Posting]]) -> tuple[list[tuple[Posting, Posting]], int]:
    """§3.3's own rule, document-wide: a posting with two or more admissible
    counterparts anywhere on the document pairs with NONE of them, and the
    match must be mutual."""
    everything = [p for ledger in ledgers for p in ledger]
    by_posting: dict[int, list[Posting]] = {}
    for left in everything:
        candidates = [right for right in everything
                      if right.ledger != left.ledger and _admissible(left, right)]
        by_posting[left.index] = candidates
    ambiguous = sum(1 for candidates in by_posting.values() if len(candidates) > 1)
    out: list[tuple[Posting, Posting]] = []
    seen: set[tuple[int, int]] = set()
    for left in everything:
        candidates = by_posting[left.index]
        if len(candidates) != 1:
            continue
        right = candidates[0]
        if len(by_posting[right.index]) != 1 or by_posting[right.index][0].index != left.index:
            continue
        key = tuple(sorted((left.index, right.index)))
        if key in seen:
            continue
        seen.add(key)
        out.append((left, right))
    return out, ambiguous


def pair_one_to_one(ledgers: list[list[Posting]]) -> list[tuple[Posting, Posting]]:
    """The greedy rule with a DOCUMENT-WIDE `taken`, so no posting is counted
    into two pairs on a document with three or more ledgers."""
    out: list[tuple[Posting, Posting]] = []
    taken: set[int] = set()
    for i in range(len(ledgers)):
        for j in range(i + 1, len(ledgers)):
            for left in ledgers[i]:
                if left.index in taken:
                    continue
                for right in ledgers[j]:
                    if right.index in taken:
                        continue
                    if _admissible(left, right):
                        taken.add(left.index)
                        taken.add(right.index)
                        out.append((left, right))
                        break
    return out


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@dataclass
class DocTransfers:
    sha16: str
    group: str
    live_ledgers: int = 0
    greedy: int = 0
    unique: int = 0
    one_to_one: int = 0
    ambiguous_postings: int = 0
    designated_greedy: int = 0
    designated_unique: int = 0
    sections_without_text: int = 0
    postings_without_text: int = 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design internal-transfer probe")
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    groups, opportunities, per_sha = load_census(args.census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(args.data_dir)

    results: list[DocTransfers] = []
    for band, group, sha16 in proto._population(groups, opportunities):
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        capture = WalkCapture()
        with capture:
            doc = proto.run_document(sha16, group, band, markdown, len(pages))
        live = [s for s in doc.sections if s.postings]
        if len(live) < 2:
            continue
        record = DocTransfers(sha16=sha16, group=group, live_ledgers=len(live))

        ledgers: list[list[Posting]] = []
        index = 0
        for ordinal, section in enumerate(live):
            texts = _descriptions_for(section, capture.walks)
            if texts is None:
                record.sections_without_text += 1
                record.postings_without_text += len(section.postings)
            ledger: list[Posting] = []
            for offset, (iso, amount) in enumerate(section.postings):
                ledger.append(Posting(
                    ledger=ordinal, index=index, date=iso, amount=amount,
                    description=texts[offset] if texts is not None else None))
                index += 1
            ledgers.append(ledger)

        greedy = pair_greedy(ledgers)
        unique, ambiguous = pair_unique(ledgers)
        one_to_one = pair_one_to_one(ledgers)
        record.greedy = len(greedy)
        record.unique = len(unique)
        record.one_to_one = len(one_to_one)
        record.ambiguous_postings = ambiguous

        def designated(pairs) -> int:
            total = 0
            for left, right in pairs:
                texts = [t for t in (left.description, right.description) if t is not None]
                if texts and any(prints_transfer_designation(t) for t in texts):
                    total += 1
            return total

        record.designated_greedy = designated(greedy)
        record.designated_unique = designated(unique)
        results.append(record)

    movers = [r for r in results if r.greedy]
    print("# L1-ARCH-DESIGN — internal transfers: what the paper prints, and what the rule counts")
    print()
    print("Same population, same reconstruction "
          "(`tools/l1_split_prototype.py::run_document`, unchanged). Three "
          "pairing rules over the same postings, and the printed designation "
          "decided by `analysis/transaction_classifier.py`'s OWN committed "
          "vocabularies — 13 internal-transfer credit patterns and 7 transfer "
          "patterns. This instrument writes no transfer grammar.")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents reconstructing two or more LIVE ledgers | {len(results)} |")
    print(f"| ... reconstructing THREE or more | **{sum(1 for r in results if r.live_ledgers >= 3)}** |")
    print(f"| documents the published greedy rule calls transfer movers | **{len(movers)}** |")
    print()

    print("## The same population under three pairing rules")
    print()
    print("| rule | pairs | documents |")
    print("|---|---:|---:|")
    print(f"| **greedy** — first admissible counterpart, `taken` per ledger pair (the published 47) | "
          f"**{sum(r.greedy for r in results)}** | {sum(1 for r in results if r.greedy)} |")
    print(f"| **document-wide one-to-one** — greedy, one `taken` for the whole document | "
          f"**{sum(r.one_to_one for r in results)}** | {sum(1 for r in results if r.one_to_one)} |")
    print(f"| **unique counterpart** — §3.3's own fail-closed rule, mutual and document-wide | "
          f"**{sum(r.unique for r in results)}** | {sum(1 for r in results if r.unique)} |")
    print()
    print(f"Postings with two or more admissible counterparts — the population "
          f"§3.3 refuses to pair and the greedy rule pairs anyway: "
          f"**{sum(r.ambiguous_postings for r in results)}** across "
          f"**{sum(1 for r in results if r.ambiguous_postings)}** documents.")
    print()

    print("## Does the paper print a transfer designation?")
    print()
    print("| population | pairs | pairs with a PRINTED designation on either leg |")
    print("|---|---:|---:|")
    print(f"| greedy | {sum(r.greedy for r in results)} | "
          f"**{sum(r.designated_greedy for r in results)}** |")
    print(f"| unique counterpart | {sum(r.unique for r in results)} | "
          f"**{sum(r.designated_unique for r in results)}** |")
    print()
    print(f"Sections whose accepted walk could not be correlated to its printed "
          f"text, and which are therefore EXCLUDED from the designation counts "
          f"rather than guessed at: "
          f"{sum(r.sections_without_text for r in results)} sections, "
          f"{sum(r.postings_without_text for r in results)} postings.")
    print()

    print("## Per document")
    print()
    print("| sha16 | live ledgers | greedy | one-to-one | unique | ambiguous postings | designated (greedy) |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for record in sorted(results, key=lambda r: (-r.greedy, r.sha16)):
        if not (record.greedy or record.ambiguous_postings):
            continue
        print(f"| `{record.sha16}` | {record.live_ledgers} | {record.greedy} | "
              f"{record.one_to_one} | {record.unique} | "
              f"{record.ambiguous_postings} | {record.designated_greedy} |")
    print()

    if args.json:
        args.json.write_text(json.dumps({
            "documents_two_or_more_ledgers": len(results),
            "documents_three_or_more_ledgers": sum(1 for r in results if r.live_ledgers >= 3),
            "greedy_pairs": sum(r.greedy for r in results),
            "one_to_one_pairs": sum(r.one_to_one for r in results),
            "unique_pairs": sum(r.unique for r in results),
            "ambiguous_postings": sum(r.ambiguous_postings for r in results),
            "designated_greedy": sum(r.designated_greedy for r in results),
            "designated_unique": sum(r.designated_unique for r in results),
            "sections_without_text": sum(r.sections_without_text for r in results),
            "per_document": [vars(r) for r in results],
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""tools/agreement_census.py — the READ-ONLY agreement and geometry census
over a research partition (Phase 2.3 cell X, `docs/agent-handoffs/P23-AGREE.md`
item 3; umbrella D3).

    python -m tools.agreement_census --data-dir <research cache> --research-partition <id>
        [--run <research run dir> | --settings-key <64 hex>]
        [--native-data-dir <cache> --native-run <run dir>]
        [--rows <rows.csv>] [--census <per_sha.csv>] [--label CTRL] [--limit N]

What it prints
--------------
The DISTRIBUTION of every statistic `layout/agreement.py` measures, over the
pages of the partition that carry BOTH a native reading and an extractor
reading — overall, by census family and by modality — plus the rotation,
skew and page-size census over every native page. On the control sample that
distribution IS the calibration ("what agreement looks like on known-good
documents", D3); on the unresolved set it is the thing the calibration is
read against.

COUNTS AND PERCENTILES ONLY. No document text, no line, no word, no figure
read off a statement, no sha beside a verdict — the only identifiers this
tool can print are the population labels it was given and the partition id.
Nothing is written anywhere; both caches and both run directories are opened
read-only. Nothing here decides: a statistic below any calibration is review
evidence (plan §H.4, E4), never a trigger, never a third engine.

Which partition, and how it is found
------------------------------------
A research partition is identified by the OCR settings key its artifacts
were written under, and the key is not recoverable from an artifact (the
partition id is key material, not payload). So the key is taken, in this
order and never by guessing:

1. ``--settings-key`` — given explicitly;
2. ``--run`` — the research run's ``provenance.json``, whose
   ``run_of_record.partitions.research_partition`` must equal
   ``--research-partition`` (a production run, or another partition, is
   refused) and whose ``paddle_ocr_key`` is the key;
3. otherwise the cache is scanned for OCR keys whose artifacts carry
   extractor evidence. Exactly one such key is used and named; zero or more
   than one is a refusal that says so.

Native evidence is read from the SAME artifact record when the research read
attached it, and otherwise — ``--native-data-dir`` with ``--native-run`` —
from the production run of record's own partition, read-only. A document
with only one reading is COUNTED as unpaired and contributes to the geometry
census alone.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

from evidence.canonical import EvidenceError, from_json
from layout.agreement import (
    AGREEMENT_VERSION,
    IOU_THRESHOLD,
    TABLE_REGION_MIN_MONEY,
    TABLE_REGION_VERSION,
    TEXT_NORMALISER_VERSION,
    geometry_census,
    page_agreement,
)

PARTITION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
PERCENTILES = (10, 25, 50, 75, 90)
#: The per-page statistics the census distributes, in report order.
STATISTICS = (
    ("matched_native", "matched, of the native words"),
    ("matched_extractor", "matched, of the extractor words"),
    ("char_agreement", "normalised character agreement"),
    ("amount_agreement", "exact money agreement"),
    ("date_agreement", "exact date agreement"),
    ("unmatched_table_density", "unmatched density in table regions"),
)


class CensusRefused(SystemExit):
    """Anything this tool will not guess about."""


# ---------------------------------------------------------------------------
# the door: a research partition's artifacts
# ---------------------------------------------------------------------------

class _Partition:
    """Read-only artifact resolution for ONE OCR settings key."""

    def __init__(self, data_dir: Path, settings_key: str) -> None:
        self.root = data_dir / "artifacts"
        self.key = settings_key
        self.conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)

    def close(self) -> None:
        self.conn.close()

    def shas(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT input_sha256 FROM artifact_cache WHERE stage='ocr' AND settings_key=? "
            "ORDER BY input_sha256", (self.key,),
        ).fetchall()
        return [str(row[0]).upper() for row in rows]

    def document(self, sha: str) -> dict | None:
        row = self.conn.execute(
            "SELECT artifact_path FROM artifact_cache WHERE stage='ocr' AND settings_key=? "
            "AND input_sha256=?", (self.key, sha),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads((self.root / str(row[0])).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        document = (payload.get("artifact") or {}).get("document")
        return document if isinstance(document, dict) else None


def _key_from_run(run: Path, partition: str) -> str:
    provenance = json.loads((run / "provenance.json").read_text(encoding="utf-8"))
    block = (provenance.get("run_of_record") or {}).get("partitions") or {}
    recorded = block.get("research_partition") or ""
    if recorded != partition:
        raise CensusRefused(
            f"refusing {run}: its recorded research_partition is {recorded!r}, not {partition!r} — "
            "a census of one partition never reads another's artifacts"
        )
    key = block.get("paddle_ocr_key") or block.get("offline_ocr_key")
    if not key:
        raise CensusRefused(f"refusing {run}: provenance.json records no OCR settings key")
    return str(key)


def _key_by_scan(data_dir: Path) -> str:
    """Every OCR key whose artifacts carry extractor evidence; exactly one or
    a refusal that names the count."""
    conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
    root = data_dir / "artifacts"
    try:
        keys = [str(row[0]) for row in conn.execute(
            "SELECT DISTINCT settings_key FROM artifact_cache WHERE stage='ocr' ORDER BY settings_key")]
        with_evidence: list[str] = []
        for key in keys:
            rows = conn.execute(
                "SELECT artifact_path FROM artifact_cache WHERE stage='ocr' AND settings_key=? LIMIT 25",
                (key,),
            ).fetchall()
            for row in rows:
                try:
                    payload = json.loads((root / str(row[0])).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                document = (payload.get("artifact") or {}).get("document") or {}
                if isinstance(document, dict) and isinstance(document.get("evidence"), dict):
                    with_evidence.append(key)
                    break
    finally:
        conn.close()
    if len(with_evidence) != 1:
        raise CensusRefused(
            f"refusing to guess the partition key: {len(with_evidence)} of the cache's {len(keys)} OCR "
            "keys carry extractor evidence; pass --run or --settings-key"
        )
    return with_evidence[0]


# ---------------------------------------------------------------------------
# grouping facts (never a value, never a verdict beside a sha)
# ---------------------------------------------------------------------------

def _modalities(rows: Path | None) -> dict[str, str]:
    if rows is None:
        return {}
    import csv

    facts: dict[str, str] = {}
    with rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if sha and sha not in facts:
                facts[sha] = (row.get("class_modality") or "unknown").strip() or "unknown"
    return facts


def _families(census: Path | None) -> dict[str, str]:
    if census is None or not census.is_file():
        return {}
    import csv

    facts: dict[str, str] = {}
    with census.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("sha") or "").strip().upper()
            if sha:
                facts[sha] = (row.get("b8_family") or "").strip() or "unnamed"
    return facts


# ---------------------------------------------------------------------------
# distributions
# ---------------------------------------------------------------------------

def _percentile(values: list[float], percent: int) -> float:
    """Nearest-rank: no interpolation, so a printed percentile is always a
    value the corpus actually produced."""
    rank = max(1, math.ceil(percent / 100 * len(values)))
    return values[min(rank, len(values)) - 1]


def _distribution(values: list[float]) -> str:
    if not values:
        return f"{'n=0':>8}" + " " * (9 * (len(PERCENTILES) + 1))
    ordered = sorted(values)
    mean = sum(ordered) / len(ordered)
    cells = "".join(f"{_percentile(ordered, p):>9.4f}" for p in PERCENTILES)
    return f"{'n=' + str(len(ordered)):>8}{mean:>9.4f}{cells}"


def _header(title: str) -> None:
    print(f"\n## {title}")
    print(f"  {'statistic':<38}{'count':>8}{'mean':>9}" + "".join(f"{'p' + str(p):>9}" for p in PERCENTILES))


def _report(title: str, pages: list) -> None:
    if not pages:
        return
    _header(title)
    for attribute, label in STATISTICS:
        values = [getattr(page, attribute) for page in pages]
        _distribution_line(label, [value for value in values if value is not None])


def _distribution_line(label: str, values: list[float]) -> None:
    print(f"  {label:<38}{_distribution(values)}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--research-partition", required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--settings-key")
    parser.add_argument("--native-data-dir", type=Path)
    parser.add_argument("--native-run", type=Path)
    parser.add_argument("--rows", type=Path, help="a run's rows.csv, for the modality of each sha")
    parser.add_argument("--census", type=Path, help="census_batch9/per_sha.csv, for the census family")
    parser.add_argument("--label", default="partition", help="the population's name (CTRL, U755, ...)")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    if PARTITION_PATTERN.fullmatch(args.research_partition) is None:
        raise CensusRefused(
            f"refusing --research-partition {args.research_partition!r}: it must match "
            f"{PARTITION_PATTERN.pattern} (the partition-id shape the OCR settings key validates)"
        )
    if args.settings_key:
        key, door = str(args.settings_key), "--settings-key"
    elif args.run:
        key, door = _key_from_run(args.run, args.research_partition), f"{args.run}/provenance.json"
    else:
        key, door = _key_by_scan(args.data_dir), "the cache scan (one key carries extractor evidence)"

    partition = _Partition(args.data_dir, key)
    native_partition = None
    if args.native_data_dir is not None:
        if args.native_run is None:
            raise CensusRefused("--native-data-dir needs --native-run (which partition of it to read)")
        from telemetry.run_of_record import partitions_for_run

        recorded = partitions_for_run(args.native_run)
        native_partition = _Partition(args.native_data_dir, recorded.ocr_keys_by_source["native"])

    modalities = _modalities(args.rows)
    families = _families(args.census)

    documents = partition.shas()
    if args.limit:
        documents = documents[: args.limit]

    all_pages: list = []
    by_modality: dict[str, list] = collections.defaultdict(list)
    by_family: dict[str, list] = collections.defaultdict(list)
    geometry: list = []
    paired = unpaired = unreadable = 0
    frame_mismatch_pages = 0
    rotations: collections.Counter = collections.Counter()
    sizes: collections.Counter = collections.Counter()
    skews: list[float] = []

    for sha in documents:
        record = partition.document(sha)
        if record is None:
            unreadable += 1
            continue
        extractor = _evidence(record.get("evidence"))
        native = _evidence(record.get("native_evidence"))
        if native is None and native_partition is not None:
            other = native_partition.document(sha)
            if other is not None:
                native = _evidence(other.get("native_evidence")) or _evidence(other.get("evidence"))
        source = native or extractor
        if source is not None:
            for facts in geometry_census(source):
                geometry.append(facts)
                rotations[facts.rotation_deg] += 1
                sizes[facts.page_size] += 1
                if facts.skew_deg is not None:
                    skews.append(facts.skew_deg)
        if native is None or extractor is None:
            unpaired += 1
            continue
        paired += 1
        extractor_pages = {page.frame.page_index: page for page in extractor.pages}
        for page in native.pages:
            other = extractor_pages.get(page.frame.page_index)
            if other is None:
                continue
            result = page_agreement(page, other)
            all_pages.append(result)
            frame_mismatch_pages += int(result.frame_mismatch)
            by_modality[modalities.get(sha, "unknown")].append(result)
            by_family[families.get(sha, "validated_or_unlisted")].append(result)

    print(f"\n# agreement census — population {args.label}, partition {args.research_partition}")
    print(f"  cache                 {args.data_dir}")
    print(f"  settings key via      {door}")
    print(f"  agreement version {AGREEMENT_VERSION} · IoU {IOU_THRESHOLD} · normaliser "
          f"{TEXT_NORMALISER_VERSION} · table region {TABLE_REGION_VERSION}"
          f" (>= {TABLE_REGION_MIN_MONEY} money shapes)")
    print(f"  documents in the partition                  {len(documents):>9}")
    print(f"  documents with BOTH readings (paired)       {paired:>9}")
    print(f"  documents with one reading (unpaired)       {unpaired:>9}")
    print(f"  documents whose record could not be read    {unreadable:>9}")
    print(f"  pages compared                              {len(all_pages):>9}")
    print(f"  pages whose two frames disagree             {frame_mismatch_pages:>9}")

    _report(f"distribution over every compared page ({args.label})", all_pages)
    for modality in sorted(by_modality):
        _report(f"by modality: {modality}", by_modality[modality])
    for family in sorted(by_family):
        _report(f"by census family: {family}", by_family[family])

    print(f"\n## geometry census ({args.label}; every page of the native reading)")
    print(f"  pages                                       {len(geometry):>9}")
    for rotation, count in sorted(rotations.items()):
        print(f"  rotation {rotation:>3} deg                             {count:>9}")
    _header("skew")
    _distribution_line("skew, degrees", skews)
    print(f"\n  page sizes (points, most common first; {len(sizes)} distinct)")
    for (width, height), count in sizes.most_common(12):
        print(f"    {width:>8.1f} x {height:<8.1f}{count:>9}")

    partition.close()
    if native_partition is not None:
        native_partition.close()
    return 0


def _evidence(payload):
    if not isinstance(payload, dict):
        return None
    try:
        return from_json(payload)
    except EvidenceError:
        return None


if __name__ == "__main__":
    sys.exit(main())

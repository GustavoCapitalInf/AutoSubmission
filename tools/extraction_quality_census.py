"""tools/extraction_quality_census.py — the extraction-quality census over a
RESEARCH partition's cached OCR artifacts (P23-EGATE item 5).

    python -m tools.extraction_quality_census --data-dir <research dir>
           --research-partition <id> [--rasters <dir>] [--out <git-ignored>.md]

What it does
------------
Reads the cached OCR artifacts under a research `--data-dir`, measures every
page of every EXTRACTOR evidence it finds with `ocr.extraction_quality`, and
prints the distribution of each metric and the E-class counts **per
configuration** — the configuration being the extractor's OWN recorded
identity (its id, its model token, the detection and recognition models, the
pipeline switches and the dpi from `ExtractionEvidence.runtime`), never a
label passed on the command line. That is what makes "never compared across
configurations" a property of the instrument rather than a discipline: two
configurations are two tables, and a rec-score column in one of them is not
the same measurement as the one beside it.

What it prints, and what it cannot
----------------------------------
COUNTS AND PERCENTILES ONLY. No page text, no line, no word, no document sha,
no file path, no verdict — and no sha beside a verdict, which is the shape
the standing rule forbids. The output of this tool is safe to paste into a
W3 section, and `tests/test_extraction_quality_census.py` asserts that over a
partition built from synthetic pages whose literal strings it then greps for.

Read-only, and refused at the door
----------------------------------
Nothing is written under `--data-dir`: the artifacts are read as JSON and the
SQLite index is never opened. A `--data-dir` that is, or is inside, the live
cache, a `webapp_data*` directory or the read-only recovery area is refused
by `discovery.runner.refuse_production_data_dir` — cell T's door, imported
rather than re-implemented, so this tool and the research runner cannot
disagree about what a production cache is. `--research-partition` is
shape-validated by the same pattern the runner uses and is recorded in the
header as the partition the operator DECLARED this directory holds; the
numbers themselves are grouped by the configurations actually found.

Rasters
-------
The ink metric needs pixels. A research partition retains them (Phase 2.3
D2) at `<data-dir>/rasters/<document sha>/pNNNN.png`; the original synthetic
partition's `<page index>.png` spelling remains readable. `--rasters`
points somewhere else. Where a page's raster is absent the ink metric is
UNMEASURED for that page and the census says how many pages that was — never
zero, which would read as a page with no ink outside its boxes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from discovery.runner import RESEARCH_PARTITION_PATTERN, refuse_production_data_dir  # noqa: E402
from evidence.canonical import EvidenceError, ExtractionEvidence, from_json  # noqa: E402
from ocr.extraction_quality import (  # noqa: E402
    EXTRACTION_QUALITY_VERSION,
    EQ_ROW_COLUMNS,
    E_CLASS_PRIORITY,
    RasterGray,
    document_quality,
)

#: The per-page figures the census distributes, in the order it prints them:
#: `(the PageQuality attribute, what it means)`. The note travels with the
#: table so a reader of the output knows what a column is without consulting
#: the module that produced it.
PAGE_METRICS: tuple[tuple[str, str], ...] = (
    ("word_count", "words on the page"),
    ("density", "words per square unit of the frame's own space"),
    ("rec_mean", "mean recognition score (per configuration only)"),
    ("rec_p10", "10th-percentile recognition score (per configuration only)"),
    ("money_rate", "numeric tokens that parse as money"),
    ("lexicon_rate", "alphabetic tokens that are statement furniture"),
    ("garbage_rate", "tokens that are over-long or a repeated-letter run"),
    ("line_height_cv", "line-height coefficient of variation"),
    ("right_edge_residual", "numeric right-edge residual, in character widths"),
    ("ink_share", "share of the raster that is ink"),
    ("ink_outside_boxes", "share of that ink outside every word box"),
    ("orientation_horizontal", "horizontal word-geometry votes"),
    ("orientation_vertical", "vertical word-geometry votes"),
    ("orientation_indeterminate", "indeterminate word-geometry votes"),
    ("orientation_vertical_share", "vertical share of decided geometry votes"),
)

DOCUMENT_METRICS: tuple[tuple[str, str], ...] = tuple(
    (attribute, note) for _, attribute, note in EQ_ROW_COLUMNS
    if attribute not in {"version", "e_class"}
)

#: The percentiles printed for every metric. Nearest-rank, no interpolation.
PERCENTILES: tuple[int, ...] = (5, 25, 50, 75, 95)


def percentile(values: Sequence[float], percent: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * percent / 100.0))
    return ordered[min(rank, len(ordered)) - 1]


def configuration_of(evidence: ExtractionEvidence) -> str:
    """The extractor's OWN recorded identity, as one label.

    Built from `runtime` field by field (the same whitelist discipline
    `ocr/paddle_rung.py` applies when it writes them): a worker that echoed
    an extra key cannot widen this label, and a configuration that recorded
    nothing shows as `unrecorded` rather than silently joining another."""
    runtime = evidence.runtime or {}
    parts = [f"extractor={evidence.extractor_id}", f"model={evidence.model_token}"]
    for name in ("text_detection_model_name", "text_recognition_model_name",
                 "pipeline_switches", "dpi", "provider", "execution_class"):
        value = runtime.get(name)
        if value is not None:
            parts.append(f"{name}={_flat(value)}")
    return " | ".join(parts)


def _flat(value: Any) -> str:
    if isinstance(value, Mapping):
        return "{" + ",".join(f"{key}:{_flat(value[key])}" for key in sorted(value)) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_flat(item) for item in value) + "]"
    return str(value)


def ocr_records(data_dir: Path) -> Iterator[dict]:
    """Every cached OCR artifact's `document` payload, read as JSON.

    The SQLite index is deliberately not opened: this is a reader, and a
    reader that opens a database can create one."""
    stage = data_dir / "artifacts" / "ocr"
    if not stage.is_dir():
        raise SystemExit(
            f"no OCR artifacts under {stage} — a research partition's cache holds them at "
            "<data-dir>/artifacts/ocr/<shard>/<key>.json"
        )
    for path in sorted(stage.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            yield {"_unreadable": True}
            continue
        artifact = payload.get("artifact") if isinstance(payload, dict) else None
        document = artifact.get("document") if isinstance(artifact, dict) else None
        yield document if isinstance(document, dict) else {"_negative": True}


class LazyRasters:
    """A page -> `RasterGray` mapping that opens ONE raster at a time.

    `document_quality` only ever calls `.get(page_index)`, so this is all the
    mapping it needs — and it is the difference between holding one page's
    pixels and holding a whole document's. A 300-dpi Letter page is ~8 MB of
    grey; a fifty-page statement measured eagerly would be 400 MB, on a host
    where that is a quarter of the memory there is. Nothing is cached: each
    page is decoded, measured and dropped."""

    def __init__(self, root: Path | None, evidence: ExtractionEvidence) -> None:
        self.root = root
        self.evidence = evidence
        self.statuses: Counter[str] = Counter()

    def get(self, page_index: int, default: Any = None) -> Any:
        found = raster_for(self.root, self.evidence, page_index, statuses=self.statuses)
        return default if found is None else found


def raster_for(root: Path | None, evidence: ExtractionEvidence, page_index: int,
               *, statuses: Counter[str] | None = None) -> RasterGray | None:
    """The wave's `pNNNN.png` (or legacy synthetic `<index>.png`), decoded to grey, or
    `None` when it is not there. The decode lives HERE, not in the metrics
    module, whose import set is the standard library, `evidence` and
    `layout.signals` and nothing else."""
    def record(status: str) -> None:
        if statuses is not None:
            statuses[status] += 1

    if root is None:
        record("absent")
        return None
    sha = evidence.document_sha256
    candidates = (
        root / name / filename
        for filename in (f"p{page_index:04d}.png", f"{page_index}.png")
        for name in dict.fromkeys((sha, sha.upper(), sha.lower()))
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        record("absent")
        return None
    from PIL import Image

    frame = next((page.frame for page in evidence.pages if page.frame.page_index == page_index), None)
    if frame is None:
        record("frame absent")
        return None
    try:
        payload = path.read_bytes()
        expected = frame.raster_sha256
        if expected is not None and hashlib.sha256(payload).hexdigest().upper() != expected.upper():
            record("hash mismatch (unmeasured)")
            return None
        with Image.open(BytesIO(payload)) as image:
            grey = image.convert("L")
            raster = RasterGray(width=grey.width, height=grey.height, pixels=grey.tobytes())
    except (OSError, ValueError):
        record("unreadable (unmeasured)")
        return None
    # A native synthetic frame can legitimately carry no raster hash. It is
    # measured but explicitly distinguished from evidence-bound pixels.
    record("hash verified" if expected is not None else "no recorded hash (unverified)")
    return raster


class Census:
    """One configuration's accumulated figures. Counts and values only — no
    identifier of any document is retained, so none can be printed."""

    def __init__(self) -> None:
        self.documents = 0
        self.pages = 0
        self.values: dict[str, list[float]] = {name: [] for name, _ in PAGE_METRICS}
        self.document_values: dict[str, list[float]] = {name: [] for name, _ in DOCUMENT_METRICS}
        self.page_classes: Counter[str] = Counter()
        self.document_classes: Counter[str] = Counter()
        #: every class each page fired, not only the one precedence reports.
        #: OVERLAPPING by construction and never summed: a page whose boxes
        #: do not cover its ink AND read down the sheet is two findings, and
        #: a census that kept only the reported one would hide the second.
        self.page_classes_any: Counter[str] = Counter()
        self.rasters_measured = 0
        self.rasters_absent = 0
        self.raster_statuses: Counter[str] = Counter()

    def add(self, quality) -> None:
        self.documents += 1
        for name, _ in DOCUMENT_METRICS:
            value = getattr(quality, name)
            if value is not None:
                self.document_values[name].append(float(value))
        for page in quality.pages:
            self.pages += 1
            for name, _ in PAGE_METRICS:
                if name.startswith("orientation_"):
                    votes = page.orientation_votes
                    value = None if votes is None else getattr(votes, name.removeprefix("orientation_"))
                else:
                    value = getattr(page, name)
                if value is not None:
                    self.values[name].append(float(value))
            if page.ink_outside_boxes is None and page.ink_share is None:
                self.rasters_absent += 1
            else:
                self.rasters_measured += 1
            self.page_classes[page.e_class or "(none)"] += 1
            for name in page.classes:
                self.page_classes_any[name] += 1
        self.document_classes[quality.e_class or "(none)"] += 1


def render(partition: str, censuses: Mapping[str, Census], *, skipped: Mapping[str, int]) -> str:
    lines = [
        f"# extraction-quality census - EXTRACTION_QUALITY_VERSION {EXTRACTION_QUALITY_VERSION}",
        "",
        f"declared research partition: `{partition}`",
        "",
        "Counts and percentiles only. No document text, no sha, no path, no verdict.",
        "Configurations are never compared with each other: a recognition score means",
        "something only within the configuration that produced it.",
        "",
        "| records | count |",
        "|---|---|",
    ]
    for name in sorted(skipped):
        lines.append(f"| {name} | {skipped[name]} |")
    lines.append("")
    for label in sorted(censuses):
        census = censuses[label]
        lines += [
            f"## configuration: `{label}`",
            "",
            f"documents {census.documents} | pages {census.pages} | "
            f"pages with a raster {census.rasters_measured} | without {census.rasters_absent}",
            "",
            "| metric | measured | min | " + " | ".join(f"p{p:02d}" for p in PERCENTILES) + " | max |",
            "|---|---|---|" + "---|" * (len(PERCENTILES) + 1),
        ]
        for name, note in PAGE_METRICS:
            values = census.values[name]
            if not values:
                lines.append(f"| {name} | 0 | - | " + " | ".join("-" for _ in PERCENTILES) + " | - |")
                continue
            cells = " | ".join(f"{percentile(values, p):.6g}" for p in PERCENTILES)
            lines.append(
                f"| {name} | {len(values)} | {min(values):.6g} | {cells} | {max(values):.6g} |"
            )
        lines += ["", "metric notes: " + "; ".join(f"{name} = {note}" for name, note in PAGE_METRICS), ""]
        lines += ["Raster provenance", "", "| status | pages |", "|---|---|"]
        for status in ("hash verified", "no recorded hash (unverified)", "absent",
                       "hash mismatch (unmeasured)", "unreadable (unmeasured)", "frame absent"):
            lines.append(f"| {status} | {census.raster_statuses[status]} |")
        lines.append("")
        lines += [
            "Document metrics (one folded value per document)", "",
            "| metric | measured | min | " + " | ".join(f"p{p:02d}" for p in PERCENTILES) + " | max |",
            "|---|---|---|" + "---|" * (len(PERCENTILES) + 1),
        ]
        for name, _ in DOCUMENT_METRICS:
            values = census.document_values[name]
            if not values:
                lines.append(f"| {name} | 0 | - | " + " | ".join("-" for _ in PERCENTILES) + " | - |")
                continue
            cells = " | ".join(f"{percentile(values, p):.6g}" for p in PERCENTILES)
            lines.append(f"| {name} | {len(values)} | {min(values):.6g} | {cells} | {max(values):.6g} |")
        lines += ["", "document folds: " + "; ".join(f"{name} = {note}" for name, note in DOCUMENT_METRICS), ""]
        for title, counter, total in (
            ("pages by E-class (the one precedence reports)", census.page_classes, census.pages),
            ("pages by EVERY class that fired (overlapping; never summed)",
             census.page_classes_any, census.pages),
            ("documents by worst-page E-class", census.document_classes, census.documents),
        ):
            lines += [f"{title} (of {total})", "", "| class | count | share |", "|---|---|---|"]
            for name in ("(none)", *E_CLASS_PRIORITY):
                count = counter.get(name, 0)
                share = 0.0 if not total else count / total
                lines.append(f"| {name} | {count} | {share:.4f} |")
            lines.append("")
    return "\n".join(lines) + "\n"


def _refuse_tracked_out(out: Path) -> None:
    """The census prints no identifier, but an `--out` file still lands
    somewhere: the same rule, and the same reason, as `tools/truth_report.py`
    — a private measurement goes to a git-ignored path."""
    try:
        result = subprocess.run(["git", "check-ignore", "-q", str(out)], capture_output=True, text=True)
    except OSError as exc:
        raise SystemExit(
            f"refusing --out {out}: git could not be asked whether the path is ignored "
            f"({type(exc).__name__})"
        )
    if result.returncode != 0:
        raise SystemExit(
            f"refusing --out {out}: the path is not git-ignored (private measurement output only)"
        )


def census(data_dir: Path, *, partition: str, rasters: Path | None,
           shas: frozenset[str] | None = None) -> tuple[dict[str, Census], Counter[str]]:
    if re.fullmatch(RESEARCH_PARTITION_PATTERN, partition) is None:
        raise SystemExit(
            f"--research-partition {partition!r} must match {RESEARCH_PARTITION_PATTERN}: "
            "this instrument reads research partitions, never a production cache"
        )
    try:
        refuse_production_data_dir(data_dir)
    except ValueError as refusal:
        # The DOOR is cell T's and works; the presentation was this tool's
        # (review MINOR-5). A refusal that escapes as a traceback reads like a
        # crash — the one shape an operator is most likely to retry around —
        # while every other refusal here is a named message and an exit code.
        raise SystemExit(f"REFUSED: {refusal}") from None

    censuses: dict[str, Census] = {}
    skipped: Counter[str] = Counter()
    seen: dict[tuple[str, str], tuple[str, tuple[int, ...]]] = {}
    measured_shas: set[str] = set()
    for document in ocr_records(data_dir):
        if document.get("_unreadable"):
            skipped["unreadable artifact"] += 1
            continue
        if document.get("_negative"):
            skipped["cached negative result (no read)"] += 1
            continue
        payload = document.get("evidence")
        if payload is None:
            skipped["no extractor evidence (a native or text-only read)"] += 1
            continue
        try:
            evidence = from_json(payload)
        except EvidenceError:
            skipped["evidence that does not reproduce its own sha"] += 1
            continue
        sha = evidence.document_sha256.upper()
        if shas is not None and sha not in shas:
            skipped["extractor evidence outside selected population"] += 1
            continue
        # The page-integrity sidecar is outside evidence_sha256 but affects
        # E5. Compare its effective set too, so duplicate traversal order
        # cannot silently choose a different metric result. Ordering and
        # repeated flags do not change the set document_quality consumes.
        truncated = tuple(sorted({
            int(entry.get("page_index", index))
            for index, entry in enumerate(document.get("page_integrity") or [])
            if isinstance(entry, dict) and entry.get("truncated")
        } & {page.frame.page_index for page in evidence.pages}))
        metric_identity = (evidence.evidence_sha256, truncated)
        identity = (configuration_of(evidence), sha)
        if identity in seen:
            if seen[identity] != metric_identity:
                raise SystemExit("REFUSED: conflicting evidence or truncation metadata for one document and configuration")
            skipped["duplicate evidence artifact"] += 1
            continue
        seen[identity] = metric_identity
        measured_shas.add(sha)
        page_rasters = LazyRasters(rasters, evidence)
        quality = document_quality(evidence, rasters=page_rasters, truncated_pages=truncated)
        counted = censuses.setdefault(configuration_of(evidence), Census())
        counted.add(quality)
        counted.raster_statuses.update(page_rasters.statuses)
        skipped["measured"] += 1
    if shas is not None:
        skipped["selected documents"] = len(shas)
        skipped["selected documents without measurable evidence"] = len(shas - measured_shas)
    return censuses, skipped


def read_population(path: Path) -> frozenset[str]:
    """Read the wave's SHA-only population file, without echoing its contents."""
    values = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        value = line.split("#", 1)[0].strip().upper()
        if not value:
            continue
        if re.fullmatch(r"[A-F0-9]{64}", value) is None:
            raise SystemExit("REFUSED: population file must contain full content hashes only")
        values.append(value)
    if not values:
        raise SystemExit("REFUSED: population file is empty")
    return frozenset(values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, required=True,
                        help="the research run's own cache directory (never a production one)")
    parser.add_argument("--research-partition", required=True,
                        help="the partition id this directory was written under")
    parser.add_argument("--rasters", type=Path, default=None,
                        help="retained page rasters (default: <data-dir>/rasters)")
    parser.add_argument("--out", type=Path, default=None, help="write the tables here too (git-ignored)")
    parser.add_argument("--shas", type=Path, default=None,
                        help="optional wave population file; identifiers are never printed")
    args = parser.parse_args(argv)

    if args.out is not None:
        _refuse_tracked_out(args.out)
    rasters = args.rasters if args.rasters is not None else args.data_dir / "rasters"
    censuses, skipped = census(args.data_dir, partition=args.research_partition,
                               rasters=rasters if rasters.is_dir() else None,
                               shas=None if args.shas is None else read_population(args.shas))
    if not censuses:
        raise SystemExit(
            "no extractor evidence found: this directory holds no page this instrument can measure"
        )
    text = render(args.research_partition, censuses, skipped=skipped)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

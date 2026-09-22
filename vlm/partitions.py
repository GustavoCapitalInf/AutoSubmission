"""Experiment populations: which documents are studied, bound by hash, holdout-checked.

Public manifests carry counts and digests only. Private manifests (`*.private.json`)
carry the archive-relative paths and are never committed.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from discovery.runner import holdout_sha16s_from_digest, read_population
from vlm.receipts import bound, dump_new, need, utc_now

DEFAULT_HOLDOUT_DIGEST = Path("docs/moneythumb-replacement/truth/MANIFEST_DIGEST.txt")
DEFAULT_POPULATIONS_DIR = Path("discovery_reports/train13-logs/populations")
DEFAULT_RUN_OF_RECORD = Path("discovery_reports/TRAIN12-52bd8f2/2026-09-11T040247.502179-0000-fd6b4d7f")
DEFAULT_ARCHIVE_ROOT = Path("Bank Statements")
DEV_SEED = "p3-ceiling-dev-v1"
DEV_SIZE = 20
MANIFEST_VERSION = 1
CUSTOMER_SCOPE = "customer"
SYNTHETIC_SCOPE = "synthetic"
POPULATION_FILES = {"CTRL": "CTRL.shas", "U755": "U755.shas"}


@dataclass(frozen=True)
class Member:
    sha: str
    relative_path: str
    byte_size: int
    page_count: int
    folder_label: str
    classification: str
    outcome_class: str
    account_count: int


def run_rows(run_dir: Path) -> dict[str, dict]:
    with (Path(run_dir) / "rows.csv").open(encoding="utf-8", newline="") as handle:
        return {row["content_sha256"].upper(): row for row in csv.DictReader(handle)}


def set_sha256(shas: Iterable[str]) -> str:
    joined = "\n".join(sorted(s.upper() for s in shas)) + "\n"
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


def dev_slice(shas: Iterable[str], n: int = DEV_SIZE, seed: str = DEV_SEED) -> list[str]:
    ranked = sorted({s.upper() for s in shas}, key=lambda s: hashlib.sha256(f"{seed}:{s}".encode()).hexdigest())
    return sorted(ranked[:n])


def refuse_holdout(shas: Iterable[str], held16: frozenset[str]) -> int:
    hits = sum(1 for s in shas if s[:16].upper() in held16)
    need(hits == 0, "population_overlaps_holdout")
    return hits


def _int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _bucket(pages: int) -> str:
    if pages <= 1:
        return "1"
    if pages <= 5:
        return "2-5"
    if pages <= 15:
        return "6-15"
    return "16+"


def build_manifest(name: str, shas: Iterable[str], *, run_dir: Path = DEFAULT_RUN_OF_RECORD,
                   archive_root: Path = DEFAULT_ARCHIVE_ROOT,
                   holdout_digest: Path = DEFAULT_HOLDOUT_DIGEST) -> tuple[dict, dict]:
    ordered = sorted(s.upper() for s in shas)
    need(len(set(ordered)) == len(ordered), "population_duplicates")
    need(bool(ordered), "population_empty")
    held16 = holdout_sha16s_from_digest(Path(holdout_digest))
    overlap = refuse_holdout(ordered, held16)
    rows = run_rows(run_dir)
    members: list[Member] = []
    for sha in ordered:
        need(sha in rows, "member_not_in_run_of_record")
        row = rows[sha]
        need((Path(archive_root) / row["relative_path"]).is_file(), "member_file_missing")
        members.append(Member(
            sha=sha, relative_path=row["relative_path"], byte_size=_int(row.get("byte_size")),
            page_count=_int(row.get("page_count")), folder_label=row.get("folder_label", ""),
            classification=row.get("classification", ""), outcome_class=row.get("outcome_class", ""),
            account_count=_int(row.get("account_count")),
        ))
    public = {
        "manifest_version": MANIFEST_VERSION,
        "name": name,
        "built_at": utc_now(),
        "documents": len(members),
        "pages": sum(m.page_count for m in members),
        "set_sha256": set_sha256(ordered),
        "run_of_record": str(Path(run_dir)),
        "holdout_digest": bound(Path(holdout_digest)),
        "holdout_overlap": overlap,
        "outcome_classes": dict(sorted(Counter(m.outcome_class for m in members).items())),
        "classifications": dict(sorted(Counter(m.classification for m in members).items())),
        "page_buckets": dict(sorted(Counter(_bucket(m.page_count) for m in members).items())),
        "multi_account_documents": sum(1 for m in members if m.account_count > 1),
    }
    private = {
        "manifest_version": MANIFEST_VERSION,
        "name": name,
        "data_scope": CUSTOMER_SCOPE,   # BLOCK-3: every manifest built from a population file is customer data
        "set_sha256": public["set_sha256"],
        "archive_root": str(Path(archive_root)),
        "members": [asdict(m) for m in members],
    }
    public["data_scope"] = CUSTOMER_SCOPE
    return public, private


def manifest_scope(path: Path) -> str:
    """The data scope a private manifest declares; a manifest without one refuses (never a default)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    scope = data.get("data_scope")
    need(scope in (CUSTOMER_SCOPE, SYNTHETIC_SCOPE), "manifest_scope_missing")
    return scope


def write_manifests(out_dir: Path, *, populations_dir: Path = DEFAULT_POPULATIONS_DIR,
                    run_dir: Path = DEFAULT_RUN_OF_RECORD, archive_root: Path = DEFAULT_ARCHIVE_ROOT,
                    holdout_digest: Path = DEFAULT_HOLDOUT_DIGEST, dev_size: int = DEV_SIZE) -> dict[str, dict]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    populations = {name: read_population(Path(populations_dir) / file) for name, file in POPULATION_FILES.items()}
    populations["DEV"] = frozenset(dev_slice(populations["CTRL"], n=dev_size))
    summary: dict[str, dict] = {}
    for name, shas in populations.items():
        public, private = build_manifest(name, shas, run_dir=run_dir, archive_root=archive_root,
                                         holdout_digest=holdout_digest)
        dump_new(out / f"{name}.manifest.private.json", private)
        public["members_sha256"] = bound(out / f"{name}.manifest.private.json")["sha256"]
        dump_new(out / f"{name}.manifest.json", public)
        summary[name] = public
    return summary


def load_private_manifest(path: Path) -> list[Member]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    need(data.get("manifest_version") == MANIFEST_VERSION, "manifest_version_unexpected")
    return [Member(**m) for m in data["members"]]

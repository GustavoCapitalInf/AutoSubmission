"""Enumerate the corpus root and partition it by the pinned manifest.

The archive is FROZEN (2026-08-06): two enumerations
twelve minutes apart agreed byte-for-byte. That inventory is the discovery
corpus of record, so every run re-verifies it before doing any work — a moved,
added, or resynced file means the thing being measured is not the thing that
was frozen, and the run stops rather than quietly measuring something else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import corpus_gate

#: The frozen archive of record. Files include non-PDFs; bytes are every file
#: under the root, PDFs and not.
FROZEN_FILES = 3768
FROZEN_PDFS = 3615
FROZEN_BYTES = 996_080_803
FROZEN_PINNED = 109
FROZEN_DISCOVERY = 3506


@dataclass(frozen=True)
class Inventory:
    root: Path
    files: int
    pdfs: tuple[str, ...]          # corpus-relative POSIX, sorted
    total_bytes: int
    pinned: tuple[str, ...]        # pinned manifest paths present on disk
    discovery: tuple[str, ...]     # everything else
    missing_pinned: tuple[str, ...] = ()
    #: (manifest spelling, on-disk spelling) where the two differ only by case.
    case_mismatches: tuple[tuple[str, str], ...] = ()
    #: On-disk paths that collide case-insensitively — a real ambiguity, not a
    #: spelling difference, and the only reason the matcher below can be wrong.
    case_collisions: tuple[str, ...] = ()

    @property
    def pdf_count(self) -> int:
        return len(self.pdfs)

    def folder_label(self, relative_path: str) -> str:
        """The human bank label: the top-level folder under the root.

        Folder names are analyst-assigned bank labels, which is what makes
        parser-claim vs folder-label agreement a free detection-accuracy
        reference (WAVE2_BRIEF §9.4).
        """
        head, _, tail = relative_path.partition("/")
        return head if tail else "(root)"

    def disk_spelling(self, relative_path: str) -> str:
        """The on-disk spelling behind a canonical (manifest-spelled) identity.

        Identical to the identity except for the documents in
        `case_mismatches`, where the filesystem kept a different casing than
        the manifest. File I/O must go through this spelling: a
        case-insensitive filesystem forgives opening the manifest spelling,
        but on Linux the case-folded path is the only one that exists.
        Identity, dedup keys, and reports keep the manifest spelling.
        """
        for wanted, actual in self.case_mismatches:
            if wanted == relative_path:
                return actual
        return relative_path


def pinned_manifest() -> list[str]:
    """The 109 pinned corpus paths — the same source the gate enumerates."""
    return corpus_gate.manifest_paths(corpus_gate.read_csv(corpus_gate.BALANCE_CSV))


def pinned_hashes() -> dict[str, str]:
    """Pinned corpus-relative path -> pinned SHA-256 (uppercase hex)."""
    return {
        row["path"]: row["sha256"]
        for row in corpus_gate.read_csv(corpus_gate.BALANCE_CSV)
    }


def enumerate_root(root: Path) -> Inventory:
    """Every file under the root, partitioned by the pinned manifest.

    The partition is case-insensitive, with a collision guard, and that is not
    tidiness — it is load-bearing. On this Windows host the archive created
    `Bank Statements/Scotiabank/` before git checked out the tracked
    `ScotiaBank/`, and Windows keeps the first spelling; `rglob` therefore
    reports a path the manifest does not contain, while every byte-level check
    passes because opening the tracked spelling still resolves. An exact-match
    partition silently moves that pinned statement into the DISCOVERY set,
    where it would be counted as an unknown document and skew every rollup.

    Matching case-insensitively fixes it without hiding it: the difference is
    recorded in `case_mismatches`, and if two on-disk paths ever collide
    case-insensitively (possible on Linux, where they are genuinely different
    files) that is recorded in `case_collisions` and reported as a deviation
    rather than guessed at.

    **`pinned` carries the MANIFEST spelling, not the on-disk one.** Once the
    fold-matcher has decided that a disk path IS a pinned document, the
    manifest spelling is that document's identity for everything downstream —
    dedup, rows, the telemetry hash map. Canonicalising here, at the one
    boundary that makes the decision, is what keeps every consumer from having
    to be case-aware: `DedupIndex.pinned` is keyed by manifest spelling, so a
    disk-spelled identity string-compares unequal against its own pinned entry
    and the document reports as a `pinned_corpus_duplicate` of itself. The
    partition below still subtracts the ON-DISK spelling, because that is what
    `rglob` produced and what must not leak into the discovery set.
    """
    manifest = pinned_manifest()
    by_fold: dict[str, str] = {}
    collisions: list[str] = []
    files = 0
    total_bytes = 0
    pdfs: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        files += 1
        try:
            total_bytes += path.stat().st_size
        except OSError:
            pass
        if path.suffix.lower() != ".pdf":
            continue
        relative = path.relative_to(root).as_posix()
        pdfs.append(relative)
        folded = relative.casefold()
        if folded in by_fold:
            collisions.append(relative)
        else:
            by_fold[folded] = relative

    pinned: list[str] = []          # canonical identity: the manifest spelling
    on_disk: set[str] = set()       # what rglob produced, for the partition
    missing: list[str] = []
    mismatches: list[tuple[str, str]] = []
    for wanted in manifest:
        actual = by_fold.get(wanted.casefold())
        if actual is None:
            missing.append(wanted)
            continue
        pinned.append(wanted)
        on_disk.add(actual)
        if actual != wanted:
            mismatches.append((wanted, actual))

    return Inventory(
        root=root,
        files=files,
        pdfs=tuple(pdfs),
        total_bytes=total_bytes,
        pinned=tuple(sorted(set(pinned))),
        discovery=tuple(sorted(set(pdfs) - on_disk)),
        missing_pinned=tuple(sorted(missing)),
        case_mismatches=tuple(sorted(mismatches)),
        case_collisions=tuple(sorted(collisions)),
    )


def baseline_deviations(inventory: Inventory) -> list[str]:
    """Every way this root differs from the frozen archive of record.

    Empty means "this is the frozen archive". Anything else is reported in
    full and stops the run: DSC-2's numbers are only comparable across
    tranches if every tranche measured the same corpus.
    """
    deviations: list[str] = []
    for label, actual, expected in (
        ("files", inventory.files, FROZEN_FILES),
        ("PDFs", inventory.pdf_count, FROZEN_PDFS),
        ("total bytes", inventory.total_bytes, FROZEN_BYTES),
        ("pinned corpus PDFs", len(inventory.pinned), FROZEN_PINNED),
        ("discovery PDFs", len(inventory.discovery), FROZEN_DISCOVERY),
    ):
        if actual != expected:
            delta = actual - expected
            deviations.append(
                f"{label}: {actual:,} on disk, frozen baseline is {expected:,} "
                f"({delta:+,})"
            )
    for name in inventory.missing_pinned:
        deviations.append(f"pinned corpus document missing from the root: {name}")
    for name in inventory.case_collisions:
        deviations.append(
            f"two documents collide case-insensitively, so the pinned/discovery "
            f"partition is ambiguous: {name}"
        )
    return deviations


def dry_run_deviations(inventory: Inventory) -> list[str]:
    """What must hold for a dry run: the truth set, whole and unambiguous.

    Deliberately NOT the archive baseline. The dry run is defined over the
    pinned manifest, so it must be runnable in any clean checkout — that is
    how every agent proves the runner before the archive is ever touched.
    """
    deviations: list[str] = []
    if len(inventory.pinned) != FROZEN_PINNED:
        deviations.append(
            f"pinned corpus PDFs: {len(inventory.pinned)} on disk, expected {FROZEN_PINNED}"
        )
    for name in inventory.missing_pinned:
        deviations.append(f"pinned corpus document missing from the root: {name}")
    for name in inventory.case_collisions:
        deviations.append(f"case-insensitive collision makes the partition ambiguous: {name}")
    return deviations


@dataclass
class DedupIndex:
    """Content-hash dedup, within the run and against the pinned corpus."""

    pinned: dict[str, str] = field(default_factory=dict)   # sha -> pinned path
    seen: dict[str, str] = field(default_factory=dict)     # sha -> first path here

    @classmethod
    def with_pinned_corpus(cls) -> "DedupIndex":
        return cls(pinned={sha: path for path, sha in pinned_hashes().items()})

    def classify(self, content_sha256: str, relative_path: str) -> tuple[str, str | None]:
        """(status, first_seen_path). Status is unique | duplicate | pinned_corpus_duplicate."""
        pinned_path = self.pinned.get(content_sha256)
        if pinned_path is not None and pinned_path != relative_path:
            return "pinned_corpus_duplicate", pinned_path
        first = self.seen.get(content_sha256)
        if first is not None:
            return "duplicate", first
        self.seen[content_sha256] = relative_path
        return "unique", None

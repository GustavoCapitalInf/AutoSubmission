"""Benchmark set -> corpus source mapping, with SHA-256 verification.

Paths are relative to the corpus root (``Bank Statements/``).  Hashes are the
uppercase SHA-256 of the raw PDF bytes and match the values recorded in
``docs/balance-metrics-audit-results.csv``.

DEVIATION NOTE (recorded for Ocean): the H-2 prompt's source-mapping table
lists the BMO statement under ``Misc/``; on disk (and in the audited balance
CSV) the file lives at ``Others/BMO/BMO_Statement_January_2026 Final-1-2
(1).pdf``.  No file with that name exists under ``Misc/``.  The on-disk path
is encoded here, its hash matches the audit CSV row for the same statement,
and the MoneyThumb upload name (``pdfas/BMO/...``) is consistent with it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkSet:
    """One MoneyThumb benchmark job and its corpus source PDF(s)."""

    name: str                      # results/<name>/response.json
    files: tuple[str, ...]         # corpus-relative PDF paths, package order
    sha256: tuple[str, ...]        # uppercase SHA-256 per file, same order
    package: bool = False          # multi-statement package comparison
    notes: str = ""


SETS: tuple[BenchmarkSet, ...] = (
    BenchmarkSet(
        name="bmo_jan",
        files=("Others/BMO/BMO_Statement_January_2026 Final-1-2 (1).pdf",),
        sha256=("E86143101E28E198EC5278B065E8BA967DD73E9AB735A1CAC4A0FE7CB46CB83F",),
        notes=(
            "Self-contradictory source document (audited). Prompt table said "
            "Misc/; actual corpus location is Others/BMO/ - see module docstring."
        ),
    ),
    BenchmarkSet(
        name="chase_dec",
        files=("Chase/Chase Salomon Dec 2025.pdf",),
        sha256=("8F8AE2F30DEA7BA2A008CDBA5E9E800FC60F7AB4C045AF0ABAD8F12883B4F01D",),
    ),
    BenchmarkSet(
        name="chase_jan_feb_mar",
        files=(
            "Chase/Chase Salomon January.pdf",
            "Chase/Chase Salomomon February 27 2026.pdf",
            "Chase/Chase Salomon March 2026.pdf",
        ),
        sha256=(
            "6C828968ED8E9E761A093F6B9B90F914E7FB49C1D211E8C6B79CB9EEEF9DD14C",
            "41C6E62E613E61BBE545F1416EBAF3FC0355ED85CF4F0D549FC79F3611E56A4B",
            "040261AC8183C1EFB7259EE0841D1CC3500AE47DE8ED675030AE837CF531705B",
        ),
        package=True,
        notes="February filename verified on disk (bank's own 'Salomomon' spelling).",
    ),
    BenchmarkSet(
        name="field_trucking_nov",
        files=("Misc/Field Trucking November 2025 .pdf",),  # trailing space is real
        sha256=("F748A799FDC7F25E8BE88462232E83CD0FBFAC2BB574F65F9B8618F2AB7D0178",),
    ),
    BenchmarkSet(
        name="klr_may",
        files=("Misc/KLR.May 31,2026 (1).pdf",),
        sha256=("A4C49ACBC03D905D3A94369311205E93D52D56CB47822D829DD542C0B39E2BCE",),
        notes="MoneyThumb returned an HTTP 202 stub (no analysis) - capability finding.",
    ),
    BenchmarkSet(
        name="wmb_may",
        files=("Misc/WMB May 25.pdf",),
        sha256=("6EFD091D2A38B437E249D3B37198B0634B1D544EF7A9B689291AC0A776D23C56",),
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


@dataclass
class ManifestCheck:
    ok: bool
    problems: list[str] = field(default_factory=list)


def verify_manifest(corpus_root: Path, sets: tuple[BenchmarkSet, ...] = SETS) -> ManifestCheck:
    """Verify every mapped PDF exists and hashes to the recorded value."""
    problems: list[str] = []
    for benchmark_set in sets:
        for relative, expected in zip(benchmark_set.files, benchmark_set.sha256):
            path = corpus_root / relative
            if not path.is_file():
                problems.append(f"{benchmark_set.name}: missing file {relative}")
                continue
            actual = sha256_file(path)
            if actual != expected.upper():
                problems.append(
                    f"{benchmark_set.name}: hash mismatch for {relative} "
                    f"(expected {expected.upper()[:12]}..., got {actual[:12]}...)"
                )
    return ManifestCheck(ok=not problems, problems=problems)

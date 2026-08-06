"""Deterministic offline corpus gate for the validated statement corpus.

Runs both independent forensic oracles over every corpus PDF and fails red on
any drift from the committed audits. Nothing here calculates a financial value
of its own: it re-runs `adb_forensic_audit` and `balance_forensic_audit`
unchanged and compares their output, field by field, with
`docs/adb-audit-results.csv` and `docs/balance-metrics-audit-results.csv`.

    python corpus_gate.py                     # the gate
    python corpus_gate.py --json report.json  # plus a machine-readable report
    pytest -m corpus                          # same gate, through pytest

Guarantees:

- Offline. No OCR endpoint, no Gemini, no network, no Tesseract binary. The 6
  image-only statements are served from committed OCR artifacts keyed by the
  SHA-256 of their source PDF (see `corpus_artifacts`).
- Complete. Every PDF under the corpus root is accounted for. A statement is
  never skipped silently: a missing artifact, an unpinned file, or an
  unreadable document is a failure, and any deliberate exclusion is named and
  counted in the report.
- Read-only against the truth set. The audit CSVs are consumed, never written.
  Regenerating them is `adb_forensic_audit.py` / `balance_forensic_audit.py`,
  which is a separate, deliberate act.

Exit code 0 when every check passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import adb_forensic_audit
import balance_forensic_audit
from corpus_artifacts import DEFAULT_CACHE, manifest_entries

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "Bank Statements"
ADB_CSV = ROOT / "docs" / "adb-audit-results.csv"
BALANCE_CSV = ROOT / "docs" / "balance-metrics-audit-results.csv"

EXPECTED_PDF_COUNT = 109
EXPECTED_PASS = 106
EXPECTED_WITHHELD = 3
WITHHELD_STATEMENTS = {
    "Ace_Auto_Final_Cut.pdf",
    "BMO_Statement_January_2026 Final-1-2 (1).pdf",
    "IBC April (1).pdf",
}

# Statements the gate cannot cover offline. Empty by design: every image-only
# statement has a committed OCR artifact. An entry here must name the file and
# the reason, and it is reported as an exclusion rather than a pass.
KNOWN_EXCLUSIONS: dict[str, str] = {}

# The audit oracles must stay independent of the production financial modules.
# Built from parts so this file's own source never contains the literals it
# searches for.
FORBIDDEN_MODULES = ("adb", "metrics")
INDEPENDENT_SOURCES = (
    "adb_forensic_audit.py",
    "balance_forensic_audit.py",
    "corpus_artifacts.py",
    "corpus_gate.py",
)


@dataclass
class Check:
    name: str
    ok: bool
    summary: str
    details: list[str] = field(default_factory=list)


@dataclass
class Result:
    checks: list[Check] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def add(self, name: str, ok: bool, summary: str, details: list[str] | None = None) -> Check:
        check = Check(name, ok, summary, list(details or []))
        self.checks.append(check)
        return check

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def as_csv_rows(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, str]]:
    """Serialise freshly computed rows exactly as the audit scripts write them.

    Round-tripping through DictWriter/DictReader is what makes the comparison
    apples-to-apples: the committed CSV holds DictWriter's rendering of these
    same values, so `None` becomes `''` and `True` becomes `'True'` on both
    sides rather than only one.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return list(csv.DictReader(buffer))


def corpus_pdfs(corpus: Path) -> list[Path]:
    return sorted(corpus.rglob("*.pdf"))


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def relative_key(row: dict[str, str]) -> str:
    """Corpus-relative path for an ADB audit row, which stores folder + name.

    The ADB audit writes its folder with the OS-native separator, so the
    committed CSV carries backslashes. Normalise before matching anything
    against the corpus, which is enumerated as POSIX paths.
    """
    folder = row.get("folder", ".").replace("\\", "/")
    return row["statement"] if folder in {"", "."} else f"{folder}/{row['statement']}"


def compare_rows(
    fresh: list[dict[str, str]],
    committed: list[dict[str, str]],
    key: str,
    label: str,
    limit: int = 25,
) -> tuple[bool, list[str]]:
    committed_by_key = {row[key]: row for row in committed}
    fresh_by_key = {row[key]: row for row in fresh}
    details: list[str] = []

    missing = sorted(set(committed_by_key) - set(fresh_by_key))
    added = sorted(set(fresh_by_key) - set(committed_by_key))
    for name in missing:
        details.append(f"{label}: {name} is in the committed audit but was not re-audited")
    for name in added:
        details.append(f"{label}: {name} was audited but is absent from the committed audit")

    drifted = 0
    for name in sorted(set(fresh_by_key) & set(committed_by_key)):
        want, got = committed_by_key[name], fresh_by_key[name]
        for column in want:
            if want[column] != got.get(column, ""):
                drifted += 1
                if len(details) < limit:
                    details.append(
                        f"{label}: {name} [{column}] expected {want[column]!r}, got {got.get(column, '')!r}"
                    )
    if drifted > limit:
        details.append(f"{label}: ... and {drifted - limit} further field differences")
    return (not missing and not added and drifted == 0), details


def check_inventory(result: Result, pdfs: list[Path], corpus: Path,
                    balance_csv: list[dict[str, str]], adb_csv: list[dict[str, str]]) -> None:
    on_disk = [path.relative_to(corpus).as_posix() for path in pdfs]
    details: list[str] = []
    ok = True

    if len(on_disk) != EXPECTED_PDF_COUNT:
        ok = False
        details.append(f"corpus holds {len(on_disk)} PDFs, expected {EXPECTED_PDF_COUNT}")

    for label, audited in (("balance audit", [row["path"] for row in balance_csv]),
                           ("ADB audit", [relative_key(row) for row in adb_csv])):
        if len(audited) != EXPECTED_PDF_COUNT:
            ok = False
            details.append(f"{label} holds {len(audited)} rows, expected {EXPECTED_PDF_COUNT}")
        for name in sorted(set(on_disk) - set(audited)):
            ok = False
            details.append(f"{label}: {name} is in the corpus but has no audited row")
        for name in sorted(set(audited) - set(on_disk)):
            ok = False
            details.append(f"{label}: {name} is audited but missing from the corpus")

    result.add(
        "inventory",
        ok,
        f"{len(on_disk)} corpus PDFs, all present in both committed audits",
        details,
    )


def check_source_integrity(result: Result, pdfs: list[Path], corpus: Path,
                           balance_csv: list[dict[str, str]]) -> None:
    pinned = {row["path"]: row["sha256"] for row in balance_csv}
    details: list[str] = []
    verified = 0
    for path in pdfs:
        rel = path.relative_to(corpus).as_posix()
        expected = pinned.get(rel)
        if expected is None:
            details.append(f"{rel} has no pinned SHA-256")
            continue
        actual = sha256_upper(path.read_bytes())
        if actual != expected:
            details.append(f"{rel} SHA-256 drifted: pinned {expected}, on disk {actual}")
        else:
            verified += 1
    result.add(
        "source_integrity",
        not details,
        f"{verified}/{len(pdfs)} source PDFs match their pinned SHA-256",
        details,
    )


def check_ocr_coverage(result: Result, source_types: dict[str, str],
                       corpus: Path, cache: Path) -> None:
    scanned = sorted(name for name, kind in source_types.items() if kind.startswith("scanned"))
    native = sorted(name for name, kind in source_types.items() if not kind.startswith("scanned"))
    entries = manifest_entries(cache)
    on_disk = {path.relative_to(corpus).as_posix() for path in corpus_pdfs(corpus)}
    orphans = sorted(entry["path"] for entry in entries.values() if entry["path"] not in on_disk)

    details = [f"served from committed OCR artifact: {name}" for name in scanned]
    details += [f"cache holds an artifact for a document not in the corpus: {name}" for name in orphans]
    result.add(
        "ocr_coverage",
        not orphans,
        f"{len(native)} native-text + {len(scanned)} committed-OCR = "
        f"{len(source_types)} statements resolved offline; no live OCR, no model calls",
        details,
    )


def check_exclusions(result: Result) -> None:
    details = [f"{name}: {reason}" for name, reason in sorted(KNOWN_EXCLUSIONS.items())]
    result.add(
        "exclusions",
        True,
        f"{len(KNOWN_EXCLUSIONS)} named exclusions",
        details,
    )


def check_outcomes(result: Result, label: str, rows: list[dict[str, str]],
                   pass_status: str, withheld_status: str) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    withheld = {row["statement"] for row in rows if row["status"] == withheld_status}
    details: list[str] = []
    ok = True

    if counts.get(pass_status, 0) != EXPECTED_PASS:
        ok = False
        details.append(f"{counts.get(pass_status, 0)} {pass_status}, expected {EXPECTED_PASS}")
    if counts.get(withheld_status, 0) != EXPECTED_WITHHELD:
        ok = False
        details.append(
            f"{counts.get(withheld_status, 0)} {withheld_status}, expected {EXPECTED_WITHHELD}"
        )
    for status, count in sorted(counts.items()):
        if status not in {pass_status, withheld_status}:
            ok = False
            details.append(f"unexpected status {status} on {count} statement(s)")
    if withheld != WITHHELD_STATEMENTS:
        ok = False
        for name in sorted(withheld - WITHHELD_STATEMENTS):
            details.append(f"{name} is newly withheld; a passing statement must not become withheld")
        for name in sorted(WITHHELD_STATEMENTS - withheld):
            details.append(
                f"{name} is a proven source contradiction and must stay withheld, not reinterpreted as passing"
            )

    result.add(
        f"{label}_outcomes",
        ok,
        f"{label}: {EXPECTED_PASS} pass, {EXPECTED_WITHHELD} withheld, same three statements",
        details,
    )


def check_oracle_independence(result: Result) -> None:
    details: list[str] = []
    for name in INDEPENDENT_SOURCES:
        source = (ROOT / name).read_text(encoding="utf-8")
        for module in FORBIDDEN_MODULES:
            for statement in (f"from analysis.{module}", f"import analysis.{module}"):
                if statement in source:
                    details.append(f"{name} contains {statement!r}")
    result.add(
        "oracle_independence",
        not details,
        f"{len(INDEPENDENT_SOURCES)} audit modules import no production financial mathematics",
        details,
    )


def run_gate(corpus: Path, cache: Path) -> Result:
    result = Result()
    started = time.perf_counter()

    pdfs = corpus_pdfs(corpus)
    balance_csv = read_csv(BALANCE_CSV)
    adb_csv = read_csv(ADB_CSV)

    check_inventory(result, pdfs, corpus, balance_csv, adb_csv)
    check_source_integrity(result, pdfs, corpus, balance_csv)

    # Balance oracle: opening/ending/highest/lowest across backend, API,
    # dashboard binding, CSV, XLSX, and the package surfaces.
    balance_rows: list[dict[str, Any]] = []
    jobs: list[Any] = []
    expected_by_id: dict[str, Any] = {}
    source_types: dict[str, str] = {}
    for path in pdfs:
        row, job, expected = balance_forensic_audit.audit_source(path, corpus, ocr_cache=cache)
        balance_rows.append(row)
        jobs.append(job)
        expected_by_id[job.id] = expected
        source_types[path.relative_to(corpus).as_posix()] = row["source_type"]
    balance_forensic_audit.apply_package_results(balance_rows, jobs, expected_by_id)
    fresh_balance = as_csv_rows(balance_rows, balance_forensic_audit.FIELDS)
    ok, details = compare_rows(fresh_balance, balance_csv, "path", "balance")
    result.add(
        "balance_audit",
        ok,
        f"{len(fresh_balance)} statements reproduce every audited balance field "
        f"across backend, API, dashboard, CSV, XLSX, and package surfaces",
        details,
    )

    # ADB oracle: independent daily-ledger reconstruction vs backend, API, and
    # dashboard-package ADB.
    adb_rows: list[dict[str, Any]] = []
    for path in pdfs:
        markdown = adb_forensic_audit.source_markdown(path, ocr_cache=cache)
        adb_rows.append(adb_forensic_audit.audit_one(path, corpus, markdown))
    fresh_adb = as_csv_rows(adb_rows, adb_forensic_audit.FIELDS)
    # Key both sides by corpus-relative path so identically named statements in
    # different folders can never be compared against each other. `folder` stays
    # in the compared columns, so a separator change still surfaces as drift.
    committed_adb = [dict(row, statement=relative_key(row)) for row in adb_csv]
    keyed_adb = [dict(row, statement=relative_key(row)) for row in fresh_adb]
    ok, details = compare_rows(keyed_adb, committed_adb, "statement", "adb")
    result.add(
        "adb_audit",
        ok,
        f"{len(fresh_adb)} statements reproduce every audited ADB field across "
        f"backend, API, and dashboard-package surfaces",
        details,
    )

    check_outcomes(result, "balance", fresh_balance, "PASS", "WITHHELD_SOURCE_CONTRADICTION")
    check_outcomes(result, "adb", fresh_adb, "PASS", "WITHHELD")
    check_ocr_coverage(result, source_types, corpus, cache)
    check_exclusions(result)
    check_oracle_independence(result)

    result.stats = {
        "corpus_pdfs": len(pdfs),
        "native_text_statements": sum(
            1 for kind in source_types.values() if not kind.startswith("scanned")
        ),
        "committed_ocr_statements": sum(
            1 for kind in source_types.values() if kind.startswith("scanned")
        ),
        "pass": EXPECTED_PASS,
        "withheld": EXPECTED_WITHHELD,
        "exclusions": len(KNOWN_EXCLUSIONS),
        "runtime_seconds": round(time.perf_counter() - started, 1),
    }
    return result


def render(result: Result) -> str:
    lines = ["Corpus gate", ""]
    for check in result.checks:
        lines.append(f"[{'PASS' if check.ok else 'FAIL'}] {check.name}: {check.summary}")
        for detail in check.details:
            lines.append(f"         {detail}")
    lines += ["", f"Coverage: {result.stats['corpus_pdfs']} PDFs "
                  f"({result.stats['native_text_statements']} native text, "
                  f"{result.stats['committed_ocr_statements']} committed OCR), "
                  f"{result.stats['exclusions']} exclusions",
              f"Outcomes: {result.stats['pass']} PASS / {result.stats['withheld']} WITHHELD",
              f"Runtime:  {result.stats['runtime_seconds']}s",
              "",
              "RESULT: " + ("GREEN" if result.ok else "RED")]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic offline corpus gate.")
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--ocr-cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--json", help="Write a machine-readable report here.")
    args = parser.parse_args()

    result = run_gate(Path(args.corpus), Path(args.ocr_cache))
    print(render(result))
    if args.json:
        payload = {
            "ok": result.ok,
            "stats": result.stats,
            "checks": [
                {"name": c.name, "ok": c.ok, "summary": c.summary, "details": c.details}
                for c in result.checks
            ],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()

"""Deterministic offline corpus gate for the validated statement corpus.

Runs both independent forensic oracles over every corpus PDF and fails red on
any drift from the committed audits. Nothing here calculates a financial value
of its own: it re-runs `adb_forensic_audit` and `balance_forensic_audit`
unchanged and compares their output, field by field, with
`docs/adb-audit-results.csv` and `docs/balance-metrics-audit-results.csv`.

    python corpus_gate.py                     # the gate
    python corpus_gate.py --json report.json  # plus a machine-readable report
    python corpus_gate.py --corpus <path>     # same gate against another root
    pytest -m corpus                          # same gate, through pytest

Scope: the **pinned manifest**, not the directory. The gate enumerates the 109
corpus-relative paths recorded in the committed audit CSVs and audits exactly
those. The corpus root is shared with untracked, sensitive discovery material
(`.gitignore`: `Bank Statements/**`), so "every PDF under the root is pinned" is
no longer a property the tree can have. What replaces it is stricter about the
validated set and honest about the rest — see `check_foreign_files`.

Guarantees:

- Offline. No OCR endpoint, no Gemini, no network, no Tesseract binary. The 6
  image-only statements are served from committed OCR artifacts keyed by the
  SHA-256 of their source PDF (see `corpus_artifacts`).
- Complete over the pinned manifest. Every pinned path must exist on disk, must
  hash-match its pin, and must carry a row in *both* committed audits; the two
  audits must pin the same 109 paths. A statement is never skipped silently: a
  missing file, a missing artifact, or an unreadable document is a failure, and
  any deliberate exclusion is named and counted in the report.
- Explicit about foreign files. PDFs under the root that are not in the manifest
  are counted and reported ("N non-corpus PDFs present — ignored"). Never
  silently, and never a failure: they are not the validated corpus and the gate
  makes no claim about them.
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
    """Every PDF on disk under the root — pinned and foreign alike.

    Used only for foreign-file accounting. The audited set comes from
    `manifest_paths`, never from this.
    """
    return sorted(corpus.rglob("*.pdf"))


def manifest_paths(balance_csv: list[dict[str, str]]) -> list[str]:
    """The pinned manifest: corpus-relative POSIX paths of the audited set.

    The balance audit is the enumerator because it stores the whole relative
    path in one column. `check_inventory` proves the ADB audit pins exactly the
    same paths, so neither audit can drift into being the sole authority.
    """
    return sorted({row["path"] for row in balance_csv})


def manifest_pdfs(corpus: Path, manifest: list[str]) -> list[Path]:
    """Resolve the pinned manifest against a corpus root, in manifest order."""
    return [corpus / Path(rel) for rel in manifest]


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


def check_inventory(result: Result, manifest: list[str], corpus: Path,
                    balance_csv: list[dict[str, str]], adb_csv: list[dict[str, str]]) -> None:
    """The pinned manifest is complete, agreed by both audits, and on disk."""
    details: list[str] = []
    ok = True

    if len(manifest) != EXPECTED_PDF_COUNT:
        ok = False
        details.append(
            f"pinned manifest holds {len(manifest)} paths, expected {EXPECTED_PDF_COUNT}"
        )

    for label, audited in (("balance audit", [row["path"] for row in balance_csv]),
                           ("ADB audit", [relative_key(row) for row in adb_csv])):
        if len(audited) != EXPECTED_PDF_COUNT:
            ok = False
            details.append(f"{label} holds {len(audited)} rows, expected {EXPECTED_PDF_COUNT}")
        if len(set(audited)) != len(audited):
            ok = False
            details.append(f"{label} holds duplicate paths")
        for name in sorted(set(manifest) - set(audited)):
            ok = False
            details.append(f"{label}: {name} is pinned but has no audited row")
        for name in sorted(set(audited) - set(manifest)):
            ok = False
            details.append(f"{label}: {name} is audited but absent from the pinned manifest")

    for rel in manifest:
        if not (corpus / Path(rel)).is_file():
            ok = False
            details.append(f"{rel} is pinned but missing from the corpus root")

    result.add(
        "inventory",
        ok,
        f"{len(manifest)} pinned corpus PDFs, all on disk and audited by both oracles",
        details,
    )


def check_foreign_files(result: Result, corpus: Path, manifest: list[str]) -> int:
    """Count PDFs under the root that are not pinned. Reported, never fatal.

    The corpus root doubles as the landing zone for untracked discovery
    material. Those documents are not the validated corpus, carry no audit row,
    and the gate makes no claim about them — but it must never pretend they are
    not there. Names are deliberately withheld: they are sensitive source data.
    """
    pinned = set(manifest)
    foreign = sorted(
        rel for rel in (path.relative_to(corpus).as_posix() for path in corpus_pdfs(corpus))
        if rel not in pinned
    )
    details: list[str] = []
    if foreign:
        folders = {rel.split("/")[0] if "/" in rel else "." for rel in foreign}
        summary = f"{len(foreign)} non-corpus PDFs present — ignored (discovery archive)"
        details = [
            f"spread across {len(folders)} top-level folder(s) under the corpus root",
            "names withheld: unpinned documents under this root are sensitive source data",
            "these are not audited, not parsed, and not part of any gate claim",
        ]
    else:
        summary = "no non-corpus PDFs under the corpus root"
    result.add("foreign_files", True, summary, details)
    return len(foreign)


def check_source_integrity(result: Result, corpus: Path,
                           balance_csv: list[dict[str, str]]) -> None:
    """Every pinned PDF exists and still hashes to its pinned SHA-256."""
    pinned = {row["path"]: row["sha256"] for row in balance_csv}
    details: list[str] = []
    verified = 0
    for rel, expected in sorted(pinned.items()):
        path = corpus / Path(rel)
        if not path.is_file():
            details.append(f"{rel} is pinned but missing from the corpus root")
            continue
        actual = sha256_upper(path.read_bytes())
        if actual != expected:
            details.append(f"{rel} SHA-256 drifted: pinned {expected}, on disk {actual}")
        else:
            verified += 1
    result.add(
        "source_integrity",
        not details,
        f"{verified}/{len(pinned)} pinned source PDFs match their pinned SHA-256",
        details,
    )


def check_ocr_coverage(result: Result, source_types: dict[str, str],
                       manifest: list[str], cache: Path) -> None:
    scanned = sorted(name for name, kind in source_types.items() if kind.startswith("scanned"))
    native = sorted(name for name, kind in source_types.items() if not kind.startswith("scanned"))
    entries = manifest_entries(cache)
    pinned = set(manifest)
    orphans = sorted(entry["path"] for entry in entries.values() if entry["path"] not in pinned)

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


def _stats(source_types: dict[str, str], pinned: int, foreign: int, started: float) -> dict[str, Any]:
    return {
        "corpus_pdfs": pinned,
        "foreign_pdfs": foreign,
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


def run_gate(corpus: Path, cache: Path) -> Result:
    result = Result()
    started = time.perf_counter()

    balance_csv = read_csv(BALANCE_CSV)
    adb_csv = read_csv(ADB_CSV)
    manifest = manifest_paths(balance_csv)
    pdfs = manifest_pdfs(corpus, manifest)

    check_inventory(result, manifest, corpus, balance_csv, adb_csv)
    foreign = check_foreign_files(result, corpus, manifest)
    check_source_integrity(result, corpus, balance_csv)

    absent = [path for path in pdfs if not path.is_file()]
    if absent:
        # Both oracles would raise on the first unreadable file. Stop here so
        # the run still renders a red report naming what is gone.
        result.add(
            "audits",
            False,
            f"not run: {len(absent)} pinned statement(s) missing from {corpus}",
            [f"{path.relative_to(corpus).as_posix()} is pinned but missing" for path in absent[:25]],
        )
        result.stats = _stats({}, len(manifest), foreign, started)
        return result

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
    check_ocr_coverage(result, source_types, manifest, cache)
    check_exclusions(result)
    check_oracle_independence(result)

    result.stats = _stats(source_types, len(pdfs), foreign, started)
    return result


def render(result: Result) -> str:
    lines = ["Corpus gate", ""]
    for check in result.checks:
        lines.append(f"[{'PASS' if check.ok else 'FAIL'}] {check.name}: {check.summary}")
        for detail in check.details:
            lines.append(f"         {detail}")
    lines += ["", f"Coverage: {result.stats['corpus_pdfs']} pinned PDFs "
                  f"({result.stats['native_text_statements']} native text, "
                  f"{result.stats['committed_ocr_statements']} committed OCR), "
                  f"{result.stats['exclusions']} exclusions",
              f"Ignored:  {result.stats['foreign_pdfs']} non-corpus PDFs under the corpus root",
              f"Outcomes: {result.stats['pass']} PASS / {result.stats['withheld']} WITHHELD",
              f"Runtime:  {result.stats['runtime_seconds']}s",
              "",
              "RESULT: " + ("GREEN" if result.ok else "RED")]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic offline corpus gate.")
    parser.add_argument(
        "--corpus",
        "--corpus-root",
        dest="corpus",
        default=str(CORPUS),
        help="Corpus root the pinned manifest is resolved against "
             "(default: this checkout's 'Bank Statements'). Lets one checkout's "
             "gate code audit another checkout's corpus root.",
    )
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

"""tools/classify_census.py — the read-only classifier census over a run of
record (Phase 2.2 cell C, `P22-CLASSIFY.md` §8; umbrella D2, cases 7–8).

    python -m tools.classify_census --run <run dir> --data-dir <cold cache> --out <private csv>
        [--archive-root "Bank Statements"] [--census <per_sha.csv>] [--clusters <clusters.json>] [--limit N]

Walks the run's `rows.csv` (one document per content sha, the first row in
run order), loads each document's cached extraction from the run's OWN
artifact partition (`telemetry/run_of_record.py`, OQ10 — never `rows[0]`,
never a preference order), builds the preflight FACTS from the row and the
file's first bytes, classifies with `layout.classify_document`, and:

* writes a PRIVATE per-sha CSV to `--out` (sha, sha16, outcome, kind,
  sub_kind, modality, tier, language, account_kind, findings, signals, the
  input mode) — the path must be git-ignored, or the tool refuses;
* prints AGGREGATES only: kind × modality × tier over the archive and over
  the unresolved set, the disjoint sum asserted (exit 2 if it does not
  hold), validated documents not classified `STATEMENT_COMPLETE` listed by
  sha16 with their kind (a named finding, never a value), and the AGREEMENT
  counts with the batch-9 census's NOT-STATEMENT and portal-export lists
  (evidence for an adjudicator, never truth — R3).

Which input the classifier sees
-------------------------------
`native_evidence` (cell K's schema-3 field) when the cached record carries
it, else `evidence` (a Paddle read), else the cached page TEXT in the
classifier's DECLARED DEGRADED mode. The report says which mode each
document was read in, per kind. Nothing here calls the analysis; nothing
here writes anywhere but `--out`; the archive and the cache are opened
read-only.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from evidence.canonical import EvidenceError, from_json
from layout import CLASSIFIER_VERSION, KINDS, DocumentProfileFacts, classify_document
from layout.refusals import MODALITIES, TIERS

LADDER = ("failed", "deferred", "withheld", "review", "validated")
NOT_STATEMENT_KINDS = ("NOT_A_STATEMENT", "FILE_INVALID", "ACTIVITY_EXPORT")
DEFAULT_CENSUS = Path("docs/moneythumb-replacement/census_batch9/per_sha.csv")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")
CSV_FIELDS = ("content_sha256", "sha16", "outcome_class", "source_path", "classification", "input_mode", "kind",
              "sub_kind", "modality", "tier", "language", "account_kind", "findings", "signals", "pages_read")


def _bool(value: str) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes")


def _refuse_tracked_out(out: Path) -> None:
    """The per-sha CSV names documents; it may live only under a git-ignored path."""
    try:
        result = subprocess.run(["git", "check-ignore", "-q", str(out)], capture_output=True, text=True)
    except OSError as exc:
        raise SystemExit(f"refusing --out {out}: git could not be asked whether the path is ignored ({type(exc).__name__})")
    ignored = result.returncode == 0
    if not ignored:
        raise SystemExit(f"refusing --out {out}: the path is not git-ignored (private per-sha output only)")


def _load_rows(run: Path) -> tuple[dict[str, dict], dict[str, str]]:
    """First row per sha (run order) and the best outcome across a sha's rows."""
    first: dict[str, dict] = {}
    best: dict[str, str] = {}
    with (run / "rows.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row.get("content_sha256") or "").strip().upper()
            if not sha:
                continue
            first.setdefault(sha, row)
            outcome = (row.get("outcome_class") or "").strip()
            rank = LADDER.index(outcome) if outcome in LADDER else -1
            if sha not in best or rank > (LADDER.index(best[sha]) if best[sha] in LADDER else -1):
                best[sha] = outcome
    return first, best


def _magic(archive_root: Path | None, relative_path: str) -> str | None:
    if archive_root is None or not relative_path:
        return None
    path = archive_root / relative_path
    try:
        with path.open("rb") as handle:
            head = handle.read(4)
    except OSError:
        return None
    return head.hex().upper() if len(head) == 4 else None


class _Cache:
    """Read-only artifact resolution through the run's own partitions."""

    def __init__(self, data_dir: Path, run: Path):
        from telemetry.run_of_record import partitions_for_run

        self.root = data_dir / "artifacts"
        self.conn = sqlite3.connect(f"file:{(data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
        try:
            self.partitions = partitions_for_run(run, conn=self.conn)
        except BaseException:
            self.conn.close()
            raise

    def close(self) -> None:
        self.conn.close()

    def document(self, sha: str, row: dict) -> dict | None:
        from telemetry.run_of_record import ocr_partition_for_row, select_artifact

        key = ocr_partition_for_row(row, self.partitions)
        path = select_artifact(self.conn, "ocr", sha, key)
        if path is None:
            return None
        try:
            payload = json.loads((self.root / path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        document = (payload.get("artifact") or {}).get("document")
        return document if isinstance(document, dict) else None


def _inputs(document: dict | None) -> tuple[str, object, tuple[str, ...] | None]:
    """(input_mode, evidence, page_texts): native evidence first, then any
    extractor evidence, then the page text (degraded); `none` when the cache
    holds nothing for the document."""
    if document is None:
        return "none", None, None
    for field, mode in (("native_evidence", "native_evidence"), ("evidence", "evidence")):
        payload = document.get(field)
        if isinstance(payload, dict):
            try:
                return mode, from_json(payload), None
            except EvidenceError:
                continue
    pages = tuple(str(p) for p in (document.get("pages") or ()))
    return ("text" if pages else "none"), None, (pages if pages else None)


def _native_pdf_inputs(archive_root: Path | None, row: dict) -> tuple[str, object, tuple[str, ...] | None] | None:
    """`--evidence-source native-pdf`: word boxes read from the archive PDF
    through the ONE native reader the platform has today
    (`analysis/structurer/geometry.py::native_evidence_from_pdf`, Phase 2.1;
    cell K re-homes it under `evidence/native.py`). A tool-side import of
    `analysis` — the classifier itself never imports it. Only rows the run
    read natively (`source_path == native`); None otherwise, so the caller
    falls back to the cache."""
    if archive_root is None or (row.get("source_path") or "").strip() != "native":
        return None
    path = archive_root / (row.get("relative_path") or "")
    try:
        pdf_bytes = path.read_bytes()
    except OSError:
        return None
    from analysis.structurer.geometry import native_evidence_from_pdf

    try:
        evidence = native_evidence_from_pdf(pdf_bytes)
    except Exception:  # a malformed page is a finding for the reader's owner, not for this census
        return None
    if evidence is None:
        return None
    return "native_pdf", evidence, None


def _facts(row: dict, pages: tuple[str, ...] | None, magic: str | None) -> DocumentProfileFacts:
    classification = (row.get("classification") or "unknown").strip()
    if classification not in ("digital", "scanned", "mixed", "unknown"):
        classification = "unknown"
    try:
        page_count = int(row.get("page_count") or 0)
    except ValueError:
        page_count = 0
    return DocumentProfileFacts(
        valid_pdf=_bool(row.get("valid_pdf", "")), encrypted=_bool(row.get("encrypted", "")),
        page_count=page_count, classification=classification,
        page_text_chars=tuple(len(p.strip()) for p in (pages or ())), magic=magic,
    )


def _table(title: str, counter: collections.Counter, keys: list[tuple], header: tuple[str, ...]) -> None:
    print(f"\n## {title}")
    print("| " + " | ".join(header) + " | n |")
    print("|" + "---|" * (len(header) + 1))
    for key in keys:
        if counter.get(key):
            print("| " + " | ".join(str(k) for k in key) + f" | {counter[key]} |")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True, help="a discovery run directory (rows.csv + provenance)")
    parser.add_argument("--data-dir", type=Path, required=True, help="the run's cold cache (opened read-only)")
    parser.add_argument("--out", type=Path, required=True, help="PRIVATE per-sha CSV (must be git-ignored)")
    parser.add_argument("--archive-root", type=Path, default=None,
                        help="the archive root for the file's first bytes (magic); omitted = magic unknown")
    parser.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    parser.add_argument("--limit", type=int, default=None, help="classify only the first N shas (a smoke run)")
    parser.add_argument("--evidence-source", choices=("cache", "native-pdf"), default="cache",
                        help="cache (the card's measurement: cached evidence, else cached page text in degraded "
                             "mode) or native-pdf (word boxes re-read from the archive PDF for native rows; "
                             "cache otherwise)")
    args = parser.parse_args(argv)

    _refuse_tracked_out(args.out)
    archive_root = args.archive_root if (args.archive_root and args.archive_root.is_dir()) else None
    first, best = _load_rows(args.run)
    shas = list(first)
    if args.limit:
        shas = shas[: args.limit]

    census_kind: dict[str, str] = {}
    if args.census.is_file():
        with args.census.open(encoding="utf-8", newline="") as handle:
            for record in csv.DictReader(handle):
                census_kind[record["sha"].upper()] = record.get("b8_kind") or ""
    not_statement_16: set[str] = set()
    if args.clusters.is_file():
        clusters = json.loads(args.clusters.read_text(encoding="utf-8"))
        not_statement_16 = {s.upper() for s in clusters.get("groups", {}).get("NOT-STATEMENT", {}).get("shas16", [])}

    cache = _Cache(args.data_dir, args.run)
    results: dict[str, dict] = {}
    try:
        for index, sha in enumerate(shas, 1):
            row = first[sha]
            document = cache.document(sha, row)
            cached_mode, cached_evidence, cached_texts = _inputs(document)
            native = _native_pdf_inputs(archive_root, row) if args.evidence_source == "native-pdf" else None
            mode, evidence, page_texts = native if native is not None else (cached_mode, cached_evidence, cached_texts)
            facts = _facts(row, cached_texts if cached_texts else tuple(), _magic(archive_root, row.get("relative_path", "")))
            verdict = classify_document(evidence=evidence, page_texts=page_texts, profile=facts)
            results[sha] = {
                "content_sha256": sha, "sha16": sha[:16], "outcome_class": best.get(sha, ""),
                "source_path": row.get("source_path", ""), "classification": row.get("classification", ""),
                "input_mode": mode, "kind": verdict.kind, "sub_kind": verdict.sub_kind or "",
                "modality": verdict.modality, "tier": verdict.tier, "language": verdict.language,
                "account_kind": verdict.account_kind,
                "findings": ";".join(f.code for f in verdict.completeness),
                "signals": ";".join(sorted({ref.signal for ref in verdict.evidence})),
                "pages_read": len(evidence.pages) if evidence is not None else len(page_texts or ()),
            }
            if index % 500 == 0:
                print(f"... {index} / {len(shas)}", file=sys.stderr)
    finally:
        cache.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for sha in shas:
            writer.writerow(results[sha])

    # ----------------------------------------------------------------- aggregates
    unresolved = [sha for sha in shas if best.get(sha) != "validated"]
    validated = [sha for sha in shas if best.get(sha) == "validated"]
    print(f"# classify_census — run {args.run.name}; evidence source {args.evidence_source}; "
          f"shas {len(shas)}; validated {len(validated)}; unresolved {len(unresolved)}")
    print(f"classifier version {CLASSIFIER_VERSION}; "
          f"input modes: {dict(collections.Counter(r['input_mode'] for r in results.values()))}")

    kind_keys = [(k,) for k in KINDS]
    for title, population in (("archive", shas), ("unresolved", unresolved)):
        counter = collections.Counter((results[s]["kind"],) for s in population)
        _table(f"kind — {title} ({len(population)})", counter, kind_keys, ("kind",))
        total = sum(counter.values())
        if total != len(population):
            print(f"DISJOINT SUM FAILED for {title}: {total} != {len(population)}")
            return 2
        print(f"disjoint sum over {title}: {total} == {len(population)}  OK")
        kmt = collections.Counter((results[s]["kind"], results[s]["modality"], results[s]["tier"]) for s in population)
        keys = [(k, m, t) for k in KINDS for m in MODALITIES for t in TIERS]
        _table(f"kind x modality x tier — {title}", kmt, keys, ("kind", "modality", "tier"))
        kmode = collections.Counter((results[s]["kind"], results[s]["input_mode"]) for s in population)
        _table(f"kind x input mode — {title}", kmode, sorted(kmode), ("kind", "input_mode"))

    sub = collections.Counter((results[s]["sub_kind"], results[s]["tier"]) for s in shas if results[s]["kind"] == "NOT_A_STATEMENT")
    _table("NOT_A_STATEMENT sub_kind x tier — archive", sub, sorted(sub), ("sub_kind", "tier"))
    findings = collections.Counter()
    for s in shas:
        for code in filter(None, results[s]["findings"].split(";")):
            findings[(code,)] += 1
    _table("STATEMENT_PARTIAL findings (a document may carry several) — archive", findings, sorted(findings), ("finding",))
    lang = collections.Counter((results[s]["language"],) for s in shas)
    _table("language — archive", lang, sorted(lang), ("language",))
    acct = collections.Counter((results[s]["account_kind"],) for s in shas)
    _table("account_kind — archive", acct, sorted(acct), ("account_kind",))

    exceptions = [s for s in validated if results[s]["kind"] != "STATEMENT_COMPLETE"]
    print(f"\n## validated documents not classified STATEMENT_COMPLETE: {len(exceptions)} of {len(validated)} (a named finding)")
    ex_kinds = collections.Counter((results[s]["kind"], results[s]["sub_kind"] or "-", results[s]["findings"] or "-") for s in exceptions)
    _table("validated exceptions by kind / sub_kind / findings", ex_kinds, sorted(ex_kinds), ("kind", "sub_kind", "findings"))
    for s in exceptions:
        r = results[s]
        print(f"  {r['sha16']}  {r['kind']}  {r['sub_kind'] or '-'}  {r['findings'] or '-'}  tier={r['tier']}  mode={r['input_mode']}")

    print("\n## agreement with the batch-9 census lists (evidence for an adjudicator, never truth — R3)")
    ns = [s for s in shas if s[:16] in not_statement_16]
    portal = [s for s in shas if census_kind.get(s) == "portal_export"]
    bare = [s for s in ns if census_kind.get(s) == "not_statement"]
    for title, population, agree in (
        ("census NOT-STATEMENT (117: 104 bare + 13 portal)", ns, NOT_STATEMENT_KINDS),
        ("census not_statement (bare list)", bare, NOT_STATEMENT_KINDS),
        ("census portal_export", portal, ("ACTIVITY_EXPORT",)),
    ):
        counter = collections.Counter((results[s]["kind"], results[s]["sub_kind"] or "-") for s in population)
        _table(f"{title}: {len(population)} present in this run", counter, sorted(counter), ("kind", "sub_kind"))
        agreeing = sum(1 for s in population if results[s]["kind"] in agree)
        print(f"agreement (classifier kind in {agree}): {agreeing} / {len(population)}")
    print(f"\nprivate per-sha CSV written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Measure the W3-3c structurer against the platform's own gates.

Graduated from the W3-3a spike, whose design came from the
archived prototype's `eval_unknown_banks.py` (f14282e): **one question per
document — did the generic path reach a value the platform would publish, or
did it fail closed, and exactly where did it stop?**

Two strata, and they answer different questions:

* `--corpus` — the pinned 109. Every one is claimed by a parser and audited
  field by field, so this stratum measures ACCURACY, including the only number
  that can veto the subsystem: **validated-and-wrong**, which must be zero.
* `--archive` — documents no parser claimed, sampled deterministically from the
  discovery rows by cluster. This measures REACH, where the platform has none.

Aggregate counts only. No document content, filename or amount from any real
statement is printed or written. Archive documents are read in place,
read-only.

    python -m tools.measure_structurer --corpus [--flat]
    python -m tools.measure_structurer --archive --per-cluster 25 \
        --reports <main>/discovery_reports --archive-root "<main>/Bank Statements"
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.metrics import compute_metrics  # noqa: E402
from analysis.pipeline import normalize_statement  # noqa: E402
from analysis.reconcile import reconcile  # noqa: E402
from analysis.structurer import geometry_from_pdf, structure_document  # noqa: E402
from analysis.transaction_classifier import classify_statement_transactions  # noqa: E402
from bank_statements import ENV_VAR, bank_statements_dir_or_exit  # noqa: E402

ARTIFACTS = Path("tests/corpus_cache")

CLUSTERS: dict[str, tuple[str, ...]] = {
    "known_bank_variants": ("BMO", "Chase", "TD Bank", "CIBC", "Bank of America", "RBC"),
    "unidentified": ("Unidentified",),
    "low_volume_unknown": ("Huntington", "Mercury", "Fifth Third", "Citibank", "Lead", "Zions", "Brex"),
}


def read_markdown(path: Path, *, allow_local_ocr: bool) -> str | None:
    from corpus_artifacts import cached_markdown
    from ocr.inspect import inspect_pdf
    from ocr.pipeline import parse_statement

    raw = path.read_bytes()
    profile = inspect_pdf(raw)
    if not profile.valid_pdf or profile.encrypted:
        return None
    document = parse_statement(
        raw, source_file=path.name, profile=profile,
        force_ocr=False, allow_local_ocr=allow_local_ocr, allow_visual_ocr=False,
    )
    if document is not None:
        return document.to_markdown()
    return cached_markdown(raw, ARTIFACTS)


def gate(markdown: str, statement):
    """Exactly the checks the pipeline applies after extraction."""
    statement = normalize_statement(statement)
    recon = reconcile(statement)
    classifications = classify_statement_transactions(statement)
    metrics = compute_metrics(
        statement,
        trust_stated_summary=recon.summary_ok,
        trust_running_balances=recon.ok,
        source_markdown=markdown,
        classifications=classifications,
    )
    return statement, recon, metrics


def disposition(outcome, recon, metrics) -> str:
    if outcome.statement is None:
        return f"refused_{outcome.reason}"
    if metrics.average_daily_balance is None:
        return "withheld_adb"
    if not recon.ok:
        return "review_recon"
    return "validated"


def field_agreement(structured, reference) -> dict[str, bool]:
    def close(a, b) -> bool:
        if a is None or b is None:
            return a is None and b is None
        return abs(a - b) <= 0.02

    return {
        "beginning_balance": close(structured.beginning_balance, reference.beginning_balance),
        "ending_balance": close(structured.ending_balance, reference.ending_balance),
        "transaction_count": len(structured.transactions) == len(reference.transactions),
        "transaction_sum": close(
            round(sum(t.amount for t in structured.transactions), 2),
            round(sum(t.amount for t in reference.transactions), 2),
        ),
    }


def run_one(path: Path, *, scanned: bool, flat: bool):
    markdown = read_markdown(path, allow_local_ocr=scanned)
    if markdown is None:
        return None, None, None, None
    geometry = None if flat else geometry_from_pdf(path.read_bytes())
    outcome = structure_document(markdown, geometry=geometry)
    recon = metrics = None
    if outcome.statement is not None:
        _, recon, metrics = gate(markdown, outcome.statement)
    return markdown, outcome, recon, metrics


def pinned_paths() -> list[Path]:
    from corpus_gate import BALANCE_CSV, manifest_paths, read_csv

    root = bank_statements_dir_or_exit()
    return [root / relative for relative in manifest_paths(read_csv(BALANCE_CSV))]


def run_corpus(limit: int | None, flat: bool) -> None:
    from analysis.parser_registry import resolve

    paths = pinned_paths()[: limit or None]
    dispositions: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    agreements: collections.Counter = collections.Counter()
    inputs: collections.Counter = collections.Counter()
    compared = 0
    started = time.perf_counter()
    for path in paths:
        if not path.exists():
            dispositions["missing_file"] += 1
            continue
        markdown, outcome, recon, metrics = run_one(path, scanned=False, flat=flat)
        if markdown is None:
            dispositions["no_text"] += 1
            continue
        verdict = disposition(outcome, recon, metrics)
        dispositions[verdict] += 1
        reasons[outcome.reason] += 1
        inputs[outcome.input_kind] += 1
        reference = resolve(markdown).statement
        if reference is not None and outcome.statement is not None:
            compared += 1
            checks = field_agreement(outcome.statement, reference)
            for name, agreed in checks.items():
                agreements[name] += int(agreed)
            if verdict == "validated":
                # THE veto metric. A published value that does not match the
                # audited truth is a false validation, and one is too many.
                agreements["validated_and_correct" if all(checks.values())
                           else "VALIDATED_AND_WRONG"] += 1
    elapsed = time.perf_counter() - started
    print(f"\n== stratum A: pinned corpus ({len(paths)} documents, "
          f"{'flat text' if flat else 'geometry'}, {elapsed:.0f}s) ==")
    _print("disposition", dispositions, len(paths))
    _print("structurer reason", reasons, len(paths))
    _print("input", inputs, len(paths))
    print(f"\ncompared against the claiming parser on {compared} documents:")
    _print("field agreement", agreements, compared or 1)


def discovery_rows(reports_root: Path) -> list[dict]:
    rows: dict[str, dict] = {}
    for run in sorted(reports_root.iterdir()):
        candidate = run / "rows.csv"
        if candidate.exists():
            for row in csv.DictReader(candidate.open(encoding="utf-8")):
                rows[row["relative_path"]] = row
    return list(rows.values())


def sample(rows: list[dict], per_cluster: int) -> dict[str, list[dict]]:
    """Deterministic stratified sample: sort by path, take every k-th."""
    out: dict[str, list[dict]] = {}
    for cluster, folders in CLUSTERS.items():
        members = sorted(
            (
                row for row in rows
                if row["outcome_class"] != "deferred"
                and row["dispatch_outcome"] in ("unclaimed", "")
                and row["outcome_reason"] in ("no_parser_matched", "parser_declined", "exception")
                and any(folder.lower() in row["folder_label"].lower() for folder in folders)
            ),
            key=lambda row: row["relative_path"],
        )
        step = max(1, len(members) // per_cluster) if members else 1
        out[cluster] = members[::step][:per_cluster]
    return out


def run_archive(reports_root: Path, archive_root: Path, per_cluster: int, flat: bool) -> None:
    rows = discovery_rows(reports_root)
    print(f"discovery rows available: {len(rows)}")
    for cluster, members in sample(rows, per_cluster).items():
        dispositions: collections.Counter = collections.Counter()
        reasons: collections.Counter = collections.Counter()
        signs: collections.Counter = collections.Counter()
        started = time.perf_counter()
        for row in members:
            path = archive_root / row["relative_path"]
            if not path.exists():
                dispositions["missing_file"] += 1
                continue
            markdown, outcome, recon, metrics = run_one(
                path, scanned=row["classification"] == "scanned", flat=flat
            )
            if markdown is None:
                dispositions["no_text"] += 1
                continue
            dispositions[disposition(outcome, recon, metrics)] += 1
            reasons[outcome.reason] += 1
            for source, count in outcome.sign_sources.items():
                signs[source] += count
        elapsed = time.perf_counter() - started
        print(f"\n== stratum B: {cluster} ({len(members)} documents, "
              f"{'flat text' if flat else 'geometry'}, {elapsed:.0f}s) ==")
        _print("disposition", dispositions, len(members) or 1)
        _print("structurer reason", reasons, len(members) or 1)
        _print("sign source (rows)", signs, sum(signs.values()) or 1)


def _print(title: str, counter: collections.Counter, total: int) -> None:
    print(f"  {title}:")
    for key, count in counter.most_common():
        print(f"    {key:<28}{count:>6}  {count / total:6.1%}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", action="store_true")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--flat", action="store_true", help="Ignore geometry (the 3a baseline).")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--per-cluster", type=int, default=25)
    parser.add_argument("--reports", default="discovery_reports")
    parser.add_argument("--archive-root", help=f"default: ${ENV_VAR}")
    args = parser.parse_args()

    if args.corpus:
        run_corpus(args.limit, args.flat)
    if args.archive:
        archive_root = Path(args.archive_root) if args.archive_root else bank_statements_dir_or_exit()
        run_archive(Path(args.reports), archive_root, args.per_cluster, args.flat)
    if not args.corpus and not args.archive:
        parser.error("choose --corpus and/or --archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

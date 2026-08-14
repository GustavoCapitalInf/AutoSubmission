"""W3-3a spike harness: measure the GATE, not the structurer. NOT PRODUCTION.

The design is taken from the prototype `eval_unknown_banks.py` (f14282e): one
question per document — did the layout-agnostic path reach a value the platform
would publish, or did it fail closed, and where exactly did it stop? Its
recorded-fixture replay mode is the right shape for a permanent harness and is
recommended in the investigation document; this spike measures live instead,
because the population it has to characterise is the archive and there are no
recorded fixtures for it yet.

Two strata:

* `--corpus` — the pinned 109. Every one of them is claimed by a deterministic
  parser and audited field by field, so this stratum measures ACCURACY: does
  the structurer reproduce what the audited truth says, or merely something
  self-consistent?
* `--archive` — documents no parser claimed, sampled deterministically from the
  discovery rows by cluster. This stratum measures REACH: how much of the
  unclaimed half becomes publishable.

Output is aggregate counts only. No document content, no filename, no amount
from any real statement is printed or written.

Usage (from the repo root, archive present):
    python -m experiments.w3_3a.evaluate --corpus
    python -m experiments.w3_3a.evaluate --archive --per-cluster 25
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.dates import assign_transaction_years  # noqa: E402
from analysis.metrics import compute_metrics  # noqa: E402
from analysis.pipeline import normalize_statement  # noqa: E402
from analysis.reconcile import reconcile  # noqa: E402
from analysis.transaction_classifier import classify_statement_transactions  # noqa: E402

from .structurer import structure  # noqa: E402

ARCHIVE = Path("Bank Statements")
ARTIFACTS = Path("tests/corpus_cache")


# ---------------------------------------------------------------------------
# Reading (production ladder, offline rungs only - the DSC-1 binding)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def gate(markdown: str, statement):
    """Exactly the checks the production pipeline applies after extraction."""
    statement = normalize_statement(assign_transaction_years(statement))
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


def disposition(result, recon, metrics) -> str:
    if result.statement is None:
        return f"refused_{result.reason}"
    if metrics.average_daily_balance is None:
        return "withheld_adb"
    if not recon.ok:
        return "review_recon"
    return "validated"


# ---------------------------------------------------------------------------
# Stratum A: the pinned corpus (accuracy against audited truth)
# ---------------------------------------------------------------------------

def pinned_paths() -> list[Path]:
    """The 109 pinned documents, from the same manifest the corpus gate pins."""
    from corpus_gate import BALANCE_CSV, manifest_paths, read_csv

    return [ROOT / ARCHIVE / relative for relative in manifest_paths(read_csv(BALANCE_CSV))]


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


def run_corpus(limit: int | None, date_anywhere: bool = False) -> None:
    from analysis.parser_registry import resolve

    paths = pinned_paths()
    if limit:
        paths = paths[:limit]
    dispositions = collections.Counter()
    agreements = collections.Counter()
    reasons = collections.Counter()
    compared = 0
    started = time.perf_counter()
    for path in paths:
        if not path.exists():
            dispositions["missing_file"] += 1
            continue
        markdown = read_markdown(path, allow_local_ocr=False)
        if markdown is None:
            dispositions["no_text"] += 1
            continue
        result = structure(markdown, date_anywhere=date_anywhere)
        recon = metrics = None
        if result.statement is not None:
            _, recon, metrics = gate(markdown, result.statement)
        verdict = disposition(result, recon, metrics)
        dispositions[verdict] += 1
        reasons[result.reason] += 1
        reference = resolve(markdown).statement
        if reference is not None and result.statement is not None:
            compared += 1
            checks = field_agreement(result.statement, reference)
            for name, agreed in checks.items():
                agreements[name] += int(agreed)
            if verdict == "validated":
                # THE metric: a value the platform would publish that does not
                # match the audited truth is a false validation, and one is too
                # many. Everything else is a fail-closed miss.
                agreements["validated_and_correct" if all(checks.values()) else "VALIDATED_AND_WRONG"] += 1
    elapsed = time.perf_counter() - started
    print(f"\n== stratum A: pinned corpus ({len(paths)} documents, {elapsed:.0f}s) ==")
    _print_counter("disposition", dispositions, len(paths))
    _print_counter("structurer reason", reasons, len(paths))
    print(f"\ncompared against the claiming parser on {compared} documents:")
    _print_counter("field agreement", agreements, compared or 1)


# ---------------------------------------------------------------------------
# Stratum B: archive clusters (reach on unclaimed documents)
# ---------------------------------------------------------------------------

CLUSTERS: dict[str, tuple[str, ...]] = {
    "known_bank_variants": ("BMO", "Chase", "TD Bank", "CIBC", "Bank of America", "RBC"),
    "unidentified": ("Unidentified",),
    "low_volume_unknown": ("Huntington", "Mercury", "Fifth Third", "Citibank", "Lead", "Zions", "Brex"),
}


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
        if not members:
            out[cluster] = []
            continue
        step = max(1, len(members) // per_cluster)
        out[cluster] = members[::step][:per_cluster]
    return out


def run_archive(reports_root: Path, per_cluster: int, archive_root: Path, date_anywhere: bool = False) -> None:
    rows = discovery_rows(reports_root)
    print(f"discovery rows available: {len(rows)}")
    for cluster, members in sample(rows, per_cluster).items():
        dispositions = collections.Counter()
        reasons = collections.Counter()
        chained = 0
        started = time.perf_counter()
        for row in members:
            path = archive_root / row["relative_path"]
            if not path.exists():
                dispositions["missing_file"] += 1
                continue
            markdown = read_markdown(path, allow_local_ocr=row["classification"] == "scanned")
            if markdown is None:
                dispositions["no_text"] += 1
                continue
            result = structure(markdown, date_anywhere=date_anywhere)
            recon = metrics = None
            if result.statement is not None:
                _, recon, metrics = gate(markdown, result.statement)
            dispositions[disposition(result, recon, metrics)] += 1
            reasons[result.reason] += 1
            chained += int(result.chained)
        elapsed = time.perf_counter() - started
        print(f"\n== stratum B: {cluster} ({len(members)} documents, {elapsed:.0f}s) ==")
        print(f"balance-chain hypothesis accepted on {chained}/{len(members)}")
        _print_counter("disposition", dispositions, len(members) or 1)
        _print_counter("structurer reason", reasons, len(members) or 1)


def _print_counter(title: str, counter: collections.Counter, total: int) -> None:
    print(f"  {title}:")
    for key, count in counter.most_common():
        print(f"    {key:<28}{count:>6}  {count / total:6.1%}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", action="store_true")
    parser.add_argument("--archive", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--per-cluster", type=int, default=25)
    parser.add_argument(
        "--date-anywhere", action="store_true",
        help="Row-detection variant B: the date may sit anywhere in the line head.",
    )
    parser.add_argument("--reports", default="discovery_reports")
    parser.add_argument(
        "--archive-root", default=str(ROOT / ARCHIVE),
        help="Where the discovery archive lives (the main checkout, not this worktree).",
    )
    args = parser.parse_args()

    if args.corpus:
        run_corpus(args.limit, args.date_anywhere)
    if args.archive:
        run_archive(Path(args.reports), args.per_cluster, Path(args.archive_root), args.date_anywhere)
    if not args.corpus and not args.archive:
        parser.error("choose --corpus and/or --archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

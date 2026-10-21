"""tools/truth_report.py — BOTH denominators, joined across the firewall
(Phase 2.2 cell T, card items 3 and 9; R11, R12, D2, D10).

    python tools/truth_report.py --rows <run dir>/rows.csv [--out <private>.md]

(Review MINOR-7: an earlier version of this block advertised a `--digest`
option the parser never defined. The sealed store is located by its own
environment variable, read by `tools/holdout`, and this tool passes no path to
it at all — so there is nothing for such a flag to do.)

Why this is a tool and not a report section
-------------------------------------------
R11 requires two denominators, always, both printed. The RAW one — validated
documents over the corpus — the discovery runner computes itself and prints
first. The CONFIRMED-COMPLETE-LEGIBLE one it cannot compute at all: `CCL` is
the set of documents an ADJUDICATOR confirmed complete and sufficiently
legible, that lives in the sealed truth store, and the leakage firewall
forbids every module under `analysis/ layout/ ocr/ evidence/ discovery/
webapp/ telemetry/` from naming `SEALED_TRUTH_DIR` or importing
`tools.holdout`. So the runner prints `ccl_adjudicated: not available in this
process` — a named absence, never a proxy under the adjudicated heading — and
this instrument, which is a `tools/` reader the firewall permits, does the
join.

D10: adjudication never blocks a gate. With no sealed store (the variable
unset, the store empty) this prints the raw denominator, the classifier's
PROPOSAL, and an explicit `adjudicated: none` — a truth table v0 that says so,
rather than a gate that waits.

What it will not print
-----------------------
No full content sha, ever, anywhere. No verdict FIGURE — not an opening or
closing balance, not a period date, not a transaction count, not a sampled
row: those live in the sealed record and reading them into a report is exactly
the leak the store exists to prevent. The finest grain this produces is
`sha16 + kind + which source said so`, and only into a git-ignored `--out`
file; stdout is aggregates. A non-ignored `--out` is refused before anything
is read.

Read-only in both directions: it opens the store to READ, writes nothing into
the checkout, and never modifies a verdict.
"""
from __future__ import annotations

import argparse
import collections
import csv
import subprocess
import sys
from pathlib import Path

from layout.refusals import ACCOUNT_KINDS, KINDS

#: R12: the PRIMARY confirmed-complete-legible population is the bank-account
#: statement kind this engine targets. Card, loan and brokerage statements are
#: measured and reported as their own rows and never folded into it, until
#: they are explicitly admitted.
PRIMARY_CCL_ACCOUNT_KIND = "deposit"

#: The one kind that can be complete: the CCL is `STATEMENT_COMPLETE` AND
#: legible. `STATEMENT_PARTIAL` and `STATEMENT_ILLEGIBLE` are named refusals,
#: not near-misses, and admitting either would make the second denominator
#: mean "documents we would like to have validated".
CCL_KIND = "STATEMENT_COMPLETE"

SOURCE_ADJUDICATED = "adjudicated"
SOURCE_PROPOSED = "classifier_proposed"


def _refuse_tracked_out(out: Path) -> None:
    """The per-document file names documents; it may live only under a
    git-ignored path."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(out)], capture_output=True, text=True)
    except OSError as exc:
        raise SystemExit(
            f"refusing --out {out}: git could not be asked whether the path is ignored "
            f"({type(exc).__name__})"
        )
    if result.returncode != 0:
        raise SystemExit(
            f"refusing --out {out}: the path is not git-ignored (private per-document output only)"
        )


def read_rows(path: Path) -> dict[str, dict]:
    """sha -> the FIRST row of that sha in run order, research rows excluded.

    Research partitions are not historical truth (D7), so a coverage
    denominator that counted them would be a number about a partition no run
    of record can select.
    """
    documents: dict[str, dict] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("research_partition") or "").strip():
                continue
            sha = (row.get("content_sha256") or "").strip().upper()
            if not sha:
                continue
            previous = documents.get(sha)
            if previous is None:
                documents[sha] = row
            elif (row.get("outcome_class") or "") == "validated":
                # A sha whose rows disagree is validated if ANY of them is:
                # the document validated, whichever path it was reached by.
                previous["outcome_class"] = "validated"
    return documents


def read_store() -> tuple[dict[str, dict] | None, str]:
    """`(sha -> the current sealed record, a note)`.

    `(None, why)` when there is no store to read — an unset variable, a
    missing directory, a store that disagrees with its own manifest. Every one
    of those is REPORTED and none of them is fatal: the raw denominator and
    the classifier's proposal do not depend on the store, and a milestone that
    stopped for a missing adjudication would be exactly the gate D10 refuses
    to build.
    """
    try:
        from tools.holdout.store import TruthStore

        store = TruthStore.open()
        return store.latest_by_sha(), f"{len(store.records())} sealed records"
    except Exception as exc:
        return None, f"no sealed store read ({type(exc).__name__}: {exc})"


def _is_ccl(record: dict) -> bool:
    return record.get("kind") == CCL_KIND and bool(record.get("legible"))


def join(documents: dict[str, dict], sealed: dict[str, dict] | None) -> dict:
    """The truth table: one primary kind per document, adjudicated where a
    sealed verdict exists and classifier-proposed everywhere else, LABELLED
    per document with which of the two it was.

    D2/D10: a proposal never masquerades as truth. The two sources are counted
    separately at every level, and the disjoint sum is asserted over their
    union — a document is in exactly one bucket whichever source named it.
    """
    sealed = sealed or {}
    per_document: list[dict] = []
    for sha, row in documents.items():
        record = sealed.get(sha)
        if record is not None:
            kind = record.get("kind") or "KIND_UNCERTAIN"
            account_kind = record.get("account_kind") or "unknown"
            legible = bool(record.get("legible"))
            source = SOURCE_ADJUDICATED
        else:
            kind = (row.get("document_class") or "KIND_UNCERTAIN").strip() or "KIND_UNCERTAIN"
            account_kind = (row.get("class_account_kind") or "unknown").strip() or "unknown"
            # The classifier has no legibility verdict of its own: an illegible
            # document is a KIND, so anything it calls complete it also calls
            # legible. Said here rather than implied, because the two sources
            # are not measuring the same thing and the report says so.
            legible = kind == CCL_KIND
            source = SOURCE_PROPOSED
        per_document.append({
            "sha16": sha[:16],
            "kind": kind if kind in KINDS else "KIND_UNCERTAIN",
            "account_kind": account_kind if account_kind in ACCOUNT_KINDS else "unknown",
            "legible": legible,
            "source": source,
            "validated": (row.get("outcome_class") or "") == "validated",
            "outcome": (row.get("outcome_class") or "").strip(),
        })

    validated = sum(1 for entry in per_document if entry["validated"])
    by_kind = collections.Counter(entry["kind"] for entry in per_document)
    by_source = collections.Counter(entry["source"] for entry in per_document)

    def ccl(source: str | None, account_kind: str | None) -> dict:
        members = [
            entry for entry in per_document
            if entry["kind"] == CCL_KIND and entry["legible"]
            and (source is None or entry["source"] == source)
            and (account_kind is None or entry["account_kind"] == account_kind)
        ]
        hit = sum(1 for entry in members if entry["validated"])
        return {"population": len(members), "validated": hit,
                "coverage": (hit / len(members)) if members else 0.0}

    return {
        "per_document": per_document,
        "raw": {"population": len(per_document), "validated": validated,
                "coverage": (validated / len(per_document)) if per_document else 0.0},
        "by_kind": {kind: by_kind[kind] for kind in KINDS if by_kind[kind]},
        "disjoint_sum": sum(by_kind.values()),
        "by_source": dict(by_source),
        "ccl_adjudicated": ccl(SOURCE_ADJUDICATED, PRIMARY_CCL_ACCOUNT_KIND),
        "ccl_classifier_proposed": ccl(SOURCE_PROPOSED, PRIMARY_CCL_ACCOUNT_KIND),
        "ccl_by_account_kind": {
            kind: {"adjudicated": ccl(SOURCE_ADJUDICATED, kind),
                   "classifier_proposed": ccl(SOURCE_PROPOSED, kind)}
            for kind in ACCOUNT_KINDS
        },
    }


def render(report: dict, *, store_note: str) -> str:
    """ASCII only, aggregates only. No sha, no verdict figure, no date."""
    raw = report["raw"]
    lines = [
        "truth report: both denominators (R11), the raw one first and never replaced",
        "",
        f"sealed store: {store_note}",
        f"  adjudicated documents in this population   {report['by_source'].get(SOURCE_ADJUDICATED, 0):>8}",
        f"  classifier-proposed                        {report['by_source'].get(SOURCE_PROPOSED, 0):>8}",
        "",
        f"RAW           validated {raw['validated']} / {raw['population']}   {raw['coverage']:.1%}",
    ]
    for label, key in (("CCL adjudicated       ", "ccl_adjudicated"),
                       ("CCL classifier-proposed", "ccl_classifier_proposed")):
        block = report[key]
        if block["population"] == 0:
            lines.append(f"{label} none ({PRIMARY_CCL_ACCOUNT_KIND} statements confirmed complete and legible: 0)")
            continue
        lines.append(
            f"{label} validated {block['validated']} / {block['population']}"
            f"   {block['coverage']:.1%}"
        )
    lines += [
        "",
        f"the raw denominator is {raw['population']} and is never replaced by either figure above",
        "",
        "account kinds, reported separately and never folded into the primary CCL (R12)",
        f"  {'kind':<12}{'adjudicated':>24}{'proposed':>20}",
    ]
    for kind in ACCOUNT_KINDS:
        block = report["ccl_by_account_kind"][kind]
        lines.append(
            f"  {kind:<12}"
            f"{block['adjudicated']['validated']:>12} / {block['adjudicated']['population']:<9}"
            f"{block['classifier_proposed']['validated']:>10} / {block['classifier_proposed']['population']:<9}"
        )
    lines += ["", "disjoint primary classification (one kind per document)",
              f"  sum {report['disjoint_sum']} == population {raw['population']}"
              f"   {'OK' if report['disjoint_sum'] == raw['population'] else 'MISMATCH'}"]
    for kind, count in report["by_kind"].items():
        share = f"{count / raw['population']:6.1%}" if raw["population"] else "     -"
        lines.append(f"  {kind:<24}{count:>8}   {share}")
    return "\n".join(lines)


def render_private(report: dict) -> str:
    """The finest grain that exists anywhere: sha16, kind, which source said
    so, and the outcome. No full sha; no figure from a sealed record."""
    lines = ["# per-document truth table (PRIVATE: git-ignored path only)", "",
             "| sha16 | kind | account_kind | source | outcome |", "|---|---|---|---|---|"]
    lines += [
        f"| {entry['sha16']} | {entry['kind']} | {entry['account_kind']} "
        f"| {entry['source']} | {entry['outcome']} |"
        for entry in sorted(report["per_document"], key=lambda e: (e["kind"], e["sha16"]))
    ]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path,
                        help="a discovery run's rows.csv")
    parser.add_argument("--out", type=Path, default=None,
                        help="a GIT-IGNORED path for the per-document table (sha16 + kind only)")
    args = parser.parse_args(argv)

    if args.out is not None:
        _refuse_tracked_out(args.out)
    documents = read_rows(args.rows)
    sealed, store_note = read_store()
    report = join(documents, sealed)
    print(render(report, store_note=store_note))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_private(report), encoding="utf-8")
        print(f"\nper-document table written to {args.out}", file=sys.stderr)
    return 0 if report["disjoint_sum"] == report["raw"]["population"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

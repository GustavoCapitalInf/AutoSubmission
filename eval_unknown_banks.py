"""Evaluate the universal ("any bank") path against never-seen statement layouts.

Answers one question per statement: did the unknown-layout path reach an
automatic corporate approval, or did it fail closed to manual review, and why?

Two modes:

* **Replay (default)** — walk `tests/fixtures/unknown_banks/`. Each case carries
  the document markdown plus a recorded structurer output, so the run is offline,
  free and deterministic. It measures the part that decides trust: reconcile,
  ADB, classification, metrics and the corporate approval gate.
* **Live** — `--pdf`/`--pdf-dir` run real documents through
  `resolve_document_markdown` (native text layer first, Unlimited-OCR otherwise)
  and a real structurer. Vendor structuring stays off unless `--allow-vendor` is
  passed, matching the zero-vendor-cost production policy.

Usage:
  .venv/bin/python eval_unknown_banks.py
  .venv/bin/python eval_unknown_banks.py --check                 # regression gate
  .venv/bin/python eval_unknown_banks.py --csv output/unknown-bank-eval.csv
  .venv/bin/python eval_unknown_banks.py --pdf-dir "Bank Statements/Others" --allow-vendor
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from analysis.schema import Statement
from analysis.universal import (
    CallableStructurer,
    PROVIDED_MARKDOWN,
    StatementStructurer,
    UniversalOutcome,
    analyze_any_bank_markdown,
    analyze_any_bank_pdf,
    default_structurers,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = ROOT / "tests" / "fixtures" / "unknown_banks"

FIELDS = [
    "case", "category", "route", "document_source", "backend", "attempts",
    "escalated", "parsed", "transactions", "reconciled", "summary_reconciled",
    "coverage_credits", "coverage_debits", "adb_validated",
    "average_daily_balance", "corporate_use", "approved", "review_reason",
    "expectation",
]


class CorpusError(RuntimeError):
    pass


@dataclass
class EvalCase:
    name: str
    category: str
    label: str
    markdown: str
    document_source: str
    structurers: tuple[StatementStructurer, ...]
    expected: dict = field(default_factory=dict)
    notes: str = ""


def _statement_from(payload: dict, *, where: str) -> Statement:
    try:
        return Statement.model_validate(payload)
    except Exception as exc:
        raise CorpusError(f"{where}: recorded structuring is not a valid Statement: {exc}") from exc


def _replay_structurers(payload: object, *, where: str) -> tuple[StatementStructurer, ...]:
    """Build a structuring ladder that replays recorded attempts in order."""
    if isinstance(payload, dict) and "attempts" in payload:
        records = payload["attempts"]
    elif isinstance(payload, list):
        records = payload
    else:
        records = [{"backend": "replay:primary", "statement": payload}]
    if not isinstance(records, list) or not records:
        raise CorpusError(f"{where}: recorded structuring has no attempts")

    chain: list[StatementStructurer] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise CorpusError(f"{where}: attempt {index} is not an object")
        backend = str(record.get("backend") or f"replay:{index}")
        if "error" in record:
            message = str(record["error"])

            def fail(_markdown: str, *, _message: str = message) -> Statement:
                raise RuntimeError(_message)

            chain.append(CallableStructurer(name=backend, fn=fail))
            continue
        statement = _statement_from(
            record.get("statement") or record,
            where=f"{where} attempt {index}",
        )
        chain.append(
            CallableStructurer(
                name=backend,
                # A recorded attempt is a fixed transcript: it does not react to
                # feedback, which keeps the replay honest about the gate.
                fn=lambda _markdown, _statement=statement: _statement.model_copy(deep=True),
            )
        )
    return tuple(chain)


def load_corpus(corpus: Path, *, only: set[str] | None = None) -> list[EvalCase]:
    if not corpus.is_dir():
        raise CorpusError(f"corpus directory not found: {corpus}")
    cases: list[EvalCase] = []
    for case_dir in sorted(path for path in corpus.iterdir() if path.is_dir()):
        name = case_dir.name
        if only and name not in only:
            continue
        markdown_path = case_dir / "statement.md"
        structured_path = case_dir / "structured.json"
        case_path = case_dir / "case.json"
        for required in (markdown_path, structured_path, case_path):
            if not required.exists():
                raise CorpusError(f"{name}: missing {required.name}")
        meta = json.loads(case_path.read_text(encoding="utf-8"))
        cases.append(
            EvalCase(
                name=name,
                category=str(meta.get("category") or "uncategorized"),
                label=str(meta.get("label") or name),
                markdown=markdown_path.read_text(encoding="utf-8"),
                document_source=str(meta.get("document_source") or PROVIDED_MARKDOWN),
                structurers=_replay_structurers(
                    json.loads(structured_path.read_text(encoding="utf-8")),
                    where=name,
                ),
                expected=dict(meta.get("expected") or {}),
                notes=str(meta.get("notes") or ""),
            )
        )
    if not cases:
        raise CorpusError(f"no cases found under {corpus}")
    return cases


def _percent(value: float | None) -> str:
    return "" if value is None else f"{value:.0%}"


def observed(outcome: UniversalOutcome) -> dict:
    """The gate facts this harness measures, independent of any expectation."""
    report = outcome.report
    recon = report.reconciliation if report else None
    metrics = report.metrics if report else None
    structuring = outcome.structuring
    return {
        "route": outcome.route,
        "document_source": outcome.document_source,
        "backend": (structuring.backend_used if structuring else outcome.model_used) or "",
        "attempts": len(structuring.attempts) if structuring else 0,
        "escalated": bool(structuring.escalated) if structuring else False,
        "parsed": outcome.parsed,
        "transactions": len(report.statement.transactions) if report else 0,
        "reconciled": outcome.reconciled,
        "summary_reconciled": outcome.summary_reconciled,
        "coverage_credits": _percent(recon.credit_coverage if recon else None),
        "coverage_debits": _percent(recon.debit_coverage if recon else None),
        "adb_validated": outcome.adb_validated,
        "average_daily_balance": (
            metrics.average_daily_balance if metrics is not None else None
        ),
        "corporate_use": outcome.corporate_use,
        "approved": outcome.approved,
        "review_reason": outcome.manual_review_reason or "",
    }


def compare(row: dict, expected: dict) -> list[str]:
    """Every way the observed gate result deviates from the recorded expectation."""
    problems: list[str] = []
    for key, want in expected.items():
        if key == "review_reason_contains":
            reason = str(row.get("review_reason") or "")
            if want is None:
                if reason:
                    problems.append(f"review_reason: expected none, got {reason!r}")
            elif str(want).lower() not in reason.lower():
                problems.append(f"review_reason: expected to contain {want!r}, got {reason!r}")
            continue
        if key not in row:
            problems.append(f"{key}: unknown field")
            continue
        got = row[key]
        if want is None and got in (None, ""):
            continue
        if got != want:
            problems.append(f"{key}: expected {want!r}, got {got!r}")
    return problems


def run_case(case: EvalCase) -> dict:
    try:
        outcome = analyze_any_bank_markdown(
            case.markdown,
            structurers=case.structurers,
            document_source=case.document_source,
        )
    except Exception as exc:
        traceback.print_exc()
        row = {name: "" for name in FIELDS}
        row.update(
            case=case.name,
            category=case.category,
            route="error",
            parsed=False,
            approved=False,
            corporate_use="manual_review_required",
            review_reason=f"{type(exc).__name__}: {exc}",
        )
        return row
    row = {"case": case.name, "category": case.category, **observed(outcome)}
    problems = compare(row, case.expected)
    row["expectation"] = "ok" if not problems else "MISMATCH: " + "; ".join(problems)
    return row


def run_pdfs(
    paths: list[Path],
    *,
    allow_vendor: bool,
    force_ocr: bool,
) -> list[dict]:
    structurers = default_structurers(allow_vendor_structurer=allow_vendor)
    rows: list[dict] = []
    for path in paths:
        print(f"analyzing {path.name} ...", file=sys.stderr, flush=True)
        try:
            outcome = analyze_any_bank_pdf(
                path.read_bytes(),
                source_file=path.name,
                force_ocr=force_ocr,
                structurers=structurers,
                allow_vendor_structurer=allow_vendor,
            )
            row = {"case": path.name, "category": "live_pdf", **observed(outcome)}
        except Exception as exc:
            traceback.print_exc()
            row = {name: "" for name in FIELDS}
            row.update(
                case=path.name,
                category="live_pdf",
                route="error",
                parsed=False,
                approved=False,
                corporate_use="manual_review_required",
                review_reason=f"{type(exc).__name__}: {exc}",
            )
        row.setdefault("expectation", "")
        rows.append(row)
    return rows


def _rate(rows: list[dict], key: str) -> float:
    return (sum(1 for row in rows if row.get(key) is True) / len(rows)) if rows else 0.0


def render(rows: list[dict]) -> str:
    lines: list[str] = ["Unknown-bank universal path — per statement", "=" * 78]
    for row in rows:
        verdict = "APPROVED" if row.get("approved") else "REVIEW"
        lines.append(f"{row['case']}  [{row['category']}]  -> {verdict}")
        lines.append(
            f"    route={row['route']} source={row['document_source']} "
            f"backend={row['backend']} attempts={row['attempts']} "
            f"escalated={row['escalated']}"
        )
        lines.append(
            f"    parsed={row['parsed']} transactions={row['transactions']} "
            f"reconciled={row['reconciled']} summary={row['summary_reconciled']} "
            f"adb_validated={row['adb_validated']} corporate_use={row['corporate_use']}"
        )
        if row.get("review_reason"):
            lines.append(f"    reason: {row['review_reason']}")
        if row.get("expectation") and row["expectation"] != "ok":
            lines.append(f"    {row['expectation']}")

    total = len(rows)
    approved = sum(1 for row in rows if row.get("approved") is True)
    lines.extend([
        "",
        "Rates",
        "-" * 78,
        f"  statements            : {total}",
        f"  parsed to a Statement : {_rate(rows, 'parsed'):.0%}",
        f"  reconciled            : {_rate(rows, 'reconciled'):.0%}",
        f"  ADB validated         : {_rate(rows, 'adb_validated'):.0%}",
        f"  corporate approved    : {approved}/{total} ({approved / total if total else 0:.0%})",
        f"  manual review         : {total - approved}/{total} "
        f"({(total - approved) / total if total else 0:.0%})",
    ])

    categories = sorted({str(row.get("category") or "") for row in rows})
    if len(categories) > 1:
        lines.append("")
        lines.append("  by category:")
        for category in categories:
            subset = [row for row in rows if row.get("category") == category]
            hits = sum(1 for row in subset if row.get("approved") is True)
            lines.append(
                f"    {category:<12} approved {hits}/{len(subset)} "
                f"({hits / len(subset):.0%})"
            )
    return "\n".join(lines)


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure approve vs manual-review rates on unknown bank layouts.",
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Fixture corpus directory.")
    parser.add_argument("--case", action="append", default=[], help="Run only this case (repeatable).")
    parser.add_argument("--pdf", action="append", default=[], help="Run a real PDF (repeatable).")
    parser.add_argument("--pdf-dir", help="Run every PDF under this directory.")
    parser.add_argument(
        "--allow-vendor",
        action="store_true",
        help="Permit the vendor structurer for live PDFs (off by default: zero vendor cost).",
    )
    parser.add_argument("--force-ocr", action="store_true", help="Skip the native text layer for live PDFs.")
    parser.add_argument("--csv", metavar="FILE", help="Write one row per statement here.")
    parser.add_argument("--json", metavar="FILE", help="Write the full result set here.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when a corpus case deviates from its recorded expectation.",
    )
    args = parser.parse_args()

    pdfs = [Path(path) for path in args.pdf]
    if args.pdf_dir:
        pdfs.extend(sorted(Path(args.pdf_dir).rglob("*.pdf")))

    if pdfs:
        rows = run_pdfs(pdfs, allow_vendor=args.allow_vendor, force_ocr=args.force_ocr)
    else:
        try:
            cases = load_corpus(Path(args.corpus), only=set(args.case) or None)
        except CorpusError as exc:
            print(f"corpus error: {exc}", file=sys.stderr)
            sys.exit(2)
        rows = [run_case(case) for case in cases]

    print(render(rows))

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({name: _csv_value(row.get(name)) for name in FIELDS})
        print(f"\nwrote {len(rows)} rows to {args.csv}", file=sys.stderr)
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    mismatches = [row for row in rows if str(row.get("expectation", "")).startswith("MISMATCH")]
    if mismatches:
        print(
            f"\n{len(mismatches)} case(s) deviate from the recorded expectation",
            file=sys.stderr,
        )
        if args.check:
            sys.exit(1)


if __name__ == "__main__":
    main()

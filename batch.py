"""Batch-analyze a folder of bank statements into one triage CSV.

Accepts OCR'd markdown files (fast) and/or PDFs (OCR'd first via the running OCR
server — set OCR_BASE_URL/OCR_API_KEY). One row per statement with the key
underwriting figures and a needs_review flag so clean statements flow through and
only the questionable ones get human eyes.

Usage:
  .venv/bin/python batch.py output/ --out triage.csv          # a folder of .md
  OCR_BASE_URL=http://localhost:8000/v1 OCR_API_KEY=EMPTY \\
      .venv/bin/python batch.py BankStatements/ --out triage.csv   # PDFs (OCR+analyze)
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import sys
import traceback
from pathlib import Path

from analysis.pipeline import analyze_document, DocumentReport, Report
from telemetry import (
    DispatchCollector,
    StageTimer,
    build_record,
    dispatch_section,
    document_section,
    model_calls_for,
    new_run_id,
    open_jsonl_sink,
    score_vector,
    source_section,
)

FIELDS = [
    "file", "bank", "account", "period_start", "period_end",
    "summary_reconciles", "average_daily_balance", "total_deposits", "total_debits",
    "total_posted_credits", "verified_revenue_total", "verified_revenue_count",
    "unverified_deposit_total", "unverified_deposit_count", "non_revenue_total",
    "non_revenue_count", "maximum_revenue", "revenue_reconciles",
    "revenue_reconciliation_delta", "cash_flow", "lender_credits", "lender_debits",
    "lender_debit_count", "lenders_detected", "potential_lenders_detected",
    "potential_lender_debit_count", "potential_lender_debit_total",
    "insurance_count", "insurance_total", "withholding_numerator",
    "withholding_denominator", "withholding_rate", "potential_withholding_numerator",
    "potential_withholding_denominator", "potential_withholding_exposure",
    "potential_withholding_review_required", "pos_count", "pos_credit_count",
    "atm_withdrawal_count", "loan_count",
    "debit_coverage", "nsf", "mca_funders", "recurring_debit_groups",
    "quality", "transaction_detail_reliable", "corporate_use", "needs_review",
    "model", "error",
]


def _markdown_for(path: Path, *, allow_visual_ocr: bool = False) -> str:
    return _read_source(path, allow_visual_ocr=allow_visual_ocr)[0]


def _read_source(path: Path, *, allow_visual_ocr: bool = False):
    """(markdown, StatementMarkdown | None, DocumentProfile | None, byte_size).

    The document object used to be discarded here; telemetry needs it for the
    OCR path taken and the O-3 truncation flags, and the preflight profile for
    the document facts. Neither changes what is analysed — `markdown` is
    produced exactly as before.

    OQ7 / F-4(a): `allow_visual_ocr` defaults to False — this CLI used to call
    `parse_statement` with the defaults (`allow_visual_ocr=True`), the same
    unbounded egress path `parse.py` had. The caller (`main`) probes and
    endpoint-checks before ever passing True (`--visual`). When the offline
    ladder cannot read a document and the visual rung is not allowed,
    `parse_statement` returns `None`: raised here as a clear, specific error
    so the per-file row records "no native/local text" rather than falling
    through into an unrelated downstream failure.
    """
    raw = path.read_bytes()
    if path.suffix.lower() == ".pdf":
        from ocr.inspect import inspect_pdf
        from ocr.pipeline import parse_statement

        profile = inspect_pdf(raw)
        doc = parse_statement(raw, source_file=path.name, allow_visual_ocr=allow_visual_ocr)
        if doc is None:
            raise RuntimeError(
                "no native or local text could be extracted; rerun with "
                "--visual to allow the local $0 OCR rung"
            )
        return doc.to_markdown(), doc, profile, len(raw)
    return path.read_text(encoding="utf-8"), None, None, len(raw)


def _content_sha256(data: bytes) -> str:
    """UPPERCASE hex, the platform-wide convention (ocr.inspect.content_sha256).

    Recomputed here rather than imported so this module keeps working on
    markdown inputs, which never go through the PDF preflight.
    """
    return hashlib.sha256(data).hexdigest().upper()


def _row(path: Path, report: Report) -> dict:
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    # A statement needs human review when the bank's own summary doesn't reconcile
    # (mis-extracted or internally inconsistent) — the figures can't be trusted.
    needs_review = (
        report.quality.corporate_use == "manual_review_required"
        or m.revenue_review_required
        or not m.revenue_reconciles
    )
    return {
        "file": path.name,
        "bank": s.bank or "",
        "account": s.account_number or "",
        "period_start": s.period_start or "",
        "period_end": s.period_end or "",
        "summary_reconciles": {True: "yes", False: "NO", None: "n/a"}[r.summary_ok],
        "average_daily_balance": (
            f"{m.average_daily_balance:.2f}"
            if m.average_daily_balance is not None
            else ""
        ),
        "total_deposits": f"{m.effective_total_deposits:.2f}",
        "total_debits": f"{m.effective_total_withdrawals:.2f}",
        "total_posted_credits": f"{m.total_posted_credits:.2f}",
        "verified_revenue_total": f"{m.verified_revenue_total:.2f}",
        "verified_revenue_count": m.verified_revenue_count,
        "unverified_deposit_total": f"{m.unverified_deposit_total:.2f}",
        "unverified_deposit_count": m.unverified_deposit_count,
        "non_revenue_total": f"{m.non_revenue_total:.2f}",
        "non_revenue_count": m.non_revenue_count,
        "maximum_revenue": f"{m.maximum_revenue:.2f}",
        "revenue_reconciles": "yes" if m.revenue_reconciles else "NO",
        "revenue_reconciliation_delta": f"{m.revenue_reconciliation_delta:.2f}",
        "cash_flow": f"{m.cash_flow:.2f}",
        "lender_credits": f"{m.lender_credits:.2f}",
        "lender_debits": f"{m.lender_debits:.2f}",
        "lender_debit_count": m.lender_debit_count,
        "lenders_detected": m.lenders_detected,
        "potential_lenders_detected": m.potential_lenders_detected,
        "potential_lender_debit_count": m.potential_lender_debit_count,
        "potential_lender_debit_total": f"{m.potential_lender_debit_total:.2f}",
        "insurance_count": m.insurance_count,
        "insurance_total": f"{m.insurance_total:.2f}",
        "withholding_numerator": f"{m.withholding_numerator:.2f}",
        "withholding_denominator": f"{m.withholding_denominator:.2f}",
        "withholding_rate": f"{m.withholding_rate:.2f}" if m.withholding_rate is not None else "",
        "potential_withholding_numerator": f"{m.potential_withholding_numerator:.2f}",
        "potential_withholding_denominator": f"{m.potential_withholding_denominator:.2f}",
        "potential_withholding_exposure": (
            f"{m.potential_withholding_exposure:.2f}"
            if m.potential_withholding_exposure is not None
            else ""
        ),
        "potential_withholding_review_required": m.potential_withholding_review_required,
        "pos_count": m.pos_count,
        "pos_credit_count": m.pos_credit_count,
        "atm_withdrawal_count": m.atm_withdrawal_count,
        "loan_count": m.loan_count,
        "debit_coverage": f"{r.debit_coverage:.0%}" if r.debit_coverage is not None else "",
        "nsf": m.effective_nsf_count,
        "mca_funders": "; ".join(fm.funder for fm in d.known_funders),
        "recurring_debit_groups": sum(1 for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")),
        "quality": report.quality.level,
        "transaction_detail_reliable": "yes" if report.quality.transaction_detail_reliable else "no",
        "corporate_use": report.quality.corporate_use,
        "needs_review": "REVIEW" if needs_review else "",
        "model": report.model_used,
        "error": "",
    }


def _emit(
    sink,
    run_id: str,
    path: Path,
    markdown: str | None,
    doc,
    profile,
    byte_size: int,
    collector: DispatchCollector,
    timer: StageTimer,
    seen_hashes: set[str],
    *,
    document: DocumentReport | None = None,
    error_type: str | None = None,
) -> None:
    """One telemetry record per document. Never raises (H3_SCHEMA I4).

    Note what is NOT recorded: `path.name`. Filenames carry customer and
    business names, so documents are identified by content hash alone.
    """
    try:
        from analysis.serialization import document_report_to_dict

        # The DOCUMENT's payload. RULE S makes this byte-identical to the
        # single-account serialisation this seam used to call, on every
        # document carrying one account -- which is every document this CLI
        # produces.
        payload = document_report_to_dict(document) if document is not None else None
        content_hash = (
            profile.content_sha256 if profile is not None
            else _content_sha256(path.read_bytes())
        )
        duplicate = content_hash in seen_hashes
        seen_hashes.add(content_hash)
        # Reuse the analysis sweep's prepared text for the near-miss sweep
        # (#PREPHAND); guarded on the text inside `score_vector`.
        scores, registration_count = score_vector(markdown, collector) if markdown else ([], 0)
        sink.write(build_record(
            run_id=run_id,
            emitter="batch",
            document=document_section(
                content_hash, byte_size, profile, duplicate_of_prior_record=duplicate
            ),
            source=source_section(doc),
            dispatch=dispatch_section(
                collector.dispatch, scores, registration_count, payload=payload,
            ),
            stages=timer.as_dict(),
            model_calls=model_calls_for(doc, payload),
            payload=payload,
            escalated=bool(report.escalated) if report is not None else False,
            error_type=error_type,
        ))
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch-analyze statements into a triage CSV.")
    ap.add_argument("path", help="A file or directory of .md and/or .pdf statements.")
    ap.add_argument("--out", metavar="FILE", help="Write CSV here (default stdout).")
    ap.add_argument(
        "--telemetry",
        metavar="FILE",
        help="H-3 telemetry JSONL (default telemetry_runs/<run_id>.jsonl; "
             "set TELEMETRY_DISABLED=1 to turn it off).",
    )
    ap.add_argument(
        "--visual", action="store_true",
        help="Allow the visual-OCR rung (local $0 server only, by default) "
             "for PDFs the offline ladder cannot read. Probed and "
             "endpoint-checked ONCE before the batch starts; a remote/paid "
             "endpoint additionally requires OCR_REMOTE_OPT_IN "
             "(see README.md).",
    )
    args = ap.parse_args()

    root = Path(args.path)
    if root.is_dir():
        files = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".md", ".pdf"))
    else:
        files = [root]
    if not files:
        print(f"no .md/.pdf statements found under {root}", file=sys.stderr)
        sys.exit(1)

    # OQ7 / F-4(a): this CLI used to call `parse_statement` with the defaults
    # (`allow_visual_ocr=True`) — every PDF without native text went straight
    # to the env-configured endpoint with its pixels. Offline-only is now the
    # default; `--visual` probes ONCE up front (as `ocr.availability`'s own
    # docstring requires for a long batch) rather than per file.
    allow_visual_ocr = False
    if args.visual:
        from ocr.availability import probe_visual_ocr

        status = probe_visual_ocr()
        if not status.usable:
            print(f"error: {status.message()}", file=sys.stderr)
            sys.exit(1)
        allow_visual_ocr = True

    run_id = new_run_id()
    sink = open_jsonl_sink(args.telemetry, run_id)
    seen_hashes: set[str] = set()

    rows = []
    for path in files:
        print(f"analyzing {path.name} ...", file=sys.stderr, flush=True)
        # Telemetry is write-only side-band: every failure below is swallowed
        # by the sink, and nothing here feeds back into the analysis.
        timer = StageTimer()
        collector = DispatchCollector()
        markdown = doc = profile = None
        byte_size = 0
        try:
            with timer.time("read"):
                markdown, doc, profile, byte_size = _read_source(
                    path, allow_visual_ocr=allow_visual_ocr
                )
            with timer.time("analysis"):
                # The intake object's page list when this input was a PDF, and
                # nothing when it was already-extracted markdown — a .md file
                # carries no evidence of how many sheets its source had, and
                # `assess_document_integrity` fail-closes on that silence rather
                # than re-splitting the text (W3 §PIPEFIX P4b.1). This CLI
                # publishes an outcome class derived from these flags into its
                # telemetry JSONL, so it is a production caller (W3 §WIRING W4).
                analysed = analyze_document(
                    markdown, on_dispatch=collector,
                    sheets=doc.pages if doc is not None else None,
                )
            # One CSV row per ACCOUNT, in printed order: a sheet that printed
            # one row per document would publish one account of several and
            # drop the rest without saying so.
            rows.extend(_row(path, account) for account in analysed.accounts)
            _emit(sink, run_id, path, markdown, doc, profile, byte_size,
                  collector, timer, seen_hashes, document=analysed)
        except Exception as e:  # keep going; record the failure in its row
            traceback.print_exc()
            # MINOR-8 (PHASE2_P20SEAM_REVIEW.md): the CSV cell carries the
            # exception CLASS NAME only, never `str(e)` — this branch gained
            # a new raise path in this card (`ocr.config.ProvenanceTokenError`
            # on a hostile filename), and that exception's message quotes the
            # whole `source_file` (`ocr/document.py`'s
            # `ProvenanceTokenError` docstring). `traceback.print_exc()`
            # above still prints the full traceback to the CONSOLE for a
            # developer debugging a run; only the durable CSV artifact is
            # reduced to the class name, matching every other class-name-only
            # sink in this tree (`telemetry.record`'s `error_type`,
            # `webapp/worker.py::_stage_failure`).
            rows.append({**{k: "" for k in FIELDS}, "file": path.name,
                         "needs_review": "REVIEW", "error": type(e).__name__})
            _emit(sink, run_id, path, markdown, doc, profile, byte_size,
                  collector, timer, seen_hashes, error_type=type(e).__name__)

    out = open(args.out, "w", newline="", encoding="utf-8") if args.out else sys.stdout
    w = csv.DictWriter(out, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    if args.out:
        out.close()
        need = sum(1 for r in rows if r["needs_review"])
        print(f"\nWrote {len(rows)} rows to {args.out}  ({need} flagged for review)", file=sys.stderr)
    sink.close()
    written = getattr(sink, "written", 0)
    if written:
        print(
            f"Telemetry: {written} records -> {sink.path}\n"
            f"  python -m telemetry.report --jsonl {sink.path}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()

"""Batch-analyze a folder of bank statements into one triage CSV.

Accepts OCR'd markdown files (fast) and/or PDFs (OCR'd first via the running OCR
server — set OCR_BASE_URL/OCR_API_KEY). One row per statement with the key
underwriting figures and a needs_review flag so clean statements flow through and
only the questionable ones get human eyes.

Usage:
  .venv/bin/python batch.py output/ --out triage.csv          # a folder of .md
  OCR_BASE_URL=http://localhost:8000/v1 OCR_API_KEY=EMPTY \\
      .venv/bin/python batch.py BankStatements/ --out triage.csv   # PDFs (OCR+analyze)

`--zelle-true-revenue {yes,no}` is the owner's "Mark Zelle Payments as True
Revenue" (the underwriter's Q3, amended 2026-10-06), yes by default as on the
Settings page: each row reads that Zelle reading. The CLI reads no webapp
setting.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import sys
import traceback
from pathlib import Path

from analysis import zelle_view
from analysis.active_positions import statement_active_positions
from analysis.pipeline import analyze_document, DocumentReport, Report
from analysis.revenue_view import apply_revenue_view, revenue_flags, withholding_basis_unestablished
from analysis.serialization import document_report_to_dict
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
    "total_posted_credits", "true_revenue_total", "counted_flagged_total", "excluded_pending_review_total",
    "verified_revenue_total", "verified_revenue_count",
    "unverified_deposit_total", "unverified_deposit_count", "non_revenue_total",
    "non_revenue_count",
    # Audit round 3, R3-B24 (R3-16; standard G7, P22): the counted credits whose source the statement does not prove
    # that are $10,000 or more and over 25% of True, information only (needs_review does not read them).
    "large_unsourced_deposit_count", "large_unsourced_deposit_total",
    # The owner's amendment of 2026-10-06 to the underwriter's Q3 (R2-OW17): the reading shown and its Zelle figures,
    # a fixed header in both modes.
    "zelle_true_revenue", "zelle_deposit_total", "zelle_in_true_revenue_total",
    # Audit round 2, R2-B16 (R52): the four-tier identity under its own name (was `revenue_reconciles`), then whether
    # the statement's revenue is Balanced (its ledger reconciles and its revenue is established) and the two flags.
    "maximum_revenue", "revenue_tiers_sum_to_posted",
    "revenue_reconciliation_delta", "revenue_balanced", "revenue_established", "verified_revenue_established",
    "cash_flow", "lender_credits", "lender_debits",
    "lender_debit_count", "returned_funder_payment_count", "returned_funder_payment_total",
    "lenders_detected", "potential_lenders_detected",
    "potential_lender_debit_count", "potential_lender_debit_total",
    # Audit round 3, R3-B22 (R3-68; the owner's Q7): the basis the withholding columns divide by, which each run reads
    # from WITHHOLDING_DENOMINATOR_MODE, written on every account row.
    "insurance_count", "insurance_total", "withholding_denominator_mode", "withholding_denominator_label",
    "withholding_numerator",
    "withholding_denominator", "withholding_rate", "potential_withholding_numerator",
    "potential_withholding_denominator", "potential_withholding_exposure",
    "potential_withholding_review_required", "pos_count", "pos_credit_count",
    "atm_withdrawal_count", "loan_count",
    "debit_coverage", "nsf", "mca_funders", "flagged_positions", "recurring_debit_groups",
    # The owner's request of 2026-10-06 (lender payment changes; R2-OW18): the statement's items by kind, and each as
    # kind:lender_label (information only).
    "lender_payment_decreases", "lender_payment_increases", "lender_payment_cadence_changes",
    "lender_payment_new_streams", "lender_payment_pauses", "lender_payment_possible_stops",
    # Audit round 3, R3-B05 (the owner's answer of 2026-10-07 to R3-25, "Add a 'Caught up' line"): the catch-ups.
    "lender_payment_catch_ups", "lender_payment_changes",
    # The owner's request of 2026-10-10 (active positions by month): the statement's active positions over its
    # printed period, the confirmed lenders' and, apart, the potential lenders' (information only).
    "active_positions", "possible_positions",
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


def _payment_change_columns(items: list[dict]) -> dict:
    """The owner's request of 2026-10-06 (R2-OW18, I2): the lender payment change columns of one account (eight since
    audit round 3, R3-B05: the catch-ups)."""
    def count(kind: str) -> int:
        return sum(1 for item in items if item.get("kind") == kind)

    def named(item: dict) -> str:
        possible = " (possible)" if item.get("schedule_confirmed") is False else ""
        potential = " (potential)" if item.get("lender_state") == "potential" else ""
        return f"{item.get('kind')}:{item.get('lender_label') or item.get('lender')}{possible}{potential}"

    return {
        "lender_payment_decreases": count("decrease"),
        "lender_payment_increases": count("increase"),
        "lender_payment_cadence_changes": count("cadence_change"),
        "lender_payment_new_streams": count("new_stream"),
        "lender_payment_pauses": count("pause"),
        "lender_payment_possible_stops": sum(1 for item in items
                                             if item.get("kind") == "stop" and item.get("stop_confirmed") is not True),
        "lender_payment_catch_ups": count("catch_up"),
        "lender_payment_changes": "; ".join(named(item) for item in items),
    }


def _row(path: Path, stored: Report, zelle_true_revenue: bool = True) -> dict:
    # R2-OW17: the Zelle reading asked for: the counted one (`Report.zelle_counted`) under Yes where the statement has
    # one, else the stored Report.
    report = stored.zelle_counted if zelle_true_revenue and stored.zelle_counted is not None else stored
    s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
    zelle = zelle_view.record_zelle_figures(stored.classifications, report.classifications)
    zelle_parts = zelle_view.figure_parts(zelle) if zelle is not None else {"in_true": 0.0}
    # Audit round 2, R2-B16 (R52; true revenue spec §10.4): the account's revenue flags in the reading shown, from its
    # serialized payload (the flags the dashboard and the downloads read), published through the document entry point
    # as a document of its one account (RULE S: that account's payload; the L1-S3 seam rule).
    payload = document_report_to_dict(DocumentReport(accounts=[report]))
    verified_established, established = revenue_flags(payload)
    # Audit round 3, R3-B24 (R3-16; §13): the account served once (analysis/revenue_view.py apply_revenue_view, in the
    # reading shown) for its large unsourced deposits; the flag is served only where the revenue is established.
    served = apply_revenue_view(payload).get("metrics") or {}
    # A statement needs human review when the bank's own summary doesn't reconcile
    # (mis-extracted or internally inconsistent) — the figures can't be trusted —
    # when its revenue gate is set (5.6, T7: a direction conflict, or held credits
    # of ten percent or more of its posted credits or of True plus held), or (R52)
    # when its revenue is not established: its captured credits are not the money
    # the bank's total counts. The four-tier identity holds by construction on every
    # analysis (analysis/metrics.py raises otherwise), so it is no term of its own.
    needs_review = (
        report.quality.corporate_use == "manual_review_required"
        or m.revenue_review_required
        or not established
    )

    def established_figure(value: float, shown: bool) -> str:
        # R52 (audit B11's I51 on the CSV): a figure the flags do not establish is an empty cell, as in the downloads.
        return f"{value:.2f}" if shown else ""

    # The final review of round 2, F1 (§10.4, §11): no rate and no basis where the basis the withholding mode divides
    # by is not established (the downloads' rule); the legacy basis is written as before.
    basis_shown = not withholding_basis_unestablished(
        m.withholding_denominator_mode, verified_established=verified_established, established=established)

    def rate(value: float | None) -> str:
        return f"{value:.2f}" if value is not None and basis_shown else ""
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
        # 5.6 (true revenue spec §5.1): True revenue and its counted and held parts; R52: empty where not established.
        "true_revenue_total": established_figure(m.true_revenue_total, established),
        "counted_flagged_total": established_figure(m.counted_flagged_total, established),
        "excluded_pending_review_total": established_figure(m.excluded_pending_review_total, established),
        "verified_revenue_total": established_figure(m.verified_revenue_total, verified_established),
        "verified_revenue_count": m.verified_revenue_count,
        "unverified_deposit_total": established_figure(m.unverified_deposit_total, established),
        "unverified_deposit_count": m.unverified_deposit_count,
        "non_revenue_total": f"{m.non_revenue_total:.2f}",
        "non_revenue_count": m.non_revenue_count,
        # R3-B24 (R3-16): 0 and 0.00 where none is flagged, both empty where the revenue is not established (R52).
        "large_unsourced_deposit_count": int(served.get("large_unsourced_deposit_count") or 0) if established else "",
        "large_unsourced_deposit_total": established_figure(
            float(served.get("large_unsourced_deposit_total") or 0.0), established),
        "zelle_true_revenue": "yes" if zelle_true_revenue else "no",
        "zelle_deposit_total": f"{zelle['total'] if zelle is not None else 0.0:.2f}",
        # Audit round 3, R3-B20 (R3-48; §10.4's I51): the Zelle part of True is empty where True is; the Zelle total
        # stays (the captured Zelle rows, as total_posted_credits is kept).
        "zelle_in_true_revenue_total": established_figure(zelle_parts["in_true"], established),
        "maximum_revenue": established_figure(m.maximum_revenue, established),
        "revenue_tiers_sum_to_posted": "yes" if m.revenue_tiers_sum_to_posted else "NO",
        "revenue_reconciliation_delta": f"{m.revenue_reconciliation_delta:.2f}",
        "revenue_balanced": "yes" if r.ok is True and established else "NO",
        "revenue_established": "yes" if established else "NO",
        "verified_revenue_established": "yes" if verified_established else "NO",
        "cash_flow": f"{m.cash_flow:.2f}",
        "lender_credits": f"{m.lender_credits:.2f}",
        "lender_debits": f"{m.lender_debits:.2f}",
        "lender_debit_count": m.lender_debit_count,
        # Owner ruling 2026-10-02 (the underwriter's Q5; R2-OW13): out of lender_debits, in withholding_numerator.
        "returned_funder_payment_count": m.returned_funder_payment_count,
        "returned_funder_payment_total": f"{m.returned_funder_payment_total:.2f}",
        "lenders_detected": m.lenders_detected,
        "potential_lenders_detected": m.potential_lenders_detected,
        "potential_lender_debit_count": m.potential_lender_debit_count,
        "potential_lender_debit_total": f"{m.potential_lender_debit_total:.2f}",
        "insurance_count": m.insurance_count,
        "insurance_total": f"{m.insurance_total:.2f}",
        # Audit round 3, R3-B22 (R3-68): the basis, written where it is not established too (the label says which basis
        # the empty cells belong to).
        "withholding_denominator_mode": m.withholding_denominator_mode,
        "withholding_denominator_label": m.withholding_denominator_label,
        "withholding_numerator": f"{m.withholding_numerator:.2f}",
        "withholding_denominator": established_figure(m.withholding_denominator, basis_shown),
        "withholding_rate": rate(m.withholding_rate),
        "potential_withholding_numerator": f"{m.potential_withholding_numerator:.2f}",
        "potential_withholding_denominator": established_figure(m.potential_withholding_denominator, basis_shown),
        "potential_withholding_exposure": rate(m.potential_withholding_exposure),
        "potential_withholding_review_required": m.potential_withholding_review_required,
        "pos_count": m.pos_count,
        "pos_credit_count": m.pos_credit_count,
        "atm_withdrawal_count": m.atm_withdrawal_count,
        "loan_count": m.loan_count,
        "debit_coverage": f"{r.debit_coverage:.0%}" if r.debit_coverage is not None else "",
        "nsf": m.effective_nsf_count,
        "mca_funders": "; ".join(fm.funder for fm in d.known_funders),
        # Spec §7: flagged obligations as group:payee, never lenders. Analysis
        # time only; the webapp's Settings never reach this CSV.
        "flagged_positions": "; ".join(f"{fp.group}:{fp.payee}" for fp in d.flagged_positions),
        "recurring_debit_groups": sum(1 for rc in d.recurring_debits if rc.cadence in ("daily", "weekly")),
        **_payment_change_columns(d.lender_payment_changes),
        **statement_active_positions(report.classifications, period_start=s.period_start, period_end=s.period_end,
                                     currency=s.currency),
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
    ap.add_argument("--zelle-true-revenue", choices=("yes", "no"), default="yes",
                    help="Mark Zelle Payments as True Revenue (default yes, the Settings default)")
    args = ap.parse_args()
    zelle_true_revenue = args.zelle_true_revenue == "yes"

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
            rows.extend(_row(path, account, zelle_true_revenue) for account in analysed.accounts)
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

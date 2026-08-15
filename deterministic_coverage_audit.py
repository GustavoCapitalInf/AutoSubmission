"""Audit deterministic parser coverage for statement PDFs.

This never falls back to Gemini. It can optionally use local Tesseract OCR for
image-only PDFs, then validates the extracted data with deterministic parsers and
reconciliation/quality gates.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from analyze import _json_safe
from analysis.pipeline import analyze_markdown
from ocr.document import StatementMarkdown
from ocr.local_tesseract import parse_local_tesseract
from ocr.native_text import (
    parse_native_desjardins,
    parse_native_first_citizens,
    parse_native_navy_federal,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
    parse_native_woodforest,
)


FIELDS = [
    "file",
    "folder",
    "native_status",
    "native_model",
    "pages",
    "chars",
    "deterministic_status",
    "parser_model",
    "bank",
    "account",
    "period_start",
    "period_end",
    "transactions",
    "reconciles",
    "summary_reconciles",
    "quality",
    "corporate_use",
    "integrity_risk",
    "integrity_flags",
    "integrity_notes",
    "quality_notes",
    "reconciliation_issues",
    "average_daily_balance",
    "adb_ok",
    "adb_validations",
    "adb_warnings",
    "pos_count",
    "pos_credit_count",
    "atm_withdrawal_count",
    "total_credits",
    "total_debits",
    "cash_flow",
    "nsf",
    "known_funders",
    "potential_lenders",
    "lender_debit_count",
    "lender_debits",
    "potential_lender_debit_count",
    "potential_lender_debit_total",
    "insurance_count",
    "insurance_total",
    "withholding_numerator",
    "withholding_denominator",
    "withholding_rate",
    "potential_withholding_numerator",
    "potential_withholding_denominator",
    "potential_withholding_exposure",
    "potential_withholding_review_required",
    "markdown",
    "json",
    "error",
]


def native_statement(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    return (
        parse_native_navy_federal(pdf_bytes, source_file=source_file)
        or parse_native_td_canada(pdf_bytes, source_file=source_file)
        or parse_native_wells_fargo(pdf_bytes, source_file=source_file)
        or parse_native_woodforest(pdf_bytes, source_file=source_file)
        or parse_native_desjardins(pdf_bytes, source_file=source_file)
        or parse_native_first_citizens(pdf_bytes, source_file=source_file)
        or parse_native_pdf_text(pdf_bytes, source_file=source_file)
    )


def _relative_folder(path: Path, root: Path) -> str:
    if root.is_file():
        return "."
    return str(path.parent.relative_to(root)) if path.parent != root else "."


def _summary(value: bool | None) -> str:
    return {True: "yes", False: "no", None: "n/a"}[value]


def audit_file(
    path: Path,
    root: Path,
    artifact_root: Path | None = None,
    index: int | None = None,
    *,
    use_local_ocr: bool = False,
) -> dict:
    base = {
        **{field: "" for field in FIELDS},
        "file": path.name,
        "folder": _relative_folder(path, root),
    }
    try:
        pdf_bytes = path.read_bytes()
        doc = native_statement(pdf_bytes, source_file=path.name)
        source_status = "native_text"
        if doc is None and use_local_ocr:
            doc = parse_local_tesseract(pdf_bytes, source_file=path.name)
            if doc is not None:
                source_status = "local_ocr"
        if doc is None:
            return {
                **base,
                "native_status": "no_native_text",
                "deterministic_status": "not_attempted",
                "quality": "needs_review",
                "corporate_use": "manual_review_required",
                "integrity_risk": "review",
                "integrity_flags": "text_unavailable",
                "integrity_notes": "native text unavailable and local OCR did not produce usable statement text",
                "quality_notes": "document cannot be processed deterministically from available text",
                "error": "native PDF text unavailable or too sparse",
            }

        markdown = doc.to_markdown()
        chars = sum(len(page.strip()) for page in doc.pages)
        markdown_path = ""
        json_path = ""
        if artifact_root is not None:
            stem = f"{index:03d}_{path.stem}" if index is not None else path.stem
            markdown_file = artifact_root / f"{stem}.md"
            markdown_file.write_text(markdown, encoding="utf-8")
            markdown_path = str(markdown_file)

        try:
            report = analyze_markdown(markdown, parse_mode="deterministic")
        except Exception as e:
            return {
                **base,
                "native_status": source_status,
                "native_model": doc.model,
                "pages": len(doc.pages),
                "chars": chars,
                "deterministic_status": "no_parser",
                "quality": "needs_review",
                "corporate_use": "manual_review_required",
                "integrity_risk": "review",
                "integrity_flags": "unsupported_statement_format",
                "integrity_notes": "no deterministic parser matched the extracted statement text",
                "quality_notes": "unsupported statement format requires manual review",
                "reconciliation_issues": str(e),
                "markdown": markdown_path,
                "error": str(e),
            }

        if artifact_root is not None:
            stem = f"{index:03d}_{path.stem}" if index is not None else path.stem
            json_file = artifact_root / f"{stem}.json"
            json_file.write_text(json.dumps(_json_safe(report), indent=2), encoding="utf-8")
            json_path = str(json_file)

        s, r, m, d = report.statement, report.reconciliation, report.metrics, report.detection
        adb = m.adb
        return {
            **base,
            "native_status": source_status,
            "native_model": doc.model,
            "pages": len(doc.pages),
            "chars": chars,
            "deterministic_status": "parsed",
            "parser_model": report.model_used,
            "bank": s.bank or "",
            "account": s.account_number or "",
            "period_start": s.period_start or "",
            "period_end": s.period_end or "",
            "transactions": len(s.transactions),
            "reconciles": "yes" if r.ok else "no",
            "summary_reconciles": _summary(r.summary_ok),
            "quality": report.quality.level,
            "corporate_use": report.quality.corporate_use,
            "integrity_risk": report.integrity.risk_level,
            "integrity_flags": "; ".join(report.integrity.flags),
            "integrity_notes": "; ".join(report.integrity.notes),
            "quality_notes": "; ".join(report.quality.notes or []),
            "reconciliation_issues": "; ".join(r.issues),
            "average_daily_balance": (
                f"{m.average_daily_balance:.2f}"
                if m.average_daily_balance is not None
                else ""
            ),
            "adb_ok": _summary(adb.ok if adb and adb.daily_balances else None),
            "adb_validations": "; ".join(
                f"{name}={_summary(passed)}"
                for name, passed in (adb.validations.items() if adb else [])
            ),
            "adb_warnings": "; ".join(adb.warnings if adb else []),
            "pos_count": m.pos_count,
            "pos_credit_count": m.pos_credit_count,
            "atm_withdrawal_count": m.atm_withdrawal_count,
            "total_credits": f"{m.effective_total_deposits:.2f}",
            "total_debits": f"{m.effective_total_withdrawals:.2f}",
            "cash_flow": f"{m.cash_flow:.2f}",
            "nsf": m.effective_nsf_count,
            "known_funders": "; ".join(match.funder for match in d.known_funders),
            "potential_lenders": "; ".join(match.funder for match in d.potential_lenders),
            "lender_debit_count": m.lender_debit_count,
            "lender_debits": f"{m.lender_debits:.2f}",
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
            "markdown": markdown_path,
            "json": json_path,
        }
    except Exception as e:
        return {**base, "native_status": "error", "deterministic_status": "error", "error": f"{type(e).__name__}: {e}"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Audit deterministic parser coverage without Gemini.")
    ap.add_argument("path", help="PDF file or folder of PDFs.")
    ap.add_argument("--out", default="output/deterministic_coverage.csv", help="CSV output path.")
    ap.add_argument("--artifacts", default="", help="Optional folder for native markdown and parsed JSON artifacts.")
    ap.add_argument("--limit", type=int, default=None, help="Only process the first N PDFs.")
    ap.add_argument(
        "--local-ocr",
        action="store_true",
        help="Fallback to local Tesseract OCR when native PDF text is unavailable.",
    )
    args = ap.parse_args()

    root = Path(args.path)
    files = [root] if root.is_file() else sorted(root.rglob("*.pdf"))
    if args.limit is not None:
        files = files[:args.limit]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    artifact_root = Path(args.artifacts) if args.artifacts else None
    if artifact_root is not None:
        artifact_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for idx, path in enumerate(files, start=1):
            print(f"[{idx}] {path}", flush=True)
            row = audit_file(
                path,
                root,
                artifact_root=artifact_root,
                index=idx,
                use_local_ocr=args.local_ocr,
            )
            writer.writerow(row)
            counts[row["deterministic_status"]] = counts.get(row["deterministic_status"], 0) + 1

    print(f"Wrote {len(files)} rows to {out}: {counts}")


if __name__ == "__main__":
    main()

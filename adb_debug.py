"""Print exactly how Average Daily Balance was calculated for a statement.

    python adb_debug.py "Bank Statements/Chase/Chase Apr.pdf"
    python adb_debug.py "Bank Statements/Chase" --summary
    python adb_debug.py extracted.md
    python adb_debug.py statement.json

Reads a statement PDF (native text, optionally local OCR), a pre-extracted
markdown file, or a statement JSON payload; runs the deterministic pipeline; and
dumps the day-by-day ledger, the validations, and the final arithmetic.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analysis.adb import compute_average_daily_balance
from analysis.pipeline import analyze_markdown
from analysis.schema import Statement
from ocr.document import StatementMarkdown
from ocr.local_tesseract import parse_local_tesseract
from ocr.native_text import (
    parse_native_desjardins,
    parse_native_pdf_text,
    parse_native_td_canada,
    parse_native_wells_fargo,
)

_PDF_SUFFIXES = {".pdf"}
_TEXT_SUFFIXES = {".md", ".markdown", ".txt"}


def _native_statement(pdf_bytes: bytes, source_file: str = "") -> StatementMarkdown | None:
    return (
        parse_native_td_canada(pdf_bytes, source_file=source_file)
        or parse_native_wells_fargo(pdf_bytes, source_file=source_file)
        or parse_native_desjardins(pdf_bytes, source_file=source_file)
        or parse_native_pdf_text(pdf_bytes, source_file=source_file)
    )


def _statement_from_path(path: Path, *, use_local_ocr: bool, parse_mode: str) -> Statement:
    suffix = path.suffix.lower()

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Accept either a bare Statement or a full analysis payload.
        return Statement.model_validate(payload.get("statement", payload))

    if suffix in _TEXT_SUFFIXES:
        markdown = path.read_text(encoding="utf-8", errors="replace")
    elif suffix in _PDF_SUFFIXES:
        doc = _native_statement(path.read_bytes(), source_file=path.name)
        if doc is None and use_local_ocr:
            doc = parse_local_tesseract(path.read_bytes(), source_file=path.name)
        if doc is None:
            raise RuntimeError(
                "no native PDF text available (image-only scan?); retry with --local-ocr"
            )
        markdown = doc.to_markdown()
    else:
        raise RuntimeError(f"unsupported file type: {path.suffix or path.name}")

    return analyze_markdown(markdown, parse_mode=parse_mode).statement


def _statement_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    allowed = _PDF_SUFFIXES | _TEXT_SUFFIXES | {".json"}
    return sorted(p for p in target.rglob("*") if p.is_file() and p.suffix.lower() in allowed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path, help="statement PDF, markdown, JSON, or a directory")
    parser.add_argument("--local-ocr", action="store_true", help="use local Tesseract for image-only PDFs")
    parser.add_argument(
        "--parse-mode", default="auto", choices=("auto", "deterministic"),
        help="deterministic refuses to fall back to the LLM extractor",
    )
    parser.add_argument("--summary", action="store_true", help="one line per statement instead of the full trace")
    parser.add_argument("--json", action="store_true", help="emit the ADB result as JSON")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"not found: {args.path}", file=sys.stderr)
        return 2

    files = _statement_files(args.path)
    if not files:
        print(f"no statement files under {args.path}", file=sys.stderr)
        return 2

    failures = 0
    for path in files:
        try:
            stmt = _statement_from_path(path, use_local_ocr=args.local_ocr, parse_mode=args.parse_mode)
            result = compute_average_daily_balance(stmt)
        except Exception as exc:  # a bad file must not abort a directory sweep
            failures += 1
            print(f"{path.name}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
            continue

        if not result.ok:
            failures += 1

        if args.json:
            from dataclasses import asdict

            print(json.dumps({"file": path.name, **asdict(result)}, indent=2))
        elif args.summary:
            adb = "n/a" if result.average_daily_balance is None else f"{result.average_daily_balance:>14,.2f}"
            days = result.calendar_day_count if result.calendar_day_count is not None else "?"
            flag = "ok  " if result.ok else "WARN"
            print(f"{flag} {adb}  {str(days):>3}d  {result.period_start}..{result.period_end}  {path.name}")
            for warning in result.warnings:
                print(f"       - {warning}")
        else:
            print(f"\n{'#' * 60}\n# {path.name}\n{'#' * 60}")
            print(result.debug_report())

    if len(files) > 1:
        print(f"\n{len(files) - failures}/{len(files)} statements produced a fully validated ADB", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

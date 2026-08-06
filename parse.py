from __future__ import annotations
import argparse
import sys
from pathlib import Path
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bank statement PDF -> Markdown via Unlimited-OCR.")
    ap.add_argument("pdf", help="Path to the statement PDF")
    ap.add_argument("--out", help="Write output here instead of stdout")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--model", default=None, help="Override the model name")
    ap.add_argument("--html", action="store_true",
                    help="Render as a styled HTML page instead of raw Markdown")
    args = ap.parse_args(argv)

    path = Path(args.pdf)
    try:
        pdf_bytes = path.read_bytes()
    except OSError as e:
        print(f"error: cannot read PDF: {e}", file=sys.stderr)
        return 2
    try:
        # O-1: parse_statement IS the single profile-driven intake ladder
        # (ocr/inspect.py preflight -> native -> visual OCR). The CLI keeps
        # its historical capabilities: allow_local_ocr stays at its False
        # default, so no tesseract rung is silently gained here.
        doc = parse_statement(pdf_bytes, source_file=path.name, dpi=args.dpi, model=args.model)
    except Exception as e:
        print(f"error: failed to parse statement: {e}", file=sys.stderr)
        return 1

    text = doc.to_markdown()
    if args.html:
        text = markdown_to_html(text, title=path.name)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

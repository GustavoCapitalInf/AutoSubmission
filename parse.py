from __future__ import annotations
import argparse
import sys
from pathlib import Path
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html

#: The no-text refusal (model-code removal, slice S2: declared). This CLI reads
#: a PDF's native text only; it has no OCR rung (local Tesseract is the web
#: app's), and the visual OCR rung `--visual` used to allow is gone.
NO_NATIVE_TEXT = "error: no native PDF text could be extracted; this CLI reads native PDF text only"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bank statement PDF -> Markdown via native text extraction.")
    ap.add_argument("pdf", help="Path to the statement PDF")
    ap.add_argument("--out", help="Write output here instead of stdout")
    ap.add_argument("--dpi", type=int, default=300)
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
        # (ocr/inspect.py preflight -> native text). The CLI keeps its
        # historical capabilities: allow_local_ocr stays at its False
        # default, so no tesseract rung is silently gained here.
        doc = parse_statement(pdf_bytes, source_file=path.name, dpi=args.dpi)
    except Exception as e:
        print(f"error: failed to parse statement: {e}", file=sys.stderr)
        return 1

    if doc is None:
        # The offline ladder read nothing: fail closed with a clear message
        # rather than crash on `doc.to_markdown()`.
        print(NO_NATIVE_TEXT, file=sys.stderr)
        return 1

    text = doc.to_markdown()
    if args.html:
        text = markdown_to_html(text, title=path.name)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        # Audit 2026-10-13, EXP-5: UTF-8, as --out writes. A redirected stdout
        # on Windows is cp1252, which cannot encode the ligatures and
        # private-use glyphs native statement text carries (UnicodeEncodeError,
        # an empty file). A stream without reconfigure is written as it is.
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from ocr.pipeline import parse_statement
from ocr.render import markdown_to_html


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bank statement PDF -> Markdown via native/local text extraction.")
    ap.add_argument("pdf", help="Path to the statement PDF")
    ap.add_argument("--out", help="Write output here instead of stdout")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--model", default=None, help="Override the model name")
    ap.add_argument("--html", action="store_true",
                    help="Render as a styled HTML page instead of raw Markdown")
    ap.add_argument(
        "--visual", action="store_true",
        help="Allow the visual-OCR rung (local $0 server only, by default) "
             "when the offline ladder cannot read the document. Probed and "
             "endpoint-checked before anything is sent; a remote/paid "
             "endpoint additionally requires OCR_REMOTE_OPT_IN "
             "(see README.md).",
    )
    args = ap.parse_args(argv)

    path = Path(args.pdf)
    try:
        pdf_bytes = path.read_bytes()
    except OSError as e:
        print(f"error: cannot read PDF: {e}", file=sys.stderr)
        return 2

    # OQ7 / F-4(a): this CLI used to default to `allow_visual_ocr=True` — any
    # document without native text went straight to the env-configured
    # endpoint with its pixels, no probe, no confirmation. Offline-only is now
    # the default; `--visual` is the explicit, probed opt-in.
    allow_visual_ocr = False
    if args.visual:
        from ocr.availability import probe_visual_ocr

        status = probe_visual_ocr()
        if not status.usable:
            print(f"error: {status.message()}", file=sys.stderr)
            return 3
        allow_visual_ocr = True

    try:
        # O-1: parse_statement IS the single profile-driven intake ladder
        # (ocr/inspect.py preflight -> native -> visual OCR). The CLI keeps
        # its historical capabilities: allow_local_ocr stays at its False
        # default, so no tesseract rung is silently gained here.
        doc = parse_statement(pdf_bytes, source_file=path.name, dpi=args.dpi, model=args.model,
                              allow_visual_ocr=allow_visual_ocr)
    except Exception as e:
        print(f"error: failed to parse statement: {e}", file=sys.stderr)
        return 1

    if doc is None:
        # `allow_visual_ocr=False` (the new default) means the offline
        # ladder can now return None instead of escalating — see
        # `parse_statement`'s own docstring. Fail closed with a clear
        # message rather than crash on `doc.to_markdown()`.
        print(
            "error: no native or local text could be extracted; rerun with "
            "--visual to allow the local $0 OCR rung",
            file=sys.stderr,
        )
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

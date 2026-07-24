"""Dev-only: OCR one representative statement per bank folder for quality review.

Picks the first PDF (alphabetically) in each leaf folder under BankStatements/,
OCRs it, and writes output/<label>.md + .html. Logs page count, timing, and any
errors to output/_sweep_log.txt so we can triage which banks read badly.
"""
from __future__ import annotations
import sys
import time
import traceback
from pathlib import Path

from ocr.pipeline import parse_statement
from ocr.rasterize import pdf_page_count
from ocr.render import markdown_to_html

ROOT = Path("BankStatements")
OUT = Path("output")
OUT.mkdir(exist_ok=True)
MAX_PAGES = 15  # skip very large statements (huge page counts take too long)


def leaf_dirs_with_pdfs():
    seen = {}
    for pdf in sorted(ROOT.rglob("*.pdf")):
        seen.setdefault(pdf.parent, pdf)  # first PDF per folder
    return seen


def label_for(folder: Path) -> str:
    rel = folder.relative_to(ROOT)
    return "_".join(rel.parts).replace(" ", "")


def main():
    only = sys.argv[1:]  # optional: substrings to filter bank folders
    picks = leaf_dirs_with_pdfs()
    log = OUT / "_sweep_log.txt"
    with open(log, "w", encoding="utf-8") as lf:
        for folder, pdf in picks.items():
            label = label_for(folder)
            if only and not any(o.lower() in label.lower() for o in only):
                continue
            line = f"{label:24s} <- {pdf.name}"
            try:
                pages = pdf_page_count(pdf.read_bytes())
                if pages > MAX_PAGES:
                    msg = f"SKIP {line}  ({pages}pg > {MAX_PAGES})"
                    print(msg, flush=True); lf.write(msg + "\n"); lf.flush()
                    continue
                t = time.time()
                doc = parse_statement(pdf.read_bytes(), source_file=pdf.name)
                dt = time.time() - t
                md = doc.to_markdown()
                (OUT / f"{label}.md").write_text(md, encoding="utf-8")
                (OUT / f"{label}.html").write_text(
                    markdown_to_html(md, title=f"{label} — {pdf.name}"), encoding="utf-8")
                msg = f"OK   {line}  ({len(doc.pages)}pg, {dt:.0f}s, {len(md)} chars)"
            except Exception as e:
                traceback.print_exc()
                msg = f"FAIL {line}  -> {type(e).__name__}: {e}"
            print(msg, flush=True)
            lf.write(msg + "\n"); lf.flush()


if __name__ == "__main__":
    main()

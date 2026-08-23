"""How many documents' native text layers weld a printed column, and where.

W3 §DESCCOLS' census, committed BEFORE any code change so the numbers that
section reports are re-derivable rather than remembered. It answers the
question DESC-ATTRIB's residue posed: the flattened text layer welds the
merchant column on the core-processor complex, and nobody had measured how
wide that class is.

    python -m tools.desccols_census --rows <run>/rows.csv \
        --corpus "<checkout>/Bank Statements" [--start 0 --end 3380] \
        [--out census.json]

WHAT IS MEASURED, defined on the geometry rather than on the flattened text.
`ocr/native_text.py::_native_pages` reads MuPDF BLOCKS and joins the lines
INSIDE a block with a single space. A block is a MuPDF grouping, not a printed
row, so when one block's lines are printed on several rows that join welds
tokens from different rows into one line of text — and the boundary is then
unrecoverable from the text, which is the whole of the DESC-ATTRIB harm.

* a **band** is the set of printed lines sharing a row of the page. Membership
  is by vertical OVERLAP of the printed line boxes (at least half of the
  shorter box), not by a point tolerance: a tolerance is a constant nobody can
  justify across type sizes, and an overlap test is scale-free;
* a **welded line** is a line of today's flattened text whose source lines come
  from more than one band. It is the defect, counted exactly;
* an **amount-bearing welded line** is a welded line carrying a money token —
  the class that can reach a ledger reader, and the card's own census metric;
* **interleaved blocks** are two blocks whose lines alternate down the page
  (each has a line strictly inside the other's vertical span). That is the
  signature of the two-stream flush specifically, as opposed to an ordinary
  multi-line paragraph, which welds its own lines and nobody else's.

READ-ONLY and $0: the PDFs are opened read-only from the corpus by direct file
path, no artifact store and no sqlite index is opened, and no model is called.

**It prints no document text and no figure.** Every field of the output is a
count, a class or a `content_sha256`, which is the same contract as the sweep
beside it.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path

#: A printed money cell, in the shared money grammar's plainest form. Used only
#: to CLASS a welded line as amount-bearing; nothing is read from it.
MONEY = re.compile(r"\d[\d,]*\.\d{2}")


def page_lines(page) -> list[tuple[int, float, float, float, float, str]]:
    """`(block, y0, y1, x0, x1, text)` for every printed line, in MuPDF order."""
    out = []
    for index, block in enumerate(page.get_text("dict").get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if not text.strip():
                continue
            x0, y0, x1, y1 = line["bbox"]
            out.append((index, y0, y1, x0, x1, text.strip()))
    return out


def bands_of(lines) -> list[int]:
    """The band index of each line, bands numbered down the page.

    Two lines share a band when their printed boxes overlap vertically by at
    least half the shorter box. Membership is tested against the band's own
    extent, which only ever narrows to the lines already in it, so a band
    cannot chain into the next row through one tall outlier.
    """
    order = sorted(range(len(lines)), key=lambda i: (lines[i][1], lines[i][3]))
    band_of = [0] * len(lines)
    top = bottom = None
    index = -1
    for position in order:
        _block, y0, y1, _x0, _x1, _text = lines[position]
        if top is None:
            index, top, bottom = index + 1, y0, y1
        else:
            overlap = min(bottom, y1) - max(top, y0)
            if overlap < 0.5 * min(bottom - top, y1 - y0):
                index, top, bottom = index + 1, y0, y1
            else:
                top, bottom = max(top, y0), min(bottom, y1)
        band_of[position] = index
    return band_of


def measure_page(page) -> dict:
    """The weld counts for one page."""
    lines = page_lines(page)
    empty = {"lines": 0, "bands": 0, "blocks": 0, "welded_blocks": 0,
             "welded_lines": 0, "amount_welded_lines": 0, "interleaved_pairs": 0}
    if not lines:
        return empty
    band_of = bands_of(lines)
    blocks: dict[int, list[int]] = {}
    for position, line in enumerate(lines):
        blocks.setdefault(line[0], []).append(position)

    welded_blocks = welded_lines = amount_welded = 0
    for positions in blocks.values():
        if len({band_of[p] for p in positions}) > 1:
            welded_blocks += 1
            welded_lines += 1  # the block IS one line of today's flattened text
            if any(MONEY.search(lines[p][5]) for p in positions):
                amount_welded += 1

    spans = {block: (min(band_of[p] for p in ps), max(band_of[p] for p in ps))
             for block, ps in blocks.items()}
    members = {block: {band_of[p] for p in ps} for block, ps in blocks.items()}
    interleaved = 0
    keys = sorted(spans)
    for position, left in enumerate(keys):
        low, high = spans[left]
        for right in keys[position + 1:]:
            other_low, other_high = spans[right]
            if any(low < band < high for band in members[right]) and \
                    any(other_low < band < other_high for band in members[left]):
                interleaved += 1
    return {"lines": len(lines), "bands": max(band_of) + 1, "blocks": len(blocks),
            "welded_blocks": welded_blocks, "welded_lines": welded_lines,
            "amount_welded_lines": amount_welded, "interleaved_pairs": interleaved}


def measure_document(path: Path) -> dict | None:
    """The weld counts for one PDF, or None when it holds no native text."""
    import fitz

    try:
        document = fitz.open(str(path))
    except Exception:
        return None
    try:
        try:
            texts = [page.get_text("text") for page in document]
        except Exception:
            return None
        # `parse_native_pdf_text`'s own quorum, so the census population is the
        # documents the generic rung actually claims.
        chars = sum(len(text.strip()) for text in texts)
        with_text = sum(1 for text in texts if len(text.strip()) >= 200)
        if chars < 500 or with_text < max(1, len(texts) // 2):
            return None
        total = {"pages": len(texts), "lines": 0, "bands": 0, "blocks": 0,
                 "welded_blocks": 0, "welded_lines": 0, "amount_welded_lines": 0,
                 "interleaved_pairs": 0}
        try:
            for page in document:
                for key, value in measure_page(page).items():
                    total[key] += value
        except Exception:
            return None
        return total
    finally:
        try:
            document.close()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=10 ** 9)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    paths: dict[str, str] = {}
    with args.rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = row["content_sha256"]
            if sha and sha not in paths:
                paths[sha] = row["relative_path"]

    began = time.time()
    records: dict[str, dict] = {}
    counts = {"documents": 0, "no_native_text": 0, "missing": 0,
              "clean": 0, "welded": 0, "amount_welded": 0}
    for sha in sorted(paths)[args.start:args.end]:
        path = args.corpus / paths[sha]
        if not path.exists():
            counts["missing"] += 1
            continue
        counts["documents"] += 1
        measured = measure_document(path)
        if measured is None:
            counts["no_native_text"] += 1
            continue
        records[sha] = measured
        if measured["welded_lines"]:
            counts["welded"] += 1
            if measured["amount_welded_lines"]:
                counts["amount_welded"] += 1
        else:
            counts["clean"] += 1

    report = {"counts": counts, "seconds": round(time.time() - began, 1),
              "documents": records}
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(counts, sort_keys=True))
    print(f"seconds={report['seconds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

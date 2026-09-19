"""Render the silver dataset's page images ON the training host from the source PDFs (R17).

The workstation's link to a rented host can be far too slow for 5 GB of JPEGs, while the source PDFs are a
tenth of that. This script rebuilds `images/<sha>/<page>.jpg` from `pdfs/<sha>.pdf` with the harness renderer
(same long edge and JPEG quality) and compares every image's SHA-256 with the hash the local build recorded
in the JSONL. Byte-identical pages keep their lines; a page whose bytes differ (a different PDFium build) is
rewritten with the host hash and counted, so the training receipt binds what was actually trained on.

    /venv/main/bin/python vlm_render_silver.py --dataset /workspace/silver-02 --long-edge 1540 --quality 90
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vlm.render import render_document  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vlm_render_silver")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--long-edge", type=int, default=1540)
    parser.add_argument("--quality", type=int, default=90)
    args = parser.parse_args(argv)
    dataset = Path(args.dataset)
    counts = {"documents": 0, "pages": 0, "identical": 0, "rewritten": 0, "missing_pdf": 0, "page_count_mismatch": 0}
    for split in ("train", "validation"):
        path = dataset / f"{split}.jsonl"
        if not path.is_file():
            continue
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        by_sha: dict[str, list[dict]] = {}
        for line in lines:
            by_sha.setdefault(line["sha"], []).append(line)
        out_lines = []
        for sha, doc_lines in by_sha.items():
            pdf = dataset / "pdfs" / f"{sha}.pdf"
            if not pdf.is_file():
                counts["missing_pdf"] += 1
                continue
            pages = render_document(pdf.read_bytes(), long_edge=args.long_edge, quality=args.quality)
            if len(pages) != doc_lines[0]["page_total"]:
                counts["page_count_mismatch"] += 1
                continue
            counts["documents"] += 1
            (dataset / "images" / sha).mkdir(parents=True, exist_ok=True)
            for line in sorted(doc_lines, key=lambda d: d["page"]):
                page = pages[line["page"]]
                image_path = dataset / line["image"]
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(page.jpeg)
                counts["pages"] += 1
                if page.jpeg_sha256 == line["image_sha256"]:
                    counts["identical"] += 1
                else:
                    counts["rewritten"] += 1
                    line["image_sha256_local_build"] = line["image_sha256"]
                    line["image_sha256"] = page.jpeg_sha256
                out_lines.append(line)
        path.write_text("".join(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n" for line in out_lines), encoding="utf-8")
    receipt = {"render": {"long_edge": args.long_edge, "jpeg_quality": args.quality}, "counts": counts,
               "jsonl_sha256": {name: hashlib.sha256((dataset / f"{name}.jsonl").read_bytes()).hexdigest()
                                for name in ("train", "validation") if (dataset / f"{name}.jsonl").is_file()}}
    (dataset / "host-render-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt))
    return 0 if counts["documents"] and not counts["missing_pdf"] and not counts["page_count_mismatch"] else 1


if __name__ == "__main__":
    sys.exit(main())

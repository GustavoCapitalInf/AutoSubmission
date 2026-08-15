"""Rebuild the committed OCR artifacts the corpus gate reads.

This is a maintenance tool, not part of the gate. It runs a live local Tesseract
pass over every corpus PDF that has no native text and writes the resulting
markdown into ``tests/corpus_cache``, keyed by the SHA-256 of the source PDF.

It does not regenerate the audit truth set. ``docs/adb-audit-results.csv`` and
``docs/balance-metrics-audit-results.csv`` are never written here; after a
rebuild the gate must still reproduce them exactly, which is what proves the new
artifacts are faithful.

    python build_corpus_cache.py            # rebuild, refusing any drift
    python build_corpus_cache.py --allow-drift

Requires the ``tesseract`` binary. Never run in CI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from corpus_artifacts import MANIFEST_NAME, sha256_hex
from ocr.local_tesseract import parse_local_tesseract
# The production native-text ladder itself — see
# `ocr/native_text.py::native_statement`. The cache is built from exactly the
# bytes production reads because it calls the same function, not a copy of it.
from ocr.native_text import native_statement as native_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="Bank Statements")
    parser.add_argument("--cache", default="tests/corpus_cache")
    parser.add_argument(
        "--allow-drift",
        action="store_true",
        help="Overwrite an artifact whose OCR output no longer matches the committed one.",
    )
    args = parser.parse_args()

    corpus = Path(args.corpus)
    cache = Path(args.cache)
    (cache / "ocr").mkdir(parents=True, exist_ok=True)

    artifacts: list[dict[str, str]] = []
    drifted: list[str] = []
    for index, path in enumerate(sorted(corpus.rglob("*.pdf")), start=1):
        pdf_bytes = path.read_bytes()
        if native_document(pdf_bytes, path.name) is not None:
            continue
        print(f"[{index}] OCR {path}", flush=True)
        document = parse_local_tesseract(pdf_bytes, source_file=path.name)
        if document is None:
            raise SystemExit(f"local Tesseract produced no usable text for {path}")
        markdown = document.to_markdown()
        pdf_digest = sha256_hex(pdf_bytes)
        artifact = cache / "ocr" / f"{pdf_digest}.md"
        if artifact.exists() and artifact.read_text(encoding="utf-8") != markdown:
            drifted.append(path.as_posix())
            if not args.allow_drift:
                continue
        artifact.write_text(markdown, encoding="utf-8", newline="\n")
        artifacts.append(
            {
                "statement": path.name,
                "path": path.relative_to(corpus).as_posix(),
                "pdf_sha256": pdf_digest,
                "artifact": f"ocr/{pdf_digest}.md",
                "artifact_sha256": sha256_hex(markdown.encode("utf-8")),
                "ocr_model": document.model,
            }
        )

    if drifted and not args.allow_drift:
        raise SystemExit(
            "local OCR output differs from the committed artifacts for:\n  "
            + "\n  ".join(drifted)
            + "\nThis Tesseract install does not reproduce the audited source text. "
              "Re-run with --allow-drift only after confirming the gate still "
              "reproduces both audit CSVs."
        )

    manifest = {
        "description": (
            "Committed OCR source text for the image-only corpus statements, so the "
            "corpus gate runs offline and deterministically. Keyed by the SHA-256 of "
            "the source PDF."
        ),
        "generator": "build_corpus_cache.py",
        "ocr": "ocr.local_tesseract.parse_local_tesseract (dpi=200, tesseract --psm 6)",
        "artifacts": sorted(artifacts, key=lambda entry: entry["path"]),
    }
    (cache / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Wrote {len(artifacts)} artifacts to {cache}")


if __name__ == "__main__":
    main()

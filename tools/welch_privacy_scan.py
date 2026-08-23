"""Does anything this branch adds appear in the family's documents? — W3 §WELCH.

The batch-7 BLOCK, made a standing rule and made mechanical: NO archive content
may enter tracked source — not a balance, an amount, a name, an account number,
nor an "example" block copied off a page. This builds the list of printed
tokens from every document in the named population and greps the WHOLE BRANCH
DIFF for each one. The count must be zero, and the count is reported.

    python -m tools.welch_privacy_scan --population tools/welch_population.txt \
        --data-dir webapp_data --base main [--out scan.json]

WHAT IS SCANNED FOR. Five token classes, taken from the documents themselves
rather than from a memory of what they contain:

* every printed money figure (`1,234.56`), with and without its separators;
* every digit run of three or more — account numbers, check numbers, reference
  numbers, ZIP codes, telephone digits;
* every fully-qualified date (`mm/dd/yy`, `mm/dd/yyyy`);
* every alphabetic word of four characters or more, in the case it was printed
  and upper-cased — holder names, merchant names, place names;
* every two-word sequence of such words, which catches a name whose halves are
  each ordinary.

WHAT IS NOT, and why each exclusion is safe rather than convenient:

* a token that ALREADY OCCURS IN THE TREE AT `--base`. This branch cannot be
  the thing that introduced it, and the class is almost entirely ordinary
  English and template vocabulary — `Date`, `Amount`, `Account`, `Balance` —
  plus the institution's own name, which the committed census already carries
  and which this registration exists to publish.
* a BARE `mm/dd` day token. It denominates nothing and identifies nobody; every
  statement in the corpus prints hundreds of them and any invented fixture must
  print some. Fully-qualified dates ARE scanned.

WHAT IS SCANNED. The branch diff `--base...HEAD`, ADDED lines only, across
every file — production, tests, tools and documentation alike. A leak in a
docstring is the batch-7 defect this rule was written for.

READ-ONLY over the archive; OCR artifacts by direct file path; $0.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MONEY_RE = re.compile(r"\d[\d,]*\.\d{2}")
DIGIT_RUN_RE = re.compile(r"\d{3,}")
FULL_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
WORD_RE = re.compile(r"[A-Za-z]{4,}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--population", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", default="main")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def _tracked_text(ref: str) -> str:
    """Every tracked file's contents at `ref`, concatenated and upper-cased."""
    names = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\n")
    chunks = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        blob = subprocess.run(
            ["git", "show", f"{ref}:{name}"],
            cwd=ROOT, capture_output=True, check=False,
        )
        chunks.append(blob.stdout.decode("utf-8", errors="replace"))
    return "\n".join(chunks).upper()


def _added_lines(base: str) -> str:
    diff = subprocess.run(
        ["git", "diff", f"{base}...HEAD", "--unified=0"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    added = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(added).upper()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]
    shas = [
        token.strip().upper()
        for line in args.population.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
        for token in line.split()
        if token.strip()
    ]

    printed: set[str] = set()
    documents = 0
    for sha in shas:
        best = None
        for key in ocr_keys:
            composed = cache_key(STAGE_OCR, sha, key)
            path = root / STAGE_OCR / composed[:2] / f"{composed}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            document = (payload.get("artifact") or {}).get("document")
            if not isinstance(document, dict):
                continue
            pages = [str(page) for page in (document.get("pages") or [])]
            text = StatementMarkdown(
                source_file="scan.pdf",
                model=str(document.get("model") or ""),
                pages=pages,
            ).to_markdown()
            if best is None or len(text) > len(best):
                best = text
        if best is None:
            continue
        documents += 1
        upper = best.upper()
        for figure in MONEY_RE.findall(upper):
            printed.add(figure)
            printed.add(figure.replace(",", ""))
        printed.update(DIGIT_RUN_RE.findall(upper))
        printed.update(FULL_DATE_RE.findall(upper))
        words = WORD_RE.findall(upper)
        printed.update(words)
        printed.update(f"{a} {b}" for a, b in zip(words, words[1:]))

    base_text = _tracked_text(args.base)
    distinctive = sorted(token for token in printed if token not in base_text)
    added = _added_lines(args.base)
    hits = sorted(token for token in distinctive if token in added)

    report = {
        "documents_read": documents,
        "printed_tokens": len(printed),
        "already_present_at_base": len(printed) - len(distinctive),
        "distinctive_literals_scanned": len(distinctive),
        "diff_added_characters": len(added),
        "hits": hits,
        "hit_count": len(hits),
    }
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(
        {key: value for key, value in report.items() if key != "hits"}, sort_keys=True
    ))
    for hit in hits:
        print(f"HIT {hit!r}", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())

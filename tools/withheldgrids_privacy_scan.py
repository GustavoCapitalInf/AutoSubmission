"""Is there one archive literal in this branch's added lines? And a control byte?

W3 §WITHHELDGRIDS's fifth committed instrument. The standing rule since the
batch-7 BLOCK is that no archive content may enter tracked source — not a
balance, an amount, a name, an account number, nor an "example" block copied
out of a document — and the way that rule is kept is by MEASURING it rather
than by being careful.

    python -m tools.withheldgrids_privacy_scan \
        --shas <file of content_sha256> \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> [--base-rev 10cc722]

WHAT IT HARVESTS from each document's cached OCR text: every amount with cents
(both decimal marks, and the space-grouped French form), every full or partial
printed date, every digit run of five or more, every capitalised token and
every capitalised bigram. Those five classes are what a leak looks like.

WHAT IT SEARCHES: every ADDED line of `git diff <base>..HEAD` — the whole
branch diff, prose and code and tests alike, not the files the cell remembers
touching.

WHAT IT DISCOUNTS, and why that is not cheating: a literal that the tracked
repository ALREADY carried at the base revision cannot have been added by this
branch. `$0.00`, `01/02` and `Total` occur in an archive of this size many
thousands of times and in the repository too. Each raw hit is therefore
re-checked with `git grep -F` against the base revision, and only what is new
in this branch is scored. Every residual is printed for a human to read.

IT ALSO BYTE-CHECKS every file the branch touched for control bytes
(0x00–0x08, 0x0B, 0x0C, 0x0E–0x1F): a copied cell can carry one, and a
control byte in tracked source is a defect on its own.

READ-ONLY and $0.00: artifacts by direct file path, no sqlite index, no
hosted model, no network.

PRIVACY OF THE TOOL ITSELF: it prints counts, `content_sha256` prefixes, and —
for a RESIDUAL only, which is a thing a human must then judge — the literal
that survived every filter. A residual is by construction a string this branch
added to tracked source, so printing it discloses nothing the diff does not.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

CONTROL_BYTES = set(range(0x00, 0x09)) | {0x0B, 0x0C} | set(range(0x0E, 0x20))

HARVEST = (
    # an amount with cents, either decimal mark, either grouping
    re.compile(r"\d[\d, .]*[.,]\d{2}(?!\d)"),
    # printed dates, full and partial
    re.compile(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"),
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"(?:January|February|March|April|May|June|July|August|September"
               r"|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct"
               r"|Nov|Dec)\.?\s+\d{1,2}(?:,?\s+\d{4})?", re.I),
    # any digit run of five or more
    re.compile(r"\d{5,}"),
    # capitalised tokens and capitalised bigrams
    re.compile(r"\b[A-Z][A-Za-z&'-]{2,}\b"),
    re.compile(r"\b[A-Z][A-Za-z&'-]{2,}\s+[A-Z][A-Za-z&'-]{2,}\b"),
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True, errors="replace").stdout


def _in_base(repo: Path, base_rev: str, literal: str) -> bool:
    proc = subprocess.run(
        ["git", "grep", "-F", "-q", "-e", literal, base_rev],
        cwd=repo, capture_output=True, text=True,
    )
    return proc.returncode == 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shas", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--baseline-settings-key", required=True)
    ap.add_argument("--base-rev", default="10cc722")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--min-length", type=int, default=4,
                    help="ignore harvested literals shorter than this")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()

    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key, ocr_settings_key

    root = Path(args.data_dir) / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
        for f, l, v in itertools.product((False, True), repeat=3)
    ]
    shas = [line.strip().upper()
            for line in Path(args.shas).read_text(encoding="utf-8").split()
            if line.strip()]

    literals: set[str] = set()
    resolved = 0
    for sha in shas:
        found_one = False
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
            text = StatementMarkdown(
                source_file="privacy.pdf",
                model=str(document.get("model") or ""),
                pages=[str(page) for page in (document.get("pages") or [])],
            ).to_markdown()
            found_one = True
            for pattern in HARVEST:
                for match in pattern.finditer(text):
                    token = match.group().strip()
                    if len(token) >= args.min_length:
                        literals.add(token)
        resolved += 1 if found_one else 0

    diff = _git(repo, "diff", f"{args.base_rev}..HEAD")
    added = [
        line[1:] for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    added_blob = "\n".join(added)

    raw = sorted(token for token in literals if token in added_blob)
    residual = [token for token in raw if not _in_base(repo, args.base_rev, token)]

    print(f"documents resolved to cached text = {resolved} of {len(shas)}")
    print(f"distinct harvested literals       = {len(literals)}")
    print(f"added lines in the branch diff    = {len(added)}")
    print(f"raw intersections                 = {len(raw)}")
    print(f"RESIDUAL (new in this branch)     = {len(residual)}")
    for token in residual:
        print(f"  residual: {token!r}")

    changed = [
        name for name in _git(repo, "diff", "--name-only", f"{args.base_rev}..HEAD").split("\n")
        if name.strip()
    ]
    offenders = []
    for name in changed:
        path = repo / name
        if not path.exists():
            continue
        data = path.read_bytes()
        bad = sorted({byte for byte in data if byte in CONTROL_BYTES})
        if bad:
            offenders.append((name, [hex(b) for b in bad]))
    print(f"files changed by the branch       = {len(changed)}")
    print(f"files carrying a control byte     = {len(offenders)}")
    for name, bad in offenders:
        print(f"  control bytes in {name}: {bad}")

    return 0 if not residual and not offenders else 2


if __name__ == "__main__":
    sys.exit(main())

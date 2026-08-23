"""The privacy scan: no printing of a named population may reach tracked source.

The batch-7 BLOCK made this a standing rule of the wave — a production
docstring quoted four real customer balances — and a rule with no instrument
is a rule nobody can re-check. This builds the literal list from the
documents themselves and greps a branch diff for every one of them:

    git diff <base>..HEAD > <private>/branch.diff
    python -m tools.cpscan_privacy_grep \
        --rows <reports>/<run-id>/rows.csv \
        --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> \
        --sha-file <private>/population.txt \
        --diff <private>/branch.diff

WHAT IS SCANNED, and why each class is in or out. The rule names "every
printed figure/name/account/date token", and a scan is only as honest as its
definition of those:

* MONEY FIGURES — every `1,234.56` and every bare `.56` the document prints,
  in both the printed form and the comma-stripped one, because a docstring
  that dropped the comma would still be quoting the balance;
* ACCOUNT AND CARD NUMBERS — masked runs (`XXXXXXXXXX0000`, `****0000`) and
  their trailing digits;
* REFERENCE RUNS — any digit run of five or more, which is where this
  platform's cheque serials, terminal ids, ACH traces and telephone numbers
  live;
* DATE TOKENS — `mm/dd/yy`, `mm/dd/yyyy`, `mm-dd-yy` and `Month D, YYYY`, the
  full forms. A statement date identifies a document; `03/12` on its own does
  not, and scanning two-field tokens would flag every date in every invented
  fixture in the tree;
* NAME PHRASES — every multi-word run of capitalised words in the masthead
  region (the institution slot, the holder block and the product line), which
  is where an issuer, a holder and a product name are printed;
* LONG WORDS — every alphabetic token of eight characters or more anywhere in
  the document. A merchant, a city or a surname is caught here even when it
  stands alone; ordinary furniture words are shorter.

DELIBERATELY OUT, and the reason: bare integers and four-digit years. A
count, a page number and `2026` are not identifying, they are unavoidable in
any measurement a log has to report, and including them would make the count
a number nobody could drive to zero and therefore nobody would read.

ALSO OUT, and this one is the difference between a number and a noise floor:
**any literal that already stands in the tracked tree at `--base-rev`.** The
question a branch scan asks is what THIS BRANCH put there. Six of the classes
above are word- and number-shaped, so they collide with ordinary source text
by construction — `subtractions` is a summary field, `transactions` is a
schema attribute, `100.00` is a figure two invented fixtures already carried
before this branch existed. A scan that reported those would report fifty
hits on a clean branch, and fifty hits nobody can act on is worse than none.
The baseline is read with `git archive <base-rev>`, so it is the tracked tree
at that commit exactly — not the working directory, which carries scratch
files, and not `HEAD`, which would exclude the branch's own additions and
make the scan vacuous.

READ-ONLY and $0. The report is COUNTS and diff LINE NUMBERS only — printing
a hit would be the leak the tool exists to prevent.
"""
from __future__ import annotations

import argparse
import io
import itertools
import json
import re
import subprocess
import tarfile
from pathlib import Path

#: Extensions a literal can hide in. A `.pdf` or a `.png` in the tracked tree
#: is not source a docstring could have quoted into, and decoding one as text
#: would put megabytes of binary into the baseline and mask real hits.
TEXT_SUFFIXES = {".py", ".md", ".txt", ".ini", ".cfg", ".toml", ".yml", ".yaml",
                 ".json", ".csv", ".html", ".js", ".css", ".sh", ".ps1", ""}

MONEY = re.compile(r"[0-9][0-9,]*\.[0-9]{2}|(?<![0-9])\.[0-9]{2}")
MASKED = re.compile(r"[Xx*•·]{3,}[0-9]{2,}")
RUN = re.compile(r"(?<![0-9])[0-9]{5,}(?![0-9])")
DATES = re.compile(
    r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}"
    r"|[0-9]{2}-[0-9]{2}-[0-9]{2,4}"
    r"|(?:January|February|March|April|May|June|July|August|September|October"
    r"|November|December)\s+[0-9]{1,2},\s+[0-9]{4}"
)
NAME_PHRASE = re.compile(r"\b[A-Z][A-Za-z&'.-]+(?: [A-Z][A-Za-z&'.-]+)+\b")
LONG_WORD = re.compile(r"(?<![A-Za-z])[A-Za-z]{8,}(?![A-Za-z])")

#: How much of the document counts as the masthead for NAME_PHRASE. The
#: institution slot, the holder block and the product line are all inside the
#: first page's header; running the phrase rule over 40 pages of merchant
#: blocks produces thousands of two-word English phrases and no signal.
MASTHEAD_CHARS = 900


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--baseline-settings-key", required=True)
    parser.add_argument("--sha-file", required=True, type=Path)
    parser.add_argument("--diff", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="the git repository the baseline tree is read from")
    parser.add_argument("--base-rev", default=None,
                        help="literals already in the tracked tree at this rev are not this branch's")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def baseline_text(repo: Path, rev: str) -> str:
    """Every tracked TEXT file of `rev`, concatenated.

    `git archive` rather than a directory walk: the working tree carries
    untracked scratch, and a literal that happens to sit in an uncommitted log
    is not a literal the branch may quote.
    """
    completed = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", rev],
        capture_output=True, check=True,
    )
    chunks: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(completed.stdout)) as archive:
        for member in archive:
            if not member.isfile() or Path(member.name).suffix.lower() not in TEXT_SUFFIXES:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            chunks.append(handle.read().decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def literals(text: str) -> set[str]:
    found: set[str] = set()
    for match in MONEY.finditer(text):
        token = match.group(0)
        found.add(token)
        found.add(token.replace(",", ""))
    for pattern in (MASKED, RUN, DATES):
        found.update(match.group(0) for match in pattern.finditer(text))
    for match in MASKED.finditer(text):
        found.add(re.sub(r"[^0-9]", "", match.group(0)))
    found.update(match.group(0) for match in NAME_PHRASE.finditer(text[:MASTHEAD_CHARS]))
    found.update(match.group(0) for match in LONG_WORD.finditer(text))
    return {token for token in found if len(token) >= 4}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import (
        STAGE_ANALYSIS, STAGE_OCR, analysis_input_sha, cache_key, ocr_settings_key,
    )

    baseline = args.baseline_settings_key.strip().upper()
    root = args.data_dir / "artifacts"
    ocr_keys = [ocr_settings_key(force_ocr=f, allow_local_ocr=l, allow_visual_ocr=v)
                for f, l, v in itertools.product((False, True), repeat=3)]
    shas = [line.strip().upper()
            for line in args.sha_file.read_text(encoding="utf-8").splitlines()
            if line.strip()]

    tokens: set[str] = set()
    read = 0
    for sha in shas:
        candidates = []
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
            candidates.append((StatementMarkdown(
                source_file="privacy.pdf", model=str(document.get("model") or ""),
                pages=pages).to_markdown(), pages))
        if not candidates:
            continue
        chosen = candidates[0]
        for markdown, pages in candidates:
            composed = cache_key(STAGE_ANALYSIS, analysis_input_sha(markdown, pages), baseline)
            if (root / STAGE_ANALYSIS / composed[:2] / f"{composed}.json").exists():
                chosen = (markdown, pages)
                break
        read += 1
        tokens |= literals(chosen[0])

    inherited = 0
    if args.base_rev:
        baseline_source = baseline_text(args.repo, args.base_rev)
        before = len(tokens)
        tokens = {token for token in tokens if token not in baseline_source}
        inherited = before - len(tokens)

    diff_lines = args.diff.read_text(encoding="utf-8", errors="replace").splitlines()
    # Only the ADDED side of the diff is tracked source. A removed line is
    # leaving the tree, and the diff header's own paths are not content.
    added = [(number, line[1:]) for number, line in enumerate(diff_lines, 1)
             if line.startswith("+") and not line.startswith("+++")]
    hits: list[dict[str, object]] = []
    for token in sorted(tokens):
        for number, line in added:
            if token in line:
                hits.append({"diff_line": number, "token_length": len(token)})
                break

    report = {
        "documents_named": len(shas),
        "documents_read": read,
        "literals": len(tokens),
        "literals_already_in_the_base_tree": inherited,
        "added_diff_lines": len(added),
        "hits": len(hits),
        "hit_locations": hits[:50],
    }
    text = json.dumps(report, indent=1)
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())

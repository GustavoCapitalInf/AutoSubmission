"""Does anything a branch ADDS appear in the documents it worked on? — the shared instrument.

The batch-7 BLOCK made a standing rule and, from batch 8, one committed tool
rather than one per cell: NO archive content may enter tracked source — not a
balance, an amount, a name, an account number, a date, nor an "example" block
copied off a page. This builds the list of printed tokens from every document
in a NAMED population (cached OCR/native text, by direct artifact path, $0) and
greps the branch's ADDED lines for each one, class by class, with file:line.

    python tools/privacy_scan_branch.py --shas population.txt \
        --data-dir <main-checkout>/webapp_data --base 10cc722 --ref wave8-frostozk

    # a population from the run of record's rows.csv instead of a file:
    python tools/privacy_scan_branch.py --rows discovery_reports/<run>/rows.csv \
        --where parser_id=td_canada_native,td_canada_french --data-dir ... --base ... --ref ...

Token classes, taken from the documents rather than from memory:

* MONEY — every printed money figure carrying cents (`1,234.56`), with and
  without its separators;
* DIGITS — every digit run of `--digit-min` (default 5) or more: account,
  cheque, reference and authorisation numbers, telephone digits, ZIP+4;
* DATES — every fully-qualified date, numeric (`mm/dd/yy`, `mm/dd/yyyy`,
  `yyyy-mm-dd`) or spelled (`January 5, 2026`, `5 January 2026`, `Jan 5 2026`);
* WORDS — every alphabetic word of `--word-min` (default 4) or more characters,
  upper-cased, and every two-word sequence of them (a name whose halves are each
  ordinary).

What is excluded, and why each exclusion is safe rather than convenient: a token
that ALREADY OCCURS IN THE TRACKED TEXT TREE AT `--base`. This branch cannot be
the thing that introduced it, and the class is almost entirely template
vocabulary — `Date`, `Amount`, `Balance` — plus institution names the committed
census already carries. Bare `mm/dd` day tokens are not scanned: they identify
nobody, and every fixture must print some.

What is scanned: the diff `--base...--ref`, ADDED lines only, every text file —
production, tests, tools, fixtures, documentation. `--include-tree` additionally
scans every tracked text file at `--ref` in full (for a branch that inherited a
leak from an earlier commit).

Exit 1 on any hit, 0 on none. The JSON summary goes to stdout; each hit goes to
stderr as `HIT <class> <file>:<line> <token>` — the report is for the operator's
terminal and must never itself be committed.

SELF-CHECK (the FROST-OZK / ATB-MEASURE lesson): a scan written through a
shell heredoc once lost the backslash of every `\\b` to a 0x08 byte and matched
nothing, so its zeros were vacuous. On import this module refuses to run unless
its own file carries no control byte and every pattern matches a synthetic
instance of the shape it names.

READ-ONLY over the archive; OCR artifacts by direct file path; no sqlite index;
no OCR; no hosted model; $0.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MONEY_RE = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d.])|(?<![\d.])\d{4,}\.\d{2}(?![\d.])")
NUMERIC_DATE_RE = re.compile(
    r"(?<![\d/])(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})(?![\d/])"
)
_MONTHS = (
    "JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUNE?|JULY?|AUG(?:UST)?|"
    "SEPT?(?:EMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?"
)
SPELLED_DATE_RE = re.compile(
    rf"\b(?:(?:{_MONTHS})\.? \d{{1,2}},? \d{{4}}|\d{{1,2}} (?:{_MONTHS})\.? \d{{4}})\b"
)
WORD_RE = re.compile(r"[A-Z]{4,}")

#: Tracked text formats. Everything else in the tree is a PDF of the validated
#: corpus, which is not source and cannot be what a branch added.
TEXT_SUFFIXES = frozenset(
    "py md txt json csv yml yaml toml cfg ini html js ts tsx jsx css sh bat "
    "gitignore in rst".split()
)

_CONTROL_BYTES = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def self_check() -> None:
    """Refuse to run as an inert instrument."""
    own = Path(__file__).read_bytes()
    found = _CONTROL_BYTES.findall(own)
    if found:
        raise SystemExit(f"privacy_scan_branch.py carries {len(found)} control byte(s); refusing to run")
    samples = {
        "MONEY_RE": (MONEY_RE, "TOTAL 12,345.67 AND 987.65 AND 1234567.89"),
        "NUMERIC_DATE_RE": (NUMERIC_DATE_RE, "ON 01/31/2026 OR 1/2/26 OR 2026-01-31"),
        "SPELLED_DATE_RE": (SPELLED_DATE_RE, "ON JANUARY 5, 2026 AND 5 FEB 2026 AND SEPT 30 2025"),
        "WORD_RE": (WORD_RE, "HOLDER NAME"),
    }
    for name, (pattern, sample) in samples.items():
        if not pattern.search(sample):
            raise SystemExit(f"{name} matches nothing in its own sample; refusing to run")
    if len(SPELLED_DATE_RE.findall("ON JANUARY 5, 2026 AND 5 FEB 2026 AND SEPT 30 2025")) != 3:
        raise SystemExit("SPELLED_DATE_RE does not match all three spelled shapes; refusing to run")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shas", action="append", default=[], type=Path,
                        help="file of content_sha256 values, one per line, '#' comments")
    parser.add_argument("--sha", action="append", default=[], help="a single content_sha256")
    parser.add_argument("--rows", type=Path, default=None, help="a run's rows.csv")
    parser.add_argument("--where", action="append", default=[],
                        help="rows.csv filter key=v1,v2 (repeatable; all must hold)")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--digit-min", type=int, default=5)
    parser.add_argument("--word-min", type=int, default=4)
    parser.add_argument("--include-tree", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args(argv)


def population(args: argparse.Namespace) -> list[str]:
    shas: set[str] = set(s.strip().upper() for s in args.sha)
    for path in args.shas:
        for line in path.read_text(encoding="utf-8").splitlines():
            token = line.split("#", 1)[0].strip().upper()
            if token:
                shas.add(token)
    if args.rows is not None:
        filters = []
        for clause in args.where:
            key, _, values = clause.partition("=")
            filters.append((key, set(v.strip() for v in values.split(","))))
        with args.rows.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if all(row.get(key, "") in values for key, values in filters):
                    if row.get("content_sha256"):
                        shas.add(row["content_sha256"].upper())
    bad = sorted(s for s in shas if not re.fullmatch(r"[0-9A-F]{64}", s))
    if bad:
        raise SystemExit(f"{len(bad)} population entries are not 64-hex shas: {bad[:3]}")
    return sorted(shas)


def cached_text(root: Path, sha: str, ocr_keys: list[str]) -> str | None:
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key

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
            source_file="scan.pdf", model=str(document.get("model") or ""), pages=pages
        ).to_markdown()
        if best is None or len(text) > len(best):
            best = text
    return best


def tokens_of(text: str, digit_min: int, word_min: int) -> dict[str, set[str]]:
    upper = text.upper()
    classes: dict[str, set[str]] = {"MONEY": set(), "DIGITS": set(), "DATES": set(), "WORDS": set()}
    for figure in MONEY_RE.findall(upper):
        classes["MONEY"].add(figure)
        classes["MONEY"].add(figure.replace(",", ""))
    classes["DIGITS"].update(re.findall(rf"\d{{{digit_min},}}", upper))
    classes["DATES"].update(NUMERIC_DATE_RE.findall(upper))
    classes["DATES"].update(SPELLED_DATE_RE.findall(upper))
    words = re.findall(rf"[A-Z]{{{word_min},}}", upper)
    classes["WORDS"].update(words)
    classes["WORDS"].update(f"{a} {b}" for a, b in zip(words, words[1:]))
    return classes


def tracked_text(ref: str) -> str:
    """Every tracked TEXT file at `ref`, concatenated and upper-cased (one cat-file batch)."""
    listing = subprocess.run(
        ["git", "ls-tree", "-r", ref], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    blobs = []
    for line in listing.splitlines():
        head, _, name = line.partition("\t")
        parts = head.split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        if name.strip().rsplit(".", 1)[-1].lower() not in TEXT_SUFFIXES:
            continue
        blobs.append(parts[2])
    batch = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=ROOT,
        input=("\n".join(blobs) + "\n").encode(), capture_output=True, check=True,
    ).stdout
    return batch.decode("utf-8", errors="replace").upper()


def added_lines(base: str, ref: str) -> list[tuple[str, int, str]]:
    """(file, new-line-number, upper-cased text) for every added line of base...ref."""
    diff = subprocess.run(
        ["git", "diff", f"{base}...{ref}", "--unified=0"],
        cwd=ROOT, capture_output=True, text=True, check=True, errors="replace",
    ).stdout
    out: list[tuple[str, int, str]] = []
    current = ""
    line_no = 0
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/")
            continue
        match = hunk.match(line)
        if match:
            line_no = int(match.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            out.append((current, line_no, line[1:].upper()))
            line_no += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
    return out


def main(argv: list[str] | None = None) -> int:
    self_check()
    args = parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from webapp.artifact_cache import ocr_settings_key

    root = args.data_dir / "artifacts"
    ocr_keys = [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]
    shas = population(args)
    printed: dict[str, set[str]] = {"MONEY": set(), "DIGITS": set(), "DATES": set(), "WORDS": set()}
    documents_read = 0
    missing: list[str] = []
    for sha in shas:
        text = cached_text(root, sha, ocr_keys)
        if text is None:
            missing.append(sha[:8])
            continue
        documents_read += 1
        for cls, values in tokens_of(text, args.digit_min, args.word_min).items():
            printed[cls].update(values)

    base_text = tracked_text(args.base)
    distinctive = {
        cls: sorted(token for token in values if token not in base_text)
        for cls, values in printed.items()
    }
    lines = added_lines(args.base, args.ref)
    if args.include_tree:
        listing = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", args.ref], cwd=ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for name in listing:
            if name.rsplit(".", 1)[-1].lower() not in TEXT_SUFFIXES:
                continue
            blob = subprocess.run(
                ["git", "show", f"{args.ref}:{name}"], cwd=ROOT,
                capture_output=True, text=True, errors="replace",
            ).stdout
            for number, text in enumerate(blob.splitlines(), 1):
                lines.append((f"tree:{name}", number, text.upper()))

    haystack = "\n".join(text for _, _, text in lines)
    hits: list[dict[str, object]] = []
    for cls, tokens in distinctive.items():
        for token in tokens:
            if token not in haystack:
                continue
            for file, number, text in lines:
                if token in text:
                    hits.append({"class": cls, "file": file, "line": number, "token": token})
    hits.sort(key=lambda h: (str(h["file"]), int(h["line"]), str(h["class"])))

    report = {
        "population": len(shas),
        "documents_read": documents_read,
        "no_cached_text": missing,
        "printed_tokens": {cls: len(v) for cls, v in printed.items()},
        "distinctive_scanned": {cls: len(v) for cls, v in distinctive.items()},
        "added_lines": len(lines),
        "hits_by_class": {cls: sum(1 for h in hits if h["class"] == cls) for cls in printed},
        "hit_count": len(hits),
        "base": args.base,
        "ref": args.ref,
    }
    if args.out is not None:
        args.out.write_text(json.dumps({**report, "hits": hits}, indent=1), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    for hit in hits:
        print(f"HIT {hit['class']} {hit['file']}:{hit['line']} {hit['token']!r}", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())

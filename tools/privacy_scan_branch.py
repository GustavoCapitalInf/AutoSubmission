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

TREE AUDITS NEED THE ROOT COMMIT AS `--base`. The base-tree exclusion removes
every token that already sits in the tracked tree at `--base` — which, for a
token inherited from an earlier commit, is exactly the token you are looking
for. `--include-tree --base 10cc722` therefore proves only that no NEW archive
token was added (SCAN-HYGIENE closure, batch 8, found this the hard way). For
an audit of what the tree already carries, pass the repository's root commit:

    python tools/privacy_scan_branch.py --shas population.txt --data-dir ... \
        --base "$(git rev-list --max-parents=0 HEAD)" --ref train8 --include-tree

and adjudicate the candidates by class.

THE EXCLUSION TABLE (batch 9, FIXTURE-PRIVACY). A whole-tree audit against a
3,351-document universe prints ~3.5x10^5 distinct money figures and ~2x10^5
digit runs, so a candidate is not yet a finding: some shapes cannot carry
archive identity at all, and some are archive text on purpose. Every rule below
names a SHAPE and is applied to every file alike — never a file list, never a
token list — and `tests/test_privacy_scan_exclusions.py` proves each one
matches exactly the shape it names and NOTHING wider (in particular that none
of them silences a bare account number). `--no-exclusions` reports the raw scan.

===================== ======================================================
rule                   what it excludes, and why that is safe
===================== ======================================================
``words_class``        class WORDS. Institution and template vocabulary:
                       `DATE`, `AMOUNT`, `DEPOSIT`, an issuer's own name. An
                       alphabetic token carries no figure and no identifier,
                       and the census already names every institution. The
                       standing exclusion applied at the batch-8 train.
``corpus_cache``       any path under ``tests/corpus_cache/``. That directory
                       IS cached archive text, committed on purpose so the
                       pinned corpus runs offline; scanning it re-finds the
                       archive in the archive. The standing exclusion applied
                       at the batch-8 train.
``round_money``        a MONEY token ending ``.00``. A round figure is a
                       magnitude, not a printed identity: `100.00` is the
                       bound of a test's tolerance as readily as it is a
                       deposit, and no document is reconstructed from one.
                       The standing exclusion applied at the batch-8 train.
``subunit_money``      a MONEY token whose integer part is a bare ``0``
                       (``0.01``..``0.99``). Cent and sub-unit CODE CONSTANTS
                       — a reconciliation tolerance, a rate floor. A
                       sub-unit magnitude identifies nobody and reconstructs
                       nothing.
``hex_sha_substring``  a DIGITS token that lies inside a 16..64-character hex
                       run on the same line. It is part of a content sha —
                       the program's own name for a document — and not a
                       number anything printed. (A sha is a hash OF the
                       document, never a token FROM it.)
``docs_session_date``  a DATES token in ``docs/`` that is an ISO date on or
                       after ``2026-07-01``. Those are the PROGRAM's own
                       session dates — when a cell ran, when a train closed —
                       written by this project after the archive was frozen
                       on 2026-08-06. A document date and a session date are
                       different facts that happen to share a shape, so the
                       rule is bounded by both the directory that holds the
                       program's records and the date the program began.
``institution_zip``    a DIGITS token of exactly five digits preceded on the
                       line, within eight non-digit characters, by a US state
                       abbreviation. A postal code of an institution's own
                       service address — the furniture the doctrine allows a
                       detection marker to carry (`P.O. BOX ... OZARK, AR
                       72949`). It identifies a bank branch, never a customer,
                       and its shape cannot spell an account number.
===================== ======================================================

Exit 1 on any hit the table does not exclude, 0 on none. The JSON summary goes
to stdout; each non-excluded hit goes to stderr as
`HIT <class> <file>:<line> <token>` — the report is for the operator's terminal
and must never itself be committed.

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

#: A content sha as it is written in this tree: 16 to 64 hex characters. The
#: token has to sit INSIDE one, so a bare digit run on the same line as a sha
#: is still a finding.
HEX_RUN_RE = re.compile(r"[0-9A-F]{16,64}")
#: `AR 72949`, `OZARK, AR\s*72949` — a state abbreviation, then at most eight
#: characters that are not digits, then the five-digit code itself. The gap is
#: short and digit-free so that the rule cannot reach past an address onto an
#: unrelated number, and both US territories and the DC code are included.
_STATE = (
    "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|"
    "MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|PR|RI|SC|SD|TN|TX|UT|VT|VA|"
    "VI|WA|WV|WI|WY"
)
ZIP_CONTEXT_RE = re.compile(rf"\b(?:{_STATE})\b[^0-9]{{0,8}}(\d{{5}})(?!\d)")
#: The archive was frozen on 2026-08-06; every record this program writes about
#: its own work is dated after it began, and the first batch-9 record is dated
#: from July 2026 on. Bounded by BOTH the directory and the date.
PROGRAM_ERA = "2026-07-01"
ISO_DATE_RE = re.compile(r"\A20\d\d-\d\d-\d\d\Z")


def _words_class(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "WORDS"


def _corpus_cache(cls: str, path: str, token: str, line: str) -> bool:
    return path.startswith("tests/corpus_cache/")


def _round_money(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "MONEY" and token.endswith(".00")


def _subunit_money(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "MONEY" and re.fullmatch(r"0\.\d\d", token) is not None


def _hex_sha_substring(cls: str, path: str, token: str, line: str) -> bool:
    return cls == "DIGITS" and any(token in run for run in HEX_RUN_RE.findall(line))


def _docs_session_date(cls: str, path: str, token: str, line: str) -> bool:
    return (
        cls == "DATES"
        and path.startswith("docs/")
        and ISO_DATE_RE.match(token) is not None
        and token >= PROGRAM_ERA
    )


def _institution_zip(cls: str, path: str, token: str, line: str) -> bool:
    return (
        cls == "DIGITS"
        and len(token) == 5
        and token in ZIP_CONTEXT_RE.findall(line)
    )


#: The table itself, in the order it is applied. A hit is attributed to the
#: FIRST rule that claims it, so the per-rule counts partition the raw hits.
EXCLUSIONS: tuple[tuple[str, object], ...] = (
    ("words_class", _words_class),
    ("corpus_cache", _corpus_cache),
    ("round_money", _round_money),
    ("subunit_money", _subunit_money),
    ("hex_sha_substring", _hex_sha_substring),
    ("docs_session_date", _docs_session_date),
    ("institution_zip", _institution_zip),
)

#: (rule, class, path, token, line, expected) — the shape each rule names and
#: the nearest thing it must NOT reach. Checked on import, so the table cannot
#: go inert the way a heredoc once made the patterns inert.
_EXCLUSION_SAMPLES = (
    ("words_class", "WORDS", "a.py", "BALANCE", "BALANCE", True),
    ("words_class", "DIGITS", "a.py", "12345", "12345", False),
    ("corpus_cache", "MONEY", "tests/corpus_cache/ocr/x.md", "1.23", "1.23", True),
    ("corpus_cache", "MONEY", "tests/test_x.py", "1.23", "1.23", False),
    ("round_money", "MONEY", "a.py", "100.00", "100.00", True),
    ("round_money", "MONEY", "a.py", "100.01", "100.01", False),
    ("subunit_money", "MONEY", "a.py", "0.01", "0.01", True),
    ("subunit_money", "MONEY", "a.py", "10.01", "10.01", False),
    ("hex_sha_substring", "DIGITS", "a.py", "12345", "AB12345CDEF01234567", True),
    ("hex_sha_substring", "DIGITS", "a.py", "12345", "ACCOUNT 12345", False),
    ("docs_session_date", "DATES", "docs/x.md", "2026-08-29", "ON 2026-08-29", True),
    ("docs_session_date", "DATES", "docs/x.md", "2026-06-30", "ON 2026-06-30", False),
    ("docs_session_date", "DATES", "tests/x.py", "2026-08-29", "ON 2026-08-29", False),
    ("institution_zip", "DIGITS", "a.py", "72949", "OZARK, AR 72949", True),
    ("institution_zip", "DIGITS", "a.py", "12345", "ACCOUNT 12345", False),
    ("institution_zip", "DIGITS", "a.py", "1234567", "OZARK, AR 1234567", False),
)


def excluded_by(cls: str, path: str, token: str, line: str) -> str | None:
    """The first rule of the table that claims this hit, or None."""
    for name, rule in EXCLUSIONS:
        if rule(cls, path, token, line):  # type: ignore[operator]
            return name
    return None


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
    named = {name for name, _ in EXCLUSIONS}
    for rule, cls, path, token, line, expected in _EXCLUSION_SAMPLES:
        if rule not in named:
            raise SystemExit(f"exclusion sample names {rule!r}, which is not in the table")
        got = excluded_by(cls, path, token, line) == rule
        if got is not expected:
            raise SystemExit(
                f"exclusion {rule!r} answers {got} for its own sample, expected {expected}; refusing to run"
            )
    for name in named:
        if not any(sample[0] == name for sample in _EXCLUSION_SAMPLES):
            raise SystemExit(f"exclusion {name!r} carries no sample; refusing to run")


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
    parser.add_argument("--no-exclusions", action="store_true",
                        help="report the RAW scan: attribute nothing to the exclusion table")
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

    # The base-tree exclusion is a SET membership, not a substring search: the
    # tracked text tree is tens of megabytes and a large population prints
    # ~10^5 tokens, and `token in text` per token made the scan quadratic (a
    # 300-document population ran for an hour). Tokenising the base tree ONCE
    # with the same patterns, plus every money figure with its separators
    # stripped, gives the same answer for every class in seconds.
    base_tokens = tokens_of(tracked_text(args.base), args.digit_min, args.word_min)
    base_all: set[str] = set().union(*base_tokens.values())
    distinctive = {
        cls: sorted(token for token in values if token not in base_all)
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

    # The branch side is tokenised with the SAME patterns, so a match is a
    # whole token on both sides: an OCR fragment such as `WELC` printed by a
    # scan cannot hit inside `WELCOME`, and `26.43` cannot hit inside
    # `1,026.43`. (Substring matching on this side, with set exclusion on the
    # other, produced hundreds of fragment false positives per branch.)
    #
    # The attribution is an INVERTED INDEX, token -> the sites that print it,
    # built over the tokens the document side actually asks about. The paired
    # loop it replaces (every distinctive token x every scanned line) is
    # quadratic: a whole-tree audit scans ~5x10^5 lines and a 3,380-document
    # universe makes ~5x10^4 of its tokens hit, which is ~10^10 set lookups —
    # hours, for exactly the same hit list this produces in seconds.
    wanted: set[str] = set().union(*distinctive.values()) if distinctive else set()
    sites: dict[str, list[int]] = {}
    for index, (_file, _number, text) in enumerate(lines):
        for token in set().union(*tokens_of(text, args.digit_min, args.word_min).values()) & wanted:
            sites.setdefault(token, []).append(index)
    hits: list[dict[str, object]] = []
    for cls, tokens in distinctive.items():
        for token in tokens:
            for index in sites.get(token, ()):
                file, number, text = lines[index]
                # `--include-tree` labels the whole-file pass `tree:<path>`;
                # the exclusion rules are about the PATH, so they see it bare.
                path = file[5:] if file.startswith("tree:") else file
                rule = None if args.no_exclusions else excluded_by(cls, path, str(token), text)
                hits.append({
                    "class": cls, "file": file, "line": number,
                    "token": token, "excluded_by": rule,
                })
    hits.sort(key=lambda h: (str(h["file"]), int(h["line"]), str(h["class"])))

    kept = [hit for hit in hits if hit["excluded_by"] is None]
    # With a root-commit `--base`, the diff pass and `--include-tree` reach the
    # same line twice under two labels. A SITE is the thing to count and to
    # fix: one class, one path, one line, one token.
    site_keys = {
        (str(h["class"]), str(h["file"]).removeprefix("tree:"), int(h["line"]), str(h["token"]))
        for h in kept
    }
    by_class_dir: dict[str, int] = {}
    for cls, path, _number, _token in site_keys:
        top = path.split("/", 1)[0] if "/" in path else "(root)"
        by_class_dir[f"{cls} {top}"] = by_class_dir.get(f"{cls} {top}", 0) + 1

    report = {
        "population": len(shas),
        "documents_read": documents_read,
        "no_cached_text": missing,
        "printed_tokens": {cls: len(v) for cls, v in printed.items()},
        "distinctive_scanned": {cls: len(v) for cls, v in distinctive.items()},
        "added_lines": len(lines),
        "raw_hit_count": len(hits),
        "excluded_by_rule": {
            name: sum(1 for h in hits if h["excluded_by"] == name) for name, _ in EXCLUSIONS
        },
        "hits_by_class": {cls: sum(1 for h in kept if h["class"] == cls) for cls in printed},
        "hit_count": len(kept),
        "residue_sites": len(site_keys),
        "residue_files": len({path for _cls, path, _n, _t in site_keys}),
        "residue_by_class_dir": dict(sorted(by_class_dir.items())),
        "base": args.base,
        "ref": args.ref,
    }
    if args.out is not None:
        args.out.write_text(json.dumps({**report, "hits": hits}, indent=1), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    for hit in kept:
        print(f"HIT {hit['class']} {hit['file']}:{hit['line']} {hit['token']!r}", file=sys.stderr)
    return 1 if kept else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""W3 §COREENC C2.1/C3/C7/C16: the censuses behind this card's headline numbers.

The card's rule is that a headline number reproduces from committed evidence.
Four of §COREENC's did not, because the throwaway scripts that produced them
were never committed. This is the instrument that produces them now, in four
modes over the SAME read: the cached OCR text of the run of record, resolved
from the D-3 artifact store by DIRECT file path across every capability
partition of `ocr_settings_key`, longest reconstruction wins.

    python -m tools.coreenc_archive_census reach     --rows <run>/rows.csv \\
        --data-dir <checkout>/webapp_data --shas <the census 58>
    python -m tools.coreenc_archive_census furniture --data-dir ... --shas ...
    python -m tools.coreenc_archive_census signs     --data-dir ... --shas ...
    python -m tools.coreenc_archive_census literals  --data-dir ... --shas ... \\
        --base <base commit> [--show-residual]

* **reach** — runs THIS registration's detector over every document of the run
  of record and reports which documents it claims, splitting them into the
  named census family and the documents claimed OUTSIDE it. For each outsider
  it reports the outcome the run recorded, the parser that wins the dispatch at
  HEAD, and whether this reader's `parse` publishes anything. That is what
  names the 13 outsiders by `content_sha256`.
* **furniture** — the per-printing document counts of C3, each pattern taken
  from the production module itself where the module has one, so the census
  measures what the reader registers on rather than a paraphrase of it.
* **signs** — the C7 sign census: every row the reader PUBLISHES, split by the
  role of the block the bank printed it in and by whether the figure carried a
  minus. It is the measurement behind "the banner decides the direction, never
  the sign".
* **literals** — the privacy scan: every archive literal the standing rule
  names, intersected with the added lines of the branch diff and filtered
  against the vocabulary the tracked repository already carried at the base
  commit. It reports COUNTS. The residual literals themselves are printed only
  under `--show-residual`, so that the instrument can be committed without
  being a channel for the thing it is looking for.

READ-ONLY and $0: nothing is written to the archive or the artifact store, the
`webapp_data` sqlite index is never opened, no model is called, no OCR is run,
and `analyze_markdown` is never called — this instrument reads the module's own
detector and reader directly.

**No document text, amount, name, account number or date is printed** by any
mode except `literals --show-residual`, which exists so a residual can be
adjudicated by the person running it and is never the committed output.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# The shared read
# ---------------------------------------------------------------------------

def _ocr_keys() -> list[str]:
    from webapp.artifact_cache import ocr_settings_key
    return [
        ocr_settings_key(force_ocr=force, allow_local_ocr=local, allow_visual_ocr=visual)
        for force, local, visual in itertools.product((False, True), repeat=3)
    ]


def _ocr_text(root: Path, sha: str, keys: list[str]) -> str | None:
    """The longest cached OCR reconstruction of one document, by direct path."""
    from ocr.document import StatementMarkdown
    from webapp.artifact_cache import STAGE_OCR, cache_key

    best: str | None = None
    for key in keys:
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
        markdown = StatementMarkdown(
            source_file="census.pdf", model=str(document.get("model") or ""),
            pages=[str(page) for page in (document.get("pages") or [])],
        ).to_markdown()
        if best is None or len(markdown) > len(best):
            best = markdown
    return best


def _named(path: Path) -> list[str]:
    return [line.strip().upper() for line in
            path.read_text(encoding="utf-8").split() if line.strip()]


def _recorded(rows: Path) -> dict[str, tuple[str, str, str]]:
    csv.field_size_limit(10_000_000)
    found: dict[str, tuple[str, str, str]] = {}
    with rows.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            sha = (row["content_sha256"] or "").upper()
            if sha:
                found.setdefault(sha, (row["outcome_class"], row["outcome_reason"],
                                       row["parser_id"] or ""))
    return found


# ---------------------------------------------------------------------------
# reach — who this registration claims, inside the family and outside it
# ---------------------------------------------------------------------------

def _reach(args: argparse.Namespace) -> int:
    # The entries import is what FILLS the registry; without it `resolve`
    # answers `unclaimed` for every document because there is nothing
    # registered to claim one.
    from analysis import parser_registry_entries as _entries  # noqa: F401
    from analysis.core_processor_enclosures import (
        detect, parse_core_processor_enclosures_statement,
    )
    from analysis.parser_registry import resolve

    root = args.data_dir / "artifacts"
    keys = _ocr_keys()
    recorded = _recorded(args.rows)
    family = set(_named(args.shas))

    started = time.perf_counter()
    scanned = with_text = 0
    claimed: list[dict[str, object]] = []
    for sha in recorded:
        scanned += 1
        markdown = _ocr_text(root, sha, keys)
        if markdown is None:
            continue
        with_text += 1
        if not detect(markdown).claims:
            continue
        dispatch = resolve(markdown)
        was = recorded[sha]
        claimed.append({
            "content_sha256": sha,
            "in_the_named_family": sha in family,
            "was_outcome_class": was[0],
            "was_outcome_reason": was[1],
            "was_parser_id": was[2],
            "dispatch_outcome": dispatch.outcome,
            "dispatch_parser_id": dispatch.parser_id or "",
            "this_reader_publishes": (
                parse_core_processor_enclosures_statement(markdown) is not None),
        })

    inside = [row for row in claimed if row["in_the_named_family"]]
    outside = [row for row in claimed if not row["in_the_named_family"]]
    transitions: dict[str, int] = {}
    for row in outside:
        key = (f'{row["was_outcome_class"]}/{row["was_outcome_reason"]}'
               f' -> dispatch {row["dispatch_outcome"]}'
               f' ({row["dispatch_parser_id"] or "-"}),'
               f' this reader publishes {row["this_reader_publishes"]}')
        transitions[key] = transitions.get(key, 0) + 1
    summary = {
        "documents_in_the_run": scanned,
        "documents_with_cached_text": with_text,
        "claimed_by_this_registration": len(claimed),
        "claimed_inside_the_named_family": len(inside),
        "claimed_outside_the_named_family": len(outside),
        "named_family_not_claimed": len(family) - len(inside),
        "outsiders_this_reader_publishes": sum(
            1 for row in outside if row["this_reader_publishes"]),
        "outsider_transitions": dict(sorted(transitions.items())),
        "seconds": round(time.perf_counter() - started, 1),
    }
    _emit(args, {"summary": summary, "rows": claimed})
    print("\n# the documents claimed OUTSIDE the named family, by content_sha256")
    for row in sorted(outside, key=lambda item: str(item["content_sha256"])):
        print(json.dumps(row, sort_keys=True))
    print("\n# the named family members this registration does NOT claim")
    for sha in sorted(family - {str(row["content_sha256"]) for row in inside}):
        print(json.dumps({"content_sha256": sha,
                          "was": recorded.get(sha, ("(not in the run)", "", ""))[0]}))
    return 0


# ---------------------------------------------------------------------------
# furniture — the C3 per-printing document counts
# ---------------------------------------------------------------------------

def _furniture_patterns() -> list[tuple[str, "re.Pattern[str]"]]:
    """Each LABEL printing, with the module's own pattern where it has one.

    Two kinds of row are deliberately kept apart, because §COREENC C3 mixed
    them and the mixture is where its days row went wrong: a LABEL the template
    prints, and the REGISTERED pattern that reads a value off it. A member can
    print the label and still not satisfy the pattern — the three
    order-scrambled text layers do exactly that — so the two counts are
    different measurements and both are reported.
    """
    import analysis.core_processor_enclosures as reader

    return [
        ("`Statement Dates` LABEL", re.compile(r"STATEMENT DATES", re.I)),
        ("the period SENTENCE with both `m/dd/yy` dates (registered)",
         reader._PERIOD_RE),
        ("`Average Ledger` LABEL (incl. `… Bal.` / `… Balance`)",
         re.compile(r"AVERAGE LEDGER", re.I)),
        ("the credit-count row welded to the `Average Ledger` cell (registered)",
         reader._LEDGER_STATISTIC_RE),
        ("`Interest Paid` LABEL", re.compile(r"INTEREST PAID", re.I)),
        ("`Interest Paid` WITH a readable figure (the reader's own pattern)",
         reader._INTEREST_RE),
        ("the days LABEL, with or without a count",
         re.compile(reader._PERIOD_DAYS, re.I)),
        ("the days sentence WITH its count (registered)", reader._PERIOD_DAYS_RE),
        ("an enclosures token (`Number of Enclosures` / `… Images` / `Acct. Enclosures`)",
         re.compile(r"NUMBER OF (?:ENCLOSURES|IMAGES)|ACCT\.?\s+ENCLOSURES", re.I)),
        ("`Average Collected`", re.compile(r"AVERAGE COLLECTED", re.I)),
        ("`Total For This Period`", re.compile(r"TOTAL FOR THIS PERIOD", re.I)),
        ("a year-to-date counter label beside it",
         re.compile(r"YEAR[\s-]*TO[\s-]*DATE", re.I)),
    ]


#: The rows of C3 that are about a BLOCK rather than a label. These are read
#: through the module's own `_blocks`, so what is counted is a block the reader
#: actually splits on and reads — not a phrase that happens to occur.
_BLOCK_ROWS = (
    ("a daily-balance grid the reader READS", ("grid",)),
    ("a fee-detail block the reader reads and publishes as no rows", ("charge",)),
    ("a cheque/deposit IMAGE appendix (a boundary, never a block)", ("appendix",)),
    ("a SUMMARY restatement block",
     ("summary_credit", "summary_checks", "summary_debit")),
    ("a date-order undivided ledger", ("dated",)),
)


def _furniture(args: argparse.Namespace) -> int:
    import analysis.core_processor_enclosures as reader

    root = args.data_dir / "artifacts"
    keys = _ocr_keys()
    named = _named(args.shas)
    patterns = _furniture_patterns()

    started = time.perf_counter()
    counts = {label: 0 for label, _pattern in patterns}
    counts.update({label: 0 for label, _roles in _BLOCK_ROWS})
    counts["a ledger header naming a running BALANCE column"] = 0
    read = 0
    for sha in named:
        markdown = _ocr_text(root, sha, keys)
        if markdown is None:
            continue
        read += 1
        upper = markdown.upper()
        for label, pattern in patterns:
            if pattern.search(upper):
                counts[label] += 1
        blocks = reader._blocks(markdown)
        for label, roles in _BLOCK_ROWS:
            if any(blocks.get(role) for role in roles):
                counts[label] += 1
        if reader._RUNNING_BALANCE_RE.search(markdown):
            counts["a ledger header naming a running BALANCE column"] += 1
    summary = {"named": len(named), "documents_read": read,
               "seconds": round(time.perf_counter() - started, 1),
               "documents_printing": counts}
    _emit(args, {"summary": summary})
    print("\n| printing | members |\n|---|---|")
    for label in counts:
        print(f"| {label} | {counts[label]} |")
    return 0


# ---------------------------------------------------------------------------
# signs — the C7 census behind "the banner decides, never the sign"
# ---------------------------------------------------------------------------

def _signs(args: argparse.Namespace) -> int:
    import analysis.core_processor_enclosures as reader
    from analysis.money import MINUS_CLASS
    from analysis.tables import dated_cells

    signed = re.compile(MINUS_CLASS)
    root = args.data_dir / "artifacts"
    keys = _ocr_keys()
    named = _named(args.shas)

    started = time.perf_counter()
    tally = {"debit_signed": 0, "debit_unsigned": 0,
             "credit_signed": 0, "credit_unsigned": 0,
             "undivided_signed": 0, "undivided_unsigned": 0}
    published = 0
    for sha in named:
        markdown = _ocr_text(root, sha, keys)
        if markdown is None:
            continue
        if reader.parse_core_processor_enclosures_statement(markdown) is None:
            continue
        published += 1
        blocks = reader._blocks(markdown)
        running = bool(reader._RUNNING_BALANCE_RE.search(markdown))
        for role, (direction, _serial, restated, _default) in reader._ROLE_READING.items():
            if running and restated:
                continue
            for _name, runs in blocks.get(role, []):
                for run in runs:
                    cells = dated_cells(reader._without_cross_references(run),
                                        date_pattern=reader._DATE_RE,
                                        value_pattern=reader._LEDGER_FIGURE_RE)
                    if cells is None:
                        continue
                    side = {"credit": "credit", "debit": "debit"}.get(
                        direction or "", "undivided")
                    for cell in cells:
                        key = f"{side}_{'signed' if signed.search(cell.value) else 'unsigned'}"
                        tally[key] += 1
    summary = {"named": len(named), "documents_published": published,
               "seconds": round(time.perf_counter() - started, 1), "rows": tally}
    _emit(args, {"summary": summary})
    return 0


# ---------------------------------------------------------------------------
# literals — the privacy scan
# ---------------------------------------------------------------------------

#: Every literal class the standing privacy rule names. Amounts are matched on
#: both sign placements and on the bare-cents form this platform prints.
_LITERAL_RES = (
    re.compile(r"-?\$?\d[\d,]*\.\d{2}-?"),
    re.compile(r"\.\d{2}-?"),
    re.compile(r"\d{1,4}[/-]\d{1,2}(?:[/-]\d{2,4})?"),
    re.compile(r"\d{5,}"),
    re.compile(r"\b[A-Z][A-Za-z]{2,}\b"),
    re.compile(r"\b[A-Za-z]*\d[A-Za-z\d]*\b"),
)
#: Tracked text the base commit already carried is not evidence of a leak.
_TEXTUAL = {".py", ".md", ".txt", ".csv", ".json", ".cfg", ".toml", ".ini",
            ".yml", ".yaml", ".html", ".js", ".css", ".rst", ".sql"}


def _tokens(text: str) -> set[str]:
    found: set[str] = set()
    for pattern in _LITERAL_RES:
        found.update(match.group(0) for match in pattern.finditer(text))
    return found


def _git(root: Path, *argv: str) -> str:
    return subprocess.run(["git", *argv], cwd=root, capture_output=True,
                          text=True, errors="replace").stdout


def _literals(args: argparse.Namespace) -> int:
    root = args.data_dir / "artifacts"
    keys = _ocr_keys()
    named = _named(args.shas)
    repo = args.repo.resolve()

    started = time.perf_counter()
    archive: set[str] = set()
    read = 0
    for sha in named:
        markdown = _ocr_text(root, sha, keys)
        if markdown is None:
            continue
        read += 1
        archive |= _tokens(markdown)

    diff = _git(repo, "diff", f"{args.base}..HEAD")
    added: dict[str, set[str]] = {}
    current = "(no file)"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            added.setdefault(current, set()).update(_tokens(line[1:]))
    added_all: set[str] = set()
    for values in added.values():
        added_all |= values

    raw = archive & added_all
    base_vocabulary: set[str] = set()
    files = 0
    for path in _git(repo, "ls-tree", "-r", "--full-tree", "--name-only", args.base).splitlines():
        if Path(path).suffix.lower() not in _TEXTUAL:
            continue
        files += 1
        base_vocabulary |= _tokens(_git(repo, "show", f"{args.base}:{path}"))
    residual = sorted(raw - base_vocabulary)

    by_file = {name: sorted(values & set(residual)) for name, values in added.items()}
    summary = {
        "named": len(named), "documents_read": read,
        "archive_literals": len(archive),
        "added_lines_literals": len(added_all),
        "base_vocabulary_files": files, "base_vocabulary_literals": len(base_vocabulary),
        "raw_intersection": len(raw),
        "residual_after_the_base_filter": len(residual),
        "residual_by_file": {name: len(values)
                             for name, values in sorted(by_file.items()) if values},
        "seconds": round(time.perf_counter() - started, 1),
    }
    _emit(args, {"summary": summary})
    if args.show_residual:
        print("\n# the residual, for adjudication — NOT committed output")
        for literal in residual:
            printers = sum(1 for name, values in by_file.items() if literal in values)
            print(json.dumps({"literal": literal, "files": printers}))
    return 0


# ---------------------------------------------------------------------------

def _emit(args: argparse.Namespace, report: dict[str, object]) -> None:
    if getattr(args, "out", None) is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    json.dump(report["summary"], sys.stdout, indent=1)
    print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("reach", "furniture", "signs", "literals"))
    parser.add_argument("--data-dir", required=True, type=Path,
                        help="the webapp_data directory")
    parser.add_argument("--shas", required=True, type=Path,
                        help="the named population, one content_sha256 per line")
    parser.add_argument("--rows", type=Path, default=None,
                        help="a run's rows.csv (reach)")
    parser.add_argument("--repo", type=Path, default=Path("."),
                        help="the worktree whose diff is scanned (literals)")
    parser.add_argument("--base", default=None, help="the base commit (literals)")
    parser.add_argument("--show-residual", action="store_true",
                        help="print the residual literals for adjudication (literals)")
    parser.add_argument("--out", type=Path, default=None, help="write the report here")
    args = parser.parse_args(argv)
    if args.mode == "reach" and args.rows is None:
        parser.error("reach needs --rows")
    if args.mode == "literals" and args.base is None:
        parser.error("literals needs --base")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return {"reach": _reach, "furniture": _furniture,
            "signs": _signs, "literals": _literals}[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())

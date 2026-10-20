"""Redact the archive tokens a RECORD carries, by class, without touching a sha.

`W3_TRACKA_LOG.md` is append-only and the train helper rebuilds it byte-exact
from the base log plus one appended section per branch, so a branch may not
edit it — a branch that redacts it cannot be composed. This tool is the answer:
it is committed here, Ocean runs it on the COMPOSED train, and the scan is run
again afterwards. It works on any record file; W3 is only the default.

    python -m tools.fixpriv_w3_redact --data-dir <cold cache> --rows <run>/rows.csv \\
        --base <root commit> [--file docs/... ...] [--write]

WHAT IT REDACTS, and how it decides. Nothing is enumerated: the tool builds the
printed-token universe from the documents themselves exactly as
`privacy_scan_branch` does, subtracts what the tracked tree already carried at
`--base`, applies the SAME committed exclusion table, and then redacts the
residue — the tokens that are archive figures, archive identifiers or archive
dates and are not excused by a rule. A token that no document prints is left
alone, which is why the program's own counts, run ids, session dates and
percentages survive: they are not in the universe.

    class    replacement
    -------  ----------------------
    MONEY    [amount redacted]
    DIGITS   [digits redacted]
    DATES    [date redacted]

`[amount redacted]` is the convention the record already uses (the `bbeeb5c`
redaction of the batch-7 record), so a redacted log stays uniform.

THE SHA RULE. `cc64232` / `bbeeb5c` were regex sweeps and they damaged content
shas — the program's own names for its documents. Here every replacement is a
SPAN found by the scanner's own patterns, and a span that overlaps a 16..64
character hex run is refused outright, twice over: the `hex_sha_substring`
exclusion drops those hits, and the writer checks the span again before it
edits. A sha cannot be shortened by this tool.

BYTE-MINIMAL and IDEMPOTENT. Only the matched spans change; no line is
reflowed, no whitespace is normalised, no other byte moves. Running it twice
changes nothing the second time, because the tokens it replaced are gone from
the file (`--check-idempotent` proves that in one pass without writing).

`--write` edits the files; without it the tool is a DRY RUN and prints counts
by class, by file and by line. Read-only over the archive; artifacts by direct
path; no OCR, no hosted model, $0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.privacy_scan_branch import (  # noqa: E402
    HEX_RUN_RE,
    MONEY_RE,
    NUMERIC_DATE_RE,
    SPELLED_DATE_RE,
    cached_text,
    excluded_by,
    population,
    resolve_run,
    rows_by_sha,
    self_check,
    tokens_of,
    tracked_text,
)
from telemetry.run_of_record import RunOfRecordError, partitions_for_run  # noqa: E402

DEFAULT_FILES = ("docs/moneythumb-replacement/W3_TRACKA_LOG.md",)

REPLACEMENT = {
    "MONEY": "[amount redacted]",
    "DIGITS": "[digits redacted]",
    "DATES": "[date redacted]",
}

#: The scanner's spelled-date pattern, case-insensitive. Spans are taken from
#: the line AS WRITTEN, never from an upper-cased copy: `.upper()` can change a
#: string's LENGTH (`ß` -> `SS`), and an offset computed on a copy of a
#: different length would cut the file in the wrong place.
_SPELLED_ANY_CASE = SPELLED_DATE_RE.pattern
_HEX_ANY_CASE = HEX_RUN_RE.pattern


def spans(line: str, digit_min: int) -> list[tuple[int, int, str, str]]:
    """Every span the scanner's own patterns find, by class, on the line as written."""
    import re

    found: list[tuple[int, int, str, str]] = []
    for match in MONEY_RE.finditer(line):
        found.append((match.start(), match.end(), "MONEY", match.group(0)))
    for match in re.finditer(rf"\d{{{digit_min},}}", line):
        found.append((match.start(), match.end(), "DIGITS", match.group(0)))
    for match in NUMERIC_DATE_RE.finditer(line):
        found.append((match.start(), match.end(), "DATES", match.group(0)))
    for match in re.finditer(_SPELLED_ANY_CASE, line, re.IGNORECASE):
        found.append((match.start(), match.end(), "DATES", match.group(0)))
    return found


def hex_spans(line: str) -> list[tuple[int, int]]:
    import re

    return [(m.start(), m.end()) for m in re.finditer(_HEX_ANY_CASE, line, re.IGNORECASE)]


def redact_line(line: str, residue: dict[str, set[str]], digit_min: int
                ) -> tuple[str, list[str]]:
    """The line with every residue span replaced, and the classes replaced."""
    protected = hex_spans(line)
    chosen: list[tuple[int, int, str]] = []
    for start, end, cls, raw in spans(line, digit_min):
        text = raw.upper()
        if text not in residue.get(cls, ()) and text.replace(",", "") not in residue.get(cls, ()):
            continue
        # THE SHA RULE, checked again at the point of edit.
        if any(start < hend and hstart < end for hstart, hend in protected):
            continue
        chosen.append((start, end, cls))
    if not chosen:
        return line, []
    # Right to left, and never overlapping: a DIGITS run inside a MONEY figure
    # must not be replaced twice, so the widest span at a position wins.
    chosen.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, cls in chosen:
        if kept and start < kept[-1][1]:
            continue
        kept.append((start, end, cls))
    out = line
    for start, end, cls in reversed(kept):
        out = out[:start] + REPLACEMENT[cls] + out[end:]
    return out, [cls for _s, _e, cls in kept]


def main(argv: list[str] | None = None) -> int:
    self_check()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shas", action="append", default=[], type=Path)
    parser.add_argument("--sha", action="append", default=[])
    parser.add_argument("--rows", type=Path, default=None)
    parser.add_argument("--where", action="append", default=[])
    parser.add_argument("--run", type=Path, default=None,
                        help="the discovery run of record whose rows.csv names each sha's "
                             "own OCR provenance (default: the train9 pointer file)")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--base", required=True, help="the ROOT commit for a tree audit")
    parser.add_argument("--file", action="append", default=[], dest="files")
    parser.add_argument("--digit-min", type=int, default=5)
    parser.add_argument("--word-min", type=int, default=4)
    parser.add_argument("--write", action="store_true", help="apply; otherwise DRY RUN")
    parser.add_argument("--check-idempotent", action="store_true",
                        help="redact twice in memory and prove the second pass is a no-op")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    args.run = resolve_run(args.run)

    # Review MINOR-9 (P20-ARTIFACTS Phase 2.0 closure): row-driven
    # run-of-record selection, replacing the live eight-combination
    # `ocr_settings_key()` enumeration that the `OCR_STAGE_VERSION` 4->5
    # bump had already made silently vacuous against the frozen, v4-keyed
    # cold caches this tool actually runs against.
    import sqlite3

    root = args.data_dir / "artifacts"
    shas = population(args)
    printed: dict[str, set[str]] = {c: set() for c in ("MONEY", "DIGITS", "DATES", "WORDS")}
    documents_read = 0
    conn = sqlite3.connect(f"file:{(args.data_dir / 'webapp.db').as_posix()}?mode=ro", uri=True)
    try:
        try:
            partitions = partitions_for_run(args.run, conn=conn)
        except RunOfRecordError as exc:
            print(f"artifact-selection policy failed: {exc}", file=sys.stderr)
            return 5
        rows = rows_by_sha(args.run)
        for sha in shas:
            text = cached_text(conn, root, sha, rows.get(sha), partitions)
            if text is None:
                continue
            documents_read += 1
            for cls, values in tokens_of(text, args.digit_min, args.word_min).items():
                printed[cls].update(values)
    finally:
        conn.close()
    if documents_read == 0:
        print("read 0 documents: the universe is empty and the run would be vacuous",
              file=sys.stderr)
        return 2
    base_all: set[str] = set().union(
        *tokens_of(tracked_text(args.base), args.digit_min, args.word_min).values()
    )

    files = args.files or list(DEFAULT_FILES)
    report: dict[str, object] = {"documents_read": documents_read, "files": {}}
    total = {cls: 0 for cls in REPLACEMENT}
    for name in files:
        path = ROOT / name
        if not path.exists():
            print(f"MISSING {name}", file=sys.stderr)
            return 2
        # newline="" both ways: the file's own line endings are data, and a
        # redaction that silently rewrote every CRLF would not be byte-minimal.
        with path.open(encoding="utf-8", newline="") as handle:
            original = handle.read()
        lines = original.splitlines(keepends=True)
        # The residue for THIS file: printed, not already in the base tree, not
        # excused by the committed exclusion table on this file's own path.
        residue: dict[str, set[str]] = {cls: set() for cls in REPLACEMENT}
        for number, line in enumerate(lines, 1):
            upper = line.upper()
            for cls, values in tokens_of(line, args.digit_min, args.word_min).items():
                if cls not in residue:
                    continue
                for token in values:
                    if token in base_all or token not in printed[cls]:
                        continue
                    if excluded_by(cls, name, token, upper) is not None:
                        continue
                    residue[cls].add(token)
        out_lines: list[str] = []
        by_line: dict[int, dict[str, int]] = {}
        counts = {cls: 0 for cls in REPLACEMENT}
        for number, line in enumerate(lines, 1):
            new, classes = redact_line(line, residue, args.digit_min)
            out_lines.append(new)
            if classes:
                per: dict[str, int] = {}
                for cls in classes:
                    counts[cls] += 1
                    per[cls] = per.get(cls, 0) + 1
                by_line[number] = per
        redacted = "".join(out_lines)
        second = 0
        if args.check_idempotent:
            for line in redacted.splitlines(keepends=True):
                second += len(redact_line(line, residue, args.digit_min)[1])
        report["files"][name] = {  # type: ignore[index]
            "lines": len(lines),
            "residue_tokens": {cls: len(v) for cls, v in residue.items()},
            "redactions": counts,
            "lines_touched": len(by_line),
            "second_pass_redactions": second,
            "bytes_before": len(original.encode("utf-8")),
            "bytes_after": len(redacted.encode("utf-8")),
        }
        for cls in counts:
            total[cls] += counts[cls]
        if args.check_idempotent and second:
            print(f"{name}: the second pass would redact {second} more spans; not idempotent",
                  file=sys.stderr)
            return 3
        if args.write and redacted != original:
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(redacted)
        print(f"{'WROTE ' if args.write else 'DRYRUN'} {name}: "
              + " · ".join(f"{cls} {counts[cls]}" for cls in ("MONEY", "DIGITS", "DATES"))
              + f" · lines touched {len(by_line)} of {len(lines)}")
        for number in sorted(by_line)[:20]:
            per = by_line[number]
            print(f"    line {number}: " + ", ".join(f"{c} x{n}" for c, n in sorted(per.items())))
        if len(by_line) > 20:
            print(f"    … {len(by_line) - 20} more lines")
    report["total"] = total
    print("\n" + json.dumps({"documents_read": documents_read, "total": total}, sort_keys=True))
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

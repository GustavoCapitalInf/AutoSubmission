"""pnc_layout_probe.py — the PNC-LAYOUTS characterisation instrument.

    python -m tools.pnc_layout_probe --parser pnc --family pnc_core_commercial_checking \
        --group WH:pnc --group DECL:pnc [--out <private>.md]

Reads each cohort document's cached text from the run of record's cold cache
(the same access `tools/cohort_replay.py` uses; read-only, no OCR, no model,
$0) and reports SHAPES and GATE NAMES only — never a printed value. Every
figure it prints is a count, a ratio or the name of a shape.

What it measures, and why each column exists
--------------------------------------------
* **masthead / period / summary / activity anchor** — the four markers
  `analysis/pnc.py` needs before it can read anything. A document that fails
  one of them is unclaimed or declined for a reason that is a MARKER problem,
  not a grammar problem, and the two need different work.
* **continuation marker** — PNC prints a section's continuation heading as
  `<name> <sep>- continued`, and the separator is not always a space: the
  archive prints it as a space, as a TAB, and as a C0 CONTROL BYTE. A grammar
  written with `\\s+` reads the first two and silently drops every page after
  the first on the third, which is a whole-section loss that no printed total
  can see unless the parser checks one.
* **date column** — the row grammar reads `mm/dd <amount> <description>`. On
  some native prints the flattening emits the date column as its OWN runs,
  detached from the amounts and split across several lines (`04 04 04` on one
  line, `/08 /10 /10` on another). The days are printed; the CORRESPONDENCE
  between a day and a row is geometry, and the flattened layer does not carry
  it. This probe names the shape; it does not guess the pairing.
* **section identity** — PNC prints its own index of the sections it itemises
  (`Description Items Amount` with a per-category item count and total, and a
  `Total` row per direction) or restates each section's count and total on the
  section's own heading line. The probe reports how many printed categories the
  reader reproduces EXACTLY (count and total), how many it reads short, how many
  it reads LONG, and how many sections it reads that the index does not print.
* **daily grid** — the day-sensitive oracle. The probe reports the grid's shape
  (`inline_pairs`, `date_column_detached`, `absent`), the number of dated pairs
  it can read, and whether the grid's own last day agrees with the printed
  closing balance (`agrees` / `contradicts`), which is what separates a grid
  that can corroborate a ledger from one that cannot.

The classification each row earns is in the last column: `shared_shape`
(a layout the reader can be widened to), `refusal` (the printed evidence does
not support publication) or `document_defect` (the document contradicts itself
or its own text layer lost printed rows).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from tools.cohort_replay import (
    ColdCache,
    DEFAULT_CENSUS,
    DEFAULT_DATA_DIR,
    DEFAULT_RUN_POINTER,
    load_baseline_rows,
    load_census,
    select_cohort,
)


def resolve_run(run: Path | None) -> Path:
    """The run of record, from `--run` or the committed pointer file."""
    if run is not None:
        return run
    return Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())

#: `<name>` `<separator>` `- continued`. The separator classes the archive
#: prints, most specific first; `plain` is the ordinary space.
_CONTINUATION = (
    ("control_byte", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]-\s*continued")),
    ("tab", re.compile(r"\t-\s*continued")),
    ("plain", re.compile(r"(?m)^\S[^\n]*?\s-\s+continued\s*$")),
)
#: A date column that stands on its own line — either the month halves
#: (`04 04 04`) or the day halves (`/08 /10 /10`) of a `mm/dd` column that the
#: flattening emitted apart from the rows they belong to.
_DETACHED_MONTHS = re.compile(r"(?m)^\s*(?:\d{2}\s+){0,}\d{2}\s*$")
_DETACHED_DAYS = re.compile(r"(?m)^\s*/\d{2}(?:\s+/\d{2})*\s*$")
#: A grid pair as PNC prints it in the `Date | balance` ladders: `04/01 1,000.00`
#: or `04/01 1,000.00-` (negatives carry a TRAILING minus).
_GRID_PAIR = re.compile(r"(\d{2}/\d{2})\s+(\d[\d,]*\.\d{2}|\.\d{2})(-?)")
_GRID_HEADS = ("Daily Balance Detail", "Daily Balance", "Ledger Balance")
#: The printed index of the itemised sections, and the per-direction `Total`.
_INDEX_ROW = re.compile(r"([A-Z][A-Za-z/.&' ]+?)\s+(\d+)\s+(\d[\d,]*\.\d{2}|\.\d{2})")
#: The index and the detail heading spell some sections differently; the probe
#: reads the reader's own table so the two never drift apart.

#: The two forms in which a section restates its OWN count and total on its
#: heading line: the treasury/commercial `<n> transactions for a total of $x`
#: and the consumer `There were <n> ... totaling $x.`
_HEADING_COUNT = re.compile(r"(\d+)\s+transactions?\s+for a total of\s+\$(\d[\d,]*\.\d{2}|\.\d{2})")
_PROSE_COUNT = re.compile(r"There were\s+(\d+)\s+[^.$]*?totaling\s+\$(\d[\d,]*\.\d{2}|\.\d{2})")

_MASTHEADS = (
    ("core_commercial", "PNC Core Commercial Checking Account Statement"),
    ("virtual_wallet", "Virtual Wallet With Performance Spend Statement"),
    ("treasury_plan", "Treasury Enterprise Plan"),
    ("business_checking", "Business Checking"),
)


def _money(token: str) -> float:
    from analysis.pnc import _money as reader_money

    return reader_money(token) or 0.0


def layout_of(markdown: str) -> str:
    for name, marker in _MASTHEADS:
        if marker in markdown:
            return name
    return "unknown"


def continuation_shape(markdown: str) -> str:
    hits = [name for name, pattern in _CONTINUATION if pattern.search(markdown)]
    return "+".join(hits) if hits else "none"


def date_column_shape(markdown: str) -> str:
    """`inline` when the rows carry their own date, `detached` when the column
    stands apart, `mixed` when both forms occur in one document."""
    inline = len(re.findall(r"(?m)\d{2}/\d{2}\s+(?:\d[\d,]*\.\d{2}|\.\d{2})\s+\S", markdown))
    detached = len(_DETACHED_DAYS.findall(markdown))
    if detached and inline:
        return "mixed"
    if detached:
        return "detached"
    return "inline" if inline else "none"


def grid_shape(markdown: str) -> tuple[str, int]:
    """The daily grid's shape and the number of dated pairs readable from it."""
    for head in _GRID_HEADS:
        match = re.search(rf"(?m)^{re.escape(head)}\b", markdown)
        if match:
            break
    else:
        return "absent", 0
    block = markdown[match.end():]
    stop = re.search(r"(?m)^(?:Activity Detail|Deposits and Other (?:Credits|Additions))\s*$", block)
    if stop:
        block = block[: stop.start()]
    pairs = _GRID_PAIR.findall(block)
    if pairs:
        return "inline_pairs", len(pairs)
    if _DETACHED_DAYS.search(block) or _DETACHED_MONTHS.search(block):
        return "date_column_detached", 0
    return "unreadable", 0


def grid_agrees_with_closing(markdown: str, closing: float | None) -> str:
    shape, count = grid_shape(markdown)
    if shape != "inline_pairs" or closing is None or not count:
        return "n/a"
    for head in _GRID_HEADS:
        match = re.search(rf"(?m)^{re.escape(head)}\b", markdown)
        if match:
            break
    block = markdown[match.end():]
    stop = re.search(r"(?m)^(?:Activity Detail|Deposits and Other (?:Credits|Additions))\s*$", block)
    if stop:
        block = block[: stop.start()]
    days: dict[str, float] = {}
    for day, amount, minus in _GRID_PAIR.findall(block):
        days[day] = -_money(amount) if minus else _money(amount)
    if not days:
        return "n/a"
    last = days[max(days)]
    return "agrees" if abs(last - closing) < 0.005 else "contradicts"


def printed_index(markdown: str) -> dict[str, tuple[int, float]]:
    """The `Description Items Amount` index, category -> (items, total)."""
    entries: dict[str, tuple[int, float]] = {}
    for block in re.finditer(r"Description\s+Items\s+Amount(?P<body>.*?)"
                             r"(?=Description\s+Items\s+Amount|\n\s*\n|$)",
                             markdown, re.DOTALL):
        body = block.group("body")
        for head in _GRID_HEADS:
            body = body.split(head)[0]
        for name, items, amount in _INDEX_ROW.findall(body):
            from analysis.pnc import _SECTION_ALIASES

            key = _SECTION_ALIASES.get(name.strip(), name.strip())
            entries[key] = (int(items), _money(amount))
    entries.pop("Total", None)
    return entries


def heading_oracles(markdown: str) -> dict[str, tuple[int, float]]:
    """Sections that restate their own count and total on the heading line."""
    entries: dict[str, tuple[int, float]] = {}
    for line in markdown.splitlines():
        for pattern in (_HEADING_COUNT, _PROSE_COUNT):
            found = pattern.findall(line)
            if not found:
                continue
            name = line[: pattern.search(line).start()].strip()
            name = re.sub(r"\s*[\x00-\x1f]?-\s*continued\s*$", "", name).strip()
            if not name:
                continue
            entries[name] = (sum(int(n) for n, _ in found),
                             round(sum(_money(a) for _, a in found), 2))
    return entries


def reader_gate(markdown: str) -> str:
    """The FIRST link of `parse_pnc_statement`'s own chain that refuses."""
    from analysis import pnc

    if not pnc.detect(markdown).claims:
        return "detect"
    if pnc._period(markdown) is None:
        return "_period"
    if pnc._summary_amounts(markdown) is None:
        return "_summary_amounts"
    statement = pnc.parse_pnc_statement(markdown)
    if statement is None:
        return "no rows"
    return "parses"


def section_identity(markdown: str) -> dict[str, int]:
    """How the reader's per-section capture stands against the printed index."""
    from analysis import pnc

    out = {"exact": 0, "short": 0, "long": 0, "unindexed": 0, "printed": 0}
    period = pnc._period(markdown)
    if period is None:
        return out
    printed = printed_index(markdown)
    printed.update(heading_oracles(markdown))
    printed.pop("Total", None)
    out["printed"] = len(printed)
    rows_by_section = pnc._captured_sections(markdown, year=int(period[1][:4]))
    if rows_by_section is None:
        return out
    captured = {name: (len(rows), round(sum(abs(row.amount) for row in rows), 2))
                for name, rows in rows_by_section.items()}
    for name, (items, total) in printed.items():
        got_items, got_total = captured.get(name, (0, 0.0))
        if (got_items, got_total) == (items, total):
            out["exact"] += 1
        elif got_items > items:
            out["long"] += 1
        else:
            out["short"] += 1
    for name, (items, _total) in captured.items():
        if items and name not in printed:
            out["unindexed"] += 1
    return out


def classify(row: dict) -> str:
    if row["gate"] != "parses":
        return "marker_or_grammar_gap" if row["layout"] != "unknown" else "refusal"
    if row["grid_vs_closing"] == "contradicts":
        return "document_defect"
    if row["date_column"] in ("detached", "mixed") and row["short"]:
        return "refusal (date column detached)"
    if row["short"] or row["long"] or row["unindexed"]:
        return "row_capture_gap"
    return "shared_shape"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--shas", type=Path, default=None)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--parser", action="append", default=[])
    parser.add_argument("--folder", action="append", default=[])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    run = resolve_run(args.run)
    rows = load_baseline_rows(run)
    census = load_census(args.census)
    cohort = select_cohort(args, rows, census)

    lines = [f"# pnc layout probe — {args.label or 'unlabelled'} — run `{run.name}`", "",
             f"population {len(cohort)}", "",
             "| sha16 | baseline | layout | period | continuation | date column | grid | pairs | "
             "grid vs closing | gate | printed | exact | short | long | unindexed | class |",
             "|---|---|---|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---|"]
    cache = ColdCache(args.data_dir)
    tally: dict[str, int] = {}
    for sha in cohort:
        markdown, _pages = cache.text(sha)
        if markdown is None:
            lines.append(f"| `{sha[:16]}` | no_text |" + " — |" * 14)
            continue
        from analysis import pnc

        summary = pnc._summary_amounts(markdown)
        row = {
            "layout": layout_of(markdown),
            "gate": reader_gate(markdown),
            "date_column": date_column_shape(markdown),
            "grid_vs_closing": grid_agrees_with_closing(markdown, summary[3] if summary else None),
        }
        shape, pairs = grid_shape(markdown)
        identity = section_identity(markdown)
        row.update(identity)
        period = ("capital" if re.search(r"For the Period\s+\d{2}/\d{2}/\d{4}", markdown)
                  else "lowercase" if re.search(r"For the period\s+\d{2}/\d{2}/\d{4}", markdown)
                  else "absent")
        klass = classify(row)
        tally[klass] = tally.get(klass, 0) + 1
        base = rows.get(sha, {})
        lines.append(
            f"| `{sha[:16]}` | {base.get('outcome_class', '?')}/{base.get('outcome_reason', '?')} "
            f"| {row['layout']} | {period} | {continuation_shape(markdown)} | {row['date_column']} "
            f"| {shape} | {pairs} | {row['grid_vs_closing']} | {row['gate']} | {identity['printed']} "
            f"| {identity['exact']} | {identity['short']} | {identity['long']} "
            f"| {identity['unindexed']} | {klass} |")
    lines += ["", "| class | documents |", "|---|---:|"]
    lines += [f"| {name} | {count} |" for name, count in sorted(tally.items())]
    report = "\n".join(lines)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

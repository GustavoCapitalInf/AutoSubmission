"""rowcap_ceiling.py — what row capture could still be worth, per document.

    python -m tools.rowcap_ceiling --run <run dir> --data-dir <cold cache>
        --shas <population> [--mode as_is|wrapped_amount] [--out <private>.md]

A coverage card owes a measured ceiling for every document it leaves withheld.
This asks two questions of the PAPER, before asking anything of the reader, and
one of the reader:

* **does the bank's own summary close?** `opening + printed credits - printed
  debits == printed closing`, from the four printed figures alone. A document
  whose own summary does not close cannot be closed by capturing rows: nothing
  a reader may do makes a statement agree with itself, and inventing the
  difference is the repair doctrine's refusal.
* **do the captured magnitudes total the printed pair?** Reported as a RATIO of
  `printed credits + printed debits`. At 1.000 the reader holds every printed
  figure and only the COLUMN each was printed in is lost, which is a solvable
  problem; away from 1.000 printed cells are missing or misread, which is not
  something the reader's row grammar can recover.
* **the one reading available inside the reader.** `--mode wrapped_amount`
  re-runs the RBC grid with a line carrying ONLY money cells joined to the
  description line above it, which is how this layout sets a row whose
  description ran the width of the column. Patched in memory, never on disk.

Ratios, counts, names and outcome classes only: no amount, no date, no
description and no account number reaches the report. Read-only over the
archive and the cold cache; no OCR, no model, $0.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rowcap_probe import ColdCache, DEFAULT_DATA_DIR, DEFAULT_RUN_POINTER, load_rows  # noqa: E402

MODES = ("as_is", "wrapped_amount")


def _cells_only(text: str, pattern) -> bool:
    """True when the whole line is money cells and the gaps between them."""
    cells = list(pattern.finditer(text))
    if not cells:
        return False
    if text[:cells[0].start()].strip() or text[cells[-1].end():].strip():
        return False
    return all(not text[a.end():b.start()].strip() for a, b in zip(cells, cells[1:]))


def install_wrapped_amount() -> None:
    """RBC only: a money-only line continues the description line above it.

    The grid reader pairs two money cells with nothing between them as one
    row's amount and its running balance. Across a LINE BREAK that pairing is
    wrong on this layout: a description that ran the width of its column pushes
    its own amount onto the next line, and the previous row — still open,
    because a description-only line does not close it — takes that amount as
    its balance. Joining the two entries before the grid sees them makes the
    amount belong to the description it was printed under.

    Installed by rebinding the name `analysis.rbc` imported, so nothing else in
    the process is affected and nothing is written to disk.
    """
    import analysis.rbc as rbc
    from analysis.tables import read_grid_rows as real

    def wrapped(entries, **kwargs):
        joined: list = []
        for entry in entries:
            text, tx_date, opens = entry
            if (joined and not opens and _cells_only(text, rbc._MONEY_RE)
                    and joined[-1][0].strip()
                    and not rbc._MONEY_RE.search(joined[-1][0])):
                previous = joined[-1]
                joined[-1] = (f"{previous[0]} {text}", previous[1], previous[2])
                continue
            joined.append(entry)
        return real(joined, **kwargs)

    rbc.read_grid_rows = wrapped


def _ratio(numerator, denominator) -> str:
    if numerator is None or not denominator:
        return "-"
    return f"{numerator / denominator:.3f}"


def measure(markdown: str) -> dict:
    from analysis.pipeline import analyze_markdown
    from analysis.serialization import report_to_dict
    from telemetry.record import classify_outcome

    report = analyze_markdown(markdown, parse_mode="deterministic")
    statement = report.statement
    klass, reason = classify_outcome(report_to_dict(report))
    postings = list(statement.transactions or [])

    printed_pair = None
    if statement.stated_total_credits is not None and statement.stated_total_debits is not None:
        printed_pair = statement.stated_total_credits + statement.stated_total_debits

    summary_closes = "-"
    if (statement.beginning_balance is not None and statement.ending_balance is not None
            and statement.stated_total_credits is not None
            and statement.stated_total_debits is not None):
        residue = (statement.beginning_balance + statement.stated_total_credits
                   - statement.stated_total_debits - statement.ending_balance)
        summary_closes = "yes" if abs(residue) <= 0.005 else "no"

    stated_count = None
    if statement.stated_credit_count is not None and statement.stated_debit_count is not None:
        stated_count = statement.stated_credit_count + statement.stated_debit_count

    return {
        "class": f"{klass}/{reason}",
        "rows": len(postings),
        "count_ratio": _ratio(len(postings), stated_count),
        "magnitude_ratio": _ratio(sum(abs(t.amount or 0.0) for t in postings), printed_pair),
        "summary_closes": summary_closes,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--shas", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, default="as_is")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    rows = load_rows(args.run)
    wanted = {line.strip().upper() for line in
              args.shas.read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.strip().startswith("#")}
    chosen = sorted(sha for sha in rows if sha in wanted or sha[:16] in wanted)

    if args.mode == "wrapped_amount":
        install_wrapped_amount()

    cache = ColdCache(args.data_dir)
    lines = [f"# rowcap ceiling — mode `{args.mode}`", "",
             "| sha16 | outcome | rows | rows / printed count | captured magnitude / "
             "printed pair | the bank's own summary closes |",
             "|---|---|---:|---:|---:|---|"]
    for sha in chosen:
        markdown = cache.text(sha)
        if markdown is None:
            lines.append(f"| {sha[:16]} | no text | - | - | - | - |")
            continue
        try:
            fact = measure(markdown)
        except Exception as error:  # noqa: BLE001 — a ceiling never stops on one document
            lines.append(f"| {sha[:16]} | raised {type(error).__name__} | - | - | - | - |")
            continue
        lines.append(f"| {sha[:16]} | {fact['class']} | {fact['rows']} "
                     f"| {fact['count_ratio']} | {fact['magnitude_ratio']} "
                     f"| {fact['summary_closes']} |")
    table = "\n".join(lines) + f"\n\ndocuments {len(chosen)}\n"
    print(table)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

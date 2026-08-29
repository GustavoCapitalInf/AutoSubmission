"""commsec_identity_ceiling.py — what a `community_section` reader COULD reach.

    python -m tools.commsec_identity_ceiling --run <run> --data-dir <cold cache> \
        --shas <file> [--mode structure|sign_search|publish] [--out <private>.md]

The decline probe says WHICH link refuses. This says whether any reader of this
module could publish the document at all — measured, not argued, in the shape
`tools/huntington_identity_ceiling.py` and `tools/cpdecl_identity_ceiling.py`
established: replay the cohort with a DIFFERENT reading in memory (the tree on
disk is never touched) and classify with the platform's own
``telemetry.record.classify_outcome``.

The question it exists for is the two `DECL:community_section` documents that
are not L-1 refusals. Both print sub-layout J-B's `Account Activity` ledger
under the header ``Post Date Description Debits Credits Balance`` — and print
**one figure per posting row**. The row's DIRECTION is the COLUMN the bank
printed that figure in, and the flattened text layer emits one space-separated
run with no column geometry at all, so the direction is not in the reader's
input. The running balance the J-B reader signs a row by is blank on every
posting row; it is printed only on the two bookends.

So the only mechanical route to a direction is to SOLVE for it against the
printed identities. Three modes measure exactly how far that reaches:

``structure``
    the shape, per document: rows, figures per row, rows carrying a running
    balance, distinct posting days, days carrying more than one row, printed
    grid days, and whether the row figures sum to the bank's own two printed
    totals (the control that says the single figure is an AMOUNT and not a
    balance).

``sign_search``
    every assignment of a direction to every posting row that satisfies ALL of
    the printed identities at once — both printed counts, both printed totals,
    and every day of the printed daily-balance grid — counted EXACTLY by a
    per-day dynamic program rather than sampled. The grid fixes each day's net
    change, so a day's credit total is determined; what is not determined is
    WHICH of that day's rows make it up. The verdict is
    ``no_reading_exists`` / ``UNIQUE_READING`` / ``ambiguous(n)``.

``publish``
    where the search returns a unique reading, build the statement from it in
    memory and run the platform's own classifier over it — so the ceiling is a
    ladder outcome and not a claim about one.

READ-ONLY, $0, and it never prints a document value: counts, booleans, verdicts
and outcome names only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_RUN_POINTER = Path("discovery_reports/train8-logs/train8_run_dir.txt")
DEFAULT_DATA_DIR = Path(".claude/recovery/webapp_data_train8_cold")
DEFAULT_CLUSTERS = Path("docs/moneythumb-replacement/census_batch9/clusters.json")

#: Cap on the solution count. A document with more readings than this is
#: `ambiguous` whatever the exact number is, and the exact number is not worth
#: an unbounded integer.
_SOLUTION_CAP = 1_000_000


def _cents(value: float) -> int:
    return int(round(value * 100))


# ---------------------------------------------------------------------------
# the printing, read as far as it can be read
# ---------------------------------------------------------------------------

class Reading:
    """One account block's activity ledger, with the directions left OPEN."""

    __slots__ = ("ok", "why", "beginning", "ending", "credits", "debits",
                 "credit_count", "debit_count", "postings", "bookends", "grid",
                 "start", "end")

    def __init__(self, **kwargs):
        for name in self.__slots__:
            setattr(self, name, kwargs.get(name))


def read_block(block: str) -> Reading:
    """The block's summary, its printed grid and its undirected posting rows."""
    from analysis import community_section as M

    summary = M._summary(block)
    if summary is None:
        return Reading(ok=False, why="no_summary")
    beginning, ending = M._balance(summary.beginning), M._balance(summary.ending)
    credits, debits = M._money(summary.credits), M._money(summary.debits)
    if None in (beginning, ending, credits, debits):
        return Reading(ok=False, why="summary_figure_not_money")

    text = M._clean(block)
    header = M._ACTIVITY_HEADER_RE.search(text)
    if not header:
        return Reading(ok=False, why="no_activity_header")
    stop = M._ACTIVITY_END_RE.search(text, header.end())
    body = text[header.end():stop.start() if stop else len(text)]

    #: One posting row: `(iso, amount-or-None, description, figures on the row,
    #: the LAST figure read as a signed balance)`. The last figure is kept in
    #: both readings because which one it IS is the question this instrument
    #: exists to answer — an amount on a ledger that leaves the `Balance`
    #: column blank, a running balance on one that prints it.
    postings: list[tuple[str, float | None, str, int, float | None]] = []
    bookends: list[tuple[str, float, str]] = []
    for part in re.split(r"(?=\b" + M._DATE + r"\s)", body):
        match = re.match(r"(" + M._DATE + r")\s+(.*)", part.strip(), re.DOTALL)
        if not match:
            continue
        rest = M._SECTION_TRAILER_RE.sub(" ", match.group(2))
        monies = list(re.finditer(M._SIGNED_MONEY, rest))
        if not monies:
            continue
        description = re.sub(r"\s+", " ", rest[:monies[-1].start()]).strip()
        try:
            iso = M._iso(match.group(1))
        except ValueError:
            return Reading(ok=False, why="row_date_not_a_date")
        if re.search(r"\b(?:Beginning|Ending)\s+Balance\b", description, re.IGNORECASE):
            balance = M._balance(monies[-1].group())
            if balance is None:
                return Reading(ok=False, why="bookend_not_money")
            bookends.append((iso, balance,
                             "beginning" if "beginn" in description.lower() else "ending"))
            continue
        postings.append((iso, M._money(monies[-1].group()), description, len(monies),
                         M._balance(monies[-1].group())))

    try:
        grid = M._daily_balances(block)
    except ValueError:
        return Reading(ok=False, why="grid_day_printed_twice")

    return Reading(ok=True, why="", beginning=beginning, ending=ending,
                   credits=credits, debits=debits,
                   credit_count=int(summary.credit_count),
                   debit_count=int(summary.debit_count),
                   postings=postings, bookends=bookends, grid=grid,
                   start=summary.start_date, end=summary.end_date)


def structure(reading: Reading) -> dict:
    """The shape of the printing, in counts and booleans."""
    if not reading.ok:
        return {"readable": False, "why": reading.why}
    figures: dict[int, int] = {}
    for _iso, _amount, _desc, count, _balance in reading.postings:
        figures[count] = figures.get(count, 0) + 1
    days: dict[str, int] = {}
    for iso, _amount, _desc, _count, _balance in reading.postings:
        days[iso] = days.get(iso, 0) + 1
    unsigned = [a for _i, a, _d, _c, _b in reading.postings if a is not None]
    total = round(sum(unsigned), 2)
    #: Is the `Balance` column PRINTED on posting rows? Measured, not assumed:
    #: a row that carries its running balance ends on the balance the printed
    #: daily grid gives for that row's own day, on the LAST row of the day. On
    #: a ledger that prints the column this is one per posting day; on one that
    #: leaves it blank it is zero, and the last figure is the amount instead.
    last_row_of_day: dict[str, float | None] = {}
    for iso, _amount, _desc, _count, balance in reading.postings:
        last_row_of_day[iso] = balance
    carried = sum(
        1 for iso, balance in last_row_of_day.items()
        if balance is not None and iso in reading.grid
        and abs(balance - reading.grid[iso]) <= 0.005)
    return {
        "readable": True,
        "posting_rows": len(reading.postings),
        "figures_per_row": dict(sorted(figures.items())),
        "rows_whose_last_figure_is_unsigned": len(unsigned),
        "posting_days_whose_last_row_ends_on_that_days_printed_balance": carried,
        "stated_row_count": reading.credit_count + reading.debit_count,
        "row_count_matches_stated": len(reading.postings) == reading.credit_count + reading.debit_count,
        "row_figures_sum_to_both_stated_totals":
            abs(total - round(reading.credits + reading.debits, 2)) <= 0.02,
        "summary_closes":
            abs(round(reading.beginning + reading.credits - reading.debits
                      - reading.ending, 2)) <= 0.02,
        "bookends": sorted(kind for _i, _v, kind in reading.bookends),
        "bookends_match_summary": {
            "beginning": any(k == "beginning" and abs(v - reading.beginning) <= 0.005
                             for _i, v, k in reading.bookends),
            "ending": any(k == "ending" and abs(v - reading.ending) <= 0.005
                          for _i, v, k in reading.bookends)},
        "printed_grid_days": len(reading.grid),
        "distinct_posting_days": len(days),
        "posting_days_with_more_than_one_row": sum(1 for n in days.values() if n > 1),
        "max_rows_on_a_day": max(days.values()) if days else 0,
        "posting_days_in_the_printed_grid": sum(1 for d in days if d in reading.grid),
        "grid_days_with_no_posting": sum(1 for d in reading.grid if d not in days),
    }


#: A printed row of the activity ledger, in the RAW text: the date opens it and
#: the figure closes it. Deliberately not `_clean`ed — this is the one read that
#: needs the printed spacing intact, because the question is whether the column
#: the bank printed the figure in survives into the text at all.
_RAW_ROW_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s(.*?)(\s+)(-?\$[\d,]+\.\d{2})\s*$")


def column_evidence(markdown: str) -> dict:
    """Does the DIRECTION column survive the flattening?

    On this layout the header is ``Post Date Description Debits Credits
    Balance`` and a posting row's direction is WHICH of the two money columns
    its figure was printed in. A text layer that keeps column geometry would
    have to keep it as spacing (there is nothing else left), so this measures
    the whitespace run immediately before every row-closing figure. One space
    on every row means the geometry is gone and the direction is not in the
    reader's input — the bound this instrument's refusal stands on.

    A COUNT of characters, never a character of the document.
    """
    widths: dict[int, int] = {}
    trailing: dict[str, int] = {}
    for line in markdown.splitlines():
        match = _RAW_ROW_RE.match(line.rstrip("\n"))
        if not match:
            continue
        widths[len(match.group(3))] = widths.get(len(match.group(3)), 0) + 1
        tail = line.rstrip("\n")[match.end(4):]
        trailing[str(len(tail))] = trailing.get(str(len(tail)), 0) + 1
    return {"rows_measured": sum(widths.values()),
            "gap_widths_before_the_figure": dict(sorted(widths.items())),
            "distinct_gap_widths": len(widths),
            "characters_after_the_figure": dict(sorted(trailing.items()))}


# ---------------------------------------------------------------------------
# the search
# ---------------------------------------------------------------------------

def sign_search(reading: Reading) -> dict:
    """EXACTLY how many direction assignments satisfy every printed identity.

    The printed grid fixes each posting day's net change, and a day's rows have
    a known gross, so the day's CREDIT total is determined:
    ``credit_day = (net + gross) / 2``. What the printing does not determine is
    which of that day's rows make it up — so the count of readings is, per day,
    the number of subsets of that day's amounts summing to `credit_day`, indexed
    by how many rows the subset holds, and across days a convolution over the
    total credit COUNT, which the summary prints.

    Exact and complete: no sampling, no early exit on the first solution.
    """
    if not reading.ok:
        return {"verdict": "unreadable", "why": reading.why}
    if not reading.postings:
        return {"verdict": "no_reading_exists", "why": "no_posting_rows"}
    if len(reading.postings) != reading.credit_count + reading.debit_count:
        return {"verdict": "no_reading_exists", "why": "row_count_disagrees_with_stated"}

    if any(amount is None for _i, amount, _d, _c, _b in reading.postings):
        # A row whose last figure carries a sign is a BALANCE, not an amount;
        # this search is only defined where every row's figure is the amount.
        return {"verdict": "no_reading_exists", "why": "row_figure_is_signed"}
    days: dict[str, list[int]] = {}
    for iso, amount, _desc, _count, _balance in reading.postings:
        days.setdefault(iso, []).append(_cents(amount))
    grid = {day: _cents(balance) for day, balance in reading.grid.items()}
    if not grid:
        return {"verdict": "no_reading_exists", "why": "no_printed_grid"}
    missing = [day for day in days if day not in grid]
    if missing:
        return {"verdict": "no_reading_exists", "why": "posting_day_not_in_the_printed_grid"}

    # Walk the printed grid in date order; a grid day with no postings must
    # repeat the previous balance, and a day with postings must move by the
    # net of its own rows.
    previous = _cents(reading.beginning)
    per_day: list[tuple[int, list[int]]] = []      # (credit_cents, amounts)
    for day in sorted(grid):
        balance = grid[day]
        amounts = days.get(day, [])
        net = balance - previous
        gross = sum(amounts)
        if not amounts:
            if net != 0:
                return {"verdict": "no_reading_exists",
                        "why": "grid_day_with_no_posting_moves_the_balance"}
            previous = balance
            continue
        if (net + gross) % 2 != 0 or not 0 <= (net + gross) // 2 <= gross:
            return {"verdict": "no_reading_exists", "why": "day_net_unreachable"}
        per_day.append(((net + gross) // 2, amounts))
        previous = balance
    if previous != _cents(reading.ending):
        return {"verdict": "no_reading_exists", "why": "grid_does_not_end_on_the_closing"}

    # Per day: subsets summing to `credit_cents`, counted by subset SIZE.
    per_day_counts: list[dict[int, int]] = []
    for credit_cents, amounts in per_day:
        table: dict[tuple[int, int], int] = {(0, 0): 1}
        for amount in amounts:
            nxt = dict(table)
            for (total, size), ways in table.items():
                if total + amount > credit_cents:
                    continue
                key = (total + amount, size + 1)
                nxt[key] = min(nxt.get(key, 0) + ways, _SOLUTION_CAP)
            table = nxt
        sizes = {size: ways for (total, size), ways in table.items()
                 if total == credit_cents}
        if not sizes:
            return {"verdict": "no_reading_exists", "why": "day_credit_total_not_a_subset"}
        per_day_counts.append(sizes)

    # Across days: convolve on the total number of credit rows.
    combined: dict[int, int] = {0: 1}
    for sizes in per_day_counts:
        nxt: dict[int, int] = {}
        for have, ways in combined.items():
            for size, more in sizes.items():
                if have + size > reading.credit_count:
                    continue
                nxt[have + size] = min(nxt.get(have + size, 0) + ways * more,
                                       _SOLUTION_CAP)
        combined = nxt
        if not combined:
            break
    solutions = combined.get(reading.credit_count, 0)
    if solutions == 0:
        return {"verdict": "no_reading_exists", "why": "credit_count_unreachable"}
    verdict = "UNIQUE_READING" if solutions == 1 else f"ambiguous({solutions})"
    return {"verdict": verdict, "solutions": solutions,
            "days_searched": len(per_day),
            "days_with_more_than_one_subset":
                sum(1 for sizes in per_day_counts if sum(sizes.values()) > 1)}


def unique_assignment(reading: Reading) -> list[int] | None:
    """The one direction per posting row, when exactly one reading exists."""
    if sign_search(reading).get("verdict") != "UNIQUE_READING":
        return None
    days: dict[str, list[int]] = {}
    for index, (iso, _a, _d, _c, _b) in enumerate(reading.postings):
        days.setdefault(iso, []).append(index)
    grid = {day: _cents(balance) for day, balance in reading.grid.items()}
    amounts = [_cents(a) for _i, a, _d, _c, _b in reading.postings]
    signs = [-1] * len(reading.postings)
    previous = _cents(reading.beginning)
    for day in sorted(grid):
        indices = days.get(day, [])
        if not indices:
            previous = grid[day]
            continue
        gross = sum(amounts[i] for i in indices)
        credit_cents = (grid[day] - previous + gross) // 2
        chosen = _one_subset(indices, amounts, credit_cents)
        if chosen is None:
            return None
        for i in chosen:
            signs[i] = 1
        previous = grid[day]
    return signs


def _one_subset(indices: list[int], amounts: list[int], target: int) -> list[int] | None:
    """Any subset of `indices` whose amounts sum to `target` (uniqueness proved
    already by `sign_search`, so 'any' is 'the')."""
    reachable: dict[int, list[int]] = {0: []}
    for i in indices:
        nxt = dict(reachable)
        for total, picked in reachable.items():
            if total + amounts[i] <= target:
                nxt.setdefault(total + amounts[i], picked + [i])
        reachable = nxt
    return reachable.get(target)


def solved_rows(block: str, *, year: int) -> list:
    """`_activity_rows`' signature, answered by the SEARCH instead of by a balance.

    The in-memory replacement the `publish` mode installs. It publishes the
    unique reading and NOTHING otherwise — an ambiguous printing returns `[]`,
    which is the decline the reader already makes.
    """
    from analysis.schema import Transaction

    reading = read_block(block)
    signs = unique_assignment(reading)
    if signs is None:
        return []
    rows = [
        Transaction(date=iso, description=description,
                    amount=round(sign * amount, 2),
                    direction="credit" if sign > 0 else "debit")
        for (iso, amount, description, _count, _balance), sign
        in zip(reading.postings, signs)
    ]
    return rows if all(int(row.date[:4]) == year for row in rows) else []


def publish(markdown: str, pages: list[str]) -> dict:
    """What the PLATFORM says when the unique reading is installed in memory.

    The tree on disk is never touched: `analysis.community_section._activity_rows`
    is rebound for the duration of one replay and restored in a `finally`, and
    the replay itself is `tools.cohort_replay.replay_one` — the runner's own
    call, the runner's own classifier — so the answer is a ladder outcome and
    not a claim about one.
    """
    from analysis import community_section as M
    from tools.cohort_replay import replay_one

    original = M._activity_rows
    M._activity_rows = solved_rows
    try:
        payload, klass, reason, claimed = replay_one(markdown, pages)
    finally:
        M._activity_rows = original
    metrics = (payload or {}).get("metrics") or {}
    adb = metrics.get("adb") or {}
    integrity = (payload or {}).get("integrity") or {}
    return {"outcome": f"{klass}/{reason}", "claimed_by": claimed,
            "n_transactions": len(((payload or {}).get("statement") or {})
                                  .get("transactions") or []),
            "adb_ok": metrics.get("adb_ok"),
            "adb_published": metrics.get("average_daily_balance") is not None,
            "adb_checks_failed": sorted(
                name for name, ok in (adb.get("validations") or {}).items()
                if ok is False),
            "integrity_flags": sorted(integrity.get("flags") or [])}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=None)
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    ap.add_argument("--group", action="append", default=[])
    ap.add_argument("--parser", action="append", default=[],
                    help="baseline parser_id — the protected cohort, as a control")
    ap.add_argument("--shas", type=Path, default=None)
    ap.add_argument("--mode", default="all",
                    choices=("all", "structure", "sign_search", "publish"))
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.run is None:
        args.run = Path(DEFAULT_RUN_POINTER.read_text(encoding="utf-8").strip())
    if not args.group and not args.shas and not args.parser:
        args.group = ["DECL:community_section"]

    from analysis import community_section as M
    from analysis.parser_registry import admissible_text
    from tools.cohort_replay import ColdCache, load_baseline_rows

    rows = load_baseline_rows(args.run)
    population: set[str] = set()
    for name in args.group:
        groups = json.loads(args.clusters.read_text(encoding="utf-8"))["groups"]
        population.update(groups.get(name, {}).get("shas16", []))
    if args.shas:
        for raw in Path(args.shas).read_text(encoding="utf-8").splitlines():
            token = raw.strip()
            if token and not token.startswith("#"):
                population.add(token.split()[0].upper()[:16])
    for sha, row in rows.items():
        if (row.get("parser_id") or "") in args.parser:
            population.add(sha[:16])

    by16 = {sha[:16]: sha for sha in rows}
    cache = ColdCache(args.data_dir)

    table = []
    for sha16 in sorted(population):
        entry: dict = {"sha16": sha16}
        sha = by16.get(sha16)
        markdown, pages = cache.text(sha) if sha else (None, [])
        if markdown is None:
            table.append({**entry, "verdict": "no-cached-text"})
            continue
        admissible = admissible_text(markdown)
        blocks = M._account_blocks(admissible)
        entry["account_blocks"] = len(blocks)
        entry["blocks"] = []
        for _product, _number, block in blocks:
            reading = read_block(block)
            found: dict = {}
            if args.mode in ("all", "structure"):
                found["structure"] = structure(reading)
            if args.mode in ("all", "sign_search", "publish"):
                found["sign_search"] = sign_search(reading)
            entry["blocks"].append(found)
        if args.mode in ("all", "structure"):
            entry["column_evidence"] = column_evidence(admissible)
        if args.mode in ("all", "publish"):
            entry["publish"] = publish(markdown, pages)
        table.append(entry)

    lines = [f"# DECL-COMMUNITY-SECTION identity ceiling — run `{args.run.name}`", ""]
    lines += ["| sha16 | blocks | verdict per block |", "|---|---:|---|"]
    for e in table:
        verdicts = "; ".join(
            str(b.get("sign_search", {}).get("verdict", "-")) for b in e.get("blocks", []))
        lines.append(f"| {e['sha16']} | {e.get('account_blocks', '')} | {verdicts} |")
    lines.append("")
    for e in table:
        lines.append(f"## {e['sha16']}")
        lines.append("")
        for index, block in enumerate(e.get("blocks", [])):
            lines.append(f"- block {index}")
            for section, facts in block.items():
                lines.append(f"    - {section}:")
                for key, value in facts.items():
                    lines.append(f"        - {key}: {value}")
        if "column_evidence" in e:
            lines.append("- column evidence (the RAW printed rows):")
            for key, value in e["column_evidence"].items():
                lines.append(f"    - {key}: {value}")
        if "publish" in e:
            lines.append("- publish (the unique reading installed in memory):")
            for key, value in e["publish"].items():
                lines.append(f"    - {key}: {value}")
        lines.append("")
    report = "\n".join(lines) + "\n"

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(table, indent=1, default=str), encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

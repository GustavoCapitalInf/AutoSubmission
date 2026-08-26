"""The three claims of this card a replay cannot see, measured.

W3 §SCANHYG. A base-vs-branch replay answers "did anything move". It cannot
answer why a gate moved nothing, and three of this card's claims are exactly
that shape:

* `--summaries`  SS-UNIQUE-MATCH's ZERO BLAST RADIUS. Adopting the shared
  one-distinct-reading rule moves no southside document because no summary row
  is printed twice with two different readings on any of them. "No document
  moved" is consistent with the rule never firing AND with it firing wrongly;
  this counts the readings per row per document, so the claim is a measurement.

* `--declines`  SCAN-DAY-GLYPH's +0 on the two EQ Bank declines. The card
  offered up to +2 and the branch's commit message reports 0. This instruments
  the reader's OWN calls — `date_tokens.day_readings` and `date_tokens.sole_day`
  are wrapped, not re-implemented — and reports, per document, where the parse
  refuses and how many candidate days survived the intersection at that point.
  One candidate would have been a publish; the number is the whole answer to
  "evidence gate working, or shortfall".

* `--clone-bound`  the clone guard's calibration. `NEAR_CLONE_MAX_STATEMENTS`
  is asserted to be calibrated ("at 6 the only match is `unique_match` itself;
  the next candidate needs eight"). This sweeps the bound over every module of
  `analysis/` and prints what matches at each, so the constant is a measured
  boundary rather than a number in a comment.

* `--day-gate-differential`  SCAN-DAY-GLYPH's change is NOT MONOTONE, measured
  rather than assumed (review finding 3). The base reader is loaded from its own
  blob and answered against this one over every constructed (day-cell shape,
  neighbour, neighbour); the differences are counted in both directions and
  reported by shape. Needs no archive and no `--rows`.

    python -m tools.scanhyg_gate_probe --summaries --declines --clone-bound \
        --rows <reports>/<run-id>/rows.csv --data-dir <checkout>/webapp_data \
        --baseline-settings-key <64 hex> [--out <private>/probe.json]
    python -m tools.scanhyg_gate_probe --day-gate-differential --base 10cc722

Read-only, offline, $0.00. It prints COUNTS and code-defined names: never a day
cell's glyphs, a label's value, or any other fragment of a document.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from tools.scanhyg_family_replay import canonical, document_text, ocr_partitions, population

REPO = Path(__file__).resolve().parent.parent


def southside_summary_readings(args) -> dict:
    """Per document, per summary row: matches printed, and DISTINCT readings.

    The distinct count is `unique_match`'s own test — the captured groups, not
    the number of matches, because a page header that reprints a row
    identically is corroboration and not a contradiction.
    """
    from analysis.scanned_small_bank import (
        _SS_COUNTED_ROWS,
        _SS_DAYS_RE,
        _SS_FIGURE_ROWS,
        _SS_PERIOD_RE,
    )
    from analysis.td_can import normalize_mojibake

    rows = [("period", _SS_PERIOD_RE), ("days", _SS_DAYS_RE)]
    rows += [(f"{key}_row", pattern) for key, pattern in _SS_COUNTED_ROWS]
    rows += [(key, pattern) for key, pattern in _SS_FIGURE_ROWS]

    root = args.data_dir / "artifacts"
    keys = ocr_partitions()
    baseline = args.baseline_settings_key.strip().upper()
    members = population(args.rows, ("southside_scanned",))
    documents: dict[str, dict[str, list[int]]] = {}
    for sha in sorted(members):
        markdown, _pages, _resolution, _payload = document_text(root, sha, keys, baseline)
        if markdown is None:
            continue
        text = normalize_mojibake(markdown)
        documents[sha[:12]] = {
            name: [
                len(list(pattern.finditer(text))),
                len({match.groups() for match in pattern.finditer(text)}),
            ]
            for name, pattern in rows
        }
    contradictions = {
        sha: {name: counts for name, counts in found.items() if counts[1] > 1}
        for sha, found in documents.items()
    }
    return {
        "documents": len(documents),
        "rows_per_document": len(rows),
        "rows_printed_more_than_once": sum(
            1 for found in documents.values() for counts in found.values() if counts[0] > 1
        ),
        "rows_with_two_distinct_readings": sum(
            1 for found in documents.values() for counts in found.values() if counts[1] > 1
        ),
        "contradictions": {sha: found for sha, found in contradictions.items() if found},
        "per_document": documents,
    }


def eq_bank_declines(args) -> dict:
    """Where each EQ Bank document's parse lands, and what the day gate saw.

    `day_readings` and `sole_day` are WRAPPED rather than re-implemented, so
    what is measured is the reader's own calls in their own order. The first
    pass asks the printed period and the row's own month; the second asks the
    legible neighbours. A refusal with more than one surviving candidate is the
    evidence gate declining to pick; a refusal with none is a cell no reading
    makes a day of.
    """
    import analysis.date_tokens as date_tokens
    import analysis.eq_bank_scanned as eq

    root = args.data_dir / "artifacts"
    keys = ocr_partitions()
    baseline = args.baseline_settings_key.strip().upper()
    members = population(args.rows, ("eq_bank_scanned",))

    trace: list[dict[str, object]] = []
    windows: list[int] = []
    rows_read: list[int] = []
    real_sole_day = date_tokens.sole_day
    real_day_readings = date_tokens.day_readings
    real_read_rows = eq._read_rows
    real_admissible = eq._admissible_days

    def watched_admissible(month, *, lower, upper):
        # Called once per ROW in pass 1 and once per unresolved cell in pass 2,
        # so its call sequence bounds the passes even for a cell that never
        # reaches `sole_day` — which an ILLEGIBLE cell no longer does: it is
        # answered by the printed order alone (W3 §SCANHYG SH4.1).
        answer = real_admissible(month, lower=lower, upper=upper)
        windows.append(len(answer))
        return answer

    def watched_read_rows(source):
        rows = real_read_rows(source)
        rows_read.append(0 if rows is None else len(rows))
        return rows

    def watched_sole_day(token, admissible):
        answer = real_sole_day(token, admissible)
        trace.append({
            "glyphs": len(token),
            "all_decimal": token.isdecimal(),
            "readings": len(real_day_readings(token)),
            "admissible": len(frozenset(admissible)),
            "candidates": len(real_day_readings(token) & frozenset(admissible)),
            "resolved": answer is not None,
        })
        return answer

    documents: dict[str, dict[str, object]] = {}
    eq.sole_day = watched_sole_day
    eq._read_rows = watched_read_rows
    eq._admissible_days = watched_admissible
    try:
        for sha in sorted(members):
            markdown, _pages, _resolution, _payload = document_text(root, sha, keys, baseline)
            if markdown is None:
                continue
            trace.clear()
            windows.clear()
            rows_read.clear()
            statement = eq.parse_eq_bank_scanned_statement(markdown)
            # `_resolve_dates` asks the period-and-month window once per ROW
            # first, and only then asks the legible neighbours about the cells
            # that survived. The first `rows` calls are therefore pass 1 and
            # everything after them is pass 2; the row count comes from the
            # reader's own `_read_rows`, wrapped rather than guessed at.
            rows = rows_read[-1] if rows_read else 0
            for index, entry in enumerate(trace):
                entry["pass"] = 1 if index < rows else 2
            damaged = [entry for entry in trace if not entry["all_decimal"]]
            documents[sha[:12]] = {
                "dispatch": members[sha]["dispatch"],
                "outcome_class": members[sha]["outcome_class"],
                "parsed": statement is not None,
                "rows_read": rows,
                "day_cells_examined": len(trace),
                "day_cells_with_a_non_decimal_glyph": len(damaged),
                "unresolved_damaged_cells": [
                    {"pass": entry["pass"],
                     "readings": entry["readings"],
                     "admissible": entry["admissible"],
                     "candidates": entry["candidates"]}
                    for entry in damaged if not entry["resolved"]
                ],
                "resolved_damaged_cells": sum(1 for entry in damaged if entry["resolved"]),
                # The width of the printed-order window every cell that reached
                # pass 2 was answered inside. ONE means its two nearest legible
                # neighbours agree, which is the only width an illegible cell
                # resolves at; anything wider is a refusal.
                "pass_2_window_days": windows[rows:],
            }
    finally:
        eq.sole_day = real_sole_day
        eq._read_rows = real_read_rows
        eq._admissible_days = real_admissible
    return {"documents": len(documents), "per_document": documents}


def clone_bound(_args) -> dict:
    """The near-clone detector's bound, swept over every module of `analysis/`.

    The guard's own shape test is imported rather than copied: a probe with its
    own idea of the shape would measure a different guard.
    """
    import sys

    sys.path.insert(0, str(REPO / "tests"))
    from test_no_parser_helper_clones import (  # noqa: E402
        SHARED_UTILITIES,
        _functions,
        _is_unique_match_shape,
        _modules,
        _rel,
    )

    by_bound: dict[int, list[str]] = {}
    shortest: dict[str, int] = {}
    for path in _modules():
        for node in _functions(path):
            body = [
                statement for statement in node.body
                if not (isinstance(statement, ast.Expr)
                        and isinstance(statement.value, ast.Constant))
            ]
            if not _is_unique_match_shape(node):
                continue
            name = f"{_rel(path)}:{node.name}"
            if path.name in SHARED_UTILITIES:
                name += " (shared utility, exempt)"
            shortest[name] = len(body)
    for bound in range(1, 13):
        by_bound[bound] = sorted(
            name for name, statements in shortest.items() if statements <= bound
        )
    return {
        "modules_scanned": len(_modules()),
        "functions_matching_the_shape": shortest,
        "matches_at_each_bound": {str(k): v for k, v in by_bound.items()},
    }


#: The day-cell shapes the differential sweeps: a lone stray glyph, a pair of
#: them, and every arrangement of one glyph beside one digit. Invented tokens
#: over an invented period; no archive text is read by this mode at all.
_DIFFERENTIAL_TOKENS = (
    "&", "g", "&&", "&5", "5&", "8&", "&8", "1&", "&1", "&0", "0&", "g5", "5g",
)


def day_gate_differential(_args) -> dict:
    """Base against branch on `_resolve_dates` alone, over constructed shapes.

    W3 §SCANHYG SH4, review finding 3. "The gate is stricter" is a claim about
    a partial order, and a gate rewritten from `delete the glyph and take what
    is left` to `enumerate the readings and intersect them with the document`
    is not obliged to obey one. This measures it rather than asserting it: the
    base implementation is loaded from its own blob at the base commit, three
    printed rows are constructed for every (day-cell shape, neighbour before,
    neighbour after), and the two answers are compared.

    A `wider` row is one the base reader refused and this one dates; a
    `stricter` row is the reverse. Both are reported by SHAPE — whether the
    cell kept a legible digit, and whether the neighbours agree — because the
    shape is what decides whether an admission is evidence or a preference.
    """
    import types

    import analysis.eq_bank_scanned as branch

    blob = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{_args.base}:analysis/eq_bank_scanned.py"],
        capture_output=True, check=True,
    ).stdout.decode("utf-8")
    base = types.ModuleType("analysis._scanhyg_base_eq_bank_scanned")
    base.__package__ = "analysis"
    sys.modules[base.__name__] = base
    exec(compile(blob, f"<{_args.base}:analysis/eq_bank_scanned.py>", "exec"), base.__dict__)

    start, end, month = date(2031, 3, 1), date(2031, 3, 31), "March"

    def answer(module, before, token, after):
        rows = [
            module._Row(month, str(before), "invented row", False, 100, 100),
            module._Row(month, token, "invented row", False, 100, 100),
            module._Row(month, str(after), "invented row", False, 100, 100),
        ]
        resolved = module._resolve_dates(rows, period_start=start, period_end=end)
        return "REFUSED" if resolved is None else resolved[1].isoformat()

    counts = {"same": 0, "wider": 0, "stricter": 0}
    census: dict[str, dict[str, int]] = {"wider": {}, "stricter": {}}
    for token in _DIFFERENTIAL_TOKENS:
        shape = "".join("d" if glyph.isdecimal() else "x" for glyph in token)
        for before in range(1, 32):
            for after in range(before, 32):
                was, now = answer(base, before, token, after), answer(branch, before, token, after)
                if was == now:
                    counts["same"] += 1
                    continue
                direction = "wider" if was == "REFUSED" else "stricter"
                counts[direction] += 1
                key = f"{shape}/{'neighbours agree' if before == after else 'neighbours differ'}"
                census[direction][key] = census[direction].get(key, 0) + 1
    return {"base": _args.base, "shapes": len(_DIFFERENTIAL_TOKENS), **counts, "census": census}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--baseline-settings-key", default="")
    parser.add_argument("--summaries", action="store_true")
    parser.add_argument("--declines", action="store_true")
    parser.add_argument("--clone-bound", action="store_true")
    parser.add_argument("--day-gate-differential", action="store_true")
    parser.add_argument("--base", default="10cc722",
                        help="the commit the day-gate differential loads the base reader from")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report: dict[str, object] = {}
    if args.summaries:
        report["southside_summary_readings"] = southside_summary_readings(args)
    if args.declines:
        report["eq_bank_declines"] = eq_bank_declines(args)
    if args.clone_bound:
        report["clone_bound"] = clone_bound(args)
    if args.day_gate_differential:
        report["day_gate_differential"] = day_gate_differential(args)
    if not report:
        parser.error(
            "choose at least one of --summaries / --declines / --clone-bound / "
            "--day-gate-differential"
        )
    if args.out is not None:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

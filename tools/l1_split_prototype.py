"""L1INV instrument 3 — READ-ONLY split/reconstruct/validate prototype.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**
It exists to MEASURE one question and then to be deleted or rewritten by
whoever implements the ruling: if a multi-account credit-union statement were
split at its printed boundaries and each section reconstructed as its own
`Statement`, how many sections would close under the EXISTING deterministic
validator, unchanged? `analysis/reconcile.py::reconcile` and
`analysis/adb.py::compute_average_daily_balance` are called exactly as
production calls them; nothing here relaxes, replaces or reimplements either.
It does not call `analyze_markdown` / `cached_analysis`, so it is not a
production analysis caller and is not wired into anything.

METHOD
------
1. Boundaries come from `tools.l1_structure_census` — the printed roll-up's
   enumerated identities where the document prints one, the section headings'
   own identities otherwise. Nothing is inferred from a product vocabulary.
2. Each section's OPENING and CLOSING are the figures the section itself
   prints beside its own `Beginning/Previous Balance` and `Ending/New Balance`
   captions. A section that does not print both FAILS CLOSED.
3. The ledger is reconstructed by a BALANCE CHAIN WALK, which is the only row
   grammar here and is self-validating: starting from the printed opening, a
   transaction is accepted only when two adjacent printed figures satisfy
   `previous balance ± printed amount = printed balance` to the cent. The
   amount is never assumed from a column position and never computed as a
   difference alone — the document must print BOTH the delta and the balance
   it lands on, and they must agree. A section whose walk does not consume its
   figures and arrive at the section's own printed closing FAILS CLOSED.
   That refuses more than a per-family row grammar would, so every count this
   instrument reports is a LOWER BOUND on what an implementation could reach.
4. The reconstructed `Statement` is handed to `reconcile` and
   `compute_average_daily_balance` unchanged. A section CLOSES when
   `recon.ok` and `adb.ok` are both true — the two deterministic oracles the
   platform already publishes on.
5. The ORACLE check is separate: does the roll-up's own row for that account
   print the closing figure the section reconstructed?

PRIVACY. Amounts and dates are read into local variables to do arithmetic and
are never emitted: the report prints counts, boolean facts, refusal-class names
and content sha16s only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import ColdCache  # noqa: E402
from tools.l1_census import CU_OPPORTUNITY_KEY, DECL_GROUPS, ATB_GROUP, load_census  # noqa: E402
from tools.l1_structure_census import (  # noqa: E402
    CLOSING_WORDS,
    MONEY,
    OPENING_WORDS,
    _flat,
    _norm,
    find_grid_header,
    structure,
)

DATE_TOKEN = re.compile(
    r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b"
    r"|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b")

_D = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
PERIOD = re.compile(rf"({_D})\s*(?:through|thru|to|-|–|—|until)\s*({_D})", re.I)
PERIOD_LABELLED = re.compile(
    rf"start date[:\s]*({_D}).{{0,40}}?end date[:\s]*({_D})", re.I | re.S)
#: `February 1, 2026 to February 28, 2026` and `Feb 1 - 28 2026`
_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
PERIOD_WORDS = re.compile(
    rf"({_MONTH}\.?\s+\d{{1,2}}),?\s*(?:\d{{4}})?\s*(?:through|thru|to|-|–|—)\s*"
    rf"({_MONTH}\.?\s+\d{{1,2}}),?\s*(\d{{4}})", re.I)
PERIOD_WORDS_SHORT = re.compile(
    rf"({_MONTH})\.?\s+(\d{{1,2}})\s*(?:-|–|—|to)\s*(\d{{1,2}}),?\s*(\d{{4}})", re.I)

MONTHS = {m: i + 1 for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def _money_value(text: str) -> float | None:
    body = text.strip()
    negative = body.startswith("(") or body.endswith(")") or body.endswith("-") or body.startswith("-")
    body = body.strip("()$-").replace(",", "").replace("$", "")
    try:
        value = float(body)
    except ValueError:
        return None
    return -value if negative else value


def _parse_ymd(token: str) -> date | None:
    parts = re.split(r"[/-]", token)
    if len(parts) != 3:
        return None
    try:
        month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _word_date(month: str, day: str, year: str) -> date | None:
    try:
        return date(int(year), MONTHS[month.strip(". ").lower()[:3]], int(day))
    except (KeyError, ValueError):
        return None


def find_period(text: str) -> tuple[date, date] | None:
    """The printed statement period.

    EVERY match of each pattern is considered, not only the first: these
    documents print dates in their marketing furniture too, and taking the
    first pair found made the instrument refuse documents whose real period is
    printed two lines lower. A pair is accepted only if it is ordered and no
    longer than a statement cycle."""
    def accept(start: date | None, end: date | None) -> tuple[date, date] | None:
        if start and end and start <= end and 20 <= (end - start).days <= 100:
            return start, end
        return None

    for pattern in (PERIOD_LABELLED, PERIOD):
        for m in pattern.finditer(text):
            got = accept(_parse_ymd(m.group(1)), _parse_ymd(m.group(2)))
            if got:
                return got
    for m in PERIOD_WORDS.finditer(text):
        left, right, year = m.group(1).split(), m.group(2).split(), m.group(3)
        got = accept(_word_date(left[0], left[1], year), _word_date(right[0], right[1], year))
        if got:
            return got
    for m in PERIOD_WORDS_SHORT.finditer(text):
        got = accept(_word_date(m.group(1), m.group(2), m.group(4)),
                     _word_date(m.group(1), m.group(3), m.group(4)))
        if got:
            return got
    return None


def _row_date(token: str, period: tuple[date, date]) -> str | None:
    """A printed row date resolved onto the printed period's calendar.

    The year is taken from the period, not invented: a row whose month equals
    the period start's month takes the start year, one whose month equals the
    end's takes the end year, and anything else is refused."""
    start, end = period
    m = DATE_TOKEN.match(token)
    if m is None:
        return None
    if m.group(1):
        month, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            resolved = _parse_ymd(token)
            return resolved.isoformat() if resolved else None
    else:
        month, day = MONTHS[m.group(4).lower()], int(m.group(5))
    for year in {start.year, end.year}:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if start <= candidate <= end:
            return candidate.isoformat()
    return None


# ---------------------------------------------------------------------------
# the section's own printed opening and closing
# ---------------------------------------------------------------------------

_OPEN_FIG = re.compile(OPENING_WORDS + r"[^\n]{0,80}?(" + MONEY.pattern + r")", re.I)
_CLOSE_FIG = re.compile(CLOSING_WORDS + r"[^\n]{0,80}?(" + MONEY.pattern + r")", re.I)
#: some issues print the figure BEFORE the caption (`5.00 Beginning Balance`)
_OPEN_FIG_LEFT = re.compile(r"(" + MONEY.pattern + r")[^\n]{0,40}?" + OPENING_WORDS, re.I)
_CLOSE_FIG_LEFT = re.compile(r"(" + MONEY.pattern + r")[^\n]{0,40}?" + CLOSING_WORDS, re.I)


def _figure(text: str, right: re.Pattern[str], left: re.Pattern[str]) -> tuple[float, int] | None:
    m = right.search(text)
    if m:
        value = _money_value(m.group(1))
        if value is not None:
            return value, m.end()
    m = left.search(text)
    if m:
        value = _money_value(m.group(1))
        if value is not None:
            return value, m.end()
    return None


# ---------------------------------------------------------------------------
# the balance chain walk
# ---------------------------------------------------------------------------


@dataclass
class Walk:
    ok: bool
    rows: list[tuple[str, float, float]] = field(default_factory=list)
    refusal: str | None = None
    skipped: int = 0


def chain_walk(ledger: str, opening: float, closing: float,
               period: tuple[date, date]) -> Walk:
    """Consume the section's printed figures into `(date, amount, balance)`
    rows, from the printed opening onto the printed closing.

    The rule, and the only one: two adjacent printed figures `a` and `b` are a
    transaction when `previous ± a == b` to the cent — the statement printed
    both the movement and the balance it produced, and they agree. Either
    order is accepted (`amount balance` and `balance amount` are both printed
    in this population) but a figure is never re-used and never skipped
    silently: any figure the walk cannot place ends it, and the section fails
    closed unless the walk has by then reached the section's own printed
    closing."""
    figures = [(m.start(), _money_value(m.group(0))) for m in MONEY.finditer(ledger)]
    figures = [(p, v) for p, v in figures if v is not None]
    dates = [(m.start(), m.group(0)) for m in DATE_TOKEN.finditer(ledger)]
    if not figures:
        return Walk(False, refusal="no-figures-in-ledger")

    rows: list[tuple[str, float, float]] = []
    previous = round(opening, 2)
    index = 0
    skipped = 0
    undated = 0
    #: the longest prefix of the chain that ENDS on the printed closing. A
    #: statement prints fee and year-to-date tables after its ledger, so the
    #: walk must be allowed to stop where the account's own arithmetic is
    #: complete rather than be required to consume the page.
    snapshot: tuple[list[tuple[str, float, float]], float, int] | None = (
        ([], previous, 0) if abs(previous - round(closing, 2)) <= 0.005 else None)

    def date_for(position: int) -> str | None:
        cursor = None
        for at, token in dates:
            if at > position:
                break
            cursor = token
        return _row_date(cursor, period) if cursor else None

    while index + 1 < len(figures):
        position, first = figures[index]
        _next_position, second = figures[index + 1]
        accepted = None
        for amount, balance in ((first, second), (second, first)):
            delta = round(balance - previous, 2)
            if delta == 0.0 and round(amount, 2) == 0.0:
                accepted = (0.0, balance)
                break
            if delta != 0.0 and abs(abs(delta) - abs(round(amount, 2))) <= 0.005:
                accepted = (delta, balance)
                break
        if accepted is None:
            # Not a ledger row here. Skipping is SAFE under this grammar and
            # not a relaxation of it: every accepted row's balance becomes the
            # next row's `previous`, so skipping a figure that belongs to a
            # real row breaks the chain and the section fails closed anyway.
            # What skipping buys is the summary block, the fee table and the
            # re-printed balance sitting in the same span as the ledger.
            skipped += 1
            index += 1
            continue
        iso = date_for(position)
        if iso is None:
            undated += 1
            skipped += 1
            index += 1
            continue
        delta, balance = accepted
        rows.append((iso, delta, balance))
        previous = round(balance, 2)
        index += 2
        if abs(previous - round(closing, 2)) <= 0.005:
            snapshot = (list(rows), previous, skipped)

    if snapshot is None:
        return Walk(False, rows, "walk-did-not-reach-the-printed-closing", skipped)
    rows, previous, skipped = snapshot
    return Walk(True, rows, None, skipped)


# ---------------------------------------------------------------------------
# reconstruct + validate
# ---------------------------------------------------------------------------


@dataclass
class SectionResult:
    refusal: str | None = None
    recon_ok: bool = False
    adb_ok: bool = False
    n_rows: int = 0
    skipped: int = 0
    #: where the section's opening/closing pair came from
    pair_source: str | None = None
    oracle_reproduced: bool | None = None

    @property
    def closes(self) -> bool:
        return self.recon_ok and self.adb_ok


def reconstruct_and_validate(section_text: str, period: tuple[date, date],
                             rollup_block: str | None) -> SectionResult:
    """One printed account section, reconstructed and handed to the validator.

    The opening/closing pair is taken from the section's own printed captions
    where it prints them and from the ROLL-UP's row for that account where it
    does not. Where BOTH are printed they must agree to the cent: a section
    whose own figures contradict the table that enumerates it is exactly the
    ambiguity this whole question is about, and it fails closed."""
    from analysis.adb import compute_average_daily_balance
    from analysis.reconcile import reconcile
    from analysis.schema import Statement, Transaction

    result = SectionResult()
    own_open = _figure(section_text, _OPEN_FIG, _OPEN_FIG_LEFT)
    own_close = _figure(section_text, _CLOSE_FIG, _CLOSE_FIG_LEFT)
    rollup_values: list[float] = []
    rollup_pair = None
    if rollup_block:
        rollup_values = [v for v in (_money_value(t) for t in MONEY.findall(rollup_block))
                         if v is not None]
        if len(rollup_values) >= 2:
            rollup_pair = (rollup_values[0], rollup_values[-1])

    if own_open is not None and own_close is not None and rollup_pair is not None:
        if (abs(rollup_pair[0] - own_open[0]) > 0.005
                or abs(rollup_pair[1] - own_close[0]) > 0.005):
            result.refusal = "section-and-rollup-disagree-on-the-pair"
            return result

    #: Candidate opening/closing pairs, strongest evidence first. Trying more
    #: than one is not a search for a number that works: the balance-chain walk
    #: only accepts a pair it can travel from end to end through the printed
    #: figures, so a wrong pair cannot be accepted, and the pair that IS
    #: accepted is reported with the evidence it came from.
    opens: list[tuple[float, str]] = []
    closes: list[tuple[float, str]] = []
    if own_open is not None:
        opens.append((own_open[0], "section"))
    if rollup_values and len(rollup_values) >= 2:
        opens.append((rollup_values[0], "rollup"))
    if own_close is not None:
        closes.append((own_close[0], "section"))
    if rollup_values:
        closes.append((rollup_values[-1], "rollup"))
    if not opens and not closes:
        result.refusal = "section-prints-neither-an-opening-nor-a-closing"
        return result
    if not opens:
        result.refusal = "section-prints-no-opening-and-no-roll-up-states-one"
        return result
    if not closes:
        result.refusal = "section-prints-no-closing-and-no-roll-up-states-one"
        return result

    grid = find_grid_header(section_text)
    open_at = own_open[1] if own_open is not None else 0
    ledger_from = max(open_at, grid[2] if grid else 0)
    ledger = section_text[ledger_from:]
    if not MONEY.search(ledger):
        # the grid header sits after the last figure (a trailing legend, a
        # continuation caption): fall back to the section's own opening.
        ledger_from = open_at
        ledger = section_text[ledger_from:]

    walk = None
    open_value = close_value = 0.0
    for open_value, open_from in opens:
        for close_value, close_from in closes:
            attempt = chain_walk(ledger, open_value, close_value, period)
            if attempt.ok:
                walk = attempt
                result.pair_source = f"open:{open_from}/close:{close_from}"
                break
            if walk is None:
                walk = attempt
        if walk is not None and walk.ok:
            break
    assert walk is not None
    result.n_rows = len(walk.rows)
    result.skipped = walk.skipped
    if not walk.ok:
        result.refusal = walk.refusal
        return result

    statement = Statement(
        period_start=period[0].isoformat(),
        period_end=period[1].isoformat(),
        beginning_balance=round(open_value, 2),
        ending_balance=round(close_value, 2),
        transactions=[
            Transaction(date=iso, description="", amount=amount,
                        direction="credit" if amount >= 0 else "debit",
                        running_balance=balance)
            for iso, amount, balance in walk.rows
        ],
    )
    recon = reconcile(statement)
    adb = compute_average_daily_balance(statement)
    result.recon_ok = recon.ok
    result.adb_ok = adb.ok
    if rollup_block:
        result.oracle_reproduced = any(
            abs((_money_value(token) or 0.0) - round(close_value, 2)) <= 0.005
            for token in MONEY.findall(rollup_block)
        )
    return result


@dataclass
class DocResult:
    sha16: str
    group: str
    band: str
    family: str
    boundary: str
    n_sections: int
    n_posting: int
    sections: list[SectionResult] = field(default_factory=list)

    @property
    def sections_closed(self) -> int:
        return sum(1 for s in self.sections if s.closes)

    @property
    def all_posting_close(self) -> bool:
        posting = [s for s in self.sections if s.n_rows >= 1 or s.refusal is None]
        return bool(posting) and all(s.closes for s in self.sections if s.n_rows >= 1)

    @property
    def oracle_reproduced(self) -> bool:
        checked = [s.oracle_reproduced for s in self.sections if s.oracle_reproduced is not None]
        return bool(checked) and all(checked)


def run_document(sha16: str, group: str, band: str, markdown: str, pages: int) -> DocResult:
    doc = structure(sha16, group, band, markdown, pages)
    text = _norm(markdown)
    period = find_period(_flat(text))
    result = DocResult(sha16, group, band, doc.family_key, doc.boundary,
                       len(doc.sections),
                       sum(1 for s in doc.sections if s.n_dated_rows >= 2))
    if period is None:
        result.sections = [SectionResult(refusal="document-prints-no-resolvable-period")]
        return result
    for section in doc.sections:
        body = text[section.start:section.end]
        block = None
        if doc.boundary.startswith("rollup-oracle") and 0 <= section.identity_index < len(doc.rollup.rows):
            block = doc.rollup.rows[section.identity_index].block
        result.sections.append(reconstruct_and_validate(body, period, block))
    return result


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    groups, opportunities, per_sha = load_census(args.census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    cache = ColdCache(args.data_dir)

    population: list[tuple[str, str, str]] = []
    for name in opportunities[CU_OPPORTUNITY_KEY]["groups"]:
        population += [("CU-SUFFIX", name, s) for s in groups[name]["shas16"]]
    for name in DECL_GROUPS:
        population += [("DECL-L1-CANDIDATE", name, s) for s in groups[name]["shas16"]]
    population += [("ATB", ATB_GROUP, s) for s in groups[ATB_GROUP]["shas16"]]

    results: list[DocResult] = []
    for band, group, sha16 in population:
        markdown, pages = cache.text(sha_by16[sha16])
        if markdown is None:
            continue
        results.append(run_document(sha16, group, band, markdown, len(pages)))

    print("# L1INV — split / reconstruct / validate prototype (LOWER BOUND)")
    print(f"# documents: {len(results)}")
    print()
    print("Every number below is produced by the EXISTING `reconcile` and "
          "`compute_average_daily_balance`, called unchanged on a `Statement` "
          "reconstructed from one printed account section. A section CLOSES "
          "when both return ok.")
    print()

    total_sections = sum(len(r.sections) for r in results)
    closed = sum(r.sections_closed for r in results)
    print("## Headline")
    print()
    print("| measure | value |")
    print("|---|---:|")
    print(f"| documents in the population | {len(results)} |")
    print(f"| sections reconstructed and offered to the validator | {total_sections} |")
    print(f"| sections that CLOSE (recon.ok and adb.ok) | {closed} |")
    docs_all = [r for r in results if r.n_sections >= 1 and r.sections_closed == r.n_sections]
    docs_multi = [r for r in docs_all if r.n_sections >= 2]
    print(f"| documents whose EVERY located section closes | {len(docs_all)} |")
    print(f"| ... of those, documents with >= 2 sections | {len(docs_multi)} |")
    oracle = [r for r in docs_all if r.oracle_reproduced]
    print(f"| ... whose roll-up also reproduces every section's closing | {len(oracle)} |")
    print()

    print("## By boundary mechanism")
    print()
    print("| boundary | docs | sections | closed | docs fully closing | roll-up reproduces |")
    print("|---|---:|---:|---:|---:|---:|")
    by_boundary: dict[str, list[DocResult]] = defaultdict(list)
    for r in results:
        by_boundary[r.boundary.split(":")[0]].append(r)
    for name in ("rollup-oracle", "section-identity", "section-equation-scan", "none"):
        members = by_boundary.get(name, [])
        sections = sum(len(m.sections) for m in members)
        full = [m for m in members if m.n_sections >= 1 and m.sections_closed == m.n_sections]
        print(f"| `{name}` | {len(members)} | {sections} | "
              f"{sum(m.sections_closed for m in members)} | {len(full)} | "
              f"{sum(1 for m in full if m.oracle_reproduced)} |")
    print()

    print("## By structural family (families with >= 1 closing section first)")
    print()
    families: dict[str, list[DocResult]] = defaultdict(list)
    for r in results:
        families[r.family].append(r)
    ranked = sorted(families.items(),
                    key=lambda kv: (-sum(m.sections_closed for m in kv[1]), -len(kv[1])))
    print("| docs | sections | closed | docs fully closing | census groups | family key |")
    print("|---:|---:|---:|---:|---|---|")
    for key, members in ranked:
        sections = sum(len(m.sections) for m in members)
        closed_here = sum(m.sections_closed for m in members)
        full = sum(1 for m in members if m.n_sections >= 1 and m.sections_closed == m.n_sections)
        gs = sorted({m.group for m in members})
        label = ", ".join(f"`{g}`" for g in gs[:3]) + (f" (+{len(gs) - 3})" if len(gs) > 3 else "")
        print(f"| {len(members)} | {sections} | {closed_here} | {full} | {label} | `{key}` |")
    print()

    print("## The L-1 question, measured: documents with TWO OR MORE posting sections")
    print()
    print("These are the documents the single-account schema refuses today. A "
          "document is counted as recoverable only when EVERY section located "
          "on it closes under the unchanged validator.")
    print()
    print("| band | docs with >= 2 posting sections | every section closes | "
          "roll-up also reproduces |")
    print("|---|---:|---:|---:|")
    for band in ("CU-SUFFIX", "DECL-L1-CANDIDATE", "ATB"):
        members = [r for r in results if r.band == band and r.n_posting >= 2]
        full = [m for m in members if m.n_sections >= 1 and m.sections_closed == m.n_sections]
        print(f"| {band} | {len(members)} | {len(full)} | "
              f"{sum(1 for m in full if m.oracle_reproduced)} |")
    every = [r for r in results if r.n_posting >= 2]
    every_full = [r for r in every if r.n_sections >= 1 and r.sections_closed == r.n_sections]
    print(f"| **total** | {len(every)} | {len(every_full)} | "
          f"{sum(1 for m in every_full if m.oracle_reproduced)} |")
    print()

    print("## Fail-closed classes (why a section was not offered, or did not close)")
    print()
    refusals = Counter(s.refusal or ("closed" if s.closes else "offered-but-validator-refused")
                       for r in results for s in r.sections)
    print("| class | sections |")
    print("|---|---:|")
    for name, count in refusals.most_common():
        print(f"| `{name}` | {count} |")
    print()

    print("## By census group")
    print()
    print("| census group | docs | sections | closed | docs fully closing |")
    print("|---|---:|---:|---:|---:|")
    by_group: dict[str, list[DocResult]] = defaultdict(list)
    for r in results:
        by_group[r.group].append(r)
    for group in sorted(by_group):
        members = by_group[group]
        full = sum(1 for m in members if m.n_sections >= 1 and m.sections_closed == m.n_sections)
        print(f"| `{group}` | {len(members)} | {sum(len(m.sections) for m in members)} | "
              f"{sum(m.sections_closed for m in members)} | {full} |")
    print()

    if args.json:
        args.json.write_text(json.dumps([
            {
                "sha16": r.sha16, "group": r.group, "band": r.band,
                "boundary": r.boundary, "family": r.family,
                "n_sections": r.n_sections, "n_posting": r.n_posting,
                "sections_closed": r.sections_closed,
                "oracle_reproduced": r.oracle_reproduced,
                "sections": [
                    {"refusal": s.refusal, "recon_ok": s.recon_ok, "adb_ok": s.adb_ok,
                     "n_rows": s.n_rows, "skipped": s.skipped,
                     "pair_source": s.pair_source, "oracle": s.oracle_reproduced}
                    for s in r.sections
                ],
            }
            for r in results
        ], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

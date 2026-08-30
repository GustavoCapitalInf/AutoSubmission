"""L1-ARCH-DESIGN instrument 5 — READ-ONLY silent-skip probe, on the DISPATCH PATH.

**NOT A PARSER. NEVER REGISTERED. NEVER IMPORTED BY PRODUCTION OR BY A TEST.**

The design's first version bounded the silent-skip population with each module's
own section-mark pattern and said, honestly, that a mark count cannot tell a
dropped section from a reprinted heading — "no instrument outside the reader
itself can tell those apart". The review's answer was the right one: **instrument
the reader itself.** This does that, and it answers the design's largest open
ruling (Q8) with a number instead of a risk.

WHAT IT MEASURES
----------------
1. **Where the skip actually fires**, per registration, over every `validated`
   document of that registration in the run of record, through
   `analyze_markdown(parse_mode="deterministic")` — the production dispatch
   path, the runner's exact call. Nothing here re-implements a reader's
   decision: the readers run, and the probe watches.
2. **What the paper printed on each skipped section**, in the evidence classes
   the checkpoint condition R-a can accept:
     * `printed_dormancy_declaration` — the section prints a no-activity
       declaration. BOTH ratified wordings are tried: `symitar._DORMANT_RE` and
       `zions._NO_ACTIVITY_RE`, each the module's own committed pattern.
     * `printed_zero_activity_summary` — the section prints its OWN opening
       balance, its OWN closing balance, the two coincide to the cent, and its
       own credit total, debit total, credit count and debit count are all
       zero. Read by `community_section._summary`, which is fail-closed by its
       own docstring: a grid missing either balance row or either count yields
       None rather than a partial answer.
   A section matching neither is `no_printed_evidence` — the class R-a refuses,
   and the class this probe exists to count.

HOW THE READER IS WATCHED, WITHOUT TOUCHING IT
----------------------------------------------
Two mechanisms, each chosen for the shape of the site:

* a LINE WATCH for the skips that are statements inside a loop with no function
  boundary of their own — `analysis/symitar.py`'s `continue` and
  `analysis/community_section.py`'s `return None` inside
  `_parse_sectioned_statement`. It uses `sys.monitoring` with LOCAL events set
  on those three code objects only, so nothing else in the process is
  instrumented and the readers' own bytecode, control flow and results are
  untouched. (`sys.settrace` was the first attempt and is the wrong tool here:
  its global call hook fires for every call in the interpreter and the probe
  did not finish.)
* a FUNCTION WATCH for `analysis/zions.py::_inert`, which IS a function
  boundary: it is wrapped, its argument and result recorded, and the original
  called. `zions` is named as a skip site by the design and was probed by no
  instrument in the first version — the review's BLOCK-1, second half.

The watched line numbers are VERIFIED at start-up against the source text they
are supposed to sit on, and the probe REFUSES rather than reporting a zero if
any has moved. A silent zero here would be the same vacuity §1.4 of the design
spends its length warning about.

PRIVACY
-------
Content sha16s, registration ids, evidence-class names and counts. No printed
value, name, account number, amount or date: figures are read only to compare
them with each other and with zero, and it is the comparison that is reported.

Usage:

    python -m tools.l1_design_skip_probe --run <run dir> --data-dir <cold cache> \
        [--registrations a,b,c] [--json <private>.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cohort_replay import ColdCache, load_baseline_rows  # noqa: E402


# ---------------------------------------------------------------------------
# the watched sites, each pinned to the source text it must sit on
# ---------------------------------------------------------------------------


def _dropped_at_call_site(locals_: dict) -> bool:
    """`community_section.py`:984 is an `if`, not a skip, and its two operands
    are not one finding.

    The other two watched lines ARE the skip — a `continue` and a `return None`
    — and executing them is the drop. This one is
    `if stmt is not None and stmt.transactions:`, which executes on every block
    the loop offers. Two corrections were needed here and both were caught by
    running the probe:

    * counting its EXECUTIONS counts blocks, not drops (the first run reported
      65 where the clause drops nothing);
    * counting `stmt is None` as a drop counts the SAME block twice, because a
      block dropped inside `_parse_sectioned_statement` at :622 arrives here as
      `None` and is already recorded at its own site.

    So the only drop this clause contributes of its own is the second operand:
    a statement that PARSED and carries no transaction. That is the clause the
    design's first version named, and measuring it is what says whether naming
    it was right.
    """
    stmt = locals_.get("stmt")
    return stmt is not None and not getattr(stmt, "transactions", None)


@dataclass(frozen=True)
class LineSite:
    module: str          # dotted module name
    lineno: int          # the line the skip EXECUTES
    expect: str          # source text that line must contain
    capture: str         # the local holding the skipped section's text
    label: str
    #: None when executing the line IS the drop; otherwise a predicate over the
    #: frame's own locals that says whether this execution dropped anything.
    predicate: object = None


LINE_SITES: tuple[LineSite, ...] = (
    LineSite("analysis.symitar", 420, "continue", "text",
             "symitar `if not rows: continue` — the absence-based dormant skip"),
    LineSite("analysis.community_section", 622, "return None", "block",
             "community_section `if not txns: return None` inside _parse_sectioned_statement"),
    # The line the design's first version named. Watched here so that its count
    # is a measurement rather than an omission (the review's MAJOR-4).
    LineSite("analysis.community_section", 984, "stmt.transactions", "block",
             "community_section — the `stmt.transactions` clause at the CALL SITE",
             _dropped_at_call_site),
)

ZIONS_LABEL = "zions `_inert` — printed zero columns and no row"


def verify_sites() -> list[str]:
    """Refuse to run on a tree where a watched line is not the line meant."""
    problems: list[str] = []
    for site in LINE_SITES:
        module = __import__(site.module, fromlist=["__file__"])
        source = Path(module.__file__).read_text(encoding="utf-8").splitlines()
        if site.lineno > len(source):
            problems.append(f"{site.module}:{site.lineno} is past the end of the file")
            continue
        if site.expect not in source[site.lineno - 1]:
            problems.append(
                f"{site.module}:{site.lineno} does not contain {site.expect!r}")
    return problems


# ---------------------------------------------------------------------------
# the line watch — `sys.monitoring`, LOCAL events, three code objects
# ---------------------------------------------------------------------------


def _code_objects(module) -> list:
    """Every code object defined in `module`, nested ones included."""
    seen: list = []
    stack = []
    for value in vars(module).values():
        code = getattr(value, "__code__", None)
        if code is not None:
            stack.append(code)
    while stack:
        code = stack.pop()
        if code in seen:
            continue
        seen.append(code)
        for const in code.co_consts:
            if hasattr(const, "co_code"):
                stack.append(const)
    return seen


def _covering_code(module, lineno: int):
    """The code object whose own line table contains `lineno`."""
    best = None
    for code in _code_objects(module):
        lines = {line for _s, _e, line in code.co_lines() if line is not None}
        if lineno in lines:
            # the innermost (latest-starting) code object wins
            if best is None or code.co_firstlineno > best.co_firstlineno:
                best = code
    return best


def _entry_point(frame) -> str:
    """The nearest enclosing `parse_*` function — i.e. WHOSE parse attempt this
    skip belongs to.

    This is not decoration. `analysis/parser_registry.py::resolve` (:998-1024)
    calls `parse` on EVERY candidate registration and records the ones that
    declined in `Dispatch.attempted`, so several parsers run on one document —
    and three registrations (`community_section`, `dakota_west`,
    `mission_valley`) route into the SAME module function
    (`_parse_sectioned_statement`, called at :686, :725 and :981). A watch that
    counts line hits without asking whose attempt they belong to attributes a
    losing candidate's drops to the winner. The first run of this probe did
    exactly that and reported 71 sections where the claiming parser drops 6.
    """
    while frame is not None:
        name = frame.f_code.co_name
        if name.startswith("parse_"):
            return name
        frame = frame.f_back
    return "<no parse frame>"


class LineWatch:
    """Records the watched local every time a watched line executes."""

    def __init__(self, sites: tuple[LineSite, ...]):
        self.sites = sites
        self.hits: list[tuple[LineSite, str, str]] = []
        self._codes: list = []
        self._by_key: dict[tuple[int, int], LineSite] = {}
        for site in sites:
            module = __import__(site.module, fromlist=["__file__"])
            code = _covering_code(module, site.lineno)
            if code is None:
                raise RuntimeError(
                    f"no code object covers {site.module}:{site.lineno}")
            self._codes.append(code)
            self._by_key[(id(code), site.lineno)] = site
        self._tool = None

    def _callback(self, code, line_number):
        site = self._by_key.get((id(code), line_number))
        if site is None:
            return
        frame = sys._getframe(1)
        locals_ = frame.f_locals
        if site.predicate is not None and not site.predicate(locals_):
            return
        value = locals_.get(site.capture)
        if not isinstance(value, str):
            value = str(getattr(value, "text", "") or "")
        self.hits.append((site, value, _entry_point(frame)))

    def __enter__(self):
        mon = sys.monitoring
        for tool_id in range(6):
            if mon.get_tool(tool_id) is None:
                self._tool = tool_id
                break
        if self._tool is None:
            raise RuntimeError("no free sys.monitoring tool id")
        mon.use_tool_id(self._tool, "l1-design-skip-probe")
        mon.register_callback(self._tool, mon.events.LINE, self._callback)
        for code in self._codes:
            mon.set_local_events(self._tool, code, mon.events.LINE)
        return self

    def __exit__(self, *exc):
        mon = sys.monitoring
        for code in self._codes:
            mon.set_local_events(self._tool, code, 0)
        mon.register_callback(self._tool, mon.events.LINE, None)
        mon.free_tool_id(self._tool)
        self._tool = None
        return False


# ---------------------------------------------------------------------------
# the function watch (zions)
# ---------------------------------------------------------------------------


class InertWatch:
    """Wraps `analysis.zions._inert`, recording every block it declared inert."""

    def __init__(self):
        self.hits: list[str] = []
        self._original = None

    def __enter__(self):
        from analysis import zions

        self._original = zions._inert

        def watched(block, rows):
            verdict = self._original(block, rows)
            if verdict:
                sections = block.get("sections") if isinstance(block, dict) else None
                self.hits.append("\n".join(str(v) for v in (sections or {}).values()))
            return verdict

        zions._inert = watched
        return self

    def __exit__(self, *exc):
        from analysis import zions

        zions._inert = self._original
        return False


# ---------------------------------------------------------------------------
# the evidence classes R-a can accept
# ---------------------------------------------------------------------------

DECLARATION = "printed_dormancy_declaration"
ZERO_SUMMARY = "printed_zero_activity_summary"
NONE_PRINTED = "no_printed_evidence"


def classify_evidence(text: str) -> tuple[str, dict]:
    """Which evidence class the paper printed on this skipped section.

    Every predicate below is a module's OWN committed pattern or helper. This
    function writes no grammar: it asks `symitar`, `zions` and
    `community_section` what they already know how to read.
    """
    from analysis.symitar import _DORMANT_RE
    from analysis.zions import _NO_ACTIVITY_RE
    from analysis.community_section import _summary, _money

    detail: dict = {}
    if _DORMANT_RE.search(text):
        detail["wording"] = "symitar"
        return DECLARATION, detail
    if _NO_ACTIVITY_RE.search(text):
        detail["wording"] = "zions"
        return DECLARATION, detail

    summary = _summary(text)
    if summary is None:
        detail["summary"] = "not fully printed"
        return NONE_PRINTED, detail
    beginning, ending = _money(summary.beginning), _money(summary.ending)
    credits, debits = _money(summary.credits), _money(summary.debits)
    detail["opening_printed"] = beginning is not None
    detail["closing_printed"] = ending is not None
    detail["pair_coincides"] = (
        beginning is not None and ending is not None
        and round(beginning - ending, 2) == 0.0
    )
    detail["zero_credit_total"] = credits == 0.0
    detail["zero_debit_total"] = debits == 0.0
    try:
        detail["zero_credit_count"] = int(str(summary.credit_count).strip() or "-1") == 0
        detail["zero_debit_count"] = int(str(summary.debit_count).strip() or "-1") == 0
    except ValueError:
        detail["zero_credit_count"] = detail["zero_debit_count"] = False
    if all(detail.get(key) for key in (
            "opening_printed", "closing_printed", "pair_coincides",
            "zero_credit_total", "zero_debit_total",
            "zero_credit_count", "zero_debit_count")):
        return ZERO_SUMMARY, detail
    return NONE_PRINTED, detail


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@dataclass
class DocSkips:
    sha16: str
    parser_id: str
    #: (site label, evidence class) for the CLAIMING registration's own attempt
    sections: list[tuple[str, str]] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    #: every skip seen during dispatch, including losing candidates' attempts
    all_sections: int = 0


#: Each registration's own `parse` entry point, from
#: `analysis/parser_registry_entries.py`. A skip is attributed to a document
#: only when it fired inside the entry point of the registration that CLAIMED
#: that document.
ENTRY_POINTS: dict[str, str] = {
    "symitar": "parse_symitar_statement",
    "community_section": "parse_community_section_statement",
    "dakota_west": "parse_dakota_west_statement",
    "mission_valley": "parse_mission_valley_statement",
    "zions": "parse_zions_statement",
}


def probe_document(sha: str, parser_id: str, cache: ColdCache,
                   watch: LineWatch, inert: InertWatch) -> DocSkips | None:
    from analysis.pipeline import analyze_markdown

    markdown, pages = cache.text(sha)
    if markdown is None:
        return None
    watch.hits.clear()
    inert.hits.clear()
    try:
        analyze_markdown(markdown, parse_mode="deterministic", sheets=pages)
    except Exception:
        # A refusal is data: the skips that fired before it still count.
        pass
    result = DocSkips(sha16=sha[:16], parser_id=parser_id)
    entry = ENTRY_POINTS.get(parser_id)
    result.all_sections = len(watch.hits) + len(inert.hits)
    for site, text, where in watch.hits:
        if entry is not None and where != entry:
            continue
        klass, detail = classify_evidence(text)
        result.sections.append((site.label, klass))
        result.evidence.append(detail)
    for text in inert.hits:
        klass, detail = classify_evidence(text)
        result.sections.append((ZIONS_LABEL, klass))
        result.evidence.append(detail)
    return result


DEFAULT_REGISTRATIONS = ("symitar", "community_section", "dakota_west",
                         "mission_valley", "zions")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="L1 design silent-skip probe")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--registrations", default=",".join(DEFAULT_REGISTRATIONS))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover
        pass

    problems = verify_sites()
    if problems:
        print("REFUSING: a watched line is not the line it is meant to be.")
        for problem in problems:
            print(f"  * {problem}")
        return 3

    registrations = tuple(r.strip() for r in args.registrations.split(",") if r.strip())
    rows = load_baseline_rows(args.run)
    cache = ColdCache(args.data_dir)

    results: dict[str, list[DocSkips]] = {}
    watch = LineWatch(LINE_SITES)
    inert = InertWatch()
    with inert, watch:
        for registration in registrations:
            shas = sorted(sha for sha, row in rows.items()
                          if (row.get("parser_id") or "") == registration
                          and (row.get("outcome_class") or "") == "validated")
            found: list[DocSkips] = []
            for sha in shas:
                probe = probe_document(sha, registration, cache, watch, inert)
                if probe is not None:
                    found.append(probe)
            results[registration] = found

    print("# L1-ARCH-DESIGN — the silent skip, on the DISPATCH PATH")
    print()
    print("Every row below is produced by RUNNING the reader over its own "
          "`validated` documents through "
          "`analyze_markdown(parse_mode=\"deterministic\")` and watching the "
          "skip execute. The watched line numbers are verified against the "
          "source text they must sit on before any document is read, so a zero "
          "here cannot be a refactor going unnoticed.")
    print()
    print("| registration | `validated` documents read | documents where a skip FIRES | sections skipped | (skips seen during dispatch, any candidate) |")
    print("|---|---:|---:|---:|---:|")
    total_read = total_docs = total_sections = total_all = 0
    for registration in registrations:
        found = results[registration]
        movers = [d for d in found if d.sections]
        sections = sum(len(d.sections) for d in found)
        every = sum(d.all_sections for d in found)
        total_read += len(found)
        total_docs += len(movers)
        total_sections += sections
        total_all += every
        print(f"| `{registration}` | {len(found)} | **{len(movers)}** | {sections} | {every} |")
    print(f"| **total** | **{total_read}** | **{total_docs}** | **{total_sections}** | {total_all} |")
    print()
    print("The last column is why the fourth exists. "
          "`analysis/parser_registry.py::resolve` calls `parse` on every "
          "CANDIDATE registration and records the decliners in "
          "`Dispatch.attempted`, and three of these registrations route into "
          "the same module function. A skip counted without asking whose parse "
          "attempt it belongs to attributes a losing candidate's drops to the "
          "winner. Only skips inside the CLAIMING registration's own entry "
          "point are counted in the columns that matter.")
    print()

    print("## Which site each skip fired at")
    print()
    print("| skip site | sections |")
    print("|---|---:|")
    by_site: collections.Counter = collections.Counter()
    for found in results.values():
        for doc in found:
            for label, _klass in doc.sections:
                by_site[label] += 1
    for site in LINE_SITES:
        print(f"| {site.label} | {by_site.get(site.label, 0)} |")
    print(f"| {ZIONS_LABEL} | {by_site.get(ZIONS_LABEL, 0)} |")
    print()

    print("## What the paper PRINTED on each skipped section")
    print()
    print("The three classes are the ones the checkpoint condition R-a can "
          "accept, plus the one it refuses. Each is decided by a module's OWN "
          "committed pattern or helper — `symitar._DORMANT_RE`, "
          "`zions._NO_ACTIVITY_RE`, `community_section._summary` — never by a "
          "grammar this instrument wrote.")
    print()
    print("| registration | `printed_dormancy_declaration` | `printed_zero_activity_summary` | `no_printed_evidence` |")
    print("|---|---:|---:|---:|")
    totals: collections.Counter = collections.Counter()
    for registration in registrations:
        counter: collections.Counter = collections.Counter()
        for doc in results[registration]:
            for _label, klass in doc.sections:
                counter[klass] += 1
                totals[klass] += 1
        print(f"| `{registration}` | {counter.get(DECLARATION, 0)} | "
              f"{counter.get(ZERO_SUMMARY, 0)} | {counter.get(NONE_PRINTED, 0)} |")
    print(f"| **total** | **{totals.get(DECLARATION, 0)}** | "
          f"**{totals.get(ZERO_SUMMARY, 0)}** | **{totals.get(NONE_PRINTED, 0)}** |")
    print()
    print(f"**Sections skipped with NO printed evidence of their empty state: "
          f"{totals.get(NONE_PRINTED, 0)}.** That is what a ruling on R-a's "
          f"reach costs: every such section is one whose document could not be "
          f"re-founded on printed evidence and would have to be refused.")
    print()

    print("## The zero-activity summary, clause by clause")
    print()
    print("Only the sections that reached the summary test are counted here — "
          "a section carrying a printed declaration is classified before it.")
    print()
    clauses = ("opening_printed", "closing_printed", "pair_coincides",
               "zero_credit_total", "zero_debit_total",
               "zero_credit_count", "zero_debit_count")
    reached = [d for found in results.values() for doc in found for d in doc.evidence
               if "summary" not in d and "wording" not in d]
    print("| clause | sections satisfying it |")
    print("|---|---:|")
    for clause in clauses:
        print(f"| `{clause}` | {sum(1 for d in reached if d.get(clause))} of {len(reached)} |")
    print()

    if args.json:
        args.json.write_text(json.dumps({
            "registrations": list(registrations),
            "documents_read": total_read,
            "documents_with_a_skip": total_docs,
            "sections_skipped": total_sections,
            "by_site": dict(by_site),
            "by_class": dict(totals),
            "movers": {
                registration: sorted(d.sha16 for d in results[registration] if d.sections)
                for registration in registrations
            },
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

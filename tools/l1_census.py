"""L1INV instrument 1 — the L-1 population, enumerated and classified.

READ-ONLY. Changes nothing, registers nothing, publishes no verdict. It does
not call `analyze_markdown` or `cached_analysis`: the readers' own entry points
and their own module-level gates are called directly, so this probe can never
be mistaken for a production path and needs no entry in
`corpus_gate.EXCLUDED_ANALYSIS_CALLERS`.

What it answers (card L1-CU-SUFFIX-INVESTIGATION, method step 1):

* WHO is in the L-1 population — the 176 documents under the census's
  `FAM-CU-SUFFIX-CORE` groups, the five `DECL:*` reader groups the batch-7
  escalation named, and `WH:atb`;
* WHICH of the `DECL:*` declines are L-1 refusals rather than grammar gaps.
  That is not asserted from the escalation's prose: each reader's OWN gate is
  re-run on the run-of-record cached text and named. A document is
  `L1-REFUSED:<gate>` only when the gate that fires is the one whose comment
  in that module cites the single-account schema;
* WHICH pinned documents (`docs/balance-metrics-audit-results.csv`, 109) the
  L-1 readers claim, so the regression surface of any publication-model change
  is enumerated rather than estimated.

PRIVACY. Nothing this instrument prints comes off a page: counts, gate names,
parser ids, group names and content sha16s only. Section text is read into
memory, matched, and discarded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.cohort_replay import ColdCache  # noqa: E402

#: The census group that carries the credit-union suffix reservoir. Read from
#: `opportunity_estimates.json` rather than copied, so the population cannot
#: drift away from the committed census.
CU_OPPORTUNITY_KEY = "FAM-CU-SUFFIX-CORE"

#: The reader groups the batch-7 escalation ("L-1 multi-account statements —
#: the single largest lever now", WAVE2_EXECUTION_LOG) named as honest L-1
#: refusals, plus ATB's consolidated statements.
DECL_GROUPS = (
    "DECL:huntington",
    "DECL:community_section",
    "DECL:navy_federal",
    "DECL:capital_one",
    "DECL:consumers",
)
ATB_GROUP = "WH:atb"


# ---------------------------------------------------------------------------
# the readers' own L-1 gates, re-run
# ---------------------------------------------------------------------------
#
# Each probe below calls the reader's own code. None of them re-implements a
# gate: where a module states the rule in one expression, that expression is
# evaluated; where the rule is a property of a helper's return value, the
# helper is called. The gate NAME is what is reported.


def _gate_huntington(markdown: str) -> tuple[str, str]:
    """`huntington.py:659` — `_LINE_OF_CREDIT_RE` refuses the statement that
    prints a Business Overdraft Protection line of credit as a second account."""
    from analysis import huntington

    if not huntington.detect(markdown).claims:
        return "not-claimed", "detect().claims is False"
    if huntington._LINE_OF_CREDIT_RE.search(markdown):
        return "L1", "huntington:_LINE_OF_CREDIT_RE"
    return "OTHER", "huntington:grammar (period/summary/blocks/validate)"


def _gate_community_section(markdown: str) -> tuple[str, str]:
    """`community_section.py:990` — `len(parsed) != 1`: more than one printed
    account posted, and the schema holds one."""
    from analysis import community_section

    if not community_section.detect_platform(markdown).claims:
        return "not-claimed", "detect_platform().claims is False"
    domains = community_section._masthead_domains(markdown)
    if len(domains) > 1:
        return "OTHER", "community_section:_masthead_domains>1"
    issuer = next(iter(domains)) if domains else None
    posting = 0
    blocks = community_section._account_blocks(markdown)
    for product, _number, block in blocks:
        stmt = community_section._parse_sectioned_statement(
            block, bank=issuer, account_name=product, account_number_pattern=None
        )
        if stmt is not None and stmt.transactions:
            posting += 1
    if posting > 1:
        return "L1", "community_section:len(parsed)!=1 (>1 posting section)"
    if posting == 0:
        return "OTHER", "community_section:len(parsed)!=1 (0 posting sections)"
    return "OTHER", "community_section:downstream"


def _gate_navy_federal(markdown: str) -> tuple[str, str]:
    """`navy_federal.py:_checking_account` — more than one checking PRODUCT is
    the L-1 refusal; zero is a grammar gap."""
    from analysis import navy_federal

    if not navy_federal.detect(markdown).claims:
        return "not-claimed", "detect().claims is False"
    checking = {
        product
        for product, _account in navy_federal._deposit_accounts(markdown)
        if product.lower().endswith("checking")
    }
    if len(checking) > 1:
        return "L1", "navy_federal:_checking_account (>1 checking product)"
    if len(checking) == 0:
        return "OTHER", "navy_federal:_checking_account (0 checking products)"
    if navy_federal._checking_account(markdown) is None:
        return "OTHER", "navy_federal:_checking_account (heading unconfirmed)"
    return "OTHER", "navy_federal:downstream"


def _gate_consumers(markdown: str) -> tuple[str, str]:
    """`consumers.py:111` — the memorized section is absent. The module's own
    docstring records WHY it is not widened: widening publishes one of several
    active ledgers under one account's name (L-1)."""
    from analysis import consumers

    if not consumers.detect(markdown).claims:
        return "not-claimed", "detect().claims is False"
    if not consumers._primary_checking_section(markdown):
        return "L1", "consumers:_primary_checking_section (CONS-L1)"
    return "OTHER", "consumers:downstream"


def _gate_capital_one(markdown: str) -> tuple[str, str]:
    """`capital_one.py` states no L-1 gate in code: the refusal is emergent —
    `_native_summary` matches ONE `Previous Balance ... Ending Balance` block
    and the declining documents print several. The structural fact is counted
    here and named as such, never asserted as a gate the module contains."""
    import re

    from analysis import capital_one

    if not capital_one.detect(markdown).claims:
        return "not-claimed", "detect().claims is False"
    blocks = len(re.findall(r"Previous Balance\s+\d{2}/\d{2}/\d{2}", markdown))
    if blocks > 1:
        return "L1", f"capital_one:emergent (n_summary_blocks={blocks})"
    return "OTHER", f"capital_one:grammar (n_summary_blocks={blocks})"


GATES = {
    "DECL:huntington": ("huntington", _gate_huntington),
    "DECL:community_section": ("community_section", _gate_community_section),
    "DECL:navy_federal": ("navy_federal", _gate_navy_federal),
    "DECL:capital_one": ("capital_one", _gate_capital_one),
    "DECL:consumers": ("consumers", _gate_consumers),
}

#: The reader entry point each gate belongs to, called to CONFIRM the decline
#: the run of record recorded (a gate probe on a document the reader would in
#: fact publish would be measuring nothing).
PARSERS = {
    "huntington": ("analysis.huntington", "parse_huntington_statement"),
    "community_section": ("analysis.community_section", "parse_community_section_statement"),
    "navy_federal": ("analysis.navy_federal", "parse_navy_federal_statement"),
    "capital_one": ("analysis.capital_one", "parse_capital_one_statement"),
    "consumers": ("analysis.consumers", "parse_consumers_statement"),
}


def _parse(parser: str, markdown: str):
    import importlib

    module_name, function = PARSERS[parser]
    return getattr(importlib.import_module(module_name), function)(markdown)


# ---------------------------------------------------------------------------
# population
# ---------------------------------------------------------------------------


def load_census(census_dir: Path):
    groups = json.loads((census_dir / "clusters.json").read_text(encoding="utf-8"))["groups"]
    opportunities = json.loads(
        (census_dir / "opportunity_estimates.json").read_text(encoding="utf-8")
    )
    per_sha = list(csv.DictReader((census_dir / "per_sha.csv").open(encoding="utf-8")))
    return groups, opportunities, per_sha


def population(groups: dict, opportunities: dict) -> list[tuple[str, str, str]]:
    """[(band, group, sha16)] for the whole L-1 population, in census order."""
    out: list[tuple[str, str, str]] = []
    for name in opportunities[CU_OPPORTUNITY_KEY]["groups"]:
        for sha16 in groups[name]["shas16"]:
            out.append(("CU-SUFFIX", name, sha16))
    for name in DECL_GROUPS:
        for sha16 in groups[name]["shas16"]:
            out.append(("DECL-L1-CANDIDATE", name, sha16))
    for sha16 in groups[ATB_GROUP]["shas16"]:
        out.append(("ATB", ATB_GROUP, sha16))
    return out


def pinned_paths(repo: Path) -> list[str]:
    csv_path = repo / "docs" / "balance-metrics-audit-results.csv"
    return [row["path"] for row in csv.DictReader(csv_path.open(encoding="utf-8"))]


def pinned_shas(repo: Path) -> dict[str, str]:
    """{content sha256 (upper) -> pinned relative path}. The corpus root is
    gitignored; a missing file is reported, never guessed."""
    out: dict[str, str] = {}
    root = repo / "Bank Statements"
    for rel in pinned_paths(repo):
        path = root / rel
        if not path.is_file():
            continue
        out[hashlib.sha256(path.read_bytes()).hexdigest().upper()] = rel
    return out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    # The Windows console is cp1252; the report is markdown with arrows and
    # multiplication signs in it. Reconfigure rather than downgrade the text.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover - non-tty callers
        pass

    repo = Path(__file__).resolve().parents[1]
    groups, opportunities, per_sha = load_census(args.census_dir)
    sha_by16 = {row["sha16"]: row["sha"] for row in per_sha}
    facts = {row["sha16"]: row for row in per_sha}
    pop = population(groups, opportunities)
    cache = ColdCache(args.data_dir)

    print("# L1INV — L-1 population census")
    print(f"# census_dir={args.census_dir}")
    print(f"# data_dir={args.data_dir}")
    print()

    # -- 1. the population -------------------------------------------------
    by_band = Counter(band for band, _g, _s in pop)
    print("## Population")
    print()
    print("| band | groups | documents |")
    print("|---|---:|---:|")
    for band in ("CU-SUFFIX", "DECL-L1-CANDIDATE", "ATB"):
        n_groups = len({g for b, g, _s in pop if b == band})
        print(f"| {band} | {n_groups} | {by_band[band]} |")
    print(f"| **total** | {len({g for _b, g, _s in pop})} | **{len(pop)}** |")
    print()

    print("### CU-SUFFIX groups (census `FAM-CU-SUFFIX-CORE`)")
    print()
    print("| group | documents | route (native/ocr) | text density |")
    print("|---|---:|---|---|")
    for name in opportunities[CU_OPPORTUNITY_KEY]["groups"]:
        g = groups[name]
        routes = "/".join(f"{k} {v}" for k, v in sorted(g.get("routes", {}).items()))
        dens = Counter(facts[s]["text_density"] for s in g["shas16"])
        print(f"| `{name}` | {g['docs']} | {routes} | "
              f"{', '.join(f'{k} {v}' for k, v in dens.most_common())} |")
    print()

    # -- 2. the DECL gates re-run -----------------------------------------
    print("## `DECL:*` refusals — each reader's OWN L-1 gate, re-run on the "
          "run-of-record cached text")
    print()
    print("| group | reader | docs | declines confirmed | L-1-refused | other | "
          "gate(s) that fired |")
    print("|---|---|---:|---:|---:|---:|---|")
    decl_detail: dict[str, list[dict]] = {}
    gate_totals: Counter = Counter()
    for group in DECL_GROUPS:
        reader, gate = GATES[group]
        rows = []
        confirmed = 0
        klasses: Counter = Counter()
        gates_fired: Counter = Counter()
        for sha16 in groups[group]["shas16"]:
            markdown, _pages = cache.text(sha_by16[sha16])
            if markdown is None:
                rows.append({"sha16": sha16, "class": "NO-TEXT", "gate": "cache miss"})
                klasses["NO-TEXT"] += 1
                continue
            try:
                declined = _parse(reader, markdown) is None
            except Exception as exc:  # a raising reader is a decline of a
                declined = True       # different kind; name the type, not the text
                gates_fired[f"{reader}:raises {type(exc).__name__}"] += 1
            confirmed += int(declined)
            klass, gate_name = gate(markdown)
            klasses[klass] += 1
            gates_fired[gate_name] += 1
            gate_totals[f"{group} | {klass} | {gate_name}"] += 1
            rows.append({"sha16": sha16, "class": klass, "gate": gate_name,
                         "decline_confirmed": declined})
        decl_detail[group] = rows
        print(f"| `{group}` | `{reader}` | {len(rows)} | {confirmed} | "
              f"{klasses['L1']} | {klasses['OTHER'] + klasses['not-claimed']} | "
              f"{'; '.join(f'{k} ×{v}' for k, v in gates_fired.most_common())} |")
    print()
    print("Per-document gate assignment (sha16 → class → gate):")
    print()
    print("| group | sha16 | class | gate |")
    print("|---|---|---|---|")
    for group, rows in decl_detail.items():
        for row in rows:
            print(f"| `{group}` | `{row['sha16']}` | {row['class']} | `{row['gate']}` |")
    print()

    # -- 3. the pinned corpus ---------------------------------------------
    print("## Pinned corpus (109) — which pinned documents the L-1 readers claim")
    print()
    pinned = pinned_shas(repo)
    by_sha: dict[str, dict] = {}
    with args.rows.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            by_sha.setdefault(row["content_sha256"].upper(), row)
    # A REGISTRATION id is not a module: `community_section` publishes under
    # three ids (`community_section`, `dakota_west`, `mission_valley`), so a
    # hand list of module names would under-report the pinned surface. Expand
    # through the registry.
    from analysis.parser_registry import registrations

    module_of_id = {
        reg.id: getattr(reg.parse, "__module__", "?").rsplit(".", 1)[-1]
        for reg in registrations()
    }
    l1_modules = set(PARSERS) | {"symitar", "atb"}
    l1_readers = {pid for pid, mod in module_of_id.items() if mod in l1_modules}
    claimed: dict[str, list[str]] = defaultdict(list)
    resolved = 0
    for sha, rel in pinned.items():
        row = by_sha.get(sha)
        if row is None:
            continue
        resolved += 1
        parser_id = row.get("parser_id") or "-"
        claimed[parser_id].append(sha[:16])
    print(f"pinned paths on disk: {len(pinned)} of {len(pinned_paths(repo))}; "
          f"resolved in the run of record: {resolved}")
    print()
    print("| parser_id | module | pinned documents | carries an L-1 rule today |")
    print("|---|---|---:|---|")
    for parser_id, shas in sorted(claimed.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"| `{parser_id}` | `{module_of_id.get(parser_id, '-')}` | {len(shas)} | "
              f"{'YES' if parser_id in l1_readers else 'no'} |")
    print()
    print("Pinned documents claimed by a reader that carries an L-1 rule "
          "(sha16 — the regression surface of any publication-model change):")
    print()
    for parser_id in sorted(l1_readers):
        if parser_id in claimed:
            print(f"- `{parser_id}`: {', '.join(sorted(claimed[parser_id]))}")
    print()

    if args.json:
        args.json.write_text(json.dumps({
            "population": [{"band": b, "group": g, "sha16": s} for b, g, s in pop],
            "decl_gates": decl_detail,
            "gate_totals": dict(gate_totals),
            "pinned_by_parser": {k: sorted(v) for k, v in claimed.items()},
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

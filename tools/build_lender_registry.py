"""Render the lender registry from the curated ledger (contract C10), and check the ledger.

    python -m tools.build_lender_registry --check            validate docs/lender-registry-ledger.json
    python -m tools.build_lender_registry --write            validate, then render both outputs
    python -m tools.build_lender_registry --privacy-review   the lines a person reads before a commit

The ledger is curated outside the code; ``tools/lender_ledger.py`` holds its schema and its validator. This
tool renders, deterministically and without inferring anything:
  * the GENERATED block of ``analysis/classification_registry.py`` (the contract C2 tables);
  * ``docs/lender-registry-evidence.md``, the evidence ledger of spec section 5, for the owner to read.

Exit codes: 0 done; 1 the ledger has problems (nothing is written); 2 refused (no ledger, or not JSON).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import lender_ledger  # noqa: E402
from tools.lender_ledger import TABLES, LedgerEntity, Rules, render_tables  # noqa: E402

REGISTRY_PATH = ROOT / "analysis" / "classification_registry.py"
EVIDENCE_PATH = ROOT / "docs" / "lender-registry-evidence.md"
BEGIN_MARKER = "# --- BEGIN GENERATED: tools/build_lender_registry.py ---"
END_MARKER = "# --- END GENERATED: tools/build_lender_registry.py ---"
HEADER = (
    "# Rendered by tools/build_lender_registry.py from docs/lender-registry-ledger.json (contract C10).",
    "# Never edit by hand: change the ledger, then run python -m tools.build_lender_registry --write.",
)


# --- the GENERATED block -----------------------------------------------------------------------------------


def render_block(tables: dict[str, dict[str, tuple[str, ...]]]) -> str:
    """The GENERATED block: one typed dict literal per C2 table, in TABLES order, with "\\n" line endings."""
    lines = [BEGIN_MARKER, *HEADER, ""]
    for _group, table, heading in TABLES:
        lines.append(f"#: {heading}.")
        entries = tables[table]
        if not entries:
            lines += [f"{table}: dict[str, tuple[str, ...]] = {{}}", ""]
            continue
        lines.append(f"{table}: dict[str, tuple[str, ...]] = {{")
        for name, aliases in entries.items():
            inner = ", ".join(json.dumps(alias) for alias in aliases) + ("," if len(aliases) == 1 else "")
            line = f"    {json.dumps(name)}: ({inner}),"
            if len(line) <= 110:
                lines.append(line)
            else:
                lines.append(f"    {json.dumps(name)}: (")
                lines.extend(f"        {json.dumps(alias)}," for alias in aliases)
                lines.append("    ),")
        lines += ["}", ""]
    lines.append(END_MARKER)
    return "\n".join(lines)


def current_block(source: str) -> str:
    """The GENERATED block of a registry source, markers included, with "\\n" line endings."""
    text = source.replace("\r\n", "\n")
    start = text.index(BEGIN_MARKER)
    return text[start:text.index(END_MARKER, start) + len(END_MARKER)]


def replace_block(source: str, block: str) -> str:
    """The registry source with its GENERATED block replaced; the file keeps its own line endings."""
    newline = "\r\n" if "\r\n" in source else "\n"
    text = source.replace("\r\n", "\n")
    start = text.index(BEGIN_MARKER)
    end = text.index(END_MARKER, start) + len(END_MARKER)
    return (text[:start] + block + text[end:]).replace("\n", newline)


# --- the evidence ledger (spec section 5) ------------------------------------------------------------------


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\r", " ").replace("\n", " ").strip() or "-"


def _verdicts(entity: LedgerEntity) -> str:
    return "; ".join(f"{v.round} {v.verdict}" + ("" if v.confirmed else " (not confirmed)")
                     for v in entity.verdicts) or "none"


def _source(entity: LedgerEntity) -> str:
    return entity.evidence[0].source if entity.evidence else "none recorded"


def _looked(entity: LedgerEntity) -> str:
    return ", ".join(entity.where_looked) or "none recorded"


def _table_row(entity: LedgerEntity) -> str:
    looked = "-" if entity.status == "admitted" else _looked(entity)
    aliases = ", ".join(dict.fromkeys(entity.aliases))
    return (f"| {_cell(entity.entity)} | {entity.group} | {_cell(entity.business_type)} | "
            f"{_cell(_verdicts(entity))} | {entity.status} | {_cell(aliases)} | {_cell(_source(entity))} | "
            f"{_cell(looked)} | {_cell(entity.notes)} |")


def _now(move: lender_ledger.Move) -> str:
    """Where a moved entity of today's registry is now, the entity it merges into, if any, and each of its
    aliases that the owner gave to another company."""
    notes = [f"merged into {move.holder}"] if move.merged else []
    notes += [f"{alias} reattributed to {holder}" for alias, holder in move.reattributed]
    return f"{move.now} ({'; '.join(notes)})" if notes else move.now


def _listed_row(entity: LedgerEntity) -> str:
    return (f"| {_cell(entity.entity)} | {entity.group} | {_cell(entity.business_type)} | "
            f"{_cell(_verdicts(entity))} | {_cell(_source(entity))} | {_cell(_looked(entity))} | "
            f"{_cell(entity.notes)} |")


def render_evidence(entities: list[LedgerEntity], digest: str, rules: Rules) -> str:
    """The evidence ledger (spec section 5): every entity with its group, its verdicts, its first public source
    (else "none recorded") and, for anything not admitted, where the researchers looked. No statement text,
    amounts, account numbers or customer names."""
    tables = render_tables(entities)
    by_name = {entity.entity: entity for entity in entities}
    lines = [
        "# Lender registry evidence",
        "",
        f"Rendered by `tools/build_lender_registry.py` from `docs/lender-registry-ledger.json` (ledger "
        f"`sha256:{digest}`). Never edit by hand: change the ledger, then run "
        "`python -m tools.build_lender_registry --write`.",
        "",
        "The ledger is curated outside the code (contract C10): the orchestrator's research workflow consolidates "
        "the research into one entity per company, checks each entity adversarially and runs a completeness "
        "critic. The code only validates the ledger and renders this page and the GENERATED block of "
        "`analysis/classification_registry.py` from it. This page holds no statement text, amounts, account "
        "numbers or customer names.",
        "",
        "## Admission",
        "",
        "- An admitted entity is in its group's table. It has at least one public source, and an independent "
        "second agent's verdict of upheld or corrected that confirms it (spec section 5).",
        "- An entity under review is in `POTENTIAL_LENDER_ALIASES` (review, never counted), whatever its group. "
        "No entity of a table read only with context (credit cards, card issuers, bank names, premium financing) "
        "is under review.",
        "- An entity awaiting an owner ruling, or rejected, is in no table. This page lists it with its group, its "
        "public source and where the researchers looked.",
        "- Every payee the owner named in spec section 2 is admitted in its ruled group: the validator refuses a "
        "ledger in which one is not.",
        "- An entity of the registry as it stood before this ledger changes place, or loses an alias, only with a "
        "reason: a sentence of its notes that starts `Move:` (spec section 9). The moves section shows that reason.",
        "- A premium-finance alias equals an alias of a hand-kept insurer (`INSURANCE_PROVIDER_ALIASES`) only on the "
        "owner's ruling (`PREMIUM_FINANCE_INSURER_ALIASES`). The insurance rule reads the premium-finance table "
        "first, so rows that print that alias stay insurance and are also flagged premium financing, and no overlap "
        "with it awaits a ruling.",
        "- An entity of that registry that the owner merged into a ledger entity (`MERGED_REGISTRY_ENTITIES`) is held "
        "by that entity under its name. The moves section shows the merge, and an alias the merge loses needs a "
        "`Move:` sentence in that entity's notes.",
        "- An alias of that registry that the owner ruled names another company (`REATTRIBUTED_REGISTRY_ALIASES`) is "
        "held by that company's ledger entity, and the known-payee and potential tables read it as that entity or not "
        "at all. The moves section shows it beside the entity that held it, and it is not counted as lost.",
        "",
        "## Summary",
        "",
        "| Table | Entities | Aliases |",
        "|---|---:|---:|",
    ]
    for _group, table, _heading in TABLES:
        entries = tables[table]
        lines.append(f"| `{table}` | {len(entries)} | {sum(len(aliases) for aliases in entries.values())} |")
    for _group, table, heading in TABLES:
        lines += ["", f"## {heading} (`{table}`)", ""]
        if not tables[table]:
            lines.append("None.")
            continue
        lines += ["| Entity | Group | Business type | Verdicts | Status | Aliases | Source | Where the researchers "
                  "looked | Notes |", "|---|---|---|---|---|---|---|---|---|"]
        lines += [_table_row(by_name[name]) for name in tables[table]]
    moves, _missing = lender_ledger.baseline_moves(entities, rules.baseline, rules.merged, rules.reattributed)
    lines += ["", "## Moves from the registry as it stood before this ledger", ""]
    if moves:
        lines += ["| Entity | Was | Now | Aliases of today's registry lost | Why |", "|---|---|---|---:|---|"]
        lines += [f"| {_cell(lender_ledger.mask_digit_runs(m.entity))} | {m.was} | "
                  f"{_cell(lender_ledger.mask_digit_runs(_now(m)))} | {m.lost} | "
                  f"{_cell(lender_ledger.mask_digit_runs(m.reason))} |" for m in moves]
    else:
        lines.append("None.")
    lines += ["", "## Awaiting an owner ruling", ""]
    waiting = [entity for entity in entities if entity.status == "owner_ruling"]
    insurers = rules.hand_kept.get("INSURANCE_PROVIDER_ALIASES", {})
    overlaps = lender_ledger.premium_insurer_overlaps(entities, insurers)
    if waiting:
        lines += ["| Entity | Group | Business type | Verdicts | Source | Where the researchers looked | Notes |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_listed_row(entity) for entity in waiting]
        if overlaps:
            lines.append("")
    for premium, insurer in overlaps:
        lines.append(f"- {premium} (premium financing) has an alias that contains an alias of the hand-kept "
                     f"insurer {insurer} (`INSURANCE_PROVIDER_ALIASES`). The insurance rule reads the premium-finance "
                     f"table first, so {premium} keeps its own rows, and rows that name only {insurer} stay plain "
                     "insurance, unflagged. The owner rules whether those rows are premium financing.")
    if not (waiting or overlaps):
        lines.append("None.")
    lines += ["", "## Rejected", ""]
    rejected = [entity for entity in entities if entity.status == "rejected"]
    if rejected:
        lines += ["| Entity | Group | Business type | Verdicts | Source | Where the researchers looked | Notes |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_listed_row(entity) for entity in rejected]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


# --- the command line ----------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate the ledger; write nothing")
    mode.add_argument("--write", action="store_true",
                      help="validate the ledger, then render the registry block and the evidence ledger")
    mode.add_argument("--privacy-review", action="store_true",
                      help="print the names and aliases a person reads before the ledger is committed")
    parser.add_argument("--ledger", type=Path, default=lender_ledger.LEDGER_PATH)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    args = parser.parse_args(argv)
    if not args.ledger.is_file():
        print(f"refused: {args.ledger} does not exist; the orchestrator's consolidation workflow commits it "
              "(contract C10)", file=sys.stderr)
        return 2
    try:
        data = lender_ledger.read_ledger(args.ledger)
    except (OSError, ValueError) as error:
        print(f"refused: {args.ledger} is not readable JSON ({type(error).__name__})", file=sys.stderr)
        return 2
    if args.privacy_review:
        entities, problems = lender_ledger.parse_ledger(data)
        for line in [f"problem: {problem}" for problem in problems] or lender_ledger.privacy_review(entities):
            print(line)
        return 1 if problems else 0
    rules = lender_ledger.current_rules()
    problems = lender_ledger.validate(data, rules)
    if problems:
        for problem in problems:
            print(f"problem: {problem}")
        print(f"refused: {len(problems)} problem(s); nothing was written")
        return 1
    entities, _problems = lender_ledger.parse_ledger(data)
    digest = lender_ledger.ledger_digest(data)
    print(f"ledger ok: {len(entities)} entities, sha256:{digest}")
    moves, _missing = lender_ledger.baseline_moves(entities, rules.baseline, rules.merged, rules.reattributed)
    for move in moves:
        merge = f"merged into {move.holder}; " if move.merged else ""
        given = "".join(f"; {alias} reattributed to {holder}" for alias, holder in move.reattributed)
        if move.merged:
            unneeded = "the owner's merge, MERGED_REGISTRY_ENTITIES"
        elif move.now == move.was:
            unneeded = "the owner's reattribution, REATTRIBUTED_REGISTRY_ALIASES"
        else:
            unneeded = "spec section 4.1"
        print(lender_ledger.mask_digit_runs(
            f"move: {move.entity} ({move.table}): {merge}{move.was} -> {move.now}, {move.lost} of today's aliases "
            f"lost{given}; why: {move.reason or f'none needed ({unneeded})'}"))
    if args.check:
        return 0
    tables = render_tables(entities)
    source = args.registry.read_bytes().decode("utf-8")
    args.registry.write_bytes(replace_block(source, render_block(tables)).encode("utf-8"))
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_bytes(render_evidence(entities, digest, rules).encode("utf-8"))
    for _group, table, _heading in TABLES:
        entries = tables[table]
        print(f"{table}: {len(entries)} entities, {sum(len(aliases) for aliases in entries.values())} aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

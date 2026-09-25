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


def _looked(entity: LedgerEntity) -> str:
    return ", ".join(entity.where_looked) or "none recorded"


def _table_row(entity: LedgerEntity) -> str:
    source = entity.evidence[0].source if entity.evidence else "none recorded"
    looked = "-" if entity.status == "admitted" else _looked(entity)
    aliases = ", ".join(dict.fromkeys(entity.aliases))
    return (f"| {_cell(entity.entity)} | {_cell(entity.business_type)} | {_cell(_verdicts(entity))} | "
            f"{entity.status} | {_cell(aliases)} | {source} | {looked} | {_cell(entity.notes)} |")


def _listed_row(entity: LedgerEntity) -> str:
    return (f"| {_cell(entity.entity)} | {entity.group} | {_cell(entity.business_type)} | "
            f"{_cell(_verdicts(entity))} | {_looked(entity)} | {_cell(entity.notes)} |")


def render_evidence(entities: list[LedgerEntity], digest: str, rules: Rules) -> str:
    """The evidence ledger: every entity with its group, verdicts, public source and, for anything not
    admitted, where the researchers looked. No statement text, amounts, account numbers or customer names."""
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
        "- An entity awaiting an owner ruling, or rejected, is in no table. This page lists it with where the "
        "researchers looked.",
        "- Every payee the owner named in spec section 2 is admitted in its ruled group: the validator refuses a "
        "ledger in which one is not.",
        "- An entity of the registry as it stood before this ledger changes place, or loses an alias, only with a "
        "reason: a sentence of its notes that starts `Move:` (spec section 9). The moves section shows that reason.",
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
        lines += ["| Entity | Business type | Verdicts | Status | Aliases | Source | Where the researchers looked "
                  "| Notes |", "|---|---|---|---|---|---|---|---|"]
        lines += [_table_row(by_name[name]) for name in tables[table]]
    moves, _missing = lender_ledger.baseline_moves(entities, rules.baseline)
    lines += ["", "## Moves from the registry as it stood before this ledger", ""]
    if moves:
        lines += ["| Entity | Was | Now | Aliases of today's registry lost | Why |", "|---|---|---|---:|---|"]
        lines += [f"| {_cell(m.entity)} | {m.was} | {m.now} | {m.lost} | {_cell(m.reason)} |" for m in moves]
    else:
        lines.append("None.")
    lines += ["", "## Awaiting an owner ruling", ""]
    waiting = [entity for entity in entities if entity.status == "owner_ruling"]
    insurers = rules.hand_kept.get("INSURANCE_PROVIDER_ALIASES", {})
    overlaps = lender_ledger.premium_insurer_overlaps(entities, insurers)
    if waiting:
        lines += ["| Entity | Group | Business type | Verdicts | Where the researchers looked | Notes |",
                  "|---|---|---|---|---|---|"]
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
        lines += ["| Entity | Group | Business type | Verdicts | Where the researchers looked | Notes |",
                  "|---|---|---|---|---|---|"]
        lines += [_listed_row(entity) for entity in rejected]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"

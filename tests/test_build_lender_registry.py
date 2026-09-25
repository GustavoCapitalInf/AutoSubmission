"""tools/build_lender_registry.py: the deterministic rendering of a curated ledger (contract C10)."""
from __future__ import annotations

import pytest

from tests.lender_ledger_fixture import RULES, ledger
from tools import build_lender_registry as builder
from tools import lender_ledger

TABLE_NAMES = [table for _group, table, _heading in lender_ledger.TABLES]


def _entities(*changes):
    entities, problems = lender_ledger.parse_ledger(ledger(*changes))
    assert problems == []
    return entities


# --- the tables and the GENERATED block ----------------------------------------------------------------------


def test_each_entity_renders_into_the_table_of_its_group_and_status():
    tables = builder.render_tables(_entities())
    assert list(tables) == TABLE_NAMES
    assert tables["LENDER_ALIASES"] == {
        "Oldco Funding": ("OLDCO FUNDING", "OLDCO"),
        "Quillon Funding": ("QUILLON FUNDING", "QUILLONFUND"),
    }
    assert tables["ALTERNATIVE_POSITION_ALIASES"] == {"Ruledco": ("RULEDCO CAPITAL",)}
    assert tables["CARD_ISSUER_ALIASES"] == {"Oxbow Card": ("OXBOW CARD PMT",)}
    assert tables["CARD_ISSUER_CONTEXT_ALIASES"] == {"Oxbow": ("OXBOW",)}
    assert tables["FLOOR_PLAN_ALIASES"] == {"Gantry Floorplan Credit": ("GANTRY FLOORPLAN",)}
    assert tables["FACTORING_ALIASES"] == {"Loxley Factoring": ("LOXLEY FACTORING",)}
    assert tables["PREMIUM_FINANCE_ALIASES"] == {
        "Brisk Mutual Funding": ("BRISK MUTUAL FUNDING",),
        "Hollin Premium Finance": ("HOLLIN PREMIUM FIN",),
    }
    assert tables["BANK_NAME_ALIASES"] == {"Brambleway Bank": ("BRAMBLEWAY BANK",)}
    assert tables["POTENTIAL_LENDER_ALIASES"] == {"Heldco Advance": ("HELDCO ADVANCE",)}
    rendered = {name for table in tables.values() for name in table}
    assert "Marsh Recovery" not in rendered and "Tarnmoor Capital" not in rendered


def test_an_entity_under_review_renders_into_the_potential_table_whatever_its_group():
    tables = builder.render_tables(_entities((3, "status", "review")))
    assert "Brambleway Capital" not in tables["LINE_OF_CREDIT_ALIASES"]
    assert tables["POTENTIAL_LENDER_ALIASES"]["Brambleway Capital"] == ("BRAMBLEWAY CAPITAL",)


def test_the_block_is_python_that_defines_exactly_the_rendered_tables():
    data = ledger((0, "aliases", ["QUILLON FUNDING", "QUILLONFUND", "QUILLON FUNDING GROUP", "QUILLON FNDG",
                                  "QUILLON FUNDING SERVICES", "QUILLON FUNDNG", "QUILLON FUNDING PAYMENTS"]))
    entities, _problems = lender_ledger.parse_ledger(data)
    tables = builder.render_tables(entities)
    block = builder.render_block(tables)
    assert block.startswith(builder.BEGIN_MARKER + "\n") and block.endswith("\n" + builder.END_MARKER)
    assert max(len(line) for line in block.split("\n")) <= 110
    namespace: dict = {}
    exec(compile(block, "block", "exec"), namespace)
    assert [name for name in namespace if name.isupper()] == TABLE_NAMES
    assert {name: namespace[name] for name in TABLE_NAMES} == tables


def test_the_block_of_an_empty_ledger_defines_fourteen_empty_tables():
    block = builder.render_block(builder.render_tables([]))
    namespace: dict = {}
    exec(compile(block, "block", "exec"), namespace)
    assert {name: namespace[name] for name in TABLE_NAMES} == {name: {} for name in TABLE_NAMES}
    assert "#: Floor plan.\nFLOOR_PLAN_ALIASES: dict[str, tuple[str, ...]] = {}\n" in block


def test_replace_block_keeps_everything_outside_the_markers_and_the_line_endings():
    block = builder.render_block(builder.render_tables(_entities()))
    source = f"HEAD = 1\r\n{builder.BEGIN_MARKER}\r\nOLD = 1\r\n{builder.END_MARKER}\r\n\r\nKEEP = 2\r\n"
    replaced = builder.replace_block(source, block)
    assert "OLD = 1" not in replaced and replaced.startswith("HEAD = 1\r\n") and replaced.endswith("KEEP = 2\r\n")
    assert "\n" not in replaced.replace("\r\n", "")
    assert builder.current_block(replaced) == block


# --- the evidence ledger -------------------------------------------------------------------------------------


@pytest.fixture
def evidence():
    return builder.render_evidence(_entities(), "a" * 64, RULES)


def test_the_evidence_ledger_names_its_ledger_digest_and_every_table(evidence):
    assert f"(ledger `sha256:{'a' * 64}`)" in evidence
    assert "| `LENDER_ALIASES` | 2 | 4 |" in evidence
    assert "| `POTENTIAL_LENDER_ALIASES` | 1 | 1 |" in evidence
    for _group, table, heading in lender_ledger.TABLES:
        assert f"\n## {heading} (`{table}`)\n" in evidence
    assert "## Mortgages (`MORTGAGE_SERVICER_ALIASES`)\n\n| Entity |" in evidence


def test_the_evidence_ledger_rows_carry_the_source_and_for_review_where_the_researchers_looked(evidence):
    assert ("| Quillon Funding | mca_or_revenue_based_funder | r1 upheld | admitted | QUILLON FUNDING, QUILLONFUND | "
            "https://quillon.example/ | - | - |") in evidence
    assert ("| Heldco Advance | mca_or_revenue_based_funder | r2 unresolved (not confirmed) | review | "
            "HELDCO ADVANCE | none recorded | https://registry.example/heldco, https://heldco.example/ | "
            "Fabricated: identity unconfirmed. |") in evidence


def test_the_evidence_ledger_lists_moves_owner_rulings_overlaps_and_rejections(evidence):
    moves = evidence.split("## Moves from the registry as it stood before this ledger\n", 1)[1].split("\n## ", 1)[0]
    assert "| Ruledco | confirmed_lender | alternative_position | 0 | fabricated owner ruling, an alternative " \
           "position. |" in moves
    assert "| Westfen Leasing | lease_or_equipment_financing | lease_or_rental | 0 | - |" in moves
    waiting = evidence.split("## Awaiting an owner ruling\n", 1)[1].split("\n## ", 1)[0]
    assert ("| Marsh Recovery | potential_lender | servicer_or_processor_for_funders | r2 unresolved (not confirmed) "
            "| https://marsh.example/, https://registry.example/marsh | Fabricated: a collector whose funder is "
            "unknown; the owner decides. |") in waiting
    assert ("- Brisk Mutual Funding (premium financing) has an alias that contains an alias of the hand-kept insurer "
            "Brisk Mutual (`INSURANCE_PROVIDER_ALIASES`).") in waiting
    rejected = evidence.split("## Rejected\n", 1)[1]
    assert ("| Tarnmoor Capital | confirmed_lender | mca_or_revenue_based_funder | r2 refuted (not confirmed) | "
            "https://tarnmoor.example/ | Fabricated: a bakery, not a funder. |") in rejected
    assert "TARNMOOR CAP" not in evidence and "MARSH RECOVERY" not in evidence


def test_the_evidence_ledger_is_the_same_text_every_time(evidence):
    assert builder.render_evidence(_entities(), "a" * 64, RULES) == evidence

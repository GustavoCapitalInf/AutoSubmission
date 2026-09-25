"""tools/build_lender_registry.py: the deterministic rendering of a curated ledger (contract C10)."""
from __future__ import annotations

import dataclasses
import json
import re

import pytest

from tests.lender_ledger_fixture import BASELINE, RULES, ledger
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


def test_the_evidence_ledger_rows_carry_the_group_the_source_and_for_review_where_the_researchers_looked(evidence):
    assert ("| Quillon Funding | confirmed_lender | mca_or_revenue_based_funder | r1 upheld | admitted | "
            "QUILLON FUNDING, QUILLONFUND | https://quillon.example/ | - | - |") in evidence
    assert ("| Heldco Advance | confirmed_lender | mca_or_revenue_based_funder | r2 unresolved (not confirmed) | "
            "review | HELDCO ADVANCE | none recorded | https://registry.example/heldco, https://heldco.example/ | "
            "Fabricated: identity unconfirmed. |") in evidence


def test_an_entity_under_review_shows_its_researched_group_in_the_potential_table():
    evidence = builder.render_evidence(_entities((3, "status", "review")), "a" * 64, RULES)
    potential = evidence.split("(`POTENTIAL_LENDER_ALIASES`)\n", 1)[1].split("\n## ", 1)[0]
    assert ("| Brambleway Capital | line_of_credit | business_loc_provider | r1 upheld | review | "
            "BRAMBLEWAY CAPITAL | https://brambleway.example/ | https://brambleway.example/ | - |") in potential


def test_the_evidence_ledger_lists_moves_owner_rulings_overlaps_and_rejections(evidence):
    moves = evidence.split("## Moves from the registry as it stood before this ledger\n", 1)[1].split("\n## ", 1)[0]
    assert "| Ruledco | confirmed_lender | alternative_position | 0 | fabricated owner ruling, an alternative " \
           "position. |" in moves
    assert "| Westfen Leasing | lease_or_equipment_financing | lease_or_rental | 0 | - |" in moves
    waiting = evidence.split("## Awaiting an owner ruling\n", 1)[1].split("\n## ", 1)[0]
    assert ("| Marsh Recovery | potential_lender | servicer_or_processor_for_funders | r2 unresolved (not confirmed) "
            "| none recorded | https://marsh.example/, https://registry.example/marsh | Fabricated: a collector whose "
            "funder is unknown; the owner decides. |") in waiting
    assert ("- Brisk Mutual Funding (premium financing) has an alias that contains an alias of the hand-kept insurer "
            "Brisk Mutual (`INSURANCE_PROVIDER_ALIASES`).") in waiting
    rejected = evidence.split("## Rejected\n", 1)[1]
    assert ("| Tarnmoor Capital | confirmed_lender | mca_or_revenue_based_funder | r2 refuted (not confirmed) | "
            "https://tarnmoor.example/ | https://registry.example/tarnmoor | Fabricated: a bakery, not a funder. "
            "|") in rejected
    assert "TARNMOOR CAP" not in evidence and "MARSH RECOVERY" not in evidence


def test_a_pipe_in_a_source_or_where_looked_never_splits_an_evidence_row():
    entities = _entities((0, "evidence", [{"source": "https://quillon.example/a|b", "note": "fabricated"}]),
                         (15, "where_looked", ["https://heldco.example/a|b"]),
                         (17, "where_looked", ["https://registry.example/t|x"]))
    evidence = builder.render_evidence(entities, "a" * 64, RULES)
    for section in evidence.split("\n## ")[1:]:
        rows = [line for line in section.splitlines() if line.startswith("|")]
        assert len({row.count("|") for row in rows}) <= 1, section.splitlines()[0]
    assert "| https://quillon.example/a/b | - | - |" in evidence
    assert "| none recorded | https://heldco.example/a/b |" in evidence
    assert "| https://tarnmoor.example/ | https://registry.example/t/x |" in evidence


def test_the_evidence_ledger_is_the_same_text_every_time(evidence):
    assert builder.render_evidence(_entities(), "a" * 64, RULES) == evidence


# --- the command line --------------------------------------------------------------------------------------


def _registry_source() -> str:
    return (f'"""Fabricated registry."""\r\nHEAD = 1\r\n\r\n{builder.BEGIN_MARKER}\r\nOLD = 1\r\n'
            f"{builder.END_MARKER}\r\n\r\nKEEP = 2\r\n")


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(lender_ledger, "current_rules", lambda: RULES)
    ledger_file = tmp_path / "ledger.json"
    ledger_file.write_text(json.dumps(ledger(), indent=2), encoding="utf-8")
    registry_file = tmp_path / "registry.py"
    registry_file.write_bytes(_registry_source().encode("utf-8"))
    return {"ledger": ledger_file, "registry": registry_file, "evidence": tmp_path / "docs" / "evidence.md"}


def _args(paths, mode):
    return [mode, "--ledger", str(paths["ledger"]), "--registry", str(paths["registry"]),
            "--evidence", str(paths["evidence"])]


def test_check_accepts_a_clean_ledger_prints_every_move_and_writes_nothing(paths, capsys):
    assert builder.main(_args(paths, "--check")) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"ledger ok: 18 entities, sha256:{lender_ledger.ledger_digest(ledger())}",
        "move: Ruledco (CONFIRMED_LENDER_ALIASES): confirmed_lender -> alternative_position, 0 of today's aliases "
        "lost; why: fabricated owner ruling, an alternative position.",
        "move: Westfen Leasing (LEASE_PROVIDER_ALIASES): lease_or_equipment_financing -> lease_or_rental, 0 of "
        "today's aliases lost; why: none needed (spec section 4.1)",
    ]
    assert paths["registry"].read_bytes() == _registry_source().encode("utf-8")
    assert not paths["evidence"].exists()


def test_move_lines_and_the_evidence_ledger_never_quote_a_run_of_five_or_more_digits(paths, monkeypatch, capsys):
    baseline = {**BASELINE, "CONFIRMED_LENDER_ALIASES": {
        **BASELINE["CONFIRMED_LENDER_ALIASES"], "Oldco 7777777 Holdings": ("OLDCO HOLDINGS", "OLDCO FUNDING")}}
    monkeypatch.setattr(lender_ledger, "current_rules", lambda: dataclasses.replace(RULES, baseline=baseline))
    paths["ledger"].write_text(json.dumps(ledger((1, "notes", "Move: fabricated merger of two funders."))),
                               encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 0
    moves = [line for line in capsys.readouterr().out.splitlines() if line.startswith("move: ")]
    assert ("move: Oldco (withheld: a run of digits) Holdings (CONFIRMED_LENDER_ALIASES): confirmed_lender -> "
            "confirmed_lender, 1 of today's aliases lost; why: fabricated merger of two funders.") in moves
    section = paths["evidence"].read_text(encoding="utf-8").split("## Moves from the registry", 1)[1]
    assert "| Oldco (withheld: a run of digits) Holdings | confirmed_lender | confirmed_lender | 1 |" in section
    assert not re.search(r"\d{5}", "\n".join(moves) + section)


def test_check_prints_every_problem_and_exits_1(paths, capsys):
    paths["ledger"].write_text(json.dumps(ledger((0, "evidence", []))), encoding="utf-8")
    assert builder.main(_args(paths, "--check")) == 1
    assert capsys.readouterr().out.splitlines() == [
        "problem: entity 0 ('Quillon Funding') is admitted without evidence",
        "refused: 1 problem(s); nothing was written",
    ]


def test_write_renders_the_block_and_the_evidence_ledger_the_same_way_twice(paths):
    assert builder.main(_args(paths, "--write")) == 0
    first = (paths["registry"].read_bytes(), paths["evidence"].read_bytes())
    assert builder.main(_args(paths, "--write")) == 0
    assert (paths["registry"].read_bytes(), paths["evidence"].read_bytes()) == first
    registry_text = first[0].decode("utf-8")
    assert "\n" not in registry_text.replace("\r\n", "") and "OLD = 1" not in registry_text
    assert registry_text.startswith('"""Fabricated registry."""\r\nHEAD = 1\r\n')
    assert registry_text.endswith("KEEP = 2\r\n")
    namespace: dict = {}
    exec(compile(registry_text, "registry.py", "exec"), namespace)
    entities, _problems = lender_ledger.parse_ledger(ledger())
    assert {name: namespace[name] for name in TABLE_NAMES} == builder.render_tables(entities)
    expected = builder.render_evidence(entities, lender_ledger.ledger_digest(ledger()), RULES)
    assert first[1].decode("utf-8") == expected


def test_write_refuses_a_ledger_with_problems_and_writes_nothing(paths):
    paths["ledger"].write_text(json.dumps(ledger((0, "aliases", ["QUILLON#FUND"]))), encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 1
    assert paths["registry"].read_bytes() == _registry_source().encode("utf-8")
    assert not paths["evidence"].exists()


def test_a_missing_or_unreadable_ledger_is_refused(paths, tmp_path):
    args = _args(paths, "--check")
    args[args.index("--ledger") + 1] = str(tmp_path / "absent.json")
    assert builder.main(args) == 2
    paths["ledger"].write_text("{not json", encoding="utf-8")
    assert builder.main(_args(paths, "--write")) == 2
    assert not paths["evidence"].exists()


def test_privacy_review_prints_the_lines_a_person_reads(paths, capsys):
    assert builder.main(_args(paths, "--privacy-review")) == 0
    entities, _problems = lender_ledger.parse_ledger(ledger())
    assert capsys.readouterr().out.splitlines() == lender_ledger.privacy_review(entities)


def test_the_rules_come_from_the_hand_kept_constants_of_the_registry():
    from analysis import classification_registry as registry

    rules = lender_ledger.current_rules()
    assert rules.owner_named is registry.OWNER_NAMED_PAYEES
    assert {"SQUARE", "SHOPIFY", "PAYPAL", "STRIPE", "INTUIT", "AMAZON"} <= rules.platforms
    assert {"CAPITAL ONE", "TOYOTA", "FORD", "APPLE"} <= rules.brands
    assert rules.hand_kept["INSURANCE_PROVIDER_ALIASES"] is registry.INSURANCE_PROVIDER_ALIASES
    assert rules.hand_kept["OPERATING_REVENUE_SOURCE_ALIASES"] is registry.OPERATING_REVENUE_SOURCE_ALIASES
    assert list(rules.baseline) == list(lender_ledger.BASELINE_TABLES)


def test_the_owner_named_payees_cover_every_group_spec_section_2_names():
    from analysis import classification_registry as registry

    assert set(registry.OWNER_NAMED_PAYEES) == {
        "confirmed_lender", "alternative_position", "line_of_credit", "credit_card_payment", "vehicle_financing",
        "bank_name", "lease_or_rental", "floor_plan_financing", "factoring", "premium_financing",
    }
    labels = {label for pairs in registry.OWNER_NAMED_PAYEES.values() for label, _spelling in pairs}
    assert {"OnDeck", "Bitty", "Legend", "LG Funding", "Hunter Caroline", "CAN Capital", "CanaCap"} <= labels
    for pairs in registry.OWNER_NAMED_PAYEES.values():
        for _label, spelling in pairs:
            assert spelling == spelling.upper() and spelling.replace(" ", "").isalnum(), spelling

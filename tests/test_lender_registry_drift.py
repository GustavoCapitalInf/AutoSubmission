"""Contract C10: the committed registry block and evidence ledger are the rendering of the committed ledger."""
from __future__ import annotations

from analysis import classification_registry as registry
from tools import build_lender_registry as builder
from tools import lender_ledger


def _committed():
    """The committed ledger, or the empty ledger until the orchestrator commits it (S1 plan, Task 9)."""
    if lender_ledger.LEDGER_PATH.exists():
        data = lender_ledger.read_ledger(lender_ledger.LEDGER_PATH)
    else:
        data = lender_ledger.EMPTY_LEDGER
    entities, problems = lender_ledger.parse_ledger(data)
    assert problems == []
    return data, entities


def test_the_generated_block_is_the_rendering_of_the_committed_ledger():
    _data, entities = _committed()
    source = builder.REGISTRY_PATH.read_text(encoding="utf-8")
    assert builder.current_block(source) == builder.registry_block(entities)
    # Audit B6 (I10): the block ends with the factoring review entities.
    assert builder.registry_block(entities) == builder.render_block(
        builder.render_tables(entities), lender_ledger.review_flag_entities(entities),
        lender_ledger.factoring_review_entities(entities))


def test_the_registry_module_holds_exactly_the_rendered_tables():
    _data, entities = _committed()
    tables = builder.render_tables(entities)
    for _group, table, _heading in lender_ledger.TABLES:
        assert getattr(registry, table) == tables[table], table


def test_the_evidence_ledger_is_the_rendering_of_the_committed_ledger():
    if not lender_ledger.LEDGER_PATH.exists():
        assert not builder.EVIDENCE_PATH.exists()
        return
    data, entities = _committed()
    expected = builder.render_evidence(entities, lender_ledger.ledger_digest(data), lender_ledger.current_rules())
    assert builder.EVIDENCE_PATH.read_text(encoding="utf-8") == expected

"""Task S1.5 (true revenue spec §7.1, §7.3, §8.7): the ledger admissions of the processors' advance products, Parafin,
Pipe's cut and the dealer-funding lenders, as the VERIFIED research carries them. Fabricated rows only; the names are
the registry's business names."""
from __future__ import annotations

import json
from pathlib import Path

from analysis.classification_registry import (
    DEALER_FUNDING_PAYERS,
    OPERATING_REVENUE_SOURCE_ALIASES,
    OPERATING_REVENUE_SOURCE_TYPES,
    PROCESSOR_ADVANCE_PRODUCTS,
    PROCESSORS_WITHOUT_ADVANCE_PRODUCT,
)
from analysis.payee_matcher import match_known_payee
from analysis.transaction_classifier import classify_transaction

LEDGER = json.loads((Path(__file__).resolve().parents[1] / "docs/lender-registry-ledger.json").read_text(
    encoding="utf-8"))
ADMITTED = {entity["entity"]: entity for entity in LEDGER["entities"] if entity["status"] == "admitted"}


def test_a_processor_s_bare_name_is_read_exactly_when_the_ledger_cleared_it():
    read = {alias for aliases in OPERATING_REVENUE_SOURCE_ALIASES.values() for alias in aliases}
    for processor, (bare, product) in PROCESSOR_ADVANCE_PRODUCTS.items():
        cleared = (product is not None and product in ADMITTED) or processor in PROCESSORS_WITHOUT_ADVANCE_PRODUCT
        assert (set(bare) <= read) is cleared, processor
        if cleared:
            assert any(processor == entity for entity in OPERATING_REVENUE_SOURCE_TYPES), processor


def test_an_admitted_advance_product_is_financing_never_a_settlement():
    for processor, (_bare, product) in PROCESSOR_ADVANCE_PRODUCTS.items():
        if product is None:
            continue
        assert ADMITTED[product]["group"] == "alternative_position", product
        alias = ADMITTED[product]["aliases"][0]
        record = classify_transaction(f"{alias} DES:ADVANCE ID:1", 5000.0, direction="credit")
        assert record.revenue_classification == "non_revenue", (processor, record.revenue_match_method)


def test_parafin_and_pipe_s_cut_read_as_financing_once_admitted():
    if "Parafin, Inc." in ADMITTED:  # the research round's entity name (ledger55.json)
        record = classify_transaction("PARAFIN DES:ADVANCE ID:1", 5000.0, direction="credit")
        assert record.revenue_classification == "non_revenue"
    pipe = ADMITTED.get("Pipe Technologies Inc")
    if pipe is not None and "PIPE TECHNOLOGIE" in pipe["aliases"]:
        found = match_known_payee("PIPE TECHNOLOGIE DES:ADVANCE ID:1")
        assert found is not None and found.entity == "Pipe Technologies Inc"


def test_every_dealer_funding_lender_the_ledger_reads_is_vehicle_financing():
    for lender, aliases in DEALER_FUNDING_PAYERS.items():
        for alias in aliases:
            found = match_known_payee(alias)
            assert found is None or found.state == "vehicle_financing", (lender, alias, found)

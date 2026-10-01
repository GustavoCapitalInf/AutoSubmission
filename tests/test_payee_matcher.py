"""Contract C3: the compiled known-payee matcher (spec section 4.6). Fabricated descriptors only."""
from __future__ import annotations

import pytest

from analysis import classification_registry as registry
from analysis import transaction_classifier
from analysis.description_text import normalize_transaction_description as normalize
from analysis.payee_matcher import (
    RUN_TOGETHER_MIN_LENGTH,
    AliasIndex,
    PayeeMatch,
    match_known_payee,
    registry_match,
)
from tools.bench_classifier import legacy_registry_match

FABRICATED = {
    "alternative_position": {"Quillon Card Loans": ("QUILLON CARD BUSINESS LOAN",)},
    "credit_card_payment": {"Quillon Card": ("QUILLON CARD",)},
    "confirmed_lender": {
        "Brambleway Funding": ("BRAMBLEWAY FUNDING", "BRAMBLEWAY"),
        "Tarnmoor Capital": ("TARNMOOR CAPITAL", "TARN MOOR"),
    },
}

TEXTS = (
    "ACH DEBIT BRAMBLEWAY FUNDING LLC",
    "CHECKCARD 0102 TARNMOORCAPITAL",
    "BRAMBLEWAYS BAKERY",
    "WEB PMT QUILLON CARD BUSINESS LOAN",
    "QUILLON CARD EPAYMENT",
    "xBRAMBLEWAYy",
    "BRAMBLEWAY-FUNDING",
    "",
    "PAYMENT TO TARN MOOR",
)


def test_normalization_moved_but_keeps_its_old_import_path():
    assert transaction_classifier.normalize_transaction_description is normalize


def test_longest_alias_wins_across_registries():
    index = AliasIndex(FABRICATED)
    assert index.match(normalize("WEB PMT QUILLON CARD BUSINESS LOAN")) == PayeeMatch(
        "Quillon Card Loans", "alternative_position", "QUILLON CARD BUSINESS LOAN"
    )
    assert index.match(normalize("QUILLON CARD EPAYMENT")) == PayeeMatch(
        "Quillon Card", "credit_card_payment", "QUILLON CARD"
    )


def test_ties_go_to_the_earlier_registry_then_the_earlier_alias():
    index = AliasIndex({
        "confirmed_lender": {"First": ("OXBOW FUND",)},
        "alternative_position": {"Second": ("OXBOW LEND",)},
    })
    assert index.match("OXBOW FUND OXBOW LEND").entity == "First"
    same_registry = AliasIndex({"confirmed_lender": {"A": ("OXBOW FUND",), "B": ("OXBOW LEND",)}})
    assert same_registry.match("OXBOW LEND OXBOW FUND").entity == "A"


def test_aliases_match_on_token_boundaries_only():
    index = AliasIndex(FABRICATED)
    assert index.match(normalize("BRAMBLEWAYS BAKERY")) is None
    assert index.match("xBRAMBLEWAYy").entity == "Brambleway Funding"
    assert index.match("BRAMBLEWAY-FUNDING").alias == "BRAMBLEWAY"


def test_a_spaced_alias_also_matches_its_run_together_form_of_eight_characters_or_more():
    index = AliasIndex(FABRICATED)
    assert RUN_TOGETHER_MIN_LENGTH == 8
    assert index.match(normalize("CHECKCARD 0102 TARNMOORCAPITAL")) == PayeeMatch(
        "Tarnmoor Capital", "confirmed_lender", "TARNMOOR CAPITAL"
    )
    assert index.match(normalize("PAYMENT TO TARNMOOR")) == PayeeMatch(
        "Tarnmoor Capital", "confirmed_lender", "TARN MOOR"
    )
    seven = AliasIndex({"confirmed_lender": {"Oxbow Lend": ("OXBOW LE",)}})  # "OXBOWLE" has 7 characters
    assert seven.match("OXBOWLE") is None


def test_an_explicit_alias_beats_another_entitys_run_together_form():
    index = AliasIndex({
        "confirmed_lender": {"Joined": ("NORTH WINDFUND",)},
        "alternative_position": {"Explicit": ("NORTHWINDFUND",)},
    })
    assert index.match("NORTHWINDFUND").entity == "Explicit"


def test_registry_match_has_no_run_together_forms():
    table = {"Tarnmoor Capital": ("TARNMOOR CAPITAL",)}
    assert registry_match("TARNMOORCAPITAL", table) is None
    assert registry_match("ACH TARNMOOR CAPITAL", table) == ("Tarnmoor Capital", "TARNMOOR CAPITAL")


def test_registry_match_on_an_empty_registry_is_none():
    assert registry_match("ANYTHING", {}) is None


def test_registry_match_never_serves_one_registrys_index_for_another():
    first = {"Brambleway Funding": ("BRAMBLEWAY",)}
    assert registry_match("BRAMBLEWAY", first) == ("Brambleway Funding", "BRAMBLEWAY")
    del first
    second = {"Tarnmoor Capital": ("TARNMOOR",)}
    assert registry_match("BRAMBLEWAY", second) is None
    assert registry_match("TARNMOOR", second) == ("Tarnmoor Capital", "TARNMOOR")


LIVE_REGISTRIES = (
    "INSURANCE_PROVIDER_ALIASES",
    "OPERATING_REVENUE_SOURCE_ALIASES",
    "LEGACY_CONFIRMED_LENDER_ALIASES",
    "LEGACY_POTENTIAL_LENDER_ALIASES",
    "LEASE_PROVIDER_ALIASES",
)


@pytest.mark.parametrize("name", LIVE_REGISTRIES)
def test_registry_match_agrees_with_the_legacy_matcher_on_every_alias_of_the_live_registries(name):
    table = getattr(registry, name, None)
    if table is None:
        pytest.skip(f"{name} no longer exists")
    texts = [*TEXTS]
    for aliases in table.values():
        for alias in aliases:
            texts.append(f"ACH DEBIT {alias} PMT 0102")
            texts.append(normalize(f"POS {alias}X"))
            texts.append(normalize(f"{alias}-{alias}"))
    for text in texts:
        assert registry_match(text, table) == legacy_registry_match(text, table), text


def test_match_known_payee_is_the_index_over_payee_group_registries():
    # Audit B6: the debit (default) index leaves out the credit-only aliases; the credit index reads every alias.
    index = AliasIndex(registry.PAYEE_GROUP_REGISTRIES, excluded=registry.CREDIT_ONLY_ALIASES)
    credit_index = AliasIndex(registry.PAYEE_GROUP_REGISTRIES)
    texts = [normalize(f"ACH DEBIT {alias}") for table in registry.PAYEE_GROUP_REGISTRIES.values()
             for aliases in table.values() for alias in aliases]
    for text in [*texts, *TEXTS]:
        assert match_known_payee(text) == index.match(text)
        assert match_known_payee(text, credit=True) == credit_index.match(text)


# --- 5.3 (owner ruling 2026-09-27): digits glued to the last word of a multi-word alias --------------------------

GLUED = {
    "confirmed_lender": {"Quillon Advance": ("QUILLON ADVANCE",), "Brisk": ("BRISK",)},
    "mortgage": {"Tarnmoor Fund": ("TARNMOOR IN FD",)},
}


@pytest.mark.parametrize(
    ("text", "entity"),
    [
        ("ACH DEBIT QUILLON ADVANCE1234 ACHDEBIT", "Quillon Advance"),
        ("QUILLON ADVANCE1234", "Quillon Advance"),
        ("QUILLON ADVANCE 1234", "Quillon Advance"),
        # a single-word alias stays strict, and so does a last word of fewer than three letters
        ("BRISK1234 PAYMENT", None),
        ("TARNMOOR IN FD1234", None),
        # the digits must be glued to the whole last word, and a longer word is another word
        ("QUILLON ADV1234", None),
        ("QUILLON ADVANCES1234", None),
    ],
)
def test_the_known_payee_index_reads_digits_glued_to_the_last_word_of_a_multi_word_alias(text, entity):
    found = AliasIndex(GLUED, glued_digits=True).match(normalize(text))
    assert (found.entity if found else None) == entity


def test_only_the_known_payee_index_reads_glued_digits():
    assert AliasIndex(GLUED).match("QUILLON ADVANCE1234") is None
    assert registry_match("QUILLON ADVANCE1234", GLUED["confirmed_lender"]) is None


def test_the_live_known_payee_index_reads_goat_advances_glued_debits():
    found = match_known_payee(normalize("GOAT ADVANCE1234 DES:ACHDEBIT ID:0001 INDN:FAB HOLDER CO ID:0002 CCD"))
    assert found is not None and (found.entity, found.state) == ("GOAT ADVANCE LLC", "confirmed_lender")

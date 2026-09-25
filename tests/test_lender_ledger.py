"""Contract C10: the curated ledger's schema and every rule of its validator, on fabricated ledgers."""
from __future__ import annotations

import dataclasses

import pytest

from tests.lender_ledger_fixture import BASELINE, ENTITIES, HAND_KEPT, RULES, UNRESOLVED, entity, ledger
from tools import lender_ledger


def _problems(*changes, rules=RULES):
    return lender_ledger.validate(ledger(*changes), rules)


def _entities(*changes):
    entities, problems = lender_ledger.parse_ledger(ledger(*changes))
    assert problems == []
    return entities


# --- the schema ------------------------------------------------------------------------------------------------


def test_the_fabricated_ledger_passes_every_rule():
    assert _problems() == []
    assert len(_entities()) == len(ENTITIES)


@pytest.mark.parametrize("data,problem", [
    ([], "the ledger is not an object with exactly the keys 'schema' and 'entities'"),
    ({"schema": 1, "entities": [], "extra": 1}, "the ledger is not an object with exactly the keys 'schema' and "
                                                "'entities'"),
    ({"schema": 2, "entities": []}, "the ledger schema is 2; this validator reads schema 1"),
    ({"schema": 1, "entities": {}}, "the ledger's 'entities' is not a list"),
])
def test_the_ledger_is_schema_1_with_a_list_of_entities(data, problem):
    assert lender_ledger.validate(data, RULES) == [problem]


def test_every_entity_has_exactly_the_c10_fields():
    data = ledger()
    del data["entities"][0]["notes"]
    data["entities"][0]["alias"] = "QUILLON"
    data["entities"][1] = "Oldco Funding"
    assert lender_ledger.validate(data, RULES) == [
        "entity 0: missing field(s) notes",
        "entity 0: unknown field(s) alias",
        "entity 1 is not an object",
    ]


@pytest.mark.parametrize("field_name,value,problem", [
    ("entity", "", "entity is not a non-empty string"),
    ("group", "insurance", "group 'insurance' is not a C10 group"),
    ("business_type", " ", "business_type is not a non-empty string"),
    ("aliases", "QUILLON FUNDING", "aliases is not a list of strings"),
    ("status", "maybe", "status 'maybe' is not one of admitted, review, owner_ruling, rejected"),
    ("short_alias_reason", "", "short_alias_reason is neither null nor a non-empty string"),
    ("evidence", {"source": "https://quillon.example/"}, "evidence is not a list"),
    ("evidence", [{"source": "https://quillon.example/"}],
     "evidence 0 is not an object of the strings 'source' and 'note'"),
    ("verdicts", [{"round": "r1", "verdict": "upheld", "confirmed": "yes"}],
     "verdict 0 is not an object of the strings 'round' and 'verdict' and a true/false 'confirmed'"),
    ("where_looked", "https://quillon.example/", "where_looked is not a list of strings"),
    ("notes", None, "notes is not a string"),
])
def test_every_field_has_its_c10_type(field_name, value, problem):
    assert _problems((0, field_name, value)) == [f"entity 0: {problem}"]


# --- C10: admission ---------------------------------------------------------------------------------------------


def test_an_admitted_entity_needs_evidence():
    assert _problems((0, "evidence", [])) == ["entity 0 ('Quillon Funding') is admitted without evidence"]


@pytest.mark.parametrize("verdicts", [
    [],
    [{"round": "r1", "verdict": "unresolved", "confirmed": True}],
    [{"round": "r1", "verdict": "upheld", "confirmed": False}],
])
def test_an_admitted_entity_needs_an_upheld_or_corrected_verdict_that_confirms_it(verdicts):
    assert _problems((0, "verdicts", verdicts)) == [
        "entity 0 ('Quillon Funding') is admitted without an upheld or corrected verdict that confirms it"
    ]


def test_a_corrected_verdict_admits_and_other_statuses_need_no_verdict():
    assert _problems((0, "verdicts", [{"round": "r2", "verdict": "corrected", "confirmed": True}])) == []
    assert _problems((17, "evidence", []), (17, "verdicts", [])) == []


def test_an_admitted_or_review_entity_needs_an_alias():
    assert _problems((15, "aliases", [])) == ["entity 15 ('Heldco Advance') is review but has no alias",
                                              "today's POTENTIAL_LENDER_ALIASES entity 'Heldco Advance' is in no "
                                              "ledger entity: record it in its place, or moved or rejected with a "
                                              "sentence starting 'Move:' in its notes"]
    assert _problems((16, "aliases", [])) == []


@pytest.mark.parametrize("group", ["credit_card_payment", "card_issuer_context", "bank_name", "premium_financing"])
def test_an_entity_of_a_table_read_only_with_context_is_never_under_review(group):
    data = ledger()
    data["entities"].append(entity("Zephyrton Card Services", group, ["ZEPHYRTON CARD PMT"], status="review",
                                   business_type="fabricated_context_payee", evidence=[], verdicts=UNRESOLVED,
                                   notes="Fabricated: identity unconfirmed."))
    assert lender_ledger.validate(data, RULES) == [
        f"entity 18 ('Zephyrton Card Services') is review in {group}, a table the classifier reads only with "
        "context, but the potential tier reads its aliases without that context: admit it, or record it as "
        "owner_ruling or rejected"
    ]


# --- C10: the alias rules --------------------------------------------------------------------------------------


@pytest.mark.parametrize("alias,problem", [
    ("QUILLON#FUND", "alias 'QUILLON#FUND' is masked ('#')"),
    ("Quillon Fund", "alias 'Quillon Fund' has lowercase letters"),
    ("QUILLON-FUND", "alias 'QUILLON-FUND' has characters outside A-Z, 0-9, space and '&'"),
    ("QUILLON  FUND", "alias 'QUILLON  FUND' has extra spaces"),
    ("", "an alias is empty"),
])
def test_an_alias_is_upper_case_letters_digits_spaces_and_ampersands(alias, problem):
    assert _problems((0, "aliases", ["QUILLON FUNDING", alias])) == [f"entity 0 ('Quillon Funding'): {problem}"]


def test_the_character_rules_hold_for_every_status_and_an_ampersand_is_allowed():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QUILLON & SONS"])) == []
    assert _problems((17, "aliases", ["TARNMOOR#CAP"])) == [
        "entity 17 ('Tarnmoor Capital'): alias 'TARNMOOR#CAP' is masked ('#')"
    ]


@pytest.mark.parametrize("alias", ["CAPITAL", "FUNDING LLC", "EQUIPMENT FINANCE", "LOAN PAYMENT"])
def test_an_alias_of_generic_words_only_is_refused(alias):
    assert _problems((0, "aliases", ["QUILLON FUNDING", alias])) == [
        f"entity 0 ('Quillon Funding'): alias {alias!r} is only generic words"
    ]


def test_an_entity_in_no_table_may_keep_a_generic_alias_as_evidence():
    assert _problems((17, "aliases", ["TARNMOOR CAP", "CAPITAL FUNDING"])) == []


def test_a_bare_platform_name_or_a_hand_kept_alias_is_refused_and_a_financing_alias_is_not():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "VELLUM"])) == [
        "entity 0 ('Quillon Funding'): alias 'VELLUM' is a bare platform name (spec section 5: the "
        "operating-revenue registry only)"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "ZANTHOS PAY"])) == [
        "entity 0 ('Quillon Funding'): alias 'ZANTHOS PAY' is also an alias of the hand-kept "
        "OPERATING_REVENUE_SOURCE_ALIASES entity 'Zanthos Pay'"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "ZANTHOS CAPITAL"])) == []


def test_a_bare_brand_name_is_an_alias_only_of_the_context_or_bank_tables():
    assert _problems((6, "aliases", ["RIVETT MOTOR CREDIT", "RIVETT"])) == [
        "entity 6 ('Rivett Motor Credit'): alias 'RIVETT' is a bare brand name; it belongs in "
        "card_issuer_context or bank_name (spec section 5)"
    ]
    data = ledger()
    data["entities"].append(entity("Rivett", "card_issuer_context", ["RIVETT"]))
    assert lender_ledger.validate(data, RULES) == []


def test_a_card_payment_alias_carries_card_or_payment_wording():
    assert _problems((4, "aliases", ["OXBOW CARD PMT", "OXBOW MUTUAL"])) == [
        "entity 4 ('Oxbow Card'): alias 'OXBOW MUTUAL' has no card or payment wording; a bare issuer name "
        "belongs in card_issuer_context (contract C10)"
    ]
    assert _problems((4, "aliases", ["OXBOW CARD PMT", "OXBOW AUTO PAY", "OXBOW CRD EPAY"])) == []


def test_an_alias_of_four_characters_or_fewer_needs_a_reason():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QFND"])) == [
        "entity 0 ('Quillon Funding'): alias 'QFND' has 4 characters or fewer and no short_alias_reason"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QFND"]),
                     (0, "short_alias_reason", "Fabricated: the funder's own initialism.")) == []


@pytest.mark.parametrize("index,aliases,problem", [
    (3, ["BRAMBLEWAY CAPITAL", "QUILLON FUNDING"],
     "alias 'QUILLON FUNDING' appears under entity 0 ('Quillon Funding') and entity 3 ('Brambleway Capital')"),
    (17, ["TARNMOOR CAP", "QUILLON FUNDING"],
     "alias 'QUILLON FUNDING' appears under entity 0 ('Quillon Funding') and entity 17 ('Tarnmoor Capital')"),
])
def test_one_alias_belongs_to_one_entity_whatever_its_status(index, aliases, problem):
    assert _problems((index, "aliases", aliases)) == [problem]


def test_spellings_that_normalize_alike_are_one_alias():
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QUILLON & SONS"]),
                     (3, "aliases", ["BRAMBLEWAY CAPITAL", "QUILLON AND SONS"])) == [
        "alias 'QUILLON AND SONS' appears under entity 0 ('Quillon Funding') and entity 3 ('Brambleway Capital')"
    ]


def test_a_run_together_form_of_a_known_payee_alias_belongs_to_that_payee_only():
    assert _problems((3, "aliases", ["BRAMBLEWAY CAPITAL", "QUILLONFUNDING"])) == [
        "run-together form 'QUILLONFUNDING' of entity 0 ('Quillon Funding') is also claimed by entity 3 "
        "('Brambleway Capital')"
    ]


def test_an_entity_name_is_used_once_and_never_the_name_of_a_hand_kept_entity():
    data = ledger()
    data["entities"].append(entity("Quillon Funding", "confirmed_lender", ["QUILLON CAPITAL"], status="rejected"))
    assert lender_ledger.validate(data, RULES) == [
        "entity name 'Quillon Funding' appears more than once (entities 0 and 18)"
    ]
    assert _problems((13, "entity", "Brisk Mutual")) == [
        "entity 13 ('Brisk Mutual') has the name of an entity of the hand-kept INSURANCE_PROVIDER_ALIASES"
    ]


def test_a_premium_alias_never_repeats_a_hand_kept_insurer_alias():
    assert _problems((13, "aliases", ["BRISK MUTUAL FUNDING", "BRISK MUTUAL"])) == [
        "entity 13 ('Brisk Mutual Funding'): alias 'BRISK MUTUAL' is also an alias of the hand-kept "
        "INSURANCE_PROVIDER_ALIASES entity 'Brisk Mutual'"
    ]


def test_a_premium_alias_that_contains_an_insurer_alias_is_listed_for_the_owner_not_refused():
    assert lender_ledger.premium_insurer_overlaps(_entities(), HAND_KEPT["INSURANCE_PROVIDER_ALIASES"]) == [
        ("Brisk Mutual Funding", "Brisk Mutual")
    ]


# --- C10: the payees the owner named ----------------------------------------------------------------------------


@pytest.mark.parametrize("changes,problem", [
    ([(0, "status", "review")],
     "owner-named Quillon is not admitted in confirmed_lender: 'QUILLON FUNDING' matches nothing"),
    ([(2, "group", "confirmed_lender"), (2, "business_type", "mca_or_revenue_based_funder")],
     "owner-named Ruledco is not admitted in alternative_position: 'RULEDCO CAPITAL' matches 'Ruledco' "
     "(confirmed_lender)"),
    ([(3, "status", "owner_ruling")],
     "owner-named Brambleway is not admitted in line_of_credit: 'BRAMBLEWAY CAPITAL' matches nothing"),
    ([(4, "group", "lease_or_rental")],
     "owner-named Oxbow is not admitted in credit_card_payment: 'OXBOW CARD PMT' matches 'Oxbow Card' "
     "(lease_or_rental)"),
    ([(12, "group", "factoring")],
     "owner-named Hollin is not admitted in premium_financing: 'HOLLIN PREMIUM FIN' matches "
     "'Hollin Premium Finance' (factoring)"),
    ([(14, "status", "rejected")],
     "owner-named Brambleway Bank is not admitted in bank_name: 'BRAMBLEWAY BANK LN PYMT' matches nothing"),
])
def test_every_payee_the_owner_named_is_admitted_in_its_group(changes, problem):
    assert _problems(*changes) == [problem]


def test_a_card_issuer_the_owner_named_may_be_a_bare_issuer_name_of_the_context_table():
    rules = dataclasses.replace(RULES, owner_named={"credit_card_payment": (("Oxbow", "OXBOW EPAYMENT"),)})
    assert _problems(rules=rules) == []


# --- privacy -----------------------------------------------------------------------------------------------------


def test_a_run_of_five_or_more_digits_is_refused_outside_urls():
    assert _problems((0, "notes", "fabricated reference 5551234")) == [
        "entity 0 ('Quillon Funding'): the notes field carries a run of five or more digits"
    ]
    assert _problems((0, "aliases", ["QUILLON FUNDING", "QUILLON 45219"])) == [
        "entity 0 ('Quillon Funding'): an alias carries a run of five or more digits that today's registry does "
        "not hold"
    ]
    assert _problems((16, "entity", "7777777 ONTARIO INC")) == [
        "entity 16: the entity field carries a run of five or more digits"
    ]
    assert _problems((0, "evidence", [{"source": "https://registry.example/company/12345678", "note": "x"}])) == []


def test_a_digit_run_is_allowed_in_an_alias_todays_registry_already_holds():
    baseline = {**BASELINE, "CONFIRMED_LENDER_ALIASES": {
        **BASELINE["CONFIRMED_LENDER_ALIASES"], "Oldco Funding": ("OLDCO FUNDING", "OLDCO", "OLDCO 4444444")}}
    rules = dataclasses.replace(RULES, baseline=baseline)
    assert _problems((1, "aliases", ["OLDCO FUNDING", "OLDCO", "OLDCO 4444444"]), rules=rules) == []


def test_sources_and_where_looked_are_public_urls_without_a_query_string():
    assert _problems((0, "where_looked", ["https://search.example/?q=QUILLON"]),
                     (0, "evidence", [{"source": "descriptor: fabricated", "note": "x"}])) == [
        "entity 0 ('Quillon Funding'): evidence 0 source is not a public URL without a query string",
        "entity 0 ('Quillon Funding'): where_looked 0 is not a public URL without a query string",
    ]


def test_the_privacy_review_lists_every_name_without_an_organisation_word_and_every_foreign_alias():
    assert lender_ledger.privacy_review(_entities()) == [
        "alias shares no word with its name: Quillon Funding | QUILLONFUND",
        "no organisation word in the name: Ruledco (admitted)",
        "no organisation word in the name: Oxbow Card (admitted)",
        "no organisation word in the name: Oxbow (admitted)",
        "no organisation word in the name: Marsh Recovery (owner_ruling)",
    ]


# --- spec section 9: today's registry -------------------------------------------------------------------------


def test_every_entity_of_todays_registry_is_in_the_ledger():
    data = ledger()
    del data["entities"][1]
    problems = lender_ledger.validate(data, RULES)
    assert problems == ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' is in no ledger entity: record it "
                        "in its place, or moved or rejected with a sentence starting 'Move:' in its notes"]


def test_an_entity_of_todays_registry_keeps_its_name():
    assert _problems((1, "entity", "Oldco Funding LLC")) == [
        "the ledger entity holding the first alias of today's 'Oldco Funding' is named 'Oldco Funding LLC': keep "
        "today's name (S2's pins and the census compare entity names)"
    ]


@pytest.mark.parametrize("changes,problems", [
    ([(1, "group", "line_of_credit"), (1, "business_type", "business_loc_provider")],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' moves from confirmed_lender to line_of_credit "
      "without a sentence starting 'Move:' in its notes"]),
    ([(1, "group", "line_of_credit"), (1, "business_type", "business_loc_provider"),
      (1, "notes", "Fabricated: the company site describes small-business funding.")],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' moves from confirmed_lender to line_of_credit "
      "without a sentence starting 'Move:' in its notes"]),
    ([(1, "aliases", ["OLDCO FUNDING"])],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' loses 1 of today's aliases without a sentence "
      "starting 'Move:' in its notes"]),
    ([(1, "status", "rejected")],
     ["today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' moves from confirmed_lender to no table without "
      "a sentence starting 'Move:' in its notes",
      "today's CONFIRMED_LENDER_ALIASES entity 'Oldco Funding' loses 2 of today's aliases without a sentence "
      "starting 'Move:' in its notes"]),
    ([(8, "group", "personal_loan")],
     ["today's LEASE_PROVIDER_ALIASES entity 'Westfen Leasing' moves from lease_or_equipment_financing to "
      "personal_loan without a sentence starting 'Move:' in its notes"]),
    ([(8, "group", "confirmed_lender")], []),
    ([(1, "status", "rejected"), (1, "notes", "Fabricated: a funder. Move: the owner ruled it out.")], []),
])
def test_a_move_or_a_lost_alias_of_todays_registry_needs_a_move_sentence(changes, problems):
    assert _problems(*changes) == problems


@pytest.mark.parametrize("notes,reason", [
    ("Move: the owner ruled it out.", "the owner ruled it out."),
    ("Fabricated: a funder. Move: the owner ruled it out.", "the owner ruled it out."),
    ("Fabricated: a funder; Move:  renamed by the owner.", "renamed by the owner."),
    ("Fabricated: see the Move: column.", ""),
    ("Move:", ""),
    ("", ""),
])
def test_only_a_sentence_that_starts_with_the_move_marker_is_a_reason(notes, reason):
    assert lender_ledger.move_reason(notes) == reason


def test_baseline_moves_list_every_changed_entity_with_its_reason():
    moves, missing = lender_ledger.baseline_moves(_entities(), BASELINE)
    assert missing == []
    assert moves == [
        lender_ledger.Move("Ruledco", "CONFIRMED_LENDER_ALIASES", "confirmed_lender", "alternative_position", 0,
                           "Ruledco", "fabricated owner ruling, an alternative position."),
        lender_ledger.Move("Westfen Leasing", "LEASE_PROVIDER_ALIASES", "lease_or_equipment_financing",
                           "lease_or_rental", 0, "Westfen Leasing", ""),
    ]


def test_the_baseline_is_read_from_a_registry_source_without_importing_it():
    source = "".join(f"{table}: dict[str, tuple[str, ...]] = {entries!r}\n" for table, entries in BASELINE.items())
    assert lender_ledger.baseline_from_source("OTHER = 1\n" + source) == BASELINE
    with pytest.raises(ValueError, match="LEASE_PROVIDER_ALIASES"):
        lender_ledger.baseline_from_source("CONFIRMED_LENDER_ALIASES = {}\nPOTENTIAL_LENDER_ALIASES = {}\n")


def test_the_baseline_revision_holds_the_lists_the_classifier_reads_until_s2():
    from analysis import classification_registry as registry

    legacy = {
        "CONFIRMED_LENDER_ALIASES": getattr(registry, "LEGACY_CONFIRMED_LENDER_ALIASES", None),
        "POTENTIAL_LENDER_ALIASES": getattr(registry, "LEGACY_POTENTIAL_LENDER_ALIASES", None),
        "LEASE_PROVIDER_ALIASES": getattr(registry, "LEASE_PROVIDER_ALIASES", None),
    }
    baseline = lender_ledger.load_baseline()
    assert list(baseline) == list(lender_ledger.BASELINE_TABLES)
    if any(table is None for table in legacy.values()):
        pytest.skip("S2 removed the legacy lists; the baseline revision stays the validator's frozen input")
    for name, table in legacy.items():
        assert baseline[name] == table, name


def test_the_ledger_digest_ignores_formatting():
    data = ledger()
    assert lender_ledger.ledger_digest(data) == lender_ledger.ledger_digest(
        {"entities": data["entities"], "schema": 1})
    assert len(lender_ledger.ledger_digest(data)) == 64
    assert lender_ledger.ledger_digest(data) != lender_ledger.ledger_digest(ledger((0, "notes", "changed")))

"""True revenue spec §7.0 to §7.10 and §7.4 (S1): the operating registry, its sixteen-character cuts, the payout and
card forms, the payer tables and the validator that checks them."""
from __future__ import annotations

import re

import pytest

from analysis import classification_registry as registry
from tools import operating_registry


def test_the_registry_has_no_problem():
    assert operating_registry.problems() == []
    assert operating_registry.main(["--check"]) == 0


def test_every_new_type_is_one_of_the_known_source_types():
    assert set(registry.OPERATING_REVENUE_SOURCE_TYPES.values()) == {
        "known_operating_counterparty", "merchant_processor", "ecommerce_marketplace", "customer_payment_platform",
        "delivery_marketplace", "invoice_and_receivables", "ecommerce_platform", "booking_marketplace",
        "transport_marketplace", "wholesale_auto_auction", "property_management_payments",
    }


@pytest.mark.parametrize(("alias", "cut"), [
    ("FIRST DATA MERCHANT", "FIRST DATA MERCH"),
    ("QUICKBOOKS PAYMENTS", "QUICKBOOKS PAYME"),
    ("AMAZON MARKETPLACE", "AMAZON MARKETPLA"),
    ("HEARTLAND PMT SYS TXNS", None),     # the cut's last word would have two letters
    ("GODADDY PAYMENTS", None),           # sixteen characters: no cut
])
def test_the_sixteen_character_cut(alias, cut):
    assert registry._operating_alias_cut(alias) == cut


def test_a_bare_processor_name_is_not_in_the_registry_until_the_ledger_clears_it():
    read = {alias for aliases in registry.OPERATING_REVENUE_SOURCE_ALIASES.values() for alias in aliases}
    for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items():
        if product is None and processor not in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT:
            assert not set(bare) & read, processor


def test_the_validator_refuses_a_bare_alias_ahead_of_its_advance_product(monkeypatch):
    # Task S1.5 admitted Shift4 Capital, so the fixture makes Shift4 wait for its product again.
    aliases = {**registry.OPERATING_REVENUE_SOURCE_ALIASES, "Shift4": ("SHIFT4", "SHIFT4 PAYMENTS")}
    products = {**registry.PROCESSOR_ADVANCE_PRODUCTS, "Shift4": (("SHIFT4",), None)}
    monkeypatch.setattr(registry, "OPERATING_REVENUE_SOURCE_ALIASES", aliases)
    monkeypatch.setattr(registry, "PROCESSOR_ADVANCE_PRODUCTS", products)
    assert any("SHIFT4" in problem and "advance product" in problem for problem in operating_registry.problems())


def test_the_validator_refuses_an_untyped_entity_and_a_financing_collision(monkeypatch):
    aliases = {**registry.OPERATING_REVENUE_SOURCE_ALIASES, "Fabrikam Pay": ("FABRIKAM PAY",),
               "Square": (*registry.OPERATING_REVENUE_SOURCE_ALIASES["Square"], "SQUARE CAPITAL")}
    monkeypatch.setattr(registry, "OPERATING_REVENUE_SOURCE_ALIASES", aliases)
    found = operating_registry.problems()
    assert "operating entity 'Fabrikam Pay' has no source type" in found
    assert any("'SQUARE CAPITAL'" in problem and "financing alias" in problem for problem in found)


@pytest.mark.parametrize(("alias", "word"), [
    ("SQUARE", "operating alias"),                    # an operating source is no factor
    ("SQUARE CAPITAL", "alias of"),                   # nor is a lender (a ledger alias)
    ("STATE FARM", "insurer alias"),                  # nor an insurer
])
def test_the_validator_refuses_a_factoring_payer_alias_another_table_holds(monkeypatch, alias, word):
    # Final review M3: the five other 5.6 tables are checked too, the factoring aliases against the ledger, the
    # operating registry and the insurers.
    monkeypatch.setattr(registry, "FACTORING_PAYOUT_PAYERS", {"Fabrikam Factoring": (alias,)})
    assert any(f"factoring payer alias {alias!r}" in problem and word in problem
               for problem in operating_registry.problems())


@pytest.mark.parametrize("name", [
    "OWNER_MONEY_PLATFORMS", "SECTION_15_DEFERRED_PAYERS",
    # Audit B6 (I23, I49): the lending banks and the earned-wage access providers.
    "LENDING_BANK_CREDIT_PAYERS", "EARNED_WAGE_ACCESS_PAYERS",
])
def test_the_validator_refuses_an_owner_money_or_deferred_pattern_that_reads_an_operating_source(monkeypatch, name):
    monkeypatch.setattr(registry, name, r"(?<![A-Z])(?:FABRIKAM WEALTH|SQUARE)\b")
    assert any(f"{name} reads the operating alias 'SQUARE'" in problem for problem in operating_registry.problems())
    monkeypatch.setattr(registry, name, r"(?:FABRIKAM")
    assert any(f"{name} does not compile" in problem for problem in operating_registry.problems())


def test_the_customer_financing_tables_read_no_operating_insurer_or_other_ledger_alias(monkeypatch):
    """Owner ruling 2026-10-02 (Q8): the lease-to-own and patient financiers' payer spellings and their name sweep pass
    M3 as committed (each reads only its own entity's ledger aliases); a spelling or a sweep that reads an operating
    source, an insurer or another entity's ledger alias, or that does not compile, fails."""
    assert not [problem for problem in operating_registry.problems() if "CUSTOMER_FINANCING" in problem]
    payers = {**registry.CUSTOMER_FINANCING_PAYERS, "Koalafi": r"(?<![A-Z])(?:KOALAFI|STRIPE)\b"}
    monkeypatch.setattr(registry, "CUSTOMER_FINANCING_PAYERS", payers)
    assert any("CUSTOMER_FINANCING_PAYERS['Koalafi'] reads the operating alias 'STRIPE'" in problem
               for problem in operating_registry.problems())
    monkeypatch.setattr(registry, "CUSTOMER_FINANCING_PAYERS", {"Koalafi": r"(?<![A-Z])(?:KOALAFI|STATE FARM)\b"})
    assert any("reads the insurer alias 'STATE FARM'" in problem for problem in operating_registry.problems())
    monkeypatch.setattr(registry, "CUSTOMER_FINANCING_PAYERS", {"Koalafi": r"(?<![A-Z])(?:KOALAFI|SNAP FINANCE)\b"})
    assert any("reads the lease_or_rental alias 'SNAP FINANCE' of 'SNAP Finance'" in problem
               for problem in operating_registry.problems())
    monkeypatch.setattr(registry, "CUSTOMER_FINANCING_PAYERS", {"Koalafi": r"(?:KOALAFI"})
    assert any("CUSTOMER_FINANCING_PAYERS['Koalafi'] does not compile" in problem
               for problem in operating_registry.problems())
    monkeypatch.setattr(registry, "CUSTOMER_FINANCING_NAMES", r"(?<![A-Z])(?:KOALAFI|SQUARE)\b")
    assert any("CUSTOMER_FINANCING_NAMES reads the operating alias 'SQUARE'" in problem
               for problem in operating_registry.problems())


def test_the_validator_refuses_bank_names_that_are_not_normalized_or_repeat(monkeypatch):
    monkeypatch.setattr(registry, "P2P_SENDING_BANK_NAMES", ("SAMPLE BANK", "Sample Bank", "SAMPLE BANK"))
    monkeypatch.setattr(registry, "STATEMENT_BANK_PRINTED_NAMES", ((("SAMPLE BANK",), ("S.B.", "SB", "SB")),))
    found = operating_registry.problems()
    assert "sending bank name 'Sample Bank' is not normalized" in found
    assert "P2P_SENDING_BANK_NAMES lists a name twice" in found
    assert "statement bank name 'S.B.' is not normalized" in found
    assert any("names no bank word, no form, or a form twice" in problem for problem in found)


def test_the_validator_checks_the_own_bank_sending_spellings(monkeypatch):
    # Audit round 3, R3-B08 (R3-31): normalized, no spelling twice, every spelling a listed sending bank's.
    assert not [problem for problem in operating_registry.problems() if "own bank" in problem.lower()]
    monkeypatch.setattr(registry, "OWN_BANK_SENDING_SPELLINGS", (
        (("Sample Bank",), ("BOFA",)),
        (("SAMPLE BANK",), ("BOFA", "SAMPLE TRUST")),
        ((), ()),
    ))
    found = operating_registry.problems()
    assert "own bank spelling 'Sample Bank' is not normalized" in found
    assert "OWN_BANK_SENDING_SPELLINGS lists 'BOFA' twice" in found
    assert "own bank spelling 'SAMPLE TRUST' is not in P2P_SENDING_BANK_NAMES" in found
    assert "own bank entry () names no marker or no spelling" in found


def test_a_waiting_processor_s_bare_aliases_are_gated_and_never_read():
    # §7.1, review I4: the gate lists every processor the ledger has not cleared, and none of its bare aliases reads.
    admitted = {entity for group in registry.PAYEE_GROUP_REGISTRIES.values() for entity in group}
    waiting = {
        processor: bare for processor, (bare, product) in registry.PROCESSOR_ADVANCE_PRODUCTS.items()
        if not (product in admitted or processor in registry.PROCESSORS_WITHOUT_ADVANCE_PRODUCT)
    }
    assert registry.GATED_PROCESSOR_ALIASES == waiting
    read = {alias for aliases in registry.OPERATING_REVENUE_READ_ALIASES.values() for alias in aliases}
    assert not read & {alias for bare in waiting.values() for alias in bare}


def test_the_structural_lens_processors_wait_for_a_printed_spelling():
    # §7.1: none of the seventeen prints a credit spelling in the corpus or the tryout dump (Task S1.1, Step 1).
    read = {word for aliases in registry.OPERATING_REVENUE_READ_ALIASES.values() for alias in aliases
            for word in alias.split()}
    for name in ("TSYS", "TRANSFIRST", "VANTIV", "PAYSAFE", "PAYANYWHERE", "PAYROC", "CARDCONNECT", "FATTMERCHANT",
                 "STAX", "REPAY", "PAYA", "NMI", "FINIX", "WEPAY", "TDMS", "MONETICO", "QUICKACCEPT"):
        assert name not in read, name


def test_every_form_compiles_and_names_a_typed_entity():
    for entity, forms in registry.OPERATING_SOURCE_PAYOUT_FORMS.items():
        assert entity in registry.OPERATING_REVENUE_SOURCE_TYPES
        for label, pattern in forms:
            assert re.compile(pattern) and label.endswith("_form")
    labels = [form.label for form in registry.CARD_SETTLEMENT_CREDIT_FORMS]
    assert len(labels) == len(set(labels))
    for form in registry.CARD_SETTLEMENT_CREDIT_FORMS:
        assert form.entity is None or form.entity in registry.OPERATING_REVENUE_SOURCE_TYPES


#: §7.0, §7.1 (owner ruling 2026-09-29): one fabricated row for each branch of every card form, each row beginning with
#: the branch's leading token, so a prefix glued on the left lands on that token's boundary.
CARD_FORM_ROWS = [
    ("bankcard", "BANKCARD DEPOSIT"),
    ("merch_dep", "MERCH DEP"),
    ("mrchntsrvs", "DESCR MRCHNTSRVS"),
    ("merch_svcs_setl_code", "MERCH SVCS DES DAILYSETL"),
    ("merchant_services_mid", "MERCHANT SERVICES TRANS SLIP"),
    ("brand_dep", "VISA DEP 1"),
    ("brand_dep", "MISC PAYMENT VISA DEP 1"),
    ("brand_dep", "VISA DEP MERCH SVC"),
    ("dep_brand", "DEP VISA 1"),
    ("dep_brand", "COMPTE DIVERS DEP VISA 1"),
    ("dep_brand", "DEP VISA MSP"),
    ("gbl_brand", "GBL VI"),
    ("net_settle", "DESCR NET SETTLE"),
    ("batch_total", "BTOT DEP"),
    ("intuit_deposit", "INTUIT 123456 DEPOSIT"),
    ("intuit_deposit", "DEPOSIT FROM INTUIT 123456"),
    ("intuit_deposit", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "QBOOKS DEPOSIT"),
    ("intuit_deposit", "ORIG CO NAME INTUIT 123456 CO ENTRY DESCR DEPOSIT"),
    # Audit B5 (I15): PNC prints the entry before the payer.
    ("intuit_deposit", "CORPORATE ACH DEPOSIT 123456 INTUIT 123456"),
    ("square_checking_sales", "CARD PAYMENT SALES"),
    ("network_settlement", "AMERICAN EXPRESS SETTLEMENT"),
    ("network_settlement", "AMEXO GBL"),
    ("network_settlement", "MISC PAYMENT AMEX BANK OF CANADA"),
    ("generic_card_sales", "VISA MC DEPOSIT"),
    ("generic_card_sales", "CREDIT CARD DEPOSIT"),
    ("french_card_settlement", "REGLEMENT CARTE"),
    ("french_card_settlement", "DEPOT MARCHAND"),
]
#: Square's whole-row Activity type keeps its bare `^`: its layout is Square's own Details column (gated by bank), so it
#: is left out of the glued-date case. The row-start branch of `brand_dep` and `dep_brand` lets a leading date through
#: (owner ruling 2026-09-29), so its rows are in.
ROW_ANCHORED_CARD_ROWS = {
    ("square_checking_sales", "CARD PAYMENT SALES"),
}


def _card_form(label):
    return next(form for form in registry.CARD_SETTLEMENT_CREDIT_FORMS if form.label == label)


def _card_form_pattern(label):
    return _card_form(label).pattern


def _card_form_reads(label, row):
    """A card form reads a row when its pattern matches and its refusal does not."""
    form = _card_form(label)
    return bool(re.search(form.pattern, row)) and not (form.refusal is not None and re.search(form.refusal, row))


def test_every_card_form_has_a_fabricated_row():
    assert {label for label, _ in CARD_FORM_ROWS} == {form.label for form in registry.CARD_SETTLEMENT_CREDIT_FORMS}


@pytest.mark.parametrize(("label", "row"), [pair for pair in CARD_FORM_ROWS if pair not in ROW_ANCHORED_CARD_ROWS])
def test_a_card_form_reads_its_row_with_a_date_glued_on_the_left(label, row):
    # §7.0: '01/02Bankcard Deposit' normalizes to '01 02BANKCARD DEPOSIT'; the left boundary is (?<![A-Z]), never \b.
    pattern = _card_form_pattern(label)
    assert re.search(pattern, row)
    assert re.search(pattern, "01 02" + row)
    assert re.search(pattern, "01 02 " + row)


@pytest.mark.parametrize(("label", "row"), CARD_FORM_ROWS)
def test_a_letter_glued_on_the_left_still_blocks_a_card_form(label, row):
    # The boundary lets a digit through, not a letter: the form's leading token is still a whole word on its left.
    pattern = _card_form_pattern(label)
    assert re.search(pattern, row)
    assert not re.search(pattern, "X" + row)


#: Owner ruling 2026-09-29: every left boundary inside the card forms (refusal words, vetoes and required words) ignores
#: a glued date, so a date in front never changes how a row reads. The dated variants of a fabricated row.
DATE_PREFIXES = ("", "01 02", "01 02 ", "1 2")

#: One fabricated row per refusal or veto word, each refused, beside the same row without that word, which reads.
CARD_REFUSED_ROWS = [
    ("bankcard", "BANKCARD CTR DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "BANKCARD CENTER DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "PREMIER BANKCARD DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "FIRST BANKCARD DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "ELAN BANKCARD SETTLEMENT", "BANKCARD SETTLEMENT"),
    ("bankcard", "CARDMEMBER BANKCARD DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "CARD SERVICES BANKCARD DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "CARD SVCS BANKCARD DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "CREDIT CARD BANKCARD DEPOSIT", "BANKCARD DEPOSIT"),
    ("bankcard", "BANKCARD PROCESSING LLC DEPOSIT", "BANKCARD DEPOSIT"),
    ("net_settle", "LAW OFFICE DES NET SETTLE", "OFFICE DES NET SETTLE"),
    ("net_settle", "ATTORNEY DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "ATTORNEYS DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "ESQ DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "TRUST DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "ESCROW DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "TITLE DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "CLAIM DES NET SETTLE", "DES NET SETTLE"),
    ("net_settle", "CLAIMS DES NET SETTLE", "DES NET SETTLE"),
    ("intuit_deposit", "TAX INTUIT PYMT SOLN", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "RFND INTUIT PYMT SOLN", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "REFUND INTUIT PYMT SOLN", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "QBC INTUIT PYMT SOLN", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "CAPITAL INTUIT PYMT SOLN", "INTUIT PYMT SOLN"),
    ("intuit_deposit", "LOAN INTUIT PYMT SOLN", "INTUIT PYMT SOLN"),
    ("generic_card_sales", "BALANCE CREDIT CARD DEPOSIT", "CREDIT CARD DEPOSIT"),
    ("generic_card_sales", "REFUND CREDIT CARD DEPOSIT", "CREDIT CARD DEPOSIT"),
    ("generic_card_sales", "REWARD CREDIT CARD DEPOSIT", "CREDIT CARD DEPOSIT"),
    ("generic_card_sales", "REWARDS CREDIT CARD DEPOSIT", "CREDIT CARD DEPOSIT"),
]


@pytest.mark.parametrize(("label", "refused", "bare"), CARD_REFUSED_ROWS)
def test_a_date_in_front_never_lifts_a_card_refusal_or_veto(label, refused, bare):
    for prefix in DATE_PREFIXES:
        assert _card_form_reads(label, prefix + bare), prefix + bare
        assert not _card_form_reads(label, prefix + refused), prefix + refused


#: S2.2 review (item B): the CO of the bankcard refusal is a company's legal form, never the CO of a field label
#: (Chase's CO ENTRY DESCR, Bank of America's CO ID, a CO NAME), so a card deposit whose fields between are absent
#: still reads. Normalized rows; the Bank of America row is read as printed and joined (' DES ' removed).
@pytest.mark.parametrize(("row", "reads"), [
    ("ORIG CO NAME BANKCARD DESC DATE CO ENTRY DESCR DEPOSIT", True),            # Chase, no ORIG ID, blank date
    ("ORIG CO NAME BANKCARD DESC DATE CO DESCR DEPOSIT", True),                  # Chase's CO DESCR, no ENTRY
    ("ORIG CO NAME BANKCARD ORIG ID BKCD DESC DATE CO ENTRY DESCR DEPOSIT SEC CCD", True),
    ("BANKCARD DES DEPOSIT CO ID 1234567890 CCD", True),                         # Bank of America, no ID field
    ("BANKCARD DEPOSIT CO ID 1234567890 CCD", True),
    ("BANKCARD DEPOSIT CO NAME FABRIKAM", True),
    ("FABRIKAM BANKCARD CO DES DEPOSIT ID 1", False),                            # a company named BANKCARD
    ("BANKCARD SAMPLE CO DES DEPOSIT ID 1", False),
    ("BANKCARD SOLUTIONS CO DES DEPOSIT ID 1", False),
    ("FIRST BANKCARD CO DES DEPOSIT ID 1", False),
    ("ORIG CO NAME BANKCARD CO DESC DATE CO ENTRY DESCR DEPOSIT", False),
    ("ORIG CO NAME FABRIKAM BANKCARD CO ORIG ID 1234567890 DESC DATE CO ENTRY DESCR DEPOSIT SEC CCD", False),
])
def test_the_bankcard_refusal_spares_the_field_labels(row, reads):
    for prefix in DATE_PREFIXES:
        assert _card_form_reads("bankcard", prefix + row) is reads, prefix + row


#: A required word inside a card form (bankcard's order-free deposit word, a word after the form's leading token) reads
#: the same with a date glued in front of it: (form, the row up to that word, the row from that word on). The row does
#: not start at the form's leading token where that would let a row-start branch read it without the word.
CARD_REQUIRED_WORD_ROWS = [
    ("bankcard", "", "DEPOSIT BANKCARD"),
    ("bankcard", "", "SETTLEMENT BKCD"),
    ("merchant_services_mid", "MERCHANT SERVICES ", "TRANS SLIP"),
    ("merchant_services_mid", "MERCHANT SERVICES ", "MID 123456"),
    ("brand_dep", "ACH VISA DEP ", "MERCH SVC"),
    ("brand_dep", "ACH VISA DEP ", "DIV"),
    ("dep_brand", "ACH DEP VISA ", "MSP"),
    ("intuit_deposit", "ORIG CO NAME INTUIT 123456 CO ENTRY ", "DESCR DEPOSIT"),
    ("network_settlement", "AMERICAN EXPRESS ", "SETTLEMENT"),
    ("network_settlement", "DISCOVER NETWORK ", "SETL"),
]


@pytest.mark.parametrize(("label", "head", "word"), CARD_REQUIRED_WORD_ROWS)
def test_a_date_glued_to_a_card_form_s_required_word_never_blocks_it(label, head, word):
    for prefix in DATE_PREFIXES:
        assert _card_form_reads(label, head + prefix + word), head + prefix + word
    assert not _card_form_reads(label, head + "X" + word)


#: The row-start branch of brand_dep and dep_brand: a leading date (glued or spaced) is let through, and the rows the
#: anchor refused before stay refused (spec §7.1: `VISA DEP <person>` and `MOBILE DEP VISA` stay unmatched).
@pytest.mark.parametrize(("label", "row", "reads"), [
    ("brand_dep", "VISA DEP 1", True),
    ("brand_dep", "MC VISA DEP 1", True),
    ("dep_brand", "DEP VISA 1", True),
    ("dep_brand", "DEP MC1", True),
    ("brand_dep", "VISA DEP JOHN DOE", False),
    ("brand_dep", "MOBILE VISA DEP 1", False),
    ("brand_dep", "123 VISA DEP 1", False),
    ("brand_dep", "VISA DEP", False),
    ("dep_brand", "MOBILE DEP VISA", False),
    ("dep_brand", "MOBILE DEP VISA 1", False),
    ("dep_brand", "DEP VISA", False),
])
def test_a_leading_date_never_changes_a_row_start_brand_reading(label, row, reads):
    for prefix in DATE_PREFIXES:
        assert _card_form_reads(label, prefix + row) is reads, prefix + row
    assert not _card_form_reads(label, "01 02X" + row)


def test_no_card_form_keeps_a_left_word_boundary():
    # Owner ruling 2026-09-29: a left boundary inside a card form is (?<![A-Z]); \b stays only on the right of a word,
    # where it is followed by ')', '|', '.' or the end, never by a letter, a group '(?:' or a class '['.
    left_boundary = re.compile(r"\\b(?=[A-Z]|\(\?:|\[)")
    for form in registry.CARD_SETTLEMENT_CREDIT_FORMS:
        for text in (form.pattern, form.refusal or ""):
            assert not left_boundary.search(text), form.label


def test_the_payer_tables_collide_with_no_ledger_or_insurer_alias(monkeypatch):
    monkeypatch.setattr(registry, "HEALTHCARE_PAYER_ALIASES", {"Fabrikam Care": ("BCBSM",)})
    assert any("insurer alias" in problem for problem in operating_registry.problems())


def test_the_bnpl_settlements_are_payout_credit_entities():
    assert {"AFFIRM", "Afterpay", "GreenSky", "Klarna Inc", "Sunbit"} <= set(registry.PAYOUT_CREDIT_ENTITIES)

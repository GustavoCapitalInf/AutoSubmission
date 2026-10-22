"""Audit fix batch B6 (true revenue spec §6.3, §8.1, §20; lender detection spec §4.2, §4.4, §4.6, §5): the financing
registry's credit side. A funder's glued, cut or run-together spelling is its alias (I08, I22), a special-purpose
vehicle's credit is held (I08), consumer lenders' and cash-advance apps' instant-payment forms are their aliases and an
earned-wage push is wages (I49, Q8), a lending bank's credit is held (I23), every IPFS spelling takes the insurance
treatment (I24), a factor's operating-account spelling is its alias (I25), and a factoring review entity's payouts are
counted and flagged, marked unconfirmed (I10). Fabricated rows only, in the banks' printed formats; public names only
where the registry lists them or the brief names them (Forward Financing, East Shore Equities, The LCF Group, SoFi,
Brigit, Tilt / Empower, MoneyLion, PayActiv, DailyPay, Celtic Bank, Newtek Bank, IPFS, Treadstone, Eagle Capital,
Texoma Capital, Primary Capital Solutions)."""
from __future__ import annotations

import copy
from dataclasses import asdict

import pytest

from analysis import classification_registry as registry
from analysis.descriptor import payer as descriptor_payer
from analysis.true_revenue import guards
from analysis.true_revenue import counter_debit_pairing
from analysis.true_revenue import words as true_revenue_words
from analysis.description_text import normalize_transaction_description as normalize
from analysis.detect import find_flagged_positions
from analysis.payee_matcher import match_known_payee, registry_match
from analysis.revenue import apply_serialized_revenue_review, rebuild_serialized_revenue_views
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "NORTHWIND LABS INC"


def _statement(rows, *, holder=HOLDER, bank=None, days=None):
    return Statement(account_name=holder, bank=bank, currency="USD", transactions=[
        Transaction(date=f"2054-03-{(days[index] if days else index + 2):02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ])


def _records(rows, **kwargs):
    return classify_statement_transactions(_statement(rows, **kwargs))


def _credits(records):
    return [record for record in records if record.amount > 0]


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method


def _out_of_true(record):
    return record.revenue_tier in {"non_revenue", "excluded_pending_review"}


FORWARD_DEBITS = [("FORWARD FIN USA DES:DEBIT ID:1234 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD", -500.0)] * 3


# --- I08: Forward Financing's glued spelling and its special-purpose vehicle -----------------------------------------


@pytest.mark.parametrize("text", [
    "ACH DEPOSIT FORWARDFINUSA1 PAYMENTS",
    "ACH DEPOSIT FORWARDFINUSA7 PAYMENTS 540302 NORTHWIND LABS ACH123456",
    "FORWARDFINUSA9 DES:PAYMENTS ID:ACH123456 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "PAYMENTS FORWARDFINUSA1",
    "PAYMENTS FORWARDFINUSA3 NORTHWIND LABS CUSTOMER ID ACH123456",
    "ACH PAYMENTS ACH123456 FORWARDFINUSA7 ACHDD",
    "ELECTRONIC DEPOSIT FROM FORWARDFINUSA9",
    "ORIG CO NAME:FORWARDFINUSA3 ORIG ID:1234567890 DESC DATE:540302 CO ENTRY DESCR:PAYMENTS SEC:CCD "
    "TRACE:123456789012345 EED:540302 IND ID:ACH123456 IND NAME:NORTHWIND LABS INC TRN:1234567890TC",
])
@pytest.mark.parametrize("debits", [[], FORWARD_DEBITS], ids=["alone", "with_forward_debits"])
def test_forward_s_glued_spelling_is_its_financing_proceeds(text, debits):
    [credit] = _credits(_records([(text, 25000.0), *debits]))
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert credit.revenue_canonical_entity == "Forward Financing"
    assert credit.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("text", [
    "FEDWIRE CREDIT VIA SAMPLE BANK/123456789 B/O: FF SPE II LLC BOSTON MA 02101 US REF: CHASE NYC/CTR/BNF=NORTHWIND "
    "LABS INC BROOKLYN NY 11201 US AC-000000001234 RFB=1234 OBI=PUR P 1234 IMAD: 0101MMQFMP9N000001 TRN: 1234567890FF",
    "INCOMING WIRE TRANSFER MTS NO 540302000001 ORIGINATOR NAME FF SPE II LLC ORIG TO BNF INFO FED ID "
    "20540302MMQFMP9N000001",
])
def test_a_special_purpose_vehicle_s_wire_is_held_as_financing(text):
    [credit] = _credits(_records([(text, 30000.0)]))
    assert _tier(credit) == ("excluded_pending_review", "financing_named_payer")


def test_forward_s_spelled_out_wire_stays_its_financing_proceeds():
    text = ("FEDWIRE CREDIT VIA SAMPLE BANK/123456789 B/O: FORWARD FINANCING USA LLC BOSTON MA 02101 US REF: CHASE "
            "NYC/CTR/BNF=NORTHWIND LABS INC BROOKLYN NY 11201 US AC-000000001234 IMAD: 0101MMQFMP9N000002")
    [credit] = _credits(_records([(text, 9000.0)]))
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert credit.revenue_canonical_entity == "Forward Financing"


@pytest.mark.parametrize("alias", ["FORWARDFINUSA", "FORWARD FIN USA", "FORWARD FINANCING USA"])
def test_forward_s_new_aliases_are_ledger_aliases(alias):
    assert alias in registry.LENDER_ALIASES["Forward Financing"]


@pytest.mark.parametrize(("text", "entity"), [
    ("ACH DEPOSIT FORWARDFINUSA1 PAYMENTS", "Forward Financing"),
    ("ACH DEPOSIT FORWARDFINUSA PAYMENTS", "Forward Financing"),
    # A multi-word alias's run-together form, a digit run glued after it.
    ("ACH DEPOSIT FORWARDFIN12 PAYMENTS", "Forward Financing"),
    ("LCFGROUPINC7 DES:REF1", "The LCF Group, Inc"),
    # Audit round 2, R2-B08 (R47 (b)): and a digit run with one or two letters after it.
    ("ACH DEPOSIT FORWARDFINUSA1X PAYMENTS", "Forward Financing"),
    ("FORWARDFINUSA12AB DES:PAYMENTS ID:ACH123456", "Forward Financing"),
    ("LCFGROUPINC7A DES:REF1", "The LCF Group, Inc"),
])
def test_a_run_together_alias_reads_a_digit_run_glued_after_it(text, entity):
    found = match_known_payee(normalize(text), credit=True)
    assert found is not None and found.entity == entity


@pytest.mark.parametrize("text", [
    "ACH DEPOSIT FORWARDFINUSA1 PAYMENTS",
    "ACH DEPOSIT FORWARDFIN12 PAYMENTS",
    "LCFGROUPINC7 DES:REF1",
    # Audit round 2, R2-B08 (R47 (b)): the letter-tail arm is the credit index's only.
    "ACH DEPOSIT FORWARDFINUSA1X PAYMENTS",
    # The credit-only alias, whole.
    "ORIG CO NAME:SAMPLEPAY ORIG ID:1234 CO ENTRY DESCR:ECHECK SEC:WEB IND ID:LCFGROUPINC IND NAME:NORTHWIND",
])
def test_a_debit_keeps_today_s_known_payee_reading(text):
    # The digit arm and the credit-only aliases are read on credits only: on a debit they would add lender and flag
    # readings the G7 allowlist has not signed off.
    assert match_known_payee(normalize(text)) is None


def test_a_debit_printing_the_credit_only_alias_takes_no_lender_reading():
    text = "ORIG CO NAME:SAMPLEPAY ORIG ID:1234 CO ENTRY DESCR:ECHECK SEC:WEB IND ID:LCFGROUPINC IND NAME:NORTHWIND"
    [debit] = _records([(text, -100.0)])
    assert debit.classification != "confirmed_lender"
    [credit] = _records([(text, 100.0)])
    assert credit.revenue_canonical_entity == "The LCF Group, Inc"


def test_the_credit_only_aliases_are_ledger_aliases():
    aliases = {alias for group in registry.PAYEE_GROUP_REGISTRIES.values() for spellings in group.values()
               for alias in spellings}
    assert registry.CREDIT_ONLY_ALIASES == {"LCFGROUPINC"}
    assert registry.CREDIT_ONLY_ALIASES <= aliases


@pytest.mark.parametrize("text", [
    # A one-word alias shorter than a run-together form keeps whole-token matching ('ONDECK' is six letters).
    "ACH DEPOSIT ONDECK123 PAYMENTS",
    "ACH DEPOSIT ONDECK123X PAYMENTS",
    # The digit run must end the token, or one or two letters after it (audit round 2, R2-B08: R47 (b)); three
    # letters or more after it are a word, a documented limit.
    "ACH DEPOSIT FORWARDFINUSA1XYZ PAYMENTS",
    "ACH DEPOSIT FORWARDFINUSAX1 PAYMENTS",
    # A run-together alias inside a longer word is no match.
    "ACH DEPOSIT XFORWARDFINUSA1 PAYMENTS",
    "ACH DEPOSIT XFORWARDFINUSA1X PAYMENTS",
    # A payer no alias names keeps no reading.
    "FABRIKAMSUPPLY1X DES:PAYMENTS ID:ACH123456",
])
def test_the_digit_arm_reads_only_a_whole_run_together_token_and_its_trailing_digits(text):
    assert match_known_payee(normalize(text), credit=True) is None


@pytest.mark.parametrize(("word", "root"), [
    ("FF SPE II LLC", True), ("FUNDAMENTAL SPE LLC", True), ("CONTOSO SPV LLC", True),
    ("SPECIALTY FOODS LLC", False), ("SPEED SHOP INC", False), ("CONTOSO SPE CO", True),
    ("FINUS SUPPLY", False),
    # B6 review round 1: a glued FIN USA is no root. With no left boundary it read any run-together name ending in
    # FIN + USA (a muffin or griffin brand); Forward's FORWARDFINUSA is its ledger alias, read with the reference on.
    ("FABRIKAMFINUSA", False), ("FABRIKAMFINUSA1", False), ("MUFFINUSA LLC", False),
])
def test_the_financing_root_reads_a_special_purpose_entity_never_a_glued_fin_usa(word, root):
    assert bool(true_revenue_words._FINANCING_ROOT.search(word)) is root


def test_a_repeat_payer_whose_run_together_name_ends_in_fin_usa_stays_verified():
    rows = [(f"MUFFINUSA LLC DES:PAYMENT ID:{n} INDN:NORTHWIND LABS INC CO ID:1234567890 CCD", 2000.0 + n)
            for n in (1, 2)]
    assert [_tier(credit) for credit in _credits(_records(rows))] == [("verified", "named_payer_repeats")] * 2


# --- I22: a funder's cut or glued spelling -----------------------------------------------------------------------------


def test_east_shore_s_cut_name_is_its_financing_proceeds_beside_its_debits():
    rows = [("EAST SHORE EQU CORP PAY NORTHWIND LABS", 3000.0), ("ESENOW COM PAYMENT", -100.0),
            ("ESENOW COM PAYMENT", -100.0)]
    [credit] = _credits(_records(rows))
    assert _out_of_true(credit)
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert credit.revenue_canonical_entity == "East Shore Equities LLC"


def test_a_customer_named_east_shore_equipment_is_no_funder():
    rows = [("EAST SHORE EQUIPMENT RENTALS INC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1 CCD", 3000.0)]
    [credit] = _credits(_records(rows))
    assert credit.revenue_tier != "non_revenue"
    assert credit.revenue_canonical_entity != "East Shore Equities LLC"


def test_lcf_s_glued_name_is_its_financing_proceeds_beside_its_debits():
    rows = [("LCFGROUPINC1 DES:REF1 ID:CONTOSO INDN:NORTHWIND LABS INC CO ID:1234567890 CCD", 900.0),
            ("LCF DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1 CCD", -300.0),
            ("LCF DES:PAYMENT ID:2 INDN:NORTHWIND LABS INC CO ID:1 CCD", -300.0)]
    [credit] = _credits(_records(rows))
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert credit.revenue_canonical_entity == "The LCF Group, Inc"


@pytest.mark.parametrize(("entity", "alias"), [
    ("East Shore Equities LLC", "EAST SHORE EQU"), ("The LCF Group, Inc", "LCFGROUPINC")])
def test_the_cut_and_glued_funder_spellings_are_ledger_aliases(entity, alias):
    assert alias in registry.LENDER_ALIASES[entity]


# --- I49: consumer lenders' and cash-advance apps' instant-payment forms ------------------------------------------------


@pytest.mark.parametrize(("text", "entity"), [
    ("SOFI PL DISB PL DISB 540211 1234 SAMPLE PERSON", "SoFi Bank, N.A."),
    ("RTP CREDIT BRIGIT 1", "Brigit"),
    ("RTP CREDIT BRIGIT AB12CD34EF56GH7", "Brigit"),
    ("INSTPMNTIN BRIGIT 02 03 12345 AB12CD34EF56GH7", "Brigit"),
    ("INSTPMNTIN EMPOWER 1", "Tilt (formerly Empower Finance)"),
    ("RTP CREDIT EMPOWER AB12CD34EF56GH7", "Tilt (formerly Empower Finance)"),
    ("INSTANT PMT FROM ML PLUS LLC ON 02 09 REF 20540209111111111P1BPF0000000000000 INSTACASH FUNDS", "MoneyLion"),
    ("REAL TIME PAYMENT CREDIT RECD FROM ABA/CONTR BNK-021000021 FROM: ML PLUS LLC REF: 1234567 INFO: TEXT "
     "INSTACASH FUNDS IID: 20540209021000021P1BPF00000000000 TRN: 1234567890GD", "MoneyLion"),
    ("CARD CREDIT TILT CASH 1234 SAN FRANCISCO CA 94105 1234", "Tilt (formerly Empower Finance)"),
])
def test_a_consumer_advance_s_instant_payment_form_is_its_financing_proceeds(text, entity):
    [credit] = _credits(_records([(text, 150.0)]))
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert credit.revenue_canonical_entity == entity


@pytest.mark.parametrize("text", [
    # An RTP or instant-payment payer named EMPOWER that prints a company's name, not a reference code, is no
    # cash-advance app.
    "RTP CREDIT EMPOWER CONTOSO LLC",
    "RTP CREDIT EMPOWER SOLUTIONS AB12CD34EF56GH7",
    "INSTPMNTIN EMPOWER CONTOSO 02 03 12345 AB12CD34EF56GH7",
    # Bare EMPOWER is never an alias.
    "EMPOWER CONTOSO DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1 CCD",
])
def test_a_company_named_empower_is_no_cash_advance_app(text):
    [credit] = _credits(_records([(text, 150.0)]))
    assert credit.revenue_match_method != "financing_proceeds_credit"
    found = match_known_payee(normalize(text), credit=True)
    assert found is None or found.entity != "Tilt (formerly Empower Finance)"


@pytest.mark.parametrize("alias", ["RTP CREDIT EMPOWER", "INSTPMNTIN EMPOWER"])
def test_the_empower_instant_payment_aliases_are_tied_to_a_reference_code(alias):
    tilt = "Tilt (formerly Empower Finance)"
    assert alias in registry.REFERENCE_TIED_ALIASES
    assert alias in registry.PERSONAL_LOAN_ALIASES[tilt]
    assert match_known_payee(alias).entity == tilt
    assert match_known_payee(f"{alias} AB12CD34EF56GH7").entity == tilt
    # A reference split by a space still starts with a token that holds a digit.
    assert match_known_payee(f"{alias} AB1C DEFGH 2IJK").entity == tilt
    assert match_known_payee(f"{alias} CONTOSO LLC") is None
    # The run-together form is tied too.
    assert match_known_payee(f"{alias.replace(' ', '')} AB12CD34EF56GH7").entity == tilt
    assert match_known_payee(f"{alias.replace(' ', '')} CONTOSO") is None


def test_every_reference_tied_alias_is_a_known_payee_alias():
    aliases = {alias for group in registry.PAYEE_GROUP_REGISTRIES.values() for spellings in group.values()
               for alias in spellings}
    assert registry.REFERENCE_TIED_ALIASES <= aliases


TILT = "Tilt (formerly Empower Finance)"


@pytest.mark.parametrize(("alias", "entity"), [
    ("RTP CREDIT EMPOWER", TILT), ("INSTPMNTIN EMPOWER", TILT), ("TILT CASH", TILT),
    ("RTP CREDIT BRIGIT", "Brigit"), ("INSTPMNTIN BRIGIT", "Brigit"),
])
def test_every_app_instant_payment_and_card_push_form_is_tied_to_a_reference_code(alias, entity):
    # B6 review round 1: BRIGIT is a given name and TILT CASH two ordinary words, so the app's rail forms are read
    # only where a reference code (a token with a digit) or nothing follows them, as the Empower forms are.
    assert registry.REFERENCE_TIED_ALIASES == {
        "RTP CREDIT EMPOWER", "INSTPMNTIN EMPOWER", "TILT CASH", "RTP CREDIT BRIGIT", "INSTPMNTIN BRIGIT"}
    assert match_known_payee(alias).entity == entity
    assert match_known_payee(f"{alias} AB12CD34EF56GH7", credit=True).entity == entity
    assert match_known_payee(f"{alias} 02 03 12345").entity == entity
    assert match_known_payee(f"{alias} SAMPLE AB12CD34EF56GH7") is None
    assert match_known_payee(f"{alias} CONTOSO LLC", credit=True) is None
    # The run-together form is tied too.
    assert match_known_payee(f"{alias.replace(' ', '')} AB12CD34EF56GH7").entity == entity
    assert match_known_payee(f"{alias.replace(' ', '')} CONTOSO", credit=True) is None


@pytest.mark.parametrize("text", [
    # A person whose given name is Brigit, paid on the RTP network or by PNC's instant payment.
    "RTP CREDIT BRIGIT SAMPLE AB12CD34EF56GH7",
    "INSTPMNTIN BRIGIT SAMPLE 02 03 12345 AB12CD34EF56GH7",
    # A company whose name starts with BRIGIT, paid on the RTP network.
    "RTP CREDIT BRIGIT CONTOSO LLC AB12CD34EF56GH7",
    # A company whose name starts with the words TILT CASH, paying by ACH.
    "TILT CASH REGISTERS INC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
])
def test_a_payer_whose_name_starts_like_an_app_s_rail_form_is_no_cash_advance_app(text):
    [credit] = _credits(_records([(text, 400.0)]))
    assert credit.revenue_tier != "non_revenue"
    assert credit.revenue_match_method != "financing_proceeds_credit"
    assert not credit.contributes_to_lender_credit_exclusion
    found = match_known_payee(normalize(text), credit=True)
    assert found is None or found.entity not in {"Brigit", TILT}


def test_tilt_s_full_advance_spelling_is_read_before_any_word():
    # TILT CASH ADVANCE is a longer alias, never tied: the app's own product name reads whatever follows it.
    [credit] = _credits(_records([("TILT CASH ADVANCE SAN FRANCISCO CA", 150.0)]))
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert credit.revenue_canonical_entity == TILT


def test_a_customer_named_empower_paying_by_accounts_payable_stays_verified():
    rows = [("ACCOUNT PAYABLE PMT EMPOWER CONTOSO", 1000.0), ("ACCOUNT PAYABLE PMT EMPOWER CONTOSO", 2000.0)]
    assert [credit.revenue_tier for credit in _credits(_records(rows))] == ["verified", "verified"]


@pytest.mark.parametrize("text", [
    "PAYACTIV PMNT",
    "PAYACTIV 02 14 123456789 PMNT RCVD PAYACTIV SAN JOSE CA",
    "MONEY TRANSFER AUTHORIZED ON 02 11 FROM DAILYPAY NY S123456789012345 CARD 1234",
])
def test_an_earned_wage_push_is_held_as_wages(text):
    [credit] = _credits(_records([(text, 150.0)]))
    assert _tier(credit) == ("excluded_pending_review", "payroll_or_salary")


def test_a_payer_named_daily_pay_spaced_is_no_earned_wage_push():
    [credit] = _credits(_records([("CONTOSO DAILY PAY LLC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1 CCD",
                                   150.0)]))
    assert credit.revenue_tier_reason != "payroll_or_salary"


@pytest.mark.parametrize(("text", "word"), [
    ("INSTPMNTIN BRIGIT 02 03 12345 AB12CD34EF56GH7", "BRIGIT"),
    ("RTP CREDIT FABRIKAMCASH AB12CD34EF56GH7", "FABRIKAMCASH"),
    ("RTP CREDIT CONTOSO TRADING AB12CD34EF56GH7", "CONTOSO"),
])
def test_the_counter_debit_reading_reads_past_an_instant_payment_rail_label(text, word):
    [record] = _credits(_records([(text, 50.0)]))
    norm = normalize(text)
    region = descriptor_payer.payer_region(norm)
    counter = counter_debit_pairing.counter_credit(record, norm, region)
    assert counter.reading.legacy == word


@pytest.mark.parametrize(("text", "region", "words"), [
    ("INSTPMNTIN FABRIKAMCASH 02 03 12345", "INSTPMNTIN FABRIKAMCASH", "FABRIKAMCASH"),
    ("RTP CREDIT FABRIKAMCASH AB12CD34EF56GH7", "", "FABRIKAMCASH AB12CD34EF56GH7"),
    # RTP CREDIT FROM prints its sender after FROM, which the person-to-person readers read: no name is taken here.
    ("RTP CREDIT FROM FABRIKAMCASH REF 1234", "", ""),
    # A label elsewhere on the row is no rail label before the payer.
    ("CONTOSO INSTPMNTIN 1234", "CONTOSO INSTPMNTIN", "CONTOSO INSTPMNTIN"),
    ("ACH CREDIT RTP CREDIT CONTOSO", "", ""),
    # Audit round 2, R2-B02 (R02): an e-Transfer's sender printed without FROM is read as Q4's sender reader reads it,
    # and a wallet's cash-out names no sender.
    ("E TRANSFER RECEIVED CONTOSO SAMPLE", "", "CONTOSO SAMPLE"),
    ("RTP CREDIT VENMO NEW YORK CITY 01 12345", "", ""),
    ("ELECTRONIC DEPOSIT FROM VENMO", "VENMO", ""),
])
def test_the_counter_region_drops_only_a_leading_rail_label(text, region, words):
    assert counter_debit_pairing._counter_region(text, region) == words


def test_an_unlisted_app_s_instant_payment_is_held_beside_its_lender_debits():
    # A cash-advance app no alias lists, whose fixed weekly pulls the classifier reads as a potential lender (D6).
    rows = [("RTP CREDIT FABRIKAMCASH AB12CD34EF56GH7", 100.0),
            ("FABRIKAMCASH DES:REPAYMENT ID:1", -25.0), ("FABRIKAMCASH DES:REPAYMENT ID:1", -25.0),
            ("FABRIKAMCASH DES:REPAYMENT ID:1", -25.0)]
    records = _records(rows, days=[1, 2, 9, 16])
    assert [record.classification for record in records[1:]] == ["potential_lender"] * 3
    [credit] = _credits(records)
    assert _tier(credit) == ("excluded_pending_review", "payer_debited_as_lender")


# --- I23: a lending bank's credit -------------------------------------------------------------------------------------


CELTIC = "CELTIC BANK DES:XXXXXXXXX ID:{n} INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"


def test_a_lending_bank_s_repeated_credits_are_held_not_verified():
    rows = [(CELTIC.format(n=1), 40000.0), (CELTIC.format(n=2), 45000.0)]
    assert [_tier(credit) for credit in _credits(_records(rows))] == [
        ("excluded_pending_review", "financing_named_payer")] * 2


@pytest.mark.parametrize("text", [
    "CELTIC BANK DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "NEWTEK BANK N A DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "NEWTEK BANK N A WIRE",
])
def test_a_lending_bank_s_credit_is_held_as_financing(text):
    [credit] = _credits(_records([(text, 20000.0)]))
    assert _tier(credit) == ("excluded_pending_review", "financing_named_payer")


def test_celtic_s_bluevine_line_stays_its_financing_proceeds():
    text = "CELTIC BANK DES:BV LOAN ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"
    [credit] = _credits(_records([(text, 40000.0)]))
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")


@pytest.mark.parametrize("text", [
    "CELTIC CONTOSO LLC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "NEWTEK CONTOSO SUPPLY DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
])
def test_a_payer_whose_name_only_starts_like_a_lending_bank_is_not_held(text):
    [credit] = _credits(_records([(text, 2000.0)]))
    assert credit.revenue_tier_reason != "financing_named_payer"


def test_a_lending_bank_debit_takes_no_lender_reading():
    records = _records([("CELTIC BANK DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD", -2000.0)])
    assert records[0].classification not in {"confirmed_lender", "potential_lender"}


def test_the_lending_bank_hold_is_the_census_s_hold_rule():
    text = normalize(CELTIC.format(n=1))
    [record] = _records([(CELTIC.format(n=1), 40000.0)])
    region = descriptor_payer.payer_region(text)
    entry = descriptor_payer.entry_fields(text)
    assert guards.hold_rule(record, text, region, entry) == "lending_bank"


# --- I24: every IPFS spelling takes the insurance treatment ----------------------------------------------------------


@pytest.mark.parametrize("text", [
    "IPFS888 123 4567 IPFSFNDFLP P 1234",
    "IPFS888 123 4567 IPFSFLP12 P 1234",
    "IPFS 800 123 4567 IPFSFNDFLP P 1234",
    "IPFS888 123 4567 DES:IPFSFNDFLP ID:P 1234 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
])
def test_every_ipfs_credit_spelling_is_premium_finance_non_revenue(text):
    [credit] = _credits(_records([(text, 10000.0)]))
    assert credit.classification == "insurance"
    assert (credit.revenue_tier, credit.revenue_match_method) == ("non_revenue", "insurance_provider_credit_exclusion")
    assert credit.revenue_canonical_entity == "IPFS Corporation"


@pytest.mark.parametrize(("text", "classification", "entity", "flag"), [
    ("IPFS888 123 4567 IPFSPMTFLP P 1234", "insurance", "IPFS Corporation", "premium_financing"),
    # A debit IPFS prints with no listed spelling keeps today's reading (the brief: IPFS debits unchanged).
    ("ORIG CO NAME:IPFS888 123 4567 ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:IPFSPMTZZZSEC:CCD TRACE:1",
     "other", None, None),
])
def test_ipfs_debits_keep_their_reading(text, classification, entity, flag):
    [record] = _records([(text, -1000.0)])
    assert (record.classification, record.canonical_entity, record.flagged_group) == (classification, entity, flag)


@pytest.mark.parametrize("alias", ["IPFSFNDFLP", "IPFSFLP"])
def test_the_ipfs_funding_spellings_are_premium_finance_aliases(alias):
    assert alias in registry.PREMIUM_FINANCE_ALIASES["IPFS Corporation"]


def test_the_premium_finance_lookup_reads_a_glued_digit_run_only_when_asked():
    assert registry_match("IPFS888 123 4567", registry.PREMIUM_FINANCE_ALIASES) is None
    assert registry_match("IPFS888 123 4567", registry.PREMIUM_FINANCE_ALIASES, glued_digits=True) == (
        "IPFS Corporation", "IPFS")
    assert registry_match("XIPFS888 123", registry.PREMIUM_FINANCE_ALIASES, glued_digits=True) is None


# --- I25: a factor's operating-account spelling ------------------------------------------------------------------------


TREADSTONE = "TREADSTONE OPER DES:PAYMENT ID:{n} INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"


def test_a_factor_s_operating_account_payouts_are_counted_and_flagged_never_verified():
    records = _records([(TREADSTONE.format(n=n), 700.0) for n in range(1, 5)])
    for record in records:
        assert _tier(record) == ("counted_flagged", "factoring_payout")
        assert (record.classification, record.canonical_entity) == ("factoring", "Treadstone US Capital, LLC")
        assert record.flagged_group == "factoring" and record.contributes_to_flagged_totals
        assert not record.review_required


@pytest.mark.parametrize("text", [
    "TREADSTONE OPER DES:INVOICE PMT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "ACCOUNTS PAYABLE TREADSTONE OPER INVOICE 1234",
])
def test_a_factor_s_payout_an_earlier_rule_verified_is_counted_and_flagged(text):
    # An invoice or accounts-payable descriptor verifies a payer earlier in the classifier; a factor's payout is never
    # verified, whichever rule read it (the factoring ruling of 2026-09-26).
    [record] = _records([(text, 700.0)])
    assert record.classification == "factoring"
    assert _tier(record) == ("counted_flagged", "factoring_payout")
    assert record.revenue_match_method == "factoring_payout_payer"


def test_another_treadstone_company_keeps_its_reading():
    rows = [("TREADSTONE TRANSPORT LLC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD", 700.0)] * 2
    for record in _records(rows):
        assert record.classification != "factoring"
        assert _tier(record) == ("verified", "named_payer_repeats")


def test_treadstone_s_operating_spelling_is_a_ledger_alias_never_its_bare_name():
    aliases = registry.FACTORING_ALIASES["Treadstone US Capital, LLC"]
    assert "TREADSTONE OPER" in aliases and "TREADSTONE" not in aliases


# --- I10: a factoring review entity's payouts ---------------------------------------------------------------------------


EAGLE = "EAGLE CAPITAL DES:EAGLE CAP ID:{n} INDN:NORTHWIND LABS INC CO ID:1234567890 CCD"


def test_a_factoring_review_entity_s_payouts_are_counted_flagged_and_unconfirmed():
    statement = _statement([(EAGLE.format(n=n), 3000.0 + n) for n in range(1, 6)])
    records = classify_statement_transactions(statement)
    for record in records:
        assert _tier(record) == ("counted_flagged", "factoring_payout")
        assert (record.classification, record.flagged_group) == ("factoring", "factoring")
        assert record.canonical_entity == "EAGLE CAPITAL (unconfirmed factoring payer)"
        assert record.review_required and record.contributes_to_flagged_totals
        assert record.match_method == "unconfirmed_flag_payee_alias"
    [position] = find_flagged_positions(statement, records)
    assert (position.group, position.count_credited, position.review_required) == ("factoring", 5, True)


def test_a_factoring_review_entity_s_payout_can_be_reviewed():
    statement = _statement([(EAGLE.format(n=1), 3000.0), (EAGLE.format(n=2), 3100.0)])
    records = classify_statement_transactions(statement)
    payload = rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)
        ]},
        "metrics": {}, "detection": {},
    })
    location = payload["statement"]["transactions"][0]["classification"]["source_location"]
    confirmed = apply_serialized_revenue_review(copy.deepcopy(payload), source_location=location, decision="confirm")
    assert confirmed["statement"]["transactions"][0]["classification"]["revenue_tier"] == "verified"


@pytest.mark.parametrize("text", [
    "TEXOMA CAPITAL LLC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD",
    "WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:2054030200001 SEQ:1/1 ORIG:TEXOMA CAPITAL LLC ID:1234 "
    "SND BK:SAMPLE BANK ID:123456789",
])
def test_each_factoring_review_entity_s_credit_takes_the_factoring_payout(text):
    [record] = _records([(text, 2000.0)])
    assert _tier(record) == ("counted_flagged", "factoring_payout")
    assert record.review_required and record.flagged_group == "factoring"


@pytest.mark.parametrize("text", [
    # The credit-side reversal rule reads a trailing RETURNED ITEM that step 3's row rule does not.
    "TEXOMA CAPITAL LLC DES:PAYMENT ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD RETURNED ITEM",
    "EAGLE CAPITAL DES:EAGLE CAP ID:1 INDN:NORTHWIND LABS INC CO ID:1234567890 CCD RETURNED ITEM",
])
def test_a_factoring_review_entity_s_reversed_credit_is_no_factoring_payout(text):
    # B6 review round 1: a reversed credit is no payout, so it takes no Factoring flag and no review mark: the row
    # keeps the reversal rule's non-revenue decision and the reading it had before the routing.
    statement = _statement([(text, 2000.0)])
    [record] = classify_statement_transactions(statement)
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "reversal_cancellation_exclusion")
    assert record.classification != "factoring" and record.flagged_group is None
    assert not record.contributes_to_flagged_totals and not record.review_required
    assert not find_flagged_positions(statement, [record])


def test_a_factoring_review_entity_s_payout_beside_its_reversal_is_still_flagged():
    statement = _statement([(EAGLE.format(n=1), 3000.0), (EAGLE.format(n=2) + " RETURNED ITEM", 3100.0)])
    payout, reversal = classify_statement_transactions(statement)
    assert _tier(payout) == ("counted_flagged", "factoring_payout") and payout.flagged_group == "factoring"
    assert reversal.revenue_match_method == "reversal_cancellation_exclusion" and reversal.flagged_group is None
    [position] = find_flagged_positions(statement, [payout, reversal])
    assert (position.group, position.count_credited) == ("factoring", 1)


def test_a_factoring_review_entity_s_debits_keep_the_potential_tier():
    text = ("WIRE TYPE:WIRE OUT DATE:540302 TIME:1200 ET TRN:2054030200001 SERVICE REF:1234 BNF:PRIMARY CAPITAL "
            "SOLUTIONS ID:1234 BNF BK:SAMPLE BANK ID:123456789 PMT DET:1234")
    [record] = _records([(text, -5000.0)])
    assert (record.classification, record.canonical_entity) == ("potential_lender", "Primary Capital Solutions")
    assert record.contributes_to_potential_lender_totals


def test_the_factoring_review_entities_are_the_ledger_s_factoring_review_entities():
    assert set(registry.FACTORING_REVIEW_ENTITIES) == {
        "EAGLE CAPITAL (unconfirmed factoring payer)", "Primary Capital Solutions", "Texoma Capital LLC"}
    assert set(registry.FACTORING_REVIEW_ENTITIES) <= set(registry.POTENTIAL_LENDER_ALIASES)
    assert not set(registry.FACTORING_REVIEW_ENTITIES) & set(registry.REVIEW_FLAG_ENTITIES)


# --- Audit round 2, R2-B03 (R10): Rook Bristol Financial's name cut at 15 characters (CPA-005 short name) ------------
# Canadian banks print a pre-authorized payment's originator short name, which cuts ROOK BRISTOL FINANCIAL LLC to
# ROOK BRISTOL FI; the ledger admits that spelling (as Sheffield Financial's SHEFFIELD FI), so a funding credit is the
# lender's financing proceeds whichever spelling the bank prints. Each statement carries two customer credits too.

ROOK = "Rook Bristol Financial LLC"
ROOK_LAYOUTS = {
    # bank: (the layout's credit with the payer's name in {payer}).
    "BMO Bank of Montreal": "Direct Deposit, {payer} MSP/DIV",
    "Desjardins": "COMPTE DIVERS {payer}",
    "TD Canada Trust": "{payer} DIV",
    "RBC Royal Bank": "Misc Payment {payer}",
    "Scotiabank": "MISC PAYMENT {payer}",
}


def _rook_records(bank, payer, amount=9500.0):
    layout = ROOK_LAYOUTS[bank]
    rows = [(layout.format(payer=payer), amount), (layout.format(payer="CONTOSO ROOFING"), 1200.0),
            (layout.format(payer="CONTOSO ROOFING"), 1300.0)]
    return _records(rows, bank=bank)


@pytest.mark.parametrize(("bank", "payer"), [
    ("BMO Bank of Montreal", "ROOK BRISTOL FI"),
    ("Desjardins", "ROOK BRISTOL FI"),
    ("TD Canada Trust", "ROOK BRISTOL FI"),
    ("RBC Royal Bank", "ROOK BRISTOL FI"),
    ("BMO Bank of Montreal", "ROOKBRISTOLFI"),
    # The full spelling, as before.
    ("Scotiabank", "ROOK BRISTOL FINANCIAL LL"),
], ids=["bmo", "desjardins", "td", "rbc", "bmo-run-together", "scotiabank-full-spelling"])
def test_rook_bristol_s_cut_name_is_its_financing_proceeds(bank, payer):
    funding = _rook_records(bank, payer)[0]
    assert (funding.revenue_tier, funding.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert funding.revenue_canonical_entity == ROOK


def test_rook_bristol_s_cut_name_on_a_debit_is_the_confirmed_lender():
    [record] = _records([("Pre-Authorized Payment, ROOK BRISTOL FI MSP/DIV", -950.0)], bank="BMO Bank of Montreal")
    assert (record.classification, record.canonical_entity) == ("confirmed_lender", ROOK)


@pytest.mark.parametrize(("bank", "payer", "expected"), [
    # A payer whose name only starts like the cut is no lender; the customers' credits keep their readings; another
    # lender's registered cut (Sheffield Financial's SHEFFIELD FI) stays its financing proceeds.
    ("TD Canada Trust", "ROOK BRISTOL FITNESS", ("counted_flagged", "named_payer_unlabelled")),
    ("BMO Bank of Montreal", "SHEFFIELD FI", ("non_revenue", "financing_proceeds_credit")),
])
def test_the_cut_reads_no_lookalike_and_other_cuts_keep_their_readings(bank, payer, expected):
    records = _rook_records(bank, payer)
    assert _tier(records[0]) == expected
    if expected[0] != "non_revenue":
        assert records[0].revenue_canonical_entity != ROOK


def test_the_customers_beside_rook_bristol_s_funding_stay_verified():
    records = _rook_records("BMO Bank of Montreal", "ROOK BRISTOL FI")
    assert [record.revenue_tier for record in records[1:]] == ["verified", "verified"]


def test_the_cut_is_a_ledger_alias_read_on_both_sides():
    assert registry.LENDER_ALIASES[ROOK] == ("ROOK BRISTOL FINANCIAL", "ROOK BRISTOL FI")
    assert "ROOK BRISTOL FI" not in registry.CREDIT_ONLY_ALIASES
    assert registry_match("ROOK BRISTOL FITNESS", registry.LENDER_ALIASES) is None
    assert registry_match("ROOK BRISTOL FI MSP DIV", registry.LENDER_ALIASES) == (ROOK, "ROOK BRISTOL FI")


# --- Audit round 2, R2-B03 (R43): Liberis, an embedded revenue-based financing provider -----------------------------
# Liberis US Inc buys merchants' future card receivables through white-label platform programmes (Vagaro Capital among
# them) and pays US fundings through Airwallex US, LLC; it is repaid from the merchant's sales before the platform
# pays out, so no debit names it. Its fundings are financing proceeds (an alternative position, Parafin's precedent).

LIBERIS = "Liberis US Inc"
LIBERIS_FILL = [("NORTHWIND MERCH SVCS ACH In", 1500.0), ("NORTHWIND MERCH SVCS ACH In", 1700.0)]
LIBERIS_CHASE = ("ORIG CO NAME:LIBERIS US INC ORIG ID:1234567890 DESC DATE: CO ENTRY DESCR:PAYMENT SEC:CCD TRACE#:1 "
                 "EED:540305 IND ID:1234 IND NAME:NORTHWIND LABS INC TRN: 1")


@pytest.mark.parametrize(("bank", "text", "amount"), [
    ("Mercury", "Liberis AB12CDEF ACH In", 4000.0),
    ("Wells Fargo", "Instant Pmt From Airwallex US, LLC-Liberis US Inc on 03/05 Ref# AB12CDEF34", 5000.0),
    ("Chase", LIBERIS_CHASE, 3000.0),
], ids=["mercury", "airwallex-instant-payment", "chase-originator"])
def test_a_liberis_funding_is_its_financing_proceeds(bank, text, amount):
    funding = _records([(text, amount), *LIBERIS_FILL], bank=bank)[0]
    assert (funding.revenue_tier, funding.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")
    assert funding.revenue_canonical_entity == LIBERIS
    assert funding.contributes_to_lender_credit_exclusion


def test_a_liberis_debit_is_an_alternative_position():
    [record] = _records([("Liberis AB12CDEF ACH Out", -900.0)], bank="Mercury")
    assert (record.classification, record.canonical_entity) == ("alternative_position", LIBERIS)


@pytest.mark.parametrize(("bank", "text", "expected"), [
    # Airwallex pays many senders: another sender's instant payment keeps its reading; a payer whose name only starts
    # like Liberis is no funder.
    ("Wells Fargo", "Instant Pmt From Airwallex US, LLC-Contoso Supply LLC on 03/05 Ref# AB12CDEF34",
     ("counted_flagged", "p2p")),
    ("Mercury", "Liberty Fabrikam AB12CDEF ACH In", ("counted_flagged", "named_payer_one_off")),
    # The platform whose capital programme Liberis powers keeps its own payouts' reading (the merchant's sales).
    ("Mercury", "Vagaro Merchant ACH In", ("counted_flagged", "platform_unconfirmed")),
], ids=["airwallex-other-sender", "liberty-lookalike", "vagaro-payout"])
def test_liberis_s_aliases_read_no_other_payer(bank, text, expected):
    records = _records([(text, 2000.0)], bank=bank)
    assert _tier(records[0]) == expected
    assert records[0].revenue_canonical_entity != LIBERIS


def test_liberis_is_a_ledger_alias_and_airwallex_and_vagaro_are_not():
    assert registry.ALTERNATIVE_POSITION_ALIASES[LIBERIS] == ("LIBERIS", "LIBERIS US INC")
    assert registry_match("INSTANT PMT FROM AIRWALLEX US LLC CONTOSO", registry.ALTERNATIVE_POSITION_ALIASES) is None
    assert registry_match("VAGARO MERCHANT ACH IN", registry.ALTERNATIVE_POSITION_ALIASES) is None
    assert registry_match("LIBERTY FABRIKAM ACH IN", registry.ALTERNATIVE_POSITION_ALIASES) is None


def test_r3_50_a_holder_named_liberis_is_read_as_liberis_a_recorded_residual():
    """Audit round 3, R3-B01 (R3-50): the RECORDED residual of the bare LIBERIS alias (true revenue spec §17.1, §20; the
    ledger's Liberis notes). LIBERIS is the company's name and also a rare surname, and the matcher reads the whole row,
    receiver fields included, so another originator's payment to a holder named '... LIBERIS ...' is read as Liberis US
    Inc's financing proceeds. No corpus row prints it. This pins today's reading for the owner: a future narrowing (the
    bare word read only outside the receiver fields, or only in the Mercury 'LIBERIS <ref> ACH IN' form) is a deliberate
    change, made by changing this test."""
    printed = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:LIBERIS SAMPLE LLC CO ID:0000000001 CCD"
    [record] = _records([(printed, 2000.0)], holder="LIBERIS SAMPLE LLC", bank="Bank of America")
    assert (record.revenue_classification, record.revenue_match_method, record.revenue_canonical_entity) == (
        "non_revenue", "financing_proceeds_credit", LIBERIS)

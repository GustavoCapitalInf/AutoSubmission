"""Audit fix batch B5 (true revenue spec §5.2, §8.1, §8.5 Q5, §20): the wire readers. A wire whose region prints only
a bank's or a layout's labels, or a lone glued reference, names no sender (I14: wire_no_sender, Q5); Columbia Bank's
'WIRE DEPOSIT WIRE IN <ref> ORG <sender>' and Navy Federal's 'BANK WIRE DEPOSIT' are incoming-wire labels, an
originator label on a loose-wire row is read, and a wire a bank originates on its own behalf is held on every wire row
(the orchestrator's ruling); U.S. Bank's 'WIRE CREDIT REF<n> <sending bank>' is a wire and its 'ORG=<sender>' names
the sender (I12's reader); Q5's repeat arm reads an LLC cut at the wire's 35-character originator field and glued to
the city as a company form (I61). Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "NORTHWIND LABS INC"


def _records(rows, *, holder: str | None = HOLDER, bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ]))


def _tiers(rows, **kwargs):
    return [(record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method)
            for record in _records(rows, **kwargs) if record.amount > 0]


NO_SENDER = ("excluded_pending_review", "wire_no_sender")
NAMED = ("counted_flagged", "wire_named_sender")
FINANCING = ("excluded_pending_review", "financing_named_payer")
HOLDER_HELD = ("excluded_pending_review", "holder_name")
REPEAT_WIRE = ("verified", "repeat_wire_sender")


# I14: label-only regions and glued references name no sender.

def test_navy_federal_bank_wire_deposit_is_a_wire_with_no_sender():
    rows = [("BANK WIRE DEPOSIT", 4000.0), ("BANK WIRE DEPOSIT", 6000.0)]
    assert _tiers(rows, bank="Navy Federal Credit Union") == [NO_SENDER, NO_SENDER]


def test_navy_federal_bank_wire_deposit_is_an_incoming_wire_label_and_never_a_bank_s_own_wire():
    text = "BANK WIRE DEPOSIT"
    assert tc._is_wire_row(text)
    assert tc.payer_region(text) == ""
    assert not tr._bank_originated_wire(text, "BANK WIRE DEPOSIT", wire=True)


def test_td_glued_reference_wire_names_no_sender():
    assert _tiers([("123456S1234567WIRE", 2500.0)], bank="TD Canada Trust") == [NO_SENDER]


def test_incoming_wire_reference_only_stays_held():
    assert _tiers([("INCOMING WIRE 1234567890", 2500.0)]) == [NO_SENDER]


@pytest.mark.parametrize("text", [
    "RECEIVED WIRE DEPOSIT",
    "DEP WIRE IN",
    "BANK WIRE",
    "INCOMING BANK WIRE 1234567",
    "WIRE DEPOSIT 12345678",
])
def test_a_loose_wire_that_prints_only_layout_labels_names_no_sender(text):
    assert _tiers([(text, 2500.0)]) == [NO_SENDER]


def test_falcon_international_iwt_reads_the_sender_its_reader_now_keeps():
    # Audit B10 (I14): the community platform's reader keeps the sender Falcon prints after the amount, behind the
    # bank's own wire field ('Falcon Internati Wires'), and IWT is an incoming-wire label: the sender is read after
    # the field, and a row that prints no sender names none (Q5's hold, as for every other label).
    assert _tiers([("INTERNATIONAL IWT FALCON INTERNATI WIRES CONTOSO TRADING SA", 2500.0)],
                  bank="falconbank.com") == [NAMED]
    assert _tiers([("INTERNATIONAL IWT", 2500.0)], bank="falconbank.com") == [NO_SENDER]


def test_a_named_sender_glued_to_wire_stays_named():
    assert _tiers([("CONTOSO PAVING LLC WIRE", 2500.0)], bank="Mercury") == [NAMED]


# I14 / I23: a bank that wires on its own behalf is held on the loose-wire layouts too.

def test_a_bank_s_own_wire_in_the_sender_wire_layout_is_held_as_financing():
    assert _tiers([("FABRIKAM BANK N A WIRE", 50000.0)], bank="Mercury") == [FINANCING]


def test_a_company_named_for_a_bank_word_wiring_in_that_layout_stays_named():
    assert _tiers([("LEFT BANK BAKERY LLC WIRE", 2500.0)], bank="Mercury") == [NAMED]


# I14: Columbia Bank's WIRE DEPOSIT WIRE IN reads the sender after ORG.

COLUMBIA = "WIRE DEPOSIT WIRE IN 1234567890123456 ORG {sender}"


def test_columbia_wire_deposit_wire_in_is_an_incoming_wire_label():
    text = COLUMBIA.format(sender="CONTOSO PAVING LLC")
    assert tc._is_wire_row(text)
    assert tc.payer_region(text) == "CONTOSO PAVING LLC"


@pytest.mark.parametrize(("sender", "expected"), [
    ("CONTOSO PAVING LLC", NAMED),
    ("NORTHWIND LABS INC", HOLDER_HELD),
    ("FABRIKAM CAPITAL FUNDING LLC", FINANCING),
    ("SAMPLE NATIONAL BANK PLC", FINANCING),
])
def test_columbia_reads_the_org_sender_for_every_hold(sender, expected):
    assert _tiers([(COLUMBIA.format(sender=sender), 10000.0)], bank="columbiabankonline.com") == [expected]


def test_columbia_without_org_reads_the_sender_after_its_label():
    assert tc.payer_region("WIRE DEPOSIT WIRE IN 1234567890123456 CONTOSO PAVING LLC") == "CONTOSO PAVING LLC"


def test_columbia_company_wiring_twice_verifies_by_q5():
    rows = [(COLUMBIA.format(sender="CONTOSO PAVING LLC"), 10000.0),
            (COLUMBIA.format(sender="CONTOSO PAVING LLC"), 12000.0)]
    assert _tiers(rows, bank="columbiabankonline.com") == [REPEAT_WIRE, REPEAT_WIRE]


# I14: an originator label on a loose-wire row (no incoming-wire label starts it) names the sender.

@pytest.mark.parametrize(("sender", "expected"), [
    ("CONTOSO PAVING LLC", NAMED),
    ("NORTHWIND LABS INC", HOLDER_HELD),
    ("FABRIKAM CAPITAL FUNDING LLC", FINANCING),
])
def test_a_loose_wire_s_originator_label_names_its_sender(sender, expected):
    text = f"DEPOSIT WIRE IN 1234 ORG {sender}"
    assert not tc._is_wire_row(text)
    assert tc.payer_region(text) == sender
    assert _tiers([(text, 5000.0)]) == [expected]


# I12's reader: U.S. Bank's WIRE CREDIT REF layout.

def test_us_bank_wire_credit_with_no_org_line_stays_a_wire_with_no_sender():
    text = "WIRE CREDIT REF001234 SAMPLE BANK NYC 260302B1234"
    assert tc._is_wire_row(text)
    assert _tiers([(text, 18000.0)], bank="U.S. Bank") == [NO_SENDER]


def test_us_bank_wire_credit_reads_the_org_sender_when_printed():
    text = "WIRE CREDIT REF001234 JPMCHASE NYC 1 ORG FABRIKAM SUPPLY INC"
    assert tc.payer_region(text) == "FABRIKAM SUPPLY INC"
    assert _tiers([(text, 18000.0)], bank="U.S. Bank") == [NAMED]


def test_us_bank_wire_credit_from_a_funder_is_held():
    text = "WIRE CREDIT REF001234 JPMCHASE NYC 1 ORG FABRIKAM CAPITAL FUNDING LLC"
    assert _tiers([(text, 18000.0)], bank="U.S. Bank") == [FINANCING]


# I61: an LLC cut at the 35-character originator field and glued to the city counts for Q5's repeat arm only.

def _chips(name: str) -> str:
    return f"CHIPS CREDIT VIA SAMPLE BANK N A 1234 B O {name} 12345 REF NBNF NORTHWIND LABS INC"


CUT_NAME = "CONTOSO HOME SERVICES MANAGEMENT LLMIAMI FL"


def test_the_cut_name_fills_the_originator_field():
    assert len("CONTOSO HOME SERVICES MANAGEMENT LL") == 35


def test_a_company_whose_llc_the_field_cuts_verifies_when_it_wires_twice():
    rows = [(_chips(CUT_NAME), 7500.0), (_chips(CUT_NAME), 8000.0)]
    assert _tiers(rows, bank="Chase") == [REPEAT_WIRE, REPEAT_WIRE]


def test_a_cut_legal_form_wiring_once_stays_counted():
    assert _tiers([(_chips(CUT_NAME), 7500.0)], bank="Chase") == [NAMED]


def test_a_cut_trade_word_stays_counted_however_often_it_wires():
    rows = [(_chips("NORTHWIND SER MIAMI FL"), 7500.0), (_chips("NORTHWIND SER MIAMI FL"), 8000.0)]
    assert _tiers(rows, holder="CONTOSO BAKERY LLC", bank="Chase") == [NAMED, NAMED]


@pytest.mark.parametrize("name", [
    "JOHN LLOYD MIAMI FL",
    "CONTOSO LLAMA RANCH MIAMI FL",
])
def test_a_name_word_starting_with_ll_before_the_field_end_is_no_cut_legal_form(name):
    rows = [(_chips(name), 7500.0), (_chips(name), 8000.0)]
    assert _tiers(rows, bank="Chase") == [NAMED, NAMED]


@pytest.mark.parametrize("region", [
    "CONTOSO HOME SERVICES MANAGEMENT LLMIAMI FL",
    # A name whose punctuation the normalizer dropped is a little shorter than the field.
    "CONTOSO HOME SERVICES MANAGEMEN LLMIAMI FL",
    "CONTOSO HOME SERVICE MANAGEMNT LLMIAMI",
])
def test_cut_legal_form_reader(region):
    assert tr._cut_wire_legal_form(region)


@pytest.mark.parametrize("region", [
    "JOHN LLOYD MIAMI FL",
    "LLMIAMI FL",
    "CONTOSO HOME MANAGEMENT LLMIAMI FL",
    "CONTOSO HOME SERVICES MANAGEMENT COMIAMI FL",
    "CONTOSO HOME SERVICES MANAGEMENT INMIAMI FL",
    "CONTOSO HOME SERVICES MANAGEMENT LIMIAMI FL",
    "CONTOSO HOME SERVICES MANAGEMENT LLC MIAMI FL",
])
def test_cut_legal_form_reader_negatives(region):
    assert not tr._cut_wire_legal_form(region)


def test_the_cut_legal_form_never_widens_q6_s_company_form():
    assert not tc.company_form("CONTOSO HOME SERVICES MANAGEMENT LLMIAMI FL")

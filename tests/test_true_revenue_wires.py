"""Audit fix batch B5 (true revenue spec §5.2, §8.1, §8.5 Q5, §20): the wire readers. A wire whose region prints only
a bank's or a layout's labels, or a lone glued reference, names no sender (I14: wire_no_sender, Q5); Columbia Bank's
'WIRE DEPOSIT WIRE IN <ref> ORG <sender>' and Navy Federal's 'BANK WIRE DEPOSIT' are incoming-wire labels, an
originator label on a loose-wire row is read, and a wire a bank originates on its own behalf is held on every wire row
(the orchestrator's ruling); U.S. Bank's 'WIRE CREDIT REF<n> <sending bank>' is a wire and its 'ORG=<sender>' names
the sender (I12's reader); Q5's repeat arm reads an LLC cut at the wire's 35-character originator field and glued to
the city as a company form (I61). Audit round 2, R2-B10: every wire layout word, and CR, is a label that names nobody,
and INCOMING FEDWIRE, INBOUND WIRE|FEDWIRE and INCOMING CHIPS are incoming-wire labels (R32); the plural WIRE
TRANSFERS label is a wire label and WIRE TRANSFER IN reads the sender after it (R21 part C); a loose-wire originator
label is read only after the row's first WIRE word, never inside the sender's own name before a row-final WIRE (R26);
a funds-transfer wire label that prints only a reference is a wire with no sender (R11's cross-card rows). Fabricated
rows only, in the banks' printed formats."""
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


# Audit round 2, R2-B10 (R32): a wire that prints only Fedwire, CHIPS, inbound or credit labels names no sender (Q5),
# and INCOMING FEDWIRE, INBOUND WIRE|FEDWIRE and INCOMING CHIPS are incoming-wire labels whose sender Q5 reads.

@pytest.mark.parametrize("text", [
    "INCOMING FEDWIRE",
    "INCOMING FEDWIRE 123456",
    "FEDWIRE IN",
    "FEDWIRE INCOMING",
    "FEDWIRE DEPOSIT",
    "FEDWIRE DEP",
    "FEDWIRE CR",
    "FEDWIRE",
    "FEDWIRE RECEIVED",
    "INCOMING FEDWIRE CR",
    "INBOUND WIRE",
    "INBOUND WIRE 123456",
    "INBOUND WIRE CR",
    "INBOUND FEDWIRE",
    "INBOUND INTERNATIONAL WIRE",
    "INCOMING CHIPS",
])
def test_r32_a_wire_that_prints_only_its_labels_is_held_with_no_sender(text):
    assert _tiers([(text, 5000.0)]) == [NO_SENDER]


def test_r32_the_label_words_are_every_wire_layout_word_and_cr():
    assert tr._WIRE_LAYOUT_WORDS <= tr._WIRE_LABEL_ONLY_WORDS
    assert tr._BARE_CHANNEL_WORDS <= tr._WIRE_LABEL_ONLY_WORDS
    assert {"BANK", "DEPOSIT", "DEP", "IN", "RECEIVED", "CR"} <= tr._WIRE_LABEL_ONLY_WORDS


@pytest.mark.parametrize("text", [
    "INCOMING FEDWIRE ORG CONTOSO BUILDERS LLC",
    "INBOUND WIRE FROM CONTOSO BUILDERS LLC",
    "INBOUND FEDWIRE ORG CONTOSO BUILDERS LLC",
    "INCOMING CHIPS ORG FABRIKAM TRADING LLC",
])
def test_r32_a_company_wiring_twice_after_the_new_labels_verifies(text):
    assert tc._is_wire_row(text)
    assert _tiers([(text, 5000.0), (text, 5000.0)]) == [REPEAT_WIRE, REPEAT_WIRE]


def test_r32_a_bank_wiring_on_its_own_behalf_after_the_new_label_is_held_as_financing():
    assert _tiers([("INCOMING FEDWIRE ORG SAMPLE BANK N A", 5000.0)]) == [FINANCING]


def test_r32_the_fedwire_transfer_label_now_reads_its_originator_as_a_wire_s():
    # The wanted side effect: the row was a person-to-person transfer (held as a round repeat), now a wire whose
    # originator Q5 reads.
    text = "INCOMING FEDWIRE TRANSFER ORG CONTOSO BUILDERS LLC"
    assert tc.payer_region(text) == "CONTOSO BUILDERS LLC"
    assert _tiers([(text, 5000.0), (text, 5000.0)]) == [REPEAT_WIRE, REPEAT_WIRE]


@pytest.mark.parametrize("text", [
    "FEDWIRE CREDIT ORG CONTOSO BUILDERS LLC",
    "INCOMING WIRE ORG CONTOSO FEDWIRE SERVICES LLC",
])
def test_r32_controls_a_named_sender_still_verifies_on_repeat(text):
    assert _tiers([(text, 5000.0), (text, 5000.0)]) == [REPEAT_WIRE, REPEAT_WIRE]


def test_r32_control_huntington_s_bare_fedwire_transfer_stays_held_and_class_other():
    [record] = _records([("INCOMING FEDWIRE TRANSFER", 5000.0)], bank="Huntington National Bank")
    assert (record.revenue_tier, record.revenue_tier_reason) == NO_SENDER
    assert record.classification == "other"
    assert tc.payer_region("INCOMING FEDWIRE TRANSFER") == ""


def test_r32_controls_bank_wire_deposit_and_the_holder_s_own_fedwire():
    assert _tiers([("BANK WIRE DEPOSIT", 5000.0)]) == [NO_SENDER]
    assert _tiers([("FEDWIRE CREDIT VIA SAMPLE BANK B O NORTHWIND LABS INC", 5000.0)]) == [HOLDER_HELD]


@pytest.mark.parametrize("text", [
    # The recorded residual (audit round 3, R3-B07 narrows it to the old labels with no FROM: FEDWIRE CREDIT, CHIPS
    # CREDIT, WIRE IN, DOMESTIC WIRE, a bare INCOMING WIRE <name>, U.S. Bank's WIRE CREDIT REF<n>): a sender printed
    # straight after them is not read; their corpus rows print an originator label or the sending bank there.
    "INCOMING WIRE CONTOSO BUILDERS LLC",
    "FEDWIRE CREDIT CONTOSO BUILDERS LLC",
])
def test_r32_recorded_residual_a_sender_after_an_old_label_with_no_from_is_not_read(text):
    assert _tiers([(text, 4000.0)]) == [NO_SENDER]


def test_r32_control_chips_alone_is_no_wire_label():
    assert not tc._is_wire_row("CHIPS")
    assert _tiers([("CHIPS", 5000.0)]) == [("counted_flagged", "named_payer_unlabelled")]


def test_r32_control_debits_keep_their_reading():
    records = _records([("OUTGOING FEDWIRE TRANSFER", -5000.0), ("INBOUND WIRE FEE", -15.0),
                        ("CONTOSO SUPPLY LLC", 10.0)])
    assert [(record.classification, record.revenue_tier) for record in records[:2]] == [("other", None), ("fee", None)]
    assert not tc._is_wire_row("OUTGOING FEDWIRE TRANSFER")


# Audit round 2, R2-B10 (R21 part C): the plural WIRE TRANSFERS label is a wire label, and WIRE TRANSFER IN reads the
# sender printed after it (TRANSFERS stays transfer wording on any other row).

def test_r21_three_plural_wire_transfers_from_one_company_verify():
    rows = [(f"WIRE TRANSFERS FROM FABRIKAM TRADING LLC REF {n}", 5000.0) for n in (1, 2, 3)]
    assert tc._is_wire_row(rows[0][0])
    assert tc.payer_region(rows[0][0]) == "FABRIKAM TRADING LLC"
    assert _tiers(rows) == [REPEAT_WIRE] * 3


def test_r21_plural_wire_transfers_incoming_verify_on_repeat():
    assert _tiers([("WIRE TRANSFERS INCOMING SAMPLE PARTS INC", 5000.0)] * 2) == [REPEAT_WIRE] * 2


def test_r21_wire_transfer_in_reads_the_sender_printed_after_it():
    rows = [(f"WIRE TRANSFER IN CONTOSO SUPPLY LLC REF {n}", 5000.0) for n in (1, 2)]
    assert tc.payer_region(rows[0][0]) == "CONTOSO SUPPLY LLC"
    assert _tiers(rows) == [REPEAT_WIRE] * 2


@pytest.mark.parametrize(("text", "expected"), [
    ("WIRE TRANSFER IN", NO_SENDER),
    ("WIRE TRANSFERS IN", NO_SENDER),
    ("WIRE TRANSFER IN 1234", NO_SENDER),
    ("WIRE TRANSFER IN WIRE FROM FABRIKAM INC", NAMED),
    ("WIRE TRANSFER IN SAMPLE FUNDING LLC", FINANCING),
    ("EXTERNAL DEPOSIT ACH TRANSFERS PAYMENT", ("excluded_pending_review", "transfer_no_counterparty")),
])
def test_r21_wire_transfer_label_controls(text, expected):
    assert _tiers([(text, 5000.0)]) == [expected]


def test_r21_control_a_loan_s_transfers_stay_non_revenue_and_transfers_stays_transfer_wording():
    [(tier, _reason)] = _tiers([("SAMPLE LOAN TRANSFERS", 5000.0)])
    assert tier == "non_revenue"
    assert tc._TRANSFER_WORDING.search("EXTERNAL DEPOSIT ACH TRANSFERS PAYMENT")


# Audit round 2, R2-B10 (R26): a loose-wire originator label is read only after the row's first WIRE word, so a label
# word inside the sender's own name before a row-final WIRE (Mercury's, Brex's '<sender> WIRE') never cuts it.

@pytest.mark.parametrize(("text", "holder", "bank"), [
    ("CONTOSO ORG LLC WIRE", "CONTOSO ORG LLC", "Mercury"),
    ("CONTOSO ORG LLC WIRE", "CONTOSO ORG LLC", "Brex"),
    ("CONTOSO ORG LLC WIRE", "CONTOSO ORG LLC DBA SAMPLE GRILL", "Mercury"),
    ("CONTOSO ORIG FOODS LLC WIRE", "CONTOSO ORIG FOODS LLC", "Mercury"),
    ("ORIGINATOR MEDIA LLC WIRE", "ORIGINATOR MEDIA LLC", "Mercury"),
    ("CONTOSO FOODS ORG WIRE", "CONTOSO FOODS ORG", "Mercury"),
])
def test_r26_a_holder_whose_name_prints_an_originator_word_is_held(text, holder, bank):
    assert not tc._loose_wire_originator(text)
    assert _tiers([(text, 2500.0)], holder=holder, bank=bank) == [HOLDER_HELD]


@pytest.mark.parametrize("text", ["CONTOSO ORG WIRE", "CONTOSO ORIG WIRE", "CONTOSO.ORG WIRE"])
def test_r26_a_sender_whose_name_ends_in_an_originator_word_is_counted(text):
    assert _tiers([(text, 2500.0)], bank="Mercury") == [NAMED]


@pytest.mark.parametrize("text", ["FABRIKAM CAPITAL ORG LLC WIRE", "CONTOSO ADVANCE ORIG INC WIRE"])
def test_r26_a_funder_whose_financing_word_precedes_the_originator_word_is_held(text):
    assert _tiers([(text, 2500.0)], bank="Mercury") == [FINANCING]


def test_r26_the_payer_region_of_a_sender_wire_row_keeps_the_whole_name():
    assert tc.payer_region("SAMPLE ORG SOLUTIONS LLC WIRE") == "SAMPLE ORG SOLUTIONS LLC WIRE"


def test_r26_a_loose_label_after_the_wire_word_is_still_read_from_its_own_position():
    text = "CONTOSO ORG DEPOSIT WIRE IN 1234 ORG FABRIKAM PAVING LLC"
    label = tc._loose_wire_label(text)
    assert label is not None and text[label.start():].startswith("ORG FABRIKAM")
    assert tc.payer_region(text) == "FABRIKAM PAVING LLC"
    assert _tiers([(text, 2500.0)], bank="Mercury") == [NAMED]


@pytest.mark.parametrize("text", [
    "CONTOSO ORG LLC WIRE",
    "B O B PAVING LLC WIRE",
    "ORIGINATOR MEDIA LLC WIRE",
])
def test_r26_a_label_before_the_row_s_first_wire_word_is_never_a_loose_label(text):
    assert tc._loose_wire_label(text) is None


@pytest.mark.parametrize(("text", "holder", "bank", "expected"), [
    ("B O B PAVING LLC WIRE", "B O B PAVING LLC", "Mercury", HOLDER_HELD),
    ("CONTOSO CAPITAL LLC WIRE", HOLDER, "Mercury", FINANCING),
    ("ONDECK CAPITAL ORG LLC WIRE", HOLDER, "Mercury", ("non_revenue", "financing_proceeds_credit")),
    ("FABRIKAM BANK N A WIRE", HOLDER, "Mercury", FINANCING),
    ("WIRE REVERSAL B O CONTOSO PAVING LLC", HOLDER, "Chase", ("non_revenue", "reversal_cancellation_exclusion")),
])
def test_r26_controls_keep_their_reading(text, holder, bank, expected):
    assert _tiers([(text, 2500.0)], holder=holder, bank=bank) == [expected]


def test_r26_control_a_sender_wire_row_never_verifies_on_repeat():
    assert _tiers([("FABRIKAM SOLUTIONS LLC WIRE", 2500.0)] * 2, bank="Mercury") == [NAMED, NAMED]


def test_r26_control_the_chase_reversal_still_reads_its_b_o_sender():
    assert tc._loose_wire_originator("WIRE REVERSAL B O CONTOSO PAVING LLC")
    assert tc.payer_region("WIRE REVERSAL B O CONTOSO PAVING LLC") == "CONTOSO PAVING LLC"


# Audit round 2, R2-B10 (R11's cross-card rows): a bare incoming-wire label of the widened list reaches Q5's hold, never
# non_revenue.

@pytest.mark.parametrize("text", ["WIRE TRANSFER IN 1234", "INCOMING FEDWIRE 1234", "INBOUND WIRE 1234"])
def test_r11_a_bare_incoming_wire_label_is_held_never_non_revenue(text):
    assert tc._bare_incoming_wire(text)
    assert _tiers([(text, 2500.0)], holder="FABRIKAM TRADING LTD", bank="Royal Bank of Canada") == [NO_SENDER]


# R2-B10 review round 1 (R11): a word after the label that is no reference and no wire label (a currency, generic,
# holder-noise or legal-form word) makes no bare incoming wire, so it never becomes the counted 'sender' of a wire.

@pytest.mark.parametrize(("text", "expected"), [
    # No funds-transfer label: the wire keeps its own reading, a wire with no sender.
    ("WIRE TRANSFER IN 1234 USD", NO_SENDER),
    ("INCOMING FEDWIRE 1234 BUSINESS", NO_SENDER),
    ("INBOUND WIRE 1234 PAYMENT", NO_SENDER),
    # A funds-transfer label: the row keeps its own-account reading, as before R11.
    ("FUNDS TRANSFER CREDIT TT 1234 BUSINESS", ("non_revenue", "strong_non_revenue_rule")),
    ("FUNDS TRANSFER WIRE FROM 1234 USD", ("non_revenue", "strong_non_revenue_rule")),
])
def test_r11_review_a_word_besides_a_reference_is_no_bare_incoming_wire(text, expected):
    assert not tc._bare_incoming_wire(text)
    assert _tiers([(text, 2500.0)], holder="FABRIKAM TRADING LTD", bank="Royal Bank of Canada") == [expected]


# Audit round 3, R3-B07 (R3-40; §8.5 Q5, the underwriter's Q1 of 2026-10-02: every wire with no sender is held): a
# wire whose region prints only label, holder-noise, account-designation, purpose, filler or legal-form words names no
# sender, on every wire layout and the labelled path; a numbered company keeps its reading.

@pytest.mark.parametrize("text", [
    "WIRE TRANSFER IN 1234 BUSINESS",
    "WIRE TRANSFER IN 1234 OPERATING",
    "WIRE TRANSFER IN 1234 TRUST",
    "WIRE TRANSFER IN 1234 SERVICES",
    "WIRE TRANSFER IN 1234 GROUP",
    "WIRE TRANSFER IN 1234 HOLDINGS",
    "WIRE TRANSFER IN 1234 RENT",
    "WIRE TRANSFER IN BUSINESS",
    "WIRE TRANSFERS IN 1234 BUSINESS",
    "WIRE TRANSFER IN THE AMOUNT OF 1234",
    "WIRE TRANSFER FROM 1234 OPERATING",
    "WIRE TRANSFER FROM BUSINESS ACCOUNT",
    "WIRE TRANSFER FROM BUSINESS CHECKING 1234",
    "WIRE TRANSFER INCOMING BUSINESS",
    "WIRE TRANSFER DEPOSIT OPERATING 1234",
    "INCOMING WIRE 1234 BUSINESS",
    "DOMESTIC WIRE DEPOSIT WIRE IN TRUST",
    "INCOMING WIRE TRANSFER BUSINESS WIRE PAYMENT",
    # The labelled path: the originator label's region holds only the designation.
    "WIRE FROM 1234 BUSINESS",
    "WIRE FROM BUSINESS ACCOUNT",
])
def test_r3_40_a_wire_that_prints_only_a_designation_word_names_no_sender(text):
    assert _tiers([(text, 2345.67)]) == [NO_SENDER]


@pytest.mark.parametrize("text", ["WIRE TRANSFER IN 1234 BUSINESS LLC", "INCOMING WIRE 1234 OPERATING LLC"])
def test_r3_40_a_designation_word_with_a_legal_form_never_verifies_as_a_repeat_sender(text):
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [NO_SENDER, NO_SENDER]


def test_r3_40_a_designation_word_wire_carries_the_funding_aid():
    from datetime import date, timedelta

    debit = "ACH DEBIT SAMPLE FUNDING LLC 1234567"
    days, day = [], date(2054, 3, 2)
    while len(days) < 12:
        day += timedelta(days=1)
        if day.weekday() < 5:
            days.append(day)
    transactions = [Transaction(date="2054-03-02", description="WIRE TRANSFER IN 1234 BUSINESS", amount=25000.0,
                                direction="credit")]
    transactions += [Transaction(date=day.isoformat(), description=debit, amount=-399.0, direction="debit")
                     for day in days]
    records = classify_statement_transactions(Statement(account_name=HOLDER, bank="Fifth Third Bank",
                                                        period_start="2054-03-01", period_end="2054-03-31",
                                                        transactions=transactions))
    wire = records[0]
    assert (wire.revenue_tier, wire.revenue_tier_reason) == NO_SENDER
    assert [series.amount for series in wire.revenue_funding_series] == [399.0]


@pytest.mark.parametrize("text", [
    "WIRE TRANSFER IN 1234 CONTOSO BUILDERS LLC",
    "WIRE FROM 1234 CONTOSO BUILDERS LLC",
])
def test_r3_40_control_a_named_sender_after_the_label_counts_and_verifies_on_repeat(text):
    assert _tiers([(text, 2345.67)]) == [NAMED]
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [REPEAT_WIRE, REPEAT_WIRE]


def test_r3_40_control_a_numbered_company_keeps_its_reading():
    text = "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA 1234567 ONTARIO INC"
    # OQ3: a numbered company is counted, never verified.
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [NAMED, NAMED]
    assert not tr._wire_names_nobody("1234567 B C LTD")
    assert not tr._wire_names_nobody("1234567 ONTARIO INC")


@pytest.mark.parametrize(("text", "expected"), [
    # A word a non-sale hold reads keeps that hold.
    ("WIRE TRANSFER IN 1234 INTEREST", ("excluded_pending_review", "non_sale_purpose")),
    # A funds-transfer label keeps its own-account reading (R2-B10 R11).
    ("FUNDS TRANSFER CREDIT TT 1234 BUSINESS", ("non_revenue", "strong_non_revenue_rule")),
])
def test_r3_40_controls_other_readings_keep_theirs(text, expected):
    assert _tiers([(text, 2345.67)]) == [expected]


def test_r3_40_control_a_holder_named_for_a_designation_word_holds_the_wire_with_no_sender():
    assert _tiers([("WIRE TRANSFER IN 1234 BUSINESS", 2345.67)], holder="NORTHWIND BUSINESS SERVICES LLC") == [
        NO_SENDER]


def test_r3_40_the_designation_words_are_the_brief_s_list_never_a_place_or_a_non_sale_word():
    words = tr._wire_designation_words()
    assert tc.REVENUE_GENERIC_WORDS <= words
    assert {"BUSINESS", "OPERATING", "CHECKING", "TRUST", "GROUP", "SERVICES", "AMOUNT", "RENT", "THE", "LLC",
            "INC", "LTD", "PLC"} <= words
    assert not {"INTEREST", "ONTARIO", "CANADA", "USA", "AMERICA", "AMERICAN", "NATIONAL", "QUEBEC"} & words


# Audit round 3, final review (R3-FF), F4 (§8.5 Q5; Q5 of 2026-09-28: a wire with a named sender is counted): a company
# named only with R3-40's product and holder-noise words ('PREMIUM SOLUTIONS LLC') read as naming nobody, so its wire
# was held as "Wire, no sender printed". Its name now reads where the row prints it behind an originator label or ends
# it with a legal form, and holds no account-designation, purpose or label word; every R3-40 pin above still names
# nobody.

FF_GENERIC_COMPANIES = ("PREMIUM SOLUTIONS LLC", "TOTAL SERVICES INC", "ELITE MANAGEMENT GROUP LLC",
                        "ADVANTAGE GROUP LLC", "SELECT HOLDINGS LLC", "COMMERCIAL SERVICES INC")


@pytest.mark.parametrize("name", FF_GENERIC_COMPANIES)
@pytest.mark.parametrize("shape", ["WIRE TRANSFER IN {}", "INCOMING WIRE ORG {} REF 12345"])
def test_ff_f4_a_company_named_with_generic_words_is_a_named_sender(shape, name):
    text = shape.format(name)
    assert _tiers([(text, 12000.0)]) == [NAMED]
    assert not tr._wire_names_nobody(name, labelled="ORG" in text)


@pytest.mark.parametrize("text", [
    # Behind an originator label, a name of those words needs no legal form.
    "INCOMING WIRE ORG PREMIUM SOLUTIONS REF 12345",
    "WIRE FROM ELITE MANAGEMENT GROUP",
    "INCOMING WIRE ORG THE ADVANTAGE GROUP REF 12345",
])
def test_ff_f4_behind_an_originator_label_the_name_needs_no_legal_form(text):
    assert _tiers([(text, 12000.0)]) == [NAMED]


@pytest.mark.parametrize("text", [
    # No originator label and no legal form: R3-40's single holder-noise words stay nobody.
    "WIRE TRANSFER IN 1234 SERVICES",
    "WIRE TRANSFER IN SELECT HOLDINGS",
    # An account-designation, purpose or holder-noise designation word keeps R3-40's reading, a legal form or a label
    # beside it or not.
    "WIRE TRANSFER IN 1234 BUSINESS LLC",
    "WIRE FROM BUSINESS ACCOUNT",
    "INCOMING WIRE ORG BUSINESS LLC REF 12345",
    "INCOMING WIRE ORG OPERATING ACCOUNT REF 12345",
    "INCOMING WIRE ORG PREMIUM BUSINESS CHECKING REF 12345",
    "WIRE TRANSFER IN TOTAL BUSINESS SERVICES LLC",
    "WIRE TRANSFER IN 1234 TRUST INC",
    "WIRE TRANSFER IN THE AMOUNT OF 1234",
    # A legal form alone, or with connecting words alone, names nobody.
    "INCOMING WIRE ORG LLC REF 12345",
    "WIRE TRANSFER IN THE LLC",
])
def test_ff_f4_controls_designations_and_lone_forms_still_name_nobody(text):
    assert _tiers([(text, 12000.0)]) == [NO_SENDER]


@pytest.mark.parametrize("holder", ["SELECT HOLDINGS LLC", "CONTOSO SELECT HOLDINGS LLC"])
@pytest.mark.parametrize("text", ["WIRE TRANSFER IN SELECT HOLDINGS LLC", "INCOMING WIRE ORG SELECT HOLDINGS LLC REF 1"])
def test_ff_f4_a_holder_named_with_those_words_keeps_its_wire_held(holder, text):
    """The holder test reads distinctive words, and these names are all its noise: a holder named with them would see
    its own money counted. Where the name's words are all words of the holder's name, the wire stays held, as at
    R3-40; another holder's reads the sender."""
    assert _tiers([(text, 12000.0)], holder=holder) == [NO_SENDER]
    assert _tiers([(text, 12000.0)], holder="CONTOSO PLUMBING LLC") == [NAMED]


def test_ff_f4_the_named_reading_is_q5_s_a_repeat_verifies_as_any_named_sender_s():
    text = "WIRE TRANSFER IN SELECT HOLDINGS LLC"
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [REPEAT_WIRE, REPEAT_WIRE]


def test_ff_f4_control_a_distinctive_name_reads_as_before():
    assert _tiers([("WIRE TRANSFER IN FABRIKAM SERVICES LLC", 12000.0)]) == [NAMED]
    assert _tiers([("INCOMING WIRE ORG FABRIKAM SERVICES LLC REF 12345", 12000.0)]) == [NAMED]


def test_ff_f4_the_name_words_are_r3_40_s_product_and_holder_noise_words_never_a_designation():
    names = tr._WIRE_COMPANY_NAME_WORDS
    assert names <= tr._WIRE_DESIGNATION_OWN_WORDS
    assert {"PREMIUM", "TOTAL", "ELITE", "ADVANTAGE", "SELECT", "COMMERCIAL", "GROUP", "HOLDINGS", "SERVICES",
            "SOLUTIONS", "MANAGEMENT", "ENTERPRISES"} <= names
    assert not {"BUSINESS", "OPERATING", "OPERATIONS", "CHECKING", "SAVINGS", "ACCOUNT", "ACCT", "MONEY", "MARKET",
                "TRUST", "DBA", "AMOUNT", "RENT", "THE", "OF", "AND", "LLC", "INC"} & names
    assert not names & (tc.REVENUE_GENERIC_WORDS | tr._WIRE_LABEL_ONLY_WORDS)


# Audit round 3, final review (R3-FF), review round 1 (findings 1 and 2; R3-40's verified claim; the underwriter's Q1 of
# 2026-10-02: a wire with no sender is held): a company's generic name needs two name words, one of them a holder-noise
# word (_WIRE_HOLDER_NOISE_NAME_WORDS). A lone holder-noise word beside a legal form or behind an originator label
# ('GROUP LLC', 'SERVICES INC', 'WIRE FROM <ref> SERVICES'), the shapes R3-40 fixed, and a region of account product
# words alone ('PLATINUM SELECT', 'ADVANTAGE PLUS LLC'), an account product's designation, keep R3-40's nobody reading,
# once and on a repeat (never Verified as repeat_wire_sender).

FF_R1_LONE_NOISE_WORD = (
    "WIRE TRANSFER IN 1234 GROUP LLC",
    "WIRE TRANSFER IN 1234 SERVICES INC",
    "WIRE TRANSFER IN SERVICES INC",
    "INCOMING WIRE 1234 GROUP LLC",
    "WIRE FROM 1234 SERVICES",
    "WIRE FROM 1234 GROUP",
    "WIRE FROM 1234 HOLDINGS",
    "WIRE FROM 1234 MANAGEMENT",
    "INCOMING WIRE ORG GROUP REF 1",
    "INCOMING WIRE ORG THE GROUP REF 1",
    "INCOMING WIRE B/O SOLUTIONS LLC REF 1",
)
FF_R1_PRODUCT_WORDS_ONLY = (
    "INCOMING WIRE ORG PLATINUM SELECT REF 1",
    "WIRE FROM ADVANTAGE PLUS",
    "WIRE FROM TOTAL",
    "WIRE TRANSFER IN FREE LLC",
    "WIRE TRANSFER IN SMALL CO",
    "INCOMING WIRE ORG ADVANTAGE PLUS LLC REF 1",
)


@pytest.mark.parametrize("text", FF_R1_LONE_NOISE_WORD + FF_R1_PRODUCT_WORDS_ONLY)
def test_ff_r1_a_lone_holder_noise_word_or_product_words_name_nobody_once_and_on_a_repeat(text):
    assert _tiers([(text, 12000.0)]) == [NO_SENDER]
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize("region", ["GROUP LLC", "SERVICES INC", "SERVICES", "THE GROUP", "GROUP GROUP LLC",
                                    "PLATINUM SELECT", "ADVANTAGE PLUS LLC", "TOTAL", "FREE LLC", "SMALL CO"])
def test_ff_r1_the_name_reader_needs_two_name_words_one_a_holder_noise_word(region):
    assert tr._wire_names_nobody(region, labelled=True)
    assert tr._wire_names_nobody(region, labelled=False)


@pytest.mark.parametrize("region", ["PREMIUM SOLUTIONS LLC", "ELITE GROUP", "THE ADVANTAGE GROUP"])
def test_ff_r1_control_two_name_words_with_a_holder_noise_word_still_name_a_company(region):
    # Re-pinned by audit round 4, R4-52: 'MANAGEMENT SERVICES LLC' (holder-noise words only, no product word) moved to
    # R4_52_NOISE_ONLY, which names no sender.
    assert not tr._wire_names_nobody(region, labelled=True)
    assert _tiers([(f"INCOMING WIRE ORG {region} REF 1", 12000.0)]) == [NAMED]


def test_ff_r1_the_holder_noise_name_words_are_r3_40_s():
    noise = tr._WIRE_HOLDER_NOISE_NAME_WORDS
    assert noise == {"GROUP", "HOLDINGS", "SERVICES", "SOLUTIONS", "MANAGEMENT", "ENTERPRISES"}
    assert noise <= tr._WIRE_COMPANY_NAME_WORDS


# Audit round 3, R3-B07 (R3-42; Q5 of 2026-09-28: a wire with a named sender is counted): a sender printed straight
# after R32's labels (INBOUND WIRE, INBOUND FEDWIRE, INCOMING FEDWIRE, INCOMING CHIPS, their TRANSFER FROM forms),
# 'INCOMING WIRE TRANSFER FROM' and the WIRE TRANSFER[S] CREDIT label is read.

@pytest.mark.parametrize("text", [
    "INBOUND WIRE CONTOSO BUILDERS LLC",
    "INBOUND WIRE TRANSFER FROM CONTOSO BUILDERS LLC",
    "INBOUND FEDWIRE CONTOSO BUILDERS LLC",
    "INCOMING FEDWIRE CONTOSO BUILDERS LLC",
    "INCOMING FEDWIRE TRANSFER FROM CONTOSO BUILDERS LLC",
    "INCOMING CHIPS CONTOSO BUILDERS LLC",
    "WIRE TRANSFERS CREDIT CONTOSO BUILDERS LLC",
    "WIRE TRANSFER CREDIT CONTOSO BUILDERS LLC",
    "INCOMING WIRE TRANSFER FROM CONTOSO BUILDERS LLC",
])
def test_r3_42_a_sender_printed_after_the_new_labels_is_read(text):
    assert tc.payer_region(text) == "CONTOSO BUILDERS LLC"
    assert _tiers([(text, 2345.67)]) == [NAMED]
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [REPEAT_WIRE, REPEAT_WIRE]


def test_r3_42_the_holder_s_own_name_after_a_new_label_is_held_as_the_holder_s():
    assert _tiers([("INBOUND WIRE NORTHWIND LABS INC", 2345.67)]) == [HOLDER_HELD]


@pytest.mark.parametrize(("text", "expected"), [
    # A funder the registry names stays financing proceeds; a bank by its own form, the bank-originated hold.
    ("INBOUND WIRE ONDECK CAPITAL", ("non_revenue", "financing_proceeds_credit")),
    ("INBOUND WIRE JPMORGAN CHASE BANK NA", FINANCING),
    # A listed sending bank's channel name names no sender.
    ("INBOUND WIRE WELLS FARGO", NO_SENDER),
    ("INCOMING FEDWIRE TRUIST 1234", NO_SENDER),
    # R3-40's guard: a designation word after the new label names no sender.
    ("INBOUND WIRE 1234 BUSINESS", NO_SENDER),
])
def test_r3_42_a_bank_or_a_designation_after_a_new_label(text, expected):
    record = _records([(text, 2345.67)])[0]
    assert (record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method) == expected


def test_r3_42_the_statement_s_own_bank_after_a_new_label_names_no_sender():
    assert _tiers([("INBOUND WIRE FABRIKAM BANK", 2345.67)], bank="Fabrikam Bank") == [NO_SENDER]
    # The same bank on another bank's statement is a bank by its form: the bank-originated hold.
    assert _tiers([("INBOUND WIRE FABRIKAM BANK", 2345.67)], bank="Contoso Bank") == [FINANCING]


def test_r3_42_control_an_originator_label_keeps_the_labelled_reading():
    text = "INCOMING FEDWIRE ORG CONTOSO BUILDERS LLC"
    assert tc.payer_region(text) == "CONTOSO BUILDERS LLC"
    assert _tiers([(text, 2345.67)]) == [NAMED]
    # Huntington's bare label reads its label word only, and no sender.
    assert tc._wire_sender_after_label("INCOMING FEDWIRE TRANSFER") == ""


# Audit round 4, R4-66 (§7.11; the owner's Q5 of 2026-09-28, standard A5): an originator's address printed as a house
# number, LN, a town, a state's code and a ZIP reads LN as a lane, so the named sender's wire is counted; a loan the
# row prints elsewhere (its OBI memo's LOAN PAYMENT) keeps it non_revenue. Holder CONTOSO REALTY LLC on Chase.
R4_66_FEDWIRE = ("FEDWIRE CREDIT VIA: SAMPLE BANK/011000000 B/O: FABRIKAM HOLDINGS {addr} UNITED STATES REF: CHASE "
                 "NYC/CTR/BNF=CONTOSO REALTY LLC SAMPLEVILLE OH 43000 US TRN: 1111111111FF{obi}")
R4_66_HOLDER = "CONTOSO REALTY LLC"


@pytest.mark.parametrize("addr", ["77 Ln Maple Grove MN 55311-0000", "4410 LN SAMPLETON IL 62701"])
def test_r4_66_a_named_sender_s_address_lane_counts_its_wire(addr):
    text = R4_66_FEDWIRE.format(addr=addr, obi="")
    [record] = _records([(text, 23456.78)], holder=R4_66_HOLDER, bank="Chase")
    assert (record.revenue_tier, record.revenue_tier_reason) == NAMED
    assert " LN " in record.normalized_description and " LOAN " not in record.normalized_description


def test_r4_66_control_a_loan_payment_memo_keeps_the_wire_non_revenue():
    text = R4_66_FEDWIRE.format(addr="77 Ln Maple Grove MN 55311-0000",
                                obi=" OBI=/URI/LOAN PAYMENT FROM FABRIKAM HOLDINGS")
    [record] = _records([(text, 23456.78)], holder=R4_66_HOLDER, bank="Chase")
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")
    assert "77 LN MAPLE GROVE MN" in record.normalized_description


def _read_as_printed_loan(rows, **kwargs):
    """R4-B13 review round 1 (finding 1): each row printing LN reads exactly as its twin printing LOAN, in every field
    but the printed description (the normalized description included)."""
    import dataclasses

    lane = _records(rows, **kwargs)
    spelled = _records([(text.replace(" LN ", " LOAN "), amount) for text, amount in rows], **kwargs)
    for record, twin in zip(lane, spelled, strict=True):
        fields = [field.name for field in dataclasses.fields(record) if field.name != "original_description"]
        assert {name: getattr(record, name) for name in fields} == {name: getattr(twin, name) for name in fields}
    return lane


def test_r4_66_controls_debits_keep_their_readings():
    [loan] = _records([("FABRIKAM BANK LN PMT 1234", -1234.56)], bank="Chase")
    assert loan.normalized_description == "FABRIKAM BANK LOAN PMT 1234"
    assert loan.classification == "potential_lender"
    # R4-B13 review round 1 (finding 1; the brief's G7 narrowing): the address arm reads only an address a wire's
    # originator label prints before it, so a debit printing '<n> LN <town> <ST> <ZIP>' with no such label does not
    # move at all: its normalized description keeps LOAN, and the financing-keyword review and every lender reading
    # are the base's.
    [lane] = _read_as_printed_loan([("ONLINE PAYMENT TO FABRIKAM SUPPLY 77 LN MAPLE GROVE MN 55311", -432.10)],
                                   bank="Chase")
    assert lane.normalized_description == "ONLINE PAYMENT TO FABRIKAM SUPPLY 77 LOAN MAPLE GROVE MN 55311"
    assert (lane.classification, lane.match_method) == ("other", "financing_keyword_review")
    # A lender-named debit keeps its potential-lender reading, alone and in a recurring series.
    text = "ACH DEBIT WOODGROVE LENDING 1234567 LN SAMPLETON OH 43000"
    [single] = _read_as_printed_loan([(text, -1234.56)], bank="Chase")
    assert (single.classification, single.canonical_entity, single.match_method, single.review_required) == (
        "potential_lender", "Unidentified lender obligation", "unidentified_loan_obligation", True)
    series = _read_as_printed_loan([(text, -1234.56)] * 4, bank="Chase")
    assert {(record.canonical_entity, record.match_method) for record in series} == {
        ("Unidentified lender obligation", "unidentified_loan_obligation")}


@pytest.mark.parametrize("text", [
    "ACH CREDIT WOODGROVE 1234567 LN SAMPLETON OH 43000",
    "WOODGROVE BANK 000123 LN PAYOFF IN 46201",
    "DEPOSIT 1234567 LN PROCEEDS SAMPLETON OH 43000",
])
def test_r4_b13_r1_an_unlabelled_address_shape_keeps_the_credit_s_loan(text):
    # R4-B13 review round 1 (finding 1): with no originator label before the number, the credit stays non_revenue on
    # the strong rule's LOAN, as at the base.
    [record] = _read_as_printed_loan([(text, 23456.78)], bank="Chase")
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


@pytest.mark.parametrize("addr", ["1234 LN PAYOFF IN 46201", "000123 LN INT DUE PA 19103",
                                  "1234567 LN ESCROW CO 80202", "1234 LN PRIN AND INT OH 43000"])
def test_r4_b13_r1_a_loan_purpose_word_after_a_labelled_ln_keeps_the_loan(addr):
    # R4-B13 review round 1 (finding 6): a loan-purpose word (R4-13's) after LN or among the town words keeps LOAN, on
    # an originator's address too.
    text = R4_66_FEDWIRE.format(addr=addr, obi="")
    [record] = _records([(text, 23456.78)], holder=R4_66_HOLDER, bank="Chase")
    assert " LOAN " in record.normalized_description and " LN " not in record.normalized_description
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


# Audit round 4, R4-14 (§8.5 Q5; the underwriter's Q1 of 2026-10-02 holds a wire with no sender): an account number and
# a province or country code printed after a wire's label name nobody; a numbered company (six to ten digits and its
# province, _NUMBERED_COMPANY_REGION) keeps its reading.

@pytest.mark.parametrize("text", [
    "WIRE TRANSFER FROM 000000000001 BC",
    "INCOMING WIRE 000000000001 ONTARIO NOTPROVIDED",
    "WIRE TRANSFER IN 000000000001 CANADA",
])
def test_r4_14_an_account_and_a_province_after_the_label_name_no_sender(text):
    assert _tiers([(text, 2345.67)]) == [NO_SENDER]
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize("text", [
    "INCOMING WIRE PAYMENT INCOMING WIRE PAYMENT CA 1234567 ONTARIO INC",
    "INCOMING WIRE 1234567 ONTARIO NOTPROVIDED",
])
def test_r4_14_controls_a_numbered_company_after_the_label_is_counted_never_verified(text):
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [NAMED, NAMED]
    assert tc.numbered_company(tc.revenue_text(tc.normalize_transaction_description(text)))


def test_r4_14_control_a_non_sale_word_keeps_its_hold():
    assert _tiers([("WIRE TRANSFER IN 1234 INTEREST", 2345.67)]) == [("excluded_pending_review", "non_sale_purpose")]


# Audit round 4, R4-52 (§8.5 Q5; R3-40's ruling under the underwriter's Q1 of 2026-10-02; standard B6): a generic
# company's name needs a product word (_WIRE_COMPANY_NAME_WORDS outside _WIRE_HOLDER_NOISE_NAME_WORDS); a name made
# only of holder-noise words, legal forms and connectors ('GROUP HOLDINGS LLC', the 'K GROUP HOLDINGS LLC' a dropped
# initial leaves) names no sender, once and on a repeat.
R4_52_BOFA = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:20540302001234 ORIG:{orig} ID:0001 SND BK:SAMPLE BANK "
              "ID:0002 PMT DET:SAMPLE {n}")
R4_52_NOISE_ONLY = (
    "WIRE TRANSFER IN 1234 GROUP HOLDINGS LLC",
    "WIRE TRANSFER IN 1234 SERVICES GROUP INC",
    "WIRE TRANSFER IN 1234 SOLUTIONS ENTERPRISES INC",
    "INCOMING WIRE ORG MANAGEMENT SERVICES LLC REF 1",
    "INCOMING WIRE ORG THE MANAGEMENT GROUP LLC REF 1",
    "INCOMING WIRE ORG HOLDINGS AND SERVICES CORP REF 1",
    "INCOMING WIRE ORG K GROUP HOLDINGS LLC REF 1",
)


@pytest.mark.parametrize("text", R4_52_NOISE_ONLY)
def test_r4_52_a_name_of_holder_noise_words_only_names_no_sender_once_and_on_a_repeat(text):
    assert _tiers([(text, 12000.0)]) == [NO_SENDER]
    assert _tiers([(text, 2345.67), (text, 3456.78)]) == [NO_SENDER, NO_SENDER]


def test_r4_52_the_bank_of_america_originator_layout_names_no_sender():
    rows = [(R4_52_BOFA.format(orig="GROUP HOLDINGS LLC", n=n), amount) for n, amount in ((1, 2345.67), (2, 3456.78))]
    assert _tiers(rows[:1], bank="Bank of America") == [NO_SENDER]
    assert _tiers(rows, bank="Bank of America") == [NO_SENDER, NO_SENDER]


def test_r4_52_a_noise_only_wire_carries_the_funding_aid():
    from datetime import date, timedelta

    debit = "ACH DEBIT SAMPLE FUNDING LLC 1234567"
    days, day = [], date(2054, 3, 2)
    while len(days) < 12:
        day += timedelta(days=1)
        if day.weekday() < 5:
            days.append(day)
    transactions = [Transaction(date="2054-03-02", description="WIRE TRANSFER IN 1234 GROUP HOLDINGS LLC",
                                amount=25000.0, direction="credit")]
    transactions += [Transaction(date=day.isoformat(), description=debit, amount=-399.0, direction="debit")
                     for day in days]
    records = classify_statement_transactions(Statement(account_name=HOLDER, bank="Fifth Third Bank",
                                                        period_start="2054-03-01", period_end="2054-03-31",
                                                        transactions=transactions))
    wire = records[0]
    assert (wire.revenue_tier, wire.revenue_tier_reason) == NO_SENDER
    assert [series.amount for series in wire.revenue_funding_series] == [399.0]


def test_r4_52_a_holder_sharing_some_noise_words_never_sees_the_noise_only_name_verified():
    text = "INCOMING WIRE ORG GROUP HOLDINGS LLC REF 1"
    assert _tiers([(text, 2345.67), (text, 3456.78)], holder="CONTOSO SERVICES GROUP LLC") == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize("region", ["GROUP HOLDINGS LLC", "SERVICES GROUP INC", "MANAGEMENT SERVICES LLC",
                                    "THE MANAGEMENT GROUP LLC", "HOLDINGS AND SERVICES CORP"])
def test_r4_52_the_name_reader_needs_a_product_word(region):
    words = tc.payer_name(region).split()
    assert not tr._wire_generic_company(words, True)
    assert not tr._wire_generic_company(words, False)
    assert tr._wire_names_nobody(region, labelled=True)


# Audit round 4, R4-53 (§8.5 Q5; R3-40's ruling, "on every wire layout and the labelled path", under the underwriter's
# Q1 of 2026-10-02): a labelled originator is read without its address, up to its first legal form or, for an account
# designation, without the town, state and country after it, so a designation-only originator printing its address
# names no sender. Holder NORTHWIND LABS INC on Chase.
R4_53_FEDWIRE = ("FEDWIRE CREDIT VIA: SAMPLE BANK/011000000 B/O: {orig} REF: CHASE NYC/CTR/BNF=NORTHWIND LABS INC "
                 "SAMPLEVILLE OH 43000 US TRN: 000000{n} IMAD: 0000")
R4_53_DESIGNATION_ADDRESSES = (
    "BUSINESS LLC SAMPLETON OH 43000 US",
    "GROUP LLC SAMPLETON OH 43000",
    "SERVICES INC MAPLE GROVE MN US",
    "OPERATING ACCOUNT MAPLE GROVE MN 55311",
    "BUSINESS CHECKING SAMPLETON OH",
    "GROUP HOLDINGS LLC SAMPLETON OH 43000",
    "BUSINESS LLC DENVER CO 80202",
)


def _r4_53(orig, times, *, template=R4_53_FEDWIRE):
    rows = [(template.format(orig=orig, n=n + 1), (2345.67, 3456.78)[n]) for n in range(times)]
    return _tiers(rows, bank="Chase")


@pytest.mark.parametrize("orig", R4_53_DESIGNATION_ADDRESSES)
def test_r4_53_a_designation_originator_with_its_address_names_no_sender(orig):
    assert _r4_53(orig, 1) == [NO_SENDER]
    assert _r4_53(orig, 2) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize("template", [
    "CHIPS CREDIT VIA: SAMPLE BANK/0001 B/O: {orig} REF: NBNF=NORTHWIND LABS INC /AC-000000000001 SSN: 000000{n}",
    "INCOMING WIRE ORG {orig} REF {n}",
])
def test_r4_53_the_chips_and_org_layouts_read_the_originator_without_its_address(template):
    assert _r4_53("BUSINESS LLC SAMPLETON OH 43000", 1, template=template) == [NO_SENDER]
    assert _r4_53("BUSINESS LLC SAMPLETON OH 43000", 2, template=template) == [NO_SENDER, NO_SENDER]


R4_53_BOOK = "BOOK TRANSFER CREDIT B/O: {orig} REF: /TIME/09:00 000000{n}"


def test_r4_53_a_book_transfer_from_an_addressed_designation_is_held_with_no_sender():
    assert _r4_53("BUSINESS LLC SAMPLETON OH 43000 US", 1, template=R4_53_BOOK) == [NO_SENDER]
    assert _r4_53("BUSINESS LLC SAMPLETON OH 43000 US", 2, template=R4_53_BOOK) == [NO_SENDER, NO_SENDER]
    # The recorded residual: with no address, the own book transfer keeps the strong rule's non_revenue.
    assert _r4_53("BUSINESS LLC", 1, template=R4_53_BOOK) == [("non_revenue", "strong_non_revenue_rule")]


@pytest.mark.parametrize(("words", "name"), [
    (["BUSINESS", "LLC", "SAMPLETON", "OH"], ["BUSINESS", "LLC"]),
    (["OPERATING", "ACCOUNT", "MAPLE", "GROVE", "MN"], ["OPERATING", "ACCOUNT"]),
    (["BUSINESS", "CHECKING", "SAMPLETON", "OH", "US"], ["BUSINESS", "CHECKING"]),
    (["BUSINESS", "LLC", "DENVER", "CO"], ["BUSINESS", "LLC"]),
    (["OPERATING", "ACCOUNT", "DENVER", "CO"], ["OPERATING", "ACCOUNT"]),
    (["OPERATING", "ACCOUNT", "TORONTO", "ON", "CANADA"], ["OPERATING", "ACCOUNT"]),
    (["CONTOSO", "BUILDERS", "CO", "SAMPLETON", "OH"], ["CONTOSO", "BUILDERS", "CO"]),
    (["THE", "CONTOSO", "SAMPLETON", "OH"], ["THE", "CONTOSO", "SAMPLETON", "OH"]),
    (["BUSINESS", "CONTOSO", "SAMPLETON", "OH"], ["BUSINESS", "CONTOSO", "SAMPLETON", "OH"]),
    (["OPERATING", "ACCOUNT"], ["OPERATING", "ACCOUNT"]),
    (["TOTAL", "SERVICES", "SAMPLETON", "OH"], ["TOTAL", "SERVICES", "SAMPLETON", "OH"]),
])
def test_r4_53_the_labelled_originator_s_name_without_its_address(words, name):
    assert tr._labelled_originator_name(words) == name


@pytest.mark.parametrize(("orig", "once", "twice"), [
    ("CONTOSO BUILDERS LLC SAMPLETON OH 43000", [NAMED], [REPEAT_WIRE, REPEAT_WIRE]),
    ("SELECT HOLDINGS LLC SAMPLETON OH", [NAMED], [REPEAT_WIRE, REPEAT_WIRE]),
    ("FABRIKAM MARINE SAMPLEVILLE TX", [NAMED], None),
    ("THE CONTOSO SAMPLETON OH", [NAMED], None),
    ("TOTAL SERVICES SAMPLETON OH", [NAMED], None),
    ("BUSINESS LLC", [NO_SENDER], [NO_SENDER, NO_SENDER]),
])
def test_r4_53_controls_a_named_originator_with_its_address_keeps_its_reading(orig, once, twice):
    assert _r4_53(orig, 1) == once
    if twice is not None:
        assert _r4_53(orig, 2) == twice


@pytest.mark.parametrize("orig", ["1XCONTOSO LLC OH 43000", "1XCONTOSO LLC SAMPLETON OH 43000", "1XCONTOSO BC"])
def test_r4_b13_a_name_word_glued_to_digits_keeps_its_sender(orig):
    # Measured on the corpus (R4-B13): a sender whose name word is glued to digits ('<n>X<NAME> LLC <ST> <ZIP>'), which
    # payer_name drops, still names that sender: neither the address cut (R4-53) nor the province test (R4-14) reads
    # its region as naming nobody, so the wire keeps its base reading (counted).
    assert _r4_53(orig, 1) == [NAMED]
    assert tr._glued_name_word(orig) and not tr._glued_name_word("000000000001 ON M5V 3Y2")


def test_r4_53_control_a_numbered_company_with_its_address_is_counted_never_verified():
    assert _r4_53("1234567 ONTARIO INC TORONTO ON", 2) == [NAMED, NAMED]
    text = tc.revenue_text(tc.normalize_transaction_description(
        R4_53_FEDWIRE.format(orig="1234567 ONTARIO INC TORONTO ON", n=1)))
    assert tc.numbered_company(text)


# R4-B13 review round 1 (findings 2, 3 and 8; R3-40's ruling under the underwriter's Q1 of 2026-10-02, "an
# originator's address is never its name"): the address cut reads only an address. A legal form is cut at only when a
# name word stands before it and an address tail follows it (one to three town words, a state's or province's code, a
# country optional); a designation cut needs two designation words, or one of ACCOUNT, ACCT or DDA, ending in an
# account word, and MARKET is one only after MONEY. A name these readings leave whole keeps the base's reading.
R4_B13_R1_ORG = "INCOMING WIRE ORG {orig} REF {n}"
R4_B13_R1_BOFA = ("WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:20540302001234 ORIG:{orig} ID:0001 "
                  "SND BK:SAMPLE BANK ID:0002 PMT DET:SAMPLE {n}")
R4_B13_R1_NAMED_ONLY = [NAMED, NAMED]
R4_B13_R1_REPEAT = [REPEAT_WIRE, REPEAT_WIRE]


@pytest.mark.parametrize(("orig", "twice"), [
    # A legal form that leads the name, or a form with no address after it (finding 2).
    ("LP CONTOSO GAS SUPPLY", R4_B13_R1_NAMED_ONLY),
    ("LIMITED FABRIKAM EDITIONS", R4_B13_R1_NAMED_ONLY),
    ("LTD FABRIKAM COMMODITIES LLC", R4_B13_R1_REPEAT),
    ("LP CONTOSO GAS SUPPLY SAMPLETON OH 43000", R4_B13_R1_NAMED_ONLY),
    ("COMPANY CONTOSO STORE SAMPLETON OH", R4_B13_R1_NAMED_ONLY),
    ("CORP OF FABRIKAM", R4_B13_R1_NAMED_ONLY),
    ("THE CO OP SAMPLETON OH 43000", R4_B13_R1_REPEAT),
    ("BUSINESS LLC DBA FABRIKAM SUPPLY", R4_B13_R1_REPEAT),
    ("SERVICES CO OF FABRIKAM", R4_B13_R1_NAMED_ONLY),
    ("CO OP CONTOSO ELECTRIC SAMPLETON OH 43000", R4_B13_R1_REPEAT),
    # A single designation word leading a name (finding 3).
    ("MARKET FABRIKAM PRODUCE SAMPLETON OH 43000", R4_B13_R1_NAMED_ONLY),
    ("MARKET CONTOSO GROCERY SAMPLETON OH 43000", R4_B13_R1_NAMED_ONLY),
    ("MARKET TAILSPIN FOODS SAMPLETON OH", R4_B13_R1_NAMED_ONLY),
    ("SAV CONTOSO DRUGS SAMPLETON CA 90000", R4_B13_R1_NAMED_ONLY),
    ("SAVINGS FABRIKAM PLUS SAMPLETON OH 43000", R4_B13_R1_NAMED_ONLY),
    ("CHECKING CONTOSO POINT SAMPLETON OH", R4_B13_R1_NAMED_ONLY),
    ("MARKET SAMPLETON OH 43000", R4_B13_R1_NAMED_ONLY),
])
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r1_a_name_the_address_cut_leaves_whole_keeps_the_base_reading(orig, twice, template):
    assert _r4_53(orig, 1, template=template) == [NAMED]
    assert _r4_53(orig, 2, template=template) == twice


@pytest.mark.parametrize("orig", ["LP CONTOSO GAS SUPPLY LLC", "LTD FABRIKAM COMMODITIES LLC",
                                  "CO OP CONTOSO ELECTRIC LLC", "LIMITED EDITION CONTOSO GALLERY LLC"])
def test_r4_b13_r1_a_legal_form_leading_the_name_on_bank_of_america_keeps_the_base_reading(orig):
    rows = [(R4_B13_R1_BOFA.format(orig=orig, n=n), amount) for n, amount in ((1, 2345.67), (2, 3456.78))]
    assert _tiers(rows[:1], bank="Bank of America") == [NAMED]
    assert _tiers(rows, bank="Bank of America") == R4_B13_R1_REPEAT


@pytest.mark.parametrize("orig", ["MONEY MARKET SAMPLETON OH 43000", "ACCOUNT SAMPLETON OH 43000",
                                  "DDA MAPLE GROVE MN",
                                  # The recorded residual: a name led by a whole two-word designation.
                                  "MONEY MARKET FABRIKAM FOODS SAMPLETON OH"])
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r1_controls_a_designation_with_its_address_still_names_no_sender(orig, template):
    assert _r4_53(orig, 1, template=template) == [NO_SENDER]
    assert _r4_53(orig, 2, template=template) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize(("words", "name"), [
    (["LP", "CONTOSO", "GAS", "SUPPLY", "LLC"], ["LP", "CONTOSO", "GAS", "SUPPLY", "LLC"]),
    (["LTD", "FABRIKAM", "COMMODITIES", "LLC"], ["LTD", "FABRIKAM", "COMMODITIES", "LLC"]),
    (["THE", "CO", "OP", "SAMPLETON", "OH"], ["THE", "CO", "OP", "SAMPLETON", "OH"]),
    (["BUSINESS", "LLC", "DBA", "FABRIKAM", "SUPPLY"], ["BUSINESS", "LLC", "DBA", "FABRIKAM", "SUPPLY"]),
    (["SERVICES", "CO", "OF", "FABRIKAM"], ["SERVICES", "CO", "OF", "FABRIKAM"]),
    (["CONTOSO", "LLC"], ["CONTOSO", "LLC"]),
    (["CONTOSO", "CO", "US"], ["CONTOSO", "CO", "US"]),
    (["CONTOSO", "CO", "DENVER", "CO", "US"], ["CONTOSO", "CO"]),
    (["MARKET", "FABRIKAM", "PRODUCE", "SAMPLETON", "OH"], ["MARKET", "FABRIKAM", "PRODUCE", "SAMPLETON", "OH"]),
    (["CHECKING", "SAMPLETON", "OH"], ["CHECKING", "SAMPLETON", "OH"]),
    (["MONEY", "MARKET", "SAMPLETON", "OH"], ["MONEY", "MARKET"]),
    (["ACCOUNT", "SAMPLETON", "OH"], ["ACCOUNT"]),
    (["DDA", "MAPLE", "GROVE", "MN"], ["DDA"]),
])
def test_r4_b13_r1_the_address_cut_reads_only_an_address(words, name):
    assert tr._labelled_originator_name(words) == name


@pytest.mark.parametrize("orig", ["REF12ABC BUSINESS LLC SAMPLETON OH 43000",
                                  "AC12345XYZ OPERATING ACCOUNT SAMPLETON OH"])
def test_r4_b13_r1_a_glued_reference_is_no_name_word(orig):
    # R4-B13 review round 1 (finding 8): only a first token of digits glued to three or more letters ('1XCONTOSO', the
    # corpus shape) is read as the sender's own name word; a glued reference ('REF12ABC', 'AC12345XYZ') never keeps a
    # designation's address as a name.
    assert _r4_53(orig, 1) == [NO_SENDER]
    assert _r4_53(orig, 2) == [NO_SENDER, NO_SENDER]
    assert not tr._glued_name_word(tc.payer_region(tc.revenue_text(tc.normalize_transaction_description(
        R4_53_FEDWIRE.format(orig=orig, n=1)))))
    assert tr._glued_name_word("1XCONTOSO LLC SAMPLETON OH") and not tr._glued_name_word("BUSINESS LLC 1XCONTOSO")


@pytest.mark.parametrize(("text", "reading"), [
    # Single words of a province's or a country's name name somebody (finding 4).
    ("WIRE TRANSFER FROM NORTHWEST", NAMED),
    ("WIRE TRANSFER FROM COLUMBIA", NAMED),
    ("WIRE TRANSFER FROM PRINCE EDWARD", NAMED),
    ("WIRE TRANSFER FROM NEW ISLAND", NAMED),
    ("INCOMING WIRE ORG UNITED REF 1", NAMED),
    ("INCOMING WIRE ORG STATES REF 1", NAMED),
    # Whole names and codes name nobody (R4-14, unchanged).
    ("INCOMING WIRE ORG ALBERTA REF 1", NO_SENDER),
    ("WIRE TRANSFER IN 1234 NOVA SCOTIA", NO_SENDER),
    ("WIRE TRANSFER IN 1234 UNITED STATES", NO_SENDER),
    ("WIRE TRANSFER FROM 000000000001 BRITISH COLUMBIA", NO_SENDER),
    ("WIRE TRANSFER FROM 000000000001 BC", NO_SENDER),
])
def test_r4_b13_r1_a_province_reads_by_its_whole_name(text, reading):
    assert _tiers([(text, 2345.67)]) == [reading]


# R4-B13 review round 2 (findings 1 to 4; R3-40's ruling under the underwriter's Q1 of 2026-10-02, "an originator's
# address is never its name", read only on an address; Q5 of 2026-09-28 counts a named sender; the brief's G7
# narrowing): a leading name word that glues letters then digits ('CONTOSO9', the common brand shape) is the sender's
# own name, as a digits-first one is, never a reference label's ('TXN12345'); an address tail never holds a trade-name
# marker (DBA, AKA, FKA, a spaced D B A), a connector, a legal form or a company-name word, so the name after the form
# keeps the base's reading; a bare state's or province's code after a named form is an address tail too; and the
# address lane reads only a row that opens as an incoming wire.
R4_B13_R2_GLUED_NAMES = [
    ("CONTOSO9 SERVICES LLC SAMPLETON OH 43000", R4_B13_R1_REPEAT),
    ("FABRIKAM9 GROUP HOLDINGS LLC SAMPLETON OH 43000", R4_B13_R1_REPEAT),
    ("TAILSPIN360 MANAGEMENT LLC SAMPLETON OH", R4_B13_R1_REPEAT),
    ("ADATUM66 HOLDINGS LLC SAMPLETON OH", R4_B13_R1_REPEAT),
    ("CONTOSO24 SERVICES INC TORONTO ON", R4_B13_R1_REPEAT),
    ("FABRIKAM3 ENTERPRISES LLC MAPLE GROVE MN", R4_B13_R1_REPEAT),
    ("CONTOSO54 SOLUTIONS INC MAPLE GROVE MN US", R4_B13_R1_REPEAT),
    ("LITWARE7 GROUP LLC SAMPLETON OH 43000", R4_B13_R1_REPEAT),
    ("LITWARE7 BUSINESS CHECKING SAMPLETON OH", R4_B13_R1_NAMED_ONLY),
    ("CONTOSO9 OPERATING ACCOUNT SAMPLETON OH", R4_B13_R1_NAMED_ONLY),
]


@pytest.mark.parametrize(("orig", "twice"), R4_B13_R2_GLUED_NAMES)
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r2_a_leading_letters_then_digits_name_word_keeps_the_base_reading(orig, twice, template):
    # Finding 1: payer_name drops every token that holds a digit, so the cut or the province test would leave such a
    # name's noise words alone; the glued guard reads the word as the sender's own name.
    assert _r4_53(orig, 1, template=template) == [NAMED]
    assert _r4_53(orig, 2, template=template) == twice


def test_r4_b13_r2_a_letters_then_digits_name_on_bank_of_america_keeps_the_base_reading():
    rows = [(R4_B13_R1_BOFA.format(orig="LITWARE7 GROUP LLC SAMPLETON OH 43000", n=n), amount)
            for n, amount in ((1, 2345.67), (2, 3456.78))]
    assert _tiers(rows[:1], bank="Bank of America") == [NAMED]
    assert _tiers(rows, bank="Bank of America") == R4_B13_R1_REPEAT


@pytest.mark.parametrize("text", ["WIRE TRANSFER FROM CONTOSO9 BC", "WIRE TRANSFER IN 1234 CONTOSO9 ONTARIO",
                                  "WIRE TRANSFER IN 1234 TAILSPIN360 ALBERTA"])
def test_r4_b13_r2_a_letters_then_digits_name_before_a_province_names_its_sender(text):
    assert _tiers([(text, 2345.67)]) == [NAMED]


@pytest.mark.parametrize("orig", ["TXN12345 BUSINESS LLC SAMPLETON OH", "ACC1234 OPERATING ACCOUNT SAMPLETON OH",
                                  "TRN12345 GROUP LLC SAMPLETON OH 43000", "ACCT1234 BUSINESS LLC SAMPLETON OH",
                                  "CHK12345 BUSINESS CHECKING SAMPLETON OH"])
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r2_a_glued_reference_label_is_no_name_word(orig, template):
    # Finding 1: a reference label's letters glued to its number (TXN, ACC, TRN, ACCT, CHK) are no sender's name, so a
    # designation with its address still names nobody.
    assert _r4_53(orig, 1, template=template) == [NO_SENDER]
    assert _r4_53(orig, 2, template=template) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize(("region", "glued"), [
    ("1XCONTOSO LLC SAMPLETON OH", True),
    ("CONTOSO9 SERVICES LLC SAMPLETON OH", True),
    ("TAILSPIN360 MANAGEMENT LLC", True),
    ("CONTOSO9 BC", True),
    ("REF12ABC BUSINESS LLC SAMPLETON OH", False),
    ("AC12345XYZ OPERATING ACCOUNT SAMPLETON OH", False),
    ("INV12345 BUSINESS LLC SAMPLETON OH", False),
    ("ACC1234 OPERATING ACCOUNT SAMPLETON OH", False),
    ("TXN12345 BUSINESS LLC SAMPLETON OH", False),
    ("TRN12345 GROUP LLC SAMPLETON OH", False),
    ("BUSINESS LLC CONTOSO9", False),
    ("000000000001 ON M5V 3Y2", False),
])
def test_r4_b13_r2_the_glued_name_word_reads_a_leading_name_either_way(region, glued):
    assert tr._glued_name_word(region) is glued


R4_B13_R2_TRADE_NAMES = [
    ("K HOLDINGS LLC DBA FABRIKAM SAMPLETON OH 43000", R4_B13_R1_REPEAT),
    ("R AND J HOLDINGS LLC DBA CONTOSO PIZZA OH 43000", R4_B13_R1_REPEAT),
    ("M AND K HOLDINGS LLC DBA FABRIKAM PIZZA OH", R4_B13_R1_REPEAT),
    ("SERVICES LLC DBA FABRIKAM OH", R4_B13_R1_REPEAT),
    ("K HOLDINGS LLC AKA FABRIKAM SAMPLETON OH", R4_B13_R1_REPEAT),
    ("K GROUP LLC FKA FABRIKAM OH 43000", R4_B13_R1_REPEAT),
    ("J SERVICES INC D B A CONTOSO OH", R4_B13_R1_REPEAT),
    ("J SERVICES INC A K A CONTOSO OH", R4_B13_R1_REPEAT),
    ("GROUP INC AND FABRIKAM OH 43000", R4_B13_R1_REPEAT),
    ("HOLDINGS LLC THE FABRIKAM OH", R4_B13_R1_REPEAT),
    ("SERVICES LLC SELECT SAMPLETON OH", R4_B13_R1_REPEAT),
    ("SERVICES CO OF OHIO SAMPLETON OH 43000", R4_B13_R1_NAMED_ONLY),
    ("MANAGEMENT CO OF AMERICA SAMPLETON OH", R4_B13_R1_NAMED_ONLY),
    ("BUSINESS CHECKING DBA FABRIKAM OH", R4_B13_R1_NAMED_ONLY),
    ("OPERATING ACCOUNT OF FABRIKAM OH", R4_B13_R1_NAMED_ONLY),
    ("BUSINESS CHECKING AND FABRIKAM OH", R4_B13_R1_NAMED_ONLY),
]


@pytest.mark.parametrize(("orig", "twice"), R4_B13_R2_TRADE_NAMES)
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r2_a_trade_name_or_a_connector_after_the_cut_keeps_the_base_reading(orig, twice, template):
    # Finding 2: the words after the form or the designation are no address when they hold a trade-name marker, a
    # connector, a legal form or a company-name word, so the trade name or the name after them still names the sender.
    assert _r4_53(orig, 1, template=template) == [NAMED]
    assert _r4_53(orig, 2, template=template) == twice


@pytest.mark.parametrize("orig", ["K D B A SERVICES LLC SAMPLETON OH", "K DBA SERVICES LLC SAMPLETON OH"])
def test_r4_b13_r2_a_trade_name_marker_before_the_form_reads_as_one_word(orig):
    # Finding 2: a spaced D B A, which payer_name's single-letter drop removes, reads as DBA does: a noise-only trade
    # name with its address still names nobody, spaced or not.
    assert _r4_53(orig, 1) == [NO_SENDER]
    assert _r4_53(orig, 2) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize(("words", "name"), [
    (["HOLDINGS", "LLC", "DBA", "FABRIKAM", "SAMPLETON", "OH"], ["HOLDINGS", "LLC", "DBA", "FABRIKAM", "SAMPLETON", "OH"]),
    (["HOLDINGS", "LLC", "AKA", "FABRIKAM", "OH"], ["HOLDINGS", "LLC", "AKA", "FABRIKAM", "OH"]),
    (["SERVICES", "CO", "OF", "OHIO", "SAMPLETON", "OH"], ["SERVICES", "CO", "OF", "OHIO", "SAMPLETON", "OH"]),
    (["GROUP", "INC", "AND", "FABRIKAM", "OH"], ["GROUP", "INC", "AND", "FABRIKAM", "OH"]),
    (["HOLDINGS", "LLC", "THE", "FABRIKAM", "OH"], ["HOLDINGS", "LLC", "THE", "FABRIKAM", "OH"]),
    (["SERVICES", "LLC", "SELECT", "SAMPLETON", "OH"], ["SERVICES", "LLC", "SELECT", "SAMPLETON", "OH"]),
    (["BUSINESS", "CHECKING", "DBA", "FABRIKAM", "OH"], ["BUSINESS", "CHECKING", "DBA", "FABRIKAM", "OH"]),
    (["OPERATING", "ACCOUNT", "OF", "FABRIKAM", "OH"], ["OPERATING", "ACCOUNT", "OF", "FABRIKAM", "OH"]),
    # Finding 3: a bare state's or province's code, a country optional, is an address tail.
    (["BUSINESS", "LLC", "OH"], ["BUSINESS", "LLC"]),
    (["SERVICES", "INC", "TX", "US"], ["SERVICES", "INC"]),
    (["GROUP", "LLC", "ON", "CANADA"], ["GROUP", "LLC"]),
    (["CONTOSO", "CO", "US"], ["CONTOSO", "CO", "US"]),
    (["BUSINESS", "LLC"], ["BUSINESS", "LLC"]),
])
def test_r4_b13_r2_the_address_cut_reads_only_an_address(words, name):
    assert tr._labelled_originator_name(words) == name


def test_r4_b13_r2_a_spaced_trade_name_marker_keeps_the_name_after_it():
    assert not tr._wire_names_nobody("J SERVICES INC D B A CONTOSO OH", labelled=True)
    assert tr._wire_names_nobody("J SERVICES INC D B A", labelled=True)


@pytest.mark.parametrize("orig", ["BUSINESS LLC OH 43000", "GROUP HOLDINGS LLC OH 43000", "SERVICES INC TX 75001 US",
                                  "BUSINESS LLC OH"])
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r2_a_designation_form_with_a_bare_state_names_no_sender(orig, template):
    # Finding 3: a legal form followed by a state's code, its ZIP or a country optional (Chase's B/O layout), is cut
    # there, so a noise-only name with only its state names nobody, once and on a repeat.
    assert _r4_53(orig, 1, template=template) == [NO_SENDER]
    assert _r4_53(orig, 2, template=template) == [NO_SENDER, NO_SENDER]


@pytest.mark.parametrize(("orig", "once", "twice"), [
    ("CONTOSO LLC OH 43000", [NAMED], [REPEAT_WIRE, REPEAT_WIRE]),
    ("SELECT HOLDINGS LLC OH 43000", [NAMED], [REPEAT_WIRE, REPEAT_WIRE]),
    ("1XCONTOSO LLC OH 43000", [NAMED], [NAMED, NAMED]),
])
def test_r4_b13_r2_controls_a_named_form_with_a_bare_state_keeps_its_reading(orig, once, twice):
    assert _r4_53(orig, 1) == once
    assert _r4_53(orig, 2) == twice


@pytest.mark.parametrize("text", [
    "ACH DEBIT ORIG NAME WOODGROVE LENDING 1234567 LN SAMPLETON OH 43000",
    "ACH DEBIT ORIG CO NM WOODGROVE LENDING 1234567 LN SAMPLETON OH 43000",
    "BOOK TRANSFER DEBIT A/C: WOODGROVE LENDING LLC ORG: NORTHWIND LABS INC 77 LN SAMPLETON OH 43000",
    "ORIG CO NAME:WOODGROVE LENDING ORIG ID:1234 DESC DATE: CO ENTRY DESCR:PAYMENT SEC:CCD "
    "IND NAME:NORTHWIND LABS 1234567 LN SAMPLETON OH 43000",
])
def test_r4_b13_r2_a_labelled_debit_reads_as_at_the_base(text):
    # Finding 4: the address lane reads only a row that opens as an incoming wire, so a debit printing an originator
    # label before '<n> LN <town> <ST> <ZIP>' reads as its LOAN-spelled twin in every field, alone and in a series.
    _read_as_printed_loan([(text, -1234.56)], bank="Chase")
    series = _read_as_printed_loan([(text, -1234.56)] * 4, bank="Chase")
    assert " LOAN " in series[0].normalized_description


@pytest.mark.parametrize("text", [
    "ACH CREDIT WOODGROVE BANK ORG ID 1234 1234567 LN SAMPLETON OH 43000",
    "ACH CREDIT WOODGROVE BANK ORIGINATOR ID 1234 1234567 LN SAMPLETON OH 43000",
    "ACH CREDIT WOODGROVE BANK B O 1234567 LN SAMPLETON OH 43000",
    "REMOTE DEPOSIT ORG 1234 WOODGROVE 1234567 LN SAMPLETON OH 43000",
    "DEPOSIT ORG WOODGROVE 1234567 LN SAMPLETON OH 43000",
    "INCOMING WIRE ORG ID 1234 FABRIKAM HOLDINGS 77 LN SAMPLETON OH 43000 REF 1",
])
def test_r4_b13_r2_a_labelled_non_wire_or_id_row_keeps_the_credit_s_loan(text):
    # Finding 4: a row that opens as no incoming wire, or whose label is an ID field (ORG ID, ORIGINATOR ID), keeps
    # the strong rule's non_revenue, as at the base.
    [record] = _read_as_printed_loan([(text, 23456.78)], bank="Chase")
    assert (record.revenue_tier, record.revenue_match_method) == ("non_revenue", "strong_non_revenue_rule")


@pytest.mark.parametrize("text", [
    "INCOMING WIRE ORG FABRIKAM HOLDINGS 77 LN SAMPLETON OH 43000 REF 1",
    "WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:20540302001234 ORIG:FABRIKAM HOLDINGS 77 LN SAMPLETON OH 43000 "
    "ID:0001 SND BK:SAMPLE BANK ID:0002 PMT DET:SAMPLE 1",
    "BOOK TRANSFER CREDIT B/O: FABRIKAM HOLDINGS 77 LN SAMPLETON OH 43000 REF: /TIME/09:00 0000001",
])
def test_r4_b13_r2_controls_an_incoming_wire_s_originator_address_is_still_a_lane(text):
    [record] = _records([(text, 23456.78)], bank="Chase")
    assert " 77 LN SAMPLETON OH 43000" in record.normalized_description
    assert (record.revenue_tier, record.revenue_tier_reason) == NAMED


# R4-B13 review round 3 (findings 1 to 3; R3-40's ruling under the underwriter's Q1 of 2026-10-02, "an originator's
# address is never its name", read only on an address; Q5 of 2026-09-28 counts a named sender): every trade-name marker
# is refused as an address's town word, the operating-as and trading-as forms (O/A, T/A, spaced O A and T A joined
# for the cut, and the AS of TRADING AS, OPERATING AS, DOING BUSINESS AS) beside DBA, AKA and FKA, so a noise-only
# legal name printing its trade name and an address keeps the base's reading on every labelled layout; the address
# lane reads only an address that follows a name (a label followed straight by the number is an account's position,
# LOAN); and a town whose name holds a connector or a company-name word is a recorded residual read as at the base.
R4_B13_R3_RBC = ("BOOK TRANSFER CREDIT B/O: ROYAL BANK OF CANADA PAYMENT CENTRE TORONTO ON CANADA ORG: 000000000001 "
                 "{orig} REF: RFB GOODS AND SERVICES TRN 000{n}")
R4_B13_R3_LAYOUTS = [(R4_53_FEDWIRE, "Chase"), (R4_B13_R1_ORG, "Chase"), (R4_B13_R3_RBC, "Chase"),
                     (R4_B13_R1_BOFA, "Bank of America")]
R4_B13_R3_TRADE_NAMES = [
    "K HOLDINGS LTD O/A FABRIKAM TORONTO ON",
    "K HOLDINGS LTD O/A FABRIKAM TORONTO ON CANADA",
    "K HOLDINGS LTD O/A FABRIKAM CALGARY AB",
    "K GROUP INC O/A CONTOSO ON",
    "SERVICES INC O/A CONTOSO OH 43000",
    "K HOLDINGS LLC T/A FABRIKAM SAMPLETON OH",
    "K HOLDINGS LLC TRADING AS FABRIKAM OH",
    "K HOLDINGS LLC OPERATING AS FABRIKAM OH",
    "K HOLDINGS LTD O/A FABRIKAM PIZZA ON",
    "SERVICES INC O A CONTOSO OH",
    "K HOLDINGS LLC OA FABRIKAM OH",
    "K HOLDINGS LLC TA FABRIKAM SAMPLETON OH",
    # Controls, unchanged: four or more words before the state are no tail; no address at all.
    "K HOLDINGS LLC DOING BUSINESS AS FABRIKAM OH",
    "K HOLDINGS LTD O/A FABRIKAM",
]


def _r4_b13_r3(orig, times, template, bank):
    rows = [(template.format(orig=orig, n=n + 1), (2345.67, 3456.78)[n]) for n in range(times)]
    return _tiers(rows, bank=bank)


@pytest.mark.parametrize("orig", R4_B13_R3_TRADE_NAMES)
@pytest.mark.parametrize(("template", "bank"), R4_B13_R3_LAYOUTS)
def test_r4_b13_r3_an_operating_as_or_trading_as_name_keeps_the_base_reading(orig, template, bank):
    # Finding 1: O/A and T/A collapse to nothing (payer_name drops single letters) and TRADING AS read as two town
    # words, so the cut left the noise-only legal name: held where the base counted it and Verified it on a repeat.
    assert _r4_b13_r3(orig, 1, template, bank) == [NAMED]
    assert _r4_b13_r3(orig, 2, template, bank) == R4_B13_R1_REPEAT


@pytest.mark.parametrize(("words", "name"), [
    ("HOLDINGS LTD OA FABRIKAM TORONTO ON", "HOLDINGS LTD OA FABRIKAM TORONTO ON"),
    ("HOLDINGS LLC TA FABRIKAM SAMPLETON OH", "HOLDINGS LLC TA FABRIKAM SAMPLETON OH"),
    ("HOLDINGS LLC TRADING AS FABRIKAM OH", "HOLDINGS LLC TRADING AS FABRIKAM OH"),
    ("HOLDINGS LLC OPERATING AS FABRIKAM OH", "HOLDINGS LLC OPERATING AS FABRIKAM OH"),
    ("BUSINESS CHECKING AS FABRIKAM OH", "BUSINESS CHECKING AS FABRIKAM OH"),
    # Controls: an address's tail is still cut.
    ("HOLDINGS LTD TORONTO ON", "HOLDINGS LTD"),
    ("BUSINESS LLC SAMPLETON OH", "BUSINESS LLC"),
])
def test_r4_b13_r3_the_address_cut_never_reads_a_trade_name_marker_as_a_town(words, name):
    assert tr._labelled_originator_name(words.split()) == name.split()


def test_r4_b13_r3_a_spaced_operating_as_marker_keeps_the_name_after_it():
    assert not tr._wire_names_nobody("K HOLDINGS LTD O A FABRIKAM TORONTO ON", labelled=True)
    assert not tr._wire_names_nobody("K HOLDINGS LLC T A FABRIKAM SAMPLETON OH", labelled=True)
    assert tr._wire_names_nobody("K HOLDINGS LTD O A", labelled=True)
    assert tr._wire_names_nobody("HOLDINGS LTD TORONTO ON", labelled=True)


@pytest.mark.parametrize(("orig", "once", "twice"), [
    # A spaced O A or T A before the form reads as the joined word does, as a spaced D B A does (review round 2): a
    # noise-only name with its address names nobody.
    ("K O A SERVICES LLC SAMPLETON OH", [NO_SENDER], [NO_SENDER, NO_SENDER]),
    ("K T A SERVICES LLC SAMPLETON OH", [NO_SENDER], [NO_SENDER, NO_SENDER]),
    ("K D B A SERVICES LLC SAMPLETON OH", [NO_SENDER], [NO_SENDER, NO_SENDER]),
    # A numbered company keeps its reading (counted, never Verified); a two-letter word before the form names it.
    ("1234567 ONTARIO INC O/A FABRIKAM TORONTO ON", [NAMED], [NAMED, NAMED]),
    ("K OA SERVICES LLC SAMPLETON OH", [NAMED], R4_B13_R1_REPEAT),
    # The designation addresses stay held (the brief's T53a/T53b).
    ("BUSINESS LLC SAMPLETON OH 43000 US", [NO_SENDER], [NO_SENDER, NO_SENDER]),
    ("SERVICES INC TORONTO ON", [NO_SENDER], [NO_SENDER, NO_SENDER]),
])
@pytest.mark.parametrize(("template", "bank"), R4_B13_R3_LAYOUTS)
def test_r4_b13_r3_controls_the_marker_refusal_moves_no_other_reading(orig, once, twice, template, bank):
    assert _r4_b13_r3(orig, 1, template, bank) == once
    assert _r4_b13_r3(orig, 2, template, bank) == twice


@pytest.mark.parametrize("orig", ["O A LLC SAMPLETON OH", "T A LLC SAMPLETON OH", "D B A LLC SAMPLETON OH"])
@pytest.mark.parametrize(("template", "bank"), R4_B13_R3_LAYOUTS)
def test_r4_b13_r3_recorded_a_name_of_single_letters_and_a_spaced_marker_names_no_sender(orig, template, bank):
    # Finding 1, recorded consequence (0 corpus rows print O A or T A): the joined O A or T A is the one word before
    # the form, so the cut reads the town as an address and the single letters payer_name drops leave no name, as a
    # spaced D B A already did at e79dc51 (R4-53's reading: the address alone is no name); the base counted the town.
    assert _r4_b13_r3(orig, 1, template, bank) == [NO_SENDER]
    assert _r4_b13_r3(orig, 2, template, bank) == [NO_SENDER, NO_SENDER]


R4_B13_R3_NAMELESS_LANES = [
    "INCOMING WIRE ORG 0001234567 LN SAMPLETON OH 43000 REF {n}",
    "FEDWIRE CREDIT VIA: SAMPLE BANK/011000000 B/O: 0001234567 LN SAMPLETON OH 43000 REF: CHASE NYC/CTR/"
    "BNF=NORTHWIND LABS INC TRN: 000000{n} IMAD: 0000",
    "WIRE TYPE:WIRE IN DATE:540302 TIME:1200 ET TRN:20540302001234 ORIG:0001234567 LN SAMPLETON OH 43000 ID:0001 "
    "SND BK:SAMPLE BANK ID:0002 PMT DET:SAMPLE {n}",
    "WT FED#0123{n} SAMPLE BANK /ORG=0001234567 LN SAMPLETON OH 43000 SRF# 0001",
    "FEDWIRE CREDIT VIA: SAMPLE BANK/011000000 B/O: 77 LN SAMPLETON OH 43000 REF: CHASE NYC/CTR/"
    "BNF=NORTHWIND LABS INC TRN: 000000{n} IMAD: 0000",
    "WIRE FROM FABRIKAM ORG 1234567 LN SAMPLETON OH 43000 REF {n}",
    "WIRE FROM WOODGROVE BANK ORG 1234567 LN SAMPLETON OH 43000 REF {n}",
    "INCOMING WIRE ORG ACCT 0001234567 LN SAMPLETON OH 43000 REF {n}",
    "INCOMING WIRE ORG REF 0001234567 LN SAMPLETON OH 43000 REF {n}",
]


@pytest.mark.parametrize("template", R4_B13_R3_NAMELESS_LANES)
def test_r4_b13_r3_a_label_followed_straight_by_the_number_keeps_the_strong_rule_s_loan(template):
    # Finding 2 (R4-53's ruling; Q1 of 2026-10-02 holds a wire with no sender; the industry vote's warning that a
    # digits-only token before LN can be a loan account): no name prints between the originator label and the number,
    # so the number is an account's and LN its loan; the 'sender' would be the address alone. Each row reads as its
    # LOAN-spelled twin in every field, once and on a repeat.
    rows = [(template.format(n=n + 1), (23456.78, 34567.89)[n]) for n in range(2)]
    for records in (_read_as_printed_loan(rows[:1], bank="Chase"), _read_as_printed_loan(rows, bank="Chase")):
        assert {(record.revenue_tier, record.revenue_match_method) for record in records} == {
            ("non_revenue", "strong_non_revenue_rule")}
        assert " LOAN SAMPLETON OH 43000" in records[0].normalized_description


@pytest.mark.parametrize("text", [
    "INCOMING WIRE ORG 0001234567 FABRIKAM HOLDINGS 77 LN SAMPLETON OH 43000 REF 1",
    "FEDWIRE CREDIT VIA: SAMPLE BANK/011000000 B/O: FABRIKAM HOLDINGS 0001234567 LN SAMPLETON OH 43000 REF: CHASE "
    "NYC/CTR/BNF=NORTHWIND LABS INC TRN: 0000001 IMAD: 0000",
])
def test_r4_b13_r3_controls_a_named_originator_s_address_is_still_a_lane(text):
    [record] = _records([(text, 23456.78)], bank="Chase")
    assert " LN SAMPLETON OH 43000" in record.normalized_description
    assert (record.revenue_tier, record.revenue_tier_reason) == NAMED


@pytest.mark.parametrize(("orig", "twice"), [
    ("BUSINESS LLC CITY OF SAMPLEVILLE CA 90000", R4_B13_R1_REPEAT),
    ("GROUP HOLDINGS LLC TOWN AND SAMPLETON MO 63000", R4_B13_R1_REPEAT),
    ("BUSINESS LLC ISLE OF SAMPLE SC 29000", R4_B13_R1_REPEAT),
    ("BUSINESS LLC THE SAMPLELANDS TX 77000", R4_B13_R1_REPEAT),
    ("SERVICES INC THE SAMPLES OR", R4_B13_R1_REPEAT),
    ("BUSINESS LLC COMMERCIAL SAMPLETON OH", R4_B13_R1_REPEAT),
])
@pytest.mark.parametrize("template", [R4_53_FEDWIRE, R4_B13_R1_ORG])
def test_r4_b13_r3_residual_a_town_holding_a_connector_or_a_company_word_reads_as_at_the_base(orig, twice, template):
    # Finding 3, recorded (fail open to the base's reading, 0 corpus rows on a labelled layout): the town-word
    # refusals that keep a trade name or a connector out of an address (review round 2) also refuse a real town whose
    # name holds THE, OF, AND or a company-name word, so a noise-only originator in such a town is counted once and
    # Verified on a repeat, as at the base, never held.
    assert _r4_53(orig, 1, template=template) == [NAMED]
    assert _r4_53(orig, 2, template=template) == twice

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

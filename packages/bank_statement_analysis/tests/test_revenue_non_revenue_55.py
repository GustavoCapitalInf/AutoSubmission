"""Classification 5.5 (true revenue spec §6.3, §7.11, T5): the narrowed non-revenue rules, the newly named non-revenue,
the tightened CUSTOMER descriptor, and the channel gate's declared demotions. Fabricated rows only."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction
from analysis.descriptor.rails import prints_internal_transfer_designation


def _credit(printed: str, *, holder: str | None = None):
    return classify_transaction(printed, 300.0, account_name=holder, direction="credit")


@pytest.mark.parametrize("printed", [
    "SAMPLE STATE MEDICAID DES:REIMBURSEMENT ID:1",
    "FABRIKAM HEALTH DES:HCCLAIMPMT REIMBURSEMENT ID:1",
    "SAMPLE COUNTY GEMT REIMBURSEMENT 1234",
])
def test_reimbursement_with_a_claim_signal_leaves_non_revenue(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


@pytest.mark.parametrize("printed", [
    "UNITEDHEALTHCARE DES:REIMBURSEMENT ID:1",
    "STATE OF TEXAS DES:TRAVEL REIMBURSEMENT ID:1",
    "FABRIKAM INC DES:EXPENSE REIMBURSEMENT ID:1",
])
def test_reimbursement_without_a_claim_signal_stays_non_revenue(printed):
    assert _credit(printed).revenue_classification == "non_revenue"


def test_exp_reimb_is_not_the_whole_word_so_it_is_not_non_revenue():
    assert _credit("FABRIKAM INC DES:EXP REIMB ID:1").revenue_classification == "unverified_deposit"


@pytest.mark.parametrize("printed", [
    "WIRE FROM 12 OAK LN SAMPLEVILLE",
    "ATM DEPOSIT 450 PINE HILL LN SAMPLEVILLE",
])
def test_a_street_ln_no_longer_reads_as_a_loan(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


def test_a_loan_ln_still_reads_as_a_loan():
    assert _credit("1234 COMMERCIAL LN PMT").revenue_classification == "non_revenue"
    assert _credit("000123 AUTO LN DISB").revenue_classification == "non_revenue"
    assert classify_transaction("TRUIST LN PYMT", -500.0).normalized_description == "TRUIST LOAN PYMT"


def test_rbc_s_funds_transfer_credit_names_its_sender():
    record = _credit("FUNDS TRANSFER CREDIT TT FABRIKAM SUPPLY LTD SAMPLEVILLE")
    assert record.revenue_classification == "unverified_deposit"
    assert not prints_internal_transfer_designation("FUNDS TRANSFER CREDIT TT FABRIKAM SUPPLY LTD SAMPLEVILLE")
    assert prints_internal_transfer_designation("FUNDS TRANSFER FROM SAVINGS 1234")


#: S2.3 review (fix 1, §7.11): 'FROM <payer>' names a third party; an account type or product after FROM describes one
#: of the holder's own accounts, so the transfer stays own-account.
OWN_ACCOUNT_DESCRIPTIONS = [
    "FUNDS TRANSFER FROM BUSINESS SAVINGS 1234",
    "FUNDS TRANSFER CREDIT FROM MONEY MARKET 1234",
    "BOOK TRANSFER FROM OPERATING ACCOUNT 1234",
    "FUNDS TRANSFER FROM PERSONAL CHECKING 1234",
    "ONLINE FUNDS TRANSFER FROM BUSINESS CHECKING 1234",
    "BOOK TRANSFER CREDIT FROM TAX RESERVE 1234",
    "FUNDS TRANSFER FROM LINE OF CREDIT 1234",
    # S2.3 re-review (minors 2 and 5): account adjectives, and the two shapes the corpus moved.
    "FUNDS TRANSFER FROM PRIMARY CHECKING 1234",
    "BOOK TRANSFER FROM MAIN ACCOUNT 1234",
    "FUNDS TRANSFER FROM JOINT SAVINGS 1234",
    "FUNDS TRANSFER FROM HIGH YIELD SAVINGS 1234",
    "FUNDS TRANSFER FROM LOAN ACCOUNT 1234",
    "FUNDS TRANSFER FROM LOC ACCOUNT 1234",
    # Audit round 2, R2-B10 (R11): 'FUNDS TRANSFER CREDIT TT 1234567890 W' left this list: a bare reference after an
    # incoming-wire label is no account description, and the wire is held with no sender (Q5; tests below).
]


@pytest.mark.parametrize("holder", [None, "FABRIKAM LLC"])
@pytest.mark.parametrize("printed", OWN_ACCOUNT_DESCRIPTIONS)
def test_a_transfer_from_an_account_description_stays_own_account(printed, holder):
    assert _credit(printed, holder=holder).revenue_classification == "non_revenue"
    assert prints_internal_transfer_designation(printed)


@pytest.mark.parametrize("printed", [
    "FUNDS TRANSFER FROM CONTOSO SUPPLY LLC",
    "FUNDS TRANSFER FROM CONTOSO BUSINESS SERVICES LLC",   # an account word inside a company name
    "FUNDS TRANSFER FROM FABRIKAM TAX PARTNERS LLC",
])
def test_a_transfer_from_a_named_payer_is_a_third_party(printed):
    assert _credit(printed, holder="NORTHWIND LLC").revenue_classification == "unverified_deposit"
    assert not prints_internal_transfer_designation(printed)


def test_a_transfer_from_a_named_payer_is_still_a_third_party():
    printed = "FUNDS TRANSFER FROM CONTOSO SUPPLY LLC"
    assert _credit(printed, holder="FABRIKAM LLC").revenue_classification == "unverified_deposit"
    assert not prints_internal_transfer_designation(printed)
    # ... unless the named payer is the holder (§5.2's holder test).
    assert _credit(printed, holder="CONTOSO SUPPLY LLC").revenue_classification == "non_revenue"


# Audit round 2, R2-B10 (R11; Q5, §7.11): an incoming wire printed on a funds-transfer wire label (or any incoming-wire
# label) that prints only a reference, no originator, no account word and no own-account product word, is a wire with
# no sender: held as wire_no_sender for review, never the holder's own transfer (non_revenue), and no own-account
# designation for R-d. Holder FABRIKAM TRADING LTD, RBC's layout, $2,500 a row.

TT_HOLDER = "FABRIKAM TRADING LTD"
TT_BANK = "Royal Bank of Canada"
NO_SENDER = ("excluded_pending_review", "wire_no_sender")


def _statement(rows, *, holder: str | None = TT_HOLDER, bank: str | None = TT_BANK) -> Statement:
    return Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=printed, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (printed, amount) in enumerate(rows)
    ])


def _tier(printed: str, amount: float = 2500.0) -> tuple[str | None, str | None]:
    [record] = classify_statement_transactions(_statement([(printed, amount)]))
    return record.revenue_tier, record.revenue_tier_reason or record.revenue_match_method


BARE_WIRE_LABELS = [
    "FUNDS TRANSFER CREDIT TT 1234567890 O",
    "FUNDS TRANSFER CREDIT TT 1234567891",
    "FUNDS TRANSFER CREDIT TT RBC123456789",
    "FUNDS TRANSFER CREDIT TT 1234567890 W",
    "INCOMING FUNDS TRANSFER 1234",
    "INBD FUNDS TRANSFER RECEIVED 1234",
    "FUNDS TRANSFER WIRE FROM 1234",
]


@pytest.mark.parametrize("printed", BARE_WIRE_LABELS)
def test_r11_a_funds_transfer_wire_label_with_only_a_reference_is_held_with_no_sender(printed):
    assert _tier(printed) == NO_SENDER
    assert not prints_internal_transfer_designation(printed)


@pytest.mark.parametrize("printed", BARE_WIRE_LABELS)
def test_r11_the_bare_incoming_wire_reader(printed):
    from analysis.descriptor.rails import _bare_incoming_wire
    from analysis.description_text import normalize_transaction_description

    assert _bare_incoming_wire(normalize_transaction_description(printed))


def test_r11_control_a_named_sender_after_the_tt_label_is_counted():
    assert _tier("FUNDS TRANSFER CREDIT TT 1234 CONTOSO SUPPLY INC") == ("counted_flagged", "wire_named_sender")


@pytest.mark.parametrize(("printed", "designation"), [
    # The holder's own name as the originator (§5.2's holder test), an account word or product word after the label,
    # a loan's proceeds, a funds or book transfer with no incoming-wire label: all stay the holder's own money.
    ("FUNDS TRANSFER CREDIT TT 1234 FABRIKAM TRADING LTD", False),
    ("FUNDS TRANSFER CREDIT TT SAVINGS 1234", True),
    ("INCOMING FUNDS TRANSFER FROM BUSINESS SAVINGS 1234", True),
    ("INCOMING FUNDS TRANSFER 1234 LOAN PROCEEDS", False),
    ("FUNDS TRANSFER 1234567", True),
    ("BOOK TRANSFER CREDIT B O 1234567", True),
])
def test_r11_controls_stay_non_revenue(printed, designation):
    assert _tier(printed)[0] == "non_revenue"
    assert prints_internal_transfer_designation(printed) is designation


def test_r11_control_a_registry_funder_after_the_tt_label_stays_financing_proceeds():
    assert _tier("FUNDS TRANSFER CREDIT TT KM CAPITAL C") == ("non_revenue", "financing_proceeds_credit")


def test_r11_control_an_incoming_wire_with_only_a_reference_stays_held():
    assert _tier("INCOMING WIRE 1234") == NO_SENDER


def test_r11_the_held_no_sender_wire_reaches_the_review_gate():
    from analysis.metrics import compute_metrics

    statement = _statement([("MISC PAYMENT SHOPIFY", 6000.0), ("FUNDS TRANSFER CREDIT TT 1234567890 O", 25000.0)])
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    assert metrics.verified_revenue_total + metrics.counted_flagged_total == 6000.0
    assert metrics.excluded_pending_review_total == 25000.0
    assert metrics.revenue_review_required


# Audit round 2, R2-B10 review round 1 (R11): the reader reads the ruling's words, a row that 'prints only a
# reference': every word after the label is a reference (digits, a masked token, a month), a single letter (RBC's O or
# W) or a wire label word (the wire label list R32 made one, and the funds-transfer labels' own TT and FROM). Any other
# word after the label (a holder-noise, generic, currency or legal-form word) is no reference, so the row keeps its
# own-account reading, never counted as a wire from a named sender with that word as its 'sender'.

NOT_ONLY_A_REFERENCE = [
    "FUNDS TRANSFER CREDIT TT 1234 BUSINESS",
    "FUNDS TRANSFER CREDIT TT 1234 TRUST",
    "FUNDS TRANSFER CREDIT TT 1234 OPERATING",
    "FUNDS TRANSFER CREDIT TT 1234 USD",
    "FUNDS TRANSFER CREDIT TT 1234 CAD",
    "FUNDS TRANSFER CREDIT TT USD 1234567890",
    "FUNDS TRANSFER CREDIT TT 1234 ONLINE",
    "FUNDS TRANSFER CREDIT TT 1234 PAYMENT",
    "FUNDS TRANSFER CREDIT TT 1234 INC",
    "FUNDS TRANSFER CREDIT TT 1234 LLC",
    "FUNDS TRANSFER CREDIT TT 1234 THE",
    "FUNDS TRANSFER WIRE FROM 1234 USD",
    "INBD FUNDS TRANSFER RECEIVED 1234 USD",
    "INCOMING FUNDS TRANSFER 1234 USD",
    "INCOMING FUNDS TRANSFER 1234 BUSINESS",
    "INCOMING FUNDS TRANSFER FROM BUSINESS",
]


def _revenue_text(printed: str) -> str:
    from analysis.descriptor.lexical import revenue_text
    from analysis.description_text import normalize_transaction_description

    return revenue_text(normalize_transaction_description(printed))


@pytest.mark.parametrize("printed", NOT_ONLY_A_REFERENCE)
def test_r11_review_a_word_besides_a_reference_keeps_the_own_account_reading(printed):
    from analysis.descriptor.rails import _bare_incoming_wire

    assert not _bare_incoming_wire(_revenue_text(printed))
    assert _tier(printed) == ("non_revenue", "strong_non_revenue_rule")
    assert prints_internal_transfer_designation(printed)


@pytest.mark.parametrize("printed", [
    # A month is a reference, and a stray originator or wire label names nobody: the row prints only a reference, so
    # it is held with no sender even where the payer reader keeps the word (pass 7 blanks a bare row's region).
    "FUNDS TRANSFER CREDIT TT 1234 MARCH",
    "FUNDS TRANSFER CREDIT TT 1234 FROM",
    "FUNDS TRANSFER CREDIT TT 1234 TT",
    "FUNDS TRANSFER CREDIT TT 1234 WIRE FROM 12345",
    "FUNDS TRANSFER CREDIT TT 1234 TRANSFER",
    "FUNDS TRANSFER CREDIT TT 1234 O W",
    "INBD FUNDS TRANSFER RECEIVED 1234 O",
    "INCOMING FUNDS TRANSFER FROM 1234",
])
def test_r11_review_a_row_of_references_and_labels_is_held_never_counted(printed):
    from analysis.descriptor.rails import _bare_incoming_wire

    assert _bare_incoming_wire(_revenue_text(printed))
    assert _tier(printed) == NO_SENDER
    assert not prints_internal_transfer_designation(printed)


def test_r11_review_recorded_residual_a_numbered_company_after_the_tt_label_keeps_the_own_account_reading():
    # The funds-transfer originator reader drops a numbered company's words, so the row reads as before R11; reading it
    # as a counted sender (OQ3) belongs to that reader. No corpus row prints one.
    from analysis.descriptor.rails import _bare_incoming_wire

    printed = "FUNDS TRANSFER CREDIT TT 1234567 ONTARIO INC"
    assert not _bare_incoming_wire(_revenue_text(printed))
    assert _tier(printed) == ("non_revenue", "strong_non_revenue_rule")


def test_r11_review_the_reader_s_label_words_are_the_wire_label_list_and_the_originator_labels():
    from analysis.descriptor import rails
    from analysis.true_revenue import self_originated_credits

    assert rails._BARE_WIRE_LABEL_WORDS == self_originated_credits._WIRE_LABEL_ONLY_WORDS | {"TT", "FROM"}


@pytest.mark.parametrize(("printed", "state"), [
    ("DEBIT CARD CREDIT VISA DIRECT SQUARE INC", "verified_revenue"),
    ("Debit Card Credit: Stripe Payout", "verified_revenue"),
    # §7.11's release rule (true revenue spec §20, final review M5): a processor's card credit leaves the reversal
    # rule only with a payout word, so a bare 'Stripe' stays non_revenue (§14.1 once said possible_return).
    ("Debit Card Credit: Stripe", "non_revenue"),
    ("DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA", "non_revenue"),
    ("DEBIT CARD CREDIT DOORDASH*FABRIKAM DELI", "non_revenue"),
    ("POS CREDIT PAYPAL *FABRIKAM STORE", "non_revenue"),
])
def test_a_card_credit_is_released_only_for_a_push_or_a_processor_payout(printed, state):
    assert _credit(printed).revenue_classification == state


def test_three_card_refunds_never_verify_each_other():
    for printed in ("DEBIT CARD CREDIT UBER *TRIP HELP.UBER.COM CA", "DEBIT CARD CREDIT DOORDASH*FABRIKAM DELI",
                    "POS CREDIT PAYPAL *FABRIKAM STORE"):
        records = classify_statement_transactions(Statement(account_name="SAMPLE CAFE LLC", transactions=[
            Transaction(date=f"2054-03-{day:02d}", description=printed, amount=20.0 + day, direction="credit")
            for day in (2, 9, 16)
        ]))
        assert {record.revenue_classification for record in records} == {"non_revenue"}


def test_customer_id_and_a_customer_check_never_verify():
    assert _credit("ACH CORP CREDIT FABRIKAM SUPPLY CUSTOMER ID 12345 PAYMENT").revenue_classification == (
        "unverified_deposit")
    assert _credit("FABRIKAM CUSTOMER CHECK PAYMENT").revenue_classification == "unverified_deposit"
    assert _credit("FABRIKAM CUSTOMER ACH PAYMENT").revenue_classification == "verified_revenue"


def test_the_customer_descriptor_never_reads_the_receiver_s_name():
    # S2.3 review (fix 4, §5.2): the receiver field prints the holder; its value never verifies a customer descriptor.
    receiver = "FABRIKAM SUPPLY DES:PAYMENT ID:1 INDN:CONTOSO CUSTOMER CARE LLC CO ID:1 CCD"
    assert _credit(receiver, holder="CONTOSO CUSTOMER CARE LLC").revenue_classification == "unverified_deposit"
    assert _credit(receiver).revenue_classification == "unverified_deposit"
    originator = "CONTOSO CUSTOMER CARE LLC DES:PAYMENT ID:1 INDN:FABRIKAM SUPPLY CO ID:1 CCD"
    assert _credit(originator, holder="FABRIKAM SUPPLY").revenue_classification == "verified_revenue"


@pytest.mark.parametrize(("printed", "rule"), [
    ("FABRIKAM DES:PAYMENT RTN ID:1", "returned_cancelled_reversed_or_provisional_credit"),
    ("FABRIKAM WIRE RECALLED 1234", "returned_cancelled_reversed_or_provisional_credit"),
    ("FABRIKAM DES:CHBK REVSL ID:1", "returned_cancelled_reversed_or_provisional_credit"),
    ("IRS TREAS 310 DES:TAX REF ID:1", "non_operating_credit"),
    ("SAMPLE STATE DES:TAXRFD ID:1", "non_operating_credit"),
    ("FRANCHISE TAX BD DES:CASTTAXRFD ID:1 PPD", "non_operating_credit"),   # glued to the state (review I6)
    ("IRS TREAS 310 DES:TAXEIC ID:1", "non_operating_credit"),
    ("SQUARE INC DES:SQ CAP1234 ID:1", "square_capital_credit"),
    ("SBAD TREAS 310 DES:MISC PAY ID:1", "sba_disbursement_credit"),
    ("EIDL 1234 SAMPLE", "sba_disbursement_credit"),
    ("FABRIKAM DES:ACCTVERIFY ID:1", "non_operating_credit"),
    ("FABRIKAM MICRO DEPOSIT", "non_operating_credit"),
])
def test_the_newly_named_non_revenue(printed, rule):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_matched_rule) == ("non_revenue", rule)


@pytest.mark.parametrize("printed", [
    # A3-G: the Canada Revenue Agency's income-tax refund direct deposit, bilingual or not (RIT and RIF are the
    # banks' two labels of one refund).
    "DIRECT DEPOSIT CANADA RIT RIF",
    "DIRECT DEPOSIT CANADA RIT",
    "CANADA RIF 12345678",
    "EFT CREDIT CANADA RIT 1234",
    # A3-G re-review: after the revenue text's and the template's prefixes, glued dates included.
    "MISC PAYMENT CANADA RIT",
    "PAYMENT FROM CANADA RIT",
    "GC DIRECT DEPOSIT CANADA RIT",
    "0102DIRECT DEPOSIT CANADA RIT",
    # The classifier's own template prefixes (_strip_revenue_template), which the posting words do not list.
    "PREAUTHORIZED CREDIT CANADA RIT",
    "ELECTRONIC DEPOSIT FROM CANADA RIF 1234",
])
def test_a3g_canada_s_income_tax_refund_is_a_tax_refund(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_matched_rule) == ("non_revenue", "non_operating_credit")


@pytest.mark.parametrize("printed", [
    "CANADA RITE SUPPLY DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "RIT RIF CONSULTING DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "DIRECT DEPOSIT CANADA RIFLE CLUB",
    # A3-G review: the refund form starts the payer (after DIRECT DEPOSIT, DEP, EFT or PAY), never inside a name.
    "FABRIKAM LIFE CANADA RIF PMT",
    "NORTHWIND CANADA RIF PAYMENT",
    "ZELLE PAYMENT FROM CANADA RIT CONF 1234",
    # A benefit form is no tax refund: the owner's ruling of 2026-09-30 holds it as personal income (class B), never
    # non_revenue. (The GST/HST refund forms became tax refunds by the same ruling, class C: tested below.)
    "CANADA CHILD BENEFIT CANADA",
])
def test_a3g_a_name_or_a_benefit_form_is_no_canadian_tax_refund(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


@pytest.mark.parametrize("printed", [
    # GOV (owner ruling 2026-09-30, class C): a business's GST/HST refund, the Canada Revenue Agency's and Revenu
    # Quebec's, read as the whole payer after the posting words and template prefixes.
    "DIRECT DEPOSIT CANADA GST TPS",
    "Direct Deposit, CANADA GST/TPS",
    "DIRECT DEPOSIT CANADA GST TPS MSP DIV",
    "GST CANADA",
    "MISC PAYMENT GST CANADA",
    "GST CANADA 12345678",
    "RQ GST",
    "ELECTRONIC DEPOSIT FROM RQ GST",
    # GOV review (M4): the CRA's name after the form, a country code, and the GST program account after it.
    "CANADA GST TPS CANADA",
    "GST CANADA CA",
    "DEPOSIT CANADA GST TPS RT0001",
    # A payment the IRS issues through the Treasury with no entry, or a refund-worded entry, is a tax refund. GOV
    # review (I1): an IRS entry such as MISC PAY or VENDOR PAY is a vendor payment, tested below.
    "ELECTRONIC DEPOSIT FROM IRS TREAS 310",
    "ACH CREDIT IRS TREAS 310 XXXXXXXXXXX1234 5678",
    "Orig CO Name:IRS Treas 310 Orig ID:1234567890 Desc Date:540102 CO Entry Descr: Sec:PPD Trace#:1",
    "IRS TREAS 310 DES:TAX EIC ID:1",
    "IRS TREAS310 DES:TAX EIC ID:1",
])
def test_gov_a_government_tax_refund_is_non_revenue(printed):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_match_method, record.revenue_matched_rule) == (
        "non_revenue", "strong_non_revenue_rule", "non_operating_credit")
    assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("printed", [
    # GOV: GST inside a name, after a payer's name or on a person-to-person rail is no GST/HST refund.
    "GST CANADA LOGISTICS INC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "NORTHWIND GST SERVICES DES:PAYMENT ID:1",
    "DIRECT DEPOSIT CANADA GST TPS CONSULTING INC",
    "FABRIKAM RQ GST",
    "ZELLE PAYMENT FROM RQ GST CONF 1234",
    "INTERAC E-TRANSFER FROM NORTHWIND GST",
    # The IRS's child tax credit and stimulus are benefits (class B), held as personal income, never non_revenue; and
    # IRS inside a word is no IRS.
    "IRS TREAS 310 DES:CHILD CTC ID:1",
    "IRS TREAS 310 DES:TAX EIP3 ID:1",
    "SIRS TREASURE SUPPLY DES:PAYMENT ID:1",
])
def test_gov_a_name_or_a_benefit_is_no_government_tax_refund(printed):
    assert _credit(printed).revenue_classification != "non_revenue"


@pytest.mark.parametrize(("printed", "reading"), [
    # GOV review (I1): Treasury's Green Book gives MISC PAY to federal vendor payments, and the IRS pays its
    # contractors that way, so an IRS credit whose entry is MISC PAY, VENDOR or VENDOR PAY keeps the reading it had
    # before the owner's ruling: counted, or a public payer's vendor payment.
    ("IRS TREAS 310 DES:MISC PAY ID:1", ("unverified_deposit", "named_payer_purpose_refused")),
    ("IRS TREAS 310 DES:VENDOR ID:1", ("unverified_deposit", "named_payer_purpose_refused")),
    ("IRS TREAS 310 MISC PAY 1234", ("unverified_deposit", "named_payer_purpose_refused")),
    ("Orig CO Name:IRS Treas 310 Orig ID:1234567890 Desc Date:540102 CO Entry Descr:Misc Pay Sec:CCD Trace#:1",
     ("unverified_deposit", "named_payer_purpose_refused")),
    ("IRS TREAS 310 DES:VENDOR PAY ID:1", ("verified_revenue", "public_payer_remittance")),
])
def test_gov_review_an_irs_vendor_payment_keeps_its_reading(printed, reading):
    [record] = classify_statement_transactions(Statement(account_name="CONTOSO BAKERY LLC", transactions=[
        Transaction(date="2054-03-02", description=printed, amount=1234.0, direction="credit")]))
    state, detail = reading
    assert record.revenue_classification == state
    assert (record.revenue_match_method if state == "verified_revenue" else record.revenue_tier_reason) == detail


def test_square_capital_and_sba_proceeds_leave_eligible_deposits():
    record = _credit("SQUARE INC DES:SQ CAP1234 ID:1")
    assert record.revenue_match_method == "financing_proceeds_credit"
    assert record.contributes_to_lender_credit_exclusion


_SBA_CHASE = ("Orig CO Name:{name} Orig ID:1234567890 Desc Date:540102 CO Entry Descr:N/A Creditsec:PPD "
              "Trace#:123456789012345 Eed:540102 Ind ID: Ind Name:Contoso Bakery 123")


@pytest.mark.parametrize("printed", [
    _SBA_CHASE.format(name="Small Business"),
    _SBA_CHASE.format(name="Small Business A"),
    _SBA_CHASE.format(name="Small Business Adm"),
    "SMALL BUSINESS ADMIN DES:N/A ID:1 INDN:CONTOSO BAKERY CO ID:1 PPD",
    "WIRE TYPE:WIRE IN DATE:540102 TIME:1200 ET TRN:1 SEQ:1/2 ORIG:SMALL BUSINESS AD ID:99 SND BK:SAMPLE BANK ID:1",
])
def test_a3_the_sba_s_name_cut_to_its_originator_field_is_a_disbursement(printed):
    # A3 (precision sample): the Small Business Administration's name cut to the originator field is an SBA
    # disbursement, financing proceeds like SBAD TREAS and EIDL.
    record = _credit(printed, holder="CONTOSO BAKERY LLC")
    assert (record.revenue_classification, record.revenue_match_method, record.revenue_matched_rule) == (
        "non_revenue", "financing_proceeds_credit", "sba_disbursement_credit")
    assert record.contributes_to_lender_credit_exclusion
    statement = classify_statement_transactions(Statement(account_name="CONTOSO BAKERY LLC", transactions=[
        Transaction(date="2054-03-02", description=printed, amount=42000.0, direction="credit")]))
    assert (statement[0].revenue_tier, statement[0].revenue_matched_rule) == ("non_revenue", "sba_disbursement_credit")


@pytest.mark.parametrize("printed", [
    _SBA_CHASE.format(name="Small Business Solutions LLC").replace("N/A Creditsec:PPD", "Payment Sec:CCD"),
    "SMALL BUSINESS SOLUTIONS LLC DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "SMALL BUSINESS SUPPLY CO DES:PAYMENT ID:1 INDN:CONTOSO BAKERY CO ID:1 CCD",
    "ONLINE TRANSFER FROM SMALL BUSINESS XXXXXX1234",
])
def test_a3_a_payer_whose_name_merely_starts_with_small_business_is_no_sba_disbursement(printed):
    record = _credit(printed, holder="CONTOSO BAKERY LLC")
    assert record.revenue_classification != "non_revenue"
    assert record.revenue_matched_rule != "sba_disbursement_credit"
    assert not record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("printed", [
    "ZELLE PAYMENT FROM JOHN SMITH MEMO INVOICE PAYMENT CONF 99",
    "MOBILE DEPOSIT CUSTOMER PAYMENT REF 1234",
    "CUSTOMER DEPOSIT",
    "ZELLE PAYMENT FROM FABRIKAM SUPPLY LLC CONF 99",
    "RTP CREDIT FROM FABRIKAM LLC INV 1234",
])
def test_the_channel_gate_never_verifies(printed):
    assert _credit(printed).revenue_classification == "unverified_deposit"


def test_a_real_time_payout_verifies_through_the_registry_only():
    records = classify_statement_transactions(Statement(account_name="SAMPLE SHOP LLC", transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=f"RTP CREDIT AMAZON COM {day}", amount=400.0 + day,
                    direction="credit")
        for day in (2, 9, 16)
    ]))
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}

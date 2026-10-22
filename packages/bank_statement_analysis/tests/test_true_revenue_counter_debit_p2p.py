"""Audit round 2, batch R2-B02 (R02; true revenue spec §5.2, §8.1, §20): the counter-debit holds compare a credit with
a debit by a word that names the counterparty, never by a rail's name, a bank's label, a person's given name or a place.
A Venmo, Cash App, Square Cash or Apple Cash cash-out names no sender (§5.2), so no debit holds it; the rails' and the
bank labels' words, the US states, the provinces, CANADA, CANADIAN and AMERICAN are never the word a payer or a debit
is read by (_COUNTER_DEBIT_NOT_A_PAYER); a person-to-person or push credit whose sender prints a name of two words or
more matches a debit only on that whole name (its glued first two words), and then the same person's Zelle or
e-Transfer round trip is held as the hold's design says; an ATM, ABM or cash withdrawal never holds a deposit; RBC's
'Paiement divers COMPTE CHEQUE <n>' is the holder's own account. Review round 1: the whole name is one more arm of
the lender hold, never the only one; a company's push and a debit for the credit's own amount are matched as before;
a company named ATM or ABM is a payee; a banking-centre credit 'FR SAV' or 'FR CHKG' names an account. Fabricated rows
only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE, invented given names and towns), in the banks' printed formats; public names
only where a bank or a rail prints its own (Venmo, Zelle, Interac, Cash App, Bank of America) or a registry lists a
lender (LendCare)."""
from __future__ import annotations

import pytest

from analysis import transaction_classifier as tc
from analysis.classification import counter_debit_reading
from analysis.descriptor import payer as descriptor_payer
from analysis.descriptor import lexical
from analysis import true_revenue as tr
from analysis.true_revenue import model
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions
from tests.zelle_reading import rules_reading

HOLDER = "NORTHWIND BAKERY LLC"
P2P = ("counted_flagged", "p2p")
HELD_ALSO = ("excluded_pending_review", "payer_also_debited")


def _credits(rows, *, bank=None, holder=HOLDER):
    statement = Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2031-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ])
    return [record for record in classify_statement_transactions(statement) if record.amount > 0]


def _tier(record):
    # The owner's ruling of 2026-10-02 (the underwriter's Q3): a Zelle deposit is read through the rules' own reading,
    # its final tier (non_revenue, zelle_excluded) asserted (tests/zelle_reading.py, R2-OW02 CR7).
    return rules_reading(record)


# 1. A wallet's cash-out names no sender: no Venmo debit holds it.

CHASE_RTP_VENMO = (
    "REAL TIME TRANSFER RECD FROM ABA CONTR BNK 000000000 FROM VENMO REF 20310305123456789 INFO TEXT RMTINF "
    "INSTANT TRANSFER IID 20310305000000000P1BRJPC00000000001 RECD 12 34 56 TRN 1234567890GC"
)
VENMO_WEB = (
    "ORIG CO NAME:VENMO ORIG ID:0000000000 DESC DATE:310306 CO ENTRY DESCR:PAYMENT SEC:WEB TRACE#:000000000000000 "
    "EED:310306 IND ID:1234567890123 IND NAME:NORTHWIND BAKERY LLC TRN: 1234567891TC"
)
VENMO_VERIFY = (
    "ORIG CO NAME:VENMO ORIG ID:0000000000 DESC DATE:310301 CO ENTRY DESCR:ACCTVERIFYSEC:WEB TRACE#:000000000000000 "
    "EED:310301 IND ID:1234567890123 IND NAME:NORTHWIND BAKERY LLC TRN: 1234567892TC"
)


@pytest.mark.parametrize(("rows", "bank"), [
    ([(CHASE_RTP_VENMO, 1500.0), (VENMO_WEB, -50.0)], "Chase"),
    ([(CHASE_RTP_VENMO, 1500.0), (VENMO_VERIFY, -1.0)], "Chase"),
    # A card push to a person through Venmo, printed as a card charge '<city> <ST> USA'.
    ([(CHASE_RTP_VENMO, 1500.0), ("VENMO NEW YORK NY USA", -40.0)], "Chase"),
    ([("RTP CREDIT VENMO NEW YORK CITY 01 12345 1234567890123456", 1500.0),
      ("INTERNET PAYMENT PAYMENT VENMO 1234567890123", -300.0)], "PNC Bank"),
    ([("ELECTRONIC DEPOSIT FROM VENMO REF=000000000000000", 1500.0),
      ("ELECTRONIC WITHDRAWAL TO VENMO REF=000000000000001", -300.0)], "U.S. Bank"),
])
def test_a_wallet_cash_out_is_counted_beside_the_holder_s_wallet_debits(rows, bank):
    assert [_tier(record) for record in _credits(rows, bank=bank)] == [P2P]


@pytest.mark.parametrize("region", ["VENMO", "VENMO NEW YORK CITY 01", "CASH APP", "CASHAPP", "SQUARE CASH",
                                    "APPLE CASH"])
def test_a_wallet_s_name_is_no_sender_the_counter_debit_holds_read(region):
    record = tc.classify_transaction("RTP CREDIT CONTOSO", 500.0, direction="credit")
    counter = tr.counter_credit(record, "RTP CREDIT CONTOSO", region)
    assert counter.reading.legacy is None and not counter.reading.keys


# 2. A rail's name, a bank's label, a state, a province and a nation are never the payer's word.

@pytest.mark.parametrize("word", [
    "ZELLE", "INTERAC", "VENMO", "POPMONEY", "AUTODEPOSIT", "CASHAPP", "PAIEMENT", "TEXAS", "CALIFORNIA", "YORK",
    "CAROLINA", "ONTARIO", "ALBERTA", "CANADA", "CANADIAN", "AMERICAN",
])
def test_the_words_that_name_no_payer(word):
    assert word in counter_debit_reading._COUNTER_DEBIT_NOT_A_PAYER


def test_the_payer_reading_skips_them_and_the_receiver_originators_keep_theirs():
    reading = counter_debit_reading.counter_debit_payer_reading("TEXAS CONTOSO LLC")
    assert reading.legacy == "CONTOSO" and "TEXAS" not in reading.keys
    # The receiver-originator grouping reads the payer's first distinctive word unchanged.
    assert counter_debit_reading._payer_first_distinctive_word("TEXAS CONTOSO LLC") == "TEXAS"
    debit = tc.classify_transaction("ZELLE PAYMENT TO PRIYA SAMPLE CONF ABC123", -400.0, direction="debit")
    reading, _ = counter_debit_reading.counter_debit_debit_reading(debit)
    assert reading.legacy == "PRIYA" and "PRIYASAMPLE" in reading.keys and "ZELLE" not in reading.keys


def test_a_company_named_for_its_state_is_compared_by_its_own_name():
    other = _credits([("TEXAS CONTOSO LLC DES:PAYMENT ID:1", 540.0), ("TEXAS FABRIKAM DES:INVOICE ID:2", -540.0)])
    assert other[0].revenue_tier == "verified"
    same = _credits([("TEXAS CONTOSO LLC DES:PAYMENT ID:1", 540.0), ("TEXAS CONTOSO DES:INVOICE ID:2", -540.0)])
    assert _tier(same[0]) == HELD_ALSO


def test_rbc_s_french_label_never_names_a_customer_after_a_lender():
    rows = [("Paiement divers CONTOSO CONSTRUCTION", 3500.0), ("Paiement divers LendCare", -236.0),
            ("Paiement divers LendCare", -236.0)]
    assert _credits(rows, bank="Royal Bank of Canada")[0].revenue_tier == "counted_flagged"


@pytest.mark.parametrize("text", ["Paiement divers COMPTE CHEQUE 1234567", "Paiement divers COMPTE EPARGNE 1234567"])
def test_rbc_s_french_label_before_the_holder_s_own_account_is_held(text):
    for rows in ([(text, 1400.0), ("Paiement divers LendCare", -236.0)], [(text, 1400.0)]):
        assert _tier(_credits(rows, bank="Royal Bank of Canada")[0]) == (
            "excluded_pending_review", "transfer_account_designation")


def test_a_company_paid_and_paying_by_ach_stays_held():
    rows = [("CONTOSO SUPPLY DES:PAYMENT ID:1", 2000.0), ("CONTOSO SUPPLY DES:PAYMENT ID:2", -500.0)]
    assert _tier(_credits(rows)[0]) == HELD_ALSO


# 3. A person-to-person or push credit from a named person matches only that person's whole name.

ZELLE_IN_WF = "ZELLE FROM QUILLAN SAMPLE ON 03/02 REF # WFCT0ABCDEF1"


@pytest.mark.parametrize(("debit", "tier"), [
    ("ONLINE TRANSFER TO QUILLAN CONTOSO EVERYDAY CHECKING XXXXXX1234 REF #IB0ABCDEF1 ON 03/04/31", P2P),
    ("ONLINE TRANSFER TO QUILLAN SAMPLE EVERYDAY CHECKING XXXXXX1234 REF #IB0ABCDEF1 ON 03/04/31", HELD_ALSO),
])
def test_a_zelle_from_a_customer_is_held_only_beside_a_transfer_to_the_same_person(debit, tier):
    assert [_tier(record) for record in _credits([(ZELLE_IN_WF, 3200.0), (debit, -300.0)], bank="Wells Fargo")] == [
        tier]


def test_only_an_e_transfer_s_sender_printed_without_from_is_read_for_the_holds():
    # A wallet's push printing a one-word display name without FROM reads no counter-debit payer (as before the batch).
    rows = [("CASH APP CONTOSO 03 02 000000001 PMNT RCVD CASH APP CONTOSO EG 0000000000 CA", 300.0),
            ("PMNT SENT 0312 CASH APP*CONTOSO 0000000000 CA", -60.0)]
    assert [_tier(record) for record in _credits(rows, bank="Bank of America")] == [P2P]
    assert tr._counter_region("CASH APP CONTOSO PMNT RCVD CASH APP CONTOSO", "") == ""
    assert tr._counter_region("E TRANSFER AUTODEPOSIT CONTOSO SAMPLE", "") == "CONTOSO SAMPLE"


def test_a_cash_app_push_to_a_person_sharing_the_sender_s_given_name_holds_nothing():
    rows = [("Zelle payment from QUILLAN SAMPLE Conf# abc12def3", 3200.0),
            ("PMNT SENT 0312 CASH APP*QUILLAN 0000000000 CA", -60.0)]
    assert [_tier(record) for record in _credits(rows, bank="Bank of America")] == [P2P]


@pytest.mark.parametrize(("credit", "debit", "bank"), [
    ("Zelle payment from {name} Conf# abc12def3", "Zelle payment to {name} Conf# abc12def4", "Bank of America"),
    ("ZELLE FROM {name} ON 03/02 REF # WFCT0ABCDEF1", "ZELLE TO {name} ON 03/04 REF # WFCT0ABCDEF2", "Wells Fargo"),
    ("Zelle Payment From {name} Jpm99abcdef1", "Zelle Payment To {name} Jpm99abcdef2", "Chase"),
    ("ZELLE INSTANT PMT FROM {name}", "ZELLE INSTANT PMT TO {name}", "U.S. Bank"),
    ("e-Transfer received {name}", "INTERAC E-TRANSFER SENT {name}", "Royal Bank of Canada"),
])
def test_a_same_person_zelle_or_e_transfer_round_trip_is_held(credit, debit, bank):
    rows = [(credit.format(name="PRIYA SAMPLE"), 900.0), (debit.format(name="PRIYA SAMPLE"), -400.0)]
    assert [_tier(record) for record in _credits(rows, bank=bank)] == [HELD_ALSO]
    other = [(credit.format(name="PRIYA SAMPLE"), 900.0), (debit.format(name="PRIYA FABRIKAM"), -400.0)]
    assert [_tier(record) for record in _credits(other, bank=bank)] == [P2P]


@pytest.mark.parametrize(("region", "key"), [
    ("PRIYA SAMPLE", "PRIYASAMPLE"),
    ("QUILLAN SAMPLE JONES", "QUILLANSAMPLE"),
    ("CONTOSO PLUMBING LLC", "CONTOSOPLUMBING"),
    # A name ends at its legal form: the town a payout prints after it is no part of it.
    ("CONTOSO INC SAMPLEVILLE CA", None),
    ("PRIYA", None),
    ("", None),
])
def test_the_sender_s_whole_name_key(region, key):
    assert tr._sender_name_key(region) == key


def test_a_named_p2p_credit_matches_a_lender_debit_by_its_whole_name_and_as_before():
    # Review round 1 (finding 1): the whole name is one more way a person-to-person or push credit names a lender
    # debit, never the only one. The lender hold never lets a funder's money into True, so a lender debit sharing the
    # sender's first word still holds it, for review (the hold's safe direction).
    reading = counter_debit_reading._counter_debit_reading("QUILLAN", [["QUILLAN", "SAMPLE"]])
    credit = model.CounterCredit(reading, 90000, None, False, False, person_key="QUILLANSAMPLE")

    def lender(words, entity=None):
        return model.CounterDebits((model._CounterDebit(counter_debit_reading._counter_debit_reading(words[0], [words]), "lender", 30000,
                                                  entity, False),), ())

    assert tr.debited_as_lender(credit, lender(["QUILLAN", "FUNDING"]), prefix=True)
    assert tr.debited_as_lender(credit, lender(["QUILLAN", "SAMPLE"]), prefix=True)
    assert not tr.debited_as_lender(credit, lender(["FABRIKAM", "FUNDING"]), prefix=True)
    named = model.CounterCredit(reading, 90000, "Sample Lender", False, False, person_key="QUILLANSAMPLE")
    assert tr.debited_as_lender(named, lender(["FABRIKAM"], "Sample Lender"), prefix=False)


WEEKLY = [2, 9, 16, 23, 30]


def _weekly(rows, *, bank=None):
    statement = Statement(account_name=HOLDER, bank=bank, transactions=[
        Transaction(date=f"2031-03-{day:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for day, (text, amount) in zip(WEEKLY, rows)
    ])
    return classify_statement_transactions(statement)


def test_a_company_s_push_beside_its_own_weekly_pulls_is_still_held_as_a_funder_s():
    # The whole-name match is for a person's name: a company sending by a person-to-person or push rail is compared
    # with the lender's debits as before (a funder's own push).
    records = _weekly([("ZELLE PAYMENT FROM CONTOSO PARTNERS LLC CONF 1234567890", 9000.0),
                       *[("CONTOSO DES:DEBIT ID:2", -300.0)] * 4])
    assert {record.classification for record in records[1:]} == {"potential_lender"}
    assert _tier(records[0]) == ("excluded_pending_review", "payer_debited_as_lender")


def test_a_funder_named_for_a_state_is_still_held_beside_its_glued_pulls():
    # The lender hold keeps the place words: the funder's own name may carry a state's.
    records = _weekly([("DEPOSIT WIRE IN TEXAS SAMPLE", 5000.0),
                       *[("ACH WITHDRAWAL TEXASSAMPLEHO ACHPAYMENT TS1234 NORTHWIND BAKERY", -1600.0)] * 4])
    assert {record.classification for record in records[1:]} == {"potential_lender"}
    assert _tier(records[0]) == ("excluded_pending_review", "payer_debited_as_lender")


# Review round 1 (finding 1): a funder that prints no legal form and no financing root, pushing by a real-time,
# Zelle or Chase real-time rail and pulling under a glued or one-word name, is still held as a funder's.
VENTURE_PULL = "ACH WITHDRAWAL CONTOSOVENTUREHO ACHPAYMENT TS1234 NORTHWIND BAKERY"
CHASE_RTP_VENTURE = (
    "REAL TIME TRANSFER RECD FROM ABA CONTR BNK 000000000 FROM CONTOSO VENTURE REF 20310305123456789 INFO TEXT "
    "RMTINF FUNDING IID 20310305000000000P1BRJPC00000000001 RECD 12 34 56 TRN 1234567890GC"
)


@pytest.mark.parametrize(("rows", "bank"), [
    ([("RTP CREDIT CONTOSO VENTURE", 9000.0), *[(VENTURE_PULL, -300.0)] * 4], None),
    ([("ZELLE PAYMENT FROM CONTOSO VENTURE CONF 1234567890", 9000.0), *[(VENTURE_PULL, -300.0)] * 4], None),
    ([("RTP CREDIT CONTOSO VENTURE", 9000.0), *[("CONTOSO DES:DEBIT ID:2", -300.0)] * 4], None),
    ([(CHASE_RTP_VENTURE, 9000.0), *[(VENTURE_PULL, -300.0)] * 4], "Chase"),
    ([("ZELLE PAYMENT FROM CONTOSO VENTURE CONF 1234567890", 9000.0), *[(VENTURE_PULL, -300.0)] * 3,
      (VENTURE_PULL, -9000.0)], None),
])
def test_a_funder_s_push_without_a_legal_form_is_still_held_beside_its_pulls(rows, bank):
    records = _weekly(rows, bank=bank)
    assert "potential_lender" in {record.classification for record in records[1:]}
    assert _tier(records[0]) == ("excluded_pending_review", "payer_debited_as_lender")


# Review round 1 (finding 3): the whole-name match never drops a match the holds made before the batch: a company's
# push (its sender prints a legal form) is compared by the B4 forms, and a debit for the credit's own amount still
# matches the sender's first word (the credit undoes it).

COMPANY_ZELLE = "ZELLE PAYMENT FROM CONTOSO PARTNERS LLC CONF 1234567890"


@pytest.mark.parametrize(("rows", "bank"), [
    ([(COMPANY_ZELLE, 9000.0), ("CONTOSO DES:DEBIT ID:2", -9000.0)], None),
    ([(COMPANY_ZELLE, 9000.0), ("CONTOSO DES:DEBIT ID:2", -300.0)], None),
    ([(COMPANY_ZELLE, 9000.0), ("ONLINE TRANSFER TO CONTOSO REF 1", -300.0)], None),
    ([(ZELLE_IN_WF, 900.0),
      ("ONLINE TRANSFER TO QUILLAN EVERYDAY CHECKING XXXXXX1234 REF #IB0ABCDEF1 ON 03/04/31", -900.0)], "Wells Fargo"),
])
def test_a_company_s_push_and_a_debit_for_the_credit_s_own_amount_are_matched_as_before(rows, bank):
    assert [_tier(record) for record in _credits(rows, bank=bank)] == [HELD_ALSO]


def test_a_person_s_push_beside_another_amount_to_the_given_name_alone_is_still_counted():
    rows = [(ZELLE_IN_WF, 900.0),
            ("ONLINE TRANSFER TO QUILLAN EVERYDAY CHECKING XXXXXX1234 REF #IB0ABCDEF1 ON 03/04/31", -300.0)]
    assert [_tier(record) for record in _credits(rows, bank="Wells Fargo")] == [P2P]


def test_the_whole_name_key_is_a_person_s_never_a_company_s():
    company = tc.classify_transaction(COMPANY_ZELLE, 9000.0, direction="credit")
    revenue = lexical.revenue_text(company.normalized_description)
    assert tr.counter_credit(company, revenue, descriptor_payer.payer_region(revenue)).person_key is None
    person = tc.classify_transaction("ZELLE PAYMENT FROM QUILLAN SAMPLE CONF 1234567890", 900.0, direction="credit")
    revenue = lexical.revenue_text(person.normalized_description)
    assert tr.counter_credit(person, revenue, descriptor_payer.payer_region(revenue)).person_key == "QUILLANSAMPLE"


@pytest.mark.parametrize(("credit", "debit", "tier"), [
    # A wire from one company beside a Zelle to another sharing its first word: the debit's recipient prints two
    # words, so only the whole name names it.
    ("WIRE TYPE:WIRE IN DATE:310302 TIME:1200 ET TRN:1 SEQ:1/2 ORIG:CONTOSO SAMPLE LLC ID:99 SND BK:SAMPLE BANK ID:1",
     "ZELLE PAYMENT TO CONTOSO FABRIKAM CONF 1234567890", ("counted_flagged", "wire_named_sender")),
    ("WIRE TYPE:WIRE IN DATE:310302 TIME:1200 ET TRN:1 SEQ:1/2 ORIG:CONTOSO SAMPLE LLC ID:99 SND BK:SAMPLE BANK ID:1",
     "ZELLE PAYMENT TO CONTOSO SAMPLE CONF 1234567890", HELD_ALSO),
])
def test_a_zelle_debit_to_a_named_recipient_names_only_that_whole_name(credit, debit, tier):
    assert [_tier(record) for record in _credits([(credit, 15000.0), (debit, -4000.0)], bank="Bank of America")] == [
        tier]


# 4. An ATM, ABM or cash withdrawal never holds a deposit; a transfer at an ATM is still circular.

def test_a_branch_deposit_is_counted_beside_a_cash_withdrawal_in_its_town():
    rows = [("DEPOSIT SAMPLEVILLE ON", 4000.0), ("ABM WITHDRAWAL SAMPLEVILLE ON SAMPLEVILLE", -200.0)]
    assert _credits(rows, bank="Scotiabank")[0].revenue_tier == "counted_flagged"


@pytest.mark.parametrize(("text", "kept"), [
    ("ABM WITHDRAWAL SAMPLEVILLE ON SAMPLEVILLE", False),
    ("BKOFAMERICA ATM 03/02 #000000000 WITHDRWL SAMPLEVILLE", False),
    ("CASH WITHDRAWAL SAMPLEVILLE BRANCH", False),
    ("ATM WITHDRAWAL SAMPLEVILLE CO", False),
    ("ATM SH TO SH TRANSFER - SAMPLEVILLE", True),
    ("CONTOSO SUPPLY DES:INVOICE ID:2", True),
    # Review round 1 (finding 6b): a company named ATM or ABM, or an ACH entry printing one, is a payee.
    ("ABM FABRIKAM DES:PAYMENT ID:2", True),
    ("ATM FABRIKAM INC 1234", True),
    ("ABM SAMPLE SUPPLY LLC INVOICE 1234", True),
    # Audit round 3, R3-B16 (R3-34): the window between ATM or ABM and the legal form is no cash or posting label, so
    # a withdrawal printing a one-word company name is still a cash withdrawal; a company named ATM keeps its debit.
    ("ATM WITHDRAWAL FABRIKAM INC SAMPLEVILLE", False),
    ("ATM DEBIT FABRIKAM LLC", False),
    ("ABM WITHDRAWAL FABRIKAM LTD", False),
    ("ATM CONTOSO GROUP LLC", True),
])
def test_the_counter_debits_leave_out_atm_abm_and_cash_withdrawals(text, kept):
    record = tc.classify_transaction(text, -200.0, direction="debit")
    debits = tr.counter_debits([record], set())
    assert bool(debits.other) is kept


def test_a_company_named_abm_paid_and_paying_stays_held():
    rows = [("ABM FABRIKAM DES:PAYMENT ID:1", 2000.0), ("ABM FABRIKAM DES:PAYMENT ID:2", -500.0)]
    assert _tier(_credits(rows)[0]) == HELD_ALSO


# Review round 1 (finding 2): a banking-centre credit from an account ('BKOFAMERICA BC <date> <ref> FR SAV', 'FR CHKG')
# names an account, never a payer: held as transfer_account_designation (T13), whatever debits the statement prints
# (it no longer depends on an ATM withdrawal at the same bank holding it by the bank's word).

@pytest.mark.parametrize("debits", [
    [],
    [("BKOFAMERICA ATM 03/03 #000000001 WITHDRWL SAMPLEVILLE", -200.0)],
    [("ONLINE BANKING TRANSFER TO SAV 1234", -200.0)],
])
@pytest.mark.parametrize("credit", [
    "BKOFAMERICA BC 03/02 #000000000 FR SAV",
    "BKOFAMERICA BC 03/02 #000000000 FR CHKG",
])
def test_a_banking_centre_credit_from_an_account_is_held_as_naming_an_account(credit, debits):
    rows = [(credit, 1300.0), *debits]
    assert [_tier(record) for record in _credits(rows, bank="Bank of America")] == [
        ("excluded_pending_review", "transfer_account_designation")]


# --- Audit round 3, R3-B16 --------------------------------------------------------------------------------------------
# R3-34 (standard A6; R2-B02 R02): an ATM withdrawal names a place, never a payer. The carve-out for a company whose
# name leads with ATM or ABM reads a legal form within the next two words, none of them a cash or posting word, so an
# ATM withdrawal printing a one-word company name keeps the cash-withdrawal exclusion. Fabricated rows, 2054 dates.

@pytest.mark.parametrize(("text", "withdrawal"), [
    ("ATM WITHDRAWAL FABRIKAM INC SAMPLEVILLE", True),
    ("ATM DEBIT FABRIKAM LLC", True),
    ("ABM WITHDRAWAL FABRIKAM LTD", True),
    ("ATM CASH FABRIKAM LLC", True),
    ("ATM WITHDRAWAL SAMPLEVILLE CO", True),
    ("ATM FABRIKAM INC 1234", False),
    ("ABM SAMPLE SUPPLY LLC INVOICE 1234", False),
    ("ATM SERVICES GROUP LLC", False),
    ("ATM CONTOSO GROUP LLC", False),
])
def test_r3_34_the_atm_company_carve_out_never_reads_a_cash_or_posting_word(text, withdrawal):
    assert tr._cash_withdrawal(text) is withdrawal


def test_r3_34_a_remittance_reads_as_without_an_atm_withdrawal_printing_a_company_s_name():
    def credits(rows):
        statement = Statement(account_name=HOLDER, bank="Bank of America", transactions=[
            Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                        direction="credit" if amount > 0 else "debit")
            for index, (text, amount) in enumerate(rows)
        ])
        return [(record.revenue_tier, record.revenue_match_method)
                for record in classify_statement_transactions(statement) if record.amount > 0]

    remittance = ("FABRIKAM INC DES:INV PMT ID:0001 INDN:NORTHWIND BAKERY LLC CO ID:0000000001 CCD", 1800.0)
    assert credits([remittance, ("ATM WITHDRAWAL FABRIKAM INC SAMPLEVILLE", -200.0)]) == credits([remittance]) == [
        ("verified", "payer_remittance_descriptor")]


# --- Audit round 3, R3-B17 (R3-15; standard C1, B6, A17; §8.1's purpose of the counter-debit holds; OQ3) -------------
# An e-Transfer round trip with a numbered company is compared by the company's number, as the same rows with a word
# name are held: the autodeposit's sender and the sent transfer's recipient read the same number. Fabricated numbers.

ETRANSFER_IN = "E-TRANSFER - AUTODEPOSIT {payer} CA0000AB"


@pytest.mark.parametrize(("payer", "recipient", "expected"), [
    # Today counted p2p: both readings were empty (the number is no word, ALBERTA a place word, LTD noise).
    pytest.param("1234567 ALBERTA LTD", "1234567 ALBERTA LTD - CONTOSO", HELD_ALSO, id="same-number"),
    pytest.param("1234567 ALBERTA LTD", "7654321 ALBERTA LTD - CONTOSO", P2P, id="another-number"),
    # The word-named twin, held as before.
    pytest.param("FABRIKAM TRADING LTD", "FABRIKAM TRADING LTD - CONTOSO", HELD_ALSO, id="word-named"),
])
def test_r3_15_an_e_transfer_round_trip_with_a_numbered_company_is_held(payer, recipient, expected):
    rows = [(ETRANSFER_IN.format(payer=payer), 2150.0), (f"E-TRANSFER SENT {recipient}", -1500.0)]
    assert [_tier(record) for record in _credits(rows, bank="Royal Bank of Canada")] == [expected]
    assert [_tier(record) for record in _credits(rows[:1], bank="Royal Bank of Canada")] == [P2P]

"""Classification 5.5 (true revenue spec §7.0, §7.1, §7.8, §7.10): the operating-source recurrence pass: the pool, its
veto, the absolute micro-deposit floor, legal-form holders, NET SETTLE, the wholesale auctions and the property
platforms. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions


def _statement(rows, *, holder: str | None = "SAMPLE CAFE", bank: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                    direction=direction or ("credit" if amount > 0 else "debit"))
        for day, text, amount, *rest in rows
        for direction in [rest[0] if rest else None]
    ]))


def _methods(records):
    return [record.revenue_match_method for record in records if record.amount > 0]


def test_a_per_row_upgrade_never_shrinks_the_pool():
    # One Square row verifies by its payout id; the other two still count it toward three.
    records = _statement([(2, "SQUARE INC DES:SQ540102 ID:1", 300.0), (9, "SQUARE INC DES:TRANSFER ID:2", 310.0),
                          (16, "SQUARE INC DES:TRANSFER ID:3", 320.0)])
    assert _methods(records) == [
        "operating_source_with_credit_context", "recurring_operating_source", "recurring_operating_source"]


def test_the_recurrence_veto_keeps_financing_and_pay_out_of_the_pool():
    records = _statement([(2, "SQUARE INC DES:TRANSFER ID:1", 300.0), (9, "SQUARE INC DES:TRANSFER ID:2", 310.0),
                          (16, "SQUARE INC DES:SQ CAP1234 ID:3", 5000.0), (20, "SHIFT4 PAYMENTS DES:CAP ADV ID:4", 900.0),
                          (23, "SUMUP DES:CASH ADV ID:5", 800.0)])
    assert [record.revenue_classification for record in records] == [
        "unverified_deposit", "unverified_deposit", "non_revenue", "unverified_deposit", "unverified_deposit"]
    weekly_pay = _statement([(day, "HEARTLAND PAYMENT SYSTEMS DES:PAYROLL ID:1", 700.0) for day in (2, 9, 16, 23)])
    assert {record.revenue_classification for record in weekly_pay} == {"unverified_deposit"}


def test_a_holder_named_like_a_veto_word_keeps_its_own_settlements():
    rows = [(day, f"SQUARE INC DES:TRANSFER ID:{day}", 300.0 + day) for day in (2, 9, 16)]
    assert set(_methods(_statement(rows, holder="FABRIKAM PAYROLL SERVICES LLC"))) == {"recurring_operating_source"}
    # A delivery platform prints the holder's store name in its entry field.
    store = [(day, f"DOORDASH INC DES:FABRIKAM CAPITA ID:ST-A1B2C{day} INDN:FABRIKAM CAPITAL GROUP CO ID:1 CCD",
              200.0 + day) for day in (2, 9, 16)]
    assert set(_methods(_statement(store, holder=None))) == {"recurring_operating_source"}


def test_three_mis_signed_rows_are_never_grouped():
    rows = [(day, "ELAVON DES:DEPOSIT ID:1", 300.0 + day, "debit") for day in (2, 9, 16)]
    assert set(_methods(_statement(rows))) == {"direction_conflict"}


def test_a_micro_deposit_never_counts_and_is_never_lifted():
    rows = [(2, "PAYPAL DES:TRANSFER ID:1", 400.0), (9, "PAYPAL DES:TRANSFER ID:2", 410.0),
            (16, "PAYPAL DES:TRANSFER ID:3", 0.03)]
    records = _statement(rows, holder="SAMPLE CAFE")
    assert [record.revenue_classification for record in records] == ["unverified_deposit"] * 3
    four = _statement([*rows, (23, "PAYPAL DES:TRANSFER ID:4", 420.0)])
    assert [record.revenue_classification for record in four] == [
        "verified_revenue", "verified_revenue", "unverified_deposit", "verified_revenue"]


def test_a_legal_form_holder_is_a_business_account_except_for_a_customer_payment_platform():
    stripe = [(2, "STRIPE DES:TRANSFER ID:1", 400.0), (9, "STRIPE DES:TRANSFER ID:2", 410.0)]
    assert set(_methods(_statement(stripe, holder="SAMPLE CAFE LLC"))) == {"recurring_operating_source"}
    assert set(_methods(_statement(stripe, holder="SAMPLE CAFE"))) == {"operating_source_requires_context"}
    paypal = [(2, "PAYPAL DES:TRANSFER ID:1", 400.0), (9, "PAYPAL DES:TRANSFER ID:2", 410.0)]
    assert set(_methods(_statement(paypal, holder="SAMPLE CAFE LLC"))) == {"operating_source_requires_context"}
    assert set(_methods(_statement(paypal, holder="SAMPLE CAFE BUSINESS CHECKING"))) == {"recurring_operating_source"}


def test_net_settle_from_an_unregistered_originator_needs_three_credits():
    three = [(day, f"FABRIKAM MERCHANT DES:NET SETTLE ID:{day}", 900.0 + day) for day in (2, 9, 16)]
    assert {record.revenue_matched_rule for record in _statement(three)} == {"card_settlement_form_net_settle"}
    assert _statement(three[:1])[0].revenue_classification == "unverified_deposit"


def test_an_auction_verifies_only_its_payout_form():
    records = _statement([(2, "MANHEIM US DES:ACH PAYMNT ID:1", 18000.0),
                          (5, "MANHEIM US DES:ADJUSTMENT ID:2", 150.0),
                          (9, "ACV AUCTIONS INC PAYMENTS 1234", 12000.0),
                          (12, "ACV AUCTIONS INC PAYMENTS PYMT1234567", 8200.0),
                          (16, "BACKLOTCARS PAYMENT 123456 7654321", 9500.0)])
    assert [record.revenue_matched_rule for record in records] == [
        "wholesale_auto_auction_proceeds", "auction_credit_without_payout_form", "wholesale_auto_auction_proceeds",
        "auction_credit_prints_buyer_payment_reference", "wholesale_auto_auction_proceeds"]


def test_an_auction_credit_paired_with_an_equal_auction_debit_stays_unverified():
    records = _statement([(2, "MANHEIM ACH PAYMNT PURCHASE 1234", -18000.0),
                          (9, "MANHEIM US DES:EDI PYMNTS ID:1", 18000.0)])
    assert records[1].revenue_matched_rule == "auction_credit_matches_same_source_debit"


def test_an_auction_alias_outside_the_originator_never_counts():
    for printed in ("ZELLE PAYMENT FROM FABRIKAM FOR MANHEIM US ACH PAYMNT CONF 1",
                    "FABRIKAM MOTORS DES:PAYMENT ID:1 INDN:MANHEIM US CO ID:1 CCD"):
        assert _statement([(2, printed, 5000.0)])[0].revenue_classification == "unverified_deposit"
    assert _statement([(2, "MANHEIM US DES:ACH PAYMNT ID:1", 0.5)])[0].revenue_classification == "unverified_deposit"


def test_a_property_platform_verifies_by_ach_recurrence_only():
    ach = [(day, f"ORIG CO NAME BUILDIUM ORIG ID 123 DESC DATE CO ENTRY DESCR FUNDING SEC CCD TRACE {day}",
            1500.0 + day) for day in (2, 9, 16)]
    records = _statement(ach, holder="SAMPLE PROPERTIES")
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}
    assert all("property_management_collections" in record.revenue_context_signals for record in records)
    # One row alone, even with ACH CREDIT context words, stays unverified.
    lone = _statement([(2, "ACH CREDIT BUILDIUM SETTLEMENT", 1500.0)], holder="SAMPLE PROPERTIES")
    assert lone[0].revenue_match_method == "operating_source_requires_context"
    # A fee debit plus one credit is no recurrence.
    fee = _statement([(2, "BUILDIUM DES:FUNDING ID:1", 1500.0), (3, "BUILDIUM PROCESSING FEE", -30.0)])
    assert fee[0].revenue_classification == "unverified_deposit"


def test_a_property_platform_never_pools_push_shapes_micro_deposits_or_owner_wording():
    mixed = _statement([(2, "APPFOLIO VISA DIRECT PAYOUT", 900.0), (9, "APPFOLIO PMNT RCVD", 950.0)],
                       holder="SAMPLE PROPERTIES LLC")
    assert {record.revenue_classification for record in mixed} == {"unverified_deposit"}
    micro = _statement([(2, "APPFOLIO DES:ACCTVERIFY ID:1", 0.12), (3, "APPFOLIO DES:ACCTVERIFY ID:2", 0.21)],
                       holder="SAMPLE PROPERTIES LLC")
    assert {record.revenue_classification for record in micro} == {"non_revenue"}
    owner = _statement([(day, f"BUILDIUM DES:OWNER DIST ID:{day}", 1500.0 + day) for day in (2, 9, 16)])
    assert {record.revenue_matched_rule for record in owner} == {"property_platform_owner_or_deposit_wording"}


# ---------------------------------------------------------------------------------------------------------------------
# §14.1's §7.8 negatives (review I5), and FUNDING outside the three platforms that print it on settlements (review C2).
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("word", ["FUNDING", "FUNDNG", "ADVANCE", "CAPTL", "FLOORPLAN", "FLOOR PLAN", "FINANCING",
                                  "NGC", "PPD"])
def test_an_auction_payout_printing_a_financing_or_consumer_word_never_verifies(word):
    records = _statement([(2, f"MANHEIM US DES:ACH PAYMNT {word} ID:1", 18000.0),
                          (9, f"MANHEIM US DES:ACH PAYMNT {word} ID:2", 17000.0),
                          (16, f"MANHEIM US DES:ACH PAYMNT {word} ID:3", 16000.0)], holder="SAMPLE MOTORS LLC")
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}


@pytest.mark.parametrize("printed", [
    "MANHEIM US DES:DEALSHIELD ID:1", "MANHEIM US DES:ARB CREDIT ID:1", "MANHEIM US DES:PAYROLL ID:1",
    "MANHEIM US DES:DIR DEP ID:1", "ACV AUCTIONS INC PAYMENTS PAYROLL", "DEBIT CARD CREDIT MANHEIM US ATLANTA GA",
])
def test_the_auction_s_own_negatives_never_verify(printed):
    records = _statement([(2, printed, 1500.0), (9, printed.replace("ID:1", "ID:2"), 1600.0),
                          (16, printed.replace("ID:1", "ID:3"), 1700.0)], holder="SAMPLE MOTORS LLC")
    assert {record.revenue_classification for record in records} <= {"unverified_deposit", "non_revenue"}


@pytest.mark.parametrize("printed", [
    "FABRIKAM MOTORS DES:PAYMENT ID:1 IND NAME:MANHEIM US", "FABRIKAM MOTORS DES:DISBURSEMENT ID:1 INDN:MANHEIM US",
    "ZELLE PAYMENT FROM JOHN SMITH MEMO MANHEIM US ACH PAYMNT CONF 1",
    "ZELLE PAYMENT TO MANHEIM US ACH PAYMNT DISBURSEMENT CONF 1",
])
def test_an_auction_alias_in_a_receiver_field_a_zelle_field_or_a_memo_never_names_the_auction(printed):
    records = _statement([(2, printed, 1500.0), (9, printed.replace("ID:1", "ID:2"), 1600.0),
                          (16, printed.replace("ID:1", "ID:3"), 1700.0)], holder="SAMPLE MOTORS LLC")
    assert not {record.revenue_canonical_entity for record in records} & {"Manheim", "ACV Auctions", "OPENLANE"}


@pytest.mark.parametrize("printed", ["ACV CAPITAL DES:FUNDING ID:1", "NEXTGEAR CAPITAL DES:ADVANCE ID:1",
                                     "KINETIC ADVANTAGE DES:PAYMENT ID:1", "WESTLAKE FLOORING DES:PAYMENT ID:1"])
def test_the_floor_plan_lenders_stay_financing_proceeds(printed):
    [record] = _statement([(2, printed, 15000.0)], holder="SAMPLE MOTORS LLC")
    assert (record.revenue_classification, record.revenue_match_method) == ("non_revenue", "financing_proceeds_credit")


def test_an_afc_funding_credit_never_verifies():
    [record] = _statement([(2, "AFC FUNDNG DES:PAYMENT ID:1", 15000.0)], holder="SAMPLE MOTORS LLC")
    assert record.revenue_classification != "verified_revenue"


def test_an_auction_credit_paired_with_a_wire_to_the_auction_stays_unverified():
    records = _statement([(2, "WIRE TYPE:WIRE OUT DATE:540302 TIME:0900 ET TRN:1 BNF:MANHEIM US ID:1", -18000.0),
                          (9, "MANHEIM US DES:ACH PAYMNT ID:1", 18000.0)], holder="SAMPLE MOTORS LLC")
    assert records[1].revenue_matched_rule == "auction_credit_matches_same_source_debit"


def test_a_duplicated_auction_payout_is_non_revenue():
    records = classify_statement_transactions(Statement(account_name="SAMPLE MOTORS LLC", transactions=[
        Transaction(date="2054-03-02", description="MANHEIM US DES:ACH PAYMNT ID:1", amount=18000.0,
                    direction="credit", running_balance=19000.0),
        Transaction(date="2054-03-02", description="MANHEIM US DES:ACH PAYMNT ID:1", amount=18000.0,
                    direction="credit", running_balance=19000.0),
    ]))
    assert [record.revenue_classification for record in records] == ["verified_revenue", "non_revenue"]


def test_funding_vetoes_recurrence_except_on_the_three_platforms_that_print_it_on_settlements():
    etsy = _statement([(day, f"ETSY DES:FUNDING ID:{day}", 900.0 + day) for day in (2, 9, 16)])
    assert {record.revenue_classification for record in etsy} == {"unverified_deposit"}
    tapgoods = _statement([(day, f"TGPAYMENTS DES:FUNDING ID:{day}", 900.0 + day) for day in (2, 9, 16)])
    assert {record.revenue_match_method for record in tapgoods} == {"recurring_operating_source"}


# ---------------------------------------------------------------------------------------------------------------------
# S2.4 review: a vetoed auction or property row carries its branch's rule; the reversal pair reads the return codes
# (pass 4).
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("word", ["FUNDING", "FUNDNG", "ADVANCE", "CAPTL", "FLOORPLAN", "FLOOR PLAN", "FINANCING",
                                  "NGC", "PPD"])
def test_an_auction_payout_printing_a_financing_or_consumer_word_carries_its_rule(word):
    # FUNDING, ADVANCE and FINANCING are recurrence vetoes too: the vetoed row still carries the auction's rule.
    records = _statement([(2, f"MANHEIM US DES:ACH PAYMNT {word} ID:1", 18000.0),
                          (9, f"MANHEIM US DES:ACH PAYMNT {word} ID:2", 17000.0),
                          (16, f"MANHEIM US DES:ACH PAYMNT {word} ID:3", 16000.0)], holder="SAMPLE MOTORS LLC")
    assert {(record.revenue_classification, record.revenue_matched_rule) for record in records} == {
        ("unverified_deposit", "auction_credit_prints_financing_or_consumer_word")}


def test_a_vetoed_auction_row_without_its_payout_form_carries_that_rule():
    records = _statement([(day, f"MANHEIM US DES:PAYROLL ID:{day}", 1500.0 + day) for day in (2, 9, 16)],
                         holder="SAMPLE MOTORS LLC")
    assert {(record.revenue_classification, record.revenue_matched_rule) for record in records} == {
        ("unverified_deposit", "auction_credit_without_payout_form")}


def test_a_vetoed_property_row_printing_advance_carries_the_property_rule():
    records = _statement([(2, "BUILDIUM DES:ADVANCE ID:1", 1500.0), (9, "BUILDIUM DES:FUNDING ID:2", 1501.0),
                          (16, "BUILDIUM DES:FUNDING ID:3", 1502.0)], holder="SAMPLE PROPERTIES LLC")
    assert (records[0].revenue_classification, records[0].revenue_matched_rule) == (
        "unverified_deposit", "property_platform_owner_or_deposit_wording")
    assert {record.revenue_match_method for record in records[1:]} == {"recurring_operating_source"}


def test_a_return_code_debit_pairs_an_equal_credit():
    records = _statement([(2, "NORTHWIND SUPPLY DES:VENDOR PAY ID:1", 5000.0),
                          (5, "NORTHWIND SUPPLY DES:RTN ID:1", -5000.0)], holder="SAMPLE CAFE LLC")
    assert (records[0].revenue_classification, records[0].revenue_match_method) == (
        "non_revenue", "matched_reversal_pair")


def test_a_return_code_credit_pairs_an_equal_debit():
    records = _statement([(2, "NORTHWIND SUPPLY DES:RETN ID:1", 5000.0),
                          (5, "NORTHWIND SUPPLY DES:PAYMENT ID:1", -5000.0)], holder="SAMPLE CAFE LLC")
    assert (records[0].revenue_classification, records[0].revenue_match_method) == (
        "non_revenue", "matched_reversal_pair")


def test_an_equal_pair_without_a_marker_is_no_reversal_pair():
    records = _statement([(2, "STRIPE DES:TRANSFER ID:1", 300.0), (9, "STRIPE DES:TRANSFER ID:2", 310.0),
                          (16, "STRIPE DES:TRANSFER ID:3", 320.0), (18, "STRIPE DES:TRANSFER ID:3", -320.0)])
    assert [record.revenue_match_method for record in records[:3]] == ["recurring_operating_source"] * 3

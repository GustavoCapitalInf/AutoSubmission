"""Classification 5.5 (true revenue spec §7.2, §7.3): marketplace, platform and transport payouts: the payout forms,
the new aliases and the vetoes on every new read. Fabricated rows only, in the banks' printed formats."""
from __future__ import annotations

import pytest

from analysis.schema import Statement, Transaction
from analysis.transaction_classifier.statement import classify_statement_transactions
from analysis.transaction_classifier.row import classify_transaction


def _credit(printed: str, *, holder: str | None = None, amount: float = 250.0, direction: str = "credit"):
    return classify_transaction(printed, amount, account_name=holder, direction=direction)


def _statement(rows, *, holder: str | None = None):
    return classify_statement_transactions(Statement(account_name=holder, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for day, text, amount in rows
    ]))


@pytest.mark.parametrize(("printed", "entity", "label"), [
    ("STP FBO WHATNOT INC FROM WHATNOT INC", "Whatnot", "whatnot_fbo_form"),
    ("RTP CREDIT WHATNOT INC SOUTH SAN FRANCISCO", "Whatnot", "whatnot_rtp_form"),
    ("FAIRE WHOLESALE ORDER 1234567", "Faire", "faire_order_form"),
    ("PAYMENTS EBAY COMN1ERKWVF FABRIKAM", "eBay", "ebay_payments_form"),
    ("RTP CREDIT EBAY COMMERCE INC", "eBay", "ebay_rtp_form"),
    ("AMAZON CK12AB34C PAYMENTS 1234", "Amazon Marketplace", "amazon_payments_form"),
    ("CLASSPASS INC DES:EDI PYMNTS ID:1", "ClassPass", "classpass_edi_form"),
    ("PAYONEER 1234 EZCATER PAYMENT STORE", "ezCater", "ezcater_payoneer_form"),
    ("Orig CO Name:Grpn Merch Svcs Orig ID:1234567890 Desc Date: CO Entry Descr:Payment Sec:CCD", "Groupon",
     "groupon_merchant_form"),
])
def test_a_payout_form_names_the_platform_and_verifies_one_row(printed, entity, label):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("verified_revenue", entity)
    assert record.revenue_matched_alias == label
    assert label in record.revenue_reason and "\\b" not in record.revenue_reason


@pytest.mark.parametrize(("printed", "entity"), [
    ("TIKTOK INC DES:PAYMENT ID:1234", "TikTok Shop"),
    ("CORPORATE ACH SNACKPASS 12345 SNACKPASS ST", "Snackpass"),
    ("FIELDPULSE ACH IN", "FieldPulse"),
    ("VAGARO MERCHANT ACH IN", "Vagaro"),
    ("Orig CO Name:Outdoorsy Orig ID:1234567890 Desc Date: CO Entry Descr:Payment Sec:CCD", "Outdoorsy"),
    ("RTP CREDIT AMAZON COM 1234", "Amazon Marketplace"),
])
def test_an_alias_without_a_form_needs_recurrence(printed, entity):
    record = _credit(printed)
    assert (record.revenue_classification, record.revenue_canonical_entity) == ("unverified_deposit", entity)
    assert record.revenue_match_method == "operating_source_requires_context"


def test_three_alias_rows_verify_by_recurrence():
    records = _statement([(2, "RTP CREDIT AMAZON COM 1234", 400.0), (9, "RTP CREDIT AMAZON COM 5678", 410.0),
                          (16, "RTP CREDIT AMAZON COM 9012", 420.0)])
    assert {record.revenue_match_method for record in records} == {"recurring_operating_source"}


@pytest.mark.parametrize("printed", [
    "WHATNOT INC DES:PAYROLL ID:1",
    "WHATNOT INC DES:DIR DEP ID:1",
    "WHATNOT INC PAYRLL 1234",
    "FAIRE WHOLESALE ORDER 1234 LOAN",
    "FAIRE WHOLESALE ORDER 1234 ADVANCE",
    "CLASSPASS INC DES:EDI PYMNTS REFUND ID:1",
    "CLASSPASS INC DES:EDI PYMNTS RTN ID:1",
    "AMAZON CAPITALSV PAYMENTS 1234",
    "AMAZON COMSERVIC PAYMENTS 1234",
    "PAYMENTS EBAY COMN1ERKWVF RETURN",
    "TIKTOK INC DES:DIR DEP ID:1",
    "TIKTOK SHOP 1234567 CULVER CITY CA",
    "ZELLE PAYMENT FROM FABRIKAM FOR WHATNOT INC CONF 99",
])
def test_the_vetoes_of_every_new_read(printed):
    record = _credit(printed)
    assert record.revenue_classification != "verified_revenue"
    assert record.revenue_match_method not in ("operating_source_with_credit_context", "operating_source_requires_context")


def test_three_super_dispatch_payouts_verify_and_one_does_not():
    rows = [(day, "123456789 FROM SUPER DISPATCH INC REF NOREF", 900.0 + day) for day in (2, 9, 16)]
    assert {record.revenue_match_method for record in _statement(rows)} == {"recurring_operating_source"}
    assert _statement(rows[:1])[0].revenue_classification == "unverified_deposit"


def test_a_tiktok_card_refund_three_times_never_recurs():
    records = _statement([(2, "TIKTOK SHOP 1234567 CULVER CITY CA", 40.0), (9, "TIKTOK SHOP 1234567 CULVER CITY CA", 41.0),
                          (16, "TIKTOK SHOP 1234567 CULVER CITY CA", 42.0)])
    assert {record.revenue_classification for record in records} == {"unverified_deposit"}


def test_three_mis_signed_form_rows_stay_unverified():
    records = classify_statement_transactions(Statement(account_name="SAMPLE SHOP LLC", transactions=[
        Transaction(date=f"2054-03-{day:02d}", description="STP FBO WHATNOT INC FROM WHATNOT INC", amount=300.0,
                    direction="debit")
        for day in (2, 9, 16)
    ]))
    assert {record.revenue_match_method for record in records} == {"direction_conflict"}


def test_transport_rows_with_a_wallet_or_wire_word_never_recur():
    rows = [(day, f"SUPER DISPATCH CASH OUT {day}", 50.0 + day) for day in (2, 9, 16)]
    assert {record.revenue_classification for record in _statement(rows)} == {"unverified_deposit"}

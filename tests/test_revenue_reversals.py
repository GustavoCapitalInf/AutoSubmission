"""Classification 5.6 (true revenue spec §6.1 step 3, §6.2 pass 4, §6.3, §7.11, §8.1, §20; audit fix batch B3: I03,
I04, I11, I43): returns, reversals, refunds and rewards.

- I03: a returned deposited item or a deposit correction takes the deposit it undoes out of True (pass 4, revenue side
  only): the undo debit pairs with an equal deposit-channel credit 0 to 14 days before it, the earliest one, with no
  shared word, so a redeposit stays counted. The lender side of pass 4 keeps classification 5.4's pairs (§20 I6).
- I04: step 3 reads more reversal, correction and refund spellings; a bare CARD CREDIT is held as a possible return;
  Cash App and Apple Cash pushes stay counted.
- I11: a card credit naming a merchant processor is that processor's instant payout (counted, flagged, never
  verified) when the statement shows the processor's ACH payout or ACH pull and no card purchase at it.
- I43: card-rewards redemptions are non-revenue, read on the whole row or beside a card issuer only.

Fabricated rows only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE names; 2054 dates; whole-dollar amounts), in the banks'
printed formats."""
from __future__ import annotations

import pytest

from analysis.metrics import compute_metrics
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import classify_statement_transactions

HOLDER = "NORTHWIND PLUMBING LLC"
HELD = "excluded_pending_review"
COUNTED = "counted_flagged"


def _statement(rows, bank: str | None = "Fabrikam Bank", holder: str | None = HOLDER):
    """`rows` are (date, description, signed amount)."""
    return Statement(bank=bank, account_name=holder, transactions=[
        Transaction(date=date, description=text, amount=amount, direction="credit" if amount > 0 else "debit")
        for date, text, amount in rows
    ])


def _classify(rows, bank: str | None = "Fabrikam Bank", holder: str | None = HOLDER):
    return classify_statement_transactions(_statement(rows, bank, holder))


def _one(text: str, bank: str | None = "Fabrikam Bank", amount: float = 400.0):
    return _classify([("2054-03-02", text, amount)], bank)[0]


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


def _true(records) -> float:
    return sum(record.amount for record in records if record.amount > 0 and record.contributes_to_true_revenue)


def _lender_fields(record):
    return (
        record.classification, record.canonical_entity, record.contributes_to_lender_count,
        record.contributes_to_potential_lender_count, record.contributes_to_lender_totals,
        record.contributes_to_withholding_rate, record.contributes_to_potential_lender_totals,
        record.contributes_to_potential_withholding_exposure, record.contributes_to_insurance_totals,
        record.contributes_to_flagged_totals, record.reversed_by,
    )


# ---------------------------------------------------------------------------------------------------------------------
# I03: a returned deposited item or a deposit correction takes its deposit out of True.
# ---------------------------------------------------------------------------------------------------------------------

def test_a_branch_deposit_returned_two_days_later_leaves_true():
    records = _classify([
        ("2054-03-02", "DEPOSIT AT BR 1234", 12345.0),
        ("2054-03-04", "RETURNED ITEM", -12345.0),
    ], "BMO")
    credit, debit = records
    assert credit.revenue_classification == "non_revenue"
    assert credit.revenue_match_method == "matched_reversal_pair"
    assert credit.revenue_related_transaction == "transaction:2"
    assert _true(records) == 0
    # The lender side of pass 4 is untouched: the undo debit reverses nothing a lender total reads.
    assert debit.reversed_by is None and credit.reversal_of is None


def test_a_corrected_mobile_cheque_and_its_branch_redeposit_count_once():
    records = _classify([
        ("2054-03-02", "MOBILE CHEQUE DEPOSIT", 7500.0),
        ("2054-03-02", "ERROR CORRECTION MOBILE CHEQUE DEPOSIT", -7500.0),
        ("2054-03-02", "DEPOSIT AT BR 1234", 7500.0),
    ], "BMO")
    mobile, _, branch = records
    assert mobile.revenue_classification == "non_revenue"
    assert mobile.revenue_match_method == "matched_reversal_pair"
    assert _tier(branch) == (COUNTED, "no_payer_printed")
    assert _true(records) == 7500.0


def test_the_redeposit_printed_first_still_counts_one_cheque_once():
    records = _classify([
        ("2054-03-02", "DEPOSIT AT BR 1234", 7500.0),
        ("2054-03-02", "MOBILE CHEQUE DEPOSIT", 7500.0),
        ("2054-03-02", "ERROR CORRECTION MOBILE CHEQUE DEPOSIT", -7500.0),
    ], "BMO")
    assert _true(records) == 7500.0
    assert sum(record.revenue_match_method == "matched_reversal_pair" for record in records) == 1


@pytest.mark.parametrize(("bank", "deposit", "undo", "gap"), [
    # Wells Fargo: an unpaid paper item, a mobile-deposit adjustment, a check posted twice.
    ("Wells Fargo", "MOBILE DEPOSIT REF NUMBER 123456789012", "DEPOSITED ITEM RETN UNPAID PAPER 123456", 1),
    ("Wells Fargo", "MOBILE DEPOSIT REF NUMBER 123456789012", "MOBILE DEPOSIT ADJUSTMENT", 0),
    ("Wells Fargo", "MOBILE DEPOSIT REF NUMBER 123456789012",
     "TRANSACTION CORRECTION MOBILE DEPOSIT CHECK POSTED TWICE REF A 1234567", 12),
    # PNC's returned deposited item.
    ("PNC Bank", "MOBILE DEPOSIT 123456789", "RET DEP ITEM 123456 1234567890123", 2),
    # Bank of America: a returned item charged back, and a correction of a posted item.
    ("Bank of America", "BKOFAMERICA MOBILE 03 02 1234567890 DEPOSIT MOBILE", "RETURN ITEM CHARGEBACK", 5),
    ("Bank of America", "BKOFAMERICA MOBILE 03 02 1234567890 DEPOSIT MOBILE", "ADJUSTMENT CORRECTION OF POSTED ITEM", 0),
    # Chase: a remote deposit returned to the maker, and a bare deposit returned under a stop payment.
    ("Chase", "REMOTE ONLINE DEPOSIT 1", "DEPOSITED ITEM RETURNED REFER TO MAKER 123456789 OF ITEMS 1 CK 12345", 3),
    ("Chase", "DEPOSIT", "DEPOSITED ITEM RETURNED STOP PAYMENT 123456789", 1),
    # Huntington's branch ATM deposit, RBC's unpaid cheque, a Citizens returned deposited check.
    ("Huntington National Bank", "BRCH ATM", "RETURNED DEPOSIT ITEM", 2),
    ("Royal Bank of Canada", "MOBILE CHEQUE DEPOSIT 1234", "ITEM RETURNED UNPAID S12345", 1),
    ("Citizens Bank", "MOBILE DEPOSIT", "DEPOSITED CHECK RETURNED", 6),
    # BMO's bare correction of a bare deposit.
    ("BMO", "DEPOSIT", "ERROR CORRECTION", 0),
    # A returned check charged back against a bare deposit.
    ("Fabrikam Bank", "DEPOSIT", "RETURNED CHECK 1234 MAKER CONTOSO MOTORS RETURN REASON REFER TO MAKER", 0),
])
def test_each_bank_s_returned_item_or_correction_pairs_with_its_deposit(bank, deposit, undo, gap):
    day = 2 + gap
    records = _classify([("2054-03-02", deposit, 2400.0), (f"2054-03-{day:02d}", undo, -2400.0)], bank)
    assert records[0].revenue_classification == "non_revenue"
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert records[1].reversed_by is None


def test_a_redeposit_after_the_return_stays_counted():
    records = _classify([
        ("2054-03-02", "MOBILE DEPOSIT REF NUMBER 123456789012", 2400.0),
        ("2054-03-04", "DEPOSITED ITEM RETN UNPAID PAPER 123456", -2400.0),
        ("2054-03-06", "MOBILE DEPOSIT REF NUMBER 123456789013", 2400.0),
    ], "Wells Fargo")
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert _tier(records[2]) == (COUNTED, "check_deposit")
    assert _true(records) == 2400.0


def test_the_earliest_equal_deposit_is_the_one_returned():
    records = _classify([
        ("2054-03-02", "MOBILE DEPOSIT", 2400.0),
        ("2054-03-06", "MOBILE DEPOSIT", 2400.0),
        ("2054-03-08", "RETURNED ITEM", -2400.0),
    ], "Fabrikam Bank")
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert _tier(records[1]) == (COUNTED, "check_deposit")


@pytest.mark.parametrize(("rows", "why"), [
    # Fifteen days is outside the window.
    ([("2054-03-02", "MOBILE DEPOSIT", 2400.0), ("2054-03-17", "RETURNED ITEM", -2400.0)], "window"),
    # A deposit after the return is no deposit the return undoes.
    ([("2054-03-04", "RETURNED ITEM", -2400.0), ("2054-03-06", "MOBILE DEPOSIT", 2400.0)], "after"),
    # Another amount (a partial return is the owner's decision I42).
    ([("2054-03-02", "MOBILE DEPOSIT", 2400.0), ("2054-03-04", "RETURNED ITEM", -2000.0)], "amount"),
    # The bank's fee for the returned item is no undo of the deposit.
    ([("2054-03-02", "MOBILE DEPOSIT", 15.0), ("2054-03-04", "RETURNED ITEM FEE", -15.0)], "fee"),
    # TD's RTN NSF is unconfirmed (audit I41): it is no returned-deposit form.
    ([("2054-03-02", "DEPOSIT", 2400.0), ("2054-03-02", "RTN NSF", -2400.0)], "td"),
])
def test_a_deposit_with_no_returned_item_of_its_own_stays_counted(rows, why):
    records = _classify(rows)
    deposit = next(record for record in records if record.amount > 0)
    assert deposit.revenue_match_method != "matched_reversal_pair", why
    assert deposit.contributes_to_true_revenue, why


def test_a_returned_item_never_pairs_with_an_electronic_payment():
    # A bare return names no payer, so it only undoes a deposit-channel credit; a customer's ACH payment of the same
    # amount keeps its reading.
    records = _classify([
        ("2054-03-02", "CONTOSO SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD", 2400.0),
        ("2054-03-04", "RETURNED ITEM", -2400.0),
    ], "Bank of America")
    assert records[0].revenue_match_method != "matched_reversal_pair"
    assert records[0].contributes_to_true_revenue


def test_the_check_family_still_pairs_a_returned_check_with_its_check_deposit():
    # Control (unchanged): both rows print CHECK, so the shared family pairs them.
    records = _classify([
        ("2054-03-02", "ATM CHECK DEPOSIT", 2400.0),
        ("2054-03-09", "RETURNED CHECK", -2400.0),
    ])
    assert records[0].revenue_match_method == "matched_reversal_pair"


def test_a_funder_debit_and_a_returned_nsf_keep_their_lender_reading():
    # Control: a registered funder's debit, then the bank's RTN NSF; the deposit pairing never reads the lender side.
    rows = [
        ("2054-03-02", "DEPOSIT", 500.0),
        ("2054-03-03", "ONDECK CAPITAL DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD", -500.0),
        ("2054-03-04", "RTN NSF", -500.0),
    ]
    records = _classify(rows)
    alone = _classify(rows[1:])
    assert _lender_fields(records[1]) == _lender_fields(alone[0])
    assert records[1].contributes_to_lender_totals and records[1].reversed_by is None
    assert records[0].contributes_to_true_revenue


def test_an_undo_debit_s_lender_reading_never_moves():
    rows = [("2054-03-02", "DEPOSIT AT BR 1234", 12345.0), ("2054-03-04", "RETURNED ITEM", -12345.0)]
    paired = _classify(rows, "BMO")
    alone = _classify(rows[1:], "BMO")
    assert _lender_fields(paired[1]) == _lender_fields(alone[0])


def test_a_correction_debit_that_shares_the_payer_s_words_undoes_its_payment():
    # The undo markers are pass 4's revenue-side markers on either row: a correction debit that prints the credit's
    # payer pairs with it as any marked pair does (the shared words), deposit channel or not.
    records = _classify([
        ("2054-03-02", "CONTOSO SUPPLY LLC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD", 2400.0),
        ("2054-03-03", "ERROR CORRECTION CONTOSO SUPPLY LLC", -2400.0),
    ], "BMO")
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert records[0].revenue_matched_rule == "opposite_direction_amount_date_description_match"
    assert records[1].reversed_by is None


def test_a_verified_payer_s_reversal_debit_still_demotes_it():
    # Spec §14.1 (§7.6), audit I03: a payer's own reversal of its payment prints its name and pairs; a bare return
    # prints none (the deposit tests above).
    records = _classify([
        ("2054-03-02", "SAMPLE COUNTY DES:VENDOR PAY ID:1", 1400.0),
        ("2054-03-04", "SAMPLE COUNTY DES:REVERSAL ID:1", -1400.0),
    ], holder="CONTOSO CLINIC")
    assert records[0].revenue_classification == "non_revenue"
    assert records[0].revenue_match_method == "matched_reversal_pair"


def test_the_metrics_count_a_corrected_cheque_once():
    statement = _statement([
        ("2054-03-02", "MOBILE CHEQUE DEPOSIT", 7500.0),
        ("2054-03-02", "ERROR CORRECTION MOBILE CHEQUE DEPOSIT", -7500.0),
        ("2054-03-02", "DEPOSIT AT BR 1234", 7500.0),
    ], "BMO")
    metrics = compute_metrics(statement, classifications=classify_statement_transactions(statement))
    assert metrics.counted_flagged_total == 7500.0
    assert metrics.non_revenue_total == 7500.0


# ---------------------------------------------------------------------------------------------------------------------
# I04: step 3's other reversal, correction and refund spellings.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("bank", "text"), [
    # Zions' bounced outgoing payment credited back; the control spelling ITEM RTN NOT PAID was already one.
    ("Zions Bancorporation", "ITEM RET NOT PAID"),
    ("Zions Bancorporation", "ITEM RTN NOT PAID"),
    ("PNC Bank", "RET DEP ITEM 123456"),
    # Bank error and transaction corrections, and a correction printed first (glued to its reference too).
    ("BMO", "ERROR CORRECTION BR 1234"),
    ("Scotiabank", "ERROR CORRECTION OPOS CONTOSO HARDWARE SAMPLEVILLE ON CA"),
    ("Wells Fargo", "TRANSACTION CORRECTION"),
    ("CIBC", "CORRECTION 12345 SAMPLE AND MAIN BANKING CE"),
    ("CIBC", "CORRECTION123456789012 CONTOSO SAMPLEVILLE 1234 567"),
    # Card-purchase refunds: U.S. Bank, Citibank's cut label, Bank of America's credit-side CHECKCARD, a point-of-sale
    # deposit from a retailer, a reversed mobile purchase.
    ("U.S. Bank", "DEBIT PURCHASE RET VISA ON 123456 SAMPLEVILLE CA 1234567890"),
    ("Citibank", "DEBIT CARD CREDI CARD ENDING IN 1234 CONTOSO HARDWARE 1234 SAMPLEVILLE NC 12345"),
    ("Bank of America", "CHECKCARD 0115 CONTOSO HARDWARE SAMPLEVILLE MO 12345678901234567890123"),
    ("Fabrikam Credit Union", "POINT OF SALE DEPOSIT CONTOSO AUTO PARTS 123 W MAIN ST SAMPLEVILLE NDUS"),
    ("Capital One", "REV MOBILE DEBIT PURCHASE 123456 FABRIKAM MARKET SAMPLEVILLE CA"),
    # A provisional credit, an unauthorized-ACH settlement, an e-Transfer the holder reclaimed.
    ("Capital One", "BANKING CARD PROVISIONAL CR"),
    ("First Citizens Bank", "SETTLEMENT ACH UNAUTHORIZED"),
    ("CIBC", "E TRANSFER RECLAIM123456789012 1234 ABC"),
    # French reversals and refunds: a returned debit (RENV), a merchandise return, a contactless refund.
    (None, "RENV TFE DEBIT"),
    (None, "RENV VIRDT IT"),
    (None, "RENVERSEMENT PRELEVEMENT CONTOSO"),
    ("CIBC", "RETOUR MDSE 123456789012 CONTOSO ST SAMPLE"),
    (None, "C RETOUR 12345678901 FABRIKAM 12345"),
    ("Banque Royale du Canada", "REMBOURSEMENT INTERAC SANS CONTACT 1234 FABRIKAM"),
    # Fee waivers and a courtesy refund of a wire fee.
    ("Huntington National Bank", "24 HOUR GRACE OVERDRAFT FEE WAIVER"),
    ("U.S. Bank", "OVERDRAFT PAID FEE WAIVED 1234567890"),
    ("Huntington National Bank", "TOTAL RELATIONSHIP SERVICE FEE WAIVE"),
    ("TD Bank", "WIRE OUT COURTESY REF"),
])
def test_step_3_reads_the_return_correction_and_refund_spellings(bank, text):
    record = _one(text, bank)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"
    assert _tier(record) == ("non_revenue", None)


@pytest.mark.parametrize(("bank", "text"), [
    # A payer whose name only starts like a marker keeps its reading.
    ("Fabrikam Bank", "RECLAIMED WOOD CONTOSO LLC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD"),
    ("Fabrikam Bank", "DEPT OF CORRECTION DES:VENDOR PAY ID:1"),
    ("Fabrikam Bank", "CORRECTIONAL CONTOSO SERVICES DES:PAYMENT ID:1"),
    ("Fabrikam Bank", "REVERE CONTOSO LLC DES:PAYMENT ID:1"),
    ("Fabrikam Bank", "CONTOSO RETOURS INC DES:PAYMENT ID:1"),
])
def test_a_payer_named_like_a_marker_is_no_reversal(bank, text):
    assert _one(text, bank).revenue_match_method != "reversal_cancellation_exclusion"


def test_a_quebec_health_payer_s_remboursement_to_a_clinic_is_counted():
    # §7.11's provider carve-out, as REIMBURSEMENT has it: the Quebec health insurance board pays a clinic for its
    # claims (French REMBOURSEMENT).
    for text in ("RAMQ REMBOURSEMENT 1234567", "MEDICAID REMBOURSEMENT 1234567"):
        record = _classify([("2054-03-02", text, 1400.0)], "Banque Royale du Canada", "CONTOSO CLINIQUE INC")[0]
        assert record.revenue_classification != "non_revenue", text
        assert record.contributes_to_true_revenue, text
    # The board's full name prints ASSURANCE, which §8.1's insurer hold reads (the owner's decision I27 stands): it
    # leaves the reversal rule and is held, never non-revenue.
    record = _classify([("2054-03-02", "REGIE DE L ASSURANCE MALADIE DU QUEBEC REMBOURSEMENT 1234567", 1400.0)],
                       "Banque Royale du Canada", "CONTOSO CLINIQUE INC")[0]
    assert record.revenue_classification != "non_revenue"


@pytest.mark.parametrize(("hold_text", "held"), [
    # §8.1's possible-return backstop reads step 3's 5.6 spellings on the hold text (the posting labels removed), so a
    # row that reaches the pass with one is held, never counted.
    (" NOT PAID", True),
    ("ITEM RET NOT PAID", True),
    (" CORRECTION 12345 SAMPLE AND MAIN BANKING CE", True),
    ("TRANSACTION CORRECTION", True),
    ("DEBIT PURCHASE RET VISA ON 123456", True),
    ("BANKING PROVISIONAL CR", True),
    ("SETTLEMENT ACH UNAUTHORIZED", True),
    ("E TRANSFER RECLAIM123456", True),
    (" REV POS PURCHASE 123456", True),
    ("RENV TFE DEBIT", True),
    ("RETOUR MDSE 123", True),
    ("24 HOUR GRACE OVERDRAFT FEE WAIVER", True),
    ("WIRE OUT COURTESY REF", True),
    # Not REMBOURSEMENT (a provider's left step 3 by §7.11's carve-out), and never a name.
    ("RAMQ REMBOURSEMENT 1234", False),
    ("RECLAIMED WOOD CONTOSO LLC", False),
    ("DEPT OF CORRECTION VENDOR PAY", False),
    ("REVERE CONTOSO LLC", False),
])
def test_the_possible_return_backstop_reads_step_3_s_new_spellings(hold_text, held):
    from analysis import true_revenue

    assert (true_revenue._POSSIBLE_RETURN.search(hold_text) is not None) is held


def test_a_card_marker_on_a_debit_pairs_nothing():
    # The credit-side markers (a CHECKCARD purchase line, a point-of-sale deposit) are read on the credit only: the
    # holder's card purchase at a customer's store never takes that customer's payment out of True.
    records = _classify([
        ("2054-03-02", "CONTOSO HARDWARE LLC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD", 400.0),
        ("2054-03-04", "CHECKCARD 0303 CONTOSO HARDWARE SAMPLEVILLE MO 12345678901234567890123", -400.0),
    ], "Bank of America")
    assert records[0].revenue_match_method != "matched_reversal_pair"
    assert records[0].contributes_to_true_revenue


# I04: card credits.
@pytest.mark.parametrize("text", ["CARD CREDIT", "CARD CREDIT 1234", "CARD CREDIT CONTOSO HARDWARE 1234 SAMPLEVILLE TX"])
def test_a_card_credit_whose_payer_is_lost_or_a_store_is_held_as_a_possible_return(text):
    record = _one(text, "BMO")
    assert record.revenue_classification == "unverified_deposit"
    assert _tier(record) == (HELD, "possible_return")


@pytest.mark.parametrize("text", [
    "CARD CREDIT CASH APP SAMPLE 1234 OAKLAND CA 12345 1234",
    "CARD CREDIT APPLE CASH INST 1234 CUPERTINO CA12345 1234",
])
def test_a_cash_app_or_apple_cash_push_stays_a_counted_p2p_credit(text):
    assert _tier(_one(text, "Regions Bank", 410.0)) == (COUNTED, "p2p")


@pytest.fixture
def cash_app_release(monkeypatch):
    """The owner's switch for Cash App and Apple Cash pushes printed as a DEBIT CARD CREDIT (it ships off: it moves a
    real statement's pinned figures)."""
    from analysis import transaction_classifier

    monkeypatch.setattr(transaction_classifier, "CASH_APP_CARD_PUSH_RELEASE", True)


@pytest.mark.usefixtures("cash_app_release")
@pytest.mark.parametrize("text", ["DEBIT CARD CREDIT CASH APP", "POS CREDIT APPLE CASH INST XF CUPERTINO CA"])
def test_a_cash_app_push_printed_as_a_debit_card_credit_leaves_the_reversal_rule(text):
    # With the switch on, Cash App and Apple Cash join the push-word release (§7.11): such a card credit is held,
    # never non-revenue.
    record = _one(text, "Thread Bank (Relay)")
    assert record.revenue_classification == "unverified_deposit"
    assert _tier(record) == (HELD, "possible_return")


@pytest.mark.parametrize("text", [
    "CHECKCARD 0115 VISA DIRECT CONTOSO SAMPLEVILLE MO 12345678901234567890123",
    "DEBIT CARD CREDI CARD ENDING IN 1234 VISA DIRECT FABRIKAM",
    "POINT OF SALE DEPOSIT VISA DIRECT FABRIKAM SAMPLEVILLE",
])
def test_a_card_shaped_refund_label_with_a_push_word_is_released_and_held(text):
    # §7.11: the card-shaped labels step 3 adds are released by a push-rail word as a card credit is; §8.1 then holds
    # the released row as a possible return (no form verified it).
    record = _one(text, "Fabrikam Bank")
    assert record.revenue_classification == "unverified_deposit"
    assert _tier(record) == (HELD, "possible_return")


def test_the_cash_app_card_push_release_ships_off():
    from analysis import transaction_classifier

    assert transaction_classifier.CASH_APP_CARD_PUSH_RELEASE is False
    record = _one("DEBIT CARD CREDIT CASH APP", "Thread Bank (Relay)")
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"


# ---------------------------------------------------------------------------------------------------------------------
# I11: a processor's instant payout printed as a card credit (the owner's switch PROCESSOR_CARD_PAYOUT_RELEASE: it
# ships off, since it moves a real statement's pinned figures; these tests turn it on).
# ---------------------------------------------------------------------------------------------------------------------

RELAY = "Thread Bank (Relay)"


@pytest.fixture
def processor_release(monkeypatch):
    from analysis import true_revenue

    monkeypatch.setattr(true_revenue, "PROCESSOR_CARD_PAYOUT_RELEASE", True)


def test_the_processor_card_payout_release_ships_off():
    from analysis import true_revenue

    assert true_revenue.PROCESSOR_CARD_PAYOUT_RELEASE is False
    records = _classify([
        ("2054-03-02", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-20", "ACH Pull: Stripe", -50.0),
    ], RELAY)
    assert records[0].revenue_classification == "non_revenue"
    assert records[0].revenue_match_method == "reversal_cancellation_exclusion"


@pytest.mark.usefixtures("processor_release")
def test_relay_stripe_card_payouts_with_a_stripe_pull_are_counted():
    records = _classify([
        ("2054-03-02", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-09", "Debit Card Credit: Stripe", 2200.0),
        ("2054-03-16", "Debit Card Credit: Stripe", 2300.0),
        ("2054-03-20", "ACH Pull: Stripe", -50.0),
    ], RELAY)
    for record in records[:3]:
        assert record.revenue_classification == "unverified_deposit"
        assert record.revenue_match_method == "processor_card_payout"
        assert _tier(record) == (COUNTED, "platform_unconfirmed")
    assert _true(records) == 6600.0


@pytest.mark.usefixtures("processor_release")
@pytest.mark.parametrize("activity", [
    ("2054-03-20", "ACH Pull: Intuit Pymt Soln", -40.0),
    ("2054-03-20", "ACH Pull: Intuit 12345678", -40.0),
    ("2054-03-20", "ACH Credit: Intuit Payments 12345678", 900.0),
    ("2054-03-20", "Returned ACH Pull: Intuit Pymt Soln", 40.0),
])
def test_bare_intuit_card_payouts_count_with_intuit_s_ach_activity(activity):
    records = _classify([
        ("2054-03-02", "Debit Card Credit: Intuit", 1100.0),
        ("2054-03-09", "Debit Card Credit: Intuit", 1200.0),
        activity,
    ], RELAY)
    for record in records[:2]:
        assert _tier(record) == (COUNTED, "platform_unconfirmed")


@pytest.mark.usefixtures("processor_release")
def test_a_pocketsuite_card_payout_counts_with_its_ach_pull():
    records = _classify([
        ("2054-03-02", "Debit Card Credit: Pocket Suite", 1100.0),
        ("2054-03-20", "ACH Pull: PocketSuite", -30.0),
    ], RELAY)
    assert _tier(records[0]) == (COUNTED, "platform_unconfirmed")


@pytest.mark.usefixtures("processor_release")
@pytest.mark.parametrize(("rows", "why"), [
    # No processor activity on the statement: a card refund cannot be told from a payout.
    ([("2054-03-02", "Debit Card Credit: Stripe", 2100.0)], "no activity"),
    # A card purchase at the processor makes the credit that purchase's refund.
    ([("2054-03-02", "Debit Card Credit: Stripe", 2100.0), ("2054-03-20", "ACH Pull: Stripe", -50.0),
      ("2054-03-21", "Debit Card Purchase: Stripe", -2100.0)], "a purchase at it"),
    ([("2054-03-02", "Debit Card Credit: Pocket Suite", 1100.0), ("2054-03-20", "ACH Pull: PocketSuite", -30.0),
      ("2054-03-21", "Debit Card Purchase: PocketSuite", -30.0)], "a purchase at it"),
    # Another processor's activity names nobody's payout.
    ([("2054-03-02", "Debit Card Credit: Stripe", 2100.0), ("2054-03-20", "ACH Pull: Intuit Pymt Soln", -40.0)],
     "another processor"),
    # A marketplace or a retailer keeps the refund reading.
    ([("2054-03-02", "Debit Card Credit: Uber", 21.0), ("2054-03-09", "Debit Card Credit: Uber", 22.0),
      ("2054-03-16", "Debit Card Credit: Uber", 23.0), ("2054-03-20", "ACH Pull: Uber", -50.0)], "Uber"),
    # A row that prints another reversal word stays a reversal, before the label too.
    ([("2054-03-02", "Debit Card Credit: Stripe Refund", 2100.0), ("2054-03-20", "ACH Pull: Stripe", -50.0)],
     "refund word"),
    ([("2054-03-02", "REVERSAL DEBIT CARD CREDIT STRIPE", 2100.0), ("2054-03-20", "ACH Pull: Stripe", -50.0)],
     "reversal word before the label"),
    # The processor's name with another word is not its payout (a capital advance pushed to the card).
    ([("2054-03-02", "Debit Card Credit: Stripe Capital", 2100.0), ("2054-03-20", "ACH Pull: Stripe", -50.0)],
     "financing word"),
])
def test_a_card_credit_without_its_processor_s_payout_or_pull_stays_a_refund(rows, why):
    credit = _classify(rows, RELAY)[0]
    assert credit.revenue_classification == "non_revenue", why
    assert credit.revenue_match_method == "reversal_cancellation_exclusion", why


@pytest.mark.usefixtures("processor_release")
def test_a_released_card_payout_is_never_verified_nor_held_as_the_payer_also_debited():
    records = _classify([
        ("2054-03-02", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-05", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-09", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-12", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-20", "ACH Pull: Stripe", -50.0),
        ("2054-03-21", "ACH Credit: Stripe", 900.0),
    ], RELAY)
    for record in records[:4]:
        assert record.revenue_classification == "unverified_deposit"
        assert _tier(record) == (COUNTED, "platform_unconfirmed")


def test_the_card_payout_processor_names_are_checked_by_the_registry_validator(monkeypatch):
    from analysis import classification_registry as registry
    from tools import operating_registry

    assert not any("card-payout processor" in problem for problem in operating_registry.problems())
    monkeypatch.setattr(registry, "CARD_PAYOUT_PROCESSOR_NAMES", {
        "Stripe": ("Stripe",), "Square": ("SQUARE CAPITAL",), "Fabrikam": ("STATE FARM",)})
    found = operating_registry.problems()
    assert "card-payout processor name 'Stripe' of 'Stripe' is not normalized" in found
    assert any("card-payout processor name 'SQUARE CAPITAL'" in problem and "alias of" in problem for problem in found)
    assert any("card-payout processor name 'STATE FARM'" in problem and "insurer alias" in problem for problem in found)


@pytest.mark.usefixtures("processor_release")
def test_a_card_payout_the_processor_pulls_back_stays_paired():
    # Pass 4 still pairs a card credit with an equal pull of the same processor (the payout taken back).
    records = _classify([
        ("2054-03-02", "Debit Card Credit: Stripe", 2100.0),
        ("2054-03-04", "ACH Pull: Stripe", -2100.0),
    ], RELAY)
    assert records[0].revenue_match_method == "matched_reversal_pair"


# ---------------------------------------------------------------------------------------------------------------------
# I43: card-rewards redemptions.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("bank", "texts"), [
    ("Chase", ["CASH REDEMPTION"]),
    ("Chase", ["CASH REDEMPTION 1234567"]),
    ("PNC Bank", ["PNC PURCHASE PAYBACK AWARD"]),
    ("PNC Bank", ["PURCHASE PAYBACK"]),
    ("Fabrikam Bank", ["POINTS REDEMPTION"]),
    ("Bank of America", [
        "AMERICAN EXPRESS DES:MR REDEEM ID:1234567890 INDN:NORTHWIND PLUMBING LLC CO ID:1234567890 PPD",
        "AMERICAN EXPRESS DES:MR REDEEM ID:1234567891 INDN:NORTHWIND PLUMBING LLC CO ID:1234567890 PPD",
    ]),
    ("Fabrikam Bank", ["AMEX DES:MEMBERSHIP REWARDS ID:1234"]),
])
def test_card_rewards_redemptions_are_non_revenue(bank, texts):
    records = _classify([(f"2054-03-{2 + index:02d}", text, 40.0 + index) for index, text in enumerate(texts)], bank)
    for record in records:
        assert record.revenue_classification == "non_revenue"
        assert record.revenue_match_method == "strong_non_revenue_rule"


def test_a_payer_named_redemption_stays_verified():
    record = _one("REDEMPTION FABRIKAM CHURCH INC DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD",
                  "Bank of America", 1400.0)
    assert record.revenue_classification == "verified_revenue"


@pytest.mark.parametrize("text", [
    # A redemption word inside a payer's name or a person's payback is no reward.
    "CASH REDEMPTION CONTOSO LLC DES:PAYMENT ID:1",
    "FABRIKAM DES:MR REDEEM ID:1",
    "ZELLE FROM PAT SAMPLE ON 03 02 REF 1234 PAYBACK",
])
def test_a_reward_word_without_its_anchor_is_no_reward(text):
    assert _one(text).revenue_match_method != "strong_non_revenue_rule"


# ---------------------------------------------------------------------------------------------------------------------
# Review round 1 (audit B3): the new step-3 spellings stay off company names and memos, the deposit mode's undo debit
# is the bank's own return, and the provider carve-out holds in pass 4.
# ---------------------------------------------------------------------------------------------------------------------

ACH_PAYER = "{name} DES:PAYMENT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD"


@pytest.mark.parametrize("name", [
    # RECLAIM is read glued to its reference or as the row's last word, never as a payer's first word.
    "RECLAIM CONTOSO LLC",
    # A leading REV and a rail word, RETOUR and UNAUTHORIZED that start a company's name.
    "REV MOBILE LLC",
    "REV POS CONTOSO LLC",
    "RETOUR CONTOSO INC",
    "UNAUTHORIZED CONTOSO LLC",
])
def test_a_company_named_like_a_new_marker_keeps_its_verified_payment(name):
    record = _one(ACH_PAYER.format(name=name), "Bank of America", 1400.0)
    assert record.revenue_classification == "verified_revenue"
    assert record.revenue_match_method == "named_payer_company_form"


def test_repeat_wires_from_a_company_named_reclaim_stay_verified():
    wire = ("WIRE TYPE WIRE IN DATE 03{day}54 TIME 1200 ET TRN 205403{day}00123456 SEQ 123456 ORIG RECLAIM FABRIKAM INC "
            "ID 123456789")
    records = _classify([
        ("2054-03-02", wire.format(day="02"), 5000.0),
        ("2054-03-09", wire.format(day="09"), 5100.0),
    ], "Bank of America")
    for record in records:
        assert record.revenue_classification == "verified_revenue"
        assert record.revenue_match_method == "repeat_wire_sender"


@pytest.mark.parametrize(("bank", "text", "tier"), [
    # NOT PAID inside a person's memo or a wire's remittance field is no returned item.
    ("Chase", "ZELLE FROM PAT SAMPLE ON 03 02 REF 1234 INVOICE NOT PAID LAST MONTH", (COUNTED, "p2p")),
    ("Bank of America", "WIRE TYPE WIRE IN DATE 030254 TIME 1200 ET TRN 2054030200123456 SEQ 123456 ORIG CONTOSO "
     "SUPPLY LLC ID 123456789 OBI INV 55 NOT PAID", ("verified", None)),
])
def test_not_paid_in_a_memo_keeps_the_payment_s_reading(bank, text, tier):
    record = _one(text, bank, 400.0)
    assert record.revenue_match_method != "reversal_cancellation_exclusion"
    assert _tier(record) == tier


@pytest.mark.parametrize(("bank", "text"), [
    # The forms the narrowed spellings still read: an e-Transfer reclaim printed last, a reversed purchase at a merchant
    # whose name has a company form (a transaction word follows the rail word), a reversed POS entry with its
    # reference, a merchandise return at a company, a returned item printed with NOT PAID or as the whole row, and a
    # bare unauthorized-entry credit.
    ("CIBC", "E TRANSFER RECLAIM"),
    ("Capital One", "REV MOBILE DEBIT PURCHASE 123456 CONTOSO HARDWARE INC SAMPLEVILLE CA"),
    ("Fabrikam Bank", "REV POS 123456 CONTOSO HARDWARE LLC"),
    ("CIBC", "RETOUR MDSE 123456789012 CONTOSO INC SAMPLE"),
    ("Fabrikam Bank", "ITEM NOT PAID"),
    ("Fabrikam Bank", "NOT PAID 123456"),
    ("Fabrikam Bank", "UNAUTHORIZED"),
])
def test_the_narrowed_spellings_still_read_the_bank_forms(bank, text):
    record = _one(text, bank)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"


@pytest.mark.parametrize(("hold_text", "held"), [
    ("RECLAIM CONTOSO LLC", False),
    ("ORIG RECLAIM FABRIKAM INC ID 123456789", False),
    ("REV MOBILE LLC", False),
    ("REV POS CONTOSO LLC", False),
    ("RETOUR CONTOSO INC", False),
    ("ZELLE FROM PAT SAMPLE INVOICE NOT PAID LAST MONTH", False),
    ("UNAUTHORIZED CONTOSO LLC", False),
    ("E TRANSFER RECLAIM", True),
    (" REV MOBILE DEBIT PURCHASE 123456 CONTOSO HARDWARE INC", True),
    ("RETOUR MDSE 123 CONTOSO INC", True),
    ("NOT PAID 123456", True),
    ("UNAUTHORIZED", True),
])
def test_the_possible_return_backstop_reads_the_narrowed_spellings(hold_text, held):
    from analysis import true_revenue

    assert (true_revenue._POSSIBLE_RETURN.search(hold_text) is not None) is held


@pytest.mark.parametrize("text", ["POINT OF SALE DEPOSIT 123456", "POINT OF SALE DEPOSIT"])
def test_a_point_of_sale_deposit_naming_no_merchant_stays_counted(text):
    # §8.1's card-credit label reads a point-of-sale deposit only before a merchant's name, as step 3 does: a bare one
    # (a credit union's own acquiring settlement, perhaps) keeps Q2's counted no-payer reading.
    record = _one(text, "Fabrikam Credit Union")
    assert record.revenue_tier == COUNTED
    assert record.contributes_to_true_revenue


@pytest.mark.parametrize(("bank", "deposit", "undo", "amount"), [
    # The holder's own person-to-person payment or paid check with a 'return item' memo is no bank return.
    ("Chase", "ATM CASH DEPOSIT 1234", "ZELLE PAYMENT TO PAT SAMPLE RETURN ITEM", 150.0),
    ("Fabrikam Bank", "DEPOSIT", "ZELLE PAYMENT TO PAT SAMPLE RETURNED ITEM", 150.0),
    ("Fabrikam Bank", "DEPOSIT", "CHECK 1234 RETURN ITEM", 150.0),
    # An electronic payment naming its payee, and a wire, are no returned deposit either.
    ("Fabrikam Bank", "DEPOSIT", "CONTOSO SUPPLY LLC DES:RETURN ITEM ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD",
     150.0),
    ("Fabrikam Bank", "DEPOSIT", "WIRE TYPE WIRE OUT DATE 030454 RETURN ITEM BNF CONTOSO SUPPLY LLC", 150.0),
    # The bank's charge for the return, in its CHARGE and CHRG wordings.
    ("Fabrikam Bank", "DEPOSIT", "RETURN ITEM CHARGE", 35.0),
    ("Fabrikam Bank", "DEPOSIT", "RETURN ITEM CHRG", 35.0),
    ("Fabrikam Bank", "DEPOSIT", "RETURNED CHECK CHARGE", 35.0),
])
def test_a_debit_that_is_not_the_bank_s_return_never_undoes_a_deposit(bank, deposit, undo, amount):
    records = _classify([("2054-03-02", deposit, amount), ("2054-03-04", undo, -amount)], bank)
    assert records[0].revenue_match_method != "matched_reversal_pair"
    assert records[0].contributes_to_true_revenue


def test_a_return_item_charged_back_in_two_words_still_undoes_its_deposit():
    # Control: CHARGE BACK is the chargeback, never the bank's charge.
    records = _classify([("2054-03-02", "DEPOSIT", 2400.0), ("2054-03-04", "RETURN ITEM CHARGE BACK", -2400.0)])
    assert records[0].revenue_match_method == "matched_reversal_pair"


@pytest.mark.parametrize(("rows", "paired"), [
    # Undated rows (or one undated row) read the row order, as pass 4 does: the deposit must come first.
    ([("", "RETURNED ITEM", -2400.0), ("", "MOBILE DEPOSIT", 2400.0)], False),
    ([("2054-03-04", "RETURNED ITEM", -2400.0), ("", "MOBILE DEPOSIT", 2400.0)], False),
    ([("", "RETURNED ITEM", -2400.0), ("2054-03-02", "MOBILE DEPOSIT", 2400.0)], False),
    ([("", "MOBILE DEPOSIT", 2400.0), ("", "RETURNED ITEM", -2400.0)], True),
    ([("2054-03-02", "MOBILE DEPOSIT", 2400.0), ("", "RETURNED ITEM", -2400.0)], True),
])
def test_an_undated_return_undoes_only_a_deposit_printed_before_it(rows, paired):
    records = _classify(rows)
    deposit = next(record for record in records if record.amount > 0)
    assert (deposit.revenue_match_method == "matched_reversal_pair") is paired
    assert deposit.contributes_to_true_revenue is not paired


@pytest.mark.parametrize("order", [(0, 1, 2), (1, 0, 2)])
def test_a_correction_naming_its_payer_undoes_that_payment_not_an_equal_deposit(order):
    rows = [
        ("2054-03-02", ACH_PAYER.format(name="CONTOSO SUPPLY LLC"), 2400.0),
        ("2054-03-02", "MOBILE DEPOSIT", 2400.0),
        ("2054-03-03", "ERROR CORRECTION CONTOSO SUPPLY LLC", -2400.0),
    ]
    records = _classify([rows[index] for index in order], "BMO")
    payment = next(record for record in records if "CONTOSO" in record.normalized_description and record.amount > 0)
    deposit = next(record for record in records if record.normalized_description == "MOBILE DEPOSIT")
    assert payment.revenue_match_method == "matched_reversal_pair"
    assert payment.revenue_matched_rule == "opposite_direction_amount_date_description_match"
    assert _tier(deposit) == (COUNTED, "check_deposit")
    assert _true(records) == 2400.0


def test_a_returned_check_naming_its_maker_undoes_the_deposit_not_the_maker_s_payment():
    # A credit union's returned check prints the check's maker: it undoes the deposited check, never the maker's equal
    # ACH payment (a replacement for the bounced check), which stays verified.
    records = _classify([
        ("2054-03-02", "MOBILE DEPOSIT", 2400.0),
        ("2054-03-05", "RETURNED CHECK 1234 MAKER CONTOSO SUPPLY RETURN REASON REFER TO MAKER", -2400.0),
        ("2054-03-06", ACH_PAYER.format(name="CONTOSO SUPPLY LLC"), 2400.0),
    ], "Fabrikam Credit Union")
    assert records[0].revenue_matched_rule == "returned_deposit_amount_date_match"
    assert records[2].revenue_classification == "verified_revenue"


def test_a_correction_never_undoes_a_deposit_printed_after_it():
    # A deposit-channel credit sharing the correction's words is the deposit mode's, which reads only deposits printed
    # before the undo: the earlier branch deposit is undone, the later mobile one stays counted.
    records = _classify([
        ("2054-03-02", "DEPOSIT AT BR 1234", 7500.0),
        ("2054-03-03", "ERROR CORRECTION MOBILE CHEQUE DEPOSIT", -7500.0),
        ("2054-03-04", "MOBILE CHEQUE DEPOSIT", 7500.0),
    ], "BMO")
    assert records[0].revenue_matched_rule == "returned_deposit_amount_date_match"
    assert _tier(records[2]) == (COUNTED, "check_deposit")


def test_a_provider_s_remboursement_is_no_pair_marker():
    # §7.11's carve-out holds in pass 4 too: the clinic's claim payment never pairs as a refund with an equal debit
    # that shares its word (the holder's loan repayment).
    records = _classify([
        ("2054-03-02", "RAMQ REMBOURSEMENT 1234567", 1400.0),
        ("2054-03-05", "REMBOURSEMENT PRET CONTOSO", -1400.0),
    ], "Banque Royale du Canada", "CONTOSO CLINIQUE INC")
    assert records[0].revenue_match_method != "matched_reversal_pair"
    assert records[0].contributes_to_true_revenue


def test_a_store_s_remboursement_still_pairs_with_its_purchase():
    # Control: a refund REMBOURSEMENT (no provider) keeps the pass-4 credit marker.
    records = _classify([
        ("2054-03-02", "REMBOURSEMENT INTERAC SANS CONTACT 1234 FABRIKAM", 40.0),
        ("2054-03-01", "ACHAT INTERAC SANS CONTACT 1234 FABRIKAM", -40.0),
    ], "Banque Royale du Canada")
    assert records[0].revenue_match_method == "matched_reversal_pair"


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 2, R2-B08 (R08; standard D1, D3, D5): the French return, reversal and refusal wordings (EFFET RETOURNE,
# CONTRE-PASSATION, EFFET or CHEQUE REFUSE SANS PROVISION) and the English check-word NOT PAID are step 3's credit
# markers, which pass 4 reads on the credit row; the French interest and fee rebate are strong non-revenue, as their
# English twins (INTEREST CREDIT, FEE REBATE) are.
# ---------------------------------------------------------------------------------------------------------------------

_REVERSAL_METHODS = {"reversal_cancellation_exclusion", "matched_reversal_pair"}


def test_r08_cibc_s_reversal_of_a_cheque_pairs_with_the_cheque():
    rows = [("2054-03-01", "CHEQUE 123 45678901", -5500.0), ("2054-03-02", "CONTRE-PASSATION DE CHEQUE", 5500.0)]
    records = _classify(rows, "CIBC")
    assert records[1].revenue_classification == "non_revenue"
    assert records[1].revenue_match_method == "matched_reversal_pair"
    assert _true(records) == 0
    # The lender side of pass 4 never reads the new markers: the cheque's own reading is untouched.
    assert _lender_fields(records[0]) == _lender_fields(_classify(rows[:1], "CIBC")[0])


@pytest.mark.parametrize(("bank", "rows"), [
    # CIBC's reversal of a cheque, alone, with its hyphen dropped.
    ("CIBC", [("2054-03-02", "CONTREPASSATION DE CHEQUE", 5500.0)]),
    # CIBC's reversal of a pre-authorized debit, twice, beside the equal debits it undoes.
    ("CIBC", [("2054-03-01", "DEBIT TLV CONTOSO", -300.0),
              ("2054-03-02", "CONTRE-PASSATION DE DEBIT TLV CONTOSO", 300.0),
              ("2054-03-08", "DEBIT TLV CONTOSO", -310.0),
              ("2054-03-09", "CONTRE-PASSATION DE DEBIT TLV CONTOSO", 310.0)]),
    # RBC's French refused item, beside the payment it refuses and the bank's NSF fee: accented, with the replacement
    # character a lost accent leaves, and the cheque form.
    ("Banque Royale du Canada", [("2054-03-01", "Paiement divers SAMPLE", -235.0),
                                 ("2054-03-02", "Effet refusé sans provision", 235.0),
                                 ("2054-03-02", "Frais pour effet sans provision", -45.0)]),
    ("Banque Royale du Canada", [("2054-03-01", "Paiement divers SAMPLE", -235.0),
                                 ("2054-03-02", "Effet refus� sans provision", 235.0),
                                 ("2054-03-02", "Frais pour effet sans provision", -45.0)]),
    ("Banque Royale du Canada", [("2054-03-01", "Paiement divers SAMPLE", -235.0),
                                 ("2054-03-02", "Chèque refusé sans provision", 235.0),
                                 ("2054-03-02", "Frais pour effet sans provision", -45.0)]),
    # A Quebec returned item, alone and beside the bank's fee for it, and its plural.
    (None, [("2054-03-02", "EFFET RETOURNE", 410.0)]),
    (None, [("2054-03-02", "EFFET RETOURNE", 410.0), ("2054-03-02", "FR EFFET RET", -45.0)]),
    (None, [("2054-03-02", "EFFETS RETOURNES", 410.0)]),
    # The English check-word forms of NOT PAID.
    ("Fabrikam Bank", [("2054-03-02", "CHECK 1234 NOT PAID", 400.0)]),
    ("Fabrikam Bank", [("2054-03-02", "CHEQUE NOT PAID", 400.0)]),
    ("Fabrikam Bank", [("2054-03-02", "CHK 1234 NOT PAID", 400.0)]),
])
def test_r08_a_french_return_reversal_or_refusal_and_a_check_not_paid_are_non_revenue(bank, rows):
    records = _classify(rows, bank)
    credits = [record for record in records if record.amount > 0]
    assert credits
    for record in credits:
        assert record.revenue_classification == "non_revenue", record.description
        assert record.revenue_match_method in _REVERSAL_METHODS, record.description
    assert _true(records) == 0


@pytest.mark.parametrize(("text", "amount"), [
    ("RABAIS SUR LES FRAIS MENSUELS", 6.0),
    ("CREDIT D'INTERET", 1.43),
    ("INTERET CREDITE", 1.43),
    # Under the $1 floor too: the non-revenue rule runs first.
    ("CREDIT D'INTERET", 0.42),
])
def test_r08_the_french_fee_rebate_and_interest_are_strong_non_revenue(text, amount):
    record = _one(text, "TD Canada Trust", amount)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "strong_non_revenue_rule"


@pytest.mark.parametrize("text", ["ITEM RET NOT PAID", "RETURNED CHEQUE NOT PAID", "Item returned NSF"])
def test_r08_the_english_returned_items_stay_non_revenue(text):
    record = _one(text)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"


@pytest.mark.parametrize("rows", [
    # A word of a marker inside a deposit, a name or a transfer's memo, and a paid check, keep their readings.
    [("2054-03-02", "DEPOT CONTOSO PASSATION INC", 400.0)],
    [("2054-03-02", "DEPOT CHEQUE 1234", 400.0)],
    [("2054-03-02", "VIREMENT EFFETS SPECIAUX FABRIKAM INC", 400.0)],
    [("2054-03-02", "CHECK 1234 PAID TO NORTHWIND", 400.0)],
    [("2054-03-02", "CONTOSO LTD PAYMENT", 400.0), ("2054-03-09", "CONTOSO LTD PAYMENT", 410.0)],
])
def test_r08_a_marker_word_outside_the_return_wordings_keeps_the_credit_counted(rows):
    records = _classify(rows)
    for record in records:
        assert record.revenue_match_method not in _REVERSAL_METHODS, record.description
        assert record.revenue_tier == COUNTED, record.description
    assert _true(records) == sum(amount for _, _, amount in rows)


@pytest.mark.parametrize("text", ["CONTRE-PASSATION DE DEPOT", "EFFET RETOURNE", "CHEQUE NOT PAID"])
def test_r08_a_debit_printing_a_new_marker_stays_untiered_and_undoes_no_deposit(text):
    rows = [("2054-03-01", "DEPOT", 400.0), ("2054-03-02", text, -400.0)]
    records = _classify(rows, "CIBC")
    deposit, debit = records
    assert (debit.revenue_tier, debit.revenue_classification) == (None, None)
    assert _lender_fields(debit) == _lender_fields(_classify(rows[1:], "CIBC")[0])
    assert deposit.revenue_match_method != "matched_reversal_pair"
    assert deposit.contributes_to_true_revenue


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 2, R2-B08 (R22; I03's ground, standard D1, D3, §4.3): the deposit mode's undo debits also read TD Bank's
# DEP RETURN CHARGEBACK, a credit union's cut DEPOSIT TYPE CORRECT and a bank's row-leading CHARGE BACK of a deposited
# item (CHARGE BACK ITEM, CHARGE BACK - <return reason>); never a bare CHARGEBACK, a processor's chargeback (owner
# decision I42), the bank's fee, a bare DEP RETURN or TD's RTN NSF.
# ---------------------------------------------------------------------------------------------------------------------

def test_r22_td_bank_s_returned_deposit_chargeback_undoes_its_deposit():
    records = _classify([
        ("2054-03-02", "SBB MDEPOSIT", 600.0),
        ("2054-03-05", "DEP RETURN CHARGEBACK", -600.0),
        ("2054-03-05", "DEP RETURN FEE", -20.0),
    ], "TD Bank")
    assert records[0].revenue_classification == "non_revenue"
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert records[0].revenue_matched_rule == "returned_deposit_amount_date_match"
    assert _true(records) == 0
    assert records[1].reversed_by is None


def test_r22_a_cut_deposit_type_correction_undoes_one_of_two_equal_deposits():
    records = _classify([
        ("2054-03-02", "DEPOSIT", 1700.0),
        ("2054-03-02", "DEPOSIT TYPE CORRECT", -1700.0),
        ("2054-03-02", "DEPOSIT", 1700.0),
    ], "Fabrikam Credit Union")
    first, _, second = records
    assert first.revenue_classification == "non_revenue"
    assert first.revenue_match_method == "matched_reversal_pair"
    assert _tier(second) == (COUNTED, "no_payer_printed")
    assert _true(records) == 1700.0


def test_r22_a_bank_s_charge_back_of_a_deposited_check_undoes_the_deposit():
    records = _classify([
        ("2054-03-02", "FIRST DESKTOP REMOTE DEPOSIT", 900.0),
        ("2054-03-04", "CHARGE BACK ITEM CHECK 12345", -900.0),
    ])
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert _true(records) == 0


def test_r22_a_charge_back_for_an_irregular_signature_undoes_the_deposit_not_its_redeposit():
    records = _classify([
        ("2054-03-02", "DEPOSIT", 450.0),
        ("2054-03-04", "CHARGE BACK - SIGNATURE(S) IRREGULAR", -450.0),
        ("2054-03-06", "DEPOSIT", 450.0),
    ])
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert _tier(records[2]) == (COUNTED, "no_payer_printed")
    assert _true(records) == 450.0


@pytest.mark.parametrize(("rows", "why"), [
    # A processor's chargeback (owner decision I42) and a bare CHARGEBACK name no returned deposited item.
    ([("2054-03-02", "DEPOSIT", 450.0), ("2054-03-04", "HRTLAND PMT SYS CHARGEBACK 123456", -450.0)], "processor"),
    ([("2054-03-02", "DEPOSIT", 450.0), ("2054-03-04", "CHARGEBACK", -450.0)], "bare"),
    # The bank's fee for the return.
    ([("2054-03-02", "DEPOSIT", 20.0), ("2054-03-04", "DEP RETURN FEE", -20.0)], "fee"),
    # A card settlement is no deposit channel.
    ([("2054-03-02", "FABRIKAM MERCHANT SVCS VISA DEPOSIT", 450.0), ("2054-03-04", "CHARGE BACK ITEM", -450.0)], "card"),
    # Fifteen days is outside the window, and a return printed before the deposit undoes nothing after it.
    ([("2054-03-02", "DEPOSIT", 450.0), ("2054-03-17", "CHARGE BACK ITEM", -450.0)], "window"),
    ([("2054-03-01", "CHARGE BACK ITEM", -450.0), ("2054-03-02", "DEPOSIT", 450.0)], "before"),
    # TD's RTN NSF stays unconfirmed (audit I41).
    ([("2054-03-02", "DEPOSIT", 450.0), ("2054-03-04", "RTN NSF", -450.0)], "rtn nsf"),
])
def test_r22_a_deposit_with_no_returned_item_of_its_own_stays_counted(rows, why):
    records = _classify(rows)
    deposit = next(record for record in records if record.amount > 0)
    assert deposit.revenue_match_method != "matched_reversal_pair", why
    assert deposit.contributes_to_true_revenue, why


def test_r22_a_charge_back_item_never_undoes_a_named_payer_s_ach_payment():
    records = _classify([
        ("2054-03-02", "ACH CREDIT CONTOSO LTD PAYMENT", 450.0),
        ("2054-03-04", "CHARGE BACK ITEM", -450.0),
    ])
    assert records[0].revenue_classification == "verified_revenue"


def test_r22_a_deposit_correction_still_undoes_the_first_of_two_equal_deposits():
    # Control (no change): the full DEPOSIT CORRECTION was one of B3's correction markers.
    records = _classify([
        ("2054-03-02", "DEPOSIT", 1700.0),
        ("2054-03-02", "DEPOSIT CORRECTION", -1700.0),
        ("2054-03-02", "DEPOSIT", 1700.0),
    ], "Fabrikam Credit Union")
    assert records[0].revenue_match_method == "matched_reversal_pair"
    assert _tier(records[2]) == (COUNTED, "no_payer_printed")


@pytest.mark.parametrize(("text", "undoes"), [
    ("DEP RETURN CHARGEBACK", True),
    ("DEPOSIT RETURN CHARGE BACK", True),
    ("DEPOSIT TYPE CORRECT", True),
    ("DEPOSIT TYPE CORRECTION", True),
    ("DEPOSIT CORRECT", True),
    ("CHARGE BACK ITEM CHECK 12345", True),
    ("CHARGEBACK ITEMS", True),
    ("CHARGE BACK SIGNATURE S IRREGULAR", True),
    ("CHARGE BACK ENDORSEMENT MISSING", True),
    ("CHARGE BACK NSF", True),
    ("CHARGE BACK INSUFFICIENT FUNDS", True),
    ("CHARGE BACK UNCOLLECTED FUNDS", True),
    ("CHARGE BACK ACCOUNT CLOSED", True),
    ("CHARGE BACK ACCT CLOSED", True),
    ("CHARGE BACK STOP PAYMENT", True),
    ("CHARGE BACK REFER TO MAKER", True),
    ("03 04 CHARGE BACK ITEM", True),
    ("CHARGEBACK", False),
    ("HRTLAND PMT SYS CHARGEBACK 123456", False),
    ("MERCHANT CHARGEBACK ITEM 123456", False),
    ("CHARGE BACK FEE", False),
    ("CHARGE BACK ITEM FEE", False),
    ("DEP RETURN FEE", False),
    ("DEP RETURN", False),
    ("DEPOSIT RETURN", False),
    ("RTN NSF", False),
    ("ZELLE PAYMENT TO PAT SAMPLE CHARGE BACK ITEM", False),
])
def test_r22_the_undo_debit_reads_the_new_bank_forms_only(text, undoes):
    from analysis import transaction_classifier as tc

    assert tc._deposit_return_debit(text) is undoes


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 2, R2-B08 (R47 (a); standard D1, D3): an e-Transfer reclaim is the holder's own money coming back, read
# with the rail word directly before RECLAIM and a reference with a digit after it (spaced or colon-separated), or
# TD's RECLAIM E-TFR; never RECLAIM as a payer's word, nor RECLAIM after a reference (a sender's name follows it).
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("bank", "text"), [
    ("CIBC", "E-TRANSFER RECLAIM 123456789012"),
    ("CIBC", "E-TRANSFER RECLAIM: 123456789012"),
    ("Royal Bank of Canada", "INTERAC E-TRANSFER RECLAIM 123456789012"),
    ("TD Canada Trust", "RECLAIM E-TFR ***ABC"),
    # Controls: the glued and the bare forms stay non-revenue.
    ("CIBC", "E TRANSFER RECLAIM123456789012"),
    ("CIBC", "E TRANSFER RECLAIM"),
])
def test_r47_an_e_transfer_reclaim_is_non_revenue(bank, text):
    record = _one(text, bank)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"


@pytest.mark.parametrize(("bank", "text", "tier"), [
    ("CIBC", "E-TRANSFER 123456789012 CONTOSO SUPPLY", (COUNTED, "p2p")),
    # A reference between the rail word and RECLAIM: RECLAIM starts the sender's name.
    ("CIBC", "E-TRANSFER 123456789012 RECLAIM CONTOSO LLC", (COUNTED, "p2p")),
    ("Bank of America", ACH_PAYER.format(name="RECLAIM CONTOSO LLC"), ("verified", None)),
])
def test_r47_reclaim_as_a_sender_s_word_keeps_the_credit_s_reading(bank, text, tier):
    record = _one(text, bank)
    assert record.revenue_match_method != "reversal_cancellation_exclusion"
    assert _tier(record) == tier


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 2, R2-B08 (R48 part 2): a fee waiver is no company's name either (no legal-form word later on the row),
# as RETOUR, REV and UNAUTHORIZED already read.
# ---------------------------------------------------------------------------------------------------------------------

def test_r48_a_company_named_fee_waiver_keeps_its_verified_payment():
    record = _one("FABRIKAM FEE WAIVER CONSULTING INC DES:INVOICE PMT ID:1 INDN:NORTHWIND PLUMBING LLC CO ID:1 CCD",
                  "Bank of America", 1400.0)
    assert record.revenue_classification == "verified_revenue"


@pytest.mark.parametrize("text", ["NSF FEE WAIVER", "SERVICE FEE WAIVED", "24 HOUR GRACE OVERDRAFT FEE WAIVER"])
def test_r48_the_bank_s_fee_waivers_stay_non_revenue(text):
    record = _one(text, amount=35.0)
    assert record.revenue_classification == "non_revenue"
    assert record.revenue_match_method == "reversal_cancellation_exclusion"


# ---------------------------------------------------------------------------------------------------------------------
# Audit round 2, R2-B08 (R08, R47 (a), R48 part 2): the backstop and the census read the same new spellings as step 3.
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("hold_text", "held"), [
    ("EFFET RETOURNE", True),
    ("EFFETS RETOURNES", True),
    ("FR EFFET RET", True),
    ("CONTRE PASSATION DE CHEQUE", True),
    ("CONTREPASSATION DE DEBIT TLV CONTOSO", True),
    ("EFFET REFUSE SANS PROVISION", True),
    ("EFFET REFUS SANS PROVISION", True),
    ("CHEQUE REFUSE SANS PROVISION", True),
    ("CHQ REFUSEE SANS PROV", True),
    ("CHECK 1234 NOT PAID", True),
    ("CHEQUE NOT PAID", True),
    ("CHK 1234 NOT PAID", True),
    ("E TRANSFER RECLAIM 123456789012", True),
    ("INTERAC E TRANSFER RECLAIM 123456789012", True),
    ("E TFR RECLAIM ABC1234", True),
    ("RECLAIM E TFR ABC", True),
    ("RECLAIM INTERAC", True),
    ("NSF FEE WAIVER", True),
    # Never a name, a memo or a deposit.
    ("DEPOT CONTOSO PASSATION INC", False),
    ("VIREMENT EFFETS SPECIAUX FABRIKAM INC", False),
    ("CHECK 1234 PAID TO NORTHWIND", False),
    ("E TRANSFER 123456789012 RECLAIM CONTOSO LLC", False),
    ("E TRANSFER RECLAIM CONTOSO LLC", False),
    ("RECLAIM E TFRS CONTOSO", False),
    ("FABRIKAM FEE WAIVER CONSULTING INC INVOICE PMT", False),
])
def test_r2_b08_the_possible_return_backstop_reads_the_new_spellings(hold_text, held):
    from analysis import true_revenue

    assert (true_revenue._POSSIBLE_RETURN.search(hold_text) is not None) is held


def test_r2_b08_the_three_readers_hold_the_same_new_arms():
    """The classifier's step-3 credit markers, the pass's possible-return backstop and the census's declared markers
    each carry the batch's arms verbatim (the census's on the digit-masked text), so the copies stay in step."""
    from analysis import transaction_classifier as tc
    from analysis import true_revenue
    from tools import revenue_census as census

    arms = tc._RETURN_REFUND_R2_B08_ARMS
    assert len(arms) == 7
    classifier = {pattern.pattern for pattern in tc._RETURN_REFUND_CREDIT_PATTERNS}
    masked = {pattern.pattern for pattern in census._REVERSAL_MARKERS_56}
    for arm in arms:
        assert arm in classifier, arm
        assert arm in true_revenue._POSSIBLE_RETURN.pattern, arm
        assert census._on_masked(arm).pattern in masked, arm
    assert census._RETURN_REFUND_R2_B08_ARMS == true_revenue._RETURN_REFUND_R2_B08_ARMS == arms
    # The fee waiver arm carries the no-legal-form guard in all three.
    waiver = r"\bFEES? WAIVE[DR]?\b" + tc._NO_LEGAL_FORM_LATER
    assert waiver in arms
    assert tc._NO_LEGAL_FORM_LATER == true_revenue._NO_LEGAL_FORM_LATER == census._NO_LEGAL_FORM_LATER
    # The old unguarded arm is gone from every copy.
    bare = r"\bFEES? WAIVE[DR]?\b"
    assert bare not in classifier
    assert census._on_masked(bare).pattern not in masked
    assert r"|\bFEES? WAIVE[DR]?\b|" not in true_revenue._POSSIBLE_RETURN.pattern

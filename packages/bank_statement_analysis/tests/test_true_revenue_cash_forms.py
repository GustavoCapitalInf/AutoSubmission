"""Owner ruling 2026-10-02 (the underwriter's Q7, audit I34; true revenue spec §2.1, §8.2, §19.1, §20; audit round 2,
R2-OW14): "2 Make True revenue the default, make cash injections like ATM count as true revenue".

ATM, branch, teller and cash deposits count in True as counted_flagged / no_payer_printed and never verify (Q2 of
2026-09-28). The corpus check found none held or excluded for being cash, and two cash shapes the cash reader
(`_CASH_BRANCH_ATM_FORM`) missed, which a same-place debit then held as payer_also_debited or which counted as a named
payer: a retail cash load printed '<ST> <town> <street> US<RETAILER> W<n>' (arm R, `_RETAIL_CASH_LOAD`; inferred from
the shape, no statement opened) and a branch deposit printed 'DEPOSIT <place> <5-digit transit> <3-digit sequence>'
(arm S, `_BRANCH_DEPOSIT_TRANSIT`). Both now read on the cash, branch and ATM channel.

Fabricated rows only (CONTOSO, FABRIKAM, SAMPLE, neutral amounts, 2054 dates)."""
from __future__ import annotations

import re

import pytest

from analysis import transaction_classifier as tc
from analysis.transaction_classifier import reversals
from analysis.descriptor import payer
from analysis.descriptor import lexical
from analysis.descriptor import words
from analysis import true_revenue as tr
from analysis.schema import Statement, Transaction

HOLDER = "CONTOSO PLUMBING LLC"
NO_PAYER = ("counted_flagged", "no_payer_printed")

#: The cash reader as it read before this batch: the two arms taken off (each is its own alternative).
BEFORE = re.compile(
    words._CASH_BRANCH_ATM_FORM.pattern.replace("|" + words._RETAIL_CASH_LOAD, "").replace(
        "|" + words._BRANCH_DEPOSIT_TRANSIT, "")
)


def _statement(bank, rows, holder=HOLDER):
    return Statement(bank=bank, holder_name=holder, currency="USD", transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for index, (text, amount) in enumerate(rows)
    ])


def _read(bank, rows, holder=HOLDER):
    return tc.classify_statement_transactions(_statement(bank, rows, holder))


def _today(bank, rows, monkeypatch, holder=HOLDER):
    """The records as the cash reader read them before this batch."""
    with monkeypatch.context() as patch:
        patch.setattr(tc, "_CASH_BRANCH_ATM_FORM", BEFORE)
        patch.setattr(payer, "_CASH_BRANCH_ATM_FORM", BEFORE)
        patch.setattr(words, "_CASH_BRANCH_ATM_FORM", BEFORE)
        patch.setattr(reversals, "_CASH_BRANCH_ATM_FORM", BEFORE)
        return _read(bank, rows, holder)


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


def test_the_before_reader_is_the_reader_without_the_two_arms():
    assert BEFORE.pattern != words._CASH_BRANCH_ATM_FORM.pattern
    assert words._RETAIL_CASH_LOAD not in BEFORE.pattern and words._BRANCH_DEPOSIT_TRANSIT not in BEFORE.pattern
    assert words._CASH_BRANCH_ATM_FORM.pattern == BEFORE.pattern + "|" + words._RETAIL_CASH_LOAD + "|" + (
        words._BRANCH_DEPOSIT_TRANSIT)


# --- the arms ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "OK SAMPLEVILLE 1234 E 51ST USWALGREENS W1234",
    "KY SAMPLEVILLE 12 SAMPLE ST USWALGREENS W1234",
    "OK SAMPLEVILLE 1234 W SAMPLE ST USCVS W12",
    "OK SAMPLEVILLE 1234 E 51ST US7 ELEVEN W 12",
    "OK SAMPLEVILLE 1234 E 51ST US 7ELEVEN W12",
    "OK SAMPLEVILLE 1234 E 51ST USWAL MART W123",
    "OK SAMPLEVILLE 1234 E 51ST USWALMART W123",
    "OK SAMPLEVILLE 1234 E 51ST USDOLLAR GENERAL W1",
    "OK SAMPLEVILLE 1234 E 51ST USRITE AID W1",
    "OK SAMPLEVILLE 1234 E 51ST USFAMILY DOLLAR W1",
    "OK SAMPLEVILLE 1234 E 51ST USCIRCLE K W1",
])
def test_arm_r_reads_a_retail_cash_load(text):
    assert re.search(words._RETAIL_CASH_LOAD, text)
    assert words._CASH_BRANCH_ATM_FORM.search(text) and not BEFORE.search(text)


@pytest.mark.parametrize("text", [
    "OK SAMPLEVILLE 1234 E 51ST USWALGREENS",              # no W id
    "OK SAMPLEVILLE 1234 E 51ST USWALGREENS W1234 REFUND",  # not the row's end
    "OK SAMPLEVILLE 1234 E 51ST BUSWALGREENS W1234",        # a word ending in US
    "WALGREENS CO DES:VENDOR PMT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD",
    "OK SAMPLEVILLE 1234 E 51ST USTARGET W1234",            # not a listed retailer
])
def test_arm_r_reads_nothing_else(text):
    assert not re.search(words._RETAIL_CASH_LOAD, text)


@pytest.mark.parametrize("text", [
    "DEPOSIT SAMPLEVILLE 12345 001",
    "DEPOSIT SAMPLE AND MAIN 12345 001",
    "DEPOSIT SAMPLEVILLE ON 12345 001",
    "DEPOSIT NORTH SAMPLE BAY ON 12345 001",
    "03 02 DEPOSIT SAMPLEVILLE 12345 001",
])
def test_arm_s_reads_a_branch_deposit(text):
    assert re.search(words._BRANCH_DEPOSIT_TRANSIT, text)
    assert words._CASH_BRANCH_ATM_FORM.search(text)


@pytest.mark.parametrize("text", [
    "DEPOSIT CONTOSO LLC 12345 001",                  # a legal form: a named depositor
    "DEPOSIT FABRIKAM LTD 12345 001",
    "DEPOSIT FABRIKAM 1234 001",                      # four digits, not a transit
    "DEPOSIT FABRIKAM 123456 001",
    "DEPOSIT FABRIKAM 12345 0001",
    "DEPOSIT 000000000001 12345 BANKCD DEP CR CHASE PAYMENTECH",
    "DEPOSIT ONE TWO THREE FOUR FIVE 12345 001",      # five words
    "DEPOSIT SAMPLEVILLE 12345 001 EXTRA",
    "MOBILE DEPOSIT SAMPLEVILLE 12345 001",           # not at the row's start
])
def test_arm_s_reads_nothing_else(text):
    assert not re.search(words._BRANCH_DEPOSIT_TRANSIT, text)


# Audit round 3, R3-B07 (R3-45; §8.1 T4, §17.1 (3)): off Scotiabank's statements, arm S's whole-row match never counts
# as "inside a deposit form", so R35's funder-name guard (a financing word after a name word keeps its place and holds)
# reads there as before arm S. On Scotiabank's statements the words are the branch's printed name: unchanged.
R345_FUNDER_PLACES = [
    "DEPOSIT WOODGROVE CAPITAL PLAZA 54321 987",
    "DEPOSIT WOODGROVE CAPITAL CITY BRANCH 54321 987",
    "DEPOSIT LITWARE LENDING PARK 54321 987",
    "DEPOSIT WOODGROVE FUNDING SAMPLETON TX 54321 987",
]
R345_FINANCING = ("excluded_pending_review", "financing_named_payer")


@pytest.mark.parametrize("bank", ["Wells Fargo", "TD Bank", None])
@pytest.mark.parametrize("text", R345_FUNDER_PLACES)
def test_r3_45_off_scotiabank_a_funder_s_name_before_a_place_holds(text, bank):
    assert re.search(words._BRANCH_DEPOSIT_TRANSIT, text)
    assert _tier(_read(bank, [(text, 2345.67)])[0]) == R345_FINANCING


@pytest.mark.parametrize("text", [*R345_FUNDER_PLACES, "DEPOSIT WESTGATE CAPITAL PLAZA 54321 987"])
def test_r3_45_on_scotiabank_the_branch_s_name_still_counts(text):
    assert _tier(_read("Scotiabank", [(text, 2345.67)])[0]) == NO_PAYER


@pytest.mark.parametrize("bank", ["Wells Fargo", "TD Bank", None, "Scotiabank"])
def test_r3_45_controls(bank):
    # A place alone and a town's name count on every bank; a financing word with no place holds on every bank.
    assert _tier(_read(bank, [("DEPOSIT CAPITAL PLAZA 54321 987", 2345.67)])[0]) == NO_PAYER
    assert _tier(_read(bank, [("DEPOSIT MAPLE GROVE 54321 987", 2345.67)])[0]) == NO_PAYER
    assert _tier(_read(bank, [("DEPOSIT WOODGROVE CAPITAL 54321 987", 2345.67)])[0]) == R345_FINANCING


def test_r3_45_the_form_without_arm_s_is_the_form_s_other_alternatives():
    assert tr._cash_form_without_arm_s().pattern + "|" + words._BRANCH_DEPOSIT_TRANSIT == words._CASH_BRANCH_ATM_FORM.pattern
    assert tr._SCOTIABANK.search("SCOTIABANK") and tr._SCOTIABANK.search("THE BANK OF NOVA SCOTIA")
    assert not tr._SCOTIABANK.search("WELLS FARGO")


# --- the cash forms that already counted ------------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "ATM CASH DEPOSIT 03/01 1234 MAIN ST SAMPLEVILLE CA", "COUNTER DEPOSIT", "TELLER DEPOSIT SAMPLEVILLE BRANCH",
    "DEPOSIT",
])
def test_the_cash_forms_that_counted_still_count_flagged(text, monkeypatch):
    rows = [(text, 500.0), (text, 500.0), (text, 500.0)]
    records = _read("Wells Fargo", rows)
    assert [_tier(record) for record in records] == [NO_PAYER] * 3
    assert not any(record.revenue_classification == "verified_revenue" for record in records)
    assert [_tier(record) for record in _today("Wells Fargo", rows, monkeypatch)] == [NO_PAYER] * 3


# --- arm R: the retail cash loads -------------------------------------------------------------------------------------

BLUEVINE_LOAD = "OK SAMPLEVILLE 1234 E 51ST USWALGREENS W1234"
BLUEVINE_ROWS = [
    (BLUEVINE_LOAD, 1000.0),
    (BLUEVINE_LOAD, 700.0),
    ("SAMPLEVILLE HARDWARE1234 SAMPLEVILLE OK", -45.0),
]


def test_a_retail_cash_load_counts_flagged_beside_a_purchase_at_the_same_place(monkeypatch):
    today = _today("Bluevine", BLUEVINE_ROWS, monkeypatch)
    assert [_tier(record) for record in today[:2]] == [("excluded_pending_review", "payer_also_debited")] * 2
    records = _read("Bluevine", BLUEVINE_ROWS)
    assert [_tier(record) for record in records[:2]] == [NO_PAYER] * 2
    assert [record.revenue_classification for record in records[:2]] == ["unverified_deposit"] * 2
    assert all(record.contributes_to_true_revenue for record in records[:2])
    assert tr._channel(lexical.revenue_text(BLUEVINE_LOAD), "Bluevine") == "cash_branch_atm"
    assert payer.channel_gate(lexical.revenue_text(BLUEVINE_LOAD)) == "closed"
    assert payer.payer_region(lexical.revenue_text(BLUEVINE_LOAD)) == ""


def test_a_retail_cash_load_never_verifies(monkeypatch):
    rows = [(BLUEVINE_LOAD, amount) for amount in (400.0, 400.0, 400.0, 400.0)]
    records = _read("Bluevine", rows)
    assert [_tier(record) for record in records] == [NO_PAYER] * 4
    today = _today("Bluevine", rows, monkeypatch)
    assert not any(record.revenue_classification == "verified_revenue" for record in today)


def test_a_retail_cash_load_moves_no_debit(monkeypatch):
    rows = BLUEVINE_ROWS + [("KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO PLUMBING LLC CO ID:0000000002 CCD",
                             -850.0)]
    today, after = _today("Bluevine", rows, monkeypatch), _read("Bluevine", rows)
    for before, record in zip(today, after):
        if record.amount < 0:
            assert record == before


def test_the_load_without_its_retailer_id_keeps_today_s_reading(monkeypatch):
    alone = [("OK SAMPLEVILLE 1234 E 51ST USWALGREENS", 300.0)]
    assert [_tier(record) for record in _read("Bluevine", alone)] == [("counted_flagged", "named_payer_unlabelled")]
    beside = alone + [("SAMPLEVILLE HARDWARE1234 SAMPLEVILLE OK", -45.0)]
    assert _tier(_read("Bluevine", beside)[0]) == _tier(_today("Bluevine", beside, monkeypatch)[0]) == (
        "excluded_pending_review", "payer_also_debited")


# --- arm S: the branch deposits ---------------------------------------------------------------------------------------

BRANCH_DEPOSIT = "DEPOSIT SAMPLEVILLE 12345 001"


def test_a_branch_deposit_counts_flagged_beside_a_withdrawal_at_the_same_branch(monkeypatch):
    rows = [(BRANCH_DEPOSIT, 5000.0), ("ABM WITHDRAWAL SAMPLEVILLE 12345", -100.0)]
    # Today (since audit round 2, R2-B02 R02 dropped cash withdrawals from the counter debits) it counts as a named
    # payer, which a repeat could verify; it is a branch deposit, which never verifies.
    assert _tier(_today("Scotiabank", rows, monkeypatch)[0]) == ("counted_flagged", "named_payer_unlabelled")
    record = _read("Scotiabank", rows)[0]
    assert _tier(record) == NO_PAYER
    assert record.revenue_classification == "unverified_deposit"
    assert tr._channel(lexical.revenue_text(BRANCH_DEPOSIT), "Scotiabank") == "cash_branch_atm"


def test_a_branch_deposit_three_times_never_verifies():
    records = _read("Scotiabank", [(BRANCH_DEPOSIT, 5000.0)] * 3)
    assert [_tier(record) for record in records] == [NO_PAYER] * 3
    assert not any(record.revenue_classification == "verified_revenue" for record in records)


@pytest.mark.parametrize("text", ["DEPOSIT CONTOSO LLC 12345 001", "DEPOSIT FABRIKAM 1234 001"])
def test_a_named_deposit_keeps_today_s_reading(text, monkeypatch):
    rows = [(text, 5000.0), ("ABM WITHDRAWAL SAMPLEVILLE 12345", -100.0)]
    assert [_tier(record) for record in _read("Scotiabank", rows)] == [
        _tier(record) for record in _today("Scotiabank", rows, monkeypatch)]
    assert _tier(_read("Scotiabank", rows)[0]) != NO_PAYER


def test_a_card_settlement_deposit_printing_digits_after_deposit_stays_verified(monkeypatch):
    settlement = "DEPOSIT 000000000001 12345 BANKCD DEP CR CHASE PAYMENTECH"
    rows = [(settlement, 1200.0), (settlement, 1300.0), (settlement, 1400.0)]
    records = _read("Scotiabank", rows)
    assert [record.revenue_classification for record in records] == ["verified_revenue"] * 3
    assert [(record.revenue_tier, record.revenue_match_method) for record in records] == [
        (record.revenue_tier, record.revenue_match_method) for record in _today("Scotiabank", rows, monkeypatch)]


# --- the controls -----------------------------------------------------------------------------------------------------

def test_a_retailer_paying_by_ach_stays_verified_and_a_purchase_return_stays_non_revenue(monkeypatch):
    rows = [
        ("WALGREENS CO DES:VENDOR PMT ID:0001 INDN:CONTOSO PLUMBING LLC CO ID:0000000001 CCD", 2400.0),
        ("PURCHASE RETURN AUTHORIZED ON 03/01 WALGREENS #1234 SAMPLEVILLE OK S0000 CARD 1234", 25.0),
    ]
    vendor, refund = _read("Bank of America", rows)
    assert (vendor.revenue_tier, vendor.revenue_match_method) == ("verified", "payer_remittance_descriptor")
    assert refund.revenue_tier == "non_revenue"
    assert [_tier(record) for record in _read("Bank of America", rows)] == [
        _tier(record) for record in _today("Bank of America", rows, monkeypatch)]

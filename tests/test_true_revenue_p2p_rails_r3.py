"""Audit round 3, R3-B12 (true revenue spec §8.2, §8.4, §20): pass 7 reads the consumer person-to-person rails as the
banks print them.

* R3-12 (the owner's amendment of 2026-10-06 to the underwriter's Q3, R2-OW17: "holds as for other P2P"): PNC prints
  the Zelle rail as 'ZEL FROM <sender>', which pass 7 reads as its 'ZELLE FROM' twin on its own text
  (`true_revenue.pass_text`): the person-to-person channel, the sender's key pooled with the same sender's ZELLE rows,
  the round-sum repeat and R2-B02's (R02) person match of the counter-debit hold. The classifier's consumer rail, the
  legacy classes and the debits are unchanged.
* R3-29 (Q3 of 2026-10-02: "Other P2P rails (Interac e-Transfer, ...) are unchanged"): Banque Royale prints its Interac
  autodeposit in French, 'DEPOT AUTO VIREMENTS PAR COURRIEL <sender> <reference>' (Interac's French name, virement par
  courriel), which pass 7 reads as the e-Transfer rail, plural or singular, never as a cash or branch DEPOT.
* R3-56: a wire is never a Zelle deposit (`true_revenue.zelle_deposit`): the word ZELLE inside a wire's memo is no rail.

Fabricated rows only (CONTOSO, FABRIKAM, NORTHWIND, SAMPLE; neutral amounts; March 2054)."""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

import pytest

from analysis import true_revenue, zelle_view
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    classify_statement_readings,
    classify_statement_transactions,
    normalize_transaction_description,
    revenue_text,
)
from tests import zelle_setting_fixtures as fx

HELD = "excluded_pending_review"
COUNTED = "counted_flagged"
EXCLUDED = ("non_revenue", "zelle_excluded")
P2P = (COUNTED, "p2p")
REPEAT = (HELD, "p2p_round_repeat")

PNC = "PNC Bank"
BAKERY = "CONTOSO BAKERY LLC"
ROYALE = "Banque Royale du Canada"
PLOMBERIE = "CONTOSO PLOMBERIE INC."
BOFA = "Bank of America"


def _statement(rows, *, bank, holder, currency=None):
    """(text, amount, day) rows, credits and debits by their sign."""
    fields = dict(account_name=holder, bank=bank, transactions=[
        Transaction(date=f"2054-03-{day:02d}", description=text, amount=amount,
                    direction="credit" if amount > 0 else "debit")
        for text, amount, day in rows
    ])
    if currency:
        fields["currency"] = currency
    return Statement(**fields)


def _yes(rows, *, bank=PNC, holder=BAKERY, currency=None):
    return classify_statement_transactions(_statement(rows, bank=bank, holder=holder, currency=currency),
                                           zelle_true_revenue=True)


def _no(rows, *, bank=PNC, holder=BAKERY, currency=None):
    return classify_statement_transactions(_statement(rows, bank=bank, holder=holder, currency=currency))


def _tier(record):
    return record.revenue_tier, record.revenue_tier_reason


def _credit_tiers(records):
    return [_tier(record) for record in records if record.amount > 0]


def _text(raw):
    return revenue_text(normalize_transaction_description(raw))


def _zelle_twin(rows):
    """The same statement with each ZEL credit printed 'ZELLE FROM <the same words>'; the debits kept as printed."""
    return [(re.sub(r"^ZEL FROM ", "ZELLE FROM ", text) if amount > 0 else text, amount, day)
            for text, amount, day in rows]


# --- R3-12: PNC's ZEL rail reads as its ZELLE twin in pass 7 ---------------------------------------------------------

P1 = [("ZEL FROM PAT SAMPLE WFCT0ABCDE12", 1000.0, 2), ("ZEL FROM PAT SAMPLE WFCT0ABCDE13", 1000.0, 9)]


def test_r3_12_p1_a_zel_round_pair_is_held_as_a_round_repeat_under_yes():
    # Before the batch: counted_flagged / named_payer_unlabelled (the channel 'other', no round-sum repeat).
    assert _credit_tiers(_yes(P1)) == [REPEAT, REPEAT]


def test_r3_12_p1_the_no_reading_keeps_the_exclusion_and_names_the_p2p_reading():
    records = [record for record in _no(P1) if record.amount > 0]
    assert [_tier(record) for record in records] == [EXCLUDED, EXCLUDED]
    # Before the batch: ('counted_flagged', 'named_payer_unlabelled').
    assert [true_revenue.zelle_prior_reading(record) for record in records] == [REPEAT, REPEAT]


#: (rows, the Yes reading of each ZEL credit). The binding assertion is the twin parity; the expected readings are
#: the brief's (before the batch: a, b and f counted named_payer_unlabelled, f held payer_also_debited).
TWINS = {
    "a_round_pair": (P1, [REPEAT, REPEAT]),
    "b_odd_pair": ([("ZEL FROM PAT SAMPLE WFCT0ABCDE12", 1237.45, 2), ("ZEL FROM PAT SAMPLE WFCT0ABCDE13", 1237.45, 9)],
                   [P2P, P2P]),
    "c_holder": ([("ZEL FROM CONTOSO BAKERY LLC", 2500.0, 3)], [(HELD, "holder_name")]),
    "d_financing": ([("ZEL FROM FABRIKAM FUNDING LLC", 5000.0, 3)], [(HELD, "financing_named_payer")]),
    # A same-person round trip stays held.
    "e_round_trip": ([("ZEL FROM MARCUS SAMPLE", 3200.0, 3), ("ZEL TO MARCUS SAMPLE PNCAA0X1234567", -800.0, 6)],
                     [(HELD, "payer_also_debited")]),
    # R2-B02 (R02): the person-to-person credit's sender names a debit only by its whole name, never by its first word.
    "f_other_person": ([("ZEL FROM MARCUS SAMPLE", 3200.0, 3), ("ZEL TO MARCUS CONTOSO PNCAA0X1234567", -800.0, 6)],
                       [P2P]),
}


@pytest.mark.parametrize("case", sorted(TWINS))
def test_r3_12_p2_a_zel_credit_reads_as_its_zelle_twin_under_yes(case):
    rows, expected = TWINS[case]
    zel, zelle = _credit_tiers(_yes(rows)), _credit_tiers(_yes(_zelle_twin(rows)))
    assert zel == zelle
    assert zel == expected


@pytest.mark.parametrize("case", sorted(TWINS))
def test_r3_12_p2_the_no_reading_s_prior_is_the_zelle_twin_s(case):
    rows, expected = TWINS[case]
    zel = [record for record in _no(rows) if record.amount > 0]
    zelle = [record for record in _no(_zelle_twin(rows)) if record.amount > 0]
    assert [_tier(record) for record in zel] == [EXCLUDED] * len(expected)
    assert [true_revenue.zelle_prior_reading(record) for record in zel] == [
        true_revenue.zelle_prior_reading(record) for record in zelle] == expected


def test_r3_12_p2_the_debits_keep_the_classifier_s_reading():
    # The debits are read on their own text: the ZEL TO debit is not respelled (§8.4's residual).
    rows = TWINS["e_round_trip"][0]
    yes, no = _yes(rows), _no(rows)
    assert [record for record in yes if record.amount < 0] == [record for record in no if record.amount < 0]


def test_r3_12_p3_one_sender_s_zel_and_zelle_round_sums_pool():
    rows = [("ZEL FROM PAT SAMPLE WFCT0ABCDE12", 500.0, 2),
            ("ZELLE FROM PAT SAMPLE ON 03/09 REF # BAC0A1B2C3D4", 1200.0, 9)]
    # Before the batch: the ZEL row counted named_payer_unlabelled and the ZELLE row counted p2p.
    assert _credit_tiers(_yes(rows)) == [REPEAT, REPEAT]


def _holder(bank, original):
    return SimpleNamespace(bank=bank, original_description=original)


@pytest.mark.parametrize(("text", "expected"), [
    ("ZEL FROM PAT SAMPLE WFCT0ABCDE12", "ZELLE FROM PAT SAMPLE WFCT0ABCDE12"),
    ("ZEL TO PAT SAMPLE 1234", "ZELLE TO PAT SAMPLE 1234"),
    ("HAZEL FROM PAT SAMPLE", "HAZEL FROM PAT SAMPLE"),
    ("ZELDA FROM PAT SAMPLE", "ZELDA FROM PAT SAMPLE"),
    ("ZEL", "ZEL"),
    ("ZEL 1234 PAT SAMPLE", "ZEL 1234 PAT SAMPLE"),
    ("ZELLE FROM PAT SAMPLE", "ZELLE FROM PAT SAMPLE"),
])
def test_r3_12_p4_pass_text_spells_pnc_s_zel_as_zelle(text, expected):
    assert true_revenue.pass_text(_holder(PNC, text), text) == expected


def test_r3_12_p4_pass_text_drops_td_s_transfer_code_as_before():
    record = _holder("TD Canada Trust", "E-TRANSFER ***PAY")
    assert true_revenue.pass_text(record, "E TRANSFER PAY") == true_revenue.without_transfer_code(
        record, "E TRANSFER PAY") == "E TRANSFER"


def test_r3_12_p4_the_census_reads_a_zel_credit_s_channel_and_key_as_its_zelle_twin_s():
    zel_raw, zelle_raw = "ZEL FROM PAT SAMPLE WFCT0ABCDE12", "ZELLE FROM PAT SAMPLE WFCT0ABCDE12"
    [zel] = _no([(zel_raw, 1234.0, 3)])
    [zelle] = _no([(zelle_raw, 1234.0, 3)])
    zel_facts = true_revenue.guard_facts(zel, _text(zel_raw))
    zelle_facts = true_revenue.guard_facts(zelle, _text(zelle_raw))
    assert zel_facts["payer_key_digest"] is not None
    assert zel_facts["payer_key_digest"] == zelle_facts["payer_key_digest"]
    assert zel_facts == zelle_facts


@pytest.mark.parametrize(("bank", "text", "expected"), [
    ("Chase", "VENMO FROM PAT SAMPLE", P2P),
    ("Royal Bank of Canada", "INTERAC E-TRANSFER RECEIVED PAT SAMPLE", P2P),
    ("Royal Bank of Canada", "E TRANSFER AUTODEPOSIT PAT SAMPLE C1AX23X", P2P),
])
def test_r3_12_the_other_rails_read_as_before(bank, text, expected):
    assert _credit_tiers(_yes([(text, 1234.0, 3)], bank=bank)) == [expected]


def test_r3_12_the_legacy_class_of_a_zel_credit_stays_other():
    [record] = _yes([("ZEL FROM PAT SAMPLE WFCT0ABCDE12", 500.0, 3)])
    assert record.classification == "other"


# --- R3-29: Banque Royale's French autodeposit is the Interac rail ---------------------------------------------------


def _royale(rows):
    return _yes(rows, bank=ROYALE, holder=PLOMBERIE, currency="CAD")


F1 = [(f"DEPOT AUTO VIREMENTS PAR COURRIEL NORTHWIND C1AX2{n}X", 500.0, day) for n, day in ((3, 2), (4, 9), (5, 16))]
F2 = [("DEPOT AUTO VIREMENTS PAR COURRIEL CONTOSO PLOMBERIE C9ZZ99Z", 1200.0, 3)]
F3 = [("DEPOT AUTO VIREMENTS PAR COURRIEL SAMPLE C4BB55B", 137.45, 3)]
F4 = [("DEPOT AUTO VIREMENT PAR COURRIEL SAMPLE C4BB56B", 137.45, 3)]


def test_r3_29_f1_one_sender_s_french_round_sums_are_held_as_a_round_repeat():
    # Before the batch: counted_flagged / no_payer_printed (a cash or branch DEPOT).
    assert _credit_tiers(_royale(F1)) == [REPEAT] * 3


def test_r3_29_f2_the_holder_s_own_french_autodeposit_is_held():
    assert _credit_tiers(_royale(F2)) == [(HELD, "holder_name")]


def test_r3_29_f3_a_one_off_french_autodeposit_is_counted_as_p2p():
    assert _credit_tiers(_royale(F3)) == [P2P]


def test_r3_29_f4_the_singular_is_the_rail_too():
    # Before the batch: a French transfer (VIREMENT with no Interac form).
    records = _royale(F4)
    assert _credit_tiers(records) == [P2P]
    assert true_revenue._channel(_text(F4[0][0]), ROYALE) == "person_to_person"


def _english(rows):
    """The English twin: 'E TRANSFER AUTODEPOSIT <sender> <reference>'."""
    return [(re.sub(r"^DEPOT AUTO VIREMENTS? PAR COURRIEL ", "E TRANSFER AUTODEPOSIT ", text), amount, day)
            for text, amount, day in rows]


@pytest.mark.parametrize("rows", [F1, F2, F3, F4], ids=["F1", "F2", "F3", "F4"])
def test_r3_29_f5_a_french_autodeposit_reads_as_its_english_twin(rows):
    assert _credit_tiers(_royale(rows)) == _credit_tiers(_royale(_english(rows)))


def test_r3_29_f6_the_counter_debit_hold_reads_the_french_sender():
    rows = [("DEPOT AUTO VIREMENTS PAR COURRIEL MARCUS SAMPLE C7CC77C", 600.0, 3),
            ("E TRANSFER SENT MARCUS SAMPLE", -150.0, 6)]
    assert _credit_tiers(_royale(rows)) == [(HELD, "payer_also_debited")]


@pytest.mark.parametrize(("debit", "expected"), [
    # R2-B02 (R02): a person-to-person credit's sender names a debit only by its whole name.
    ("MARCUS CONTOSO", P2P),
    ("BILL PAYMENT MARCUS CONTOSO", P2P),
    ("E TRANSFER SENT MARCUS CONTOSO", P2P),
    ("MARCUS SAMPLE", (HELD, "payer_also_debited")),
])
@pytest.mark.parametrize("rail", ["DEPOT AUTO VIREMENTS PAR COURRIEL", "DEPOT AUTO VIREMENT PAR COURRIEL"])
def test_r3_29_f6_the_french_sender_names_a_debit_as_its_english_twin_s_does(rail, debit, expected):
    rows = [(f"{rail} MARCUS SAMPLE C7CC77C", 600.0, 3), (debit, -150.0, 6)]
    assert _credit_tiers(_royale(rows)) == _credit_tiers(_royale(_english(rows))) == [expected]


@pytest.mark.parametrize(("text", "expected"), [
    # Transfer wording, as before the batch.
    ("VIREMENT EN LIGNE TF 0001", (HELD, "transfer_no_counterparty")),
    ("VIREMENT ENTRE COMPTES", (HELD, "transfer_no_counterparty")),
    # Interac's own French autodeposit reads through INTERAC, as before.
    ("VIREMENT INTERAC DEPOT AUTOMATIQUE NORTHWIND", P2P),
    # A bare DEPOT is a branch deposit, and DEPOT DIRECT a direct deposit, as before.
    ("DEPOT", (COUNTED, "no_payer_printed")),
    ("DEPOT DIRECT FABRIKAM PAIE", (HELD, "payroll_or_salary")),
])
def test_r3_29_the_other_french_rows_read_as_before(text, expected):
    assert _credit_tiers(_royale([(text, 1234.0, 3)])) == [expected]


def test_r3_29_a_bare_depot_stays_a_branch_deposit():
    assert true_revenue._channel(_text("DEPOT"), ROYALE) == "cash_branch_atm"


@pytest.mark.parametrize("text", [row[0] for row in (*F1, *F2, *F3, *F4)])
def test_r3_29_a_french_autodeposit_is_no_zelle_deposit(text):
    assert true_revenue.zelle_deposit(_text(text)) is False


def test_r3_29_the_classifier_s_rail_is_unchanged():
    # The 5.5 channel gate, the legacy classes and the debits read the classifier's rail, which this batch leaves as
    # it is: its VIREMENT never reads the plural (§8.4's residual).
    from analysis import transaction_classifier as classifier

    assert "COURRIEL" not in classifier._CONSUMER_P2P_RAIL.pattern
    assert classifier._CONSUMER_P2P_RAIL.search(_text(F1[0][0])) is None


# --- R3-56: a wire is never a Zelle deposit --------------------------------------------------------------------------

W1 = ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1200 ET TRN:2054030200001 ORIG:NORTHWIND TRADING INC ID:0001 "
      "PMT DET:INVOICE 1234 PAID BY WIRE INSTEAD OF ZELLE")
W0 = ("WIRE TYPE:WIRE IN DATE: 540302 TIME:1200 ET TRN:2054030200001 ORIG:NORTHWIND TRADING INC ID:0001 "
      "PMT DET:INVOICE 1234 PAID BY WIRE")
W2 = "DEPOSIT WIRE IN 000123 ORG NORTHWIND TRADING INC OBI INVOICE 1234 NOT VIA ZELLE"


@pytest.mark.parametrize("text", [W1, W2])
def test_r3_56_a_wire_s_memo_is_no_zelle_rail(text):
    assert true_revenue.zelle_deposit(_text(text)) is False


def test_r3_56_w1_a_wire_printing_zelle_has_one_reading_never_excluded():
    # Before the batch the No reading excluded it (non_revenue / zelle_excluded) and only Yes counted it.
    statement = _statement([(W1, 6400.0, 3)], bank=BOFA, holder=BAKERY)
    no, yes = classify_statement_readings(statement)
    assert yes is None
    assert true_revenue.zelle_credits_present(no, set()) is False
    [w1] = no
    assert _tier(w1) == (COUNTED, "wire_named_sender")
    assert true_revenue.zelle_prior_reading(w1) is None
    assert w1.contributes_to_true_revenue


def test_r3_56_w1_the_classifier_s_rail_still_costs_the_wire_its_verification():
    # §8.4's recorded residual (the brief's "Not fixed"): the classifier's consumer rail, shared with the 5.5 channel
    # gate, the legacy classes and the debits, still reads the memo's word, so the wire is counted where its twin
    # without the word is verified. Pinned so a later change is deliberate.
    [w1] = classify_statement_transactions(_statement([(W1, 6400.0, 3)], bank=BOFA, holder=BAKERY))
    [w0] = classify_statement_transactions(_statement([(W0, 6400.0, 3)], bank=BOFA, holder=BAKERY))
    assert (w0.revenue_tier, w0.revenue_match_method) == ("verified", "payer_remittance_descriptor")
    assert (w1.revenue_tier, w1.classification) == (COUNTED, "transfer")


def test_r3_56_w1_the_served_yes_payload_tags_no_zelle_deposit():
    stored = json.loads(json.dumps(fx.payload([(W1, 6400.00, 3)], holder=BAKERY)))
    served = zelle_view.apply_zelle_view(stored, counted=True)
    [transaction] = served["statement"]["transactions"]
    assert zelle_view.ZELLE_ROW_TAG not in transaction
    assert zelle_view.ZELLE_DEPOSITS_KEY not in (served.get("metrics") or {})
    assert zelle_view.zelle_rows(stored) == ([], False)


#: The rail rows that stay Zelle deposits: mid-row rail layouts, the ACH entry-description forms (kept: an entry the
#: sender wrote as ZELLE most plausibly went through Zelle), a card push, and a company whose name holds the word
#: (§8.4's recorded residual, pinned so a later change is deliberate).
STILL_ZELLE = [
    "EARLY WARNING S DES:ZELLE ID:000001 INDN:CONTOSO BAKERY LLC CO ID:0000000001 PPD",
    "NORTHWIND TRADING INC DES:ZELLE PMT ID:0001 INDN:CONTOSO BAKERY LLC",
    "VISA DIRECT ZELLE PAT SAMPLE",
    "TRANSFER IN ZELLE FROM PAT SAMPLE",
    "DE ZELLE HOLDINGS LLC DES:VENDOR PAY ID:0001",
    "ZEL FROM PAT SAMPLE WFCT0ABCDE12",
    "NOW NETWORK CREDIT ZELLE CREDIT NOW NET ID 1A2B ZELLE PAT SAMPLE 5678",
]


@pytest.mark.parametrize("text", STILL_ZELLE)
def test_r3_56_the_rail_rows_stay_zelle_deposits(text):
    assert true_revenue.zelle_deposit(_text(text)) is True

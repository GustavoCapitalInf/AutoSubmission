"""Owner ruling 2026-10-02 (the underwriter's Q12; spec §6.1 step 3a, §6.3, §7.6, §8.6, §19.1, §20; audit I40, GOV
class E of 2026-09-30): the seven government payments that print no purpose are non_revenue (Excluded), not held:
Minnesota Management and Budget's MN STATE MMB, the VA's 36 TREAS 310 MISC PAY (agency code 36 only), Wisconsin DCF's
WI DCF ... WIDCF DD, PROVINCIAL PAYMENT PROVINCE OF BC, Ontario's WSIB, GOUV QUEBEC MSP and North Dakota's WORKFORCE
SAFETY. "No purpose" means the row prints only the form, posting words, ACH field labels, SEC codes, references and the
no-purpose entries (MISC PAY, PAYMENT, PMT, DD, WIDCF, EME, MSP, DIV), read with each receiver field's value removed and
every field after it kept (Bank of America's PMT INFO addenda is read; American Express's template up to its id). A
purpose printed anywhere (VENDOR PAY, PROV PAY, RMR IV, an invoice in the addenda, the VA's XXVA entry codes, a grant,
a rebate, a claim) keeps the row's reading, and so does every form the ruling did not name. Fabricated rows only: the
holder NORTHWIND CLINIC LLC printed in the receiver fields, neutral amounts and dates."""
from __future__ import annotations

import pytest

from analysis.description_text import normalize_transaction_description
from analysis.schema import Statement, Transaction
from analysis.transaction_classifier import (
    GOVERNMENT_NO_PURPOSE_FORMS,
    classify_statement_transactions,
    government_no_purpose,
    revenue_text,
)

HOLDER = "NORTHWIND CLINIC LLC"
METHOD = "government_no_purpose_exclusion"
RULE = "government_payment_no_purpose"
VERIFIED, COUNTED, HELD = "verified", "counted_flagged", "excluded_pending_review"
UNIDENTIFIED, AMBIGUOUS = "unidentified_posted_credit", "ambiguous_credit_descriptor"

_BOFA = "{payer} DES:{entry} ID:{id} INDN:NORTHWIND CLINIC LLC CO ID:1234567890 {sec}"
_CHASE = ("ORIG CO NAME:{payer} ORIG ID:1234567890 DESC DATE:010254 CO ENTRY DESCR:{entry}SEC:{sec} "
          "TRACE#:123456789012345 EED:540102 IND ID:1 IND NAME:NORTHWIND CLINIC LLC TRN: 1234567890TC")
_AMEX = ("ONLINE TRANSFER PAYMENT CREDIT {payer} {entry} 1234 XXXX5678 NORTHWIND CLINIC LLC EXTERNAL FABRIKAM BANK "
         "ID 123456789012345")


def _records(bank, texts, *, holder=HOLDER, amount=None, direction="credit"):
    """One statement of `texts`, each a credit of 4000.00 + 500 * i (or `amount`), or a debit with direction debit."""
    rows = []
    for index, text in enumerate(texts):
        value = 4000.0 + 500 * index if amount is None else amount
        rows.append(Transaction(date=f"2054-03-{index + 2:02d}", description=text,
                                amount=-value if direction == "debit" else value, direction=direction))
    return classify_statement_transactions(Statement(bank=bank, account_name=holder, transactions=rows))


def _reading(record):
    return record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method


#: The moves: (label, bank, texts, amount (None: 4000.00 + 500 * i), the form's key in matched_alias).
MOVES = (
    # Minnesota Management and Budget (U.S. Bank's ELECTRONIC DEPOSIT FROM, verified as repeats before the ruling).
    ("mn x2", "U.S. Bank", ["ELECTRONIC DEPOSIT FROM MN STATE-MMB"] * 2, None, "mn_mmb"),
    ("mn one-off", "U.S. Bank", ["ELECTRONIC DEPOSIT FROM MN STATE-MMB 1234"], None, "mn_mmb"),
    ("mn bofa", "Bank of America", [_BOFA.format(payer="MN STATE MMB", entry="PAYMENT", id="1", sec="CCD")], None,
     "mn_mmb"),
    ("mn amex", "American Express", [_AMEX.format(payer="MN STATE MMB", entry="PAYMENT")], None, "mn_mmb"),
    # The VA's Treasury payment, agency code 36.
    ("va bare", "Sample Bank", ["36 TREAS 310 MISC PAY 123456789012345"], None, "va_treasury"),
    ("va masked x2", "Huntington National Bank", ["36 TREAS 310 MISC PAY 123456 XXXXX1234567890"] * 2, None,
     "va_treasury"),
    ("va all-x mask", "Huntington National Bank", ["36 TREAS 310 MISC PAY 123456 XXXXXXXX"], None, "va_treasury"),
    ("va wells", "Wells Fargo", ["36 TREAS 310 MISC PAY 123456 XXXXX1234 123456\\GE*1*123456789\\IEA*1*123456789\\"],
     None, "va_treasury"),
    ("va chase x2", "Chase", [_CHASE.format(payer="36 TREAS 310", entry=" MISC PAY", sec="CTX")] * 2, None,
     "va_treasury"),
    ("va bofa", "Bank of America", [_BOFA.format(payer="36 TREAS 310", entry="MISC PAY", id="123456", sec="CCD")],
     None, "va_treasury"),
    ("va pnc", "PNC Bank", ["ACH CREDIT 36 TREAS 310 MISC PAY RECEIVER NAME NORTHWIND CLINIC LLC 123456"], None,
     "va_treasury"),
    ("va no entry", "Sample Bank", ["36 TREAS 310 123456789012345"], None, "va_treasury"),
    ("va amex", "American Express", [_AMEX.format(payer="36 TREAS 310", entry="MISC PAY")], None, "va_treasury"),
    # Under the $1 floor the step decides too (non_revenue, never the floor's hold), as step 3 does.
    ("va under $1", "Sample Bank", ["36 TREAS 310 MISC PAY 123456789012345"], 0.50, "va_treasury"),
    ("mn under $1", "U.S. Bank", ["ELECTRONIC DEPOSIT FROM MN STATE-MMB"], 0.99, "mn_mmb"),
    # Wisconsin DCF's direct deposit to a child-care provider (verified as repeats before the ruling).
    ("wi x2", "Bank of America", [_BOFA.format(payer="WI DCF", entry="WIDCF DD", id="E123456 01", sec="CCD")] * 2,
     None, "wi_dcf"),
    # British Columbia's provincial payment.
    ("bc", "Scotiabank", ["PROVINCIAL PAYMENT PROVINCE OF BC"], None, "bc_provincial"),
    ("bc long", "Scotiabank", ["PROVINCIAL PAYMENT PROVINCE OF BRITISH COLUMBIA 1234"], None, "bc_provincial"),
    # Ontario's Workplace Safety and Insurance Board (the full name was held as an insurer's before the ruling).
    ("wsib x2", "Royal Bank of Canada", ["WORK. COMP. BOARD WSIB_EME"] * 2, None, "ontario_wsib"),
    ("wsib mixed case", "Royal Bank of Canada", ["Work. Comp. Board WSIB"], None, "ontario_wsib"),
    ("wsib full name", "Sample Bank", ["WORKPLACE SAFETY AND INSURANCE BOARD 1234"], None, "ontario_wsib"),
    # Quebec's government (RBC's AUTOMATED CREDIT label is a template prefix since audit round 2, R2-B09).
    ("qc", "TD Canada Trust", ["GOUV. QUEBEC MSP"], None, "quebec_government"),
    ("qc long", "TD Canada Trust", ["GOUVERNEMENT DU QUEBEC MSP 1234"], None, "quebec_government"),
    ("qc rbc", "Royal Bank of Canada", ["AUTOMATED CREDIT GOUV QUEBEC MSP"], None, "quebec_government"),
    # North Dakota's Workforce Safety and Insurance (its full name was held as an insurer's before the ruling).
    ("nd", "Sample Credit Union", ["DESCRIPTIVE DEPOSIT WORKFORCE SAFETY"], None, "nd_workforce_safety"),
    ("nd bare", "Sample Bank", ["WORKFORCE SAFETY 1234"], None, "nd_workforce_safety"),
    ("nd insurance", "Sample Credit Union", ["DESCRIPTIVE DEPOSIT WORKFORCE SAFETY & INSURANCE 1234"], None,
     "nd_workforce_safety"),
    # Audit round 3, R3-B13 (R3-55): a digit run glued before a letter-led form's first letter is a reference (a
    # glued date), as the GST form's glued lead is (today each counted, the form missed).
    ("qc glued", "TD Canada Trust", ["0102GOUV QUEBEC MSP"], None, "quebec_government"),
    ("wsib board glued", "Royal Bank of Canada", ["0102WORK COMP BOARD WSIB EME"], None, "ontario_wsib"),
    ("wsib glued", "Royal Bank of Canada", ["0102WSIB EME"], None, "ontario_wsib"),
    ("mn glued", "U.S. Bank", ["ELECTRONIC DEPOSIT FROM 0102MN STATE MMB"], None, "mn_mmb"),
    ("wi glued", "Bank of America",
     ["0102WI DCF DES:WIDCF DD ID:E000000 01 INDN:NORTHWIND CLINIC LLC CO ID:1234567890 CCD"], None, "wi_dcf"),
    ("bc glued", "Scotiabank", ["0102PROVINCE OF BC"], None, "bc_provincial"),
    ("qc glued after a template", "TD Canada Trust", ["ACH CREDIT 0102GOUV QUEBEC MSP"], None, "quebec_government"),
    ("nd glued", "Sample Bank", ["0102NORTH DAKOTA WORKFORCE SAFETY"], None, "nd_workforce_safety"),
)


@pytest.mark.parametrize(("label", "bank", "texts", "amount", "alias"), MOVES, ids=[move[0] for move in MOVES])
def test_a_government_payment_that_prints_no_purpose_is_non_revenue(label, bank, texts, amount, alias):
    for record in _records(bank, texts, amount=amount):
        assert record.revenue_classification == "non_revenue", label
        assert (record.revenue_match_method, record.revenue_matched_rule, record.revenue_matched_alias) == (
            METHOD, RULE, alias), label
        # R2-OW03: the display reason the non-revenue breakdown reads (the tier, state, method and flags unchanged).
        assert (record.revenue_tier, record.revenue_tier_reason) == ("non_revenue", "government_no_purpose"), label
        assert (record.revenue_initial_classification, record.revenue_initial_tier) == ("non_revenue", "non_revenue")
        assert record.revenue_review_status == "not_required" and not record.revenue_review_required, label
        assert not record.contributes_to_true_revenue, label
        assert not record.contributes_to_lender_credit_exclusion and not record.contributes_to_lender_totals, label


#: The controls keep their reading: (label, bank, holder, texts, the (tier, reason, method) of every row).
CONTROLS = (
    # A purpose printed in Bank of America's PMT INFO addenda, after the receiver field.
    ("va addenda remittance", "Bank of America", HOLDER,
     [_BOFA.format(payer="36 TREAS 310", entry="MISC PAY", id="123456", sec="CCD PMT INFO:RMR*IV*INV12345")],
     (VERIFIED, None, "public_payer_remittance")),
    ("va addenda vendor payment", "Bank of America", HOLDER,
     [_BOFA.format(payer="36 TREAS 310", entry="MISC PAY", id="123456",
                   sec="CCD PMT INFO:VENDOR PAYMENT INVOICE 12345")],
     (COUNTED, "named_payer_one_off", UNIDENTIFIED)),
    ("mn addenda invoice", "Bank of America", HOLDER,
     [_BOFA.format(payer="MN STATE MMB", entry="PAYMENT", id="1", sec="CCD PMT INFO:INVOICE 12345 CONTRACT 9")],
     (COUNTED, "named_payer_one_off", UNIDENTIFIED)),
    ("wi addenda child care", "Bank of America", HOLDER,
     [_BOFA.format(payer="WI DCF", entry="WIDCF DD", id="E123456 01", sec="CCD PMT INFO:CHILD CARE INV 123")],
     (VERIFIED, None, "public_or_healthcare_payer")),
    # The VA's masked entry codes print a purpose (education, vocational rehabilitation, a benefit).
    ("va ch33", "Sample Bank", HOLDER, ["36 TREAS 310 XXVA CH33 123456789012345"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("va ch31", "Sample Bank", HOLDER, ["36 TREAS 310 XXVA CH31 123456789012345"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("va ch33 chase", "Chase", HOLDER, [_CHASE.format(payer="36 TREAS 310", entry="XXVA CH33", sec="PPD")],
     (COUNTED, "named_payer_one_off", UNIDENTIFIED)),
    ("va ch33 bofa", "Bank of America", HOLDER,
     [_BOFA.format(payer="36 TREAS 310", entry="XXVA CH33", id="123456", sec="PPD")],
     (COUNTED, "named_payer_one_off", UNIDENTIFIED)),
    ("va edu", "Sample Bank", HOLDER, ["36 TREAS 310 XXVA EDU 123456789012345"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("va benefit", "Sample Bank", HOLDER, ["36 TREAS 310 XXVA BENEF 123456789012345"],
     (HELD, "personal_income", UNIDENTIFIED)),
    ("va letter code benefit", "Sample Bank", HOLDER, ["VA TREAS 310 XXVA BENEF 123456789012345"],
     (HELD, "personal_income", UNIDENTIFIED)),
    ("vacp benefit", "Sample Bank", HOLDER, ["VACP TREAS 310 XXVA BENEF 123456789012345"],
     (HELD, "personal_income", UNIDENTIFIED)),
    # A purpose printed in the entry.
    ("mn vendor pay", "U.S. Bank", HOLDER, ["ELECTRONIC DEPOSIT FROM MN STATE-MMB VENDOR PAY"],
     (VERIFIED, None, "payer_remittance_descriptor")),
    ("mn bofa vendor pay", "Bank of America", HOLDER,
     [_BOFA.format(payer="MN STATE MMB", entry="VENDOR PAY", id="1", sec="CCD")],
     (VERIFIED, None, "payer_remittance_descriptor")),
    ("va remittance", "Citibank", HOLDER,
     ["ELECTRONIC CREDIT 36 TREAS 310 MISC PAY 123456789012345 APR 54 RMR IV SAMPLE 1234"],
     (VERIFIED, None, "payer_remittance_descriptor")),
    ("va bofa vendor pay", "Bank of America", HOLDER,
     [_BOFA.format(payer="36 TREAS 310", entry="VENDOR PAY", id="1", sec="CCD")],
     (VERIFIED, None, "payer_remittance_descriptor")),
    ("va letter code vendor pay", "Bank of America", HOLDER,
     [_BOFA.format(payer="VA TREAS 310", entry="VENDOR PAY", id="1", sec="CCD")],
     (VERIFIED, None, "payer_remittance_descriptor")),
    ("va amex vendor pay", "American Express", HOLDER, [_AMEX.format(payer="36 TREAS 310", entry="VENDOR PAY")],
     (VERIFIED, None, "payer_remittance_descriptor")),
    # Codes and names the ruling did not cover.
    ("va letter code", "Sample Bank", HOLDER, ["VA TREAS 310 MISC PAY 123456789012345"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("mn refund", "Sample Bank", HOLDER, ["MN STATE MMB REFUND"],
     ("non_revenue", None, "reversal_cancellation_exclusion")),
    ("another payer's state mmb", "Sample Bank", HOLDER, ["CONTOSO STATE MMB"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("chase treasury with no agency code", "Chase", HOLDER,
     [_CHASE.format(payer="TREAS 310", entry=" MISC PAY", sec="CCD")],
     (VERIFIED, None, "public_or_healthcare_payer")),
    ("agency 12", "Sample Bank", HOLDER, ["12 TREAS 310 MISC PAY 123456789012345"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("usda", "Sample Bank", HOLDER, ["USDA TREAS 310 MISC PAY 1234"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("vacp", "Sample Bank", HOLDER, ["VACP TREAS 310 123456789012345"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("treasury dod", "Sample Bank", HOLDER, ["TREAS 310 DOD MISC 123456789012345"],
     (VERIFIED, None, "public_payer_remittance")),
    # Health and child-care programs paying the business for its services.
    ("optum va", "Huntington National Bank", HOLDER,
     ["OPTUM VA CCN REG HCCLAIMPMT 123456789 TRN 1 1234567890 1234567890"],
     (VERIFIED, None, "operating_income_descriptor")),
    ("wisconsin shares card x2", "Bank of America", HOLDER,
     [_BOFA.format(payer="FIS EBT", entry="WIDCF EBT", id="E123456", sec="CCD")] * 2,
     (COUNTED, "named_payer_purpose_refused", UNIDENTIFIED)),
    ("wi provider pay", "Bank of America", HOLDER, [_BOFA.format(payer="WI DCF", entry="PROV PAY", id="1", sec="CCD")],
     (VERIFIED, None, "public_payer_remittance")),
    # Canadian forms.
    ("crown corporation", "Scotiabank", HOLDER, ["PROVINCIAL PAYMENT FABRIKAM LIQUOR CORPORATION"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("another province", "Scotiabank", HOLDER, ["PROVINCIAL PAYMENT PROVINCE OF ONTARIO"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("bc grant", "Scotiabank", HOLDER, ["PROVINCIAL PAYMENT PROVINCE OF BC GRANT"],
     (HELD, "non_sale_purpose", UNIDENTIFIED)),
    ("provincial benefit", "Royal Bank of Canada", HOLDER, ["PROV LOCAL GVT PAYMENT CANADA"],
     (HELD, "personal_income", UNIDENTIFIED)),
    ("wsib rebate", "Royal Bank of Canada", HOLDER, ["WORK. COMP. BOARD WSIB REBATE 1234"],
     (HELD, "non_sale_purpose", UNIDENTIFIED)),
    ("wsib company", "Sample Bank", HOLDER,
     [_BOFA.format(payer="WSIB CONSULTING INC", entry="PAYMENT", id="1", sec="CCD")],
     (VERIFIED, None, "named_payer_company_form")),
    ("wsib e-transfer", "TD Canada Trust", HOLDER, ["E-TRANSFER 123456789012 WSIB"], (COUNTED, "p2p", UNIDENTIFIED)),
    ("another board", "Royal Bank of Canada", HOLDER, ["WORK. COMP. BOARD WCB ALBERTA 1234"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("board with no wsib", "Royal Bank of Canada", HOLDER, ["WORK. COMP. BOARD 1234"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("quebec revenue", "TD Canada Trust", HOLDER, ["GOUV. QUEBEC RQ 1234"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("quebec lottery", "TD Canada Trust", HOLDER, ["LOTO QUEBEC DIV"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("quebec gst refund", "TD Canada Trust", HOLDER, ["RQ GST"], ("non_revenue", None, "strong_non_revenue_rule")),
    # North Dakota.
    ("workforce safety company", "Sample Bank", "CONTOSO CLINIC LLC",
     ["NORTHWIND WORKFORCE SAFETY LLC DES:PAYMENT ID:1 INDN:CONTOSO CLINIC LLC CO ID:1 CCD"],
     (VERIFIED, None, "named_payer_company_form")),
    ("workforce safety claim", "Sample Credit Union", HOLDER,
     ["DESCRIPTIVE DEPOSIT WORKFORCE SAFETY AND INSURANCE CLAIM 1234"],
     ("non_revenue", None, "strong_non_revenue_rule")),
    # A government or a program paying the business for its services, with the purpose printed.
    ("dhs provider pay", "Bank of America", HOLDER, ["SAMPLE STATE DHS DES:PROV PAY ID:1"],
     (VERIFIED, None, "public_payer_remittance")),
    ("mn dhs provider pay", "U.S. Bank", HOLDER, ["ELECTRONIC DEPOSIT FROM DHS CAF PROV PAY"],
     (VERIFIED, None, "public_payer_remittance")),
    ("medicaid claim", "Bank of America", HOLDER,
     [_BOFA.format(payer="SAMPLE STATE MEDICAID", entry="HCCLAIMPMT", id="1", sec="CCD")],
     (VERIFIED, None, "operating_income_descriptor")),
    ("dental care plan x2", "Royal Bank of Canada", HOLDER, ["MISC PAYMENT GC CDCP ASO FABRIKAM LIFE"] * 2,
     (VERIFIED, None, "named_payer_repeats")),
    ("county vendor pay", "Bank of America", HOLDER,
     [_BOFA.format(payer="COUNTY OF CONTOSO", entry="VENDOR PAY", id="1", sec="CCD")],
     (VERIFIED, None, "payer_remittance_descriptor")),
    # Audit round 3, R3-B13 (R3-55): the VA's Treasury form is not read glued (a glued agency code is unreadable);
    # letters glued before a form are another word; the GST form's glued lead is read as before.
    ("va glued", "Sample Bank", HOLDER, ["010236 TREAS 310 MISC PAY"],
     (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("letters glued", "Sample Bank", HOLDER, ["ABCMN STATE MMB"], (COUNTED, "named_payer_unlabelled", UNIDENTIFIED)),
    ("gst glued", "TD Canada Trust", HOLDER, ["0102GST CANADA"], ("non_revenue", None, "strong_non_revenue_rule")),
)


@pytest.mark.parametrize(("label", "bank", "holder", "texts", "expected"), CONTROLS,
                         ids=[control[0] for control in CONTROLS])
def test_a_payment_that_prints_a_purpose_or_a_form_the_ruling_did_not_name_keeps_its_reading(
        label, bank, holder, texts, expected):
    for record in _records(bank, texts, holder=holder):
        assert _reading(record) == expected, label
        assert record.revenue_match_method != METHOD, label


def test_a_lender_printing_a_board_s_name_stays_financing():
    """The residue test keeps any other payer name off the row, so step 3a never pre-empts D1."""
    record = _records("Sample Bank", ["WSIB FORWARD FINANCING 1234"])[0]
    assert _reading(record) == ("non_revenue", None, "financing_proceeds_credit")
    assert record.contributes_to_lender_credit_exclusion


@pytest.mark.parametrize("text", ["PAD WSIB", "WORK COMP BOARD WSIB PREMIUM"])
def test_a_debit_naming_a_form_carries_no_revenue_fields(text):
    record = _records("Royal Bank of Canada", [text], direction="debit")[0]
    assert _reading(record) == (None, None, None)


def test_a_form_printed_in_the_debit_direction_stays_a_direction_conflict():
    record = classify_statement_transactions(Statement(bank="U.S. Bank", account_name=HOLDER, transactions=[
        Transaction(date="2054-03-02", description="ELECTRONIC DEPOSIT FROM MN STATE-MMB", amount=4000.0,
                    direction="debit")]))[0]
    assert _reading(record) == (HELD, "direction_conflict", "direction_conflict")


def _read(text: str) -> str | None:
    return government_no_purpose(revenue_text(normalize_transaction_description(text)))


@pytest.mark.parametrize(("text", "alias"), [(texts[0], alias) for _label, _bank, texts, _amount, alias in MOVES])
def test_the_reader_names_the_form_of_each_move(text, alias):
    assert _read(text) == alias


@pytest.mark.parametrize("text", [
    text for _label, _bank, _holder, texts, _expected in CONTROLS for text in texts
] + ["WSIB FORWARD FINANCING 1234"])
def test_the_reader_names_no_form_on_a_control(text):
    assert _read(text) is None


@pytest.mark.parametrize(("text", "alias"), [
    ("0102WSIB EME", "ontario_wsib"), ("0102PROVINCE OF BC", "bc_provincial"),
    ("0102GOUV QUEBEC MSP", "quebec_government"), ("0102MN STATE MMB", "mn_mmb"), ("0102WI DCF", "wi_dcf"), ("0102WORKFORCE SAFETY", "nd_workforce_safety"),
    # The optional leads take the glued digits too.
    ("0102PROVINCIAL PAYMENT PROVINCE OF BC", "bc_provincial"), ("0102ND WORKFORCE SAFETY", "nd_workforce_safety"),
    # Not read: the VA's form glued, letters glued before a form.
    ("010236 TREAS 310 MISC PAY", None), ("ABCMN STATE MMB", None), ("XWSIB EME", None),
])
def test_r3_55_the_reader_reads_a_form_after_a_glued_digit_run(text, alias):
    """Audit round 3, R3-B13 (R3-55; the underwriter's Q12 of 2026-10-02, "Let's just change to Exclude"): the six
    letter-led forms take the left boundary (?<![A-Z]); the VA's 36 TREAS keeps (?<![A-Z0-9])."""
    assert _read(text) == alias


def test_r3_55_the_left_boundaries():
    boundaries = {name: form.pattern.split(")", 1)[0] + ")" for name, form in GOVERNMENT_NO_PURPOSE_FORMS}
    assert boundaries.pop("va_treasury") == "(?<![A-Z0-9])"
    assert set(boundaries.values()) == {"(?<![A-Z])"}


def test_the_seven_forms_are_the_owner_s():
    assert [name for name, _form in GOVERNMENT_NO_PURPOSE_FORMS] == [
        "mn_mmb", "va_treasury", "wi_dcf", "bc_provincial", "ontario_wsib", "quebec_government", "nd_workforce_safety"]


# Owner ruling 2026-10-02, R2-OW03 (the brief's Q12 open point 2, its default): the excluded government payments are
# shown in the non-revenue breakdown under their own display reason, `government_no_purpose` ("Government payment, no
# purpose printed"); a sub-$1 form row too. No figure moves, and no review path opens.
_BREAKDOWN_ROWS = (
    ("ELECTRONIC DEPOSIT FROM MN STATE-MMB", 4000.0),
    ("ELECTRONIC DEPOSIT FROM MN STATE-MMB 1234", 4500.0),
    ("36 TREAS 310 MISC PAY 123456789012345", 0.5),
    ("MN STATE MMB REFUND", 200.0),
    ("MOBILE DEPOSIT", 300.0),
)


def _breakdown_statement():
    return Statement(bank="U.S. Bank", account_name=HOLDER, currency="USD", transactions=[
        Transaction(date=f"2054-03-{index + 2:02d}", description=text, amount=amount, direction="credit")
        for index, (text, amount) in enumerate(_BREAKDOWN_ROWS)])


def test_the_display_reason_is_in_the_non_revenue_breakdown():
    from dataclasses import asdict

    from analysis.metrics import compute_metrics
    from analysis.revenue import REVENUE_TIER_REASONS, rebuild_serialized_revenue_views

    assert REVENUE_TIER_REASONS["government_no_purpose"] == ("non_revenue", "Government payment, no purpose printed")
    statement = _breakdown_statement()
    records = classify_statement_transactions(statement)
    assert [(record.revenue_tier, record.revenue_tier_reason, record.revenue_match_method) for record in records] == [
        ("non_revenue", "government_no_purpose", METHOD), ("non_revenue", "government_no_purpose", METHOD),
        ("non_revenue", "government_no_purpose", METHOD),
        # A row another non-revenue rule decided keeps no reason, and is not in the breakdown.
        ("non_revenue", None, "reversal_cancellation_exclusion"), (COUNTED, "check_deposit", AMBIGUOUS),
    ]
    expected = {"government_no_purpose": {"count": 3, "total": 8500.5}}
    metrics = compute_metrics(statement, classifications=records)
    assert metrics.non_revenue_by_reason == expected
    assert (metrics.non_revenue_total, metrics.non_revenue_count) == (8700.5, 4)
    assert metrics.true_revenue_total == 300.0 and metrics.revenue_tiers_sum_to_posted is True
    payload = rebuild_serialized_revenue_views({
        "statement": {"currency": "USD", "transactions": [
            {**transaction.model_dump(), "classification": asdict(record)}
            for transaction, record in zip(statement.transactions, records)]},
        "metrics": {}, "detection": {},
    })
    assert payload["metrics"]["non_revenue_by_reason"] == expected


@pytest.mark.parametrize("decision", ["confirm", "reject", "reset"])
def test_a_government_payment_that_prints_no_purpose_has_no_review_path(decision):
    from dataclasses import asdict

    from analysis.revenue import record_serialized_revenue_review

    statement = _breakdown_statement()
    records = classify_statement_transactions(statement)
    payload = {"statement": {"transactions": [
        {**transaction.model_dump(), "classification": asdict(record)}
        for transaction, record in zip(statement.transactions, records)]}}
    with pytest.raises(ValueError, match="only automatically unverified deposits can be reviewed"):
        record_serialized_revenue_review(payload, source_location=records[0].source_location, decision=decision)

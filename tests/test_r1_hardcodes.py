"""R-1 remediation fixture tests.

Each inventory item gets positive AND negative coverage proving the
generalized rule fires on structural evidence, not on the memorized
instance it replaced. All fixtures are synthetic.
"""
from __future__ import annotations

import pytest

from analysis.bank_repairs import repair_chase_remote_deposit_count_column
from analysis.community_section import (
    _clean as community_clean,
    parse_dakota_west_statement,
    parse_mission_valley_statement,
)
from analysis.rbc import _fr_month, _is_debit, parse_rbc_statement
from analysis.scanned_small_bank import (
    _extract_holder_name,
    _repair_checks_from_image_captions,
    parse_apex_scanned_statement,
    parse_southside_scanned_statement,
)
from analysis.schema import Statement, Transaction
from analysis.td_can import (
    _native_credit_like,
    normalize_mojibake,
    parse_td_canada_statement,
)
from analysis.transaction_classifier import classify_transaction
from analysis.wells import _infer_year, parse_wells_statement
from analysis.wilson_muir import parse_wilson_muir_statement


def _txn(date, amount, desc, bal=None):
    return Transaction(
        date=date, description=desc, amount=amount,
        direction="credit" if amount > 0 else "debit", running_balance=bal,
    )


# ---------------------------------------------------------------------------
# Item 1 - check-image caption repair (generic, evidence-gated)
# ---------------------------------------------------------------------------

class TestCheckCaptionRepair:
    def _stmt(self):
        return Statement(
            beginning_balance=1000.0, ending_balance=700.0,
            stated_credit_count=1, stated_debit_count=1,
            stated_total_credits=400.0, stated_total_debits=700.0,
        )

    def test_caption_correction_restores_identity(self):
        # Parsed check reads -3700; the statement's own check image says $700.
        txns = [
            _txn("2026-03-02", 400.0, "Regular Deposit"),
            _txn("2026-03-10", -3700.0, "Check 2101"),
        ]
        markdown = "Number: 2101 Date: 3/10/2026 Amount: $700.00"
        repaired = _repair_checks_from_image_captions(markdown, txns, self._stmt())
        assert [t.amount for t in repaired] == [400.0, -700.0]

    def test_no_repair_when_identity_already_holds(self):
        txns = [
            _txn("2026-03-02", 400.0, "Regular Deposit"),
            _txn("2026-03-10", -700.0, "Check 2101"),
        ]
        # A (bogus) caption disagreeing with a reconciled ledger is ignored.
        markdown = "Number: 2101 Date: 3/10/2026 Amount: $9999.00"
        repaired = _repair_checks_from_image_captions(markdown, txns, self._stmt())
        assert [t.amount for t in repaired] == [400.0, -700.0]

    def test_no_repair_when_caption_does_not_restore_identity(self):
        txns = [
            _txn("2026-03-02", 400.0, "Regular Deposit"),
            _txn("2026-03-10", -3700.0, "Check 2101"),
        ]
        markdown = "Number: 2101 Date: 3/10/2026 Amount: $123.45"
        repaired = _repair_checks_from_image_captions(markdown, txns, self._stmt())
        assert [t.amount for t in repaired] == [400.0, -3700.0]

    def test_caption_date_and_number_must_both_match(self):
        txns = [
            _txn("2026-03-02", 400.0, "Regular Deposit"),
            _txn("2026-03-10", -3700.0, "Check 2101"),
        ]
        markdown = "Number: 2101 Date: 3/11/2026 Amount: $700.00"  # wrong day
        repaired = _repair_checks_from_image_captions(markdown, txns, self._stmt())
        assert [t.amount for t in repaired] == [400.0, -3700.0]


# ---------------------------------------------------------------------------
# Items 2 + 3 - structural gates, generic holder extraction, printed counts
# ---------------------------------------------------------------------------

APEX_TEMPLATE = """
{holder}
88 Some Road
Anytown, TN 11111
Account Number: ****9911
Balance Forward From 05/01/2026 1,000.00
{credit_count} Deposits/Credits 300.00 + Minimum Balance 830.00
{debit_count} Withdrawals/Debits 170.00 - Average Balance 1,100.00
Ending Balance As Of 05/31/2026 1,130.00
Interest Paid This Period 0.00
Days In Earnings Period 31
124 Summit Business Checking
DATE AMOUNT DESCRIPTION DATE AMOUNT DESCRIPTION
05/15/2026 100.00 Regular Deposit 05/26/2026 100.00 Regular Deposit
OTHER CREDITS
DATE AMOUNT DESCRIPTION
05/04/2026 100.00 Wire Transfer In
CHECK NO DATE AMOUNT CHECK NO DATE AMOUNT
2847 05/01/2026 10.00
* - denotes missing check number in sequence
OTHER DEBITS
DATE AMOUNT DESCRIPTION
{other_debits}
SERVICE CHARGES
DATE AMOUNT DESCRIPTION
05/29/2026 10.00 Net Service Charge
SFRVICE CHARGE ANALYSIS
FEESCHARGED
DATE AMOUNT DESCRIPTION
05/13/2026 10.00 NSF Charge
TOTAL FEES FOR THIS PERIOD
DAILY BALANCE INFORMATION
"""


def _apex_md(holder="ACME LOGISTICS LLC", debit_rows=14):
    other_debits = "\n".join(
        f"05/{day:02d}/2026 10.00 Ach withdrawal\nVendor {day}"
        for day in range(1, debit_rows + 1)
    )
    return APEX_TEMPLATE.format(
        holder=holder,
        credit_count=3,
        debit_count=debit_rows + 3,
        other_debits=other_debits,
    )


class TestApexStructuralGates:
    def test_parses_any_holder_without_customer_name_gate(self):
        stmt = parse_apex_scanned_statement(_apex_md(holder="ACME LOGISTICS LLC"))
        assert stmt is not None
        assert stmt.bank == "Apex Bank"
        assert stmt.account_name == "ACME LOGISTICS LLC"
        assert len(stmt.transactions) == 20

    def test_small_statement_passes_when_detail_matches_printed_counts(self):
        # 3 credits + 13 debits = 16 rows: below the old magic `< 20` gate.
        stmt = parse_apex_scanned_statement(_apex_md(debit_rows=10))
        assert stmt is not None
        assert len(stmt.transactions) == 16

    def test_incomplete_detail_fails_closed_against_printed_counts(self):
        md = _apex_md(debit_rows=14).replace(
            "05/04/2026 100.00 Wire Transfer In", ""
        )  # one stated credit row missing from the detail
        assert parse_apex_scanned_statement(md) is None

    def test_gate_is_structural_not_customer_name(self):
        md = _apex_md().replace("Balance Forward From", "Balance Fwd")
        assert parse_apex_scanned_statement(md) is None


class TestHolderExtraction:
    def test_entity_suffix_on_first_page(self):
        assert _extract_holder_name(
            "8 THE MARBLE WOMEN, LLC PAGE | tof 5\nBUILDER ACCOUNT"
        ) == "THE MARBLE WOMEN, LLC"
        assert _extract_holder_name(
            "Zenith Enterprises\n101 Somewhere Ln"
        ) == "Zenith Enterprises"

    def test_no_suffix_no_holder(self):
        assert _extract_holder_name("JOHN DOE\n101 Somewhere Ln") is None

    def test_only_first_page_is_scanned(self):
        assert _extract_holder_name(
            "no name here\n--- Page 2 ---\nLATE MENTION LLC"
        ) is None


# ---------------------------------------------------------------------------
# Items 4 + 5 - structural page-header scrub + account-section discovery
# ---------------------------------------------------------------------------

DAKOTA_TEMPLATE = """
Statement Ending 11/30/2025
{holder} Page 1 of 3
Member Number: 999999
Website dakotawestcu.com
Thank you for being a member of Dakota West Credit Union.
Summary of Accounts
Account Type Account Number Ending Balance Badlands Savings {savings} $50.41 Small Business Checking {checking} $4,026.32
--- Page 2 ---
{holder} 999999 Statement Ending 11/30/2025 Page 2 of 3
Small Business Checking - {checking}
Account Summary Date Description Amount
11/01/2025 Beginning Balance $100.00
1 Credit(s) This Period $50.00
1 Debit(s) This Period $30.00
11/30/2025 Ending Balance $120.00
Deposits
Date Description Amount
11/05/2025 Branch Deposit $50.00
Electronic Debits
Date Description Amount
11/06/2025 ACH Payment Vendor $30.00
Daily Balances
Date Amount
11/05/2025 $150.00
11/06/2025 $120.00
"""


def _dakota_md(holder="RIVER HAULING LLC", checking="61234570", savings="61234562"):
    return DAKOTA_TEMPLATE.format(holder=holder, checking=checking, savings=savings)


class TestCommunityPlatform:
    def test_page_header_scrub_is_structural(self):
        cleaned = community_clean(
            "SOME OTHER COMPANY 123 Statement Ending 01/31/2026 Page 2 of 9\n"
            "01/05/2026 Vendor payment $10.00"
        )
        assert "SOME OTHER COMPANY" not in cleaned
        assert "Vendor payment" in cleaned

    def test_dakota_west_discovers_account_from_headings(self):
        stmt = parse_dakota_west_statement(_dakota_md())
        assert stmt is not None
        assert stmt.account_number == "61234570"   # not the old literal
        assert stmt.account_name == "Small Business Checking"
        assert len(stmt.transactions) == 2
        assert stmt.beginning_balance == 100.0
        assert stmt.ending_balance == 120.0

    def test_dakota_west_requires_bank_marker(self):
        md = _dakota_md().replace("dakotawestcu.com", "someothercu.com")
        assert parse_dakota_west_statement(md) is None

    def test_dakota_west_no_headings_fails_closed(self):
        md = _dakota_md().replace("Small Business Checking - 61234570", "")
        assert parse_dakota_west_statement(md) is None

    def test_mission_valley_parses_any_customer(self):
        md = (
            "Mission Valley Bank\n"
            "Online Banking www.missionvalleybank.com\n"
            "BLUE HARBOR LLC Page 1 of 2\n"
            "Business Checking - XXXXXXXX7777\n"
            "Account Summary Date Description Amount\n"
            "01/01/2026 Beginning Balance $200.00\n"
            "1 Credit(s) This Period $25.00\n"
            "1 Debit(s) This Period $20.00\n"
            "01/30/2026 Ending Balance $205.00\n"
            "Deposits\n"
            "Date Description Amount\n"
            "01/10/2026 Branch Deposit $25.00\n"
            "Electronic Debits\n"
            "Date Description Amount\n"
            "01/12/2026 ACH Payment Vendor $20.00\n"
        )
        stmt = parse_mission_valley_statement(md)
        assert stmt is not None
        assert stmt.account_number == "XXXXXXXX7777"
        assert len(stmt.transactions) == 2


# ---------------------------------------------------------------------------
# Item 6 - Chase remote-deposit repair (fused count digit, any magnitude)
# ---------------------------------------------------------------------------

class TestChaseRemoteDepositRepair:
    def _stmt(self, amount, ending):
        return Statement(
            bank="Chase", beginning_balance=100.0, ending_balance=ending,
            transactions=[
                _txn("2026-01-04", amount, "Remote Online Deposit 1"),
                _txn("2026-01-05", -40.0, "Online Payment"),
            ],
        )

    def test_fused_count_digit_removed(self):
        stmt = self._stmt(1040.98, ending=100.98)   # true amount 40.98
        repaired = repair_chase_remote_deposit_count_column(stmt)
        assert repaired.transactions[0].amount == 40.98

    def test_fused_two_count_prefix_removed(self):
        stmt = self._stmt(2150.25, ending=210.25)   # true amount 150.25
        repaired = repair_chase_remote_deposit_count_column(stmt)
        assert repaired.transactions[0].amount == 150.25

    def test_no_repair_when_digits_are_not_a_fused_prefix(self):
        stmt = self._stmt(1340.98, ending=741.87)   # delta not prefix-shaped
        repaired = repair_chase_remote_deposit_count_column(stmt)
        assert repaired.transactions[0].amount == 1340.98

    def test_no_repair_when_identity_already_holds(self):
        stmt = self._stmt(1040.98, ending=1100.98)
        repaired = repair_chase_remote_deposit_count_column(stmt)
        assert repaired.transactions[0].amount == 1040.98

    def test_other_banks_untouched(self):
        stmt = self._stmt(1040.98, ending=100.98)
        stmt.bank = "Wells Fargo"
        repaired = repair_chase_remote_deposit_count_column(stmt)
        assert repaired.transactions[0].amount == 1040.98


# ---------------------------------------------------------------------------
# Item 7 - RBC: no counterparty sign knowledge; French parser generalized
# ---------------------------------------------------------------------------

#: The French PERSONAL product, which is the layout the pinned corpus document
#: `RBC French/12 - Relevé Royale Décembre 2025` prints. Its business sibling
#: heads the same grid `Chèques et débits` and prints instance counts beside
#: its totals; that one is covered in `tests/test_rbc_variants.py` (W3 §RBCCIBC
#: card C), which is the layout `rbc_french` used to miss entirely.
RBC_FR_TEMPLATE = """
Relevé de votre compte forfait bancaire personnel RBC
Banque Royale du Canada
Du 3 {start_month} {start_year} au 2 {end_month} {end_year}
Sommaire de votre compte pour cette période
Votre solde d'ouverture le 3 {start_month} {start_year} 1 000,00 $
Total des dépôts dans votre compte + 500,00
Total des retraits de votre compte - 300,00
Votre solde de clôture le 2 {end_month} {end_year} = 1 200,00 $
Détails de l'activité du compte
Date Description Retraits ($) Dépôts ($) Solde ($)
Solde d'ouverture 1 000,00
5 {start_abbr} Dépôt reçu client 500,00 1 500,00
12 {start_abbr} Paiement fournisseur 300,00 1 200,00
Solde de clôture de votre compte 1 200,00
"""


class TestRbcFrenchGeneralized:
    def test_non_december_period_parses(self):
        md = RBC_FR_TEMPLATE.format(
            start_month="mars", start_year=2026, start_abbr="mars",
            end_month="avril", end_year=2026,
        )
        stmt = parse_rbc_statement(md)
        assert stmt is not None
        assert stmt.period_start == "2026-03-03"
        assert stmt.period_end == "2026-04-02"
        dates = [t.date for t in stmt.transactions]
        assert dates == ["2026-03-05", "2026-03-12"]
        assert [t.amount for t in stmt.transactions] == [500.0, -300.0]

    def test_cross_year_period_resolves_years_from_period(self):
        md = RBC_FR_TEMPLATE.format(
            start_month="décembre", start_year=2025, start_abbr="déc",
            end_month="janvier", end_year=2026,
        )
        stmt = parse_rbc_statement(md)
        assert stmt is not None
        assert stmt.period_start == "2025-12-03"
        assert stmt.period_end == "2026-01-02"
        assert [t.date for t in stmt.transactions] == ["2025-12-05", "2025-12-12"]

    def test_missing_period_line_fails_closed(self):
        md = RBC_FR_TEMPLATE.format(
            start_month="mars", start_year=2026, start_abbr="mars",
            end_month="avril", end_year=2026,
        ).replace("Du 3 mars 2026 au 2 avril 2026", "")
        assert parse_rbc_statement(md) is None

    def test_french_month_prefix_resolution(self):
        assert _fr_month("déc") == 12
        assert _fr_month("janv") == 1
        assert _fr_month("juil") == 7
        assert _fr_month("jui") is None      # ambiguous: juin / juillet
        assert _fr_month("xyz") is None

    def test_counterparty_names_are_not_debit_evidence(self):
        # Removed literals are gone; unmatched rows still default to debit.
        assert not _is_debit("FUNDIFI CANADA PAD")
        assert not _is_debit("2313833 ONTARIO INC")
        assert _is_debit("MONTHLY FEE")


# ---------------------------------------------------------------------------
# Item 8 - TD sign from transaction codes, not merchant names
# ---------------------------------------------------------------------------

class TestTdSignCodes:
    @pytest.mark.parametrize("desc", [
        "Lightspeed MSP", "UNKNOWN SHOP MSP", "GOUV. QUEBEC MSP",
        "Canacap CLN", "PRODIGY SYSTEMS PAY", "RQ GST",
        "IQ111 TFR-FR 6017297", "E-TRANSFER ***6Rp",
    ])
    def test_credit_codes(self, desc):
        assert _native_credit_like(desc)

    @pytest.mark.parametrize("desc", [
        "Canacap BUS", "CMCA Finance BUS", "PAY 1274501 BUS",
        "HQ014 TFR-TO 6017297", "SEND E-TFR ***mQx",
        "DANNY'S CONVENI", "CITY SOUTH PIZZ", "PHO ANH", "FRESHCO #3811",
        "CASH 4 YOU # 03", "MONTHLY PLAN FEE", "CREDIT CARD PAYMENT",
    ])
    def test_debit_or_uncoded(self, desc):
        assert not _native_credit_like(desc)

    def test_table_credit_column_is_trusted_over_merchant_name(self):
        md = """
Accounts issued by: THE TORONTO-DOMINION BANK
<table>
<tr><td>Branch No.</td><td>Account No.</td><td>BUSINESS CHEQUING ACCOUNT - CAD EVERY DAY A</td><td>SEP 29/25 - OCT 31/25</td></tr>
<tr><td>DESCRIPTION</td><td>CHEQUE/DEBIT</td><td>DEPOSIT/CREDIT</td><td>DATE</td><td>BALANCE</td></tr>
<tr><td>BALANCE FORWARD</td><td></td><td></td><td>SEP29</td><td>100.00</td></tr>
<tr><td>FRESHCO REFUND</td><td></td><td>25.00</td><td>OCT10</td><td>125.00</td></tr>
<tr><td>0 CHQS ENCLOSED NEXT STATEMENT DATE IS</td><td>NOV 28/25</td><td></td><td>No.</td><td>Amount</td></tr>
<tr><td>MONTHLY AVER. CR. BAL.</td><td>$100.00</td><td>Credits</td><td>1 25.00</td></tr>
<tr><td>DEP CONTENT- CASH 0</td><td>ITEMS 0</td><td>UNC BATCH 0</td><td>Debits</td><td>0 0.00</td></tr>
</table>
"""
        stmt = parse_td_canada_statement(md)
        assert stmt is not None
        row = next(t for t in stmt.transactions if "FRESHCO" in t.description)
        assert row.amount == 25.0     # printed credit column wins


# ---------------------------------------------------------------------------
# Items 9 + 10 - Wells year evidence; Wilson & Muir derived days
# ---------------------------------------------------------------------------

WELLS_TEMPLATE = """
WELLS FARGO COMBINED STATEMENT {maybe_year}
Account number: 1234567
WF_NATIVE_TRANSACTIONS
Statement period activity summary
Beginning balance on 2/1 100.00
Deposits/Credits 50.00
Withdrawals/Debits - 30.00
Ending balance on 2/28 120.00
WF_TX|2/3|Purchase Vendor||30.00|70.00
WF_TX|2/10|Deposit|50.00||120.00
"""


class TestWellsYearEvidence:
    def test_year_from_document(self):
        stmt = parse_wells_statement(WELLS_TEMPLATE.format(maybe_year="2024"))
        assert stmt is not None
        assert stmt.period_start == "2024-02-01"
        assert all(t.date.startswith("2024-") for t in stmt.transactions)

    def test_no_year_fails_closed(self):
        assert _infer_year("no year anywhere") is None
        assert parse_wells_statement(WELLS_TEMPLATE.format(maybe_year="")) is None


WILSON_TEMPLATE = """
WILSON & MUIR BK & TRUST
Statement Date: {end}/2025 Account No.: #299 Page: 1
SMALL BUSINESS PACKAGE SUMMARY Type : **REG Status : Active
Category Number Amount Balance Forward From {start}/25 100.00
Deposits 1 50.00+ Debits 1 30.00 Automatic Withdrawals 1 20.00
Automatic Deposits 1 10.00+ Card Activity 0 0.00
Ending Balance On {end}/25 110.00 Foreign Items Deposited 0 Items Deposited 1
Average Balance (Ledger) 105.00+
ALL CREDIT ACTIVITY
Date Type Amount 05/08/25 Deposit 50.00
Date Description Amount 05/29/25 MERCH BNKCD NSD DEPOSIT 10.00
ELECTRONIC DEBITS
Date Description Amount 05/01/25 ONDECK CAPITAL 5 33952 20.00
CHECKS AND OTHER DEBITS * indicates a gap in the check numbers
Date Check # Amount 05/02/25 1367 30.00
DAILY BALANCE SUMMARY
"""


class TestWilsonMuirDerivedDays:
    def test_thirty_day_period(self):
        stmt = parse_wilson_muir_statement(
            WILSON_TEMPLATE.format(start="04/30", end="05/30")
        )
        assert stmt is not None
        assert stmt.days_in_period == 30

    def test_days_follow_the_printed_period_not_a_constant(self):
        stmt = parse_wilson_muir_statement(
            WILSON_TEMPLATE.format(start="04/30", end="05/27")
        )
        assert stmt is not None
        assert stmt.days_in_period == 27


# ---------------------------------------------------------------------------
# Item 11 - mojibake normalization
# ---------------------------------------------------------------------------

class TestMojibakeNormalization:
    def test_double_encoded_text_repaired(self):
        assert normalize_mojibake("REÃ‡U") == "REÇU"
        assert normalize_mojibake("numÃ©ro") == "numéro"
        assert normalize_mojibake("â€” dash") == "— dash"

    def test_clean_text_passes_through(self):
        assert normalize_mojibake("Relevé décembre") == "Relevé décembre"

    def test_nbsp_becomes_space(self):
        assert normalize_mojibake("1 234,56") == "1 234,56"

    def test_mixed_content_uses_targeted_fallback(self):
        assert normalize_mojibake("café numÃ©ro") == "café numéro"

    def test_french_parser_accepts_mojibake_input(self):
        md = RBC_FR_TEMPLATE.format(
            start_month="mars", start_year=2026, start_abbr="mars",
            end_month="avril", end_year=2026,
        ).encode("utf-8").decode("cp1252")   # simulate double-encoding
        stmt = parse_rbc_statement(md)
        assert stmt is not None
        assert stmt.period_start == "2026-03-03"


# ---------------------------------------------------------------------------
# Item 12a - pre-approved registry entries (Ocean ruling, H-2 evidence)
# ---------------------------------------------------------------------------

class TestPreApprovedRegistryEntries:
    def test_afc_funding_confirmed_lender(self):
        record = classify_transaction("AFC FUNDING CORP XPRESS PAY", -4229.99)
        assert record.classification == "confirmed_lender"
        assert record.canonical_entity == "AFC FUNDING CORP"
        assert record.contributes_to_withholding_rate

    def test_intuit_financing_confirmed_lender(self):
        record = classify_transaction("INTUIT FINANCING QBC_PMTS", -632.24)
        assert record.classification == "confirmed_lender"
        assert record.canonical_entity == "INTUIT FINANCING"

    def test_intuit_software_purchase_is_not_a_lender(self):
        # H-2 negative evidence: the $37.10 QuickBooks software charge.
        record = classify_transaction("VSA PUR INTUIT QBOOKS ONLINE CL.INT", -37.10)
        assert record.classification not in ("confirmed_lender", "potential_lender")
        assert record.canonical_entity != "INTUIT FINANCING"

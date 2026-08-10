"""The three BMO layout families, positive and negative (W3 §BMO-LAYOUTS).

The cell: the BMO documents in the discovery archive that no registration
claimed — 179 records / 164 distinct documents in run `52b4b2b2`. They are not
one layout. Three structural families account for 160 of them, and the families
are recorded in `docs/moneythumb-replacement/W3_TRACKA_LOG.md` (§BMO-LAYOUTS):

* **A** — BMO Canada `Business Banking statement`: a `Summary of account` row
  and a four-column ledger (`Amounts debited` / `Amounts credited` / `Balance`),
  133 documents;
* **C** — the same printed statement in French, 4 documents;
* **B** — BMO Bank N.A. (US) `Monthly Activity Details`, 23 documents.

Every document below is synthetic. No archive bytes, no customer, and no amount
or date copied from a real statement: what is reproduced is the *shape* BMO
prints, including the two shapes that defeat a naive reading — a description
that contains a money-shaped token, and an account number written as groups of
digits separated by spaces.

Each `test_f<N>` names the printed structure it constrains. The negatives are
not demonstrations of a defect: each one constrains a rule this cell added, and
in particular pins that the three BMO registrations stay disjoint from each
other and from `analysis/bmo.py`'s pre-existing layout.
"""
from __future__ import annotations

import pytest

from analysis import bmo, bmo_ca_business, bmo_us_activity
from analysis import parser_registry_entries  # noqa: F401  — populates the registry
from analysis.parser_registry import resolve
from analysis.reconcile import reconcile

# ---------------------------------------------------------------------------
# Family A — BMO Canada "Business Banking statement", English
# ---------------------------------------------------------------------------

CA_TEMPLATE = """\
1 SAMPLE STREET SOMEWHERE, ON A1A1A1 Business Banking
Your branch address:
Your Branch SAMPLE BRANCH Transit number: 1234
NORTHWIND SUPPLY LTD. 1 SAMPLE STREET SOMEWHERE ON A1A1A1
For questions about your statement call (000) 000-0000
Direct Banking 1-000-000-0000 www.bmo.com
Your Plan Enhanced Plan
Business Banking statement
For the period ending {period_end}
Summary of account
Total Total Closing Opening amounts amounts balance ($) on - + = Account balance ($) debited ($) credited ($) {period_end}
Business Account # 1234 1000-001 {opening} {debited} {credited} {closing}
Transaction details
Amounts debited Amounts credited Date Description from your account ($) to your account ($) Balance ($)
Business Account # 1234 1000-001
Account Type: CHQ BUS Business name: NORTHWIND SUPPLY LTD.
{opening_row} Opening balance {opening}
{rows}
{closing_row} Closing totals {debited} {credited}
Number of items processed {debit_count} .................................. {credit_count} ..........
Page 1 of 1
"""


def ca_statement(
    *,
    period_end="April 30, 2026",
    opening_row="Apr 01",
    closing_row="Apr 30",
    opening="1,000.00",
    debited="300.00",
    credited="500.00",
    closing="1,200.00",
    rows=(
        "Apr 02 Debit Card Purchase, SAMPLE MERCHANT 100.00 900.00",
        "Apr 03 Direct Deposit, SAMPLE PAYER 500.00 1,400.00",
        "Apr 04 INTERAC e-Transfer Sent 200.00 1,200.00",
    ),
    debit_count=2,
    credit_count=1,
):
    return CA_TEMPLATE.format(
        period_end=period_end,
        opening_row=opening_row,
        closing_row=closing_row,
        opening=opening,
        debited=debited,
        credited=credited,
        closing=closing,
        rows="\n".join(rows),
        debit_count=debit_count,
        credit_count=credit_count,
    )


def amounts(stmt):
    return [txn.amount for txn in stmt.transactions]


def test_f1_direction_comes_from_the_balance_column_not_from_the_wording():
    """The four-column grid flattens to one money cell plus a balance, so which
    money column the cell stood in is only recoverable from the balance BMO
    prints beside it.

    The three rows below are deliberately worded so that no vocabulary could
    separate them correctly: the middle row is the only credit, and the rule
    that finds it is `balance went up`.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement())
    assert amounts(stmt) == [-100.00, 500.00, -200.00]
    assert [txn.direction for txn in stmt.transactions] == ["debit", "credit", "debit"]
    assert [txn.running_balance for txn in stmt.transactions] == [900.0, 1400.0, 1200.0]


def test_f1_the_naive_same_wording_rule_is_what_this_fixture_refutes():
    """Identical descriptions, opposite directions. Any rule keyed on the words
    gets one of these two rows wrong; the printed balance gets both right.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement(
        opening="500.00", debited="75.00", credited="75.00", closing="500.00",
        rows=(
            "Apr 02 Miscellaneous Adjustment 75.00 425.00",
            "Apr 03 Miscellaneous Adjustment 75.00 500.00",
        ),
        debit_count=1, credit_count=1,
    ))
    assert amounts(stmt) == [-75.00, 75.00]


def test_f2_the_summary_of_account_row_is_the_statement_of_record():
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement())
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_total_credits == 500.00
    assert stmt.account_number == "1234 1000-001"
    assert stmt.currency == "CAD"
    # The identity the row prints closes, and the extracted ledger reproduces it.
    assert reconcile(stmt).ok


def test_f3_closing_totals_is_a_section_total_and_not_a_posting():
    """`Apr 30 Closing totals 300.00 500.00` prints the period totals under the
    two money columns. Read as a row it would double the ledger; it ends the
    grid instead, and nothing printed after it is a posting.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement())
    assert len(stmt.transactions) == 3
    assert all("Closing totals" not in txn.description for txn in stmt.transactions)
    assert all(txn.date != "2026-04-30" for txn in stmt.transactions)


def test_f4_number_of_items_processed_is_the_printed_row_count():
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement())
    assert stmt.stated_debit_count == 2
    assert stmt.stated_credit_count == 1


def test_f5_a_money_shaped_token_inside_a_description_is_not_the_amount():
    """BMO prints unit prices and exchange-rate operands inside the Description
    column (`13 ITMS AT 1.25`, `AT1.3285 HC $0.00,`). They stand to the left of
    the money columns, so the row's amount is the second-to-last cell — never
    the first money-shaped token on the line.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement(
        opening="500.00", debited="31.25", credited="0.00", closing="468.75",
        rows=(
            "Apr 02 Pre-Authorized Payment Fee, DEFT 13 ITMS AT 1.25 16.25 483.75",
            "Apr 03 Deposit Contents fee, CHQ 1 @ $0.10 15.00 468.75",
        ),
        debit_count=2, credit_count=0,
    ))
    assert amounts(stmt) == [-16.25, -15.00]
    assert stmt.transactions[0].description.endswith("13 ITMS AT 1.25")


def test_f6_the_account_number_is_not_read_as_a_money_column():
    """`Business Account # 1234 1000-001 1,000.00 ...` writes the account number
    as groups of digits separated by spaces — the same shape a printed amount
    has. The summary row must still find exactly four money cells.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement())
    assert stmt.account_number == "1234 1000-001"
    assert (stmt.beginning_balance, stmt.ending_balance) == (1000.00, 1200.00)


def test_f7_a_text_layer_that_dropped_its_inter_word_spacing_still_reads():
    """Some BMO PDFs render the same furniture without spaces between words.
    Only the gaps are optional — every money and date token is unchanged — so a
    document read this way still has to satisfy the printed ledger identity.
    """
    document = ca_statement().replace(
        "For the period ending", "Forthe period ending"
    ).replace("April 30, 2026", "April30, 2026").replace(
        "Apr 01 Opening balance", "Apr01 Openingbalance"
    ).replace("Business Account #", "BusinessAccount #")
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(document)
    assert stmt is not None
    assert stmt.period_start == "2026-04-01"
    assert stmt.period_end == "2026-04-30"
    assert reconcile(stmt).ok


def test_f8_the_period_starts_where_the_opening_balance_row_is_dated():
    """The opening row is the only start the statement prints, and it can fall
    in the previous calendar year.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement(
        period_end="January 31, 2026",
        opening_row="Dec 30", closing_row="Jan 31",
        rows=("Jan 05 Direct Deposit, SAMPLE PAYER 500.00 1,500.00",
              "Jan 06 INTERAC e-Transfer Sent 300.00 1,200.00"),
        debit_count=1, credit_count=1,
    ))
    assert stmt.period_start == "2025-12-30"
    assert stmt.period_end == "2026-01-31"
    assert [txn.date for txn in stmt.transactions] == ["2026-01-05", "2026-01-06"]


def test_f9_a_row_whose_amount_contradicts_its_balance_breaks_continuity():
    """The adversarial case. The balance movement orients a row; it never
    replaces the printed amount. A document whose printed amount and printed
    balance disagree must therefore fail the fail-closed gate rather than
    silently produce a ledger that reconciles with itself.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(ca_statement(
        rows=(
            "Apr 02 Debit Card Purchase, SAMPLE MERCHANT 100.00 900.00",
            "Apr 03 Direct Deposit, SAMPLE PAYER 500.00 1,400.00",
            # printed amount 200.00, but the printed balance moved by 300.00
            "Apr 04 INTERAC e-Transfer Sent 200.00 1,100.00",
        ),
    ))
    assert amounts(stmt) == [-100.00, 500.00, -200.00]
    result = reconcile(stmt)
    assert not result.ok
    assert result.continuity_breaks >= 1


def test_f10_a_summary_row_the_ledger_contradicts_is_reported():
    """Registered as this parser's integrity check: the `Closing totals` row is
    a second printing of the two period totals, and a document that prints two
    different answers is contradicting itself.
    """
    document = ca_statement().replace("Closing totals 300.00 500.00",
                                      "Closing totals 350.00 500.00")
    stmt = bmo_ca_business.parse_bmo_ca_business_statement(document)
    notes = bmo_ca_business.closing_totals_contradictions(document, stmt)
    assert notes == [
        "the summary of account and the ledger's closing totals state "
        "different period totals"
    ]
    assert bmo_ca_business.closing_totals_contradictions(
        ca_statement(), bmo_ca_business.parse_bmo_ca_business_statement(ca_statement())
    ) == []


# ---------------------------------------------------------------------------
# Family C — the same statement, French edition
# ---------------------------------------------------------------------------

CA_FR_TEMPLATE = """\
1 RUE MODELE MONTREAL,QUEBEC A1A1A1 Services bancaires aux entreprises
Adresse de votre succursale:
Votre succursale MODELE Numéro de domiciliation : 1234
SOCIÉTÉ MODÈLE INC. 1 RUE MODELE LAVAL QC A1A1A1
Pour toute question concernant le présent relevé, composez le (000) 000-0000
Services bancaires en direct 1-000-000-0000 www.bmo.com
Type de programme Programme Essentiel
Relevé de services bancaires aux entreprises
Période terminée le {period_end}
Sommaire de votre compte
Total Total Solde Solde des montants des montants de fermeture ($) - + = Compte d'ouverture ($) déduits ($) ajoutés ($) le {period_end}
Compte d'entreprise # 1234 1000-001 {opening} {debited} {credited} {closing}
Détails des transactions
Montants déduits Montants ajoutés Date Description de votre compte ($) à votre compte ($) Solde ($)
Compte d'entreprise # 1234 1000-001
Nom de l'entreprise : SOCIÉTÉ MODÈLE INC.
{opening_row} Solde d'ouverture {opening}
{rows}
{closing_row} Totaux à la fermeture {debited} {credited}
Nombre d'articles traités {debit_count} ........................... {credit_count} ......
Page 1 de 1
"""


def ca_fr_statement(
    *,
    period_end="30 Avril 2026",
    opening_row="1er Avr",
    closing_row="30 Avr",
    opening="1 000,00",
    debited="300,00",
    credited="500,00",
    closing="1 200,00",
    rows=(
        "02 Avr Achat par carte de débit, MARCHAND MODÈLE 100,00 900,00",
        "03 Avr Dépôt direct, PAYEUR MODÈLE 500,00 1 400,00",
        "04 Avr Virement INTERAC envoyé 200,00 1 200,00",
    ),
    debit_count=2,
    credit_count=1,
):
    return CA_FR_TEMPLATE.format(
        period_end=period_end, opening_row=opening_row, closing_row=closing_row,
        opening=opening, debited=debited, credited=credited, closing=closing,
        rows="\n".join(rows), debit_count=debit_count, credit_count=credit_count,
    )


def test_f11_the_french_edition_reads_fr_ca_money_and_french_dates():
    """`1 000,00` is one thousand, not one; `1er Avr` and `02 Avr` are the Date
    column. The grid, the summary identity and the direction rule are the
    English edition's — only the printed vocabulary differs.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_french_statement(ca_fr_statement())
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1200.00
    assert amounts(stmt) == [-100.00, 500.00, -200.00]
    assert [txn.date for txn in stmt.transactions] == [
        "2026-04-02", "2026-04-03", "2026-04-04"
    ]
    assert stmt.period_start == "2026-04-01"
    assert stmt.currency == "CAD"
    assert reconcile(stmt).ok


def test_f12_totaux_a_la_fermeture_ends_the_french_grid():
    stmt = bmo_ca_business.parse_bmo_ca_business_french_statement(ca_fr_statement())
    assert len(stmt.transactions) == 3
    assert all("fermeture" not in txn.description for txn in stmt.transactions)
    assert (stmt.stated_debit_count, stmt.stated_credit_count) == (2, 1)


def test_f13_the_french_account_number_is_not_read_as_fr_ca_money():
    """`# 1234 1000-001 1 000,00` is the hazard this edition adds: an account
    number written as space-separated digit groups is exactly the shape of an
    FR-CA amount. Only the group boundaries separate them.
    """
    stmt = bmo_ca_business.parse_bmo_ca_business_french_statement(ca_fr_statement())
    assert stmt.account_number == "1234 1000-001"
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_total_credits == 500.00


# ---------------------------------------------------------------------------
# Family B — BMO Bank N.A. (US), "Monthly Activity Details"
# ---------------------------------------------------------------------------

US_TEMPLATE = """\
How to reach us
P.O. BOX 00000, SOMEWHERE, IL 00000 Return Service Requested
bmo.com/contact 000-000-0000
NORTHWIND SUPPLY LLC 1 SAMPLE STREET SOMEWHERE FL 00000
Date {start} through {end} Primary Account Number
1000000001
BMO BANK N.A. MEMBER FDIC EQUAL HOUSING LENDER.
Statement Summary
ACCOUNT DESCRIPTION ACCOUNT NUMBER BALANCE
BMO SAMPLE BUSINESS CKG 1000000001 {ending}
CONTINUED ON NEXT PAGE
1 of 2
bmo.com/contact 000-000-0000
Account Summary - BMO SAMPLE BUSINESS CKG #1000000001
BEGINNING BALANCE AS OF {as_of} NUMBER OF DEPOSITS DEPOSIT AMOUNT NUMBER OF WITHDRAWALS WITHDRAWAL AMOUNT SERVICE CHARGES ENDING BALANCE AS OF {end_caps}
{beginning} {credit_count} {credits} {debit_count} {debits} {service} {ending}
Monthly Activity Details
Date Transaction description Withdrawal Deposit Balance
BEGINNING BALANCE {beginning}
{rows}
ENDING BALANCE {ending}
Account Summary - BMO SAMPLE BUSINESS CKG #1000000001
AVERAGE LEDGER BALANCE AVERAGE FLOAT AVERAGE COLLECTED BALANCE
{average} $10.00 $900.00
Service Charge Summary
Description Volume Units Amount
Checks Paid 3 $0.00 $0.00
Total Service Charges {service}
Checks in Serial Number Order
Date Serial Number Amount Date Serial Number Amount
Apr 02 1001 $500.00 Apr 09 1002 $250.00
2 of 2
"""


def us_statement(
    *,
    start="April 01, 2026",
    end="April 30, 2026",
    as_of="MARCH 31, 2026",
    end_caps="APRIL 30, 2026",
    beginning="$1,000.00",
    credit_count=1,
    credits="$500.00",
    debit_count=2,
    debits="$300.00",
    service="$0.00",
    ending="$1,200.00",
    average="$1,050.00",
    rows=(
        "Apr 02 POS PURCHASE ($100.00)",
        "RECORD NO. 000001   CARD NO. 0001",
        "SAMPLE MERCHANT            SOMEWHERE      FL",
        "Apr 03 ACH DEPOSIT $500.00 $1,400.00",
        "CCD SAMPLE PAYER",
        "Apr 04 TRANSFER OUT ($200.00) $1,200.00",
        "RECORD NO. 000002",
    ),
):
    return US_TEMPLATE.format(
        start=start, end=end, as_of=as_of, end_caps=end_caps, beginning=beginning,
        credit_count=credit_count, credits=credits, debit_count=debit_count,
        debits=debits, service=service, ending=ending, average=average,
        rows="\n".join(rows),
    )


def test_f14_the_bracket_is_the_printed_direction():
    """This layout brackets a withdrawal and prints a deposit bare. The
    direction needs no vocabulary and no balance arithmetic — but the days on
    which a balance IS printed check it.
    """
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement())
    assert amounts(stmt) == [-100.00, 500.00, -200.00]
    assert [txn.direction for txn in stmt.transactions] == ["debit", "credit", "debit"]


def test_f15_the_balance_column_is_printed_only_on_the_last_row_of_a_day():
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement())
    assert [txn.running_balance for txn in stmt.transactions] == [None, 1400.0, 1200.0]
    assert reconcile(stmt).ok


def test_f16_a_wrapped_description_neither_opens_a_row_nor_carries_money():
    """`RECORD NO.`, the card number and the merchant location stand in the
    Description column under the row. They must not become rows of their own.
    """
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement())
    assert len(stmt.transactions) == 3
    assert [txn.description for txn in stmt.transactions] == [
        "POS PURCHASE", "ACH DEPOSIT", "TRANSFER OUT"
    ]


def test_f17_the_summary_row_carries_both_totals_both_counts_and_the_charge():
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement(
        service="$7.50", ending="$1,192.50",
    ))
    assert stmt.beginning_balance == 1000.00
    assert stmt.ending_balance == 1192.50
    assert stmt.stated_total_credits == 500.00
    assert stmt.stated_total_debits == 300.00
    assert stmt.stated_credit_count == 1
    assert stmt.stated_debit_count == 2
    assert stmt.stated_service_charge == 7.50
    assert stmt.account_number == "1000000001"


def test_f18_the_printed_average_ledger_balance_is_carried_as_stated_evidence():
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement())
    assert stmt.stated_average_balance == 1050.00


def test_f19_ending_balance_closes_the_grid_before_the_check_listing():
    """`Checks in Serial Number Order` prints dated rows with amounts after the
    ledger has closed. They are a listing of postings already in the ledger; a
    grid that did not end at `ENDING BALANCE` would count them twice.
    """
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement())
    assert len(stmt.transactions) == 3
    assert all("Serial" not in txn.description for txn in stmt.transactions)
    assert reconcile(stmt).ok


def test_f20_a_bracketed_ending_balance_is_a_negative_balance():
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(us_statement(
        beginning="$100.00", credits="$0.00", credit_count=0,
        debits="$300.00", debit_count=1, ending="($200.00)",
        rows=("Apr 02 POS PURCHASE ($300.00) ($200.00)",),
    ))
    assert stmt.beginning_balance == 100.00
    assert stmt.ending_balance == -200.00
    assert amounts(stmt) == [-300.00]
    assert stmt.transactions[0].running_balance == -200.00
    assert reconcile(stmt).ok


def test_f21_a_ledger_that_contradicts_the_summary_closing_balance_is_reported():
    document = us_statement().replace("ENDING BALANCE $1,200.00",
                                      "ENDING BALANCE $1,250.00")
    stmt = bmo_us_activity.parse_bmo_us_activity_statement(document)
    assert bmo_us_activity.summary_row_contradictions(document, stmt) == [
        "the account summary and the activity ledger state different "
        "closing balances"
    ]
    assert bmo_us_activity.summary_row_contradictions(
        us_statement(), bmo_us_activity.parse_bmo_us_activity_statement(us_statement())
    ) == []


# ---------------------------------------------------------------------------
# Negatives — each constrains a rule this cell added
# ---------------------------------------------------------------------------

#: The layout `analysis/bmo.py` already claims. Reproduced structurally, not
#: copied: the point is that its evidence is a different set of headings.
BMO_SUMMARY_TOTALS_LAYOUT = (
    "BMO Bank of Montreal\n"
    "Statement Period: April 2026\n"
    "Currency: CAD\n"
    "Account Number: 1000000001\n"
    "Account Summary\n"
    "Transaction Details Date Description Withdrawal Deposit Balance\n"
    "04/02 SAMPLE ROW $ 100.00 $ 900.00\n"
    "Account Summary Totals\n"
    "Total Deposits $ 500.00 Total Withdrawals $ 300.00\n"
)


@pytest.mark.parametrize("detector", [
    bmo_ca_business.detect,
    bmo_ca_business.detect_french,
    bmo_us_activity.detect,
])
def test_negative_the_pre_existing_bmo_layout_is_not_claimed_by_a_new_one(detector):
    assert not detector(BMO_SUMMARY_TOTALS_LAYOUT).claims


def test_negative_the_pre_existing_bmo_registration_does_not_claim_the_new_layouts():
    """The other direction of the same disjointness. `analysis/bmo.py` requires
    `ACCOUNT SUMMARY TOTALS`, which none of these three layouts prints — which
    is why no `supersedes` edge is needed and no document becomes ambiguous.
    """
    for document in (ca_statement(), ca_fr_statement(), us_statement()):
        assert not bmo.detect(document).claims


@pytest.mark.parametrize("detector", [
    bmo_ca_business.detect,
    bmo_ca_business.detect_french,
    bmo_us_activity.detect,
])
def test_negative_the_issuer_domain_alone_is_not_a_claim(detector):
    """`bmo.com` on someone else's statement — a bill-payment biller list, a
    wire instruction — is one marker. No registration here identifies BMO by
    one marker.
    """
    assert not detector(
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "04/02 ONLINE TRANSFER TO BMO www.bmo.com REF 000000 100.00\n"
        "04/03 WIRE TO BMO BANK N.A. bmo.com/contact 250.00\n"
    ).claims


def test_negative_the_french_edition_is_not_claimed_by_the_english_registration():
    assert not bmo_ca_business.detect(ca_fr_statement()).claims
    assert not bmo_ca_business.detect_french(ca_statement()).claims


def test_negative_the_canadian_and_us_layouts_do_not_claim_each_other():
    assert not bmo_us_activity.detect(ca_statement()).claims
    assert not bmo_us_activity.detect(ca_fr_statement()).claims
    assert not bmo_ca_business.detect(us_statement()).claims
    assert not bmo_ca_business.detect_french(us_statement()).claims


def test_negative_a_header_without_a_ledger_is_not_parsed():
    """Self-invalidation, at the parser rather than the registry level: the
    summary alone is not a statement this parser can publish.
    """
    header, _, _ = ca_statement().partition("Transaction details")
    assert bmo_ca_business.parse_bmo_ca_business_statement(header) is None
    us_header, _, _ = us_statement().partition("Monthly Activity Details")
    assert bmo_us_activity.parse_bmo_us_activity_statement(us_header) is None


@pytest.mark.parametrize("document,expected", [
    (ca_statement(), "bmo_ca_business"),
    (ca_fr_statement(), "bmo_ca_business_french"),
    (us_statement(), "bmo_us_activity"),
    (BMO_SUMMARY_TOTALS_LAYOUT, "bmo"),
])
def test_each_layout_resolves_to_exactly_one_registration(document, expected):
    """The ambiguity protection, exercised rather than assumed: four BMO
    documents, four single claimants, no `ambiguous` outcome anywhere.
    """
    dispatch = resolve(document)
    assert dispatch.outcome == "claimed", dispatch.candidates
    assert dispatch.parser_id == expected
    assert len(dispatch.candidates) == 1

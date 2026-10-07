"""Fabricated statements for the Zelle setting (the owner's amendment of 2026-10-06 to the underwriter's Q3; R2-OW17):
Bank of America rows, dates in March 2054, holders and senders CONTOSO / FABRIKAM / NORTHWIND / SAMPLE, neutral amounts.
Each case is analysed by the real pipeline (analysis/pipeline.py analyze_statement, every row with its running
balance so the statement reconciles) and published by analysis/serialization.py. The builder reads only APIs the tree
had before R2-OW17, so tests/fixtures/zelle_setting_no_view.json was written with it from R2-OW16's tip."""
from __future__ import annotations

HOLDER = "CONTOSO BAKERY LLC"
BANK = "Bank of America"
ACCOUNT = "000000001234"
SALE = "FABRIKAM SUPPLY INC DES:PAYMENT ID:0001 INDN:CONTOSO BAKERY LLC CO ID:0000000001 CCD"
KAPITUS = "KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD"
PAT = "ZELLE PAYMENT FROM PAT SAMPLE CONF# A1B2C3D4E"
FABRIKAM_1 = "ZELLE PAYMENT FROM FABRIKAM LANDSCAPING LLC CONF# A1B2C3D4F"
FABRIKAM_2 = "ZELLE PAYMENT FROM FABRIKAM LANDSCAPING LLC CONF# B1B2C3D4F"
OWN = "ZELLE PAYMENT FROM CONTOSO BAKERY LLC CONF 99"
VENMO = "VENMO CASHOUT PPD ID: 5264681992"
TRUCK = "ZELLE PAYMENT FROM PAT SAMPLE FOR TRUCK SALE CONF ABC123"
DRAW = "ZELLE PAYMENT FROM CONTOSO BUILDERS INC FOR DRAW 3 CONF ABC123"
BOUNCE = "ZELLE PAYMENT FROM PAT SAMPLE NOT PAID CONF 7"

# (description, amount, day[, direction]); a row whose direction is given prints that direction whatever its sign.
Z1 = [
    (SALE, 10000.00, 2), (PAT, 1234.56, 3), (FABRIKAM_1, 2000.00, 4), (FABRIKAM_2, 2000.00, 5), (OWN, 2500.00, 6),
    (VENMO, 300.00, 7), (KAPITUS, -850.00, 9),
]
Z2 = [(PAT, 1500.00, 3), ("KAPITUS DES:PAYMENT ID:000000001 INDN:CONTOSO BAKERY LLC CO ID:0000000002 CCD", -150.00, 9)]
Z3 = [("ZELLE PAYMENT FROM SAMPLE PERSON CONF 1234567890", 900.00, 3), ("DEPOSIT", 2345.67, 4)]
Z4_TRUCK = [(TRUCK, 9000.00, 3)]
Z4_DRAW = [(DRAW, 9000.00, 3)]
Z4_TENANTS = [("ZELLE PAYMENT FROM PAT SAMPLE RENT UNIT 2 CONF 11", 1450.00, 1),
              ("ZELLE PAYMENT FROM JO SAMPLE RENT UNIT 3 CONF 12", 1325.00, 2)]
LEASE = "CONTOSO DENTAL LLC DES:LEASE PMT ID:0001 INDN:NORTHWIND HOLDINGS LLC CO ID:0000000001 PPD"
THIRD_RENT = "FABRIKAM CAFE LLC DES:RENT ID:0002 INDN:NORTHWIND HOLDINGS LLC CO ID:0000000003 PPD"
Z4_LESSOR = [*Z4_TENANTS, (LEASE, 2200.00, 3)]
Z4_LESSOR_COMPLETE = [*Z4_LESSOR, (THIRD_RENT, 1800.00, 4)]
# A Zelle sale beside a second credit of the same sender on the same (channel, key) group.
Z4_PARTNER = [("ZELLE PAYMENT FROM FABRIKAM LANDSCAPING LLC FOR TRUCK SALE CONF 1", 9000.00, 3),
              ("VENMO FROM FABRIKAM LANDSCAPING LLC", 1250.00, 9)]
Z5 = [(KAPITUS, -850.00, 2), (BOUNCE, 850.00, 3)]
Z5_RETURNED = [(KAPITUS, -850.00, 2), ("ZELLE PAYMENT FROM PAT SAMPLE CREDIT RETURNED CONF 7", 850.00, 3)]
Z5_NSF = [(KAPITUS, -850.00, 2), ("ZELLE PAYMENT FROM PAT SAMPLE NSF CONF 7", 850.00, 3)]
Z6 = [("ZELLE PAYMENT FROM PAT SAMPLE CONF 1", 0.75, 3), ("ZELLE PAYMENT FROM PAT SAMPLE CONF 2", 125.00, 9)]
# R2-OW02's controls: a listed funder's Zelle credit, a direction conflict and a refund a non-revenue rule decides.
Z7 = [("ZELLE PAYMENT FROM FORWARD FINANCING CONF 1", 5000.00, 3), ("ZELLE PAYMENT TO PAT SAMPLE CONF 1", 400.00, 4,
                                                                       "debit"),
      ("ZELLE PAYMENT FROM PAT SAMPLE FOR REFUND CONF 1", 799.50, 5)]
FREE = [(SALE, 10000.00, 2), (VENMO, 300.00, 7), (KAPITUS, -850.00, 9)]

#: name -> (rows, holder, title)
CASES = {
    "Z1": (Z1, HOLDER, None),
    "Z2": (Z2, HOLDER, None),
    "Z3": (Z3, "CONTOSO INSURANCE AGENCY LLC", "PREMIUM TRUST ACCOUNT"),
    "Z4_TRUCK": (Z4_TRUCK, "NORTHWIND SOLAR LLC", None),
    "Z4_DRAW": (Z4_DRAW, "NORTHWIND SOLAR LLC", None),
    "Z4_LESSOR": (Z4_LESSOR, "NORTHWIND HOLDINGS LLC", None),
    "Z4_LESSOR_COMPLETE": (Z4_LESSOR_COMPLETE, "NORTHWIND HOLDINGS LLC", None),
    "Z4_PARTNER": (Z4_PARTNER, "NORTHWIND SOLAR LLC", None),
    "Z5": (Z5, HOLDER, None),
    "Z5_RETURNED": (Z5_RETURNED, HOLDER, None),
    "Z5_NSF": (Z5_NSF, HOLDER, None),
    "Z6": (Z6, HOLDER, None),
    "Z7": (Z7, HOLDER, None),
}


def statement(rows, *, holder=HOLDER, title=None, bank=BANK, number=ACCOUNT, opening=1000.0, month=3,
              currency="USD", year=2054):
    """The fabricated statement of `rows`, each row with its running balance."""
    from analysis.schema import Statement, Transaction

    transactions, balance = [], opening
    for text, amount, day, *direction in rows:
        balance = round(balance + amount, 2)
        transactions.append(Transaction(
            date=f"{year}-{month:02d}-{day:02d}", description=text, amount=amount,
            direction=direction[0] if direction else ("credit" if amount > 0 else "debit"), running_balance=balance,
        ))
    fields = dict(bank=bank, account_name=holder, account_number=number, period_start=f"{year}-{month:02d}-01",
                  period_end=f"{year}-{month:02d}-28", beginning_balance=opening, ending_balance=balance,
                  currency=currency, currency_source="printed", transactions=transactions)
    if title:
        fields["account_title"] = title
    return Statement(**fields)


def document(rows, **kwargs):
    """The DocumentReport of `rows`, analysed by the real pipeline."""
    from analysis.pipeline import analyze_statement
    from analysis.reconcile import reconcile

    built = statement(rows, **kwargs)
    return analyze_statement(built, reconciliation=reconcile(built), markdown="", sheets=[],
                             model_used="fabricated-test")


def payload(rows, **kwargs):
    """The stored payload of `rows` (analysis/serialization.py document_report_to_dict)."""
    from analysis.serialization import document_report_to_dict

    return document_report_to_dict(document(rows, **kwargs))


def case(name: str, **kwargs):
    rows, holder, title = CASES[name]
    return payload(rows, holder=holder, title=title, **kwargs)


def case_document(name: str, **kwargs):
    rows, holder, title = CASES[name]
    return document(rows, holder=holder, title=title, **kwargs)


def row(payload_or_account, text):
    """The transaction dict of the first row printing `text`."""
    return next(transaction for transaction in payload_or_account["statement"]["transactions"]
                if transaction["description"] == text)

"""The five issuer-furniture markers, positive and negative (R-3.4).

Five parsers
identified their bank by a bare name substring, which also matched when that
bank appeared as a *counterparty* in someone else's statement — a Capital One
card payment, a BMO wire, a Regions ACH originator. Chain order hid it; the
registry did not. Each now also requires evidence the issuer prints on its own
statements.

R-4b extended the same remedy to six more parsers that R-4's synthetic
cross-product caught (finding R4-3). The corpus contains no statement naming
those six as a counterparty, so only a synthetic foreign statement could expose
them; their negative fixtures carry the wire/ACH boilerplate the real world puts
on other banks' statements.

Each marker gets two tests:

* **detection-positive** — a minimal document carrying the issuer furniture is
  claimed. (Corpus-wide coverage is `tests/test_parser_parity.py`; this is the
  direct fixture Ocean asked for alongside it.)
* **detection-negative** — a document whose *only* mention of the bank is a
  transaction line is NOT claimed. Each negative fixture reproduces the exact
  counterparty text observed in a named corpus document, cited in the test.

The negatives are the point. A parser that quietly claims another bank's
statement is the failure mode R-3 exists to prevent, and it is invisible to
arithmetic checks: a wrong parse that happens to reconcile corrupts a real
result and the discovery statistics alike.
"""
from __future__ import annotations

import pytest

from analysis import (
    bmo,
    bofa,
    capital_one,
    chase,
    community_section,
    consumers,
    first_citizens,
    regions,
    scotia,
    texas_bank,
)

#: (parser module, human name, positive document, negative document, the corpus
#: document the negative reproduces).
CASES = [
    pytest.param(
        capital_one,
        "capital_one",
        "CAPITAL ONE\nAN IMPORTANT MESSAGE TO OUR CLIENTS\nAccount Summary\n",
        "TRUIST\nAccount summary Your previous balance\n"
        "03/23 CONVERTED CHECK-ARC CHECK PYMT CAPITAL ONE ARC 0020720 727.93\n",
        "Truist/Truist April, 2026.pdf",
        id="capital_one",
    ),
    pytest.param(
        bmo,
        "bmo",
        "BMO BANK OF MONTREAL\nAccount Summary Totals\n",
        "JPMorgan Chase Bank\n"
        "03/16 ZELLE PAYMENT FROM PROGRESSIVE LEASING BREACH LITIGATI BMOZ000RIJ8B 129.54\n",
        "Chase/Chase Mar.pdf",
        id="bmo",
    ),
    pytest.param(
        regions,
        "regions",
        "REGIONS BANK\nSUMMARY\nThank you for banking with Regions!\n",
        "americanexpress.com/businesscheckinghome\nBusiness Checking Account Statement\nSUMMARY\n"
        "XX8ZKF PSCBATH EXTERNAL - JACK HENRY CO/ REGIONS BANK ID 009002514875552\n",
        "Amex/Amex Apr2026.pdf",
        id="regions",
    ),
    pytest.param(
        bofa,
        "bank_of_america",
        "BANK OF AMERICA\nACCOUNT SUMMARY\nbankofamerica.com\n",
        "TD Bank, N.A.\nSTATEMENT OF ACCOUNT\nACCOUNT SUMMARY\n"
        "04/06 ELECTRONIC PMT-TEL, BANK OF AMERICA PAYMENT J9JXBE69W 2,500.00\n",
        "TD/TD BANK NARROW APR.pdf",
        id="bank_of_america",
    ),
    pytest.param(
        scotia,
        "scotiabank",
        "SCOTIABANK\nAccount Details:\nThe Bank of Nova Scotia\n",
        "Santander\nAccount Activity\n"
        "04-17 USD WIRE IN FROM SCOTIABANK CHIL ACCT * 9246 SOC COMERCIALIZA REF PAYMENT\n",
        "Others/Santander/Santander_April26.pdf",
        id="scotiabank",
    ),
    pytest.param(
        chase,
        "chase",
        "JPMorgan Chase Bank\n*start*summary\n",
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 WIRE IN FED#0902 JPMorgan Chase Bank, N.A. /BNF/ACME LLC 4,000.00\n",
        "R4-3: industry-wide wire boilerplate; Chase is the largest discovery folder (618 docs)",
        id="chase",
    ),
    pytest.param(
        consumers,
        "consumers",
        "Consumers Credit Union\nSummary of All Accounts\n",
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ACH DEBIT PAYMENT TO Consumers Credit Union 250.00\n",
        "R4-3: a loan payment to the credit union",
        id="consumers",
    ),
    pytest.param(
        community_section,
        "dakota_west",
        "dakotawestcu.com\nThank you for being a member of Dakota West Credit Union.\n",
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ACH DEBIT PAYMENT TO dakotawestcu.com 250.00\n",
        "R4-3: a payment citing the credit union's domain",
        id="dakota_west",
    ),
    pytest.param(
        first_citizens,
        "first_citizens",
        "First Citizens\nYour Account(s) At A Glance\n",
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ACH DEBIT PAYMENT TO First Citizens 250.00\n",
        "R4-3: a card payment to the bank",
        id="first_citizens",
    ),
    pytest.param(
        community_section,
        "mission_valley",
        "Mission Valley Bank\nOnline Banking www.missionvalleybank.com\n",
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ACH DEBIT PAYMENT TO Mission Valley Bank 250.00\n",
        "R4-3: a payment to the bank",
        id="mission_valley",
    ),
    pytest.param(
        texas_bank,
        "texas_bank",
        "Texas Bank and Trust\nWITHDRAWALS AND OTHER DEBITS (CONTINUED)\n",
        "COMMUNITY TRUST BANK\nStatement of Account\n"
        "01/15 ACH DEBIT PAYMENT TO Texas Bank and Trust 250.00\n",
        "R4-3: a payment to the bank",
        id="texas_bank",
    ),
]


#: `community_section` hosts two parsers, so its detectors are named.
DETECTORS = {"dakota_west": "detect_dakota_west", "mission_valley": "detect_mission_valley"}


def _detect(module, name, document):
    return getattr(module, DETECTORS.get(name, "detect"))(document)


@pytest.mark.parametrize("module,name,positive,negative,evidence", CASES)
def test_detection_positive_issuer_furniture_is_recognised(
    module, name, positive, negative, evidence
):
    detection = _detect(module, name, positive)
    assert detection.claims, f"{name} no longer recognises its own statement: {detection}"


@pytest.mark.parametrize("module,name,positive,negative,evidence", CASES)
def test_detection_negative_a_counterparty_mention_is_not_a_claim(
    module, name, positive, negative, evidence
):
    """Reproduces the counterparty text from the cited corpus document."""
    detection = _detect(module, name, negative)
    assert not detection.claims, (
        f"{name} claims a document that only mentions the bank in a transaction "
        f"line; reproduced from {evidence} (detection={detection})"
    )


@pytest.mark.parametrize("module,name,positive,negative,evidence", CASES)
def test_a_counterparty_mention_still_scores_above_nothing(
    module, name, positive, negative, evidence
):
    """Near-misses stay visible.

    The bank name really is present, so the score must not collapse to zero —
    that distinction is what lets DSC-2 tell "almost matched" apart from "never
    heard of this bank" when it ranks unknown-layout clusters.
    """
    detection = _detect(module, name, negative)
    assert 0.0 < detection.score < 0.5, f"{name}: expected a weak score, got {detection}"


def test_scotiabank_no_longer_detects_on_an_account_number_fragment():
    """R-1 residual: the old guard also accepted `BUSINESS ACCOUNT 01180`.

    That is an account-number fragment, not issuer evidence. It is gone; a
    document carrying it but no Scotiabank identity must not be claimed.
    """
    assert not scotia.detect("BUSINESS ACCOUNT 01180\nStatement\n").claims


@pytest.mark.parametrize("module,name,positive,negative,evidence", CASES)
def test_bare_bank_name_alone_is_never_enough(module, name, positive, negative, evidence):
    """The heart of the finding, stated per parser."""
    for bare in (
        "CAPITAL ONE", "BMO", "REGIONS BANK", "BANK OF AMERICA", "SCOTIABANK",
        "JPMorgan Chase Bank", "Consumers Credit Union", "dakotawestcu.com",
        "First Citizens", "Mission Valley Bank", "Texas Bank and Trust",
    ):
        assert not _detect(module, name, f"Some other bank's statement\n{bare}\n").claims


# --- IBC: the issuer marker must not fire inside another bank's name ----------
# (audit 2026-10-13 PARSERS-8). The marker was the substring "IBC", which every
# CIBC statement prints ("CIBC") and which RBC/TD/BMO documents carry in
# counterparty text, so IBC's claim rested on its product phrase alone and a
# false `ibc` near-miss was published for every such document. The marker is
# now the WORD IBC. Fabricated fixtures; account numbers are zeros.

_IBC_PRODUCT = "Biz Rite Account Recap Account Number: 0000\n"


@pytest.mark.parametrize("text", [
    "CIBC\nAccount Summary\n",
    "CIBC Bank USA\nAccount Summary\n",
    "www.cibc.com\nAccount Summary\n",
    "CONTOSO TRADING\n01/15 WIRE FROM CIBC REF 0000 250.00\n",
])
def test_the_ibc_bank_name_marker_does_not_fire_inside_another_name(text):
    from analysis import ibc

    detection = ibc.detect(text)
    assert "bank_name" not in detection.matched, detection
    assert detection.score == 0.0, detection


def test_another_banks_statement_quoting_the_ibc_product_phrase_is_not_claimed():
    """The latent hazard: before, a CIBC document that printed IBC's product
    phrase scored 0.5 and was claimed by IBC."""
    from analysis import ibc

    detection = ibc.detect("CIBC Bank USA\n" + _IBC_PRODUCT)
    assert not detection.claims, detection
    assert "bank_name" not in detection.matched


@pytest.mark.parametrize("header", ["IBC", "IBC BANK", "WWW.IBC.COM", "Member FDIC IBC"])
def test_ibc_still_recognises_its_own_name(header):
    from analysis import ibc

    detection = ibc.detect(f"{header}\n" + _IBC_PRODUCT)
    assert detection.claims, detection


def test_the_ibc_name_alone_is_never_enough():
    from analysis import ibc

    assert not ibc.detect("Some other bank's statement\nIBC\n").claims

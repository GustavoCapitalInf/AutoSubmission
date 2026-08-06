"""The five issuer-furniture markers, positive and negative (R-3.4).

Background: `docs/moneythumb-replacement/R3_DETECTION_FINDING.md`. Five parsers
identified their bank by a bare name substring, which also matched when that
bank appeared as a *counterparty* in someone else's statement — a Capital One
card payment, a BMO wire, a Regions ACH originator. Chain order hid it; the
registry did not. Each now also requires evidence the issuer prints on its own
statements.

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

from analysis import bmo, bofa, capital_one, regions, scotia

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
]


@pytest.mark.parametrize("module,name,positive,negative,evidence", CASES)
def test_detection_positive_issuer_furniture_is_recognised(
    module, name, positive, negative, evidence
):
    detection = module.detect(positive)
    assert detection.claims, f"{name} no longer recognises its own statement: {detection}"


@pytest.mark.parametrize("module,name,positive,negative,evidence", CASES)
def test_detection_negative_a_counterparty_mention_is_not_a_claim(
    module, name, positive, negative, evidence
):
    """Reproduces the counterparty text from the cited corpus document."""
    detection = module.detect(negative)
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
    detection = module.detect(negative)
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
    for bare in ("CAPITAL ONE", "BMO", "REGIONS BANK", "BANK OF AMERICA", "SCOTIABANK"):
        assert not module.detect(f"Some other bank's statement\n{bare}\n").claims

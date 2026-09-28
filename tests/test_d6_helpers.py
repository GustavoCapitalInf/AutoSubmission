"""5.3 (2026-09-27): the shared helpers every new D6 skip and rule reads. Fabricated descriptors only."""
from __future__ import annotations

import re

import pytest

from analysis.description_text import normalize_transaction_description as normalize
from analysis.transaction_classifier import _LEGAL_FORM_SUFFIXES, _names_financing, _skips


@pytest.mark.parametrize(
    "printed",
    [
        "FABRIKAM KOVOCREDIT", "FAB CONSTRULOANS", "FAB BYZFUNDER", "FAB GRP FUNDIN INVOICE", "FAB CAPITA INVOICES",
        "FABCO RECOVERY LLC", "FAB RECEIVABLES", "FAB COLLECTIONS", "FAB CLICKLEASE", "FAB LENDINGSERVICES",
        "FAB CAP LLC", "FAB MCA", "FAB RTR PMT", "FAB DAILY PMT", "FAB FINL", "FAB ACCEPTANCE CORP",
        "FAB MORTGAGE SERV", "FAB EQUIP", "FAB FACTORING", "FAB MERCHANT SVCS", "FAB REMITTANCE",
        # the card verifier's REQUIRED roots: a settlement payee, CRED-prefixed names, ACCEPT
        "FAB DEBT SETTLEMENT", "FAB SETTLE", "CREDIBLYCO", "CREDORA", "FAB CRED", "FAB ACCEPT CORP",
        "FAB DEBT SETTLEMENT, BROOKLYN, NY", "FAB DEBT SETTLEMENT Card spend", "CREDIBLYCO, BROOKLYN, NY",
        "ZEL TO FAB SETTLEMENT PNCAA0X7654321",
    ],
)
def test_the_veto_reads_run_together_cut_and_collector_names(printed):
    assert _names_financing(normalize(printed))


@pytest.mark.parametrize(
    "printed",
    ["FAB MART SPRINGFIELD IL", "CINTAS CORP", "PAT EXAMPLE", "FAB STREAMING CO", "ZEL TO PAT EXAMPLE", "KOODO MOBILE",
     "FAB INCREDIBLE PIZZA"],  # CRED is a root only before IT, ORA, IBLY or a word end
)
def test_rows_that_name_no_financing_are_not_vetoed(printed):
    assert not _names_financing(normalize(printed))


def test_the_skips_own_words_never_veto_it():
    text = normalize("Orig CO Name:Stash Capital Orig ID:0000 Ind Name:Pat Example")
    assert _names_financing(text)
    assert not _names_financing(text, besides="STASH CAPITAL")


def test_a_skip_fires_on_its_region_only_when_the_rest_of_the_row_names_no_financing():
    patterns = (re.compile(r"\bFAB WORD\b"),)
    assert _skips("FAB WORD 0001", patterns, "FAB WORD 0001 PAT EXAMPLE")
    assert not _skips("FAB WORD 0001", patterns, "FAB WORD 0001 FAB CAPITAL LLC")
    assert not _skips("NOTHING HERE", patterns, "NOTHING HERE FAB WORD")  # read on the region, not the row


def test_the_legal_form_suffixes():
    assert _LEGAL_FORM_SUFFIXES == frozenset({
        "LLC", "INC", "CORP", "CORPORATION", "COMPANY", "INCORPORATED", "LTD", "LIMITED", "LP", "LLP", "PLLC",
    })
